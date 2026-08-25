import io
import json
import re
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape


BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data" / "management" / "quarters.json"
WOORI_KEYS = ("우리금융저축은행", "우리금융")

FIELDS = [
    ("total_assets", "총자산", "억원", "amount"),
    ("corporate_loans", "기업자금대출", "억원", "amount"),
    ("household_loans", "가계자금대출", "억원", "amount"),
    ("total_loans", "총대출", "억원", "amount"),
    ("bis_ratio", "BIS비율", "%", "ratio"),
    ("npl_ratio", "고정이하여신비율", "%", "ratio_bad"),
    ("delinquency_ratio", "연체율", "%", "ratio_bad"),
    ("net_income", "당기순이익", "억원", "amount"),
    ("employees", "임직원수", "명", "count"),
]


def _load_store():
    try:
        with DATA_FILE.open("r", encoding="utf-8-sig") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _quarter_sort_key(value):
    m = re.fullmatch(r"(\d{4})Q([1-4])", str(value or ""))
    if not m:
        return (0, 0)
    return int(m.group(1)), int(m.group(2))


def _quarter_label(value):
    m = re.fullmatch(r"(\d{4})Q([1-4])", str(value or ""))
    return f"{m.group(1)}년 {m.group(2)}분기" if m else str(value or "-")


