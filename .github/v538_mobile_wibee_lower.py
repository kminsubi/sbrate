from pathlib import Path

css_path = Path("static/css/v513-mobile-hero-hotfix.css")
html_path = Path("templates/mobile.html")

css = css_path.read_text(encoding="utf-8").rstrip()
marker = "SBRate V5.38 MOBILE WIBEE LOWER FOR ISA / IRP"

if marker not in css:
    css += """

/* =====================================================
   SBRate V5.38 MOBILE WIBEE LOWER FOR ISA / IRP
   Lower the whole Wibee briefing group slightly
   for ISA and IRP to match the Deposit visual balance.
===================================================== */

body:has(#mobile-product-tabs .product-tab.is-active[data-product=\"isa\"]) .hero-wibee-wrap,
body:has(#mobile-product-tabs .product-tab.is-active[data-product=\"irp\"]) .hero-wibee-wrap{
  top:4px !important;
}

@media(max-width:380px){
  body:has(#mobile-product-tabs .product-tab.is-active[data-product=\"isa\"]) .hero-wibee-wrap,
  body:has(#mobile-product-tabs .product-tab.is-active[data-product=\"irp\"]) .hero-wibee-wrap{
    top:3px !important;
  }
}

@media(min-width:430px){
  body:has(#mobile-product-tabs .product-tab.is-active[data-product=\"isa\"]) .hero-wibee-wrap,
  body:has(#mobile-product-tabs .product-tab.is-active[data-product=\"irp\"]) .hero-wibee-wrap{
    top:5px !important;
  }
}
"""

css_path.write_text(css.rstrip() + "\n", encoding="utf-8")

html = html_path.read_text(encoding="utf-8")
old = "v513-mobile-hero-hotfix.css?v=20260815v537"
new = "v513-mobile-hero-hotfix.css?v=20260815v538"
if old not in html and new not in html:
    raise SystemExit("mobile CSS cache token not found")
html = html.replace(old, new)
html_path.write_text(html, encoding="utf-8")
