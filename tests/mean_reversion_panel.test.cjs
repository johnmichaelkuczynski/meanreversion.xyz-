const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const test = require("node:test");
const helpers = require("../components/mean_reversion_panel/panel.js");

test("three common-date rows preserve the provided prices and probabilities", () => {
  const rows = helpers.bandRowsFromPoint({
    customdata: ["2027-11-19", "$300.00", "21.5%", "$100.00", "56.0%", "$20.00", "9.0%"]
  }, "2026-11-19");
  assert.equal(rows.length, 3);
  assert.deepEqual(rows.map(r => r.target_price), ["$300.00", "$100.00", "$20.00"]);
  assert.deepEqual(rows.map(r => r.probability_text), ["21.5%", "56.0%", "9.0%"]);
  assert.equal(helpers.bandRowsFromPoint({customdata: 12}, "2026-11-19"), null);
  const historical = helpers.bandRowsFromPoint({
    customdata: ["2025-11-19", "$100", null, "$80", null, "$60", null]
  }, "2026-11-19");
  assert.ok(historical.every(row => row.probability_text === "Historical date — not a forecast"));
  assert.equal(helpers.formatProbability(0), "0.0%");
  assert.equal(helpers.formatProbability(null), "Not available");
  assert.equal(helpers.formatProbability(0.0001), "<0.1%");
  assert.equal(helpers.formatProbability(0.9999), ">99.9%");
});

function harness() {
  class Node {
    constructor(id) {
      this.id = id; this.children = []; this.events = {}; this.attrs = {};
      this.style = {setProperty(key, value) { this[key] = value; }};
      this.dataset = {}; this.offsetWidth = 420; this.offsetHeight = 500;
      this.clientWidth = 1100; this.clientHeight = 800;
      this.hidden = false;
      const classes = new Set();
      this.classList = {toggle(name, enabled) { enabled ? classes.add(name) : classes.delete(name); },
                        contains(name) { return classes.has(name); }};
    }
    append(...nodes) { for (const node of nodes) this.appendChild(node); }
    appendChild(node) { this.children.push(node); node.parentElement = this; }
    replaceChildren(...nodes) { this.children = []; this.append(...nodes); }
    get firstElementChild() { return this.children[0]; }
    addEventListener(name, fn) { this.events[name] = fn; }
    setAttribute(name, value) { this.attrs[name] = value; }
    getBoundingClientRect() { return {left:0, top:0, width:this.offsetWidth, height:this.offsetHeight}; }
    on(name, fn) { this.events[name] = fn; }
    closest() { return null; }
  }
  const nodes = {};
  const document = {getElementById(id) { return nodes[id] ||= new Node(id); },
                    createElement() { return new Node(""); }};
  const handlers = {}, messages = [], plots = [];
  const window = {
    matchMedia: () => ({matches:false}),
    parent: {postMessage: (message) => messages.push(message)},
    addEventListener: (name, fn) => { handlers[name] = fn; },
    removeEventListener: (name) => { delete handlers[name]; },
    Plotly: {react: (...args) => { plots.push(args); return Promise.resolve(); }}
  };
  vm.runInNewContext(fs.readFileSync("components/mean_reversion_panel/panel.js", "utf8"),
                    {window, document, console});
  return {nodes, handlers, messages, plots, render(args) {
    handlers.message({data:{type:"streamlit:render", args}});
  }};
}

const args = {
  symbol:"SOXL", last_date:"2026-11-19", selected_date:"2027-11-19",
  rows: [{kind:"upper",target_price:300,hit_probability:.215},
         {kind:"median",target_price:100,hit_probability:.56},
         {kind:"lower",target_price:20,hit_probability:.09}],
  figure:{data:[{name:"SOXL · actual",y:[1,2]}],layout:{height:520}},
  readout_height:640
};

test("ticker replacement updates the component's actual chart and readout data", async () => {
  const h = harness();
  h.render(args);
  await new Promise(setImmediate);
  const panel = h.nodes.readout;
  assert.equal(panel.hidden, false);
  assert.equal(h.nodes["panel-symbol"].textContent, "SOXL");
  assert.equal(h.nodes["band-rows"].children.length, 3);
  const upper = h.nodes["band-rows"].children[0];
  assert.equal(upper.children[1].textContent, "Price: $300.00");
  assert.equal(upper.children[2].textContent, "Probability: 21.5%");
  // Old prices must not survive in the chart or panel after switching securities.
  h.render({...args,symbol:"AAPL",rows:args.rows.map(row => ({...row,target_price:42})),
    figure:{data:[{name:"AAPL · actual",y:[30,42]}],layout:{height:520}}});
  assert.equal(h.nodes["panel-symbol"].textContent, "AAPL");
  assert.equal(h.plots.at(-1)[1][0].name, "AAPL · actual");
  assert.equal(h.nodes["band-rows"].children[0].children[1].textContent, "Price: $42.00");
  h.render({...args,symbol:"VWAV",rows:[]});
  assert.equal(panel.hidden, true);
  h.render({...args,symbol:"",rows:[],figure:{data:[],layout:{}}});
  assert.equal(panel.hidden, true);
  assert.equal(h.plots.at(-1)[1].length, 0);
});

