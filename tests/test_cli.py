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
