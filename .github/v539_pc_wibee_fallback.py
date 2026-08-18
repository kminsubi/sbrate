from pathlib import Path

html_path = Path('templates/index.html')
css_path = Path('static/css/dashboard.css')

html = html_path.read_text(encoding='utf-8')
old = '<div class="w-[31%] flex items-center justify-start overflow-visible self-stretch pl-1">'
new = '<div class="wibee-pc-stage w-[31%] flex items-center justify-start overflow-visible self-stretch pl-1">'
if old not in html and new not in html:
    raise SystemExit('Wibee wrapper target not found')
html = html.replace(old, new, 1)
html = html.replace('dashboard.css?v=20260815v535', 'dashboard.css?v=20260818v539')
html_path.write_text(html, encoding='utf-8')

css = css_path.read_text(encoding='utf-8').rstrip()
marker = 'SBRate V5.39 PC WIBEE LEGACY FALLBACK'
if marker not in css:
    css += r'''

/* =====================================================
   SBRate V5.39 PC WIBEE LEGACY FALLBACK
   Keep PC Wibee idle motion + repeating speech bubble
   working even when the enterprise browser does not support :has().
===================================================== */

.wibee-pc-stage{
  position:relative !important;
  transform-origin:55% 82% !important;
  animation:sb-v519-pc-idle 5s ease-in-out 1.4s infinite both !important;
  will-change:transform;
}

.wibee-pc-stage::before{
  content:"브리핑을 시작할게요";
  position:absolute;
  left:0 !important;
  top:6px !important;
  z-index:6 !important;
  padding:4px 9px !important;
  border:1px solid rgba(255,255,255,.52);
  border-radius:11px !important;
  background:rgba(255,255,255,.96);
  box-shadow:0 4px 12px rgba(7,55,131,.11) !important;
  color:#25558f;
  font-size:9px;
  font-weight:800;
  line-height:1.2;
  white-space:nowrap;
  pointer-events:none;
  opacity:0;
  transform-origin:center bottom !important;
  animation:sb-v524-pc-bubble 7.2s cubic-bezier(.22,.72,.2,1) infinite both !important;
  will-change:transform,opacity !important;
}

@media(max-width:1500px){
  .wibee-pc-stage::before{
    left:-2px !important;
    top:7px !important;
    font-size:8.5px !important;
    padding:4px 7px !important;
  }
}

@media(prefers-reduced-motion:reduce){
  .wibee-pc-stage{
    animation:none !important;
    transform:none !important;
  }
  .wibee-pc-stage::before{
    display:none !important;
    animation:none !important;
  }
}
'''

css_path.write_text(css.rstrip() + '\n', encoding='utf-8')
