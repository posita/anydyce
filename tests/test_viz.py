# ======================================================================================
# Copyright and other protections apply. Please see the accompanying LICENSE file for
# rights and restrictions governing use of this software. All rights not expressly
# waived or licensed are reserved. If that file is missing or appears to be modified
# from its original, then please contact the author before viewing or using this
# software in any capacity.
#
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# !!!!!!!!!!!!!!! IMPORTANT: READ THIS BEFORE EDITING! !!!!!!!!!!!!!!!
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# Please keep each docstring sentence on its own unwrapped line. It looks like crap in a
# text editor, but it has no effect on rendering, and it allows much more useful diffs.
# (This does not apply to code comments.) Thank you!
# ======================================================================================

import warnings
from fractions import Fraction

import matplotlib as mpl
import pytest
from dyce import H, P
from dyce.lifecycle import ExperimentalWarning
from ipywidgets import widgets  # type: ignore[import-untyped]

from anydyce import HPlotterChooser
from anydyce.viz import (
    BurstHPlotter,
    HorizontalBarHPlotter,
    LineHPlotter,
    PlotWarning,
    PlotWidgets,
    _csv_download_link,
    _histogram_specs_to_h_tuples,
    limit_for_display,
    values_xy_for_graph_type,
)

__all__ = ()


@pytest.fixture(autouse=True)
def _suppress_experimental() -> None:
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    warnings.filterwarnings("ignore", category=ExperimentalWarning)
    warnings.filterwarnings("ignore", category=RuntimeWarning)


# ---- Tests ---------------------------------------------------------------------------


class TestPlotWidgets:
    def test_construction(self) -> None:
        mpl.use("agg")
        plot_widgets = PlotWidgets(
            initial_alpha=0.125,
            initial_enable_cutoff=True,
            initial_graph_type="at_least",
            initial_markers="xo",
            initial_plot_style="default",
        )
        assert plot_widgets.alpha.value == 0.125  # 1/(2**3) # noqa: RUF069
        assert plot_widgets.enable_cutoff.value is True
        assert plot_widgets.graph_type.value == "at_least"
        assert plot_widgets.markers.value == "xo"
        assert plot_widgets.plot_style.value == "default"

    def test_construction_defaults(self) -> None:
        mpl.use("agg")
        plot_widgets = PlotWidgets()
        widget_map = plot_widgets.asdict()
        assert set(widget_map) == {
            "rev_no",
            "alpha",
            "burst_cmap_inner",
            "burst_cmap_link",
            "burst_cmap_outer",
            "burst_cmap_use_midpoints",
            "burst_color_bg",
            "burst_color_bg_trnsp",
            "burst_color_text",
            "burst_columns",
            "burst_swap",
            "burst_zero_fill_normalize",
            "cutoff",
            "enable_cutoff",
            "graph_type",
            "markers",
            "plot_style",
            "resolution",
        }
        assert all(isinstance(widget, widgets.Widget) for widget in widget_map.values())

    def test_construction_warns_on_nonexistant_plot_type(self) -> None:
        mpl.use("agg")
        with pytest.warns(PlotWarning, match=r"\bunrecognized plot style\b"):
            PlotWidgets(initial_plot_style="does not exist")


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


class TestHPlotterChooser:
    def test_construction(self) -> None:
        plot_widgets = PlotWidgets()
        chooser = HPlotterChooser(plot_widgets=plot_widgets)
        assert chooser.hs == ()
        assert set(
            chooser._plotters_by_name.keys()  # noqa: SLF001
        ) == {
            "Line Plot",
            "Horizontal Bar Plots",
            "Burst Plots",
        }
        accordion_widget = chooser._out.children[0]  # noqa: SLF001
        assert isinstance(accordion_widget, widgets.Accordion)
        assert accordion_widget.selected_index is None
        tab_widget = accordion_widget.children[0]
        assert isinstance(tab_widget, widgets.Tab)
        assert tab_widget.selected_index == 0

    def test_construction_histogram_specs(self) -> None:
        chooser = HPlotterChooser([H(6)])
        assert chooser.hs == (("Histogram 1", H(6), None),)

    def test_construction_controls_expanded(self) -> None:
        chooser = HPlotterChooser(controls_expanded=True)
        accordion_widget = chooser._out.children[0]  # noqa: SLF001
        assert isinstance(accordion_widget, widgets.Accordion)
        assert accordion_widget.selected_index == 0

    def test_construction_selected_name(self) -> None:
        chooser = HPlotterChooser(
            plotters_or_factories=(BurstHPlotter, LineHPlotter),
            selected_name="Line Plot",
        )
        accordion_widget = chooser._out.children[0]  # noqa: SLF001
        assert isinstance(accordion_widget, widgets.Accordion)
        tab_widget = accordion_widget.children[0]
        assert isinstance(tab_widget, widgets.Tab)
        assert tab_widget.selected_index == 1

    def test_construction_warns_on_duplicate_plotter_name(self) -> None:
        plotters = LineHPlotter(), LineHPlotter()
        with pytest.warns(PlotWarning, match=r"\bignoring\b.*\bduplicate names\b"):
            HPlotterChooser(plotters_or_factories=plotters)

    def test_construction_fails_on_no_plotters(self) -> None:
        with pytest.raises(ValueError, match=r"^must provide at least one plotter$"):
            HPlotterChooser(plotters_or_factories=())

    def test_construction_fails_on_bad_selected_name(self) -> None:
        plotters = (LineHPlotter(),)
        with pytest.raises(ValueError, match=r"\bdoes not match any plotter$"):
            HPlotterChooser(
                plotters_or_factories=plotters,
                selected_name="no such plotter",
            )

    def test_update_hs_minimal(self) -> None:
        chooser = HPlotterChooser()
        expected = (("Histogram 1", H(6), None),)
        assert chooser.hs != expected
        chooser.update_hs([H(6)])
        assert chooser.hs == expected


