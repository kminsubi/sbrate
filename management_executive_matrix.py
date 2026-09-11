from __future__ import annotations

import re
import sys
from typing import Any

import management_intelligence as mi
import management_report as mr


PEERS = (
    ("woori", "우리금융", ("우리금융",)),
    ("shinhan", "신한", ("신한",)),
    ("hana", "하나", ("하나",)),
    ("kb", "KB", ("kb", "케이비", "케이비저축은행")),
)

GROUPS = (
    {
        "category": "규모·여신",
        "metrics": (
            ("total_assets", "총자산", "억원", "higher", "basic"),
            ("total_loans", "총대출", "억원", "higher", "basic"),
            ("corporate_loans", "기업자금대출", "억원", "higher", "basic"),
            ("household_loans", "가계자금대출", "억원", "higher", "basic"),
        ),
    },
    {
        "category": "수신·조달",
        "metrics": (
            ("deposits", "총예수금", "억원", "higher", "funding"),
            ("time_deposits", "정기예금", "억원", "higher", "funding"),
            ("time_deposit_mix", "정기예금 비중", "%", "neutral", "funding"),
            ("simple_loan_deposit_ratio", "단순 예대율", "%", "neutral", "funding"),
            ("deposit_interest_expense", "예수금 이자비용", "억원", "lower", "funding"),
            ("time_deposit_interest_expense", "정기예금 이자비용", "억원", "lower", "funding"),
        ),
    },
    {
        "category": "수익성",
        "metrics": (
            ("operating_profit", "영업이익", "억원", "higher", "profitability"),
            ("net_income", "당기순이익", "억원", "higher", "profitability"),
            ("net_interest_income", "이자 순수익", "억원", "higher", "profitability"),
            ("interest_income", "이자수익", "억원", "higher", "profitability"),
            ("loan_interest_income", "대출채권 이자수익", "억원", "higher", "profitability"),
            ("interest_expense", "이자비용", "억원", "lower", "profitability"),
        ),
    },
    {
        "category": "건전성",
        "metrics": (
            ("bis_ratio", "BIS비율", "%", "higher", "soundness"),
            ("liquidity_ratio", "유동성비율", "%", "higher", "soundness"),
            ("delinquency_ratio", "연체율", "%", "lower", "soundness"),
            ("npl_ratio_effective", "고정이하여신비율", "%", "lower", "soundness"),
            ("npl_coverage_ratio", "NPL 충당금커버리지", "%", "higher", "soundness"),
            ("allowance_balance", "대손충당금 적립잔액", "억원", "higher", "soundness"),
        ),
    },
)


def _norm(value: Any) -> str:
    text = str(value or "").strip().lower()
    for token in ("(주)", "㈜", "주식회사", "저축은행", "은행", " ", "-", "_"):
        text = text.replace(token, "")
    aliases = {"국민": "케이비", "kb": "케이비"}
    return aliases.get(text, text)


def _peer_id(bank: Any) -> str | None:
    value = _norm(bank)
    for peer_id, _, aliases in PEERS:
        if any(value == _norm(alias) for alias in aliases):
            return peer_id
    return None


def _number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except Exception:
        return None


def _quarter_parts(value: Any) -> tuple[int, int] | None:
    match = re.fullmatch(r"(\d{4})Q([1-4])", str(value or ""))
    return (int(match.group(1)), int(match.group(2))) if match else None


def _previous_year_end(value: Any) -> str | None:
    parts = _quarter_parts(value)
    return f"{parts[0] - 1}Q4" if parts else None


def _row_map(rows: Any) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        peer_id = _peer_id(row.get("bank"))
        if peer_id:
            result[peer_id] = row
    return result


def _metric_from_intelligence(
    row: dict[str, Any],
    key: str,
    *,
    profitability: bool = False,
) -> dict[str, Any]:
    metric = ((row or {}).get("metrics") or {}).get(key) or {}
    base = _number(metric.get("base"))
    if profitability:
        compare = _number(metric.get("yoy_compare"))
        delta = _number(metric.get("yoy_delta"))
        basis = "전년동기比"
    else:
        compare = _number(metric.get("compare"))
        delta = _number(metric.get("delta"))
        basis = "전분기比"
    return {
        "base": base,
        "compare": compare,
        "delta": delta,
        "compare_basis": basis,
        "comparable": metric.get("comparable", True),
        "derived": bool(metric.get("derived")),
    }


