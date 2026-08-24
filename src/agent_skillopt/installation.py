"""Render and explicitly execute confirmation-gated host installation plans."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

from agent_skillopt.errors import AgentSkillOptError, ConfirmationError, SpecError
from agent_skillopt.models import HostName, InstallPlan
from agent_skillopt.naming import normalize_skill_name
from agent_skillopt.validation import assert_valid_bundle

_SUPPORTED_HOSTS = frozenset(("codex", "claude", "hermes", "openclaw"))
_WINDOWS_CMD_UNSAFE_CHARACTERS = frozenset("&|<>()^%!\"'")
_FILE_ATTRIBUTE_REPARSE_POINT = 0x0400
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_BINARY = getattr(os, "O_BINARY", 0)


class _Digest(Protocol):
    """The small hashlib interface used by the deterministic fingerprint."""

    def update(self, data: bytes) -> object: ...


@dataclass(frozen=True, slots=True)
class _EntryState:
    """No-follow filesystem metadata used to prove one observed entry stayed stable."""

    device: int
    inode: int
    mode: int
    size: int
    mtime_ns: int
    ctime_ns: int


@dataclass(frozen=True, slots=True)
class _BundleSnapshot:
    """One coherent local bundle state captured without executing its contents."""

    root: Path
    name: str
    fingerprint: str
    root_identity: tuple[int, int]


def build_install_plan(host: str, bundle_root: Path, source: str | None) -> InstallPlan:
    """Render one validated, argv-safe host installation plan without executing it."""
    if host not in _SUPPORTED_HOSTS:
        raise SpecError("unsupported host")

    selected_host = cast(HostName, host)
    selected_source = _validated_source(selected_host, source)
    direct_root = Path(bundle_root)
    _assert_safe_command_argument(str(direct_root), "bundle root")
    snapshot = _validated_bundle_snapshot(direct_root)
    return _render_install_plan(selected_host, snapshot, selected_source)


def execute_install(
    plan: InstallPlan, token: str, runner: Callable[[tuple[str, ...]], int]
) -> int:
    """Execute only a freshly reconstructed equivalent of the approved plan."""
    if token != plan.confirmation_token:
        raise ConfirmationError("confirmation token is missing or stale.")

    try:
        expected = build_install_plan(plan.host, plan.bundle_root, plan.source)
    except (AgentSkillOptError, OSError, TypeError, ValueError) as error:
        raise ConfirmationError("installation plan is stale.") from error
    if plan != expected:
        raise ConfirmationError("installation plan is stale.")

    for step in expected.steps:
        status = runner(step)
        if status != 0:
            return status
    return 0


def _render_install_plan(
    host: HostName, snapshot: _BundleSnapshot, source: str | None
) -> InstallPlan:
    """Construct the exact host tuple sequence from one trusted local snapshot."""
    root_argument = _assert_safe_command_argument(str(snapshot.root), "bundle root")
    name = _assert_safe_command_argument(snapshot.name, "bundle name")
    if host == "hermes":
        if source is None:
            raise SpecError("--source is required and must name a Git source for Hermes.")
        steps = (
            ("hermes", "plugins", "install", source, "--no-enable"),
            ("hermes", "plugins", "enable", name),
        )
        network_required = True
    else:
        if source is not None:
            raise SpecError("--source is only supported for Hermes installations.")
        steps = _local_host_steps(host, root_argument, name)
        network_required = False

    _assert_safe_plan_arguments(steps)
    return InstallPlan(
        host=host,
        steps=steps,
        confirmation_token=_confirmation_token(host, snapshot, source, steps, network_required),
        network_required=network_required,
        bundle_root=snapshot.root,
        bundle_fingerprint=snapshot.fingerprint,
        bundle_root_identity=snapshot.root_identity,
        bundle_name=name,
        source=source,
    )


def _validated_bundle_snapshot(root: Path) -> _BundleSnapshot:
    """Capture a stable, formally validated root without mixing observed filesystem states."""
    direct_root = Path(root)
    direct_before = _directory_state(direct_root)
    assert_valid_bundle(direct_root)
    _assert_same_state(direct_before, _directory_state(direct_root))
    try:
        canonical_root = direct_root.resolve(strict=True)
    except OSError as error:
        raise SpecError("validated bundle root cannot be resolved") from error
    _assert_same_state(direct_before, _directory_state(direct_root))

    canonical_before = _directory_state(canonical_root)
    assert_valid_bundle(canonical_root)
    _assert_same_state(canonical_before, _directory_state(canonical_root))
    name, identity_state = _read_validated_bundle_name(canonical_root)
    fingerprint, observations = _bundle_fingerprint(canonical_root)
    observed_identity = observations.get(canonical_root / "plugin.json")
    if observed_identity is None:
        raise SpecError("validated bundle changed during snapshot capture")
    _assert_same_state(identity_state, observed_identity)
    _assert_same_state(canonical_before, _directory_state(canonical_root))
    assert_valid_bundle(canonical_root)
    _assert_same_state(canonical_before, _directory_state(canonical_root))
    _assert_same_state(direct_before, _directory_state(direct_root))
    return _BundleSnapshot(
        root=canonical_root,
        name=name,
        fingerprint=fingerprint,
        root_identity=(canonical_before.device, canonical_before.inode),
    )


def _read_validated_bundle_name(root: Path) -> tuple[str, _EntryState]:
    """Read the trusted identity through the same stable no-follow file protocol."""
    try:
        content, state = _read_stable_file(root / "plugin.json")
        manifest = json.loads(content.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SpecError("validated bundle identity cannot be read") from error
    if not isinstance(manifest, dict):
        raise SpecError("validated bundle identity is invalid")
    return normalize_skill_name(manifest.get("name")), state


def _bundle_fingerprint(root: Path) -> tuple[str, dict[Path, _EntryState]]:
    """Hash one stable, sorted local tree without following a link for file data."""
    digest = hashlib.sha256()
    observations: dict[Path, _EntryState] = {}
    try:
        for current, directories, filenames in _safe_walk(root):
            _record_observation(observations, current, _directory_state(current))
            _update_fingerprint_value(
                digest, b"D", current.relative_to(root).as_posix().encode("utf-8")
            )
            for directory_name in directories:
                child = current / directory_name
                _record_observation(observations, child, _directory_state(child))
            for filename in filenames:
                path = current / filename
                state = _update_fingerprint_file(digest, root, path)
                _record_observation(observations, path, state)
        if observations != _tree_observations(root):
            raise SpecError("validated bundle changed during snapshot capture")
    except (OSError, UnicodeError, ValueError) as error:
        raise SpecError("validated bundle cannot be fingerprinted") from error
    return digest.hexdigest(), observations


def _safe_walk(root: Path):
    """Yield sorted entries while rejecting any link, reparse point, or walk error."""

    def raise_walk_error(error: OSError) -> None:
        raise SpecError("validated bundle cannot be fingerprinted") from error

    walk = os.walk(root, topdown=True, followlinks=False, onerror=raise_walk_error)
    for directory, directories, filenames in walk:
        directories.sort()
        filenames.sort()
        yield Path(directory), directories, filenames


def _tree_observations(root: Path) -> dict[Path, _EntryState]:
    """Return a second no-data traversal used to reject additions, removals, and drift."""
    observations: dict[Path, _EntryState] = {}
    for current, directories, filenames in _safe_walk(root):
        _record_observation(observations, current, _directory_state(current))
        for directory_name in directories:
            child = current / directory_name
            _record_observation(observations, child, _directory_state(child))
        for filename in filenames:
            path = current / filename
            _record_observation(observations, path, _regular_file_state(path))
    return observations


def _record_observation(
    observations: dict[Path, _EntryState], path: Path, state: _EntryState
) -> None:
    previous = observations.setdefault(path, state)
    _assert_same_state(previous, state)


def _update_fingerprint_file(digest: _Digest, root: Path, path: Path) -> _EntryState:
    relative_path = path.relative_to(root).as_posix()
    _update_fingerprint_value(digest, b"F", relative_path.encode("utf-8"))

    def update_content(chunk: bytes) -> None:
        _update_fingerprint_value(digest, b"C", chunk)

    _content, state = _read_stable_file(path, update_content)
    return state


def _read_stable_file(
    path: Path, consume: Callable[[bytes], None] | None = None
) -> tuple[bytes, _EntryState]:
    """Open a regular file no-follow where supported, then prove it stayed the same."""
    before = _regular_file_state(path)
    try:
        descriptor = os.open(str(path), os.O_RDONLY | _BINARY | _NOFOLLOW)
    except OSError as error:
        raise SpecError("validated bundle file cannot be opened safely") from error
    try:
        opened = _regular_file_state_from_stat(os.fstat(descriptor))
        _assert_same_state(before, opened)
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 64 * 1024):
            if consume is None:
                chunks.append(chunk)
            else:
                consume(chunk)
        after_descriptor = _regular_file_state_from_stat(os.fstat(descriptor))
    except OSError as error:
        raise SpecError("validated bundle file cannot be read safely") from error
    finally:
        try:
            os.close(descriptor)
        except OSError as error:
            raise SpecError("validated bundle file cannot be closed safely") from error
    after_path = _regular_file_state(path)
    _assert_same_state(before, opened)
    _assert_same_state(before, after_descriptor)
    _assert_same_state(before, after_path)
    return b"".join(chunks) if consume is None else b"", before


def _update_fingerprint_value(digest: _Digest, marker: bytes, value: bytes) -> None:
    digest.update(marker)
    digest.update(len(value).to_bytes(8, "big"))
    digest.update(value)


def _directory_state(path: Path) -> _EntryState:
    info = _safe_lstat(path)
    if not stat.S_ISDIR(info.st_mode):
        raise SpecError("validated bundle contains an unsafe directory")
    return _entry_state(info)


def _regular_file_state(path: Path) -> _EntryState:
    return _regular_file_state_from_stat(_safe_lstat(path))


def _regular_file_state_from_stat(info: os.stat_result) -> _EntryState:
    if not stat.S_ISREG(info.st_mode) or _is_reparse_point(info):
        raise SpecError("validated bundle contains an unsafe file")
    return _entry_state(info)


def _safe_lstat(path: Path) -> os.stat_result:
    try:
        info = path.lstat()
    except OSError as error:
        raise SpecError("validated bundle entry cannot be inspected") from error
    if stat.S_ISLNK(info.st_mode) or _is_reparse_point(info):
        raise SpecError("validated bundle contains a link")
    return info


def _entry_state(info: os.stat_result) -> _EntryState:
    return _EntryState(
        device=int(info.st_dev),
        inode=int(info.st_ino),
        mode=int(info.st_mode),
        size=int(info.st_size),
        mtime_ns=int(info.st_mtime_ns),
        ctime_ns=int(info.st_ctime_ns),
    )


def _assert_same_state(expected: _EntryState, observed: _EntryState) -> None:
    if expected != observed:
        raise SpecError("validated bundle changed during snapshot capture")


def _is_reparse_point(info: os.stat_result) -> bool:
    return bool(getattr(info, "st_file_attributes", 0) & _FILE_ATTRIBUTE_REPARSE_POINT)


def _validated_source(host: HostName, source: str | None) -> str | None:
    if host == "hermes":
        return _required_git_source(source)
    if source is not None:
        raise SpecError("--source is only supported for Hermes installations.")
    return None


def _required_git_source(source: str | None) -> str:
    if not isinstance(source, str) or not source:
        raise SpecError("--source is required and must name a Git source for Hermes.")
    source = _assert_safe_command_argument(source, "Hermes source")
    if source != source.strip() or source.startswith("-") or any(
        character.isspace() for character in source
    ):
        raise SpecError("--source is required and must name a Git source for Hermes.")
    return source


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
    plugin_reference = _assert_safe_command_argument(f"{name}@{name}", "plugin reference")
    if host == "codex":
        return (
            ("codex", "plugin", "marketplace", "add", root_argument),
            ("codex", "plugin", "add", plugin_reference),
        )
    if host == "claude":
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
    snapshot: _BundleSnapshot,
    source: str | None,
    steps: tuple[tuple[str, ...], ...],
    network_required: bool,
) -> str:
    payload = {
        "bundle_fingerprint": snapshot.fingerprint,
        "bundle_name": snapshot.name,
        "bundle_root": str(snapshot.root),
        "bundle_root_identity": snapshot.root_identity,
        "host": host,
        "network_required": network_required,
        "source": source,
        "steps": steps,
    }
    canonical_json = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()[:16]
