// Tests for the AnyDice tokenizer (../anydice-tokenizer.js).
//
// Run with: node --test playground/test/test-tokenize.mjs
//
// The tokenizer's `token(stream, state)` shape is what CodeMirror's
// StreamLanguage expects.  We test it directly via a minimal mock stream that
// implements just the methods the tokenizer uses.  No CodeMirror runtime
// required.

import { test } from "node:test";
import assert from "node:assert/strict";

import { startState, token } from "../anydice-tokenizer.js";

// ---- Mock stream ----------------------------------------------------------

class MockStream {
  constructor(line) {
    this.line = line;
    this.pos = 0;
    this.start = 0;
  }

  peek() {
    return this.pos < this.line.length ? this.line[this.pos] : undefined;
  }

  next() {
    if (this.pos >= this.line.length) return undefined;
    return this.line[this.pos++];
  }

  eatSpace() {
    const start = this.pos;
    while (this.pos < this.line.length && /\s/.test(this.line[this.pos])) {
      this.pos++;
    }
    return this.pos > start;
  }

  eatWhile(pattern) {
    let ate = false;
    while (this.pos < this.line.length) {
      const ch = this.line[this.pos];
      if (pattern instanceof RegExp) {
        if (!pattern.test(ch)) break;
      } else if (typeof pattern === "string") {
        if (ch !== pattern) break;
      } else if (typeof pattern === "function") {
        if (!pattern(ch)) break;
      }
      this.pos++;
      ate = true;
    }
    return ate;
  }

  eol() {
    return this.pos >= this.line.length;
  }

  current() {
    return this.line.substring(this.start, this.pos);
  }

  match(str) {
    if (this.line.substring(this.pos, this.pos + str.length) === str) {
      this.pos += str.length;
      return true;
    }
    return false;
  }
}

// Tokenize one line; returns array of [tokenName, text] pairs.  Whitespace
// (returned as `null` from the tokenizer) is filtered out for assertion
// readability -- tests asserting on null whitespace tokens would be noisy and
// uninteresting.
function tokenize(line, state = startState()) {
  const stream = new MockStream(line);
  const tokens = [];
  while (!stream.eol()) {
    stream.start = stream.pos;
    const name = token(stream, state);
    const text = stream.current();
    if (text.length === 0) {
      throw new Error(
        `Tokenizer did not advance at position ${stream.pos} of "${line}"`,
      );
    }
    if (name !== null) tokens.push([name, text]);
  }
  return tokens;
}

// Tokenize a multi-line program by running each line through the tokenizer
// with shared state, so multi-line comments span correctly.
function tokenizeProgram(source) {
  const state = startState();
  const result = [];
  for (const line of source.split("\n")) {
    result.push(tokenize(line, state));
  }
  return result;
}

// ---- Tests: basic token kinds ---------------------------------------------

test("number literal", () => {
  assert.deepEqual(tokenize("42"), [["number", "42"]]);
});

test("UPPERNAME variable", () => {
  assert.deepEqual(tokenize("FOO"), [["variableName", "FOO"]]);
});

test("UPPERNAME with underscores", () => {
  assert.deepEqual(tokenize("FOO_BAR"), [["variableName", "FOO_BAR"]]);
});

test("UPPERNAME with leading underscore", () => {
  assert.deepEqual(tokenize("_FOO"), [["variableName", "_FOO"]]);
});

test("LOWERNAME function-pattern word", () => {
  assert.deepEqual(tokenize("lowest"), [["propertyName", "lowest"]]);
});

test("bare 'd' is the dice operator, not a propertyName", () => {
  assert.deepEqual(tokenize("d"), [["operatorKeyword", "d"]]);
});

test("longer word starting with 'd' is a propertyName", () => {
  assert.deepEqual(tokenize("dee"), [["propertyName", "dee"]]);
  assert.deepEqual(tokenize("double"), [["propertyName", "double"]]);
});

test("each KEYWORD recognized", () => {
  for (const kw of [
    "output", "function", "result", "if", "else",
    "loop", "over", "set", "to", "named",
  ]) {
    assert.deepEqual(
      tokenize(kw), [["keyword", kw]],
      `expected ${kw} to tokenize as keyword`,
    );
  }
});

test("string literal", () => {
  assert.deepEqual(tokenize('"hello"'), [["string", '"hello"']]);
});

