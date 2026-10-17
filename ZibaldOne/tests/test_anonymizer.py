import pytest

from zibaldone.core.anon_eval import EVAL_PEOPLE, EVAL_SENTENCES, eval_anonymizer, evaluate, parse_labeled
from zibaldone.core.anonymizer import (
    KIND_DESCRIPTIONS,
    Anonymizer,
    Finding,
    codice_fiscale_check_char,
    codice_fiscale_ok,
    iban_ok,
    luhn_ok,
    partita_iva_ok,
    people_from_entries,
    people_groups,
    resolve_overlaps,
    restore,
)
from zibaldone.core.packs import find_builtin_pack
from zibaldone.core.templates import Entry


def found(text, anonymizer=None):
    """(kind, text) of every finding, in order."""
    return [(finding.kind, finding.text) for finding in (anonymizer or Anonymizer()).find(text)]


# * — rule detectors —

def test_emails() -> None:
    text = "Scrivi a giulia.sartori+libri@example.com o a MARCO@EXAMPLE.IT."
    assert found(text) == [("EMAIL", "giulia.sartori+libri@example.com"), ("EMAIL", "MARCO@EXAMPLE.IT")]
    assert found("la chiocciola @ e un indirizzo come @marco") == []


@pytest.mark.parametrize("phone", [
    "333 1234567", "3331234567", "333-123-4567", "333.123.4567", "347 12 34 567", "333/1234567",
    "+39 347 123 4567", "+393471234567", "0039 333 765 4321", "(+39) 333 1234567", "+39-347-1234567",
    "06 1234567", "02 4851 2299", "0471/982345", "011 123 4567", "(06) 1234567", "800 123 456",
    "+44 20 7946 0958", "+1 (555) 123-4567", "0044 20 7946 0958",
])
def test_phone_formats(phone: str) -> None:
    assert found(f"Il numero è {phone}, chiamalo.") == [("TELEFONO", phone)]


@pytest.mark.parametrize("text", [
    "Oggi 10.000 passi e 345 pagine.",
    "Ho speso 1.250 euro, ordine n. 4471 del 03/05/2024.",
    "Lezione 08.30-10.30 in aula 4, poi 08.30 - 10.30 di nuovo.",
    "Il CAP è 00185.",
    "Il treno delle 18:45, nel 2026, con 3 amici e 12 euro.",
    "Il numero 12345 non basta, nemmeno 0123.",
    "IBAN sbagliato IT61 X054 2811 1010 0000 0123 456 da ricontrollare.",
])
def test_numbers_that_are_not_phones(text: str) -> None:
    assert [kind for kind, _ in found(text)] == []


def test_codice_fiscale_check_character() -> None:
    assert codice_fiscale_ok("RSSMRA85T10A562S")
    assert codice_fiscale_ok("rssmra85t10a562s")
    assert codice_fiscale_ok("RSSMRA85T10A56NH")  # omocodia: last digit of the comune code as a letter
    assert not codice_fiscale_ok("RSSMRA85T10A562T")
    assert not codice_fiscale_ok("RSSMRA85T10A562")
    assert codice_fiscale_check_char("BNCLRA92E45F205") == "F"
    with pytest.raises(ValueError, match="15 caratteri"):
        codice_fiscale_check_char("RSS")
    text = "CF RSSMRA85T10A562S, minuscolo rssmra85t10a562s, sbagliato RSSMRA85T10A562T."
    assert found(text) == [("CODICE_FISCALE", "RSSMRA85T10A562S"), ("CODICE_FISCALE", "rssmra85t10a562s")]


def test_partita_iva() -> None:
    assert partita_iva_ok("12345678903") and partita_iva_ok("IT01234567897")
    assert not partita_iva_ok("12345678901")
    assert not partita_iva_ok("00000000000")
    text = "P.IVA 12345678903, poi IT01234567897; l'ordine 12345678901 no."
    assert found(text) == [("PARTITA_IVA", "12345678903"), ("PARTITA_IVA", "IT01234567897")]


def test_iban_mod_97() -> None:
    assert iban_ok("IT60X0542811101000000123456")
    assert iban_ok("de89 3704 0044 0532 0130 00")
    assert iban_ok("GB82WEST12345698765432")
    assert not iban_ok("IT61X0542811101000000123456")
    assert not iban_ok("IT60X054281110100000012345")  # one character short for Italy
    text = "Conto IT60 X054 2811 1010 0000 0123 456 grazie, oppure DE89370400440532013000."
    assert found(text) == [("IBAN", "IT60 X054 2811 1010 0000 0123 456"), ("IBAN", "DE89370400440532013000")]
    assert found("IBAN IT61X0542811101000000123456 sbagliato") == []


