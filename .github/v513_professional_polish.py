from pathlib import Path


def read(path):
    return Path(path).read_text(encoding="utf-8")


def write(path, text):
    Path(path).write_text(text, encoding="utf-8")


def replace_required(path, old, new, count=None):
    text = read(path)
    hits = text.count(old)
    if hits == 0:
        raise SystemExit(f"required text not found in {path}: {old[:100]!r}")
    if count is not None and hits != count:
        raise SystemExit(
            f"unexpected match count in {path}: {hits} != {count} for {old[:100]!r}"
        )
    write(path, text.replace(old, new))
    print(f"patched {path}: {hits} replacement(s)")


# -------------------------------------------------
# PC HTML: original Wibee + AI report naming/basis.
# -------------------------------------------------
replace_required(
    "templates/index.html",
    "/static/images/wibee_v512.png?v=20260815",
    "/static/images/wibee.png?v=20260815v513",
    1,
)
replace_required(
    "templates/index.html",
    "/static/css/dashboard.css?v=20260815",
    "/static/css/dashboard.css?v=20260815v513",
    1,
)
replace_required(
    "templates/index.html",
    "/static/js/dashboard.js?v=20260815",
    "/static/js/dashboard.js?v=20260815v513",
    1,
)
replace_required(
    "templates/index.html",
    ">📊 AI 시장분석</button>",
    ">📊 AI 보고서</button>",
    1,
)
replace_required(
    "templates/index.html",
    "📊 AI 시장분석 보고서",
    "📊 AI 보고서",
    1,
)
replace_required(
    "templates/index.html",
    "데이터 기준 -",
    "데이터 업데이트 기준 -",
    1,
)
replace_required(
    "templates/index.html",
    "AI 시장분석 보고서를 준비하고 있습니다.",
    "AI 보고서를 준비하고 있습니다.",
    1,
)


# -------------------------------------------------
# Mobile HTML: same original Wibee + fresh assets.
# -------------------------------------------------
replace_required(
    "templates/mobile.html",
    "/static/images/wibee_v512.png?v=20260815",
    "/static/images/wibee.png?v=20260815v513",
    1,
)
replace_required(
    "templates/mobile.html",
    "/static/css/mobile.css?v=20260815",
    "/static/css/mobile.css?v=20260815v513",
    1,
)
replace_required(
    "templates/mobile.html",
    "/static/css/v512-mobile.css?v=20260815",
    "/static/css/v512-mobile.css?v=20260815v513",
    1,
)
replace_required(
    "templates/mobile.html",
    "/static/js/mobile.js?v=20260815",
    "/static/js/mobile.js?v=20260815v513",
    1,
)


# -------------------------------------------------
# PC JS: report naming/basis only. Preserve IDs/APIs.
# -------------------------------------------------
js = read("static/js/dashboard.js")
js = js.replace(
    "`데이터 업데이트 시간 ${formatDataBasis(value)}`",
    "`데이터 업데이트 기준 ${formatDataBasis(value)}`",
)
js = js.replace(
    "`데이터 업데이트 시간 ${dataBasis}`",
    "`데이터 업데이트 기준 ${dataBasis}`",
)
js = js.replace(
    "`데이터 업데이트 시간 ${dataBasis}. ${marketProductLabel()} ${currentSelectedPeriod()}개월 AI 시장분석 보고서의 AI Management Insight를 작성해줘.",
    "`데이터 업데이트 기준 ${dataBasis}. ${marketProductLabel()} ${currentSelectedPeriod()}개월 AI 보고서의 AI Management Insight를 작성해줘.",
)
write("static/js/dashboard.js", js)


