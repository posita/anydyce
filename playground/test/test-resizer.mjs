// Tests for the resizer's pure helpers (../resizer.js).
//
// The DOM-bound attachResizer is verified by browser smoke test only; these
// tests cover the math (clampPercent, pointerToPercent) and the template
// writing (applyLayout, via a style stub).
//
// Run with: node --test playground/test/test-resizer.mjs

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  MAX_PERCENT,
  MIN_PERCENT,
  applyLayout,
  clampPercent,
  pointerToPercent,
} from "../resizer.js";

// ---- clampPercent --------------------------------------------------------

test("clampPercent passes through values inside the bounds", () => {
  assert.equal(clampPercent(50), 50);
  assert.equal(clampPercent(MIN_PERCENT), MIN_PERCENT);
  assert.equal(clampPercent(MAX_PERCENT), MAX_PERCENT);
});

test("clampPercent clamps values below the minimum", () => {
  assert.equal(clampPercent(0), MIN_PERCENT);
  assert.equal(clampPercent(-50), MIN_PERCENT);
  assert.equal(clampPercent(MIN_PERCENT - 0.001), MIN_PERCENT);
});

test("clampPercent clamps values above the maximum", () => {
  assert.equal(clampPercent(95), MAX_PERCENT);
  assert.equal(clampPercent(1000), MAX_PERCENT);
  assert.equal(clampPercent(MAX_PERCENT + 0.001), MAX_PERCENT);
});

test("clampPercent honors custom bounds", () => {
  assert.equal(clampPercent(20, 25, 75), 25);
  assert.equal(clampPercent(80, 25, 75), 75);
  assert.equal(clampPercent(50, 25, 75), 50);
});

test("clampPercent returns null on non-finite input", () => {
  assert.equal(clampPercent(NaN), null);
  assert.equal(clampPercent(Infinity), null);
  assert.equal(clampPercent(-Infinity), null);
});

// ---- pointerToPercent ------------------------------------------------------
// The math is axis-agnostic 1D: the same function serves the row divider
// (pointer Y against container top/height) and the column divider (pointer
// X against container left/width).

test("pointerToPercent computes the first-pane share from the pointer coord", () => {
  // Container at viewport start=100, extent=300, resizer 6px.
  // Available = 294. Pointer at 247 -> delta=147 -> 50%.
  assert.equal(pointerToPercent(247, 100, 300, 6), 50);
});

test("pointerToPercent at the leading edge yields 0 (caller will clamp)", () => {
  assert.equal(pointerToPercent(100, 100, 300, 6), 0);
});

test("pointerToPercent past the trailing edge yields > 100 (caller will clamp)", () => {
  // Formula doesn't clamp; the consumer's clampPercent does.
  assert.equal(pointerToPercent(500, 100, 300, 6) > 100, true);
});

test("pointerToPercent before the leading edge yields negative", () => {
  assert.equal(pointerToPercent(50, 100, 300, 6) < 0, true);
});

test("pointerToPercent returns null when available extent is non-positive", () => {
  // Container extent <= resizerSize means there's no room for either pane.
  assert.equal(pointerToPercent(100, 100, 6, 6), null);
  assert.equal(pointerToPercent(100, 100, 5, 6), null);
  assert.equal(pointerToPercent(100, 100, 0, 6), null);
});

test("pointerToPercent + clampPercent compose into a safe percentage", () => {
  // Realistic UI sequence: raw pointer math, then clamp.
  const raw = pointerToPercent(500, 100, 300, 6); // > 100
  const safe = clampPercent(raw);
  assert.equal(safe, MAX_PERCENT);
});

// ---- applyLayout -----------------------------------------------------------

function makeContainerStub() {
  return { style: {} };
}

test("applyLayout writes grid-template-rows for the row axis", () => {
  const c = makeContainerStub();
  applyLayout(c, 70, 6, "row");
  assert.equal(c.style.gridTemplateRows, "70fr 6px 30fr");
  assert.equal(c.style.gridTemplateColumns, undefined);
});

test("applyLayout writes grid-template-columns for the column axis", () => {
  const c = makeContainerStub();
  applyLayout(c, 40, 6, "column");
  assert.equal(c.style.gridTemplateColumns, "40fr 6px 60fr");
  assert.equal(c.style.gridTemplateRows, undefined);
});

test("applyLayout panes always sum to 100", () => {
  const c = makeContainerStub();
  applyLayout(c, 12.5, 8, "row");
  assert.equal(c.style.gridTemplateRows, "12.5fr 8px 87.5fr");
});
