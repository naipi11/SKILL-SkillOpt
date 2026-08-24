"""Contract tests for the repository's installable four-host package."""

import json
import subprocess
import sys

from agent_skillopt.validation import validate_bundle


def test_repository_root_is_a_valid_agent_plugin_package(project_root):
    assert validate_bundle(project_root) == ()


def test_codex_and_claude_manifests_share_identity(project_root):
    codex = json.loads((project_root / ".codex-plugin" / "plugin.json").read_text())
    claude = json.loads((project_root / ".claude-plugin" / "plugin.json").read_text())

    assert codex["name"] == claude["name"] == "agent-skillopt"
    assert codex["version"] == claude["version"] == "0.2.0"
    assert codex["repository"] == claude["repository"]
    assert codex["license"] == claude["license"] == "MIT"


def test_portable_package_has_no_native_openclaw_or_hermes_adapter(project_root):
    assert not (project_root / "openclaw.plugin.json").exists()
    assert not (project_root / "plugin.yaml").exists()


def test_scaffolder_wrapper_forwards_help_without_writing(project_root, tmp_path):
    wrapper = project_root / "skills" / "agent-skillopt" / "scripts" / "scaffold_bundle.py"
    result = subprocess.run(
        [sys.executable, str(wrapper), "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "preview" in result.stdout
    assert list(tmp_path.iterdir()) == []
