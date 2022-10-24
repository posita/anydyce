# ======================================================================================
# Copyright and other protections apply. Please see the accompanying LICENSE file for
# rights and restrictions governing use of this software. All rights not expressly
# waived or licensed are reserved. If that file is missing or appears to be modified
# from its original, then please contact the author before viewing or using this
# software in any capacity.
# ======================================================================================

from __future__ import annotations

import random
import re
from fractions import Fraction
from math import isclose
from test.support.warnings_helper import check_warnings
from typing import Tuple

import matplotlib
import pytest
from dyce import H, P
from ipywidgets import widgets
from matplotlib import patches, pyplot

from anydyce import HPlotterChooser
from anydyce.viz import (
    BarHPlotter,
    BurstHPlotter,
    HorizontalBarHPlotter,
    LineHPlotter,
    PlotWidgets,
    ScatterHPlotter,
    TraditionalPlotType,
    _csv_download_link,
    _histogram_specs_to_h_tuples,
    alphasize,
    cumulative_probability_formatter,
    limit_for_display,
    plot_burst,
    values_xy_for_graph_type,
)

__all__ = ()


# ---- Tests ---------------------------------------------------------------------------


class TestPlotWidgets:
    def test_construction(self) -> None:
        matplotlib.use("agg")
        plot_widgets = PlotWidgets(
            initial_alpha=0.125,
            initial_enable_cutoff=True,
            initial_graph_type=TraditionalPlotType.AT_LEAST,
            initial_markers="xo",
            initial_plot_style="default",
            initial_show_shadow=True,
        )
        assert plot_widgets.alpha.value == 0.125
        assert plot_widgets.enable_cutoff.value is True
        assert plot_widgets.graph_type.value is TraditionalPlotType.AT_LEAST
        assert plot_widgets.markers.value == "xo"
        assert plot_widgets.plot_style.value == "default"
        assert plot_widgets.show_shadow.value is True

    def test_construction_defaults(self) -> None:
        matplotlib.use("agg")
        plot_widgets = PlotWidgets()
        widget_map = plot_widgets.asdict()
        assert set(widget_map) == {
            "_rev_no",
            "alpha",
            "burst_cmap_inner",
            "burst_cmap_link",
            "burst_cmap_outer",
            "burst_color_bg",
            "burst_color_text",
            "burst_swap",
            "burst_zero_fill_normalize",
            "cutoff",
            "enable_cutoff",
            "graph_type",
            "markers",
            "plot_style",
            "scale",
            "show_shadow",
        }
        assert all(isinstance(widget, widgets.Widget) for widget in widget_map.values())

    def test_construction_warns_on_nonexistant_plot_type(self) -> None:
        matplotlib.use("agg")

        with check_warnings(quiet=True) as w:
            PlotWidgets(initial_plot_style="does not exist")
            assert any(
                isinstance(warning.message, RuntimeWarning)
                and warning.message.args
                and re.search(
                    r"\Aunrecognized plot style .*; reverting to .default.\Z",
                    warning.message.args[0],
                )
                for warning in w.warnings
            )


class TestBarHPlotter:
    def test_layouts(self) -> None:
        plot_widgets = PlotWidgets()
        bar_plotter = BarHPlotter()
        layout_widget = bar_plotter.layout(plot_widgets)
        assert isinstance(layout_widget, widgets.Widget)


class TestBurstHPlotter:
    def test_layouts(self) -> None:
        plot_widgets = PlotWidgets()
        burst_plotter = BurstHPlotter()
        layout_widget = burst_plotter.layout(plot_widgets)
        assert isinstance(layout_widget, widgets.Widget)


class TestHorizontalBarHPlotter:
    def test_layouts(self) -> None:
        plot_widgets = PlotWidgets()
        horizontal_bar_plotter = HorizontalBarHPlotter()
        layout_widget = horizontal_bar_plotter.layout(plot_widgets)
        assert isinstance(layout_widget, widgets.Widget)


class TestLineHPlotter:
    def test_layouts(self) -> None:
        plot_widgets = PlotWidgets()
        line_plotter = LineHPlotter()
        layout_widget = line_plotter.layout(plot_widgets)
        assert isinstance(layout_widget, widgets.Widget)


class TestScatterHPlotter:
    def test_layouts(self) -> None:
        plot_widgets = PlotWidgets()
        scatter_plotter = ScatterHPlotter()
        layout_widget = scatter_plotter.layout(plot_widgets)
        assert isinstance(layout_widget, widgets.Widget)


