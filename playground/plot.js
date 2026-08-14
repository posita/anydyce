// Plotly figure-spec construction for AnyDice histograms.
//
// `plotSpec(label, items)` is pure (no DOM, no Plotly imports) so its math
// can be unit-tested under Node. The actual rendering wrapper
// `renderPlots(container, outputs)` lives below and requires Plotly to be
// loaded; it's the only DOM-bound bit.

// Retained for consumers of raw worker output; Plotly views now receive their
// percentages directly in dyce's portable specifications.
const PERCENT_SCALE = 10n ** 15n;
const PERCENT_DIVISOR = 1e13;

function asBigInt(x) {
  return typeof x === "bigint" ? x : BigInt(x);
}

export function itemsToPercents(items) {
  if (!items || items.length === 0) return null;
  let total = 0n;
  const counts = items.map(([, count]) => {
    const value = asBigInt(count);
    total += value;
    return value;
  });
  if (total === 0n) return null;
  return counts.map(
    (count) => Number((count * PERCENT_SCALE) / total) / PERCENT_DIVISOR,
  );
}

// Vertical sizing: every outcome row gets the same pixel allotment in every
// chart, so bar thickness is uniform across outputs regardless of how many
// outcomes each output has.
export const PX_PER_OUTCOME = 24;
// Per-chart chrome: the title above (top margin) and x-axis labels below
// (bottom margin). plotSpec builds its layout margins from these SAME
// constants, so chartHeight is correct by construction -- there is no
// second copy to drift.
export const MARGIN_TOP_PX = 40;
export const MARGIN_BOTTOM_PX = 50;
export const CHART_CHROME_PX = MARGIN_TOP_PX + MARGIN_BOTTOM_PX;
export const EMPTY_CHART_PX = 120;

export const DEFAULT_PLOT_PRECISION = 2;

function normalizePrecision(precision) {
  return Number.isInteger(precision) && precision >= 0
    ? precision
    : DEFAULT_PLOT_PRECISION;
}

// Read the chart theme from the CSS custom properties in playground.css --
// the single source of truth for colors and fonts, including the dark-mode
// values behind the prefers-color-scheme media query. Returns a plain
// object consumable by plotSpec's `theme` option, or null outside a DOM
// (Node tests). Callers re-invoke per render, so a theme flip between
// renders is picked up automatically.
export function readCssTheme(root = globalThis.document?.documentElement) {
  if (!root) return null;
  const styles = getComputedStyle(root);
  const v = (name) => styles.getPropertyValue(name).trim();
  return {
    bg: v("--bg"),
    text: v("--text"),
    muted: v("--muted"),
    border: v("--border"),
    accent: v("--accent"),
    fontFamily: v("--font-ui"),
    // Qualitative palette for the line view, pulled from the theme's hue
    // slots so it follows light/dark AND the theme family (Default /
    // Colorblind / High contrast / No color). Plotly cycles traces through
    // layout.colorway when no per-trace color is set. (No-color collapses
    // to one repeated hue -- lines are then distinguished only by the
    // legend; line-style cycling is a deliberate future add.)
      series: [
          "blue", "red", "green",
          "yellow", "cyan", "magenta",
          "blue-muted", "red-muted", "green-muted",
          "yellow-muted", "cyan-muted", "magenta-muted",
      ]
      .map((h) => v(`--c-${h}`))
      .filter(Boolean),
  };
}

// Layout-level theme injection. Returns {} when theme is null/undefined so
// plotSpec stays usable (with Plotly's defaults) in themeless contexts
// like unit tests.
function themeLayoutBits(theme) {
  if (!theme) return {};
  return {
    paper_bgcolor: theme.bg,
    plot_bgcolor: theme.bg,
    font: { color: theme.text, family: theme.fontFamily },
    hoverlabel: {
      bgcolor: theme.bg,
      bordercolor: theme.border,
      font: { color: theme.text, family: theme.fontFamily },
    },
    modebar: {
      color: theme.muted,
      activecolor: theme.text,
      bgcolor: "transparent",
    },
  };
}

// Per-axis theme injection (grid / line / tick colors).
function themeAxisBits(theme) {
  if (!theme) return {};
  return {
    gridcolor: theme.border,
    linecolor: theme.border,
    zerolinecolor: theme.border,
    tickfont: { color: theme.muted },
  };
}

