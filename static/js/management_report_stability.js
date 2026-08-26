(() => {
  'use strict';

  let timer = null;

  function dedupeId(id) {
    const nodes = [...document.querySelectorAll(`[id="${id}"]`)];
    nodes.slice(1).forEach(node => node.remove());
    return nodes[0] || null;
  }

  function dedupeHeaderActions() {
    ['management-report-open','management-report-open-mobile','error-report-open','mobile-error-report']
      .forEach(dedupeId);

    const cleanByText = (root, pattern, preferredId) => {
      if (!root) return;
      const matches = [...root.querySelectorAll('button')].filter(btn => pattern.test(btn.textContent || ''));
      if (matches.length <= 1) return;
      const keep = matches.find(btn => btn.id === preferredId) || matches[0];
      matches.forEach(btn => { if (btn !== keep) btn.remove(); });
    };

    const desktopHeader = document.querySelector('body > header');
    cleanByText(desktopHeader, /경영현황/, 'management-report-open');
    cleanByText(desktopHeader, /오류\s*제보/, 'error-report-open');

    const mobileHeader = document.querySelector('.mobile-header');
    cleanByText(mobileHeader, /경영현황/, 'management-report-open-mobile');
  }

  function previousQuarter(key) {
    const match = String(key || '').match(/^(\d{4})Q([1-4])$/);
    if (!match) return '';
    const year = Number(match[1]);
    const quarter = Number(match[2]);
    return quarter === 1 ? `${year - 1}Q4` : `${year}Q${quarter - 1}`;
  }

  function quarterOptions(selectId) {
    return [...document.querySelectorAll(`#${selectId} option`)].map(option => option.value).filter(Boolean);
  }

  function exportSingleQuarter() {
    const base = document.getElementById('mr-single-quarter')?.value || '';
    if (!base) return;
    const keys = quarterOptions('mr-single-quarter');
    let compare = previousQuarter(base);
    if (!keys.includes(compare)) compare = keys.find(key => key !== base) || '';
    if (!compare) return;
    window.location.href = `/api/management-report/export.xlsx?base=${encodeURIComponent(base)}&compare=${encodeURIComponent(compare)}`;
  }

  function ensureSingleExport() {
    const toolbar = document.getElementById('mr-single-controls');
    if (!toolbar) return;

    const existing = [...toolbar.querySelectorAll('#mr-export-single')];
    existing.slice(1).forEach(node => node.remove());
    if (existing[0]) return;

    const btn = document.createElement('button');
    btn.type = 'button';
    btn.id = 'mr-export-single';
    btn.className = 'mr-secondary-btn mr-single-export-btn';
    btn.textContent = '⬇ Excel 다운로드';
    btn.title = '선택 분기와 직전 공시분기 비교 데이터를 Excel로 다운로드';
    btn.addEventListener('click', exportSingleQuarter);
    toolbar.appendChild(btn);
  }

  function ensureScrollableReport() {
    const modal = document.getElementById('management-report-modal');
    const shell = modal?.querySelector('.mr-shell');
    if (!modal || !shell) return;
    modal.classList.add('mr-scroll-stable');
    shell.setAttribute('data-scroll-ready', '1');
  }

  function stabilize() {
    dedupeHeaderActions();
    ensureSingleExport();
    ensureScrollableReport();
  }

  function schedule() {
    clearTimeout(timer);
    timer = setTimeout(stabilize, 20);
  }

  const observer = new MutationObserver(schedule);
  observer.observe(document.documentElement, { childList: true, subtree: true });

  document.addEventListener('click', event => {
    if (event.target.closest?.('#management-report-open,#management-report-open-mobile,[data-mi-section],[data-mr-mode]')) {
      setTimeout(stabilize, 40);
    }
  }, true);

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', stabilize, { once: true });
  } else {
    stabilize();
  }
})();
