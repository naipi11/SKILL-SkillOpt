from pathlib import Path
from shutil import copytree

import pytest


@pytest.fixture(scope="session")
def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture
def minimal_bundle(tmp_path: Path, project_root: Path) -> Path:
    destination = tmp_path / "minimal-skill"
    copytree(project_root / "tests" / "fixtures" / "minimal-skill", destination)
    return destination


@pytest.fixture
def valid_bundle(minimal_bundle: Path) -> Path:
    return minimal_bundle
