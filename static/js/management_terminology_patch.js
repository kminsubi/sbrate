(() => {
  'use strict';

  let timer = null;

  function setText(node, value) {
    if (node && node.textContent !== value) node.textContent = value;
  }

  function renameTableTitle() {
    const title = document.getElementById('mr-table-title');
    if (!title) return;
    const current = String(title.textContent || '').trim();
    let next = current;
    if (current === '업권 경영현황') next = '업권 경영지표';
    else if (/경영현황$/.test(current)) next = current.replace(/경영현황$/, '경영지표');
    if (next !== current) title.textContent = next;
  }

  function renameStatus() {
    const status = document.getElementById('mr-status');
    if (!status) return;
    const current = String(status.textContent || '');
    const next = current
      .replace('경영현황을 비교하고 있습니다.', '업권현황을 비교하고 있습니다.')
      .replace('선택 분기 경영현황을 조회하고 있습니다.', '선택 분기 경영지표를 조회하고 있습니다.');
    if (next !== current) status.textContent = next;
  }

  function applyTerminology() {
    const desktop = document.getElementById('management-report-open');
    if (desktop) {
      setText(desktop, '📑 업권현황');
      desktop.title = 'FISIS 저축은행 업권현황 열기';
    }

    const mobile = document.getElementById('management-report-open-mobile');
    if (mobile) {
      setText(mobile, '📑 업권현황');
      mobile.title = 'FISIS 저축은행 업권현황 열기';
    }

    const shell = document.querySelector('#management-report-modal .mr-shell');
    if (shell && shell.getAttribute('aria-label') !== '저축은행 업권현황') {
      shell.setAttribute('aria-label', '저축은행 업권현황');
    }

    setText(document.querySelector('#management-report-modal .mr-title-block h2'), '저축은행 업권현황');

    const generalTab = document.querySelector('#mi-section-tabs [data-mi-section="general"]');
    setText(generalTab, '경영지표');
    if (generalTab) generalTab.title = '저축은행 업권 핵심 경영지표';

    renameTableTitle();
    renameStatus();
  }

  function scheduleApply() {
    clearTimeout(timer);
    timer = setTimeout(applyTerminology, 30);
  }

  const observer = new MutationObserver(scheduleApply);
  observer.observe(document.documentElement, { childList: true, subtree: true, characterData: true });

  document.addEventListener('DOMContentLoaded', applyTerminology, { once: true });
  document.addEventListener('click', event => {
    if (event.target.closest?.('#management-report-open,#management-report-open-mobile,#mi-section-tabs,[data-mr-mode],#mr-single-run,#mr-run')) {
      setTimeout(applyTerminology, 80);
      setTimeout(applyTerminology, 300);
    }
  }, true);

  applyTerminology();
})();
