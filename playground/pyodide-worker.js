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
//     { type: "result", results, runId }            -- successful run
//     { type: "error", stage: "init"|"run", error, runId? }

const PYODIDE_VERSION = "v0.27.5";
const PYODIDE_INDEX_URL = `https://cdn.jsdelivr.net/pyodide/${PYODIDE_VERSION}/full/`;

// Pyodide ships as a non-module classic script that registers `loadPyodide`
// on the worker's global scope. importScripts() is the classic-worker
// equivalent of a <script src> tag; module workers can't use it, so this
// worker is intentionally classic (not type: "module").
importScripts(`${PYODIDE_INDEX_URL}pyodide.js`);

const PYTHON_BOOTSTRAP = `
import warnings
from dyce.lifecycle import ExperimentalWarning
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=ExperimentalWarning)

from anydyce.anydice import run as _anydyce_run

def _do_run(source):
    results = _anydyce_run(source)
    return [
        {
            "label": label,
            "text": h.format() if h else "(empty distribution)",
            "short": h.format_short() if h else "{}",
            "items": list(h.items()) if h else [],
        }
        for label, h in results
    ]
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
  // Install non-anydyce wheels before anydyce. micropip resolves transitive
  // deps from PyPI automatically; local wheels override.
  wheelNames.sort((a, b) => {
    const aA = a.startsWith("anydyce-") ? 1 : 0;
    const bA = b.startsWith("anydyce-") ? 1 : 0;
    return aA - bA;
  });
  for (const name of wheelNames) {
    postStatus(`Installing ${name}...`);
    // micropip requires an absolute URL with a real scheme; resolve against
    // the worker's location so we get e.g. http://localhost:8000/wheels/X.whl.
    const wheelUrl = new URL(`./wheels/${name}`, self.location.href).toString();
    await micropip.install(wheelUrl);
  }

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
      const results = runSource(msg.source);
      self.postMessage({ type: "result", results, runId: msg.runId });
    } catch (err) {
      self.postMessage({
        type: "error",
        stage: "run",
        error: (err && err.message) || String(err),
        runId: msg.runId,
      });
    }
  }
});
