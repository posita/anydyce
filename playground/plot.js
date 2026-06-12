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

// Build a Plotly figure spec for a single output's histogram.
//
// label:  text to display as the plot title (the AnyDice output's name).
// items:  array of [outcome, count] pairs in outcome order. Counts may be
//         BigInt or Number; outcomes are integers.
//
// Returns {data, layout, isEmpty}. `isEmpty` is true when the distribution
// has no mass (empty items, all-zero counts, or null items); in that case
// `data` is a no-trace spec and `layout` carries an "(empty)" annotation,
// so the layout still renders a labeled placeholder rather than an empty
// container with no context.
export function plotSpec(label, items) {
  const percents = itemsToPercents(items);
  if (percents === null) {
    return {
      data: [],
      layout: {
        title: { text: `${label} (empty)` },
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
  const hover = percents.map((p) => `${p.toFixed(4)}%`);
  return {
    data: [
      {
        type: "bar",
        orientation: "h",
        x: percents,
        y,
        text: hover,
        textposition: "auto",
        hovertemplate: "%{y}: %{x:.4f}%<extra></extra>",
      },
    ],
    layout: {
      title: { text: label },
      xaxis: {
        title: { text: "Probability (%)" },
        rangemode: "tozero",
      },
      yaxis: {
        title: { text: "Outcome" },
        type: "category",
        // The first item we passed has the smallest outcome; Plotly's
        // default category order would put it at the BOTTOM of the y-axis.
        // Flip so smallest is on top -- matches the text view's ordering.
        autorange: "reversed",
      },
      margin: { l: 60, r: 20, t: 40, b: 50 },
    },
    isEmpty: false,
  };
}

// Render a list of outputs as stacked horizontal bar charts inside `container`.
// Each output gets its own <div> with a Plotly chart. Requires a Plotly object
// (the lazily-loaded plotly.js module's default export or namespace).
//
// outputs: array of {label, items}. label is a string, items is an array of
//          [outcome, count] pairs.
export function renderPlots(container, outputs, Plotly) {
  container.replaceChildren();
  if (!outputs || outputs.length === 0) {
    const empty = document.createElement("div");
    empty.className = "plot-empty";
    empty.textContent = "(no output)";
    container.appendChild(empty);
    return;
  }
  for (const { label, items } of outputs) {
    const div = document.createElement("div");
    div.className = "plot";
    container.appendChild(div);
    const spec = plotSpec(label, items);
    Plotly.newPlot(div, spec.data, spec.layout, {
      responsive: true,
      displaylogo: false,
      // Keep the modebar lean; we don't ship the geo / 3d / etc. plugins.
      modeBarButtonsToRemove: ["lasso2d", "select2d"],
    });
  }
}
