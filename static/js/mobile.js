const MobileState = {
  product: "deposit",
  period: "12",
  data: {
    deposit: null,
    isa: null,
    irp: null
  },
  topExpanded: false,
  productPeriod: "12",
  products: [],
  dataBasis: null,
  dataBasisKind: "확인시각",
  clockTimer: null
};

const $ = (id) => document.getElementById(id);

// Kakao Developers > 플랫폼 키 > JavaScript 키 값을 아래에 입력하세요.
// JavaScript 키는 웹에서 사용하는 공개 식별키이며 Admin 키/REST API 키를 넣으면 안 됩니다.
const KAKAO_JAVASCRIPT_KEY = "9f12a43c394b689a99d49dd633f4d8ca";

function number(value){
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function pct(value, digits=2){
  const n = number(value);
  return n === null ? "-" : `${n.toFixed(digits)}%`;
}

function gap(value){
  const n = number(value);

  if(n === null || Math.abs(n) < 0.00001){
    return {html:"0.00%p", cls:"neutral"};
  }

  if(n > 0){
    return {html:`+${n.toFixed(2)}%p`, cls:"positive"};
  }

  return {
    html:`▲${Math.abs(n).toFixed(2)}%p`,
    cls:"negative"
  };
}

function normalizeBankCore(name){
  return String(name || "")
    .replace(/저축은행|금융|주식회사|㈜|\s/g,"")
    .toUpperCase();
}

function displayBankName(name){
  return String(name || "-")
    .replace(/저축은행/g,"")
    .replace(/\s{2,}/g," ")
    .trim();
}

function isWoori(name){
  return String(name || "").includes("우리금융");
}

function disclosure(value){
  return String(value || "")
    .trim()
    .replace(/\s*기준\s*$/g,"")
    .replace(/\s{2,}/g," ") || "-";
}

function disclosureSortValue(value){
  if(!value) return 0;
  const t = Date.parse(String(value).replace(/\./g,"-"));
  return Number.isFinite(t) ? t : 0;
}

async function api(url, options){
  const response = await fetch(url, options);

  if(!response.ok){
    throw new Error(`${url} ${response.status}`);
  }

  return await response.json();
}

function toast(message){
  const el = $("mobile-toast");
  el.textContent = message;
  el.classList.add("show");

  clearTimeout(window.__mobileToastTimer);

  window.__mobileToastTimer =
    setTimeout(
      () => el.classList.remove("show"),
      1600
    );
}


function currentLabel(){
  if(MobileState.product === "deposit") return "정기예금";
  if(MobileState.product === "isa") return "ISA";
  return "퇴직연금(IRP)";
}

function displayRateOrDash(value,digits=2){
  const n = number(value);
  return n === null || n <= 0 ? "-" : `${n.toFixed(digits)}%`;
}

function formatClockDateTime(date){
  const d = date instanceof Date ? date : new Date(date);
  if(Number.isNaN(d.getTime())) return "-";
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth()+1).padStart(2,"0");
  const dd = String(d.getDate()).padStart(2,"0");
  const hh = String(d.getHours()).padStart(2,"0");
  const mi = String(d.getMinutes()).padStart(2,"0");
  const ss = String(d.getSeconds()).padStart(2,"0");
  return `${yyyy}-${mm}-${dd} ${hh}:${mi}:${ss}`;
}

function extractDataBasis(...payloads){
  for(const payload of payloads){
    if(!payload) continue;
    const candidates = [
      payload.last_update,
      payload.updated_at,
      payload.update_time,
      payload.data_basis,
      payload.data_date,
      payload.generated_at
    ];
    for(const value of candidates){
      if(value){
        // 서버가 Asia/Seoul 기준 문자열을 제공하므로 브라우저가 임의 timezone 변환하지 않도록 그대로 표시한다.
        return {value:String(value), kind:"데이터 업데이트 시간"};
      }
    }
  }
  return {value:formatClockDateTime(new Date()), kind:"확인시각"};
}

function startMobileClock(){
  if(MobileState.clockTimer){
    clearInterval(MobileState.clockTimer);
  }

  const tick = ()=>{
    const el = $("mobile-live-clock");
    if(!el) return;
    const now = new Date();
    const hh = String(now.getHours()).padStart(2,"0");
    const mi = String(now.getMinutes()).padStart(2,"0");
    const ss = String(now.getSeconds()).padStart(2,"0");
    el.textContent = `현재 ${hh}:${mi}:${ss}`;
  };

  tick();
  MobileState.clockTimer = setInterval(tick,1000);
}

function setMobileDataBasis(basis){
  MobileState.dataBasis = basis?.value || formatClockDateTime(new Date());
  MobileState.dataBasisKind = basis?.kind || "확인시각";

  // 상단 UI는 정책상 "데이터 업데이트 00:30 · 현재 HH:MM:SS"로 고정 표기.
  // 실제 수집/공시 기준시각은 보고서 및 Data Source 영역에서 별도 사용한다.
}

function mobileSourceLabel(){
  if(MobileState.product === "deposit"){
    return "저축은행중앙회 비교공시";
  }
  return "각 저축은행 홈페이지";
}

