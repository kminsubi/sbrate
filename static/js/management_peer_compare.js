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
      return n.toLocaleString('ko-KR', { minimumFractionDigits: digits, maximumFractionDigits: digits });
    }
    if (unit === '%') return `${n.toLocaleString('ko-KR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`;
    return n.toLocaleString('ko-KR');
  }

  function deltaHtml(value, unit) {
    const n = num(value);
    if (n === null || Math.abs(n) < 0.0000001) return '<span class="mp-delta mp-flat">-</span>';
    const digits = unit === '억원' ? (Math.abs(n) >= 100 ? 0 : 1) : 2;
    const body = Math.abs(n).toLocaleString('ko-KR', { minimumFractionDigits: digits, maximumFractionDigits: digits });
    const suffix = unit === '%' ? '%p' : '억';
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

  function setGeneralVisible(show) {
    const modal = document.getElementById('management-report-modal');
    if (!modal) return;
    const status = document.getElementById('mr-status');
    const summary = document.getElementById('mr-summary');
    const table = modal.querySelector('.mr-table-card');
    if (status) status.style.display = show ? '' : 'none';
    if (summary) summary.style.display = show ? '' : 'none';
    if (table) table.style.display = show ? '' : 'none';
  }

  function restoreSection(section) {
    const miContent = document.getElementById('mi-content');
    if (section === 'general') {
      setGeneralVisible(true);
      if (miContent) miContent.hidden = true;
    } else {
      setGeneralVisible(false);
      if (miContent) miContent.hidden = false;
    }
  }

  function activatePeer() {
    if (!ensureUI()) return;
    peerActive = true;
    document.getElementById('management-report-modal')?.classList.add('mp-peer-active');
    document.querySelectorAll('#mi-section-tabs [data-mi-section]').forEach(btn => {
      btn.classList.toggle('is-active', btn.dataset.miSection === PEER_KEY);
    });
    setGeneralVisible(false);
    const miContent = document.getElementById('mi-content');
    if (miContent) miContent.hidden = true;
    const content = document.getElementById('mp-content');
    if (content) content.hidden = false;
    loadPeer();
  }

  function deactivatePeer(section) {
    peerActive = false;
    document.getElementById('management-report-modal')?.classList.remove('mp-peer-active');
    const content = document.getElementById('mp-content');
    if (content) content.hidden = true;
    if (section) restoreSection(section);
  }

  function exportPeer() {
    if (!peerActive) return;
    const mode = isCompareMode() ? 'compare' : 'single';
    const base = currentBase();
    const compare = currentCompare();
    if (!base || (mode === 'compare' && (!compare || compare === base))) return;
    const params = new URLSearchParams({ mode, base });
    if (mode === 'compare') params.set('compare', compare);
    window.location.href = `/api/management-peer/export.xlsx?${params.toString()}`;
  }

  function avgDiff(data, key) {
    const a = num(getMetric(data.woori, key).base);
    const b = num(data.peer_average?.[key]);
    return a !== null && b !== null ? a - b : null;
  }

  function signedText(value, unit) {
    const n = num(value);
    if (n === null) return '-';
    const digits = unit === '억원' ? 0 : 2;
    const body = Math.abs(n).toLocaleString('ko-KR', { minimumFractionDigits: digits, maximumFractionDigits: digits });
    return `${n >= 0 ? '+' : '-'}${body}${unit === '%' ? '%p' : '억'}`;
  }

  function summaryBar(data) {
    const ranks = data.woori_peer_ranks || {};
    const items = [
      ['총자산', ranks.total_assets],
      ['총예수금', ranks.deposits],
      ['BIS', ranks.bis_ratio],
      ['연체율', ranks.delinquency_ratio],
      ['ROE', ranks.roe],
    ];
    return `<div class="mp-summary-bar">
      <span class="mp-summary-prefix">우리금융 Peer 위치</span>
      ${items.map(([label, rank]) => `<span class="mp-summary-item"><b>${esc(label)}</b> ${esc(peerRankText(rank))}</span>`).join('')}
    </div>`;
  }

  function insightHtml(data) {
    const bisGap = avgDiff(data, 'bis_ratio');
    const delinGap = avgDiff(data, 'delinquency_ratio');
    const roeGap = avgDiff(data, 'roe');
    return `<div class="mp-insight">
      <span class="mp-insight-title">우리금융 Peer 인사이트</span>
      <span class="mp-insight-text">BIS 평균 대비 <b>${esc(signedText(bisGap, '%'))}</b> · 연체율 <b>${esc(signedText(delinGap, '%'))}</b> · ROE(산출) <b>${esc(signedText(roeGap, '%'))}</b></span>
      <span class="mp-insight-help">연체율은 낮을수록 양호</span>
    </div>`;
  }

  function fieldHeader(field) {
    const compareLabel = field.compare_quarter
      ? `${field.delta_label || ''} ${field.compare_quarter}`
      : (field.delta_label || '');
    return `<th data-mp-field="${esc(field.key)}">
      <strong>${esc(field.label)}</strong>
      <small>${esc(field.unit)}${compareLabel ? ` · ${esc(compareLabel)}` : ''}</small>
    </th>`;
  }

  function metricCell(peer, field) {
    const pack = getMetric(peer, field.key);
    return `<td data-mp-field="${esc(field.key)}">
      <div class="mp-cell-value">${esc(fmt(pack.base, field.unit))}${field.unit === '억원' && num(pack.base) !== null ? '<span class="mp-unit">억</span>' : ''}</div>
      <div class="mp-cell-delta">${deltaHtml(pack.delta, field.unit)}</div>
    </td>`;
  }

  function bankCell(peer) {
    const rank = peer.industry_asset_rank ? `업권 자산 ${peer.industry_asset_rank}위` : '';
    return `<td class="mp-bank-col"><strong>${esc(peer.label)}</strong><small>${esc(rank)}</small></td>`;
  }

  function comparisonTable(data) {
    const fields = data.fields || [];
    const peers = data.peers || [];
    const headers = fields.map(fieldHeader).join('');
    const rows = peers.map(peer => `<tr class="${peer.id === 'woori' ? 'mp-woori-row' : ''}" data-peer-id="${esc(peer.id)}">
      ${bankCell(peer)}
      ${fields.map(field => metricCell(peer, field)).join('')}
    </tr>`).join('');

    return `<div class="mp-table-wrap">
      <table class="mp-table">
        <thead><tr><th class="mp-bank-col">금융사</th>${headers}</tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
  }

  function render(data) {
    if (!data?.ok) return `<div class="mi-warmup">4대금융 비교 데이터를 불러오지 못했습니다.<br>${esc(data?.error || '')}</div>`;
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
      ${summaryBar(data)}
      ${insightHtml(data)}
      <div class="mp-table-head"><strong>4개사 핵심 경영지표</strong><span>현재값 아래에 비교기준 증감 표시</span></div>
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
    const params = new URLSearchParams({ mode, base });
    if (mode === 'compare') params.set('compare', compare);
    try {
      const response = await fetch(`/api/management-peer?${params.toString()}`, { cache: 'no-store' });
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
        const key = section.dataset.miSection;
        if (key === PEER_KEY) {
          event.preventDefault();
          activatePeer();
        } else {
          deactivatePeer(key);
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
    }, 50);
  });
  observer.observe(document.documentElement, { childList: true, subtree: true });

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true });
  else boot();
})();
