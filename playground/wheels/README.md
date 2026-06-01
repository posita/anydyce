# Playground wheels

The playground installs `anydyce` (and any of its non-Pyodide-bundled
dependencies) into the in-browser Pyodide runtime via `micropip`. Pyodide
needs the wheels served from a same-origin URL, so they live here.

## Setup

1. Build the anydyce wheel:

   ```sh
   cd <repo-root>
   uv build --wheel
   cp dist/anydyce-*.whl playground/wheels/
   ```

2. List the wheel filename(s) in `index.json`:

   ```json
   ["anydyce-0.5.0rc1-py3-none-any.whl"]
   ```

   Multiple entries are allowed; non-anydyce wheels install first.
   Anydyce's other deps (`dyce`, `lark`, `ipywidgets`, `typing_extensions`)
   are resolved transitively by micropip from PyPI -- only bundle wheels
   here for packages that aren't installable via micropip / PyPI directly
   (notably: pre-release `anydyce` builds before publish to PyPI).

3. Serve the playground and the wheels will load on first runtime init.

## Why this matters

`micropip.install("./wheels/X.whl")` fetches from the same origin the page is
served from, so the static-server (`python3 -m http.server` etc.) must be
running from `playground/` (or a parent that includes it).

The wheels themselves are NOT committed to the repo; they're build artifacts.
The `.gitignore` here keeps them out of git. `index.json` IS committed and
acts as the contract between the dev's local build and the playground's
runtime discovery.
