import os
import string
import sys

import requests

BASE = "https://fisis.fss.or.kr/openapi"
TIMEOUT = 20


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
    return r.json()


def _name(row):
    if not isinstance(row, dict):
        return ""
    return str(
        row.get("finance_nm")
        or row.get("financeNm")
        or row.get("finance_name")
        or row.get("kor_co_nm")
        or row.get("name")
        or ""
    )


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

        out = {"ok": True, "configured": True, "company_part_candidates": [], "company_unfiltered": None}
        errors = []

        # First try an unfiltered company lookup. Some FISIS deployments allow this.
        try:
            payload = _get("companySearch", key)
            rows = _rows(payload)
            out["company_unfiltered"] = {
                "count": len(rows),
                "sample_keys": sorted(rows[0].keys()) if rows and isinstance(rows[0], dict) else [],
                "matching": [row for row in rows if any(t in _name(row) for t in ("우리금융", "SBI", "OK", "웰컴", "KB"))][:12],
            }
        except Exception as exc:
            errors.append(f"company-unfiltered: {type(exc).__name__}: {exc}")

        # Discover the savings-bank partDiv without hard-coding a possibly stale code.
        for code in list(string.ascii_uppercase) + [str(i) for i in range(10)]:
            try:
                payload = _get("companySearch", key, partDiv=code)
                rows = _rows(payload)
                if not rows:
                    continue
                names = [_name(r) for r in rows]
                hits = [n for n in names if any(t in n for t in ("우리금융", "SBI", "OK", "웰컴", "KB"))]
                if hits or 60 <= len(rows) <= 100:
                    out["company_part_candidates"].append({
                        "partDiv": code,
                        "count": len(rows),
                        "hits": hits[:10],
                        "sample_keys": sorted(rows[0].keys()) if isinstance(rows[0], dict) else [],
                        "sample": rows[:3],
                    })
            except Exception as exc:
                if len(errors) < 8:
                    errors.append(f"partDiv={code}: {type(exc).__name__}: {exc}")

        out["errors"] = errors
        return jsonify(out)

    app_module._fisis_probe_installed = True
    return True
