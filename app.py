# ===================================
# SBRateBot V4 app.py
# 1/4
# ===================================


from flask import Flask, render_template, jsonify, request

from ai.gemini import ask_gemini
from prompt import get_prompt, detect_prompt_type

import json
import os
import re
import hashlib
import threading
import requests as http_requests
from datetime import datetime



app = Flask(__name__)


# -------------------------------
# Dashboard
# -------------------------------

@app.route("/")
def index():

    return render_template(
        "index.html"
    )




# -------------------------------
# Mobile Dashboard V1
# -------------------------------

@app.route("/mobile")
def mobile_dashboard():
    return render_template(
        "mobile.html"
    )


# -------------------------------
# 기본 경로 설정
# -------------------------------


BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)



DATA_FILE = os.path.join(
    BASE_DIR,
    "data",
    "latest_rates.json"
)


PREVIOUS_DATA_FILE = os.path.join(
    BASE_DIR,
    "data",
    "previous_rates.json"
)



# -------------------------------
# ISA / 퇴직연금 데이터 파일 V5
# -------------------------------

ISA_DATA_FILE = os.path.join(
    BASE_DIR,
    "data",
    "isa_rates.json"
)

IRP_DATA_FILE = os.path.join(
    BASE_DIR,
    "data",
    "irp_rates.json"
)


# -------------------------------
# 기간 설정
# -------------------------------


PERIOD_MAP = {

    "1개월": "1",
    "3개월": "3",
    "6개월": "6",
    "12개월": "12",
    "24개월": "24",
    "36개월": "36"

}



# 금융지주 계열 저축은행

FINANCIAL_BANKS = [

    "우리금융저축은행",
    "신한저축은행",
    "하나저축은행",
    "KB저축은행"

]



# -------------------------------
# 데이터 로드
# -------------------------------


def load_rates():


    try:


        with open(

            DATA_FILE,

            "r",

            encoding="utf-8"

        ) as f:


            data = json.load(f)



        if isinstance(data, list):


            return [

                x

                for x in data

                if isinstance(x, dict)

            ]



        return []



    except Exception:


        return []




# -------------------------------
# 전일 데이터 로드
# -------------------------------

def load_previous_rates():

    try:
        with open(
            PREVIOUS_DATA_FILE,
            "r",
            encoding="utf-8"
        ) as f:
            data = json.load(f)

        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]

        if isinstance(data, dict):
            for key in ["REC", "data", "items", "rates"]:
                value = data.get(key)
                if isinstance(value, list):
                    return [x for x in value if isinstance(x, dict)]

        return []

    except Exception:
        return []


# -------------------------------
# ISA / 퇴직연금 데이터 로드 V5
# -------------------------------

def load_pension_rate_file(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]

        if isinstance(data, dict):
            for key in ["data", "items", "rates", "REC"]:
                value = data.get(key)
                if isinstance(value, list):
                    return [x for x in value if isinstance(x, dict)]

        return []

    except Exception as e:
        print("ISA/IRP DATA LOAD ERROR:", file_path, e)
        return []


def normalize_pension_bank_name(value):
    name = str(value or "").strip()

    if not name:
        return ""

    if "저축은행" in name:
        return name

    return name + "저축은행"


def pension_rate_value(row, month):
    rates = row.get("rates", {})

    if not isinstance(rates, dict):
        return None

    value = rates.get(f"{month}m")

    if value in [None, "", "-"]:
        return None

    try:
        return float(value)
    except Exception:
        return None


def build_pension_products(file_path, category):
    rows = load_pension_rate_file(file_path)
    result = []

    for row in rows:
        bank = normalize_pension_bank_name(
            row.get("bank")
            or row.get("bank_name")
            or ""
        )

        product = str(
            row.get("product")
            or row.get("product_name")
            or ""
        ).strip()

        if not bank:
            continue

        rates = {}

        for month in [3, 6, 12, 24, 36]:
            rates[f"{month}m"] = pension_rate_value(row, month)

        result.append({
            "category": category,
            "bank": bank,
            "product": product,
            "rates": rates,
            "disclosure_date": row.get("disclosure_date"),
            "disclosure_date_source": row.get("disclosure_date_source"),
            "source_url": row.get("source_url"),
            "status": row.get("status"),
            "note": row.get("note"),
            "rate_month": row.get("rate_month"),
            "rate_type": row.get("rate_type")
        })

    return result


# -------------------------------
# 숫자 변환
# -------------------------------


def safe_float(value):

    try:

        if value in [None, "", "-"]:
            return None

        if isinstance(value, (int, float)):
            return float(value)

        text = str(value).strip()
        if not text or text == "-":
            return None

        # 크롤러/JSON 버전에 따라 +0.10%p, ▲0.10%p, -0.10, 0.10% 등
        # 다양한 표시형식이 들어올 수 있으므로 숫자로 정규화한다.
        negative_marker = ("▲" in text or "▼" in text)
        text = (
            text
            .replace(",", "")
            .replace("%p", "")
            .replace("%", "")
            .replace("▲", "")
            .replace("▼", "")
            .replace("+", "")
            .strip()
        )

        number = float(text)
        if negative_marker and number > 0:
            number = -number

        return number

    except Exception:
        return None



# -------------------------------
# 문자열 정규화
# 은행명 검색 정확도 개선
# 저축은행 명칭 제거
# -------------------------------


def normalize(text):


    text = str(text or "")


    replace_list = [

        "(주)",

        "㈜",

        "주식회사",

        "저축은행",

        "은행",

        " ",

        "-",

        "_"

    ]


    for item in replace_list:


        text = text.replace(

            item,

            ""

        )


    return text.lower()



# -------------------------------
# 상품 키워드 검색 V5
# 은행명 + 상품명 검색
# -------------------------------


def search_product_keyword(products, question):


    q = normalize(question)


    # -------------------------------
    # 은행명 Alias
    # -------------------------------

    bank_alias = {

        "우리금융":
            "우리금융저축은행",

        "우리":
            "우리금융저축은행",

        "신한":
            "신한저축은행",

        "하나":
            "하나저축은행",

        "kb":
            "KB저축은행",

        "국민":
            "KB저축은행",

        "페퍼":
            "페퍼저축은행",

        "페퍼저축":
            "페퍼저축은행",

        "osb":
            "OSB저축은행",

        "오에스비":
            "OSB저축은행"

    }



    target_bank = None



    for key, value in bank_alias.items():


        if normalize(key) in q:


            target_bank = normalize(value)

            break



    # -------------------------------
    # 검색 키워드
    # -------------------------------

    keywords = [

        "정기예금",

        "예금",

        "회전정기예금",

        "저축은행",

        "비대면",

        "특판"

    ]



    target_keyword = None



    for item in keywords:


        if normalize(item) in q:


            target_keyword = normalize(item)

            break



    result = []



    for product in products:


        bank = normalize(

            product.get(

                "bank",

                ""

            )

        )


        product_name = normalize(

            product.get(

                "product",

                ""

            )

        )


        # -------------------------------
        # 은행명 검색
        # -------------------------------

        if target_bank:


            if target_bank not in bank:

                continue



        # -------------------------------
        # 상품명 검색
        # -------------------------------

        if target_keyword:


            if target_keyword not in product_name:

                continue



        result.append(product)



    # -------------------------------
    # 금리 높은 순 정렬
    # -------------------------------

    result.sort(

        key=lambda x:

        x.get(

            "rate",

            0

        ),

        reverse=True

    )


    return result

# -------------------------------
# AI 자연어 질문 전처리 V4.6
# -------------------------------

def normalize_question(question):

    q = normalize(question)

    replace_map = {

        "잘주는": "높은",

        "금리좋은": "높은",

        "유리한": "높은",

        "강한": "경쟁력",

        "강점": "경쟁력",

        "약점": "경쟁력",

        "왜낮": "경쟁력",

        "왜높": "경쟁력",

        "괜찮": "경쟁력",

        "수준": "경쟁력",

        "시장에서": "시장",

        "현재시장": "시장",

        "시장상황": "시장현황",

        "현재위치": "시장현황",

        "잘주는곳": "높은곳",

        "못주는": "낮은",

        "불리한": "낮은",

        "뒤지는": "낮은"

    }


    for old, new in replace_map.items():

        q = q.replace(old, new)


    return q



# -------------------------------
# AI 검색 Intent 판단 V5.3
# -------------------------------

def detect_intent(question):


    q = normalize_question(question)



        # -------------------------------
    # 은행 비교 검색 V5.2
    #
    # 특정 은행 대비 높은/낮은 곳
    #
    # 예:
    # 우리금융보다 높은 곳
    # OK보다 좋은 곳
    # -------------------------------


    if any(

        x in q

        for x in [

            "보다 높은",
            "보다 낮은",
            "보다 좋은",
            "보다 나은",
            "대비 높은",
            "대비 낮은",
            "경쟁력 좋은",
            "경쟁력 높은"

        ]

    ):

        return "BANK_COMPARE"




    # -------------------------------
    # 경쟁력 개선 전략 분석 V5.4
    #
    # 금리 개선 방향 / 전략 질문
    #
    # 예:
    # 우리금융 어떻게 해야돼
    # 경쟁력 개선방안 알려줘
    # 금리 전략 알려줘
    # 대응방안
    # -------------------------------


    if any(

        x in q

        for x in [

            "어떻게 해야",
            "어떻게해야",
            "개선",
            "개선방안",
            "개선 방법",
            "개선해야",
            "전략",
            "대응",
            "대응방안",
            "대응 방안",
            "방향",
            "올려야",
            "낮춰야",
            "제안",
            "추천",
            "액션",
            "액션플랜",
            "해야돼",
            "해야되",
            "해야 해",
            "금리전략",
            "금리 전략"

        ]

    ):


        if any(

            bank in q

            for bank in [

                "우리금융",
                "우리",
                "ok",
                "페퍼",
                "sbi",
                "신한",
                "하나",
                "kb"

            ]

        ):

            return "STRATEGY_ANALYSIS"




    # -------------------------------
    # 특정 은행 경쟁력 분석 V5.3
    #
    # 예:
    # 우리금융 어때
    # OK 현황
    # 페퍼 분석
    # -------------------------------

    if any(

        bank in q

        for bank in [

            "우리금융",
            "우리",
            "ok",
            "페퍼",
            "sbi",
            "신한",
            "하나",
            "kb"

        ]

    ):

        if any(

            x in q

            for x in [

                "어때",
                "현황",
                "분석",
                "평가",
                "경쟁력",
                "상황"

            ]

        ):

            return "COMPETITIVENESS"



    # -------------------------------
    # 금융지주 계열 비교
    # -------------------------------

    if any(

        x in q

        for x in [

            "금융지주",
            "지주계열",
            "4대금융",
            "우리신한하나kb"

        ]

    ):

        return "FINANCIAL_COMPARE"



    # -------------------------------
    # 시장 현황
    # -------------------------------

    if any(

        x in q

        for x in [

            "시장현황",
            "시장 상황",
            "시장상황",
            "현재위치",
            "시장위치",
            "순위",
            "시장"

        ]

    ):

        return "MARKET_STATUS"



    # -------------------------------
    # 동일 금리 비교
    # -------------------------------

    if any(

        x in q

        for x in [

            "같은금리",
            "동일금리",
            "비슷한금리",
            "동률",
            "공동"

        ]

    ):

        return "COMPARE_SAME"



    # -------------------------------
    # 높은 금리 비교
    # -------------------------------

    if any(

        x in q

        for x in [

            "높은곳",
            "높은",
            "좋은곳",
            "좋은금리",
            "금리좋",
            "우위",
            "앞서는",
            "나은",
            "상회",
            "초과",
            "더높",
            "높은금리",
            "금리높은"

        ]

    ):

        return "COMPARE_HIGH"



    # -------------------------------
    # 낮은 금리 비교
    # -------------------------------

    if any(

        x in q

        for x in [

            "낮은곳",
            "낮은",
            "낮은금리",
            "금리낮",
            "하회",
            "뒤처지는",
            "열위",
            "떨어지는",
            "더낮",
            "금리낮은"

        ]

    ):

        return "COMPARE_LOW"



    # -------------------------------
    # 최고 금리
    # -------------------------------

    if any(

        x in q

        for x in [

            "최고금리",
            "최고",
            "가장높",
            "top",
            "탑",
            "1위"

        ]

    ):

        return "TOP_RATE"



    # -------------------------------
    # 일반 경쟁력 질문
    # -------------------------------

    if any(

        x in q

        for x in [

            "경쟁력",
            "경쟁",
            "비교",
            "어때",
            "괜찮",
            "평가",
            "위치"

        ]

    ):

        return "COMPARE_HIGH"



    # -------------------------------
    # 기본
    # -------------------------------

    return "GENERAL"



    # -------------------------------
    # 최고 금리
    # -------------------------------

    if any(

        x in q

        for x in [

            "최고금리",

            "가장높",

            "높은금리",

            "1위금리"

        ]

    ):

        return "TOP_RATE"



    # -------------------------------
    # 최저 금리
    # -------------------------------

    if any(

        x in q

        for x in [

            "최저금리",

            "가장낮",

            "낮은금리"

        ]

    ):

        return "LOW_RATE"



    return "UNKNOWN"


# -------------------------------
# 저축은행명 별칭 매핑
# -------------------------------

BANK_ALIAS = {

    # 우리금융저축은행
    "우리금융저축은행": "우리금융저축은행",
    "우리금융": "우리금융저축은행",
    "우리저축": "우리금융저축은행",
    "우리저축은행": "우리금융저축은행",
    "우리": "우리금융저축은행",


    # 신한저축은행
    "신한저축은행": "신한저축은행",
    "신한저축": "신한저축은행",
    "신한": "신한저축은행",


    # 하나저축은행
    "하나저축은행": "하나저축은행",
    "하나저축": "하나저축은행",
    "하나": "하나저축은행",


    # KB저축은행
    "KB저축은행": "KB저축은행",
    "KB저축": "KB저축은행",
    "kb": "KB저축은행",
    "국민": "KB저축은행",


    # SBI저축은행
    "SBI저축은행": "SBI저축은행",
    "SBI저축": "SBI저축은행",
    "SBI": "SBI저축은행",
    "sbi": "SBI저축은행",


    # OK저축은행
    "OK저축은행": "OK저축은행",
    "OK저축": "OK저축은행",
    "OK": "OK저축은행",
    "ok": "OK저축은행",


    # 페퍼저축은행
    "페퍼저축은행": "페퍼저축은행",
    "페퍼저축": "페퍼저축은행",
    "페퍼": "페퍼저축은행",


    # 웰컴저축은행
    "웰컴저축은행": "웰컴저축은행",
    "웰컴": "웰컴저축은행",


    # 모아저축은행
    "모아저축은행": "모아저축은행",
    "모아": "모아저축은행",


    # 한국투자저축은행
    "한국투자저축은행": "한국투자저축은행",
    "한국투자": "한국투자저축은행",


    # 대원저축은행
    "대원저축은행": "대원저축은행",
    "대원": "대원저축은행"

}



def resolve_bank_name(question):


    print(

        "resolve 입력:",

        question

    )


    q = normalize(question)


    print(

        "normalize 결과:",

        q

    )


        # -------------------------------
    # 기존 별칭 우선 검색
    # -------------------------------

    for keyword, bank_name in sorted(

        BANK_ALIAS.items(),

        key=lambda x: len(x[0]),

        reverse=True

    ):


        if normalize(keyword) in q:


            print(

                "별칭 매칭:",

                keyword,

                "->",

                bank_name

            )


            return bank_name.replace(

                "저축은행",

                ""

            )



    # -------------------------------
    # 전체 저축은행 자동 검색
    # -------------------------------

    try:


        products = build_products()


        print(

            "AI 검색 질문:",

            question

        )


        print(

            "정규화 질문:",

            q

        )


        print(

            "은행 샘플:",

            [

                x.get("bank")

                for x in products[:10]

            ]

        )



        banks = sorted(

            set(

                x.get("bank")

                for x in products

                if x.get("bank")

            ),

            key=len,

            reverse=True

        )



        for bank in banks:


            bank_normal = normalize(bank)



            if bank_normal in q:


                return bank



            if (

                bank_normal + "저축은행"

            ) in q:


                return bank



    except Exception as e:


        print(

            "은행 자동검색 오류:",

            e

        )



    return None


# -------------------------------
# 상품 데이터 생성
# -------------------------------


def build_products(

    period_name="12개월"

):


    raw_data = load_rates()

    previous_data = load_previous_rates()

    previous_map = {}

    for prev in previous_data:
        prev_bank = normalize(
            prev.get("bank")
            or prev.get("kor_co_nm")
            or prev.get("bank_name")
            or ""
        )
        prev_product = normalize(
            prev.get("product")
            or prev.get("fin_prdt_nm")
            or prev.get("product_name")
            or ""
        )
        if prev_bank and prev_product:
            previous_map[(prev_bank, prev_product)] = prev


    period = PERIOD_MAP.get(

        period_name,

        "12"

    )



    rate_field = (

        "top_"

        +

        period

        +

        "m"

    )



    change_field = (

        "change_"

        +

        period

    )



    products = []




    for item in raw_data:



        rate = safe_float(

            item.get(

                rate_field

            )

        )



        if rate is None:


            rate = 0



        # 전일 대비 금리변동값
        # crawler 버전에 따라 change_12 / change_12m / diff 계열이
        # 혼용될 수 있어 모두 지원하고, 없으면 previous_rates.json으로 계산한다.
        change_candidates = [
            item.get(change_field),
            item.get(f"change_{period}m"),
            item.get(f"diff_{period}"),
            item.get(f"diff_{period}m"),
            item.get("change"),
            item.get("change_rate"),
            item.get("diff")
        ]

        change = None

        for candidate in change_candidates:
            parsed = safe_float(candidate)
            if parsed is not None:
                change = parsed
                break

        bank_for_change = str(
            item.get("bank")
            or item.get("kor_co_nm")
            or item.get("bank_name")
            or ""
        ).strip()
        product_for_change = str(
            item.get("product")
            or item.get("fin_prdt_nm")
            or item.get("product_name")
            or ""
        ).strip()

        prev_item = previous_map.get(
            (normalize(bank_for_change), normalize(product_for_change))
        )

        if prev_item:
            prev_rate = safe_float(
                prev_item.get(rate_field)
                or prev_item.get(f"intr_rate_{period}")
                or prev_item.get("intr_rate2")
                or prev_item.get("max_rate")
                or prev_item.get("rate")
            )

            if prev_rate is not None and rate is not None:
                calculated_change = round(rate - prev_rate, 4)

                # 명시적 change 값이 누락되었거나 0인데 실제 전일금리가 다르면
                # previous_rates 기준 계산값을 우선 사용한다.
                if change is None or (change == 0 and calculated_change != 0):
                    change = calculated_change

        if change is None:
            change = 0


        bank = str(

            item.get(

                "bank",

                ""

            )

            or ""

        ).strip()



        product = str(

            item.get(

                "product",

                ""

            )

            or ""

        ).strip()




        if not bank or not product:


            continue




        products.append({

            "category":

                "정기예금",


            "period":

                period_name,


            "bank":

                bank,


            "product":

                product,


            "rate":

                rate,


            "change":

                change,


            "reg_date":

                item.get(

                    "reg_date",

                    ""

                )

        })



    return products
    
