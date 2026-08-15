from pathlib import Path

html_path=Path('templates/index.html')
js_path=Path('static/js/dashboard.js')

html=html_path.read_text(encoding='utf-8')
old='''  #ai-center-content.ai-market-compact{\n    overflow:hidden !important;\n  }'''
new='''  #ai-center-content.ai-market-compact{\n    overflow-y:auto !important;\n    overflow-x:hidden !important;\n  }'''
if old not in html:
    raise SystemExit('market compact overflow rule not found')
html=html.replace(old,new,1)
html_path.write_text(html,encoding='utf-8')

js=js_path.read_text(encoding='utf-8')
old_js='target.style.overflowY = tab === "market" ? "hidden" : "auto";'
new_js='target.style.overflowY = "auto";'
if old_js not in js:
    raise SystemExit('AI center overflow JS rule not found')
js=js.replace(old_js,new_js,1)
js_path.write_text(js,encoding='utf-8')
print('AI center overflow consistency fixed')
