// Pyodide runner -- main-thread shim. Spawns the Pyodide Web Worker and
// translates its postMessage protocol into Promise-based calls for the
// playground UI. The Pyodide instance itself lives inside the worker (see
// pyodide-worker.js); main thread never touches it directly.
//
// Public API:
//   await initPyodide(onStatus)  -> resolves when runtime is ready
//   await runAnydice(source)     -> resolves to {text, outputs,
//                                   displayPrecision, csv, csvFilename,
//                                   warnings};
//                                   rejects with RunError (Python exception:
//                                   carries .traceback and .warnings) or
//                                   CancelledError (deliberate cancel).
//                                   `text` is the fully-rendered display
//                                   string (anydyce's format_results).
//                                   `outputs` is raw per-output data for
//                                   the bars view. `displayPrecision` is
//                                   the run's final display precision.
//   cancelCurrentRun()           -> terminates the worker, rejecting any
//                                   in-flight run with CancelledError; caller
//                                   re-calls initPyodide() to bring runtime
//                                   back up before the next runAnydice().

// Distinct error class so the caller can distinguish a deliberate cancel
// from a real runtime error (e.g. a Python exception inside the program).
export class CancelledError extends Error {
  constructor() {
    super("Run cancelled.");
    this.name = "CancelledError";
  }
}

// Carries the full Python traceback and any warnings emitted before the
// exception was raised. The short summary lives in .message (e.g.
// "ValueError: foo"); .traceback is the full multi-line traceback.
export class RunError extends Error {
  constructor(message, traceback, warnings) {
    super(message);
    this.name = "RunError";
    this.traceback = traceback || null;
    this.warnings = warnings || [];
  }
}

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
          handler.resolve({
            text: msg.text || "",
            outputs: msg.outputs || [],
            displayPrecision: msg.displayPrecision,
            csv: msg.csv || "",
            csvFilename: msg.csvFilename || "",
            warnings: msg.warnings || [],
          });
        }
        break;
      }
      case "error":
        if (msg.stage === "run") {
          const handler = pendingRuns.get(msg.runId);
          if (handler) {
            pendingRuns.delete(msg.runId);
            handler.reject(
              new RunError(msg.error, msg.traceback, msg.warnings),
            );
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

// Returns true if there's at least one run currently waiting for a result.
// Useful for the UI to decide whether the Cancel button should be enabled.
export function hasInFlightRun() {
  return pendingRuns.size > 0;
}

// Terminate the worker, killing any in-flight run. The pending Promise(s)
// reject with CancelledError. State is reset so the next initPyodide() call
// creates a fresh worker -- there's no way to "resume" a terminated worker,
// re-init is mandatory before the next run.
//
// Why hard terminate instead of a co-operative cancel signal: Pyodide's
// Python execution can spend long stretches in C-level loops (dyce's deep
// arithmetic, importlib, etc.) where it never checks interrupt buffers. A
// terminate is the only mechanism that ALWAYS works in finite wall-clock
// time. The cost is one full Pyodide re-init (~5s) per cancel, which we
// accept for guaranteed responsiveness.
export function cancelCurrentRun() {
  if (!worker) return;
  worker.terminate();
  const cancelError = new CancelledError();
  for (const { reject } of pendingRuns.values()) reject(cancelError);
  pendingRuns.clear();
  worker = null;
  initPromise = null;
  // Deliberate-cancel resets are NOT crashes; clear those flags so the next
  // initPyodide() doesn't immediately short-circuit with the "please reload"
  // message left over from an actual prior crash.
  workerCrashed = false;
  workerCrashError = null;
}
