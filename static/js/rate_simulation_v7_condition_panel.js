/* SBRate Rate Simulation V7
   Group period/product controls into one compact condition subpanel.
   Keeps V6 market-basis logic and default calculation unchanged.
*/
(()=>{
  'use strict';

  if(window.__sbrateRateSimulationV7ConditionPanel) return;
  window.__sbrateRateSimulationV7ConditionPanel=true;

  const roots=()=>[
    document.querySelector('#rate-simulation-v3-layer'),
    document.querySelector('#rate-simulation-v3-mobile')
  ].filter(Boolean);

  function enhance(root){
    const controls=root.querySelector('.rate-simulation-controls');
    if(!controls) return;

    let panel=controls.closest('.rate-simulation-condition-panel');
    if(!panel){
      panel=document.createElement('section');
      panel.className='rate-simulation-condition-panel';
      panel.setAttribute('data-sim-condition-panel','');

      const caption=document.createElement('div');
      caption.className='rate-simulation-condition-caption';
      caption.textContent='시뮬레이션 조건';

      const parent=controls.parentNode;
      parent.insertBefore(panel,controls);
      panel.appendChild(caption);
      panel.appendChild(controls);
    }

    /* V6 may insert the comparison picker next to controls. Keep the final
       hierarchy stable: comparison basis first, then condition subpanel. */
    const picker=root.querySelector('[data-sim-market-picker]');
    if(picker && panel.parentNode){
      if(picker.parentNode===panel || panel.previousElementSibling!==picker){
        panel.parentNode.insertBefore(picker,panel);
      }
    }
  }

  function sync(){
    roots().forEach(enhance);
  }

  const observer=new MutationObserver(sync);
  observer.observe(document.documentElement,{subtree:true,childList:true});

  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded',()=>setTimeout(sync,0),{once:true});
  }else{
    setTimeout(sync,0);
  }
})();
