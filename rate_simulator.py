# ==========================================
# SBRate Woori Rate Simulator V1
# - PC draggable floating module
# - Mobile bottom sheet
# - Deposit / ISA / IRP simulation API
# - Telegram inline simulator menu
# - Simulation only: never mutates rate data
# ==========================================

import os
import sys
import threading
import time
from copy import deepcopy
from functools import wraps


SIMULATOR_CSS = "/static/css/rate_simulator.css?v=20260819v1"
SIMULATOR_JS = "/static/js/rate_simulator.js?v=20260819v1"


def _find_running_app_module():
    for name in ("app", "__main__"):
        module = sys.modules.get(name)
        if module is not None and hasattr(module, "app"):
            return module
    return None


def _safe_float(app_module, value):
    helper = getattr(app_module, "safe_float", None)
    if callable(helper):
        try:
            return helper(value)
        except Exception:
            pass

    if value in (None, "", "-"):
        return None

    try:
        return float(
            str(value)
            .replace(",", "")
            .replace("%p", "")
            .replace("%", "")
            .replace("+", "")
            .replace("▲", "-")
            .strip()
        )
    except Exception:
        return None


def _normalize_bank(app_module, value):
    helper = getattr(app_module, "normalize", None)
    if callable(helper):
        try:
            return str(helper(value) or "")
        except Exception:
            pass

    return (
        str(value or "")
        .replace("(주)", "")
        .replace("㈜", "")
        .replace("주식회사", "")
        .replace("저축은행", "")
        .replace("은행", "")
        .replace(" ", "")
        .replace("-", "")
        .replace("_", "")
        .lower()
    )


def _is_woori(app_module, bank):
    raw = str(bank or "")
    if "우리금융" in raw:
        return True

    target = _normalize_bank(
        app_module,
        "우리금융저축은행"
    )
    return _normalize_bank(app_module, raw) == target


def _category_label(category):
    return {
        "deposit": "정기예금",
        "isa": "ISA",
        "irp": "퇴직연금(IRP)",
    }.get(category, "정기예금")


def _source_label(category):
    return (
        "저축은행중앙회 비교공시"
        if category == "deposit"
        else "각 저축은행 홈페이지"
    )


def _valid_period(category, period):
    period = str(period or "12").strip()
    allowed = (
        ("1", "3", "6", "12", "24", "36")
        if category == "deposit"
        else ("3", "6", "12", "24", "36")
    )
    return period if period in allowed else "12"


def _aggregate_bank_best(app_module, rows):
    best = {}
    order = []

    for row in rows or []:
        if not isinstance(row, dict):
            continue

        bank = str(
            row.get("bank")
            or row.get("bank_name")
            or row.get("kor_co_nm")
            or ""
        ).strip()

        rate = _safe_float(
            app_module,
            row.get("rate")
            if row.get("rate") not in (None, "")
            else row.get("max_rate")
        )

        if not bank or rate is None or rate <= 0:
            continue

        key = _normalize_bank(app_module, bank)
        if not key:
            continue

        candidate = {
            "bank": bank,
            "rate": float(rate),
            "product": str(
                row.get("product")
                or row.get("product_name")
                or ""
            ).strip(),
            "disclosure_date": row.get("disclosure_date"),
        }

        if key not in best:
            order.append(key)
            best[key] = candidate
        elif float(rate) > float(best[key]["rate"]):
            best[key] = candidate

    return [best[key] for key in order]


def _market_rows(app_module, category, period):
    period = _valid_period(category, period)

    if category == "deposit":
        builder = getattr(app_module, "build_products", None)
        if not callable(builder):
            return []

        rows = builder(f"{period}개월") or []
        unique = getattr(app_module, "unique_products", None)
        if callable(unique):
            try:
                rows = unique(rows)
            except Exception:
                pass

        bank_best = getattr(app_module, "get_bank_best_rates", None)
        if callable(bank_best):
            try:
                result = bank_best(rows) or []
                aggregated = _aggregate_bank_best(
                    app_module,
                    result
                )
                if aggregated:
                    return aggregated
            except Exception:
                pass

        return _aggregate_bank_best(app_module, rows)

    file_path = (
        getattr(app_module, "ISA_DATA_FILE", "")
        if category == "isa"
        else getattr(app_module, "IRP_DATA_FILE", "")
    )

    builder = getattr(
        app_module,
        "build_pension_products",
        None
    )
    if not callable(builder) or not file_path:
        return []

    rows = builder(
        file_path,
        "ISA" if category == "isa" else "퇴직연금"
    ) or []

    period_builder = getattr(
        app_module,
        "pension_items_with_period",
        None
    )

    if callable(period_builder):
        try:
            rows = period_builder(rows, period) or []
        except Exception:
            rows = []
    else:
        key = f"{period}m"
        normalized = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            item = dict(row)
            rates = item.get("rates") or {}
            item["rate"] = (
                rates.get(key)
                if isinstance(rates, dict)
                else None
            )
            normalized.append(item)
        rows = normalized

    return _aggregate_bank_best(app_module, rows)


