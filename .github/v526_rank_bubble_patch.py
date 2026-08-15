from pathlib import Path

repo = Path('.')
mobile_html_path = repo / 'templates/mobile.html'
index_html_path = repo / 'templates/index.html'
mobile_css_path = repo / 'static/css/v513-mobile-hero-hotfix.css'
dashboard_css_path = repo / 'static/css/dashboard.css'

mobile_html = mobile_html_path.read_text(encoding='utf-8')
index_html = index_html_path.read_text(encoding='utf-8')
mobile_css = mobile_css_path.read_text(encoding='utf-8').rstrip()
dashboard_css = dashboard_css_path.read_text(encoding='utf-8').rstrip()

old_rank = '''            <span id="hero-rank-pill" class="rank-pill">-위</span>'''
new_rank = '''            <div class="hero-rank-context">
              <div class="hero-rank-copy">
                <span class="hero-rank-label">시장순위</span>
                <small>(최고금리 기준)</small>
              </div>
              <span id="hero-rank-pill" class="rank-pill">-위</span>
            </div>'''

if old_rank in mobile_html:
    mobile_html = mobile_html.replace(old_rank, new_rank, 1)
elif 'class="hero-rank-context"' not in mobile_html:
    raise SystemExit('mobile rank target not found')

mobile_block = r'''

/* =====================================================
   SBRate V5.26 MOBILE RANK CONTEXT + BUBBLE POSITION
   - explain market rank basis next to the rank pill
   - move mobile briefing bubble three visual steps right
===================================================== */

.hero-rank-context{
  margin-left:auto;
  display:flex;
  align-items:center;
  justify-content:flex-end;
  gap:8px;
  min-width:0;
}

.hero-rank-copy{
  min-width:0;
  text-align:right;
  line-height:1.05;
  white-space:nowrap;
}

.hero-rank-label{
  display:block;
  color:#edf5ff;
  font-size:9px;
  font-weight:800;
  letter-spacing:-.02em;
}

.hero-rank-copy small{
  display:block;
  margin-top:3px;
  color:#bdd7ff;
  font-size:7px;
  font-weight:600;
  letter-spacing:-.02em;
}

.hero-wibee-wrap::before{
  left:112px !important;
}

@media(max-width:380px){
  .hero-rank-context{gap:5px;}
  .hero-rank-label{font-size:8.2px;}
  .hero-rank-copy small{font-size:6.4px;}
  .rank-pill{padding-left:7px !important;padding-right:7px !important;}
  .hero-wibee-wrap::before{left:100px !important;}
}

@media(min-width:430px){
  .hero-wibee-wrap::before{left:116px !important;}
}
'''

if 'SBRate V5.26 MOBILE RANK CONTEXT + BUBBLE POSITION' not in mobile_css:
    mobile_css += mobile_block

pc_block = r'''

/* =====================================================
   SBRate V5.26 PC BUBBLE POSITION
   Move the dashboard briefing bubble one visual step down only.
===================================================== */

div:has(> img[alt="위비 캐릭터"])::before{
  top:6px !important;
}

@media (max-width:1500px){
  div:has(> img[alt="위비 캐릭터"])::before{
    top:7px !important;
  }
}
'''

if 'SBRate V5.26 PC BUBBLE POSITION' not in dashboard_css:
    dashboard_css += pc_block

mobile_html = mobile_html.replace('/static/css/v513-mobile-hero-hotfix.css?v=20260815v525', '/static/css/v513-mobile-hero-hotfix.css?v=20260815v526', 1)
index_html = index_html.replace('/static/css/dashboard.css?v=20260815v525', '/static/css/dashboard.css?v=20260815v526', 1)

mobile_html_path.write_text(mobile_html, encoding='utf-8')
index_html_path.write_text(index_html, encoding='utf-8')
mobile_css_path.write_text(mobile_css, encoding='utf-8')
dashboard_css_path.write_text(dashboard_css, encoding='utf-8')

print('V5.26 rank and bubble patch applied')
