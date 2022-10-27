# ======================================================================================
# Copyright other protections apply. Please see the accompanying LICENSE file for
# rights and restrictions governing use of this software. All rights not expressly
# waived or licensed are reserved. If that file is missing or appears to be modified
# from its original, then please contact the author before viewing or using this
# software in any capacity.
# ======================================================================================

from __future__ import annotations

import asyncio
import base64
import csv
import io
import math
import urllib.parse
import warnings
from abc import abstractmethod, abstractproperty
from collections import Counter
from dataclasses import dataclass, field, fields
from enum import Enum
from fractions import Fraction
from functools import partial, wraps
from itertools import accumulate, chain, cycle, islice
from operator import __add__, __sub__, itemgetter
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    Iterator,
    Mapping,
    Optional,
    Sequence,
    Set,
    Tuple,
    TypedDict,
    Union,
    cast,
)

import matplotlib.colors
import matplotlib.markers
import matplotlib.patheffects
import matplotlib.pyplot
import matplotlib.style
import matplotlib.ticker
from dyce import H
from dyce.h import HableT
from dyce.lifecycle import experimental
from IPython.display import HTML, display
from ipywidgets import widgets
from matplotlib.axes import Axes as Axes
from matplotlib.figure import Figure
from numerary import RealLike
from numerary.bt import beartype

__all__ = (
    "jupyter_visualize",
    "HPlotterChooser",
)


# ---- Types ---------------------------------------------------------------------------


ColorT = Sequence[float]
ColorListT = Iterable[ColorT]
HLikeT = Union[H, HableT]
HFormatterT = Callable[[RealLike, Fraction, H], str]
HPlotterFactoryT = Callable[[], "HPlotter"]


class ImageType(str, Enum):
    PNG = "PNG"
    SVG = "SVG"


class TraditionalPlotType(str, Enum):
    NORMAL = "Normal"
    AT_MOST = "At Most"
    AT_LEAST = "At Least"


class SettingsDict(TypedDict):
    alpha: float
    burst_cmap_inner: str
    burst_cmap_link: bool
    burst_cmap_outer: str
    burst_color_bg: str
    burst_color_bg_trnsp: bool
    burst_color_text: str
    burst_swap: bool
    burst_zero_fill_normalize: bool
    enable_cutoff: bool
    graph_type: TraditionalPlotType
    img_type: ImageType
    markers: str
    plot_style: str
    scale: int
    show_shadow: bool


# ---- Data ----------------------------------------------------------------------------


DEFAULT_CMAP_BURST_INNER = "RdYlGn_r"
DEFAULT_CMAP_BURST_OUTER = "RdYlBu_r"
DEFAULT_COLOR_TEXT = "black"
DEFAULT_COLOR_BG = "white"
DEFAULT_ALPHA = 0.75
_LABEL_LIM = Fraction(1, 2**5)
_CUTOFF_LIM = Fraction(1, 2**13)
_CUTOFF_BASE = 10
_CUTOFF_EXP = 6


_MARKERS = {
    "point": ".",
    "pixel": ",",
    "circle": "o",
    "triangle_down": "v",
    "triangle_up": "^",
    "triangle_left": "<",
    "triangle_right": ">",
    "tri_down": "1",
    "tri_up": "2",
    "tri_left": "3",
    "tri_right": "4",
    "octagon": "8",
    "square": "s",
    "pentagon": "p",
    "plus (filled)": "P",
    "star": "*",
    "hexagon1": "h",
    "hexagon2": "H",
    "plus": "+",
    "x": "x",
    "x (filled)": "X",
    "diamond": "D",
    "thin_diamond": "d",
    "vline": "|",
    "hline": "_",
    "tickleft": matplotlib.markers.TICKLEFT,
    "tickright": matplotlib.markers.TICKRIGHT,
    "tickup": matplotlib.markers.TICKUP,
    "tickdown": matplotlib.markers.TICKDOWN,
    "caretleft": matplotlib.markers.CARETLEFT,
    "caretright": matplotlib.markers.CARETRIGHT,
    "caretup": matplotlib.markers.CARETUP,
    "caretdown": matplotlib.markers.CARETDOWN,
    "caretleft (centered at base)": matplotlib.markers.CARETLEFTBASE,
    "caretright (centered at base)": matplotlib.markers.CARETRIGHTBASE,
    "caretup (centered at base)": matplotlib.markers.CARETUPBASE,
    "caretdown (centered at base)": matplotlib.markers.CARETDOWNBASE,
    "nothing": " ",
}


# ---- Decorators ----------------------------------------------------------------------


def debounce(
    f: Optional[Callable] = None,
    *,
    wait_seconds: float = 0.2,
):
    r"""
    Decorator (inspired by [this
    example](https://ipywidgets.readthedocs.io/en/latest/examples/Widget%20Events.html#Debouncing))
    to postpone a function's execution until after *wait_seconds* have elapsed since the
    last time it was invoked.

    ``` python
    @debounce
    def debounced_func():
        ...

    @debounce(wait_seconds=0.5)  # wait half a second
    def debounced_with_custom_time_func():
        ...
    ```
    """

    def _decorator(f):
        task = None

        async def _sleep_then_call_f(*args, **kw) -> None:
            nonlocal task

            await asyncio.sleep(wait_seconds)
            task = None
            f(*args, **kw)

        @wraps(f)
        def _taskify_sleep_then_call_f(*args, **kw) -> None:
            nonlocal task

            if task is not None:
                task.cancel()

            task = asyncio.create_task(_sleep_then_call_f(*args, **kw))

        return _taskify_sleep_then_call_f

    assert callable(f) or f is None

    return _decorator(f) if callable(f) else _decorator


# ---- Classes -------------------------------------------------------------------------


class Image:
    @beartype
    def __init__(self, file_name: str, file_type: ImageType, data: bytes):
        if file_type is ImageType.PNG:
            self._data = base64.b64encode(data).decode()
            self._mime_pfx = "data:image/png;base64,"
        elif file_type is ImageType.SVG:
            self._data = data.decode()
            self._mime_pfx = "data:image/svg+xml,"
        else:
            assert False, f"unrecognized file type {file_type}"

        if file_name.lower().endswith(file_type.lower()):
            self._file_name = file_name
        else:
            self._file_name = file_name + "." + file_type.lower()

        self._file_type = file_type

    @beartype
    def _repr_png_(self):
        return self._data if self._file_type is ImageType.PNG else None

    @beartype
    def _repr_svg_(self):
        return self._data if self._file_type is ImageType.SVG else None

    @beartype
    def download_link(self) -> str:
        return f'<a download="{self._file_name}" href="{self._mime_pfx}{urllib.parse.quote(self._data)}" target="_blank">Download {self._file_type} image</a>'


