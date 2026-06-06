// AnyDice Playground -- editor wiring.
//
// Wires the CodeMirror 6 editor, the Pyodide worker runtime (see
// pyodide-runner.js), the Run / Cancel / Share buttons, and URL-fragment
// program hydration:
//   `#p=<base64url>` -- inline program text encoded in the URL fragment
//                       (sync; no network involvement).
//   `#id=<hex>`      -- corpus program ID; fetched async from the GitHub
//                       raw-content mirror via ./corpus-mirror.js.
// `#p=` takes precedence if both are present.
//
// Cancel terminates the Pyodide worker mid-run; a fresh worker is then
// re-initialized (incurs the ~5s Pyodide load again, but guarantees the
// runtime is back in a clean state regardless of what the prior run was
// doing in C-level Python code).

// CodeMirror 6 imports use bare specifiers; the importmap in index.html maps
// them to esm.sh URLs. See the importmap comment for the version-pinning and
// peer-dep-externalization (`*` prefix) story.
import { EditorView, keymap } from "@codemirror/view";
import { Prec } from "@codemirror/state";
import { basicSetup } from "codemirror";
import { indentWithTab } from "@codemirror/commands";
import { HighlightStyle, syntaxHighlighting } from "@codemirror/language";
import { tags as t } from "@lezer/highlight";
import { anydice } from "./anydice-mode.js";
import {
  CancelledError,
  RunError,
  cancelCurrentRun,
  initPyodide,
  runAnydice,
} from "./pyodide-runner.js";

// Editor theme. All tunable knobs (colors, sizes, paddings) live as CSS
// variables in playground.css; this block only handles the structural
// mapping from CM6 selectors to those variables. To change a value, edit
// playground.css; structural changes (which selector gets which kind of
// value) live here.
const anydiceEditorTheme = EditorView.theme({
  "&": {
    backgroundColor: "var(--bg)",
    color:           "var(--text)",
    height:          "100%",
  },
  ".cm-content":         { caretColor: "var(--text)" },
  // Block cursor: translucent background block (vs default border-left
  // line) so the character behind shows through. See playground.css for
  // the opacity/width knobs.
  ".cm-cursor, .cm-cursor-primary": {
    border:          "none",
    backgroundColor: "var(--text)",
    opacity:         "var(--cursor-opacity)",
    width:           "var(--cursor-width)",
    marginLeft:      "0",
  },
  ".cm-gutters": {
    backgroundColor: "var(--bg-elev)",
    color:           "var(--muted)",
    borderRight:     "1px solid var(--border)",
  },
  // Active-line tint MUST be semi-transparent. drawSelection's z-index:
  // -1 means an opaque .cm-line background would cover the selection on
  // whichever line the cursor sits on. See --active-line-bg.
  ".cm-activeLine":       { backgroundColor: "var(--active-line-bg)" },
  ".cm-activeLineGutter": { backgroundColor: "var(--active-line-bg)" },
  // Selection background. CM6-canonical pattern: two separate rules
  // (unfocused + focused) without a child combinator (which would miss
  // some of the per-line selection divs in multi-line selections).
  ".cm-selectionBackground, .cm-content ::selection": {
    backgroundColor: "var(--selection-bg) !important",
  },
  "&.cm-focused .cm-selectionBackground": {
    backgroundColor: "var(--selection-bg) !important",
  },
  ".cm-selectionMatch":  { backgroundColor: "var(--match-bg)" },
  ".cm-scroller":        { fontFamily: "var(--font-mono)" },
  ".cm-tooltip": {
    backgroundColor: "var(--bg-elev)",
    color:           "var(--text)",
    border:          "1px solid var(--border)",
  },
  // Find / replace panel (from @codemirror/search).
  ".cm-panels": {
    backgroundColor: "var(--bg-elev)",
    color:           "var(--text)",
  },
  ".cm-panels.cm-panels-top":    { borderBottom: "1px solid var(--border)" },
  ".cm-panels.cm-panels-bottom": { borderTop:    "1px solid var(--border)" },
  // CM6's default sizes .cm-textfield and .cm-button at 70% of their
  // parent; overriding them to "inherit" makes the whole panel scale
  // from the single --search-font-size knob.
  ".cm-search":                                    { fontSize: "var(--search-font-size)" },
  ".cm-search .cm-textfield, .cm-search .cm-button, .cm-search label": {
    fontSize: "inherit",
  },
  ".cm-textfield": {
    backgroundColor: "var(--bg)",
    color:           "var(--text)",
    border:          "1px solid var(--border)",
    borderRadius:    "var(--control-radius)",
    padding:         "var(--control-padding-y) var(--textfield-padding-x)",
    fontFamily:      "var(--font-mono)",
  },
  ".cm-textfield:focus": {
    outline:     "none",
    borderColor: "var(--accent)",
  },
  ".cm-button": {
    backgroundColor: "var(--bg)",
    color:           "var(--text)",
    border:          "1px solid var(--border)",
    borderRadius:    "var(--control-radius)",
    cursor:          "pointer",
    padding:         "var(--control-padding-y) var(--button-padding-x)",
    backgroundImage: "none",
  },
  ".cm-button:hover":    { backgroundColor: "var(--code-bg)" },
  ".cm-button:active":   { backgroundColor: "var(--border)" },
  ".cm-search label":    { color: "var(--muted)" },
  // Close button (the X in the corner). Slightly larger than the other
  // controls so the X glyph isn't visually undersized.
  ".cm-search [name=close]": {
    color:      "var(--muted)",
    background: "transparent",
    border:     "none",
    fontSize:   "var(--search-close-font-size)",
    lineHeight: "1",
  },
  ".cm-search [name=close]:hover": { color: "var(--text)" },
});

