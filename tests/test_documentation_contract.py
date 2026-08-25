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
