"""Recent-quarter FISIS cache for management intelligence.

The stable base management-report cache is never modified here.  Expanded
funding/soundness/profitability fields live in their own Upstash key.  When an
older intelligence cache already contains the 79-bank core dataset, schema
upgrades re-use those rows and fetch only the newly required FISIS tables.
"""

import json
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

SCHEMA_VERSION = 7
CACHE_KEY = "sbrate:management:intelligence:v1"
CACHE_MAX_AGE = timedelta(days=14)
MAX_QUARTERS = 6
BASE_DIR = Path(__file__).resolve().parent
LOCAL_CACHE = BASE_DIR / "data" / "management" / "fisis_intelligence.json"

TABLES = {
    "SE028": {"deposits": "A1", "time_deposits": "A14"},
    "SE031": {"personal_deposits": "A", "corporate_deposits": "B", "sole_prop_deposits": "B1"},
    "SE006": {"operating_profit": "C"},
    "SE014": {
        "net_interest_income": "A", "interest_income": "A1", "loan_interest_income": "A13",
        "interest_expense": "A2", "deposit_interest_expense": "A21",
        "time_deposit_interest_expense": "A215",
    },
    "SE008": {
        "fixed_below_loans": "A3", "npl_ratio_detail": "A4",
        "allowance_balance": "A6", "npl_coverage_ratio": "A9",
    },
    "SE011": {"liquidity_ratio": "A"},
    "SE036": {"industry_corporate_loans": "A", "real_estate_industry_loans": "A6"},
}

# Schema 7 removes unsupported quarterly SE010 entirely.
UPGRADE_TABLES = {}

AMOUNT_METRICS = {
    "deposits", "time_deposits", "personal_deposits", "corporate_deposits", "sole_prop_deposits",
    "operating_profit", "avg_assets", "avg_equity", "profit_net_income", "net_interest_income",
    "interest_income", "loan_interest_income", "interest_expense", "deposit_interest_expense",
    "time_deposit_interest_expense", "fixed_below_loans", "allowance_balance",
    "industry_corporate_loans", "real_estate_industry_loans",
}
RATIO_METRICS = {"roa", "roe", "npl_ratio_detail", "npl_coverage_ratio", "liquidity_ratio"}
METRIC_KIND = {metric: "amount" for metric in AMOUNT_METRICS}
METRIC_KIND.update({metric: "ratio" for metric in RATIO_METRICS})

_MEMORY_LOCK = threading.Lock()
_MEMORY_STORE = None
_REFRESH_LOCK = threading.Lock()
_REFRESH_THREAD = None
_REFRESH_STATE = {
    "running": False,
    "phase": "idle",
    "mode": None,
    "started_at": None,
    "finished_at": None,
    "company_total": 0,
    "company_done": 0,
    "table_count": 0,
    "errors": [],
}


def _quarter_rank(key):
    match = re.fullmatch(r"(\d{4})Q([1-4])", str(key or ""))
    return int(match.group(1)) * 4 + int(match.group(2)) if match else -1


def _quarter_month(key):
    match = re.fullmatch(r"(\d{4})Q([1-4])", str(key or ""))
    return f"{match.group(1)}{int(match.group(2)) * 3:02d}" if match else None


def _row_key(row):
    code = str((row or {}).get("finance_cd") or "").strip()
    if code:
        return code
    return re.sub(r"\s+", "", str((row or {}).get("bank") or "")).replace("저축은행", "")


def _base_store():
    import fisis_management as fm
    return fm.get_management_store(trigger_refresh=False) or {}


def _target_quarters(base=None):
    base = base if isinstance(base, dict) else _base_store()
    quarters = base.get("quarters") if isinstance(base.get("quarters"), dict) else {}
    return sorted(quarters.keys(), key=_quarter_rank, reverse=True)[:MAX_QUARTERS]


def _companies_from_base(base, targets):
    quarters = base.get("quarters") if isinstance(base.get("quarters"), dict) else {}
    latest = quarters.get(targets[0]) if targets else {}
    rows = latest.get("banks") if isinstance(latest, dict) else []
    result, seen = [], set()
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        code = str(row.get("finance_cd") or "").strip()
        name = str(row.get("bank") or "").strip()
        if not code or not name or code in seen:
            continue
        seen.add(code)
        result.append({"finance_cd": code, "finance_nm": name, "region": row.get("region")})
    return result


def _cache_age(store):
    import fisis_management as fm
    value = str((store or {}).get("updated_at") or "").strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S%z"):
        try:
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


def _number(value):
    try:
        if value in (None, "", "-", "--"):
            return None
        return float(str(value).replace(",", ""))
    except Exception:
        return None


