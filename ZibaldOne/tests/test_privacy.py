import json

from typer.testing import CliRunner

from zibaldone.cli.app import app
from zibaldone.core.privacy import NOTICE_VERSION

runner = CliRunner()


def saved_privacy(folder):
    return json.loads((folder / "settings.json").read_text(encoding="utf-8"))["privacy"]


def test_first_start_shows_notice_and_saves_consent(isolated_data_dir) -> None:
    result = runner.invoke(app, ["data", "path"], input="sì\n")
    assert result.exit_code == 0
    assert "Nessuno, nemmeno chi ha creato l'app" in result.output
    assert str(isolated_data_dir) in result.output
    privacy = saved_privacy(isolated_data_dir)
    assert privacy["accepted"] is True
    assert privacy["notice_version"] == NOTICE_VERSION


def test_refusing_consent_saves_nothing(isolated_data_dir) -> None:
    result = runner.invoke(app, ["data", "path"], input="no\n")
    assert result.exit_code == 1
    assert "non ha salvato nulla" in result.output
    assert not isolated_data_dir.exists()


def test_unclear_answer_is_asked_again(isolated_data_dir) -> None:
    result = runner.invoke(app, ["data", "path"], input="forse\ns\n")
    assert result.exit_code == 0
    assert "Rispondi sì oppure no" in result.output


def test_notice_is_shown_only_once(isolated_data_dir) -> None:
    runner.invoke(app, ["data", "path"], input="s\n")
    result = runner.invoke(app, ["data", "path"])
    assert result.exit_code == 0
    assert result.output.strip() == str(isolated_data_dir)


def test_help_and_version_need_no_consent(isolated_data_dir) -> None:
    for command in (["help"], ["version"], ["data", "path", "--help"]):
        result = runner.invoke(app, command)
        assert result.exit_code == 0
    assert not isolated_data_dir.exists()


def test_privacy_report_before_consent(isolated_data_dir) -> None:
    result = runner.invoke(app, ["privacy"])
    assert result.exit_code == 0
    assert "Rischi" in result.output
    assert "Cartella esiste: no" in result.output
    assert "non ancora dato" in result.output
    assert not isolated_data_dir.exists()


def test_privacy_report_shows_size_and_consent(isolated_data_dir) -> None:
    runner.invoke(app, ["privacy", "accept"])
    result = runner.invoke(app, ["privacy"])
    assert "Cartella esiste: sì" in result.output
    assert "1 file" in result.output
    assert "accettato il" in result.output


def test_revoke_asks_again_and_keeps_files(isolated_data_dir) -> None:
    runner.invoke(app, ["privacy", "accept"])
    result = runner.invoke(app, ["privacy", "revoke"])
    assert result.exit_code == 0
    assert saved_privacy(isolated_data_dir)["accepted"] is False
    assert (isolated_data_dir / "settings.json").exists()
    again = runner.invoke(app, ["data", "path"], input="no\n")
    assert again.exit_code == 1


def test_new_notice_version_asks_again(isolated_data_dir) -> None:
    runner.invoke(app, ["privacy", "accept"])
    settings_file = isolated_data_dir / "settings.json"
    settings = json.loads(settings_file.read_text(encoding="utf-8"))
    settings["privacy"]["notice_version"] = NOTICE_VERSION - 1
    settings_file.write_text(json.dumps(settings), encoding="utf-8")
    result = runner.invoke(app, ["data", "path"], input="no\n")
    assert result.exit_code == 1
