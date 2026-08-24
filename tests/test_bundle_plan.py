import json
from pathlib import Path

import pytest

from agent_skillopt.bundle import build_plan, render_preview
from agent_skillopt.errors import SpecError
from agent_skillopt.models import SkillSpec


def test_preview_builds_all_host_files_without_creating_the_target(tmp_path: Path):
    target = tmp_path / "skills" / "release-notes"
    spec = SkillSpec.from_json(
        json.dumps(
            {
                "name": "release-notes",
                "description": (
                    "Draft release notes when a versioned change needs a concise summary."
                ),
                "body": "Collect verified changes before drafting the release notes.",
                "output_directory": str(target),
            }
        )
    )

    preview = render_preview(build_plan(spec))

    assert target.exists() is False
    assert preview["confirmation_token"]
    assert {item["path"] for item in preview["files"]} >= {
        "plugin.json",
        ".codex-plugin/plugin.json",
        ".agents/plugins/marketplace.json",
        ".claude-plugin/plugin.json",
        ".claude-plugin/marketplace.json",
        "skills/release-notes/SKILL.md",
        "README.md",
        "tests/validate_bundle.py",
    }


def test_preview_rejects_an_unnormalized_skill_name(tmp_path: Path):
    with pytest.raises(SpecError, match="lowercase letters, digits, and hyphens"):
        SkillSpec.from_json(
            json.dumps(
                {
                    "name": "Release Notes",
                    "description": "A valid sentence.",
                    "body": "A valid body.",
                    "output_directory": str(tmp_path / "release-notes"),
                }
            )
        )
