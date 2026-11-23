#!/usr/bin/env python
"""Forbid hard-coded scheduling numbers (SET-0, ARCH §3).

Scans ``engine/`` and ``services/`` for integer literals used as
``timedelta(...)`` / ``time(...)`` arguments or assigned to names ending in
``_min`` / ``_sec`` / ``_minutes``.

Allowed: ``0``, ``1``, any value defined in ``scheduler/constants.py``, and lines
carrying ``# noqa: magic`` (with a reason on the same line).
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "scheduler"
SCANNED_PACKAGES = ("engine", "services")
DURATION_CALLS = {"timedelta", "time"}
DURATION_SUFFIXES = ("_min", "_sec", "_minutes")
ALLOWED_VALUES = {0, 1}
CONSTANTS_MODULE = SRC / "constants.py"


def _constants_values() -> set[int]:
    if not CONSTANTS_MODULE.exists():
        return set()
    tree = ast.parse(CONSTANTS_MODULE.read_text(encoding="utf-8"))
    values: set[int] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, int)
            and not isinstance(node.value, bool)
        ):
            values.add(node.value)
        elif isinstance(node, (ast.Tuple, ast.List)):
            values.update(
                elt.value
                for elt in node.elts
                if isinstance(elt, ast.Constant) and isinstance(elt.value, int)
            )
    return values


def _int_literals(node: ast.AST) -> list[ast.Constant]:
    found: list[ast.Constant] = []
    for child in ast.walk(node):
        if (
            isinstance(child, ast.Constant)
            and isinstance(child.value, int)
            and not isinstance(child.value, bool)
        ):
            found.append(child)
    return found


def _is_waived(lines: list[str], lineno: int) -> bool:
    return "noqa: magic" in lines[lineno - 1]


def scan(path: Path, allowed: set[int]) -> list[str]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    lines = source.splitlines()
    problems: list[str] = []

    def report(node: ast.AST, why: str) -> None:
        literal = next(
            (
                c
                for c in _int_literals(node)
                if c.value not in allowed and not _is_waived(lines, c.lineno)
            ),
            None,
        )
        if literal is not None:
            problems.append(f"{path}:{literal.lineno}: {literal.value} ({why})")

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
            if name in DURATION_CALLS:
                report(node, f"literal in {name}(...)")
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.endswith(DURATION_SUFFIXES):
                    report(node.value, f"literal assigned to {target.id}")

    return problems


def main() -> int:
    allowed = ALLOWED_VALUES | _constants_values()
    problems: list[str] = []
    scanned = 0
    for package in SCANNED_PACKAGES:
        root = SRC / package
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.py")):
            scanned += 1
            problems.extend(scan(path, allowed))

    if problems:
        print("Hard-coded scheduling numbers found (SET-0):", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        print(
            "Move the value into settings (seed/defaults.py) or scheduler/constants.py, "
            "or annotate the line with '# noqa: magic: <reason>'.",
            file=sys.stderr,
        )
        return 1

    print(f"check_no_magic_numbers: {scanned} file(s) clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