def test_payment_cards_with_luhn() -> None:
    assert luhn_ok("4111111111111111") and not luhn_ok("4111111111111112")
    text = "Carte 4111 1111 1111 1111 12/27, 5555-5555-5555-4444, 3782 822463 10005 e 4012888888881881."
    assert found(text) == [
        ("CARTA", "4111 1111 1111 1111"),
        ("CARTA", "5555-5555-5555-4444"),
        ("CARTA", "3782 822463 10005"),
        ("CARTA", "4012888888881881"),
    ]
    assert found("Tessera 4111 1111 1111 1112 e zeri 0000 0000 0000 0000.") == []
    assert found("Libro ISBN 9788817101455, bellissimo.") == []  # passes Luhn, but it is an ISBN


def test_urls() -> None:
    text = "Vedi https://www.instagram.com/ale.conti.foto, (www.example.it/pagina) e github.com/marcoferri-dev."
    assert found(text) == [
        ("URL", "https://www.instagram.com/ale.conti.foto"),
        ("URL", "www.example.it/pagina"),
        ("URL", "github.com/marcoferri-dev"),
    ]
    assert found("Il link https://it.wikipedia.org/wiki/Python_(linguaggio).") == [
        ("URL", "https://it.wikipedia.org/wiki/Python_(linguaggio)")
    ]
    assert found("Ho letto su repubblica.it e uso Python 3.12.") == []


def test_ip_addresses() -> None:
    assert found("Server 192.168.1.24 e 2001:db8::8a2e:370:7334.") == [("IP", "192.168.1.24"), ("IP", "2001:db8::8a2e:370:7334")]
    assert found("Valori 999.12.4.1, versione 2.10.4, ore 12:30:45, MAC 00:1A:2B:3C:4D:5E.") == []


@pytest.mark.parametrize("address", [
    "via Roma 12", "piazza Garibaldi, 3/A", "Viale dei Mille 45", "Via XX Settembre 7b", "via Roma n. 5",
    "Corso Vittorio Emanuele II 118, 10121 Torino", "località Pian del Re", "p.zza Duomo 1", "v.le Monza 120",
    "Piazza Sant'Ambrogio", "via dell'Indipendenza 8", "vicolo del Pozzo 2 bis", "largo Augusto 3",
])
def test_street_addresses(address: str) -> None:
    assert found(f"Ci vediamo in {address}, alle otto.") == [("INDIRIZZO", address)]


def test_words_that_look_like_streets() -> None:
    assert found("Sono andato via presto, e così via. Ci siamo sentiti via Zoom e via WhatsApp.") == []
    assert found("Ho finito il corso di Python. Corso di Statistica domani. Una strada di campagna.") == []
    assert found("Un bar su corso Como, abito in corso Buenos Aires.") == [
        ("INDIRIZZO", "corso Como"), ("INDIRIZZO", "corso Buenos Aires")
    ]


def test_birth_dates_need_a_cue_and_keep_only_the_date() -> None:
    text = (
        "Nato il 12/03/1990. È nata l'8 marzo 2024. Nata a Bologna il 3 aprile 1993. "
        "Data di nascita: 1990-05-17. Compleanno: 5 giugno. Nato nel 1988. D.d.n. 3/4/88."
    )
    assert [value for kind, value in found(text) if kind == "DATA_NASCITA"] == [
        "12/03/1990", "8 marzo 2024", "3 aprile 1993", "1990-05-17", "5 giugno", "1988", "3/4/88",
    ]
    assert found("Il 12/03/1990 sono andato al mare, il 3 marzo torno.") == []


# * — names —

def test_names_on_word_boundaries_and_elisions() -> None:
    anonymizer = Anonymizer(names=["Marco", "Ale", "Marco Ferri"])
    text = "Marco Ferri, poi marco e MARCO, dall'Ale. Marconi, Marcon, Alessandria e Marco2 no."
    assert found(text, anonymizer) == [
        ("PERSONA", "Marco Ferri"), ("PERSONA", "marco"), ("PERSONA", "MARCO"), ("PERSONA", "Ale"),
    ]


def test_names_with_accents_hyphens_and_spaces() -> None:
    anonymizer = Anonymizer(names=["Nicolò", "Anna-Maria", "nonna Pina"])
    text = "Nicolò, Nicolo, Nicolo' e Anna Maria con nonna   Pina."
    assert [value for _, value in found(text, anonymizer)] == ["Nicolò", "Nicolo", "Nicolo'", "Anna Maria", "nonna   Pina"]


def test_names_that_are_common_words_need_a_capital() -> None:
    anonymizer = Anonymizer(names=["Rosa", "Vale", "Chiara", "Al"])
    text = "Rosa ha una maglia rosa; vale la pena, dice Vale; un'idea chiara di Chiara; al cinema con Al."
    assert [value for _, value in found(text, anonymizer)] == ["Rosa", "Vale", "Chiara", "Al"]


