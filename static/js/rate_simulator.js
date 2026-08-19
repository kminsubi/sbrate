/* =========================================
   SBRate Woori Rate Simulator V1
========================================= */

(function(){
    "use strict";

    const state = {
        open:false,
        mobile:false,
        minimized:false,
        requestId:0,
        currentData:null,
        drag:null,
        sheetDrag:null,
        inputTimer:null,
    };

    function isMobilePage(){
        return location.pathname === "/mobile" || !!document.querySelector(".app-shell");
    }

    function categoryLabel(category){
        return {
            deposit:"정기예금",
            isa:"ISA",
            irp:"퇴직연금(IRP)"
        }[category] || "정기예금";
    }

    function selectedCategory(){
        if(isMobilePage()){
            const active = document.querySelector("#mobile-product-tabs .product-tab.is-active");
            return active?.dataset?.product || "deposit";
        }

        const buttons = [...document.querySelectorAll("[data-market-product]")];
        const active = buttons.find(button =>
            button.classList.contains("text-white") ||
            button.getAttribute("aria-selected") === "true"
        );
        return active?.dataset?.marketProduct || "deposit";
    }

    function periodFromText(value){
        const match = String(value || "").match(/(1|3|6|12|24|36)\s*개월/);
        return match ? match[1] : "";
    }

    function selectedPeriod(){
        const category = selectedCategory();
        let period = "";

        if(isMobilePage()){
            period = periodFromText(
                document.getElementById("hero-product-label")?.textContent
            );
            if(!period){
                period = document.getElementById("mobile-product-period")?.value || "12";
            }
        }else{
            period = document.getElementById("product-period-select")?.value || "";
            if(!period){
                period = periodFromText(
                    document.getElementById("dashboard-market-label")?.textContent
                );
            }
        }

        if(category !== "deposit" && period === "1"){
            period = "12";
        }

        return period || "12";
    }

    function currentContext(){
        return {
            category:selectedCategory(),
            period:selectedPeriod()
        };
    }

    function fmtRate(value){
        const n = Number(value);
        return Number.isFinite(n) ? `${n.toFixed(2)}%` : "-";
    }

    function changeMarkup(value){
        const n = Number(value);
        if(!Number.isFinite(n) || Math.abs(n) < 0.00001){
            return '<span class="sb-sim-flat">-</span>';
        }
        if(n > 0){
            return `<span class="sb-sim-up">+${Math.abs(n).toFixed(2)}%p</span>`;
        }
        return `<span class="sb-sim-down">▲${Math.abs(n).toFixed(2)}%p</span>`;
    }

    function gapMarkup(value){
        return changeMarkup(value);
    }

    function rankStatus(currentRank, simulatedRank){
        const current = Number(currentRank);
        const simulated = Number(simulatedRank);
        if(!Number.isFinite(current) || !Number.isFinite(simulated)){
            return {text:"-", cls:"flat"};
        }
        const delta = current - simulated;
        if(delta > 0){
            return {text:`${delta}계단 개선`, cls:"good"};
        }
        if(delta < 0){
            return {text:`${Math.abs(delta)}계단 악화`, cls:"bad"};
        }
        return {text:"변동 없음", cls:"flat"};
    }

    function gapStatus(currentGap, simulatedGap){
        const current = Number(currentGap);
        const simulated = Number(simulatedGap);
        if(!Number.isFinite(current) || !Number.isFinite(simulated)){
            return {text:"-", cls:"flat"};
        }
        const currentAbs = Math.abs(current);
        const simulatedAbs = Math.abs(simulated);
        if(simulatedAbs + 0.00001 < currentAbs){
            return {text:"Gap 축소", cls:"good"};
        }
        if(simulatedAbs > currentAbs + 0.00001){
            return {text:"Gap 확대", cls:"bad"};
        }
        return {text:"유지", cls:"flat"};
    }

    function shortBank(name){
        return String(name || "-")
            .replace(/저축은행/g, "")
            .replace(/\s{2,}/g, " ")
            .trim() || "-";
    }

    function neighborRow(item, label){
        if(!item){
            return "";
        }
        return `
          <div class="sb-sim-neighbor-row">
            <span>${label} · ${shortBank(item.bank)}</span>
            <strong>${fmtRate(item.rate)}</strong>
          </div>`;
    }

    function simulatorBody(data){
        if(!data?.ok){
            return `<div class="sb-sim-error">${data?.message || "시뮬레이션 데이터를 불러올 수 없습니다."}</div>`;
        }

        const current = data.current || {};
        const simulated = data.simulated || {};
        const thresholds = data.thresholds || {};
        const rank = rankStatus(current.rank, simulated.rank);
        const topGap = gapStatus(current.gap_top, simulated.gap_top);
        const averageGap = gapStatus(current.gap_average, simulated.gap_average);
        const financialRank = (
            current.financial_rank != null && simulated.financial_rank != null
        ) ? `
          <div class="sb-sim-result-card">
            <span class="sb-sim-label">금융지주계 순위</span>
            <div class="sb-sim-transition">
              <span class="from">${current.financial_rank}위</span>
              <span class="arrow">→</span>
              <span class="to">${simulated.financial_rank}위</span>
              ${Number(current.financial_rank) > Number(simulated.financial_rank)
                ? '<span class="sb-sim-status good">개선</span>'
                : Number(current.financial_rank) < Number(simulated.financial_rank)
                  ? '<span class="sb-sim-status bad">악화</span>'
                  : '<span class="sb-sim-status flat">유지</span>'}
            </div>
          </div>` : "";

        return `
          <div class="sb-sim-rate-row">
            <div class="sb-sim-rate-box">
              <span class="sb-sim-label">현재 우리금융 금리</span>
              <div class="sb-sim-current-rate">${fmtRate(current.rate)}</div>
            </div>
            <div class="sb-sim-arrow">→</div>
            <div class="sb-sim-rate-box is-target">
              <span class="sb-sim-label">시뮬레이션 금리</span>
              <div class="sb-sim-target-wrap">
                <input id="sb-sim-target-input" class="sb-sim-target-input" type="number" inputmode="decimal"
                  min="0.01" max="10" step="0.01" value="${Number(simulated.rate || current.rate || 0).toFixed(2)}"
                  aria-label="시뮬레이션 금리" />
                <span class="sb-sim-percent">%</span>
              </div>
            </div>
          </div>

          <div class="sb-sim-delta">금리변화 ${changeMarkup(Number(simulated.rate || 0) - Number(current.rate || 0))}</div>

          <div class="sb-sim-presets">
            <button type="button" class="sb-sim-preset is-down" data-sim-delta="-0.10">▲0.10</button>
            <button type="button" class="sb-sim-preset is-down" data-sim-delta="-0.05">▲0.05</button>
            <button type="button" class="sb-sim-preset is-current" data-sim-current="1">현재</button>
            <button type="button" class="sb-sim-preset is-up" data-sim-delta="0.05">+0.05</button>
            <button type="button" class="sb-sim-preset is-up" data-sim-delta="0.10">+0.10</button>
            <button type="button" class="sb-sim-preset is-up" data-sim-delta="0.20">+0.20</button>
          </div>

          <div class="sb-sim-result-grid">
            <div class="sb-sim-result-card">
              <span class="sb-sim-label">시장 순위</span>
              <div class="sb-sim-transition">
                <span class="from">${current.rank ?? "-"}위</span>
                <span class="arrow">→</span>
                <span class="to">${simulated.rank ?? "-"}위</span>
                <span class="sb-sim-status ${rank.cls}">${rank.text}</span>
              </div>
            </div>

            <div class="sb-sim-result-card">
              <span class="sb-sim-label">시장 최고 대비</span>
              <div class="sb-sim-transition">
                <span class="from">${gapMarkup(current.gap_top)}</span>
                <span class="arrow">→</span>
                <span class="to">${gapMarkup(simulated.gap_top)}</span>
                <span class="sb-sim-status ${topGap.cls}">${topGap.text}</span>
              </div>
            </div>

            <div class="sb-sim-result-card">
              <span class="sb-sim-label">시장 평균 대비</span>
              <div class="sb-sim-transition">
                <span class="from">${gapMarkup(current.gap_average)}</span>
                <span class="arrow">→</span>
                <span class="to">${gapMarkup(simulated.gap_average)}</span>
                <span class="sb-sim-status ${averageGap.cls}">${averageGap.text}</span>
              </div>
            </div>

            ${financialRank}
          </div>

          <div class="sb-sim-zone">
            <div class="sb-sim-zone-title">경쟁 구간 · 시뮬레이션 ${fmtRate(simulated.rate)} 기준</div>
            ${neighborRow(simulated.above, "바로 위")}
            <div class="sb-sim-neighbor-row is-woori">
              <span>우리금융 · ${current.product || "대표상품"}</span>
              <strong>${fmtRate(simulated.rate)}</strong>
            </div>
            ${neighborRow(simulated.below, "바로 아래")}
          </div>

          <div class="sb-sim-thresholds">
            <div class="sb-sim-threshold">
              <span class="sb-sim-label">TOP10 경쟁선</span>
              <strong>${thresholds.top10 != null ? fmtRate(thresholds.top10) : "-"}</strong>
            </div>
            <div class="sb-sim-threshold">
              <span class="sb-sim-label">TOP5 경쟁선</span>
              <strong>${thresholds.top5 != null ? fmtRate(thresholds.top5) : "-"}</strong>
            </div>
          </div>

          <div class="sb-sim-foot">
            <span>[출처 : ${data.source || "-"}]</span>
            <span>※ 조회용 시뮬레이션이며 실제 금리 데이터는 변경되지 않습니다.</span>
          </div>`;
    }

    function panelTitle(data){
        const context = data?.ok
            ? {category:data.category, period:data.period}
            : currentContext();
        return {
            title:"우리금융 금리 시뮬레이터",
            basis:`${categoryLabel(context.category)} · ${context.period}개월`
        };
    }

    function createPcPanel(){
        let layer = document.getElementById("sb-rate-sim-pc-layer");
        if(layer){
            return layer;
        }

        layer = document.createElement("div");
        layer.id = "sb-rate-sim-pc-layer";
        layer.className = "sb-sim-pc-layer";
        layer.innerHTML = `
          <section id="sb-rate-sim-panel" class="sb-sim-panel" role="dialog" aria-label="우리금융 금리 시뮬레이터">
            <header class="sb-sim-drag">
              <div class="sb-sim-title-wrap">
                <div class="sb-sim-title">우리금융 금리 시뮬레이터</div>
                <small class="sb-sim-basis">정기예금 · 12개월</small>
              </div>
              <div class="sb-sim-head-actions">
                <button type="button" class="sb-sim-head-btn" data-sim-minimize aria-label="최소화">−</button>
                <button type="button" class="sb-sim-head-btn" data-sim-close aria-label="닫기">×</button>
              </div>
            </header>
            <div class="sb-sim-content"><div class="sb-sim-loading">시뮬레이션 데이터를 불러오고 있습니다.</div></div>
          </section>`;
        document.body.appendChild(layer);

        const panel = layer.querySelector(".sb-sim-panel");
        const handle = layer.querySelector(".sb-sim-drag");

        handle.addEventListener("pointerdown", event => {
            if(event.target.closest("button,input")) return;
            const rect = panel.getBoundingClientRect();
            state.drag = {
                pointerId:event.pointerId,
                offsetX:event.clientX - rect.left,
                offsetY:event.clientY - rect.top
            };
            handle.setPointerCapture?.(event.pointerId);
        });

        handle.addEventListener("pointermove", event => {
            if(!state.drag || state.drag.pointerId !== event.pointerId) return;
            const width = panel.offsetWidth;
            const height = panel.offsetHeight;
            const left = Math.max(8, Math.min(window.innerWidth - width - 8, event.clientX - state.drag.offsetX));
            const top = Math.max(8, Math.min(window.innerHeight - Math.min(height, window.innerHeight - 16) - 8, event.clientY - state.drag.offsetY));
            panel.style.left = `${left}px`;
            panel.style.top = `${top}px`;
        });

        const stopDrag = event => {
            if(state.drag && state.drag.pointerId === event.pointerId){
                state.drag = null;
            }
        };
        handle.addEventListener("pointerup", stopDrag);
        handle.addEventListener("pointercancel", stopDrag);

        layer.querySelector("[data-sim-close]").addEventListener("click", closeSimulator);
        layer.querySelector("[data-sim-minimize]").addEventListener("click", () => {
            state.minimized = !state.minimized;
            panel.classList.toggle("is-minimized", state.minimized);
            layer.querySelector("[data-sim-minimize]").textContent = state.minimized ? "□" : "−";
        });

        return layer;
    }

    function createMobileSheet(){
        let backdrop = document.getElementById("sb-rate-sim-mobile");
        if(backdrop){
            return backdrop;
        }

        backdrop = document.createElement("div");
        backdrop.id = "sb-rate-sim-mobile";
        backdrop.className = "sb-sim-mobile-backdrop";
        backdrop.innerHTML = `
          <section class="sb-sim-sheet" role="dialog" aria-label="우리금융 금리 시뮬레이터">
            <div class="sb-sim-sheet-handle" aria-hidden="true"></div>
            <header class="sb-sim-drag">
              <div class="sb-sim-title-wrap">
                <div class="sb-sim-title">우리금융 금리 시뮬레이터</div>
                <small class="sb-sim-basis">정기예금 · 12개월</small>
              </div>
              <div class="sb-sim-head-actions">
                <button type="button" class="sb-sim-head-btn" data-sim-close aria-label="닫기">×</button>
              </div>
            </header>
            <div class="sb-sim-content"><div class="sb-sim-loading">시뮬레이션 데이터를 불러오고 있습니다.</div></div>
          </section>`;
        document.body.appendChild(backdrop);

        const sheet = backdrop.querySelector(".sb-sim-sheet");
        const dragTarget = backdrop.querySelector(".sb-sim-drag");

        dragTarget.addEventListener("pointerdown", event => {
            if(event.target.closest("button,input")) return;
            state.sheetDrag = {
                pointerId:event.pointerId,
                startY:event.clientY,
                delta:0
            };
            dragTarget.setPointerCapture?.(event.pointerId);
        });

        dragTarget.addEventListener("pointermove", event => {
            if(!state.sheetDrag || state.sheetDrag.pointerId !== event.pointerId) return;
            const delta = Math.max(0, event.clientY - state.sheetDrag.startY);
            state.sheetDrag.delta = delta;
            sheet.style.transition = "none";
            sheet.style.transform = `translateY(${delta}px)`;
        });

        function finishSheetDrag(event){
            if(!state.sheetDrag || state.sheetDrag.pointerId !== event.pointerId) return;
            const delta = state.sheetDrag.delta || 0;
            state.sheetDrag = null;
            sheet.style.transition = "transform .18s ease";
            if(delta > 110){
                closeSimulator();
            }else{
                sheet.style.transform = "translateY(0)";
            }
        }
        dragTarget.addEventListener("pointerup", finishSheetDrag);
        dragTarget.addEventListener("pointercancel", finishSheetDrag);

        backdrop.addEventListener("click", event => {
            if(event.target === backdrop){
                closeSimulator();
            }
        });
        backdrop.querySelector("[data-sim-close]").addEventListener("click", closeSimulator);

        return backdrop;
    }

    function activeContainer(){
        return state.mobile
            ? createMobileSheet()
            : createPcPanel();
    }

    function contentElement(){
        return activeContainer().querySelector(".sb-sim-content");
    }

    function updateHeader(data){
        const title = panelTitle(data);
        const container = activeContainer();
        const titleEl = container.querySelector(".sb-sim-title");
        const basisEl = container.querySelector(".sb-sim-basis");
        if(titleEl) titleEl.textContent = title.title;
        if(basisEl) basisEl.textContent = title.basis;
    }

    function bindContentEvents(data){
        const content = contentElement();
        const input = content.querySelector("#sb-sim-target-input");
        if(input){
            input.addEventListener("input", () => {
                clearTimeout(state.inputTimer);
                state.inputTimer = setTimeout(() => {
                    const value = Number(input.value);
                    if(Number.isFinite(value) && value > 0){
                        loadSimulation(value);
                    }
                }, 350);
            });
            input.addEventListener("keydown", event => {
                if(event.key === "Enter"){
                    event.preventDefault();
                    const value = Number(input.value);
                    if(Number.isFinite(value) && value > 0){
                        loadSimulation(value);
                    }
                }
            });
        }

        content.querySelectorAll("[data-sim-delta]").forEach(button => {
            button.addEventListener("click", () => {
                const delta = Number(button.dataset.simDelta || 0);
                const current = Number(data?.current?.rate || 0);
                loadSimulation(Math.max(0.01, current + delta));
            });
        });

        content.querySelectorAll("[data-sim-current]").forEach(button => {
            button.addEventListener("click", () => {
                loadSimulation(Number(data?.current?.rate || 0));
            });
        });
    }

    async function loadSimulation(targetRate){
        const context = currentContext();
        const requestId = ++state.requestId;
        const content = contentElement();
        content.innerHTML = '<div class="sb-sim-loading">시뮬레이션 데이터를 계산하고 있습니다.</div>';
        updateHeader({
            ok:true,
            category:context.category,
            period:context.period
        });

        try{
            const response = await fetch("/api/rate-simulator", {
                method:"POST",
                headers:{"Content-Type":"application/json"},
                body:JSON.stringify({
                    category:context.category,
                    period:context.period,
                    target_rate:(targetRate == null ? null : Number(targetRate))
                })
            });
            const data = await response.json();
            if(requestId !== state.requestId) return;
            state.currentData = data;
            updateHeader(data);
            content.innerHTML = simulatorBody(data);
            bindContentEvents(data);
        }catch(error){
            if(requestId !== state.requestId) return;
            console.error("RATE SIMULATOR ERROR", error);
            content.innerHTML = '<div class="sb-sim-error">시뮬레이션 데이터를 불러오지 못했습니다.</div>';
        }
    }

    function openSimulator(){
        state.mobile = isMobilePage();
        state.open = true;
        state.minimized = false;

        if(state.mobile){
            const backdrop = createMobileSheet();
            backdrop.classList.add("is-open");
            const sheet = backdrop.querySelector(".sb-sim-sheet");
            sheet.style.transform = "translateY(0)";
        }else{
            const layer = createPcPanel();
            const panel = layer.querySelector(".sb-sim-panel");
            panel.classList.remove("is-minimized");
            layer.querySelector("[data-sim-minimize]").textContent = "−";
            layer.classList.add("is-open");

            if(!panel.dataset.positioned){
                const width = Math.min(520, window.innerWidth - 32);
                panel.style.left = `${Math.max(16, (window.innerWidth - width) / 2)}px`;
                panel.style.top = `${Math.max(70, Math.min(125, window.innerHeight * .13))}px`;
                panel.dataset.positioned = "1";
            }
        }

        loadSimulation(null);
    }

    function closeSimulator(){
        state.open = false;
        document.getElementById("sb-rate-sim-pc-layer")?.classList.remove("is-open");
        const mobile = document.getElementById("sb-rate-sim-mobile");
        if(mobile){
            mobile.classList.remove("is-open");
            const sheet = mobile.querySelector(".sb-sim-sheet");
            if(sheet) sheet.style.transform = "translateY(0)";
        }
    }

    function installPcButton(){
        if(document.getElementById("rate-sim-open-pc")) return;
        const heroCard = document.querySelector("#dashboard-hero-start > .col-span-4:first-child > .bg-white");
        if(!heroCard) return;
        const header = heroCard.querySelector(":scope > .flex.items-center.justify-between.mb-4");
        if(!header) return;

        const button = document.createElement("button");
        button.id = "rate-sim-open-pc";
        button.type = "button";
        button.className = "sb-sim-open-btn";
        button.textContent = "📈 금리 시뮬레이션";
        button.title = "우리금융 금리 시뮬레이션";
        button.addEventListener("click", openSimulator);

        const slot = header.children[1];
        if(slot){
            slot.textContent = "";
            slot.appendChild(button);
        }else{
            header.appendChild(button);
        }
    }

    function installMobileButton(){
        if(document.getElementById("rate-sim-open-mobile")) return;
        const right = document.querySelector(".data-meta-right");
        if(!right) return;
        const button = document.createElement("button");
        button.id = "rate-sim-open-mobile";
        button.type = "button";
        button.className = "sb-sim-open-btn";
        button.textContent = "📈 금리 시뮬레이션";
        button.addEventListener("click", openSimulator);
        right.appendChild(button);
    }

    function watchContextChanges(){
        document.addEventListener("click", event => {
            const productTab = event.target.closest("[data-market-product], #mobile-product-tabs .product-tab");
            if(productTab && state.open){
                setTimeout(() => loadSimulation(null), 80);
            }
        });

        ["product-period-select", "mobile-product-period"].forEach(id => {
            document.getElementById(id)?.addEventListener("change", () => {
                if(state.open){
                    setTimeout(() => loadSimulation(null), 80);
                }
            });
        });

        window.addEventListener("resize", () => {
            if(!state.open || state.mobile) return;
            const panel = document.querySelector("#sb-rate-sim-panel");
            if(!panel) return;
            const rect = panel.getBoundingClientRect();
            if(rect.right > window.innerWidth - 8){
                panel.style.left = `${Math.max(8, window.innerWidth - panel.offsetWidth - 8)}px`;
            }
            if(rect.bottom > window.innerHeight - 8){
                panel.style.top = `${Math.max(8, window.innerHeight - panel.offsetHeight - 8)}px`;
            }
        });
    }

    function init(){
        state.mobile = isMobilePage();
        if(state.mobile){
            installMobileButton();
        }else{
            installPcButton();
        }
        watchContextChanges();
        window.openSBRateSimulator = openSimulator;
    }

    if(document.readyState === "loading"){
        document.addEventListener("DOMContentLoaded", init, {once:true});
    }else{
        init();
    }
})();
