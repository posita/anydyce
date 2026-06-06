// URL-fragment encoding for the playground.
//
// Pure-JS module (no CodeMirror, no DOM access) so the helpers can be tested
// under Node directly. The playground main file (playground.js) imports these
// and wraps them with the DOM-dependent bits: reading `location.hash`,
// writing to the clipboard, etc.
//
// Format: `#p=<base64url>` encodes the program text into the URL fragment.
// Fragments are never sent to the server (browser strips them before HTTP
// request), so they're privacy-friendly for sharing arbitrary program text.

// Encode a string to URL-safe base64 (base64url, RFC 4648 §5). Handles
// Unicode via TextEncoder so non-ASCII characters (e.g. in AnyDice string
// literals) round-trip correctly. btoa() alone only accepts Latin-1.
export function b64urlEncode(text) {
  const utf8 = new TextEncoder().encode(text);
  let bin = "";
  for (const byte of utf8) bin += String.fromCharCode(byte);
  return btoa(bin)
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

// Decode a base64url string back to its original text. Throws if the input
// isn't valid base64url (the caller should catch and decide how to fall
// back).
export function b64urlDecode(b64url) {
  const b64 = b64url.replace(/-/g, "+").replace(/_/g, "/");
  // atob() requires the input to be padded to a multiple of 4.
  const padded = b64 + "=".repeat((4 - (b64.length % 4)) % 4);
  const bin = atob(padded);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new TextDecoder().decode(bytes);
}

// Parse a URL hash string (e.g. "#p=abc" or "p=abc&id=xyz") and return the
// decoded program text from the `p` parameter, or null if not present /
// malformed. Accepts hash with or without leading "#".
export function parseUrlHashForProgram(hashStr) {
  if (!hashStr) return null;
  const stripped = hashStr.replace(/^#/, "");
  if (!stripped) return null;
  const params = new URLSearchParams(stripped);
  const p = params.get("p");
  if (!p) return null;
  try {
    return b64urlDecode(p);
  } catch {
    return null;
  }
}

// Parse a URL hash string and return the value of the `id` parameter (a hex
// program ID), or null if not present. Returns the raw string -- normalization
// (case, leading-zero stripping, validation) is the caller's responsibility
// via corpus-mirror's helpers. Accepts hash with or without leading "#".
export function parseUrlHashForProgramId(hashStr) {
  if (!hashStr) return null;
  const stripped = hashStr.replace(/^#/, "");
  if (!stripped) return null;
  const params = new URLSearchParams(stripped);
  const id = params.get("id");
  return id || null;
}
