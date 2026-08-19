# ==========================================
# SBRateBot V4 Scheduler
# 매일 익일 00:30 금리 업데이트 실행
# + V5.45 익명 방문 통계 연결
# ==========================================


import os
import re
import sys
import hashlib
import sqlite3
import subprocess

from datetime import datetime, timedelta, timezone
from functools import wraps

from apscheduler.schedulers.background import BackgroundScheduler


# ==========================================
# 기본 경로
# ==========================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)


# ==========================================
# V5.45 익명 방문 통계
# - PC / 모바일 고유 브라우저 및 조회수 분리
# - IP / 이름 / 사번 / User-Agent 저장 안 함
# - Telegram /stats 는 관리자 개인채팅만 응답
# ==========================================

VISITOR_STATS_FILE = os.getenv(
    "SB_RATE_VISITOR_DB",
    os.path.join(
        BASE_DIR,
        "data",
        "visitor_stats.sqlite3"
    )
).strip()

VISITOR_COOKIE_NAME = "sbrate_vid"
VISITOR_COOKIE_MAX_AGE = 60 * 60 * 24 * 365
VISITOR_STATS_KST = timezone(
    timedelta(hours=9)
)
VISITOR_HASH_SALT = (
    os.getenv(
        "SB_RATE_VISITOR_SALT",
        "sbrate-anonymous-visitor-v1"
    ).strip()
    or "sbrate-anonymous-visitor-v1"
)


def _visitor_now():
    return datetime.now(
        VISITOR_STATS_KST
    )


def _visitor_db():
    parent = os.path.dirname(
        VISITOR_STATS_FILE
    )

    if parent:
        os.makedirs(
            parent,
            exist_ok=True
        )

    conn = sqlite3.connect(
        VISITOR_STATS_FILE,
        timeout=8
    )

    try:
        conn.execute(
            "PRAGMA journal_mode=WAL"
        )
        conn.execute(
            "PRAGMA synchronous=NORMAL"
        )
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


def _visitor_should_track(request):
    ua = str(
        request.headers.get(
            "User-Agent",
            ""
        )
    ).strip().lower()

    if not ua:
        return False

    # 자동 Keep Alive / Wake / crawler 요청은 이용자로 집계하지 않는다.
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

    return not any(
        token in ua
        for token in ignored
    )


def _visitor_normalize_id(value):
    value = str(
        value or ""
    ).strip()

    if re.fullmatch(
        r"[A-Za-z0-9_-]{16,80}",
        value
    ):
        return value

    return ""


def _visitor_hash(visitor_id):
    raw = (
        f"{VISITOR_HASH_SALT}:{visitor_id}"
        .encode("utf-8")
    )

    return hashlib.sha256(
        raw
    ).hexdigest()[:32]


