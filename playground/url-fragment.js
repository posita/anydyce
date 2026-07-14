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

// Parse a URL hash (e.g. "#p=abc" or "p=abc&id=xyz", with or without the
// leading "#") into URLSearchParams, or null if empty.
function hashParams(hashStr) {
  if (!hashStr) return null;
  const stripped = hashStr.replace(/^#/, "");
  return stripped ? new URLSearchParams(stripped) : null;
}

// Decoded program text from the hash's `p` parameter, or null if absent /
// malformed.
export function parseUrlHashForProgram(hashStr) {
  const p = hashParams(hashStr)?.get("p");
  if (!p) return null;
  try {
    return b64urlDecode(p);
  } catch {
    return null;
  }
}

// The hash's `id` parameter (a hex program ID), or null if absent. Raw string
// -- normalization (case, leading-zero stripping, validation) is the caller's
// job via corpus-mirror's helpers.
export function parseUrlHashForProgramId(hashStr) {
  return hashParams(hashStr)?.get("id") || null;
}
