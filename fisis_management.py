import json
import math
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests


BASE_DIR = Path(__file__).resolve().parent
LOCAL_CACHE = BASE_DIR / "data" / "management" / "fisis_quarters.json"
FISIS_BASE = "https://fisis.fss.or.kr/openapi"
FISIS_SECTOR = "E"
FISIS_SOURCE_NAME = "금융감독원 금융통계정보시스템(FISIS)"
FISIS_SOURCE_URL = "https://fisis.fss.or.kr/"
CACHE_KEY = "sbrate:management:fisis:v1"
CACHE_MAX_AGE = timedelta(days=14)
MIN_QUARTER_COVERAGE = 0.90
KST = timezone(timedelta(hours=9))

# One FISIS table call returns every account in that table across the requested
# quarter range. Grouping metrics by list_no keeps API traffic low.
TABLES = {
    "SE003": {"total_assets": "A"},
    "SE020": {
        "corporate_loans": "A",
        "household_loans": "B",
        "total_loans": "D",
    },
    "SE035": {"bis_ratio": "C"},
    "SE034": {"npl_ratio": "A"},
    "SE019": {"delinquency_ratio": "C"},
    "SE033": {"net_income": "A"},
    "SE001": {"employees": "A"},
}

METRIC_KIND = {
    "total_assets": "amount",
    "corporate_loans": "amount",
    "household_loans": "amount",
    "total_loans": "amount",
    "bis_ratio": "ratio",
    "npl_ratio": "ratio",
    "delinquency_ratio": "ratio",
    "net_income": "amount",
    "employees": "count",
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


def _now():
    return datetime.now(KST)


def _api_key():
    return str(os.environ.get("FISIS_API_KEY") or "").strip()


def _upstash_config():
    url = str(os.environ.get("UPSTASH_REDIS_REST_URL") or "").strip().rstrip("/")
    token = str(os.environ.get("UPSTASH_REDIS_REST_TOKEN") or "").strip()
    return url, token


def _upstash_command(command, timeout=10):
    url, token = _upstash_config()
    if not url or not token:
        raise RuntimeError("Upstash is not configured")
    response = requests.post(
        f"{url}/pipeline",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=[command],
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list) or not payload:
        raise RuntimeError("Invalid Upstash response")
    item = payload[0]
    if isinstance(item, dict) and item.get("error"):
        raise RuntimeError(str(item.get("error")))
    return item.get("result") if isinstance(item, dict) else None


def _load_upstash():
    raw = _upstash_command(["GET", CACHE_KEY])
    if not raw:
        return None
    data = json.loads(raw)
    return data if isinstance(data, dict) else None


def _save_upstash(store):
    raw = json.dumps(store, ensure_ascii=False, separators=(",", ":"))
    _upstash_command(["SET", CACHE_KEY, raw], timeout=20)


def _load_local():
    try:
        with LOCAL_CACHE.open("r", encoding="utf-8-sig") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _save_local(store):
    try:
        LOCAL_CACHE.parent.mkdir(parents=True, exist_ok=True)
        with LOCAL_CACHE.open("w", encoding="utf-8") as f:
            json.dump(store, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        print("FISIS MANAGEMENT LOCAL CACHE SAVE ERROR:", exc)


def _cache_age(store):
    value = str((store or {}).get("updated_at") or "").strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            dt = datetime.strptime(value, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=KST)
            return _now() - dt.astimezone(KST)
        except Exception:
            pass
    return None


def _cache_is_fresh(store):
    quarters = (store or {}).get("quarters")
    if not isinstance(quarters, dict) or not quarters:
        return False
    age = _cache_age(store)
    return age is not None and age <= CACHE_MAX_AGE


def _load_store_once():
    try:
        store = _load_upstash()
        if store:
            return store
    except Exception as exc:
        print("FISIS MANAGEMENT UPSTASH LOAD ERROR:", exc)
    return _load_local() or {}


def get_management_store(trigger_refresh=True):
    global _MEMORY_STORE
    with _MEMORY_LOCK:
        if _MEMORY_STORE is None:
            _MEMORY_STORE = _load_store_once()
        store = _MEMORY_STORE or {}
    if trigger_refresh and not _cache_is_fresh(store):
        trigger_management_refresh(force=False)
    return store


def get_refresh_state():
    with _REFRESH_LOCK:
        return dict(_REFRESH_STATE)


def _api_get(path, **params):
    key = _api_key()
    if not key:
        raise RuntimeError("FISIS_API_KEY is not configured")
    query = {"lang": "kr", "auth": key}
    query.update({k: v for k, v in params.items() if v not in (None, "")})
    last_error = None
    for attempt in range(4):
        try:
            response = requests.get(
                f"{FISIS_BASE}/{path}.json",
                params=query,
                timeout=25,
                headers={"User-Agent": "SBRate-FISIS/1.0"},
            )
            if response.status_code == 429 or response.status_code >= 500:
                raise RuntimeError(f"HTTP {response.status_code}")
            response.raise_for_status()
            payload = response.json()
            result = payload.get("result") if isinstance(payload, dict) else None
            if not isinstance(result, dict):
                raise RuntimeError("FISIS result missing")
            err_cd = str(result.get("err_cd") or "000")
            if err_cd not in ("000", "0", ""):
                raise RuntimeError(f"FISIS err_cd={err_cd}: {result.get('err_msg')}")
            return result
        except Exception as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(1.2 * (attempt + 1))
    raise RuntimeError(str(last_error))


def _as_rows(value):
    if value is None:
        return []
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)]
    return []