@dataclass(frozen=True)
class _PlotWidgetsDataclass:

    # Widget to trigger updates (hack)
    _rev_no: widgets.IntText = field(
        init=False,
        repr=False,
        default_factory=partial(
            widgets.IntText,
            value=0,
            layout={"display": "none"},
        ),
    )

    # Data culling widgets
    cutoff: widgets.FloatLogSlider = field(
        init=False,
        repr=False,
        default_factory=partial(
            widgets.FloatLogSlider,
            value=_CUTOFF_BASE ** -(_CUTOFF_EXP - 2),
            base=_CUTOFF_BASE,
            min=-_CUTOFF_EXP,
            max=-(_CUTOFF_EXP - 3),
            step=0.2,
            continuous_update=False,
            readout_format=".6f",
            description="Threshold",
        ),
    )

    enable_cutoff: widgets.Checkbox = field(
        init=False,
        repr=False,
        default_factory=partial(
            widgets.Checkbox,
            description="Hide Small Outcomes",
        ),
    )

    # Generic display widgets
    scale: widgets.FloatLogSlider = field(
        init=False,
        repr=False,
        default_factory=partial(
            widgets.IntSlider,
            value=12,
            min=8,
            max=16,
            step=1,
            continuous_update=False,
            description="Scale",
        ),
    )

    img_type: widgets.ToggleButtons = field(
        init=False,
        repr=False,
        default_factory=partial(
            widgets.ToggleButtons,
            value=next(iter(ImageType)),
            options=[(img_type.value, img_type) for img_type in ImageType],
            description="Image Format",
            rows=min(len(ImageType), 5),
        ),
    )

    # Burst plot widgets
    burst_cmap_inner: widgets.Dropdown = field(
        init=False,
        repr=False,
        default_factory=partial(
            widgets.Dropdown,
            value=next(iter(matplotlib.colormaps)),
            options=sorted(matplotlib.colormaps.keys()),
            description="Inner Colors",
        ),
    )

    burst_cmap_link: widgets.Checkbox = field(
        init=False,
        repr=False,
        default_factory=partial(
            widgets.Checkbox,
            description="Link Colors",
        ),
    )

    burst_cmap_outer: widgets.Dropdown = field(
        init=False,
        repr=False,
        default_factory=partial(
            widgets.Dropdown,
            value=next(iter(matplotlib.colormaps)),
            options=sorted(matplotlib.colormaps.keys()),
            description="Outer Colors",
        ),
    )

    burst_color_bg: widgets.ColorPicker = field(
        init=False,
        repr=False,
        default_factory=partial(
            widgets.ColorPicker,
            value="white",
            # options=sorted(sorted(matplotlib.colors.CSS4_COLORS.keys())),
            concise=False,
            description="Background",
        ),
    )

    burst_color_bg_trnsp: widgets.Checkbox = field(
        init=False,
        repr=False,
        default_factory=partial(
            widgets.Checkbox,
            value=False,
            description="Transparent",
        ),
    )

    burst_color_text: widgets.ColorPicker = field(
        init=False,
        repr=False,
        default_factory=partial(
            widgets.ColorPicker,
            value="black",
            # options=sorted(sorted(matplotlib.colors.CSS4_COLORS.keys())),
            concise=False,
            description="Text",
        ),
    )

    burst_swap: widgets.Checkbox = field(
        init=False,
        repr=False,
        default_factory=partial(
            widgets.Checkbox,
            description="Swap Inner/Outer Histograms",
            disabled=True,
        ),
    )

    burst_zero_fill_normalize: widgets.Checkbox = field(
        init=False,
        repr=False,
        default_factory=partial(
            widgets.Checkbox,
            description="Normalize Outcomes",
        ),
    )

    # Traditional plot widgets
    alpha: widgets.FloatSlider = field(
        init=False,
        repr=False,
        default_factory=partial(
            widgets.FloatSlider,
            value=1.0,
            min=0.0,
            max=1.0,
            step=0.05,
            continuous_update=False,
            readout_format="0.0%",
            description="Opacity",
        ),
    )

    graph_type: widgets.Select = field(
        init=False,
        repr=False,
        default_factory=partial(
            widgets.Select,
            value=next(iter(TraditionalPlotType)),
            options=[
                (graph_type.value, graph_type) for graph_type in TraditionalPlotType
            ],
            description="Plot Type",
            rows=min(len(TraditionalPlotType), 5),
        ),
    )

    markers: widgets.Text = field(
        init=False,
        repr=False,
        default_factory=partial(
            widgets.Text,
            value=" ",
            description="Markers",
        ),
    )

    plot_style: widgets.Dropdown = field(
        init=False,
        repr=False,
        default_factory=partial(
            widgets.Dropdown,
            value="default",
            options=["default"]
            + [
                style
                for style in matplotlib.style.available
                if not style.startswith("_")
            ],
            description="Style",
        ),
    )

    show_shadow: widgets.Checkbox = field(
        init=False,
        repr=False,
        default_factory=partial(
            widgets.Checkbox,
            description="Shadows",
        ),
    )


class PlotWidgets(_PlotWidgetsDataclass):
    r"""
    !!! warning "Experimental"

        This class should be considered experimental and may change or disappear in
        future versions.
    """

    @beartype
    def __init__(
        self,
        *,
        initial_alpha: float = DEFAULT_ALPHA,
        initial_burst_cmap_inner: str = DEFAULT_CMAP_BURST_INNER,
        initial_burst_cmap_link: bool = True,
        initial_burst_cmap_outer: str = DEFAULT_CMAP_BURST_OUTER,
        initial_burst_color_bg: str = "white",
        initial_burst_color_bg_trnsp: bool = False,
        initial_burst_color_text: str = DEFAULT_COLOR_TEXT,
        initial_burst_swap: bool = False,
        initial_burst_zero_fill_normalize: bool = False,
        initial_enable_cutoff: bool = False,
        initial_graph_type: TraditionalPlotType = TraditionalPlotType.NORMAL,
        initial_img_type: ImageType = ImageType.PNG,
        initial_markers: str = "oX^v><dP",
        initial_plot_style: str = "bmh",
        initial_show_shadow: bool = False,
    ):
        super().__init__()

        if initial_plot_style not in matplotlib.style.available:
            warnings.warn(
                f"unrecognized plot style {initial_plot_style!r}; reverting to 'default'",
                category=RuntimeWarning,
            )
            initial_plot_style = "default"

        self.alpha.value = initial_alpha
        self.burst_cmap_inner.value = initial_burst_cmap_inner
        self.burst_cmap_link.value = initial_burst_cmap_link
        self.burst_cmap_outer.disabled = initial_burst_cmap_link
        self.burst_cmap_outer.value = initial_burst_cmap_outer
        self.burst_color_bg.value = initial_burst_color_bg
        self.burst_color_bg_trnsp.value = initial_burst_color_bg_trnsp
        self.burst_color_text.value = initial_burst_color_text
        self.burst_swap.value = initial_burst_swap
        self.burst_zero_fill_normalize.value = initial_burst_zero_fill_normalize
        self.cutoff.disabled = not initial_enable_cutoff
        self.enable_cutoff.value = initial_enable_cutoff
        self.graph_type.value = initial_graph_type
        self.img_type.value = initial_img_type
        self.markers.value = initial_markers
        self.plot_style.value = initial_plot_style
        self.show_shadow.value = initial_show_shadow

        def _handle_burst_cmap_link(change) -> None:
            self.burst_cmap_outer.disabled = change["new"]

        self.burst_cmap_link.observe(_handle_burst_cmap_link, names="value")

        def _handle_burst_color_bg_trnsp(change) -> None:
            self.burst_color_bg.disabled = change["new"]

        self.burst_color_bg_trnsp.observe(_handle_burst_color_bg_trnsp, names="value")

        def _handle_cutoff(change) -> None:
            self.cutoff.disabled = not change["new"]

        self.enable_cutoff.observe(_handle_cutoff, names="value")

    @beartype
    def asdict(self) -> Dict[str, Any]:
        return dict((field.name, getattr(self, field.name)) for field in fields(self))


