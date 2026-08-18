from pathlib import Path

html_path = Path('templates/index.html')
css_path = Path('static/css/dashboard.css')

html = html_path.read_text(encoding='utf-8')
old = '''        <div class="wibee-pc-stage w-[31%] flex items-center justify-start overflow-visible self-stretch pl-1">
          <img
            src="/static/images/wibee.png?v=20260815v513"
            alt="위비 캐릭터"
            class="w-[142px] max-w-none h-auto max-h-[160px] object-contain object-center -translate-x-[12px] translate-y-[4px]"
          />
        </div>'''
new = '''        <div class="wibee-pc-stage w-[31%] flex items-center justify-start overflow-visible self-stretch pl-1">
          <span class="wibee-pc-motion" aria-hidden="true">
            <img
              src="/static/images/wibee.png?v=20260815v513"
              alt="위비 캐릭터"
              class="w-[142px] max-w-none h-auto max-h-[160px] object-contain object-center -translate-x-[12px] translate-y-[4px]"
            />
          </span>
        </div>'''
if old not in html:
    raise SystemExit('target Wibee block not found')
html = html.replace(old, new, 1)
html = html.replace('/static/css/dashboard.css?v=20260818v541', '/static/css/dashboard.css?v=20260818v542', 1)
html_path.write_text(html.rstrip() + '\n', encoding='utf-8')

css = css_path.read_text(encoding='utf-8').rstrip()
append = r'''

/* =====================================================
   SBRate V5.42 PC WIBEE MOTION WRAPPER
   Move the image through a dedicated <span> so enterprise
   reduced-motion rules targeting div/img transforms cannot pin it.
===================================================== */

.wibee-pc-stage{
  animation:none !important;
  transform:none !important;
}

.wibee-pc-motion{
  display:flex !important;
  align-items:center !important;
  justify-content:flex-start !important;
  width:100% !important;
  height:100% !important;
  transform-origin:55% 82% !important;
  animation:sb-v542-pc-wibee-idle 4.8s ease-in-out 1.1s infinite both !important;
  will-change:transform !important;
}

@keyframes sb-v542-pc-wibee-idle{
  0%,100%{transform:translate3d(0,0,0) rotate(-.18deg)}
  25%{transform:translate3d(0,-2px,0) rotate(-.42deg)}
  50%{transform:translate3d(2px,-4px,0) rotate(.42deg)}
  75%{transform:translate3d(1px,-1px,0) rotate(-.16deg)}
}

@media(prefers-reduced-motion:reduce){
  .wibee-pc-motion{
    animation:sb-v542-pc-wibee-idle 4.8s ease-in-out 1.1s infinite both !important;
  }
}
'''
if 'SBRate V5.42 PC WIBEE MOTION WRAPPER' not in css:
    css += append
css_path.write_text(css.rstrip() + '\n', encoding='utf-8')
