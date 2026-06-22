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
export const EDITOR_SPLIT_KEY = "anydyce-playground:editor-split";
export const VIEW_MODE_KEY = "anydyce-playground:view-mode";

export const VIEW_MODE_BARS = "bars";
export const VIEW_MODE_LINES = "lines";
export const VIEW_MODE_TEXT = "text";
const _ALL_VIEW_MODES = new Set([
  VIEW_MODE_BARS,
  VIEW_MODE_LINES,
  VIEW_MODE_TEXT,
]);

export const ACCENT_KEY = "anydyce-playground:accent";
// Accent hue keys = the color slots usable as an accent (the neutrals are
// excluded). Order is the swatch row's display order (roughly spectral).
// Each maps to var(--c-<key>) via an html[data-accent] rule in
// playground.css; "cyan" is the default and matches the base --accent.
export const ACCENTS = ["red", "yellow", "green", "cyan", "blue", "magenta"];
export const DEFAULT_ACCENT = "cyan";
const _ACCENT_SET = new Set(ACCENTS);

export const THEME_KEY = "anydyce-playground:theme";
// Theme family keys. "default" lives in themes.css's bare :root (no
// attribute); the rest are html[data-theme="<key>"] blocks. The picker's
// <option> values must match these.
export const THEMES = ["default", "no-color", "colorblind", "high-contrast"];
export const DEFAULT_THEME = "default";
const _THEME_SET = new Set(THEMES);

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

// Shared numeric load/save for the divider-position keys. Validation is
// light -- the consumer clamps to its own bounds before use, so we only
// reject obvious garbage here. Silent no-op / null on storage error, same
// as saveDoc / loadSavedDoc.
function loadNumber(key, storage) {
  try {
    if (!storage) return null;
    const raw = storage.getItem(key);
    if (raw === null) return null;
    const n = Number(raw);
    if (!Number.isFinite(n)) return null;
    return n;
  } catch {
    return null;
  }
}

function saveNumber(key, value, storage) {
  try {
    if (!storage) return;
    storage.setItem(key, String(value));
  } catch {
    // ignore
  }
}

// Output/logs divider position (the output pane's percent share).
export function loadLogsSplit(storage = globalThis.localStorage) {
  return loadNumber(LOGS_SPLIT_KEY, storage);
}

export function saveLogsSplit(percent, storage = globalThis.localStorage) {
  saveNumber(LOGS_SPLIT_KEY, percent, storage);
}

// Editor/output divider position (the editor pane's percent share).
export function loadEditorSplit(storage = globalThis.localStorage) {
  return loadNumber(EDITOR_SPLIT_KEY, storage);
}

export function saveEditorSplit(percent, storage = globalThis.localStorage) {
  saveNumber(EDITOR_SPLIT_KEY, percent, storage);
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

// Read the persisted accent hue, or null if absent / unrecognized. The
// consumer applies DEFAULT_ACCENT for null.
export function loadAccent(storage = globalThis.localStorage) {
  try {
    if (!storage) return null;
    const raw = storage.getItem(ACCENT_KEY);
    return _ACCENT_SET.has(raw) ? raw : null;
  } catch {
    return null;
  }
}

// Persist the accent hue. Silent no-op on storage error / unknown hue.
export function saveAccent(accent, storage = globalThis.localStorage) {
  if (!_ACCENT_SET.has(accent)) return;
  try {
    if (!storage) return;
    storage.setItem(ACCENT_KEY, accent);
  } catch {
    // ignore
  }
}

// Read the persisted theme family, or null if absent / unrecognized. The
// consumer applies DEFAULT_THEME for null.
export function loadTheme(storage = globalThis.localStorage) {
  try {
    if (!storage) return null;
    const raw = storage.getItem(THEME_KEY);
    return _THEME_SET.has(raw) ? raw : null;
  } catch {
    return null;
  }
}

// Persist the theme family. Silent no-op on storage error / unknown theme.
export function saveTheme(theme, storage = globalThis.localStorage) {
  if (!_THEME_SET.has(theme)) return;
  try {
    if (!storage) return;
    storage.setItem(THEME_KEY, theme);
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
