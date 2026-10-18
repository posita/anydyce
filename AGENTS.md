# `dyceum` development guidance

`dyceum` contains higher-level visualization and application experiments around `dyce`.
It includes a cleanroom AnyDice-compatible interpreter, Jupyter integration, and a static Pyodide browser playground.
It supports CPython 3.11–3.15 and PyPy 3.11-3.12.
Versions come from Git tags through `setuptools-scm`; do not edit a version file.

The code is authoritative when this guidance becomes stale.
Update this file when durable project structure, tooling, or conventions change.

## Working safely

Treat the live working tree as authoritative.
Before editing an existing file, inspect its current working-tree, staged, and `HEAD` versions, then record and immediately recheck a content hash.
If it changed, re-read it and preserve the newer work.
After editing, inspect the diff and limit it to the requested regions.
Do not stage changes unless the user asks.

Generated documentation files can change during `make -C docs-src`.
Edit their source scripts rather than generated output, and verify hashes around generation when another process may be touching the tree.

When work depends on unreleased `dyce` changes, use the neighboring development checkout deliberately and do not leave accidental path dependencies in `pyproject.toml` or `uv.lock`.

## Layout

- `dyceum/anydice/` is the AnyDice-compatible interpreter.
  Its parser, AST, interpreter, settings, built-ins, formatter, and unparser are separate components.
- `dyceum/viz.py` provides the Matplotlib and ipywidgets visualization layer.
  The package root imports it lazily so `import dyceum` remains light.
- `dyceum/csv.py` provides result-export helpers.
- `playground/` is a static, zero-build application using JavaScript modules, Pyodide, CodeMirror, and Plotly.
- `tests/` contains package and interpreter tests.
- `docs/` contains site pages, notebooks, compatibility findings, and release notes.
- `docs-src/` contains the documentation generators and notebook sources used during site builds.
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

## Common commands

```bash
uv sync --group dev
uv run pytest
uv run pytest --cov --cov-report=term-missing
uv run tox -e py313
uv run pre-commit run --all-files --hook-stage pre-push
uv run make -C docs-src
uv run zensical build --strict
uv run zensical serve --strict
```

The pre-push hooks run Ruff, doctest normalization checks, and all four static type checkers: mypy, pyright, ty, and zuban.
Do not validate a typing change with only one checker.
Tox adds runtime checking with beartype and covers the supported Python matrix.

Pytest discovers doctests from package docstrings, `README.md`, and Markdown under `docs/`.

`docs-src/Makefile` builds the wheel and assembles JupyterLite, the playground, and pinned wheels into `docs/`.
Run it before building or serving the site with either builder.
Review it before changing documentation packaging.

## Python and documentation conventions

- Do not add `from __future__ import annotations`.
  Quote forward references only when necessary.
- Public docstrings use Markdown, raw triple-quoted strings, and one sentence per source line.
- Use mkdocstrings cross-references such as ``[`anyd`][dyceum.magic.anyd]`` for public intra-library references.
- Use `` `expression` `` and `` `#!math expression` `` for inline code and math.
- Comments should explain architecture, component boundaries, or genuinely counterintuitive code.
  Prefer descriptive names over commentary that restates the implementation.
- Use American spelling except for the project-wide `cancelled` and `cancelling` forms.
- In prose use curly quotation marks and apostrophes.
  In code, comments, and verbatim spans use ASCII quotes.
- Type-ignore comments have no space before `[`, and multiple error codes are alphabetized.
  All four type checkers must pass.

### Write plainly

Perfection is achieved, not when there is nothing more to add, but when there is nothing left to take away.

Use Orwell's tests: know what you mean; choose concrete words; cut needless words; prefer active voice when the actor matters; and avoid stale metaphors and inflated jargon. Prefer minimalism and a conversational tone that prioritizes clarity over complex syntax. Employ short, direct sentences and plain language to make complex themes accessible to a broad audience. Avoid metaphor or metaphorical professional jargon in technical writing. Prose must be precise, consistent, and unambiguous. Use one authoritative term consistently to refer to a single concept.

Complete thoughts should be separated by periods and a single space. Colons, em-dashes, and semicolons should be used sparingly. For example, semicolons may be used to separate items in a complicated list, usually preceded by a colon (see, e.g., Orwell's tests above). Em-dashes can be used to signal the occasional aside or parenthetical, but parentheses are preferred. If the aside is relevant in context, consider instead restructuring to improve clarity or simplicity. If it is not relevant, omit it. Occasional, brief asides that providing an appropriate jab or comic relief to a frustrating or complicated topic can remain in place, but they should be very rare exceptions and always subject to approval.

Avoid empty openings, recaps, motivational language, marketing adjectives, and conclusions that add no information. Do not shorten text by deleting a necessary fact or qualifier.

Use ASD-STE100 Simplified Technical English, Issue 9 (January 2025), as the writing standard for new or changed technical prose. This requirement applies to documentation, runbooks, handoff material, architecture text, migration plans, pull request text, review comments, issue comments, and code comments.

## Project mechanisms

- Import `experimental` from `dyce.lifecycle` for experimental APIs.
- Use `typing_extensions.deprecated` before Python 3.13 and `warnings.deprecated` on Python 3.13 and later.
- `_griffe_ext.py` adds lifecycle admonitions to generated API documentation.
- `helpers/check-doctests.py` checks and normalizes doctest blocks.
- Jupyter dependencies live in the `jupyter` extra and dependency group.

GitHub Actions references are pinned to full commit SHAs with matching version comments.
Update both together.
Releases are made by pushing a PEP 440-compatible `v*` tag; publishing and versioned documentation are handled by GitHub Actions.
