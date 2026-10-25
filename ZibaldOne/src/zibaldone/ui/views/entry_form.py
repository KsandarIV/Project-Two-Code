"""The entry form, generated from the template: one control per block type.

Each editor keeps its block's state in `EntryForm.states` (see `ui/forms.py`)
and redraws only itself; saving goes through `forms.collect_values`, so the
core decides what is valid and its Italian messages appear under the field.
"""

from datetime import date
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import flet as ft

from zibaldone.core import secrets
from zibaldone.core.brand import mascot_for
from zibaldone.core.templates import BlockSpec, Entry, Template
from zibaldone.storage.database import StoreError
from zibaldone.ui import cloud_model as cm
from zibaldone.ui import drafts
from zibaldone.ui import forms
from zibaldone.ui import theme as T
from zibaldone.ui import viewmodels as vm
from zibaldone.ui import widgets as W
from zibaldone.ui.context import AppContext
from zibaldone.ui.navigation import Route
from zibaldone.storage import media
from zibaldone.ui.views.common import not_found, pick_date
from zibaldone.ui.views.media_view import attachment_list
from zibaldone.ui.views.vault import unlock_secrets, vault_of

AREA_KEY = "_area"


class FieldEditor:
    """Base: holds the block spec and writes its state into the form."""

    def __init__(self, form: "EntryForm", spec: BlockSpec) -> None:
        self.form = form
        self.spec = spec
        self.ctx = form.ctx

    @property
    def state(self) -> Any:
        return self.form.states[self.spec.key]

    @state.setter
    def state(self, value: Any) -> None:
        self.form.states[self.spec.key] = value
        self.form.dirty = True

    def build(self) -> ft.Control:
        raise NotImplementedError


class TextEditor(FieldEditor):
    def build(self) -> ft.Control:
        long = self.spec.type == "longtext"
        keyboard = {"email": ft.KeyboardType.EMAIL, "telefono": ft.KeyboardType.PHONE}.get(self.spec.options.get("format", ""))
        field = W.text_input(
            self.state,
            hint_text=forms.field_hint(self.spec) or None,
            **({"keyboard_type": keyboard} if keyboard else {}),
            multiline=long,
            min_lines=3 if long else 1,
            max_lines=12 if long else 1,
            on_change=self.changed,
            expand=True,
        )
        return ft.Row([field])  # a TextField alone in a Column stays narrow

    def changed(self, event: Any) -> None:
        self.state = event.control.value or ""


class NumberEditor(TextEditor):
    def build(self) -> ft.Control:
        unit = self.spec.options.get("unit")
        return W.text_input(
            self.state,
            hint_text=forms.field_hint(self.spec),
            keyboard_type=ft.KeyboardType.NUMBER,
            suffix=unit or None,
            width=260,
            on_change=self.changed,
        )


class RatingEditor(FieldEditor):
    def build(self) -> ft.Control:
        self.holder = ft.Row([self._stars()], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER, wrap=True)
        return self.holder

    def _stars(self) -> ft.Control:
        top = forms.rating_max(self.spec)
        label = "nessun voto" if self.state is None else f"{forms.format_number(self.state)} su {top}"
        return ft.Row([W.stars(self.state, top, size=28, on_pick=self.pick), W.caption(label)], spacing=8, wrap=True)

    def pick(self, number: int) -> None:
        self.state = forms.toggle_rating(self.state, number, bool(self.spec.options.get("half")))
        self.holder.controls = [self._stars()]
        self.ctx.update(self.holder)


