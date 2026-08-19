// Tests for the Plotly theme helpers (../plot.js).
//
// Run with: node --test playground/test/test-plot.mjs

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  CHART_CHROME_PX,
  PX_PER_OUTCOME,
  chartHeight,
  readCssTheme,
  themePortableSpec,
  themeRidgeSpec,
} from "../plot.js";

// ---- chartHeight / uniform bar thickness ---------------------------------

test("chartHeight: each additional outcome adds exactly PX_PER_OUTCOME", () => {
  assert.equal(chartHeight(7) - chartHeight(6), PX_PER_OUTCOME);
  assert.equal(chartHeight(1), CHART_CHROME_PX + PX_PER_OUTCOME);
});

// ---- theme -----------------------------------------------------------------

const THEME = {
  bg: "#14171c",
  surface: "#181b1f",
  text: "#e6edf3",
  muted: "#8b949e",
  border: "#2d333b",
  accent: "#4cc38a",
  fontFamily: "TestFont, sans-serif",
};

test("readCssTheme: returns null outside a DOM", () => {
  // Node has no document; the default param resolves to undefined.
  assert.equal(readCssTheme(), null);
  assert.equal(readCssTheme(null), null);
});

// ---- themeRidgeSpec -----------------------------------------------------

test("themePortableSpec themes dyce line series without changing geometry", () => {
  const portable = {
    data: [{
      x: [1n, 2n],
      y: [25, 75],
      marker: { size: 5 },
      meta: { series: 1, role: "line" },
    }],
    layout: { xaxis: {}, yaxis: {} },
    config: { responsive: true },
  };
  const spec = themePortableSpec(portable, {
    ...THEME,
    series: ["#111111", "#222222"],
  });
  assert.deepEqual(spec.data[0].x, [1, 2]);
  assert.equal(spec.data[0].line.color, "#222222");
  assert.equal(spec.data[0].marker.color, "#222222");
  assert.equal(spec.data[0].hoverlabel.bgcolor, "#222222");
  assert.equal(spec.data[0].hoverlabel.bordercolor, "#222222");
  assert.equal(spec.data[0].hoverlabel.font.color, THEME.bg);
  assert.equal(spec.layout.hoverlabel.bgcolor, THEME.surface);
  assert.equal(spec.layout.hoverlabel.bordercolor, THEME.text);
  assert.equal(spec.layout.hoverlabel.font.color, THEME.text);
  assert.equal(portable.data[0].line, undefined);
  assert.equal(portable.data[0].hoverlabel, undefined);
});

test("themePortableSpec uses the accent for dyce bars", () => {
  const portable = {
    data: [{ marker: { color: "#000" }, meta: { series: 0, role: "bar" } }],
    layout: {},
    config: {},
  };
  const spec = themePortableSpec(portable, THEME, { accentBars: true });
  assert.equal(spec.data[0].marker.color, THEME.accent);
});

test("themePortableSpec preserves exact horizontal-bar outcomes", () => {
  const outcomes = [-(2n ** 80n), 2n ** 80n];
  const portable = {
    data: [{
      x: [25, 75],
      y: outcomes,
      orientation: "h",
      hovertemplate: "%{y}: %{customdata}%",
      meta: { series: 0, role: "bar" },
    }],
    layout: { xaxis: {}, yaxis: { title: { text: "Outcome" } } },
  };
  const spec = themePortableSpec(portable, THEME, { accentBars: true });
  assert.deepEqual(spec.data[0].y, outcomes.map(String));
  assert.equal(spec.data[0].hovertemplate, "%{y}: %{customdata}%");
  assert.equal(spec.layout.yaxis.automargin, true);
  assert.equal(spec.layout.yaxis.type, "category");
});

test("themePortableSpec uses elided ordinal ticks for unsafe line outcomes", () => {
  const outcomes = [-(2n ** 80n), 0n, 2n ** 80n];
  const portable = {
    data: [{
      x: outcomes,
      y: [25, 50, 25],
      hovertemplate: "%{x}: %{y}%",
      meta: { series: 0, role: "line" },
    }],
    layout: { xaxis: {}, yaxis: {} },
  };
  const spec = themePortableSpec(portable, THEME);
  assert.deepEqual(spec.data[0].x, [0, 1, 2]);
  assert.deepEqual(spec.data[0].text, outcomes.map(String));
  assert.equal(spec.data[0].hovertemplate, "%{text}: %{y}%");
  assert.deepEqual(spec.layout.xaxis.tickvals, [0, 1, 2]);
  assert.deepEqual(spec.layout.xaxis.ticktext, ["-1208…6176", "0", "12089…6176"]);
});

