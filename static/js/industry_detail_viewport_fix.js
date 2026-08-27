(() => {
  'use strict';

  let timer = null;
  const BACKDROP_Z = '100050';
  const PANEL_Z = '100060';

  function reparentDetailLayers() {
    const panel = document.getElementById('ids-bank-detail-panel');
    const backdrop = document.getElementById('ids-bank-detail-backdrop');

    if (backdrop) {
      if (backdrop.parentElement !== document.body) document.body.appendChild(backdrop);
      backdrop.style.zIndex = BACKDROP_Z;
    }
    if (panel) {
      if (panel.parentElement !== document.body) document.body.appendChild(panel);
      panel.style.zIndex = PANEL_Z;
    }
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
