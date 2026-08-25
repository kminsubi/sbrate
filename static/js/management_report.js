(() => {
  'use strict';

  const state = {
    quarters: [],
    base: '',
    compare: '',
    payload: null,
    mounted: false,
  };

  const moneyFields = new Set(['total_assets','corporate_loans','household_loans','total_loans','net_income']);
  const ratioFields = new Set(['bis_ratio','npl_ratio','delinquency_ratio']);
  const badRatioFields = new Set(['npl_ratio','delinquency_ratio']);

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

  function deltaText(value, fieldKey) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
    const num = Number(value);
    const sign = num > 0 ? '+' : '';
    if (ratioFields.has(fieldKey)) return `${sign}${num.toFixed(2)}%p`;
    return `${sign}${Math.round(num).toLocaleString('ko-KR')}`;
  }

  function deltaClass(value, fieldKey) {
    const num = Number(value);
    if (!Number.isFinite(num) || num === 0) return 'mr-delta-flat';
    if (badRatioFields.has(fieldKey)) return num < 0 ? 'mr-delta-good' : 'mr-delta-bad';
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
          <button type="button" id="mr-close" class="mr-icon-btn" aria-label="닫기">×</button>
        </div>

        <div class="mr-toolbar">
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

        <div id="mr-status" class="mr-status">분기 데이터를 불러오고 있습니다.</div>
        <div id="mr-summary" class="mr-summary"></div>

        <div class="mr-table-card">
          <div class="mr-table-headline">
            <div>
              <strong id="mr-table-title">업권 경영현황 비교</strong>
              <span>총자산 기준 순위</span>
            </div>
            <div class="mr-legend">
              <span class="mr-legend-good">● 개선/증가</span>
              <span class="mr-legend-bad">● 악화/감소</span>
              <span>※ 연체율·고정이하여신비율은 하락이 개선 · 당기순이익은 공시 누적값</span>
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
    document.getElementById('mr-run').addEventListener('click', loadReport);
    document.getElementById('mr-export').addEventListener('click', exportExcel);
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

  async function loadQuarters() {
    const status = document.getElementById('mr-status');
    status.textContent = 'FISIS 분기 데이터를 확인하고 있습니다.';
    const data = await fetchJson('/api/management-report/quarters');
    state.quarters = Array.isArray(data.quarters) ? data.quarters : [];
    const baseSel = document.getElementById('mr-base-quarter');
    const compareSel = document.getElementById('mr-compare-quarter');
    baseSel.innerHTML = '';
    compareSel.innerHTML = '';

    state.quarters.forEach((item, index) => {
      const a = document.createElement('option');
      a.value = item.key;
      a.textContent = `${item.label} (${item.bank_count}개사)`;
      baseSel.appendChild(a);
      const b = a.cloneNode(true);
      compareSel.appendChild(b);
      if (index === 0) state.base = item.key;
      if (index === 1) state.compare = item.key;
    });

    if (state.base) baseSel.value = state.base;
    if (state.compare) compareSel.value = state.compare;
    status.textContent = state.quarters.length >= 2
      ? `사용 가능한 분기 ${state.quarters.length}개 · 최신 분기와 직전 분기를 기본 비교합니다.`
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
      if (state.quarters.length >= 2) await loadReport();
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

  async function loadReport() {
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
      renderSummary(data);
      renderTable(data);
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

  function summaryCard(label, value, sub, cls='') {
    return `<article class="mr-summary-card ${cls}"><span>${label}</span><strong>${value}</strong><small>${sub}</small></article>`;
  }

  function renderSummary(data) {
    const root = document.getElementById('mr-summary');
    const w = data.woori;
    if (!w) {
      root.innerHTML = summaryCard('우리금융', '-', '선택 분기에 우리금융 데이터가 없습니다.');
      return;
    }
    const totalAssets = w.metrics.total_assets || {};
    const totalLoans = w.metrics.total_loans || {};
    const bis = w.metrics.bis_ratio || {};
    const delinquency = w.metrics.delinquency_ratio || {};
    const rankDelta = rankDeltaText(w.rank_change);
    root.innerHTML = [
      summaryCard('우리금융 총자산 순위', `${w.rank || '-'}위`, `비교분기 ${w.compare_rank || '-'}위 · ${rankDelta}`, 'mr-summary-woori'),
      summaryCard('총자산 증감', deltaText(totalAssets.delta,'total_assets'), `기준 ${fmt(totalAssets.base,'total_assets')}억원`),
      summaryCard('총대출 증감', deltaText(totalLoans.delta,'total_loans'), `기준 ${fmt(totalLoans.base,'total_loans')}억원`),
      summaryCard('BIS 변화', deltaText(bis.delta,'bis_ratio'), `기준 ${fmt(bis.base,'bis_ratio')}`),
      summaryCard('연체율 변화', deltaText(delinquency.delta,'delinquency_ratio'), `기준 ${fmt(delinquency.base,'delinquency_ratio')}`),
    ].join('');
  }

  function renderTable(data) {
    const table = document.getElementById('mr-table');
    const fields = data.fields || [];
    let top = '<thead><tr>' +
      '<th rowspan="2" class="mr-sticky mr-col-rank">순위</th>' +
      '<th rowspan="2" class="mr-sticky mr-col-rankchg">순위변동</th>' +
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
        const m = item.metrics[field.key] || {};
        body += `<td>${fmt(m.base,field.key)}</td>`;
        body += `<td class="mr-compare-cell">${fmt(m.compare,field.key)}</td>`;
        body += `<td class="${deltaClass(m.delta,field.key)}">${deltaText(m.delta,field.key)}</td>`;
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
