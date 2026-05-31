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

r"""AnyDice tree-walking interpreter backed by dyce primitives."""

import operator
import sys
import warnings
from collections import Counter
from collections.abc import Callable, Iterator

from dyce import H, P, RollT, TruncationWarning
from dyce.h import aggregate_weighted

from .ast_ import (
    BinOp,
    Call,
    DiceBinOp,
    DiceUnary,
    EmptySeq,
    Expr,
    FunctionDef,
    HashOp,
    IfStmt,
    LoopStmt,
    NegOp,
    NotOp,
    Number,
    OutputStmt,
    Param,
    PosOp,
    Program,
    RangeElem,
    RangeRepeatElem,
    ResultStmt,
    SeqElem,
    SeqExpr,
    SetStmt,
    Stmt,
    StringExpr,
    StrLit,
    StrVar,
    ValueElem,
    ValueRepeatElem,
    Var,
    VarAssign,
)
from .builtins_ import BUILTINS
from .settings import Settings

try:
    import warnings

    from dyce.d import (  # type: ignore[attr-defined]
        dempty,  # pyrefly: ignore[missing-module-attribute] # pyright: ignore[reportAttributeAccessIssue] # ty: ignore[unresolved-import]
        dzero,  # pyrefly: ignore[missing-module-attribute] # pyright: ignore[reportAttributeAccessIssue] # ty: ignore[unresolved-import]
    )

    warnings.warn("dyce is sane now, remove this guard", stacklevel=0)
except ImportError:
    from dyce.d import d0 as dempty

    dzero = H({0: 1})

__all__ = ("AnyDiceInterpreter",)

NumT = int
SeqT = RollT[NumT]
DieT = P[NumT]
AnyDiceResultT = tuple[str, H[NumT]]
AnyDiceResultsT = list[AnyDiceResultT]
# AnyDice's surface "die" type maps to two cooperating internal types. The split exists
# because positional information is meaningful for some operations and meaningless for
# others. P (DieT) is a multi-die pool that retains per-position information, which `@`
# uses to project a single position out of the pool. Once that position is consumed--or
# in any operation where positions don't apply (single dice, arithmetic, comparisons,
# bool ops)--the natural representation is a flat distribution, i.e. H. Wrapping
# everything in P would be ceremony for no gain at the non-pool sites. Insisting that
# everything be H would force us to recompute pool positions at every `@`. So both types
# coexist in _Val, and are used wherever each fits. `P op X` (for X in P/H/int) already
# collapses to H by design. We only convert P -> H by hand at sites that build outcome
# maps directly (see _h_binop, _apply_cmp).
_Val = NumT | H[NumT] | DieT | SeqT | str

# ---- Operator tables ---------------------------------------------------------------------

# `0^negative` is mathematically undefined. AnyDice's behavior splits by
# context: in scalar^scalar form it raises an explicit error; in any
# H-iterated form (one or both operands are dice/pools) it substitutes the
# sentinel value below for every offending per-outcome result, so the
# overall distribution survives. The principle is "errors don't compose
# probabilistically" -- raising on one outcome would kill the entire
# computation. We mirror this split. The sentinel value AnyDice emits is
# `-2**63 = INT64_MIN = -0x8000000000000000` -- the signed-int overflow of
# the float-to-int conversion of `-INF`. Verified: every sentinel-bearing
# output in the captured corpus uses this exact value.
_POW_NEG_INF_SENTINEL = -9223372036854775808


class _EmptyPoolOfOne(P[NumT]):
    r"""
    Nope, that’s not a contradiction.
    But nor is it some kind of deep existential thought exercise.

    Yup, it’s a hack.

    This is ***solely*** to represent a pool of length one containing the empty die, which `dyce` itself takes a principled stance against.
    (`dyce` refuses to include the empty die in pools because its presence would either have to be ignored or any convolution would collapse the entire pool into the empty die.)
    But AnyDice treats `#d{}` (the “number” of one empty die) and `#(d{}d{})` (the “number” of a pool of one empty die) as different.
    The former is zero.
    The latter is one.
    You do the math.

    Oh wait.
    You can’t.
    Your guess is as good as mine as to why this makes sense.
    Given the types of other bugs we’ve discovered, it probably doesn’t.
    It’s probably yet another artifact of hacking the thing together without really understanding what’s going on.
    """

    def __init__(self) -> None:
        super().__init__()
        self._hs = (H({}),)


def _anydice_pow_strict(a: int, b: int) -> int:
    # AnyDice truncates fractional power results toward zero so `^` always
    # produces integer outcomes (e.g. `2^-1 = 0`, `(-2)^-1 = 0`, `(-1)^-1 =
    # -1`). Python's `**` returns a float for negative integer exponents;
    # wrapping in `int()` recovers truncation-toward-zero for all cases.
    if a == 0 and b < 0:
        raise ZeroDivisionError(
            f"cannot raise 0 to negative exponent ({b}); result is undefined"
        )
    return int(a**b)


def _anydice_pow_lenient(a: int, b: int) -> int:
    # Same truncation as the strict variant, but `0^negative` returns the
    # AnyDice sentinel instead of raising. Used in the H-iteration loop of
    # `_h_binop` so a single undefined per-outcome computation doesn't kill
    # the surrounding distribution.
    if a == 0 and b < 0:
        return _POW_NEG_INF_SENTINEL
    return int(a**b)


_OP_FUNCS: dict[str, Callable[[int, int], int]] = {
    "+": operator.add,
    "-": operator.sub,
    "*": operator.mul,
    # AnyDice truncates toward zero (matches int(a/b)) and substitutes 0 for division
    # by zero rather than raising; the substitution applies per-outcome inside H/H or
    # H/int dispatch via the cross-product in `_h_binop`.
    "/": lambda a, b: 0 if b == 0 else int(a / b),
    "^": _anydice_pow_strict,
    "=": lambda a, b: int(a == b),
    "!=": lambda a, b: int(a != b),
    "<": lambda a, b: int(a < b),
    ">": lambda a, b: int(a > b),
    "<=": lambda a, b: int(a <= b),
    ">=": lambda a, b: int(a >= b),
    "&": lambda a, b: int(bool(a) and bool(b)),
    "|": lambda a, b: int(bool(a) or bool(b)),
}

