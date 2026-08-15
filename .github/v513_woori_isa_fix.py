from pathlib import Path
import json
import re

collector_path=Path('crawler/pension_rates.py')
source_map_path=Path('data/pension_source_map.json')

text=collector_path.read_text(encoding='utf-8')

pattern=re.compile(r'''def woori_isa\(bank,kind,cfg\):\n.*?\n(?=def woori_irp\()''',re.S)
replacement=r'''WOORI_ISA_URL=(
    "https://m.woorisavingsbank.com/product/deposite/view.do"
    "?depositeOrder=high&page=1&prdSn=315"
)
WOORI_ISA_URLS=(
    "https://www.woorisavingsbank.com/product/deposite/view.do?depositeOrder=high&page=1&prdSn=315",
    WOORI_ISA_URL,
)
WOORI_ISA_VERIFIED_FALLBACK={
    "rates":{"3m":2.40,"6m":3.70,"12m":3.70,"24m":3.30,"36m":3.00},
    "disclosure_date":"2026-07-31",
}


def _woori_isa_parse_official(html,final_url,bank,kind,cfg):
    soup=BeautifulSoup(html,"html.parser")
    text_value=clean(" ".join(soup.stripped_strings))

    if "ISA 정기예금" not in text_value:
        raise ValueError("우리금융 ISA 공식 상품페이지 검증 실패")

    start=text_value.find("금리안내")
    if start < 0:
        raise ValueError("우리금융 ISA 금리안내 영역 미확인")

    end=text_value.find("중도해지이율",start)
    if end < 0:
        end=min(len(text_value),start+2200)

    section=text_value[start:end]
    rates={f"{p}m":None for p in ISA_PERIODS}

    for period in ISA_PERIODS:
        m=re.search(
            rf"(?<!\d){period}\s*개월\s+"
            rf"(\d{{1,2}}(?:\.\d{{1,4}})?)\s*%",
            section,
            re.I,
        )
        if not m:
            continue

        rate=float(m.group(1))
        if 0 <= rate <= 10:
            rates[f"{period}m"]=rate

    found=sum(value is not None for value in rates.values())
    if rates.get("12m") is None:
        raise ValueError("우리금융 ISA 12개월 약정금리 미확인")

    o=blank(
        bank,
        kind,
        cfg,
        "verified_official" if found==len(ISA_PERIODS) else "verified_official_partial",
    )
    o["product"]="ISA 정기예금"
    o["rates"]=rates
    o["source_url"]=final_url
    o["collector"]="woori_isa_official_product_page"

    date_match=re.search(
        r"기준\s*:\s*세전\s*,\s*연이율\s*,\s*"
        r"(\d{4})[.](\d{1,2})[.](\d{1,2})",
        section,
        re.I,
    )

    if date_match:
        year,month,day=map(int,date_match.groups())
        o["disclosure_date"]=f"{year:04d}-{month:02d}-{day:02d}"
        o["reference_date"]=o["disclosure_date"]
        o["disclosure_date_source"]="woori_isa_rate_table_reference_date"
        o["disclosure_date_url"]=final_url

    o["note"]=(
        "우리금융저축은행 공식 ISA 정기예금 상품페이지의 금리안내 표 자동수집. "
        "기간별 단리(이율) 사용, 복리 수익률/중도해지이율 제외."
    )
    return o


def woori_isa(bank,kind,cfg):
    """
    우리금융저축은행 ISA 정기예금.

    1) 공식 상품페이지를 우선 실시간 수집한다.
    2) GitHub Actions 네트워크에서 우리금융 도메인이 일시 차단/timeout이면
       마지막으로 공식 페이지에서 검증한 기준값을 사용한다.
    3) fallback 사용 여부와 기준일을 status/note에 명시해 새 데이터처럼 위장하지 않는다.
    """
    errors=[]

    for url in WOORI_ISA_URLS:
        try:
            r=S.get(
                url,
                timeout=8,
                verify=False,
                allow_redirects=True,
            )
            r.raise_for_status()
            if not r.encoding:
                r.encoding=r.apparent_encoding
            return _woori_isa_parse_official(
                r.text,
                r.url,
                bank,
                kind,
                cfg,
            )
        except Exception as error:
            errors.append(f"{url}: {error}")

    fallback=WOORI_ISA_VERIFIED_FALLBACK
    o=blank(bank,kind,cfg,"verified_official_fallback")
    o["product"]="ISA 정기예금"
    o["rates"]=dict(fallback["rates"])
    o["source_url"]=WOORI_ISA_URL
    o["collector"]="woori_isa_verified_fallback"
    o["disclosure_date"]=fallback["disclosure_date"]
    o["reference_date"]=fallback["disclosure_date"]
    o["disclosure_date_source"]="verified_official_fallback_date"
    o["disclosure_date_url"]=WOORI_ISA_URL
    o["fetch_error"]=" | ".join(errors)
    o["note"]=(
        "우리금융 공식 ISA 상품페이지 접속 실패로 마지막 검증 공식값 유지. "
        "공식 금리안내 기준일 2026-07-31: "
        "3개월 2.40%, 6개월 3.70%, 12개월 3.70%, 24개월 3.30%, 36개월 3.00%. "
        "공식 페이지 접속이 복구되면 자동수집값을 우선 사용."
    )
    return o

'''

text,new_count=pattern.subn(replacement,text,count=1)
if new_count != 1:
    raise SystemExit(f'woori_isa function replacement failed: {new_count}')

old='''    if category=="ISA":\n        url="https://www.woorisavingsbank.com/deposite-interest/view.do"'''
new='''    if category=="ISA":\n        url=WOORI_ISA_URL'''
if old not in text:
    raise SystemExit('collect_woori_disclosure_date ISA URL marker not found')
text=text.replace(old,new,1)

# Preserve a specific collector-provided date source instead of overwriting it
# with the generic existing_collector label.
old_source='''        else:\n            item["disclosure_date_source"]="existing_collector"\n            return item'''
new_source='''        else:\n            if not item.get("disclosure_date_source"):\n                item["disclosure_date_source"]="existing_collector"\n            return item'''
if old_source not in text:
    raise SystemExit('disclosure source preservation marker not found')
text=text.replace(old_source,new_source,1)

collector_path.write_text(text,encoding='utf-8')

source_map=json.loads(source_map_path.read_text(encoding='utf-8'))
woori_isa=source_map['banks']['우리금융']['isa']
woori_isa['source_type']='official_product'
woori_isa['url']='https://m.woorisavingsbank.com/product/deposite/view.do?depositeOrder=high&page=1&prdSn=315'
woori_isa['note']='공식 ISA 정기예금 상품페이지 금리안내 표 우선 자동수집. GitHub 네트워크 timeout 시 마지막 공식 검증값과 기준일을 명시해 유지.'
source_map_path.write_text(json.dumps(source_map,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Woori ISA live-first + verified fallback parser/source map patched')