def _sorted_rows(rows):
    # Python sort is stable. This preserves the existing order inside ties,
    # matching the dashboard's current sequential ranking behaviour.
    return sorted(
        [deepcopy(row) for row in rows],
        key=lambda row: float(row.get("rate") or 0),
        reverse=True,
    )


def _woori_index(app_module, rows):
    for idx, row in enumerate(rows):
        if _is_woori(app_module, row.get("bank")):
            return idx
    return None


def _financial_group_rank(app_module, rows):
    aliases = [
        "우리금융저축은행",
        "신한저축은행",
        "하나저축은행",
        "KB저축은행",
    ]

    configured = getattr(app_module, "FINANCIAL_BANKS", None)
    if isinstance(configured, (list, tuple)) and configured:
        aliases = list(configured)

    group_keys = {
        _normalize_bank(app_module, name)
        for name in aliases
        if name
    }

    group_rows = [
        row
        for row in rows
        if _normalize_bank(
            app_module,
            row.get("bank")
        ) in group_keys
    ]

    woori_idx = _woori_index(app_module, group_rows)
    return {
        "rank": (
            woori_idx + 1
            if woori_idx is not None
            else None
        ),
        "total": len(group_rows),
    }


def _snapshot(app_module, rows):
    sorted_rows = _sorted_rows(rows)
    if not sorted_rows:
        return None

    woori_idx = _woori_index(
        app_module,
        sorted_rows
    )
    if woori_idx is None:
        return None

    woori = sorted_rows[woori_idx]
    rate = float(woori.get("rate") or 0)
    rates = [
        float(row.get("rate") or 0)
        for row in sorted_rows
        if float(row.get("rate") or 0) > 0
    ]

    if not rates:
        return None

    top_rate = max(rates)
    avg_rate = sum(rates) / len(rates)
    financial = _financial_group_rank(
        app_module,
        sorted_rows
    )

    above = (
        sorted_rows[woori_idx - 1]
        if woori_idx > 0
        else None
    )
    below = (
        sorted_rows[woori_idx + 1]
        if woori_idx + 1 < len(sorted_rows)
        else None
    )

    return {
        "rate": rate,
        "rank": woori_idx + 1,
        "total": len(sorted_rows),
        "top_rate": top_rate,
        "average_rate": avg_rate,
        "gap_top": rate - top_rate,
        "gap_average": rate - avg_rate,
        "financial_rank": financial.get("rank"),
        "financial_total": financial.get("total"),
        "product": woori.get("product") or "-",
        "above": deepcopy(above) if above else None,
        "below": deepcopy(below) if below else None,
    }


def _thresholds(app_module, rows):
    competitors = [
        row
        for row in _sorted_rows(rows)
        if not _is_woori(
            app_module,
            row.get("bank")
        )
    ]

    def cutoff(rank):
        if len(competitors) < rank:
            return None
        return float(
            competitors[rank - 1].get("rate")
            or 0
        )

    return {
        "top5": cutoff(5),
        "top10": cutoff(10),
    }


