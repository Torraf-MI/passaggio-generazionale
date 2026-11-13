"""Caso dimostrativo: la famiglia Bianchi."""

from __future__ import annotations

from .famiglia import Famiglia, Persona
from .normativa import Parentela
from .patrimonio import Bene, TipoBene
from .strategie import Donazione, PattoDiFamiglia, Polizza, Strategia, Testamento, Trust

MARCO, LAURA, SOFIA, ELENA = "Marco", "Laura", "Sofia", "Elena"
CASA, MARE, UFFICIO = "Casa di Milano", "Casa al mare", "Ufficio in via Larga"
AZIENDA, BTP, ETF, CONTO = "Bianchi Meccanica srl (70%)", "BTP", "ETF e fondi", "Conto corrente"


def famiglia_dimostrativa() -> Famiglia:
    return Famiglia("Giorgio Bianchi", eta=74, persone=[
        Persona(MARCO, Parentela.FIGLIO, 46, note="lavora nell'azienda di famiglia"),
        Persona(LAURA, Parentela.FIGLIO, 42, note="medico, non lavora nell'azienda"),
        Persona(SOFIA, Parentela.DISCENDENTE, 12, note="figlia di Laura"),
        Persona(ELENA, Parentela.ESTRANEO, 66, prima_casa=True, note="compagna convivente da quindici anni"),
    ])


def patrimonio_dimostrativo() -> list[Bene]:
    return [
        Bene(CASA, TipoBene.IMMOBILE, 1_100_000, rendita=2_600, categoria="A/2"),
        Bene(MARE, TipoBene.IMMOBILE, 750_000, rendita=1_500, categoria="A/7"),
        Bene(UFFICIO, TipoBene.IMMOBILE, 600_000, rendita=4_200, categoria="A/10"),
        Bene(AZIENDA, TipoBene.PARTECIPAZIONE, 3_000_000, valore_fiscale=1_800_000, quota_societaria=0.70),
        Bene(BTP, TipoBene.TITOLI_STATO, 600_000),
        Bene(ETF, TipoBene.FONDI, 2_800_000, costo_fiscale=1_900_000),
        Bene(CONTO, TipoBene.LIQUIDITA, 500_000),
    ]


def testamento_base() -> Testamento:
    """Il testamento che Giorgio vorrebbe: l'azienda a Marco, gli immobili a Laura, la casa in usufrutto a Elena."""
    return Testamento(
        assegnazioni={AZIENDA: {MARCO: 1.0}, MARE: {LAURA: 1.0}, UFFICIO: {LAURA: 1.0}, CASA: {LAURA: 1.0}},
        usufrutti={CASA: ELENA},
        legati={ELENA: 400_000, SOFIA: 200_000},
        residuo={MARCO: 0.25, LAURA: 0.75},
    )


def _senza_legati(t: Testamento, **legati: float) -> Testamento:
    return Testamento(assegnazioni=dict(t.assegnazioni), usufrutti=dict(t.usufrutti), legati=legati,
                      residuo=dict(t.residuo))


def strategie_dimostrative() -> list[Strategia]:
    t = testamento_base()
    fai_da_te = Testamento(
        assegnazioni={AZIENDA: {MARCO: 1.0}, ETF: {MARCO: 1.0}, CASA: {LAURA: 1.0}, MARE: {LAURA: 1.0},
                      UFFICIO: {LAURA: 1.0}},
        usufrutti={CASA: ELENA}, residuo={LAURA: 1.0})
    btp_a_elena = Testamento(assegnazioni={**t.assegnazioni, BTP: {ELENA: 2 / 3}}, usufrutti=dict(t.usufrutti),
                             legati={SOFIA: 200_000}, residuo=dict(t.residuo))
    paritario = Testamento(usufrutti={CASA: ELENA}, legati={ELENA: 400_000, SOFIA: 200_000},
                           residuo={MARCO: 0.45, LAURA: 0.55})
    patto = PattoDiFamiglia(MARCO, AZIENDA, {LAURA: 1_000_000}, [BTP, CONTO])
    return [
        Strategia("Successione legittima", "Nessun testamento: tutto ai due figli in parti uguali, nulla a Elena "
                  "e a Sofia."),
        Strategia("Testamento fai da te", "Azienda ed ETF a Marco, immobili a Laura, usufrutto della casa a Elena.",
                  testamento=fai_da_te),
        Strategia("Testamento", "Azienda a Marco, immobili a Laura, usufrutto della casa e 400.000 € a Elena, "
                  "200.000 € a Sofia, il resto per un quarto a Marco e tre quarti a Laura.", testamento=t),
        Strategia("Donazioni in vita", "Come il testamento, ma oggi l'azienda a Marco e 1 milione di ETF a Laura.",
                  atti=[Donazione(MARCO, AZIENDA), Donazione(LAURA, ETF, importo=1_000_000)], testamento=t),
        Strategia("Nuda proprietà", "Come il testamento, ma oggi la nuda proprietà di casa al mare e ufficio "
                  "a Laura.", atti=[Donazione(LAURA, MARE, nuda_proprieta=True),
                                    Donazione(LAURA, UFFICIO, nuda_proprieta=True)], testamento=t),
        Strategia("Polizza vita", "Come il testamento, ma i 400.000 € di Elena in una polizza vita pagata con "
                  "il conto corrente.", atti=[Polizza({ELENA: 1.0}, 400_000, CONTO)],
                  testamento=_senza_legati(t, **{SOFIA: 200_000})),
        Strategia("BTP per legato", "Come il testamento, ma a Elena 400.000 € di BTP invece del denaro.",
                  testamento=btp_a_elena),
        Strategia("Trust", "Come il testamento, ma i 200.000 € di Sofia in un trust fino ai suoi 25 anni.",
                  atti=[Trust(SOFIA, 200_000, CONTO, durata=13)], testamento=_senza_legati(t, **{ELENA: 400_000})),
        Strategia("Patto di famiglia", "Oggi l'azienda a Marco con un patto di famiglia e 1 milione a Laura (BTP e "
                  "conto) come liquidazione; il resto per testamento, il 55% a Laura e il 45% a Marco, con "
                  "l'usufrutto della casa e 400.000 € a Elena e 200.000 € a Sofia.",
                  atti=[patto], testamento=paritario),
        Strategia("Piano integrato", "Il patto di famiglia, più oggi la nuda proprietà della casa al mare a Laura e "
                  "dell'ufficio a Marco; il resto per testamento come sopra.",
                  atti=[patto, Donazione(LAURA, MARE, nuda_proprieta=True),
                        Donazione(MARCO, UFFICIO, nuda_proprieta=True)], testamento=paritario),
    ]
