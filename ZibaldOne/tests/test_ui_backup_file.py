"""Mnemosyne in the app: automatic or manual, a snapshot to a file, a file back."""

from pathlib import Path
from types import SimpleNamespace

import pytest

ft = pytest.importorskip("flet")

from test_ui_views import FakePage, button, click, folder, ready, texts, walk  # noqa: E402,F401
from zibaldone.storage import backups, bundle  # noqa: E402
from zibaldone.storage.database import Store  # noqa: E402
from zibaldone.ui import services  # noqa: E402
from zibaldone.ui.app import Shell  # noqa: E402


def test_mnemosyne_says_what_automatic_and_manual_do_and_remembers_the_choice(ready: Path) -> None:
    shell = Shell(FakePage(), ready)
    shell.start("/organon/mnemosyne")
    shown = texts(shell.body.content)
    assert "istantanee complete dei tuoi dati" in " ".join(shown) and "commit" not in " ".join(shown)
    assert any("dopo l'1:00" in text for text in shown)
    group = next(item for item in walk(shell.body.content) if isinstance(item, ft.RadioGroup))
    assert group.value == "app"
    group.value = "utente"
    group.on_change(SimpleNamespace(control=group))
    click(button(shell.ctx.page.dialogs[-1], "Continua"))
    assert backups.load_backup_settings(ready).auto is False and services.backup_mode(ready) == "utente"
    assert any("Gestisco io" in text for text in texts(shell.body.content))


def test_a_snapshot_is_saved_to_a_file_and_the_path_is_shown(ready: Path) -> None:
    snapshot = backups.create_snapshot(ready, "manual")
    shell = Shell(FakePage(), ready)
    shell.start("/organon/mnemosyne")
    click(next(item for item in walk(shell.body.content) if isinstance(item, ft.IconButton) and item.tooltip == "Salva in un file di backup"))
    files = list((ready / "exports").glob("*.zbbackup"))
    assert len(files) == 1 and bundle.inspect_bundle(files[0]).ok
    assert str(files[0]) in " ".join(texts(shell.ctx.page.dialogs[-1]))
    assert snapshot.id


def test_a_backup_file_is_added_or_restores_the_data(ready: Path, tmp_path: Path) -> None:
    with Store.open(ready) as store:
        before = store.count_entries("libro")
        store.add_entry("libro", {"titolo": "Dune"})
    snapshot = backups.create_snapshot(ready, "manual")
    file = bundle.export_bundle(ready, snapshot.id, tmp_path / "out")
    with Store.open(ready) as store:
        store.add_entry("libro", {"titolo": "Altro"})
    shell = Shell(FakePage(), ready)
    shell.ctx.pick_files = lambda on_picked, multiple=True: on_picked([SimpleNamespace(path=str(file))])
    shell.start("/organon/mnemosyne")
    click(button(shell.body.content, "Importa da un file"))
    dialog = shell.ctx.page.dialogs[-1]
    assert "Backup trovato" in str(dialog.title) or dialog.title == "Backup trovato"
    click(button(dialog, "Ripristina i dati"))
    with Store.open(ready) as store:
        assert store.count_entries("libro") == before + 1
    assert any("riportati" in toast for toast in shell.ctx.toasts)


def test_a_file_that_is_not_a_backup_is_refused_with_a_message(ready: Path, tmp_path: Path) -> None:
    bad = tmp_path / "x.zbbackup"
    bad.write_bytes(b"niente")
    shell = Shell(FakePage(), ready)
    shell.ctx.pick_files = lambda on_picked, multiple=True: on_picked([SimpleNamespace(path=str(bad))])
    shell.start("/organon/mnemosyne")
    click(button(shell.body.content, "Importa da un file"))
    assert shell.ctx.toasts and "backup" in shell.ctx.toasts[-1].lower()


