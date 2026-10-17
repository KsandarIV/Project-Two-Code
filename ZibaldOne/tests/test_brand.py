from datetime import date, timedelta

from zibaldone.core.blocks import BLOCK_TYPES
from zibaldone.core.brand import AREAS, MASCOTS, QUOTES, mascot_for, quote_of_the_day


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
