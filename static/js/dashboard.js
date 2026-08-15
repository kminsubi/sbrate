/**
 * SBRateBot V5 Executive Dashboard JS
 * Part 1/3
 *
 * KPI + Woori Market Position
 */



/* ==========================================================
   GLOBAL DASHBOARD DATA
========================================================== */

let dashboardKPIData = {};

let wooriMarketData = {};

let activeMarketProduct = "deposit";
let currentMarketItems = [];
let currentMarketMeta = {};
let currentMarketPeriod = "12";
let marketModeRequestId = 0;

const MARKET_PRODUCT_CONFIG = {
    deposit:{label:"정기예금"},
    isa:{label:"ISA"},
    irp:{label:"퇴직연금(IRP)"}
};

function marketProductLabel(mode = activeMarketProduct){
    return MARKET_PRODUCT_CONFIG[mode]?.label || "정기예금";
}

function currentSelectedPeriod(){
    return document.getElementById("product-period-select")?.value || currentMarketPeriod || "12";
}

function normalizeMarketItem(item,index=0){
    const rawRate=item?.rate ?? item?.intr_rate2 ?? item?.max_rate ?? item?.intr_rate;
    const rate=(rawRate===null || rawRate===undefined || rawRate==="") ? null : Number(rawRate);
    return {
        ...item,
        bank:item?.bank ?? item?.bank_name ?? item?.kor_co_nm ?? "-",
        product:item?.product ?? item?.product_name ?? item?.fin_prdt_nm ?? marketProductLabel(),
        rate:Number.isFinite(rate)?rate:null,
        disclosure_date:item?.disclosure_date ?? null,
        period:item?.period ?? `${currentSelectedPeriod()}개월`,
        rank:item?.rank ?? index+1,
        change:Number(item?.change ?? item?.diff ?? 0) || 0
    };
}

function validRateItems(items){
    return (Array.isArray(items) ? items : [])
        .map(normalizeMarketItem)
        .filter(item => {
            const raw = item?.rate;
            if(raw === null || raw === undefined || raw === ""){
                return false;
            }

            const rate = Number(raw);
            return Number.isFinite(rate) && rate > 0;
        });
}

function findWooriItem(items){
    return (Array.isArray(items)?items:[])
        .map(normalizeMarketItem)
        .find(item=>String(item.bank).includes("우리금융")) || null;
}

function disclosureSortValue(value){
    if(!value) return 0;
    const t=Date.parse(String(value).replace(/\./g,"-"));
    return Number.isFinite(t)?t:0;
}

function normalizeBankCore(name){
    return String(name||"").replace(/저축은행|금융|주식회사|㈜|\s/g,"").toUpperCase();
}

function isWooriBank(name){
    return String(name || "").includes("우리금융");
}

function displayBankName(name){
    return String(name || "-")
        .replace(/저축은행/g, "")
        .replace(/\s{2,}/g, " ")
        .trim();
}

function formatDisclosureDate(value){
    const text=String(value || "").trim();
    if(!text) return "";
    return text
        .replace(/\s*기준\s*$/g,"")
        .replace(/\s{2,}/g," ")
        .trim();
}



window.sbLastAIQuestion = window.sbLastAIQuestion || "";
window.sbLastAIAnswer = window.sbLastAIAnswer || "";



console.log(
    "🔥 DASHBOARD JS LOADED"
);



document.addEventListener("click", function(event){
    const sideBtn = event.target.closest("#ai-side-detail-btn");
    if(sideBtn){
        const normalDetail = document.getElementById("ai-detail-modal");
        if(normalDetail){
            normalDetail.classList.add("hidden");
            normalDetail.classList.remove("flex");
        }
    }
}, true);


document.addEventListener(
    "DOMContentLoaded",
    () => {


        console.log(
            "🔥 DOM CONTENT LOADED"
        );


        initDashboard().catch(error => {
            console.error("DASHBOARD INIT ERROR:", error);
        });


    }
);




/* ==========================================================
   3-PRODUCT MARKET MODE
========================================================== */

function updateMarketProductTabs(){
    document.querySelectorAll("[data-market-product]").forEach(button=>{
        const active=button.dataset.marketProduct===activeMarketProduct;
        button.className=active
            ?"market-product-tab bg-[#1a58c8] text-white px-4 py-1.5 rounded-lg text-[11px] font-bold shadow-sm"
            :"market-product-tab text-gray-500 px-4 py-1.5 rounded-lg text-[11px] font-semibold hover:bg-white hover:text-blue-700";
    });
}

function setText(id,value){
    const el=document.getElementById(id); if(el) el.textContent=value;
}
function setHtml(id,value){
    const el=document.getElementById(id); if(el) el.innerHTML=value;
}

function updateMarketProductLabels(){
    const label=marketProductLabel();
    const period=currentSelectedPeriod()||"12";
    setText("dashboard-market-label",`📌 저축은행 ${label}(${period}개월) 시장현황`);
    setText("market-top10-title",activeMarketProduct==="deposit"?"🏆 시장 TOP10":`🏆 ${label} TOP10`);
    setText("market-top10-meta",`${label} ${period}개월 · ${activeMarketProduct==="irp" ? "IRP 기준금리" : "최고금리 기준"}`);
    setText("product-panel-caption",activeMarketProduct==="deposit"?"정기예금 전체 기간 조회":`${label} 공시상품 조회 · 공시일 포함`);
    const q=document.getElementById("ai-question");
    if(q) q.placeholder=activeMarketProduct==="deposit"?"(예시) 금융지주 저축은행 금리 알려줘":`(예시) 우리금융 ${label} 경쟁력 알려줘`;
}

function updateAlternativeHeaders(){
    const isDeposit = activeMarketProduct === "deposit";

    setText("market-top10-col4", isDeposit ? "전일比" : "공시일");
    setText("market-top10-col4-right", isDeposit ? "전일比" : "공시일");

    if(isDeposit){
        setText("market-left-card-title","📈 상승 TOP5");
        setText("market-right-card-title","📉 하락 TOP5");
        setText("market-left-col4","전일比");
        setText("market-right-col4","전일比");
        setText("product-last-header","전일比");
    }else{
        setText("market-left-card-title","🗓️ 최근 공시 TOP5");
        setText("market-right-card-title","🎯 우리금융比 상위 TOP5");
        setText("market-left-col4","공시일");
        setText("market-right-col4","당행比");
        setText("product-last-header","공시일");
    }
}

function updateProductSortOptions(){
    const select=document.getElementById("product-sort-select");
    if(!select) return;
    const current=select.value;
    select.innerHTML=activeMarketProduct==="deposit"
        ?`<option value="rate_desc">금리 높은순</option><option value="rate_asc">금리 낮은순</option><option value="change_desc">변동폭 큰순</option><option value="bank_asc">은행명순</option>`
        :`<option value="rate_desc">금리 높은순</option><option value="rate_asc">금리 낮은순</option><option value="disclosure_desc">공시일 최신순</option><option value="bank_asc">은행명순</option>`;
    select.value=[...select.options].some(o=>o.value===current)?current:"rate_desc";
}

async function fetchAlternativeMarketItems(mode=activeMarketProduct,period=currentSelectedPeriod()){
    const endpoint=mode==="isa"?"/api/isa":"/api/irp";
    const data=await apiFetch(`${endpoint}?period=${encodeURIComponent(period||"12")}`);
    const items=Array.isArray(data)?data:(Array.isArray(data?.items)?data.items:[]);
    currentMarketMeta=data && !Array.isArray(data)?data:{};
    currentMarketItems=items.map(normalizeMarketItem);
    currentMarketPeriod=String(period||"12");
    return currentMarketItems;
}

function buildAlternativeKPI(items){
    const valid=validRateItems(items).sort((a,b)=>Number(b.rate)-Number(a.rate));
    const woori=findWooriItem(valid);
    const rates=valid.map(i=>Number(i.rate));
    const max=rates.length?Math.max(...rates):null;
    const min=rates.length?Math.min(...rates):null;
    const avg=rates.length?rates.reduce((a,b)=>a+b,0)/rates.length:null;
    const rank=woori?valid.findIndex(i=>String(i.bank).includes("우리금융"))+1:null;
    return {valid,woori,max,min,avg,rank,total:valid.length,disclosed:items.filter(i=>i.disclosure_date).length};
}

function neutralGap(value){
    const n=Number(value);
    if(!Number.isFinite(n)) return '<span class="text-gray-500">-</span>';
    if(n>0) return `<span class="text-blue-600 font-bold">+${n.toFixed(2)}%p</span>`;
    if(n<0) return `<span class="text-red-600 font-bold">▲${Math.abs(n).toFixed(2)}%p</span>`;
    return '<span class="text-gray-800 font-bold">0.00%p</span>';
}

function renderAlternativeHero(items){
    const {valid,woori,max,min,avg,rank,total,disclosed}=buildAlternativeKPI(items);
    const wr=Number(woori?.rate);
    setText("kpi-rank",rank||"-");
    setText("kpi-woori-rate-mini",Number.isFinite(wr)?`${wr.toFixed(2)}%`:"-");
    setText("kpi-best-rate-mini",max!=null?`${max.toFixed(2)}%`:"-");
    setText("kpi-lowest-rate-mini",min!=null?`${min.toFixed(2)}%`:"-");
    setHtml("kpi-highest-gap",Number.isFinite(wr)&&Number.isFinite(max)?neutralGap(wr-max):"-");
    setHtml("kpi-lowest-gap",Number.isFinite(wr)&&Number.isFinite(min)?neutralGap(wr-min):"-");
    setText("kpi-average-rate",avg!=null?`${avg.toFixed(2)}%`:"-");
    setHtml("kpi-average-gap",Number.isFinite(wr)&&Number.isFinite(avg)?neutralGap(wr-avg):"-");
    setText("kpi-product-count",`${items.length}개`);
    setText("kpi-change-count",`${disclosed}건`);

    const label=marketProductLabel(), top=valid[0];
    const summary=document.getElementById("executive-summary-mini");
    if(summary){
        const second=valid.find(item => !woori || normalizeBankCore(item.bank)!==normalizeBankCore(woori.bank));
        const top5=valid.slice(0,5);
        const top5Avg=top5.length
            ? top5.reduce((sum,item)=>sum+Number(item.rate||0),0)/top5.length
            : null;
        const gapTop=Number.isFinite(wr)&&Number.isFinite(max)?wr-max:null;
        const gapAvg=Number.isFinite(wr)&&Number.isFinite(avg)?wr-avg:null;
        const gapSecond=woori&&second&&Number.isFinite(wr)
            ? wr-Number(second.rate)
            : null;

        let positionText="우리금융 금리 확인이 필요합니다.";
        if(woori){
            if(rank===1 && gapSecond!==null){
                positionText=`우리금융 ${wr.toFixed(2)}%로 1위이며 2위 ${displayBankName(second.bank)} 대비 ${Math.abs(gapSecond).toFixed(2)}%p ${gapSecond>=0?"높습니다":"낮습니다"}.`;
            }else{
                positionText=`우리금융 ${wr.toFixed(2)}%로 ${rank}위/${total}, 시장 최고 대비 ${gapTop===null?"-":Math.abs(gapTop).toFixed(2)+"%p"} ${gapTop!==null&&gapTop<0?"낮은":"수준"}입니다.`;
            }
        }

        const avgText=gapAvg===null
            ? ""
            : gapAvg>0
                ? `시장 평균 대비 +${gapAvg.toFixed(2)}%p`
                : gapAvg<0
                    ? `시장 평균 대비 ${gapAvg.toFixed(2)}%p`
                    : "시장 평균과 동일";

        summary.innerHTML=`<div class="space-y-2 [word-break:keep-all]">
          <div>
            <div class="text-[10px] font-bold text-blue-700 mb-0.5">💡 AI 의견</div>
            <div class="text-[11px] leading-[1.5] text-gray-700">${positionText} ${avgText}${avgText?".":""}</div>
          </div>
          <div class="border-t border-gray-100 pt-2">
            <div class="text-[10px] font-bold text-gray-700 mb-1">📊 경쟁 구조</div>
            <div class="text-[10px] leading-[1.55] text-gray-500">
              상위5 평균 <b class="text-gray-700">${top5Avg!=null?top5Avg.toFixed(2)+"%":"-"}</b>
              · 시장최고 <b class="text-blue-700">${top?displayBankName(top.bank)+" "+Number(top.rate).toFixed(2)+"%":"-"}</b><br>
              공시일 확인 <b class="text-gray-700">${disclosed}/${items.length}개 기관</b>
              · 상위권 금리와 당행 Gap을 우선 모니터링
            </div>
          </div>
        </div>`;
    }
    setText("wibee-woori-rate",Number.isFinite(wr)?`${wr.toFixed(2)}%`:"-");
    setText("wibee-best-rate",max!=null?`${max.toFixed(2)}%`:"-");
    setText("wibee-average-rate",avg!=null?`${avg.toFixed(2)}%`:"-");
    setText("wibee-rank",rank?`${rank}위 / ${total}`:"-");
    setText("wibee-rise-count",disclosed);
    setText("wibee-fall-count",items.length-disclosed);
    setText("wibee-change-count",items.length);
    setText("wibee-rise-label","공시확인");
    setText("wibee-fall-label","공시미확인");
    setText("wibee-change-label","수집기관");
    const status=document.getElementById("wibee-market-status");
    if(status){status.className="inline-flex items-center gap-1 text-blue-600";status.innerHTML='<span class="w-2 h-2 rounded-full bg-blue-500"></span>공시 모니터링';}
    setText("wibee-judgement",woori?`우리금융 ${label}은 ${rank}위/${total}이며 공시일과 상위권 금리를 함께 모니터링합니다.`:`우리금융 ${label} 금리 확인이 필요합니다.`);
}

function renderAlternativeTop10(items){
    const valid = validRateItems(items)
        .sort((a,b) => Number(b.rate) - Number(a.rate));

    const b1 = document.getElementById("top5-table-body");
    const b2 = document.getElementById("top10-table-body");

    if(!b1 || !b2) return;

    b1.innerHTML = "";
    b2.innerHTML = "";

    valid.slice(0,10).forEach((item,index) => {
        const tr = document.createElement("tr");
        const isWoori = isWooriBank(item.bank);

        if(isWoori){
            /*
             * V5.11.6
             * - colspan 내부의 실제 데이터 grid는 header와 동일한 12/40/22/26
             * - 배경 레이어만 right:-10px
             * - 데이터 좌표는 width:100% 기준이라 절대 이동하지 않음
             */
            tr.innerHTML = `
              <td colspan="4" class="py-1 overflow-visible">
                <div class="relative w-full overflow-visible">
                  <div
                    class="absolute inset-y-0 left-0 -right-[10px] rounded-[14px] border border-blue-300 bg-gradient-to-r from-blue-50 to-[#f3f8ff] pointer-events-none"
                    aria-hidden="true"
                  ></div>

                  <div class="relative z-10 grid grid-cols-[12%_40%_22%_26%] items-center w-full py-2">
                    <div class="text-center">
                      <span class="${index<3 ? "bg-orange-100 text-orange-600" : "bg-blue-100 text-blue-700 ring-1 ring-blue-200"} min-w-5 h-5 px-1 rounded-full inline-flex items-center justify-center text-[10px] font-bold">
                        ${index+1}
                      </span>
                    </div>

                    <div class="text-center truncate px-1 font-bold text-blue-700" title="${item.bank}">
                      ${displayBankName(item.bank)}
                    </div>

                    <div class="text-center font-bold text-blue-700">
                      ${Number(item.rate).toFixed(2)}%
                    </div>

                    <div class="text-center text-xs font-semibold text-blue-700 whitespace-nowrap">
                      ${formatDisclosureDate(item.disclosure_date || item.rate_month) || "-"}
                    </div>
                  </div>
                </div>
              </td>`;
        }else{
            const rankClass = index < 3
                ? "bg-orange-100 text-orange-600"
                : "bg-gray-100 text-gray-600";

            tr.innerHTML = `
              <td class="py-2 text-center">
                <span class="${rankClass} min-w-5 h-5 px-1 rounded-full inline-flex items-center justify-center text-[10px] font-bold">${index+1}</span>
              </td>
              <td class="py-2 text-center truncate px-1" title="${item.bank}">
                ${displayBankName(item.bank)}
              </td>
              <td class="py-2 text-center font-semibold text-blue-600">
                ${Number(item.rate).toFixed(2)}%
              </td>
              <td class="py-2 text-center text-xs font-semibold whitespace-nowrap">
                ${formatDisclosureDate(item.disclosure_date || item.rate_month) || "-"}
              </td>`;
        }

        (index < 5 ? b1 : b2).appendChild(tr);
    });

    if(valid.length === 0){
        const empty =
            '<tr><td colspan="4" class="text-center py-4 text-gray-400">금리 공시 데이터 없음</td></tr>';

        b1.innerHTML = empty;
        b2.innerHTML = empty;
    }

    requestAnimationFrame(syncAIAnalysisCenterHeight);
}


function renderAlternativeSideCards(items){
    const left = document.getElementById("rates-up-list");
    const right = document.getElementById("rates-down-list");

    if(!left || !right) return;

    const valid = validRateItems(items)
        .sort((a,b) => Number(b.rate) - Number(a.rate));

    const woori = findWooriItem(valid);
    const wooriRate = Number(woori?.rate);

    // 공시일이 있는 기관 중 금리 높은 순
    const recent = valid
        .filter(item => item.disclosure_date)
        .sort((a,b) => Number(b.rate) - Number(a.rate))
        .slice(0,5);

    const higher = Number.isFinite(wooriRate)
        ? valid
            .filter(item =>
                Number(item.rate) > wooriRate &&
                !isWooriBank(item.bank)
            )
            .slice(0,5)
        : valid.slice(0,5);

    left.innerHTML = recent.length
        ? recent.map((item,index) => {
            if(isWooriBank(item.bank)){
                return `
                  <tr>
                    <td colspan="4" class="py-1 overflow-visible">
                      <div class="relative w-full overflow-visible">
                        <div
                          class="absolute inset-y-0 left-0 -right-[10px] rounded-[14px] border border-blue-300 bg-gradient-to-r from-blue-50 to-[#f3f8ff] pointer-events-none"
                          aria-hidden="true"
                        ></div>

                        <div class="relative z-10 grid grid-cols-[14%_38%_22%_26%] items-center w-full py-2">
                          <div class="text-center font-bold text-blue-700">${index+1}</div>
                          <div class="text-center truncate px-1 font-bold text-blue-700" title="${item.bank}">
                            ${displayBankName(item.bank)}
                          </div>
                          <div class="text-center font-bold text-blue-700">
                            ${Number(item.rate).toFixed(2)}%
                          </div>
                          <div class="text-center text-xs font-semibold whitespace-nowrap text-blue-700">
                            ${formatDisclosureDate(item.disclosure_date || item.rate_month) || "-"}
                          </div>
                        </div>
                      </div>
                    </td>
                  </tr>`;
            }

            return `
              <tr>
                <td class="py-2 text-center text-gray-500">${index+1}</td>
                <td class="py-2 text-center truncate px-1 text-gray-700" title="${item.bank}">${displayBankName(item.bank)}</td>
                <td class="py-2 text-center font-semibold text-blue-700">${Number(item.rate).toFixed(2)}%</td>
                <td class="py-2 text-center text-xs font-semibold whitespace-nowrap">${formatDisclosureDate(item.disclosure_date || item.rate_month) || "-"}</td>
              </tr>`;
          }).join("")
        : '<tr><td colspan="4" class="py-4 text-center text-gray-400">공시일 데이터 없음</td></tr>';

    right.innerHTML = higher.length
        ? higher.map((item,index) => {
            const gap = Number.isFinite(wooriRate)
                ? Number(item.rate) - wooriRate
                : null;

            return `
              <tr>
                <td class="py-2 text-center text-gray-500">${index+1}</td>
                <td class="py-2 text-center truncate px-1 text-gray-700" title="${item.bank}">${displayBankName(item.bank)}</td>
                <td class="py-2 text-center font-semibold text-indigo-700">${Number(item.rate).toFixed(2)}%</td>
                <td class="py-2 text-center font-semibold whitespace-nowrap">
                  ${gap === null ? "-" : `<span class="text-blue-600">+${gap.toFixed(2)}%p</span>`}
                </td>
              </tr>`;
          }).join("")
        : '<tr><td colspan="4" class="py-4 text-center text-gray-400">우리금융보다 높은 기관 없음</td></tr>';

    requestAnimationFrame(syncAIAnalysisCenterHeight);
}