def simulate_rate(
    app_module,
    category="deposit",
    period="12",
    target_rate=None,
):
    category = str(category or "deposit").strip().lower()
    if category not in ("deposit", "isa", "irp"):
        category = "deposit"

    period = _valid_period(category, period)
    rows = _market_rows(
        app_module,
        category,
        period
    )

    current = _snapshot(app_module, rows)
    if current is None:
        return {
            "ok": False,
            "error": "woori_rate_not_found",
            "message": "우리금융 금리 데이터를 확인할 수 없습니다.",
        }

    current_rate = float(current["rate"])

    if target_rate in (None, ""):
        target = current_rate
    else:
        try:
            target = float(target_rate)
        except Exception:
            target = current_rate

    # Deposit rates in this system are percentage values, not fractions.
    target = max(0.01, min(target, 10.0))
    target = round(target, 2)

    simulated_rows = deepcopy(rows)
    found = False
    for row in simulated_rows:
        if _is_woori(app_module, row.get("bank")):
            row["rate"] = target
            found = True
            break

    if not found:
        return {
            "ok": False,
            "error": "woori_rate_not_found",
            "message": "우리금융 금리 데이터를 확인할 수 없습니다.",
        }

    simulated = _snapshot(
        app_module,
        simulated_rows
    )
    if simulated is None:
        return {
            "ok": False,
            "error": "simulation_failed",
            "message": "시뮬레이션 결과를 계산하지 못했습니다.",
        }

    thresholds = _thresholds(
        app_module,
        rows
    )

    return {
        "ok": True,
        "category": category,
        "category_label": _category_label(category),
        "period": period,
        "source": _source_label(category),
        "current": current,
        "simulated": simulated,
        "change": {
            "rate": simulated["rate"] - current["rate"],
            "rank_improvement": current["rank"] - simulated["rank"],
            "gap_top": simulated["gap_top"] - current["gap_top"],
            "gap_average": (
                simulated["gap_average"]
                - current["gap_average"]
            ),
        },
        "thresholds": thresholds,
    }


def _telegram_sim_category_menu():
    return {
        "inline_keyboard": [
            [
                {
                    "text": "🏦 정기예금",
                    "callback_data": "simcat:deposit",
                },
                {
                    "text": "🏦 ISA",
                    "callback_data": "simcat:isa",
                },
            ],
            [
                {
                    "text": "🏦 퇴직연금(IRP)",
                    "callback_data": "simcat:irp",
                }
            ],
            [
                {
                    "text": "⬅️ 메인 메뉴",
                    "callback_data": "main",
                }
            ],
        ]
    }


def _telegram_sim_period_menu(category):
    periods = (
        ["1", "3", "6", "12", "24", "36"]
        if category == "deposit"
        else ["3", "6", "12", "24", "36"]
    )

    buttons = [
        {
            "text": f"{period}개월",
            "callback_data": f"simperiod:{category}:{period}",
        }
        for period in periods
    ]

    rows = [buttons[:3], buttons[3:]]
    rows.append([
        {
            "text": "⬅️ 상품 선택",
            "callback_data": "sim_main",
        },
        {
            "text": "🏠 메인",
            "callback_data": "main",
        },
    ])

    return {
        "inline_keyboard": [row for row in rows if row]
    }


def _telegram_sim_adjust_menu(category, period, public_url):
    return {
        "inline_keyboard": [
            [
                {
                    "text": "▲0.10%p",
                    "callback_data": f"simadj:{category}:{period}:-10",
                },
                {
                    "text": "▲0.05%p",
                    "callback_data": f"simadj:{category}:{period}:-5",
                },
                {
                    "text": "현재",
                    "callback_data": f"simadj:{category}:{period}:0",
                },
            ],
            [
                {
                    "text": "+0.05%p",
                    "callback_data": f"simadj:{category}:{period}:5",
                },
                {
                    "text": "+0.10%p",
                    "callback_data": f"simadj:{category}:{period}:10",
                },
                {
                    "text": "+0.20%p",
                    "callback_data": f"simadj:{category}:{period}:20",
                },
            ],
            [
                {
                    "text": "⬅️ 기간 선택",
                    "callback_data": f"simcat:{category}",
                },
                {
                    "text": "📱 화면에서 직접입력",
                    "url": public_url + "/mobile",
                },
            ],
            [
                {
                    "text": "🏠 메인 메뉴",
                    "callback_data": "main",
                }
            ],
        ]
    }


def _telegram_change_text(value):
    value = float(value or 0)
    if abs(value) < 0.00001:
        return "-"
    if value > 0:
        return f"+{abs(value):.2f}%p"
    return f"▲{abs(value):.2f}%p"


def _telegram_gap_text(value):
    return _telegram_change_text(value)


