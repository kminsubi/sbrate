from pathlib import Path

css_path=Path('static/css/dashboard.css')
html_path=Path('templates/index.html')

css=css_path.read_text(encoding='utf-8')
marker='SBRate V5.21 PC WIBEE POSITION TUNE'
block='''

/* =====================================================
   SBRate V5.21 PC WIBEE POSITION TUNE
   - lower Wibee slightly without fighting transform animation
   - move speech bubble clearly further left and upward
===================================================== */

img[alt="위비 캐릭터"]{
  position:relative !important;
  top:8px !important;
}

div:has(> img[alt="위비 캐릭터"])::before{
  left:4px !important;
  top:-6px !important;
  z-index:6 !important;
}

@media (max-width:1500px){
  img[alt="위비 캐릭터"]{
    top:8px !important;
  }
  div:has(> img[alt="위비 캐릭터"])::before{
    left:2px !important;
    top:-5px !important;
  }
}
'''

if marker not in css:
    css=css.rstrip()+block
css_path.write_text(css.rstrip()+'\n',encoding='utf-8')

html=html_path.read_text(encoding='utf-8')
for old in (
    '/static/css/dashboard.css?v=20260815v520',
    '/static/css/dashboard.css?v=20260815v519',
    '/static/css/dashboard.css?v=20260815v518',
):
    if old in html:
        html=html.replace(old,'/static/css/dashboard.css?v=20260815v521',1)
        break
if '/static/css/dashboard.css?v=20260815v521' not in html:
    raise SystemExit('dashboard css cache marker not found')
html_path.write_text(html,encoding='utf-8')

print('V5.21 PC Wibee position tuned')
