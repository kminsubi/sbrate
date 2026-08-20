# ==========================================
# SBRate Verified Visitor Stats V2
# - Count a visit only after the page is visibly rendered for 3 seconds
# - Exclude simple GET previews/security scanners/keep-alive traffic
# - PC/mobile resolved at confirmation time without storing User-Agent/IP
# - Separate Redis namespace from legacy request-based counters
# ==========================================

import os
import sqlite3
import sys
from datetime import timedelta

import visitor_stats as legacy


VERIFIED_PREFIX = "sbrate:visitor:v2"
VERIFIED_TABLE = "visitor_stats_verified"
VERIFIED_VISIBLE_MS = 3000


def _find_running_app_module():
    for name in ("app", "__main__"):
        module = sys.modules.get(name)
        if module is not None and hasattr(module, "app"):
            return module
    return None


def _redis_keys(day, platform=None):
    if platform:
        return {
            "visitors": f"{VERIFIED_PREFIX}:{day}:{platform}:visitors",
            "views": f"{VERIFIED_PREFIX}:{day}:{platform}:views",
        }
    return {"all": f"{VERIFIED_PREFIX}:{day}:all:visitors"}


def _record_upstash(platform, visitor_hash, day):
    keys = _redis_keys(day, platform)
    all_key = _redis_keys(day)["all"]
    commands = [
        ["SADD", keys["visitors"], visitor_hash],
        ["SADD", all_key, visitor_hash],
        ["INCR", keys["views"]],
        ["EXPIRE", keys["visitors"], legacy.VISITOR_RETENTION_SECONDS],
        ["EXPIRE", all_key, legacy.VISITOR_RETENTION_SECONDS],
        ["EXPIRE", keys["views"], legacy.VISITOR_RETENTION_SECONDS],
    ]
    legacy._upstash_pipeline(commands)


