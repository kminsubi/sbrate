(() => {
  'use strict';

  let timer = null;

  function dedupeId(id) {
    const nodes = [...document.querySelectorAll(`[id="${id}"]`)];
    nodes.slice(1).forEach(node => node.remove());
    return nodes[0] || null;
  }

  function cleanByText(root, pattern, preferredId) {
    if (!root) return null;
    const preferred = preferredId ? document.getElementById(preferredId) : null;
    if (preferred && root.contains(preferred)) return preferred;
    const matches = [...root.querySelectorAll('button')].filter(btn => pattern.test(btn.textContent || ''));
    return matches[0] || null;
  }

  function normalizeDesktopHeaderActions() {
    const header = document.querySelector('body > header');
    if (!header) return;

    header.classList.add('mr-header-stable');

    const management = document.getElementById('management-report-open')
      || cleanByText(header, /경영현황/, 'management-report-open');
    const error = document.getElementById('error-report-open')
      || cleanByText(header, /오류\s*제보/, 'error-report-open');
    const updateTime = document.getElementById('header-data-update-time');
    const updateWrap = updateTime?.parentElement;
    if (updateWrap) updateWrap.classList.add('mr-header-update');

    // Important: do not repeatedly remove/reinsert the two action buttons.
    // The previous implementation generated a MutationObserver/reflow loop.
    // Keep the bound management button intact and only move it once if needed.
    if (management && error && error.parentElement) {
      const parent = error.parentElement;
      if (management.parentElement !== parent || management.nextElementSibling !== error) {
        parent.insertBefore(management, error);
      }
      management.style.pointerEvents = 'auto';
      management.style.position = 'relative';
      management.style.zIndex = '3';
    }
  }

  function normalizeMobileHeaderActions() {
    const mobileHeader = document.querySelector('.mobile-header');
    if (!mobileHeader) return;

    const management = document.getElementById('management-report-open-mobile')
      || cleanByText(mobileHeader, /경영현황/, 'management-report-open-mobile');
    const simulation = document.getElementById('rate-simulation-open-mobile');
    const row = simulation?.closest('.mobile-simulation-row');
    if (!management || !simulation || !row) return;

    let actions = row.querySelector('.mr-mobile-simulation-actions');
    if (!actions) {
      actions = document.createElement('div');
      actions.className = 'mr-mobile-simulation-actions';
      row.appendChild(actions);
    }

    if (management.parentElement !== actions || management.nextElementSibling !== simulation) {
      actions.insertBefore(management, simulation);
    }
  }

  function dedupeHeaderActions() {
    // management-report-open is intentionally not deduped here: it owns the
    // openReport listener created by management_report.js. Removing/replacing
    // it can leave a visible but unbound button.
    ['management-report-open-mobile','error-report-open','mobile-error-report']
      .forEach(dedupeId);
    normalizeDesktopHeaderActions();
    normalizeMobileHeaderActions();
  }

  function resetAccidentalHorizontalScroll() {
    if (window.scrollX !== 0) {
      window.scrollTo({ left: 0, top: window.scrollY, behavior: 'auto' });
    }
  }

  function currentSection() {
    return document.querySelector('#mi-section-tabs [data-mi-section].is-active')?.dataset.miSection || 'general';
  }

  function currentMode() {
    return document.querySelector('#management-report-modal [data-mr-mode="compare"].is-active')
      ? 'compare'
      : 'single';
  }

  function exportCurrentView() {
    const section = currentSection();
    const mode = currentMode();
    const base = mode === 'compare'
      ? document.getElementById('mr-base-quarter')?.value || ''
      : document.getElementById('mr-single-quarter')?.value || '';
    const compare = mode === 'compare'
      ? document.getElementById('mr-compare-quarter')?.value || ''
      : '';

    if (!base || (mode === 'compare' && (!compare || compare === base))) return;

    const params = new URLSearchParams({ section, mode, base });
    if (mode === 'compare') params.set('compare', compare);
    window.location.href = `/api/management-export.xlsx?${params.toString()}`;
  }

  function ensureSingleExport() {
    const toolbar = document.getElementById('mr-single-controls');
    if (!toolbar) return;

    const existing = [...toolbar.querySelectorAll('#mr-export-single')];
    existing.slice(1).forEach(node => node.remove());
    if (existing[0]) {
      existing[0].title = '현재 화면의 선택 분기 데이터를 Excel로 다운로드';
      return;
    }

    const btn = document.createElement('button');
    btn.type = 'button';
    btn.id = 'mr-export-single';
    btn.className = 'mr-secondary-btn mr-single-export-btn';
    btn.textContent = '⬇ Excel 다운로드';
    btn.title = '현재 화면의 선택 분기 데이터를 Excel로 다운로드';
    toolbar.appendChild(btn);
  }

  function normalizeCompareExport() {
    const btn = document.getElementById('mr-export');
    if (!btn) return;
    btn.title = '현재 화면의 기준분기·비교분기 데이터를 Excel로 다운로드';
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
    normalizeCompareExport();
    ensureScrollableReport();
    resetAccidentalHorizontalScroll();
  }

  function schedule() {
    clearTimeout(timer);
    timer = setTimeout(stabilize, 20);
  }

  const observer = new MutationObserver(schedule);
  observer.observe(document.documentElement, { childList: true, subtree: true });

  document.addEventListener('click', event => {
    const exportButton = event.target.closest?.('#mr-export-single,#mr-export');
    if (exportButton) {
      // Capture phase에서 기존 비교용 export handler보다 먼저 처리한다.
      // 현재 탭/모드에 맞는 V2 export만 한 번 실행한다.
      event.preventDefault();
      event.stopImmediatePropagation();
      exportCurrentView();
      return;
    }

    if (event.target.closest?.('#management-report-open,#management-report-open-mobile,[data-mi-section],[data-mr-mode],#mr-single-run,#mr-run')) {
      setTimeout(stabilize, 40);
    }
  }, true);

  window.addEventListener('resize', schedule, { passive: true });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', stabilize, { once: true });
  } else {
    stabilize();
  }
})();
