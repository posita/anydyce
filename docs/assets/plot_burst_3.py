# ======================================================================================
# Copyright and other protections apply. Please see the accompanying LICENSE file for
# rights and restrictions governing use of this software. All rights not expressly
# waived or licensed are reserved. If that file is missing or appears to be modified
# from its original, then please contact the author before viewing or using this
# software in any capacity.
# ======================================================================================

from __future__ import annotations

from fractions import Fraction
from typing import Dict

from dyce import H
from numerary import RealLike

from anydyce.viz import plot_burst


def do_it(style: str) -> None:
    import matplotlib.pyplot

    def d20formatter(outcome: RealLike, probability: Fraction, h: H) -> str:
        vals: Dict[RealLike, str] = {
            -2: "crit. fail.",
            -1: "fail.",
            1: "succ.",
            2: "crit. succ.",
        }

        return vals[outcome]

    d20 = H(20)

    ax = matplotlib.pyplot.axes()
    text_color = "white" if style == "dark" else "black"
    plot_burst(
        ax,
        h_inner=d20,
        h_outer=H(
            {
                -2: d20.le(1)[1],
                -1: d20.within(2, 14)[0],
                1: d20.within(15, 19)[0],
                2: d20.ge(20)[1],
            }
        ),
        inner_color="RdYlBu_r",
        outer_formatter=d20formatter,
        text_color=text_color,
    )
