(() => {
  'use strict';

  const state = { quarters: [], selected: '' };

  function esc(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function fmt(value, unit) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
    const n = Number(value);
    if (unit === '%') return n.toFixed(2) + '%';
    return Math.round(n).toLocaleString('ko-KR');
  }

  function deltaText(pack, unit) {
    const value = Number(pack?.delta);
    if (!Number.isFinite(value)) return '';
    const prefix = value > 0 ? '+' : value < 0 ? '▲' : '';
    const abs = Math.abs(value);
    const body = unit === '%' ? abs.toFixed(2) + '%p' : Math.round(abs).toLocaleString('ko-KR');
    return prefix + body;
  }

  function deltaClass(pack, direction) {
    const value = Number(pack?.delta);
    if (!Number.isFinite(value) || value === 0 || direction === 'neutral') return 'mx-delta-flat';
    const improved = direction === 'lower' ? value < 0 : value > 0;
    return improved ? 'mx-delta-good' : 'mx-delta-bad';
  }

  async function fetchJson(url) {
    const response = await fetch(url, { cache: 'no-store' });
    const data = await response.json().catch(() => null);
    if (!response.ok || !data || data.ok === false) {
      throw new Error(data?.error || ('HTTP ' + response.status));
    }
    return data;
  }

  function ensurePanel() {
    if (document.getElementById('management-executive-matrix')) return;
    const shell = document.querySelector('#management-report-modal .mr-shell');
    if (!shell) return;

    const panel = document.createElement('section');
    panel.id = 'management-executive-matrix';
    panel.className = 'mx-panel';
    panel.setAttribute('aria-hidden', 'true');
    panel.innerHTML = `
      <div class="mx-head">
        <div>
          <div class="mx-eyebrow">EXECUTIVE PEER MATRIX</div>
          <h3>4대 금융지주 저축은행 경영현황</h3>
          <p id="mx-source">FISIS 기준 · 우리금융 / 신한 / 하나 / KB</p>
        </div>
        <button type="button" id="mx-close" class="mx-close" aria-label="닫기">×</button>
      </div>
      <div class="mx-controls">
        <label><span>조회분기</span><select id="mx-quarter"></select></label>
        <button type="button" id="mx-refresh">조회</button>
        <span id="mx-coverage" class="mx-coverage">데이터 확인중</span>
      </div>
      <div id="mx-insights" class="mx-insights"></div>
      <div class="mx-table-wrap">
        <table class="mx-table">
          <thead>
            <tr>
              <th class="mx-cat-col">구분</th>
              <th class="mx-metric-col">지표</th>
              <th class="mx-woori-col">우리금융</th>
              <th>신한</th>
              <th>하나</th>
              <th>KB</th>
            </tr>
          </thead>
          <tbody id="mx-body"></tbody>
        </table>
      </div>
      <div id="mx-note" class="mx-note"></div>
    `;
    shell.appendChild(panel);

    panel.querySelector('#mx-close').addEventListener('click', closePanel);
    panel.querySelector('#mx-refresh').addEventListener('click', () => loadMatrix());
    panel.querySelector('#mx-quarter').addEventListener('change', (event) => {
      state.selected = event.target.value;
    });
  }

  function ensureLaunchButton() {
    const tabs = document.querySelector('#management-report-modal .mr-mode-tabs');
    if (!tabs || document.getElementById('mx-launch')) return;
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.id = 'mx-launch';
    btn.className = 'mr-mode-tab mx-launch';
    btn.textContent = '4대금융 Matrix';
    btn.title = '우리금융·신한·하나·KB 임원형 비교표';
    btn.addEventListener('click', openPanel);
    tabs.appendChild(btn);
  }

  function fillQuarterSelect() {
    const select = document.getElementById('mx-quarter');
    if (!select) return;
    select.innerHTML = state.quarters.map(item =>
      `<option value="${esc(item.key)}">${esc(item.label)}</option>`
    ).join('');
    if (state.selected) select.value = state.selected;
  }

  async function loadQuarters() {
    if (state.quarters.length) return;
    const data = await fetchJson('/api/management-report/quarters');
    state.quarters = Array.isArray(data.quarters) ? data.quarters : [];
    const current = document.getElementById('mr-single-quarter')?.value
      || document.getElementById('mr-base-quarter')?.value;
    state.selected = current || state.quarters[0]?.key || '';
    fillQuarterSelect();
  }

  function renderInsights(data) {
    const box = document.getElementById('mx-insights');
    const strengths = data.insights?.strengths || [];
    const watchpoints = data.insights?.watchpoints || [];
    box.innerHTML = `
      <div class="mx-insight-summary">
        <strong>핵심 해석</strong>
        <span>${esc(data.insights?.summary || '-')}</span>
      </div>
      <div class="mx-chip-row">
        ${strengths.slice(0, 3).map(x => `<span class="mx-chip mx-chip-good">강점 · ${esc(x)}</span>`).join('')}
        ${watchpoints.slice(0, 3).map(x => `<span class="mx-chip mx-chip-watch">점검 · ${esc(x)}</span>`).join('')}
      </div>
    `;
  }

  function renderTable(data) {
    const body = document.getElementById('mx-body');
    const rows = Array.isArray(data.rows) ? data.rows : [];
    const categoryCounts = rows.reduce((acc, row) => {
      acc[row.category] = (acc[row.category] || 0) + 1;
      return acc;
    }, {});
    const categorySeen = new Set();
    const peerIds = ['woori', 'shinhan', 'hana', 'kb'];

    body.innerHTML = rows.map(row => {
      let categoryCell = '';
      if (!categorySeen.has(row.category)) {
        categorySeen.add(row.category);
        categoryCell = `<th class="mx-category" rowspan="${categoryCounts[row.category]}">${esc(row.category)}</th>`;
      }
      const cells = peerIds.map(peerId => {
        const pack = row.values?.[peerId] || {};
        const rank = row.ranks?.[peerId];
        const rankText = Number.isFinite(Number(rank))
          ? `<span class="mx-rank">4대금융 ${rank}위</span>`
          : '';
        const bestClass = Number(rank) === 1 ? ' mx-best' : '';
        const wooriClass = peerId === 'woori' ? ' mx-woori-cell' : '';
        const delta = deltaText(pack, row.unit);
        const deltaHtml = delta
          ? `<span class="mx-delta ${deltaClass(pack, row.direction)}">${esc(pack.compare_basis || '')} ${esc(delta)}</span>`
          : '<span class="mx-delta mx-delta-flat">비교 -</span>';
        return `
          <td class="mx-value-cell${bestClass}${wooriClass}">
            <div class="mx-value">${fmt(pack.base, row.unit)}${pack.base != null && row.unit === '억원' ? '<small>억원</small>' : ''}</div>
            <div class="mx-cell-meta">${rankText}${deltaHtml}</div>
          </td>
        `;
      }).join('');
      return `
        <tr>
          ${categoryCell}
          <th class="mx-metric">
            <span>${esc(row.label)}</span>
            <small>${esc(row.direction === 'neutral' ? '참고지표' : (row.direction === 'lower' ? '낮을수록 양호' : '높을수록 우위'))}</small>
          </th>
          ${cells}
        </tr>
      `;
    }).join('');
  }

  function renderNotes(data) {
    const pending = (data.phase2_pending || []).join(' · ');
    document.getElementById('mx-note').innerHTML = `
      <strong>기준</strong> ${esc(data.notes?.size_basis || '')}
      · ${esc(data.notes?.funding_soundness_basis || '')}
      · ${esc(data.notes?.profitability_basis || '')}
      <br><strong>2단계 확장</strong> ${esc(pending || '-')}
      <span class="mx-note-muted"> — 원천 계정코드 검증 전에는 수치를 만들지 않습니다.</span>
    `;
  }

  async function loadMatrix() {
    const quarter = state.selected || document.getElementById('mx-quarter')?.value || '';
    const coverage = document.getElementById('mx-coverage');
    coverage.textContent = '불러오는 중';
    try {
      const data = await fetchJson('/api/management-executive-matrix?base=' + encodeURIComponent(quarter));
      state.selected = data.base || quarter;
      const ratio = Number(data.coverage?.ratio || 0) * 100;
      coverage.textContent = `데이터 충족 ${ratio.toFixed(0)}% · ${data.base_label || data.base}`;
      coverage.classList.toggle('is-ready', !!data.ready);
      document.getElementById('mx-source').textContent =
        `${data.source} · ${data.base_label || data.base} · 기준일 ${data.as_of || '-'}`;
      renderInsights(data);
      renderTable(data);
      renderNotes(data);
    } catch (error) {
      coverage.textContent = '조회 실패';
      document.getElementById('mx-body').innerHTML =
        `<tr><td colspan="6" class="mx-error">${esc(error.message)}</td></tr>`;
    }
  }

  async function openPanel() {
    ensurePanel();
    const panel = document.getElementById('management-executive-matrix');
    if (!panel) return;
    panel.classList.add('is-open');
    panel.setAttribute('aria-hidden', 'false');
    try {
      await loadQuarters();
      await loadMatrix();
    } catch (error) {
      document.getElementById('mx-coverage').textContent = '조회 실패 · ' + error.message;
    }
  }

  function closePanel() {
    const panel = document.getElementById('management-executive-matrix');
    if (!panel) return;
    panel.classList.remove('is-open');
    panel.setAttribute('aria-hidden', 'true');
  }

  function wire() {
    ensureLaunchButton();
    ensurePanel();
  }

  const observer = new MutationObserver(wire);
  observer.observe(document.documentElement, { childList: true, subtree: true });
  wire();
})();
