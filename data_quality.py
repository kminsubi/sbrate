# ==========================================
# SBRate Data Quality Guard V1
# - Validate deposit / ISA / IRP after collection
# - Block obviously broken data before GitHub commit
# - Write machine-readable status for audit
# ==========================================

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DEPOSIT_FILE = os.path.join(DATA_DIR, "latest_rates.json")
PREVIOUS_DEPOSIT_FILE = os.path.join(DATA_DIR, "previous_rates.json")
ISA_FILE = os.path.join(DATA_DIR, "isa_rates.json")
IRP_FILE = os.path.join(DATA_DIR, "irp_rates.json")
PENSION_SOURCES_FILE = os.path.join(BASE_DIR, "pension_sources.json")
STATUS_FILE = os.path.join(DATA_DIR, "data_quality_status.json")
KST = timezone(timedelta(hours=9))
DEPOSIT_PERIODS = ("1", "3", "6", "12", "24", "36")
PENSION_PERIODS = ("3m", "6m", "12m", "24m", "36m")


def now_kst():
    return datetime.now(KST)


def load_json(path, default=None):
    if default is None:
        default = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def safe_float(value):
    if value in (None, "", "-"):
        return None
    try:
        return float(str(value).replace(",", "").replace("%", "").strip())
    except Exception:
        return None


def normalize_name(value):
    return (
        str(value or "")
        .replace("(주)", "")
        .replace("㈜", "")
        .replace("주식회사", "")
        .replace("저축은행", "")
        .replace(" ", "")
        .strip()
        .lower()
    )


def parse_date(value):
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            return datetime.strptime(text, fmt).date()
        except Exception:
            pass
    return None


def add_issue(issues, level, key, section, message):
    issues.append({"level": level, "key": key, "section": section, "message": message})


def is_woori(row):
    return normalize_name((row or {}).get("bank")) == "우리금융"


def load_previous_status():
    previous = load_json(STATUS_FILE, {})
    return previous if isinstance(previous, dict) else {}


def validate_deposit(issues, collector_outcome):
    latest = load_json(DEPOSIT_FILE, [])
    previous = load_json(PREVIOUS_DEPOSIT_FILE, [])

    if collector_outcome != "success":
        add_issue(issues, "ERROR", "deposit:collector_failed", "정기예금", "정기예금 수집기가 정상 완료되지 않았습니다.")

    if not isinstance(latest, list) or not latest:
        add_issue(issues, "ERROR", "deposit:empty", "정기예금", "정기예금 데이터가 비어 있거나 형식이 잘못되었습니다.")
        return {"items": 0, "banks": 0, "previous_items": 0, "previous_banks": 0, "woori_rate_12m": None}

    latest = [x for x in latest if isinstance(x, dict)]
    previous = [x for x in previous if isinstance(x, dict)] if isinstance(previous, list) else []
    banks = {normalize_name(x.get("bank")) for x in latest if normalize_name(x.get("bank"))}
    previous_banks = {normalize_name(x.get("bank")) for x in previous if normalize_name(x.get("bank"))}
    current_count = len(latest)
    previous_count = len(previous)

    if previous_count:
        min_items = max(150, int(previous_count * 0.75))
        if current_count < min_items:
            add_issue(issues, "ERROR", "deposit:item_count_collapse", "정기예금", f"상품 수가 직전 {previous_count}건에서 {current_count}건으로 급감했습니다.")

    if previous_banks:
        min_banks = max(50, int(len(previous_banks) * 0.80))
        if len(banks) < min_banks:
            add_issue(issues, "ERROR", "deposit:bank_count_collapse", "정기예금", f"은행 수가 직전 {len(previous_banks)}개사에서 {len(banks)}개사로 급감했습니다.")

    if len(banks) < 50:
        add_issue(issues, "ERROR", "deposit:bank_count_too_low", "정기예금", f"수집 은행 수가 {len(banks)}개사로 비정상적으로 적습니다.")

    invalid_rate_count = 0
    empty_rate_rows = 0
    extreme_changes = []
    for row in latest:
        valid_rates = 0
        for period in DEPOSIT_PERIODS:
            rate = safe_float(row.get(f"top_{period}m"))
            if rate is None:
                continue
            valid_rates += 1
            if rate < 0.10 or rate > 10.0:
                invalid_rate_count += 1
            change = safe_float(row.get(f"change_{period}"))
            if change is not None and abs(change) >= 0.50:
                extreme_changes.append((str(row.get("bank") or "-"), str(row.get("product") or "-"), period, change))
        if valid_rates == 0:
            empty_rate_rows += 1

    if invalid_rate_count:
        add_issue(issues, "ERROR", "deposit:invalid_rate_range", "정기예금", f"정상 범위(0.10~10.00%)를 벗어난 금리가 {invalid_rate_count}건 있습니다.")

    if latest and empty_rate_rows / len(latest) >= 0.15:
        add_issue(issues, "WARNING", "deposit:many_empty_rates", "정기예금", f"전체 기간 금리가 비어 있는 상품이 {empty_rate_rows}건입니다.")

    if extreme_changes:
        max_change = max(extreme_changes, key=lambda x: abs(x[3]))
        level = "ERROR" if abs(max_change[3]) >= 2.0 else "WARNING"
        bank, product, period, change = max_change
        add_issue(issues, level, "deposit:large_rate_change", "정기예금", f"비정상 급변 후보: {bank} {product} {period}개월 {change:+.2f}%p.")

    woori_rows = [row for row in latest if is_woori(row)]
    woori_rep = [row for row in woori_rows if "회전정기예금" in str(row.get("product") or "").replace(" ", "")]

    if not woori_rows:
        add_issue(issues, "ERROR", "deposit:woori_missing", "정기예금", "우리금융저축은행 데이터가 누락되었습니다.")

    if not woori_rep:
        add_issue(issues, "ERROR", "deposit:woori_rep_missing", "정기예금", "우리금융 대표상품 '회전정기예금'이 누락되었습니다.")
        woori_rate = None
    else:
        woori_rate = max((safe_float(row.get("top_12m")) for row in woori_rep if safe_float(row.get("top_12m")) is not None), default=None)
        if woori_rate is None:
            add_issue(issues, "ERROR", "deposit:woori_rep_rate_missing", "정기예금", "우리금융 회전정기예금 12개월 금리가 비어 있습니다.")

    return {"items": current_count, "banks": len(banks), "previous_items": previous_count, "previous_banks": len(previous_banks), "woori_rate_12m": woori_rate}


