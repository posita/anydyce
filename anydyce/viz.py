# ======================================================================================
# Copyright and other protections apply. Please see the accompanying LICENSE file for
# rights and restrictions governing use of this software. All rights not expressly
# waived or licensed are reserved. If that file is missing or appears to be modified
# from its original, then please contact the author before viewing or using this
# software in any capacity.
# ======================================================================================

import base64
import csv
import io
import urllib.parse
import warnings
from abc import abstractmethod
from collections import Counter
from collections.abc import Callable, Generator, Iterable, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field, fields
from enum import StrEnum
from fractions import Fraction
from functools import partial
from itertools import accumulate, chain, cycle, islice
from operator import __add__, __sub__, itemgetter
from typing import (
    Any,
    TypedDict,
    TypeVar,
    cast,
)

import matplotlib as mpl
from dyce import H, HableT
from dyce.lifecycle import experimental
from dyce.viz import (
    _DEFAULT_ALPHA,
    _DEFAULT_MARKERS,
    GraphTypeT,
    plot_bar,
    plot_burst,
    plot_line,
)
from IPython.display import HTML, display
from ipywidgets import widgets  # type: ignore[import-untyped]
from matplotlib import colors as mcolors
from matplotlib import markers as mmarkers
from matplotlib import pyplot as plt
from matplotlib import style as mstyle
from matplotlib import ticker as mticker
from matplotlib.axes import Axes as Axes
from traitlets import TraitError

__all__ = (
    "HPlotterChooser",
    "PlotWidgets",
    "jupyter_visualize",
)


# ---- Types ---------------------------------------------------------------------------


_T = TypeVar("_T")
_ChangeT = Mapping[str, Any]
ColorT = tuple[float, float, float, float]
ColorListT = Sequence[ColorT]
HLikeT = H | HableT
HPlotterFactoryT = Callable[[], "HPlotter"]


def _first_of(i: Iterable[_T]) -> _T:
    return next(iter(i))


_DEFAULT_GRAPH_TYPE = _first_of(GraphTypeT.__args__)  # type: ignore[attr-defined]
_CMAP_NAMES = tuple(sorted(mpl.colormaps.keys()))


class PlotWarning(UserWarning):
    r"""
    Issued when a plotter encounters unusual but non-fatal circumstances.
    """


class ImageType(StrEnum):
    PNG = "PNG"
    SVG = "SVG"


class SettingsDict(TypedDict):
    alpha: float
    burst_cmap_inner: str
    burst_cmap_link: bool
    burst_cmap_outer: str
    burst_cmap_use_mpts: bool
    burst_color_bg: str
    burst_color_bg_trnsp: bool
    burst_color_text: str
    burst_columns: int
    burst_swap: bool
    burst_zero_fill_normalize: bool
    enable_cutoff: bool
    graph_type: GraphTypeT
    img_type: ImageType
    markers: str
    plot_style: str
    resolution: int


# ---- Data ----------------------------------------------------------------------------

_DEFAULT_COLS_BURST = 3
_DEFAULT_RESOLUTION = 12
_CUTOFF_BASE = 10
_CUTOFF_EXP = 6


def _get_param_for_style(style_name: str, param_name: str) -> Any:  # noqa: ANN401
    style = mstyle.library.get(style_name)
    default_param = mpl.rcParams[param_name]
    return style.get(param_name, default_param) if style else default_param


_DEFAULT_MPL_STYLE = "default"
_DEFAULT_PLOT_STYLE = "bmh"
_DEFAULT_CMAP = _DEFAULT_COMPARE_CMAP = _get_param_for_style(
    _DEFAULT_PLOT_STYLE, "image.cmap"
)
_DEFAULT_BURST_COLOR_TEXT = _get_param_for_style(_DEFAULT_PLOT_STYLE, "text.color")
_DEFAULT_BURST_COLOR_BG = _get_param_for_style(_DEFAULT_PLOT_STYLE, "figure.facecolor")

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
    "tickleft": mmarkers.TICKLEFT,
    "tickright": mmarkers.TICKRIGHT,
    "tickup": mmarkers.TICKUP,
    "tickdown": mmarkers.TICKDOWN,
    "caretleft": mmarkers.CARETLEFT,
    "caretright": mmarkers.CARETRIGHT,
    "caretup": mmarkers.CARETUP,
    "caretdown": mmarkers.CARETDOWN,
    "caretleft (centered at base)": mmarkers.CARETLEFTBASE,
    "caretright (centered at base)": mmarkers.CARETRIGHTBASE,
    "caretup (centered at base)": mmarkers.CARETUPBASE,
    "caretdown (centered at base)": mmarkers.CARETDOWNBASE,
    "nothing": " ",
}


# ---- Classes -------------------------------------------------------------------------


