import io
import re
import sys
import zipfile
from xml.sax.saxutils import escape

import management_report as mr
from management_intelligence import build_intelligence


SECTION_LABELS = {
    "general": "종합현황",
    "funding": "수신·조달",
    "soundness": "건전성",
    "profitability": "수익성",
}

GENERAL_ORDER = [
    "total_assets", "household_loans", "corporate_loans", "total_loans",
    "bis_ratio", "npl_ratio", "delinquency_ratio", "net_income", "employees",
]


def _display_bank(value):
    return re.sub(r"\s*저축은행\s*$", "", str(value or "").strip()) or "-"


def _prev_quarter(key):
    m = re.fullmatch(r"(\d{4})Q([1-4])", str(key or ""))
    if not m:
        return None
    y, q = int(m.group(1)), int(m.group(2))
    return f"{y - 1}Q4" if q == 1 else f"{y}Q{q - 1}"


def _prev_year_end(key):
    m = re.fullmatch(r"(\d{4})Q[1-4]", str(key or ""))
    return f"{int(m.group(1)) - 1}Q4" if m else None


def _yoy_quarter(key):
    m = re.fullmatch(r"(\d{4})Q([1-4])", str(key or ""))
    return f"{int(m.group(1)) - 1}Q{m.group(2)}" if m else None


def _row_map(rows):
    return {mr._bank_key(row.get("bank")): row for row in rows if isinstance(row, dict)}


def _delta(a, b):
    a, b = mr._num(a), mr._num(b)
    return a - b if a is not None and b is not None else None


def _excel_col(index):
    value, result = index, ""
    while value:
        value, rem = divmod(value - 1, 26)
        result = chr(65 + rem) + result
    return result


def _cell(row, col, value, style=0):
    ref = f"{_excel_col(col)}{row}"
    if value is None:
        return f'<c r="{ref}" s="{style}"/>'
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f'<c r="{ref}" s="{style}"><v>{value}</v></c>'
    text = escape(str(value))
    return f'<c r="{ref}" s="{style}" t="inlineStr"><is><t>{text}</t></is></c>'


def _style_for(kind, value, woori=False):
    if woori:
        if kind in ("ratio", "delta_ratio"):
            return 9
        if kind in ("amount", "delta_amount"):
            return 8
        if kind in ("int", "rank_delta"):
            return 7
        return 6
    if kind in ("ratio", "delta_ratio"):
        return 5
    if kind in ("amount", "delta_amount"):
        return 4
    if kind in ("int", "rank_delta"):
        return 3
    return 0


def _xlsx_bytes(title, subtitle, sheet_name, headers, kinds, rows):
    xml_rows = [
        f'<row r="1" ht="28" customHeight="1">{_cell(1, 1, title, 1)}</row>',
        f'<row r="2" ht="22" customHeight="1">{_cell(2, 1, subtitle, 2)}</row>',
    ]
    xml_rows.append('<row r="4" ht="30" customHeight="1">' + ''.join(
        _cell(4, i, header, 10) for i, header in enumerate(headers, 1)
    ) + '</row>')

    for r_idx, item in enumerate(rows, 5):
        values = item["values"]
        woori = bool(item.get("is_woori"))
        cells = []
        for c_idx, value in enumerate(values, 1):
            kind = kinds[c_idx - 1] if c_idx - 1 < len(kinds) else "text"
            cells.append(_cell(r_idx, c_idx, value, _style_for(kind, value, woori)))
        xml_rows.append(f'<row r="{r_idx}">{"".join(cells)}</row>')

    max_col = len(headers)
    end_col = _excel_col(max_col)
    end_row = 4 + len(rows)
    widths = []
    for idx, header in enumerate(headers, 1):
        width = 13
        if idx == 1:
            width = 9
        elif "저축은행" in str(header):
            width = 16
        elif "지역" in str(header):
            width = 10
        elif len(str(header)) >= 12:
            width = 18
        widths.append(f'<col min="{idx}" max="{idx}" width="{width}" customWidth="1"/>')

    sheet_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetViews><sheetView workbookViewId="0"><pane ySplit="4" xSplit="3" topLeftCell="D5" activePane="bottomRight" state="frozen"/></sheetView></sheetViews>
  <cols>{''.join(widths)}</cols>
  <sheetData>{''.join(xml_rows)}</sheetData>
  <mergeCells count="2"><mergeCell ref="A1:{end_col}1"/><mergeCell ref="A2:{end_col}2"/></mergeCells>
  <autoFilter ref="A4:{end_col}{end_row}"/>
