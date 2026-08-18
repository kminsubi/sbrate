from pathlib import Path

css_path = Path('static/css/dashboard.css')
html_path = Path('templates/index.html')

css = css_path.read_text(encoding='utf-8').rstrip()
marker = 'SBRate V5.40 PC WIBEE FORCE MOTION'
block = r'''

/* =====================================================
   SBRate V5.40 PC WIBEE FORCE MOTION
   Keep only the PC Wibee idle motion + repeating bubble active
   even when the enterprise OS/browser requests reduced motion.
   Mobile and all other motion continue to respect system settings.
===================================================== */

.wibee-pc-stage{
  animation:sb-v519-pc-idle 5s ease-in-out 1.4s infinite both !important;
  transform-origin:55% 82% !important;
  will-change:transform !important;
}

.wibee-pc-stage::before{
  display:block !important;
  animation:sb-v524-pc-bubble 7.2s cubic-bezier(.22,.72,.2,1) infinite both !important;
  will-change:transform,opacity !important;
}

@media(prefers-reduced-motion:reduce){
  .wibee-pc-stage{
    animation:sb-v519-pc-idle 5s ease-in-out 1.4s infinite both !important;
    transform-origin:55% 82% !important;
  }

  .wibee-pc-stage::before{
    display:block !important;
    animation:sb-v524-pc-bubble 7.2s cubic-bezier(.22,.72,.2,1) infinite both !important;
  }
}
'''

if marker not in css:
    css += block
css_path.write_text(css.rstrip() + '\n', encoding='utf-8')

html = html_path.read_text(encoding='utf-8')
old = '/static/css/dashboard.css?v=20260818v539'
new = '/static/css/dashboard.css?v=20260818v540'
if old in html:
    html = html.replace(old, new, 1)
elif new not in html:
    raise SystemExit('dashboard.css cache token not found')
html_path.write_text(html, encoding='utf-8')
