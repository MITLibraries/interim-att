# mypy: ignore-errors
from unittest.mock import patch

import click
import pytest
from click.testing import CliRunner

from att.cli import cli, validate_remote_file_format


# Basic tests for Click
def test_cli_help():
    """Test att runs --help."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0


def test_cli_no_command_fail():
    """Test att fails without a command."""
    runner = CliRunner()
    result = runner.invoke(cli)
    assert result.exit_code == 2  # noqa: PLR2004


def test_cli_verbose():
    """Test core att cli using --verbose flag."""
    runner = CliRunner()
    with patch("att.cli.configure_logger") as mock_config_logger:
        runner.invoke(cli, ["--verbose", "file"])
        mock_config_logger.assert_called_once()
        assert mock_config_logger.call_args[1]["verbose"] is True


# positive tests
def test_remote_file_success_ext3(ctx):
    response = validate_remote_file_format(ctx, "--remote_file", "folder/file name.ext")
    assert response == "folder/file name.ext"


def test_remote_file_success_ext4(ctx):
    response = validate_remote_file_format(ctx, "--remote_file", "folder/file name.exts")
    assert response == "folder/file name.exts"


def test_remote_file_success_extra_dots(ctx):
    response = validate_remote_file_format(ctx, "--remote_file", "folder/file.name.exts")
    assert response == "folder/file.name.exts"


# negative tests
def test_remote_file_fail_leading_slash(ctx):
    with pytest.raises(click.BadParameter) as excinfo:
        validate_remote_file_format(ctx, "--remote_file", "/folder/file name.ext")
    assert "Parameter not formatted as folder/file name.ext" in str(excinfo)


def test_remote_file_fail_trailing_slash(ctx):
    with pytest.raises(click.BadParameter) as excinfo:
        validate_remote_file_format(ctx, "--remote_file", "folder/file name.ext/")
    assert "Parameter not formatted as folder/file name.ext" in str(excinfo)


def test_remote_file_fail_no_slash(ctx):
    with pytest.raises(click.BadParameter) as excinfo:
        validate_remote_file_format(ctx, "--remote_file", "folder.file name.ext")
    assert "Parameter not formatted as folder/file name.ext" in str(excinfo)


def test_remote_file_fail_no_extension(ctx):
    with pytest.raises(click.BadParameter) as excinfo:
        validate_remote_file_format(ctx, "--remote_file", "folder/file name")
    assert "Parameter not formatted as folder/file name.ext" in str(excinfo)


def test_remote_file_fail_two_slashes(ctx):
    with pytest.raises(click.BadParameter) as excinfo:
        validate_remote_file_format(ctx, "--remote_file", "folder//file name.ext")
    assert "Parameter not formatted as folder/file name.ext" in str(excinfo)
