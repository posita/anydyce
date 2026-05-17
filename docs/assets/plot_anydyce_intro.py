# ======================================================================================
# Copyright and other protections apply. Please see the accompanying LICENSE file for
# rights and restrictions governing use of this software. All rights not expressly
# waived or licensed are reserved. If that file is missing or appears to be modified
# from its original, then please contact the author before viewing or using this
# software in any capacity.
# ======================================================================================


def fig_callback(_line_color: str) -> None:
    from matplotlib import style as mstyle

    mstyle.use("default")

    # NOTE: Changes to this section should be propagated to docs/assets/nb_anydice_intro.py
    # --8<-- [start:core]
    from dyce import H
    from dyce.viz import plot_bar, plot_burst, plot_line
    from matplotlib import pyplot as plt

    d10_2 = 2 @ H(10)
    d10_2_label = "2d10"
    d8d12 = H(8) + H(12)
    d8d12_label = "d8+d12"

    # Burst chart
    ax_burst = plt.subplot2grid((2, 2), (0, 0), colspan=2)
    plot_burst(
        d10_2,
        d8d12,
        alpha=0.8,
        ax=ax_burst,
        cmap="Purples_r",
        compare_cmap="Greens_r",
        title=f"Outer: {d8d12_label}\nInner: {d10_2_label}",
    )

    # Bar chart
    ax_bar = plt.subplot2grid((2, 2), (1, 0))
    plot_bar(
        d10_2,
        d8d12,
        alpha=0.8,
        ax=ax_bar,
        horizontal=True,
        labels=(d10_2_label, d8d12_label),
    )
    # Re-color the bars
    so_far = 0
    for count, color in zip(
        (len(h) for h in (d10_2, d8d12)),
        ("tab:purple", "tab:green"),
        strict=True,
    ):
        for i in range(count):
            ax_bar.patches[i + so_far].set_color(color)
        so_far += count
    ax_bar.legend()

    # Line chart
    ax_line = plt.subplot2grid((2, 2), (1, 1))
    plot_line(
        d10_2,
        d8d12,
        alpha=0.8,
        ax=ax_line,
        labels=(d10_2_label, d8d12_label),
        markers="<>",
    )
    # Re-color the lines
    ax_line.lines[0].set_color("tab:purple")
    ax_line.lines[1].set_color("tab:green")
    ax_line.legend()

    plt.gcf().set_size_inches(9.6, 9.6)
    # --8<-- [end:core]


if __name__ == "__main__":
    from _plot import main  # pyrefly: ignore[missing-import]

    main(fig_callback)
