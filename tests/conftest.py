from pathlib import Path

import pytest

from agent_skillopt.config import load_config

PINNED_SKILLOPT_REF = "9c776fcb51ae681c046d6f619b55e5f337d4f900"


@pytest.fixture
def valid_config_path(tmp_path: Path) -> Path:
    path = tmp_path / "agent-skillopt.yaml"
    path.write_text(
        f"""version: 1
skillopt:
  root: SkillOpt
  entry_script: scripts/train.py
  required_ref: {PINNED_SKILLOPT_REF}
  upstream_config: configs/searchqa/default.yaml
provider:
  api_key_env: DEEPSEEK_API_KEY
  base_url: https://api.deepseek.com
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


@pytest.fixture
def fake_config(valid_config_path: Path):
    return load_config(valid_config_path)


@pytest.fixture
def fake_skillopt_root(tmp_path: Path) -> Path:
    root = tmp_path / "SkillOpt"
    (root / "scripts").mkdir(parents=True)
    (root / "configs" / "searchqa").mkdir(parents=True)
    (root / "skillopt" / "model").mkdir(parents=True)
    (root / "scripts" / "train.py").write_text("# fake upstream entry\n", encoding="utf-8")
    (root / "configs" / "searchqa" / "default.yaml").write_text(
        "task: searchqa\n", encoding="utf-8"
    )
    (root / "skillopt" / "model" / "openai_compatible_backend.py").write_text(
        "# fake compatible backend\n",
        encoding="utf-8",
    )
    (tmp_path / "data" / "searchqa_split").mkdir(parents=True)
    return root
