import os
import sys

import requests

BASE = "https://fisis.fss.or.kr/openapi"
TIMEOUT = 20
SAVINGS_BANK_SECTOR = "E"
WOORI_FINANCE_CD = "0010488"
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
    result = payload.get("result") if isinstance(payload, dict) else None
    rows = result.get("list") if isinstance(result, dict) else None
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
        try:
            companies = _rows(_get("companySearch", key, partDiv=SAVINGS_BANK_SECTOR))
            active = [r for r in companies if "[폐]" not in str(r.get("finance_nm") or "")]
            out["companies"] = {
                "count": len(companies),
                "active_name_count": len(active),
                "woori": [r for r in companies if str(r.get("finance_cd") or "") == WOORI_FINANCE_CD],
            }
        except Exception as exc:
            out["companies"] = {"count": 0, "error": f"{type(exc).__name__}: {exc}"}

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
        return jsonify(out)

    app_module._fisis_probe_installed = True
    return True
