from pathlib import Path

css_path = Path("static/css/v513-mobile-hero-hotfix.css")
html_path = Path("templates/mobile.html")

css = css_path.read_text(encoding="utf-8")
html = html_path.read_text(encoding="utf-8")

marker = "SBRate V5.37 MOBILE POINTER CUE PER PRODUCT"
block = r'''

/* =====================================================
   SBRate V5.37 MOBILE POINTER CUE PER PRODUCT
   Replay the white briefing pointer whenever
   Deposit / ISA / IRP becomes the active product tab.
===================================================== */

body:has(#mobile-product-tabs .product-tab.is-active[data-product="deposit"]) .hero-wibee-wrap::after{
  animation:sb-v537-pointer-deposit 1.4s ease-out .42s 1 both !important;
}

body:has(#mobile-product-tabs .product-tab.is-active[data-product="isa"]) .hero-wibee-wrap::after{
  animation:sb-v537-pointer-isa 1.4s ease-out .42s 1 both !important;
}

body:has(#mobile-product-tabs .product-tab.is-active[data-product="irp"]) .hero-wibee-wrap::after{
  animation:sb-v537-pointer-irp 1.4s ease-out .42s 1 both !important;
}

@keyframes sb-v537-pointer-deposit{
  0%{opacity:0;transform:scaleX(.15)}
  32%,66%{opacity:.9;transform:scaleX(1)}
  100%{opacity:0;transform:scaleX(.55) translateX(5px)}
}

@keyframes sb-v537-pointer-isa{
  0%{opacity:0;transform:scaleX(.15)}
  32%,66%{opacity:.9;transform:scaleX(1)}
  100%{opacity:0;transform:scaleX(.55) translateX(5px)}
}

@keyframes sb-v537-pointer-irp{
  0%{opacity:0;transform:scaleX(.15)}
  32%,66%{opacity:.9;transform:scaleX(1)}
  100%{opacity:0;transform:scaleX(.55) translateX(5px)}
}

@media(prefers-reduced-motion:reduce){
  body:has(#mobile-product-tabs .product-tab.is-active[data-product="deposit"]) .hero-wibee-wrap::after,
  body:has(#mobile-product-tabs .product-tab.is-active[data-product="isa"]) .hero-wibee-wrap::after,
  body:has(#mobile-product-tabs .product-tab.is-active[data-product="irp"]) .hero-wibee-wrap::after{
    animation:none !important;
    display:none !important;
  }
}
'''.strip("\n")

if marker not in css:
    css = css.rstrip() + "\n\n" + block + "\n"

html = html.replace(
    "/static/css/v513-mobile-hero-hotfix.css?v=20260815v536",
    "/static/css/v513-mobile-hero-hotfix.css?v=20260815v537",
)

css_path.write_text(css, encoding="utf-8")
html_path.write_text(html, encoding="utf-8")

assert marker in css
assert "sb-v537-pointer-deposit" in css
assert "sb-v537-pointer-isa" in css
assert "sb-v537-pointer-irp" in css
assert "v513-mobile-hero-hotfix.css?v=20260815v537" in html
