// Corpus-mirror URL formation.
//
// Pure-JS port of `anydyce.anydice.fetch.gh_mirror_url_for_program_id_hex` (and
// its supporting helpers). Computes the raw-content GitHub URL where a given
// program ID's source text lives in the `posita/anydice-data` mirror repo.
//
// Why JS (vs calling the Python helper via Pyodide): we want `#id=...` URL
// fragments to start fetching corpus programs in PARALLEL with Pyodide's
// runtime startup. URL formation is instant; the fetch is async but doesn't
// block on the runtime. Routing through Python would gate the fetch on
// Pyodide being ready, defeating the parallelism.
//
// Algorithm (see Python docstrings in `anydyce/anydice/fetch.py`):
//   1. Parse the input as a signed hex integer.
//   2. Format it as 5-wide zero-padded hex; the minus sign (if any) counts
//      toward the width.
//   3. Slice [-4:-2] and [-2:] of the padded string for the two 2-char
//      subdirectory names.
//   4. The filename is the unpadded hex form (still possibly negative) + ".txt".
//   5. Prepend the base URL.

const _GH_MIRROR_URL_BASE =
  "https://raw.githubusercontent.com/posita/anydice-data/" +
  "refs/heads/main/anydice.com/program/";

const _HEX_RE = /^-?[0-9A-Fa-f]+$/;

// Parse a program ID (string or number) to a signed integer. Strings are
// interpreted as base-16 with optional leading "-" sign. Throws if the input
// can't be parsed.
export function programIdAsInt(programId) {
  if (typeof programId === "number") {
    if (!Number.isInteger(programId)) {
      throw new Error(`unable to parse program ID (${programId})`);
    }
    return programId;
  }
  if (typeof programId !== "string") {
    throw new Error(`unable to parse program ID (${programId})`);
  }
  const s = programId.trim();
  if (!_HEX_RE.test(s)) {
    throw new Error(`unable to parse program ID (${programId})`);
  }
  // parseInt("-abc", 16) === -2748; supported directly.
  const n = parseInt(s, 16);
  if (!Number.isFinite(n)) {
    throw new Error(`unable to parse program ID (${programId})`);
  }
  return n;
}

// Return the lowercase hex form of a program ID, preserving any leading
// minus sign.
export function programIdAsHex(programId) {
  const n = programIdAsInt(programId);
  return n.toString(16);
}

// Return the sharded subpath ("XX/YY/<id>.txt") for a program ID. The two
// 2-char subdirectories come from positions [-4:-2] and [-2:] of the
// 5-wide zero-padded hex (where any minus sign counts toward the width,
// matching Python's `f"{n:05x}"` behavior).
export function shardedSubpathFromProgramId(programId) {
  const n = programIdAsInt(programId);
  // Replicate Python's f"{n:05x}". Python pads the entire signed value to
  // 5 chars including any minus sign. JS's toString(16) on a negative
  // number includes the "-" prefix; we manually pad the absolute-value
  // body to (5 - sign_width).
  const sign = n < 0 ? "-" : "";
  const absBody = Math.abs(n).toString(16);
  const minBodyLen = 5 - sign.length;
  const paddedBody =
    absBody.length >= minBodyLen ? absBody : absBody.padStart(minBodyLen, "0");
  const padded = sign + paddedBody;
  const sub1 = padded.slice(-4, -2);
  const sub2 = padded.slice(-2);
  const filename = `${programIdAsHex(programId)}.txt`;
  return `${sub1}/${sub2}/${filename}`;
}

// Return the absolute raw-GitHub URL for a program's mirrored source file.
// This is pure URL formation; the file may or may not actually exist (e.g.
// the missing programs documented in `anydice-data/MISSING.md`).
export function ghMirrorUrlForProgramId(programId) {
  return _GH_MIRROR_URL_BASE + shardedSubpathFromProgramId(programId);
}

const _ANYDICE_PROGRAM_URL_BASE = "https://anydice.com/program/";

// Build an AnyDice block-comment provenance header for a corpus program
// loaded via `#id=...`. Mirrors the header `%anyd_load` prepends in
// anydyce/magic.py so provenance reads the same across surfaces. The
// header ends with a newline; callers prepend it directly to the fetched
// program text.
//
// `fetchedAt` is a preformatted timestamp string and `via` the full
// playground URL that triggered the load (the caller owns clock and
// location access so this stays pure and unit-testable). `via` falls back
// to the bare `#id=` fragment when not provided.
//
// Positive IDs cite the canonical anydice.com URL (user-meaningful, and
// where the program actually originated). Negative IDs are locally-minted
// fakes for programs that never existed on anydice.com -- citing
// anydice.com would fabricate provenance, so those cite the mirror file
// that actually served the fetch.
export function provenanceHeader(programId, fetchedAt, via = null) {
  const hexId = programIdAsHex(programId);
  const sourceUrl = hexId.startsWith("-")
    ? ghMirrorUrlForProgramId(hexId)
    : _ANYDICE_PROGRAM_URL_BASE + hexId;
  return (
    "\\ ================================================================================ /\n" +
    `  AnyDice program ${hexId} fetched from ${sourceUrl}\n` +
    `  at ${fetchedAt} using:\n` +
    `  ${via ?? `#id=${hexId}`}\n` +
    "/ ================================================================================ \\\n"
  );
}
