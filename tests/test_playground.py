# ======================================================================================
# Copyright and other protections apply. Please see the accompanying LICENSE file for
# rights and restrictions governing use of this software. All rights not expressly
# waived or licensed are reserved. If that file is missing or appears to be modified
# from its original, then please contact the author before viewing or using this
# software in any capacity.
# ======================================================================================

import warnings
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def bootstrap() -> Iterator[dict[str, Any]]:
    source = (Path(__file__).parents[1] / "playground/pyodide-worker.js").read_text()
    python = source.split("const PYTHON_BOOTSTRAP = `\n", 1)[1].split("\n`;", 1)[0]
    namespace: dict[str, Any] = {}
    with warnings.catch_warnings():
        exec(python, namespace)  # ruff: ignore[exec-builtin]
        yield namespace


@pytest.mark.parametrize(
    ("graph_type", "probabilities"),
    [
        ("normal", [25.0, 75.0]),
        ("at_least", [100.0, 75.0]),
        ("at_most", [25.0, 100.0]),
    ],
)
def test_plot_probabilities(
    bootstrap: dict[str, Any],
    graph_type: str,
    probabilities: list[float],
) -> None:
    result = bootstrap["_do_run"]("output d{1, 2, 2, 2}")
    specs = result["probabilitySpecs"][graph_type]
    assert specs["barSpecs"][0]["data"][0]["customdata"] == probabilities
    assert specs["lineSpec"]["data"][0]["y"] == probabilities
    ridge = next(s for s in specs["ridgeSpec"]["data"] if "customdata" in s)
    assert ridge["customdata"] == probabilities