function populateAlternativeProductBanks(items){
    const s=document.getElementById("product-bank-select"); if(!s)return;
    s.innerHTML='<option value="">전체 저축은행</option>';
    [...new Set(items.map(productBankName).filter(Boolean))].sort((a,b)=>a.localeCompare(b,"ko")).forEach(bank=>{const o=document.createElement("option");o.value=bank;o.textContent=bank;s.appendChild(o);});
    s.dataset.loaded="1";
}

async function loadAlternativeMarket(mode=activeMarketProduct,requestId=marketModeRequestId){
    const periodAtRequest=currentSelectedPeriod()||"12";
    const items=await fetchAlternativeMarketItems(mode,periodAtRequest);

    if(requestId!==marketModeRequestId || activeMarketProduct!==mode) return;

    renderAlternativeHero(items);
    renderAlternativeTop10(items);
    renderAlternativeSideCards(items);

    allProductData=items.map(normalizeMarketItem);
    populateAlternativeProductBanks(allProductData);
    updateProductSortOptions();
    applyProductFilters();

    if(requestId!==marketModeRequestId || activeMarketProduct!==mode) return;
    await renderAIAnalysisCenter(aiCenterActiveTab||"market");
    requestAnimationFrame(syncAIAnalysisCenterHeight);
}

async function switchMarketProduct(mode){
    if(!MARKET_PRODUCT_CONFIG[mode]) return;

    // Product dashboard switch always starts from the first screen.
    // Initial page load is already at the top, so this is harmless there.
    window.scrollTo({
        top: 0,
        behavior: "smooth"
    });

    const requestId = ++marketModeRequestId;
    activeMarketProduct = mode;
    currentMarketPeriod = currentSelectedPeriod() || "12";

    markAIAnalysisCenterSyncing();

    updateMarketProductTabs();
    updateMarketProductLabels();
    updateAlternativeHeaders();
    updateProductSortOptions();

    const bank = document.getElementById("product-bank-select");
    if(bank){
        bank.dataset.loaded = "0";
        bank.innerHTML = '<option value="">전체 저축은행</option>';
    }

    if(mode === "deposit"){
        // 직전 ISA/IRP HERO 제거
        ["kpi-rank","kpi-woori-rate-mini","kpi-best-rate-mini","kpi-lowest-rate-mini",
         "kpi-average-rate","kpi-product-count","kpi-change-count",
         "wibee-woori-rate","wibee-best-rate","wibee-average-rate","wibee-rank"]
        .forEach(id => setText(id, "-"));

        ["kpi-highest-gap","kpi-lowest-gap","kpi-average-gap"]
        .forEach(id => setHtml(id, "-"));

        setText("wibee-rise-label","상승");
        setText("wibee-fall-label","하락");
        setText("wibee-change-label","전체변동");

        // 정기예금 HERO는 loadHero()가 실제 담당하므로 반드시 호출
        await Promise.all([
            loadHero(),
            fetchKPI(),
            fetchWooriData(),
            fetchAISummary(),
            fetchWibeeBriefing(),
            fetchRatesData(),
            fetchFinancialData(),
            fetchAllProducts()
        ]);

        if(requestId !== marketModeRequestId || activeMarketProduct !== "deposit"){
            return;
        }

        // 화면 마지막 상태를 정기예금 데이터로 한 번 더 확정
        await loadHero();

        if(requestId !== marketModeRequestId || activeMarketProduct !== "deposit"){
            return;
        }

        await renderAIAnalysisCenter(aiCenterActiveTab || "market");
        requestAnimationFrame(syncAIAnalysisCenterHeight);
        return;
    }

    await loadAlternativeMarket(mode, requestId);
}


function syncAIAnalysisCenterHeight(){
    /*
      V5.11
      AI센터 높이는 더 이상 JS로 계산하지 않는다.
      main(9col) + aside(3col)이 같은 CSS Grid row에 있으므로
      브라우저가 좌측 전체 높이와 우측 패널 높이를 자동으로 동일하게 맞춘다.
      상품 전환 시 누적 height / marginTop이 남지 않도록 inline style만 제거한다.
    */
    const aiCenter = document.getElementById("ai-analysis-center");
    if(!aiCenter) return;

    aiCenter.style.removeProperty("margin-top");
    aiCenter.style.removeProperty("height");
    aiCenter.style.removeProperty("min-height");
    aiCenter.style.removeProperty("max-height");
    aiCenter.style.removeProperty("overflow");

    aiCenter.classList.remove("ai-syncing");
    aiCenter.classList.add("ai-synced");
}

function markAIAnalysisCenterSyncing(){
    const aiCenter = document.getElementById("ai-analysis-center");
    if(!aiCenter) return;
    aiCenter.classList.remove("ai-syncing");
    aiCenter.classList.add("ai-synced");
}

function setupMarketProductTabs(){
    document.querySelectorAll("[data-market-product]").forEach(b=>b.addEventListener("click",()=>switchMarketProduct(b.dataset.marketProduct)));
    updateMarketProductTabs(); updateMarketProductLabels();
    requestAnimationFrame(syncAIAnalysisCenterHeight);
}

/* ==========================================================
   DASHBOARD INITIALIZE
========================================================== */


async function initDashboard() {

    console.log(
        "🔥 SBRateBot V5 Dashboard START"
    );

    setupMarketProductTabs();

    /*
        UI EVENT BINDING
    */
    setupEventListeners();
    initDraggableModals();
    initErrorReportCenter();

    /*
        AI ANALYSIS CENTER EVENT BINDING
        - 내부에서 최초 market render 1회 실행
    */
    await initAIAnalysisCenter();

    /*
        IMPORTANT:
        최초 접속도 사용자가 '정기예금' 탭을 다시 누른 것과
        완전히 같은 데이터/레이아웃 경로를 사용한다.

        기존에는 최초 로딩 시 여러 fetch가 병렬 실행되면서
        AI센터 높이 계산 타이밍이 먼저 잡혀 패널이 길어졌고,
        탭을 다시 누르면 정상화되는 현상이 있었다.
    */
    await switchMarketProduct("deposit");

    /*
        폰트/브라우저 최종 레이아웃 반영 뒤 재확정.
        최초 접속에서만 발생하던 패널 길이 오차 방지.
    */
    requestAnimationFrame(syncAIAnalysisCenterHeight);
    if(document.fonts && document.fonts.ready){
        document.fonts.ready.then(() => requestAnimationFrame(syncAIAnalysisCenterHeight)).catch(()=>{});
    }

}


/* ==========================================================
   Common API Fetch
========================================================== */

// 동일 API가 초기 렌더링 과정에서 여러 컴포넌트에 의해 반복 호출되는 것을 방지한다.
// 정기예금 데이터는 스케줄러가 갱신하므로, 화면 초기화 중 짧은 시간은 같은 응답을 공유해도 안전하다.
const sbApiCache = new Map();
const sbApiInFlight = new Map();
const SB_API_CACHE_MS = 5000;

function clearDashboardApiCache(){
    sbApiCache.clear();
}

async function apiFetch(url) {

    const now = Date.now();
    const cached = sbApiCache.get(url);

    if(cached && (now - cached.time) < SB_API_CACHE_MS){
        return cached.data;
    }

    if(sbApiInFlight.has(url)){
        return sbApiInFlight.get(url);
    }

    const requestPromise = (async () => {
        try {
            const response = await fetch(url);

            if (!response.ok) {
                throw new Error(`API Error : ${response.status}`);
            }

            const data = await response.json();
            sbApiCache.set(url, { time: Date.now(), data });
            return data;

        } catch(error) {
            console.error("API Fetch Error:", url, error);
            return null;
        } finally {
            sbApiInFlight.delete(url);
        }
    })();

    sbApiInFlight.set(url, requestPromise);
    return requestPromise;
}



/* ==========================================================
   KPI SECTION
   /api/kpi

   V5 Executive Dashboard KPI Rendering
========================================================== */


async function fetchKPI() {


    const data =
        await apiFetch(
            "/api/kpi"
        );


    if(!data){

        return;

    }


    console.log(
        "KPI DATA",
        data
    );


    renderKPI(
        data
    );


}

/* ==========================================================
   AI MARKET SUMMARY
   /api/ai

   V5 Executive Dashboard
   AI 시장분석 현황
========================================================== */


async function fetchAISummary(){


    const [data, kpiData, freshWooriData] = await Promise.all([
        apiFetch("/api/ai"),
        apiFetch("/api/kpi"),
        apiFetch("/api/woori")
    ]);

    if(!data){
        return;
    }

    const marketKpi = kpiData || {};
    const marketWoori = freshWooriData || wooriPositionData || {};



    console.log(
        "AI SUMMARY DATA",
        data
    );



    const target =
        document.getElementById(
            "executive-summary-mini"
        );



    if(!target){

        return;

    }



    if(

        !Array.isArray(
            data.summary
        )

    ){

        target.innerHTML =
            "시장 데이터를 분석하는 중입니다.";

        return;

    }



    const summary =
        data.summary;



    /*
        AI 의견
        summary 마지막 2개 문장 사용
    */


        const maxRate = Number(
        marketKpi.max_rate ??
        marketKpi.highest_rate
    );

    const avgRate = Number(
        marketKpi.average_rate
    );

    const minRate = Number(
        marketKpi.min_rate
    );

    const wooriRate = Number(
        marketWoori.rate
    );

    const marketRank =
        marketWoori.market_rank ??
        marketWoori.rank ??
        "-";

    const gapToTop =
        Number.isFinite(maxRate) &&
        Number.isFinite(wooriRate)
            ? wooriRate - maxRate
            : null;

    const gapToAverage =
        Number.isFinite(avgRate) &&
        Number.isFinite(wooriRate)
            ? wooriRate - avgRate
            : null;

    const aiOpinion = (() => {
        if(!Number.isFinite(wooriRate)){
            return "우리금융 금리 데이터 확인 후 시장 상단과의 경쟁력 격차를 점검할 필요가 있습니다.";
        }

        const topText =
            gapToTop === null
                ? ""
                : gapToTop === 0
                    ? "시장 최고금리와 동일한 수준"
                    : `시장 최고 대비 ${Math.abs(gapToTop).toFixed(2)}%p 낮은 수준`;

        const avgText =
            gapToAverage === null
                ? ""
                : gapToAverage > 0
                    ? `시장 평균보다 ${gapToAverage.toFixed(2)}%p 높습니다`
                    : gapToAverage < 0
                        ? `시장 평균보다 ${Math.abs(gapToAverage).toFixed(2)}%p 낮습니다`
                        : "시장 평균과 동일합니다";

        return `우리금융은 ${marketRank}위 · ${wooriRate.toFixed(2)}%로 ${topText}이며, ${avgText}. 상위권 금리 조정과 당행 Gap 변화를 중심으로 모니터링이 필요합니다.`;
    })();



/* ==========================================================
   AI DETAIL MODAL CONTENT (COMPACT EXECUTIVE STYLE)
========================================================== */


const detailContent = `


<div class="space-y-2">



<!-- 시장 흐름 분석 -->

<div
class="
bg-blue-50
border
border-blue-100
rounded-lg
px-3
py-2
"
>


<div
class="
font-bold
text-blue-700
text-xs
mb-1
"
>
📈 시장 흐름 분석
</div>


<div
class="
text-gray-600
leading-5
"
>

${

    aiOpinion

    ||

    "시장 분석 데이터가 없습니다."

}

</div>


</div>






        <!-- 시장 현황 -->

        <div
        class="border border-gray-100 rounded-xl p-3"
        >


            <div
            class="font-bold text-gray-800 mb-3 text-sm"
            >

                📊 시장 현황

            </div>



            <div
            class="grid grid-cols-5 gap-2 text-center"
            >



                <div
                class="bg-gray-50 rounded-lg p-2"
                >

                    <div
                    class="text-[10px] text-gray-400"
                    >
                        상품수
                    </div>

                    <div
                    class="text-sm font-bold text-gray-800"
                    >
                        ${Number(marketKpi.product_count || 0).toLocaleString()}개
                    </div>

                </div>





                <div
                class="bg-gray-50 rounded-lg p-2"
                >

                    <div
                    class="text-[10px] text-gray-400"
                    >
                        평균금리
                    </div>

                    <div
                    class="text-sm font-bold text-blue-700"
                    >
                        ${Number(marketKpi.average_rate || 0).toFixed(2)}%
                    </div>

                </div>





                <div
                class="bg-gray-50 rounded-lg p-2"
                >

                    <div
                    class="text-[10px] text-gray-400"
                    >
                        최고금리
                    </div>

                    <div
                    class="text-sm font-bold text-blue-700"
                    >
                        ${Number(marketKpi.max_rate || 0).toFixed(2)}%
                    </div>

                    <div
                    class="text-[9px] text-gray-400"
                    >
                        조은
                    </div>

                </div>





                <div
                class="bg-gray-50 rounded-lg p-2"
                >

                    <div
                    class="text-[10px] text-gray-400"
                    >
                        최저금리
                    </div>

                    <div
                    class="text-sm font-bold text-gray-700"
                    >
                        ${Number(marketKpi.min_rate || 0).toFixed(2)}%
                    </div>

                    <div
                    class="text-[9px] text-gray-400"
                    >
                        조은
                    </div>

                </div>





                <div
                class="bg-gray-50 rounded-lg p-2"
                >

                    <div
                    class="text-[10px] text-gray-400"
                    >
                        금리 스프레드
                    </div>

                    <div
                    class="text-sm font-bold text-orange-600"
                    >
                        ${(Number(marketKpi.max_rate || 0) - Number(marketKpi.min_rate || 0)).toFixed(2)}%p
                    </div>

                </div>



            </div>


        </div>




<!-- 우리금융 경쟁력 -->

<div
class="
bg-blue-50
border
border-blue-100
rounded-lg
px-3
py-2
"
>


<div
class="
font-bold
text-blue-700
text-xs
mb-2
"
>
🏦 우리금융 경쟁력 분석
</div>



<div
class="
grid
grid-cols-3
gap-2
text-center
"
>


<!-- 시장순위 -->

<div
class="
bg-white
rounded-lg
py-2
"
>

<div
class="text-[10px] text-gray-400"
>
시장순위
</div>


<div
class="
font-bold
text-blue-700
text-sm
"
>
${
marketWoori.market_rank
?
marketWoori.market_rank + "위"
:
"-"
}
</div>


</div>






<!-- 현재금리 -->

<div
class="
bg-white
rounded-lg
py-2
"
>

<div
class="text-[10px] text-gray-400"
>
현재금리
</div>


<div
class="
font-bold
text-gray-800
text-sm
"
>
${
marketWoori.rate
?
Number(
    marketWoori.rate
)
.toFixed(2)
+
"%"
:
"-"
}
</div>


</div>







<!-- 평균금리 대비 -->

<div
class="
bg-white
rounded-lg
py-2
"
>

<div
class="text-[10px] text-gray-400"
>
평균금리 대비
</div>


<div
class="
font-bold
text-sm
"
>


${

Number(
    marketWoori.average_gap || 0
)
> 0

?

`
<span class="text-blue-600">
+${Number(
    marketWoori.average_gap
)
.toFixed(2)}%p
</span>
`

:

Number(
    marketWoori.average_gap || 0
)
< 0

?

`
<span class="text-red-600">
▲${Math.abs(
Number(
    marketWoori.average_gap
)
)
.toFixed(2)}%p
</span>
`

:

`
<span class="text-gray-800">
0.00%p
</span>
`

}


</div>


</div>




</div>


</div>








<!-- 체크포인트 -->

<div
class="
bg-yellow-50
border
border-yellow-100
rounded-lg
px-3
py-2
"
>


<div
class="
font-bold
text-yellow-700
text-xs
mb-1
"
>
⚠️ 주요 체크포인트
</div>


<div
class="
text-gray-600
leading-5
"
>

• 경쟁사 최고금리 변화 모니터링

<br>

• 금리 상승 기관 발생 여부 확인

<br>

• 시장 평균 대비 경쟁력 점검

</div>


</div>








<!-- AI 대응 전략 -->

<div
class="
bg-gray-50
border
border-gray-100
rounded-lg
px-3
py-2
"
>


<div
class="
font-bold
text-gray-800
text-xs
mb-1
"
>
🎯 AI 대응 전략
</div>


<div
class="
text-gray-600
leading-5
"
>

• 금리 경쟁력 유지 및 시장 변화 대응

<br>

• 경쟁사 금리 조정 시 즉시 검토

<br>

• 신규 상품 출시 가능성 점검

</div>


</div>








<!-- AI 종합 판단 -->

<div
class="
bg-amber-50
border
border-amber-100
rounded-lg
px-3
py-2
"
>


<div
class="
font-bold
text-amber-800
text-xs
mb-1
"
>
🤖 AI 종합 판단
</div>


<div
class="
text-gray-700
leading-5
"
>

우리금융은 시장 내 안정적인 경쟁력을 유지하고 있습니다.

<br>

경쟁사 금리 조정 및 신규 상품 출시 여부를 지속적으로 모니터링할 필요가 있습니다.

</div>


</div>



</div>


`;



    /* ==========================================================
       모달 내용 갱신
    ========================================================== */

    const modal =

        document.getElementById(
            "market-detail-content"
        );


    if (modal) {

        modal.innerHTML = detailContent;

    }



        /*
        시장 데이터
    */


    const marketSpread =
        Number.isFinite(maxRate) && Number.isFinite(minRate)
            ? maxRate - minRate
            : null;

    const marketData = `
        <div class="text-[11px] text-gray-700 leading-5">
            <div class="mb-1 text-[11px] font-bold text-gray-800">
                📊 시장 현황
            </div>

            <div class="grid grid-cols-3 gap-x-4 gap-y-0.5">
                <div class="whitespace-nowrap">
                    <span class="text-gray-400">분석상품</span>
                    <b class="ml-1">${Number(marketKpi.product_count || 0).toLocaleString()}개</b>
                </div>

                <div class="whitespace-nowrap">
                    <span class="text-gray-400">평균금리</span>
                    <b class="ml-1">${Number.isFinite(avgRate) ? avgRate.toFixed(2) + "%" : "-"}</b>
                </div>

                <div class="whitespace-nowrap">
                    <span class="text-gray-400">금리 스프레드</span>
                    <b class="ml-1">${marketSpread === null ? "-" : marketSpread.toFixed(2) + "%p"}</b>
                </div>

                <div class="whitespace-nowrap">
                    <span class="text-gray-400">시장 최고</span>
                    <b class="ml-1 text-blue-700">${Number.isFinite(maxRate) ? maxRate.toFixed(2) + "%" : "-"}</b>
                </div>

                <div class="whitespace-nowrap">
                    <span class="text-gray-400">우리금융</span>
                    <b class="ml-1 text-blue-700">${Number.isFinite(wooriRate) ? wooriRate.toFixed(2) + "%" : "-"}</b>
                </div>

                <div class="text-right whitespace-nowrap">
                    <button
                        id="market-detail-btn"
                        class="text-[11px] text-blue-600 font-semibold hover:underline"
                    >
                        AI 상세분석 &gt;
                    </button>
                </div>
            </div>
        </div>
    `;


    /*
        최종 출력
    */


    target.innerHTML = `


        <div class="mb-2">


            <div class="text-xs font-bold text-gray-800 mb-1">

                💡 AI 의견

            </div>



            <div class="text-[11px] text-gray-700 leading-[1.45] [word-break:keep-all]">


                ${

                    aiOpinion

                    ||

                    "시장 금리 흐름을 분석 중입니다."

                }


            </div>


        </div>





        <div class="border-t pt-2">


            ${marketData}


        </div>



    `;



}



