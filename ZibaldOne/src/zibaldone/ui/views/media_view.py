"""Attached files in the app (0.2.4): photos shown in the entry, the rest opened with the system."""

from typing import Any, Callable, List, Mapping, Optional, Sequence

import flet as ft

from zibaldone.core.blocks import media_kind
from zibaldone.storage import media
from zibaldone.ui import theme as T
from zibaldone.ui import widgets as W
from zibaldone.ui.context import AppContext

KIND_ICONS = {"foto": "PHOTO_OUTLINED", "video": "VIDEOCAM_OUTLINED", "audio": "AUDIOTRACK", "documento": "DESCRIPTION_OUTLINED"}
MAX_PREVIEW_BYTES = 15 * 1024 * 1024
THUMB = 120


def _thumbnail(ctx: AppContext, item: Mapping[str, Any]) -> Optional[ft.Control]:
    """A photo small enough to show; None when it is missing or too big."""
    if media_kind(item["name"]) != "foto" or item["size"] > MAX_PREVIEW_BYTES:
        return None
    try:
        data = media.read(ctx.folder, item["file"])
    except media.MediaError:
        return None
    image = ft.Image(src=data, width=THUMB, height=THUMB, fit=ft.BoxFit.COVER, border_radius=T.RADIUS_SMALL, cache_width=THUMB * 3)
    path = media.path_of(ctx.folder, item["file"])
    return ft.Container(image, on_click=lambda _: ctx.open_file(path), border_radius=T.RADIUS_SMALL, ink=True, tooltip=item["name"])


def _row(ctx: AppContext, item: Mapping[str, Any], on_remove: Optional[Callable[[str], Any]]) -> ft.Control:
    path = media.path_of(ctx.folder, item["file"])
    present = path.exists()
    caption = f"{media_kind(item['name'])} · {media.size_label(item['size'])}" if present else "manca su questo dispositivo: ripristina un backup"
    controls: List[ft.Control] = [
        ft.Icon(W.icon_of(KIND_ICONS[media_kind(item["name"])]), color=T.ACCENT if present else T.TEXT_DIM, size=22),
        ft.Column([W.body(item["name"]), W.caption(caption)], spacing=0, expand=True),
    ]
    if present:
        controls.append(W.text_button("Apri", lambda _: ctx.open_file(path), icon="OPEN_IN_NEW"))
    if on_remove is not None:
        controls.append(W.icon_button("DELETE_OUTLINE", lambda _: on_remove(item["file"]), "Togli"))
    return ft.Row(controls, spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER)


def attachment_list(ctx: AppContext, items: Sequence[Mapping[str, Any]], on_remove: Optional[Callable[[str], Any]] = None) -> ft.Control:
    """Photos as thumbnails, the other files one per row with «Apri»; in the form every file has a row with «Togli»."""
    thumbnails = {item["file"]: _thumbnail(ctx, item) for item in items}
    shown = [thumb for thumb in thumbnails.values() if thumb is not None]
    rows: List[ft.Control] = []
    if shown:
        rows.append(ft.Row(shown, wrap=True, spacing=8, run_spacing=8))
    rows += [_row(ctx, item, on_remove) for item in items if on_remove is not None or thumbnails[item["file"]] is None]
    return ft.Column(rows, spacing=8)
