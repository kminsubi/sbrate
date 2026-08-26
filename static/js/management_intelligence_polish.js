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

  function fixProfitabilityBasis() {
    const root = document.getElementById('mi-content');
    if (!root) return;

    const profitability = [...root.querySelectorAll('.mi-block')].find(block =>
      (block.querySelector('.mi-block-title')?.textContent || '').includes('우리금융 수익성')
    );
    if (!profitability) return;

    profitability.querySelectorAll('.mi-card-label').forEach(label => {
      const text = (label.textContent || '').trim();
      if (text === 'ROA') label.textContent = 'ROA(산출)';
      if (text === 'ROE') label.textContent = 'ROE(산출)';
    });

    root.querySelectorAll('.mi-table th').forEach(th => {
      const text = (th.textContent || '').trim();
      if (text === 'ROA') th.textContent = 'ROA(산출)';
      if (text === 'ROE') th.textContent = 'ROE(산출)';
    });

    const oldNote = profitability.querySelector('[data-mi-roa-period-note]');
    if (oldNote) oldNote.remove();

    if (!profitability.querySelector('[data-mi-roa-derived-note]')) {
      const note = document.createElement('div');
      note.className = 'mi-note';
      note.dataset.miRoaDerivedNote = 'true';
      note.innerHTML = '<b>ROA·ROE 안내</b> · FISIS 분기 원천자료의 누적 당기순이익과 전년말·분기말 총자산/자기자본 평균을 이용한 연환산 산출값입니다. FISIS SE010 공식 기간평잔 지표와는 소폭 차이가 날 수 있습니다.';
      profitability.appendChild(note);
    }
  }

  function polish() {
    fixFundingLabels();
    fixProfitabilityBasis();
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