def _verified_db():
    parent = os.path.dirname(legacy.VISITOR_STATS_FILE)
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(legacy.VISITOR_STATS_FILE, timeout=8)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
    except Exception:
        pass
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {VERIFIED_TABLE} (
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


def _record_sqlite(platform, visitor_hash, now):
    day = now.strftime("%Y-%m-%d")
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    cutoff = (now.date() - timedelta(days=45)).isoformat()
    with _verified_db() as conn:
        conn.execute(
            f"""
            INSERT INTO {VERIFIED_TABLE} (
                day, platform, visitor_hash,
                pageviews, first_seen, last_seen
            ) VALUES (?, ?, ?, 1, ?, ?)
            ON CONFLICT(day, platform, visitor_hash)
            DO UPDATE SET
                pageviews = pageviews + 1,
                last_seen = excluded.last_seen
            """,
            (day, platform, visitor_hash, timestamp, timestamp),
        )
        conn.execute(
            f"DELETE FROM {VERIFIED_TABLE} WHERE day < ?",
            (cutoff,),
        )


def _record_verified(platform, visitor_id):
    if platform not in ("pc", "mobile"):
        return False
    now = legacy._now()
    day = now.strftime("%Y-%m-%d")
    visitor_hash = legacy._hash_visitor_id(visitor_id)

    if legacy._upstash_enabled():
        try:
            _record_upstash(platform, visitor_hash, day)
            return True
        except Exception as error:
            print("VERIFIED VISITOR UPSTASH RECORD ERROR:", error)

    try:
        _record_sqlite(platform, visitor_hash, now)
        return True
    except Exception as error:
        print("VERIFIED VISITOR SQLITE RECORD ERROR:", error)
        return False


def _is_mobile_request(request, page_path=""):
    if str(page_path or "").strip() == "/mobile":
        return True

    hint = str(request.headers.get("Sec-CH-UA-Mobile", "")).strip()
    if hint == "?1":
        return True

    ua = str(request.headers.get("User-Agent", "")).lower()
    mobile_tokens = (
        "iphone", "ipod", "ipad", "android", "mobile",
        "windows phone", "opera mini", "opera mobi", "samsungbrowser",
    )
    return any(token in ua for token in mobile_tokens)


def _cookie_only_track_response(response, platform, request, make_response):
    """Issue/retain anonymous cookie, but do not count the HTML GET itself."""
    response = make_response(response)

    if not legacy._should_track(request):
        return response

    visitor_id = legacy._normalize_visitor_id(
        request.cookies.get(legacy.VISITOR_COOKIE_NAME)
    )
    if visitor_id:
        return response

    visitor_id = os.urandom(18).hex()
    forwarded_proto = str(
        request.headers.get("X-Forwarded-Proto", "")
    ).lower()
    response.set_cookie(
        legacy.VISITOR_COOKIE_NAME,
        visitor_id,
        max_age=legacy.VISITOR_COOKIE_MAX_AGE,
        httponly=True,
        secure=(request.is_secure or forwarded_proto == "https"),
        samesite="Lax",
        path="/",
    )
    return response


def _snapshot_upstash(days):
    now, date_list, result = legacy._empty_snapshot(days)
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

    payload = legacy._upstash_pipeline(commands)
    cursor = 0
    for day in date_list:
        pc_visitors = int(legacy._redis_result(payload[cursor], 0) or 0)
        pc_views = int(legacy._redis_result(payload[cursor + 1], 0) or 0)
        mobile_visitors = int(legacy._redis_result(payload[cursor + 2], 0) or 0)
        mobile_views = int(legacy._redis_result(payload[cursor + 3], 0) or 0)
        total_visitors = int(legacy._redis_result(payload[cursor + 4], 0) or 0)
        cursor += 5
        result[day]["pc"] = {"visitors": pc_visitors, "views": pc_views}
        result[day]["mobile"] = {"visitors": mobile_visitors, "views": mobile_views}
        result[day]["total"] = {
            "visitors": total_visitors,
            "views": pc_views + mobile_views,
        }
    return now, date_list, result, "Upstash (영구)"


def _snapshot_sqlite(days):
    now, date_list, result = legacy._empty_snapshot(days)
    with _verified_db() as conn:
        placeholders = ",".join("?" for _ in date_list)
        rows = conn.execute(
            f"""
            SELECT day, platform, COUNT(*) AS visitors,
                   COALESCE(SUM(pageviews), 0) AS views
            FROM {VERIFIED_TABLE}
            WHERE day IN ({placeholders})
            GROUP BY day, platform
            """,
            date_list,
        ).fetchall()
        totals = conn.execute(
            f"""
            SELECT day, COUNT(DISTINCT visitor_hash) AS visitors,
                   COALESCE(SUM(pageviews), 0) AS views
            FROM {VERIFIED_TABLE}
            WHERE day IN ({placeholders})
            GROUP BY day
            """,
            date_list,
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
    return now, date_list, result, "SQLite (임시)"


def _snapshot_verified(days=7):
    days = max(1, min(int(days or 7), 31))
    if legacy._upstash_enabled():
        try:
            return _snapshot_upstash(days)
        except Exception as error:
            print("VERIFIED VISITOR UPSTASH READ ERROR:", error)
    try:
        return _snapshot_sqlite(days)
    except Exception as error:
        print("VERIFIED VISITOR SQLITE READ ERROR:", error)
        now, date_list, result = legacy._empty_snapshot(days)
        return now, date_list, result, "저장소 오류"


def visitor_stats_text_verified():
    now, date_list, stats, backend = _snapshot_verified(7)
    current = stats[date_list[0]]
    lines = [
        "📊 SBRate 이용현황",
        f"{now.strftime('%Y-%m-%d %H:%M')} KST",
        f"저장소 : {backend}",
        "집계기준 : 실사용 확인 (3초 이상 화면 표시)",
        "",
        "오늘",
        f"🖥 PC : {current['pc']['visitors']}명 · {current['pc']['views']}회",
        f"📱 모바일 : {current['mobile']['visitors']}명 · {current['mobile']['views']}회",
        f"👥 전체 : {current['total']['visitors']}명 · {current['total']['views']}회",
        "",
        "최근 7일",
    ]
    for day in date_list:
        item = stats[day]
        mmdd = day[5:].replace("-", "/")
        lines.append(
            f"{mmdd}  PC {item['pc']['visitors']}명/{item['pc']['views']}회 · "
            f"모바일 {item['mobile']['visitors']}명/{item['mobile']['views']}회"
        )
    lines.extend([
        "",
        "※ 단순 URL 조회·링크 미리보기·Keep Alive는 실사용으로 집계하지 않습니다.",
        "※ 방문자는 익명 브라우저 기준이며 IP·이름·사번은 수집하지 않습니다.",
        "※ 새 실사용 집계 방식 적용 이후 데이터입니다.",
    ])
    return "\n".join(lines)


VERIFIED_SCRIPT = r'''<script data-sbrate-verified-visitor="v2">
(()=>{
  'use strict';
  if(window.__sbrateVerifiedVisitorV2) return;
  window.__sbrateVerifiedVisitorV2=true;
  let sent=false, timer=null;

  const eligible=()=>{
    if(sent) return false;
    if(document.prerendering) return false;
    if(document.visibilityState!=='visible') return false;
    if(navigator.webdriver===true) return false;
    if(!navigator.cookieEnabled) return false;
    return true;
  };

  const confirm=()=>{
    if(!eligible()) return;
    sent=true;
    fetch('/api/visitor/confirm-v2',{
      method:'POST',
      credentials:'same-origin',
      keepalive:true,
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({page:location.pathname})
    }).catch(()=>{sent=false;});
  };

  const arm=()=>{
    if(timer) clearTimeout(timer);
    if(!eligible()) return;
    requestAnimationFrame(()=>{
      requestAnimationFrame(()=>{
        timer=setTimeout(confirm,''' + str(VERIFIED_VISIBLE_MS) + r''');
      });
    });
  };

  document.addEventListener('visibilitychange',()=>{
    if(document.visibilityState==='visible') arm();
    else if(timer){clearTimeout(timer);timer=null;}
  });

  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded',arm,{once:true});
  }else{
    arm();
  }
})();
</script>'''


def install_verified_visitor_tracking():
    app_module = _find_running_app_module()
    if app_module is None:
        print("Verified Visitor Stats: app module not found")
        return False
    if getattr(app_module, "_verified_visitor_stats_installed", False):
        return True

    app = app_module.app
    from flask import jsonify, request

    # Replace request-based counting with cookie issuance only.
    legacy._track_response = _cookie_only_track_response

    # Make /stats read only the verified V2 namespace.
    legacy._snapshot = _snapshot_verified
    legacy.visitor_stats_text = visitor_stats_text_verified

    if "visitor_stats_verified_confirm" not in app.view_functions:
        def confirm():
            if not legacy._should_track(request):
                return jsonify({"ok": False, "ignored": "automated"}), 202

            visitor_id = legacy._normalize_visitor_id(
                request.cookies.get(legacy.VISITOR_COOKIE_NAME)
            )
            if not visitor_id:
                return jsonify({"ok": False, "ignored": "cookie_missing"}), 202

            payload = request.get_json(silent=True) or {}
            page_path = str(payload.get("page") or "").strip()
            platform = "mobile" if _is_mobile_request(request, page_path) else "pc"
            ok = _record_verified(platform, visitor_id)
            return jsonify({"ok": bool(ok), "platform": platform}), (200 if ok else 503)

        app.add_url_rule(
            "/api/visitor/confirm-v2",
            "visitor_stats_verified_confirm",
            confirm,
            methods=["POST"],
        )

    @app.after_request
    def inject_verified_visitor_script(response):
        try:
            if (
                request.path in ("/", "/mobile")
                and response.status_code == 200
                and "text/html" in str(response.content_type or "")
            ):
                html = response.get_data(as_text=True)
                if "data-sbrate-verified-visitor=\"v2\"" not in html:
                    html = html.replace("</body>", VERIFIED_SCRIPT + "\n</body>", 1)
                    response.set_data(html)
                    response.headers.pop("Content-Length", None)
        except Exception as error:
            print("VERIFIED VISITOR SCRIPT INJECT ERROR:", error)
        return response

    app_module._verified_visitor_stats_installed = True
    print("Verified Visitor Stats V2 installed")
    return True
