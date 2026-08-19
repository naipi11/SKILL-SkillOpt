import os
import sys
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from agent_skillopt.cli import main
from agent_skillopt.errors import ConfigurationError, ExecutionGateError
from agent_skillopt.invocation import render_invocation, require_execution_permission

FIXED_TIME = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def test_dry_run_command_uses_compatible_backends_and_never_contains_a_key(
    fake_config, fake_skillopt_root, valid_config_path, monkeypatch
):
    """Changing either backend flag or adding a credential to the command must fail."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-secret-value")
    config = fake_config.with_root(fake_skillopt_root)

    invocation = render_invocation(config, valid_config_path, FIXED_TIME)

    assert invocation.command == (
        sys.executable,
        str(fake_skillopt_root / "scripts" / "train.py"),
        "--config",
        "configs/searchqa/default.yaml",
        "--optimizer_backend",
        "openai_compatible",
        "--target_backend",
        "openai_compatible",
        "--optimizer_model",
        "deepseek-v4-flash",
        "--target_model",
        "deepseek-v4-flash",
        "--data_path",
        str(config.data.path),
        "--out_root",
        str(config.run.output_root / "searchqa-20260102T030405Z"),
        "--seed",
        "42",
    )
    assert invocation.child_environment == {
        "OPENAI_COMPATIBLE_BASE_URL": "https://api.deepseek.com",
        "OPENAI_COMPATIBLE_MODEL": "deepseek-v4-flash",
    }
    assert "--backend" not in invocation.command
    assert "test-secret-value" not in " ".join(invocation.command)


def test_live_execution_requires_explicit_network_acknowledgement(fake_config, monkeypatch):
    """Removing the command-line acknowledgement must block an otherwise keyed run."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-secret-value")

    with pytest.raises(ExecutionGateError, match="--allow-network") as error:
        require_execution_permission(fake_config, False, os.environ)

    assert error.value.exit_code == 3


def test_live_execution_requires_configured_key_environment(fake_config):
    """Dropping the configured key environment variable must block execution."""
    with pytest.raises(ExecutionGateError, match="DEEPSEEK_API_KEY") as error:
        require_execution_permission(fake_config, True, {})

    assert error.value.exit_code == 2


def test_render_rejects_upstream_arguments_that_attempt_to_supply_a_key(
    fake_config, fake_skillopt_root, valid_config_path
):
    """Adding a credential-style upstream option must not create a bypass around api_key_env."""
    config = replace(
        fake_config.with_root(fake_skillopt_root),
        run=replace(fake_config.run, upstream_args=("--api-key", "test-secret-value")),
    )

    with pytest.raises(ConfigurationError, match="upstream_args"):
        render_invocation(config, valid_config_path, FIXED_TIME)


def test_render_rejects_an_endpoint_argument_with_a_query_string(
    fake_config, fake_skillopt_root, valid_config_path
):
    """Embedding a queried URL after an option equals sign must not reach a manifest."""
    config = replace(
        fake_config.with_root(fake_skillopt_root),
        run=replace(
            fake_config.run,
            upstream_args=("--endpoint=https://provider.example/v1?run=1",),
        ),
    )

    with pytest.raises(ConfigurationError, match="query parameters"):
        render_invocation(config, valid_config_path, FIXED_TIME)


def test_cli_dry_run_renders_without_creating_run_artifacts(
    fake_skillopt_root, valid_config_path, monkeypatch, capsys
):
    """A dry-run must display a command while leaving the configured output root absent."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-secret-value")

    assert main(["run", "--config", str(valid_config_path), "--dry-run"]) == 0

    rendered = capsys.readouterr().out
    assert "--optimizer_backend openai_compatible" in rendered
    assert "test-secret-value" not in rendered
    assert not (valid_config_path.parent / "runs").exists()
