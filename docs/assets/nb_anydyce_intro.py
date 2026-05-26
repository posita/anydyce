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

# `anydyce` affords functionality similar to [AnyDice](https://anydice.com/) within [Jupyter](https://jupyter.org/) via various interface.

# %% jupyter={"source_hidden": true}
# Install additional requirements if necessary
from prerequisites import (  # pyright: ignore[reportMissingImports] # pyrefly: ignore[missing-import] # ty: ignore[unresolved-import]
    install_if_missing,
)

await install_if_missing(  # type: ignore[top-level-await] # noqa: PGH003
    # The optional piplite_spec (third item) omits version to use the local wheel
    ("anydyce", "anydyce~=0.5.0.dev1", "anydyce"),
)

import warnings

import matplotlib_inline
from dyce.lifecycle import ExperimentalWarning

import anydyce.magic  # noqa: F401

matplotlib_inline.backend_inline.set_matplotlib_formats("svg")
warnings.filterwarnings("ignore", category=ExperimentalWarning)

# %% [markdown]
# ### Interactive example: comparing d8+d12 and 2d10

# %%
from dyce import P
from dyce.d import d8, d12, h2d10

from anydyce import jupyter_visualize

p_3d6 = 3 @ P(6)
jupyter_visualize(
    (
        ("d8+d12", d8 + d12),
        ("2d10", h2d10),
    ),
    initial_markers="v^",
    selected_name="Line Plot",
)

# %% [markdown]
# ### Interactive example: *Powered by the Apocalypse* (PbtA)

# Expected distributions from *[Apocalypse World](http://apocalypse-world.com/)&rsquo;s* core mechanic with various modifiers.

# %%
from enum import IntEnum, auto

from dyce import HResult, expand
from dyce.d import h2d6

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


jupyter_visualize(
    ((f"PBTA {mod:+}", expand(pbta, h2d6 + mod), (h2d6 + mod)) for mod in range(-1, 4)),
    initial_burst_cmap_inner="RdYlGn",
    initial_burst_cmap_link=False,
    initial_burst_cmap_outer="Greys",
    initial_burst_cmap_use_midpoints=False,
)

# %% [markdown]
# ### Interactive AnyDice example from [4d6 Drop Lowest](https://anydice.com/articles/4d6-drop-lowest/)

# TODO(posita): # noqa: TD003 - Fill this out, and include instructions for `%%anyd?`

# %% language="anyd"
# %%anyd --line
# output [highest 3 of 4d6] named "4d6 drop lowest"
# output 3d6 named "3d6"

# %% [markdown]
# ### Interactive AnyDice example from [4d6 Drop Lowest](https://anydice.com/articles/4d6-drop-lowest/)

# TODO(posita): # noqa: TD003 - Fill this out, and include instructions for
# `%anyd_load?`

# %% language="txt"
# %anyd_load https://anydice.com/program/130e6