const portableRidge = {
  data: [
    {
      x: [0.9, 1, 1.1],
      y: [0, 2.4, 0],
      fill: "toself",
      fillcolor: "rgba(0, 0, 0, 0.4)",
      line: { width: 0 },
      meta: { ridge: 0, role: "fill" },
    },
    {
      x: [1],
      y: [2.4],
      customdata: [100],
      line: { color: "#000000", width: 1.5 },
      marker: { color: "#000000", size: 4 },
      meta: { ridge: 0, role: "line" },
    },
  ],
  layout: {
    xaxis: { title: { text: "Outcome" } },
    yaxis: { showticklabels: false },
    annotations: [
      {
        name: "ridge-label",
        text: "a",
        bgcolor: "rgba(0, 0, 0, 0.72)",
        borderpad: 2,
      },
      {
        name: "ridge-peak-label",
        text: "100%",
        bgcolor: "rgba(0, 0, 0, 0.72)",
        arrowcolor: "rgba(0, 0, 0, 0.4)",
        arrowwidth: 0.75,
        borderpad: 2,
      },
    ],
    shapes: [],
  },
  config: { responsive: true, displaylogo: false },
};

const ridgeTheme = {
  series: ["#112233"],
  bg: "#ffffff",
  surface: "#f5f5f5",
  text: "#222222",
  muted: "#666666",
  border: "#cccccc",
  fontFamily: "sans-serif",
};

test("themeRidgeSpec preserves dyce geometry, structure, and config", () => {
  const spec = themeRidgeSpec(portableRidge, ridgeTheme);
  assert.deepEqual(spec.data[0].x, portableRidge.data[0].x);
  assert.deepEqual(spec.data[0].y, portableRidge.data[0].y);
  assert.deepEqual(spec.data[1].customdata, [100]);
  assert.equal(spec.data[0].fill, "toself");
  assert.deepEqual(spec.config, portableRidge.config);
});

test("themeRidgeSpec themes matching ridge fills, lines, and tooltips", () => {
  const spec = themeRidgeSpec(portableRidge, ridgeTheme);
  assert.equal(spec.data[0].fillcolor, "rgba(17, 34, 51, 0.4)");
  assert.equal(spec.data[1].line.color, "#112233");
  assert.equal(spec.data[1].marker.color, "#112233");
  assert.equal(spec.data[1].hoverlabel.bgcolor, "#112233");
});

test("themeRidgeSpec themes label pill while preserving dyce opacity", () => {
  const spec = themeRidgeSpec(portableRidge, ridgeTheme);
  assert.equal(spec.layout.annotations[0].bgcolor, "rgba(245, 245, 245, 0.72)");
  assert.equal(spec.layout.annotations[0].font.color, "#666666");
  assert.equal(spec.layout.annotations[0].borderpad, 2);
});

test("themeRidgeSpec themes the peak callout", () => {
  const spec = themeRidgeSpec(portableRidge, ridgeTheme);
  assert.equal(
    spec.layout.annotations[1].bgcolor,
    "rgba(245, 245, 245, 0.72)",
  );
  assert.equal(spec.layout.annotations[1].arrowcolor, "rgba(17, 34, 51, 0.4)");
  assert.equal(spec.layout.annotations[1].arrowwidth, 0.75);
});

test("themeRidgeSpec keeps peak colors aligned across empty ridges", () => {
  const portable = structuredClone(portableRidge);
  portable.layout.annotations = [
    { name: "ridge-label", text: "empty" },
    { name: "ridge-label", text: "b" },
    {
      name: "ridge-peak-label",
      text: "100%",
      arrowcolor: "rgba(0, 0, 0, 0.4)",
    },
  ];
  const spec = themeRidgeSpec(portable, {
    ...ridgeTheme,
    series: ["#112233", "#445566"],
  });
  assert.equal(spec.layout.annotations[2].arrowcolor, "rgba(68, 85, 102, 0.4)");
});

test("themeRidgeSpec uses elided ordinal ticks for unsafe outcomes", () => {
  const outcomes = [-(2n ** 80n), 2n ** 80n];
  const portable = structuredClone(portableRidge);
  portable.data[0].x = [0, 0, 0, 0];
  portable.data[0].y = [0, 2.4, 2.4, 0];
  portable.data[1].x = outcomes;
  portable.data[1].y = [2.4, 2.4];
  portable.data[1].customdata = [50, 50];
  portable.data[1].hovertemplate = "%{x}: %{customdata}%";
  portable.layout.annotations[1].x = outcomes[1];
  portable.layout.annotations[1].xref = "x";
  const spec = themeRidgeSpec(portable, ridgeTheme);
  assert.deepEqual(spec.data[0].x, [-0.1, 0, 1, 1.1]);
  assert.deepEqual(spec.data[1].x, [0, 1]);
  assert.deepEqual(spec.data[1].text, outcomes.map(String));
  assert.equal(spec.data[1].hovertemplate, "%{text}: %{customdata}%");
  assert.equal(spec.layout.annotations[1].x, 1);
  assert.deepEqual(spec.layout.xaxis.tickvals, [0, 1]);
  assert.deepEqual(spec.layout.xaxis.ticktext, ["-1208…6176", "12089…6176"]);
});

test("themeRidgeSpec does not mutate the portable input", () => {
  const before = structuredClone(portableRidge);
  themeRidgeSpec(portableRidge, ridgeTheme);
  assert.deepEqual(portableRidge, before);
});

test("themeRidgeSpec recognizes an empty portable figure", () => {
  assert.equal(
    themeRidgeSpec({ data: [], layout: {}, config: {} }, ridgeTheme).isEmpty,
    true,
  );
});
