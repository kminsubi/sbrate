import json
import math
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
import sys


MIN_QUARTER_COVERAGE = 0.90
PROBE_REUSE_AGE = timedelta(hours=6)
PROBE_RESULT_KEY = "sbrate:management:fisis:latest-quarter-probe:v1"
PROBE_LOCK_KEY = "sbrate:management:fisis:latest-quarter-probe:lock:v1"
PROBE_RESULT_TTL_SECONDS = 24 * 60 * 60
PROBE_LOCK_TTL_SECONDS = 30 * 60

_LOCK = threading.Lock()
_STATE = {
    "running": False,
    "started_at": None,
    "finished_at": None,
    "last_probe_at": None,
    "result": None,
    "lock_token": None,
}


def _quarter_rank(key):
    text = str(key or "")
    if len(text) != 6 or text[4] != "Q":
        return 0
    try:
        return int(text[:4]) * 4 + int(text[5])
    except Exception:
        return 0


def _target_info(fm):
    _, end_month = fm._quarter_range()
    target = fm._quarter_key(end_month)
    as_of = fm._quarter_as_of(target) if target else None
    return target, end_month, as_of


def _days_after(as_of):
    if not as_of:
        return 999
    try:
        end = datetime.strptime(as_of, "%Y-%m-%d").date()
        return (fm_now_date() - end).days
    except Exception:
        return 999


def fm_now_date():
    import fisis_management as fm
    return fm._now().date()


def _parse_dt(value, fm):
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            dt = datetime.strptime(text, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=fm.KST)
            return dt.astimezone(fm.KST)
        except Exception:
            pass
    return None


def _stored_asset_count(store, quarter):
    quarters = store.get("quarters") if isinstance(store.get("quarters"), dict) else {}
    meta = quarters.get(quarter) if isinstance(quarters.get(quarter), dict) else {}
    count = int(meta.get("asset_bank_count") or 0)
    if count:
        return count
    rows = meta.get("banks") if isinstance(meta.get("banks"), list) else []
    return sum(
        1 for row in rows
        if isinstance(row, dict) and row.get("total_assets") is not None
    )


def _load_persisted_probe(fm):
    try:
        raw = fm._upstash_command(["GET", PROBE_RESULT_KEY], timeout=10)
        if not raw:
            return None
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except Exception as exc:
        print("FISIS latest-quarter persisted probe load error:", exc)
        return None


def _save_persisted_probe(fm, result):
    try:
        raw = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
        fm._upstash_command(
            ["SET", PROBE_RESULT_KEY, raw, "EX", str(PROBE_RESULT_TTL_SECONDS)],
            timeout=15,
        )
        return True
    except Exception as exc:
        print("FISIS latest-quarter persisted probe save error:", exc)
        return False


def _acquire_probe_lock(fm):
    token = uuid.uuid4().hex
    try:
        result = fm._upstash_command(
            ["SET", PROBE_LOCK_KEY, token, "NX", "EX", str(PROBE_LOCK_TTL_SECONDS)],
            timeout=10,
        )
        return token if str(result or "").upper() == "OK" else None
    except Exception as exc:
        print("FISIS latest-quarter distributed lock error:", exc)
        return None


def _release_probe_lock(fm, token):
    if not token:
        return
    try:
        current = fm._upstash_command(["GET", PROBE_LOCK_KEY], timeout=10)
        if str(current or "") == str(token):
            fm._upstash_command(["DEL", PROBE_LOCK_KEY], timeout=10)
    except Exception as exc:
        print("FISIS latest-quarter distributed unlock error:", exc)


def _recent_persisted_result(fm, target):
    persisted = _load_persisted_probe(fm)
    if not isinstance(persisted, dict):
        return None
    if target and str(persisted.get("target_quarter") or "") != str(target):
        return None
    finished = _parse_dt(persisted.get("finished_at"), fm)
    if not finished:
        return None
    if fm._now() - finished >= PROBE_REUSE_AGE:
        return None
    return persisted


def _probe_worker(base_result, target, target_month, lock_token=None):
    import fisis_management as fm

    result = dict(base_result)
    try:
        companies = fm._companies()
        coverage_ratio = float(getattr(fm, "MIN_QUARTER_COVERAGE", MIN_QUARTER_COVERAGE))
        threshold = max(20, math.ceil(len(companies) * coverage_ratio))
        stored_count = int(result.get("stored_asset_count") or 0)
        result.update({
            "probe_required": True,
            "company_count": len(companies),
            "coverage_ratio_required": coverage_ratio,
            "coverage_threshold": threshold,
            "published_asset_count": 0,
        })

        def fetch_one(company):
            values = fm._fetch_table(
                company["finance_cd"],
                "SE003",
                {"total_assets": "A"},
                target_month,
                target_month,
            )
            metric = (values.get(target) or {}).get("total_assets")
            return metric is not None

        published = 0
        errors = 0
        workers = min(6, max(2, len(companies)))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(fetch_one, company) for company in companies]
            for future in as_completed(futures):
                try:
                    if future.result():
                        published += 1
                except Exception:
                    errors += 1

        result["published_asset_count"] = published
        result["probe_error_count"] = errors

        should_refresh = published >= threshold and published > stored_count
        if should_refresh:
            result["triggered_refresh"] = bool(fm.trigger_management_refresh(force=True))
            result["status"] = (
                "new_quarter_refresh_started"
                if result["triggered_refresh"]
                else "refresh_already_running"
            )
        elif published >= threshold:
            result["status"] = "latest_quarter_no_new_banks"
        else:
            result["status"] = "new_quarter_not_broadly_published"

    except Exception as exc:
        result.update({
            "ok": False,
            "status": "probe_failed",
            "error": f"{type(exc).__name__}: {exc}",
        })
    finally:
        now = fm._now()
        result["finished_at"] = now.strftime("%Y-%m-%d %H:%M:%S")
        _save_persisted_probe(fm, result)
        _release_probe_lock(fm, lock_token)
        with _LOCK:
            _STATE["running"] = False
            _STATE["finished_at"] = now
            _STATE["last_probe_at"] = now
            _STATE["result"] = dict(result)
            _STATE["lock_token"] = None
    return result


