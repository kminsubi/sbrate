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


def woori_isa(bank,kind,cfg):
    """
    우리금융저축은행 ISA 정기예금 공식 상품페이지 실시간 수집.

    금리안내 영역의 단리(이율) 열만 사용하고
    복리 수익률 / 중도해지이율은 제외한다.
    """
    try:
        html,final_url=fetch(WOORI_ISA_URL)
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
                rf"(?<!\\d){period}\\s*개월\\s+"
                rf"(\\d{{1,2}}(?:\\.\\d{{1,4}})?)\\s*%",
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

        status=(
            "verified_official"
            if found==len(ISA_PERIODS)
            else "verified_official_partial"
        )

        o=blank(bank,kind,cfg,status)
        o["product"]="ISA 정기예금"
        o["rates"]=rates
        o["source_url"]=final_url
        o["collector"]="woori_isa_official_product_page"

        date_match=re.search(
            r"기준\\s*:\\s*세전\\s*,\\s*연이율\\s*,\\s*"
            r"(\\d{4})[.](\\d{1,2})[.](\\d{1,2})",
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

    except Exception as error:
        o=blank(bank,kind,cfg,"fetch_or_parse_error")
        o["source_url"]=WOORI_ISA_URL
        o["error"]=str(error)
        o["note"]=f"우리금융 ISA 공식 상품페이지 수집 실패: {error}"
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
collector_path.write_text(text,encoding='utf-8')

source_map=json.loads(source_map_path.read_text(encoding='utf-8'))
woori_isa=source_map['banks']['우리금융']['isa']
woori_isa['source_type']='official_product'
woori_isa['url']='https://m.woorisavingsbank.com/product/deposite/view.do?depositeOrder=high&page=1&prdSn=315'
woori_isa['note']='공식 ISA 정기예금 상품페이지 금리안내 표에서 기간별 단리(이율) 및 기준일 직접 수집.'
source_map_path.write_text(json.dumps(source_map,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Woori ISA live parser/source map patched')