class Image:
    r"""
    Abstraction to support downloading images of varying types.

    The [initializer][anydyce.viz.Image.__init__] requires several parameters.
    *file_name* is the name of the file to be downloaded. *file_type* is the type of the
    image data. *data* is the image data.

    !!! warning

        This is a relatively dumb class. It is left to the caller to ensure that
        *file_type* accurately describes *data*.
    """

    def __init__(self, file_name: str, file_type: ImageType, data: bytes) -> None:
        if file_type is ImageType.PNG:
            self._data = base64.b64encode(data).decode()
            self._mime_pfx = "data:image/png;base64,"
        elif file_type is ImageType.SVG:
            self._data = data.decode()
            self._mime_pfx = "data:image/svg+xml,"
        else:
            assert False, f"unrecognized file type {file_type}"  # noqa: B011, PT015

        if file_name.lower().endswith(file_type.lower()):
            self._file_name = file_name
        else:
            self._file_name = file_name + "." + file_type.lower()

        self._file_type = file_type

    def _repr_png_(self) -> str | None:  # noqa: PLW3201
        r"""
        [Rich
        display](https://ipython.readthedocs.io/en/stable/config/integrating.html#integrating-rich-display)
        hook method used by IPython to display PNG images.
        """
        return self._data if self._file_type is ImageType.PNG else None

    def _repr_svg_(self) -> str | None:  # noqa: PLW3201
        r"""
        [Rich
        display](https://ipython.readthedocs.io/en/stable/config/integrating.html#integrating-rich-display)
        hook method used by IPython to display SVG images.
        """
        return self._data if self._file_type is ImageType.SVG else None

    def download_link(self) -> str:
        return f'<a download="{self._file_name}" href="{self._mime_pfx}{urllib.parse.quote(self._data)}" target="_blank">Download {self._file_type.value} image</a>'


@dataclass(frozen=True)
class _PlotWidgetsDataclass:
    # Widget to trigger updates (hack)
    rev_no: widgets.IntText = field(
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
        init=True,
        repr=False,
        default_factory=partial(
            widgets.Checkbox,
            description="Hide Small Outcomes",
        ),
    )

    # Generic display widgets
    resolution: widgets.IntSlider = field(
        init=False,
        repr=False,
        default_factory=partial(
            widgets.IntSlider,
            value=_DEFAULT_RESOLUTION,
            min=4,
            max=32,
            step=1,
            continuous_update=False,
            description="Resolution",
        ),
    )

    img_type: widgets.ToggleButtons = field(
        init=False,
        repr=False,
        default_factory=partial(
            widgets.ToggleButtons,
            value=_first_of(ImageType),
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
            value=_DEFAULT_CMAP,
            options=_CMAP_NAMES,
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
            value=_DEFAULT_COMPARE_CMAP,
            options=_CMAP_NAMES,
            description="Outer Colors",
        ),
    )

    burst_cmap_use_mpts: widgets.Checkbox = field(
        init=False,
        repr=False,
        default_factory=partial(
            widgets.Checkbox,
            value=True,
            description="Color at Midpoints",
        ),
    )

    burst_color_bg: widgets.ColorPicker = field(
        init=False,
        repr=False,
        default_factory=partial(
            widgets.ColorPicker,
            value=_DEFAULT_BURST_COLOR_BG,
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
            value=_DEFAULT_BURST_COLOR_TEXT,
            concise=False,
            description="Text",
        ),
    )

    burst_columns: widgets.IntSlider = field(
        init=False,
        repr=False,
        default_factory=partial(
            widgets.IntSlider,
            value=_DEFAULT_COLS_BURST,
            min=1,
            max=12,
            step=1,
            continuous_update=False,
            description="Columns",
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
            value=_DEFAULT_GRAPH_TYPE,
            options=[(graph_type, graph_type) for graph_type in GraphTypeT.__args__],  # type: ignore[attr-defined]
            description="Plot Type",
            rows=min(len(GraphTypeT.__args__), 5),  # type: ignore[attr-defined]
        ),
    )

    markers: widgets.Text = field(
        init=False,
        repr=False,
        default_factory=partial(
            widgets.Text,
            value=_DEFAULT_MARKERS,
            description="Markers",
        ),
    )

    plot_style: widgets.Dropdown = field(
        init=False,
        repr=False,
        default_factory=partial(
            widgets.Dropdown,
            value=_DEFAULT_MPL_STYLE,
            options=[_DEFAULT_MPL_STYLE]
            + [style for style in mstyle.available if not style.startswith("_")],
            description="Style",
        ),
    )