class TestHPlotterChooser:
    def test_construction(self) -> None:
        plot_widgets = PlotWidgets()
        chooser = HPlotterChooser(plot_widgets=plot_widgets)
        assert chooser._hs == ()
        assert set(chooser._plotters_by_name.keys()) == {
            "Line Plot",
            "Bar Plot",
            "Horizontal Bar Plots",
            "Burst Plots",
            "Scatter Plot",
        }
        accordion_widget = chooser._out.children[0]
        assert isinstance(accordion_widget, widgets.Accordion)
        assert accordion_widget.selected_index is None
        tab_widget = accordion_widget.children[0]
        assert isinstance(tab_widget, widgets.Tab)
        assert tab_widget.selected_index == 0

    def test_construction_histogram_specs(self) -> None:
        chooser = HPlotterChooser([H(6)])
        assert chooser._hs == (("Histogram 1", H(6), None),)

    def test_construction_controls_expanded(self) -> None:
        chooser = HPlotterChooser(controls_expanded=True)
        accordion_widget = chooser._out.children[0]
        assert isinstance(accordion_widget, widgets.Accordion)
        assert accordion_widget.selected_index == 0

    def test_construction_selected_name(self) -> None:
        chooser = HPlotterChooser(
            plotters_or_factories=(LineHPlotter, ScatterHPlotter),
            selected_name="Scatter Plot",
        )
        accordion_widget = chooser._out.children[0]
        assert isinstance(accordion_widget, widgets.Accordion)
        tab_widget = accordion_widget.children[0]
        assert isinstance(tab_widget, widgets.Tab)
        assert tab_widget.selected_index == 1

    def test_construction_warns_on_duplicate_plotter_name(self) -> None:
        with check_warnings(quiet=True) as w:
            plotters = LineHPlotter(), LineHPlotter()
            HPlotterChooser(plotters_or_factories=plotters)
            assert any(
                isinstance(warning.message, RuntimeWarning)
                and warning.message.args
                and re.search(
                    r"^ignoring redundant plotters with duplicate names 'Line Plot'$",
                    warning.message.args[0],
                )
                for warning in w.warnings
            )

    def test_construction_fails_on_no_plotters(self) -> None:
        with pytest.raises(ValueError):
            HPlotterChooser(plotters_or_factories=())

    def test_construction_fails_on_bad_selected_name(self) -> None:
        with pytest.raises(ValueError):
            plotters = (LineHPlotter(),)
            HPlotterChooser(
                plotters_or_factories=plotters,
                selected_name="no such plotter",
            )

    def test_update_hs(self) -> None:
        chooser = HPlotterChooser()
        expected = (("Histogram 1", H(6), None),)
        assert chooser._hs != expected
        chooser.update_hs([H(6)])
        assert chooser._hs == expected


def test_alphasize() -> None:
    colors = [
        [r / 10, g / 10, b / 10, random.random()]
        for r, g, b in zip(*(range(0, 10, 2), range(3, 9), range(10, 0, -2)))
    ]
    actual_colors = alphasize(colors, 0.8)
    expected_colors = [(r, g, b, 0.8) for r, g, b, _ in colors]
    assert actual_colors == expected_colors
    assert alphasize(colors, -1.0) == colors


