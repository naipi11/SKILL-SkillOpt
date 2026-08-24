"""Run the repository's offline Skill-package CLI from an installed Skill path."""

import importlib
import sys
from pathlib import Path


def main() -> int:
    """Load only this repository's source tree and delegate CLI argument handling."""
    repository_root = Path(__file__).resolve().parents[3]
    source_root = (repository_root / "src").resolve()
    source_root_text = str(source_root)
    sys.path[:] = [entry for entry in sys.path if entry != source_root_text]
    sys.path.insert(0, source_root_text)
    _remove_cached_agent_skillopt_modules()
    importlib.invalidate_caches()

    from agent_skillopt.cli import main as cli_main

    return cli_main()


def _remove_cached_agent_skillopt_modules() -> None:
    """Force a fresh import from this wrapper's source root in this subprocess only."""
    for name in tuple(sys.modules):
        if name == "agent_skillopt" or name.startswith("agent_skillopt."):
            del sys.modules[name]


if __name__ == "__main__":
    raise SystemExit(main())
