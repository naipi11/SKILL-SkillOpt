"""Typed, immutable configuration models."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SkillOptConfig:
    """Location and compatibility target for a local SkillOpt checkout."""

    root: Path
    entry_script: Path
    required_ref: str
    upstream_config: Path


@dataclass(frozen=True, slots=True)
class ProviderConfig:
    """A provider contract that intentionally contains no credential value."""

    api_key_env: str
    base_url: str
    model: str


@dataclass(frozen=True, slots=True)
class DataConfig:
    """The local task data consumed by the upstream checkout."""

    task: str
    path: Path


@dataclass(frozen=True, slots=True)
class RunConfig:
    """Deterministic local run settings."""

    output_root: Path
    seed: int
    upstream_args: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SafetyConfig:
    """Explicit opt-ins that control unsafe provider configurations."""

    require_allow_network: bool
    allow_insecure_localhost: bool = False


@dataclass(frozen=True, slots=True)
class ProjectConfig:
    """The complete validated Agent-SkillOpt project configuration."""

    version: int
    skillopt: SkillOptConfig
    provider: ProviderConfig
    data: DataConfig
    run: RunConfig
    safety: SafetyConfig

    def with_root(self, root: Path) -> ProjectConfig:
        """Return an equivalent configuration that uses a different checkout root."""
        return replace(self, skillopt=replace(self.skillopt, root=root))
