"""Notify on actionable second-pass failures without hiding quality warnings.

The state file is committed by the 06:30 GitHub workflow and is the
cross-run record. last_notified changes only after the HTTP alert succeeds.
"""
import argparse
import json
import os
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
STATUS_FILE = DATA / "data_quality_status.json"
RETRY_PAYLOAD_FILE = DATA / "data_quality_retry_status.json"
STATE_FILE = DATA / "data_quality_retry_alert_state.json"
ISA_FILE = DATA / "isa_rates.json"
IRP_FILE = DATA / "irp_rates.json"
KST = timezone(timedelta(hours=9))
STALE_ALERT_DAYS = 7


def load_json(path, default):
    try:
        with path.open("r", encoding="utf-8-sig") as stream:
            return json.load(stream)
    except (OSError, ValueError):
        return default


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def parsed_date(value):
    try:
        return date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return None


def bank_key(value):
    return str(value or "").lower().replace("저축은행", "").replace(" ", "")


def retry_issue(item):
    if not isinstance(item, dict):
        return False
    level = str(item.get("level") or "WARNING").upper()
    key = str(item.get("key") or "").lower()
    if level == "ERROR":
        return True
    return any(marker in key for marker in (
        ":retained:", ":fetch_failed_no_value:", ":collector_failed",
        ":disclosure_not_refreshed:",
    ))


def has_rate(row):
    rates = row.get("rates")
    if not isinstance(rates, dict):
        return False
    for value in rates.values():
        try:
            if value not in (None, "", "-") and 0.1 <= float(value) <= 10:
                return True
        except (ValueError, TypeError):
            continue
    return False


def row_for_issue(issue, isa_rows, irp_rows):
    key = str(issue.get("key") or "").lower()
    rows = isa_rows if key.startswith("isa:") else irp_rows if key.startswith("irp:") else []
    bank = key.rsplit(":", 1)[-1]
    if not isinstance(rows, list):
        return None
    return next((r for r in rows if isinstance(r, dict) and bank_key(r.get("bank")) == bank), None)


def warning_actionable(issue, previous, today, isa_rows, irp_rows, days):
    """A valid last-good rate gets a grace period; no-rate issues do not."""
    key = str(issue.get("key") or "").lower()
    if str(issue.get("level") or "").upper() == "ERROR":
        return True
    # A missing rate must never be hidden by a recent alert's cooldown.
    if ":fetch_failed_no_value:" in key or ":collector_failed" in key:
        return True
    is_freshness = ":retained:" in key or ":disclosure_not_refreshed:" in key
    row = row_for_issue(issue, isa_rows, irp_rows) if is_freshness else None
    if is_freshness and (row is None or not has_rate(row)):
        return True
    last_sent = parsed_date(previous.get("last_notified"))
    if last_sent and (today - last_sent).days < days:
        return False
    if not is_freshness:
        return True
    if ":retained:" in key:
        # Never use last_attempt_at or today's collector touch for a stale value.
        last_good = parsed_date(row.get("collected_at")) or parsed_date(row.get("updated_at"))
    else:
        # A disclosure's effective date is NOT its last successful check date.
        last_good = parsed_date(row.get("disclosure_checked_at"))
    first_seen = parsed_date(previous.get("first_seen")) or today
    since = last_good or first_seen
    return (today - since).days >= days


def build_alert(source, state, isa_rows, irp_rows, today, days=STALE_ALERT_DAYS):
    if not isinstance(source, dict) or not isinstance(source.get("issues"), list):
        raise ValueError("Data quality guard status is unavailable or invalid")
    active_before = state.get("active", {}) if isinstance(state, dict) else {}
    if not isinstance(active_before, dict):
        active_before = {}
    remaining = [issue for issue in source["issues"] if retry_issue(issue)]
    active = {}
    alerts = []
    for issue in remaining:
        key = str(issue.get("key") or "").lower()
        if not key:
            continue
        old = active_before.get(key, {})
        if not isinstance(old, dict):
            old = {}
        record = {
            "first_seen": old.get("first_seen") if parsed_date(old.get("first_seen")) else today.isoformat(),
        }
        if parsed_date(old.get("last_notified")):
            record["last_notified"] = old["last_notified"]
        active[key] = record
        if warning_actionable(issue, record, today, isa_rows, irp_rows, days):
            alerts.append(issue)

    has_error = any(str(i.get("level") or "").upper() == "ERROR" for i in remaining)
    status = "BLOCKED" if has_error else ("WARNING" if remaining else "OK")
    payload = deepcopy(source)
    payload.update({
        "status": status,
        "notify": bool(alerts),
        "issues": alerts,
        "remaining_issue_count": len(remaining),
        "verification_phase": "06:30 2차 공식소스 재확인",
        "retry_policy": "잔여 실패 기록 유지, 정상값 7일 이내 반복경고 알림 제외, 장기실패 7일 간격 통지",
    })
    return payload, {"version": 1, "active": active}, len(remaining)


def write_output(path, notify, status, issue_count, alert_count):
    if path:
        with open(path, "a", encoding="utf-8") as stream:
            stream.write(f"notify={'true' if notify else 'false'}\n")
            stream.write(f"status={status}\n")
            stream.write(f"issue_count={issue_count}\n")
            stream.write(f"alert_count={alert_count}\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--github-output", default=os.getenv("GITHUB_OUTPUT", ""))
    parser.add_argument("--mark-sent", action="store_true")
    args = parser.parse_args()
    if args.mark_sent:
        payload = load_json(RETRY_PAYLOAD_FILE, {})
        if not isinstance(payload, dict) or not payload.get("notify") or not isinstance(payload.get("issues"), list):
            raise SystemExit("No successfully submitted alert payload to acknowledge")
        state = load_json(STATE_FILE, {})
        if not isinstance(state, dict) or not isinstance(state.get("active"), dict):
            raise SystemExit("Missing alert state")
        sent_on = parsed_date(payload.get("generated_at")) or datetime.now(KST).date()
        for item in payload["issues"]:
            key = str(item.get("key") or "").lower()
            if key in state["active"]:
                state["active"][key]["last_notified"] = sent_on.isoformat()
        write_json(STATE_FILE, state)
        print("Acknowledged delivered retry alert")
        return

    source = load_json(STATUS_FILE, {})
    today = parsed_date(source.get("generated_at")) if isinstance(source, dict) else None
    if today is None:
        raise SystemExit("Invalid or missing data quality generated_at")
    payload, state, remaining_count = build_alert(
        source, load_json(STATE_FILE, {}), load_json(ISA_FILE, []),
        load_json(IRP_FILE, []), today,
    )
    write_json(RETRY_PAYLOAD_FILE, payload)
    write_json(STATE_FILE, state)
    write_output(args.github_output, payload["notify"], payload["status"], remaining_count, len(payload["issues"]))
    print(f"SBRate retry alert: status={payload['status']}, remaining={remaining_count}, alert={len(payload['issues'])}")


if __name__ == "__main__":
    main()
