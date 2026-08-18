from pathlib import Path

INDEX = Path('templates/index.html')
MOBILE = Path('templates/mobile.html')
WORKFLOW = Path('.github/workflows/v543_brand_reload_patch.yml')
SCRIPT = Path('.github/v543_brand_reload_patch.py')

index = INDEX.read_text(encoding='utf-8')
mobile = MOBILE.read_text(encoding='utf-8')

old_pc_img = '''      <img \n        src="/static/images/ci.png"\n        alt="우리금융저축은행"\n        class="h-7 object-contain"\n        onerror="this.onerror=null; this.src='https://via.placeholder.com/150x30?text=WOORI+SAVINGS+BANK';"\n      />'''
new_pc_img = '''      <img \n        src="/static/images/ci.png"\n        alt="우리금융저축은행"\n        class="h-7 object-contain cursor-pointer select-none"\n        title="대시보드 새로고침"\n        role="button"\n        tabindex="0"\n        onclick="window.location.reload()"\n        onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();window.location.reload();}"\n        onerror="this.onerror=null; this.src='https://via.placeholder.com/150x30?text=WOORI+SAVINGS+BANK';"\n      />'''

old_pc_h1 = '''      <h1 class="text-base font-bold text-gray-900 border-l border-gray-300 pl-3 whitespace-nowrap shrink-0 leading-none">\n        수신 모니터링 현황\n      </h1>'''
new_pc_h1 = '''      <h1 class="text-base font-bold text-gray-900 border-l border-gray-300 pl-3 whitespace-nowrap shrink-0 leading-none cursor-pointer select-none"\n          title="대시보드 새로고침"\n          role="button"\n          tabindex="0"\n          onclick="window.location.reload()"\n          onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();window.location.reload();}">\n        수신 모니터링 현황\n      </h1>'''

old_mobile_brand = '''        <div class="brand">\n          <img src="/static/images/ci.png" alt="우리금융저축은행" class="brand-logo" />\n          <div class="brand-text">\n            <strong>수신 모니터링 현황</strong>\n          </div>\n        </div>'''
new_mobile_brand = '''        <div class="brand"\n             title="대시보드 새로고침"\n             role="button"\n             tabindex="0"\n             onclick="window.location.reload()"\n             onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();window.location.reload();}"\n             style="cursor:pointer;">\n          <img src="/static/images/ci.png" alt="우리금융저축은행" class="brand-logo" />\n          <div class="brand-text">\n            <strong>수신 모니터링 현황</strong>\n          </div>\n        </div>'''

for label, haystack, needle in [
    ('PC CI', index, old_pc_img),
    ('PC title', index, old_pc_h1),
    ('mobile brand', mobile, old_mobile_brand),
]:
    if needle not in haystack:
        raise SystemExit(f'Expected block not found: {label}')

index = index.replace(old_pc_img, new_pc_img, 1).replace(old_pc_h1, new_pc_h1, 1)
mobile = mobile.replace(old_mobile_brand, new_mobile_brand, 1)

# Sanity checks
if index.count('onclick="window.location.reload()"') < 2:
    raise SystemExit('PC reload handlers missing')
if mobile.count('onclick="window.location.reload()"') < 1:
    raise SystemExit('Mobile reload handler missing')

INDEX.write_text(index.rstrip() + '\n', encoding='utf-8')
MOBILE.write_text(mobile.rstrip() + '\n', encoding='utf-8')

# Self-remove one-shot files before commit.
if WORKFLOW.exists():
    WORKFLOW.unlink()
if SCRIPT.exists():
    SCRIPT.unlink()
