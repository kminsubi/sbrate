# ============================================
# SBRateBot V5
# IRP Common Disclosure Collector v1
# crawler/irp_disclosure.py
#
# 공식 퇴직연금 사업자 '타사제공 원리금보장상품' 공시에서
# 저축은행 IRP 금리를 공통 수집한다.
#
# 출력:
#   data/irp_disclosure_rates.json
#
# 현재 1차 source:
#   KB퇴직연금 타사제공상품
# ============================================

import json
import re
from datetime import datetime
from pathlib import Path

import requests
import urllib3
from bs4 import BeautifulSoup


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

TARGET_BANKS_FILE = BASE_DIR / "target_banks.json"
OUTPUT_FILE = DATA_DIR / "irp_disclosure_rates.json"

DISCLOSURE_URLS = [
    {
        "name": "KB퇴직연금_타사제공상품",
        "url": "https://okbfex.kbstar.com/quics?page=C110015",
    }
]

PERIOD_MAP = {
    "3개월": "3m",
    "6개월": "6m",
    "1년": "12m",
    "12개월": "12m",
    "2년": "24m",
    "24개월": "24m",
    "3년": "36m",
    "36개월": "36m",
}

# 타사 공시 상품명에 나타날 수 있는 표기
BANK_ALIASES = {
    "우리금융": [
        "우리금융저축은행",
    ],
    "KB": [
        "KB저축은행",
        "케이비저축은행",
    ],
    "신한": [
        "신한저축은행",
    ],
    "하나": [
        "하나저축은행",
    ],
    "SBI": [
        "SBI저축은행",
        "에스비아이저축은행",
    ],
    "OK": [
        "OK저축은행",
        "오케이저축은행",
    ],
    "한국투자": [
        "한국투자저축은행",
    ],
    "웰컴": [
        "웰컴저축은행",
    ],
    "애큐온": [
        "애큐온저축은행",
    ],
    "다올": [
        "다올저축은행",
    ],
    "DB": [
        "DB저축은행",
        "디비저축은행",
    ],
    "JT친애": [
        "JT친애저축은행",
        "제이티친애저축은행",
    ],
    "NH": [
        "NH저축은행",
        "엔에이치저축은행",
    ],
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/142.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
}

urllib3.disable_warnings(
    urllib3.exceptions.InsecureRequestWarning
)

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def clean_text(value):
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def load_json(path, default=None):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_targets():
    if not TARGET_BANKS_FILE.is_file():
        raise FileNotFoundError(
            f"IRP disclosure target file not found: {TARGET_BANKS_FILE}"
        )

    data = load_json(TARGET_BANKS_FILE, {})

    if isinstance(data, dict):
        values = data.get("targets_deduped", [])
    elif isinstance(data, list):
        values = data
    else:
        values = []

    targets = [
        clean_text(x)
        for x in values
        if clean_text(x)
    ]
    if not targets:
        raise ValueError(
            f"IRP disclosure target list is empty: {TARGET_BANKS_FILE}"
        )
    return targets


def fetch_html(url):
    response = SESSION.get(
        url,
        timeout=20,
        verify=False,
        allow_redirects=True,
    )

    response.raise_for_status()

    if not response.encoding:
        response.encoding = response.apparent_encoding

    return response.text, response.url


def identify_bank(product_name, targets):
    normalized = clean_text(product_name).lower()

    # 반드시 "저축은행" 상품만 인식해
    # 신한은행/국민은행 등을 오인하지 않도록 한다.
    if "저축은행" not in normalized:
        return None

    for bank in targets:
        for alias in BANK_ALIASES.get(bank, []):
            if alias.lower() in normalized:
                return bank

    return None


def normalize_period(text):
    value = clean_text(text)

    for label, key in PERIOD_MAP.items():
        if re.search(
            rf"(?<!\d){re.escape(label)}(?!\d)",
            value,
            re.I,
        ):
            return key

    return None


def parse_rate_cell(text):
    value = clean_text(text)

    if value in ("", "-", "–", "—"):
        return None

    # 셀 전체가 금리 숫자에 가까운 경우만 인정
    match = re.fullmatch(
        r"(?:연\s*)?(\d{1,2}(?:\.\d{1,4})?)\s*%?",
        value,
        re.I,
    )

    if not match:
        return None

    rate = float(match.group(1))

    if 0.1 <= rate <= 10.0:
        return rate

    return None


