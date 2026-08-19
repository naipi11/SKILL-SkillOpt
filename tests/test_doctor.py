import json
import os

from agent_skillopt.cli import main
from agent_skillopt.doctor import run_doctor


def test_doctor_reports_missing_compatible_backend_and_redacts_secret(fake_config, monkeypatch):
    """A missing upstream feature must be reported without exposing the environment value."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-secret-value")

    diagnostics = run_doctor(fake_config, os.environ)
    rendered = json.dumps([item.to_dict() for item in diagnostics])

    assert "UPSTREAM_COMPAT_BACKEND_MISSING" in rendered
    assert "test-secret-value" not in rendered


def test_doctor_accepts_feature_complete_fake_checkout(fake_config, fake_skillopt_root):
    """All required local artifacts must make doctor free of error diagnostics."""
    diagnostics = run_doctor(fake_config.with_root(fake_skillopt_root), {})

    assert not [item for item in diagnostics if item.level == "error"]


def test_doctor_marks_a_different_upstream_revision_unverified(
    fake_config, fake_skillopt_root, monkeypatch
):
    """A feature-complete but unpinned checkout must remain a warning, not silent acceptance."""
    monkeypatch.setattr("agent_skillopt.doctor._git_revision", lambda _: "different-revision")

    diagnostics = run_doctor(fake_config.with_root(fake_skillopt_root), {})

    assert "UPSTREAM_REF_MISMATCH" in {item.code for item in diagnostics}


def test_doctor_cli_emits_redacted_json(fake_config, fake_skillopt_root, monkeypatch, capsys):
    """Machine-readable doctor output must keep credentials out of the JSON payload."""
    config_path = fake_config.with_root(fake_skillopt_root)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-secret-value")
    config_file = fake_config_path(config_path, fake_skillopt_root)

    assert main(["doctor", "--config", str(config_file), "--json"]) == 0
    rendered = capsys.readouterr().out

    assert "test-secret-value" not in rendered
    assert isinstance(json.loads(rendered), list)


def fake_config_path(config, root):
    """Write a config for the fake checkout without introducing a test credential."""
    path = root.parent / "doctor-config.yaml"
    path.write_text(
        f"""version: 1
skillopt:
  root: {root.name}
  entry_script: scripts/train.py
  required_ref: {config.skillopt.required_ref}
  upstream_config: configs/searchqa/default.yaml
provider:
  api_key_env: {config.provider.api_key_env}
  base_url: {config.provider.base_url}
  model: {config.provider.model}
data:
  task: {config.data.task}
  path: data/searchqa_split
run:
  output_root: runs
  seed: {config.run.seed}
  upstream_args: []
safety:
  require_allow_network: true
""",
        encoding="utf-8",
    )
    return path
