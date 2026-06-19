// Draggable resizer for grid-based panes, supporting both axes.
//
// Splits a CSS-grid container into first-pane / resizer / second-pane along
// either axis. The resizer is a thin element that the user drags; the
// container's grid-template-rows (axis "row") or grid-template-columns
// (axis "column") is updated live to reflect the new ratio. Position is
// expressed as the FIRST pane's share of the available space (container
// minus resizer), in [MIN_PERCENT, MAX_PERCENT] so neither pane fully
// disappears.
//
// Pure helpers (clampPercent, pointerToPercent) are exported separately so
// they can be unit-tested without a DOM; applyLayout takes any object with
// a .style and is testable with a stub. attachResizer wires pointer events
// to the actual elements.

export const MIN_PERCENT = 10;
export const MAX_PERCENT = 90;

// Clamp a percentage to [min, max]. Returns null for non-finite input so a
// bad call site can be detected; the caller is expected to fall back to its
// last known value (or the CSS default).
export function clampPercent(p, min = MIN_PERCENT, max = MAX_PERCENT) {
  if (!Number.isFinite(p)) return null;
  return Math.max(min, Math.min(max, p));
}

// Convert a pointer coordinate (viewport x or y, depending on the axis) to
// the first pane's share of the container's content extent. `containerStart`
// and `containerExtent` are the container's viewport-relative leading edge
// and total size along the drag axis (typically from getBoundingClientRect:
// top/height for rows, left/width for columns). `resizerSize` is the
// resizer's thickness in px; subtracting it gives the space actually
// available to the two panes. Returns null if the available space is
// non-positive (degenerate layout).
export function pointerToPercent(
  pointerCoord,
  containerStart,
  containerExtent,
  resizerSize,
) {
  const available = containerExtent - resizerSize;
  if (available <= 0) return null;
  return ((pointerCoord - containerStart) / available) * 100;
}

// Apply a two-pane grid template around a fixed-size resizer track, on the
// given axis. Direct DOM write; no framework.
export function applyLayout(container, firstPercent, resizerSize, axis) {
  const value = `${firstPercent}fr ${resizerSize}px ${100 - firstPercent}fr`;
  if (axis === "column") {
    container.style.gridTemplateColumns = value;
  } else {
    container.style.gridTemplateRows = value;
  }
}

// Attach pointer-drag handlers to a resizer element inside a grid container.
//
// Options:
//   container:      the parent grid element whose template we mutate
//   resizer:        the thin handle element that captures pointer events
//   axis:           "row" (default; drag up/down, mutates grid-template-rows)
//                   or "column" (drag left/right, grid-template-columns)
//   resizerSize:    thickness (px) of the resizer track; defaults to 6
//   initialPercent: starting first-pane share (in clamp range); if provided,
//                   layout is applied immediately. If omitted, the
//                   container's existing CSS layout is left alone until the
//                   user drags.
//   onSettled:      called with the final percent when the user releases the
//                   pointer (i.e. one save per drag, not one per pointermove)
//
// Returns a cleanup function that removes the listeners (useful in tests or
// hot-reload scenarios; not used by the playground itself).
export function attachResizer({
  container,
  resizer,
  axis = "row",
  resizerSize = 6,
  initialPercent,
  onSettled,
}) {
  const isColumn = axis === "column";
  const cursor = isColumn ? "col-resize" : "row-resize";

  if (initialPercent !== undefined && initialPercent !== null) {
    applyLayout(container, initialPercent, resizerSize, axis);
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
    document.body.style.cursor = cursor;
    document.body.style.userSelect = "none";
    e.preventDefault();
  }

  function onPointerMove(e) {
    if (!dragging) return;
    const rect = container.getBoundingClientRect();
    const raw = pointerToPercent(
      isColumn ? e.clientX : e.clientY,
      isColumn ? rect.left : rect.top,
      isColumn ? rect.width : rect.height,
      resizerSize,
    );
    const pct = clampPercent(raw);
    if (pct === null) return;
    applyLayout(container, pct, resizerSize, axis);
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
