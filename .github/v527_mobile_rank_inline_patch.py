from pathlib import Path

css_path = Path('static/css/v513-mobile-hero-hotfix.css')
html_path = Path('templates/mobile.html')

css = css_path.read_text(encoding='utf-8').rstrip()
marker = 'SBRate V5.27 MOBILE RANK INLINE'
block = r'''

/* =====================================================
   SBRate V5.27 MOBILE RANK INLINE
   Show market rank context on one line like the dashboard panel.
===================================================== */

.hero-rank-copy{
  display:flex !important;
  align-items:center !important;
  gap:3px !important;
  line-height:1 !important;
  white-space:nowrap !important;
}

.hero-rank-copy .hero-rank-label,
.hero-rank-copy small{
  display:inline !important;
  margin:0 !important;
  white-space:nowrap !important;
}

.hero-rank-copy small{
  color:#cfe1ff !important;
  font-size:7.5px !important;
}

@media(max-width:380px){
  .hero-rank-copy{gap:2px !important;}
  .hero-rank-copy small{font-size:6.6px !important;}
}
'''

if marker not in css:
    css += block
css_path.write_text(css.rstrip() + '\n', encoding='utf-8')

html = html_path.read_text(encoding='utf-8')
html = html.replace('/static/css/v513-mobile-hero-hotfix.css?v=20260815v526', '/static/css/v513-mobile-hero-hotfix.css?v=20260815v527', 1)
html = html.replace('<div class="version-row"><span>Mobile Version</span><strong>V2.0</strong></div>', '<div class="version-row"><span>Mobile Version</span><strong>V2.1</strong></div>', 1)
html_path.write_text(html, encoding='utf-8')

print('V5.27 mobile rank inline applied')
