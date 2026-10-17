from typer.testing import CliRunner

from zibaldone import __version__
from zibaldone.cli.app import app

runner = CliRunner()


def test_version_prints_package_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_help_lists_every_command() -> None:
    result = runner.invoke(app, ["help"])
    assert result.exit_code == 0
    for command in ("help", "version", "privacy", "privacy accept", "privacy revoke", "data path"):
        assert command in result.output
    assert "zbone" in result.output


def test_no_arguments_shows_usage() -> None:
    result = runner.invoke(app, [])
    assert "Usage" in result.output
