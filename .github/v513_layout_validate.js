const puppeteer = require('puppeteer-core');

const chrome = process.env.CHROME_BIN;
if (!chrome) throw new Error('CHROME_BIN not set');

function assert(cond, message){
  if(!cond) throw new Error(message);
}

(async()=>{
  const browser = await puppeteer.launch({
    executablePath: chrome,
    headless: true,
    args: ['--no-sandbox','--disable-dev-shm-usage']
  });

  try{
    const page = await browser.newPage();
    page.on('pageerror', ()=>{});
    page.on('console', ()=>{});

    async function pcCheck(width,height,mode){
      await page.setViewport({width,height,deviceScaleFactor:1});
      await page.goto('http://127.0.0.1:8123/index.html', {waitUntil:'networkidle2', timeout:60000});
      await page.waitForFunction(()=>{
        const grid=document.querySelector('body > div.p-6');
        return grid && getComputedStyle(grid).display==='grid';
      }, {timeout:30000});

      await page.evaluate((activeMode)=>{
        document.querySelectorAll('[data-market-product]').forEach(btn=>{
          const active=btn.dataset.marketProduct===activeMode;
          btn.className=active
            ? 'market-product-tab bg-[#1a58c8] text-white px-4 py-1.5 rounded-lg text-[11px] font-bold shadow-sm'
            : 'market-product-tab text-gray-500 px-4 py-1.5 rounded-lg text-[11px] font-semibold hover:bg-white hover:text-blue-700';
        });
      }, mode);

      await new Promise(r=>setTimeout(r,150));

      const m = await page.evaluate(()=>{
        const main=document.querySelector('main.col-span-9').getBoundingClientRect();
        const aside=document.querySelector('#ai-analysis-center').getBoundingClientRect();
        const content=document.querySelector('#ai-center-content');
        const tabs=document.querySelector('#market-product-tabs');
        const wibee=document.querySelector('img[alt="위비 캐릭터"]');
        const after=getComputedStyle(tabs,'::after').content;
        const style=getComputedStyle(wibee);
        return {
          mainBottom:main.bottom,
          asideBottom:aside.bottom,
          mainHeight:main.height,
          asideHeight:aside.height,
          overflow:getComputedStyle(document.querySelector('#ai-analysis-center')).overflow,
          contentOverflowY:getComputedStyle(content).overflowY,
          scrollWidth:document.documentElement.scrollWidth,
          viewport:window.innerWidth,
          sourceAfter:after,
          animationIterations:style.animationIterationCount,
          asset:wibee.getAttribute('src')
        };
      });

      assert(Math.abs(m.mainBottom-m.asideBottom) <= 2.5,
        `PC ${width} ${mode}: bottom mismatch ${m.mainBottom} vs ${m.asideBottom}`);
      assert(m.overflow==='hidden', `PC ${width}: AI parent overflow=${m.overflow}`);
      assert(['hidden','auto'].includes(m.contentOverflowY), `PC ${width}: unexpected AI content overflowY=${m.contentOverflowY}`);
      assert(m.scrollWidth <= m.viewport + 2, `PC ${width}: horizontal overflow ${m.scrollWidth}>${m.viewport}`);
      assert(m.asset.includes('/static/images/wibee.png'), `PC: wrong Wibee asset ${m.asset}`);
      assert(m.animationIterations==='1', `PC: Wibee loop count ${m.animationIterations}`);

      if(mode==='deposit') assert(m.sourceAfter.includes('정기예금 12개월 시장현황') && m.sourceAfter.includes('저축은행중앙회 비교공시'), `PC deposit source: ${m.sourceAfter}`);
      if(mode==='isa') assert(m.sourceAfter.includes('ISA 12개월 시장현황') && m.sourceAfter.includes('각 저축은행 홈페이지'), `PC ISA source: ${m.sourceAfter}`);
      if(mode==='irp') assert(m.sourceAfter.includes('퇴직연금(IRP) 12개월 시장현황') && m.sourceAfter.includes('각 저축은행 홈페이지'), `PC IRP source: ${m.sourceAfter}`);

      const longAnswer = await page.evaluate(()=>{
        const main=document.querySelector('main.col-span-9');
        const aside=document.querySelector('#ai-analysis-center');
        const content=document.querySelector('#ai-center-content');
        content.style.overflowY='auto';
        content.innerHTML = Array.from({length:90},(_,i)=>`<p>AI 분석 답변 ${i+1} · 시장금리/Gap/순위 검토 문장</p>`).join('');
        const mainRect=main.getBoundingClientRect();
        const asideRect=aside.getBoundingClientRect();
        return {
          bottomDiff:Math.abs(mainRect.bottom-asideRect.bottom),
          overflowY:getComputedStyle(content).overflowY,
          scrollHeight:content.scrollHeight,
          clientHeight:content.clientHeight,
          asideHeight:asideRect.height
        };
      });
      assert(longAnswer.bottomDiff <= 2.5, `PC ${width} ${mode}: long-answer bottom mismatch ${longAnswer.bottomDiff}`);
      assert(longAnswer.overflowY==='auto', `PC ${width} ${mode}: long-answer overflowY=${longAnswer.overflowY}`);
      assert(longAnswer.scrollHeight > longAnswer.clientHeight, `PC ${width} ${mode}: long answer did not become internally scrollable`);

      console.log('PC OK', width, height, mode, JSON.stringify({...m,longAnswer}));
    }

    for(const [w,h] of [[1700,1000],[1366,900]]){
      for(const mode of ['deposit','isa','irp']) await pcCheck(w,h,mode);
    }

    async function mobileCheck(width){
      await page.setViewport({width,height:900,deviceScaleFactor:1});
      await page.goto('http://127.0.0.1:8123/mobile.html', {waitUntil:'networkidle2', timeout:60000});
      await new Promise(r=>setTimeout(r,250));
      const m=await page.evaluate(()=>{
        const hero=document.querySelector('.hero-card').getBoundingClientRect();
        const grid=document.querySelector('.hero-main-grid').getBoundingClientRect();
        const img=document.querySelector('.hero-wibee').getBoundingClientRect();
        const rate=document.querySelector('.hero-rate-panel').getBoundingClientRect();
        const firstKpi=document.querySelector('.kpi-grid')?.getBoundingClientRect();
        const wibee=document.querySelector('.hero-wibee');
        const style=getComputedStyle(wibee);
        return {
          heroHeight:hero.height,
          gridHeight:grid.height,
          visualGap:rate.left-img.right,
          heroToKpi:firstKpi ? firstKpi.top-hero.bottom : null,
          scrollWidth:document.documentElement.scrollWidth,
          viewport:window.innerWidth,
          asset:wibee.getAttribute('src'),
          animationIterations:style.animationIterationCount,
          sourceAfter:getComputedStyle(document.querySelector('.data-meta-left'),'::after').content
        };
      });
      assert(m.heroHeight < 185, `Mobile ${width}: hero too tall ${m.heroHeight}`);
      assert(m.gridHeight <= 90, `Mobile ${width}: hero grid too tall ${m.gridHeight}`);
      assert(m.visualGap <= 16, `Mobile ${width}: Wibee/rate gap too large ${m.visualGap}`);
      assert(m.heroToKpi === null || m.heroToKpi <= 18, `Mobile ${width}: hero/KPI gap ${m.heroToKpi}`);
      assert(m.scrollWidth <= m.viewport + 1, `Mobile ${width}: horizontal overflow ${m.scrollWidth}>${m.viewport}`);
      assert(m.asset.includes('/static/images/wibee.png'), `Mobile: wrong Wibee asset ${m.asset}`);
      assert(m.animationIterations==='1', `Mobile: Wibee loop count ${m.animationIterations}`);
      assert(m.sourceAfter.includes('저축은행중앙회 비교공시'), `Mobile source: ${m.sourceAfter}`);
      console.log('MOBILE OK', width, JSON.stringify(m));
    }

    for(const w of [360,390,430]) await mobileCheck(w);

    await page.emulateMediaFeatures([{name:'prefers-reduced-motion', value:'reduce'}]);
    await page.setViewport({width:390,height:900,deviceScaleFactor:1});
    await page.goto('http://127.0.0.1:8123/mobile.html', {waitUntil:'networkidle2', timeout:60000});
    const mobileReduced=await page.$eval('.hero-wibee', el=>getComputedStyle(el).animationName);
    assert(mobileReduced==='none', `Mobile reduced motion animation=${mobileReduced}`);

    await page.setViewport({width:1700,height:1000,deviceScaleFactor:1});
    await page.goto('http://127.0.0.1:8123/index.html', {waitUntil:'networkidle2', timeout:60000});
    const pcReduced=await page.$eval('img[alt="위비 캐릭터"]', el=>getComputedStyle(el).animationName);
    assert(pcReduced==='none', `PC reduced motion animation=${pcReduced}`);
    console.log('REDUCED MOTION OK');
  } finally {
    await browser.close();
  }
})();
