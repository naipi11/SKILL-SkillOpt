from pathlib import Path


def test_packaged_source_has_no_retired_training_identifiers():
    source_tree = Path(__file__).parents[1] / "src"
    source_text = "\n".join(
        source_path.read_text(encoding="utf-8") for source_path in source_tree.rglob("*.py")
    )
    retired_identifiers = {
        "SkillOptConfig",
        "ProjectConfig",
        "ConfigurationError",
        "ExecutionGateError",
    }

    found_identifiers = {
        identifier for identifier in retired_identifiers if identifier in source_text
    }

    assert not found_identifiers
