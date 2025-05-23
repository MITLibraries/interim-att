# mypy: ignore-errors
import logging
from pathlib import Path, PurePosixPath
from unittest.mock import MagicMock, patch

import pytest
from dropbox.exceptions import ApiError

from att.utils import Archive


# Some mocks that are used later
class MockMetadata:
    def __init__(self):
        import datetime

        self.client_modified = datetime.datetime(1900, 1, 23, 4, 56, 7)  # noqa: DTZ001
        self.content_hash = "mockedhash"


class MockResponse:
    content = b"filecontent"


# Tests for core properties/attributes of the class
def test_dbox_object_path(archive_nas_does_not_exist):
    """Test Archive class initialization for dbox_object_path property."""
    assert archive_nas_does_not_exist.dbox_object_path == PurePosixPath(
        "/foldername/testfolder/testfile.zip"
    )


def test_dbox_metadata_path(archive_nas_does_not_exist):
    """Test Archive class initialization for dbox_metadata_path property."""
    assert archive_nas_does_not_exist.dbox_metadata_path == PurePosixPath(
        "/foldername/testfolder/default_metadata.json"
    )


def test_dbox_submission_agreement_folder(archive_nas_does_not_exist):
    """Test Archive class initialization for dbox_submission_agreement_folder property."""
    assert archive_nas_does_not_exist.dbox_submission_agreement_folder == "testfolder"


def test_nas_cleaned_name():
    """Test Archive class initialization for nas_cleaned_name property."""
    remote_file = "folder/file name_with.spaces.pdf"
    response = Archive(remote_file)
    assert response.nas_cleaned_name == "file_name_with_spaces"


def test_nas_folder_path_macos():
    """Test Archive class initialization for nas_folder_path property for macOS."""
    remote_file = "folder/file name_with.spaces.pdf"
    response = Archive(remote_file)
    assert response.nas_folder_path == Path(
        "/path/to/folder/folder/file_name_with_spaces"
    )


def test_nas_folder_path_windows(monkeypatch):
    """Test Archive class initialization for nas_folder_path property for Windows."""
    monkeypatch.setenv("NAS_FOLDER", "Y:/folder/")
    remote_file = "folder/file name_with.spaces.pdf"
    response = Archive(remote_file)
    assert response.nas_folder_path == Path("Y:/folder/folder/file_name_with_spaces")


def test_nas_object_path_macos():
    """Test Archive class initialization for nas_object_path property for macOS."""
    remote_file = "folder/file name_with.spaces.pdf"
    response = Archive(remote_file)
    assert response.nas_object_path == Path(
        "/path/to/folder/folder/file_name_with_spaces/file name_with.spaces.pdf"
    )


def test_nas_object_path_windows(monkeypatch):
    """Test Archive class initialization for nas_object_path property for Windows."""
    monkeypatch.setenv("NAS_FOLDER", "Y:/folder/")
    remote_file = "folder/file name_with.spaces.pdf"
    response = Archive(remote_file)
    assert response.nas_object_path == Path(
        "Y:/folder/folder/file_name_with_spaces/file name_with.spaces.pdf"
    )


def test_nas_metadata_path_macos():
    """Test Archive class initialization for nas_metadata_path property for macOS."""
    remote_file = "folder/file name_with.spaces.pdf"
    response = Archive(remote_file)
    assert response.nas_metadata_path == Path(
        "/path/to/folder/folder/file_name_with_spaces/file name_with.spaces_metadata.json"
    )


def test_nas_metadata_path_windows(monkeypatch):
    """Test Archive class initialization for nas_metadata_path property for Windows."""
    monkeypatch.setenv("NAS_FOLDER", "Y:/folder/")
    remote_file = "folder/file name_with.spaces.pdf"
    response = Archive(remote_file)
    assert response.nas_metadata_path == Path(
        "Y:/folder/folder/file_name_with_spaces/file name_with.spaces_metadata.json"
    )


def test_nas_manifest_path_macos():
    """Test Archive class initialization for nas_manifest_path property for macOS."""
    remote_file = "folder/file name_with.spaces.pdf"
    response = Archive(remote_file)
    assert response.nas_manifest_path == Path(
        "/path/to/folder/folder/file_name_with_spaces/file name_with.spaces_manifest.txt"
    )


def test_nas_manifest_path_windows(monkeypatch):
    """Test Archive class initialization for nas_manifest_path property for Windows."""
    monkeypatch.setenv("NAS_FOLDER", "Y:/folder/")
    remote_file = "folder/file name_with.spaces.pdf"
    response = Archive(remote_file)
    assert response.nas_manifest_path == Path(
        "Y:/folder/folder/file_name_with_spaces/file name_with.spaces_manifest.txt"
    )


## Tests for the create_nas_folder logic
def test_create_nas_folder_no_submission_agreement_overwrite(
    monkeypatch, tmp_path, caplog
):
    """Test for missing Submission Agreement Folder.

    Verifies correct behavior if the Submission Agreement folder does not exist
    yet (overwrite = True)
    """
    monkeypatch.setenv("NAS_FOLDER", tmp_path.as_posix())
    remote_file = "folder/filename.pdf"
    overwrite = True
    response = Archive(remote_file)
    with caplog.at_level(logging.INFO):
        response.create_nas_folder(overwrite)
        assert "does not exist" in caplog.text