# -------------------------------
# 상품 중복 제거
# -------------------------------


def unique_products(products):


    result = []

    seen = set()



    for item in products:


        key = (

            item["bank"],

            item["product"],

            item["period"]

        )



        if key in seen:

            continue



        seen.add(key)

        result.append(item)



    return result




# -------------------------------
# 은행 상품 검색
# -------------------------------


def find_bank_products(

    products,

    keyword

):


    keyword = normalize(keyword)



    result = []



    for item in products:


        bank_name = normalize(

            item["bank"]

        )



        if keyword in bank_name:


            result.append(item)



    return result




# -------------------------------
# 은행별 최고 금리
# -------------------------------


def get_bank_best_rates(products):

    bank_map = {}

    for item in products:

        bank = item["bank"]

        if not bank:
            continue


        if (
            bank not in bank_map
            or
            item["rate"] > bank_map[bank]["rate"]
        ):

            bank_map[bank] = item


    return list(
        bank_map.values()
    )


# ===================================
# SBRateBot V4 app.py
# 2/20
# ===================================


# -------------------------------
# 시장 은행 순위 계산
# -------------------------------


def get_market_bank_rank(

    products,

    target_bank

):


    bank_best = get_bank_best_rates(

        products

    )


    bank_best.sort(

        key=lambda x:

            x["rate"],

        reverse=True

    )


    rank = "-"


    total = len(

        bank_best

    )


    target = normalize(

        target_bank

    )


    for idx,item in enumerate(

        bank_best,

        start=1

    ):


        if normalize(

            item["bank"]

        ) == target:


            rank = idx

            break



    return {

        "rank":

            rank,


        "total":

            total

    }




# -------------------------------
# 금리 변화 표시 포맷
# -------------------------------


def format_change(

    value

):


    try:


        value = float(

            value

        )


    except:


        return "0.00%p"



    if value > 0:


        return (

            '<span class="rate-change increase">'

            f'+{value:.2f}%p'

            '</span>'

        )


    elif value < 0:


        return (

            '<span class="rate-change decrease">'

            f'▲{abs(value):.2f}%p'

            '</span>'

        )


    else:


        return (

            '<span class="rate-change">'

            '0.00%p'

            '</span>'

        )




# -------------------------------
# TOP 금리 상품
# -------------------------------


def get_top_products(

    products,

    count=5

):


    result = sorted(

        products,

        key=lambda x:

            x["rate"],

        reverse=True

    )


    return result[:count]




# -------------------------------
# 낮은 금리 상품
# -------------------------------


def get_bottom_products(

    products,

    count=5

):


    result = sorted(

        products,

        key=lambda x:

            x["rate"]

    )


    return result[:count]




# -------------------------------
# 특정 금리 이상 검색
# -------------------------------


def filter_over_rate(

    products,

    rate

):


    result = []


    for item in products:


        if item["rate"] >= rate:


            result.append(

                item

            )


    result.sort(

        key=lambda x:

            x["rate"],

        reverse=True

    )


    return result




# -------------------------------
# 특정 금리 이하 검색
# -------------------------------


def filter_under_rate(

    products,

    rate

):


    result = []


    for item in products:


        if item["rate"] <= rate:


            result.append(

                item

            )


    result.sort(

        key=lambda x:

            x["rate"],

        reverse=True

    )


    return result




# -------------------------------
# 숫자 추출
# 예)
# TOP5
# 3% 이상
# 0.5% 높은곳
# -------------------------------


def extract_number(

    text

):


    result = re.search(

        r'(\d+\.?\d*)',

        text

    )


    if result:


        return float(

            result.group(1)

        )


    return None




# -------------------------------
# 금리 차이 조건 추출
#
# 예)
# 대원보다 0.5% 높은곳
# 우리금융보다 1% 낮은곳
#
# return
# {
#   type : HIGHER / LOWER,
#   value : 차이
# }
# -------------------------------


def extract_rate_condition(

    question

):


    q = normalize_question(

        question

    )


    value = extract_number(

        q

    )


    if value is None:


        return None



    higher = [

        "높",

        "상회",

        "이상",

        "초과",

        "큰"

    ]



    lower = [

        "낮",

        "하회",

        "미만",

        "작은"

    ]



    if any(

        x in q

        for x in higher

    ):


        return {


            "type":

                "HIGHER",


            "value":

                value

        }



    if any(

        x in q

        for x in lower

    ):


        return {


            "type":

                "LOWER",


            "value":

                value

        }



    return None




# -------------------------------
# 비교 대상 은행 찾기
# -------------------------------


def find_target_bank(

    question

):


    bank = resolve_bank_name(

        question

    )


    return bank




# -------------------------------
# 두 은행 비교
# -------------------------------


def compare_two_banks(

    products,

    bank1,

    bank2

):


    bank1_items = find_bank_products(

        products,

        bank1

    )


    bank2_items = find_bank_products(

        products,

        bank2

    )


    if not bank1_items or not bank2_items:


        return None



    best1 = max(

        bank1_items,

        key=lambda x:

            x["rate"]

    )


    best2 = max(

        bank2_items,

        key=lambda x:

            x["rate"]

    )


    return {


        "bank1":

            best1,


        "bank2":

            best2,


        "difference":

            round(

                best1["rate"]

                -

                best2["rate"],

                2

            )

    }




# -------------------------------
# 은행 경쟁력 분석
# -------------------------------


def analyze_bank_status(

    products,

    bank_name

):


    items = find_bank_products(

        products,

        bank_name

    )


    if not items:

        return None



    best = max(

        items,

        key=lambda x:

            x["rate"]

    )



    rank = get_market_bank_rank(

        products,

        bank_name

    )



    avg_rate = sum(

        x["rate"]

        for x in products

    ) / len(products)



    gap = round(

        best["rate"]

        -

        avg_rate,

        2

    )



    bank_best = get_bank_best_rates(

        products

    )



    bank_best.sort(

        key=lambda x:

            x["rate"],

        reverse=True

    )



    top10 = bank_best[:10]



    top10_avg = sum(

        x["rate"]

        for x in top10

    ) / len(top10)



    higher = [

        x

        for x in bank_best

        if x["rate"] > best["rate"]

        and normalize(x["bank"])

        != normalize(bank_name)

    ]



    lower = [

        x

        for x in bank_best

        if x["rate"] < best["rate"]

        and normalize(x["bank"])

        != normalize(bank_name)

    ]



    higher.sort(

        key=lambda x:

            x["rate"],

        reverse=True

    )



    lower.sort(

        key=lambda x:

            x["rate"],

        reverse=True

    )



    return {


        "bank":

            best["bank"],


        "product":

            best["product"],


        "rate":

            best["rate"],


        "rank":

            rank["rank"],


        "total":

            rank["total"],


        "avg_gap":

            gap,


        "top10_avg":

            round(

                top10_avg,

                2

            ),


        "top10_gap":

            round(

                best["rate"]

                -

                top10_avg,

                2

            ),


        "higher":

            higher,


        "lower":

            lower,


        "position_text":

            (

                "상위권"

                if rank["rank"] <= 15

                else

                "중위권"

                if rank["rank"] <= 50

                else

                "하위권"

            )

    }

    # ===================================
# SBRateBot V4 app.py
# 3/20
# ===================================


@app.route("/api/kpi")
def api_kpi():

    products = unique_products(
        build_products("12개월")
    )

    products = [
        p
        for p in products
        if p["rate"] > 0
    ]

    if not products:

        return jsonify({
            "product_count": 0,
            "change_count": 0,
            "average_rate": 0,
            "highest_gap": 0,
            "lowest_gap": 0,
            "average_gap": 0,
            "max_rate": 0,
            "min_rate": 0
        })

    # -------------------------
    # 시장 데이터
    # -------------------------

    max_rate = max(
        p["rate"]
        for p in products
    )

    min_rate = min(
        p["rate"]
        for p in products
    )

    avg_rate = (
        sum(
            p["rate"]
            for p in products
        )
        / len(products)
    )

    # -------------------------
    # 우리금융 최고상품
    # -------------------------

    woori_products = find_bank_products(
        products,
        "우리금융저축은행"
    )

    if woori_products:

        woori = max(
            woori_products,
            key=lambda x: x["rate"]
        )

        woori_rate = woori["rate"]

    else:

        woori_rate = 0

    # -------------------------
    # Gap 계산
    # -------------------------

    highest_gap = round(
        woori_rate - max_rate,
        2
    )

    lowest_gap = round(
        woori_rate - min_rate,
        2
    )

    average_gap = round(
        woori_rate - avg_rate,
        2
    )

    # -------------------------
    # 금리변동건수
    # -------------------------

    change_count = len([
        p
        for p in products
        if p.get("change", 0) != 0
    ])

    return jsonify({

        "product_count": len(products),

        "change_count": change_count,

        "average_rate": round(
            avg_rate,
            2
        ),

        "max_rate": round(
            max_rate,
            2
        ),

        "min_rate": round(
            min_rate,
            2
        ),

        "highest_gap": highest_gap,

        "lowest_gap": lowest_gap,

        "average_gap": average_gap

    })




# -------------------------------
# 우리금융 Market Position
# -------------------------------

@app.route("/api/woori")
def api_woori():

    products = unique_products(

        build_products(

            "12개월"

        )

    )

    # -------------------------------
    # 우리금융 최고금리 상품
    # -------------------------------


    woori_products = find_bank_products(

        products,

        "우리금융저축은행"

    )


    if not woori_products:

        return jsonify({

            "bank":

                "우리금융저축은행"

        })



    woori = max(

        woori_products,

        key=lambda x:

            x["rate"]

    )



    # -------------------------------
    # 은행별 최고금리 추출
    # -------------------------------


    bank_rates = {}


    for p in products:


        bank = p["bank"]

        rate = p["rate"]


        if (

            bank not in bank_rates

            or rate > bank_rates[bank]

        ):

            bank_rates[bank] = rate



    # -------------------------------
    # 은행별 금리 순위
    # -------------------------------


    bank_rank_list = sorted(

        bank_rates.items(),

        key=lambda x:

            x[1],

        reverse=True

    )


    # -------------------------------
    # 우리금융저축은행 시장 순위 계산
    # 우리저축은행과 절대 분리
    # 은행별 최고금리 기준
    # -------------------------------

    market_rank = "-"

    market_total = len(
        bank_rank_list
    )

    TARGET_BANK = "우리금융"

        # -------------------------------
    # 우리금융 시장 순위 계산
    # 동일 금리 공동순위 확인
    # -------------------------------


    same_rank_count = 0


    for idx, item in enumerate(

        bank_rank_list,

        start=1

    ):


        bank_name = normalize(

            item[0]

        )


        # 정확히 우리금융만 검색
        if bank_name == TARGET_BANK:


            market_rank = idx


            target_rate = item[1]


            for _, rate in bank_rank_list:

                if rate == target_rate:

                    same_rank_count += 1









            break

        # -------------------------------
    # 시장 평균 / 최고 / 최저
    # 0% 상품 제외
    # -------------------------------


    valid_rates = [

        x["rate"]

        for x in products

        if x["rate"] > 0

    ]


    avg_rate = sum(

        valid_rates

    ) / len(valid_rates)



    highest_rate = max(

        valid_rates

    )



    lowest_rate = min(

        valid_rates

    )

    # -------------------------------
    # 금융지주 순위
    # -------------------------------

    financial_products = []

    for bank in FINANCIAL_BANKS:

        items = find_bank_products(
            products,
            bank
        )

        if items:

            financial_products.append(
                max(
                    items,
                    key=lambda x: x["rate"]
                )
            )

    financial_products.sort(
        key=lambda x: x["rate"],
        reverse=True
    )

    financial_rank = "-"

    for idx, item in enumerate(
        financial_products,
        start=1
    ):

        if normalize(item["bank"]) == normalize(woori["bank"]):

            financial_rank = idx

            break

    # -------------------------------
    # API Response
    # -------------------------------

    return jsonify({

        "bank": woori["bank"],

        "product": woori["product"],

        "rate": round(
            woori["rate"],
            2
        ),

                "lowest_rate":

            round(

                lowest_rate,

                2

            ),

        "market_rank": market_rank,

        "market_total": market_total,

        "same_rank_count": same_rank_count,

        "financial_rank": financial_rank,

        "average_gap": round(
            woori["rate"] - avg_rate,
            2
        ),

        "highest_gap": round(
            woori["rate"] - highest_rate,
            2
        ),

        "lowest_gap": round(
            woori["rate"] - lowest_rate,
            2
        )

    })

    # ===================================
# SBRateBot V4 app.py
# 4/20
# ===================================


# -------------------------------
# 시장 TOP10
# -------------------------------


@app.route("/api/rates")
def api_rates():

    products = unique_products(
        build_products(
            "12개월"
        )
    )

    bank_best = get_bank_best_rates(
        products
    )

    bank_best = [
        x
        for x in bank_best
        if x["rate"] > 0
    ]

    bank_best.sort(
        key=lambda x: x["rate"],
        reverse=True
    )

    # 기본은 TOP10, ?all=1 요청 시 전체 은행 순위 반환
    show_all = str(
        request.args.get(
            "all",
            "0"
        )
    ).lower() in [
        "1",
        "true",
        "yes",
        "all"
    ]

    target_items = (
        bank_best
        if show_all
        else bank_best[:10]
    )

    result = []

    for idx, item in enumerate(
        target_items,
        start=1
    ):

        result.append({
            "rank": idx,
            "bank": item["bank"],
            "product": item["product"],
            "rate": item["rate"],
            "change": item.get(
                "change",
                0
            )
        })

    return jsonify(result)


# -------------------------------
# 전일 대비 금리 상승 / 하락 TOP5
# 은행별 12개월 최고금리 상품 기준
# -------------------------------

@app.route("/api/rate-changes")
def api_rate_changes():

    current_rows = load_rates()
    previous_rows = load_previous_rates()

    def get_bank(row):
        return str(
            row.get("bank")
            or row.get("kor_co_nm")
            or row.get("bank_name")
            or ""
        ).strip()

    def get_product(row):
        return str(
            row.get("product")
            or row.get("fin_prdt_nm")
            or row.get("product_name")
            or ""
        ).strip()

    def get_12m_rate(row):
        for field in [
            "top_12m",
            "rate_12m",
            "intr_rate2",
            "max_rate",
            "rate"
        ]:
            value = safe_float(row.get(field))
            if value is not None and value > 0:
                return value
        return None

    def bank_best_map(rows):
        result = {}
        for row in rows:
            bank = get_bank(row)
            rate = get_12m_rate(row)
            if not bank or rate is None:
                continue

            key = normalize(bank)
            current = result.get(key)

            if current is None or rate > current["rate"]:
                result[key] = {
                    "bank": bank,
                    "product": get_product(row),
                    "rate": rate
                }
        return result

    current_best = bank_best_map(current_rows)
    previous_best = bank_best_map(previous_rows)

    changes = []

    for key, current in current_best.items():
        previous = previous_best.get(key)
        if not previous:
            continue

        change = round(
            current["rate"] - previous["rate"],
            4
        )

        if change == 0:
            continue

        changes.append({
            "bank": current["bank"],
            "product": current["product"],
            "rate": round(current["rate"], 2),
            "previous_rate": round(previous["rate"], 2),
            "change": change,
            "change_value": change
        })

    # 이전 데이터가 없거나 매칭이 적은 경우 current 자체의 explicit change를 보강
    if not changes:
        products = unique_products(build_products("12개월"))
        by_bank = {}

        for item in products:
            bank = str(item.get("bank") or "").strip()
            change = safe_float(item.get("change"))
            if not bank or change is None or change == 0:
                continue

            key = normalize(bank)
            existing = by_bank.get(key)
            if existing is None or abs(change) > abs(existing["change"]):
                by_bank[key] = {
                    "bank": bank,
                    "product": item.get("product", ""),
                    "rate": round(float(item.get("rate") or 0), 2),
                    "previous_rate": round(float(item.get("rate") or 0) - change, 2),
                    "change": change,
                    "change_value": change
                }

        changes = list(by_bank.values())

    up_all = sorted(
        [x for x in changes if x["change"] > 0],
        key=lambda x: x["change"],
        reverse=True
    )

    down_all = sorted(
        [x for x in changes if x["change"] < 0],
        key=lambda x: x["change"]
    )

    return jsonify({
        "up_top5": up_all[:5],
        "down_top5": down_all[:5],
        "up_all": up_all,
        "down_all": down_all,
        "up_count": len(up_all),
        "down_count": len(down_all),
        "change_count": len(up_all) + len(down_all)
    })


# -------------------------------
# 금융지주 저축은행 비교
# -------------------------------


@app.route("/api/financial")

def api_financial():


    products = unique_products(

        build_products(

            "12개월"

        )

    )



    result = []



    for bank in FINANCIAL_BANKS:


        items = find_bank_products(

            products,

            bank

        )



        if items:


            best = max(

                items,

                key=lambda x:

                    x["rate"]

            )


            result.append(best)



    result.sort(

        key=lambda x:

            x["rate"],

        reverse=True

    )



    response = []



    for idx,item in enumerate(

        result,

        start=1

    ):


        response.append({


            "rank":

                idx,



            "bank":

                item["bank"],



            "product":

                item["product"],



            "rate":

                item["rate"],



            "change":

                item["change"],



            # -------------------------------
            # 금리 증감 표시
            # 상승 : 파란색 +
            # 하락 : 빨간색 ▲
            # -------------------------------


            "change_html":


                (

                    '<span class="rate-change increase">'

                    f'+{item["change"]:.2f}%p'

                    '</span>'

                )


                if item["change"] > 0


                else


                (

                    '<span class="rate-change decrease">'

                    f'▲{abs(item["change"]):.2f}%p'

                    '</span>'

                )


                if item["change"] < 0


                else


                (

                    '<span class="rate-change">'

                    '0.00%p'

                    '</span>'

                )

        })



    return jsonify(response)




# -------------------------------
# 전체상품 조회
# -------------------------------


@app.route("/api/products")

def api_products():


    products = []



    for period in PERIOD_MAP:


        products.extend(

            build_products(

                period

            )

        )



    products = unique_products(

        products

    )



    products.sort(

        key=lambda x:

        (

            x["period"],

            -x["rate"]

        )

    )



    return jsonify(products)

# ===================================
# SBRateBot V4 app.py
# 5/20
# ===================================


# -------------------------------
# AI 시장 요약
# -------------------------------


@app.route("/api/ai")

