from pathlib import Path

js_path = Path('static/js/mobile.js')
html_path = Path('templates/mobile.html')

js = js_path.read_text(encoding='utf-8')
html = html_path.read_text(encoding='utf-8')

old = '? `${MobileState.period}개월`\n                    : disclosure('
new = '? `${MobileState.productPeriod || MobileState.period}개월`\n                    : disclosure('
if old not in js:
    raise SystemExit('mobile product row period label target not found')
js = js.replace(old, new, 1)

html = html.replace('/static/js/mobile.js?v=20260815v529', '/static/js/mobile.js?v=20260815v530', 1)

js_path.write_text(js.rstrip() + '\n', encoding='utf-8')
html_path.write_text(html, encoding='utf-8')

print('V5.30 mobile product period label fixed')
