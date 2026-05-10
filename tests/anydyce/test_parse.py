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
from lark import UnexpectedInput

from dyce.anydyce import parse
from dyce.anydyce.ast_ import (
    BinOp,
    Call,
    DiceBinOp,
    DiceUnary,
    ElseBranch,
    EmptySeq,
    FunctionDef,
    HashOp,
    IfBranch,
    IfStmt,
    LoopStmt,
    NegOp,
    NotOp,
    Number,
    OutputStmt,
    Param,
    RangeElem,
    RangeRepeatElem,
    ResultStmt,
    SeqExpr,
    SetStmt,
    StringExpr,
    StrLit,
    StrVar,
    ValueElem,
    ValueRepeatElem,
    Var,
    VarAssign,
)

__all__ = ()

# ---- Operator precedence - unary operators -------------------------------------------


class TestUnaryPrecedence:
    def test_hash_of_dice_unary(self) -> None:
        # #d6 -> #(d6)
        # AnyDice: produces 1  (count of outcomes in one die)
        assert parse("output #d6").stmts == [
            OutputStmt(expr=HashOp(DiceUnary(Number(6))))
        ]

    def test_hash_of_not(self) -> None:
        # #!1 -> #(!1)
        # AnyDice: produces 1  (!1 = 0 scalar, #0 = 1)
        assert parse("output #!1").stmts == [OutputStmt(expr=HashOp(NotOp(Number(1))))]

    def test_not_of_hash(self) -> None:
        # !#1 -> !(#1)
        # AnyDice: produces 0  (#1 = 1, !1 = 0)
        assert parse("output !#1").stmts == [OutputStmt(expr=NotOp(HashOp(Number(1))))]

    def test_hash_number_then_binary_d(self) -> None:
        # #3d6 -> (#3)d6
        # AnyDice: identical to "output 1d6"  (#3 = 1, so 1d6)
        assert parse("output #3d6").stmts == [
            OutputStmt(expr=DiceBinOp(n=HashOp(Number(3)), faces=Number(6)))
        ]

    def test_neg_of_dice_unary(self) -> None:
        # -d6 -> -(d6)
        assert parse("output -d6").stmts == [
            OutputStmt(expr=NegOp(DiceUnary(Number(6))))
        ]

    def test_neg_of_hash(self) -> None:
        # -#1 -> -(#1)
        assert parse("output -#1").stmts == [OutputStmt(expr=NegOp(HashOp(Number(1))))]


# ---- Operator precedence - logical & and | -------------------------------------------


class TestLogicalPrecedence:
    def test_and_or_same_precedence_left_associative(self) -> None:
        # Per AnyDice's EBNF and verified empirically: `&` and `|` are at the
        # SAME precedence level (level 7) and left-associative.
        # `1 | 1 & 0` must parse as `(1 | 1) & 0`, which evaluates to 0.
        # (Verified against AnyDice's calculator.)
        # NOT C-style `1 | (1 & 0) = 1`.
        assert parse("output 1 | 1 & 0").stmts == [
            OutputStmt(expr=BinOp("&", BinOp("|", Number(1), Number(1)), Number(0)))
        ]

    def test_or_after_and_same_precedence_left_associative(self) -> None:
        # `1 & 0 | 1` parses as `(1 & 0) | 1` (same answer under either model
        # because of left-assoc, but the AST shape differs).
        assert parse("output 1 & 0 | 1").stmts == [
            OutputStmt(expr=BinOp("|", BinOp("&", Number(1), Number(0)), Number(1)))
        ]


# ---- Lexer: case-change token boundaries ---------------------------------------------


