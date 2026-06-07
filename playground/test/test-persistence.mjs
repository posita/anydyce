// Tests for the editor-persistence helpers (../persistence.js).
//
// Run with: node --test playground/test/test-persistence.mjs

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  LOGS_SPLIT_KEY,
  STORAGE_KEY,
  createDebouncedSaver,
  loadLogsSplit,
  loadSavedDoc,
  saveDoc,
  saveLogsSplit,
  stripUrlFragment,
} from "../persistence.js";

// ---- Minimal localStorage stub --------------------------------------------

function makeStorage() {
  const map = new Map();
  return {
    getItem(k) {
      return map.has(k) ? map.get(k) : null;
    },
    setItem(k, v) {
      map.set(k, String(v));
    },
    removeItem(k) {
      map.delete(k);
    },
    clear() {
      map.clear();
    },
    get size() {
      return map.size;
    },
  };
}

function makeThrowingStorage() {
  return {
    getItem() {
      throw new Error("private browsing");
    },
    setItem() {
      throw new Error("private browsing");
    },
  };
}

// ---- loadSavedDoc / saveDoc ----------------------------------------------

test("saveDoc + loadSavedDoc round-trip", () => {
  const storage = makeStorage();
  saveDoc("output 3d6", storage);
  assert.equal(loadSavedDoc(storage), "output 3d6");
});

test("loadSavedDoc returns null when nothing has been saved", () => {
  const storage = makeStorage();
  assert.equal(loadSavedDoc(storage), null);
});

test("loadSavedDoc returns empty string when an empty doc was saved", () => {
  // Empty saved doc is distinguishable from "never saved" by virtue of
  // getItem returning "" vs null.
  const storage = makeStorage();
  saveDoc("", storage);
  assert.equal(loadSavedDoc(storage), "");
});

test("saveDoc swallows storage errors silently", () => {
  // Private-browsing modes throw on setItem. The save must not propagate.
  const storage = makeThrowingStorage();
  assert.doesNotThrow(() => saveDoc("output 1d6", storage));
});

test("loadSavedDoc swallows storage errors silently and returns null", () => {
  const storage = makeThrowingStorage();
  assert.equal(loadSavedDoc(storage), null);
});

test("loadSavedDoc returns null when storage is unavailable (null/undefined)", () => {
  assert.equal(loadSavedDoc(null), null);
  assert.equal(loadSavedDoc(undefined), null);
});

test("saveDoc no-ops when storage is unavailable", () => {
  assert.doesNotThrow(() => saveDoc("x", null));
  assert.doesNotThrow(() => saveDoc("x", undefined));
});

test("STORAGE_KEY is stable and namespaced", () => {
  // Other tabs / apps on the same origin must not collide. The "anydyce-
  // playground:" prefix is the namespace.
  assert.match(STORAGE_KEY, /^anydyce-playground:/);
});

// ---- loadLogsSplit / saveLogsSplit ---------------------------------------

test("LOGS_SPLIT_KEY shares the playground namespace", () => {
  assert.match(LOGS_SPLIT_KEY, /^anydyce-playground:/);
  assert.notEqual(LOGS_SPLIT_KEY, STORAGE_KEY);
});

test("saveLogsSplit + loadLogsSplit round-trip a numeric percentage", () => {
  const storage = makeStorage();
  saveLogsSplit(42.5, storage);
  assert.equal(loadLogsSplit(storage), 42.5);
});

test("saveLogsSplit + loadLogsSplit round-trip an integer percentage", () => {
  const storage = makeStorage();
  saveLogsSplit(75, storage);
  assert.equal(loadLogsSplit(storage), 75);
});

test("loadLogsSplit returns null when unset", () => {
  assert.equal(loadLogsSplit(makeStorage()), null);
});

test("loadLogsSplit returns null on garbage values", () => {
  const storage = makeStorage();
  storage.setItem(LOGS_SPLIT_KEY, "nonsense");
  assert.equal(loadLogsSplit(storage), null);
});

test("loadLogsSplit returns null on storage error", () => {
  assert.equal(loadLogsSplit(makeThrowingStorage()), null);
});

test("saveLogsSplit swallows storage errors silently", () => {
  assert.doesNotThrow(() => saveLogsSplit(50, makeThrowingStorage()));
});

test("loadLogsSplit / saveLogsSplit no-op when storage is unavailable", () => {
  assert.equal(loadLogsSplit(null), null);
  assert.doesNotThrow(() => saveLogsSplit(50, null));
});

// ---- stripUrlFragment ----------------------------------------------------

function makeLocAndHist(initialHash, pathname = "/", search = "") {
  const loc = { hash: initialHash, pathname, search };
  const hist = {
    calls: [],
    replaceState(state, title, url) {
      this.calls.push({ state, title, url });
      // Mirror real browser: update loc.hash since the URL we passed has no #
      loc.hash = "";
    },
  };
  return { loc, hist };
}

