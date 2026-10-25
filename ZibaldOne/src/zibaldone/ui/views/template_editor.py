"""The template editor: name, look and the list of blocks (Atomi) of a template."""

from typing import Any, List, Optional

import flet as ft

from zibaldone.core.areas import AREA_LIST
from zibaldone.core.blocks import BLOCK_TYPES
from zibaldone.core.brand import NOMENCLATURE
from zibaldone.core.templates import slugify
from zibaldone.storage.database import StoreError
from zibaldone.ui import carousel
from zibaldone.ui import theme as T
from zibaldone.ui import viewmodels as vm
from zibaldone.ui import widgets as W
from zibaldone.ui.context import AppContext
from zibaldone.ui.navigation import Route
from zibaldone.ui.views.common import not_found

AUTO = "*"


class TemplateEditor:
    def __init__(self, ctx: AppContext, state: vm.EditorState, entry_count: int, template_slugs: List[tuple]) -> None:
        self.ctx = ctx
        self.state = state
        self.entry_count = entry_count
        self.template_slugs = template_slugs  # (slug, name) for link options
        self.blocks_column = ft.Column(spacing=12)
        self.error = W.error_text()
        self.title_menu: Optional[ft.Dropdown] = None
        self.color_row = ft.Row(spacing=8, wrap=True, run_spacing=8)
        self.area_chips = ft.Row(spacing=4, wrap=True, run_spacing=4, alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        self.dirty = False

    # — layout —

    def build(self) -> ft.Control:
        state = self.state
        title = "Nuovo modello" if state.is_new else state.name
        actions: List[ft.Control] = [W.primary_button("Salva il modello", self.save, icon="CHECK")]
        if not state.is_new:
            actions.append(W.secondary_button("Scrivi una voce", lambda _: self.ctx.go(f"/scrivi/{state.slug}"), icon="EDIT_NOTE"))
            actions.append(
                W.secondary_button("Cancella", self.ask_delete, icon="DELETE_OUTLINE", disabled=self.entry_count > 0)
            )
        subtitle = "un modello è una ricetta di blocchi: ogni voce la compila"
        if not state.is_new:
            subtitle = f"nome tecnico «{state.slug}» · " + ("nessuna voce" if self.entry_count == 0 else f"{self.entry_count} voci scritte")
        name = W.text_input(state.name, label="Nome *", on_change=lambda e: self._set("name", e.control.value))
        description = W.text_input(state.description, label="Descrizione", multiline=True, min_lines=1, max_lines=3, on_change=lambda e: self._set("description", e.control.value))
        category = W.text_input(state.category, label="Categoria", hint_text="diario, collezioni, io, persone o una tua", on_change=lambda e: self._set("category", e.control.value))
        icons = list(vm.TEMPLATE_ICONS)
        if state.icon and state.icon not in icons:
            icons.insert(0, state.icon)
        icon_menu = ft.Dropdown(
            options=[ft.DropdownOption(key=name, text=name.replace("_", " ").lower(), leading_icon=W.icon_of(name)) for name in icons],
            value=state.icon or None,
            label="Icona",
            on_select=lambda e: self._set("icon", e.control.value or ""),
            border=W.input_border(),
            filled=True,
            fill_color=T.BG,
            menu_height=360,
            expand=True,
        )
        self._draw_colors()
        self._draw_area()
        look = W.panel(
            ft.Column(
                [
                    W.wide(name),
                    W.wide(description),
                    ft.ResponsiveRow(
                        [ft.Container(category, col={"xs": 12, "md": 6}), ft.Container(ft.Row([icon_menu]), col={"xs": 12, "md": 6})],
                        spacing=12,
                        run_spacing=12,
                    ),
                    ft.Column([W.caption("Colore"), self.color_row], spacing=6),
                    ft.Column([W.caption("Aree della vita delle sue voci (anche più di una; nessuna = Generale)"), self.area_chips], spacing=6),
                ],
                spacing=14,
            )
        )
        self._draw_blocks(update=False)
        self.title_menu = W.dropdown([], None, label="Il titolo di ogni voce viene da", on_select=self._title_changed, expand=True)
        self._fill_title_menu()
        return W.screen(
            [
                W.screen_header(title, NOMENCLATURE["template"].name, subtitle, on_back=self.leave, actions=actions),
                look,
                W.section_label("Blocchi", NOMENCLATURE["block"].name),
                self.blocks_column,
                ft.Row([W.secondary_button("Aggiungi un blocco", self.add_dialog, icon="ADD")]),
                W.panel(ft.Row([self.title_menu]), padding=14),
                self.error,
                ft.Row([W.text_button("Annulla", self.leave, color=T.TEXT), W.primary_button("Salva il modello", self.save, icon="CHECK")], alignment=ft.MainAxisAlignment.END),
            ],
            self.ctx.wide,
        )

    def _set(self, attribute: str, value: Any) -> None:
        setattr(self.state, attribute, value or "")
        self.dirty = True

    def _draw_area(self) -> None:
        """One chip with the mascot of each area; the ones on are the template's areas."""
        on = ([self.state.area] if self.state.area else []) + list(self.state.areas)
        self.area_chips.controls = [
            carousel.bar_item(W.mascot_avatar(area.mascot, 30), area.color, area.label, area.key in on, lambda key=area.key: self.toggle_area(key))
            for area in AREA_LIST
        ]

    def toggle_area(self, key: str) -> None:
        self.state.area, self.state.areas = vm.toggle_template_area(self.state.area, self.state.areas, key)
        self.dirty = True
        self._draw_area()
        self.ctx.update(self.area_chips)

    def _draw_colors(self) -> None:
        swatches = []
        for color in vm.TEMPLATE_COLORS:
            selected = self.state.color.upper() == color.upper()
            swatches.append(
                ft.Container(
                    ft.Icon(ft.Icons.CHECK, size=16, color=T.readable_on(color)) if selected else None,
                    width=32,
                    height=32,
                    bgcolor=color,
                    border_radius=16,
                    border=ft.Border.all(2, T.TEXT if selected else T.BORDER),
                    alignment=ft.Alignment.CENTER,
                    on_click=lambda _, color=color: self.pick_color(color),
                    tooltip=color,
                )
            )
        self.color_row.controls = swatches

    def pick_color(self, color: str) -> None:
        self.state.color = color
        self.dirty = True
        self._draw_colors()
        self.ctx.update(self.color_row)

    def _fill_title_menu(self) -> None:
        if self.title_menu is None:
            return
        options = [(AUTO, "automatico (il primo testo breve)")]
        options += [(block.key, block.label) for block in self.state.blocks if block.key and block.type in ("text", "bookmark", "date", "choice")]
        self.title_menu.options = [ft.DropdownOption(key=key, text=text) for key, text in options]
        keys = [key for key, _ in options]
        self.title_menu.value = self.state.title_block if self.state.title_block in keys else AUTO

    def _title_changed(self, event: Any) -> None:
        value = event.control.value
        self.state.title_block = "" if value in (None, AUTO) else value
        self.dirty = True

    def _draw_blocks(self, update: bool = True) -> None:
        count = len(self.state.blocks)
        self.blocks_column.controls = [self._block_panel(index, block, count) for index, block in enumerate(self.state.blocks)]
        if not self.state.blocks:
            self.blocks_column.controls = [W.empty_state("Ancora nessun blocco: aggiungi il primo, per esempio un «Aforisma · Testo breve» per il titolo.", "WIDGETS_OUTLINED")]
        if update:
            self._fill_title_menu()
            self.ctx.update(self.blocks_column, *( [self.title_menu] if self.title_menu else []))

    def _block_panel(self, index: int, block: vm.EditorBlock, count: int) -> ft.Control:
        block_type = BLOCK_TYPES[block.type]
        header = ft.Row(
            [
                ft.Container(ft.Text(str(index + 1), size=13, color=T.BG, weight=ft.FontWeight.W_700), width=26, height=26, bgcolor=T.ACCENT, border_radius=13, alignment=ft.Alignment.CENTER),
                ft.Column([ft.Text(block.caption, size=14, weight=ft.FontWeight.W_600, color=T.TEXT), W.caption(block_type.description)], spacing=0, expand=True),
                W.icon_button("ARROW_UPWARD", lambda _: self.move(index, -1), "Sposta su", disabled=index == 0),
                W.icon_button("ARROW_DOWNWARD", lambda _: self.move(index, 1), "Sposta giù", disabled=index == count - 1),
                W.icon_button("DELETE_OUTLINE", lambda _: self.remove(index), "Togli il blocco"),
            ],
            spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        label = W.text_input(block.label, label="Etichetta *", on_change=lambda e: self._block_set(block, "label", e.control.value or ""))
        required = ft.Checkbox(label="Obbligatorio", value=block.required, active_color=T.ACCENT, on_change=lambda e: self._block_set(block, "required", bool(e.control.value)))
        option_controls: List[ft.Control] = []
        for item in vm.OPTION_FIELDS.get(block.type, ()):
            option_controls.append(ft.Container(self._option_control(block, item), col={"xs": 12, "md": 6}))
        parts: List[ft.Control] = [header, ft.ResponsiveRow([ft.Container(label, col={"xs": 12, "md": 8}), ft.Container(required, col={"xs": 12, "md": 4}, alignment=ft.Alignment.CENTER_LEFT)], spacing=12, run_spacing=8)]
        if option_controls:
            parts.append(ft.ResponsiveRow(option_controls, spacing=12, run_spacing=12))
        if block.key:
            parts.append(W.caption(f"chiave: {block.key} · il tipo di un blocco già salvato non si cambia"))
        return W.panel(ft.Column(parts, spacing=12), padding=14)

    def _option_control(self, block: vm.EditorBlock, item: vm.OptionField) -> ft.Control:
        current = block.options.get(item.name, "")
        if item.kind == "bool":
            return ft.Checkbox(
                label=item.label,
                value=current == "true",
                active_color=T.ACCENT,
                on_change=lambda e: self._option_set(block, item.name, "true" if e.control.value else ""),
            )
        if item.kind == "template":
            options = [(AUTO, "qualsiasi modello")] + list(self.template_slugs)
            return ft.Row(
                [
                    W.dropdown(
                        options,
                        current or AUTO,
                        label=item.label,
                        on_select=lambda e: self._option_set(block, item.name, "" if e.control.value in (None, AUTO) else e.control.value),
                        expand=True,
                    )
                ]
            )
        keyboard = ft.KeyboardType.NUMBER if item.kind in ("int", "number") else ft.KeyboardType.TEXT
        return W.text_input(
            current,
            label=item.label,
            hint_text=item.hint or None,
            keyboard_type=keyboard,
            on_change=lambda e: self._option_set(block, item.name, e.control.value or ""),
        )

    def _block_set(self, block: vm.EditorBlock, attribute: str, value: Any) -> None:
        setattr(block, attribute, value)
        self.dirty = True

    def _option_set(self, block: vm.EditorBlock, name: str, value: str) -> None:
        block.options[name] = value
        self.dirty = True

    # — block list actions —

    def move(self, index: int, delta: int) -> None:
        self.state.blocks = vm.move_block(self.state.blocks, index, delta)
        self.dirty = True
        self._draw_blocks()

    def remove(self, index: int) -> None:
        block = self.state.blocks[index]

        def drop() -> None:
            self.state.blocks = [item for position, item in enumerate(self.state.blocks) if position != index]
            self.dirty = True
            self._draw_blocks()

        if block.key and self.entry_count:
            self.ctx.confirm(
                "Togliere questo blocco?",
                f"Le voci già scritte hanno dei valori in «{block.label}»: se togli il blocco, il salvataggio non sarà possibile finché quei valori esistono.",
                "Togli",
                drop,
            )
        else:
            drop()

    def add_dialog(self, _: Any = None) -> None:
        def add(type_name: str) -> None:
            self.ctx.close_dialog()
            self.state.blocks.append(vm.new_editor_block(type_name))
            self.dirty = True
            self._draw_blocks()

        rows = [
            ft.Container(
                ft.Column([ft.Text(caption, size=15, weight=ft.FontWeight.W_600, color=T.TEXT), W.caption(description)], spacing=0),
                padding=ft.Padding.symmetric(horizontal=10, vertical=8),
                border_radius=T.RADIUS_SMALL,
                on_click=lambda _, name=name: add(name),
                ink=True,
            )
            for name, caption, description in vm.block_type_choices()
        ]
        dialog = ft.AlertDialog(
            title="Che blocco aggiungo?",
            content=ft.Container(ft.Column(rows, spacing=2, scroll=ft.ScrollMode.AUTO), width=440, height=480),
            actions=[W.text_button("Annulla", self.ctx.close_dialog, color=T.TEXT)],
        )
        self.ctx.show_dialog(dialog)

    # — save, leave, delete —

    def save(self, _: Any = None) -> None:
        state = self.state
        try:
            with self.ctx.store() as store:
                slug = state.slug or store.free_slug(slugify(state.name or "modello"))
                template = vm.template_from_editor(state, slug)
                if not state.is_new:
                    broken = vm.entries_broken_by(store, template)
                    if broken:
                        raise ValueError(
                            f"{broken} voci già scritte non sarebbero più valide con queste modifiche. "
                            "Cambia le voci prima, oppure crea un modello nuovo."
                        )
                store.save_template(template, replace=not state.is_new)
        except (ValueError, StoreError) as problem:
            self.error.value = str(problem)
            self.error.visible = True
            self.ctx.update(self.error)
            self.ctx.toast("Il modello non è stato salvato: guarda in fondo alla pagina.", error=True)
            return
        self.dirty = False
        self.ctx.data_changed()
        self.ctx.toast(f"Modello «{template.name}» salvato.")
        self.ctx.go("/modelli", replace=True)

    def leave(self, _: Any = None) -> None:
        if not self.dirty:
            self.ctx.back()
            return
        self.ctx.confirm("Lasciare senza salvare?", "Le modifiche al modello andranno perse.", "Lascia", self.ctx.back, cancel_label="Resta")

    def ask_delete(self, _: Any = None) -> None:
        def delete() -> None:
            try:
                with self.ctx.store() as store:
                    store.delete_template(self.state.slug)
            except StoreError as problem:
                self.ctx.toast(str(problem), error=True)
                return
            self.ctx.data_changed()
            self.ctx.toast("Modello cancellato.")
            self.ctx.go("/modelli", replace=True)

        self.ctx.confirm("Cancellare il modello?", f"«{self.state.name}» non ha voci: sparirà dalle tue Forme. Puoi sempre reinstallarlo o ricrearlo.", "Cancella", delete)


def build(ctx: AppContext, route: Route) -> ft.Control:
    with ctx.store() as store:
        templates = store.list_templates()
        slugs = [(template.slug, template.name) for template in templates]
        if route.arg:
            template = store.find_template(route.arg)
            if template is None:
                return not_found(ctx, f"Non c'è un modello «{route.arg}».")
            state = vm.editor_from_template(template)
            count = store.count_entries(template.slug)
        else:
            state = vm.EditorState(color=T.ACCENT, icon="ARTICLE_OUTLINED", blocks=[vm.new_editor_block("text")])
            state.blocks[0].label = "Titolo"
            count = 0
    return TemplateEditor(ctx, state, count, slugs).build()