def _metric_from_basic(
    current: dict[str, Any],
    compare: dict[str, Any],
    key: str,
) -> dict[str, Any]:
    base = _number((current or {}).get(key))
    old = _number((compare or {}).get(key))
    return {
        "base": base,
        "compare": old,
        "delta": base - old if base is not None and old is not None else None,
        "compare_basis": "전년말比",
        "comparable": True,
        "derived": False,
    }


def _rank_map(
    peer_metrics: dict[str, dict[str, dict[str, Any]]],
    key: str,
    direction: str,
) -> dict[str, int]:
    if direction == "neutral":
        return {}
    values = {
        peer_id: _number((metrics.get(key) or {}).get("base"))
        for peer_id, metrics in peer_metrics.items()
    }
    values = {peer_id: value for peer_id, value in values.items() if value is not None}
    result: dict[str, int] = {}
    for peer_id, value in values.items():
        if direction == "lower":
            better = sum(1 for other in values.values() if other < value)
        else:
            better = sum(1 for other in values.values() if other > value)
        result[peer_id] = better + 1
    return result


def _insights(rows: list[dict[str, Any]]) -> dict[str, Any]:
    strengths: list[str] = []
    watchpoints: list[str] = []
    for row in rows:
        rank = ((row.get("ranks") or {}).get("woori"))
        available = int(row.get("available_peer_count") or 0)
        if rank == 1 and available >= 3:
            strengths.append(f"{row['label']} 4대금융 1위")
        elif rank == available and available >= 3:
            watchpoints.append(f"{row['label']} 4대금융 {rank}위")

    summary_parts = []
    if strengths:
        summary_parts.append("강점: " + ", ".join(strengths[:3]))
    if watchpoints:
        summary_parts.append("점검: " + ", ".join(watchpoints[:3]))
    if not summary_parts:
        summary_parts.append("비교 가능한 지표가 충분히 쌓이면 강점·열위가 자동 표시됩니다.")

    return {
        "summary": " / ".join(summary_parts),
        "strengths": strengths[:5],
        "watchpoints": watchpoints[:5],
    }