class TestCaseChangeTokenBarrier:
    # AnyDice's tokenizer treats case changes between adjacent characters as
    # token boundaries (no whitespace required). `_` is in the uppercase
    # character class (and thus a valid UPPERNAME by itself); transitions
    # between lowercase and uppercase/underscore split into separate tokens.
    # Verified by the user via:
    #   function: test_name { result: _ } output [test 3 name]
    # producing H({3: 1}) -- equivalent to `function: testVARname { result:
    # VAR }` with VAR=3.
    # Our regex-based lexer SHOULD handle this correctly since LOWERNAME and
    # UPPERNAME have disjoint character classes (`[a-z]` vs `[A-Z_]`), so
    # greedy match terminates at every case transition. This test locks
    # that in.

    def test_function_param_underscore_between_lowercase_words(self) -> None:
        # `test_name` -> ["test", UPPERNAME("_"), "name"], so the function
        # signature is [word("test"), param(name="_"), word("name")].
        assert parse("function: test_name { result: _ }").stmts == [
            FunctionDef(
                pattern=["test", Param(name="_", type=None), "name"],
                body=[ResultStmt(expr=Var("_"))],
            )
        ]

    def test_function_param_mixed_case_between_lowercase_words(self) -> None:
        # `testVARname` -> ["test", UPPERNAME("VAR"), "name"].
        assert parse("function: testVARname { result: VAR }").stmts == [
            FunctionDef(
                pattern=["test", Param(name="VAR", type=None), "name"],
                body=[ResultStmt(expr=Var("VAR"))],
            )
        ]

    def test_uppername_greedy_through_trailing_underscore(self) -> None:
        # `_NAME_` is a single UPPERNAME (no case change inside since `_` is
        # in the uppercase class). `_NAME_name` would split as
        # UPPERNAME("_NAME_") + LOWERNAME("name") because of the case
        # transition between `_` and `n`.
        assert parse("function: TEST_NAME_name { result: TEST_NAME_ }").stmts == [
            FunctionDef(
                pattern=[Param(name="TEST_NAME_", type=None), "name"],
                body=[ResultStmt(expr=Var("TEST_NAME_"))],
            )
        ]


# ---- Operator precedence - power -----------------------------------------------------


class TestPowerAssociativity:
    def test_power_is_left_associative(self) -> None:
        # AnyDice's `^` is left-associative (verified empirically: `2^3^2`
        # produces 64 = (2^3)^2, NOT 512 = 2^(3^2)). Most programming
        # languages have power as right-associative, so this is a divergence
        # from common convention. Our grammar's `pow_expr` is left-recursive,
        # matching AnyDice. Lock that in with a parse-shape test so we don't
        # accidentally flip it later.
        assert parse("output 2^3^2").stmts == [
            OutputStmt(expr=BinOp("^", BinOp("^", Number(2), Number(3)), Number(2)))
        ]


# ---- STRING is not a value type ------------------------------------------------------


class TestStringNotAValue:
    # STRING is only syntactically valid in two positions:
    #   1. `set <STRING> to <STRING|operation>` (key and optional value)
    #   2. `output <operation> named <STRING>` (named clause)
    # Anywhere else `expr`/`operation` is allowed, STRING is a parse error.
    # AnyDice has no string type; treating STRING as a general value form
    # would be a real semantic divergence. (Empirically verified: AnyDice
    # rejects `output 1 named 1` and similar shape errors at the named slot.)

    def test_output_named_requires_string_literal(self) -> None:
        # `output X named <non-STRING>` should be a parse error. AnyDice
        # rejects `output 1 named 1` (number in the named slot).
        with pytest.raises(UnexpectedInput):
            parse("output 1 named 1")

    def test_string_rejected_in_var_assign_value(self) -> None:
        # X: "foo" is not a valid assignment in AnyDice (STRING isn't a value).
        with pytest.raises(UnexpectedInput):
            parse('X: "foo"')

    def test_string_rejected_in_function_argument(self) -> None:
        # Functions can't take STRING as an argument; only operations.
        with pytest.raises(UnexpectedInput):
            parse('output [foo "bar"]')

    def test_string_rejected_in_arithmetic(self) -> None:
        # No string concatenation or other operator semantics.
        with pytest.raises(UnexpectedInput):
            parse('output "a" + "b"')

    def test_string_rejected_in_seq_literal(self) -> None:
        # Sequence elements are operations only, not STRING.
        with pytest.raises(UnexpectedInput):
            parse('output {"a", "b"}')

    # The valid positions still parse normally:

    def test_output_named_string_still_parses(self) -> None:
        # Smoke test: the legitimate `output X named "..."` form still works.
        assert parse('output 1 named "label"').stmts == [
            OutputStmt(expr=Number(1), name=StringExpr(parts=[StrLit("label")]))
        ]

    def test_set_to_string_still_parses(self) -> None:
        # Smoke test: `set "x" to "y"` is the canonical AnyDice form for
        # string-valued settings.
        assert parse('set "position order" to "highest first"').stmts == [
            SetStmt(
                key="position order",
                value=StringExpr(parts=[StrLit("highest first")]),
            )
        ]

    def test_set_to_expr_still_parses(self) -> None:
        # Smoke test: `set "x" to <number>` and arbitrary expressions remain
        # valid (per user's empirical probe with `set "max ..." to (2@{1..3})`).
        assert parse('set "maximum function depth" to 5').stmts == [
            SetStmt(key="maximum function depth", value=Number(5))
        ]


