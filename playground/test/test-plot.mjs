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
  chartHeight,
  globalMaxPercent,
  itemsToPercents,
  lineSpec,
  perOutputSeries,
  plotSpec,
  readCssTheme,
  ridgeSpec,
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

// ---- perOutputSeries ----------------------------------------------------

test("perOutputSeries: keeps each output's own outcomes and percents", () => {
  const series = perOutputSeries([
    { label: "a", items: [[1, 1], [2, 1]] },
    { label: "b", items: [[2, 1], [3, 1], [4, 2]] },
  ]);
  // No union fill: each keeps only the outcomes it has (b's counts -> 25/25/50).
  assert.deepEqual(series[0], { label: "a", xs: [1, 2], ys: [50, 50] });
  assert.deepEqual(series[1], { label: "b", xs: [2, 3, 4], ys: [25, 25, 50] });
});

test("perOutputSeries: empty distribution yields empty xs/ys", () => {
  const series = perOutputSeries([
    { label: "x", items: [[1, 1]] },
    { label: "empty", items: [] },
  ]);
  assert.deepEqual(series[1], { label: "empty", xs: [], ys: [] });
});

test("perOutputSeries: no outputs -> empty array", () => {
  assert.deepEqual(perOutputSeries([]), []);
});

// ---- lineSpec -----------------------------------------------------------

test("lineSpec: one scatter/lines trace per output, numeric x-axis", () => {
  const spec = lineSpec([
    { label: "a", items: [[1, 1]] },
    { label: "b", items: [[2, 1]] },
  ]);
  assert.equal(spec.data.length, 2);
  assert.equal(spec.data[0].type, "scatter");
  assert.equal(spec.data[0].mode, "lines+markers");
  assert.equal(spec.data[0].name, "a");
  // Numeric (not categorical) x so series align on a shared scale and
  // Plotly auto-picks tick density.
  assert.equal(spec.layout.xaxis.type, undefined);
  assert.equal(spec.layout.yaxis.rangemode, "tozero");
  assert.equal(spec.layout.hovermode, "x");
  assert.equal(spec.isEmpty, false);
});

