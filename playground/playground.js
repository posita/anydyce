// AnyDice Playground -- editor wiring.
//
// First iteration: just sets up the CodeMirror 6 editor with the AnyDice
// syntax mode and a sample program. Pyodide integration / Run button /
// URL-fragment encoding will follow.

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
import { initPyodide, runAnydice } from "./pyodide-runner.js";

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

// ---- DOM refs and helpers ---------------------------------------------------

const statusEl = document.getElementById("status");
const runBtn   = document.getElementById("run-btn");
const outputEl = document.getElementById("output");

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
  outputEl.classList.remove("output-placeholder");
  const detail = (err && err.message) || String(err);
  outputEl.textContent = `Error:\n\n${detail}`;
}

// Forward-declared so the keymap binding below can close over it without
// touching it at registration time. Assigned by the `new EditorView(...)`
// call later in this file.
let editor;
let pyodideRef = null;
// Set when the user hits Run / Shift-Enter before the runtime is ready.
// The initPyodide .then() callback checks this flag and auto-fires
// handleRun() the moment Pyodide finishes loading, so the user's click
// isn't lost to timing.
let runPending = false;

async function handleRun() {
  if (!pyodideRef) {
    runPending = true;
    setStatus("Run queued; will execute when runtime is ready.");
    return;
  }
  const source = editor.state.doc.toString();
  // Visual run-in-progress state: clear the output pane, disable the Run
  // button, and reflect running in the corner status. The Shift-Enter
  // keymap binding calls into handleRun() the same way the button click
  // does, so both paths get this behavior. Restoration happens in the
  // `finally` block below, regardless of whether the run succeeded or threw.
  setStatus("Running...");
  runBtn.disabled = true;
  outputEl.classList.remove("output-placeholder");
  outputEl.textContent = "";
  // Yield to the event loop so the browser actually paints the "running"
  // state before we hand control to Pyodide. runPython is synchronous and
  // blocks the main thread until Python returns, so without this yield the
  // "Running..." status and cleared output flash by invisibly between two
  // adjacent paints. requestAnimationFrame resolves after the next paint.
  await new Promise((resolve) => requestAnimationFrame(resolve));
  const t0 = performance.now();
  try {
    const results = await runAnydice(pyodideRef, source);
    const dt = Math.round(performance.now() - t0);
    renderResults(results);
    setStatus(`Ran in ${dt} ms.`);
  } catch (err) {
    renderError(err);
    setStatus("Run failed.");
  } finally {
    runBtn.disabled = false;
  }
}

// ---- Editor -----------------------------------------------------------------

editor = new EditorView({
  parent: document.getElementById("editor"),
  doc: SAMPLE_PROGRAM,
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

// ---- Runtime wiring ---------------------------------------------------------

// Eager background load: kick off Pyodide initialization as soon as the page
// is interactive, so by the time the user clicks Run the runtime is
// (probably) ready. The Run button stays disabled until init succeeds.
initPyodide(setStatus)
  .then((pyodide) => {
    pyodideRef = pyodide;
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
