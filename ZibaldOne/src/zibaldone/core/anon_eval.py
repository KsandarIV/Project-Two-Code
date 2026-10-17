"""Measure the anonymizer on a small labelled Italian set (ADR-0009, `zbone anon eval`).

The sentences are synthetic diary lines with fake data only: published test IBANs
and card numbers, computed codici fiscali and partite IVA, example.com addresses.
Labels are inline, `[[KIND:text]]`. The set keeps honest hard cases on purpose:
negatives that look like data (wrong checksums, "Marconi", "via Zoom", "corso di
Python", times and amounts) and a few misses the rules cannot avoid (a person
missing from the dictionary, "nato" said of a project).

Scores are computed twice: exact (same kind and same span) and relaxed (same kind,
overlapping spans).
"""

import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from zibaldone.core.anonymizer import Anonymizer, Finding, people_groups

LABEL = re.compile(r"\[\[([A-Z_]+):(.+?)\]\]")

EVAL_PEOPLE: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("Marco Ferri", ("Marchino",)),
    ("Giulia Sartori", ("Giuly",)),
    ("Alessandra Conti", ("Ale",)),
    ("Tommaso Rinaldi", ("Tommy",)),
    ("Chiara Moretti", ()),
    ("Rosa Bellandi", ()),
    ("Valentina Greco", ("Vale",)),
    ("Giuseppina Russo", ("nonna Pina",)),
)

