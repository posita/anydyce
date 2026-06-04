// Tests for the corpus-mirror URL formation (../corpus-mirror.js).
//
// Run with: node --test playground/test/test-corpus-mirror.mjs
//
// The Python source these mirror lives in `anydyce/anydice/fetch.py`. Test
// cases derive from the Python module's docstring examples so the JS port
// stays in sync with the reference implementation.

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  ghMirrorUrlForProgramId,
  programIdAsHex,
  programIdAsInt,
  shardedSubpathFromProgramId,
} from "../corpus-mirror.js";

// ---- programIdAsInt -------------------------------------------------------

test("programIdAsInt: integer input passes through", () => {
  assert.equal(programIdAsInt(22), 22);
  assert.equal(programIdAsInt(0), 0);
  assert.equal(programIdAsInt(-255), -255);
});

test("programIdAsInt: hex string parses to integer", () => {
  assert.equal(programIdAsInt("0"), 0);
  assert.equal(programIdAsInt("16"), 22); // 0x16 = 22 (decimal)
  assert.equal(programIdAsInt("ff"), 255);
  assert.equal(programIdAsInt("fF"), 255); // case-insensitive
  assert.equal(programIdAsInt("FF"), 255);
});

test("programIdAsInt: negative hex string parses to negative integer", () => {
  assert.equal(programIdAsInt("-abc"), -2748);
  assert.equal(programIdAsInt("-1"), -1);
});

test("programIdAsInt: large positive hex parses correctly", () => {
  assert.equal(programIdAsInt("fedcba98"), 0xfedcba98);
  assert.equal(programIdAsInt("1a2b3c"), 0x1a2b3c);
});

test("programIdAsInt: hex with leading zeros parses correctly", () => {
  assert.equal(programIdAsInt("000fedcba98"), 0xfedcba98);
  assert.equal(programIdAsInt("-000fedcba98"), -0xfedcba98);
  assert.equal(programIdAsInt("0001a2b3c"), 0x1a2b3c);
  assert.equal(programIdAsInt("-0001a2b3c"), -0x1a2b3c);
});

test("programIdAsInt: throws on invalid input", () => {
  assert.throws(() => programIdAsInt("Ka-BLAM!"));
  assert.throws(() => programIdAsInt("gg"));
  assert.throws(() => programIdAsInt(""));
  assert.throws(() => programIdAsInt(1.5)); // non-integer number
  assert.throws(() => programIdAsInt(null));
  assert.throws(() => programIdAsInt(undefined));
});

// ---- programIdAsHex -------------------------------------------------------

test("programIdAsHex: integer to lowercase hex", () => {
  assert.equal(programIdAsHex(22), "16");
  assert.equal(programIdAsHex(0), "0");
  assert.equal(programIdAsHex(-255), "-ff");
});

test("programIdAsHex: hex string normalizes (preserves negative)", () => {
  assert.equal(programIdAsHex("-abc"), "-abc");
  assert.equal(programIdAsHex("FFF"), "fff"); // case-normalized
  assert.equal(programIdAsHex("FfF"), "fff");
  assert.equal(programIdAsHex("0"), "0");
});

test("programIdAsHex: large hex string round-trip", () => {
  assert.equal(programIdAsHex("fedcba98"), "fedcba98");
  assert.equal(programIdAsHex("1a2b3c"), "1a2b3c");
});

test("programIdAsHex: strips leading zeros", () => {
  assert.equal(programIdAsHex("01a2"), "1a2");
  assert.equal(programIdAsHex("-01a2"), "-1a2");
  assert.equal(programIdAsHex("001a2"), "1a2");
  assert.equal(programIdAsHex("-001a2"), "-1a2");
  assert.equal(programIdAsHex("0001a2"), "1a2");
  assert.equal(programIdAsHex("-0001a2"), "-1a2");
  assert.equal(programIdAsHex("000abcd"), "abcd");
  assert.equal(programIdAsHex("-000abcd"), "-abcd");
  assert.equal(programIdAsHex("000fedcba98"), "fedcba98");
  assert.equal(programIdAsHex("-000fedcba98"), "-fedcba98");
});

test("programIdAsHex: throws on invalid input", () => {
  assert.throws(() => programIdAsHex("Ka-BLAM!"));
});

// ---- shardedSubpathFromProgramId ------------------------------------------
// Verify the sharded subpath matches the Python docstring examples exactly.

test("shardedSubpathFromProgramId: docstring examples", () => {
  // From `anydyce.anydice.fetch.sharded_subpath_from_program_id` docstring.
  assert.equal(shardedSubpathFromProgramId("f"), "00/0f/f.txt");
  assert.equal(shardedSubpathFromProgramId("1a2b3c"), "2b/3c/1a2b3c.txt");
  assert.equal(shardedSubpathFromProgramId("-abc"), "0a/bc/-abc.txt");
});

test("shardedSubpathFromProgramId: zero ID", () => {
  assert.equal(shardedSubpathFromProgramId("0"), "00/00/0.txt");
});

test("shardedSubpathFromProgramId: single-character IDs", () => {
  assert.equal(shardedSubpathFromProgramId("a"), "00/0a/a.txt");
  assert.equal(shardedSubpathFromProgramId("1"), "00/01/1.txt");
});

