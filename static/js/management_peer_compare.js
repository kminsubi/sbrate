(() => {
  'use strict';

  const PEER_KEY = 'peer';
  let peerActive = false;
  let loadSeq = 0;
  let timer = null;

  const esc = value => String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');

  function num(value) {
    if (value === null || value === undefined || value === '') return null;
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  }

  function isCompareMode() {
    return !!document.querySelector('#management-report-modal [data-mr-mode="compare"].is-active');
  }

  function currentBase() {
    return isCompareMode()
      ? document.getElementById('mr-base-quarter')?.value || ''
      : document.getElementById('mr-single-quarter')?.value || '';
  }

  function currentCompare() {
    return isCompareMode() ? document.getElementById('mr-compare-quarter')?.value || '' : '';
  }

  function fmt(value, unit) {
    const n = num(value);
    if (n === null) return '-';
    if (unit === '억원') {
      const digits = Math.abs(n) >= 100 ? 0 : Math.abs(n) >= 10 ? 1 : 2;
      return `${n.toLocaleString('ko-KR', {minimumFractionDigits: digits, maximumFractionDigits: digits})}억원`;
    }
    if (unit === '%') return `${n.toLocaleString('ko-KR', {minimumFractionDigits: 2, maximumFractionDigits: 2})}%`;
    return n.toLocaleString('ko-KR');
  }

  function deltaHtml(value, unit) {
    const n = num(value);
    if (n === null || Math.abs(n) < 0.0000001) return '<span class="mp-delta mp-flat">-</span>';
    const digits = unit === '억원' ? (Math.abs(n) >= 100 ? 0 : 1) : 2;
    const body = Math.abs(n).toLocaleString('ko-KR', {minimumFractionDigits: digits, maximumFractionDigits: digits});
    const suffix = unit === '%' ? '%p' : unit;
    return n > 0
      ? `<span class="mp-delta mp-up">+${body}${suffix}</span>`
      : `<span class="mp-delta mp-down">▲${body}${suffix}</span>`;
  }

  function peerRankText(rank) {
    return rank ? `${rank}/4위` : '-';
  }

  function getMetric(peer, key) {
    return peer?.metrics?.[key] || {};
  }

  function ensureUI() {
    const modal = document.getElementById('management-report-modal');
    const tabs = document.getElementById('mi-section-tabs');
    if (!modal || !tabs) return false;

    let tab = tabs.querySelector('[data-mi-section="peer"]');
    if (!tab) {
      tab = document.createElement('button');
      tab.type = 'button';
      tab.className = 'mi-section-tab mp-section-tab';
      tab.dataset.miSection = PEER_KEY;
      tab.textContent = '4대금융 비교';
      tab.title = '우리금융·신한·하나·KB 저축은행 비교';
      tabs.appendChild(tab);
    }

    let content = document.getElementById('mp-content');
    if (!content) {
      content = document.createElement('div');
      content.id = 'mp-content';
      content.className = 'mp-content';
      content.hidden = true;
      const miContent = document.getElementById('mi-content');
      if (miContent?.parentNode) miContent.insertAdjacentElement('afterend', content);
      else {
        const tableCard = modal.querySelector('.mr-table-card');
        if (tableCard?.parentNode) tableCard.parentNode.insertBefore(content, tableCard);
      }
    }
    return true;
  }

  function setBaseVisible(show) {
    const modal = document.getElementById('management-report-modal');
    if (!modal) return;
    const status = document.getElementById('mr-status');
    const summary = document.getElementById('mr-summary');
    const table = modal.querySelector('.mr-table-card');
    const miContent = document.getElementById('mi-content');
    if (status) status.style.display = show ? '' : 'none';
    if (summary) summary.style.display = show ? '' : 'none';
    if (table) table.style.display = show ? '' : 'none';
    if (miContent) miContent.hidden = true;
  }

  function activatePeer() {
    if (!ensureUI()) return;
    peerActive = true;
    const modal = document.getElementById('management-report-modal');
    modal?.classList.add('mp-peer-active');
    document.querySelectorAll('#mi-section-tabs [data-mi-section]').forEach(btn => {
      btn.classList.toggle('is-active', btn.dataset.miSection === PEER_KEY);
    });
    setBaseVisible(false);
    const content = document.getElementById('mp-content');
    if (content) content.hidden = false;
    loadPeer();
  }

  function deactivatePeer() {
    peerActive = false;
    document.getElementById('management-report-modal')?.classList.remove('mp-peer-active');
    const content = document.getElementById('mp-content');
    if (content) content.hidden = true;
  }

  function exportPeer() {
    if (!peerActive) return;
    const mode = isCompareMode() ? 'compare' : 'single';
    const base = currentBase();
    const compare = currentCompare();
    if (!base || (mode === 'compare' && (!compare || compare === base))) return;
    const params = new URLSearchParams({mode, base});
    if (mode === 'compare') params.set('compare', compare);
    window.location.href = `/api/management-peer/export.xlsx?${params.toString()}`;
  }

  function summaryCard(label, rank, value, note = '') {
    return `<div class="mp-summary-card">
      <div class="mp-summary-label">${esc(label)}</div>
      <div class="mp-summary-rank">${esc(peerRankText(rank))}</div>
      <div class="mp-summary-value">${esc(value)}</div>
      ${note ? `<div class="mp-summary-note">${esc(note)}</div>` : ''}
    </div>`;
  }

  function avgDiff(data, key) {
    const w = getMetric(data.woori, key).base;
    const avg = data.peer_average?.[key];
    const a = num(w), b = num(avg);
    return a !== null && b !== null ? a - b : null;
  }

  function signedText(value, unit) {
    const n = num(value);
    if (n === null) return '-';
    const digits = unit === '억원' ? 0 : 2;
    const body = Math.abs(n).toLocaleString('ko-KR', {minimumFractionDigits: digits, maximumFractionDigits: digits});
    return `${n >= 0 ? '+' : '-'}${body}${unit === '%' ? '%p' : unit}`;
  }

  function insightHtml(data) {
    const ranks = data.woori_peer_ranks || {};
    const bisGap = avgDiff(data, 'bis_ratio');
    const delinGap = avgDiff(data, 'delinquency_ratio');
    const roeGap = avgDiff(data, 'roe');
    const assetRank = ranks.total_assets ? `${ranks.total_assets}/4위` : '-';
    const depositRank = ranks.deposits ? `${ranks.deposits}/4위` : '-';
    return `<div class="mp-insight">
      <div class="mp-insight-title">우리금융 Peer 인사이트</div>
      <div class="mp-insight-text">
        우리금융은 4개사 중 <b>총자산 ${esc(assetRank)}</b>, <b>총예수금 ${esc(depositRank)}</b>입니다.
        BIS는 Peer 평균 대비 <b>${esc(signedText(bisGap, '%'))}</b>, 연체율은 <b>${esc(signedText(delinGap, '%'))}</b>, ROE(산출)는 <b>${esc(signedText(roeGap, '%'))}</b>입니다.
        <span class="mp-insight-help">연체율은 낮을수록 건전성 측면에서 유리합니다.</span>
      </div>
    </div>`;
  }

  function metricCell(peer, field) {
    const pack = getMetric(peer, field.key);
    return `<td class="${peer?.id === 'woori' ? 'mp-woori-col' : ''}">
      <div class="mp-cell-value">${esc(fmt(pack.base, field.unit))}</div>
      <div class="mp-cell-delta">${deltaHtml(pack.delta, field.unit)}</div>
    </td>`;
  }

  function comparisonTable(data) {
    const peers = data.peers || [];
    const headers = peers.map(peer => `<th class="${peer.id === 'woori' ? 'mp-woori-col' : ''}">
      <strong>${esc(peer.label)}</strong>
      <small>${peer.industry_asset_rank ? `업권 자산 ${peer.industry_asset_rank}위` : ''}</small>
    </th>`).join('');

    const rows = (data.fields || []).map(field => {
      const cells = peers.map(peer => metricCell(peer, field)).join('');
      const compareLabel = field.compare_quarter ? `${field.delta_label} · ${field.compare_quarter}` : field.delta_label;
      return `<tr>
        <td class="mp-metric-col">
          <span class="mp-category">${esc(field.category)}</span>
          <strong>${esc(field.label)}</strong>
          <small>${esc(field.unit)} · ${esc(compareLabel || '')}</small>
        </td>
        ${cells}
      </tr>`;
    }).join('');

    return `<div class="mp-table-wrap">
      <table class="mp-table">
        <thead><tr><th class="mp-metric-col">지표</th>${headers}</tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
  }

  function render(data) {
    if (!data?.ok) return `<div class="mi-warmup">4대금융 비교 데이터를 불러오지 못했습니다.<br>${esc(data?.error || '')}</div>`;
    const w = data.woori || {};
    const ranks = data.woori_peer_ranks || {};
    const summary = `<div class="mp-summary-grid">
      ${summaryCard('총자산', ranks.total_assets, fmt(getMetric(w, 'total_assets').base, '억원'), `업권 ${w.industry_asset_rank ?? '-'}위`)}
      ${summaryCard('총예수금', ranks.deposits, fmt(getMetric(w, 'deposits').base, '억원'), `업권 ${w.industry_deposit_rank ?? '-'}위`)}
      ${summaryCard('BIS비율', ranks.bis_ratio, fmt(getMetric(w, 'bis_ratio').base, '%'), '높을수록 양호')}
      ${summaryCard('연체율', ranks.delinquency_ratio, fmt(getMetric(w, 'delinquency_ratio').base, '%'), '낮을수록 양호')}
      ${summaryCard('ROE(산출)', ranks.roe, fmt(getMetric(w, 'roe').base, '%'), 'FISIS 원천자료 산출')}
    </div>`;

    const warning = (data.missing_peers || []).length
      ? `<div class="mp-warning">일부 Peer 데이터가 없습니다: ${esc(data.missing_peers.join(', '))}</div>`
      : '';

    return `<section class="mp-panel">
      <div class="mp-heading">
        <div>
          <div class="mp-eyebrow">FINANCIAL GROUP PEER</div>
          <h3>4대 금융지주 저축은행 비교</h3>
          <p>${esc(data.base_label || data.base || '-')} · ${esc(data.as_of || '-')} 기준 · 우리금융 → 신한 → 하나 → KB</p>
        </div>
        <div class="mp-heading-actions">
          <div class="mp-mode-badge">${data.mode === 'compare' ? `${esc(data.base || '')} vs ${esc(data.compare || '')}` : '분기현황'}</div>
          <button type="button" id="mp-export" class="mr-secondary-btn mp-export-btn">⬇ Excel 다운로드</button>
        </div>
      </div>
      ${warning}
      ${summary}
      ${insightHtml(data)}
      <div class="mp-table-head">
        <div><strong>4개사 핵심 경영지표</strong><span>현재값과 비교기준 증감을 함께 표시</span></div>
      </div>
      ${comparisonTable(data)}
      <div class="mp-note">${esc(data.notes?.comparison_basis || '')}<br>${esc(data.notes?.roa_roe || '')}<br>출처: ${esc(data.source || '금융감독원 금융통계정보시스템(FISIS)')}</div>
    </section>`;
  }

  async function loadPeer() {
    if (!peerActive || !ensureUI()) return;
    const content = document.getElementById('mp-content');
    if (!content) return;
    const base = currentBase();
    const compare = currentCompare();
    const mode = isCompareMode() ? 'compare' : 'single';
    if (!base || (mode === 'compare' && (!compare || compare === base))) {
      content.innerHTML = '<div class="mi-warmup">조회할 분기를 선택해 주세요.</div>';
      return;
    }
    const seq = ++loadSeq;
    content.innerHTML = '<div class="mi-warmup">4대 금융지주 저축은행 데이터를 비교하고 있습니다.</div>';
    const params = new URLSearchParams({mode, base});
    if (mode === 'compare') params.set('compare', compare);
    try {
      const response = await fetch(`/api/management-peer?${params.toString()}`, {cache: 'no-store'});
      const data = await response.json();
      if (seq !== loadSeq || !peerActive) return;
      content.innerHTML = render(data);
    } catch (error) {
      if (seq !== loadSeq || !peerActive) return;
      content.innerHTML = `<div class="mi-warmup">4대금융 비교 데이터를 불러오지 못했습니다.<br>${esc(error?.message || error)}</div>`;
    }
  }

  function bind() {
    if (document.documentElement.dataset.mpBound === '1') return;
    document.documentElement.dataset.mpBound = '1';
    document.addEventListener('click', event => {
      if (event.target.closest?.('#mp-export')) {
        event.preventDefault();
        exportPeer();
        return;
      }
      const section = event.target.closest?.('#mi-section-tabs [data-mi-section]');
      if (section) {
        if (section.dataset.miSection === PEER_KEY) {
          event.preventDefault();
          activatePeer();
        } else {
          deactivatePeer();
        }
        return;
      }
      if (event.target.closest?.('#mr-single-run,#mr-run,[data-mr-mode]')) {
        if (peerActive) setTimeout(loadPeer, 120);
        return;
      }
      if (event.target.closest?.('#management-report-open,#management-report-open-mobile')) {
        setTimeout(() => {
          ensureUI();
          if (peerActive) activatePeer();
        }, 160);
      }
    }, true);
  }

  function boot() {
    ensureUI();
    bind();
  }

  const observer = new MutationObserver(() => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      ensureUI();
      if (peerActive) {
        const content = document.getElementById('mp-content');
        if (content) content.hidden = false;
      }
    }, 40);
  });
  observer.observe(document.documentElement, {childList: true, subtree: true});

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, {once: true});
  else boot();
})();
