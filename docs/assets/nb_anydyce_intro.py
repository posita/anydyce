# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.1
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
#   language_info:
#     name: python
# ---

# %% [markdown]
# <!---
# Copyright and other protections apply. Please see the accompanying LICENSE file for
# rights and restrictions governing use of this software. All rights not expressly
# waived or licensed are reserved. If that file is missing or appears to be modified
# from its original, then please contact the author before viewing or using this
# software in any capacity.
#
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# !!!!!!!!!!!!!!! IMPORTANT: READ THIS BEFORE EDITING! !!!!!!!!!!!!!!!
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# When updating a cell, plan to re-run the notebook locally and recommit the .ipynb
# afterward. Otherwise, the pre-populated output for that cell will disappear or be
# stale.
# -->
#
# ## Introduction to [`anydyce`](https://posita.github.io/anydyce/)&rsquo;s interactive visualization capabilities

# Selected examples highlighting [`dyce`](https://posita.github.io/dyce/)&rsquo;s use and capabilities. Select `Run All Cells` from the `Run` menu above.
#
# %% [markdown]
# ## AnyDice replacement

# `anydyce` affords functionality similar to [AnyDice](https://anydice.com/) within [Jupyter](https://jupyter.org/) via its `anydyce.jupyter_visualize` interface.

# %% jupyter={"source_hidden": true}
# Install additional requirements if necessary
from prerequisites import (  # pyright: ignore[reportMissingImports] # pyrefly: ignore[missing-import] # ty: ignore[unresolved-import]
    install_if_missing,
)

await install_if_missing(  # type: ignore[top-level-await] # noqa: PGH003
    # The optional piplite_spec (third item) omits version to use the local wheel
    ("anydyce", "anydyce~=0.5.0.dev1", "anydyce"),
    ("dyce", "dyce~=0.7.0rc1"),
)

import warnings

import matplotlib_inline
from dyce.lifecycle import ExperimentalWarning

import anydyce as _  # noqa: F401

matplotlib_inline.backend_inline.set_matplotlib_formats("svg")
warnings.filterwarnings("ignore", category=ExperimentalWarning)

# %% [markdown]
# ### Interactive example: highest, middle, and lowest of 3d6

# %%
from dyce import P

from anydyce import jupyter_visualize

p_3d6 = 3 @ P(6)
jupyter_visualize(
    (
        p_3d6.h(-1),  # highest
        p_3d6.h(1),  # middle
        p_3d6.h(0),  # lowest
    ),
    initial_markers="o",
    selected_name="Line Plot",
)

# %% [markdown]
# ### Interactive example: *Powered by the Apocalypse* (PbtA)

# Expected distributions from *[Apocalypse World](http://apocalypse-world.com/)&rsquo;s* core mechanic with various modifiers.

# %%
from enum import IntEnum, auto

from dyce import H, HResult, expand

from anydyce import jupyter_visualize


class PBTA(IntEnum):
    FAIL = 0
    COST = auto()
    SUCC = auto()


def pbta(result: HResult) -> PBTA:
    if result.outcome <= 6:
        return PBTA.FAIL
    elif result.outcome >= 10:
        return PBTA.SUCC
    else:
        return PBTA.COST


h2d6 = 2 @ H(6)

jupyter_visualize(
    ((f"PBTA {mod:+}", expand(pbta, h2d6 + mod), (h2d6 + mod)) for mod in range(-1, 4)),
    initial_burst_cmap_inner="RdYlGn",
    initial_burst_cmap_link=False,
    initial_burst_cmap_outer="Greys",
    initial_burst_cmap_use_mpts=False,
)

# %% [markdown]
# ## Lower level visualization conveniences

# `dyce` provides the lower level visualization functions that `anydyce` uses for its display.
# You can access them directly for more control.

# %% [markdown]
# ### Visualization example: 2d10 vs. d8+d12, bar, line, and burst charts

# The following compares two mechanics with similar distributions via `dyce`&rsquo;s take on a bar chart (`dyce.viz.plot_bar`), a line chart (`dyce.viz.plot_line`), and a “burst” chart (`dyce.viz.plot_burst` which is `dyce`&rsquo;s take on a donut chart).

# %%
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
plt.tight_layout()
plt.show()
