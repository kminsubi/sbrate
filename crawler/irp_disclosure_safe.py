import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import irp_disclosure as source


BASE = Path(__file__).resolve().parent.parent
OUTPUT = BASE / "data" / "irp_disclosure_rates.json"
KST = timezone(timedelta(hours=9))


def _load_existing():
    try:
        with OUTPUT.open("r", encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return {}


def main():
    targets = source.load_targets()
    previous = _load_existing()
    all_rows = []
    source_errors = []

    print("=" * 72)
    print("SBRate IRP disclosure safe refresh")
    print("=" * 72)

    for item in source.DISCLOSURE_URLS:
        try:
            html, final_url = source.fetch_html(item["url"])
            rows = source.parse_tables(
                html,
                item["name"],
                final_url,
                targets,
            )
            all_rows.extend(rows)
            print(item["name"], "rows=", len(rows))
        except Exception as error:
            source_errors.append({
                "source": item["name"],
                "url": item["url"],
                "error": str(error),
            })
            print(item["name"], "ERROR:", error)

    # Do not replace the last known disclosure with an empty result caused by
    # a temporary provider-site outage or parsing failure.
    if not all_rows:
        print("No verified disclosure rows collected; preserving previous file")
        if previous:
            raise SystemExit(2)
        raise SystemExit(3)

    banks = source.build_bank_results(all_rows, targets)
    verified_count = sum(
        1
        for item in banks.values()
        if str(item.get("status") or "").startswith("verified_disclosure")
    )

    if verified_count < 5:
        print(
            "Disclosure result too small; preserving previous file:",
            verified_count,
        )
        raise SystemExit(4)

    # GitHub Actions runners use UTC. Store verification timestamps explicitly
    # in KST so 00:30/06:30 runs are classified as the correct Korean date.
    now_text = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    for item in banks.values():
        if isinstance(item, dict):
            item["updated_at"] = now_text
            item["verification_timezone"] = "Asia/Seoul"

    payload = {
        "generated_at": now_text,
        "timezone": "Asia/Seoul",
        "strategy": "retirement_provider_disclosure",
        "sources": source.DISCLOSURE_URLS,
        "source_errors": source_errors,
        "banks": banks,
        "raw_match_count": len(all_rows),
        "daily_refresh_verified": True,
    }

    source.save_json(OUTPUT, payload)
    print("verified banks:", verified_count)
    print("saved:", OUTPUT)


if __name__ == "__main__":
    main()
