import re
import requests

PAGE = 'https://www.fsb.or.kr/busmagequar_0100.act'
JS = 'https://www.fsb.or.kr/js/jex/hsspb/cpspt/bus/mage/sumy/busmagequar_0100.js?251349'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/142.0 Safari/537.36',
    'Accept-Language': 'ko-KR,ko;q=0.9',
    'Referer': PAGE,
}

TOKENS = (
    'jex', '.act', 'excel', 'gosi', 'busi', 'fina', 'gain', 'etc',
    'SEQ', 'FILE_NM', 'search', 'list', 'ajax', 'inJson', 'execute',
    'YEAR', 'QUAR', 'TERM', 'GUBUN', 'getElementById', 'val(',
)


def main():
    r = requests.get(JS, headers=HEADERS, timeout=40)
    r.raise_for_status()
    text = r.text
    print('JS_URL=', r.url, 'STATUS=', r.status_code, 'BYTES=', len(r.content))
    print('\n=== RELEVANT JS LINES ===')
    lines = text.splitlines()
    for idx, line in enumerate(lines, 1):
        low = line.lower()
        if any(token.lower() in low for token in TOKENS):
            print(f'{idx:04d}: {line[:1800]}')

    print('\n=== SERVICE / ENDPOINT CANDIDATES ===')
    patterns = [
        r'[A-Za-z0-9_/-]+\.act',
        r'[A-Za-z0-9_/-]+\.json',
        r'JexLoader[^\n]{0,300}',
        r'jexAjax[^\n]{0,300}',
        r'createJex[^\n]{0,300}',
        r'gosiExcel[^\n]{0,1200}',
    ]
    seen = set()
    for pat in patterns:
        for m in re.finditer(pat, text, re.I):
            value = re.sub(r'\s+', ' ', m.group(0)).strip()
            if value and value not in seen:
                seen.add(value)
                print(value[:1800])

    print('\n=== FULL JS BEGIN ===')
    print(text[:50000])
    print('=== FULL JS END ===')


if __name__ == '__main__':
    main()