def _num(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except Exception:
        return None


def _bank_key(name):
    text = re.sub(r"\s+", "", str(name or ""))
    return text.replace("㈜", "").replace("(주)", "")


def _is_woori(name):
    key = _bank_key(name)
    return any(_bank_key(item) in key for item in WOORI_KEYS)


def _rows_for_quarter(store, quarter):
    quarters = store.get("quarters") if isinstance(store.get("quarters"), dict) else {}
    payload = quarters.get(quarter) if isinstance(quarters.get(quarter), dict) else {}
    rows = payload.get("banks") if isinstance(payload.get("banks"), list) else []
    return [row for row in rows if isinstance(row, dict)], payload


def _rank_map(rows):
    ranked = sorted(
        [row for row in rows if _num(row.get("total_assets")) is not None],
        key=lambda row: (-_num(row.get("total_assets")), _bank_key(row.get("bank"))),
    )
    return {_bank_key(row.get("bank")): idx for idx, row in enumerate(ranked, 1)}


def _comparison_payload(base_quarter, compare_quarter):
    store = _load_store()
    base_rows, base_meta = _rows_for_quarter(store, base_quarter)
    compare_rows, compare_meta = _rows_for_quarter(store, compare_quarter)
    if not base_rows:
        return None, f"기준분기 {base_quarter} 데이터가 없습니다."
    if not compare_rows:
        return None, f"비교분기 {compare_quarter} 데이터가 없습니다."

    base_rank = _rank_map(base_rows)
    compare_rank = _rank_map(compare_rows)
    compare_by_bank = {_bank_key(row.get("bank")): row for row in compare_rows}
    ordered = sorted(
        base_rows,
        key=lambda row: (
            base_rank.get(_bank_key(row.get("bank")), 10**9),
            _bank_key(row.get("bank")),
        ),
    )

    out = []
    for row in ordered:
        key = _bank_key(row.get("bank"))
        old = compare_by_bank.get(key, {})
        b_rank = base_rank.get(key)
        c_rank = compare_rank.get(key)
        rank_change = c_rank - b_rank if b_rank is not None and c_rank is not None else None
        metrics = {}
        for field, label, unit, kind in FIELDS:
            base_value = _num(row.get(field))
            compare_value = _num(old.get(field))
            delta = base_value - compare_value if base_value is not None and compare_value is not None else None
            metrics[field] = {
                "label": label, "unit": unit, "kind": kind,
                "base": base_value, "compare": compare_value, "delta": delta,
            }
        out.append({
            "rank": b_rank,
            "compare_rank": c_rank,
            "rank_change": rank_change,
            "bank": row.get("bank") or "-",
            "region": row.get("region") or old.get("region") or "-",
            "is_woori": _is_woori(row.get("bank")),
            "metrics": metrics,
        })

    woori = next((item for item in out if item.get("is_woori")), None)
    return {
        "base_quarter": base_quarter,
        "base_label": base_meta.get("label") or _quarter_label(base_quarter),
        "compare_quarter": compare_quarter,
        "compare_label": compare_meta.get("label") or _quarter_label(compare_quarter),
        "base_source_url": base_meta.get("source_url"),
        "compare_source_url": compare_meta.get("source_url"),
        "source_name": "저축은행중앙회 금융통계자료",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "fields": [
            {"key": field, "label": label, "unit": unit, "kind": kind}
            for field, label, unit, kind in FIELDS
        ],
        "rows": out,
        "woori": woori,
    }, None


def _excel_col(index):
    value = index
    result = ""
    while value:
        value, rem = divmod(value - 1, 26)
        result = chr(65 + rem) + result
    return result


def _xml_cell(row, col, value, style=0):
    ref = f"{_excel_col(col)}{row}"
    if value is None:
        return f'<c r="{ref}" s="{style}"/>'
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f'<c r="{ref}" s="{style}"><v>{value}</v></c>'
    text = escape(str(value))
    return f'<c r="{ref}" s="{style}" t="inlineStr"><is><t>{text}</t></is></c>'


def _xlsx_bytes(payload):
    headers = ["순위", "순위변동", "저축은행", "지역"]
    for field in payload["fields"]:
        headers.extend([
            f"{field['label']}({payload['base_label']})",
            f"{field['label']}({payload['compare_label']})",
            f"{field['label']} 증감",
        ])

    rows = []
    for item in payload["rows"]:
        rank_change = item.get("rank_change")
        rank_text = "-"
        if rank_change is not None:
            rank_text = "-" if rank_change == 0 else (f"+{rank_change}" if rank_change > 0 else str(rank_change))
        row = [item.get("rank"), rank_text, item.get("bank"), item.get("region")]
        for field in payload["fields"]:
            metric = item["metrics"].get(field["key"], {})
            row.extend([metric.get("base"), metric.get("compare"), metric.get("delta")])
        rows.append((row, item.get("is_woori")))

    title = f"SBRate 경영현황 비교 - {payload['base_label']} vs {payload['compare_label']}"
    subtitle = "출처: 저축은행중앙회 금융통계자료 | 금액: 억원 / 비율 증감: %p"
    xml_rows = []
    max_col = len(headers)
    xml_rows.append(f'<row r="1" ht="28" customHeight="1">{_xml_cell(1,1,title,1)}</row>')
    xml_rows.append(f'<row r="2" ht="20" customHeight="1">{_xml_cell(2,1,subtitle,2)}</row>')
    header_cells = "".join(_xml_cell(4, idx, value, 3) for idx, value in enumerate(headers, 1))
    xml_rows.append(f'<row r="4" ht="32" customHeight="1">{header_cells}</row>')

    ratio_field_indexes = {
        index for index, field in enumerate(payload["fields"])
        if field.get("kind") in ("ratio", "ratio_bad")
    }
    for r_idx, (values, is_woori) in enumerate(rows, 5):
        cells = []
        for c_idx, value in enumerate(values, 1):
            is_number = isinstance(value, (int, float)) and not isinstance(value, bool)
            is_ratio_number = False
            if is_number and c_idx >= 5:
                field_index = (c_idx - 5) // 3
                is_ratio_number = field_index in ratio_field_indexes
            if is_woori:
                style = 8 if is_ratio_number else (6 if is_number else 5)
            else:
                style = 7 if is_ratio_number else (4 if is_number else 0)
            cells.append(_xml_cell(r_idx, c_idx, value, style))
        xml_rows.append(f'<row r="{r_idx}">{"".join(cells)}</row>')

    widths = []
    for idx in range(1, max_col + 1):
        width = 10
        if idx == 3:
            width = 20
        elif idx == 4:
            width = 12
        elif idx > 4:
            width = 16
        widths.append(f'<col min="{idx}" max="{idx}" width="{width}" customWidth="1"/>')

    end_row = 4 + len(rows)
    end_col = _excel_col(max_col)
    sheet_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetViews><sheetView workbookViewId="0"><pane ySplit="4" xSplit="4" topLeftCell="E5" activePane="bottomRight" state="frozen"/></sheetView></sheetViews>
  <cols>{''.join(widths)}</cols>
  <sheetData>{''.join(xml_rows)}</sheetData>
  <mergeCells count="2"><mergeCell ref="A1:{end_col}1"/><mergeCell ref="A2:{end_col}2"/></mergeCells>
  <autoFilter ref="A4:{end_col}{end_row}"/>
</worksheet>'''

    styles_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="4">
    <font><sz val="10"/><name val="Arial"/></font>
    <font><b/><sz val="16"/><color rgb="FF153F8F"/><name val="Arial"/></font>
    <font><sz val="10"/><color rgb="FF64748B"/><name val="Arial"/></font>
    <font><b/><sz val="10"/><color rgb="FFFFFFFF"/><name val="Arial"/></font>
  </fonts>
  <fills count="4">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF1556C0"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFEFF6FF"/><bgColor indexed="64"/></patternFill></fill>
  </fills>
  <borders count="2">
    <border><left/><right/><top/><bottom/><diagonal/></border>
    <border><left style="thin"><color rgb="FFE2E8F0"/></left><right style="thin"><color rgb="FFE2E8F0"/></right><top style="thin"><color rgb="FFE2E8F0"/></top><bottom style="thin"><color rgb="FFE2E8F0"/></bottom><diagonal/></border>
  </borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <numFmts count="1"><numFmt numFmtId="164" formatCode="0.00"/></numFmts>
  <cellXfs count="9">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1"/>
    <xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/>
    <xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0" applyFont="1"/>
    <xf numFmtId="0" fontId="3" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="3" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1"/>
    <xf numFmtId="0" fontId="0" fillId="3" borderId="1" xfId="0" applyFill="1" applyBorder="1"/>
    <xf numFmtId="3" fontId="0" fillId="3" borderId="1" xfId="0" applyNumberFormat="1" applyFill="1" applyBorder="1"/>
    <xf numFmtId="164" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1"/>
    <xf numFmtId="164" fontId="0" fillId="3" borderId="1" xfId="0" applyNumberFormat="1" applyFill="1" applyBorder="1"/>
  </cellXfs>
</styleSheet>'''

    workbook_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="경영현황 비교" sheetId="1" r:id="rId1"/></sheets>
</workbook>'''
    content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>'''
    root_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>'''
    workbook_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>'''

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", root_rels)
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        zf.writestr("xl/styles.xml", styles_xml)
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    output.seek(0)
    return output


def install_management_report():
    app_module = sys.modules.get("app") or sys.modules.get("__main__")
    if app_module is None or not hasattr(app_module, "app"):
        return False
    if getattr(app_module, "_management_report_installed", False):
        return True

    flask_app = app_module.app
    from flask import jsonify, request, send_file

    @flask_app.get("/api/management-report/quarters")
    def management_report_quarters():
        store = _load_store()
        quarters = store.get("quarters") if isinstance(store.get("quarters"), dict) else {}
        items = []
        for key in sorted(quarters.keys(), key=_quarter_sort_key, reverse=True):
            meta = quarters.get(key) if isinstance(quarters.get(key), dict) else {}
            rows = meta.get("banks") if isinstance(meta.get("banks"), list) else []
            items.append({
                "key": key,
                "label": meta.get("label") or _quarter_label(key),
                "as_of": meta.get("as_of"),
                "bank_count": len(rows),
                "source_url": meta.get("source_url"),
            })
        return jsonify({
            "ok": True,
            "source": "저축은행중앙회 금융통계자료",
            "updated_at": store.get("updated_at"),
            "quarters": items,
        })

    @flask_app.get("/api/management-report")
    def management_report_data():
        base = str(request.args.get("base") or "").strip()
        compare = str(request.args.get("compare") or "").strip()
        store = _load_store()
        available = sorted(list((store.get("quarters") or {}).keys()), key=_quarter_sort_key, reverse=True)
        if not base and available:
            base = available[0]
        if not compare and len(available) > 1:
            compare = available[1]
        if not base or not compare:
            return jsonify({"ok": False, "error": "비교 가능한 분기 데이터가 아직 없습니다."}), 404
        payload, error = _comparison_payload(base, compare)
        if error:
            return jsonify({"ok": False, "error": error}), 404
        return jsonify({"ok": True, **payload})

    @flask_app.get("/api/management-report/export.xlsx")
    def management_report_export():
        base = str(request.args.get("base") or "").strip()
        compare = str(request.args.get("compare") or "").strip()
        payload, error = _comparison_payload(base, compare)
        if error:
            return jsonify({"ok": False, "error": error}), 404
        stream = _xlsx_bytes(payload)
        filename = f"SBRate_경영현황_{base}_vs_{compare}.xlsx"
        return send_file(
            stream,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename,
            max_age=0,
        )

    @flask_app.after_request
    def management_report_assets(response):
        try:
            if (
                request.path in ("/", "/mobile")
                and response.status_code == 200
                and "text/html" in str(response.content_type or "")
            ):
                html = response.get_data(as_text=True)
                marker = 'data-sbrate-management-report="1"'
                if marker not in html:
                    css = (
                        '<link data-sbrate-management-report="1" rel="stylesheet" '
                        'href="/static/css/management_report.css?v=20260825v1">'
                    )
                    js = (
                        '<script data-sbrate-management-report="1" '
                        'src="/static/js/management_report.js?v=20260825v1"></script>'
                    )
                    html = html.replace("</head>", css + "\n</head>", 1)
                    html = html.replace("</body>", js + "\n</body>", 1)
                    response.set_data(html)
                    response.headers.pop("Content-Length", None)
        except Exception as error:
            print("Management report asset wiring error:", error)
        return response

    app_module._management_report_installed = True
    print("Management Report installed")
    return True
