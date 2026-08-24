"""Render and explicitly execute confirmation-gated host installation plans."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import cast

from agent_skillopt.errors import ConfirmationError, SpecError
from agent_skillopt.models import HostName, InstallPlan
from agent_skillopt.naming import normalize_skill_name
from agent_skillopt.validation import assert_valid_bundle

_SUPPORTED_HOSTS = frozenset(("codex", "claude", "hermes", "openclaw"))


def build_install_plan(host: str, bundle_root: Path, source: str | None) -> InstallPlan:
    """Render one validated, argv-safe host installation plan without executing it."""
    if host not in _SUPPORTED_HOSTS:
        raise SpecError("unsupported host")

    root = Path(bundle_root)
    name = _validated_bundle_name(root)
    selected_host = cast(HostName, host)
    if selected_host == "hermes":
        git_source = _required_git_source(source)
        steps = (
            ("hermes", "plugins", "install", git_source, "--no-enable"),
            ("hermes", "plugins", "enable", name),
        )
        network_required = True
    else:
        _reject_unneeded_source(source)
        steps = _local_host_steps(selected_host, root, name)
        network_required = False

    return InstallPlan(
        host=selected_host,
        steps=steps,
        confirmation_token=_confirmation_token(selected_host, steps, network_required),
        network_required=network_required,
    )


def execute_install(
    plan: InstallPlan, token: str, runner: Callable[[tuple[str, ...]], int]
) -> int:
    """Run the rendered argv tuples only after exact confirmation, stopping on failure."""
    if token != plan.confirmation_token:
        raise ConfirmationError("confirmation token is missing or stale.")

    for step in plan.steps:
        status = runner(step)
        if status != 0:
            return status
    return 0


def _validated_bundle_name(root: Path) -> str:
    """Return the package identity only after the formal bundle validator accepts it."""
    assert_valid_bundle(root)
    try:
        manifest = json.loads((root / "plugin.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SpecError("validated bundle identity cannot be read") from error
    if not isinstance(manifest, dict):
        raise SpecError("validated bundle identity is invalid")
    return normalize_skill_name(manifest.get("name"))


def _required_git_source(source: str | None) -> str:
    if (
        not isinstance(source, str)
        or not source
        or source != source.strip()
        or source.startswith("-")
        or any(character.isspace() for character in source)
    ):
        raise SpecError("--source is required and must name a Git source for Hermes.")
    if "\x00" in source:
        raise SpecError("--source must name a Git source for Hermes.")
    return source


def _reject_unneeded_source(source: str | None) -> None:
    if source is not None:
        raise SpecError("--source is only supported for Hermes installations.")


def _local_host_steps(host: HostName, root: Path, name: str) -> tuple[tuple[str, ...], ...]:
    if host == "codex":
        return (
            ("codex", "plugin", "marketplace", "add", str(root)),
            ("codex", "plugin", "add", f"{name}@{name}"),
        )
    if host == "claude":
        return (
            ("claude", "plugin", "marketplace", "add", str(root)),
            ("claude", "plugin", "install", f"{name}@{name}"),
        )
    if host == "openclaw":
        return (
            ("openclaw", "plugins", "install", str(root)),
            ("openclaw", "plugins", "inspect", name),
            ("openclaw", "gateway", "restart"),
        )
    raise SpecError("unsupported host")


def _confirmation_token(
    host: HostName, steps: tuple[tuple[str, ...], ...], network_required: bool
) -> str:
    payload = {
        "host": host,
        "network_required": network_required,
        "steps": steps,
    }
    canonical_json = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()[:16]
