"""Keep user-facing documentation aligned with the offline plugin contract."""

from pathlib import Path


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
