import re
import sys


# 저축은행중앙회 '전국 저축은행 현황'의 6개 권역 기준.
# https://www.fsb.or.kr/sabintr_0100.act
FSB_REGION_GROUPS = {
    "서울": [
        "DB", "JT친애", "KB", "NH", "OK", "OSB", "SBI", "대신", "더케이", "민국",
        "HB", "스카이", "바로", "신한", "애큐온", "예가람", "웰컴", "유안타", "다올",
        "조은", "키움예스", "푸른", "하나",
    ],
    "인천/경기": [
        "JT", "금화", "남양", "모아", "부림", "삼정", "상상인", "세람", "안국", "안양",
        "영진", "융창", "인성", "인천", "키움", "페퍼", "평택", "한국투자", "한화",
    ],
    "부산/경남": [
        "BNK", "DH", "IBK", "고려", "국제", "동원제일", "솔브레인", "에스앤티", "우리",
        "조흥", "진주", "흥국",
    ],
    "대구/경북/강원": [
        "CK", "대백", "대아", "대원", "드림", "라온", "머스트삼일", "엠에스", "오성",
        "유니온", "참",
    ],
    "호남": [
        "대한", "더블", "동양", "삼호", "센트럴", "스마트", "스타",
    ],
    "충청": [
        "대명", "상상인플러스", "아산", "우리금융", "오투", "청주", "한성",
    ],
}

# FISIS 회사명은 일부 영문 약칭을 한글 음역으로 제공한다.
FISIS_NAME_ALIASES = {
    "디비": "DB",
    "제이티친애": "JT친애",
    "케이비": "KB",
    "엔에이치": "NH",
    "오케이": "OK",
    "오에스비": "OSB",
    "에스비아이": "SBI",
    "에이치비": "HB",
    "제이티": "JT",
    "비엔케이": "BNK",
    "디에이치": "DH",
    "아이비케이": "IBK",
    "씨케이": "CK",
}


def _normalize_bank(name):
    text = re.sub(r"\s+", "", str(name or ""))
    text = text.replace("㈜", "").replace("(주)", "")
    text = text.replace("상호저축은행", "").replace("저축은행", "")
    return text.upper()


FSB_REGION_BY_BANK = {
    _normalize_bank(bank): region
    for region, banks in FSB_REGION_GROUPS.items()
    for bank in banks
}
for alias, canonical in FISIS_NAME_ALIASES.items():
    key = _normalize_bank(canonical)
    if key in FSB_REGION_BY_BANK:
        FSB_REGION_BY_BANK[_normalize_bank(alias)] = FSB_REGION_BY_BANK[key]


def _address_from_company_row(row):
    if not isinstance(row, dict):
        return ""

    preferred = (
        "finance_addr",
        "finance_address",
        "address",
        "addr",
        "finance_adr",
        "finance_adres",
    )
    for key in preferred:
        value = str(row.get(key) or "").strip()
        if value:
            return value

    for key, value in row.items():
        key_text = str(key or "").lower()
        if "addr" in key_text or "address" in key_text or "주소" in str(key or ""):
            text = str(value or "").strip()
            if text:
                return text
    return ""


def _region_from_address(address):
    text = re.sub(r"\s+", " ", str(address or "")).strip()
    if not text:
        return ""
    first = text.split(" ", 1)[0]
    if first.startswith("서울"):
        return "서울"
    if first.startswith(("인천", "경기")):
        return "인천/경기"
    if first.startswith(("부산", "경남")):
        return "부산/경남"
    if first.startswith(("대구", "경북", "강원")):
        return "대구/경북/강원"
    if first.startswith(("광주", "전라", "전북", "전남", "제주")):
        return "호남"
    if first.startswith(("세종", "대전", "충청", "충북", "충남")):
        return "충청"
    return ""


def _region_for_company(name, address=""):
    return FSB_REGION_BY_BANK.get(_normalize_bank(name)) or _region_from_address(address) or "기타"


