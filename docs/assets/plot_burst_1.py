# ======================================================================================
# Copyright and other protections apply. Please see the accompanying LICENSE file for
# rights and restrictions governing use of this software. All rights not expressly
# waived or licensed are reserved. If that file is missing or appears to be modified
# from its original, then please contact the author before viewing or using this
# software in any capacity.
# ======================================================================================

from dyce import H

from anydyce.viz import plot_burst


def do_it(style: str) -> None:
    import matplotlib.pyplot

    ax = matplotlib.pyplot.axes()
    text_color = "white" if style == "dark" else "black"
    plot_burst(ax, 2 @ H(6), text_color=text_color)