test("lineSpec: each line keeps its own outcomes (no union zero-fill)", () => {
  const spec = lineSpec([
    { label: "a", items: [[1, 1]] },
    { label: "b", items: [[3, 1], [4, 1]] },
  ]);
  // a covers only outcome 1, b only 3,4 -- no dip-to-zero across the other's
  // outcomes, so markers land only on real outcomes.
  assert.deepEqual(spec.data[0].x, [1]);
  assert.deepEqual(spec.data[0].y, [100]);
  assert.deepEqual(spec.data[1].x, [3, 4]);
  assert.deepEqual(spec.data[1].y, [50, 50]);
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

// ---- ridgeSpec ----------------------------------------------------------

const approx = (a, b, eps = 1e-9) =>
  assert.ok(Math.abs(a - b) < eps, `expected ${a} ~= ${b}`);

// A ridge is two traces: the fill polygon (even index) and the visible line
// (odd index). The line is true to the actual outcomes and carries the hover;
// its max-above-baseline is what "scaling" controls.
const fillTrace = (spec, i) => spec.data[2 * i];
const lineTrace = (spec, i) => spec.data[2 * i + 1];
const ridgeHeight = (spec, i) => {
  const baseline = spec.layout.annotations[i].y; // labels sit at each baseline
  return Math.max(...lineTrace(spec, i).y) - baseline;
};

test("ridgeSpec: two traces per output (fill polygon + true-to-outcome line)", () => {
  const spec = ridgeSpec([
    { label: "a", items: [[1, 1], [2, 1]] },
    { label: "b", items: [[3, 1], [4, 1]] },
  ]);
  assert.equal(spec.data.length, 4);
  // Fill trace: self-closed polygon, no visible line, no hover.
  assert.equal(fillTrace(spec, 0).fill, "toself");
  assert.equal(fillTrace(spec, 0).line.width, 0);
  assert.equal(fillTrace(spec, 0).hoverinfo, "skip");
  // Line trace: the visible stroke -- no fill, carries name + hover.
  assert.equal(lineTrace(spec, 0).fill, undefined);
  assert.equal(lineTrace(spec, 0).name, "a");
  assert.equal(lineTrace(spec, 0).mode, "lines+markers"); // dots on each outcome
  assert.equal(spec.isEmpty, false);
});

test("ridgeSpec: outputs[0] is the top band, labelled via a left-aligned annotation", () => {
  const spec = ridgeSpec([
    { label: "a", items: [[1, 1]] },
    { label: "b", items: [[2, 1]] },
  ]);
  const [a, b] = spec.layout.annotations;
  assert.equal(a.text, "a");
  assert.equal(b.text, "b");
  // Pinned left-aligned to the plot's left edge (paper x=0), not a y-axis tick.
  assert.equal(a.xref, "paper");
  assert.equal(a.x, 0);
  assert.equal(a.xanchor, "left");
  // a (index 0) sits above b (index 1).
  assert.ok(a.y > b.y);
  // The y-axis carries no tick labels now.
  assert.equal(spec.layout.yaxis.showticklabels, false);
});

test("ridgeSpec: line true to outcomes; fill closes to baseline with a small foot", () => {
  const spec = ridgeSpec([
    { label: "a", items: [[1, 1]] }, // single outcome
    { label: "b", items: [[3, 1], [4, 1]] }, // outcomes 3,4
  ]);
  // Line: exactly the output's own outcomes -- no union fill, no tail padding,
  // so it never runs flat out to another output's extent.
  assert.deepEqual(lineTrace(spec, 0).x, [1]);
  assert.deepEqual(lineTrace(spec, 0).customdata, [100]);
  assert.deepEqual(lineTrace(spec, 1).x, [3, 4]);
  assert.deepEqual(lineTrace(spec, 1).customdata, [50, 50]);
  // Fill: every ridge closes to the baseline with a +/-0.1 foot at each end
  // (single or multi) -- so a lone spike (a) is a narrow triangle, not a sliver.
  assert.deepEqual(fillTrace(spec, 0).x, [0.9, 1, 1.1]);
  assert.deepEqual(fillTrace(spec, 1).x, [2.9, 3, 4, 4.1]);
  // Both lines carry markers (a dot per outcome); for the single-outcome ridge
  // the marker is also what makes its segment-less line visible.
  assert.equal(lineTrace(spec, 0).mode, "lines+markers");
  assert.equal(lineTrace(spec, 1).mode, "lines+markers");
});

test("ridgeSpec: shared scaling keeps peak heights comparable", () => {
  // a peaks at 100%, b at 50%; shared scale -> b's ridge is half as tall, and
  // the global peak reaches exactly overlap*ROW_STEP. Pin overlap so the test
  // asserts the scaling, not the current default.
  const spec = ridgeSpec(
    [
      { label: "a", items: [[1, 1]] },
      { label: "b", items: [[1, 1], [2, 1]] },
    ],
    { overlap: 2 },
  );
  approx(ridgeHeight(spec, 0), 2);
  approx(ridgeHeight(spec, 1), 1);
});

test("ridgeSpec: normalize 'each' makes every ridge reach the same peak", () => {
  const spec = ridgeSpec(
    [
      { label: "a", items: [[1, 1]] },
      { label: "b", items: [[1, 1], [2, 1]] },
    ],
    { normalize: "each", overlap: 2 },
  );
  approx(ridgeHeight(spec, 0), 2);
  approx(ridgeHeight(spec, 1), 2);
});

test("ridgeSpec: overlap option scales the peak height", () => {
  const spec = ridgeSpec([{ label: "a", items: [[1, 1]] }], { overlap: 3 });
  approx(ridgeHeight(spec, 0), 3);
});

test("ridgeSpec: precision flows into the hover template", () => {
  const spec = ridgeSpec([{ label: "a", items: [[1, 1]] }], { precision: 4 });
  assert.match(lineTrace(spec, 0).hovertemplate, /%\{customdata:\.4f\}%/);
});

test("ridgeSpec: theme.series colors ridges; opaque line, translucent fill", () => {
  const spec = ridgeSpec(
    [
      { label: "a", items: [[1, 1]] },
      { label: "b", items: [[2, 1]] },
    ],
    { theme: { series: ["#112233", "#445566"] } },
  );
  // Line keeps the solid theme hue; the separate fill polygon is that hue at
  // FILL_ALPHA so overlapping ridges read through. No trace-level opacity --
  // that would dim the crisp line along with the fill.
  assert.equal(lineTrace(spec, 0).line.color, "#112233");
  assert.equal(lineTrace(spec, 0).opacity, undefined);
  assert.equal(fillTrace(spec, 0).fillcolor, "rgba(17, 34, 51, 0.4)");
  assert.equal(lineTrace(spec, 1).line.color, "#445566");
  assert.equal(fillTrace(spec, 1).fillcolor, "rgba(68, 85, 102, 0.4)");
});

test("ridgeSpec: themed label gets a translucent pill for legibility", () => {
  const spec = ridgeSpec([{ label: "a", items: [[1, 1]] }], {
    theme: { series: ["#112233"], bg: "#ffffff", muted: "#666666" },
  });
  const ann = spec.layout.annotations[0];
  // Background pill from the theme bg at partial alpha; muted theme text on top.
  assert.match(ann.bgcolor, /^rgba\(255, 255, 255, /);
  assert.equal(ann.font.color, "#666666");
});

test("ridgeSpec: no outcomes -> isEmpty", () => {
  const spec = ridgeSpec([{ label: "x", items: [] }]);
  assert.equal(spec.isEmpty, true);
});
