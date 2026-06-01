// Pyodide runner -- main-thread shim. Spawns the Pyodide Web Worker and
// translates its postMessage protocol into Promise-based calls for the
// playground UI. The Pyodide instance itself lives inside the worker (see
// pyodide-worker.js); main thread never touches it directly.
//
// Public API:
//   await initPyodide(onStatus)  -> resolves when runtime is ready
//   await runAnydice(source)     -> returns array of {label, text, short, items}

let worker = null;
let initPromise = null;
let onStatusCallback = null;
let nextRunId = 0;
const pendingRuns = new Map(); // runId -> { resolve, reject }
// Sticky flag set when the worker emits an `error` event (worker-script-level
// crash, e.g. Pyodide internal failure, OOM, importScripts failure). Once
// set, subsequent runAnydice / initPyodide calls reject immediately with a
// "please reload" message rather than silently hanging on postMessage to a
// dead worker. We could try to rebuild the worker in place, but for a
// persistent crash that'd just re-crash on the next run; surfacing the
// failure and letting the user reload is more honest.
let workerCrashed = false;
let workerCrashError = null;

function ensureWorker() {
  if (worker) return;
  // Classic worker (NOT type: "module") because pyodide.js uses
  // importScripts(), which isn't available in module workers.
  worker = new Worker(new URL("./pyodide-worker.js", import.meta.url));

  worker.addEventListener("message", (ev) => {
    const msg = ev.data;
    switch (msg.type) {
      case "status":
        if (onStatusCallback) onStatusCallback(msg.message);
        break;
      case "result": {
        const handler = pendingRuns.get(msg.runId);
        if (handler) {
          pendingRuns.delete(msg.runId);
          handler.resolve(msg.results);
        }
        break;
      }
      case "error":
        if (msg.stage === "run") {
          const handler = pendingRuns.get(msg.runId);
          if (handler) {
            pendingRuns.delete(msg.runId);
            handler.reject(new Error(msg.error));
          }
        }
        // init errors are handled by the listener installed in initPyodide().
        break;
      // "ready" is also handled by the init listener; no-op here.
    }
  });

  worker.addEventListener("error", (ev) => {
    // Worker-script-level error (e.g. Pyodide internal crash, OOM, syntax
    // error in the worker file, importScripts failure). Mark the worker as
    // crashed so subsequent runAnydice / initPyodide calls reject
    // immediately rather than silently no-op'ing against the dead worker.
    workerCrashed = true;
    workerCrashError = new Error(
      `Pyodide worker crashed: ${ev.message || "unknown error"} ` +
        `(${ev.filename || "?"}:${ev.lineno || "?"}). ` +
        "Please reload the page.",
    );
    if (initPromise && initPromise.then) {
      initPromise = Promise.reject(workerCrashError);
    }
    for (const { reject } of pendingRuns.values()) reject(workerCrashError);
    pendingRuns.clear();
  });
}

export function initPyodide(onStatus = () => {}) {
  if (workerCrashed) return Promise.reject(workerCrashError);
  if (initPromise) return initPromise;
  ensureWorker();
  onStatusCallback = onStatus;

  initPromise = new Promise((resolve, reject) => {
    const onMessage = (ev) => {
      const msg = ev.data;
      if (msg.type === "ready") {
        worker.removeEventListener("message", onMessage);
        resolve();
      } else if (msg.type === "error" && msg.stage === "init") {
        worker.removeEventListener("message", onMessage);
        reject(new Error(msg.error));
      }
    };
    worker.addEventListener("message", onMessage);
    worker.postMessage({ type: "init" });
  });

  return initPromise;
}

export function runAnydice(source) {
  if (workerCrashed) return Promise.reject(workerCrashError);
  ensureWorker();
  const runId = ++nextRunId;
  return new Promise((resolve, reject) => {
    pendingRuns.set(runId, { resolve, reject });
    worker.postMessage({ type: "run", source, runId });
  });
}
