# `dyceum` development guidance

`dyceum` contains higher-level visualization and application experiments around `dyce`.
It includes a cleanroom AnyDice-compatible interpreter, Jupyter integration, and a static Pyodide browser playground.
It supports CPython 3.11–3.14 and PyPy 3.11.
Versions come from Git tags through `setuptools-scm`; do not edit a version file.

The code is authoritative when this guidance becomes stale.
Update this file when durable project structure, tooling, or conventions change.

## Working safely

Treat the live working tree as authoritative.
Before editing an existing file, inspect its current working-tree, staged, and `HEAD` versions, then record and immediately recheck a content hash.
If it changed, re-read it and preserve the newer work.
After editing, inspect the diff and limit it to the requested regions.
Do not stage changes unless the user asks.

When work depends on unreleased `dyce` changes, use the neighboring development checkout deliberately and do not leave accidental path dependencies in `pyproject.toml` or `uv.lock`.

## Layout

- `dyceum/anydice/` is the AnyDice-compatible interpreter.
  Its parser, AST, interpreter, settings, built-ins, formatter, and unparser are separate components.
- `dyceum/viz.py` provides the Matplotlib and ipywidgets visualization layer.
  The package root imports it lazily so `import dyceum` remains light.
- `dyceum/csv.py` provides result-export helpers.
- `playground/` is a static, zero-build application using JavaScript modules, Pyodide, CodeMirror, and Plotly.
- `tests/` contains package and interpreter tests.
- `docs/` contains MkDocs sources, notebooks, compatibility findings, and release notes.
- `docs/notes/` and `notes/` contain design and reverse-engineering material rather than public API guarantees.

Avoid exhaustive module inventories here.
Use the package tree, `README.md`, and `docs/` for current detail.

## AnyDice compatibility

The existing interpreter aims to reproduce observed AnyDice behavior, including awkward behavior, unless a documented `dyceum:` extension says otherwise.
Do not “fix” a surprising semantic without checking the compatibility documentation, tests, probes, and corpus evidence.

`docs/anydice.md` is the public behavior report.
`docs/notes/anydice-semantics.md` and `docs/notes/dyceum-interpreter.md` hold deeper evidence and exploratory design notes.
The large oracle corpus may exist in the sibling `anydice-data/` directory when working in the shared development workspace.

Any stricter AnyDice-inspired language is a separate design and must not silently change the compatibility interpreter.

## Playground boundaries

The playground runs the Python interpreter in a Pyodide worker.
Its JavaScript owns browser rendering, persistence, resizing, and theme adaptation.
Portable chart structure comes from `dyce.viz.plotly`; the browser applies context-specific colors and calls Plotly.

Keep the playground zero-build unless a deliberate project decision changes that constraint.
Run its tests with:

```bash
cd playground
npm test
```

`_mkdocs_hooks.py` builds the wheel and assembles JupyterLite, the playground, and pinned wheels into the documentation site.
Review that hook before changing documentation packaging.

## Common commands

```bash
uv sync --group dev
uv run pytest
uv run pytest --cov --cov-report=term-missing
uv run tox -e py313
uv run pre-commit run --all-files --hook-stage pre-push
uv run mkdocs build
```

The pre-push hooks run Ruff, doctest normalization checks, and all four static type checkers: mypy, Pyrefly, Pyright, and ty.
Do not validate a typing change with only one checker.
Tox adds runtime checking with beartype and covers the supported Python matrix.

Pytest discovers doctests from package docstrings, `README.md`, and Markdown under `docs/`.

## Python and documentation conventions

- Do not add `from __future__ import annotations`.
  Quote forward references only when necessary.
- Public docstrings use Markdown, raw triple-quoted strings, and one sentence per source line.
- Use mkdocstrings cross-references for public intra-library references.
- Use `` `#!python expression` `` and `` `#!math expression` `` for inline code and math.
- Comments should explain architecture, component boundaries, or genuinely counterintuitive code.
  Prefer descriptive names over commentary that restates the implementation.
- Use American spelling except for the project-wide `cancelled` and `cancelling` forms.
- In prose use curly quotation marks and apostrophes.
  In code, comments, and verbatim spans use ASCII quotes.
- Type-ignore comments have no space before `[`, and multiple error codes are alphabetized.
  All four type checkers must pass.

Write direct prose.
Prefer periods to semicolons or dashes used as asides.
Avoid “+” as shorthand for “and” and avoid stock AI metaphors or throat-clearing.

## Project mechanisms

- Import `experimental` from `dyce.lifecycle` for experimental APIs.
- Use `typing_extensions.deprecated` before Python 3.13 and `warnings.deprecated` on Python 3.13 and later.
- `_griffe_ext.py` adds lifecycle admonitions to generated API documentation.
- `helpers/check-doctests.py` checks and normalizes doctest blocks.
- Jupyter dependencies live in the `jupyter` extra and dependency group.

GitHub Actions references are pinned to full commit SHAs with matching version comments.
Update both together.
Releases are made by pushing a PEP 440-compatible `v*` tag; publishing and versioned documentation are handled by GitHub Actions.
