import re
import zipfile
from datetime import datetime, timedelta, timezone

import pytest
import typer
from typer.testing import CliRunner

from zibaldone.cli.backup_cmd import backup_app, run_auto_backup
from zibaldone.cli.entry_cmd import entry_app
from zibaldone.cli.export_cmd import export_app
from zibaldone.cli.privacy_cmd import privacy_app
from zibaldone.cli.template_cmd import template_app
from zibaldone.core import crypto
from zibaldone.core.crypto import ScryptParams
from zibaldone.storage import backups, keys

# The groups mounted the same way as in cli/app.py, so these tests do not
# depend on when the root app registers `backup` and `export`.
app = typer.Typer()
for group, name in ((privacy_app, "privacy"), (template_app, "template"), (entry_app, "entry"), (backup_app, "backup"), (export_app, "export")):
    app.add_typer(group, name=name)

runner = CliRunner()
PASSPHRASE = "cavallo batteria graffetta"
RECOVERY_CODE = crypto.recovery_code_from_bytes(bytes(range(15)))
LAST_GROUP = RECOVERY_CODE.split("-")[-1]
SNAPSHOT_ID = re.compile(r"\d{8}T\d{6}Z-[0-9a-f]{6}")


@pytest.fixture(autouse=True)
def fast_and_predictable(monkeypatch):
    monkeypatch.setattr(keys, "DEFAULT_SCRYPT_PARAMS", ScryptParams(n=2**10))
    monkeypatch.setattr(crypto, "generate_recovery_code", lambda: RECOVERY_CODE)


def invoke(*args, input=None):
    return runner.invoke(app, list(args), input=input)


def start_with_books(*titles: str) -> None:
    assert invoke("privacy", "accept").exit_code == 0
    assert invoke("template", "create", "Libro", "--block", "titolo:text:Titolo!").exit_code == 0
    for title in titles:
        assert invoke("entry", "add", "libro", "--set", f"titolo={title}").exit_code == 0


def forget_automatic_snapshots(folder) -> None:
    """Adding the first book starts the daily snapshot; some tests count snapshots from zero."""
    for snapshot in backups.list_snapshots(folder):
        snapshot.path.unlink()


def created_id(result) -> str:
    assert result.exit_code == 0, result.output
    return SNAPSHOT_ID.search(result.output).group(0)


def setup_encryption():
    return invoke("backup", "setup", input=f"{PASSPHRASE}\n{PASSPHRASE}\n{LAST_GROUP}\n")


def no_traceback(result) -> None:
    assert "Traceback" not in result.output
    assert isinstance(result.exception, SystemExit)


# * — history without encryption —


def test_create_list_verify_restore_and_undo() -> None:
    start_with_books("Dune")
    first = created_id(invoke("backup", "create", "--note", "prima di Emma"))
    invoke("entry", "add", "libro", "--set", "titolo=Emma")

    listed = invoke("backup", "list")
    assert first in listed.output and "manuale" in listed.output and "«prima di Emma»" in listed.output
    assert "in chiaro" in listed.output and "Cifratura:    non attiva" in listed.output
    assert "7 giornaliere, 4 settimanali, 12 mensili" in listed.output

    verified = invoke("backup", "verify")
    assert verified.exit_code == 0 and "integra" in verified.output

    declined = invoke("backup", "restore", first, input="no\n")
    assert "non ho cambiato nulla" in declined.output
    assert "Emma" in invoke("entry", "list").output

    restored = invoke("backup", "restore", first.split("-")[1], input="sì\n")
    assert restored.exit_code == 0, restored.output
    assert "Dati riportati" in restored.output
    undo = re.search(r"Per annullare: zbone backup restore (\S+)", restored.output).group(1)
    assert "Emma" not in invoke("entry", "list").output

    assert invoke("backup", "restore", undo, "--yes").exit_code == 0
    assert "Emma" in invoke("entry", "list").output