def parse_tables(html, source_name, source_url, targets):
    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    rows_out = []

    last_product = ""

    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            cells = [
                clean_text(
                    cell.get_text(
                        " ",
                        strip=True,
                    )
                )
                for cell in tr.find_all(
                    ["th", "td"]
                )
            ]

            if not cells:
                continue

            joined = " | ".join(cells)

            # 상품명 셀 찾기
            product = None

            for cell in cells:
                if "저축은행" in cell:
                    product = cell
                    last_product = cell
                    break

            if product is None:
                product = last_product

            if not product:
                continue

            bank = identify_bank(
                product,
                targets,
            )

            if not bank:
                continue

            # 만기 찾기
            period_key = None
            period_index = None

            for idx, cell in enumerate(cells):
                key = normalize_period(cell)
                if key:
                    period_key = key
                    period_index = idx
                    break

            if not period_key:
                continue

            # 만기 뒤 셀에서 금리 후보만 수집한다.
            # 표 구조는 예정적용금리 DB/DC/IRP 순이므로
            # rate-like 값의 마지막 3개를 DB/DC/IRP로 본다.
            tail = (
                cells[period_index + 1:]
                if period_index is not None
                else cells
            )

            numeric_rates = []

            for cell in tail:
                rate = parse_rate_cell(cell)
                if rate is not None:
                    numeric_rates.append(rate)

            # DB/DC/IRP 3개를 모두 특정할 수 있을 때만 채움.
            # 모호한 행은 잘못된 숫자를 넣지 않는다.
            if len(numeric_rates) < 3:
                continue

            db_rate, dc_rate, irp_rate = numeric_rates[-3:]

            rows_out.append({
                "bank": bank,
                "product": product,
                "period": period_key,
                "db_rate": db_rate,
                "dc_rate": dc_rate,
                "irp_rate": irp_rate,
                "source_name": source_name,
                "source_url": source_url,
                "raw_row": joined[:1000],
            })

    return rows_out


def build_bank_results(rows, targets):
    result = {}

    for bank in targets:
        result[bank] = {
            "bank": bank,
            "rates": {
                "3m": None,
                "6m": None,
                "12m": None,
                "24m": None,
                "36m": None,
            },
            "status": "not_found",
            "sources": [],
            "updated_at": datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
        }

    for row in rows:
        bank = row["bank"]
        period = row["period"]
        rate = row["irp_rate"]

        if bank not in result:
            continue

        old = result[bank]["rates"].get(period)

        # 같은 은행/만기가 여러 사업자 상품으로 존재할 경우
        # 일단 최고 IRP 금리를 대표값으로 저장.
        if old is None or rate > old:
            result[bank]["rates"][period] = rate

        source_ref = {
            "source_name": row["source_name"],
            "source_url": row["source_url"],
            "product": row["product"],
            "period": period,
            "irp_rate": rate,
        }

        if source_ref not in result[bank]["sources"]:
            result[bank]["sources"].append(source_ref)

    for bank, item in result.items():
        found = sum(
            value is not None
            for value in item["rates"].values()
        )

        if found >= 3:
            item["status"] = "verified_disclosure"

        elif found >= 1:
            item["status"] = "verified_disclosure_partial"

        else:
            item["status"] = "not_found"

    return result


def main():
    targets = load_targets()

    print("=" * 72)
    print("SBRateBot V5 IRP Common Disclosure Collector")
    print("=" * 72)
    print(
        "대상:",
        ", ".join(targets),
    )
    print()

    all_rows = []
    source_errors = []

    for source in DISCLOSURE_URLS:
        print(
            "[SOURCE]",
            source["name"],
        )

        try:
            html, final_url = fetch_html(
                source["url"]
            )

            rows = parse_tables(
                html,
                source["name"],
                final_url,
                targets,
            )

            all_rows.extend(rows)

            print(
                "  저축은행 IRP 행:",
                len(rows),
            )

        except Exception as e:
            source_errors.append({
                "source": source["name"],
                "url": source["url"],
                "error": str(e),
            })

            print(
                "  오류:",
                e,
            )

    results = build_bank_results(
        all_rows,
        targets,
    )

    output = {
        "generated_at": datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "strategy": "retirement_provider_disclosure",
        "sources": DISCLOSURE_URLS,
        "source_errors": source_errors,
        "banks": results,
        "raw_match_count": len(all_rows),
    }

    save_json(
        OUTPUT_FILE,
        output,
    )

    print()
    print("=" * 72)

    for bank in targets:
        item = results[bank]

        print(
            bank,
            ":",
            item["rates"],
            f"[{item['status']}]",
        )

    print("=" * 72)
    print(
        "저장:",
        OUTPUT_FILE,
    )


if __name__ == "__main__":
    main()
