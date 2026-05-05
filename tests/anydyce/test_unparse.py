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

import pytest

from dyce.anydyce import parse, unparse

__all__ = ()

# ---- Golden output -------------------------------------------------------------------


class TestUnparseStatements:
    def test_output_anon(self) -> None:
        src = "output 1"
        assert unparse(parse(src)) == src

    def test_output_named(self) -> None:
        src = 'output 1 named "hello"'
        assert unparse(parse(src)) == src

    def test_var_assign(self) -> None:
        src = "X: 3"
        assert unparse(parse(src)) == src

    def test_set_stmt(self) -> None:
        src = 'set "order" to 1'
        assert unparse(parse(src)) == src

    def test_function_def(self) -> None:
        src = "function: double X {\n    result: X + X\n}"
        assert unparse(parse(src)) == src

    def test_function_def_typed_param(self) -> None:
        src = "function: roll X:d {\n    result: X\n}"
        assert unparse(parse(src)) == src

    def test_function_def_multi_word(self) -> None:
        src = "function: highest X:n of Y:d {\n    result: X\n}"
        assert unparse(parse(src)) == src

    def test_loop_stmt(self) -> None:
        src = "loop X over {1..3} {\n    output X\n}"
        assert unparse(parse(src)) == src

    def test_if_stmt(self) -> None:
        src = "if 1 {\n    output 2\n}"
        assert unparse(parse(src)) == src

    def test_if_else(self) -> None:
        src = "if 1 {\n    output 2\n} else {\n    output 3\n}"
        assert unparse(parse(src)) == src

    def test_if_elseif_else(self) -> None:
        src = "if 1 {\n    output 2\n} else if 3 {\n    output 4\n} else {\n    output 5\n}"
        assert unparse(parse(src)) == src

    def test_multiline_program(self) -> None:
        src = "X: 3d6\noutput X"
        assert unparse(parse(src)) == src


class TestUnparseExpressions:
    @pytest.mark.parametrize(
        "src",
        [
            "output 42",
            "output X",
            "output {}",
            "output {1, 2, 3}",
            "output {1..3}",
            "output {1..3:2}",
            "output {1:4}",
            "output {1..3, 5:2, 7}",
            'output 1 named "roll [X]"',
            "output [highest 2 of 4d6]",
            "output #d6",
            "output !1",
            "output -1",
            "output +1",
            "output d6",
            "output 2d6",
            "output 1 + 2",
            "output 1 - 2",
            "output 1 * 2",
            "output 1 / 2",
            "output 1 ^ 2",
            "output 1 | 2",
            "output 1 & 2",
            "output 1 = 2",
            "output 1 != 2",
            "output 1 < 2",
            "output 1 > 2",
            "output 1 <= 2",
            "output 1 >= 2",
            "output 2 @ d6",
        ],
    )
    def test_golden(self, src: str) -> None:
        assert unparse(parse(src)) == src


# ---- Operator precedence -------------------------------------------------------------