class HPlotter:
    r"""
    !!! warning "Experimental"

        This class should be considered experimental and may change or disappear in
        future versions.

    A plotter responsible for laying out control widgets and visualizing data provided
    by primary and optional secondary histograms. (See the
    [*plot* method][anydyce.viz.HPlotter.plot].)
    """

    @abstractproperty
    def NAME(self) -> str:
        r"""
        The display name of the plotter.
        """
        raise NotImplementedError

    @beartype
    def layout(self, plot_widgets: PlotWidgets) -> widgets.Widget:
        r"""
        Takes a set of widgets (*plot_widgets*) and returns a container (layout) widget
        selecting those needed by the plotter.
        """
        return widgets.VBox(
            [
                plot_widgets.enable_cutoff,
                plot_widgets.cutoff,
                plot_widgets.img_type,
                plot_widgets.scale,
            ]
        )

    @abstractmethod
    def plot(
        self,
        hs: Sequence[Tuple[str, H, Optional[H]]],
        settings: SettingsDict,
    ):
        r"""
        Creates and displays a visualization of the provided histograms. *fig* is the
        [``#!python
        matplotlib.figure.Figure``](https://matplotlib.org/stable/api/figure_api.html#matplotlib.figure.Figure)
        in which the visualization should be constructed. *hs* is a sequence of
        three-tuples, a name, a primary histogram, and an optional secondary histogram
        (``#!python None`` if omitted). Plotters should implement this function to
        display at least the primary histogram and visually associate it with the name.
        """
        raise NotImplementedError

    @beartype
    def transparent(self, requested: bool) -> bool:
        r"""
        Returns whether this plotter produces plots which support transparency if
        *requested*. The default implementation always returns ``#!python False``.
        """
        return False


class BarHPlotter(HPlotter):
    r"""
    !!! warning "Experimental"

        This class should be considered experimental and may change or disappear in
        future versions.

    A plotter for creating a single vertical bar plot visualizing all primary
    histograms. Secondary histograms are ignored.
    """

    NAME = "Bar Plot"

    @beartype
    def layout(self, plot_widgets: PlotWidgets) -> widgets.Widget:
        cutoff_layout_widget = super().layout(plot_widgets)

        return widgets.VBox(
            [
                widgets.HBox(
                    [
                        cutoff_layout_widget,
                        plot_widgets.graph_type,
                        widgets.VBox(
                            [
                                plot_widgets.alpha,
                                plot_widgets.plot_style,
                                plot_widgets.show_shadow,
                            ]
                        ),
                    ]
                ),
            ]
        )

    @beartype
    def plot(
        self,
        hs: Sequence[Tuple[str, H, Optional[H]]],
        settings: SettingsDict,
    ) -> None:
        _, ax = matplotlib.pyplot.subplots(
            figsize=(
                settings["scale"],
                settings["scale"] / 16 * 9,
            )
        )

        plot_bar(
            ax,
            tuple((label, h) for label, h, _ in hs),
            alpha=settings["alpha"],
            graph_type=settings["graph_type"],
            shadow=settings["show_shadow"],
        )

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            ax.legend()


class BurstHPlotter(HPlotter):
    r"""
    !!! warning "Experimental"

        This class should be considered experimental and may change or disappear in
        future versions.

    A plotter for creating one burst plot per primary histogram. If provided, associated
    secondary histograms are used for the outer rings.
    """

    NAME = "Burst Plots"

    @beartype
    def layout(self, plot_widgets: PlotWidgets) -> widgets.Widget:
        cutoff_layout_widget = super().layout(plot_widgets)

        return widgets.VBox(
            [
                widgets.HBox(
                    [
                        widgets.VBox(
                            [
                                cutoff_layout_widget,
                            ]
                        ),
                        widgets.VBox(
                            [
                                plot_widgets.burst_swap,
                                plot_widgets.burst_zero_fill_normalize,
                                plot_widgets.burst_cmap_inner,
                                plot_widgets.burst_cmap_outer,
                                plot_widgets.burst_cmap_link,
                            ]
                        ),
                        widgets.VBox(
                            [
                                plot_widgets.alpha,
                                plot_widgets.burst_color_text,
                                plot_widgets.burst_color_bg,
                                plot_widgets.burst_color_bg_trnsp,
                            ]
                        ),
                    ]
                ),
            ]
        )

    @beartype
    def plot(
        self,
        hs: Sequence[Tuple[str, H, Optional[H]]],
        settings: SettingsDict,
    ) -> None:
        cols = 3
        logical_rows = len(hs) // cols + (len(hs) % cols != 0)
        # Height of row gaps in relation to height of figs
        gap_size_ratio = Fraction(1, 5)
        total_gaps = max(0, logical_rows - 1)
        figsize = (
            settings["scale"],
            float(
                settings["scale"] * (logical_rows + total_gaps * gap_size_ratio) / cols
            ),
        )
        matplotlib.pyplot.figure(facecolor=settings["burst_color_bg"], figsize=figsize)
        actual_rows_per_fig = gap_size_ratio.denominator
        actual_rows_per_gap = gap_size_ratio.numerator
        total_actual_rows = (
            logical_rows * actual_rows_per_fig + total_gaps * actual_rows_per_gap
        )

        def _zero_fill_normalize():
            unique_outcomes: Set[RealLike] = set()

            for i, (_, first_h, second_h) in enumerate(hs):
                unique_outcomes.update(first_h)

                if second_h:
                    unique_outcomes.update(second_h)

            for i, (label, first_h, second_h) in enumerate(hs):
                yield (
                    label,
                    first_h.zero_fill(unique_outcomes),
                    None if second_h is None else second_h.zero_fill(unique_outcomes),
                )

        if settings["burst_zero_fill_normalize"]:
            hs = tuple(_zero_fill_normalize())

        for i, (label, h_inner, h_outer) in enumerate(hs):
            plot_burst_kw: Dict[str, Any] = dict(
                title=label,
                inner_cmap=settings["burst_cmap_inner"],
                outer_cmap=settings["burst_cmap_outer"]
                if not settings["burst_cmap_link"]
                else settings["burst_cmap_inner"],
                text_color=settings["burst_color_text"],
                alpha=settings["alpha"],
            )

            if h_outer is not None:
                if settings["burst_swap"]:
                    h_inner, h_outer = h_outer, h_inner

            logical_row = i // cols
            actual_row_start = logical_row * (actual_rows_per_gap + actual_rows_per_fig)
            ax = matplotlib.pyplot.subplot2grid(
                (total_actual_rows, cols),
                (actual_row_start, i % cols),
                rowspan=actual_rows_per_fig,
            )
            plot_burst(
                ax,
                h_inner,
                h_outer,
                **plot_burst_kw,
            )

    @beartype
    def transparent(self, requested: bool) -> bool:
        return requested


