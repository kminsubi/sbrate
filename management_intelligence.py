import json
import re
import sys
from datetime import date, datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
HISTORY_DIR = DATA_DIR / "history"
WOORI_NAMES = {"우리금융", "우리금융저축은행"}

SECTION_FIELDS = {
    "funding": [
        ("deposits", "총예수금", "억원", "higher"),
        ("time_deposits", "정기예금", "억원", "higher"),
        ("personal_deposits", "개인 예수금", "억원", "higher"),
        ("corporate_deposits", "기업 예수금", "억원", "higher"),
        ("sole_prop_deposits", "개인사업자 예수금", "억원", "higher"),
        ("time_deposit_mix", "정기예금 비중", "%", "neutral"),
        ("deposit_market_share", "예수금 시장점유율", "%", "higher"),
        ("simple_loan_deposit_ratio", "단순 예대율", "%", "neutral"),
        ("deposit_interest_expense", "예수금 이자비용", "억원", "lower"),
        ("time_deposit_interest_expense", "정기예금 이자비용", "억원", "lower"),
    ],
    "soundness": [
        ("bis_ratio", "BIS비율", "%", "higher"),
        ("liquidity_ratio", "유동성비율", "%", "higher"),
        ("delinquency_ratio", "연체율", "%", "lower"),
        ("npl_ratio_effective", "고정이하여신비율", "%", "lower"),
        ("fixed_below_loans", "고정이하여신", "억원", "lower"),
        ("allowance_balance", "대손충당금 적립잔액", "억원", "higher"),
        ("npl_coverage_ratio", "NPL 충당금커버리지", "%", "higher"),
        ("real_estate_industry_loans", "부동산업 기업대출", "억원", "lower"),
        ("real_estate_corp_share", "부동산업 기업대출 비중", "%", "lower"),
    ],
    "profitability": [
        ("net_income", "당기순이익", "억원", "higher"),
        ("operating_profit", "영업이익", "억원", "higher"),
        ("roa", "ROA", "%", "higher"),
        ("roe", "ROE", "%", "higher"),
        ("net_interest_income", "이자 순수익", "억원", "higher"),
        ("interest_income", "이자수익", "억원", "higher"),
        ("interest_expense", "이자비용", "억원", "lower"),
        ("deposit_interest_expense", "예수금 이자비용", "억원", "lower"),
        ("time_deposit_interest_expense", "정기예금 이자비용", "억원", "lower"),
    ],
}


def _normalize_bank(value):
    text = str(value or "").strip().lower()
    for token in ("(주)", "㈜", "주식회사", "저축은행", "은행", " ", "-", "_"):
        text = text.replace(token, "")
    return text


def _number(value):
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace(",", ""))
    except Exception:
        return None


def _round(value, digits=2):
    value = _number(value)
    return None if value is None else round(value, digits)


def _quarter_rank(key):
    match = re.fullmatch(r"(\d{4})Q([1-4])", str(key or ""))
    if not match:
        return -1
    return int(match.group(1)) * 4 + int(match.group(2))


def _previous_quarter(key):
    match = re.fullmatch(r"(\d{4})Q([1-4])", str(key or ""))
    if not match:
        return None
    year = int(match.group(1))
    quarter = int(match.group(2))
    if quarter == 1:
        return f"{year - 1}Q4"
    return f"{year}Q{quarter - 1}"


def _yoy_quarter(key):
    match = re.fullmatch(r"(\d{4})Q([1-4])", str(key or ""))
    if not match:
        return None
    return f"{int(match.group(1)) - 1}Q{match.group(2)}"


def _quarter_bounds(key):
    match = re.fullmatch(r"(\d{4})Q([1-4])", str(key or ""))
    if not match:
        return None, None
    year = int(match.group(1))
    quarter = int(match.group(2))
    starts = {1: (1, 1), 2: (4, 1), 3: (7, 1), 4: (10, 1)}
    ends = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}
    sm, sd = starts[quarter]
    em, ed = ends[quarter]
    return date(year, sm, sd), date(year, em, ed)


