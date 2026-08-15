from pathlib import Path
import re

html_path = Path('templates/mobile.html')
js_path = Path('static/js/mobile.js')
css_path = Path('static/css/mobile.css')

html = html_path.read_text(encoding='utf-8')
js = js_path.read_text(encoding='utf-8')
css = css_path.read_text(encoding='utf-8')

# 1) Mobile product explorer: add independent period selector beside search.
old_filter = '''          <div class="product-filter-row">
            <input id="mobile-product-search" type="search" placeholder="저축은행명 또는 실제 상품명 검색" />
          </div>'''
new_filter = '''          <div class="product-filter-row product-explorer-filter-row">
            <input id="mobile-product-search" type="search" placeholder="저축은행명 또는 실제 상품명 검색" />
            <select id="mobile-product-period" class="product-period-select" aria-label="조회 기간">
              <option value="3">3개월</option>
              <option value="6">6개월</option>
              <option value="12" selected>12개월</option>
              <option value="24">24개월</option>
              <option value="36">36개월</option>
            </select>
          </div>'''
if old_filter not in html:
    raise SystemExit('mobile product filter markup not found')
html = html.replace(old_filter, new_filter, 1)

# Cache bust + version.
html = html.replace('/static/css/mobile.css?v=20260815v513', '/static/css/mobile.css?v=20260815v529', 1)
html = html.replace('/static/js/mobile.js?v=20260815v513', '/static/js/mobile.js?v=20260815v529', 1)
html = html.replace('<div class="version-row"><span>Mobile Version</span><strong>V2.1</strong></div>', '<div class="version-row"><span>Mobile Version</span><strong>V2.2</strong></div>', 1)

# 2) Independent period state for the product explorer.
state_old = '  topExpanded: false,\n  products: [],'
state_new = '  topExpanded: false,\n  productPeriod: "12",\n  products: [],'
if state_old not in js:
    raise SystemExit('MobileState insertion point not found')
js = js.replace(state_old, state_new, 1)

# 3) Replace loadProducts so product explorer can query a different period
#    without changing the hero/market period.
load_products_pattern = re.compile(
    r'async function loadProducts\(\)\{.*?\n\}\n\nfunction renderProducts\(\)\{',
    re.S
)
load_products_replacement = r'''async function loadProducts(){
  const data =
    MobileState.data[
      MobileState.product
    ];

  const explorerPeriod =
    String(
      MobileState.productPeriod ||
      MobileState.period ||
      "12"
    );

  if(MobileState.product === "deposit"){
    try{
      const payload =
        await api("/api/products");

      const source =
        Array.isArray(payload)
          ? payload
          : (
              payload?.items ||
              payload?.products ||
              []
            );

      MobileState.products =
        source.filter(item=>{
          const period =
            normalizePeriod(
              item.period ??
              item.term ??
              item.save_trm
            );

          return (
            !period ||
            period === explorerPeriod
          );
        });
    }catch(error){
      console.error(
        "MOBILE PRODUCTS ERROR",
        error
      );

      MobileState.products =
        explorerPeriod === MobileState.period
          ? (data?.ranked || [])
          : [];
    }
  }else{
    try{
      const payload =
        await api(
          `/api/${MobileState.product}?period=${encodeURIComponent(explorerPeriod)}`
        );

      const source =
        Array.isArray(payload)
          ? payload
          : (payload?.items || []);

      MobileState.products =
        source.map(
          (item,index) =>
            normalizeAlternativeItem(item,index)
        );
    }catch(error){
      console.error(
        "MOBILE ALTERNATIVE PRODUCTS ERROR",
        error
      );

      MobileState.products =
        explorerPeriod === MobileState.period
          ? (data?.items || [])
          : [];
    }
  }

  renderProducts();
}

function renderProducts(){'''
js, count = load_products_pattern.subn(load_products_replacement, js, count=1)
if count != 1:
    raise SystemExit('loadProducts replacement failed')

# 4) Product row period should reflect explorer period, not hero period.
js = js.replace(
    '? `${MobileState.period}개월`',
    '? `${MobileState.productPeriod || MobileState.period}개월`',
    1
)

# 5) Add period selector event listener next to search listener.
listener_old = '''    $("mobile-product-search")
      .addEventListener(
        "input",
        renderProducts
      );'''
listener_new = '''    $("mobile-product-search")
      .addEventListener(
        "input",
        renderProducts
      );

    $("mobile-product-period")
      ?.addEventListener(
        "change",
        async event=>{
          MobileState.productPeriod =
            String(event.target.value || "12");

          await loadProducts();
        }
      );'''
if listener_old not in js:
    raise SystemExit('product search listener not found')
js = js.replace(listener_old, listener_new, 1)

# 6) Compact mobile styling: search + period selector on one line.
marker = 'SBRate V5.29 MOBILE PRODUCT PERIOD'
if marker not in css:
    block = r'''
/* =========================================================
   SBRate V5.29 MOBILE PRODUCT PERIOD
   Product explorer search + independent period selector
========================================================= */
.product-explorer-filter-row{
  display:grid !important;
  grid-template-columns:minmax(0,1fr) 88px !important;
  gap:8px !important;
  align-items:center !important;
}

.product-explorer-filter-row input,
.product-explorer-filter-row .product-period-select{
  min-width:0 !important;
  height:42px !important;
  border:1px solid #dfe6ef !important;
  border-radius:12px !important;
  background:#fafcff !important;
  color:#5f6c7e !important;
  font-size:10px !important;
  outline:none !important;
}

.product-explorer-filter-row input{
  width:100% !important;
  padding:0 12px !important;
}

.product-explorer-filter-row .product-period-select{
  width:88px !important;
  padding:0 8px !important;
  font-weight:700 !important;
  color:#1556c0 !important;
}

.product-explorer-filter-row input:focus,
.product-explorer-filter-row .product-period-select:focus{
  border-color:#92b9f2 !important;
  box-shadow:0 0 0 3px rgba(21,86,192,.06) !important;
}

@media(max-width:380px){
  .product-explorer-filter-row{
    grid-template-columns:minmax(0,1fr) 82px !important;
    gap:6px !important;
  }
  .product-explorer-filter-row .product-period-select{
    width:82px !important;
    padding:0 6px !important;
    font-size:9.5px !important;
  }
}
'''.strip()
    css = css.rstrip() + '\n\n' + block + '\n'

html_path.write_text(html, encoding='utf-8')
js_path.write_text(js.rstrip() + '\n', encoding='utf-8')
css_path.write_text(css.rstrip() + '\n', encoding='utf-8')

print('V5.29 mobile product period selector applied')