// Syntax-highlight style driven by the same CSS variables. We define this
// as a high-precedence style so it wins over basicSetup's defaultHighlightStyle.
const anydiceHighlightStyle = HighlightStyle.define([
  { tag: t.keyword,         color: "var(--syn-keyword)" },
  { tag: t.operatorKeyword, color: "var(--syn-op-kw)" },
  { tag: t.variableName,    color: "var(--syn-var)" },
  { tag: t.propertyName,    color: "var(--syn-prop)" },
  { tag: t.number,          color: "var(--syn-num)" },
  { tag: t.string,          color: "var(--syn-str)" },
  { tag: t.comment,         color: "var(--syn-comment)", fontStyle: "italic" },
  { tag: t.operator,        color: "var(--syn-op)" },
  { tag: t.bracket,         color: "var(--syn-bracket)" },
  { tag: t.punctuation,     color: "var(--syn-punct)" },
]);

const SAMPLE_PROGRAM = `\\ ============================================ /
  This program is meant to illustrate what
  expressions like d2d3 really mean, since it
  is probably not what you think or want.
/ ============================================ \\

function: roll N:n of the die D:d { result: NdD }

output [roll 4 of the die d3]                       named "same as output 4d3"
output [roll d2 of the die d3]                      named "same as output d2d3"
output [roll 2d4 of the die d3]                     named "same as output 2d4d3"
output [roll [roll d2 of the die d4] of the die d3] named "same as output d2d4d3"
output [roll 2 of the die 4d3]                      named "same as output 2d(4d3)"
output [roll d2 of the die 4d3]                     named "same as output d2d(4d3)"
`;

// ---- URL fragment helpers ---------------------------------------------------
// The pure encoding logic lives in ./url-fragment.js and ./corpus-mirror.js so
// both can be unit-tested under Node without DOM. This file wraps them with
// the location-reading bits and the fetch logic for #id=.

import {
  b64urlEncode,
  parseUrlHashForProgram,
  parseUrlHashForProgramId,
} from "./url-fragment.js";
import { ghMirrorUrlForProgramId, programIdAsHex } from "./corpus-mirror.js";

// Pull a program from `#p=...` if present, else return null. Synchronous --
// the inline-encoded program is decoded immediately with no I/O.
function programFromUrl() {
  return parseUrlHashForProgram(location.hash);
}

