"""Impostazioni → Personalizza: the choices about how the app looks, in one place, each under its own section."""

from typing import Any, List

import flet as ft

from zibaldone.ui import services
from zibaldone.ui import widgets as W
from zibaldone.ui.context import AppContext
from zibaldone.ui.navigation import settings_part
from zibaldone.ui.views import app_icon, home_layout

VIEW_MODES = (("completa", "Completa: nome, descrizione e conteggio"), ("icone", "Solo icone"))
DEFAULT_VIEW = "completa"


def templates_view(ctx: AppContext) -> str:
    """The way Modelli shows its pages: the one chosen in this session, else the saved one."""
    saved = services.ui_settings(ctx.folder).get("modelli_vista", DEFAULT_VIEW)
    mode = ctx.memory.get("modelli_vista", saved)
    return mode if mode in dict(VIEW_MODES) else DEFAULT_VIEW


def set_templates_view(ctx: AppContext, mode: str) -> None:
    ctx.memory["modelli_vista"] = mode
    services.save_ui_settings(ctx.folder, modelli_vista=mode)


def build(ctx: AppContext) -> ft.Control:
    part = settings_part("personalizza")

    def choose(event: Any) -> None:
        set_templates_view(ctx, event.control.value)
        ctx.toast("Vista dei modelli salvata.")

    picker = W.dropdown(VIEW_MODES, templates_view(ctx), label="Come si vedono i modelli", on_select=choose)
    controls: List[ft.Control] = [
        W.screen_header(part.nickname, part.label, part.description, on_back=ctx.back),
        W.section_label("Modelli"),
        W.panel(ft.Column([W.body("La vista con cui si aprono le pagine dei modelli. Si cambia anche dal pulsante in alto nella schermata Modelli.", dim=True), W.wide(picker)], spacing=10)),
        W.section_label("Icona"),
        W.panel(ft.Column([W.body("L'icona dell'app. Cambia subito quella della finestra; l'icona del collegamento o dell'app installata cambia con la guida «Cambiare l'icona».", dim=True), app_icon.picker(ctx, lambda letter: app_icon.choose(ctx, letter))], spacing=10)),
        W.section_label("La home", "Oikos"),
        *home_layout.build(ctx),
    ]
    return W.screen(controls, ctx.wide)