def test_the_first_start_offers_a_backup_file(ready: Path, tmp_path: Path) -> None:
    from zibaldone.core.privacy import NOTICE_VERSION
    from zibaldone.storage.settings import record_consent

    snapshot = backups.create_snapshot(ready, "manual")
    file = bundle.export_bundle(ready, snapshot.id, tmp_path / "out")
    fresh = tmp_path / "nuovo"
    fresh.mkdir()
    record_consent(fresh, True, NOTICE_VERSION)
    shell = Shell(FakePage(), fresh)
    shell.ctx.pick_files = lambda on_picked, multiple=True: on_picked([SimpleNamespace(path=str(file))])
    from zibaldone.ui.navigation import Route
    from zibaldone.ui.views import onboarding

    shell.start("/oggi")  # the sign-in step itself is skipped where there is no account module: build it directly
    page = onboarding.sign_in(shell.ctx, Route("accesso", ""))
    click(button(page, "Ho già un backup"))
    click(button(shell.ctx.page.dialogs[-1], "Ripristina i dati"))
    assert shell.current.path == "/oggi"
    with Store.open(fresh) as store:
        assert store.list_templates()


def test_a_backup_found_on_the_first_start_is_offered_and_can_be_set_aside(ready: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from zibaldone.ui.views import backup_file

    snapshot = backups.create_snapshot(ready, "manual")
    file = bundle.export_bundle(ready, snapshot.id, tmp_path / "out")
    monkeypatch.setattr(bundle, "first_run_candidate", lambda folder: bundle.inspect_bundle(file))
    shell = Shell(FakePage(), ready)
    shell.start("/oggi")
    panel = backup_file.found_backup_panel(shell.ctx, lambda: None)
    assert panel is not None and "Ho trovato un tuo backup di ZibaldOne." in texts(panel)
    click(button(panel, "Parto da zero"))
    assert backup_file.found_backup_panel(shell.ctx, lambda: None) is None


def test_the_start_screen_makes_the_suggested_folder_and_uses_it(folder: Path) -> None:
    from zibaldone.core.privacy import NOTICE_VERSION
    from zibaldone.storage.settings import record_consent

    record_consent(folder, True, NOTICE_VERSION)
    shell = Shell(FakePage(), folder)
    shell.start("/")
    assert shell.current.screen == "cartella"
    assert "ZibaldOne/Data" in " ".join(texts(shell.body.content))
    click(button(shell.body.content, "Crea la cartella per me"))
    made = services.suggested_folder()
    assert made.is_dir() and services.backup_files_folder(folder) == str(made)
    assert services.folder_history(folder) == [str(made)]


def test_without_backup_the_strip_shows_and_can_be_switched_off(ready: Path) -> None:
    services.save_ui_settings(ready, backup_files_folder="")
    shell = Shell(FakePage(), ready)
    shell.start("/oggi")
    assert shell.strip.visible and "senza backup" in " ".join(texts(shell.strip.content))
    shell.no_backup_options()
    click(button(shell.ctx.page.dialogs[-1], "Spegni l'avviso"))
    assert not shell.strip.visible and services.without_backup(ready) is False


def test_parresia_follows_the_choice_and_does_not_write_the_private_path(ready: Path, tmp_path: Path) -> None:
    shell = Shell(FakePage(), ready)
    services.save_ui_settings(ready, backup_files_folder="")
    shell.start("/organon/parresia")
    shown = " ".join(texts(shell.body.content))
    assert "Hai deciso di non fare backup" in shown and str(ready) not in shown
    services.set_backup_folder(ready, str(tmp_path / "miei"))
    services.set_backup_mode(ready, "utente")
    shell.start("/organon/parresia")
    shown = " ".join(texts(shell.body.content))
    assert "Hai deciso di gestire da solo i backup" in shown and str(tmp_path / "miei") in shown
    click(button(shell.body.content, "Passa alla gestione dell'app"))
    click(button(shell.ctx.page.dialogs[-1], "Continua"))
    click(button(shell.ctx.page.dialogs[-1], "Sì, passa a «Gestisce l'app»"))
    assert services.backup_mode(ready) == "app" and backups.load_backup_settings(ready).auto is True


def test_changing_folder_remembers_the_old_one_and_can_bring_the_files_along(ready: Path, tmp_path: Path) -> None:
    old, new = tmp_path / "vecchia", tmp_path / "nuova"
    services.set_backup_folder(ready, str(old))
    backups.create_snapshot(ready, reason="manual")
    assert services.export_to_files_folder(ready) == ""
    moved = services.set_backup_folder(ready, str(new), move_old=True)
    assert len(moved) == 1 and moved[0].is_relative_to(new)
    assert services.folder_history(ready) == [str(old), str(new)]
    old.rmdir() if not any(old.iterdir()) else None
    import shutil

    shutil.rmtree(old, ignore_errors=True)
    assert services.folder_history(ready) == [str(new)]