class PlotWidgets(_PlotWidgetsDataclass):
    r"""
    !!! warning "Experimental"

        This class should be considered experimental and may change or disappear in
        future versions.

    Class to encapsulate interactive plot control widgets. All parameters for the
    [initializer][anydyce.viz.PlotWidgets.__init__] are optional.

    - *initial_alpha* is the starting alpha value for graphs (defaults to `#!python
       0.75`).

    - *initial_burst_cmap_inner* is the initially selected color map for inner burst
       graphs (defaults to `#!python "viridis"`).

    - *initial_burst_cmap_link* is the starting value for linking the color maps for
       inner and outer burst graphs (defaults to `#!python True`).

    - *initial_burst_cmap_outer* is the initially selected color map for outer burst
       graphs (defaults to `#!python "viridis"`).

    - *initial_burst_cmap_use_mpts* is the starting value for whether to map midpoints to color maps for burst
       graphs (defaults to `#!python True`).

    - *initial_burst_color_bg* is the initially selected background color for burst
       graphs (defaults to `#!python "white"`).

    - *initial_burst_color_bg_trnsp* is the initially selected background transparency
       color burst graphs (defaults to `#!python False`).

    - *initial_burst_color_text* is the initially selected text color for burst graphs
       (defaults to `#!python "black"`).

    - *initial_burst_columns* is the initially selected number of columns for displaying
       burst graphs (defaults to `#!python 3`).

    - *initial_burst_swap* is whether the inner and outer burst graphs should be swapped
       at first (defaults to `#!python False`).

    - *initial_burst_zero_fill_normalize* is whether all burst graphs should share a
       scale at first (i.e., so similar values share similar colors across burst graphs)
       (defaults to `#!python False`).

    - *initial_enable_cutoff* is whether small values should be omitted from graphs at
       first (defaults to `#!python True`).

    - *initial_graph_type* is the type of graph first shown (defaults to
       `#!python "normal"`.

    - *initial_img_type* is the initially selected image type (defaults to
       [`ImageType.SVG`][anydyce.viz.ImageType.SVG]).

    - *initial_markers* are the starting set of markers for line plots (defaults to
       `#!python "oX^v><dP"`).

    - *initial_plot_style* is the starting color style for non-burst graphs (defaults to
       `#!python "bmh"`).

    - *initial_resolution* is the starting value for the graph resolution (defaults to
      `#!python 12`).
    """

    def __init__(
        self,
        *,
        initial_alpha: float = _DEFAULT_ALPHA,
        initial_burst_cmap_inner: str = _DEFAULT_CMAP,
        initial_burst_cmap_link: bool = True,
        initial_burst_cmap_outer: str = _DEFAULT_COMPARE_CMAP,
        initial_burst_cmap_use_mpts: bool = True,
        initial_burst_columns: int = _DEFAULT_COLS_BURST,
        initial_burst_swap: bool = False,
        initial_burst_zero_fill_normalize: bool = False,
        initial_burst_color_bg: str = _DEFAULT_BURST_COLOR_BG,
        initial_burst_color_bg_trnsp: bool = False,
        initial_burst_color_text: str = _DEFAULT_BURST_COLOR_TEXT,
        initial_enable_cutoff: bool = True,
        initial_graph_type: GraphTypeT = _DEFAULT_GRAPH_TYPE,
        initial_img_type: ImageType = ImageType.SVG,
        initial_markers: str = _DEFAULT_MARKERS,
        initial_plot_style: str = _DEFAULT_PLOT_STYLE,
        initial_resolution: int = _DEFAULT_RESOLUTION,
    ) -> None:
        super().__init__()

        if (
            initial_plot_style != _DEFAULT_MPL_STYLE
            and initial_plot_style not in mstyle.available
        ):
            warnings.warn(
                f"unrecognized plot style {initial_plot_style!r}; reverting to {_DEFAULT_MPL_STYLE!r}",
                PlotWarning,
                stacklevel=1,
            )
            initial_plot_style = _DEFAULT_MPL_STYLE

        self.alpha.value = initial_alpha
        self.burst_cmap_inner.value = initial_burst_cmap_inner
        self.burst_cmap_link.value = initial_burst_cmap_link
        self.burst_cmap_outer.disabled = initial_burst_cmap_link
        self.burst_cmap_outer.value = initial_burst_cmap_outer
        self.burst_cmap_use_mpts.value = initial_burst_cmap_use_mpts
        self.burst_color_bg.value = initial_burst_color_bg
        self.burst_color_bg_trnsp.value = initial_burst_color_bg_trnsp
        self.burst_color_text.value = initial_burst_color_text
        self.burst_columns.value = initial_burst_columns
        self.burst_swap.value = initial_burst_swap
        self.burst_zero_fill_normalize.value = initial_burst_zero_fill_normalize
        self.cutoff.disabled = not initial_enable_cutoff
        self.enable_cutoff.value = initial_enable_cutoff
        self.graph_type.value = initial_graph_type
        self.img_type.value = initial_img_type
        self.markers.value = initial_markers
        self.plot_style.value = initial_plot_style
        self.resolution.value = initial_resolution
        self._suspend_plot_updates_depth = 0  # ty: ignore[invalid-assignment]

        def _handle_cutoff(change: _ChangeT) -> None:
            self.cutoff.disabled = not change["new"]

        self.enable_cutoff.observe(_handle_cutoff, names="value")

        def _handle_plot_style(change: _ChangeT) -> None:
            new_style = change["new"]
            with self.suspend_plot_updates():
                self.burst_cmap_outer.value = self.burst_cmap_inner.value = (
                    _get_param_for_style(new_style, "image.cmap")
                )
                burst_color_text = _get_param_for_style(new_style, "text.color")
                try:
                    self.burst_color_text.value = burst_color_text
                except TraitError:
                    self.burst_color_text.value = mcolors.to_hex(burst_color_text)
                burst_color_bg = _get_param_for_style(new_style, "figure.facecolor")
                try:
                    self.burst_color_bg.value = burst_color_bg
                except TraitError:
                    self.burst_color_bg.value = mcolors.to_hex(burst_color_bg)

        # INVARIANT: This observer must be registered on plot_style *before*
        # HPlotterChooser wires interactive_output (which also observes plot_style).
        # traitlets dispatches observers in registration order, so _handle_plot_style
        # runs first (suppressing its cascade), and interactive_output's trailing
        # plot_style notification is then the single redraw, with all cascaded values
        # already applied. If registration order ever inverts, the plot renders with the
        # new style but stale burst_* values, then the cascade updates them with no
        # redraw following, which would present an incorrect view.
        self.plot_style.observe(_handle_plot_style, names="value")

        def _handle_burst_cmap_link(change: _ChangeT) -> None:
            self.burst_cmap_outer.disabled = change["new"]

        self.burst_cmap_link.observe(_handle_burst_cmap_link, names="value")

        def _handle_burst_color_bg_trnsp(change: _ChangeT) -> None:
            self.burst_color_bg.disabled = change["new"]

        self.burst_color_bg_trnsp.observe(_handle_burst_color_bg_trnsp, names="value")

    def asdict(self) -> dict[str, Any]:
        return {field.name: getattr(self, field.name) for field in fields(self)}

    @property
    def plot_updates_suspended(self) -> bool:
        r"""
        Whether plot redraws are currently being suppressed by an active
        [`suspend_plot_updates`][anydyce.viz.PlotWidgets.suspend_plot_updates] block.
        """
        return self._suspend_plot_updates_depth > 0

    @contextmanager
    def suspend_plot_updates(self) -> Generator[None]:
        r"""
        Nesting-safe context manager to allow suppression of plot redraws for the
        duration of the block.

        This ***only*** manages a flag readable via
        [`plot_updates_suspended`][anydyce.viz.PlotWidgets.plot_updates_suspended]. No
        suppression or redraw logic is contained here.
        """
        self._suspend_plot_updates_depth += 1
        try:
            yield
        finally:
            self._suspend_plot_updates_depth -= 1