test("string with spaces", () => {
  assert.deepEqual(
    tokenize('"hello world"'),
    [["string", '"hello world"']],
  );
});

// ---- Tests: comments ------------------------------------------------------

test("single-line comment", () => {
  assert.deepEqual(
    tokenize("\\ this is a comment \\"),
    [["comment", "\\ this is a comment \\"]],
  );
});

test("multi-line comment spans lines via state", () => {
  // Line 1 opens the comment but doesn't close it.
  const state = startState();
  const line1 = tokenize("\\ start of comment", state);
  assert.deepEqual(line1, [["comment", "\\ start of comment"]]);
  assert.equal(state.inComment, true);

  // Line 2 closes the comment.
  const line2 = tokenize("still in comment \\", state);
  assert.deepEqual(line2, [["comment", "still in comment \\"]]);
  assert.equal(state.inComment, false);
});

test("comment-then-code on same line", () => {
  assert.deepEqual(
    tokenize("\\ skip \\ output 3"),
    [
      ["comment", "\\ skip \\"],
      ["keyword", "output"],
      ["number", "3"],
    ],
  );
});

// ---- Tests: operators -----------------------------------------------------

test("single-char operators", () => {
  assert.deepEqual(
    tokenize("+ - * / ^ @ # & |"),
    [
      ["operator", "+"], ["operator", "-"], ["operator", "*"],
      ["operator", "/"], ["operator", "^"], ["operator", "@"],
      ["operator", "#"], ["operator", "&"], ["operator", "|"],
    ],
  );
});

test("equality operator", () => {
  assert.deepEqual(tokenize("1 = 2"), [
    ["number", "1"], ["operator", "="], ["number", "2"],
  ]);
});

test("comparison operators (multi-char)", () => {
  assert.deepEqual(tokenize("a <= b"), [
    ["propertyName", "a"], ["operator", "<="], ["propertyName", "b"],
  ]);
  assert.deepEqual(tokenize("a >= b"), [
    ["propertyName", "a"], ["operator", ">="], ["propertyName", "b"],
  ]);
  assert.deepEqual(tokenize("a != b"), [
    ["propertyName", "a"], ["operator", "!="], ["propertyName", "b"],
  ]);
});

test("less-than and greater-than as single chars", () => {
  assert.deepEqual(tokenize("a < b"), [
    ["propertyName", "a"], ["operator", "<"], ["propertyName", "b"],
  ]);
  assert.deepEqual(tokenize("a > b"), [
    ["propertyName", "a"], ["operator", ">"], ["propertyName", "b"],
  ]);
});

test("bang (negation) as single char", () => {
  assert.deepEqual(tokenize("!1"), [
    ["operator", "!"], ["number", "1"],
  ]);
});

test("range operator `..`", () => {
  assert.deepEqual(tokenize("{1..3}"), [
    ["bracket", "{"],
    ["number", "1"],
    ["punctuation", ".."],
    ["number", "3"],
    ["bracket", "}"],
  ]);
});

// ---- Tests: brackets and punctuation --------------------------------------

test("brackets", () => {
  assert.deepEqual(
    tokenize("( ) { } [ ]"),
    [
      ["bracket", "("], ["bracket", ")"],
      ["bracket", "{"], ["bracket", "}"],
      ["bracket", "["], ["bracket", "]"],
    ],
  );
});

test("colon (var-assign)", () => {
  assert.deepEqual(tokenize("X: 5"), [
    ["variableName", "X"],
    ["punctuation", ":"],
    ["number", "5"],
  ]);
});

test("comma (seq separator)", () => {
  assert.deepEqual(tokenize("{1, 2, 3}"), [
    ["bracket", "{"],
    ["number", "1"], ["punctuation", ","],
    ["number", "2"], ["punctuation", ","],
    ["number", "3"],
    ["bracket", "}"],
  ]);
});

// ---- Tests: real-world program shapes -------------------------------------

test("simple dice expression: output 3d6", () => {
  assert.deepEqual(tokenize("output 3d6"), [
    ["keyword", "output"],
    ["number", "3"],
    ["operatorKeyword", "d"],
    ["number", "6"],
  ]);
});

test("named output: output 1d6 named \"my roll\"", () => {
  assert.deepEqual(tokenize('output 1d6 named "my roll"'), [
    ["keyword", "output"],
    ["number", "1"], ["operatorKeyword", "d"], ["number", "6"],
    ["keyword", "named"],
    ["string", '"my roll"'],
  ]);
});