// Fetch the program identified by `#id=...` from the corpus mirror, or return
// null if the URL doesn't contain `#id=` or the fetch fails. Async because it
// makes a network request. Caller handles editor update + status messages.
async function fetchProgramFromUrl() {
  const rawId = parseUrlHashForProgramId(location.hash);
  if (!rawId) return null;
  // Normalize the ID via corpus-mirror's parser (handles case, leading zeros,
  // sign). Throws on malformed input -- catch and surface as null.
  let hexId;
  try {
    hexId = programIdAsHex(rawId);
  } catch {
    setStatus(`Invalid program ID: ${rawId}`);
    return null;
  }
  const url = ghMirrorUrlForProgramId(hexId);
  setStatus(`Loading program 0x${hexId} from corpus...`);
  try {
    const resp = await fetch(url);
    if (!resp.ok) {
      if (resp.status === 404) {
        setStatus(`Program 0x${hexId} not found in corpus.`);
      } else {
        setStatus(`Failed to load 0x${hexId}: HTTP ${resp.status}.`);
      }
      return null;
    }
    const text = await resp.text();
    setStatus(`Loaded program 0x${hexId}.`);
    return text;
  } catch (err) {
    setStatus(`Failed to load 0x${hexId}: ${err.message || err}.`);
    return null;
  }
}

// ---- DOM refs and helpers ---------------------------------------------------

const statusEl  = document.getElementById("status");
const runBtn    = document.getElementById("run-btn");
const shareBtn  = document.getElementById("share-btn");
const cancelBtn = document.getElementById("cancel-btn");
const outputEl  = document.getElementById("output");
const logsEl    = document.getElementById("logs");

function setStatus(msg) {
  if (statusEl) statusEl.textContent = msg;
}

function renderResults(results) {
  outputEl.classList.remove("output-placeholder");
  if (results.length === 0) {
    outputEl.textContent = "(no output)";
    return;
  }
  const blocks = results.map(({ label, text }) => `=== ${label} ===\n${text}`);
  outputEl.textContent = blocks.join("\n\n");
}

function renderError(err) {
  // Output shows a short error summary only; the full traceback lives in
  // the logs pane (see logTraceback). Keeping output terse means the eye
  // can quickly tell "did it work?" without scrolling past 30 lines of
  // traceback.
  outputEl.classList.remove("output-placeholder");
  const detail = (err && err.message) || String(err);
  outputEl.textContent = `Error: ${detail}`;
}

// ---- Logs pane -------------------------------------------------------------
//
// Cleared at the start of every run, so the pane always reflects just the
// current run's warnings / errors / cancel events. The output and logs
// panes together represent one run: output for results, logs for
// diagnostic messages. The Run button doubles as the clear action.
//
// Severity classes (.log-entry-info / -warning / -error / -cancel /
// -traceback) drive CSS colors; see playground.css.

let logsHasContent = false;

function resetLogs() {
  logsEl.textContent = "";
  logsEl.classList.remove("logs-placeholder");
  logsHasContent = true;
}

function scrollLogsToBottom() {
  logsEl.scrollTop = logsEl.scrollHeight;
}

function logEntry(severity, text) {
  if (!logsHasContent) resetLogs();
  const entry = document.createElement("div");
  entry.className = `log-entry log-entry-${severity}`;
  entry.textContent = text;
  logsEl.appendChild(entry);
  scrollLogsToBottom();
}

function logWarnings(warnings) {
  if (!warnings || warnings.length === 0) return;
  for (const w of warnings) {
    // Format mirrors Python's default warning formatter, which users will
    // recognize from console output: filename:lineno: Category: message.
    const loc = w.filename ? `${w.filename}:${w.lineno}: ` : "";
    logEntry("warning", `${loc}${w.category}: ${w.message}`);
  }
}

function logTraceback(traceback) {
  if (!traceback) return;
  if (!logsHasContent) resetLogs();
  const block = document.createElement("div");
  block.className = "log-entry log-entry-traceback";
  block.textContent = traceback.trimEnd();
  logsEl.appendChild(block);
  scrollLogsToBottom();
}

// Forward-declared so the keymap binding below can close over it without
// touching it at registration time. Assigned by the `new EditorView(...)`
// call later in this file.
let editor;
let runtimeReady = false;
// Set when the user hits Run / Shift-Enter before the runtime is ready.
// The initPyodide .then() callback checks this flag and auto-fires
// handleRun() the moment Pyodide finishes loading, so the user's click
// isn't lost to timing.
let runPending = false;
// Lock: at most one in-flight run per output pane. The Run button is
// disabled during a run, but the Shift-Enter keymap binding bypasses the
// disabled state, so a separate flag is needed to make the guard work for
// both code paths.
let runInFlight = false;

