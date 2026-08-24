import json
import subprocess
import sys
from importlib import resources
from pathlib import Path

import pytest

from agent_skillopt import bundle
from agent_skillopt.cli import main
from agent_skillopt.models import SkillSpec
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


def test_validator_decodes_json_escaped_frontmatter_description(minimal_bundle: Path):
    description = 'Quoted "text", a backslash \\, and a newline\\nmarker.'
    manifest = minimal_bundle / "plugin.json"
    document = json.loads(manifest.read_text(encoding="utf-8"))
    document["description"] = description
    manifest.write_text(json.dumps(document), encoding="utf-8")
    for host_manifest in (
        minimal_bundle / ".codex-plugin" / "plugin.json",
        minimal_bundle / ".claude-plugin" / "plugin.json",
    ):
        host = json.loads(host_manifest.read_text(encoding="utf-8"))
        host["description"] = description
        host_manifest.write_text(json.dumps(host), encoding="utf-8")
    (minimal_bundle / "skills" / "minimal-skill" / "SKILL.md").write_text(
        "---\nname: minimal-skill\ndescription: " + json.dumps(description) + "\n---\nbody\n",
        encoding="utf-8",
    )

    assert validate_bundle(minimal_bundle) == ()


def test_validator_rejects_an_unterminated_json_frontmatter_string(minimal_bundle: Path):
    skill = minimal_bundle / "skills" / "minimal-skill" / "SKILL.md"
    skill.write_text(
        '---\nname: minimal-skill\ndescription: "Valid description.\n---\nbody\n',
        encoding="utf-8",
    )

    assert "SKILL_FRONTMATTER_INVALID" in {issue.code for issue in validate_bundle(minimal_bundle)}


def test_validator_decodes_yaml_single_quoted_frontmatter_description(minimal_bundle: Path):
    description = "A single ' quote."
    manifest = minimal_bundle / "plugin.json"
    document = json.loads(manifest.read_text(encoding="utf-8"))
    document["description"] = description
    manifest.write_text(json.dumps(document), encoding="utf-8")
    for host_manifest in (
        minimal_bundle / ".codex-plugin" / "plugin.json",
        minimal_bundle / ".claude-plugin" / "plugin.json",
    ):
        host = json.loads(host_manifest.read_text(encoding="utf-8"))
        host["description"] = description
        host_manifest.write_text(json.dumps(host), encoding="utf-8")
    (minimal_bundle / "skills" / "minimal-skill" / "SKILL.md").write_text(
        "---\nname: minimal-skill\ndescription: 'A single '' quote.'\n---\nbody\n",
        encoding="utf-8",
    )

    assert validate_bundle(minimal_bundle) == ()


def test_validator_does_not_read_an_outside_skill_symlink(minimal_bundle: Path, tmp_path: Path):
    skill = minimal_bundle / "skills" / "minimal-skill" / "SKILL.md"
    outside = tmp_path / "outside.md"
    outside.write_text(
        "---\nname: minimal-skill\ndescription: Outside description.\n---\nbody\n",
        encoding="utf-8",
    )
    skill.unlink()
    try:
        skill.symlink_to(outside)
    except OSError:
        pytest.skip("symlink creation is unavailable on this host")

    codes = {issue.code for issue in validate_bundle(minimal_bundle)}

    assert codes == {"PATH_OUTSIDE_BUNDLE"}


def test_validator_rejects_unknown_root_manifest_field(minimal_bundle: Path):
    manifest = minimal_bundle / "plugin.json"
    document = json.loads(manifest.read_text(encoding="utf-8"))
    document["unexpected"] = True
    manifest.write_text(json.dumps(document), encoding="utf-8")

    assert "ROOT_MANIFEST_UNKNOWN_FIELD" in {
        issue.code for issue in validate_bundle(minimal_bundle)
    }


def test_validator_rejects_wrong_optional_root_manifest_type(minimal_bundle: Path):
    manifest = minimal_bundle / "plugin.json"
    document = json.loads(manifest.read_text(encoding="utf-8"))
    document["keywords"] = "not-an-array"
    manifest.write_text(json.dumps(document), encoding="utf-8")

    assert "ROOT_MANIFEST_OPTIONAL_TYPE_INVALID" in {
        issue.code for issue in validate_bundle(minimal_bundle)
    }


def test_validator_accepts_matching_optional_repository_and_license_metadata(minimal_bundle: Path):
    root_manifest = minimal_bundle / "plugin.json"
    root = json.loads(root_manifest.read_text(encoding="utf-8"))
    root.update({"repository": "https://example.test/minimal", "license": "MIT"})
    root_manifest.write_text(json.dumps(root), encoding="utf-8")
    for host_manifest in (
        minimal_bundle / ".codex-plugin" / "plugin.json",
        minimal_bundle / ".claude-plugin" / "plugin.json",
    ):
        host = json.loads(host_manifest.read_text(encoding="utf-8"))
        host.update({"repository": "https://example.test/minimal", "license": "MIT"})
        host_manifest.write_text(json.dumps(host), encoding="utf-8")

    assert validate_bundle(minimal_bundle) == ()


def test_build_plan_loads_the_validator_from_packaged_resources(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    monkeypatch.setattr(bundle, "_PORTABLE_VALIDATOR_PATH", tmp_path / "missing.py", raising=False)
    specification = SkillSpec.from_json(
        json.dumps(
            {
                "name": "minimal-skill",
                "description": "Valid description.",
                "body": "body",
                "output_directory": str(tmp_path / "bundle"),
            }
        )
    )

    validator = next(
        file.content
        for file in bundle.build_plan(specification).files
        if file.relative_path.as_posix() == "tests/validate_bundle.py"
    )

    assert validator == (
        resources.files("agent_skillopt")
        .joinpath("assets/validate_bundle.py")
        .read_text(encoding="utf-8")
    )
    assert "agent_skillopt" not in validator


def test_validator_rejects_case_mismatched_required_manifest_name(minimal_bundle: Path):
    manifest = minimal_bundle / ".codex-plugin" / "plugin.json"
    manifest.rename(manifest.with_name("Plugin.json"))

    assert "REQUIRED_FILE_MISSING" in {issue.code for issue in validate_bundle(minimal_bundle)}


def test_validator_rejects_reference_style_markdown_path_traversal(minimal_bundle: Path):
    skill = minimal_bundle / "skills" / "minimal-skill" / "SKILL.md"
    skill.write_text(
        "---\nname: minimal-skill\ndescription: Valid description.\n---\n"
        "Read [secret][reference].\n\n[reference]: ../secret.md\n",
        encoding="utf-8",
    )

    assert "SKILL_PATH_TRAVERSAL" in {issue.code for issue in validate_bundle(minimal_bundle)}


def test_validator_sorts_os_walk_directory_names_in_place(
    minimal_bundle: Path, monkeypatch: pytest.MonkeyPatch
):
    directories = ["z", "a"]
    filenames = ["z.md", "a.md"]

    def unordered_walk(root: Path, followlinks: bool):
        yield str(root), directories, filenames

    monkeypatch.setattr("agent_skillopt.validation.os.walk", unordered_walk)

    validate_bundle(minimal_bundle)

    assert directories == ["a", "z"]
    assert filenames == ["a.md", "z.md"]
