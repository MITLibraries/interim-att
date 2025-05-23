# mypy: ignore-errors
import logging

import pytest

from att.config import Config, configure_logger


def test_configure_logger_not_verbose():
    logger = logging.getLogger(__name__)
    result = configure_logger(logger, verbose=False)
    info_log_level = 20
    assert logger.getEffectiveLevel() == info_log_level
    assert result == "Logger 'tests.test_config' configured with level=INFO"


def test_configure_logger_verbose():
    logger = logging.getLogger(__name__)
    result = configure_logger(logger, verbose=True)
    debug_log_level = 10
    assert logger.getEffectiveLevel() == debug_log_level
    assert result == "Logger 'tests.test_config' configured with level=DEBUG"


def test_config_check_required_env_vars_pass(config_instance):
    config_instance.check_required_env_vars()


def test_config_check_env_var_format_pass(config_instance):
    config_instance.check_env_var_format()


def test_config_env_dot_notation():
    config = Config()
    assert config.WORKSPACE == "test"


# negative tests for env vars
def test_invalid_config_attribute_raises():
    config = Config()
    with pytest.raises(AttributeError) as excinfo:
        _ = config.NOT_A_REAL_VAR
    assert "'NOT_A_REAL_VAR' not a valid configuration variable" in str(excinfo.value)


def test_config_check_env_var_format_fail_dropbox_folder(monkeypatch):
    monkeypatch.setenv("DROPBOX_FOLDER", "/foldername")
    config = Config()
    with pytest.raises(
        AttributeError, match="DROPBOX_FOLDER is missing a leading and or trailing slash"
    ):
        config.check_env_var_format()


def test_config_check_env_var_format_fail_nas_folder_macos(monkeypatch):
    monkeypatch.setenv("NAS_FOLDER", "path/to/folder")
    config = Config()
    with pytest.raises(AttributeError, match="NAS_FOLDER is missing a trailing slash"):
        config.check_env_var_format()


def test_config_check_env_var_format_fail_nas_folder_windows(monkeypatch):
    monkeypatch.setenv("NAS_FOLDER", r"C:\path\to\folder")
    config = Config()
    with pytest.raises(AttributeError, match="NAS_FOLDER is missing a trailing slash"):
        config.check_env_var_format()


def test_config_check_required_env_vars_fail_missing(monkeypatch):
    monkeypatch.delenv("WORKSPACE", raising=False)
    config = Config()
    with pytest.raises(
        AttributeError, match="Missing required environment variables: WORKSPACE"
    ):
        config.check_required_env_vars()
