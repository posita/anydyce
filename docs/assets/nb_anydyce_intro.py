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

# %% jupyter={"source_hidden": true}
# Install additional requirements if necessary
from prerequisites import (  # pyright: ignore[reportMissingImports] # pyrefly: ignore[missing-import] # ty: ignore[unresolved-import]
    install_if_missing,
)

await install_if_missing(  # type: ignore[top-level-await] # noqa: PGH003
    # The optional piplite_spec (third item) omits version to use the local wheel
    ("anydyce[jupyter]", "anydyce~=0.5.0.dev1[jupyter]", "anydyce[jupyter]"),
)

import warnings

# For some reason, this needs to be imported before matplotlib_line
import matplotlib as mpl  # noqa: F401
import matplotlib_inline
from dyce.lifecycle import ExperimentalWarning

import anydyce.magic  # noqa: F401

matplotlib_inline.backend_inline.set_matplotlib_formats("svg")
warnings.filterwarnings("ignore", category=ExperimentalWarning)

# %% [markdown]
# ### Using `dyce` to visualize *[Apocalypse World](http://apocalypse-world.com/)&rsquo;s* core mechanic with various modifiers

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
# ### Using the `%%anyd` magic command to run an AnyDice program

# See `?%%anyd` for details.

# %% language="anyd"
# %%anyd --line
# output 2d10 named "2d10"
# output d8+d12 named "d8+d12"

# %% [markdown]
# ### Using the `%anyd_load` magic command to retrieve a previously saved AnyDice program

# See `?%anyd_load` for details.

# %% language="txt"
# %anyd_load https://anydice.com/program/130e6
