(() => {
  'use strict';

  const SECTION_LABELS = {
    general: '종합현황',
    funding: '수신·조달',
    soundness: '건전성',
    profitability: '수익성',
  };
  let activeSection = 'general';
  let loadSeq = 0;

  const esc = (value) => String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');

  function num(value) {
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  }

  function decimals(value, unit) {
    const n = Math.abs(Number(value));
    if (unit === '억원') return n >= 100 ? 0 : n >= 10 ? 1 : 2;
    if (unit === '%') return 2;
    return 2;
  }

  function valueText(value, unit = '', digits = null) {
    const n = num(value);
    if (n === null) return '-';
    const d = digits === null ? decimals(n, unit) : digits;
    const text = n.toLocaleString('ko-KR', { minimumFractionDigits: d, maximumFractionDigits: d });
    return unit ? `${text}${unit}` : text;
  }

  function deltaHtml(value, unit = '', digits = null) {
    const n = num(value);
    if (n === null || Math.abs(n) < 0.0000001) return '<span class="mi-delta flat">-</span>';
    const d = digits === null ? decimals(n, unit) : digits;
    const body = Math.abs(n).toLocaleString('ko-KR', { minimumFractionDigits: d, maximumFractionDigits: d });
    if (n > 0) return `<span class="mi-delta up">+${body}${unit}</span>`;
    return `<span class="mi-delta down">▲${body}${unit}</span>`;
  }

  function rankDeltaHtml(value) {
    const n = num(value);
    if (n === null || n === 0) return '<span class="mi-delta flat">-</span>';
    if (n > 0) return `<span class="mi-delta up">+${Math.abs(n)}위</span>`;
    return `<span class="mi-delta down">▲${Math.abs(n)}위</span>`;
  }

  function metric(row, key) {
    return row?.metrics?.[key] || {};
  }

  function isCompareMode() {
    return !!document.querySelector('#management-report-modal [data-mr-mode="compare"].is-active');
  }

  function compareLabel() {
    return isCompareMode() ? '비교분기比' : '전분기比';
  }

  function card(label, value, sub = '', primary = false) {
    return `
      <div class="mi-card${primary ? ' mi-card-primary' : ''}">
        <div class="mi-card-label">${esc(label)}</div>
        <div class="mi-card-value">${value}</div>
        ${sub ? `<div class="mi-card-sub">${sub}</div>` : ''}
      </div>`;
  }

  function block(title, meta, body, extraClass = '') {
    return `
      <section class="mi-block ${extraClass}">
        <div class="mi-block-head">
          <div class="mi-block-title">${esc(title)}</div>
          <div class="mi-block-meta">${esc(meta || '')}</div>
        </div>
        ${body}
      </section>`;
  }

  function renderWarmup(data) {
    return `
      <div class="mi-warmup">
        <strong>FISIS 확장 경영지표를 최초 수집 중입니다.</strong><br>
        총예수금·정기예금·유동성·ROA/ROE 등 신규 지표를 79개 저축은행 기준으로 채우고 있습니다.<br>
        기존 종합현황은 정상 이용할 수 있으며, 수집이 끝나면 이 화면도 자동으로 표시됩니다.<br>
        <span style="font-size:10px;color:#8b98aa">현재 캐시 갱신: ${esc(data?.updated_at || '-')}</span>
      </div>`;
  }

  function fundingTable(data) {
    const rows = [...(data.rows || [])].sort((a, b) => (a.section_rank || 999) - (b.section_rank || 999));
    const deltaLabel = compareLabel();
    const body = rows.map(row => {
      const dep = metric(row, 'deposits');
      const td = metric(row, 'time_deposits');
      const mix = metric(row, 'time_deposit_mix');
      const personal = metric(row, 'personal_deposits');
      const corp = metric(row, 'corporate_deposits');
      const ldr = metric(row, 'simple_loan_deposit_ratio');
      return `
        <tr class="${row.is_woori ? 'mi-woori' : ''}">
          <td>${row.section_rank ?? '-'}</td>
          <td>${esc(row.bank || '-')}</td>
          <td>${esc(row.region || '-')}</td>
          <td>${valueText(dep.base, '억원')}</td>
          <td>${deltaHtml(dep.delta, '억원')}</td>
          <td>${valueText(td.base, '억원')}</td>
          <td>${deltaHtml(td.delta, '억원')}</td>
          <td>${valueText(mix.base, '%')}</td>
          <td>${valueText(personal.base, '억원')}</td>
          <td>${valueText(corp.base, '억원')}</td>
          <td>${valueText(ldr.base, '%')}</td>
        </tr>`;
    }).join('');
    return `
      <div class="mi-table-wrap">
        <table class="mi-table">
          <thead><tr>
            <th>예수금순위</th><th>저축은행</th><th>지역</th><th>총예수금</th><th>${deltaLabel}</th>
            <th>정기예금</th><th>${deltaLabel}</th><th>정기예금비중</th><th>개인예수금</th><th>기업예수금</th><th>단순예대율</th>
          </tr></thead>
          <tbody>${body}</tbody>
        </table>
      </div>`;
  }

  function renderFunding(data) {
    const w = data.woori || {};
    const market = data.current_market || {};
    const mw = market.woori || {};
    const dep = metric(w, 'deposits');
    const td = metric(w, 'time_deposits');
    const mix = metric(w, 'time_deposit_mix');
    const share = metric(w, 'deposit_market_share');
    const personal = metric(w, 'personal_deposits');
    const corp = metric(w, 'corporate_deposits');
    const sole = metric(w, 'sole_prop_deposits');
    const ldr = metric(w, 'simple_loan_deposit_ratio');
    const rankSub = `${compareLabel} ${rankDeltaHtml(w.section_rank_change)}`;

    const current = block(
      '현재 시장',
      `${market.updated_at || '-'} · 정기예금 12개월 은행별 최고금리`,
      `<div class="mi-card-grid">
        ${card('우리금융 현재금리', valueText(mw.rate, '%'), `시장 ${mw.rank ?? '-'}위`, true)}
        ${card('시장 평균금리', valueText(market.market_average, '%'))}
        ${card('시장 최고금리', valueText(market.market_max, '%'))}
        ${card('금리 비교 은행', `${market.bank_count ?? '-'}개사`)}
        ${card('FISIS 실적 기준', esc(data.base_label || '-'), data.as_of ? `${esc(data.as_of)} 기준` : '')}
      </div>`
    );

    const confirmed = block(
      `확정 실적 · ${data.base_label || ''}`,
      `${data.as_of || '-'} 기준 · FISIS`,
      `<div class="mi-card-grid">
        ${card('총예수금 순위', `${w.section_rank ?? '-'}위`, rankSub, true)}
        ${card('총예수금', valueText(dep.base, '억원'), `${compareLabel} ${deltaHtml(dep.delta, '억원')}`)}
        ${card('정기예금', valueText(td.base, '억원'), `${compareLabel} ${deltaHtml(td.delta, '억원')}`)}
        ${card('정기예금 비중', valueText(mix.base, '%'), `${compareLabel} ${deltaHtml(mix.delta, '%')}`)}
        ${card('예수금 시장점유율', valueText(share.base, '%'), `${compareLabel} ${deltaHtml(share.delta, '%')}`)}
        ${card('개인 예수금', valueText(personal.base, '억원'), `${compareLabel} ${deltaHtml(personal.delta, '억원')}`)}
        ${card('기업 예수금', valueText(corp.base, '억원'), `${compareLabel} ${deltaHtml(corp.delta, '억원')}`)}
        ${card('개인사업자 예수금', valueText(sole.base, '억원'), '기업 예수금에 포함')}
        ${card('단순 예대율', valueText(ldr.base, '%'), '총대출 ÷ 총예수금')}
      </div>`
    );

    const h = data.rate_history || {};
    let linkage;
    if (h.available) {
      const scope = h.status === 'full' ? '분기 전체 금리이력' : '보유 금리이력 구간';
      linkage = `<div class="mi-linkage">
        <strong>금리-수신 연계분석 · ${esc(scope)}</strong><br>
        우리금융 12개월 최고금리 ${valueText(h.first_rate, '%')} → ${valueText(h.last_rate, '%')}
        (${deltaHtml(h.rate_change, '%p')}) · 평균 ${valueText(h.average_rate, '%')} ·
        금리순위 ${h.first_rank ?? '-'}위 → ${h.last_rank ?? '-'}위.<br>
        같은 분기 총예수금은 ${deltaHtml(dep.delta, '억원')}, 정기예금은 ${deltaHtml(td.delta, '억원')} 변동했습니다.
        ${h.note ? `<br><span>${esc(h.note)}</span>` : ''}
      </div>`;
    } else {
      linkage = `<div class="mi-linkage">
        <strong>금리-수신 연계분석</strong><br>
        ${esc(data.base_label || '')}에 대응하는 SBRate 일별 금리 이력이 없어 현재 금리와 과거 FISIS 잔액을 억지로 연결하지 않습니다.<br>
        일별 금리 이력이 축적되는 향후 분기부터 <b>분기 평균금리·분기말 금리·금리순위 변화 ↔ 실제 예수금/정기예금 증감</b>을 자동 비교합니다.
      </div>`;
    }

    return current + confirmed + block(
      '금리-수신 연계분석',
      h.available ? `${h.first_date || '-'} ~ ${h.last_date || '-'} · ${h.snapshot_count || 0}개 스냅샷` : '동일 기간 데이터만 비교',
      linkage + `<div class="mi-note">${esc(data.notes?.rate_basis || '')}<br>${esc(data.notes?.loan_deposit_ratio || '')}</div>`
    ) + block('업권 수신 현황', `${data.bank_count || 0}개사`, fundingTable(data));
  }

  function soundnessTable(data) {
    const rows = [...(data.rows || [])].sort((a, b) => (a.asset_rank || 999) - (b.asset_rank || 999));
    const dLabel = compareLabel();
    const body = rows.map(row => {
      const bis = metric(row, 'bis_ratio');
      const delin = metric(row, 'delinquency_ratio');
      const npl = metric(row, 'npl_ratio_effective');
      const liq = metric(row, 'liquidity_ratio');
      const cover = metric(row, 'npl_coverage_ratio');
      const re = metric(row, 'real_estate_corp_share');
      return `<tr class="${row.is_woori ? 'mi-woori' : ''}">
        <td>${row.asset_rank ?? '-'}</td><td>${esc(row.bank || '-')}</td><td>${esc(row.region || '-')}</td>
        <td>${valueText(bis.base, '%')}</td><td>${deltaHtml(bis.delta, '%p')}</td>
        <td>${valueText(delin.base, '%')}</td><td>${deltaHtml(delin.delta, '%p')}</td>
        <td>${valueText(npl.base, '%')}</td><td>${valueText(liq.base, '%')}</td>
        <td>${valueText(cover.base, '%')}</td><td>${valueText(re.base, '%')}</td>
      </tr>`;
    }).join('');
    return `<div class="mi-table-wrap"><table class="mi-table"><thead><tr>
      <th>총자산순위</th><th>저축은행</th><th>지역</th><th>BIS</th><th>${dLabel}</th><th>연체율</th><th>${dLabel}</th>
      <th>고정이하여신</th><th>유동성비율</th><th>NPL커버리지</th><th>부동산업 기업대출비중</th>
    </tr></thead><tbody>${body}</tbody></table></div>`;
  }

  function renderSoundness(data) {
    const w = data.woori || {};
    const bis = metric(w, 'bis_ratio');
    const delin = metric(w, 'delinquency_ratio');
    const npl = metric(w, 'npl_ratio_effective');
    const liq = metric(w, 'liquidity_ratio');
    const cover = metric(w, 'npl_coverage_ratio');
    const fixed = metric(w, 'fixed_below_loans');
    const re = metric(w, 'real_estate_corp_share');
    return block(
      `우리금융 건전성 · ${data.base_label || ''}`,
      `${data.as_of || '-'} 기준 · FISIS`,
      `<div class="mi-card-grid">
        ${card('BIS비율', valueText(bis.base, '%'), `${compareLabel()} ${deltaHtml(bis.delta, '%p')}`, true)}
        ${card('연체율', valueText(delin.base, '%'), `${compareLabel()} ${deltaHtml(delin.delta, '%p')}`)}
        ${card('고정이하여신비율', valueText(npl.base, '%'), `${compareLabel()} ${deltaHtml(npl.delta, '%p')}`)}
        ${card('유동성비율', valueText(liq.base, '%'), `${compareLabel()} ${deltaHtml(liq.delta, '%p')}`)}
        ${card('NPL 충당금커버리지', valueText(cover.base, '%'), `${compareLabel()} ${deltaHtml(cover.delta, '%p')}`)}
        ${card('고정이하여신', valueText(fixed.base, '억원'), `${compareLabel()} ${deltaHtml(fixed.delta, '억원')}`)}
        ${card('부동산업 기업대출 비중', valueText(re.base, '%'), `${compareLabel()} ${deltaHtml(re.delta, '%p')}`)}
      </div>
      <div class="mi-note">연체율·고정이하여신비율·부동산업 대출비중은 낮을수록 건전성 측면에서 유리하지만, 증감 표시는 SBRate 공통 규칙에 따라 증가 + 파란색 / 감소 ▲ 빨간색으로 표시합니다.</div>`
    ) + block('업권 건전성 현황', `${data.bank_count || 0}개사`, soundnessTable(data));
  }

  function profitabilityTable(data) {
    const rows = [...(data.rows || [])].sort((a, b) => (a.asset_rank || 999) - (b.asset_rank || 999));
    const single = !isCompareMode();
    const dLabel = single ? '전년동기比' : '비교분기比';
    const body = rows.map(row => {
      const ni = metric(row, 'net_income');
      const op = metric(row, 'operating_profit');
      const roa = metric(row, 'roa');
      const roe = metric(row, 'roe');
      const nii = metric(row, 'net_interest_income');
      const ie = metric(row, 'interest_expense');
      const tdie = metric(row, 'time_deposit_interest_expense');
      const delta = single ? ni.yoy_delta : ni.delta;
      return `<tr class="${row.is_woori ? 'mi-woori' : ''}">
        <td>${row.asset_rank ?? '-'}</td><td>${esc(row.bank || '-')}</td><td>${esc(row.region || '-')}</td>
        <td>${valueText(ni.base, '억원')}</td><td>${deltaHtml(delta, '억원')}</td>
        <td>${valueText(op.base, '억원')}</td><td>${valueText(roa.base, '%')}</td><td>${valueText(roe.base, '%')}</td>
        <td>${valueText(nii.base, '억원')}</td><td>${valueText(ie.base, '억원')}</td><td>${valueText(tdie.base, '억원')}</td>
      </tr>`;
    }).join('');
    return `<div class="mi-table-wrap"><table class="mi-table"><thead><tr>
      <th>총자산순위</th><th>저축은행</th><th>지역</th><th>당기순이익</th><th>${dLabel}</th><th>영업이익</th><th>ROA</th><th>ROE</th>
      <th>이자 순수익</th><th>이자비용</th><th>정기예금 이자비용</th>
    </tr></thead><tbody>${body}</tbody></table></div>`;
  }

  function renderProfitability(data) {
    const w = data.woori || {};
    const single = !isCompareMode();
    const label = single ? '전년동기比' : '비교분기比';
    const pickDelta = pack => single ? pack?.yoy_delta : pack?.delta;
    const ni = metric(w, 'net_income');
    const op = metric(w, 'operating_profit');
    const roa = metric(w, 'roa');
    const roe = metric(w, 'roe');
    const nii = metric(w, 'net_interest_income');
    const ii = metric(w, 'interest_income');
    const ie = metric(w, 'interest_expense');
    const de = metric(w, 'deposit_interest_expense');
    const tde = metric(w, 'time_deposit_interest_expense');
    const yoyBasis = single ? (data.yoy_compare_label || '전년동기 데이터 없음') : (data.compare_label || '-');
    return block(
      `우리금융 수익성 · ${data.base_label || ''}`,
      `${data.as_of || '-'} 기준 · 손익 누적 · 비교기준 ${yoyBasis}`,
      `<div class="mi-card-grid">
        ${card('당기순이익', valueText(ni.base, '억원'), `${label} ${deltaHtml(pickDelta(ni), '억원')}`, true)}
        ${card('영업이익', valueText(op.base, '억원'), `${label} ${deltaHtml(pickDelta(op), '억원')}`)}
        ${card('ROA', valueText(roa.base, '%'), `${label} ${deltaHtml(pickDelta(roa), '%p')}`)}
        ${card('ROE', valueText(roe.base, '%'), `${label} ${deltaHtml(pickDelta(roe), '%p')}`)}
        ${card('이자 순수익', valueText(nii.base, '억원'), `${label} ${deltaHtml(pickDelta(nii), '억원')}`)}
        ${card('이자수익', valueText(ii.base, '억원'), `${label} ${deltaHtml(pickDelta(ii), '억원')}`)}
        ${card('이자비용', valueText(ie.base, '억원'), `${label} ${deltaHtml(pickDelta(ie), '억원')}`)}
        ${card('예수금 이자비용', valueText(de.base, '억원'), `${label} ${deltaHtml(pickDelta(de), '억원')}`)}
        ${card('정기예금 이자비용', valueText(tde.base, '억원'), `${label} ${deltaHtml(pickDelta(tde), '억원')}`)}
      </div>
      <div class="mi-note">손익은 FISIS 공시 누적값입니다. 단일분기 화면에서는 누적기간이 다른 전분기와 직접 비교하지 않고 전년동기比를 우선 표시합니다.</div>`
    ) + block('업권 수익성 현황', `${data.bank_count || 0}개사`, profitabilityTable(data));
  }

  function renderSection(data) {
    if (!data?.ok) return `<div class="mi-warmup">데이터를 불러오지 못했습니다.<br>${esc(data?.error || '')}</div>`;
    if (!data.ready) return renderWarmup(data);
    if (data.section === 'funding') return renderFunding(data);
    if (data.section === 'soundness') return renderSoundness(data);
    return renderProfitability(data);
  }

  function modal() {
    return document.getElementById('management-report-modal');
  }

  function ensureUI() {
    const m = modal();
    if (!m) return false;
    const topbar = m.querySelector('.mr-topbar');
    const close = document.getElementById('mr-close');
    if (topbar && close && !document.getElementById('mi-section-tabs')) {
      const tabs = document.createElement('div');
      tabs.id = 'mi-section-tabs';
      tabs.className = 'mi-section-tabs';
      tabs.innerHTML = Object.entries(SECTION_LABELS).map(([key, label]) =>
        `<button type="button" class="mi-section-tab${key === activeSection ? ' is-active' : ''}" data-mi-section="${key}">${label}</button>`
      ).join('');
      topbar.insertBefore(tabs, close);
    }
    if (!document.getElementById('mi-content')) {
      const content = document.createElement('div');
      content.id = 'mi-content';
      content.className = 'mi-content';
      content.hidden = true;
      const tableCard = m.querySelector('.mr-table-card');
      if (tableCard) tableCard.parentNode.insertBefore(content, tableCard);
      else m.querySelector('.mr-shell')?.appendChild(content);
    }
    return true;
  }

  function toggleBaseReport(show) {
    const m = modal();
    if (!m) return;
    const status = document.getElementById('mr-status');
    const summary = document.getElementById('mr-summary');
    const table = m.querySelector('.mr-table-card');
    if (status) status.style.display = show ? '' : 'none';
    if (summary) summary.style.display = show ? '' : 'none';
    if (table) table.style.display = show ? '' : 'none';
    const content = document.getElementById('mi-content');
    if (content) content.hidden = show;
  }

  async function loadActiveSection() {
    if (activeSection === 'general') return;
    if (!ensureUI()) return;
    const content = document.getElementById('mi-content');
    if (!content) return;
    const base = isCompareMode()
      ? document.getElementById('mr-base-quarter')?.value
      : document.getElementById('mr-single-quarter')?.value;
    const compare = isCompareMode() ? document.getElementById('mr-compare-quarter')?.value : '';
    const seq = ++loadSeq;
    content.innerHTML = '<div class="mi-warmup">FISIS 경영 데이터를 분석하고 있습니다.</div>';
    const params = new URLSearchParams({ section: activeSection });
    if (base) params.set('base', base);
    if (compare) params.set('compare', compare);
    try {
      const response = await fetch(`/api/management-intelligence?${params.toString()}`, { cache: 'no-store' });
      const data = await response.json();
      if (seq !== loadSeq) return;
      content.innerHTML = renderSection(data);
    } catch (error) {
      if (seq !== loadSeq) return;
      content.innerHTML = `<div class="mi-warmup">FISIS 분석 데이터를 불러오지 못했습니다.<br>${esc(error?.message || error)}</div>`;
    }
  }

  function selectSection(section) {
    if (!(section in SECTION_LABELS)) return;
    activeSection = section;
    ensureUI();
    document.querySelectorAll('#mi-section-tabs [data-mi-section]').forEach(btn => {
      btn.classList.toggle('is-active', btn.dataset.miSection === section);
    });
    toggleBaseReport(section === 'general');
    if (section !== 'general') loadActiveSection();
  }

  function smallInsightDelta(pack, unit = '', useYoy = false) {
    const value = useYoy ? pack?.yoy_delta : pack?.delta;
    return deltaHtml(value, unit);
  }

  async function mountInsight() {
    const aside = document.getElementById('ai-analysis-center');
    if (!aside || document.getElementById('fisis-management-insight')) return;
    const buttons = document.getElementById('ai-side-detail-btn')?.parentElement;
    if (!buttons) return;
    const box = document.createElement('div');
    box.id = 'fisis-management-insight';
    box.className = 'mi-insight-box';
    box.innerHTML = '<div class="mi-insight-title">FISIS 경영 인사이트 <span class="mi-insight-basis">불러오는 중</span></div>';
    buttons.parentNode.insertBefore(box, buttons);
    try {
      const res = await fetch('/api/management-intelligence/insight', { cache: 'no-store' });
      const data = await res.json();
      if (!data?.ok || !data.ready) {
        box.innerHTML = '<div class="mi-insight-title">FISIS 경영 인사이트 <span class="mi-insight-basis">확장지표 수집 중</span></div><div class="mi-insight-line">총예수금·건전성·수익성 지표를 최초 수집하고 있습니다.</div>';
        return;
      }
      const f = data.funding || {};
      const s = data.soundness || {};
      const p = data.profitability || {};
      const market = data.current_market || {};
      const mw = market.woori || {};
      const dep = metric(f, 'deposits');
      const delin = metric(s, 'delinquency_ratio');
      const bis = metric(s, 'bis_ratio');
      const ni = metric(p, 'net_income');
      box.innerHTML = `
        <div class="mi-insight-title">FISIS 경영 인사이트 <span class="mi-insight-basis">${esc(data.latest_label || '-')} · ${esc(data.as_of || '-')}</span></div>
        <div class="mi-insight-line"><b>수신</b> 총예수금 ${valueText(dep.base, '억원')} · 전분기比 ${smallInsightDelta(dep, '억원')} / 현재금리 ${valueText(mw.rate, '%')} (${mw.rank ?? '-'}위)</div>
        <div class="mi-insight-line"><b>건전성</b> 연체율 ${valueText(delin.base, '%')} (${smallInsightDelta(delin, '%p')}) · BIS ${valueText(bis.base, '%')} (${smallInsightDelta(bis, '%p')})</div>
        <div class="mi-insight-line"><b>수익</b> 당기순이익 ${valueText(ni.base, '억원')} · 전년동기比 ${smallInsightDelta(ni, '억원', true)}</div>`;
    } catch (_) {
      box.innerHTML = '<div class="mi-insight-title">FISIS 경영 인사이트</div><div class="mi-insight-line">경영 데이터를 불러오지 못했습니다.</div>';
    }
  }

  function bindEvents() {
    if (document.documentElement.dataset.miEventsBound === '1') return;
    document.documentElement.dataset.miEventsBound = '1';
    document.addEventListener('click', event => {
      const sectionButton = event.target.closest?.('[data-mi-section]');
      if (sectionButton) {
        event.preventDefault();
        selectSection(sectionButton.dataset.miSection);
        return;
      }
      if (event.target.closest?.('#mr-single-run,#mr-run,[data-mr-mode]')) {
        if (activeSection !== 'general') setTimeout(loadActiveSection, 90);
      }
      if (event.target.closest?.('#management-report-open,#management-report-open-mobile')) {
        setTimeout(() => {
          ensureUI();
          selectSection(activeSection);
        }, 120);
      }
    }, true);
  }

  function boot() {
    ensureUI();
    bindEvents();
    mountInsight();
  }

  const observer = new MutationObserver(() => {
    ensureUI();
    mountInsight();
  });
  observer.observe(document.documentElement, { childList: true, subtree: true });

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true });
  else boot();
})();