test("stripUrlFragment removes the fragment via history.replaceState", () => {
  const { loc, hist } = makeLocAndHist("#p=abc");
  stripUrlFragment(loc, hist);
  assert.equal(hist.calls.length, 1);
  assert.equal(hist.calls[0].url, "/");
  assert.equal(loc.hash, "");
});

test("stripUrlFragment preserves pathname and query string", () => {
  const { loc, hist } = makeLocAndHist("#p=abc", "/playground/", "?foo=bar");
  stripUrlFragment(loc, hist);
  assert.equal(hist.calls[0].url, "/playground/?foo=bar");
});

test("stripUrlFragment is a no-op when no fragment is present", () => {
  const { loc, hist } = makeLocAndHist("");
  stripUrlFragment(loc, hist);
  assert.equal(hist.calls.length, 0);
});

test("stripUrlFragment swallows errors silently", () => {
  const loc = { hash: "#p=abc", pathname: "/", search: "" };
  const hist = {
    replaceState() {
      throw new Error("file:// restricted");
    },
  };
  assert.doesNotThrow(() => stripUrlFragment(loc, hist));
});

test("stripUrlFragment no-ops when loc / hist are unavailable", () => {
  assert.doesNotThrow(() => stripUrlFragment(null, null));
  assert.doesNotThrow(() => stripUrlFragment(undefined, undefined));
});

// ---- createDebouncedSaver -------------------------------------------------

function makeFakeTimers() {
  const timers = new Map();
  let nextId = 1;
  let now = 0;
  const setTimer = (fn, delay) => {
    const id = nextId++;
    timers.set(id, { fn, fireAt: now + delay });
    return id;
  };
  const clearTimer = (id) => {
    timers.delete(id);
  };
  const advance = (ms) => {
    now += ms;
    // Fire any timers whose fireAt has elapsed, in insertion order.
    for (const [id, t] of [...timers.entries()]) {
      if (t.fireAt <= now) {
        timers.delete(id);
        t.fn();
      }
    }
  };
  return { setTimer, clearTimer, advance, get pending() { return timers.size; } };
}

test("createDebouncedSaver fires onFire after delayMs", () => {
  const timers = makeFakeTimers();
  const fired = [];
  const saver = createDebouncedSaver({
    delayMs: 500,
    onFire: (t) => fired.push(t),
    setTimer: timers.setTimer,
    clearTimer: timers.clearTimer,
  });
  saver.schedule("hello");
  assert.deepEqual(fired, []);
  timers.advance(499);
  assert.deepEqual(fired, []);
  timers.advance(1);
  assert.deepEqual(fired, ["hello"]);
});

test("createDebouncedSaver only fires once per quiet period (debounce semantics)", () => {
  const timers = makeFakeTimers();
  const fired = [];
  const saver = createDebouncedSaver({
    delayMs: 500,
    onFire: (t) => fired.push(t),
    setTimer: timers.setTimer,
    clearTimer: timers.clearTimer,
  });
  saver.schedule("a");
  timers.advance(400);
  saver.schedule("ab");
  timers.advance(400);
  saver.schedule("abc");
  // 800ms elapsed but never 500 of quiet -- nothing fired yet
  assert.deepEqual(fired, []);
  timers.advance(500);
  assert.deepEqual(fired, ["abc"]);
});

test("createDebouncedSaver uses the latest scheduled text", () => {
  const timers = makeFakeTimers();
  const fired = [];
  const saver = createDebouncedSaver({
    delayMs: 100,
    onFire: (t) => fired.push(t),
    setTimer: timers.setTimer,
    clearTimer: timers.clearTimer,
  });
  saver.schedule("one");
  saver.schedule("two");
  saver.schedule("three");
  timers.advance(100);
  assert.deepEqual(fired, ["three"]);
});

test("createDebouncedSaver.flush fires immediately and clears the pending timer", () => {
  const timers = makeFakeTimers();
  const fired = [];
  const saver = createDebouncedSaver({
    delayMs: 500,
    onFire: (t) => fired.push(t),
    setTimer: timers.setTimer,
    clearTimer: timers.clearTimer,
  });
  saver.schedule("x");
  saver.flush();
  assert.deepEqual(fired, ["x"]);
  assert.equal(timers.pending, 0);
  // Subsequent advance should NOT fire again
  timers.advance(1000);
  assert.deepEqual(fired, ["x"]);
});

test("createDebouncedSaver.flush is a no-op when nothing is scheduled", () => {
  const timers = makeFakeTimers();
  const fired = [];
  const saver = createDebouncedSaver({
    delayMs: 500,
    onFire: (t) => fired.push(t),
    setTimer: timers.setTimer,
    clearTimer: timers.clearTimer,
  });
  saver.flush();
  assert.deepEqual(fired, []);
});

test("createDebouncedSaver.cancel discards the pending save without firing", () => {
  const timers = makeFakeTimers();
  const fired = [];
  const saver = createDebouncedSaver({
    delayMs: 500,
    onFire: (t) => fired.push(t),
    setTimer: timers.setTimer,
    clearTimer: timers.clearTimer,
  });
  saver.schedule("x");
  saver.cancel();
  timers.advance(1000);
  assert.deepEqual(fired, []);
});
