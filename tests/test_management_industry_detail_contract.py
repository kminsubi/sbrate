from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PEER_JS = ROOT / "static" / "js" / "management_peer_compare.js"
PEER_CSS = ROOT / "static" / "css" / "management_peer_compare.css"
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
        self.assertIn("'📑 경영관리'", text)

    def test_peer_view_hides_legacy_summary_and_only_keeps_horizontal_table_pan(self):
        text = PEER_CSS.read_text(encoding="utf-8")
        self.assertIn(".mp-peer-active #ids-overview-strip", text)
        self.assertIn(".mp-peer-active #mr-summary-heading", text)
        self.assertIn(".mp-table-wrap{width:100%;overflow-x:auto;overflow-y:hidden", text)
        self.assertIn(".mp-table-wrap::-webkit-scrollbar{height:0;width:0}", text)


if __name__ == "__main__":
    unittest.main()
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
