import json
from pathlib import Path

from agent_skillopt.bundle import build_plan
from agent_skillopt.models import SkillSpec


def _spec(tmp_path: Path, **extra: object) -> SkillSpec:
    payload = {
        "name": "release-notes",
        "description": "Draft concise release notes from verified changes.",
        "body": "Collect verified changes before drafting release notes.",
        "output_directory": str(tmp_path / "release-notes"),
        **extra,
    }
    return SkillSpec.from_json(json.dumps(payload))


def test_every_generated_bundle_contains_a_default_smoke_case(tmp_path: Path):
    plan = build_plan(_spec(tmp_path))

    files = {file.relative_path.as_posix(): file.content for file in plan.files}
    case = json.loads(files["tests/cases/smoke-test.json"])

    assert case == {
        "forbidden_contains": [],
        "name": "smoke-test",
        "prompt": "Describe when to use this Skill and follow its documented procedure.",
        "required_contains": [],
    }


def test_declared_test_cases_are_packaged_deterministically(tmp_path: Path):
    plan = build_plan(
        _spec(
            tmp_path,
            test_cases=[
                {
                    "name": "happy-path",
                    "prompt": "Draft release notes from verified changes.",
                    "required_contains": ["verified changes", "release notes"],
                    "forbidden_contains": ["invented change"],
                }
            ],
        )
    )

    files = {file.relative_path.as_posix(): file.content for file in plan.files}
    assert json.loads(files["tests/cases/happy-path.json"]) == {
        "forbidden_contains": ["invented change"],
        "name": "happy-path",
        "prompt": "Draft release notes from verified changes.",
        "required_contains": ["verified changes", "release notes"],
    }
    assert [path for path in files if path.startswith("tests/cases/")] == [
        "tests/cases/happy-path.json"
    ]
    assert "agent-skillopt review" in files["tests/README.md"]
    assert "agent-skillopt evaluate" in files["tests/README.md"]
    assert "responses.json" in files["tests/README.md"]
