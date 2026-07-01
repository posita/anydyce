// Plotly figure-spec construction for AnyDice histograms.
//
// `plotSpec(label, items)` is pure (no DOM, no Plotly imports) so its math
// can be unit-tested under Node. The actual rendering wrapper
// `renderPlots(container, outputs)` lives below and requires Plotly to be
// loaded; it's the only DOM-bound bit.

// Items can contain BigInt counts (Python ints > 2^53 cross the worker
// boundary as JS BigInts). Plotly can't plot BigInts directly, and naive
// `Number(c) / Number(total)` overflows to Infinity / loses precision for
// counts that don't fit in a float64 (any count with > ~16 decimal digits).
// We compute percent via scaled BigInt division and only cast at the end.
const PERCENT_SCALE = 10n ** 15n;
const PERCENT_DIVISOR = 1e13;

function asBigInt(x) {
  return typeof x === "bigint" ? x : BigInt(x);
}

// Convert a list of [outcome, count] pairs to percent values in [0, 100],
// preserving precision for counts of arbitrary magnitude. Returns an array
// of finite numbers; returns null if the total is zero (caller decides how
// to handle an empty / zero-mass distribution).
export function itemsToPercents(items) {
  if (!items || items.length === 0) return null;
  let total = 0n;
  const counts = items.map(([, c]) => {
    const b = asBigInt(c);
    total += b;
    return b;
  });
  if (total === 0n) return null;
  return counts.map((c) => Number((c * PERCENT_SCALE) / total) / PERCENT_DIVISOR);
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

// Decimal places for percent labels when the caller doesn't provide a
// precision. Matches anydyce's display-precision default so the bars view
// and the text view agree out of the box.
export const DEFAULT_PLOT_PRECISION = 2;

// Normalize a caller-provided precision to a safe non-negative integer,
// falling back to the default for anything else (undefined from an older
// worker message, null, NaN, negatives).
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
        // title: { text: "Probability (%)" },
        ...(xMax !== null ? { range: [0, xMax] } : { rangemode: "tozero" }),
        ...themeAxisBits(theme),
      },
      yaxis: {
        // title: { text: "Outcome" },
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
export function renderPlots(container, outputs, Plotly, { precision } = {}) {
  container.replaceChildren();
  if (!outputs || outputs.length === 0) {
    const empty = document.createElement("div");
    empty.className = "plot-empty";
    empty.textContent = "(no output)";
    container.appendChild(empty);
    return;
  }
  const theme = readCssTheme();
  // Shared x-axis range: every chart runs [0, global max + 5% headroom] so
  // bar lengths are comparable across outputs. Null when no output has
  // mass; each chart then auto-ranges (moot -- they're all empty).
  const maxPct = globalMaxPercent(outputs);
  const xMax = maxPct === null ? null : maxPct * 1.05;
  for (const { label, items } of outputs) {
    const div = document.createElement("div");
    div.className = "plot";
    container.appendChild(div);
    const spec = plotSpec(label, items, { xMax, precision, theme });
    Plotly.newPlot(div, spec.data, spec.layout, {
      responsive: true,
      displaylogo: false,
      // Keep the modebar lean; we don't ship the geo / 3d / etc. plugins.
      modeBarButtonsToRemove: ["lasso2d", "select2d"],
    });
  }
}

// Align every output's distribution onto the sorted union of all outcomes,
// zero-filling where a series has no mass. Each line then has a value at
// every outcome in the combined range, so the overlay reads like
// anydice.com's graph -- continuous lines that drop to 0 outside their own
// support -- rather than each line spanning only its own outcomes (which
// would interpolate straight across gaps). Returns
// { x: number[], series: [{label, y: number[]}] }.
export function alignedSeries(outputs) {
  const xSet = new Set();
  for (const { items } of outputs || []) {
    for (const [o] of items) xSet.add(Number(o));
  }
  const x = [...xSet].sort((a, b) => a - b);
  const indexOf = new Map(x.map((o, i) => [o, i]));
  const series = (outputs || []).map(({ label, items }) => {
    const y = new Array(x.length).fill(0);
    const percents = itemsToPercents(items); // null for an empty distribution
    if (percents !== null) {
      items.forEach(([o], i) => {
        y[indexOf.get(Number(o))] = percents[i];
      });
    }
    return { label, y };
  });
  return { x, series };
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
// The x-axis is NUMERIC (not categorical) so series align on a shared scale
// and Plotly auto-picks a readable tick density; the data is zero-filled
// across the outcome union (see alignedSeries) for line continuity. No
// per-trace color is set, so Plotly assigns from colorway.
export function lineSpec(
  outputs,
  { precision = DEFAULT_PLOT_PRECISION, theme = null } = {},
) {
  const prec = normalizePrecision(precision);
  const { x, series } = alignedSeries(outputs);
  const data = series.map(({ label, y }) => ({
    type: "scatter",
    mode: "lines",
    name: label,
    x,
    y,
    // hovermode "x unified" (see layout) shows the outcome once as the box
    // header and labels each row with the trace name, so the per-point
    // template only carries the percent; <extra></extra> drops the
    // otherwise-redundant secondary name box.
    // hovertemplate: `%{y:.${prec}f}%<extra></extra>`,
    hovertemplate: `%{y:.${prec}f}%`,
  }));
  return {
    data,
    layout: {
      showlegend: true,
      // One shared tooltip per outcome, listing every series' value --
      // good for comparing the distributions at a glance.
      hovermode: "x unified",
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
      ...(theme && theme.series && theme.series.length
        ? { colorway: theme.series }
        : {}),
      ...themeLayoutBits(theme),
    },
    isEmpty: x.length === 0,
  };
}

// Render the consolidated line overlay into `container`: a single Plotly
// chart (cf. renderPlots, which appends one chart per output). The chart
// fills the container via CSS (#output-lines .plot { flex: 1 }) -- its
// height is the pane's, not a per-outcome computation. The CSS theme is
// re-read per call, like renderPlots, so the palette tracks the current
// light/dark + family.
export function renderLines(container, outputs, Plotly, { precision } = {}) {
  container.replaceChildren();
  if (!outputs || outputs.length === 0) {
    const empty = document.createElement("div");
    empty.className = "plot-empty";
    empty.textContent = "(no output)";
    container.appendChild(empty);
    return;
  }
  const theme = readCssTheme();
  const spec = lineSpec(outputs, { precision, theme });
  if (spec.isEmpty) {
    const empty = document.createElement("div");
    empty.className = "plot-empty";
    empty.textContent = "(empty distribution)";
    container.appendChild(empty);
    return;
  }
  const div = document.createElement("div");
  div.className = "plot";
  container.appendChild(div);
  Plotly.newPlot(div, spec.data, spec.layout, {
    responsive: true,
    displaylogo: false,
    modeBarButtonsToRemove: ["lasso2d", "select2d"],
  });
}

// Vertical geometry for the ridgeline view, in data-space units. Each output's
// band sits one ROW_STEP above the next; a ridge's tallest point rises
// RIDGE_OVERLAP * ROW_STEP, so with overlap > 1 a ridge pokes up behind the
// band above it -- the characteristic ridgeline / "joy plot" look. ROW_STEP is
// arbitrary (the y-axis range is derived from it), so only their RATIO matters.
const ROW_STEP = 1;
const RIDGE_OVERLAP = 2.4;

// Fill translucency for ridges: the area under each curve is drawn at this
// alpha so overlapping ridges show THROUGH one another -- a tighter, more
// overlapped stack stays legible -- while the line on top stays fully opaque so
// each ridge's silhouette stays crisp. Trace-level opacity can't separate fill
// from line (it dims both), so the alpha is baked into the fillcolor below.
const FILL_ALPHA = 0.4;

// Return `color` as an "rgba(...)" string at the given alpha, so a ridge's fill
// can be translucent while its line stays solid. Accepts the hex the theme uses
// (#rgb / #rrggbb, with or without an alpha nibble) and rgb()/rgba() forms;
// anything it can't parse is returned unchanged (an opaque but still-valid
// fill, so a surprising theme value degrades rather than breaks).
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

// Build a single Plotly figure stacking every output as a filled "ridge" -- a
// third consolidated view (cf. lineSpec's overlay and plotSpec's per-output
// bars). Each output becomes a horizontal band whose distribution is drawn as a
// filled curve rising from a baseline; the bands are offset vertically and
// overlap. The visible LINE stays true to each output's own outcomes -- unlike
// the line view it is NOT zero-filled across the outcome union, so it (and the
// tooltips) cover just the outcomes that output actually has, bridging internal
// "gaps" (an outcome a neighbor has but this output lacks) rather than running
// flat out to other outputs' min/max. The fill drops straight to the baseline
// at each end (vertical edges, below) so the area closes without overhanging
// the real outcomes -- except a lone single-outcome spike, which gets a small
// foot so it doesn't collapse to zero width.
//
// outputs:   array of {label, items}; see plotSpec.
// precision: decimal places for the percent hover labels.
// theme:     optional color/font object (see readCssTheme). theme.series colors
//            the ridges (cycled, one hue per output); without it Plotly's
//            defaults apply (themeless unit-test contexts).
// overlap:   how far a ridge may rise, in row-steps (default RIDGE_OVERLAP);
//            > 1 makes ridges overlap, smaller values separate them.
// normalize: "shared" (default) scales every ridge by the SAME factor so peak
//            heights stay comparable across outputs -- matching the bars view's
//            shared x-range. "each" scales every ridge to its own max so all
//            peaks reach the same height (the classic ridgeline aesthetic, but
//            relative magnitude across outputs is no longer readable).
//
// Output order: outputs[0] is the TOP band, descending. Ridges rise upward and
// are emitted top band first, bottom band last, so Plotly draws the lower /
// front ridge over the one behind it where they overlap (mountains receding).
//
// Each ridge is two traces: a self-closed FILL polygon (the curve dropped
// vertically to the baseline at each end -- a single-outcome spike gets a small
// foot instead so it doesn't vanish -- drawn with no visible line) and then the
// visible LINE over it. The line carries the REAL percents in customdata
// (the plotted y is offset + scaled and never shown to the user); the label is
// a left-aligned annotation at the ridge's baseline (so long names extend
// rightward over the ridge instead of clipping in a gutter) -- no legend.
//
// Returns {data, layout, isEmpty}; isEmpty is true only when there are no
// outcomes at all (every output empty), matching lineSpec.
export function ridgeSpec(
  outputs,
  {
    precision = DEFAULT_PLOT_PRECISION,
    theme = null,
    overlap = RIDGE_OVERLAP,
    normalize = "shared",
  } = {},
) {
  const prec = normalizePrecision(precision);
  // Each ridge keeps ONLY its own outcomes (no union zero-fill); xs/ys are
  // empty for an output with no mass.
  const ridges = outputs.map(({ label, items }) => {
    const percents = itemsToPercents(items); // null for an empty distribution
    return {
      label,
      xs: percents ? items.map(([o]) => Number(o)) : [],
      ys: percents || [],
    };
  });
  const n = ridges.length;
  const palette =
    theme && theme.series && theme.series.length ? theme.series : null;
  const peakHeight = overlap * ROW_STEP;
  // Shared scale: one percent->height factor for every ridge, sized so the
  // single global tallest outcome reaches peakHeight. ("each" recomputes this
  // per ridge below.) globalMax is 0 only when every output is empty.
  const globalMax = ridges.reduce(
    (m, { ys }) => ys.reduce((mm, v) => (v > mm ? v : mm), m),
    0,
  );
  if (globalMax <= 0) {
    return { data: [], layout: {}, isEmpty: true };
  }
  const data = [];
  const annotations = [];
  ridges.forEach(({ label, xs, ys }, i) => {
    // outputs[0] on top: highest baseline at i=0, descending to 0.
    const baseline = (n - 1 - i) * ROW_STEP;
    // Label each ridge with a LEFT-aligned annotation pinned to the left edge of
    // the plot (paper x=0) at its baseline -- not a y-axis tick. A y-axis tick
    // is right-justified into the left margin, so a long output name grows
    // leftward and clips; this way it grows rightward, overlapping the ridge.
    annotations.push({
      xref: "paper",
      x: 0,
      xanchor: "left",
      xshift: 4,
      yref: "y",
      y: baseline,
      yanchor: "bottom",
      yshift: 2,
      text: label,
      showarrow: false,
      align: "left",
      // A translucent "pill" (the theme background) with a little padding keeps
      // the label legible where it overlaps a ridge's fill/line.
      ...(theme
        ? {
            font: { color: theme.muted, family: theme.fontFamily },
            bgcolor: withAlpha(theme.bg, 0.72),
            borderpad: 2,
          }
        : {}),
    });
    const localMax =
      normalize === "each" ? ys.reduce((mm, v) => (v > mm ? v : mm), 0) : globalMax;
    const scale = localMax > 0 ? peakHeight / localMax : 0;
    const color = palette ? palette[i % palette.length] : undefined;
    const curveY = ys.map((v) => baseline + v * scale);
    // A single-outcome ridge (common -- an always-true/false question like
    // "2d6 > 1" lands 100% on one outcome) would collapse to a zero-width sliver
    // with vertical edges, so give it a small foot instead.
    const single = xs.length === 1;
    const foot = single ? 0.5 : 0;
    // FILL: a self-closed polygon -- the curve plus a baseline point at each end
    // so the area drops to the baseline. A multi-outcome ridge anchors those at
    // the SAME x as min/max (vertical edges, no horizontal overhang past the
    // real outcomes); a single-outcome ridge uses a +/-0.5 foot so its lone
    // spike fills a visible unit-wide triangle. Internal "gaps" are bridged, NOT
    // dropped: a gap only means a neighbor has an outcome this output lacks, so
    // the area spans them like the line. No visible line (the line trace below
    // is the stroke) and no hover.
    const fillX = xs.length
      ? [xs[0] - foot, ...xs, xs[xs.length - 1] + foot]
      : [];
    const fillY = xs.length ? [baseline, ...curveY, baseline] : [];
    data.push({
      type: "scatter",
      mode: "lines",
      x: fillX,
      y: fillY,
      fill: "toself",
      line: { width: 0 },
      hoverinfo: "skip",
      showlegend: false,
      ...(color ? { fillcolor: withAlpha(color, FILL_ALPHA) } : {}),
    });
    // LINE: the visible stroke, true to the actual outcomes (no tails, no gap
    // padding), opaque over the translucent fill so it stays crisp where ridges
    // overlap. Carries the tooltips; the REAL percents ride in customdata (the
    // plotted y is offset + scaled and never shown). A single outcome has no
    // segment to stroke, so it also gets a marker -- a visible, hoverable dot.
    data.push({
      type: "scatter",
      mode: single ? "lines+markers" : "lines",
      x: xs,
      y: curveY,
      name: label,
      customdata: ys,
      hovertemplate: `${label}<br>%{x}: %{customdata:.${prec}f}%<extra></extra>`,
      showlegend: false,
      ...(color
        ? {
            line: { color, width: 1.5 },
            ...(single ? { marker: { color } } : {}),
          }
        : {}),
    });
  });
  return {
    data,
    layout: {
      showlegend: false,
      hovermode: "closest",
      xaxis: {
        title: { text: "Outcome" },
        ...themeAxisBits(theme),
      },
      yaxis: {
        // Labels are annotations (see above) and the baselines are the only
        // reference lines, so the y-axis carries no ticks, grid, or zeroline.
        showticklabels: false,
        showgrid: false,
        zeroline: false,
        range: [
          -0.5 * ROW_STEP,
          (n - 1) * ROW_STEP + peakHeight + 0.5 * ROW_STEP,
        ],
        ...themeAxisBits(theme),
      },
      annotations,
      // Slim left margin now that labels live inside the plot rather than in a
      // y-axis gutter (just enough for the leftmost x-axis tick label).
      margin: { l: 40, r: 20, t: MARGIN_TOP_PX, b: MARGIN_BOTTOM_PX },
      ...themeLayoutBits(theme),
    },
    isEmpty: false,
  };
}

// Render the consolidated ridgeline into `container`: a single Plotly chart
// (cf. renderLines). Like the line view it fills the pane via CSS rather than a
// per-outcome height computation, and re-reads the CSS theme per call so the
// palette tracks the current light/dark + family.
export function renderRidge(container, outputs, Plotly, { precision } = {}) {
  container.replaceChildren();
  if (!outputs || outputs.length === 0) {
    const empty = document.createElement("div");
    empty.className = "plot-empty";
    empty.textContent = "(no output)";
    container.appendChild(empty);
    return;
  }
  const theme = readCssTheme();
  const spec = ridgeSpec(outputs, { precision, theme });
  if (spec.isEmpty) {
    const empty = document.createElement("div");
    empty.className = "plot-empty";
    empty.textContent = "(empty distribution)";
    container.appendChild(empty);
    return;
  }
  const div = document.createElement("div");
  div.className = "plot";
  container.appendChild(div);
  Plotly.newPlot(div, spec.data, spec.layout, {
    responsive: true,
    displaylogo: false,
    modeBarButtonsToRemove: ["lasso2d", "select2d"],
  });
}
