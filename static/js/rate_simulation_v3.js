/* SBRate Rate Simulation V3 - direct template asset */
(()=>{
  'use strict';

  const State={
    mobile:false,
    open:false,
    data:null,
    requestId:0,
    inputTimer:null,
    drag:null
  };

  const $=(selector,root=document)=>root.querySelector(selector);
  const $$=(selector,root=document)=>[...root.querySelectorAll(selector)];

  function isMobilePage(){
    return location.pathname==='/mobile' || !!$('.app-shell');
  }

  function category(){
    if(isMobilePage()){
      return $('#mobile-product-tabs .product-tab.is-active')?.dataset.product || 'deposit';
    }
    const active=$$('[data-market-product]').find(button=>
      button.classList.contains('text-white') || button.getAttribute('aria-selected')==='true'
    );
    return active?.dataset.marketProduct || 'deposit';
  }

  function categoryLabel(value=category()){
    return {deposit:'정기예금',isa:'ISA',irp:'퇴직연금(IRP)'}[value] || '정기예금';
  }

  function mainPeriod(){
    let period='12';
    if(isMobilePage()){
      period=$('#hero-product-label')?.textContent.match(/(1|3|6|12|24|36)\s*개월/)?.[1] || '12';
    }else{
      period=$('#product-period-select')?.value || '12';
    }
    if(category()!=='deposit' && period==='1') return '12';
    return period;
  }

  function rate(value){
    const n=Number(value);
    return Number.isFinite(n) ? `${n.toFixed(2)}%` : '-';
  }

  function change(value){
    const n=Number(value);
    if(!Number.isFinite(n) || Math.abs(n)<0.00001){
      return '<span class="sim-flat">-</span>';
    }
    return n>0
      ? `<span class="sim-up">+${Math.abs(n).toFixed(2)}%p</span>`
      : `<span class="sim-down">▲${Math.abs(n).toFixed(2)}%p</span>`;
  }

  function shortBank(name){
    return String(name||'-').replace(/저축은행/g,'').replace(/\s{2,}/g,' ').trim();
  }

  function rankStatus(from,to){
    const a=Number(from), b=Number(to);
    if(!Number.isFinite(a)||!Number.isFinite(b)) return {text:'-',cls:''};
    if(b<a) return {text:`${a-b}계단 개선`,cls:'good'};
    if(b>a) return {text:`${b-a}계단 악화`,cls:'bad'};
    return {text:'유지',cls:''};
  }

  function rateStatus(from,to){
    const a=Number(from), b=Number(to);
    if(!Number.isFinite(a)||!Number.isFinite(b)) return {text:'-',cls:''};
    if(b>a+0.00001) return {text:'상승',cls:'good'};
    if(b<a-0.00001) return {text:'하락',cls:'bad'};
    return {text:'유지',cls:''};
  }

  function bodyMarkup(){
    return `
      <div class="rate-simulation-controls">
        <div class="rate-simulation-field">
          <label>기간</label>
          <select data-sim-period aria-label="시뮬레이션 기간"></select>
        </div>
        <div class="rate-simulation-field">
          <label>우리금융 상품</label>
          <select data-sim-product aria-label="우리금융 상품"></select>
        </div>
      </div>

      <div class="rate-simulation-rate-row">
        <div class="rate-simulation-rate-box">
          <span class="rate-simulation-label">선택상품 현재금리</span>
          <div class="rate-simulation-big" data-sim-selected-current>-</div>
        </div>
        <div class="rate-simulation-arrow">→</div>
        <div class="rate-simulation-rate-box is-target">
          <span class="rate-simulation-label">시뮬레이션 금리</span>
          <div class="rate-simulation-target">
            <input data-sim-target type="number" min="0.01" max="10" step="0.01" inputmode="decimal" aria-label="시뮬레이션 금리" />
            <b>%</b>
          </div>
        </div>
      </div>

      <div class="rate-simulation-delta">금리변화 <span data-sim-delta>-</span></div>

      <div class="rate-simulation-presets">
        <button type="button" class="is-down" data-sim-step="-0.10">▲0.10</button>
        <button type="button" class="is-down" data-sim-step="-0.05">▲0.05</button>
        <button type="button" data-sim-current>현재</button>
        <button type="button" class="is-up" data-sim-step="0.05">+0.05</button>
        <button type="button" class="is-up" data-sim-step="0.10">+0.10</button>
        <button type="button" class="is-up" data-sim-step="0.20">+0.20</button>
      </div>

      <div class="rate-simulation-grid">
        <div class="rate-simulation-card">
          <span class="rate-simulation-label">당행 최고금리</span>
          <div class="rate-simulation-transition">
            <span data-sim-bank-from>-</span><span>→</span><b data-sim-bank-to>-</b>
            <span class="rate-simulation-pill" data-sim-bank-status>유지</span>
          </div>
        </div>
        <div class="rate-simulation-card">
          <span class="rate-simulation-label">시장 순위</span>
          <div class="rate-simulation-transition">
            <span data-sim-rank-from>-</span><span>→</span><b data-sim-rank-to>-</b>
            <span class="rate-simulation-pill" data-sim-rank-status>유지</span>
          </div>
        </div>
        <div class="rate-simulation-card">
          <span class="rate-simulation-label">시장 최고 대비</span>
          <div class="rate-simulation-transition"><span data-sim-top-from>-</span><span>→</span><b data-sim-top-to>-</b></div>
        </div>
        <div class="rate-simulation-card">
          <span class="rate-simulation-label">시장 평균 대비</span>
          <div class="rate-simulation-transition"><span data-sim-avg-from>-</span><span>→</span><b data-sim-avg-to>-</b></div>
        </div>
        <div class="rate-simulation-card">
          <span class="rate-simulation-label">최고금리 상품</span>
          <div class="rate-simulation-transition"><span data-sim-product-from>-</span><span>→</span><b data-sim-product-to>-</b></div>
        </div>
        <div class="rate-simulation-card">
          <span class="rate-simulation-label">금융지주계 순위</span>
          <div class="rate-simulation-transition"><span data-sim-fin-from>-</span><span>→</span><b data-sim-fin-to>-</b></div>
        </div>
      </div>

      <div class="rate-simulation-note" data-sim-note>
        선택한 상품만 가정 변경하며 시장순위는 은행별 최고금리 기준으로 계산합니다.
      </div>
      <div class="rate-simulation-zone" data-sim-zone></div>

      <div class="rate-simulation-grid">
        <div class="rate-simulation-card"><span class="rate-simulation-label">TOP10 경쟁선</span><b data-sim-top10>-</b></div>
        <div class="rate-simulation-card"><span class="rate-simulation-label">TOP5 경쟁선</span><b data-sim-top5>-</b></div>
      </div>

      <div class="rate-simulation-foot">
        <span data-sim-source></span>
        <span>※ 조회용이며 실제 금리 데이터는 변경되지 않습니다.</span>
      </div>`;
  }

  function createPc(){
    let layer=$('#rate-simulation-v3-layer');
    if(layer) return layer;
    layer=document.createElement('div');
    layer.id='rate-simulation-v3-layer';
    layer.innerHTML=`
      <section class="rate-simulation-panel" role="dialog" aria-label="우리금융 금리 시뮬레이션">
        <header class="rate-simulation-head">
          <div>
            <div class="rate-simulation-title">우리금융 금리 시뮬레이션</div>
            <div class="rate-simulation-basis" data-sim-basis>정기예금 · 12개월</div>
          </div>
          <div class="rate-simulation-head-actions">
            <span class="rate-simulation-progress" data-sim-progress></span>
            <button type="button" class="rate-simulation-head-btn" data-sim-min aria-label="최소화">−</button>
            <button type="button" class="rate-simulation-head-btn" data-sim-close aria-label="닫기">×</button>
          </div>
        </header>
        <div class="rate-simulation-body">${bodyMarkup()}</div>
      </section>`;
    document.body.appendChild(layer);

    const panel=$('.rate-simulation-panel',layer);
    const head=$('.rate-simulation-head',layer);
    head.addEventListener('pointerdown',event=>{
      if(event.target.closest('button,input,select')) return;
      const rect=panel.getBoundingClientRect();
      State.drag={id:event.pointerId,x:event.clientX-rect.left,y:event.clientY-rect.top};
      head.setPointerCapture?.(event.pointerId);
    });
    head.addEventListener('pointermove',event=>{
      if(!State.drag || State.drag.id!==event.pointerId) return;
      const left=Math.max(8,Math.min(innerWidth-panel.offsetWidth-8,event.clientX-State.drag.x));
      const top=Math.max(8,Math.min(innerHeight-panel.offsetHeight-8,event.clientY-State.drag.y));
      panel.style.left=`${left}px`;
      panel.style.top=`${top}px`;
    });
    head.addEventListener('pointerup',()=>State.drag=null);
    head.addEventListener('pointercancel',()=>State.drag=null);

    $('[data-sim-close]',layer).addEventListener('click',closeSimulation);
    $('[data-sim-min]',layer).addEventListener('click',event=>{
      panel.classList.toggle('is-minimized');
      event.currentTarget.textContent=panel.classList.contains('is-minimized')?'□':'−';
    });
    bindControls(layer);
    return layer;
  }

  function createMobile(){
    let layer=$('#rate-simulation-v3-mobile');
    if(layer) return layer;
    layer=document.createElement('div');
    layer.id='rate-simulation-v3-mobile';
    layer.innerHTML=`
      <section class="rate-simulation-sheet" role="dialog" aria-label="우리금융 금리 시뮬레이션">
        <div class="rate-simulation-handle" aria-hidden="true"></div>
        <header class="rate-simulation-head">
          <div>
            <div class="rate-simulation-title">우리금융 금리 시뮬레이션</div>
            <div class="rate-simulation-basis" data-sim-basis>정기예금 · 12개월</div>
          </div>
          <div class="rate-simulation-head-actions">
            <span class="rate-simulation-progress" data-sim-progress></span>
            <button type="button" class="rate-simulation-head-btn" data-sim-close aria-label="닫기">×</button>
          </div>
        </header>
        <div class="rate-simulation-body">${bodyMarkup()}</div>
      </section>`;
    document.body.appendChild(layer);
    $('[data-sim-close]',layer).addEventListener('click',closeSimulation);
    layer.addEventListener('click',event=>{if(event.target===layer) closeSimulation();});
    bindControls(layer);
    return layer;
  }

  function activeContainer(){
    return State.mobile ? createMobile() : createPc();
  }

  function bindControls(root){
    $('[data-sim-period]',root).addEventListener('change',()=>loadSimulation(null,null));
    $('[data-sim-product]',root).addEventListener('change',event=>loadSimulation(null,event.target.value));

    const input=$('[data-sim-target]',root);
    input.addEventListener('input',()=>{
      clearTimeout(State.inputTimer);
      State.inputTimer=setTimeout(()=>{
        const value=Number(input.value);
        if(Number.isFinite(value)&&value>0){
          loadSimulation(value,$('[data-sim-product]',root).value);
        }
      },350);
    });
    input.addEventListener('keydown',event=>{
      if(event.key==='Enter'){
        event.preventDefault();
        const value=Number(input.value);
        if(Number.isFinite(value)&&value>0){
          loadSimulation(value,$('[data-sim-product]',root).value);
        }
      }
    });

    $$('[data-sim-step]',root).forEach(button=>{
      button.addEventListener('click',()=>{
        const base=Number(State.data?.selected_product_current_rate||0);
        loadSimulation(Math.max(.01,base+Number(button.dataset.simStep||0)),$('[data-sim-product]',root).value);
      });
    });
    $('[data-sim-current]',root).addEventListener('click',()=>{
      const base=Number(State.data?.selected_product_current_rate||0);
      loadSimulation(base,$('[data-sim-product]',root).value);
    });
  }

  function setBusy(on){
    const root=activeContainer();
    $('[data-sim-progress]',root).textContent=on?'계산중…':'';
    $$('select,[data-sim-step],[data-sim-current]',root).forEach(control=>control.disabled=on);
  }

  function optionHtml(items,getValue,getLabel){
    return items.map(item=>{
      const value=String(getValue(item)??'').replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;');
      return `<option value="${value}">${getLabel(item)}</option>`;
    }).join('');
  }

  function syncSelect(select,items,value,getValue,getLabel){
    const html=optionHtml(items,getValue,getLabel);
    if(select.innerHTML!==html) select.innerHTML=html;
    select.value=String(value??'');
  }

  function render(data){
    const root=activeContainer();
    if(!data?.ok){
      $('[data-sim-note]',root).textContent=data?.message||'시뮬레이션 데이터를 확인할 수 없습니다.';
      return;
    }

    State.data=data;
    const current=data.current||{};
    const simulated=data.simulated||{};
    const bankBest=data.bank_best||{};
    const thresholds=data.thresholds||{};

    $('[data-sim-basis]',root).textContent=`${data.category_label} · ${data.period}개월`;
    syncSelect(
      $('[data-sim-period]',root),
      (data.period_options||[]).map(value=>({value})),
      data.period,
      item=>item.value,
      item=>`${item.value}개월`
    );
    syncSelect(
      $('[data-sim-product]',root),
      data.product_options||[],
      data.selected_product,
      item=>item.name,
      item=>`${item.name} · ${rate(item.rate)}`
    );

    $('[data-sim-selected-current]',root).textContent=rate(data.selected_product_current_rate);
    const target=$('[data-sim-target]',root);
    if(document.activeElement!==target){
      target.value=Number(data.target_rate).toFixed(2);
    }
    $('[data-sim-delta]',root).innerHTML=change(Number(data.target_rate)-Number(data.selected_product_current_rate));

    $('[data-sim-bank-from]',root).textContent=rate(bankBest.current_rate);
    $('[data-sim-bank-to]',root).textContent=rate(bankBest.simulated_rate);
    const bankState=rateStatus(bankBest.current_rate,bankBest.simulated_rate);
    const bankPill=$('[data-sim-bank-status]',root);
    bankPill.textContent=bankState.text;
    bankPill.className=`rate-simulation-pill ${bankState.cls}`.trim();

    $('[data-sim-rank-from]',root).textContent=current.rank?`${current.rank}위`:'-';
    $('[data-sim-rank-to]',root).textContent=simulated.rank?`${simulated.rank}위`:'-';
    const rankState=rankStatus(current.rank,simulated.rank);
    const rankPill=$('[data-sim-rank-status]',root);
    rankPill.textContent=rankState.text;
    rankPill.className=`rate-simulation-pill ${rankState.cls}`.trim();

    $('[data-sim-top-from]',root).innerHTML=change(current.gap_top);
    $('[data-sim-top-to]',root).innerHTML=change(simulated.gap_top);
    $('[data-sim-avg-from]',root).innerHTML=change(current.gap_average);
    $('[data-sim-avg-to]',root).innerHTML=change(simulated.gap_average);
    $('[data-sim-product-from]',root).textContent=bankBest.current_product||'-';
    $('[data-sim-product-to]',root).textContent=bankBest.simulated_product||'-';
    $('[data-sim-fin-from]',root).textContent=current.financial_rank?`${current.financial_rank}위`:'-';
    $('[data-sim-fin-to]',root).textContent=simulated.financial_rank?`${simulated.financial_rank}위`:'-';

    $('[data-sim-note]',root).textContent=bankBest.product_changed
      ? `${data.selected_product} 조정으로 당행 최고금리 상품이 ${bankBest.current_product} → ${bankBest.simulated_product}로 변경됩니다.`
      : `${bankBest.simulated_product} ${rate(bankBest.simulated_rate)}가 당행 최고금리입니다. 선택상품을 조정해도 시장순위는 은행별 최고금리 기준으로 계산합니다.`;

    const zone=[];
    if(simulated.above){
      zone.push(`<div class="rate-simulation-neighbor"><span>바로 위 · ${shortBank(simulated.above.bank)}</span><b>${rate(simulated.above.rate)}</b></div>`);
    }
    zone.push(`<div class="rate-simulation-neighbor is-woori"><span>우리금융 · ${bankBest.simulated_product||data.selected_product}</span><b>${rate(bankBest.simulated_rate)}</b></div>`);
    if(simulated.below){
      zone.push(`<div class="rate-simulation-neighbor"><span>바로 아래 · ${shortBank(simulated.below.bank)}</span><b>${rate(simulated.below.rate)}</b></div>`);
    }
    $('[data-sim-zone]',root).innerHTML=zone.join('');

    $('[data-sim-top10]',root).textContent=thresholds.top10!=null?rate(thresholds.top10):'-';
    $('[data-sim-top5]',root).textContent=thresholds.top5!=null?rate(thresholds.top5):'-';
    $('[data-sim-source]',root).textContent=`[출처 : ${data.source||'-'}]`;
  }

  async function loadSimulation(targetRate,product){
    const root=activeContainer();
    const period=$('[data-sim-period]',root).value || mainPeriod();
    const requestId=++State.requestId;
    setBusy(true);

    try{
      const response=await fetch('/api/rate-simulation-v2',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        cache:'no-store',
        body:JSON.stringify({
          category:category(),
          period,
          target_rate:targetRate==null?null:Number(targetRate),
          product:product||null
        })
      });
      const data=await response.json();
      if(requestId!==State.requestId) return;
      render(data);
    }catch(error){
      console.error('RATE SIMULATION V3 ERROR',error);
      if(requestId===State.requestId){
        $('[data-sim-note]',root).textContent='시뮬레이션 데이터를 불러오지 못했습니다.';
      }
    }finally{
      if(requestId===State.requestId) setBusy(false);
    }
  }

  function openSimulation(){
    State.mobile=isMobilePage();
    State.open=true;
    const root=activeContainer();
    root.classList.add('is-open');

    if(!State.mobile){
      const panel=$('.rate-simulation-panel',root);
      panel.classList.remove('is-minimized');
      const min=$('[data-sim-min]',root);
      if(min) min.textContent='−';
      if(!panel.dataset.positioned){
        const width=Math.min(560,innerWidth-30);
        panel.style.left=`${Math.max(16,(innerWidth-width)/2)}px`;
        panel.style.top=`${Math.max(70,Math.min(120,innerHeight*.13))}px`;
        panel.dataset.positioned='1';
      }
    }

    const periodSelect=$('[data-sim-period]',root);
    periodSelect.innerHTML=`<option value="${mainPeriod()}">${mainPeriod()}개월</option>`;
    periodSelect.value=mainPeriod();
    loadSimulation(null,null);
  }

  function closeSimulation(){
    State.open=false;
    $('#rate-simulation-v3-layer')?.classList.remove('is-open');
    $('#rate-simulation-v3-mobile')?.classList.remove('is-open');
  }

  function installPcButton(){
    if($('#rate-simulation-open-pc')) return;
    const card=$('#dashboard-hero-start > .col-span-4:first-child > .bg-white');
    const header=card?.querySelector(':scope > .flex.items-center.justify-between.mb-4');
    if(!header) return;

    const button=document.createElement('button');
    button.id='rate-simulation-open-pc';
    button.type='button';
    button.className='rate-simulation-open';
    button.textContent='📈 금리 시뮬레이션';
    button.addEventListener('click',openSimulation);

    const slot=header.children[1];
    if(slot){slot.textContent='';slot.appendChild(button);}else{header.appendChild(button);}
  }

  function updateMobileSource(){
    const source=$('#mobile-simulation-source');
    if(!source) return;
    source.textContent=category()==='deposit'
      ? '[출처 : 저축은행중앙회 비교공시]'
      : '[출처 : 각 저축은행 홈페이지]';
  }

  function installMobileButton(){
    const button=$('#rate-simulation-open-mobile');
    if(button && !button.dataset.bound){
      button.dataset.bound='1';
      button.addEventListener('click',openSimulation);
    }
    updateMobileSource();
  }

  function removeLegacy(){
    $$('#rate-sim-open-pc,#rate-sim-open-mobile,#rate-sim-v2-open-pc,#rate-sim-v2-open-mobile,.sb2-mobile-row').forEach(node=>node.remove());
  }

  function watchContext(){
    document.addEventListener('click',event=>{
      if(event.target.closest('[data-market-product],#mobile-product-tabs .product-tab')){
        setTimeout(()=>{
          updateMobileSource();
          if(State.open){
            const root=activeContainer();
            const periodSelect=$('[data-sim-period]',root);
            periodSelect.innerHTML=`<option value="${mainPeriod()}">${mainPeriod()}개월</option>`;
            periodSelect.value=mainPeriod();
            loadSimulation(null,null);
          }
        },100);
      }
    },true);
  }

  function init(){
    State.mobile=isMobilePage();
    removeLegacy();
    State.mobile?installMobileButton():installPcButton();
    setTimeout(removeLegacy,120);
    watchContext();
    window.openSBRateSimulation=openSimulation;
  }

  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded',init,{once:true});
  }else{
    init();
  }
})();
