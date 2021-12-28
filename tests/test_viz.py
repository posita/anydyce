# ======================================================================================
# Copyright and other protections apply. Please see the accompanying LICENSE file for
# rights and restrictions governing use of this software. All rights not expressly
# waived or licensed are reserved. If that file is missing or appears to be modified
# from its original, then please contact the author before viewing or using this
# software in any capacity.
# ======================================================================================

from __future__ import annotations

import random

import pytest
from dyce import H

from anydyce import viz

__all__ = ()


# ---- Tests ---------------------------------------------------------------------------


def test_alphasize() -> None:
    colors = [
        [r / 10, g / 10, b / 10, random.random()]
        for r, g, b in zip(*(range(0, 10, 2), range(3, 9), range(10, 0, -2)))
    ]
    actual_colors = viz.alphasize(colors, 0.8)
    expected_colors = [(r, g, b, 0.8) for r, g, b, _ in colors]
    assert actual_colors == expected_colors
    assert viz.alphasize(colors, -1.0) == colors


def test_cumulative_probability_formatter() -> None:
    h = 2 @ H(6)
    labels = tuple(
        viz.cumulative_probability_formatter(outcome, probability, h)
        for outcome, probability in h.distribution()
    )
    assert labels == (
        "2 2.78%; ≥2.78%; ≤100.00%",
        "3 5.56%; ≥8.33%; ≤97.22%",
        "4 8.33%; ≥16.67%; ≤91.67%",
        "5 11.11%; ≥27.78%; ≤83.33%",
        "6 13.89%; ≥41.67%; ≤72.22%",
        "7 16.67%; ≥58.33%; ≤58.33%",
        "8 13.89%; ≥72.22%; ≤41.67%",
        "9 11.11%; ≥83.33%; ≤27.78%",
        "10 8.33%; ≥91.67%; ≤16.67%",
        "11 5.56%; ≥97.22%; ≤8.33%",
        "12 2.78%; ≥100.00%; ≤2.78%",
    )


def test_plot_burst() -> None:
    patches = pytest.importorskip("matplotlib.patches", reason="requires matplotlib")
    pyplot = pytest.importorskip("matplotlib.pyplot", reason="requires matplotlib")

    _, ax = pyplot.subplots()
    d6_2 = 2 @ H(6)
    viz.plot_burst(ax, d6_2)
    wedge_labels = [
        w.get_label() for w in ax.get_children() if isinstance(w, patches.Wedge)
    ]
    assert len(wedge_labels) == 22
    assert wedge_labels == [
        "",  # 2 is hidden
        "5.56%",
        "8.33%",
        "11.11%",
        "13.89%",
        "16.67%",
        "13.89%",
        "11.11%",
        "8.33%",
        "5.56%",
        "",  # 12 is hidden
        "",  # 2 is hidden
        "3",
        "4",
        "5",
        "6",
        "7",
        "8",
        "9",
        "10",
        "11",
        "",  # 12 is hidden
    ]


def test_plot_burst_outer() -> None:
    patches = pytest.importorskip("matplotlib.patches", reason="requires matplotlib")
    pyplot = pytest.importorskip("matplotlib.pyplot", reason="requires matplotlib")

    _, ax = pyplot.subplots()
    d6_2 = 2 @ H(6)
    viz.plot_burst(ax, d6_2, outer_formatter=viz.cumulative_probability_formatter)
    wedge_labels = [
        w.get_label() for w in ax.get_children() if isinstance(w, patches.Wedge)
    ]
    assert len(wedge_labels) == 22
    assert wedge_labels == [
        "",  # 2 is hidden
        "3 5.56%; ≥8.33%; ≤97.22%",
        "4 8.33%; ≥16.67%; ≤91.67%",
        "5 11.11%; ≥27.78%; ≤83.33%",
        "6 13.89%; ≥41.67%; ≤72.22%",
        "7 16.67%; ≥58.33%; ≤58.33%",
        "8 13.89%; ≥72.22%; ≤41.67%",
        "9 11.11%; ≥83.33%; ≤27.78%",
        "10 8.33%; ≥91.67%; ≤16.67%",
        "11 5.56%; ≥97.22%; ≤8.33%",
        "",  # 12 is hidden
        "",  # 2 is hidden
        "3",
        "4",
        "5",
        "6",
        "7",
        "8",
        "9",
        "10",
        "11",
        "",  # 12 is hidden
    ]