# -------------------------------------------------
# Mobile JS: report naming/basis + source vocabulary.
# -------------------------------------------------
mjs = read("static/js/mobile.js")
mjs = mjs.replace(
    "각 저축은행 공식 공시·상품 페이지",
    "각 저축은행 홈페이지",
)
mjs = mjs.replace(
    "`${currentLabel()} AI 시장분석 보고서`",
    "`AI 보고서`",
)
mjs = mjs.replace(
    "`데이터 업데이트 시간 ${mobileDataBasis()}`",
    "`데이터 업데이트 기준 ${mobileDataBasis()}`",
)
mjs = mjs.replace(
    "`데이터 업데이트 시간 ${mobileDataBasis()}. ${currentLabel()} ${MobileState.period}개월 AI 시장분석 보고서의 AI Management Insight를 작성해줘.",
    "`데이터 업데이트 기준 ${mobileDataBasis()}. ${currentLabel()} ${MobileState.period}개월 AI 보고서의 AI Management Insight를 작성해줘.",
)
write("static/js/mobile.js", mjs)


# -------------------------------------------------
# Telegram: short single-line divider in every section.
# -------------------------------------------------
app = read("app.py")
app = app.replace('"━━━━━━━━━━━━"', '"────────────"')

old = '    lines.extend(["", "🔥 주요 변동"])'
new = '    lines.extend(["", "────────────", "🔥 주요 변동", "────────────"])'
if old not in app:
    raise SystemExit("Morning Brief movement section marker not found")
app = app.replace(old, new, 1)

old = '    lines.extend(["", *pension_lines("ISA", isa), "", *pension_lines("퇴직연금(IRP)", irp)])'
new = '''    lines.extend([
        "",
        "────────────",
        *pension_lines("ISA", isa),
        "────────────",
        "",
        "────────────",
        *pension_lines("퇴직연금(IRP)", irp),
        "────────────",
    ])'''
if old not in app:
    raise SystemExit("Morning Brief pension section marker not found")
app = app.replace(old, new, 1)
write("app.py", app)


