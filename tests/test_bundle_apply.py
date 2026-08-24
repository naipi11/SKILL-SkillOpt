import json
import os
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from agent_skillopt import bundle
from agent_skillopt.bundle import apply_plan, build_plan
from agent_skillopt.errors import (
    ConfirmationError,
    PublicationError,
    StagingCleanupError,
    WriteConflictError,
)
from agent_skillopt.models import PlannedFile, SkillSpec
from agent_skillopt.validation import BundleValidationError


@pytest.fixture
def sample_spec(tmp_path: Path) -> SkillSpec:
    return SkillSpec.from_json(json.dumps({
        "name": "release-notes",
        "description": "Draft release notes from verified changes.",
        "body": "Collect verified changes before drafting the release notes.",
        "output_directory": str(tmp_path / "release-notes"),
    }))


def test_apply_requires_the_exact_preview_token(sample_spec: SkillSpec):
    plan = build_plan(sample_spec)

    with pytest.raises(ConfirmationError, match="confirmation token"):
        apply_plan(plan, "not-the-preview-token")

    assert sample_spec.output_directory.exists() is False


def test_apply_refuses_existing_target_without_changing_it(sample_spec: SkillSpec):
    sample_spec.output_directory.mkdir(parents=True)
    marker = sample_spec.output_directory / "user-file.txt"
    marker.write_text("preserve", encoding="utf-8")
    plan = build_plan(sample_spec)

    with pytest.raises(WriteConflictError):
        apply_plan(plan, plan.confirmation_token)

    assert marker.read_text(encoding="utf-8") == "preserve"


def test_apply_writes_a_complete_package_after_confirmation(sample_spec: SkillSpec):
    plan = build_plan(sample_spec)

    written = apply_plan(plan, plan.confirmation_token)

    assert sample_spec.output_directory / "plugin.json" in written
    assert (sample_spec.output_directory / "skills" / sample_spec.name / "SKILL.md").is_file()


def test_apply_refuses_to_publish_a_staging_bundle_that_fails_formal_validation(
    sample_spec: SkillSpec,
):
    plan = build_plan(sample_spec)
    invalid_files = tuple(
        PlannedFile(file.relative_path, "not json", file.purpose)
        if file.relative_path.as_posix() == "plugin.json"
        else file
        for file in plan.files
    )
    invalid_plan = replace(plan, files=invalid_files)

    with pytest.raises(BundleValidationError, match="MANIFEST_JSON_INVALID"):
        apply_plan(invalid_plan, invalid_plan.confirmation_token)

    assert sample_spec.output_directory.exists() is False


def test_apply_accepts_generated_json_escaped_frontmatter_description(tmp_path: Path):
    description = 'Quoted "text", a backslash \\, and a newline\\nmarker.'
    specification = SkillSpec.from_json(
        json.dumps(
            {
                "name": "release-notes",
                "description": description,
                "body": "Collect verified changes before drafting the release notes.",
                "output_directory": str(tmp_path / "release-notes"),
            }
        )
    )
    plan = build_plan(specification)

    apply_plan(plan, plan.confirmation_token)

    assert specification.output_directory.is_dir()


def test_apply_preserves_a_dangling_final_target_link(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    raw_target = tmp_path / "release-notes"
    missing_destination = tmp_path / "missing-destination"
    try:
        raw_target.symlink_to(missing_destination, target_is_directory=True)
    except OSError:
        link_created = False
        specification = SkillSpec.from_json(
            json.dumps(
                {
                    "name": "release-notes",
                    "description": "Draft release notes from verified changes.",
                    "body": "Collect verified changes before drafting the release notes.",
                    "output_directory": str(tmp_path / "unused-output"),
                }
            )
        )
        plan = replace(build_plan(specification), output_directory=raw_target)
        monkeypatch.setattr(bundle, "_path_lexists", lambda path: path == raw_target)
    else:
        link_created = True
        specification = SkillSpec.from_json(
            json.dumps(
                {
                    "name": "release-notes",
                    "description": "Draft release notes from verified changes.",
                    "body": "Collect verified changes before drafting the release notes.",
                    "output_directory": str(raw_target),
                }
            )
        )
        plan = build_plan(specification)

    with pytest.raises(WriteConflictError):
        apply_plan(plan, plan.confirmation_token)

    if link_created:
        assert os.path.lexists(raw_target)
        assert raw_target.is_symlink()
        assert missing_destination.exists() is False
    else:
        assert raw_target.exists() is False


def test_apply_refuses_a_dangling_link_created_after_the_initial_conflict_check(
    monkeypatch: pytest.MonkeyPatch, sample_spec: SkillSpec
):
    raw_target = sample_spec.output_directory
    missing_destination = raw_target.parent / "missing-destination"
    lexists = bundle._path_lexists
    first_check = True

    def create_link_after_initial_check(path: Path) -> bool:
        nonlocal first_check
        exists = lexists(path)
        if first_check:
            first_check = False
            assert exists is False
            raw_target.symlink_to(missing_destination, target_is_directory=True)
        return exists

    monkeypatch.setattr(bundle, "_path_lexists", create_link_after_initial_check)
    plan = build_plan(sample_spec)

    with pytest.raises(WriteConflictError):
        apply_plan(plan, plan.confirmation_token)

    assert os.path.lexists(raw_target)
    assert raw_target.is_symlink()
    assert missing_destination.exists() is False


def test_apply_refuses_a_target_created_during_publication(
    monkeypatch: pytest.MonkeyPatch, sample_spec: SkillSpec
):
    plan = build_plan(sample_spec)
    publish = bundle._publish_staging_no_clobber

    def target_appears_then_publish(staging_directory: Path, target: Path) -> None:
        target.mkdir()
        (target / "user-file.txt").write_text("preserve", encoding="utf-8")
        publish(staging_directory, target)

    monkeypatch.setattr(bundle, "_publish_staging_no_clobber", target_appears_then_publish)

    with pytest.raises(WriteConflictError):
        apply_plan(plan, plan.confirmation_token)

    marker = sample_spec.output_directory / "user-file.txt"
    assert marker.read_text(encoding="utf-8") == "preserve"
    assert list(sample_spec.output_directory.parent.glob(".release-notes.staging-*")) == []


def test_apply_reports_the_residual_staging_directory_when_cleanup_fails(
    monkeypatch: pytest.MonkeyPatch, sample_spec: SkillSpec
):
    cleanup_paths: list[Path] = []
    real_rmtree = shutil.rmtree

    def fail_staged_write(staging_root: Path, files: tuple[object, ...]) -> None:
        raise RuntimeError("simulated staged write failure")

    def fail_cleanup(path: Path) -> None:
        cleanup_paths.append(path)
        raise OSError("simulated cleanup failure")

    monkeypatch.setattr(bundle, "_write_staged_files", fail_staged_write)
    monkeypatch.setattr(bundle.shutil, "rmtree", fail_cleanup)
    plan = build_plan(sample_spec)

    with pytest.raises(StagingCleanupError) as error:
        apply_plan(plan, plan.confirmation_token)

    assert cleanup_paths == [error.value.path]
    assert str(error.value.path) in str(error.value)
    assert isinstance(error.value.__cause__, OSError)
    assert error.value.path.is_dir()
    real_rmtree(error.value.path)


def test_publication_fails_closed_on_unsupported_platform(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    monkeypatch.setattr(bundle.sys, "platform", "darwin")

    with pytest.raises(PublicationError, match="unsupported"):
        bundle._publish_staging_no_clobber(tmp_path / "staging", tmp_path / "target")
