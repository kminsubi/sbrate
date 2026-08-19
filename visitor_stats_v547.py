# ==========================================
# SBRate V5.47 Anonymous Visitor Stats
# - PC / mobile unique browser + pageview counts
# - Telegram /stats for admin private chat only
# - Upstash Redis REST persistent storage
# - Robust Render env parsing (quotes / KEY=value tolerated)
# - SQLite fallback with visible backend diagnostics
# - No IP / name / employee ID / User-Agent stored
# ==========================================

import hashlib
import os
import re
import sqlite3
import sys

from datetime import datetime, timedelta, timezone
from functools import wraps

import requests


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

VISITOR_STATS_FILE = os.getenv(
    "SB_RATE_VISITOR_DB",
    os.path.join(BASE_DIR, "data", "visitor_stats.sqlite3")
).strip()

VISITOR_COOKIE_NAME = "sbrate_vid"
VISITOR_COOKIE_MAX_AGE = 60 * 60 * 24 * 365
VISITOR_STATS_KST = timezone(timedelta(hours=9))
VISITOR_RETENTION_SECONDS = 60 * 60 * 24 * 60

VISITOR_HASH_SALT = (
    os.getenv(
        "SB_RATE_VISITOR_SALT",
        "sbrate-anonymous-visitor-v1"
    ).strip()
    or "sbrate-anonymous-visitor-v1"
)

_LAST_UPSTASH_ERROR = ""


def _clean_env_value(name):
    """Accept raw value, quoted value, or copied KEY=value snippets."""
    raw = str(os.getenv(name, "") or "").strip()
    if not raw:
        return ""

    # If the user pasted a full line like KEY="value", extract only value.
    pattern = rf"(?:^|\n)\s*{re.escape(name)}\s*=\s*[\"']?([^\"'\s]+)"
    match = re.search(pattern, raw)
    if match:
        raw = match.group(1)

    raw = raw.strip().strip('"').strip("'").strip()

    # URL field can also contain extra copied text; keep the https URL only.
    if name.endswith("_URL") and not raw.startswith(("http://", "https://")):
        url_match = re.search(r"https://[^\s\"']+", raw)
        if url_match:
            raw = url_match.group(0)

    return raw.rstrip("/") if name.endswith("_URL") else raw


UPSTASH_REDIS_REST_URL = _clean_env_value("UPSTASH_REDIS_REST_URL")
UPSTASH_REDIS_REST_TOKEN = _clean_env_value("UPSTASH_REDIS_REST_TOKEN")


def _now():
    return datetime.now(VISITOR_STATS_KST)


def _upstash_enabled():
    return bool(UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN)


def _safe_upstash_error(error):
    """Return a short diagnostic without ever exposing URL/token."""
    text = str(error or "").strip()
    if not text:
        return "unknown"

    lowered = text.lower()
    if "401" in text or "unauthorized" in lowered:
        return "인증 실패"
    if "403" in text or "forbidden" in lowered:
        return "권한 오류"
    if "invalid url" in lowered or "missing schema" in lowered:
        return "URL 형식 오류"
    if "timeout" in lowered or "timed out" in lowered:
        return "연결 시간초과"
    if "connection" in lowered or "name resolution" in lowered:
        return "네트워크 연결 오류"
    if "400" in text or "bad request" in lowered:
        return "요청 형식 오류"
    return "연결 오류"


def _upstash_pipeline(commands, timeout=6):
    global _LAST_UPSTASH_ERROR

    if not _upstash_enabled():
        raise RuntimeError("Upstash is not configured")

    try:
        response = requests.post(
            f"{UPSTASH_REDIS_REST_URL}/pipeline",
            headers={
                "Authorization": f"Bearer {UPSTASH_REDIS_REST_TOKEN}",
                "Content-Type": "application/json",
            },
            json=commands,
            timeout=timeout,
        )
        response.raise_for_status()

        payload = response.json()
        if not isinstance(payload, list):
            raise RuntimeError("Invalid Upstash pipeline response")

        for item in payload:
            if isinstance(item, dict) and item.get("error"):
                raise RuntimeError(str(item.get("error")))

        _LAST_UPSTASH_ERROR = ""
        return payload

    except Exception as error:
        _LAST_UPSTASH_ERROR = _safe_upstash_error(error)
        raise


def _redis_result(item, default=0):
    if not isinstance(item, dict):
        return default
    value = item.get("result")
    if value is None:
        return default
    return value


def _redis_keys(day, platform=None):
    prefix = "sbrate:visitor:v1"
    if platform:
        return {
            "visitors": f"{prefix}:{day}:{platform}:visitors",
            "views": f"{prefix}:{day}:{platform}:views",
        }
    return {"all": f"{prefix}:{day}:all:visitors"}


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


