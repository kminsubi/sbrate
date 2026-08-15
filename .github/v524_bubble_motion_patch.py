from pathlib import Path

pc_css_path = Path('static/css/dashboard.css')
mobile_css_path = Path('static/css/v513-mobile-hero-hotfix.css')
index_path = Path('templates/index.html')
mobile_html_path = Path('templates/mobile.html')

pc_css = pc_css_path.read_text(encoding='utf-8').rstrip()
mobile_css = mobile_css_path.read_text(encoding='utf-8').rstrip()
index_html = index_path.read_text(encoding='utf-8')
mobile_html = mobile_html_path.read_text(encoding='utf-8')

pc_marker = 'SBRate V5.24 PC BUBBLE MOTION'
pc_block = r'''/* =====================================================
   SBRate V5.24 PC BUBBLE MOTION
   - make the repeating speech bubble motion clearly visible
   - preserve current bubble coordinates and Wibee position
===================================================== */

div:has(> img[alt="위비 캐릭터"])::before{
  animation:sb-v524-pc-bubble 7.2s cubic-bezier(.22,.72,.2,1) infinite both !important;
  will-change:transform,opacity !important;
}

@keyframes sb-v524-pc-bubble{
  0%,7%{opacity:0;transform:translate3d(-6px,7px,0) scale(.94) rotate(-1deg)}
  12%{opacity:1;transform:translate3d(-2px,2px,0) scale(.99) rotate(-.3deg)}
  22%{opacity:1;transform:translate3d(4px,-3px,0) scale(1.03) rotate(.5deg)}
  31%{opacity:1;transform:translate3d(0,-5px,0) scale(1) rotate(0deg)}
  40%,100%{opacity:0;transform:translate3d(7px,-8px,0) scale(.97) rotate(.3deg)}
}

@media (prefers-reduced-motion:reduce){
  div:has(> img[alt="위비 캐릭터"])::before{
    animation:none !important;
    display:none !important;
  }
}'''

mobile_marker = 'SBRate V5.24 MOBILE BUBBLE POSITION'
mobile_block = r'''/* =====================================================
   SBRate V5.24 MOBILE BUBBLE POSITION
   Move the mobile briefing bubble one visual step right.
===================================================== */

.hero-wibee-wrap::before{
  left:96px;
}

@media(max-width:380px){
  .hero-wibee-wrap::before{left:84px;}
}

@media(min-width:430px){
  .hero-wibee-wrap::before{left:100px;}
}'''

if pc_marker not in pc_css:
    pc_css = pc_css + '\n\n' + pc_block.strip()
if mobile_marker not in mobile_css:
    mobile_css = mobile_css + '\n\n' + mobile_block.strip()

pc_css_path.write_text(pc_css.rstrip() + '\n', encoding='utf-8')
mobile_css_path.write_text(mobile_css.rstrip() + '\n', encoding='utf-8')

index_html = index_html.replace('/static/css/dashboard.css?v=20260815v523', '/static/css/dashboard.css?v=20260815v524', 1)
mobile_html = mobile_html.replace('/static/css/v513-mobile-hero-hotfix.css?v=20260815v519', '/static/css/v513-mobile-hero-hotfix.css?v=20260815v524', 1)

index_path.write_text(index_html, encoding='utf-8')
mobile_html_path.write_text(mobile_html, encoding='utf-8')

print('V5.24 PC bubble motion + mobile bubble position applied')