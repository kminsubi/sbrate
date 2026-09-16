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
    if (unit === 'ìµì') {
      const digits = Math.abs(n) >= 100 ? 0 : Math.abs(n) >= 10 ? 1 : 2;
      return n.toLocaleString('ko-KR', { minimumFractionDigits: digits, maximumFractionDigits: digits });
    }
    if (unit === '%') return `${n.toLocaleString('ko-KR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`;
    return n.toLocaleString('ko-KR');
  }

  function deltaHtml(value, unit) {
    const n = num(value);
    if (n === null || Math.abs(n) < 0.0000001) return '<span class="mp-delta mp-flat">-</span>';
    const digits = unit === 'ìµì' ? (Math.abs(n) >= 100 ? 0 : 1) : 2;
    const body = Math.abs(n).toLocaleString('ko-KR', { minimumFractionDigits: digits, maximumFractionDigits: digits });
    const suffix = unit === '%' ? '%p' : 'ìµ';
    return n > 0
      ? `<span class="mp-delta mp-up">+${body}${suffix}</span>`
      : `<span class="mp-delta mp-down">â²${body}${suffix}</span>`;
  }

  function peerRankText(rank) {
    return rank ? `${rank}/4ì` : '-';
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
      tab.textContent = '4ëê¸ìµ ë¹êµ';
      tab.title = 'ì°ë¦¬ê¸ìµÂ·ì íÂ·íëÂ·KB ì ì¶ìí ë¹êµ';
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
    const digits = unit === 'ìµì' ? 0 : 2;
    const body = Math.abs(n).toLocaleString('ko-KR', { minimumFractionDigits: digits, maximumFractionDigits: digits });
    return `${n >= 0 ? '+' : '-'}${body}${unit === '%' ? '%p' : 'ìµ'}`;
  }

  function summaryBar(data) {
    const ranks = data.woori_peer_ranks || {};
    const items = [
      ['ì´ìì°', ranks.total_assets],
      ['ì´ììê¸', ranks.deposits],
      ['BIS', ranks.bis_ratio],
      ['ì°ì²´ì¨', ranks.delinquency_ratio],
      ['ROE', ranks.roe],
    ];
    return `<div class="mp-summary-bar">
      <span class="mp-summary-prefix">ì°ë¦¬ê¸ìµ Peer ìì¹</span>
      ${items.map(([label, rank]) => `<span class="mp-summary-item"><b>${esc(label)}</b> ${esc(peerRankText(rank))}</span>`).join('')}
    </div>`;
  }

  function insightHtml(data) {
    const bisGap = avgDiff(data, 'bis_ratio');
    const delinGap = avgDiff(data, 'delinquency_ratio');
    const roeGap = avgDiff(data, 'roe');
    return `<div class="mp-insight">
      <span class="mp-insight-title">ì°ë¦¬ê¸ìµ Peer ì¸ì¬ì´í¸</span>
      <span class="mp-insight-text">BIS íê·  ëë¹ <b>${esc(signedText(bisGap, '%'))}</b> Â· ì°ì²´ì¨ <b>${esc(signedText(delinGap, '%'))}</b> Â· ROE(ì°ì¶) <b>${esc(signedText(roeGap, '%'))}</b></span>
      <span class="mp-insight-help">ì°ì²´ì¨ì ë®ììë¡ ìí¸</span>
    </div>`;
  }

  function fieldHeader(field) {
    const compareLabel = field.compare_quarter
      ? `${field.delta_label || ''} ${field.compare_quarter}`
      : (field.delta_label || '');
    return `<th data-mp-field="${esc(field.key)}">
      <strong>${esc(field.label)}</strong>
      <small>${esc(field.unit)}${compareLabel ? ` Â· ${esc(compareLabel)}` : ''}</small>
    </th>`;
  }

  function metricCell(peer, field) {
    const pack = getMetric(peer, field.key);
    return `<td data-mp-field="${esc(field.key)}">
      <div class="mp-cell-value">${esc(fmt(pack.base, field.unit))}${field.unit === 'ìµì' && num(pack.base) !== null ? '<span class="mp-unit">ìµ</span>' : ''}</div>
      <div class="mp-cell-delta">${deltaHtml(pack.delta, field.unit)}</div>
    </td>`;
  }

  function bankCell(peer) {
    const rank = peer.industry_asset_rank ? `ìê¶ ìì° ${peer.industry_asset_rank}ì` : '';
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
        <thead><tr><th class="mp-bank-col">ê¸ìµì¬</th>${headers}</tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
  }

  function render(data) {
    if (!data?.ok) return `<div class="mi-warmup">4ëê¸ìµ ë¹êµ ë°ì´í°ë¥¼ ë¶ë¬ì¤ì§ ëª»íìµëë¤.<br>${esc(data?.error || '')}</div>`;
    const warning = (data.missing_peers || []).length
      ? `<div class="mp-warning">ì¼ë¶ Peer ë°ì´í°ê° ììµëë¤: ${esc(data.missing_peers.join(', '))}</div>`
      : '';

    return `<section class="mp-panel">
      <div class="mp-heading">
        <div>
          <div class="mp-eyebrow">FINANCIAL GROUP PEER</div>
          <h3>4ë ê¸ìµì§ì£¼ ì ì¶ìí ë¹êµ</h3>
          <p>${esc(data.base_label || data.base || '-')} Â· ${esc(data.as_of || '-')} ê¸°ì¤ Â· ì°ë¦¬ê¸ìµ â ì í â íë â KB</p>
        </div>
        <div class="mp-heading-actions">
          <div class="mp-mode-badge">${data.mode === 'compare' ? `${esc(data.base || '')} vs ${esc(data.compare || '')}` : 'ë¶ê¸°íí©'}</div>
          <button type="button" id="mp-export" class="mr-secondary-btn mp-export-btn">â¬ Excel ë¤ì´ë¡ë</button>
        </div>
      </div>
      ${warning}
      ${summaryBar(data)}
      ${insightHtml(data)}
      <div class="mp-table-head"><strong>4ê°ì¬ íµì¬ ê²½ìì§í</strong><span>íì¬ê° ìëì ë¹êµê¸°ì¤ ì¦ê° íì</span></div>
      ${comparisonTable(data)}
      <div class="mp-note">${esc(data.notes?.comparison_basis || '')}<br>${esc(data.notes?.roa_roe || '')}<br>ì¶ì²: ${esc(data.source || 'ê¸ìµê°ëì ê¸ìµíµê³ì ë³´ìì¤í(FISIS)')}</div>
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
      content.innerHTML = '<div class="mi-warmup">ì¡°íí  ë¶ê¸°ë¥¼ ì íí´ ì£¼ì¸ì.</div>';
      return;
    }
    const seq = ++loadSeq;
    content.innerHTML = '<div class="mi-warmup">4ë ê¸ìµì§ì£¼ ì ì¶ìí ë°ì´í°ë¥¼ ë¹êµíê³  ììµëë¤.</div>';
    const params = new URLSearchParams({ mode, base });
    if (mode === 'compare') params.set('compare', compare);
    try {
      const response = await fetch(`/api/management-peer?${params.toString()}`, { cache: 'no-store' });
      const data = await response.json();
      if (seq !== loadSeq || !peerActive) return;
      content.innerHTML = render(data);
    } catch (error) {
      if (seq !== loadSeq || !peerActive) return;
      content.innerHTML = `<div class="mi-warmup">4ëê¸ìµ ë¹êµ ë°ì´í°ë¥¼ ë¶ë¬ì¤ì§ ëª»íìµëë¤.<br>${esc(error?.message || error)}</div>`;
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
        // The FISIS modal renders its tabs asynchronously.  Activate the peer
        // comparison after each render phase so management always lands on the
        // intended default instead of briefly falling back to ê²½ìì§í.
        [160, 500, 1100].forEach(delay => {
          setTimeout(() => {
            const modal = document.getElementById('management-report-modal');
            if (!modal || modal.hidden) return;
            ensureUI();
            activatePeer();
          }, delay);
        });
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
