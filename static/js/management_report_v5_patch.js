(() => {
  'use strict';

  let lastKnownLatest = '';

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

  function bind() {
    const modal = reportModal();
    if (!modal || modal.dataset.v5PatchBound === '1') return;
    modal.dataset.v5PatchBound = '1';

    const observer = new MutationObserver(() => patchRankSummaryLabel());
    const summary = document.getElementById('mr-summary');
    if (summary) observer.observe(summary, { childList: true, subtree: true });
    patchRankSummaryLabel();

    document.addEventListener('click', event => {
      const target = event.target?.closest?.('#management-report-open,#management-report-open-mobile');
      if (!target) return;
      setTimeout(() => syncLatestQuarter({ rerunSingle: true }), 80);
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