class HorizontalBarHPlotter(BarHPlotter):
    r"""
    !!! warning "Experimental"

        This class should be considered experimental and may change or disappear in
        future versions.

    A plotter for creating one horizontal bar plot per primary histogram. Secondary
    histograms are ignored.
    """

    NAME = "Horizontal Bar Plots"

    @beartype
    def plot(
        self,
        hs: Sequence[Tuple[str, H, Optional[H]]],
        settings: SettingsDict,
    ) -> None:
        total_outcomes = sum(
            1 for _ in chain.from_iterable(h.outcomes() for _, h, _ in hs)
        )
        total_height = total_outcomes + 1  # one extra to accommodate the axis
        inches_per_height_unit = settings["scale"] / 64
        figsize = (
            settings["scale"],
            total_height * inches_per_height_unit,
        )
        matplotlib.pyplot.figure(figsize=figsize)
        barh_kw: Dict[str, Any] = dict(alpha=settings["alpha"])

        if settings["show_shadow"]:
            barh_kw.update(
                dict(
                    path_effects=[
                        matplotlib.patheffects.withSimplePatchShadow(),
                        matplotlib.patheffects.Normal(),
                    ]
                )
            )

        plot_style = settings["plot_style"]

        if (
            plot_style in matplotlib.style.library
            and "axes.prop_cycle" in matplotlib.style.library[plot_style]
            and "color" in matplotlib.style.library[plot_style]["axes.prop_cycle"]
        ):
            # Our current style has a cycler with colors, so use it
            cycler = matplotlib.style.library[plot_style]["axes.prop_cycle"]
        else:
            # Revert to the global default
            cycler = matplotlib.rcParams["axes.prop_cycle"]

        color_iter = cycle(cycler.by_key().get("color", (None,)))
        row_start = 0
        first_ax = ax = None

        for i, (label, h, _) in enumerate(hs):
            outcomes, values = values_xy_for_graph_type(h, settings["graph_type"])
            rowspan = len(outcomes)

            if first_ax is None:
                first_ax = ax = matplotlib.pyplot.subplot2grid(
                    (total_height, 1), (row_start, 0), rowspan=rowspan
                )
            else:
                ax = matplotlib.pyplot.subplot2grid(
                    (total_height, 1), (row_start, 0), rowspan=rowspan, sharex=first_ax
                )

            ax.set_yticks(outcomes)
            ax.tick_params(labelbottom=False)
            ax.set_ylim((max(outcomes) + 0.5, min(outcomes) - 0.5))
            ax.barh(outcomes, values, color=next(color_iter), label=label, **barh_kw)
            ax.legend(loc="upper right")
            row_start += rowspan

        if ax is not None:
            ax.tick_params(labelbottom=True)
            ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(xmax=1))


class LineHPlotter(HPlotter):
    r"""
    !!! warning "Experimental"

        This class should be considered experimental and may change or disappear in
        future versions.

    A plotter for creating a single line plot visualizing all primary histograms.
    Secondary histograms are ignored.
    """

    NAME = "Line Plot"

    @beartype
    def layout(self, plot_widgets: PlotWidgets) -> widgets.Widget:
        cutoff_layout_widget = super().layout(plot_widgets)

        return widgets.VBox(
            [
                widgets.HBox(
                    [
                        cutoff_layout_widget,
                        plot_widgets.graph_type,
                        widgets.VBox(
                            [
                                plot_widgets.alpha,
                                plot_widgets.plot_style,
                                plot_widgets.show_shadow,
                                plot_widgets.markers,
                            ]
                        ),
                    ]
                ),
            ]
        )

    @beartype
    def plot(
        self,
        hs: Sequence[Tuple[str, H, Optional[H]]],
        settings: SettingsDict,
    ) -> None:
        _, ax = matplotlib.pyplot.subplots(
            figsize=(
                settings["scale"],
                settings["scale"] / 16 * 9,
            )
        )

        plot_line(
            ax,
            tuple((label, h) for label, h, _ in hs),
            alpha=settings["alpha"],
            graph_type=settings["graph_type"],
            markers=settings["markers"],
            shadow=settings["show_shadow"],
        )

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            ax.legend()


class ScatterHPlotter(LineHPlotter):
    r"""
    !!! warning "Experimental"

        This class should be considered experimental and may change or disappear in
        future versions.

    A plotter for creating a single scatter plot visualizing all primary histograms.
    Secondary histograms are ignored.
    """

    NAME = "Scatter Plot"

    @beartype
    def plot(
        self,
        hs: Sequence[Tuple[str, H, Optional[H]]],
        settings: SettingsDict,
    ) -> None:
        _, ax = matplotlib.pyplot.subplots(
            figsize=(
                settings["scale"],
                settings["scale"] / 16 * 9,
            )
        )

        plot_scatter(
            ax,
            tuple((label, h) for label, h, _ in hs),
            alpha=settings["alpha"],
            graph_type=settings["graph_type"],
            markers=settings["markers"],
            shadow=settings["show_shadow"],
        )

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            ax.legend()