def _telegram_rank_text(current_rank, simulated_rank):
    delta = int(current_rank or 0) - int(simulated_rank or 0)
    if delta > 0:
        return f"{delta}계단 개선"
    if delta < 0:
        return f"{abs(delta)}계단 악화"
    return "변동 없음"


def _telegram_sim_text(result):
    current = result.get("current") or {}
    simulated = result.get("simulated") or {}
    thresholds = result.get("thresholds") or {}

    lines = [
        "🧮 우리금융 금리 시뮬레이터",
        f"{result.get('category_label','-')} · {result.get('period','12')}개월",
        f"대표상품 : {current.get('product') or '-'}",
        "",
        (
            f"현재 {float(current.get('rate') or 0):.2f}% → "
            f"가정 {float(simulated.get('rate') or 0):.2f}%"
        ),
        (
            "금리변화 : "
            + _telegram_change_text(
                float(simulated.get("rate") or 0)
                - float(current.get("rate") or 0)
            )
        ),
        "",
        (
            f"시장순위 : {current.get('rank','-')}위 → "
            f"{simulated.get('rank','-')}위 "
            f"({_telegram_rank_text(current.get('rank'), simulated.get('rank'))})"
        ),
        (
            "시장 최고 대비 : "
            f"{_telegram_gap_text(current.get('gap_top'))} → "
            f"{_telegram_gap_text(simulated.get('gap_top'))}"
        ),
        (
            "시장 평균 대비 : "
            f"{_telegram_gap_text(current.get('gap_average'))} → "
            f"{_telegram_gap_text(simulated.get('gap_average'))}"
        ),
    ]

    if (
        current.get("financial_rank") is not None
        and simulated.get("financial_rank") is not None
    ):
        lines.append(
            "금융지주계 순위 : "
            f"{current.get('financial_rank')}위 → "
            f"{simulated.get('financial_rank')}위"
        )

    if thresholds.get("top10") is not None:
        lines.append(
            f"TOP10 경쟁선 : {float(thresholds['top10']):.2f}%"
        )

    if thresholds.get("top5") is not None:
        lines.append(
            f"TOP5 경쟁선 : {float(thresholds['top5']):.2f}%"
        )

    lines.extend([
        "",
        f"출처 : {result.get('source','-')}",
        "※ 실제 금리에 반영되지 않는 조회용 시뮬레이션입니다.",
    ])

    return "\n".join(lines)


def _refresh_telegram_commands_later(app_module):
    def worker():
        # app.py starts its original Telegram setup thread just before
        # scheduler import. Run after it so /simulate remains in the menu.
        time.sleep(5)
        api = getattr(app_module, "telegram_api", None)
        if not callable(api):
            return

        commands = [
            {"command": "start", "description": "SBRate 메인 메뉴"},
            {"command": "brief", "description": "오늘의 시장 브리핑"},
            {"command": "simulate", "description": "우리금융 금리 시뮬레이터"},
            {"command": "report", "description": "PC·모바일 대시보드"},
            {"command": "help", "description": "사용방법"},
        ]

        try:
            result = api(
                "setMyCommands",
                {"commands": commands},
            )
            print("Rate Simulator Telegram commands:", result)
        except Exception as error:
            print("Rate Simulator command setup error:", error)

    threading.Thread(
        target=worker,
        daemon=True,
    ).start()


