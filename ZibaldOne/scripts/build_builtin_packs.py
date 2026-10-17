"""Write the built-in packs into src/zibaldone/packs/ as .zbpack.json files.

The packs bring the ideas of the old Journal App (3 moments of the day,
8 life areas, collections, identity, people) as editable templates.
Run after changing this file:  py scripts/build_builtin_packs.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from zibaldone.core.packs import Pack, write_pack_file  # noqa: E402
from zibaldone.core.templates import Template  # noqa: E402

OUTPUT = ROOT / "src" / "zibaldone" / "packs"
AUTHOR = "ZibaldOne"
LICENSE = "CC0-1.0"

MOOD = {
    "key": "umore",
    "type": "choice",
    "label": "Umore",
    "options": {
        "choices": ["😄 Ottimo", "🙂 Buono", "😐 Così così", "🙁 Giù", "😣 Pessimo"],
        "values": [5, 4, 3, 2, 1],
    },
}
AREAS = ["Personale", "Salute", "Finanze", "Famiglia", "Sociale", "Lavoro", "Studio", "Svago"]


def block(key, block_type, label, required=False, help="", **options):
    data = {"key": key, "type": block_type, "label": label}
    if required:
        data["required"] = True
    if options:
        data["options"] = options
    if help:
        data["help"] = help
    return data


def scale(key, label, low=0, high=10, **labels):
    return block(key, "scale", label, min=low, max=high, **labels)


def progress(unit=""):
    return block("stato", "progress", "Stato", **({"unit": unit} if unit else {}))


def review(key, name, period, icon, description):
    return {
        "slug": key, "name": name, "category": "diario", "icon": icon, "color": "#8A2BE2",
        "description": description,
        "blocks": [
            scale("voto", f"Voto al {period}", low_label="pessimo", high_label="splendido"),
            block("momenti_belli", "longtext", "Momenti belli"),
            block("difficolta", "longtext", "Difficoltà"),
            block("imparato", "longtext", "Cosa ho imparato"),
            block("area_focus", "choice", "Area su cui concentrarmi", choices=AREAS),
            block("obiettivi", "checklist", f"Obiettivi per il prossimo {period}"),
        ],
    }


DIARIO = {
    "id": "zibaldone.diario",
    "name": "Stoa · Diario",
    "description": "Il diario come esercizio quotidiano, alla maniera degli stoici: i 3 momenti della giornata, il check-in delle 8 aree della vita, le revisioni di settimana, mese e anno, i pensieri liberi.",
    "templates": [
        {
            "slug": "mattina", "name": "Meditazione del mattino", "category": "diario", "icon": "WB_SUNNY", "color": "#FFFF00",
            "description": "Inizio giornata: cosa voglio fare oggi? Come Marco Aurelio, Meditazioni II, 1.",
            "blocks": [
                MOOD,
                scale("energia", "Energia", low_label="a terra", high_label="al massimo"),
                block("intenzione", "text", "La mia intenzione per oggi"),
                block("priorita", "checklist", "Le cose importanti di oggi", max_items=10),
                block("gratitudine", "text", "Una cosa per cui sono grato"),
            ],
        },
        {
            "slug": "meta_giornata", "name": "Meriggio", "category": "diario", "icon": "WB_TWILIGHT", "color": "#FF5500",
            "description": "Metà giornata: a che punto sono? Il grande meriggio di Nietzsche, Così parlò Zarathustra.",
            "blocks": [
                MOOD,
                scale("avanzamento", "Quanto ho fatto finora", low_label="niente", high_label="tutto"),
                block("priorita", "checklist", "Le cose importanti di oggi", max_items=10),
                block("nota", "longtext", "Come sta andando?"),
            ],
        },
        {
            "slug": "sera", "name": "Esame serale", "category": "diario", "icon": "NIGHTLIGHT", "color": "#00E5FF",
            "description": "Fine giornata: cosa ho fatto, cosa ho imparato, cosa farò domani. Seneca, De ira III, 36.",
            "blocks": [
                MOOD,
                block("fatto", "longtext", "Cosa ho fatto"),
                block("imparato", "longtext", "Cosa ho imparato"),
                block("domani", "checklist", "Da fare domani"),
                scale("voto", "Voto alla giornata", low_label="da dimenticare", high_label="perfetta"),
            ],
        },
        {
            "slug": "aree", "name": "Eudaimonia", "category": "diario", "icon": "DONUT_LARGE", "color": "#74EE15",
            "description": "Check-in delle 8 aree della vita, da 0 a 10. Aristotele, Etica Nicomachea: la vita che fiorisce.",
            "blocks": [scale(area.lower(), area) for area in AREAS] + [block("nota", "longtext", "Nota")],
        },
        {
            "slug": "riflessione", "name": "Pensiero", "category": "diario", "icon": "PSYCHOLOGY", "color": "#FF007F",
            "description": "Scrittura libera: pensieri, idee, domande. Leopardi, Zibaldone di pensieri.",
            "blocks": [
                block("titolo", "text", "Titolo", required=True),
                block("testo", "longtext", "Testo", required=True, help="puoi citare altre voci con [[Titolo]]"),
                block("etichette", "tags", "Etichette"),
                MOOD,
            ],
        },
        review("settimana", "Hypomnemata", "settimana", "VIEW_WEEK", "Revisione della settimana. I quaderni di appunti dei Greci, riletti da Foucault in La scrittura di sé (1983)."),
        review("mese", "Lettera a Lucilio", "mese", "CALENDAR_MONTH", "Revisione del mese, come una lettera a te stesso. Seneca, Lettere a Lucilio."),
        {
            "slug": "anno", "name": "Almanacco", "category": "diario", "icon": "AUTO_AWESOME", "color": "#8A2BE2",
            "description": "Revisione dell'anno: com'è andato e dove voglio andare. Leopardi, Dialogo di un venditore d'almanacchi e di un passeggere (1832).",
            "blocks": [
                block("parola", "text", "La parola dell'anno"),
                block("traguardi", "longtext", "Traguardi"),
                block("lezioni", "longtext", "Lezioni"),
                block("propositi", "checklist", "Propositi per il prossimo anno"),
            ],
        },
    ],
}


def collection(slug, name, icon, color, description, blocks):
    return {"slug": slug, "name": name, "category": "collezioni", "icon": icon, "color": color, "description": description, "blocks": blocks}


TITLE = block("titolo", "text", "Titolo", required=True)
RATING = block("voto", "rating", "Voto", max=5)
GENRES = block("generi", "tags", "Generi")
REVIEW = block("recensione", "longtext", "Recensione")

COLLEZIONI = {
    "id": "zibaldone.collezioni",
    "name": "Museion · Collezioni",
    "description": "Come il Museo di Alessandria, la casa delle Muse e dei libri: libri, film, serie, anime, videogiochi, giochi da tavolo, sport, musica e guardaroba.",
    "templates": [
        collection("libro", "Biblioteca di Babele", "MENU_BOOK", "#00E5FF", "Libri: la tua libreria e il tuo viaggio intellettuale. Borges, La biblioteca di Babele (1941).", [
            TITLE, block("autore", "text", "Autore"), progress("pagine"), block("segnalibro", "bookmark", "Segnalibro"),
            RATING, GENRES, REVIEW, block("citazioni", "longtext", "Citazioni"), block("isbn", "text", "ISBN", max_length=20),
        ]),
        collection("film", "Caverna", "MOVIE", "#FF5500", "Film visti e da vedere: ombre su una parete, come nel mito di Platone (Repubblica VII).", [
            TITLE, block("regista", "text", "Regia"), block("anno", "number", "Anno", integer=True, min=1880, max=2100),
            progress(), RATING, GENRES, REVIEW,
        ]),
        collection("serie", "Eterno ritorno", "TV", "#FF007F", "Serie TV, un episodio dopo l'altro. Nietzsche, La gaia scienza, 341.", [
            TITLE, block("piattaforma", "text", "Dove la guardo"), progress("episodi"),
            block("segnalibro", "bookmark", "Segnalibro", placeholder="S02E05"), RATING, GENRES, REVIEW,
        ]),
        collection("anime", "Anima mundi", "AUTO_AWESOME_MOTION", "#B3F3F6", "Anime e manga. L'anima del mondo di Platone, Timeo.", [
            TITLE, block("studio", "text", "Studio"), progress("episodi"), block("segnalibro", "bookmark", "Segnalibro"),
            RATING, GENRES, REVIEW,
        ]),
        collection("videogioco", "Homo ludens", "SPORTS_ESPORTS", "#74EE15", "Videogiochi, piattaforme e ore di gioco. Huizinga, Homo ludens (1938).", [
            TITLE, block("piattaforma", "text", "Piattaforma"), progress(), block("ore", "number", "Ore di gioco", min=0, unit="ore"),
            RATING, GENRES, REVIEW,
        ]),
        collection("gioco_tavolo", "Alea", "CASINO", "#FFFF00", "Giochi da tavolo, di carte e di ruolo. Caillois, I giochi e gli uomini (1958).", [
            TITLE, block("tipo", "choice", "Tipo", choices=["Gioco di ruolo", "Gioco da tavolo", "Gioco di carte", "Wargame", "Altro"]),
            block("giocatori", "text", "Giocatori"), progress(), RATING, block("note", "longtext", "Note"),
        ]),
        collection("sport", "Mens sana", "FITNESS_CENTER", "#FF0000", "Sport: allenamenti, partite e record. Giovenale, Satire X.", [
            block("attivita", "text", "Attività", required=True), block("durata", "number", "Durata", min=0, unit="min"),
            scale("intensita", "Intensità", 1, 10), block("record", "text", "Record personale"), block("note", "longtext", "Note"),
        ]),
        collection("musica", "Armonia delle sfere", "MUSIC_NOTE", "#8A2BE2", "Musica: la colonna sonora della tua vita. Dalla tradizione pitagorica.", [
            TITLE, block("artista", "text", "Artista"), block("tipo", "choice", "Tipo", choices=["Album", "Canzone", "Playlist"]),
            RATING, GENRES, block("testo", "longtext", "Testo o appunti"), block("ricordo", "longtext", "A cosa la associo"),
        ]),
        collection("capo", "Maschera", "CHECKROOM", "#00E5FF", "Guardaroba: come ti presenti al mondo. In latino persona è la maschera; Pirandello, Uno, nessuno e centomila (1926).", [
            block("nome", "text", "Nome", required=True),
            block("categoria", "choice", "Categoria", choices=["Maglia", "Camicia", "Pantaloni", "Giacca", "Scarpe", "Accessorio", "Altro"]),
            block("colori", "tags", "Colori"),
            block("stagione", "choice", "Stagione", choices=["Primavera", "Estate", "Autunno", "Inverno", "Tutto l'anno"]),
            block("stile", "tags", "Stile"), block("voto", "rating", "Quanto mi piace", max=5),
        ]),
    ],
}

IO = {
    "id": "zibaldone.io",
    "name": "Delfi · Io",
    "description": "Il secondo cervello, all'ombra del tempio di Delfi: identità, filosofia personale, capitoli di vita, desideri e abitudini.",
    "templates": [
        {
            "slug": "identita", "name": "Conosci te stesso", "category": "io", "icon": "FINGERPRINT", "color": "#FF007F",
            "description": "Chi sono, ridotto all'essenziale. Il motto del tempio di Delfi.",
            "blocks": [
                block("tratti", "tags", "I miei tratti"),
                block("punti_forza", "longtext", "Punti di forza"),
                block("crescita", "longtext", "Dove voglio crescere"),
                block("successo", "longtext", "Cos'è per me il successo"),
                block("felicita", "longtext", "Cos'è per me la felicità"),
                block("eredita", "longtext", "Cosa voglio lasciare"),
            ],
        },
        {
            "slug": "filosofia", "name": "Arché", "category": "io", "icon": "BALANCE", "color": "#8A2BE2",
            "description": "La mia filosofia: valori, principi e domande che guidano le scelte. I presocratici cercavano l'arché, il principio di tutte le cose.",
            "blocks": [
                block("valori", "tags", "Valori"),
                block("principi", "checklist", "Principi di vita"),
                block("domande", "longtext", "Le domande che mi guidano"),
                block("maestri", "tags", "Chi mi ha ispirato"),
                block("chiarezza", "longtext", "Momenti di chiarezza"),
            ],
        },
        {
            "slug": "capitolo", "name": "Confessioni", "category": "io", "icon": "AUTO_STORIES", "color": "#00E5FF",
            "description": "L'autobiografia, un capitolo di vita alla volta. Agostino, Confessioni.",
            "blocks": [
                block("titolo", "text", "Titolo", required=True),
                block("periodo", "text", "Periodo"),
                block("racconto", "longtext", "Racconto"),
                block("svolta", "longtext", "Il punto di svolta"),
            ],
        },
        {
            "slug": "desiderio", "name": "Conatus", "category": "io", "icon": "STAR", "color": "#FFFF00",
            "description": "La lista dei desideri, da sognare a realizzato. Spinoza, Etica III: il desiderio è l'essenza stessa dell'uomo.",
            "blocks": [block("desiderio", "text", "Desiderio", required=True), progress(), block("perche", "longtext", "Perché lo voglio")],
        },
        {
            "slug": "abitudine", "name": "Hexis", "category": "io", "icon": "REPEAT", "color": "#74EE15",
            "description": "Un'abitudine da costruire o da lasciare. Aristotele, Etica Nicomachea II: le virtù nascono dall'abitudine.",
            "blocks": [
                block("nome", "text", "Abitudine", required=True),
                block("frequenza", "text", "Ogni quanto"),
                progress("giorni"),
                block("note", "longtext", "Note"),
            ],
        },
    ],
}

PERSONE = {
    "id": "zibaldone.persone",
    "name": "Agorà · Persone",
    "description": "La piazza dove ci si incontra: le persone della tua vita e i momenti con loro. Niente dati sensibili come documenti o salute.",
    "templates": [
        {
            "slug": "persona", "name": "L'Altro", "category": "persone", "icon": "PERSON", "color": "#FF5500",
            "description": "Una persona della tua vita: famiglia, amici, lavoro. Levinas, Totalità e infinito (1961).",
            "blocks": [
                block("nome", "text", "Nome", required=True),
                block("soprannomi", "tags", "Soprannomi"),
                block("ruolo", "choice", "Ruolo", choices=["Famiglia", "Amico", "Collega", "Mentore", "Conoscente", "Altro"]),
                block("aree", "tags", "Aree", suggestions=[area.lower() for area in AREAS]),
                block("compleanno", "date", "Compleanno"),
                block("note", "longtext", "Note"),
            ],
        },
        {
            "slug": "incontro", "name": "Simposio", "category": "persone", "icon": "GROUPS", "color": "#FF5500",
            "description": "Un incontro, un momento passato con qualcuno. Platone, Simposio.",
            "blocks": [
                block("titolo", "text", "Titolo", required=True),
                block("con", "link", "Con chi", template="persona", multiple=True),
                block("dove", "text", "Dove"),
                block("cosa", "longtext", "Cosa è successo"),
                MOOD,
            ],
        },
    ],
}


def build(spec):
    templates = [Template.from_dict(template) for template in spec["templates"]]
    return Pack(spec["id"], spec["name"], "1.0.0", templates, AUTHOR, LICENSE, spec["description"]).validate()


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for spec in (DIARIO, COLLEZIONI, IO, PERSONE):
        path = write_pack_file(build(spec), OUTPUT / f"{spec['id'].split('.')[-1]}.zbpack.json")
        print(f"scritto {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
