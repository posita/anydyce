// Tests for the URL-fragment encoding helpers (../url-fragment.js).
//
// Run with: node --test playground/test/test-url-fragment.mjs

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  b64urlDecode,
  b64urlEncode,
  parseUrlHashForProgram,
} from "../url-fragment.js";

// ---- Round-trip tests -----------------------------------------------------

test("round-trips simple ASCII", () => {
  const src = "output 3d6";
  assert.equal(b64urlDecode(b64urlEncode(src)), src);
});

test("round-trips empty string", () => {
  assert.equal(b64urlDecode(b64urlEncode("")), "");
});

test("round-trips AnyDice with comments and operators", () => {
  const src = '\\ block comment \\\noutput 1d6 named "my roll"';
  assert.equal(b64urlDecode(b64urlEncode(src)), src);
});

test("round-trips multi-line function definition", () => {
  const src =
    "function: f X:n Y:d {\n" +
    "  result: X * Y\n" +
    "}\n" +
    "output [f 2 d6]";
  assert.equal(b64urlDecode(b64urlEncode(src)), src);
});

test("round-trips UTF-8 non-ASCII characters", () => {
  const src = 'set "naïve mæthod" to 1\noutput "résult" 2d6';
  assert.equal(b64urlDecode(b64urlEncode(src)), src);
});

test("round-trips a long program", () => {
  // ~2KB string; well within URL-fragment practical limits.
  const src = "output 3d6\n".repeat(200);
  assert.equal(b64urlDecode(b64urlEncode(src)), src);
});

test("round-trips characters that would expand under percent-encoding", () => {
  const src = "spaces & ?queries# & =equals + plus / slash";
  assert.equal(b64urlDecode(b64urlEncode(src)), src);
});

// ---- URL-safety property tests --------------------------------------------

test("encoded output contains no '+' character", () => {
  // Construct input likely to produce '+' in standard base64 (which becomes
  // '-' in base64url). Bytes 0xFB, 0xFE, 0xFF tend to produce '+' / '/'.
  const src = String.fromCharCode(0xfb, 0xfe, 0xff, 0xfb, 0xfe, 0xff);
  const encoded = b64urlEncode(src);
  assert.ok(!encoded.includes("+"), `'+' found in: ${encoded}`);
});

test("encoded output contains no '/' character", () => {
  const src = String.fromCharCode(0xff, 0xfe, 0xfd, 0xff, 0xfe, 0xfd);
  const encoded = b64urlEncode(src);
  assert.ok(!encoded.includes("/"), `'/' found in: ${encoded}`);
});

test("encoded output contains no '=' padding", () => {
  // Bytes whose count is NOT a multiple of 3 normally produce '=' padding.
  for (const len of [1, 2, 4, 5, 7]) {
    const src = "x".repeat(len);
    const encoded = b64urlEncode(src);
    assert.ok(!encoded.includes("="), `'=' found in: ${encoded} (len=${len})`);
  }
});

test("encoded output uses only the URL-safe alphabet", () => {
  const src = "AnyDice playground! Test: output [some d6 d8 d12 d20].\n";
  const encoded = b64urlEncode(src);
  assert.match(encoded, /^[A-Za-z0-9_-]*$/);
});

// ---- Hash-parser tests ----------------------------------------------------

test("parses #p=<base64> and decodes to original", () => {
  const src = "output 5d6";
  const hash = `#p=${b64urlEncode(src)}`;
  assert.equal(parseUrlHashForProgram(hash), src);
});

test("parses without leading '#'", () => {
  const src = "output 1d20";
  const hash = `p=${b64urlEncode(src)}`;
  assert.equal(parseUrlHashForProgram(hash), src);
});

test("returns null on empty hash", () => {
  assert.equal(parseUrlHashForProgram(""), null);
  assert.equal(parseUrlHashForProgram("#"), null);
});

test("returns null when 'p' key is absent", () => {
  assert.equal(parseUrlHashForProgram("#id=183b0"), null);
  assert.equal(parseUrlHashForProgram("#foo=bar&baz=qux"), null);
});

test("returns null on undefined or null input (defensive)", () => {
  assert.equal(parseUrlHashForProgram(null), null);
  assert.equal(parseUrlHashForProgram(undefined), null);
});

test("returns empty string when 'p' is present but empty", () => {
  // A `#p=` with no value should decode to empty string (not null);
  // an empty fragment value is technically valid and round-trips.
  assert.equal(parseUrlHashForProgram("#p="), null);
  // ^ URLSearchParams.get('p') returns '' for `p=`; b64urlDecode('') is '';
  // but our parser returns null for falsy `p` to distinguish "no program"
  // from "empty program". If you want to allow loading an empty program,
  // change `if (!p) return null;` to `if (p === null) return null;`.
});

test("picks 'p' even when other parameters are present", () => {
  const src = "output 7d6";
  const enc = b64urlEncode(src);
  const hash = `#id=183b0&p=${enc}&foo=bar`;
  assert.equal(parseUrlHashForProgram(hash), src);
});

test("returns null on malformed base64", () => {
  // Non-base64 characters in the value. b64urlDecode throws; the parser
  // catches and returns null so the caller can fall back to a default.
  assert.equal(parseUrlHashForProgram("#p=!!not-base64!!"), null);
});

test("parses a real-world program round-trip via hash", () => {
  const src =
    "function: f X:n { result: X * X }\noutput [f 3d6]";
  const hash = `#p=${b64urlEncode(src)}`;
  assert.equal(parseUrlHashForProgram(hash), src);
});
