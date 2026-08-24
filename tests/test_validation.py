import json
import runpy
import subprocess
import sys
from importlib import resources
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote

import pytest

from agent_skillopt import bundle, validation
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


def test_standalone_validator_copies_match_the_packaged_asset(project_root: Path):
    asset = (
        project_root / "src" / "agent_skillopt" / "assets" / "validate_bundle.py"
    ).read_text(encoding="utf-8")

    assert (project_root / "tests" / "validate_bundle.py").read_text(encoding="utf-8") == asset
    assert (
        project_root / "tests" / "fixtures" / "minimal-skill" / "tests" / "validate_bundle.py"
    ).read_text(encoding="utf-8") == asset


def test_validator_rejects_case_mismatched_required_manifest_name(minimal_bundle: Path):
    manifest = minimal_bundle / ".codex-plugin" / "plugin.json"
    manifest.rename(manifest.with_name("Plugin.json"))

    assert "REQUIRED_FILE_MISSING" in {issue.code for issue in validate_bundle(minimal_bundle)}


@pytest.mark.parametrize(
    ("relative_path", "expected_code"),
    (
        ("openclaw.plugin.json", "ROOT_NATIVE_OPENCLAW_FORBIDDEN"),
        ("OPENCLAW.PLUGIN.JSON", "ROOT_NATIVE_OPENCLAW_FORBIDDEN"),
        ("plugin.yaml", "ROOT_NATIVE_HERMES_FORBIDDEN"),
        ("PLUGIN.YAML", "ROOT_NATIVE_HERMES_FORBIDDEN"),
        ("mcp.json", "ROOT_MCP_CONFIGURATION_FORBIDDEN"),
        (".MCP.JSON", "ROOT_MCP_CONFIGURATION_FORBIDDEN"),
        ("hooks.json", "ROOT_HOOK_SURFACE_FORBIDDEN"),
        ("HOOKS", "ROOT_HOOK_SURFACE_FORBIDDEN"),
    ),
)
def test_validator_rejects_prohibited_root_runtime_surfaces(
    minimal_bundle: Path, relative_path: str, expected_code: str
):
    surface = minimal_bundle / relative_path
    if relative_path.casefold() == "hooks":
        surface.mkdir()
    else:
        surface.write_text("{}\n", encoding="utf-8")

    assert expected_code in {issue.code for issue in validate_bundle(minimal_bundle)}


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


@pytest.mark.parametrize(
    "body",
    (
        "Read [secret](file:///../secret.md)",
        "Read [secret](%2e%2e/secret.md)",
        "Read [secret](/absolute/secret.md)",
        "Read [secret](\\\\server\\share\\secret.md)",
        "Read [secret][reference].\n\n[reference]: file:///../secret.md",
    ),
)
def test_validator_rejects_encoded_and_local_markdown_targets(minimal_bundle: Path, body: str):
    skill = minimal_bundle / "skills" / "minimal-skill" / "SKILL.md"
    skill.write_text(
        "---\nname: minimal-skill\ndescription: Valid description.\n---\n" + body + "\n",
        encoding="utf-8",
    )

    assert "SKILL_PATH_TRAVERSAL" in {issue.code for issue in validate_bundle(minimal_bundle)}


@pytest.mark.parametrize(
    ("field", "drift"),
    (
        ("author", {"name": "Different"}),
        ("homepage", "https://example.test/drift"),
        ("keywords", ["different"]),
        ("extensions", {"org.example": {"setting": False}}),
    ),
)
def test_validator_compares_every_optional_host_metadata_field(
    minimal_bundle: Path, field: str, drift: object
):
    optional_metadata = {
        "author": {"name": "Example"},
        "homepage": "https://example.test/home",
        "keywords": ["portable"],
        "extensions": {"org.example": {"setting": True}},
    }
    root_manifest = minimal_bundle / "plugin.json"
    root = json.loads(root_manifest.read_text(encoding="utf-8"))
    root.update(optional_metadata)
    root_manifest.write_text(json.dumps(root), encoding="utf-8")
    for host_manifest in (
        minimal_bundle / ".codex-plugin" / "plugin.json",
        minimal_bundle / ".claude-plugin" / "plugin.json",
    ):
        host = json.loads(host_manifest.read_text(encoding="utf-8"))
        host.update(optional_metadata)
        if host_manifest.parent.name == ".codex-plugin":
            host[field] = drift
        host_manifest.write_text(json.dumps(host), encoding="utf-8")

    assert "MANIFEST_METADATA_MISMATCH" in {issue.code for issue in validate_bundle(minimal_bundle)}


