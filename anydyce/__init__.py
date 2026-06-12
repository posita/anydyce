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

r"""
!!! warning "Experimental"

    This package is an attempt to explore conveniences for integration with [Matplotlib](https://matplotlib.org/).
    It is an explicit departure from [RFC 1925, § 2.2](https://datatracker.ietf.org/doc/html/rfc1925#section-2) and should be considered experimental.
    Be warned that future release may introduce incompatibilities or remove this package altogether.
    [Feedback, suggestions, and contributions](contrib.md) are welcome and appreciated.
"""

from importlib.metadata import PackageNotFoundError, version
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # Type-checker-only imports.
    # `from anydyce import HPlotterChooser` resolves against this block at
    # type-check time; the runtime path goes through `__getattr__` below.
    # `TYPE_CHECKING` is always False at runtime, so importing `viz` here
    # has no effect on import-time cost.
    from .viz import HPlotterChooser, PlotWidgets, jupyter_visualize

_VIZ_ALL = frozenset(("HPlotterChooser", "PlotWidgets", "jupyter_visualize"))

__all__ = (
    "HPlotterChooser",
    "PlotWidgets",
    "jupyter_visualize",
)


def __dir__() -> list[str]:
    # PEP 562: declare what dir(anydyce) returns. Without this, lazy names
    # only appear after first access (when __getattr__ materializes them
    # into the module dict). Union of real globals + the lazy names.
    return sorted(set(globals()) | _VIZ_ALL)


def __getattr__(name: str) -> Any:  # noqa: ANN401
    # PEP 562 module-level __getattr__: Defer importing the viz layer (which has some
    # heavy dependencies) until someone actually accesses one of the names in __all__,
    # allowing consumers like the playground worker to avoid the viz import entirely.
    if name in _VIZ_ALL:
        from . import viz

        return getattr(viz, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


try:
    __version__: str = version("anydyce")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0+unknown"
