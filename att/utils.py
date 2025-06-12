import hashlib
import io
import logging
from pathlib import Path, PurePosixPath

import dropbox
import pandas as pd
from dropbox.exceptions import ApiError

from att.config import Config
from att.dropbox_utils import DropboxContentHasher

logger = logging.getLogger(__name__)

CONFIG = Config()


class Archive:
    """An Archive object, starting in Dropbox.

    A single file, sourced from Dropbox. From this original file in Dropbox, it builds
    out a set of properties that contain details of its location in Dropbox and its
    eventual location on the NAS. There are methods that handle the secure,
    checksum-validated copy from Dropbox to NAS, including the creation of the target
    location for the file on the NAS.
    """

    def __init__(self, remote_file: str):
        """Initialize the object.

        As part of the intialization of the object, we set a bunch of paths that
        are needed in the various methods. This includes PurePosixPaths for the
        "archive" in Dropbox and the associated default_metadata.json file in
        Dropbox.

        It also includes the cleaned name (strip periods and spaces) of the
        "archive" folder for the NAS (this is just a string) and the Path objects
        for the "archive" on the NAS and the default_metadata.json file that this
        tool will generate on the NAS.

        Args:
            remote_file (str): The relative path to the object inside the
                ArchivesTransfer folder (always in the form "folder/filename.ext")
        """
        # Set the baseline properties for the object starting with the relative
        # path and the CONFIG environment values.
        # Dropbox-specific paths
        self.dbox_object_path = PurePosixPath(CONFIG.DROPBOX_FOLDER) / remote_file
        self.dbox_metadata_path = self.dbox_object_path.parent / "default_metadata.json"
        self.dbox_submission_agreement_folder = self.dbox_object_path.parent.relative_to(
            CONFIG.DROPBOX_FOLDER
        ).as_posix()

        # NAS-specific paths
        self.nas_cleaned_name = self.dbox_object_path.stem.replace(".", "_").replace(
            " ", "_"
        )
        self.nas_folder_path = (
            Path(CONFIG.NAS_FOLDER)
            / self.dbox_submission_agreement_folder
            / self.nas_cleaned_name
        )
        self.nas_object_path = self.nas_folder_path / self.dbox_object_path.name
        self.nas_metadata_path = (
            self.nas_object_path.parent / f"{self.nas_object_path.stem}_metadata.json"
        )
        self.nas_manifest_path = (
            self.nas_object_path.parent / f"{self.nas_object_path.stem}_manifest.txt"
        )

    @staticmethod
    def dropbox_sha256(file_path: Path) -> str:
        """Generate Dropbox-SHA256 in hexdigest form.

        This is the special Dropbox style SHA256 checksum.

        Args:
            file_path: The full pathlib.Path to the file on the local machine

        Return:
            string: Dropbox-specific SHA256 checksum in hexdigest form
        """
        hasher = DropboxContentHasher()
        with file_path.open("rb") as f:
            while True:
                chunk = f.read(4096)
                if len(chunk) == 0:
                    break
                hasher.update(chunk)
        logger.debug("Dropbox style SHA256 generated for %s", file_path.name)
        return hasher.hexdigest()

    def create_nas_folder(self, *, overwrite: bool = False) -> None:
        """Create the folder on the NAS.

        Check for the submission agreement folder and then check to see if the
        "archive" has already been copied to the NAS.

        Args:
            overwrite: A boolean to determine if we are willing to overwrite
                a folder on the NAS if it already exists
        """
        if not self.nas_folder_path.parent.exists():
            message = f"The Submission Agreement folder ({self.nas_folder_path.parent}) does not exist yet in the ATT/ folder"
            logger.error(message)
            raise FileNotFoundError(message)

        if self.nas_folder_path.exists() and (not overwrite):
            message = (
                f"The target folder ({self.nas_folder_path}) already exists on the NAS."
            )
            logger.error(message)
            raise FileExistsError(message)

        self.nas_folder_path.mkdir(mode=0o775, parents=True, exist_ok=True)

    def copy_dropbox_to_nas(self, dbx: dropbox.Dropbox) -> str:
        """Copy archive file from Dropbox to NAS.

        This proceeds in three distinct steps.
        1. Try to copy file from Dropbox.
        2. Try to upload file to the NAS
        3. Confirm Dropbox-style checksum for file on NAS.

        Args:
            dbx: The Dropbox class (authentication)

        Returns:
            str: if the file is copied successfully, return the timestamp of the
                file in Dropbox. If the file is not copied successfully, return an
                empty string.
        """
        # 1. Download from Dropbox
        try:
            metadata, response = dbx.files_download(self.dbox_object_path.as_posix())
        except ApiError as err:
            if err.error.is_path() and err.error.get_path().is_not_found():
                message = "ERROR: The file %s was not found in Dropbox."
                logger.info(message, self.dbox_object_path)
                raise FileNotFoundError(message, self.dbox_object_path) from err
            message = "ERROR: %s"
            logger.info(message, err)
            raise RuntimeError(message, err) from err
        except:  # noqa: E722
            message = "ERROR: unhandled Dropbox download error"
            logger.exception(message)
            raise RuntimeError(message) from None

        timestamp = metadata.client_modified.strftime("%Y-%m-%dT%H:%M:%S.00000Z")

        # 2. Upload to NAS
        try:
            with self.nas_object_path.open("wb") as f:
                f.write(response.content)
        except:  # noqa: E722
            message = "ERROR: could not write to NAS"
            logger.exception(message)
            raise RuntimeError(message) from None

        # 3. Validate checksum
        local_dbox_sha = self.dropbox_sha256(self.nas_object_path)
        if local_dbox_sha != metadata.content_hash:
            message = "ERROR: Checksum validation failed."
            logger.info(message)
            raise RuntimeError(message)
        logger.debug("The SHA256 checksums match.")
        return timestamp

    def create_nas_sha_manifest(self) -> bool:
        """Create manifest for Archive on NAS.

        Creates a standard SHA256 hexdigest for the archive file after it is copied
        to the NAS.

        Returns:
            bool: True if the manifest is created.
        """
        hash_sha256 = hashlib.sha256()
        try:
            with self.nas_object_path.open("rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            with self.nas_manifest_path.open("w") as f:
                f.write(f"{hash_sha256.hexdigest()}  {self.nas_object_path.name}\n")
        except:  # noqa: E722
            logger.exception("An unknown error occured.")
            return False
        else:
            return True

    def download_metadata(self, dbx: dropbox.Dropbox) -> bool:
        """Download the default metadata.json file.

        This makes no changes to the default metadata.json file, it just copies it
        to the NAS together with the archive file.

        Args:
            dbx: The Dropbox class (authentication)

        Returns:
            bool: True if download is successful
        """
        try:
            metadata, response = dbx.files_download(self.dbox_metadata_path.as_posix())
            with self.nas_metadata_path.open("wb") as f:
                f.write(response.content)
        except ApiError as err:
            if err.error.is_path() and err.error.get_path().is_not_found():
                logger.exception(
                    "ERROR: The file %s was not found in Dropbox.", self.dbox_object_path
                )
            else:
                logger.exception("ERROR: %s", err.error)
            return False
        else:
            return True


class FileList:
    """A CSV object, sourced from Dropbox.

    This models the .csv file that is passed to the csv command for the cli application.
    """

    def __init__(self, remote_csv: str):
        """Initialize the object.

        This is used when the submitter has uploaded a collection of files along with
        the file-specific metadata in a .csv that is stored alongside the uploaded
        objects.

        Args:
            remote_csv (str): The relative path to the csv inside the
                ArchivesTransfer folder (always in the form "folder/filename.csv")
        """
        # Set the baseline properties for the object starting with the relative
        # path and the CONFIG environment values.
        # Dropbox-specific paths
        self.dbox_csv_path = PurePosixPath(CONFIG.DROPBOX_FOLDER) / remote_csv
        self.dbox_metadata_path = self.dbox_csv_path.parent / "default_metadata.xml"
        self.dbox_submission_agreement_folder = self.dbox_csv_path.parent.relative_to(
            PurePosixPath(CONFIG.DROPBOX_FOLDER)
        ).as_posix()

    def load_csv(self, dbx: dropbox.Dropbox) -> pd.DataFrame:
        """Load CSV content into dataframe.

        Load the content of the CSV file from Dropbox into a dataframe for other
        processing and updates the filename data to include the parent folder so that
        it is in the correct format for processing.

        Args:
            dbx: The authenticated Dropbox session.

        Return:
            pandas.DataFrame: A Pandas DataFrame with all the content from the CSV.
        """
        metadata, response = dbx.files_download(self.dbox_csv_path.as_posix())
        csv_df = pd.read_csv(io.StringIO(response.content.decode("utf-8")))
        csv_df["filename"] = (
            csv_df["filename"]
            .astype(str)
            .apply(lambda filename: f"{self.dbox_submission_agreement_folder}/{filename}")
        )
        return csv_df