def test_verify_reports_a_damaged_snapshot(isolated_data_dir) -> None:
    start_with_books("Dune")
    snapshot_id = created_id(invoke("backup", "create"))
    path = isolated_data_dir / "backups" / f"{snapshot_id}.zbsnap"
    path.write_bytes(path.read_bytes()[:-30])
    result = invoke("backup", "verify", "--all")
    assert result.exit_code == 1 and "ROTTA" in result.output
    assert "non sono integre" in result.output
    no_traceback(result)


def test_errors_are_short_messages() -> None:
    assert invoke("privacy", "accept").exit_code == 0
    empty = invoke("backup", "create")
    assert empty.exit_code == 1 and "non ci sono ancora dati" in empty.output
    no_traceback(empty)
    missing = invoke("backup", "restore", "20260101")
    assert missing.exit_code == 1 and "nessuna istantanea" in missing.output
    assert invoke("backup", "passphrase").exit_code == 1


def test_backup_commands_ask_for_consent_first(isolated_data_dir) -> None:
    result = invoke("backup", "list", input="no\n")
    assert result.exit_code == 1
    assert not isolated_data_dir.exists()


def test_config_and_prune(isolated_data_dir) -> None:
    start_with_books("Dune")
    shown = invoke("backup", "config")
    assert "Automatico:   sì, ogni 24 ore" in shown.output
    changed = invoke("backup", "config", "--no-auto", "--days", "2", "--weeks", "0", "--months", "0", "--interval", "12")
    assert changed.exit_code == 0 and "Impostazioni salvate" in changed.output
    assert "Automatico:   no" in changed.output and "2 giornaliere, 0 settimanali, 0 mensili" in changed.output
    settings = backups.load_backup_settings(isolated_data_dir)
    assert (settings.auto, settings.auto_interval_hours, settings.retention.daily) == (False, 12, 2)

    forget_automatic_snapshots(isolated_data_dir)
    noon = datetime.now(timezone.utc).replace(hour=12)
    for back in range(5):
        backups.create_snapshot(isolated_data_dir, now=noon - timedelta(days=back))
    preview = invoke("backup", "prune", "--dry-run")
    assert "Prova" in preview.output and len(SNAPSHOT_ID.findall(preview.output)) == 3
    assert len(backups.list_snapshots(isolated_data_dir)) == 5
    done = invoke("backup", "prune")
    assert done.exit_code == 0 and "Istantanee cancellate" in done.output and "Restano 2" in done.output
    assert "Niente da cancellare" in invoke("backup", "prune").output


# * — encryption —


def test_setup_encrypts_existing_snapshots_and_restore_asks_passphrase(isolated_data_dir) -> None:
    start_with_books("Dune")
    forget_automatic_snapshots(isolated_data_dir)
    plain = created_id(invoke("backup", "create", "--note", "in chiaro"))

    result = invoke("backup", "setup", input=f"{PASSPHRASE}\n{PASSPHRASE}\nZZZZ\n{LAST_GROUP.lower()}\n")
    assert result.exit_code == 0, result.output
    assert RECOVERY_CODE in result.output
    assert "Non corrisponde" in result.output and "Cifratura attiva" in result.output
    assert "ora cifrate: 1" in result.output
    assert crypto.is_sealed((isolated_data_dir / "backups" / f"{plain}.zbsnap").read_bytes())
    assert PASSPHRASE not in (isolated_data_dir / "keys.json").read_text(encoding="utf-8")

    encrypted = created_id(invoke("backup", "create"))
    listed = invoke("backup", "list")
    assert "cifrata" in listed.output and "«in chiaro»" not in listed.output and "Cifratura:    attiva" in listed.output
    detailed = invoke("backup", "list", "--details", input=f"{PASSPHRASE}\n")
    assert "«in chiaro»" in detailed.output

    invoke("entry", "add", "libro", "--set", "titolo=Emma")
    wrong = invoke("backup", "restore", encrypted, "--yes", input="non è questa\n")
    assert wrong.exit_code == 1 and "passphrase sbagliata" in wrong.output
    no_traceback(wrong)
    assert "Emma" in invoke("entry", "list").output

    right = invoke("backup", "restore", encrypted, "--yes", input=f"{PASSPHRASE}\n")
    assert right.exit_code == 0, right.output
    assert "Emma" not in invoke("entry", "list").output

    verified = invoke("backup", "verify", "--all", input=f"{PASSPHRASE}\n")
    assert verified.exit_code == 0, verified.output
    assert "Tutte le 3 istantanee sono integre" in verified.output


