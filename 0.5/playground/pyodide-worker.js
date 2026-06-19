// Pyodide worker. Runs in a Web Worker context (no DOM access; fetch / console
// are fine). Owns the Pyodide instance and all the Python-side state. Main-
// thread shim is pyodide-runner.js, which handles worker lifecycle and
// translates the message protocol into Promise-based calls.
//
// Why a worker: Pyodide's runPython is synchronous from JS's perspective and
// blocks whatever thread it's on. Running it in a worker keeps the main
// thread free, so the UI stays responsive during long Python runs (and a
// future Cancel button could just terminate the worker).
//
// Message protocol:
//   Main -> Worker:
//     { type: "init" }                              -- start loading Pyodide + wheels
//     { type: "run", source, runId }                -- run AnyDice source
//   Worker -> Main:
//     { type: "status", message }                   -- progress updates
//     { type: "ready" }                             -- init complete
//     { type: "result", text, outputs, displayPrecision, csv, warnings,
//       runId }                                     -- successful run
//     { type: "error", stage: "init"|"run", error,
//                      traceback?, warnings?, runId? }
//
// `text` is the fully-formatted, multi-block result string produced by
// anydyce's `format_results` -- the single source of truth for textual
// rendering, so the playground stays in lock-step with the magic and any
// other anydyce consumer. `outputs` is a list of {label, items} per
// `output` statement (items = list of [outcome, count] pairs) consumed by
// the bars view. `displayPrecision` is the run's final display precision
// (after any `set "anydyce: display precision"` directives) so the bars
// view formats percent labels consistently with the text view. `csv` and
// `csvFilename` are the base64-encoded CSV export and its download name
// (anydyce.csv.csv_base64 / csv_filename, same as the Jupyter widget's
// download link) backing the CSV button.
//
// `warnings` is an array of {category, message, filename, lineno} captured
// by the Python-side showwarning override. It accompanies BOTH successful
// runs and run-stage errors -- a program can emit warnings up to the point
// it raises. `traceback` is the full Python traceback string (separate
// from `error`, which is a short one-line summary like
// "ValueError: foo"). Init-stage errors have neither traceback nor
// warnings populated.

const PYODIDE_VERSION = "v0.27.5";
const PYODIDE_INDEX_URL = `https://cdn.jsdelivr.net/pyodide/${PYODIDE_VERSION}/full/`;

// Pyodide ships as a non-module classic script that registers `loadPyodide`
// on the worker's global scope. importScripts() is the classic-worker
// equivalent of a <script src> tag; module workers can't use it, so this
// worker is intentionally classic (not type: "module").
importScripts(`${PYODIDE_INDEX_URL}pyodide.js`);

const PYTHON_BOOTSTRAP = `
import traceback as _traceback
import warnings
from dyce.lifecycle import ExperimentalWarning
# Default action is "default" (print first occurrence per location). The
# playground UI shows every warning explicitly in the logs pane, so we
# switch to "always" -- a recurring TruncationWarning at the same site
# should be visible each run, not silently de-duplicated. simplefilter()
# RESETS the filter list, so the category-specific ignores below MUST be
# added AFTER it; filterwarnings() prepends, so the last-added rule is
# checked first.
warnings.simplefilter("always")
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=ExperimentalWarning)

from anydyce.anydice import Settings, format_results, run as _anydyce_run
from anydyce.csv import csv_base64, csv_filename

_captured_warnings = []

def _capture_warning(message, category, filename, lineno, file=None, line=None):
    _captured_warnings.append({
        "category": category.__name__,
        "message": str(message),
        "filename": filename or "",
        "lineno": int(lineno) if lineno is not None else 0,
    })

warnings.showwarning = _capture_warning

def _do_run(source):
    _captured_warnings.clear()
    # Fresh Settings per run so a prior cell's set directives don't leak.
    # _anydyce_run mutates this in place when the program uses
    # \`set "anydyce: display precision" to ...\` / calculation precision;
    # format_results then reads the final display_precision back.
    settings = Settings()
    try:
        results = _anydyce_run(source, settings=settings)
    except BaseException as exc:
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": _traceback.format_exc(),
            "warnings": list(_captured_warnings),
        }
    return {
        "ok": True,
        # Single source of truth for text rendering: anydyce's format_results.
        # Header style, empty-distribution wording, precision handling, etc.
        # all live in one place; the playground tracks anydyce automatically.
        "text": format_results(results, settings=settings),
        # Raw per-output data for the bars view (and future graphical
        # consumers).
        "outputs": [
            {"label": label, "items": list(h.items()) if h else []}
            for label, h in results
        ],
        # Final display precision after any \`set "anydyce: display
        # precision"\` directives -- the bars view formats its percent
        # labels with this so both views honor the same setting.
        "displayPrecision": settings.display_precision,
        # Base64 CSV + filename via the same anydyce.csv helpers the Jupyter
        # widget uses, so both surfaces export identical files with identical
        # names. Computed eagerly (not on demand) so the download keeps
        # working after a Cancel terminates the worker and wipes Python-side
        # state.
        "csv": csv_base64([(label, h, None) for label, h in results]),
        "csvFilename": csv_filename([label for label, _ in results]),
        "warnings": list(_captured_warnings),
    }
`;

