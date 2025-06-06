# mypy: ignore-errors
from unittest.mock import MagicMock

import click
import pytest
from click.testing import CliRunner

from att.config import Config
from att.utils import Archive


@pytest.fixture(autouse=True)
def _test_env(monkeypatch, request):
    monkeypatch.setenv("WORKSPACE", "test")
    monkeypatch.setenv("DROPBOX_APP_KEY", "rand0mcharact3rs")
    monkeypatch.setenv("DROPBOX_FOLDER", "/foldername/")
    monkeypatch.setenv("NAS_FOLDER", "/path/to/folder/")


@pytest.fixture
def config_instance():
    return Config()


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def ctx():
    return MagicMock(spec=click.Context)


@pytest.fixture
def archive_nas_exists(tmp_path):
    # Create a dummy Archive object with a test file path
    test_file = "testfolder/testfile.zip"
    archive = Archive(test_file)
    # Patch the NAS folder and file paths to use the tmp_path
    archive.nas_folder_path = tmp_path / "testfolder" / "testfile_zip"
    archive.nas_object_path = archive.nas_folder_path / "testfile.zip"
    archive.nas_folder_path.mkdir(parents=True, exist_ok=True)
    return archive


@pytest.fixture
def archive_nas_does_not_exist(tmp_path):
    # Create a dummy Archive object with a test file path
    test_file = "testfolder/testfile.zip"
    archive = Archive(test_file)
    # Patch the NAS folder and file paths to use the tmp_path
    archive.nas_folder_path = tmp_path / "testfolder" / "testfile_zip"
    archive.nas_object_path = archive.nas_folder_path / "testfile.zip"
    return archive
