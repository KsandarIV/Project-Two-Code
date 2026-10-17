"""Small building blocks shared by every view, in the ZibaldOne look."""

from typing import Any, Callable, List, Optional, Sequence

import flet as ft

from zibaldone.core.brand import Mascot
from zibaldone.ui import theme as T

Handler = Optional[Callable[..., Any]]


def fade(color: str, opacity: float) -> str:
    return ft.Colors.with_opacity(opacity, color)


def icon_of(name: str, fallback: str = "ARTICLE_OUTLINED") -> Any:
    """A Flet icon from its name ('WB_SUNNY'); `fallback` when the name is unknown."""
    try:
        found = getattr(ft.Icons, name) if name else None
    except Exception:
        found = None
    return found if found is not None else getattr(ft.Icons, fallback)


def build_theme() -> ft.Theme:
    scheme = ft.ColorScheme(
        primary=T.ACCENT,
        on_primary=T.BG,
        primary_container="#003A42",
        on_primary_container=T.TEXT,
        secondary=T.ACCENT_2,
        on_secondary=T.BG,
        secondary_container="#00363D",
        on_secondary_container=T.TEXT,
        tertiary=T.ACCENT_2,
        on_tertiary=T.BG,
        error=T.ERROR,
        on_error=T.BG,
        surface=T.PANEL,
        on_surface=T.TEXT,
        on_surface_variant=T.TEXT_DIM,
        outline=T.BORDER,
        outline_variant=T.BORDER,
        surface_container_lowest=T.BG,
        surface_container_low=T.PANEL,
        surface_container=T.PANEL,
        surface_container_high=T.PANEL_HIGH,
        surface_container_highest=T.PANEL_HIGH,
        inverse_surface=T.TEXT,
        on_inverse_surface=T.BG,
        inverse_primary="#006874",
        shadow="#000000",
        scrim="#000000",
        surface_tint=T.PANEL,
    )
    radius = ft.RoundedRectangleBorder(radius=T.RADIUS)
    return ft.Theme(
        color_scheme=scheme,
        use_material3=True,
        scaffold_bgcolor=T.BG,
        canvas_color=T.PANEL,
        card_bgcolor=T.PANEL,
        divider_color=T.BORDER,
        hint_color=T.TEXT_DIM,
        navigation_bar_theme=ft.NavigationBarTheme(
            bgcolor=T.PANEL,
            indicator_color=fade(T.ACCENT, 0.18),
            label_text_style=ft.TextStyle(size=11, color=T.TEXT),
            elevation=0,
        ),
        navigation_rail_theme=ft.NavigationRailTheme(
            bgcolor=T.PANEL,
            indicator_color=fade(T.ACCENT, 0.18),
            selected_label_text_style=ft.TextStyle(size=12, color=T.ACCENT, weight=ft.FontWeight.W_600),
            unselected_label_text_style=ft.TextStyle(size=12, color=T.TEXT_DIM),
        ),
        snackbar_theme=ft.SnackBarTheme(
            bgcolor=T.PANEL_HIGH,
            content_text_style=ft.TextStyle(color=T.TEXT, size=14),
            action_text_color=T.ACCENT,
            behavior=ft.SnackBarBehavior.FLOATING,
            shape=radius,
        ),
        dialog_theme=ft.DialogTheme(
            bgcolor=T.PANEL,
            shape=radius,
            title_text_style=ft.TextStyle(size=20, weight=ft.FontWeight.W_600, color=T.TEXT),
            content_text_style=ft.TextStyle(size=14, color=T.TEXT),
        ),
        chip_theme=ft.ChipTheme(
            bgcolor=T.PANEL,
            selected_color=fade(T.ACCENT, 0.22),
            label_text_style=ft.TextStyle(color=T.TEXT, size=14),
            border_side=ft.BorderSide(1, T.BORDER),
            check_color=T.ACCENT,
            shape=ft.RoundedRectangleBorder(radius=T.RADIUS_SMALL),
        ),
        progress_indicator_theme=ft.ProgressIndicatorTheme(color=T.ACCENT, linear_track_color=T.BORDER),
        divider_theme=ft.DividerTheme(color=T.BORDER, thickness=1, space=1),
    )


