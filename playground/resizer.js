// Draggable row-resizer for grid-based panes.
//
// Splits a vertical CSS-grid container into top-row / resizer / bottom-row.
// The resizer is a thin element that the user drags up/down; the container's
// grid-template-rows is updated live to reflect the new ratio. Position is
// expressed as `outputPercent` -- the share of the available height
// (container minus resizer) given to the top row, in [MIN_PERCENT,
// MAX_PERCENT] so neither pane fully disappears.
//
// Pure helpers (clampPercent, pointerYToPercent) are exported separately so
// they can be unit-tested without a DOM. attachRowResizer wires pointer
// events to the actual elements.

export const MIN_PERCENT = 10;
export const MAX_PERCENT = 90;

// Clamp a percentage to [min, max]. Returns null for non-finite input so a
// bad call site can be detected; the caller is expected to fall back to its
// last known value (or the CSS default).
export function clampPercent(p, min = MIN_PERCENT, max = MAX_PERCENT) {
  if (!Number.isFinite(p)) return null;
  return Math.max(min, Math.min(max, p));
}

// Convert a pointer Y in viewport coordinates to the top-row's share of the
// container's content height. `containerTop` and `containerHeight` are the
// container's viewport-relative top edge and total height (typically from
// getBoundingClientRect). `resizerSize` is the resizer row's height in px;
// subtracting it gives the height actually available to the two panes.
// Returns null if the available height is non-positive (degenerate layout).
export function pointerYToPercent(
  pointerY,
  containerTop,
  containerHeight,
  resizerSize,
) {
  const available = containerHeight - resizerSize;
  if (available <= 0) return null;
  return ((pointerY - containerTop) / available) * 100;
}

// Apply a grid-template-rows expressed as top/bottom percentages around a
// fixed-size resizer row. Direct DOM write; no React/no framework. Returns
// nothing.
export function applyRowLayout(container, outputPercent, resizerSize) {
  container.style.gridTemplateRows =
    `${outputPercent}fr ${resizerSize}px ${100 - outputPercent}fr`;
}

// Attach pointer-drag handlers to a resizer element inside a grid container.
//
// Options:
//   container:      the parent grid element whose gridTemplateRows we mutate
//   resizer:        the thin handle element that captures pointer events
//   resizerSize:    height (px) of the resizer row; defaults to 6
//   initialPercent: starting top-row share (in clamp range); if provided,
//                   layout is applied immediately. If omitted, the
//                   container's existing CSS layout is left alone until the
//                   user drags.
//   onSettled:      called with the final outputPercent when the user
//                   releases the pointer (i.e. one save per drag, not one
//                   per pointermove)
//
// Returns a cleanup function that removes the listeners (useful in tests or
// hot-reload scenarios; not used by the playground itself).
export function attachRowResizer({
  container,
  resizer,
  resizerSize = 6,
  initialPercent,
  onSettled,
}) {
  if (initialPercent !== undefined && initialPercent !== null) {
    applyRowLayout(container, initialPercent, resizerSize);
  }

  let dragging = false;
  let lastPct = initialPercent ?? null;

  function onPointerDown(e) {
    // Only left mouse button (or any touch / pen contact).
    if (e.pointerType === "mouse" && e.button !== 0) return;
    dragging = true;
    resizer.setPointerCapture(e.pointerId);
    // Force the resize cursor + suppress text selection globally for the
    // duration of the drag. Otherwise the cursor reverts to default whenever
    // the pointer crosses a child element with its own cursor rule, and the
    // browser may start selecting text in the panes as the pointer moves.
    document.body.style.cursor = "row-resize";
    document.body.style.userSelect = "none";
    e.preventDefault();
  }

  function onPointerMove(e) {
    if (!dragging) return;
    const rect = container.getBoundingClientRect();
    const raw = pointerYToPercent(
      e.clientY,
      rect.top,
      rect.height,
      resizerSize,
    );
    const pct = clampPercent(raw);
    if (pct === null) return;
    applyRowLayout(container, pct, resizerSize);
    lastPct = pct;
  }

  function onPointerUp(e) {
    if (!dragging) return;
    dragging = false;
    try {
      resizer.releasePointerCapture(e.pointerId);
    } catch {
      // Some browsers throw if the capture is no longer valid; safe to ignore.
    }
    document.body.style.cursor = "";
    document.body.style.userSelect = "";
    if (lastPct !== null && onSettled) onSettled(lastPct);
  }

  resizer.addEventListener("pointerdown", onPointerDown);
  resizer.addEventListener("pointermove", onPointerMove);
  resizer.addEventListener("pointerup", onPointerUp);
  resizer.addEventListener("pointercancel", onPointerUp);

  return function detach() {
    resizer.removeEventListener("pointerdown", onPointerDown);
    resizer.removeEventListener("pointermove", onPointerMove);
    resizer.removeEventListener("pointerup", onPointerUp);
    resizer.removeEventListener("pointercancel", onPointerUp);
  };
}