class HPlotter:
    r"""
    !!! warning "Experimental"

        This class should be considered experimental and may change or disappear in
        future versions.

    A plotter responsible for laying out control widgets and visualizing data provided
    by primary and optional secondary histograms. (See the
    [*plot* method][anydyce.viz.HPlotter.plot].)
    """

    @property
    @abstractmethod
    def NAME(self) -> str:  # noqa: N802
        r"""
        The display name of the plotter.
        """
        raise NotImplementedError

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
                plot_widgets.resolution,
            ]
        )

    @abstractmethod
    def plot(
        self,
        hs: Sequence[tuple[str, H, H | None]],
        settings: SettingsDict,
    ) -> None:
        r"""
        Creates and displays a visualization of the provided histograms. *fig* is the
        [`#!python
        matplotlib.figure.Figure`](https://matplotlib.org/stable/api/figure_api.html#matplotlib.figure.Figure)
        in which the visualization should be constructed. *hs* is a sequence of
        three-tuples, a name, a primary histogram, and an optional secondary histogram
        (`#!python None` if omitted). Plotters should implement this function to
        display at least the primary histogram and visually associate it with the name.
        """
        raise NotImplementedError

    def transparent(self, *, requested: bool) -> bool:  # noqa: ARG002
        r"""
        Returns whether this plotter produces plots which support transparency if
        *requested*. The default implementation always returns `#!python False`.
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

    NAME: str = "Bar Plot"

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
                            ]
                        ),
                    ]
                ),
            ]
        )

    def plot(
        self,
        hs: Sequence[tuple[str, H, H | None]],
        settings: SettingsDict,
    ) -> None:
        _, ax = plt.subplots(
            figsize=(
                settings["resolution"],
                settings["resolution"] / 16 * 9,
            )
        )

        plot_bar(
            *(h for _, h, _ in hs),
            alpha=settings["alpha"],
            ax=ax,
            graph_type=settings["graph_type"],
            labels=[label for label, _, _ in hs],
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

    NAME: str = "Burst Plots"

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
                                plot_widgets.burst_cmap_use_mpts,
                                plot_widgets.burst_cmap_link,
                            ]
                        ),
                        widgets.VBox(
                            [
                                plot_widgets.alpha,
                                plot_widgets.plot_style,
                                plot_widgets.burst_color_text,
                                plot_widgets.burst_color_bg,
                                plot_widgets.burst_color_bg_trnsp,
                                plot_widgets.burst_columns,
                            ]
                        ),
                    ]
                ),
            ]
        )

    def plot(
        self,
        hs: Sequence[tuple[str, H, H | None]],
        settings: SettingsDict,
    ) -> None:
        cols = settings["burst_columns"]
        assert cols > 0
        logical_rows = len(hs) // cols + (len(hs) % cols != 0)
        # Height of row gaps in relation to height of figs
        gap_size_ratio = Fraction(1, 5)
        total_gaps = max(0, logical_rows - 1)
        figsize = (
            settings["resolution"],
            float(
                settings["resolution"]
                * (logical_rows + total_gaps * gap_size_ratio)
                / cols
            ),
        )
        plt.figure(figsize=figsize)
        actual_rows_per_fig = gap_size_ratio.denominator
        actual_rows_per_gap = gap_size_ratio.numerator
        total_actual_rows = (
            logical_rows * actual_rows_per_fig + total_gaps * actual_rows_per_gap
        )

        def _zero_fill_normalize() -> Iterable[tuple[str, H, H | None]]:
            unique_outcomes: set[Any] = set()
            for _, first_h, second_h in hs:
                unique_outcomes.update(first_h)
                if second_h:
                    unique_outcomes.update(second_h)
            for label, first_h, second_h in hs:
                yield (
                    label,
                    first_h.zero_fill(unique_outcomes),
                    None if second_h is None else second_h.zero_fill(unique_outcomes),
                )

        if settings["burst_zero_fill_normalize"]:
            hs = tuple(_zero_fill_normalize())
        h_inner: H
        h_outer: H | None
        for i, (label, h_inner, h_outer) in enumerate(hs):
            if h_outer is not None and settings["burst_swap"]:
                h_inner, h_outer = h_outer, h_inner  # noqa: PLW2901
            logical_row = i // cols
            actual_row_start = logical_row * (actual_rows_per_gap + actual_rows_per_fig)
            ax = plt.subplot2grid(
                (total_actual_rows, cols),
                (actual_row_start, i % cols),
                rowspan=actual_rows_per_fig,
            )
            plot_burst(
                h_inner,
                h_outer,
                alpha=settings["alpha"],
                ax=ax,
                cmap=settings["burst_cmap_inner"],
                compare_cmap=(
                    settings["burst_cmap_inner"]
                    if settings["burst_cmap_link"]
                    else settings["burst_cmap_outer"]
                ),
                title=label,
                use_midpoints_for_colors=settings["burst_cmap_use_mpts"],
            )
            ax.title.set_color(settings["burst_color_text"])
            for text in ax.texts:
                text.set_color(
                    settings["burst_color_text"]
                )  # wedge labels (both rings)
            for patch in ax.patches:
                patch.set_edgecolor(
                    settings["burst_color_text"]
                )  # wedge edges (both rings)
            ax.set_facecolor(settings["burst_color_bg"])

    def transparent(self, *, requested: bool) -> bool:
        return requested


class HorizontalBarHPlotter(BarHPlotter):
    r"""
    !!! warning "Experimental"

        This class should be considered experimental and may change or disappear in
        future versions.

    A plotter for creating one horizontal bar plot per primary histogram. Secondary
    histograms are ignored.
    """

    NAME: str = "Horizontal Bar Plots"

    def plot(
        self,
        hs: Sequence[tuple[str, H, H | None]],
        settings: SettingsDict,
    ) -> None:
        total_outcomes = sum(
            1 for _ in chain.from_iterable(h.outcomes() for _, h, _ in hs)
        )
        total_height = total_outcomes + 1  # one extra to accommodate the axis
        inches_per_height_unit = settings["resolution"] / 64
        figsize = (
            settings["resolution"],
            total_height * inches_per_height_unit,
        )
        plt.figure(figsize=figsize)
        barh_kw: dict[str, Any] = {"alpha": settings["alpha"]}
        plot_style = settings["plot_style"]

        if (
            plot_style in mstyle.library
            and "axes.prop_cycle" in mstyle.library[plot_style]
            and "color" in mstyle.library[plot_style]["axes.prop_cycle"]
        ):
            # Our current style has a cycler with colors, so use it
            cycler = mstyle.library[plot_style]["axes.prop_cycle"]
        else:
            # Revert to the global default
            cycler = mpl.rcParams["axes.prop_cycle"]

        color_iter = cycle(cycler.by_key().get("color", (None,)))
        row_start = 0
        first_ax = ax = None

        for label, h, _ in hs:
            if not h:
                continue

            outcomes, values = values_xy_for_graph_type(h, settings["graph_type"])
            rowspan = len(outcomes)

            if first_ax is None:
                first_ax = ax = plt.subplot2grid(
                    (total_height, 1), (row_start, 0), rowspan=rowspan
                )
            else:
                ax = plt.subplot2grid(
                    (total_height, 1), (row_start, 0), rowspan=rowspan, sharex=first_ax
                )

            ax.set_yticks(outcomes)
            ax.tick_params(labelbottom=False)
            ax.set_ylim((max(outcomes) + 0.5, min(outcomes) - 0.5))
            ax.barh(
                outcomes,
                tuple(float(v) for v in values),
                color=next(color_iter),
                label=label,
                **barh_kw,
            )
            ax.legend(loc="upper right")
            row_start += rowspan

        if ax is not None:
            ax.tick_params(labelbottom=True)
            ax.xaxis.set_major_formatter(mticker.PercentFormatter(xmax=1))


class LineHPlotter(HPlotter):
    r"""
    !!! warning "Experimental"

        This class should be considered experimental and may change or disappear in
        future versions.

    A plotter for creating a single line plot visualizing all primary histograms.
    Secondary histograms are ignored.
    """

    NAME: str = "Line Plot"

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
                                plot_widgets.markers,
                            ]
                        ),
                    ]
                ),
            ]
        )

    def plot(
        self,
        hs: Sequence[tuple[str, H, H | None]],
        settings: SettingsDict,
    ) -> None:
        _, ax = plt.subplots(
            figsize=(
                settings["resolution"],
                settings["resolution"] / 16 * 9,
            )
        )

        plot_line(
            *(h for _, h, _ in hs),
            alpha=settings["alpha"],
            ax=ax,
            graph_type=settings["graph_type"],
            labels=[label for label, _, _ in hs],
            markers=settings["markers"],
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
    data changes. All parameters for the [initializer][anydyce.HPlotterChooser.__init__]
    are optional.

    *histogram_specs* is the histogram data set which defaults to an empty tuple. If
    provided, each item therein can be a `#!python dyce.H` object, a 2-tuple, or a
    3-tuple. 2-tuples are in the format `#!python (str, H)`, where `#!python str` is
    a name or description that will be used to identify the accompanying `#!python H`
    object where it appears in the visualization. 3-tuples are in the format `#!python
    (str, H, H)`. The second `#!python H` object is used for the interior ring in
    “burst” break-out graphs, but otherwise ignored. If an item is `#!python None`, it
    is roughly synonymous with `#!python ("", H({}), None)`, with the exception that
    it does not advance the automatic naming counter. This can be useful as “blank”
    filler to achieve a desired layout (e.g., where one wants to compare across burst
    graphs that don't neatly fit into a particular row size).

    The histogram data set can also be replaced via
    [`update_hs`][anydyce.viz.HPlotterChooser.update_hs].

    Plotter controls (including the selection tabs) are contained within an accordion
    interface. If *controls_expanded* is `#!python True`, the accordion is initially
    expanded for the user. If it is `#!python False`, it is initially collapsed.

    *plot_widgets* allows object creators to customize the available control widgets,
    including their initial values. It defaults to `#!python None` which results in a
    fresh [`PlotWidgets`][anydyce.viz.PlotWidgets] object being created during
    construction.

    *plotters_or_factories* allows overriding which plotters are available. The default
    is to provide factories for all plotters currently available in `anydyce`.

    *selected_name* is the name of the plotter to be displayed initially. It must match
    the `#!python NAME` property of an available plotter provided by the
    *plotters_or_factories* parameter.
    """

    def __init__(
        self,
        histogram_specs: Iterable[
            HLikeT | tuple[str, HLikeT] | tuple[str, HLikeT, HLikeT | None] | None
        ] = (),
        *,
        controls_expanded: bool = False,
        plot_widgets: PlotWidgets | None = None,
        plotters_or_factories: Iterable[HPlotter | HPlotterFactoryT] = (
            BurstHPlotter,
            LineHPlotter,
            BarHPlotter,
            HorizontalBarHPlotter,
        ),
        selected_name: str | None = None,
    ) -> None:
        r"""Constructor."""
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
            selected_name = _first_of(self._plotters_by_name)

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
                PlotWarning,
                stacklevel=1,
            )

        if plot_widgets is None:
            plot_widgets = PlotWidgets()

        self._plot_widgets = plot_widgets
        self._layouts_by_name: Mapping[str, widgets.Widget] = {}

        for plotter_name, plotter in self._plotters_by_name.items():
            self._layouts_by_name[plotter_name] = plotter.layout(plot_widgets)

        self.hs: tuple[tuple[str, H, H | None], ...] = ()
        self._hs_culled: tuple[tuple[str, H, H | None], ...] = ()
        self._cutoff: float | None = None
        self._csv_download_link = ""
        self.update_hs(histogram_specs)
        self._selected_plotter: HPlotter | None
        tab_names = tuple(self._plotters_by_name.keys())

        chooser_tab = widgets.Tab(
            children=tuple(self._layouts_by_name.values()),
            selected_index=(
                0 if selected_name is None else tab_names.index(selected_name)
            ),
        )

        for i, tab_name in enumerate(tab_names):
            chooser_tab.set_title(i, tab_name)

        def _handle_tab(change: _ChangeT) -> None:
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
                # INVARIANT: This registers interactive_output's observers on every
                # control (incl. plot_style) *after* PlotWidgets.__init__ registers
                # _handle_plot_style. See the matching note there. Do not reorder these
                # so that interactive_output observes plot_style before
                # _handle_plot_style.
                widgets.interactive_output(self.plot, self._plot_widgets.asdict()),
            ]
        )

    def interact(self) -> None:
        r"""
        Displays the container responsible for selecting which plotter is used.
        """
        display(self._out)

    def plot(
        self,
        **kw,  # noqa: ANN003
    ) -> None:
        r"""
        Callback for updating the visualization in response to configuration or data
        changes. *settings* are the current values from all control widgets. (See
        [`PlotWidgets`][anydyce.viz.PlotWidgets].)
        """
        if self._plot_widgets.plot_updates_suspended:
            return
        settings = cast("SettingsDict", kw)
        cutoff = (
            self._plot_widgets.cutoff.value
            if self._plot_widgets.enable_cutoff.value
            else None
        )

        if self._cutoff != cutoff:
            self._cutoff = cutoff
            self._cull_data()

        with mstyle.context(settings["plot_style"]):
            if self._selected_plotter is not None:
                self._selected_plotter.plot(self._hs_culled, settings)
                transparent = self._selected_plotter.transparent(
                    requested=settings["burst_color_bg_trnsp"]
                )
            else:
                transparent = False
            buf = io.BytesIO()
            plt.savefig(
                buf,
                bbox_inches="tight",
                facecolor=mcolors.to_rgba(
                    settings["burst_color_bg"], alpha=0.0 if transparent else None
                ),
                format=settings["img_type"],
                transparent=transparent,
            )
            img_name = "-".join(label for label, _, _ in self.hs)
            img = Image(img_name, settings["img_type"], buf.getvalue())
            display(HTML(f"{self._csv_download_link} | {img.download_link()}"))
            display(img)
            plt.clf()
            plt.close()

    def update_hs(
        self,
        histogram_specs: Iterable[
            HLikeT | tuple[str, HLikeT] | tuple[str, HLikeT, HLikeT | None] | None
        ],
    ) -> None:
        r"""
        Triggers an update to the histogram data. See
        [`HPlotterChooser`][anydyce.viz.HPlotterChooser] for a more detailed
        explanation of *histogram_specs*.
        """
        self.hs = _histogram_specs_to_h_tuples(histogram_specs, cutoff=None)
        self._csv_download_link = _csv_download_link(self.hs)

        self._plot_widgets.burst_swap.disabled = all(
            h_outer is None or h_inner == h_outer for _, h_inner, h_outer in self.hs
        )

        self._cull_data()
        self._trigger_update()

    def _cull_data(self) -> None:
        self._hs_culled = _histogram_specs_to_h_tuples(self.hs, self._cutoff)

    def _trigger_update(self) -> None:
        self._plot_widgets.rev_no.value += 1