def _record_visit_upstash(platform, visitor_hash, day):
    platform_keys = _redis_keys(day, platform)
    all_key = _redis_keys(day)["all"]

    commands = [
        ["SADD", platform_keys["visitors"], visitor_hash],
        ["SADD", all_key, visitor_hash],
        ["INCR", platform_keys["views"]],
        ["EXPIRE", platform_keys["visitors"], VISITOR_RETENTION_SECONDS],
        ["EXPIRE", all_key, VISITOR_RETENTION_SECONDS],
        ["EXPIRE", platform_keys["views"], VISITOR_RETENTION_SECONDS],
    ]
    _upstash_pipeline(commands)


def _record_visit_sqlite(platform, visitor_hash, now):
    day = now.strftime("%Y-%m-%d")
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    cutoff = (now.date() - timedelta(days=45)).isoformat()

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
        conn.execute("DELETE FROM visitor_stats WHERE day < ?", (cutoff,))


def _record_visit(platform, visitor_id):
    if platform not in ("pc", "mobile"):
        return

    now = _now()
    day = now.strftime("%Y-%m-%d")
    visitor_hash = _hash_visitor_id(visitor_id)

    if _upstash_enabled():
        try:
            _record_visit_upstash(platform, visitor_hash, day)
            return
        except Exception as error:
            print("VISITOR STATS UPSTASH RECORD ERROR:", _safe_upstash_error(error))

    try:
        _record_visit_sqlite(platform, visitor_hash, now)
    except Exception as error:
        print("VISITOR STATS SQLITE RECORD ERROR:", error)


def _track_response(response, platform, request, make_response):
    response = make_response(response)

    if not _should_track(request):
        return response

    visitor_id = _normalize_visitor_id(request.cookies.get(VISITOR_COOKIE_NAME))

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


def _empty_snapshot(days):
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
    return now, date_list, result


def _snapshot_upstash(days):
    now, date_list, result = _empty_snapshot(days)
    commands = []

    for day in date_list:
        pc = _redis_keys(day, "pc")
        mobile = _redis_keys(day, "mobile")
        all_key = _redis_keys(day)["all"]
        commands.extend([
            ["SCARD", pc["visitors"]],
            ["GET", pc["views"]],
            ["SCARD", mobile["visitors"]],
            ["GET", mobile["views"]],
            ["SCARD", all_key],
        ])

    payload = _upstash_pipeline(commands)
    cursor = 0

    for day in date_list:
        pc_visitors = int(_redis_result(payload[cursor], 0) or 0)
        pc_views = int(_redis_result(payload[cursor + 1], 0) or 0)
        mobile_visitors = int(_redis_result(payload[cursor + 2], 0) or 0)
        mobile_views = int(_redis_result(payload[cursor + 3], 0) or 0)
        total_visitors = int(_redis_result(payload[cursor + 4], 0) or 0)
        cursor += 5

        result[day]["pc"] = {"visitors": pc_visitors, "views": pc_views}
        result[day]["mobile"] = {
            "visitors": mobile_visitors,
            "views": mobile_views,
        }
        result[day]["total"] = {
            "visitors": total_visitors,
            "views": pc_views + mobile_views,
        }

    return now, date_list, result, "Upstash (영구)"


def _snapshot_sqlite(days):
    now, date_list, result = _empty_snapshot(days)

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

    return now, date_list, result


def _snapshot(days=7):
    days = max(1, min(int(days or 7), 31))

    if _upstash_enabled():
        try:
            return _snapshot_upstash(days)
        except Exception as error:
            print("VISITOR STATS UPSTASH READ ERROR:", _safe_upstash_error(error))
            now, date_list, result = _snapshot_sqlite(days)
            reason = _LAST_UPSTASH_ERROR or _safe_upstash_error(error)
            return now, date_list, result, f"SQLite (임시 · Upstash {reason})"

    now, date_list, result = _snapshot_sqlite(days)
    return now, date_list, result, "SQLite (임시 · Upstash 설정 없음)"


def visitor_stats_text():
    try:
        now, date_list, stats, backend = _snapshot(7)
    except Exception as error:
        now, date_list, stats = _empty_snapshot(7)
        backend = "저장소 오류"
        print("VISITOR STATS SNAPSHOT ERROR:", error)

    current = stats[date_list[0]]

    lines = [
        "📊 SBRate 이용현황",
        f"{now.strftime('%Y-%m-%d %H:%M')} KST",
        f"저장소 : {backend}",
        "",
        "오늘",
        f"🖥 PC : {current['pc']['visitors']}명 · {current['pc']['views']}회",
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
    for name in ("app", "__main__"):
        module = sys.modules.get(name)
        if module is not None and hasattr(module, "app"):
            return module
    return None


def install_visitor_stats_hooks():
    """Attach tracking and admin /stats without changing app.py."""
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

        original_handler = getattr(app_module, "telegram_handle_message", None)
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
                            getattr(app_module, "TELEGRAM_ADMIN_CHAT_ID", "")
                            or ""
                        ).strip()
                        is_private = (
                            str(chat.get("type", "")).lower() == "private"
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
            mode = "Upstash configured" if _upstash_enabled() else "SQLite fallback"
            print("Visitor Stats V5.47 hooks installed:", mode)
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
