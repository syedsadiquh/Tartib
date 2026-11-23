"""The installed distribution imports and reports a version (F-02)."""

from __future__ import annotations

from scheduler import __version__


def test_version_is_declared() -> None:
    assert __version__ == "0.1.0"


def test_package_imports_from_src_layout() -> None:
    import scheduler

    assert scheduler.__file__ is not None
    assert scheduler.__file__.endswith("scheduler/__init__.py")
