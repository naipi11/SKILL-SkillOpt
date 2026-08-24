import json
import subprocess
import sys
from pathlib import Path

import pytest

from agent_skillopt.cli import main
from agent_skillopt.validation import BundleValidationError, assert_valid_bundle, validate_bundle


def test_minimal_fixture_is_a_valid_four_host_bundle(minimal_bundle: Path):
    assert validate_bundle(minimal_bundle) == ()


def test_validator_rejects_manifest_identity_drift(minimal_bundle: Path):
    codex_manifest = minimal_bundle / ".codex-plugin" / "plugin.json"
    document = json.loads(codex_manifest.read_text(encoding="utf-8"))
    document["version"] = "9.9.9"
    codex_manifest.write_text(json.dumps(document), encoding="utf-8")

    issues = validate_bundle(minimal_bundle)

    assert "MANIFEST_VERSION_MISMATCH" in {issue.code for issue in issues}


def test_validator_rejects_path_traversal_resource(minimal_bundle: Path):
    skill = minimal_bundle / "skills" / "minimal-skill" / "SKILL.md"
    skill.write_text(
        "---\nname: minimal-skill\ndescription: Valid description.\n---\n"
        "Read [secret](../secret.md)",
        encoding="utf-8",
    )

    issues = validate_bundle(minimal_bundle)

    assert "SKILL_PATH_TRAVERSAL" in {issue.code for issue in issues}


def test_validator_requires_the_exact_agent_plugins_schema_url(minimal_bundle: Path):
    manifest = minimal_bundle / "plugin.json"
    document = json.loads(manifest.read_text(encoding="utf-8"))
    document["$schema"] = "https://agent-plugins.org/schemas/latest/plugin.schema.json"
    manifest.write_text(json.dumps(document), encoding="utf-8")

    assert "MANIFEST_SCHEMA_INVALID" in {issue.code for issue in validate_bundle(minimal_bundle)}


def test_validator_rejects_non_strict_skill_frontmatter(minimal_bundle: Path):
    skill = minimal_bundle / "skills" / "minimal-skill" / "SKILL.md"
    skill.write_text(
        "---\nname: minimal-skill\nname: duplicate\ndescription: Valid description.\n---\nbody",
        encoding="utf-8",
    )

    assert "SKILL_FRONTMATTER_INVALID" in {issue.code for issue in validate_bundle(minimal_bundle)}


def test_validator_rejects_a_skill_symlink_that_escapes_the_bundle(
    minimal_bundle: Path, tmp_path: Path
):
    skill = minimal_bundle / "skills" / "minimal-skill" / "SKILL.md"
    outside = tmp_path / "outside.md"
    outside.write_text(skill.read_text(encoding="utf-8"), encoding="utf-8")
    skill.unlink()
    try:
        skill.symlink_to(outside)
    except OSError:
        pytest.skip("symlink creation is unavailable on this host")

    assert "PATH_OUTSIDE_BUNDLE" in {issue.code for issue in validate_bundle(minimal_bundle)}


def test_assert_valid_bundle_reports_every_failure_code(minimal_bundle: Path):
    manifest = minimal_bundle / "plugin.json"
    manifest.write_text("not json", encoding="utf-8")

    with pytest.raises(BundleValidationError, match="MANIFEST_JSON_INVALID"):
        assert_valid_bundle(minimal_bundle)


def test_validate_command_prints_valid_for_a_conforming_bundle(minimal_bundle: Path, capsys):
    assert main(["validate", "--path", str(minimal_bundle)]) == 0

    assert capsys.readouterr().out == "VALID\n"


def test_validate_command_prints_each_structural_issue_to_standard_error(
    minimal_bundle: Path, capsys
):
    (minimal_bundle / "plugin.json").write_text("not json", encoding="utf-8")

    assert main(["validate", "--path", str(minimal_bundle)]) == 1

    assert "MANIFEST_JSON_INVALID" in capsys.readouterr().err


def test_generated_validator_is_the_exact_self_contained_root_copy(
    project_root: Path, minimal_bundle: Path
):
    root_validator = project_root / "tests" / "validate_bundle.py"
    generated_validator = minimal_bundle / "tests" / "validate_bundle.py"

    assert generated_validator.read_text(encoding="utf-8") == root_validator.read_text(
        encoding="utf-8"
    )
    assert "agent_skillopt" not in generated_validator.read_text(encoding="utf-8")


def test_root_validation_wrapper_uses_the_current_checkout(
    project_root: Path, minimal_bundle: Path
):
    result = subprocess.run(
        [sys.executable, str(project_root / "scripts" / "validate_bundle.py"), str(minimal_bundle)],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0
    assert result.stdout == "VALID\n"
