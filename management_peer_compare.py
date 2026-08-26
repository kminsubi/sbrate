import re
import sys

import management_intelligence as mi
import management_report as mr


PEER_ORDER = [
    ("woori", "우리금융", ("우리금융",)),
    ("shinhan", "신한", ("신한",)),
    ("hana", "하나", ("하나",)),
    ("kb", "KB", ("kb",)),
]

PEER_FIELDS = [
    {"key": "total_assets", "label": "총자산", "unit": "억원", "category": "규모", "direction": "higher"},
    {"key": "total_loans", "label": "총대출", "unit": "억원", "category": "규모", "direction": "higher"},
    {"key": "deposits", "label": "총예수금", "unit": "억원", "category": "수신", "direction": "higher"},
    {"key": "time_deposits", "label": "정기예금", "unit": "억원", "category": "수신", "direction": "higher"},
    {"key": "bis_ratio", "label": "BIS비율", "unit": "%", "category": "건전성", "direction": "higher"},
    {"key": "delinquency_ratio", "label": "연체율", "unit": "%", "category": "건전성", "direction": "lower"},
    {"key": "npl_ratio", "label": "고정이하여신비율", "unit": "%", "category": "건전성", "direction": "lower"},
    {"key": "net_income", "label": "당기순이익", "unit": "억원", "category": "수익성", "direction": "higher"},
    {"key": "roa", "label": "ROA(산출)", "unit": "%", "category": "수익성", "direction": "higher"},
    {"key": "roe", "label": "ROE(산출)", "unit": "%", "category": "수익성", "direction": "higher"},
]


def _norm(value):
    text = str(value or "").strip().lower()
    for token in ("(주)", "㈜", "주식회사", "저축은행", "은행", " ", "-", "_"):
        text = text.replace(token, "")
    return text


def _peer_id(bank):
    value = _norm(bank)
    for peer_id, _, aliases in PEER_ORDER:
        if any(value == _norm(alias) for alias in aliases):
            return peer_id
    return None


def _prev_quarter(key):
    match = re.fullmatch(r"(\d{4})Q([1-4])", str(key or ""))
    if not match:
        return None
    year, quarter = int(match.group(1)), int(match.group(2))
    return f"{year - 1}Q4" if quarter == 1 else f"{year}Q{quarter - 1}"


def _prev_year_end(key):
    match = re.fullmatch(r"(\d{4})Q[1-4]", str(key or ""))
    return f"{int(match.group(1)) - 1}Q4" if match else None


def _yoy_quarter(key):
    match = re.fullmatch(r"(\d{4})Q([1-4])", str(key or ""))
    return f"{int(match.group(1)) - 1}Q{match.group(2)}" if match else None


