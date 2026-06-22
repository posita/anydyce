// Tests for the pure plot-spec helpers (../plot.js).
//
// renderPlots is DOM/Plotly-bound and verified by browser smoke test only;
// plotSpec and itemsToPercents are pure and tested here.
//
// Run with: node --test playground/test/test-plot.mjs

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  CHART_CHROME_PX,
  DEFAULT_PLOT_PRECISION,
  EMPTY_CHART_PX,
  PX_PER_OUTCOME,
  alignedSeries,
  chartHeight,
  globalMaxPercent,
  itemsToPercents,
  lineSpec,
  plotSpec,
  readCssTheme,
} from "../plot.js";

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

// ---- chartHeight / uniform bar thickness ---------------------------------

test("chartHeight: each additional outcome adds exactly PX_PER_OUTCOME", () => {
  assert.equal(chartHeight(7) - chartHeight(6), PX_PER_OUTCOME);
  assert.equal(chartHeight(1), CHART_CHROME_PX + PX_PER_OUTCOME);
});

test("plotSpec: layout.height tracks outcome count", () => {
  const items3 = [[1, 1], [2, 1], [3, 1]];
  const items6 = [[1, 1], [2, 1], [3, 1], [4, 1], [5, 1], [6, 1]];
  const spec3 = plotSpec("a", items3);
  const spec6 = plotSpec("b", items6);
  assert.equal(spec3.layout.height, chartHeight(3));
  assert.equal(spec6.layout.height, chartHeight(6));
  // The whole point: pixels-per-outcome identical across the two charts.
  assert.equal(
    spec6.layout.height - spec3.layout.height,
    3 * PX_PER_OUTCOME,
  );
});

test("plotSpec: empty spec uses the fixed empty height", () => {
  const spec = plotSpec("the empty die", []);
  assert.equal(spec.layout.height, EMPTY_CHART_PX);
});

// ---- shared x-axis range --------------------------------------------------

test("plotSpec: xMax fixes the x-axis range", () => {
  const spec = plotSpec("a", [[1, 1], [2, 3]], { xMax: 42 });
  assert.deepEqual(spec.layout.xaxis.range, [0, 42]);
});

test("plotSpec: without xMax the x-axis auto-ranges from zero", () => {
  const spec = plotSpec("a", [[1, 1], [2, 3]]);
  assert.equal(spec.layout.xaxis.range, undefined);
  assert.equal(spec.layout.xaxis.rangemode, "tozero");
});

test("globalMaxPercent: picks the max across all outputs", () => {
  const outputs = [
    { label: "a", items: [[1, 1], [2, 3]] },       // max 75%
    { label: "b", items: [[5, 1]] },               // max 100%
    { label: "c", items: [[1, 1], [2, 1], [3, 2]] }, // max 50%
  ];
  const max = globalMaxPercent(outputs);
  assert.ok(Math.abs(max - 100) < 1e-9, `max=${max}`);
});

test("globalMaxPercent: ignores empty outputs", () => {
  const outputs = [
    { label: "a", items: [] },
    { label: "b", items: [[1, 1], [2, 1]] }, // max 50%
  ];
  const max = globalMaxPercent(outputs);
  assert.ok(Math.abs(max - 50) < 1e-9, `max=${max}`);
});

test("globalMaxPercent: null when every output is empty", () => {
  assert.equal(globalMaxPercent([{ label: "a", items: [] }]), null);
  assert.equal(globalMaxPercent([]), null);
  assert.equal(globalMaxPercent(null), null);
});

// ---- display precision -----------------------------------------------------

test("plotSpec: default precision matches anydyce's display default", () => {
  assert.equal(DEFAULT_PLOT_PRECISION, 2);
  const spec = plotSpec("a", [[1, 1], [2, 3]]);
  assert.deepEqual(spec.data[0].text, ["25.00%", "75.00%"]);
  assert.match(spec.data[0].hovertemplate, /%\{x:\.2f\}/);
});

test("plotSpec: precision 0 drops decimals", () => {
  const spec = plotSpec("a", [[1, 1], [2, 3]], { precision: 0 });
  assert.deepEqual(spec.data[0].text, ["25%", "75%"]);
  assert.match(spec.data[0].hovertemplate, /%\{x:\.0f\}/);
});

test("plotSpec: precision 6 widens decimals", () => {
  const spec = plotSpec("a", [[1, 2], [2, 1]], { precision: 6 });
  assert.deepEqual(spec.data[0].text, ["66.666667%", "33.333333%"]);
  assert.match(spec.data[0].hovertemplate, /%\{x:\.6f\}/);
});

test("plotSpec: invalid precision falls back to the default", () => {
  for (const bad of [null, undefined, -1, 2.5, "high", NaN]) {
    const spec = plotSpec("a", [[1, 1]], { precision: bad });
    assert.match(
      spec.data[0].hovertemplate,
      new RegExp(`%\\{x:\\.${DEFAULT_PLOT_PRECISION}f\\}`),
      `precision=${String(bad)}`,
    );
  }
});

// ---- theme -----------------------------------------------------------------

const THEME = {
  bg: "#14171c",
  text: "#e6edf3",
  muted: "#8b949e",
  border: "#2d333b",
  accent: "#4cc38a",
  fontFamily: "TestFont, sans-serif",
};

