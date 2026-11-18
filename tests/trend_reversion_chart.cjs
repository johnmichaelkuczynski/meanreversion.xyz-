const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("components/mean_reversion/chart.js", "utf8");
const body = source.slice(source.indexOf("  var COLORS"), source.indexOf("  function setHeight"));
const context = {console, currentHeight: 680};
vm.createContext(context);
vm.runInContext(body, context);
const data = {
  symbol: "TEST",
  dates: ["2020-01-01", "2020-01-02"],
  prices: [100, 110],
  verdict: {random_walk: false, band_width: .2, residuals: [-.1, .1], position_text: "10% above trend"},
  historical_trend: {dates: ["2020-01-01", "2020-01-02"], trend: [105, 106], upper: [150, 160], lower: [70, 75]},
  forecast: {
    dates: ["2030-01-01"], upper: [200], lower: [90], trend: [130],
    probabilities: {upper: [.3], lower: [.2], trend: [.5]}
  },
  overlays: [{symbol: "OTHER", dates: ["2020-01-01", "2020-01-02"], prices: [50, 60]}]
};
context.testData = data;
const prepared = vm.runInContext("makeTraces(testData)", context);
const lower = prepared.traces.find(t => t.name === "−2 band");
assert.ok(Math.abs(lower.y[0] - Math.expm1(-.4) * 100) < 1e-10);
const upper = prepared.traces.find(t => t.name === "+2 band");
assert.ok(Math.abs(upper.y[0] - Math.expm1(.4) * 100) < 1e-10);
assert.ok(prepared.traces.find(t => t.name === "Distance from trend"));
const overlay = prepared.traces.find(t => t.name === "OTHER (scaled)");
assert.deepEqual(Array.from(overlay.y), [100, 120]);
assert.deepEqual(Array.from(overlay.customdata), [50, 60]);
context.prepared = prepared;
const layout = vm.runInContext("getLayout(testData, prepared)", context);
assert.equal(layout.yaxis.type, "log");
assert.equal(layout.dragmode, "pan");
assert.equal(layout.xaxis2.matches, "x");
assert.equal(layout.annotations[0].y, Math.log10(110));
assert.equal(layout.yaxis.tickmode, "array");
assert.ok(layout.yaxis.ticktext.every(label => /^\$/.test(label)));
assert.ok(layout.yaxis.tickvals.every(value => value > 0));

data.verdict.random_walk = true;
const rejected = vm.runInContext("makeTraces(testData)", context);
assert.ok(rejected.traces.find(t => t.name === "OTHER (scaled)"));
assert.ok(rejected.traces.find(t => t.name === "Upper"));
assert.ok(rejected.traces.find(t => t.name === "Historical trend"));
assert.ok(rejected.traces.find(t => t.name === "Historical upper band"));
assert.ok(rejected.traces.find(t => t.name === "Historical lower band"));
assert.ok(rejected.traces.find(t => t.name === "Distance from trend"));
context.prepared = rejected;
assert.equal(vm.runInContext("getLayout(testData, prepared).yaxis2.visible", context), true);
assert.doesNotMatch(source, /gate_passed|gatePassed|no trend line drawn/);
assert.match(source, /xaxis\.p2d\(px\)/);
assert.doesNotMatch(source, /window\.parent\.document/);
console.log("Mean Reversion chart: bands and projections always visible, dollar-only log labels, log annotation, overlays and live-axis tooltips passed.");
