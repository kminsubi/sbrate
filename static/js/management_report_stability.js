(() => {
  'use strict';

  let timer = null;

  function dedupeDesktopHeaderActions() {
    const header = document.querySelector('body > header');
    if (!header) return;

    const buttons = [...header.querySelectorAll('button')];
    const groups = [
      {
        match: btn => btn.id === 'management-report-open' || /경영현황/.test(btn.textContent || ''),
        preferredId: 'management-report-open',
      },
      {
        match: btn => btn.id === 'error-report-open' || /오류\s*제보/.test(btn.textContent || ''),
        preferredId: 'error-report-open',
      },
    ];

    groups.forEach(group => {
      const matches = buttons.filter(group.match);
      if (matches.length <= 1) return;
      const keep = matches.find(btn => btn.id === group.preferredId) || matches[0];
      matches.forEach(btn => {
        if (btn !== keep) btn.remove();
      });
    });
  }

  async function exportSingleQuarter() {
    const select = document.getElementById('mr-single-quarter');
    const base = select?.value || '';
    if (!base) return;

    let compare = '';
    try {
      const response = await fetch('/api/management-report/quarters', { cache: 'no-store' });
      const data = await response.json();
      const quarters = Array.isArray(data?.quarters) ? data.quarters : [];
      const index = quarters.findIndex(item => item.key === base);
      if (index >= 0) compare = quarters[index + 1]?.key || quarters[index - 1]?.key || '';
    } catch (_) {}

    if (!compare) {
      const compareSelect = document.getElementById('mr-compare-quarter');
      compare = compareSelect?.value || '';
    }
    if (!compare || compare === base) return;

    window.location.href = `/api/management-report/export.xlsx?base=${encodeURIComponent(base)}&compare=${encodeURIComponent(compare)}`;
  }

  function ensureSingleExport() {
    const toolbar = document.getElementById('mr-single-controls');
    if (!toolbar || document.getElementById('mr-export-single')) return;

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

    shell.setAttribute('tabindex', '-1');
    shell.setAttribute('data-scroll-ready', '1');

    const content = document.getElementById('mi-content');
    if (content && !content.hidden) content.setAttribute('data-scroll-ready', '1');
  }

  function stabilize() {
    dedupeDesktopHeaderActions();
    ensureSingleExport();
    ensureScrollableReport();
  }

  function schedule() {
    clearTimeout(timer);
    timer = setTimeout(stabilize, 25);
  }

  const observer = new MutationObserver(schedule);
  observer.observe(document.documentElement, { childList: true, subtree: true });

  document.addEventListener('click', event => {
    if (event.target.closest?.('#management-report-open,#management-report-open-mobile,[data-mi-section],[data-mr-mode]')) {
      setTimeout(stabilize, 60);
    }
  }, true);

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', stabilize, { once: true });
  } else {
    stabilize();
  }
})();
