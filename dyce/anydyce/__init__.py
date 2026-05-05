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

__all__ = ("parse", "run", "unparse")

_GRAMMAR: str = (Path(__file__).parent / "grammar.lark").read_text()
_PARSER = Lark(_GRAMMAR, parser="lalr", transformer=AnyDiceTransformer())


def run(source: str) -> AnyDiceResultsT:
    r"""Run AnyDice source text and return `(name, distribution)` pairs, one per `output` statement."""
    program = parse(source)
    return AnyDiceInterpreter().run(program)


def parse(source: str) -> Program:
    r"""Parse AnyDice source text and return an AST [`Program`][dyce.anydyce.ast_.Program]."""
    # The cast is necessary because, despite its type hint, parse will return an
    # instance of whatever is created by the provided transformer. Since we provide one,
    # and we know what its output should be, we check and then safely cast it.
    program = _PARSER.parse(source)
    if isinstance(program, Program):
        return cast("Program", program)
    else:
        raise TypeError(
            f"expected type of program ({program!r}) to be {Program!r}, not {type(program)!r}"  # pragma: no cover
        )
