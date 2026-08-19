"""Local, secret-safe diagnostics for a configured SkillOpt checkout."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path

from agent_skillopt.models import ProjectConfig


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """One actionable diagnostic result that is safe to serialize."""

    level: str
    code: str
    message: str
    remediation: str

    def to_dict(self) -> dict[str, str]:
        """Return the stable JSON representation used by the CLI."""
        return asdict(self)


def run_doctor(config: ProjectConfig, environ: Mapping[str, str]) -> list[Diagnostic]:
    """Inspect only local prerequisites and report every discoverable issue."""
    diagnostics = [
        Diagnostic(
            level="info",
            code="PYTHON_VERSION",
            message=f"Python {sys.version_info.major}.{sys.version_info.minor} is running.",
            remediation="Use Python 3.10 or newer.",
        )
    ]
    diagnostics.append(_provider_key_diagnostic(config, environ))
    diagnostics.extend(_checkout_diagnostics(config))
    diagnostics.append(_data_diagnostic(config))
    return diagnostics


def _provider_key_diagnostic(config: ProjectConfig, environ: Mapping[str, str]) -> Diagnostic:
    environment_name = config.provider.api_key_env
    if environ.get(environment_name):
        return Diagnostic(
            level="info",
            code="PROVIDER_API_KEY_SET",
            message=f"Environment variable {environment_name} is set.",
            remediation="The value is intentionally not displayed.",
        )
    return Diagnostic(
        level="warning",
        code="PROVIDER_API_KEY_MISSING",
        message=f"Environment variable {environment_name} is not set.",
        remediation=(
            "Set it only before an explicitly authorized live run; " + "dry-run does not need it."
        ),
    )


def _checkout_diagnostics(config: ProjectConfig) -> list[Diagnostic]:
    root = config.skillopt.root
    diagnostics = [_directory_diagnostic(root, "SKILLOPT_ROOT", "SkillOpt checkout")]
    diagnostics.extend(
        [
            _file_diagnostic(
                root / config.skillopt.entry_script,
                "UPSTREAM_ENTRY_SCRIPT",
                "configured SkillOpt entry script",
            ),
            _file_diagnostic(
                root / config.skillopt.upstream_config,
                "UPSTREAM_CONFIG",
                "configured upstream config",
            ),
            _file_diagnostic(
                root / "skillopt" / "model" / "openai_compatible_backend.py",
                "UPSTREAM_COMPAT_BACKEND",
                "OpenAI-compatible backend",
            ),
        ]
    )
    if root.is_dir():
        diagnostics.append(_revision_diagnostic(config.skillopt.required_ref, root))
    return diagnostics


def _data_diagnostic(config: ProjectConfig) -> Diagnostic:
    return _directory_diagnostic(config.data.path, "DATA_PATH", "configured task data")


def _directory_diagnostic(path: Path, code_prefix: str, label: str) -> Diagnostic:
    if path.is_dir():
        return Diagnostic(
            level="info",
            code=f"{code_prefix}_PRESENT",
            message=f"{label} is present at {path}.",
            remediation="",
        )
    return Diagnostic(
        level="error",
        code=f"{code_prefix}_MISSING",
        message=f"{label} is missing at {path}.",
        remediation="Create or select the local path before running SkillOpt.",
    )


def _file_diagnostic(path: Path, code_prefix: str, label: str) -> Diagnostic:
    if path.is_file():
        return Diagnostic(
            level="info",
            code=f"{code_prefix}_PRESENT",
            message=f"{label} is present at {path}.",
            remediation="",
        )
    return Diagnostic(
        level="error",
        code=f"{code_prefix}_MISSING",
        message=f"{label} is missing at {path}.",
        remediation="Use a compatible local SkillOpt checkout and configuration.",
    )


def _revision_diagnostic(required_ref: str, root: Path) -> Diagnostic:
    revision = _git_revision(root)
    if revision is None:
        return Diagnostic(
            level="warning",
            code="UPSTREAM_REF_UNAVAILABLE",
            message="The local SkillOpt revision could not be read from Git.",
            remediation="Use a Git checkout at the required compatible revision when possible.",
        )
    if revision == required_ref:
        return Diagnostic(
            level="info",
            code="UPSTREAM_REF_MATCHED",
            message="The local SkillOpt revision matches the configured compatible baseline.",
            remediation="",
        )
    return Diagnostic(
        level="warning",
        code="UPSTREAM_REF_MISMATCH",
        message="The local SkillOpt revision differs from the configured compatible baseline.",
        remediation=(
            f"Verify required ref {required_ref} and the required feature files "
            + "before a live run."
        ),
    )


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
