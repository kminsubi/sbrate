(() => {
  'use strict';

  let enhanceTimer = null;

  function shortBankName(value) {
    return String(value || '')
      .replace(/\s*저축은행\s*$/g, '')
      .trim();
  }

  function shortenDisplayedBankNames() {
    document.querySelectorAll('#mr-table tbody .mr-col-bank').forEach(cell => {
      const original = String(cell.textContent || '').trim();
      const shortened = shortBankName(original);
      if (!shortened || shortened === original) return;
      if (!cell.title) cell.title = original;
      cell.textContent = shortened;
    });

    document.querySelectorAll('#mi-content .mi-table tbody tr').forEach(row => {
      const cell = row.cells?.[1];
      if (!cell) return;
      const original = String(cell.textContent || '').trim();
      const shortened = shortBankName(original);
      if (!shortened || shortened === original) return;
      if (!cell.title) cell.title = original;
      cell.textContent = shortened;
    });
  }

  function pulseRow(row) {
    if (!row) return;
    row.classList.remove('mi-woori-focus-pulse');
    void row.offsetWidth;
    row.classList.add('mi-woori-focus-pulse');
    window.setTimeout(() => row.classList.remove('mi-woori-focus-pulse'), 1800);
  }

  function focusIntelligenceWoori(wrap) {
    const row = wrap?.querySelector('tbody tr.mi-woori');
    if (!row) return;

    pulseRow(row);

    if (wrap.scrollHeight > wrap.clientHeight + 8) {
      const targetTop = Math.max(
        0,
        row.offsetTop - (wrap.clientHeight / 2) + (row.offsetHeight / 2)
      );
      wrap.scrollTo({ top: targetTop, behavior: 'smooth' });
      return;
    }

    const shell = row.closest('.mr-shell');
    if (shell && shell.scrollHeight > shell.clientHeight + 8) {
      const rowRect = row.getBoundingClientRect();
      const shellRect = shell.getBoundingClientRect();
      const targetTop = Math.max(
        0,
        shell.scrollTop + rowRect.top - shellRect.top - (shell.clientHeight / 2) + (rowRect.height / 2)
      );
      shell.scrollTo({ top: targetTop, behavior: 'smooth' });
      return;
    }

    row.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'nearest' });
  }

  function ensureIntelligenceWooriButtons() {
    document.querySelectorAll('#mi-content .mi-table-wrap').forEach((wrap, index) => {
      const block = wrap.closest('.mi-block');
      if (!block) return;

      let actions = block.querySelector('.mi-bank-focus-actions');
      if (!actions) {
        actions = document.createElement('div');
        actions.className = 'mi-bank-focus-actions';
        actions.innerHTML = `
          <span>업권 전체보기</span>
          <button type="button" class="mi-bank-focus-btn">우리금융 보기</button>`;
        wrap.insertAdjacentElement('beforebegin', actions);
      }

      const button = actions.querySelector('.mi-bank-focus-btn');
      if (!button) return;

      const hasWoori = !!wrap.querySelector('tbody tr.mi-woori');
      button.disabled = !hasWoori;
      button.dataset.focusIndex = String(index);

      if (button.dataset.bound !== '1') {
        button.dataset.bound = '1';
        button.addEventListener('click', () => focusIntelligenceWoori(wrap));
      }
    });
  }

  function enhance() {
    shortenDisplayedBankNames();
    ensureIntelligenceWooriButtons();
  }

  function scheduleEnhance() {
    window.clearTimeout(enhanceTimer);
    enhanceTimer = window.setTimeout(enhance, 30);
  }

  const observer = new MutationObserver(scheduleEnhance);
  observer.observe(document.documentElement, { childList: true, subtree: true });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', enhance, { once: true });
  } else {
    enhance();
  }
})();