function renderMobileDataSource(data){
  const el = $("mobile-source-note");
  if(!el) return;

  const sourceItems = (data?.items || [])
    .filter(item => item?.source)
    .slice(0,2);

  const sourceLinks = sourceItems
    .map(item=>{
      const url = String(item.source || "");
      if(!/^https?:\/\//i.test(url)) return "";
      return `<a href="${url}" target="_blank" rel="noopener">${displayBankName(item.bank)} 원문</a>`;
    })
    .filter(Boolean);

  const basis = MobileState.dataBasis || "-";

  el.innerHTML = `
    <b>데이터 출처</b> · ${mobileSourceLabel()}
    <br>
    ${MobileState.dataBasisKind} ${basis}
    ${sourceLinks.length ? `<br>${sourceLinks.join(" · ")}` : ""}
    <br>
    공시일은 각 기관의 공식 공시 기준이며, 금리 미확인 값은 0%가 아닌 <b>-</b>로 표시합니다.
  `;
}

function quickQuestionConfig(){
  if(MobileState.product === "deposit"){
    return [
      ["당행 경쟁력","우리금융 경쟁력 알려줘"],
      ["최고금리 Gap","시장 최고금리와 우리금융 차이 알려줘"],
      ["금융지주 현황","금융지주 저축은행 현황 알려줘"],
      ["오늘 변동","오늘 금리 변동 핵심 알려줘"],
      ["상위 경쟁사","우리금융보다 금리가 높은 곳 알려줘"],
      ["시장 평균 비교","시장 평균과 우리금융을 비교해줘"]
    ];
  }

  const label = currentLabel();

  return [
    ["당행 경쟁력",`우리금융 ${label} 경쟁력 알려줘`],
    ["최고금리 Gap",`${label} 시장 최고금리와 우리금융 차이 알려줘`],
    ["금융지주 현황",`${label} 금융지주 저축은행 현황 알려줘`],
    ["최근 공시",`${label} 최근 공시 핵심 알려줘`],
    ["상위 경쟁사",`${label}에서 우리금융보다 높은 곳 알려줘`],
    ["시장 평균 비교",`${label} 시장 평균과 우리금융을 비교해줘`]
  ];
}

function renderQuickQuestions(){
  const box = $("mobile-quick-questions");
  if(!box) return;

  box.innerHTML = quickQuestionConfig()
    .map(([label,question])=>
      `<button data-question="${question.replace(/"/g,"&quot;")}">${label}</button>`
    )
    .join("");

  box.querySelectorAll("button").forEach(button=>{
    button.addEventListener("click",()=>{
      $("mobile-ai-question").value = button.dataset.question || "";
      sendAI();
    });
  });
}

function scrollDashboardTop(){
  window.scrollTo({
    top: 0,
    behavior: "smooth"
  });
}

/* =========================================================
   PC DASHBOARD-COMPATIBLE NORMALIZATION
========================================================= */

function normalizeAlternativeItem(item,index=0){
  const rawRate =
    item?.rate ??
    item?.intr_rate2 ??
    item?.max_rate ??
    item?.intr_rate;

  const rate =
    rawRate === null ||
    rawRate === undefined ||
    rawRate === ""
      ? null
      : Number(rawRate);

  return {
    ...item,
    bank:
      item?.bank ??
      item?.bank_name ??
      item?.kor_co_nm ??
      "-",
    product:
      item?.product ??
      item?.product_name ??
      item?.fin_prdt_nm ??
      null,
    rate:Number.isFinite(rate) ? rate : null,
    disclosure_date:item?.disclosure_date ?? null,
    rate_month:item?.rate_month ?? null,
    source:item?.source ?? item?.source_url ?? item?.url ?? null,
    period:item?.period ?? `${MobileState.productPeriod || MobileState.period}개월`,
    rank:item?.rank ?? index+1,
    change:Number(item?.change ?? item?.diff ?? 0) || 0
  };
}

function validAlternativeItems(items){
  return (Array.isArray(items) ? items : [])
    .map(normalizeAlternativeItem)
    .filter(item => Number.isFinite(Number(item.rate)) && Number(item.rate) > 0)
    .sort((a,b)=>Number(b.rate)-Number(a.rate));
}

function buildAlternativeState(payload,type){
  const source =
    Array.isArray(payload)
      ? payload
      : Array.isArray(payload?.items)
        ? payload.items
        : [];

  const items = source.map(normalizeAlternativeItem);
  const ranked = validAlternativeItems(items);

  const woori =
    ranked.find(item => isWoori(item.bank)) ||
    items.find(item => isWoori(item.bank)) ||
    null;

  const wr = number(woori?.rate);
  const rates = ranked.map(item => Number(item.rate));

  const max = rates.length ? Math.max(...rates) : null;
  const min = rates.length ? Math.min(...rates) : null;
  const avg = rates.length
    ? rates.reduce((a,b)=>a+b,0)/rates.length
    : null;

  const rankIndex =
    woori
      ? ranked.findIndex(
          item =>
            normalizeBankCore(item.bank) === normalizeBankCore(woori.bank)
        )
      : -1;

  return {
    type,
    raw:payload,
    items,
    ranked:ranked.map((item,index)=>({...item,rank:index+1})),
    woori,
    wr,
    max,
    min,
    avg,
    rank:rankIndex >= 0 ? rankIndex+1 : null,
    total:ranked.length,
    disclosed:items.filter(
      item => item.disclosure_date || item.rate_month
    ).length,
    lastHead:"공시일"
  };
}

/* =========================================================
   DEPOSIT — SAME API/RULES AS PC DASHBOARD
========================================================= */

async function loadDeposit(){
  /*
   * PC dashboard source of truth:
   * hero/KPI      => /api/kpi + /api/woori
   * Market TOP10  => /api/rates
   * movement      => /api/rate-changes
   *
   * 모바일에서 자체적으로 전체상품을 다시 rank 계산하지 않는다.
   */
  const [kpi, woori, rates, changes] =
    await Promise.all([
      api("/api/kpi"),
      api("/api/woori"),
      api("/api/rates"),
      api("/api/rate-changes")
    ]);

  const ranked =
    (Array.isArray(rates) ? rates : (rates?.top10 || []))
      .map((item,index)=>({
        ...item,
        bank:
          item.bank ??
          item.bank_name ??
          item.kor_co_nm ??
          "-",
        product:
          item.product ??
          item.product_name ??
          item.fin_prdt_nm ??
          null,
        rate:number(
          item.rate ??
          item.intr_rate2 ??
          item.max_rate ??
          item.intr_rate ??
          item.base_rate
        ),
        change:number(
          item.diff ??
          item.change ??
          item.change_value ??
          0
        ) ?? 0,
        rank:index+1
      }));

  setMobileDataBasis(extractDataBasis(kpi,woori));

  MobileState.data.deposit = {
    type:"deposit",
    kpi,
    woori,
    ranked,
    changes,
    wr:number(woori?.rate),
    max:number(kpi?.max_rate ?? kpi?.highest_rate),
    min:number(kpi?.min_rate ?? kpi?.lowest_rate),
    avg:number(kpi?.average_rate),
    rank:number(woori?.market_rank ?? woori?.rank),
    total:number(woori?.market_total ?? kpi?.bank_count),
    lastHead:"전일比"
  };
}

/* =========================================================
   ISA / IRP — SAME NORMALIZATION AS PC DASHBOARD
========================================================= */

async function loadAlternative(type){
  const payload =
    await api(
      `/api/${type}?period=${encodeURIComponent(MobileState.period)}`
    );

  setMobileDataBasis(extractDataBasis(payload));

  MobileState.data[type] =
    buildAlternativeState(
      payload,
      type
    );
}

async function ensureData(type){
  if(type === "deposit"){
    await loadDeposit();
  }else{
    await loadAlternative(type);
  }
}

/* =========================================================
   HERO
========================================================= */

function buildBrief(data){
  if(!data){
    return "시장 데이터를 확인 중입니다.";
  }

  if(data.wr === null){
    return "우리금융 금리가 확인되지 않아 경쟁력 분석을 대기하고 있습니다.";
  }

  const topGap =
    data.max === null
      ? null
      : data.wr - data.max;

  const avgGap =
    data.avg === null
      ? null
      : data.wr - data.avg;

  if(data.rank === 1){
    const second =
      data.ranked.find(item => !isWoori(item.bank));

    const secondGap =
      second && Number.isFinite(Number(second.rate))
        ? data.wr - Number(second.rate)
        : null;

    return [
      `우리금융 ${pct(data.wr)}로 시장 1위입니다.`,
      secondGap === null
        ? ""
        : `2위 대비 ${Math.abs(secondGap).toFixed(2)}%p ${secondGap >= 0 ? "높고" : "낮고"},`,
      avgGap === null
        ? ""
        : `시장 평균 대비 ${avgGap >= 0 ? "+" : ""}${avgGap.toFixed(2)}%p입니다.`,
      "상위권 금리와 공시 변화를 중심으로 모니터링합니다."
    ].filter(Boolean).join(" ");
  }

  return [
    `우리금융 ${data.rank || "-"}위 · ${pct(data.wr)}.`,
    topGap === null
      ? ""
      : `시장 최고 대비 ${Math.abs(topGap).toFixed(2)}%p ${topGap < 0 ? "낮고" : "높고"},`,
    avgGap === null
      ? ""
      : `시장 평균 대비 ${avgGap >= 0 ? "+" : ""}${avgGap.toFixed(2)}%p입니다.`,
    "상위권과의 Gap 변화를 우선 확인합니다."
  ].filter(Boolean).join(" ");
}

function renderHero(data){
  $("hero-product-label").textContent =
    `${currentLabel()} ${MobileState.period}개월`;

  $("hero-woori-rate").textContent =
    pct(data?.wr);

  const heroProduct =
    data?.woori?.product ||
    data?.woori?.product_name ||
    data?.woori?.fin_prdt_nm ||
    "-";

  const heroProductEl = $("hero-woori-product");
  if(heroProductEl){
    heroProductEl.textContent =
      heroProduct === "-"
        ? "대표상품 -"
        : `대표상품 · ${heroProduct}`;
  }

  $("hero-rank-pill").textContent =
    data?.rank
      ? `${data.rank}위`
      : "-위";

  const topGap =
    data &&
    data.wr !== null &&
    data.max !== null
      ? data.wr - data.max
      : null;

  const topGapView = gap(topGap);
  const topGapEl = $("hero-gap-top");

  topGapEl.innerHTML = topGapView.html;
  topGapEl.className = topGapView.cls;

  $("hero-ai-brief").textContent =
    buildBrief(data);

  $("kpi-top-rate").textContent =
    pct(data?.max);

  $("kpi-top-bank").textContent =
    data?.ranked?.[0]
      ? displayBankName(data.ranked[0].bank)
      : "-";

  $("kpi-average-rate").textContent =
    pct(data?.avg);

  const avgGap =
    data &&
    data.wr !== null &&
    data.avg !== null
      ? data.wr - data.avg
      : null;

  const avgGapView = gap(avgGap);

  $("kpi-average-gap").innerHTML =
    `당행 ${avgGapView.html}`;

  $("kpi-average-gap").className =
    avgGapView.cls;

  $("kpi-market-rank").textContent =
    data?.rank
      ? `${data.rank}위`
      : "-";

  $("kpi-market-total").textContent =
    data?.total
      ? `${data.total}개 기관`
      : "-";

  if(MobileState.product === "deposit"){
    $("kpi-fourth-label").textContent =
      "금리 변동";

    $("kpi-fourth-value").textContent =
      `${Number(data?.changes?.change_count || 0)}건`;

    $("kpi-fourth-sub").textContent =
      `상승 ${Number(data?.changes?.up_count || 0)} / 하락 ${Number(data?.changes?.down_count || 0)}`;
  }else{
    $("kpi-fourth-label").textContent =
      "공시 확인";

    $("kpi-fourth-value").textContent =
      `${data?.disclosed || 0}개`;

    $("kpi-fourth-sub").textContent =
      `전체 ${data?.items?.length || 0}개 기관`;
  }

  $("mobile-market-label").textContent =
    `${currentLabel()} ${MobileState.period}개월 시장현황`;
}

/* =========================================================
   MARKET TOP5 / TOP10
========================================================= */

function rankLastValue(item,data){
  if(data.type === "deposit"){
    const change = number(item.change);

    if(change === null || change === 0){
      return {
        text:"-",
        cls:"neutral"
      };
    }

    if(change > 0){
      return {
        text:`+${change.toFixed(2)}%p`,
        cls:"positive"
      };
    }

    return {
      text:`▲${Math.abs(change).toFixed(2)}%p`,
      cls:"negative"
    };
  }

  return {
    text:disclosure(
      item.disclosure_date ||
      item.rate_month
    ),
    cls:""
  };
}

function renderRanking(data){
  $("market-last-head").textContent =
    data?.lastHead || "전일比";

  const list =
    $("market-ranking-list");

  const maxCount =
    MobileState.topExpanded
      ? 10
      : 5;

  const rows =
    (data?.ranked || [])
      .slice(0,maxCount);

  if(!rows.length){
    list.innerHTML =
      '<div class="loading">시장 데이터가 없습니다.</div>';
    return;
  }

  list.innerHTML =
    rows.map((item,index)=>{
      const woori =
        isWoori(item.bank);

      const last =
        rankLastValue(
          item,
          data
        );

      return `
        <div class="rank-row ${index < 3 ? "top3" : ""} ${woori ? "woori" : ""}">
          <div>
            <span class="rank-badge">${item.rank ?? index+1}</span>
          </div>
          <div class="bank">${displayBankName(item.bank)}</div>
          <div class="rate">${pct(item.rate)}</div>
          <div class="last ${last.cls}">${last.text}</div>
        </div>
      `;
    }).join("");

  $("toggle-top10").textContent =
    MobileState.topExpanded
      ? "TOP5 보기"
      : "TOP10 보기";
}

/* =========================================================
   WATCH
========================================================= */

function changeMagnitude(item){
  return number(
    item?.change ??
    item?.change_value
  ) || 0;
}

function renderWatch(data){
  const target =
    $("watch-content");

  if(data.type === "deposit"){
    $("watch-title").textContent =
      "금리 변동 브리핑";

    const ups =
      Array.isArray(data.changes?.up_top5)
        ? data.changes.up_top5
        : [];

    const downs =
      Array.isArray(data.changes?.down_top5)
        ? data.changes.down_top5
        : [];

    const strongestUp =
      [...ups].sort(
        (a,b) => changeMagnitude(b) - changeMagnitude(a)
      )[0];

    const strongestDown =
      [...downs].sort(
        (a,b) =>
          Math.abs(changeMagnitude(b)) -
          Math.abs(changeMagnitude(a))
      )[0];

    const upCount =
      Number(data.changes?.up_count ?? ups.length ?? 0);

    const downCount =
      Number(data.changes?.down_count ?? downs.length ?? 0);

    const totalCount =
      Number(
        data.changes?.change_count ??
        (upCount + downCount)
      );

    const allMoves = [...ups,...downs];

    const wooriMove =
      allMoves.find(
        item => isWoori(item.bank)
      );

    const wooriChange =
      wooriMove
        ? changeMagnitude(wooriMove)
        : 0;

    const direction =
      totalCount === 0
        ? "변동 없음"
        : downCount > upCount
          ? "인하 우세"
          : upCount > downCount
            ? "인상 우세"
            : "혼조";

    const strongestUpText =
      strongestUp
        ? `${displayBankName(strongestUp.bank)} <span class="change-up">+${Math.abs(changeMagnitude(strongestUp)).toFixed(2)}%p</span>`
        : '<span class="change-flat">상승 없음</span>';

    const strongestDownText =
      strongestDown
        ? `${displayBankName(strongestDown.bank)} <span class="change-down">▲${Math.abs(changeMagnitude(strongestDown)).toFixed(2)}%p</span>`
        : '<span class="change-flat">하락 없음</span>';

    const wooriText =
      wooriMove
        ? `우리금융 ${
            wooriChange > 0
              ? `<span class="change-up">+${Math.abs(wooriChange).toFixed(2)}%p</span>`
              : wooriChange < 0
                ? `<span class="change-down">▲${Math.abs(wooriChange).toFixed(2)}%p</span>`
                : '<span class="change-flat">유지</span>'
          }`
        : `우리금융 ${pct(data.wr)} · <span class="change-flat">금리 유지</span>`;

    let aiText =
      "시장 변동이 제한적입니다. 당행 금리와 시장 상단 Gap을 중심으로 모니터링합니다.";

    if(downCount > upCount){
      aiText =
        "인하 조정이 시장 전반에 우세합니다. 상위금리권 인하가 이어질 경우 시장 최고와 당행 간 Gap 축소 여부를 주시할 필요가 있습니다.";
    }
    else if(upCount > downCount){
      aiText =
        "일부 저축은행의 수신 경쟁 강화가 나타납니다. 상위권 추가 인상 여부와 당행 경쟁력 변화를 함께 확인할 필요가 있습니다.";
    }
    else if(totalCount > 0){
      aiText =
        "상승과 하락이 혼재한 시장입니다. 전체 방향성보다 상위금리권과 우리금융 인접 순위의 변동을 우선 확인하는 것이 유효합니다.";
    }

    target.innerHTML = `
      <div class="movement-brief">
        <div class="movement-summary">
          <strong>${direction}</strong>
          <div class="movement-counts">
            총 ${totalCount}건 ·
            <span class="change-up">상승 ${upCount}</span> /
            <span class="change-down">하락 ${downCount}</span>
          </div>
        </div>

        <div class="movement-detail-grid">
          <div class="movement-detail">
            <span>최대 상승</span>
            <strong>${strongestUpText}</strong>
          </div>
          <div class="movement-detail">
            <span>최대 하락</span>
            <strong>${strongestDownText}</strong>
          </div>
        </div>

        <div class="woori-movement">
          <b>우리금융</b> · ${wooriText.replace(/^우리금융\s*/,"")}
        </div>

        <div class="movement-ai">
          <b>AI 판단</b><br>
          ${aiText}
        </div>
      </div>
    `;

    return;
  }

  $("watch-title").textContent =
    "최근 공시 TOP5";

  const recent =
    [...(data.ranked || [])]
      .filter(
        item =>
          item.disclosure_date ||
          item.rate_month
      )
      .sort(
        (a,b) =>
          Number(b.rate) -
          Number(a.rate)
      )
      .slice(0,5);

  target.innerHTML =
    recent.length
      ? recent.map((item,index)=>`
          <div class="product-row ${isWoori(item.bank) ? "woori-product woori-highlight-mobile" : ""}">
            <div class="product-main">
              <div class="product-bank">${index+1}. ${displayBankName(item.bank)}</div>
              <div class="product-name ${item.product ? "" : "product-missing"}">
                ${item.product || "상품명 미수집"}
              </div>
            </div>
            <div class="product-meta">
              <strong>${pct(item.rate)}</strong>
              <small>${disclosure(item.disclosure_date || item.rate_month)}</small>
            </div>
          </div>
        `).join("")
      : '<div class="loading">공시 데이터가 없습니다.</div>';
}

/* =========================================================
   PRODUCTS — NO FAKE PRODUCT NAME FALLBACK
========================================================= */

function normalizePeriod(value){
  return String(value || "")
    .replace(/\s/g,"")
    .replace(/개월/g,"");
}

function productBank(item){
  return (
    item?.bank ??
    item?.bank_name ??
    item?.kor_co_nm ??
    "-"
  );
}

function actualProductName(item){
  const name =
    item?.product ??
    item?.product_name ??
    item?.fin_prdt_nm ??
    null;

  const text =
    String(name || "").trim();

  return text || null;
}

function productRate(item){
  return number(
    item?.rate ??
    item?.rate_12m ??
    item?.intr_rate2 ??
    item?.max_rate
  );
}

async function loadProducts(){
  const data =
    MobileState.data[
      MobileState.product
    ];

  const explorerPeriod =
    String(
      MobileState.productPeriod ||
      MobileState.period ||
      "12"
    );

  if(MobileState.product === "deposit"){
    try{
      const payload =
        await api("/api/products");

      const source =
        Array.isArray(payload)
          ? payload
          : (
              payload?.items ||
              payload?.products ||
              []
            );

      MobileState.products =
        source.filter(item=>{
          const period =
            normalizePeriod(
              item.period ??
              item.term ??
              item.save_trm
            );

          return (
            !period ||
            period === explorerPeriod
          );
        });
    }catch(error){
      console.error(
        "MOBILE PRODUCTS ERROR",
        error
      );

      MobileState.products =
        explorerPeriod === MobileState.period
          ? (data?.ranked || [])
          : [];
    }
  }else{
    try{
      const payload =
        await api(
          `/api/${MobileState.product}?period=${encodeURIComponent(explorerPeriod)}`
        );

      const source =
        Array.isArray(payload)
          ? payload
          : (payload?.items || []);

      MobileState.products =
        source.map(
          (item,index) =>
            normalizeAlternativeItem(item,index)
        );
    }catch(error){
      console.error(
        "MOBILE ALTERNATIVE PRODUCTS ERROR",
        error
      );

      MobileState.products =
        explorerPeriod === MobileState.period
          ? (data?.items || [])
          : [];
    }
  }

  renderProducts();
}

function renderProducts(){
  const query =
    String(
      $("mobile-product-search").value ||
      ""
    )
      .trim()
      .toLowerCase();

  const items =
    (MobileState.products || [])
      .filter(item=>{
        if(!query){
          return true;
        }

        return (
          `${productBank(item)} ${actualProductName(item) || ""}`
            .toLowerCase()
            .includes(query)
        );
      });

  $("mobile-product-list").innerHTML =
    items
      .slice(0,80)
      .map(item=>{
        const bank =
          productBank(item);

        const product =
          actualProductName(item);

        const isWooriProduct =
          isWoori(bank);

        return `
          <div class="product-row ${isWooriProduct ? "woori-product woori-highlight-mobile" : ""}">
            <div class="product-main">
              <div class="product-bank">${displayBankName(bank)}</div>
              <div class="product-name ${product ? "" : "product-missing"}">
                ${product || "상품명 미수집"}
              </div>
            </div>

            <div class="product-meta">
              <strong>${displayRateOrDash(productRate(item))}</strong>
              <small>
                ${
                  MobileState.product === "deposit"
                    ? `${MobileState.period}개월`
                    : disclosure(
                        item.disclosure_date ||
                        item.rate_month
                      )
                }
              </small>
            </div>
          </div>
        `;
      }).join("")
    ||
    '<div class="loading">검색 결과가 없습니다.</div>';
}

/* =========================================================
   AI
========================================================= */

async function sendAI(){
  const textarea =
    $("mobile-ai-question");

  const question =
    String(
      textarea.value || ""
    ).trim();

  if(!question){
    return;
  }

  const answer =
    $("mobile-ai-answer");

  answer.textContent =
    "AI가 시장 데이터를 분석하고 있습니다...";

  const contextPrefix =
    MobileState.product === "deposit"
      ? `[정기예금 ${MobileState.period}개월]`
      : MobileState.product === "isa"
        ? `[ISA ${MobileState.period}개월]`
        : `[퇴직연금 IRP ${MobileState.period}개월]`;

  try{
    const data =
      await api(
        "/api/ai/search",
        {
          method:"POST",
          headers:{
            "Content-Type":"application/json"
          },
          body:JSON.stringify({
            question:
              `${contextPrefix} ${question}`,
            category:
              MobileState.product,
            period:
              MobileState.period
          })
        }
      );

    answer.textContent =
      data?.answer ||
      data?.result ||
      data?.response ||
      "답변 결과가 없습니다.";
  }catch(error){
    console.error(
      "MOBILE AI ERROR",
      error
    );

    answer.textContent =
      "AI 답변을 불러오지 못했습니다.";
  }
}

/* =========================================================
   PRODUCT SWITCH
========================================================= */

function updateTabUI(){
  document
    .querySelectorAll(".product-tab")
    .forEach(button=>{
      button.classList.toggle(
        "is-active",
        button.dataset.product ===
          MobileState.product
      );
    });
}

async function switchProduct(type,{
  scrollTop=true
}={}){
  if(!["deposit","isa","irp"].includes(type)){
    return;
  }

  if(scrollTop){
    scrollDashboardTop();
  }

  MobileState.product =
    type;

  MobileState.topExpanded =
    false;

  updateTabUI();

  $("hero-ai-brief").textContent =
    "시장 데이터를 불러오고 있습니다.";

  $("market-ranking-list").innerHTML =
    '<div class="loading">시장 데이터 로딩 중...</div>';

  try{
    await ensureData(type);

    const data =
      MobileState.data[type];

    renderHero(data);
    renderRanking(data);
    renderWatch(data);
    renderQuickQuestions();
    await loadProducts();
    renderMobileDataSource(data);
    setUpdateTime();
  }catch(error){
    console.error(
      "MOBILE PRODUCT SWITCH ERROR",
      error
    );

    toast(
      "데이터를 불러오지 못했습니다."
    );
  }
}

function setUpdateTime(){
  if(!MobileState.dataBasis){
    setMobileDataBasis({
      value:formatClockDateTime(new Date()),
      kind:"확인시각"
    });
  }
}

/* =========================================================
   KAKAO SHARE
========================================================= */

function initKakaoShare(){
  if(
    !KAKAO_JAVASCRIPT_KEY ||
    KAKAO_JAVASCRIPT_KEY ===
      "PASTE_YOUR_KAKAO_JAVASCRIPT_KEY_HERE"
  ){
    console.warn(
      "KAKAO SHARE: JavaScript 키가 아직 설정되지 않았습니다."
    );
    return false;
  }

  if(
    typeof window.Kakao === "undefined"
  ){
    console.warn(
      "KAKAO SHARE: Kakao SDK를 불러오지 못했습니다."
    );
    return false;
  }

  try{
    if(!window.Kakao.isInitialized()){
      window.Kakao.init(
        KAKAO_JAVASCRIPT_KEY
      );
    }

    return window.Kakao.isInitialized();
  }
  catch(error){
    console.error(
      "KAKAO INIT ERROR",
      error
    );
    return false;
  }
}


function buildKakaoShareText(){
  const data = MobileState.data[MobileState.product];
  const label = currentLabel();
  const period = MobileState.period;
  const wooriRate = displayRateOrDash(data?.wr);
  const topRate = displayRateOrDash(data?.max);
  const topBank = data?.ranked?.[0]
    ? displayBankName(data.ranked[0].bank)
    : "-";
  const rankText = data?.rank
    ? (data?.total ? `${data.rank}위 / ${data.total}개` : `${data.rank}위`)
    : "-";
  const wooriProduct = data?.woori?.product || data?.woori?.product_name || "-";
  const topGap = number(data?.wr) !== null && number(data?.max) !== null
    ? number(data.wr) - number(data.max)
    : null;
  const gapText = topGap === null
    ? "-"
    : topGap >= 0
      ? `+${Math.abs(topGap).toFixed(2)}%p`
      : `▲${Math.abs(topGap).toFixed(2)}%p`;

  const divider = "━━━━━━━━━━━━";
  const lines = [
    "☀️ SBRate Morning Brief",
    `데이터 업데이트 기준 : ${mobileDataBasis()} KST`,
    "",
    divider,
    `📌 ${label} ${period}개월`,
    divider,
    `우리금융 : ${wooriRate} · ${rankText}`,
    `대표상품 : ${wooriProduct}`,
    `시장 최고 : ${topBank} ${topRate}`,
    `최고 대비 : ${gapText}`,
  ];

  if(MobileState.product === "deposit"){
    const c = data?.changes || {};
    lines.push(`전일 변동 : 상승 ${c.up_count ?? 0} / 하락 ${c.down_count ?? 0}`);
  }else{
    const disclosure = data?.woori?.disclosure_date || "미확인";
    lines.push(`우리금융 공시일 : ${disclosure}`);
  }

  lines.push("", `🤖 ${buildBrief(data)}`, "", "상세 현황은 모바일 대시보드에서 확인하세요.");
  return lines.join("\n");
}

function mobileDashboardShareUrl(){
  return "https://sbrate.onrender.com/mobile";
}


function shareKakao(){
  const data =
    MobileState.data[
      MobileState.product
    ];

  if(!data){
    toast(
      "시장 데이터를 불러온 후 공유해주세요."
    );
    return;
  }

  if(!initKakaoShare()){
    if(
      KAKAO_JAVASCRIPT_KEY ===
      "PASTE_YOUR_KAKAO_JAVASCRIPT_KEY_HERE"
    ){
      toast(
        "카카오 JavaScript 키를 먼저 설정해주세요."
      );
    }
    else{
      toast(
        "카카오톡 공유 모듈을 불러오지 못했습니다."
      );
    }

    return;
  }

  const shareUrl =
    mobileDashboardShareUrl();

  try{
    window.Kakao.Share.sendDefault({
      objectType:"text",
      text:buildKakaoShareText(),
      link:{
        mobileWebUrl:shareUrl,
        webUrl:shareUrl
      },
      buttonTitle:
        "모바일 대시보드 보기"
    });
  }
  catch(error){
    console.error(
      "KAKAO SHARE ERROR",
      error
    );

    toast(
      "카카오톡 공유를 실행하지 못했습니다."
    );
  }
}


/* =========================================================
   NAV / ERROR REPORT
========================================================= */

function initNavObserver(){
  const sections =
    [...document.querySelectorAll(".section-block")];

  const navs =
    [...document.querySelectorAll(".nav-item")];

  const observer =
    new IntersectionObserver(
      entries=>{
        const visible =
          entries
            .filter(entry=>entry.isIntersecting)
            .sort(
              (a,b) =>
                b.intersectionRatio -
                a.intersectionRatio
            )[0];

        if(!visible){
          return;
        }

        navs.forEach(nav=>{
          nav.classList.toggle(
            "is-active",
            nav.dataset.section ===
              visible.target.id
          );
        });
      },
      {
        rootMargin:
          "-30% 0px -55% 0px",
        threshold:[
          0,
          .15,
          .3
        ]
      }
    );

  sections.forEach(
    section =>
      observer.observe(section)
  );
}

function initErrorReport(){
  const modal =
    $("mobile-error-modal");

  $("mobile-error-report")
    .addEventListener(
      "click",
      () =>
        modal.classList.remove("hidden")
    );

  $("mobile-error-close")
    .addEventListener(
      "click",
      () =>
        modal.classList.add("hidden")
    );

  $("mobile-error-submit")
    .addEventListener(
      "click",
      async ()=>{
        const message =
          String(
            $("mobile-error-message").value ||
            ""
          ).trim();

        if(!message){
          toast(
            "오류 내용을 입력해주세요."
          );
          return;
        }

        try{
          const data =
            await api(
              "/api/error-report",
              {
                method:"POST",
                headers:{
                  "Content-Type":"application/json"
                },
                body:JSON.stringify({
                  category:
                    MobileState.product,
                  product:
                    `${currentLabel()} Mobile`,
                  period:
                    MobileState.period,
                  error_type:
                    $("mobile-error-type").value,
                  message,
                  page_url:
                    location.href,
                  user_agent:
                    navigator.userAgent
                })
              }
            );

          $("mobile-error-message").value =
            "";

          modal.classList.add("hidden");

          toast(
            `접수 완료 ${data?.id || ""}`.trim()
          );
        }catch(error){
          console.error(
            "MOBILE ERROR REPORT ERROR",
            error
          );

          toast(
            "오류 제보 등록에 실패했습니다."
          );
        }
      }
    );
}


/* =========================================================
   EXECUTIVE REPORT / PDF
========================================================= */

function mobileDataBasis(){
  return MobileState.dataBasis || "-";
}

function mobileMovementSummary(data){
  if(data.type !== "deposit"){
    return `공시 확인 ${data.disclosed || 0}/${data.items?.length || 0}개 기관`;
  }

  const up =
    Number(data.changes?.up_count ?? 0);

  const down =
    Number(data.changes?.down_count ?? 0);

  const total =
    Number(
      data.changes?.change_count ??
      up + down
    );

  return `변동 ${total}건 · 상승 ${up} / 하락 ${down}`;
}

function executiveReportSourceLabel(){
  return MobileState.product === "deposit"
    ? "저축은행중앙회 비교공시"
    : "각 저축은행 홈페이지";
}

function reportFinancialPeers(data){
  return Array.isArray(data?.financial)
    ? data.financial
    : [];
}

function reportMovementRows(data){
  if(data.type === "deposit"){
    const ups = Array.isArray(data.changes?.up_top5) ? data.changes.up_top5 : [];
    const downs = Array.isArray(data.changes?.down_top5) ? data.changes.down_top5 : [];

    return [...ups,...downs]
      .sort((a,b)=>Math.abs(changeMagnitude(b))-Math.abs(changeMagnitude(a)))
      .slice(0,5)
      .map((item,index)=>({
        rank:index+1,
        bank:item.bank,
        rate:item.rate,
        last:
          changeMagnitude(item) > 0
            ? `+${Math.abs(changeMagnitude(item)).toFixed(2)}%p`
            : changeMagnitude(item) < 0
              ? `▲${Math.abs(changeMagnitude(item)).toFixed(2)}%p`
              : "-"
      }));
  }

  return [...(data.items || [])]
    .filter(item=>item.disclosure_date || item.rate_month)
    .sort((a,b)=>disclosureSortValue(b.disclosure_date || b.rate_month)-disclosureSortValue(a.disclosure_date || a.rate_month))
    .slice(0,5)
    .map((item,index)=>({
      rank:index+1,
      bank:item.bank,
      rate:item.rate,
      last:disclosure(item.disclosure_date || item.rate_month)
    }));
}

function buildMobileExecutiveReport(data,aiText=""){
  const basis = mobileDataBasis();
  const rates = data?.ranked || [];
  const top = rates[0] || {};
  const financial = reportFinancialPeers(data);
  const movementRows = reportMovementRows(data);

  const wr = number(data?.wr);
  const max = number(data?.max);
  const avg = number(data?.avg);
  const min = number(data?.min);

  const topGap = wr !== null && max !== null ? wr-max : null;
  const avgGap = wr !== null && avg !== null ? wr-avg : null;
  const top5Boundary = rates[4] ? number(rates[4].rate) : null;
  const top5Gap = wr !== null && top5Boundary !== null ? wr-top5Boundary : null;
  const higherCount = wr === null ? null : rates.filter(item=>number(item.rate) > wr).length;

  const financialWooriIndex =
    financial.findIndex(item=>isWoori(item.bank));

  const movementTitle =
    data.type === "deposit"
      ? "최근 금리 변동"
      : "최근 공시 현황";

  const movementSummary =
    data.type === "deposit"
      ? `변동 ${Number(data.changes?.change_count ?? 0)}건 · 상승 ${Number(data.changes?.up_count ?? 0)} / 하락 ${Number(data.changes?.down_count ?? 0)}`
      : `공시 확인 ${data.disclosed || 0}/${data.items?.length || 0}개 기관`;

  const sourceCount =
    (data.items || []).filter(item=>item.source).length;

  const monitorPoints = [
    top5Gap === null
      ? "TOP5 경계 금리 데이터를 확인합니다."
      : `TOP5 경계 금리 ${pct(top5Boundary)}와 우리금융의 단순 금리차 ${top5Gap >= 0 ? "+" : ""}${top5Gap.toFixed(2)}%p를 모니터링합니다.`,
    data.type === "deposit"
      ? `전일 변동 ${Number(data.changes?.change_count ?? 0)}건 중 상위금리권 조정 여부를 우선 확인합니다.`
      : "최근 공시일이 갱신된 상위기관의 금리 재조정 여부를 우선 확인합니다.",
    financial.length
      ? `금융지주계 저축은행 내 우리금융 순위 ${financialWooriIndex >= 0 ? financialWooriIndex+1 : "-"}위와 선두사 Gap을 확인합니다.`
      : "금융지주계 비교 데이터의 추가 확보 여부를 확인합니다."
  ];

  return `
    <div id="mobile-executive-report-document" class="mobile-report-document">

      <div class="mr-header">
        <div class="mr-header-top">
          <div class="eyebrow" style="color:#d7e7ff">EXECUTIVE INTELLIGENCE</div>
          <h4>SBRateBot ${currentLabel()} AI 보고서</h4>
          <div class="mr-header-meta">
            ${currentLabel()} ${MobileState.period}개월 · 데이터 업데이트 시간 ${basis}
          </div>
        </div>

        <div class="mr-metrics">
          <div class="mr-metric">
            <span>우리금융</span>
            <strong style="color:#1556c0">${pct(wr)}</strong>
          </div>
          <div class="mr-metric">
            <span>시장 최고</span>
            <strong>${pct(max)}</strong>
          </div>
          <div class="mr-metric">
            <span>시장 순위</span>
            <strong>${data.rank ? data.rank+"위" : "-"}</strong>
          </div>
        </div>
      </div>

      <section class="mr-section">
        <div class="mr-section-title"><span>01 · Executive Summary</span><span>TODAY</span></div>
        <div class="mr-section-body">
          ${buildBrief(data)}
          <br><br>
          ${higherCount === null ? "" : `우리금융보다 높은 금리를 제시하는 기관은 ${higherCount}개이며, `}
          ${top5Gap === null ? "" : `TOP5 경계와의 단순 금리차는 ${top5Gap >= 0 ? "+" : ""}${top5Gap.toFixed(2)}%p입니다. `}
          ${movementSummary}.
        </div>
      </section>

      <section class="mr-section">
        <div class="mr-section-title"><span>02 · Market Snapshot</span><span>${data.total || rates.length}개 기관</span></div>
        <div class="mr-section-body">
          <div class="mr-kv"><span>시장 최고</span><b>${displayBankName(top.bank || "-")} ${pct(max)}</b></div>
          <div class="mr-kv"><span>시장 평균</span><b>${pct(avg)}</b></div>
          <div class="mr-kv"><span>시장 최저</span><b>${pct(min)}</b></div>
          <div class="mr-kv"><span>${data.type === "deposit" ? "금리 변동" : "공시 확인"}</span><b>${movementSummary}</b></div>
        </div>
      </section>

      <section class="mr-section">
        <div class="mr-section-title"><span>03 · Woori Market Position</span><span>${data.rank ? data.rank+"위" : "-"}</span></div>
        <div class="mr-section-body">
          <div class="mr-kv"><span>우리금융 금리</span><b style="color:#1556c0">${pct(wr)}</b></div>
          <div class="mr-kv"><span>시장 최고 대비</span><b>${topGap === null ? "-" : (topGap >= 0 ? "+" : "")+topGap.toFixed(2)+"%p"}</b></div>
          <div class="mr-kv"><span>시장 평균 대비</span><b>${avgGap === null ? "-" : (avgGap >= 0 ? "+" : "")+avgGap.toFixed(2)+"%p"}</b></div>
          <div class="mr-kv"><span>우리금융보다 높은 기관</span><b>${higherCount === null ? "-" : higherCount+"개"}</b></div>
          <div class="mr-kv"><span>TOP5 경계 금리</span><b>${pct(top5Boundary)}</b></div>
        </div>
      </section>

      <section class="mr-section">
        <div class="mr-section-title"><span>04 · Competitive Landscape</span><span>TOP10</span></div>
        <div class="mr-section-body">
          <div class="mr-row" style="font-size:8px;color:#8a96a7">
            <span>순위</span><span>저축은행</span><span>금리</span><span>${data.type === "deposit" ? "전일比" : "공시일"}</span>
          </div>
          ${rates.slice(0,10).map((item,index)=>{
            const w = isWoori(item.bank);
            let last = "-";
            if(data.type === "deposit"){
              const c = number(item.change);
              last = c === null || c === 0 ? "-" : c > 0 ? `+${c.toFixed(2)}%p` : `▲${Math.abs(c).toFixed(2)}%p`;
            }else{
              last = disclosure(item.disclosure_date || item.rate_month);
            }
            return `
              <div class="mr-row ${w ? "woori" : ""}">
                <span>${item.rank ?? index+1}</span>
                <span>${displayBankName(item.bank)}</span>
                <span>${pct(item.rate)}</span>
                <span>${last}</span>
              </div>`;
          }).join("")}
        </div>
      </section>

      <section class="mr-section">
        <div class="mr-section-title"><span>05 · Financial Group Peers</span><span>${financial.length}개</span></div>
        <div class="mr-section-body">
          ${
            financial.length
              ? financial.slice(0,8).map((item,index)=>`
                  <div class="mr-row ${isWoori(item.bank) ? "woori" : ""}">
                    <span>${item.rank ?? index+1}</span>
                    <span>${displayBankName(item.bank)}</span>
                    <span>${pct(item.rate)}</span>
                    <span>${data.type === "deposit" ? (number(item.change) > 0 ? "+"+number(item.change).toFixed(2)+"%p" : number(item.change) < 0 ? "▲"+Math.abs(number(item.change)).toFixed(2)+"%p" : "-") : disclosure(item.disclosure_date || item.rate_month)}</span>
                  </div>
                `).join("")
              : '<div style="color:#8a96a7">금융지주계 비교 데이터가 확인되지 않았습니다.</div>'
          }
        </div>
      </section>

      <section class="mr-section">
        <div class="mr-section-title"><span>06 · ${movementTitle}</span><span>${movementSummary}</span></div>
        <div class="mr-section-body">
          ${
            movementRows.length
              ? movementRows.map(item=>`
                  <div class="mr-row ${isWoori(item.bank) ? "woori" : ""}">
                    <span>${item.rank}</span>
                    <span>${displayBankName(item.bank)}</span>
                    <span>${pct(item.rate)}</span>
                    <span>${item.last}</span>
                  </div>
                `).join("")
              : '<div style="color:#8a96a7">해당 기간의 변동·공시 데이터가 없습니다.</div>'
          }
        </div>
      </section>

      <section class="mr-section">
        <div class="mr-section-title"><span>07 · AI Management Insight</span><span>AI</span></div>
        <div class="mr-section-body mr-ai">
          ${aiText || "AI 종합 판단을 생성하고 있습니다..."}
        </div>
      </section>

      <section class="mr-section">
        <div class="mr-section-title"><span>08 · Key Monitoring Points</span><span>ACTION</span></div>
        <div class="mr-section-body">
          <ol class="mr-monitor-list">
            ${monitorPoints.map(point=>`<li>${point}</li>`).join("")}
          </ol>
        </div>
      </section>

      <section class="mr-section">
        <div class="mr-section-title"><span>09 · Data Source & Notes</span><span>TRUST</span></div>
        <div class="mr-section-body">
          <div class="mr-source-box">
            <b>출처</b> · ${executiveReportSourceLabel()}<br>
            <b>데이터 업데이트 시간</b> · ${basis}<br>
            <b>원문 링크 보유</b> · ${sourceCount}건<br>
            공시일은 개별 기관의 공식 공시 기준입니다. 금리 미확인 값은 0%로 해석하지 않고 '-'로 표시합니다.
            본 보고서의 순위·금리·Gap·공시일 등 수치는 SBRateBot 수집 데이터로 계산하며, AI는 제공된 수치의 해석에만 사용됩니다.
          </div>
        </div>
      </section>

      <div style="margin-top:9px;text-align:right;color:#98a1ae;font-size:7.5px">
        SBRateBot · ${basis}
      </div>
    </div>
  `;
}

async function openMobileExecutiveReport(){
  const modal =
    $("mobile-report-modal");

  const content =
    $("mobile-report-content");

  const data =
    MobileState.data[
      MobileState.product
    ];

  if(!modal || !content || !data){
    toast("보고서 데이터를 준비하지 못했습니다.");
    return;
  }

  try{
    const baseFinancial = await api("/api/financial");
    const base = Array.isArray(baseFinancial) ? baseFinancial : [];
    const cores = new Set(
      base.map(item=>normalizeBankCore(item.bank ?? item.bank_name ?? item.kor_co_nm))
    );

    let financial = [];

    if(MobileState.product === "deposit"){
      financial = base.map((item,index)=>({
        ...item,
        bank:item.bank ?? item.bank_name ?? item.kor_co_nm ?? "-",
        rate:number(item.rate ?? item.max_rate ?? item.intr_rate2),
        rank:item.rank ?? index+1,
        change:number(item.change ?? item.diff ?? 0) ?? 0
      }));
    }else{
      financial = (data.ranked || []).filter(item=>{
        const core = normalizeBankCore(item.bank);
        return [...cores].some(baseCore =>
          baseCore && (core.includes(baseCore) || baseCore.includes(core))
        );
      });

      if(!financial.length){
        const keys = ["우리","KB","신한","하나","NH","IBK","BNK","DGB","한국투자"];
        financial = (data.ranked || []).filter(item =>
          keys.some(key =>
            normalizeBankCore(item.bank).includes(normalizeBankCore(key))
          )
        );
      }

      financial = financial
        .sort((a,b)=>number(b.rate)-number(a.rate))
        .map((item,index)=>({...item,rank:index+1,change:0}));
    }

    data.financial = financial;
  }catch(error){
    console.error("MOBILE REPORT FINANCIAL ERROR",error);
    data.financial = [];
  }

  $("mobile-report-title").textContent =
    `AI 보고서`;

  $("mobile-report-basis").textContent =
    `데이터 업데이트 기준 ${mobileDataBasis()}`;

  modal.classList.remove("hidden");

  content.innerHTML =
    buildMobileExecutiveReport(
      data,
      ""
    );

  const financial = reportFinancialPeers(data);
  const top5Boundary = data.ranked?.[4]?.rate ?? null;
  const higherCount = number(data.wr) === null
    ? null
    : (data.ranked || []).filter(item=>number(item.rate) > number(data.wr)).length;

  const question =
    `데이터 업데이트 기준 ${mobileDataBasis()}. ${currentLabel()} ${MobileState.period}개월 AI 보고서의 AI Management Insight를 작성해줘.
반드시 아래 제공 데이터만 사용하고 새로운 숫자를 만들거나 추정하지 마.
우리금융 금리 ${data.wr ?? "-"}%, 시장순위 ${data.rank ?? "-"}위, 시장 최고 ${data.max ?? "-"}%, 시장 평균 ${data.avg ?? "-"}%, TOP5 경계 ${top5Boundary ?? "-"}%, 우리금융보다 높은 기관 ${higherCount ?? "-"}개.
금융지주계 데이터: ${JSON.stringify(financial.slice(0,8))}.
${data.type === "deposit" ? `변동 데이터: ${JSON.stringify(data.changes || {})}` : `최근 공시 데이터: ${JSON.stringify(reportMovementRows(data))}`}.
다음 순서로 간결하지만 전문적으로 작성해줘:
① 시장상황 2문장
② 우리금융 경쟁력 2문장
③ 핵심 리스크·기회 2문장
④ 대응 및 모니터링 포인트 3개.
일반론은 제외하고 ${currentLabel()} 데이터에 근거해 작성해줘.`;

  try{
    const result =
      await api(
        "/api/ai/search",
        {
          method:"POST",
          headers:{
            "Content-Type":"application/json"
          },
          body:JSON.stringify({
            question,
            category:MobileState.product,
            period:MobileState.period
          })
        }
      );

    const answer =
      String(
        result?.answer ||
        result?.result ||
        result?.response ||
        ""
      ).trim();

    content.innerHTML =
      buildMobileExecutiveReport(
        data,
        answer ||
        "AI 추가 판단이 없어 데이터 기반 보고서만 표시합니다."
      );
  }
  catch(error){
    console.error(
      "MOBILE REPORT AI ERROR",
      error
    );

    content.innerHTML =
      buildMobileExecutiveReport(
        data,
        "AI 추가 판단을 불러오지 못했습니다. 데이터 기반 보고서는 정상적으로 사용할 수 있습니다."
      );
  }
}

function closeMobileExecutiveReport(){
  $("mobile-report-modal")
    ?.classList.add("hidden");
}

async function downloadMobileExecutiveReportPDF(){
  const report =
    document.getElementById(
      "mobile-executive-report-document"
    );

  if(!report){
    toast("보고서를 먼저 열어주세요.");
    return;
  }

  const basis =
    mobileDataBasis()
      .replace(/[: ]/g,"-");

  const filename =
    `SBRateBot_${MobileState.product}_Executive_Report_${basis}.pdf`;

  if(typeof html2pdf === "undefined"){
    alert(
      "PDF 모듈을 불러오지 못했습니다. 네트워크 상태를 확인해주세요."
    );
    return;
  }

  const options = {
    margin:[8,8,8,8],
    filename,
    image:{
      type:"jpeg",
      quality:0.98
    },
    html2canvas:{
      scale:2,
      useCORS:true,
      backgroundColor:"#ffffff"
    },
    jsPDF:{
      unit:"mm",
      format:"a4",
      orientation:"portrait"
    },
    pagebreak:{
      mode:[
        "avoid-all",
        "css",
        "legacy"
      ]
    }
  };

  await html2pdf()
    .set(options)
    .from(report)
    .save();
}


/* =========================================================
   INIT
========================================================= */

document.addEventListener(
  "DOMContentLoaded",
  ()=>{
    document
      .querySelectorAll(".product-tab")
      .forEach(button=>{
        button.addEventListener(
          "click",
          () =>
            switchProduct(
              button.dataset.product,
              {scrollTop:true}
            )
        );
      });

    $("mobile-refresh")
      .addEventListener(
        "click",
        () =>
          switchProduct(
            MobileState.product,
            {scrollTop:false}
          )
      );

    $("toggle-top10")
      .addEventListener(
        "click",
        ()=>{
          MobileState.topExpanded =
            !MobileState.topExpanded;

          renderRanking(
            MobileState.data[
              MobileState.product
            ]
          );
        }
      );


    $("mobile-ai-send")
      .addEventListener(
        "click",
        sendAI
      );

    $("mobile-product-search")
      .addEventListener(
        "input",
        renderProducts
      );

    $("mobile-product-period")
      ?.addEventListener(
        "change",
        async event=>{
          MobileState.productPeriod =
            String(event.target.value || "12");

          await loadProducts();
        }
      );

    $("mobile-report-open")
      ?.addEventListener(
        "click",
        openMobileExecutiveReport
      );

    $("mobile-report-close")
      ?.addEventListener(
        "click",
        closeMobileExecutiveReport
      );

    $("mobile-report-pdf")
      ?.addEventListener(
        "click",
        downloadMobileExecutiveReportPDF
      );

    $("mobile-report-modal")
      ?.addEventListener(
        "click",
        event=>{
          if(event.target === $("mobile-report-modal")){
            closeMobileExecutiveReport();
          }
        }
      );

    $("mobile-kakao-share")
      ?.addEventListener(
        "click",
        shareKakao
      );

    initKakaoShare();

    initNavObserver();
    initErrorReport();
    startMobileClock();

    switchProduct(
      "deposit",
      {scrollTop:false}
    );
  }
);
