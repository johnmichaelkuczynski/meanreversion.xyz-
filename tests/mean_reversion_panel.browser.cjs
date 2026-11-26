// Isolated component regression: real CSS/pointer events, no app session or data changes.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const {test, before, after} = require("node:test");
const {chromium} = require("playwright");
const {execFileSync} = require("node:child_process");
const root = path.resolve("components/mean_reversion_panel");
let browser;
const args = {
  symbol:"SOXL", last_date:"2026-11-19", selected_date:"2027-11-19",
  rows:[{kind:"upper",target_price:300,hit_probability:.2},
        {kind:"median",target_price:100,hit_probability:.5},
        {kind:"lower",target_price:20,hit_probability:.1}],
  figure:{data:[],layout:{height:640}}, readout_height:640
};
before(async () => { browser = await chromium.launch({
  executablePath:process.env.CHROMIUM_PATH ||
    (fs.existsSync("/repl/tools/bin/chromium") ? "/repl/tools/bin/chromium" : undefined),
  headless:true,args:["--no-sandbox"]
}); });
after(async () => { if (browser) await browser.close(); });

for (const width of [360, 600, 1100]) {
  test(`panel moves, shrinks, stretches, collapses and stays reachable at ${width}px`, async () => {
    const context = await browser.newContext({viewport:{width,height:1000}});
    const page = await context.newPage();
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    await page.route("https://component.test/**", async route => {
      const filename = path.basename(new URL(route.request().url()).pathname);
      if (filename === "plotly.js") {
        return route.fulfill({contentType:"application/javascript",
          body:"window.Plotly={react:async function(chart){chart.on=function(name,fn){(chart.events||={})[name]=fn;};}};"});
      }
      const name = filename || "index.html";
      await route.fulfill({contentType:name.endsWith(".css")?"text/css":name.endsWith(".js")?
        "application/javascript":"text/html", body:fs.readFileSync(path.join(root,name))});
    });
    async function render(next=args) {
      await page.evaluate(value => window.postMessage({type:"streamlit:render",args:value},"*"),next);
      await page.waitForFunction(() => document.querySelector("#panel-symbol").textContent !== "Stock");
    }
    const rect = selector => page.locator(selector).boundingBox();
    async function reachable() {
      const panel = await rect("#readout");
      for (const id of ["dock-button","collapse-button"]) {
        const button = await rect("#"+id);
        assert.ok(button && button.y >= panel.y && button.y+button.height <= panel.y+panel.height+1,
          `${id} must remain inside the visible panel`);
      }
    }
    try {
      await page.goto("https://component.test/index.html");
      await render();
      const chart = await rect("#plot-stage");
      let panel = await rect("#readout");
      assert.ok(panel.y >= chart.y+chart.height, "default panel must not cover the chart");
      await page.locator("#dock-button").click();
      await page.locator("#drag-handle").scrollIntoViewIfNeeded();
      assert.equal(await page.locator("#readout").evaluate(el=>getComputedStyle(el).position),"absolute");
      panel = await rect("#readout");
      const header = await rect("#drag-handle");
      await page.mouse.move(header.x+25,header.y+20);
      await page.mouse.down();
      await page.mouse.move(header.x+65,header.y-70,{steps:8});
      await page.mouse.up();
      const moved = await rect("#readout");
      assert.ok(Math.abs(moved.y-panel.y)>20, "drag must move on narrow and wide previews");
      await page.locator("#smaller-button").click();
      const smaller = await rect("#readout");
      assert.ok(smaller.height<moved.height, "Smaller must reduce actual height");
      await page.locator("#larger-button").click();
      const larger = await rect("#readout");
      assert.ok(larger.height>smaller.height, "Larger must increase actual height");
      assert.ok(larger.width>=smaller.width);
      const corner = await rect("#resize-handle");
      await page.mouse.move(corner.x+10,corner.y+10);
      await page.mouse.down();
      await page.mouse.move(corner.x-45,corner.y-35,{steps:8});
      await page.mouse.up();
      const resized = await rect("#readout");
      assert.ok(resized.width<larger.width && resized.height<larger.height,
        "corner must resize both real dimensions");
      // Several shrinks must never hide the recovery controls.
      for(let i=0;i<4;i++) await page.locator("#smaller-button").click();
      await reachable();
      await page.locator("#collapse-button").click();
      const compact = await rect("#readout");
      assert.ok(compact.height<170, "collapse must produce a compact usable bar");
      await reachable();
      const state = await page.locator("#readout").getAttribute("class");
      await render({...args,symbol:"AAPL"});
      assert.equal(await page.locator("#readout").getAttribute("class"),state,
        "ticker rerender must not reopen or move the readout");
      await page.reload(); await render();
      assert.ok((await page.locator("#readout").getAttribute("class")).includes("is-collapsed"),
        "collapse must survive reload");
      await page.locator("#collapse-button").click();
      await reachable();
      await page.locator("#expand-button").click();
      const expanded = await rect("#readout");
      await page.locator("#expand-button").click();
      assert.ok((await rect("#readout")).height<expanded.height, "Restore must undo expansion");
      await page.locator("#dock-button").click();
      panel = await rect("#readout");
      assert.ok(panel.y >= (await rect("#plot-stage")).height, "Dock must remove overlap");
      assert.deepEqual(errors,[]);
    } finally { await context.close(); }
  });
}

