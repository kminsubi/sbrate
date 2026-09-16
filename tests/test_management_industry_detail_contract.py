from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "static" / "js" / "management_executive_matrix.js"
CSS = ROOT / "static" / "css" / "management_executive_matrix.css"


class ManagementIndustryDetailContractTests(unittest.TestCase):
    def test_full_industry_detail_is_nested_and_table_is_user_revealed(self):
        text = JS.read_text(encoding="utf-8")
        self.assertIn('id="mx-industry-detail"', text)
        self.assertIn('id="mx-industry-table-toggle"', text)
        self.assertIn('id="mx-industry-table-section"', text)
        self.assertRegex(text, r"#mx-detail'\)\.addEventListener\('click',\s*openIndustryDetail\)")
        self.assertIn("section.hidden = !section.hidden", text)
        self.assertNotIn("panel.querySelector('#mx-detail').addEventListener('click', closePanel)", text)

    def test_mobile_keeps_full_industry_button_and_uses_scrollable_table(self):
        text = CSS.read_text(encoding="utf-8")
        self.assertNotRegex(text, r"#mx-detail\s*\{\s*display\s*:\s*none")
        self.assertIn(".mx-industry-table-wrap", text)
        self.assertIn("-webkit-overflow-scrolling: touch", text)
        self.assertIn(".mx-industry-table", text)
        self.assertIn("min-width: 820px", text)
        self.assertIn(".mx-industry-summary", text)

    def test_industry_snapshot_uses_executive_columns_and_woori_highlight(self):
        text = JS.read_text(encoding="utf-8")
        for label in ("순위", "저축은행", "총자산", "총여신", "BIS", "연체율", "NPL", "당기순이익"):
            self.assertIn(label, text)
        self.assertIn("mx-industry-woori", text)
        self.assertIn("우리금융", text)


if __name__ == "__main__":
    unittest.main()
