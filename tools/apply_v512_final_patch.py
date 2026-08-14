from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def write(rel, text):
    (ROOT / rel).write_text(text, encoding="utf-8", newline="\n")


def replace_all(text, pairs):
    for old, new in pairs:
        text = text.replace(old, new)
    return text


# ---------------------------------------------------------
# PC dashboard HTML
# ---------------------------------------------------------
rel = "templates/index.html"
text = read(rel)
text = replace_all(text, [
    ('href="/static/css/dashboard.css"', 'href="/static/css/dashboard.css?v=20260815"'),
    ('src="/static/js/dashboard.js"', 'src="/static/js/dashboard.js?v=20260815"'),
    ('src="/static/images/wibee.png"', 'src="/static/images/wibee_v512.png?v=20260815"'),
    ('📣 제보하기', '📣 오류 제보하기'),
    ('>제보센터<', '>오류 제보센터<'),
    ('>제보 등록<', '>오류 제보 등록<'),
    ('<span>⏱️ 데이터 기준</span>', '<span>⏱️ 데이터 업데이트 기준</span>'),
    ('임원 보고서', 'AI 보고서'),
    ('임원보고서', 'AI 보고서'),
    ('productRect.bottom - heroRect.top', 'productRect.top - heroRect.top'),
])
# Make the inline alignment stronger than accumulated !important overrides.
text = text.replace(
    'aside.style.height =\n            `${targetHeight}px`;\n\n        aside.style.maxHeight =\n            `${targetHeight}px`;',
    'aside.style.setProperty(\n            "height",\n            `${targetHeight}px`,\n            "important"\n        );\n\n        aside.style.setProperty(\n            "max-height",\n            `${targetHeight}px`,\n            "important"\n        );'
)
write(rel, text)


# ---------------------------------------------------------
# Mobile HTML
# ---------------------------------------------------------
rel = "templates/mobile.html"
text = read(rel)
text = replace_all(text, [
    ('href="/static/css/mobile.css"', 'href="/static/css/mobile.css?v=20260815"'),
    ('href="/static/css/v512-mobile.css"', 'href="/static/css/v512-mobile.css?v=20260815"'),
    ('src="/static/js/mobile.js"', 'src="/static/js/mobile.js?v=20260815"'),
    ('src="/static/images/wibee.png"', 'src="/static/images/wibee_v512.png?v=20260815"'),
    ('데이터 업데이트 00:30', '데이터 업데이트 기준 00:30'),
    ('데이터 기준 -', '데이터 업데이트 기준 -'),
    ('📣 제보하기', '📣 오류 제보하기'),
    ('제보 등록', '오류 제보 등록'),
    ('임원 보고서', 'AI 보고서'),
    ('임원보고서', 'AI 보고서'),
])
write(rel, text)


# ---------------------------------------------------------
# Mobile JS: wording + Kakao brief formatting + report naming
# ---------------------------------------------------------
rel = "static/js/mobile.js"
text = read(rel)
text = replace_all(text, [
    ('데이터 기준 : ${mobileDataBasis()} KST', '데이터 업데이트 기준 : ${mobileDataBasis()} KST'),
    ('⏱ 데이터 업데이트 : ${telegram_read_update_time()}', '⏱ 데이터 업데이트 기준 : ${telegram_read_update_time()}'),
    ('SBRateBot ${currentLabel()} AI Market Analysis Report', 'SBRateBot ${currentLabel()} AI 보고서'),
    ('임원 보고서', 'AI 보고서'),
    ('임원보고서', 'AI 보고서'),
])
# Kakao share uses the same compact divider rhythm as Telegram.
old = '''  const lines = [\n    "☀️ SBRate 오늘의 수신시장 브리핑",\n    `데이터 업데이트 기준 : ${mobileDataBasis()} KST`,\n    "",\n    `📌 ${label} ${period}개월`,\n    `우리금융 : ${wooriRate} · ${rankText}`,'''
if old not in text:
    old = '''  const lines = [\n    "☀️ SBRate 오늘의 수신시장 브리핑",\n    `데이터 기준 : ${mobileDataBasis()} KST`,\n    "",\n    `📌 ${label} ${period}개월`,\n    `우리금융 : ${wooriRate} · ${rankText}`,'''
new = '''  const divider = "━━━━━━━━━━━━";\n  const lines = [\n    "☀️ SBRate Morning Brief",\n    `데이터 업데이트 기준 : ${mobileDataBasis()} KST`,\n    "",\n    divider,\n    `📌 ${label} ${period}개월`,\n    divider,\n    `우리금융 : ${wooriRate} · ${rankText}`,'''
text = text.replace(old, new)
write(rel, text)


# ---------------------------------------------------------
# Telegram / server wording and dividers
# ---------------------------------------------------------
rel = "app.py"
text = read(rel)
text = replace_all(text, [
    ('"━━━━━━━━━━━━━━━━"', '"━━━━━━━━━━━━"'),
    ('f"데이터 기준 : {telegram_read_update_time()} KST"', 'f"데이터 업데이트 기준 : {telegram_read_update_time()} KST"'),
    ('f"데이터 업데이트 : {telegram_read_update_time()}"', 'f"데이터 업데이트 기준 : {telegram_read_update_time()}"'),
    ('"📣 제보하기"', '"📣 오류 제보하기"'),
    ('임원 보고서', 'AI 보고서'),
    ('임원보고서', 'AI 보고서'),
])
write(rel, text)


# ---------------------------------------------------------
# PC CSS final regression guard and Wibee styling
# ---------------------------------------------------------
rel = "static/css/dashboard.css"
text = read(rel)
marker = "SBRate V5.12 FINAL REGRESSION GUARD 2026-08-15"
if marker not in text:
    text += '''\n\n/* =====================================================\n   SBRate V5.12 FINAL REGRESSION GUARD 2026-08-15\n===================================================== */\n\n/* Inline JS owns AI panel height. Do not override it with auto/max viewport. */\n#ai-analysis-center{\n  min-height:320px !important;\n  overflow:hidden !important;\n  contain:layout paint;\n}\n#ai-center-content{\n  min-height:0 !important;\n  overflow-y:auto !important;\n  overflow-x:hidden !important;\n}\n\n/* Same Wibee asset on PC and mobile, with a calm micro-motion. */\nimg[src*="wibee_v512.png"]{\n  filter:drop-shadow(0 9px 15px rgba(4,43,107,.16)) !important;\n  animation:sb-wibee-pc-final 4.4s ease-in-out infinite !important;\n  will-change:transform;\n}\n@keyframes sb-wibee-pc-final{\n  0%,100%{transform:translate3d(-18px,2px,0) rotate(-.3deg) scale(1)}\n  50%{transform:translate3d(-18px,-5px,0) rotate(.55deg) scale(1.012)}\n}\n'''
write(rel, text)

print("V5.12 final patch applied")
