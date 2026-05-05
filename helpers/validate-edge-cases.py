#!/usr/bin/env python3
# ======================================================================================
# Copyright and other protections apply. Please see the accompanying LICENSE file for
# rights and restrictions governing use of this software. All rights not expressly
# waived or licensed are reserved. If that file is missing or appears to be modified
# from its original, then please contact the author before viewing or using this
# software in any capacity.
# ======================================================================================

"""Link and compute AnyDice outputs for every program in test_interpreter.py.

Extracts the first string argument of every run() call that is not inside a
pytest.raises() context, then links each unique program to AnyDice and computes
any missing outputs.
"""

import ast
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
_TEST_FILE = _ROOT / "tests" / "anydyce" / "test_interpreter.py"
_HELPER = str(Path(__file__).parent / "anydice-programs.py")


def _in_raises(_node: ast.AST, parents: list[ast.AST]) -> bool:
    for parent in reversed(parents):
        if isinstance(parent, ast.withitem):
            continue
        if isinstance(parent, ast.With):
            for item in parent.items:
                call = item.context_expr
                if (
                    isinstance(call, ast.Call)
                    and isinstance(call.func, ast.Attribute)
                    and call.func.attr == "raises"
                ):
                    return True
            break
    return False


def _extract_programs(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf_8"))
    programs: list[str] = []
    seen: set[str] = set()

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self._parents: list[ast.AST] = []

        def generic_visit(self, node: ast.AST) -> None:
            self._parents.append(node)
            super().generic_visit(node)
            self._parents.pop()

        def visit_Call(self, node: ast.Call) -> None:
            func = node.func
            is_run = (isinstance(func, ast.Name) and func.id == "run") or (
                isinstance(func, ast.Attribute) and func.attr == "run"
            )
            if (
                is_run
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
                and not _in_raises(node, self._parents)
            ):
                program = node.args[0].value
                if program not in seen:
                    seen.add(program)
                    programs.append(program)
            self.generic_visit(node)

    Visitor().visit(tree)
    return programs


def main() -> None:
    programs = _extract_programs(_TEST_FILE)
    print(f"found {len(programs)} unique programs", file=sys.stderr)
    result = subprocess.run(
        [sys.executable, _HELPER, "link", *programs],
        check=False,
    )
    if result.returncode:
        sys.exit(result.returncode)
    subprocess.run(
        [sys.executable, _HELPER, "compute", "--all"],
        check=False,
    )


if __name__ == "__main__":
    main()