class FavoriteEditor(FieldEditor):
    def build(self) -> ft.Control:
        self.button = W.icon_button("FAVORITE_BORDER", self.toggle, "Preferito", size=28)
        self.note = W.caption("")
        self._redraw(update=False)
        return ft.Row([self.button, self.note], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    def _redraw(self, update: bool = True) -> None:
        on = bool(self.state)
        self.button.icon = W.icon_of("FAVORITE" if on else "FAVORITE_BORDER")
        self.button.icon_color = T.ACCENT_2 if on else T.TEXT_DIM
        self.note.value = "tra i preferiti" if on else "non è tra i preferiti"
        if update:
            self.ctx.update(self.button, self.note)

    def toggle(self, _: Any) -> None:
        self.state = None if self.state else True
        self._redraw()


class TagsEditor(FieldEditor):
    def build(self) -> ft.Control:
        self.known = self.form.known_tags(self.spec.key)
        self.chips = ft.Row(spacing=6, run_spacing=6, wrap=True)
        self.suggestions = ft.Row(spacing=6, run_spacing=6, wrap=True)
        self.input = W.text_input(
            self.state.get("text", ""),
            hint_text="scrivi e metti una virgola per aggiungere",
            on_change=self.changed,
            on_submit=self.finish,
            on_blur=self.finish,
            expand=True,
        )
        self._redraw(update=False)
        return ft.Column([self.chips, ft.Row([self.input]), self.suggestions], spacing=8)

    def _redraw(self, update: bool = True) -> None:
        tags = self.state.get("tags", [])
        self.chips.controls = [W.tag_chip(tag, lambda _, tag=tag: self.remove(tag)) for tag in tags]
        self.chips.visible = bool(tags)
        found = forms.tag_suggestions(self.spec, self.known, tags, self.state.get("text", ""))
        self.suggestions.controls = [W.suggestion_chip(tag, lambda _, tag=tag: self.add(tag)) for tag in found]
        self.suggestions.visible = bool(found)
        if update:
            self.ctx.update(self.chips, self.suggestions)

    def changed(self, event: Any) -> None:
        text = event.control.value or ""
        tags, remainder = forms.absorb_tag_text(self.state.get("tags", []), text)
        self.state = {"tags": tags, "text": remainder}
        if remainder != text:
            self.input.value = remainder
            self.ctx.update(self.input)
        self._redraw()

    def finish(self, _: Any = None) -> None:
        tags, _rest = forms.absorb_tag_text(self.state.get("tags", []), self.state.get("text", ""), finish=True)
        if tags != self.state.get("tags", []) or self.state.get("text"):
            self.state = {"tags": tags, "text": ""}
            self.input.value = ""
            self.ctx.update(self.input)
            self._redraw()

    def add(self, tag: str) -> None:
        tags, _rest = forms.absorb_tag_text(self.state.get("tags", []), tag, finish=True)
        self.state = {"tags": tags, "text": ""}
        self.input.value = ""
        self.ctx.update(self.input)
        self._redraw()

    def remove(self, tag: str) -> None:
        self.state = {"tags": forms.remove_tag(self.state.get("tags", []), tag), "text": self.state.get("text", "")}
        self._redraw()


class DateEditor(FieldEditor):
    def build(self) -> ft.Control:
        self.button = W.secondary_button("", self.open, icon="CALENDAR_TODAY")
        self.clear = W.icon_button("CLOSE", self.reset, "Togli la data")
        self._redraw(update=False)
        return ft.Row([self.button, self.clear], spacing=4)

    def _redraw(self, update: bool = True) -> None:
        try:
            self.button.content = vm.italian_date(date.fromisoformat(self.state)) if self.state else "Scegli il giorno"
        except ValueError:
            self.button.content = str(self.state)
        self.clear.visible = bool(self.state)
        if update:
            self.ctx.update(self.button, self.clear)

    def open(self, _: Any) -> None:
        pick_date(self.ctx, self.state, self.chosen, self.spec.label)

    def chosen(self, day: date) -> None:
        self.state = day.isoformat()
        self._redraw()

    def reset(self, _: Any) -> None:
        self.state = ""
        self._redraw()


class ChecklistEditor(FieldEditor):
    def build(self) -> ft.Control:
        self.items = ft.Column(spacing=2)
        self.new_item = W.text_input("", hint_text="Nuova voce della lista", on_submit=self.add, expand=True, dense=True)
        self.counter = W.caption("")
        self._redraw(update=False)
        add_row = ft.Row([self.new_item, W.secondary_button("Aggiungi", self.add, icon="ADD")], spacing=8)
        return ft.Column([self.items, add_row, self.counter], spacing=8)

    def _redraw(self, update: bool = True) -> None:
        rows = []
        for index, item in enumerate(self.state):
            rows.append(
                ft.Row(
                    [
                        ft.Checkbox(value=bool(item.get("done")), on_change=lambda e, index=index: self.toggle(index, e.control.value), active_color=T.ACCENT),
                        ft.TextField(
                            value=item.get("text", ""),
                            on_change=lambda e, index=index: self.edit(index, e.control.value),
                            border=ft.NoInputBorder(),
                            text_size=15,
                            color=T.TEXT_DIM if item.get("done") else T.TEXT,
                            dense=True,
                            expand=True,
                        ),
                        W.icon_button("DELETE_OUTLINE", lambda _, index=index: self.remove(index), "Togli"),
                    ],
                    spacing=4,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )
        self.items.controls = rows
        done, total = forms.checklist_progress(self.state)
        self.counter.value = f"{done} di {total} fatte" if total else ""
        self.counter.visible = bool(total)
        if update:
            self.ctx.update(self.items, self.counter)

    def add(self, _: Any = None) -> None:
        text = self.new_item.value or ""
        if not text.strip():
            return
        self.state = forms.checklist_add(self.state, text)
        self.new_item.value = ""
        self.ctx.update(self.new_item)
        self._redraw()

    def toggle(self, index: int, done: Optional[bool]) -> None:
        items = [dict(item) for item in self.state]
        items[index]["done"] = bool(done)
        self.state = items
        self._redraw()

    def edit(self, index: int, text: str) -> None:
        items = [dict(item) for item in self.state]
        items[index]["text"] = text or ""
        self.state = items

    def remove(self, index: int) -> None:
        self.state = [item for position, item in enumerate(self.state) if position != index]
        self._redraw()


class ScaleEditor(FieldEditor):
    def build(self) -> ft.Control:
        low, high = forms.scale_bounds(self.spec)
        mascot = mascot_for(self.spec.key)
        self.color = mascot.color if mascot else T.ACCENT
        low_text, high_text = forms.scale_captions(self.spec)
        self.value_text = ft.Text("", size=15, weight=ft.FontWeight.W_600, color=T.TEXT)
        self.clear = W.text_button("azzera", self.reset, color=T.TEXT_DIM)
        self.slider = ft.Slider(
            min=low,
            max=high,
            divisions=high - low,
            value=self.state if self.state is not None else low,
            label="{value}",
            on_change=self.changed,
            inactive_color=T.BORDER,
            thumb_color=self.color,
            expand=True,
        )
        self._redraw(update=False)
        return ft.Column(
            [
                ft.Row([self.value_text, self.clear], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Row([self.slider]),
                ft.Row([W.caption(low_text), W.caption(high_text)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ],
            spacing=0,
        )

    def _redraw(self, update: bool = True) -> None:
        self.value_text.value = forms.scale_value_text(self.spec, self.state)
        self.value_text.color = T.TEXT if self.state is not None else T.TEXT_DIM
        self.slider.active_color = self.color if self.state is not None else T.TEXT_DIM
        self.clear.visible = self.state is not None
        if update:
            self.ctx.update(self.value_text, self.slider, self.clear)

    def changed(self, event: Any) -> None:
        self.state = int(round(event.control.value))
        self._redraw()

    def reset(self, _: Any) -> None:
        self.state = None
        self.slider.value = forms.scale_bounds(self.spec)[0]
        self._redraw()


class ChoiceEditor(FieldEditor):
    def build(self) -> ft.Control:
        self.row = ft.Row(spacing=8, run_spacing=8, wrap=True)
        self._redraw(update=False)
        return self.row

    def _redraw(self, update: bool = True) -> None:
        self.row.controls = [
            ft.Chip(
                label=ft.Text(choice, size=15, color=T.TEXT),
                selected=self.state == choice,
                show_checkmark=False,
                selected_color=W.fade(T.ACCENT, 0.24),
                bgcolor=T.BG,
                border_side=ft.BorderSide(1, T.ACCENT if self.state == choice else T.BORDER),
                on_select=lambda _, choice=choice: self.pick(choice),
            )
            for choice in forms.choice_options(self.spec)
        ]
        if update:
            self.ctx.update(self.row)

    def pick(self, choice: str) -> None:
        self.state = forms.toggle_choice(self.state, choice)
        self._redraw()


class ProgressEditor(FieldEditor):
    def build(self) -> ft.Control:
        unit = self.spec.options.get("unit", "")
        self.status = W.dropdown(forms.PROGRESS_CHOICES, self.state.get("status"), label="Stato", width=210, on_select=self.status_changed)
        self.current = W.text_input(self.state.get("current", ""), label="A che punto", keyboard_type=ft.KeyboardType.NUMBER, width=140, on_change=self.current_changed)
        self.total = W.text_input(self.state.get("total", ""), label="Totale", keyboard_type=ft.KeyboardType.NUMBER, width=140, suffix=unit or None, on_change=self.total_changed)
        self.bar = W.meter(None)
        self.percent = W.caption("")
        self._redraw(update=False)
        return ft.Column(
            [
                ft.Row([self.status, self.current, self.total], spacing=10, run_spacing=10, wrap=True),
                ft.Row([ft.Container(self.bar, expand=True), self.percent], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ],
            spacing=10,
        )

    def _redraw(self, update: bool = True) -> None:
        fraction = forms.progress_state_fraction(self.spec, self.state)
        self.bar.value = fraction or 0.0
        self.percent.value = f"{round((fraction or 0) * 100)}%" if fraction is not None else ""
        if update:
            self.ctx.update(self.bar, self.percent)

    def _set(self, **changes: Any) -> None:
        self.state = {**self.state, **changes}
        self._redraw()

    def status_changed(self, event: Any) -> None:
        self._set(status=event.control.value)

    def current_changed(self, event: Any) -> None:
        self._set(current=event.control.value or "")

    def total_changed(self, event: Any) -> None:
        self._set(total=event.control.value or "")


class LinkEditor(FieldEditor):
    def build(self) -> ft.Control:
        self.candidates = dict(self.form.link_candidates(self.spec))
        self.many = forms.link_allows_many(self.spec)
        self.chips = ft.Row(spacing=6, run_spacing=6, wrap=True)
        if not self.candidates:
            wanted = self.spec.options.get("template")
            note = f"Non ci sono ancora voci «{self.form.template_name(wanted)}» da collegare." if wanted else "Non ci sono ancora voci da collegare."
            self._redraw(update=False)
            return ft.Column([self.chips, W.caption(note)], spacing=8)
        self.menu = W.dropdown(
            sorted(self.candidates.items(), key=lambda item: item[1].lower()),
            None,
            label="Aggiungi un collegamento" if self.many else "Scegli una voce",
            editable=True,
            enable_filter=True,
            menu_height=320,
            on_select=self.chosen,
            expand=True,
        )
        self._redraw(update=False)
        return ft.Column([self.chips, ft.Row([self.menu])], spacing=8)

    def _redraw(self, update: bool = True) -> None:
        self.chips.controls = [
            W.tag_chip(self.candidates.get(entry_id, entry_id[:8]), lambda _, entry_id=entry_id: self.remove(entry_id)) for entry_id in self.state
        ]
        self.chips.visible = bool(self.state)
        if update:
            self.ctx.update(self.chips)

    def chosen(self, event: Any) -> None:
        entry_id = event.control.value
        if not entry_id:
            return
        self.state = forms.add_link(self.state, entry_id, self.many)
        self._redraw()

    def remove(self, entry_id: str) -> None:
        self.state = [item for item in self.state if item != entry_id]
        self._redraw()


class SecretEditor(FieldEditor):
    """A secret (0.2.3): while closed an empty field keeps it; «Apri» shows it to change it."""

    def build(self) -> ft.Control:
        multiline = bool(self.spec.options.get("multiline"))
        self.field = W.text_input(
            self.state.get("text", ""),
            hint_text=forms.field_hint(self.spec) or None,
            password=not multiline,
            can_reveal_password=not multiline,
            multiline=multiline,
            min_lines=3 if multiline else 1,
            max_lines=12 if multiline else 1,
            on_change=self.changed,
            expand=True,
        )
        self.note = W.caption("")
        self.open_button = W.text_button("Apri", self.open, icon="LOCK_OPEN")
        self.remove_button = W.text_button("Togli", self.remove, icon="DELETE_OUTLINE", color=T.TEXT_DIM)
        self._redraw(update=False)
        actions = ft.Row([self.note, self.open_button, self.remove_button], wrap=True, spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        return ft.Column([ft.Row([self.field]), actions], spacing=6)

    def _redraw(self, update: bool = True) -> None:
        closed = self.state.get("sealed") is not None and self.state.get("original") is None
        if closed:
            self.note.value = f"{secrets.LOCKED_TEXT}: se lasci vuoto resta com'è, quello che scrivi lo sostituisce"
        else:
            self.note.value = secrets.LEVEL_LABELS[secrets.level_of(self.spec.options)]
        self.open_button.visible = closed
        self.remove_button.visible = self.state.get("sealed") is not None
        if update:
            self.ctx.update(self.field, self.note, self.open_button, self.remove_button)

    def changed(self, event: Any) -> None:
        self.state = {**self.state, "text": event.control.value or ""}

    def show(self, text: str) -> None:
        self.form.states[self.spec.key] = forms.reveal_secret_state(self.state, text)  # seeing it is not a change
        self.field.value = text
        self._redraw()

    def open(self, _: Any) -> None:
        sealed = self.state.get("sealed")

        def opened() -> None:
            try:
                self.show(vault_of(self.ctx).reveal(sealed, self.ctx.now()))
            except secrets.SecretsError as error:
                self.ctx.toast(cm.error_text(error), error=True)

        unlock_secrets(self.ctx, [sealed], opened)

    def remove(self, _: Any) -> None:
        self.state = forms.removed_secret_state()
        self.field.value = ""
        self._redraw()


class MediaEditor(FieldEditor):
    """Attached files (0.2.4): «Aggiungi file» copies them into the media folder at once."""

    def build(self) -> ft.Control:
        self.holder = ft.Column(spacing=8)
        self.add_button = W.secondary_button("Aggiungi file", lambda _: self.ctx.pick_files(self.add_files), icon="ATTACH_FILE")
        self._redraw(update=False)
        return ft.Column([self.holder, ft.Row([self.add_button])], spacing=8)

    def _redraw(self, update: bool = True) -> None:
        self.holder.controls = [attachment_list(self.ctx, self.state, on_remove=self.remove)] if self.state else []
        self.holder.visible = bool(self.state)
        if update:
            self.ctx.update(self.holder)

    def add_files(self, files: List[Any]) -> None:
        """Files from the picker: a path on PC and phone, the bytes in the browser."""
        folder = self.ctx.folder

        def work() -> List[Dict[str, Any]]:
            added = []
            for picked in files:
                if getattr(picked, "path", None):
                    added.append(media.add_file(folder, Path(picked.path)).to_value())
                elif getattr(picked, "bytes", None):
                    added.append(media.add_bytes(folder, picked.name, picked.bytes).to_value())
                else:
                    raise media.MediaError(f"non riesco a leggere «{picked.name}» da qui")
            return added

        def done(added: List[Dict[str, Any]]) -> None:
            known = {item["file"] for item in self.state}
            self.state = list(self.state) + [item for item in added if item["file"] not in known]
            self._redraw()

        def failed(problem: Exception) -> None:
            self.ctx.toast(cm.error_text(problem), error=True)

        if files:
            self.ctx.run_blocking(work, done, failed)

    def remove(self, file: str) -> None:
        self.state = [item for item in self.state if item["file"] != file]
        self._redraw()


EDITORS: Dict[str, Callable[["EntryForm", BlockSpec], FieldEditor]] = {
    "text": TextEditor,
    "longtext": TextEditor,
    "bookmark": TextEditor,
    "number": NumberEditor,
    "rating": RatingEditor,
    "tags": TagsEditor,
    "date": DateEditor,
    "checklist": ChecklistEditor,
    "scale": ScaleEditor,
    "choice": ChoiceEditor,
    "progress": ProgressEditor,
    "link": LinkEditor,
    "secret": SecretEditor,
    "media": MediaEditor,
    "favorite": FavoriteEditor,
}


class EntryForm:
    def __init__(self, ctx: AppContext, template: Template, entry: Optional[Entry] = None, area: str = "", draft: Optional[Dict[str, Any]] = None) -> None:
        self.ctx = ctx
        self.template = template
        self.entry = entry
        self.draft_key = drafts.key_of(template.slug, entry.id if entry else "")
        self.area = entry.area if entry else area  # 0.2.0: '' = the template's area
        values = dict(entry.values) if entry else {}
        self.day = entry.day if entry else ctx.now().date().isoformat()
        if draft is not None:  # the draft holds every block it keeps: a block missing from it was emptied
            left_out = {spec.key for spec in template.blocks if spec.type in drafts.KEPT_OUT}
            values = {**{key: value for key, value in values.items() if key in left_out}, **draft["values"]}
            self.day, self.area = draft.get("day") or self.day, draft.get("area", self.area)
        self.states: Dict[str, Any] = forms.initial_states(template, values)
        self._show_open_secrets()
        self.draft = draft
        self.dirty = draft is not None
        self.errors: Dict[str, ft.Text] = {}
        self._entries: Optional[List[Entry]] = None
        self._templates: Optional[Dict[str, Template]] = None

    def _show_open_secrets(self) -> None:
        """Secrets the vault can open right now are shown in their fields, to change them."""
        vault, now = vault_of(self.ctx), self.ctx.now()
        for spec in secrets.secret_specs(self.template):
            sealed = self.states[spec.key].get("sealed")
            if sealed and vault.can_open(sealed, now):
                try:
                    self.states[spec.key] = forms.reveal_secret_state(self.states[spec.key], vault.reveal(sealed, now))
                except secrets.SecretsError:
                    continue  # stays closed; the field says so

    # — data the editors need —

    def _load(self) -> None:
        if self._entries is None:
            with self.ctx.store() as store:
                self._entries = store.list_entries()
                self._templates = {template.slug: template for template in store.list_templates()}

    def known_tags(self, key: str) -> List[str]:
        self._load()
        return forms.known_tags((entry for entry in self._entries or [] if entry.template == self.template.slug), key)

    def link_candidates(self, spec: BlockSpec) -> List[tuple]:
        self._load()
        return forms.link_candidates(spec, self._entries or [], self._templates or {}, self.entry.id if self.entry else "")

    def template_name(self, slug: str) -> str:
        self._load()
        template = (self._templates or {}).get(slug)
        return template.name if template else slug

    # — layout —

    def build(self) -> ft.Control:
        editing = self.entry is not None
        self.day_button = W.secondary_button("", self.pick_day, icon="EVENT")
        self.form_error = W.error_text()
        self._day_label()
        self.errors[forms.DAY_KEY] = W.error_text()
        self.errors[AREA_KEY] = W.error_text()
        self.area_menu = W.dropdown(
            vm.area_options(self.template.area),
            self.area or vm.NO_AREA,
            label="Area della vita",
            on_select=self.area_changed,
            width=280,
        )
        fields: List[ft.Control] = [
            W.panel(
                ft.Column(
                    [
                        ft.Row([W.caption("Il giorno di questa voce"), self.day_button], wrap=True, spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        self.errors[forms.DAY_KEY],
                        ft.Row([self.area_menu], wrap=True),
                        self.errors[AREA_KEY],
                    ],
                    spacing=6,
                ),
                padding=ft.Padding.symmetric(horizontal=16, vertical=10),
            )
        ]
        for spec in self.template.blocks:
            fields.append(self._field(spec))
        save_label = "Salva le modifiche" if editing else "Salva"
        bottom = ft.Row(
            [W.text_button("Annulla", self.cancel, color=T.TEXT), W.primary_button(save_label, self.save, icon="CHECK")],
            alignment=ft.MainAxisAlignment.END,
            spacing=8,
        )
        subtitle = self.template.description or ("modifica la voce" if editing else "una nuova voce")
        header = W.screen_header(self.template.name, "modifica" if editing else "nuova voce", subtitle, on_back=self.cancel)
        banner: List[ft.Control] = []
        if self.draft is not None:
            banner.append(
                W.panel(
                    ft.Row(
                        [W.body(f"Ripresa dalla bozza di {self.draft.get('saved', '')[:16].replace('T', ' alle ')}.", size=13, expand=True), W.text_button("Scarta la bozza", self.discard_draft, color=T.TEXT_DIM)],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    border_color=W.fade(T.ACCENT_2, 0.5),
                )
            )
        self.ctx.leave_guard = self.keep_draft
        return W.screen([header, *banner, *fields, self.form_error, bottom], self.ctx.wide)

    def _field(self, spec: BlockSpec) -> ft.Control:
        editor = EDITORS.get(spec.type, TextEditor)(self, spec)
        self.errors[spec.key] = W.error_text()
        label_items: List[ft.Control] = []
        mascot = mascot_for(spec.key) if spec.type == "scale" else None
        if mascot is not None:
            label_items.append(W.mascot_avatar(mascot, 30))
        texts: List[ft.Control] = [ft.Text(forms.field_label(spec), size=15, weight=ft.FontWeight.W_600, color=T.TEXT)]
        if mascot is not None:
            texts.append(W.caption(f"{mascot.name}, {mascot.animal} · {mascot.philosopher}"))
        label_items.append(ft.Column(texts, spacing=0, expand=True))
        hint = forms.type_hint(spec.type)
        label_items.append(
            ft.Container(
                ft.Row([ft.Text(forms.type_caption(spec.type), size=11, color=T.TEXT_DIM, italic=True), ft.Icon(ft.Icons.INFO_OUTLINE, size=14, color=T.TEXT_DIM)], spacing=4),
                tooltip=hint,
                on_click=lambda _, text=hint: self.ctx.toast(text),
                ink=True,
                border_radius=T.RADIUS_SMALL,
                padding=ft.Padding.all(4),
            )
        )
        return W.panel(
            ft.Column(
                [ft.Row(label_items, spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER), editor.build(), self.errors[spec.key]],
                spacing=10,
            ),
            padding=ft.Padding.only(left=16, right=16, top=14, bottom=12),
        )

    def _day_label(self) -> None:
        try:
            day = date.fromisoformat(self.day)
            label = vm.italian_date(day)
            if day == self.ctx.now().date():
                label = f"oggi, {label}"
        except ValueError:
            label = self.day
        self.day_button.content = label

    # — actions —

    def pick_day(self, _: Any) -> None:
        def chosen(day: date) -> None:
            self.day = day.isoformat()
            self.dirty = True
            self._day_label()
            self.ctx.update(self.day_button)

        pick_date(self.ctx, self.day, chosen, "Il giorno della voce")

    def area_changed(self, event: Any) -> None:
        self.area = vm.area_from_option(event.control.value)
        self.dirty = True

    def cancel(self, _: Any = None) -> None:
        self.ctx.back()  # leaving a half-written entry keeps it as a draft (`keep_draft`, run by the shell)

    def keep_draft(self) -> None:
        """Leaving the form (back button, another section): what was written stays as a draft."""
        if not self.dirty:
            return
        result = forms.collect_values(self.template, self.states, self.day)  # values of the valid blocks, even when others still miss
        try:
            drafts.put(self.ctx.folder, self.template, result.values, self.day, self.area, self.entry.id if self.entry else "", self.ctx.now())
        except OSError as problem:
            self.ctx.toast(f"Non riesco a salvare la bozza: {problem}", error=True)
            return
        self.dirty = False
        self.ctx.toast("Bozza salvata: la ritrovi in Voci.")

    def discard_draft(self, _: Any = None) -> None:
        self.dirty = False
        drafts.discard(self.ctx.folder, self.draft_key)
        self.ctx.toast("Bozza scartata.")
        self.ctx.back()

    def show_errors(self, errors: Dict[str, str]) -> None:
        for key, text in self.errors.items():
            message = errors.get(key, "")
            text.value = message
            text.visible = bool(message)
        general = errors.get(forms.FORM_KEY, "")
        self.form_error.value = general
        self.form_error.visible = bool(general)

    def save(self, _: Any = None) -> None:
        result = forms.collect_values(self.template, self.states, self.day)
        area_problem = vm.entry_area_problem(self.template, self.area)
        if area_problem:
            result.errors[AREA_KEY] = area_problem
        self.show_errors(result.errors)
        if not result.ok or area_problem:
            labels = [spec.label for spec in self.template.blocks if spec.key in result.errors]
            if forms.DAY_KEY in result.errors:
                labels.insert(0, "giorno")
            if area_problem:
                labels.insert(0, "area")
            self.ctx.toast(f"Da sistemare: {', '.join(labels) or 'la voce'}.", error=True)
            self.ctx.update()
            return
        try:
            with self.ctx.store() as store:
                if self.entry is not None:
                    saved = store.update_entry(self.entry.id, result.values, day=result.day or None, merge=False, area=self.area)
                else:
                    saved = store.add_entry(self.template.slug, result.values, day=result.day or None, area=self.area or None)
        except (StoreError, ValueError) as error:
            self.show_errors({forms.FORM_KEY: cm.app_hint(str(error))})
            self.ctx.update()
            return
        self.dirty = False
        drafts.discard(self.ctx.folder, self.draft_key)
        self.ctx.data_changed()
        self.ctx.toast("Voce salvata." if self.entry is None else "Modifiche salvate.")
        self.ctx.go(f"/voci/{saved.id}", replace=True)


def build_new(ctx: AppContext, route: Route) -> ft.Control:
    with ctx.store() as store:
        template = store.find_template(route.arg)
    if template is None:
        return not_found(ctx, f"Non c'è un modello «{route.arg}». Puoi installarlo dalle Scuole o crearlo nelle Forme.")
    return EntryForm(ctx, template, area=route.extra, draft=drafts.get(ctx.folder, drafts.key_of(template.slug))).build()


def build_edit(ctx: AppContext, route: Route) -> ft.Control:
    try:
        with ctx.store() as store:
            entry = store.get_entry(route.arg)
            template = store.get_template(entry.template)
    except StoreError:
        return not_found(ctx, "Questa voce non esiste più.")
    return EntryForm(ctx, template, entry, draft=drafts.get(ctx.folder, drafts.key_of(template.slug, entry.id))).build()
