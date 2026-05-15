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
    from dyce import H
    from dyce.d import h2d6
    from dyce.viz import plot_burst

    df = H((-1, 0, 1))
    h4df = 4 @ df

    ax = plot_burst(
        h4df,
        h2d6,
        cmap="turbo",
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
