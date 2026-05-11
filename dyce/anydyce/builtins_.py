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

r"""AnyDice built-in functions.

Each function takes and returns AnyDice runtime values.
Type coercion is handled by the interpreter before dispatch.
"""

from collections.abc import Callable
from typing import Any

from dyce import H, P

__all__ = ("BUILTINS",)

AnyVal = int | H | P | tuple[int, ...]

# ---- Helpers ---------------------------------------------------------------------------


def _to_int(v: AnyVal) -> int:
    r"""Coerce a value to int: sequences sum to int, H and P are not supported."""
    if isinstance(v, int):
        return v
    elif isinstance(v, tuple):
        return sum(v)
    else:
        raise TypeError(f"expected number, got {type(v).__name__}")


def _to_seq(v: AnyVal) -> tuple[int, ...]:
    r"""Coerce to sequence, highest-first."""
    if isinstance(v, int):
        return (v,)
    elif isinstance(v, tuple):
        return v
    elif isinstance(v, H):
        # TODO(posita): # noqa: TD003 - Should we export dyce.h.aggregate_weighted for
        # this?
        # Expand weighted outcomes (duplicates for weight > 1), sort highest first.
        items: list[int] = []
        for outcome, count in v.items():
            items.extend([outcome] * count)
        return tuple(sorted(items, reverse=True))
    elif isinstance(v, P):
        raise TypeError("cannot coerce pool to sequence directly -- use :s parameter")
    else:
        raise TypeError(f"cannot coerce {type(v).__name__} to sequence")


def _h_from_pool(p: P) -> H:
    r"""Collapse a pool to a die representing the sum distribution."""
    return H({0: 1}) if len(p) == 0 else p.h(slice(0, None))


# ---- Built-ins -------------------------------------------------------------------------


def _absolute(x: int) -> int:
    return abs(x)


def _contains(seq: tuple[int, ...], val: int) -> int:
    return int(val in seq)


def _count_in(values: tuple[int, ...], seq: tuple[int, ...]) -> int:
    # AnyDice counts VALS as a MULTISET: each element of seq contributes
    # `values.count(elem)` to the total, not just 1-or-0 set-membership.
    # Verified via `[count {6, 6} in {6}]` = 2.
    return sum(values.count(v) for v in seq)


def _maximum_of(die: H | P) -> int:
    # AnyDice (42b18): `[maximum of <pool>]` returns the max of the sum H.
    # Empty die returns 0 (NOT H({}) -- AnyDice does not propagate emptiness
    # through `[maximum of]`).
    if isinstance(die, P):
        die = _h_from_pool(die)
    return max(die.outcomes(), default=0)


def _sort_highest(seq: tuple[int, ...]) -> tuple[int, ...]:
    return tuple(sorted(seq, reverse=True))


def _sort_lowest(seq: tuple[int, ...]) -> tuple[int, ...]:
    return tuple(sorted(seq))


def _highest_of_and(a: int, b: int) -> int:
    return max(a, b)


def _lowest_of_and(a: int, b: int) -> int:
    return min(a, b)


def _highest_n_of(n: int, pool: P) -> H:
    # sum of n highest dice from pool
    selectors = tuple(slice(-(i), -(i - 1) if i > 1 else None) for i in range(1, n + 1))
    return pool.h(*selectors) if selectors else H({0: 1})


def _lowest_n_of(n: int, pool: P) -> H:
    # sum of n lowest dice from pool
    selectors = tuple(slice(i, i + 1) for i in range(n))
    return pool.h(*selectors) if selectors else H({0: 1})


def _middle_n_of(n: int, pool: P) -> H:
    # Sum of middle n dice. Per AnyDice (42b1c):
    #   - n <= 0     -> H({0: 1}) (NOT H({})).
    #   - n >= total -> clamp to total (return the full pool sum).
    #   - drop is asymmetric when (total - n) is odd: drop one MORE from the
    #     low end than from the high end (so middle leans toward higher
    #     positions). Hence `(total - n + 1) // 2` rather than `(total - n) // 2`.
    total = len(pool)
    if n <= 0:
        return H({0: 1})
    if n >= total:
        return pool.h() if total > 0 else H({0: 1})
    drop = (total - n + 1) // 2
    selectors = tuple(slice(drop + i, drop + i + 1) for i in range(n))
    return pool.h(*selectors)


