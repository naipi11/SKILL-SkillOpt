"""Regression coverage for public CLI failure status codes."""

from __future__ import annotations

from pathlib import Path

from agent_skillopt.cli import main


def test_doctor_returns_two_when_configuration_is_invalid(tmp_path: Path) -> None:
    """Treating a malformed configuration as success would hide an unusable project."""
    bad_config = tmp_path / "bad.yaml"
    bad_config.write_text("version: 1\n", encoding="utf-8")

    assert main(["doctor", "--config", str(bad_config)]) == 2


def test_run_returns_three_without_allow_network(
    valid_config_path: Path, fake_skillopt_root: Path, monkeypatch
) -> None:
    """Removing the explicit network gate must not turn a normal run command into a live call."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-secret-value")

    assert main(["run", "--config", str(valid_config_path)]) == 3


def test_report_returns_two_for_a_non_object_manifest(tmp_path: Path, capsys) -> None:
    """Accepting a malformed manifest would make the report contract ambiguous."""
    (tmp_path / "manifest.json").write_text("[]", encoding="utf-8")

    assert main(["report", "--run-dir", str(tmp_path)]) == 2

    assert "manifest.json" in capsys.readouterr().err
