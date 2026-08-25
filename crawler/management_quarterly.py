import argparse
import io
import json
import re
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup


BASE = Path(__file__).resolve().parent.parent
DATA_DIR = BASE / "data" / "management"
OUTPUT = DATA_DIR / "quarters.json"
LIST_URL = "https://www.fsb.or.kr/cosstatfina_0100.act"
KST = timezone(timedelta(hours=9))

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.7",
}

FIELD_PATTERNS = {
    "rank": ["순위"],
    "bank": ["저축은행명", "저축은행", "금융회사명"],
    "region": ["지역", "영업구역"],
    "total_assets": ["총자산"],
    "corporate_loans": ["기업자금", "기업대출", "기업여신"],
    "household_loans": ["가계자금", "가계대출", "가계여신"],
    "total_loans": ["총대출", "총여신"],
    "bis_ratio": ["BIS비율", "BIS기준자기자본비율", "BIS"],
    "npl_ratio": ["고정이하여신비율", "고정이하비율", "고정이하"],
    "delinquency_ratio": ["연체율"],
    "net_income": ["당기순이익", "순이익"],
    "employees": ["임직원수", "임직원"],
}

CURRENT_VALUE_FIELDS = {
    "total_assets", "total_loans", "net_income", "corporate_loans",
    "household_loans", "bis_ratio", "npl_ratio", "delinquency_ratio",
    "employees",
}


