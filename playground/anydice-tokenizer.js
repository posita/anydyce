// AnyDice tokenizer -- pure JS, no CodeMirror dependency.
//
// The token() function is the same shape CodeMirror's StreamLanguage expects:
// (stream, state) -> tokenName | null, where the function may advance the
// stream's position by zero or more chars and the state object persists across
// lines so multi-line constructs (the `\ ... \` block comment) work.
//
// Splitting the tokenizer out lets us test it without bringing in CodeMirror
// (which would require a browser or an installed npm dep). The tests in
// test/test-tokenize.mjs use a minimal mock stream.
//
// See ./anydice-mode.js for the CodeMirror-integration wrapper that exports
// the StreamLanguage and the token-name -> highlight-tag mapping.

export const KEYWORDS = new Set([
  "output", "function", "result", "if", "else", "loop", "over",
  "set", "to", "named",
]);

// Token-name vocabulary returned by token(). The CodeMirror integration maps
// each of these to a @lezer/highlight tag via TOKEN_TABLE in anydice-mode.js.
export const TOKEN_NAMES = Object.freeze([
  "comment",
  "string",
  "number",
  "variableName",
  "propertyName",
  "keyword",
  "operatorKeyword",
  "operator",
  "bracket",
  "punctuation",
]);

export function startState() {
  return { inComment: false };
}

// eslint-disable-next-line complexity -- single big dispatch over char classes;
// breaking it up adds indirection without reducing complexity.
export function token(stream, state) {
  // Mid-comment continuation (line started still inside `\...\`).
  if (state.inComment) {
    while (!stream.eol()) {
      if (stream.next() === "\\") {
        state.inComment = false;
        return "comment";
      }
    }
    return "comment";
  }

  if (stream.eatSpace()) return null;

  const ch = stream.peek();

  // Block comment start (`\ ... \`). Try to close on the same line; if we
  // run off the end without finding a closing `\`, persist into next line.
  if (ch === "\\") {
    stream.next();
    while (!stream.eol()) {
      if (stream.next() === "\\") {
        return "comment";
      }
    }
    state.inComment = true;
    return "comment";
  }

  // String literal (no escapes; AnyDice strings can't contain a literal ").
  if (ch === '"') {
    stream.next();
    while (!stream.eol()) {
      if (stream.next() === '"') break;
    }
    return "string";
  }

  // Number literal.
  if (/\d/.test(ch)) {
    stream.eatWhile(/\d/);
    return "number";
  }

  // UPPERNAME (variable name) -- [A-Z_]+.
  if (/[A-Z_]/.test(ch)) {
    stream.eatWhile(/[A-Z_]/);
    return "variableName";
  }

  // LOWERNAME / keyword / 'd'.
  if (/[a-z]/.test(ch)) {
    stream.eatWhile(/[a-z]/);
    const word = stream.current();
    if (KEYWORDS.has(word)) return "keyword";
    if (word === "d") return "operatorKeyword";
    return "propertyName";
  }

  // Range operator `..` (also tolerate `. .` with whitespace per AnyDice's
  // smart tokenizer; we only attempt the contiguous form here -- the
  // whitespace-between variant is rare and the editor will just color them
  // as two separate punctuation marks).
  if (ch === "." && stream.match("..")) {
    return "punctuation";
  }

  // Multi-char comparison operators: <=, >=, !=. Single chars otherwise.
  if (ch === "<" || ch === ">" || ch === "!") {
    stream.next();
    if (stream.peek() === "=") stream.next();
    return "operator";
  }

  // Other operators.
  if (/[+\-*/^@#&|=]/.test(ch)) {
    stream.next();
    return "operator";
  }

  // Brackets.
  if (/[(){}[\]]/.test(ch)) {
    stream.next();
    return "bracket";
  }

  // Statement punctuation: `:` (var-assign / result), `,` (seq separator).
  if (ch === ":" || ch === ",") {
    stream.next();
    return "punctuation";
  }

  // Unknown char: advance one to avoid infinite loop, no class.
  stream.next();
  return null;
}
