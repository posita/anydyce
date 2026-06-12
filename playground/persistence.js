// Editor-content persistence across reloads.
//
// Pure-JS module (no CodeMirror, no DOM access except localStorage / history
// / location, which are mockable) so the helpers can be unit-tested under
// Node. The playground main file (playground.js) imports these and wires the
// debounced save into CodeMirror's update listener.
//
// Contract:
//   - On editor idle (~500ms after last keystroke), save the current doc
//     under localStorage["anydyce-playground:doc"] and strip any URL
//     fragment so the bare URL on reload picks up the saved doc.
//   - On initial load, fall back to the saved doc IFF no URL fragment is
//     present (the fragment wins, so shared links work first visit).
//   - localStorage access can throw in private-browsing modes -- always
//     wrap in try/catch and treat errors as "no-op + carry on".

export const STORAGE_KEY = "anydyce-playground:doc";
export const LOGS_SPLIT_KEY = "anydyce-playground:logs-split";
export const VIEW_MODE_KEY = "anydyce-playground:view-mode";

export const VIEW_MODE_BARS = "bars";
export const VIEW_MODE_TEXT = "text";
const _ALL_VIEW_MODES = new Set([VIEW_MODE_BARS, VIEW_MODE_TEXT]);

// Read the saved editor doc, or null if absent / unreadable.
export function loadSavedDoc(storage = globalThis.localStorage) {
  try {
    if (!storage) return null;
    const text = storage.getItem(STORAGE_KEY);
    return text === null ? null : text;
  } catch {
    return null;
  }
}

// Persist the editor doc. Silent no-op on storage error (private browsing,
// quota exceeded, etc.).
export function saveDoc(text, storage = globalThis.localStorage) {
  try {
    if (!storage) return;
    storage.setItem(STORAGE_KEY, text);
  } catch {
    // ignore
  }
}

// Read the persisted output/logs split as a number (the output pane's
// percent share), or null if absent / unparsable / out of plausible range.
// Validation is light -- the consumer clamps to its own bounds before use,
// so we only reject obvious garbage here.
export function loadLogsSplit(storage = globalThis.localStorage) {
  try {
    if (!storage) return null;
    const raw = storage.getItem(LOGS_SPLIT_KEY);
    if (raw === null) return null;
    const n = Number(raw);
    if (!Number.isFinite(n)) return null;
    return n;
  } catch {
    return null;
  }
}

// Persist the output/logs split as a percentage string. Silent no-op on
// storage error, same as saveDoc.
export function saveLogsSplit(percent, storage = globalThis.localStorage) {
  try {
    if (!storage) return;
    storage.setItem(LOGS_SPLIT_KEY, String(percent));
  } catch {
    // ignore
  }
}

// Read the persisted output-pane view mode ("bars" or "text"), or null if
// absent or set to an unrecognized value. The consumer applies its own
// default for null.
export function loadViewMode(storage = globalThis.localStorage) {
  try {
    if (!storage) return null;
    const raw = storage.getItem(VIEW_MODE_KEY);
    if (raw === null) return null;
    return _ALL_VIEW_MODES.has(raw) ? raw : null;
  } catch {
    return null;
  }
}

// Persist the view mode. Silent no-op on storage error / unknown mode.
export function saveViewMode(mode, storage = globalThis.localStorage) {
  if (!_ALL_VIEW_MODES.has(mode)) return;
  try {
    if (!storage) return;
    storage.setItem(VIEW_MODE_KEY, mode);
  } catch {
    // ignore
  }
}

// Strip the URL fragment without reloading or triggering a hashchange event.
// `history.replaceState` doesn't fire hashchange, which is what we want --
// the existing hashchange listener in playground.js shouldn't react to our
// post-save cleanup. No-op if no fragment is present.
//
// loc / hist params exist for testability; in the browser they default to
// the globals.
export function stripUrlFragment(
  loc = globalThis.location,
  hist = globalThis.history,
) {
  try {
    if (!loc || !hist) return;
    if (!loc.hash) return;
    // location.pathname + location.search keeps the path and any ?query=
    // intact; only the #fragment is dropped.
    hist.replaceState(null, "", loc.pathname + loc.search);
  } catch {
    // ignore (e.g. file:// origins with restricted history APIs)
  }
}

// Build a debounced save scheduler. Each call to the returned function
// resets a `delayMs` timer; when the timer fires, `onFire(latestText)` runs
// once. Independent of any specific timer source so tests can inject a fake
// scheduler.
export function createDebouncedSaver({
  delayMs = 500,
  onFire,
  setTimer = setTimeout,
  clearTimer = clearTimeout,
} = {}) {
  let pending = null;
  let latest = null;
  function schedule(text) {
    latest = text;
    if (pending !== null) clearTimer(pending);
    pending = setTimer(() => {
      pending = null;
      onFire(latest);
    }, delayMs);
  }
  function flush() {
    if (pending !== null) {
      clearTimer(pending);
      pending = null;
      onFire(latest);
    }
  }
  function cancel() {
    if (pending !== null) {
      clearTimer(pending);
      pending = null;
    }
  }
  return { schedule, flush, cancel };
}
