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
from lark.exceptions import UnexpectedInput

from dyce import H, P
from dyce.anydyce import run

__all__ = ()

# ---- Literals and output -----------------------------------------------------------------


class TestLiterals:
    def test_zero_output(self) -> None:
        assert run("output 0") == [("output 1", H({0: 1}))]

    def test_num_output(self) -> None:
        assert run("output 1") == [("output 1", H({1: 1}))]

    def test_negative_output(self) -> None:
        assert run("output -3") == [("output 1", H({-3: 1}))]

    def test_named_output(self) -> None:
        assert run('output 1 named "one"') == [("one", H({1: 1}))]

    def test_multiple_outputs(self) -> None:
        assert run("output 1\noutput 2") == [
            ("output 1", H({1: 1})),
            ("output 2", H({2: 1})),
        ]

    def test_multiple_named_outputs(self) -> None:
        assert run('output 1 named "a"\noutput 2 named "b"') == [
            ("a", H({1: 1})),
            ("b", H({2: 1})),
        ]


# ---- Dice --------------------------------------------------------------------------------


class TestDieUnary:
    def test_d_empty_seq(self) -> None:
        assert run("output d{}") == [("output 1", H({}))]

    def test_d_num_zero(self) -> None:
        assert run("output d0") == [("output 1", H({0: 1}))]

    def test_d_num_one(self) -> None:
        assert run("output d1") == [("output 1", H(1))]

    def test_d_num(self) -> None:
        assert run("output d6") == [("output 1", H(6))]

    def test_d_seq(self) -> None:
        assert run("output d{1,2,3}") == [("output 1", H({1: 1, 2: 1, 3: 1}))]

    def test_d_weighted_seq(self) -> None:
        # {2,2,4}: die twice as likely to show 2 as 4
        assert run("output d{2,2,4}") == [("output 1", H({2: 2, 4: 1}))]

    def test_d_die(self) -> None:
        # d(die) uses die's outcomes as faces; d(d6) is equivalent (same AST)
        assert run("output d(d6)") == [("output 1", H(6))]


class TestDieBinary:
    def test_zero_d_empty_seq(self) -> None:
        assert run("output 0d{}") == [("output 1", H({}))]

    def test_num_d_empty_seq(self) -> None:
        assert run("output 2d{}") == [("output 1", H({}))]

    def test_zero_d_num(self) -> None:
        # 0 dice: AnyDice yields 0
        assert run("output 0d6") == [("output 1", H({0: 1}))]

    def test_one_d_num(self) -> None:
        assert run("output 1d6") == [("output 1", H(6))]

    def test_num_d_num(self) -> None:
        assert run("output 2d6") == [("output 1", H(6) + H(6))]

    def test_num_d_seq(self) -> None:
        assert run("output 2d{1,2,3}") == [
            ("output 1", H({1: 1, 2: 1, 3: 1}) + H({1: 1, 2: 1, 3: 1}))
        ]

    def test_num_d_die(self) -> None:
        # 2d(d6): d6's outcomes are the faces, rolled twice
        assert run("output 2d(d6)") == [("output 1", H(6) + H(6))]

    def test_seq_d_num(self) -> None:
        # {1,2}=3; seq coerces to sum as count -> 3d6
        assert run("output {1,2}d6") == [("output 1", H(6) + H(6) + H(6))]

    def test_seq_d_seq(self) -> None:
        # {1,2}=3; 3d{3,4}
        assert run("output {1,2}d{3,4}") == [
            ("output 1", H({9: 1, 10: 3, 11: 3, 12: 1}))
        ]

    def test_seq_d_die(self) -> None:
        # {1,2}=3; d(d6)=d6; 3d6
        assert run("output {1,2}d(d6)") == [("output 1", H(6) + H(6) + H(6))]

    def test_die_d_num(self) -> None:
        # AnyDice expands a die-count over its outcomes; for d2d2:
        # k=1 (w=1) -> 1d2 = H({1:1, 2:1}), total 2
        # k=2 (w=1) -> 2d2 = H({2:1, 3:2, 4:1}), total 4
        # LCM=4. Scale 1d2 by 2: {1:2, 2:2}. Scale 2d2 by 1: {2:1, 3:2, 4:1}.
        # Combined: {1:2, 2:3, 3:2, 4:1}.
        assert run("output d2d2") == [("output 1", H({1: 2, 2: 3, 3: 2, 4: 1}))]

    def test_die_d_seq(self) -> None:
        # d2 d {2,4}: k=1 -> 1d{2,4} = H({2:1, 4:1}); k=2 -> 2d{2,4} =
        # H({4:1, 6:2, 8:1}). LCM(2, 4)=4: scaled to {2:2, 4:2} and
        # {4:1, 6:2, 8:1}. Combined: {2:2, 4:3, 6:2, 8:1}.
        assert run("output d2d{2,4}") == [("output 1", H({2: 2, 4: 3, 6: 2, 8: 1}))]

    def test_die_d_die(self) -> None:
        # Outer count is d2 again; inner faces is d2. k=1 -> 1d(d2) = d2 =
        # H({1:1, 2:1}); k=2 -> 2d(d2) = H({2:1, 3:2, 4:1}). Same shape as
        # d2d2 above.
        assert run("output d2d(d2)") == [("output 1", H({1: 2, 2: 3, 3: 2, 4: 1}))]

    def test_weighted_die_d_die(self) -> None:
        # Outer count is weighted d{1:3, 2:1}; inner faces is d2.
        # k=1 (w=3) -> 1d2 = H({1:1, 2:1}), total 2
        # k=2 (w=1) -> 2d2 = H({2:1, 3:2, 4:1}), total 4
        # LCM=4. Scaled inner: {1:2, 2:2} and {2:1, 3:2, 4:1}.
        # Multiplied by outer weights:
        #   {1: 6, 2: 6} + {2: 1, 3: 2, 4: 1} = {1:6, 2:7, 3:2, 4:1}.
        assert run("output d{1:3, 2:1} d 2") == [
            ("output 1", H({1: 6, 2: 7, 3: 2, 4: 1}))
        ]

    def test_die_d_weighted_die(self) -> None:
        # Outer count is d2; inner faces is weighted H({1:3, 2:1}).
        # k=1 (w=1) -> 1d{1:3, 2:1} = H({1:3, 2:1}), total 4
        # k=2 (w=1) -> 2d{1:3, 2:1}: outcomes 1+1, 1+2, 2+1, 2+2 with weights
        # 9, 3, 3, 1 -> H({2:9, 3:6, 4:1}), total 16.
        # LCM=16. Scaled: {1:12, 2:4} and {2:9, 3:6, 4:1}.
        # Combined: {1:12, 2:13, 3:6, 4:1}.
        assert run("output d2 d {1:3, 2:1}") == [
            ("output 1", H({1: 12, 2: 13, 3: 6, 4: 1}))
        ]

    def test_weighted_die_d_weighted_die(self) -> None:
        # Both sides weighted. Combines the two cases above.
        # k=1 (w=3) -> H({1:3, 2:1}), scaled by 4 -> {1:12, 2:4} -> *3 outer
        # k=2 (w=1) -> H({2:9, 3:6, 4:1}) -> *1 outer
        # Combined: {1:36, 2:21, 3:6, 4:1}.
        assert run("output d{1:3, 2:1} d {1:3, 2:1}") == [
            ("output 1", H({1: 36, 2: 21, 3: 6, 4: 1}))
        ]


# ---- Variables ---------------------------------------------------------------------------


class TestVariables:
    def test_num_variable(self) -> None:
        assert run("X: 5\noutput X") == [("output 1", H({5: 1}))]

    def test_seq_variable(self) -> None:
        assert run("X: {1..3}\noutput X") == [("output 1", H({1: 1, 2: 1, 3: 1}))]

    def test_die_variable(self) -> None:
        assert run("X: d6\noutput X") == [("output 1", H(6))]

    def test_variable_in_expression(self) -> None:
        assert run("X: 3\noutput X + 2") == [("output 1", H({5: 1}))]

    def test_variable_chain(self) -> None:
        assert run("X: d6\nY: X\noutput Y") == [("output 1", H(6))]


# ---- Sequences ---------------------------------------------------------------------------


class TestSequences:
    def test_sequence_output(self) -> None:
        assert run("output {1,2,3}") == [("output 1", H({1: 1, 2: 1, 3: 1}))]

    def test_sequence_with_repeats(self) -> None:
        assert run("output {2,2,4}") == [("output 1", H({2: 2, 4: 1}))]

    def test_range(self) -> None:
        assert run("output {1..3}") == [("output 1", H({1: 1, 2: 1, 3: 1}))]

    def test_range_repeat(self) -> None:
        # each value in 1..3 appears twice; weights are not GCD-reduced
        assert run("output {1..3:2}") == [("output 1", H({1: 2, 2: 2, 3: 2}))]

    def test_value_repeat(self) -> None:
        # {1:3} is three 1s
        assert run("output {1:3}") == [("output 1", H({1: 3}))]

    def test_variable_type_reassignment(self) -> None:
        assert run("X: 5\nX: {1..3}\noutput X") == [("output 1", H({1: 1, 2: 1, 3: 1}))]


# ---- Sequences (advanced) ----------------------------------------------------------------


class TestSequencesAdvanced:
    def test_empty_sequence_literal(self) -> None:
        assert run("output {}") == [("output 1", H({}))]

    def test_descending_range_is_empty(self) -> None:
        # .. ranges are always ascending; {4..1} is empty
        assert run("output {4..1}") == [("output 1", H({}))]

    def test_descending_repeat_range_is_empty(self) -> None:
        assert run("output {4..1:2}") == [("output 1", H({}))]

    def test_die_in_sequence(self) -> None:
        # {die} yields the die's distinct outcomes once each, ascending
        assert run("output {d4}") == [("output 1", H({1: 1, 2: 1, 3: 1, 4: 1}))]

    def test_weighted_die_in_sequence(self) -> None:
        # weights collapse to distinct outcomes; {d{10:3,11:2,12:1}} = {10,11,12}
        assert run("output {d{10:3,11:2,12:1}}") == [
            ("output 1", H({10: 1, 11: 1, 12: 1}))
        ]

    def test_pool_sum_die_in_sequence(self) -> None:
        # multi-die expression: distinct outcomes of the summed distribution
        assert run("output {3d2}") == [("output 1", H({3: 1, 4: 1, 5: 1, 6: 1}))]

    def test_weighted_die_repeat_in_sequence(self) -> None:
        # {die:n} repeats the distinct-outcomes block n times in the seq
        # (NOT interleave each outcome n times). The H output is identical
        # under either interpretation because `output` collapses to a count
        # dict; positional ordering is exercised by `test_die_repeat_block_order`
        # below.
        assert run("output {2d4:2}") == [
            ("output 1", H({2: 2, 3: 2, 4: 2, 5: 2, 6: 2, 7: 2, 8: 2}))
        ]

    def test_die_repeat_block_order(self) -> None:
        # AnyDice (program 42971) returns 1 for `5 @ {d4:2, d8}`. That requires
        # the d4:2 expansion to be (1,2,3,4,1,2,3,4) -- block-repeat of the
        # outcome list -- not (1,1,2,2,3,3,4,4) (interleaved).
        assert run("output 5 @ {d4:2, d8}") == [("output 1", H({1: 1}))]

    def test_die_repeat_block_position_in_first_block(self) -> None:
        # Program 42974: position 2 lands in the first block of d4:2 -> 2.
        assert run("output 2 @ {d4:2, d8}") == [("output 1", H({2: 1}))]

    def test_die_repeat_block_position_at_block_end(self) -> None:
        # Program 42975: position 4 is the last element of d4:2's first block -> 4.
        assert run("output 4 @ {d4:2, d8}") == [("output 1", H({4: 1}))]

    def test_chained_d_is_left_associative(self) -> None:
        # AnyDice's `<count> d <faces>` operator chains left-associatively:
        # `2d2d2` parses as `(2d2)d2`, NOT `2d(2d2)`. The left-assoc form takes
        # the first dice expression as the count of the next roll. The
        # right-assoc form is just nested pools (= 4d2 here). Verified against
        # AnyDice (program 42af2).
        default = run("output 2d2d2")
        explicit_left = run("output (2d2)d2")
        explicit_right = run("output 2d(2d2)")
        # `2d2d2` matches `(2d2)d2`, NOT `2d(2d2)`.
        assert default == explicit_left
        assert default != explicit_right
        # `2d(2d2)` is just 4d2 (pool of two indep 2d2 sums).
        assert explicit_right == run("output 4d2")

    def test_chained_d_left_assoc_distribution(self) -> None:
        # Concrete values for the left-assoc 2d2d2 computed by hand and
        # verified against AnyDice (42af2). Each 2d2 outer outcome counts how
        # many d2s to roll for the inner stage; LCM-normalize across outer
        # outcomes.
        assert run("output 2d2d2") == [
            ("output 1", H({2: 4, 3: 12, 4: 17, 5: 16, 6: 10, 7: 4, 8: 1}))
        ]

    def test_chained_d_three_levels(self) -> None:
        # `4d3d2d1` parses as `((4d3)d2)d1`. Verified against AnyDice (42af2).
        assert run("output 4d3d2d1") == [
            (
                "output 1",
                H(
                    {
                        4: 256,
                        5: 1536,
                        6: 4736,
                        7: 10496,
                        8: 18864,
                        9: 28672,
                        10: 37736,
                        11: 43800,
                        12: 45313,
                        13: 41988,
                        14: 34938,
                        15: 26124,
                        16: 17503,
                        17: 10440,
                        18: 5492,
                        19: 2512,
                        20: 975,
                        21: 308,
                        22: 74,
                        23: 12,
                        24: 1,
                    }
                ),
            )
        ]

    def test_seq_repeat_matches_die_repeat_block_semantic(self) -> None:
        # `{{1,2,3,4}:2, d8}` and `{d4:2, d8}` must yield the same sequence
        # since d4's distinct outcomes are exactly (1,2,3,4). Both should
        # block-repeat to (1,2,3,4,1,2,3,4) for the d4/seq, then concatenate
        # d8's (1..8). Earlier our die-repeat path interleaved each outcome
        # while the seq-repeat path block-repeated; these tests pin both forms
        # equivalent.
        die_form = run("output 5 @ {d4:2, d8}")
        seq_form = run("output 5 @ {{1, 2, 3, 4}:2, d8}")
        assert die_form == seq_form == [("output 1", H({1: 1}))]

    # AnyDice flattens nested sequences in a sequence literal (i.e. concatenates
    # the inner seq's elements into the outer one) rather than sum-coercing the
    # inner to a single int. Bug surfaced via 663d (a `set element I in SEQ to N`
    # function building a new seq incrementally with `NEW: {NEW, value}`).

    def test_nested_seq_flattens(self) -> None:
        assert run("output # {{1, 2}, 3}") == [("output 1", H({3: 1}))]

    def test_nested_seq_flattens_at_position(self) -> None:
        # Position 2 of flattened (1, 2, 3) is 2 (source order, not sum).
        assert run("output 2 @ {{1, 2}, 3}") == [("output 1", H({2: 1}))]

    def test_two_nested_seqs_flatten(self) -> None:
        assert run("output # {{1, 2}, {3, 4}}") == [("output 1", H({4: 1}))]

    def test_seq_var_in_seq_literal_flattens(self) -> None:
        assert run("S: {1, 2}\noutput # {S, 3}") == [("output 1", H({3: 1}))]


# ---- Addition (+) ------------------------------------------------------------------------


class TestAdd:
    def test_num_add_num(self) -> None:
        assert run("output 2 + 3") == [("output 1", H({5: 1}))]

    def test_num_add_seq(self) -> None:
        # seq coerces to sum for arithmetic: {1,2,3}=6; 1+6=7
        assert run("output 1 + {1,2,3}") == [("output 1", H({7: 1}))]

    def test_num_add_die(self) -> None:
        assert run("output 1 + d6") == [
            ("output 1", H({2: 1, 3: 1, 4: 1, 5: 1, 6: 1, 7: 1}))
        ]

    def test_seq_add_num(self) -> None:
        assert run("output {1,2,3} + 1") == [("output 1", H({7: 1}))]

    def test_seq_add_seq(self) -> None:
        # {1,2}=3, {3,4}=7; 3+7=10
        assert run("output {1,2} + {3,4}") == [("output 1", H({10: 1}))]

    def test_seq_add_die(self) -> None:
        assert run("output {1,2,3} + d4") == [
            ("output 1", H({7: 1, 8: 1, 9: 1, 10: 1}))
        ]

    def test_die_add_num(self) -> None:
        assert run("output d6 + 1") == [
            ("output 1", H({2: 1, 3: 1, 4: 1, 5: 1, 6: 1, 7: 1}))
        ]

    def test_die_add_seq(self) -> None:
        assert run("output d4 + {1,2,3}") == [
            ("output 1", H({7: 1, 8: 1, 9: 1, 10: 1}))
        ]

    def test_die_add_die(self) -> None:
        assert run("output d6 + d6") == [("output 1", H(6) + H(6))]

    def test_empty_seq_add_num(self) -> None:
        assert run("output {} + 5") == [("output 1", H({5: 1}))]

    def test_num_add_empty_seq(self) -> None:
        assert run("output 5 + {}") == [("output 1", H({5: 1}))]

    def test_empty_seq_add_seq(self) -> None:
        assert run("output {} + {1..5}") == [("output 1", H({15: 1}))]

    def test_seq_add_empty_seq(self) -> None:
        assert run("output {1..5} + {}") == [("output 1", H({15: 1}))]

    def test_empty_seq_add_die(self) -> None:
        assert run("output {} + 2d6") == [("output 1", 2 @ H(6))]

    def test_die_add_empty_seq(self) -> None:
        assert run("output 2d6 + {}") == [("output 1", 2 @ H(6))]

    def test_empty_die_add_num(self) -> None:
        # +/- treat empty die as scalar 0 on either side (NOT propagating emptiness)
        assert run("output d{} + 5") == [("output 1", H({5: 1}))]

    def test_num_add_empty_die(self) -> None:
        assert run("output 5 + d{}") == [("output 1", H({5: 1}))]

    def test_empty_die_add_seq(self) -> None:
        assert run("output d{} + {1..5}") == [("output 1", H({15: 1}))]

    def test_seq_add_empty_die(self) -> None:
        assert run("output {1..5} + d{}") == [("output 1", H({15: 1}))]

    def test_empty_die_add_die(self) -> None:
        assert run("output d{} + 2d6") == [("output 1", 2 @ H(6))]

    def test_die_add_empty_die(self) -> None:
        assert run("output 2d6 + d{}") == [("output 1", 2 @ H(6))]


# ---- Subtraction (-) ---------------------------------------------------------------------


