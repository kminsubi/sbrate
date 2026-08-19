# SBRate Rate Simulation V6
# - Adds selectable market basis: bank-best vs all-products
# - Reuses the proven V2 product/period loaders without mutating source data
import sys
from copy import deepcopy

import rate_simulator_v2 as base


def _appmod():
    for name in ("app", "__main__"):
        module = sys.modules.get(name)
        if module is not None and hasattr(module, "app"):
            return module
    return None


def _basis(value):
    value = str(value or "bank_best").strip().lower()
    return value if value in ("bank_best", "all_products") else "bank_best"


def _basis_label(value):
    return "전체상품 기준" if value == "all_products" else "은행별 최고금리 기준"


def _sorted_products(rows):
    return sorted(
        [deepcopy(row) for row in (rows or []) if isinstance(row, dict)],
        key=lambda row: float(row.get("rate") or 0),
        reverse=True,
    )


def _target_row(m, row, selected_product):
    return (
        base._woori(m, row.get("bank"))
        and str(row.get("product") or "") == str(selected_product or "")
    )


def _financial_group_keys(m):
    aliases = [
        "우리금융저축은행",
        "신한저축은행",
        "하나저축은행",
        "KB저축은행",
    ]
    configured = getattr(m, "FINANCIAL_BANKS", None)
    if isinstance(configured, (list, tuple)) and configured:
        aliases = list(configured)
    return {base._norm(m, name) for name in aliases if name}


def _all_product_snapshot(m, rows, selected_product):
    ranked = _sorted_products(rows)
    if not ranked:
        return None

    idx = next(
        (i for i, row in enumerate(ranked) if _target_row(m, row, selected_product)),
        None,
    )
    if idx is None:
        return None

    selected = ranked[idx]
    selected_rate = float(selected.get("rate") or 0)
    rates = [float(row.get("rate") or 0) for row in ranked if float(row.get("rate") or 0) > 0]
    if not rates:
        return None

    group_keys = _financial_group_keys(m)
    group_rows = [
        row for row in ranked
        if base._norm(m, row.get("bank")) in group_keys
    ]
    group_idx = next(
        (i for i, row in enumerate(group_rows) if _target_row(m, row, selected_product)),
        None,
    )

    above = ranked[idx - 1] if idx > 0 else None
    below = ranked[idx + 1] if idx + 1 < len(ranked) else None

    return {
        "rate": selected_rate,
        "rank": idx + 1,
        "total": len(ranked),
        "top_rate": max(rates),
        "average_rate": sum(rates) / len(rates),
        "gap_top": selected_rate - max(rates),
        "gap_average": selected_rate - (sum(rates) / len(rates)),
        "financial_rank": group_idx + 1 if group_idx is not None else None,
        "financial_total": len(group_rows),
        "product": selected.get("product") or "-",
        "above": deepcopy(above) if above else None,
        "below": deepcopy(below) if below else None,
    }


def _thresholds(m, rows, selected_product, market_basis):
    if market_basis == "bank_best":
        pool = [
            row for row in base._bank_best(m, rows)
            if not base._woori(m, row.get("bank"))
        ]
    else:
        # For an all-product competition line, exclude only the selected Woori
        # product itself. Other Woori products remain part of the actual market pool.
        pool = [
            row for row in _sorted_products(rows)
            if not _target_row(m, row, selected_product)
        ]

    pool = sorted(pool, key=lambda row: float(row.get("rate") or 0), reverse=True)

    def cut(n):
        return float(pool[n - 1].get("rate")) if len(pool) >= n else None

    return {"top5": cut(5), "top10": cut(10)}


def simulate_v6(
    m,
    category="deposit",
    period="12",
    target_rate=None,
    product=None,
    market_basis="bank_best",
):
    category = str(category or "deposit").lower()
    category = category if category in ("deposit", "isa", "irp") else "deposit"
    period = base._period(category, period)
    market_basis = _basis(market_basis)

    rows = base._rows(m, category, period)
    products = base._products(m, rows)
    if not rows or not products:
        return {"ok": False, "message": "우리금융 금리 데이터를 확인할 수 없습니다."}

    current_bank = base._snapshot(m, rows)
    if not current_bank:
        return {"ok": False, "message": "우리금융 시장 데이터를 확인할 수 없습니다."}

    names = [item["name"] for item in products]
    selected_product = (
        product if product in names
        else current_bank.get("product") if current_bank.get("product") in names
        else names[0]
    )
    selected_rate = next(item["rate"] for item in products if item["name"] == selected_product)

    try:
        target = float(target_rate) if target_rate not in (None, "") else float(selected_rate)
    except Exception:
        target = float(selected_rate)
    target = round(max(0.01, min(10.0, target)), 2)

    simulated_rows = deepcopy(rows)
    for row in simulated_rows:
        if _target_row(m, row, selected_product):
            row["rate"] = target

    simulated_bank = base._snapshot(m, simulated_rows)
    if not simulated_bank:
        return {"ok": False, "message": "시뮬레이션 결과를 계산하지 못했습니다."}

    if market_basis == "all_products":
        current = _all_product_snapshot(m, rows, selected_product)
        simulated = _all_product_snapshot(m, simulated_rows, selected_product)
    else:
        current = current_bank
        simulated = simulated_bank

    if not current or not simulated:
        return {"ok": False, "message": "선택상품의 시장 위치를 계산하지 못했습니다."}

    thresholds = _thresholds(m, rows, selected_product, market_basis)

    return {
        "ok": True,
        "category": category,
        "category_label": base._label(category),
        "period": period,
        "period_options": (
            ["1", "3", "6", "12", "24", "36"]
            if category == "deposit"
            else ["3", "6", "12", "24", "36"]
        ),
        "source": base._source(category),
        "product_options": products,
        "selected_product": selected_product,
        "selected_product_current_rate": selected_rate,
        "target_rate": target,
        "market_basis": market_basis,
        "market_basis_label": _basis_label(market_basis),
        "market_basis_options": [
            {"value": "bank_best", "label": "은행별 최고금리"},
            {"value": "all_products", "label": "전체상품"},
        ],
        "current": current,
        "simulated": simulated,
        "bank_best": {
            "current_rate": current_bank.get("rate"),
            "simulated_rate": simulated_bank.get("rate"),
            "current_product": current_bank.get("product"),
            "simulated_product": simulated_bank.get("product"),
            "product_changed": current_bank.get("product") != simulated_bank.get("product"),
        },
        "thresholds": thresholds,
    }


def install_rate_simulation_v6():
    m = _appmod()
    if m is None:
        return False

    app = m.app
    if "rate_simulation_v6_api" in app.view_functions:
        return True

    from flask import jsonify, request

    def endpoint():
        q = request.get_json(silent=True) or {} if request.method == "POST" else request.args
        result = simulate_v6(
            m,
            q.get("category", "deposit"),
            q.get("period", "12"),
            q.get("target_rate"),
            q.get("product"),
            q.get("market_basis", "bank_best"),
        )
        return jsonify(result), (200 if result.get("ok") else 404)

    app.add_url_rule(
        "/api/rate-simulation-v6",
        "rate_simulation_v6_api",
        endpoint,
        methods=["GET", "POST"],
    )
    print("Rate Simulation V6 API installed")
    return True
