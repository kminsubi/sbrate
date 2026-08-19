/* SBRate Rate Simulation V4 polish */
(()=>{
  'use strict';

  const formatStep=(value)=>{
    const n=Number(value);
    if(!Number.isFinite(n)) return '';
    return n<0
      ? `▲${Math.abs(n).toFixed(2)}%p`
      : `+${Math.abs(n).toFixed(2)}%p`;
  };

  const polish=()=>{
    document.querySelectorAll('[data-sim-step]').forEach(button=>{
      const label=formatStep(button.dataset.simStep);
      if(label && button.textContent!==label){
        button.textContent=label;
      }
    });

    document.querySelectorAll('[data-sim-delta] .sim-up,[data-sim-delta] .sim-down').forEach(node=>{
      const text=String(node.textContent||'').trim();
      if(text && !/%p$/.test(text)){
        node.textContent=`${text}%p`;
      }
    });
  };

  polish();
  document.addEventListener('DOMContentLoaded',polish,{once:true});
  new MutationObserver(polish).observe(document.documentElement,{
    subtree:true,
    childList:true,
    characterData:true
  });
})();