def clean(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def compact(value):
    return re.sub(r"\s+", "", str(value or "")).replace("\n", "")


def number(value):
    text = clean(value)
    if not text or text in ("-", "–", "—", "N/A", "n/a"):
        return None
    negative = False
    if text.startswith(("△", "▲", "-")):
        negative = True
    text = text.replace(",", "").replace("%", "")
    text = text.replace("△", "").replace("▲", "").replace("억원", "").replace("명", "")
    m = re.search(r"-?\d+(?:\.\d+)?", text)
    if not m:
        return None
    value = float(m.group(0))
    if negative and value > 0:
        value = -value
    return value


def parse_quarter_title(title):
    m = re.search(r"(20\d{2})\s*년\s*(3|6|9|12)\s*월말", clean(title))
    if not m:
        return None
    year = int(m.group(1))
    month = int(m.group(2))
    quarter = month // 3
    return {
        "key": f"{year}Q{quarter}",
        "label": f"{year}년 {quarter}분기",
        "as_of": f"{year:04d}-{month:02d}-{31 if month in (3,12) else 30:02d}",
        "month": month,
    }


def session():
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def discover_downloads(limit=12):
    s = session()
    r = s.get(LIST_URL, timeout=35)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    found = []

    for a in soup.find_all("a", href=True):
        if "다운로드" not in clean(a.get_text(" ", strip=True)):
            continue
        block = a.parent
        context = ""
        for _ in range(4):
            if block is None:
                break
            context = clean(block.get_text(" ", strip=True))
            if re.search(r"20\d{2}\s*년\s*(?:3|6|9|12)\s*월말\s*저축은행\s*금융통계\s*현황", context):
                break
            block = block.parent
        m = re.search(r"20\d{2}\s*년\s*(?:3|6|9|12)\s*월말\s*저축은행\s*금융통계\s*현황", context)
        if not m:
            continue
        title = m.group(0)
        q = parse_quarter_title(title)
        if not q:
            continue
        found.append({**q, "title": title, "url": urljoin(r.url, a["href"])})

    if not found:
        for a in soup.select('a[href*="FileDown.jsp"]'):
            context = clean(a.parent.parent.get_text(" ", strip=True) if a.parent and a.parent.parent else "")
            q = parse_quarter_title(context)
            if q:
                found.append({**q, "title": context, "url": urljoin(r.url, a.get("href"))})

    dedup = {}
    for item in found:
        dedup[item["key"]] = item
    return sorted(dedup.values(), key=lambda x: (x["key"][:4], x["key"][-1]), reverse=True)[:limit]


def xlsx_tables(content):
    zf = zipfile.ZipFile(io.BytesIO(content))
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    shared = []
    if "xl/sharedStrings.xml" in zf.namelist():
        root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
        for si in root.findall("m:si", ns):
            parts = [node.text or "" for node in si.findall(".//m:t", ns)]
            shared.append("".join(parts))

    tables = []
    for name in sorted(n for n in zf.namelist() if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")):
        root = ET.fromstring(zf.read(name))
        rows = []
        for row in root.findall(".//m:sheetData/m:row", ns):
            cells = {}
            max_col = 0
            for cell in row.findall("m:c", ns):
                ref = cell.get("r") or "A1"
                letters = re.match(r"[A-Z]+", ref).group(0)
                col = 0
                for ch in letters:
                    col = col * 26 + (ord(ch) - 64)
                max_col = max(max_col, col)
                t = cell.get("t")
                v = cell.find("m:v", ns)
                value = v.text if v is not None else ""
                if t == "s" and value.isdigit():
                    idx = int(value)
                    value = shared[idx] if idx < len(shared) else value
                elif t == "inlineStr":
                    parts = [node.text or "" for node in cell.findall(".//m:t", ns)]
                    value = "".join(parts)
                cells[col] = value
            if max_col:
                rows.append([cells.get(i, "") for i in range(1, max_col + 1)])
        if rows:
            tables.append(rows)
    return tables


def pdf_tables(content):
    import pdfplumber
    tables = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables() or []:
                if table:
                    tables.append([[clean(cell) for cell in row] for row in table if row])
    return tables


def _looks_like_bank(value):
    text = clean(value)
    return "저축은행" in text and 2 <= len(text) <= 40


def _numeric_count(row):
    return sum(number(cell) is not None for cell in row)


def _header_text(rows, data_idx, col):
    values = []
    for row in rows[max(0, data_idx - 5):data_idx]:
        if col >= len(row):
            continue
        text = clean(row[col])
        if text and text not in values:
            values.append(text)
    return compact(" ".join(values))


def _field_for_header(header, field):
    return any(compact(pattern).lower() in header.lower() for pattern in FIELD_PATTERNS[field])


def _is_delta_header(header):
    return any(token in header for token in ("대비", "전년말", "전년동기", "증감", "比", "변동"))


def parse_table(rows):
    if not rows:
        return [], 0
    width = max((len(row) for row in rows), default=0)
    rows = [list(row) + [""] * (width - len(row)) for row in rows]

    data_idx = None
    for idx, row in enumerate(rows):
        if any(_looks_like_bank(cell) for cell in row) and _numeric_count(row) >= 4:
            data_idx = idx
            break
    if data_idx is None:
        return [], 0

    headers = [_header_text(rows, data_idx, col) for col in range(width)]
    mapping = {}

    for col in range(width):
        hits = sum(1 for row in rows[data_idx:data_idx+12] if _looks_like_bank(row[col]))
        if hits >= 2:
            mapping["bank"] = col
            break

    for field in FIELD_PATTERNS:
        if field == "bank" or field in mapping:
            continue
        candidates = []
        for col, header in enumerate(headers):
            if not _field_for_header(header, field):
                continue
            penalty = 0
            if field in CURRENT_VALUE_FIELDS and _is_delta_header(header):
                penalty += 10
            if field == "rank" and _is_delta_header(header):
                penalty += 10
            candidates.append((penalty, col))
        if candidates:
            candidates.sort()
            mapping[field] = candidates[0][1]

    score = sum(1 for key in (
        "bank", "total_assets", "corporate_loans", "household_loans",
        "total_loans", "bis_ratio", "npl_ratio", "delinquency_ratio",
        "net_income", "employees",
    ) if key in mapping)
    if "bank" not in mapping or score < 5:
        return [], score

    output = []
    for row in rows[data_idx:]:
        bank = clean(row[mapping["bank"]]) if mapping["bank"] < len(row) else ""
        if not _looks_like_bank(bank):
            continue
        item = {"bank": bank}
        for field, col in mapping.items():
            if field == "bank" or col >= len(row):
                continue
            raw = clean(row[col])
            if field == "region":
                item[field] = raw or None
            elif field == "rank":
                value = number(raw)
                item[field] = int(value) if value is not None else None
            else:
                item[field] = number(raw)
        output.append(item)
    return output, score


def parse_document(content):
    if content.startswith(b"%PDF"):
        tables = pdf_tables(content)
        source_type = "pdf"
    elif content.startswith(b"PK"):
        tables = xlsx_tables(content)
        source_type = "xlsx"
    else:
        raise RuntimeError("지원하지 않는 중앙회 첨부파일 형식")

    all_rows = []
    best_score = 0
    for table in tables:
        rows, score = parse_table(table)
        best_score = max(best_score, score)
        if score >= 7 and rows:
            all_rows.extend(rows)

    dedup = {}
    for row in all_rows:
        key = compact(row.get("bank"))
        if key:
            old = dedup.get(key, {})
            merged = dict(old)
            for field, value in row.items():
                if value not in (None, ""):
                    merged[field] = value
            dedup[key] = merged

    rows = list(dedup.values())
    rows.sort(key=lambda row: (-(row.get("total_assets") or -1), compact(row.get("bank"))))
    for idx, row in enumerate(rows, 1):
        if row.get("total_assets") is not None:
            row["asset_rank"] = idx

    return rows, source_type, best_score


def load_store():
    try:
        with OUTPUT.open("r", encoding="utf-8-sig") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_store(store):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)


def collect(limit=12):
    downloads = discover_downloads(limit=limit)
    if not downloads:
        raise RuntimeError("저축은행중앙회 금융통계 다운로드 목록을 찾지 못했습니다.")

    store = load_store()
    quarters = store.get("quarters") if isinstance(store.get("quarters"), dict) else {}
    now_text = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    changed = 0
    errors = []
    s = session()

    for item in downloads:
        key = item["key"]
        print(f"[{key}] {item['url']}")
        try:
            response = s.get(item["url"], timeout=60, allow_redirects=True)
            response.raise_for_status()
            rows, source_type, score = parse_document(response.content)
            valid_assets = sum(1 for row in rows if row.get("total_assets") is not None)
            if len(rows) < 20 or valid_assets < 15:
                raise RuntimeError(
                    f"표 파싱 품질 부족 rows={len(rows)} assets={valid_assets} header_score={score}"
                )

            quarters[key] = {
                "label": item["label"],
                "as_of": item["as_of"],
                "source_url": item["url"],
                "source_listing_url": LIST_URL,
                "source_type": source_type,
                "collected_at": now_text,
                "bank_count": len(rows),
                "banks": rows,
            }
            changed += 1
            print(f"  OK {len(rows)} banks / {source_type} / score={score}")
        except Exception as error:
            errors.append({"quarter": key, "error": str(error), "url": item["url"]})
            print(f"  ERROR {error}")

    store.update({
        "source_name": "저축은행중앙회 금융통계자료",
        "source_listing_url": LIST_URL,
        "updated_at": now_text,
        "quarters": quarters,
        "last_errors": errors,
    })
    save_store(store)
    print("saved:", OUTPUT)
    print("changed quarters:", changed)
    print("errors:", len(errors))
    return changed, errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=12)
    args = parser.parse_args()
    changed, errors = collect(limit=max(2, min(args.limit, 20)))
    if changed == 0:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
