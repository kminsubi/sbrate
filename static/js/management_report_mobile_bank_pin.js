(() => {
  'use strict';

  let timer = null;

  const mobile = () => window.matchMedia('(max-width: 900px)').matches;
  const shortBankName = value => String(value || '').replace(/\s*저축은행\s*$/g, '').trim();

  function shortenBankCell(cell) {
    if (!cell || cell.tagName === 'TH') return;
    const original = String(cell.textContent || '').trim();
    const shortened = shortBankName(original);
    if (!shortened || shortened === original) return;
    if (!cell.title) cell.title = original;
    cell.textContent = shortened;
  }

  function tagIntelligenceSourceColumns() {
    document.querySelectorAll('#mi-content .mi-table').forEach(table => {
      table.querySelectorAll('tr').forEach(row => {
        const cells = [...row.children].filter(node => /^(TH|TD)$/.test(node.tagName));
        if (!cells.length || row.dataset.miColumnsTagged === '1') return;

        if (row.closest('thead')) {
          const bank = cells.find(cell => (cell.textContent || '').trim() === '저축은행');
          if (!bank) return;
          const bankIndex = cells.indexOf(bank);
          bank.classList.add('mi-col-bank');
          cells[0]?.classList.add('mi-col-rank');
          cells[bankIndex + 1]?.classList.add('mi-col-region');
          row.dataset.miColumnsTagged = '1';
          return;
        }

        // Intelligence body rows are rendered rank / bank / region / metrics.
        if (cells.length >= 3) {
          cells[0].classList.add('mi-col-rank');
          cells[1].classList.add('mi-col-bank');
          cells[2].classList.add('mi-col-region');
          row.dataset.miColumnsTagged = '1';
        }
      });
    });
  }

  function moveBankFirst(row, bank) {
    if (row && bank && row.firstElementChild !== bank) row.insertBefore(bank, row.firstElementChild);
  }

  function restoreBankBeforeRegion(row, bank, region) {
    if (row && bank && region && bank.nextElementSibling !== region) row.insertBefore(bank, region);
  }

  function normalizeGeneralOrder() {
    const table = document.getElementById('mr-table');
    if (!table) return;
    table.querySelectorAll('tr').forEach(row => {
      const bank = row.querySelector(':scope > .mr-col-bank');
      if (!bank) return;
      shortenBankCell(bank);
      if (mobile()) moveBankFirst(row, bank);
      else restoreBankBeforeRegion(row, bank, row.querySelector(':scope > .mr-col-region'));
    });
  }

  function normalizeIntelligenceOrder() {
    tagIntelligenceSourceColumns();
    document.querySelectorAll('#mi-content .mi-table tr').forEach(row => {
      const bank = row.querySelector(':scope > .mi-col-bank');
      if (!bank) return;
      shortenBankCell(bank);
      if (mobile()) moveBankFirst(row, bank);
      else restoreBankBeforeRegion(row, bank, row.querySelector(':scope > .mi-col-region'));
    });
  }

  function normalizeFloatingHeaderOrder() {
    if (!mobile()) return;
    const clone = document.querySelector('#mr-mobile-column-header .mr-mobile-floating-table');
    if (!clone) return;
    clone.querySelectorAll('tr').forEach(row => {
      const bank = row.querySelector(':scope > .mr-col-bank,:scope > .mi-col-bank');
      if (bank) moveBankFirst(row, bank);
    });
  }

  function syncPinScroll(wrapper = null) {
    if (!mobile()) return;
    const activeWrapper = wrapper
      || [...document.querySelectorAll('#management-report-modal .mr-table-wrap,#management-report-modal .mi-table-wrap')]
        .find(node => node.offsetParent !== null);
    const scrollLeft = Math.max(0, Number(activeWrapper?.scrollLeft || 0));
    const modal = document.getElementById('management-report-modal');
    if (modal) modal.style.setProperty('--mr-bank-pin-scroll', `${scrollLeft}px`);
  }

  function normalize() {
    normalizeGeneralOrder();
    normalizeIntelligenceOrder();
    normalizeFloatingHeaderOrder();
    syncPinScroll();
  }

  function schedule() {
    clearTimeout(timer);
    timer = setTimeout(normalize, 20);
  }

  const observer = new MutationObserver(schedule);
  observer.observe(document.documentElement, { childList: true, subtree: true });

  document.addEventListener('scroll', event => {
    const target = event.target;
    if (target instanceof Element && target.matches('.mr-table-wrap,.mi-table-wrap')) {
      syncPinScroll(target);
      requestAnimationFrame(() => {
        normalizeFloatingHeaderOrder();
        syncPinScroll(target);
      });
    }
  }, true);

  document.addEventListener('click', event => {
    if (event.target.closest?.('[data-mi-section],[data-mr-mode],#mr-single-run,#mr-run,#management-report-open-mobile')) {
      setTimeout(() => {
        normalize();
        const visible = [...document.querySelectorAll('#management-report-modal .mr-table-wrap,#management-report-modal .mi-table-wrap')]
          .find(node => node.offsetParent !== null);
        if (visible) visible.scrollLeft = 0;
        syncPinScroll(visible);
      }, 80);
    }
  }, true);

  window.addEventListener('resize', schedule, { passive: true });

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', normalize, { once: true });
  else normalize();
})();