# * — text —


def h1(text: str) -> ft.Text:
    return ft.Text(text, size=26, weight=ft.FontWeight.W_700, color=T.TEXT)


def h2(text: str, color: str = T.TEXT) -> ft.Text:
    return ft.Text(text, size=18, weight=ft.FontWeight.W_600, color=color)


def body(text: str, dim: bool = False, size: int = 14, selectable: bool = False, italic: bool = False, **kwargs: Any) -> ft.Text:
    return ft.Text(text, size=size, color=T.TEXT_DIM if dim else T.TEXT, selectable=selectable, italic=italic, **kwargs)


def caption(text: str, color: str = T.TEXT_DIM) -> ft.Text:
    return ft.Text(text, size=12, color=color)


def section_label(text: str, nickname: str = "") -> ft.Control:
    spans = [ft.TextSpan(text.upper(), style=ft.TextStyle(size=12, letter_spacing=1.2, weight=ft.FontWeight.W_600, color=T.TEXT_DIM))]
    if nickname:
        spans.append(ft.TextSpan(f"  ·  {nickname}", style=ft.TextStyle(size=12, italic=True, color=T.ACCENT)))
    return ft.Container(ft.Text(spans=spans), padding=ft.Padding.only(top=8, left=2))


def title_with_nickname(title: str, nickname: str = "", size: int = 26) -> ft.Text:
    spans = [ft.TextSpan(title, style=ft.TextStyle(size=size, weight=ft.FontWeight.W_700, color=T.TEXT))]
    if nickname:
        spans.append(ft.TextSpan(f"  ·  {nickname}", style=ft.TextStyle(size=round(size * 0.68), italic=True, color=T.ACCENT)))
    return ft.Text(spans=spans)


# * — containers —


def panel(
    content: ft.Control,
    padding: Any = T.PAD,
    on_click: Handler = None,
    border_color: str = T.BORDER,
    bgcolor: str = T.PANEL,
    expand: Any = None,
    width: Optional[float] = None,
    col: Any = None,
    margin: Any = None,
) -> ft.Container:
    kwargs: dict = {}
    if col is not None:
        kwargs["col"] = col
    return ft.Container(
        content=content,
        padding=padding,
        bgcolor=bgcolor,
        border=ft.Border.all(1, border_color),
        border_radius=T.RADIUS,
        on_click=on_click,
        ink=on_click is not None,
        expand=expand,
        width=width,
        margin=margin,
        **kwargs,
    )


