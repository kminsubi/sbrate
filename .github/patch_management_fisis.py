from pathlib import Path


def replace_once(path, old, new):
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"pattern not found in {path}: {old[:80]!r}")
    text = text.replace(old, new, 1)
    p.write_text(text.rstrip() + "\n", encoding="utf-8")


report = Path("management_report.py")
text = report.read_text(encoding="utf-8")
old_loader = '''def _load_store():
    try:
        with DATA_FILE.open("r", encoding="utf-8-sig") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}
'''
new_loader = '''def _load_store():
    try:
        from fisis_management import get_management_store
        data = get_management_store(trigger_refresh=True)
        return data if isinstance(data, dict) else {}
    except Exception as error:
        print("Management report FISIS store error:", error)
        return {}
'''
if old_loader not in text:
    raise RuntimeError("management_report.py loader block not found")
text = text.replace(old_loader, new_loader, 1)
text = text.replace("저축은행중앙회 금융통계자료", "금융감독원 금융통계정보시스템(FISIS)")
text = text.replace("/static/css/management_report.css?v=20260825v1", "/static/css/management_report.css?v=20260825v2")
text = text.replace("/static/js/management_report.js?v=20260825v1", "/static/js/management_report.js?v=20260825v2")
report.write_text(text.rstrip() + "\n", encoding="utf-8")

js = Path("static/js/management_report.js")
text = js.read_text(encoding="utf-8")
text = text.replace("저축은행중앙회 금융통계자료 기준", "금융감독원 금융통계정보시스템(FISIS) 기준")
text = text.replace("중앙회 분기 데이터를 확인하고 있습니다.", "FISIS 분기 데이터를 확인하고 있습니다.")
needle = '<span>※ 연체율·고정이하여신비율은 하락이 개선</span>'
replacement = '<span>※ 연체율·고정이하여신비율은 하락이 개선 · 당기순이익은 공시 누적값</span>'
text = text.replace(needle, replacement)
js.write_text(text.rstrip() + "\n", encoding="utf-8")

scheduler = Path("scheduler.py")
text = scheduler.read_text(encoding="utf-8")
text = text.replace("from fisis_probe_runtime import install_fisis_probe\n", "from fisis_management import install_fisis_management\n")
text = text.replace("install_fisis_probe()\n", "install_fisis_management()\n")
scheduler.write_text(text.rstrip() + "\n", encoding="utf-8")
