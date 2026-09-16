from pathlib import Path


INDEX = Path(__file__).resolve().parents[1] / "templates" / "index.html"


def test_ai_market_panel_does_not_create_dashboard_scrollbars():
    text = INDEX.read_text(encoding="utf-8")
    marker = "#ai-center-content.ai-market-compact{"
    start = text.index(marker)
    block = text[start:text.index("}", start) + 1]
    assert "overflow:hidden !important" in block