def _number(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except Exception:
        return None


def _row_map(rows):
    result = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        peer_id = _peer_id(row.get("bank"))
        if peer_id:
            result[peer_id] = row
    return result


def _metric(row, key):
    return ((row or {}).get("metrics") or {}).get(key) or {}


def _pack(source, use_yoy=False):
    source = source or {}
    base = _number(source.get("base"))
    if use_yoy:
        compare = _number(source.get("yoy_compare"))
        delta = _number(source.get("yoy_delta"))
    else:
        compare = _number(source.get("compare"))
        delta = _number(source.get("delta"))
    return {
        "base": base,
        "compare": compare,
        "delta": delta,
        "comparable": source.get("comparable", True),
        "derived": bool(source.get("derived")),
    }


def _peer_ranks(peers, field_key, direction):
    values = []
    for peer in peers:
        value = _number(((peer.get("metrics") or {}).get(field_key) or {}).get("base"))
        if value is not None:
            values.append((peer["id"], value))
    values.sort(key=lambda item: (item[1], item[0]) if direction == "lower" else (-item[1], item[0]))
    return {peer_id: idx for idx, (peer_id, _) in enumerate(values, 1)}


def _peer_average(peers, field_key):
    values = [
        _number(((peer.get("metrics") or {}).get(field_key) or {}).get("base"))
        for peer in peers
    ]
    values = [value for value in values if value is not None]
    return round(sum(values) / len(values), 4) if values else None


def build_peer_compare(base=None, compare=None, mode="single"):
    mode = str(mode or "single").strip().lower()
    if mode not in ("single", "compare"):
        raise ValueError("지원하지 않는 Peer 비교 모드입니다.")

    store = mr._load_store()
    quarters = store.get("quarters") if isinstance(store.get("quarters"), dict) else {}
    available = sorted(quarters.keys(), key=mr._quarter_sort_key, reverse=True)
    if not available:
        return {"ok": False, "ready": False, "error": "FISIS 경영현황 분기 데이터가 없습니다."}

    base = base if base in quarters else available[0]
    prev_q = _prev_quarter(base)
    prev_year_end = _prev_year_end(base)
    yoy = _yoy_quarter(base)

    if mode == "compare":
        compare = compare if compare in quarters and compare != base else (available[1] if len(available) > 1 else None)
        if not compare or compare == base:
            raise ValueError("분기비교는 서로 다른 두 분기가 필요합니다.")
        general_compare = compare
        intel_compare = compare
    else:
        general_compare = prev_year_end if prev_year_end in quarters else (prev_q if prev_q in quarters else None)
        intel_compare = prev_q if prev_q in quarters else (available[1] if len(available) > 1 else None)

    if not general_compare or not intel_compare:
        return {"ok": False, "ready": False, "error": "Peer 비교에 필요한 비교분기 데이터가 없습니다."}

    general, error = mr._comparison_payload(base, general_compare)
    if error or not general:
        return {"ok": False, "ready": False, "error": error or "종합현황 데이터를 불러오지 못했습니다."}

    funding = mi.build_intelligence("funding", base=base, compare=intel_compare)
    soundness = mi.build_intelligence("soundness", base=base, compare=intel_compare)
    profitability = mi.build_intelligence("profitability", base=base, compare=intel_compare)

    maps = {
        "general": _row_map(general.get("rows")),
        "funding": _row_map(funding.get("rows")),
        "soundness": _row_map(soundness.get("rows")),
        "profitability": _row_map(profitability.get("rows")),
    }

    fields = []
    for item in PEER_FIELDS:
        field = dict(item)
        if mode == "compare":
            field["delta_label"] = "비교분기比"
            field["compare_quarter"] = compare
        elif item["key"] in ("total_assets", "total_loans"):
            field["delta_label"] = "전년말比"
            field["compare_quarter"] = prev_year_end if prev_year_end in quarters else general_compare
        elif item["key"] in ("net_income", "roa", "roe"):
            field["delta_label"] = "전년동기比"
            field["compare_quarter"] = yoy if yoy in quarters else None
        else:
            field["delta_label"] = "전분기比"
            field["compare_quarter"] = prev_q if prev_q in quarters else intel_compare
        fields.append(field)

    peers = []
    for peer_id, label, _ in PEER_ORDER:
        g = maps["general"].get(peer_id) or {}
        f = maps["funding"].get(peer_id) or {}
        s = maps["soundness"].get(peer_id) or {}
        p = maps["profitability"].get(peer_id) or {}
        use_yoy = mode == "single"
        peers.append({
            "id": peer_id,
            "label": label,
            "bank": g.get("bank") or f.get("bank") or s.get("bank") or p.get("bank") or label,
            "present": bool(g or f or s or p),
            "industry_asset_rank": g.get("rank") or s.get("asset_rank") or p.get("asset_rank"),
            "industry_deposit_rank": f.get("section_rank"),
            "metrics": {
                "total_assets": _pack(_metric(g, "total_assets")),
                "total_loans": _pack(_metric(g, "total_loans")),
                "deposits": _pack(_metric(f, "deposits")),
                "time_deposits": _pack(_metric(f, "time_deposits")),
                "bis_ratio": _pack(_metric(s, "bis_ratio")),
                "delinquency_ratio": _pack(_metric(s, "delinquency_ratio")),
                "npl_ratio": _pack(_metric(s, "npl_ratio_effective")),
                "net_income": _pack(_metric(p, "net_income"), use_yoy=use_yoy),
                "roa": _pack(_metric(p, "roa"), use_yoy=use_yoy),
                "roe": _pack(_metric(p, "roe"), use_yoy=use_yoy),
            },
        })

    field_directions = {item["key"]: item["direction"] for item in PEER_FIELDS}
    rank_maps = {
        key: _peer_ranks(peers, key, direction)
        for key, direction in field_directions.items()
    }
    averages = {item["key"]: _peer_average(peers, item["key"]) for item in PEER_FIELDS}
    for peer in peers:
        peer["peer_ranks"] = {key: rank_map.get(peer["id"]) for key, rank_map in rank_maps.items()}

    woori = next((peer for peer in peers if peer["id"] == "woori"), None)
    missing = [peer["label"] for peer in peers if not peer.get("present")]

    return {
        "ok": True,
        "ready": len(missing) == 0,
        "mode": mode,
        "source": "금융감독원 금융통계정보시스템(FISIS)",
        "base": base,
        "base_label": general.get("base_label") or mr._quarter_label(base),
        "as_of": (quarters.get(base) or {}).get("as_of"),
        "compare": compare if mode == "compare" else None,
        "compare_label": (quarters.get(compare) or {}).get("label") if mode == "compare" and compare else None,
        "previous_quarter": prev_q if prev_q in quarters else None,
        "previous_year_end": prev_year_end if prev_year_end in quarters else None,
        "yoy_quarter": yoy if yoy in quarters else None,
        "peer_order": [peer_id for peer_id, _, _ in PEER_ORDER],
        "peer_count": len(peers),
        "missing_peers": missing,
        "fields": fields,
        "peers": peers,
        "peer_average": averages,
        "woori": woori,
        "woori_peer_ranks": (woori or {}).get("peer_ranks") or {},
        "notes": {
            "comparison_basis": "단일분기에서는 규모는 전년말, 수신·건전성은 전분기, 손익·ROA·ROE는 전년동기 기준으로 비교합니다." if mode == "single" else "분기비교에서는 선택한 기준분기와 비교분기를 직접 비교합니다.",
            "roa_roe": (profitability.get("notes") or {}).get("roa_roe_basis") or "ROA·ROE는 FISIS 분기 원천자료를 이용한 산출 참고지표입니다.",
            "peer_scope": "4대 금융지주 계열 저축은행: 우리금융·신한·하나·KB",
        },
    }


def _peer_excel(data):
    import management_export_v2 as export_v2

    headers = ["저축은행", "업권 총자산순위", "업권 예수금순위"]
    kinds = ["text", "int", "int"]
    for field in data.get("fields") or []:
        headers.extend([f"{field['label']}({field['unit']})", field.get("delta_label") or "증감"])
        if field.get("unit") == "%":
            kinds.extend(["ratio", "delta_ratio"])
        else:
            kinds.extend(["amount", "delta_amount"])

    rows = []
    for peer in data.get("peers") or []:
        values = [peer.get("label"), peer.get("industry_asset_rank"), peer.get("industry_deposit_rank")]
        for field in data.get("fields") or []:
            pack = (peer.get("metrics") or {}).get(field["key"]) or {}
            values.extend([pack.get("base"), pack.get("delta")])
        rows.append({"values": values, "is_woori": peer.get("id") == "woori"})

    if data.get("mode") == "compare":
        title = f"SBRate 4대금융 비교 분기비교 - {data.get('base_label') or data.get('base')} vs {data.get('compare_label') or data.get('compare')}"
        subtitle = f"출처: FISIS | 금융사 순서: 우리금융 → 신한 → 하나 → KB | 기준분기 {data.get('base') or '-'} | 비교분기 {data.get('compare') or '-'}"
    else:
        title = f"SBRate 4대금융 비교 분기현황 - {data.get('base_label') or data.get('base')}"
        subtitle = (
            f"출처: FISIS | 금융사 순서: 우리금융 → 신한 → 하나 → KB | "
            f"규모 전년말比 {data.get('previous_year_end') or '-'} · 수신/건전성 전분기比 {data.get('previous_quarter') or '-'} · 손익/ROA/ROE 전년동기比 {data.get('yoy_quarter') or '-'}"
        )
    return export_v2._xlsx_bytes(title, subtitle, "4대금융 비교", headers, kinds, rows)


def install_management_peer_compare():
    app_module = sys.modules.get("app") or sys.modules.get("__main__")
    if app_module is None or not hasattr(app_module, "app"):
        return False
    if getattr(app_module, "_management_peer_compare_installed", False):
        return True

    flask_app = app_module.app
    from flask import jsonify, request, send_file

    @flask_app.get("/api/management-peer")
    def management_peer_api():
        try:
            return jsonify(build_peer_compare(
                base=request.args.get("base"),
                compare=request.args.get("compare"),
                mode=request.args.get("mode") or "single",
            ))
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        except Exception as exc:
            return jsonify({"ok": False, "error": f"{type(exc).__name__}: {exc}"}), 500

    @flask_app.get("/api/management-peer/export.xlsx")
    def management_peer_export():
        try:
            data = build_peer_compare(
                base=request.args.get("base"),
                compare=request.args.get("compare"),
                mode=request.args.get("mode") or "single",
            )
            if not data.get("ok"):
                return jsonify(data), 404
            stream = _peer_excel(data)
            base_key = data.get("base") or "latest"
            filename = (
                f"SBRate_4대금융_비교_{base_key}_vs_{data.get('compare')}.xlsx"
                if data.get("mode") == "compare"
                else f"SBRate_4대금융_비교_{base_key}.xlsx"
            )
            return send_file(
                stream,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                as_attachment=True,
                download_name=filename,
                max_age=0,
            )
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        except Exception as exc:
            return jsonify({"ok": False, "error": f"{type(exc).__name__}: {exc}"}), 500

    app_module._management_peer_compare_installed = True
    print("Management peer compare API installed: Woori/Shinhan/Hana/KB")
    return True
