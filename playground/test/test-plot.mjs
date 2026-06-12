// Tests for the pure plot-spec helpers (../plot.js).
//
// renderPlots is DOM/Plotly-bound and verified by browser smoke test only;
// plotSpec and itemsToPercents are pure and tested here.
//
// Run with: node --test playground/test/test-plot.mjs

import { test } from "node:test";
import assert from "node:assert/strict";

import { itemsToPercents, plotSpec } from "../plot.js";

// ---- itemsToPercents ----------------------------------------------------

test("itemsToPercents: uniform 1d6 -> six equal percents", () => {
  const items = [
    [1, 1],
    [2, 1],
    [3, 1],
    [4, 1],
    [5, 1],
    [6, 1],
  ];
  const p = itemsToPercents(items);
  assert.equal(p.length, 6);
  for (const v of p) {
    // Allow a tiny epsilon for the scaled-bigint round-trip.
    assert.ok(Math.abs(v - 100 / 6) < 1e-9, `got ${v}`);
  }
});

test("itemsToPercents: counts sum to ~100", () => {
  const items = [
    [1, 1],
    [2, 2],
    [3, 3],
    [4, 4],
  ];
  const p = itemsToPercents(items);
  const sum = p.reduce((a, b) => a + b, 0);
  assert.ok(Math.abs(sum - 100) < 1e-9, `sum=${sum}`);
});

test("itemsToPercents: handles BigInt counts (worker boundary)", () => {
  const items = [
    [1, 1n],
    [2, 3n],
  ];
  const p = itemsToPercents(items);
  assert.equal(p.length, 2);
  assert.ok(Math.abs(p[0] - 25) < 1e-9);
  assert.ok(Math.abs(p[1] - 75) < 1e-9);
});

test("itemsToPercents: huge BigInt counts don't overflow", () => {
  // Counts that don't fit in float64. Naive Number(c) would lose precision
  // or hit Infinity; scaled-bigint math stays exact.
  const huge1 = 10n ** 100n;
  const huge3 = 3n * huge1;
  const items = [
    [1, huge1],
    [2, huge3],
  ];
  const p = itemsToPercents(items);
  assert.ok(Math.abs(p[0] - 25) < 1e-9, `p[0]=${p[0]}`);
  assert.ok(Math.abs(p[1] - 75) < 1e-9, `p[1]=${p[1]}`);
});

test("itemsToPercents: zero-mass returns null", () => {
  // E.g. an empty distribution H({}) materializes as items=[].
  assert.equal(itemsToPercents([]), null);
});

test("itemsToPercents: all-zero counts return null", () => {
  // Defensive: a histogram with explicit zero-count entries (e.g. from
  // preserve_zero_counts=True) but no positive mass.
  assert.equal(itemsToPercents([[1, 0], [2, 0]]), null);
});

test("itemsToPercents: null / undefined return null", () => {
  assert.equal(itemsToPercents(null), null);
  assert.equal(itemsToPercents(undefined), null);
});

// ---- plotSpec ----------------------------------------------------------

test("plotSpec: includes label as title", () => {
  const spec = plotSpec("my roll", [[1, 1], [2, 1]]);
  assert.equal(spec.layout.title.text, "my roll");
});

test("plotSpec: horizontal bar with outcomes on y-axis", () => {
  const spec = plotSpec("output 1", [[1, 1], [2, 3]]);
  assert.equal(spec.data.length, 1);
  const trace = spec.data[0];
  assert.equal(trace.type, "bar");
  assert.equal(trace.orientation, "h");
  // y holds outcome labels (as strings, category axis).
  assert.deepEqual(trace.y, ["1", "2"]);
  // x is percent.
  assert.equal(trace.x.length, 2);
  assert.ok(Math.abs(trace.x[0] - 25) < 1e-9);
  assert.ok(Math.abs(trace.x[1] - 75) < 1e-9);
});

test("plotSpec: y-axis configured to put smallest outcome on top", () => {
  const spec = plotSpec("output 1", [[1, 1], [2, 1]]);
  assert.equal(spec.layout.yaxis.type, "category");
  // Plotly's default category order would put the FIRST y-value at the
  // bottom; we reverse so smallest sits on top, matching the text view.
  assert.equal(spec.layout.yaxis.autorange, "reversed");
});

test("plotSpec: empty distribution is marked isEmpty", () => {
  const spec = plotSpec("the empty die", []);
  assert.equal(spec.isEmpty, true);
  // No traces.
  assert.equal(spec.data.length, 0);
  // Title still labeled.
  assert.match(spec.layout.title.text, /the empty die/);
  // "(empty)" annotation present.
  assert.equal(spec.layout.annotations.length, 1);
  assert.match(spec.layout.annotations[0].text, /empty/i);
});

test("plotSpec: zero-mass distribution treated as empty", () => {
  const spec = plotSpec("zeroed", [[1, 0], [2, 0]]);
  assert.equal(spec.isEmpty, true);
});

test("plotSpec: non-empty distribution is not isEmpty", () => {
  const spec = plotSpec("normal", [[1, 1]]);
  assert.equal(spec.isEmpty, false);
});

test("plotSpec: outcome order preserved in trace", () => {
  // AnyDice may return outcomes in any order (sorted by interpreter); we
  // preserve whatever the worker shipped.
  const items = [
    [5, 1],
    [3, 1],
    [4, 1],
  ];
  const spec = plotSpec("output 1", items);
  assert.deepEqual(spec.data[0].y, ["5", "3", "4"]);
});

test("plotSpec: hovertemplate is set (avoid the auto 'trace 0' label)", () => {
  const spec = plotSpec("output 1", [[1, 1]]);
  assert.ok(spec.data[0].hovertemplate);
});
