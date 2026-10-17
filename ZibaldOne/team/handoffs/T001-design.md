# T001 — Design: registro temi in `brand.py`
Scopo: aggiungere un tema = aggiungere una voce `register_theme(Theme(...))` in `core/brand.py`; nessun altro file cambia. Tutto resta in `brand.py` (D1), nessun plugin, nessun caricamento da file.

## Dataclass (in `brand.py`, dopo `Name`/`Mascot`/`Quote`, che restano invariate)
`@dataclass(frozen=True) class Theme`: `id: str` (slug minuscolo, es. "filosofia"), `label: str` (nome visibile, es. "Filosofia"), `app_name: str`, `app_tagline: str`, `app_motto: str`, `nomenclature: Mapping[str, Name]`, `mascots: Tuple[Mascot, ...]`, `quotes: Tuple[Quote, ...]`. Metodi: `mascot_for(sphere) -> Optional[Mascot]` (confronto su `sphere.lower()`, come oggi) e `quote_of_the_day(day=None) -> Quote` (stessa formula `toordinal() % len`).
Fuori dal tema: `AREAS` (struttura dati, D3), i colori di `ui/theme.py` (D4; `Mascot.color` resta campo della mascotte), i nomi fissi in `navigation.py` (es. "Museion").
Nessun codice dipende dai nomi delle mascotte (Diogy/Diggy ecc.): le chiavi sono le `sphere`.

## API
- `DEFAULT_THEME_ID = "filosofia"`; `THEME_ENV_VAR = "ZIBALDONE_THEME"`; `THEME_SETTING_KEY = "theme"`.
- `_THEMES: Dict[str, Theme]` (privato, ordine d'inserimento).
- `register_theme(theme) -> Theme`: chiama `validate_theme`, poi inserisce; `ValueError` se l'id esiste già. Restituisce il tema.
- `list_themes() -> List[Theme]`: default per primo, poi ordine di registrazione.
- `get_theme(theme_id: Optional[str]) -> Theme`: id normalizzato (`strip().lower()`); id ignoto/None/vuoto → tema default (nessuna eccezione, nessun log obbligatorio).
- `active_theme(settings: Optional[Mapping[str, Any]] = None) -> Theme`: priorità env `ZIBALDONE_THEME` > `settings.get("theme")` > default; poi `get_theme`. Funzione pura: riceve il dict già caricato (`storage/settings.load_settings`), `brand.py` non importa `storage`.

## Validazione (`validate_theme(theme)`, solleva `ValueError` con messaggio che nomina tema e problema)
1. `id` non vuoto, `[a-z0-9_-]+`; `label`, `app_name`, `app_tagline`, `app_motto` non vuoti.
2. `set(nomenclature) == set(FILOSOFIA.nomenclature)` (chiavi di `_THEMES[DEFAULT_THEME_ID]`; se il default non è ancora registrato, cioè mentre si registra lui stesso, il controllo si salta); ogni `Name` con `name`, `meaning`, `source` non vuoti.
3. Mascotte: esattamente una per ogni area di `AREAS` più una con sphere `"app"`; nessuna sphere duplicata o estranea; `name` non vuoti e unici nel tema.
4. Citazioni: almeno `MIN_QUOTES = 7` (la rotazione settimanale non si ripete), testi unici, `author` e `source` non vuoti.

## Compatibilità (comportamento identico)
I dati attuali diventano `FILOSOFIA = register_theme(Theme(id="filosofia", label="Filosofia", ...))` con gli stessi valori e lo stesso ordine. Gli alias pubblici restano a livello di modulo e puntano al default, legati all'import (come richiede `navigation.py`, che legge `NOMENCLATURE` all'import):
`APP_NAME = FILOSOFIA.app_name` (idem `APP_TAGLINE`, `APP_MOTTO`), `NOMENCLATURE = dict(FILOSOFIA.nomenclature)`, `MASCOTS = list(FILOSOFIA.mascots)`, `QUOTES = list(FILOSOFIA.quotes)`; `mascot_for(s)` e `quote_of_the_day(d)` delegano a `FILOSOFIA`. Tipi pubblici invariati (`Dict`, `List`), import di tutti i chiamanti invariati.
Nessun chiamante usa ancora `active_theme`: il collegamento della UI/CLI al tema attivo e il cambio tema a runtime sono un task futuro (richiede di non leggere `NOMENCLATURE` all'import). Futuro (T005, installer): pacchetti tema scaricabili; non ora.

## Test da scrivere (`tests/test_brand.py`, quelli esistenti restano invariati)
1. `get_theme("filosofia") is FILOSOFIA`; `get_theme("ignoto")`, `get_theme(None)`, `get_theme("")` → default; `get_theme(" Filosofia ")` → FILOSOFIA.
2. Alias: `NOMENCLATURE == FILOSOFIA.nomenclature`, `MASCOTS == list(FILOSOFIA.mascots)`, `QUOTES`, `APP_*`; `mascot_for`/`quote_of_the_day` uguali ai metodi del default.
3. `list_themes()[0].id == DEFAULT_THEME_ID`; `register_theme` con id duplicato → `ValueError`.
4. Validazione: tema copia di FILOSOFIA (`dataclasses.replace`) con chiave di nomenclatura mancante/extra, area senza mascotte, sphere duplicata, 6 citazioni, id non valido → `ValueError`; copia valida con nuovo id → registrata e restituita da `get_theme` (ripulire `_THEMES` nel teardown/fixture).
5. `active_theme`: env (monkeypatch) batte settings; `{"theme": "filosofia"}` → default; `{"theme": "ignoto"}`, `{}`, `None` → default.