def api_ai():


    try:


        with open(

            DATA_FILE,

            "r",

            encoding="utf-8"

        ) as f:


            products = json.load(f)



        if isinstance(products, dict):


            products = products.get(

                "REC",

                []

            )



        if not products:


            return jsonify({

                "summary":[

                    "시장 데이터를 불러올 수 없습니다."

                ]

            })




        rate_products = []



        for item in products:


            try:


                rate = float(

                    str(

                        item.get(

                            "top_12m"

                        )

                        or item.get(

                            "rate"

                        )

                        or 0

                    )

                    .replace(

                        ",",

                        ""

                    )

                )



                if rate > 0:


                    item["rate"] = rate


                    rate_products.append(

                        item

                    )



            except:


                continue




        if not rate_products:


            return jsonify({

                "summary":[

                    "금리 데이터가 없습니다."

                ]

            })




        rate_products.sort(

            key=lambda x:

                x["rate"],

            reverse=True

        )




        total = len(

            rate_products

        )




        avg_rate = sum(

            x["rate"]

            for x in rate_products

        ) / total




        highest = rate_products[0]



        lowest = rate_products[-1]




        highest_gap = (

            highest["rate"]

            -

            avg_rate

        )



        lowest_gap = (

            lowest["rate"]

            -

            avg_rate

        )




        if highest_gap >= 0:


            highest_gap_text = (

                f"+{highest_gap:.2f}%p"

            )


        else:


            highest_gap_text = (

                f"▲{abs(highest_gap):.2f}%p"

            )




        if lowest_gap < 0:


            lowest_gap_text = (

                f"▲{abs(lowest_gap):.2f}%p"

            )


        else:


            lowest_gap_text = (

                f"+{lowest_gap:.2f}%p"

            )




        spread = (

            highest["rate"]

            -

            lowest["rate"]

        )




        summary = []



        summary.append(

            "📊 12개월 정기예금 시장 분석"

        )



        summary.append(

            f"분석상품 : {total}개"

        )



        summary.append(

            f"평균금리 : {avg_rate:.2f}%"

        )



        summary.append(

            f"최고금리 : "

            f"{highest.get('bank','')} "

            f"{highest['rate']:.2f}%"

        )



        summary.append(

            f"최저금리 : "

            f"{lowest.get('bank','')} "

            f"{lowest['rate']:.2f}%"

        )



        summary.append(

            f"금리 스프레드 : {spread:.2f}%p"

        )

# ===================================
# SBRateBot V4 app.py
# 6/20
# ===================================


        if spread >= 0.5:


            summary.append(

                "은행별 금리 경쟁 차이가 큰 시장으로 "

                "최고금리 상품 중심의 경쟁이 진행되고 있습니다."

            )


        else:


            summary.append(

                "은행별 금리 차이가 크지 않은 "

                "안정적인 금리 경쟁 시장입니다."

            )




        if avg_rate >= 3:


            summary.append(

                "평균금리는 3% 이상으로 "

                "예금 유치를 위한 금리 경쟁력이 중요한 상황입니다."

            )


        else:


            summary.append(

                "평균금리는 낮은 수준으로 "

                "고객 선택 시 금리 차별화가 중요합니다."

            )




        return jsonify({

            "summary":

                summary

        })




    except Exception as e:


        print(

            "AI 시장 분석 오류:",

            e

        )


        return jsonify({

            "summary":[

                "AI 시장 분석 오류가 발생했습니다."

            ]

        })





# -------------------------------
# ISA / 퇴직연금 AI 검색 V5.2
# 선택 상품 데이터 전용
# -------------------------------

def build_pension_ai_answer(category, period, question):

    category = str(category or "").strip().lower()
    period = str(period or "12").strip()

    if category not in ["isa", "irp"]:
        return None

    if period not in ["3", "6", "12", "24", "36"]:
        period = "12"

    data_file = (
        ISA_DATA_FILE
        if category == "isa"
        else IRP_DATA_FILE
    )

    category_name = (
        "ISA"
        if category == "isa"
        else "퇴직연금(IRP)"
    )

    source_category_name = (
        "ISA"
        if category == "isa"
        else "퇴직연금"
    )

    items = build_pension_products(
        data_file,
        source_category_name
    )

    key = period + "m"

    normalized_items = []

    for item in items:

        row = dict(item)

        rate = (
            row.get("rates", {})
            .get(key)
        )

        row["period"] = period + "개월"
        row["rate"] = rate

        normalized_items.append(
            row
        )

    valid_items = [

        x

        for x in normalized_items

        if (
            x.get("rate")
            is not None
        )
        and
        isinstance(
            x.get("rate"),
            (int, float)
        )
        and
        x.get("rate") > 0

    ]

    valid_items.sort(
        key=lambda x:
            x.get("rate", 0),
        reverse=True
    )

    woori = next(
        (
            x
            for x in valid_items
            if "우리금융" in str(
                x.get("bank", "")
            )
        ),
        None
    )

    market_context = {

        "상품군":
            category_name,

        "조회기간":
            period + "개월",

        "수집기관수":
            len(normalized_items),

        "유효금리기관수":
            len(valid_items),

        "우리금융":
            woori,

        "금리순위":
            valid_items[:20],

        "전체수집데이터":
            normalized_items[:30]

    }

    market_data = json.dumps(

        market_context,

        ensure_ascii=False,

        indent=2

    )

    strict_prompt = (
        "당신은 저축은행 수신상품 분석 AI입니다.\n"
        f"현재 선택된 상품은 [{category_name}] 입니다.\n"
        f"조회기간은 [{period}개월] 입니다.\n\n"
        "중요 규칙:\n"
        "1. 아래 제공된 데이터만 사용합니다.\n"
        "2. 정기예금 시장 데이터로 바꾸어 답하지 않습니다.\n"
        f"3. 모든 답변의 상품 기준은 반드시 {category_name}입니다.\n"
        + (
            "퇴직연금은 DB형이 아니라 IRP/DC·IRP 약정금리 기준으로만 답합니다.\n"
            if category == "irp"
            else ""
        )
        + "4. 금리가 null인 기관은 금리 순위에서 제외하되, "
        "상품/공시 존재 여부를 묻는 질문에는 포함할 수 있습니다.\n"
        "5. 공시일이 null이면 임의 날짜를 만들지 말고 '공시일 미확인'이라고 답합니다.\n"
        "6. 우리금융 관련 질문은 제공된 우리금융 항목을 기준으로 합니다.\n\n"
        "사용자 질문:\n"
        + question
    )

    try:

        ai_comment = ask_gemini(

            strict_prompt,

            market_data

        )

        if ai_comment:

            return (
                f"🤖 {category_name} AI 분석\n\n"
                + ai_comment
            )

    except Exception as e:

        print(
            "PENSION AI GEMINI ERROR:",
            e
        )

    # Gemini 실패 시에도 선택 상품 기준 기본답변
    if not valid_items:

        return (
            f"{category_name} {period}개월 기준 "
            "현재 유효 금리 데이터가 없습니다."
        )

    top = valid_items[0]

    answer = (
        f"📊 {category_name} {period}개월 기준\n\n"
        f"수집기관 : {len(normalized_items)}개\n"
        f"유효금리기관 : {len(valid_items)}개\n"
        f"최고금리 : {top.get('bank','-')} "
        f"{top.get('rate',0):.2f}%\n"
    )

    if woori:

        rank = (
            valid_items.index(woori)
            + 1
        )

        answer += (
            f"우리금융 : "
            f"{woori.get('rate',0):.2f}% "
            f"({rank}위)\n"
            f"공시일 : "
            f"{woori.get('disclosure_date') or '미확인'}"
        )

    return answer


# -------------------------------
# AI 검색 V4.1
# Python Intent + Gemini 분리
# -------------------------------


@app.route(

    "/api/ai/search",

    methods=["POST"]

)

def ai_search():


    try:


        data = request.json



        question = str(

            data.get(

                "question",

                ""

            )

        ).strip()




        if not question:


            return jsonify({

                "answer":

                    "질문을 입력해주세요."

            })



        category = str(

            data.get(
                "category",
                "deposit"
            )

        ).strip().lower()


        period = str(

            data.get(
                "period",
                "12"
            )

        ).strip()



        if category in [
            "isa",
            "irp"
        ]:


            pension_answer = (
                build_pension_ai_answer(
                    category,
                    period,
                    question
                )
            )


            return jsonify({

                "answer":
                    pension_answer

            })




        q = normalize(

            question

        )




        # -------------------------------
        # AI Intent 판단 V4.5
        # -------------------------------


        intent = detect_intent(

            question

        )



        print(

            "AI INTENT:",

            intent

        )




        # -------------------------------
        # 은행명 자동 인식
        # -------------------------------


        target_bank = resolve_bank_name(

            question

        )



        print(

            "TARGET BANK:",

            target_bank

        )




        # -------------------------------
        # 검색 기간 선택
        # 기본 12개월
        # -------------------------------


        search_period = "12개월"



        if "1개월" in question:


            search_period = "1개월"



        elif "3개월" in question:


            search_period = "3개월"



        elif "6개월" in question:


            search_period = "6개월"



        elif "24개월" in question:


            search_period = "24개월"



        elif "36개월" in question:


            search_period = "36개월"




        products = unique_products(

            build_products(

                search_period

            )

        )



        products = [

            x

            for x in products

            if x["rate"] > 0

        ]




        # -------------------------------
        # 은행 시장 분석
        # -------------------------------


        bank_analysis = None



        if target_bank:


            bank_analysis = analyze_bank_status(

                products,

                target_bank

            )

# -------------------------------
# 금리 차이 조건 검색 V4.5.2
#
# 예)
# 대원보다 0.5% 높은곳
# 우리금융보다 1% 낮은곳
#
# 기준:
# - 은행별 최고금리 기준
# - 전체 저축은행 비교
#
# 증감 표시:
# 증가 : 파란색 + 표시
# 감소 : 빨간색 ▲ 표시
# -------------------------------


        rate_condition = extract_rate_condition(

            question

        )



        condition_answer = None

        answer = ""





        if (

            target_bank

            and

            rate_condition

            and

            intent != "BANK_COMPARE"

        ):



            target_products = find_bank_products(

                products,

                target_bank

            )



            if target_products:



                base_rate = max(

                    x["rate"]

                    for x in target_products

                )



                bank_best_rates = get_bank_best_rates(

                    products

                )





                if rate_condition["type"] == "HIGHER":



                    target_rate = (

                        base_rate

                        +

                        rate_condition["value"]

                    )



                    candidates = [

                        x

                        for x in bank_best_rates

                        if (

                            x["rate"]

                            >=

                            target_rate

                        )

                        and

                        normalize(x["bank"])

                        !=

                        normalize(target_bank)

                    ]



                    candidates.sort(

                        key=lambda x:

                            x["rate"],

                        reverse=True

                    )



                    condition_answer = (


                        f"📈 {target_bank} 대비 "

                        f"{rate_condition['value']:.2f}%p 이상 높은 은행\n\n"


                        f"기준금리 : {base_rate:.2f}%\n"

                        f"조건금리 : {target_rate:.2f}% 이상\n\n"


                    )





                    if candidates:



                        for idx,item in enumerate(

                            candidates[:10],

                            start=1

                        ):



                            diff = round(

                                item["rate"]

                                -

                                base_rate,

                                2

                            )



                            diff_text = (


                                f'<span class="rate-change increase">'

                                f'+{diff:.2f}%p'

                                f'</span>'


                            )



                            condition_answer += (


                                f"{idx}. "

                                f"{item['bank']} "

                                f"{item['rate']:.2f}% "

                                f"({diff_text})\n"


                            )



                    else:



                        condition_answer += (

                            "조건을 만족하는 은행이 없습니다."

                        )





                elif rate_condition["type"] == "LOWER":



                    target_rate = (

                        base_rate

                        -

                        rate_condition["value"]

                    )



                    candidates = [


                        x

                        for x in bank_best_rates

                        if (

                            x["rate"]

                            <=

                            target_rate

                        )

                        and

                        normalize(x["bank"])

                        !=

                        normalize(target_bank)

                    ]



                    candidates.sort(

                        key=lambda x:

                            x["rate"],

                        reverse=True

                    )



                    condition_answer = (


                        f"📉 {target_bank} 대비 "

                        f"{rate_condition['value']:.2f}%p 이상 낮은 은행\n\n"


                        f"기준금리 : {base_rate:.2f}%\n"

                        f"조건금리 : {target_rate:.2f}% 이하\n\n"


                    )





                    if candidates:



                        for idx,item in enumerate(

                            candidates[:10],

                            start=1

                        ):



                            diff = round(

                                base_rate

                                -

                                item["rate"],

                                2

                            )



                            diff_text = (


                                f'<span class="rate-change decrease">'

                                f'▲{diff:.2f}%p'

                                f'</span>'


                            )



                            condition_answer += (


                                f"{idx}. "

                                f"{item['bank']} "

                                f"{item['rate']:.2f}% "

                                f"({diff_text})\n"


                            )



                    else:



                        condition_answer += (

                            "조건을 만족하는 은행이 없습니다."

                        )

# ===================================
# SBRateBot V4 app.py
# 8/20
# ===================================



        # -------------------------------
        # 은행 비교 검색 V5.2
        # BANK_COMPARE 우선 처리
        # -------------------------------


        if (


            intent == "BANK_COMPARE"


            and


            target_bank


        ):


            if bank_analysis:



                base_rate = bank_analysis["rate"]



                bank_best_rates = get_bank_best_rates(

                    products

                )



                higher = [


                    x


                    for x in bank_best_rates


                    if x["rate"] > base_rate


                    and


                    normalize(x["bank"])

                    !=

                    normalize(target_bank)


                ]



                higher.sort(

                    key=lambda x:

                        x["rate"],

                    reverse=True

                )



                answer = (


                    f"📈 {target_bank.replace('저축은행','')}보다 높은 금리 TOP5\n\n"


                )



                if higher:


                    for item in higher[:5]:


                        answer += (


                            f"{item['bank']} "

                            f"{item['rate']:.2f}% "

                            f"(+{item['rate'] - base_rate:.2f}%p)\n"


                        )


                else:


                    answer += (


                        "현재 기준 더 높은 금리 상품이 없습니다."


                    )



            else:


                answer = (


                    f"{target_bank} 은행 정보를 찾을 수 없습니다."


                )





                # -------------------------------
        # 금리 차이 조건 검색 결과 우선 적용 V4.5.1
        # -------------------------------


        elif condition_answer:


            answer = condition_answer





                # -------------------------------
        # 경쟁력 개선 전략 분석 V5.4
        #
        # 예:
        # 우리금융 어떻게 해야돼
        # 경쟁력 개선방안 알려줘
        # 금리 전략 알려줘
        # -------------------------------


        elif (

            not condition_answer

            and

            intent == "STRATEGY_ANALYSIS"

            and

            target_bank

        ):


            if bank_analysis:


                rate = bank_analysis["rate"]

                rank = bank_analysis["rank"]

                total = bank_analysis["total"]



                top10 = sorted(

                    products,

                    key=lambda x: x["rate"],

                    reverse=True

                )[:10]



                top10_avg = sum(

                    x["rate"]

                    for x in top10

                ) / len(top10)



                top10_gap = rate - top10_avg



                if top10_gap < 0:


                    gap_text = (

                        f'<span class="rate-change decrease">'

                        f'▲{abs(top10_gap):.2f}%p'

                        f'</span>'

                    )


                elif top10_gap > 0:


                    gap_text = (

                        f'<span class="rate-change increase">'

                        f'+{top10_gap:.2f}%p'

                        f'</span>'

                    )


                else:


                    gap_text = "0.00%p"



                answer = (

                    f"■ {bank_analysis['bank'].replace('저축은행','')} 경쟁력 개선 전략\n\n"

                    f"기준기간 : {search_period}\n\n"

                    f"현재금리 : {rate:.2f}%\n\n"

                    f"시장순위 : {rank}위 / {total}개사\n\n"

                    f"TOP10 평균금리 : {top10_avg:.2f}%\n\n"

                    f"TOP10 대비 : {gap_text}\n\n"


                    "📌 개선 방향\n\n"

                    "1. 대표상품 금리 경쟁력 강화\n"

                    "- TOP10 진입을 위해 핵심 상품 금리 개선 검토 필요\n\n"


                    "2. 주력상품 집중 전략\n"

                    "- 회전형·비대면 상품 중심 경쟁력 확보 필요\n\n"


                    "3. 시장 대응 전략\n"

                    "- 경쟁 저축은행 금리 변동 모니터링 및 탄력 대응 필요\n\n"


                    "4. 고객 확보 전략\n"

                    "- 금리뿐 아니라 우대조건·채널 경쟁력을 함께 강화 필요"

                )


            if bank_analysis:


                rate = bank_analysis["rate"]

                rank = bank_analysis["rank"]

                total = bank_analysis["total"]



                top10 = sorted(

                    products,

                    key=lambda x: x["rate"],

                    reverse=True

                )[:10]



                top10_avg = sum(

                    x["rate"]

                    for x in top10

                ) / len(top10)



                top10_gap = rate - top10_avg



                if top10_gap < 0:


                    gap_text = (

                        f'<span class="rate-change decrease">'

                        f'▲{abs(top10_gap):.2f}%p'

                        f'</span>'

                    )


                elif top10_gap > 0:


                    gap_text = (

                        f'<span class="rate-change increase">'

                        f'+{top10_gap:.2f}%p'

                        f'</span>'

                    )


                else:


                    gap_text = "0.00%p"





                answer = (

                    f"■ {bank_analysis['bank'].replace('저축은행','')} 경쟁력 개선 전략\n\n"

                    f"기준기간 : {search_period}\n\n"

                    f"현재금리 : {rate:.2f}%\n\n"

                    f"시장순위 : {rank}위 / {total}개사\n\n"

                    f"TOP10 평균금리 : {top10_avg:.2f}%\n\n"

                    f"TOP10 대비 : {gap_text}\n\n"


                    "📌 개선 방향\n\n"


                    "1. 대표상품 금리 경쟁력 강화\n"

                    "- TOP10 진입을 위해 핵심 상품 금리 개선 검토 필요\n\n"


                    "2. 주력상품 집중 전략\n"

                    "- 회전형·비대면 상품 중심 경쟁력 확보 필요\n\n"


                    "3. 시장 대응 전략\n"

                    "- 경쟁 저축은행 금리 변동 모니터링 및 탄력 대응 필요\n\n"


                    "4. 고객 확보 전략\n"

                    "- 금리뿐 아니라 우대조건·채널 경쟁력을 함께 강화 필요"

                )







        # -------------------------------
        # 은행 경쟁력 분석 V5.0
        # 시장 위치 / TOP10 대비 / 평가 / 비교 TOP5
        # -------------------------------


        elif (

            not condition_answer

            and

            intent == "COMPETITIVENESS"

            and

            target_bank

        ):


            if bank_analysis:


                gap = bank_analysis["avg_gap"]

                rate = bank_analysis["rate"]

                rank = bank_analysis["rank"]

                total = bank_analysis["total"]


                # -------------------------------
                # 시장 포지션 판단
                # -------------------------------

                if rank <= 15:

                    market_position = "상위권"


                elif rank <= 50:

                    market_position = "중위권"


                else:

                    market_position = "하위권"



                # -------------------------------
                # TOP10 평균 계산
                # -------------------------------

                top10 = sorted(

                    products,

                    key=lambda x: x["rate"],

                    reverse=True

                )[:10]


                top10_avg = sum(

                    x["rate"]

                    for x in top10

                ) / len(top10)



                top10_gap = rate - top10_avg



                # -------------------------------
                # 평균 대비 표시
                # -------------------------------

                if gap > 0:

                    gap_text = (

                        f'<span class="rate-change increase">'
                        f'+{gap:.2f}%p'
                        f'</span>'

                    )


                elif gap < 0:

                    gap_text = (

                        f'<span class="rate-change decrease">'
                        f'▲{abs(gap):.2f}%p'
                        f'</span>'

                    )


                else:

                    gap_text = "0.00%p"



                # -------------------------------
                # TOP10 대비 표시
                # -------------------------------

                if top10_gap > 0:

                    top10_gap_text = (

                        f'<span class="rate-change increase">'
                        f'+{top10_gap:.2f}%p'
                        f'</span>'

                    )


                elif top10_gap < 0:

                    top10_gap_text = (

                        f'<span class="rate-change decrease">'
                        f'▲{abs(top10_gap):.2f}%p'
                        f'</span>'

                    )


                else:

                    top10_gap_text = "0.00%p"



                # -------------------------------
                # 평가 문구
                # -------------------------------

                if gap >= 0:

                    evaluation = (

                        "시장 평균 대비 금리 경쟁력을 확보하고 있습니다."

                    )

                elif top10_gap >= -0.3:

                    evaluation = (

                        "시장 평균 대비 양호하나 TOP10 대비 개선 여지가 있습니다."

                    )

                else:

                    evaluation = (

                        "시장 평균 대비 낮은 금리 수준으로 금리 경쟁력 개선이 필요합니다."

                    )



                # -------------------------------
                # 높은 금리 TOP5
                # -------------------------------

                higher = [

                    x

                    for x in get_bank_best_rates(products)

                    if (

                        x["rate"] > rate

                    )

                    and

                    normalize(x["bank"])

                    !=

                    normalize(target_bank)

                ]


                higher.sort(

                    key=lambda x:

                    x["rate"],

                    reverse=True

                )



                higher_text = ""


                for item in higher[:5]:

                    diff = round(

                        item["rate"]

                        - rate,

                        2

                    )

                    higher_text += (

                        f"{item['bank']} "
                        f"{item['rate']:.2f}% "
                        f"(+{diff:.2f}%p)\n"

                    )



                # -------------------------------
                # 낮은 금리 TOP5
                # -------------------------------

                lower = [

                    x

                    for x in get_bank_best_rates(products)

                    if (

                        x["rate"] < rate

                    )

                    and

                    normalize(x["bank"])

                    !=

                    normalize(target_bank)

                ]


                lower.sort(

                    key=lambda x:

                    x["rate"],

                    reverse=True

                )



                lower_text = ""


                for item in lower[:5]:

                    diff = round(

                        rate

                        -

                        item["rate"],

                        2

                    )

                    lower_text += (

                        f"{item['bank']} "
                        f"{item['rate']:.2f}% "
                        f"(▲{diff:.2f}%p)\n"

                    )



                answer = (

                    f"■ {bank_analysis['bank'].replace('저축은행','')} 경쟁력 분석\n\n"

                    f"기준기간 : {search_period}\n\n"

                    f"현재금리 : {rate:.2f}%\n\n"

                    f"시장순위 : {rank}위 / {total}개사\n\n"

                    f"시장 위치 : {market_position}\n\n"

                    f"평균금리 대비 : {gap_text}\n\n"

                    f"TOP10 평균금리 : {top10_avg:.2f}%\n\n"

                    f"TOP10 대비 : {top10_gap_text}\n\n"

                    f"평가 : {evaluation}\n\n"

                    f"📈 {target_bank}보다 높은 금리 TOP5\n\n"

                    f"{higher_text}\n"

                    f"📉 {target_bank}보다 낮은 금리 TOP5\n\n"

                    f"{lower_text}"

                )