class HPlotterChooser:
    r"""
    !!! warning "Experimental"

        This class should be considered experimental and may change or disappear in
        future versions.

    A controller for coordinating the display of a histogram data set and selection of
    one or more plotters as well as triggering updates in response to either control or
    data changes. All parameters for the
    [initializer][anydyce.viz.HPlotterChooser.__init__] are optional.

    *histogram_specs* is the histogram data set which defaults to an empty tuple. The
    histogram data set can also be replaced vi the
    [``update_hs``][anydyce.viz.HPlotterChooser.update_hs] method.

    Plotter controls (including the selection tabs) are contained within an accordion
    interface. If *controls_expanded* is ``#!python True``, the accordion is initially
    expanded for the user. If it is ``#!python False``, it is initially collapsed.

    *plot_widgets* allows object creators to customize the available control widgets,
    including their initial values. It defaults to ``#!python None`` which results in a
    fresh [``PlotWidgets``][anydyce.viz.PlotWidgets] object being created during
    construction.

    *plotters_or_factories* allows overriding which plotters are available. The default
    is to provide factories for all plotters currently available in ``anydyce``.

    *selected_name* is the name of the plotter to be displayed initially. It must match
    the [``HPlotter.NAME`` property][anydyce.viz.HPlotter.NAME] of an available plotter
    provided by the *plotters_or_factories* parameter.
    """

    @beartype
    def __init__(
        self,
        histogram_specs: Iterable[
            Union[HLikeT, Tuple[str, HLikeT], Tuple[str, HLikeT, Optional[HLikeT]]]
        ] = (),
        *,
        controls_expanded: bool = False,
        plot_widgets: Optional[PlotWidgets] = None,
        plotters_or_factories: Iterable[Union[HPlotter, HPlotterFactoryT]] = (
            BurstHPlotter,
            LineHPlotter,
            BarHPlotter,
            ScatterHPlotter,
            HorizontalBarHPlotter,
        ),
        selected_name: Optional[str] = None,
    ):
        plotters = tuple(
            plotter if isinstance(plotter, HPlotter) else plotter()
            for plotter in plotters_or_factories
        )

        if not plotters:
            raise ValueError("must provide at least one plotter")

        self._plotters_by_name: Mapping[str, HPlotter] = {
            plotter.NAME: plotter for plotter in plotters
        }

        assert self._plotters_by_name

        if selected_name is None:
            selected_name = next(iter(self._plotters_by_name))

        if selected_name is not None and selected_name not in self._plotters_by_name:
            raise ValueError(
                f"selected_name {selected_name!r} does not match any plotter"
            )

        if len(self._plotters_by_name) < len(plotters):
            duplicate_names = ", ".join(
                repr(plotter_name)
                for plotter_name, count in Counter(
                    plotter.NAME for plotter in plotters
                ).items()
                if count > 1
            )
            warnings.warn(
                f"ignoring redundant plotters with duplicate names {duplicate_names}",
                category=RuntimeWarning,
            )

        if plot_widgets is None:
            plot_widgets = PlotWidgets()

        self._plot_widgets = plot_widgets
        self._layouts_by_name: Mapping[str, widgets.Widget] = {}

        for plotter_name, plotter in self._plotters_by_name.items():
            self._layouts_by_name[plotter_name] = plotter.layout(plot_widgets)

        self._hs: Tuple[Tuple[str, H, Optional[H]], ...] = ()
        self._hs_culled: Tuple[Tuple[str, H, Optional[H]], ...] = ()
        self._cutoff: Optional[float] = None
        self._csv_download_link = ""
        self.update_hs(histogram_specs)

        self._selected_plotter: Optional[HPlotter]

        tab_names = tuple(self._plotters_by_name.keys())

        chooser_tab = widgets.Tab(
            children=tuple(self._layouts_by_name.values()),
            selected_index=0
            if selected_name is None
            else tab_names.index(selected_name),
            titles=tab_names,
        )

        def _handle_tab(change) -> None:
            assert change["name"] == "selected_index"
            self._selected_plotter = next(
                islice(self._plotters_by_name.values(), change["new"], None)
            )
            self._trigger_update()

        chooser_tab.observe(_handle_tab, names="selected_index")

        self._selected_plotter = next(
            islice(self._plotters_by_name.values(), chooser_tab.selected_index, None)
        )

        self._out = widgets.VBox(
            [
                widgets.Accordion(
                    children=[chooser_tab],
                    titles=["Plot Controls"],
                    selected_index=0 if controls_expanded else None,
                ),
                widgets.interactive_output(self.plot, self._plot_widgets.asdict()),
            ]
        )

    @beartype
    def interact(self) -> None:
        r"""
        Displays the container responsible for selecting which plotter is used.
        """
        display(self._out)

    @beartype
    # @debounce
    def plot(self, **kw) -> None:
        r"""
        Callback for updating the visualization in response to configuration or data
        changes. *settings* are the current values from all control widgets. (See
        [``PlotWidgets``][anydyce.viz.PlotWidgets].)
        """
        settings = cast(SettingsDict, kw)
        cutoff = (
            self._plot_widgets.cutoff.value
            if self._plot_widgets.enable_cutoff.value
            else None
        )

        if self._cutoff != cutoff:
            self._cutoff = cutoff
            self._cull_data()

        with matplotlib.style.context(settings["plot_style"]):
            if self._selected_plotter is not None:
                self._selected_plotter.plot(self._hs_culled, settings)
                transparent = self._selected_plotter.transparent(
                    settings["burst_color_bg_trnsp"]
                )
            else:
                transparent = False

            buf = io.BytesIO()
            matplotlib.pyplot.savefig(
                buf,
                bbox_inches="tight",
                format=settings["img_type"],
                transparent=transparent,
            )
            img_name = "-".join(label for label, _, _ in self._hs)
            img = Image(img_name, settings["img_type"], buf.getvalue())
            display(HTML(f"{self._csv_download_link} | {img.download_link()}"))
            display(img)
            matplotlib.pyplot.clf()
            matplotlib.pyplot.close()

    @beartype
    def update_hs(
        self,
        histogram_specs: Iterable[
            Union[HLikeT, Tuple[str, HLikeT], Tuple[str, HLikeT, Optional[HLikeT]]]
        ],
    ) -> None:
        r"""
        Triggers an update to the histogram data. *histogram_specs* is an iterable of either
        a single [``HLikeT``][anydyce.viz.HLikeT] object, a two-tuple of a name and a
        primary ``HLikeT`` object, or a three-tuple of a name, a primary ``HLikeT``
        object, and an optional secondary ``HLikeT`` object (``#!python None`` if
        omitted).
        """
        self._hs = _histogram_specs_to_h_tuples(histogram_specs, cutoff=None)
        self._csv_download_link = _csv_download_link(self._hs)

        self._plot_widgets.burst_swap.disabled = all(
            h_outer is None or h_inner == h_outer for _, h_inner, h_outer in self._hs
        )

        self._cull_data()
        self._trigger_update()

    @beartype
    def _cull_data(self) -> None:
        self._hs_culled = _histogram_specs_to_h_tuples(self._hs, self._cutoff)

    @beartype
    def _trigger_update(self) -> None:
        self._plot_widgets._rev_no.value += 1


