"""Contract tests for the repository's installable four-host package."""

import importlib.machinery
import json
import runpy
import subprocess
import sys
import types

import pytest

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


def test_installed_skill_uses_its_own_absolute_directory_for_wrapper_invocation(project_root):
    skill = project_root / "skills" / "agent-skillopt" / "SKILL.md"
    content = skill.read_text(encoding="utf-8")

    assert "python skills/agent-skillopt/scripts/scaffold_bundle.py" not in content
    assert "当前正在阅读的 SKILL.md 的绝对路径" in content
    assert "<absolute-SKILL-directory>/scripts/scaffold_bundle.py" in content


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


def test_scaffolder_wrapper_overrides_a_preloaded_external_package(project_root, tmp_path):
    wrapper = project_root / "skills" / "agent-skillopt" / "scripts" / "scaffold_bundle.py"
    stale_package = tmp_path / "stale" / "agent_skillopt"
    stale_package.mkdir(parents=True)
    (stale_package / "__init__.py").write_text("", encoding="utf-8")
    (stale_package / "cli.py").write_text(
        "def main():\n    print('STALE_AGENT_SKILLOPT')\n    return 0\n",
        encoding="utf-8",
    )
    command = "\n".join(
        (
            "import runpy",
            "import sys",
            f"sys.path.insert(0, {str(stale_package.parent)!r})",
            "import agent_skillopt.cli",
            f"sys.path.append({str(project_root / 'src')!r})",
            f"runpy.run_path({str(wrapper)!r}, run_name='__main__')",
        )
    )

    result = subprocess.run(
        [sys.executable, "-c", command, "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "preview" in result.stdout
    assert "STALE_AGENT_SKILLOPT" not in result.stdout


def test_scaffolder_wrapper_discards_preloaded_modules_without_an_origin(project_root, tmp_path):
    wrapper = project_root / "skills" / "agent-skillopt" / "scripts" / "scaffold_bundle.py"
    command = "\n".join(
        (
            "import runpy",
            "import sys",
            "import types",
            "package = types.ModuleType('agent_skillopt')",
            "cli = types.ModuleType('agent_skillopt.cli')",
            "cli.main = lambda: (print('ORIGINLESS_STALE_AGENT_SKILLOPT') or 0)",
            "sys.modules['agent_skillopt'] = package",
            "sys.modules['agent_skillopt.cli'] = cli",
            f"sys.path.append({str(project_root / 'src')!r})",
            f"runpy.run_path({str(wrapper)!r}, run_name='__main__')",
        )
    )

    result = subprocess.run(
        [sys.executable, "-c", command, "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "preview" in result.stdout
    assert "ORIGINLESS_STALE_AGENT_SKILLOPT" not in result.stdout


def test_scaffolder_wrapper_discards_a_cached_module_from_repo_outside_src(project_root, tmp_path):
    wrapper = project_root / "skills" / "agent-skillopt" / "scripts" / "scaffold_bundle.py"
    stale_origin = project_root / "README.md"
    command = "\n".join(
        (
            "import importlib.machinery",
            "import runpy",
            "import sys",
            "import types",
            "package = types.ModuleType('agent_skillopt')",
            "cli = types.ModuleType('agent_skillopt.cli')",
            f"package.__file__ = {str(stale_origin)!r}",
            f"cli.__file__ = {str(stale_origin)!r}",
            "package.__spec__ = importlib.machinery.ModuleSpec('agent_skillopt', None,",
            "    origin=package.__file__)",
            "cli.__spec__ = importlib.machinery.ModuleSpec('agent_skillopt.cli', None,",
            "    origin=cli.__file__)",
            "cli.main = lambda: (print('REPOSITORY_LOCAL_STALE_AGENT_SKILLOPT') or 0)",
            "sys.modules['agent_skillopt'] = package",
            "sys.modules['agent_skillopt.cli'] = cli",
            f"sys.path.append({str(project_root / 'src')!r})",
            f"runpy.run_path({str(wrapper)!r}, run_name='__main__')",
        )
    )

    result = subprocess.run(
        [sys.executable, "-c", command, "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "preview" in result.stdout
    assert "REPOSITORY_LOCAL_STALE_AGENT_SKILLOPT" not in result.stdout


def test_scaffolder_wrapper_trusts_only_resolved_src_module_origins(project_root, tmp_path):
    wrapper = project_root / "skills" / "agent-skillopt" / "scripts" / "scaffold_bundle.py"
    source_root = (project_root / "src").resolve()
    module = types.ModuleType("agent_skillopt.cli")
    source_file = source_root / "agent_skillopt" / "cli.py"
    module.__file__ = str(source_file)
    module.__spec__ = importlib.machinery.ModuleSpec(
        "agent_skillopt.cli", None, origin=str(source_file)
    )
    wrapper_namespace = runpy.run_path(str(wrapper), run_name="scaffold_bundle_test")
    origin_is_within = wrapper_namespace["_module_origin_is_within"]

    assert origin_is_within(module, source_root)

    source_link = tmp_path / "cli-link.py"
    try:
        source_link.symlink_to(source_file)
    except OSError:
        pytest.skip("symlink creation is unavailable on this host")
    module.__file__ = str(source_link)
    module.__spec__ = importlib.machinery.ModuleSpec(
        "agent_skillopt.cli", None, origin=str(source_link)
    )

    assert origin_is_within(module, source_root)