# ===================================
# SBRateBot V4 app.py
# 9/20
# ===================================


        # -------------------------------
        # 전체 시장현황 검색
        # -------------------------------


        if (


            not bank_analysis


            and


            any(


                x in question


                for x in [


                    "시장현황",


                    "시장 현황",


                    "시장상황",


                    "금리 상황",


                    "금리현황",


                    "금리 현황"


                ]


            )


        ):



            highest = max(


                products,


                key=lambda x:


                    x["rate"]


            )



            lowest = min(


                products,


                key=lambda x:


                    x["rate"]


            )



            avg_rate = sum(


                x["rate"]


                for x in products


            ) / len(products)





            spread = (


                highest["rate"]


                -


                lowest["rate"]


            )





            highest_gap = (


                highest["rate"]


                -


                avg_rate


            )





            lowest_gap = (


                lowest["rate"]


                -


                avg_rate


            )





            if highest_gap >= 0:



                highest_gap_text = (



                    f'<span class="rate-change increase">'


                    f'+{highest_gap:.2f}%p'


                    f'</span>'


                )



            else:



                highest_gap_text = (



                    f'<span class="rate-change decrease">'


                    f'▲{abs(highest_gap):.2f}%p'


                    f'</span>'


                )





            if lowest_gap < 0:



                lowest_gap_text = (



                    f'<span class="rate-change decrease">'


                    f'▲{abs(lowest_gap):.2f}%p'


                    f'</span>'


                )



            else:



                lowest_gap_text = (



                    f'<span class="rate-change increase">'


                    f'+{lowest_gap:.2f}%p'


                    f'</span>'


                )





            answer = (



                f"■ 정기예금 시장현황\n\n"



                f"기준기간 : {search_period}\n\n"



                f"상품 수 : {len(products)}개\n\n"



                f"최고금리 : {highest['rate']:.2f}%\n"


                f"최고상품 : {highest['bank']} / {highest['product']}\n\n"



                f"평균금리 : {avg_rate:.2f}%\n\n"



                f"최저금리 : {lowest['rate']:.2f}%\n"


                f"최저상품 : {lowest['bank']} / {lowest['product']}\n\n"



                f"최고금리-평균금리 : {highest_gap_text}<br>"


                f"최저금리-평균금리 : {lowest_gap_text}"



            )





        # -------------------------------
        # 은행 시장현황 검색
        # -------------------------------


        if (


            bank_analysis


            and


            any(


                x in question


                for x in [


                    "시장현황",


                    "현황",


                    "상황",


                    "시장",


                    "순위",


                ]


            )


        ):



            gap = bank_analysis["avg_gap"]





            if gap > 0:



                gap_text = (


                    f'<span class="rate-change increase">'


                    f'+{gap:.2f}%p'


                    f'</span>'


                )



            elif gap < 0:



                gap_text = (


                    f'<span class="rate-change decrease">'


                    f'▲{abs(gap):.2f}%p'


                    f'</span>'


                )



            else:



                gap_text = "0.00%p"

# ===================================
# SBRateBot V4 app.py
# 10/20
# ===================================


            answer = (


                f"■ {bank_analysis['bank']} 시장현황\n\n"


                f"기준기간 : {search_period}\n\n"


                f"대표상품 : {bank_analysis['product']}\n"


                f"현재금리 : {bank_analysis['rate']:.2f}%\n\n"


                f"시장순위 : {bank_analysis['rank']}위 / {bank_analysis['total']}개\n"


                f"평균금리 대비 : {gap_text}"


            )





               # -------------------------------
        # 은행 경쟁력 분석 V5.1
        # 평균금리 + TOP10 대비 평가 반영
        # -------------------------------


        elif (


            not condition_answer


            and


            bank_analysis


            and


            any(


                x in question


                for x in [


                    "경쟁력",


                    "경쟁",


                    "비교",


                    "어때",


                    "괜찮",


                    "괜찮아",


                    "평가",


                    "위치"


                ]


            )


        ):



            gap = bank_analysis["avg_gap"]





            top10_gap = bank_analysis["top10_gap"]





            if gap > 0:



                gap_text = (


                    f'<span class="rate-change increase">'


                    f'+{gap:.2f}%p'


                    f'</span>'


                )





                if top10_gap >= 0:



                    evaluation = (


                        "시장 평균 및 TOP10 대비 높은 금리 수준으로 "


                        "금리 경쟁력이 우수합니다."


                    )



                else:



                    evaluation = (


                        "시장 평균 대비 금리 경쟁력은 확보하고 있으나 "


                        "TOP10 대비 금리 격차가 있어 추가 개선이 필요합니다."


                    )







            elif gap < 0:



                gap_text = (


                    f'<span class="rate-change decrease">'


                    f'▲{abs(gap):.2f}%p'


                    f'</span>'


                )





                evaluation = (


                    "시장 평균 대비 낮은 금리 수준으로 "


                    "금리 경쟁력 개선이 필요합니다."


                )







            else:



                gap_text = "0.00%p"





                evaluation = (


                    "시장 평균 수준의 금리 경쟁력을 보이고 있습니다."


                )





            answer = (


                f"■ {bank_analysis['bank']} 경쟁력 분석\n\n"


                f"기준기간 : {search_period}\n\n"


                f"현재금리 : {bank_analysis['rate']:.2f}%\n\n"


                f"시장순위 : "


                f"{bank_analysis['rank']}위 / "


                f"{bank_analysis['total']}개사\n\n"


                f"시장 위치 : "


                f"{bank_analysis['position_text']}\n\n"


                f"평균금리 대비 : "


                f"{gap_text}\n\n"


                f"TOP10 평균금리 : "


                f"{bank_analysis['top10_avg']:.2f}%\n\n"


                f"TOP10 대비 : "


                f"{format_change(bank_analysis['top10_gap'])}\n\n"


                f"평가 : "


                f"{evaluation}"


            )





            # -------------------------------
            # 경쟁사 비교 TOP5 추가
            # -------------------------------


            if bank_analysis.get("higher"):



                answer += (


                    "\n\n📈 "


                    f"{bank_analysis['bank']}보다 높은 금리 TOP5\n\n"


                )



                for item in bank_analysis["higher"][:5]:



                    diff = round(


                        item["rate"]


                        -


                        bank_analysis["rate"],


                        2


                    )



                    diff_text = (


                        f'<span class="rate-change increase">'


                        f'+{diff:.2f}%p'


                        f'</span>'


                    )



                    answer += (


                        f"{item['bank']} "


                        f"{item['rate']:.2f}% "


                        f"({diff_text})<br>"


                    )





            if bank_analysis.get("lower"):



                answer += (


                    "\n\n📉 "


                    f"{bank_analysis['bank']}보다 낮은 금리 TOP5\n\n"


                )



                for item in bank_analysis["lower"][:5]:



                    diff = round(


                        bank_analysis["rate"]


                        -


                        item["rate"],


                        2


                    )



                    diff_text = (


                        f'<span class="rate-change decrease">'


                        f'▲{diff:.2f}%p'


                        f'</span>'


                    )



                    answer += (


                        f"{item['bank']} "


                        f"{item['rate']:.2f}% "


                        f"({diff_text})<br>"


                    )

# ===================================
# SBRateBot V4 app.py
# 11/20
# ===================================


        # -------------------------------
        # 최고 금리
        # -------------------------------


        elif any(


            x in question


            for x in [


                "최고금리",


                "최고 금리",


                "가장 높은",


                "높은 금리"


            ]


        ):



            item = max(


                products,


                key=lambda x:


                    x["rate"]


            )



            rank = get_market_bank_rank(


                products,


                item["bank"]


            )



            answer = (


                f"📈 {search_period} 최고금리\n\n"



                f"은행 : {item['bank']}\n"


                f"상품 : {item['product']}\n"


                f"최고금리 : {item['rate']:.2f}%\n"


                f"시장순위 : {rank['rank']}위 / {rank['total']}개사"



            )





        
        # -------------------------------
        # 최저 금리
        # -------------------------------


        elif any(


            x in question


            for x in [


                "최저금리",


                "최저 금리",


                "가장 낮은",


                "낮은 금리"


            ]


        ):



            item = min(


                products,


                key=lambda x:


                    x["rate"]


            )



            rank = get_market_bank_rank(


                products,


                item["bank"]


            )



            answer = (


                f"📉 {search_period} 최저금리\n\n"



                f"은행 : {item['bank']}\n"


                f"상품 : {item['product']}\n"


                f"최저금리 : {item['rate']:.2f}%\n"


                f"시장순위 : {rank['rank']}위 / {rank['total']}개사"



            )





        # -------------------------------
        # TOP 검색
        # 예) 3개월 TOP5
        # -------------------------------


        elif (


            "TOP"


            in question.upper()



            or



            "상위"


            in question


        ):



            count = extract_number(


                question


            )



            if not count:


                count = 5





            items = get_top_products(


                products,


                int(count)


            )



            answer = (


                f"🏆 {search_period} 금리 TOP {int(count)}\n\n"


            )



            for idx,item in enumerate(


                items,


                start=1


            ):



                answer += (


                    f"{idx}. "


                    f"{item['bank']} "


                    f"{item['product']} "


                    f"{item['rate']:.2f}%\n"


                )

                # ===================================
# SBRateBot V4 app.py
# 12/20
# ===================================


        # -------------------------------
        # 하위 검색
        # -------------------------------


        elif (


            "하위"


            in question



            or



            "낮은순"


            in question


        ):



            count = extract_number(


                question


            )



            if not count:


                count = 5





            items = get_bottom_products(


                products,


                int(count)


            )



            answer = (


                f"📉 {search_period} 낮은 금리 TOP {int(count)}\n\n"


            )



            for idx,item in enumerate(


                items,


                start=1


            ):



                answer += (


                    f"{idx}. "


                    f"{item['bank']} "


                    f"{item['product']} "


                    f"{item['rate']:.2f}%\n"


                )





        # -------------------------------
        # 금리 이상 검색
        # 예) 3% 이상
        # -------------------------------


        elif (


            "이상"


            in question



            and



            extract_number(question)


        ):



            rate = extract_number(


                question


            )



            items = filter_over_rate(


                products,


                rate


            )



            answer = (


                f"📌 {search_period} {rate}% 이상 상품\n\n"


            )



            for item in items[:10]:


                answer += (


                    f"{item['bank']} "


                    f"{item['product']} "


                    f"{item['rate']:.2f}%\n"


                )





        # -------------------------------
        # 금리 이하 검색
        # 예) 3% 이하
        # -------------------------------


        elif (


            "이하"


            in question



            and



            extract_number(question)


        ):



            rate = extract_number(


                question


            )



            items = filter_under_rate(


                products,


                rate


            )



            answer = (


                f"📌 {search_period} {rate}% 이하 상품\n\n"


            )



            for item in items[:10]:


                answer += (


                    f"{item['bank']} "


                    f"{item['product']} "


                    f"{item['rate']:.2f}%\n"


                )





        # -------------------------------
        # 은행 비교
        # 예) KB vs 신한
        # -------------------------------


        elif (


            "vs"


            in q



            or



            "비교"


            in question


        ):



            banks = []



            for bank in FINANCIAL_BANKS + [


                "KB저축은행",


                "신한저축은행",


                "SBI저축은행",


                "OK저축은행"


            ]:



                if normalize(bank) in q:


                    banks.append(bank)



            if len(banks) >= 2:



                result = compare_two_banks(


                    products,


                    banks[0],


                    banks[1]


                )



                if result:



                    answer = (


                        "⚖️ 은행 비교\n\n"


                        f"{banks[0]}\n"


                        f"금리 : {result['bank1']['rate']:.2f}%\n\n"


                        f"{banks[1]}\n"


                        f"금리 : {result['bank2']['rate']:.2f}%\n\n"


                        f"차이 : "


                        f"{result['difference']:.2f}%p"


                    )

# ===================================
# SBRateBot V4 app.py
# 13/20
# ===================================

                # -------------------------------
        # 경쟁력 개선 전략 분석 V5.5
        #
        # 예:
        # 우리금융 어떻게 해야돼
        # 경쟁력 개선방안 알려줘
        # 금리 전략 알려줘
        #
        # TOP10 진입 목표금리 / 필요 개선폭 추가
        # -------------------------------


        elif (

            not condition_answer

            and

            intent == "STRATEGY_ANALYSIS"

            and

            target_bank

        ):


            if bank_analysis:


                rate = bank_analysis["rate"]

                rank = bank_analysis["rank"]

                total = bank_analysis["total"]



                top10 = sorted(

                    products,

                    key=lambda x:x["rate"],

                    reverse=True

                )[:10]



                top10_avg = sum(

                    x["rate"]

                    for x in top10

                ) / len(top10)



                top10_gap = rate - top10_avg



                # -------------------------------
                # TOP10 진입 목표금리 계산 V5.5
                #
                # 시장 TOP10 마지막 금리 기준
                # -------------------------------


                bank_best_rates = get_bank_best_rates(

                    products

                )



                top10_rates = sorted(

                    [

                        x["rate"]

                        for x in bank_best_rates

                    ],

                    reverse=True

                )



                if len(top10_rates) >= 10:


                    target_rate = top10_rates[9]


                else:


                    target_rate = top10_rates[-1]



                target_gap = target_rate - rate



                if target_gap > 0:


                    target_gap_text = (

                        f'<span class="rate-change increase">'

                        f'+{target_gap:.2f}%p'

                        f'</span>'

                    )


                elif target_gap < 0:


                    target_gap_text = (

                        f'<span class="rate-change decrease">'

                        f'▲{abs(target_gap):.2f}%p'

                        f'</span>'

                    )


                else:


                    target_gap_text = "0.00%p"





                # -------------------------------
                # TOP10 대비 표시
                # -------------------------------


                if top10_gap < 0:


                    gap_text = (

                        f'<span class="rate-change decrease">'

                        f'▲{abs(top10_gap):.2f}%p'

                        f'</span>'

                    )


                else:


                    gap_text = (

                        f'<span class="rate-change increase">'

                        f'+{top10_gap:.2f}%p'

                        f'</span>'

                    )





                # -------------------------------
                # 개선 전략 자동 문구
                # -------------------------------


                if target_gap >= 0.6:


                    strategy_text = (

                        "- TOP10 진입을 위해 대표상품 금리 "

                        f"약 {target_gap:.2f}%p 수준의 개선 필요\n\n"

                    )


                elif target_gap >= 0.3:


                    strategy_text = (

                        "- 핵심 상품 중심의 금리 조정으로 "

                        "경쟁력 개선 검토 필요\n\n"

                    )


                else:


                    strategy_text = (

                        "- 현재 금리 수준에서 소폭 조정으로 "

                        "시장 경쟁력 확보 가능\n\n"

                    )





                answer = (

                    f"■ {bank_analysis['bank'].replace('저축은행','')} 경쟁력 개선 전략\n\n"

                    f"기준기간 : {search_period}\n\n"

                    f"현재금리 : {rate:.2f}%\n\n"

                    f"시장순위 : {rank}위 / {total}개사\n\n"

                    f"TOP10 평균금리 : {top10_avg:.2f}%\n\n"

                    f"TOP10 진입 목표금리 : {target_rate:.2f}%\n\n"

                    f"필요 개선폭 : {target_gap_text}\n\n"

                    f"TOP10 대비 : {gap_text}\n\n"


                    "📌 개선 방향\n\n"


                    "1. 대표상품 금리 경쟁력 강화\n"

                    + strategy_text +


                    "2. 주력상품 집중 전략\n"

                    "- 회전형·비대면 상품 중심 경쟁력 확보 필요\n\n"


                    "3. 시장 대응 전략\n"

                    "- 경쟁 저축은행 금리 변동 모니터링 및 탄력 대응 필요\n\n"


                    "4. 고객 확보 전략\n"

                    "- 금리뿐 아니라 우대조건·채널 경쟁력을 함께 강화 필요\n\n"

                    "5. 차별화 전략\n"

                    "- 단순 금리 경쟁보다 상품 구조 및 고객 혜택 차별화 필요"

                )





        # -------------------------------
        # 우리금융 자연어 경쟁력 분석 V4.6
        # -------------------------------


        elif (


            not condition_answer


            and



            resolve_bank_name(question) == "우리금융"



            and



            intent == "COMPETITIVENESS"


        ):



            woori_items = find_bank_products(


                products,


                "우리금융저축은행"


            )



            if woori_items:



                woori_best = max(


                    woori_items,


                    key=lambda x:


                        x["rate"]


                )



                rank = get_market_bank_rank(


                    products,


                    woori_best["bank"]


                )



                avg_rate = sum(


                    x["rate"]


                    for x in products


                ) / len(products)





                bank_best_rates = get_bank_best_rates(


                    products


                )



                higher = [



                    x



                    for x in bank_best_rates



                    if (



                        x["rate"]



                        >



                        woori_best["rate"]



                    )



                    and



                    normalize(x["bank"])



                    !=



                    normalize(woori_best["bank"])



                ]





                lower = [



                    x



                    for x in bank_best_rates



                    if (



                        x["rate"]



                        <



                        woori_best["rate"]



                    )



                    and



                    normalize(x["bank"])



                    !=



                    normalize(woori_best["bank"])



                ]





                higher.sort(


                    key=lambda x: x["rate"],


                    reverse=True


                )





                lower.sort(


                    key=lambda x: x["rate"]


                )





                gap = round(


                    woori_best["rate"]


                    -


                    avg_rate,


                    2


                )





                if gap > 0:



                    gap_text = (



                        f'<span class="rate-change increase">'



                        f'+{gap:.2f}%p'



                        f'</span>'



                    )



                    evaluation = (



                        "시장 평균 대비 높은 금리로 "



                        "금리 경쟁력이 양호합니다."



                    )





                elif gap < 0:



                    gap_text = (



                        f'<span class="rate-change decrease">'



                        f'▲{abs(gap):.2f}%p'



                        f'</span>'



                    )



                    evaluation = (



                        "시장 평균 대비 낮은 금리로 "



                        "금리 경쟁력 개선이 필요합니다."



                    )





                else:



                    gap_text = "0.00%p"



                    evaluation = (



                        "시장 평균 수준의 금리입니다."



                    )



