from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
LOADER = ROOT / "static" / "css" / "dashboard.css"
LEGACY = ROOT / "static" / "css" / "dashboard_legacy.css"
EXECUTIVE = ROOT / "static" / "css" / "executive_ui_v6.css"


class ExecutiveUiV6ContractTests(unittest.TestCase):
    def test_dashboard_loader_imports_legacy_then_executive_ui(self):
        text = LOADER.read_text(encoding="utf-8")
        legacy = '@import url("/static/css/dashboard_legacy.css?v=20260915v1");'
        executive = '@import url("/static/css/executive_ui_v6.css?v=20260915v1");'
        self.assertIn(legacy, text)
        self.assertIn(executive, text)
        self.assertLess(text.index(legacy), text.index(executive))

    def test_legacy_dashboard_css_is_preserved(self):
        text = LEGACY.read_text(encoding="utf-8")
        self.assertIn("SBRateBot V5 Executive Dashboard", text)
        self.assertIn("--woori:#0066b3", text.replace(" ", ""))

    def test_executive_ui_targets_existing_dashboard_contract(self):
        text = EXECUTIVE.read_text(encoding="utf-8")
        required = (
            "#dashboard-hero-start",
            "#kpi-rank",
            "#executive-summary-mini",
            "#wibee-market-status",
            "#market-ranking-row",
            "#ai-analysis-center",
            "#product-search-panel",
            "@media (max-width: 1500px)",
        )
        for selector in required:
            self.assertIn(selector, text)

    def test_executive_ui_does_not_hide_or_reorder_live_sections(self):
        text = EXECUTIVE.read_text(encoding="utf-8").lower()
        self.assertIsNone(re.search(r"display\s*:\s*none", text))
        self.assertIsNone(re.search(r"(?:^|[;{])\s*order\s*:", text))
        self.assertIsNone(re.search(r"position\s*:\s*fixed", text))


if __name__ == "__main__":
    unittest.main()