def expected_pension_banks():
    sources = load_json(PENSION_SOURCES_FILE, {})
    if not isinstance(sources, dict):
        return set()
    return {normalize_name(name) for name in sources.keys() if normalize_name(name)}


def validate_pension_file(label, path, issues, collector_outcome):
    rows = load_json(path, [])
    if collector_outcome != "success":
        add_issue(issues, "ERROR", f"{label.lower()}:collector_failed", label, f"{label} 수집기가 정상 완료되지 않았습니다.")
    if not isinstance(rows, list) or not rows:
        add_issue(issues, "ERROR", f"{label.lower()}:empty", label, f"{label} 데이터가 비어 있거나 형식이 잘못되었습니다.")
        return {"rows": 0, "banks": 0, "valid_rate_rows": 0, "stale_rows": 0, "woori_rate_12m": None}

    rows = [x for x in rows if isinstance(x, dict)]
    banks = {normalize_name(x.get("bank")) for x in rows if normalize_name(x.get("bank"))}
    expected = expected_pension_banks()
    if expected:
        minimum = max(6, int(len(expected) * 0.65))
        if len(banks) < minimum:
            add_issue(issues, "ERROR", f"{label.lower()}:bank_count_collapse", label, f"은행 수가 {len(banks)}개사로 예상 범위({len(expected)}개사 기준)보다 크게 적습니다.")

    invalid_rates = 0
    valid_rate_rows = 0
    all_null_rows = 0
    stale_rows = 0
    missing_disclosure = 0
    old_disclosure = []
    duplicate_banks = len(rows) - len(banks)

    for row in rows:
        rates = row.get("rates") if isinstance(row.get("rates"), dict) else {}
        values = [safe_float(rates.get(key)) for key in PENSION_PERIODS]
        non_null = [v for v in values if v is not None]
        if non_null:
            valid_rate_rows += 1
        else:
            all_null_rows += 1
        for value in non_null:
            if value < 0.10 or value > 10.0:
                invalid_rates += 1

        status = str(row.get("status") or "").lower()
        if "stale" in status or "fetch_error" in status or row.get("stale") is True:
            stale_rows += 1
            bank = str(row.get("bank") or "-")
            add_issue(issues, "WARNING", f"{label.lower()}:stale:{normalize_name(bank)}", label, f"{bank} 데이터가 직전 정상값 유지 상태입니다.")

        disclosure = parse_date(row.get("disclosure_date") or row.get("reference_date") or row.get("effective_date"))
        if disclosure is None and non_null:
            missing_disclosure += 1
        elif disclosure is not None:
            age = (now_kst().date() - disclosure).days
            if age > 60:
                old_disclosure.append((str(row.get("bank") or "-"), age))

    if invalid_rates:
        add_issue(issues, "ERROR", f"{label.lower()}:invalid_rate_range", label, f"정상 범위(0.10~10.00%)를 벗어난 금리가 {invalid_rates}건 있습니다.")

    if rows and valid_rate_rows / len(rows) < 0.40:
        add_issue(issues, "ERROR", f"{label.lower()}:too_few_valid_rows", label, f"금리가 확인된 은행이 {valid_rate_rows}/{len(rows)}개사로 너무 적습니다.")
    elif all_null_rows >= max(3, int(len(rows) * 0.25)):
        add_issue(issues, "WARNING", f"{label.lower()}:many_null_rows", label, f"전 기간 금리가 비어 있는 은행이 {all_null_rows}개사입니다.")

    if duplicate_banks > 0:
        add_issue(issues, "WARNING", f"{label.lower()}:duplicate_banks", label, f"동일 은행 중복 행이 {duplicate_banks}건 있습니다.")
    if missing_disclosure >= max(3, int(len(rows) * 0.25)):
        add_issue(issues, "WARNING", f"{label.lower()}:missing_disclosure", label, f"금리는 있으나 공시기준일이 없는 은행이 {missing_disclosure}개사입니다.")
    if old_disclosure:
        bank, age = max(old_disclosure, key=lambda x: x[1])
        add_issue(issues, "WARNING", f"{label.lower()}:old_disclosure", label, f"공시기준일 장기 미갱신 후보가 있습니다. 가장 오래된 곳: {bank} {age}일.")

    woori_rows = [row for row in rows if is_woori(row)]
    if not woori_rows:
        add_issue(issues, "ERROR", f"{label.lower()}:woori_missing", label, "우리금융저축은행 데이터가 누락되었습니다.")
        woori_rate = None
    else:
        woori_rate = max((safe_float((row.get("rates") or {}).get("12m")) for row in woori_rows if isinstance(row.get("rates"), dict) and safe_float((row.get("rates") or {}).get("12m")) is not None), default=None)
        if woori_rate is None:
            add_issue(issues, "ERROR", f"{label.lower()}:woori_12m_missing", label, "우리금융 12개월 금리가 비어 있습니다.")

    return {"rows": len(rows), "banks": len(banks), "valid_rate_rows": valid_rate_rows, "stale_rows": stale_rows, "woori_rate_12m": woori_rate}


