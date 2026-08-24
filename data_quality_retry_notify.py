import argparse
import json
import os
from copy import deepcopy
from pathlib import Path


BASE = Path(__file__).resolve().parent
STATUS_FILE = BASE / "data" / "data_quality_status.json"
RETRY_PAYLOAD_FILE = BASE / "data" / "data_quality_retry_status.json"


def load_json(path, default):
    try:
        with path.open("r", encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return default


def retry_issue(item):
    if not isinstance(item, dict):
        return False

    level = str(item.get("level") or "WARNING").upper()
    key = str(item.get("key") or "").lower()

    if level == "ERROR":
        return True

    retry_markers = (
        ":retained:",
        ":fetch_failed_no_value:",
        ":collector_failed",
    )
    return any(marker in key for marker in retry_markers)


def write_output(path, notify, status, issue_count):
    if not path:
        return
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"notify={'true' if notify else 'false'}\n")
        f.write(f"status={status}\n")
        f.write(f"issue_count={issue_count}\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--github-output", default=os.getenv("GITHUB_OUTPUT", ""))
    args = parser.parse_args()

    source = load_json(STATUS_FILE, {})
    issues = source.get("issues") if isinstance(source.get("issues"), list) else []
    remaining = [item for item in issues if retry_issue(item)]

    has_error = any(str(item.get("level") or "").upper() == "ERROR" for item in remaining)
    notify = bool(remaining)
    status = "BLOCKED" if has_error else ("WARNING" if notify else "OK")

    payload = deepcopy(source) if isinstance(source, dict) else {}
    payload["status"] = status
    payload["notify"] = notify
    payload["issues"] = remaining
    payload["verification_phase"] = "06:30 2차 공식소스 재확인"
    payload["retry_policy"] = "00:30 1차 실패 은행만 재확인 후 잔여 실패만 알림"

    RETRY_PAYLOAD_FILE.parent.mkdir(parents=True, exist_ok=True)
    with RETRY_PAYLOAD_FILE.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    write_output(args.github_output, notify, status, len(remaining))

    print("=" * 68)
    print("SBRate 06:30 retry alert filter")
    print("status:", status)
    print("notify:", notify)
    print("remaining retry issues:", len(remaining))
    for item in remaining:
        print(f"[{item.get('level','WARNING')}] {item.get('section','-')} - {item.get('message','-')}")
    print("=" * 68)


if __name__ == "__main__":
    main()