# Per-outcome dispatch for H-iteration. Identical to `_OP_FUNCS` except `^`
# uses the lenient variant (sentinel substitution instead of raising). Other
# ops behave the same in scalar vs probabilistic contexts.
_OP_FUNCS_H_ITER: dict[str, Callable[[int, int], int]] = {
    **_OP_FUNCS,
    "^": _anydice_pow_lenient,
}

# Raw comparison ops for use on heterogeneous Python operands (e.g., tuples in lex
# comparison). _OP_FUNCS is typed for ints. These are typed permissively to accommodate
# operator.lt et al., whose stubs require _SupportsDunderLT etc.
_CMP_RAW: dict[str, Callable[..., bool]] = {
    "=": operator.eq,
    "!=": operator.ne,
    "<": operator.lt,
    ">": operator.gt,
    "<=": operator.le,
    ">=": operator.ge,
}

_ARITH_OPS = {"+", "-", "*", "/", "^", "&", "|"}
_CMP_OPS = {"=", "!=", "<", ">", "<=", ">="}

# +/- treat empty die as scalar 0; */^ propagate emptiness as H({})
_EMPTY_DIE_SKIPS_ARITH = {"+", "-", "|"}

# ---- Function pattern shape --------------------------------------------------------------

# A pattern shape is a tuple slotting words at fixed positions and `None` for each
# parameter slot. It is the user-visible function "name" in AnyDice: two definitions
# with the same shape are the same callable, regardless of parameter types.


def _call_shape(parts: list[str | Expr]) -> tuple[str | None, ...]:
    return tuple(p if isinstance(p, str) else None for p in parts)


def _pattern_shape(pattern: list[str | Param]) -> tuple[str | None, ...]:
    return tuple(p if isinstance(p, str) else None for p in pattern)


class _ResultReturn(Exception):  # noqa: N818
    r"""Internal control-flow signal: a `result:` statement fired in a function body.

    Carries the result value so the function-call machinery can return it.
    Using an exception lets `result:` fire from arbitrary nesting depth (inside
    `if` / `loop` bodies) rather than only at the top of a function body.
    """

    def __init__(self, value: _Val) -> None:
        super().__init__()
        self.value = value


# ---- Interpreter -------------------------------------------------------------------------


