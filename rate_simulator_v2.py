# SBRate Rate Simulation V2 extension
# Keeps V1 Telegram routing, adds stable product/period-aware PC/mobile UI.
import sys, threading, time
from copy import deepcopy


def _appmod():
    for name in ('app','__main__'):
        m=sys.modules.get(name)
        if m is not None and hasattr(m,'app'):
            return m
    return None


def _num(m,v):
    f=getattr(m,'safe_float',None)
    if callable(f):
        try:return f(v)
        except Exception:pass
    try:return float(str(v).replace(',','').replace('%','').strip())
    except Exception:return None


def _norm(m,v):
    f=getattr(m,'normalize',None)
    if callable(f):
        try:return str(f(v) or '')
        except Exception:pass
    return str(v or '').replace('(주)','').replace('㈜','').replace('주식회사','').replace('저축은행','').replace(' ','').lower()


def _woori(m,v):
    return '우리금융' in str(v or '') or _norm(m,v)==_norm(m,'우리금융저축은행')


def _period(category, period):
    p=str(period or '12').strip()
    allow=('1','3','6','12','24','36') if category=='deposit' else ('3','6','12','24','36')
    return p if p in allow else '12'


def _label(c):
    return {'deposit':'정기예금','isa':'ISA','irp':'퇴직연금(IRP)'}.get(c,'정기예금')


def _source(c):
    return '저축은행중앙회 비교공시' if c=='deposit' else '각 저축은행 홈페이지'


def _rows(m,c,p):
    p=_period(c,p)
    if c=='deposit':
        f=getattr(m,'build_products',None)
        if not callable(f):return []
        rows=f(f'{p}개월') or []
        u=getattr(m,'unique_products',None)
        if callable(u):
            try:rows=u(rows) or rows
            except Exception:pass
    else:
        path=getattr(m,'ISA_DATA_FILE' if c=='isa' else 'IRP_DATA_FILE','')
        f=getattr(m,'build_pension_products',None)
        if not callable(f) or not path:return []
        rows=f(path,'ISA' if c=='isa' else '퇴직연금') or []
        pf=getattr(m,'pension_items_with_period',None)
        if callable(pf):
            try:rows=pf(rows,p) or []
            except Exception:rows=[]
        else:
            key=p+'m'; out=[]
            for r in rows:
                x=dict(r); x['rate']=(x.get('rates') or {}).get(key); out.append(x)
            rows=out
    out=[]
    for r in rows:
        if not isinstance(r,dict):continue
        bank=str(r.get('bank') or r.get('bank_name') or r.get('kor_co_nm') or '').strip()
        product=str(r.get('product') or r.get('product_name') or r.get('fin_prdt_nm') or '').strip()
        rate=_num(m,r.get('rate') if r.get('rate') not in (None,'') else (r.get('max_rate') if r.get('max_rate') not in (None,'') else r.get('intr_rate2')))
        if bank and rate is not None and rate>0:
            out.append({'bank':bank,'product':product or '-', 'rate':float(rate),'disclosure_date':r.get('disclosure_date')})
    return out


def _bank_best(m,rows):
    best={}; order=[]
    for r in rows:
        k=_norm(m,r['bank'])
        if not k:continue
        if k not in best:
            order.append(k); best[k]=deepcopy(r)
        elif r['rate']>best[k]['rate']:
            best[k]=deepcopy(r)
    return sorted([best[k] for k in order],key=lambda x:x['rate'],reverse=True)


def _snapshot(m,rows):
    ranked=_bank_best(m,rows)
    wi=next((i for i,r in enumerate(ranked) if _woori(m,r['bank'])),None)
    if wi is None:return None
    w=ranked[wi]; rates=[r['rate'] for r in ranked]
    avg=sum(rates)/len(rates); top=max(rates)
    fin=getattr(__import__('rate_simulator'),'_financial_group_rank',None)
    fr={'rank':None,'total':0}
    if callable(fin):
        try:fr=fin(m,ranked) or fr
        except Exception:pass
    return {'rate':w['rate'],'rank':wi+1,'total':len(ranked),'top_rate':top,'average_rate':avg,
            'gap_top':w['rate']-top,'gap_average':w['rate']-avg,'financial_rank':fr.get('rank'),
            'financial_total':fr.get('total'),'product':w.get('product') or '-',
            'above':deepcopy(ranked[wi-1]) if wi>0 else None,
            'below':deepcopy(ranked[wi+1]) if wi+1<len(ranked) else None}


