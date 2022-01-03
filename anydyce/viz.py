# ======================================================================================
# Copyright and other protections apply. Please see the accompanying LICENSE file for
# rights and restrictions governing use of this software. All rights not expressly
# waived or licensed are reserved. If that file is missing or appears to be modified
# from its original, then please contact the author before viewing or using this
# software in any capacity.
# ======================================================================================

from __future__ import annotations

import base64
import csv
import io
import math
import warnings
from enum import Enum, auto
from fractions import Fraction
from itertools import chain, cycle
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    Iterator,
    Optional,
    Sequence,
    Tuple,
    Union,
)

from dyce import H
from dyce.h import HableT
from dyce.lifecycle import experimental
from numerary import RealLike
from numerary.bt import beartype

try:
    import ipywidgets
    from IPython.display import HTML, display
except ImportError:
    warnings.warn(f"ipywidgets not found; some {__name__} APIs disabled")
    ipywidgets = None  # noqa: F811

    def display(*args, **kw) -> Any:
        pass


try:
    import matplotlib.cm
    import matplotlib.colors
    import matplotlib.patheffects
    import matplotlib.pyplot
    import matplotlib.style
    import matplotlib.ticker
    from matplotlib.axes import Axes as AxesT
    from matplotlib.figure import Figure as FigureT
except ImportError:
    warnings.warn(f"matplotlib not found; some {__name__} APIs disabled")
    matplotlib = None  # noqa: F811
    AxesT = Any  # noqa: F811
    FigureT = Any  # noqa: F811

__all__ = ("BreakoutType", "jupyter_visualize")


# ---- Types ---------------------------------------------------------------------------


ColorT = Sequence[float]
ColorListT = Iterable[ColorT]
HLikeT = Union[H, HableT]
HFormatterT = Callable[[RealLike, Fraction, H], str]


class BreakoutType(Enum):
    NONE = 0
    BARH = auto()
    BURST = auto()


# ---- Functions -----------------------------------------------------------------------


def _bar(
    ax: AxesT,
    hs: Sequence[Tuple[str, H, Optional[H]]],
    alpha: float,
    show_shadow: bool,
    **kw,
) -> None:
    plot_bar(ax, tuple((label, h) for label, h, _ in hs), alpha, show_shadow)


def _line(
    ax: AxesT,
    hs: Sequence[Tuple[str, H, Optional[H]]],
    alpha: float,
    show_shadow: bool,
    markers: str,
    **kw,
) -> None:
    plot_line(ax, tuple((label, h) for label, h, _ in hs), alpha, show_shadow, markers)


def _scatter(
    ax: AxesT,
    hs: Sequence[Tuple[str, H, Optional[H]]],
    alpha: float,
    show_shadow: bool,
    markers: str,
    **kw,
) -> None:
    plot_scatter(
        ax, tuple((label, h) for label, h, _ in hs), alpha, show_shadow, markers
    )


# ---- Data ----------------------------------------------------------------------------


DEFAULT_GRAPH_COLOR = "RdYlGn_r"
DEFAULT_TEXT_COLOR = "black"
DEFAULT_BURST_ALPHA = 0.6
DEFAULT_GRAPH_ALPHA = 0.8
_HIDE_LIM = Fraction(1, 2 ** 5)

_DEFAULT_MAIN_PLOT_FUNCS_BY_NAME = {
    "bar": _bar,
    "line": _line,
    "scatter": _scatter,
}


# ---- Functions -----------------------------------------------------------------------


_formatter: HFormatterT


def _outcome_name_formatter(outcome: RealLike, _, __) -> str:
    if hasattr(outcome, "name"):
        return f"{outcome.name}"  # type: ignore [attr-defined]
    else:
        return f"{str(outcome)}"


_formatter = _outcome_name_formatter


def _outcome_name_probability_formatter(
    outcome: RealLike, probability: Fraction, _
) -> str:
    if hasattr(outcome, "name"):
        return f"{outcome.name}\n{float(probability):.2%}"  # type: ignore [attr-defined]
    else:
        return f"{str(outcome)}\n{float(probability):.2%}"


_formatter = _outcome_name_formatter


def _probability_formatter(_, probability: Fraction, __) -> str:
    return f"{float(probability):.2%}"


_formatter = _probability_formatter
del _formatter