def test_name_inside_email_or_address_is_one_finding() -> None:
    anonymizer = Anonymizer(names=["Giulia", "Marco"])
    text = "Giulia scrive da giulia@example.com e abita in via Marco Polo 3."
    assert found(text, anonymizer) == [("PERSONA", "Giulia"), ("EMAIL", "giulia@example.com"), ("INDIRIZZO", "via Marco Polo 3")]


def test_dictionary_validation() -> None:
    with pytest.raises(ValueError, match="troppo corto"):
        Anonymizer(names=["M"])
    with pytest.raises(ValueError, match="lista di nomi"):
        Anonymizer(people=["Marco"])
    with pytest.raises(ValueError, match="tipo di termine"):
        Anonymizer(terms={"luogo": ["Bressanone"]})
    assert Anonymizer(names=["", "  "]).names == []


def test_custom_terms_have_their_own_kind() -> None:
    anonymizer = Anonymizer(terms={"LUOGO": ["Bressanone", "Val di Funes"]})
    result = anonymizer.anonymize("Weekend a Bressanone e in Val di Funes, poi ancora Bressanone.")
    assert result.text == "Weekend a [LUOGO_1] e in [LUOGO_2], poi ancora [LUOGO_1]."
    assert "LUOGO" in KIND_DESCRIPTIONS


def test_extra_detectors_can_be_plugged_in() -> None:
    def fake_ner(text: str):
        start = text.find("Federico")
        if start >= 0:
            yield Finding("PERSONA", start, start + len("Federico"), "Federico")

    anonymizer = Anonymizer(detectors=[fake_ner])
    assert anonymizer.anonymize("Ho conosciuto Federico, mail federico@example.com").text == (
        "Ho conosciuto [PERSONA_1], mail federico@example.com"
    )


# * — overlaps, placeholders, restore —

def test_overlaps_longest_then_earliest_then_priority() -> None:
    findings = [
        Finding("PERSONA", 0, 5, "Marco"),
        Finding("EMAIL", 0, 17, "marco@example.com"),
        Finding("URL", 20, 25, "aaaaa"),
        Finding("IP", 23, 28, "bbbbb"),
        Finding("TELEFONO", 30, 41, "01234567897"),
        Finding("PARTITA_IVA", 30, 41, "01234567897"),
    ]
    assert [(finding.kind, finding.start) for finding in resolve_overlaps(findings)] == [
        ("EMAIL", 0), ("URL", 20), ("PARTITA_IVA", 30),
    ]
    assert resolve_overlaps(reversed(findings)) == resolve_overlaps(findings)


def test_same_value_same_placeholder_across_texts() -> None:
    anonymizer = Anonymizer(names=["Marco", "Giulia"])
    first = anonymizer.anonymize("Marco ha chiamato Giulia al 333 1234567.")
    second = anonymizer.anonymize("Poi GIULIA ha richiamato Marco dal +39 333 123 4567 e dal 06 1234567.")
    assert first.text == "[PERSONA_1] ha chiamato [PERSONA_2] al [TELEFONO_1]."
    assert second.text == "Poi [PERSONA_2] ha richiamato [PERSONA_1] dal [TELEFONO_1] e dal [TELEFONO_2]."
    assert second.mapping == {"[PERSONA_2]": "Giulia", "[PERSONA_1]": "Marco", "[TELEFONO_1]": "333 1234567", "[TELEFONO_2]": "06 1234567"}
    assert anonymizer.mapping["[PERSONA_1]"] == "Marco"
    anonymizer.forget()
    assert anonymizer.anonymize("Giulia").text == "[PERSONA_1]" and anonymizer.mapping == {"[PERSONA_1]": "Giulia"}


def test_aliases_of_one_person_share_a_placeholder() -> None:
    groups = people_groups([("Marco Ferri", ["Marchino"]), ("Marco Bianchi", []), ("Giulia Sartori", ["Giuly"])])
    assert groups == [["Marco Ferri", "Marchino", "Ferri"], ["Marco Bianchi", "Bianchi"], ["Giulia Sartori", "Giuly", "Giulia", "Sartori"], ["Marco"]]
    anonymizer = Anonymizer(people=groups)
    result = anonymizer.anonymize("Marchino, cioè Marco Ferri, e Giuly. Marco chi? Bianchi.")
    assert result.text == "[PERSONA_1], cioè [PERSONA_1], e [PERSONA_2]. [PERSONA_3] chi? [PERSONA_4]."
    assert result.mapping["[PERSONA_1]"] == "Marco Ferri"
    assert result.restore("Saluta [PERSONA_1] e [PERSONA_2].") == "Saluta Marco Ferri e Giulia Sartori."


