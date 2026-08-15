from pathlib import Path

pc_css_path = Path('static/css/dashboard.css')
mobile_css_path = Path('static/css/v513-mobile-hero-hotfix.css')
index_path = Path('templates/index.html')
mobile_html_path = Path('templates/mobile.html')

pc_css = pc_css_path.read_text(encoding='utf-8').rstrip()
mobile_css = mobile_css_path.read_text(encoding='utf-8').rstrip()

pc_marker = 'SBRate V5.25 PC BUBBLE POSITION'
mobile_marker = 'SBRate V5.25 MOBILE BUBBLE POSITION'

if pc_marker not in pc_css:
    pc_css += r'''

/* =====================================================
   SBRate V5.25 PC BUBBLE POSITION
   - move dashboard speech bubble one visual step right
   - keep vertical position, motion, and Wibee position unchanged
===================================================== */

div:has(> img[alt="위비 캐릭터"])::before{
  left:0px !important;
}

@media (max-width:1500px){
  div:has(> img[alt="위비 캐릭터"])::before{
    left:-2px !important;
  }
}
'''

if mobile_marker not in mobile_css:
    mobile_css += r'''

/* =====================================================
   SBRate V5.25 MOBILE BUBBLE POSITION
   Force the briefing bubble one more visible step right.
===================================================== */

.hero-wibee-wrap::before{
  left:100px !important;
}

@media(max-width:380px){
  .hero-wibee-wrap::before{left:88px !important;}
}

@media(min-width:430px){
  .hero-wibee-wrap::before{left:104px !important;}
}
'''

pc_css_path.write_text(pc_css, encoding='utf-8')
mobile_css_path.write_text(mobile_css, encoding='utf-8')

index_html = index_path.read_text(encoding='utf-8')
index_html = index_html.replace('/static/css/dashboard.css?v=20260815v524', '/static/css/dashboard.css?v=20260815v525', 1)
index_path.write_text(index_html, encoding='utf-8')

mobile_html = mobile_html_path.read_text(encoding='utf-8')
mobile_html = mobile_html.replace('/static/css/v513-mobile-hero-hotfix.css?v=20260815v524', '/static/css/v513-mobile-hero-hotfix.css?v=20260815v525', 1)
mobile_html_path.write_text(mobile_html, encoding='utf-8')

print('V5.25 bubble positions applied')