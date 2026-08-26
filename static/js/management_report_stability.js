(() => {
  'use strict';

  let timer = null;
  let mobileHeaderRaf = null;
  const mobileHeaderState = {
    overlay: null,
    viewport: null,
    cloneTable: null,
    sourceTable: null,
    wrapper: null,
    wrapperScrollHandler: null,
    modal: null,
  };

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

  function isMobileReport() {
    return window.matchMedia('(max-width: 900px)').matches;
  }

  function visibleManagementTable() {
    const general = document.getElementById('mr-table');
    const intelligence = [...document.querySelectorAll('#mi-content .mi-table')];
    return [general, ...intelligence].find(table => {
      if (!table || table.offsetParent === null) return false;
      const rect = table.getBoundingClientRect();
      return rect.width > 0 && rect.height > 0;
    }) || null;
  }

  function tableScrollWrapper(table) {
    if (!table) return null;
    return table.closest('.mr-table-wrap,.mi-table-wrap') || table.parentElement;
  }

  function copyHeaderPresentation(sourceThead, cloneThead) {
    const sourceRows = [...sourceThead.querySelectorAll('tr')];
    const cloneRows = [...cloneThead.querySelectorAll('tr')];
    sourceRows.forEach((row, index) => {
      const target = cloneRows[index];
      if (!target) return;
      const style = getComputedStyle(row);
      const height = row.getBoundingClientRect().height;
      if (height > 0) target.style.height = `${height}px`;
      target.style.backgroundColor = style.backgroundColor;
    });

    const sourceCells = [...sourceThead.querySelectorAll('th')];
    const cloneCells = [...cloneThead.querySelectorAll('th')];
    const props = [
      'fontFamily','fontSize','fontWeight','lineHeight','letterSpacing','color','backgroundColor',
      'borderTopWidth','borderTopStyle','borderTopColor','borderRightWidth','borderRightStyle','borderRightColor',
      'borderBottomWidth','borderBottomStyle','borderBottomColor','borderLeftWidth','borderLeftStyle','borderLeftColor',
      'paddingTop','paddingRight','paddingBottom','paddingLeft','textAlign','verticalAlign','whiteSpace','boxSizing'
    ];

    sourceCells.forEach((cell, index) => {
      const target = cloneCells[index];
      if (!target) return;
      const style = getComputedStyle(cell);
      const width = cell.getBoundingClientRect().width;
      props.forEach(prop => {
        target.style[prop] = style[prop];
      });
      if (width > 0) {
        target.style.width = `${width}px`;
        target.style.minWidth = `${width}px`;
        target.style.maxWidth = `${width}px`;
      }
      target.style.position = 'relative';
      target.style.left = 'auto';
      target.style.top = 'auto';
      target.style.boxShadow = style.boxShadow;
    });
  }

  function mobileBankHeaderCells(table) {
    if (!table) return [];
    const direct = [...table.querySelectorAll('thead .mr-col-bank')];
    if (direct.length) return direct;
    if (table.classList.contains('mi-table')) {
      return [...table.querySelectorAll('thead tr > th:nth-child(2)')];
    }
    return [];
  }

  function destroyMobileTableHeader() {
    if (mobileHeaderState.wrapper && mobileHeaderState.wrapperScrollHandler) {
      mobileHeaderState.wrapper.removeEventListener('scroll', mobileHeaderState.wrapperScrollHandler);
    }
    mobileHeaderState.overlay?.remove();
    mobileHeaderState.overlay = null;
    mobileHeaderState.viewport = null;
    mobileHeaderState.cloneTable = null;
    mobileHeaderState.sourceTable = null;
    mobileHeaderState.wrapper = null;
    mobileHeaderState.wrapperScrollHandler = null;
  }

  function buildMobileTableHeader(table) {
    const modal = document.getElementById('management-report-modal');
    const wrapper = tableScrollWrapper(table);
    const sourceThead = table?.tHead;
    if (!modal || !wrapper || !sourceThead) {
      destroyMobileTableHeader();
      return;
    }

    destroyMobileTableHeader();

    const overlay = document.createElement('div');
    overlay.id = 'mr-mobile-column-header';
    overlay.className = 'mr-mobile-column-header';
    overlay.setAttribute('aria-hidden', 'true');

    const viewport = document.createElement('div');
    viewport.className = 'mr-mobile-column-header-viewport';

    const cloneTable = table.cloneNode(false);
    cloneTable.removeAttribute('id');
    cloneTable.classList.add('mr-mobile-floating-table');
    cloneTable.setAttribute('aria-hidden', 'true');
    const cloneThead = sourceThead.cloneNode(true);
    cloneTable.appendChild(cloneThead);
    viewport.appendChild(cloneTable);
    overlay.appendChild(viewport);
    modal.appendChild(overlay);

    const sourceTableStyle = getComputedStyle(table);
    cloneTable.style.borderCollapse = sourceTableStyle.borderCollapse;
    cloneTable.style.borderSpacing = sourceTableStyle.borderSpacing;
    cloneTable.style.tableLayout = sourceTableStyle.tableLayout;
    cloneTable.style.fontFamily = sourceTableStyle.fontFamily;
    cloneTable.style.width = `${Math.max(table.scrollWidth, table.getBoundingClientRect().width)}px`;
    cloneTable.style.minWidth = cloneTable.style.width;
    copyHeaderPresentation(sourceThead, cloneThead);

    const sourceBankCells = mobileBankHeaderCells(table);
    const cloneBankCells = mobileBankHeaderCells(cloneTable);
    cloneBankCells.forEach((cell, index) => {
      const source = sourceBankCells[index];
      const naturalLeft = source ? source.offsetLeft : 0;
      cell.dataset.mobileBankNaturalLeft = String(naturalLeft || 0);
      cell.style.zIndex = '5';
    });

    const wrapperScrollHandler = () => scheduleMobileTableHeader();
    wrapper.addEventListener('scroll', wrapperScrollHandler, { passive: true });

    mobileHeaderState.overlay = overlay;
    mobileHeaderState.viewport = viewport;
    mobileHeaderState.cloneTable = cloneTable;
    mobileHeaderState.sourceTable = table;
    mobileHeaderState.wrapper = wrapper;
    mobileHeaderState.wrapperScrollHandler = wrapperScrollHandler;
    mobileHeaderState.modal = modal;
  }

  function syncMobileTableHeader() {
    mobileHeaderRaf = null;
    const modal = document.getElementById('management-report-modal');
    if (!isMobileReport() || !modal?.classList.contains('is-open')) {
      if (mobileHeaderState.overlay) mobileHeaderState.overlay.style.display = 'none';
      return;
    }

    const table = visibleManagementTable();
    if (!table?.tHead) {
      destroyMobileTableHeader();
      return;
    }
    if (table !== mobileHeaderState.sourceTable || !mobileHeaderState.overlay?.isConnected) {
      buildMobileTableHeader(table);
    }

    const overlay = mobileHeaderState.overlay;
    const cloneTable = mobileHeaderState.cloneTable;
    const wrapper = mobileHeaderState.wrapper;
    const topbar = modal.querySelector('.mr-topbar');
    if (!overlay || !cloneTable || !wrapper || !topbar) return;

    const tableRect = table.getBoundingClientRect();
    const wrapperRect = wrapper.getBoundingClientRect();
    const topbarRect = topbar.getBoundingClientRect();
    const headerHeight = table.tHead.getBoundingClientRect().height;
    const stickyTop = Math.max(0, Math.round(topbarRect.bottom));
    const shouldShow = tableRect.top < stickyTop && tableRect.bottom > stickyTop + headerHeight + 4;

    if (!shouldShow) {
      overlay.style.display = 'none';
      return;
    }

    const left = Math.max(0, wrapperRect.left);
    const width = Math.max(0, Math.min(wrapperRect.right, window.innerWidth) - left);
    if (width <= 0) {
      overlay.style.display = 'none';
      return;
    }

    overlay.style.display = 'block';
    overlay.style.top = `${stickyTop}px`;
    overlay.style.left = `${left}px`;
    overlay.style.width = `${width}px`;
    overlay.style.height = `${Math.ceil(headerHeight)}px`;

    const scrollLeft = wrapper.scrollLeft || 0;
    cloneTable.style.transform = `translate3d(${-scrollLeft}px,0,0)`;

    mobileBankHeaderCells(cloneTable).forEach(cell => {
      const naturalLeft = Number(cell.dataset.mobileBankNaturalLeft || 0);
      const correction = Math.max(0, scrollLeft - naturalLeft);
      cell.style.transform = `translate3d(${correction}px,0,0)`;
    });
  }

  function scheduleMobileTableHeader() {
    if (mobileHeaderRaf !== null) return;
    mobileHeaderRaf = requestAnimationFrame(syncMobileTableHeader);
  }

  function ensureMobileTableHeader() {
    const modal = document.getElementById('management-report-modal');
    if (!modal) return;

    if (mobileHeaderState.modal !== modal) {
      mobileHeaderState.modal = modal;
      if (modal.dataset.mobileColumnHeaderBound !== '1') {
        modal.dataset.mobileColumnHeaderBound = '1';
        modal.addEventListener('scroll', scheduleMobileTableHeader, { passive: true });
      }
    }

    if (!isMobileReport()) {
      destroyMobileTableHeader();
      return;
    }

    const table = visibleManagementTable();
    if (table && table !== mobileHeaderState.sourceTable) {
      buildMobileTableHeader(table);
    }
    scheduleMobileTableHeader();
  }

  function ensureScrollableReport() {
    const modal = document.getElementById('management-report-modal');
    const shell = modal?.querySelector('.mr-shell');
    if (!modal || !shell) return;
    modal.classList.add('mr-scroll-stable');
    shell.setAttribute('data-scroll-ready', '1');
    ensureMobileTableHeader();
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
      setTimeout(() => {
        stabilize();
        scheduleMobileTableHeader();
      }, 40);
    }
  }, true);

  window.addEventListener('resize', () => {
    schedule();
    scheduleMobileTableHeader();
  }, { passive: true });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', stabilize, { once: true });
  } else {
    stabilize();
  }
})();
