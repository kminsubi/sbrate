import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
import sys


_LOCK = threading.Lock()
_LAST_PROBE = {
    "at": None,
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


def check_latest_quarter(force_probe=False):
    import fisis_management as fm

    store = fm.get_management_store(trigger_refresh=False) or {}
    quarters = store.get("quarters") if isinstance(store.get("quarters"), dict) else {}
    current_latest = max(quarters.keys(), key=_quarter_rank, default="")
    target, target_month, target_as_of = _target_info(fm)

    result = {
        "ok": True,
        "checked_at": fm._now().strftime("%Y-%m-%d %H:%M:%S"),
        "current_latest": current_latest or None,
        "target_quarter": target,
        "target_as_of": target_as_of,
        "probe_required": False,
        "triggered_refresh": False,
    }

    if not target or _quarter_rank(current_latest) >= _quarter_rank(target):
        result["status"] = "latest_already_loaded"
        return result

    # 분기 종료 직후에는 대부분 미공시 상태이므로 불필요한 FISIS 호출을 줄인다.
    # 종료 40일 이후부터 새 분기 공시 여부를 확인한다.
    days_after = _days_after(target_as_of)
    result["days_after_quarter_end"] = days_after
    if days_after < 40 and not force_probe:
        result["status"] = "waiting_for_disclosure_window"
        return result

    with _LOCK:
        previous_at = _LAST_PROBE.get("at")
        previous_result = _LAST_PROBE.get("result")
        if (
            previous_at
            and not force_probe
            and fm._now() - previous_at < timedelta(hours=6)
            and isinstance(previous_result, dict)
        ):
            cached = dict(previous_result)
            cached["status"] = "recent_probe_reused"
            return cached

    companies = fm._companies()
    threshold = max(20, int(len(companies) * 0.65))
    result.update({
        "probe_required": True,
        "company_count": len(companies),
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

    if published >= threshold:
        result["triggered_refresh"] = bool(fm.trigger_management_refresh(force=True))
        result["status"] = "new_quarter_refresh_started" if result["triggered_refresh"] else "refresh_already_running"
    else:
        result["status"] = "new_quarter_not_broadly_published"

    with _LOCK:
        _LAST_PROBE["at"] = fm._now()
        _LAST_PROBE["result"] = dict(result)

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

    app_module._management_report_auto_update_installed = True
    print("Management Report automatic latest-quarter check installed")
    return True