test("function definition with typed params", () => {
  // A representative function header.  Note: ':n' and ':d' tokenize as
  // `punctuation` (`:`) + `propertyName` (`n` or `d`-as-LOWERNAME)... except
  // bare `d` is operatorKeyword.  This is faithful to how the grammar
  // disambiguates: the lexer sees the colon-then-letter, the parser
  // reassembles the param-type from those tokens.  Test the actual emitted
  // stream so we catch any change.
  const result = tokenize("function: pick N:n of D:d {");
  assert.deepEqual(result, [
    ["keyword", "function"],
    ["punctuation", ":"],
    ["propertyName", "pick"],
    ["variableName", "N"],
    ["punctuation", ":"],
    ["propertyName", "n"],
    ["propertyName", "of"],
    ["variableName", "D"],
    ["punctuation", ":"],
    ["operatorKeyword", "d"],
    ["bracket", "{"],
  ]);
});

test("function call brackets", () => {
  assert.deepEqual(tokenize("[reroll 1d6]"), [
    ["bracket", "["],
    ["propertyName", "reroll"],
    ["number", "1"],
    ["operatorKeyword", "d"],
    ["number", "6"],
    ["bracket", "]"],
  ]);
});

test("if statement", () => {
  assert.deepEqual(tokenize("if X < 4 {"), [
    ["keyword", "if"],
    ["variableName", "X"],
    ["operator", "<"],
    ["number", "4"],
    ["bracket", "{"],
  ]);
});

test("set statement (set ... to ...)", () => {
  assert.deepEqual(
    tokenize('set "maximum function depth" to 20'),
    [
      ["keyword", "set"],
      ["string", '"maximum function depth"'],
      ["keyword", "to"],
      ["number", "20"],
    ],
  );
});

// ---- Tests: full sample program (multi-line) ------------------------------

test("full sample program -- reroll-with-depth", () => {
  const source = [
    "\\ reroll low results \\",
    "function: reroll N:n less than T:n depth D:n {",
    "  if N < T & D > 0 {",
    "    D: D - 1",
    "    result: [reroll 1d6 less than T depth D]",
    "  }",
    "  result: N",
    "}",
    "output [reroll 1d6 less than 4 depth 3]",
  ].join("\n");

  const lines = tokenizeProgram(source);

  // Spot-check key lines rather than asserting on the entire stream
  // (which would be brittle to formatting tweaks).
  assert.deepEqual(lines[0], [["comment", "\\ reroll low results \\"]]);

  // Line 1: function definition
  const fnLine = lines[1];
  assert.equal(fnLine[0][0], "keyword");
  assert.equal(fnLine[0][1], "function");
  // Confirm the 'd' in "depth" tokenizes as propertyName, NOT operatorKeyword.
  const depthTok = fnLine.find(([, text]) => text === "depth");
  assert.deepEqual(depthTok, ["propertyName", "depth"]);

  // Multiple distinct propertyName words on the function header
  const propNames = fnLine.filter(([name]) => name === "propertyName")
    .map(([, text]) => text);
  assert.deepEqual(propNames, ["reroll", "n", "less", "than", "n", "depth", "n"]);
});

// ---- Tests: regressions / edge cases --------------------------------------

test("empty input -> no tokens", () => {
  assert.deepEqual(tokenize(""), []);
});

test("whitespace only -> no tokens (whitespace is filtered)", () => {
  assert.deepEqual(tokenize("   \t  "), []);
});

test("contiguous range vs separated dots", () => {
  // Contiguous: tokenizes as the range punctuation.
  assert.deepEqual(tokenize("1..3"), [
    ["number", "1"],
    ["punctuation", ".."],
    ["number", "3"],
  ]);
  // Single dot is unknown / advances without emitting (per the tokenizer's
  // fallback).  Sanity that we don't infinite-loop on bare `.`.
  const result = tokenize("1.3");
  // Don't assert on exact dot-handling (it's undefined behavior); just that
  // we tokenized without crashing.
  assert.ok(result.length >= 2);
});

test("number followed by lowercase letter -- no ambiguity", () => {
  // `3d6` tokenizes as number + operatorKeyword + number, not as one mash.
  assert.deepEqual(tokenize("3d6"), [
    ["number", "3"],
    ["operatorKeyword", "d"],
    ["number", "6"],
  ]);
});
