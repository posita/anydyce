#!/usr/bin/env python3
# ======================================================================================
# Copyright and other protections apply. Please see the accompanying LICENSE file for
# rights and restrictions governing use of this software. All rights not expressly
# waived or licensed are reserved. If that file is missing or appears to be modified
# from its original, then please contact the author before viewing or using this
# software in any capacity.
# ======================================================================================

"""Compare each test_interpreter.py expectation against AnyDice's actual output.

For every `assert run(<program>) == <expected>` in the test file, look up the
program in the AnyDice DB and compare. Mismatches are reported.

A "match" requires:
  - same number of distributions (outputs)
  - same labels (string compare)
  - same set of outcomes per distribution
  - count vectors are positive-scalar multiples of each other (i.e. same
    relative weights; absolute counts may differ by a constant factor)

`pytest.raises(...)` blocks and tests that don't follow the simple
`assert run(...) == [...]` shape are skipped and reported as such.
"""

import ast
import json
import sqlite3
import sys
from collections.abc import Iterator
from fractions import Fraction
from functools import reduce
from math import gcd
from pathlib import Path

_ROOT = Path(__file__).parent.parent
_TEST_FILE = _ROOT / "tests" / "anydyce" / "test_interpreter.py"
_DB = Path(__file__).parent / "anydice-programs.db"

sys.path.insert(0, str(_ROOT))
from dyce.anydyce import parse as anydyce_parse  # noqa: E402
from dyce.anydyce import unparse as anydyce_unparse  # noqa: E402


def _canonicalize(program: str) -> str:
    try:
        return anydyce_unparse(anydyce_parse(program))
    except Exception:  # noqa: BLE001
        return program


# ---- AnyDice output -> normalized (label, {outcome: count}) -------------------------


