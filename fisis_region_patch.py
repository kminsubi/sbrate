import re
import sys


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

    rules = (
        (("서울특별시", "서울시", "서울 "), "서울"),
        (("인천광역시", "인천시", "인천 "), "인천"),
        (("경기도", "경기 "), "경기"),
        (("세종특별자치시", "세종시", "세종 "), "충청"),
        (("대전광역시", "대전시", "대전 ", "충청북도", "충북", "충청남도", "충남"), "충청"),
        (("광주광역시", "광주시", "광주 ", "전라북도", "전북", "전북특별자치도", "전라남도", "전남"), "전라"),
        (("부산광역시", "부산시", "부산 ", "대구광역시", "대구시", "대구 ", "울산광역시", "울산시", "울산 ", "경상북도", "경북", "경상남도", "경남"), "경상"),
        (("강원특별자치도", "강원도", "강원 "), "강원"),
        (("제주특별자치도", "제주도", "제주 "), "제주"),
    )
    for tokens, region in rules:
        if any(token in text for token in tokens):
            return region
    return "기타"


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
                "region": _region_from_address(address),
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
        return int((store or {}).get("region_schema_version") or 0) >= 1

    def build_store_with_region():
        store = original_build_store()
        if isinstance(store, dict):
            store["region_schema_version"] = 1
            quarters = store.get("quarters") if isinstance(store.get("quarters"), dict) else {}
            latest_key = max(quarters.keys(), default="")
            latest = quarters.get(latest_key) if latest_key else {}
            rows = latest.get("banks") if isinstance(latest, dict) else []
            store["latest_region_count"] = sum(
                1 for row in (rows or [])
                if isinstance(row, dict) and str(row.get("region") or "").strip()
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
                    companies = fm._companies()
                    with_address = [x for x in companies if x.get("address")]
                    with_region = [x for x in companies if x.get("region")]
                    woori = next(
                        (x for x in companies if "우리금융저축은행" in str(x.get("finance_nm") or "")),
                        None,
                    )
                    return jsonify({
                        "ok": True,
                        "company_count": len(companies),
                        "address_count": len(with_address),
                        "region_count": len(with_region),
                        "woori": {
                            "bank": (woori or {}).get("finance_nm"),
                            "address": (woori or {}).get("address"),
                            "region": (woori or {}).get("region"),
                        },
                    })
                except Exception as exc:
                    return jsonify({"ok": False, "error": str(exc)}), 500

    print("FISIS management region patch installed: headquarters address -> region")
    return True