async function handleRun() {
  if (!runtimeReady) {
    runPending = true;
    setStatus("Run queued; will execute when runtime is ready.");
    return;
  }
  if (runInFlight) {
    // Already running; silently ignore the extra trigger rather than
    // queueing it. If the user wants concurrent runs, they can open a
    // second tab.
    return;
  }
  runInFlight = true;
  const source = editor.state.doc.toString();
  // Visual run-in-progress state: clear the output pane, disable the Run
  // button, enable the Cancel button, and reflect running in the corner
  // status. The Shift-Enter keymap binding calls into handleRun() the same
  // way the button click does, so both paths get this behavior. Restoration
  // happens in the `finally` block below, regardless of whether the run
  // succeeded, threw, or was cancelled.
  // (With Pyodide now in a worker, the main thread stays responsive during
  // the run; the rAF yield from the prior single-threaded version is no
  // longer needed.)
  setStatus("Running...");
  runBtn.disabled = true;
  cancelBtn.disabled = false;
  cancelBtn.title = "Cancel the current run (terminates and re-initializes the worker)";
  outputEl.classList.remove("output-placeholder");
  outputEl.textContent = "";
  resetLogs();
  const t0 = performance.now();
  try {
    const { results, warnings } = await runAnydice(source);
    const dt = Math.round(performance.now() - t0);
    logWarnings(warnings);
    renderResults(results);
    setStatus(`Ran in ${dt} ms.`);
  } catch (err) {
    if (err instanceof CancelledError) {
      // Cancel is a deliberate user action, not a failure. handleCancel()
      // updates the status and re-inits the runtime; don't overwrite that
      // here.
      outputEl.textContent = "(cancelled)";
      logEntry("cancel", "Cancelled by user.");
    } else if (err instanceof RunError) {
      // Python-level error from the program. Output gets the short summary;
      // logs get the traceback (and any warnings emitted before the throw).
      logWarnings(err.warnings);
      renderError(err);
      logEntry("error", err.message);
      logTraceback(err.traceback);
      setStatus("Run failed.");
    } else {
      // Anything else is a runtime-level failure (worker crash, etc.) --
      // no traceback or warnings available.
      renderError(err);
      logEntry("error", (err && err.message) || String(err));
      setStatus("Run failed.");
    }
  } finally {
    runInFlight = false;
    runBtn.disabled = false;
    cancelBtn.disabled = true;
    cancelBtn.title = "No run in progress";
  }
}

async function handleCancel() {
  if (!runInFlight) return;
  // Disable Cancel immediately to avoid double-clicks during the (brief)
  // teardown + re-init window.
  cancelBtn.disabled = true;
  cancelBtn.title = "Cancelling...";
  setStatus("Cancelling and re-initializing runtime...");
  // Mark runtime as not-ready so any Run / Shift-Enter triggered during
  // re-init gets queued (handleRun checks runtimeReady).
  runtimeReady = false;
  // Terminate the worker. The pending run's Promise rejects with
  // CancelledError; handleRun's catch handles the UI for that, and its
  // finally re-enables runBtn. We disable it again below for the re-init
  // window.
  cancelCurrentRun();
  // Yield once so handleRun's catch + finally run before we proceed.
  await Promise.resolve();
  runBtn.disabled = true;
  try {
    await initPyodide(setStatus);
    runtimeReady = true;
    runBtn.disabled = false;
    if (runPending) {
      // Same queued-run logic as the initial-load path: if the user clicked
      // Run while re-init was in progress, honor it now.
      runPending = false;
      handleRun();
    }
  } catch (err) {
    setStatus("Runtime failed to re-initialize. Reload to recover.");
    renderError(err);
  }
}

// ---- Editor -----------------------------------------------------------------

// Initial document. Two-stage hydration:
//   1. Synchronous: if `#p=` is present in the URL, decode and use it for the
//      initial editor doc -- no flicker, no network round-trip.
//   2. Asynchronous: if `#id=` is present (and `#p=` wasn't), the editor
//      starts with the bundled sample, then a fetch kicks off and replaces
//      the doc when it completes (handled below, after `editor` exists).
const initialDoc = programFromUrl() ?? SAMPLE_PROGRAM;