class TestSub:
    def test_num_sub_num(self) -> None:
        assert run("output 5 - 2") == [("output 1", H({3: 1}))]

    def test_num_sub_seq(self) -> None:
        # {1,2,3}=6; 10-6=4
        assert run("output 10 - {1,2,3}") == [("output 1", H({4: 1}))]

    def test_num_sub_die(self) -> None:
        assert run("output 10 - d6") == [
            ("output 1", H({4: 1, 5: 1, 6: 1, 7: 1, 8: 1, 9: 1}))
        ]

    def test_seq_sub_num(self) -> None:
        # {4,5}=9; 9-1=8
        assert run("output {4,5} - 1") == [("output 1", H({8: 1}))]

    def test_seq_sub_seq(self) -> None:
        # {3,4}=7, {1,2}=3; 7-3=4
        assert run("output {3,4} - {1,2}") == [("output 1", H({4: 1}))]

    def test_seq_sub_die(self) -> None:
        # {4,5}=9; 9-d{1,2}: 9-2=7, 9-1=8
        assert run("output {4,5} - d{1,2}") == [("output 1", H({7: 1, 8: 1}))]

    def test_die_sub_num(self) -> None:
        assert run("output d6 - 1") == [
            ("output 1", H({0: 1, 1: 1, 2: 1, 3: 1, 4: 1, 5: 1}))
        ]

    def test_die_sub_seq(self) -> None:
        # {1,2}=3; d4-3: 1-3=-2, 2-3=-1, 3-3=0, 4-3=1
        assert run("output d4 - {1,2}") == [("output 1", H({-2: 1, -1: 1, 0: 1, 1: 1}))]

    def test_die_sub_die(self) -> None:
        assert run("output d6 - d6") == [("output 1", H(6) - H(6))]

    def test_empty_seq_sub_num(self) -> None:
        assert run("output {} - 5") == [("output 1", H({-5: 1}))]

    def test_num_sub_empty_seq(self) -> None:
        assert run("output 5 - {}") == [("output 1", H({5: 1}))]

    def test_empty_seq_sub_seq(self) -> None:
        assert run("output {} - {1..5}") == [("output 1", H({-15: 1}))]

    def test_seq_sub_empty_seq(self) -> None:
        assert run("output {1..5} - {}") == [("output 1", H({15: 1}))]

    def test_empty_seq_sub_die(self) -> None:
        assert run("output {} - 2d6") == [("output 1", 2 @ H(-6))]

    def test_die_sub_empty_seq(self) -> None:
        assert run("output 2d6 - {}") == [("output 1", 2 @ H(6))]

    def test_num_sub_empty_die(self) -> None:
        assert run("output 5 - d{}") == [("output 1", H({5: 1}))]

    def test_empty_die_sub_num(self) -> None:
        # +/- treat empty die as scalar 0 on either side
        assert run("output d{} - 5") == [("output 1", H({-5: 1}))]

    def test_seq_sub_empty_die(self) -> None:
        assert run("output {1..5} - d{}") == [("output 1", H({15: 1}))]

    def test_empty_die_sub_seq(self) -> None:
        # d{} acts as scalar 0; {1..5} sums to 15; 0 - 15 = -15.
        assert run("output d{} - {1..5}") == [("output 1", H({-15: 1}))]

    def test_empty_die_sub_die(self) -> None:
        assert run("output d{} - 2d6") == [("output 1", 2 @ H(-6))]

    def test_die_sub_empty_die(self) -> None:
        assert run("output 2d6 - d{}") == [("output 1", 2 @ H(6))]


# ---- Multiplication (*) ------------------------------------------------------------------


class TestMul:
    def test_num_mul_num(self) -> None:
        assert run("output 2 * 3") == [("output 1", H({6: 1}))]

    def test_num_mul_seq(self) -> None:
        # {1,2,3}=6; 2*6=12
        assert run("output 2 * {1,2,3}") == [("output 1", H({12: 1}))]

    def test_num_mul_die(self) -> None:
        assert run("output 2 * d6") == [
            ("output 1", H({2: 1, 4: 1, 6: 1, 8: 1, 10: 1, 12: 1}))
        ]

    def test_seq_mul_num(self) -> None:
        assert run("output {1,2,3} * 2") == [("output 1", H({12: 1}))]

    def test_seq_mul_seq(self) -> None:
        # {1,2}=3, {3,4}=7; 3*7=21
        assert run("output {1,2} * {3,4}") == [("output 1", H({21: 1}))]

    def test_seq_mul_die(self) -> None:
        # {1,2}=3; 3*d{1,2,3}: 3, 6, 9
        assert run("output {1,2} * d{1,2,3}") == [("output 1", H({3: 1, 6: 1, 9: 1}))]

    def test_die_mul_num(self) -> None:
        assert run("output d{1,2,3} * 2") == [("output 1", H({2: 1, 4: 1, 6: 1}))]

    def test_die_mul_seq(self) -> None:
        # {1,2}=3; d{2,3}*3: 6, 9
        assert run("output d{2,3} * {1,2}") == [("output 1", H({6: 1, 9: 1}))]

    def test_die_mul_die(self) -> None:
        # d{1,2}*d{1,2}: 1*1=1, 1*2=2, 2*1=2, 2*2=4
        assert run("output d{1,2} * d{1,2}") == [("output 1", H({1: 1, 2: 2, 4: 1}))]

    def test_empty_seq_mul_num(self) -> None:
        # sum 0 * 5 = 0
        assert run("output {} * 5") == [("output 1", H({0: 1}))]

    def test_num_mul_empty_seq(self) -> None:
        assert run("output 5 * {}") == [("output 1", H({0: 1}))]

    def test_empty_seq_mul_seq(self) -> None:
        # 0 * 15 = 0
        assert run("output {} * {1..5}") == [("output 1", H({0: 1}))]

    def test_seq_mul_empty_seq(self) -> None:
        assert run("output {1..5} * {}") == [("output 1", H({0: 1}))]

    def test_empty_seq_mul_die(self) -> None:
        # 0 * each-2d6-outcome = 0; total weight from 2d6 (36).
        assert run("output {} * 2d6") == [("output 1", H({0: 36}))]

    def test_die_mul_empty_seq(self) -> None:
        assert run("output 2d6 * {}") == [("output 1", H({0: 36}))]

    def test_empty_die_mul_num(self) -> None:
        # *, /, ^ propagate empty-die emptiness (UNLIKE +/-)
        assert run("output d{} * 5") == [("output 1", H({}))]

    def test_num_mul_empty_die(self) -> None:
        assert run("output 5 * d{}") == [("output 1", H({}))]

    def test_empty_die_mul_seq(self) -> None:
        assert run("output d{} * {1..5}") == [("output 1", H({}))]

    def test_seq_mul_empty_die(self) -> None:
        assert run("output {1..5} * d{}") == [("output 1", H({}))]

    def test_empty_die_mul_die(self) -> None:
        assert run("output d{} * 2d6") == [("output 1", H({}))]

    def test_die_mul_empty_die(self) -> None:
        assert run("output 2d6 * d{}") == [("output 1", H({}))]


# ---- Division (/) ------------------------------------------------------------------------


class TestDiv:
    def test_num_div_num(self) -> None:
        # AnyDice division truncates toward zero
        assert run("output 7 / -2") == [("output 1", H({-3: 1}))]

    def test_num_div_seq(self) -> None:
        # {2,3}=5; 10/5=2
        assert run("output -10 / {2,3}") == [("output 1", H({-2: 1}))]

    def test_num_div_die(self) -> None:
        # 6/d{1,2,3}: 6, 3, 2
        assert run("output 6 / d{1,2,3}") == [("output 1", H({2: 1, 3: 1, 6: 1}))]

    def test_seq_div_num(self) -> None:
        # {4,-8}=-4; -4/2=-2
        assert run("output {4,-8} / 2") == [("output 1", H({-2: 1}))]

    def test_seq_div_seq(self) -> None:
        # {6,4}=10, {1,2}=3; 10/3=3
        assert run("output {6,4} / {-1,-2}") == [("output 1", H({-3: 1}))]

    def test_seq_div_die(self) -> None:
        # {6,4}=10; 10/d{1,2}: 10, 5
        assert run("output {6,4} / d{1,-2}") == [("output 1", H({-5: 1, 10: 1}))]

    def test_die_div_num(self) -> None:
        # d6/2: 1->0, 2->1, 3->1, 4->2, 5->2, 6->3
        assert run("output d6 / -2") == [("output 1", H({-3: 1, -2: 2, -1: 2, 0: 1}))]

    def test_die_div_seq(self) -> None:
        # {1,2}=3; d{3,6}/3: 1, 2
        assert run("output d{3,6} / {1,2}") == [("output 1", H({1: 1, 2: 1}))]

    def test_die_div_die(self) -> None:
        # d{2,4}/d{1,2}: 2/1=2, 2/2=1, 4/1=4, 4/2=2
        assert run("output d{2,4} / d{1,2}") == [("output 1", H({1: 1, 2: 2, 4: 1}))]

    # AnyDice substitutes 0 for division by zero at the smallest expression that
    # triggers it; outer arithmetic propagates normally.
    def test_num_div_zero(self) -> None:
        assert run("output 1 / 0") == [("output 1", H({0: 1}))]

    def test_zero_div_zero(self) -> None:
        assert run("output 0 / 0") == [("output 1", H({0: 1}))]

    def test_div_zero_propagates_through_outer_arith(self) -> None:
        assert run("output (1 / 0) + 5") == [("output 1", H({5: 1}))]

    def test_num_div_die_with_zero_outcome(self) -> None:
        # 1/0=0, 1/1=1
        assert run("output 1 / d{0, 1}") == [("output 1", H({0: 1, 1: 1}))]

    def test_num_div_die_zero_and_truncate(self) -> None:
        # 1/0=0, 1/1=1, 1/2=0 (truncated)
        assert run("output 1 / d{0, 1, 2}") == [("output 1", H({0: 2, 1: 1}))]

    def test_num_div_die_with_repeated_zero(self) -> None:
        # 1/0 twice, 1/1 once
        assert run("output 1 / d{0, 0, 1}") == [("output 1", H({0: 2, 1: 1}))]

    def test_empty_seq_div_num(self) -> None:
        # sum 0 / 5 = 0
        assert run("output {} / 5") == [("output 1", H({0: 1}))]

    def test_num_div_empty_seq(self) -> None:
        # Empty seq sum-coerces to 0; AnyDice substitutes 0 for division by zero.
        assert run("output 5 / {}") == [("output 1", H({0: 1}))]

    def test_empty_seq_div_seq(self) -> None:
        # 0 / 15 = 0
        assert run("output {} / {1..5}") == [("output 1", H({0: 1}))]

    def test_seq_div_empty_seq(self) -> None:
        # Empty seq sum-coerces to 0; sum {1..5}=15; 15/0=0.
        assert run("output {1..5} / {}") == [("output 1", H({0: 1}))]

    def test_empty_seq_div_die(self) -> None:
        # 0 / each-2d6-outcome = 0; total weight from 2d6 (36).
        assert run("output {} / 2d6") == [("output 1", H({0: 36}))]

    def test_die_div_empty_seq(self) -> None:
        # Empty seq sum-coerces to 0; each 2d6 outcome divided by 0 yields 0;
        # total weight from 2d6 (36).
        assert run("output 2d6 / {}") == [("output 1", H({0: 36}))]

    def test_empty_die_div_num(self) -> None:
        # *, /, ^ propagate empty-die emptiness
        assert run("output d{} / 5") == [("output 1", H({}))]

    def test_num_div_empty_die(self) -> None:
        assert run("output 5 / d{}") == [("output 1", H({}))]

    def test_empty_die_div_seq(self) -> None:
        assert run("output d{} / {1..5}") == [("output 1", H({}))]

    def test_seq_div_empty_die(self) -> None:
        assert run("output {1..5} / d{}") == [("output 1", H({}))]

    def test_empty_die_div_die(self) -> None:
        assert run("output d{} / 2d6") == [("output 1", H({}))]

    def test_die_div_empty_die(self) -> None:
        assert run("output 2d6 / d{}") == [("output 1", H({}))]


# ---- Exponentiation (^) ------------------------------------------------------------------


class TestPow:
    def test_num_pow_num(self) -> None:
        assert run("output 2 ^ 3") == [("output 1", H({8: 1}))]

    def test_num_pow_seq(self) -> None:
        # {1,2}=3; 2^3=8
        assert run("output 2 ^ {1,2}") == [("output 1", H({8: 1}))]

    def test_num_pow_die(self) -> None:
        assert run("output 2 ^ d{1,2,3}") == [("output 1", H({2: 1, 4: 1, 8: 1}))]

    def test_seq_pow_num(self) -> None:
        # {1,2}=3; 3^2=9
        assert run("output {1,2} ^ 2") == [("output 1", H({9: 1}))]

    def test_seq_pow_seq(self) -> None:
        # {1,2}=3, {1,2}=3; 3^3=27
        assert run("output {1,2} ^ {1,2}") == [("output 1", H({27: 1}))]

    def test_seq_pow_die(self) -> None:
        # {1,2}=3; 3^d{1,2}: 3, 9
        assert run("output {1,2} ^ d{1,2}") == [("output 1", H({3: 1, 9: 1}))]

    def test_die_pow_num(self) -> None:
        assert run("output d{1,2,3} ^ 2") == [("output 1", H({1: 1, 4: 1, 9: 1}))]

    def test_die_pow_seq(self) -> None:
        # {1,2}=3; d{1,2,3}^3: 1, 8, 27
        assert run("output d{1,2,3} ^ {1,2}") == [("output 1", H({1: 1, 8: 1, 27: 1}))]

    def test_die_pow_die(self) -> None:
        # d{1,2}^d{1,2}: 1^1=1, 1^2=1, 2^1=2, 2^2=4
        assert run("output d{1,2} ^ d{1,2}") == [("output 1", H({1: 2, 2: 1, 4: 1}))]

    def test_empty_seq_pow_num(self) -> None:
        # sum 0 ^ 5 = 0
        assert run("output {} ^ 5") == [("output 1", H({0: 1}))]

    def test_num_pow_empty_seq(self) -> None:
        # 5 ^ sum 0 = 1
        assert run("output 5 ^ {}") == [("output 1", H({1: 1}))]

    def test_empty_seq_pow_seq(self) -> None:
        # 0 ^ 15 = 0
        assert run("output {} ^ {1..5}") == [("output 1", H({0: 1}))]

    def test_seq_pow_empty_seq(self) -> None:
        # 15 ^ 0 = 1
        assert run("output {1..5} ^ {}") == [("output 1", H({1: 1}))]

    def test_empty_seq_pow_die(self) -> None:
        # 0 ^ each-positive-2d6-outcome = 0; total weight 36
        assert run("output {} ^ 2d6") == [("output 1", H({0: 36}))]

    def test_die_pow_empty_seq(self) -> None:
        # each ^ 0 = 1; total weight 36
        assert run("output 2d6 ^ {}") == [("output 1", H({1: 36}))]

    def test_empty_die_pow_num(self) -> None:
        # *, /, ^ propagate empty-die emptiness
        assert run("output d{} ^ 5") == [("output 1", H({}))]

    def test_num_pow_empty_die(self) -> None:
        assert run("output 5 ^ d{}") == [("output 1", H({}))]

    def test_empty_die_pow_seq(self) -> None:
        assert run("output d{} ^ {1..5}") == [("output 1", H({}))]

    def test_seq_pow_empty_die(self) -> None:
        assert run("output {1..5} ^ d{}") == [("output 1", H({}))]

    def test_empty_die_pow_die(self) -> None:
        assert run("output d{} ^ 2d6") == [("output 1", H({}))]

    def test_die_pow_empty_die(self) -> None:
        assert run("output 2d6 ^ d{}") == [("output 1", H({}))]


# ---- Position selection (@) --------------------------------------------------------------


class TestAt:
    def test_num_at_num(self) -> None:
        # N @ num: 1-based digit from most significant (highest first by default)
        assert run("output 2 @ 4567") == [("output 1", H({5: 1}))]

    def test_num_at_num_out_of_range(self) -> None:
        assert run("output 3 @ 42") == [("output 1", H({0: 1}))]

    def test_num_at_num_negative(self) -> None:
        # sign is retained for all digit positions
        assert run("output 1 @ -456") == [("output 1", H({-4: 1}))]

    def test_num_at_num_lowest_first(self) -> None:
        # lowest first: position 1 = least significant digit
        assert run('set "position order" to "lowest first"\noutput 2 @ 4567') == [
            ("output 1", H({6: 1}))
        ]

    def test_num_at_seq(self) -> None:
        # Position order does not affect seq indexing. Position 2 is still the
        # second written element even under "lowest first".
        res = [("output 1", H({6: 1}))]
        assert run("output 2 @ {7,6,5,4}") == res
        assert (
            run('set "position order" to "lowest first"\noutput 2 @ {7,6,5,4}') == res
        )

    def test_num_at_seq_out_of_range(self) -> None:
        assert run("output 5 @ {3,1,4,2}") == [("output 1", H({0: 1}))]

    def test_num_at_empty_seq(self) -> None:
        assert run("output 2 @ {}") == [("output 1", H({0: 1}))]

    def test_num_at_pool(self) -> None:
        # 1 @ 3d6: pool sorted highest-first by default; position 1 = highest die
        assert run("output 1 @ 3d6") == [
            (
                "output 1",
                H({1: 1, 2: 7, 3: 19, 4: 37, 5: 61, 6: 91}),
            )
        ]

    def test_num_at_pool_lowest_first(self) -> None:
        # under "lowest first": position 1 = lowest die (mirror of highest-first above)
        assert run('set "position order" to "lowest first"\noutput 1 @ 3d6') == [
            (
                "output 1",
                H({1: 91, 2: 61, 3: 37, 4: 19, 5: 7, 6: 1}),
            )
        ]

    def test_seq_at_num(self) -> None:
        # seq-on-left of @: each element is a separate position; results summed.
        # Position 1 of 4567 = 4, position 3 of 4567 = 6; sum = 10.
        assert run("output {1,3} @ 4567") == [("output 1", H({10: 1}))]

    def test_seq_at_seq(self) -> None:
        # seq-on-left of @: each element is a separate position; results summed.
        # Verified against AnyDice (program 42ad5) with disambiguating values:
        # multi-position {1, 4} @ seq → seq[0] + seq[3] = 10 + 40 = 50.
        assert run("output {1, 4} @ {10, 20, 30, 40}") == [("output 1", H({50: 1}))]

    def test_seq_at_pool(self) -> None:
        # seq-on-left of @ with a pool: same multi-position semantics.
        # {1, 3} @ 3d6 = top-1-of-3d6 + bottom-1-of-3d6 sum distribution.
        # Verified against AnyDice (program 42ad5).
        assert run("output {1, 3} @ 3d6") == [
            (
                "output 1",
                H(
                    {
                        2: 1,
                        3: 6,
                        4: 13,
                        5: 24,
                        6: 37,
                        7: 54,
                        8: 37,
                        9: 24,
                        10: 13,
                        11: 6,
                        12: 1,
                    }
                ),
            )
        ]

    def test_die_at_seq(self) -> None:
        with pytest.raises(
            TypeError, match=r"@ left operand must be a number or sequence, got die"
        ):
            run("output d{2,4} @ {10,20,30,40}")

    def test_empty_seq_at_num(self) -> None:
        # left empty seq sums to 0; position 0 is out-of-range -> 0
        assert run("output {} @ 123") == [("output 1", H({0: 1}))]

    def test_empty_seq_at_seq(self) -> None:
        assert run("output {} @ {1,2,3}") == [("output 1", H({0: 1}))]

    def test_num_at_empty_die(self) -> None:
        # @ propagates empty-die emptiness on right operand
        assert run("output 1 @ d{}") == [("output 1", H({}))]

    # AnyDice treats a non-empty H as a 1-element pool for `@`. `1@H` returns the
    # die's distribution; `N@H` for N != 1 returns 0 (out-of-range on a 1-pool).
    # Verified against AnyDice via 405c6 (ex chain) and the spot-check program
    # `D: 1@d6\noutput D named "[D]"` which AnyDice labels "d6" in its output.

    def test_num_at_die_position_one(self) -> None:
        # 1 @ <die> returns the die's distribution unchanged.
        assert run("output 1 @ d6") == [
            ("output 1", H({1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1}))
        ]

    def test_num_at_die_position_two(self) -> None:
        # 2 @ <die> on a 1-position pool is out of range -> 0.
        assert run("output 2 @ d6") == [("output 1", H({0: 1}))]

    def test_num_at_die_position_zero(self) -> None:
        # 0 @ <die>: pos < 1 -> 0.
        assert run("output 0 @ d6") == [("output 1", H({0: 1}))]


