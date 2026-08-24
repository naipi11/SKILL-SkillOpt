import io
import json
import sys

from agent_skillopt.cli import main


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