// The theme's qualitative palette (theme.series) when present, else null --
// shared by the line view (as layout.colorway) and the ridge (per-trace color
// cycling). Optional chaining tolerates a null theme or a palette-less theme.
function themePalette(theme) {
  return theme?.series?.length ? theme.series : null;
}

export function chartHeight(nOutcomes) {
  return CHART_CHROME_PX + nOutcomes * PX_PER_OUTCOME;
}

// The largest single-outcome percent across ALL outputs, or null when no
// output has mass. Used to give every chart the same x-axis range so bar
// lengths are comparable across outputs, not just within one.
export function globalMaxPercent(outputs) {
  let max = null;
  for (const { items } of outputs || []) {
    const percents = itemsToPercents(items);
    if (percents === null) continue;
    for (const v of percents) {
      if (max === null || v > max) max = v;
    }
  }
  return max;
}

// Build a Plotly figure spec for a single output's histogram.
//
// label:      text to display as the plot title (the AnyDice output's name).
// items:      array of [outcome, count] pairs in outcome order. Counts may
//             be BigInt or Number; outcomes are integers.
// xMax:       optional shared x-axis maximum (percent). When provided, the
//             x-axis range is fixed to [0, xMax] so bar lengths are
//             comparable across charts; when omitted, the axis auto-ranges
//             to this chart alone. renderPlots passes the padded global max
//             across outputs.
// precision:  decimal places for percent labels (bar text + hover). Comes
//             from the run's final `set "anydyce: display precision"` value
//             so both views format numbers identically.
// theme:      optional color/font object (see readCssTheme). When provided,
//             backgrounds, text, axes, bars, and hover labels follow the
//             playground's CSS theme (including dark mode); when omitted,
//             Plotly's defaults apply (themeless unit-test contexts).
//
// Returns {data, layout, isEmpty}. `isEmpty` is true when the distribution
// has no mass (empty items, all-zero counts, or null items); in that case
// `data` is a no-trace spec and `layout` carries an "(empty)" annotation,
// so the layout still renders a labeled placeholder rather than an empty
// container with no context.
//
// layout.height is computed via chartHeight so that every outcome row gets
// PX_PER_OUTCOME pixels regardless of how many outcomes this particular
// output has -- uniform bar thickness across charts.
export function plotSpec(
  label,
  items,
  { xMax = null, precision = DEFAULT_PLOT_PRECISION, theme = null } = {},
) {
  const prec = normalizePrecision(precision);
  const percents = itemsToPercents(items);
  if (percents === null) {
    return {
      data: [],
      layout: {
        title: { text: `${label} (empty)` },
        height: EMPTY_CHART_PX,
        xaxis: { visible: false },
        yaxis: { visible: false },
        annotations: [
          {
            text: "(empty distribution)",
            xref: "paper",
            yref: "paper",
            x: 0.5,
            y: 0.5,
            showarrow: false,
            font: { size: 14, ...(theme ? { color: theme.muted } : {}) },
          },
        ],
        margin: { l: 40, r: 20, t: 40, b: 40 },
        ...themeLayoutBits(theme),
      },
      isEmpty: true,
    };
  }
  // Horizontal bars: outcomes on the y-axis (treated as categories so
  // non-contiguous integers don't leave gaps), percent on the x-axis.
  const y = items.map(([o]) => String(o));
  const barText = percents.map((p) => `${p.toFixed(prec)}%`);
  return {
    data: [
      {
        type: "bar",
        orientation: "h",
        x: percents,
        y,
        text: barText,
        textposition: "auto",
        hovertemplate: `%{y}: %{x:.${prec}f}%<extra></extra>`,
        ...(theme ? { marker: { color: theme.accent } } : {}),
      },
    ],
    layout: {
      title: { text: label },
      height: chartHeight(items.length),
      xaxis: {
        ...(xMax !== null ? { range: [0, xMax] } : { rangemode: "tozero" }),
        ...themeAxisBits(theme),
      },
      yaxis: {
        type: "category",
        // The first item we passed has the smallest outcome; Plotly's
        // default category order would put it at the BOTTOM of the y-axis.
        // Flip so smallest is on top -- matches the text view's ordering.
        autorange: "reversed",
        ...themeAxisBits(theme),
      },
      margin: { l: 60, r: 20, t: MARGIN_TOP_PX, b: MARGIN_BOTTOM_PX },
      ...themeLayoutBits(theme),
    },
    isEmpty: false,
  };
}