@experimental
@beartype
def alphasize(colors: ColorListT, alpha: float) -> ColorListT:
    r"""
    !!! warning "Experimental"

        This function should be considered experimental and may change or disappear in
        future versions.

    Returns a new color list where *alpha* has been applied to each color in *colors*.
    If *alpha* is negative, *colors* is returned unmodified.
    """
    if alpha < 0.0:
        return colors
    else:
        return [(r, g, b, alpha) for r, g, b, _ in colors]


@experimental
@beartype
def cumulative_probability_formatter(
    outcome: RealLike,
    probability: Fraction,
    h: H,
) -> str:
    r"""
    !!! warning "Experimental"

        This function should be considered experimental and may change or disappear in
        future versions.

    Inefficiently (i.e., $O \left( {n} ^ {2} \right)$) calculates cumulative probability
    pairs for *outcome* in *h*. This can be useful for passing as the *outer_formatter*
    value to [``plot_burst``][anydyce.viz.plot_burst].
    """
    le_total, ge_total = Fraction(0), Fraction(1)

    for h_outcome, h_probability in h.distribution():
        le_total += h_probability

        if math.isclose(h_outcome, outcome):
            return f"{outcome} {float(probability):.2%}; ≥{float(le_total):.2%}; ≤{float(ge_total):.2%}"

        ge_total -= h_probability

    return f"{outcome} {float(probability):.2%}"


@experimental
@beartype
def graph_colors(name: str, vals: Iterable, alpha: float = -1.0) -> ColorListT:
    r"""
    !!! warning "Experimental"

        This function should be considered experimental and may change or disappear in
        future versions.

    Returns a color list computed from a [``matplotlib``
    colormap](https://matplotlib.org/stable/gallery/color/colormap_reference.html)
    matching *name*, weighted to to *vals*. The color list and *alpha* are passed
    through [``alphasize``][anydyce.viz.alphasize] before being returned.
    """
    assert matplotlib
    cmap = matplotlib.pyplot.get_cmap(name)
    count = sum(1 for _ in vals)

    if count <= 1:
        colors = cmap((0.5,))
    else:
        colors = cmap([v / (count - 1) for v in range(count - 1, -1, -1)])

    return alphasize(colors, alpha)


@experimental
@beartype
def plot_bar(
    ax: AxesT,
    hs: Sequence[Tuple[str, H]],
    alpha: float = DEFAULT_GRAPH_ALPHA,
    shadow: bool = False,
) -> None:
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(xmax=1))
    width = 0.8
    bar_kw: Dict[str, Any] = dict(alpha=alpha, width=width / len(hs))

    if shadow:
        bar_kw.update(
            dict(
                path_effects=[
                    matplotlib.patheffects.withSimplePatchShadow(),
                    matplotlib.patheffects.Normal(),
                ]
            )
        )

    for i, (label, h) in enumerate(hs):
        # Orient to the middle of each bar ((i + 0.5) ... ) whose width is an even share
        # of the total width (... * width / len(hs) ...) and center the whole cluster of
        # bars around the data point (... - width / 2)
        adj = (i + 0.5) * width / len(hs) - width / 2
        outcomes, probabilities = zip(*h.distribution(rational_t=lambda n, d: n / d))
        ax.bar(
            [outcome + adj for outcome in outcomes],
            probabilities,
            label=label,
            **bar_kw,
        )


@experimental
@beartype
def plot_line(
    ax: AxesT,
    hs: Sequence[Tuple[str, H]],
    alpha: float = DEFAULT_GRAPH_ALPHA,
    shadow: bool = False,
    markers: str = "o",
) -> None:
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(xmax=1))
    plot_kw: Dict[str, Any] = dict(alpha=alpha)

    if shadow:
        plot_kw.update(
            dict(
                path_effects=[
                    matplotlib.patheffects.SimpleLineShadow(),
                    matplotlib.patheffects.Normal(),
                ]
            )
        )

    for (label, h), marker in zip(hs, cycle(markers)):
        outcomes, probabilities = zip(*h.distribution(rational_t=lambda n, d: n / d))
        ax.plot(outcomes, probabilities, label=label, marker=marker, **plot_kw)


