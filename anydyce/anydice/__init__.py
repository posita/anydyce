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
AnyDice-compatible interpreter backed by dyce primitives.
"""

from pathlib import Path
from typing import cast

from lark import Lark

from .ast_ import Program
from .interpreter import AnyDiceInterpreter, AnyDiceResultsT
from .transformer import AnyDiceTransformer
from .unparser import unparse

__all__ = ("DEFAULT_PRECISION", "parse", "run", "unparse")

# The default precision to be passed to H.format() for any user-facing presentation
# TODO(posita): # noqa: TD003 - Propagate this?
DEFAULT_PRECISION = 2

_GRAMMAR: str = (Path(__file__).parent / "grammar.lark").read_text()
_PARSER = Lark(_GRAMMAR, parser="lalr", transformer=AnyDiceTransformer())


def format_anydice_results(
    results: AnyDiceResultsT, *, precision: int = DEFAULT_PRECISION, short: bool = False
) -> str:
    r"""
    Formats output results from [`run`][anydyce.anydice.run].

    >>> from anydyce.anydice import format_anydice_results, run
    >>> print(
    ...     format_anydice_results(
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
    ...     format_anydice_results(
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


def parse(source: str) -> Program:
    r"""
    Parses AnyDice source text into an AST [`Program`][anydyce.anydice.ast_.Program].

    Useful for (e.g.) passing to [`AnyDiceInterpreter.run`][anydice.anydice.interpreter.AnyDiceInterpreter.run].
    """
    program = _PARSER.parse(source)
    if isinstance(program, Program):  # expected return value of our transformer
        return cast("Program", program)
    else:
        raise TypeError(
            f"expected type of program ({program!r}) to be {Program!r}, not {type(program)!r}"  # pragma: no cover
        )


def run(source: str) -> AnyDiceResultsT:
    r"""
    Shorthand for `#!python AnyDiceInterpreter().run(parse(source))`, returning one `#!python (name, distribution)` pair per `output` statement.

    See [`parse`][anydyce.anydice.parse] and [`AnyDiceInterpreter.run`][anydice.anydice.interpreter.AnyDiceInterpreter.run] for additional detail.
    """
    return AnyDiceInterpreter().run(parse(source))
