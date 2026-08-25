"""Lightweight persistent FISIS cache for expanded management intelligence.

The proven base management cache is intentionally left untouched.  This store
collects only the recent quarters needed by the funding, soundness and
profitability views and persists them under a separate Upstash/local key.
FISIS authentication is read only by fisis_management on the Render server and
is never returned by these APIs.
"""

import json
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta
from pathlib import Path


SCHEMA_VERSION = 4
CACHE_KEY = "sbrate:management:intelligence:v1"
CACHE_MAX_AGE = timedelta(days=14)
MAX_QUARTERS = 6
BASE_DIR = Path(__file__).resolve().parent
LOCAL_CACHE = BASE_DIR / "data" / "management" / "fisis_intelligence.json"

# Only fields that are not already supplied by the stable base management store.
# One FISIS call is made per table/bank for a short recent-quarter range.
TABLES = {
    "SE028": {
        "deposits": "A1",
        "time_deposits": "A14",
    },
    "SE031": {
        "personal_deposits": "A",
        "corporate_deposits": "B",
        "sole_prop_deposits": "B1",
    },
    "SE006": {
        "operating_profit": "C",
    },
    "SE010": {
        "roa": "C",
        "roe": "D",
    },
    "SE014": {
        "net_interest_income": "A",
        "interest_income": "A1",
        "loan_interest_income": "A13",
        "interest_expense": "B1",
        "deposit_interest_expense": "B11",
        "time_deposit_interest_expense": "B115",
    },
    "SE008": {
        "fixed_below_loans": "A3",
        "npl_ratio_detail": "A4",
        "allowance_balance": "A6",
        "npl_coverage_ratio": "A9",
    },
    "SE011": {
        "liquidity_ratio": "A",
    },
    "SE036": {
        "industry_corporate_loans": "A",
        "real_estate_industry_loans": "A6",
    },
}

METRIC_KIND = {
    "deposits": "amount",
    "time_deposits": "amount",
    "personal_deposits": "amount",
    "corporate_deposits": "amount",
    "sole_prop_deposits": "amount",
    "operating_profit": "amount",
    "roa": "ratio",
    "roe": "ratio",
    "net_interest_income": "amount",
    "interest_income": "amount",
    "loan_interest_income": "amount",
    "interest_expense": "amount",
    "deposit_interest_expense": "amount",
    "time_deposit_interest_expense": "amount",
    "fixed_below_loans": "amount",
    "npl_ratio_detail": "ratio",
    "allowance_balance": "amount",
    "npl_coverage_ratio": "ratio",
    "liquidity_ratio": "ratio",
    "industry_corporate_loans": "amount",
    "real_estate_industry_loans": "amount",
}

_MEMORY_LOCK = threading.Lock()
_MEMORY_STORE = None
_REFRESH_LOCK = threading.Lock()
_REFRESH_THREAD = None
_REFRESH_STATE = {
    "running": False,
    "started_at": None,
    "finished_at": None,
    "company_total": 0,
    "company_done": 0,
    "errors": [],
}


def _quarter_rank(key):
    match = re.fullmatch(r"(\d{4})Q([1-4])", str(key or ""))
    return int(match.group(1)) * 4 + int(match.group(2)) if match else -1


def _quarter_month(key):
    match = re.fullmatch(r"(\d{4})Q([1-4])", str(key or ""))
    if not match:
        return None
    return f"{match.group(1)}{int(match.group(2)) * 3:02d}"


def _base_store():
    import fisis_management as fm
    return fm.get_management_store(trigger_refresh=True) or {}


def _target_quarters():
    base = _base_store()
    quarters = base.get("quarters") if isinstance(base.get("quarters"), dict) else {}
    ordered = sorted(quarters.keys(), key=_quarter_rank, reverse=True)
    return ordered[:MAX_QUARTERS]


def _cache_age(store):
    import fisis_management as fm
    value = str((store or {}).get("updated_at") or "").strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            from datetime import datetime
            dt = datetime.strptime(value, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=fm.KST)
            return fm._now() - dt.astimezone(fm.KST)
        except Exception:
            pass
    return None


def _cache_is_fresh(store):
    if int((store or {}).get("schema_version") or 0) < SCHEMA_VERSION:
        return False
    quarters = (store or {}).get("quarters")
    if not isinstance(quarters, dict) or len(quarters) < 2:
        return False
    targets = _target_quarters()
    if not targets or str((store or {}).get("target_latest") or "") != targets[0]:
        return False
    age = _cache_age(store)
    return age is not None and age <= CACHE_MAX_AGE


def _load_upstash():
    import fisis_management as fm
    raw = fm._upstash_command(["GET", CACHE_KEY])
    if not raw:
        return None
    value = json.loads(raw)
    return value if isinstance(value, dict) else None


