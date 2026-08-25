"""Run the public offline validation command for one portable bundle."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run(argv: list[str] | None = None) -> int:
    """Delegate exactly one bundle-root argument to the public CLI command."""
    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) != 1:
        print("usage: validate_bundle.py bundle-root", file=sys.stderr)
        return 2
    sys.path.insert(0, str(PROJECT_ROOT / "src"))
    from agent_skillopt.cli import main

    return main(["validate", "--path", arguments[0]])


if __name__ == "__main__":
    raise SystemExit(run())
