from pathlib import Path

css_path = Path('static/css/dashboard.css')
html_path = Path('templates/index.html')

css = css_path.read_text(encoding='utf-8').rstrip()
marker = 'SBRate V5.23 PC WIBEE BUBBLE FINE TUNE'

block = r'''

/* =====================================================
   SBRate V5.23 PC WIBEE BUBBLE FINE TUNE
   - move bubble one visual step right
   - move bubble two visual steps down
   - keep Wibee position unchanged
===================================================== */

div:has(> img[alt="위비 캐릭터"])::before{
  left:-4px !important;
  top:2px !important;
}

@media (max-width:1500px){
  div:has(> img[alt="위비 캐릭터"])::before{
    left:-6px !important;
    top:3px !important;
  }
}
'''

if marker not in css:
    css += block
css_path.write_text(css.rstrip() + '\n', encoding='utf-8')

html = html_path.read_text(encoding='utf-8')
html = html.replace('/static/css/dashboard.css?v=20260815v522', '/static/css/dashboard.css?v=20260815v523', 1)
html_path.write_text(html, encoding='utf-8')

print('V5.23 bubble fine tune applied')