# ---- Equality (=) ------------------------------------------------------------------------


class TestEq:
    def test_num_eq_num(self) -> None:
        assert run("output 2 = 2") == [("output 1", H({1: 1}))]

    def test_num_eq_seq(self) -> None:
        # right-side seq: counts elements satisfying 6 = elem; none -> 0
        assert run("output 6 = {1,2,3}") == [("output 1", H({0: 1}))]

    def test_num_eq_die(self) -> None:
        assert run("output 3 = d6") == [("output 1", H({0: 5, 1: 1}))]

    def test_seq_eq_num(self) -> None:
        # left seq: counts elements satisfying the condition
        assert run("output {1,2,3} = 2") == [("output 1", H({1: 1}))]

    def test_seq_eq_num_multiple(self) -> None:
        assert run("output {2,2,4} = 2") == [("output 1", H({2: 1}))]

    def test_seq_eq_seq(self) -> None:
        # seq-vs-seq is lexicographic tuple comparison (after position-order sorting),
        # NOT sum-coercion. {1,2,3}=(3,2,1), {1,2}=(2,1); different lengths -> not equal
        assert run("output {1,2,3} = {1,2}") == [("output 1", H({0: 1}))]

    def test_seq_eq_seq_lex_distinguishes(self) -> None:
        # {1,3} sorted=(3,1), {2,2}=(2,2); tuples differ even though sums match (4=4).
        # Sum-coercion would yield true; lex yields false.
        assert run("output {1,3} = {2,2}") == [("output 1", H({0: 1}))]

    def test_seq_eq_die(self) -> None:
        # seq-on-left with die-on-right: seq coerces to sum (6); 6 = d{2,3} always false
        assert run("output {1,2,3} = d{2,3}") == [("output 1", H({0: 1}))]

    def test_die_eq_num(self) -> None:
        assert run("output d6 = 3") == [("output 1", H({0: 5, 1: 1}))]

    def test_die_eq_seq(self) -> None:
        # right seq coerces to sum; d6=6: only outcome 6 matches
        assert run("output d6 = {1,2,3}") == [("output 1", H({0: 5, 1: 1}))]

    def test_die_eq_die(self) -> None:
        assert run("output d{1,2} = d{1,2}") == [("output 1", H({0: 2, 1: 2}))]

    def test_empty_seq_eq_num(self) -> None:
        # left empty seq counts elements equal to num; 0 elements
        assert run("output {} = 5") == [("output 1", H({0: 1}))]

    def test_num_eq_empty_seq(self) -> None:
        assert run("output 5 = {}") == [("output 1", H({0: 1}))]

    def test_empty_seq_eq_seq(self) -> None:
        # lex tuple compare: () = (5,4,3,2,1) -> false
        assert run("output {} = {1..5}") == [("output 1", H({0: 1}))]

    def test_seq_eq_empty_seq(self) -> None:
        assert run("output {1..5} = {}") == [("output 1", H({0: 1}))]

    def test_empty_seq_eq_die(self) -> None:
        # die-vs-seq sum-coerces seq to 0; 0 = each-2d6-outcome always false
        assert run("output {} = 2d6") == [("output 1", H({0: 36}))]

    def test_die_eq_empty_seq(self) -> None:
        assert run("output 2d6 = {}") == [("output 1", H({0: 36}))]

    def test_empty_die_eq_num(self) -> None:
        # comparisons propagate empty-die emptiness on either side
        assert run("output d{} = 5") == [("output 1", H({}))]

    def test_num_eq_empty_die(self) -> None:
        assert run("output 5 = d{}") == [("output 1", H({}))]

    def test_empty_die_eq_seq(self) -> None:
        assert run("output d{} = {1..5}") == [("output 1", H({}))]

    def test_seq_eq_empty_die(self) -> None:
        assert run("output {1..5} = d{}") == [("output 1", H({}))]

    def test_empty_die_eq_die(self) -> None:
        assert run("output d{} = 2d6") == [("output 1", H({}))]

    def test_die_eq_empty_die(self) -> None:
        assert run("output 2d6 = d{}") == [("output 1", H({}))]


# ---- Inequality (!=) ---------------------------------------------------------------------


class TestNeq:
    def test_num_neq_num(self) -> None:
        assert run("output 2 != 3") == [("output 1", H({1: 1}))]

    def test_num_neq_seq(self) -> None:
        # right-side seq: counts elements satisfying 5 != elem; all 3
        assert run("output 5 != {1,2,3}") == [("output 1", H({3: 1}))]

    def test_num_neq_die(self) -> None:
        assert run("output 2 != d6") == [("output 1", H({0: 1, 1: 5}))]

    def test_seq_neq_num(self) -> None:
        # counts elements !=2: {1,3} -> 2
        assert run("output {1,2,3} != 2") == [("output 1", H({2: 1}))]

    def test_seq_neq_seq(self) -> None:
        # lex tuple compare: (3,2,1) != (2,1) (different lengths) -> true
        assert run("output {1,2,3} != {1,2}") == [("output 1", H({1: 1}))]

    def test_seq_neq_seq_lex_distinguishes(self) -> None:
        # {1,3}=(3,1), {2,2}=(2,2); lex says not-equal even though sums match (4=4)
        assert run("output {1,3} != {2,2}") == [("output 1", H({1: 1}))]

    def test_seq_neq_die(self) -> None:
        # seq-on-left with die-on-right: seq coerces to sum (6); 6 != d{2,3} always true
        assert run("output {1,2,3} != d{2,3}") == [("output 1", H({1: 1}))]

    def test_die_neq_num(self) -> None:
        assert run("output d6 != 3") == [("output 1", H({0: 1, 1: 5}))]

    def test_die_neq_seq(self) -> None:
        # sum=6; d6!=6: outcomes 1-5 -> true
        assert run("output d6 != {1,2,3}") == [("output 1", H({0: 1, 1: 5}))]

    def test_die_neq_die(self) -> None:
        assert run("output d{1,2} != d{1,2}") == [("output 1", H({0: 2, 1: 2}))]

    def test_empty_seq_neq_num(self) -> None:
        # left empty seq counts elements != num; 0 elements
        assert run("output {} != 5") == [("output 1", H({0: 1}))]

    def test_num_neq_empty_seq(self) -> None:
        assert run("output 5 != {}") == [("output 1", H({0: 1}))]

    def test_empty_seq_neq_seq(self) -> None:
        # lex tuple compare: () != (5,4,3,2,1) -> true
        assert run("output {} != {1..5}") == [("output 1", H({1: 1}))]

    def test_seq_neq_empty_seq(self) -> None:
        assert run("output {1..5} != {}") == [("output 1", H({1: 1}))]

    def test_empty_seq_neq_die(self) -> None:
        # sum 0; 0 != each-2d6-outcome always true
        assert run("output {} != 2d6") == [("output 1", H({1: 36}))]

    def test_die_neq_empty_seq(self) -> None:
        assert run("output 2d6 != {}") == [("output 1", H({1: 36}))]

    def test_empty_die_neq_num(self) -> None:
        # comparisons propagate empty-die emptiness on either side
        assert run("output d{} != 5") == [("output 1", H({}))]

    def test_num_neq_empty_die(self) -> None:
        assert run("output 5 != d{}") == [("output 1", H({}))]

    def test_empty_die_neq_seq(self) -> None:
        assert run("output d{} != {1..5}") == [("output 1", H({}))]

    def test_seq_neq_empty_die(self) -> None:
        assert run("output {1..5} != d{}") == [("output 1", H({}))]

    def test_empty_die_neq_die(self) -> None:
        assert run("output d{} != 2d6") == [("output 1", H({}))]

    def test_die_neq_empty_die(self) -> None:
        assert run("output 2d6 != d{}") == [("output 1", H({}))]


# ---- Less than (<) -----------------------------------------------------------------------


class TestLt:
    def test_num_lt_num(self) -> None:
        assert run("output 2 < 3") == [("output 1", H({1: 1}))]

    def test_num_lt_seq(self) -> None:
        # 2<{1,2,3}=6 -> true
        assert run("output 2 < {1,2,3}") == [("output 1", H({1: 1}))]

    def test_num_lt_die(self) -> None:
        # 1<d6: outcome 1 fails, rest pass
        assert run("output 1 < d6") == [("output 1", H({0: 1, 1: 5}))]

    def test_seq_lt_num(self) -> None:
        # counts elements <3: {1,2} -> 2
        assert run("output {1,2,3} < 3") == [("output 1", H({2: 1}))]

    def test_seq_lt_seq(self) -> None:
        # lex tuple compare: (3,2,1) < (4,3) -> 3<4 -> true
        assert run("output {1,2,3} < {3,4}") == [("output 1", H({1: 1}))]

    def test_seq_lt_seq_lex_distinguishes(self) -> None:
        # {4,1}=(4,1), {3,3}=(3,3); lex: 4>3 -> false. Sum-coercion would say 5<6 -> true.
        assert run("output {4,1} < {3,3}") == [("output 1", H({0: 1}))]

    def test_seq_lt_die(self) -> None:
        # seq-on-left with die-on-right: seq coerces to sum (6); 6 < d{3,5} always false
        assert run("output {1,2,3} < d{3,5}") == [("output 1", H({0: 1}))]

    def test_die_lt_num(self) -> None:
        # d6<3: outcomes 1,2 qualify
        assert run("output d6 < 3") == [("output 1", H({0: 4, 1: 2}))]

    def test_die_lt_seq(self) -> None:
        # {1,2}=3; d6<3: outcomes 1,2 qualify
        assert run("output d6 < {1,2}") == [("output 1", H({0: 4, 1: 2}))]

    def test_die_lt_die(self) -> None:
        # d{1,2}<d{2,3}: 1<2=T,1<3=T,2<2=F,2<3=T
        assert run("output d{1,2} < d{2,3}") == [("output 1", H({0: 1, 1: 3}))]

    def test_empty_seq_lt_num(self) -> None:
        # left empty seq counts elements < num; 0 elements
        assert run("output {} < 5") == [("output 1", H({0: 1}))]

    def test_num_lt_empty_seq(self) -> None:
        assert run("output 5 < {}") == [("output 1", H({0: 1}))]

    def test_empty_seq_lt_seq(self) -> None:
        # lex tuple compare: () < (5,4,3,2,1) -> true (empty < non-empty)
        assert run("output {} < {1..5}") == [("output 1", H({1: 1}))]

    def test_seq_lt_empty_seq(self) -> None:
        assert run("output {1..5} < {}") == [("output 1", H({0: 1}))]

    def test_empty_seq_lt_die(self) -> None:
        # sum 0; 0 < each positive 2d6 outcome -> always true
        assert run("output {} < 2d6") == [("output 1", H({1: 36}))]

    def test_die_lt_empty_seq(self) -> None:
        # each positive 2d6 outcome < 0 -> always false
        assert run("output 2d6 < {}") == [("output 1", H({0: 36}))]

    def test_empty_die_lt_num(self) -> None:
        # comparisons propagate empty-die emptiness on either side
        assert run("output d{} < 5") == [("output 1", H({}))]

    def test_num_lt_empty_die(self) -> None:
        assert run("output 5 < d{}") == [("output 1", H({}))]

    def test_empty_die_lt_seq(self) -> None:
        assert run("output d{} < {1..5}") == [("output 1", H({}))]

    def test_seq_lt_empty_die(self) -> None:
        assert run("output {1..5} < d{}") == [("output 1", H({}))]

    def test_empty_die_lt_die(self) -> None:
        assert run("output d{} < 2d6") == [("output 1", H({}))]

    def test_die_lt_empty_die(self) -> None:
        assert run("output 2d6 < d{}") == [("output 1", H({}))]


# ---- Greater than (>) --------------------------------------------------------------------


class TestGt:
    def test_num_gt_num(self) -> None:
        assert run("output 3 > 2") == [("output 1", H({1: 1}))]

    def test_num_gt_seq(self) -> None:
        # right-side seq: counts elements satisfying 7 > elem; all 3
        assert run("output 7 > {1,2,3}") == [("output 1", H({3: 1}))]

    def test_num_gt_die(self) -> None:
        # 6>d6: only outcome 6 fails
        assert run("output 6 > d6") == [("output 1", H({0: 1, 1: 5}))]

    def test_seq_gt_num(self) -> None:
        # counts elements >1: {2,3} -> 2
        assert run("output {1,2,3} > 1") == [("output 1", H({2: 1}))]

    def test_seq_gt_seq(self) -> None:
        # lex tuple compare: (4,3) > (2,1) -> 4>2 -> true
        assert run("output {3,4} > {1,2}") == [("output 1", H({1: 1}))]

    def test_seq_gt_seq_lex_distinguishes(self) -> None:
        # {2,2,2}=(2,2,2), {2,2}=(2,2); prefix-equal, longer is greater under lex.
        # Sum-coercion would say 6>4 (also true) but the longer-vs-shorter case is the
        # one only lex explains.
        assert run("output {2,2,2} > {2,2}") == [("output 1", H({1: 1}))]

    def test_seq_gt_die(self) -> None:
        # seq-on-left with die-on-right: seq coerces to sum (6); 6 > d{1,2} always true
        assert run("output {1,2,3} > d{1,2}") == [("output 1", H({1: 1}))]

    def test_die_gt_num(self) -> None:
        # d6>3: outcomes 4,5,6 qualify
        assert run("output d6 > 3") == [("output 1", H({0: 3, 1: 3}))]

    def test_die_gt_seq(self) -> None:
        # {2,3}=5; d6>5: only 6 qualifies
        assert run("output d6 > {2,3}") == [("output 1", H({0: 5, 1: 1}))]

    def test_die_gt_die(self) -> None:
        # d{2,3}>d{1,2}: 2>1=T,2>2=F,3>1=T,3>2=T
        assert run("output d{2,3} > d{1,2}") == [("output 1", H({0: 1, 1: 3}))]

    def test_empty_seq_gt_num(self) -> None:
        # left empty seq counts elements > num; 0 elements
        assert run("output {} > 5") == [("output 1", H({0: 1}))]

    def test_num_gt_empty_seq(self) -> None:
        assert run("output 5 > {}") == [("output 1", H({0: 1}))]

    def test_empty_seq_gt_seq(self) -> None:
        # lex tuple compare: () > (5,4,3,2,1) -> false
        assert run("output {} > {1..5}") == [("output 1", H({0: 1}))]

    def test_seq_gt_empty_seq(self) -> None:
        assert run("output {1..5} > {}") == [("output 1", H({1: 1}))]

    def test_empty_seq_gt_die(self) -> None:
        # sum 0; 0 > each positive 2d6 outcome -> always false
        assert run("output {} > 2d6") == [("output 1", H({0: 36}))]

    def test_die_gt_empty_seq(self) -> None:
        # each positive 2d6 outcome > 0 -> always true
        assert run("output 2d6 > {}") == [("output 1", H({1: 36}))]

    def test_empty_die_gt_num(self) -> None:
        # comparisons propagate empty-die emptiness on either side
        assert run("output d{} > 5") == [("output 1", H({}))]

    def test_num_gt_empty_die(self) -> None:
        assert run("output 5 > d{}") == [("output 1", H({}))]

    def test_empty_die_gt_seq(self) -> None:
        assert run("output d{} > {1..5}") == [("output 1", H({}))]

    def test_seq_gt_empty_die(self) -> None:
        assert run("output {1..5} > d{}") == [("output 1", H({}))]

    def test_empty_die_gt_die(self) -> None:
        assert run("output d{} > 2d6") == [("output 1", H({}))]

    def test_die_gt_empty_die(self) -> None:
        assert run("output 2d6 > d{}") == [("output 1", H({}))]


# ---- Less than or equal (<=) -------------------------------------------------------------


