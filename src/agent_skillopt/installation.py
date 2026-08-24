"""Render and explicitly execute confirmation-gated host installation plans."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from collections.abc import Callable
from pathlib import Path
from typing import cast

from agent_skillopt.errors import AgentSkillOptError, ConfirmationError, SpecError
from agent_skillopt.models import HostName, InstallPlan
from agent_skillopt.naming import normalize_skill_name
from agent_skillopt.validation import assert_valid_bundle

_SUPPORTED_HOSTS = frozenset(("codex", "claude", "hermes", "openclaw"))
_WINDOWS_CMD_UNSAFE_CHARACTERS = frozenset("&|<>()^%!\"'")
_FILE_ATTRIBUTE_REPARSE_POINT = 0x0400


def build_install_plan(host: str, bundle_root: Path, source: str | None) -> InstallPlan:
    """Render one validated, argv-safe host installation plan without executing it."""
    if host not in _SUPPORTED_HOSTS:
        raise SpecError("unsupported host")

    selected_host = cast(HostName, host)
    if selected_host == "hermes":
        git_source = _required_git_source(source)
    else:
        _reject_unneeded_source(source)
        git_source = None

    direct_root = Path(bundle_root)
    _assert_safe_command_argument(str(direct_root), "bundle root")
    root, name, fingerprint, root_identity = _validated_bundle_snapshot(direct_root)
    root_argument = _assert_safe_command_argument(str(root), "bundle root")
    name = _assert_safe_command_argument(name, "bundle name")
    if selected_host == "hermes":
        steps = (
            ("hermes", "plugins", "install", git_source, "--no-enable"),
            ("hermes", "plugins", "enable", name),
        )
        network_required = True
    else:
        steps = _local_host_steps(selected_host, root_argument, name)
        network_required = False

    _assert_safe_plan_arguments(steps)
    return InstallPlan(
        host=selected_host,
        steps=steps,
        confirmation_token=_confirmation_token(
            selected_host, root, fingerprint, root_identity, steps, network_required
        ),
        network_required=network_required,
        bundle_root=root,
        bundle_fingerprint=fingerprint,
        bundle_root_identity=root_identity,
    )


def execute_install(
    plan: InstallPlan, token: str, runner: Callable[[tuple[str, ...]], int]
) -> int:
    """Run rendered argv tuples only after exact and still-current confirmation."""
    if token != plan.confirmation_token:
        raise ConfirmationError("confirmation token is missing or stale.")

    _assert_plan_is_current(plan)
    for step in plan.steps:
        status = runner(step)
        if status != 0:
            return status
    return 0


def _validated_bundle_snapshot(root: Path) -> tuple[Path, str, str, tuple[int, int]]:
    """Validate a direct root, canonicalize it, and return its checked content snapshot."""
    direct_root = Path(root)
    assert_valid_bundle(direct_root)
    try:
        canonical_root = direct_root.resolve(strict=True)
    except OSError as error:
        raise SpecError("validated bundle root cannot be resolved") from error
    assert_valid_bundle(canonical_root)
    name = _read_validated_bundle_name(canonical_root)
    fingerprint = _bundle_fingerprint(canonical_root)
    root_identity = _bundle_root_identity(canonical_root)
    return canonical_root, name, fingerprint, root_identity


def _assert_plan_is_current(plan: InstallPlan) -> None:
    """Fail closed if a rendered local bundle no longer denotes the approved tree."""
    try:
        _assert_safe_command_argument(str(plan.bundle_root), "bundle root")
        _assert_safe_plan_arguments(plan.steps)
        root, _name, fingerprint, root_identity = _validated_bundle_snapshot(plan.bundle_root)
    except (AgentSkillOptError, OSError, ValueError) as error:
        raise ConfirmationError("installation plan is stale.") from error
    if (
        root != plan.bundle_root
        or fingerprint != plan.bundle_fingerprint
        or root_identity != plan.bundle_root_identity
    ):
        raise ConfirmationError("installation plan is stale.")


def _read_validated_bundle_name(root: Path) -> str:
    """Read package identity only after the formal validator accepted this root."""
    try:
        manifest = json.loads((root / "plugin.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SpecError("validated bundle identity cannot be read") from error
    if not isinstance(manifest, dict):
        raise SpecError("validated bundle identity is invalid")
    return normalize_skill_name(manifest.get("name"))


def _bundle_fingerprint(root: Path) -> str:
    """Hash the fully validated local tree with sorted paths and bounded binary reads."""
    digest = hashlib.sha256()
    _assert_safe_directory(root)

    def raise_walk_error(error: OSError) -> None:
        raise SpecError("validated bundle cannot be fingerprinted") from error

    try:
        walk = os.walk(root, followlinks=False, onerror=raise_walk_error)
        for directory, directories, filenames in walk:
            current = Path(directory)
            _assert_safe_directory(current)
            directories.sort()
            filenames.sort()
            relative_directory = current.relative_to(root).as_posix()
            _update_fingerprint_value(digest, b"D", relative_directory.encode("utf-8"))
            for directory_name in directories:
                _assert_safe_directory(current / directory_name)
            for filename in filenames:
                _update_fingerprint_file(digest, root, current / filename)
    except (OSError, UnicodeError, ValueError) as error:
        raise SpecError("validated bundle cannot be fingerprinted") from error
    return digest.hexdigest()


def _update_fingerprint_file(digest: object, root: Path, path: Path) -> None:
    _assert_safe_regular_file(path)
    relative_path = path.relative_to(root).as_posix()
    _update_fingerprint_value(digest, b"F", relative_path.encode("utf-8"))
    try:
        with path.open("rb") as file:
            while chunk := file.read(64 * 1024):
                _update_fingerprint_value(digest, b"C", chunk)
    except OSError as error:
        raise SpecError("validated bundle cannot be fingerprinted") from error


def _update_fingerprint_value(digest: object, marker: bytes, value: bytes) -> None:
    digest.update(marker)
    digest.update(len(value).to_bytes(8, "big"))
    digest.update(value)


def _bundle_root_identity(root: Path) -> tuple[int, int]:
    info = _safe_lstat(root)
    if not stat.S_ISDIR(info.st_mode) or _is_reparse_point(info):
        raise SpecError("validated bundle root is no longer a directory")
    return (int(info.st_dev), int(info.st_ino))


def _assert_safe_directory(path: Path) -> None:
    info = _safe_lstat(path)
    if not stat.S_ISDIR(info.st_mode) or _is_reparse_point(info):
        raise SpecError("validated bundle contains an unsafe directory")


def _assert_safe_regular_file(path: Path) -> None:
    info = _safe_lstat(path)
    if not stat.S_ISREG(info.st_mode) or _is_reparse_point(info):
        raise SpecError("validated bundle contains an unsafe file")


def _safe_lstat(path: Path) -> os.stat_result:
    try:
        info = path.lstat()
    except OSError as error:
        raise SpecError("validated bundle entry cannot be inspected") from error
    if stat.S_ISLNK(info.st_mode):
        raise SpecError("validated bundle contains a link")
    return info


def _is_reparse_point(info: os.stat_result) -> bool:
    return bool(getattr(info, "st_file_attributes", 0) & _FILE_ATTRIBUTE_REPARSE_POINT)


def _required_git_source(source: str | None) -> str:
    if not isinstance(source, str) or not source:
        raise SpecError("--source is required and must name a Git source for Hermes.")
    source = _assert_safe_command_argument(source, "Hermes source")
    if source != source.strip() or source.startswith("-") or any(
        character.isspace() for character in source
    ):
        raise SpecError("--source is required and must name a Git source for Hermes.")
    return source


def _reject_unneeded_source(source: str | None) -> None:
    if source is not None:
        raise SpecError("--source is only supported for Hermes installations.")


def _assert_safe_command_argument(value: str, field: str) -> str:
    """Reject values CMD can reinterpret if a host executable is a batch wrapper."""
    if not isinstance(value, str) or not value or any(
        character in _WINDOWS_CMD_UNSAFE_CHARACTERS or ord(character) < 32 or ord(character) == 127
        for character in value
    ):
        raise SpecError(f"{field} contains unsafe command characters.")
    return value


def _assert_safe_plan_arguments(steps: tuple[tuple[str, ...], ...]) -> None:
    for step in steps:
        for argument in step:
            _assert_safe_command_argument(argument, "installation argument")


def _local_host_steps(
    host: HostName, root_argument: str, name: str
) -> tuple[tuple[str, ...], ...]:
    if host == "codex":
        plugin_reference = _assert_safe_command_argument(f"{name}@{name}", "plugin reference")
        return (
            ("codex", "plugin", "marketplace", "add", root_argument),
            ("codex", "plugin", "add", plugin_reference),
        )
    if host == "claude":
        plugin_reference = _assert_safe_command_argument(f"{name}@{name}", "plugin reference")
        return (
            ("claude", "plugin", "marketplace", "add", root_argument),
            ("claude", "plugin", "install", plugin_reference),
        )
    if host == "openclaw":
        return (
            ("openclaw", "plugins", "install", root_argument),
            ("openclaw", "plugins", "inspect", name),
            ("openclaw", "gateway", "restart"),
        )
    raise SpecError("unsupported host")


def _confirmation_token(
    host: HostName,
    root: Path,
    fingerprint: str,
    root_identity: tuple[int, int],
    steps: tuple[tuple[str, ...], ...],
    network_required: bool,
) -> str:
    payload = {
        "bundle_fingerprint": fingerprint,
        "bundle_root": str(root),
        "bundle_root_identity": root_identity,
        "host": host,
        "network_required": network_required,
        "steps": steps,
    }
    canonical_json = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()[:16]
