"""Run the repository's offline Skill-package CLI from an installed Skill path."""

import importlib
import os
import sys
from pathlib import Path


def main() -> int:
    """Load only this repository's source tree and delegate CLI argument handling."""
    repository_root = Path(__file__).resolve().parents[3]
    source_root = (repository_root / "src").resolve()
    source_root_text = str(source_root)
    sys.path[:] = [entry for entry in sys.path if entry != source_root_text]
    sys.path.insert(0, source_root_text)
    _remove_external_agent_skillopt_modules(source_root)
    importlib.invalidate_caches()

    from agent_skillopt.cli import main as cli_main

    return cli_main()


def _remove_external_agent_skillopt_modules(source_root: Path) -> None:
    """Discard stale package cache entries that cannot be trusted to be this checkout."""
    for name, module in tuple(sys.modules.items()):
        if name == "agent_skillopt" or name.startswith("agent_skillopt."):
            if not _module_origin_is_within(module, source_root):
                del sys.modules[name]


def _module_origin_is_within(module: object, source_root: Path) -> bool:
    """Accept cache entries only when every available origin is a readable file below src."""
    specification = getattr(module, "__spec__", None)
    origins = (getattr(module, "__file__", None), getattr(specification, "origin", None))
    known_origins = [origin for origin in origins if origin is not None]
    if not known_origins:
        return False
    return all(_origin_is_within(origin, source_root) for origin in known_origins)


def _origin_is_within(origin: object, source_root: Path) -> bool:
    if not isinstance(origin, str) or not origin:
        return False
    origin_path = Path(origin)
    if not origin_path.is_absolute():
        return False
    try:
        resolved_origin = origin_path.resolve(strict=True)
        return resolved_origin.is_file() and os.access(resolved_origin, os.R_OK) and (
            resolved_origin.is_relative_to(source_root)
        )
    except (OSError, RuntimeError):
        return False


if __name__ == "__main__":
    raise SystemExit(main())
