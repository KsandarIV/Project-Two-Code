from typer.testing import CliRunner

from zibaldone.cli.anon_cmd import anon_app
from zibaldone.cli.app import app

runner = CliRunner()


def invoke(*args, input=None):
    return runner.invoke(app, list(args), input=input)


def anon(*args, input=None):
    return runner.invoke(anon_app, list(args), input=input)


def accept_privacy() -> None:
    assert invoke("privacy", "accept").exit_code == 0


def add_people() -> None:
    assert invoke("pack", "install", "persone", "--yes").exit_code == 0
    added = invoke("entry", "add", "persona", "--set", "nome=Marco Ferri", "--set", "soprannomi=Marchino")
    assert added.exit_code == 0, added.output
    assert invoke("entry", "add", "incontro", "--set", "titolo=Pizza con Giulia").exit_code == 0


def test_preview_with_names_flag_touches_no_data(isolated_data_dir) -> None:
    result = anon("preview", "Marco mi ha scritto da marco@example.com, chiamalo al 333 1234567. Marco!", "--names", "Marco, Giulia")
    assert result.exit_code == 0, result.output
    assert "[PERSONA_1] mi ha scritto da [EMAIL_1], chiamalo al [TELEFONO_1]. [PERSONA_1]!" in result.output
    assert "Dizionario dei nomi: 2 da --names." in result.output
    assert "pseudonimi reversibili" in result.output
    lines = result.output.splitlines()
    assert any("nome di persona" in line and "Marco" in line and "[PERSONA_1]  (×2)" in line for line in lines)
    assert any("numero di telefono" in line and "333 1234567" in line and "[TELEFONO_1]" in line for line in lines)
    assert "non è stata salvata" in result.output
    assert not isolated_data_dir.exists()


def test_preview_uses_person_entries_and_writes_nothing(isolated_data_dir) -> None:
    accept_privacy()
    add_people()
    result = anon("preview", "Marchino, cioè Ferri, ha mangiato la pizza con Giulia in via Roma 12.")
    assert result.exit_code == 0, result.output
    assert "dalle tue voci Persona" in result.output
    # Giulia appears only in the title of an 'incontro' entry, which is not a person
    assert "[PERSONA_1], cioè [PERSONA_1], ha mangiato la pizza con Giulia in [INDIRIZZO_1]." in result.output
    for path in isolated_data_dir.rglob("*"):
        if path.is_file():
            assert b"mangiato la pizza" not in path.read_bytes()


def test_preview_without_person_entries_says_so() -> None:
    accept_privacy()
    result = anon("preview", "Ciao Marco, tutto bene?")
    assert result.exit_code == 0, result.output
    assert "Nessuna voce Persona" in result.output
    assert "zbone pack install persone" in result.output
    assert "Nessun dato personale riconosciuto" in result.output


def test_preview_anon_mode() -> None:
    result = anon("preview", "Marco: marco@example.com", "--names", "Marco", "--mode", "anon")
    assert result.exit_code == 0, result.output
    assert "anonimato irreversibile" in result.output
    assert "[PERSONA_1]: [EMAIL_1]" in result.output
    assert "la tabella non viene conservata" in result.output


def test_preview_errors_are_short_messages() -> None:
    wrong_mode = anon("preview", "Ciao", "--names", "Marco", "--mode", "hash")
    assert wrong_mode.exit_code == 1
    assert "modalità sconosciuta 'hash'" in wrong_mode.output
    short_name = anon("preview", "Ciao", "--names", "M")
    assert short_name.exit_code == 1
    assert "troppo corto" in short_name.output


def test_preview_asks_for_consent_before_reading_entries(isolated_data_dir) -> None:
    result = anon("preview", "Ciao Marco", input="no\n")
    assert result.exit_code == 1
    assert not isolated_data_dir.exists()


def test_eval_prints_scores_per_kind() -> None:
    result = anon("eval")
    assert result.exit_code == 0, result.output
    assert "Frasi di prova:" in result.output
    for label in ("PERSONA", "TELEFONO", "IBAN", "CODICE_FISCALE", "DATA_NASCITA", "Totale", "Precisione", "Richiamo"):
        assert label in result.output
    assert "Confronto parziale" in result.output
    assert "--errors" in result.output
    detailed = anon("eval", "--errors")
    assert "sfuggito" in detailed.output and "in più" in detailed.output