# ===================================
# SBRateBot V4 app.py
# 14/20
# ===================================


                answer = (


                    "🏦 우리금융저축은행 경쟁력 분석\n\n"


                    f"기준기간 : {search_period}\n\n"


                    f"현재금리 : {woori_best['rate']:.2f}%\n\n"


                    f"시장순위 : {rank['rank']}위 / {rank['total']}개사\n\n"


                    f"시장 위치 : {market_position}\n\n"


                    f"평균금리 대비 : {gap_text}\n\n"


                    f"평가 : {evaluation}\n\n"


                    f"📈 우리보다 높은 금리 : {len(higher)}개사\n"


                    f"📉 우리보다 낮은 금리 : {len(lower)}개사\n\n"


                )





                if higher:


                    answer += "\n📈 우리보다 높은 경쟁사 TOP5\n\n"



                    for item in higher[:5]:


                        diff = round(


                            item["rate"]


                            -


                            woori_best["rate"],


                            2


                        )



                        if diff > 0:


                            diff_text = (


                                f'<span class="rate-change increase">'


                                f'+{diff:.2f}%p'


                                f'</span>'


                            )


                        elif diff < 0:


                            diff_text = (


                                f'<span class="rate-change decrease">'


                                f'▲{abs(diff):.2f}%p'


                                f'</span>'


                            )


                        else:


                            diff_text = "0.00%p"




                        answer += (


                            f"{item['bank']} "


                            f"{item['rate']:.2f}% "


                            f"{diff_text}<br>"


                        )






                if lower:


                    answer += "\n📉 우리보다 낮은 경쟁사 TOP5\n\n"



                    for item in lower[:5]:


                        diff = round(


                            woori_best["rate"]


                            -


                            item["rate"],


                            2


                        )



                        if diff > 0:


                            diff_text = (


                                f'<span class="rate-change decrease">'


                                f'▲{diff:.2f}%p'


                                f'</span>'


                            )


                        elif diff < 0:


                            diff_text = (


                                f'<span class="rate-change increase">'


                                f'+{abs(diff):.2f}%p'


                                f'</span>'


                            )


                        else:


                            diff_text = "0.00%p"




                        answer += (


                            f"{item['bank']} "


                            f"{item['rate']:.2f}% "


                            f"{diff_text}<br>"


                        )

# ===================================
# SBRateBot V4 app.py
# 15/20
# ===================================


        # -------------------------------
        # 은행 비교 처리 V4.6
        #
        # COMPARE_HIGH
        # - 기준 은행보다 높은 금리
        #
        # COMPARE_LOW
        # - 기준 은행보다 낮은 금리
        #
        # COMPARE_SAME
        # - 기준 은행과 동일 금리
        #
        # -------------------------------


        print(

            "COMPARE CHECK:",

            condition_answer,

            target_bank,

            intent

        )



        if (

            not condition_answer

            and

            target_bank

            and

            intent in [

                "COMPARE_HIGH",

                "COMPARE_LOW",

                "COMPARE_SAME"

            ]

        ):


            answer = ""


            target_bank_full = resolve_bank_name(

                question

            )


            print(

                "COMPARE TARGET FULL:",

                target_bank_full

            )



            target_items = find_bank_products(

                products,

                target_bank_full

            )



            print(

                "COMPARE TARGET ITEMS:",

                len(target_items),

                target_items[:3]

            )



            if target_items:


                target_rate = max(

                    x["rate"]

                    for x in target_items

                )



                rank = get_market_bank_rank(

                    products,

                    target_bank_full

                )



                # -------------------------------
                # 시장 평균금리 계산
                # -------------------------------


                valid_rates = []


                for item in products:


                    rate = float(

                        item.get("top_12m")

                        or item.get("rate")

                        or 0

                    )


                    if rate > 0:

                        valid_rates.append(rate)



                if valid_rates:


                    market_average = (

                        sum(valid_rates)

                        /

                        len(valid_rates)

                    )


                else:


                    market_average = 0



                                # -------------------------------
                # 은행별 최고금리 생성
                # (은행명 정규화 + 우리저축은행/우리금융 분리)
                # -------------------------------

                bank_best_rates = {}

                for item in products:

                    raw_bank = (
                        item.get("bank")
                        or item.get("bank_name")
                        or ""
                    ).strip()

                    rate = float(
                        item.get("top_12m")
                        or item.get("rate")
                        or item.get("max_rate")
                        or 0
                    )

                    if rate <= 0:
                        continue

                                    # -------------------------------
                # 은행별 최고금리 생성
                # 우리저축은행 / 우리금융저축은행 분리
                # -------------------------------


                bank_best_rates = {}


                for item in products:


                    raw_bank = (

                        item.get("bank")

                        or item.get("bank_name")

                        or ""

                    ).strip()



                    rate = float(

                        item.get("top_12m")

                        or item.get("rate")

                        or item.get("max_rate")

                        or 0

                    )



                    if rate <= 0:

                        continue



                    # -------------------------------
                    # 우리저축은행 / 우리금융저축은행 분리
                    # -------------------------------


                    if raw_bank == "우리저축은행":


                        bank = "우리저축은행"



                    elif raw_bank == "우리금융저축은행":


                        bank = "우리금융저축은행"



                    else:


                        bank = resolve_bank_name(

                            raw_bank

                        )



                    if not bank:

                        continue



                    if (

                        bank not in bank_best_rates

                        or rate > bank_best_rates[bank]

                    ):


                        bank_best_rates[bank] = rate





                # -------------------------------
                # 은행별 최고금리 순위
                # -------------------------------


                bank_rank_list = sorted(

                    bank_best_rates.items(),

                    key=lambda x: x[1],

                    reverse=True

                )





                print("==============================")

                print(

                    "은행별 최고금리 TOP10:",

                    bank_rank_list[:10]

                )


                print(

                    "은행 개수:",

                    len(bank_rank_list)

                )


                print("==============================")


                print(

                    "우리 관련 은행:",

                    [

                        item

                        for item in bank_rank_list

                        if "우리" in item[0]

                    ]

                )


                print("==============================")





                # -------------------------------
                # 우리금융저축은행 시장순위 계산
                # -------------------------------


                market_rank = "-"


                market_total = len(

                    bank_rank_list

                )



                TARGET_BANK = "우리금융저축은행"




                for idx, (

                    bank_name,

                    rate

                ) in enumerate(

                    bank_rank_list,

                    start=1

                ):



                    if bank_name == TARGET_BANK:


                        market_rank = idx



                        print(

                            "우리금융저축은행 순위:",

                            idx,

                            (

                                bank_name,

                                rate

                            )

                        )


                        break




                if market_rank == "-":


                    print(

                        "우리금융저축은행 미확인"

                    )


                # -------------------------------
                # 디버그
                # -------------------------------

                print(
                    "\n=== 우리 관련 은행 ==="
                )

                for bank, rate in bank_rank_list:

                    if "우리" in bank:

                        print(
                            bank,
                            rate
                        )


                print(
                    "\n=== products 원본 ==="
                )

                for item in products:

                    bank = resolve_bank_name(
                        item.get("bank")
                        or item.get("bank_name")
                        or ""
                    )

                    if "우리" in bank:

                        print(
                            bank,
                            item.get("product"),
                            item.get("rate"),
                            item.get("top_12m")
                        )

                # -------------------------------
                # 우리금융저축은행 시장순위 계산
                # -------------------------------

                market_rank = "-"

                market_total = len(
                    bank_rank_list
                )

                TARGET_BANK = "우리금융저축은행"

                for idx, (
                    bank_name,
                    rate
                ) in enumerate(
                    bank_rank_list,
                    start=1
                ):

                    if (
                        resolve_bank_name(
                            bank_name
                        )
                        == TARGET_BANK
                    ):

                        market_rank = idx

                        print(
                            "우리금융저축은행 순위:",
                            idx,
                            (
                                bank_name,
                                rate
                            )
                        )

                        break


                if market_rank == "-":

                    print(
                        "우리금융저축은행을 찾지 못했습니다."
                    )



                # -------------------------------
                # 시장 평균 대비
                #
                # 증가 : +
                # 감소 : ▲
                #
                # 괄호 표시 통일
                # -------------------------------


                gap = round(

                    target_rate - market_average,

                    2

                )



                if gap > 0:


                    gap_text = (

                        f'<span class="rate-change increase">'

                        f'(+{gap:.2f}%p)'

                        f'</span>'

                    )


                elif gap < 0:


                    gap_text = (

                        f'<span class="rate-change decrease">'

                        f'(▲{abs(gap):.2f}%p)'

                        f'</span>'

                    )


                else:


                    gap_text = "(0.00%p)"



                # -------------------------------
                # 비교 대상 제외
                # -------------------------------


                bank_products = []



                for bank, rate in bank_best_rates.items():


                    if normalize(bank) == normalize(target_bank_full):

                        continue



                    bank_products.append({

                        "bank": bank,

                        "rate": rate

                    })



                bank_products.sort(

                    key=lambda x:x["rate"],

                    reverse=True

                )



                # -------------------------------
                # 비교 조건 처리
                # -------------------------------


                if intent == "COMPARE_SAME":


                    result = [

                        x

                        for x in bank_products

                        if x["rate"] == target_rate

                    ]


                    title = (

                        f"🔄 {target_bank_full} 동일 금리 은행"

                    )



                elif intent == "COMPARE_HIGH":


                    result = [

                        x

                        for x in bank_products

                        if x["rate"] > target_rate

                    ]


                    title = (

                        f"📈 {target_bank_full} 대비 높은 금리 은행"

                    )



                else:


                    result = [

                        x

                        for x in bank_products

                        if x["rate"] < target_rate

                    ]


                    title = (

                        f"📉 {target_bank_full} 대비 낮은 금리 은행"

                    )



                result.sort(

                    key=lambda x:x["rate"],

                    reverse=True

                )



                # -------------------------------
                # 동일 최고금리 은행
                #
                # 17 출력용
                # -------------------------------


                same_rate_result = [

                    x

                    for x in bank_products

                    if x["rate"] == target_rate

                ]



                same_rate_result.sort(

                    key=lambda x:x["bank"]

                )



                same_rate_count = (

                    len(same_rate_result)

                    +

                    1

                )



                print(

                    "COMPARE RESULT COUNT:",

                    len(result)

                )


                print(

                    "SAME RATE RESULT:",

                    same_rate_result[:5]

                )

                    

# ===================================
# SBRateBot V4 app.py
# 16/20
# ===================================


                # -------------------------------
                # 비교 대상 제외 후 은행 리스트 생성
                #
                # 기준:
                # - 은행별 최고금리 기준
                # - 비교 대상 은행 제외
                # -------------------------------


                bank_products = []


                for bank, rate in bank_best_rates.items():


                    if normalize(bank) == normalize(target_bank_full):

                        continue


                    bank_products.append({

                        "bank": bank,

                        "rate": rate

                    })



                # -------------------------------
                # 은행 금리 내림차순 정렬
                # -------------------------------


                bank_products.sort(

                    key=lambda x: x["rate"],

                    reverse=True

                )



                # -------------------------------
                # 비교 대상 로그
                # -------------------------------


                print("BANK PRODUCTS")


                for item in bank_products[:20]:

                    print(item)


                print(

                    "COMPARE TARGET BANK:",

                    target_bank_full

                )


                print(

                    "COMPARE TARGET RATE:",

                    target_rate

                )



                # -------------------------------
                # 비교 조건 처리
                #
                # COMPARE_HIGH
                # 기준 은행보다 높은 금리
                #
                # COMPARE_LOW
                # 기준 은행보다 낮은 금리
                #
                # COMPARE_SAME
                # 기준 은행과 동일 금리
                # -------------------------------


                if intent == "COMPARE_HIGH":


                    result = [

                        x

                        for x in bank_products

                        if x["rate"] > target_rate

                    ]


                    title = (

                        f"📈 {target_bank_full} 대비 높은 금리 은행"

                    )


                elif intent == "COMPARE_SAME":


                    result = [

                        x

                        for x in bank_products

                        if x["rate"] == target_rate

                    ]


                    title = (

                        f"🔄 {target_bank_full} 동일 금리 은행"

                    )


                else:


                    result = [

                        x

                        for x in bank_products

                        if x["rate"] < target_rate

                    ]


                    title = (

                        f"📉 {target_bank_full} 대비 낮은 금리 은행"

                    )



                # -------------------------------
                # 동일 금리 경쟁 은행
                #
                # 기준은행 제외
                #
                # COMPARE_HIGH 출력용
                # -------------------------------


                same_rate_result = [

                    x

                    for x in bank_products

                    if x["rate"] == target_rate

                ]


                same_rate_result.sort(

                    key=lambda x:x["bank"]

                )



                # 기준은행 포함 공동 1위 개수

                same_rate_count = len(same_rate_result) + 1



                # -------------------------------
                # 결과 금리순 정렬
                # -------------------------------


                result.sort(

                    key=lambda x:x["rate"],

                    reverse=True

                )



                # -------------------------------
                # 로그
                # -------------------------------


                print(

                    "COMPARE RESULT COUNT:",

                    len(result)

                )


                print(

                    "COMPARE RESULT SAMPLE:",

                    result[:5]

                )


                print(

                    "SAME RATE RESULT:",

                    same_rate_result[:5]

                )


                print(

                    "BANK BEST SAMPLE:",

                    bank_products[:10]

                )



                # -------------------------------
                # 기본 답변 생성
                # -------------------------------


                if intent == "COMPARE_HIGH":


                    if result:


                        answer = (

                            "📊 시장 모니터링 결과<br><br>"

                            f"{target_bank_full}보다 높은 금리를 제공하는 은행이 있습니다.<br><br>"

                            f"시장 최고금리 : {result[0]['rate']:.2f}%<br>"

                            f"{target_bank_full} 최고금리 : {target_rate:.2f}%<br>"

                            f"시장순위 : {rank['rank']}위 / {rank['total']}개사<br><br>"

                        )


                    else:


                        if same_rate_result:


                            answer = (

                                "🏆 시장 모니터링 결과<br><br>"

                                f"{target_bank_full}는 현재 시장 최고금리 공동 1위입니다.<br><br>"

                                f"시장 최고금리 : {target_rate:.2f}%<br>"

                                f"공동 1위 경쟁 은행 : {same_rate_count}개 은행<br><br>"

                            )


                        else:


                            answer = (

                                "🏆 시장 모니터링 결과<br><br>"

                                f"{target_bank_full}는 현재 시장 최고금리 단독 1위입니다.<br><br>"

                                f"시장 최고금리 : {target_rate:.2f}%<br>"

                                f"시장순위 : 1위 / {rank['total']}개사<br><br>"

                            )



                elif intent == "COMPARE_SAME":


                    answer = (

                        f"{title}<br><br>"

                        f"{target_bank_full} 최고금리 : {target_rate:.2f}%<br>"

                        f"시장순위 : {rank['rank']}위 / {rank['total']}개사<br>"

                        f"시장 평균 대비 : {gap_text}<br><br>"

                    )



                else:


                    answer = (

                        f"{title}<br><br>"

                        f"{target_bank_full} 최고금리 : {target_rate:.2f}%<br>"

                        f"시장순위 : {rank['rank']}위 / {rank['total']}개사<br>"

                        f"시장 평균 대비 : {gap_text}<br><br>"

                    )


# ===================================
# SBRateBot V4 app.py
# 17/20
# ===================================


                # -------------------------------
                # AI 비교 검색 결과 출력 V4.6
                #
                # COMPARE_HIGH
                # - 기준 은행보다 높은 금리 검색
                #
                # COMPARE_LOW
                # - 기준 은행보다 낮은 금리 검색
                #
                # COMPARE_SAME
                # - 기준 은행과 동일 금리 검색
                #
                # 금리 증감 표시 통일
                #
                # 증가 : 파란색 + 표시
                # 감소 : 빨간색 ▲ 표시
                #
                # 대시보드 / AI 응답 동일 기준
                # -------------------------------


                print(
                    "COMPARE RESULT:",
                    result[:10]
                )


                print(
                    "SAME RATE RESULT:",
                    same_rate_result[:10]
                )



                # -------------------------------
                # 비교 결과 출력
                # -------------------------------


                if result:


                    for idx, item in enumerate(

                        result[:10],

                        start=1

                    ):


                        diff = round(

                            item["rate"]

                            -

                            target_rate,

                            2

                        )



                        if diff > 0:


                            diff_text = (

                                f'<span class="rate-change increase">'

                                f'(+{diff:.2f}%p)'

                                f'</span>'

                            )


                        elif diff < 0:


                            diff_text = (

                                f'<span class="rate-change decrease">'

                                f'(▲{abs(diff):.2f}%p)'

                                f'</span>'

                            )


                        else:


                            diff_text = "(동일금리)"



                        answer += (

                            f"{idx}. "

                            f"{item['bank']} "

                            f"{item['rate']:.2f}% "

                            f"{diff_text}<br>"

                        )



                # -------------------------------
                # 동일 금리 결과
                #
                # COMPARE_SAME
                # -------------------------------


                elif intent == "COMPARE_SAME":


                    if same_rate_result:


                        answer += (

                            "<b>동일 최고금리 경쟁 은행</b><br><br>"

                        )


                        for idx, item in enumerate(

                            same_rate_result,

                            start=1

                        ):


                            answer += (

                                f"{idx}. "

                                f"{item['bank']} "

                                f"{item['rate']:.2f}% "

                                "(동일금리)<br>"

                            )


                    else:


                        answer += (

                            f"현재 {target_bank_full}와 "

                            "동일한 금리를 제공하는 은행은 없습니다.<br>"

                        )



                # -------------------------------
                # 높은 금리 없음
                #
                # 최고금리 유지 상태
                # -------------------------------


                elif intent == "COMPARE_HIGH":


                    answer += (

                        f"현재 {target_bank_full}보다 "

                        f"높은 금리를 제공하는 은행은 없습니다.<br>"

                    )


                    if same_rate_result:


                        answer += (

                            "<br><b>동일 최고금리 경쟁 은행</b><br>"

                        )


                        for idx, item in enumerate(

                            same_rate_result,

                            start=1

                        ):


                            answer += (

                                f"{idx}. "

                                f"{item['bank']} "

                                f"{item['rate']:.2f}% "

                                "(동일금리)<br>"

                            )



                # -------------------------------
                # 낮은 금리 없음
                # -------------------------------


                elif intent == "COMPARE_LOW":


                    answer += (

                        f"현재 {target_bank_full}보다 "

                        f"낮은 금리를 제공하는 은행은 없습니다.<br>"

                    )

