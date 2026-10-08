"""Regression tests for quiet-but-honest second-pass Telegram notifications."""
import importlib.util
import unittest
from datetime import date, timedelta
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "retry", Path(__file__).resolve().parents[1] / "data_quality_retry_notify.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class RetryNotifyTests(unittest.TestCase):
    def setUp(self):
        self.today = date(2026, 10, 8)
        self.kb = {
            "bank": "KB", "rates": {"12m": 3.5},
            "collected_at": "2026-10-02 05:27:02",
            "last_attempt_at": "2026-10-08 10:13:55",
        }
        self.nh = {
            "bank": "NH", "rates": {"12m": 3.7},
            "disclosure_date": "2026-09-28",
            "collected_at": "2026-10-08 05:44:54",
        }
        self.issues = [
            {"level": "WARNING", "key": "isa:retained:kb", "section": "ISA", "message": "KB stale"},
            {"level": "WARNING", "key": "irp:disclosure_not_refreshed:nh", "section": "IRP", "message": "NH stale"},
        ]
        self.source = {
            "issues": self.issues,
            "counts": {"isa": {"verified_today": 9}},
            "generated_at": "2026-10-08 10:14:10",
        }

    def test_today_case_suppressed_but_validation_retained(self):
        payload, state, remaining = mod.build_alert(self.source, {}, [self.kb], [self.nh], self.today)
        self.assertEqual((payload["notify"], payload["status"], remaining), (False, "WARNING", 2))
        self.assertEqual(payload["counts"], self.source["counts"])
        self.assertEqual(len(state["active"]), 2)

    def test_stale_after_seven_days_and_weekly_throttle(self):
        current = self.today + timedelta(days=1)
        state = {"active": {"isa:retained:kb": {"first_seen": self.today.isoformat()}}}
        payload, updated, _ = mod.build_alert(self.source, state, [self.kb], [self.nh], current)
        self.assertEqual([x["key"] for x in payload["issues"]], ["isa:retained:kb"])
        updated["active"]["isa:retained:kb"]["last_notified"] = current.isoformat()
        payload, _, _ = mod.build_alert(self.source, updated, [self.kb], [self.nh], current + timedelta(days=1))
        self.assertFalse(payload["notify"])
        payload, _, _ = mod.build_alert(self.source, updated, [self.kb], [self.nh], current + timedelta(days=7))
        self.assertTrue(payload["notify"])

    def test_disclosure_escalates_by_first_seen_not_effective_date(self):
        prev = {"active": {"irp:disclosure_not_refreshed:nh": {"first_seen": self.today.isoformat()}}}
        payload, _, _ = mod.build_alert(self.source, prev, [self.kb], [self.nh], self.today + timedelta(days=7))
        self.assertIn("irp:disclosure_not_refreshed:nh", [x["key"] for x in payload["issues"]])

    def test_no_rate_is_immediately_actionable(self):
        row = dict(self.kb, rates={"12m": None})
        payload, _, _ = mod.build_alert(self.source, {}, [row], [self.nh], self.today)
        self.assertEqual([x["key"] for x in payload["issues"]], ["isa:retained:kb"])

    def test_missing_rate_bypasses_recent_warning_cooldown(self):
        old = {"active": {"isa:retained:kb": {"first_seen": "2026-10-02", "last_notified": "2026-10-08"}}}
        kb = dict(self.kb, rates={"12m": None})
        payload, _, _ = mod.build_alert(self.source, old, [kb], [self.nh], self.today)
        self.assertEqual([x["key"] for x in payload["issues"]], ["isa:retained:kb"])

    def test_errors_bypass_throttle(self):
        issue = {"level": "ERROR", "key": "irp:collector_failed", "message": "fail"}
        source = {"issues": [issue], "generated_at": self.source["generated_at"]}
        state = {"active": {"irp:collector_failed": {"first_seen": "2026-10-01", "last_notified": "2026-10-08"}}}
        payload, _, _ = mod.build_alert(source, state, [], [], self.today)
        self.assertEqual((payload["notify"], payload["status"]), (True, "BLOCKED"))

    def test_resolution_clears_active_and_reappearance_resets(self):
        old = {"active": {"isa:retained:kb": {"first_seen": "2026-09-01", "last_notified": "2026-10-08"}}}
        _, cleared, _ = mod.build_alert(
            {"issues": [], "generated_at": self.source["generated_at"]}, old, [], [], self.today
        )
        self.assertEqual(cleared["active"], {})
        _, recreated, _ = mod.build_alert(self.source, cleared, [self.kb], [self.nh], self.today)
        self.assertEqual(recreated["active"]["isa:retained:kb"]["first_seen"], "2026-10-08")

    def test_only_second_pass_issues_considered(self):
        source = {
            "issues": self.issues + [{"level": "WARNING", "key": "isa:unavailable_rows"}],
            "generated_at": self.source["generated_at"],
        }
        _, _, remaining = mod.build_alert(source, {}, [self.kb], [self.nh], self.today)
        self.assertEqual(remaining, 2)

    def test_missing_rate_is_urgent(self):
        source = {
            "issues": [{"level": "WARNING", "key": "isa:fetch_failed_no_value:kb"}],
            "generated_at": self.source["generated_at"],
        }
        payload, _, _ = mod.build_alert(source, {}, [], [], self.today)
        self.assertTrue(payload["notify"])

    def test_invalid_status_raises(self):
        with self.assertRaises(ValueError):
            mod.build_alert({}, {}, [], [], self.today)


if __name__ == "__main__":
    unittest.main()
