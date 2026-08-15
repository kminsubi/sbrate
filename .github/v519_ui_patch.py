from pathlib import Path

INDEX = Path('templates/index.html')
MOBILE = Path('templates/mobile.html')
DASH_CSS = Path('static/css/dashboard.css')
MOBILE_CSS = Path('static/css/v513-mobile-hero-hotfix.css')

# -----------------------------
# PC index.html structural fixes
# -----------------------------
html = INDEX.read_text(encoding='utf-8')

old_h1 = 'class="text-base font-bold text-gray-900 border-l border-gray-300 pl-3"'
new_h1 = 'class="text-base font-bold text-gray-900 border-l border-gray-300 pl-3 whitespace-nowrap shrink-0 leading-none"'
if old_h1 in html:
    html = html.replace(old_h1, new_h1, 1)
elif new_h1 not in html:
    raise SystemExit('PC header h1 marker not found')

old_wrap = '<div class="w-[35%] flex items-center justify-start overflow-visible self-stretch pl-1">'
new_wrap = '<div class="w-[31%] flex items-center justify-start overflow-visible self-stretch pl-1">'
if old_wrap in html:
    html = html.replace(old_wrap, new_wrap, 1)
elif new_wrap not in html:
    raise SystemExit('PC Wibee wrapper marker not found')

old_img = 'class="w-[180px] max-w-none h-[300px] object-contain object-center -translate-x-[25px] translate-y-[2px]"'
new_img = 'class="w-[142px] max-w-none h-auto max-h-[160px] object-contain object-center -translate-x-[12px] translate-y-[4px]"'
if old_img in html:
    html = html.replace(old_img, new_img, 1)
elif new_img not in html:
    raise SystemExit('PC Wibee image marker not found')

old_grid = '<div class="mt-1 grid grid-cols-4 gap-1 w-full text-center">'
new_grid = '<div class="mt-1 grid grid-cols-3 gap-1 w-full text-center">'
if old_grid in html:
    html = html.replace(old_grid, new_grid, 1)
elif new_grid not in html:
    raise SystemExit('Wibee metric grid marker not found')

avg_card = '''            <div class="bg-white/90 border border-blue-100 rounded-md px-1 py-1">
              <div class="text-[8px] text-gray-400 whitespace-nowrap">시장평균</div>
              <div id="wibee-average-rate" class="text-[10px] font-bold text-gray-800 leading-tight">-</div>
            </div>'''
avg_hidden = '''            <div class="hidden bg-white/90 border border-blue-100 rounded-md px-1 py-1" aria-hidden="true">
              <div class="text-[8px] text-gray-400 whitespace-nowrap">시장평균</div>
              <div id="wibee-average-rate" class="text-[10px] font-bold text-gray-800 leading-tight">-</div>
            </div>'''
if avg_card in html:
    html = html.replace(avg_card, avg_hidden, 1)
elif avg_hidden not in html:
    raise SystemExit('Wibee market average card marker not found')

html = html.replace('/static/css/dashboard.css?v=20260815v518', '/static/css/dashboard.css?v=20260815v519', 1)
INDEX.write_text(html.rstrip() + '\n', encoding='utf-8')

# -----------------------------
# PC dashboard.css polish
# -----------------------------
css = DASH_CSS.read_text(encoding='utf-8')
marker = 'SBRate V5.19 PC MOBILE-WIBEE CONSISTENCY'
block = r'''

/* =====================================================
   SBRate V5.19 PC MOBILE-WIBEE CONSISTENCY
   - structural single-line header
   - remove duplicated market-average card from Wibee visual grid
   - mobile-like original Wibee ratio + repeating briefing bubble
===================================================== */

body > header,
body > header > div:first-child{
  flex-wrap:nowrap !important;
}
body > header > div:first-child{
  min-width:0 !important;
  white-space:nowrap !important;
}
body > header h1{
  white-space:nowrap !important;
  word-break:keep-all !important;
  flex:0 0 auto !important;
  min-width:max-content !important;
}

/* Use the same natural-looking Wibee proportions as mobile. */
img[alt="위비 캐릭터"]{
  width:142px !important;
  height:auto !important;
  max-height:160px !important;
  max-width:none !important;
  object-fit:contain !important;
  filter:drop-shadow(0 7px 12px rgba(4,43,107,.16)) !important;
}

div:has(> img[alt="위비 캐릭터"]){
  position:relative !important;
  transform-origin:55% 82% !important;
  animation:sb-v519-pc-idle 5s ease-in-out 1.4s infinite both !important;
}

@keyframes sb-v519-pc-idle{
  0%,100%{transform:translate3d(0,0,0) rotate(0deg)}
  25%{transform:translate3d(0,-1px,0) rotate(-.35deg)}
  50%{transform:translate3d(1px,0,0) rotate(.3deg)}
  75%{transform:translate3d(0,1px,0) rotate(-.15deg)}
}

/* Repeating briefing cue, same world-view as mobile. */
div:has(> img[alt="위비 캐릭터"])::before{
  content:"브리핑을 시작할게요";
  position:absolute;
  left:78px;
  top:8px;
  z-index:4;
  padding:4px 8px;
  border:1px solid rgba(255,255,255,.52);
  border-radius:10px 10px 10px 3px;
  background:rgba(255,255,255,.96);
  box-shadow:0 5px 15px rgba(7,55,131,.12);
  color:#25558f;
  font-size:9px;
  font-weight:800;
  line-height:1.2;
  white-space:nowrap;
  pointer-events:none;
  opacity:0;
  animation:sb-v519-pc-bubble 8s ease-in-out infinite both;
}

@keyframes sb-v519-pc-bubble{
  0%,5%{opacity:0;transform:translate3d(-3px,3px,0) scale(.97)}
  10%,34%{opacity:1;transform:translate3d(0,0,0) scale(1)}
  42%,100%{opacity:0;transform:translate3d(3px,-2px,0) scale(.99)}
}

/* Notebook widths: protect the header title first, then compact tabs/context. */
@media (max-width:1500px){
  body > header{gap:.6rem !important;}
  body > header > div:first-child{gap:.5rem !important;}
  body > header h1{font-size:13px !important;}
  #market-product-tabs{margin-left:.15rem !important;margin-right:235px !important;}
  #market-product-tabs::after{font-size:8.5px !important;padding:4px 7px !important;}
  #market-product-tabs .market-product-tab{padding-left:.6rem !important;padding-right:.6rem !important;}
  body > header > div:last-child{gap:.45rem !important;}
}

@media (max-width:1365px){
  #market-product-tabs{margin-right:205px !important;}
  #market-product-tabs::after{font-size:8px !important;}
  body > header h1{font-size:12.5px !important;}
}

@media (prefers-reduced-motion:reduce){
  div:has(> img[alt="위비 캐릭터"]){animation:none !important;transform:none !important;}
  div:has(> img[alt="위비 캐릭터"])::before{display:none !important;animation:none !important;}
}
'''
if marker not in css:
    css = css.rstrip() + block + '\n'
