"""Extend the FISIS management cache with funding, soundness and profitability data.

This module intentionally monkey-patches the existing provider so the proven management
report path remains intact. It never exposes or stores the FISIS authentication key.
"""

INTELLIGENCE_SCHEMA_VERSION = 1


def install_fisis_intelligence_patch():
    import fisis_management as fm

    if getattr(fm, "_sbrate_intelligence_patch_installed", False):
        return True

    # Funding / depositor composition
    fm.TABLES.setdefault("SE028", {}).update({
        "deposits": "A1",
        "demand_deposits": "A11",
        "time_deposits": "A14",
        "savings_deposits": "A15",
        "corporate_free_deposits": "A16",
        "installment_savings": "A17",
    })
    fm.TABLES.setdefault("SE031", {}).update({
        "personal_deposits": "A",
        "corporate_deposits": "B",
        "sole_prop_deposits": "B1",
        "other_deposits": "C",
        "depositor_total": "D",
    })

    # Profitability / funding cost
    fm.TABLES.setdefault("SE006", {}).update({
        "operating_revenue": "A",
        "operating_expense": "B",
        "operating_profit": "C",
    })
    fm.TABLES.setdefault("SE010", {}).update({
        "roa": "C",
        "roe": "D",
    })
    fm.TABLES.setdefault("SE014", {}).update({
        "net_interest_income": "A",
        "interest_income": "A1",
        "loan_interest_income": "A13",
        "interest_expense": "A2",
        "deposit_interest_expense": "A21",
        "time_deposit_interest_expense": "A215",
    })

    # Soundness / liquidity / capital detail
    fm.TABLES.setdefault("SE008", {}).update({
        "total_credit": "A1",
        "fixed_below_loans": "A3",
        "npl_ratio_detail": "A4",
        "allowance_required": "A5",
        "allowance_balance": "A6",
        "allowance_total_credit_ratio": "A7",
        "allowance_required_coverage": "A8",
        "npl_coverage_ratio": "A9",
    })
    fm.TABLES.setdefault("SE011", {}).update({
        "liquidity_ratio": "A",
        "liquid_assets": "A1",
        "liquid_liabilities": "A2",
        "available_funds_ratio": "B",
        "average_deposits": "B2",
    })
    fm.TABLES.setdefault("SE016", {}).update({
        "regulatory_capital": "E",
        "risk_weighted_assets": "F",
        "bis_ratio_detail": "G",
    })

    # Lending mix useful for risk context
    fm.TABLES.setdefault("SE020", {}).update({
        "sme_loans": "A1",
        "sole_prop_loans": "A11",
        "large_corp_loans": "A2",
    })
    fm.TABLES.setdefault("SE036", {}).update({
        "industry_corporate_loans": "A",
        "manufacturing_loans": "A1",
        "construction_loans": "A2",
        "wholesale_retail_loans": "A3",
        "real_estate_industry_loans": "A6",
    })

    amount_metrics = {
        "deposits", "demand_deposits", "time_deposits", "savings_deposits",
        "corporate_free_deposits", "installment_savings", "personal_deposits",
        "corporate_deposits", "sole_prop_deposits", "other_deposits", "depositor_total",
        "operating_revenue", "operating_expense", "operating_profit", "net_interest_income",
        "interest_income", "loan_interest_income", "interest_expense", "deposit_interest_expense",
        "time_deposit_interest_expense", "total_credit", "fixed_below_loans",
        "allowance_required", "allowance_balance", "liquid_assets", "liquid_liabilities",
        "average_deposits", "regulatory_capital", "risk_weighted_assets", "sme_loans",
        "sole_prop_loans", "large_corp_loans", "industry_corporate_loans",
        "manufacturing_loans", "construction_loans", "wholesale_retail_loans",
        "real_estate_industry_loans",
    }
    ratio_metrics = {
        "roa", "roe", "npl_ratio_detail", "allowance_total_credit_ratio",
        "allowance_required_coverage", "npl_coverage_ratio", "liquidity_ratio",
        "available_funds_ratio", "bis_ratio_detail",
    }
    for metric in amount_metrics:
        fm.METRIC_KIND[metric] = "amount"
    for metric in ratio_metrics:
        fm.METRIC_KIND[metric] = "ratio"

    original_cache_is_fresh = fm._cache_is_fresh
    original_build_store = fm._build_store

    def cache_is_fresh(store):
        if not original_cache_is_fresh(store):
            return False
        return int((store or {}).get("intelligence_schema_version") or 0) >= INTELLIGENCE_SCHEMA_VERSION

    def build_store():
        store = original_build_store()
        if isinstance(store, dict):
            store["intelligence_schema_version"] = INTELLIGENCE_SCHEMA_VERSION
            store["intelligence_metric_groups"] = ["funding", "soundness", "profitability"]
        return store

    fm._cache_is_fresh = cache_is_fresh
    fm._build_store = build_store
    fm._sbrate_intelligence_patch_installed = True
    print("FISIS management intelligence patch installed: schema", INTELLIGENCE_SCHEMA_VERSION)
    return True