class TestLeq:
    def test_num_leq_num(self) -> None:
        assert run("output 2 <= 2") == [("output 1", H({1: 1}))]

    def test_num_leq_seq(self) -> None:
        # right-side seq: counts elements satisfying 6 <= elem; none
        assert run("output 6 <= {1,2,3}") == [("output 1", H({0: 1}))]

    def test_num_leq_die(self) -> None:
        # 3<=d6: outcomes 3,4,5,6 qualify
        assert run("output 3 <= d6") == [("output 1", H({0: 2, 1: 4}))]

    def test_seq_leq_num(self) -> None:
        # counts elements <=2: {1,2} -> 2
        assert run("output {1,2,3} <= 2") == [("output 1", H({2: 1}))]

    def test_seq_leq_seq(self) -> None:
        # lex tuple compare: (3,2,1) <= (4,3) -> 3<4 -> true
        assert run("output {1,2,3} <= {3,4}") == [("output 1", H({1: 1}))]

    def test_seq_leq_seq_lex_distinguishes(self) -> None:
        # {4,1}=(4,1), {3,3}=(3,3); lex: 4>3 -> false. Sum would give 5<=6 -> true.
        assert run("output {4,1} <= {3,3}") == [("output 1", H({0: 1}))]

    def test_seq_leq_die(self) -> None:
        # seq-on-left with die-on-right: seq coerces to sum (6); 6 <= d{2,3} always false
        assert run("output {1,2,3} <= d{2,3}") == [("output 1", H({0: 1}))]

    def test_die_leq_num(self) -> None:
        # d6<=3: outcomes 1,2,3 qualify
        assert run("output d6 <= 3") == [("output 1", H({0: 3, 1: 3}))]

    def test_die_leq_seq(self) -> None:
        # NOTE: AnyDice itself returns the same output for `d6 <= {2,3}` and `d6 > {2,3}`,
        # which is internally inconsistent and not derivable from any coercion model.
        # We treat that as an AnyDice bug and follow the consistent rule: right-side seq
        # coerces to sum (5); d6 <= 5 -> outcomes 1-5 qualify.
        assert run("output d6 <= {2,3}") == [("output 1", H({0: 1, 1: 5}))]

    def test_die_leq_die(self) -> None:
        # d{1,2}<=d{2,3}: all four combinations satisfy
        assert run("output d{1,2} <= d{2,3}") == [("output 1", H({1: 4}))]

    def test_empty_seq_leq_num(self) -> None:
        # left empty seq counts elements <= num; 0 elements
        assert run("output {} <= 5") == [("output 1", H({0: 1}))]

    def test_num_leq_empty_seq(self) -> None:
        assert run("output 5 <= {}") == [("output 1", H({0: 1}))]

    def test_empty_seq_leq_seq(self) -> None:
        # lex tuple compare: () <= (5,4,3,2,1) -> true
        assert run("output {} <= {1..5}") == [("output 1", H({1: 1}))]

    def test_seq_leq_empty_seq(self) -> None:
        assert run("output {1..5} <= {}") == [("output 1", H({0: 1}))]

    def test_empty_seq_leq_die(self) -> None:
        # sum 0; 0 <= each positive 2d6 outcome -> always true
        assert run("output {} <= 2d6") == [("output 1", H({1: 36}))]

    def test_die_leq_empty_seq(self) -> None:
        # each positive 2d6 outcome <= 0 -> always false
        assert run("output 2d6 <= {}") == [("output 1", H({0: 36}))]

    def test_empty_die_leq_num(self) -> None:
        # comparisons propagate empty-die emptiness on either side
        assert run("output d{} <= 5") == [("output 1", H({}))]

    def test_num_leq_empty_die(self) -> None:
        assert run("output 5 <= d{}") == [("output 1", H({}))]

    def test_empty_die_leq_seq(self) -> None:
        assert run("output d{} <= {1..5}") == [("output 1", H({}))]

    def test_seq_leq_empty_die(self) -> None:
        assert run("output {1..5} <= d{}") == [("output 1", H({}))]

    def test_empty_die_leq_die(self) -> None:
        assert run("output d{} <= 2d6") == [("output 1", H({}))]

    def test_die_leq_empty_die(self) -> None:
        assert run("output 2d6 <= d{}") == [("output 1", H({}))]


# ---- Greater than or equal (>=) ----------------------------------------------------------


class TestGeq:
    def test_num_geq_num(self) -> None:
        assert run("output 2 >= 2") == [("output 1", H({1: 1}))]

    def test_num_geq_seq(self) -> None:
        # right-side seq: counts elements satisfying 6 >= elem; all 3
        assert run("output 6 >= {1,2,3}") == [("output 1", H({3: 1}))]

    def test_num_geq_die(self) -> None:
        # 3>=d6: outcomes 1,2,3 qualify
        assert run("output 3 >= d6") == [("output 1", H({0: 3, 1: 3}))]

    def test_seq_geq_num(self) -> None:
        # counts elements >=2: {2,3} -> 2
        assert run("output {1,2,3} >= 2") == [("output 1", H({2: 1}))]

    def test_seq_geq_seq(self) -> None:
        # lex tuple compare: (4,3) >= (2,1) -> 4>2 -> true
        assert run("output {3,4} >= {1,2}") == [("output 1", H({1: 1}))]

    def test_seq_geq_seq_lex_distinguishes(self) -> None:
        # {3,3}=(3,3), {4,1}=(4,1); lex: 3<4 -> false. Sum would give 6>=5 -> true.
        assert run("output {3,3} >= {4,1}") == [("output 1", H({0: 1}))]

    def test_seq_geq_die(self) -> None:
        # seq-on-left with die-on-right: seq coerces to sum (6); 6 >= d{1,3} always true
        assert run("output {1,2,3} >= d{1,3}") == [("output 1", H({1: 1}))]

    def test_die_geq_num(self) -> None:
        # d6>=3: outcomes 3,4,5,6 qualify
        assert run("output d6 >= 3") == [("output 1", H({0: 2, 1: 4}))]

    def test_die_geq_seq(self) -> None:
        # {1,2}=3; d6>=3: outcomes 3-6 qualify
        assert run("output d6 >= {1,2}") == [("output 1", H({0: 2, 1: 4}))]

    def test_die_geq_die(self) -> None:
        # d{1,2}>=d{1,2}: 1>=1=T,1>=2=F,2>=1=T,2>=2=T
        assert run("output d{1,2} >= d{1,2}") == [("output 1", H({0: 1, 1: 3}))]

    def test_empty_seq_geq_num(self) -> None:
        # left empty seq counts elements >= num; 0 elements
        assert run("output {} >= 5") == [("output 1", H({0: 1}))]

    def test_num_geq_empty_seq(self) -> None:
        assert run("output 5 >= {}") == [("output 1", H({0: 1}))]

    def test_empty_seq_geq_seq(self) -> None:
        # lex tuple compare: () >= (5,4,3,2,1) -> false
        assert run("output {} >= {1..5}") == [("output 1", H({0: 1}))]

    def test_seq_geq_empty_seq(self) -> None:
        assert run("output {1..5} >= {}") == [("output 1", H({1: 1}))]

    def test_empty_seq_geq_die(self) -> None:
        # sum 0; 0 >= each positive 2d6 outcome -> always false
        assert run("output {} >= 2d6") == [("output 1", H({0: 36}))]

    def test_die_geq_empty_seq(self) -> None:
        # each positive 2d6 outcome >= 0 -> always true
        assert run("output 2d6 >= {}") == [("output 1", H({1: 36}))]

    def test_empty_die_geq_num(self) -> None:
        # comparisons propagate empty-die emptiness on either side
        assert run("output d{} >= 5") == [("output 1", H({}))]

    def test_num_geq_empty_die(self) -> None:
        assert run("output 5 >= d{}") == [("output 1", H({}))]

    def test_empty_die_geq_seq(self) -> None:
        assert run("output d{} >= {1..5}") == [("output 1", H({}))]

    def test_seq_geq_empty_die(self) -> None:
        assert run("output {1..5} >= d{}") == [("output 1", H({}))]

    def test_empty_die_geq_die(self) -> None:
        assert run("output d{} >= 2d6") == [("output 1", H({}))]

    def test_die_geq_empty_die(self) -> None:
        assert run("output 2d6 >= d{}") == [("output 1", H({}))]


# ---- Logical and (&) ---------------------------------------------------------------------


class TestAnd:
    def test_num_and_num(self) -> None:
        assert run("output 1 & 1") == [("output 1", H({1: 1}))]

    def test_num_and_seq(self) -> None:
        # {1,2,3}=6, nonzero; 1 & 6 -> 1
        assert run("output 1 & {1,2,3}") == [("output 1", H({1: 1}))]

    def test_num_and_die(self) -> None:
        # 1 & d{0,1}: 1&0=0, 1&1=1
        assert run("output 1 & d{0,1}") == [("output 1", H({0: 1, 1: 1}))]

    def test_seq_and_num(self) -> None:
        # {1,2,3}=6, nonzero; 6 & 1 -> 1
        assert run("output {1,2,3} & 1") == [("output 1", H({1: 1}))]

    def test_seq_and_seq(self) -> None:
        # {1,2,3}=6, {0}=0; 6 & 0 -> 0
        assert run("output {1,2,3} & {0}") == [("output 1", H({0: 1}))]

    def test_seq_and_die(self) -> None:
        # {1,2,3}=6, nonzero; 6 & d{0,1}: 0, 1
        assert run("output {1,2,3} & d{0,1}") == [("output 1", H({0: 1, 1: 1}))]

    def test_die_and_num(self) -> None:
        # d{0,1} & 1: 0&1=0, 1&1=1
        assert run("output d{0,1} & 1") == [("output 1", H({0: 1, 1: 1}))]

    def test_die_and_seq(self) -> None:
        # {1,2,3}=6, nonzero; d{0,1} & 6: 0, 1
        assert run("output d{0,1} & {1,2,3}") == [("output 1", H({0: 1, 1: 1}))]

    def test_die_and_die(self) -> None:
        # d{0,1} & d{0,1}: 0&0=0, 0&1=0, 1&0=0, 1&1=1
        assert run("output d{0,1} & d{0,1}") == [("output 1", H({0: 3, 1: 1}))]

    def test_empty_seq_and_num(self) -> None:
        # sum 0; 0 & 5 = 0
        assert run("output {} & 5") == [("output 1", H({0: 1}))]

    def test_num_and_empty_seq(self) -> None:
        # 5 & sum 0 = 0
        assert run("output 5 & {}") == [("output 1", H({0: 1}))]

    def test_empty_seq_and_seq(self) -> None:
        # sum 0; 0 & 15 = 0
        assert run("output {} & {1..5}") == [("output 1", H({0: 1}))]

    def test_seq_and_empty_seq(self) -> None:
        assert run("output {1..5} & {}") == [("output 1", H({0: 1}))]

    def test_empty_seq_and_die(self) -> None:
        # 0 & each-2d6-outcome = 0; total weight 36
        assert run("output {} & 2d6") == [("output 1", H({0: 36}))]

    def test_die_and_empty_seq(self) -> None:
        assert run("output 2d6 & {}") == [("output 1", H({0: 36}))]

    def test_empty_die_and_num(self) -> None:
        # & propagates empty-die emptiness on either side
        assert run("output d{} & 5") == [("output 1", H({}))]

    def test_num_and_empty_die(self) -> None:
        assert run("output 5 & d{}") == [("output 1", H({}))]

    def test_empty_die_and_seq(self) -> None:
        assert run("output d{} & {1..5}") == [("output 1", H({}))]

    def test_seq_and_empty_die(self) -> None:
        assert run("output {1..5} & d{}") == [("output 1", H({}))]

    def test_empty_die_and_die(self) -> None:
        assert run("output d{} & 2d6") == [("output 1", H({}))]

    def test_die_and_empty_die(self) -> None:
        assert run("output 2d6 & d{}") == [("output 1", H({}))]


# ---- Logical or (|) ----------------------------------------------------------------------


class TestOr:
    def test_num_or_num(self) -> None:
        assert run("output 1 | 0") == [("output 1", H({1: 1}))]

    def test_num_or_seq(self) -> None:
        # {1,2,3}=6, nonzero; 0 | 6 -> 1
        assert run("output 0 | {1,2,3}") == [("output 1", H({1: 1}))]

    def test_num_or_die(self) -> None:
        # 0 | d{0,1}: 0|0=0, 0|1=1
        assert run("output 0 | d{0,1}") == [("output 1", H({0: 1, 1: 1}))]

    def test_seq_or_num(self) -> None:
        # {0}=0; 0 | 1 -> 1
        assert run("output {0} | 1") == [("output 1", H({1: 1}))]

    def test_seq_or_seq(self) -> None:
        # {0}=0, {0}=0; 0 | 0 -> 0
        assert run("output {0} | {0}") == [("output 1", H({0: 1}))]

    def test_seq_or_die(self) -> None:
        # {0}=0; 0 | d{0,1}: 0, 1
        assert run("output {0} | d{0,1}") == [("output 1", H({0: 1, 1: 1}))]

    def test_die_or_num(self) -> None:
        # d{0,1} | 0: 0|0=0, 1|0=1
        assert run("output d{0,1} | 0") == [("output 1", H({0: 1, 1: 1}))]

    def test_die_or_seq(self) -> None:
        # {0}=0; d{0,1} | 0: 0, 1
        assert run("output d{0,1} | {0}") == [("output 1", H({0: 1, 1: 1}))]

    def test_die_or_die(self) -> None:
        # d{0,1} | d{0,1}: 0|0=0, 0|1=1, 1|0=1, 1|1=1
        assert run("output d{0,1} | d{0,1}") == [("output 1", H({0: 1, 1: 3}))]

    def test_empty_seq_or_num(self) -> None:
        # sum 0 | 5 = 1
        assert run("output {} | 5") == [("output 1", H({1: 1}))]

    def test_num_or_empty_seq(self) -> None:
        assert run("output 5 | {}") == [("output 1", H({1: 1}))]

    def test_empty_seq_or_seq(self) -> None:
        # sum 0 | sum 15 = 1
        assert run("output {} | {1..5}") == [("output 1", H({1: 1}))]

    def test_seq_or_empty_seq(self) -> None:
        assert run("output {1..5} | {}") == [("output 1", H({1: 1}))]

    def test_empty_seq_or_die(self) -> None:
        # 0 | each-2d6-outcome (all truthy) -> 1; total weight 36
        assert run("output {} | 2d6") == [("output 1", H({1: 36}))]

    def test_die_or_empty_seq(self) -> None:
        assert run("output 2d6 | {}") == [("output 1", H({1: 36}))]

    def test_empty_die_or_num(self) -> None:
        # | typically treats empty die as scalar 0; 0 | 5 = 1
        assert run("output d{} | 5") == [("output 1", H({1: 1}))]

    def test_num_or_empty_die(self) -> None:
        # 5 | 0 = 1
        assert run("output 5 | d{}") == [("output 1", H({1: 1}))]

    def test_empty_die_or_seq(self) -> None:
        # 0 | sum 15 = 1
        assert run("output d{} | {1..5}") == [("output 1", H({1: 1}))]

    def test_seq_or_empty_die(self) -> None:
        assert run("output {1..5} | d{}") == [("output 1", H({1: 1}))]

    def test_empty_die_or_die(self) -> None:
        # 0 | each-2d6-outcome (all truthy) -> 1; total weight 36
        assert run("output d{} | 2d6") == [("output 1", H({1: 36}))]

    def test_die_or_empty_die(self) -> None:
        assert run("output 2d6 | d{}") == [("output 1", H({1: 36}))]

    # ---- Anomaly probes: cases where both | operands evaluate to zero/empty -----

    def test_empty_seq_or_empty_seq(self) -> None:
        # sum 0 | sum 0 = 0
        assert run("output {} | {}") == [("output 1", H({0: 1}))]

    def test_empty_seq_or_empty_die(self) -> None:
        # sum 0 | (right empty die acts as 0) = 0
        assert run("output {} | d{}") == [("output 1", H({0: 1}))]

    def test_empty_die_or_empty_seq(self) -> None:
        # AnyDice anomaly: d{} | {} returns H({}) even though d{} | 5 returns H({1:1}).
        # We match AnyDice's actual output for this specific corner case.
        assert run("output d{} | {}") == [("output 1", H({}))]

    def test_empty_die_or_empty_die(self) -> None:
        # Both sides empty die -> propagate.
        assert run("output d{} | d{}") == [("output 1", H({}))]


# ---- Negation (unary -) ------------------------------------------------------------------


class TestNeg:
    def test_neg_num(self) -> None:
        assert run("output -3") == [("output 1", H({-3: 1}))]

    def test_neg_seq(self) -> None:
        # unary - coerces seq to sum, then negates: -(1+2+3)=-6
        assert run("output -{1,2,3}") == [("output 1", H({-6: 1}))]

    def test_neg_die(self) -> None:
        assert run("output -d6") == [("output 1", -H(6))]

    def test_neg_empty_seq(self) -> None:
        # sum 0 -> -0 -> 0
        assert run("output -{}") == [("output 1", H({0: 1}))]

    def test_neg_empty_die(self) -> None:
        assert run("output -d{}") == [("output 1", H({}))]


# ---- Unary plus (unary +) ----------------------------------------------------------------


class TestPos:
    def test_pos_num(self) -> None:
        assert run("output +5") == [("output 1", H({5: 1}))]

    def test_pos_seq(self) -> None:
        # unary + is identity: seq is NOT coerced to its sum
        assert run("output +{1,2,3}") == [("output 1", H({1: 1, 2: 1, 3: 1}))]

    def test_pos_die(self) -> None:
        assert run("output +d6") == [("output 1", H(6))]

    def test_pos_empty_seq(self) -> None:
        # unary + is identity; empty seq is H({})
        assert run("output +{}") == [("output 1", H({}))]

    def test_pos_empty_die(self) -> None:
        assert run("output +d{}") == [("output 1", H({}))]


# ---- Length / digit count (#) ------------------------------------------------------------


class TestHash:
    def test_hash_num(self) -> None:
        assert run("output #5") == [("output 1", H({1: 1}))]

    def test_hash_num_two_digits(self) -> None:
        assert run("output #42") == [("output 1", H({2: 1}))]

    def test_hash_num_negative(self) -> None:
        # counts digits of absolute value
        assert run("output #-23") == [("output 1", H({2: 1}))]

    def test_hash_zero(self) -> None:
        assert run("output #0") == [("output 1", H({1: 1}))]

    def test_hash_seq(self) -> None:
        assert run("output #{1,2,3}") == [("output 1", H({3: 1}))]

    def test_hash_seq_with_repeats(self) -> None:
        # duplicate elements each count as one position
        assert run("output #{2,2,4}") == [("output 1", H({3: 1}))]

    def test_hash_empty_seq(self) -> None:
        assert run("output #{}") == [("output 1", H({0: 1}))]

    def test_hash_empty_die(self) -> None:
        # # of an empty die is 0 (not H({}) -- # does NOT propagate emptiness)
        assert run("output #d{}") == [("output 1", H({0: 1}))]

    def test_hash_empty_pool(self) -> None:
        # #(3d{}) is 0 too
        assert run("output #(3d{})") == [("output 1", H({0: 1}))]

    # Per AnyDice (program 42af3), `#` on a non-empty die or pool returns the
    # number of positions. A bare die (H) is a 1-position pool. A multi-die
    # pool (P) returns its length. Empty H/P still propagate 0 (above).

    def test_hash_die(self) -> None:
        assert run("output #d6") == [("output 1", H({1: 1}))]

    def test_hash_pool(self) -> None:
        assert run("output #(2d6)") == [("output 1", H({2: 1}))]

    def test_hash_pool_three(self) -> None:
        assert run("output #(3d6)") == [("output 1", H({3: 1}))]


# ---- Logical not (!) ---------------------------------------------------------------------


