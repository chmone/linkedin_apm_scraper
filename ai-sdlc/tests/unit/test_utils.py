import json
from pathlib import Path

import pytest

from ai_sdlc import utils


def test_slugify():
    assert utils.slugify("Hello World!") == "hello-world"
    assert utils.slugify("  Test Slug with Spaces  ") == "test-slug-with-spaces"
    assert utils.slugify("Special!@#Chars") == "special-chars"
    assert utils.slugify("") == "idea"  # As per current implementation


def test_load_config_success(temp_project_dir: Path, mocker):
    mock_aisdlc_content = """
    version = "0.1.0"
    steps = ["01-idea", "02-prd"]
    prompt_dir = "prompts"
    """
    aisdlc_file = temp_project_dir / ".aisdlc"
    aisdlc_file.write_text(mock_aisdlc_content)

    mocker.patch(
        "ai_sdlc.utils.ROOT", temp_project_dir
    )  # Ensure ROOT points to test dir

    config = utils.load_config()
    assert config["version"] == "0.1.0"
    assert config["steps"] == ["01-idea", "02-prd"]


def test_load_config_missing(temp_project_dir: Path, mocker):
    mocker.patch("ai_sdlc.utils.ROOT", temp_project_dir)
    with pytest.raises(SystemExit, match="1"):
        utils.load_config()


def test_load_config_corrupted(temp_project_dir: Path, mocker):
    aisdlc_file = temp_project_dir / ".aisdlc"
    aisdlc_file.write_text("this is not valid toml content {")  # Corrupted TOML
    mocker.patch("ai_sdlc.utils.ROOT", temp_project_dir)
    mocker.patch("sys.exit")  # Prevent test suite from exiting

    # Should call sys.exit(1)
    utils.load_config()
    utils.sys.exit.assert_called_once_with(1)


def test_read_write_lock(temp_project_dir: Path, mocker):
    mocker.patch("ai_sdlc.utils.ROOT", temp_project_dir)
    lock_data = {"slug": "test-slug", "current": "01-idea"}

    # Test write_lock
    utils.write_lock(lock_data)
    lock_file = temp_project_dir / ".aisdlc.lock"
    assert lock_file.exists()
    assert json.loads(lock_file.read_text()) == lock_data

    # Test read_lock
    read_data = utils.read_lock()
    assert read_data == lock_data

    # Test read_lock when file doesn't exist
    lock_file.unlink()
    assert utils.read_lock() == {}

    # Test read_lock with corrupted JSON
    lock_file.write_text("not json {")
    assert utils.read_lock() == {}  # Should return empty dict on corruption
