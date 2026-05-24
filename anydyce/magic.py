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
IPython Magic(s) for the AnyDice interpreter.

Currently, this includes:

- `%%anyd` - legacy AnyDice interpreter
"""

import warnings

from dyce.lifecycle import ExperimentalWarning
from IPython.core.interactiveshell import InteractiveShell
from IPython.core.magic_arguments import argument, magic_arguments, parse_argstring

from .anydice import DEFAULT_PRECISION, format_anydice_results, run

__all__ = ("load_ipython_extension",)


@magic_arguments()
@argument(
    "--short",
    action="store_true",
    help="Format each output on one-line instead of the default multi-line format.",
)
@argument(
    "--precision",
    type=int,
    default=DEFAULT_PRECISION,
    help=f"Number of decimal places used when formatting output values. Default: {DEFAULT_PRECISION}.",
)
def anyd(line: str, cell: str) -> None:
    r"""
    Run the cell as legacy AnyDice source and print each output's distribution.

    Examples:

        %%anyd
        output 3d6

        %%anyd --short
        output 2d20

        %%anyd --precision 32
        output 1d100
    """
    args = parse_argstring(anyd, line)

    with warnings.catch_warnings():
        # Everything other than a DeprecationWarning or ExperimentalWarning (e.g.,
        # TruncationWarning, etc.) should bubble up so Jupyter renders it next to the
        # cell output
        warnings.filterwarnings("ignore", category=DeprecationWarning)
        warnings.filterwarnings("ignore", category=ExperimentalWarning)
        print(
            format_anydice_results(
                run(cell), precision=args.precision, short=args.short
            )
        )


def load_ipython_extension(ipython: InteractiveShell) -> None:
    r"""
    IPython extension entry point. Registers Magics.

    Invoked by `%load_ext anydyce.magic` from inside an IPython/Jupyter session.
    """
    # The expected ipython.register_magic_function works at runtime (as verified by our
    # load-extension tests), but type checkers get confused if we use it that way.
    # Apparently register_magic_function is unbound? Not sure. Anyway, this approach
    # seems to make everyone happy for now.
    type(ipython).register_magic_function(
        ipython,
        anyd,
        magic_kind="cell",
    )