def _products(m,rows):
    d={}; order=[]
    for r in rows:
        if not _woori(m,r['bank']):continue
        name=r.get('product') or '-'
        if name not in d:order.append(name);d[name]=r['rate']
        elif r['rate']>d[name]:d[name]=r['rate']
    return [{'name':n,'rate':d[n]} for n in order]


def simulate(m,category='deposit',period='12',target_rate=None,product=None):
    c=str(category or 'deposit').lower(); c=c if c in ('deposit','isa','irp') else 'deposit'; p=_period(c,period)
    rows=_rows(m,c,p); current=_snapshot(m,rows); opts=_products(m,rows)
    if not current or not opts:return {'ok':False,'message':'우리금융 금리 데이터를 확인할 수 없습니다.'}
    names=[x['name'] for x in opts]
    selected=product if product in names else current['product'] if current['product'] in names else names[0]
    selected_rate=next(x['rate'] for x in opts if x['name']==selected)
    try:target=float(target_rate) if target_rate not in (None,'') else selected_rate
    except Exception:target=selected_rate
    target=round(max(.01,min(10,target)),2)
    sim=deepcopy(rows)
    for r in sim:
        if _woori(m,r['bank']) and r.get('product')==selected:r['rate']=target
    after=_snapshot(m,sim)
    if not after:return {'ok':False,'message':'시뮬레이션 결과를 계산하지 못했습니다.'}
    comp=[r for r in _bank_best(m,rows) if not _woori(m,r['bank'])]
    def cut(n):return comp[n-1]['rate'] if len(comp)>=n else None
    return {'ok':True,'category':c,'category_label':_label(c),'period':p,'period_options':['1','3','6','12','24','36'] if c=='deposit' else ['3','6','12','24','36'],
            'source':_source(c),'product_options':opts,'selected_product':selected,'selected_product_current_rate':selected_rate,
            'current':current,'simulated':after,'target_rate':target,
            'bank_best':{'current_rate':current['rate'],'simulated_rate':after['rate'],'current_product':current['product'],'simulated_product':after['product'],'product_changed':current['product']!=after['product']},
            'thresholds':{'top5':cut(5),'top10':cut(10)}}

