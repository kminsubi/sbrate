(() => {
  'use strict';

  function readMarketLowestRate() {
    const direct = document.getElementById('kpi-lowest-rate-mini')?.textContent?.trim();
    if (direct && direct !== '-') return direct;

    try {
      if (typeof currentMarketItems !== 'undefined' && Array.isArray(currentMarketItems)) {
        const rates = currentMarketItems
          .map(item => Number(item?.rate))
          .filter(rate => Number.isFinite(rate) && rate > 0);
        if (rates.length) return `${Math.min(...rates).toFixed(2)}%`;
      }
    } catch (_) {
      // Fall through to the existing placeholder.
    }
    return '-';
  }

  function normalizeDepositAiSummary() {
    const root = document.getElementById('executive-summary-mini');
    if (!root) return;

    const labels = [...root.querySelectorAll('span')];
    const hasSpread = labels.some(node => (node.textContent || '').trim() === '금리 스프레드');
    const hasMarketTop = labels.some(node => (node.textContent || '').trim() === '시장 최고');
    if (!hasSpread || !hasMarketTop) return;

    // The AI opinion already explains Woori's position/rate.  The market
    // snapshot should stay MECE and show the missing market-low metric.
    const duplicateWoori = labels.find(node => (node.textContent || '').trim() === '우리금융');
    if (!duplicateWoori) return;

    duplicateWoori.textContent = '시장 최저';
    const value = duplicateWoori.nextElementSibling;
    if (value) {
      value.textContent = readMarketLowestRate();
      value.classList.remove('text-blue-700');
      value.classList.add('text-gray-800');
    }
  }

  function install() {
    normalizeDepositAiSummary();
    const root = document.getElementById('executive-summary-mini');
    if (!root || root.dataset.sbrateFinalGuard === '1') return;
    root.dataset.sbrateFinalGuard = '1';
    new MutationObserver(normalizeDepositAiSummary).observe(root, {
      childList: true,
      subtree: true,
      characterData: true,
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', install, { once: true });
  } else {
    install();
  }

  // Dashboard data is async; a short deferred pass covers the first render
  // even if the summary element was populated after DOMContentLoaded.
  window.addEventListener('load', () => {
    install();
    setTimeout(normalizeDepositAiSummary, 250);
    setTimeout(normalizeDepositAiSummary, 1200);
  }, { once: true });
})();
