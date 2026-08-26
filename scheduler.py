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
from fisis_history_patch import install_fisis_history_patch
import fisis_intelligence_store
from fisis_profitability_period_patch import install_fisis_profitability_period_patch
from fisis_quality_patch import install_fisis_quality_patch
from fisis_region_patch import install_fisis_region_patch
from management_export_v2 import install_management_export_v2
from management_intelligence import install_management_intelligence
from management_report import install_management_report
from management_report_auto_update import check_latest_quarter, install_management_report_auto_update
from management_report_v4_runtime import install_management_report_v4_runtime
from management_report_v5_runtime import install_management_report_v5_runtime
from rate_simulator import install_rate_simulator
from rate_simulator_v2 import install_rate_simulator_v2
from rate_simulator_v2_polish import install_rate_simulator_v2_polish
from rate_simulation_v3_runtime import install_rate_simulation_v3_runtime
from rate_simulation_v6 import install_rate_simulation_v6
from visitor_platform import enable_mobile_platform_detection
from visitor_stats import install_visitor_stats_hooks
from visitor_stats_verified import install_verified_visitor_tracking


BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def run_crawler():
    print()
    print("=" * 60)
    print("SBRateBot 통합 데이터 업데이트 시작")
    print(datetime.now())
    print("=" * 60)
    jobs = [
        ("정기예금", os.path.join(BASE_DIR, "crawler", "fsb.py")),
        ("ISA / 퇴직연금(IRP)", os.path.join(BASE_DIR, "crawler", "pension_rates.py")),
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
            subprocess.run([sys.executable, script_path], cwd=BASE_DIR, check=True)
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
        print(f"{name}: {'OK' if success else 'FAIL'} ({message})")
    print("완료 시각:", datetime.now())
    print("=" * 60)


scheduler = BackgroundScheduler(timezone="Asia/Seoul")


def run_fisis_quarter_check():
    try:
        # Scheduled runs finish the lightweight 79-bank publication probe in
        # this scheduler job.  This avoids losing a daemon thread between
        # Render workers/restarts and persists the result to Upstash.
        result = check_latest_quarter(force_probe=False, wait=True)
        print("FISIS latest-quarter check:", result)
    except Exception as e:
        print("FISIS latest-quarter check error:", e)


def start_scheduler():
    scheduler.add_job(
        run_crawler,
        "cron",
        hour=0,
        minute=30,
        id="daily_sbratebot_update",
        replace_existing=True,
    )
    scheduler.add_job(
        run_fisis_quarter_check,
        "cron",
        hour="7,19",
        minute=10,
        id="fisis_quarter_check",
        replace_existing=True,
    )
    scheduler.start()
    print()
    print("SBRateBot Scheduler 시작")
    print("업데이트 시간 : 매일 00:30 (정기예금 → ISA/퇴직연금 순차 실행)")
    print("FISIS 최신분기 확인 : 매일 07:10 / 19:10")


enable_mobile_platform_detection()
install_verified_visitor_tracking()
install_visitor_stats_hooks()
install_data_quality_endpoint()

# after_request는 등록 역순으로 실행된다. V5를 먼저 등록해
# management_report -> V4 -> V5 순서로 최종 HTML을 보정한다.
install_management_report_v5_runtime()
install_management_report_v4_runtime()
install_management_report()

# 기본 FISIS provider에는 검증된 이력/권역/품질 규칙만 적용한다.
install_fisis_history_patch()
install_fisis_region_patch()
install_fisis_quality_patch()
install_management_report_auto_update()

# 확장 지표는 기존 경영현황 캐시와 분리한다. SE010 수익성 표는
# FISIS가 term=Q를 지원하지 않으므로 분기 화면에서 ROA/ROE를 추정하지
# 않고 실제 분기 손익지표만 사용하도록 주기 패치를 먼저 적용한다.
import fisis_management as _fm
fisis_intelligence_store._base_store = lambda: _fm.get_management_store(trigger_refresh=False) or {}
install_fisis_profitability_period_patch()
fisis_intelligence_store.install_fisis_intelligence_store()
install_management_intelligence()
install_management_export_v2()

install_rate_simulator()
install_rate_simulator_v2()
install_rate_simulator_v2_polish()
install_rate_simulation_v6()
install_rate_simulation_v3_runtime()
