/* Ensures V3 entry point wins after legacy V1 scripts finish. */
(()=>{
  'use strict';

  const ensure=()=>{
    document.querySelectorAll('#rate-sim-open-pc,#rate-sim-open-mobile,#rate-sim-v2-open-pc,#rate-sim-v2-open-mobile,.sb2-mobile-row')
      .forEach(node=>node.remove());

    if(location.pathname==='/mobile' || document.querySelector('.app-shell')) return;
    if(document.getElementById('rate-simulation-open-pc')) return;

    const card=document.querySelector('#dashboard-hero-start > .col-span-4:first-child > .bg-white');
    const header=card?.querySelector(':scope > .flex.items-center.justify-between.mb-4');
    if(!header) return;

    const button=document.createElement('button');
    button.id='rate-simulation-open-pc';
    button.type='button';
    button.className='rate-simulation-open';
    button.textContent='📈 금리 시뮬레이션';
    button.addEventListener('click',()=>window.openSBRateSimulation?.());

    const slot=header.children[1];
    if(slot){
      slot.textContent='';
      slot.appendChild(button);
    }else{
      header.appendChild(button);
    }
  };

  const start=()=>{
    ensure();
    setTimeout(ensure,180);
    setTimeout(ensure,700);
  };

  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded',start,{once:true});
  }else{
    start();
  }
})();