def test_limit_for_display_identity() -> None:
    h = H(6)
    assert limit_for_display(h, Fraction(0)) is h


def test_limit_for_display_empty() -> None:
    assert limit_for_display(H({}), Fraction(1, 2**13)) == H({})


def test_limit_for_display_cull_everything() -> None:
    assert limit_for_display(H(6), Fraction(1)) == H({})


def test_limit_for_display_out_of_bounds() -> None:
    with pytest.raises(ValueError, match=r"\bmust be between zero and one\b"):
        assert limit_for_display(H(6), Fraction(-1))

    with pytest.raises(ValueError, match=r"\bmust be between zero and one\b"):
        assert limit_for_display(H(6), Fraction(2))


def test_values_xy_for_graph_type() -> None:
    d6 = H(6)
    d6_outcomes = tuple(d6.outcomes())
    p_3d6 = 3 @ P(d6)
    lo = p_3d6.h(0)
    hi = p_3d6.h(-1)

    lo_outcomes_normal, lo_values_normal = values_xy_for_graph_type(lo, "normal")
    _, hi_values_normal = values_xy_for_graph_type(hi, "normal")
    assert lo_outcomes_normal == d6_outcomes
    assert lo_values_normal == (
        Fraction(91, 216),
        Fraction(61, 216),
        Fraction(37, 216),
        Fraction(19, 216),
        Fraction(7, 216),
        Fraction(1, 216),
    )
    assert hi_values_normal == lo_values_normal[::-1]

    lo_outcomes_at_least, lo_values_at_least = values_xy_for_graph_type(lo, "at_least")
    _, hi_values_at_least = values_xy_for_graph_type(hi, "at_least")
    assert lo_outcomes_at_least == d6_outcomes
    assert lo_values_at_least == (
        Fraction(1),
        Fraction(125, 216),
        Fraction(8, 27),
        Fraction(1, 8),
        Fraction(1, 27),
        Fraction(1, 216),
    )
    assert hi_values_at_least == (
        Fraction(1),
        Fraction(215, 216),
        Fraction(26, 27),
        Fraction(7, 8),
        Fraction(19, 27),
        Fraction(91, 216),
    )

    lo_outcomes_at_most, lo_values_at_most = values_xy_for_graph_type(lo, "at_most")
    _, hi_values_at_most = values_xy_for_graph_type(hi, "at_most")
    assert lo_outcomes_at_most == d6_outcomes
    assert lo_values_at_most == hi_values_at_least[::-1]
    assert hi_values_at_most == lo_values_at_least[::-1]


def test_csv_download_link_emtpy() -> None:
    empty_csv_html = _csv_download_link(())
    assert (
        empty_csv_html
        == '<a download=".csv" href="data:text/csv;base64,T3V0Y29tZQ0K" target="_blank">Download raw data as CSV</a>'
    )


def test_csv_download_link_single_histogram() -> None:
    d6_csv_html = _csv_download_link([("d6", H(6), None)])
    assert (
        d6_csv_html
        == '<a download="d6.csv" href="data:text/csv;base64,T3V0Y29tZSxkNg0KMSwwLjE2NjY2NjY2NjY2NjY2NjY2DQoyLDAuMTY2NjY2NjY2NjY2NjY2NjYNCjMsMC4xNjY2NjY2NjY2NjY2NjY2Ng0KNCwwLjE2NjY2NjY2NjY2NjY2NjY2DQo1LDAuMTY2NjY2NjY2NjY2NjY2NjYNCjYsMC4xNjY2NjY2NjY2NjY2NjY2Ng0K" target="_blank">Download raw data as CSV</a>'
    )


def test_csv_download_link_secondary_histogram_ignored() -> None:
    d8d12_csv_html = _csv_download_link([("d8d12", H(8) + H(12), None)])
    d8d12_vs_2d10_csv_html = _csv_download_link([("d8d12", H(8) + H(12), 2 @ H(10))])
    assert d8d12_csv_html == d8d12_vs_2d10_csv_html


def test_csv_download_link_multiple_histograms() -> None:
    d6_and_d8_csv_html = _csv_download_link([("d6", H(6), None), ("d8", H(8), None)])
    assert (
        d6_and_d8_csv_html
        == '<a download="d6-d8.csv" href="data:text/csv;base64,T3V0Y29tZSxkNixkOA0KMSwwLjE2NjY2NjY2NjY2NjY2NjY2LDAuMTI1DQoyLDAuMTY2NjY2NjY2NjY2NjY2NjYsMC4xMjUNCjMsMC4xNjY2NjY2NjY2NjY2NjY2NiwwLjEyNQ0KNCwwLjE2NjY2NjY2NjY2NjY2NjY2LDAuMTI1DQo1LDAuMTY2NjY2NjY2NjY2NjY2NjYsMC4xMjUNCjYsMC4xNjY2NjY2NjY2NjY2NjY2NiwwLjEyNQ0KNywsMC4xMjUNCjgsLDAuMTI1DQo=" target="_blank">Download raw data as CSV</a>'
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


def test_histogram_specs_to_h_tuples_none() -> None:
    assert _histogram_specs_to_h_tuples([H(6), None, H(6)]) == (
        ("Histogram 1", H(6), None),
        ("", H({}), None),
        ("Histogram 2", H(6), None),
    )