def test_setup_needs_the_last_group_and_matching_passphrases(isolated_data_dir) -> None:
    start_with_books("Dune")
    cancelled = invoke("backup", "setup", input=f"{PASSPHRASE}\n{PASSPHRASE}\nAAAA\nBBBB\nCCCC\n")
    assert cancelled.exit_code == 1 and "non ho salvato nulla" in cancelled.output
    assert not (isolated_data_dir / "keys.json").exists()
    mismatch = invoke("backup", "setup", input=f"{PASSPHRASE}\naltra passphrase\n")
    assert mismatch.exit_code == 1 and "non coincidono" in mismatch.output
    weak = invoke("backup", "setup", input="corta\n")
    assert weak.exit_code == 1 and "almeno 10 caratteri" in weak.output
    assert not (isolated_data_dir / "keys.json").exists()
    assert setup_encryption().exit_code == 0
    again = setup_encryption()
    assert again.exit_code == 1 and "già attiva" in again.output


def test_change_passphrase_and_recover(isolated_data_dir) -> None:
    start_with_books("Dune")
    assert setup_encryption().exit_code == 0

    wrong = invoke("backup", "passphrase", input="sbagliata sbagliata\n")
    assert wrong.exit_code == 1 and "passphrase sbagliata" in wrong.output
    changed = invoke("backup", "passphrase", input=f"{PASSPHRASE}\nnuova passphrase lunga\nnuova passphrase lunga\n")
    assert changed.exit_code == 0 and "Passphrase cambiata" in changed.output
    keys.unlock_with_passphrase(isolated_data_dir, "nuova passphrase lunga")

    typo = RECOVERY_CODE[:-1] + ("A" if RECOVERY_CODE[-1] != "A" else "B")
    recovered = invoke("backup", "recover", input=f"{typo}\n{RECOVERY_CODE}\npassphrase ritrovata\npassphrase ritrovata\n")
    assert recovered.exit_code == 0, recovered.output
    assert "errore di battitura" in recovered.output and "Nuova passphrase salvata" in recovered.output
    keys.unlock_with_passphrase(isolated_data_dir, "passphrase ritrovata")

    other = crypto.recovery_code_from_bytes(bytes(15))
    refused = invoke("backup", "recover", input=f"{other}\n")
    assert refused.exit_code == 1 and "codice di recupero sbagliato" in refused.output
    no_traceback(refused)


# * — automatic backups —


def test_run_auto_backup_is_silent_and_never_fails(isolated_data_dir, capsys) -> None:
    start_with_books("Dune")
    run_auto_backup()
    run_auto_backup()  # within the interval: nothing new
    assert len(backups.list_snapshots(isolated_data_dir)) == 1
    assert capsys.readouterr().out == ""
    (isolated_data_dir / "settings.json").write_text("{ rotto", encoding="utf-8")
    run_auto_backup()
    assert "backup automatico non riuscito" in capsys.readouterr().err


# * — export —