EVAL_SENTENCES: Tuple[str, ...] = (
    # people
    "Oggi pranzo con [[PERSONA:Marco]] in centro, mi ha raccontato del nuovo lavoro.",
    "Sono passato dall'[[PERSONA:Ale]] e poi a cena con [[PERSONA:Marchino]].",
    "stasera [[PERSONA:giulia]] e [[PERSONA:TOMMASO]] vengono a cena, scrivo di fretta.",
    "Ho incontrato [[PERSONA:Marco Ferri]] alla conferenza di data science a Milano.",
    "La professoressa [[PERSONA:Moretti]] ha apprezzato il mio progetto sul clustering.",
    "[[PERSONA:Rosa]] mi ha prestato un libro sulle serie temporali.",
    "[[PERSONA:Vale]] dice che vale la pena rifare l'esame a settembre.",
    "Il professor [[PERSONA:Russo]] parla un russo perfetto.",
    "Partita a calcetto finita 7-3, [[PERSONA:Marco]] ha segnato due gol.",
    "Al meetup ho conosciuto [[PERSONA:Federico]], lavora sui modelli linguistici.",
    "Ho visitato il museo dedicato a Marconi vicino a Bologna.",
    "Il treno per Marcon era in ritardo di 20 minuti.",
    "Ho comprato una maglia rosa e l'idea è chiara: niente più acquisti per un mese.",
    "Vale la pena iscriversi al corso avanzato?",
    "[[PERSONA:Marco]], [[PERSONA:Giulia]] e [[PERSONA:Ale]] sono venuti a vedere la partita.",
    "Ho prestato i ferri da stiro a [[PERSONA:Marchino]].",
    "Rosa e azzurro sono i colori della cameretta.",
    "La dottoressa [[PERSONA:Bassani]] mi ha prescritto gli esami del sangue.",
    "Siamo stati ad Alessandria con [[PERSONA:Giuliano]], il fratello di [[PERSONA:Giulia]].",
    # email, phones
    "Ho scritto a [[PERSONA:Giulia]] all'indirizzo [[EMAIL:giulia.sartori@example.com]] per restituirle il libro.",
    "[[PERSONA:Giuly]] mi ha mandato il suo numero, [[TELEFONO:3471234567]], e l'email [[EMAIL:giuly.s@example.org]].",
    "Il numero nuovo di [[PERSONA:Tommy]] è [[TELEFONO:+39 347 123 4567]], salvato in rubrica.",
    "Chiamare il dentista allo [[TELEFONO:02 4851 2299]] entro venerdì.",
    "Ho ritrovato il vecchio numero di casa dei nonni: [[TELEFONO:0471/982345]].",
    "Mamma ha cambiato cellulare, ora è [[TELEFONO:333-987-6543]].",
    "Il referente del progetto a Londra risponde al [[TELEFONO:+44 20 7946 0958]] solo la mattina.",
    "Ho prenotato la cena per [[PERSONA:Marchino]], telefono del ristorante [[TELEFONO:+39 06 6982 1234]].",
    "Mio cugino ha chiamato dall'estero dal [[TELEFONO:0039 333 765 4321]].",
    "Il dottore ha detto di richiamare lo [[TELEFONO:011 123 4567]] dopo le analisi.",
    "Il numero verde della banca è [[TELEFONO:800 123 456]], aperto anche il sabato.",
    "Oggi 10.000 passi, 2 litri d'acqua e 345 pagine di statistica.",
    "Ho speso 1.250 euro per il portatile, ordine n. 4471 del 03/05/2024.",
    "Lezione 08.30-10.30 in aula 4, poi pausa caffè.",
    "Il pacco arriva al CAP 00185, che è la zona vicino alla stazione.",
    "Il suo cell:[[TELEFONO:3331234567]], quello del lavoro è [[TELEFONO:347 12 34 567]].",
    "Ho chiamato [[PERSONA:Tommy]] al [[TELEFONO:333 1234567]] alle 18:00 e poi [[PERSONA:Vale]].",
    "Scrivere a [[EMAIL:MARCO.FERRI@EXAMPLE.COM]] per il preventivo del trasloco.",
    "Il volo AZ 0610 parte alle 7, codice sconto ABCD1234.",
    # bank, cards, tax codes
    "Per il rimborso ho girato l'IBAN [[IBAN:IT60X0542811101000000123456]] all'amministrazione.",
    "L'affitto va su [[IBAN:IT60 X054 2811 1010 0000 0123 456]], ricordarsi la causale.",
    "Il collega di Berlino mi ha dato il suo conto, [[IBAN:DE89 3704 0044 0532 0130 00]], per dividere le spese.",
    "Nella mail c'era un IBAN strano, IT61X0542811101000000123456: secondo me ha sbagliato una cifra.",
    "Ho pagato il corso online con la carta [[CARTA:4111 1111 1111 1111]] e poi l'ho bloccata per sicurezza.",
    "Nuova carta arrivata: [[CARTA:5555-5555-5555-4444]], scadenza 09/27.",
    "Sull'estratto conto compare la [[CARTA:3782 822463 10005]] che non uso da anni.",
    "Il numero della tessera fedeltà è 4111 1111 1111 1112, punti quasi finiti.",
    "Finalmente in Comune hanno corretto il mio codice fiscale: [[CODICE_FISCALE:BNCLRA92E45F205F]].",
    "In segreteria l'avevano scritto tutto minuscolo, [[CODICE_FISCALE:rssmra85t10a562s]], e il modulo veniva rifiutato.",
    "Il codice fiscale di [[PERSONA:Tommaso]] è omocodico, [[CODICE_FISCALE:RSSMRA85T10A56NH]], per questo il CAF faceva storie.",
    "Sul vecchio tesserino c'era RSSMRA85T10A562T, ma l'ultima lettera è sbagliata.",
    "Fattura della libreria salvata, partita IVA [[PARTITA_IVA:12345678903]].",
    "Per il lavoro da freelance ho aperto la P.IVA [[PARTITA_IVA:IT01234567897]] con il regime forfettario.",
    "Il numero d'ordine 12345678901 non è ancora arrivato.",
    "Il codice di prenotazione è AB12CD34, la sala è la numero 3.",
    "Ho registrato la carta [[CARTA:4012888888881881]] sull'app della palestra.",
    "Ho finito il libro con ISBN 9788817101455, da consigliare a tutti.",
    # web
    "Ho salvato il profilo di [[PERSONA:Ale]] su [[URL:https://www.instagram.com/ale.conti.foto]] per vedere le foto del viaggio.",
    "[[PERSONA:Tommaso]] ha aperto un blog, [[URL:www.tommasoviaggia.it]], e mi ha chiesto un parere.",
    "Il portfolio di [[PERSONA:Marco]] è online su [[URL:github.com/marcoferri-dev]].",
    "Ho mandato a [[PERSONA:Marco]] il link [[URL:https://example.com/foto?album=estate-2026]] con le foto.",
    "Il Raspberry di casa risponde su [[IP:192.168.1.24]], l'ho configurato stasera.",
    "Nel log c'erano accessi da [[IP:2001:db8::8a2e:370:7334]] che non riconosco.",
    "Ho aggiornato la libreria alla 2.10.4 e il valore 999.12.4.1 nel file era un errore di battitura.",
    "La password del Wi-Fi è cambiata, ora la chiede a tutti.",
    "Il pannello del router è su [[URL:http://10.0.0.5:8080/admin]], la password è sul post-it.",
    "Ho letto la guida su [[URL:https://example.org/blog]]. Molto utile.",
    "Uso Python 3.12.1 e pandas 2.2 per il progetto.",
    # addresses
    "Ci vediamo da [[PERSONA:Giulia]] in [[INDIRIZZO:via Roma 12]] alle otto.",
    "Il nuovo studio del dottore è in [[INDIRIZZO:piazza Garibaldi, 3/A]], secondo piano.",
    "Abbiamo firmato il contratto per [[INDIRIZZO:Viale dei Mille 45]], trasloco a fine mese.",
    "Indirizzo per il pacco: [[INDIRIZZO:Corso Vittorio Emanuele II 118, 10121 Torino]].",
    "La casa al mare di [[PERSONA:nonna Pina]] è in [[INDIRIZZO:località Pian del Re]], niente segnale.",
    "La nuova casa di [[PERSONA:Giulia Sartori]] è in [[INDIRIZZO:Via XX Settembre 7b]], vicino al fiume.",
    "Abito ancora in [[INDIRIZZO:corso Buenos Aires 23]], ma cerco casa altrove.",
    "Sono andato via presto dalla festa perché ero stanco, e così via.",
    "Ci siamo sentiti via Zoom e poi ci siamo scritti via WhatsApp.",
    "Ho finito il corso di Python e domani inizio il corso di Statistica Bayesiana.",
    "Aperitivo in [[INDIRIZZO:p.zza Duomo 1]], poi cena in [[INDIRIZZO:v.le Monza 120]].",
    "C'è un bar carino su [[INDIRIZZO:corso Como]], ci torno con [[PERSONA:Giuly]].",
    "Sono passato da [[INDIRIZZO:via Verdi]], al numero 8, ma non c'era nessuno.",
    # birth dates
    "[[PERSONA:Tommaso]] è nato il [[DATA_NASCITA:12/03/1990]], quindi è dei Pesci.",
    "La mia nipotina è nata l'[[DATA_NASCITA:8 marzo 2024]] alle 6 del mattino.",
    "Sul modulo della palestra: data di nascita [[DATA_NASCITA:17.05.1990]].",
    "[[PERSONA:Ale]] è nata a Bologna il [[DATA_NASCITA:3 aprile 1993]], lo stesso giorno di sua cugina.",
    "[[PERSONA:Chiara]] compie gli anni il [[DATA_NASCITA:5 giugno]], devo segnarmelo.",
    "Mio fratello è nato nel [[DATA_NASCITA:1988]], due anni prima di me.",
    "Il progetto è nato il 3 marzo da un'idea di [[PERSONA:Marco]].",
    # nothing personal
    "Giornata tranquilla, ho letto due capitoli e fatto una passeggiata al parco.",
    "Mi sento più sereno dopo la meditazione di stamattina.",
    "Riunione alle 9:30 sul modello di regressione, poi pranzo veloce.",
    "Ho dormito 7 ore e 45 minuti, umore 8 su 10.",
    "Domani provo a finire il notebook sulla regressione logistica.",
)


