import math
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
import sys


MIN_QUARTER_COVERAGE = 0.90

_LOCK = threading.Lock()
_STATE = {
    "running": False,
    "started_at": None,
    "finished_at": None,
    "last_probe_at": None,
    "result": None,
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


def _probe_worker(base_result, target, target_month):
    import fisis_management as fm

    result = dict(base_result)
    try:
        companies = fm._companies()
        threshold = max(20, math.ceil(len(companies) * MIN_QUARTER_COVERAGE))
        stored_count = int(result.get("stored_asset_count") or 0)
        result.update({
            "probe_required": True,
            "company_count": len(companies),
            "coverage_ratio_required": MIN_QUARTER_COVERAGE,
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

        # 새 분기 최초 승격: 90% 이상 공시됐을 때만 전체 데이터를 받는다.
        # 이미 최신분기로 승격된 뒤에는 추가 은행이 공시될 때마다 다시 받아
        # 72/79 같은 중간 상태에 멈추지 않도록 한다.
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
        with _LOCK:
            _STATE["running"] = False
            _STATE["finished_at"] = now
            _STATE["last_probe_at"] = now
            _STATE["result"] = dict(result)


def check_latest_quarter(force_probe=False):
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
        "coverage_ratio_required": MIN_QUARTER_COVERAGE,
        "stored_asset_count": stored_target_count,
        "active_company_count": active_count,
        "probe_required": False,
        "triggered_refresh": False,
    }

    if not target:
        result["status"] = "latest_already_loaded"
        return result

    # 목표 분기가 이미 최신이어도 전 은행 데이터가 다 들어오기 전까지는
    # 하루 두 번 가볍게 총자산 공시 수를 확인해 후속 공시를 자동 반영한다.
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

    # 이미 전체 FISIS 캐시를 갱신 중이면 같은 API를 중복 호출하지 않는다.
    refresh_state = fm.get_refresh_state()
    if bool(refresh_state.get("running")) and not force_probe:
        result["status"] = "management_refresh_running"
        return result

    with _LOCK:
        if _STATE.get("running"):
            result["status"] = "probe_running"
            return result

        previous_at = _STATE.get("last_probe_at")
        previous_result = _STATE.get("result")
        if (
            previous_at
            and not force_probe
            and fm._now() - previous_at < timedelta(hours=6)
            and isinstance(previous_result, dict)
        ):
            cached = dict(previous_result)
            cached["status"] = "recent_probe_reused"
            return cached

        _STATE["running"] = True
        _STATE["started_at"] = fm._now()

    thread = threading.Thread(
        target=_probe_worker,
        args=(result, target, target_month),
        name="sbrate-fisis-latest-quarter-probe",
        daemon=True,
    )
    thread.start()

    result["probe_required"] = True
    result["status"] = "probe_started"
    return result


def get_auto_update_state():
    with _LOCK:
        result = dict(_STATE.get("result") or {})
        result["running"] = bool(_STATE.get("running"))
        started = _STATE.get("started_at")
        finished = _STATE.get("finished_at")
        result["started_at"] = started.strftime("%Y-%m-%d %H:%M:%S") if started else None
        result["finished_at"] = finished.strftime("%Y-%m-%d %H:%M:%S") if finished else result.get("finished_at")
        return result


def install_management_report_auto_update():
    app_module = sys.modules.get("app") or sys.modules.get("__main__")
    if app_module is None or not hasattr(app_module, "app"):
        return False
    if getattr(app_module, "_management_report_auto_update_installed", False):
        return True

    flask_app = app_module.app
    from flask import jsonify, request

    @flask_app.get("/api/management-report/check-latest")
    def management_report_check_latest():
        force_probe = str(request.args.get("force") or "").strip() == "1"
        try:
            return jsonify(check_latest_quarter(force_probe=force_probe))
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500

    @flask_app.get("/api/management-report/check-latest/status")
    def management_report_check_latest_status():
        return jsonify({"ok": True, **get_auto_update_state()})

    app_module._management_report_auto_update_installed = True
    print("Management Report automatic latest-quarter check installed")
    return True
