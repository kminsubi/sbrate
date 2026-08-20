# ==========================================
# SBRateBot V4 Scheduler
# 매일 익일 00:30 금리 업데이트 실행
# ==========================================


import os
import subprocess
import sys

from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from data_quality_runtime import install_data_quality_endpoint
from rate_simulator import install_rate_simulator
from rate_simulator_v2 import install_rate_simulator_v2
from rate_simulator_v2_polish import install_rate_simulator_v2_polish
from rate_simulation_v3_runtime import install_rate_simulation_v3_runtime
from rate_simulation_v6 import install_rate_simulation_v6
from visitor_platform import enable_mobile_platform_detection
from visitor_stats import install_visitor_stats_hooks
from visitor_stats_verified import install_verified_visitor_tracking


# ==========================================
# 기본 경로
# ==========================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
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
            os.path.join(BASE_DIR, "crawler", "fsb.py")
        ),
        (
            "ISA / 퇴직연금(IRP)",
            os.path.join(BASE_DIR, "crawler", "pension_rates.py")
        ),
    ]

    results = []

    for name, script_path in jobs:

        print()
        print("-" * 60)
        print(f"[{name}] 업데이트 시작")
        print("실행 파일:", script_path)

        if not os.path.exists(script_path):
            print(f"[{name}] 실행 파일 없음 - 건너뜀")
            results.append((name, False, "실행 파일 없음"))
            continue

        try:
            subprocess.run(
                [sys.executable, script_path],
                cwd=BASE_DIR,
                check=True
            )

            print(f"[{name}] 업데이트 완료")
            results.append((name, True, "완료"))

        except subprocess.CalledProcessError as e:
            print(f"[{name}] 업데이트 실패:", e)
            results.append((name, False, str(e)))

        except Exception as e:
            print(f"[{name}] 업데이트 오류:", e)
            results.append((name, False, str(e)))

    print()
    print("=" * 60)
    print("SBRateBot 통합 데이터 업데이트 결과")

    for name, success, message in results:
        status = "OK" if success else "FAIL"
        print(f"{name}: {status} ({message})")

    print("완료 시각:", datetime.now())
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
        "업데이트 시간 : 매일 00:30 (정기예금 → ISA/퇴직연금 순차 실행)"
    )


# app.py가 scheduler를 import하는 시점에 PC/모바일/Telegram route는
# 이미 등록되어 있으므로 런타임 hook/endpoint를 연결한다.
# 휴대폰이 루트(/) 주소로 접속해도 실제 기기 기준으로 모바일 판별한다.
# 단순 HTML 요청은 방문자로 확정하지 않고, 실제 화면이 3초 이상
# 표시된 브라우저만 Verified Visitor V2에서 실사용으로 집계한다.
enable_mobile_platform_detection()
install_verified_visitor_tracking()
install_visitor_stats_hooks()
install_data_quality_endpoint()
install_rate_simulator()
install_rate_simulator_v2()
install_rate_simulator_v2_polish()
install_rate_simulation_v6()
install_rate_simulation_v3_runtime()