DASH_CSS.write_text(css.rstrip() + '\n', encoding='utf-8')

# -----------------------------
# Mobile repeating briefing bubble
# -----------------------------
mobile_css = MOBILE_CSS.read_text(encoding='utf-8')
old_selector = '''body:has(#mobile-product-tabs .product-tab.is-active[data-product="deposit"]) .hero-wibee-wrap::before,
body:has(#mobile-product-tabs .product-tab.is-active[data-product="isa"]) .hero-wibee-wrap::before,
body:has(#mobile-product-tabs .product-tab.is-active[data-product="irp"]) .hero-wibee-wrap::before{
  content:"브리핑을 시작할게요";
  animation:sb-v516-bubble 2.9s ease 1 both;
}

@keyframes sb-v516-bubble{
  0%,9%{opacity:0;transform:translate3d(-3px,3px,0) scale(.97)}
  22%,74%{opacity:1;transform:translate3d(0,0,0) scale(1)}
  100%{opacity:0;transform:translate3d(3px,-2px,0) scale(.99)}
}'''
new_selector = '''body:has(#mobile-product-tabs .product-tab.is-active[data-product="deposit"]) .hero-wibee-wrap::before{
  content:"브리핑을 시작할게요";
  animation:sb-v519-mobile-bubble-deposit 8s ease-in-out infinite both;
}
body:has(#mobile-product-tabs .product-tab.is-active[data-product="isa"]) .hero-wibee-wrap::before{
  content:"브리핑을 시작할게요";
  animation:sb-v519-mobile-bubble-isa 8s ease-in-out infinite both;
}
body:has(#mobile-product-tabs .product-tab.is-active[data-product="irp"]) .hero-wibee-wrap::before{
  content:"브리핑을 시작할게요";
  animation:sb-v519-mobile-bubble-irp 8s ease-in-out infinite both;
}

@keyframes sb-v519-mobile-bubble-deposit{
  0%,5%{opacity:0;transform:translate3d(-3px,3px,0) scale(.97)}
  10%,34%{opacity:1;transform:translate3d(0,0,0) scale(1)}
  42%,100%{opacity:0;transform:translate3d(3px,-2px,0) scale(.99)}
}
@keyframes sb-v519-mobile-bubble-isa{
  0%,5%{opacity:0;transform:translate3d(-3px,3px,0) scale(.97)}
  10%,34%{opacity:1;transform:translate3d(0,0,0) scale(1)}
  42%,100%{opacity:0;transform:translate3d(3px,-2px,0) scale(.99)}
}
@keyframes sb-v519-mobile-bubble-irp{
  0%,5%{opacity:0;transform:translate3d(-3px,3px,0) scale(.97)}
  10%,34%{opacity:1;transform:translate3d(0,0,0) scale(1)}
  42%,100%{opacity:0;transform:translate3d(3px,-2px,0) scale(.99)}
}'''
if old_selector in mobile_css:
    mobile_css = mobile_css.replace(old_selector, new_selector, 1)
elif 'sb-v519-mobile-bubble-deposit' not in mobile_css:
    raise SystemExit('Mobile briefing bubble marker not found')
MOBILE_CSS.write_text(mobile_css.rstrip() + '\n', encoding='utf-8')

mobile_html = MOBILE.read_text(encoding='utf-8')
mobile_html = mobile_html.replace('v513-mobile-hero-hotfix.css?v=20260815v517', 'v513-mobile-hero-hotfix.css?v=20260815v519', 1)
MOBILE.write_text(mobile_html.rstrip() + '\n', encoding='utf-8')

print('V5.19 PC/mobile Wibee + header patch applied')
