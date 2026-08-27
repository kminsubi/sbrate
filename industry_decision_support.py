import math
import re
import sys
from datetime import datetime

import fisis_management as fm
import management_report as mr


ASSET_VERSION = "20260827ds1"
TREND_FIELDS = [
    ("total_assets", "총자산", "억원", "higher"),
    ("total_loans", "총대출", "억원", "higher"),
    ("bis_ratio", "BIS비율", "%", "higher"),
    ("delinquency_ratio", "연체율", "%", "lower"),
    ("npl_ratio", "고정이하여신비율", "%", "lower"),
    ("net_income", "당기순이익", "억원", "higher"),
]


def _app_module():
    return sys.modules.get("app") or sys.modules.get("__main__")


def _num(value):
    if value is None or value == "":
        return None
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except Exception:
        return None


def _quarter_parts(key):
    match = re.fullmatch(r"(\d{4})Q([1-4])", str(key or ""))
    return (int(match.group(1)), int(match.group(2))) if match else None


def _prev_quarter(key):
    parts = _quarter_parts(key)
    if not parts:
        return None
    year, quarter = parts
    return f"{year - 1}Q4" if quarter == 1 else f"{year}Q{quarter - 1}"


def _prev_year_end(key):
    parts = _quarter_parts(key)
    return f"{parts[0] - 1}Q4" if parts else None


def _yoy_quarter(key):
    parts = _quarter_parts(key)
    return f"{parts[0] - 1}Q{parts[1]}" if parts else None


def _display_bank(value):
    text = str(value or "").strip()
    text = re.sub(r"\s*저축은행\s*$", "", text)
    return text or "-"


def _bank_key(value):
    text = str(value or "").strip().lower()
    for token in ("(주)", "㈜", "주식회사", "저축은행", "은행", " ", "-", "_"):
        text = text.replace(token, "")
    aliases = {"kb": "케이비", "국민": "케이비"}
    return aliases.get(text, text)


def _find_bank(rows, name):
    target = _bank_key(name)
    if not target:
        return None
    exact = [row for row in rows or [] if _bank_key(row.get("bank")) == target]
    if exact:
        return exact[0]
    partial = [
        row for row in rows or []
        if target in _bank_key(row.get("bank")) or _bank_key(row.get("bank")) in target
    ]
    return partial[0] if partial else None


def _latest_text(rows, keys):
    values = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        for key in keys:
            value = str(row.get(key) or "").strip()
            if value:
                values.append(value)
    return max(values) if values else None


def _positive_rate_count(rows):
    count = 0
    for row in rows or []:
        rates = row.get("rates") if isinstance(row, dict) else None
        if isinstance(rates, dict) and any((_num(value) or 0) > 0 for value in rates.values()):
            count += 1
    return count


