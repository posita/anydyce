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
[AnyDice](https://anydice.com/)-compatible interpreter backed by [`dyce`](https://github.com/posita/dyce/) primitives.
"""

from pathlib import Path
from typing import cast

from dyce.lifecycle import experimental
from lark import Lark

from .ast_ import Program
from .interpreter import AnyDiceInterpreter, AnyDiceResultsT
from .transformer import AnyDiceTransformer
from .unparser import unparse

__all__ = (
    "DEFAULT_PRECISION",
    "AnyDiceInterpreter",
    "AnyDiceResultsT",
    "AnyDiceTransformer",
    "Program",
    "parse",
    "run",
    "unparse",
)

try:
    import warnings

    from dyce.h import (  # type: ignore[attr-defined]
        DEFAULT_PRECISION,  # pyrefly: ignore[missing-module-attribute] # pyright: ignore[reportAttributeAccessIssue] # ty: ignore[unresolved-import]
    )

    warnings.warn("dyce is sane now, remove this guard", stacklevel=0)
except ImportError:
    DEFAULT_PRECISION = 2

_GRAMMAR: str = (Path(__file__).parent / "grammar.lark").read_text()
_PARSER = Lark(_GRAMMAR, parser="lalr", transformer=AnyDiceTransformer())


@experimental
def format_results(
    results: AnyDiceResultsT, *, precision: int = DEFAULT_PRECISION, short: bool = False
) -> str:
    r"""
    Formats output results from [`run`][anydyce.anydice.run].

    >>> from anydyce.anydice import format_results, run
    >>> print(
    ...     format_results(
    ...         run('output 2d3 named "2d3" output d{} named "the empty die"')
    ...     )
    ... )
    ==== 2d3 ====
    avg |    4.00
    std |    1.15
    var |    1.33
      2 |  11.11% |#####
      3 |  22.22% |###########
      4 |  33.33% |################
      5 |  22.22% |###########
      6 |  11.11% |#####
    <BLANKLINE>
    ==== the empty die ====
    (empty distribution)

    >>> print(
    ...     format_results(
    ...         run('output [highest 3 of 4d6] named "4d6 drop lowest"'),
    ...         precision=4,
    ...         short=True,
    ...     )
    ... )
    ==== 4d6 drop lowest ====
    {avg: 12.24, 3:  0.0772%, 4:  0.3086%, 5:  0.7716%, ..., 16:  7.2531%, 17:  4.1667%, 18:  1.6204%}
    """
    blocks: list[str] = []

    for label, h in results:
        block = f"==== {label} ====\n"
        if not h:
            block += "(empty distribution)"
        elif short:
            block += h.format_short(precision=precision)
        else:
            block += h.format(precision=precision)
        blocks.append(block)

    return "\n\n".join(blocks) if blocks else "(no output)"


@experimental
def parse(source: str) -> Program:
    r"""
    Parses AnyDice source text into an AST [`Program`][anydyce.anydice.Program].

    Useful for (e.g.) passing to [`AnyDiceInterpreter.run`][anydice.anydice.AnyDiceInterpreter.run].
    """
    program = _PARSER.parse(source)
    if isinstance(program, Program):  # expected return value of our transformer
        return cast("Program", program)
    else:
        raise TypeError(
            f"expected type of program ({program!r}) to be {Program!r}, not {type(program)!r}"  # pragma: no cover
        )


@experimental
def run(source: str) -> AnyDiceResultsT:
    r"""
    Shorthand for `AnyDiceInterpreter().run(parse(source))`, returning one `(name, distribution)` pair per `output` statement.

    See [`parse`][anydyce.anydice.parse] and [`AnyDiceInterpreter.run`][anydice.anydice.AnyDiceInterpreter.run] for additional detail.
    """
    return AnyDiceInterpreter().run(parse(source))