test("plotSpec: theme drives backgrounds, text, and font", () => {
  const spec = plotSpec("a", [[1, 1], [2, 3]], { theme: THEME });
  assert.equal(spec.layout.paper_bgcolor, THEME.bg);
  assert.equal(spec.layout.plot_bgcolor, THEME.bg);
  assert.equal(spec.layout.font.color, THEME.text);
  assert.equal(spec.layout.font.family, THEME.fontFamily);
});

test("plotSpec: theme drives bar color", () => {
  const spec = plotSpec("a", [[1, 1]], { theme: THEME });
  assert.equal(spec.data[0].marker.color, THEME.accent);
});

test("plotSpec: theme drives axis grid / line / tick colors", () => {
  const spec = plotSpec("a", [[1, 1]], { theme: THEME });
  for (const axis of [spec.layout.xaxis, spec.layout.yaxis]) {
    assert.equal(axis.gridcolor, THEME.border);
    assert.equal(axis.linecolor, THEME.border);
    assert.equal(axis.tickfont.color, THEME.muted);
  }
});

test("plotSpec: theme applies to the empty-distribution spec too", () => {
  const spec = plotSpec("empty", [], { theme: THEME });
  assert.equal(spec.layout.paper_bgcolor, THEME.bg);
  assert.equal(spec.layout.annotations[0].font.color, THEME.muted);
});

test("plotSpec: without theme, Plotly defaults are left alone", () => {
  // No color keys injected -- unit tests and themeless contexts get the
  // spec unmodified.
  const spec = plotSpec("a", [[1, 1]]);
  assert.equal(spec.layout.paper_bgcolor, undefined);
  assert.equal(spec.layout.font, undefined);
  assert.equal(spec.data[0].marker, undefined);
  assert.equal(spec.layout.xaxis.gridcolor, undefined);
});

test("readCssTheme: returns null outside a DOM", () => {
  // Node has no document; the default param resolves to undefined.
  assert.equal(readCssTheme(), null);
  assert.equal(readCssTheme(null), null);
});

// ---- alignedSeries ------------------------------------------------------

test("alignedSeries: unions outcomes and zero-fills each series", () => {
  const outputs = [
    {
      label: "a",
      items: [
        [1, 1],
        [2, 1],
      ],
    },
    {
      label: "b",
      items: [
        [2, 1],
        [3, 1],
        [4, 2],
      ],
    },
  ];
  const { x, series } = alignedSeries(outputs);
  assert.deepEqual(x, [1, 2, 3, 4]);
  assert.deepEqual(series[0], { label: "a", y: [50, 50, 0, 0] });
  assert.deepEqual(series[1], { label: "b", y: [0, 25, 25, 50] });
});

test("alignedSeries: empty distribution yields an all-zero series", () => {
  const { x, series } = alignedSeries([
    { label: "x", items: [[1, 1]] },
    { label: "empty", items: [] },
  ]);
  assert.deepEqual(x, [1]);
  assert.deepEqual(series[1], { label: "empty", y: [0] });
});

test("alignedSeries: no outputs -> empty x and series", () => {
  const { x, series } = alignedSeries([]);
  assert.deepEqual(x, []);
  assert.deepEqual(series, []);
});

// ---- lineSpec -----------------------------------------------------------

test("lineSpec: one scatter/lines trace per output, numeric x-axis", () => {
  const spec = lineSpec([
    { label: "a", items: [[1, 1]] },
    { label: "b", items: [[2, 1]] },
  ]);
  assert.equal(spec.data.length, 2);
  assert.equal(spec.data[0].type, "scatter");
  assert.equal(spec.data[0].mode, "lines");
  assert.equal(spec.data[0].name, "a");
  // Numeric (not categorical) x so series align on a shared scale and
  // Plotly auto-picks tick density.
  assert.equal(spec.layout.xaxis.type, undefined);
  assert.equal(spec.layout.yaxis.rangemode, "tozero");
  assert.equal(spec.layout.hovermode, "x unified");
  assert.equal(spec.isEmpty, false);
});

test("lineSpec: shared zero-filled x across traces", () => {
  const spec = lineSpec([
    { label: "a", items: [[1, 1]] },
    { label: "b", items: [[3, 1]] },
  ]);
  assert.deepEqual(spec.data[0].x, [1, 3]);
  assert.deepEqual(spec.data[1].x, [1, 3]);
  assert.deepEqual(spec.data[0].y, [100, 0]);
  assert.deepEqual(spec.data[1].y, [0, 100]);
});

test("lineSpec: precision flows into the hover template", () => {
  const spec = lineSpec([{ label: "a", items: [[1, 1]] }], { precision: 4 });
  assert.match(spec.data[0].hovertemplate, /%\{y:\.4f\}%/);
});

test("lineSpec: theme.series becomes layout.colorway", () => {
  const spec = lineSpec([{ label: "a", items: [[1, 1]] }], {
    theme: { series: ["#111", "#222"] },
  });
  assert.deepEqual(spec.layout.colorway, ["#111", "#222"]);
});

test("lineSpec: no theme leaves colorway unset (Plotly default palette)", () => {
  const spec = lineSpec([{ label: "a", items: [[1, 1]] }]);
  assert.equal(spec.layout.colorway, undefined);
});

test("lineSpec: all-empty outputs -> isEmpty", () => {
  const spec = lineSpec([{ label: "x", items: [] }]);
  assert.equal(spec.isEmpty, true);
});