def test_validator_rejects_case_mismatched_canonical_skills_directory(minimal_bundle: Path):
    skills = minimal_bundle / "skills"
    skills.rename(skills.with_name("Skills"))

    assert "SKILL_DIRECTORY_COUNT_INVALID" in {
        issue.code for issue in validate_bundle(minimal_bundle)
    }


def test_validator_rejects_a_contained_symlink_for_the_canonical_skills_directory(
    minimal_bundle: Path,
):
    skills = minimal_bundle / "skills"
    target = minimal_bundle / "skills-target"
    skills.rename(target)
    try:
        skills.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is unavailable on this host")

    assert "SKILL_DIRECTORY_COUNT_INVALID" in {
        issue.code for issue in validate_bundle(minimal_bundle)
    }


def test_validator_keeps_independent_checks_after_invalid_root_identity(minimal_bundle: Path):
    root = minimal_bundle / "plugin.json"
    root.write_text(json.dumps({"$schema": "wrong", "name": 1}), encoding="utf-8")
    codex = minimal_bundle / ".codex-plugin" / "plugin.json"
    document = json.loads(codex.read_text(encoding="utf-8"))
    document["skills"] = []
    codex.write_text(json.dumps(document), encoding="utf-8")
    marketplace = minimal_bundle / ".agents" / "plugins" / "marketplace.json"
    marketplace.write_text(json.dumps({"name": "minimal-skill", "plugins": []}), encoding="utf-8")
    skill = minimal_bundle / "skills" / "minimal-skill" / "SKILL.md"
    skill.write_text("not frontmatter", encoding="utf-8")

    codes = {issue.code for issue in validate_bundle(minimal_bundle)}

    assert {
        "MANIFEST_SCHEMA_INVALID",
        "MANIFEST_METADATA_INVALID",
        "HOST_SKILLS_PATH_INVALID",
        "MARKETPLACE_STRUCTURE_INVALID",
        "SKILL_FRONTMATTER_INVALID",
    } <= codes


@pytest.mark.parametrize(
    "body",
    (
        "Read [secret](%252e%252e%252fsecret.md)",
        "Read [secret][reference].\n\n[reference]: %252e%252e%252fsecret.md",
    ),
)
def test_validator_rejects_repeatedly_encoded_markdown_traversal(minimal_bundle: Path, body: str):
    skill = minimal_bundle / "skills" / "minimal-skill" / "SKILL.md"
    skill.write_text(
        "---\nname: minimal-skill\ndescription: Valid description.\n---\n" + body + "\n",
        encoding="utf-8",
    )

    assert "SKILL_PATH_TRAVERSAL" in {issue.code for issue in validate_bundle(minimal_bundle)}


def test_validator_fails_closed_when_percent_decoding_exceeds_its_bound(minimal_bundle: Path):
    target = "%2e%2e%2fsecret.md"
    for _ in range(16):
        target = quote(target, safe="")
    skill = minimal_bundle / "skills" / "minimal-skill" / "SKILL.md"
    skill.write_text(
        "---\nname: minimal-skill\ndescription: Valid description.\n---\n"
        f"Read [secret]({target})\n",
        encoding="utf-8",
    )

    assert "SKILL_PATH_TRAVERSAL" in {issue.code for issue in validate_bundle(minimal_bundle)}


def test_validator_rejects_a_contained_skill_directory_symlink(minimal_bundle: Path):
    skills = minimal_bundle / "skills"
    skill_directory = skills / "minimal-skill"
    target = minimal_bundle / "internal-target"
    skill_directory.rename(target)
    try:
        skill_directory.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is unavailable on this host")

    assert "SKILL_DIRECTORY_COUNT_INVALID" in {
        issue.code for issue in validate_bundle(minimal_bundle)
    }


