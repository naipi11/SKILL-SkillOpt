"""Safe YAML configuration loading and redacted summaries."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml

from agent_skillopt.errors import ConfigurationError
from agent_skillopt.models import (
    DataConfig,
    ProjectConfig,
    ProviderConfig,
    RunConfig,
    SafetyConfig,
    SkillOptConfig,
)

_ENVIRONMENT_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}


def load_config(path: Path) -> ProjectConfig:
    """Load and validate one project YAML file without reading credential values."""
    config_path = Path(path).resolve()
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ConfigurationError(f"Configuration file not found: {config_path}") from error
    except UnicodeDecodeError as error:
        raise ConfigurationError(f"Configuration file is not UTF-8: {config_path}") from error
    except yaml.YAMLError as error:
        raise ConfigurationError(f"Invalid YAML in {config_path}: {error}") from error

    document = _mapping(raw, "configuration")
    version = _required_int(document, "version", "configuration")
    if version != 1:
        raise ConfigurationError("configuration.version must be 1")

    safety = _load_safety(document.get("safety"))
    provider = _load_provider(_mapping(document.get("provider"), "provider"), safety)
    skillopt = _load_skillopt(
        _mapping(document.get("skillopt"), "skillopt"),
        config_path.parent,
    )
    data = _load_data(_mapping(document.get("data"), "data"), config_path.parent)
    run = _load_run(_mapping(document.get("run"), "run"), config_path.parent)
    return ProjectConfig(
        version=version,
        skillopt=skillopt,
        provider=provider,
        data=data,
        run=run,
        safety=safety,
    )


def redacted_config_summary(config: ProjectConfig) -> dict[str, Any]:
    """Return reproducibility metadata without a provider secret or full endpoint URL."""
    return {
        "version": config.version,
        "skillopt": {
            "root": str(config.skillopt.root),
            "entry_script": str(config.skillopt.entry_script),
            "required_ref": config.skillopt.required_ref,
            "upstream_config": str(config.skillopt.upstream_config),
        },
        "provider": {
            "api_key_env": config.provider.api_key_env,
            "base_url_host": urlsplit(config.provider.base_url).hostname,
            "model": config.provider.model,
        },
        "data": {"task": config.data.task, "path": str(config.data.path)},
        "run": {
            "output_root": str(config.run.output_root),
            "seed": config.run.seed,
            "upstream_args": list(config.run.upstream_args),
        },
        "safety": {
            "require_allow_network": config.safety.require_allow_network,
            "allow_insecure_localhost": config.safety.allow_insecure_localhost,
        },
    }


def _load_safety(raw: object) -> SafetyConfig:
    if raw is None:
        return SafetyConfig(require_allow_network=True)
    safety = _mapping(raw, "safety")
    return SafetyConfig(
        require_allow_network=_optional_bool(safety, "require_allow_network", True, "safety"),
        allow_insecure_localhost=_optional_bool(
            safety, "allow_insecure_localhost", False, "safety"
        ),
    )


def _load_provider(raw: dict[str, Any], safety: SafetyConfig) -> ProviderConfig:
    if "api_key" in raw:
        raise ConfigurationError("provider.api_key is forbidden; use provider.api_key_env instead")
    api_key_env = _required_text(raw, "api_key_env", "provider")
    if not _ENVIRONMENT_NAME.fullmatch(api_key_env):
        raise ConfigurationError("provider.api_key_env must be an environment-variable identifier")

    base_url = _required_text(raw, "base_url", "provider")
    _validate_base_url(base_url, safety)
    return ProviderConfig(
        api_key_env=api_key_env,
        base_url=base_url,
        model=_required_text(raw, "model", "provider"),
    )


def _load_skillopt(raw: dict[str, Any], config_directory: Path) -> SkillOptConfig:
    return SkillOptConfig(
        root=_resolve_project_path(_required_text(raw, "root", "skillopt"), config_directory),
        entry_script=_relative_upstream_path(
            _required_text(raw, "entry_script", "skillopt"), "skillopt.entry_script"
        ),
        required_ref=_required_text(raw, "required_ref", "skillopt"),
        upstream_config=_relative_upstream_path(
            _required_text(raw, "upstream_config", "skillopt"), "skillopt.upstream_config"
        ),
    )


def _load_data(raw: dict[str, Any], config_directory: Path) -> DataConfig:
    return DataConfig(
        task=_required_text(raw, "task", "data"),
        path=_resolve_project_path(_required_text(raw, "path", "data"), config_directory),
    )


def _load_run(raw: dict[str, Any], config_directory: Path) -> RunConfig:
    upstream_args = raw.get("upstream_args", [])
    if not isinstance(upstream_args, list) or not all(
        isinstance(arg, str) for arg in upstream_args
    ):
        raise ConfigurationError("run.upstream_args must be a list of strings")
    return RunConfig(
        output_root=_resolve_project_path(
            _required_text(raw, "output_root", "run"), config_directory
        ),
        seed=_required_int(raw, "seed", "run"),
        upstream_args=tuple(upstream_args),
    )


def _mapping(value: object, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigurationError(f"{name} must be a mapping")
    return value


def _required_text(mapping: dict[str, Any], key: str, section: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"{section}.{key} is required and must be a non-empty string")
    return value


def _required_int(mapping: dict[str, Any], key: str, section: str) -> int:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigurationError(f"{section}.{key} is required and must be an integer")
    return value


def _optional_bool(mapping: dict[str, Any], key: str, default: bool, section: str) -> bool:
    value = mapping.get(key, default)
    if not isinstance(value, bool):
        raise ConfigurationError(f"{section}.{key} must be a boolean")
    return value


def _resolve_project_path(value: str, config_directory: Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = config_directory / path
    return path.resolve()


def _relative_upstream_path(value: str, field: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ConfigurationError(f"{field} must stay within skillopt.root")
    return path


def _validate_base_url(base_url: str, safety: SafetyConfig) -> None:
    parsed = urlsplit(base_url)
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ConfigurationError(
            "provider.base_url must not contain credentials, query, or fragment"
        )
    hostname = parsed.hostname
    if not hostname:
        raise ConfigurationError("provider.base_url must include a hostname")
    if parsed.scheme == "https":
        return
    if (
        parsed.scheme == "http"
        and safety.allow_insecure_localhost
        and hostname.lower() in _LOOPBACK_HOSTS
    ):
        return
    raise ConfigurationError(
        "provider.base_url must use HTTPS unless safety.allow_insecure_localhost is true"
    )