class TestUnparsePrecedence:
    def test_left_assoc_same_op_no_extra_parens(self) -> None:
        # (1-2)-3 is the natural left-assoc parse of "1 - 2 - 3". The unparser must not
        # emit the redundant outer parens on the left child.
        assert unparse(parse("output (1 - 2) - 3")) == "output 1 - 2 - 3"

    def test_right_same_op_needs_parens(self) -> None:
        # 1-(2-3) != (1-2)-3, so parens are required on the right child when it has the
        # same precedence as its parent (all ops are left-associative).
        assert unparse(parse("output 1 - (2 - 3)")) == "output 1 - (2 - 3)"

    def test_higher_prec_left_child_no_parens(self) -> None:
        # 1*2 binds tighter than +, so (1*2)+3 is canonical without parens on the left
        # child.
        assert unparse(parse("output 1 * 2 + 3")) == "output 1 * 2 + 3"

    def test_lower_prec_left_child_needs_parens(self) -> None:
        # + binds looser than *, so (1+2)*3 must keep its parens.
        assert unparse(parse("output (1 + 2) * 3")) == "output (1 + 2) * 3"

    def test_lower_prec_right_child_needs_parens(self) -> None:
        # + binds looser than *: 3*(1+2) must keep its parens on the right child even
        # though the left child has no issue.
        assert unparse(parse("output 3 * (1 + 2)")) == "output 3 * (1 + 2)"

    def test_pow_right_group_needs_parens(self) -> None:
        # ^ is left-associative, so 1^(2^3) must keep its parens.
        assert unparse(parse("output 1 ^ (2 ^ 3)")) == "output 1 ^ (2 ^ 3)"

    def test_pow_left_assoc_no_extra_parens(self) -> None:
        # (1^2)^3 is the natural left-assoc parse. Redundant parens must be stripped.
        assert unparse(parse("output (1 ^ 2) ^ 3")) == "output 1 ^ 2 ^ 3"

    def test_dice_binop_lower_prec_n_needs_parens(self) -> None:
        # The n side of nDm is evaluated at _PREC_DICE_BIN. Any expression with lower
        # precedence (like +) must be parenthesised.
        assert unparse(parse("output (1 + 1)d6")) == "output (1 + 1)d6"

    def test_dice_binop_faces_dice_unary_needs_parens(self) -> None:
        # DiceUnary as faces would produce "2dd6", but the lexer merges "dd" as a single
        # LOWERNAME token, making it unparsable. The unparser must emit "2d(d6)"
        # instead.
        assert unparse(parse("output 2d(d6)")) == "output 2d(d6)"

    def test_dice_unary_faces_dice_unary_needs_parens(self) -> None:
        # Same lexer hazard for DiceUnary containing DiceUnary: "d" followed by "d6"
        # would produce "dd6" (LOWERNAME). The unparser must emit "d(d6)".
        assert unparse(parse("output d(d6)")) == "output d(d6)"

    def test_at_lower_prec_than_dice_no_parens(self) -> None:
        # @ binds looser than d, so "2 @ d6" needs no parens around d6.
        assert unparse(parse("output 2@d6")) == "output 2 @ d6"

    def test_at_right_group_needs_parens(self) -> None:
        # @ is left-associative, so 1@(2@d6) must keep its parens.
        assert unparse(parse("output 1 @ (2 @ d6)")) == "output 1 @ (2 @ d6)"

    def test_hash_of_unary_no_extra_parens(self) -> None:
        # # and d are both unary (same prec), so #d6 needs no parens; sister of test_parse.py::test_hash_of_dice_unary
        assert unparse(parse("output #d6")) == "output #d6"

    def test_hash_of_not_no_extra_parens(self) -> None:
        # # and ! are both unary (same prec), so #!1 needs no parens; sister of test_parse.py::test_hash_of_not
        assert unparse(parse("output #!1")) == "output #!1"

    def test_not_of_hash_no_extra_parens(self) -> None:
        # ! and # are both unary (same prec), so !#1 needs no parens; sister of test_parse.py::test_not_of_hash
        assert unparse(parse("output !#1")) == "output !#1"

    def test_hash_as_dice_n_no_extra_parens(self) -> None:
        # # (prec=unary=9) binds tighter than d-as-n (prec=8), so #3d6 needs no parens; sister of test_parse.py::test_hash_number_then_binary_d
        assert unparse(parse("output #3d6")) == "output #3d6"

    def test_hash_lower_prec_operand_needs_parens(self) -> None:
        # + (prec=4) is lower than unary (prec=9), so # forces parens around 1+2
        assert unparse(parse("output #(1 + 2)")) == "output #(1 + 2)"

    def test_neg_of_unary_no_extra_parens(self) -> None:
        # - and d are both unary (same prec), so -d6 needs no parens; sister of test_parse.py::test_neg_of_dice_unary
        assert unparse(parse("output -d6")) == "output -d6"


# ---- Round-trip ----------------------------------------------------------------------

_ROUND_TRIP_SOURCES = [
    "output 1",
    "output 2d6",
    "output d6 + d8",
    'output d6 named "d6"',
    "X: 3d6\noutput X",
    'set "order" to "lowest first"\noutput d6',
    "function: double X:n {\n    result: X * 2\n}\noutput [double 3]",
    "loop X over {1..3} {\n    output X\n}",
    "if 1 {\n    output 2\n} else {\n    output 3\n}",
    "if 1 {\n    output 2\n} else if 3 {\n    output 4\n} else {\n    output 5\n}",
    "output {1, 2, 3:2, 4..6, 7..9:3}",
    'output 1 named "roll [X]"',
    "output [highest 2 of 4d6]",
    "output 1 + 2 * 3",
    "output (1 + 2) * 3",
    "output 1 - (2 - 3)",
    "output #3d6",
    "output !1 & 1 = 1",
]


class TestUnparseRoundTrip:
    @pytest.mark.parametrize("src", _ROUND_TRIP_SOURCES)
    def test_ast_stable(self, src: str) -> None:
        # parse(unparse(parse(src))) must produce the same AST as parse(src).
        assert parse(unparse(parse(src))) == parse(src)

    @pytest.mark.parametrize("src", _ROUND_TRIP_SOURCES)
    def test_output_idempotent(self, src: str) -> None:
        # unparse is idempotent: applying it twice yields the same string.
        first = unparse(parse(src))
        assert unparse(parse(first)) == first