# ---- Dice operator -------------------------------------------------------------------


class TestDiceOperator:
    def test_binary_d(self) -> None:
        assert parse("output 2d6").stmts == [
            OutputStmt(expr=DiceBinOp(n=Number(2), faces=Number(6)))
        ]

    def test_unary_d(self) -> None:
        assert parse("output d6").stmts == [OutputStmt(expr=DiceUnary(faces=Number(6)))]

    def test_binary_d_parenthesized_n(self) -> None:
        # (1+1) binds as a unit before d; sister of test_unparse.py::test_dice_binop_lower_prec_n_needs_parens
        assert parse("output (1+1)d6").stmts == [
            OutputStmt(
                expr=DiceBinOp(n=BinOp("+", Number(1), Number(1)), faces=Number(6))
            )
        ]

    def test_binary_d_right_operand_is_seq(self) -> None:
        assert parse("output 1d{1,2,3}").stmts == [
            OutputStmt(
                expr=DiceBinOp(
                    n=Number(1),
                    faces=SeqExpr(
                        elems=[
                            ValueElem(Number(1)),
                            ValueElem(Number(2)),
                            ValueElem(Number(3)),
                        ]
                    ),
                )
            )
        ]


# ---- Sequences -----------------------------------------------------------------------


class TestSequences:
    def test_empty_seq(self) -> None:
        assert parse("output {}").stmts == [OutputStmt(expr=EmptySeq())]

    def test_value_list(self) -> None:
        assert parse("output {1,2,3}").stmts == [
            OutputStmt(
                expr=SeqExpr(
                    elems=[
                        ValueElem(Number(1)),
                        ValueElem(Number(2)),
                        ValueElem(Number(3)),
                    ]
                )
            )
        ]

    def test_range(self) -> None:
        assert parse("output {1..3}").stmts == [
            OutputStmt(expr=SeqExpr(elems=[RangeElem(Number(1), Number(3))]))
        ]

    def test_range_repeat(self) -> None:
        assert parse("output {1..3:2}").stmts == [
            OutputStmt(
                expr=SeqExpr(elems=[RangeRepeatElem(Number(1), Number(3), Number(2))])
            )
        ]

    def test_range_with_whitespace_between_dots(self) -> None:
        # AnyDice's "smart tokenizer" allows whitespace between the two dots
        # of the `..` range operator. Verified empirically against AnyDice.
        expected_range = [
            OutputStmt(expr=SeqExpr(elems=[RangeElem(Number(2), Number(3))]))
        ]
        assert parse("output {2..3}").stmts == expected_range
        assert parse("output {2. .3}").stmts == expected_range
        assert parse("output {2 . . 3}").stmts == expected_range
        assert parse("output {2.  .3}").stmts == expected_range

        expected_range_repeat = [
            OutputStmt(
                expr=SeqExpr(elems=[RangeRepeatElem(Number(2), Number(3), Number(4))])
            )
        ]
        assert parse("output {2..3:4}").stmts == expected_range_repeat
        assert parse("output {2 . . 3 : 4}").stmts == expected_range_repeat

    def test_value_repeat(self) -> None:
        assert parse("output {1:4}").stmts == [
            OutputStmt(expr=SeqExpr(elems=[ValueRepeatElem(Number(1), Number(4))]))
        ]

    def test_mixed_seq_elems(self) -> None:
        assert parse("output {1..3, 5:2, 7}").stmts == [
            OutputStmt(
                expr=SeqExpr(
                    elems=[
                        RangeElem(Number(1), Number(3)),
                        ValueRepeatElem(Number(5), Number(2)),
                        ValueElem(Number(7)),
                    ]
                )
            )
        ]

    def test_nested_seq(self) -> None:
        # Three levels of nesting, all element types present at each level
        assert parse("output {1..3, {4, 5:2, 6..8, {9:3, 10..12}}, 13}").stmts == [
            OutputStmt(
                expr=SeqExpr(
                    elems=[
                        RangeElem(Number(1), Number(3)),
                        ValueElem(
                            SeqExpr(
                                elems=[
                                    ValueElem(Number(4)),
                                    ValueRepeatElem(Number(5), Number(2)),
                                    RangeElem(Number(6), Number(8)),
                                    ValueElem(
                                        SeqExpr(
                                            elems=[
                                                ValueRepeatElem(Number(9), Number(3)),
                                                RangeElem(Number(10), Number(12)),
                                            ]
                                        )
                                    ),
                                ]
                            )
                        ),
                        ValueElem(Number(13)),
                    ]
                )
            )
        ]