let pyodide = null;

function postStatus(message) {
  self.postMessage({ type: "status", message });
}

async function discoverLocalWheels() {
  try {
    const url = new URL("./wheels/index.json", self.location.href);
    const resp = await fetch(url);
    if (!resp.ok) return [];
    const list = await resp.json();
    if (!Array.isArray(list)) return [];
    return list.filter((n) => typeof n === "string" && n.endsWith(".whl"));
  } catch {
    return [];
  }
}

async function init() {
  postStatus("Loading Python runtime...");
  pyodide = await loadPyodide({ indexURL: PYODIDE_INDEX_URL });

  postStatus("Loading micropip...");
  await pyodide.loadPackage("micropip");
  const micropip = pyodide.pyimport("micropip");

  postStatus("Discovering local wheels...");
  const wheelNames = await discoverLocalWheels();
  if (wheelNames.length === 0) {
    throw new Error(
      "No wheels found in ./wheels/. Build the anydyce wheel " +
      "(`uv build --wheel` in the repo root) and list its filename in " +
      "playground/wheels/index.json (e.g. " +
      '`["anydyce-0.5.0rc1-py3-none-any.whl"]`).',
    );
  }

  postStatus(`Installing ${wheelNames.length} local wheel(s)...`);
  // Install all bundled wheels in a SINGLE micropip call so micropip resolves
  // the set as one transaction: inter-dependencies (dyce needs optype;
  // anydyce needs dyce/lark) are satisfied from the provided wheels rather
  // than fetched from PyPI, so init makes no cross-origin round-trips.
  // (Installing one wheel at a time would let a dependency resolve from PyPI
  // before its bundled wheel had been installed -- notably optype, which dyce
  // pulls in -- which is why ordering the loop wasn't enough.) micropip
  // requires absolute URLs with a real scheme, so resolve each against the
  // worker's location (e.g. http://localhost:8000/wheels/X.whl).
  const wheelUrls = wheelNames.map((name) =>
    new URL(`./wheels/${name}`, self.location.href).toString(),
  );
  await micropip.install(wheelUrls);

  postStatus("Initializing AnyDice interpreter...");
  await pyodide.runPythonAsync(PYTHON_BOOTSTRAP);

  postStatus("Ready.");
}

function runSource(source) {
  if (!pyodide) {
    throw new Error("Pyodide not initialized");
  }
  const doRun = pyodide.globals.get("_do_run");
  let resultProxy;
  try {
    resultProxy = doRun(source);
    return resultProxy.toJs({ dict_converter: Object.fromEntries });
  } finally {
    if (resultProxy && typeof resultProxy.destroy === "function") {
      resultProxy.destroy();
    }
    doRun.destroy();
  }
}

self.addEventListener("message", async (ev) => {
  const msg = ev.data;
  if (msg.type === "init") {
    try {
      await init();
      self.postMessage({ type: "ready" });
    } catch (err) {
      self.postMessage({
        type: "error",
        stage: "init",
        error: (err && err.message) || String(err),
      });
    }
  } else if (msg.type === "run") {
    try {
      const out = runSource(msg.source);
      // out is the structured result from _do_run: either {ok:true,
      // results, warnings} or {ok:false, error, traceback, warnings}.
      // We translate to the existing result/error message split.
      if (out.ok) {
        self.postMessage({
          type: "result",
          text: out.text,
          outputs: out.outputs,
          displayPrecision: out.displayPrecision,
          csv: out.csv,
          csvFilename: out.csvFilename,
          warnings: out.warnings,
          runId: msg.runId,
        });
      } else {
        self.postMessage({
          type: "error",
          stage: "run",
          error: out.error,
          traceback: out.traceback,
          warnings: out.warnings,
          runId: msg.runId,
        });
      }
    } catch (err) {
      // Hard failure outside _do_run's try/except (Pyodide-level error,
      // e.g. _do_run not defined). No captured warnings available.
      self.postMessage({
        type: "error",
        stage: "run",
        error: (err && err.message) || String(err),
        traceback: null,
        warnings: [],
        runId: msg.runId,
      });
    }
  }
});
