"""Architecture guards (01-architecture §3).

These tests fail the build when layering rules are broken. Never weaken them:
the engine's purity is what makes plans reproducible.
"""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "scheduler"

#: 03-engine §3 — the complete import surface of the pure engine.
ENGINE_STDLIB_ALLOWED = {
    "__future__",
    "bisect",
    "collections",
    "dataclasses",
    "datetime",
    "enum",
    "functools",
    "hashlib",
    "heapq",
    "itertools",
    "math",
    "typing",
    "uuid",
    "zoneinfo",
}

#: Wall-clock reads are only legal in clock.py.
WALL_CLOCK_NAMES = {"now", "utcnow", "today"}
WALL_CLOCK_CALLERS = {"datetime", "date", "time"}


def _py_files(package: str) -> list[Path]:
    return sorted((SRC / package).rglob("*.py"))


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _top_level_imports(tree: ast.Module) -> list[str]:
    """Every absolute import target a module pulls in."""
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative import: stays inside the package
                continue
            if node.module:
                found.append(node.module)
    return found


def test_engine_imports_only_allowlisted_stdlib() -> None:
    offenders: list[str] = []
    files = _py_files("engine")
    assert files, "engine package is missing"
    for path in files:
        for target in _top_level_imports(_parse(path)):
            if target.split(".")[0] in ENGINE_STDLIB_ALLOWED:
                continue
            if target == "scheduler.engine" or target.startswith("scheduler.engine."):
                continue
            offenders.append(f"{path.relative_to(SRC.parent.parent)}: {target}")
    assert not offenders, "engine must not import outside its allow-list:\n" + "\n".join(offenders)


def test_engine_never_reads_the_wall_clock() -> None:
    offenders: list[str] = []
    for path in _py_files("engine"):
        for node in ast.walk(_parse(path)):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Attribute) or func.attr not in WALL_CLOCK_NAMES:
                continue
            owner = func.value
            if isinstance(owner, ast.Name) and owner.id in WALL_CLOCK_CALLERS:
                offenders.append(f"{path}:{node.lineno}: {owner.id}.{func.attr}()")
    assert not offenders, "engine must not read wall time:\n" + "\n".join(offenders)


def test_only_clock_module_reads_wall_time() -> None:
    offenders: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        if path.name == "clock.py":
            continue
        for node in ast.walk(_parse(path)):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Attribute) or func.attr not in WALL_CLOCK_NAMES:
                continue
            owner = func.value
            if isinstance(owner, ast.Name) and owner.id in WALL_CLOCK_CALLERS:
                offenders.append(f"{path}:{node.lineno}: {owner.id}.{func.attr}()")
    assert not offenders, "read time through scheduler.clock.now():\n" + "\n".join(offenders)


def test_routers_do_not_import_models_or_integrations() -> None:
    offenders: list[str] = []
    for path in _py_files("api/routers"):
        for target in _top_level_imports(_parse(path)):
            if target.startswith(("scheduler.models", "scheduler.integrations")):
                offenders.append(f"{path}: {target}")
    assert not offenders, "routers must go through services:\n" + "\n".join(offenders)


def test_services_do_not_import_api() -> None:
    offenders: list[str] = []
    for path in _py_files("services"):
        for target in _top_level_imports(_parse(path)):
            if target.startswith("scheduler.api"):
                offenders.append(f"{path}: {target}")
    assert not offenders, "services must not depend on the HTTP layer:\n" + "\n".join(offenders)
