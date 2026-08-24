# ==========================================
# SBRate Data Quality Telegram Endpoint
# - Receives signed GitHub validation payload
# - Notifies TELEGRAM_ADMIN_CHAT_ID only for anomalies
# ==========================================

import os
import sys


def _find_running_app_module():
    for name in ("app", "__main__"):
        module = sys.modules.get(name)
        if module is not None and hasattr(module, "app"):
            return module
    return None


def _pension_count_line(label, data):
    banks = data.get("banks", 0)
    valid = data.get("valid_rate_rows", 0)
    verified = data.get("verified_today")
    retained = data.get("retained_last_good")
    unavailable = data.get("unavailable_rows")
    failed_no_value = data.get("fetch_failed_rows")

    # Backward compatibility with V1 payloads.
    if verified is None and retained is None and unavailable is None:
        return f"• {label} : {banks}개사 / 금리확인 {valid}개사"

    verified = int(verified or 0)
    retained = int(retained or 0)
    unavailable = int(unavailable or 0) + int(failed_no_value or 0)
    return (
        f"• {label} : {banks}개사 / 금리확인 {valid}개사"
        f" · 오늘확인 {verified} · 직전값 {retained} · 미확보 {unavailable}"
    )


def _quality_message(payload):
    status = str(payload.get("status") or "UNKNOWN").upper()
    generated_at = str(payload.get("generated_at") or "-")
    verification_phase = str(payload.get("verification_phase") or "").strip()
    counts = payload.get("counts") if isinstance(payload.get("counts"), dict) else {}
    issues = payload.get("issues") if isinstance(payload.get("issues"), list) else []

    deposit = counts.get("deposit") if isinstance(counts.get("deposit"), dict) else {}
    isa = counts.get("isa") if isinstance(counts.get("isa"), dict) else {}
    irp = counts.get("irp") if isinstance(counts.get("irp"), dict) else {}

    icon = "🚨" if status == "BLOCKED" else "⚠️"
    title = "데이터 반영 차단" if status == "BLOCKED" else "데이터 검증 경고"

    lines = [
        f"{icon} SBRate {title}",
        "",
        f"검증상태 : {status}",
        f"검증시각 : {generated_at}",
    ]

    if verification_phase:
        lines.append(f"검증단계 : {verification_phase}")

    lines.extend([
        "",
        "수집현황",
        f"• 정기예금 : {deposit.get('banks', 0)}개사 / {deposit.get('items', 0)}상품",
        _pension_count_line("ISA", isa),
        _pension_count_line("IRP", irp),
    ])

    if issues:
        lines.extend(["", "확인 필요"])
        for item in issues[:12]:
            if not isinstance(item, dict):
                continue
            level = str(item.get("level") or "WARNING")
            section = str(item.get("section") or "-")
            message = str(item.get("message") or "-")
            bullet = "❌" if level == "ERROR" else "•"
            lines.append(f"{bullet} [{section}] {message}")

    if status == "BLOCKED":
        lines.extend([
            "",
            "※ 이상 데이터는 GitHub main에 반영하지 않도록 차단했습니다.",
            "※ 원인 확인 후 수집기를 재실행하거나 데이터를 점검해주세요.",
        ])
    else:
        lines.extend([
            "",
            "※ '오늘확인'은 이번 실행에서 공식소스를 정상 확인한 건수입니다.",
            "※ '직전값'은 오늘 확인 실패로 마지막 정상값을 유지한 건수입니다.",
        ])
        if verification_phase:
            lines.append("※ 00:30 1차 실패 후 06:30 재확인에서도 남은 실패만 알립니다.")
        else:
            lines.append("※ WARNING 데이터는 반영되지만 관리자 확인이 필요합니다.")

    return "\n".join(lines)


def install_data_quality_endpoint():
    app_module = _find_running_app_module()
    if app_module is None:
        print("Data Quality endpoint: app module not found")
        return False

    flask_app = getattr(app_module, "app", None)
    if flask_app is None:
        return False

    if "telegram_data_quality" in flask_app.view_functions:
        return True

    try:
        from flask import jsonify, request

        def telegram_data_quality():
            expected_secret = os.getenv("TELEGRAM_BRIEF_SECRET", "").strip()
            provided_secret = request.headers.get("X-SBRate-Secret", "").strip()

            if expected_secret and provided_secret != expected_secret:
                return jsonify({"ok": False, "error": "invalid_secret"}), 403

            payload = request.get_json(silent=True) or {}
            if not isinstance(payload, dict):
                return jsonify({"ok": False, "error": "invalid_payload"}), 400

            status = str(payload.get("status") or "").upper()
            should_notify = bool(payload.get("notify"))

            if status not in ("WARNING", "BLOCKED") or not should_notify:
                return jsonify({"ok": True, "notified": False, "status": status})

            admin_chat_id = str(
                getattr(app_module, "TELEGRAM_ADMIN_CHAT_ID", "") or ""
            ).strip()

            if not admin_chat_id:
                return jsonify({"ok": False, "error": "admin_chat_id_missing"}), 503

            send_message = getattr(app_module, "telegram_send_message", None)
            if not callable(send_message):
                return jsonify({"ok": False, "error": "telegram_sender_missing"}), 503

            send_message(admin_chat_id, _quality_message(payload))
            return jsonify({"ok": True, "notified": True, "status": status})

        flask_app.add_url_rule(
            "/telegram/data-quality",
            endpoint="telegram_data_quality",
            view_func=telegram_data_quality,
            methods=["POST"],
        )

        print("Data Quality Telegram endpoint installed")
        return True

    except Exception as error:
        print("Data Quality endpoint install error:", error)
        return False