# * — scores —

@dataclass
class Score:
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0

    @property
    def precision(self) -> Optional[float]:
        predicted = self.true_positives + self.false_positives
        return self.true_positives / predicted if predicted else None

    @property
    def recall(self) -> Optional[float]:
        expected = self.true_positives + self.false_negatives
        return self.true_positives / expected if expected else None

    @property
    def f1(self) -> Optional[float]:
        precision, recall = self.precision, self.recall
        if precision is None or recall is None or precision + recall == 0:
            return None
        return 2 * precision * recall / (precision + recall)

    def add(self, other: "Score") -> None:
        self.true_positives += other.true_positives
        self.false_positives += other.false_positives
        self.false_negatives += other.false_negatives


@dataclass
class CaseResult:
    """One sentence: what the labels say and what the anonymizer found (exact matching)."""

    text: str
    expected: List[Finding]
    predicted: List[Finding]

    @property
    def missed(self) -> List[Finding]:
        found = {(finding.kind, finding.start, finding.end) for finding in self.predicted}
        return [finding for finding in self.expected if (finding.kind, finding.start, finding.end) not in found]

    @property
    def spurious(self) -> List[Finding]:
        wanted = {(finding.kind, finding.start, finding.end) for finding in self.expected}
        return [finding for finding in self.predicted if (finding.kind, finding.start, finding.end) not in wanted]


