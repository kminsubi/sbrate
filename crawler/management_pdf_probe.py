import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

PAGE = 'https://www.fsb.or.kr/busmagequar_0100.act'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/142.0 Safari/537.36',
    'Accept-Language': 'ko-KR,ko;q=0.9',
    'Referer': PAGE,
}


def main():
    s = requests.Session()
    s.headers.update(HEADERS)
    page = s.get(PAGE, timeout=40)
    page.raise_for_status()
    soup = BeautifulSoup(page.text, 'html.parser')

    print('PAGE=', page.url, 'BYTES=', len(page.content))
    print('\n=== SCRIPT TRANSPORT SEARCH ===')
    matched = 0
    for tag in soup.find_all('script', src=True):
        url = urljoin(page.url, tag.get('src'))
        try:
            r = s.get(url, timeout=30)
            r.raise_for_status()
        except Exception as error:
            print('SCRIPT ERROR', url, type(error).__name__, error)
            continue
        text = r.text
        lower = text.lower()
        if 'createajaxutil' not in lower and 'jexajax' not in lower and 'jexajaxutil' not in lower:
            continue
        matched += 1
        print('\n--- SCRIPT', url, 'BYTES=', len(r.content), '---')
        lines = text.splitlines()
        for idx, line in enumerate(lines, 1):
            low = line.lower()
            if any(token in low for token in (
                'createajaxutil', 'ajaxutil', '$.ajax', 'ajax(', 'serviceid',
                'jex', 'content-type', 'url:', 'url =', '.act', '.json',
                'execute', 'requestdata', 'input', 'output', 'wsid', 'svc',
            )):
                print(f'{idx:05d}: {line[:2400]}')
    print('MATCHED_SCRIPTS=', matched)

    print('\n=== KNOWN PAGE SERVICE BLOCKS ===')
    page_js = 'https://www.fsb.or.kr/js/jex/hsspb/cpspt/bus/mage/sumy/busmagequar_0100.js?251349'
    r = s.get(page_js, timeout=30)
    r.raise_for_status()
    text = r.text
    for service in ('01','02','03','04','05','06','07'):
        marker = f'busmagequar_0100_{service}'
        pos = text.find(marker)
        if pos >= 0:
            print('\nSERVICE', service)
            print(text[max(0,pos-500):pos+1200])


if __name__ == '__main__':
    main()
