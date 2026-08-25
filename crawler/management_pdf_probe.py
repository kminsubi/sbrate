import io
import requests
import pdfplumber

from management_quarterly import discover_downloads, HEADERS


def main():
    item = discover_downloads(limit=1)[0]
    r = requests.get(item['url'], headers=HEADERS, timeout=60, allow_redirects=True)
    r.raise_for_status()
    print('PROBE', item['key'], item['url'], 'bytes=', len(r.content))
    with pdfplumber.open(io.BytesIO(r.content)) as pdf:
        print('PAGES=', len(pdf.pages))
        hits = 0
        for idx, page in enumerate(pdf.pages, 1):
            text = page.extract_text(layout=True) or ''
            compact = text.replace(' ', '')
            keywords = ['저축은행명', '총자산', '기업자금', '가계자금', 'BIS비율', '고정이하', '연체율', '임직원수']
            if any(k.replace(' ', '') in compact for k in keywords):
                hits += 1
                print('\n=== PAGE', idx, '===')
                print(text[:7000])
                print('WORDS=', len(page.extract_words() or []), 'TABLES=', len(page.extract_tables() or []))
        print('HIT_PAGES=', hits)


if __name__ == '__main__':
    main()
