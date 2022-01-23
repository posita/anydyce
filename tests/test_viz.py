# ======================================================================================
# Copyright and other protections apply. Please see the accompanying LICENSE file for
# rights and restrictions governing use of this software. All rights not expressly
# waived or licensed are reserved. If that file is missing or appears to be modified
# from its original, then please contact the author before viewing or using this
# software in any capacity.
# ======================================================================================

from __future__ import annotations

import random
from fractions import Fraction
from math import isclose
from typing import Tuple

import pytest
from dyce import H, P

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


def test_limit_for_display_identity() -> None:
    h = H(6)
    assert viz.limit_for_display(h, Fraction(0)) is h


def test_limit_for_display_empty() -> None:
    assert viz.limit_for_display(H({})) == H({})


def test_limit_for_display_cull_everything() -> None:
    assert viz.limit_for_display(H(6), Fraction(1)) == H({})


def test_limit_for_display_out_of_bounds() -> None:
    with pytest.raises(ValueError):
        assert viz.limit_for_display(H(6), Fraction(-1))

    with pytest.raises(ValueError):
        assert viz.limit_for_display(H(6), Fraction(2))


def test_values_xy_for_graph_type() -> None:
    d6 = H(6)
    d6_outcomes = tuple(d6.outcomes())
    p_3d6 = 3 @ P(d6)
    lo = p_3d6.h(0)
    hi = p_3d6.h(-1)

    def _tuples_close(a: Tuple[float, ...], b: Tuple[float, ...]) -> bool:
        if len(a) != len(b):
            return False

        return all(isclose(a_val, b_val) for a_val, b_val in zip(a, b))

    lo_outcomes_normal, lo_values_normal = viz.values_xy_for_graph_type(
        lo, viz.GraphType.NORMAL
    )
    hi_outcomes_normal, hi_values_normal = viz.values_xy_for_graph_type(
        hi, viz.GraphType.NORMAL
    )
    assert lo_outcomes_normal == d6_outcomes
    assert _tuples_close(
        lo_values_normal,
        (
            0.4212962962962,
            0.2824074074074,
            0.1712962962962,
            0.0879629629629,
            0.0324074074074,
            0.0046296296296,
        ),
    )
    assert _tuples_close(hi_values_normal, lo_values_normal[::-1])

    lo_outcomes_at_least, lo_values_at_least = viz.values_xy_for_graph_type(
        lo, viz.GraphType.AT_LEAST
    )
    hi_outcomes_at_least, hi_values_at_least = viz.values_xy_for_graph_type(
        hi, viz.GraphType.AT_LEAST
    )
    assert lo_outcomes_at_least == d6_outcomes
    assert _tuples_close(
        lo_values_at_least,
        (
            1.0,
            0.5787037037037,
            0.2962962962962,
            0.125,
            0.0370370370370,
            0.0046296296296,
        ),
    )
    assert _tuples_close(
        hi_values_at_least,
        (
            1.0,
            0.9953703703703,
            0.9629629629629,
            0.875,
            0.7037037037037,
            0.4212962962962,
        ),
    )

    lo_outcomes_at_most, lo_values_at_most = viz.values_xy_for_graph_type(
        lo, viz.GraphType.AT_MOST
    )
    hi_outcomes_at_most, hi_values_at_most = viz.values_xy_for_graph_type(
        hi, viz.GraphType.AT_MOST
    )
    assert lo_outcomes_at_most == d6_outcomes
    assert _tuples_close(lo_values_at_most, hi_values_at_least[::-1])
    assert _tuples_close(hi_values_at_most, lo_values_at_least[::-1])


def test_plot_burst() -> None:
    matplotlib = pytest.importorskip("matplotlib", reason="requires matplotlib")
    # See <https://github.com/matplotlib/matplotlib/issues/14304#issuecomment-545717061>
    matplotlib.use("agg")
    from matplotlib import patches, pyplot

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
    matplotlib = pytest.importorskip("matplotlib", reason="requires matplotlib")
    # See <https://github.com/matplotlib/matplotlib/issues/14304#issuecomment-545717061>
    matplotlib.use("agg")
    from matplotlib import patches, pyplot

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