# ---- Functions -----------------------------------------------------------------------


@experimental
def limit_for_display(h: H[_T], cutoff: Fraction) -> H:
    r"""
    !!! warning "Experimental"

        This function should be considered experimental and may change or disappear in
        future versions.

    Discards outcomes in *h*, starting with the smallest counts as long as the total
    discarded in proportion to `#!python h.total` does not exceed *cutoff*. This can
    be useful in speeding up plots where there are large number of negligible
    probabilities.

    <!-- BEGIN MONKEY PATCH --
    >>> import warnings
    >>> from dyce.lifecycle import ExperimentalWarning
    >>> warnings.filterwarnings("ignore", category=ExperimentalWarning)

      -- END MONKEY PATCH -->

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

    <!-- BEGIN MONKEY PATCH --
    >>> warnings.resetwarnings()

       -- END MONKEY PATCH -->

    """
    if cutoff < 0 or cutoff > 1:
        raise ValueError(f"cutoff ({cutoff}) must be between zero and one, inclusive")

    cutoff_count = int(cutoff * h.total)

    if cutoff_count == 0:
        return h

    def _cull() -> Iterable[tuple[_T, int]]:
        so_far = 0

        for outcome, count in sorted(h.items(), key=itemgetter(1)):
            so_far += count

            if so_far > cutoff_count:
                yield outcome, count

    return H(dict(_cull()))


