// AnyDice CodeMirror 6 integration. The tokenization logic lives in the pure-JS
// ./anydice-tokenizer.js so it can be tested without CodeMirror; this file just
// wraps that tokenizer in a StreamLanguage and maps token names to highlight
// tags.

import { StreamLanguage } from "@codemirror/language";
import { tags as t } from "@lezer/highlight";
import { startState, token } from "./anydice-tokenizer.js";

// Explicit token-name -> tag mapping.  StreamLanguage's default name-resolution
// silently returns undefined for any name not in its built-in table, and
// CodeMirror's highlight pipeline then crashes downstream when iterating the
// undefined.  Mapping every name we return explicitly avoids the silent gap.
const TOKEN_TABLE = {
  comment:         t.comment,
  string:          t.string,
  number:          t.number,
  variableName:    t.variableName,
  propertyName:    t.propertyName,
  keyword:         t.keyword,
  operatorKeyword: t.operatorKeyword,
  operator:        t.operator,
  bracket:         t.bracket,
  punctuation:     t.punctuation,
};

export const anydice = StreamLanguage.define({
  startState,
  token,
  tokenTable: TOKEN_TABLE,
  languageData: {
    commentTokens: { block: { open: "\\", close: "\\" } },
    indentOnInput: /^\s*[\]}]$/,
  },
});
