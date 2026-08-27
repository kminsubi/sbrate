(() => {
  'use strict';

  let timer = null;

  function reparentDetailLayers() {
    const panel = document.getElementById('ids-bank-detail-panel');
    const backdrop = document.getElementById('ids-bank-detail-backdrop');
    if (backdrop && backdrop.parentElement !== document.body) document.body.appendChild(backdrop);
    if (panel && panel.parentElement !== document.body) document.body.appendChild(panel);
  }

  function schedule() {
    if (timer) return;
    timer = setTimeout(() => {
      timer = null;
      reparentDetailLayers();
    }, 20);
  }

  const observer = new MutationObserver(schedule);
  observer.observe(document.documentElement, { childList: true, subtree: true });

  document.addEventListener('DOMContentLoaded', reparentDetailLayers, { once: true });
  document.addEventListener('click', event => {
    if (event.target.closest?.('#management-report-open,#management-report-open-mobile,.ids-bank-link')) {
      setTimeout(reparentDetailLayers, 40);
      setTimeout(reparentDetailLayers, 180);
    }
  }, true);

  reparentDetailLayers();
})();
