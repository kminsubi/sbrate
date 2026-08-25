from datetime import datetime


def install_fisis_history_patch():
    import fisis_management as fm

    if getattr(fm, "_sbrate_history_patch_installed", False):
        return True

    original_cache_is_fresh = fm._cache_is_fresh
    original_build_store = fm._build_store

    def quarter_range():
        now = fm._now()
        start = "202001"
        completed_month = ((now.month - 1) // 3) * 3
        year = now.year
        if completed_month == 0:
            year -= 1
            completed_month = 12
        end = f"{year:04d}{completed_month:02d}"
        return start, end

    def cache_is_fresh(store):
        if not original_cache_is_fresh(store):
            return False
        quarter_range_meta = (store or {}).get("quarter_range") or {}
        return str(quarter_range_meta.get("start") or "") <= "202001"

    def build_store():
        store = original_build_store()
        if isinstance(store, dict):
            meta = store.setdefault("quarter_range", {})
            meta["start"] = "202001"
            store["history_start_label"] = "2020년 1분기"
        return store

    fm._quarter_range = quarter_range
    fm._cache_is_fresh = cache_is_fresh
    fm._build_store = build_store
    fm._sbrate_history_patch_installed = True

    print("FISIS management history patch installed: 2020Q1+")
    return True