# ===================================
# SBRateBot V4 app.py
# 18/20
# ===================================
                        
        # -------------------------------
        # Gemini 전략 분석 여부 판단 V4.9
        #
        # 전망 / 전략 / 보고서 / 운영방향 질문은
        # Gemini 전문 분석 처리
        #
        # 일반 상품 검색과 분리
        # -------------------------------


        gemini_required = any(


            x in question


            for x in [


                "전망",

                "예측",

                "전략",

                "보고서",

                "시장전망",

                "시장 전망",

                "금리전망",

                "금리 전망",

                "대응방향",

                "대응 방향",

                "운영방향",

                "운영 방향",

                "경쟁전략",

                "경쟁 전략",

                "상품전략",

                "상품 전략",

                "수신전략",

                "수신 전략",

                "향후",

                "앞으로",

                "어떻게 운영",

                "어떻게 가져가"


            ]


        )

        # -------------------------------
        # 은행명 금리 조회 우선 처리 V4.9
        # 은행명 입력 시 해당 은행 상품 먼저 검색
        # -------------------------------


        if not answer and target_bank:


            bank_products = find_bank_products(


                products,


                target_bank


            )



            if bank_products:


                bank_products.sort(


                    key=lambda x: x["rate"],


                    reverse=True


                )



                answer = (


                    f"📌 {search_period} {target_bank} 금리 검색 결과\n\n"


                )



                for item in bank_products[:10]:


                    bank_name = item["bank"]


                    product_name = item["product"]



                    # 상품명 앞 은행명 중복 제거
                    if product_name.startswith(bank_name):


                        product_name = (


                            product_name[len(bank_name):]


                            .strip()


                        )



                    answer += (


                        f"{bank_name} "


                        f"{product_name} "


                        f"{item['rate']:.2f}%\n"


                    )





                # -------------------------------
        # 일반 상품 검색
        #
        # 단순 상품명 / 금리 조회 처리
        # Gemini 분석 제외
        # -------------------------------


        if not answer and not gemini_required:


            result = search_product_keyword(


                products,


                question


            )



            if result:


                answer = (


                    f"📌 {search_period} 검색 결과\n\n"


                )



                for item in result[:10]:

                    join_target = item.get(
                        "join_target",
                        ""
                    )

                    # 줄바꿈 제거
                    join_target = (
                        join_target
                        .replace("\n", " ")
                        .replace("\r", " ")
                        .strip()
                    )


                    product_name = (
                        item.get(
                            "product",
                            ""
                        )
                        .replace("\n", " ")
                        .replace("\r", " ")
                        .strip()
                    )


                    if join_target:

                        answer += (

                            f"{item['bank']} "

                            f"{product_name} "

                            f"{join_target} "

                            f"{item['rate']:.2f}%\n"

                        )

                    else:

                        answer += (

                            f"{item['bank']} "

                            f"{product_name} "

                            f"{item['rate']:.2f}%\n"

                        )

        # -------------------------------
        # Gemini 전략 분석 V4.9
        #
        # 목적:
        # - 경영진 보고 수준 분석
        # - 단순 상품 나열 방지
        # - 시장 위치 기반 전략 제시
        # -------------------------------

        if gemini_required:

            try:

                avg_rate = sum(
                    x["rate"]
                    for x in products
                ) / len(products)

                highest = max(
                    products,
                    key=lambda x: x["rate"]
                )

                lowest = min(
                    products,
                    key=lambda x: x["rate"]
                )

                top10_rates = sorted(
                    products,
                    key=lambda x: x["rate"],
                    reverse=True
                )[:10]

                # -------------------------------
                # 우리금융 시장정보 생성
                # Gemini에게 실제 데이터 제공
                # -------------------------------

                bank_info = None

                if bank_analysis:

                    top10_avg = (
                        sum(x["rate"] for x in top10_rates)
                        / len(top10_rates)
                    )

                    bank_info = {

                        "은행명": target_bank,

                        "대표상품": bank_analysis.get("product"),

                        "현재금리": round(
                            bank_analysis["rate"],
                            2
                        ),

                        "시장순위": bank_analysis["rank"],

                        "전체은행수": bank_analysis["total"],

                        "시장평균금리": round(
                            avg_rate,
                            2
                        ),

                        "평균대비": round(
                            bank_analysis["avg_gap"],
                            2
                        ),

                        "TOP10평균금리": round(
                            top10_avg,
                            2
                        ),

                        "TOP10대비": round(
                            bank_analysis["rate"] - top10_avg,
                            2
                        ),

                        "시장위치(%)": round(
                            (
                                bank_analysis["rank"]
                                / bank_analysis["total"]
                            ) * 100,
                            1
                        )

                    }





                # -------------------------------
                # 우리금융 전략 분석 데이터
                #
                # Python 계산 결과를 Gemini 제공
                # Gemini는 해석 역할 수행
                # -------------------------------

                market_context = {

                    "검색기간":
                        search_period,

                    "상품수":
                        len(products),

                    "시장평균금리":
                        round(
                            avg_rate,
                            2
                        ),

                    "최고금리상품":
                        highest,

                    "최저금리상품":
                        lowest,

                    "TOP10상품":
                        top10_rates,

                    "우리금융분석":
                        bank_info,

                    "전체상품":
                        products[:50]

                }

                market_data = json.dumps(

                    market_context,

                    ensure_ascii=False,

                    indent=2

                )

                prompt_type = detect_prompt_type(
                    question
                )

                prompt_question = (
                    get_prompt(prompt_type)
                    + "\n\n"
                    + "사용자 질문:\n"
                    + question
                )

                ai_comment = ask_gemini(

                    prompt_question,

                    market_data

                )

                answer = (

                    "🤖 AI 전문가 분석\n\n"

                    + ai_comment

                )



            except Exception as e:


                print(


                    "GEMINI ERROR:",

                    e

                )


# ===================================
# SBRateBot V4 app.py
# 19/20
# ===================================


        # -------------------------------
        # 검색 결과 없음 처리
        # -------------------------------


        if not answer:



            answer = (



                "검색 결과가 없습니다."



            )





        return jsonify({



            "answer":



                answer



        })






    except Exception as e:



        print(



            "AI SEARCH ERROR:",



            e



        )





        return jsonify({



            "answer":



                "AI 검색 오류가 발생했습니다."



        })






# ===================================
# ISA / 퇴직연금 API V5
# 기존 정기예금 API와 분리
# ===================================

def pension_items_with_period(items, period):
    if period not in ["3", "6", "12", "24", "36"]:
        return items

    key = period + "m"

    for item in items:
        item["period"] = period + "개월"
        item["rate"] = item.get("rates", {}).get(key)

    items.sort(
        key=lambda x: (
            x.get("rate") is not None,
            x.get("rate") or 0
        ),
        reverse=True
    )

    return items


@app.route("/api/isa")
def api_isa():
    period = str(request.args.get("period", "")).strip()

    items = build_pension_products(
        ISA_DATA_FILE,
        "ISA"
    )

    items = pension_items_with_period(
        items,
        period
    )

    return jsonify({
        "category": "ISA",
        "count": len(items),
        "items": items
    })


@app.route("/api/irp")
def api_irp():
    period = str(request.args.get("period", "")).strip()

    items = build_pension_products(
        IRP_DATA_FILE,
        "퇴직연금"
    )

    items = pension_items_with_period(
        items,
        period
    )

    return jsonify({
        "category": "퇴직연금",
        "count": len(items),
        "items": items
    })


@app.route("/api/pension")
def api_pension():
    pension_type = str(
        request.args.get("type", "all")
    ).strip().lower()

    period = str(
        request.args.get("period", "")
    ).strip()

    bank_query = str(
        request.args.get("bank", "")
    ).strip()

    items = []

    if pension_type in ["all", "isa"]:
        items.extend(
            build_pension_products(
                ISA_DATA_FILE,
                "ISA"
            )
        )

    if pension_type in ["all", "irp", "퇴직연금"]:
        items.extend(
            build_pension_products(
                IRP_DATA_FILE,
                "퇴직연금"
            )
        )

    if bank_query:
        target = normalize(bank_query)

        items = [
            item
            for item in items
            if target in normalize(item.get("bank", ""))
        ]

    items = pension_items_with_period(
        items,
        period
    )

    return jsonify({
        "type": pension_type,
        "period": period + "개월" if period else None,
        "count": len(items),
        "items": items
    })



# -------------------------------
# 오류 제보센터 V5.10
# -------------------------------

ERROR_REPORT_FILE = os.path.join(
    BASE_DIR,
    "data",
    "error_reports.json"
)

# 오류 제보 관리자 개인 Telegram Chat ID
# Render Environment:
# TELEGRAM_ADMIN_CHAT_ID = 개인 /chatid 값
TELEGRAM_ADMIN_CHAT_ID = os.getenv(
    "TELEGRAM_ADMIN_CHAT_ID",
    ""
).strip()


def telegram_error_report_source(report):
    category = str(
        (report or {}).get("category", "")
    ).strip()

    page_url = str(
        (report or {}).get("page_url", "")
    ).strip()

    if category.lower() == "telegram" or page_url.lower() == "telegram":
        return "Telegram"

    if "/mobile" in page_url.lower():
        return "모바일 대시보드"

    return "PC 대시보드"


def telegram_notify_error_report(report):
    """오류 제보 저장 후 관리자 개인 Telegram으로 알린다."""
    if not TELEGRAM_ADMIN_CHAT_ID:
        return False

    try:
        source = telegram_error_report_source(
            report
        )

        text = (
            "🚨 SBRate 오류 제보\n\n"
            f"접수번호 : {report.get('id', '-')}\n"
            f"접수경로 : {source}\n"
            f"상품 : {report.get('product') or '-'}\n"
            f"기간 : {report.get('period') or '-'}\n"
            f"유형 : {report.get('error_type') or '기타'}\n\n"
            "내용\n"
            f"{report.get('message') or '-'}\n\n"
            f"접수시각 : {report.get('created_at') or '-'}"
        )

        page_url = str(
            report.get("page_url", "")
        ).strip()

        if page_url and page_url.lower() != "telegram":
            text += f"\n페이지 : {page_url}"

        telegram_send_message(
            TELEGRAM_ADMIN_CHAT_ID,
            text
        )

        return True

    except Exception as e:
        print(
            "ERROR REPORT TELEGRAM NOTIFY ERROR:",
            e
        )
        return False


@app.route("/api/error-report", methods=["POST"])
def api_error_report():
    try:
        payload = request.get_json(silent=True) or {}

        message = str(payload.get("message", "")).strip()
        if not message:
            return jsonify({
                "ok": False,
                "error": "message_required"
            }), 400

        now = datetime.now()
        report_id = "ERR-" + now.strftime("%Y%m%d-%H%M%S-%f")[:20]

        report = {
            "id": report_id,
            "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
            "app_version": "V5.11.5",
            "category": str(payload.get("category", "")).strip(),
            "product": str(payload.get("product", "")).strip(),
            "period": str(payload.get("period", "")).strip(),
            "error_type": str(payload.get("error_type", "기타")).strip(),
            "message": message,
            "page_url": str(payload.get("page_url", "")).strip(),
            "user_agent": str(payload.get("user_agent", "")).strip()
        }

        reports = []

        if os.path.exists(ERROR_REPORT_FILE):
            try:
                with open(ERROR_REPORT_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, list):
                        reports = loaded
            except Exception:
                reports = []

        reports.append(report)

        os.makedirs(
            os.path.dirname(ERROR_REPORT_FILE),
            exist_ok=True
        )

        temp_file = ERROR_REPORT_FILE + ".tmp"

        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(
                reports,
                f,
                ensure_ascii=False,
                indent=2
            )

        os.replace(
            temp_file,
            ERROR_REPORT_FILE
        )

        # JSON 저장 성공 후 관리자 Telegram 알림.
        # 알림 실패가 제보 저장 자체를 실패시키지는 않는다.
        telegram_notify_error_report(
            report
        )

        return jsonify({
            "ok": True,
            "id": report_id
        })

    except Exception as e:
        print("ERROR REPORT SAVE ERROR:", e)

        return jsonify({
            "ok": False,
            "error": "save_failed"
        }), 500


@app.route("/api/error-reports")
def api_error_reports():
    try:
        if not os.path.exists(ERROR_REPORT_FILE):
            return jsonify({
                "count": 0,
                "items": []
            })

        with open(ERROR_REPORT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            data = []

        return jsonify({
            "count": len(data),
            "items": list(reversed(data))
        })

    except Exception:
        return jsonify({
            "count": 0,
            "items": []
        })



# ==========================================
# Telegram Bot Integration V1
# Render Webhook / SBRate
# ==========================================

TELEGRAM_BOT_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN",
    ""
).strip()

# 현재 Render 공개 URL.
# 향후 Custom Domain으로 변경할 때 Render Environment에
# SB_RATE_PUBLIC_URL만 추가하면 Telegram webhook도 자동 변경된다.
SB_RATE_PUBLIC_URL = os.getenv(
    "SB_RATE_PUBLIC_URL",
    "https://sbrate.onrender.com"
).strip().rstrip("/")

SB_RATE_TELEGRAM_USERNAME = os.getenv(
    "SB_RATE_TELEGRAM_USERNAME",
    "SBRateBot"
).strip().lstrip("@")

SB_RATE_TELEGRAM_URL = (
    f"https://t.me/{SB_RATE_TELEGRAM_USERNAME}"
    if SB_RATE_TELEGRAM_USERNAME
    else "https://t.me/SBRateBot"
)

TELEGRAM_API_BASE = (
    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
    if TELEGRAM_BOT_TOKEN
    else ""
)

# 별도 Secret 입력 없이도 Telegram webhook 요청을 검증한다.
TELEGRAM_WEBHOOK_SECRET = (
    hashlib.sha256(
        TELEGRAM_BOT_TOKEN.encode("utf-8")
    ).hexdigest()
    if TELEGRAM_BOT_TOKEN
    else ""
)


def telegram_split_text(text, limit=3900):
    text = str(text or "").strip()

    if not text:
        return ["응답 내용이 없습니다."]

    if len(text) <= limit:
        return [text]

    chunks = []
    current = ""

    for line in text.splitlines():
        candidate = (
            current + "\n" + line
            if current
            else line
        )

        if len(candidate) <= limit:
            current = candidate
            continue

        if current:
            chunks.append(current)

        while len(line) > limit:
            chunks.append(line[:limit])
            line = line[limit:]

        current = line

    if current:
        chunks.append(current)

    return chunks


def telegram_api(method, payload=None, timeout=20):
    if not TELEGRAM_API_BASE:
        return {
            "ok": False,
            "error": "TELEGRAM_BOT_TOKEN missing"
        }

    try:
        response = http_requests.post(
            f"{TELEGRAM_API_BASE}/{method}",
            json=payload or {},
            timeout=timeout
        )

        try:
            return response.json()
        except Exception:
            return {
                "ok": False,
                "status_code": response.status_code,
                "text": response.text[:500]
            }

    except Exception as e:
        print("TELEGRAM API ERROR:", method, e)

        return {
            "ok": False,
            "error": str(e)
        }


def telegram_plain_text(text):
    """Telegram 전송용: 대시보드 HTML을 일반 텍스트로 변환한다."""
    text = str(text or "")

    # 잘못 생성된 "\\n" 문자열도 실제 줄바꿈으로 변환
    text = text.replace(
        "\\n",
        "\n"
    )

    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(?:p|div|li|tr|h[1-6])\s*>", "\n", text)
    text = re.sub(r"(?i)<li(?:\s+[^>]*)?>", "• ", text)
    text = re.sub(r"<[^>]+>", "", text)

    for old, new in {
        "&nbsp;": " ", "&amp;": "&", "&lt;": "<", "&gt;": ">",
        "&quot;": '"', "&#39;": "'"
    }.items():
        text = text.replace(old, new)

    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def telegram_send_message(
    chat_id,
    text,
    disable_web_page_preview=True,
    reply_markup=None,
    force_reply=False
):
    text = telegram_plain_text(text)
    chunks = telegram_split_text(text)
    last_message_id = None

    for idx, chunk in enumerate(chunks):
        payload = {
            "chat_id": chat_id,
            "text": chunk,
            "disable_web_page_preview":
                disable_web_page_preview
        }

        # 버튼/ForceReply는 마지막 메시지에만 부착
        if idx == len(chunks) - 1:
            if reply_markup:
                payload["reply_markup"] = reply_markup

            if force_reply:
                payload["reply_markup"] = {
                    "force_reply": True,
                    "selective": True
                }

        result = telegram_api(
            "sendMessage",
            payload
        )

        if isinstance(result, dict):
            last_message_id = (
                (result.get("result") or {}).get(
                    "message_id"
                )
                or last_message_id
            )

    return last_message_id


def telegram_delete_message(chat_id, message_id):
    if not message_id:
        return

    telegram_api(
        "deleteMessage",
        {
            "chat_id": chat_id,
            "message_id": message_id
        },
        timeout=10
    )


def telegram_send_progress(
    chat_id,
    text="🔎 요청을 처리하고 있습니다..."
):
    telegram_send_typing(
        chat_id
    )

    return telegram_send_message(
        chat_id,
        text
    )


def telegram_finish_progress(chat_id, message_id):
    telegram_delete_message(
        chat_id,
        message_id
    )


def telegram_send_typing(chat_id):
    telegram_api(
        "sendChatAction",
        {
            "chat_id": chat_id,
            "action": "typing"
        },
        timeout=10
    )


def telegram_read_update_time():
    update_file = os.path.join(
        BASE_DIR,
        "data",
        "update_info.json"
    )

    try:
        with open(
            update_file,
            "r",
            encoding="utf-8"
        ) as f:
            data = json.load(f)

        if isinstance(data, dict):
            return (
                data.get("last_update")
                or data.get("updated_at")
                or data.get("update_time")
                or "-"
            )

    except Exception:
        pass

    return "-"


def telegram_period_from_text(
    text,
    default="12",
    pension=False
):
    text = str(text or "")

    match = re.search(
        r"(?<!\d)(1|3|6|12|24|36)\s*(?:개월|m)?",
        text,
        flags=re.I
    )

    period = (
        match.group(1)
        if match
        else str(default)
    )

    if pension and period == "1":
        period = "3"

    return period