def _quality_status():
    app_module = _app_module()
    store = mr._load_store()
    quarters = store.get("quarters") if isinstance(store.get("quarters"), dict) else {}
    available = sorted(quarters.keys(), key=mr._quarter_sort_key, reverse=True)
    latest = available[0] if available else None
    latest_meta = quarters.get(latest) if latest and isinstance(quarters.get(latest), dict) else {}
    expected = int(store.get("active_company_count") or 0)
    covered = int(latest_meta.get("asset_bank_count") or latest_meta.get("bank_count") or 0)
    minimum = int(store.get("minimum_quarter_asset_count") or 0)
    refresh = fm.get_refresh_state()

    fisis_state = "normal" if latest and covered and covered >= max(1, minimum) else "warning"
    if not latest or covered == 0:
        fisis_state = "error"

    sources = [{
        "key": "fisis",
        "label": "FISIS",
        "state": fisis_state,
        "headline": f"{mr._quarter_label(latest) if latest else '-'} · {covered}/{expected or covered}개사",
        "detail": f"총자산 공시 커버리지 {covered}개사 · 승격기준 {minimum or '-'}개사",
        "updated_at": store.get("updated_at"),
        "refreshing": bool(refresh.get("running")),
        "error_count": len(store.get("last_errors") or []),
    }]

    if app_module is not None:
        try:
            rates = app_module.load_rates() if callable(getattr(app_module, "load_rates", None)) else []
            rate_banks = {str(row.get("bank") or "").strip() for row in rates if isinstance(row, dict) and row.get("bank")}
            valid12 = sum(1 for row in rates if isinstance(row, dict) and (_num(row.get("top_12m")) or 0) > 0)
            rate_state = "normal" if len(rate_banks) >= 60 and valid12 >= 60 else "warning"
            if not rates:
                rate_state = "error"
            sources.append({
                "key": "deposit",
                "label": "정기예금",
                "state": rate_state,
                "headline": f"{len(rate_banks)}개사 · {len(rates):,}상품",
                "detail": f"12개월 유효금리 {valid12:,}상품",
                "updated_at": _latest_text(rates, ("reg_date", "updated_at", "collected_at")),
            })
        except Exception as exc:
            sources.append({"key": "deposit", "label": "정기예금", "state": "error", "headline": "확인 실패", "detail": str(exc)[:120]})

        for key, label, file_attr in (("isa", "ISA", "ISA_DATA_FILE"), ("irp", "IRP", "IRP_DATA_FILE")):
            try:
                file_path = getattr(app_module, file_attr, None)
                loader = getattr(app_module, "load_pension_rate_file", None)
                rows = loader(file_path) if callable(loader) and file_path else []
                banks = {str(row.get("bank") or row.get("bank_name") or "").strip() for row in rows if isinstance(row, dict)}
                banks.discard("")
                valid = _positive_rate_count(rows)
                state = "normal" if len(banks) >= 8 and valid >= 8 else "warning"
                if not rows:
                    state = "error"
                sources.append({
                    "key": key,
                    "label": label,
                    "state": state,
                    "headline": f"{len(banks)}개사 · 금리확인 {valid}개사",
                    "detail": f"공식/보유 데이터 {len(rows)}건",
                    "updated_at": _latest_text(rows, ("updated_at", "collected_at", "reference_date", "disclosure_date")),
                })
            except Exception as exc:
                sources.append({"key": key, "label": label, "state": "error", "headline": "확인 실패", "detail": str(exc)[:120]})

    states = [item.get("state") for item in sources]
    overall = "error" if "error" in states else "warning" if "warning" in states else "normal"
    labels = {"normal": "데이터 정상", "warning": "일부 확인 필요", "error": "데이터 오류"}
    return {
        "state": overall,
        "label": labels[overall],
        "latest_quarter": latest,
        "latest_label": mr._quarter_label(latest) if latest else None,
        "bank_coverage": covered,
        "active_company_count": expected or covered,
        "sources": sources,
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def _delta_item(key, title, metric, basis, unit, semantic=None, priority=50):
    delta = _num((metric or {}).get("delta"))
    base = _num((metric or {}).get("base"))
    compare = _num((metric or {}).get("compare"))
    if delta is None:
        return None
    movement = "up" if delta > 0 else "down" if delta < 0 else "flat"
    if semantic is None:
        semantic = "good" if delta > 0 else "bad" if delta < 0 else "neutral"
    return {
        "key": key,
        "title": title,
        "base": base,
        "compare": compare,
        "delta": delta,
        "unit": unit,
        "basis": basis,
        "movement": movement,
        "semantic": semantic,
        "priority": priority,
    }


def _brief_single(base, quarters):
    prev_q = _prev_quarter(base)
    year_end = _prev_year_end(base)
    yoy = _yoy_quarter(base)
    prev_data = year_data = yoy_data = None
    if prev_q in quarters:
        prev_data, _ = mr._comparison_payload(base, prev_q)
    if year_end in quarters:
        year_data, _ = mr._comparison_payload(base, year_end)
    if yoy in quarters:
        yoy_data, _ = mr._comparison_payload(base, yoy)

    items = []
    prev_w = (prev_data or {}).get("woori") or {}
    rank_change = _num(prev_w.get("rank_change"))
    if rank_change is not None:
        items.append({
            "key": "asset_rank",
            "title": "총자산 순위",
            "base": prev_w.get("rank"),
            "compare": prev_w.get("compare_rank"),
            "delta": rank_change,
            "unit": "위",
            "basis": f"전분기比 {prev_q}",
            "movement": "up" if rank_change > 0 else "down" if rank_change < 0 else "flat",
            "semantic": "good" if rank_change > 0 else "bad" if rank_change < 0 else "neutral",
            "priority": 100,
            "rank_metric": True,
        })

    year_metrics = ((year_data or {}).get("woori") or {}).get("metrics") or {}
    prev_metrics = prev_w.get("metrics") or {}
    yoy_metrics = ((yoy_data or {}).get("woori") or {}).get("metrics") or {}
    for item in (
        _delta_item("total_assets", "총자산", year_metrics.get("total_assets"), f"전년말比 {year_end}", "억원", priority=90),
        _delta_item("total_loans", "총대출", year_metrics.get("total_loans"), f"전년말比 {year_end}", "억원", priority=70),
        _delta_item("bis_ratio", "BIS비율", prev_metrics.get("bis_ratio"), f"전분기比 {prev_q}", "%p", priority=85),
        _delta_item(
            "delinquency_ratio", "연체율", prev_metrics.get("delinquency_ratio"), f"전분기比 {prev_q}", "%p",
            semantic=("good" if _num((prev_metrics.get("delinquency_ratio") or {}).get("delta")) is not None and _num((prev_metrics.get("delinquency_ratio") or {}).get("delta")) < 0 else "bad"),
            priority=95,
        ),
        _delta_item("net_income", "당기순이익", yoy_metrics.get("net_income"), f"전년동기比 {yoy}", "억원", priority=80),
    ):
        if item:
            items.append(item)

    try:
        import management_peer_compare as mpc
        current_peer = mpc.build_peer_compare(base=base, mode="single")
        previous_peer = mpc.build_peer_compare(base=prev_q, mode="single") if prev_q in quarters else None
        if current_peer.get("ok") and previous_peer and previous_peer.get("ok"):
            now_ranks = current_peer.get("woori_peer_ranks") or {}
            old_ranks = previous_peer.get("woori_peer_ranks") or {}
            for field, title, priority in (("total_assets", "4대금융 자산 Peer", 65), ("roe", "4대금융 ROE Peer", 75)):
                now_rank, old_rank = now_ranks.get(field), old_ranks.get(field)
                if now_rank and old_rank and now_rank != old_rank:
                    change = old_rank - now_rank
                    items.append({
                        "key": f"peer_{field}", "title": title, "base": now_rank, "compare": old_rank,
                        "delta": change, "unit": "위", "basis": f"전분기 Peer {prev_q}",
                        "movement": "up" if change > 0 else "down", "semantic": "good" if change > 0 else "bad",
                        "priority": priority, "rank_metric": True,
                    })
    except Exception:
        pass

    return items


def _brief_compare(base, compare):
    data, error = mr._comparison_payload(base, compare)
    if error or not data:
        return []
    w = data.get("woori") or {}
    metrics = w.get("metrics") or {}
    items = []
    rank_change = _num(w.get("rank_change"))
    if rank_change is not None:
        items.append({
            "key": "asset_rank", "title": "총자산 순위", "base": w.get("rank"), "compare": w.get("compare_rank"),
            "delta": rank_change, "unit": "위", "basis": f"비교분기比 {compare}",
            "movement": "up" if rank_change > 0 else "down" if rank_change < 0 else "flat",
            "semantic": "good" if rank_change > 0 else "bad" if rank_change < 0 else "neutral",
            "priority": 100, "rank_metric": True,
        })
    for key, title, unit, priority in (
        ("total_assets", "총자산", "억원", 90),
        ("total_loans", "총대출", "억원", 70),
        ("bis_ratio", "BIS비율", "%p", 85),
        ("delinquency_ratio", "연체율", "%p", 95),
        ("net_income", "당기순이익", "억원", 80),
    ):
        metric = metrics.get(key) or {}
        if metric.get("comparable") is False:
            continue
        delta = _num(metric.get("delta"))
        semantic = None
        if key == "delinquency_ratio" and delta is not None:
            semantic = "good" if delta < 0 else "bad" if delta > 0 else "neutral"
        item = _delta_item(key, title, metric, f"비교분기比 {compare}", unit, semantic=semantic, priority=priority)
        if item:
            items.append(item)
    return items


def _change_brief(base=None, compare=None, mode="single"):
    store = mr._load_store()
    quarters = store.get("quarters") if isinstance(store.get("quarters"), dict) else {}
    available = sorted(quarters.keys(), key=mr._quarter_sort_key, reverse=True)
    if not available:
        return {"ready": False, "items": [], "error": "FISIS 분기 데이터가 없습니다."}
    base = base if base in quarters else available[0]
    mode = "compare" if str(mode or "single").lower() == "compare" else "single"
    if mode == "compare":
        compare = compare if compare in quarters and compare != base else (available[1] if len(available) > 1 else None)
        items = _brief_compare(base, compare) if compare else []
        heading = "선택분기 핵심 변화"
    else:
        items = _brief_single(base, quarters)
        heading = "이번 분기 핵심 변화"
    changed = [item for item in items if abs(_num(item.get("delta")) or 0) > 0.0000001]
    changed.sort(key=lambda item: (-int(item.get("priority") or 0), str(item.get("key") or "")))
    if not changed:
        changed = sorted(items, key=lambda item: -int(item.get("priority") or 0))[:3]
    return {
        "ready": True,
        "mode": mode,
        "base": base,
        "base_label": (quarters.get(base) or {}).get("label") or mr._quarter_label(base),
        "compare": compare if mode == "compare" else None,
        "heading": heading,
        "items": changed[:5],
    }


def build_industry_overview(base=None, compare=None, mode="single"):
    return {
        "ok": True,
        "quality": _quality_status(),
        "brief": _change_brief(base=base, compare=compare, mode=mode),
    }


def build_bank_detail(bank, base=None):
    store = mr._load_store()
    quarters = store.get("quarters") if isinstance(store.get("quarters"), dict) else {}
    available = sorted(quarters.keys(), key=mr._quarter_sort_key, reverse=True)
    if not available:
        return {"ok": False, "error": "FISIS 분기 데이터가 없습니다."}
    base = base if base in quarters else available[0]
    base_index = available.index(base)
    eligible = available[base_index:]
    history_keys = list(reversed(eligible[:8]))

    selected_rows, selected_meta = mr._rows_for_quarter(store, base)
    target = _find_bank(selected_rows, bank)
    if target is None:
        for quarter in eligible:
            rows, _ = mr._rows_for_quarter(store, quarter)
            target = _find_bank(rows, bank)
            if target is not None:
                break
    if target is None:
        return {"ok": False, "error": f"'{bank}' 저축은행을 찾을 수 없습니다."}

    canonical = target.get("bank") or bank
    history = []
    for quarter in history_keys:
        rows, meta = mr._rows_for_quarter(store, quarter)
        row = _find_bank(rows, canonical)
        if not row:
            continue
        rank_map = mr._rank_map(rows)
        point = {
            "quarter": quarter,
            "label": meta.get("label") or mr._quarter_label(quarter),
            "as_of": meta.get("as_of"),
            "rank": rank_map.get(mr._bank_key(row.get("bank"))),
            "metrics": {key: _num(row.get(key)) for key, _, _, _ in TREND_FIELDS},
        }
        history.append(point)

    base_rows, base_meta = mr._rows_for_quarter(store, base)
    current = _find_bank(base_rows, canonical)
    if not current and history:
        current = _find_bank(base_rows, bank)
    rank_map = mr._rank_map(base_rows)
    woori = next((row for row in base_rows if mr._is_woori(row.get("bank"))), None)
    current_metrics = {key: _num((current or {}).get(key)) for key, _, _, _ in TREND_FIELDS}
    woori_metrics = {key: _num((woori or {}).get(key)) for key, _, _, _ in TREND_FIELDS}
    gaps = {
        key: (round(current_metrics[key] - woori_metrics[key], 4) if current_metrics[key] is not None and woori_metrics[key] is not None else None)
        for key, _, _, _ in TREND_FIELDS
    }

    return {
        "ok": True,
        "bank": current.get("bank") if current else canonical,
        "display_bank": _display_bank(current.get("bank") if current else canonical),
        "region": (current or {}).get("region") or "-",
        "finance_cd": (current or {}).get("finance_cd"),
        "base": base,
        "base_label": base_meta.get("label") or mr._quarter_label(base),
        "as_of": base_meta.get("as_of"),
        "asset_rank": rank_map.get(mr._bank_key((current or {}).get("bank"))),
        "bank_count": len(base_rows),
        "is_woori": mr._is_woori((current or {}).get("bank")),
        "current": current_metrics,
        "woori": woori_metrics,
        "gap_vs_woori": gaps,
        "fields": [
            {"key": key, "label": label, "unit": unit, "direction": direction}
            for key, label, unit, direction in TREND_FIELDS
        ],
        "history": history,
        "history_count": len(history),
        "source": store.get("source_name") or "금융감독원 금융통계정보시스템(FISIS)",
        "store_updated_at": store.get("updated_at"),
        "note": "당기순이익은 FISIS 공시 누적값이므로 분기 간 단순 증감 해석에 유의해야 합니다.",
    }


def install_industry_decision_support():
    app_module = _app_module()
    if app_module is None or not hasattr(app_module, "app"):
        return False
    if getattr(app_module, "_industry_decision_support_installed", False):
        return True

    flask_app = app_module.app
    from flask import jsonify, request

    @flask_app.get("/api/industry-overview")
    def industry_overview_api():
        try:
            return jsonify(build_industry_overview(
                base=str(request.args.get("base") or "").strip() or None,
                compare=str(request.args.get("compare") or "").strip() or None,
                mode=str(request.args.get("mode") or "single").strip(),
            ))
        except Exception as exc:
            return jsonify({"ok": False, "error": f"{type(exc).__name__}: {exc}"}), 500

    @flask_app.get("/api/industry-bank-detail")
    def industry_bank_detail_api():
        bank = str(request.args.get("bank") or "").strip()
        if not bank:
            return jsonify({"ok": False, "error": "저축은행명이 필요합니다."}), 400
        try:
            result = build_bank_detail(bank, base=str(request.args.get("base") or "").strip() or None)
            return jsonify(result), (200 if result.get("ok") else 404)
        except Exception as exc:
            return jsonify({"ok": False, "error": f"{type(exc).__name__}: {exc}"}), 500

    @flask_app.after_request
    def industry_decision_support_assets(response):
        try:
            if (
                request.path in ("/", "/mobile")
                and response.status_code == 200
                and "text/html" in str(response.content_type or "")
            ):
                html = response.get_data(as_text=True)
                if "industry_decision_support.css" not in html:
                    html = html.replace(
                        "</head>",
                        f'<link rel="stylesheet" href="/static/css/industry_decision_support.css?v={ASSET_VERSION}">\n</head>',
                        1,
                    )
                if "industry_decision_support.js" not in html:
                    html = html.replace(
                        "</body>",
                        f'<script src="/static/js/industry_decision_support.js?v={ASSET_VERSION}"></script>\n</body>',
                        1,
                    )
                response.set_data(html)
                response.headers.pop("Content-Length", None)
        except Exception as exc:
            print("Industry decision support asset error:", exc)
        return response

    app_module._industry_decision_support_installed = True
    print("Industry decision support installed: trust / changes / bank detail")
    return True