@dataclass
class EvalReport:
    exact: Dict[str, Score] = field(default_factory=dict)
    relaxed: Dict[str, Score] = field(default_factory=dict)
    cases: List[CaseResult] = field(default_factory=list)

    @property
    def kinds(self) -> List[str]:
        return sorted(set(self.exact) | set(self.relaxed))

    @property
    def overall(self) -> Score:
        return _total(self.exact.values())

    @property
    def overall_relaxed(self) -> Score:
        return _total(self.relaxed.values())

    @property
    def errors(self) -> List[CaseResult]:
        return [case for case in self.cases if case.missed or case.spurious]


def _total(scores: Iterable[Score]) -> Score:
    total = Score()
    for score in scores:
        total.add(score)
    return total


# * — evaluation —

def parse_labeled(sentence: str) -> Tuple[str, List[Finding]]:
    """'Ciao [[PERSONA:Marco]]' -> ('Ciao Marco', [Finding('PERSONA', 5, 10, 'Marco')])."""
    pieces: List[str] = []
    findings: List[Finding] = []
    cursor = length = 0
    for match in LABEL.finditer(sentence):
        before = sentence[cursor:match.start()]
        pieces.append(before)
        length += len(before)
        value = match.group(2)
        findings.append(Finding(kind=match.group(1), start=length, end=length + len(value), text=value))
        pieces.append(value)
        length += len(value)
        cursor = match.end()
    rest = sentence[cursor:]
    if "[[" in rest or "]]" in rest:
        raise ValueError(f"etichetta malformata in: {sentence}")
    pieces.append(rest)
    return "".join(pieces), findings


def eval_anonymizer() -> Anonymizer:
    """The anonymizer with the dictionary of the evaluation set."""
    return Anonymizer(people=people_groups(EVAL_PEOPLE))


def _score_exact(expected: List[Finding], predicted: List[Finding], scores: Dict[str, Score]) -> None:
    wanted = {(finding.kind, finding.start, finding.end) for finding in expected}
    found = {(finding.kind, finding.start, finding.end) for finding in predicted}
    for kind, _, _ in wanted & found:
        scores.setdefault(kind, Score()).true_positives += 1
    for kind, _, _ in found - wanted:
        scores.setdefault(kind, Score()).false_positives += 1
    for kind, _, _ in wanted - found:
        scores.setdefault(kind, Score()).false_negatives += 1


def _score_relaxed(expected: List[Finding], predicted: List[Finding], scores: Dict[str, Score]) -> None:
    unmatched = list(predicted)
    for gold in expected:
        match = next(
            (finding for finding in unmatched if finding.kind == gold.kind and finding.start < gold.end and gold.start < finding.end),
            None,
        )
        score = scores.setdefault(gold.kind, Score())
        if match is None:
            score.false_negatives += 1
        else:
            score.true_positives += 1
            unmatched.remove(match)
    for finding in unmatched:
        scores.setdefault(finding.kind, Score()).false_positives += 1


def evaluate(anonymizer: Optional[Anonymizer] = None, sentences: Sequence[str] = EVAL_SENTENCES) -> EvalReport:
    """Precision, recall and F1 per kind and overall, exact and relaxed."""
    anonymizer = anonymizer or eval_anonymizer()
    report = EvalReport()
    for sentence in sentences:
        text, expected = parse_labeled(sentence)
        predicted = anonymizer.find(text)
        _score_exact(expected, predicted, report.exact)
        _score_relaxed(expected, predicted, report.relaxed)
        report.cases.append(CaseResult(text=text, expected=expected, predicted=predicted))
    return report
