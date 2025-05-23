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


## The "special" Dropbox-style SHA256 checksum hash
def dropbox_sha256(file_path: Path) -> str:
    """Generate Dropbox-SHA256 in hexdigest form.

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


## The Archive class for the object that starts in Dropbox
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
        self.dbox_object_path = PurePosixPath(CONFIG.DROPBOX_FOLDER + remote_file)
        self.dbox_metadata_path = PurePosixPath(
            self.dbox_object_path.parent.as_posix() + "/default_metadata.json"
        )
        self.dbox_submission_agreement_folder = self.dbox_object_path.parent.relative_to(
            CONFIG.DROPBOX_FOLDER
        ).as_posix()

        # NAS-specific paths
        self.nas_cleaned_name = self.dbox_object_path.stem.replace(".", "_").replace(
            " ", "_"
        )
        self.nas_folder_path = (
            Path(CONFIG.NAS_FOLDER)
            .joinpath(self.dbox_submission_agreement_folder)
            .joinpath(self.nas_cleaned_name)
        )
        self.nas_object_path = self.nas_folder_path / self.dbox_object_path.name
        self.nas_metadata_path = Path(
            self.nas_object_path.parent.as_posix()
            + "/"
            + self.nas_object_path.stem
            + "_metadata.json"
        )
        self.nas_manifest_path = Path(
            self.nas_object_path.parent.as_posix()
            + "/"
            + self.nas_object_path.stem
            + "_manifest.txt"
        )

    def create_nas_folder(self, overwrite: bool) -> bool:  # noqa: FBT001
        """Create the folder on the NAS.

        Check for the submission agreement folder and then check to see if the
        "archive" has already been copied to the NAS, and then proceed.

        Args:
            overwrite: A boolean to determine if we are willing to overwrite
                a folder on the NAS if it already exists
        Returns:
            bool: True if folder is created (or already exists and overwrite = True)
        """
        if not self.nas_folder_path.parent.exists():
            message = f"The Submission Agreement folder ({self.nas_folder_path.parent}) does not exist yet in the ATT/ folder"
            logger.info(message)
            return False
        if self.nas_folder_path.exists() and (not overwrite):
            message = (
                f"The target folder ({self.nas_folder_path}) already exists on the NAS."
            )
            logger.info(message)
            return False
        self.nas_folder_path.mkdir(mode=0o775, parents=True, exist_ok=True)
        return True

    def dropbox_to_nas(self, dbx: dropbox.Dropbox) -> str:
        """Copy archive file from Dropbox to NAS.

        Copies the file from Dropbox to the NAS and verifies that the file on the NAS has
        the same SHA256 Dropbox-style checksum as the file in Dropbox. We don't need the
        overwrite flag here because we've already processed that flag when we
        created/verified the NAS folder.

        Args:
            dbx: The Dropbox class (authentication)

        Returns:
            str: if the file is copied successfully, return the timestamp of the
                file in Dropbox. If the file is not copied successfully, return an
                empty string.
        """
        try:
            metadata, response = dbx.files_download(self.dbox_object_path.as_posix())

            timestamp = metadata.client_modified.strftime("%Y-%m-%dT%H:%M:%S.00000Z")

            with self.nas_object_path.open("wb") as f:
                f.write(response.content)
            local_dbox_sha = dropbox_sha256(self.nas_object_path)
            if local_dbox_sha == metadata.content_hash:
                logger.debug("The SHA256 checksums match")
                return timestamp
        except ApiError as err:
            if err.error.is_path() and err.error.get_path().is_not_found():
                message = "ERROR: The file %s was not found in Dropbox."
                logger.info(message, self.dbox_object_path)
                raise FileNotFoundError(message, self.dbox_object_path) from err
            message = "ERROR: %s"
            logger.info(message, err)
            raise RuntimeError(message, err) from err
        else:
            message = "ERROR: Checksum validation failed."
            logger.info(message)
            raise RuntimeError(message)

    def nas_sha_manifest(self) -> bool:
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
            logger.info("An unknown error occured.")
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
                logger.info(
                    "ERROR: The file %s was not found in Dropbox.", self.dbox_object_path
                )
            else:
                logger.info("ERROR: %s", err)
            return False
        else:
            return True


# The Class for handling the .csv file passed to the cli
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
        self.dbox_csv_path = PurePosixPath(CONFIG.DROPBOX_FOLDER + remote_csv)
        self.dbox_metadata_path = PurePosixPath(
            self.dbox_csv_path.parent.as_posix() + "/default_metadata.xml"
        )
        self.dbox_submission_agreement_folder = self.dbox_csv_path.parent.relative_to(
            CONFIG.DROPBOX_FOLDER
        ).as_posix()

    def load(self, dbx: dropbox.Dropbox) -> pd.DataFrame:
        """Load CSV content into dataframe.

        Load the content of the .csv file from Dropbox into a dataframe for other
        processing and updates the filename data to include the parent folder so that
        it is in the correct format for processing.

        Args:
            dbx: The authenticated Dropbox session.

        Return:
            pandas.DataFrame: A Pandas DataFrame with all the content from the .csv.
        """
        metadata, response = dbx.files_download(self.dbox_csv_path.as_posix())
        csv_df = pd.read_csv(io.StringIO(response.content.decode("utf-8")))
        csv_df.iloc[:, 0] = (
            self.dbox_submission_agreement_folder + "/" + csv_df.iloc[:, 0].astype(str)
        )
        return csv_df
