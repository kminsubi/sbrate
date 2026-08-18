from pathlib import Path

css_path = Path("static/css/dashboard.css")
index_path = Path("templates/index.html")
workflow_path = Path(".github/workflows/patch_v541_pc_wibee_priority.yml")
script_path = Path(".github/patch_v541_pc_wibee_priority.py")

css = css_path.read_text(encoding="utf-8")
index = index_path.read_text(encoding="utf-8")

marker = "SBRate V5.41 PC WIBEE REDUCED-MOTION PRIORITY FIX"
block = r'''

/* =====================================================
   SBRate V5.41 PC WIBEE REDUCED-MOTION PRIORITY FIX
   Earlier :has() reduced-motion rules have higher specificity.
   This PC-only rule deliberately outranks them so the enterprise
   dashboard keeps Wibee idle motion + repeating bubble visible.
===================================================== */

html body div.wibee-pc-stage{
  animation:sb-v519-pc-idle 5s ease-in-out 1.4s infinite both !important;
  transform-origin:55% 82% !important;
  will-change:transform !important;
}

html body div.wibee-pc-stage::before{
  display:block !important;
  animation:sb-v524-pc-bubble 7.2s cubic-bezier(.22,.72,.2,1) infinite both !important;
  will-change:transform,opacity !important;
}

@media(prefers-reduced-motion:reduce){
  html body div.wibee-pc-stage{
    animation:sb-v519-pc-idle 5s ease-in-out 1.4s infinite both !important;
    transform-origin:55% 82% !important;
    transform:none;
  }

  html body div.wibee-pc-stage::before{
    display:block !important;
    animation:sb-v524-pc-bubble 7.2s cubic-bezier(.22,.72,.2,1) infinite both !important;
  }
}
'''.rstrip()

if marker not in css:
    css = css.rstrip() + "\n" + block + "\n"

if "dashboard.css?v=20260818v540" not in index:
    raise SystemExit("Expected dashboard.css v540 cache token not found")
index = index.replace("dashboard.css?v=20260818v540", "dashboard.css?v=20260818v541", 1)

css_path.write_text(css, encoding="utf-8")
index_path.write_text(index, encoding="utf-8")

# One-shot helper/workflow cleanup before commit.
if workflow_path.exists():
    workflow_path.unlink()
if script_path.exists():
    script_path.unlink()