def test_export_markdown_and_csv(tmp_path) -> None:
    start_with_books("Dune", "Emma")
    target = tmp_path / "voci.zip"
    result = invoke("export", "markdown", "-o", str(target))
    assert result.exit_code == 0, result.output
    assert "voci: 2, modelli: 1" in result.output and "non è cifrato" in result.output
    with zipfile.ZipFile(target) as archive:
        assert len([name for name in archive.namelist() if name.startswith("Libro/") and name.endswith(" Dune.md")]) == 1

    declined = invoke("export", "csv", "-o", str(target), input="no\n")
    assert "non ho esportato nulla" in declined.output
    with zipfile.ZipFile(target) as archive:
        assert "libro.csv" not in archive.namelist()
    replaced = invoke("export", "csv", "-o", str(target), input="sì\n")
    assert replaced.exit_code == 0
    with zipfile.ZipFile(target) as archive:
        assert archive.namelist() == ["libro.csv"]

    missing_folder = invoke("export", "csv", "-o", str(tmp_path / "manca" / "x.zip"))
    assert missing_folder.exit_code == 1 and "non esiste" in missing_folder.output


def test_export_without_entries(tmp_path) -> None:
    assert invoke("privacy", "accept").exit_code == 0
    result = invoke("export", "markdown", "-o", str(tmp_path / "x.zip"))
    assert "Nessuna voce da esportare" in result.output
    assert not (tmp_path / "x.zip").exists()


def test_writes_start_the_daily_snapshot_reads_do_not(isolated_data_dir) -> None:
    assert invoke("privacy", "accept").exit_code == 0
    assert invoke("template", "list").exit_code == 0
    assert backups.list_snapshots(isolated_data_dir) == []
    assert invoke("template", "create", "Libro", "--block", "titolo:text:Titolo!").exit_code == 0
    assert [item.reason for item in backups.list_snapshots(isolated_data_dir)] == ["auto"]
    assert invoke("entry", "add", "libro", "--set", "titolo=Dune").exit_code == 0
    assert len(backups.list_snapshots(isolated_data_dir)) == 1


# * — the backup file (0.3.1) —


def test_export_then_import_brings_the_data_back_and_can_be_undone(isolated_data_dir, tmp_path) -> None:
    start_with_books("Dune")
    assert setup_encryption().exit_code == 0
    made = created_id(invoke("backup", "create"))  # the daily one was taken before the first book
    exported = invoke("backup", "export", made, "--to", str(tmp_path / "Download"))
    assert exported.exit_code == 0, exported.output
    assert "File di backup creato:" in exported.output and ".zbbackup" in exported.output and "codice di recupero" in exported.output
    path = next((tmp_path / "Download").glob("*.zbbackup"))

    invoke("entry", "add", "libro", "--set", "titolo=Emma")
    declined = invoke("backup", "import", str(path), input="n\n")
    assert declined.exit_code == 0 and "non ho cambiato nulla" in declined.output and "Emma" in invoke("entry", "list").output
    wrong = invoke("backup", "import", str(path), "--yes", input="non è questa\n")
    assert wrong.exit_code == 1 and "Traceback" not in wrong.output and "Emma" in invoke("entry", "list").output
    done = invoke("backup", "import", str(path), "--yes", input=f"{PASSPHRASE}\n")
    assert done.exit_code == 0, done.output
    assert "Emma" not in invoke("entry", "list").output and "Dune" in invoke("entry", "list").output
    assert "Per annullare: zbone backup restore" in done.output
    again = invoke("backup", "import", str(path), "--yes", input=f"\n{RECOVERY_CODE}\n")
    assert again.exit_code == 0, again.output


def test_import_refuses_what_is_not_a_backup_file_and_export_with_nothing_says_so(isolated_data_dir, tmp_path) -> None:
    assert invoke("privacy", "accept").exit_code == 0
    assert invoke("backup", "export").exit_code == 1
    fake = tmp_path / "x.zbbackup"
    fake.write_bytes(b"niente")
    refused = invoke("backup", "import", str(fake), "--yes")
    assert refused.exit_code == 1 and "non è un backup di ZibaldOne" in refused.output
    no_traceback(refused)
