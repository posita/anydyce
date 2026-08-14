// Plotly rendering and theme adaptation for dyce's portable figure specs.

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

// Render the consolidated line overlay emitted by dyce.
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
