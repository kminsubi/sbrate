# SBRate Data Quality Guard V2
# Distinguishes today's official verification, retained last-good values,
# and rates that are still unavailable. Suppresses false stale-date warnings
# when today's official source was successfully checked.
import argparse
import os
from datetime import datetime

import data_quality as base


def _row_date(row):
    for key in ("last_attempt_at", "collected_at", "updated_at"):
        value = base.parse_date(row.get(key))
        if value is not None:
            return value
    return None


def _verified_today(row):
    status = str(row.get("status") or "").lower()
    if not status.startswith("verified_official"):
        return False
    row_date = _row_date(row)
    return row_date == base.now_kst().date()


def validate_pension_file_v2(label, path, issues, collector_outcome):
    rows = base.load_json(path, [])
    if collector_outcome != "success":
        base.add_issue(
            issues, "ERROR", f"{label.lower()}:collector_failed", label,
            f"{label} 수집기가 정상 완료되지 않았습니다."
        )

    if not isinstance(rows, list) or not rows:
        base.add_issue(
            issues, "ERROR", f"{label.lower()}:empty", label,
            f"{label} 데이터가 비어 있거나 형식이 잘못되었습니다."
        )
        return {
            "rows": 0, "banks": 0, "valid_rate_rows": 0,
            "verified_today": 0, "retained_last_good": 0,
            "unavailable_rows": 0, "fetch_failed_rows": 0,
            "woori_rate_12m": None,
        }

    rows = [row for row in rows if isinstance(row, dict)]
    banks = {
        base.normalize_name(row.get("bank"))
        for row in rows if base.normalize_name(row.get("bank"))
    }

    expected = base.expected_pension_banks()
    if expected:
        minimum = max(6, int(len(expected) * 0.65))
        if len(banks) < minimum:
            base.add_issue(
                issues, "ERROR", f"{label.lower()}:bank_count_collapse", label,
                f"은행 수가 {len(banks)}개사로 예상 범위({len(expected)}개사 기준)보다 크게 적습니다."
            )

    invalid_rates = 0
    valid_rate_rows = 0
    verified_today = 0
    retained_last_good = 0
    unavailable_rows = 0
    fetch_failed_rows = 0
    duplicate_banks = len(rows) - len(banks)
    missing_disclosure = 0
    old_unverified_disclosure = []

    today = base.now_kst().date()

    for row in rows:
        rates = row.get("rates") if isinstance(row.get("rates"), dict) else {}
        values = [base.safe_float(rates.get(key)) for key in base.PENSION_PERIODS]
        non_null = [value for value in values if value is not None]
        if non_null:
            valid_rate_rows += 1
        for value in non_null:
            if value < 0.10 or value > 10.0:
                invalid_rates += 1

        status = str(row.get("status") or "").lower()
        bank = str(row.get("bank") or "-")
        is_stale = (
            "stale" in status
            or row.get("stale") is True
            or row.get("retained_last_good") is True
        )
        is_fetch_error = "fetch_error" in status or "fetch_or_parse_error" in status
        is_today_verified = _verified_today(row)

        if is_today_verified:
            verified_today += 1

        if is_stale:
            retained_last_good += 1
            attempt_date = base.parse_date(row.get("last_attempt_at"))
            when = "오늘" if attempt_date == today else "최근"
            base.add_issue(
                issues,
                "WARNING",
                f"{label.lower()}:retained:{base.normalize_name(bank)}",
                label,
                f"{bank} {when} 공식확인 실패 → 직전 정상값 유지 중입니다.",
            )
        elif is_fetch_error and not non_null:
            fetch_failed_rows += 1
            base.add_issue(
                issues,
                "WARNING",
                f"{label.lower()}:fetch_failed_no_value:{base.normalize_name(bank)}",
                label,
                f"{bank} 공식확인에 실패했고 현재 표시 가능한 금리가 없습니다.",
            )
        elif not non_null:
            unavailable_rows += 1

        # An old disclosure/effective date is not an anomaly when the official
        # source itself was successfully checked today. It may simply mean the
        # bank has not changed its rate for a long time.
        disclosure = base.parse_date(
            row.get("disclosure_date")
            or row.get("reference_date")
            or row.get("effective_date")
        )
        if not is_today_verified and not is_stale and non_null:
            if disclosure is None:
                missing_disclosure += 1
            else:
                age = (today - disclosure).days
                if age > 60:
                    old_unverified_disclosure.append((bank, age))

    if invalid_rates:
        base.add_issue(
            issues, "ERROR", f"{label.lower()}:invalid_rate_range", label,
            f"정상 범위(0.10~10.00%)를 벗어난 금리가 {invalid_rates}건 있습니다."
        )

    if rows and valid_rate_rows / len(rows) < 0.40:
        base.add_issue(
            issues, "ERROR", f"{label.lower()}:too_few_valid_rows", label,
            f"금리가 확인된 은행이 {valid_rate_rows}/{len(rows)}개사로 너무 적습니다."
        )

    if unavailable_rows:
        base.add_issue(
            issues,
            "WARNING",
            f"{label.lower()}:unavailable_rows",
            label,
            f"금리 미확보 은행이 {unavailable_rows}개사입니다. 오늘 실패한 은행과는 별도 관리합니다.",
        )

    if duplicate_banks > 0:
        base.add_issue(
            issues, "WARNING", f"{label.lower()}:duplicate_banks", label,
            f"동일 은행 중복 행이 {duplicate_banks}건 있습니다."
        )

    if missing_disclosure >= max(3, int(len(rows) * 0.25)):
        base.add_issue(
            issues, "WARNING", f"{label.lower()}:missing_disclosure", label,
            f"오늘 공식확인이 되지 않은 데이터 중 공시기준일이 없는 은행이 {missing_disclosure}개사입니다."
        )

    if old_unverified_disclosure:
        bank, age = max(old_unverified_disclosure, key=lambda item: item[1])
        base.add_issue(
            issues, "WARNING", f"{label.lower()}:old_unverified_disclosure", label,
            f"오늘 공식확인이 되지 않은 데이터 중 기준일 장기 미갱신 후보가 있습니다: {bank} {age}일."
        )

    woori_rows = [row for row in rows if base.is_woori(row)]
    if not woori_rows:
        base.add_issue(
            issues, "ERROR", f"{label.lower()}:woori_missing", label,
            "우리금융저축은행 데이터가 누락되었습니다."
        )
        woori_rate = None
    else:
        woori_rate = max(
            (
                base.safe_float((row.get("rates") or {}).get("12m"))
                for row in woori_rows
                if isinstance(row.get("rates"), dict)
                and base.safe_float((row.get("rates") or {}).get("12m")) is not None
            ),
            default=None,
        )
        if woori_rate is None:
            base.add_issue(
                issues, "ERROR", f"{label.lower()}:woori_12m_missing", label,
                "우리금융 12개월 금리가 비어 있습니다."
            )

    return {
        "rows": len(rows),
        "banks": len(banks),
        "valid_rate_rows": valid_rate_rows,
        "verified_today": verified_today,
        "retained_last_good": retained_last_good,
        "unavailable_rows": unavailable_rows,
        "fetch_failed_rows": fetch_failed_rows,
        "woori_rate_12m": woori_rate,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--deposit-outcome", default=os.getenv("DEPOSIT_OUTCOME", "success"))
    parser.add_argument("--pension-outcome", default=os.getenv("PENSION_OUTCOME", "success"))
    parser.add_argument("--github-output", default=os.getenv("GITHUB_OUTPUT", ""))
    args = parser.parse_args()

    base.validate_pension_file = validate_pension_file_v2
    result = base.run_guard(
        deposit_outcome=str(args.deposit_outcome or "unknown").lower(),
        pension_outcome=str(args.pension_outcome or "unknown").lower(),
    )
    base.write_github_output(args.github_output, result)


if __name__ == "__main__":
    main()
