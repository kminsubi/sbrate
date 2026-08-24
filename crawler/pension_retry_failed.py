import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pension_rates as pr


BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"
MAP = DATA / "pension_source_map.json"
ISA = DATA / "isa_rates.json"
IRP = DATA / "irp_rates.json"

KST = timezone(timedelta(hours=9))
RETRY_STATUSES = {
    "stale_retained_after_fetch_error",
    "fetch_or_parse_error",
    "rate_not_found",
    "verified_official_fallback",
}


def load(path, default):
    try:
        with path.open("r", encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return default


def save(path, value):
    with path.open("w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)


def by_bank(rows):
    result = {}
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        bank = pr.clean(row.get("bank"))
        if bank:
            result[bank] = row
    return result


def retry_candidate(row):
    if not isinstance(row, dict):
        return False

    status = pr.clean(row.get("status")).lower()
    last_status = pr.clean(row.get("last_fetch_status")).lower()

    if status in RETRY_STATUSES:
        return True
    if last_status in ("fetch_error", "fetch_or_parse_error", "rate_not_found"):
        return True
    if row.get("stale") is True or row.get("retained_last_good") is True:
        return True
    if row.get("fetch_error"):
        return True

    return False


def collect_kind(bank, bank_cfg, kind, disclosure_banks):
    cfg = bank_cfg[kind.lower()]

    if bank == "한국투자":
        result = pr.get_koreainvest_official(bank, bank_cfg)
        item = result.get(kind.upper())
        if not isinstance(item, dict):
            item = pr.blank(bank, kind.lower(), cfg, "fetch_or_parse_error")

    elif bank in ("웰컴", "웰컴저축은행"):
        item = (
            pr.welcome_isa(bank, "isa", cfg)
            if kind == "ISA"
            else pr.welcome_irp(bank, "irp", cfg)
        )

    elif bank == "OK":
        item = (
            pr.ok_isa(bank, "isa", cfg)
            if kind == "ISA"
            else pr.ok_irp(bank, "irp", cfg)
        )

    elif bank == "DB":
        if kind == "ISA":
            item = pr.db_isa_official(bank, "isa", cfg)
        else:
            item = pr.one(bank, "irp", cfg)
            item = pr.merge_irp_disclosure(bank, item, disclosure_banks)

    else:
        item = pr.one(bank, kind.lower(), cfg)
        if kind == "IRP":
            item = pr.merge_irp_disclosure(bank, item, disclosure_banks)

    item = pr.enrich_disclosure_date_v53(item)

    if kind == "IRP":
        item = pr.apply_irp_latest_month_metadata(item)

    if bank == "한국투자":
        item["disclosure_date"] = None
        item["disclosure_date_source"] = "not_collected"
        item.pop("disclosure_date_url", None)

    return item


def clean_retained_note(item):
    if not isinstance(item, dict):
        return item
    note = pr.clean(item.get("note"))
    marker = "이번 공식소스 수집 실패로 직전 정상금리 유지"
    if marker in note:
        parts = [part.strip() for part in note.split("|") if part.strip()]
        seen_marker = False
        unique = []
        for part in parts:
            if marker in part:
                if seen_marker:
                    continue
                seen_marker = True
                unique.append(marker)
            else:
                unique.append(part)
        item["note"] = " | ".join(unique)
    return item


def main():
    source_map = load(MAP, {})
    banks_cfg = source_map.get("banks", {}) if isinstance(source_map, dict) else {}

    isa_rows = load(ISA, [])
    irp_rows = load(IRP, [])
    previous_isa = by_bank(isa_rows)
    previous_irp = by_bank(irp_rows)
    disclosure_banks = pr.load_irp_disclosure()

    retry_banks = []
    result_isa = []
    result_irp = []
    now_text = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")

    # Fresh process normally starts with empty caches. Reset explicitly so the
    # 06:30 pass never reuses a value created by an import-time side effect.
    if hasattr(pr, "_KOREAINVEST_CACHE"):
        pr._KOREAINVEST_CACHE = None
    if hasattr(pr, "_OK_CACHE"):
        pr._OK_CACHE = None

    print("=" * 72)
    print("SBRate ISA / IRP 06:30 targeted retry")
    print("=" * 72)

    for bank, bank_cfg in banks_cfg.items():
        old_isa = previous_isa.get(bank)
        old_irp = previous_irp.get(bank)
        retry_isa = retry_candidate(old_isa)
        retry_irp = retry_candidate(old_irp)

        new_isa = old_isa
        new_irp = old_irp

        if retry_isa or retry_irp:
            retry_banks.append(bank)
            print(f"[{bank}] retry ISA={retry_isa} IRP={retry_irp}")

        # 한국투자는 ISA/IRP를 같은 브라우저 collector cache로 묶어 쓰므로
        # 둘 중 하나라도 실패했으면 한 번만 수집하고 필요한 결과만 반영한다.
        if bank == "한국투자" and (retry_isa or retry_irp):
            pr._KOREAINVEST_CACHE = None

        if retry_isa:
            fresh = collect_kind(bank, bank_cfg, "ISA", disclosure_banks)
            fresh = pr.retain_last_known_good_on_fetch_error(fresh, old_isa)
            fresh = clean_retained_note(fresh)
            fresh["retry_attempt_at"] = now_text
            fresh["retry_phase"] = "06:30_second_check"
            new_isa = fresh

        if retry_irp:
            fresh = collect_kind(bank, bank_cfg, "IRP", disclosure_banks)
            fresh = pr.retain_last_known_good_on_fetch_error(fresh, old_irp)
            fresh = clean_retained_note(fresh)
            fresh["retry_attempt_at"] = now_text
            fresh["retry_phase"] = "06:30_second_check"
            new_irp = fresh

        if isinstance(new_isa, dict):
            result_isa.append(new_isa)
        if isinstance(new_irp, dict):
            result_irp.append(new_irp)

    if result_isa:
        save(ISA, result_isa)
    if result_irp:
        save(IRP, result_irp)

    print("retry banks:", ", ".join(retry_banks) if retry_banks else "none")
    print("ISA saved:", ISA)
    print("IRP saved:", IRP)
    print("=" * 72)


if __name__ == "__main__":
    main()
