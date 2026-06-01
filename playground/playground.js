// AnyDice Playground -- editor wiring.
//
// First iteration: just sets up the CodeMirror 6 editor with the AnyDice
// syntax mode and a sample program. Pyodide integration / Run button /
// URL-fragment encoding will follow.

// CodeMirror 6 imports use bare specifiers; the importmap in index.html maps
// them to esm.sh URLs. See the importmap comment for the version-pinning and
// peer-dep-externalization (`*` prefix) story.
import { EditorView, keymap } from "@codemirror/view";
import { basicSetup } from "codemirror";
import { indentWithTab } from "@codemirror/commands";
import { HighlightStyle, syntaxHighlighting } from "@codemirror/language";
import { tags as t } from "@lezer/highlight";
import { anydice } from "./anydice-mode.js";

// Editor theme: drive every color via CSS variables defined in playground.css,
// so the page's `@media (prefers-color-scheme: dark)` block controls the
// editor's appearance too. No JS-side media-query listening needed.
const anydiceEditorTheme = EditorView.theme({
  "&": {
    backgroundColor: "var(--bg)",
    color:           "var(--text)",
    height:          "100%",
  },
  ".cm-content":         { caretColor: "var(--text)" },
  ".cm-cursor":          { borderLeftColor: "var(--text)" },
  ".cm-gutters": {
    backgroundColor: "var(--bg-elev)",
    color:           "var(--muted)",
    borderRight:     "1px solid var(--border)",
  },
  ".cm-activeLine":       { backgroundColor: "var(--code-bg)" },
  ".cm-activeLineGutter": { backgroundColor: "var(--code-bg)" },
  ".cm-selectionBackground, &.cm-focused > .cm-scroller .cm-selectionBackground, .cm-content ::selection": {
    backgroundColor: "var(--selection-bg) !important",
  },
  ".cm-scroller":        { fontFamily: "var(--font-mono)" },
  ".cm-tooltip": {
    backgroundColor: "var(--bg-elev)",
    color:           "var(--text)",
    border:          "1px solid var(--border)",
  },
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

const SAMPLE_PROGRAM = `\\ Reroll low results up to N times \\
\\
  This program demonstrates an AnyDice quirk: DEPTH is decremented
  across the d6 expansion, so AnyDice's output skews lower than the
  intended "up to N rerolls per call".  anydyce returns the
  mathematically correct distribution.
\\

function: reroll N:n less than THRESHOLD:n depth DEPTH:n {
  if N < THRESHOLD & DEPTH > 0 {
    DEPTH: DEPTH - 1
    result: [reroll 1d6 less than THRESHOLD depth DEPTH]
  }
  result: N
}

output [reroll 1d6 less than 4 depth 3]
  named "reroll under 4, up to 3 tries"
`;

const editor = new EditorView({
  parent: document.getElementById("editor"),
  doc: SAMPLE_PROGRAM,
  extensions: [
    basicSetup,
    keymap.of([indentWithTab]),
    anydice,
    syntaxHighlighting(anydiceHighlightStyle),
    anydiceEditorTheme,
  ],
});

// Expose for ad-hoc poking during development.
window.editor = editor;
