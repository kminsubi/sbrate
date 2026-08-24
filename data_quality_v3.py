# SBRate Data Quality Guard V3
# Refines 'today verified' so official disclosure merges count as verified,
# while explicit fallback/fetch-error rows never masquerade as fresh checks.
import data_quality_v2 as guard


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


guard._verified_today = _verified_today


if __name__ == "__main__":
    guard.main()
