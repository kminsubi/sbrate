import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"
DISCLOSURE = DATA / "irp_disclosure_rates.json"
IRP = DATA / "irp_rates.json"
KST = timezone(timedelta(hours=9))


def load(path, default):
    try:
        with path.open("r", encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return default


def save(path, value):
    with path.open("w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)


def parse_day(value):
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except Exception:
        try:
            return datetime.strptime(text[:10], "%Y-%m-%d").date()
        except Exception:
            return None


def has_rate(item):
    rates = item.get("rates") if isinstance(item, dict) else None
    if not isinstance(rates, dict):
        return False
    return any(isinstance(value, (int, float)) for value in rates.values())


def source_product(item):
    for source in item.get("sources", []) if isinstance(item, dict) else []:
        if not isinstance(source, dict):
            continue
        product = str(source.get("product") or "").strip()
        if not product:
            continue
        if "/" in product:
            product = product.split("/", 1)[1].strip()
        if product:
            return product
    return None


def main():
    disclosure = load(DISCLOSURE, {})
    rows = load(IRP, [])

    if not isinstance(disclosure, dict) or not isinstance(rows, list):
        print("IRP disclosure postprocess: invalid input")
        return

    today = datetime.now(KST).date()
    generated_at = str(disclosure.get("generated_at") or "").strip()
    generated_day = parse_day(generated_at)
    fresh_daily = (
        generated_day == today
        and disclosure.get("daily_refresh_verified") is True
        and not disclosure.get("source_errors")
    )

    if not fresh_daily:
        print(
            "IRP disclosure postprocess: today's verified disclosure unavailable; "
            "no fresh fallback applied"
        )
        return

    bank_map = disclosure.get("banks")
    if not isinstance(bank_map, dict):
        return

    changed = 0

    for row in rows:
        if not isinstance(row, dict):
            continue

        bank = str(row.get("bank") or "").strip()
        disc = bank_map.get(bank)
        if not isinstance(disc, dict):
            continue

        disc_status = str(disc.get("status") or "")
        if not disc_status.startswith("verified_disclosure") or not has_rate(disc):
            continue

        checked_at = str(disc.get("updated_at") or generated_at).strip()
        checked_day = parse_day(checked_at)
        if checked_day != today:
            continue

        # Record the actual daily verification timestamp for quality guard.
        row["disclosure_checked_at"] = checked_at

        if isinstance(disc.get("sources"), list) and disc.get("sources"):
            row["disclosure_sources"] = disc.get("sources")
        row["disclosure_status"] = disc_status

        # Korea Investment direct WebSquare is currently unstable in Actions.
        # If the direct collection has no usable rate, use today's official
        # pension-provider disclosure instead of leaving IRP blank.
        if bank == "한국투자" and not has_rate(row):
            direct_status = str(row.get("status") or "")
            direct_error = str(
                row.get("error")
                or row.get("last_fetch_error")
                or row.get("note")
                or ""
            ).strip()

            row["direct_fetch_status"] = direct_status
            if direct_error:
                row["direct_fetch_error"] = direct_error

            row["rates"] = dict(disc.get("rates") or {})
            row["status"] = "verified_disclosure_fallback"
            row["product"] = row.get("product") or source_product(disc) or "정기예금"
            row["source_url"] = (
                (disc.get("sources") or [{}])[0].get("source_url")
                or row.get("source_url")
            )
            row["note"] = (
                "한국투자저축은행 직접 WebSquare 자동확인 실패. "
                "금리는 오늘 재확인한 KB퇴직연금 타사제공상품 공식 공시의 "
                "IRP 금리를 표시합니다."
            )
            row["fallback_reason"] = "direct_websquare_failed_fresh_provider_disclosure_used"
            row["fallback_verified_at"] = checked_at
            changed += 1
        else:
            changed += 1

    if changed:
        save(IRP, rows)

    print("IRP disclosure postprocess changed rows:", changed)
    print("daily disclosure generated_at:", generated_at)


if __name__ == "__main__":
    main()