def _explode(die: H | P, depth: int) -> H:
    r"""Explode a die: when the max face is rolled, add that value and roll again, up to `depth` extra times."""
    if isinstance(die, P):
        die = _h_from_pool(die)
    if not die or depth <= 0:
        return die
    max_val = max(die.outcomes())
    inner = _explode(die, depth - 1)
    inner_total = sum(inner.values())
    expanded: dict[int, int] = {}
    for outcome, weight in die.items():
        if outcome == max_val:
            for inner_outcome, inner_weight in inner.items():
                combined = outcome + inner_outcome
                expanded[combined] = expanded.get(combined, 0) + weight * inner_weight
        else:
            # Scale non-explosion outcomes to match the inner distribution's total weight
            # so that all outcomes share a common denominator.
            expanded[outcome] = expanded.get(outcome, 0) + weight * inner_total
    return H(expanded)


# ---- Registry --------------------------------------------------------------------------

BUILTINS: list[tuple[list[str | None], list[str | None], Callable[..., Any]]] = [
    # pattern               param_types          impl
    #
    # Entries below are written but not yet wired -- we are enabling builtin families
    # one at a time, with dedicated tests per family before lighting them up.
    # Uncomment as each family passes its tests.
    #
    (["absolute", None], ["n"], lambda _s, x: _absolute(x)),
    ([None, "contains", None], ["s", "n"], lambda _s, seq, val: _contains(seq, val)),
    (
        ["count", None, "in", None],
        ["s", "s"],
        lambda _s, vals, seq: _count_in(vals, seq),
    ),
    (["maximum", "of", None], ["d"], lambda _s, die: _maximum_of(die)),
    # AnyDice quirk (42b19): `[reverse {}]` returns 0, not the empty seq.
    # (Compare `[sort {}]` which returns H({}).)
    (["reverse", None], ["s"], lambda _s, seq: seq[::-1] if seq else 0),
    # AnyDice's [sort] returns a seq whose source-order position 1 is the
    # "most prominent" element under the current position-order setting:
    # under highest-first (default), position 1 is the HIGHEST element so the
    # seq is sorted DESC; under lowest-first, position 1 is the LOWEST so the
    # seq is sorted ASC. Verified via probes (42afc).
    (
        ["sort", None],
        ["s"],
        lambda s, seq: _sort_highest(seq) if s.highest_first() else _sort_lowest(seq),
    ),
    (
        ["highest", "of", None, "and", None],
        ["n", "n"],
        lambda _s, a, b: _highest_of_and(a, b),
    ),
    (
        ["lowest", "of", None, "and", None],
        ["n", "n"],
        lambda _s, a, b: _lowest_of_and(a, b),
    ),
    (
        ["highest", None, "of", None],
        ["n", "d"],
        lambda _s, n, pool: _highest_n_of(n, pool if isinstance(pool, P) else P(pool)),
    ),
    (
        ["lowest", None, "of", None],
        ["n", "d"],
        lambda _s, n, pool: _lowest_n_of(n, pool if isinstance(pool, P) else P(pool)),
    ),
    # `[highest N of A and B]` / `[lowest N of A and B]` -- undocumented but
    # present in AnyDice. Combines the two `:d` args (any pool/die/scalar
    # mix) into a heterogeneous pool and selects the N highest/lowest. P()
    # flattens nested pools so `P(2d6, 1d4)` correctly produces a 3-die
    # pool.
    (
        ["highest", None, "of", None, "and", None],
        ["n", "d", "d"],
        lambda _s, n, a, b: _highest_n_of(n, P(a, b)),
    ),
    (
        ["lowest", None, "of", None, "and", None],
        ["n", "d", "d"],
        lambda _s, n, a, b: _lowest_n_of(n, P(a, b)),
    ),
    # Three-die variants. AnyDice has these but NO four-or-more form, so we
    # stop here.
    (
        ["highest", None, "of", None, "and", None, "and", None],
        ["n", "d", "d", "d"],
        lambda _s, n, a, b, c: _highest_n_of(n, P(a, b, c)),
    ),
    (
        ["lowest", None, "of", None, "and", None, "and", None],
        ["n", "d", "d", "d"],
        lambda _s, n, a, b, c: _lowest_n_of(n, P(a, b, c)),
    ),
    # Empty H wrapped as a 1-pool would otherwise sum to H({0:1}) via dyce's
    # P.h(); AnyDice instead propagates H({}) for `[middle N of d{}]`.
    # Detect the empty H input here before wrapping.
    (
        ["middle", None, "of", None],
        ["n", "d"],
        lambda _s, n, pool: (
            H({})
            if isinstance(pool, H) and not pool
            else _middle_n_of(n, pool if isinstance(pool, P) else P(pool))
        ),
    ),
    (["explode", None], ["d"], lambda s, die: _explode(die, s.explode_depth)),
]