test("real Plotly pointer hover shows all three bands inside a scrolled host without clicking", async () => {
  const context = await browser.newContext({viewport:{width:1100,height:850}});
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  const plotly = fs.readFileSync(execFileSync("python", ["-c",
    "import plotly; from pathlib import Path; print(Path(plotly.__file__).parent/'package_data'/'plotly.min.js')"
  ], {encoding:"utf8"}).trim());
  await page.route("https://component.test/**", async route => {
    const filename = path.basename(new URL(route.request().url()).pathname);
    if (filename === "host.html") return route.fulfill({contentType:"text/html",
      body:'<body style="margin:0"><div style="height:500px"></div><iframe id="host" title="Chart" src="/index.html" style="border:0;width:100%;height:1100px"></iframe><div style="height:500px"></div></body>'});
    if (filename === "plotly.js") return route.fulfill({contentType:"application/javascript",body:plotly});
    return route.fulfill({contentType:filename.endsWith(".css")?"text/css":filename.endsWith(".js")?
      "application/javascript":"text/html",body:fs.readFileSync(path.join(root,filename))});
  });
  try {
    await page.goto("https://component.test/host.html");
    const frame = page.frame({url:"https://component.test/index.html"});
    await frame.waitForFunction(() => Boolean(window.Plotly));
    const dates = ["2026-11-19","2035-11-19","2046-11-19"];
    const custom = dates.map(day => [day,"$300.00","21.5%","$100.00","56.0%","$20.00","9.0%"]);
    const traces = ["Upper trend","Mean trend","Lower trend"].map((name,i) => ({
      name,x:dates,y:[[250,300,400],[80,100,150],[15,20,40]][i],
      mode:"lines",hoverinfo:"none",customdata:custom,
      line:{color:["#e53935","#475569","#43a047"][i]}
    }));
    await frame.evaluate(value => window.postMessage({type:"streamlit:render",args:value},"*"),
      {...args,figure:{data:traces,layout:{height:640,hovermode:"closest",
        margin:{l:60,r:20,t:25,b:40},xaxis:{type:"date"},yaxis:{type:"log"}}}});
    await frame.waitForFunction(() => Boolean(document.querySelector("#chart").__meanReversionEventsReady));
    await page.evaluate(() => window.scrollTo(0,430));
    async function hoverBand(index) {
      const point = await frame.evaluate(i => {
        const chart = document.querySelector("#chart"), layout = chart._fullLayout;
        const box = chart.getBoundingClientRect(), trace = chart.data[i];
        return {x:box.left+layout.xaxis._offset+layout.xaxis.d2p(trace.x[1]),
          y:box.top+layout.yaxis._offset+layout.yaxis.l2p(Math.log10(trace.y[1]))};
      },index);
      const box = await page.locator("#host").boundingBox();
      await page.mouse.move(box.x+point.x,box.y+point.y);
      await frame.locator("#hover-readout").waitFor({state:"visible"});
      assert.equal(await frame.locator("#hover-heading").innerText(),"SOXL · 2035-11-19");
      assert.equal(await frame.locator("#hover-band-rows .band-row").count(),3);
      assert.deepEqual(await frame.locator("#hover-band-rows .band-price").allTextContents(),
        ["Price: $300.00","Price: $100.00","Price: $20.00"]);
      assert.deepEqual(await frame.locator("#hover-band-rows .band-probability").allTextContents(),
        ["Probability: 21.5%","Probability: 56.0%","Probability: 9.0%"]);
      const card = await frame.locator("#hover-readout").boundingBox();
      assert.ok(card.x>=0 && card.y>=0 && card.x+card.width<=1100 && card.y+card.height<=850,
        "the complete hover card must remain in the parent viewport");
      assert.equal(await frame.locator("#hover-readout").evaluate(el=>getComputedStyle(el).pointerEvents),"none");
    }
    for (const band of [0,1,2]) await hoverBand(band);
    // Move the iframe's top above the visible parent window, as on a scrolled app page.
    await page.evaluate(() => window.scrollTo(0,750));
    await hoverBand(2);
    fs.mkdirSync("generated-artifacts/mean-reversion-hover",{recursive:true});
    await page.screenshot({path:"generated-artifacts/mean-reversion-hover/hover-comparison.png"});
    await page.mouse.move(1090,840);
    await frame.locator("#hover-readout").waitFor({state:"hidden"});
    assert.deepEqual(errors,[]);
  } finally { await context.close(); }
});
