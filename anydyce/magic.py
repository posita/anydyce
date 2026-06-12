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

from . import jupyter_visualize
from .anydice import (
    DEFAULT_PRECISION,
    Settings,
    format_results,
    run,
)
from .anydice.fetch import fetch_anydice_program, is_pyodide
from .viz import BurstHPlotter, HorizontalBarHPlotter, LineHPlotter

__all__ = ("load_ipython_extension",)

_FORMAT_BAR = "bar"
_FORMAT_BURST = "burst"
_FORMAT_LINE = "line"
_FORMAT_TEXT = "text"
_FORMAT_TEXT_SHORT = "short-text"

_PLOTTER_NAMES_BY_FORMAT = {
    _FORMAT_BAR: HorizontalBarHPlotter.NAME,
    _FORMAT_BURST: BurstHPlotter.NAME,
    _FORMAT_LINE: LineHPlotter.NAME,
}

_OUTPUT_FORMAT = "output_format"


@magic_arguments()
@argument(
    f"--{_FORMAT_BAR}",
    action="store_const",
    const=_FORMAT_BAR,
    default=_FORMAT_TEXT,
    dest=_OUTPUT_FORMAT,
    help=f'use interactive visual formatting with "{_PLOTTER_NAMES_BY_FORMAT[_FORMAT_BAR]}" selected',
)
@argument(
    f"--{_FORMAT_BURST}",
    action="store_const",
    const=_FORMAT_BURST,
    dest=_OUTPUT_FORMAT,
    help=f'use interactive visual formatting with "{_PLOTTER_NAMES_BY_FORMAT[_FORMAT_BURST]}" selected',
)
@argument(
    f"--{_FORMAT_LINE}",
    action="store_const",
    const=_FORMAT_LINE,
    dest=_OUTPUT_FORMAT,
    help=f'use interactive visual formatting with "{_PLOTTER_NAMES_BY_FORMAT[_FORMAT_LINE]}" selected',
)
@argument(
    f"--{_FORMAT_TEXT}",
    action="store_const",
    const=_FORMAT_TEXT,
    dest=_OUTPUT_FORMAT,
    help="format each output as multi-line text",
)
@argument(
    f"--{_FORMAT_TEXT_SHORT}",
    action="store_const",
    const=_FORMAT_TEXT_SHORT,
    dest=_OUTPUT_FORMAT,
    help="format each output as single-line text",
)
@argument(
    "--precision",
    type=int,
    default=DEFAULT_PRECISION,
    help=f"number of decimal places used when formatting output values as text. Default: {DEFAULT_PRECISION}",
)
def anyd(line: str, cell: str) -> None:
    r"""
    Run the cell as legacy AnyDice source and display each output's distribution.

    Examples:

        %%anyd
        output 3d6

        %%anyd --bar
        output 3d6

        %%anyd --short --precision 32
        output 1d100
    """
    args = parse_argstring(anyd, line)

    with warnings.catch_warnings():
        # Everything other than a DeprecationWarning or ExperimentalWarning (e.g.,
        # TruncationWarning, etc.) should bubble up so Jupyter renders it next to the
        # cell output
        warnings.filterwarnings("ignore", category=DeprecationWarning)
        warnings.filterwarnings("ignore", category=ExperimentalWarning)
        # Seed the display precision from the CLI flag; `set "anydyce: display
        # precision"` inside the cell can override (the run() call mutates
        # settings in place). format_results then reads the final value.
        settings = Settings()
        settings.set("anydyce: display precision", args.precision)
        results = run(cell, settings=settings)
        if args.output_format in _PLOTTER_NAMES_BY_FORMAT:
            jupyter_visualize(
                results,
                selected_name=_PLOTTER_NAMES_BY_FORMAT[args.output_format],
            )
        else:
            print(
                format_results(
                    results,
                    settings=settings,
                    short=args.output_format == _FORMAT_TEXT_SHORT,
                )
            )


@magic_arguments()
@argument(
    "location_or_id",
    help="an AnyDice program ID or URL",
)
def anyd_load(line: str) -> None:
    r"""
    Fetch an AnyDice program by ID or URL and replace the cell with its source.

    Examples:

        %anyd_load 4d2
        %anyd_load https://anydice.com/program/4d2

    On success, the cell is replaced with an `%%anyd` cell containing the fetched
    program plus a comment header recording the source URL and fetch time. The replaced
    cell is *not* auto-executed. On failure (e.g., network error, missing program,
    etc.), the exception propagates to Jupyter and the original `%anyd_load` line is
    left in place.
    """
    args = parse_argstring(anyd_load, line)
    program_id_hex, initial_url, _final_url, program = fetch_anydice_program(
        args.location_or_id
    )
    fetched_at = datetime.now(UTC).astimezone().isoformat(timespec="seconds")
    new_cell = (
        "%%anyd\n"
        "\\ ================================================================================ /\n"
        f"  AnyDice program {program_id_hex} fetched from {initial_url}\n"
        f"  at {fetched_at} using:\n"
        f"  %anyd_load {args.location_or_id}\n"
        "/ ================================================================================ \\\n"
        f"{program}"
    )
    if is_pyodide():
        # Insert a space after any `\\<LF>` or `\\<CR>` so Python's tokenizer doesn't
        # treat the `\\` as a line continuation.
        #
        # JupyterLite's pyodide-kernel eagerly tokenizes cell-magic bodies as Python.
        # `\\<LF>` collapses lines via line continuation, often producing mixed-
        # indentation `IndentationError`s. Adding a space after `\\` breaks the
        # continuation. AnyDice ignores trailing whitespace after a comment-closing
        # `\\`, so this is a no-op for AnyDice parsing.
        new_cell = new_cell.replace("\\\n", "\\ \n").replace("\\\r", "\\ \r")
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