def telegram_woori_row(items):
    for item in items:
        if normalize(
            item.get("bank", "")
        ) == normalize(
            "우리금융저축은행"
        ):
            return item

    return None


def telegram_deposit_summary(period="12"):
    period_name = f"{period}개월"

    products = unique_products(
        build_products(
            period_name
        )
    )

    products = [
        item
        for item in products
        if safe_float(
            item.get("rate")
        ) is not None
        and safe_float(
            item.get("rate")
        ) > 0
    ]

    if not products:
        return (
            f"📊 정기예금 {period_name}\n\n"
            "유효 금리 데이터가 없습니다."
        )

    bank_best = get_bank_best_rates(
        products
    )

    bank_best = [
        item
        for item in bank_best
        if safe_float(
            item.get("rate")
        ) is not None
        and safe_float(
            item.get("rate")
        ) > 0
    ]

    bank_best.sort(
        key=lambda x:
            safe_float(
                x.get("rate")
            ) or 0,
        reverse=True
    )

    rates = [
        safe_float(
            item.get("rate")
        )
        for item in bank_best
    ]

    avg_rate = (
        sum(rates) / len(rates)
        if rates
        else 0
    )

    top = (
        bank_best[0]
        if bank_best
        else {}
    )

    woori = telegram_woori_row(
        bank_best
    )

    woori_rank = "-"

    if woori:
        for idx, item in enumerate(
            bank_best,
            start=1
        ):
            if normalize(
                item.get("bank", "")
            ) == normalize(
                "우리금융저축은행"
            ):
                woori_rank = idx
                break

    lines = [
        f"📊 정기예금 {period_name} 시장현황",
        "",
        f"시장 최고 : {top.get('bank','-')} "
        f"{safe_float(top.get('rate')) or 0:.2f}%",
        f"시장 평균 : {avg_rate:.2f}%",
        f"참여은행 : {len(bank_best)}개",
    ]

    if woori:
        woori_rate = (
            safe_float(
                woori.get("rate")
            ) or 0
        )

        top_rate = (
            safe_float(
                top.get("rate")
            ) or 0
        )

        lines.extend([
            "",
            "🏦 우리금융저축은행",
            f"금리 : {woori_rate:.2f}%",
            f"시장 순위 : {woori_rank}위 / "
            f"{len(bank_best)}개",
            f"최고금리 Gap : "
            f"{woori_rate - top_rate:+.2f}%p"
        ])

    if period == "12":
        try:
            with app.test_request_context(
                "/api/rate-changes",
                method="GET"
            ):
                change_response = (
                    api_rate_changes()
                )

            change_data = (
                change_response.get_json(
                    silent=True
                )
                if hasattr(
                    change_response,
                    "get_json"
                )
                else {}
            ) or {}

            lines.extend([
                "",
                "🔄 최근 변동",
                f"상승 {change_data.get('up_count',0)}건 / "
                f"하락 {change_data.get('down_count',0)}건"
            ])

        except Exception as e:
            print(
                "TELEGRAM CHANGE SUMMARY ERROR:",
                e
            )

    lines.extend([
        "",
        f"데이터 업데이트 : "
        f"{telegram_read_update_time()}"
    ])

    return "\n".join(lines)


def telegram_pension_summary(
    category,
    period="12"
):
    is_isa = (
        category == "isa"
    )

    file_path = (
        ISA_DATA_FILE
        if is_isa
        else IRP_DATA_FILE
    )

    label = (
        "ISA"
        if is_isa
        else "퇴직연금(IRP)"
    )

    items = build_pension_products(
        file_path,
        "ISA"
        if is_isa
        else "퇴직연금"
    )

    items = pension_items_with_period(
        items,
        period
    )

    valid = [
        item
        for item in items
        if safe_float(
            item.get("rate")
        ) is not None
        and safe_float(
            item.get("rate")
        ) > 0
    ]

    if not valid:
        return (
            f"📊 {label} {period}개월\n\n"
            "현재 유효 금리 데이터가 없습니다."
        )

    valid.sort(
        key=lambda x:
            safe_float(
                x.get("rate")
            ) or 0,
        reverse=True
    )

    top = valid[0]
    rates = [
        safe_float(
            item.get("rate")
        )
        for item in valid
    ]

    avg_rate = (
        sum(rates) / len(rates)
        if rates
        else 0
    )

    woori = telegram_woori_row(
        valid
    )

    lines = [
        f"📊 {label} {period}개월 시장현황",
        "",
        f"시장 최고 : {top.get('bank','-')} "
        f"{safe_float(top.get('rate')) or 0:.2f}%",
        f"시장 평균 : {avg_rate:.2f}%",
        f"수집기관 : {len(items)}개",
        f"유효금리 : {len(valid)}개"
    ]

    if woori:
        rank = (
            valid.index(woori) + 1
        )

        woori_rate = (
            safe_float(
                woori.get("rate")
            ) or 0
        )

        top_rate = (
            safe_float(
                top.get("rate")
            ) or 0
        )

        lines.extend([
            "",
            "🏦 우리금융저축은행",
            f"금리 : {woori_rate:.2f}%",
            f"시장 순위 : {rank}위 / "
            f"{len(valid)}개",
            f"최고금리 Gap : "
            f"{woori_rate - top_rate:+.2f}%p",
            f"공시일 : "
            f"{woori.get('disclosure_date') or '미확인'}"
        ])

    lines.extend([
        "",
        "데이터 출처 : 각 저축은행 공식 공시·상품 페이지"
    ])

    return "\n".join(lines)


def telegram_brief():
    deposit_products = unique_products(
        build_products(
            "12개월"
        )
    )

    deposit_products = [
        item
        for item in deposit_products
        if safe_float(
            item.get("rate")
        ) is not None
        and safe_float(
            item.get("rate")
        ) > 0
    ]

    bank_best = get_bank_best_rates(
        deposit_products
    )

    bank_best = [
        item
        for item in bank_best
        if safe_float(
            item.get("rate")
        ) is not None
        and safe_float(
            item.get("rate")
        ) > 0
    ]

    bank_best.sort(
        key=lambda x:
            safe_float(
                x.get("rate")
            ) or 0,
        reverse=True
    )

    isa_items = pension_items_with_period(
        build_pension_products(
            ISA_DATA_FILE,
            "ISA"
        ),
        "12"
    )

    irp_items = pension_items_with_period(
        build_pension_products(
            IRP_DATA_FILE,
            "퇴직연금"
        ),
        "12"
    )

    def compact(items):
        valid = [
            item
            for item in items
            if safe_float(
                item.get("rate")
            ) is not None
            and safe_float(
                item.get("rate")
            ) > 0
        ]

        valid.sort(
            key=lambda x:
                safe_float(
                    x.get("rate")
                ) or 0,
            reverse=True
        )

        top = (
            valid[0]
            if valid
            else {}
        )

        woori = telegram_woori_row(
            valid
        )

        return {
            "count": len(valid),
            "top": top,
            "woori": woori,
            "woori_rank": (
                valid.index(woori) + 1
                if woori
                else None
            )
        }

    deposit_compact = compact(
        bank_best
    )

    isa_compact = compact(
        isa_items
    )

    irp_compact = compact(
        irp_items
    )

    market_context = {
        "데이터업데이트":
            telegram_read_update_time(),
        "정기예금":
            deposit_compact,
        "ISA":
            isa_compact,
        "퇴직연금":
            irp_compact
    }

    prompt = (
        "SBRateBot의 오늘 수신시장 브리핑을 작성해줘. "
        "반드시 제공 데이터에 있는 숫자만 사용하고 "
        "새로운 숫자를 추정하거나 만들지 마. "
        "정기예금, ISA, 퇴직연금 순으로 핵심 현황을 설명하고, "
        "우리금융저축은행의 경쟁력과 오늘 확인할 포인트를 "
        "간결하고 전문적인 한국어로 정리해줘. "
        "텔레그램 메시지이므로 표는 사용하지 말고 "
        "900자 이내로 작성해줘."
    )

    try:
        ai_text = ask_gemini(
            prompt,
            json.dumps(
                market_context,
                ensure_ascii=False,
                indent=2,
                default=str
            )
        )

        if ai_text:
            return (
                "🤖 SBRate AI 시장 브리핑\n\n"
                + ai_text
                + "\n\n"
                + "🌐 대시보드\n"
                + SB_RATE_PUBLIC_URL
                + "\n"
                + "📱 모바일\n"
                + SB_RATE_PUBLIC_URL
                + "/mobile"
            )

    except Exception as e:
        print(
            "TELEGRAM BRIEF GEMINI ERROR:",
            e
        )

    # Gemini 실패 시 데이터 기반 기본 브리핑.
    return (
        "🤖 SBRate 시장 브리핑\n\n"
        + telegram_deposit_summary("12")
        + "\n\n"
        + telegram_pension_summary(
            "isa",
            "12"
        )
        + "\n\n"
        + telegram_pension_summary(
            "irp",
            "12"
        )
    )


def telegram_category_label(category):
    if category == "isa":
        return "ISA"
    if category == "irp":
        return "퇴직연금(IRP)"
    return "정기예금"


def telegram_data_rows(category="deposit", period="12"):
    if category == "deposit":
        products = unique_products(
            build_products(f"{period}개월")
        )
        products = [
            item for item in products
            if safe_float(item.get("rate")) is not None
            and safe_float(item.get("rate")) > 0
        ]
        rows = get_bank_best_rates(products)
    else:
        file_path = ISA_DATA_FILE if category == "isa" else IRP_DATA_FILE
        rows = pension_items_with_period(
            build_pension_products(
                file_path,
                "ISA" if category == "isa" else "퇴직연금"
            ),
            period
        )

    rows = [
        item for item in rows
        if safe_float(item.get("rate")) is not None
        and safe_float(item.get("rate")) > 0
    ]
    rows.sort(
        key=lambda x: safe_float(x.get("rate")) or 0,
        reverse=True
    )
    return rows


def telegram_fast_question(question, category="deposit", period="12"):
    """단순 데이터 질문은 Gemini 없이 JSON에서 즉시 답변."""
    q = str(question or "").strip()
    q_norm = normalize(q)

    analysis_words = [
        "분석", "전망", "예측", "왜", "이유", "평가",
        "브리핑", "전략", "시사점", "어떻게대응", "의견"
    ]
    if any(normalize(word) in q_norm for word in analysis_words):
        return None

    lookup_words = [
        "높은", "낮은", "최고", "최저", "top", "상위",
        "순위", "몇위", "금리", "비교", "우리금융보다", "우리보다"
    ]
    if not any(normalize(word) in q_norm for word in lookup_words):
        return None

    rows = telegram_data_rows(category, period)
    label = telegram_category_label(category)

    if not rows:
        return f"📊 {label} {period}개월 기준\\n\\n현재 유효 금리 데이터가 없습니다."

    woori = telegram_woori_row(rows)
    top_match = re.search(r"(?:top|상위)\\s*(\\d+)", q, flags=re.I)
    top_n = max(1, min(int(top_match.group(1)), 20)) if top_match else 10

    if "최고" in q and "우리" not in q and "높" not in q:
        top = rows[0]
        return (
            f"📊 {label} {period}개월 기준\\n\\n"
            f"시장 최고금리 : {top.get('bank','-')} "
            f"{safe_float(top.get('rate')) or 0:.2f}%"
        )

    if "최저" in q or "낮은" in q:
        bottom = rows[-1]
        return (
            f"📊 {label} {period}개월 기준\\n\\n"
            f"시장 최저금리 : {bottom.get('bank','-')} "
            f"{safe_float(bottom.get('rate')) or 0:.2f}%"
        )

    if ("순위" in q or "몇위" in q) and "우리" in q:
        if not woori:
            return f"📊 {label} {period}개월 기준\\n\\n우리금융저축은행의 유효 금리 데이터가 없습니다."
        rank = rows.index(woori) + 1
        return (
            f"📊 {label} {period}개월 기준\\n\\n"
            f"우리금융저축은행 : {safe_float(woori.get('rate')) or 0:.2f}%\\n"
            f"시장 순위 : {rank}위 / {len(rows)}개"
        )

    if "우리" in q and ("높" in q or "상위" in q or "비교" in q):
        if not woori:
            return f"📊 {label} {period}개월 기준\\n\\n우리금융저축은행의 유효 금리 데이터가 없습니다."

        woori_rate = safe_float(woori.get("rate")) or 0
        higher = [
            item for item in rows
            if (safe_float(item.get("rate")) or 0) > woori_rate
        ]
        lines = [
            f"📊 {label} {period}개월 기준",
            "",
            f"우리금융 : {woori_rate:.2f}%",
            f"우리금융보다 높은 곳 : {len(higher)}개",
            ""
        ]
        for idx, item in enumerate(higher[:top_n], start=1):
            rate = safe_float(item.get("rate")) or 0
            lines.append(
                f"{idx}. {item.get('bank','-')} {rate:.2f}% "
                f"({rate - woori_rate:+.2f}%p)"
            )
        if len(higher) > top_n:
            lines.append(f"\\n상위 {top_n}개만 표시했습니다.")
        return "\\n".join(lines)

    if "top" in q.lower() or "상위" in q:
        lines = [f"🏆 {label} {period}개월 TOP {top_n}", ""]
        for idx, item in enumerate(rows[:top_n], start=1):
            lines.append(
                f"{idx}. {item.get('bank','-')} "
                f"{safe_float(item.get('rate')) or 0:.2f}%"
            )
        return "\\n".join(lines)

    if category == "deposit":
        return telegram_deposit_summary(period)
    return telegram_pension_summary(category, period)


def telegram_ai_question(
    question,
    category="deposit",
    period="12"
):
    try:
        with app.test_request_context(
            "/api/ai/search",
            method="POST",
            json={
                "question": question,
                "category": category,
                "period": period
            }
        ):
            response = ai_search()

        status_code = 200

        if isinstance(
            response,
            tuple
        ):
            response, status_code = (
                response[0],
                response[1]
            )

        payload = (
            response.get_json(
                silent=True
            )
            if hasattr(
                response,
                "get_json"
            )
            else None
        )

        if isinstance(
            payload,
            dict
        ):
            answer = str(
                payload.get(
                    "answer",
                    ""
                )
            ).strip()

            if answer:
                return answer

        return (
            "AI 답변을 생성하지 못했습니다."
        )

    except Exception as e:
        print(
            "TELEGRAM AI QUESTION ERROR:",
            e
        )

        return (
            "AI 질문 처리 중 오류가 발생했습니다."
        )


def telegram_detect_category(text):
    q = str(
        text or ""
    ).lower()

    if "isa" in q:
        return "isa"

    if (
        "irp" in q
        or "퇴직연금" in q
        or "퇴직 연금" in q
    ):
        return "irp"

    return "deposit"


def telegram_main_menu():
    return {
        "inline_keyboard": [
            [
                {
                    "text": "🏦 정기예금",
                    "callback_data": "cat:deposit"
                },
                {
                    "text": "🏦 ISA",
                    "callback_data": "cat:isa"
                }
            ],
            [
                {
                    "text": "🏦 퇴직연금(IRP)",
                    "callback_data": "cat:irp"
                },
                {
                    "text": "📊 오늘의 브리핑",
                    "callback_data": "brief"
                }
            ],
            [
                {
                    "text": "💬 AI에게 물어보기",
                    "callback_data": "ai_help"
                },
                {
                    "text": "🐞 오류제보",
                    "callback_data": "error_report"
                }
            ],
            [
                {
                    "text": "🖥 PC 대시보드",
                    "url": SB_RATE_PUBLIC_URL
                },
                {
                    "text": "📱 모바일 대시보드",
                    "url": SB_RATE_PUBLIC_URL + "/mobile"
                }
            ]
        ]
    }


def telegram_period_menu(category):
    return {
        "inline_keyboard": [
            [
                {
                    "text": "3개월",
                    "callback_data": f"period:{category}:3"
                },
                {
                    "text": "6개월",
                    "callback_data": f"period:{category}:6"
                },
                {
                    "text": "12개월",
                    "callback_data": f"period:{category}:12"
                }
            ],
            [
                {
                    "text": "24개월",
                    "callback_data": f"period:{category}:24"
                },
                {
                    "text": "36개월",
                    "callback_data": f"period:{category}:36"
                }
            ],
            [
                {
                    "text": "⬅️ 메인 메뉴",
                    "callback_data": "main"
                }
            ]
        ]
    }


def telegram_query_menu(category, period):
    return {
        "inline_keyboard": [
            [
                {
                    "text": "🏆 최고금리",
                    "callback_data":
                        f"query:{category}:{period}:highest"
                },
                {
                    "text": "🔟 TOP10",
                    "callback_data":
                        f"query:{category}:{period}:top10"
                }
            ],
            [
                {
                    "text": "🏦 우리금융 순위",
                    "callback_data":
                        f"query:{category}:{period}:woori_rank"
                }
            ],
            [
                {
                    "text": "📈 우리금융보다 높은 곳",
                    "callback_data":
                        f"query:{category}:{period}:higher"
                }
            ],
            [
                {
                    "text": "💬 AI에게 물어보기",
                    "callback_data":
                        f"ai_category:{category}:{period}"
                }
            ],
            [
                {
                    "text": "⬅️ 기간 선택",
                    "callback_data":
                        f"cat:{category}"
                },
                {
                    "text": "🏠 메인",
                    "callback_data": "main"
                }
            ]
        ]
    }


def telegram_send_main_menu(chat_id, intro=True):
    text = (
        "안녕하세요. SBRate입니다. 🤖\\n\\n"
        "조회할 메뉴를 선택해주세요."
        if intro
        else
        "SBRate 메뉴를 선택해주세요."
    )

    telegram_send_message(
        chat_id,
        text,
        reply_markup=telegram_main_menu()
    )


def telegram_answer_callback(callback_id, text=None):
    payload = {
        "callback_query_id": callback_id
    }

    if text:
        payload["text"] = text

    telegram_api(
        "answerCallbackQuery",
        payload,
        timeout=10
    )


def telegram_data_footer(category="deposit", period="12"):
    source = (
        "저축은행중앙회 비교공시"
        if category == "deposit"
        else "각 저축은행 공식 공시·상품 페이지"
    )

    return (
        "\n\n"
        f"⏱ 데이터 업데이트 : {telegram_read_update_time()}\n"
        f"🔎 출처 : {source}"
    )


def telegram_with_footer(text, category="deposit", period="12"):
    text = str(text or "").strip()

    if not text:
        return text

    # 오류/안내 메시지에는 불필요한 데이터 footer를 붙이지 않는다.
    if any(
        marker in text
        for marker in [
            "유효 금리 데이터가 없습니다",
            "오류가 발생",
            "생성하지 못했습니다"
        ]
    ):
        return text

    return (
        text
        + telegram_data_footer(
            category,
            period
        )
    )


def telegram_callback_result(
    category,
    period,
    query_type
):
    label = telegram_category_label(
        category
    )

    question_map = {
        "highest":
            f"{label} {period}개월 최고금리",
        "top10":
            f"{label} {period}개월 TOP10",
        "woori_rank":
            f"{label} {period}개월 우리금융 순위",
        "higher":
            f"{label} {period}개월 우리금융보다 높은 곳"
    }

    question = question_map.get(
        query_type
    )

    if question:
        answer = telegram_fast_question(
            question,
            category,
            period
        )

        return telegram_with_footer(
            answer,
            category,
            period
        )

    return (
        f"📊 {label} {period}개월 기준\n\n"
        "조회 항목을 선택해주세요."
    )


