(() => {
  'use strict';

  function dedupeById(id) {
    const nodes = [...document.querySelectorAll(`[id="${id}"]`)];
    nodes.slice(1).forEach(node => node.remove());
    return nodes[0] || null;
  }

  function dedupeHeaderButtons() {
    [
      'error-report-open',
      'management-report-open',
      'management-report-open-mobile',
      'mobile-error-report',
    ].forEach(dedupeById);

    // Extra defensive cleanup for cloned buttons that lost their id.
    const desktopHeader = document.querySelector('body > header');
    if (desktopHeader) {
      const management = [...desktopHeader.querySelectorAll('button')].filter(btn =>
        (btn.textContent || '').replace(/\s+/g, ' ').trim().includes('경영현황')
      );
      management.slice(1).forEach(btn => btn.remove());

      const errors = [...desktopHeader.querySelectorAll('button')].filter(btn =>
        (btn.textContent || '').replace(/\s+/g, ' ').trim().includes('오류 제보')
      );
      errors.slice(1).forEach(btn => btn.remove());
    }

    const mobileHeader = document.querySelector('.mobile-header');
    if (mobileHeader) {
      const management = [...mobileHeader.querySelectorAll('button')].filter(btn =>
        (btn.textContent || '').replace(/\s+/g, ' ').trim().includes('경영현황')
      );
      management.slice(1).forEach(btn => btn.remove());
    }
  }

  function previousQuarter(key) {
    const m = String(key || '').match(/^(\d{4})Q([1-4])$/);
    if (!m) return '';
    const y = Number(m[1]);
    const q = Number(m[2]);
    return q === 1 ? `${y - 1}Q4` : `${y}Q${q - 1}`;
  }

  function availableQuarterKeys() {
    return [...document.querySelectorAll('#mr-single-quarter option')].map(o => o.value).filter(Boolean);
  }

  function singleExportUrl() {
    const base = document.getElementById('mr-single-quarter')?.value || '';
    if (!base) return '';
    const keys = availableQuarterKeys();
    let compare = previousQuarter(base);
    if (!keys.includes(compare)) compare = keys.find(key => key !== base) || '';
    if (!compare) return '';
    return `/api/management-report/export.xlsx?base=${encodeURIComponent(base)}&compare=${encodeURIComponent(compare)}`;
  }

  function compareExportUrl() {
    const base = document.getElementById('mr-base-quarter')?.value || '';
    const compare = document.getElementById('mr-compare-quarter')?.value || '';
    if (!base || !compare || base === compare) return '';
    return `/api/management-report/export.xlsx?base=${encodeURIComponent(base)}&compare=${encodeURIComponent(compare)}`;
  }

  function runUniversalExport() {
    const single = !!document.querySelector('[data-mr-mode="single"].is-active');
    const url = single ? singleExportUrl() : compareExportUrl();
    if (url) window.location.href = url;
  }

  function ensureUniversalExport() {
    const modal = document.getElementById('management-report-modal');
    if (!modal) return;

    const singleToolbar = document.getElementById('mr-single-controls');
    if (singleToolbar && !document.getElementById('mr-export-single')) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.id = 'mr-export-single';
      btn.className = 'mr-secondary-btn mr-export-always';
      btn.textContent = '⬇ Excel 다운로드';
      btn.addEventListener('click', runUniversalExport);
      singleToolbar.appendChild(btn);
    }

    const compareExport = document.getElementById('mr-export');
    if (compareExport) {
      compareExport.classList.add('mr-export-always');
      if (compareExport.dataset.hotfixBound !== '1') {
        compareExport.dataset.hotfixBound = '1';
        compareExport.addEventListener('click', event => {
          event.preventDefault();
          event.stopImmediatePropagation();
          runUniversalExport();
        }, true);
      }
    }
  }

  function makeReportScrollable() {
    const modal = document.getElementById('management-report-modal');
    const shell = modal?.querySelector('.mr-shell');
    if (!modal || !shell) return;
    modal.classList.add('mr-mobile-scroll-hotfix');
  }

  function enhance() {
    dedupeHeaderButtons();
    ensureUniversalExport();
    makeReportScrollable();
  }

  let timer = null;
  const observer = new MutationObserver(() => {
    clearTimeout(timer);
    timer = setTimeout(enhance, 20);
  });
  observer.observe(document.documentElement, { childList: true, subtree: true });

  document.addEventListener('click', event => {
    if (event.target.closest?.('#management-report-open,#management-report-open-mobile,[data-mr-mode]')) {
      setTimeout(enhance, 30);
    }
  }, true);

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', enhance, { once: true });
  } else {
    enhance();
  }
})();