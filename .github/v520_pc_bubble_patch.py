from pathlib import Path

css_path=Path('static/css/dashboard.css')
html_path=Path('templates/index.html')

css=css_path.read_text(encoding='utf-8')
marker='SBRate V5.20 PC WIBEE BUBBLE ABOVE HEAD'
block='''

/* =====================================================
   SBRate V5.20 PC WIBEE BUBBLE ABOVE HEAD
   Keep the speech cue entirely inside the Wibee visual area
   so it never covers briefing text or metrics.
===================================================== */

div:has(> img[alt="위비 캐릭터"])::before{
  left:18px !important;
  top:1px !important;
  transform-origin:center bottom !important;
  border-radius:11px !important;
  padding:4px 9px !important;
  box-shadow:0 4px 12px rgba(7,55,131,.11) !important;
}

@keyframes sb-v519-pc-bubble{
  0%,5%{opacity:0;transform:translate3d(0,4px,0) scale(.97)}
  10%,34%{opacity:1;transform:translate3d(0,0,0) scale(1)}
  42%,100%{opacity:0;transform:translate3d(0,-3px,0) scale(.99)}
}

@media (max-width:1500px){
  div:has(> img[alt="위비 캐릭터"])::before{
    left:14px !important;
    top:2px !important;
    font-size:8.5px !important;
    padding:4px 7px !important;
  }
}
'''

if marker not in css:
    css=css.rstrip()+block
    css_path.write_text(css,encoding='utf-8')

html=html_path.read_text(encoding='utf-8')
for old in (
    '/static/css/dashboard.css?v=20260815v519',
    '/static/css/dashboard.css?v=20260815v518',
):
    if old in html:
        html=html.replace(old,'/static/css/dashboard.css?v=20260815v520',1)
        break
else:
    if '/static/css/dashboard.css?v=20260815v520' not in html:
        raise SystemExit('dashboard css cache marker not found')
html_path.write_text(html,encoding='utf-8')
print('V5.20 PC bubble moved above Wibee head')
