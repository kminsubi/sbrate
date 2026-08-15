from pathlib import Path

mobile_css = Path('static/css/v513-mobile-hero-hotfix.css')
dashboard_css = Path('static/css/dashboard.css')
mobile_html = Path('templates/mobile.html')
index_html = Path('templates/index.html')

MOBILE_MARKER = 'SBRate V5.35 MOBILE HERO RATE EMPHASIS'
PC_MARKER = 'SBRate V5.35 PC PRODUCT PERIOD EMPHASIS'

mcss = mobile_css.read_text(encoding='utf-8').rstrip()
if MOBILE_MARKER not in mcss:
    mcss += '''

/* =====================================================
   SBRate V5.35 MOBILE HERO RATE EMPHASIS
   - use the open vertical space in the hero
   - strengthen Woori rate hierarchy without changing the gap metric
===================================================== */

.hero-rate-metric{
  transform:translateY(-3px) !important;
}

.hero-rate-metric .metric-label{
  font-size:10.4px !important;
  margin-bottom:4px !important;
  font-weight:700 !important;
}

.hero-rate{
  font-size:35.5px !important;
  line-height:.96 !important;
  letter-spacing:-.045em !important;
}

@media(max-width:380px){
  .hero-rate-metric{transform:translateY(-2px) !important;}
  .hero-rate-metric .metric-label{font-size:9.4px !important;}
  .hero-rate{font-size:31.5px !important;}
}

@media(min-width:430px){
  .hero-rate-metric .metric-label{font-size:10.7px !important;}
  .hero-rate{font-size:36.5px !important;}
}
'''
mobile_css.write_text(mcss + '\n', encoding='utf-8')

dcss = dashboard_css.read_text(encoding='utf-8').rstrip()
if PC_MARKER not in dcss:
    dcss += '''

/* =====================================================
   SBRate V5.35 PC PRODUCT PERIOD EMPHASIS
   Match the mobile product explorer's blue period control.
===================================================== */

#product-period-select{
  border-color:#bfd6f6 !important;
  background:#f3f8ff !important;
  color:#1556c0 !important;
  font-weight:800 !important;
}

#product-period-select:hover{
  border-color:#9fc4f4 !important;
  background:#eef6ff !important;
}

#product-period-select:focus{
  border-color:#7eadeb !important;
  box-shadow:0 0 0 3px rgba(21,86,192,.07) !important;
  outline:none !important;
}
'''
dashboard_css.write_text(dcss + '\n', encoding='utf-8')

mhtml = mobile_html.read_text(encoding='utf-8')
mhtml = mhtml.replace('v513-mobile-hero-hotfix.css?v=20260815v534', 'v513-mobile-hero-hotfix.css?v=20260815v535')
mhtml = mhtml.replace('<div class="version-row"><span>Mobile Version</span><strong>V2.4</strong></div>', '<div class="version-row"><span>Mobile Version</span><strong>V2.5</strong></div>')
mobile_html.write_text(mhtml.rstrip() + '\n', encoding='utf-8')

html = index_html.read_text(encoding='utf-8')
html = html.replace('dashboard.css?v=20260815v526', 'dashboard.css?v=20260815v535')
index_html.write_text(html.rstrip() + '\n', encoding='utf-8')