class TestNot:
    def test_not_num_zero(self) -> None:
        assert run("output !0") == [("output 1", H({1: 1}))]

    def test_not_num_nonzero(self) -> None:
        assert run("output !5") == [("output 1", H({0: 1}))]

    def test_not_seq_nonzero_sum(self) -> None:
        # seq coerces to sum before !: sum({1,2,3})=6, !6=0
        assert run("output !{1,2,3}") == [("output 1", H({0: 1}))]

    def test_not_seq_zero_sum(self) -> None:
        assert run("output !{0,0,0}") == [("output 1", H({1: 1}))]

    def test_not_die(self) -> None:
        # ! expands over die outcomes; all d6 outcomes are nonzero -> all map to 0
        assert run("output !d6") == [("output 1", H({0: 6}))]

    def test_not_empty_seq(self) -> None:
        # sum 0; !0 = 1
        assert run("output !{}") == [("output 1", H({1: 1}))]

    def test_not_empty_die(self) -> None:
        assert run("output !d{}") == [("output 1", H({}))]


# ---- Error handling ----------------------------------------------------------------------


class TestErrors:
    def test_double_d(self) -> None:
        with pytest.raises(
            UnexpectedInput, match=r"Unexpected token .* at line \d+, column \d+\b"
        ):
            run("output 2dd6")

    def test_die_as_range_bound(self) -> None:
        with pytest.raises(TypeError, match=r"range bounds must be a number"):
            run("output {2..d4}")

    def test_undefined_variable(self) -> None:
        with pytest.raises(NameError, match=r"undefined variable"):
            run("output X")


# ---- Functions ---------------------------------------------------------------------------


class TestFunctionBasic:
    _F_DOUBLE_Xn = "function: double N:n { result: N * 2 }"
    _F_ADD_An_Bn = "function: add A:n B:n { result: A + B }"

    def test_no_arg_function(self) -> None:
        assert run("function: one { result: 1 }\noutput [one]") == [
            ("output 1", H({1: 1}))
        ]

    def test_num_param_with_num(self) -> None:
        assert run(f"{self._F_DOUBLE_Xn}\noutput [double 3]") == [
            ("output 1", H({6: 1}))
        ]

    def test_num_param_with_die_expands(self) -> None:
        # [double d6]: body runs once per outcome of d6, results are recombined
        assert run(f"{self._F_DOUBLE_Xn}\noutput [double d6]") == [
            ("output 1", H({2: 1, 4: 1, 6: 1, 8: 1, 10: 1, 12: 1}))
        ]

    def test_two_num_params_both_num(self) -> None:
        assert run(f"{self._F_ADD_An_Bn}\noutput [add 2 3]") == [
            ("output 1", H({5: 1}))
        ]

    def test_two_num_params_first_is_die(self) -> None:
        # [add d6 2]: expands over d6 outcomes, adding 2 to each
        assert run(f"{self._F_ADD_An_Bn}\noutput [add d6 2]") == [
            ("output 1", H({3: 1, 4: 1, 5: 1, 6: 1, 7: 1, 8: 1}))
        ]

    def test_no_result_returns_empty(self) -> None:
        # function with no result: statement returns H({})
        assert run("function: nothing { }\noutput [nothing]") == [("output 1", H({}))]

    def test_maximum_recursion_depth_default(self) -> None:
        assert run("function: { result: 1 + [] }\noutput []") == [
            ("output 1", H({10: 1}))
        ]

    def test_maximum_recursion_depth(self) -> None:
        assert run(
            'set "maximum function depth" to 5\nfunction: { result: 1 + [] }\noutput []'
        ) == [("output 1", H({5: 1}))]

    def test_value_returned_after_maxium_recursion_depth_is_empty_die(self) -> None:
        assert run("function: { result: 1 / [] }\noutput []") == [("output 1", H({}))]

    def test_wildcard_param_type_equivalent_to_bare(self) -> None:
        # `:?` is AnyDice's explicit "any type" marker; identical to a bare param.
        # Both should accept a die argument and expand the body once per outcome.
        assert run("function: f X:? { result: X * 2 }\noutput [f d6]") == [
            ("output 1", H({2: 1, 4: 1, 6: 1, 8: 1, 10: 1, 12: 1}))
        ]


class TestFunctionDieParam:
    _F_PICK = "function: pick D:d { result: D }"

    def test_die_param_with_num(self) -> None:
        # int wraps as 1-outcome die
        assert run(f"{self._F_PICK}\noutput [pick 5]") == [("output 1", H({5: 1}))]

    def test_die_param_with_seq(self) -> None:
        # seq sum-coerces to int, then 1-outcome die. AnyDice does NOT extract
        # distinct outcomes here.
        assert run(f"{self._F_PICK}\noutput [pick {{1,2,3}}]") == [
            ("output 1", H({6: 1}))
        ]

    def test_die_param_with_die(self) -> None:
        # die passes through unchanged (no expansion)
        assert run(f"{self._F_PICK}\noutput [pick d6]") == [("output 1", H(6))]

    def test_die_param_with_pool(self) -> None:
        # pool flattens to its summed distribution
        assert run(f"{self._F_PICK}\noutput [pick 2d6]") == [("output 1", H(6) + H(6))]

    def test_die_param_does_not_short_circuit_on_empty(self) -> None:
        # A `:d` parameter receiving an empty die does NOT short-circuit the
        # whole call -- the body runs once with the empty H bound, and the
        # body's conditionals (e.g. `if ROLL = BAD { result: REROLL }`) decide
        # which iterations produce empty (eliminated branches) vs which produce
        # values. Verified against AnyDice (program 17b65) where
        # `[[highest 3 of 4d6] reroll {3..9} as d{}]` produces the [highest 3
        # of 4d6] distribution restricted to outcomes 10..18.
        src = """
function: ROLL:n reroll BAD:s as REROLL:d {
  if ROLL = BAD { result: REROLL }
  result: ROLL
}
output [[highest 3 of 4d6] reroll {3..9} as d{}]
"""
        assert run(src) == [
            (
                "output 1",
                H(
                    {
                        10: 122,
                        11: 148,
                        12: 167,
                        13: 172,
                        14: 160,
                        15: 131,
                        16: 94,
                        17: 54,
                        18: 21,
                    }
                ),
            )
        ]

    def test_die_param_preserves_pool_for_position_ops(self) -> None:
        # AnyDice's `:d` is lossless on pool arguments: `{FIRST,SECOND}@POOL`
        # inside the body must see the actual pool (so multi-position selection
        # works), not the summed H. Prior to this test, our impl collapsed P to
        # H in _invoke's `:d` branch -- which made the body's `{1, 3}@POOL`
        # behave as `{1, 3}@(sum H)` (= a 1-element-pool multi-position lookup
        # = the H itself), instead of "top + bottom of 3d6."
        # Verified against AnyDice (program 428fb).
        src = """
function: pick FIRST:n and SECOND:n from pool POOL:d {
  result: {FIRST, SECOND} @ POOL
}
output [pick 1 and 3 from pool 3d6]
"""
        assert run(src) == [
            (
                "output 1",
                H(
                    {
                        2: 1,
                        3: 6,
                        4: 13,
                        5: 24,
                        6: 37,
                        7: 54,
                        8: 37,
                        9: 24,
                        10: 13,
                        11: 6,
                        12: 1,
                    }
                ),
            )
        ]


class TestFunctionSeqParam:
    _F_COUNT = "function: count X:s { result: #X }"
    _F_SUM12 = "function: sum X:s { result: 1@X + 2@X }"

    def test_seq_param_with_num(self) -> None:
        # int becomes a 1-element seq; #X = 1
        assert run(f"{self._F_COUNT}\noutput [count 5]") == [("output 1", H({1: 1}))]

    def test_seq_param_with_seq(self) -> None:
        assert run(f"{self._F_COUNT}\noutput [count {{1,2,3,4}}]") == [
            ("output 1", H({4: 1}))
        ]

    def test_seq_param_with_die(self) -> None:
        # die-as-:s treats the die opaquely as a 1-element seq (NOT as distinct
        # outcomes). The body still expands over the die's outcomes, but every
        # outcome yields #X = 1, so the result is H({1: 1}).
        assert run(f"{self._F_COUNT}\noutput [count d6]") == [("output 1", H({1: 1}))]

    def test_seq_param_with_die_each_outcome_in_one_elem_seq(self) -> None:
        # The body runs once per die outcome o with X = (o,); 1@X = o, 2@X = 0
        # (out of range), so the body returns o. Recombining over the die's
        # outcomes happens to recover the die's distribution.
        assert run(f"{self._F_SUM12}\noutput [sum d{{10,20,30}}]") == [
            ("output 1", H({10: 1, 20: 1, 30: 1}))
        ]

    def test_seq_param_with_pool_each_roll_is_full_seq(self) -> None:
        # 3d6 as :s binds X to the rolled tuple sorted highest-first by default.
        # The body 1@X + 2@X selects the top two dice and sums them, giving the
        # distribution of "sum of top two of 3d6".
        assert run(f"{self._F_SUM12}\noutput [sum 3d6]") == [
            (
                "output 1",
                H(
                    {
                        2: 1,
                        3: 3,
                        4: 7,
                        5: 12,
                        6: 19,
                        7: 27,
                        8: 34,
                        9: 36,
                        10: 34,
                        11: 27,
                        12: 16,
                    }
                ),
            )
        ]


class TestFunctionMultiPatternDispatch:
    # AnyDice's "function name" is a function's *pattern shape* -- words at fixed
    # positions plus parameter slot count. Param type annotations (:n/:d/:s/:?) are
    # body-evaluation hints, not dispatch keys. A second definition with the same shape
    # REPLACES the first, regardless of how the parameter types differ. The tests below
    # all share a shape (`f` followed by a single param slot), so each new definition
    # overwrites the previous; whichever was defined last is the one the call resolves
    # to.

    def test_die_wins_when_defined_last(self) -> None:
        prog = (
            "function: f X:n { result: X * 100 }\n"
            "function: f X:d { result: X }\n"
            "output [f d6]"
        )
        # :d matched, no expansion -> die passes through
        assert run(prog) == [("output 1", H(6))]

    def test_last_defined_wins(self) -> None:
        prog = (
            "D: 2d{1:1, 2:2, 3:3, 4:4, 5:5, 6:6}\n"
            "function: f X:d { result: X + 2 }\n"
            "output [f D]"
            "function: f X:n { result: X * 100 }\n"
            "output [f D]"
            "function: f X:s { result: X * 10 }\n"
            "output [f D]"
        )
        assert run(prog) == [
            # :d matched, returns D + 2
            (
                "output 1",
                H(
                    {
                        4: 1,
                        5: 4,
                        6: 10,
                        7: 20,
                        8: 35,
                        9: 56,
                        10: 70,
                        11: 76,
                        12: 73,
                        13: 60,
                        14: 36,
                    }
                ),
            ),
            # :n matched, body expands over outcomes
            (
                "output 2",
                H(
                    {
                        200: 1,
                        300: 4,
                        400: 10,
                        500: 20,
                        600: 35,
                        700: 56,
                        800: 70,
                        900: 76,
                        1000: 73,
                        1100: 60,
                        1200: 36,
                    }
                ),
            ),
            # :s matched, body expands over rolls
            (
                "output 3",
                H(
                    {
                        20: 1,
                        30: 4,
                        40: 10,
                        50: 20,
                        60: 35,
                        70: 56,
                        80: 70,
                        90: 76,
                        100: 73,
                        110: 60,
                        120: 36,
                    }
                ),
            ),
        ]


# ---- Function expansion LCM normalization -----------------------------------------------


class TestFunctionExpansionLCM:
    # AnyDice expands an n-typed argument across the argument's outcomes, runs the
    # body once per outcome, and combines the per-iteration return values as a
    # weighted mixture. Per-iteration returns can have different internal totals
    # (e.g. one branch returns a die [sum=k] and another returns a scalar [sum=1]).
    # AnyDice normalizes those internal totals to a common LCM before combining,
    # so each iteration contributes its outer weight, not its outer weight scaled
    # by its inner total. Verified against AnyDice (program 42ac8 for the minimal
    # case; program 3f046 for the boost-style multi-branch case).

    def test_minimal_scalar_vs_die_branches(self) -> None:
        # f(1) returns d4 (sum=4); f(2) returns 2 (sum=1). d2 weights both equally.
        # Per AnyDice (42ac8): P(2) = 1/2 + 1/8 = 5/8.
        src = """
function: f X:n {
 if X = 1 { result: d4 }
 result: X
}
output [f d2]
"""
        assert run(src) == [("output 1", H({1: 1, 2: 5, 3: 1, 4: 1}))]

    def test_boost_outcome_at_pivot(self) -> None:
        # Subset of program 3f046: only the d4-arg variant. The user reported that
        # for n=21 (the only N value that hits the unconditional `result: N` branch
        # because 20 < 21 < 22), AnyDice's count is 80 while ours was 20 -- the
        # 4x ratio matches the d4 sum=4 vs scalar sum=1 mismatch.
        src = """
function: boost N:n low L:n high H:n with D:d {
 if N <= L { result: N - D }
 if N >= H { result: N + D }
 result: N
}
output [boost 2d20 low 20 high 22 with d4]
"""
        result = run(src)
        assert len(result) == 1
        label, h = result[0]
        assert label == "output 1"
        assert h[21] == 80


# ---- Bare-param pass-through (no coercion, no expansion) --------------------------------


class TestBareParamPassthrough:
    # AnyDice's bare-param semantics differ from any of the explicit `n`/`d`/`s`
    # types: the value is passed through to the body without coercion or expansion.
    # The body sees whatever the caller passed -- int as int, seq as seq, die as die.
    # Verified against AnyDice via:
    #   - 42ace: `function: f X { result: X + X }` with `[f d6]` produces 2d6 sum
    #     (not 2*d6 element-wise), confirming X is the die.
    #   - paste-tested: `function: f X { result: # X }` with `[f {1, 2, 3}]` produces
    #     H({3:1}), confirming X is the seq (no sum-coercion).

    def test_bare_param_with_die_runs_body_on_die(self) -> None:
        # X bound to d6; X + X computes the 2d6 sum (convolution), not 2*d6.
        src = "function: f X { result: X + X }\noutput [f d6]"
        assert run(src) == [
            (
                "output 1",
                H(
                    {
                        2: 1,
                        3: 2,
                        4: 3,
                        5: 4,
                        6: 5,
                        7: 6,
                        8: 5,
                        9: 4,
                        10: 3,
                        11: 2,
                        12: 1,
                    }
                ),
            )
        ]

    def test_bare_param_with_seq_keeps_seq(self) -> None:
        # X bound to seq {1, 2, 3}; #X is the length 3.
        src = "function: f X { result: # X }\noutput [f {1, 2, 3}]"
        assert run(src) == [("output 1", H({3: 1}))]

    def test_bare_param_with_int_keeps_int(self) -> None:
        # X bound to int 4567; 2 @ X is the digit-extraction (2nd digit, MSB-first).
        src = "function: f X { result: 2 @ X }\noutput [f 4567]"
        assert run(src) == [("output 1", H({5: 1}))]

    def test_bare_param_arithmetic_is_invariant(self) -> None:
        # `X * 2` on a die produces the same H as per-outcome scalar*2 (because
        # multiplication by a constant scales each outcome the same way). This
        # confirms our existing X:? alias test still passes under no-coercion.
        src = "function: f X { result: X * 2 }\noutput [f d6]"
        assert run(src) == [("output 1", H({2: 1, 4: 1, 6: 1, 8: 1, 10: 1, 12: 1}))]


# ---- Function body returns under expansion (sum-coerce on tuple) ------------------------


class TestFunctionBodySeqReturnSumCoerce:
    # When a function with explicit n-typed params expands across argument outcomes
    # and the body returns a sequence per iteration, AnyDice sum-coerces the seq to
    # a number before accumulating. Our impl previously distributed seq elements
    # as separate outcomes, which double-counted. Verified against AnyDice (program
    # 405c6) where [roll 1d6 1d6] with `result: {A+B, C}` produces an H over
    # A+B+C values, not an H over A+B and C separately.

    def test_seq_return_sum_coerced_simple(self) -> None:
        # Body returns {A+B, 0}; sum is A+B; result is the 2d6 sum distribution.
        src = """
function: roll A:n B:n {
 result: {A + B, 0}
}
output [roll 1d6 1d6]
"""
        assert run(src) == [
            (
                "output 1",
                H(
                    {
                        2: 1,
                        3: 2,
                        4: 3,
                        5: 4,
                        6: 5,
                        7: 6,
                        8: 5,
                        9: 4,
                        10: 3,
                        11: 2,
                        12: 1,
                    }
                ),
            )
        ]

    def test_program_405c6_integration(self) -> None:
        # The full 405c6 program. Combines all three fixes:
        #   (1) bare param `ex A` -> A is bound to the H from [roll]
        #   (2) `2 @ <die>` returns 0 (1-element-pool out-of-range)
        #   (3) [roll]'s seq-returning iterations sum-coerce
        # AnyDice oracle: H({0: 1}).
        src = """
function: roll A:n B:n {
 C: 0
 if (A = 6) {
  C: 1
 }
 if (B = 6) {
  C: C + 1
 }
 S: {A + B, C}
 result: S
}

function: ex A {
 result: 2 @ A
}

output [ex [roll 1d6 1d6]]
"""
        result = run(src)
        assert len(result) == 1
        label, h = result[0]
        assert label == "output 1"
        # Whole result reduces to a single outcome 0; the actual count depends on
        # the inner [roll]'s total weight (36, since 6x6 outcomes), so check that
        # the only key is 0.
        assert set(h.keys()) == {0}


# ---- Function variable scoping -----------------------------------------------------------