def test_validator_compares_structured_optional_metadata_with_exact_json_types(
    minimal_bundle: Path,
):
    root_manifest = minimal_bundle / "plugin.json"
    root = json.loads(root_manifest.read_text(encoding="utf-8"))
    root["extensions"] = {"org.example": {"enabled": True}}
    root_manifest.write_text(json.dumps(root), encoding="utf-8")
    for host_manifest in (
        minimal_bundle / ".codex-plugin" / "plugin.json",
        minimal_bundle / ".claude-plugin" / "plugin.json",
    ):
        host = json.loads(host_manifest.read_text(encoding="utf-8"))
        host["extensions"] = {"org.example": {"enabled": True}}
        if host_manifest.parent.name == ".codex-plugin":
            host["extensions"] = {"org.example": {"enabled": 1}}
        host_manifest.write_text(json.dumps(host), encoding="utf-8")

    assert "MANIFEST_METADATA_MISMATCH" in {issue.code for issue in validate_bundle(minimal_bundle)}


def test_validator_aggregates_optional_metadata_drift_with_invalid_host_identity(
    minimal_bundle: Path,
):
    root_manifest = minimal_bundle / "plugin.json"
    root = json.loads(root_manifest.read_text(encoding="utf-8"))
    root["homepage"] = "https://example.test/root"
    root_manifest.write_text(json.dumps(root), encoding="utf-8")
    host_manifest = minimal_bundle / ".codex-plugin" / "plugin.json"
    host = json.loads(host_manifest.read_text(encoding="utf-8"))
    host["version"] = 1
    host["homepage"] = "https://example.test/drift"
    host_manifest.write_text(json.dumps(host), encoding="utf-8")

    codes = {issue.code for issue in validate_bundle(minimal_bundle)}

    assert {"MANIFEST_METADATA_INVALID", "MANIFEST_METADATA_MISMATCH"} <= codes


def test_link_detector_rejects_junctions_and_lstat_reparse_points():
    class JunctionPath:
        def is_symlink(self) -> bool:
            return False

        def is_junction(self) -> bool:
            return True

        def lstat(self) -> object:
            raise AssertionError("a reported junction must not need lstat")

    class ReparsePointPath:
        def is_symlink(self) -> bool:
            return False

        def lstat(self) -> SimpleNamespace:
            return SimpleNamespace(st_file_attributes=0x0400)

    assert (
        validation._probe_link_or_reparse_point(JunctionPath())
        is validation._LinkProbeResult.LINK
    )
    assert (
        validation._probe_link_or_reparse_point(ReparsePointPath())
        is validation._LinkProbeResult.LINK
    )


def test_validator_rejects_a_reparse_skills_directory_before_reading_it(
    minimal_bundle: Path, monkeypatch: pytest.MonkeyPatch
):
    skills = minimal_bundle / "skills"
    original_detector = validation._probe_link_or_reparse_point
    original_iterdir = Path.iterdir

    monkeypatch.setattr(
        validation,
        "_probe_link_or_reparse_point",
        lambda path: (
            validation._LinkProbeResult.LINK if path == skills else original_detector(path)
        ),
    )

    def guarded_iterdir(path: Path):
        if path == skills:
            raise AssertionError("a reparse skills directory must not be traversed")
        return original_iterdir(path)

    monkeypatch.setattr(Path, "iterdir", guarded_iterdir)

    codes = {issue.code for issue in validate_bundle(minimal_bundle)}

    assert {"PATH_OUTSIDE_BUNDLE", "SKILL_DIRECTORY_COUNT_INVALID"} <= codes


def test_containment_prunes_a_reparse_directory_before_walk_descends(
    minimal_bundle: Path, monkeypatch: pytest.MonkeyPatch
):
    skills = minimal_bundle / "skills"
    scheduled_directories = ["skills"]
    original_detector = validation._probe_link_or_reparse_point

    def guarded_walk(root: Path, followlinks: bool):
        yield str(root), scheduled_directories, []
        if scheduled_directories:
            raise AssertionError("a reparse directory must be pruned before os.walk descends")

    monkeypatch.setattr("agent_skillopt.validation.os.walk", guarded_walk)
    monkeypatch.setattr(
        validation,
        "_probe_link_or_reparse_point",
        lambda path: (
            validation._LinkProbeResult.LINK if path == skills else original_detector(path)
        ),
    )

    codes = {issue.code for issue in validate_bundle(minimal_bundle)}

    assert scheduled_directories == []
    assert {"PATH_OUTSIDE_BUNDLE", "SKILL_DIRECTORY_COUNT_INVALID"} <= codes


