from pathlib import Path

path=Path('crawler/pension_rates.py')
text=path.read_text(encoding='utf-8')

marker='''def main():\n    mp=load(MAP)\n    a=[]\n    b=[]\n    disclosure_banks=load_irp_disclosure()'''

insert='''def _rates_have_value(item):
    if not isinstance(item,dict):
        return False

    rates=item.get("rates")
    if not isinstance(rates,dict):
        return False

    return any(
        isinstance(value,(int,float)) and 0 < value <= 20
        for value in rates.values()
    )


def _previous_rows_by_bank(path):
    if not path.exists():
        return {}

    try:
        rows=load(path)
    except Exception:
        return {}

    if not isinstance(rows,list):
        return {}

    result={}
    for row in rows:
        if not isinstance(row,dict):
            continue
        bank=clean(row.get("bank"))
        if bank:
            result[bank]=row

    return result


def retain_last_known_good_on_fetch_error(current,previous):
    """
    일시적인 공식사이트 timeout/파싱실패가 기존 정상금리를 null로
    덮어쓰는 것을 방지한다.

    적용 조건은 매우 제한적이다.
    - 이번 결과 status가 fetch_or_parse_error / rate_not_found
    - 이번 결과에 유효 금리가 하나도 없음
    - 직전 저장값에는 유효 금리가 있음

    정상 수집, 실제 금리 변경, 의도적인 rate_pending/research_pending에는
    관여하지 않는다. 보존 시 stale 상태와 마지막 실패 원인을 명시한다.
    """
    if not isinstance(current,dict):
        return current

    status=clean(current.get("status"))
    if status not in ("fetch_or_parse_error","rate_not_found"):
        return current

    if _rates_have_value(current):
        return current

    if not isinstance(previous,dict) or not _rates_have_value(previous):
        return current

    retained=dict(previous)
    retained["status"]="stale_retained_after_fetch_error"
    retained["stale"]=True
    retained["retained_last_good"]=True
    retained["last_fetch_status"]=status
    retained["last_attempt_at"]=(
        current.get("collected_at")
        or current.get("updated_at")
        or datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M:%S")
    )

    error_text=clean(
        current.get("error")
        or current.get("fetch_error")
        or current.get("note")
    )
    if error_text:
        retained["last_fetch_error"]=error_text

    previous_note=clean(retained.get("note"))
    retained["note"]=(
        previous_note
        + (" | " if previous_note else "")
        + "이번 공식소스 수집 실패로 직전 정상금리 유지"
    )

    return retained


def main():
    mp=load(MAP)
    a=[]
    b=[]
    disclosure_banks=load_irp_disclosure()
    previous_isa=_previous_rows_by_bank(ISA)
    previous_irp=_previous_rows_by_bank(IRP)'''

if marker not in text:
    raise SystemExit('main marker not found')
text=text.replace(marker,insert,1)

old='''        # IRP 최신 적용월 / IRP 기준 메타데이터 최종 확정\n        y=apply_irp_latest_month_metadata(y)\n\n        # 한국투자 공시일은 공식 자동수집 안정성이 확보될 때까지 공란 유지.'''
new='''        # IRP 최신 적용월 / IRP 기준 메타데이터 최종 확정\n        y=apply_irp_latest_month_metadata(y)\n\n        # 공식사이트 일시 장애가 직전 정상 데이터를 null로 덮어쓰지 않도록\n        # '실패 + 신규 유효금리 0건'인 경우에만 마지막 정상값을 보존한다.\n        x=retain_last_known_good_on_fetch_error(\n            x,\n            previous_isa.get(bank)\n        )\n        y=retain_last_known_good_on_fetch_error(\n            y,\n            previous_irp.get(bank)\n        )\n\n        # 한국투자 공시일은 공식 자동수집 안정성이 확보될 때까지 공란 유지.'''

if old not in text:
    raise SystemExit('post-enrichment marker not found')
text=text.replace(old,new,1)

path.write_text(text,encoding='utf-8')
print('Collector last-known-good resilience applied')