def issue_fingerprint(issues):
    keys = sorted(str(item.get("key") or "") for item in issues)
    raw = "\n".join(keys).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16] if keys else ""


def write_github_output(path, result):
    if not path:
        return
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"status={result['status']}\n")
        f.write(f"block={'true' if result['block'] else 'false'}\n")
        f.write(f"notify={'true' if result['notify'] else 'false'}\n")
        f.write(f"issue_count={len(result['issues'])}\n")


def run_guard(deposit_outcome="success", pension_outcome="success"):
    issues = []
    previous_status = load_previous_status()
    counts = {
        "deposit": validate_deposit(issues, deposit_outcome),
        "isa": validate_pension_file("ISA", ISA_FILE, issues, pension_outcome),
        "irp": validate_pension_file("IRP", IRP_FILE, issues, pension_outcome),
    }
    has_error = any(item.get("level") == "ERROR" for item in issues)
    has_warning = any(item.get("level") == "WARNING" for item in issues)
    status = "BLOCKED" if has_error else ("WARNING" if has_warning else "OK")
    fingerprint = issue_fingerprint(issues)
    previous_fingerprint = str(previous_status.get("fingerprint") or "")
    previous_status_name = str(previous_status.get("status") or "")
    notify = False
    if status == "BLOCKED":
        notify = True
    elif status == "WARNING":
        notify = fingerprint != previous_fingerprint or previous_status_name not in ("WARNING", "BLOCKED")

    result = {
        "generated_at": now_kst().strftime("%Y-%m-%d %H:%M:%S"),
        "timezone": "Asia/Seoul",
        "status": status,
        "block": has_error,
        "notify": notify,
        "fingerprint": fingerprint,
        "previous_fingerprint": previous_fingerprint,
        "collector_outcomes": {"deposit": deposit_outcome, "pension": pension_outcome},
        "counts": counts,
        "issues": issues,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print("=" * 68)
    print("SBRate Data Quality Guard")
    print("status:", status)
    print("issues:", len(issues))
    print("notify:", notify)
    for item in issues[:12]:
        print(f"[{item['level']}] {item['section']} - {item['message']}")
    print("=" * 68)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--deposit-outcome", default=os.getenv("DEPOSIT_OUTCOME", "success"))
    parser.add_argument("--pension-outcome", default=os.getenv("PENSION_OUTCOME", "success"))
    parser.add_argument("--github-output", default=os.getenv("GITHUB_OUTPUT", ""))
    args = parser.parse_args()
    result = run_guard(
        deposit_outcome=str(args.deposit_outcome or "unknown").lower(),
        pension_outcome=str(args.pension_outcome or "unknown").lower(),
    )
    write_github_output(args.github_output, result)


if __name__ == "__main__":
    main()