editor = new EditorView({
  parent: document.getElementById("editor"),
  doc: initialDoc,
  extensions: [
    basicSetup,
    // Shift-Enter runs the program. Registered through CM6's keymap (NOT a
    // DOM-level listener) so CM6 treats the binding as consumed and skips
    // its own Enter command. Wrap in Prec.high() so this keymap is
    // consulted BEFORE basicSetup's defaultKeymap -- without it, the
    // canonical-shift-field-on-Enter pattern still doesn't fire (CM6's
    // defaultKeymap Enter binding wins at default precedence). Returning
    // true from `run` signals "I handled this key; do not fall through to
    // lower-precedence bindings or default behavior".
    Prec.high(keymap.of([
      indentWithTab,
      {
        key: "Shift-Enter",
        run: () => {
          handleRun();
          return true;
        },
        preventDefault: true,
      },
    ])),
    anydice,
    syntaxHighlighting(anydiceHighlightStyle),
    anydiceEditorTheme,
  ],
});

// Expose for ad-hoc poking during development.
window.editor = editor;

// Stage 2 of URL hydration: if the URL has `#id=` (and not `#p=`), fetch the
// program from the corpus mirror and replace the editor's content when it
// arrives. This runs in parallel with Pyodide startup -- by the time the
// runtime is ready, the corpus program will (probably) already be loaded.
if (programFromUrl() === null) {
  fetchProgramFromUrl().then((text) => {
    if (text !== null && text !== editor.state.doc.toString()) {
      editor.dispatch({
        changes: { from: 0, to: editor.state.doc.length, insert: text },
      });
    }
  });
}

// ---- Runtime wiring ---------------------------------------------------------

// Eager background load: kick off Pyodide initialization as soon as the page
// is interactive, so by the time the user clicks Run the runtime is
// (probably) ready. The Run button stays disabled until init succeeds.
initPyodide(setStatus)
  .then(() => {
    runtimeReady = true;
    runBtn.disabled = false;
    runBtn.title = "Run the program (Shift+Enter)";
    if (runPending) {
      // User clicked Run / hit Shift-Enter while loading; honor the
      // queued click now that the runtime is up. handleRun() reads from
      // editor state at call time, so any edits the user made during
      // the wait are reflected in the run.
      runPending = false;
      handleRun();
    } else if (outputEl.classList.contains("output-placeholder")) {
      outputEl.textContent =
        "Click Run (or Shift+Enter in the editor). Output will appear here.";
    }
  })
  .catch((err) => {
    setStatus("Runtime failed to load.");
    renderError(err);
  });

runBtn.addEventListener("click", handleRun);
cancelBtn.addEventListener("click", handleCancel);

// ---- Share URL --------------------------------------------------------------

async function handleShare() {
  const source = editor.state.doc.toString();
  const encoded = b64urlEncode(source);
  const shareUrl = `${location.origin}${location.pathname}#p=${encoded}`;
  // Update the address bar (no reload). Doesn't trigger hashchange when the
  // hash is unchanged, but the editor already contains the latest content
  // anyway, so a no-op event would be benign.
  history.replaceState(null, "", `#p=${encoded}`);
  try {
    await navigator.clipboard.writeText(shareUrl);
    setStatus("Share URL copied to clipboard.");
  } catch (err) {
    // Clipboard API can fail in non-secure contexts or when not focused.
    // Fall back to surfacing the URL in the output pane so the user can
    // copy it manually.
    outputEl.classList.remove("output-placeholder");
    outputEl.textContent =
      `Share URL (copy manually -- clipboard access denied):\n\n${shareUrl}`;
    setStatus("Share URL ready (clipboard unavailable).");
  }
}

shareBtn.addEventListener("click", handleShare);

// ---- Hash-change reload -----------------------------------------------------

// Back/forward navigation between programs without page reload. Tries `#p=`
// first (sync), then `#id=` (async). Skips dispatch when the new text matches
// the current editor content to avoid undo-stack churn.
function replaceEditorDoc(text) {
  if (text === editor.state.doc.toString()) return;
  editor.dispatch({
    changes: { from: 0, to: editor.state.doc.length, insert: text },
  });
}

window.addEventListener("hashchange", async () => {
  const sync = programFromUrl();
  if (sync !== null) {
    replaceEditorDoc(sync);
    return;
  }
  const fetched = await fetchProgramFromUrl();
  if (fetched !== null) replaceEditorDoc(fetched);
});
