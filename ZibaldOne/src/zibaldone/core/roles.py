"""Roles of people and the life areas they belong to (0.2.1).

A person's "legame" (the `ruolo` choice of the Persona template: Famiglia,
Amico, Collega …) and its roles (the `ruoli` tags: madre, capo, medico …)
put the person in an area by themselves. Roles not listed here are the user's
own: they are kept as they are and give no area (the `aree` tags do).
"""

from typing import Dict, List, Optional, Tuple

from zibaldone.core.templates import Entry, Template

BOND_BLOCK = "ruolo"
ROLES_BLOCK = "ruoli"

# The broad bond (one per person) and its area.
BOND_AREAS: Dict[str, str] = {
    "famiglia": "famiglia",
    "amico": "sociale",
    "amica": "sociale",
    "collega": "lavoro",
    "mentore": "studio",
    "conoscente": "sociale",
}

# Base roles, by area, in the order the form suggests them.
ROLE_GROUPS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("famiglia", (
        "madre", "padre", "genitore", "fratello", "sorella", "partner", "marito", "moglie", "figlio", "figlia",
        "nonno", "nonna", "zio", "zia", "cugino", "cugina", "nipote", "suocero", "suocera", "cognato", "cognata",
    )),
    ("sociale", ("amico", "amica", "migliore amico", "migliore amica", "vicino di casa", "vicina di casa", "conoscente")),
    ("lavoro", ("collega", "capo", "responsabile", "cliente", "fornitore", "socio", "socia", "collaboratore", "collaboratrice")),
    ("studio", ("professore", "professoressa", "insegnante", "tutor", "mentore", "compagno di corso", "compagna di corso")),
    ("salute", ("medico", "dentista", "psicologo", "psicologa", "fisioterapista", "allenatore", "allenatrice")),
    ("finanze", ("commercialista", "consulente finanziario", "consulente finanziaria", "assicuratore")),
    ("svago", ("compagno di squadra", "compagna di squadra", "compagno di giochi", "compagna di giochi")),
)

ROLE_AREAS: Dict[str, str] = {role: area for area, roles in ROLE_GROUPS for role in roles}

# What the form suggests: the most common role of each kind first.
SUGGESTED_ROLES: List[str] = [
    "madre", "padre", "fratello", "sorella", "partner", "figlio", "figlia", "nonno", "nonna", "cugino", "cugina",
    "amico", "amica", "migliore amico", "migliore amica", "vicino di casa",
    "collega", "capo", "cliente", "socio",
    "professore", "compagno di corso", "mentore",
    "medico", "allenatore", "commercialista", "compagno di squadra",
]


def _key(text: str) -> str:
    return " ".join(str(text).strip().lower().split())


def role_area(role: str) -> Optional[str]:
    """The area of a base role or bond ('Madre' -> 'famiglia'); None for the user's own roles."""
    key = _key(role)
    return ROLE_AREAS.get(key) or BOND_AREAS.get(key)


def bond_of(entry: Entry, template: Optional[Template]) -> str:
    """The person's broad bond ('Famiglia', 'Amico' …), '' when not set."""
    if template is None:
        return ""
    for spec in template.blocks:
        if spec.key == BOND_BLOCK and spec.type == "choice":
            value = entry.values.get(spec.key)
            return value if isinstance(value, str) else ""
    return ""


def roles_of(entry: Entry, template: Optional[Template]) -> List[str]:
    """The person's specific roles (base and custom), as written."""
    if template is None:
        return []
    for spec in template.blocks:
        if spec.key == ROLES_BLOCK and spec.type == "tags":
            return [role for role in entry.values.get(spec.key, []) if isinstance(role, str)]
    return []


def role_areas(entry: Entry, template: Optional[Template]) -> List[str]:
    """Areas given by the bond and the roles, in that order, without repeats."""
    found: List[str] = []
    for text in [bond_of(entry, template), *roles_of(entry, template)]:
        area = role_area(text) if text else None
        if area and area not in found:
            found.append(area)
    return found
