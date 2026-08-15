from pathlib import Path

css_path=Path('static/css/dashboard.css')
html_path=Path('templates/index.html')

css=css_path.read_text(encoding='utf-8')
marker='SBRate V5.18 PC HEADER + WIBEE HOTFIX'

block='''

/* =====================================================
   SBRate V5.18 PC HEADER + WIBEE HOTFIX
   - keep dashboard header title on one line
   - slightly reduce PC Wibee size
   - retain one-shot briefing intro and add calm continuous idle motion
===================================================== */

body > header h1{
  white-space:nowrap !important;
  flex-shrink:0 !important;
  min-width:max-content !important;
  line-height:1.2 !important;
}

img[alt="위비 캐릭터"]{
  width:156px !important;
  height:250px !important;
  max-width:none !important;
}

div:has(> img[alt="위비 캐릭터"]){
  transform-origin:55% 82% !important;
  animation:sb-v518-pc-wibee-idle 5.2s ease-in-out 1.45s infinite both !important;
  will-change:transform;
}

@keyframes sb-v518-pc-wibee-idle{
  0%,100%{transform:translate3d(0,0,0) rotate(0deg)}
  25%{transform:translate3d(0,-1px,0) rotate(-.35deg)}
  50%{transform:translate3d(1px,0,0) rotate(.3deg)}
  75%{transform:translate3d(0,1px,0) rotate(-.15deg)}
}

@media (max-width:1500px){
  body > header h1{font-size:14px !important;}
  #market-product-tabs{margin-left:.25rem !important;}
}

@media (prefers-reduced-motion:reduce){
  div:has(> img[alt="위비 캐릭터"]){
    animation:none !important;
    transform:none !important;
  }
}
'''

if marker not in css:
    css=css.rstrip()+block+'\n'
    css_path.write_text(css,encoding='utf-8')

html=html_path.read_text(encoding='utf-8')
old='/static/css/dashboard.css?v=20260815v513'
new='/static/css/dashboard.css?v=20260815v518'
if old in html:
    html=html.replace(old,new,1)
elif new not in html:
    raise SystemExit('dashboard.css cache-bust marker not found')
html_path.write_text(html,encoding='utf-8')

print('V5.18 PC header/Wibee hotfix applied')