function renderKPI(data){

    dashboardKPIData = data;



    /* ======================================================
       KPI DOM
    ====================================================== */


    const highestGap =
        document.getElementById(
            "kpi-highest-gap"
        );


    const lowestGap =
        document.getElementById(
            "kpi-lowest-gap"
        );


    const averageRate =
        document.getElementById(
            "kpi-average-rate"
        );


    const averageGap =
        document.getElementById(
            "kpi-average-gap"
        );


    const productCount =
        document.getElementById(
            "kpi-product-count"
        );


    const changeCount =
        document.getElementById(
            "kpi-change-count"
        );





    /* ======================================================
       최고금리 比
    ====================================================== */


    if(highestGap){


        const value =
            Number(
                data.highest_gap || 0
            );


        highestGap.innerHTML =
            value < 0
            ?
            `
            <span class="text-red-600">
            ▲${Math.abs(value).toFixed(2)}%p
            </span>
            `
            :
            `
            <span class="text-blue-600">
            +${value.toFixed(2)}%p
            </span>
            `;


    }






    /* ======================================================
       최저금리 比
    ====================================================== */


    if(lowestGap){


        const value =
            Number(
                data.lowest_gap || 0
            );


        lowestGap.innerHTML =
            value < 0
            ?
            `
            <span class="text-red-600">
            ▲${Math.abs(value).toFixed(2)}%p
            </span>
            `
            :
            `
            <span class="text-blue-600">
            +${value.toFixed(2)}%p
            </span>
            `;


    }






    /* ======================================================
       평균금리
    ====================================================== */


    if(averageRate){


        averageRate.innerHTML =
            data.average_rate !== undefined
            ?
            `${Number(data.average_rate).toFixed(2)}%`
            :
            "-";


    }






    /* ======================================================
       평균금리 比
    ====================================================== */


    if(averageGap){


        const value =
            Number(
                data.average_gap || 0
            );


        averageGap.innerHTML =
            value < 0
            ?
            `
            <span class="text-red-600">
            ▲${Math.abs(value).toFixed(2)}%p
            </span>
            `
            :
            value > 0
            ?
            `
            <span class="text-blue-600">
            +${value.toFixed(2)}%p
            </span>
            `
            :
            `
            <span class="text-gray-800">
            0.00%p
            </span>
            `;


    }






    /* ======================================================
       상품수
    ====================================================== */


    if(productCount){


        productCount.innerHTML =
            data.product_count !== undefined
            ?
            `${Number(data.product_count).toLocaleString()}개`
            :
            "-";


    }






    /* ======================================================
       금리변동수
    ====================================================== */


    if(changeCount){


        changeCount.innerHTML =
            data.change_count !== undefined
            ?
            `${Number(data.change_count)}건`
            :
            "0건";


    }






    updateTime(
        data.last_updated
    );


}







/* ==========================================================
   LAST UPDATED
========================================================== */


function updateTime(time){


    const target =
        document.getElementById(
            "last-updated"
        );



    if(!target){

        return;

    }





    if(time){


        target.innerHTML =
        `
        <i class="fa-regular fa-clock"></i>
        기준일시 : ${time}
        `;


    }


    else{


        const now =
            new Date()
            .toLocaleString(
                "ko-KR"
            );


        target.innerHTML =
        `
        <i class="fa-regular fa-clock"></i>
        ${now}
        `;


    }


}




/* ==========================================================
   HEADER LIVE TIME + DATA UPDATE TIME
========================================================== */

function formatKoreanCurrentDateTime(dateValue){
    const d = dateValue instanceof Date ? dateValue : new Date(dateValue);

    if(Number.isNaN(d.getTime())){
        return "-";
    }

    const days = ["일","월","화","수","목","금","토"];
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth()+1).padStart(2,"0");
    const dd = String(d.getDate()).padStart(2,"0");
    const hh = String(d.getHours()).padStart(2,"0");
    const mi = String(d.getMinutes()).padStart(2,"0");
    const ss = String(d.getSeconds()).padStart(2,"0");

    return `${yyyy}-${mm}-${dd} (${days[d.getDay()]}) ${hh}:${mi}:${ss}`;
}

function extractTimeOnly(value){
    if(!value){
        return "-";
    }

    const text = String(value).trim();

    const match = text.match(/(\d{1,2}):(\d{2})(?::(\d{2}))?/);
    if(match){
        return `${String(match[1]).padStart(2,"0")}:${match[2]}`;
    }

    return text;
}

function startHeaderClock(){
    const target = document.getElementById("header-current-datetime");
    if(!target){
        return;
    }

    const render = () => {
        target.textContent = formatKoreanCurrentDateTime(new Date());
    };

    render();
    window.setInterval(render, 1000);
}

function parseDashboardDateTime(value){
    if(!value){
        return null;
    }

    const raw = String(value).trim();

    const match = raw.match(
        /(\d{4})[-./](\d{1,2})[-./](\d{1,2})[^\d]+(\d{1,2}):(\d{2})(?::(\d{2}))?/
    );

    if(match){
        return new Date(
            Number(match[1]),
            Number(match[2]) - 1,
            Number(match[3]),
            Number(match[4]),
            Number(match[5]),
            Number(match[6] || 0)
        );
    }

    const parsed = new Date(raw);

    return Number.isNaN(parsed.getTime())
        ? null
        : parsed;
}

function formatDataBasis(value){
    const parsed = parseDashboardDateTime(value);

    if(parsed){
        const yyyy = parsed.getFullYear();
        const mm = String(parsed.getMonth()+1).padStart(2,"0");
        const dd = String(parsed.getDate()).padStart(2,"0");
        const hh = String(parsed.getHours()).padStart(2,"0");
        const mi = String(parsed.getMinutes()).padStart(2,"0");

        return `${yyyy}-${mm}-${dd} ${hh}:${mi}`;
    }

    return value
        ? String(value)
        : "-";
}

function renderDataFreshness(value){
    const badge = document.getElementById("header-data-status");

    if(!badge){
        return;
    }

    badge.className =
        "px-2 py-0.5 rounded-full text-[10px] font-semibold whitespace-nowrap";

    const parsed = parseDashboardDateTime(value);

    if(!parsed){
        badge.textContent = "기준시각 확인";
        badge.classList.add(
            "bg-gray-100",
            "text-gray-500",
            "border",
            "border-gray-200"
        );
        return;
    }

    const ageHours =
        (Date.now() - parsed.getTime())
        / (1000 * 60 * 60);

    if(ageHours >= 24){
        badge.textContent = "갱신 지연";
        badge.classList.add(
            "bg-orange-50",
            "text-orange-700",
            "border",
            "border-orange-100"
        );
    }
    else{
        badge.textContent = "최신";
        badge.classList.add(
            "bg-emerald-50",
            "text-emerald-700",
            "border",
            "border-emerald-100"
        );
    }
}

async function refreshHeaderDataUpdateTime(){
    const target = document.getElementById("header-data-update-time");

    if(!target){
        return;
    }

    const kpi = await apiFetch("/api/kpi");

    const value =
        kpi?.last_updated ??
        kpi?.last_update ??
        kpi?.updated_at ??
        null;

    window.sbDataBasisValue = value;

    target.textContent = formatDataBasis(value);
    target.title = value
        ? `데이터 업데이트 시간일시: ${value}`
        : "데이터 업데이트 시간일시 정보 없음";

    renderDataFreshness(value);

    const reportBasis =
        document.getElementById(
            "ai-report-data-basis"
        );

    if(reportBasis){
        reportBasis.textContent =
            `데이터 업데이트 기준 ${formatDataBasis(value)}`;
    }
}

function setupHeaderRefresh(){
    const btn = document.getElementById("header-refresh-btn");
    if(!btn){
        return;
    }

    btn.addEventListener("click", async () => {
        btn.disabled = true;
        clearDashboardApiCache();

        try{
            await Promise.all([
                refreshHeaderDataUpdateTime(),
                typeof fetchKPI === "function" ? fetchKPI() : Promise.resolve(),
                typeof fetchRatesData === "function" ? fetchRatesData() : Promise.resolve(),
                typeof fetchFinancialData === "function" ? fetchFinancialData() : Promise.resolve(),
                typeof fetchWibeeBriefing === "function" ? fetchWibeeBriefing() : Promise.resolve()
            ]);

            if(typeof renderAIAnalysisCenter === "function"){
                await renderAIAnalysisCenter(aiCenterActiveTab || "market");
            }
        }
        finally{
            btn.disabled = false;
        }
    });
}

/* ==========================================================
   WOORI MARKET POSITION
   /api/woori
========================================================== */


let wooriPositionData = {};



async function fetchWooriData(){


    const data =
        await apiFetch(
            "/api/woori"
        );


    if(!data){

        console.log(
            "WOORI DATA EMPTY"
        );

        return;

    }



    console.log(
        "🔥 WOORI API",
        data
    );



    wooriPositionData = data;



    renderWooriPosition(
        data
    );


}





function renderWooriPosition(data){

    console.log(
        "🔥 RENDER WOORI",
        data
    );


    const rank =
        document.getElementById(
            "woori-rank"
        );


    const rate =
        document.getElementById(
            "woori-rate"
        );


    const avgGap =
        document.getElementById(
            "woori-gap-average"
        );



    /*
        시장순위
    */

    if(rank){

        rank.innerHTML =
            data.market_rank
            ?
            `${data.market_rank}위`
            :
            "-";

    }



    /*
        현재금리
    */

    if(rate){

        rate.innerHTML =
            data.rate !== undefined
            ?
            `${Number(data.rate).toFixed(2)}%`
            :
            "-";

    }



    /*
        시장평균 대비
    */

    if(avgGap){


        const value =
            Number(
                data.average_gap ?? 0
            );


        if(
            value > 0
        ){

            avgGap.innerHTML =
            `
            <span class="text-blue-600 font-bold">
            +${value.toFixed(2)}%p
            </span>
            `;


        }
        else if(
            value < 0
        ){

            avgGap.innerHTML =
            `
            <span class="text-red-600 font-bold">
            ▲${Math.abs(value).toFixed(2)}%p
            </span>
            `;


        }
        else{


            avgGap.innerHTML =
            `
            <span class="text-gray-500">
            -
            </span>
            `;


        }


    }



}

/* ==========================================================
   WIBEE AI BRIEFING
   /api/kpi + /api/woori
========================================================== */

async function fetchWibeeBriefing(){

    const [kpi, woori, changes] = await Promise.all([
        apiFetch("/api/kpi"),
        apiFetch("/api/woori"),
        apiFetch("/api/rate-changes")
    ]);

    if(!kpi || !woori){
        return;
    }

    renderWibeeBriefing(kpi, woori, changes || {});
}


function renderWibeeBriefing(kpi, woori, changes = {}){

    const status = document.getElementById("wibee-market-status");
    const judgementEl = document.getElementById("wibee-judgement");
    const riseEl = document.getElementById("wibee-rise-count");
    const fallEl = document.getElementById("wibee-fall-count");
    const changeEl = document.getElementById("wibee-change-count");
    const wooriRateEl = document.getElementById("wibee-woori-rate");
    const rankEl = document.getElementById("wibee-rank");
    const bestRateEl = document.getElementById("wibee-best-rate");
    const averageRateEl = document.getElementById("wibee-average-rate");

    const gap = Number(woori.average_gap ?? kpi.average_gap ?? 0);
    const changeCount = Number(
        changes.change_count ??
        changes.total_change_count ??
        kpi.change_count ??
        0
    );
    const riseCount = Number(
        changes.up_count ??
        changes.rise_count ??
        (Array.isArray(changes.up_all) ? changes.up_all.length : 0)
    );
    const fallCount = Number(
        changes.down_count ??
        changes.fall_count ??
        (Array.isArray(changes.down_all) ? changes.down_all.length : 0)
    );

    let marketStatus = "안정";
    let dotClass = "bg-emerald-500";
    let textClass = "text-emerald-600";

    if(changeCount >= 120){
        marketStatus = "변동 확대";
        dotClass = "bg-orange-500";
        textClass = "text-orange-600";
    }
    else if(changeCount >= 80){
        marketStatus = "변동 관찰";
        dotClass = "bg-amber-400";
        textClass = "text-amber-600";
    }

    if(status){
        status.className = `inline-flex items-center gap-1 ${textClass}`;
        status.innerHTML = `<span class="w-2 h-2 rounded-full ${dotClass}"></span>${marketStatus}`;
    }

    if(riseEl){ riseEl.textContent = Number.isFinite(riseCount) ? riseCount : 0; }
    if(fallEl){ fallEl.textContent = Number.isFinite(fallCount) ? fallCount : 0; }
    if(changeEl){ changeEl.textContent = Number.isFinite(changeCount) ? changeCount : 0; }

    const wooriRate = Number(woori.rate ?? woori.best_rate ?? 0);
    const bestRate = Number(kpi.max_rate ?? kpi.highest_rate ?? 0);
    const averageRate = Number(kpi.average_rate ?? kpi.avg_rate ?? 0);
    const rank = woori.market_rank ?? woori.rank ?? "-";
    const total = woori.market_total ?? woori.total ?? "-";

    if(wooriRateEl){
        wooriRateEl.textContent = Number.isFinite(wooriRate) && wooriRate > 0 ? `${wooriRate.toFixed(2)}%` : "-";
    }
    if(bestRateEl){
        bestRateEl.textContent = Number.isFinite(bestRate) && bestRate > 0 ? `${bestRate.toFixed(2)}%` : "-";
    }
    if(averageRateEl){
        averageRateEl.textContent = Number.isFinite(averageRate) && averageRate > 0 ? `${averageRate.toFixed(2)}%` : "-";
    }
    if(rankEl){
        rankEl.textContent = rank !== "-" ? `${rank}위 / ${total}` : "-";
    }

    if(judgementEl){
        let judgement = "시장 평균 수준의 금리 경쟁이 이어지고 있습니다.";
        if(gap < -0.20){
            judgement = "우리금융은 시장평균을 하회해 상위권과의 금리 격차 점검이 필요합니다.";
        }
        else if(gap < 0){
            judgement = "우리금융은 시장평균을 소폭 하회하며 최고금리 중심의 경쟁을 모니터링할 필요가 있습니다.";
        }
        else if(gap > 0.20){
            judgement = "우리금융은 시장평균을 뚜렷하게 상회하며 높은 금리 경쟁력을 유지하고 있습니다.";
        }
        else if(gap > 0){
            judgement = "우리금융은 시장평균을 소폭 상회하며 안정적인 금리 경쟁력을 유지하고 있습니다.";
        }
        judgementEl.textContent = judgement;
    }
}


/* ==========================================================
   TOP 10 RATE RANKING
   /api/rates
========================================================== */

async function fetchRatesData() {

    const select =
        document.getElementById(
            "top10-category-select"
        );

    let category = "ALL";

    if (select) {

        category =
            select.value;

    }

    const data =
        await apiFetch(
            `/api/rates?category=${category}`
        );

    if (!data) {
        return;
    }

    renderTop10(
        data.top10 || data
    );

}

function renderTop10(items) {

    const top5Body =
        document.getElementById(
            "top5-table-body"
        );

    const top10Body =
        document.getElementById(
            "top10-table-body"
        );

    if (!top5Body || !top10Body) {
        return;
    }

    top5Body.innerHTML = "";
    top10Body.innerHTML = "";

    if (!Array.isArray(items) || items.length === 0) {

        const emptyRow = `
        <tr>
            <td colspan="4" class="text-center py-4 text-gray-400">
                데이터 없음
            </td>
        </tr>
        `;

        top5Body.innerHTML = emptyRow;
        top10Body.innerHTML = emptyRow;
        return;
    }

    items
        .slice(0, 10)
        .forEach((item, index) => {

            const tr = document.createElement("tr");

            const bank =
                item.kor_co_nm ||
                item.bank_name ||
                item.bank ||
                "-";

            const rate =
                item.intr_rate2 ??
                item.max_rate ??
                item.intr_rate ??
                item.base_rate ??
                item.rate ??
                null;

            const rawDiff =
                item.diff ??
                item.change ??
                item.change_value ??
                0;

            const diffValue = Number(rawDiff);
            let diffHtml = '<span class="text-gray-400">-</span>';

            if(!Number.isNaN(diffValue) && diffValue > 0){
                diffHtml = `<span class="text-blue-600">+${diffValue.toFixed(2)}%p</span>`;
            }
            else if(!Number.isNaN(diffValue) && diffValue < 0){
                diffHtml = `<span class="text-red-500">▲${Math.abs(diffValue).toFixed(2)}%p</span>`;
            }
            else if(typeof rawDiff === "string" && rawDiff.trim() && rawDiff !== "-"){
                diffHtml = rawDiff;
            }

            const isWoori = String(bank).includes("우리금융");

            if(isWoori){
                tr.className = "bg-blue-50/80 font-bold text-blue-700 [box-shadow:inset_0_0_0_1px_#bfdbfe]";
            }

            const rankClass = index < 3
                ? "bg-orange-100 text-orange-600"
                : isWoori
                    ? "bg-blue-600 text-white"
                    : "bg-gray-100 text-gray-600";

            tr.innerHTML = `
            <td class="py-2 text-center">
                <span class="${rankClass} w-4 h-4 rounded-full inline-flex items-center justify-center text-[10px] font-bold">
                    ${index + 1}
                </span>
            </td>
            <td class="py-2 text-center truncate px-1" title="${bank}">${bank}</td>
            <td class="py-2 text-center font-semibold ${isWoori ? "text-blue-700" : "text-blue-600"}">
                ${rate !== null && !Number.isNaN(Number(rate)) ? Number(rate).toFixed(2) + "%" : "-"}
            </td>
            <td class="py-2 text-center font-semibold whitespace-nowrap">
                ${diffHtml}
            </td>
            `;

            if (index < 5) {
                top5Body.appendChild(tr);
            }
            else {
                top10Body.appendChild(tr);
            }

        });
}



