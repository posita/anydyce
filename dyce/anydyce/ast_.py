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

from dataclasses import dataclass, field

__all__ = (
    "BinOp",
    "Call",
    "DiceBinOp",
    "DiceUnary",
    "ElseBranch",
    "EmptySeq",
    "Expr",
    "FunctionDef",
    "HashOp",
    "IfBranch",
    "IfStmt",
    "LoopStmt",
    "NegOp",
    "NotOp",
    "Number",
    "OutputStmt",
    "Param",
    "PosOp",
    "Program",
    "RangeElem",
    "RangeRepeatElem",
    "ResultStmt",
    "SeqElem",
    "SeqExpr",
    "SetStmt",
    "Stmt",
    "StrLit",
    "StrVar",
    "StringExpr",
    "ValueElem",
    "ValueRepeatElem",
    "Var",
    "VarAssign",
)

# ---- Expression nodes ------------------------------------------------------------------


@dataclass
class BinOp:
    op: str
    left: "Expr"
    right: "Expr"


@dataclass
class DiceBinOp:
    r"""n d m: roll n dice of m faces."""

    n: "Expr"
    faces: "Expr"


@dataclass
class DiceUnary:
    r"""d m: roll one die of m faces."""

    faces: "Expr"


@dataclass
class HashOp:
    r"""#expr: count / length."""

    expr: "Expr"


@dataclass
class NotOp:
    expr: "Expr"


@dataclass
class NegOp:
    expr: "Expr"


@dataclass
class PosOp:
    expr: "Expr"


@dataclass
class Number:
    value: int


@dataclass
class Var:
    name: str


@dataclass
class EmptySeq:
    pass


@dataclass
class RangeElem:
    start: "Expr"
    stop: "Expr"


@dataclass
class RangeRepeatElem:
    start: "Expr"
    stop: "Expr"
    repeat: "Expr"


@dataclass
class ValueElem:
    expr: "Expr"


@dataclass
class ValueRepeatElem:
    expr: "Expr"
    repeat: "Expr"


SeqElem = RangeElem | RangeRepeatElem | ValueElem | ValueRepeatElem


@dataclass
class SeqExpr:
    elems: list[SeqElem]


@dataclass
class StrLit:
    text: str


@dataclass
class StrVar:
    name: str


@dataclass
class StringExpr:
    parts: list[StrLit | StrVar]


@dataclass
class Call:
    r"""Function call: alternating words (str) and argument expressions (Expr)."""

    parts: "list[str | Expr]"


Expr = (
    BinOp
    | DiceBinOp
    | DiceUnary
    | HashOp
    | NotOp
    | NegOp
    | PosOp
    | Number
    | Var
    | EmptySeq
    | SeqExpr
    | StringExpr
    | Call
)

# ---- Statement nodes -------------------------------------------------------------------


@dataclass
class OutputStmt:
    expr: Expr
    name: "Expr | None" = None


@dataclass
class Param:
    name: str
    type: str | None  # 'n', 'd', 's', or None


@dataclass
class FunctionDef:
    r"""Pattern is a list of words (str) and parameters (Param)."""

    pattern: list[str | Param]
    body: "list[Stmt]"


@dataclass
class LoopStmt:
    var: str
    over: Expr
    body: "list[Stmt]"


@dataclass
class IfBranch:
    condition: Expr
    body: "list[Stmt]"


@dataclass
class ElseBranch:
    body: "list[Stmt]"


@dataclass
class IfStmt:
    branches: list[IfBranch]
    else_branch: ElseBranch | None = None


@dataclass
class SetStmt:
    key: str
    value: Expr


@dataclass
class ResultStmt:
    expr: Expr


@dataclass
class VarAssign:
    name: str
    expr: Expr


Stmt = OutputStmt | FunctionDef | LoopStmt | IfStmt | SetStmt | ResultStmt | VarAssign


@dataclass
class Program:
    stmts: "list[Stmt]" = field(default_factory=list)
