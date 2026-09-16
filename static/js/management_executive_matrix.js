(() => {
  'use strict';

  const state = {
    quarters: [],
    selected: '',
    autoOpened: false,
    industryLoadedQuarter: '',
  };

  const INDUSTRY_FIELDS = [
    { key: 'total_assets', label: '총자산' },
    { key: 'total_loans', label: '총여신' },
    { key: 'bis_ratio', label: 'BIS' },
    { key: 'delinquency_ratio', label: '연체율' },
    { key: 'npl_ratio', label: 'NPL' },
    { key: 'net_income', label: '당기순이익' },
  ];

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
    if (!Number.isFinite(value)) return '-';
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

  function closeModal() {
    document.getElementById('management-report-modal')
      ?.querySelector('#mr-close')?.click();
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
      <div id="mx-peer-sheet" class="mx-sheet">
        <div class="mx-sheet-titlebar">
          <div>
            <strong>4대 금융지주 저축은행 경영현황</strong>
            <span id="mx-source">금융감독원 FISIS 기준</span>
          </div>
          <div class="mx-sheet-actions">
            <button type="button" id="mx-detail">전체업권 상세</button>
            <button type="button" id="mx-close" aria-label="닫기">×</button>
          </div>
        </div>

        <div class="mx-sheet-toolbar">
          <label>조회분기
            <select id="mx-quarter"></select>
          </label>
          <button type="button" id="mx-refresh">조회</button>
          <span id="mx-coverage">데이터 확인중</span>
        </div>

        <div class="mx-table-wrap">
          <table class="mx-table" aria-label="4대 금융지주 저축은행 경영현황 비교">
            <thead>
              <tr class="mx-title-row">
                <th colspan="2">구분</th>
                <th>우리금융</th>
                <th>신한</th>
                <th>하나</th>
                <th>KB</th>
              </tr>
            </thead>
            <tbody id="mx-body"></tbody>
          </table>
        </div>

        <div class="mx-bottom">
          <div id="mx-insights" class="mx-insights"></div>
          <div id="mx-note" class="mx-note"></div>
        </div>
      </div>

      <section id="mx-industry-detail" class="mx-industry-detail" aria-hidden="true" hidden>
        <div class="mx-industry-head">
          <div class="mx-industry-heading">
            <span class="mx-industry-kicker">INDUSTRY DETAIL</span>
            <strong>전체 업권 상세</strong>
            <span id="mx-industry-source">금융감독원 FISIS 기준</span>
          </div>
          <div class="mx-industry-head-actions">
            <button type="button" id="mx-industry-back">← 4대금융 비교</button>
            <button type="button" id="mx-industry-close" aria-label="닫기">×</button>
          </div>
        </div>

        <div class="mx-industry-toolbar">
          <label>조회분기
            <select id="mx-industry-quarter"></select>
          </label>
          <button type="button" id="mx-industry-refresh">조회</button>
          <span id="mx-industry-status">데이터 확인중</span>
        </div>

        <div id="mx-industry-summary" class="mx-industry-summary">
          <article><span>업권 기관수</span><strong>-</strong><small>저축은행</small></article>
          <article><span>우리금융 자산순위</span><strong>-</strong><small>총자산 기준</small></article>
          <article><span>우리금융 총자산</span><strong>-</strong><small>억원</small></article>
          <article><span>우리금융 연체율</span><strong>-</strong><small>FISIS 기준</small></article>
        </div>

        <div class="mx-industry-table-gate">
          <div>
            <strong>업권현황 표</strong>
            <span>필요할 때만 상세표를 열어 전체 저축은행을 비교합니다.</span>
          </div>
          <button type="button" id="mx-industry-table-toggle" aria-expanded="false">업권현황 표 보기</button>
        </div>

        <section id="mx-industry-table-section" class="mx-industry-table-section" hidden>
          <div class="mx-industry-table-wrap" role="region" aria-label="전체 업권 경영현황 표" tabindex="0">
            <table id="mx-industry-table" class="mx-industry-table">
              <thead>
                <tr>
                  <th>순위</th>
                  <th>저축은행</th>
                  <th>총자산</th>
                  <th>총여신</th>
                  <th>BIS</th>
                  <th>연체율</th>
                  <th>NPL</th>
                  <th>당기순이익</th>
                </tr>
              </thead>
              <tbody id="mx-industry-body"></tbody>
            </table>
          </div>
          <div id="mx-industry-note" class="mx-industry-note"></div>
        </section>
      </section>
    `;
    shell.appendChild(panel);

    panel.querySelector('#mx-close').addEventListener('click', closeModal);
    panel.querySelector('#mx-detail').addEventListener('click', openIndustryDetail);
    panel.querySelector('#mx-refresh').addEventListener('click', () => loadMatrix());
    panel.querySelector('#mx-quarter').addEventListener('change', (event) => {
      state.selected = event.target.value;
      syncQuarterSelects();
    });

    panel.querySelector('#mx-industry-close').addEventListener('click', closeModal);
    panel.querySelector('#mx-industry-back').addEventListener('click', closeIndustryDetail);
    panel.querySelector('#mx-industry-refresh').addEventListener('click', () => {
      state.selected = panel.querySelector('#mx-industry-quarter')?.value || state.selected;
      syncQuarterSelects();
      loadIndustryDetail();
    });
    panel.querySelector('#mx-industry-quarter').addEventListener('change', (event) => {
      state.selected = event.target.value;
      syncQuarterSelects();
    });
    panel.querySelector('#mx-industry-table-toggle').addEventListener('click', toggleIndustryTable);
  }

  function ensureLegacyTab() {
    const tabs = document.querySelector('#management-report-modal .mr-mode-tabs');
    if (!tabs || document.getElementById('mx-launch')) return;

    const btn = document.createElement('button');
    btn.type = 'button';
    btn.id = 'mx-launch';
    btn.className = 'mr-mode-tab mx-launch is-active';
    btn.textContent = '4대금융 비교';
    btn.title = '우리금융·신한·하나·KB 임원보고형 비교표';
    btn.addEventListener('click', openPanel);
    tabs.insertBefore(btn, tabs.firstChild);
  }

  function syncQuarterSelects() {
    ['mx-quarter', 'mx-industry-quarter'].forEach(id => {
      const select = document.getElementById(id);
      if (!select) return;
      select.innerHTML = state.quarters.map(item =>
        `<option value="${esc(item.key)}">${esc(item.label)}</option>`
      ).join('');
      if (state.selected) select.value = state.selected;
    });
  }

  function fillQuarterSelect() {
    syncQuarterSelects();
  }

  async function loadQuarters() {
    if (state.quarters.length) {
      syncQuarterSelects();
      return;
    }
    const data = await fetchJson('/api/management-report/quarters');
    state.quarters = Array.isArray(data.quarters) ? data.quarters : [];
    const current = document.getElementById('mr-single-quarter')?.value
      || document.getElementById('mr-base-quarter')?.value;
    state.selected = current || state.quarters[0]?.key || '';
    fillQuarterSelect();
  }

  function renderInsights(data) {
    const box = document.getElementById('mx-insights');
    if (!box) return;
    const strengths = data.insights?.strengths || [];
    const watchpoints = data.insights?.watchpoints || [];

    const parts = [];
    if (strengths.length) parts.push('<b>강점</b> ' + strengths.slice(0, 3).map(esc).join(' · '));
    if (watchpoints.length) parts.push('<b>점검</b> ' + watchpoints.slice(0, 3).map(esc).join(' · '));
    if (!parts.length) parts.push(esc(data.insights?.summary || '-'));

    box.innerHTML = '<strong>핵심 해석</strong><span>' + parts.join(' &nbsp; | &nbsp; ') + '</span>';
  }

  function categoryLabel(category) {
    const map = {
      '규모·여신': '① 규모·여신',
      '수신·조달': '② 수신·조달',
      '수익성': '③ 수익성',
      '건전성': '④ 건전성'
    };
    return map[category] || category;
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
        categoryCell = `<th class="mx-category" rowspan="${categoryCounts[row.category]}">${esc(categoryLabel(row.category))}</th>`;
      }

      const cells = peerIds.map(peerId => {
        const pack = row.values?.[peerId] || {};
        const rank = Number(row.ranks?.[peerId]);
        const best = rank === 1 && Number(row.available_peer_count || 0) >= 3;
        const cellClass = [
          'mx-value-cell',
          peerId === 'woori' ? 'mx-woori-cell' : '',
          best ? 'mx-best' : ''
        ].filter(Boolean).join(' ');

        const rankHtml = Number.isFinite(rank)
          ? `<span class="mx-rank">${rank}위</span>`
          : '';
        const delta = deltaText(pack, row.unit);
        const deltaHtml = delta !== '-'
          ? `<span class="mx-delta ${deltaClass(pack, row.direction)}">${esc(pack.compare_basis || '')} ${esc(delta)}</span>`
          : '<span class="mx-delta mx-delta-flat">-</span>';

        return `
          <td class="${cellClass}">
            <div class="mx-number">${fmt(pack.base, row.unit)}${pack.base != null && row.unit === '억원' ? '<small>억원</small>' : ''}</div>
            <div class="mx-meta">${rankHtml}${deltaHtml}</div>
          </td>
        `;
      }).join('');

      const basis = row.direction === 'neutral'
        ? '참고'
        : (row.direction === 'lower' ? '낮을수록 양호' : '높을수록 우위');

      return `
        <tr>
          ${categoryCell}
          <th class="mx-metric">
            <span>${esc(row.label)}</span>
            <small>${esc(basis)}</small>
          </th>
          ${cells}
        </tr>
      `;
    }).join('');
  }

  function renderNotes(data) {
    const node = document.getElementById('mx-note');
    if (!node) return;
    node.innerHTML =
      '<b>비교기준</b> 규모·여신 전년말比 · 수신/조달/건전성 전분기比 · 손익 전년동기比'
      + '<br><b>출처</b> 금융감독원 금융통계정보시스템(FISIS)'
      + '<br><span>※ 노란색은 4대 금융지주 중 우위(1위) 셀입니다. 검증되지 않은 비율은 표시하지 않습니다.</span>';
  }

  function comparisonQuarter(base) {
    const index = state.quarters.findIndex(item => item.key === base);
    if (index >= 0 && state.quarters[index + 1]?.key) return state.quarters[index + 1].key;
    return state.quarters.find(item => item.key !== base)?.key || base;
  }

  function industryFieldMap(data) {
    return new Map((data.fields || []).map(field => [field.key, field]));
  }

  function industryMetric(row, key) {
    return row?.metrics?.[key]?.base ?? null;
  }

  function industryValueHtml(row, key, fieldMap) {
    const value = industryMetric(row, key);
    const field = fieldMap.get(key) || {};
    const unit = field.unit || (['bis_ratio', 'delinquency_ratio', 'npl_ratio'].includes(key) ? '%' : '억원');
    const text = fmt(value, unit);
    if (text === '-') return '-';
    if (unit === '억원') return `${text}<small>억원</small>`;
    return text;
  }

  function renderIndustrySummary(data) {
    const root = document.getElementById('mx-industry-summary');
    if (!root) return;
    const rows = Array.isArray(data.rows) ? data.rows : [];
    const woori = rows.find(item => item.is_woori || String(item.bank || '').includes('우리금융'));
    const asset = industryMetric(woori, 'total_assets');
    const delinquency = industryMetric(woori, 'delinquency_ratio');

    root.innerHTML = `
      <article>
        <span>업권 기관수</span>
        <strong>${rows.length.toLocaleString('ko-KR')}개</strong>
        <small>저축은행</small>
      </article>
      <article>
        <span>우리금융 자산순위</span>
        <strong>${woori?.rank ? `${woori.rank}위` : '-'}</strong>
        <small>총자산 기준</small>
      </article>
      <article>
        <span>우리금융 총자산</span>
        <strong>${asset == null ? '-' : Math.round(Number(asset)).toLocaleString('ko-KR')}</strong>
        <small>억원</small>
      </article>
      <article>
        <span>우리금융 연체율</span>
        <strong>${delinquency == null ? '-' : Number(delinquency).toFixed(2) + '%'}</strong>
        <small>FISIS 기준</small>
      </article>
    `;
  }

  function renderIndustryTable(data) {
    const body = document.getElementById('mx-industry-body');
    if (!body) return;
    const rows = Array.isArray(data.rows) ? data.rows : [];
    const fieldMap = industryFieldMap(data);

    body.innerHTML = rows.map(item => {
      const isWoori = item.is_woori || String(item.bank || '').includes('우리금융');
      return `
        <tr class="${isWoori ? 'mx-industry-woori' : ''}">
          <td class="mx-industry-rank">${item.rank || '-'}</td>
          <td class="mx-industry-bank">
            <strong>${esc(item.bank || '-')}</strong>
            <span>${esc(item.region || '-')}</span>
          </td>
          ${INDUSTRY_FIELDS.map(field => `
            <td class="mx-industry-number" data-field="${field.key}">
              ${industryValueHtml(item, field.key, fieldMap)}
            </td>
          `).join('')}
        </tr>
      `;
    }).join('');

    const note = document.getElementById('mx-industry-note');
    if (note) {
      note.innerHTML =
        `<b>기준</b> ${esc(data.base_label || data.base || '-')} · 총자산 순위 기준`
        + ` &nbsp; <b>출처</b> ${esc(data.source_name || data.source || '금융감독원 금융통계정보시스템(FISIS)')}`
        + '<br><span>※ 우리금융저축은행은 파란색으로 고정 강조합니다. 모바일에서는 표 영역을 좌우로 스크롤해 전체 지표를 확인할 수 있습니다.</span>';
    }
  }

  async function loadIndustryDetail() {
    const quarter = state.selected || document.getElementById('mx-industry-quarter')?.value || '';
    const status = document.getElementById('mx-industry-status');
    const body = document.getElementById('mx-industry-body');
    if (!quarter) return;

    if (status) status.textContent = '전체 업권 데이터를 불러오는 중';
    if (body) body.innerHTML = '<tr><td colspan="8" class="mx-industry-loading">데이터를 불러오고 있습니다.</td></tr>';

    try {
      const compare = comparisonQuarter(quarter);
      const data = await fetchJson(
        '/api/management-report?base=' + encodeURIComponent(quarter)
        + '&compare=' + encodeURIComponent(compare)
      );
      state.industryLoadedQuarter = quarter;
      renderIndustrySummary(data);
      renderIndustryTable(data);

      const source = document.getElementById('mx-industry-source');
      if (source) {
        source.textContent = `${data.source_name || '금융감독원 FISIS'} · ${data.base_label || data.base || quarter}`;
      }
      if (status) status.textContent = `${data.base_label || data.base || quarter} · ${Array.isArray(data.rows) ? data.rows.length : 0}개 기관`;
    } catch (error) {
      if (status) status.textContent = '조회 실패';
      if (body) {
        body.innerHTML = `<tr><td colspan="8" class="mx-error">${esc(error.message)}</td></tr>`;
      }
    }
  }

  function resetIndustryTableGate() {
    const section = document.getElementById('mx-industry-table-section');
    const button = document.getElementById('mx-industry-table-toggle');
    if (section) section.hidden = true;
    if (button) {
      button.setAttribute('aria-expanded', 'false');
      button.textContent = '업권현황 표 보기';
    }
  }

  function toggleIndustryTable() {
    const section = document.getElementById('mx-industry-table-section');
    const button = document.getElementById('mx-industry-table-toggle');
    if (!section || !button) return;
    section.hidden = !section.hidden;
    button.setAttribute('aria-expanded', section.hidden ? 'false' : 'true');
    button.textContent = section.hidden ? '업권현황 표 보기' : '업권현황 표 닫기';
    if (!section.hidden) {
      section.querySelector('.mx-industry-table-wrap')?.focus({ preventScroll: true });
    }
  }

  async function openIndustryDetail() {
    ensurePanel();
    await loadQuarters();

    const sheet = document.getElementById('mx-peer-sheet');
    const detail = document.getElementById('mx-industry-detail');
    if (!detail) return;

    if (sheet) sheet.hidden = true;
    detail.hidden = false;
    detail.setAttribute('aria-hidden', 'false');
    syncQuarterSelects();
    resetIndustryTableGate();
    await loadIndustryDetail();
  }

  function closeIndustryDetail() {
    const sheet = document.getElementById('mx-peer-sheet');
    const detail = document.getElementById('mx-industry-detail');
    if (detail) {
      detail.hidden = true;
      detail.setAttribute('aria-hidden', 'true');
    }
    if (sheet) sheet.hidden = false;
    resetIndustryTableGate();
  }

  async function loadMatrix() {
    const quarter = state.selected || document.getElementById('mx-quarter')?.value || '';
    const coverage = document.getElementById('mx-coverage');
    if (coverage) coverage.textContent = '불러오는 중';

    try {
      const data = await fetchJson('/api/management-executive-matrix?base=' + encodeURIComponent(quarter));
      state.selected = data.base || quarter;
      fillQuarterSelect();
      const ratio = Number(data.coverage?.ratio || 0) * 100;
      if (coverage) {
        coverage.textContent = `데이터 ${ratio.toFixed(0)}% · ${data.base_label || data.base}`;
        coverage.classList.toggle('is-ready', !!data.ready);
      }
      const source = document.getElementById('mx-source');
      if (source) source.textContent =
        `${data.source} · ${data.base_label || data.base} · 기준일 ${data.as_of || '-'}`;
      renderTable(data);
      renderInsights(data);
      renderNotes(data);
    } catch (error) {
      if (coverage) coverage.textContent = '조회 실패';
      const body = document.getElementById('mx-body');
      if (body) body.innerHTML =
        `<tr><td colspan="6" class="mx-error">${esc(error.message)}</td></tr>`;
    }
  }

  async function openPanel() {
    ensurePanel();
    ensureLegacyTab();

    const panel = document.getElementById('management-executive-matrix');
    if (!panel) return;

    panel.classList.add('is-open');
    panel.setAttribute('aria-hidden', 'false');
    closeIndustryDetail();

    document.querySelectorAll('#management-report-modal [data-mr-mode]')
      .forEach(btn => btn.classList.remove('is-active'));
    document.getElementById('mx-launch')?.classList.add('is-active');

    try {
      await loadQuarters();
      await loadMatrix();
    } catch (error) {
      const coverage = document.getElementById('mx-coverage');
      if (coverage) coverage.textContent = '조회 실패 · ' + error.message;
    }
  }

  function closePanel() {
    const panel = document.getElementById('management-executive-matrix');
    if (!panel) return;
    closeIndustryDetail();
    panel.classList.remove('is-open');
    panel.setAttribute('aria-hidden', 'true');
    document.getElementById('mx-launch')?.classList.remove('is-active');

    const activeLegacy = document.querySelector('#management-report-modal [data-mr-mode].is-active');
    if (!activeLegacy) {
      document.querySelector('#management-report-modal [data-mr-mode="single"]')?.classList.add('is-active');
    }
  }

  function autoOpenFromManagementButton(event) {
    const target = event.target?.closest?.('#management-report-open, #management-report-open-mobile');
    if (!target) return;
    setTimeout(() => {
      ensurePanel();
      ensureLegacyTab();
      openPanel();
    }, 0);
  }

  function wire() {
    ensurePanel();
    ensureLegacyTab();
  }

  document.addEventListener('click', autoOpenFromManagementButton, true);

  const observer = new MutationObserver(wire);
  observer.observe(document.documentElement, { childList: true, subtree: true });
  wire();
})();