test("shardedSubpathFromProgramId: 4-char ID (no padding needed beyond width)", () => {
  // 0xabcd -- already 4 chars, but padded to 5: "0abcd" internally.
  // Slice [-4:-2] = "ab", [-2:] = "cd". Filename uses unpadded
  // "abcd".
  assert.equal(shardedSubpathFromProgramId("abcd"), "ab/cd/abcd.txt");
});

test("shardedSubpathFromProgramId: strips leading zeros", () => {
  assert.equal(shardedSubpathFromProgramId("0abc"), "0a/bc/abc.txt");
  assert.equal(shardedSubpathFromProgramId("-0abc"), "0a/bc/-abc.txt");
  assert.equal(shardedSubpathFromProgramId("00abc"), "0a/bc/abc.txt");
  assert.equal(shardedSubpathFromProgramId("-00abc"), "0a/bc/-abc.txt");
  assert.equal(shardedSubpathFromProgramId("000abc"), "0a/bc/abc.txt");
  assert.equal(shardedSubpathFromProgramId("-000abc"), "0a/bc/-abc.txt");
  assert.equal(shardedSubpathFromProgramId("0abcd"), "ab/cd/abcd.txt");
  assert.equal(shardedSubpathFromProgramId("-0abcd"), "ab/cd/-abcd.txt");
  assert.equal(shardedSubpathFromProgramId("000abcd"), "ab/cd/abcd.txt");
  assert.equal(shardedSubpathFromProgramId("-000abcd"), "ab/cd/-abcd.txt");
  assert.equal(shardedSubpathFromProgramId("000abcde"), "bc/de/abcde.txt");
  assert.equal(shardedSubpathFromProgramId("-000abcde"), "bc/de/-abcde.txt");
});

test("shardedSubpathFromProgramId: very large IDs (no padding)", () => {
  // 0x12345678 -- already 8 chars wide, no padding applied. Slice [-4:-2] =
  // "56", [-2:] = "78".
  assert.equal(shardedSubpathFromProgramId("12345678"), "56/78/12345678.txt");
});

test("shardedSubpathFromProgramId: integer input behaves the same as hex string", () => {
  // 0x1a2b3c == 1715004 decimal. Either form should yield the same sharded path.
  assert.equal(
    shardedSubpathFromProgramId(0x1a2b3c),
    shardedSubpathFromProgramId("1a2b3c"),
  );
});

test("shardedSubpathFromProgramId: negative integer input matches negative hex string", () => {
  // -0xabc == -2748 decimal. Either form should yield "0a/bc/-abc.txt".
  assert.equal(shardedSubpathFromProgramId(-0xabc), "0a/bc/-abc.txt");
});

test("shardedSubpathFromProgramId: case-insensitive input, lowercase output", () => {
  // The filename should always be lowercase regardless of input case.
  assert.equal(shardedSubpathFromProgramId("ABCD"), "ab/cd/abcd.txt");
  assert.equal(shardedSubpathFromProgramId("FF"), "00/ff/ff.txt");
});

// ---- ghMirrorUrlForProgramId ----------------------------------------------

test("ghMirrorUrlForProgramId: docstring examples", () => {
  // From `anydyce.anydice.fetch.gh_mirror_url_for_program_id_hex` docstring.
  assert.equal(
    ghMirrorUrlForProgramId("123"),
    "https://raw.githubusercontent.com/posita/anydice-data/" +
      "refs/heads/main/anydice.com/program/01/23/123.txt",
  );
  assert.equal(
    ghMirrorUrlForProgramId("fedcba98"),
    "https://raw.githubusercontent.com/posita/anydice-data/" +
      "refs/heads/main/anydice.com/program/ba/98/fedcba98.txt",
  );
});

test("ghMirrorUrlForProgramId: faked corpus entry (negative ID)", () => {
  // Faked corpus entries (e.g. -0x12, -0x47, -0x48) live in the mirror
  // under the same sharding scheme as real entries.
  assert.equal(
    ghMirrorUrlForProgramId("-12"),
    "https://raw.githubusercontent.com/posita/anydice-data/" +
      "refs/heads/main/anydice.com/program/00/12/-12.txt",
  );
});

test("ghMirrorUrlForProgramId: well-known corpus IDs from our session", () => {
  // 0x183b0 -- the doubling-amplification class A program.
  assert.equal(
    ghMirrorUrlForProgramId("183b0"),
    "https://raw.githubusercontent.com/posita/anydice-data/" +
      "refs/heads/main/anydice.com/program/83/b0/183b0.txt",
  );
  // 0x1102 -- the pentastar-dice-with-penalty-dice param-leakage canonical.
  assert.equal(
    ghMirrorUrlForProgramId("1102"),
    "https://raw.githubusercontent.com/posita/anydice-data/" +
      "refs/heads/main/anydice.com/program/11/02/1102.txt",
  );
  // 0x22432 -- the "highest of 10 million d6" program.
  assert.equal(
    ghMirrorUrlForProgramId("22432"),
    "https://raw.githubusercontent.com/posita/anydice-data/" +
      "refs/heads/main/anydice.com/program/24/32/22432.txt",
  );
});

test("ghMirrorUrlForProgramId: throws on invalid input", () => {
  assert.throws(() => ghMirrorUrlForProgramId("not-hex!"));
});
