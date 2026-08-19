# ==========================================
# SBRate V5.45 Anonymous Visitor Stats
# - PC / mobile unique browser + pageview counts
# - Telegram /stats for admin private chat only
# - No IP / name / employee ID / User-Agent stored
# ==========================================

import hashlib
import os
import re
import sqlite3
import sys

from datetime import datetime, timedelta, timezone
from functools import wraps


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

VISITOR_STATS_FILE = os.getenv(
    "SB_RATE_VISITOR_DB",
    os.path.join(BASE_DIR, "data", "visitor_stats.sqlite3")
).strip()

VISITOR_COOKIE_NAME = "sbrate_vid"
VISITOR_COOKIE_MAX_AGE = 60 * 60 * 24 * 365
VISITOR_STATS_KST = timezone(timedelta(hours=9))
VISITOR_HASH_SALT = (
    os.getenv(
        "SB_RATE_VISITOR_SALT",
        "sbrate-anonymous-visitor-v1"
    ).strip()
    or "sbrate-anonymous-visitor-v1"
)


def _now():
    return datetime.now(VISITOR_STATS_KST)


def _db():
    parent = os.path.dirname(VISITOR_STATS_FILE)
    if parent:
        os.makedirs(parent, exist_ok=True)

    conn = sqlite3.connect(VISITOR_STATS_FILE, timeout=8)

    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
    except Exception:
        pass

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS visitor_stats (
            day TEXT NOT NULL,
            platform TEXT NOT NULL,
            visitor_hash TEXT NOT NULL,
            pageviews INTEGER NOT NULL DEFAULT 0,
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            PRIMARY KEY (day, platform, visitor_hash)
        )
        """
    )
    return conn


def _should_track(request):
    ua = str(request.headers.get("User-Agent", "")).strip().lower()
    if not ua:
        return False

    # Automated Render/GitHub/crawler traffic must not inflate usage.
    ignored = (
        "sbrate-keepalive",
        "github-actions",
        "curl/",
        "wget/",
        "python-requests",
        "healthcheck",
        "uptime",
        "monitoring",
        "crawler",
        "spider",
        "bot/",
    )
    return not any(token in ua for token in ignored)


def _normalize_visitor_id(value):
    value = str(value or "").strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{16,80}", value):
        return value
    return ""


def _hash_visitor_id(visitor_id):
    raw = f"{VISITOR_HASH_SALT}:{visitor_id}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:32]


def _record_visit(platform, visitor_id):
    if platform not in ("pc", "mobile"):
        return

    now = _now()
    day = now.strftime("%Y-%m-%d")
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    visitor_hash = _hash_visitor_id(visitor_id)
    cutoff = (now.date() - timedelta(days=45)).isoformat()

    try:
        with _db() as conn:
            conn.execute(
                """
                INSERT INTO visitor_stats (
                    day, platform, visitor_hash,
                    pageviews, first_seen, last_seen
                )
                VALUES (?, ?, ?, 1, ?, ?)
                ON CONFLICT(day, platform, visitor_hash)
                DO UPDATE SET
                    pageviews = pageviews + 1,
                    last_seen = excluded.last_seen
                """,
                (day, platform, visitor_hash, timestamp, timestamp)
            )
            conn.execute(
                "DELETE FROM visitor_stats WHERE day < ?",
                (cutoff,)
            )
    except Exception as error:
        print("VISITOR STATS RECORD ERROR:", error)


def _track_response(response, platform, request, make_response):
    response = make_response(response)

    if not _should_track(request):
        return response

    visitor_id = _normalize_visitor_id(
        request.cookies.get(VISITOR_COOKIE_NAME)
    )

    if not visitor_id:
        visitor_id = os.urandom(18).hex()
        forwarded_proto = str(
            request.headers.get("X-Forwarded-Proto", "")
        ).lower()

        response.set_cookie(
            VISITOR_COOKIE_NAME,
            visitor_id,
            max_age=VISITOR_COOKIE_MAX_AGE,
            httponly=True,
            secure=(request.is_secure or forwarded_proto == "https"),
            samesite="Lax",
            path="/"
        )

    _record_visit(platform, visitor_id)
    return response


def _snapshot(days=7):
    days = max(1, min(int(days or 7), 31))
    now = _now()
    date_list = [
        (now.date() - timedelta(days=offset)).isoformat()
        for offset in range(days)
    ]

    result = {
        day: {
            "pc": {"visitors": 0, "views": 0},
            "mobile": {"visitors": 0, "views": 0},
            "total": {"visitors": 0, "views": 0},
        }
        for day in date_list
    }

    try:
        with _db() as conn:
            placeholders = ",".join("?" for _ in date_list)

            rows = conn.execute(
                f"""
                SELECT day, platform,
                       COUNT(*) AS visitors,
                       COALESCE(SUM(pageviews), 0) AS views
                FROM visitor_stats
                WHERE day IN ({placeholders})
                GROUP BY day, platform
                """,
                date_list
            ).fetchall()

            totals = conn.execute(
                f"""
                SELECT day,
                       COUNT(DISTINCT visitor_hash) AS visitors,
                       COALESCE(SUM(pageviews), 0) AS views
                FROM visitor_stats
                WHERE day IN ({placeholders})
                GROUP BY day
                """,
                date_list
            ).fetchall()

        for day, platform, visitors, views in rows:
            if day in result and platform in ("pc", "mobile"):
                result[day][platform] = {
                    "visitors": int(visitors or 0),
                    "views": int(views or 0),
                }

        for day, visitors, views in totals:
            if day in result:
                result[day]["total"] = {
                    "visitors": int(visitors or 0),
                    "views": int(views or 0),
                }

    except Exception as error:
        print("VISITOR STATS READ ERROR:", error)

    return now, date_list, result


def visitor_stats_text():
    now, date_list, stats = _snapshot(7)
    current = stats[date_list[0]]

    lines = [
        "📊 SBRate 이용현황",
        f"{now.strftime('%Y-%m-%d %H:%M')} KST",
        "",
        "오늘",
        (
            f"🖥 PC : {current['pc']['visitors']}명 · "
            f"{current['pc']['views']}회"
        ),
        (
            f"📱 모바일 : {current['mobile']['visitors']}명 · "
            f"{current['mobile']['views']}회"
        ),
        (
            f"👥 전체 : {current['total']['visitors']}명 · "
            f"{current['total']['views']}회"
        ),
        "",
        "최근 7일",
    ]

    for day in date_list:
        item = stats[day]
        mmdd = day[5:].replace("-", "/")
        lines.append(
            f"{mmdd}  "
            f"PC {item['pc']['visitors']}명/{item['pc']['views']}회 · "
            f"모바일 {item['mobile']['visitors']}명/"
            f"{item['mobile']['views']}회"
        )

    lines.extend([
        "",
        "※ 방문자는 익명 브라우저 기준입니다.",
        "※ IP·이름·사번은 수집하지 않습니다.",
    ])
    return "\n".join(lines)


def _find_running_app_module():
    # Gunicorn: app / local python app.py: __main__
    for name in ("app", "__main__"):
        module = sys.modules.get(name)
        if module is not None and hasattr(module, "app"):
            return module
    return None


def install_visitor_stats_hooks():
    """Attach tracking and admin /stats without changing the large app.py."""
    app_module = _find_running_app_module()
    if app_module is None:
        print("Visitor Stats: app module not found")
        return False

    if getattr(app_module, "_visitor_stats_hooks_installed", False):
        return True

    flask_app = getattr(app_module, "app", None)
    if flask_app is None:
        return False

    try:
        from flask import make_response, request

        def wrap_view(endpoint, platform):
            original = flask_app.view_functions.get(endpoint)
            if original is None:
                print("Visitor Stats endpoint missing:", endpoint)
                return False

            @wraps(original)
            def tracked(*args, **kwargs):
                response = original(*args, **kwargs)
                return _track_response(
                    response,
                    platform,
                    request,
                    make_response
                )

            flask_app.view_functions[endpoint] = tracked
            return True

        pc_ok = wrap_view("index", "pc")
        mobile_ok = wrap_view("mobile_dashboard", "mobile")

        original_handler = getattr(
            app_module,
            "telegram_handle_message",
            None
        )
        telegram_ok = False

        if original_handler:
            @wraps(original_handler)
            def telegram_with_stats(message):
                if isinstance(message, dict):
                    chat = message.get("chat") or {}
                    chat_id = chat.get("id")
                    text = str(message.get("text", "")).strip()
                    command = (
                        text.split()[0].split("@")[0].lower()
                        if text else ""
                    )

                    if command == "/stats":
                        admin_chat_id = str(
                            getattr(
                                app_module,
                                "TELEGRAM_ADMIN_CHAT_ID",
                                ""
                            )
                            or ""
                        ).strip()
                        is_private = (
                            str(chat.get("type", "")).lower()
                            == "private"
                        )

                        if (
                            is_private
                            and admin_chat_id
                            and str(chat_id) == admin_chat_id
                        ):
                            app_module.telegram_send_message(
                                chat_id,
                                visitor_stats_text()
                            )
                        return

                return original_handler(message)

            app_module.telegram_handle_message = telegram_with_stats
            telegram_ok = True

        if pc_ok and mobile_ok and telegram_ok:
            app_module._visitor_stats_hooks_installed = True
            print("Visitor Stats V5.45 hooks installed")
            return True

        print(
            "Visitor Stats hook incomplete:",
            f"pc={pc_ok}",
            f"mobile={mobile_ok}",
            f"telegram={telegram_ok}"
        )
        return False

    except Exception as error:
        print("Visitor Stats hook error:", error)
        return False
