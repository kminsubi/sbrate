from pathlib import Path

css_path=Path('static/css/dashboard.css')
html_path=Path('templates/index.html')

css=css_path.read_text(encoding='utf-8')
html=html_path.read_text(encoding='utf-8')

old='''/* =====================================================\n   SBRate V5.21 PC WIBEE POSITION TUNE\n   - lower Wibee slightly without fighting transform animation\n   - move speech bubble clearly further left and upward\n===================================================== */\n\nimg[alt="위비 캐릭터"]{\n  position:relative !important;\n  top:8px !important;\n}\n\ndiv:has(> img[alt="위비 캐릭터"])::before{\n  left:4px !important;\n  top:-6px !important;\n  z-index:6 !important;\n}\n\n@media (max-width:1500px){\n  img[alt="위비 캐릭터"]{\n    top:8px !important;\n  }\n  div:has(> img[alt="위비 캐릭터"])::before{\n    left:2px !important;\n    top:-5px !important;\n  }\n}\n'''
new='''/* =====================================================\n   SBRate V5.22 PC WIBEE POSITION TUNE\n   - lower Wibee two visual steps\n   - move speech bubble three visual steps left\n   - keep bubble vertical position unchanged\n===================================================== */\n\nimg[alt="위비 캐릭터"]{\n  position:relative !important;\n  top:16px !important;\n}\n\ndiv:has(> img[alt="위비 캐릭터"])::before{\n  left:-8px !important;\n  top:-6px !important;\n  z-index:6 !important;\n}\n\n@media (max-width:1500px){\n  img[alt="위비 캐릭터"]{\n    top:16px !important;\n  }\n  div:has(> img[alt="위비 캐릭터"])::before{\n    left:-10px !important;\n    top:-5px !important;\n  }\n}\n'''

if old not in css:
    raise SystemExit('V5.21 position block not found')
css=css.replace(old,new,1)
css_path.write_text(css,encoding='utf-8')

old_link='/static/css/dashboard.css?v=20260815v521'
new_link='/static/css/dashboard.css?v=20260815v522'
if old_link not in html:
    raise SystemExit('dashboard cache marker not found')
html=html.replace(old_link,new_link,1)
html_path.write_text(html,encoding='utf-8')

print('V5.22 PC Wibee/bubble position patch applied')