def _normalize_cached_amount(value):
    """Convert legacy raw-KRW values to 억원 without touching already-converted rows."""
    number = _number(value)
    if number is None:
        return value
    # No Korean savings-bank intelligence amount in 억원 approaches one
    # million.  Legacy raw KRW values do, so this is a conservative signature.
    if abs(number) >= 1_000_000:
        return round(number / 100_000_000.0, 2)
    return number


def _normalize_seed_row(row):
    result = dict(row or {})
    for unsupported in ("avg_assets", "avg_equity", "profit_net_income", "roa", "roe"):
        result.pop(unsupported, None)
    for metric in AMOUNT_METRICS:
        if metric in result and result.get(metric) is not None:
            result[metric] = _normalize_cached_amount(result.get(metric))
    return result


def _legacy_store_usable(store, targets):
    if int((store or {}).get("schema_version") or 0) < 4:
        return False
    if str((store or {}).get("target_latest") or "") != (targets[0] if targets else ""):
        return False
    quarters = store.get("quarters") if isinstance(store.get("quarters"), dict) else {}
    latest = quarters.get(targets[0]) if targets else {}
    rows = latest.get("banks") if isinstance(latest, dict) else []
    if len(rows or []) < 70:
        return False
    coverage = latest.get("coverage") if isinstance(latest, dict) else {}
    return int((coverage or {}).get("deposits") or 0) >= 70 and int((coverage or {}).get("liquidity_ratio") or 0) >= 70


def _legend_with_unit_fallback(result):
    import fisis_management as fm
    legend = fm._legend(result)
    if not legend or any(str(unit or "").strip() for _, _, unit in legend):
        return legend
    tokens = [token.strip() for token in str(result.get("unit") or "").split(",") if token.strip()]
    unique = []
    for token in tokens:
        if token not in unique:
            unique.append(token)
    if len(unique) == 1:
        return [(cid, name, unique[0]) for cid, name, _ in legend]
    return legend


def _fetch_table(finance_cd, list_no, metric_accounts, start_month, end_month):
    import fisis_management as fm
    params = {
        "financeCd": finance_cd,
        "listNo": list_no,
        "term": "Q",
        "startBaseMm": start_month,
        "endBaseMm": end_month,
    }
    if list_no == "SE006" and len(metric_accounts) == 1:
        params["accountCd"] = next(iter(metric_accounts.values()))
    result = fm._api_get("statisticsInfoSearch", **params)
    legend = _legend_with_unit_fallback(result)
    by_account = {account_cd: metric for metric, account_cd in metric_accounts.items()}
    values = {}
    for row in fm._as_rows(result.get("list")):
        metric = by_account.get(str(row.get("account_cd") or "").strip())
        if not metric:
            continue
        quarter = fm._quarter_key(row.get("base_month"))
        if not quarter:
            continue
        value = fm._choose_value(row, legend, METRIC_KIND[metric])
        if value is not None:
            # Defensive normalization handles FISIS responses whose unit legend
            # is absent even after the common-unit fallback.
            if metric in AMOUNT_METRICS:
                value = _normalize_cached_amount(value)
            values.setdefault(quarter, {})[metric] = value
    return values


def _fetch_company(company, start_month, end_month, targets, tables):
    code, name = company["finance_cd"], company["finance_nm"]
    quarters, errors, target_set = {}, [], set(targets)
    for list_no, metric_accounts in tables.items():
        try:
            table_values = _fetch_table(code, list_no, metric_accounts, start_month, end_month)
            for quarter, metrics in table_values.items():
                if quarter not in target_set:
                    continue
                row = quarters.setdefault(quarter, {
                    "bank": name,
                    "finance_cd": code,
                    "region": company.get("region"),
                })
                row.update(metrics)
        except Exception as exc:
            errors.append(f"{name}/{list_no}: {type(exc).__name__}: {exc}")
    return quarters, errors


def _seed_gathered(existing, targets, companies):
    gathered = {quarter: {} for quarter in targets}
    quarters = existing.get("quarters") if isinstance(existing.get("quarters"), dict) else {}
    company_keys = {company["finance_cd"] for company in companies}
    for quarter in targets:
        meta = quarters.get(quarter) if isinstance(quarters.get(quarter), dict) else {}
        for row in meta.get("banks") or []:
            if not isinstance(row, dict):
                continue
            key = _row_key(row)
            if key in company_keys:
                gathered[quarter][key] = _normalize_seed_row(row)
    for quarter in targets:
        for company in companies:
            key = company["finance_cd"]
            gathered[quarter].setdefault(key, {
                "bank": company["finance_nm"],
                "finance_cd": key,
                "region": company.get("region"),
            })
    return gathered