// Config passed to every Plotly.newPlot in this module: responsive to window
// resizes, no Plotly logo, and a lean modebar (we don't ship the geo / 3d /
// etc. plugins, so drop their leftover buttons).
const PLOTLY_CONFIG = {
  responsive: true,
  displaylogo: false,
  modeBarButtonsToRemove: ["lasso2d", "select2d"],
};

// Append a "(...)" status line (e.g. "(empty distribution)") into an empty
// chart container.
function appendPlaceholder(container, text) {
  const div = document.createElement("div");
  div.className = "plot-empty";
  div.textContent = text;
  container.appendChild(div);
}

// Render a consolidated chart from a local JavaScript spec builder. Clears
// `container`, builds the figure via `buildSpec(outputs,
// {precision, theme})`, and hands it to Plotly. The chart fills the pane via CSS
// (its .plot grows to the container height) rather than a per-outcome height
// computation, and the CSS theme is re-read per call so the palette tracks the
// current light/dark + family. The dyce-backed ridge view has its own thin
// renderer below because its portable spec arrives from the worker.
function renderConsolidated(
  container,
  outputs,
  Plotly,
  buildSpec,
  { precision } = {},
) {
  // Callers pass at least one output; the zero-output case is a whole-pane
  // message handled upstream (playground.js showMessage), not here.
  container.replaceChildren();
  const spec = buildSpec(outputs, { precision, theme: readCssTheme() });
  if (spec.isEmpty) {
    appendPlaceholder(container, "(empty distribution)");
    return;
  }
  const div = document.createElement("div");
  div.className = "plot";
  container.appendChild(div);
  Plotly.newPlot(div, spec.data, spec.layout, PLOTLY_CONFIG);
}

// Render a list of outputs as stacked horizontal bar charts inside `container`.
// Each output gets its own <div> with a Plotly chart. Requires a Plotly object
// (the plotly.js module's default export or namespace).
//
// outputs:   array of {label, items}. label is a string, items is an array
//            of [outcome, count] pairs.
// precision: decimal places for percent labels; see plotSpec.
//
// The CSS theme is re-read on every call, so charts always reflect the
// CURRENT light/dark palette; the caller is responsible for re-invoking on
// a prefers-color-scheme change (see the matchMedia listener in
// playground.js).
export function renderPlots(container, portableSpecs, Plotly) {
  container.replaceChildren();
  const theme = readCssTheme();
  for (const portableSpec of portableSpecs || []) {
    const spec = themePortableSpec(portableSpec, theme, { accentBars: true });
    const outcomeCount = spec.data[0]?.y?.length || 0;
    const div = document.createElement("div");
    div.className = "plot";
    container.appendChild(div);
    spec.layout.height = outcomeCount
      ? chartHeight(outcomeCount)
      : EMPTY_CHART_PX;
    spec.layout.title = {
      text: outcomeCount
        ? spec.data[0]?.name || ""
        : `${spec.data[0]?.name || ""} (empty)`,
    };
    spec.layout.margin = {
      l: 60,
      r: 20,
      t: MARGIN_TOP_PX,
      b: MARGIN_BOTTOM_PX,
    };
    spec.layout.yaxis = {
      ...spec.layout.yaxis,
      type: "category",
      autorange: "reversed",
    };
    Plotly.newPlot(div, spec.data, spec.layout, spec.config);
  }
}

// Each output's OWN outcomes and percents -- no union zero-fill. A line or ridge
// then spans just the outcomes that output actually has, bridging any interior
// "gap" (an outcome a neighboring output has but this one lacks) rather than
// dipping to the axis there, and putting a marker only on real outcomes. xs/ys
// are empty for an output with no mass. Returns
// [{label, xs: number[], ys: number[]}] -- the input to lineSpec.
export function perOutputSeries(outputs) {
  return (outputs || []).map(({ label, items }) => {
    const percents = itemsToPercents(items); // null for an empty distribution
    return {
      label,
      xs: percents ? items.map(([o]) => Number(o)) : [],
      ys: percents || [],
    };
  });
}