def _load_json(path, default=None):
    try:
        with Path(path).open("r", encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return default


def _best_12m_by_bank(rows):
    best = {}
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        bank = str(row.get("bank") or "").strip()
        value = _number(row.get("top_12m"))
        if not bank or value is None:
            continue
        norm = _normalize_bank(bank)
        existing = best.get(norm)
        if existing is None or value > existing["rate"]:
            best[norm] = {
                "bank": bank,
                "product": str(row.get("product") or "").strip(),
                "rate": value,
            }
    ranked = sorted(best.values(), key=lambda x: (-x["rate"], x["bank"]))
    rank_map = {_normalize_bank(row["bank"]): idx for idx, row in enumerate(ranked, 1)}
    for norm, row in best.items():
        row["rank"] = rank_map.get(norm)
    return best, ranked


def _current_rate_market():
    rows = _load_json(DATA_DIR / "latest_rates.json", [])
    info = _load_json(DATA_DIR / "update_info.json", {}) or {}
    best, ranked = _best_12m_by_bank(rows)
    woori = best.get(_normalize_bank("우리금융")) or best.get(_normalize_bank("우리금융저축은행"))
    values = [x["rate"] for x in ranked]
    return {
        "basis": "현재 정기예금 12개월 은행별 최고금리",
        "updated_at": info.get("last_update"),
        "bank_count": len(ranked),
        "market_average": round(sum(values) / len(values), 4) if values else None,
        "market_max": max(values) if values else None,
        "woori": woori,
    }


def _rate_history_for_quarter(quarter):
    start, end = _quarter_bounds(quarter)
    if not start or not end or not HISTORY_DIR.exists():
        return {"available": False, "status": "no_history", "quarter": quarter, "snapshot_count": 0}

    snapshots = []
    for path in sorted(HISTORY_DIR.glob("*.json")):
        try:
            snap_date = datetime.strptime(path.stem, "%Y-%m-%d").date()
        except Exception:
            continue
        if snap_date < start or snap_date > end:
            continue
        payload = _load_json(path, {}) or {}
        rows = payload.get("deposit") if isinstance(payload, dict) else None
        best, ranked = _best_12m_by_bank(rows)
        woori = best.get(_normalize_bank("우리금융")) or best.get(_normalize_bank("우리금융저축은행"))
        if not woori:
            continue
        values = [x["rate"] for x in ranked]
        snapshots.append({
            "date": snap_date.isoformat(),
            "woori_rate": woori.get("rate"),
            "woori_rank": woori.get("rank"),
            "market_average": round(sum(values) / len(values), 4) if values else None,
            "market_max": max(values) if values else None,
        })

    if not snapshots:
        return {
            "available": False,
            "status": "no_history",
            "quarter": quarter,
            "snapshot_count": 0,
            "note": "SBRate 일별 금리 이력이 해당 분기에 존재하지 않습니다.",
        }

    rates = [x["woori_rate"] for x in snapshots if x.get("woori_rate") is not None]
    first = snapshots[0]
    last = snapshots[-1]
    first_date = datetime.strptime(first["date"], "%Y-%m-%d").date()
    last_date = datetime.strptime(last["date"], "%Y-%m-%d").date()
    full = (first_date - start).days <= 3 and (end - last_date).days <= 3
    return {
        "available": len(rates) > 0,
        "status": "full" if full else "partial",
        "quarter": quarter,
        "snapshot_count": len(snapshots),
        "first_date": first["date"],
        "last_date": last["date"],
        "first_rate": first.get("woori_rate"),
        "last_rate": last.get("woori_rate"),
        "average_rate": round(sum(rates) / len(rates), 4) if rates else None,
        "max_rate": max(rates) if rates else None,
        "min_rate": min(rates) if rates else None,
        "rate_change": _round((last.get("woori_rate") or 0) - (first.get("woori_rate") or 0), 4)
            if first.get("woori_rate") is not None and last.get("woori_rate") is not None else None,
        "first_rank": first.get("woori_rank"),
        "last_rank": last.get("woori_rank"),
        "note": None if full else "분기 전체가 아닌 보유 중인 SBRate 일별 금리 이력 구간만 반영합니다.",
    }


def _derived_row(row, total_deposits=None):
    source = dict(row or {})
    deposits = _number(source.get("deposits"))
    time_deposits = _number(source.get("time_deposits"))
    total_loans = _number(source.get("total_loans"))
    industry_corp = _number(source.get("industry_corporate_loans"))
    real_estate = _number(source.get("real_estate_industry_loans"))
    source["npl_ratio_effective"] = (
        source.get("npl_ratio_detail")
        if source.get("npl_ratio_detail") is not None
        else source.get("npl_ratio")
    )
    source["time_deposit_mix"] = _round(time_deposits / deposits * 100, 4) if deposits not in (None, 0) and time_deposits is not None else None
    source["simple_loan_deposit_ratio"] = _round(total_loans / deposits * 100, 4) if deposits not in (None, 0) and total_loans is not None else None
    source["deposit_market_share"] = _round(deposits / total_deposits * 100, 4) if deposits is not None and total_deposits not in (None, 0) else None
    source["real_estate_corp_share"] = _round(real_estate / industry_corp * 100, 4) if real_estate is not None and industry_corp not in (None, 0) else None
    return source


def _bank_map(quarter_meta):
    rows = quarter_meta.get("banks") if isinstance(quarter_meta, dict) else []
    return {
        str(row.get("finance_cd") or _normalize_bank(row.get("bank"))): row
        for row in rows if isinstance(row, dict)
    }


def _fields(section):
    return [
        {"key": key, "label": label, "unit": unit, "direction": direction}
        for key, label, unit, direction in SECTION_FIELDS[section]
    ]


def _metric_pack(base_row, compare_row, yoy_row, key):
    base = _number((base_row or {}).get(key))
    compare = _number((compare_row or {}).get(key))
    yoy = _number((yoy_row or {}).get(key))
    return {
        "base": _round(base, 4),
        "compare": _round(compare, 4),
        "delta": _round(base - compare, 4) if base is not None and compare is not None else None,
        "yoy_compare": _round(yoy, 4),
        "yoy_delta": _round(base - yoy, 4) if base is not None and yoy is not None else None,
    }


def build_intelligence(section="funding", base=None, compare=None):
    import fisis_management as fm

    section = str(section or "funding").strip().lower()
    if section not in SECTION_FIELDS:
        raise ValueError(f"지원하지 않는 분석 구분입니다: {section}")

    store = fm.get_management_store(trigger_refresh=True) or {}
    quarters = store.get("quarters") if isinstance(store.get("quarters"), dict) else {}
    ordered = sorted(quarters.keys(), key=_quarter_rank, reverse=True)
    if not ordered:
        return {"ok": False, "ready": False, "error": "FISIS 분기 데이터가 없습니다."}

    base = base if base in quarters else ordered[0]
    compare = compare if compare in quarters else _previous_quarter(base)
    if compare not in quarters:
        compare = ordered[1] if len(ordered) > 1 else None
    yoy_key = _yoy_quarter(base)
    yoy_meta = quarters.get(yoy_key) if yoy_key in quarters else {}

    base_meta = quarters.get(base) or {}
    compare_meta = quarters.get(compare) or {}
    base_rows_raw = [x for x in (base_meta.get("banks") or []) if isinstance(x, dict)]
    compare_map_raw = _bank_map(compare_meta)
    yoy_map_raw = _bank_map(yoy_meta)
    total_deposits = sum(_number(x.get("deposits")) or 0 for x in base_rows_raw)
    compare_total_deposits = sum(_number(x.get("deposits")) or 0 for x in (compare_meta.get("banks") or []) if isinstance(x, dict))
    yoy_total_deposits = sum(_number(x.get("deposits")) or 0 for x in (yoy_meta.get("banks") or []) if isinstance(x, dict))

    base_rows = []
    for raw in base_rows_raw:
        key_id = str(raw.get("finance_cd") or _normalize_bank(raw.get("bank")))
        base_row = _derived_row(raw, total_deposits)
        compare_row = _derived_row(compare_map_raw.get(key_id), compare_total_deposits) if compare_map_raw.get(key_id) else {}
        yoy_row = _derived_row(yoy_map_raw.get(key_id), yoy_total_deposits) if yoy_map_raw.get(key_id) else {}
        metrics = {field[0]: _metric_pack(base_row, compare_row, yoy_row, field[0]) for field in SECTION_FIELDS[section]}
        base_rows.append({
            "bank": base_row.get("bank"),
            "finance_cd": base_row.get("finance_cd"),
            "region": base_row.get("region"),
            "asset_rank": base_row.get("asset_rank"),
            "is_woori": _normalize_bank(base_row.get("bank")) == _normalize_bank("우리금융"),
            "metrics": metrics,
        })

    # Deposit rank is a useful neutral ranking for the funding section.
    if section == "funding":
        ranked = sorted(
            [x for x in base_rows if x["metrics"]["deposits"]["base"] is not None],
            key=lambda x: (-x["metrics"]["deposits"]["base"], str(x.get("bank") or "")),
        )
        for idx, item in enumerate(ranked, 1):
            item["section_rank"] = idx
        comp_ranked = sorted(
            [(k, _number(v.get("deposits"))) for k, v in compare_map_raw.items() if _number(v.get("deposits")) is not None],
            key=lambda x: (-x[1], x[0]),
        )
        comp_ranks = {key: idx for idx, (key, _) in enumerate(comp_ranked, 1)}
        for item in base_rows:
            key_id = str(item.get("finance_cd") or _normalize_bank(item.get("bank")))
            item["compare_section_rank"] = comp_ranks.get(key_id)
            if item.get("section_rank") is not None and item.get("compare_section_rank") is not None:
                item["section_rank_change"] = item["compare_section_rank"] - item["section_rank"]
    else:
        for item in base_rows:
            item["section_rank"] = item.get("asset_rank")

    woori = next((x for x in base_rows if x.get("is_woori")), None)
    current_market = _current_rate_market() if section == "funding" else None
    rate_history = _rate_history_for_quarter(base) if section == "funding" else None

    ready = int(store.get("intelligence_schema_version") or 0) >= 1
    if ready and woori:
        # Require the section's anchor metric as a second readiness guard.
        anchor = {"funding": "deposits", "soundness": "liquidity_ratio", "profitability": "roa"}[section]
        ready = woori.get("metrics", {}).get(anchor, {}).get("base") is not None

    return {
        "ok": True,
        "ready": ready,
        "section": section,
        "source_name": store.get("source_name"),
        "updated_at": store.get("updated_at"),
        "intelligence_schema_version": store.get("intelligence_schema_version"),
        "base": base,
        "base_label": base_meta.get("label") or base,
        "as_of": base_meta.get("as_of"),
        "compare": compare,
        "compare_label": (compare_meta or {}).get("label") or compare,
        "yoy_compare": yoy_key if yoy_key in quarters else None,
        "yoy_compare_label": (yoy_meta or {}).get("label") if yoy_key in quarters else None,
        "bank_count": len(base_rows),
        "fields": _fields(section),
        "woori": woori,
        "rows": base_rows,
        "current_market": current_market,
        "rate_history": rate_history,
        "notes": {
            "rate_basis": "현재 금리는 저축은행중앙회 정기예금 12개월 은행별 최고금리 기준입니다.",
            "fisis_basis": "FISIS 수치는 선택한 분기 말 기준이며 손익 지표는 공시 누적값입니다.",
            "loan_deposit_ratio": "단순 예대율은 총대출/총예수금으로 계산한 참고지표이며 규제상 예대율과 다를 수 있습니다.",
            "profitability_compare": "수익성 단일분기 해석은 전년동기 비교를 우선 사용합니다.",
        },
    }


def build_latest_insight():
    funding = build_intelligence("funding")
    soundness = build_intelligence("soundness")
    profitability = build_intelligence("profitability")
    ready = all(x.get("ready") for x in (funding, soundness, profitability))
    return {
        "ok": True,
        "ready": ready,
        "latest": funding.get("base"),
        "latest_label": funding.get("base_label"),
        "as_of": funding.get("as_of"),
        "updated_at": funding.get("updated_at"),
        "current_market": funding.get("current_market"),
        "funding": funding.get("woori"),
        "soundness": soundness.get("woori"),
        "profitability": profitability.get("woori"),
        "notes": funding.get("notes"),
    }


def install_management_intelligence():
    app_module = sys.modules.get("app") or sys.modules.get("__main__")
    if app_module is None or not hasattr(app_module, "app"):
        return False
    if getattr(app_module, "_management_intelligence_installed", False):
        return True

    flask_app = app_module.app
    from flask import jsonify, request

    @flask_app.get("/api/management-intelligence")
    def management_intelligence_api():
        try:
            return jsonify(build_intelligence(
                section=request.args.get("section") or "funding",
                base=request.args.get("base"),
                compare=request.args.get("compare"),
            ))
        except Exception as exc:
            return jsonify({"ok": False, "error": f"{type(exc).__name__}: {exc}"}), 500

    @flask_app.get("/api/management-intelligence/insight")
    def management_intelligence_insight_api():
        try:
            return jsonify(build_latest_insight())
        except Exception as exc:
            return jsonify({"ok": False, "error": f"{type(exc).__name__}: {exc}"}), 500

    app_module._management_intelligence_installed = True
    print("Management intelligence APIs installed")
    return True