def screen(controls: Sequence[ft.Control], wide: bool) -> ft.Control:
    """A scrolling page whose content stays centred and not too wide on desktop."""
    inner = ft.Column(list(controls), spacing=14, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
    side = 28 if wide else 16
    holder = ft.Container(inner, padding=ft.Padding.only(left=side, right=side, top=20 if wide else 12, bottom=40), col=T.CONTENT_COLUMNS)
    return ft.Column(
        [ft.ResponsiveRow([holder], alignment=ft.MainAxisAlignment.CENTER)],
        scroll=ft.ScrollMode.AUTO,
        expand=True,
        spacing=0,
    )


def screen_header(
    title: str,
    nickname: str = "",
    subtitle: str = "",
    on_back: Handler = None,
    actions: Sequence[ft.Control] = (),
) -> ft.Control:
    texts: List[ft.Control] = [title_with_nickname(title, nickname)]
    if subtitle:
        texts.append(body(subtitle, dim=True))
    head: List[ft.Control] = []
    if on_back is not None:
        head.append(ft.IconButton(icon=ft.Icons.ARROW_BACK, icon_color=T.TEXT, tooltip="Indietro", on_click=on_back))
    head.append(ft.Column(texts, spacing=2, expand=True))
    rows: List[ft.Control] = [ft.Row(head, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=4)]
    if actions:
        rows.append(ft.Row(list(actions), wrap=True, spacing=8, run_spacing=8))
    return ft.Column(rows, spacing=10)


def divider() -> ft.Divider:
    return ft.Divider(height=1, thickness=1, color=T.BORDER)


def empty_state(text: str, icon: str = "LIGHTBULB_OUTLINE", action: Optional[ft.Control] = None) -> ft.Control:
    items: List[ft.Control] = [ft.Icon(icon_of(icon), color=T.TEXT_DIM, size=28), body(text, dim=True, text_align=ft.TextAlign.CENTER)]
    if action is not None:
        items.append(action)
    return panel(
        ft.Column(items, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
        padding=24,
    )


# * — buttons —


def _shape() -> ft.RoundedRectangleBorder:
    return ft.RoundedRectangleBorder(radius=T.RADIUS_SMALL)


def primary_button(text: str, on_click: Handler = None, icon: str = "", disabled: bool = False, color: str = T.ACCENT) -> ft.FilledButton:
    return ft.FilledButton(
        content=text,
        icon=icon_of(icon) if icon else None,
        on_click=on_click,
        disabled=disabled,
        style=ft.ButtonStyle(
            bgcolor={ft.ControlState.DEFAULT: color, ft.ControlState.DISABLED: fade(color, 0.22)},
            color={ft.ControlState.DEFAULT: T.readable_on(color), ft.ControlState.DISABLED: T.TEXT_DIM},
            shape=_shape(),
            padding=ft.Padding.symmetric(horizontal=18, vertical=12),
        ),
    )


def secondary_button(text: str, on_click: Handler = None, icon: str = "", disabled: bool = False) -> ft.OutlinedButton:
    return ft.OutlinedButton(
        content=text,
        icon=icon_of(icon) if icon else None,
        on_click=on_click,
        disabled=disabled,
        style=ft.ButtonStyle(
            color=T.TEXT,
            icon_color=T.ACCENT,
            side=ft.BorderSide(1, T.BORDER),
            shape=_shape(),
            padding=ft.Padding.symmetric(horizontal=16, vertical=12),
        ),
    )


def text_button(text: str, on_click: Handler = None, icon: str = "", color: str = T.ACCENT) -> ft.TextButton:
    return ft.TextButton(content=text, icon=icon_of(icon) if icon else None, on_click=on_click, style=ft.ButtonStyle(color=color, shape=_shape()))


def danger_button(text: str, on_click: Handler = None, icon: str = "") -> ft.FilledButton:
    return primary_button(text, on_click, icon, color=T.ERROR)


def icon_button(icon: str, on_click: Handler = None, tooltip: str = "", color: str = T.TEXT_DIM, size: int = 20, disabled: bool = False) -> ft.IconButton:
    return ft.IconButton(icon=icon_of(icon), icon_color=color, icon_size=size, tooltip=tooltip or None, on_click=on_click, disabled=disabled)


# * — small pieces —


def pill(text: str, color: str = T.TEXT_DIM, icon: str = "") -> ft.Container:
    content: ft.Control = ft.Text(text, size=12, color=T.TEXT)
    if icon:
        content = ft.Row([ft.Icon(icon_of(icon), size=14, color=color), content], spacing=4, tight=True)
    return ft.Container(
        content,
        padding=ft.Padding.symmetric(horizontal=10, vertical=4),
        border_radius=999,
        bgcolor=fade(color, 0.16),
        border=ft.Border.all(1, fade(color, 0.45)),
    )


def template_badge(icon: str, color: str, size: int = 40) -> ft.Container:
    return ft.Container(
        ft.Icon(icon_of(icon), color=color, size=round(size * 0.55)),
        width=size,
        height=size,
        alignment=ft.Alignment.CENTER,
        bgcolor=fade(color, 0.14),
        border_radius=T.RADIUS_SMALL,
    )


def mascot_avatar(mascot: Optional[Mascot], size: int = 34) -> ft.Control:
    if mascot is None:
        return ft.Container(width=size, height=size)
    return ft.Container(
        ft.Text(mascot.name[0], size=round(size * 0.45), weight=ft.FontWeight.W_700, color=T.readable_on(mascot.color)),
        width=size,
        height=size,
        alignment=ft.Alignment.CENTER,
        bgcolor=mascot.color,
        border_radius=size,
        tooltip=f"{mascot.name}, {mascot.animal}",
    )


def stars(value: Optional[float], maximum: int, size: int = 18, on_pick: Optional[Callable[[int], Any]] = None) -> ft.Row:
    """A row of stars (a half point shows a half star); with `on_pick`, each star is a button."""
    items: List[ft.Control] = []
    for number in range(1, maximum + 1):
        filled = value is not None and number <= value
        halved = value is not None and not filled and number - 0.5 <= value
        name = ft.Icons.STAR if filled else (ft.Icons.STAR_HALF if halved else ft.Icons.STAR_BORDER)
        color = T.ACCENT_2 if filled or halved else T.TEXT_DIM
        if on_pick is None:
            items.append(ft.Icon(name, color=color, size=size))
        else:
            items.append(
                ft.IconButton(
                    icon=name,
                    icon_color=color,
                    icon_size=size,
                    tooltip=f"{number} su {maximum}",
                    on_click=lambda _, number=number: on_pick(number),
                    style=ft.ButtonStyle(padding=ft.Padding.all(4)),
                )
            )
    return ft.Row(items, spacing=0, tight=True, wrap=True)


def meter(fraction: Optional[float], color: str = T.ACCENT, height: int = 6) -> ft.ProgressBar:
    """A determinate bar; an unknown value shows an empty track, never an animation."""
    return ft.ProgressBar(
        value=max(0.0, min(1.0, fraction or 0.0)),
        color=color,
        bgcolor=T.BORDER,
        bar_height=height,
        border_radius=height,
        track_gap=0,
        stop_indicator_radius=0,
    )


def labelled_meter(label: str, fraction: Optional[float], right: str = "", color: str = T.ACCENT) -> ft.Control:
    return ft.Column(
        [
            ft.Row([body(label, size=13), caption(right)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            meter(fraction, color),
        ],
        spacing=6,
    )


def info_row(label: str, value: str, selectable: bool = False) -> ft.Control:
    return ft.Column([caption(label), body(value, selectable=selectable)], spacing=2)


def error_text(message: str = "") -> ft.Text:
    return ft.Text(message, size=12, color=T.ERROR, visible=bool(message))


def coming_soon(text: str) -> ft.Control:
    return panel(
        ft.Row(
            [ft.Icon(ft.Icons.HOURGLASS_EMPTY, color=T.ACCENT_2, size=20), ft.Column([body("In arrivo", size=15), body(text, dim=True)], spacing=2, expand=True)],
            spacing=12,
        ),
        border_color=fade(T.ACCENT_2, 0.35),
    )


def upcoming_card(title: str, teaser: str, when: str, color: str = T.ACCENT_2, col: Any = None) -> ft.Control:
    """A feature announced before it exists (0.2.0): name, what it will do, when it arrives."""
    return panel(
        ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.AUTO_AWESOME, color=color, size=20),
                        ft.Text(title, size=15, weight=ft.FontWeight.W_600, color=T.TEXT, expand=True),
                    ],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                body(teaser, dim=True, size=13),
                ft.Row([pill(f"In arrivo · {when}", color, icon="HOURGLASS_EMPTY")], wrap=True),
            ],
            spacing=8,
        ),
        border_color=fade(color, 0.35),
        col=col,
    )


