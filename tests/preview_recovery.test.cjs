const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const test = require("node:test");
const source = fs.readFileSync("preview_recovery.js", "utf8");

for (const readyState of ["loading", "complete"]) {
  test(`legacy overlay is removed without reload or user action (${readyState})`, () => {
    let panel, observer, loaded, removals = 0;
    const addOverlay = () => { panel = {remove() { panel = null; removals++; }}; };
    addOverlay();
    const document = {
      readyState, documentElement: {},
      getElementById(id) { assert.equal(id,"soxl-preview-recovery"); return panel; },
      addEventListener(event, callback) { assert.equal(event,"DOMContentLoaded"); loaded=callback; },
      createElement() { assert.fail("Recovery must never create a popup"); }
    };
    vm.runInNewContext(source, {
      document,
      MutationObserver: class {
        constructor(callback) { observer = callback; }
        observe(target, options) { assert.equal(target,document.documentElement); assert.ok(options.subtree); }
      },
      setTimeout() { assert.fail("Recovery must not schedule prompts or reloads"); },
      location: {replace() { assert.fail("Recovery must not navigate"); }},
      window: {addEventListener() { assert.fail("Do not turn errors into recovery popups"); }}
    });
    if (loaded) loaded();
    assert.equal(panel,null);
    assert.equal(removals,1);
    // Protect against an old, already-loaded copy adding the card again.
    addOverlay(); observer();
    assert.equal(panel,null);
    assert.equal(removals,2);
  });
}

test("shared app style also hides a stale card in already-open sessions", () => {
  const style = fs.readFileSync("clean_presentation.py","utf8");
  assert.match(style, /#soxl-preview-recovery\s*\{\s*display:\s*none\s*!important/);
});
