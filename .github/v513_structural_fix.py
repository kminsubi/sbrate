from pathlib import Path
import re

index_path = Path("templates/index.html")
css_path = Path("static/css/dashboard.css")

html = index_path.read_text(encoding="utf-8")

outer = '''  <!-- 메인 레이아웃 (대시보드 + 우측 AI 분석센터) -->
  <div class="p-6 max-w-[1700px] mx-auto grid grid-cols-12 gap-6 items-start">

    <!-- 좌측 메인 영역 (9컬럼) -->
    <main class="col-span-9 space-y-5">'''

wrapped = '''  <!-- 메인 레이아웃 (대시보드 + 우측 AI 분석센터) -->
  <div class="p-6 max-w-[1700px] mx-auto grid grid-cols-12 gap-6 items-start">

    <!--
      V5.13 structural row:
      좌측 main만 행 높이를 결정하고, 우측 AI 패널은 같은 행의 top/bottom에 고정된다.
      긴 AI 답변은 우측 내부 스크롤만 발생하며 전체 행 높이를 늘리지 않는다.
    -->
    <div id="dashboard-intelligence-row" class="col-span-12 relative grid grid-cols-12 gap-6 items-start">

    <!-- 좌측 메인 영역 (9컬럼) -->
    <main class="col-span-9 space-y-5">'''

if outer not in html:
    raise SystemExit("outer dashboard/main marker not found")
html = html.replace(outer, wrapped, 1)

aside_end = '''    </aside>

    <section id="fullwidth-product-row" class="col-span-12">'''
aside_wrapped_end = '''    </aside>

    </div><!-- /#dashboard-intelligence-row -->

    <section id="fullwidth-product-row" class="col-span-12">'''
if aside_end not in html:
    raise SystemExit("aside/fullwidth boundary not found")
html = html.replace(aside_end, aside_wrapped_end, 1)

# Remove the old JS pixel height synchronizer entirely.
pattern = re.compile(
    r'''\n<script>\n\(function \(\) \{\n\n    function alignAIAnalysisCenter\(\) \{.*?\n\}\)\(\);\n</script>\n''',
    re.S,
)
html, removed = pattern.subn("\n", html, count=1)
if removed != 1:
    raise SystemExit(f"expected one alignAIAnalysisCenter script, removed={removed}")

index_path.write_text(html, encoding="utf-8")

css = css_path.read_text(encoding="utf-8")
marker = "SBRate V5.13 STRUCTURAL AI ROW"
if marker not in css:
    css += r'''

/* =====================================================
   SBRate V5.13 STRUCTURAL AI ROW
   The left main column is the only intrinsic height owner.
   The right AI panel fills that row without contributing
   its content height back into the grid sizing algorithm.
===================================================== */

#dashboard-intelligence-row{
  position:relative !important;
  align-items:start !important;
  min-width:0;
}

#dashboard-intelligence-row > main{
  grid-column:1 / span 9 !important;
  min-width:0;
}

#dashboard-intelligence-row > #ai-analysis-center{
  position:absolute !important;
  grid-column:10 / 13 !important;
  grid-row:1 !important;
  top:0 !important;
  right:0 !important;
  bottom:0 !important;
  left:0 !important;
  align-self:stretch !important;
  width:auto !important;
  height:auto !important;
  min-height:0 !important;
  max-height:none !important;
  margin:0 !important;
  overflow:hidden !important;
}

#dashboard-intelligence-row > #ai-analysis-center > #ai-center-content{
  flex:1 1 0% !important;
  min-height:0 !important;
  max-height:100% !important;
}
'''

css_path.write_text(css, encoding="utf-8")
print("V5.13 structural AI row fix applied")