def input_border() -> dict:
    """Rounded outline: quiet border at rest, accent when focused."""
    return {
        ft.ControlState.DEFAULT: ft.OutlineInputBorder(side=ft.BorderSide(1, T.BORDER), border_radius=T.RADIUS_SMALL),
        ft.ControlState.FOCUSED: ft.OutlineInputBorder(side=ft.BorderSide(1.5, T.ACCENT), border_radius=T.RADIUS_SMALL),
        ft.ControlState.ERROR: ft.OutlineInputBorder(side=ft.BorderSide(1, T.ERROR), border_radius=T.RADIUS_SMALL),
    }


def text_input(value: str = "", **kwargs: Any) -> ft.TextField:
    """A text field in the app style; any TextField argument can be passed."""
    style: dict = dict(
        border=input_border(),
        cursor_color=T.ACCENT,
        text_size=15,
        filled=True,
        fill_color=T.BG,
        color=T.TEXT,
        label_style=ft.TextStyle(color=T.TEXT_DIM),
        hint_style=ft.TextStyle(color=T.TEXT_DIM),
        content_padding=ft.Padding.symmetric(horizontal=14, vertical=12),
    )
    style.update(kwargs)
    return ft.TextField(value=value, **style)


def wide(control: ft.Control) -> ft.Row:
    """Full width for a field: a TextField alone in a Column stays narrow."""
    control.expand = True
    return ft.Row([control])


