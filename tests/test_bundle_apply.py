import json
from pathlib import Path

import pytest

from agent_skillopt.bundle import apply_plan, build_plan
from agent_skillopt.errors import ConfirmationError, WriteConflictError
from agent_skillopt.models import SkillSpec


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
