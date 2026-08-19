"""Atomic, redacted run-manifest persistence."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from agent_skillopt import __version__
from agent_skillopt.models import ProjectConfig

if TYPE_CHECKING:
    from agent_skillopt.invocation import RenderedInvocation


def create_manifest(invocation: RenderedInvocation, config: ProjectConfig, status: str) -> Path:
    """Create a run directory and atomically write its initial redacted manifest."""
    if status != "started":
        raise ValueError("A new manifest must begin with status 'started'")

    invocation.run_directory.mkdir(parents=True, exist_ok=False)
    manifest_path = invocation.run_directory / "manifest.json"
    payload = {
        "schema_version": 1,
        "agent_skillopt": {"version": __version__},
        "status": status,
        "timestamps": {
            "started_at": _timestamp(invocation.started_at),
            "finished_at": None,
        },
        "config": {
            "path": str(invocation.config_path),
            "sha256": _sha256_file(invocation.config_path),
        },
        "upstream": {
            "root": str(config.skillopt.root),
            "required_ref": config.skillopt.required_ref,
            "revision": _git_revision(config.skillopt.root),
        },
        "provider": {
            "base_url_host": urlsplit(config.provider.base_url).hostname,
            "model": config.provider.model,
        },
        "data": {
            "task": config.data.task,
            "path": str(config.data.path),
            "sha256": _sha256_file(config.data.path) if config.data.path.is_file() else None,
        },
        "run": {
            "directory": str(invocation.run_directory),
            "seed": config.run.seed,
        },
        "command": list(invocation.command),
    }
    _atomic_write_json(manifest_path, payload)
    return manifest_path


def update_manifest_status(
    invocation: RenderedInvocation, status: str, exit_code: int | None
) -> Path:
    """Atomically record the terminal status of a previously started run."""
    if status not in {"succeeded", "failed"}:
        raise ValueError("A terminal manifest status must be succeeded or failed")

    manifest_path = invocation.run_directory / "manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["status"] = status
    payload["exit_code"] = exit_code
    payload["timestamps"]["finished_at"] = _timestamp(datetime.now(timezone.utc))
    _atomic_write_json(manifest_path, payload)
    return manifest_path


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        text=True,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_revision(root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            check=False,
            text=True,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    revision = result.stdout.strip()
    return revision or None


def _timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