// Build a single Plotly figure overlaying every output as a line trace -- one
// consolidated chart (like anydice.com's graph view), versus plotSpec /
// renderPlots' one-chart-per-output bars.
//
// outputs:   array of {label, items}; see plotSpec.
// precision: decimal places for the percent hover labels.
// theme:     optional color/font object (see readCssTheme). theme.series
//            becomes layout.colorway, so traces cycle the theme palette.
//
// Each line spans only its OWN outcomes (see perOutputSeries) -- no union
// zero-fill -- so lines bridge interior gaps instead of saw-toothing down to the
// axis, and the markers land only on real outcomes. The x-axis is NUMERIC (not
// categorical) so the lines align on a shared scale and Plotly auto-picks a
// readable tick density. No per-trace color is set, so Plotly assigns from
// colorway.
export function lineSpec(
  outputs,
  { precision = DEFAULT_PLOT_PRECISION, theme = null } = {},
) {
  const prec = normalizePrecision(precision);
  const series = perOutputSeries(outputs);
  const palette = themePalette(theme);
  const data = series.map(({ label, xs, ys }) => ({
    type: "scatter",
    mode: "lines+markers",
    name: label,
    x: xs,
    y: ys,
    marker: { size: 5 },
    hovertemplate: `%{y:.${prec}f}%`,
  }));
  return {
    data,
    layout: {
      showlegend: true,
      // "x": a separate per-line tooltip at the outcome nearest the cursor's
      // horizontal position (like the ridge view). Alternative: "x unified" --
      // one combined box listing every series, which reads cleaner when the
      // lines bunch together on the shared y-axis.
      hovermode: "x",
      xaxis: {
        title: { text: "Outcome" },
        ...themeAxisBits(theme),
      },
      yaxis: {
        title: { text: "Probability (%)" },
        rangemode: "tozero",
        ...themeAxisBits(theme),
      },
      margin: { l: 60, r: 20, t: MARGIN_TOP_PX, b: MARGIN_BOTTOM_PX },
      ...(palette ? { colorway: palette } : {}),
      ...themeLayoutBits(theme),
    },
    isEmpty: series.every(({ xs }) => xs.length === 0),
  };
}

// Render the consolidated line overlay -- one chart overlaying every output as a
// line (cf. renderPlots' one-chart-per-output bars). See renderConsolidated.
export function renderLines(container, portableSpec, Plotly) {
  container.replaceChildren();
  const spec = themePortableSpec(portableSpec, readCssTheme());
  if (!spec || spec.data.every((trace) => !trace.x?.length)) {
    appendPlaceholder(container, "(empty distribution)");
    return;
  }
  spec.layout.margin = {
    l: 60,
    r: 20,
    t: MARGIN_TOP_PX,
    b: MARGIN_BOTTOM_PX,
  };
  const div = document.createElement("div");
  div.className = "plot";
  container.appendChild(div);
  Plotly.newPlot(div, spec.data, spec.layout, spec.config);
}

// Theme a portable dyce spec without changing its structural data. Metadata
// identifies series consistently across bar, line, and ridge builders.
export function themePortableSpec(spec, theme = null, { accentBars = false } = {}) {
  if (!spec) return null;
  const palette = themePalette(theme);
  const data = (spec.data || []).map((trace) => {
    const themed = {
      ...trace,
      ...(trace.x ? { x: trace.x.map((value) => Number(value)) } : {}),
      ...(trace.y ? { y: trace.y.map((value) => Number(value)) } : {}),
      ...(trace.line ? { line: { ...trace.line } } : {}),
      ...(trace.marker ? { marker: { ...trace.marker } } : {}),
    };
    const series = trace.meta?.series || 0;
    const color = accentBars && trace.meta?.role === "bar"
      ? theme?.accent
      : palette?.[series % palette.length];
    if (color) {
      themed.marker = { ...themed.marker, color };
      if (trace.meta?.role === "line") {
        themed.line = { ...themed.line, color };
        themed.hoverlabel = {
          ...(trace.hoverlabel || {}),
          bgcolor: color,
          bordercolor: color,
          font: { ...(trace.hoverlabel?.font || {}), color: theme.bg },
        };
      }
    }
    return themed;
  });
  return {
    data,
    layout: {
      ...(spec.layout || {}),
      xaxis: { ...(spec.layout?.xaxis || {}), ...themeAxisBits(theme) },
      yaxis: { ...(spec.layout?.yaxis || {}), ...themeAxisBits(theme) },
      ...themeLayoutBits(theme),
    },
    config: { ...(spec.config || PLOTLY_CONFIG) },
  };
}

