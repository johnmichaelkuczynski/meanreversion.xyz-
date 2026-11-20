// Isolated component regression: real CSS/pointer events, no app session or data changes.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const {test, before, after} = require("node:test");
const {chromium} = require("playwright");
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
  executablePath:process.env.CHROMIUM_PATH, headless:true,args:["--no-sandbox"]
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
