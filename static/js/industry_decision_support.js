(() => {
  'use strict';

  let overviewSeq = 0;
  let detailSeq = 0;
  let observerTimer = null;

  const esc = value => String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');

  const num = value => {
    if (value === null || value === undefined || value === '') return null;
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  };

  function modal() {
    return document.getElementById('management-report-modal');
  }

  function isCompareMode() {
    return !!document.querySelector('#management-report-modal [data-mr-mode="compare"].is-active');
  }

  function currentQuery() {
    const mode = isCompareMode() ? 'compare' : 'single';
    const base = mode === 'compare'
      ? document.getElementById('mr-base-quarter')?.value || ''
      : document.getElementById('mr-single-quarter')?.value || '';
    const compare = mode === 'compare' ? document.getElementById('mr-compare-quarter')?.value || '' : '';
    return { mode, base, compare };
  }

  function formatValue(value, unit, rankMetric = false) {
    const n = num(value);
    if (n === null) return '-';
    if (rankMetric || unit === '위') return `${Math.round(n)}위`;
    if (unit === '%p' || unit === '%') return `${n.toLocaleString('ko-KR', {minimumFractionDigits: 2, maximumFractionDigits: 2})}%`;
    if (unit === '억원') return `${n.toLocaleString('ko-KR', {maximumFractionDigits: Math.abs(n) < 10 ? 1 : 0})}억원`;
    return n.toLocaleString('ko-KR');
  }

  function formatDelta(value, unit, rankMetric = false) {
    const n = num(value);
    if (n === null || Math.abs(n) < 0.0000001) return '-';
    const marker = n > 0 ? '+' : '▲';
    const abs = Math.abs(n);
    if (rankMetric || unit === '위') return `${marker}${Math.round(abs)}위`;
    if (unit === '%p') return `${marker}${abs.toLocaleString('ko-KR', {minimumFractionDigits: 2, maximumFractionDigits: 2})}%p`;
    if (unit === '억원') return `${marker}${abs.toLocaleString('ko-KR', {maximumFractionDigits: abs < 10 ? 1 : 0})}억원`;
    return `${marker}${abs.toLocaleString('ko-KR')}`;
  }

  function ensureUI() {
    const m = modal();
    if (!m) return false;

    const titleLine = m.querySelector('.mr-title-line');
    if (titleLine && !document.getElementById('ids-quality-badge')) {
      const badge = document.createElement('button');
      badge.type = 'button';
      badge.id = 'ids-quality-badge';
      badge.className = 'ids-quality-badge is-loading';
      badge.innerHTML = '<span class="ids-quality-dot"></span><span>데이터 확인중</span>';
      badge.title = '데이터 신뢰도 상세보기';
      titleLine.appendChild(badge);
    }

    const query = m.querySelector('.mr-query-area');
    if (query && !document.getElementById('ids-overview-strip')) {
      const section = document.createElement('section');
      section.id = 'ids-overview-strip';
      section.className = 'ids-overview-strip';
      section.innerHTML = `
        <div id="ids-quality-panel" class="ids-quality-panel" hidden></div>
        <div class="ids-brief-head">
          <div><span class="ids-brief-kicker">DECISION BRIEF</span><strong id="ids-brief-title">이번 분기 핵심 변화</strong></div>
          <span id="ids-brief-basis" class="ids-brief-basis">불러오는 중</span>
        </div>
        <div id="ids-brief-items" class="ids-brief-items"><div class="ids-brief-loading">핵심 변화를 확인하고 있습니다.</div></div>`;
      query.insertAdjacentElement('afterend', section);
    }

    if (!document.getElementById('ids-bank-detail-panel')) {
      const backdrop = document.createElement('div');
      backdrop.id = 'ids-bank-detail-backdrop';
      backdrop.className = 'ids-bank-detail-backdrop';
      backdrop.hidden = true;
      const panel = document.createElement('aside');
      panel.id = 'ids-bank-detail-panel';
      panel.className = 'ids-bank-detail-panel';
      panel.setAttribute('aria-hidden', 'true');
      panel.innerHTML = '<div class="ids-detail-loading">은행 상세정보를 준비하고 있습니다.</div>';
      m.appendChild(backdrop);
      m.appendChild(panel);
    }
    return true;
  }

  function renderQuality(quality) {
    const badge = document.getElementById('ids-quality-badge');
    const panel = document.getElementById('ids-quality-panel');
    if (!badge || !panel) return;
    const state = quality?.state || 'warning';
    badge.className = `ids-quality-badge is-${state}`;
    badge.innerHTML = `<span class="ids-quality-dot"></span><span>${esc(quality?.label || '데이터 확인 필요')}</span>`;
    const sources = Array.isArray(quality?.sources) ? quality.sources : [];
    panel.innerHTML = `
      <div class="ids-quality-panel-head">
        <div><strong>데이터 신뢰도</strong><span>${esc(quality?.checked_at || '-')} 확인</span></div>
        <button type="button" class="ids-quality-close" aria-label="데이터 신뢰도 닫기">×</button>
      </div>
      <div class="ids-quality-grid">
        ${sources.map(source => `
          <article class="ids-quality-source is-${esc(source.state || 'warning')}">
            <div class="ids-quality-source-title"><span class="ids-quality-source-dot"></span><strong>${esc(source.label || '-')}</strong></div>
            <div class="ids-quality-source-main">${esc(source.headline || '-')}</div>
            <div class="ids-quality-source-sub">${esc(source.detail || '')}</div>
            <div class="ids-quality-source-time">기준/갱신 ${esc(source.updated_at || '-')}</div>
          </article>`).join('')}
      </div>
      <div class="ids-quality-note">FISIS는 최신분기 총자산 공시 커버리지 기준, 예금·ISA·IRP는 현재 보유 데이터와 유효금리 기준으로 상태를 표시합니다.</div>`;
  }

  function briefItemHtml(item) {
    const move = item?.movement || 'flat';
    const rankMetric = !!item?.rank_metric;
    const semantic = item?.semantic === 'good' ? ' · 개선' : item?.semantic === 'bad' ? ' · 확인' : '';
    return `<article class="ids-brief-item is-${esc(move)}">
      <div class="ids-brief-item-title">${esc(item?.title || '-')}</div>
      <div class="ids-brief-item-value">${esc(formatValue(item?.base, item?.unit, rankMetric))}</div>
      <div class="ids-brief-item-change"><b>${esc(formatDelta(item?.delta, item?.unit, rankMetric))}</b>${esc(semantic)}</div>
      <div class="ids-brief-item-basis">${esc(item?.basis || '')}</div>
    </article>`;
  }

  function renderBrief(brief) {
    const title = document.getElementById('ids-brief-title');
    const basis = document.getElementById('ids-brief-basis');
    const root = document.getElementById('ids-brief-items');
    if (!title || !basis || !root) return;
    title.textContent = brief?.heading || '핵심 변화';
    basis.textContent = brief?.mode === 'compare'
      ? `${brief?.base_label || brief?.base || '-'} vs ${brief?.compare || '-'}`
      : (brief?.base_label || brief?.base || '-');
    const items = Array.isArray(brief?.items) ? brief.items : [];
    root.innerHTML = items.length
      ? items.map(briefItemHtml).join('')
      : '<div class="ids-brief-empty">표시할 주요 변동이 없습니다.</div>';
  }

  async function loadOverview() {
    if (!ensureUI()) return;
    const query = currentQuery();
    if (!query.base) return;
    const seq = ++overviewSeq;
    const params = new URLSearchParams({mode: query.mode, base: query.base});
    if (query.compare) params.set('compare', query.compare);
    try {
      const response = await fetch(`/api/industry-overview?${params.toString()}`, {cache: 'no-store'});
      const data = await response.json();
      if (seq !== overviewSeq) return;
      if (!response.ok || !data?.ok) throw new Error(data?.error || `HTTP ${response.status}`);
      renderQuality(data.quality || {});
      renderBrief(data.brief || {});
      decorateBankCells();
    } catch (error) {
      if (seq !== overviewSeq) return;
      const badge = document.getElementById('ids-quality-badge');
      if (badge) {
        badge.className = 'ids-quality-badge is-warning';
        badge.innerHTML = '<span class="ids-quality-dot"></span><span>데이터 확인 필요</span>';
      }
      const root = document.getElementById('ids-brief-items');
      if (root) root.innerHTML = `<div class="ids-brief-empty">변화 브리핑을 불러오지 못했습니다. ${esc(error?.message || error)}</div>`;
    }
  }

  function bankNameFromCell(cell) {
    if (!cell) return '';
    const strong = cell.querySelector('strong');
    return String(strong?.textContent || cell.textContent || '').trim().replace(/\s*업권\s*자산\s*\d+위.*$/u, '').trim();
  }

  function decorateBankCells(root = document) {
    const cells = [
      ...(root.querySelectorAll?.('#mr-table tbody td.mr-col-bank') || []),
      ...(root.querySelectorAll?.('#mi-content .mi-table tbody tr td:nth-child(2)') || []),
      ...(root.querySelectorAll?.('#mp-content .mp-table tbody td.mp-bank-col') || []),
    ];
    cells.forEach(cell => {
      const bank = bankNameFromCell(cell);
      if (!bank) return;
      cell.classList.add('ids-bank-link');
      cell.dataset.idsBank = bank;
      cell.setAttribute('role', 'button');
      cell.setAttribute('tabindex', '0');
      cell.title = `${bank} 상세 추이 보기`;
    });
  }

  function metricFormat(value, unit) {
    const n = num(value);
    if (n === null) return '-';
    if (unit === '%') return `${n.toLocaleString('ko-KR', {minimumFractionDigits: 2, maximumFractionDigits: 2})}%`;
    if (unit === '억원') return `${n.toLocaleString('ko-KR', {maximumFractionDigits: Math.abs(n) < 10 ? 1 : 0})}억원`;
    return n.toLocaleString('ko-KR');
  }

  function gapFormat(value, unit) {
    const n = num(value);
    if (n === null || Math.abs(n) < 0.0000001) return '-';
    const marker = n > 0 ? '+' : '▲';
    const abs = Math.abs(n);
    if (unit === '%') return `${marker}${abs.toLocaleString('ko-KR', {minimumFractionDigits: 2, maximumFractionDigits: 2})}%p`;
    return `${marker}${abs.toLocaleString('ko-KR', {maximumFractionDigits: abs < 10 ? 1 : 0})}억원`;
  }

  function sparkline(history, key) {
    const values = (history || []).map(point => num(point?.metrics?.[key]));
    const valid = values.map((value, index) => value === null ? null : {value, index}).filter(Boolean);
    if (valid.length < 2) return '<div class="ids-spark-empty">추이 데이터 부족</div>';
    const min = Math.min(...valid.map(item => item.value));
    const max = Math.max(...valid.map(item => item.value));
    const range = max - min || 1;
    const lastIndex = Math.max(1, values.length - 1);
    const points = valid.map(item => {
      const x = 4 + (item.index / lastIndex) * 172;
      const y = 44 - ((item.value - min) / range) * 34;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');
    return `<svg class="ids-spark" viewBox="0 0 180 50" preserveAspectRatio="none" aria-hidden="true"><polyline points="${points}" fill="none" vector-effect="non-scaling-stroke"></polyline></svg>`;
  }

  function trendCard(field, history) {
    const values = (history || []).map(point => ({label: point.label, value: num(point?.metrics?.[field.key])})).filter(item => item.value !== null);
    const first = values[0];
    const last = values[values.length - 1];
    return `<article class="ids-trend-card">
      <div class="ids-trend-head"><strong>${esc(field.label)}</strong><span>${esc(metricFormat(last?.value, field.unit))}</span></div>
      ${sparkline(history, field.key)}
      <div class="ids-trend-foot"><span>${esc(first?.label || '-')} ${esc(metricFormat(first?.value, field.unit))}</span><span>${esc(last?.label || '-')}</span></div>
    </article>`;
  }

  function comparisonRows(data) {
    if (data?.is_woori) return '<div class="ids-woori-self">우리금융 자체 상세화면입니다.</div>';
    return `<div class="ids-compare-table">
      <div class="ids-compare-row ids-compare-head"><span>지표</span><span>${esc(data.display_bank || '-')}</span><span>우리금융</span><span>차이</span></div>
      ${(data.fields || []).map(field => `
        <div class="ids-compare-row">
          <span>${esc(field.label)}</span>
          <b>${esc(metricFormat(data.current?.[field.key], field.unit))}</b>
          <span>${esc(metricFormat(data.woori?.[field.key], field.unit))}</span>
          <span class="${(num(data.gap_vs_woori?.[field.key]) || 0) > 0 ? 'ids-gap-up' : (num(data.gap_vs_woori?.[field.key]) || 0) < 0 ? 'ids-gap-down' : ''}">${esc(gapFormat(data.gap_vs_woori?.[field.key], field.unit))}</span>
        </div>`).join('')}
    </div>`;
  }

  function renderBankDetail(data) {
    const panel = document.getElementById('ids-bank-detail-panel');
    if (!panel) return;
    const fields = Array.isArray(data?.fields) ? data.fields : [];
    panel.innerHTML = `
      <div class="ids-detail-head">
        <div>
          <span class="ids-detail-kicker">BANK DETAIL</span>
          <h3>${esc(data.display_bank || '-')}</h3>
          <p>${esc(data.region || '-')} · ${esc(data.base_label || data.base || '-')} · 총자산 ${esc(data.asset_rank ? `${data.asset_rank}/${data.bank_count}위` : '-')}</p>
        </div>
        <button type="button" class="ids-detail-close" aria-label="은행 상세 닫기">×</button>
      </div>
      <div class="ids-detail-current">
        ${fields.map(field => `<article><span>${esc(field.label)}</span><strong>${esc(metricFormat(data.current?.[field.key], field.unit))}</strong></article>`).join('')}
      </div>
      <section class="ids-detail-section">
        <div class="ids-detail-section-head"><strong>최근 ${esc(data.history_count || 0)}개 분기 추이</strong><span>FISIS 공시 기준</span></div>
        <div class="ids-trend-grid">${fields.map(field => trendCard(field, data.history || [])).join('')}</div>
      </section>
      <section class="ids-detail-section">
        <div class="ids-detail-section-head"><strong>우리금융과 비교</strong><span>${esc(data.base_label || '-')}</span></div>
        ${comparisonRows(data)}
      </section>
      <div class="ids-detail-note">${esc(data.note || '')}<br>출처: ${esc(data.source || '금융감독원 금융통계정보시스템(FISIS)')} · 캐시갱신 ${esc(data.store_updated_at || '-')}</div>`;
  }

  async function openBankDetail(bank) {
    if (!bank || !ensureUI()) return;
    const panel = document.getElementById('ids-bank-detail-panel');
    const backdrop = document.getElementById('ids-bank-detail-backdrop');
    if (!panel || !backdrop) return;
    const base = currentQuery().base;
    panel.innerHTML = `<div class="ids-detail-loading"><strong>${esc(bank)}</strong><br>최근 분기 추이를 불러오고 있습니다.</div>`;
    panel.classList.add('is-open');
    panel.setAttribute('aria-hidden', 'false');
    backdrop.hidden = false;
    backdrop.classList.add('is-open');
    modal()?.classList.add('ids-bank-detail-open');
    const seq = ++detailSeq;
    const params = new URLSearchParams({bank});
    if (base) params.set('base', base);
    try {
      const response = await fetch(`/api/industry-bank-detail?${params.toString()}`, {cache: 'no-store'});
      const data = await response.json();
      if (seq !== detailSeq) return;
      if (!response.ok || !data?.ok) throw new Error(data?.error || `HTTP ${response.status}`);
      renderBankDetail(data);
    } catch (error) {
      if (seq !== detailSeq) return;
      panel.innerHTML = `<div class="ids-detail-head"><div><h3>${esc(bank)}</h3><p>상세정보 확인 실패</p></div><button type="button" class="ids-detail-close">×</button></div><div class="ids-detail-error">${esc(error?.message || error)}</div>`;
    }
  }

  function closeBankDetail() {
    detailSeq += 1;
    const panel = document.getElementById('ids-bank-detail-panel');
    const backdrop = document.getElementById('ids-bank-detail-backdrop');
    panel?.classList.remove('is-open');
    panel?.setAttribute('aria-hidden', 'true');
    if (backdrop) {
      backdrop.classList.remove('is-open');
      backdrop.hidden = true;
    }
    modal()?.classList.remove('ids-bank-detail-open');
  }

  function toggleQuality(show = null) {
    const panel = document.getElementById('ids-quality-panel');
    if (!panel) return;
    const shouldShow = show === null ? panel.hidden : Boolean(show);
    panel.hidden = !shouldShow;
    document.getElementById('ids-quality-badge')?.classList.toggle('is-expanded', shouldShow);
  }

  function scheduleDecorate(delay = 120) {
    setTimeout(() => decorateBankCells(), delay);
    setTimeout(() => decorateBankCells(), Math.max(350, delay + 250));
  }

  function bindEvents() {
    if (document.documentElement.dataset.idsEventsBound === '1') return;
    document.documentElement.dataset.idsEventsBound = '1';

    document.addEventListener('click', event => {
      if (event.target.closest?.('#ids-quality-badge')) {
        event.preventDefault();
        toggleQuality();
        return;
      }
      if (event.target.closest?.('.ids-quality-close')) {
        event.preventDefault();
        toggleQuality(false);
        return;
      }
      if (event.target.closest?.('.ids-detail-close,#ids-bank-detail-backdrop')) {
        event.preventDefault();
        closeBankDetail();
        return;
      }
      const bankCell = event.target.closest?.('.ids-bank-link');
      if (bankCell) {
        event.preventDefault();
        openBankDetail(bankCell.dataset.idsBank || bankNameFromCell(bankCell));
        return;
      }
      if (event.target.closest?.('#mi-section-tabs [data-mi-section]')) {
        scheduleDecorate(180);
        return;
      }
      if (event.target.closest?.('#mr-single-run,#mr-run,[data-mr-mode]')) {
        scheduleDecorate(180);
        setTimeout(loadOverview, 220);
        return;
      }
      if (event.target.closest?.('#management-report-open,#management-report-open-mobile')) {
        setTimeout(() => {
          ensureUI();
          decorateBankCells();
          loadOverview();
        }, 260);
        scheduleDecorate(500);
        return;
      }
      if (event.target.closest?.('#mr-close')) closeBankDetail();
    }, true);

    document.addEventListener('keydown', event => {
      if ((event.key === 'Enter' || event.key === ' ') && event.target?.classList?.contains('ids-bank-link')) {
        event.preventDefault();
        openBankDetail(event.target.dataset.idsBank || bankNameFromCell(event.target));
      } else if (event.key === 'Escape') {
        closeBankDetail();
        toggleQuality(false);
      }
    });
  }

  function boot() {
    ensureUI();
    bindEvents();
    decorateBankCells();
    if (modal()?.classList.contains('is-open')) loadOverview();
  }

  const observer = new MutationObserver(() => {
    if (observerTimer) return;
    observerTimer = setTimeout(() => {
      observerTimer = null;
      ensureUI();
      decorateBankCells();
    }, 50);
  });
  observer.observe(document.documentElement, {childList: true, subtree: true});

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, {once: true});
  else boot();
})();