/* ==========================================================
   시장 전체 순위 MODAL
========================================================== */

async function openAllRatesModal(){

    const modal = document.getElementById("top10-all-modal");
    const tbody = document.getElementById("top10-all-table-body");

    if(!modal || !tbody){
        return;
    }

    modal.classList.remove("hidden");
    modal.classList.add("flex");

    tbody.innerHTML = `
        <tr>
            <td colspan="5" class="py-6 text-center text-gray-400">
                전체 순위를 불러오는 중입니다.
            </td>
        </tr>
    `;

    const data = activeMarketProduct==="deposit" ? await apiFetch("/api/rates?all=1") : currentMarketItems;
    const items = activeMarketProduct==="deposit"
        ? (Array.isArray(data)?data:[])
        : validRateItems(data).sort((a,b)=>Number(b.rate)-Number(a.rate));

    if(items.length === 0){
        tbody.innerHTML = `
            <tr>
                <td colspan="5" class="py-6 text-center text-gray-400">
                    순위 데이터가 없습니다.
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = "";

    items.forEach((item, index) => {

        const bank = item.bank || item.bank_name || item.kor_co_nm || "-";
        const product = item.product || item.product_name || item.fin_prdt_nm || "-";
        const rate = Number(item.rate ?? item.max_rate ?? item.intr_rate2);
        const change = Number(item.change ?? item.diff ?? 0);
        const isWoori = String(bank).includes("우리금융");

        let changeHtml = '<span class="text-gray-400">-</span>';
        if(Number.isFinite(change) && change > 0){
            changeHtml = `<span class="text-blue-600">+${change.toFixed(2)}%p</span>`;
        }
        else if(Number.isFinite(change) && change < 0){
            changeHtml = `<span class="text-red-500">▲${Math.abs(change).toFixed(2)}%p</span>`;
        }

        const tr = document.createElement("tr");
        if(isWoori){
            tr.className = "bg-blue-50/80 font-bold text-blue-700 [box-shadow:inset_0_0_0_1px_#bfdbfe]";
        }

        tr.innerHTML = `
            <td class="py-2 text-center">${item.rank ?? index + 1}</td>
            <td class="py-2 text-center ${isWoori ? "font-bold text-blue-700" : "text-gray-700"}">${bank}</td>
            <td class="py-2 text-center text-gray-500 truncate" title="${product}">${product}</td>
            <td class="py-2 text-right font-semibold ${isWoori ? "text-blue-700" : "text-gray-800"}">${Number.isFinite(rate) ? rate.toFixed(2) + "%" : "-"}</td>
            <td class="py-2 text-right whitespace-nowrap">${changeHtml}</td>
        `;

        tbody.appendChild(tr);
    });
}

function closeAllRatesModal(){
    const modal = document.getElementById("top10-all-modal");
    if(!modal){
        return;
    }
    modal.classList.add("hidden");
    modal.classList.remove("flex");
}

document.addEventListener("click", function(e){
    if(e.target.closest("#top10-all-btn")){
        openAllRatesModal();
        return;
    }

    if(e.target.closest("#top10-all-close")){
        closeAllRatesModal();
        return;
    }

    const modal = document.getElementById("top10-all-modal");
    if(modal && e.target === modal){
        closeAllRatesModal();
    }
});





/* ==========================================================
   상승 / 하락 TOP5
   /api/financial
========================================================== */


async function fetchFinancialData(){

    // V6: 백엔드 전용 변동 API를 우선 사용
    const data = await apiFetch(
        "/api/rate-changes"
    );

    if(data){

        const upList = Array.isArray(data.up_top5)
            ? data.up_top5
            : [];

        const downList = Array.isArray(data.down_top5)
            ? data.down_top5
            : [];

        console.log(
            "RATE CHANGE API",
            data
        );

        renderRateChanges(
            upList,
            downList
        );

        return;
    }

    // API 실패 시 기존 /api/rates 결과를 이용한 최소 fallback
    const rates = await apiFetch(
        "/api/rates?all=1"
    );

    const items = Array.isArray(rates)
        ? rates
        : [];

    const normalized = items
        .map(item => ({
            ...item,
            change_value: Number(item.change ?? 0)
        }))
        .filter(item => Number.isFinite(item.change_value));

    const upList = normalized
        .filter(item => item.change_value > 0)
        .sort((a,b) => b.change_value - a.change_value)
        .slice(0,5);

    const downList = normalized
        .filter(item => item.change_value < 0)
        .sort((a,b) => a.change_value - b.change_value)
        .slice(0,5);

    renderRateChanges(
        upList,
        downList
    );
}

function renderRateChanges(
    upList,
    downList
){

    const up = document.getElementById("rates-up-list");
    const down = document.getElementById("rates-down-list");

    const renderRows = (target, list, direction) => {

        if(!target){
            return;
        }

        target.innerHTML = "";

        if(!Array.isArray(list) || list.length === 0){
            target.innerHTML = `
            <tr>
                <td colspan="4" class="py-4 text-center text-gray-400 font-normal">
                    ${direction === "up" ? "금리 상승 없음" : "금리 하락 없음"}
                </td>
            </tr>
            `;
            return;
        }

        list.slice(0, 5).forEach((item, index) => {

            const bank =
                item.kor_co_nm ||
                item.bank_name ||
                item.bank ||
                "-";

            const currentRateRaw =
                item.rate ??
                item.current_rate ??
                item.new_rate ??
                item.intr_rate2 ??
                item.max_rate ??
                null;

            const currentRate = Number(currentRateRaw);

            let value = Number(
                item.change_value ??
                item.change ??
                ((Number(item.new_rate) || 0) - (Number(item.old_rate) || 0))
            );

            if(Number.isNaN(value)){
                value = 0;
            }

            const absValue = Math.abs(value).toFixed(2);
            const tr = document.createElement("tr");

            const isWoori = String(bank).includes("우리금융");
            if(isWoori){
                tr.className = "bg-blue-50/80 font-bold text-blue-700 [box-shadow:inset_0_0_0_1px_#bfdbfe]";
            }

            tr.innerHTML = `
                <td class="py-2 text-center ${isWoori ? "text-blue-700" : "text-gray-500"}">${index + 1}</td>
                <td class="py-2 text-center px-1 ${isWoori ? "text-blue-700 font-bold" : "text-gray-700"} truncate" title="${bank}">${bank}</td>
                <td class="py-2 text-center text-xs font-semibold whitespace-nowrap ${isWoori ? "text-blue-700" : "text-gray-700"}">
                    ${Number.isFinite(currentRate) ? currentRate.toFixed(2) + "%" : "-"}
                </td>
                <td class="py-2 text-center text-xs font-semibold whitespace-nowrap ${isWoori ? "text-blue-700 font-bold" : (direction === "up" ? "text-blue-600" : "text-red-500")}">
                    ${direction === "up" ? "+" : "▲"}${absValue}%p
                </td>
            `;

            target.appendChild(tr);
        });
    };

    renderRows(up, upList, "up");
    renderRows(down, downList, "down");
}




/* ==========================================================
   전체 상품 조회 - V5 실제 데이터 연결
   /api/products
========================================================== */

let allProductData = [];

function productBankName(item){
    return String(item.bank ?? item.kor_co_nm ?? item.bank_name ?? "").trim();
}

function productName(item){
    return String(item.product ?? item.fin_prdt_nm ?? item.product_name ?? "").trim();
}

function productPeriod(item){
    const raw = item.period ?? item.save_trm ?? item.period_months ?? "";
    const match = String(raw).match(/\d+/);
    return match ? match[0] : String(raw || "");
}

function productRate(item){
    const raw = item.rate ?? item.intr_rate2 ?? item.max_rate ?? item.intr_rate ?? item.base_rate;
    const value = Number(raw);
    return Number.isFinite(value) ? value : null;
}

function productChange(item){
    const raw = item.change ?? item.diff ?? item.change_value;
    const value = Number(raw);
    return Number.isFinite(value) ? value : 0;
}

async function fetchAllProducts(){
    const data = await apiFetch("/api/products");
    if(!data){
        renderAllProductsTable([]);
        return;
    }

    allProductData = Array.isArray(data)
        ? data
        : (data.products || data.all_products || data.items || []);

    populateProductBankSelect(allProductData);
    applyProductFilters();
}

function populateProductBankSelect(products){
    const select = document.getElementById("product-bank-select");
    if(!select || select.dataset.loaded === "1") return;

    const banks = [...new Set(products.map(productBankName).filter(Boolean))]
        .sort((a,b) => a.localeCompare(b, "ko"));

    banks.forEach(bank => {
        const option = document.createElement("option");
        option.value = bank;
        option.textContent = bank;
        select.appendChild(option);
    });
    select.dataset.loaded = "1";
}

function applyProductFilters(){
    const bank = document.getElementById("product-bank-select")?.value?.trim() || "";
    const period = document.getElementById("product-period-select")?.value?.trim() || "";
    const sortMode = document.getElementById("product-sort-select")?.value || "rate_desc";
    const keyword = document.getElementById("product-search-input")?.value?.trim().toLowerCase() || "";

    let filtered = [...allProductData];
    if(bank) filtered = filtered.filter(item => productBankName(item) === bank);
    if(period) filtered = filtered.filter(item => productPeriod(item) === period);
    if(keyword){
        filtered = filtered.filter(item => `${productBankName(item)} ${productName(item)}`.toLowerCase().includes(keyword));
    }

    filtered.sort((a,b) => {
        if(sortMode === "rate_asc"){
            const diff =
                (productRate(a) ?? Number.MAX_VALUE)
                - (productRate(b) ?? Number.MAX_VALUE);

            return diff !== 0
                ? diff
                : productBankName(a).localeCompare(
                    productBankName(b),
                    "ko"
                );
        }

        if(sortMode === "change_desc"){
            const diff =
                Math.abs(productChange(b))
                - Math.abs(productChange(a));

            return diff !== 0
                ? diff
                : (productRate(b) ?? -1)
                    - (productRate(a) ?? -1);
        }

        if(sortMode === "disclosure_desc"){
            const diff=disclosureSortValue(b.disclosure_date)-disclosureSortValue(a.disclosure_date);
            return diff!==0?diff:(productRate(b)??-1)-(productRate(a)??-1);
        }

        if(sortMode === "bank_asc"){
            const bankDiff =
                productBankName(a).localeCompare(
                    productBankName(b),
                    "ko"
                );

            return bankDiff !== 0
                ? bankDiff
                : (productRate(b) ?? -1)
                    - (productRate(a) ?? -1);
        }

        // 기본: 금리 높은순
        // ISA/IRP 확장 시 disclosure_date 최신순 모드를
        // 이 정렬 구조에 추가할 수 있도록 분리해 둠.
        const diff =
            (productRate(b) ?? -1)
            - (productRate(a) ?? -1);

        return diff !== 0
            ? diff
            : productBankName(a).localeCompare(
                productBankName(b),
                "ko"
            );
    });
    renderAllProductsTable(filtered);
}

function renderAllProductsTable(products){
    const tbody=document.getElementById("all-products-table-body");
    const count=document.getElementById("product-result-count");
    if(count)count.textContent=`${Number(products.length).toLocaleString()}개 조회`;
    if(!tbody)return; tbody.innerHTML="";
    if(!Array.isArray(products)||!products.length){tbody.innerHTML='<tr><td colspan="6" class="py-6 text-center text-gray-400">조회 결과가 없습니다.</td></tr>';return;}
    products.forEach((item,index)=>{
        const bank=productBankName(item)||"-", displayBank=displayBankName(bank);
        const rawProduct=productName(item);
        const product=rawProduct || (activeMarketProduct==="irp" ? "상품명 미수집" : "-");
        const period=productPeriod(item), rate=productRate(item), change=productChange(item), isW=bank.includes("우리금융");
        let last='<span class="text-gray-400">-</span>';
        if(activeMarketProduct==="deposit"){
            if(change>0)last=`<span class="text-blue-600 font-semibold">+${change.toFixed(2)}%p</span>`;
            else if(change<0)last=`<span class="text-red-600 font-semibold">▲${Math.abs(change).toFixed(2)}%p</span>`;
            else last='<span class="text-gray-700">0.00%p</span>';
        }else{
            const disclosure = formatDisclosureDate(item.disclosure_date || item.rate_month);
            last=disclosure?`<span class="${isW ? "text-blue-700 font-bold" : "text-gray-600"}">${disclosure}</span>`:'<span class="text-gray-400">-</span>';
        }
        const tr=document.createElement("tr"); if(isW)tr.className="bg-blue-50/70 font-bold text-blue-700";
        tr.innerHTML=`<td class="py-2 text-center">${index+1}</td><td class="py-2 text-center truncate px-1" title="${bank}">${displayBank}</td><td class="py-2 text-center truncate px-4" title="${product}">${product}</td><td class="py-2 text-center">${period?`${period}개월`:"-"}</td><td class="py-2 text-center font-semibold">${rate!=null?rate.toFixed(2)+"%":"-"}</td><td class="py-2 text-center whitespace-nowrap">${last}</td>`;
        tbody.appendChild(tr);
    });
}


function setupProductSearch(){
    const input = document.getElementById("product-search-input");
    const button = document.getElementById("product-search-btn");
    const bankSelect = document.getElementById("product-bank-select");
    const periodSelect = document.getElementById("product-period-select");
    const sortSelect = document.getElementById("product-sort-select");

    if(input){
        input.addEventListener("keydown", e => {
            if(e.key === "Enter"){
                e.preventDefault();
                applyProductFilters();
            }
        });
    }
    if(button) button.addEventListener("click", applyProductFilters);
    if(bankSelect) bankSelect.addEventListener("change", applyProductFilters);
    if(periodSelect) periodSelect.addEventListener("change", async()=>{
        currentMarketPeriod=periodSelect.value||"12";
        updateMarketProductLabels();
        updateAlternativeHeaders();
        if(activeMarketProduct==="deposit"){
            applyProductFilters();
        }else{
            const requestId=++marketModeRequestId;
            await loadAlternativeMarket(activeMarketProduct,requestId);
        }
    });
    if(sortSelect) sortSelect.addEventListener("change", applyProductFilters);
}


/* ==========================================================
   AI 분석센터 V5 - 4탭 실제 데이터 연결
========================================================== */

let aiCenterActiveTab = "market";

function aiCenterRate(value){
    const n = Number(value);
    return Number.isFinite(n) ? `${n.toFixed(2)}%` : "-";
}

function aiCenterGap(value){
    const n = Number(value);
    if(!Number.isFinite(n)) return '<span class="text-gray-500">-</span>';
    if(n > 0) return `<span class="text-blue-600 font-bold">+${n.toFixed(2)}%p</span>`;
    if(n < 0) return `<span class="text-red-600 font-bold">▲${Math.abs(n).toFixed(2)}%p</span>`;
    return '<span class="text-gray-800 font-bold">0.00%p</span>';
}

function aiCenterChange(value){
    const n = Number(value);
    if(!Number.isFinite(n)) return '<span class="text-gray-400">-</span>';
    if(n > 0) return `<span class="text-blue-600 font-semibold">+${n.toFixed(2)}%p</span>`;
    if(n < 0) return `<span class="text-red-600 font-semibold">▲${Math.abs(n).toFixed(2)}%p</span>`;
    return '<span class="text-gray-700 font-semibold">0.00%p</span>';
}


function escapeReportHtml(value){
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function closeAIExecutiveReport(){
    const modal = document.getElementById("ai-report-modal");
    if(!modal){
        return;
    }

    modal.classList.add("hidden");
    modal.classList.remove("flex");
}

function reportSourceLabel(mode){
    return mode === "deposit"
        ? "저축은행중앙회 비교공시"
        : "각 저축은행 공식 공시·상품 페이지";
}

function reportDisclosureValue(item){
    return formatDisclosureDate(item?.disclosure_date || item?.rate_month) || "-";
}

function reportMovementRows(data){
    if(data.mode === "deposit"){
        const ups = Array.isArray(data.changes?.up_top5) ? data.changes.up_top5 : [];
        const downs = Array.isArray(data.changes?.down_top5) ? data.changes.down_top5 : [];

        return [...ups,...downs]
            .sort((a,b)=>Math.abs(Number(b.change ?? b.change_value ?? 0))-Math.abs(Number(a.change ?? a.change_value ?? 0)))
            .slice(0,5)
            .map((item,index)=>({
                ...item,
                rank:index+1
            }));
    }

    return Array.isArray(data.changes?.recent_disclosures)
        ? data.changes.recent_disclosures.slice(0,5)
        : [];
}

function buildExecutiveReportBase(data, dataBasis){
    const {kpi, woori, rates, financial, changes, mode} = data;

    const reportRates = Array.isArray(rates) ? rates : [];
    const reportFinancial = Array.isArray(financial) ? financial : [];
    const top = reportRates[0] || {};
    const movementRows = reportMovementRows(data);

    const marketAvg = Number(kpi.average_rate);
    const topRate = Number(top.rate ?? kpi.max_rate ?? kpi.highest_rate);
    const lowRate = Number(kpi.lowest_rate);
    const wooriRate = Number(woori.rate);

    const marketSpread =
        Number.isFinite(topRate) && Number.isFinite(marketAvg)
            ? topRate - marketAvg
            : null;

    const wooriToTop =
        Number.isFinite(wooriRate) && Number.isFinite(topRate)
            ? wooriRate - topRate
            : null;

    const avgGap =
        Number.isFinite(wooriRate) && Number.isFinite(marketAvg)
            ? wooriRate - marketAvg
            : null;

    const top5Boundary =
        reportRates[4] && Number.isFinite(Number(reportRates[4].rate))
            ? Number(reportRates[4].rate)
            : null;

    const top5Gap =
        Number.isFinite(wooriRate) && Number.isFinite(top5Boundary)
            ? wooriRate - top5Boundary
            : null;

    const higherCount =
        Number.isFinite(wooriRate)
            ? reportRates.filter(item=>Number(item.rate) > wooriRate).length
            : null;

    const changeCount = Number(changes.change_count ?? kpi.change_count ?? 0);
    const upCount = Number(changes.up_count ?? 0);
    const downCount = Number(changes.down_count ?? 0);

    const movementSummary =
        mode === "deposit"
            ? `변동 ${changeCount}건 · 상승 ${upCount} / 하락 ${downCount}`
            : `최근 공시 ${movementRows.length}건`;

    const movementTitle =
        mode === "deposit"
            ? "최근 금리 변동"
            : "최근 공시 현황";

    const reportSource =
        reportSourceLabel(mode);

    const sourceCount =
        mode === "deposit"
            ? "-"
            : reportRates.filter(item=>item.source || item.source_url || item.url).length;

    const financialWooriIndex =
        reportFinancial.findIndex(item=>String(item.bank || "").includes("우리금융"));

    const monitorPoints = [
        top5Gap === null
            ? "TOP5 경계 금리 데이터를 확인합니다."
            : `TOP5 경계 금리 ${aiCenterRate(top5Boundary)}와 우리금융의 단순 금리차 ${top5Gap >= 0 ? "+" : ""}${top5Gap.toFixed(2)}%p를 모니터링합니다.`,
        mode === "deposit"
            ? `전일 변동 ${changeCount}건 중 상위금리권 조정 여부를 우선 확인합니다.`
            : "최근 공시일이 갱신된 상위기관의 금리 재조정 여부를 우선 확인합니다.",
        reportFinancial.length
            ? `금융지주계 저축은행 내 우리금융 순위 ${financialWooriIndex >= 0 ? financialWooriIndex+1 : "-"}위와 선두사 Gap을 확인합니다.`
            : "금융지주계 비교 데이터의 추가 확보 여부를 확인합니다."
    ];

    return `
      <div id="executive-report-document" class="space-y-3 bg-white">

        <div class="rounded-xl overflow-hidden border border-blue-100">
          <div class="bg-gradient-to-r from-[#0b4ea2] to-[#1a67d2] text-white px-4 py-3 flex items-end justify-between gap-4">
            <div>
              <div class="text-[10px] text-blue-100 tracking-[0.12em]">EXECUTIVE INTELLIGENCE</div>
              <div class="text-[17px] font-bold mt-0.5">SBRateBot ${marketProductLabel()} AI Market Analysis Report</div>
              <div class="text-[10px] text-blue-100 mt-1">${marketProductLabel()} ${currentSelectedPeriod()}개월 · 우리금융 수신시장 경쟁력 분석</div>
            </div>
            <div class="text-right text-[10px] leading-4 text-blue-100">
              <div>데이터 업데이트 시간 ${dataBasis}</div>
              <div>생성 ${formatKoreanCurrentDateTime(new Date())}</div>
            </div>
          </div>

          <div class="grid grid-cols-4 gap-2 p-3 bg-[#fbfdff] text-center">
            <div class="er-metric bg-blue-50 border-blue-100">
              <div class="er-metric-label text-blue-600">우리금융</div>
              <div class="er-metric-value text-blue-700">${aiCenterRate(wooriRate)}</div>
            </div>
            <div class="er-metric">
              <div class="er-metric-label">시장 최고</div>
              <div class="er-metric-value text-blue-700">${aiCenterRate(topRate)}</div>
            </div>
            <div class="er-metric">
              <div class="er-metric-label">시장 평균</div>
              <div class="er-metric-value">${aiCenterRate(marketAvg)}</div>
            </div>
            <div class="er-metric">
              <div class="er-metric-label">시장 순위</div>
              <div class="er-metric-value">${woori.market_rank ?? "-"}위</div>
            </div>
          </div>
        </div>

        <section class="er-section">
          <div class="er-title"><span>01 · Executive Summary</span><span class="text-[9px] text-blue-600">TODAY</span></div>
          <div class="er-body space-y-2">
            <div class="er-insight">
              <b>${displayBankName(top.bank ?? "-")}</b>가 ${aiCenterRate(topRate)}로 시장 상단을 형성하고 있으며
              시장 평균은 ${aiCenterRate(marketAvg)}입니다.
              우리금융은 ${aiCenterRate(wooriRate)}로 시장 ${woori.market_rank ?? "-"}위입니다.
            </div>
            <div class="er-insight">
              우리금융보다 높은 금리 기관은 ${higherCount ?? "-"}개이며,
              TOP5 경계와의 단순 금리차는 ${top5Gap === null ? "-" : (top5Gap >= 0 ? "+" : "") + top5Gap.toFixed(2) + "%p"}입니다.
              ${movementSummary}.
            </div>
          </div>
        </section>

        <section class="er-section">
          <div class="er-title"><span>02 · Market Snapshot</span><span>${woori.market_total ?? reportRates.length}개 기관</span></div>
          <div class="er-body grid grid-cols-2 gap-x-5 gap-y-1.5 text-[11px]">
            <div class="flex justify-between"><span class="text-gray-500">시장 최고</span><b>${displayBankName(top.bank ?? "-")} ${aiCenterRate(topRate)}</b></div>
            <div class="flex justify-between"><span class="text-gray-500">시장 평균</span><b>${aiCenterRate(marketAvg)}</b></div>
            <div class="flex justify-between"><span class="text-gray-500">시장 최저</span><b>${Number.isFinite(lowRate) ? aiCenterRate(lowRate) : "-"}</b></div>
            <div class="flex justify-between"><span class="text-gray-500">${mode === "deposit" ? "금리 변동" : "공시 현황"}</span><b>${movementSummary}</b></div>
          </div>
        </section>

        <section class="er-section">
          <div class="er-title"><span>03 · Woori Market Position</span><span class="text-blue-600">${woori.market_rank ?? "-"}위</span></div>
          <div class="er-body grid grid-cols-2 gap-x-5 gap-y-1.5 text-[11px]">
            <div class="flex justify-between"><span class="text-gray-500">우리금융 금리</span><b class="text-blue-700">${aiCenterRate(wooriRate)}</b></div>
            <div class="flex justify-between"><span class="text-gray-500">시장 최고 대비</span><b>${wooriToTop === null ? "-" : aiCenterGap(wooriToTop)}</b></div>
            <div class="flex justify-between"><span class="text-gray-500">시장 평균 대비</span><b>${avgGap === null ? "-" : aiCenterGap(avgGap)}</b></div>
            <div class="flex justify-between"><span class="text-gray-500">우리보다 높은 기관</span><b>${higherCount ?? "-"}개</b></div>
            <div class="flex justify-between"><span class="text-gray-500">TOP5 경계</span><b>${top5Boundary === null ? "-" : aiCenterRate(top5Boundary)}</b></div>
            <div class="flex justify-between"><span class="text-gray-500">금융지주 순위</span><b>${financialWooriIndex >= 0 ? financialWooriIndex+1 : "-"}위</b></div>
          </div>
        </section>

        <section class="er-section">
          <div class="er-title"><span>04 · Competitive Landscape</span><span>TOP10</span></div>
          <div class="er-body pt-1">
            <div class="grid grid-cols-[34px_1fr_72px_88px] gap-2 px-2 py-1 text-[9px] text-gray-400">
              <span>순위</span><span>저축은행</span><span class="text-right">금리</span><span class="text-right">${mode === "deposit" ? "전일比" : "공시일"}</span>
            </div>
            ${reportRates.slice(0,10).map((item,index)=>{
                const isWoori = String(item.bank || "").includes("우리금융");
                const last =
                    mode === "deposit"
                        ? aiCenterChange(item.change)
                        : reportDisclosureValue(item);
                return `<div class="grid grid-cols-[34px_1fr_72px_88px] gap-2 px-2 py-1.5 text-[10px] border-b border-gray-50 ${isWoori ? "bg-blue-50 text-blue-700 font-bold rounded-md border border-blue-200" : ""}">
                  <span>${item.rank ?? index+1}</span>
                  <span>${displayBankName(item.bank ?? "-")}</span>
                  <span class="text-right font-semibold">${aiCenterRate(item.rate)}</span>
                  <span class="text-right">${last}</span>
                </div>`;
            }).join("")}
          </div>
        </section>

        <section class="er-section">
          <div class="er-title"><span>05 · Financial Group Peers</span><span>${reportFinancial.length}개</span></div>
          <div class="er-body pt-1">
            ${reportFinancial.slice(0,8).map((item,index)=>{
                const isWoori = String(item.bank || "").includes("우리금융");
                const last =
                    mode === "deposit"
                        ? aiCenterChange(item.change)
                        : reportDisclosureValue(item);
                return `<div class="grid grid-cols-[34px_1fr_72px_88px] gap-2 px-2 py-1.5 text-[10px] border-b border-gray-50 ${isWoori ? "bg-blue-50 text-blue-700 font-bold rounded-md border border-blue-200" : ""}">
                  <span>${item.rank ?? index+1}</span>
                  <span>${displayBankName(item.bank ?? "-")}</span>
                  <span class="text-right font-semibold">${aiCenterRate(item.rate)}</span>
                  <span class="text-right">${last}</span>
                </div>`;
            }).join("") || '<div class="text-center text-gray-400 py-3">금융지주계 비교 데이터 없음</div>'}
          </div>
        </section>

        <section class="er-section">
          <div class="er-title"><span>06 · ${movementTitle}</span><span>${movementSummary}</span></div>
          <div class="er-body pt-1">
            ${movementRows.map((item,index)=>{
                const c = Number(item.change ?? item.change_value ?? 0);
                const last =
                    mode === "deposit"
                        ? (c > 0 ? `<span class="text-blue-600 font-bold">+${Math.abs(c).toFixed(2)}%p</span>` : c < 0 ? `<span class="text-red-600 font-bold">▲${Math.abs(c).toFixed(2)}%p</span>` : "-")
                        : reportDisclosureValue(item);
                return `<div class="grid grid-cols-[34px_1fr_72px_88px] gap-2 px-2 py-1.5 text-[10px] border-b border-gray-50 ${String(item.bank || "").includes("우리금융") ? "bg-blue-50 text-blue-700 font-bold rounded-md border border-blue-200" : ""}">
                  <span>${item.rank ?? index+1}</span>
                  <span>${displayBankName(item.bank ?? "-")}</span>
                  <span class="text-right font-semibold">${aiCenterRate(item.rate)}</span>
                  <span class="text-right">${last}</span>
                </div>`;
            }).join("") || '<div class="text-center text-gray-400 py-3">변동·공시 데이터 없음</div>'}
          </div>
        </section>

        <section id="executive-report-ai-section" class="er-section">
          <div class="er-title"><span>07 · AI Management Insight</span><span class="text-indigo-600">AI</span></div>
          <div class="er-body">
            <div id="executive-report-ai-text" class="text-gray-500 leading-[1.5]">
              AI 시장분석 판단을 생성하고 있습니다...
            </div>
          </div>
        </section>

        <section class="er-section">
          <div class="er-title"><span>08 · Key Monitoring Points</span><span>ACTION</span></div>
          <div class="er-body text-[11px]">
            <ol class="list-decimal pl-5 space-y-1">
              ${monitorPoints.map(point=>`<li>${point}</li>`).join("")}
            </ol>
          </div>
        </section>

        <section class="er-section">
          <div class="er-title"><span>09 · Data Source & Notes</span><span>TRUST</span></div>
          <div class="er-body text-[10px] leading-5">
            <div class="rounded-lg bg-gray-50 border border-gray-100 p-3">
              <div><b>출처</b> · ${reportSource}</div>
              <div><b>데이터 업데이트 시간</b> · ${dataBasis}</div>
              <div><b>원문 링크 보유</b> · ${sourceCount}건</div>
              <div class="mt-1 text-gray-500">
                공시일은 개별 기관의 공식 공시 기준입니다. 금리 미확인 값은 0%로 해석하지 않고 '-'로 표시합니다.
                순위·금리·Gap·공시일 등 수치는 SBRateBot 수집 데이터로 계산하며 AI는 제공된 수치의 해석에만 사용됩니다.
              </div>
            </div>
          </div>
        </section>
      </div>`;
}

async function openAIExecutiveReport(){
    const modal = document.getElementById("ai-report-modal");
    const content = document.getElementById("ai-report-content");

    if(!modal || !content) return;

    modal.classList.remove("hidden");
    modal.classList.add("flex");

    const dataBasis = formatDataBasis(window.sbDataBasisValue);
    const data = await loadAIAnalysisCenterData();

    // AI 응답과 무관하게 실제 API 데이터로 보고서 본문을 먼저 생성
    content.innerHTML = buildExecutiveReportBase(data, dataBasis);

    const basisEl = document.getElementById("ai-report-data-basis");
    if(basisEl) basisEl.textContent = `데이터 업데이트 기준 ${dataBasis}`;

    const top5Boundary = data.rates?.[4]?.rate ?? null;
    const higherCount = Number.isFinite(Number(data.woori.rate))
        ? (data.rates || []).filter(item=>Number(item.rate) > Number(data.woori.rate)).length
        : null;

    const question =
        `데이터 업데이트 기준 ${dataBasis}. ${marketProductLabel()} ${currentSelectedPeriod()}개월 AI 보고서의 AI Management Insight를 작성해줘.
반드시 아래 제공 데이터만 사용하고 새로운 숫자를 만들거나 추정하지 마.
우리금융 금리 ${data.woori.rate ?? "-"}%, 시장순위 ${data.woori.market_rank ?? "-"}위, 시장 최고 ${data.kpi.max_rate ?? data.kpi.highest_rate ?? "-"}%, 시장 평균 ${data.kpi.average_rate ?? "-"}%, TOP5 경계 ${top5Boundary ?? "-"}%, 우리금융보다 높은 기관 ${higherCount ?? "-"}개.
금융지주계 데이터: ${JSON.stringify((data.financial || []).slice(0,8))}.
${data.mode === "deposit" ? `변동 데이터: ${JSON.stringify(data.changes || {})}` : `최근 공시 데이터: ${JSON.stringify(reportMovementRows(data))}`}.
다음 순서로 간결하지만 전문적으로 작성해줘:
① 시장상황 2문장
② 우리금융 경쟁력 2문장
③ 핵심 리스크·기회 2문장
④ 대응 및 모니터링 포인트 3개.
일반론은 제외하고 ${marketProductLabel()} 데이터에 근거해 작성해줘.`;

    try{
        const response = await fetch("/api/ai/search", {
            method: "POST",
            headers: {"Content-Type":"application/json"},
            body: JSON.stringify({
                question,
                category: activeMarketProduct,
                period: currentSelectedPeriod()
            })
        });

        if(!response.ok) throw new Error(`AI Report API Error : ${response.status}`);

        const result = await response.json();
        const answer = result?.answer || result?.result || result?.response || result?.message || "";
        const aiText = document.getElementById("executive-report-ai-text");

        if(aiText){
            const compactAnswer = String(answer || "")
                .replace(/\r\n/g, "\n")
                .replace(/\n{3,}/g, "\n\n")
                .trim();

            aiText.textContent = compactAnswer || "AI 추가 판단이 없어 데이터 기반 보고서만 표시합니다.";
            aiText.className = compactAnswer
                ? "text-gray-700 whitespace-pre-line leading-[1.45]"
                : "text-gray-500";
        }
    }
    catch(error){
        console.error("AI REPORT ERROR:", error);
        const aiText = document.getElementById("executive-report-ai-text");
        if(aiText){
            aiText.textContent = "AI 추가 판단을 불러오지 못했습니다. 위 데이터 기반 보고서는 정상적으로 사용할 수 있습니다.";
            aiText.className = "text-gray-500";
        }
    }
}

function printExecutiveReport(){
    const report = document.getElementById("executive-report-document");
    if(!report) return;

    const popup = window.open("", "_blank", "width=900,height=1000");
    if(!popup) return;

    popup.document.write(`
      <!doctype html>
      <html lang="ko">
      <head>
        <meta charset="utf-8">
        <title>SBRateBot AI Market Analysis Report</title>
        <script src="https://cdn.tailwindcss.com"><\/script>
        <style>
          body{font-family:Arial,"Noto Sans KR",sans-serif;padding:32px;color:#1f2937}
          @media print{body{padding:0}}
        </style>
      </head>
      <body>${report.outerHTML}</body>
      </html>
    `);
    popup.document.close();
    popup.focus();
    setTimeout(() => popup.print(), 700);
}

async function downloadExecutiveReportPDF(){
    const report = document.getElementById("executive-report-document");
    if(!report) return;

    const basis = formatDataBasis(window.sbDataBasisValue).replace(/[: ]/g, "-");
    const filename = `SBRateBot_Executive_Report_${basis}.pdf`;

    if(typeof html2pdf === "undefined"){
        alert("PDF 모듈을 불러오지 못했습니다. 출력 버튼에서 'PDF로 저장'을 선택해주세요.");
        printExecutiveReport();
        return;
    }

    const options = {
        margin: [8,8,8,8],
        filename,
        image: {type:"jpeg", quality:0.98},
        html2canvas: {scale:2, useCORS:true, backgroundColor:"#ffffff"},
        jsPDF: {unit:"mm", format:"a4", orientation:"portrait"},
        pagebreak: {mode:["avoid-all","css","legacy"]}
    };

    await html2pdf().set(options).from(report).save();
}


function closeAICenterDetail(){
    const modal = document.getElementById("ai-center-detail-modal");
    if(modal){
        modal.classList.add("hidden");
        modal.classList.remove("flex");
    }
}

function centerDetailFallback(tab, data){
    const {kpi, woori, rates, financial, changes} = data;

    if(activeMarketProduct !== "deposit"){
        const label = marketProductLabel();
        const collectedBanks = [...new Set(
            currentMarketItems
                .map(item => String(item.bank || "").trim())
                .filter(Boolean)
        )];

        if(tab === "financial"){
            const leader = financial[0] || {};
            const gapToLeader =
                Number.isFinite(Number(leader.rate)) &&
                Number.isFinite(Number(woori.rate))
                    ? Number(woori.rate) - Number(leader.rate)
                    : null;

            return `
              <div class="space-y-3">
                <div class="font-bold text-blue-700">${label} 금융지주 저축은행 심층 분석</div>
                <div class="grid grid-cols-3 gap-2 text-center">
                  <div class="bg-gray-50 rounded-xl p-3"><div class="text-[10px] text-gray-400">우리금융 금리</div><div class="font-bold">${aiCenterRate(woori.rate)}</div></div>
                  <div class="bg-gray-50 rounded-xl p-3"><div class="text-[10px] text-gray-400">시장순위</div><div class="font-bold">${woori.market_rank ?? "-"}위</div></div>
                  <div class="bg-gray-50 rounded-xl p-3"><div class="text-[10px] text-gray-400">공시일</div><div class="font-bold text-[11px]">${woori.disclosure_date || "-"}</div></div>
                </div>
                <div class="bg-blue-50 border border-blue-100 rounded-xl p-3">
                  ${label} 기준 금융지주 선두 대비 격차는 ${gapToLeader === null ? "-" : aiCenterGap(gapToLeader)}이며,
                  우리금융의 시장 평균 대비 수준은 ${aiCenterGap(woori.average_gap)}입니다.
                </div>
              </div>`;
        }

        if(tab === "change"){
            const recent = Array.isArray(changes.recent_disclosures)
                ? changes.recent_disclosures
                : [];

            return `
              <div class="space-y-3">
                <div class="font-bold text-blue-700">${label} 공시 심층 분석</div>
                <div class="grid grid-cols-3 gap-2 text-center">
                  <div class="bg-blue-50 rounded-xl p-3"><div class="text-[10px] text-gray-400">공시일 확인</div><div class="font-bold text-blue-700">${recent.length}개</div></div>
                  <div class="bg-gray-50 rounded-xl p-3"><div class="text-[10px] text-gray-400">수집기관</div><div class="font-bold">${collectedBanks.length}개</div></div>
                  <div class="bg-amber-50 rounded-xl p-3"><div class="text-[10px] text-gray-400">우리금융 공시</div><div class="font-bold text-[11px]">${woori.disclosure_date || "-"}</div></div>
                </div>
                <div class="bg-amber-50 border border-amber-100 rounded-xl p-3">
                  ${label}은 전일 변동 대신 공시일과 현재 금리를 함께 비교해 경쟁사 움직임을 판단합니다.
                </div>
              </div>`;
        }

        return `
          <div class="space-y-3">
            <div class="font-bold text-blue-700">${label} 시장 심층 분석</div>
            <div class="grid grid-cols-3 gap-2 text-center">
              <div class="bg-gray-50 rounded-xl p-3"><div class="text-[10px] text-gray-400">시장 평균</div><div class="font-bold">${aiCenterRate(kpi.average_rate)}</div></div>
              <div class="bg-blue-50 rounded-xl p-3"><div class="text-[10px] text-gray-400">최고금리</div><div class="font-bold text-blue-700">${aiCenterRate(kpi.max_rate ?? kpi.highest_rate)}</div></div>
              <div class="bg-gray-50 rounded-xl p-3"><div class="text-[10px] text-gray-400">수집기관</div><div class="font-bold">${collectedBanks.length}개</div></div>
            </div>
            <div class="bg-blue-50 border border-blue-100 rounded-xl p-3">
              현재 TOP1은 ${displayBankName(rates[0]?.bank ?? "-")} ${aiCenterRate(rates[0]?.rate)}이며,
              우리금융은 ${woori.market_rank ?? "-"}위 ${aiCenterRate(woori.rate)}입니다.
            </div>
          </div>`;
    }


    if(tab === "financial"){
        const leader = financial[0] || {};
        const gapToLeader =
            Number.isFinite(Number(leader.rate)) &&
            Number.isFinite(Number(woori.rate))
                ? Number(woori.rate) - Number(leader.rate)
                : null;

        return `
          <div class="space-y-3">
            <div class="font-bold text-blue-700">금융지주 저축은행 심층 분석</div>
            <div class="grid grid-cols-3 gap-2 text-center">
              <div class="bg-gray-50 rounded-xl p-3"><div class="text-[10px] text-gray-400">우리금융 금리</div><div class="font-bold">${aiCenterRate(woori.rate)}</div></div>
              <div class="bg-gray-50 rounded-xl p-3"><div class="text-[10px] text-gray-400">금융지주 순위</div><div class="font-bold">${woori.financial_rank ?? "-"}위</div></div>
              <div class="bg-gray-50 rounded-xl p-3"><div class="text-[10px] text-gray-400">선두 대비</div><div class="font-bold">${gapToLeader === null ? "-" : aiCenterGap(gapToLeader)}</div></div>
            </div>
            <div class="bg-blue-50 border border-blue-100 rounded-xl p-3">
              우리금융의 금융지주 내 위치와 상위 금융지주 저축은행의 금리 조정 여부를 우선 확인합니다.
              시장 평균 대비 경쟁력은 ${aiCenterGap(woori.average_gap)} 입니다.
            </div>
          </div>`;
    }

    if(tab === "change"){
        const ups = Array.isArray(changes.up_top5) ? changes.up_top5 : [];
        const downs = Array.isArray(changes.down_top5) ? changes.down_top5 : [];
        return `
          <div class="space-y-3">
            <div class="font-bold text-blue-700">금리 변동 심층 분석</div>
            <div class="grid grid-cols-3 gap-2 text-center">
              <div class="bg-blue-50 rounded-xl p-3"><div class="text-[10px] text-gray-400">상승</div><div class="font-bold text-blue-600">${changes.up_count ?? ups.length}건</div></div>
              <div class="bg-red-50 rounded-xl p-3"><div class="text-[10px] text-gray-400">하락</div><div class="font-bold text-red-600">${changes.down_count ?? downs.length}건</div></div>
              <div class="bg-gray-50 rounded-xl p-3"><div class="text-[10px] text-gray-400">전체변동</div><div class="font-bold">${changes.change_count ?? 0}건</div></div>
            </div>
            <div class="bg-amber-50 border border-amber-100 rounded-xl p-3">
              전일 대비 실제 금리 변경 기관을 기준으로 방향성과 변동폭을 분석합니다.
              변동이 없는 날에는 상승·하락 목록이 비어 있는 것이 정상입니다.
            </div>
          </div>`;
    }

    return `
      <div class="space-y-3">
        <div class="font-bold text-blue-700">시장 심층 분석</div>
        <div class="grid grid-cols-3 gap-2 text-center">
          <div class="bg-gray-50 rounded-xl p-3"><div class="text-[10px] text-gray-400">시장 평균</div><div class="font-bold">${aiCenterRate(kpi.average_rate)}</div></div>
          <div class="bg-blue-50 rounded-xl p-3"><div class="text-[10px] text-gray-400">최고금리</div><div class="font-bold text-blue-700">${aiCenterRate(kpi.max_rate ?? kpi.highest_rate)}</div></div>
          <div class="bg-gray-50 rounded-xl p-3"><div class="text-[10px] text-gray-400">변동</div><div class="font-bold">${changes.change_count ?? kpi.change_count ?? 0}건</div></div>
        </div>
        <div class="bg-blue-50 border border-blue-100 rounded-xl p-3">
          상위권 금리 수준, 시장 평균, 금리 변동 건수를 함께 확인해 시장 경쟁 강도를 판단합니다.
          현재 TOP1은 ${displayBankName(rates[0]?.bank ?? "-")} ${aiCenterRate(rates[0]?.rate)} 입니다.
        </div>
      </div>`;
}

function centerDetailQuestion(tab, data){
    const {kpi, woori, financial, changes} = data;
    const basis = formatDataBasis(window.sbDataBasisValue);

    if(activeMarketProduct !== "deposit"){
        const label=marketProductLabel();
        if(tab==="financial") return `데이터 업데이트 시간 ${basis}. ${label} ${currentSelectedPeriod()}개월 기준 금융지주 저축은행 경쟁현황을 심층 분석해줘. 우리금융 금리 ${woori.rate??"-"}%, 시장순위 ${woori.market_rank??"-"}위, 평균대비 ${woori.average_gap??0}%p이며 금융지주 현황은 ${JSON.stringify(financial.slice(0,10))}이다. 공시일과 금리격차 중심으로 대응 포인트를 작성해줘.`;
        if(tab==="change") return `데이터 업데이트 시간 ${basis}. ${label} 최근 공시 현황을 심층 분석해줘. 최근 공시 데이터는 ${JSON.stringify(changes.recent_disclosures||[])}이다. 우리금융 공시일과 경쟁사 공시 움직임을 중심으로 작성해줘.`;
        return `데이터 업데이트 시간 ${basis}. ${label} ${currentSelectedPeriod()}개월 시장을 심층 분석해줘. 평균 ${kpi.average_rate??"-"}%, 최고 ${kpi.max_rate??"-"}%, 우리금융 ${woori.rate??"-"}%, 시장순위 ${woori.market_rank??"-"}위다. 상위권 경쟁강도와 우리금융 시사점을 작성해줘.`;
    }

    if(tab === "financial"){
        return `데이터 업데이트 시간 ${basis}. 금융지주 저축은행만 대상으로 우리금융의 경쟁력을 심층 분석해줘. 우리금융 금리 ${woori.rate ?? "-"}%, 금융지주 순위 ${woori.financial_rank ?? "-"}위, 시장 평균 대비 ${woori.average_gap ?? 0}%p이며 금융지주 현황 데이터는 ${JSON.stringify(financial.slice(0,10))}이다. 상위사 대비 GAP, 경쟁사 금리 조정, 우리금융 대응 포인트 순으로 분석해줘. 일반적인 AI 질문 답변이 아니라 이 데이터에 근거한 분석만 작성해줘.`;
    }

    if(tab === "change"){
        return `데이터 업데이트 시간 ${basis}. 오늘 저축은행 정기예금 금리 변동을 심층 분석해줘. 상승 ${changes.up_count ?? 0}건, 하락 ${changes.down_count ?? 0}건, 전체변동 ${changes.change_count ?? 0}건이며 상승 TOP5 ${JSON.stringify(changes.up_top5 || [])}, 하락 TOP5 ${JSON.stringify(changes.down_top5 || [])}이다. 변동 방향, 주요 기관, 우리금융에 미치는 시사점 순으로 작성해줘.`;
    }

    return `데이터 업데이트 시간 ${basis}. 오늘 정기예금 시장을 심층 분석해줘. 시장 평균 ${kpi.average_rate ?? "-"}%, 최고금리 ${kpi.max_rate ?? kpi.highest_rate ?? "-"}%, 상품수 ${kpi.product_count ?? 0}개, 금리변동 ${changes.change_count ?? kpi.change_count ?? 0}건이다. 시장 수준, 상위권 경쟁 강도, 오늘의 체크포인트 순으로 데이터 기반 분석해줘.`;
}

async function openAICenterDetail(){
    // AI 분석센터 상세는 일반 AI 답변 상세/시장 상세와 완전 분리
    ["ai-detail-modal", "market-detail-modal"].forEach(id => {
        const other = document.getElementById(id);
        if(other){
            other.classList.add("hidden");
            other.classList.remove("flex");
        }
    });

    const preview = document.getElementById("ai-detail-preview");
    if(preview){
        preview.style.display = "none";
    }

    const modal = document.getElementById("ai-center-detail-modal");
    const content = document.getElementById("ai-center-detail-content");
    const title = document.getElementById("ai-center-detail-title");
    const subtitle = document.getElementById("ai-center-detail-subtitle");

    if(!modal || !content) return;

    const tab = aiCenterActiveTab || "market";
    const selectedLabel = marketProductLabel();

    const titles = activeMarketProduct === "deposit"
        ? {
            market: "📊 시장분석 상세",
            financial: "🏦 금융지주 저축은행 상세",
            change: "📈 변동분석 상세"
          }
        : {
            market: `📊 ${selectedLabel} 시장분석 상세`,
            financial: `🏦 ${selectedLabel} 금융지주 상세`,
            change: `🗓️ ${selectedLabel} 공시분석 상세`
          };

    if(title) title.textContent = titles[tab] || "📊 AI 상세 분석";
    if(subtitle) subtitle.textContent = "선택한 탭의 실제 데이터 업데이트 시간 심층 분석";

    modal.classList.remove("hidden");
    modal.classList.add("flex");
    content.innerHTML = '<div class="py-10 text-center text-gray-400">실제 데이터를 불러와 심층 분석 중입니다...</div>';

    const data = await loadAIAnalysisCenterData();

    // API 장애가 있어도 데이터 기반 기본 분석은 반드시 표시
    content.innerHTML = centerDetailFallback(tab, data) +
        '<div id="ai-center-deep-ai" class="mt-4 border-t pt-4"><div class="text-gray-400">AI 심층 해석을 생성하고 있습니다...</div></div>';

    try{
        const response = await fetch("/api/ai/search", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                question: centerDetailQuestion(tab, data),
                category: activeMarketProduct,
                period: currentSelectedPeriod()
            })
        });

        if(!response.ok) throw new Error(`AI API Error : ${response.status}`);

        const result = await response.json();
        const answer = result?.answer || result?.result || result?.message || "";
        const aiBox = document.getElementById("ai-center-deep-ai");

        if(aiBox){
            aiBox.innerHTML = answer
                ? `<div class="font-bold text-blue-700 mb-2">🤖 AI 심층 해석</div><div class="bg-gray-50 border border-gray-100 rounded-xl p-3 whitespace-pre-wrap">${escapeReportHtml(answer)}</div>`
                : '<div class="text-gray-400">AI 추가 해석이 없어 기본 데이터 분석만 표시합니다.</div>';
        }
    }
    catch(error){
        console.error("AI CENTER DETAIL ERROR:", error);
        const aiBox = document.getElementById("ai-center-deep-ai");
        if(aiBox){
            aiBox.innerHTML = '<div class="text-gray-400">AI 추가 해석을 불러오지 못해 기본 데이터 분석만 표시합니다.</div>';
        }
    }
}

async function initAIAnalysisCenter(){
    const tabs = document.querySelectorAll("[data-ai-center-tab]");
    if(!tabs.length) return;

    tabs.forEach(button => {
        button.addEventListener("click", () => {
            aiCenterActiveTab = button.dataset.aiCenterTab || "market";
            updateAIAnalysisCenterTabs();
            renderAIAnalysisCenter(aiCenterActiveTab);
        });
    });

    const sideDetailBtn = document.getElementById("ai-side-detail-btn");
    if(sideDetailBtn){
        sideDetailBtn.addEventListener("click", async event => {
            event.preventDefault();
            event.stopPropagation();
            if(typeof event.stopImmediatePropagation === "function"){
                event.stopImmediatePropagation();
            }
            await openAICenterDetail();
        });
    }

    const centerDetailClose = document.getElementById("ai-center-detail-close");
    if(centerDetailClose){
        centerDetailClose.addEventListener("click", closeAICenterDetail);
    }

    const centerDetailModal = document.getElementById("ai-center-detail-modal");
    if(centerDetailModal){
        centerDetailModal.addEventListener("click", e => {
            if(e.target === centerDetailModal){
                closeAICenterDetail();
            }
        });
    }

    const reportBtn = document.getElementById("ai-report-btn");
    if(reportBtn){
        reportBtn.addEventListener("click", openAIExecutiveReport);
    }

    const reportPrint = document.getElementById("ai-report-print");
    if(reportPrint){
        reportPrint.addEventListener("click", printExecutiveReport);
    }

    const reportPdf = document.getElementById("ai-report-pdf");
    if(reportPdf){
        reportPdf.addEventListener("click", downloadExecutiveReportPDF);
    }

    const reportClose = document.getElementById("ai-report-close");
    if(reportClose){
        reportClose.addEventListener("click", closeAIExecutiveReport);
    }

    const reportModal = document.getElementById("ai-report-modal");
    if(reportModal){
        reportModal.addEventListener("click", e => {
            if(e.target === reportModal){
                closeAIExecutiveReport();
            }
        });
    }

    // 최초 렌더는 switchMarketProduct()에서 실제 상품 데이터가 준비된 뒤 실행.
}

function updateAIAnalysisCenterTabs(){
    document.querySelectorAll("[data-ai-center-tab]").forEach(button => {
        const active = button.dataset.aiCenterTab === aiCenterActiveTab;
        button.className = active
            ? "ai-center-tab bg-white text-blue-700 shadow-sm rounded-md py-1.5 font-bold"
            : "ai-center-tab text-gray-500 rounded-md py-1.5 hover:text-blue-600";
    });
}

async function loadAIAnalysisCenterData(){
    if(activeMarketProduct==="deposit"){
        const [kpi,woori,rates,financial,changes,ai]=await Promise.all([
            apiFetch("/api/kpi"),apiFetch("/api/woori"),apiFetch("/api/rates?all=1"),apiFetch("/api/financial"),apiFetch("/api/rate-changes"),apiFetch("/api/ai")
        ]);
        return {kpi:kpi||{},woori:woori||{},rates:Array.isArray(rates)?rates:[],financial:Array.isArray(financial)?financial:[],changes:changes||{},ai:ai||{},mode:"deposit"};
    }
    if(!currentMarketItems.length)await fetchAlternativeMarketItems(activeMarketProduct,currentSelectedPeriod());
    const items=currentMarketItems.map(normalizeMarketItem),s=buildAlternativeKPI(items),wi=s.woori||{};
    const base=await apiFetch("/api/financial"),bf=Array.isArray(base)?base:[];
    const cores=new Set(bf.map(i=>normalizeBankCore(i.bank??i.bank_name??i.kor_co_nm)));
    let financial=s.valid.filter(i=>{const c=normalizeBankCore(i.bank);return [...cores].some(b=>b&&(c.includes(b)||b.includes(c)))});
    if(!financial.length){const keys=["우리","KB","신한","하나","NH","IBK","BNK","DGB","한국투자"];financial=s.valid.filter(i=>keys.some(k=>normalizeBankCore(i.bank).includes(normalizeBankCore(k))))}
    financial=financial.sort((a,b)=>Number(b.rate)-Number(a.rate)).map((i,x)=>({...i,rank:x+1,change:0}));
    const recent=[...items].filter(i=>i.disclosure_date).sort((a,b)=>disclosureSortValue(b.disclosure_date)-disclosureSortValue(a.disclosure_date));
    const kpi={average_rate:s.avg,max_rate:s.max,highest_rate:s.max,lowest_rate:s.min,product_count:items.length,change_count:recent.length};
    const woori={...wi,market_rank:s.rank,market_total:s.total,average_gap:Number.isFinite(Number(wi.rate))&&Number.isFinite(s.avg)?Number(wi.rate)-s.avg:0,financial_rank:(financial.findIndex(i=>String(i.bank).includes("우리금융"))+1)||null};
    return {kpi,woori,rates:s.valid.map((i,x)=>({...i,rank:x+1})),financial,changes:{change_count:recent.length,up_count:0,down_count:0,recent_disclosures:recent.slice(0,10)},ai:{summary:[]},mode:activeMarketProduct};
}


function renderAlternativeAIAnalysisCenter(tab,data){
    const target = document.getElementById("ai-center-content");
    if(!target) return;

    const {kpi,woori,rates,financial,changes} = data;
    const label = marketProductLabel();
    const recent = Array.isArray(changes.recent_disclosures)
        ? changes.recent_disclosures
        : [];

    const collectedBanks = [...new Set(
        currentMarketItems
            .map(item => String(item.bank || "").trim())
            .filter(Boolean)
    )];

    if(tab === "financial"){
        target.innerHTML = `
        <div class="space-y-3">
          <div class="bg-blue-50 border border-blue-100 rounded-xl p-3">
            <div class="flex items-center justify-between mb-2">
              <span class="font-bold text-blue-700">🏦 우리금융 경쟁력</span>
              <span class="text-[10px] text-gray-400">${label} ${currentSelectedPeriod()}개월</span>
            </div>

            <div class="grid grid-cols-[1fr_1fr_1fr] gap-2 text-center">
              <div class="bg-white rounded-lg py-2 border border-blue-50">
                <div class="text-[10px] text-gray-400">순위</div>
                <div class="font-bold text-blue-700">${woori.market_rank ?? "-"}위</div>
              </div>
              <div class="bg-white rounded-lg py-2 border border-blue-50">
                <div class="text-[10px] text-gray-400">금리</div>
                <div class="font-bold">${aiCenterRate(woori.rate)}</div>
              </div>
              <div class="bg-white rounded-lg py-2 border border-blue-50">
                <div class="text-[10px] text-gray-400">공시일</div>
                <div class="font-bold text-[11px]">${woori.disclosure_date || "-"}</div>
              </div>
            </div>
          </div>

          <div class="border border-gray-100 rounded-xl p-3">
            <div class="font-bold text-gray-700 mb-2">📋 금융지주 저축은행 현황</div>

            <div class="grid grid-cols-[30px_1fr_60px_76px] gap-2 px-2 pb-1 text-[10px] text-gray-400 text-center">
              <span>순위</span><span>저축은행</span><span>금리</span><span>공시일</span>
            </div>

            <div class="space-y-1">
              ${financial.map(item => {
                  const matched = currentMarketItems.find(x =>
                      normalizeBankCore(x.bank) === normalizeBankCore(item.bank)
                  );

                  const disclosureDate =
                      item.disclosure_date ||
                      matched?.disclosure_date ||
                      (item.rate_month ? `${item.rate_month}` : null) ||
                      (matched?.rate_month ? `${matched.rate_month}` : null) ||
                      "-";

                  const isWoori = String(item.bank).includes("우리금융");

                  return `
                    <div class="grid grid-cols-[30px_1fr_60px_76px] gap-2 px-2 py-1.5 rounded-xl items-center
                      ${isWoori ? "woori-highlight-row font-bold" : "bg-gray-50"}">
                      <span class="text-center">${item.rank}</span>
                      <span class="truncate text-center">${displayBankName(item.bank)}</span>
                      <span class="text-center">${aiCenterRate(item.rate)}</span>
                      <span class="text-[10px] text-center">${formatDisclosureDate(disclosureDate)}</span>
                    </div>`;
              }).join("") || '<div class="text-center text-gray-400 py-4">금융지주 데이터 없음</div>'}
            </div>
          </div>

          <div class="bg-indigo-50 border border-indigo-100 rounded-xl p-3 text-[11px] text-gray-600 leading-5">
            <div class="font-bold text-indigo-700 mb-1">🧠 AI 금융지주 분석 포인트</div>
            ${label} 기준 우리금융의 금융지주 내 위치, 상위사 금리 격차와 최근 공시일을 함께 점검합니다.
          </div>
        </div>`;
        return;
    }

    if(tab === "change"){
        target.innerHTML = `
        <div class="space-y-3">
          <div class="grid grid-cols-3 gap-2 text-center">
            <div class="bg-blue-50 rounded-lg p-2">
              <div class="text-[10px] text-gray-400">공시일 확인</div>
              <div class="text-lg font-bold text-blue-700">${recent.length}</div>
            </div>
            <div class="bg-gray-50 rounded-lg p-2">
              <div class="text-[10px] text-gray-400">수집기관</div>
              <div class="text-lg font-bold">${collectedBanks.length}</div>
            </div>
            <div class="bg-amber-50 rounded-lg p-2">
              <div class="text-[10px] text-gray-400">우리금융 공시</div>
              <div class="text-sm font-bold">${woori.disclosure_date || "-"}</div>
            </div>
          </div>

          <div class="border border-gray-100 rounded-xl p-3">
            <div class="font-bold text-gray-700 mb-2">🗓️ 공시 현황</div>

            <div class="grid grid-cols-[30px_1fr_64px_76px] gap-2 px-2 pb-1 text-[10px] text-gray-400 text-center">
              <span>순위</span><span>저축은행</span><span>금리</span><span>공시일</span>
            </div>

            ${validRateItems(recent)
                .sort((a,b) => Number(b.rate) - Number(a.rate))
                .slice(0,7)
                .map((item,index) => `
                  <div class="grid grid-cols-[30px_1fr_64px_76px] gap-2 px-2 py-1.5 mb-1 items-center ${isWooriBank(item.bank) ? "woori-highlight-row font-bold" : "bg-gray-50 rounded-lg"}">
                    <span class="text-center">${index + 1}</span>
                    <span class="truncate text-center">${displayBankName(item.bank)}</span>
                    <span class="font-semibold text-center">${aiCenterRate(item.rate)}</span>
                    <span class="text-[10px] font-semibold text-center whitespace-nowrap">${formatDisclosureDate(item.disclosure_date || item.rate_month) || "-"}</span>
                  </div>`)
                .join("") || '<div class="text-center text-gray-400 py-4">공시일 데이터 없음</div>'}
          </div>

          <div class="bg-amber-50 border border-amber-100 rounded-xl p-3 text-[11px] text-gray-600 leading-5">
            <div class="font-bold text-amber-800 mb-1">💡 공시 모니터링</div>
            ${label}은 전일변동 대신 공시일과 금리 수준을 함께 기준으로 최근 경쟁현황을 확인합니다.
          </div>
        </div>`;
        return;
    }

    const altTopRate = Number(rates?.[0]?.rate ?? kpi.max_rate);
    const altWooriRate = Number(woori.rate);
    const altAvgRate = Number(kpi.average_rate);
    const altGap =
        Number.isFinite(altTopRate) && Number.isFinite(altWooriRate)
            ? altWooriRate - altTopRate
            : null;
    const altAvgGap =
        Number.isFinite(altAvgRate) && Number.isFinite(altWooriRate)
            ? altWooriRate - altAvgRate
            : null;
    const altTop5 = rates.slice(0,5);
    const altTop5Avg = altTop5.length
        ? altTop5.reduce((sum,item)=>sum+Number(item.rate||0),0)/altTop5.length
        : null;
    const altHigherCount = Number.isFinite(altWooriRate)
        ? rates.filter(item => !isWooriBank(item.bank) && Number(item.rate)>altWooriRate).length
        : 0;

    target.innerHTML = `
    <div class="space-y-2.5">
      <div class="grid grid-cols-3 gap-2 text-center">
        <div class="bg-blue-50 border border-blue-100 rounded-xl p-2">
          <div class="text-[9px] text-gray-400">우리금융 금리</div>
          <div class="text-sm font-bold text-blue-700">${aiCenterRate(woori.rate)}</div>
        </div>
        <div class="bg-gray-50 border border-gray-100 rounded-xl p-2">
          <div class="text-[9px] text-gray-400">시장순위</div>
          <div class="text-sm font-bold">${woori.market_rank ?? "-"}위</div>
        </div>
        <div class="bg-gray-50 border border-gray-100 rounded-xl p-2">
          <div class="text-[9px] text-gray-400">최고금리 Gap</div>
          <div class="text-sm font-bold">${altGap === null ? "-" : aiCenterGap(altGap)}</div>
        </div>
      </div>

      <div class="border border-gray-100 rounded-xl p-2.5">
        <div class="flex items-center justify-between mb-1.5">
          <div class="font-bold text-gray-700">🏦 수집 저축은행</div>
          <span class="text-[9px] text-gray-400">${collectedBanks.length}개 기관</span>
        </div>
        <div class="text-[9.5px] leading-[1.45] text-gray-500 [word-break:keep-all]">
          ${collectedBanks.map(displayBankName).join(" · ") || "수집기관 없음"}
        </div>
      </div>

      <div class="border border-gray-100 rounded-xl p-2.5">
        <div class="font-bold text-gray-700 mb-1.5">🏆 ${label} TOP5</div>
        <div class="grid grid-cols-[34px_1fr_62px_78px] gap-2 px-2 pb-1 text-[9px] text-gray-400 text-center">
          <span>순위</span><span>저축은행</span><span>금리</span><span>공시일</span>
        </div>
        <div class="space-y-1">
          ${rates.slice(0,5).map(item => {
              const isWoori = isWooriBank(item.bank);
              return `
                <div class="grid grid-cols-[34px_1fr_62px_78px] gap-2 items-center px-2 py-1.5
                  ${isWoori ? "woori-highlight-row font-bold" : "bg-gray-50 rounded-lg"}">
                  <span class="text-center">${item.rank ?? "-"}</span>
                  <span class="text-center truncate">${displayBankName(item.bank)}</span>
                  <span class="text-center font-bold">${aiCenterRate(item.rate)}</span>
                  <span class="text-center text-[10px] font-semibold whitespace-nowrap">${formatDisclosureDate(item.disclosure_date || item.rate_month) || "-"}</span>
                </div>`;
          }).join("") || '<div class="text-gray-400 text-center py-4">시장 데이터 없음</div>'}
        </div>
      </div>

      <div class="bg-[#f6f9ff] border border-blue-100 rounded-xl px-3 py-2 text-[10.5px] leading-[1.5] text-gray-600 [word-break:keep-all]">
        <div class="font-bold text-blue-700 mb-0.5">🧠 경쟁력 판단</div>
        <b class="text-gray-800">우리금융 ${woori.market_rank ?? "-"}위 · ${aiCenterRate(woori.rate)}</b>.
        ${altGap === null ? "시장 최고와의 Gap 확인이 필요합니다." : altGap === 0 ? "시장 최고금리와 동일한 수준입니다." : `시장 최고 대비 ${Math.abs(altGap).toFixed(2)}%p 낮습니다.`}
        ${altAvgGap === null ? "" : altAvgGap > 0 ? ` 시장 평균 대비 +${altAvgGap.toFixed(2)}%p로 우위입니다.` : altAvgGap < 0 ? ` 시장 평균 대비 ${altAvgGap.toFixed(2)}%p입니다.` : " 시장 평균과 동일합니다."}
        상위5 평균은 <b>${altTop5Avg!=null?altTop5Avg.toFixed(2)+"%":"-"}</b>,
        당행보다 높은 기관은 <b>${altHigherCount}개</b>입니다.
      </div>
    </div>`;
}


async function renderAIAnalysisCenter(tab){
    const target = document.getElementById("ai-center-content");
    if(!target) return;

    target.classList.toggle("ai-market-compact", tab === "market");
    target.style.overflowY = "auto";

    target.innerHTML = '<div class="py-10 text-center text-gray-400">분석 데이터를 불러오는 중입니다.</div>';

    const data = await loadAIAnalysisCenterData();
    const {kpi,woori,rates,financial,changes} = data;

    if(activeMarketProduct !== "deposit"){
        renderAlternativeAIAnalysisCenter(tab,data);
        requestAnimationFrame(syncAIAnalysisCenterHeight);
        return;
    }

    if(tab === "financial"){
        const financialRank =
            woori.financial_rank ??
            financial.findIndex(item =>
                String(item.bank || "").includes("우리금융")
            ) + 1;

        target.innerHTML = `
        <div class="space-y-3">

          <!-- 기존 우리금융 경쟁력 미니패널 유지 -->
          <div class="bg-blue-50 border border-blue-100 rounded-xl p-3">
            <div class="flex items-center justify-between mb-2">
              <span class="font-bold text-blue-700">🏦 우리금융 경쟁력</span>
              <span class="text-[10px] text-gray-400">12개월 기준</span>
            </div>
            <div class="grid grid-cols-3 gap-2 text-center">
              <div class="bg-white rounded-lg py-2 border border-blue-50">
                <div class="text-[10px] text-gray-400">시장순위</div>
                <div class="font-bold text-blue-700 text-sm">${woori.market_rank ?? "-"}위</div>
              </div>
              <div class="bg-white rounded-lg py-2 border border-blue-50">
                <div class="text-[10px] text-gray-400">현재금리</div>
                <div class="font-bold text-gray-800 text-sm">${aiCenterRate(woori.rate)}</div>
              </div>
              <div class="bg-white rounded-lg py-2 border border-blue-50">
                <div class="text-[10px] text-gray-400">평균금리 대비</div>
                <div class="text-sm">${aiCenterGap(woori.average_gap)}</div>
              </div>
            </div>
          </div>

          <!-- 금융지주 저축은행 현황 -->
          <div class="border border-gray-100 rounded-xl p-3">
            <div class="flex items-center justify-between mb-3">
              <span class="font-bold text-gray-700">📋 금융지주 저축은행 현황</span>
              <span class="text-[10px] bg-blue-50 text-blue-700 px-2 py-1 rounded-full">우리금융 ${Number(financialRank) > 0 ? financialRank : "-"}위</span>
            </div>
            <div class="grid grid-cols-[34px_1fr_62px_70px] gap-2 px-2 pb-1 text-[10px] text-gray-400 text-center">
              <span>순위</span><span>저축은행</span><span>금리</span><span>전일比</span>
            </div>
            <div class="space-y-1">
              ${financial.map(item=>{
                  const isWoori = String(item.bank || "").includes("우리금융");
                  return `<div class="grid grid-cols-[34px_1fr_62px_70px] gap-2 items-center rounded-lg px-2 py-1.5 ${isWoori ? "woori-highlight-row font-bold" : "bg-gray-50"}">
                    <span class="text-center">${item.rank ?? "-"}</span>
                    <span class="truncate text-center">${displayBankName(item.bank ?? "-")}</span>
                    <span class="font-bold text-center">${aiCenterRate(item.rate)}</span>
                    <span class="text-center">${aiCenterChange(item.change)}</span>
                  </div>`;
              }).join("") || '<div class="text-gray-400 text-center py-4">금융지주 저축은행 데이터 없음</div>'}
            </div>
          </div>

          <!-- 경쟁사 AI 분석을 금융지주 탭으로 통합 -->
          <div class="bg-indigo-50 border border-indigo-100 rounded-xl p-3 text-[11px] text-gray-600 leading-5">
            <div class="font-bold text-indigo-700 mb-1">🧠 AI 금융지주 저축은행 분석</div>
            금융지주 저축은행의 금리 순위와 전일 변동을 기준으로 우리금융의 경쟁 위치를 점검합니다.
            상위 금융지주 저축은행과의 금리 격차 및 경쟁사의 금리 조정 여부를 함께 모니터링합니다.
          </div>
        </div>`;
        return;
    }

    if(tab === "change"){
        const ups = Array.isArray(changes.up_top5)?changes.up_top5:[];
        const downs = Array.isArray(changes.down_top5)?changes.down_top5:[];
        const upCount = Number(changes.up_count ?? ups.length ?? 0);
        const downCount = Number(changes.down_count ?? downs.length ?? 0);
        const totalCount = Number(changes.change_count ?? (upCount+downCount) ?? 0);

        const strongestUp = [...ups]
            .sort((a,b)=>Number(b.change??b.change_value??0)-Number(a.change??a.change_value??0))[0];
        const strongestDown = [...downs]
            .sort((a,b)=>Math.abs(Number(b.change??b.change_value??0))-Math.abs(Number(a.change??a.change_value??0)))[0];

        const wooriMove = [...ups,...downs].find(item=>isWooriBank(item.bank));
        const wooriChange = Number(wooriMove?.change ?? wooriMove?.change_value ?? 0);

        const direction =
            downCount > upCount ? "인하 우세" :
            upCount > downCount ? "인상 우세" :
            totalCount > 0 ? "혼조" : "변동 없음";

        const directionText =
            downCount > upCount
                ? `하락 ${downCount}건이 상승 ${upCount}건보다 많아 시장 금리 조정은 인하 방향이 우세합니다.`
                : upCount > downCount
                    ? `상승 ${upCount}건이 하락 ${downCount}건보다 많아 일부 은행의 수신 경쟁 강화가 나타납니다.`
                    : totalCount > 0
                        ? `상승 ${upCount}건·하락 ${downCount}건으로 방향성이 엇갈리는 혼조 국면입니다.`
                        : "전일 대비 금리 변동이 없어 시장 금리 수준은 유지되고 있습니다.";

        const wooriText =
            wooriMove
                ? `우리금융은 ${wooriChange>0?"+"+wooriChange.toFixed(2):"▲"+Math.abs(wooriChange).toFixed(2)}%p 변동했습니다.`
                : "우리금융은 금일 변동 목록에 없어 금리를 유지했습니다.";

        target.innerHTML = `
        <div class="space-y-3">
          <div class="grid grid-cols-3 gap-2 text-center">
            <div class="bg-gray-50 border border-gray-100 rounded-xl p-2.5">
              <div class="text-[9px] text-gray-400">시장 방향</div>
              <div class="text-sm font-bold text-gray-800">${direction}</div>
            </div>
            <div class="bg-blue-50 border border-blue-100 rounded-xl p-2.5">
              <div class="text-[9px] text-gray-400">상승 / 하락</div>
              <div class="text-sm font-bold"><span class="text-blue-600">${upCount}</span> / <span class="text-red-500">${downCount}</span></div>
            </div>
            <div class="bg-gray-50 border border-gray-100 rounded-xl p-2.5">
              <div class="text-[9px] text-gray-400">전체 변동</div>
              <div class="text-sm font-bold">${totalCount}건</div>
            </div>
          </div>

          <div class="grid grid-cols-2 gap-2">
            <div class="border border-gray-100 rounded-xl p-3">
              <div class="text-[10px] text-gray-400 mb-1">최대 상승</div>
              ${strongestUp
                  ? `<div class="font-bold text-gray-800">${displayBankName(strongestUp.bank)}</div>
                     <div class="mt-1">${aiCenterRate(strongestUp.rate)} · ${aiCenterChange(strongestUp.change ?? strongestUp.change_value)}</div>`
                  : '<div class="text-gray-400 py-2">상승 없음</div>'}
            </div>
            <div class="border border-gray-100 rounded-xl p-3">
              <div class="text-[10px] text-gray-400 mb-1">최대 하락</div>
              ${strongestDown
                  ? `<div class="font-bold text-gray-800">${displayBankName(strongestDown.bank)}</div>
                     <div class="mt-1">${aiCenterRate(strongestDown.rate)} · ${aiCenterChange(strongestDown.change ?? strongestDown.change_value)}</div>`
                  : '<div class="text-gray-400 py-2">하락 없음</div>'}
            </div>
          </div>

          <div class="bg-[#f6f9ff] border border-blue-100 rounded-xl p-3 text-[11px] leading-[1.55] text-gray-600 [word-break:keep-all]">
            <div class="font-bold text-blue-700 mb-1">🧠 AI 변동 인사이트</div>
            ${directionText}<br>
            ${wooriText}
            ${downCount>upCount ? " 상위금리권 인하가 이어질 경우 당행과 시장 상단의 Gap 축소 여부를 확인할 필요가 있습니다." : upCount>downCount ? " 경쟁사의 추가 인상 여부와 당행 경쟁력 변화를 점검할 필요가 있습니다." : ""}
          </div>
        </div>`;
        return;
    }

    const summary = Array.isArray(data.ai.summary)?data.ai.summary:[];
    const topRate = Number(rates?.[0]?.rate ?? kpi.max_rate ?? kpi.highest_rate);
    const wooriRateValue = Number(woori.rate);
    const gapToTopValue =
        Number.isFinite(topRate) && Number.isFinite(wooriRateValue)
            ? wooriRateValue - topRate
            : null;

    const marketInsight =
        Number.isFinite(wooriRateValue)
            ? `우리금융 ${woori.market_rank ?? "-"}위 · ${wooriRateValue.toFixed(2)}%. `
              + (
                  gapToTopValue === null
                      ? "시장 최고와의 Gap을 확인 중입니다."
                      : gapToTopValue === 0
                          ? "시장 최고금리와 동일한 수준입니다."
                          : `시장 최고 대비 ${Math.abs(gapToTopValue).toFixed(2)}%p 낮습니다.`
                )
              + ` 전일 변동 ${changes.change_count ?? kpi.change_count ?? 0}건을 함께 점검합니다.`
            : "우리금융 금리와 시장 상단 Gap을 확인 중입니다.";

    target.innerHTML = `
    <div class="space-y-2.5">
      <div class="grid grid-cols-3 gap-2 text-center">
        <div class="bg-blue-50 border border-blue-100 rounded-xl p-2">
          <div class="text-[9px] text-gray-400">우리금융 금리</div>
          <div class="text-sm font-bold text-blue-700">${aiCenterRate(woori.rate)}</div>
        </div>
        <div class="bg-gray-50 border border-gray-100 rounded-xl p-2">
          <div class="text-[9px] text-gray-400">시장순위</div>
          <div class="text-sm font-bold">${woori.market_rank ?? "-"}위</div>
        </div>
        <div class="bg-gray-50 border border-gray-100 rounded-xl p-2">
          <div class="text-[9px] text-gray-400">최고금리 Gap</div>
          <div class="text-sm font-bold">${gapToTopValue === null ? "-" : aiCenterGap(gapToTopValue)}</div>
        </div>
      </div>

      <div class="border border-gray-100 rounded-xl p-2.5">
        <div class="font-bold text-gray-700 mb-1.5">🏆 시장 TOP5</div>

        <div class="grid grid-cols-[38px_1fr_66px] gap-2 px-2 pb-1 text-[9px] text-gray-400 text-center">
          <span>순위</span><span>저축은행</span><span>금리</span>
        </div>

        <div class="space-y-1">
          ${rates.slice(0,5).map(item=>{
              const isWoori = isWooriBank(item.bank);
              return `<div class="grid grid-cols-[38px_1fr_66px] gap-2 items-center px-2 py-1.5
                ${isWoori ? "woori-highlight-row font-bold" : "bg-gray-50 rounded-lg"}">
                <span class="text-center">${item.rank ?? "-"}</span>
                <span class="text-center truncate">${displayBankName(item.bank ?? "-")}</span>
                <span class="text-center font-bold">${aiCenterRate(item.rate)}</span>
              </div>`;
          }).join("") || '<div class="text-gray-400 text-center py-4">시장 데이터 없음</div>'}
        </div>
      </div>

      <div class="bg-[#f6f9ff] border border-blue-100 rounded-xl px-3 py-2 text-[10.5px] text-gray-600 leading-[1.4] [word-break:keep-all]">
        <div class="font-bold text-blue-700 mb-0.5">🧠 판단 포인트</div>
        ${marketInsight}
      </div>
    </div>`;

}



function enableDraggableModal(modalId){
    const overlay=document.getElementById(modalId);
    if(!overlay || overlay.dataset.dragReady==="1") return;

    const panel=overlay.firstElementChild;
    const handle=panel?.querySelector(".modal-drag-handle");
    if(!panel || !handle) return;

    overlay.dataset.dragReady="1";
    panel.classList.add("modal-drag-panel");

    let dragging=false, startX=0, startY=0, baseX=0, baseY=0;

    const reset=()=>{
        baseX=0; baseY=0;
        panel.style.transform="translate(0px, 0px)";
    };

    const originalObserver=new MutationObserver(()=>{
        if(!overlay.classList.contains("hidden")) reset();
    });
    originalObserver.observe(overlay,{attributes:true,attributeFilter:["class"]});

    handle.addEventListener("mousedown",e=>{
        if(e.button!==0 || e.target.closest("button,input,select,a")) return;
        dragging=true;
        startX=e.clientX-baseX;
        startY=e.clientY-baseY;
        document.body.style.userSelect="none";
        e.preventDefault();
    });

    window.addEventListener("mousemove",e=>{
        if(!dragging) return;
        const rect=panel.getBoundingClientRect();
        let nx=e.clientX-startX;
        let ny=e.clientY-startY;

        const maxX=Math.max(0,(window.innerWidth-panel.offsetWidth)/2-12);
        const maxY=Math.max(0,(window.innerHeight-panel.offsetHeight)/2-12);

        nx=Math.max(-maxX,Math.min(maxX,nx));
        ny=Math.max(-maxY,Math.min(maxY,ny));

        baseX=nx; baseY=ny;
        panel.style.transform=`translate(${nx}px, ${ny}px)`;
    });

    window.addEventListener("mouseup",()=>{
        if(!dragging) return;
        dragging=false;
        document.body.style.userSelect="";
    });
}

function initDraggableModals(){
    [
        "ai-center-detail-modal",
        "ai-report-modal",
        "market-detail-modal",
        "ai-detail-modal",
        "error-report-modal"
    ].forEach(enableDraggableModal);
}



function initErrorReportCenter(){
    const openBtn=document.getElementById("error-report-open");
    const modal=document.getElementById("error-report-modal");
    const closeBtn=document.getElementById("error-report-close");
    const cancelBtn=document.getElementById("error-report-cancel");
    const form=document.getElementById("error-report-form");
    const productInput=document.getElementById("error-report-product");
    const typeInput=document.getElementById("error-report-type");
    const messageInput=document.getElementById("error-report-message");
    const status=document.getElementById("error-report-status");

    if(!modal || !form) return;

    const close=()=>{
        modal.classList.add("hidden");
        modal.classList.remove("flex");
    };

    const open=()=>{
        if(productInput) productInput.value=`${marketProductLabel()} · ${currentSelectedPeriod()}개월`;
        if(status) status.textContent="";
        modal.classList.remove("hidden");
        modal.classList.add("flex");
        setTimeout(()=>messageInput?.focus(),30);
    };

    openBtn?.addEventListener("click",open);
    closeBtn?.addEventListener("click",close);
    cancelBtn?.addEventListener("click",close);
    modal.addEventListener("click",e=>{if(e.target===modal) close();});

    form.addEventListener("submit",async e=>{
        e.preventDefault();
        const message=String(messageInput?.value || "").trim();
        if(!message){
            if(status){status.className="text-xs text-red-500";status.textContent="오류 내용을 입력해주세요.";}
            return;
        }

        if(status){status.className="text-xs text-gray-400";status.textContent="제보를 등록하고 있습니다...";}

        try{
            const response=await fetch("/api/error-report",{
                method:"POST",
                headers:{"Content-Type":"application/json"},
                body:JSON.stringify({
                    category:activeMarketProduct,
                    product:marketProductLabel(),
                    period:currentSelectedPeriod(),
                    error_type:typeInput?.value || "기타",
                    message,
                    page_url:location.href,
                    user_agent:navigator.userAgent
                })
            });

            const data=await response.json();
            if(!response.ok || !data?.ok) throw new Error(data?.error || `HTTP ${response.status}`);

            if(status){
                status.className="text-xs text-emerald-600 font-semibold";
                status.textContent=`접수 완료 · ${data.id}`;
            }
            if(messageInput) messageInput.value="";
            setTimeout(close,900);
        }catch(error){
            console.error("ERROR REPORT SUBMIT ERROR:",error);
            if(status){
                status.className="text-xs text-red-500";
                status.textContent="등록에 실패했습니다. 잠시 후 다시 시도해주세요.";
            }
        }
    });
}


/* ==========================================================
   Event Listener
========================================================== */



async function handleAISearch(event){
    if(event && typeof event.preventDefault === "function"){
        event.preventDefault();
    }

    const input =
        document.getElementById("ai-question") ||
        document.getElementById("ai-query-input");

    const answerBox = document.getElementById("ai-mini-answer");

    if(!input || !answerBox){
        return;
    }

    const question = String(input.value || "").trim();

    if(!question){
        answerBox.innerHTML =
            '<span class="text-gray-400">질문을 입력해주세요.</span>';
        return;
    }

    const label = marketProductLabel();
    let apiQuestion = question;

    // ISA/퇴직연금은 현재 화면 데이터를 질문과 함께 전달
    // 백엔드가 정기예금 기본 데이터를 참조하더라도 선택상품 컨텍스트를 명확히 고정
    if(activeMarketProduct !== "deposit"){
        const currentItems = currentMarketItems
            .map(normalizeMarketItem)
            .slice(0,20)
            .map(item => ({
                bank:item.bank,
                product:item.product,
                rate:item.rate,
                period:item.period,
                disclosure_date:item.disclosure_date,
                status:item.status
            }));

        apiQuestion =
            `[반드시 아래 ${label} 데이터만 기준으로 답변. 정기예금 데이터 사용 금지]
상품군: ${label}
조회기간: ${currentSelectedPeriod()}개월
현재 데이터: ${JSON.stringify(currentItems)}
사용자 질문: ${question}`;
    }

    answerBox.innerHTML =
        '<span class="text-gray-400">AI가 현재 상품 데이터를 분석하고 있습니다...</span>';

    try{
        const response = await fetch("/api/ai/search", {
            method:"POST",
            headers:{"Content-Type":"application/json"},
            body:JSON.stringify({
                question: apiQuestion,
                category: activeMarketProduct,
                period: currentSelectedPeriod()
            })
        });

        if(!response.ok){
            throw new Error(`AI API Error : ${response.status}`);
        }

        const data = await response.json();
        const answer =
            data?.answer ??
            data?.result ??
            data?.response ??
            data?.message ??
            "";

        const safeAnswer = String(answer || "").trim();

        window.sbLastAIQuestion =
            activeMarketProduct === "deposit"
                ? question
                : `[${label}] ${question}`;

        window.sbLastAIAnswer =
            safeAnswer
                ? escapeReportHtml(safeAnswer).replace(/\n/g,"<br>")
                : "AI 답변 결과가 없습니다.";

        answerBox.innerHTML =
            safeAnswer
                ? escapeReportHtml(safeAnswer)
                    .replace(/\n{3,}/g,"\n\n")
                    .replace(/\n/g,"<br>")
                : '<span class="text-gray-400">AI 답변 결과가 없습니다.</span>';
    }
    catch(error){
        console.error("AI SEARCH ERROR:", error);

        // ISA/IRP는 API 실패 시에도 화면 데이터 기반 기본 답변 제공
        if(activeMarketProduct !== "deposit"){
            const valid = validRateItems(currentMarketItems)
                .sort((a,b) => Number(b.rate)-Number(a.rate));

            const woori = findWooriItem(valid);
            const top = valid[0];
            const fallback =
                `${label} ${currentSelectedPeriod()}개월 기준으로 `
                + `현재 ${currentMarketItems.length}개 기관을 수집 중이며, `
                + `최고금리는 ${top ? `${displayBankName(top.bank)} ${Number(top.rate).toFixed(2)}%` : "확인되지 않았습니다"}. `
                + `우리금융은 ${woori ? `${Number(woori.rate).toFixed(2)}%` : "금리 확인 필요"}입니다.`;

            window.sbLastAIQuestion = `[${label}] ${question}`;
            window.sbLastAIAnswer = escapeReportHtml(fallback);
            answerBox.textContent = fallback;
            return;
        }

        answerBox.innerHTML =
            '<span class="text-red-500">AI 답변을 불러오지 못했습니다.</span>';
    }
}

function setupEventListeners(){


    /* ======================================================
       TOP10 카테고리 변경
    ====================================================== */

    const category =
        document.getElementById(
            "top10-category-select"
        );


    if(category){

        category.addEventListener(
            "change",
            fetchRatesData
        );

    }



    /* ======================================================
       AI 질문
       현재 V5 index.html : #ai-question
    ====================================================== */

    const aiInput =
        document.getElementById(
            "ai-question"
        )
        ||
        document.getElementById(
            "ai-query-input"
        );


    if(aiInput){


        const inputRow =
            aiInput.parentElement;


        const searchButton =
            inputRow
            ?
            inputRow.querySelector(
                "button"
            )
            :
            null;


        if(searchButton){

            searchButton.addEventListener(
                "click",
                handleAISearch
            );

        }


        aiInput.addEventListener(
            "keydown",
            e => {

                if(e.key === "Enter"){

                    handleAISearch(e);

                }

            }
        );


        const questionPanel =
            aiInput.closest(
                ".bg-gray-50"
            );


        if(questionPanel){

            const quickButtons =
                questionPanel.querySelectorAll(
                    "button"
                );


            quickButtons.forEach(
                button => {

                    if(button === searchButton){

                        return;

                    }


                    button.addEventListener(
                        "click",
                        e => {

                            e.preventDefault();

                            const label =
                                button.textContent.trim();


                            const questionMap = {

                                "시장현황":
                                    "시장현황 알려줘",

                                "우리금융":
                                    "우리금융 경쟁력은",

                                "금융지주 저축은행":
                                    "금융지주 저축은행 현황 알려줘"

                            };


                            aiInput.value =
                                questionMap[label]
                                ||
                                label;


                            handleAISearch(e);

                        }
                    );

                }
            );

        }

    }



    /* ======================================================
       기존 FORM 방식도 호환
    ====================================================== */

    const aiForm =
        document.getElementById(
            "ai-search-form"
        );


    if(aiForm){

        aiForm.addEventListener(
            "submit",
            handleAISearch
        );

    }



    /* ======================================================
       상품 검색
    ====================================================== */

    setupProductSearch();


}




/* ==========================================================
   Dashboard Final Initialize
========================================================== */


window.addEventListener(
    "load",

    ()=>{
        startHeaderClock();
        refreshHeaderDataUpdateTime();
        setupHeaderRefresh();




        fetchAllProducts();



    }

);

/* ======================================================
   HERO 시장경쟁력 데이터 로딩
====================================================== */

async function loadHero(){

    try {

        const data = await apiFetch("/api/woori");

        if(!data){
            return;
        }


        // 시장순위

        const rank =
            document.getElementById("kpi-rank");


        if(rank){

            rank.innerHTML =
                `${data.market_rank || "-"}`;

        }



        // 우리금융 금리

        const wooriRate =
            document.getElementById("kpi-woori-rate-mini");


        if(wooriRate){

            wooriRate.innerText =
                data.rate
                ? `${Number(data.rate).toFixed(2)}%`
                : "-";

        }



        // 업권 최고금리

        const bestRate =
            document.getElementById("kpi-best-rate-mini");


        if(bestRate){

            const gap =
                Number(data.highest_gap || 0);


            const best =
                Number(data.rate || 0) - gap;


            bestRate.innerText =
                best
                ? `${best.toFixed(2)}%`
                : "-";

        }



                // 업권 최저금리

        const heroLowest =
            document.getElementById(
                "kpi-lowest-rate-mini"
            );


        if(heroLowest){

            const lowestRate =
                Number(
                    data.lowest_rate || 0
                );


            if(lowestRate > 0){

                heroLowest.innerText =
                    `${lowestRate.toFixed(2)}%`;

                heroLowest.className =
                    "text-sm font-bold";

            }


            else{

                heroLowest.innerText =
                    "-";

            }

        }



    }
    catch(error){

        console.error(
            "Hero 데이터 로딩 오류:",
            error
        );

    }

}


/* ==========================================================
   AI DETAIL MODAL + HOVER PREVIEW
========================================================== */


document.addEventListener(
    "click",
    function(e){


       /*
    상세 분석 버튼 클릭
*/


const btn =
    e.target.closest(
        "#ai-detail-btn"
    );


if(btn){


    console.log(
        "AI DETAIL BUTTON CLICK"
    );



    /*
        클릭 순간 우리금융 데이터 재조회
    */


    fetch(
        "/api/woori"
    )


    .then(
        response =>
            response.json()
    )


    .then(
        data => {


            console.log(
                "DETAIL WOORI DATA",
                data
            );



            /*
                상세분석 전용 데이터 저장
            */


            wooriPositionData =
                data;



            /*
                상세내용 다시 생성
            */


            if(
                typeof renderAIDetailModal === "function"
            ){


                renderAIDetailModal();


            }





            /*
                모달 열기
            */


            const modal =
                document.getElementById(
                    "ai-detail-modal"
                );



            if(modal){


                modal.classList.remove(
                    "hidden"
                );


                modal.classList.add(
                    "flex"
                );


            }


        }

    )


    .catch(
        error => {


            console.error(
                "WOORI DETAIL ERROR",
                error
            );


        }
    );


}




        /*
            모달 닫기
        */


        const close =
            e.target.closest(
                "#ai-detail-close"
            );



        if(close){


            const modal =
                document.getElementById(
                    "ai-detail-modal"
                );



            if(modal){


                modal.classList.add(
                    "hidden"
                );


                modal.classList.remove(
                    "flex"
                );


                console.log(
                    "AI DETAIL MODAL CLOSE"
                );


            }


        }


    }
);








/* ==========================================================
   AI DETAIL HOVER PREVIEW - 마지막 실제 질문/답변
========================================================== */

document.addEventListener(
    "mouseover",
    function(e){

        const btn = e.target.closest("#ai-detail-btn");
        if(!btn){
            return;
        }

        let preview = document.getElementById("ai-detail-preview");

        if(!preview){
            preview = document.createElement("div");
            preview.id = "ai-detail-preview";
            preview.className = `
                fixed z-[9999] w-96 bg-white border border-blue-100
                rounded-xl shadow-xl p-4 text-xs text-gray-700
            `;
            document.body.appendChild(preview);
        }

        const escapeHtml = value => String(value ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");

        const question = window.sbLastAIQuestion ||
            document.getElementById("ai-question")?.value?.trim() ||
            "AI 질문";

        const answerHtml = window.sbLastAIAnswer ||
            "먼저 AI 질문을 실행하면 실제 답변 미리보기가 표시됩니다.";

        preview.innerHTML = `
            <div class="mb-3">
                <div class="font-bold text-blue-700">📊 AI 답변 미리보기</div>
            </div>
            <div class="text-[10px] text-gray-400 mb-1">질문</div>
            <div class="font-bold text-gray-800 mb-2">${escapeHtml(question)}</div>
            <div class="text-[10px] text-gray-400 mb-1">답변</div>
            <div class="text-[11px] leading-5 max-h-56 overflow-y-auto pr-1">${answerHtml}</div>
            <div class="mt-3 pt-2 border-t text-[10px] text-blue-600 text-right">클릭하면 전체 답변을 확인합니다 →</div>
        `;

        const rect = btn.getBoundingClientRect();
        const maxLeft = window.innerWidth - 400;
        preview.style.left = Math.max(12, Math.min(rect.left, maxLeft)) + "px";
        preview.style.top = (rect.bottom + 8) + "px";
        preview.style.display = "block";
    }
);


/* ==========================================================
   AI DETAIL HOVER OUT
========================================================== */


document.addEventListener(
    "mouseout",
    function(e){


        const btn =
            e.target.closest(
                "#ai-detail-btn"
            );



        if(!btn){

            return;

        }



        const preview =
            document.getElementById(
                "ai-detail-preview"
            );



        if(preview){


            preview.style.display =
                "none";


        }


    }
);

/* ==========================================================
   AI DETAIL CLICK TEST
========================================================== */

document.addEventListener(
    "click",
    function(e){

        const btn =
            e.target.closest(
                "#ai-detail-btn"
            );


        if(btn){

            console.log(
                "🔥 AI DETAIL CLICK TEST OK"
            );

        }

    }
);

/* ==========================================================
   시장분석 상세보기 : AI 질문 상세보기와 완전 분리
========================================================== */
document.addEventListener("click", function(event){
    if(event.target.closest("#market-detail-btn")){
        event.preventDefault();
        const modal = document.getElementById("market-detail-modal");
        if(modal){
            modal.classList.remove("hidden");
            modal.classList.add("flex");
        }
        return;
    }

    if(event.target.closest("#market-detail-close")){
        const modal = document.getElementById("market-detail-modal");
        if(modal){
            modal.classList.add("hidden");
            modal.classList.remove("flex");
        }
        return;
    }

    const modal = document.getElementById("market-detail-modal");
    if(modal && event.target === modal){
        modal.classList.add("hidden");
        modal.classList.remove("flex");
    }
});