def install_rate_simulator():
    app_module = _find_running_app_module()
    if app_module is None:
        print("Rate Simulator: app module not found")
        return False

    if getattr(app_module, "_rate_simulator_installed", False):
        return True

    flask_app = getattr(app_module, "app", None)
    if flask_app is None:
        return False

    try:
        from flask import jsonify, request

        if "rate_simulator_api" not in flask_app.view_functions:
            def rate_simulator_api():
                payload = (
                    request.get_json(silent=True) or {}
                    if request.method == "POST"
                    else request.args
                )

                category = str(
                    payload.get("category", "deposit")
                    or "deposit"
                ).strip().lower()
                period = str(
                    payload.get("period", "12")
                    or "12"
                ).strip()
                target_rate = payload.get("target_rate")

                result = simulate_rate(
                    app_module,
                    category=category,
                    period=period,
                    target_rate=target_rate,
                )

                return jsonify(result), (200 if result.get("ok") else 404)

            flask_app.add_url_rule(
                "/api/rate-simulator",
                endpoint="rate_simulator_api",
                view_func=rate_simulator_api,
                methods=["GET", "POST"],
            )

        @flask_app.after_request
        def inject_rate_simulator_assets(response):
            try:
                if (
                    request.path not in ("/", "/mobile")
                    or response.status_code != 200
                    or "text/html" not in str(response.content_type or "")
                ):
                    return response

                html = response.get_data(as_text=True)
                if "data-sbrate-rate-simulator" in html:
                    return response

                css_tag = (
                    f'<link data-sbrate-rate-simulator="css" '
                    f'rel="stylesheet" href="{SIMULATOR_CSS}">'
                )
                js_tag = (
                    f'<script data-sbrate-rate-simulator="js" '
                    f'defer src="{SIMULATOR_JS}"></script>'
                )

                if "</head>" in html:
                    html = html.replace(
                        "</head>",
                        css_tag + "\n</head>",
                        1,
                    )
                if "</body>" in html:
                    html = html.replace(
                        "</body>",
                        js_tag + "\n</body>",
                        1,
                    )

                response.set_data(html)
                response.headers.pop("Content-Length", None)
            except Exception as error:
                print("Rate Simulator asset inject error:", error)

            return response

        original_main_menu = getattr(
            app_module,
            "telegram_main_menu",
            None,
        )

        if callable(original_main_menu):
            @wraps(original_main_menu)
            def telegram_main_menu_with_simulator():
                menu = original_main_menu() or {}
                keyboard = menu.get("inline_keyboard")
                if not isinstance(keyboard, list):
                    keyboard = []
                    menu["inline_keyboard"] = keyboard

                already = any(
                    isinstance(button, dict)
                    and button.get("callback_data") == "sim_main"
                    for row in keyboard
                    if isinstance(row, list)
                    for button in row
                )

                if not already:
                    insert_at = max(0, len(keyboard) - 1)
                    keyboard.insert(
                        insert_at,
                        [
                            {
                                "text": "🧮 금리 시뮬레이터",
                                "callback_data": "sim_main",
                            }
                        ],
                    )

                return menu

            app_module.telegram_main_menu = (
                telegram_main_menu_with_simulator
            )

        original_query_menu = getattr(
            app_module,
            "telegram_query_menu",
            None,
        )

        if callable(original_query_menu):
            @wraps(original_query_menu)
            def telegram_query_menu_with_simulator(category, period):
                menu = original_query_menu(category, period) or {}
                keyboard = menu.get("inline_keyboard")
                if not isinstance(keyboard, list):
                    keyboard = []
                    menu["inline_keyboard"] = keyboard

                callback = f"simperiod:{category}:{period}"
                already = any(
                    isinstance(button, dict)
                    and button.get("callback_data") == callback
                    for row in keyboard
                    if isinstance(row, list)
                    for button in row
                )

                if not already:
                    insert_at = max(0, len(keyboard) - 1)
                    keyboard.insert(
                        insert_at,
                        [
                            {
                                "text": "🧮 우리금융 금리 시뮬레이션",
                                "callback_data": callback,
                            }
                        ],
                    )

                return menu

            app_module.telegram_query_menu = (
                telegram_query_menu_with_simulator
            )

        original_callback = getattr(
            app_module,
            "telegram_handle_callback",
            None,
        )

        if callable(original_callback):
            @wraps(original_callback)
            def telegram_callback_with_simulator(callback):
                data = str(
                    (callback or {}).get("data", "")
                ).strip()

                if not (
                    data == "sim_main"
                    or data.startswith("simcat:")
                    or data.startswith("simperiod:")
                    or data.startswith("simadj:")
                ):
                    return original_callback(callback)

                message = (callback or {}).get("message") or {}
                chat = message.get("chat") or {}
                chat_id = chat.get("id")
                callback_id = (callback or {}).get("id")

                if chat_id is None:
                    return

                private_check = getattr(
                    app_module,
                    "telegram_is_private_chat",
                    None,
                )
                if callable(private_check) and not private_check(chat):
                    answer_callback = getattr(
                        app_module,
                        "telegram_answer_callback",
                        None,
                    )
                    if callable(answer_callback):
                        answer_callback(
                            callback_id,
                            "시뮬레이터는 SBRateBot 개인채팅에서 이용해주세요.",
                        )
                    return

                answer_callback = getattr(
                    app_module,
                    "telegram_answer_callback",
                    None,
                )
                if callable(answer_callback):
                    answer_callback(callback_id)

                send = getattr(
                    app_module,
                    "telegram_send_message",
                    None,
                )
                if not callable(send):
                    return

                if data == "sim_main":
                    send(
                        chat_id,
                        "🧮 우리금융 금리 시뮬레이터\n\n조회할 상품을 선택해주세요.",
                        reply_markup=_telegram_sim_category_menu(),
                    )
                    return

                if data.startswith("simcat:"):
                    category = data.split(":", 1)[1]
                    send(
                        chat_id,
                        (
                            f"🧮 {_category_label(category)} 금리 시뮬레이터\n\n"
                            "조회할 기간을 선택해주세요."
                        ),
                        reply_markup=_telegram_sim_period_menu(category),
                    )
                    return

                if data.startswith("simperiod:"):
                    parts = data.split(":")
                    if len(parts) != 3:
                        return
                    _, category, period = parts
                    result = simulate_rate(
                        app_module,
                        category,
                        period,
                        None,
                    )
                else:
                    parts = data.split(":")
                    if len(parts) != 4:
                        return
                    _, category, period, delta_raw = parts
                    base = simulate_rate(
                        app_module,
                        category,
                        period,
                        None,
                    )
                    if not base.get("ok"):
                        result = base
                    else:
                        try:
                            delta = int(delta_raw) / 100.0
                        except Exception:
                            delta = 0
                        current_rate = float(
                            (base.get("current") or {}).get("rate")
                            or 0
                        )
                        result = simulate_rate(
                            app_module,
                            category,
                            period,
                            current_rate + delta,
                        )

                if not result.get("ok"):
                    send(
                        chat_id,
                        result.get("message") or "시뮬레이션 데이터를 확인할 수 없습니다.",
                        reply_markup=_telegram_sim_category_menu(),
                    )
                    return

                public_url = str(
                    getattr(
                        app_module,
                        "SB_RATE_PUBLIC_URL",
                        "https://sbrate.onrender.com",
                    )
                    or "https://sbrate.onrender.com"
                ).rstrip("/")

                send(
                    chat_id,
                    _telegram_sim_text(result),
                    reply_markup=_telegram_sim_adjust_menu(
                        category,
                        period,
                        public_url,
                    ),
                )

            app_module.telegram_handle_callback = (
                telegram_callback_with_simulator
            )

        original_message = getattr(
            app_module,
            "telegram_handle_message",
            None,
        )

        if callable(original_message):
            @wraps(original_message)
            def telegram_message_with_simulator(message):
                text = str(
                    (message or {}).get("text", "")
                ).strip()
                command = (
                    text.split()[0].split("@")[0].lower()
                    if text
                    else ""
                )

                if (
                    command in ("/simulate", "/sim")
                    or text in (
                        "시뮬레이터",
                        "금리 시뮬레이터",
                        "금리 시뮬레이션",
                    )
                ):
                    chat = (message or {}).get("chat") or {}
                    chat_id = chat.get("id")
                    private_check = getattr(
                        app_module,
                        "telegram_is_private_chat",
                        None,
                    )

                    if (
                        chat_id is not None
                        and (
                            not callable(private_check)
                            or private_check(chat)
                        )
                    ):
                        send = getattr(
                            app_module,
                            "telegram_send_message",
                            None,
                        )
                        if callable(send):
                            send(
                                chat_id,
                                "🧮 우리금융 금리 시뮬레이터\n\n조회할 상품을 선택해주세요.",
                                reply_markup=_telegram_sim_category_menu(),
                            )
                    return

                return original_message(message)

            app_module.telegram_handle_message = (
                telegram_message_with_simulator
            )

        original_help = getattr(
            app_module,
            "telegram_help_text",
            None,
        )
        if callable(original_help):
            @wraps(original_help)
            def telegram_help_with_simulator():
                text = str(original_help() or "")
                if "/simulate" not in text:
                    text += (
                        "\n/simulate - 우리금융 금리 시뮬레이터"
                    )
                return text

            app_module.telegram_help_text = (
                telegram_help_with_simulator
            )

        _refresh_telegram_commands_later(app_module)

        app_module._rate_simulator_installed = True
        print("Rate Simulator V1 installed")
        return True

    except Exception as error:
        print("Rate Simulator install error:", error)
        return False
