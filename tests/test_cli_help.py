from agent_skillopt.cli import main


def test_help_returns_zero_and_names_product(capsys):
    """A missing or renamed top-level command must be visible to users."""
    assert main(["--help"]) == 0
    assert "Agent-SkillOpt" in capsys.readouterr().out