INLINE_CSS=r'''
#rate-sim-open-pc,#rate-sim-open-mobile{display:none!important}.app-shell .data-meta-left::after{display:none!important;content:""!important}
.sb2-open{border:1px solid #b9d4f8;background:#f5f9ff;color:#1556c0;border-radius:10px;padding:6px 9px;font-size:10px;font-weight:800;white-space:nowrap}.sb2-mobile-row{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-top:5px;color:#8a96a7;font-size:7.7px}.sb2-mobile-row .sb2-open{padding:5px 8px;border-radius:999px;font-size:8.5px;background:#fff}
.sb2-layer{display:none;position:fixed;inset:0;z-index:180;pointer-events:none}.sb2-layer.open{display:block}.sb2-panel{position:fixed;width:min(540px,calc(100vw - 30px));max-height:calc(100vh - 30px);overflow:hidden;background:#fff;border:1px solid #dbe5f2;border-radius:18px;box-shadow:0 24px 70px rgba(22,35,60,.22);pointer-events:auto;color:#172033}.sb2-panel.min .sb2-body{display:none}.sb2-panel.min{width:330px}.sb2-head{display:flex;align-items:center;justify-content:space-between;padding:12px 14px;border-bottom:1px solid #e5ebf3;background:linear-gradient(90deg,#f8fbff,#fff);cursor:move;user-select:none;touch-action:none}.sb2-title{font-size:14px;font-weight:850}.sb2-basis{font-size:9px;color:#8793a5;margin-top:2px}.sb2-actions{display:flex;gap:5px}.sb2-actions button{width:29px;height:29px;border:1px solid #e5ebf3;border-radius:9px;background:#fff;color:#677489;font-size:16px}.sb2-body{max-height:calc(100vh - 96px);overflow:auto;padding:14px}.sb2-busy{font-size:8px;color:#8793a5;min-width:38px;text-align:right}.sb2-controls{display:grid;grid-template-columns:110px 1fr;gap:8px;margin-bottom:10px}.sb2-field{border:1px solid #e5ebf3;border-radius:12px;background:#fafcff;padding:7px 9px}.sb2-field label{display:block;font-size:8px;color:#8995a6;margin-bottom:4px}.sb2-field select{width:100%;border:0;background:transparent;outline:0;color:#344054;font-size:10px;font-weight:750}.sb2-rate{display:grid;grid-template-columns:1fr 24px 1fr;align-items:end;gap:8px}.sb2-ratebox{border:1px solid #e7edf5;border-radius:14px;padding:10px 11px;background:#fbfcfe}.sb2-ratebox.target{background:#f5f9ff;border-color:#b9d4f8}.sb2-label{display:block;font-size:8.5px;color:#8792a3;margin-bottom:5px}.sb2-big{font-size:24px;font-weight:850;letter-spacing:-.04em}.sb2-target{display:flex;align-items:center}.sb2-target input{width:100%;min-width:0;border:0;background:transparent;outline:0;color:#1556c0;font-size:24px;font-weight:850}.sb2-arrow{text-align:center;color:#738198;font-size:18px}.sb2-delta{margin-top:7px;font-size:9px;font-weight:800}.up{color:#1556c0!important}.down{color:#e15151!important}.flat{color:#6f7b8c!important}.sb2-presets{display:grid;grid-template-columns:repeat(6,1fr);gap:5px;margin-top:8px}.sb2-presets button{min-height:30px;border:1px solid #e2e8f1;border-radius:9px;background:#f8fafc;font-size:8.5px;font-weight:800}.sb2-presets .u{color:#1556c0;background:#f2f7ff}.sb2-presets .d{color:#e15151;background:#fff7f7}.sb2-grid{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-top:11px}.sb2-card{border:1px solid #e8edf4;border-radius:12px;padding:9px;background:#fff}.sb2-transition{display:flex;align-items:center;gap:5px;flex-wrap:wrap;font-size:10px}.sb2-transition b{color:#1f2d44}.sb2-pill{border-radius:999px;padding:3px 6px;font-size:7.5px;font-weight:800;background:#f1f3f6;color:#667387}.sb2-pill.good{background:#edf5ff;color:#1556c0}.sb2-pill.bad{background:#fff1f1;color:#d94c4c}.sb2-note{margin-top:9px;padding:8px 10px;border:1px solid #dce9fb;border-radius:11px;background:#f7fbff;font-size:9px;line-height:1.45;color:#526174}.sb2-zone{margin-top:9px;border:1px solid #dce9fb;border-radius:12px;background:#f7fbff;padding:9px}.sb2-neighbor{display:flex;justify-content:space-between;gap:8px;padding:5px 2px;border-top:1px solid #e5eefb;font-size:9px}.sb2-neighbor:first-child{border-top:0}.sb2-neighbor.woori{margin:3px -2px;padding:6px;border:1px solid #9fc6fb;border-radius:8px;background:#eaf3ff;color:#1556c0;font-weight:800}.sb2-foot{display:flex;justify-content:space-between;gap:8px;margin-top:10px;padding-top:9px;border-top:1px solid #edf1f6;color:#8b96a6;font-size:8px}.sb2-mobile{display:none;position:fixed;inset:0;z-index:190;background:rgba(12,20,35,.42);align-items:flex-end;justify-content:center}.sb2-mobile.open{display:flex}.sb2-sheet{width:min(720px,100%);max-height:86vh;overflow:hidden;background:#fff;border-radius:22px 22px 0 0;box-shadow:0 -18px 55px rgba(20,32,53,.24)}.sb2-sheet .sb2-head{cursor:default}.sb2-sheet .sb2-body{max-height:calc(86vh - 58px);padding-bottom:calc(18px + env(safe-area-inset-bottom))}
@media(max-width:640px){.sb2-controls{grid-template-columns:92px 1fr}.sb2-presets{grid-template-columns:repeat(3,1fr)}.sb2-grid{grid-template-columns:1fr 1fr}.sb2-big,.sb2-target input{font-size:22px}.sb2-foot{flex-direction:column}.sb2-body{padding:12px}}@media(max-width:380px){.sb2-mobile-row{font-size:7px}.sb2-mobile-row .sb2-open{font-size:8px;padding:5px 7px}.sb2-grid{grid-template-columns:1fr}}
'''

