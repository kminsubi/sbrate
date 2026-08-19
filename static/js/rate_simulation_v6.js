/* SBRate Rate Simulation V6
   Adds a single-select market basis without replacing the stable V3 UI.
*/
(()=>{
  'use strict';

  if(window.__sbrateRateSimulationV6) return;
  window.__sbrateRateSimulationV6=true;

  const rawFetch=window.fetch.bind(window);
  let lastData=null;

  const $=(selector,root=document)=>root?.querySelector(selector)||null;
  const $$=(selector,root=document)=>root?[...root.querySelectorAll(selector)]:[];

  const activeRoot=()=>{
    const mobile=$('#rate-simulation-v3-mobile');
    if(mobile?.classList.contains('is-open')) return mobile;
    const pc=$('#rate-simulation-v3-layer');
    if(pc?.classList.contains('is-open')) return pc;
    return mobile || pc;
  };

  const shortBank=(name)=>String(name||'-').replace(/저축은행/g,'').trim();
  const rate=(value)=>Number.isFinite(Number(value))?`${Number(value).toFixed(2)}%`:'-';

  function pickerMarkup(root){
    const suffix=root?.id==='rate-simulation-v3-mobile'?'mobile':'pc';
    return `
      <div class="rate-simulation-basis-picker" data-sim-market-picker>
        <span class="rate-simulation-basis-caption">비교기준</span>
        <div class="rate-simulation-basis-options">
          <label class="rate-simulation-basis-option">
            <input type="radio" name="rate-sim-market-${suffix}" value="all_products">
            <span>전체상품</span>
          </label>
          <label class="rate-simulation-basis-option">
            <input type="radio" name="rate-sim-market-${suffix}" value="bank_best" checked>
            <span>은행별 최고금리</span>
          </label>
        </div>
      </div>`;
  }

  function installPicker(root){
    if(!root || $('[data-sim-market-picker]',root)) return;
    const controls=$('.rate-simulation-controls',root);
    if(!controls) return;

    // Comparison basis is the first decision in the simulator, so place it
    // above period/product selection. Visual order is all-products first,
    // bank-best second, while bank-best remains the default calculation basis.
    controls.insertAdjacentHTML('beforebegin',pickerMarkup(root));
    root.dataset.marketBasis=root.dataset.marketBasis||'bank_best';

    $$('[data-sim-market-picker] input[type="radio"]',root).forEach(input=>{
      input.checked=input.value===root.dataset.marketBasis;
      input.addEventListener('change',()=>{
        if(!input.checked) return;
        root.dataset.marketBasis=input.value;
        const period=$('[data-sim-period]',root);
        if(period){
          period.dispatchEvent(new Event('change',{bubbles:true}));
        }
      });
    });
  }

  function installAllPickers(){
    installPicker($('#rate-simulation-v3-layer'));
    installPicker($('#rate-simulation-v3-mobile'));
  }

  function cardLabelFor(selector,root){
    const node=$(selector,root);
    const card=node?.closest('.rate-simulation-card');
    return card?$('.rate-simulation-label',card):null;
  }

  function ensureTotal(root){
    const rankNode=$('[data-sim-rank-to]',root);
    const card=rankNode?.closest('.rate-simulation-card');
    if(!card) return null;
    let total=$('[data-sim-market-total]',card);
    if(!total){
      total=document.createElement('small');
      total.setAttribute('data-sim-market-total','');
      total.className='rate-simulation-market-total';
      card.appendChild(total);
    }
    return total;
  }

  function zoneMarkup(data){
    const simulated=data?.simulated||{};
    const basis=data?.market_basis||'bank_best';
    const bankBest=data?.bank_best||{};
    const selected=data?.selected_product||'-';

    const label=(row)=>{
      if(!row) return '-';
      if(basis==='all_products'){
        return `${shortBank(row.bank)} · ${row.product||'-'}`;
      }
      return shortBank(row.bank);
    };

    const result=[];
    if(simulated.above){
      result.push(`<div class="rate-simulation-neighbor"><span>바로 위 · ${label(simulated.above)}</span><b>${rate(simulated.above.rate)}</b></div>`);
    }
    result.push(`<div class="rate-simulation-neighbor is-woori"><span>우리금융 · ${basis==='all_products'?selected:(bankBest.simulated_product||selected)}</span><b>${rate(basis==='all_products'?simulated.rate:bankBest.simulated_rate)}</b></div>`);
    if(simulated.below){
      result.push(`<div class="rate-simulation-neighbor"><span>바로 아래 · ${label(simulated.below)}</span><b>${rate(simulated.below.rate)}</b></div>`);
    }
    return result.join('');
  }

  function syncResult(data,root=activeRoot()){
    if(!data?.ok || !root) return;
    installPicker(root);
    lastData=data;

    const basis=data.market_basis||'bank_best';
    root.dataset.marketBasis=basis;
    $$('[data-sim-market-picker] input[type="radio"]',root).forEach(input=>{
      input.checked=input.value===basis;
    });

    const titleBasis=$('[data-sim-basis]',root);
    if(titleBasis){
      titleBasis.textContent=`${data.category_label} · ${data.period}개월 · ${data.market_basis_label}`;
    }

    const rankLabel=cardLabelFor('[data-sim-rank-from]',root);
    if(rankLabel) rankLabel.textContent=basis==='all_products'?'전체상품 순위':'시장 순위';

    const financialLabel=cardLabelFor('[data-sim-fin-from]',root);
    if(financialLabel) financialLabel.textContent=basis==='all_products'?'금융지주계 상품순위':'금융지주계 순위';

    const top10Label=cardLabelFor('[data-sim-top10]',root);
    const top5Label=cardLabelFor('[data-sim-top5]',root);
    if(top10Label) top10Label.textContent=basis==='all_products'?'전체상품 TOP10 경쟁선':'TOP10 경쟁선';
    if(top5Label) top5Label.textContent=basis==='all_products'?'전체상품 TOP5 경쟁선':'TOP5 경쟁선';

    const total=ensureTotal(root);
    if(total){
      total.textContent=basis==='all_products'
        ? `전체 ${data.simulated?.total||0}상품 기준`
        : `전체 ${data.simulated?.total||0}개사 기준`;
    }

    const note=$('[data-sim-note]',root);
    if(note){
      if(basis==='all_products'){
        note.textContent=`${data.selected_product} 자체를 전체 상품 기준으로 비교합니다. 당행 최고금리 카드는 선택상품 조정이 우리금융 대표 최고금리에 미치는 영향을 별도로 보여줍니다.`;
      }else if(data.bank_best?.product_changed){
        note.textContent=`${data.selected_product} 조정으로 당행 최고금리 상품이 ${data.bank_best.current_product} → ${data.bank_best.simulated_product}로 변경됩니다. 시장순위는 은행별 최고금리 기준입니다.`;
      }else{
        note.textContent=`${data.bank_best?.simulated_product||data.selected_product} ${rate(data.bank_best?.simulated_rate)}가 당행 최고금리입니다. 시장순위는 각 저축은행의 최고금리 상품만 비교합니다.`;
      }
    }

    const zone=$('[data-sim-zone]',root);
    if(zone) zone.innerHTML=zoneMarkup(data);
  }

  window.fetch=async function(input,init){
    let url=typeof input==='string'?input:(input?.url||'');
    if(!url.includes('/api/rate-simulation-v2')){
      return rawFetch(input,init);
    }

    const root=activeRoot();
    const basis=root?.dataset.marketBasis||'bank_best';
    let body={};
    try{
      body=init?.body?JSON.parse(init.body):{};
    }catch(_error){
      body={};
    }
    body.market_basis=basis;

    const nextInit={
      ...(init||{}),
      body:JSON.stringify(body),
      headers:{'Content-Type':'application/json',...(init?.headers||{})},
    };
    const response=await rawFetch('/api/rate-simulation-v6',nextInit);

    try{
      response.clone().json().then(data=>{
        setTimeout(()=>syncResult(data,root),40);
      }).catch(()=>{});
    }catch(_error){}

    return response;
  };

  const observer=new MutationObserver(()=>installAllPickers());
  observer.observe(document.documentElement,{subtree:true,childList:true});

  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded',installAllPickers,{once:true});
  }else{
    installAllPickers();
  }

  window.addEventListener('resize',()=>{
    if(lastData) setTimeout(()=>syncResult(lastData),20);
  });
})();
