"""Derive quarterly ROA/ROE from FISIS source balances.

FISIS SE010 (profitability) rejects term=Q for savings banks, so quarterly
ROA/ROE cannot be fetched directly.  Instead we fetch quarterly BS equity from
SE017 and calculate transparent reference ratios from FISIS source data:

    annualized YTD net income / average(beginning, ending) assets/equity

These values are explicitly marked as derived and are never presented as the
direct SE010 published ratios.
"""

import re


def install_fisis_profitability_period_patch():
    import fisis_intelligence_store as store
    import management_intelligence as intelligence

    if getattr(store, "_profitability_period_patch_installed", False):
        return True

    # Schema 8 adds one quarterly source field only: BS equity from SE017.
    # Existing schema-7 rows are reused and only SE017 is fetched during the
    # incremental migration, keeping FISIS traffic small.
    store.SCHEMA_VERSION = 8
    store.MAX_QUARTERS = max(int(getattr(store, "MAX_QUARTERS", 6) or 6), 7)
    store.TABLES.pop("SE010", None)
    store.TABLES["SE017"] = {"bs_equity": "A"}
    store.UPGRADE_TABLES = {"SE017": {"bs_equity": "A"}}
    store.AMOUNT_METRICS.add("bs_equity")
    store.METRIC_KIND["bs_equity"] = "amount"

    intelligence.INTELLIGENCE_SCHEMA_VERSION = 8
    original_build = intelligence.build_intelligence

    def qno(key):
        match = re.fullmatch(r"\d{4}Q([1-4])", str(key or ""))
        return int(match.group(1)) if match else None

    def prior_year_end(key):
        match = re.fullmatch(r"(\d{4})Q[1-4]", str(key or ""))
        return f"{int(match.group(1)) - 1}Q4" if match else None

    def row_key(row):
        code = str((row or {}).get("finance_cd") or "").strip()
        if code:
            return code
        return intelligence._normalize_bank((row or {}).get("bank"))

    def bank_map(meta):
        rows = (meta or {}).get("banks") if isinstance(meta, dict) else []
        return {row_key(row): row for row in (rows or []) if isinstance(row, dict)}

    def derive_for(raw, opening, quarter):
        if not isinstance(raw, dict) or not isinstance(opening, dict):
            return None, None
        quarter_no = qno(quarter)
        if quarter_no not in (1, 2, 3, 4):
            return None, None

        net_income = intelligence._number(raw.get("net_income"))
        end_assets = intelligence._number(raw.get("total_assets"))
        begin_assets = intelligence._number(opening.get("total_assets"))
        end_equity = intelligence._number(raw.get("bs_equity"))
        begin_equity = intelligence._number(opening.get("bs_equity"))
        if net_income is None:
            return None, None

        annualized_income = net_income * (4.0 / quarter_no)
        avg_assets = (
            (begin_assets + end_assets) / 2.0
            if begin_assets is not None and end_assets is not None
            else None
        )
        avg_equity = (
            (begin_equity + end_equity) / 2.0
            if begin_equity is not None and end_equity is not None
            else None
        )
        roa = (
            intelligence._round(annualized_income / avg_assets * 100.0, 4)
            if avg_assets not in (None, 0)
            else None
        )
        roe = (
            intelligence._round(annualized_income / avg_equity * 100.0, 4)
            if avg_equity not in (None, 0)
            else None
        )
        return roa, roe

    def ratio_pack(base_value, compare_value, yoy_value):
        return {
            "base": intelligence._round(base_value, 4),
            "compare": intelligence._round(compare_value, 4),
            "delta": intelligence._round(base_value - compare_value, 4)
                if base_value is not None and compare_value is not None else None,
            "yoy_compare": intelligence._round(yoy_value, 4),
            "yoy_delta": intelligence._round(base_value - yoy_value, 4)
                if base_value is not None and yoy_value is not None else None,
            "derived": True,
        }

    def values_for_quarter(quarters, quarter, keys):
        if not quarter or quarter not in quarters:
            return {}
        current = bank_map(quarters.get(quarter) or {})
        opening_key = prior_year_end(quarter)
        opening = bank_map(quarters.get(opening_key) or {}) if opening_key else {}
        values = {}
        for key in keys:
            roa, roe = derive_for(current.get(key), opening.get(key), quarter)
            values[key] = {"roa": roa, "roe": roe}
        return values

    def build_with_derived_profitability(section="funding", base=None, compare=None):
        data = original_build(section=section, base=base, compare=compare)
        if not isinstance(data, dict):
            return data

        notes = data.setdefault("notes", {})
        notes["roa_roe_basis"] = (
            "ROA·ROE(산출)는 FISIS 분기 원천자료로 계산한 참고지표입니다. "
            "누적 당기순이익을 연환산하고, 전년말·해당분기말 총자산/자기자본(BS)의 "
            "평균으로 나누어 산출합니다. FISIS SE010의 공식 기간평잔 ROA·ROE와는 "
            "산식의 평균잔액 기준 차이로 소폭 다를 수 있습니다."
        )

        if str(section or "").lower() != "profitability" or not data.get("ok"):
            return data

        merged = intelligence._merge_store()
        quarters = merged.get("quarters") if isinstance(merged.get("quarters"), dict) else {}
        base_key = data.get("base")
        compare_key = data.get("compare")
        yoy_key = data.get("yoy_compare")
        payload_rows = data.get("rows") or []
        keys = [row_key(row) for row in payload_rows if isinstance(row, dict)]

        base_values = values_for_quarter(quarters, base_key, keys)
        compare_values = values_for_quarter(quarters, compare_key, keys)
        yoy_values = values_for_quarter(quarters, yoy_key, keys)

        derived_count = 0
        for row in payload_rows:
            if not isinstance(row, dict):
                continue
            key = row_key(row)
            metrics = row.setdefault("metrics", {})
            bv = base_values.get(key) or {}
            cv = compare_values.get(key) or {}
            yv = yoy_values.get(key) or {}
            for metric_name in ("roa", "roe"):
                base_value = bv.get(metric_name)
                metrics[metric_name] = ratio_pack(
                    base_value,
                    cv.get(metric_name),
                    yv.get(metric_name),
                )
                row[f"{metric_name}_derived"] = base_value is not None
            if bv.get("roa") is not None and bv.get("roe") is not None:
                derived_count += 1

        woori = next((row for row in payload_rows if row.get("is_woori")), None)
        data["woori"] = woori
        data["derived_profitability_count"] = derived_count
        data["periodicity"] = {
            "quarterly_profitability": True,
            "quarterly_roa_roe": True,
            "roa_roe_source": "derived from FISIS SE006 + SE003 + SE017",
            "method": "annualized YTD net income / average beginning-and-ending balance",
            "official_se010_quarterly_supported": False,
        }
        return data

    intelligence.build_intelligence = build_with_derived_profitability
    store._profitability_period_patch_installed = True
    print("FISIS profitability patch installed: quarterly ROA/ROE derived from source balances")
    return True