def test_validator_rejects_a_reparse_skill_child_before_reading_it(
    minimal_bundle: Path, monkeypatch: pytest.MonkeyPatch
):
    skill_directory = minimal_bundle / "skills" / "minimal-skill"
    skill_file = skill_directory / "SKILL.md"
    original_detector = validation._probe_link_or_reparse_point
    original_read_text = Path.read_text

    monkeypatch.setattr(
        validation,
        "_probe_link_or_reparse_point",
        lambda path: (
            validation._LinkProbeResult.LINK
            if path == skill_directory
            else original_detector(path)
        ),
    )

    def guarded_read_text(path: Path, *args: object, **kwargs: object) -> str:
        if path == skill_file:
            raise AssertionError("a reparse Skill directory must not be traversed")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)

    codes = {issue.code for issue in validate_bundle(minimal_bundle)}

    assert {"PATH_OUTSIDE_BUNDLE", "SKILL_DIRECTORY_COUNT_INVALID"} <= codes


@pytest.mark.parametrize("operation", ("is_symlink", "is_junction", "lstat"))
def test_validator_fails_closed_when_link_probe_errors(
    minimal_bundle: Path,
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
):
    skills = minimal_bundle / "skills"
    skill_file = skills / "minimal-skill" / "SKILL.md"
    original_is_symlink = Path.is_symlink
    original_is_junction = getattr(Path, "is_junction", None)
    original_lstat = Path.lstat
    original_iterdir = Path.iterdir
    original_read_text = Path.read_text
    scheduled_directory_lists: list[list[str]] = []

    def failing_is_symlink(path: Path) -> bool:
        if path == skills:
            raise OSError("link probe failed")
        return original_is_symlink(path)

    def failing_is_junction(path: Path) -> bool:
        if path == skills:
            raise OSError("link probe failed")
        if original_is_junction is None:
            return False
        return original_is_junction(path)

    def failing_lstat(path: Path, *args: object, **kwargs: object) -> object:
        if path == skills:
            raise OSError("link probe failed")
        return original_lstat(path, *args, **kwargs)

    def guarded_walk(root: Path, followlinks: bool):
        directories = ["skills"]
        scheduled_directory_lists.append(directories)
        yield str(root), directories, []
        if directories:
            raise AssertionError("a probe-failed directory must not be walked")

    def guarded_iterdir(path: Path):
        if path == skills:
            raise AssertionError("a probe-failed directory must not be traversed")
        return original_iterdir(path)

    def guarded_read_text(path: Path, *args: object, **kwargs: object) -> str:
        if path == skill_file:
            raise AssertionError("a probe-failed directory must not be read")
        return original_read_text(path, *args, **kwargs)

    if operation == "is_symlink":
        monkeypatch.setattr(Path, "is_symlink", failing_is_symlink)
    elif operation == "is_junction":
        monkeypatch.setattr(Path, "is_junction", failing_is_junction, raising=False)
    else:
        monkeypatch.setattr(Path, "lstat", failing_lstat)
    monkeypatch.setattr("agent_skillopt.validation.os.walk", guarded_walk)
    monkeypatch.setattr(Path, "iterdir", guarded_iterdir)
    monkeypatch.setattr(Path, "read_text", guarded_read_text)

    library_output = [
        (issue.code, issue.path, issue.message) for issue in validate_bundle(minimal_bundle)
    ]
    standalone = runpy.run_path(str(project_root / "tests" / "validate_bundle.py"))
    standalone_output = standalone["validate"](minimal_bundle)

    assert len(scheduled_directory_lists) == 2
    assert all(directories == [] for directories in scheduled_directory_lists)
    assert library_output == standalone_output == [
        (
            "PATH_LINK_PROBE_INVALID",
            skills,
            "link or reparse-point metadata cannot be inspected",
        )
    ]