def build_executive_matrix(base: str | None = None) -> dict[str, Any]:
    store = mr._load_store()
    quarters = store.get("quarters") if isinstance(store.get("quarters"), dict) else {}
    available = sorted(quarters.keys(), key=mr._quarter_sort_key, reverse=True)
    if not available:
        return {"ok": False, "ready": False, "error": "FISIS 경영현황 분기 데이터가 없습니다."}

    base = base if base in quarters else available[0]
    base_meta = quarters.get(base) or {}
    base_rows = _row_map(base_meta.get("banks") or [])

    previous_year_end = _previous_year_end(base)
    old_meta = quarters.get(previous_year_end) if previous_year_end in quarters else {}
    old_rows = _row_map((old_meta or {}).get("banks") or [])

    funding = mi.build_intelligence("funding", base=base)
    soundness = mi.build_intelligence("soundness", base=base)
    profitability = mi.build_intelligence("profitability", base=base)

    section_maps = {
        "funding": _row_map(funding.get("rows") or []),
        "soundness": _row_map(soundness.get("rows") or []),
        "profitability": _row_map(profitability.get("rows") or []),
    }

    peer_metrics: dict[str, dict[str, dict[str, Any]]] = {
        peer_id: {} for peer_id, _, _ in PEERS
    }
    metric_meta: dict[str, dict[str, Any]] = {}

    for group in GROUPS:
        for key, label, unit, direction, source in group["metrics"]:
            metric_meta[key] = {
                "key": key,
                "label": label,
                "unit": unit,
                "direction": direction,
                "category": group["category"],
                "source": source,
            }
            for peer_id, _, _ in PEERS:
                if source == "basic":
                    pack = _metric_from_basic(
                        base_rows.get(peer_id) or {},
                        old_rows.get(peer_id) or {},
                        key,
                    )
                else:
                    pack = _metric_from_intelligence(
                        section_maps[source].get(peer_id) or {},
                        key,
                        profitability=(source == "profitability"),
                    )
                peer_metrics[peer_id][key] = pack

    rank_maps = {
        key: _rank_map(peer_metrics, key, meta["direction"])
        for key, meta in metric_meta.items()
    }

    rows: list[dict[str, Any]] = []
    for group in GROUPS:
        for key, label, unit, direction, source in group["metrics"]:
            values = {
                peer_id: peer_metrics[peer_id][key]
                for peer_id, _, _ in PEERS
            }
            ranks = rank_maps.get(key) or {}
            rows.append({
                "category": group["category"],
                "key": key,
                "label": label,
                "unit": unit,
                "direction": direction,
                "values": values,
                "ranks": ranks,
                "available_peer_count": sum(
                    1 for item in values.values() if item.get("base") is not None
                ),
            })

    peers = [
        {
            "id": peer_id,
            "label": label,
            "bank": (
                (base_rows.get(peer_id) or {}).get("bank")
                or (section_maps["funding"].get(peer_id) or {}).get("bank")
                or label
            ),
        }
        for peer_id, label, _ in PEERS
    ]

    readiness = {
        "funding": bool(funding.get("ready")),
        "soundness": bool(soundness.get("ready")),
        "profitability": bool(profitability.get("ready")),
    }
    coverage_values = sum(
        1
        for row in rows
        for item in (row.get("values") or {}).values()
        if item.get("base") is not None
    )
    coverage_total = len(rows) * len(PEERS)

    return {
        "ok": True,
        "ready": all(readiness.values()),
        "view": "executive_peer_matrix_v1",
        "base": base,
        "base_label": base_meta.get("label") or mr._quarter_label(base),
        "as_of": base_meta.get("as_of"),
        "updated_at": (
            funding.get("updated_at")
            or soundness.get("updated_at")
            or profitability.get("updated_at")
            or store.get("updated_at")
        ),
        "source": "금융감독원 금융통계정보시스템(FISIS)",
        "peer_scope": "4대 금융지주 계열 저축은행",
        "peers": peers,
        "rows": rows,
        "insights": _insights(rows),
        "coverage": {
            "value_count": coverage_values,
            "total_cells": coverage_total,
            "ratio": round(coverage_values / coverage_total, 4) if coverage_total else 0,
            "section_ready": readiness,
        },
        "notes": {
            "amount_unit": "억원",
            "profitability_basis": "손익 지표는 공시 누적값이며 전년동기 비교를 우선합니다.",
            "funding_soundness_basis": "수신·조달·건전성 증감은 전분기 비교를 우선합니다.",
            "size_basis": "규모·여신 증감은 전년말 비교를 우선합니다.",
            "neutral_metrics": "정기예금 비중·단순 예대율은 단순히 높거나 낮다고 우열 판정하지 않습니다.",
            "roa_roe": (profitability.get("notes") or {}).get("roa_roe_basis"),
        },
        "phase2_pending": [
            "대출이자수익률",
            "대출채권 매각손익",
            "세부 조달비용률",
            "세부 대손비용률",
        ],
        "phase2_verified_source_map": {
            "loan_interest_income": {
                "table": "SE014",
                "account": "A13",
                "label": "이자수익_대출채권이자",
                "status": "ACTIVE_IN_INTELLIGENCE_STORE",
            },
            "loan_receivable_trading_gain": {
                "table": "SE006",
                "account": "A40",
                "label": "대출채권관련수익_대출채권매매이익",
                "status": "SOURCE_VERIFIED_COLLECTOR_PENDING",
            },
            "loan_receivable_trading_loss": {
                "table": "SE006",
                "account": "B530",
                "label": "대출채권관련손실_대출채권매매손실",
                "status": "SOURCE_VERIFIED_COLLECTOR_PENDING",
            },
            "borrowing_interest_expense": {
                "table": "SE014",
                "account": "A22",
                "label": "이자비용_차입금이자",
                "status": "SOURCE_VERIFIED_COLLECTOR_PENDING",
            },
            "bond_interest_expense": {
                "table": "SE014",
                "account": "A23",
                "label": "이자비용_사채이자",
                "status": "SOURCE_VERIFIED_COLLECTOR_PENDING",
            },
        },
        "phase2_policy": (
            "FISIS 원천 테이블·계정코드가 검증된 항목만 추가합니다. "
            "대출이자수익률은 검증된 대출평잔 분모가 확보되기 전까지 산출하지 않습니다."
        ),
    }


def install_management_executive_matrix() -> bool:
    app_module = sys.modules.get("app") or sys.modules.get("__main__")
    if app_module is None or not hasattr(app_module, "app"):
        return False
    if getattr(app_module, "_management_executive_matrix_installed", False):
        return True

    flask_app = app_module.app
    from flask import jsonify, request

    @flask_app.get("/api/management-executive-matrix")
    def management_executive_matrix_api():
        try:
            payload = build_executive_matrix(
                base=str(request.args.get("base") or "").strip() or None
            )
            return jsonify(payload), (200 if payload.get("ok") else 404)
        except Exception as exc:
            return jsonify({
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
            }), 500

    app_module._management_executive_matrix_installed = True
    print("Management executive 4-peer matrix API installed")
    return True