def _save_upstash(store):
    import fisis_management as fm
    raw = json.dumps(store, ensure_ascii=False, separators=(",", ":"))
    fm._upstash_command(["SET", CACHE_KEY, raw], timeout=20)


def _load_local():
    try:
        with LOCAL_CACHE.open("r", encoding="utf-8-sig") as f:
            value = json.load(f)
        return value if isinstance(value, dict) else None
    except Exception:
        return None


def _save_local(store):
    try:
        LOCAL_CACHE.parent.mkdir(parents=True, exist_ok=True)
        with LOCAL_CACHE.open("w", encoding="utf-8") as f:
            json.dump(store, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        print("FISIS INTELLIGENCE LOCAL CACHE SAVE ERROR:", exc)


def _load_store_once():
    try:
        value = _load_upstash()
        if value:
            return value
    except Exception as exc:
        print("FISIS INTELLIGENCE UPSTASH LOAD ERROR:", exc)
    return _load_local() or {}


def get_intelligence_store(trigger_refresh=True):
    global _MEMORY_STORE
    with _MEMORY_LOCK:
        if _MEMORY_STORE is None:
            _MEMORY_STORE = _load_store_once()
        store = _MEMORY_STORE or {}
    if trigger_refresh and not _cache_is_fresh(store):
        trigger_intelligence_refresh(force=False)
    return store


def get_intelligence_refresh_state():
    with _REFRESH_LOCK:
        return dict(_REFRESH_STATE)


def _fetch_table(finance_cd, list_no, metric_accounts, start_month, end_month):
    import fisis_management as fm

    params = {
        "financeCd": finance_cd,
        "listNo": list_no,
        "term": "Q",
        "startBaseMm": start_month,
        "endBaseMm": end_month,
    }
    # SE006 is very large. Only operating profit is needed, so request that
    # account directly. Other selected tables are compact enough for one call.
    if list_no == "SE006" and len(metric_accounts) == 1:
        params["accountCd"] = next(iter(metric_accounts.values()))

    result = fm._api_get("statisticsInfoSearch", **params)
    legend = fm._legend(result)
    by_account = {account_cd: metric for metric, account_cd in metric_accounts.items()}
    values = {}
    for row in fm._as_rows(result.get("list")):
        account_cd = str(row.get("account_cd") or "").strip()
        metric = by_account.get(account_cd)
        if not metric:
            continue
        quarter = fm._quarter_key(row.get("base_month"))
        if not quarter:
            continue
        value = fm._choose_value(row, legend, METRIC_KIND[metric])
        if value is not None:
            values.setdefault(quarter, {})[metric] = value
    return values


def _fetch_company(company, start_month, end_month, targets):
    code = company["finance_cd"]
    name = company["finance_nm"]
    region = company.get("region")
    quarters = {}
    errors = []
    target_set = set(targets)

    for list_no, metric_accounts in TABLES.items():
        try:
            table_values = _fetch_table(code, list_no, metric_accounts, start_month, end_month)
            for quarter, metrics in table_values.items():
                if quarter not in target_set:
                    continue
                row = quarters.setdefault(quarter, {
                    "bank": name,
                    "finance_cd": code,
                    "region": region,
                })
                row.update(metrics)
        except Exception as exc:
            errors.append(f"{name}/{list_no}: {type(exc).__name__}: {exc}")
    return quarters, errors


def _build_store():
    import fisis_management as fm

    targets = _target_quarters()
    if len(targets) < 2:
        raise RuntimeError("확장 지표 기준이 될 FISIS 분기가 부족합니다.")
    oldest = targets[-1]
    latest = targets[0]
    start_month = _quarter_month(oldest)
    end_month = _quarter_month(latest)
    companies = fm._companies()
    if not companies:
        raise RuntimeError("FISIS 저축은행 회사목록이 비어 있습니다.")

    with _REFRESH_LOCK:
        _REFRESH_STATE.update({
            "company_total": len(companies),
            "company_done": 0,
            "errors": [],
        })

    gathered = {quarter: [] for quarter in targets}
    errors = []
    workers = min(6, max(2, len(companies)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {
            executor.submit(_fetch_company, company, start_month, end_month, targets): company
            for company in companies
        }
        for future in as_completed(future_map):
            company = future_map[future]
            try:
                qdata, qerrors = future.result()
                errors.extend(qerrors)
                for quarter, row in qdata.items():
                    gathered.setdefault(quarter, []).append(row)
            except Exception as exc:
                errors.append(f"{company.get('finance_nm')}: {type(exc).__name__}: {exc}")
            with _REFRESH_LOCK:
                _REFRESH_STATE["company_done"] += 1
                _REFRESH_STATE["errors"] = errors[-20:]

    quarters = {}
    metric_names = sorted(METRIC_KIND.keys())
    for quarter in targets:
        rows = gathered.get(quarter) or []
        rows.sort(key=lambda row: str(row.get("bank") or ""))
        coverage = {
            metric: sum(1 for row in rows if row.get(metric) is not None)
            for metric in metric_names
        }
        quarters[quarter] = {
            "bank_count": len(rows),
            "coverage": coverage,
            "banks": rows,
        }

    latest_rows = quarters.get(latest, {}).get("banks") or []
    if len(latest_rows) < 50:
        raise RuntimeError(
            f"확장 FISIS 최신분기 수집 은행 수 부족: latest={latest} banks={len(latest_rows)} errors={len(errors)}"
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "source_name": fm.FISIS_SOURCE_NAME,
        "source_url": fm.FISIS_SOURCE_URL,
        "updated_at": fm._now().strftime("%Y-%m-%d %H:%M:%S"),
        "target_latest": latest,
        "target_quarters": targets,
        "quarter_count": len(quarters),
        "active_company_count": len(companies),
        "fetch_mode": "separate-recent-quarter-cache",
        "quarters": quarters,
        "last_errors": errors[-50:],
    }


def refresh_intelligence_cache(force=False):
    global _MEMORY_STORE
    current = get_intelligence_store(trigger_refresh=False)
    if not force and _cache_is_fresh(current):
        return current
    store = _build_store()
    try:
        _save_upstash(store)
    except Exception as exc:
        print("FISIS INTELLIGENCE UPSTASH SAVE ERROR:", exc)
    _save_local(store)
    with _MEMORY_LOCK:
        _MEMORY_STORE = store
    return store


def _refresh_worker(force):
    try:
        refresh_intelligence_cache(force=force)
    except Exception as exc:
        print("FISIS INTELLIGENCE REFRESH ERROR:", exc)
        with _REFRESH_LOCK:
            _REFRESH_STATE["errors"] = (_REFRESH_STATE.get("errors") or [])[-19:] + [
                f"refresh: {type(exc).__name__}: {exc}"
            ]
    finally:
        import fisis_management as fm
        with _REFRESH_LOCK:
            _REFRESH_STATE["running"] = False
            _REFRESH_STATE["finished_at"] = fm._now().strftime("%Y-%m-%d %H:%M:%S")


def trigger_intelligence_refresh(force=False):
    global _REFRESH_THREAD
    import fisis_management as fm

    if not fm._api_key():
        return False
    with _REFRESH_LOCK:
        if _REFRESH_STATE["running"]:
            return False
        if not force:
            current = get_intelligence_store(trigger_refresh=False)
            if _cache_is_fresh(current):
                return False
        _REFRESH_STATE.update({
            "running": True,
            "started_at": fm._now().strftime("%Y-%m-%d %H:%M:%S"),
            "finished_at": None,
            "company_total": 0,
            "company_done": 0,
            "errors": [],
        })
        _REFRESH_THREAD = threading.Thread(
            target=_refresh_worker,
            args=(force,),
            name="sbrate-fisis-intelligence-refresh",
            daemon=True,
        )
        _REFRESH_THREAD.start()
    return True


def intelligence_status():
    store = get_intelligence_store(trigger_refresh=True) or {}
    targets = _target_quarters()
    latest = targets[0] if targets else None
    meta = (store.get("quarters") or {}).get(latest) if latest else {}
    rows = meta.get("banks") if isinstance(meta, dict) else []
    woori = next(
        (row for row in (rows or []) if "우리금융" in str(row.get("bank") or "")),
        None,
    )
    return {
        "ok": True,
        "ready": _cache_is_fresh(store),
        "schema_version": store.get("schema_version"),
        "updated_at": store.get("updated_at"),
        "target_latest": latest,
        "quarter_count": len(store.get("quarters") or {}),
        "bank_count": len(rows or []),
        "woori_available": bool(woori),
        "coverage": meta.get("coverage") if isinstance(meta, dict) else {},
        "refresh": get_intelligence_refresh_state(),
    }


def install_fisis_intelligence_store():
    # Warm the separate cache without changing fisis_management.TABLES or its
    # cache freshness rules.
    try:
        trigger_intelligence_refresh(force=False)
    except Exception as exc:
        print("FISIS INTELLIGENCE STORE INSTALL ERROR:", exc)

    app_module = sys.modules.get("app") or sys.modules.get("__main__")
    if app_module is not None and hasattr(app_module, "app"):
        flask_app = app_module.app
        existing = {rule.rule for rule in flask_app.url_map.iter_rules()}
        if "/api/management-report/intelligence-status" not in existing:
            from flask import jsonify

            @flask_app.get("/api/management-report/intelligence-status")
            def management_intelligence_status_api():
                try:
                    return jsonify(intelligence_status())
                except Exception as exc:
                    return jsonify({"ok": False, "error": f"{type(exc).__name__}: {exc}"}), 500

    print("FISIS separate intelligence store installed: schema", SCHEMA_VERSION)
    return True
