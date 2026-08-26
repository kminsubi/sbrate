(() => {
  'use strict';

  let lastKnownLatest = '';
  let compactRows = false;
  let enhanceTimer = null;

  function reportModal() {
    return document.getElementById('management-report-modal');
  }

  function singleModeActive() {
    return !!document.querySelector('[data-mr-mode="single"].is-active');
  }

  function patchRankSummaryLabel() {
    const card = document.querySelector('#mr-summary .mr-summary-card.mr-summary-woori');
    const small = card?.querySelector('small');
    if (!small) return;

    const text = String(small.textContent || '').trim();
    let label = '';
    if (singleModeActive() || text.startsWith('전분기')) label = '전분기比';
    else if (text.startsWith('비교분기')) label = '비교분기比';
    if (!label) return;

    const delta = small.querySelector('b');
    if (delta) {
      small.innerHTML = `${label} ${delta.outerHTML}`;
    } else {
      const match = text.match(/([+▲]\s*\d+(?:\.\d+)?|-)(?:\s*)$/);
      small.textContent = `${label} ${match ? match[1] : '-'}`;
    }
  }

  function fillSelect(select, quarters, selected) {
    if (!select) return;
    select.innerHTML = '';
    quarters.forEach(item => {
      const option = document.createElement('option');
      option.value = item.key;
      option.textContent = `${item.label} (${item.bank_count}개사)`;
      select.appendChild(option);
    });
    if (selected && quarters.some(item => item.key === selected)) {
      select.value = selected;
    }
  }

  async function syncLatestQuarter({ rerunSingle = false } = {}) {
    const modal = reportModal();
    if (!modal) return;

    try {
      const response = await fetch('/api/management-report/quarters', { cache: 'no-store' });
      const data = await response.json();
      if (!response.ok || !data?.ok || !Array.isArray(data.quarters) || !data.quarters.length) return;

      const quarters = data.quarters;
      const latest = quarters[0];
      const second = quarters[1];
      const single = document.getElementById('mr-single-quarter');
      const base = document.getElementById('mr-base-quarter');
      const compare = document.getElementById('mr-compare-quarter');
      const badge = document.getElementById('mr-latest-quarter');

      const oldSingle = single?.value || '';
      const oldBase = base?.value || '';
      const oldCompare = compare?.value || '';
      const previousLatest = lastKnownLatest || oldSingle || oldBase;
      const latestChanged = !!previousLatest && previousLatest !== latest.key;
      const singleWasDefault = !oldSingle || oldSingle === previousLatest;
      const baseWasDefault = !oldBase || oldBase === previousLatest;

      const singleSelected = (latestChanged && singleWasDefault) || !oldSingle
        ? latest.key
        : oldSingle;
      const baseSelected = (latestChanged && baseWasDefault) || !oldBase
        ? latest.key
        : oldBase;
      const compareSelected = latestChanged && baseWasDefault
        ? (second?.key || oldCompare)
        : ((!oldCompare || oldCompare === baseSelected) ? (second?.key || oldCompare) : oldCompare);

      fillSelect(single, quarters, singleSelected);
      fillSelect(base, quarters, baseSelected);
      fillSelect(compare, quarters, compareSelected);

      if (badge) badge.textContent = latest.label;
      lastKnownLatest = latest.key;

      if (rerunSingle && singleModeActive() && latestChanged && singleWasDefault) {
        setTimeout(() => document.getElementById('mr-single-run')?.click(), 30);
      }
    } catch (_) {
      // 기존 경영현황 조회 동작을 방해하지 않는다.
    }
  }

  function ensureSummaryHeading() {
    const summary = document.getElementById('mr-summary');
    if (!summary || document.getElementById('mr-summary-heading')) return;

    const heading = document.createElement('div');
    heading.id = 'mr-summary-heading';
    heading.className = 'mr-summary-heading';
    heading.innerHTML = `
      <div class="mr-summary-heading-title">
        <strong>우리금융 핵심 경영지표</strong>
        <span id="mr-summary-basis"></span>
      </div>`;
    summary.insertAdjacentElement('beforebegin', heading);
  }

  function updateSummaryHeading() {
    ensureSummaryHeading();
    const basis = document.getElementById('mr-summary-basis');
    if (!basis) return;
    basis.textContent = singleModeActive()
      ? '자산·총대출 전년말比 · 손익 전년동기比 · 대출구성·건전성 전분기比'
      : '선택한 두 분기 직접 비교 · 누적 손익은 동일 누적기간일 때만 증감 표시';
  }

  function mainRows() {
    return [...document.querySelectorAll('#mr-table tbody tr')];
  }

  function applyCompactRows() {
    const rows = mainRows();
    if (!rows.length) return;

    let visible = 0;
    rows.forEach(row => {
      const rank = Number.parseInt(row.cells?.[0]?.textContent || '', 10);
      const isWoori = row.classList.contains('mr-woori-row');
      const hide = compactRows && Number.isFinite(rank) && rank > 20 && !isWoori;
      row.classList.toggle('mr-row-hidden', hide);
      if (!hide) visible += 1;
    });

    const toggle = document.getElementById('mr-compact-toggle');
    const scope = document.getElementById('mr-visible-scope');
    if (toggle) {
      toggle.textContent = compactRows ? '전체보기' : '상위20+우리';
      toggle.setAttribute('aria-pressed', compactRows ? 'true' : 'false');
    }
    if (scope) {
      scope.textContent = compactRows
        ? `핵심보기 · ${visible}개사 표시`
        : `전체 ${rows.length}개사`;
    }
  }

  function focusWoori() {
    const row = document.querySelector('#mr-table tbody tr.mr-woori-row');
    const wrap = row?.closest('.mr-table-wrap');
    if (!row || !wrap) return;

    row.classList.remove('mr-woori-pulse');
    void row.offsetWidth;
    row.classList.add('mr-woori-pulse');

    const targetTop = Math.max(0, row.offsetTop - (wrap.clientHeight / 2) + (row.offsetHeight / 2));
    wrap.scrollTo({ top: targetTop, behavior: 'smooth' });
    setTimeout(() => row.classList.remove('mr-woori-pulse'), 1800);
  }

  function ensureTableActions() {
    const card = document.querySelector('#management-report-modal .mr-table-card');
    const headline = card?.querySelector('.mr-table-headline');
    if (!card || !headline || document.getElementById('mr-table-actions')) return;

    const bar = document.createElement('div');
    bar.id = 'mr-table-actions';
    bar.className = 'mr-table-actions';
    bar.innerHTML = `
      <div class="mr-table-scope">
        <strong id="mr-visible-scope">전체보기</strong>
        <span class="mr-scroll-hint">좌우로 밀어 전체 지표 확인</span>
      </div>
      <div class="mr-table-action-buttons">
        <button type="button" id="mr-compact-toggle" class="mr-table-action-btn" aria-pressed="false">상위20+우리</button>
        <button type="button" id="mr-focus-woori" class="mr-table-action-btn mr-table-action-primary">우리금융 바로보기</button>
      </div>`;
    headline.insertAdjacentElement('afterend', bar);

    document.getElementById('mr-compact-toggle')?.addEventListener('click', () => {
      compactRows = !compactRows;
      applyCompactRows();
    });
    document.getElementById('mr-focus-woori')?.addEventListener('click', focusWoori);
  }

  function enhanceMainTable() {
    const wrap = document.querySelector('#management-report-modal .mr-table-wrap');
    if (wrap) {
      wrap.tabIndex = 0;
      wrap.setAttribute('aria-label', '저축은행 경영현황 표. 좌우와 상하로 스크롤할 수 있습니다.');
    }
    ensureTableActions();
    applyCompactRows();
  }

  function hideUnavailableProfitabilityMetrics() {
    const root = document.getElementById('mi-content');
    if (!root || root.hidden) return;

    const profitability = [...root.querySelectorAll('.mi-block')].find(block =>
      (block.querySelector('.mi-block-title')?.textContent || '').includes('우리금융 수익성')
    );
    if (profitability) {
      profitability.querySelectorAll('.mi-card').forEach(card => {
        const label = card.querySelector('.mi-card-label')?.textContent?.trim();
        const value = card.querySelector('.mi-card-value')?.textContent?.trim();
        if ((label === 'ROA' || label === 'ROE') && value === '-') {
          card.classList.add('mi-metric-unavailable');
        }
      });
    }

    const industry = [...root.querySelectorAll('.mi-block')].find(block =>
      (block.querySelector('.mi-block-title')?.textContent || '').includes('업권 수익성 현황')
    );
    const table = industry?.querySelector('.mi-table');
    if (!table) return;

    ['ROA', 'ROE'].forEach(label => {
      const headers = [...table.querySelectorAll('thead th')];
      const index = headers.findIndex(th => th.textContent.trim() === label);
      if (index < 0) return;
      const cells = [...table.querySelectorAll(`tbody tr td:nth-child(${index + 1})`)];
      const unavailable = cells.length > 0 && cells.every(td => ['-', ''].includes(td.textContent.trim()));
      if (!unavailable) return;
      headers[index].classList.add('mi-metric-unavailable');
      cells.forEach(td => td.classList.add('mi-metric-unavailable'));
    });
  }

  function enhanceUi() {
    patchRankSummaryLabel();
    updateSummaryHeading();
    enhanceMainTable();
    hideUnavailableProfitabilityMetrics();
  }

  function scheduleEnhance() {
    window.clearTimeout(enhanceTimer);
    enhanceTimer = window.setTimeout(enhanceUi, 30);
  }

  function bind() {
    const modal = reportModal();
    if (!modal || modal.dataset.v5PatchBound === '1') return;
    modal.dataset.v5PatchBound = '1';

    ensureSummaryHeading();
    ensureTableActions();

    const observer = new MutationObserver(scheduleEnhance);
    observer.observe(modal, { childList: true, subtree: true });
    enhanceUi();

    document.addEventListener('click', event => {
      const openTarget = event.target?.closest?.('#management-report-open,#management-report-open-mobile');
      if (openTarget) {
        setTimeout(() => syncLatestQuarter({ rerunSingle: true }), 80);
      }
      if (event.target?.closest?.('[data-mr-mode],#mr-single-run,#mr-run,[data-mi-section]')) {
        setTimeout(enhanceUi, 120);
      }
    }, true);
  }

  const rootObserver = new MutationObserver(() => bind());
  rootObserver.observe(document.documentElement, { childList: true, subtree: true });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bind, { once: true });
  } else {
    bind();
  }
})();