// Return `color` with the alpha encoded by `template`. dyce owns structural
// opacity; the browser substitutes only the current theme's hue.
function withTemplateAlpha(color, template) {
  const match = String(template || "").match(
    /^rgba\([^,]+,[^,]+,[^,]+,\s*([\d.]+)\s*\)$/i,
  );
  return match ? withAlpha(color, Number(match[1])) : color;
}

function withAlpha(color, alpha) {
  if (!color) return color;
  const c = color.trim();
  let r, g, b;
  if (c[0] === "#") {
    const h = c.slice(1);
    if (h.length === 3 || h.length === 4) {
      [r, g, b] = [h[0], h[1], h[2]].map((d) => parseInt(d + d, 16));
    } else if (h.length === 6 || h.length === 8) {
      [r, g, b] = [h.slice(0, 2), h.slice(2, 4), h.slice(4, 6)].map((p) =>
        parseInt(p, 16),
      );
    } else {
      return color;
    }
  } else {
    const m = c.match(/rgba?\(([^)]+)\)/i);
    if (!m) return color;
    [r, g, b] = m[1].split(",").map((s) => parseFloat(s));
  }
  if (![r, g, b].every(Number.isFinite)) return color;
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

// Apply the page's current CSS theme to dyce's portable ridge PlotSpec without
// changing its geometry, ordering, hover text, or configuration. Trace metadata
// identifies each ridge and its fill/line role, so presentation does not depend
// on trace position. The input remains unchanged for later light/dark re-renders.
export function themeRidgeSpec(spec, theme = null) {
  if (!spec) return null;
  const palette = themePalette(theme);
  const data = (spec.data || []).map((trace) => {
    const themed = {
      ...trace,
      ...(trace.x ? { x: trace.x.map((value) => Number(value)) } : {}),
      ...(trace.y ? { y: trace.y.map((value) => Number(value)) } : {}),
      ...(trace.line ? { line: { ...trace.line } } : {}),
      ...(trace.marker ? { marker: { ...trace.marker } } : {}),
    };
    const ridge = trace.meta?.ridge;
    const color = palette?.length ? palette[ridge % palette.length] : null;
    if (color && trace.meta?.role === "fill") {
      themed.fillcolor = withTemplateAlpha(color, trace.fillcolor);
    } else if (color && trace.meta?.role === "line") {
      themed.line = { ...themed.line, color };
      themed.marker = { ...themed.marker, color };
      themed.hoverlabel = {
        ...(trace.hoverlabel || {}),
        bgcolor: color,
        bordercolor: color,
        font: { ...(trace.hoverlabel?.font || {}), color: theme.bg },
      };
    }
    return themed;
  });
  const annotations = (spec.layout?.annotations || []).map((annotation) => ({
    ...annotation,
    ...(theme
      ? {
          font: {
            ...(annotation.font || {}),
            color: theme.muted,
            family: theme.fontFamily,
          },
          bgcolor: withTemplateAlpha(theme.bg, annotation.bgcolor),
        }
      : {}),
  }));
  return {
    data,
    layout: {
      ...(spec.layout || {}),
      xaxis: { ...(spec.layout?.xaxis || {}), ...themeAxisBits(theme) },
      yaxis: { ...(spec.layout?.yaxis || {}), ...themeAxisBits(theme) },
      annotations,
      margin: { l: 40, r: 20, t: MARGIN_TOP_PX, b: MARGIN_BOTTOM_PX },
      ...themeLayoutBits(theme),
    },
    config: { ...(spec.config || {}) },
    isEmpty: data.every((trace) => !trace.x?.length),
  };
}

// Render the portable ridge figure emitted by dyce. AnyDice owns only the
// surrounding page theme and container presentation.
export function renderRidge(container, portableSpec, Plotly) {
  container.replaceChildren();
  const spec = themeRidgeSpec(portableSpec, readCssTheme());
  if (!spec || spec.isEmpty) {
    appendPlaceholder(container, "(empty distribution)");
    return;
  }
  const div = document.createElement("div");
  div.className = "plot";
  container.appendChild(div);
  Plotly.newPlot(div, spec.data, spec.layout, spec.config);
}
