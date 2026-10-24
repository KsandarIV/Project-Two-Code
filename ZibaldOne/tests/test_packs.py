import json

import pytest
from typer.testing import CliRunner

from zibaldone.cli.app import app
from zibaldone.core.blocks import BLOCK_TYPES
from zibaldone.core.packs import (
    MAX_PACK_BYTES,
    Pack,
    apply_install,
    build_pack,
    builtin_packs,
    find_builtin_pack,
    load_pack_bytes,
    plan_install,
)
from zibaldone.storage.database import Store

runner = CliRunner()


def test_builtin_packs_are_valid_and_cover_journal_app_ideas() -> None:
    packs = {pack.short_name: pack for pack in builtin_packs()}
    assert set(packs) == {"diario", "aree", "collezioni", "io", "persone", "segreti", "finanze", "askesis", "theoria"}
    diario = {template.slug for template in packs["diario"].templates}
    assert {"mattina", "meta_giornata", "sera", "aree", "settimana", "mese", "anno"} <= diario
    aree = next(template for template in packs["diario"].templates if template.slug == "aree")
    assert [block.label for block in aree.blocks[:8]] == ["Personale", "Salute", "Finanze", "Famiglia", "Sociale", "Lavoro", "Studio", "Svago"]
    collezioni = {template.slug for template in packs["collezioni"].templates}
    assert {"libro", "anime", "videogioco", "serie", "sport", "film", "gioco_tavolo", "musica", "capo"} == collezioni
    for pack in packs.values():
        assert set(pack.required_blocks) <= set(BLOCK_TYPES)


def test_pack_round_trip() -> None:
    pack = find_builtin_pack("diario")
    again = load_pack_bytes(pack.to_json().encode("utf-8"))
    assert again.to_dict() == pack.to_dict()


def pack_data() -> dict:
    return json.loads(find_builtin_pack("persone").to_json())


@pytest.mark.parametrize(
    "change, message",
    [
        (lambda data: data.update(format=99), "formato più recente"),
        (lambda data: data.update(code="import os"), "campi non previsti"),
        (lambda data: data.update(required_blocks=["audio"]), "non conosce: audio"),
        (lambda data: data.update(required_blocks=["text"]), "non corrisponde"),
        (lambda data: data["templates"][0]["blocks"][0].update(type="audio"), "tipo di blocco sconosciuto"),
        (lambda data: data.update(templates=[]), "non contiene modelli"),
        (lambda data: data.update(id="../../etc"), "identificativo"),
    ],
)
def test_bad_packs_are_rejected(change, message) -> None:
    data = pack_data()
    change(data)
    with pytest.raises(ValueError, match=message):
        Pack.from_dict(data)


def test_too_big_or_not_json() -> None:
    with pytest.raises(ValueError, match="troppo grande"):
        load_pack_bytes(b" " * (MAX_PACK_BYTES + 1))
    with pytest.raises(ValueError, match="JSON"):
        load_pack_bytes(b"\xff\xfe")


def test_install_plan_new_same_update_copy(tmp_path) -> None:
    pack = find_builtin_pack("persone")
    with Store.open(tmp_path) as store:
        plan = plan_install(pack, store)
        assert [step.action for step in plan.steps] == ["new", "new"]
        apply_install(plan, store)
        assert store.get_template("persona").origin["pack_id"] == "zibaldone.persone"
        assert [step.action for step in plan_install(pack, store).steps] == ["same", "same"]

        store.add_entry("persona", {"nome": "Marco", "ruolo": "Amico"})
        newer = Pack.from_dict({**pack.to_dict(), "version": "1.1.0"})
        newer.templates[0].description = "nuova descrizione"
        assert plan_install(newer, store).steps[0].action == "update"

        breaking = Pack.from_dict(pack.to_dict())
        breaking.templates[0].blocks = [block for block in breaking.templates[0].blocks if block.key != "ruolo"]
        step = plan_install(breaking, store).steps[0]
        assert step.action == "copy" and step.target_slug == "persona_2"
        assert "1 voci" in step.reason


def test_slug_taken_by_user_template_becomes_copy(tmp_path) -> None:
    from zibaldone.core.templates import BlockSpec, Template

    with Store.open(tmp_path) as store:
        store.save_template(Template("persona", "La mia persona", [BlockSpec("nome", "text", "Nome")]))
        plan = plan_install(find_builtin_pack("persone"), store)
        assert plan.steps[0].action == "copy"
        apply_install(plan, store)
        assert store.get_template("persona").name == "La mia persona"
        assert store.get_template("persona_2").origin["pack_id"] == "zibaldone.persone"


def test_export_contains_structure_only(tmp_path) -> None:
    with Store.open(tmp_path) as store:
        apply_install(plan_install(find_builtin_pack("collezioni"), store), store)
        store.add_entry("libro", {"titolo": "Diario segretissimo"})
        pack = build_pack([store.get_template("libro")], "alex.letture", "Letture", author="Alex")
    text = pack.to_json()
    assert "Diario segretissimo" not in text
    assert "origin" not in text


def test_cli_install_export_import(tmp_path) -> None:
    runner.invoke(app, ["privacy", "accept"])
    listed = runner.invoke(app, ["pack", "list"])
    assert "diario" in listed.output and "da installare" in listed.output
    installed = runner.invoke(app, ["pack", "install", "diario", "--yes"])
    assert installed.exit_code == 0, installed.output
    assert "Installati 8 modelli" in installed.output
    again = runner.invoke(app, ["pack", "install", "diario", "--yes"])
    assert "già installato" in again.output

    added = runner.invoke(app, ["entry", "add", "sera", "--set", "umore=buono", "--set", "voto=8", "--set", "domani=palestra; [x] spesa"])
    assert added.exit_code == 0, added.output

    target = tmp_path / "serate"
    exported = runner.invoke(app, ["pack", "export", "sera", "mattina", "-o", str(target), "--author", "Alex", "--name", "Le mie giornate"])
    assert exported.exit_code == 0, exported.output
    file = tmp_path / "serate.zbpack.json"
    assert file.exists()
    shown = runner.invoke(app, ["pack", "show", str(file)])
    assert "Le mie giornate 1.0.0 (alex.le-mie-giornate) di Alex" in shown.output
    imported = runner.invoke(app, ["pack", "import", str(file), "--yes"])
    assert imported.exit_code == 0, imported.output
    assert "installato come copia" in imported.output


def test_cli_unknown_pack() -> None:
    runner.invoke(app, ["privacy", "accept"])
    result = runner.invoke(app, ["pack", "install", "cucina"])
    assert result.exit_code == 1
    assert "non è un pacchetto integrato" in result.output
