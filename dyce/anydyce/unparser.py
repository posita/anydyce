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
AnyDice AST unparser: converts a parsed AST back to canonical source text.

Comments are not part of the AST, so the output is always comment-free.
The output is idempotent: `unparse(parse(unparse(parse(src)))) == unparse(parse(src))`.
"""

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

__all__ = ("unparse",)

# ---- Precedence ----------------------------------------------------------------------

# Numeric precedence levels matching the grammar (higher = tighter binding).
_PREC_OR = 1
_PREC_AND = 2
_PREC_CMP = 3
_PREC_ADD = 4
_PREC_MUL = 5
_PREC_POW = 6
_PREC_AT = 7
_PREC_DICE_BIN = 8
_PREC_UNARY = 9

_BINOP_PREC: dict[str, int] = {
    "|": _PREC_OR,
    "&": _PREC_AND,
    "=": _PREC_CMP,
    "!=": _PREC_CMP,
    "<": _PREC_CMP,
    ">": _PREC_CMP,
    "<=": _PREC_CMP,
    ">=": _PREC_CMP,
    "+": _PREC_ADD,
    "-": _PREC_ADD,
    "*": _PREC_MUL,
    "/": _PREC_MUL,
    "^": _PREC_POW,
    "@": _PREC_AT,
}

# ---- Public entry point --------------------------------------------------------------


def unparse(program: Program) -> str:
    r"""Convert a parsed [`Program`][dyce.anydyce.ast_.Program] to canonical source text."""
    return "\n".join(_stmt(s, 0) for s in program.stmts)


# ---- Statements ----------------------------------------------------------------------


def _stmt(node: Stmt, depth: int) -> str:
    pad = "    " * depth
    if isinstance(node, OutputStmt):
        if node.name is None:
            return f"{pad}output {_expr(node.expr)}"
        return f"{pad}output {_expr(node.expr)} named {_expr(node.name)}"
    elif isinstance(node, FunctionDef):
        pat = " ".join(_func_part(p) for p in node.pattern)
        return f"{pad}function: {pat} {_block(node.body, depth)}"
    elif isinstance(node, LoopStmt):
        return (
            f"{pad}loop {node.var} over {_expr(node.over)} {_block(node.body, depth)}"
        )
    elif isinstance(node, IfStmt):
        return _if_stmt(node.branches, node.else_branch, depth)
    elif isinstance(node, SetStmt):
        return f'{pad}set "{node.key}" to {_expr(node.value)}'
    elif isinstance(node, ResultStmt):
        return f"{pad}result: {_expr(node.expr)}"
    elif isinstance(node, VarAssign):
        return f"{pad}{node.name}: {_expr(node.expr)}"
    else:  # pragma: no cover
        raise NotImplementedError(f"unhandled stmt node: {node!r}")


def _block(stmts: list[Stmt], depth: int) -> str:
    pad = "    " * depth
    if not stmts:
        return "{}"
    body = "\n".join(_stmt(s, depth + 1) for s in stmts)
    return f"{{\n{body}\n{pad}}}"


def _if_stmt(
    branches: list[IfBranch], else_branch: ElseBranch | None, depth: int
) -> str:
    pad = "    " * depth
    first = branches[0]
    result = f"{pad}if {_expr(first.condition)} {_block(first.body, depth)}"
    for branch in branches[1:]:
        result += f" else if {_expr(branch.condition)} {_block(branch.body, depth)}"
    if else_branch is not None:
        result += f" else {_block(else_branch.body, depth)}"
    return result


def _func_part(part: str | Param) -> str:
    if isinstance(part, str):
        return part
    elif part.type is not None:
        return f"{part.name}:{part.type}"
    else:
        return part.name


# ---- Expressions ---------------------------------------------------------------------


def _expr(node: Expr, min_prec: int = 0) -> str:  # noqa: C901
    if isinstance(node, Number):
        return str(node.value)
    elif isinstance(node, Var):
        return node.name
    elif isinstance(node, EmptySeq):
        return "{}"
    elif isinstance(node, SeqExpr):
        return "{" + ", ".join(_seq_elem(e) for e in node.elems) + "}"
    elif isinstance(node, StringExpr):
        return '"' + "".join(_str_part(p) for p in node.parts) + '"'
    elif isinstance(node, BinOp):
        prec = _BINOP_PREC[node.op]
        # Right child uses prec+1 so that same-precedence right-side gets parens
        # (all binary ops are left-associative, so a-(b-c) != (a-b)-c).
        s = f"{_expr(node.left, prec)} {node.op} {_expr(node.right, prec + 1)}"
        return f"({s})" if prec < min_prec else s
    elif isinstance(node, DiceBinOp):
        faces_str = _expr(node.faces, _PREC_UNARY)
        # The lexer merges a leading "d" in the faces text with the preceding "d"
        # operator as a single LOWERNAME token (e.g. "dd6" is illegal). Wrap in
        # parens so "2d(d6)" is emitted instead of "2dd6".
        if faces_str.startswith("d"):
            faces_str = f"({faces_str})"
        s = f"{_expr(node.n, _PREC_DICE_BIN)}d{faces_str}"
        return f"({s})" if min_prec > _PREC_DICE_BIN else s
    elif isinstance(node, DiceUnary):
        faces_str = _expr(node.faces, _PREC_UNARY)
        # Same lexer hazard: "d" followed by another "d..." produces an illegal
        # LOWERNAME. Wrap to avoid "dd..." sequences.
        if faces_str.startswith("d"):
            faces_str = f"({faces_str})"
        s = f"d{faces_str}"
        return f"({s})" if min_prec > _PREC_UNARY else s
    elif isinstance(node, HashOp):
        s = f"#{_expr(node.expr, _PREC_UNARY)}"
        return f"({s})" if min_prec > _PREC_UNARY else s
    elif isinstance(node, NotOp):
        s = f"!{_expr(node.expr, _PREC_UNARY)}"
        return f"({s})" if min_prec > _PREC_UNARY else s
    elif isinstance(node, NegOp):
        s = f"-{_expr(node.expr, _PREC_UNARY)}"
        return f"({s})" if min_prec > _PREC_UNARY else s
    elif isinstance(node, PosOp):
        s = f"+{_expr(node.expr, _PREC_UNARY)}"
        return f"({s})" if min_prec > _PREC_UNARY else s
    elif isinstance(node, Call):
        inner = " ".join(p if isinstance(p, str) else _expr(p) for p in node.parts)
        return f"[{inner}]"
    else:  # pragma: no cover
        raise NotImplementedError(f"unhandled expr node: {node!r}")


# ---- Sequences -----------------------------------------------------------------------


def _seq_elem(node: SeqElem) -> str:
    if isinstance(node, RangeElem):
        return f"{_expr(node.start)}..{_expr(node.stop)}"
    elif isinstance(node, RangeRepeatElem):
        return f"{_expr(node.start)}..{_expr(node.stop)}:{_expr(node.repeat)}"
    elif isinstance(node, ValueElem):
        return _expr(node.expr)
    elif isinstance(node, ValueRepeatElem):
        return f"{_expr(node.expr)}:{_expr(node.repeat)}"
    else:  # pragma: no cover
        raise NotImplementedError(f"unhandled seq_elem node: {node!r}")


def _str_part(node: StrLit | StrVar) -> str:
    if isinstance(node, StrLit):
        return node.text
    elif isinstance(node, StrVar):
        return f"[{node.name}]"
    else:  # pragma: no cover
        raise NotImplementedError(f"unhandled str_part node: {node!r}")
