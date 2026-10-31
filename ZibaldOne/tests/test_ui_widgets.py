import flet as ft

from zibaldone.ui import widgets as W


def test_badge_shows_the_drawing_when_the_icon_names_a_mascot_file() -> None:
    badge = W.template_badge("Pannychis", "#8A2BE2", size=40)
    assert isinstance(badge.content, ft.Image)
    assert badge.content.src == "mascots/Pannychis.svg"


def test_badge_keeps_the_material_icon_otherwise() -> None:
    for name in ("BEDTIME", "../Pannychis"):
        badge = W.template_badge(name, "#8A2BE2", size=40)
        assert isinstance(badge.content, ft.Icon)
