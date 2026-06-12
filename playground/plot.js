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
  { xMax = null, precision = DEFAULT_PLOT_PRECISION } = {},
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
            font: { size: 14 },
          },
        ],
        margin: { l: 40, r: 20, t: 40, b: 40 },
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
      },
    ],
    layout: {
      title: { text: label },
      height: chartHeight(items.length),
      xaxis: {
        title: { text: "Probability (%)" },
        ...(xMax !== null ? { range: [0, xMax] } : { rangemode: "tozero" }),
      },
      yaxis: {
        title: { text: "Outcome" },
        type: "category",
        // The first item we passed has the smallest outcome; Plotly's
        // default category order would put it at the BOTTOM of the y-axis.
        // Flip so smallest is on top -- matches the text view's ordering.
        autorange: "reversed",
      },
      margin: { l: 60, r: 20, t: MARGIN_TOP_PX, b: MARGIN_BOTTOM_PX },
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
export function renderPlots(container, outputs, Plotly, { precision } = {}) {
  container.replaceChildren();
  if (!outputs || outputs.length === 0) {
    const empty = document.createElement("div");
    empty.className = "plot-empty";
    empty.textContent = "(no output)";
    container.appendChild(empty);
    return;
  }
  // Shared x-axis range: every chart runs [0, global max + 5% headroom] so
  // bar lengths are comparable across outputs. Null when no output has
  // mass; each chart then auto-ranges (moot -- they're all empty).
  const maxPct = globalMaxPercent(outputs);
  const xMax = maxPct === null ? null : maxPct * 1.05;
  for (const { label, items } of outputs) {
    const div = document.createElement("div");
    div.className = "plot";
    container.appendChild(div);
    const spec = plotSpec(label, items, { xMax, precision });
    Plotly.newPlot(div, spec.data, spec.layout, {
      responsive: true,
      displaylogo: false,
      // Keep the modebar lean; we don't ship the geo / 3d / etc. plugins.
      modeBarButtonsToRemove: ["lasso2d", "select2d"],
    });
  }
}