def _build_store(existing=None):
    import fisis_management as fm

    existing = existing if isinstance(existing, dict) else {}
    with _REFRESH_LOCK:
        _REFRESH_STATE["phase"] = "loading_base"
    base = _base_store()
    targets = _target_quarters(base)
    if len(targets) < 2:
        raise RuntimeError("확장 지표 기준이 될 FISIS 분기가 부족합니다.")
    companies = _companies_from_base(base, targets)
    if len(companies) < 50:
        raise RuntimeError(f"기본 경영현황의 활성 저축은행이 부족합니다: {len(companies)}")

    incremental = _legacy_store_usable(existing, targets)
    tables = UPGRADE_TABLES if incremental else TABLES
    mode = "incremental-upgrade" if incremental else "full-build"
    latest = targets[0]
    start_month, end_month = _quarter_month(targets[-1]), _quarter_month(latest)
    gathered = _seed_gathered(existing, targets, companies) if incremental else {
        quarter: {
            company["finance_cd"]: {
                "bank": company["finance_nm"],
                "finance_cd": company["finance_cd"],
                "region": company.get("region"),
            }
            for company in companies
        }
        for quarter in targets
    }

    with _REFRESH_LOCK:
        _REFRESH_STATE.update({
            "phase": "fetching_metrics",
            "mode": mode,
            "company_total": len(companies),
            "company_done": 0,
            "table_count": len(tables),
            "errors": [],
        })

    errors = []
    with ThreadPoolExecutor(max_workers=min(8, max(2, len(companies)))) as executor:
        future_map = {
            executor.submit(_fetch_company, company, start_month, end_month, targets, tables): company
            for company in companies
        }
        for future in as_completed(future_map):
            company = future_map[future]
            try:
                qdata, qerrors = future.result()
                errors.extend(qerrors)
                for quarter, row in qdata.items():
                    key = company["finance_cd"]
                    target = gathered.setdefault(quarter, {}).setdefault(key, {
                        "bank": company["finance_nm"],
                        "finance_cd": key,
                        "region": company.get("region"),
                    })
                    target.update(row)
            except Exception as exc:
                errors.append(f"{company.get('finance_nm')}: {type(exc).__name__}: {exc}")
            with _REFRESH_LOCK:
                _REFRESH_STATE["company_done"] += 1
                _REFRESH_STATE["errors"] = errors[-20:]

    with _REFRESH_LOCK:
        _REFRESH_STATE["phase"] = "saving"
    metric_names = sorted(METRIC_KIND.keys())
    quarters = {}
    for quarter in targets:
        rows = [_normalize_seed_row(row) for row in gathered.get(quarter, {}).values()]
        # Rows with only identifiers can occur only on a failed full build; do
        # not count them as successfully collected institutions.
        rows = [row for row in rows if any(row.get(metric) is not None for metric in metric_names)]
        rows.sort(key=lambda row: str(row.get("bank") or ""))
        quarters[quarter] = {
            "bank_count": len(rows),
            "coverage": {
                metric: sum(1 for row in rows if row.get(metric) is not None)
                for metric in metric_names
            },
            "banks": rows,
        }

    latest_rows = quarters.get(latest, {}).get("banks") or []
    if len(latest_rows) < 70:
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
        "fetch_mode": mode,
        "fetched_tables": list(tables.keys()),
        "quarters": quarters,
        "last_errors": errors[-50:],
    }


def refresh_intelligence_cache(force=False):
    global _MEMORY_STORE
    current = get_intelligence_store(trigger_refresh=False)
    if not force and _cache_is_fresh(current):
        return current
    store = _build_store(existing=current)
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
            _REFRESH_STATE.update({
                "running": False,
                "phase": "idle",
                "finished_at": fm._now().strftime("%Y-%m-%d %H:%M:%S"),
            })


def trigger_intelligence_refresh(force=False):
    global _REFRESH_THREAD
    import fisis_management as fm
    if not fm._api_key():
        return False
    with _REFRESH_LOCK:
        if _REFRESH_STATE["running"]:
            return False
        current = get_intelligence_store(trigger_refresh=False)
        if not force and _cache_is_fresh(current):
            return False
        _REFRESH_STATE.update({
            "running": True,
            "phase": "starting",
            "mode": None,
            "started_at": fm._now().strftime("%Y-%m-%d %H:%M:%S"),
            "finished_at": None,
            "company_total": 0,
            "company_done": 0,
            "table_count": 0,
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
    woori = next((row for row in (rows or []) if "우리금융" in str(row.get("bank") or "")), None)
    return {
        "ok": True,
        "ready": _cache_is_fresh(store),
        "schema_version": store.get("schema_version"),
        "code_schema_version": SCHEMA_VERSION,
        "updated_at": store.get("updated_at"),
        "target_latest": latest,
        "quarter_count": len(store.get("quarters") or {}),
        "bank_count": len(rows or []),
        "woori_available": bool(woori),
        "fetch_mode": store.get("fetch_mode"),
        "fetched_tables": store.get("fetched_tables") or [],
        "coverage": meta.get("coverage") if isinstance(meta, dict) else {},
        "refresh": get_intelligence_refresh_state(),
    }


def install_fisis_intelligence_store():
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
