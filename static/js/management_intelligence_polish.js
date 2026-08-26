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

  function fixProfitabilityPeriodicity() {
    const root = document.getElementById('mi-content');
    if (!root) return;

    const profitability = [...root.querySelectorAll('.mi-block')].find(block =>
      (block.querySelector('.mi-block-title')?.textContent || '').includes('우리금융 수익성')
    );
    if (!profitability) return;

    if (!profitability.querySelector('[data-mi-roa-period-note]')) {
      const note = document.createElement('div');
      note.className = 'mi-note';
      note.dataset.miRoaPeriodNote = 'true';
      note.innerHTML = '<b>ROA·ROE 안내</b> · FISIS 저축은행 수익성(SE010)은 분기(Q) 조회를 지원하지 않습니다. 최신 분기 화면에서는 값을 추정하지 않고 <b>-</b>로 표시하며, 당기순이익·영업이익·이자수익·이자비용 등 실제 분기 공시 실적만 사용합니다.';
      profitability.appendChild(note);
    }
  }

  function polish() {
    fixFundingLabels();
    fixProfitabilityPeriodicity();
  }

  const observer = new MutationObserver(polish);
  observer.observe(document.documentElement, { childList: true, subtree: true });
  document.addEventListener('click', event => {
    if (event.target.closest?.('[data-mr-mode],#mr-single-run,#mr-run,[data-mi-section]')) {
      setTimeout(polish, 120);
    }
  }, true);
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', polish, { once: true });
  } else {
    polish();
  }
})();