@experimental
def values_xy_for_graph_type(
    h: H[_T],
    graph_type: GraphTypeT,
) -> tuple[tuple[_T, ...], tuple[Fraction, ...]]:
    outcomes, probabilities = (
        zip(*h.probability_items(), strict=True) if h else ((), ())
    )

    if graph_type == "at_least":
        probabilities = tuple(
            accumulate(
                probabilities,
                __sub__,
                initial=Fraction(1),
            )
        )[:-1]
    elif graph_type == "at_most":
        probabilities = tuple(
            accumulate(
                probabilities,
                __add__,
                initial=Fraction(0),
            )
        )[1:]
    elif graph_type == "normal":
        pass
    else:
        assert False, f"unrecognized graph type {graph_type}"  # noqa: B011, PT015

    return outcomes, probabilities


@experimental
def jupyter_visualize(
    histogram_specs: Iterable[
        HLikeT | tuple[str, HLikeT] | tuple[str, HLikeT, HLikeT | None] | None
    ],
    *,
    controls_expanded: bool = False,
    initial_alpha: float = _DEFAULT_ALPHA,
    initial_burst_cmap_inner: str = _DEFAULT_CMAP,
    initial_burst_cmap_link: bool = True,
    initial_burst_cmap_outer: str = _DEFAULT_COMPARE_CMAP,
    initial_burst_cmap_use_mpts: bool = True,
    initial_burst_color_bg: str = _DEFAULT_BURST_COLOR_BG,
    initial_burst_color_bg_trnsp: bool = False,
    initial_burst_color_text: str = _DEFAULT_BURST_COLOR_TEXT,
    initial_burst_columns: int = _DEFAULT_COLS_BURST,
    initial_burst_swap: bool = False,
    initial_burst_zero_fill_normalize: bool = False,
    initial_enable_cutoff: bool = True,
    initial_graph_type: GraphTypeT = _DEFAULT_GRAPH_TYPE,
    initial_img_type: ImageType = ImageType.SVG,
    initial_markers: str = _DEFAULT_MARKERS,
    initial_plot_style: str = _DEFAULT_PLOT_STYLE,
    initial_resolution: int = _DEFAULT_RESOLUTION,
    selected_name: str | None = None,
) -> None:
    r"""
    !!! warning "Experimental"

        This function should be considered experimental and may change or disappear in
        future versions.

    Takes a list of one or more *histogram_specs* and produces an interactive
    visualization reminiscent of [AnyDice](https://anydice.com/), but with some extra
    goodies.

    The “Powered by the _Apocalypse_ (PbtA)” example in the introduction notebook should
    give an idea of the effect. (See [Interactive quick
    start](index.md#interactive-quick-start).)

    Parameters have the same meanings as with
    [`HPlotterChooser`][anydyce.viz.HPlotterChooser] and
    [`PlotWidgets`][anydyce.viz.PlotWidgets].
    """
    plotter_chooser = HPlotterChooser(
        histogram_specs,
        controls_expanded=controls_expanded,
        plot_widgets=PlotWidgets(
            initial_alpha=initial_alpha,
            initial_burst_cmap_inner=initial_burst_cmap_inner,
            initial_burst_cmap_link=initial_burst_cmap_link,
            initial_burst_cmap_outer=initial_burst_cmap_outer,
            initial_burst_cmap_use_mpts=initial_burst_cmap_use_mpts,
            initial_burst_color_bg=initial_burst_color_bg,
            initial_burst_color_bg_trnsp=initial_burst_color_bg_trnsp,
            initial_burst_color_text=initial_burst_color_text,
            initial_burst_columns=initial_burst_columns,
            initial_burst_swap=initial_burst_swap,
            initial_burst_zero_fill_normalize=initial_burst_zero_fill_normalize,
            initial_enable_cutoff=initial_enable_cutoff,
            initial_graph_type=initial_graph_type,
            initial_img_type=initial_img_type,
            initial_markers=initial_markers,
            initial_plot_style=initial_plot_style,
            initial_resolution=initial_resolution,
        ),
        selected_name=selected_name,
    )

    plotter_chooser.interact()