test("right-edge growth shifts left instead of getting stuck at the viewport edge", () => {
  assert.deepEqual(helpers.clampPanelGeometry(680,20,500,400,{width:1100,height:640}),
    {x:600,y:20,width:500,height:400});
  assert.deepEqual(helpers.clampPanelGeometry(200,20,300,400,{width:360,height:640}),
    {x:60,y:20,width:300,height:400});
  assert.deepEqual(helpers.panelDimensions(190,120,false),{width:190,height:120});
});

test("hover cards flip away from the edges and respect the visible scrolled region", () => {
  for (const [x,y,bounds] of [
    [1080,620,{x:0,y:0,width:1100,height:640}],
    [15,260,{x:0,y:250,width:1100,height:390}],
    [350,490,{x:0,y:100,width:360,height:400}]
  ]) {
    const width = Math.min(340, bounds.width-16), height = 230;
    const placed = helpers.hoverPosition(x,y,width,height,bounds);
    assert.ok(placed.x >= bounds.x+8 && placed.x+width <= bounds.x+bounds.width-8);
    assert.ok(placed.y >= bounds.y+8 && placed.y+height <= bounds.y+bounds.height-8);
  }
});

test("hover persists, pin freezes the date, click and return use one shared readout", async () => {
  const h = harness();
  h.render(args);
  await new Promise(setImmediate);
  const point = {customdata:["2028-11-19","$400","30%","$150","60%","$40","12%"]};
  h.nodes.chart.events.plotly_hover({points:[point]});
  assert.equal(h.nodes["hover-readout"].hidden, false, "hover must show an on-chart card without a click");
  assert.equal(h.nodes["hover-heading"].textContent, "SOXL · 2028-11-19");
  assert.equal(h.nodes["hover-band-rows"].children.length, 3);
  assert.deepEqual(h.nodes["hover-band-rows"].children.map(row => row.children[1].textContent),
    ["Price: $400", "Price: $150", "Price: $40"]);
  assert.equal(h.nodes["panel-date"].textContent, "Hovered date: 2028-11-19");
  assert.equal(h.nodes["band-rows"].children.length, 3);
  h.nodes["pin-button"].events.click();
  h.nodes.chart.events.plotly_hover({points:[{customdata:[
    "2029-11-19","$500","40%","$200","70%","$50","20%"
  ]}]});
  assert.equal(h.nodes["panel-date"].textContent, "Hovered date: 2028-11-19");
  assert.equal(h.nodes["hover-heading"].textContent, "SOXL · 2029-11-19",
    "pinning the optional lower panel must not freeze the live hover card");
  assert.deepEqual(h.nodes["hover-band-rows"].children.map(row => row.children[2].textContent),
    ["Probability: 40%", "Probability: 70%", "Probability: 20%"]);
  // Hovering the actual-price trace must not overwrite the band prices.
  h.nodes.chart.events.plotly_hover({points:[{customdata:100}]});
  assert.equal(h.nodes["hover-readout"].hidden, true);
  assert.equal(h.nodes["band-rows"].children[0].children[1].textContent, "Price: $400");
  h.nodes["return-button"].events.click();
  assert.equal(h.nodes["panel-date"].textContent, "Selected date: 2027-11-19");
  assert.equal(h.nodes["band-rows"].children[0].children[1].textContent, "Price: $300.00");
  h.nodes.chart.events.plotly_hover({points:[point]});
  h.nodes.chart.events.plotly_unhover();
  assert.equal(h.nodes["hover-readout"].hidden, true);
  h.nodes.chart.events.plotly_hover({points:[point]});
  h.nodes.chart.events.pointerleave();
  assert.equal(h.nodes["hover-readout"].hidden, true);
  h.nodes.chart.events.plotly_hover({points:[point]});
  h.render({...args,symbol:"AAPL"});
  assert.equal(h.nodes["hover-readout"].hidden, true, "old stock hover values cannot survive a rerender");
  h.nodes.chart.events.plotly_hover({points:[{customdata:[
    "2029-11-19","$250","11%","$200","35%","$150","65%"
  ]}]});
  assert.equal(h.nodes["hover-heading"].textContent,"AAPL · 2029-11-19");
  assert.equal(h.nodes["hover-band-rows"].children[0].children[1].textContent,"Price: $250");
  assert.ok(!h.messages.some(message => message.type === "streamlit:setComponentValue"),
    "hovering must never rerun the server or fetch new prices");
});