class TestFunctionScoping:
    # AnyDice's function call model:
    #   - The callee starts with a snapshot of the CALLER's current bindings (not just
    #     globals) Nested calls inherit from their immediate caller.
    #   - Param bindings overlay that snapshot.
    #   - Writes inside the function body are local: they do not propagate
    #     back to the caller.
    # Equivalently: each frame is a copy-on-call; reads see the snapshot, writes
    # mutate the local copy, and the caller's env is restored on return.

    def test_param_not_visible_after_call(self) -> None:
        # X is bound only inside f's body. Reading it after the call must error.
        prog = "function: f X:n { result: X }\noutput [f 5]\noutput X"
        with pytest.raises(NameError, match=r"undefined variable"):
            run(prog)

    def test_outer_var_visible_inside_function(self) -> None:
        # The function reads a variable defined in the caller's scope.
        prog = "Y: 7\nfunction: g { result: Y }\noutput [g]"
        assert run(prog) == [("output 1", H({7: 1}))]

    def test_function_internal_assignment_does_not_leak(self) -> None:
        # h reassigns Y inside its body; the caller's Y should be untouched.
        prog = "Y: 7\nfunction: h { Y: 99 result: Y }\noutput [h]\noutput Y"
        assert run(prog) == [
            ("output 1", H({99: 1})),
            ("output 2", H({7: 1})),
        ]

    def test_nested_call_inherits_from_caller_not_global(self) -> None:
        # Per program 42aab: a nested function inherits its IMMEDIATE caller's bindings,
        # not the global scope. Three outputs probe the model:
        #   1. The outer anonymous function sets X=5 before calling [inner]. inner reads
        #      X and sees 5, not the global 4.
        #   2. After the call returns, the global X is still 4. The inner X=5 did NOT
        #      leak back.
        #   3. Calling [inner] directly from the global scope sees X=4. No contamination
        #      from the earlier nested call's snapshot.
        prog = (
            "function: {\n"
            "  X: 5\n"
            "  result: [inner]\n"
            "}\n"
            "function: inner { result: X }\n"
            "X: 4\n"
            "output X\n"
            "output []\n"
            "output [inner]"
        )
        assert run(prog) == [
            ("output 1", H({4: 1})),
            ("output 2", H({5: 1})),
            ("output 3", H({4: 1})),
        ]

    def test_assignment_in_one_function_invisible_in_sibling(self) -> None:
        # a sets a local Z. b is called from the global scope (no caller Z), so b cannot
        # see a's Z. Reading Z inside b must raise NameError.
        prog = (
            "function: a { Z: 1 result: Z }\n"
            "function: b { result: Z }\n"
            "output [a]\n"
            "output [b]"
        )
        with pytest.raises(NameError, match=r"undefined variable"):
            run(prog)

    def test_recursion_uses_independent_param_frames(self) -> None:
        # Triangular sum via recursion: each recursive call has its own N param, not
        # contaminated by the caller's N. depth(0) returns 0. depth(N) for N>0 returns N
        # + depth(N-1).
        prog = (
            'set "maximum function depth" to 20\n'
            "function: tri N:n {\n"
            "  if N = 0 { result: 0 }\n"
            "  result: N + [tri N - 1]\n"
            "}\n"
            "output [tri 5]"
        )
        # 5 + 4 + 3 + 2 + 1 + 0 = 15
        assert run(prog) == [("output 1", H({15: 1}))]


# ---- Function dispatch: multi-word and multi-shape patterns ------------------------------


class TestFunctionDispatchShapes:
    # AnyDice's "function name" is its pattern shape: words at fixed positions plus
    # parameter slots. Distinct shapes (different words, different word positions,
    # different param counts) are different callables that coexist without conflict.
    # Calls that don't match any registered shape are an error.

    def test_word_interleaved_pattern(self) -> None:
        # Words and params can alternate. `add 2 to 3` matches the shape ('add', None,
        # 'to', None) -- two literal words around two slots.
        prog = "function: add A:n to B:n { result: A + B }\noutput [add 2 to 3]"
        assert run(prog) == [("output 1", H({5: 1}))]

    def test_three_word_pattern(self) -> None:
        # Pattern with no params at all.
        prog = "function: the answer { result: 42 }\noutput [the answer]"
        assert run(prog) == [("output 1", H({42: 1}))]

    def test_distinct_shapes_share_first_word(self) -> None:
        # Two functions with the same first word but different shapes coexist. `[fmt X]`
        # (one slot) and `[fmt X around Y]` (two slots, interleaved word) are distinct
        # callables.
        prog = (
            "function: fmt X:n { result: X * 10 }\n"
            "function: fmt X:n around Y:n { result: X + Y }\n"
            "output [fmt 5]\n"
            "output [fmt 3 around 4]"
        )
        assert run(prog) == [
            ("output 1", H({50: 1})),
            ("output 2", H({7: 1})),
        ]

    def test_param_count_alone_distinguishes_shapes(self) -> None:
        # Same words, different number of param slots is a different shape. No
        # word-position differences. Shape diverges only on param count.
        prog = (
            "function: f A:n { result: A }\n"
            "function: f A:n B:n { result: A * B }\n"
            "output [f 7]\n"
            "output [f 3 4]"
        )
        assert run(prog) == [
            ("output 1", H({7: 1})),
            ("output 2", H({12: 1})),
        ]

    def test_undefined_call_raises_name_error(self) -> None:
        # No function with the shape ('mystery', None) was registered.
        with pytest.raises(NameError, match=r"undefined function"):
            run("output [mystery 5]")

    def test_shape_mismatch_does_not_silently_match_other_shape(self) -> None:
        # `add A to B` is registered, but the call uses different connecting words.
        # AnyDice should not silently match `add A:n to B:n` for `[add 2 plus 3]`. The
        # connecting word `plus` is part of the shape.
        prog = "function: add A:n to B:n { result: A + B }\noutput [add 2 plus 3]"
        with pytest.raises(NameError, match=r"undefined function"):
            run(prog)


# ---- Conditionals (if / else if / else) --------------------------------------------------


class TestIfStmt:
    def test_if_true_runs_body(self) -> None:
        assert run("if 1 { output 1 }") == [("output 1", H({1: 1}))]

    def test_if_false_no_body(self) -> None:
        # No outputs are emitted when the condition is false and there is no else
        assert run("if 0 { output 1 }") == []

    def test_if_true_no_body(self) -> None:
        # No outputs are emitted when the condition is false and there is no else
        assert run("if 1 {} else { output 1 }") == []

    def test_if_false_empty_else_body(self) -> None:
        # No outputs are emitted when the condition is false and there is an empty else
        assert run("if 0 { output 1 } else {}") == []

    def test_if_else_true(self) -> None:
        assert run("if 1 { output 1 } else { output 2 }") == [("output 1", H({1: 1}))]

    def test_if_else_false(self) -> None:
        assert run("if 0 { output 1 } else { output 2 }") == [("output 1", H({2: 1}))]

    def test_else_if_chain_picks_first_match(self) -> None:
        assert run(
            "if 0 { output 1 }\n"
            "else if 0 { output 2 }\n"
            "else if 1 { output 3 }\n"
            "else { output 4 }"
        ) == [("output 1", H({3: 1}))]

    def test_else_if_chain_no_match_runs_else(self) -> None:
        assert run("if 0 { output 1 }\nelse if 0 { output 2 }\nelse { output 3 }") == [
            ("output 1", H({3: 1}))
        ]

    def test_else_if_chain_no_match_no_else(self) -> None:
        assert run("if 0 { output 1 } else if 0 { output 2 }") == []

    def test_seq_condition_is_type_error(self) -> None:
        # AnyDice rejects sequences as boolean conditions (verified via program 42aac,
        # which errors on `if {} { ... }` with "Boolean values can only be numbers").
        # Sequences are NOT sum-coerced in condition position.
        with pytest.raises(TypeError, match=r"as boolean condition"):
            run("if {1,2,3} { output 1 } else { output 2 }")

    def test_seq_condition_zero_sum_is_still_type_error(self) -> None:
        # Even a sequence whose sum is 0 doesn't coerce. Still a TypeError.
        with pytest.raises(TypeError, match=r"as boolean condition"):
            run("if {0,0} { output 1 } else { output 2 }")

    def test_empty_seq_condition_is_type_error(self) -> None:
        # Per program 42aac
        with pytest.raises(TypeError, match=r"as boolean condition"):
            run("if {} { output 1 } else { output 2 }")

    def test_var_condition(self) -> None:
        assert run("X: 5\nif X { output 1 } else { output 2 }") == [
            ("output 1", H({1: 1}))
        ]

    def test_nested_if(self) -> None:
        assert run("if 1 { if 1 { output 99 } }") == [("output 1", H({99: 1}))]

    def test_var_assigned_inside_if_visible_after(self) -> None:
        # Variables assigned inside an `if` body remain in the surrounding scope
        assert run("if 1 { X: 7 }\noutput X") == [("output 1", H({7: 1}))]


# ---- Loops (loop X over <seq>) -----------------------------------------------------------


class TestLoopStmt:
    def test_loop_iterates_sequence(self) -> None:
        # Sum integers 1..3 by accumulator
        assert run("T: 0\nloop X over {1..3} { T: T + X }\noutput T") == [
            ("output 1", H({6: 1}))
        ]

    def test_loop_iterates_explicit_seq(self) -> None:
        assert run("T: 0\nloop X over {2,4,6} { T: T + X }\noutput T") == [
            ("output 1", H({12: 1}))
        ]

    def test_loop_empty_seq_no_iterations(self) -> None:
        # Body never executes. The accumulator retains its initial value.
        assert run("T: 99\nloop X over {} { T: 0 }\noutput T") == [
            ("output 1", H({99: 1}))
        ]

    def test_loop_descending_range_no_iterations(self) -> None:
        # `{4..1}` is empty in AnyDice. Loop body should not run.
        assert run("T: 99\nloop X over {4..1} { T: 0 }\noutput T") == [
            ("output 1", H({99: 1}))
        ]

    def test_loop_outputs_per_iteration(self) -> None:
        assert run("loop X over {1..3} { output X }") == [
            ("output 1", H({1: 1})),
            ("output 2", H({2: 1})),
            ("output 3", H({3: 1})),
        ]

    def test_loop_var_visible_after_loop(self) -> None:
        # AnyDice does not introduce a child scope for loop bodies. The loop variable
        # retains its last-assigned value after the loop completes.
        assert run("loop X over {1..3} { }\noutput X") == [("output 1", H({3: 1}))]

    def test_loop_var_persists_assignments_after_loop(self) -> None:
        # An assignment inside the loop body remains in scope after the loop
        assert run("loop X over {1..3} { Y: X }\noutput Y") == [("output 1", H({3: 1}))]

    def test_nested_loop(self) -> None:
        # Sum over a 2x2 grid: (1,1) + (1,2) + (2,1) + (2,2) = 6
        assert run(
            "T: 0\n"
            "loop X over {1..2} {\n"
            "  loop Y over {1..2} {\n"
            "    T: T + X * Y\n"
            "  }\n"
            "}\n"
            "output T"
        ) == [("output 1", H({9: 1}))]  # 1*1 + 1*2 + 2*1 + 2*2 = 9

    def test_loop_over_num_is_type_error(self) -> None:
        # `loop X over <num>` is invalid; the iterable must be a sequence.
        with pytest.raises(TypeError, match=r"loop over must be a sequence"):
            run("loop X over 5 { output X }")

    def test_loop_over_die_is_type_error(self) -> None:
        # A die is not iterable in AnyDice's loop construct -- only sequences.
        with pytest.raises(TypeError, match=r"loop over must be a sequence"):
            run("loop X over d6 { output X }")

    def test_loop_over_pool_is_type_error(self) -> None:
        # A pool (`2d6`) is also rejected, even though it carries positional info.
        with pytest.raises(TypeError, match=r"loop over must be a sequence"):
            run("loop X over 2d6 { output X }")


# ---- Statement context restrictions ------------------------------------------------------


class TestStatementContextRestrictions:
    # Per AnyDice's EBNF, certain statements are restricted to either top-level
    # or function-body contexts. The grammar enforces these at parse time.
    #   top-level only: output, function definition, set
    #   function-body only: result

    def test_output_inside_function_is_parse_error(self) -> None:
        with pytest.raises(UnexpectedInput):
            run("function: foo { output 5 result: 1 }")

    def test_nested_function_definition_is_parse_error(self) -> None:
        with pytest.raises(UnexpectedInput):
            run("function: outer { function: inner { result: 1 } result: 2 }")

    def test_set_inside_function_is_parse_error(self) -> None:
        with pytest.raises(UnexpectedInput):
            run('function: foo { set "maximum function depth" to 5 result: 1 }')

    def test_result_at_top_level_is_parse_error(self) -> None:
        with pytest.raises(UnexpectedInput):
            run("result: 5")

    def test_result_in_top_level_loop_is_parse_error(self) -> None:
        # Top-level `loop_stmt` body uses `stmt*`, which excludes result_stmt
        with pytest.raises(UnexpectedInput):
            run("loop X over {1..3} { result: X }")

    def test_result_in_top_level_if_is_parse_error(self) -> None:
        # Same restriction for top-level `if_stmt`
        with pytest.raises(UnexpectedInput):
            run("if 1 { result: 5 }")

    def test_output_inside_function_body_loop_is_parse_error(self) -> None:
        # Body-level loops use body_stmt*, which still excludes output
        with pytest.raises(UnexpectedInput):
            run("function: foo { loop X over {1..3} { output X } result: 1 }")

    def test_output_inside_function_body_if_is_parse_error(self) -> None:
        with pytest.raises(UnexpectedInput):
            run("function: foo { if 1 { output 1 } result: 1 }")

    def test_stmt_after_result_in_function_body_is_parse_error(self) -> None:
        # AnyDice rejects statements after `result:` in a function body
        # (verified via 2f5ce, which errors at "loop THROW" expecting `}`
        # after `result: NIX`). Our grammar enforces this by allowing
        # `result_stmt` only as the optional last element of a body block.
        with pytest.raises(UnexpectedInput):
            run("function: f { result: 1 X: 2 }")

    def test_loop_after_result_in_function_body_is_parse_error(self) -> None:
        with pytest.raises(UnexpectedInput):
            run("function: f { result: 1 loop X over {1..3} { Y: X } }")

    def test_result_at_end_of_if_branch_is_ok(self) -> None:
        # Multiple `result:` calls are fine as long as each is the last
        # statement in its enclosing block (each if-branch counts as a block).
        # Pattern from 24c93's `roll` function.
        assert run(
            "function: f X:n {\n"
            "  if X = 1 { result: 1 }\n"
            "  if X = 2 { result: 2 }\n"
            "  result: 0\n"
            "}\n"
            "output [f d3]"
        ) == [("output 1", H({0: 1, 1: 1, 2: 1}))]

    def test_function_def_inside_loop_is_ok(self) -> None:
        # AnyDice DOES allow function definitions inside top-level loops
        # (verified via 24c93, which has `function: dc after K:n successes`
        # nested inside `loop Y over {1,3,5} { ... }`). Pin this so it
        # doesn't drift back to "rejected".
        src = (
            "loop X over {1, 2, 3} {\n"
            "  function: factor { result: X }\n"
            '  output [factor] named "factor [X]"\n'
            "}"
        )
        result = run(src)
        assert len(result) == 3
        assert result[0] == ("factor 1", H({1: 1}))
        assert result[1] == ("factor 2", H({2: 1}))
        assert result[2] == ("factor 3", H({3: 1}))


# ---- Conditionals inside function bodies -------------------------------------------------


class TestIfStmtInFunctionBody:
    def test_result_in_if_branch_returns_from_function(self) -> None:
        # When `result:` lives inside an if branch, hitting it must return from the
        # enclosing function regardless of nesting depth. The body's trailing `result:
        # 1` should not run for outcomes where the if fired.
        prog = (
            "function: classify X:n {\n"
            "  if X > 5 { result: 100 }\n"
            "  result: 1\n"
            "}\n"
            "output [classify d6]"
        )
        # X expands over d6 outcomes 1..6: 1..5 -> 1; 6 -> 100
        assert run(prog) == [("output 1", H({1: 5, 100: 1}))]

    def test_result_in_else_branch_returns_from_function(self) -> None:
        prog = (
            "function: classify X:n {\n"
            "  if X = 1 { result: 999 } else { result: X * 10 }\n"
            "}\n"
            "output [classify d3]"
        )
        # d3 outcomes 1..3: 1 -> 999; 2 -> 20; 3 -> 30
        assert run(prog) == [("output 1", H({999: 1, 20: 1, 30: 1}))]

    def test_else_if_chain_in_function_body(self) -> None:
        prog = (
            "function: tier X:n {\n"
            "  if X = 1 { result: 1 }\n"
            "  else if X = 2 { result: 20 }\n"
            "  else { result: 999 }\n"
            "}\n"
            "output [tier d3]"
        )
        assert run(prog) == [("output 1", H({1: 1, 20: 1, 999: 1}))]

    def test_if_assignment_visible_to_trailing_result(self) -> None:
        # An `if` body assigning a variable (not result:ing) leaves the var
        # available to a later `result:` in the same function body.
        prog = (
            "function: f X:n {\n"
            "  Y: 0\n"
            "  if X > 3 { Y: X * 100 }\n"
            "  result: Y\n"
            "}\n"
            "output [f d6]"
        )
        # 1,2,3 -> 0; 4 -> 400; 5 -> 500; 6 -> 600
        assert run(prog) == [("output 1", H({0: 3, 400: 1, 500: 1, 600: 1}))]


# ---- Loops inside function bodies --------------------------------------------------------


class TestLoopStmtInFunctionBody:
    def test_loop_accumulator_in_function_body(self) -> None:
        prog = (
            "function: triangular N:n {\n"
            "  T: 0\n"
            "  loop X over {1..N} { T: T + X }\n"
            "  result: T\n"
            "}\n"
            "output [triangular 4]"
        )
        # 1+2+3+4 = 10
        assert run(prog) == [("output 1", H({10: 1}))]

    def test_loop_with_die_count(self) -> None:
        # N:n expands over die outcomes; for each, the loop runs that many times
        # accumulating, and the function returns the per-outcome sum.
        prog = (
            "function: triangular N:n {\n"
            "  T: 0\n"
            "  loop X over {1..N} { T: T + X }\n"
            "  result: T\n"
            "}\n"
            "output [triangular d4]"
        )
        # d4 outcomes 1..4: triangulars 1, 3, 6, 10
        assert run(prog) == [("output 1", H({1: 1, 3: 1, 6: 1, 10: 1}))]

    def test_result_in_loop_body_returns_from_function(self) -> None:
        # The first `result:` to fire returns from the function. Here it fires on the
        # very first iteration, so the function returns 1 unconditionally.
        prog = (
            "function: f {\n"
            "  loop X over {1..5} { result: X }\n"
            "  result: 999\n"
            "}\n"
            "output [f]"
        )
        assert run(prog) == [("output 1", H({1: 1}))]

    def test_loop_inside_if_inside_function(self) -> None:
        prog = (
            "function: f X:n {\n"
            "  T: 0\n"
            "  if X > 0 { loop Y over {1..X} { T: T + Y } }\n"
            "  result: T\n"
            "}\n"
            "output [f d3]"
        )
        # d3 outcomes 1..3: triangular(1)=1, triangular(2)=3, triangular(3)=6
        assert run(prog) == [("output 1", H({1: 1, 3: 1, 6: 1}))]


# ---- String interpolation in named outputs -----------------------------------------------


