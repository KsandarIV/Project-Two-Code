from dataclasses import replace
from datetime import date, timedelta

import pytest

from zibaldone.core import brand
from zibaldone.core.blocks import BLOCK_TYPES
from zibaldone.core.brand import (
    APP_MOTTO,
    APP_NAME,
    APP_TAGLINE,
    AREAS,
    DEFAULT_THEME_ID,
    FILOSOFIA,
    MASCOTS,
    NOMENCLATURE,
    QUOTES,
    active_theme,
    get_theme,
    list_themes,
    mascot_for,
    quote_of_the_day,
    register_theme,
)


def test_one_mascot_per_area_plus_the_app() -> None:
    assert sorted(mascot.sphere for mascot in MASCOTS if mascot.sphere != "app") == sorted(AREAS)
    assert mascot_for("Studio").name == "Hegy"
    assert mascot_for("app").name == "Zibby"


def test_quote_of_the_day_is_stable_and_rotates() -> None:
    today = date(2026, 10, 17)
    assert quote_of_the_day(today) == quote_of_the_day(today)
    week = {quote_of_the_day(today + timedelta(days=offset)).text for offset in range(7)}
    assert len(week) == 7
    assert all(quote.author and quote.source for quote in QUOTES)


def test_every_block_has_a_philosophical_name() -> None:
    nicknames = [block.nickname for block in BLOCK_TYPES.values()]
    assert all(nicknames) and len(set(nicknames)) == len(nicknames)


# * — theme registry —
@pytest.fixture
def clean_registry():
    before = dict(brand._THEMES)
    yield
    brand._THEMES.clear()
    brand._THEMES.update(before)


def _copy(theme_id: str = "prova", **changes):
    return replace(FILOSOFIA, id=theme_id, label="Prova", **changes)


def test_get_theme_by_id_and_fallback() -> None:
    assert get_theme("filosofia") is FILOSOFIA
    assert get_theme(" Filosofia ") is FILOSOFIA
    for unknown in ("ignoto", "", None):
        assert get_theme(unknown) is FILOSOFIA
    assert DEFAULT_THEME_ID == "filosofia"


def test_module_aliases_match_the_default_theme() -> None:
    assert NOMENCLATURE == FILOSOFIA.nomenclature
    assert MASCOTS == list(FILOSOFIA.mascots)
    assert QUOTES == list(FILOSOFIA.quotes)
    assert (APP_NAME, APP_TAGLINE, APP_MOTTO) == (FILOSOFIA.app_name, FILOSOFIA.app_tagline, FILOSOFIA.app_motto)
    day = date(2026, 10, 17)
    assert quote_of_the_day(day) == FILOSOFIA.quote_of_the_day(day)
    assert mascot_for("Salute") == FILOSOFIA.mascot_for("salute")
    assert mascot_for("nessuna") is None


def test_list_themes_default_first(clean_registry) -> None:
    assert list_themes()[0].id == DEFAULT_THEME_ID
    extra = register_theme(_copy())
    assert [theme.id for theme in list_themes()] == [DEFAULT_THEME_ID, "prova"]
    assert get_theme("prova") is extra


def test_duplicate_id_is_rejected(clean_registry) -> None:
    with pytest.raises(ValueError, match="already registered"):
        register_theme(_copy(DEFAULT_THEME_ID))


def test_validation_rejects_incomplete_themes(clean_registry) -> None:
    nomenclature = dict(FILOSOFIA.nomenclature)
    missing = {key: value for key, value in nomenclature.items() if key != "block"}
    extra = dict(nomenclature, nuovo=nomenclature["block"])
    no_area = tuple(mascot for mascot in FILOSOFIA.mascots if mascot.sphere != "salute")
    duplicate = no_area + (replace(FILOSOFIA.mascots[0], name="Altro"),)
    bad_themes = [
        _copy(nomenclature=missing),
        _copy(nomenclature=extra),
        _copy(mascots=no_area),
        _copy(mascots=duplicate),
        _copy(quotes=FILOSOFIA.quotes[:6]),
        _copy("Non Valido!"),
        _copy(app_name=" "),
    ]
    for theme in bad_themes:
        with pytest.raises(ValueError, match="theme"):
            register_theme(theme)
    assert [theme.id for theme in list_themes()] == [DEFAULT_THEME_ID]


def test_active_theme_priority(clean_registry, monkeypatch) -> None:
    other = register_theme(_copy())
    monkeypatch.delenv(brand.THEME_ENV_VAR, raising=False)
    assert active_theme({"theme": "prova"}) is other
    assert active_theme({"theme": "filosofia"}) is FILOSOFIA
    for settings in ({"theme": "ignoto"}, {}, None):
        assert active_theme(settings) is FILOSOFIA
    monkeypatch.setenv(brand.THEME_ENV_VAR, "prova")
    assert active_theme({"theme": "filosofia"}) is other


def test_every_area_mascot_has_a_drawing_and_the_avatar_uses_it() -> None:
    from zibaldone.ui import widgets as W

    for mascot in MASCOTS:
        if mascot.sphere != "app":
            assert W.mascot_svg(mascot.name), mascot.name
            assert isinstance(W.mascot_avatar(mascot).content, W.ft.Image)
    assert W.mascot_svg("Zibby") is None  # no drawing yet: the avatar falls back to the initial
