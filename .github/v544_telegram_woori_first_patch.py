from pathlib import Path

APP = Path('app.py')
text = APP.read_text(encoding='utf-8')

old_pension = '''    def pension_lines(label, data):
        top = data["top"] or {}
        w = data["woori"] or {}
        top_rate = safe_float(top.get("rate")) or 0
        wr = safe_float(w.get("rate")) if w else None
        lines = [
            f"📌 {label} 12개월",
            f"🥇 {top.get('bank','-')} {top_rate:.2f}%"
        ]
        if w:
            product = telegram_product_name(w)
            gap = (wr or 0) - top_rate
            lines.extend([
                f"🔵 우리금융 {wr:.2f}% · {data['woori_rank']}위 / {data['count']}개",
                f"상품 : {product}",
                f"최고 대비 : {gap:+.2f}%p" if gap >= 0 else f"최고 대비 : ▲{abs(gap):.2f}%p",
                f"공시일 : {w.get('disclosure_date') or '미확인'}"
            ])
        else:
            lines.append("🔵 우리금융 : 유효금리 미확인")
        return lines
'''

new_pension = '''    def pension_lines(label, data):
        top = data["top"] or {}
        w = data["woori"] or {}
        top_rate = safe_float(top.get("rate")) or 0
        wr = safe_float(w.get("rate")) if w else None
        lines = [f"📌 {label} 12개월"]
        if w:
            product = telegram_product_name(w)
            gap = (wr or 0) - top_rate
            lines.extend([
                f"🔵 우리금융 {wr:.2f}% · {data['woori_rank']}위 / {data['count']}개",
                f"상품 : {product}",
                f"최고 대비 : {gap:+.2f}%p" if gap >= 0 else f"최고 대비 : ▲{abs(gap):.2f}%p",
                f"공시일 : {w.get('disclosure_date') or '미확인'}"
            ])
        else:
            lines.append("🔵 우리금융 : 유효금리 미확인")
        lines.append(f"🥇 {top.get('bank','-')} {top_rate:.2f}%")
        return lines
'''

if old_pension not in text:
    raise SystemExit('pension_lines target not found')
text = text.replace(old_pension, new_pension, 1)

old_core = '''    lines = [
        "☀️ SBRate Morning Brief",
        f"데이터 업데이트 기준 : {telegram_read_update_time()} KST",
        "",
        "────────────",
        "📌 오늘의 핵심",
        "────────────",
        f"시장 최고 : {dep_top_rate:.2f}%",
        f"시장 평균 : {dep_avg:.2f}%",
    ]
'''

new_core = '''    lines = [
        "☀️ SBRate Morning Brief",
        f"데이터 업데이트 기준 : {telegram_read_update_time()} KST",
        "",
        "────────────",
        "📌 오늘의 핵심",
        "────────────",
    ]
'''

if old_core not in text:
    raise SystemExit('core header target not found')
text = text.replace(old_core, new_core, 1)

old_after_woori = '''        lines.extend([
            f"우리금융 : {dep_woori_rate:.2f}% · {telegram_change_text(dep_woori_change)}",
            f"시장 순위 : {dep['woori_rank']}위 / {dep['count']}개 · {rank_change_text}",
            f"대표상품 : {telegram_product_name(dep['woori'])}",
            f"시장 최고 대비 : {dep_gap:+.2f}%p" if dep_gap is not None and dep_gap >= 0 else f"시장 최고 대비 : ▲{abs(dep_gap or 0):.2f}%p",
            f"Gap 전일비 : {gap_change_text}",
        ])

    lines.extend([
        f"전일 변동 : 상승 {changes.get('up_count',0)} / 하락 {changes.get('down_count',0)}",
'''

new_after_woori = '''        lines.extend([
            f"우리금융 : {dep_woori_rate:.2f}% · {telegram_change_text(dep_woori_change)}",
            f"시장 순위 : {dep['woori_rank']}위 / {dep['count']}개 · {rank_change_text}",
            f"대표상품 : {telegram_product_name(dep['woori'])}",
            f"시장 최고 대비 : {dep_gap:+.2f}%p" if dep_gap is not None and dep_gap >= 0 else f"시장 최고 대비 : ▲{abs(dep_gap or 0):.2f}%p",
            f"Gap 전일비 : {gap_change_text}",
        ])
    else:
        lines.append("우리금융 : 유효금리 미확인")

    lines.extend([
        f"시장 최고 : {dep_top_rate:.2f}%",
        f"시장 평균 : {dep_avg:.2f}%",
        f"전일 변동 : 상승 {changes.get('up_count',0)} / 하락 {changes.get('down_count',0)}",
'''

if old_after_woori not in text:
    raise SystemExit('core Woori target not found')
text = text.replace(old_after_woori, new_after_woori, 1)

APP.write_text(text.rstrip() + '\n', encoding='utf-8')

# validation assertions
final = APP.read_text(encoding='utf-8')
assert 'lines = [f"📌 {label} 12개월"]' in final
assert 'lines.append(f"🥇 {top.get(\'bank\',\'-\')} {top_rate:.2f}%")' in final
assert final.index('f"우리금융 : {dep_woori_rate:.2f}%') < final.index('f"시장 최고 : {dep_top_rate:.2f}%')
print('V5.44 Telegram Woori-first patch applied')
