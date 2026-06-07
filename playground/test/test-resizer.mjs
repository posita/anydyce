// Tests for the resizer's pure helpers (../resizer.js).
//
// The DOM-bound attachRowResizer is verified by browser smoke test only;
// these tests cover the math that's testable in isolation.
//
// Run with: node --test playground/test/test-resizer.mjs

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  MAX_PERCENT,
  MIN_PERCENT,
  clampPercent,
  pointerYToPercent,
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

// ---- pointerYToPercent ---------------------------------------------------

test("pointerYToPercent computes the top-row share from pointer Y", () => {
  // Container at viewport top=100, height=300, resizer 6px
  // Available = 294. Pointer at viewport Y=247 -> dy=147 -> 50%.
  assert.equal(pointerYToPercent(247, 100, 300, 6), 50);
});

test("pointerYToPercent at the very top yields 0 (caller will clamp)", () => {
  assert.equal(pointerYToPercent(100, 100, 300, 6), 0);
});

test("pointerYToPercent below the container yields > 100 (caller will clamp)", () => {
  // Pointer well past the bottom -- formula doesn't clamp; the consumer's
  // clampPercent does.
  assert.equal(pointerYToPercent(500, 100, 300, 6) > 100, true);
});

test("pointerYToPercent above the container yields negative", () => {
  assert.equal(pointerYToPercent(50, 100, 300, 6) < 0, true);
});

test("pointerYToPercent returns null when available height is non-positive", () => {
  // Container.height <= resizerSize means there's no room for either pane.
  assert.equal(pointerYToPercent(100, 100, 6, 6), null);
  assert.equal(pointerYToPercent(100, 100, 5, 6), null);
  assert.equal(pointerYToPercent(100, 100, 0, 6), null);
});

test("pointerYToPercent + clampPercent compose into a safe percentage", () => {
  // Realistic UI sequence: raw pointer math, then clamp.
  const raw = pointerYToPercent(500, 100, 300, 6); // > 100
  const safe = clampPercent(raw);
  assert.equal(safe, MAX_PERCENT);
});
