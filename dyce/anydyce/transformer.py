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

import re

from lark import Token, Transformer
from lark.visitors import v_args

from .ast_ import (
    BinOp,
    Call,
    DiceBinOp,
    DiceUnary,
    ElseBranch,
    EmptySeq,
    Expr,
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

_IVAR_RE = re.compile(r"\[([A-Z][A-Z_]*)\]")

__all__ = ("AnyDiceTransformer",)


def _parse_string(token: str) -> StringExpr:
    r"""Convert a STRING token (with enclosing quotes) to a StringExpr."""
    inner = token[1:-1]  # strip leading/trailing "
    parts: list[StrLit | StrVar] = []
    pos = 0
    for m in _IVAR_RE.finditer(inner):
        if m.start() > pos:
            parts.append(StrLit(inner[pos : m.start()]))
        parts.append(StrVar(m.group(1)))
        pos = m.end()
    if pos < len(inner):
        parts.append(StrLit(inner[pos:]))
    if not parts:
        parts.append(StrLit(""))
    return StringExpr(parts)


@v_args(inline=True)
class AnyDiceTransformer(Transformer):
    # ---- Program -----------------------------------------------------------------------

    def start(self, *stmts: Stmt) -> Program:
        return Program(list(stmts))

    # ---- Statements --------------------------------------------------------------------

    def output_named(self, expr: Expr, name: StringExpr) -> OutputStmt:
        return OutputStmt(expr=expr, name=name)

    def output_anon(self, expr: Expr) -> OutputStmt:
        return OutputStmt(expr=expr, name=None)

    def function_def(self, funcname: list[str | Param], *stmts: Stmt) -> FunctionDef:
        return FunctionDef(pattern=funcname, body=list(stmts))

    def loop_stmt(self, var: Token, over: Expr, *stmts: Stmt) -> LoopStmt:
        return LoopStmt(var=str(var), over=over, body=list(stmts))

    def set_stmt(self, key: Token, value: Expr) -> SetStmt:
        return SetStmt(key=str(key)[1:-1], value=value)  # strip enclosing quotes

    def result_stmt(self, expr: Expr) -> ResultStmt:
        return ResultStmt(expr=expr)

    def var_assign(self, name: Token, expr: Expr) -> VarAssign:
        return VarAssign(name=str(name), expr=expr)

    def if_stmt(self, cond: Expr, *rest: Stmt | IfBranch | ElseBranch) -> IfStmt:
        # With @v_args(inline=True) and stmt* inlined, rest is a flat mix of
        # body statements, IfBranch nodes (from elseif), and an optional ElseBranch.
        # IfBranch and ElseBranch are always at the tail; body stmts come first.
        body: list[Stmt] = []
        branches_extra: list[IfBranch] = []
        else_branch: ElseBranch | None = None
        for node in rest:
            if isinstance(node, IfBranch):
                branches_extra.append(node)
            elif isinstance(node, ElseBranch):
                else_branch = node
            else:
                body.append(node)
        return IfStmt(
            branches=[IfBranch(condition=cond, body=body), *branches_extra],
            else_branch=else_branch,
        )

    def elseif(self, cond: Expr, *stmts: Stmt) -> IfBranch:
        return IfBranch(condition=cond, body=list(stmts))

    def else_clause(self, *stmts: Stmt) -> ElseBranch:
        return ElseBranch(body=list(stmts))

    # ---- Function name -----------------------------------------------------------------

    def funcname(self, *parts: str | Param) -> list[str | Param]:
        return list(parts)

    def fname_part(self, part: str | Param) -> str | Param:
        return part

    def fname_word(self, token: Token) -> str:
        return str(token)

    def typed_param(self, name: Token, ptype: str) -> Param:
        # `:?` is the AnyDice wildcard, equivalent to a bare parameter. Normalize to
        # type=None at the AST level so downstream code only sees one form.
        return Param(name=str(name), type=None if ptype == "?" else str(ptype))

    def bare_param(self, name: Token) -> Param:
        return Param(name=str(name), type=None)

    def param_type(self, t: Token) -> str:
        return str(t)

    # ---- Expressions -------------------------------------------------------------------

    def binop(self, left: Expr, op: Token, right: Expr) -> BinOp:
        return BinOp(op=str(op), left=left, right=right)

    def dice_binop(self, n: Expr, faces: Expr) -> DiceBinOp:
        return DiceBinOp(n=n, faces=faces)

    def dice_unary(self, faces: Expr) -> DiceUnary:
        return DiceUnary(faces=faces)

    def hash_op(self, _tok: Token, expr: Expr) -> HashOp:
        return HashOp(expr=expr)

    def not_op(self, _tok: Token, expr: Expr) -> NotOp:
        return NotOp(expr=expr)

    def neg_op(self, _tok: Token, expr: Expr) -> NegOp:
        return NegOp(expr=expr)

    def pos_op(self, _tok: Token, expr: Expr) -> PosOp:
        return PosOp(expr=expr)

    def number(self, tok: Token) -> Number:
        return Number(value=int(tok))

    def var(self, tok: Token) -> Var:
        return Var(name=str(tok))

    def empty_seq(self) -> EmptySeq:
        return EmptySeq()

    def seq(self, elems: SeqExpr) -> SeqExpr:
        return elems

    def string(self, tok: Token) -> StringExpr:
        return _parse_string(str(tok))

    # ---- Sequences ---------------------------------------------------------------------

    def seq_elems(self, *elems: SeqElem) -> SeqExpr:
        return SeqExpr(elems=list(elems))

    def range(self, start: Expr, stop: Expr) -> RangeElem:
        return RangeElem(start=start, stop=stop)

    def range_repeat(self, start: Expr, stop: Expr, repeat: Expr) -> RangeRepeatElem:
        return RangeRepeatElem(start=start, stop=stop, repeat=repeat)

    def value(self, expr: Expr) -> ValueElem:
        return ValueElem(expr=expr)

    def value_repeat(self, expr: Expr, repeat: Expr) -> ValueRepeatElem:
        return ValueRepeatElem(expr=expr, repeat=repeat)

    # ---- Function calls ----------------------------------------------------------------

    def call(self, call_expr: Call) -> Call:
        return call_expr

    def call_expr(self, *parts: str | Expr) -> Call:
        return Call(parts=list(parts))

    def call_word(self, token: Token) -> str:
        return str(token)

    def call_arg(self, expr: Expr) -> Expr:
        return expr
