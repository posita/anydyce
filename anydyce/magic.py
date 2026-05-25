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

- `%%anyd` - run cell body as legacy AnyDice source.
- `%anyd_load` - fetch an AnyDice program by ID or URL and replace the cell with its source.
"""

import html
import warnings
from datetime import UTC, datetime

from dyce.lifecycle import ExperimentalWarning
from IPython import get_ipython  # pyright: ignore[reportPrivateImportUsage]
from IPython.core.interactiveshell import InteractiveShell
from IPython.core.magic_arguments import argument, magic_arguments, parse_argstring
from IPython.display import HTML, Markdown, display

from .anydice import DEFAULT_PRECISION, format_anydice_results, run
from .anydice.fetch import fetch_anydice_program, is_pyodide

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


@magic_arguments()
@argument(
    "location_or_id",
    help="An AnyDice program ID or URL.",
)
def anyd_load(line: str) -> None:
    r"""
    Fetch an AnyDice program by ID or URL and replace the cell with its source.

    Examples:

        %anyd_load 4d2
        %anyd_load https://anydice.com/program/4d2

    On success, the cell is replaced with an `%%anyd` cell containing the fetched program plus a comment header recording the source URL and fetch time.
    The replaced cell is ***not*** auto-executed.
    If the program cannot be retrieved directly from anydice.com, an attempt is made to find it using a mirror.
    On failure (e.g., network error, missing program, etc.), the exception propagates to Jupyter and the original `%anyd_load` line is left in place.
    """
    args = parse_argstring(anyd_load, line)
    program_id_hex, initial_url, _final_url, program = fetch_anydice_program(
        args.location_or_id
    )
    fetched_at = datetime.now(UTC).astimezone().isoformat(timespec="seconds")
    new_cell = (
        "%%anyd\n"
        "\\\n"
        f"  AnyDice program {program_id_hex} fetched from {initial_url} at {fetched_at} using:\n"
        f"  %anyd_load {args.location_or_id}\n"
        "\\\n"
        f"{program}"
    )
    # Inside a magic, the shell is what just invoked us is guaranteed to exist
    if is_pyodide():
        _display_program_with_copy_button(new_cell)
    else:
        ipy = get_ipython()
        assert ipy
        ipy.set_next_input(new_cell, replace=True)


def _display_program_with_copy_button(content: str) -> None:
    content = content.strip()
    escaped_for_attr = html.escape(content, quote=True)
    display(
        Markdown(
            "**Copy the block below into a new cell to run it:**\n\n"
            f"```anydice\n{content}\n```"
        ),
        HTML(f"""
          <button
              data-copy-content="{escaped_for_attr}"
              onclick="navigator.clipboard.writeText(this.dataset.copyContent).then(
                () => {{ this.textContent = 'Copied'; setTimeout(() => this.textContent = 'Copy', 1500); }},
                () => {{ this.textContent = 'Failed'; setTimeout(() => this.textContent = 'Copy', 1500); }}
              )"
              style="padding: 0.3em 0.8em; cursor: pointer; min-width: 7em;
                background: #99999999; border: 1px solid #999; border-radius: 3px;
                font-size: 0.85em;">
            Copy
          </button>
        """),
    )


def load_ipython_extension(ipy: InteractiveShell) -> None:
    r"""
    IPython extension entry point. Registers Magics.

    Invoked by `%load_ext anydyce.magic` from inside an IPython/Jupyter session.
    """
    # The expected ipython.register_magic_function works at runtime (as verified by our
    # load-extension tests), but type checkers get confused if we use it that way.
    # Apparently register_magic_function is unbound? Not sure. Anyway, this approach
    # seems to make everyone happy for now.
    type(ipy).register_magic_function(
        ipy,
        anyd,
        magic_kind="cell",
    )
    type(ipy).register_magic_function(
        ipy,
        anyd_load,
        magic_kind="line",
    )


_ipy = get_ipython()
if _ipy is not None:
    load_ipython_extension(_ipy)
