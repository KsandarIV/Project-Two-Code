"""The screens of the app. Each builder takes (AppContext, Route) and returns a control.

To add a screen: write `build(ctx, route)` in a module here, add its route to
`ui/navigation.py` (`parse_route` and `route_path`) and register it below.
"""

from typing import Callable, Dict

import flet as ft

from zibaldone.ui.context import AppContext
from zibaldone.ui.navigation import Route
from zibaldone.ui.views import areas, collections, entries, entry_form, finance, graph, habits, onboarding, people, settings, stats, template_editor, templates, today

Builder = Callable[[AppContext, Route], ft.Control]

SCREENS: Dict[str, Builder] = {
    "oggi": today.build,
    "voci": entries.build_list,
    "voce": entries.build_detail,
    "scrivi": entry_form.build_new,
    "modifica": entry_form.build_edit,
    "collezioni": collections.build,
    "modelli": templates.build_list,
    "modello": template_editor.build,
    "scuole": templates.build_packs,
    "grafo": graph.build,
    "theoria": stats.build,
    "finanze": finance.build,
    "abitudini": habits.build,
    "aree": areas.build_overview,
    "area": areas.build_area,
    "persona": people.build_person,
    "albero": people.build_tree,
    "rete": people.build_network,
    "organon": settings.build_index,
    "parte": settings.build_part,
    "consenso": onboarding.consent,
    "accesso": onboarding.sign_in,
    "copie": onboarding.copies,
    "diario": onboarding.diario,
}

# Shown full screen, without the navigation.
ONBOARDING_SCREENS = frozenset({"consenso", "accesso", "copie", "diario"})
