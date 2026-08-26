import json
from pathlib import Path

from agent_skillopt.bundle import build_plan
from agent_skillopt.cli import main
from agent_skillopt.models import SkillSpec


def _bundle(tmp_path: Path) -> Path:
    root = tmp_path / "bundle"
    specification = {
        "name": "release-notes",
        "description": "Draft concise release notes from verified changes.",
        "body": """## When to use

Use this for verified changes.

## Procedure

Collect changes and draft notes.

## Output format

Return release notes.

## Safety boundaries

Do not invent changes.
""",
        "output_directory": str(root),
        "test_cases": [
            {
                "name": "happy-path",
                "prompt": "Draft release notes.",
                "required_contains": ["release notes"],
                "forbidden_contains": ["invented change"],
            }
        ],
    }
    plan = build_plan(SkillSpec.from_json(json.dumps(specification)))
    for planned_file in plan.files:
        destination = root.joinpath(*planned_file.relative_path.parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(planned_file.content, encoding="utf-8")
    return root


def test_review_cli_emits_a_json_safety_report(tmp_path: Path, capsys):
    root = _bundle(tmp_path)

    assert main(["review", "--path", str(root)]) == 0

    report = json.loads(capsys.readouterr().out)
    assert report["quality_score"] >= 90
    assert report["security"]["status"] == "pass"
    assert report["executed"] is False


def test_evaluate_cli_emits_a_passing_quality_report(tmp_path: Path, capsys):
    root = _bundle(tmp_path)
    responses = tmp_path / "responses.json"
    responses.write_text(
        json.dumps(
            {"responses": {"happy-path": "These release notes summarize verified changes."}}
        ),
        encoding="utf-8",
    )

    assert main(["evaluate", "--path", str(root), "--responses", str(responses)]) == 0

    report = json.loads(capsys.readouterr().out)
    assert report["evaluation"]["score"] == 100
    assert report["evaluation"]["passed"] == 1


def test_evaluate_cli_returns_one_for_a_failed_case(tmp_path: Path, capsys):
    root = _bundle(tmp_path)
    responses = tmp_path / "responses.json"
    responses.write_text(
        json.dumps({"responses": {"happy-path": "No useful answer."}}), encoding="utf-8"
    )

    assert main(["evaluate", "--path", str(root), "--responses", str(responses)]) == 1

    report = json.loads(capsys.readouterr().out)
    assert report["evaluation"]["failed"] == 1


def test_evaluate_cli_hides_malformed_response_errors(tmp_path: Path, capsys):
    root = _bundle(tmp_path)
    responses = tmp_path / "responses.json"
    responses.write_text("[]", encoding="utf-8")

    assert main(["evaluate", "--path", str(root), "--responses", str(responses)]) == 2

    assert "评估失败：响应文件无效。" in capsys.readouterr().err
