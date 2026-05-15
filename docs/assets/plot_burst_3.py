# ======================================================================================
# Copyright and other protections apply. Please see the accompanying LICENSE file for
# rights and restrictions governing use of this software. All rights not expressly
# waived or licensed are reserved. If that file is missing or appears to be modified
# from its original, then please contact the author before viewing or using this
# software in any capacity.
# ======================================================================================


def fig_callback(line_color: str) -> None:
    # NOTE: Changes to this section should be propagated to docs/assets/TODO.py
    # --8<-- [start:core]
    from enum import IntEnum
    from fractions import Fraction

    from dyce import H
    from dyce.d import d20
    from dyce.viz import plot_burst

    class Result(IntEnum):
        FAIL_CRIT = -2
        FAIL = -1
        SUCC = 1
        SUCC_CRIT = 2

    def d20_to_result(outcome: int) -> Result:
        return (
            Result.FAIL_CRIT
            if outcome <= 1
            else Result.FAIL
            if outcome <= 14
            else Result.SUCC
            if outcome <= 19
            else Result.SUCC_CRIT
        )

    def d20_formatter(outcome: Result, _probability: Fraction, _h: H[Result]) -> str:
        return {
            Result.FAIL_CRIT: "Critical\nFailure",
            Result.FAIL: "Failure",
            Result.SUCC: "Success",
            Result.SUCC_CRIT: "Critical\nSuccess",
        }[outcome]

    ax = plot_burst(
        d20,
        d20.apply(d20_to_result),
        cmap="RdYlBu_r",
        compare_formatter=d20_formatter,
    )
    # --8<-- [end:core]

    ax.title.set_color(line_color)
    for text in ax.texts:
        text.set_color(line_color)  # wedge labels (both rings)
    for patch in ax.patches:
        patch.set_edgecolor(line_color)  # wedge edges (both rings)


if __name__ == "__main__":
    from _plot import main  # pyrefly: ignore[missing-import]

    main(fig_callback)
