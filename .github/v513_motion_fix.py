from pathlib import Path

pc=Path('static/css/dashboard.css')
mobile=Path('static/css/v512-mobile.css')

pc_text=pc.read_text(encoding='utf-8')
marker='SBRate V5.13 REDUCED MOTION FINAL'
if marker not in pc_text:
    pc_text += r'''

/* =====================================================
   SBRate V5.13 REDUCED MOTION FINAL
   Match active-state selector specificity so accessibility
   preference always wins over the one-shot briefing motion.
===================================================== */
@media (prefers-reduced-motion:reduce){
  body:has(#market-product-tabs button[data-market-product="deposit"][class*="text-white"]) img[alt="위비 캐릭터"],
  body:has(#market-product-tabs button[data-market-product="isa"][class*="text-white"]) img[alt="위비 캐릭터"],
  body:has(#market-product-tabs button[data-market-product="irp"][class*="text-white"]) img[alt="위비 캐릭터"]{
    animation:none !important;
    opacity:1 !important;
    transform:translate3d(-25px,2px,0) !important;
  }
  body:has(#market-product-tabs) div:has(> img[alt="위비 캐릭터"])::after{
    animation:none !important;
    display:none !important;
  }
}
'''
pc.write_text(pc_text,encoding='utf-8')

mobile_text=mobile.read_text(encoding='utf-8')
marker='SBRate V5.13 MOBILE REDUCED MOTION FINAL'
if marker not in mobile_text:
    mobile_text += r'''

/* =====================================================
   SBRate V5.13 MOBILE REDUCED MOTION FINAL
===================================================== */
@media (prefers-reduced-motion:reduce){
  body:has(#mobile-product-tabs .product-tab.is-active[data-product="deposit"]) .hero-wibee,
  body:has(#mobile-product-tabs .product-tab.is-active[data-product="isa"]) .hero-wibee,
  body:has(#mobile-product-tabs .product-tab.is-active[data-product="irp"]) .hero-wibee{
    animation:none !important;
    opacity:1 !important;
    transform:none !important;
  }
  body:has(#mobile-product-tabs .product-tab.is-active[data-product="deposit"]) .hero-wibee-wrap::after,
  body:has(#mobile-product-tabs .product-tab.is-active[data-product="isa"]) .hero-wibee-wrap::after,
  body:has(#mobile-product-tabs .product-tab.is-active[data-product="irp"]) .hero-wibee-wrap::after{
    animation:none !important;
    display:none !important;
  }
}
'''
mobile.write_text(mobile_text,encoding='utf-8')
print('Reduced-motion specificity fixed')