# -------------------------------------------------
# PC CSS: final authoritative structural/polish layer.
# -------------------------------------------------
css_path = Path("static/css/dashboard.css")
css = css_path.read_text(encoding="utf-8")
marker = "SBRate V5.13 PROFESSIONAL CONSISTENCY"
if marker not in css:
    css += r'''

/* =====================================================
   SBRate V5.13 PROFESSIONAL CONSISTENCY
   - structural AI-panel stretch (no fixed px matching)
   - exact source vocabulary
   - original Wibee, one-shot briefing micro-motion
===================================================== */

#market-product-tabs:has(button[data-market-product="deposit"][class*="text-white"])::after{
  content:"정기예금 12개월 시장현황  ·  [출처 : 저축은행중앙회 비교공시]" !important;
}
#market-product-tabs:has(button[data-market-product="isa"][class*="text-white"])::after{
  content:"ISA 12개월 시장현황  ·  [출처 : 각 저축은행 홈페이지]" !important;
}
#market-product-tabs:has(button[data-market-product="irp"][class*="text-white"])::after{
  content:"퇴직연금(IRP) 12개월 시장현황  ·  [출처 : 각 저축은행 홈페이지]" !important;
}

/* Grid row owns the height. AI content scrolls inside rather than expanding the row. */
#ai-analysis-center{
  align-self:stretch !important;
  height:100% !important;
  min-height:0 !important;
  max-height:none !important;
  overflow:hidden !important;
  contain:none !important;
}
#ai-center-content{
  flex:1 1 auto !important;
  min-height:0 !important;
  overflow-y:auto !important;
  overflow-x:hidden !important;
  overscroll-behavior:contain;
  scrollbar-gutter:stable;
}

/* Major-card geometry is consistent without redesigning the current layout. */
#dashboard-hero-start > .col-span-4 > .bg-white,
#market-ranking-row > .bg-white,
#ai-analysis-center,
#product-search-panel{
  border-radius:16px !important;
  border-color:#e4ebf4 !important;
  box-shadow:0 6px 20px rgba(15,23,42,.035) !important;
}

/* Original Wibee: brief once on entry/product change, never float endlessly. */
img[alt="위비 캐릭터"]{
  filter:drop-shadow(0 9px 15px rgba(4,43,107,.15)) !important;
  transform-origin:center bottom !important;
  will-change:transform,opacity;
}
body:has(#market-product-tabs button[data-market-product="deposit"][class*="text-white"]) img[alt="위비 캐릭터"]{
  animation:sb-wibee-brief-deposit 1.35s cubic-bezier(.22,.72,.2,1) 1 both !important;
}
body:has(#market-product-tabs button[data-market-product="isa"][class*="text-white"]) img[alt="위비 캐릭터"]{
  animation:sb-wibee-brief-isa 1.35s cubic-bezier(.22,.72,.2,1) 1 both !important;
}
body:has(#market-product-tabs button[data-market-product="irp"][class*="text-white"]) img[alt="위비 캐릭터"]{
  animation:sb-wibee-brief-irp 1.35s cubic-bezier(.22,.72,.2,1) 1 both !important;
}
@keyframes sb-wibee-brief-deposit{
  0%{opacity:0;transform:translate3d(-25px,5px,0) rotate(-.5deg) scale(.985)}
  38%{opacity:1;transform:translate3d(-25px,2px,0) rotate(-.9deg) scale(1)}
  68%{transform:translate3d(-25px,2px,0) rotate(.65deg) scale(1)}
  100%{opacity:1;transform:translate3d(-25px,2px,0) rotate(0) scale(1)}
}
@keyframes sb-wibee-brief-isa{
  0%{opacity:0;transform:translate3d(-25px,5px,0) rotate(-.5deg) scale(.985)}
  38%{opacity:1;transform:translate3d(-25px,2px,0) rotate(-.9deg) scale(1)}
  68%{transform:translate3d(-25px,2px,0) rotate(.65deg) scale(1)}
  100%{opacity:1;transform:translate3d(-25px,2px,0) rotate(0) scale(1)}
}
@keyframes sb-wibee-brief-irp{
  0%{opacity:0;transform:translate3d(-25px,5px,0) rotate(-.5deg) scale(.985)}
  38%{opacity:1;transform:translate3d(-25px,2px,0) rotate(-.9deg) scale(1)}
  68%{transform:translate3d(-25px,2px,0) rotate(.65deg) scale(1)}
  100%{opacity:1;transform:translate3d(-25px,2px,0) rotate(0) scale(1)}
}

/* Small cue toward briefing metrics; one-shot only. */
div:has(> img[alt="위비 캐릭터"]){position:relative;}
div:has(> img[alt="위비 캐릭터"])::after{
  content:"";
  position:absolute;
  right:2px;
  top:47%;
  width:7px;
  height:7px;
  border-radius:999px;
  background:#5b91df;
  box-shadow:0 0 0 0 rgba(91,145,223,.20);
  opacity:0;
  animation:sb-wibee-pointer 1.25s ease-out .45s 1 both;
}
@keyframes sb-wibee-pointer{
  0%{opacity:0;transform:translateX(-4px);box-shadow:0 0 0 0 rgba(91,145,223,.24)}
  35%{opacity:.8;transform:translateX(0);box-shadow:0 0 0 5px rgba(91,145,223,.10)}
  72%{opacity:.65;transform:translateX(2px);box-shadow:0 0 0 2px rgba(91,145,223,.07)}
  100%{opacity:0;transform:translateX(7px);box-shadow:0 0 0 0 rgba(91,145,223,0)}
}

/* Deposit briefing explicitly names the representative Woori product. */
body:has(#market-product-tabs button[data-market-product="deposit"][class*="text-white"]) #wibee-brief-text{
  display:block !important;
  margin-top:4px;
  color:#1556c0;
  font-size:9px;
  line-height:1.2;
  font-weight:700;
  white-space:nowrap;
}
body:has(#market-product-tabs button[data-market-product="deposit"][class*="text-white"]) #wibee-brief-text::before{
  content:"대표상품 · 회전정기예금";
}
body:has(#market-product-tabs button[data-market-product="isa"][class*="text-white"]) #wibee-brief-text,
body:has(#market-product-tabs button[data-market-product="irp"][class*="text-white"]) #wibee-brief-text{
  display:none !important;
}

@media (prefers-reduced-motion:reduce){
  img[alt="위비 캐릭터"]{
    animation:none !important;
    opacity:1 !important;
    transform:translate3d(-25px,2px,0) !important;
  }
  div:has(> img[alt="위비 캐릭터"])::after{
    display:none !important;
    animation:none !important;
  }
}
'''
    css_path.write_text(css, encoding="utf-8")


