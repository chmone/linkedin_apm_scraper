from pathlib import Path

import pytest


@pytest.fixture
def temp_project_dir(tmp_path: Path):
    """Creates a temporary directory simulating a project root."""
    # tmp_path is a pytest fixture providing a temporary directory unique to the test
    # For more complex setups, you might copy baseline files here
    return tmp_path