class TestStringInterpolation:
    # AnyDice's only interpolation site is the string given to `output ... named`.
    # `[UPPERNAME]` references are resolved from the current scope and substituted as
    # text. Set statements don't interpolate. Their key is always a literal selector
    # (one of the three documented setting names) and their value is either a numeric
    # expression a literal string value (e.g., "lowest first" / "highest first").
    #
    # Only UPPERNAME variables interpolate; bracketed text that doesn't match
    # `[A-Z][A-Z_]*` is preserved verbatim, including the brackets.

    def test_interpolation_replaces_var_with_int_value(self) -> None:
        assert run('X: 42\noutput 1 named "answer is [X]"') == [
            ("answer is 42", H({1: 1}))
        ]

    def test_interpolation_at_start(self) -> None:
        assert run('N: 5\noutput Nd6 named "[N]d6"') == [
            ("5d6", H(6) + H(6) + H(6) + H(6) + H(6))
        ]

    def test_interpolation_at_end(self) -> None:
        assert run('X: 7\noutput 1 named "value: [X]"') == [("value: 7", H({1: 1}))]

    def test_interpolation_only_no_literal_text(self) -> None:
        assert run('X: 9\noutput 1 named "[X]"') == [("9", H({1: 1}))]

    def test_multiple_interpolations(self) -> None:
        assert run('A: 1\nB: 2\noutput 1 named "[A] and [B]"') == [
            ("1 and 2", H({1: 1}))
        ]

    def test_loop_var_interpolated_per_iteration(self) -> None:
        # The classic AnyDice idiom: emit a labeled output per iteration.
        assert run('loop X over {1..3} { output X named "iter [X]" }') == [
            ("iter 1", H({1: 1})),
            ("iter 2", H({2: 1})),
            ("iter 3", H({3: 1})),
        ]

    def test_negative_value_interpolates_with_sign(self) -> None:
        assert run('X: -7\noutput 1 named "neg [X]"') == [("neg -7", H({1: 1}))]

    def test_zero_value_interpolates(self) -> None:
        assert run('X: 0\noutput 1 named "x = [X]"') == [("x = 0", H({1: 1}))]

    def test_undefined_var_in_interpolation_raises(self) -> None:
        with pytest.raises(NameError, match=r"undefined variable"):
            run('output 1 named "[UNSET]"')

    def test_non_uppername_bracketed_text_preserved_verbatim(self) -> None:
        # Per AnyDice (program 42aae): only [UPPERNAME] interpolates. Brackets
        # around anything else are part of the literal label text.
        assert run('output 0 named "[2 * 3]"') == [("[2 * 3]", H({0: 1}))]

    def test_non_uppername_arbitrary_text_preserved(self) -> None:
        assert run('output 0 named "[I\'m an arbitrary string!]"') == [
            ("[I'm an arbitrary string!]", H({0: 1}))
        ]

    def test_die_value_interpolates_as_opaque_marker(self) -> None:
        # Non-empty die renders opaquely. We don't reverse-engineer AnyDice's
        # source-text rendering ("d6", etc.); "d{?}" conveys "this was a die".
        assert run('D: d6\noutput 1 named "die: [D]"') == [("die: d{?}", H({1: 1}))]

    def test_pool_value_interpolates_with_size(self) -> None:
        # A pool's size is preserved in the marker.
        assert run('D: 2d6\noutput 1 named "pool: [D]"') == [("pool: 2d{?}", H({1: 1}))]

    def test_seq_value_interpolates_as_opaque_marker(self) -> None:
        assert run('S: {1..4}\noutput 1 named "seq: [S]"') == [("seq: {?}", H({1: 1}))]

    def test_empty_seq_interpolates_distinctly(self) -> None:
        # Empties get distinct markers as a debugging aid: "{}" vs the opaque
        # "{?}" for a populated seq.
        assert run('S: {}\noutput 1 named "empty: [S]"') == [("empty: {}", H({1: 1}))]

    def test_empty_die_interpolates_distinctly(self) -> None:
        assert run('D: d{}\noutput 1 named "empty: [D]"') == [("empty: d{}", H({1: 1}))]

    def test_interpolation_uses_value_at_output_time(self) -> None:
        # The label is computed when the `output` statement runs, using the
        # variable's value at that point -- not at definition or any earlier
        # time. After the loop, Y holds 6 (the running sum 1+2+3).
        assert run(
            'X: 5\nY: 0\nloop I over {1..3} { Y: Y + I }\noutput Y named "[X]+[Y]"'
        ) == [("5+6", H({6: 1}))]


# ---- Builtin: [highest of A and B] -------------------------------------------------------


class TestBuiltinHighestOfAnd:
    def test_num_num(self) -> None:
        assert run("output [highest of 3 and 5]") == [("output 1", H({5: 1}))]

    def test_num_num_swapped(self) -> None:
        assert run("output [highest of 5 and 3]") == [("output 1", H({5: 1}))]

    def test_num_num_tie(self) -> None:
        assert run("output [highest of 5 and 5]") == [("output 1", H({5: 1}))]

    def test_num_num_negative(self) -> None:
        assert run("output [highest of -3 and -5]") == [("output 1", H({-3: 1}))]

    def test_die_num(self) -> None:
        # max(1,3)=3, max(2,3)=3, max(3,3)=3, max(4,3)=4, max(5,3)=5, max(6,3)=6
        assert run("output [highest of d6 and 3]") == [
            ("output 1", H({3: 3, 4: 1, 5: 1, 6: 1}))
        ]

    def test_num_die(self) -> None:
        # Symmetric -- order should not matter.
        assert run("output [highest of 3 and d6]") == [
            ("output 1", H({3: 3, 4: 1, 5: 1, 6: 1}))
        ]

    def test_die_die(self) -> None:
        # max of two d6s: count of (a,b) with max=k is 2k-1 for k=1..6.
        assert run("output [highest of d6 and d6]") == [
            ("output 1", H({1: 1, 2: 3, 3: 5, 4: 7, 5: 9, 6: 11}))
        ]

    def test_seq_num(self) -> None:
        # n-typed param sum-coerces sequences: {1,2}=3, max(3,5)=5
        assert run("output [highest of {1,2} and 5]") == [("output 1", H({5: 1}))]

    def test_empty_die_propagates(self) -> None:
        # n-typed param: empty die yields H({}).
        assert run("output [highest of d{} and 3]") == [("output 1", H({}))]

    def test_empty_die_on_right_propagates(self) -> None:
        # Symmetric: empty die on either side yields H({}). Verified against
        # AnyDice (program 42ac6).
        assert run("output [highest of d6 and d{}]") == [("output 1", H({}))]


# ---- Builtin: [highest N of P] -----------------------------------------------------------


class TestBuiltinHighestNOf:
    def test_highest_1_of_1d6(self) -> None:
        assert run("output [highest 1 of 1d6]") == [
            ("output 1", H({1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1}))
        ]

    def test_highest_1_of_2d6(self) -> None:
        # Equivalent to max of 2d6.
        assert run("output [highest 1 of 2d6]") == [
            ("output 1", H({1: 1, 2: 3, 3: 5, 4: 7, 5: 9, 6: 11}))
        ]

    def test_highest_2_of_2d6(self) -> None:
        # Equivalent to sum of 2d6.
        assert run("output [highest 2 of 2d6]") == [
            (
                "output 1",
                H(
                    {
                        2: 1,
                        3: 2,
                        4: 3,
                        5: 4,
                        6: 5,
                        7: 6,
                        8: 5,
                        9: 4,
                        10: 3,
                        11: 2,
                        12: 1,
                    }
                ),
            )
        ]

    def test_highest_3_of_4d6_dnd_classic(self) -> None:
        # 4d6 keep highest 3 -- the classic D&D ability-score distribution.
        assert run("output [highest 3 of 4d6]") == [
            (
                "output 1",
                H(
                    {
                        3: 1,
                        4: 4,
                        5: 10,
                        6: 21,
                        7: 38,
                        8: 62,
                        9: 91,
                        10: 122,
                        11: 148,
                        12: 167,
                        13: 172,
                        14: 160,
                        15: 131,
                        16: 94,
                        17: 54,
                        18: 21,
                    }
                ),
            )
        ]

    def test_highest_0_of_pool(self) -> None:
        # n=0: nothing kept; AnyDice (program 42ac6) returns H({0: 1}).
        assert run("output [highest 0 of 4d6]") == [("output 1", H({0: 1}))]

    def test_highest_n_exceeds_pool_size(self) -> None:
        # n=5 of 4-die pool: AnyDice (program 42ac6) returns the full pool sum.
        # Selectors past the pool's leftmost position contribute nothing, so the
        # result is identical to summing all 4 dice.
        expected = P(6, 6, 6, 6).h()
        assert run("output [highest 5 of 4d6]") == [("output 1", expected)]

    def test_highest_n_of_empty_pool(self) -> None:
        # AnyDice (program 42ac6): `0d6` parses as a zero-die pool; `highest 3 of` it
        # returns H({0: 1}).
        assert run("output [highest 3 of 0d6]") == [("output 1", H({0: 1}))]

    def test_highest_negative_n(self) -> None:
        # Negative n: AnyDice (program 42ac6) returns H({0: 1}). Our impl builds an
        # empty selector tuple for n <= 0, producing the same result.
        assert run("output [highest -1 of 4d6]") == [("output 1", H({0: 1}))]

    def test_highest_n_of_pool_collapsed_via_arith(self) -> None:
        # Per AnyDice (program 42ac6), `(4d6 + 4d6)` collapses to a single die (the
        # 8d6 sum) before `highest 3 of` is applied -- so the result equals the 8d6
        # sum, not the top-3 of 8 dice. We match this because `P + P` sum-coerces
        # to H in our interpreter, and `[highest N of H]` wraps in a 1-element pool
        # whose single element is the H itself. (See todo 31 for the related
        # pool-syntactic-origin question on the literal `NdX` form.)
        expected = P(6, 6, 6, 6, 6, 6, 6, 6).h()
        assert run("output [highest 3 of (4d6 + 4d6)]") == [("output 1", expected)]


# ---- Builtin: [count A in B] -------------------------------------------------------


class TestBuiltinCountIn:
    # Verified against AnyDice (program 42ad4). `[count VALS in SEQ]` counts
    # how many elements of SEQ appear in (the set of) VALS. Both args are :s,
    # so dies/pools expand per-outcome / per-roll.

    def test_seq_in_seq_with_repeats(self) -> None:
        # Each occurrence of an element of SEQ in VALS counts; not set membership.
        # SEQ = {1,2,2,3}, VALS = {1,2}: matches at positions 1, 2, 3 -> 3.
        assert run("output [count {1, 2} in {1, 2, 2, 3}]") == [("output 1", H({3: 1}))]

    def test_seq_in_self(self) -> None:
        assert run("C: {1, 2, 3}\noutput [count C in C]") == [("output 1", H({3: 1}))]

    def test_disjoint(self) -> None:
        assert run("output [count {1, 3} in {2, 4, 6}]") == [("output 1", H({0: 1}))]

    def test_empty_vals(self) -> None:
        assert run("output [count {} in {1, 2, 3}]") == [("output 1", H({0: 1}))]

    def test_empty_seq(self) -> None:
        assert run("output [count {1, 2} in {}]") == [("output 1", H({0: 1}))]

    def test_int_in_die_expansion(self) -> None:
        # 1d6: each outcome treated as a 1-element seq under :s. For each die
        # face, count occurrences of 5 in (face,): 1 if face==5 else 0.
        # Combined: H({0:5, 1:1}).
        assert run("output [count 5 in 1d6]") == [("output 1", H({0: 5, 1: 1}))]

    def test_int_in_pool_expansion(self) -> None:
        # 4d6: roll-based expansion via rolls_with_counts. For each (sorted)
        # 4-tuple roll, count how many of its elements are in {1,2,3} -- aka
        # binomial(4, k) * P(low half)^k. Result is the binomial-4 distribution.
        assert run("output [count {1..3} in 4d6]") == [
            ("output 1", H({0: 1, 1: 4, 2: 6, 3: 4, 4: 1}))
        ]

    def test_vals_multiset_dupes_count(self) -> None:
        # AnyDice counts VALS as a multiset, not a set: an element appearing
        # twice in VALS contributes 2 to the count for each match in SEQ.
        # Single-shot oracle: `[count {6, 6} in {6}]` = 2.
        assert run("output [count {6, 6} in {6}]") == [("output 1", H({2: 1}))]

    def test_vals_multiset_partial_dupes(self) -> None:
        # VALS = {1..7, 1..3} = (1..7) ++ (1..3) -- so faces 1, 2, 3 appear
        # twice and 4..7 once each. Per-die count for 1d12: faces 1..3 give 2,
        # 4..7 give 1, 8..12 give 0. H({0:5, 1:4, 2:3}).
        assert run("output [count {1..7, 1..3} in 1d12]") == [
            ("output 1", H({0: 5, 1: 4, 2: 3}))
        ]


# ---- Builtin: [sort SEQ] -----------------------------------------------------------------


class TestBuiltinSort:
    # AnyDice's `[sort SEQ]` returns a sorted sequence whose source-order position 1
    # is the "most prominent" element per the current position-order setting:
    #   - Under "highest first" (default): position 1 = HIGHEST -> DESC sort.
    #   - Under "lowest first":            position 1 = LOWEST  -> ASC sort.
    # Verified against AnyDice (program 42afc).

    def test_position_one_default_is_highest(self) -> None:
        assert run("output 1 @ [sort {3, 1, 2}]") == [("output 1", H({3: 1}))]

    def test_position_three_default_is_lowest(self) -> None:
        assert run("output 3 @ [sort {3, 1, 2}]") == [("output 1", H({1: 1}))]

    def test_position_one_lowest_first_is_lowest(self) -> None:
        assert run(
            'set "position order" to "lowest first"\noutput 1 @ [sort {3, 1, 2}]'
        ) == [("output 1", H({1: 1}))]

    def test_position_three_lowest_first_is_highest(self) -> None:
        assert run(
            'set "position order" to "lowest first"\noutput 3 @ [sort {3, 1, 2}]'
        ) == [("output 1", H({3: 1}))]

    def test_sort_preserves_duplicates(self) -> None:
        # `output` of the sorted seq coerces to count-dict; duplicates remain.
        # Verified via 42afb (`[sort {2, 2, 1, 1}]` -> H({1:2, 2:2}) gcd-reduced
        # to H({1:1, 2:1}) on AnyDice's display).
        assert run("output [sort {2, 2, 1, 1}]") == [("output 1", H({1: 2, 2: 2}))]

    def test_sort_empty(self) -> None:
        assert run("output [sort {}]") == [("output 1", H({}))]

    def test_sort_singleton(self) -> None:
        assert run("output [sort {7}]") == [("output 1", H({7: 1}))]

    def test_sort_with_negatives(self) -> None:
        # Per AnyDice (42afb): negatives sort numerically.
        assert run("output [sort {-3, 1, -2}]") == [
            ("output 1", H({-3: 1, -2: 1, 1: 1}))
        ]

    def test_sort_die_yields_die(self) -> None:
        # d6 expands per-outcome through :s; sort of 1-element seq is the
        # element; sum-coerce-on-tuple-result yields the face. Result = d6.
        # Verified via 42afb.
        assert run("output [sort d6]") == [
            ("output 1", H({1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1}))
        ]

    def test_sort_pool_yields_sum(self) -> None:
        # 2d6 expands per-roll through :s; sort of (sorted) 2-tuple is itself;
        # sum-coerce-on-tuple-result yields the roll's sum. Result = 2d6 sum.
        # Verified via 42afb.
        assert run("output [sort 2d6]") == [
            (
                "output 1",
                H(
                    {
                        2: 1,
                        3: 2,
                        4: 3,
                        5: 4,
                        6: 5,
                        7: 6,
                        8: 5,
                        9: 4,
                        10: 3,
                        11: 2,
                        12: 1,
                    }
                ),
            )
        ]


# ---- Set statement value validation ----------------------------------------------------


class TestSetSettingValidation:
    # AnyDice (probe 42aff and follow-ups): `"explode depth"` and
    # `"maximum function depth"` may only be set to a POSITIVE INTEGER (>=1).
    # Setting them to 0, a negative integer, or a string yields a calculation
    # error.

    def test_explode_depth_zero_errors(self) -> None:
        with pytest.raises(ValueError, match="positive integer"):
            run('set "explode depth" to 0')

    def test_explode_depth_negative_errors(self) -> None:
        with pytest.raises(ValueError, match="positive integer"):
            run('set "explode depth" to -1')

    def test_explode_depth_string_errors(self) -> None:
        with pytest.raises(ValueError, match="positive integer"):
            run('set "explode depth" to "2"')

    def test_explode_depth_one_is_ok(self) -> None:
        run('set "explode depth" to 1')

    def test_max_function_depth_zero_errors(self) -> None:
        with pytest.raises(ValueError, match="positive integer"):
            run('set "maximum function depth" to 0')

    def test_max_function_depth_negative_errors(self) -> None:
        with pytest.raises(ValueError, match="positive integer"):
            run('set "maximum function depth" to -1')

    def test_max_function_depth_string_errors(self) -> None:
        with pytest.raises(ValueError, match="positive integer"):
            run('set "maximum function depth" to "10"')


# ---- Builtin: [explode <die>] ----------------------------------------------------------