def test_restore_tolerates_what_models_do() -> None:
    mapping = {"[PERSONA_1]": "Marco", "[CODICE_FISCALE_1]": "RSSMRA85T10A562S"}
    answer = "[PERSONA_1] e ancora [PERSONA_1]; [persona_1], [ PERSONA 1 ], PERSONA_1 e CODICE_FISCALE_1. [PERSONA_2] resta."
    assert restore(answer, mapping) == "Marco e ancora Marco; Marco, Marco, Marco e RSSMRA85T10A562S. [PERSONA_2] resta."


def test_pseudo_round_trip() -> None:
    anonymizer = Anonymizer(names=["Giulia"])
    text = "Giulia (giulia@example.com, IBAN IT60X0542811101000000123456) abita in via Roma 12."
    result = anonymizer.anonymize(text)
    assert "Giulia" not in result.text and "IT60" not in result.text and "Roma" not in result.text
    assert restore(result.text, result.mapping) == text


def test_anon_mode_keeps_no_mapping() -> None:
    anonymizer = Anonymizer(names=["Marco"])
    result = anonymizer.anonymize("Marco e Marco: marco@example.com", mode="anon")
    assert result.text == "[PERSONA_1] e [PERSONA_1]: [EMAIL_1]"
    assert result.mapping == {} and anonymizer.mapping == {}
    assert [finding.kind for finding in result.findings] == ["PERSONA", "PERSONA", "EMAIL"]
    with pytest.raises(ValueError, match="anonimato"):
        result.restore("[PERSONA_1]")
    with pytest.raises(ValueError, match="modalità sconosciuta"):
        anonymizer.anonymize("Marco", mode="hash")
    with pytest.raises(ValueError, match="serve un testo"):
        anonymizer.find(None)  # type: ignore[arg-type]


def test_text_without_personal_data_is_unchanged() -> None:
    text = "Giornata tranquilla: due capitoli, una passeggiata e 10.000 passi."
    result = Anonymizer(names=["Marco"]).anonymize(text)
    assert result.text == text and result.replacements == [] and result.mapping == {}


# * — names from the user's entries —

def test_people_from_person_entries_only() -> None:
    templates = {template.slug: template for template in find_builtin_pack("persone").templates}
    persona, incontro = templates["persona"], templates["incontro"]
    pairs = [
        (Entry.new(persona, {"nome": "Marco De Luca", "soprannomi": ["Marchino", "il Delu"]}), persona),
        (Entry.new(persona, {"nome": "Giulia"}), persona),
        (Entry.new(incontro, {"titolo": "Pizza con Giulia"}), incontro),
    ]
    assert people_from_entries(pairs) == [["Marco De Luca", "marchino", "il delu", "Marco", "Luca"], ["Giulia"]]


# * — evaluation set —

def test_labeled_sentences_parse() -> None:
    text, labels = parse_labeled("Ciao [[PERSONA:Marco]], scrivi a [[EMAIL:m@example.com]].")
    assert text == "Ciao Marco, scrivi a m@example.com."
    assert [(label.kind, text[label.start:label.end]) for label in labels] == [("PERSONA", "Marco"), ("EMAIL", "m@example.com")]
    with pytest.raises(ValueError, match="malformata"):
        parse_labeled("Ciao [[PERSONA:Marco")


def test_evaluation_set_is_large_honest_and_fake() -> None:
    parsed = [parse_labeled(sentence) for sentence in EVAL_SENTENCES]
    assert len(parsed) >= 40
    assert sum(1 for _, labels in parsed if not labels) >= 15
    kinds = {label.kind for _, labels in parsed for label in labels}
    assert kinds == set(KIND_DESCRIPTIONS) - {"LUOGO", "TERMINE"}
    for _, labels in parsed:
        for label in labels:
            if label.kind == "EMAIL":
                assert label.text.lower().split("@")[1] in {"example.com", "example.org"}
            if label.kind == "IBAN":
                assert iban_ok(label.text)
    assert len(EVAL_PEOPLE) >= 5


def test_evaluation_scores() -> None:
    report = evaluate(eval_anonymizer())
    overall, relaxed = report.overall, report.overall_relaxed
    assert overall.recall >= 0.9 and overall.precision >= 0.9 and overall.f1 >= 0.9
    assert relaxed.recall >= overall.recall
    assert report.exact["PERSONA"].false_negatives >= 1  # people missing from the dictionary stay a known gap
    for kind in ("EMAIL", "IBAN", "CODICE_FISCALE", "PARTITA_IVA", "CARTA", "IP"):
        assert report.exact[kind].recall == 1.0, kind
    assert report.errors and all(case.missed or case.spurious for case in report.errors)