INLINE_JS=r'''
(()=>{'use strict';const S={mobile:false,open:false,data:null,req:0,timer:null,drag:null};const $=(s,r=document)=>r.querySelector(s);const mobile=()=>location.pathname==='/mobile'||!!$('.app-shell');
const cat=()=>mobile()?($('#mobile-product-tabs .product-tab.is-active')?.dataset.product||'deposit'):([...document.querySelectorAll('[data-market-product]')].find(x=>x.classList.contains('text-white'))?.dataset.marketProduct||'deposit');
const mainPeriod=()=>{let p=mobile()?($('#hero-product-label')?.textContent.match(/(1|3|6|12|24|36)개월/)?.[1]||'12'):($('#product-period-select')?.value||'12');return cat()!=='deposit'&&p==='1'?'12':p};
const rate=v=>Number.isFinite(Number(v))?Number(v).toFixed(2)+'%':'-';const ch=v=>{v=Number(v);return !Number.isFinite(v)||Math.abs(v)<1e-6?'<span class="flat">-</span>':v>0?`<span class="up">+${Math.abs(v).toFixed(2)}%p</span>`:`<span class="down">▲${Math.abs(v).toFixed(2)}%p</span>`};
const short=n=>String(n||'-').replace(/저축은행/g,'').trim();const status=(a,b)=>{a=Number(a);b=Number(b);if(a>b)return ['개선','good'];if(a<b)return ['악화','bad'];return ['유지','']};
function shell(){return `<div class="sb2-controls"><div class="sb2-field"><label>기간</label><select data-period></select></div><div class="sb2-field"><label>우리금융 상품</label><select data-product></select></div></div><div class="sb2-rate"><div class="sb2-ratebox"><span class="sb2-label">선택상품 현재금리</span><div class="sb2-big" data-selected-current>-</div></div><div class="sb2-arrow">→</div><div class="sb2-ratebox target"><span class="sb2-label">시뮬레이션 금리</span><div class="sb2-target"><input data-target type="number" min="0.01" max="10" step="0.01"><b>%</b></div></div></div><div class="sb2-delta">금리변화 <span data-delta>-</span></div><div class="sb2-presets"><button class="d" data-delta-btn="-.10">▲0.10</button><button class="d" data-delta-btn="-.05">▲0.05</button><button data-current>현재</button><button class="u" data-delta-btn=".05">+0.05</button><button class="u" data-delta-btn=".10">+0.10</button><button class="u" data-delta-btn=".20">+0.20</button></div><div class="sb2-grid"><div class="sb2-card"><span class="sb2-label">당행 최고금리</span><div class="sb2-transition"><span data-bank-from>-</span>→<b data-bank-to>-</b><span class="sb2-pill" data-bank-status>유지</span></div></div><div class="sb2-card"><span class="sb2-label">시장 순위</span><div class="sb2-transition"><span data-rank-from>-</span>→<b data-rank-to>-</b><span class="sb2-pill" data-rank-status>유지</span></div></div><div class="sb2-card"><span class="sb2-label">시장 최고 대비</span><div class="sb2-transition"><span data-top-from>-</span>→<b data-top-to>-</b></div></div><div class="sb2-card"><span class="sb2-label">시장 평균 대비</span><div class="sb2-transition"><span data-avg-from>-</span>→<b data-avg-to>-</b></div></div><div class="sb2-card"><span class="sb2-label">최고금리 상품</span><div class="sb2-transition"><span data-prod-from>-</span>→<b data-prod-to>-</b></div></div><div class="sb2-card"><span class="sb2-label">금융지주계 순위</span><div class="sb2-transition"><span data-fin-from>-</span>→<b data-fin-to>-</b></div></div></div><div class="sb2-note" data-note>선택한 상품만 가정 변경하며 시장순위는 은행별 최고금리 기준으로 계산합니다.</div><div class="sb2-zone" data-zone></div><div class="sb2-grid"><div class="sb2-card"><span class="sb2-label">TOP10 경쟁선</span><b data-top10>-</b></div><div class="sb2-card"><span class="sb2-label">TOP5 경쟁선</span><b data-top5>-</b></div></div><div class="sb2-foot"><span data-source></span><span>※ 조회용이며 실제 금리 데이터는 변경되지 않습니다.</span></div>`}
function container(){return S.mobile?createMobile():createPC()}function createPC(){let l=$('#sb2-layer');if(l)return l;l=document.createElement('div');l.id='sb2-layer';l.className='sb2-layer';l.innerHTML=`<section class="sb2-panel"><header class="sb2-head"><div><div class="sb2-title">우리금융 금리 시뮬레이션</div><div class="sb2-basis" data-basis>정기예금 · 12개월</div></div><div class="sb2-actions"><span class="sb2-busy" data-busy></span><button data-min>−</button><button data-close>×</button></div></header><div class="sb2-body">${shell()}</div></section>`;document.body.append(l);let p=$('.sb2-panel',l),h=$('.sb2-head',l);h.onpointerdown=e=>{if(e.target.closest('button'))return;let r=p.getBoundingClientRect();S.drag={id:e.pointerId,x:e.clientX-r.left,y:e.clientY-r.top};h.setPointerCapture?.(e.pointerId)};h.onpointermove=e=>{if(!S.drag||S.drag.id!==e.pointerId)return;p.style.left=Math.max(8,Math.min(innerWidth-p.offsetWidth-8,e.clientX-S.drag.x))+'px';p.style.top=Math.max(8,Math.min(innerHeight-p.offsetHeight-8,e.clientY-S.drag.y))+'px'};h.onpointerup=()=>S.drag=null;$('[data-close]',l).onclick=close;$('[data-min]',l).onclick=e=>{p.classList.toggle('min');e.currentTarget.textContent=p.classList.contains('min')?'□':'−'};bind(l);return l}
function createMobile(){let l=$('#sb2-mobile');if(l)return l;l=document.createElement('div');l.id='sb2-mobile';l.className='sb2-mobile';l.innerHTML=`<section class="sb2-sheet"><header class="sb2-head"><div><div class="sb2-title">우리금융 금리 시뮬레이션</div><div class="sb2-basis" data-basis>정기예금 · 12개월</div></div><div class="sb2-actions"><span class="sb2-busy" data-busy></span><button data-close>×</button></div></header><div class="sb2-body">${shell()}</div></section>`;document.body.append(l);$('[data-close]',l).onclick=close;l.onclick=e=>{if(e.target===l)close()};bind(l);return l}
function bind(l){$('[data-period]',l).onchange=()=>load(null,null);$('[data-product]',l).onchange=e=>load(null,e.target.value);let inp=$('[data-target]',l);inp.oninput=()=>{clearTimeout(S.timer);S.timer=setTimeout(()=>{let n=Number(inp.value);if(n>0)load(n,$('[data-product]',l).value)},320)};inp.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();let n=Number(inp.value);if(n>0)load(n,$('[data-product]',l).value)}};l.querySelectorAll('[data-delta-btn]').forEach(b=>b.onclick=()=>{let base=Number(S.data?.selected_product_current_rate||0);load(base+Number(b.dataset.deltaBtn),$('[data-product]',l).value)});$('[data-current]',l).onclick=()=>load(Number(S.data?.selected_product_current_rate||0),$('[data-product]',l).value)}
function busy(on){let l=container();$('[data-busy]',l).textContent=on?'계산중…':'';l.querySelectorAll('select,button[data-delta-btn],[data-current]').forEach(x=>x.disabled=on)}
async function load(target,product){let l=container(),period=$('[data-period]',l).value||mainPeriod(),id=++S.req;busy(true);try{let r=await fetch('/api/rate-simulation-v2',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({category:cat(),period,target_rate:target,product})});let d=await r.json();if(id!==S.req)return;S.data=d;render(d)}catch(e){console.error('RATE SIM V2',e);$('[data-busy]',l).textContent='오류'}finally{if(id===S.req)busy(false)}}
function opts(sel,items,value,fmt){let html=items.map(x=>`<option value="${String(x.value).replace(/"/g,'&quot;')}">${fmt(x)}</option>`).join('');if(sel.innerHTML!==html)sel.innerHTML=html;sel.value=value}
function render(d){let l=container();if(!d?.ok){$('[data-note]',l).textContent=d?.message||'데이터를 확인할 수 없습니다.';return}let c=d.current||{},s=d.simulated||{},bb=d.bank_best||{},th=d.thresholds||{};$('[data-basis]',l).textContent=`${d.category_label} · ${d.period}개월`;opts($('[data-period]',l),(d.period_options||[]).map(x=>({value:x})),d.period,x=>x.value+'개월');opts($('[data-product]',l),(d.product_options||[]).map(x=>({value:x.name,rate:x.rate})),d.selected_product,x=>`${x.value} · ${rate(x.rate)}`);$('[data-selected-current]',l).textContent=rate(d.selected_product_current_rate);$('[data-target]',l).value=Number(d.target_rate).toFixed(2);$('[data-delta]',l).innerHTML=ch(Number(d.target_rate)-Number(d.selected_product_current_rate));$('[data-bank-from]',l).textContent=rate(bb.current_rate);$('[data-bank-to]',l).textContent=rate(bb.simulated_rate);let bs=status(bb.current_rate,bb.simulated_rate),bp=$('[data-bank-status]',l);bp.textContent=bs[0];bp.className='sb2-pill '+bs[1];$('[data-rank-from]',l).textContent=c.rank+'위';$('[data-rank-to]',l).textContent=s.rank+'위';let rs=status(c.rank,s.rank),rp=$('[data-rank-status]',l);rp.textContent=rs[0];rp.className='sb2-pill '+rs[1];$('[data-top-from]',l).innerHTML=ch(c.gap_top);$('[data-top-to]',l).innerHTML=ch(s.gap_top);$('[data-avg-from]',l).innerHTML=ch(c.gap_average);$('[data-avg-to]',l).innerHTML=ch(s.gap_average);$('[data-prod-from]',l).textContent=bb.current_product||'-';$('[data-prod-to]',l).textContent=bb.simulated_product||'-';$('[data-fin-from]',l).textContent=c.financial_rank?c.financial_rank+'위':'-';$('[data-fin-to]',l).textContent=s.financial_rank?s.financial_rank+'위':'-';$('[data-note]',l).textContent=bb.product_changed?`${d.selected_product} 조정으로 당행 최고금리 상품이 ${bb.current_product} → ${bb.simulated_product}로 변경됩니다.`:`${bb.simulated_product} ${rate(bb.simulated_rate)}가 당행 최고금리입니다. 선택상품 조정 후에도 시장순위는 은행별 최고금리 기준으로 계산합니다.`;let z=[];if(s.above)z.push(`<div class="sb2-neighbor"><span>바로 위 · ${short(s.above.bank)}</span><b>${rate(s.above.rate)}</b></div>`);z.push(`<div class="sb2-neighbor woori"><span>우리금융 · ${bb.simulated_product||d.selected_product}</span><b>${rate(bb.simulated_rate)}</b></div>`);if(s.below)z.push(`<div class="sb2-neighbor"><span>바로 아래 · ${short(s.below.bank)}</span><b>${rate(s.below.rate)}</b></div>`);$('[data-zone]',l).innerHTML=z.join('');$('[data-top10]',l).textContent=th.top10!=null?rate(th.top10):'-';$('[data-top5]',l).textContent=th.top5!=null?rate(th.top5):'-';$('[data-source]',l).textContent=`[출처 : ${d.source}]`}
function open(){S.mobile=mobile();S.open=true;let l=container();l.classList.add('open');if(!S.mobile){let p=$('.sb2-panel',l);if(!p.dataset.pos){p.style.left=Math.max(16,(innerWidth-Math.min(540,innerWidth-30))/2)+'px';p.style.top=Math.max(70,Math.min(120,innerHeight*.13))+'px';p.dataset.pos=1}}let ps=$('[data-period]',l);if(!ps.value)ps.innerHTML=`<option value="${mainPeriod()}">${mainPeriod()}개월</option>`;load(null,null)}function close(){S.open=false;$('#sb2-layer')?.classList.remove('open');$('#sb2-mobile')?.classList.remove('open')}
function pcButton(){if($('#rate-sim-v2-open-pc'))return;let card=$('#dashboard-hero-start > .col-span-4:first-child > .bg-white'),h=card?.querySelector(':scope > .flex.items-center.justify-between.mb-4');if(!h)return;let b=document.createElement('button');b.id='rate-sim-v2-open-pc';b.className='sb2-open';b.textContent='📈 금리 시뮬레이션';b.onclick=open;let slot=h.children[1];if(slot){slot.textContent='';slot.append(b)}else h.append(b)}
function mobileButton(){if($('#rate-sim-v2-open-mobile'))return;let meta=$('.data-meta');if(!meta)return;let row=document.createElement('div');row.className='sb2-mobile-row';row.innerHTML=`<span data-msource></span><button id="rate-sim-v2-open-mobile" class="sb2-open">📈 금리 시뮬레이션</button>`;meta.insertAdjacentElement('afterend',row);$('#rate-sim-v2-open-mobile').onclick=open;sourceText()}
function sourceText(){let e=$('[data-msource]');if(!e)return;e.textContent=cat()==='deposit'?'[출처 : 저축은행중앙회 비교공시]':'[출처 : 각 저축은행 홈페이지]'}
function init(){S.mobile=mobile();setTimeout(()=>{document.querySelectorAll('#rate-sim-open-pc,#rate-sim-open-mobile').forEach(x=>x.remove());S.mobile?mobileButton():pcButton()},30);document.addEventListener('click',e=>{if(e.target.closest('[data-market-product],#mobile-product-tabs .product-tab'))setTimeout(()=>{sourceText();if(S.open)load(null,null)},100)},true);window.openSBRateSimulation=open}
document.readyState==='loading'?document.addEventListener('DOMContentLoaded',init,{once:true}):init()})();
'''


