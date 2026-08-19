"""Deterministic SkillOpt invocation rendering and live-execution gates."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from agent_skillopt.errors import ConfigurationError, ExecutionGateError
from agent_skillopt.models import ProjectConfig

Runner = Callable[[tuple[str, ...], Path, Mapping[str, str]], int]

_SENSITIVE_UPSTREAM_MARKERS = (
    "api-key",
    "apikey",
    "authorization",
    "password",
    "secret",
    "token",
)


@dataclass(frozen=True, slots=True)
class RenderedInvocation:
    """A safe, local launch contract with no credential value."""

    command: tuple[str, ...]
    child_environment: dict[str, str]
    working_directory: Path
    run_directory: Path
    config_path: Path
    started_at: datetime
    api_key_env: str
    config: ProjectConfig


def render_invocation(
    config: ProjectConfig, config_path: Path, now: datetime
) -> RenderedInvocation:
    """Render a local command without launching a process or reading a credential."""
    _validate_local_prerequisites(config)
    _validate_upstream_args(config.run.upstream_args)

    started_at = _as_utc(now)
    run_name = f"{config.data.task}-{started_at.strftime('%Y%m%dT%H%M%SZ')}"
    run_directory = config.run.output_root / run_name
    command = (
        sys.executable,
        str(config.skillopt.root / config.skillopt.entry_script),
        "--config",
        config.skillopt.upstream_config.as_posix(),
        "--optimizer_backend",
        "openai_compatible",
        "--target_backend",
        "openai_compatible",
        "--optimizer_model",
        config.provider.model,
        "--target_model",
        config.provider.model,
        "--data_path",
        str(config.data.path),
        "--out_root",
        str(run_directory),
        "--seed",
        str(config.run.seed),
        *config.run.upstream_args,
    )
    return RenderedInvocation(
        command=command,
        child_environment={
            "OPENAI_COMPATIBLE_BASE_URL": config.provider.base_url,
            "OPENAI_COMPATIBLE_MODEL": config.provider.model,
        },
        working_directory=config.skillopt.root,
        run_directory=run_directory,
        config_path=Path(config_path).resolve(),
        started_at=started_at,
        api_key_env=config.provider.api_key_env,
        config=config,
    )


def require_execution_permission(
    config: ProjectConfig, allow_network: bool, environ: Mapping[str, str]
) -> None:
    """Require explicit acknowledgement and a configured key before a live run."""
    if not allow_network:
        raise ExecutionGateError(
            "Live execution requires explicit --allow-network acknowledgement.",
            exit_code=3,
        )
    if not environ.get(config.provider.api_key_env):
        raise ExecutionGateError(
            f"Configured API key environment variable {config.provider.api_key_env} is not set.",
            exit_code=2,
        )


def execute(invocation: RenderedInvocation, runner: Runner) -> int:
    """Persist a redacted lifecycle manifest around one already-authorized child process."""
    from agent_skillopt.manifest import create_manifest, update_manifest_status

    api_key = os.environ.get(invocation.api_key_env)
    if not api_key:
        raise ExecutionGateError(
            f"Configured API key environment variable {invocation.api_key_env} is not set.",
            exit_code=2,
        )

    child_environment = dict(os.environ)
    child_environment.pop(invocation.api_key_env, None)
    child_environment.update(invocation.child_environment)
    child_environment["OPENAI_COMPATIBLE_API_KEY"] = api_key

    create_manifest(invocation, invocation.config, status="started")
    try:
        return_code = runner(invocation.command, invocation.working_directory, child_environment)
    except BaseException:
        update_manifest_status(invocation, "failed", exit_code=None)
        raise

    status = "succeeded" if return_code == 0 else "failed"
    update_manifest_status(invocation, status, exit_code=return_code)
    return return_code


def _validate_local_prerequisites(config: ProjectConfig) -> None:
    root = config.skillopt.root
    checks = (
        (root.is_dir(), "skillopt.root directory"),
        ((root / config.skillopt.entry_script).is_file(), "skillopt.entry_script"),
        ((root / config.skillopt.upstream_config).is_file(), "skillopt.upstream_config"),
        (
            (root / "skillopt" / "model" / "openai_compatible_backend.py").is_file(),
            "compatible upstream backend",
        ),
        (config.data.path.is_dir(), "data.path directory"),
    )
    for is_present, label in checks:
        if not is_present:
            raise ConfigurationError(f"Required local prerequisite is missing: {label}")


def _validate_upstream_args(arguments: tuple[str, ...]) -> None:
    for argument in arguments:
        normalized = argument.lstrip("-").lower().replace("_", "-")
        if any(marker in normalized for marker in _SENSITIVE_UPSTREAM_MARKERS):
            raise ConfigurationError(
                "run.upstream_args must not include credential-style arguments; "
                "use provider.api_key_env instead"
            )
        url_candidate = argument.partition("=")[2] or argument
        parsed = urlsplit(url_candidate)
        if parsed.scheme and parsed.query:
            raise ConfigurationError(
                "run.upstream_args must not include endpoint URLs with query parameters"
            )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
