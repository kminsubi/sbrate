from pathlib import Path

index_path = Path('templates/index.html')
mobile_path = Path('templates/mobile.html')

index = index_path.read_text(encoding='utf-8')
mobile = mobile_path.read_text(encoding='utf-8')

pc_old = '''            <option value="">전체 기간</option>\n            <option value="3">3개월</option>'''
pc_new = '''            <option value="">전체 기간</option>\n            <option value="1">1개월</option>\n            <option value="3">3개월</option>'''

mobile_old = '''            <select id="mobile-product-period" class="product-period-select" aria-label="조회 기간">\n              <option value="3">3개월</option>'''
mobile_new = '''            <select id="mobile-product-period" class="product-period-select" aria-label="조회 기간">\n              <option value="1">1개월</option>\n              <option value="3">3개월</option>'''

if '<option value="1">1개월</option>' not in index:
    if pc_old not in index:
        raise SystemExit('PC period select target not found')
    index = index.replace(pc_old, pc_new, 1)

if '<option value="1">1개월</option>' not in mobile:
    if mobile_old not in mobile:
        raise SystemExit('Mobile period select target not found')
    mobile = mobile.replace(mobile_old, mobile_new, 1)

mobile = mobile.replace(
    '<div class="version-row"><span>Mobile Version</span><strong>V2.2</strong></div>',
    '<div class="version-row"><span>Mobile Version</span><strong>V2.3</strong></div>',
    1
)

index_path.write_text(index, encoding='utf-8')
mobile_path.write_text(mobile, encoding='utf-8')

print('V5.31 one-month period options applied to PC and mobile')
