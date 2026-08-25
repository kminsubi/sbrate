import re
import requests

PAGE = 'https://www.fsb.or.kr/busmagequar_0100.act'
JEX = 'https://www.fsb.or.kr/js/jexjs/jex.js'
COMM = 'https://www.fsb.or.kr/js/jex/hsspb/comm/FSBcomm.js?251354'
QUAR = 'https://www.fsb.or.kr/js/jex/hsspb/cpspt/bus/mage/sumy/busmagequar_0100.js?251354'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/142.0 Safari/537.36',
    'Accept-Language': 'ko-KR,ko;q=0.9',
    'Referer': PAGE,
}


def fetch(session, url):
    r = session.get(url, timeout=40)
    r.raise_for_status()
    return r.text


def line_slice(text, start, end, title):
    print(f'\n=== {title} lines {start}-{end} ===')
    lines = text.splitlines()
    for idx in range(start, min(end, len(lines)) + 1):
        print(f'{idx:05d}: {lines[idx-1][:3000]}')


def keyword_context(text, keyword, radius=1600):
    print(f'\n=== FIELD KEYWORD {keyword} ===')
    positions = [m.start() for m in re.finditer(re.escape(keyword), text, re.I)]
    if not positions:
        print('NOT FOUND')
        return
    for pos in positions[:8]:
        snippet = text[max(0, pos-radius):pos+radius]
        print(re.sub(r'\n{3,}', '\n\n', snippet))
        print('---')


def main():
    s = requests.Session()
    s.headers.update(HEADERS)
    page = s.get(PAGE, timeout=40)
    page.raise_for_status()
    print('PAGE=', page.url, 'STATUS=', page.status_code)

    jex = fetch(s, JEX)
    comm = fetch(s, COMM)
    quar = fetch(s, QUAR)

    line_slice(jex, 6660, 6805, 'JEX AJAX CORE')
    line_slice(comm, 285, 395, 'FSBCOMM _JEX WRAPPER')

    print('\n=== AJAX SETUP OCCURRENCES ===')
    for source_name, text in [('JEX', jex), ('COMM', comm)]:
        for m in re.finditer(r'ajaxSetup', text, re.I):
            print(source_name, re.sub(r'\s+', ' ', text[max(0,m.start()-900):m.start()+1500])[:2600])

    print('\n=== DESIRED DISPLAY FIELD CONTEXT ===')
    for keyword in (
        '총자산', '기업자금', '가계자금', '총대출', 'BIS',
        '고정이하', '연체율', '당기순이익', '임직원',
    ):
        keyword_context(quar, keyword)

    print('\n=== SERVICE INPUTS ===')
    for service in ('01','02','03','04','05','06'):
        marker = f"createAjaxUtil('busmagequar_0100_{service}')"
        pos = quar.find(marker)
        print('\nSERVICE', service)
        print(quar[max(0,pos-300):pos+1200] if pos >= 0 else 'NOT FOUND')


if __name__ == '__main__':
    main()
