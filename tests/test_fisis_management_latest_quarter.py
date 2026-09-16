from datetime import datetime
from unittest.mock import patch

import fisis_management as fm


def _store(*quarters):
    return {
        "updated_at": "2026-09-16 09:00:00",
        "quarters": {key: {"banks": [{}]} for key in quarters},
    }


@patch.object(fm, "_now", return_value=datetime(2026, 9, 16, 12, 0, tzinfo=fm.KST))
def test_fresh_cache_without_latest_completed_quarter_requests_refresh(_now):
    assert fm._cache_is_fresh(_store("2026Q1")) is False


@patch.object(fm, "_now", return_value=datetime(2026, 9, 16, 12, 0, tzinfo=fm.KST))
def test_fresh_cache_with_latest_completed_quarter_stays_fresh(_now):
    assert fm._cache_is_fresh(_store("2026Q2", "2026Q1")) is True
