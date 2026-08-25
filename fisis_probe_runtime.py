import os
import sys

import requests

BASE = "https://fisis.fss.or.kr/openapi"
TIMEOUT = 25
SAVINGS_BANK_SECTOR = "E"
WOORI_FINANCE_CD = "0010488"
KEYWORDS = (
    "재무", "자산", "대출", "여신", "기업", "가계", "손익", "순이익",
    "경영", "BIS", "자본", "건전", "연체", "고정이하", "임직원", "직원", "인원", "생산성",
)
VALIDATION_METRICS = {
    "total_assets": ("SE003", "A"),
    "corporate_loans": ("SE020", "A"),
    "household_loans": ("SE020", "B"),
    "total_loans": ("SE020", "D"),
    "bis_ratio": ("SE035", "C"),
    "npl_ratio": ("SE034", "A"),
    "delinquency_ratio": ("SE019", "C"),
    "net_income_press": ("SE033", "A"),
    "net_income_statement": ("SE006", "K"),
    "employees": ("SE001", "A"),
}


def _rows(payload):
    if not isinstance(payload, dict):
        return []
    result = payload.get("result")
    if not isinstance(result, dict):
        return []
    rows = result.get("list")
    return rows if isinstance(rows, list) else []


def _get(path, key, **params):
    query = {"lang": "kr", "auth": key}
    query.update({k: v for k, v in params.items() if v not in (None, "")})
    r = requests.get(f"{BASE}/{path}.json", params=query, timeout=TIMEOUT)
    r.raise_for_status()
    payload = r.json()
    result = payload.get("result") if isinstance(payload, dict) else None
    if isinstance(result, dict):
        err_cd = str(result.get("err_cd") or "000")
        if err_cd not in ("000", "0", ""):
            raise RuntimeError(f"FISIS {path} err_cd={err_cd} err_msg={result.get('err_msg')}")
    return payload


def _stat_name(row):
    return str((row or {}).get("list_nm") or "")


def _score_stat(row):
    text = _stat_name(row)
    return sum(1 for word in KEYWORDS if word.lower() in text.lower())


def _safe_stat_result(payload):
    result = payload.get("result") if isinstance(payload, dict) else {}
    if not isinstance(result, dict):
        return {}
    return {
        "unit": result.get("unit"),
        "description": result.get("description"),
        "list": result.get("list"),
        "total_count": result.get("total_count"),
    }


def install_fisis_probe():
    app_module = sys.modules.get("app") or sys.modules.get("__main__")
    if app_module is None or not hasattr(app_module, "app"):
        return False
    if getattr(app_module, "_fisis_probe_installed", False):
        return True

    flask_app = app_module.app
    from flask import jsonify

    @flask_app.get("/api/_sbrate/fisis-probe")
    def fisis_probe():
        key = str(os.environ.get("FISIS_API_KEY") or "").strip()
        if not key:
            return jsonify({"ok": False, "configured": False, "error": "FISIS_API_KEY missing"}), 503

        out = {"ok": True, "configured": True, "sector": SAVINGS_BANK_SECTOR}
        errors = []

        try:
            companies = _rows(_get("companySearch", key, partDiv=SAVINGS_BANK_SECTOR))
            active = [r for r in companies if "[폐]" not in str(r.get("finance_nm") or "")]
            out["companies"] = {
                "count": len(companies),
                "active_name_count": len(active),
                "sample_keys": sorted(companies[0].keys()) if companies else [],
                "woori": [r for r in companies if "우리금융" in str(r.get("finance_nm") or "")],
                "sample": companies[:5],
            }
        except Exception as exc:
            out["companies"] = {"count": 0}
            errors.append(f"companies: {type(exc).__name__}: {exc}")

        statistics = []
        try:
            statistics = _rows(_get("statisticsListSearch", key, lrgDiv=SAVINGS_BANK_SECTOR))
            out["statistics"] = {
                "count": len(statistics),
                "sample_keys": sorted(statistics[0].keys()) if statistics else [],
                "all": statistics,
            }
        except Exception as exc:
            errors.append(f"statistics-all: {type(exc).__name__}: {exc}")
            merged = {}
            for category in ("A", "B", "C", "D", "P"):
                try:
                    for row in _rows(_get("statisticsListSearch", key, lrgDiv=SAVINGS_BANK_SECTOR, smlDiv=category)):
                        list_no = str(row.get("list_no") or "")
                        if list_no:
                            merged[list_no] = row
                except Exception as sub_exc:
                    errors.append(f"statistics-{category}: {type(sub_exc).__name__}: {sub_exc}")
            statistics = list(merged.values())
            out["statistics"] = {
                "count": len(statistics),
                "sample_keys": sorted(statistics[0].keys()) if statistics else [],
                "all": statistics,
            }

        candidates = sorted(
            [row for row in statistics if _score_stat(row) > 0],
            key=lambda row: (-_score_stat(row), str(row.get("list_no") or "")),
        )[:30]
        account_map = []
        for row in candidates:
            list_no = str(row.get("list_no") or "")
            if not list_no:
                continue
            try:
                accounts = _rows(_get("accountListSearch", key, listNo=list_no))
                matching = [
                    a for a in accounts
                    if any(word.lower() in str(a.get("account_nm") or "").lower() for word in KEYWORDS)
                ]
                account_map.append({
                    "list_no": list_no,
                    "list_nm": row.get("list_nm"),
                    "score": _score_stat(row),
                    "account_count": len(accounts),
                    "accounts": accounts,
                    "matching_accounts": matching,
                })
            except Exception as exc:
                errors.append(f"accounts-{list_no}: {type(exc).__name__}: {exc}")
        out["candidate_accounts"] = account_map

        validation = {}
        for metric, (list_no, account_cd) in VALIDATION_METRICS.items():
            try:
                payload = _get(
                    "statisticsInfoSearch",
                    key,
                    financeCd=WOORI_FINANCE_CD,
                    listNo=list_no,
                    accountCd=account_cd,
                    term="Q",
                    startBaseMm="202603",
                    endBaseMm="202603",
                )
                validation[metric] = {
                    "list_no": list_no,
                    "account_cd": account_cd,
                    "result": _safe_stat_result(payload),
                }
            except Exception as exc:
                validation[metric] = {
                    "list_no": list_no,
                    "account_cd": account_cd,
                    "error": f"{type(exc).__name__}: {exc}",
                }
        out["validation_2026q1"] = validation
        out["errors"] = errors[:30]
        return jsonify(out)

    app_module._fisis_probe_installed = True
    return True
