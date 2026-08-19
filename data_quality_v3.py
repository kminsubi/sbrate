# SBRate Data Quality Guard V3
# Refines 'today verified' so official disclosure merges count as verified,
# while explicit fallback/fetch-error rows never masquerade as fresh checks.
import data_quality_v2 as guard


def _verified_today(row):
    status = str(row.get("status") or "").lower()
    disclosure_status = str(row.get("disclosure_status") or "").lower()
    row_date = guard._row_date(row)
    if row_date != guard.base.now_kst().date():
        return False

    # A current official pension-provider disclosure is a valid verification
    # source even if the bank's own page was unavailable in the same run.
    if disclosure_status == "verified_disclosure":
        return True

    # Explicit fallback/error rows must not be presented as freshly verified.
    if (
        "fallback" in status
        or row.get("fetch_error")
        or str(row.get("last_fetch_status") or "").lower() in ("fetch_error", "fetch_or_parse_error")
    ):
        return False

    return status.startswith("verified_official")


guard._verified_today = _verified_today


if __name__ == "__main__":
    guard.main()