def _companies():
    rows = _as_rows(_api_get("companySearch", partDiv=FISIS_SECTOR).get("list"))
    active = []
    seen = set()
    for row in rows:
        name = str(row.get("finance_nm") or "").strip()
        code = str(row.get("finance_cd") or "").strip()
        if not name or not code or "[폐]" in name:
            continue
        if code in seen:
            continue
        seen.add(code)
        active.append({"finance_cd": code, "finance_nm": name})
    return active


def _quarter_range():
    now = _now()
    # Keep enough history for arbitrary quarter comparisons without approaching
    # FISIS's 40-quarter window limit.
    start = "202303"
    completed_month = ((now.month - 1) // 3) * 3
    year = now.year
    if completed_month == 0:
        year -= 1
        completed_month = 12
    end = f"{year:04d}{completed_month:02d}"
    return start, end


def _legend(result):
    description = result.get("description")
    if isinstance(description, dict) and "column_id" not in description:
        description = description.get("column")
    entries = []
    for item in _as_rows(description):
        cid = str(item.get("column_id") or "").strip()
        name = str(item.get("column_nm") or "").strip()
        if cid and name:
            entries.append((cid, name))
    units_raw = result.get("unit")
    units = [token.strip() for token in str(units_raw or "").split(",")]
    if len(units) != len(entries):
        units = [""] * len(entries)
    return [(cid, name, units[idx]) for idx, (cid, name) in enumerate(entries)]


def _number(value):
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text or text in ("-", "--", "N/A", "null", "None"):
        return None
    negative = False
    if text.startswith(("△", "▲", "(")):
        negative = True
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    number = float(match.group(0))
    if negative and number > 0:
        number = -number
    return number


def _convert(value, unit, kind):
    number = _number(value)
    if number is None:
        return None
    unit = str(unit or "").replace(" ", "")
    if kind == "amount":
        if "억원" in unit:
            pass
        elif "백만원" in unit:
            number /= 100.0
        elif "천원" in unit:
            number /= 100000.0
        elif unit == "원" or unit.endswith("원"):
            number /= 100000000.0
    return round(number, 4 if kind == "ratio" else 2)


def _quarter_key(base_month):
    text = re.sub(r"\D", "", str(base_month or ""))
    if len(text) < 6:
        return None
    year = int(text[:4])
    month = int(text[4:6])
    if month not in (3, 6, 9, 12):
        return None
    return f"{year}Q{month // 3}"


def _quarter_label(key):
    match = re.fullmatch(r"(\d{4})Q([1-4])", str(key or ""))
    return f"{match.group(1)}년 {match.group(2)}분기" if match else str(key or "-")


def _quarter_as_of(key):
    match = re.fullmatch(r"(\d{4})Q([1-4])", str(key or ""))
    if not match:
        return None
    year = int(match.group(1))
    quarter = int(match.group(2))
    month = quarter * 3
    day = 31 if month in (3, 12) else 30
    return f"{year:04d}-{month:02d}-{day:02d}"


def _choose_value(row, legend, kind):
    candidates = []
    for cid, name, unit in legend:
        if cid not in row:
            continue
        value = _number(row.get(cid))
        if value is None:
            continue
        score = 0
        clean_unit = str(unit or "").replace(" ", "")
        clean_name = str(name or "")
        if kind == "ratio" and "%" in clean_unit:
            score += 50
        elif kind == "count" and "명" in clean_unit:
            score += 50
        elif kind == "amount" and any(token in clean_unit for token in ("원", "백만원", "억원", "천원")):
            score += 50
        for token, weight in (("금액", 20), ("말잔", 18), ("합계", 14), ("비율", 14), ("인원", 14), ("당기", 8)):
            if token in clean_name:
                score += weight
        if any(token in clean_name for token in ("전년", "증감", "비교")):
            score -= 25
        candidates.append((score, cid, unit))
    if not candidates:
        # Defensive fallback for FISIS tables with a missing legend.
        for key, value in row.items():
            if key in ("base_month", "finance_cd", "finance_nm", "account_cd", "account_nm"):
                continue
            if _number(value) is not None:
                candidates.append((0, key, ""))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    _, key, unit = candidates[0]
    return _convert(row.get(key), unit, kind)


def _fetch_table(finance_cd, list_no, metric_accounts, start_month, end_month):
    result = _api_get(
        "statisticsInfoSearch",
        financeCd=finance_cd,
        listNo=list_no,
        term="Q",
        startBaseMm=start_month,
        endBaseMm=end_month,
    )
    legend = _legend(result)
    by_account = {account_cd: metric for metric, account_cd in metric_accounts.items()}
    values = {}
    for row in _as_rows(result.get("list")):
        metric = by_account.get(str(row.get("account_cd") or "").strip())
        if not metric:
            continue
        quarter = _quarter_key(row.get("base_month"))
        if not quarter:
            continue
        value = _choose_value(row, legend, METRIC_KIND[metric])
        if value is not None:
            values.setdefault(quarter, {})[metric] = value
    return values


def _fetch_company(company, start_month, end_month):
    code = company["finance_cd"]
    name = company["finance_nm"]
    quarters = {}
    errors = []
    for list_no, metric_accounts in TABLES.items():
        try:
            table_values = _fetch_table(code, list_no, metric_accounts, start_month, end_month)
            for quarter, metrics in table_values.items():
                row = quarters.setdefault(quarter, {
                    "bank": name,
                    "finance_cd": code,
                    "region": None,
                })
                row.update(metrics)
        except Exception as exc:
            errors.append(f"{name}/{list_no}: {type(exc).__name__}: {exc}")
    return quarters, errors


def _build_store():
    companies = _companies()
    if not companies:
        raise RuntimeError("FISIS 저축은행 회사목록이 비어 있습니다.")
    start_month, end_month = _quarter_range()

    with _REFRESH_LOCK:
        _REFRESH_STATE["company_total"] = len(companies)
        _REFRESH_STATE["company_done"] = 0
        _REFRESH_STATE["errors"] = []

    gathered = {}
    errors = []
    workers = min(6, max(2, len(companies)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {
            executor.submit(_fetch_company, company, start_month, end_month): company
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
                errors.append(f"{company['finance_nm']}: {type(exc).__name__}: {exc}")
            with _REFRESH_LOCK:
                _REFRESH_STATE["company_done"] += 1
                _REFRESH_STATE["errors"] = errors[-20:]

    # Only expose quarters with broad industry coverage. This prevents a newly
    # opening reporting quarter from becoming the default while most banks are
    # still unpublished.
    minimum_assets = max(20, math.ceil(len(companies) * MIN_QUARTER_COVERAGE))
    quarters = {}
    for key, rows in gathered.items():
        valid_assets = [row for row in rows if row.get("total_assets") is not None]
        if len(valid_assets) < minimum_assets:
            continue
        rows.sort(key=lambda row: (-(row.get("total_assets") or -1), str(row.get("bank") or "")))
        valid_assets = [row for row in rows if row.get("total_assets") is not None]
        for idx, row in enumerate(valid_assets, 1):
            row["asset_rank"] = idx
        quarters[key] = {
            "label": _quarter_label(key),
            "as_of": _quarter_as_of(key),
            "source_url": FISIS_SOURCE_URL,
            "source_name": FISIS_SOURCE_NAME,
            "bank_count": len(rows),
            "asset_bank_count": len(valid_assets),
            "banks": rows,
        }

    if not quarters:
        raise RuntimeError(f"FISIS 분기 데이터 품질 기준 미달: companies={len(companies)} errors={len(errors)}")

    return {
        "source_name": FISIS_SOURCE_NAME,
        "source_url": FISIS_SOURCE_URL,
        "updated_at": _now().strftime("%Y-%m-%d %H:%M:%S"),
        "quarter_range": {"start": start_month, "end": end_month},
        "active_company_count": len(companies),
        "minimum_quarter_coverage_ratio": MIN_QUARTER_COVERAGE,
        "minimum_quarter_asset_count": minimum_assets,
        "quarters": quarters,
        "last_errors": errors[-50:],
        "note": "당기순이익은 FISIS 공시 기준 누적값입니다.",
    }


def refresh_management_cache(force=False):
    global _MEMORY_STORE
    current = get_management_store(trigger_refresh=False)
    if not force and _cache_is_fresh(current):
        return current
    store = _build_store()
    try:
        _save_upstash(store)
    except Exception as exc:
        print("FISIS MANAGEMENT UPSTASH SAVE ERROR:", exc)
    _save_local(store)
    with _MEMORY_LOCK:
        _MEMORY_STORE = store
    return store


def _refresh_worker(force):
    try:
        refresh_management_cache(force=force)
    except Exception as exc:
        print("FISIS MANAGEMENT REFRESH ERROR:", exc)
        with _REFRESH_LOCK:
            _REFRESH_STATE["errors"] = (_REFRESH_STATE.get("errors") or [])[-19:] + [
                f"refresh: {type(exc).__name__}: {exc}"
            ]
    finally:
        with _REFRESH_LOCK:
            _REFRESH_STATE["running"] = False
            _REFRESH_STATE["finished_at"] = _now().strftime("%Y-%m-%d %H:%M:%S")


def trigger_management_refresh(force=False):
    global _REFRESH_THREAD
    if not _api_key():
        return False
    with _REFRESH_LOCK:
        if _REFRESH_STATE["running"]:
            return False
        if not force:
            current = get_management_store(trigger_refresh=False)
            if _cache_is_fresh(current):
                return False
        _REFRESH_STATE.update({
            "running": True,
            "started_at": _now().strftime("%Y-%m-%d %H:%M:%S"),
            "finished_at": None,
            "company_total": 0,
            "company_done": 0,
            "errors": [],
        })
        _REFRESH_THREAD = threading.Thread(
            target=_refresh_worker,
            args=(force,),
            name="sbrate-fisis-management-refresh",
            daemon=True,
        )
        _REFRESH_THREAD.start()
    return True


def install_fisis_management():
    # Warm the persistent cache in the background on deploy only when stale.
    try:
        trigger_management_refresh(force=False)
    except Exception as exc:
        print("FISIS MANAGEMENT INSTALL ERROR:", exc)
    return True
