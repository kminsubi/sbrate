from pathlib import Path

APP = Path('app.py')
CSS = Path('static/css/v513-mobile-hero-hotfix.css')
MOBILE = Path('templates/mobile.html')

CLOSING = '이상 수신 업권현황 브리핑을 마칩니다.'
MARKER = 'SBRate V5.36 MOBILE RATE CUE PER PRODUCT'

# 1) Telegram Morning Brief closing terminology
app = APP.read_text(encoding='utf-8')
if CLOSING not in app:
    old = '''        *insight,
        "",
        "🌐 PC 대시보드",'''
    new = '''        *insight,
        "",
        "이상 수신 업권현황 브리핑을 마칩니다.",
        "",
        "🌐 PC 대시보드",'''
    if old not in app:
        raise RuntimeError('telegram_brief closing anchor not found')
    app = app.replace(old, new, 1)
APP.write_text(app.rstrip() + '\n', encoding='utf-8')

# 2) Replay the same subtle Woori-rate cue whenever product tab changes.
#    Distinct animation names force a restart on deposit/ISA/IRP transitions.
css = CSS.read_text(encoding='utf-8').rstrip()
if MARKER not in css:
    block = r'''
/* =====================================================
   SBRate V5.36 MOBILE RATE CUE PER PRODUCT
   Replay the same one-shot Woori-rate highlight whenever
   Deposit / ISA / IRP becomes the active product tab.
===================================================== */

body:has(#mobile-product-tabs .product-tab.is-active[data-product="deposit"]) .hero-rate{
  animation:sb-v536-rate-cue-deposit 1.1s ease-out .30s 1 both !important;
}

body:has(#mobile-product-tabs .product-tab.is-active[data-product="isa"]) .hero-rate{
  animation:sb-v536-rate-cue-isa 1.1s ease-out .30s 1 both !important;
}

body:has(#mobile-product-tabs .product-tab.is-active[data-product="irp"]) .hero-rate{
  animation:sb-v536-rate-cue-irp 1.1s ease-out .30s 1 both !important;
}

@keyframes sb-v536-rate-cue-deposit{
  0%,100%{text-shadow:none;transform:translateZ(0)}
  45%{text-shadow:0 0 20px rgba(220,239,255,.62);transform:scale(1.028)}
}

@keyframes sb-v536-rate-cue-isa{
  0%,100%{text-shadow:none;transform:translateZ(0)}
  45%{text-shadow:0 0 20px rgba(220,239,255,.62);transform:scale(1.028)}
}

@keyframes sb-v536-rate-cue-irp{
  0%,100%{text-shadow:none;transform:translateZ(0)}
  45%{text-shadow:0 0 20px rgba(220,239,255,.62);transform:scale(1.028)}
}

@media(prefers-reduced-motion:reduce){
  body:has(#mobile-product-tabs .product-tab.is-active[data-product="deposit"]) .hero-rate,
  body:has(#mobile-product-tabs .product-tab.is-active[data-product="isa"]) .hero-rate,
  body:has(#mobile-product-tabs .product-tab.is-active[data-product="irp"]) .hero-rate{
    animation:none !important;
    transform:none !important;
    text-shadow:none !important;
  }
}
'''.strip()
    css += '\n\n' + block
CSS.write_text(css.rstrip() + '\n', encoding='utf-8')

# 3) Cache/version bump
html = MOBILE.read_text(encoding='utf-8')
html = html.replace(
    'v513-mobile-hero-hotfix.css?v=20260815v535',
    'v513-mobile-hero-hotfix.css?v=20260815v536'
)
html = html.replace(
    '<div class="version-row"><span>Mobile Version</span><strong>V2.5</strong></div>',
    '<div class="version-row"><span>Mobile Version</span><strong>V2.6</strong></div>'
)
MOBILE.write_text(html.rstrip() + '\n', encoding='utf-8')