def _rename_telegram(m):
    send=getattr(m,'telegram_send_message',None)
    if callable(send) and not getattr(m,'_sim_v2_send_wrapped',False):
        def wrapped(chat_id,text,*a,**kw):return send(chat_id,str(text or '').replace('금리 시뮬레이터','금리 시뮬레이션'),*a,**kw)
        m.telegram_send_message=wrapped;m._sim_v2_send_wrapped=True
    menu=getattr(m,'telegram_main_menu',None)
    if callable(menu) and not getattr(m,'_sim_v2_menu_wrapped',False):
        def mw():
            x=menu() or {}
            for row in x.get('inline_keyboard',[]):
                for b in row:
                    if isinstance(b,dict) and 'text' in b:b['text']=str(b['text']).replace('시뮬레이터','시뮬레이션')
            return x
        m.telegram_main_menu=mw;m._sim_v2_menu_wrapped=True
    def worker():
        time.sleep(6); api=getattr(m,'telegram_api',None)
        if callable(api):
            try:api('setMyCommands',{'commands':[{'command':'start','description':'SBRate 메인 메뉴'},{'command':'brief','description':'오늘의 시장 브리핑'},{'command':'simulate','description':'우리금융 금리 시뮬레이션'},{'command':'report','description':'PC·모바일 대시보드'},{'command':'help','description':'사용방법'}]})
            except Exception as e:print('Simulation V2 Telegram commands:',e)
    threading.Thread(target=worker,daemon=True).start()


