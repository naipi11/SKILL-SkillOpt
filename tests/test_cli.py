import io
import json
import sys
from pathlib import Path

from agent_skillopt.bundle import build_plan
from agent_skillopt.cli import main
from agent_skillopt.models import SkillSpec


def test_help_exposes_the_skill_package_workflow(capsys):
    assert main(["--help"]) == 0
    output = capsys.readouterr().out
    assert "preview" in output
    assert "apply" in output
    assert "validate" in output
    assert "install" in output
    assert "Microsoft SkillOpt" not in output


def test_legacy_training_command_is_not_a_supported_subcommand(capsys):
    assert main(["run"]) == 2
    assert "invalid choice" in capsys.readouterr().err


def test_preview_returns_a_chinese_error_for_a_non_string_resource_kind(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(
            json.dumps(
                {
                    "name": "release-notes",
                    "description": "A valid sentence.",
                    "body": "A valid body.",
                    "output_directory": "bundle-output",
                    "resources": [
                        {"kind": [], "filename": "notes.txt", "content": "Reference material."}
                    ],
                }
            )
        ),
    )

    assert main(["preview", "--spec", "-"]) == 2

    error_output = capsys.readouterr().err
    assert "预览失败：规格无效。" in error_output
    assert "Traceback" not in error_output


def test_apply_hides_specification_content_when_confirmation_is_stale(
    tmp_path: Path, capsys
):
    target = tmp_path / "release-notes"
    specification = {
        "name": "release-notes",
        "description": "Draft release notes from verified changes.",
        "body": "private specification body must not appear in errors",
        "output_directory": str(target),
    }
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(specification), encoding="utf-8")

    assert main(["apply", "--spec", str(spec_path), "--confirm", "stale-token"]) == 2

    error_output = capsys.readouterr().err
    assert "应用失败：确认令牌无效。" in error_output
    assert specification["body"] not in error_output
    assert target.exists() is False


def test_apply_prints_the_published_directory_after_confirmation(tmp_path: Path, capsys):
    target = tmp_path / "release-notes"
    specification = {
        "name": "release-notes",
        "description": "Draft release notes from verified changes.",
        "body": "Collect verified changes before drafting the release notes.",
        "output_directory": str(target),
    }
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(specification), encoding="utf-8")
    token = build_plan(SkillSpec.from_json(json.dumps(specification))).confirmation_token

    assert main(["apply", "--spec", str(spec_path), "--confirm", token]) == 0

    assert f"已创建 Skill 包：{target}" in capsys.readouterr().out
    assert (target / "plugin.json").is_file()