def _pct_to_counts(outcomes: list[list]) -> dict[int, int]:
    # AnyDice represents an empty distribution as [[null, null]].
    filtered = [(o, p) for o, p in outcomes if o is not None and p is not None]
    if not filtered:
        return {}
    fracs = [
        (int(o), Fraction(str(p)).limit_denominator(10**9) / 100) for o, p in filtered
    ]
    denom = reduce(lambda a, b: a * b // gcd(a, b), (f.denominator for _, f in fracs))
    return {o: int(f * denom) for o, f in fracs}


def _normalize_anydice(output_json: str) -> list[tuple[str, dict[int, int]]] | None:
    data = json.loads(output_json)
    if "error" in data:
        return None
    dists = data.get("distributions", {})
    dist_data = dists.get("data", [])
    labels = dists.get("labels", [])
    out: list[tuple[str, dict[int, int]]] = []
    for i, outcomes in enumerate(dist_data):
        label = labels[i] if i < len(labels) else f"output {i + 1}"
        out.append((label, _pct_to_counts(outcomes)))
    return out


# ---- Expected expression -> normalized (label, {outcome: count}) --------------------


def _eval_expected(node: ast.AST) -> list[tuple[str, dict[int, int]]]:
    """Evaluate the right-hand side of `assert run(...) == <expected>`."""
    # The expected expression is a list of (label, H(...)) tuples. We evaluate it
    # in a controlled namespace exposing H.
    src = ast.unparse(node)
    from dyce import H

    val = eval(src, {"H": H})  # noqa: S307
    result: list[tuple[str, dict[int, int]]] = []
    for label, h in val:
        result.append((label, dict(h)))
    return result


# ---- Match logic --------------------------------------------------------------------


def _proportional(a: dict[int, int], b: dict[int, int]) -> bool:
    if set(a) != set(b):
        return False
    if not a:
        return True
    total_a = sum(a.values())
    total_b = sum(b.values())
    if total_a == 0 or total_b == 0:
        return total_a == total_b
    # AnyDice's float-derived counts can drift by O(1) from the true ratio when
    # the recovered total is large. Compare normalized fractions with tolerance.
    for k in a:
        ratio_a = Fraction(a[k], total_a)
        ratio_b = Fraction(b[k], total_b)
        if abs(ratio_a - ratio_b) > Fraction(1, 10**9):
            return False
    return True


def _compare(
    expected: list[tuple[str, dict[int, int]]],
    actual: list[tuple[str, dict[int, int]]],
) -> str | None:
    if len(expected) != len(actual):
        return f"output count differs: expected {len(expected)}, AnyDice {len(actual)}"
    for i, ((el, ec), (al, ac)) in enumerate(zip(expected, actual, strict=True)):
        if el != al:
            return f"label[{i}] differs: expected {el!r}, AnyDice {al!r}"
        if not _proportional(ec, ac):
            return (
                f"distribution[{i}] ({el!r}) differs:\n"
                f"    expected: {dict(sorted(ec.items()))}\n"
                f"    AnyDice:  {dict(sorted(ac.items()))}"
            )
    return None


# ---- Test file walk -----------------------------------------------------------------


def _iter_assertions(path: Path) -> Iterator[tuple[str, str, ast.expr]]:
    """
    Yield (test_name, program_str, expected_node) for each simple `assert run(<str>) == <expr>` we can statically extract.
    """
    tree = ast.parse(path.read_text(encoding="utf_8"))
    for cls in ast.iter_child_nodes(tree):
        if not isinstance(cls, ast.ClassDef):
            continue
        for fn in cls.body:
            if not isinstance(fn, ast.FunctionDef):
                continue
            qualname = f"{cls.name}.{fn.name}"
            for stmt in ast.walk(fn):
                if not isinstance(stmt, ast.Assert):
                    continue
                test = stmt.test
                if not (
                    isinstance(test, ast.Compare)
                    and len(test.ops) == 1
                    and isinstance(test.ops[0], ast.Eq)
                ):
                    continue
                left = test.left
                if not (
                    isinstance(left, ast.Call)
                    and isinstance(left.func, ast.Name)
                    and left.func.id == "run"
                    and len(left.args) == 1
                    and isinstance(left.args[0], ast.Constant)
                    and isinstance(left.args[0].value, str)
                ):
                    continue
                program = left.args[0].value
                expected = test.comparators[0]
                yield qualname, program, expected


def main() -> None:
    conn = sqlite3.connect(_DB)
    canonical_to_output = dict(
        conn.execute("SELECT canonical, output FROM programs WHERE output IS NOT NULL")
    )
    conn.close()

    mismatches: list[tuple[str, str, str]] = []
    not_in_db: list[tuple[str, str]] = []
    no_output: list[tuple[str, str]] = []
    anydice_errors: list[tuple[str, str]] = []
    eval_errors: list[tuple[str, str, str]] = []
    matched = 0

    for qualname, program, expected_node in _iter_assertions(_TEST_FILE):
        canonical = _canonicalize(program)
        if canonical not in canonical_to_output:
            not_in_db.append((qualname, program))
            continue
        out_json = canonical_to_output[canonical]
        if out_json is None:
            no_output.append((qualname, program))
            continue
        actual = _normalize_anydice(out_json)
        if actual is None:
            anydice_errors.append((qualname, program))
            continue
        try:
            expected = _eval_expected(expected_node)
        except Exception as exc:  # noqa: BLE001
            eval_errors.append((qualname, program, f"{type(exc).__name__}: {exc}"))
            continue
        diff = _compare(expected, actual)
        if diff is None:
            matched += 1
        else:
            mismatches.append((qualname, program, diff))

    print(f"matched: {matched}")
    print(f"mismatches: {len(mismatches)}")
    print(f"not in DB: {len(not_in_db)}")
    print(f"no output yet: {len(no_output)}")
    print(f"AnyDice errors: {len(anydice_errors)}")
    print(f"eval errors: {len(eval_errors)}")

    if mismatches:
        print("\n==== MISMATCHES ====")
        for name, prog, diff in mismatches:
            print(f"\n{name}")
            print(f"  program: {prog!r}")
            print(f"  {diff}")

    if anydice_errors:
        print("\n==== ANYDICE ERRORS ====")
        for name, prog in anydice_errors:
            print(f"  {name}: {prog!r}")

    if not_in_db:
        print("\n==== NOT IN DB ====")
        for name, prog in not_in_db:
            print(f"  {name}: {prog!r}")

    if no_output:
        print("\n==== NO OUTPUT YET ====")
        for name, prog in no_output:
            print(f"  {name}: {prog!r}")

    if eval_errors:
        print("\n==== EVAL ERRORS ====")
        for name, prog, err in eval_errors:
            print(f"  {name}: {prog!r} -> {err}")


if __name__ == "__main__":
    main()
