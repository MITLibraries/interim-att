# mypy: ignore-errors
import hashlib
import logging
import sys

import dropbox
import six
from dropbox import DropboxOAuth2FlowNoRedirect
from dropbox.common import PathRoot
from dropbox.exceptions import AuthError

from att.config import Config

logger = logging.getLogger(__name__)

CONFIG = Config()

# From https://github.com/dropbox/dropbox-api-content-hasher
# See https://www.dropbox.com/developers/reference/content-hash for the details
# on how Dropbox actually calculates the SHA256 checksum... it's weird.


class DropboxContentHasher:
    """Compute a hash using the same algorithm as Dropbox API.

    Computes a hash using the same algorithm that the Dropbox API uses for the
    the "content_hash" metadata field.

    The digest() method returns a raw binary representation of the hash.  The
    hexdigest() convenience method returns a hexadecimal-encoded version, which
    is what the "content_hash" metadata field uses.

    This class has the same interface as the hashers in the standard 'hashlib'
    package.

    Example:
        hasher = DropboxContentHasher()
        with open('some-file', 'rb') as f:
            while True:
                chunk = f.read(1024)  # or whatever chunk size you want
                if len(chunk) == 0:
                    break
                hasher.update(chunk)
        print(hasher.hexdigest())
    """

    BLOCK_SIZE = 4 * 1024 * 1024

    def __init__(self) -> None:
        self._overall_hasher = hashlib.sha256()
        self._block_hasher = hashlib.sha256()
        self._block_pos = 0
        self.digest_size = self._overall_hasher.digest_size

    def update(self, new_data: bytes) -> None:
        if self._overall_hasher is None:
            message = "can't use this object anymore; you already called digest()"
            raise AssertionError(message)

        assert isinstance(
            new_data, six.binary_type
        ), f"Expecting a byte string, got {format(new_data)}"

        new_data_pos = 0
        while new_data_pos < len(new_data):
            if self._block_pos == self.BLOCK_SIZE:
                self._overall_hasher.update(self._block_hasher.digest())
                self._block_hasher = hashlib.sha256()
                self._block_pos = 0

            space_in_block = self.BLOCK_SIZE - self._block_pos
            part = new_data[new_data_pos : (new_data_pos + space_in_block)]
            self._block_hasher.update(part)

            self._block_pos += len(part)
            new_data_pos += len(part)

    def _finish(self) -> "hashlib._Hash":
        if self._overall_hasher is None:
            message = "can't use this object anymore; you already called digest() or hexdigest()"
            raise AssertionError(message)
        if self._block_pos > 0:
            self._overall_hasher.update(self._block_hasher.digest())
            self._block_hasher = None
        h = self._overall_hasher
        self._overall_hasher = None  # Make sure we can't use this object anymore.
        return h

    def digest(self) -> bytes:
        return self._finish().digest()

    def hexdigest(self) -> str:
        return self._finish().hexdigest()

    def copy(self) -> "DropboxContentHasher":
        c = DropboxContentHasher.__new__(DropboxContentHasher)
        c._overall_hasher = self._overall_hasher.copy()
        c._block_hasher = self._block_hasher.copy()
        c._block_pos = self._block_pos
        return c


def dropbox_oauth_pkce() -> dropbox.Dropbox:
    """Dropbox API PKCE OAuth.

    This is based on the PKCE auth flow described here:
    https://github.com/dropbox/dropbox-sdk-python/blob/main/example/oauth/commandline-oauth-pkce.py

    This uses the `.with_path_root` method to ensure that the User has access
    to the Team Folder

    Args: None
    Return: Dropbox OAuth authorization object
    """
    auth_flow = DropboxOAuth2FlowNoRedirect(
        CONFIG.DROPBOX_APP_KEY, use_pkce=True, token_access_type="offline"  # noqa: S106
    )

    authorize_url = auth_flow.start()
    print("1. Go to: " + authorize_url)
    print('2. Click "Allow" (you might have to log in first).')
    print("3. Copy the authorization code.")
    auth_code = input("Enter the authorization code here: ").strip()

    try:
        oauth_result = auth_flow.finish(auth_code)
    except Exception as e:  # noqa: BLE001
        print(f"Error: {e}")
        sys.exit(1)

    with dropbox.Dropbox(
        oauth2_refresh_token=oauth_result.refresh_token, app_key=CONFIG.DROPBOX_APP_KEY
    ) as dbx:
        account_info = dbx.users_get_current_account()
    logger.debug("Successfully set up client via PKCE.")
    root_namespace_id = account_info.root_info.root_namespace_id
    return dropbox.Dropbox(
        oauth_result.access_token,
    ).with_path_root(PathRoot.root(root_namespace_id))


def dropbox_oauth_dev() -> dropbox.Dropbox:
    """Dropbox OAuth using Pregenerated Token.

    Only used in development work. Requires that a manager of the app can click
    the Generate button on the Dropbox App settings page. This saves a few
    clicks on each run.

    This uses the `.with_path_root` method to ensure that the User has access
    to the Team Folder

    Args: None
    Return: Dropbox OAuth authorization object
    """
    # Only for user testing with a pre-generated ACCESS TOKEN
    with dropbox.Dropbox(CONFIG.DROPBOX_ACCESS_TOKEN) as dbx:
        # Check that the access token is valid
        try:
            account_info = dbx.users_get_current_account()
        except AuthError:
            sys.exit(
                "ERROR: Invalid access token; try re-generating an "
                "access token from the app console on the web."
            )
    logger.debug("Successfully set up client via ACCESS_TOKEN.")
    root_namespace_id = account_info.root_info.root_namespace_id
    return dropbox.Dropbox(CONFIG.DROPBOX_ACCESS_TOKEN).with_path_root(
        PathRoot.root(root_namespace_id)
    )
