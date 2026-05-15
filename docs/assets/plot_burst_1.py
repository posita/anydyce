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


def fig_callback(line_color: str) -> None:
    # NOTE: Changes to this section should be propagated to docs/assets/TODO.py
    # --8<-- [start:core]
    from dyce.d import p2d6
    from dyce.viz import plot_burst

    ax = plot_burst(
        p2d6.h(0),
        p2d6.h(-1),
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
