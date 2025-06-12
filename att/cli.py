import json
import logging
import pathlib
import re

import click

from att.config import Config, configure_logger
from att.dropbox_utils import (
    dropbox_oauth_dev,
    dropbox_oauth_pkce,
)
from att.utils import Archive, FileList

logger = logging.getLogger(__name__)
CONFIG = Config()


def validate_remote_file_format(
    _ctx: click.Context, _remote_file_parameter: str, remote_file_value: str
) -> str:
    """Utility function to validate input.

    Validates the --remote-file input to make sure it matches the "folder/file name.ext"
    format. It uses a regex pattern to verify that format.
    """
    remote_file_pattern = r"^[a-zA-Z0-9][^\/]+[\/][^\/]+\.[^\/]{3,5}$"
    if not re.fullmatch(remote_file_pattern, remote_file_value):
        message = "Parameter not formatted as folder/file name.ext"
        raise click.BadParameter(message, param_hint="--remote-file")
    return remote_file_value


@click.group()
@click.pass_context
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="Pass to log at debug level instead of info",
)
@click.option(
    "-ow",
    "--overwrite",
    is_flag=True,
    default=False,
    help="Whether to overwrite the file if it already exists in the NAS; defaults to FALSE",
)
def cli(ctx: click.Context, *, overwrite: bool, verbose: bool) -> None:
    """The att CLI."""
    ctx.ensure_object(dict)
    configure_logger(logging.getLogger(), verbose=verbose)
    ctx.obj["VERBOSE"] = verbose
    ctx.obj["OVERWRITE"] = overwrite

    CONFIG.check_required_env_vars()
    logger.debug("Environment variables are present and formatted properly")


@cli.command()
def check() -> None:
    """Basic check command to verify Dropbox and NAS access.

    Used to verify that Dropbox and the NAS are accessible.
    """
    if CONFIG.WORKSPACE == "test":
        logger.debug("Test environment, do nothing.")
        return
    if CONFIG.WORKSPACE == "dev":
        dbx = dropbox_oauth_dev()
        logger.info("Successful Dropbox API OAuth via AccessToken")
    else:
        dbx = dropbox_oauth_pkce()
        logger.info("Successful Dropbox OAuth via PKCE")

    if dbx.users_get_current_account().team.name == "MIT":
        logger.info("SUCCESS: Connected to MIT Dropbox")
    else:
        logger.error("ERROR: Not connected to MIT Dropbox")

    nas = pathlib.Path(CONFIG.NAS_FOLDER)
    if nas.exists():
        logger.info("SUCCESS: NAS Folder is connected.")
    else:
        logger.error("ERROR: NAS Folder is not connected.")


@cli.command()
@click.pass_context
@click.option(
    "-rf",
    "--remote-file",
    type=str,
    callback=validate_remote_file_format,
    required=True,
    help="Path, starting with the subfolder name and including the full filename, including the extension (like 'subfolder/filename can contain spaces.ext')",
)
def single_file_copy(_ctx: click.Context, *, remote_file: str) -> None:
    """Copies a single file from Dropbox to NAS.

    This works on one file at a time, copying it from Dropbox to the NAS. Each file moved
    by this command will get put in its own folder in the NAS. The default metadata file
    from Dropbox will get put in this folder along with the SHA256 checksum manifest file.

    What starts as a single file in Dropbox ends up as a folder on the NAS with three
    files: the original file, the default metadata file, and the SHA256 manifest file.

    Args:
        remote_file: the "folder/filename.ext" of the file to move
    Return:
        None
    """
    # Create the Archive object for the specific remote_file specified as a cli parameter
    archive = Archive(remote_file)
    archive.create_nas_folder(overwrite=_ctx.obj["OVERWRITE"])

    # Different options for Dropbox authentication
    if CONFIG.WORKSPACE == "test":
        logger.debug("No OAuth to Dropbox for testing")
        return
    if CONFIG.WORKSPACE == "dev":
        logger.debug("Dopbox API OAuth via AccessToken")
        dbx = dropbox_oauth_dev()
    else:
        logger.debug("Dropbox OAuth via PKCE")
        dbx = dropbox_oauth_pkce()

    # Do the work
    archive.copy_dropbox_to_nas(dbx)
    archive.create_nas_sha_manifest()
    archive.download_metadata(dbx)


@cli.command()
@click.pass_context
@click.option(
    "-rc",
    "--remote-csv",
    type=str,
    callback=validate_remote_file_format,
    required=True,
    help="Path, starting with the subfolder name and including the full CSV filename, including the .csv extension",
)
def bulk_file_copy(ctx: click.Context, *, remote_csv: str) -> None:
    """Bulk copy files, read from a CSV, from Dropbox to the NAS.

    This takes the remote CSV file as an input. It runs through the CSV, copying each
    listed file from Dropbox to the NAS. After the file (and the metadata and the
    checksum manifest) are copied to the NAS, it updates the default metadata file on
    the NAS with the information from the CSV.

    Args:
        ctx: click Context
        remote_csv: The "folder/filename.csv" of the CSV that lists all the files to copy
    Return:
        None
    """
    file_list = FileList(remote_csv)
    if CONFIG.WORKSPACE == "test":
        logger.debug("No OAuth to Dropbox for testing")
    elif CONFIG.WORKSPACE == "dev":
        logger.debug("Dopbox API OAuth via AccessToken")
        dbx = dropbox_oauth_dev()
    else:
        logger.debug("Dropbox OAuth via PKCE")
        dbx = dropbox_oauth_pkce()

    csv_df = file_list.load_csv(dbx)

    for _index, row in csv_df.iterrows():
        archive = Archive(row["filename"])
        archive.create_nas_folder(overwrite=ctx.obj["OVERWRITE"])
        transferdate = archive.copy_dropbox_to_nas(dbx)
        archive.create_nas_sha_manifest()
        archive.download_metadata(dbx)
        with open(archive.nas_metadata_path, encoding="utf-8") as f:
            metadata = json.load(f)
        metadata["Beginning Year"] = str(row["beginning_year"])
        metadata["Ending Year"] = str(row["ending_year"])
        metadata["Description"] = str(row["description"])
        metadata["Transfer Date"] = transferdate
        with open(archive.nas_metadata_path.as_posix(), "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=4)
