from pathlib import Path

import pytest


@pytest.fixture
def tmp_output(tmp_path: Path) -> Path:
    return tmp_path / "output"
