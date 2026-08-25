"""Keep user-facing documentation aligned with the offline plugin contract."""

import json
import os
import subprocess
import sys
from pathlib import Path

from agent_skillopt.bundle import apply_plan, build_plan
from agent_skillopt.models import SkillSpec


def test_readme_lists_each_host_and_the_safe_creation_boundary(project_root: Path):
    readme = (project_root / "README.md").read_text(encoding="utf-8")

    for host in ("Codex", "Claude Code", "Hermes", "OpenClaw"):
        assert host in readme
    for boundary in ("preview", "确认", "validate", "install", "离线", "PLAN ONLY"):
        assert boundary in readme


def test_readme_does_not_reintroduce_retired_provider_or_credential_claims(project_root: Path):
    active_docs = "\n".join(
        (project_root / path).read_text(encoding="utf-8")
        for path in (
            "README.md",
            "CONTRIBUTING.md",
            "docs/compatibility.md",
            "docs/security.md",
            "docs/migration-v0.2.md",
        )
    )

    for retired_claim in ("Microsoft SkillOpt", "DEEPSEEK_API_KEY", "OpenAI-compatible"):
        assert retired_claim not in active_docs
    assert "NOTICE" not in active_docs


def test_remote_marketplace_quick_start_matches_the_host_manifest_contract(project_root: Path):
    published_sha = "9a3c9e1765a5ff0561af5221906879670f5c4536"
    readme = (project_root / "README.md").read_text(encoding="utf-8")
    compatibility = (project_root / "docs" / "compatibility.md").read_text(encoding="utf-8")
    security = (project_root / "docs" / "security.md").read_text(encoding="utf-8")
    claude_marketplace = json.loads(
        (project_root / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
    )
    agents_marketplace = json.loads(
        (project_root / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8")
    )
    claude_plugin = json.loads(
        (project_root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    codex_plugin = json.loads(
        (project_root / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
    )

    for command in (
        "claude plugin marketplace add naipi11/Agent-SkillOpt --scope user",
        "claude plugin install agent-skillopt@agent-skillopt --scope user --yes",
        f"codex plugin marketplace add naipi11/Agent-SkillOpt --ref {published_sha}",
        "codex plugin add agent-skillopt@agent-skillopt",
        f"hermes plugins install naipi11/Agent-SkillOpt --ref {published_sha} --no-enable",
        "hermes plugins show agent-skillopt",
        "hermes plugins enable agent-skillopt",
        "openclaw plugins install <bundle-root>",
    ):
        assert command in readme
    assert "当前 Agent-SkillOpt 插件" in readme
    assert "已发布 `v0.2.1` 的本机实际安装快照" in readme
    assert "当前文档只验证了 CLI/清单契约" not in readme
    assert "Python 3.10+" in readme
    assert "`main` 是可变分支" in readme
    assert "release tag" in readme
    assert "天然不可变" in readme
    assert "40 位 commit SHA" in readme
    assert "相同的 ref 语义" in readme
    assert "不可变 tag" not in readme

    for text in (readme, compatibility, security):
        normalized = "".join(text.split())
        assert "依据ClaudeCode官方插件契约，Gitmarketplace可能会按其设置在后台刷新" in normalized
        assert "初始配置后，即使没有新的明确用户命令，也可能发生远程获取" in normalized
        assert "显式安装或更新同样会访问网络并改变宿主状态" in normalized
        assert "本项目没有运行真实的远程刷新、更新或安装" not in text
        assert "刷新或更新须由用户显式发起" not in text
        assert "刷新或更新必须由用户另行明确执行" not in text
        assert "刷新或更新不是自动行为，必须由用户显式发起" not in text

    for marketplace in (claude_marketplace, agents_marketplace):
        assert marketplace["name"] == "agent-skillopt"
        assert marketplace["plugins"] == [{"name": "agent-skillopt", "source": "./"}]
    assert claude_plugin["name"] == codex_plugin["name"] == "agent-skillopt"
    assert codex_plugin["skills"] == ["./skills/"]

    assert "已实际安装并验证元数据" in compatibility
    assert "已实际安装并启用" in compatibility
    assert published_sha in compatibility
    assert "扫描阻断" not in compatibility
    assert "后台刷新" in compatibility
    assert "可变分支" in compatibility
    assert "release tag" in compatibility
    assert "天然不可变" in compatibility
    assert "40 位 commit SHA" in compatibility
    assert "相同的 ref 语义" in compatibility
    assert "不可变 tag" not in compatibility
    assert "实际 Codex/Claude/Hermes 安装" in security
    assert "兼容性矩阵" in security
    assert "后台刷新" in security
    assert "可变分支" in security
    assert "release tag" in security
    assert "天然不可变" in security
    assert "40 位 commit SHA" in security
    assert "相同的 ref 语义" in security
    assert "不可变 tag" not in security


def test_docs_record_safe_host_boundaries_and_openclaw_status(project_root: Path):
    compatibility = (project_root / "docs" / "compatibility.md").read_text(encoding="utf-8")
    security = (project_root / "docs" / "security.md").read_text(encoding="utf-8")

    for text in (compatibility, security):
        assert "OpenClaw" in text
        assert "未本机安装验证" in text
    for boundary in ("不读取凭据", "不发起网络", "不执行", "确认令牌"):
        assert boundary in security
    assert "Hermes" in compatibility
    assert "Claude Code" in compatibility


def test_docs_distinguish_project_installation_from_generated_bundle_installation(
    project_root: Path,
):
    readme = (project_root / "README.md").read_text(encoding="utf-8")
    skill = (project_root / "skills" / "agent-skillopt" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    host_installation = (
        project_root / "skills" / "agent-skillopt" / "references" / "host-installation.md"
    ).read_text(encoding="utf-8")

    assert "安装当前 Agent-SkillOpt 插件" in readme
    assert "而非下文示例中由它创建的" in readme
    assert "`release-notes` bundle" in readme
    assert "--source-ref <40-char-sha>" in readme
    assert "--source-ref <40-char-sha>" in skill
    assert "--source-ref" in host_installation
    assert "plugins show <name>" in host_installation
    assert (
        "`hermes plugins install <owner>/<repository> --ref <40-char-sha> --no-enable`"
        "<br>`hermes plugins enable release-notes`"
    ) in readme
    assert "hermes plugins show release-notes" not in readme
    assert (
        "`hermes plugins install <owner>/<repository> --ref <40-char-sha> --no-enable`，"
        "再 `hermes plugins enable <name>`"
    ) in host_installation


def test_docs_record_non_atomic_recovery_and_manifest_version_parity(project_root: Path):
    root_manifest = json.loads((project_root / "plugin.json").read_text(encoding="utf-8"))
    codex_manifest = json.loads(
        (project_root / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    claude_manifest = json.loads(
        (project_root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    pyproject = (project_root / "pyproject.toml").read_text(encoding="utf-8")
    package_init = (project_root / "src" / "agent_skillopt" / "__init__.py").read_text(
        encoding="utf-8"
    )
    documents = [
        (project_root / "README.md").read_text(encoding="utf-8"),
        (project_root / "docs" / "compatibility.md").read_text(encoding="utf-8"),
        (project_root / "docs" / "security.md").read_text(encoding="utf-8"),
    ]

    assert (
        root_manifest["version"]
        == codex_manifest["version"]
        == claude_manifest["version"]
        == "0.2.1"
    )
    assert 'version = "0.2.1"' in pyproject
    assert '__version__ = "0.2.1"' in package_init
    for text in documents:
        assert "原子" in text
        assert "40 位 commit SHA" in text
        assert "OpenClaw" in text
    assert "OpenClaw 未在本机验证" in documents[0]
    assert "OpenClaw 未本机安装" in documents[1]
    assert "OpenClaw 未本机安装验证" in documents[2]


def test_migration_retains_a_clear_legacy_pin_and_retired_docs_are_absent(project_root: Path):
    migration = (project_root / "docs" / "migration-v0.2.md").read_text(encoding="utf-8")

    assert "bcbad16" in migration
    assert "0.1.x" in migration
    assert not (project_root / "docs" / "evaluation.md").exists()
    assert not (project_root / "docs" / "experiment-checklist.md").exists()
    assert not (project_root / "NOTICE").exists()


def test_documented_preview_contract_matches_the_wrapper_from_an_arbitrary_cwd(
    project_root: Path, tmp_path: Path
):
    readme = (project_root / "README.md").read_text(encoding="utf-8")
    wrapper = project_root / "skills" / "agent-skillopt" / "scripts" / "scaffold_bundle.py"
    output_directory = tmp_path / "release-notes"
    specification = {
        "name": "release-notes",
        "description": "Draft release notes from verified changes.",
        "body": "Collect verified changes before drafting release notes.",
        "output_directory": str(output_directory),
        "resources": [
            {
                "kind": "reference",
                "filename": "checklist.md",
                "content": "Verify every change before publishing.",
            }
        ],
    }

    result = subprocess.run(
        [sys.executable, str(wrapper), "preview", "--spec", "-"],
        cwd=tmp_path,
        input=json.dumps(specification),
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=True,
    )
    preview = json.loads(result.stdout)

    assert set(preview) == {"confirmation_token", "files", "output_directory"}
    assert preview["output_directory"] == str(output_directory.resolve())
    assert output_directory.exists() is False
    assert {item["path"] for item in preview["files"]} >= {
        "references/checklist.md",
        "skills/release-notes/SKILL.md",
    }
    for key in ("`output_directory`", "`files`", "`confirmation_token`"):
        assert key in readme
    assert "没有顶层 `resources` 字段" in readme


def test_documented_hermes_render_requires_source_and_does_not_execute_a_host(
    project_root: Path, tmp_path: Path
):
    wrapper = project_root / "skills" / "agent-skillopt" / "scripts" / "scaffold_bundle.py"
    bundle_root = tmp_path / "portable-docs"
    specification = SkillSpec.from_json(
        json.dumps(
            {
                "name": "portable-docs",
                "description": "Render a portable documentation package.",
                "body": "Keep host installation as a separate confirmed operation.",
                "output_directory": str(bundle_root),
            }
        )
    )
    apply_plan(build_plan(specification), build_plan(specification).confirmation_token)
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    marker = tmp_path / "hermes-was-run.txt"
    fake_hermes = fake_bin / "hermes.cmd"
    fake_hermes.write_text(
        f'@echo off\r\necho executed > "{marker}"\r\nexit /b 0\r\n', encoding="utf-8"
    )
    environment = dict(os.environ)
    environment["PATH"] = f"{fake_bin}{os.pathsep}{environment.get('PATH', '')}"

    result = subprocess.run(
        [
            sys.executable,
            str(wrapper),
            "install",
            "--host",
            "hermes",
            "--path",
            str(bundle_root),
            "--source",
            "owner/repository",
        ],
        cwd=tmp_path,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=True,
        env=environment,
    )
    rendered = json.loads(result.stdout)

    assert rendered["network_required"] is True
    assert rendered["steps"] == [
        ["hermes", "plugins", "install", "owner/repository", "--no-enable"],
        ["hermes", "plugins", "enable", "portable-docs"],
    ]
    assert marker.exists() is False
    documented_paths = (
        project_root / "README.md",
        project_root / "skills" / "agent-skillopt" / "SKILL.md",
    )
    for path in documented_paths:
        text = path.read_text(encoding="utf-8")
        assert "<codex|claude|openclaw>" in text
        assert "--host hermes" in text
        assert "--source <owner>/<repository>" in text
        assert "<codex|claude|hermes|openclaw>" not in text
