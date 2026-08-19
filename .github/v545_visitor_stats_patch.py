from pathlib import Path
import re

path = Path("app.py")
text = path.read_text(encoding="utf-8")

old = "from flask import Flask, render_template, jsonify, request"
new = "from flask import Flask, render_template, jsonify, request, make_response"
if old not in text:
    raise SystemExit("flask import marker not found")
text = text.replace(old, new, 1)

old = "import threading\nimport requests as http_requests\nfrom datetime import datetime"
new = "import threading\nimport sqlite3\nimport requests as http_requests\nfrom datetime import datetime, timedelta, timezone"
if old not in text:
    raise SystemExit("stdlib import marker not found")
text = text.replace(old, new, 1)

# Route responses: render through anonymous visit tracker.
text, count_pc = re.subn(
    r'(@app\.route\("/"\)\ndef index\(\):\s*)return render_template\(\s*"index\.html"\s*\)',
    r'\1return tracked_dashboard_response("index.html", "pc")',
    text,
    count=1,
)
if count_pc != 1:
    raise SystemExit(f"PC route patch count={count_pc}")

text, count_mobile = re.subn(
    r'(@app\.route\("/mobile"\)\ndef mobile_dashboard\(\):\s*)return render_template\(\s*"mobile\.html"\s*\)',
    r'\1return tracked_dashboard_response("mobile.html", "mobile")',
    text,
    count=1,
)
if count_mobile != 1:
    raise SystemExit(f"mobile route patch count={count_mobile}")

marker = "# -------------------------------\n# 기간 설정\n# -------------------------------"
if marker not in text:
    raise SystemExit("period marker not found")

analytics_block = r'''
# -------------------------------
# 익명 방문 통계 V5.45
# PC / 모바일 고유 브라우저 + 페이지 조회수
# IP, 이름, 사번, User-Agent는 저장하지 않는다.
# -------------------------------

VISITOR_STATS_FILE = os.getenv(
    "SB_RATE_VISITOR_DB",
    os.path.join(BASE_DIR, "data", "visitor_stats.sqlite3")
).strip()

VISITOR_COOKIE_NAME = "sbrate_vid"
VISITOR_COOKIE_MAX_AGE = 60 * 60 * 24 * 365
VISITOR_STATS_KST = timezone(timedelta(hours=9))
VISITOR_HASH_SALT = os.getenv(
    "SB_RATE_VISITOR_SALT",
    "sbrate-anonymous-visitor-v1"
).strip() or "sbrate-anonymous-visitor-v1"


def visitor_stats_now():
    return datetime.now(VISITOR_STATS_KST)


def visitor_stats_connect():
    os.makedirs(
        os.path.dirname(VISITOR_STATS_FILE),
        exist_ok=True
    )

    conn = sqlite3.connect(
        VISITOR_STATS_FILE,
        timeout=8
    )

    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
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


def visitor_should_track():
    ua = str(
        request.headers.get("User-Agent", "")
    ).strip().lower()

    # Render keep-alive / health checks / crawlers must never inflate usage.
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


def visitor_normalize_id(value):
    value = str(value or "").strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{16,80}", value):
        return value
    return ""


def visitor_hash_id(visitor_id):
    raw = f"{VISITOR_HASH_SALT}:{visitor_id}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:32]


def visitor_record(platform, visitor_id):
    if platform not in ("pc", "mobile"):
        return False

    now = visitor_stats_now()
    day = now.strftime("%Y-%m-%d")
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    visitor_hash = visitor_hash_id(visitor_id)
    cutoff = (now.date() - timedelta(days=45)).isoformat()

    try:
        with visitor_stats_connect() as conn:
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
                (
                    day,
                    platform,
                    visitor_hash,
                    timestamp,
                    timestamp,
                )
            )
            conn.execute(
                "DELETE FROM visitor_stats WHERE day < ?",
                (cutoff,)
            )
        return True
    except Exception as error:
        print("VISITOR STATS RECORD ERROR:", error)
        return False


def tracked_dashboard_response(template_name, platform):
    response = make_response(
        render_template(template_name)
    )

    if not visitor_should_track():
        return response

    visitor_id = visitor_normalize_id(
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

    visitor_record(
        platform,
        visitor_id
    )

    return response


def visitor_stats_snapshot(days=7):
    days = max(1, min(int(days or 7), 31))
    now = visitor_stats_now()
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
        with visitor_stats_connect() as conn:
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


def telegram_visitor_stats_text():
    now, date_list, stats = visitor_stats_snapshot(7)
    today = date_list[0]
    current = stats[today]

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
            f"모바일 {item['mobile']['visitors']}명/{item['mobile']['views']}회"
        )

    lines.extend([
        "",
        "※ 방문자는 익명 브라우저 기준입니다.",
        "※ IP·이름·사번은 수집하지 않습니다.",
    ])

    return "\n".join(lines)


'''

if "# 익명 방문 통계 V5.45" in text:
    raise SystemExit("visitor analytics block already exists")
text = text.replace(marker, analytics_block + marker, 1)

# Hidden admin-only /stats command; no public menu exposure.
command_marker = '''    if command == "/help":
        telegram_send_message(
            chat_id,
            telegram_help_text(),
            reply_markup=
                telegram_main_menu()
        )
        return

'''
if command_marker not in text:
    raise SystemExit("telegram /help marker not found")

stats_command = command_marker + '''    if command == "/stats":
        # 관리자 개인채팅 전용. 일반 사용자는 통계 접근 불가.
        if not TELEGRAM_ADMIN_CHAT_ID:
            telegram_send_message(
                chat_id,
                (
                    "⚠️ 관리자 Chat ID가 설정되지 않았습니다.\n"
                    "Render의 TELEGRAM_ADMIN_CHAT_ID를 확인해주세요."
                )
            )
            return

        if str(chat_id) != str(TELEGRAM_ADMIN_CHAT_ID):
            return

        telegram_send_message(
            chat_id,
            telegram_visitor_stats_text()
        )
        return

'''
text = text.replace(command_marker, stats_command, 1)

path.write_text(text.rstrip() + "\n", encoding="utf-8")
print("V5.45 visitor stats patch applied")