def check_latest_quarter(force_probe=False, wait=False):
    import fisis_management as fm

    store = fm.get_management_store(trigger_refresh=False) or {}
    quarters = store.get("quarters") if isinstance(store.get("quarters"), dict) else {}
    current_latest = max(quarters.keys(), key=_quarter_rank, default="")
    target, target_month, target_as_of = _target_info(fm)
    active_count = int(store.get("active_company_count") or 0)
    stored_target_count = _stored_asset_count(store, target) if target else 0

    result = {
        "ok": True,
        "checked_at": fm._now().strftime("%Y-%m-%d %H:%M:%S"),
        "current_latest": current_latest or None,
        "target_quarter": target,
        "target_as_of": target_as_of,
        "coverage_ratio_required": float(getattr(fm, "MIN_QUARTER_COVERAGE", MIN_QUARTER_COVERAGE)),
        "stored_asset_count": stored_target_count,
        "active_company_count": active_count,
        "probe_required": False,
        "triggered_refresh": False,
    }

    if not target:
        result["status"] = "latest_already_loaded"
        return result

    target_is_latest = _quarter_rank(current_latest) >= _quarter_rank(target)
    target_is_complete = active_count > 0 and stored_target_count >= active_count
    if target_is_latest and target_is_complete and not force_probe:
        result["status"] = "latest_already_loaded"
        return result

    days_after = _days_after(target_as_of)
    result["days_after_quarter_end"] = days_after
    if days_after < 40 and not force_probe:
        result["status"] = "waiting_for_disclosure_window"
        return result

    refresh_state = fm.get_refresh_state()
    if bool(refresh_state.get("running")) and not force_probe:
        result["status"] = "management_refresh_running"
        return result

    if not force_probe:
        persisted = _recent_persisted_result(fm, target)
        if persisted:
            cached = dict(persisted)
            cached["checked_at"] = result["checked_at"]
            cached["current_latest"] = current_latest or None
            cached["stored_asset_count"] = stored_target_count
            cached["active_company_count"] = active_count
            cached["status_detail"] = str(cached.get("status") or "")
            cached["status"] = "recent_probe_reused"
            return cached

    with _LOCK:
        if _STATE.get("running"):
            result["status"] = "probe_running"
            return result

    lock_token = _acquire_probe_lock(fm)
    if not lock_token:
        result["status"] = "probe_running"
        result["distributed_lock"] = True
        return result

    with _LOCK:
        _STATE["running"] = True
        _STATE["started_at"] = fm._now()
        _STATE["lock_token"] = lock_token

    if wait:
        return _probe_worker(result, target, target_month, lock_token=lock_token)

    thread = threading.Thread(
        target=_probe_worker,
        args=(result, target, target_month, lock_token),
        name="sbrate-fisis-latest-quarter-probe",
        daemon=True,
    )
    thread.start()

    result["probe_required"] = True
    result["status"] = "probe_started"
    return result


def get_auto_update_state():
    import fisis_management as fm

    persisted = _load_persisted_probe(fm) or {}
    with _LOCK:
        result = dict(_STATE.get("result") or {})
        running = bool(_STATE.get("running"))
        started = _STATE.get("started_at")
        finished = _STATE.get("finished_at")

    local_finished = _parse_dt(result.get("finished_at"), fm) or finished
    persisted_finished = _parse_dt(persisted.get("finished_at"), fm)
    if persisted and (not result or (persisted_finished and (not local_finished or persisted_finished >= local_finished))):
        result = dict(persisted)

    result["running"] = running
    result["started_at"] = started.strftime("%Y-%m-%d %H:%M:%S") if started else result.get("started_at")
    result["finished_at"] = finished.strftime("%Y-%m-%d %H:%M:%S") if finished else result.get("finished_at")
    result["persistent"] = bool(persisted)
    return result


def install_management_report_auto_update():
    app_module = sys.modules.get("app") or sys.modules.get("__main__")
    if app_module is None or not hasattr(app_module, "app"):
        return False
    if getattr(app_module, "_management_report_auto_update_installed", False):
        return True

    flask_app = app_module.app
    from flask import jsonify

    @flask_app.get("/api/management-report/check-latest")
    def management_report_check_latest():
        try:
            return jsonify(check_latest_quarter(force_probe=False, wait=False))
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500

    @flask_app.get("/api/management-report/check-latest/status")
    def management_report_check_latest_status():
        return jsonify({"ok": True, **get_auto_update_state()})

    app_module._management_report_auto_update_installed = True
    print("Management Report automatic latest-quarter check installed")
    return True