def install_rate_simulator_v2():
    m=_appmod()
    if not m:return False
    app=m.app
    if getattr(m,'_rate_simulator_v2_installed',False):return True
    from flask import request, jsonify
    if 'rate_simulation_v2_api' not in app.view_functions:
        def endpoint():
            q=request.get_json(silent=True) or {} if request.method=='POST' else request.args
            r=simulate(m,q.get('category','deposit'),q.get('period','12'),q.get('target_rate'),q.get('product'))
            return jsonify(r),(200 if r.get('ok') else 404)
        app.add_url_rule('/api/rate-simulation-v2','rate_simulation_v2_api',endpoint,methods=['GET','POST'])
    @app.after_request
    def inject(response):
        try:
            if request.path in ('/','/mobile') and response.status_code==200 and 'text/html' in str(response.content_type or ''):
                html=response.get_data(as_text=True)
                if 'data-sbrate-rate-simulation-v2' not in html:
                    html=html.replace('</head>',f'<style data-sbrate-rate-simulation-v2="css">{INLINE_CSS}</style></head>',1)
                    html=html.replace('</body>',f'<script data-sbrate-rate-simulation-v2="js">{INLINE_JS}</script></body>',1)
                    response.set_data(html);response.headers.pop('Content-Length',None)
        except Exception as e:print('Simulation V2 inject:',e)
        return response
    _rename_telegram(m);m._rate_simulator_v2_installed=True;print('Rate Simulation V2 installed');return True
