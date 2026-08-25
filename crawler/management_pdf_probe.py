import json
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

PAGE = 'https://www.fsb.or.kr/busmagequar_0100.act'
QUAR = 'https://www.fsb.or.kr/js/jex/hsspb/cpspt/bus/mage/sumy/busmagequar_0100.js?251354'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/142.0 Safari/537.36',
    'Accept-Language': 'ko-KR,ko;q=0.9',
    'Referer': PAGE,
    'X-Requested-With': 'XMLHttpRequest',
}


def call(session, service, data):
    url = urljoin(PAGE, f'/{service}.jct')
    r = session.post(url, data=data, timeout=40)
    print('POST', service, 'status=', r.status_code, 'type=', r.headers.get('content-type'), 'bytes=', len(r.content))
    r.raise_for_status()
    try:
        payload = r.json()
    except Exception:
        print('NONJSON=', r.text[:1200])
        return None
    head = payload.get('COMMON_HEAD') if isinstance(payload, dict) else None
    if head:
        print('COMMON_HEAD=', json.dumps(head, ensure_ascii=False)[:800])
    return payload


def find_global_candidates(text, name):
    values = []
    patterns = [
        rf'\b{name}\s*=\s*["\']([^"\']*)["\']',
        rf'\bvar\s+{name}\s*=\s*["\']([^"\']*)["\']',
    ]
    for pat in patterns:
        for m in re.finditer(pat, text, re.I):
            value = m.group(1)
            if value not in values:
                values.append(value)
    return values


def print_selected(payload, service):
    if not isinstance(payload, dict):
        return
    keys = sorted(k for k in payload.keys() if k != 'COMMON_HEAD')
    print(f'SERVICE {service} KEY_COUNT=', len(keys))
    print('KEYS=', keys)
    interesting = {}
    tokens = (
        'ASSET', 'LOAN', 'CREDIT', 'CAPITAL', 'OVER', 'DELAY', 'ARREAR',
        'PROFIT', 'STAFF', 'YEAR', 'MON', 'QUAR', 'GUBUN', 'AREA', 'REGION',
    )
    for key in keys:
        if any(token in key.upper() for token in tokens):
            interesting[key] = payload.get(key)
    print('INTERESTING=', json.dumps(interesting, ensure_ascii=False)[:16000])


def main():
    s = requests.Session()
    s.headers.update(HEADERS)
    page = s.get(PAGE, timeout=40)
    page.raise_for_status()
    html = page.text
    quar = s.get(QUAR, timeout=40).text
    print('PAGE=', page.url, 'STATUS=', page.status_code, 'cookies=', s.cookies.get_dict())

    print('\n=== GLOBAL CANDIDATES ===')
    for name in ('AREA', 'G_GUBUN', 'bankCode', 'seq'):
        values = find_global_candidates(html + '\n' + quar, name)
        print(name, values[:20])

    soup = BeautifulSoup(html, 'html.parser')
    area_values = ['']
    for node in soup.select('select option, input'):
        if str(node.get('name') or node.get('id') or '').upper() == 'AREA':
            value = str(node.get('value') or '')
            if value not in area_values:
                area_values.append(value)
    for value in ('01','02','03','04','05','06'):
        if value not in area_values:
            area_values.append(value)

    print('\n=== BANK LIST ===')
    banks = {}
    successful_area = None
    for area in area_values:
        payload = call(s, 'busmagequar_0100_01', {'AREA': area, 'BANK_NAME': ''})
        rec = payload.get('REC') if isinstance(payload, dict) else None
        if isinstance(rec, list):
            print('AREA', repr(area), 'REC=', len(rec), 'sample=', json.dumps(rec[:3], ensure_ascii=False)[:1800])
            if rec and successful_area is None:
                successful_area = area
            for row in rec:
                if isinstance(row, dict) and row.get('BANK_CODE'):
                    banks[str(row['BANK_CODE'])] = row
    print('BANK_UNIQUE=', len(banks))
    woori = next((row for row in banks.values() if '우리' in str(row.get('BANK_NAME') or '')), None)
    print('WOORI=', json.dumps(woori, ensure_ascii=False))
    target = woori or next(iter(banks.values()), None)
    if not target:
        raise SystemExit('No bank row from service 01')

    bank_code = str(target.get('BANK_CODE'))
    g_candidates = find_global_candidates(html + '\n' + quar, 'G_GUBUN')
    for value in ('', '1', '01', '0'):
        if value not in g_candidates:
            g_candidates.append(value)

    print('\n=== QUARTER LIST FOR', target.get('BANK_NAME'), bank_code, '===')
    quarter_payload = None
    chosen_g = None
    for g in g_candidates:
        payload = call(s, 'busmagequar_0100_02', {'BANK_CODE': bank_code, 'G_GUBUN': g, 'SEQ': ''})
        rec = payload.get('REC') if isinstance(payload, dict) else None
        if isinstance(rec, list):
            print('G_GUBUN', repr(g), 'REC=', len(rec), 'sample=', json.dumps(rec[:8], ensure_ascii=False)[:5000])
            if rec and quarter_payload is None:
                quarter_payload = payload
                chosen_g = g
    if not quarter_payload:
        raise SystemExit('No quarter list from service 02')

    rec = quarter_payload.get('REC') or []
    seq = str(rec[0].get('SEQ'))
    print('CHOSEN G_GUBUN=', repr(chosen_g), 'SEQ=', seq, 'TITLE=', rec[0].get('G_TITLE'))

    print('\n=== DETAIL RESPONSES ===')
    detail_params = {
        'SEQ': seq,
        'UPDATE_CNT': '',
        'BANK_CODE': bank_code,
        'G_GUBUN': chosen_g,
    }
    for service in ('03','04','05','06'):
        payload = call(s, f'busmagequar_0100_{service}', detail_params)
        print_selected(payload, service)


if __name__ == '__main__':
    main()
