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
from collections import Counter
from collections.abc import Callable
from functools import reduce
from math import lcm

from dyce import H, P, RollT

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

__all__ = ("AnyDiceInterpreter",)

NumT = int
SeqT = RollT[NumT]
DieT = P[NumT]
AnyDiceResultT = tuple[str, H[int]]
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
_Val = NumT | H[int] | DieT | SeqT | str

# ---- Operator tables ---------------------------------------------------------------------

_OP_FUNCS: dict[str, Callable[[int, int], int]] = {
    "+": operator.add,
    "-": operator.sub,
    "*": operator.mul,
    # AnyDice truncates toward zero (matches int(a/b)) and substitutes 0 for division
    # by zero rather than raising; the substitution applies per-outcome inside H/H or
    # H/int dispatch via the cross-product in `_h_binop`.
    "/": lambda a, b: 0 if b == 0 else int(a / b),
    "^": operator.pow,
    "=": lambda a, b: int(a == b),
    "!=": lambda a, b: int(a != b),
    "<": lambda a, b: int(a < b),
    ">": lambda a, b: int(a > b),
    "<=": lambda a, b: int(a <= b),
    ">=": lambda a, b: int(a >= b),
    "&": lambda a, b: int(bool(a) and bool(b)),
    "|": lambda a, b: int(bool(a) or bool(b)),
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

_ARITH_OPS = {"+", "-", "*", "/", "^"}
_CMP_OPS = {"=", "!=", "<", ">", "<=", ">="}
_BOOL_OPS = {"&", "|"}

# +/- treat empty die as scalar 0; */^ propagate emptiness as H({})
_EMPTY_DIE_AS_ZERO_ARITH = {"+", "-"}

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
        for stmt in program.stmts:
            self._exec(stmt)
        return list(self._outputs)

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
            return self._make_die(self._eval(node.faces))
        elif isinstance(node, DiceBinOp):
            n = self._eval(node.n)
            if isinstance(n, tuple):
                n = sum(n)
            if isinstance(n, P):
                n = n.h()
            if isinstance(n, int):
                return self._roll_n(n, self._make_die(self._eval(node.faces)))
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

    def _apply_neg(self, v: _Val) -> int | H[int]:
        if isinstance(v, tuple):
            v = sum(v)
        elif isinstance(v, P):
            v = v.h()
        if isinstance(v, (int, H)):
            return -v
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
            # `#P` returns the number of dice in the pool; an empty pool yields
            # 0 (does NOT propagate emptiness). Verified via 42af3.
            return len(v) if v.h() else 0
        elif isinstance(v, H):
            # A bare die is a 1-position pool. Empty H -> 0. Verified via 42af3.
            return 1 if v else 0
        else:  # pragma: no cover
            raise TypeError(f"cannot apply # to {type(v).__name__}")

    # ---- Binary operators ----------------------------------------------------------------

    def _apply_binop(self, op: str, left: _Val, right: _Val) -> int | H[int]:
        if op in _ARITH_OPS:
            return self._apply_arith(op, left, right)
        elif op in _CMP_OPS:
            return self._apply_cmp(op, left, right)
        elif op in _BOOL_OPS:
            return self._apply_bool(op, left, right)
        else:  # pragma: no cover
            raise NotImplementedError(f"unhandled operator: {op!r}")

    def _apply_arith(self, op: str, left: _Val, right: _Val) -> int | H[int]:
        # Sequences sum-coerce in arithmetic contexts
        if isinstance(left, tuple):
            left = sum(left)
        if isinstance(right, tuple):
            right = sum(right)
        if isinstance(left, P):
            left = left.h()
        if isinstance(right, P):
            right = right.h()
        # Empty-die handling: + and - treat empty die as scalar 0. * / and ^ propagate
        # H({}).
        if isinstance(left, H) and not left:
            if op in _EMPTY_DIE_AS_ZERO_ARITH:
                left = 0
            else:
                return H({})
        if isinstance(right, H) and not right:
            if op in _EMPTY_DIE_AS_ZERO_ARITH:
                right = 0
            else:
                return H({})
        return self._h_binop(op, left, right)

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

    def _apply_bool(self, op: str, left: _Val, right: _Val) -> int | H[int]:  # noqa: C901
        # Sequences sum-coerce for boolean ops
        if isinstance(left, tuple):
            left = sum(left)
        if isinstance(right, tuple):
            right = sum(right)
        if isinstance(left, P):
            left = left.h()
        if isinstance(right, P):
            right = right.h()
        l_empty = isinstance(left, H) and not left
        r_empty = isinstance(right, H) and not right
        if op == "&":
            # Both sides propagate empty-die emptiness
            if l_empty or r_empty:
                return H({})
        elif op == "|":
            # AnyDice anomaly: d{} | <0> propagates H({}) (where <0> is empty seq summed
            # to 0 or another empty die), but d{} | <nonzero> does NOT propagate (acts
            # as scalar 0). We match AnyDice's actual outputs.
            if l_empty and r_empty:
                return H({})
            if l_empty and isinstance(right, int) and right == 0:
                return H({})
            if l_empty:
                left = 0
            if r_empty:
                right = 0
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
        for lo, lw in left_h.items():
            for ro, rw in right_h.items():
                outcome = _OP_FUNCS[op](lo, ro)
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
        if isinstance(left, tuple):
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
                return H({0: 1})
            return pool.h(*selectors)
        if not isinstance(left, int):
            raise TypeError(
                f"@ left operand must be a number or sequence, got {type(left).__name__}"
            )
        size = len(pool)
        if left < 1 or left > size:
            return H({0: 1})
        # 1-based position. highest-first: pos 1 = highest = pool.h(-1).
        # lowest-first:  pos 1 = lowest  = pool.h(0).
        elif self._settings.highest_first():
            return pool.h(-left)
        else:
            return pool.h(left - 1)

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
            return H({0: 1}) if faces == 0 else H(faces)
        elif isinstance(faces, tuple):
            return H(Counter(faces)) if faces else H({})
        elif isinstance(faces, P):
            return faces.h()
        elif isinstance(faces, H):
            return faces
        else:
            raise TypeError(f"cannot use {type(faces).__name__} as die faces")

    def _roll_n(self, n: int, die: H[int]) -> H[int] | DieT:
        if not die:
            # Empty die regardless of n
            return H({})
        elif n <= 0:
            return H({0: 1})
        else:
            # Use a Pool so that @ can select positions. Arithmetic/output sums via .h().
            return n @ P(die)

    def _expand_dice_count(self, n_die: H[int], face_die: H[int]) -> H[int]:
        # For each outcome k of n_die with weight w_k, compute kd<face_die> and
        # combine. Inner distributions can have different totals (e.g. 1d6 has
        # total 6 vs 2d6's 36), so we LCM-normalize them before merging to
        # preserve the relative probabilities of each outer-outcome branch.
        if not n_die:
            return H({})
        inner: list[tuple[int, int, H[int]]] = []  # (k, w_k, kd<face_die>)
        for k, w_k in n_die.items():
            sub = self._roll_n(k, face_die)
            sub_h = sub.h() if isinstance(sub, P) else sub
            inner.append((k, w_k, sub_h))
        nonzero_totals = [sum(h.values()) for _, _, h in inner if h]
        if not nonzero_totals:
            return H({})
        total_lcm = reduce(lcm, nonzero_totals)
        result: dict[int, int] = {}
        for _, w_k, h in inner:
            if not h:
                continue
            scale = total_lcm // sum(h.values())
            for o, c in h.items():
                result[o] = result.get(o, 0) + c * scale * w_k
        return H(result)

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

    def _eval_seq(self, elems: list[SeqElem]) -> SeqT:  # noqa: C901
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
                    for v in range(start, stop + 1):
                        values.extend([v] * repeat)
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
        func = self._funcs.get(shape)
        if func is not None:
            params: list[Param] = [p for p in func.pattern if isinstance(p, Param)]
            return self._invoke(func, params, args)
        builtin = self._builtins.get(shape)
        if builtin is not None:
            param_types, impl = builtin
            return self._call_builtin(param_types, args, impl)
        raise NameError(f"undefined function for call: {call.parts!r}")

    def _invoke(self, func: FunctionDef, params: list[Param], args: list[_Val]) -> _Val:  # noqa: C901
        # For each parameter, decide whether the argument needs to expand the body (a
        # die or pool argument bound to an n- or s-typed param) or be passed through
        # (d-typed dice, concrete numbers, sequences as-is). Each expansion entry stores
        # the iterations as `(bound_value, weight)` pairs already in the right shape for
        # assignment, unifying H-outcome and pool-roll cases.
        bound: list[_Val] = [0] * len(params)
        expansion: list[tuple[int, list[tuple[_Val, int]]]] = []
        for i, (param, arg) in enumerate(zip(params, args, strict=True)):
            ptype = param.type
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
                    arg = sum(arg)  # noqa: PLW2901
                if isinstance(arg, int):
                    bound[i] = arg
                elif isinstance(arg, H):
                    if not arg:
                        # An empty die argument to an n-typed param yields H({})
                        return H({})
                    expansion.append((i, [(o, w) for o, w in arg.items()]))
                else:
                    raise TypeError(
                        f"function param {param.name}: expected number, got {type(arg).__name__}"
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
                        f"function param {param.name}: expected die, got {type(arg).__name__}"
                    )
                bound[i] = arg
            elif ptype == "s":
                if isinstance(arg, int):
                    bound[i] = (arg,)
                elif isinstance(arg, tuple):
                    bound[i] = arg
                elif isinstance(arg, P):
                    # Pool: Each roll becomes a tuple sorted by position-order setting.
                    # dyce yields rolls in ascending order. Reverse for the default
                    # highest-first.
                    if not arg.h():
                        return H({})

                    expansion.append(
                        (i, [(r[::-1], c) for r, c in arg.rolls_with_counts()])
                        if self._settings.highest_first()
                        else (i, [(r, c) for r, c in arg.rolls_with_counts()])
                    )
                elif isinstance(arg, H):
                    if not arg:
                        return H({})
                    # A bare die (vs a pool) is treated as a 1-element seq. The body
                    # still expands once per outcome with X = (outcome,).
                    expansion.append((i, [((o,), w) for o, w in arg.items()]))
                else:
                    raise TypeError(
                        f"function param {param.name}: expected sequence, got {type(arg).__name__}"
                    )
            else:
                raise NotImplementedError(f"unknown param type: {ptype!r}")

        if not expansion:
            return self._invoke_with_bound(func, params, bound)

        # Cartesian product over expanded iterations. Per-iteration return values may
        # have differing internal totals (a body branch returning a die has sum>1; a
        # branch returning a scalar has sum=1). AnyDice normalizes those internal
        # totals to a common LCM before combining so each iteration contributes its
        # outer weight, not its outer weight scaled by its inner total. Same pattern
        # as `_expand_dice_count`.
        from itertools import product

        iterations: list[tuple[int, H[int]]] = []
        for combo in product(*[items for _, items in expansion]):
            weight = 1
            for j, (idx, _) in enumerate(expansion):
                value, w = combo[j]
                bound[idx] = value
                weight *= w
            r = self._invoke_with_bound(func, params, bound)
            # When a body iteration returns a sequence, AnyDice sum-coerces it to a
            # single number rather than distributing seq elements as separate
            # outcomes. (Verified against AnyDice via 405c6's `[roll 1d6 1d6]`
            # which produces an H over A+B+C, not over {A+B, C} elements.)
            if isinstance(r, tuple):
                r = sum(r)
            iterations.append((weight, self._coerce_to_h(r)))

        nonzero_totals = [sum(h.values()) for _, h in iterations if h]
        if not nonzero_totals:
            return H({})
        total_lcm = reduce(lcm, nonzero_totals)
        result: dict[int, int] = {}
        for weight, r_h in iterations:
            if not r_h:
                continue
            scale = total_lcm // sum(r_h.values())
            for outcome, count in r_h.items():
                result[outcome] = result.get(outcome, 0) + count * scale * weight
        return H(result)

    def _invoke_with_bound(
        self, func: FunctionDef, params: list[Param], bound: list[_Val]
    ) -> _Val:
        saved_env = self._env
        self._env = dict(saved_env)
        for param, val in zip(params, bound, strict=True):
            self._env[param.name] = val
        self._depth += 1
        try:
            try:
                for stmt in func.body:
                    self._exec(stmt)
            except _ResultReturn as r:
                return r.value
            # Function fell through without firing a `result:`; AnyDice returns
            # H({}) (the empty die) in that case.
            return H({})
        finally:
            self._depth -= 1
            self._env = saved_env

    def _call_builtin(  # noqa: C901
        self,
        param_types: list[str | None],
        args: list[_Val],
        impl: Callable[..., _Val],
    ) -> _Val:
        # Builtin dispatch mirrors `_invoke`'s coercion (n-typed expands across H
        # outcomes; s-typed expands across pool rolls or die outcomes-as-singleton-seqs)
        # but DIFFERS for d-typed: pools are passed through as-is rather than collapsed
        # via `arg.h()`. This preserves per-die structure that some builtins
        # (e.g. `[highest N of P]`) need. Bare param types (None) pass through with
        # no coercion (matches the AnyDice bare-param semantic in `_invoke`).
        bound: list[_Val] = [0] * len(param_types)
        expansion: list[tuple[int, list[tuple[_Val, int]]]] = []
        for i, (ptype, arg) in enumerate(zip(param_types, args, strict=True)):
            if ptype is None:
                bound[i] = arg
            elif ptype == "n":
                if isinstance(arg, P):
                    arg = arg.h()  # noqa: PLW2901
                if isinstance(arg, tuple):
                    arg = sum(arg)  # noqa: PLW2901
                if isinstance(arg, int):
                    bound[i] = arg
                elif isinstance(arg, H):
                    if not arg:
                        return H({})
                    expansion.append((i, [(o, w) for o, w in arg.items()]))
                else:
                    raise TypeError(
                        f"builtin param {i}: expected number, got {type(arg).__name__}"
                    )
            elif ptype == "d":
                # `:d` builtins do NOT short-circuit on empty H/P -- the impl
                # decides (e.g. `[explode d{}]` -> H({}), but `[maximum of
                # d{}]` -> 0). Same convention as user functions in `_invoke`.
                if isinstance(arg, int):
                    arg = H({arg: 1})  # noqa: PLW2901
                elif isinstance(arg, tuple):
                    arg = H({sum(arg): 1})  # noqa: PLW2901
                if not isinstance(arg, (H, P)):
                    raise TypeError(
                        f"builtin param {i}: expected die, got {type(arg).__name__}"
                    )
                bound[i] = arg
            elif ptype == "s":
                if isinstance(arg, int):
                    bound[i] = (arg,)
                elif isinstance(arg, tuple):
                    bound[i] = arg
                elif isinstance(arg, P):
                    if not arg.h():
                        return H({})
                    expansion.append(
                        (i, [(r[::-1], c) for r, c in arg.rolls_with_counts()])
                        if self._settings.highest_first()
                        else (i, [(r, c) for r, c in arg.rolls_with_counts()])
                    )
                elif isinstance(arg, H):
                    if not arg:
                        return H({})
                    expansion.append((i, [((o,), w) for o, w in arg.items()]))
                else:
                    raise TypeError(
                        f"builtin param {i}: expected sequence, got {type(arg).__name__}"
                    )
            else:
                raise NotImplementedError(f"unknown builtin param type: {ptype!r}")

        if not expansion:
            return impl(self._settings, *bound)

        # Same LCM-normalization pattern as `_invoke`: per-iteration return values
        # may have differing internal totals (latent for the currently-wired highest
        # variants, but will surface for any builtin returning a variable-total H).
        from itertools import product

        iterations: list[tuple[int, H[int]]] = []
        for combo in product(*[items for _, items in expansion]):
            weight = 1
            for j, (idx, _) in enumerate(expansion):
                value, w = combo[j]
                bound[idx] = value
                weight *= w
            r = impl(self._settings, *bound)
            # Mirror `_invoke`: sum-coerce a tuple return to a single number.
            if isinstance(r, tuple):
                r = sum(r)
            iterations.append((weight, self._coerce_to_h(r)))

        nonzero_totals = [sum(h.values()) for _, h in iterations if h]
        if not nonzero_totals:
            return H({})
        total_lcm = reduce(lcm, nonzero_totals)
        result: dict[int, int] = {}
        for weight, r_h in iterations:
            if not r_h:
                continue
            scale = total_lcm // sum(r_h.values())
            for outcome, count in r_h.items():
                result[outcome] = result.get(outcome, 0) + count * scale * weight
        return H(result)
