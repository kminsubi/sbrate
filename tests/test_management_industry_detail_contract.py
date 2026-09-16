from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "static" / "js" / "management_executive_matrix.js"
CSS = ROOT / "static" / "css" / "management_executive_matrix.css"


class ManagementIndustryDetailContractTests(unittest.TestCase):
    def test_detail_button_returns_to_existing_industry_panel(self):
        text = JS.read_text(encoding="utf-8")
        self.assertIn("panel.querySelector('#mx-detail').addEventListener('click', closePanel)", text)
        self.assertNotIn('id="mx-industry-detail"', text)
        self.assertNotIn('id="mx-industry-table-toggle"', text)

    def test_existing_matrix_layout_is_restored_without_touching_v6_panels(self):
        text = CSS.read_text(encoding="utf-8")
        self.assertRegex(text, r"#mx-detail\s*\{\s*display\s*:\s*none")
        self.assertNotIn(".mx-industry-detail", text)
        self.assertNotIn(".mx-industry-table", text)


if __name__ == "__main__":
    unittest.main()
