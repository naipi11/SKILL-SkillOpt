"""Run the repository's offline Skill-package CLI from an installed Skill path."""

import sys
from pathlib import Path


def main() -> int:
    """Load only this repository's source tree and delegate CLI argument handling."""
    repository_root = Path(__file__).resolve().parents[3]
    source_root = repository_root / "src"
    source_root_text = str(source_root)
    if source_root_text not in sys.path:
        sys.path.insert(0, source_root_text)

    from agent_skillopt.cli import main as cli_main

    return cli_main()


if __name__ == "__main__":
    raise SystemExit(main())
