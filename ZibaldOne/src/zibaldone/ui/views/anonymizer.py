"""Organon · Velo d'ignoranza (0.1.5): try the anonymizer on a text, before any AI model sees it."""

from typing import Any, List

import flet as ft

from zibaldone.core.brand import NOMENCLATURE
from zibaldone.ui import theme as T
from zibaldone.ui import viewmodels as vm
from zibaldone.ui import widgets as W
from zibaldone.ui.context import AppContext
from zibaldone.ui.navigation import settings_part

EXPLAIN = (
    "Prima che un testo arrivi a un modello di IA, l'anonimizzatore toglie nomi, contatti, codici e indirizzi "
    "e mette al loro posto dei segnaposto come [PERSONA_1]. Lavora solo su questo dispositivo: qui puoi provarlo, "
    "nulla viene salvato né inviato."
)
MODE_NOTES = {
    "pseudo": "Pseudonimi reversibili: la tabella dei segnaposto resta in memoria, così la risposta di un modello si può riportare ai nomi veri.",
    "anon": "Anonimato: la tabella non si conserva e il testo non è più riconducibile ai valori originali.",
}
RULES_WARNING = "Le regole possono sbagliare: rileggi sempre il testo prima di usarlo."


class VeloScreen:
    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx
        self.mode = "pseudo"
        self.input = W.text_input("", label="Testo da provare", multiline=True, min_lines=4, max_lines=12, hint_text="Ieri ho visto Giulia, mi ha scritto a giulia@example.com …")
        self.result = ft.Column([], spacing=10, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

    def build(self) -> ft.Control:
        part = settings_part("velo")
        modes = ft.RadioGroup(
            content=ft.Row(
                [
                    ft.Radio(value="pseudo", label="Pseudonimi reversibili", active_color=T.ACCENT, label_style=ft.TextStyle(color=T.TEXT, size=15)),
                    ft.Radio(value="anon", label="Anonimato", active_color=T.ACCENT, label_style=ft.TextStyle(color=T.TEXT, size=15)),
                ],
                wrap=True,
                spacing=16,
            ),
            value=self.mode,
            on_change=self.mode_changed,
        )
        return W.screen(
            [
                W.screen_header(part.nickname, part.label, NOMENCLATURE["anonymizer"].source, on_back=self.ctx.back),
                W.panel(
                    ft.Column(
                        [
                            W.body(EXPLAIN, size=14),
                            self.input,
                            modes,
                            ft.Row(
                                [W.primary_button("Prova", self.run, icon="VISIBILITY_OFF_OUTLINED"), W.secondary_button("Usa l'ultima voce", self.use_latest, icon="EDIT_NOTE")],
                                wrap=True,
                                spacing=8,
                                run_spacing=8,
                            ),
                        ],
                        spacing=12,
                    )
                ),
                self.result,
            ],
            self.ctx.wide,
        )

    def mode_changed(self, event: Any) -> None:
        self.mode = event.control.value or "pseudo"
        if self.result.controls:
            self.run()

    def use_latest(self, _: Any = None) -> None:
        with self.ctx.store() as store:
            text = vm.latest_entry_text(store)
        if not text:
            self.ctx.toast("Non ci sono ancora voci con del testo.")
            return
        self.input.value = text
        self.run()

    def run(self, _: Any = None) -> None:
        text = (self.input.value or "").strip()
        if not text:
            self.result.controls = [W.caption("Scrivi o incolla un testo, poi tocca Prova.")]
            self.ctx.update()
            return
        with self.ctx.store() as store:
            preview = vm.anonymize_preview(store, text, self.mode)
        controls: List[ft.Control] = []
        if not preview.name_forms:
            controls.append(W.caption("Nessuna voce Persona: i nomi di persona non vengono riconosciuti. Aggiungile con il pacchetto Persone, in Modelli → Scuole."))
        controls.append(
            W.panel(
                ft.Column(
                    [W.body("Testo da inviare", size=16, weight=ft.FontWeight.W_600), ft.Text(preview.text, selectable=True, size=14, color=T.TEXT)],
                    spacing=8,
                )
            )
        )
        if preview.rows:
            rows: List[ft.Control] = [W.body(f"Sostituzioni ({sum(row.times for row in preview.rows)})", size=16, weight=ft.FontWeight.W_600)]
            for row in preview.rows:
                times = f" · {row.times} volte" if row.times > 1 else ""
                rows.append(W.info_row(f"{row.kind}{times}", f"{row.original}  →  {row.placeholder}"))
            controls.append(W.panel(ft.Column(rows, spacing=10)))
        else:
            controls.append(W.body("Nessun dato personale riconosciuto.", dim=True))
        controls.append(W.caption(f"{MODE_NOTES[preview.mode]} {RULES_WARNING}"))
        self.result.controls = controls
        self.ctx.update()


def build(ctx: AppContext) -> ft.Control:
    return VeloScreen(ctx).build()