# ---- Statements ----------------------------------------------------------------------


class TestStatements:
    def test_output_anon(self) -> None:
        assert parse("output 1").stmts == [OutputStmt(expr=Number(1), name=None)]

    def test_output_named(self) -> None:
        assert parse('output 1 named "one"').stmts == [
            OutputStmt(expr=Number(1), name=StringExpr([StrLit("one")]))
        ]

    def test_var_assign(self) -> None:
        assert parse("X: 3").stmts == [VarAssign(name="X", expr=Number(3))]

    def test_set_stmt(self) -> None:
        assert parse('set "order" to "lowest first"').stmts == [
            SetStmt(key="order", value=StringExpr([StrLit("lowest first")]))
        ]

    def test_set_stmt_numeric_value(self) -> None:
        assert parse('set "maximum function depth" to 10').stmts == [
            SetStmt(key="maximum function depth", value=Number(10))
        ]

    def test_result_stmt_only_in_function_body(self) -> None:
        # "result: X" at top level should be a parse error
        with pytest.raises(UnexpectedInput):
            parse("result: 1")

    def test_output_not_in_function_body(self) -> None:
        # "output" inside a function body should be a parse error
        with pytest.raises(UnexpectedInput):
            parse("function: foo { output 1 }")

    def test_function_def_not_nested(self) -> None:
        # Nested function definitions should be a parse error
        with pytest.raises(UnexpectedInput):
            parse("function: outer { function: inner { result: 1 } }")

    def test_set_not_in_function_body(self) -> None:
        # "set" inside a function body should be a parse error
        with pytest.raises(UnexpectedInput):
            parse('function: foo { set "maximum function depth" to 5 result: 1 }')

    def test_lowercase_loop_var_is_error(self) -> None:
        # Loop variable must be UPPERNAME
        with pytest.raises(UnexpectedInput):
            parse("loop x over {1..3} { output x }")

    def test_lowercase_var_assign_is_error(self) -> None:
        # Variable assignment target must be UPPERNAME
        with pytest.raises(UnexpectedInput):
            parse("x: 3")


# ---- Function definitions ------------------------------------------------------------


class TestFunctionDef:
    def test_simple_function(self) -> None:
        assert parse("function: double X { result: X + X }").stmts == [
            FunctionDef(
                pattern=["double", Param("X", None)],
                body=[ResultStmt(BinOp("+", Var("X"), Var("X")))],
            )
        ]

    def test_typed_param(self) -> None:
        assert parse("function: roll X:d { result: X }").stmts == [
            FunctionDef(
                pattern=["roll", Param("X", "d")],
                body=[ResultStmt(Var("X"))],
            )
        ]

    def test_zero_word_function(self) -> None:
        # AnyDice allows functions that are pure params with no keyword words
        assert parse("function: X:n Y:n { result: X + Y }").stmts == [
            FunctionDef(
                pattern=[Param("X", "n"), Param("Y", "n")],
                body=[ResultStmt(BinOp("+", Var("X"), Var("Y")))],
            )
        ]

    def test_zero_word_bare_param_function(self) -> None:
        assert parse("function: X Y { result: X + Y }").stmts == [
            FunctionDef(
                pattern=[Param("X", None), Param("Y", None)],
                body=[ResultStmt(BinOp("+", Var("X"), Var("Y")))],
            )
        ]

    def test_single_word_no_param_function(self) -> None:
        assert parse("function: attack { result: 1 }").stmts == [
            FunctionDef(
                pattern=["attack"],
                body=[ResultStmt(Number(1))],
            )
        ]

    def test_d_as_function_word(self) -> None:
        # "d" is a valid word in a function name pattern
        assert parse("function: A d B { result: BdA }").stmts == [
            FunctionDef(
                pattern=[Param("A", None), "d", Param("B", None)],
                body=[ResultStmt(DiceBinOp(Var("B"), Var("A")))],
            )
        ]

    def test_d_in_call_is_binary_dice(self) -> None:
        # In a call expression, "d" is always the binary dice operator, never a word. [4
        # d 6] parses as [4d6]. A single-argument call with DiceBinOp(4, 6). This means
        # a function defined as "function: A d B" cannot be called as [4 d 6]. The call
        # must be written as [4d6] instead, and the interpreter matches on arity.
        assert parse("output [4 d 6]").stmts == [
            OutputStmt(expr=Call(parts=[DiceBinOp(Number(4), Number(6))]))
        ]