def test_cumulative_probability_formatter() -> None:
    h = 2 @ H(6)
    labels = tuple(
        cumulative_probability_formatter(outcome, probability, h)
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
    assert limit_for_display(h, Fraction(0)) is h


def test_limit_for_display_empty() -> None:
    assert limit_for_display(H({}), Fraction(1, 2**13)) == H({})


def test_limit_for_display_cull_everything() -> None:
    assert limit_for_display(H(6), Fraction(1)) == H({})


def test_limit_for_display_out_of_bounds() -> None:
    with pytest.raises(ValueError):
        assert limit_for_display(H(6), Fraction(-1))

    with pytest.raises(ValueError):
        assert limit_for_display(H(6), Fraction(2))


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

    lo_outcomes_normal, lo_values_normal = values_xy_for_graph_type(
        lo, TraditionalPlotType.NORMAL
    )
    hi_outcomes_normal, hi_values_normal = values_xy_for_graph_type(
        hi, TraditionalPlotType.NORMAL
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

    lo_outcomes_at_least, lo_values_at_least = values_xy_for_graph_type(
        lo, TraditionalPlotType.AT_LEAST
    )
    hi_outcomes_at_least, hi_values_at_least = values_xy_for_graph_type(
        hi, TraditionalPlotType.AT_LEAST
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

    lo_outcomes_at_most, lo_values_at_most = values_xy_for_graph_type(
        lo, TraditionalPlotType.AT_MOST
    )
    hi_outcomes_at_most, hi_values_at_most = values_xy_for_graph_type(
        hi, TraditionalPlotType.AT_MOST
    )
    assert lo_outcomes_at_most == d6_outcomes
    assert _tuples_close(lo_values_at_most, hi_values_at_least[::-1])
    assert _tuples_close(hi_values_at_most, lo_values_at_least[::-1])


def test_plot_burst() -> None:
    matplotlib.use("agg")
    _, ax = pyplot.subplots()
    d6_2 = 2 @ H(6)
    plot_burst(ax, d6_2)
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
    matplotlib.use("agg")
    _, ax = pyplot.subplots()
    d6_2 = 2 @ H(6)
    plot_burst(ax, d6_2, outer_formatter=cumulative_probability_formatter)
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


def test_csv_download_link_emtpy() -> None:
    empty_csv_html = _csv_download_link(())
    assert (
        empty_csv_html.data
        == '\n<a download=".csv" href="data:text/csv;base64,T3V0Y29tZQ0K" target="_blank">\nDownload raw data as CSV\n</a>\n'
    )


def test_csv_download_link_single_histogram() -> None:
    d6_csv_html = _csv_download_link([("d6", H(6), None)])
    assert (
        d6_csv_html.data
        == '\n<a download="d6.csv" href="data:text/csv;base64,T3V0Y29tZSxkNg0KMSwwLjE2NjY2NjY2NjY2NjY2NjY2DQoyLDAuMTY2NjY2NjY2NjY2NjY2NjYNCjMsMC4xNjY2NjY2NjY2NjY2NjY2Ng0KNCwwLjE2NjY2NjY2NjY2NjY2NjY2DQo1LDAuMTY2NjY2NjY2NjY2NjY2NjYNCjYsMC4xNjY2NjY2NjY2NjY2NjY2Ng0K" target="_blank">\nDownload raw data as CSV\n</a>\n'
    )


def test_csv_download_link_secondary_histogram_ignored() -> None:
    d8d12_csv_html = _csv_download_link([("d8d12", H(8) + H(12), None)])
    d8d12_vs_2d10_csv_html = _csv_download_link([("d8d12", H(8) + H(12), 2 @ H(10))])
    assert d8d12_csv_html.data == d8d12_vs_2d10_csv_html.data


def test_csv_download_link_multiple_histograms() -> None:
    d6_and_d8_csv_html = _csv_download_link([("d6", H(6), None), ("d8", H(8), None)])
    assert (
        d6_and_d8_csv_html.data
        == '\n<a download="d6, d8.csv" href="data:text/csv;base64,T3V0Y29tZSxkNixkOA0KMSwwLjE2NjY2NjY2NjY2NjY2NjY2LDAuMTI1DQoyLDAuMTY2NjY2NjY2NjY2NjY2NjYsMC4xMjUNCjMsMC4xNjY2NjY2NjY2NjY2NjY2NiwwLjEyNQ0KNCwwLjE2NjY2NjY2NjY2NjY2NjY2LDAuMTI1DQo1LDAuMTY2NjY2NjY2NjY2NjY2NjYsMC4xMjUNCjYsMC4xNjY2NjY2NjY2NjY2NjY2NiwwLjEyNQ0KNywsMC4xMjUNCjgsLDAuMTI1DQo=" target="_blank">\nDownload raw data as CSV\n</a>\n'
    )


def test_histogram_specs_to_h_tuples_empty() -> None:
    assert _histogram_specs_to_h_tuples(()) == ()


def test_histogram_specs_to_h_tuples_single_h_like() -> None:
    assert _histogram_specs_to_h_tuples([H(8), P(12)]) == (
        ("Histogram 1", H(8), None),
        ("Histogram 2", H(12), None),
    )


def test_histogram_specs_to_h_tuples_two_tuple() -> None:
    assert _histogram_specs_to_h_tuples([("d8", H(8)), ("d12", P(12))]) == (
        ("d8", H(8), None),
        ("d12", H(12), None),
    )


def test_histogram_specs_to_h_tuples_three_tuple() -> None:
    assert _histogram_specs_to_h_tuples(
        [("d8d12", H(8), P(12)), ("d12d8", P(12), H(8)), ("d10", H(10), None)]
    ) == (
        ("d8d12", H(8), H(12)),
        ("d12d8", H(12), H(8)),
        ("d10", H(10), None),
    )