# -------------------------------------------------
# Mobile CSS: compact hero + original Wibee briefing motion.
# -------------------------------------------------
mobile_css_path = Path("static/css/v512-mobile.css")
mobile_css = mobile_css_path.read_text(encoding="utf-8")
marker = "SBRate V5.13 MOBILE BRIEFING"
if marker not in mobile_css:
    mobile_css += r'''

/* =====================================================
   SBRate V5.13 MOBILE BRIEFING
===================================================== */

#mobile-product-tabs:has(.product-tab.is-active[data-product="deposit"]) + .data-meta .data-meta-left::after{
  content:"[출처 : 저축은행중앙회 비교공시]" !important;
}
#mobile-product-tabs:has(.product-tab.is-active[data-product="isa"]) + .data-meta .data-meta-left::after,
#mobile-product-tabs:has(.product-tab.is-active[data-product="irp"]) + .data-meta .data-meta-left::after{
  content:"[출처 : 각 저축은행 홈페이지]" !important;
}

.hero-card{
  padding:10px 13px 10px !important;
  border-radius:18px !important;
}
.hero-top{min-height:30px !important;}
.hero-card h1{font-size:13.5px !important;}
.hero-main-grid{
  grid-template-columns:minmax(0,40%) minmax(0,60%) !important;
  gap:0 !important;
  min-height:80px !important;
  margin-top:0 !important;
}
.hero-wibee-wrap{
  height:80px !important;
  justify-content:flex-end !important;
  align-items:flex-end !important;
  padding-right:0 !important;
  position:relative;
}
.hero-wibee{
  width:min(122px,34vw) !important;
  max-height:98px !important;
  transform-origin:center bottom !important;
  filter:drop-shadow(0 7px 11px rgba(4,43,107,.16)) !important;
  will-change:transform,opacity;
}
body:has(#mobile-product-tabs .product-tab.is-active[data-product="deposit"]) .hero-wibee{
  animation:sb-mobile-wibee-deposit 1.25s cubic-bezier(.22,.72,.2,1) 1 both !important;
}
body:has(#mobile-product-tabs .product-tab.is-active[data-product="isa"]) .hero-wibee{
  animation:sb-mobile-wibee-isa 1.25s cubic-bezier(.22,.72,.2,1) 1 both !important;
}
body:has(#mobile-product-tabs .product-tab.is-active[data-product="irp"]) .hero-wibee{
  animation:sb-mobile-wibee-irp 1.25s cubic-bezier(.22,.72,.2,1) 1 both !important;
}
@keyframes sb-mobile-wibee-deposit{
  0%{opacity:0;transform:translate3d(-2px,4px,0) rotate(-.45deg) scale(.985)}
  40%{opacity:1;transform:translate3d(0,1px,0) rotate(-.8deg) scale(1)}
  70%{transform:translate3d(0,1px,0) rotate(.55deg) scale(1)}
  100%{opacity:1;transform:translate3d(0,1px,0) rotate(0) scale(1)}
}
@keyframes sb-mobile-wibee-isa{
  0%{opacity:0;transform:translate3d(-2px,4px,0) rotate(-.45deg) scale(.985)}
  40%{opacity:1;transform:translate3d(0,1px,0) rotate(-.8deg) scale(1)}
  70%{transform:translate3d(0,1px,0) rotate(.55deg) scale(1)}
  100%{opacity:1;transform:translate3d(0,1px,0) rotate(0) scale(1)}
}
@keyframes sb-mobile-wibee-irp{
  0%{opacity:0;transform:translate3d(-2px,4px,0) rotate(-.45deg) scale(.985)}
  40%{opacity:1;transform:translate3d(0,1px,0) rotate(-.8deg) scale(1)}
  70%{transform:translate3d(0,1px,0) rotate(.55deg) scale(1)}
  100%{opacity:1;transform:translate3d(0,1px,0) rotate(0) scale(1)}
}

body:has(#mobile-product-tabs .product-tab.is-active[data-product="deposit"]) .hero-wibee-wrap::after{
  animation:sb-mobile-pointer-deposit 1.1s ease-out .4s 1 both;
}
body:has(#mobile-product-tabs .product-tab.is-active[data-product="isa"]) .hero-wibee-wrap::after{
  animation:sb-mobile-pointer-isa 1.1s ease-out .4s 1 both;
}
body:has(#mobile-product-tabs .product-tab.is-active[data-product="irp"]) .hero-wibee-wrap::after{
  animation:sb-mobile-pointer-irp 1.1s ease-out .4s 1 both;
}
.hero-wibee-wrap::after{
  content:"";
  position:absolute;
  right:0;
  top:48%;
  width:6px;
  height:6px;
  border-radius:999px;
  background:#79a9e8;
  opacity:0;
}
@keyframes sb-mobile-pointer-deposit{
  0%{opacity:0;transform:translateX(-4px)}
  40%{opacity:.8;transform:translateX(0);box-shadow:0 0 0 4px rgba(121,169,232,.12)}
  100%{opacity:0;transform:translateX(6px);box-shadow:0 0 0 0 rgba(121,169,232,0)}
}
@keyframes sb-mobile-pointer-isa{
  0%{opacity:0;transform:translateX(-4px)}
  40%{opacity:.8;transform:translateX(0);box-shadow:0 0 0 4px rgba(121,169,232,.12)}
  100%{opacity:0;transform:translateX(6px);box-shadow:0 0 0 0 rgba(121,169,232,0)}
}
@keyframes sb-mobile-pointer-irp{
  0%{opacity:0;transform:translateX(-4px)}
  40%{opacity:.8;transform:translateX(0);box-shadow:0 0 0 4px rgba(121,169,232,.12)}
  100%{opacity:0;transform:translateX(6px);box-shadow:0 0 0 0 rgba(121,169,232,0)}
}

.hero-rate-panel{padding-left:0 !important;}
.hero-product-name{font-size:9.2px !important;margin-bottom:1px !important;}
.hero-rate{font-size:30px !important;}
.hero-card .ai-brief{
  margin-top:5px !important;
  padding-top:6px !important;
  font-size:10.2px !important;
  line-height:1.4 !important;
}

@media(max-width:380px){
  .hero-card{padding:9px 12px 9px !important;}
  .hero-main-grid{
    grid-template-columns:minmax(0,38%) minmax(0,62%) !important;
    min-height:76px !important;
  }
  .hero-wibee-wrap{height:76px !important;}
  .hero-wibee{width:min(108px,31vw) !important;max-height:92px !important;}
  .hero-rate{font-size:28px !important;}
}
@media(min-width:430px){
  .hero-main-grid{grid-template-columns:40% 60% !important;min-height:84px !important;}
  .hero-wibee-wrap{height:84px !important;}
  .hero-wibee{width:130px !important;max-height:103px !important;}
  .hero-rate{font-size:32px !important;}
}
@media (prefers-reduced-motion:reduce){
  .hero-wibee{
    animation:none !important;
    opacity:1 !important;
    transform:none !important;
  }
  .hero-wibee-wrap::after{
    display:none !important;
    animation:none !important;
  }
}
'''
    mobile_css_path.write_text(mobile_css, encoding="utf-8")

print("V5.13 targeted patch applied")