def _visitor_record(
    platform,
    visitor_id
):
    if platform not in (
        "pc",
        "mobile"
    ):
        return

    now = _visitor_now()
    day = now.strftime(
        "%Y-%m-%d"
    )
    timestamp = now.strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    visitor_hash = _visitor_hash(
        visitor_id
    )
    cutoff = (
        now.date()
        - timedelta(days=45)
    ).isoformat()

    try:
        with _visitor_db() as conn:
            conn.execute(
                """
                INSERT INTO visitor_stats (
                    day,
                    platform,
                    visitor_hash,
                    pageviews,
                    first_seen,
                    last_seen
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

    except Exception as error:
        print(
            "VISITOR STATS RECORD ERROR:",
            error
        )


def _visitor_track_response(
    response,
    platform,
    request,
    make_response
):
    response = make_response(
        response
    )

    if not _visitor_should_track(
        request
    ):
        return response

    visitor_id = _visitor_normalize_id(
        request.cookies.get(
            VISITOR_COOKIE_NAME
        )
    )

    if not visitor_id:
        visitor_id = os.urandom(
            18
        ).hex()

        forwarded_proto = str(
            request.headers.get(
                "X-Forwarded-Proto",
                ""
            )
        ).lower()

        response.set_cookie(
            VISITOR_COOKIE_NAME,
            visitor_id,
            max_age=VISITOR_COOKIE_MAX_AGE,
            httponly=True,
            secure=(
                request.is_secure
                or forwarded_proto == "https"
            ),
            samesite="Lax",
            path="/"
        )

    _visitor_record(
        platform,
        visitor_id
    )

    return response


def _visitor_snapshot(days=7):
    days = max(
        1,
        min(
            int(days or 7),
            31
        )
    )

    now = _visitor_now()
    date_list = [
        (
            now.date()
            - timedelta(days=offset)
        ).isoformat()
        for offset in range(days)
    ]

    result = {
        day: {
            "pc": {
                "visitors": 0,
                "views": 0
            },
            "mobile": {
                "visitors": 0,
                "views": 0
            },
            "total": {
                "visitors": 0,
                "views": 0
            },
        }
        for day in date_list
    }

    try:
        with _visitor_db() as conn:
            placeholders = ",".join(
                "?"
                for _ in date_list
            )

            rows = conn.execute(
                f"""
                SELECT
                    day,
                    platform,
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
                SELECT
                    day,
                    COUNT(DISTINCT visitor_hash) AS visitors,
                    COALESCE(SUM(pageviews), 0) AS views
                FROM visitor_stats
                WHERE day IN ({placeholders})
                GROUP BY day
                """,
                date_list
            ).fetchall()

        for (
            day,
            platform,
            visitors,
            views
        ) in rows:
            if (
                day in result
                and platform in (
                    "pc",
                    "mobile"
                )
            ):
                result[day][platform] = {
                    "visitors": int(
                        visitors or 0
                    ),
                    "views": int(
                        views or 0
                    ),
                }

        for (
            day,
            visitors,
            views
        ) in totals:
            if day in result:
                result[day]["total"] = {
                    "visitors": int(
                        visitors or 0
                    ),
                    "views": int(
                        views or 0
                    ),
                }

    except Exception as error:
        print(
            "VISITOR STATS READ ERROR:",
            error
        )

    return now, date_list, result


def _visitor_stats_text():
    now, date_list, stats = (
        _visitor_snapshot(7)
    )

    today = date_list[0]
    current = stats[today]

    lines = [
        "📊 SBRate 이용현황",
        f"{now.strftime('%Y-%m-%d %H:%M')} KST",
        "",
        "오늘",
        (
            f"🖥 PC : "
            f"{current['pc']['visitors']}명 · "
            f"{current['pc']['views']}회"
        ),
        (
            f"📱 모바일 : "
            f"{current['mobile']['visitors']}명 · "
            f"{current['mobile']['views']}회"
        ),
        (
            f"👥 전체 : "
            f"{current['total']['visitors']}명 · "
            f"{current['total']['views']}회"
        ),
        "",
        "최근 7일",
    ]

    for day in date_list:
        item = stats[day]
        mmdd = day[5:].replace(
            "-",
            "/"
        )

        lines.append(
            f"{mmdd}  "
            f"PC {item['pc']['visitors']}명/"
            f"{item['pc']['views']}회 · "
            f"모바일 {item['mobile']['visitors']}명/"
            f"{item['mobile']['views']}회"
        )

    lines.extend([
        "",
        "※ 방문자는 익명 브라우저 기준입니다.",
        "※ IP·이름·사번은 수집하지 않습니다.",
    ])

    return "\n".join(
        lines
    )


def _find_running_app_module():
    # Gunicorn: app / 로컬 python app.py: __main__
    for name in (
        "app",
        "__main__"
    ):
        module = sys.modules.get(
            name
        )

        if (
            module is not None
            and hasattr(
                module,
                "app"
            )
        ):
            return module

    return None


def _install_visitor_stats_hooks():
    """
    app.py가 scheduler를 import하는 시점에는 PC/모바일/Telegram route가
    이미 등록되어 있다. 여기서 view function과 Telegram handler만 감싸
    대형 app.py를 수정하지 않고 통계를 연결한다.
    """
    app_module = (
        _find_running_app_module()
    )

    if app_module is None:
        print(
            "Visitor Stats: app module not found"
        )
        return

    if getattr(
        app_module,
        "_visitor_stats_hooks_installed",
        False
    ):
        return

    flask_app = getattr(
        app_module,
        "app",
        None
    )

    if flask_app is None:
        return

    try:
        from flask import (
            request,
            make_response
        )

        def wrap_view(
            endpoint,
            platform
        ):
            original = (
                flask_app.view_functions
                .get(endpoint)
            )

            if original is None:
                print(
                    "Visitor Stats endpoint missing:",
                    endpoint
                )
                return

            @wraps(original)
            def tracked(
                *args,
                **kwargs
            ):
                response = original(
                    *args,
                    **kwargs
                )

                return _visitor_track_response(
                    response,
                    platform,
                    request,
                    make_response
                )

            flask_app.view_functions[
                endpoint
            ] = tracked

        wrap_view(
            "index",
            "pc"
        )
        wrap_view(
            "mobile_dashboard",
            "mobile"
        )

        original_telegram_handler = getattr(
            app_module,
            "telegram_handle_message",
            None
        )

        if original_telegram_handler:
            @wraps(
                original_telegram_handler
            )
            def telegram_with_stats(
                message
            ):
                if isinstance(
                    message,
                    dict
                ):
                    chat = (
                        message.get(
                            "chat"
                        )
                        or {}
                    )
                    chat_id = chat.get(
                        "id"
                    )
                    text = str(
                        message.get(
                            "text",
                            ""
                        )
                    ).strip()
                    command = (
                        text.split()[0]
                        .split("@")[0]
                        .lower()
                        if text
                        else ""
                    )

                    if command == "/stats":
                        # 관리자 개인채팅에서만 통계를 반환한다.
                        admin_chat_id = str(
                            getattr(
                                app_module,
                                "TELEGRAM_ADMIN_CHAT_ID",
                                ""
                            )
                            or ""
                        ).strip()

                        is_private = (
                            str(
                                chat.get(
                                    "type",
                                    ""
                                )
                            ).lower()
                            == "private"
                        )

                        if (
                            is_private
                            and admin_chat_id
                            and str(chat_id)
                            == admin_chat_id
                        ):
                            app_module.telegram_send_message(
                                chat_id,
                                _visitor_stats_text()
                            )

                        return

                return original_telegram_handler(
                    message
                )

            app_module.telegram_handle_message = (
                telegram_with_stats
            )

        app_module._visitor_stats_hooks_installed = True

        print(
            "Visitor Stats V5.45 hooks installed"
        )

    except Exception as error:
        print(
            "Visitor Stats hook error:",
            error
        )


# ==========================================
# 크롤러 실행
# ==========================================

def run_crawler():

    print()
    print("=" * 60)
    print("SBRateBot 통합 데이터 업데이트 시작")
    print(datetime.now())
    print("=" * 60)

    jobs = [
        (
            "정기예금",
            os.path.join(
                BASE_DIR,
                "crawler",
                "fsb.py"
            )
        ),
        (
            "ISA / 퇴직연금(IRP)",
            os.path.join(
                BASE_DIR,
                "crawler",
                "pension_rates.py"
            )
        ),
    ]

    results = []

    for name, script_path in jobs:

        print()
        print("-" * 60)
        print(f"[{name}] 업데이트 시작")
        print("실행 파일:", script_path)

        if not os.path.exists(
            script_path
        ):
            print(
                f"[{name}] 실행 파일 없음 - 건너뜀"
            )
            results.append(
                (
                    name,
                    False,
                    "실행 파일 없음"
                )
            )
            continue

        try:
            subprocess.run(
                [
                    sys.executable,
                    script_path
                ],
                cwd=BASE_DIR,
                check=True
            )

            print(
                f"[{name}] 업데이트 완료"
            )
            results.append(
                (
                    name,
                    True,
                    "완료"
                )
            )

        except subprocess.CalledProcessError as error:
            print(
                f"[{name}] 업데이트 실패:",
                error
            )
            results.append(
                (
                    name,
                    False,
                    str(error)
                )
            )

        except Exception as error:
            print(
                f"[{name}] 업데이트 오류:",
                error
            )
            results.append(
                (
                    name,
                    False,
                    str(error)
                )
            )

    print()
    print("=" * 60)
    print("SBRateBot 통합 데이터 업데이트 결과")

    for (
        name,
        success,
        message
    ) in results:
        status = (
            "OK"
            if success
            else "FAIL"
        )
        print(
            f"{name}: {status} ({message})"
        )

    print(
        "완료 시각:",
        datetime.now()
    )
    print("=" * 60)


# ==========================================
# Scheduler
# ==========================================

scheduler = BackgroundScheduler(
    timezone="Asia/Seoul"
)


def start_scheduler():

    scheduler.add_job(
        run_crawler,
        "cron",
        hour=0,
        minute=30,
        id="daily_sbratebot_update",
        replace_existing=True
    )

    scheduler.start()

    print()
    print(
        "SBRateBot Scheduler 시작"
    )
    print(
        "업데이트 시간 : 매일 00:30 "
        "(정기예금 → ISA/퇴직연금 순차 실행)"
    )


# app.py import가 끝나기 직전 익명 방문통계 hook 설치.
_install_visitor_stats_hooks()