def install_fisis_region_patch():
    import fisis_management as fm

    if getattr(fm, "_sbrate_region_patch_installed", False):
        return True

    original_fetch_company = fm._fetch_company
    original_build_store = fm._build_store
    original_cache_is_fresh = fm._cache_is_fresh

    def companies_with_region():
        rows = fm._as_rows(fm._api_get("companySearch", partDiv=fm.FISIS_SECTOR).get("list"))
        active = []
        seen = set()
        for row in rows:
            name = str(row.get("finance_nm") or "").strip()
            code = str(row.get("finance_cd") or "").strip()
            if not name or not code or "[폐]" in name:
                continue
            if code in seen:
                continue
            seen.add(code)
            address = _address_from_company_row(row)
            active.append({
                "finance_cd": code,
                "finance_nm": name,
                "address": address,
                "region": _region_for_company(name, address),
            })
        return active

    def fetch_company_with_region(company, start_month, end_month):
        quarters, errors = original_fetch_company(company, start_month, end_month)
        region = str(company.get("region") or "").strip()
        for row in (quarters or {}).values():
            if isinstance(row, dict):
                row["region"] = region or None
        return quarters, errors

    def cache_is_fresh(store):
        if not original_cache_is_fresh(store):
            return False
        return int((store or {}).get("region_schema_version") or 0) >= 3

    def build_store_with_region():
        store = original_build_store()
        if isinstance(store, dict):
            store["region_schema_version"] = 3
            store["region_source"] = "저축은행중앙회 전국 저축은행 현황"
            store["region_source_url"] = "https://www.fsb.or.kr/sabintr_0100.act"
            quarters = store.get("quarters") if isinstance(store.get("quarters"), dict) else {}
            latest_key = max(quarters.keys(), default="")
            latest = quarters.get(latest_key) if latest_key else {}
            rows = latest.get("banks") if isinstance(latest, dict) else []
            store["latest_region_count"] = sum(
                1 for row in (rows or [])
                if isinstance(row, dict) and str(row.get("region") or "").strip() not in ("", "기타")
            )
        return store

    fm._companies = companies_with_region
    fm._fetch_company = fetch_company_with_region
    fm._cache_is_fresh = cache_is_fresh
    fm._build_store = build_store_with_region
    fm._sbrate_region_patch_installed = True

    app_module = sys.modules.get("app") or sys.modules.get("__main__")
    if app_module is not None and hasattr(app_module, "app"):
        flask_app = app_module.app
        existing = {rule.rule for rule in flask_app.url_map.iter_rules()}
        if "/api/management-report/region-diagnostic" not in existing:
            from flask import jsonify

            @flask_app.get("/api/management-report/region-diagnostic")
            def management_region_diagnostic():
                try:
                    store = fm.get_management_store(trigger_refresh=False) or {}
                    quarters = store.get("quarters") if isinstance(store.get("quarters"), dict) else {}
                    latest_key = max(quarters.keys(), default="")
                    latest = quarters.get(latest_key) if isinstance(quarters.get(latest_key), dict) else {}
                    cached_rows = latest.get("banks") if isinstance(latest.get("banks"), list) else []
                    companies = [
                        {"finance_nm": row.get("bank"), "address": "", "region": row.get("region")}
                        for row in cached_rows if isinstance(row, dict)
                    ]
                    with_address = [x for x in companies if x.get("address")]
                    with_region = [x for x in companies if x.get("region") and x.get("region") != "기타"]
                    unmatched = [
                        x.get("finance_nm") for x in companies
                        if x.get("region") in (None, "", "기타")
                    ]
                    woori = next(
                        (x for x in companies if "우리금융저축은행" in str(x.get("finance_nm") or "")),
                        None,
                    )
                    return jsonify({
                        "ok": True,
                        "company_count": len(companies),
                        "address_count": len(with_address),
                        "region_count": len(with_region),
                        "unmatched": unmatched,
                        "region_source": "저축은행중앙회 전국 저축은행 현황",
                        "woori": {
                            "bank": (woori or {}).get("finance_nm"),
                            "address": (woori or {}).get("address"),
                            "region": (woori or {}).get("region"),
                        },
                    })
                except Exception as exc:
                    return jsonify({"ok": False, "error": str(exc)}), 500

    print("FISIS management region patch installed: FSB 6-region mapping")
    return True
