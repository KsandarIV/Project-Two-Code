from typer.testing import CliRunner

from zibaldone.cli.app import app

runner = CliRunner()


def invoke(*args, input=None):
    return runner.invoke(app, list(args), input=input)


def accept_privacy() -> None:
    assert invoke("privacy", "accept").exit_code == 0


def test_template_create_with_flags_and_entry_flow() -> None:
    accept_privacy()
    result = invoke(
        "template", "create", "Libro",
        "--block", "titolo:text:Titolo!",
        "--block", "voto:rating:Voto",
        "--block", "generi:tags",
        "--option", "voto.max=10",
    )
    assert result.exit_code == 0, result.output
    assert "Modello creato: Libro (libro)" in result.output

    shown = invoke("template", "show", "libro")
    assert "titolo" in shown.output and '"max": 10' in shown.output

    added = invoke("entry", "add", "libro", "--set", "titolo=Dune", "--set", "voto=9", "--set", "generi=fantascienza, deserto", "--day", "2026-10-17")
    assert added.exit_code == 0, added.output
    entry_id = added.output.split("id ")[1].strip(")\n ")

    listed = invoke("entry", "list")
    assert "Dune" in listed.output and "2026-10-17" in listed.output

    detail = invoke("entry", "show", entry_id)
    assert "Voto: ★★★★★★★★★☆" in detail.output
    assert "Generi: fantascienza, deserto" in detail.output

    edited = invoke("entry", "edit", entry_id, "--set", "voto=")
    assert edited.exit_code == 0
    assert "Voto" not in invoke("entry", "show", entry_id).output

    assert invoke("entry", "delete", entry_id, "--yes").exit_code == 0
    assert "Nessuna voce" in invoke("entry", "list").output


def test_interactive_template_and_entry() -> None:
    accept_privacy()
    # name, block label, type, required?, empty label to finish
    answers = "Umore del giorno\nCome sto\n9\nCiao, Bene, Male\nsì\n\n"
    created = invoke("template", "create", input=answers)
    assert created.exit_code == 0, created.output
    added = invoke("entry", "add", "umore_del_giorno", input="\n2\n")
    assert added.exit_code == 0, added.output
    assert "questo blocco è obbligatorio" in added.output
    assert "Voce salvata" in added.output


def test_errors_are_short_messages() -> None:
    accept_privacy()
    missing = invoke("entry", "add", "film", "--set", "titolo=Alien")
    assert missing.exit_code == 1
    assert "non esiste un modello 'film'" in missing.output
    invoke("template", "create", "Film", "--block", "titolo:text:Titolo!")
    wrong = invoke("entry", "add", "film", "--set", "regista=Scott")
    assert wrong.exit_code == 1
    assert "non ha il blocco" in wrong.output
    bad_block = invoke("template", "create", "Prova", "--block", "x:audio")
    assert bad_block.exit_code == 1
    assert "tipo di blocco sconosciuto" in bad_block.output


def test_template_delete_and_block_list() -> None:
    accept_privacy()
    invoke("template", "create", "Film", "--block", "titolo:text:Titolo!")
    assert "longtext" in invoke("template", "blocks").output
    assert invoke("template", "delete", "film", "--yes").exit_code == 0
    assert "Nessun modello" in invoke("template", "list").output


def test_commands_ask_for_consent_first(isolated_data_dir) -> None:
    result = invoke("template", "list", input="no\n")
    assert result.exit_code == 1
    assert not isolated_data_dir.exists()
