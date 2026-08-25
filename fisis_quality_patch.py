import math


MIN_QUARTER_COVERAGE = 0.90


def install_fisis_quality_patch():
    import fisis_management as fm

    if getattr(fm, "_sbrate_quality_patch_installed", False):
        return True

    original_build_store = fm._build_store
    original_cache_is_fresh = fm._cache_is_fresh

    def cache_is_fresh(store):
        if not original_cache_is_fresh(store):
            return False
        return int((store or {}).get("quality_schema_version") or 0) >= 1

    def build_store_high_coverage():
        store = original_build_store()
        if not isinstance(store, dict):
            return store

        active_count = int(store.get("active_company_count") or 0)
        threshold = max(20, math.ceil(active_count * MIN_QUARTER_COVERAGE))
        quarters = store.get("quarters") if isinstance(store.get("quarters"), dict) else {}
        removed = []

        for key in list(quarters.keys()):
            meta = quarters.get(key) if isinstance(quarters.get(key), dict) else {}
            asset_count = int(meta.get("asset_bank_count") or 0)
            if not asset_count:
                rows = meta.get("banks") if isinstance(meta.get("banks"), list) else []
                asset_count = sum(
                    1 for row in rows
                    if isinstance(row, dict) and row.get("total_assets") is not None
                )
            if asset_count < threshold:
                removed.append({"quarter": key, "asset_bank_count": asset_count})
                quarters.pop(key, None)

        if not quarters:
            raise RuntimeError(
                f"FISIS 고신뢰 분기 데이터 없음: threshold={threshold}, removed={removed[-8:]}"
            )

        store["quarters"] = quarters
        store["quality_schema_version"] = 1
        store["minimum_quarter_coverage_ratio"] = MIN_QUARTER_COVERAGE
        store["minimum_quarter_asset_count"] = threshold
        store["withheld_partial_quarters"] = removed[-12:]
        return store

    fm._cache_is_fresh = cache_is_fresh
    fm._build_store = build_store_high_coverage
    fm._sbrate_quality_patch_installed = True

    print(f"FISIS management quality patch installed: coverage >= {MIN_QUARTER_COVERAGE:.0%}")
    return True