</worksheet>'''

    styles_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <numFmts count="2"><numFmt numFmtId="164" formatCode="#,#0.00"/><numFmt numFmtId="165" formatCode="0.00"/></numFmts>
  <fonts count="4">
    <font><sz val="10"/><name val="Arial"/></font>
    <font><b/><sz val="16"/><color rgb="FF153F8F"/><name val="Arial"/></font>
    <font><sz val="10"/><color rgb="FF64748B"/><name val="Arial"/></font>
    <font><b/><sz val="10"/><color rgb="FFFFFFFF"/><name val="Arial"/></font>
  </fonts>
  <fills count="4">
    <fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF1556C0"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFEFF6FF"/><bgColor indexed="64"/></patternFill></fill>
  </fills>
  <borders count="2"><border><left/><right/><top/><bottom/><diagonal/></border><border><left style="thin"><color rgb="FFE2E8F0"/></left><right style="thin"><color rgb="FFE2E8F0"/></right><top style="thin"><color rgb="FFE2E8F0"/></top><bottom style="thin"><color rgb="FFE2E8F0"/></bottom><diagonal/></border></borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="11">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1"/>
    <xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/>
    <xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0" applyFont="1"/>
    <xf numFmtId="3" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1"/>
    <xf numFmtId="164" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1"/>
    <xf numFmtId="165" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1"/>
    <xf numFmtId="0" fontId="0" fillId="3" borderId="1" xfId="0" applyFill="1" applyBorder="1"/>
    <xf numFmtId="3" fontId="0" fillId="3" borderId="1" xfId="0" applyNumberFormat="1" applyFill="1" applyBorder="1"/>
    <xf numFmtId="164" fontId="0" fillId="3" borderId="1" xfId="0" applyNumberFormat="1" applyFill="1" applyBorder="1"/>
    <xf numFmtId="165" fontId="0" fillId="3" borderId="1" xfId="0" applyNumberFormat="1" applyFill="1" applyBorder="1"/>
    <xf numFmtId="0" fontId="3" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
  </cellXfs>
</styleSheet>'''

    safe_sheet = str(sheet_name or "경영현황")[:31]
    workbook_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="{escape(safe_sheet)}" sheetId="1" r:id="rId1"/></sheets></workbook>'''
    content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>'''
    root_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'''
    workbook_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>'''

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


def _general_single(base):
    store = mr._load_store()
    quarters = store.get("quarters") if isinstance(store.get("quarters"), dict) else {}
    base_rows, base_meta = mr._rows_for_quarter(store, base)
    if not base_rows:
        raise ValueError(f"{base} 데이터가 없습니다.")

    prev_key, year_key, yoy_key = _prev_quarter(base), _prev_year_end(base), _yoy_quarter(base)
    prev_rows, _ = mr._rows_for_quarter(store, prev_key) if prev_key in quarters else ([], {})
    year_rows, _ = mr._rows_for_quarter(store, year_key) if year_key in quarters else ([], {})
    yoy_rows, _ = mr._rows_for_quarter(store, yoy_key) if yoy_key in quarters else ([], {})

    base_rank, prev_rank = mr._rank_map(base_rows), mr._rank_map(prev_rows)
    prev_map, year_map, yoy_map = _row_map(prev_rows), _row_map(year_rows), _row_map(yoy_rows)
    by_field = {key: (label, unit, kind) for key, label, unit, kind in mr.FIELDS}

    headers = ["순위", "전분기比", "저축은행", "지역"]
    kinds = ["int", "rank_delta", "text", "text"]
    for key in GENERAL_ORDER:
        label, unit, kind = by_field[key]
        headers.append(f"{label}({unit})")
        kinds.append("ratio" if kind.startswith("ratio") else "int" if kind == "count" else "amount")
        if key in ("total_assets", "total_loans"):
            headers.append("전년말比")
            kinds.append("delta_amount")
        elif key == "net_income":
            headers.append("전년동기比")
            kinds.append("delta_amount")

    ordered = sorted(base_rows, key=lambda row: (base_rank.get(mr._bank_key(row.get("bank")), 10**9), mr._bank_key(row.get("bank"))))
    rows = []
    for row in ordered:
        key_id = mr._bank_key(row.get("bank"))
        rank = base_rank.get(key_id)
        old_rank = prev_rank.get(key_id)
        rank_change = old_rank - rank if rank is not None and old_rank is not None else None
        values = [rank, rank_change, _display_bank(row.get("bank")), row.get("region") or "-"]
        for key in GENERAL_ORDER:
            values.append(mr._num(row.get(key)))
            if key in ("total_assets", "total_loans"):
                values.append(_delta(row.get(key), (year_map.get(key_id) or {}).get(key)))
            elif key == "net_income":
                values.append(_delta(row.get(key), (yoy_map.get(key_id) or {}).get(key)))
        rows.append({"values": values, "is_woori": mr._is_woori(row.get("bank"))})

    label = base_meta.get("label") or mr._quarter_label(base)
    subtitle = (
        f"출처: 금융감독원 금융통계정보시스템(FISIS) | 조회분기 {label} | "
        f"순위 전분기比 {prev_key or '-'} · 총자산/총대출 전년말比 {year_key or '-'} · 당기순이익 전년동기比 {yoy_key or '-'}"
    )
    return _xlsx_bytes(f"SBRate 종합현황 분기현황 - {label}", subtitle, "종합현황", headers, kinds, rows)


