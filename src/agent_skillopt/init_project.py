"""Non-destructive project initialization from packaged preset assets."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

_PRESETS = {"searchqa-deepseek": "searchqa-deepseek.yaml"}


def initialize_project(destination: Path, preset_name: str, force: bool) -> Path:
    """Write one project config and ensure generated run artifacts are ignored."""
    target_directory = Path(destination).resolve()
    target_directory.mkdir(parents=True, exist_ok=True)
    config_path = target_directory / "agent-skillopt.yaml"
    if config_path.exists() and not force:
        raise FileExistsError(f"Refusing to overwrite existing configuration: {config_path}")

    config_path.write_text(_preset_text(preset_name), encoding="utf-8")
    _ensure_runs_ignore(target_directory / ".gitignore")
    return config_path


def available_presets() -> tuple[str, ...]:
    """Return the stable list of shipped initialization preset names."""
    return tuple(_PRESETS)


def _preset_text(preset_name: str) -> str:
    try:
        filename = _PRESETS[preset_name]
    except KeyError as error:
        choices = ", ".join(available_presets())
        raise ValueError(f"Unknown preset {preset_name!r}; choose one of: {choices}") from error
    return (
        resources.files("agent_skillopt").joinpath("assets", filename).read_text(encoding="utf-8")
    )


def _ensure_runs_ignore(ignore_path: Path) -> None:
    if ignore_path.exists():
        existing = ignore_path.read_text(encoding="utf-8")
    else:
        existing = ""
    lines = existing.splitlines()
    if "runs/" in lines:
        return
    prefix = existing if not existing or existing.endswith("\n") else f"{existing}\n"
    ignore_path.write_text(f"{prefix}runs/\n", encoding="utf-8")
