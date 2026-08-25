(() => {
  'use strict';

  function activeCompareLabel() {
    return document.querySelector('#management-report-modal [data-mr-mode="compare"].is-active')
      ? '비교분기比'
      : '전분기比';
  }

  function fixFundingLabels() {
    const root = document.getElementById('mi-content');
    if (!root) return;
    root.querySelectorAll('.mi-block').forEach(block => {
      const title = block.querySelector('.mi-block-title')?.textContent?.trim() || '';
      if (!title.startsWith('확정 실적')) return;
      block.querySelectorAll('.mi-card-sub').forEach(sub => {
        const text = sub.textContent || '';
        if (!text.includes('function compareLabel') && !text.includes('isCompareMode')) return;
        const delta = sub.querySelector('.mi-delta');
        sub.innerHTML = `${activeCompareLabel()} ${delta ? delta.outerHTML : '<span class="mi-delta flat">-</span>'}`;
      });
    });
  }

  const observer = new MutationObserver(fixFundingLabels);
  observer.observe(document.documentElement, { childList: true, subtree: true });
  document.addEventListener('click', event => {
    if (event.target.closest?.('[data-mr-mode],#mr-single-run,#mr-run,[data-mi-section]')) {
      setTimeout(fixFundingLabels, 120);
    }
  }, true);
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', fixFundingLabels, { once: true });
  } else {
    fixFundingLabels();
  }
})();
