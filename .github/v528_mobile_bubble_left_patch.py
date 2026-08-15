from pathlib import Path

css_path = Path('static/css/v513-mobile-hero-hotfix.css')
html_path = Path('templates/mobile.html')

css = css_path.read_text(encoding='utf-8').rstrip()
marker = 'SBRate V5.28 MOBILE BUBBLE LEFT TUNE'
block = '''

/* =====================================================
   SBRate V5.28 MOBILE BUBBLE LEFT TUNE
   Move the mobile briefing bubble one visual step left.
===================================================== */

.hero-wibee-wrap::before{
  left:108px !important;
}

@media(max-width:380px){
  .hero-wibee-wrap::before{left:96px !important;}
}

@media(min-width:430px){
  .hero-wibee-wrap::before{left:112px !important;}
}
'''

if marker not in css:
    css += block
css_path.write_text(css.rstrip() + '\n', encoding='utf-8')

html = html_path.read_text(encoding='utf-8')
html = html.replace('/static/css/v513-mobile-hero-hotfix.css?v=20260815v527', '/static/css/v513-mobile-hero-hotfix.css?v=20260815v528', 1)
html_path.write_text(html, encoding='utf-8')

print('V5.28 mobile bubble left tune applied')
