"""``scheduler-cli`` entry point.

Commands are registered by the packages that own them; the console script and the
dispatcher exist from F-02 so ``make seed`` / ``make migrate``-style calls resolve to
a real executable.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scheduler-cli",
        description="Tartib maintenance CLI",
    )
    parser.add_argument("command", nargs="?", help="command to run (added by later packages)")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0
    parser.error(f"unknown command: {args.command}")
    return 2  # unreachable: parser.error exits


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
