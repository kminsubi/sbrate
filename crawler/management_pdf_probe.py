import re
import requests
from bs4 import BeautifulSoup

URL = 'https://www.fsb.or.kr/busmagequar_0100.act'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/142.0 Safari/537.36',
    'Accept-Language': 'ko-KR,ko;q=0.9',
}


def main():
    r = requests.get(URL, headers=HEADERS, timeout=40)
    r.raise_for_status()
    html = r.text
    soup = BeautifulSoup(html, 'html.parser')
    print('URL=', r.url, 'STATUS=', r.status_code, 'BYTES=', len(r.content))

    print('\n=== FORMS ===')
    for form in soup.find_all('form'):
        print('FORM', form.get('id'), form.get('name'), form.get('method'), form.get('action'))
        for node in form.find_all(['input','select','button'])[:160]:
            print(' ', node.name, 'id=', node.get('id'), 'name=', node.get('name'), 'value=', node.get('value'), 'onclick=', node.get('onclick'), 'text=', node.get_text(' ', strip=True)[:80])

    print('\n=== SCRIPTS ===')
    for script in soup.find_all('script'):
        src = script.get('src')
        if src:
            print('SRC', src)
        text = script.get_text('\n', strip=False)
        if any(token.lower() in text.lower() for token in ('excel','busmagequar','ajax','quar','조회')):
            print('INLINE-BEGIN')
            for line in text.splitlines():
                if any(token.lower() in line.lower() for token in ('excel','busmagequar','.act','ajax','quar','year','term','gubun','search','select')):
                    print(line[:900])
            print('INLINE-END')

    print('\n=== HTML MATCHES ===')
    for match in re.finditer(r'.{0,220}(?:엑셀|excel|xlsx|ajax|busmagequar|\.act).{0,350}', html, re.I | re.S):
        snippet = re.sub(r'\s+', ' ', match.group(0)).strip()
        print(snippet[:1100])


if __name__ == '__main__':
    main()
