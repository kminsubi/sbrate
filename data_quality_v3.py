# SBRate Data Quality Guard V3
# Refines 'today verified' so official disclosure merges count as verified,
# while explicit fallback/fetch-error rows never masquerade as fresh checks.
import data_quality_v2 as guard


_original_validate_pension = guard.validate_pension_file_v2


def _verified_today(row):
    status = str(row.get("status") or "").lower()
    disclosure_status = str(row.get("disclosure_status") or "").lower()
    today = guard.base.now_kst().date()
    row_date = guard._row_date(row)

    if row_date != today:
        return False

    # Pension-provider disclosure is valid as today's verification only when
    # that disclosure itself was actually refreshed today. A stale disclosure
    # file must never become 'today verified' merely because another collector
    # touched the row today.
    if disclosure_status.startswith("verified_disclosure"):
        disclosure_checked = guard.base.parse_date(
            row.get("disclosure_checked_at")
        )
        if disclosure_checked == today:
            return True

    # Explicit fallback/error rows must not be presented as freshly verified,
    # unless the fresh disclosure check above already verified the value.
    if (
        "fallback" in status
        or row.get("fetch_error")
        or str(row.get("last_fetch_status") or "").lower()
        in ("fetch_error", "fetch_or_parse_error")
    ):
        return False

    return status.startswith("verified_official")


def _validate_pension_v3(label, path, issues, collector_outcome):
    result = _original_validate_pension(
        label,
        path,
        issues,
        collector_outcome,
    )

    if str(label).upper() != "IRP":
        return result

    rows = guard.base.load_json(path, [])
    if not isinstance(rows, list):
        return result

    today = guard.base.now_kst().date()

    for row in rows:
        if not isinstance(row, dict):
            continue

        status = str(row.get("status") or "").lower()
        relies_on_disclosure = status in (
            "verified_disclosure_merged",
            "verified_disclosure_fallback",
        )
        if not relies_on_disclosure:
            continue

        checked = guard.base.parse_date(
            row.get("disclosure_checked_at")
        )
        if checked == today:
            continue

        bank = str(row.get("bank") or "-")
        guard.base.add_issue(
            issues,
            "WARNING",
            f"irp:disclosure_not_refreshed:{guard.base.normalize_name(bank)}",
            "IRP",
            f"{bank} IRP 공통공시를 오늘 재확인하지 못해 최신 검증 상태가 아닙니다.",
        )

    return result


guard._verified_today = _verified_today
guard.validate_pension_file_v2 = _validate_pension_v3


if __name__ == "__main__":
    guard.main()
