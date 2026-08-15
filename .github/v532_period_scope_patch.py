from pathlib import Path

MARKER_PC = "/* SBRate V5.32 PRODUCT PERIOD AVAILABILITY */"
MARKER_MOBILE = "/* SBRate V5.32 MOBILE PRODUCT PERIOD AVAILABILITY */"

pc_js = Path("static/js/dashboard.js")
mobile_js = Path("static/js/mobile.js")
index = Path("templates/index.html")
mobile = Path("templates/mobile.html")

pc = pc_js.read_text(encoding="utf-8")
if MARKER_PC not in pc:
    pc = pc.rstrip() + "\n\n" + MARKER_PC + r'''
function syncProductPeriodAvailability(mode = activeMarketProduct){
    const select = document.getElementById("product-period-select");
    const oneMonth = select?.querySelector('option[value="1"]');
    if(!select || !oneMonth) return;

    const allowOneMonth = mode === "deposit";
    oneMonth.hidden = !allowOneMonth;
    oneMonth.disabled = !allowOneMonth;

    if(!allowOneMonth && select.value === "1"){
        select.value = "12";
        currentMarketPeriod = "12";
    }
}

document.addEventListener("click", event => {
    const tab = event.target.closest("[data-market-product]");
    if(tab){
        syncProductPeriodAvailability(tab.dataset.marketProduct);
    }
}, true);

document.addEventListener("DOMContentLoaded", () => {
    syncProductPeriodAvailability("deposit");
});
'''
pc_js.write_text(pc.rstrip("\n") + "\n", encoding="utf-8")

mj = mobile_js.read_text(encoding="utf-8")
if MARKER_MOBILE not in mj:
    mj = mj.rstrip() + "\n\n" + MARKER_MOBILE + r'''
function syncMobileProductPeriodAvailability(type = MobileState.product){
  const select = document.getElementById("mobile-product-period");
  const oneMonth = select?.querySelector('option[value="1"]');
  if(!select || !oneMonth) return;

  const allowOneMonth = type === "deposit";
  oneMonth.hidden = !allowOneMonth;
  oneMonth.disabled = !allowOneMonth;

  if(!allowOneMonth && select.value === "1"){
    select.value = "12";
    MobileState.productPeriod = "12";
  }
}

document.addEventListener("click", event => {
  const tab = event.target.closest("#mobile-product-tabs .product-tab[data-product]");
  if(tab){
    syncMobileProductPeriodAvailability(tab.dataset.product);
  }
}, true);

document.addEventListener("DOMContentLoaded", () => {
  syncMobileProductPeriodAvailability("deposit");
});
'''
mobile_js.write_text(mj.rstrip("\n") + "\n", encoding="utf-8")

html = index.read_text(encoding="utf-8")
html = html.replace('/static/js/dashboard.js?v=20260815v513', '/static/js/dashboard.js?v=20260815v532')
index.write_text(html.rstrip() + "\n", encoding="utf-8")

mhtml = mobile.read_text(encoding="utf-8")
mhtml = mhtml.replace('/static/js/mobile.js?v=20260815v530', '/static/js/mobile.js?v=20260815v532')
mhtml = mhtml.replace('<div class="version-row"><span>Mobile Version</span><strong>V2.3</strong></div>', '<div class="version-row"><span>Mobile Version</span><strong>V2.4</strong></div>')
mobile.write_text(mhtml.rstrip() + "\n", encoding="utf-8")