class AnyDiceInterpreter:
    def __init__(self) -> None:
        self._settings = Settings()
        self._env: dict[str, _Val] = {}
        self._outputs: AnyDiceResultsT = []
        # Functions are keyed by their pattern *shape* -- a tuple slotting fixed words
        # at fixed positions and `None` for each parameter slot regardless of type
        # annotation. AnyDice's user-visible "function name" is exactly this shape (e.g.
        # `function: add X:n to Y:d` and `function: add X:s to Y:n` are the same
        # callable. The latter REPLACES the former on registration). Param type
        # annotations are body-evaluation hints, not dispatch keys.
        self._funcs: dict[tuple[str | None, ...], FunctionDef] = {}
        # Built-in dispatch table mirrors _funcs but maps to (param_types, impl). User
        # functions take precedence: _call consults _funcs first and falls back here.
        self._builtins: dict[
            tuple[str | None, ...], tuple[list[str | None], Callable[..., _Val]]
        ] = {}
        for pattern, param_types, impl in BUILTINS:
            shape = tuple(p if isinstance(p, str) else None for p in pattern)
            self._builtins[shape] = (list(param_types), impl)
        self._depth = 0

    def run(self, program: Program) -> AnyDiceResultsT:
        r"""Execute a parsed program and return `(name, distribution)` pairs."""
        self._env = {}
        self._outputs = []
        self._funcs = {}
        self._depth = 0
        # Bump Python's recursion limit for the duration of this run. Both
        # `dyce.p`'s pool-selection (recurses ~4 Python frames per distinct
        # outcome of the underlying H, via `lowest_terms` / `__hash__` in
        # the inner loop) and our own interpreter call chain (~7 Python
        # frames per AnyDice call) can hit the default ~1000 limit on
        # otherwise reasonable programs. Empirically 5000 covers
        # pool-selection on dies up to ~d1250 and user-function recursion
        # up to ~`set "maximum function depth" to 700`, while staying well
        # below the C-stack overflow risk zone (a Python frame is a few
        # hundred bytes, default Linux thread stack is 8MB).
        prev_limit = sys.getrecursionlimit()
        if prev_limit < 5000:
            sys.setrecursionlimit(5000)
        try:
            for stmt in program.stmts:
                self._exec(stmt)
            return list(self._outputs)
        finally:
            if prev_limit < 5000:
                sys.setrecursionlimit(prev_limit)

    # ---- Statement execution -------------------------------------------------------------

    def _exec(self, stmt: Stmt) -> None:
        if isinstance(stmt, OutputStmt):
            value = self._eval(stmt.expr)
            h = self._coerce_to_h(value)
            label = self._eval_name(stmt.name)
            if label is None:
                label = f"output {len(self._outputs) + 1}"
            self._outputs.append((label, h))
        elif isinstance(stmt, SetStmt):
            v = self._eval(stmt.value)
            if isinstance(v, (str, int)):
                self._settings.set(stmt.key, v)
            else:  # pragma: no cover
                raise TypeError(
                    f"set value must resolve to string or number, got {type(v).__name__}"
                )
        elif isinstance(stmt, FunctionDef):
            # Redefinition with the same shape replaces. Param types do not affect
            # identity.
            self._funcs[_pattern_shape(stmt.pattern)] = stmt
        elif isinstance(stmt, VarAssign):
            self._env[stmt.name] = self._eval(stmt.expr)
        elif isinstance(stmt, IfStmt):
            self._exec_if(stmt)
        elif isinstance(stmt, LoopStmt):
            self._exec_loop(stmt)
        elif isinstance(stmt, ResultStmt):
            # `result:` is grammatically restricted to function bodies, but the body can
            # nest the statement inside `if` / `loop` blocks. Raising an exception
            # unwinds through any nesting back to the function-call machinery, which
            # catches it.
            raise _ResultReturn(self._eval(stmt.expr))
        else:  # pragma: no cover
            raise NotImplementedError(f"unhandled statement: {type(stmt).__name__}")

    def _exec_if(self, stmt: IfStmt) -> None:
        for branch in stmt.branches:
            if self._is_truthy(self._eval(branch.condition)):
                for body_stmt in branch.body:
                    self._exec(body_stmt)
                return
        if stmt.else_branch is not None:
            for body_stmt in stmt.else_branch.body:
                self._exec(body_stmt)

    def _exec_loop(self, stmt: LoopStmt) -> None:
        over = self._eval(stmt.over)
        if not isinstance(over, tuple):
            raise TypeError(f"loop over must be a sequence, got {type(over).__name__}")
        # AnyDice does not introduce a child scope for loop bodies. The loop variable is
        # bound in the enclosing environment and any assignments in the body persist
        # after the loop.
        for value in over:
            self._env[stmt.var] = value
            for body_stmt in stmt.body:
                self._exec(body_stmt)

    def _is_truthy(self, v: _Val) -> bool:
        # AnyDice's `if` accepts ONLY numbers. Sequences are NOT sum-coerced in
        # condition position (verified against AnyDice via program 42aac, which
        # errors on `if {} { ... }` with "Boolean values can only be numbers").
        # Dice and strings are also rejected.
        if isinstance(v, int):
            return v != 0
        else:
            raise TypeError(f"cannot use {type(v).__name__} as boolean condition")

    # ---- Expression evaluation -----------------------------------------------------------

    def _eval(self, node: Expr) -> _Val:  # noqa: C901
        if isinstance(node, EmptySeq):
            return ()
        elif isinstance(node, Number):
            return node.value
        elif isinstance(node, SeqExpr):
            return self._eval_seq(node.elems)
        elif isinstance(node, DiceUnary):
            faces = self._eval(node.faces)
            # Unary `d` on an already-die-like value (H or P) is identity.
            # Critical for preserving pool positional info through `dDIE` when
            # DIE = NdX is a pool: collapsing via `_make_die` (which would
            # call `P.h()`) loses the N-die structure that downstream
            # `[highest K of dDIE]`-style builtins need to operate over.
            # Verified necessary by program 178 (`[highest H of dDIE]` where
            # DIE = 4d100; AnyDice's `d` on a pool is a no-op).
            return faces if isinstance(faces, (H, P)) else self._make_die(faces)
        elif isinstance(node, DiceBinOp):
            n = self._eval(node.n)
            if isinstance(n, tuple):
                n = sum(n)
            elif isinstance(n, P):
                n = n.h()
            if isinstance(n, int):
                faces = self._eval(node.faces)
                if n == 1 and isinstance(faces, P):
                    # 1d(<pool>) is treated as a no-op
                    return faces
                return self._roll_n(n, self._make_die(faces))
            elif isinstance(n, H):
                # AnyDice expands a die-as-count over its outcomes: for each
                # outcome k, evaluate `k d <faces>` and combine the per-outcome
                # distributions weighted by k's probability. Inner distributions
                # have different totals (1d6 vs 2d6 vs ...) so we must LCM-
                # normalize before merging or the relative weighting will be
                # wrong.
                return self._expand_dice_count(
                    n, self._make_die(self._eval(node.faces))
                )
            else:
                raise TypeError(f"dice count must be a number, got {type(n).__name__}")
        elif isinstance(node, StringExpr):
            return self._eval_string(node.parts)
        elif isinstance(node, Var):
            if node.name not in self._env:
                raise NameError(f"undefined variable: {node.name!r}")
            return self._env[node.name]
        elif isinstance(node, BinOp):
            left = self._eval(node.left)
            right = self._eval(node.right)
            if node.op == "@":
                return self._apply_at(left, right)
            return self._apply_binop(node.op, left, right)
        elif isinstance(node, HashOp):
            return self._apply_hash(self._eval(node.expr))
        elif isinstance(node, NegOp):
            return self._apply_neg(self._eval(node.expr))
        elif isinstance(node, NotOp):
            return self._apply_not(self._eval(node.expr))
        elif isinstance(node, PosOp):
            return self._eval(node.expr)
        elif isinstance(node, Call):
            return self._call(node)
        else:  # pragma: no cover
            raise NotImplementedError(f"unhandled expression: {type(node).__name__}")

    # ---- Unary operators -----------------------------------------------------------------

    def _apply_neg(self, v: _Val) -> int | H[int] | P[int]:
        if isinstance(v, tuple):
            return -sum(v)
        elif isinstance(v, (int, H)):
            return -v
        elif isinstance(v, P):
            return P(*(-h for h in v))
        else:  # pragma: no cover
            raise TypeError(f"cannot negate {type(v).__name__}")

    def _apply_not(self, v: _Val) -> int | H[int]:
        if isinstance(v, tuple):
            v = sum(v)
        elif isinstance(v, P):
            v = v.h()
        if isinstance(v, int):
            return int(not v)
        elif isinstance(v, H):
            return v.apply(lambda x: int(not x))
        else:  # pragma: no cover
            raise TypeError(f"cannot apply ! to {type(v).__name__}")

    def _apply_hash(self, v: _Val) -> int:
        if isinstance(v, int):
            return len(str(abs(v))) if v != 0 else 1
        elif isinstance(v, tuple):
            return len(v)
        elif isinstance(v, P):
            return len(v)  # this could be _EmptyPoolOfOne
        elif isinstance(v, H):
            # A bare die is a 1-position pool. Empty H -> 0. Verified via 42af3.
            return 1 if v else 0
        else:  # pragma: no cover
            raise TypeError(f"cannot apply # to {type(v).__name__}")

    # ---- Binary operators ----------------------------------------------------------------

    def _apply_binop(self, op: str, left: _Val, right: _Val) -> int | H[int] | P[int]:
        if op in _ARITH_OPS:
            return self._apply_arith(op, left, right)
        elif op in _CMP_OPS:
            return self._apply_cmp(op, left, right)
        else:  # pragma: no cover
            raise NotImplementedError(f"unhandled operator: {op!r}")

    def _apply_arith(self, op: str, left: _Val, right: _Val) -> int | H[int] | P[int]:
        l_empty = isinstance(left, (H, P)) and not left
        r_empty = isinstance(right, (H, P)) and not right
        if l_empty and r_empty:
            return dempty
        # Sequences sum-coerce for boolean ops
        if isinstance(left, tuple):
            left = sum(left)
        if isinstance(right, tuple):
            right = sum(right)
        if op in _EMPTY_DIE_SKIPS_ARITH:
            # AnyDice anomaly: d{} - <thing> propagates <thing> (acts as a no-op). We
            # match AnyDice's actual outputs (except for a bug where AnyDice is
            # internally inconsistent when d{} is the lhs parameter).
            if l_empty:
                if isinstance(right, P):
                    return right
                else:
                    left = 0
                    l_empty = False
            elif r_empty:
                if isinstance(left, P):
                    return left
                else:
                    right = 0
                    r_empty = False
        left = left.h() if isinstance(left, P) else left
        right = right.h() if isinstance(right, P) else right

        return dempty if l_empty or r_empty else self._h_binop(op, left, right)

    def _apply_cmp(self, op: str, left: _Val, right: _Val) -> int | H[int]:  # noqa: C901
        if isinstance(left, P):
            left = left.h()
        if isinstance(right, P):
            right = right.h()
        # Empty die: Comparisons always propagate H({}).
        if (isinstance(left, H) and not left) or (isinstance(right, H) and not right):
            return H({})
        if isinstance(left, tuple) and isinstance(right, tuple):
            # Lex tuple compare (per AnyDice docs, "compared number by number, left to
            # right"). Tuples support Python's native lex comparison directly.
            return int(_CMP_RAW[op](left, right))
        if isinstance(left, tuple):
            if isinstance(right, int):
                # seq vs number: Count elements satisfying op(elem, num).
                return sum(_OP_FUNCS[op](e, right) for e in left)
            elif isinstance(right, H):
                # seq vs die: sum-coerce seq.
                left = sum(left)
            else:  # pragma: no cover
                raise TypeError(f"unexpected right operand type {type(right).__name__}")
        if isinstance(right, tuple):
            if isinstance(left, H):
                # die vs seq: Sum-coerce seq.
                right = sum(right)
            elif isinstance(left, int):
                # number vs seq: Count elements satisfying op(num, elem).
                return sum(_OP_FUNCS[op](left, e) for e in right)
            else:  # pragma: no cover
                raise TypeError(f"unexpected left operand type {type(left).__name__}")
        return self._h_binop(op, left, right)

    def _h_binop(self, op: str, left: _Val, right: _Val) -> int | H[int]:
        if isinstance(left, int) and isinstance(right, int):
            return _OP_FUNCS[op](left, right)
        if not isinstance(left, (int, H)):  # pragma: no cover
            raise TypeError(f"expected a number or die, got {type(left).__name__}")
        if not isinstance(right, (int, H)):  # pragma: no cover
            raise TypeError(f"expected a number or die, got {type(right).__name__}")
        left_h = left if isinstance(left, H) else H({left: 1})
        right_h = right if isinstance(right, H) else H({right: 1})
        result: dict[int, int] = {}
        op_func = _OP_FUNCS_H_ITER[op]
        for lo, lw in left_h.items():
            for ro, rw in right_h.items():
                outcome = op_func(lo, ro)
                result[outcome] = result.get(outcome, 0) + lw * rw
        return H(result)

    # ---- @ operator ----------------------------------------------------------------------

    def _apply_at(self, left: _Val, right: _Val) -> int | H[int]:
        if isinstance(left, (H, P)):
            raise TypeError("@ left operand must be a number or sequence, got die")
        # Right-side empty die propagates emptiness
        if isinstance(right, int):
            return self._at_num(left, right)
        elif isinstance(right, tuple):
            return self._at_seq(left, right)
        elif isinstance(right, P):
            return self._at_pool(left, right)
        elif isinstance(right, H):
            # AnyDice treats a non-empty H as a 1-element pool for `@`. Empty H
            # propagates as H({}); non-empty H wraps as P(H) and reuses the pool
            # path so `1@die` returns the die and `N@die` (N != 1) returns 0.
            if not right:
                return H({})
            return self._at_pool(left, P(right))
        else:  # pragma: no cover
            raise TypeError(
                f"@ right operand has unexpected type {type(right).__name__}"
            )

    def _at_pool(self, left: _Val, pool: DieT) -> H[int]:
        if isinstance(left, int):
            size = len(pool)
            # Left is out of range
            if not 1 <= left <= size:
                return dzero
            # 1-based position. highest-first: pos 1 = highest = pool.h(-1).
            # lowest-first:  pos 1 = lowest  = pool.h(0).
            elif self._settings.highest_first():
                return pool.h(-left)
            else:
                return pool.h(left - 1)
        elif isinstance(left, tuple):
            # Multi-position semantic: each element of the seq is a separate
            # position. The positions come from the SAME pool roll, so they're
            # correlated; dyce's `P.h(*selectors)` sums them jointly. Out-of-
            # range positions are silently dropped (they contribute 0 to the
            # sum). Verified against AnyDice via 42ad5.
            size = len(pool)
            highest_first = self._settings.highest_first()
            selectors: list[int] = []
            for p in left:
                p_int = int(p)
                if 1 <= p_int <= size:
                    selectors.append(-p_int if highest_first else p_int - 1)
            if not selectors:
                return dzero
            return pool.h(*selectors)
        else:
            raise TypeError(
                f"@ left operand must be a number or sequence, got {type(left).__name__}"
            )

    def _at_num(self, left: _Val, num: int) -> int:
        if isinstance(left, int):
            return self._digit_at(left, num)
        elif isinstance(left, tuple):
            # Each element of the seq is a separate position. Results sum.
            return sum(self._digit_at(int(p), num) for p in left)
        else:
            raise TypeError(
                f"@ left operand must be a number or sequence, got {type(left).__name__}"
            )

    def _at_seq(self, left: _Val, seq: SeqT) -> int:
        if isinstance(left, tuple):
            # Multi-position semantic: each element of the seq is a separate
            # position; results are summed (verified against AnyDice via 42ad5).
            return sum(self._at_seq(int(p), seq) for p in left)
        if not isinstance(left, int):
            raise TypeError(
                f"@ left operand must be a number or sequence, got {type(left).__name__}"
            )
        elif left < 1 or left > len(seq):
            return 0
        else:
            # The seq tuple is in position-order order already (highest-first or
            # lowest-first)
            return seq[left - 1]

    def _digit_at(self, pos: int, num: int) -> int:
        if pos < 1:
            return 0
        sign = -1 if num < 0 else 1
        digits = str(abs(num))
        n = len(digits)
        if pos > n:
            return 0
        d = digits[pos - 1] if self._settings.highest_first() else digits[n - pos]
        return sign * int(d)

    # ---- Dice helpers --------------------------------------------------------------------

    def _make_die(self, faces: _Val) -> H[int]:
        if isinstance(faces, int):
            # AnyDice convention: d0 always shows 0.
            return dzero if faces == 0 else H(faces)
        elif isinstance(faces, tuple):
            return H(Counter(faces)) if faces else H({})
        elif isinstance(faces, P):
            return faces.h()
        elif isinstance(faces, H):
            return faces
        else:
            raise TypeError(f"cannot use {type(faces).__name__} as die faces")

    def _roll_n(self, n: int, die: H[int]) -> H[int] | DieT:
        # Strip zero-count entries before constructing a pool. `_truncate`
        # preserves them as keys (so `#{H}` reads the right support), but pool
        # selection arithmetic in dyce.p assumes positive counts and divides
        # by gcd(0, 0) when fed zeros.
        die = H({o: c for o, c in die.items() if c > 0})
        if not die:
            # Empty die regardless of n
            return H({})
        elif n == 0:
            return dzero
        elif n < 0:
            # AnyDice convention: `(-N)dX = -(NdX)` -- roll |N| dice and negate the
            # sum. Verified via 6585 (`1d6 - (-1d6)` yields 2d6's distribution).
            # Returns an H since negation collapses the pool's positional info,
            # which the negative-count case can't preserve anyway.
            return (-n) @ P(-die)
        else:
            # Use a Pool so that @ can select positions. Arithmetic/output sums via .h().
            return n @ P(die)

    def _expand_dice_count(
        self, n_die: H[int], face_die: H[int]
    ) -> H[int] | _EmptyPoolOfOne:
        # For each outcome k of n_die with weight w_k, compute kd<face_die> and combine.
        # Inner distributions can have different totals (e.g. 1d6 has total 6 vs 2d6's
        # 36). aggregate_weighted LCM-normalizes them before merging to preserve the
        # relative probabilities of each outer-outcome branch.
        #
        # Erm, that is, *except* when either n_die or face_die is the empty die. How big
        # is the die with no faces? To answer, we have to leave the world of reality,
        # entering a realm not only of sight and sound, but lacking of mind. That's the
        # signpost up ahead--your next stop, the AnyDice Twilight Clone. (3-5 days to
        # get a basic syntax and interpreter working, and 5-10 times that trying to
        # figure out and possibly reproduce all of the unprincipled idiosyncrasies. But
        # who's counting?)
        if not n_die or not face_die:
            return _EmptyPoolOfOne()

        def _gen() -> Iterator[tuple[H[int], int]]:
            for k, w_k in n_die.items():
                sub = self._roll_n(k, face_die)
                yield (sub.h() if isinstance(sub, P) else sub), w_k

        return self._truncate(aggregate_weighted(_gen()))  # ty: ignore[invalid-argument-type]

    # ---- Coercion ------------------------------------------------------------------------

    def _coerce_to_h(self, value: _Val) -> H[int]:
        if isinstance(value, int):
            return H({value: 1})
        elif isinstance(value, tuple):
            return H(Counter(value)) if value else H({})
        elif isinstance(value, P):
            return value.h()
        elif isinstance(value, H):
            return value
        else:
            raise TypeError(f"cannot coerce {type(value).__name__} to die")

    def _truncate(self, h: H[int]) -> H[int]:
        r"""Zero the count of any outcome whose within-H probability falls
        below `self._settings.precision`, then reduce the survivors to lowest
        terms so subsequent operations don't compound the magnitude.
        Outcomes are preserved as zero-count keys rather than dropped, so
        operators that read H's keys (e.g. `#{H}` taking length of a seq
        constructed from H's outcomes) see the same support AnyDice does
        under its float-floor rounding. Emits a `TruncationWarning` when any
        outcome is zeroed. No-op when precision is 0 or the H is empty."""
        precision = self._settings.precision
        if precision <= 0 or not h:
            return h
        # Compare via cross-multiplication to avoid Fraction allocations per outcome.
        # Zero iff count / total < precision  <==>  count * precision.denominator
        # < total * precision.numerator.
        num = h.total * precision.numerator
        den = precision.denominator
        counts: dict[int, int] = {}
        zeroed = 0
        survived = False
        for outcome, count in h.items():
            if count * den < num:
                counts[outcome] = 0
                zeroed += 1
            else:
                counts[outcome] = count
                survived = True
        if zeroed:
            warnings.warn(
                f"truncated {zeroed} outcome(s) below precision {precision!r}",
                TruncationWarning,
                stacklevel=2,
            )
        if not survived:
            return H({})
        # Reduce to lowest terms (preserving zero-count keys) regardless of
        # whether anything was zeroed -- the count magnitude is what matters
        # for downstream big-int cost. For the deep-recursion case, this
        # collapses single-surviving-outcome Hs from H({k: huge}) to
        # H({k: 1}), bounding the magnitude across recursion levels.
        return H(counts).lowest_terms(preserve_zero_counts=True)

    def _eval_name(self, name: Expr | None) -> str | None:
        if name is None:
            return None
        v = self._eval(name)
        if isinstance(v, str):
            return v
        else:
            raise TypeError(
                f"output name must resolve to string, got {type(v).__name__}"
            )

    def _eval_string(self, parts: list[StrLit | StrVar]) -> str:
        fragments: list[str] = []
        for part in parts:
            if isinstance(part, StrLit):
                fragments.append(part.text)
            elif isinstance(part, StrVar):
                if part.name not in self._env:
                    raise NameError(f"undefined variable: {part.name!r}")
                fragments.append(self._stringify(self._env[part.name]))
        return "".join(fragments)

    def _stringify(self, v: _Val) -> str:
        # Used for string interpolation. We don't try to reverse-engineer AnyDice's
        # source-text rendering ("2d6", "d{1..6}", etc.) for arbitrary values. Our
        # evaluated form has lost that history. Instead we render opaquely with just
        # enough shape to disambiguate types, plus a special case for empties (useful as
        # a debugging signal).
        #   int             -> decimal
        #   ()              -> "{}"
        #   non-empty tuple -> "{?}"
        #   H({})           -> "d{}"
        #   non-empty H     -> "d{?}"
        #   P of size N     -> "Nd{?}"
        if isinstance(v, int):
            return str(v)
        if isinstance(v, tuple):
            return "{}" if not v else "{?}"
        if isinstance(v, H):
            return "d{}" if not v else "d{?}"
        if isinstance(v, P):
            return f"{len(v)}d{{?}}"
        raise TypeError(f"cannot interpolate {type(v).__name__} into a string")

    # ---- Sequence evaluation -------------------------------------------------------------

    def _eval_seq(self, elems: list[SeqElem]) -> SeqT:
        values: list[int] = []
        for elem in elems:
            if isinstance(elem, ValueElem):
                self._extend_seq_value(values, self._eval(elem.expr), repeat=1)
            elif isinstance(elem, ValueRepeatElem):
                repeat = self._eval(elem.repeat)
                if isinstance(repeat, tuple):
                    repeat = sum(repeat)
                if not isinstance(repeat, int):
                    raise TypeError("sequence repeat count must be a number")
                self._extend_seq_value(values, self._eval(elem.expr), repeat=repeat)
            elif isinstance(elem, RangeElem):
                start = self._eval_int(elem.start, "range bounds")
                stop = self._eval_int(elem.stop, "range bounds")
                # AnyDice: Only ascending ranges yield values. Descending yields empty.
                if start <= stop:
                    values.extend(range(start, stop + 1))
            elif isinstance(elem, RangeRepeatElem):
                start = self._eval_int(elem.start, "range bounds")
                stop = self._eval_int(elem.stop, "range bounds")
                repeat = self._eval_int(elem.repeat, "range repeat count")
                if start <= stop:
                    # `{a..b:N}` concatenates the whole [a..b] range N times, *not* each
                    # element repeated N times
                    values.extend(list(range(start, stop + 1)) * repeat)
            else:
                raise NotImplementedError(
                    f"unhandled sequence element: {type(elem).__name__}"
                )
        # Sequences preserve write order. The "position order" setting affects digit
        # selection on numbers and position selection on pools, not sequence indexing.
        return tuple(values)

    def _extend_seq_value(self, values: list[int], v: _Val, *, repeat: int) -> None:
        if isinstance(v, int):
            values.extend([v] * repeat)
            return
        if isinstance(v, tuple):
            # Sub-sequences flatten into the outer sequence (concatenation), not
            # sum-coerce. AnyDice idiom: {NEW, val} appends val to NEW. Bug
            # discovered via 663d's `set element` function.
            values.extend(list(v) * repeat)
            return
        if isinstance(v, P):
            v = v.h()
        if isinstance(v, H):
            # AnyDice repeats the distinct-outcomes block as a unit, not each
            # outcome individually: `{d4:2}` yields (1, 2, 3, 4, 1, 2, 3, 4),
            # not (1, 1, 2, 2, 3, 3, 4, 4). Verified via 42971/42974/42975.
            # H already iterates outcomes in ascending order (sorted on
            # construction), so we extend directly without materializing.
            for _ in range(repeat):
                values.extend(v)
            return
        raise TypeError(
            f"sequence element must be a number, sequence, or die, got {type(v).__name__}"
        )

    def _eval_int(self, expr: Expr, what: str) -> int:
        v = self._eval(expr)
        if isinstance(v, tuple):
            v = sum(v)
        if isinstance(v, int):
            return v
        raise TypeError(f"{what} must be a number")

    # ---- Function calls ------------------------------------------------------------------

    def _call(self, call: Call) -> _Val:
        # Recursion-depth guard: Each call exceeding the configured maximum returns
        # H({}) without executing the body. The unwinding result is then governed by
        # how each operator treats H({}) (e.g. + treats it as 0; / propagates).
        if self._depth >= self._settings.max_depth:
            return H({})
        shape = _call_shape(call.parts)
        args: list[_Val] = [
            self._eval(part) for part in call.parts if not isinstance(part, str)
        ]
        # User-defined functions shadow builtins by lookup order.
        entry: FunctionDef | tuple[list[str | None], Callable[..., _Val]] | None = (
            self._funcs.get(shape) or self._builtins.get(shape)
        )
        if entry is None:
            raise NameError(f"undefined function for call: {call.parts!r}")
        return self._invoke(entry, args)

    def _bind_and_expand(  # noqa: C901
        self,
        param_types: list[str | None],
        args: list[_Val],
        *,
        err_label: Callable[[int], str],
    ) -> tuple[list[_Val], list[tuple[int, list[tuple[_Val, int]]]]] | None:
        r"""Coerce args per their param types, building the (bound, expansion) pair.

        Returns `(bound, expansion)` where `bound` carries each arg in its final
        per-param shape and `expansion` lists the per-param iteration items for
        any `:n`/`:s` arg that needs to expand the body across outcomes.
        Returns `None` to signal an early-empty short-circuit: an empty H bound
        to an `:n` or `:s` param means the caller should return `H({})` without
        executing the body.

        Param-type semantics (shared between user-defined and builtin entry):
            * `None`: pass arg through with no coercion (AnyDice bare-param).
            * `:n`: sum-coerce sequences, collapse P -> H; scalar binds directly,
              H expands per-outcome.
            * `:d`: int/tuple wraps as a 1-outcome H; H/P passes through (no
              empty short-circuit -- the body decides).
            * `:s`: int wraps as `(int,)`, tuple binds directly, P expands per-roll
              under AnyDice's tripartite rule (single-die pool -> ascending
              H-outcome order; multi-die under highest-first -> roll-tuples
              sorted by reversed form lex-descending; multi-die under lowest-
              first -> roll-tuples sorted lex-ascending; corpus 0xbcc and
              probes -0x2a / -0x2b / -0x2c), H expands as singleton-per-outcome.

        *err_label(i)* returns the human-readable label for param `i`, used in
        TypeError messages -- e.g. `"function param FOO"` or `"builtin param 0"`.
        """
        bound: list[_Val] = [0] * len(param_types)
        expansion: list[tuple[int, list[tuple[_Val, int]]]] = []
        for i, (ptype, arg) in enumerate(zip(param_types, args, strict=True)):
            if ptype is None:
                # AnyDice's bare/untyped params pass the argument through without
                # coercion or expansion. The body sees whatever was passed --
                # int as int, seq as seq, die as die, pool as pool. Verified
                # against AnyDice via probes (42ace and the [f {1,2,3}]/#X
                # round-trip).
                bound[i] = arg
            elif ptype == "n":
                if isinstance(arg, P):
                    arg = arg.h()  # noqa: PLW2901
                if isinstance(arg, tuple):
                    # AnyDice sum-coerces a seq arg to `:n`, then wraps it as
                    # a 1-outcome die at that sum so the call still routes
                    # through the expansion-aggregation path. That way a
                    # body that returns a tuple gets per-iter sum-coerced
                    # (1 iter), even though the seq arg itself doesn't
                    # multiply iterations. An empty seq is `H({sum(()): 1})`
                    # = `H({0: 1})`, NOT `H({})` -- AnyDice runs the body
                    # once with N=0 rather than eliminating the call.
                    # Verified via tmp-probes -0x40 (weighted-seq body), -0x41
                    # (scalar body), and -0x42 (empty-seq edge case).
                    arg = H({sum(arg): 1})  # noqa: PLW2901
                if isinstance(arg, int):
                    bound[i] = arg
                elif isinstance(arg, H):
                    if not arg:
                        # An empty die argument to an n-typed param yields H({})
                        return None
                    expansion.append((i, [(o, w) for o, w in arg.items()]))
                else:
                    raise TypeError(
                        f"{err_label(i)}: expected number, got {type(arg).__name__}"
                    )
            elif ptype == "d":
                # `:d` is lossless on pools: the body's `@` and other pool-aware
                # ops must see the actual pool. Arithmetic and comparison ops
                # already collapse P -> H at the operator site, so keeping P in
                # the env doesn't break those.
                #
                # Note we DO NOT short-circuit on empty H/P here -- the body
                # runs once regardless, and the body's conditionals decide
                # whether each outcome eliminates (e.g. `if X { result: REROLL }`
                # with REROLL bound to d{} only eliminates the X-matching
                # branches, not the whole call).
                if isinstance(arg, int):
                    arg = H({arg: 1})  # noqa: PLW2901
                elif isinstance(arg, tuple):
                    # AnyDice sum-coerces a seq to an int, then wraps as a 1-outcome die
                    # (NOT distinct outcomes)
                    arg = H({sum(arg): 1})  # noqa: PLW2901
                if not isinstance(arg, (H, P)):
                    raise TypeError(
                        f"{err_label(i)}: expected die, got {type(arg).__name__}"
                    )
                bound[i] = arg
            elif ptype == "s":
                if isinstance(arg, int):
                    bound[i] = (arg,)
                elif isinstance(arg, tuple):
                    bound[i] = arg
                elif isinstance(arg, P):
                    if not arg.h():
                        return None
                    if len(arg) == 1:
                        expansion.append((i, [((o,), w) for o, w in arg.h().items()]))
                    elif self._settings.highest_first():
                        rolls = sorted(
                            arg.rolls_with_counts(),
                            key=lambda rc: rc[0][::-1],
                            reverse=True,
                        )
                        expansion.append((i, [(r[::-1], c) for r, c in rolls]))
                    else:
                        rolls = sorted(arg.rolls_with_counts())
                        expansion.append((i, [(r, c) for r, c in rolls]))
                elif isinstance(arg, H):
                    if not arg:
                        return None
                    # A bare die (vs a pool) is treated as a 1-element seq. The body
                    # still expands once per outcome with X = (outcome,).
                    expansion.append((i, [((o,), w) for o, w in arg.items()]))
                else:
                    raise TypeError(
                        f"{err_label(i)}: expected sequence, got {type(arg).__name__}"
                    )
            else:
                raise NotImplementedError(f"unknown param type: {ptype!r}")
        return bound, expansion

    def _invoke(
        self,
        entry: FunctionDef | tuple[list[str | None], Callable[..., _Val]],
        args: list[_Val],
    ) -> _Val:
        # Polymorphic on entry type. User-defined functions (`FunctionDef`)
        # tree-walk an AST body inside a managed local env with first-
        # occurrence-wins duplicate-name handling. Builtins
        # (`(param_types, impl)`) call a Python callable per expansion combo
        # with the bound args. Both paths share the per-param coercion via
        # `_bind_and_expand` and the LCM-aggregate via `_aggregate_iters`.
        if isinstance(entry, FunctionDef):
            params = [p for p in entry.pattern if isinstance(p, Param)]
            param_types = [p.type for p in params]
            err_label = lambda i: f"function param {params[i].name}"  # noqa: E731
            bind = self._bind_and_expand(param_types, args, err_label=err_label)
            if bind is None:
                return H({})
            bound, expansion = bind
            return self._invoke_user(entry, params, bound, expansion)
        else:
            param_types, impl = entry
            err_label = lambda i: f"builtin param {i}"  # noqa: E731
            bind = self._bind_and_expand(param_types, args, err_label=err_label)
            if bind is None:
                return H({})
            bound, expansion = bind
            return self._invoke_builtin(impl, bound, expansion)

    def _invoke_user(
        self,
        func: FunctionDef,
        params: list[Param],
        bound: list[_Val],
        expansion: list[tuple[int, list[tuple[_Val, int]]]],
    ) -> _Val:
        # No-expansion fast path: invoke the body once with `bound` installed
        # in the env. Truncate the return when it's an H -- important for deep-
        # recursion programs whose recursive calls are all-passthrough (e.g.
        # `function: f N:n D:d { ... [f N/2 D] ... }` -- both args bypass
        # expansion, so the body's bigint-growing operations would otherwise
        # propagate untruncated).
        if not expansion:
            r = self._invoke_with_bound(func, params, bound)
            return self._truncate(r) if isinstance(r, H) else r

        # Cartesian product over expanded iterations. Per-iteration return
        # values may have differing internal totals (a body branch returning
        # a die has sum>1; a branch returning a scalar has sum=1). AnyDice
        # normalizes those internal totals to a common LCM before combining
        # so each iteration contributes its outer weight, not its outer
        # weight scaled by its inner total. Same pattern as
        # `_expand_dice_count`.
        #
        # The function's local env is forked ONCE at the top of the call.
        # Within that single local env, the body runs once per outcome combo.
        # Two distinct semantics across iterations:
        #   - Parameters reset to their entry-bound values at the start of
        #     each iteration. Verified via 5fec (`SEQUENCE:s` parameter, body
        #     does `SEQUENCE: [remove X from SEQUENCE]`; AnyDice's output
        #     matches independent draw-without-replacement semantics, which
        #     requires each X-iteration to see the original SEQUENCE).
        #   - Non-parameter variables persist mutations across iterations.
        #     Verified via program -7 (`[weird d6]` produces the cumulative
        #     sequence d{1, 3, 6, 10, 15, 21}, where REROLL is a non-param
        #     accumulator that visibly carries across V-iterations).

        # Duplicate-named params: AnyDice's rule is FIRST-OCCURRENCE WINS
        # (positional, regardless of `:n`/`:d`/`:s` annotation). Subsequent
        # same-named params are bound but their values are discarded -- the
        # body sees only the first binding. Verified empirically:
        #   function: dup A:n and A:d { result: A } output [dup 7 and 1d6]
        #     -> H({7: 1})
        #   function: dup A:n and A:d { if A=7 {result: 1dA} result: 999 }
        #     output [dup 7 and 1d6] -> H({1:1,...,7:1}) i.e. 1dA = 1d7.
        # Surfaced by corpus program 26018 (signature has `D:n` and `D:d`).
        first_idx_for_name: dict[str, int] = {}
        for i, param in enumerate(params):
            first_idx_for_name.setdefault(param.name, i)

        saved_env = self._env
        self._env = dict(saved_env)
        self._depth += 1
        try:

            def _per_iter(combo: tuple[tuple[_Val, int], ...]) -> _Val:
                # Reset ALL params to their entry-bound values per iter.
                # Non-param env vars persist their mutations from the
                # previous iter. Skip duplicate-named param positions so
                # only the first-occurrence binding takes effect.
                for i, param in enumerate(params):
                    if first_idx_for_name[param.name] == i:
                        self._env[param.name] = bound[i]
                # Override expanding params with this iteration's combo,
                # again only at the first-occurrence position so a
                # duplicate that happens to expand doesn't clobber the
                # earlier binding.
                for j, (idx, _) in enumerate(expansion):
                    value, _w = combo[j]
                    if first_idx_for_name[params[idx].name] == idx:
                        self._env[params[idx].name] = value
                return self._execute_body(func)

            return self._aggregate_iters(
                expansion, reverse_combos=True, per_iter=_per_iter
            )
        finally:
            self._depth -= 1
            self._env = saved_env

    def _invoke_builtin(
        self,
        impl: Callable[..., _Val],
        bound: list[_Val],
        expansion: list[tuple[int, list[tuple[_Val, int]]]],
    ) -> _Val:
        # No-expansion fast path: just call the impl with the bound args.
        if not expansion:
            return impl(self._settings, *bound)

        # Expansion path: aggregate impl results across the Cartesian product.
        # `reverse_combos=True` mirrors the user-defined enumeration order.
        # Stateless builtin impls produce aggregates that are independent of
        # iteration order, so True is observably equivalent to False here.
        # The `_depth` bracket is structurally a no-op for builtins (impls
        # don't recursively re-enter `_call`), but kept for symmetry with the
        # user-defined path so future stateful builtins, if any, would behave
        # consistently.
        self._depth += 1
        try:

            def _per_iter(combo: tuple[tuple[_Val, int], ...]) -> _Val:
                for j, (idx, _) in enumerate(expansion):
                    value, _w = combo[j]
                    bound[idx] = value
                return impl(self._settings, *bound)

            return self._aggregate_iters(
                expansion, reverse_combos=True, per_iter=_per_iter
            )
        finally:
            self._depth -= 1

    def _aggregate_iters(
        self,
        expansion: list[tuple[int, list[tuple[_Val, int]]]],
        *,
        reverse_combos: bool,
        per_iter: Callable[[tuple[tuple[_Val, int], ...]], _Val],
    ) -> H[int]:
        r"""LCM-aggregate per-iteration results across the expansion's
        Cartesian product, returning a truncated H.

        Each combination of expansion items is passed to *per_iter*, which
        mutates whatever ambient state it needs (env, bound list, etc.) and
        returns the body result for that combination. The per-combination
        weight (product of the expansion's item weights) is computed here.

        *reverse_combos* controls iteration order:
            * `True`: iterate with the *reversed* expansion order so the first
              expansion entry varies fastest (AnyDice's little-endian rule;
              required for any user-defined function body that may observe
              iteration order via non-param accumulators).
            * `False`: iterate the natural Cartesian-product order. Observably
              equivalent to True for any *per_iter* whose return depends only
              on the combination's values (e.g. stateless builtin impls), but
              distinct for user-defined bodies that read mutated non-param
              env vars.
        """
        from itertools import product

        if reverse_combos:
            items_list = [items for _, items in reversed(expansion)]
        else:
            items_list = [items for _, items in expansion]

        def _gen() -> Iterator[tuple[H[int], int]]:
            for combo in product(*items_list):
                if reverse_combos:
                    combo = combo[::-1]  # noqa: PLW2901
                weight = 1
                for _, w in combo:
                    weight *= w
                r = per_iter(combo)
                # When a body iteration returns a sequence, AnyDice sum-coerces
                # it to a single number rather than distributing seq elements
                # as separate outcomes. (Verified against AnyDice via 405c6's
                # `[roll 1d6 1d6]` which produces an H over A+B+C, not over
                # {A+B, C} elements.)
                if isinstance(r, tuple):
                    r = sum(r)
                yield self._coerce_to_h(r), weight

        return self._truncate(aggregate_weighted(_gen()))  # ty: ignore[invalid-argument-type]

    def _execute_body(self, func: FunctionDef) -> _Val:
        r"""Run `func`'s body in the current env, returning the `result:` value
        or `H({})` if the body falls through. Caller is responsible for env
        save/restore and depth tracking. Used directly by `_invoke`'s
        expansion path so iterations share the function's local env."""
        try:
            for stmt in func.body:
                self._exec(stmt)
        except _ResultReturn as r:
            return r.value
        return H({})

    def _invoke_with_bound(
        self, func: FunctionDef, params: list[Param], bound: list[_Val]
    ) -> _Val:
        saved_env = self._env
        self._env = dict(saved_env)
        # First-occurrence wins for duplicate-named params (see `_invoke`'s
        # expansion path for the full rationale + AnyDice verification).
        seen: set[str] = set()
        for param, val in zip(params, bound, strict=True):
            if param.name not in seen:
                self._env[param.name] = val
                seen.add(param.name)
        self._depth += 1
        try:
            return self._execute_body(func)
        finally:
            self._depth -= 1
            self._env = saved_env
