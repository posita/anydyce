// Pyodide runtime wrapper.  Loads Pyodide, installs the anydyce wheel from
// ./wheels/, and exposes a single async run(source) -> [{label, text, short}]
// entry point for the playground UI.
//
// Pyodide-the-runtime (NOT the kernel-wrapped variant we use in JupyterLite):
// no Jupyter messaging protocol, no message handlers; just `pyodide.runPython`
// at the boundary.  Simpler than spinning up an actual kernel for a one-shot
// editor + run + render workflow.

const PYODIDE_VERSION = "v0.27.5";
const PYODIDE_INDEX_URL = `https://cdn.jsdelivr.net/pyodide/${PYODIDE_VERSION}/full/`;

// Python-side bootstrap. Defines a single _do_run(source) helper that runs
// the AnyDice program through anydyce and shapes the output into a
// JS-friendly structure.  Suppresses experimental warnings in the same
// shape as our IPython %%anyd magic.
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

// Find every .whl file the user has dropped into ./wheels/. Pyodide's micropip
// will install them in the order returned; anydyce should be last since it
// imports the deps installed earlier.  We rely on naming convention rather
// than inspecting METADATA: anydyce wheel filename starts with "anydyce-",
// everything else is treated as a dependency.
async function discoverLocalWheels() {
  const candidates = [];

  // Try fetching wheels/index.json if present (preferred for clean enumeration).
  // The user is expected to maintain wheels/index.json as a list of filenames.
  try {
    const resp = await fetch("./wheels/index.json");
    if (resp.ok) {
      const list = await resp.json();
      if (Array.isArray(list)) {
        for (const name of list) {
          if (typeof name === "string" && name.endsWith(".whl")) {
            candidates.push(name);
          }
        }
      }
    }
  } catch {
    // Fall through to filename-guess fallback.
  }

  return candidates;
}

// Single shared promise so concurrent callers all wait on the same load.
let _initPromise = null;

export function initPyodide(onStatus = () => {}) {
  if (_initPromise) return _initPromise;
  _initPromise = (async () => {
    onStatus("Loading Python runtime...");

    if (typeof loadPyodide !== "function") {
      throw new Error(
        "loadPyodide is not defined. The Pyodide CDN script in index.html " +
        "may have failed to load -- check the network tab.",
      );
    }

    const pyodide = await loadPyodide({ indexURL: PYODIDE_INDEX_URL });

    onStatus("Loading micropip...");
    await pyodide.loadPackage("micropip");
    const micropip = pyodide.pyimport("micropip");

    onStatus("Discovering local wheels...");
    const wheelNames = await discoverLocalWheels();
    if (wheelNames.length === 0) {
      throw new Error(
        "No wheels found in ./wheels/. Build the anydyce wheel " +
        "(`uv build --wheel` in the repo root) and list its filename in " +
        "playground/wheels/index.json (e.g. " +
        '`["anydyce-0.5.0rc1-py3-none-any.whl"]`).',
      );
    }

    onStatus(`Installing ${wheelNames.length} local wheel(s)...`);
    // Sort so non-anydyce wheels install before anydyce. Pyodide / micropip
    // resolves transitive deps from PyPI automatically; local wheels override.
    wheelNames.sort((a, b) => {
      const aAnyd = a.startsWith("anydyce-") ? 1 : 0;
      const bAnyd = b.startsWith("anydyce-") ? 1 : 0;
      return aAnyd - bAnyd;
    });
    for (const name of wheelNames) {
      onStatus(`Installing ${name}...`);
      // micropip requires an absolute URL with a real http/https scheme; a
      // bare relative path "./wheels/X.whl" is rejected with "Cannot download
      // from a non-remote location". Resolve against the document base URL so
      // we end up with e.g. http://localhost:8000/wheels/X.whl.
      const wheelUrl = new URL(`./wheels/${name}`, window.location.href).toString();
      await micropip.install(wheelUrl);
    }

    onStatus("Initializing AnyDice interpreter...");
    await pyodide.runPythonAsync(PYTHON_BOOTSTRAP);

    onStatus("Ready.");
    return pyodide;
  })();
  return _initPromise;
}

// Run an AnyDice source string through anydyce, returning an array of
// {label, text, short, items} objects -- one per `output` statement.
export async function runAnydice(pyodide, source) {
  const doRun = pyodide.globals.get("_do_run");
  let resultProxy;
  try {
    resultProxy = doRun(source);
    // Convert the Python list-of-dicts to a JS array-of-objects. The
    // dict_converter ensures each Python dict becomes a plain JS object
    // rather than a Pyodide PyProxy we'd have to clean up.
    return resultProxy.toJs({ dict_converter: Object.fromEntries });
  } finally {
    if (resultProxy && typeof resultProxy.destroy === "function") {
      resultProxy.destroy();
    }
    doRun.destroy();
  }
}
