import json
from datetime import datetime, timezone

from agent_skillopt.invocation import execute, render_invocation
from agent_skillopt.manifest import create_manifest

FIXED_TIME = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def test_manifest_contains_reproducibility_metadata_without_secret_or_full_endpoint(
    fake_config, fake_skillopt_root, valid_config_path, monkeypatch
):
    """Serializing a manifest with an injected key must retain only safe metadata."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-secret-value")
    config = fake_config.with_root(fake_skillopt_root)
    invocation = render_invocation(config, valid_config_path, FIXED_TIME)

    manifest_path = create_manifest(invocation, config, "started")
    rendered = manifest_path.read_text(encoding="utf-8")
    payload = json.loads(rendered)

    assert manifest_path == invocation.run_directory / "manifest.json"
    assert payload["status"] == "started"
    assert payload["provider"] == {
        "base_url_host": "api.deepseek.com",
        "model": "deepseek-v4-flash",
    }
    assert payload["config"]["sha256"]
    assert payload["command"] == list(invocation.command)
    assert "test-secret-value" not in rendered
    assert "https://api.deepseek.com" not in rendered
    assert "OPENAI_COMPATIBLE_API_KEY" not in rendered


def test_execute_writes_started_manifest_before_runner_and_records_failure(
    fake_config, fake_skillopt_root, valid_config_path, monkeypatch
):
    """Launching before the started manifest, or keeping a failure as started, must fail."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-secret-value")
    config = fake_config.with_root(fake_skillopt_root)
    invocation = render_invocation(config, valid_config_path, FIXED_TIME)

    def failing_runner(command, working_directory, child_environment):
        started = json.loads(
            (invocation.run_directory / "manifest.json").read_text(encoding="utf-8")
        )
        assert started["status"] == "started"
        assert command == invocation.command
        assert working_directory == fake_skillopt_root
        assert child_environment["OPENAI_COMPATIBLE_API_KEY"] == "test-secret-value"
        assert "DEEPSEEK_API_KEY" not in child_environment
        return 9

    assert execute(invocation, failing_runner) == 9

    rendered = (invocation.run_directory / "manifest.json").read_text(encoding="utf-8")
    assert json.loads(rendered)["status"] == "failed"
    assert "test-secret-value" not in rendered


def test_execute_records_a_successful_child_result(
    fake_config, fake_skillopt_root, valid_config_path, monkeypatch
):
    """A zero child result must be persisted as succeeded rather than failed."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-secret-value")
    config = fake_config.with_root(fake_skillopt_root)
    invocation = render_invocation(config, valid_config_path, FIXED_TIME)

    assert execute(invocation, lambda *_: 0) == 0

    payload = json.loads((invocation.run_directory / "manifest.json").read_text(encoding="utf-8"))
    assert payload["status"] == "succeeded"
