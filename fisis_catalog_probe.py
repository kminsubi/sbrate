import re
import sys


KEYWORDS = (
    "예수", "예금", "수신", "자금조달", "조달", "이자비용", "이자수익", "순이자",
    "손익", "영업이익", "당기순이익", "ROA", "ROE", "총자산이익률", "자기자본이익률",
    "연체", "고정이하", "부실", "대손", "충당", "건전성", "BIS", "자기자본",
    "위험가중", "유동성", "예대율", "대출", "여신", "업종별", "담보별", "용도별",
    "가계", "기업", "중소기업", "부동산", "PF", "프로젝트", "점포", "임직원",
)

# FISIS 경영정보 공식 분류: 일반현황 / 재무현황 / 주요경영지표 / 주요영업활동.
STAT_CATEGORIES = "ABCD"


def _rows(value):
    if value is None:
        return []
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [x for x in value if isinstance(x, dict)]
    return []


def _clean_row(row):
    if not isinstance(row, dict):
        return {}
    blocked = {"auth", "api_key", "apikey", "key", "token"}
    return {
        str(k): v
        for k, v in row.items()
        if str(k).lower() not in blocked
    }


def _table_no(row):
    for key in ("list_no", "listNo", "list_cd", "listCd"):
        value = str((row or {}).get(key) or "").strip()
        if value:
            return value
    return ""


def _table_name(row):
    for key in ("list_nm", "listName", "list_name", "listNm"):
        value = str((row or {}).get(key) or "").strip()
        if value:
            return value
    return ""


def _account_code(row):
    for key in ("account_cd", "accountCd", "account_code"):
        value = str((row or {}).get(key) or "").strip()
        if value:
            return value
    return ""


def _account_name(row):
    for key in ("account_nm", "accountName", "account_name", "accountNm"):
        value = str((row or {}).get(key) or "").strip()
        if value:
            return value
    return ""


def _interesting(row):
    text = " ".join(str(v or "") for v in (row or {}).values()).upper()
    return any(keyword.upper() in text for keyword in KEYWORDS)


def scan_fisis_catalog(include_accounts=True, max_account_tables=60):
    import fisis_management as fm

    tables = {}
    category_errors = []

    for sml_div in STAT_CATEGORIES:
        try:
            result = fm._api_get(
                "statisticsListSearch",
                lrgDiv=fm.FISIS_SECTOR,
                smlDiv=sml_div,
            )
            for raw in _rows(result.get("list")):
                row = _clean_row(raw)
                list_no = _table_no(row)
                if not list_no:
                    continue
                item = tables.setdefault(list_no, row)
                item.setdefault("_sml_div", sml_div)
        except Exception as exc:
            category_errors.append({
                "sml_div": sml_div,
                "error": f"{type(exc).__name__}: {exc}",
            })

    ordered = sorted(
        tables.values(),
        key=lambda row: (_table_no(row), _table_name(row)),
    )
    interesting = [row for row in ordered if _interesting(row)]

    accounts = {}
    account_errors = []
    if include_accounts:
        for row in interesting[: max(1, int(max_account_tables))]:
            list_no = _table_no(row)
            if not list_no:
                continue
            try:
                result = fm._api_get("accountListSearch", listNo=list_no)
                items = []
                for raw in _rows(result.get("list")):
                    account = _clean_row(raw)
                    code = _account_code(account)
                    name = _account_name(account)
                    if code or name:
                        items.append(account)
                accounts[list_no] = items
            except Exception as exc:
                account_errors.append({
                    "list_no": list_no,
                    "error": f"{type(exc).__name__}: {exc}",
                })

    return {
        "ok": True,
        "sector": fm.FISIS_SECTOR,
        "source": fm.FISIS_SOURCE_NAME,
        "table_count": len(ordered),
        "interesting_table_count": len(interesting),
        "tables": ordered,
        "interesting_tables": interesting,
        "accounts": accounts,
        "category_errors": category_errors,
        "account_errors": account_errors,
        "keywords": list(KEYWORDS),
    }


def install_fisis_catalog_probe():
    app_module = sys.modules.get("app") or sys.modules.get("__main__")
    if app_module is None or not hasattr(app_module, "app"):
        return False
    if getattr(app_module, "_fisis_catalog_probe_installed", False):
        return True

    flask_app = app_module.app
    from flask import jsonify, request

    @flask_app.get("/api/management-report/fisis-catalog")
    def fisis_catalog_probe():
        try:
            accounts = str(request.args.get("accounts") or "1").strip() != "0"
            limit = int(request.args.get("account_limit") or 60)
            limit = min(max(limit, 1), 80)
            return jsonify(scan_fisis_catalog(include_accounts=accounts, max_account_tables=limit))
        except Exception as exc:
            return jsonify({"ok": False, "error": f"{type(exc).__name__}: {exc}"}), 500

    app_module._fisis_catalog_probe_installed = True
    print("FISIS catalog probe installed")
    return True