def telegram_handle_callback(callback):
    callback_id = callback.get("id")

    message = callback.get("message") or {}

    chat = message.get("chat") or {}

    chat_id = chat.get("id")

    data = str(
        callback.get("data", "")
    ).strip()

    if chat_id is None:
        return

    # 그룹방의 기존 인라인 버튼 클릭도 무응답 처리.
    if not telegram_is_private_chat(
        chat
    ):
        telegram_answer_callback(
            callback_id,
            "상세 조회는 SBRateBot 개인채팅에서 이용해주세요."
        )
        return

    telegram_answer_callback(
        callback_id
    )

    if data == "main":
        telegram_send_main_menu(
            chat_id,
            intro=False
        )
        return

    if data.startswith("cat:"):
        category = data.split(
            ":",
            1
        )[1]

        label = telegram_category_label(
            category
        )

        telegram_send_message(
            chat_id,
            (
                f"🏦 {label}\\n\\n"
                "조회할 기간을 선택해주세요."
            ),
            reply_markup=
                telegram_period_menu(
                    category
                )
        )
        return

    if data.startswith("period:"):
        parts = data.split(":")

        if len(parts) != 3:
            return

        _, category, period = parts

        label = telegram_category_label(
            category
        )

        telegram_send_message(
            chat_id,
            (
                f"📊 {label} {period}개월\\n\\n"
                "조회할 내용을 선택해주세요."
            ),
            reply_markup=
                telegram_query_menu(
                    category,
                    period
                )
        )
        return

    if data.startswith("query:"):
        parts = data.split(":")

        if len(parts) != 4:
            return

        _, category, period, query_type = parts

        progress_id = telegram_send_progress(
            chat_id,
            "🔎 금리 정보를 조회하고 있습니다..."
        )

        answer = telegram_callback_result(
            category,
            period,
            query_type
        )

        telegram_finish_progress(
            chat_id,
            progress_id
        )

        telegram_send_message(
            chat_id,
            answer,
            reply_markup=
                telegram_query_menu(
                    category,
                    period
                )
        )
        return

    if data == "brief":
        progress_id = telegram_send_progress(
            chat_id,
            "📊 최신 데이터를 분석해 브리핑을 만들고 있습니다..."
        )

        answer = telegram_brief()

        telegram_finish_progress(
            chat_id,
            progress_id
        )

        telegram_send_message(
            chat_id,
            answer,
            reply_markup=
                telegram_main_menu()
        )
        return

    if data == "ai_help":
        telegram_send_message(
            chat_id,
            (
                "💬 AI에게 물어보기\\n\\n"
                "궁금한 내용을 자유롭게 입력해주세요.\\n\\n"
                "예)\\n"
                "• 정기예금 6개월 TOP5 알려줘\\n"
                "• ISA 12개월 우리금융 순위는?\\n"
                "• IRP 24개월 우리금융보다 높은 곳\\n"
                "• 최근 금리 변동을 분석해줘\\n\\n"
                "상품명과 기간을 함께 입력하면 "
                "더 정확하게 조회합니다."
            ),
            reply_markup=
                telegram_main_menu()
        )
        return

    if data.startswith("ai_category:"):
        parts = data.split(":")

        if len(parts) != 3:
            return

        _, category, period = parts

        label = telegram_category_label(
            category
        )

        telegram_send_message(
            chat_id,
            (
                f"💬 {label} {period}개월 AI에게 물어보기\n\n"
                "이제 질문을 그대로 입력해주세요.\n"
                "예) 우리금융보다 높은 곳 알려줘\n"
                "예) 시장 경쟁력을 분석해줘\n\n"
                f"상품/기간을 생략하면 "
                f"{label} {period}개월 기준으로 "
                "질문하는 것이 가장 정확합니다."
            ),
            reply_markup=
                telegram_main_menu()
        )
        return

    if data == "error_report":
        telegram_send_message(
            chat_id,
            (
                "🐞 오류제보\\n\\n"
                "아래 메시지에 답장하는 방식으로 "
                "오류 내용을 입력해주세요.\\n\\n"
                "예) ISA 6개월 조회 시 순위가 이상합니다."
            ),
            force_reply=True
        )
        return


def telegram_save_error_report(
    chat_id,
    message_text
):
    payload = {
        "category": "Telegram",
        "product": "SBRate Bot",
        "period": "",
        "error_type": "텔레그램 오류제보",
        "message": str(
            message_text or ""
        ).strip(),
        "page_url": "telegram",
        "user_agent": f"telegram_chat_{chat_id}"
    }

    try:
        with app.test_request_context(
            "/api/error-report",
            method="POST",
            json=payload
        ):
            response = api_error_report()

        if isinstance(
            response,
            tuple
        ):
            response = response[0]

        result = (
            response.get_json(
                silent=True
            )
            if hasattr(
                response,
                "get_json"
            )
            else {}
        ) or {}

        if result.get("ok"):
            return str(
                result.get("id", "")
            ).strip() or "접수완료"

        return None

    except Exception as e:
        print(
            "TELEGRAM ERROR REPORT SAVE ERROR:",
            e
        )

        return False


def telegram_help_text():
    return (
        "안녕하세요. SBRate입니다. 🤖\n\n"
        "저축은행 수신시장 데이터를 조회하고 "
        "AI 분석을 제공합니다.\n\n"
        "사용 가능한 명령\n"
        "/deposit - 정기예금 12개월 시장현황\n"
        "/isa - ISA 12개월 시장현황\n"
        "/irp - 퇴직연금 12개월 시장현황\n"
        "/brief - 오늘의 AI 시장 브리핑\n"
        "/report - 대시보드·모바일 바로가기\n"
        "/help - 사용방법\n\n"
        "기간을 같이 입력할 수도 있습니다.\n"
        "예: /deposit 6, /isa 24, /irp 36\n\n"
        "명령어 없이 AI에게 바로 물어봐도 됩니다.\n"
        "예: 우리금융보다 금리 높은 곳 알려줘\n"
        "예: ISA 우리금융 경쟁력 알려줘\n"
        "예: 퇴직연금 최고금리 알려줘"
    )


def telegram_is_private_chat(chat):
    return str(
        (chat or {}).get(
            "type",
            ""
        )
    ).lower() == "private"


def telegram_handle_message(message):
    chat = (
        message.get("chat")
        if isinstance(
            message,
            dict
        )
        else {}
    ) or {}

    chat_id = chat.get("id")

    if chat_id is None:
        return

    text = str(
        message.get(
            "text",
            ""
        )
    ).strip()

    if not text:
        return

    command = (
        text.split()[0]
        .split("@")[0]
        .lower()
    )

    # 그룹/슈퍼그룹은 Morning Brief 전용.
    # 관리용 /chatid 외 일반 명령·자연어 질문에는 응답하지 않는다.
    if (
        not telegram_is_private_chat(
            chat
        )
        and command != "/chatid"
    ):
        return

    if command == "/chatid":
        telegram_send_message(
            chat_id,
            (
                "🆔 Telegram Chat ID\n\n"
                f"{chat_id}\n\n"
                "이 숫자를 Render의 "
                "TELEGRAM_CHAT_ID Value에 입력하세요."
            )
        )
        return

    if command == "/start":
        telegram_send_main_menu(
            chat_id,
            intro=True
        )
        return

    if command == "/help":
        telegram_send_message(
            chat_id,
            telegram_help_text(),
            reply_markup=
                telegram_main_menu()
        )
        return

    # 오류제보 ForceReply 응답 처리
    reply_to = (
        message.get(
            "reply_to_message"
        )
        or {}
    )

    reply_text = str(
        reply_to.get(
            "text",
            ""
        )
    )

    if "오류제보" in reply_text:
        report_id = telegram_save_error_report(
            chat_id,
            text
        )

        telegram_send_message(
            chat_id,
            (
                (
                    "✅ 오류제보가 접수되었습니다.\n"
                    f"접수번호 : {report_id}"
                )
                if report_id
                else
                (
                    "⚠️ 오류제보 저장 중 문제가 발생했습니다.\n"
                    "잠시 후 다시 시도해주세요."
                )
            ),
            reply_markup=
                telegram_main_menu()
        )
        return

    if command == "/report":
        telegram_send_message(
            chat_id,
            "📊 SBRateBot 대시보드를 선택해주세요.",
            reply_markup={
                "inline_keyboard": [
                    [
                        {
                            "text": "🖥 PC 대시보드",
                            "url": SB_RATE_PUBLIC_URL
                        }
                    ],
                    [
                        {
                            "text": "📱 모바일 대시보드",
                            "url": SB_RATE_PUBLIC_URL + "/mobile"
                        }
                    ],
                    [
                        {
                            "text": "🏠 메인 메뉴",
                            "callback_data": "main"
                        }
                    ]
                ]
            }
        )
        return

    if command == "/deposit":
        period = telegram_period_from_text(
            text,
            default="12",
            pension=False
        )

        progress_id = telegram_send_progress(
            chat_id,
            "🔎 정기예금 정보를 조회하고 있습니다..."
        )

        answer = telegram_with_footer(
            telegram_deposit_summary(
                period
            ),
            "deposit",
            period
        )

        telegram_finish_progress(
            chat_id,
            progress_id
        )

        telegram_send_message(
            chat_id,
            answer,
            reply_markup=
                telegram_main_menu()
        )
        return

    if command == "/isa":
        period = telegram_period_from_text(
            text,
            default="12",
            pension=True
        )

        progress_id = telegram_send_progress(
            chat_id,
            "🔎 ISA 정보를 조회하고 있습니다..."
        )

        answer = telegram_with_footer(
            telegram_pension_summary(
                "isa",
                period
            ),
            "isa",
            period
        )

        telegram_finish_progress(
            chat_id,
            progress_id
        )

        telegram_send_message(
            chat_id,
            answer,
            reply_markup=
                telegram_main_menu()
        )
        return

    if command == "/irp":
        period = telegram_period_from_text(
            text,
            default="12",
            pension=True
        )

        progress_id = telegram_send_progress(
            chat_id,
            "🔎 퇴직연금 정보를 조회하고 있습니다..."
        )

        answer = telegram_with_footer(
            telegram_pension_summary(
                "irp",
                period
            ),
            "irp",
            period
        )

        telegram_finish_progress(
            chat_id,
            progress_id
        )

        telegram_send_message(
            chat_id,
            answer,
            reply_markup=
                telegram_main_menu()
        )
        return

    if command == "/brief":
        progress_id = telegram_send_progress(
            chat_id,
            "📊 최신 데이터를 분석해 브리핑을 만들고 있습니다..."
        )

        answer = telegram_brief()

        telegram_finish_progress(
            chat_id,
            progress_id
        )

        telegram_send_message(
            chat_id,
            answer,
            reply_markup=
                telegram_main_menu()
        )
        return

    category = telegram_detect_category(
        text
    )

    period = telegram_period_from_text(
        text,
        default="12",
        pension=(
            category in [
                "isa",
                "irp"
            ]
        )
    )

    progress_id = telegram_send_progress(
        chat_id,
        "🤖 질문을 분석하고 있습니다..."
    )

    answer = telegram_fast_question(
        text,
        category=category,
        period=period
    )

    if answer is None:
        answer = telegram_ai_question(
            text,
            category=category,
            period=period
        )
    else:
        answer = telegram_with_footer(
            answer,
            category,
            period
        )

    telegram_finish_progress(
        chat_id,
        progress_id
    )

    telegram_send_message(
        chat_id,
        answer,
        reply_markup=
            telegram_main_menu()
    )


@app.route(
    "/telegram/webhook",
    methods=["POST"]
)
def telegram_webhook():
    if not TELEGRAM_BOT_TOKEN:
        return jsonify({
            "ok": False,
            "error":
                "telegram_not_configured"
        }), 503

    secret_header = request.headers.get(
        "X-Telegram-Bot-Api-Secret-Token",
        ""
    )

    if (
        TELEGRAM_WEBHOOK_SECRET
        and secret_header
        != TELEGRAM_WEBHOOK_SECRET
    ):
        return jsonify({
            "ok": False,
            "error": "invalid_secret"
        }), 403

    update = (
        request.get_json(
            silent=True
        )
        or {}
    )

    callback_query = update.get(
        "callback_query"
    )

    if isinstance(
        callback_query,
        dict
    ):
        telegram_handle_callback(
            callback_query
        )

        return jsonify({
            "ok": True
        })

    message = (
        update.get("message")
        or update.get(
            "edited_message"
        )
    )

    if isinstance(
        message,
        dict
    ):
        telegram_handle_message(
            message
        )

    return jsonify({
        "ok": True
    })


@app.route(
    "/telegram/morning-brief",
    methods=["POST"]
)
def telegram_morning_brief():
    expected_secret = os.getenv("TELEGRAM_BRIEF_SECRET", "").strip()
    provided_secret = request.headers.get("X-SBRate-Secret", "").strip()

    if expected_secret and provided_secret != expected_secret:
        return jsonify({"ok": False, "error": "invalid_secret"}), 403

    chat_ids_raw = (
        os.getenv(
            "TELEGRAM_CHAT_IDS",
            ""
        ).strip()
        or os.getenv(
            "TELEGRAM_CHAT_ID",
            ""
        ).strip()
    )

    chat_ids = [
        item.strip()
        for item in chat_ids_raw.split(",")
        if item.strip()
    ]

    if not chat_ids:
        return jsonify({
            "ok": False,
            "error":
                "TELEGRAM_CHAT_ID(S) missing"
        }), 503

    message = telegram_morning_brief_text()

    failed = []

    detail_button = {
        "inline_keyboard": [
            [
                {
                    "text":
                        "🤖 SBRateBot에서 상세조회",
                    "url":
                        SB_RATE_TELEGRAM_URL
                }
            ]
        ]
    }

    for chat_id in chat_ids:
        telegram_send_message(
            chat_id,
            message,
            reply_markup=
                detail_button
        )

    return jsonify({
        "ok": True,
        "recipient_count": len(chat_ids),
        "failed": failed
    })


def telegram_morning_brief_text():
    try:
        with app.test_request_context("/api/rate-changes", method="GET"):
            response = api_rate_changes()
        changes = response.get_json(silent=True) if hasattr(response, "get_json") else {}
        changes = changes or {}
    except Exception as e:
        print("TELEGRAM MORNING CHANGE ERROR:", e)
        changes = {}

    up_items = changes.get("up_all", []) or []
    down_items = changes.get("down_all", []) or []

    lines = [
        "☀️ SBRate Morning Brief",
        "",
        f"데이터 업데이트 : {telegram_read_update_time()}",
        "",
        "📊 정기예금 12개월 변동",
        f"상승 {len(up_items)}건 / 하락 {len(down_items)}건"
    ]

    if up_items:
        lines.extend(["", "🔺 상승"])
        for item in up_items[:5]:
            lines.append(
                f"• {item.get('bank','-')} "
                f"{safe_float(item.get('rate')) or 0:.2f}% "
                f"({safe_float(item.get('change')) or 0:+.2f}%p)"
            )

    if down_items:
        lines.extend(["", "🔻 하락"])
        for item in down_items[:5]:
            lines.append(
                f"• {item.get('bank','-')} "
                f"{safe_float(item.get('rate')) or 0:.2f}% "
                f"({safe_float(item.get('change')) or 0:+.2f}%p)"
            )

    if not up_items and not down_items:
        lines.extend(["", "금일 주요 정기예금 금리 변동 없음"])

    for category in ["isa", "irp"]:
        rows = telegram_data_rows(category, "12")
        label = telegram_category_label(category)
        woori = telegram_woori_row(rows)

        lines.extend(["", f"📌 {label} 12개월"])

        if rows:
            top = rows[0]
            lines.append(
                f"시장 최고 : {top.get('bank','-')} "
                f"{safe_float(top.get('rate')) or 0:.2f}%"
            )
        if woori:
            lines.append(
                f"우리금융 : {safe_float(woori.get('rate')) or 0:.2f}% "
                f"({rows.index(woori)+1}위/{len(rows)}개)"
            )

    lines.extend([
        "",
        "🌐 대시보드",
        SB_RATE_PUBLIC_URL,
        "📱 모바일",
        SB_RATE_PUBLIC_URL + "/mobile",
        "",
        "상세 조회·AI 질문은 "
        "@SBRateBot 개인채팅에서 이용해주세요."
    ])
    return "\\n".join(lines)


@app.route(
    "/telegram/health",
    methods=["GET"]
)
def telegram_health():
    return jsonify({
        "ok": True,
        "configured":
            bool(
                TELEGRAM_BOT_TOKEN
            ),
        "bot": "SBRate",
        "webhook":
            (
                SB_RATE_PUBLIC_URL
                + "/telegram/webhook"
            )
    })


def configure_telegram_webhook():
    if not TELEGRAM_BOT_TOKEN:
        print(
            "Telegram Bot: "
            "TELEGRAM_BOT_TOKEN 없음"
        )
        return

    webhook_url = (
        SB_RATE_PUBLIC_URL
        + "/telegram/webhook"
    )

    result = telegram_api(
        "setWebhook",
        {
            "url": webhook_url,
            "secret_token":
                TELEGRAM_WEBHOOK_SECRET,
            "allowed_updates": [
                "message",
                "edited_message",
                "callback_query"
            ],
            "drop_pending_updates":
                False
        }
    )

    print(
        "Telegram setWebhook:",
        result
    )

    commands = [
        {
            "command": "start",
            "description":
                "SBRate 메인 메뉴"
        },
        {
            "command": "brief",
            "description":
                "오늘의 시장 브리핑"
        },
        {
            "command": "report",
            "description":
                "PC·모바일 대시보드"
        },
        {
            "command": "help",
            "description":
                "사용방법"
        }
    ]

    command_result = telegram_api(
        "setMyCommands",
        {
            "commands": commands
        }
    )

    print(
        "Telegram setMyCommands:",
        command_result
    )

    menu_button_result = telegram_api(
        "setChatMenuButton",
        {
            "menu_button": {
                "type": "commands"
            }
        }
    )

    print(
        "Telegram setChatMenuButton:",
        menu_button_result
    )


def start_telegram_webhook_setup():
    if not TELEGRAM_BOT_TOKEN:
        return

    thread = threading.Thread(
        target=
            configure_telegram_webhook,
        daemon=True
    )

    thread.start()


# Gunicorn(Render) import 시에도 Telegram webhook 자동 등록.
start_telegram_webhook_setup()




# -------------------------------
# Scheduler 연결
# -------------------------------


from scheduler import start_scheduler






# -------------------------------
# 실행
# -------------------------------


if __name__ == "__main__":



    # ===============================
    # 자동 금리 업데이트 스케줄러 시작
    # 매일 00:30 crawler.py 실행
    # ===============================



    start_scheduler()






    # ===============================
    # Flask 서버 실행
    # ===============================



    app.run(



        host="0.0.0.0",



        port=5000,



        debug=True,



        use_reloader=False



    )

# ===================================
# SBRateBot V4 app.py
# 20/20
# ===================================


# 파일 종료
#
# app.py 마지막 실행부:
#
# if __name__ == "__main__":
#
#     start_scheduler()
#
#     app.run(
#         host="0.0.0.0",
#         port=5000,
#         debug=True,
#         use_reloader=False
#     )
#
# ===================================
# END OF FILE
# ===================================