def dropdown(options: Sequence[tuple], value: Optional[str] = None, **kwargs: Any) -> ft.Dropdown:
    """`options` are (key, text) pairs."""
    style: dict = dict(
        border=input_border(),
        filled=True,
        fill_color=T.BG,
        text_size=15,
        label_style=ft.TextStyle(color=T.TEXT_DIM),
    )
    style.update(kwargs)
    return ft.Dropdown(options=[ft.DropdownOption(key=key, text=text) for key, text in options], value=value, **style)


def tag_chip(text: str, on_remove: Handler = None, color: str = T.ACCENT) -> ft.Container:
    items: List[ft.Control] = [ft.Text(text, size=13, color=T.TEXT)]
    if on_remove is not None:
        items.append(
            ft.Container(
                ft.Icon(ft.Icons.CLOSE, size=14, color=T.TEXT_DIM),
                on_click=on_remove,
                tooltip="Togli",
                padding=2,
                border_radius=10,
            )
        )
    return ft.Container(
        ft.Row(items, spacing=4, tight=True),
        padding=ft.Padding.only(left=10, right=6 if on_remove else 10, top=4, bottom=4),
        border_radius=999,
        bgcolor=fade(color, 0.14),
        border=ft.Border.all(1, fade(color, 0.4)),
    )


def suggestion_chip(text: str, on_click: Handler) -> ft.Container:
    return ft.Container(
        ft.Row([ft.Icon(ft.Icons.ADD, size=14, color=T.ACCENT), ft.Text(text, size=13, color=T.TEXT_DIM)], spacing=2, tight=True),
        padding=ft.Padding.only(left=6, right=10, top=4, bottom=4),
        border_radius=999,
        border=ft.Border.all(1, T.BORDER),
        on_click=on_click,
        ink=True,
    )


def entry_tile(title: str, meta: str, summary: str, icon: str, color: str, on_click: Handler) -> ft.Container:
    texts: List[ft.Control] = [
        ft.Text(title, size=15, weight=ft.FontWeight.W_600, color=T.TEXT, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
        caption(meta),
    ]
    if summary:
        texts.append(ft.Text(summary, size=13, color=T.TEXT_DIM, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS))
    return panel(
        ft.Row(
            [
                template_badge(icon, color),
                ft.Column(texts, spacing=2, expand=True),
                ft.Icon(ft.Icons.CHEVRON_RIGHT, color=T.TEXT_DIM, size=20),
            ],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding.symmetric(horizontal=14, vertical=12),
        on_click=on_click,
    )
