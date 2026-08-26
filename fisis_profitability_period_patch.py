"""Make the intelligence layer respect FISIS profitability periodicity.

FISIS SE010 (profitability / ROA / ROE) rejects term=Q for savings banks.
Do not retry an unsupported quarterly request and do not invent quarterly
ROA/ROE values.  The Q1 management view remains ready using the directly
reported quarterly P&L metrics, while ROA/ROE stay blank with an explicit note.
"""


def install_fisis_profitability_period_patch():
    import fisis_intelligence_store as store
    import management_intelligence as intelligence

    if getattr(store, "_profitability_period_patch_installed", False):
        return True

    # Force one cheap schema migration.  The persisted schema-5 cache already
    # contains 79-bank coverage for the corrected SE014 interest/expense fields.
    # Reusing it avoids any new FISIS calls during this migration.
    store.SCHEMA_VERSION = 7
    store.TABLES.pop("SE010", None)
    store.UPGRADE_TABLES = {}

    intelligence.INTELLIGENCE_SCHEMA_VERSION = 7
    original_build = intelligence.build_intelligence

    def build_with_periodicity(section="funding", base=None, compare=None):
        data = original_build(section=section, base=base, compare=compare)
        if not isinstance(data, dict):
            return data

        notes = data.setdefault("notes", {})
        notes["roa_roe_basis"] = (
            "FISIS 저축은행 수익성(SE010)은 분기(Q) 조회를 지원하지 않습니다. "
            "따라서 최신 분기 화면의 ROA·ROE는 추정하지 않고 '-'로 표시하며, "
            "당기순이익·영업이익·이자수익·이자비용 등 분기 공시 실적만 사용합니다."
        )

        if str(section or "").lower() == "profitability" and data.get("ok"):
            woori = data.get("woori") or {}
            metrics = woori.get("metrics") or {}
            operating_profit = (metrics.get("operating_profit") or {}).get("base")
            interest_expense = (metrics.get("interest_expense") or {}).get("base")
            schema = int(data.get("intelligence_schema_version") or 0)
            if schema >= 7 and operating_profit is not None and interest_expense is not None:
                data["ready"] = True
                data["periodicity"] = {
                    "quarterly_profitability": True,
                    "quarterly_roa_roe": False,
                    "roa_roe_source": "FISIS SE010",
                    "reason": "term=Q unsupported by FISIS for this table",
                }
        return data

    intelligence.build_intelligence = build_with_periodicity
    store._profitability_period_patch_installed = True
    print("FISIS profitability periodicity patch installed: quarterly ROA/ROE are not estimated")
    return True
