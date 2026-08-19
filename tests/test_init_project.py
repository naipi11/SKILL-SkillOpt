import pytest

from agent_skillopt.cli import main
from agent_skillopt.init_project import initialize_project


def test_init_refuses_to_overwrite_existing_config(tmp_path):
    """A user-owned configuration must survive an accidental repeat init command."""
    target = tmp_path / "agent-skillopt.yaml"
    target.write_text("existing", encoding="utf-8")

    with pytest.raises(FileExistsError):
        initialize_project(tmp_path, "searchqa-deepseek", force=False)

    assert target.read_text(encoding="utf-8") == "existing"


def test_init_writes_preset_and_run_ignore(tmp_path):
    """Initialization must create a usable config and ignore generated run artifacts."""
    path = initialize_project(tmp_path, "searchqa-deepseek", force=False)

    assert path.name == "agent-skillopt.yaml"
    assert "runs/" in (tmp_path / ".gitignore").read_text(encoding="utf-8")


def test_init_preserves_existing_ignore_rules(tmp_path):
    """Appending the run artifact rule must not erase unrelated user ignore entries."""
    ignore_path = tmp_path / ".gitignore"
    ignore_path.write_text("private-notes/\n", encoding="utf-8")

    initialize_project(tmp_path, "searchqa-deepseek", force=False)

    assert ignore_path.read_text(encoding="utf-8").splitlines() == ["private-notes/", "runs/"]


def test_init_cli_creates_a_project_configuration(tmp_path):
    """The public init command must expose the same non-destructive behavior as its API."""
    assert main(["init", "--path", str(tmp_path)]) == 0
    assert (tmp_path / "agent-skillopt.yaml").exists()