@experimental
@beartype
def plot_scatter(
    ax: AxesT,
    hs: Sequence[Tuple[str, H]],
    alpha: float = DEFAULT_GRAPH_ALPHA,
    shadow: bool = False,
    markers: str = "<>v^dPXo",
) -> None:
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(xmax=1))
    scatter_kw: Dict[str, Any] = dict(alpha=alpha)

    if shadow:
        scatter_kw.update(
            dict(
                path_effects=[
                    matplotlib.patheffects.SimpleLineShadow(),
                    matplotlib.patheffects.Normal(),
                ]
            )
        )

    for (label, h), marker in zip(hs, cycle(markers)):
        outcomes, probabilities = zip(*h.distribution(rational_t=lambda n, d: n / d))
        ax.scatter(outcomes, probabilities, label=label, marker=marker, **scatter_kw)


@experimental
@beartype
def plot_burst(
    ax: AxesT,
    h_inner: H,
    h_outer: Optional[H] = None,
    title: Optional[str] = None,
    inner_formatter: HFormatterT = _outcome_name_formatter,
    inner_color: str = DEFAULT_GRAPH_COLOR,
    outer_formatter: Optional[HFormatterT] = None,
    outer_color: Optional[str] = None,
    text_color: str = DEFAULT_TEXT_COLOR,
    alpha: float = DEFAULT_BURST_ALPHA,
) -> None:
    r"""
    !!! warning "Experimental"

        This function should be considered experimental and may change or disappear in
        future versions.

    Creates a dual, overlapping, cocentric pie chart in *ax*, which can be useful for
    visualizing relative probability distributions. See the TODO (was
    countin.md#visualization) for examples.
    """
    assert matplotlib
    h_outer = h_inner if h_outer is None else h_outer

    if outer_formatter is None:
        if h_outer == h_inner:
            outer_formatter = _probability_formatter
        else:
            outer_formatter = inner_formatter

    outer_color = inner_color if outer_color is None else outer_color

    inner = (
        (
            inner_formatter(outcome, probability, h_inner)
            if probability >= _HIDE_LIM
            else "",
            probability,
        )
        for outcome, probability in (h_inner.distribution())
    )

    inner_labels, inner_values = list(zip(*inner))
    inner_colors = graph_colors(inner_color, inner_values, alpha)

    outer = (
        (
            outer_formatter(outcome, probability, h_outer)
            if probability >= _HIDE_LIM
            else "",
            probability,
        )
        for outcome, probability in (h_outer.distribution())
    )

    outer_labels, outer_values = list(zip(*outer))
    outer_colors = graph_colors(outer_color, outer_values, alpha)

    if title:
        ax.set_title(
            title,
            fontdict={"fontweight": "bold", "color": text_color},
            pad=24.0,
        )

    ax.pie(
        outer_values,
        labels=outer_labels,
        radius=1.0,
        labeldistance=1.15,
        startangle=90,
        colors=outer_colors,
        textprops=dict(color=text_color),
        wedgeprops=dict(width=0.8, edgecolor=text_color),
    )
    ax.pie(
        inner_values,
        labels=inner_labels,
        radius=0.85,
        labeldistance=0.7,
        startangle=90,
        colors=inner_colors,
        textprops=dict(color=text_color),
        wedgeprops=dict(width=0.5, edgecolor=text_color),
    )
    ax.set(aspect="equal")


@experimental
@beartype
def plot_burst_subplot(
    h_inner: H,
    h_outer: Optional[H] = None,
    title: Optional[str] = None,
    inner_formatter: HFormatterT = _outcome_name_formatter,
    inner_color: str = DEFAULT_GRAPH_COLOR,
    outer_formatter: Optional[HFormatterT] = None,
    outer_color: Optional[str] = None,
    text_color: str = DEFAULT_TEXT_COLOR,
    alpha: float = DEFAULT_BURST_ALPHA,
) -> Tuple[FigureT, AxesT]:
    r"""
    !!! warning "Experimental"

        This function should be considered experimental and may change or disappear in
        future versions.

    Wrapper around [``plot_burst``][anydyce.viz.plot_burst] that creates a figure, axis
    pair, calls
    [``matplotlib.pyplot.tight_layout``](https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.tight_layout.html),
    and returns the pair.
    """
    assert matplotlib
    fig, ax = matplotlib.pyplot.subplots()
    plot_burst(
        ax,
        h_inner,
        h_outer,
        title,
        inner_formatter,
        inner_color,
        outer_formatter,
        outer_color,
        text_color,
        alpha,
    )

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        matplotlib.pyplot.tight_layout()

    return fig, ax


