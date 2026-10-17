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


def test_quote_and_about() -> None:
    quote = runner.invoke(app, ["pensiero"])
    assert quote.exit_code == 0 and "«" in quote.output
    about = runner.invoke(app, ["about"])
    for name in ("Leopy", "Hegy", "Archy", "Monty", "Diggy", "Mandy", "Ary", "Hobbsy", "Velo d'ignoranza"):
        assert name in about.output
