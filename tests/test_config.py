import json
from pathlib import Path

import pytest

from agent_skillopt.config import load_config, redacted_config_summary
from agent_skillopt.errors import ConfigurationError


def write_valid_config(tmp_path: Path, *, base_url: str = "https://api.deepseek.com") -> Path:
    path = tmp_path / "agent-skillopt.yaml"
    path.write_text(
        f"""version: 1
skillopt:
  root: ../SkillOpt
  entry_script: scripts/train.py
  required_ref: 9c776fcb51ae681c046d6f619b55e5f337d4f900
  upstream_config: configs/searchqa/default.yaml
provider:
  api_key_env: DEEPSEEK_API_KEY
  base_url: {base_url}
  model: deepseek-v4-flash
data:
  task: searchqa
  path: data/searchqa_split
run:
  output_root: runs
  seed: 42
  upstream_args: []
safety:
  require_allow_network: true
""",
        encoding="utf-8",
    )
    return path


def test_load_config_requires_provider_key_environment_name(tmp_path):
    """Removing the key-variable name must make the configuration invalid."""
    path = tmp_path / "bad.yaml"
    path.write_text(
        """version: 1
provider: {}
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError, match="api_key_env"):
        load_config(path)


def test_redacted_summary_never_contains_environment_secret(tmp_path, monkeypatch):
    """A future summary that reads environment values must not expose a credential."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-secret-value")
    config = load_config(write_valid_config(tmp_path))

    summary = redacted_config_summary(config)

    assert "test-secret-value" not in json.dumps(summary)
    assert summary["provider"]["base_url_host"] == "api.deepseek.com"


def test_load_config_resolves_project_paths_from_the_yaml_location(tmp_path):
    """Moving a project directory must move its configured local paths with it."""
    config_path = write_valid_config(tmp_path)

    config = load_config(config_path)

    assert config.skillopt.root == (tmp_path / "../SkillOpt").resolve()
    assert config.data.path == tmp_path / "data" / "searchqa_split"
    assert config.run.output_root == tmp_path / "runs"


def test_load_config_rejects_a_secret_value_in_yaml(tmp_path):
    """Accidentally adding provider.api_key must fail before it can reach output."""
    path = write_valid_config(tmp_path)
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "  api_key_env: DEEPSEEK_API_KEY\n",
            "  api_key_env: DEEPSEEK_API_KEY\n  api_key: do-not-store-credentials-here\n",
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError, match="provider.api_key"):
        load_config(path)


def test_load_config_allows_insecure_loopback_only_with_explicit_opt_in(tmp_path):
    """An HTTP endpoint must never become valid without the localhost safety switch."""
    path = write_valid_config(tmp_path, base_url="http://localhost:8080")

    with pytest.raises(ConfigurationError, match="HTTPS"):
        load_config(path)

    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "  require_allow_network: true\n",
            "  require_allow_network: true\n  allow_insecure_localhost: true\n",
        ),
        encoding="utf-8",
    )

    assert load_config(path).provider.base_url == "http://localhost:8080"


def test_shipped_searchqa_deepseek_preset_loads_with_the_pinned_baseline():
    """A changed or malformed distributed preset must fail before users copy it."""
    preset_path = Path(__file__).parents[1] / "presets" / "searchqa-deepseek.yaml"

    config = load_config(preset_path)

    assert config.provider.api_key_env == "DEEPSEEK_API_KEY"
    assert config.provider.base_url == "https://api.deepseek.com"
    assert config.skillopt.required_ref == "9c776fcb51ae681c046d6f619b55e5f337d4f900"