@experimental
@beartype
def jupyter_visualize(
    histogram_specs: Iterable[
        Union[HLikeT, Tuple[str, HLikeT], Tuple[str, HLikeT, HLikeT]]
    ],
    default_breakout_type: Union[int, BreakoutType] = BreakoutType.NONE,
    default_markers="<>v^dPXo",
    default_main_plot_type: str = "line",
    main_plot_funcs_by_type=_DEFAULT_MAIN_PLOT_FUNCS_BY_NAME,
):
    r"""
    !!! warning "Experimental"

        This function should be considered experimental and may change or disappear in
        future versions.

    Takes a list of one or more *histogram_specs* and produces an interactive
    visualization reminiscent of [AnyDice](https://anydice.com/), but with some extra
    goodies.

    Each item in *histogram_specs* can be an ``dyce.H`` object, a 2-tuple, or a 3-tuple.
    2-tuples are in the format ``#!python (str, H)``, where ``#!python str`` is a name
    or description that will be used to identify the accompanying ``#! H`` object where
    it appears in the visualization. 3-tuples are in the format ``#!python (str, H,
    H)``. The second ``#! H`` object is used for the interior ring in “burst” break-out
    graphs, but otherwise ignored.

    The “Powered by the _Apocalypse_ (PbtA)” example in the introduction notebook should
    give an idea of the effect. (See [Interactive quick
    start](index.md#interactive-quick-start).)

    The *default_breakout_type* parameter indicates which break-out graphs to display
    initially and defaults to [``BreakoutType.NONE``][anydyce.viz.BreakoutType.NONE].
    This only affects the initial display. Break-out graphs can be hidden or changed
    with the interactive controls.
    """
    # TODO(posita): This is a hack-on-a-stream-of-consciousness-until-it-kind-of-works
    # approach. It would be nice if we had some semblance of an architecture, especially
    # one that allowed for better customization building blocks. Right now, it's pretty
    # limited and fragile.
    assert ipywidgets
    assert matplotlib
    assert default_main_plot_type in main_plot_funcs_by_type

    def _display(
        breakouts: BreakoutType,
        scale: float,
        main_plot_type: str,
        main_plot_style: str,
        alpha: float,
        show_shadow: bool,
        markers: str,
        burst_graph_color: str,
        burst_text_color: str,
        burst_bg_color: str,
        burst_swap: bool,
    ) -> None:
        def _hs() -> Iterator[Tuple[str, H, Optional[H]]]:
            label: str
            first_h_like: HLikeT
            second_h_like: Optional[HLikeT]

            for i, thing in enumerate(histogram_specs):
                if isinstance(thing, (H, HableT)):
                    label = f"Histogram {i + 1}"
                    first_h_like = thing
                    second_h_like = None
                else:
                    label, first_h_like = thing[:2]

                    if len(thing) < 3:
                        second_h_like = None
                    else:
                        second_h_like = thing[2]  # type: ignore [misc]

                assert isinstance(label, str)
                first_h = (
                    first_h_like.h()
                    if isinstance(first_h_like, HableT)
                    else first_h_like
                )
                assert isinstance(
                    first_h, H
                ), f"unrecognized histogram type {first_h!r}"
                second_h = (
                    second_h_like.h()
                    if isinstance(second_h_like, HableT)
                    else second_h_like
                )
                assert second_h is None or isinstance(
                    second_h, H
                ), f"unrecognized histogram type {second_h!r}"
                yield label, first_h, second_h

        hs_list = list(_hs())
        unique_outcomes = sorted(
            set(chain.from_iterable(h.outcomes() for _, h, _ in hs_list))
        )

        def _csv_download_link() -> HTML:
            labels = [label for label, _, _ in hs_list]
            raw_buffer = io.BytesIO()
            csv_buffer = io.TextIOWrapper(
                raw_buffer, encoding="utf-8", newline="", write_through=True
            )
            csv_writer = csv.DictWriter(csv_buffer, fieldnames=["Outcome"] + labels)
            csv_writer.writeheader()

            for outcome in unique_outcomes:
                row = {"Outcome": outcome}
                row.update(
                    {
                        label: h[outcome] / h.total
                        for label, h, _ in hs_list
                        if outcome in h
                    }
                )
                csv_writer.writerow(row)

            # Inspiration: <https://medium.com/@charles2588/how-to-upload-download-files-to-from-notebook-in-my-local-machine-6a4e65a15767>
            csv_name = ", ".join(labels)
            csv_name = csv_name if len(labels) <= 32 else (csv_name[:29] + "...")
            payload = base64.standard_b64encode(raw_buffer.getvalue()).decode()

            return HTML(
                f"""
<a download="{csv_name}.csv" href="data:text/csv;base64,{payload}" target="_blank">
Download raw data as CSV
</a>
"""
            )

        display(_csv_download_link())

        matplotlib.rcParams.update(matplotlib.rcParamsDefault)
        matplotlib.pyplot.rcParams["figure.figsize"] = (
            scale,
            scale / 16 * 9,
        )
        matplotlib.style.use(main_plot_style)
        _, ax = matplotlib.pyplot.subplots()

        if main_plot_type == "scatter":
            matplotlib.pyplot.rcParams["lines.markersize"] *= 2

        main_plot_funcs_by_type[main_plot_type](
            ax,
            hs_list,
            alpha=alpha,
            show_shadow=show_shadow,
            markers=markers if markers else " ",
        )
        ax.set_xticks(unique_outcomes)
        ax.legend()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            matplotlib.pyplot.tight_layout()

        matplotlib.pyplot.show()

        burst_graph_color_widget.disabled = True
        burst_text_color_widget.disabled = True
        burst_bg_color_widget.disabled = True
        burst_swap_widget.disabled = True

        if breakouts == BreakoutType.BARH:
            per_outcome_height = 1
            per_breakout_height = 1
            total_height = per_breakout_height * len(hs_list) + sum(
                per_outcome_height
                for _ in chain.from_iterable(h.outcomes() for _, h, _ in hs_list)
            )
            inches_per_height_unit = scale / 64
            matplotlib.pyplot.rcParams["figure.figsize"] = (
                scale,
                total_height * inches_per_height_unit,
            )
            grid = (total_height, 1)
            top = 0
            ax = None
            src_ax = None
            barh_kw: Dict[str, Any] = dict(alpha=alpha)

            if show_shadow:
                barh_kw.update(
                    dict(
                        path_effects=[
                            matplotlib.patheffects.withSimplePatchShadow(),
                            matplotlib.patheffects.Normal(),
                        ]
                    )
                )

            for i, (label, h, _) in enumerate(hs_list):
                outcomes, probabilities = zip(
                    *h.distribution(rational_t=lambda n, d: n / d)
                )
                outcomes = list(outcomes)
                loc = (top, 0)
                rowspan = per_breakout_height + per_outcome_height * len(outcomes)
                top += rowspan

                if src_ax is None:
                    src_ax = ax = matplotlib.pyplot.subplot2grid(
                        grid, loc, rowspan=rowspan
                    )
                else:
                    ax = matplotlib.pyplot.subplot2grid(
                        grid, loc, rowspan=rowspan, sharex=src_ax
                    )

                ax.set_yticks(sorted(outcomes))
                ax.tick_params(labelbottom=False)
                ax.barh(outcomes, probabilities, label=label, **barh_kw)
                ax.legend(loc="upper right")

            if ax is not None:
                ax.tick_params(labelbottom=True)
                ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(xmax=1))

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                matplotlib.pyplot.tight_layout()

            matplotlib.pyplot.show()
        elif breakouts == BreakoutType.BURST:
            cols = 3
            rows = len(hs_list) // cols + (len(hs_list) % cols != 0)
            matplotlib.pyplot.rcParams["figure.figsize"] = (
                scale,
                scale / 16 * 5 * rows,
            )
            matplotlib.pyplot.figure(facecolor=burst_bg_color)
            burst_graph_color_widget.disabled = False
            burst_text_color_widget.disabled = False
            burst_bg_color_widget.disabled = False

            if any(
                h_outer is not None and h_inner != h_outer
                for _, h_inner, h_outer in hs_list
            ):
                burst_swap_widget.disabled = False

            for i, (label, h_inner, h_outer) in enumerate(hs_list):
                plot_burst_kw: Dict[str, Any] = dict(
                    title=label,
                    inner_color=burst_graph_color,
                    text_color=burst_text_color,
                    alpha=alpha,
                )

                if h_outer is not None:
                    if not burst_swap:
                        h_inner, h_outer = h_outer, h_inner

                    plot_burst_kw.update(
                        dict(outer_formatter=_outcome_name_probability_formatter)
                    )

                ax = matplotlib.pyplot.subplot2grid((rows, cols), (i // cols, i % cols))
                plot_burst(
                    ax,
                    h_inner,
                    h_outer,
                    **plot_burst_kw,
                )

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                matplotlib.pyplot.tight_layout()

            matplotlib.pyplot.show()
        else:
            assert (
                breakouts == BreakoutType.NONE
            ), f"unrecognized breakout type {breakouts!r}"

    breakouts_widget = ipywidgets.widgets.RadioButtons(
        value=BreakoutType(default_breakout_type),
        options=(
            ("None", BreakoutType.NONE),
            ("Horizontal Bar", BreakoutType.BARH),
            ("Burst", BreakoutType.BURST),
        ),
    )
    scale_widget = ipywidgets.widgets.FloatSlider(
        value=12,
        min=8,
        max=16,
        step=1,
        continuous_update=False,
        readout_format="0d",
        description="Scale",
    )
    main_plot_type_widget = ipywidgets.widgets.Dropdown(
        value=default_main_plot_type,
        options=main_plot_funcs_by_type.keys(),
        description="Main Type",
    )
    main_plot_style_widget = ipywidgets.widgets.Dropdown(
        value="bmh",
        options=["default"] + matplotlib.style.available,
        description="Main Colors",
    )
    alpha_widget = ipywidgets.widgets.FloatSlider(
        value=0.6,
        min=0.0,
        max=1.0,
        step=0.05,
        continuous_update=False,
        readout_format="0.0%",
        description="Opacity",
    )
    show_shadow_widget = ipywidgets.widgets.Checkbox(
        value=False,
        description="Shadows",
    )
    markers_widget = ipywidgets.widgets.Text(
        value=default_markers,
        description="Markers",
    )
    burst_graph_color_widget = ipywidgets.widgets.Dropdown(
        value=DEFAULT_GRAPH_COLOR,
        options=sorted(matplotlib.cm.cmap_d.keys()),
        disabled=True,
        description="Burst Graph",
    )
    burst_text_color_widget = ipywidgets.widgets.Dropdown(
        value=DEFAULT_TEXT_COLOR,
        options=sorted(sorted(matplotlib.colors.CSS4_COLORS.keys())),
        disabled=True,
        description="Burst Text",
    )
    burst_bg_color_widget = ipywidgets.widgets.Dropdown(
        value="white",
        options=sorted(sorted(matplotlib.colors.CSS4_COLORS.keys())),
        disabled=True,
        description="Burst Bkgrd",
    )
    burst_swap_widget = ipywidgets.widgets.Checkbox(
        value=False,
        description="Burst Swap",
    )

    display(
        ipywidgets.widgets.VBox(
            [
                ipywidgets.widgets.HBox(
                    [
                        ipywidgets.widgets.VBox(
                            [
                                ipywidgets.widgets.Label("Break-out Graphs:"),
                                breakouts_widget,
                                scale_widget,
                            ]
                        ),
                        ipywidgets.widgets.VBox(
                            [
                                main_plot_type_widget,
                                main_plot_style_widget,
                                alpha_widget,
                                show_shadow_widget,
                                markers_widget,
                            ]
                        ),
                        ipywidgets.widgets.VBox(
                            [
                                burst_graph_color_widget,
                                burst_text_color_widget,
                                burst_bg_color_widget,
                                burst_swap_widget,
                            ]
                        ),
                    ]
                ),
                ipywidgets.widgets.interactive_output(
                    _display,
                    {
                        "breakouts": breakouts_widget,
                        "scale": scale_widget,
                        "main_plot_type": main_plot_type_widget,
                        "main_plot_style": main_plot_style_widget,
                        "alpha": alpha_widget,
                        "show_shadow": show_shadow_widget,
                        "markers": markers_widget,
                        "burst_graph_color": burst_graph_color_widget,
                        "burst_text_color": burst_text_color_widget,
                        "burst_bg_color": burst_bg_color_widget,
                        "burst_swap": burst_swap_widget,
                    },
                ),
            ]
        )
    )
