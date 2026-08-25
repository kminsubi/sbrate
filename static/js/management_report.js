(() => {
  'use strict';

  const state = {
    quarters: [],
    single: '',
    base: '',
    compare: '',
    mode: 'compare',
    payload: null,
    mounted: false,
  };

  const moneyFields = new Set(['total_assets','corporate_loans','household_loans','total_loans','net_income']);
  const ratioFields = new Set(['bis_ratio','npl_ratio','delinquency_ratio']);
  const preferredFieldOrder = [
    'total_assets',
    'household_loans',
    'corporate_loans',
    'total_loans',
    'bis_ratio',
    'npl_ratio',
    'delinquency_ratio',
    'net_income',
    'employees',
  ];

  function el(tag, cls, text) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function fmt(value, fieldKey) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
    const num = Number(value);
    if (ratioFields.has(fieldKey)) return `${num.toFixed(2)}%`;
    if (moneyFields.has(fieldKey) || fieldKey === 'employees') return Math.round(num).toLocaleString('ko-KR');
    return num.toLocaleString('ko-KR');
  }

  function valueWithUnit(value, fieldKey) {
    const text = fmt(value, fieldKey);
    if (text === '-') return '-';
    if (moneyFields.has(fieldKey)) return `${text}억원`;
    if (fieldKey === 'employees') return `${text}명`;
    return text;
  }

  function deltaText(value, fieldKey) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
    const num = Number(value);
    const sign = num > 0 ? '+' : '';
    if (ratioFields.has(fieldKey)) return `${sign}${num.toFixed(2)}%p`;
    return `${sign}${Math.round(num).toLocaleString('ko-KR')}`;
  }

  // SBRate 공통 증감 규칙: 증가(+) 파랑 / 감소(-) 빨강.
  // 건전성 지표도 색상은 방향 자체를 표시하고, 개선 여부는 별도 주석으로 설명한다.
  function deltaClass(value) {
    const num = Number(value);
    if (!Number.isFinite(num) || num === 0) return 'mr-delta-flat';
    return num > 0 ? 'mr-delta-good' : 'mr-delta-bad';
  }

  function rankDeltaText(value) {
    if (value === null || value === undefined) return '-';
    const num = Number(value);
    if (!Number.isFinite(num) || num === 0) return '-';
    return num > 0 ? `↑${num}` : `↓${Math.abs(num)}`;
  }

  function rankDeltaClass(value) {
    const num = Number(value);
    if (!Number.isFinite(num) || num === 0) return 'mr-delta-flat';
    return num > 0 ? 'mr-delta-good' : 'mr-delta-bad';
  }

  function orderedFields(fields) {
    const list = Array.isArray(fields) ? fields : [];
    const byKey = new Map(list.map(item => [item.key, item]));
    const ordered = preferredFieldOrder.map(key => byKey.get(key)).filter(Boolean);
    list.forEach(item => {
      if (!preferredFieldOrder.includes(item.key)) ordered.push(item);
    });
    return ordered;
  }

  function quarterIndex(key) {
    return state.quarters.findIndex(item => item.key === key);
  }

  function isPreviousQuarter(base, compare) {
    const baseIndex = quarterIndex(base);
    const compareIndex = quarterIndex(compare);
    return baseIndex >= 0 && compareIndex === baseIndex + 1;
  }

  function rankComparisonLabel(data) {
    return isPreviousQuarter(data.base_quarter, data.compare_quarter)
      ? '전분기比'
      : '비교분기比';
  }

  function comparisonSubLabel(data) {
    return isPreviousQuarter(data.base_quarter, data.compare_quarter)
      ? '전분기'
      : '비교분기';
  }

  function fallbackCompareQuarter(base) {
    const index = quarterIndex(base);
    if (index < 0) return state.quarters[1]?.key || '';
    return state.quarters[index + 1]?.key || state.quarters[index - 1]?.key || '';
  }

  function polishExecutiveReportHtml(html) {
    return String(html || '')
      .replace(/(<div class="er-insight">\s*<b>[^<]+<\/b>)가\s+/g, '$1 ')
      .replace(/시장 상단을 형성하고 있으며/g, '시장 최고금리를 기록하고 있으며')
      .replace(/우리금융보다 높은 금리 기관은/g, '우리금융보다 금리가 높은 저축은행은')
      .replace(/TOP5 경계와의 단순 금리차는/g, 'TOP5 진입 기준과의 금리 차이는')
      .replace(/TOP5 경계 금리/g, 'TOP5 진입 기준 금리')
      .replace(/단순 금리차/g, '금리 차이')
      .replace(/선두사 Gap/g, '선두 저축은행과의 금리 격차')
      .replace(/상위금리권/g, '상위 금리권')
      .replace(/상위기관/g, '상위 기관');
  }

  function polishRenderedExecutiveReport(root = document) {
    const report = root.querySelector ? root.querySelector('#executive-report-document') : null;
    if (!report || report.dataset.koreanPolished === '1') return;

    report.querySelectorAll('.er-insight').forEach((block) => {
      const firstBold = block.querySelector('b');
      if (firstBold) {
        let node = firstBold.nextSibling;
        while (node && node.nodeType === Node.TEXT_NODE && !node.textContent.trim()) node = node.nextSibling;
        if (node && node.nodeType === Node.TEXT_NODE) {
          node.textContent = node.textContent.replace(/^\s*가\s+/, ' ');
        }
      }
    });

    report.innerHTML = polishExecutiveReportHtml(report.innerHTML);
    report.dataset.koreanPolished = '1';
  }

  function installExecutiveReportPolish() {
    const original = window.buildExecutiveReportBase;
    if (typeof original === 'function' && !original.__sbrateKoreanPolished) {
      const wrapped = function(...args) {
        return polishExecutiveReportHtml(original.apply(this, args));
      };
      wrapped.__sbrateKoreanPolished = true;
      window.buildExecutiveReportBase = wrapped;
    }

    const observer = new MutationObserver(() => polishRenderedExecutiveReport(document));
    observer.observe(document.documentElement, { childList: true, subtree: true });
    polishRenderedExecutiveReport(document);
  }

  function mountOpenButtons() {
    const pcAnchor = document.getElementById('error-report-open');
    if (pcAnchor && !document.getElementById('management-report-open')) {
      const btn = el('button', 'mr-open-btn', '📑 경영현황');
      btn.id = 'management-report-open';
      btn.type = 'button';
      btn.title = 'FISIS 경영현황 보고서 열기';

      const marketTabs = document.getElementById('market-product-tabs');
      if (marketTabs && marketTabs.parentNode) {
        marketTabs.insertAdjacentElement('afterend', btn);
      } else {
        pcAnchor.parentNode.insertBefore(btn, pcAnchor);
      }
      btn.addEventListener('click', openReport);
    }

    const mobileAnchor = document.getElementById('mobile-report-open');
    if (mobileAnchor && !document.getElementById('management-report-open-mobile')) {
      const btn = el('button', 'mr-open-btn mr-open-btn-mobile', '경영현황');
      btn.id = 'management-report-open-mobile';
      btn.type = 'button';
      mobileAnchor.insertAdjacentElement('afterend', btn);
      btn.addEventListener('click', openReport);
    }
  }

  function mountModal() {
    if (document.getElementById('management-report-modal')) return;
    const modal = el('div', 'mr-modal');
    modal.id = 'management-report-modal';
    modal.setAttribute('aria-hidden', 'true');
    modal.innerHTML = `
      <div class="mr-shell" role="dialog" aria-modal="true" aria-label="경영현황 보고서">
        <div class="mr-topbar">
          <div>
            <div class="mr-eyebrow">MANAGEMENT INTELLIGENCE</div>
            <h2>경영현황 보고서</h2>
            <p id="mr-source-line">금융감독원 금융통계정보시스템(FISIS) 기준</p>
          </div>
          <div class="mr-topbar-actions">
            <div class="mr-latest-badge"><span>최신데이터</span><strong id="mr-latest-quarter">확인중</strong></div>
            <button type="button" id="mr-close" class="mr-icon-btn" aria-label="닫기">×</button>
          </div>
        </div>

        <div class="mr-query-area">
          <div class="mr-mode-tabs" role="tablist" aria-label="조회 방식">
            <button type="button" class="mr-mode-tab" data-mr-mode="single">분기현황 조회</button>
            <button type="button" class="mr-mode-tab is-active" data-mr-mode="compare">분기비교</button>
          </div>

          <div id="mr-single-controls" class="mr-toolbar mr-toolbar-single is-hidden">
            <label class="mr-select-box">
              <span>조회분기</span>
              <select id="mr-single-quarter"></select>
            </label>
            <button type="button" id="mr-single-run" class="mr-primary-btn">분기조회</button>
          </div>

          <div id="mr-compare-controls" class="mr-toolbar mr-toolbar-compare">
            <label class="mr-select-box">
              <span>기준분기</span>
              <select id="mr-base-quarter"></select>
            </label>
            <div class="mr-vs">VS</div>
            <label class="mr-select-box">
              <span>비교분기</span>
              <select id="mr-compare-quarter"></select>
            </label>
            <button type="button" id="mr-run" class="mr-primary-btn">비교조회</button>
            <button type="button" id="mr-export" class="mr-secondary-btn">⬇ Excel 다운로드</button>
          </div>
        </div>

        <div id="mr-status" class="mr-status">분기 데이터를 불러오고 있습니다.</div>
        <div id="mr-summary" class="mr-summary"></div>

        <div class="mr-table-card">
          <div class="mr-table-headline">
            <div>
              <strong id="mr-table-title">업권 경영현황 비교</strong>
              <span>총자산 기준 순위</span>
            </div>
            <div class="mr-legend">
              <span class="mr-legend-good">● 증가(+)</span>
              <span class="mr-legend-bad">● 감소(-)</span>
              <span>※ 모든 증감 색상은 동일 기준 · 연체율·고정이하여신비율은 하락 시 건전성 개선 · 당기순이익은 공시 누적값</span>
            </div>
          </div>
          <div class="mr-table-wrap">
            <table id="mr-table" class="mr-table"></table>
          </div>
        </div>
      </div>`;
    document.body.appendChild(modal);

    modal.addEventListener('click', (event) => {
      if (event.target === modal) closeReport();
    });
    document.getElementById('mr-close').addEventListener('click', closeReport);
    document.getElementById('mr-run').addEventListener('click', loadCompareReport);
    document.getElementById('mr-single-run').addEventListener('click', loadSingleReport);
    document.getElementById('mr-export').addEventListener('click', exportExcel);
    document.querySelectorAll('[data-mr-mode]').forEach(btn => {
      btn.addEventListener('click', () => switchMode(btn.dataset.mrMode));
    });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && modal.classList.contains('is-open')) closeReport();
    });
  }

  async function fetchJson(url) {
    const response = await fetch(url, { cache: 'no-store' });
    let data = null;
    try { data = await response.json(); } catch (_) {}
    if (!response.ok || !data || data.ok === false) {
      throw new Error((data && data.error) || `HTTP ${response.status}`);
    }
    return data;
  }

  function fillQuarterSelect(select, selected) {
    if (!select) return;
    select.innerHTML = '';
    state.quarters.forEach(item => {
      const option = document.createElement('option');
      option.value = item.key;
      option.textContent = `${item.label} (${item.bank_count}개사)`;
      select.appendChild(option);
    });
    if (selected) select.value = selected;
  }

  async function loadQuarters() {
    const status = document.getElementById('mr-status');
    status.textContent = 'FISIS 분기 데이터를 확인하고 있습니다.';
    const data = await fetchJson('/api/management-report/quarters');
    state.quarters = Array.isArray(data.quarters) ? data.quarters : [];

    state.single = state.single || state.quarters[0]?.key || '';
    state.base = state.base || state.quarters[0]?.key || '';
    state.compare = state.compare || state.quarters[1]?.key || '';

    fillQuarterSelect(document.getElementById('mr-single-quarter'), state.single);
    fillQuarterSelect(document.getElementById('mr-base-quarter'), state.base);
    fillQuarterSelect(document.getElementById('mr-compare-quarter'), state.compare);

    const latest = state.quarters[0];
    const latestEl = document.getElementById('mr-latest-quarter');
    if (latestEl) latestEl.textContent = latest ? latest.label : '-';

    status.textContent = state.quarters.length >= 2
      ? `사용 가능한 분기 ${state.quarters.length}개 · 최신 공시 ${latest?.label || '-'}`
      : '비교 가능한 분기 데이터가 아직 충분하지 않습니다.';
  }

  async function openReport() {
    mountModal();
    const modal = document.getElementById('management-report-modal');
    modal.classList.add('is-open');
    modal.setAttribute('aria-hidden', 'false');
    document.body.classList.add('mr-lock');

    try {
      if (!state.quarters.length) await loadQuarters();
      if (state.mode === 'single') await loadSingleReport();
      else if (state.quarters.length >= 2) await loadCompareReport();
    } catch (error) {
      document.getElementById('mr-status').textContent = `데이터 확인 실패: ${error.message}`;
    }
  }

  function closeReport() {
    const modal = document.getElementById('management-report-modal');
    if (!modal) return;
    modal.classList.remove('is-open');
    modal.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('mr-lock');
  }

  async function switchMode(mode) {
    if (!['single','compare'].includes(mode)) return;
    state.mode = mode;
    document.querySelectorAll('[data-mr-mode]').forEach(btn => {
      btn.classList.toggle('is-active', btn.dataset.mrMode === mode);
    });
    document.getElementById('mr-single-controls')?.classList.toggle('is-hidden', mode !== 'single');
    document.getElementById('mr-compare-controls')?.classList.toggle('is-hidden', mode !== 'compare');

    if (mode === 'single') await loadSingleReport();
    else await loadCompareReport();
  }

  async function loadCompareReport() {
    const base = document.getElementById('mr-base-quarter').value;
    const compare = document.getElementById('mr-compare-quarter').value;
    const status = document.getElementById('mr-status');
    if (!base || !compare) return;
    if (base === compare) {
      status.textContent = '기준분기와 비교분기를 서로 다르게 선택해주세요.';
      return;
    }
    state.base = base;
    state.compare = compare;
    status.textContent = '경영현황을 비교하고 있습니다.';
    try {
      const data = await fetchJson(`/api/management-report?base=${encodeURIComponent(base)}&compare=${encodeURIComponent(compare)}`);
      state.payload = data;
      renderCompareSummary(data);
      renderCompareTable(data);
      const sourceLine = document.getElementById('mr-source-line');
      sourceLine.textContent = `${data.source_name} · ${data.base_label} vs ${data.compare_label}`;
      document.getElementById('mr-table-title').textContent = `${data.base_label} vs ${data.compare_label}`;
      status.textContent = `${data.rows.length}개 저축은행 · 기준분기 총자산 순 정렬`;
    } catch (error) {
      state.payload = null;
      document.getElementById('mr-summary').innerHTML = '';
      document.getElementById('mr-table').innerHTML = '';
      status.textContent = `비교조회 실패: ${error.message}`;
    }
  }

  async function loadSingleReport() {
    const selected = document.getElementById('mr-single-quarter').value;
    const status = document.getElementById('mr-status');
    if (!selected) return;
    const fallback = fallbackCompareQuarter(selected);
    if (!fallback) {
      status.textContent = '분기현황을 조회할 수 있는 데이터가 부족합니다.';
      return;
    }
    state.single = selected;
    status.textContent = '선택 분기 경영현황을 조회하고 있습니다.';
    try {
      // 현재 API의 기준분기 값만 사용한다. 비교분기는 단일조회 렌더링에서 표시하지 않는다.
      const data = await fetchJson(`/api/management-report?base=${encodeURIComponent(selected)}&compare=${encodeURIComponent(fallback)}`);
      state.payload = data;
      renderSingleSummary(data);
      renderSingleTable(data);
      document.getElementById('mr-source-line').textContent = `${data.source_name} · ${data.base_label}`;
      document.getElementById('mr-table-title').textContent = `${data.base_label} 경영현황`;
      status.textContent = `${data.rows.length}개 저축은행 · ${data.base_label} 총자산 순 정렬`;
    } catch (error) {
      state.payload = null;
      document.getElementById('mr-summary').innerHTML = '';
      document.getElementById('mr-table').innerHTML = '';
      status.textContent = `분기조회 실패: ${error.message}`;
    }
  }

  function summaryCard(label, value, sub, cls='', valueCls='') {
    return `<article class="mr-summary-card ${cls}"><span>${label}</span><strong class="${valueCls}">${value}</strong><small>${sub}</small></article>`;
  }

  function renderCompareSummary(data) {
    const root = document.getElementById('mr-summary');
    const w = data.woori;
    if (!w) {
      root.innerHTML = summaryCard('우리금융', '-', '선택 분기에 우리금융 데이터가 없습니다.');
      return;
    }
    const totalAssets = w.metrics.total_assets || {};
    const household = w.metrics.household_loans || {};
    const totalLoans = w.metrics.total_loans || {};
    const netIncome = w.metrics.net_income || {};
    const bis = w.metrics.bis_ratio || {};
    const delinquency = w.metrics.delinquency_ratio || {};
    const rankDelta = rankDeltaText(w.rank_change);
    const rankLabel = comparisonSubLabel(data);
    root.innerHTML = [
      summaryCard('우리금융 총자산 순위', `${w.rank || '-'}위`, `${rankLabel} ${w.compare_rank || '-'}위 · <b class="${rankDeltaClass(w.rank_change)}">${rankDelta}</b>`, 'mr-summary-woori'),
      summaryCard('총자산 증감', deltaText(totalAssets.delta,'total_assets'), `기준 ${fmt(totalAssets.base,'total_assets')}억원`, '', deltaClass(totalAssets.delta)),
      summaryCard('가계대출 증감', deltaText(household.delta,'household_loans'), `기준 ${fmt(household.base,'household_loans')}억원`, '', deltaClass(household.delta)),
      summaryCard('총대출 증감', deltaText(totalLoans.delta,'total_loans'), `기준 ${fmt(totalLoans.base,'total_loans')}억원`, '', deltaClass(totalLoans.delta)),
      summaryCard('당기순이익 증감', deltaText(netIncome.delta,'net_income'), `기준 ${fmt(netIncome.base,'net_income')}억원`, '', deltaClass(netIncome.delta)),
      summaryCard('BIS 증감', deltaText(bis.delta,'bis_ratio'), `기준 ${fmt(bis.base,'bis_ratio')}`, '', deltaClass(bis.delta)),
      summaryCard('연체율 증감', deltaText(delinquency.delta,'delinquency_ratio'), `기준 ${fmt(delinquency.base,'delinquency_ratio')}`, '', deltaClass(delinquency.delta)),
    ].join('');
  }

  function renderSingleSummary(data) {
    const root = document.getElementById('mr-summary');
    const w = data.woori;
    if (!w) {
      root.innerHTML = summaryCard('우리금융', '-', '선택 분기에 우리금융 데이터가 없습니다.');
      return;
    }
    const m = w.metrics || {};
    root.innerHTML = [
      summaryCard('우리금융 총자산 순위', `${w.rank || '-'}위`, `${data.rows.length}개사 중`, 'mr-summary-woori'),
      summaryCard('총자산', valueWithUnit(m.total_assets?.base,'total_assets'), data.base_label),
      summaryCard('가계대출', valueWithUnit(m.household_loans?.base,'household_loans'), data.base_label),
      summaryCard('총대출', valueWithUnit(m.total_loans?.base,'total_loans'), data.base_label),
      summaryCard('당기순이익', valueWithUnit(m.net_income?.base,'net_income'), '공시 누적값'),
      summaryCard('BIS비율', valueWithUnit(m.bis_ratio?.base,'bis_ratio'), data.base_label),
      summaryCard('연체율', valueWithUnit(m.delinquency_ratio?.base,'delinquency_ratio'), data.base_label),
    ].join('');
  }

  function renderCompareTable(data) {
    const table = document.getElementById('mr-table');
    table.classList.remove('is-single');
    table.classList.add('is-compare');
    const fields = orderedFields(data.fields);
    let top = '<thead><tr>' +
      '<th rowspan="2" class="mr-sticky mr-col-rank">순위</th>' +
      `<th rowspan="2" class="mr-sticky mr-col-rankchg">${rankComparisonLabel(data)}</th>` +
      '<th rowspan="2" class="mr-sticky mr-col-bank">저축은행</th>' +
      '<th rowspan="2" class="mr-sticky mr-col-region">지역</th>';
    fields.forEach(field => {
      top += `<th colspan="3" class="mr-group-head">${field.label}<small>${field.unit}</small></th>`;
    });
    top += '</tr><tr>';
    fields.forEach(() => {
      top += `<th>${data.base_label.replace('년 ','-')}</th><th>${data.compare_label.replace('년 ','-')}</th><th>증감</th>`;
    });
    top += '</tr></thead>';

    let body = '<tbody>';
    (data.rows || []).forEach(item => {
      body += `<tr class="${item.is_woori ? 'mr-woori-row' : ''}">`;
      body += `<td class="mr-sticky mr-col-rank">${item.rank || '-'}</td>`;
      body += `<td class="mr-sticky mr-col-rankchg ${rankDeltaClass(item.rank_change)}">${rankDeltaText(item.rank_change)}</td>`;
      body += `<td class="mr-sticky mr-col-bank">${item.bank}</td>`;
      body += `<td class="mr-sticky mr-col-region">${item.region || '-'}</td>`;
      fields.forEach(field => {
        const metric = item.metrics[field.key] || {};
        body += `<td>${fmt(metric.base,field.key)}</td>`;
        body += `<td class="mr-compare-cell">${fmt(metric.compare,field.key)}</td>`;
        body += `<td class="${deltaClass(metric.delta)}">${deltaText(metric.delta,field.key)}</td>`;
      });
      body += '</tr>';
    });
    body += '</tbody>';
    table.innerHTML = top + body;
  }

  function renderSingleTable(data) {
    const table = document.getElementById('mr-table');
    table.classList.add('is-single');
    table.classList.remove('is-compare');
    const fields = orderedFields(data.fields);
    let top = '<thead><tr>' +
      '<th class="mr-sticky mr-col-rank">순위</th>' +
      '<th class="mr-sticky mr-col-bank">저축은행</th>' +
      '<th class="mr-sticky mr-col-region">지역</th>';
    fields.forEach(field => {
      top += `<th class="mr-group-head">${field.label}<small>${field.unit}</small></th>`;
    });
    top += '</tr></thead>';

    let body = '<tbody>';
    (data.rows || []).forEach(item => {
      body += `<tr class="${item.is_woori ? 'mr-woori-row' : ''}">`;
      body += `<td class="mr-sticky mr-col-rank">${item.rank || '-'}</td>`;
      body += `<td class="mr-sticky mr-col-bank">${item.bank}</td>`;
      body += `<td class="mr-sticky mr-col-region">${item.region || '-'}</td>`;
      fields.forEach(field => {
        const metric = item.metrics[field.key] || {};
        body += `<td>${fmt(metric.base,field.key)}</td>`;
      });
      body += '</tr>';
    });
    body += '</tbody>';
    table.innerHTML = top + body;
  }

  function exportExcel() {
    if (!state.base || !state.compare) return;
    const url = `/api/management-report/export.xlsx?base=${encodeURIComponent(state.base)}&compare=${encodeURIComponent(state.compare)}`;
    window.location.href = url;
  }

  function init() {
    if (state.mounted) return;
    state.mounted = true;
    installExecutiveReportPolish();
    mountOpenButtons();
    mountModal();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }
})();