# ---- Control flow --------------------------------------------------------------------


class TestControlFlow:
    def test_loop_stmt(self) -> None:
        assert parse("loop X over {1..3} { output X }").stmts == [
            LoopStmt(
                var="X",
                over=SeqExpr([RangeElem(Number(1), Number(3))]),
                body=[OutputStmt(Var("X"))],
            )
        ]

    def test_if_stmt(self) -> None:
        assert parse("if 1 { output 2 }").stmts == [
            IfStmt(
                branches=[IfBranch(Number(1), [OutputStmt(Number(2))])],
                else_branch=None,
            )
        ]

    def test_if_else(self) -> None:
        assert parse("if 1 { output 2 } else { output 3 }").stmts == [
            IfStmt(
                branches=[IfBranch(Number(1), [OutputStmt(Number(2))])],
                else_branch=ElseBranch([OutputStmt(Number(3))]),
            )
        ]

    def test_if_elseif(self) -> None:
        assert parse("if 1 { output 2 } else if 3 { output 4 }").stmts == [
            IfStmt(
                branches=[
                    IfBranch(Number(1), [OutputStmt(Number(2))]),
                    IfBranch(Number(3), [OutputStmt(Number(4))]),
                ],
                else_branch=None,
            )
        ]


# ---- String interpolation ------------------------------------------------------------


class TestStringInterpolation:
    def test_plain_string(self) -> None:
        assert parse('output 1 named "hello"').stmts == [
            OutputStmt(Number(1), name=StringExpr([StrLit("hello")]))
        ]

    def test_interpolated_string(self) -> None:
        assert parse('output 1 named "roll [X]"').stmts == [
            OutputStmt(Number(1), name=StringExpr([StrLit("roll "), StrVar("X")]))
        ]

    def test_string_only_var(self) -> None:
        assert parse('output 1 named "[X]"').stmts == [
            OutputStmt(Number(1), name=StringExpr([StrVar("X")]))
        ]


# ---- Binary operators ----------------------------------------------------------------


class TestBinaryOps:
    def test_add(self) -> None:
        assert parse("output 1 + 2").stmts == [
            OutputStmt(BinOp("+", Number(1), Number(2)))
        ]

    def test_left_assoc_grouping(self) -> None:
        # 1 - 2 - 3 -> (1-2) - 3; sister of test_unparse.py::test_left_assoc_same_op_no_extra_parens
        assert parse("output 1 - 2 - 3").stmts == [
            OutputStmt(BinOp("-", BinOp("-", Number(1), Number(2)), Number(3)))
        ]

    def test_right_assoc_explicit_parens(self) -> None:
        # 1 - (2-3) is a distinct grouping from (1-2)-3; sister of test_unparse.py::test_right_same_op_needs_parens
        assert parse("output 1 - (2 - 3)").stmts == [
            OutputStmt(BinOp("-", Number(1), BinOp("-", Number(2), Number(3))))
        ]

    def test_lower_prec_in_mul_needs_explicit_parens(self) -> None:
        # (1+2)*3 groups the add first; sister of test_unparse.py::test_lower_prec_left_child_needs_parens
        assert parse("output (1 + 2) * 3").stmts == [
            OutputStmt(BinOp("*", BinOp("+", Number(1), Number(2)), Number(3)))
        ]

    def test_precedence_mul_over_add(self) -> None:
        # 1 + 2 * 3 -> 1 + (2 * 3)
        assert parse("output 1 + 2 * 3").stmts == [
            OutputStmt(BinOp("+", Number(1), BinOp("*", Number(2), Number(3))))
        ]

    def test_at_operator(self) -> None:
        assert parse("output 2@d6").stmts == [
            OutputStmt(BinOp("@", Number(2), DiceUnary(Number(6))))
        ]

    def test_comparison(self) -> None:
        assert parse("output 1 = 1").stmts == [
            OutputStmt(BinOp("=", Number(1), Number(1)))
        ]