def _csv_download_link(hs: Sequence[tuple[str, H, H | None]]) -> str:
    unique_outcomes = sorted(set(chain.from_iterable(h.outcomes() for _, h, _ in hs)))
    labels = [label for label, _, _ in hs]
    raw_buffer = io.BytesIO()
    csv_buffer = io.TextIOWrapper(
        raw_buffer, encoding="utf-8", newline="", write_through=True
    )
    csv_writer = csv.DictWriter(csv_buffer, fieldnames=["Outcome", *labels])
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


# ---- Helpers -------------------------------------------------------------------------


def _histogram_specs_to_h_tuples(
    histogram_specs: Iterable[
        HLikeT | tuple[str, HLikeT] | tuple[str, HLikeT, HLikeT | None] | None
    ],
    cutoff: float | None = None,
) -> tuple[tuple[str, H, H | None], ...]:
    h_specs = []

    if cutoff is None:
        cutoff_frac = Fraction(0, 1)
    else:
        cutoff_frac = Fraction(cutoff).limit_denominator(_CUTOFF_BASE**_CUTOFF_EXP)

    label: str
    first_h_like: HLikeT
    second_h_like: HLikeT | None
    num_blanks = 0

    for i, thing in enumerate(histogram_specs):
        if thing is None:
            label = ""
            first_h_like = H({})
            second_h_like = None
            num_blanks += 1
        elif isinstance(thing, (H, HableT)):
            label = f"Histogram {i - num_blanks + 1}"
            first_h_like = thing
            second_h_like = None
        else:
            label, first_h_like = thing[:2]
            second_h_like = thing[2] if len(thing) >= 3 else None  # ty: ignore[index-out-of-bounds]

        assert isinstance(label, str)
        first_h = limit_for_display(
            first_h_like.h() if isinstance(first_h_like, HableT) else first_h_like,
            cutoff_frac,
        )

        if second_h_like is None:
            second_h = None
        else:
            second_h = limit_for_display(
                (
                    second_h_like.h()
                    if isinstance(second_h_like, HableT)
                    else second_h_like
                ),
                cutoff_frac,
            )

        h_specs.append((label, first_h, second_h))

    return tuple(h_specs)