def test_create_nas_folder_no_submission_agreement_no_overwrite(
    monkeypatch, tmp_path, caplog
):
    """Test for missing Submission Agreement Folder.

    Verifies correct behavior if the Submission Agreement folder does not exist
    yet (overwrite = False)
    """
    monkeypatch.setenv("NAS_FOLDER", tmp_path.as_posix())
    remote_file = "folder/filename.pdf"
    overwrite = False
    response = Archive(remote_file)
    with caplog.at_level(logging.INFO):
        response.create_nas_folder(overwrite)
        assert "does not exist" in caplog.text


def test_create_nas_folder_filename_overwrite(monkeypatch, tmp_path):
    """Test for missing Submission Agreement Folder.

    Verifies correct behavior if the clean target folder in the Submission
    Agreement folder does exist (overwrite = True)
    """
    monkeypatch.setenv("NAS_FOLDER", tmp_path.as_posix())
    submission_agreement = tmp_path / "folder" / "filename"
    submission_agreement.mkdir(parents=True)
    remote_file = "folder/filename.pdf"
    overwrite = True
    response = Archive(remote_file)
    assert response.create_nas_folder(overwrite) is True


def test_create_nas_folder_filename_no_overwrite(monkeypatch, tmp_path, caplog):
    """Test for missing Submission Agreement Folder.

    Verifies correct behavior if the clean target folder in the Submission
    Agreement folder does exist (overwrite = False)
    """
    monkeypatch.setenv("NAS_FOLDER", tmp_path.as_posix())
    submission_agreement = tmp_path / "folder" / "filename"
    submission_agreement.mkdir(parents=True)
    remote_file = "folder/filename.pdf"
    overwrite = False
    response = Archive(remote_file)
    with caplog.at_level(logging.INFO):
        response.create_nas_folder(overwrite)
        assert "already exists" in caplog.text


def test_create_nas_folder_no_filename_overwrite(monkeypatch, tmp_path):
    """Test for missing Submission Agreement Folder.

    Verifies correct behavior if the Submission Agreement folder does exist
    yet (overwrite = False)
    """
    monkeypatch.setenv("NAS_FOLDER", tmp_path.as_posix())
    submission_agreement = tmp_path / "folder"
    submission_agreement.mkdir(parents=True)
    remote_file = "folder/filename.pdf"
    overwrite = True
    response = Archive(remote_file)
    assert response.create_nas_folder(overwrite) is True


def test_create_nas_folder_no_filename_no_overwrite(monkeypatch, tmp_path):
    """Test for missing Submission Agreement Folder.

    Verifies correct behavior if the Submission Agreement folder does exist
    yet (overwrite = False)
    """
    monkeypatch.setenv("NAS_FOLDER", tmp_path.as_posix())
    submission_agreement = tmp_path / "folder"
    submission_agreement.mkdir(parents=True)
    remote_file = "folder/filename.pdf"
    overwrite = False
    response = Archive(remote_file)
    assert response.create_nas_folder(overwrite) is True


## Tests for Dropbox actions
def test_dropbox_to_nas(monkeypatch, tmp_path, archive_nas_does_not_exist):
    """Test copy from Dropbox to NAS."""
    monkeypatch.setenv("NAS_FOLDER", tmp_path.as_posix())
    submission_agreement = tmp_path / "testfolder"
    submission_agreement.mkdir(parents=True)
    dbx = MagicMock()
    assert archive_nas_does_not_exist.create_nas_folder(dbx) is True


@patch("att.utils.dropbox_sha256", return_value="mockedhash")
def test_dropbox_to_nas_success(mock_sha, archive_nas_exists):
    """Test that successful copy returns a timestamp."""
    dbx = MagicMock()
    dbx.files_download.return_value = (MockMetadata(), MockResponse())

    timestamp = archive_nas_exists.dropbox_to_nas(dbx)

    assert archive_nas_exists.nas_object_path.exists()
    assert timestamp == "1900-01-23T04:56:07.00000Z"


@patch("att.utils.dropbox_sha256", return_value="wronghash")
def test_dropbox_to_nas_checksum_fail(mock_sha, archive_nas_exists):
    """Test that mismatch checksums raises error."""
    dbx = MagicMock()
    dbx.files_download.return_value = (MockMetadata(), MockResponse())

    # Should raise error due to ApiError
    with pytest.raises(RuntimeError):
        archive_nas_exists.dropbox_to_nas(dbx)


def test_dropbox_to_nas_apierror_file_not_found(archive_nas_exists):
    """Test that a Dropbox API Error is_not_found raises FileNotfound."""
    dbx = MagicMock()

    # Simulate ApiError with .error.is_path() and .error.get_path().is_not_found()
    class DummyError:
        def is_path(self):
            return True

        def get_path(self):
            class NotFound:
                def is_not_found(self):
                    return True

            return NotFound()

    api_error = ApiError("request_id", DummyError(), "user_message", "en-US")
    dbx.files_download.side_effect = api_error

    # Should raise FileNotFoundError due to ApiError
    with pytest.raises(FileNotFoundError):
        archive_nas_exists.dropbox_to_nas(dbx)


def test_dropbox_to_nas_apierror_other(archive_nas_exists):
    """Test that a Dropbox API Error raises error."""
    dbx = MagicMock()

    # Simulate ApiError that is not a path error
    class DummyError:
        def is_path(self):
            return False

        def get_path(self):
            return False

    api_error = ApiError("request_id", DummyError(), "user_message", "en-US")
    dbx.files_download.side_effect = api_error

    # Should raise RuntimeError due to ApiError
    with pytest.raises(RuntimeError):
        archive_nas_exists.dropbox_to_nas(dbx)