# ---- Functions -----------------------------------------------------------------------


_formatter: HFormatterT


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

    Formatter for use with [``plot_burst``][anydyce.viz.plot_burst] to inefficiently
    (i.e., $O \left( {n} ^ {2} \right)$) calculate and format cumulative probability
    pairs for *outcome* in *h*.
    """
    le_total, ge_total = Fraction(0), Fraction(1)

    for h_outcome, h_probability in h.distribution():
        le_total += h_probability

        if math.isclose(h_outcome, outcome):
            return f"{outcome} {float(probability):.2%}; ≥{float(le_total):.2%}; ≤{float(ge_total):.2%}"

        ge_total -= h_probability

    return f"{outcome} {float(probability):.2%}"


_formatter = cumulative_probability_formatter


@experimental
@beartype
def outcome_name_formatter(outcome: RealLike, _, __) -> str:
    r"""
    !!! warning "Experimental"

        This function should be considered experimental and may change or disappear in
        future versions.

    Formatter for use with [``plot_burst``][anydyce.viz.plot_burst] to format each
    *outcome*. If *outcome* has a *name* attribute (e.g., as with an ``#!python Enum``),
    that is used. Otherwise *outcome* is passed to ``#!pythonn str`` and the result is
    used.
    """
    if hasattr(outcome, "name"):
        return f"{outcome.name}"  # type: ignore [attr-defined]
    else:
        return f"{str(outcome)}"


_formatter = outcome_name_formatter


@experimental
@beartype
def outcome_name_probability_formatter(
    outcome: RealLike, probability: Fraction, __
) -> str:
    r"""
    !!! warning "Experimental"

        This function should be considered experimental and may change or disappear in
        future versions.

    Formatter for use with [``plot_burst``][anydyce.viz.plot_burst] to display each
    outcome and probability (separated by a newline). If *outcome* has a *name*
    attribute (e.g., as with an ``#!python Enum``), that is used. Otherwise *outcome* is
    passed to ``#!pythonn str`` and the result is used. *probability* is passed to
    ``#!python float`` and formatted to two decimal places.
    """
    if hasattr(outcome, "name"):
        return f"{outcome.name}\n{float(probability):.2%}"  # type: ignore [attr-defined]
    else:
        return f"{str(outcome)}\n{float(probability):.2%}"


_formatter = outcome_name_probability_formatter


@experimental
@beartype
def probability_formatter(_, probability: Fraction, __) -> str:
    r"""
    !!! warning "Experimental"

        This function should be considered experimental and may change or disappear in
        future versions.

    Formatter for use with [``plot_burst``][anydyce.viz.plot_burst] to display the
    probability for each outcome (but not the outcome itself). *probability* is passed
    to ``#!python float`` and formatted to two decimal places.
    """
    return f"{float(probability):.2%}"


_formatter = probability_formatter
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
def graph_colors(
    cmap: Union[str, matplotlib.colors.Colormap],
    vals: Iterable,
    alpha: float = -1.0,
) -> ColorListT:
    r"""
    !!! warning "Experimental"

        This function should be considered experimental and may change or disappear in
        future versions.

    Returns a color list computed from *cmap*, weighted to to *vals*. If *cmap* is a
    string, it must reference a [``matplotlib``
    colormap](https://matplotlib.org/stable/gallery/color/colormap_reference.html). The
    color list and *alpha* are passed through [``alphasize``][anydyce.viz.alphasize]
    before being returned.
    """
    cmap = matplotlib.pyplot.get_cmap(cmap) if isinstance(cmap, str) else cmap
    count = sum(1 for _ in vals)

    if count <= 1:
        colors = cmap((0.5,))
    else:
        colors = cmap([v / (count - 1) for v in range(count - 1, -1, -1)])

    return alphasize(colors, alpha)


@experimental
@beartype
def limit_for_display(h: H, cutoff) -> H:
    r"""
    !!! warning "Experimental"

        This function should be considered experimental and may change or disappear in
        future versions.

    Discards outcomes in *h*, starting with the smallest counts as long as the total
    discarded in proportion to ``#!python h.total`` does not exceed *cutoff*. This can
    be useful in speeding up plots where there are large number of negligible
    probabilities.

    ``` python
    >>> from anydyce.viz import limit_for_display
    >>> from dyce import H
    >>> from fractions import Fraction
    >>> h = H({1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6})
    >>> h.total
    21
    >>> limit_for_display(h, cutoff=Fraction(5, 21))
    H({3: 3, 4: 4, 5: 5, 6: 6})
    >>> limit_for_display(h, cutoff=Fraction(6, 21))
    H({4: 4, 5: 5, 6: 6})

    ```
    """
    if cutoff < 0 or cutoff > 1:
        raise ValueError(f"cutoff ({cutoff}) must be between zero and one, inclusive")

    cutoff_count = int(cutoff * h.total)

    if cutoff_count == 0:
        return h

    def _cull() -> Iterator[Tuple[RealLike, int]]:
        so_far = 0

        for outcome, count in sorted(h.items(), key=itemgetter(1)):
            so_far += count

            if so_far > cutoff_count:
                yield outcome, count

    return H(_cull())


@experimental
@beartype
def values_xy_for_graph_type(
    h: H, graph_type: TraditionalPlotType
) -> Tuple[Tuple[RealLike, ...], Tuple[float, ...]]:
    outcomes, probabilities = h.distribution_xy()

    if graph_type is TraditionalPlotType.AT_LEAST:
        probabilities = tuple(accumulate(probabilities, __sub__, initial=1.0))[:-1]
    elif graph_type is TraditionalPlotType.AT_MOST:
        probabilities = tuple(accumulate(probabilities, __add__, initial=0.0))[1:]
    elif graph_type is TraditionalPlotType.NORMAL:
        pass
    else:
        assert False, f"unrecognized graph type {graph_type}"

    return outcomes, probabilities


@experimental
@beartype
def plot_bar(
    ax: Axes,
    hs: Sequence[Tuple[str, H]],
    graph_type: TraditionalPlotType = TraditionalPlotType.NORMAL,
    alpha: float = DEFAULT_ALPHA,
    shadow: bool = False,
) -> None:
    r"""
    !!! warning "Experimental"

        This function should be considered experimental and may change or disappear in
        future versions.

    Plots a bar graph of *hs* using
    [*ax*](https://matplotlib.org/stable/api/axes_api.html#the-axes-class) with *alpha*
    and *shadow*. *hs* is a sequence of two-tuples (pairs) of strings (labels) and ``H``
    objects. Bars are interleaved and non-overlapping, so this is best suited to plots
    where *hs* contains a small number of histograms.
    """
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(xmax=1))
    width = 0.8
    bar_kw: Dict[str, Any] = dict(alpha=alpha)

    if hs:
        bar_kw.update(dict(width=width / len(hs)))

    if shadow:
        bar_kw.update(
            dict(
                path_effects=[
                    matplotlib.patheffects.withSimplePatchShadow(),
                    matplotlib.patheffects.Normal(),
                ]
            )
        )

    unique_outcomes = sorted(set(chain.from_iterable(h.outcomes() for _, h in hs)))

    if hs:
        ax.set_xticks(unique_outcomes)
        ax.set_xlim((min(unique_outcomes) - 1.0, max(unique_outcomes) + 1.0))

    for i, (label, h) in enumerate(hs):
        # Orient to the middle of each bar ((i + 0.5) ... ) whose width is an even share
        # of the total width (... * width / len(hs) ...) and center the whole cluster of
        # bars around the data point (... - width / 2)
        adj = (i + 0.5) * width / len(hs) - width / 2
        outcomes, values = values_xy_for_graph_type(h, graph_type)
        ax.bar(
            [outcome + adj for outcome in outcomes],
            values,
            label=label,
            **bar_kw,
        )


@experimental
@beartype
def plot_line(
    ax: Axes,
    hs: Sequence[Tuple[str, H]],
    graph_type: TraditionalPlotType = TraditionalPlotType.NORMAL,
    alpha: float = DEFAULT_ALPHA,
    shadow: bool = False,
    markers: str = "o",
) -> None:
    r"""
    !!! warning "Experimental"

        This function should be considered experimental and may change or disappear in
        future versions.

    Plots a line graph of *hs* using
    [*ax*](https://matplotlib.org/stable/api/axes_api.html#the-axes-class) with *alpha*
    and *shadow*. *hs* is a sequence of two-tuples (pairs) of strings (labels) and
    ``#!python dyce.H`` objects. *markers* is cycled through when creating each line.
    For example, if *markers* is ``#!python "o+"``, the first histogram in *hs* will be
    plotted with a circle, the second will be plotted with a plus, the third will be
    plotted with a circle, the fourth will be plotted with a plus, and so on.
    """
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

    unique_outcomes = sorted(set(chain.from_iterable(h.outcomes() for _, h in hs)))

    if hs:
        ax.set_xticks(unique_outcomes)
        ax.set_xlim((min(unique_outcomes) - 0.5, max(unique_outcomes) + 0.5))

    for (label, h), marker in zip(hs, cycle(markers if markers else " ")):
        outcomes, values = values_xy_for_graph_type(h, graph_type)
        ax.plot(outcomes, values, label=label, marker=marker, **plot_kw)


@experimental
@beartype
def plot_scatter(
    ax: Axes,
    hs: Sequence[Tuple[str, H]],
    graph_type: TraditionalPlotType = TraditionalPlotType.NORMAL,
    alpha: float = DEFAULT_ALPHA,
    shadow: bool = False,
    markers: str = "<>v^dPXo",
) -> None:
    r"""
    !!! warning "Experimental"

        This function should be considered experimental and may change or disappear in
        future versions.

    Plots a scatter graph of *hs* using
    [*ax*](https://matplotlib.org/stable/api/axes_api.html#the-axes-class) with *alpha*
    and *shadow*. *hs* is a sequence of two-tuples (pairs) of strings (labels) and
    ``dyce.H`` objects. *markers* is cycled through when creating each line. For
    example, if *markers* is ``#!python "o+"``, the first histogram in *hs* will be
    plotted with a circle, the second will be plotted with a plus, the third will be
    plotted with a circle, the fourth will be plotted with a plus, and so on.
    """
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

    unique_outcomes = sorted(set(chain.from_iterable(h.outcomes() for _, h in hs)))

    if hs:
        ax.set_xticks(unique_outcomes)
        ax.set_xlim((min(unique_outcomes) - 0.5, max(unique_outcomes) + 0.5))

    for (label, h), marker in zip(hs, cycle(markers if markers else " ")):
        outcomes, values = values_xy_for_graph_type(h, graph_type)
        ax.scatter(outcomes, values, label=label, marker=marker, **scatter_kw)


@experimental
@beartype
def plot_burst(
    ax: Axes,
    h_inner: H,
    h_outer: Optional[H] = None,
    title: Optional[str] = None,
    inner_formatter: HFormatterT = outcome_name_formatter,
    inner_cmap: Union[str, matplotlib.colors.Colormap] = DEFAULT_CMAP_BURST_INNER,
    outer_formatter: Optional[HFormatterT] = None,
    outer_cmap: Union[str, matplotlib.colors.Colormap, None] = None,
    text_color: str = DEFAULT_COLOR_TEXT,
    alpha: float = DEFAULT_ALPHA,
) -> None:
    r"""
    !!! warning "Experimental"

        This function should be considered experimental and may change or disappear in
        future versions.

    Creates a dual, overlapping, cocentric pie chart in
    [*ax*](https://matplotlib.org/stable/api/axes_api.html#the-axes-class), which can be
    useful for visualizing relative probability distributions. Examples can be found in
    [Additional interfaces](index.md#additional-interfaces).
    """
    h_outer = h_inner if h_outer is None else h_outer

    if outer_formatter is None:
        if h_outer == h_inner:
            outer_formatter = probability_formatter
        else:
            outer_formatter = inner_formatter

    outer_cmap = inner_cmap if outer_cmap is None else outer_cmap

    inner = (
        (
            inner_formatter(outcome, probability, h_inner)
            if probability >= _LABEL_LIM
            else "",
            probability,
        )
        for outcome, probability in (h_inner.distribution())
    )

    inner_labels, inner_values = list(zip(*inner))
    inner_colors = graph_colors(inner_cmap, inner_values, alpha)

    outer = (
        (
            outer_formatter(outcome, probability, h_outer)
            if probability >= _LABEL_LIM
            else "",
            probability,
        )
        for outcome, probability in (h_outer.distribution())
    )

    outer_labels, outer_values = list(zip(*outer))
    outer_colors = graph_colors(outer_cmap, outer_values, alpha)

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
    inner_formatter: HFormatterT = outcome_name_formatter,
    inner_cmap: Union[str, matplotlib.colors.Colormap] = DEFAULT_CMAP_BURST_INNER,
    outer_formatter: Optional[HFormatterT] = None,
    outer_cmap: Union[str, matplotlib.colors.Colormap, None] = None,
    text_color: str = DEFAULT_COLOR_TEXT,
    alpha: float = DEFAULT_ALPHA,
) -> Tuple[Figure, Axes]:
    r"""
    !!! warning "Experimental"

        This function should be considered experimental and may change or disappear in
        future versions.

    Wrapper around [``plot_burst``][anydyce.viz.plot_burst] that creates a figure, axis
    pair, calls
    [``matplotlib.pyplot.tight_layout``](https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.tight_layout.html),
    and returns the pair.
    """
    fig, ax = matplotlib.pyplot.subplots()
    plot_burst(
        ax,
        h_inner,
        h_outer,
        title,
        inner_formatter,
        inner_cmap,
        outer_formatter,
        outer_cmap,
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
        Union[HLikeT, Tuple[str, HLikeT], Tuple[str, HLikeT, Optional[HLikeT]]]
    ],
    *,
    controls_expanded: bool = True,
    initial_alpha: float = DEFAULT_ALPHA,
    initial_burst_cmap_inner: str = DEFAULT_CMAP_BURST_INNER,
    initial_burst_cmap_link: bool = True,
    initial_burst_cmap_outer: str = DEFAULT_CMAP_BURST_OUTER,
    initial_burst_color_bg: str = "white",
    initial_burst_color_bg_trnsp: bool = False,
    initial_burst_color_text: str = DEFAULT_COLOR_TEXT,
    initial_burst_swap: bool = False,
    initial_burst_zero_fill_normalize: bool = False,
    initial_enable_cutoff: bool = False,
    initial_graph_type: TraditionalPlotType = TraditionalPlotType.NORMAL,
    initial_img_type: ImageType = ImageType.PNG,
    initial_markers: str = "oX^v><dP",
    initial_plot_style: str = "bmh",
    initial_show_shadow: bool = False,
    selected_name: Optional[str] = None,
):
    r"""
    !!! warning "Experimental"

        This function should be considered experimental and may change or disappear in
        future versions.

    Takes a list of one or more *histogram_specs* and produces an interactive
    visualization reminiscent of [AnyDice](https://anydice.com/), but with some extra
    goodies.

    Each item in *histogram_specs* can be a ``#!python dyce.H`` object, a 2-tuple, or a
    3-tuple. 2-tuples are in the format ``#!python (str, H)``, where ``#!python str`` is
    a name or description that will be used to identify the accompanying ``#!python H``
    object where it appears in the visualization. 3-tuples are in the format ``#!python
    (str, H, H)``. The second ``#!python H`` object is used for the interior ring in
    “burst” break-out graphs, but otherwise ignored.

    The “Powered by the _Apocalypse_ (PbtA)” example in the introduction notebook should
    give an idea of the effect. (See [Interactive quick
    start](index.md#interactive-quick-start).)

    Parameters have the same meanings as with
    [``HPlotterChooser``][anydyce.viz.HPlotterChooser] and
    [``PlotWidgets``][anydyce.viz.PlotWidgets].
    """
    plotter_chooser = HPlotterChooser(
        histogram_specs,
        plot_widgets=PlotWidgets(
            initial_alpha=initial_alpha,
            initial_burst_cmap_inner=initial_burst_cmap_inner,
            initial_burst_cmap_link=initial_burst_cmap_link,
            initial_burst_cmap_outer=initial_burst_cmap_outer,
            initial_burst_color_bg=initial_burst_color_bg,
            initial_burst_color_bg_trnsp=initial_burst_color_bg_trnsp,
            initial_burst_color_text=initial_burst_color_text,
            initial_burst_swap=initial_burst_swap,
            initial_burst_zero_fill_normalize=initial_burst_zero_fill_normalize,
            initial_enable_cutoff=initial_enable_cutoff,
            initial_graph_type=initial_graph_type,
            initial_img_type=initial_img_type,
            initial_markers=initial_markers,
            initial_plot_style=initial_plot_style,
            initial_show_shadow=initial_show_shadow,
        ),
        selected_name=selected_name,
    )

    plotter_chooser.interact()


@beartype
def _csv_download_link(hs: Sequence[Tuple[str, H, Optional[H]]]) -> str:
    unique_outcomes = sorted(set(chain.from_iterable(h.outcomes() for _, h, _ in hs)))
    labels = [label for label, _, _ in hs]
    raw_buffer = io.BytesIO()
    csv_buffer = io.TextIOWrapper(
        raw_buffer, encoding="utf-8", newline="", write_through=True
    )
    csv_writer = csv.DictWriter(csv_buffer, fieldnames=["Outcome"] + labels)
    csv_writer.writeheader()

    for outcome in unique_outcomes:
        row = {"Outcome": outcome}
        row.update({label: h[outcome] / h.total for label, h, _ in hs if outcome in h})
        csv_writer.writerow(row)

    # Inspiration: <https://medium.com/@charles2588/how-to-upload-download-files-to-from-notebook-in-my-local-machine-6a4e65a15767>
    csv_name = "-".join(labels)
    csv_name = csv_name if len(labels) <= 32 else (csv_name[:29] + "...")
    payload = base64.standard_b64encode(raw_buffer.getvalue()).decode()

    return f'<a download="{csv_name}.csv" href="data:text/csv;base64,{payload}" target="_blank">Download raw data as CSV</a>'


@beartype
def _histogram_specs_to_h_tuples(
    histogram_specs: Iterable[
        Union[HLikeT, Tuple[str, HLikeT], Tuple[str, HLikeT, Optional[HLikeT]]]
    ],
    cutoff: Optional[float] = None,
) -> Tuple[Tuple[str, H, Optional[H]], ...]:
    h_specs = []

    if cutoff is None:
        cutoff_frac = _CUTOFF_LIM
    else:
        cutoff_frac = Fraction(cutoff).limit_denominator(_CUTOFF_BASE**_CUTOFF_EXP)

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

            if len(thing) >= 3:
                # TODO(posita): See <https://github.com/python/mypy/issues/1178>
                second_h_like = thing[2]  # type: ignore [misc]
            else:
                second_h_like = None

        assert isinstance(label, str)
        first_h = limit_for_display(
            first_h_like.h() if isinstance(first_h_like, HableT) else first_h_like,
            cutoff_frac,
        )

        if second_h_like is None:
            second_h = None
        else:
            second_h = limit_for_display(
                second_h_like.h()
                if isinstance(second_h_like, HableT)
                else second_h_like,
                cutoff_frac,
            )

        h_specs.append((label, first_h, second_h))

    return tuple(h_specs)
