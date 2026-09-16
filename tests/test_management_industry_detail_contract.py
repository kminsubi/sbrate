from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PEER_JS = ROOT / "static" / "js" / "management_peer_compare.js"
RUNTIME = ROOT / "management_report_v5_runtime.py"
TERMINOLOGY = ROOT / "static" / "js" / "management_terminology_patch.js"


class ManagementIndustryDetailContractTests(unittest.TestCase):
    def test_management_entry_opens_the_single_existing_four_peer_tab(self):
        text = PEER_JS.read_text(encoding="utf-8")
        self.assertIn("#management-report-open,#management-report-open-mobile", text)
        self.assertIn("[160, 500, 1100].forEach", text)
        self.assertIn("if (!modal || modal.hidden) return;", text)
        self.assertIn("ensureUI();\n            activatePeer();", text)

    def test_legacy_full_screen_matrix_is_not_injected_alongside_peer_tab(self):
        text = RUNTIME.read_text(encoding="utf-8")
        self.assertNotIn('src="/static/js/management_executive_matrix.js', text)
        self.assertNotIn('href="/static/css/management_executive_matrix.css', text)

    def test_shared_entry_is_named_management(self):
        text = TERMINOLOGY.read_text(encoding="utf-8")
        self.assertIn("'ð ê²½ìê´ë¦¬'", text)


if __name__ == "__main__":
    unittest.main()