def _general_compare(base, compare):
    payload, error = mr._comparison_payload(base, compare)
    if error:
        raise ValueError(error)
    field_map = {field["key"]: field for field in payload["fields"]}
    headers = ["순위", "비교분기比", "저축은행", "지역"]
    kinds = ["int", "rank_delta", "text", "text"]
    for key in GENERAL_ORDER:
        field = field_map[key]
        kind = "ratio" if field["kind"].startswith("ratio") else "int" if field["kind"] == "count" else "amount"
        headers += [f"{field['label']}({payload['base_label']})", f"{field['label']}({payload['compare_label']})", "증감"]
        kinds += [kind, kind, "delta_ratio" if kind == "ratio" else "delta_amount" if kind == "amount" else "int"]
    rows = []
    for item in payload["rows"]:
        values = [item.get("rank"), item.get("rank_change"), _display_bank(item.get("bank")), item.get("region") or "-"]
        for key in GENERAL_ORDER:
            pack = item.get("metrics", {}).get(key, {})
            values += [pack.get("base"), pack.get("compare"), pack.get("delta")]
        rows.append({"values": values, "is_woori": item.get("is_woori")})
    title = f"SBRate 종합현황 분기비교 - {payload['base_label']} vs {payload['compare_label']}"
    subtitle = "출처: 금융감독원 금융통계정보시스템(FISIS) | 기준분기·비교분기·증감"
    return _xlsx_bytes(title, subtitle, "종합현황 비교", headers, kinds, rows)


def _metric(row, key):
    return (row.get("metrics") or {}).get(key) or {}


def _intelligence_table(section, mode, base, compare):
    data = build_intelligence(section=section, base=base, compare=compare if mode == "compare" else None)
    if not data.get("ok") or not data.get("ready"):
        raise ValueError(data.get("error") or "확장 경영지표가 준비되지 않았습니다.")
    single = mode == "single"
    delta_label = "전년동기比" if section == "profitability" and single else "전분기比" if single else "비교분기比"

    if section == "funding":
        headers = ["예수금순위", "저축은행", "지역", "총예수금(억원)", delta_label, "정기예금(억원)", delta_label, "정기예금비중(%)", "개인예수금(억원)", "기업예수금(억원)", "단순예대율(%)"]
        kinds = ["int", "text", "text", "amount", "delta_amount", "amount", "delta_amount", "ratio", "amount", "amount", "ratio"]
        def values(row):
            return [row.get("section_rank"), _display_bank(row.get("bank")), row.get("region") or "-", _metric(row,"deposits").get("base"), _metric(row,"deposits").get("delta"), _metric(row,"time_deposits").get("base"), _metric(row,"time_deposits").get("delta"), _metric(row,"time_deposit_mix").get("base"), _metric(row,"personal_deposits").get("base"), _metric(row,"corporate_deposits").get("base"), _metric(row,"simple_loan_deposit_ratio").get("base")]
        ordered = sorted(data.get("rows") or [], key=lambda row: row.get("section_rank") or 10**9)
    elif section == "soundness":
        headers = ["총자산순위", "저축은행", "지역", "BIS(%)", delta_label, "연체율(%)", delta_label, "고정이하여신비율(%)", "유동성비율(%)", "NPL커버리지(%)", "부동산업 기업대출비중(%)"]
        kinds = ["int", "text", "text", "ratio", "delta_ratio", "ratio", "delta_ratio", "ratio", "ratio", "ratio", "ratio"]
        def values(row):
            return [row.get("asset_rank"), _display_bank(row.get("bank")), row.get("region") or "-", _metric(row,"bis_ratio").get("base"), _metric(row,"bis_ratio").get("delta"), _metric(row,"delinquency_ratio").get("base"), _metric(row,"delinquency_ratio").get("delta"), _metric(row,"npl_ratio_effective").get("base"), _metric(row,"liquidity_ratio").get("base"), _metric(row,"npl_coverage_ratio").get("base"), _metric(row,"real_estate_corp_share").get("base")]
        ordered = sorted(data.get("rows") or [], key=lambda row: row.get("asset_rank") or 10**9)
    else:
        headers = ["총자산순위", "저축은행", "지역", "당기순이익(억원)", delta_label, "영업이익(억원)", "ROA(%)", "ROE(%)", "이자 순수익(억원)", "이자비용(억원)", "정기예금 이자비용(억원)"]
        kinds = ["int", "text", "text", "amount", "delta_amount", "amount", "ratio", "ratio", "amount", "amount", "amount"]
        delta_key = "yoy_delta" if single else "delta"
        def values(row):
            return [row.get("asset_rank"), _display_bank(row.get("bank")), row.get("region") or "-", _metric(row,"net_income").get("base"), _metric(row,"net_income").get(delta_key), _metric(row,"operating_profit").get("base"), _metric(row,"roa").get("base"), _metric(row,"roe").get("base"), _metric(row,"net_interest_income").get("base"), _metric(row,"interest_expense").get("base"), _metric(row,"time_deposit_interest_expense").get("base")]
        ordered = sorted(data.get("rows") or [], key=lambda row: row.get("asset_rank") or 10**9)

    rows = [{"values": values(row), "is_woori": row.get("is_woori")} for row in ordered]
    label = SECTION_LABELS[section]
    if single:
        title = f"SBRate {label} 분기현황 - {data.get('base_label') or base}"
        compare_basis = data.get("yoy_compare_label") if section == "profitability" else data.get("compare_label")
        subtitle = f"출처: 금융감독원 금융통계정보시스템(FISIS) | 조회분기 {data.get('base_label') or base} | {delta_label} {compare_basis or '-'}"
    else:
        title = f"SBRate {label} 분기비교 - {data.get('base_label') or base} vs {data.get('compare_label') or compare}"
        subtitle = f"출처: 금융감독원 금융통계정보시스템(FISIS) | 기준분기 {data.get('base_label') or base} | 비교분기 {data.get('compare_label') or compare}"
    return _xlsx_bytes(title, subtitle, label, headers, kinds, rows)


