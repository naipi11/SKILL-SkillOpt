"""Contract tests for the repository's installable four-host package."""

import json
import os
import subprocess
import sys

import pytest

from agent_skillopt.validation import validate_bundle


def test_repository_root_is_a_valid_agent_plugin_package(project_root):
    assert validate_bundle(project_root) == ()


def test_codex_and_claude_manifests_share_identity(project_root):
    codex = json.loads((project_root / ".codex-plugin" / "plugin.json").read_text())
    claude = json.loads((project_root / ".claude-plugin" / "plugin.json").read_text())

    assert codex["name"] == claude["name"] == "agent-skillopt"
    assert codex["version"] == claude["version"] == "0.3.0"
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
        encoding="utf-8",
        check=False,
    )

    assert result.returncode == 0
    for command in ("preview", "apply", "validate", "review", "evaluate", "install"):
        assert command in result.stdout
    assert list(tmp_path.iterdir()) == []


def test_cli_outputs_utf8_when_pythonioencoding_is_a_legacy_code_page(project_root, tmp_path):
    wrapper = project_root / "skills" / "agent-skillopt" / "scripts" / "scaffold_bundle.py"
    environment = {
        **os.environ,
        "PYTHONIOENCODING": "cp1252:strict",
        "PYTHONPATH": str(project_root / "src"),
    }

    for command in (
        [sys.executable, str(wrapper), "--help"],
        [sys.executable, "-m", "agent_skillopt", "--help"],
    ):
        result = subprocess.run(
            command,
            cwd=tmp_path,
            capture_output=True,
            text=False,
            env=environment,
            check=False,
        )

        assert result.returncode == 0
        assert "跨宿主 Skill 创作工具" in result.stdout.decode("utf-8")

    for command in (
        [sys.executable, str(wrapper), "preview", "--spec", "missing.json"],
        [sys.executable, "-m", "agent_skillopt", "preview", "--spec", "missing.json"],
    ):
        error_result = subprocess.run(
            command,
            cwd=tmp_path,
            capture_output=True,
            text=False,
            env=environment,
            check=False,
        )

        assert error_result.returncode == 2
        assert "预览失败：规格无效。" in error_result.stderr.decode("utf-8")


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
        encoding="utf-8",
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
        encoding="utf-8",
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
        encoding="utf-8",
        check=False,
    )

    assert result.returncode == 0
    assert "preview" in result.stdout
    assert "REPOSITORY_LOCAL_STALE_AGENT_SKILLOPT" not in result.stdout


@pytest.mark.parametrize("use_external_search_path", (False, True))
def test_scaffolder_wrapper_discards_source_looking_package_with_poisoned_search_paths(
    project_root, tmp_path, use_external_search_path
):
    wrapper = project_root / "skills" / "agent-skillopt" / "scripts" / "scaffold_bundle.py"
    source_root = (project_root / "src").resolve()
    source_init = source_root / "agent_skillopt" / "__init__.py"
    poisoned_paths = [str(tmp_path / "poisoned-search")] if use_external_search_path else []
    command = "\n".join(
        (
            "import importlib.machinery",
            "import runpy",
            "import sys",
            "import types",
            "package = types.ModuleType('agent_skillopt')",
            f"package.__file__ = {str(source_init)!r}",
            "package.__spec__ = importlib.machinery.ModuleSpec('agent_skillopt', None,",
            "    is_package=True)",
            "package.__spec__.origin = package.__file__",
            f"package.__path__ = {poisoned_paths!r}",
            f"package.__spec__.submodule_search_locations = {poisoned_paths!r}",
            "sys.modules['agent_skillopt'] = package",
            f"sys.path.append({str(source_root)!r})",
            f"runpy.run_path({str(wrapper)!r}, run_name='__main__')",
        )
    )

    result = subprocess.run(
        [sys.executable, "-c", command, "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert result.returncode == 0
    assert "preview" in result.stdout