class TestBuiltinExplode:
    # Verified against AnyDice (programs 42aff, 42b00). `[explode <die>]`
    # rerolls when the *max* face is rolled, summing the rerolls; default
    # `explode depth` is 2 (so up to 2 extra rerolls past the original).

    def test_explode_d2_default(self) -> None:
        # d2 outcomes 1, 2 (max=2). Depth 2: max-chain caps at 3 dice.
        # 1 (no explode): 1/2 -> 4/8.
        # 2+1: 1/4 -> 2/8.
        # 2+2+1: 1/8.
        # 2+2+2: 1/8 (depth limit, no more rerolls).
        assert run("output [explode d2]") == [("output 1", H({1: 4, 3: 2, 5: 1, 6: 1}))]

    def test_explode_d6_default(self) -> None:
        # Default depth 2. Total = 6^3 = 216.
        assert run("output [explode d6]") == [
            (
                "output 1",
                H(
                    {
                        1: 36,
                        2: 36,
                        3: 36,
                        4: 36,
                        5: 36,
                        7: 6,
                        8: 6,
                        9: 6,
                        10: 6,
                        11: 6,
                        13: 1,
                        14: 1,
                        15: 1,
                        16: 1,
                        17: 1,
                        18: 1,
                    }
                ),
            )
        ]

    def test_explode_d6_depth_1(self) -> None:
        # Total = 6^2 = 36. Outcome 12 (= 6+6) appears weight 1: at depth 1
        # the second roll's 6 terminates without further explode.
        assert run('set "explode depth" to 1\noutput [explode d6]') == [
            (
                "output 1",
                H(
                    {
                        1: 6,
                        2: 6,
                        3: 6,
                        4: 6,
                        5: 6,
                        7: 1,
                        8: 1,
                        9: 1,
                        10: 1,
                        11: 1,
                        12: 1,
                    }
                ),
            )
        ]

    def test_explode_d6_depth_3(self) -> None:
        # Total = 6^4 = 1296. Outcomes reach 24 (= 6+6+6+6).
        assert run('set "explode depth" to 3\noutput [explode d6]') == [
            (
                "output 1",
                H(
                    {
                        1: 216,
                        2: 216,
                        3: 216,
                        4: 216,
                        5: 216,
                        7: 36,
                        8: 36,
                        9: 36,
                        10: 36,
                        11: 36,
                        13: 6,
                        14: 6,
                        15: 6,
                        16: 6,
                        17: 6,
                        19: 1,
                        20: 1,
                        21: 1,
                        22: 1,
                        23: 1,
                        24: 1,
                    }
                ),
            )
        ]

    def test_explode_singleton_die_always_max(self) -> None:
        # d{5} has only one outcome, which is the max -> always explodes.
        # At depth 2 -> 5+5+5 = 15.
        assert run("output [explode d{5}]") == [("output 1", H({15: 1}))]

    def test_explode_empty_die(self) -> None:
        # Empty die propagates as empty.
        assert run("output [explode d{}]") == [("output 1", H({}))]

    def test_explode_pool_collapses_to_sum_first(self) -> None:
        # `[explode 2d6]` collapses 2d6 to its sum H (range 2..12) first, then
        # explodes when the *sum* hits 12. Total = 6^6 = 46656. Outcomes 12,
        # 13, 24, 25 are missing (those would require 12 to terminate without
        # further explode within depth).
        assert run("output [explode 2d6]") == [
            (
                "output 1",
                H(
                    {
                        2: 1296,
                        3: 2592,
                        4: 3888,
                        5: 5184,
                        6: 6480,
                        7: 7776,
                        8: 6480,
                        9: 5184,
                        10: 3888,
                        11: 2592,
                        14: 36,
                        15: 72,
                        16: 108,
                        17: 144,
                        18: 180,
                        19: 216,
                        20: 180,
                        21: 144,
                        22: 108,
                        23: 72,
                        26: 1,
                        27: 2,
                        28: 3,
                        29: 4,
                        30: 5,
                        31: 6,
                        32: 5,
                        33: 4,
                        34: 3,
                        35: 2,
                        36: 1,
                    }
                ),
            )
        ]

    def test_explode_weighted_die(self) -> None:
        # d{1, 2, 3:5} -> outcomes (1, 1), (2, 1), (3, 5). Max = 3.
        # 7 weight-units total: 1 each for 1 and 2, 5 for 3 (which explodes).
        assert run("output [explode d{1, 2, 3:5}]") == [
            (
                "output 1",
                H({1: 49, 2: 49, 4: 35, 5: 35, 7: 25, 8: 25, 9: 125}),
            )
        ]

    def test_explode_independent_of_max_function_depth(self) -> None:
        # Verified via 42b05: setting maximum function depth low does NOT
        # restrict explode's depth budget.
        assert (
            run(
                'set "maximum function depth" to 1\n'
                'set "explode depth" to 5\n'
                "output [explode d6]"
            )[0][0]
            == "output 1"
        )


# ---- Builtin: [lowest of A and B] -------------------------------------------------------


class TestBuiltinLowestOfAnd:
    # Mirror of TestBuiltinHighestOfAnd. AnyDice symmetry: replacing `highest`
    # with `lowest` flips max -> min throughout.

    def test_num_num(self) -> None:
        assert run("output [lowest of 3 and 5]") == [("output 1", H({3: 1}))]

    def test_num_num_swapped(self) -> None:
        assert run("output [lowest of 5 and 3]") == [("output 1", H({3: 1}))]

    def test_num_num_tie(self) -> None:
        assert run("output [lowest of 5 and 5]") == [("output 1", H({5: 1}))]

    def test_num_num_negative(self) -> None:
        assert run("output [lowest of -3 and -5]") == [("output 1", H({-5: 1}))]

    def test_die_num(self) -> None:
        # min(1,3)=1, min(2,3)=2, min(3-6, 3) = 3
        assert run("output [lowest of d6 and 3]") == [
            ("output 1", H({1: 1, 2: 1, 3: 4}))
        ]

    def test_num_die(self) -> None:
        assert run("output [lowest of 3 and d6]") == [
            ("output 1", H({1: 1, 2: 1, 3: 4}))
        ]

    def test_die_die(self) -> None:
        # min of two d6: count of (a,b) with min=k is 2*(7-k)-1 = 13-2k for k=1..6.
        assert run("output [lowest of d6 and d6]") == [
            ("output 1", H({1: 11, 2: 9, 3: 7, 4: 5, 5: 3, 6: 1}))
        ]

    def test_seq_num(self) -> None:
        # n-typed: {1,2}=3, min(3,5)=3
        assert run("output [lowest of {1,2} and 5]") == [("output 1", H({3: 1}))]

    def test_empty_die_propagates(self) -> None:
        assert run("output [lowest of d{} and 3]") == [("output 1", H({}))]


# ---- Builtin: [lowest N of P] -----------------------------------------------------------


class TestBuiltinLowestNOf:
    # Mirror of TestBuiltinHighestNOf. Selects the N lowest positions of the
    # pool and sums them.

    def test_lowest_1_of_1d6(self) -> None:
        assert run("output [lowest 1 of 1d6]") == [
            ("output 1", H({1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1}))
        ]

    def test_lowest_1_of_2d6(self) -> None:
        # Equivalent to min of 2d6.
        assert run("output [lowest 1 of 2d6]") == [
            ("output 1", H({1: 11, 2: 9, 3: 7, 4: 5, 5: 3, 6: 1}))
        ]

    def test_lowest_2_of_2d6(self) -> None:
        # Equivalent to sum of 2d6.
        assert run("output [lowest 2 of 2d6]") == [
            (
                "output 1",
                H(
                    {
                        2: 1,
                        3: 2,
                        4: 3,
                        5: 4,
                        6: 5,
                        7: 6,
                        8: 5,
                        9: 4,
                        10: 3,
                        11: 2,
                        12: 1,
                    }
                ),
            )
        ]

    def test_lowest_3_of_4d6_drop_highest(self) -> None:
        # 4d6 drop highest -- the inverted D&D distribution.
        assert run("output [lowest 3 of 4d6]") == [
            (
                "output 1",
                H(
                    {
                        3: 21,
                        4: 54,
                        5: 94,
                        6: 131,
                        7: 160,
                        8: 172,
                        9: 167,
                        10: 148,
                        11: 122,
                        12: 91,
                        13: 62,
                        14: 38,
                        15: 21,
                        16: 10,
                        17: 4,
                        18: 1,
                    }
                ),
            )
        ]

    def test_lowest_0_of_pool(self) -> None:
        # Mirror of [highest 0 of 4d6].
        assert run("output [lowest 0 of 4d6]") == [("output 1", H({0: 1}))]

    def test_lowest_n_exceeds_pool_size(self) -> None:
        # Selectors past pool size silently drop; result equals full sum.
        expected = P(6, 6, 6, 6).h()
        assert run("output [lowest 5 of 4d6]") == [("output 1", expected)]

    def test_lowest_n_of_empty_pool(self) -> None:
        assert run("output [lowest 3 of 0d6]") == [("output 1", H({0: 1}))]

    def test_lowest_negative_n(self) -> None:
        assert run("output [lowest -1 of 4d6]") == [("output 1", H({0: 1}))]

    def test_lowest_n_of_pool_collapsed_via_arith(self) -> None:
        # Mirror of highest's pool-collapse-via-arith. (4d6 + 4d6) collapses to
        # 8d6 sum H first; lowest 3 of (1-element pool) returns the sum die.
        expected = P(6, 6, 6, 6, 6, 6, 6, 6).h()
        assert run("output [lowest 3 of (4d6 + 4d6)]") == [("output 1", expected)]


# ---- Builtin: [maximum of <die>] -------------------------------------------------------


class TestBuiltinMaximumOf:
    # Verified against AnyDice (program 42b18). `[maximum of <die>]` returns the
    # maximum POSSIBLE outcome of the die. For pools, the max of the SUM
    # distribution. Empty die returns 0 (NOT H({})).

    def test_maximum_of_d6(self) -> None:
        assert run("output [maximum of d6]") == [("output 1", H({6: 1}))]

    def test_maximum_of_custom_die(self) -> None:
        assert run("output [maximum of d{1, 2, 5}]") == [("output 1", H({5: 1}))]

    def test_maximum_of_weighted_die(self) -> None:
        assert run("output [maximum of d{1:5, 10:2, 100:3}]") == [
            ("output 1", H({100: 1}))
        ]

    def test_maximum_of_pool(self) -> None:
        # Max of 2d6's sum = 12.
        assert run("output [maximum of 2d6]") == [("output 1", H({12: 1}))]

    def test_maximum_of_4d6(self) -> None:
        assert run("output [maximum of 4d6]") == [("output 1", H({24: 1}))]

    def test_maximum_of_empty_die(self) -> None:
        # Empty die -> 0, not H({}).
        assert run("output [maximum of d{}]") == [("output 1", H({0: 1}))]

    def test_maximum_of_die_with_negatives(self) -> None:
        assert run("output [maximum of d{-3, -1, 2}]") == [("output 1", H({2: 1}))]


# ---- Builtin: [reverse SEQ] ------------------------------------------------------------


class TestBuiltinReverse:
    # Verified against AnyDice (program 42b19). `[reverse SEQ]` reverses the
    # sequence in source order (NOT affected by position-order setting -- unlike
    # `[sort]`). Empty input returns 0, NOT the empty seq.

    def test_reverse_position_one_default(self) -> None:
        # Reversed (1,2,3) is (3,2,1); position 1 (source order) = 3.
        assert run("output 1 @ [reverse {1, 2, 3}]") == [("output 1", H({3: 1}))]

    def test_reverse_position_three_default(self) -> None:
        assert run("output 3 @ [reverse {1, 2, 3}]") == [("output 1", H({1: 1}))]

    def test_reverse_independent_of_position_order(self) -> None:
        # Position-order setting does NOT affect reverse (unlike sort).
        assert run(
            'set "position order" to "lowest first"\noutput 1 @ [reverse {1, 2, 3}]'
        ) == [("output 1", H({3: 1}))]

    def test_reverse_preserves_duplicates(self) -> None:
        # (2, 2, 1, 1) reversed = (1, 1, 2, 2); position 4 = 2.
        assert run("output 4 @ [reverse {2, 2, 1, 1}]") == [("output 1", H({2: 1}))]

    def test_reverse_empty_returns_zero(self) -> None:
        # AnyDice quirk: `[reverse {}]` -> 0, NOT the empty seq.
        # (`[sort {}]` returns H({}); they differ on empty input.)
        assert run("output [reverse {}]") == [("output 1", H({0: 1}))]

    def test_reverse_singleton(self) -> None:
        assert run("output [reverse {7}]") == [("output 1", H({7: 1}))]

    def test_reverse_pool_yields_sum(self) -> None:
        # `:s` expansion + per-iteration sum-coerce makes [reverse <pool>]
        # observationally identical to <pool> sum.
        assert run("output [reverse 2d6]") == [
            (
                "output 1",
                H(
                    {
                        2: 1,
                        3: 2,
                        4: 3,
                        5: 4,
                        6: 5,
                        7: 6,
                        8: 5,
                        9: 4,
                        10: 3,
                        11: 2,
                        12: 1,
                    }
                ),
            )
        ]

    def test_reverse_die_yields_die(self) -> None:
        assert run("output [reverse d6]") == [
            ("output 1", H({1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1}))
        ]


# ---- Builtin: [absolute N] -------------------------------------------------------------


class TestBuiltinAbsolute:
    # Verified against AnyDice (program 42b1a). `[absolute N]` with `:n` typing:
    # ints abs; seqs sum-coerce then abs; dies expand per-outcome; empty die
    # propagates as H({}); pools sum-coerce first.

    def test_absolute_positive(self) -> None:
        assert run("output [absolute 5]") == [("output 1", H({5: 1}))]

    def test_absolute_negative(self) -> None:
        assert run("output [absolute -5]") == [("output 1", H({5: 1}))]

    def test_absolute_zero(self) -> None:
        assert run("output [absolute 0]") == [("output 1", H({0: 1}))]

    def test_absolute_seq_mixed(self) -> None:
        # sum({-3, 1, -2}) = -4; abs = 4.
        assert run("output [absolute {-3, 1, -2}]") == [("output 1", H({4: 1}))]

    def test_absolute_seq_positive(self) -> None:
        assert run("output [absolute {1, 2, 3}]") == [("output 1", H({6: 1}))]

    def test_absolute_empty_seq(self) -> None:
        # sum({}) = 0; abs = 0.
        assert run("output [absolute {}]") == [("output 1", H({0: 1}))]

    def test_absolute_die_with_negatives(self) -> None:
        # Per-outcome: abs(-3)=3, abs(-1)=1, abs(2)=2.
        assert run("output [absolute d{-3, -1, 2}]") == [
            ("output 1", H({1: 1, 2: 1, 3: 1}))
        ]

    def test_absolute_die_mixed_signs(self) -> None:
        assert run("output [absolute 1d{-2, 5}]") == [("output 1", H({2: 1, 5: 1}))]

    def test_absolute_empty_die(self) -> None:
        # `:n` empty die propagates as H({}).
        assert run("output [absolute d{}]") == [("output 1", H({}))]

    def test_absolute_pool(self) -> None:
        # 2d{-3, 1}: sum H = {-6:1, -2:2, 2:1}. Abs: {2:3, 6:1}.
        assert run("output [absolute 2d{-3, 1}]") == [("output 1", H({2: 3, 6: 1}))]


# ---- Builtin: [SEQ contains VAL] -------------------------------------------------------


class TestBuiltinContains:
    # Verified against AnyDice (program 42b1b). `[SEQ contains VAL]` is per-
    # element membership: returns 1 if any element of SEQ equals VAL, else 0.
    # `:s, :n` typing means SEQ expands per-roll for pools and per-outcome for
    # dies. Notably, `[2d6 contains 7]` = 0 because 7 never appears as a roll
    # *element* (it's a sum). This is membership, not "could the pool ever
    # produce VAL".

    def test_contains_present(self) -> None:
        assert run("output [{1, 2, 3} contains 2]") == [("output 1", H({1: 1}))]

    def test_contains_absent(self) -> None:
        assert run("output [{1, 2, 3} contains 4]") == [("output 1", H({0: 1}))]

    def test_contains_with_duplicates_returns_boolean(self) -> None:
        # `[contains]` is a boolean: returns 0/1, not the count of matches.
        assert run("output [{1, 2, 2, 3} contains 2]") == [("output 1", H({1: 1}))]

    def test_contains_empty(self) -> None:
        assert run("output [{} contains 2]") == [("output 1", H({0: 1}))]

    def test_contains_singleton_self(self) -> None:
        assert run("output [{2} contains 2]") == [("output 1", H({1: 1}))]

    def test_contains_die_as_val(self) -> None:
        # VAL is `:n`; d6 expands per-outcome. 3 of 6 outcomes are in {1,2,3}.
        assert run("output [{1, 2, 3} contains d6]") == [("output 1", H({0: 1, 1: 1}))]

    def test_contains_pool_as_seq(self) -> None:
        # `:s` expansion of 2d6 -> per-roll tuples; 7 never appears as a roll
        # element (it's a sum). Result H({0: 1}).
        assert run("output [2d6 contains 7]") == [("output 1", H({0: 1}))]

    def test_contains_die_as_seq(self) -> None:
        # d6 -> 1-element seq per outcome; (f,) contains 3 iff f == 3.
        assert run("output [d6 contains 3]") == [("output 1", H({0: 5, 1: 1}))]


# ---- Builtin: [middle N of P] ----------------------------------------------------------


class TestBuiltinMiddleNOf:
    # Verified against AnyDice (program 42b1c). `[middle N of P]` selects the
    # middle N positions of the pool (drop (total-N)/2 from each end, integer
    # division rounding down) and sums them.

    def test_middle_1_of_3d6_is_median(self) -> None:
        assert run("output [middle 1 of 3d6]") == [
            ("output 1", H({1: 28, 2: 70, 3: 91, 4: 91, 5: 70, 6: 28}))
        ]

    def test_middle_1_of_5d6_is_median(self) -> None:
        assert run("output [middle 1 of 5d6]") == [
            ("output 1", H({1: 23, 2: 113, 3: 188, 4: 188, 5: 113, 6: 23}))
        ]

    def test_middle_2_of_4d6(self) -> None:
        # Drop 1 from each end (positions 0 and 3); sum positions 1 and 2.
        assert run("output [middle 2 of 4d6]") == [
            (
                "output 1",
                H(
                    {
                        2: 7,
                        3: 18,
                        4: 37,
                        5: 52,
                        6: 67,
                        7: 70,
                        8: 67,
                        9: 52,
                        10: 37,
                        11: 18,
                        12: 7,
                    }
                ),
            )
        ]

    def test_middle_1_of_4d6_left_leaning(self) -> None:
        # Even pool, odd middle: drop = (4-1)/2 = 1 (integer division), so
        # the lone middle position is index 1 (lowest-first), the 2nd-lowest die.
        assert run("output [middle 1 of 4d6]") == [
            ("output 1", H({1: 7, 2: 41, 3: 87, 4: 121, 5: 119, 6: 57}))
        ]

    def test_middle_n_equals_pool_size(self) -> None:
        # N == total -> full sum.
        from dyce import P

        assert run("output [middle 4 of 4d6]") == [("output 1", P(6, 6, 6, 6).h())]

    def test_middle_n_exceeds_pool_size(self) -> None:
        # N > total: AnyDice clamps to total, returning the full sum.
        from dyce import P

        assert run("output [middle 5 of 4d6]") == [("output 1", P(6, 6, 6, 6).h())]

    def test_middle_zero(self) -> None:
        assert run("output [middle 0 of 4d6]") == [("output 1", H({0: 1}))]

    def test_middle_negative(self) -> None:
        assert run("output [middle -1 of 4d6]") == [("output 1", H({0: 1}))]

    def test_middle_of_zero_die_pool(self) -> None:
        # 0d6 evaluates to H({0:1}); middle 1 of a 1-element pool is the element.
        assert run("output [middle 1 of 0d6]") == [("output 1", H({0: 1}))]

    def test_middle_1_of_1d6(self) -> None:
        assert run("output [middle 1 of 1d6]") == [
            ("output 1", H({1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1}))
        ]

    def test_middle_1_of_empty_die(self) -> None:
        assert run("output [middle 1 of d{}]") == [("output 1", H({}))]

    def test_middle_independent_of_position_order(self) -> None:
        # Position-order setting has no effect on [middle].
        assert run(
            'set "position order" to "lowest first"\noutput [middle 1 of 5d6]'
        ) == [("output 1", H({1: 23, 2: 113, 3: 188, 4: 188, 5: 113, 6: 23}))]