def install_management_export_v2():
    app_module = sys.modules.get("app") or sys.modules.get("__main__")
    if app_module is None or not hasattr(app_module, "app"):
        return False
    if getattr(app_module, "_management_export_v2_installed", False):
        return True

    flask_app = app_module.app
    from flask import jsonify, request, send_file

    @flask_app.get("/api/management-export.xlsx")
    def management_export_v2():
        section = str(request.args.get("section") or "general").strip().lower()
        mode = str(request.args.get("mode") or "single").strip().lower()
        base = str(request.args.get("base") or "").strip()
        compare = str(request.args.get("compare") or "").strip()

        if section not in SECTION_LABELS:
            return jsonify({"ok": False, "error": "지원하지 않는 경영현황 구분입니다."}), 400
        if mode not in ("single", "compare"):
            return jsonify({"ok": False, "error": "지원하지 않는 Excel 조회 모드입니다."}), 400
        if base and not mr._valid_quarter(base):
            return jsonify({"ok": False, "error": "조회분기 형식이 올바르지 않습니다."}), 400
        if compare and not mr._valid_quarter(compare):
            return jsonify({"ok": False, "error": "비교분기 형식이 올바르지 않습니다."}), 400

        store = mr._load_store()
        available = sorted((store.get("quarters") or {}).keys(), key=mr._quarter_sort_key, reverse=True)
        if not base and available:
            base = available[0]
        if mode == "compare":
            if not compare and len(available) > 1:
                compare = available[1]
            if not compare or base == compare:
                return jsonify({"ok": False, "error": "분기비교 Excel은 서로 다른 기준분기와 비교분기가 필요합니다."}), 400
        if not base or base not in available:
            return jsonify({"ok": False, "error": "조회 가능한 분기 데이터가 없습니다."}), 404

        try:
            if section == "general":
                stream = _general_single(base) if mode == "single" else _general_compare(base, compare)
            else:
                stream = _intelligence_table(section, mode, base, compare)
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 404
        except Exception as exc:
            return jsonify({"ok": False, "error": f"{type(exc).__name__}: {exc}"}), 500

        label = SECTION_LABELS[section].replace("·", "_")
        filename = f"SBRate_{label}_{base}.xlsx" if mode == "single" else f"SBRate_{label}_{base}_vs_{compare}.xlsx"
        return send_file(
            stream,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename,
            max_age=0,
        )

    app_module._management_export_v2_installed = True
    print("Management export V2 installed: section/mode-aware Excel")
    return True
