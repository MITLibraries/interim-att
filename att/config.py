import logging
import os
from typing import Any


class Config:
    REQUIRED_ENV_VARS = ("WORKSPACE", "DROPBOX_APP_KEY", "DROPBOX_FOLDER", "NAS_FOLDER")
    OPTIONAL_ENV_VARS = "DROPBOX_ACCESS_TOKEN"

    def __getattr__(self, name: str) -> Any:  # noqa: ANN401
        """Provide dot notation access to configurations and env vars on this class."""
        if name in self.REQUIRED_ENV_VARS or name in self.OPTIONAL_ENV_VARS:
            return os.getenv(name)
        message = f"'{name}' not a valid configuration variable"
        raise AttributeError(message)

    def check_required_env_vars(self) -> None:
        """Method to raise exception if required env vars not set."""
        missing_vars = [var for var in self.REQUIRED_ENV_VARS if not os.getenv(var)]
        if missing_vars:
            message = f"Missing required environment variables: {', '.join(missing_vars)}"
            raise AttributeError(message)
        self.check_env_var_format()

    def validate_folder_env_var_format(self) -> None:
        """Mathod to raise exception if an env var is not formatted correctly."""
        dropbox_folder = str(os.getenv(self.REQUIRED_ENV_VARS[2]))
        if not (dropbox_folder.startswith("/") and dropbox_folder.endswith("/")):
            message = "DROPBOX_FOLDER is missing a leading and or trailing slash"
            raise AttributeError(message)

        nas_folder = str(os.getenv(self.REQUIRED_ENV_VARS[3]))
        if not (nas_folder[-1:] == "/" or nas_folder[-1:] == "\\"):
            message = "NAS_FOLDER is missing a trailing slash"
            raise AttributeError(message)


def configure_logger(logger: logging.Logger, *, verbose: bool) -> str:
    if verbose:
        logging.basicConfig(
            format="%(asctime)s %(levelname)s %(name)s.%(funcName)s() line %(lineno)d: "
            "%(message)s"
        )
        logger.setLevel(logging.DEBUG)
    else:
        logging.basicConfig(
            format="%(asctime)s %(levelname)s %(name)s.%(funcName)s(): %(message)s"
        )
        logger.setLevel(logging.INFO)
        for handler in logging.root.handlers:
            handler.addFilter(logging.Filter("att"))
    return (
        f"Logger '{logger.name}' configured with level="
        f"{logging.getLevelName(logger.getEffectiveLevel())}"
    )