def test_validator_reports_a_missing_skills_directory_as_layout_invalid(minimal_bundle: Path):
    (minimal_bundle / "skills").rename(minimal_bundle / "missing-skills")

    codes = {issue.code for issue in validate_bundle(minimal_bundle)}

    assert "SKILL_DIRECTORY_COUNT_INVALID" in codes
    assert "PATH_LINK_PROBE_INVALID" not in codes


def test_validator_rejects_a_symlinked_bundle_root_before_accessing_it(
    minimal_bundle: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    root_link = tmp_path / "minimal-skill-link"
    try:
        root_link.symlink_to(minimal_bundle, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is unavailable on this host")

    original_is_dir = Path.is_dir
    original_resolve = Path.resolve
    original_iterdir = Path.iterdir
    original_read_text = Path.read_text
    original_walk = validation.os.walk
    accesses: list[str] = []

    def is_root_or_descendant(path: Path) -> bool:
        return path == root_link or root_link in path.parents

    def tracking_is_dir(path: Path) -> bool:
        if path == root_link:
            accesses.append("is_dir")
        return original_is_dir(path)

    def tracking_resolve(path: Path, *args: object, **kwargs: object) -> Path:
        if path == root_link:
            accesses.append("resolve")
        return original_resolve(path, *args, **kwargs)

    def tracking_iterdir(path: Path):
        if is_root_or_descendant(path):
            accesses.append("iterdir")
        return original_iterdir(path)

    def tracking_read_text(path: Path, *args: object, **kwargs: object) -> str:
        if is_root_or_descendant(path):
            accesses.append("read_text")
        return original_read_text(path, *args, **kwargs)

    def tracking_walk(root: Path, *args: object, **kwargs: object):
        if root == root_link:
            accesses.append("walk")
        return original_walk(root, *args, **kwargs)

    monkeypatch.setattr(Path, "is_dir", tracking_is_dir)
    monkeypatch.setattr(Path, "resolve", tracking_resolve)
    monkeypatch.setattr(Path, "iterdir", tracking_iterdir)
    monkeypatch.setattr(Path, "read_text", tracking_read_text)
    monkeypatch.setattr("agent_skillopt.validation.os.walk", tracking_walk)

    output = [(issue.code, issue.path, issue.message) for issue in validate_bundle(root_link)]

    assert accesses == []
    assert output == [
        (
            "BUNDLE_ROOT_LINK_INVALID",
            root_link,
            "bundle root cannot be a link or reparse point",
        )
    ]


@pytest.mark.parametrize(
    ("operation", "expected_code", "expected_message"),
    (
        ("junction", "BUNDLE_ROOT_LINK_INVALID", "bundle root cannot be a link or reparse point"),
        ("reparse", "BUNDLE_ROOT_LINK_INVALID", "bundle root cannot be a link or reparse point"),
        ("is_symlink", "BUNDLE_ROOT_PROBE_INVALID", "bundle root metadata cannot be inspected"),
        ("is_junction", "BUNDLE_ROOT_PROBE_INVALID", "bundle root metadata cannot be inspected"),
        ("lstat", "BUNDLE_ROOT_PROBE_INVALID", "bundle root metadata cannot be inspected"),
    ),
)
def test_validator_rejects_unsafe_root_probe_before_accessing_it(
    minimal_bundle: Path,
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
    expected_code: str,
    expected_message: str,
):
    original_is_symlink = Path.is_symlink
    original_is_junction = getattr(Path, "is_junction", None)
    original_lstat = Path.lstat
    original_is_dir = Path.is_dir
    original_resolve = Path.resolve
    original_iterdir = Path.iterdir
    original_read_text = Path.read_text
    original_walk = validation.os.walk
    accesses: list[str] = []

    def false_is_symlink(path: Path) -> bool:
        if path == minimal_bundle:
            return False
        return original_is_symlink(path)

    def false_is_junction(path: Path) -> bool:
        if path == minimal_bundle or original_is_junction is None:
            return False
        return original_is_junction(path)

    def failing_is_symlink(path: Path) -> bool:
        if path == minimal_bundle:
            raise OSError("root probe failed")
        return original_is_symlink(path)

    def failing_is_junction(path: Path) -> bool:
        if path == minimal_bundle:
            raise OSError("root probe failed")
        if original_is_junction is None:
            return False
        return original_is_junction(path)

    def reparse_lstat(path: Path, *args: object, **kwargs: object) -> object:
        if path == minimal_bundle:
            return SimpleNamespace(st_file_attributes=0x0400)
        return original_lstat(path, *args, **kwargs)

    def failing_lstat(path: Path, *args: object, **kwargs: object) -> object:
        if path == minimal_bundle:
            raise OSError("root probe failed")
        return original_lstat(path, *args, **kwargs)

    def tracking_is_dir(path: Path) -> bool:
        if path == minimal_bundle:
            accesses.append("is_dir")
        return original_is_dir(path)

    def tracking_resolve(path: Path, *args: object, **kwargs: object) -> Path:
        if path == minimal_bundle:
            accesses.append("resolve")
        return original_resolve(path, *args, **kwargs)

    def tracking_iterdir(path: Path):
        if path == minimal_bundle or minimal_bundle in path.parents:
            accesses.append("iterdir")
        return original_iterdir(path)

    def tracking_read_text(path: Path, *args: object, **kwargs: object) -> str:
        if path == minimal_bundle or minimal_bundle in path.parents:
            accesses.append("read_text")
        return original_read_text(path, *args, **kwargs)

    def tracking_walk(root: Path, *args: object, **kwargs: object):
        if root == minimal_bundle:
            accesses.append("walk")
        return original_walk(root, *args, **kwargs)

    if operation == "junction":
        monkeypatch.setattr(Path, "is_symlink", false_is_symlink)
        monkeypatch.setattr(
            Path,
            "is_junction",
            lambda path: path == minimal_bundle or false_is_junction(path),
            raising=False,
        )
    elif operation == "reparse":
        monkeypatch.setattr(Path, "is_symlink", false_is_symlink)
        monkeypatch.setattr(Path, "is_junction", false_is_junction, raising=False)
        monkeypatch.setattr(Path, "lstat", reparse_lstat)
    elif operation == "is_symlink":
        monkeypatch.setattr(Path, "is_symlink", failing_is_symlink)
    elif operation == "is_junction":
        monkeypatch.setattr(Path, "is_symlink", false_is_symlink)
        monkeypatch.setattr(Path, "is_junction", failing_is_junction, raising=False)
    else:
        monkeypatch.setattr(Path, "is_symlink", false_is_symlink)
        monkeypatch.setattr(Path, "is_junction", false_is_junction, raising=False)
        monkeypatch.setattr(Path, "lstat", failing_lstat)
    monkeypatch.setattr(Path, "is_dir", tracking_is_dir)
    monkeypatch.setattr(Path, "resolve", tracking_resolve)
    monkeypatch.setattr(Path, "iterdir", tracking_iterdir)
    monkeypatch.setattr(Path, "read_text", tracking_read_text)
    monkeypatch.setattr("agent_skillopt.validation.os.walk", tracking_walk)

    library_output = [
        (issue.code, issue.path, issue.message) for issue in validate_bundle(minimal_bundle)
    ]
    standalone = runpy.run_path(str(project_root / "tests" / "validate_bundle.py"))
    standalone_output = standalone["validate"](minimal_bundle)

    assert accesses == []
    assert library_output == standalone_output == [
        (expected_code, minimal_bundle, expected_message)
    ]


def test_validator_preserves_missing_bundle_root_semantics(
    tmp_path: Path, project_root: Path
):
    missing_root = tmp_path / "missing-bundle"

    library_output = [
        (issue.code, issue.path, issue.message) for issue in validate_bundle(missing_root)
    ]
    standalone = runpy.run_path(str(project_root / "tests" / "validate_bundle.py"))
    standalone_output = standalone["validate"](missing_root)

    assert library_output == standalone_output == [
        ("BUNDLE_ROOT_INVALID", missing_root, "bundle root must be a directory")
    ]
