"""Regole del passaggio generazionale in Italia (2026): aliquote e franchigie, valori catastali, usufrutto.

Riferimenti: D.Lgs. 346/1990 (Testo unico sulle successioni e donazioni, TUS) come modificato dal D.Lgs. 139/2024;
D.Lgs. 347/1990 (imposte ipotecaria e catastale); D.P.R. 131/1986 (prospetto dei coefficienti per l'usufrutto);
TUIR, artt. 44, 45 e 68 (redditi finanziari).
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass
from enum import StrEnum


class Parentela(StrEnum):
    """Rapporto tra chi trasferisce e chi riceve: decide aliquota e franchigia."""

    CONIUGE = "coniuge"            # anche la parte di un'unione civile
    FIGLIO = "figlio"
    DISCENDENTE = "discendente"    # nipote figlio di un figlio, pronipote
    ASCENDENTE = "ascendente"      # genitore, nonno
    FRATELLO = "fratello"          # fratello o sorella
    PARENTE = "parente"            # altri parenti fino al 4° grado, affini in linea retta e collaterali fino al 3°
    ESTRANEO = "estraneo"          # convivente di fatto, amici, enti non esenti

    @property
    def descrizione(self) -> str:
        return DESCRIZIONI[self]


DESCRIZIONI = {
    Parentela.CONIUGE: "Coniuge o unito civilmente",
    Parentela.FIGLIO: "Figlio",
    Parentela.DISCENDENTE: "Nipote in linea retta",
    Parentela.ASCENDENTE: "Genitore",
    Parentela.FRATELLO: "Fratello o sorella",
    Parentela.PARENTE: "Altri parenti e affini",
    Parentela.ESTRANEO: "Convivente o estraneo",
}


@dataclass(frozen=True)
class Scaglione:
    aliquota: float
    franchigia: float


# art. 2, commi 48-49, D.L. 262/2006: le stesse aliquote valgono per successioni e donazioni
ALIQUOTE: dict[Parentela, Scaglione] = {
    Parentela.CONIUGE: Scaglione(0.04, 1_000_000.0),
    Parentela.FIGLIO: Scaglione(0.04, 1_000_000.0),
    Parentela.DISCENDENTE: Scaglione(0.04, 1_000_000.0),
    Parentela.ASCENDENTE: Scaglione(0.04, 1_000_000.0),
    Parentela.FRATELLO: Scaglione(0.06, 100_000.0),
    Parentela.PARENTE: Scaglione(0.06, 0.0),
    Parentela.ESTRANEO: Scaglione(0.08, 0.0),
}
FRANCHIGIA_DISABILE = 1_500_000.0           # persona con handicap grave (L. 104/1992), qualunque sia la parentela

# esenzione per aziende e partecipazioni di controllo (art. 3, comma 4-ter, TUS)
PARENTELE_ESENZIONE_AZIENDA = frozenset({Parentela.CONIUGE, Parentela.FIGLIO, Parentela.DISCENDENTE})
ANNI_VINCOLO_AZIENDA = 5

IPOTECARIA, CATASTALE = 0.02, 0.01
MINIMO_IPOCATASTALE = 200.0                 # minimo per ciascuna delle due imposte
FISSA_PRIMA_CASA = 200.0                    # ipotecaria e catastale fisse se c'è il requisito prima casa
RIVALUTAZIONE_RENDITA = 1.05
MOLTIPLICATORI = {"A": 120.0, "A/10": 60.0, "B": 140.0, "C": 120.0, "C/1": 40.8, "D": 60.0}
MOLTIPLICATORE_PRIMA_CASA = 110.0

ALIQUOTA_REDDITI = 0.26
QUOTA_IMPONIBILE_STATO = 12.5 / 26.0        # i titoli di Stato sono tassati al 12,5%: base al 48,08%

# percentuale del valore della piena proprietà attribuita all'usufrutto vitalizio, per età dell'usufruttuario.
# Il prospetto del D.P.R. 131/1986 è aggiornato ogni anno con il tasso legale in modo che il prodotto
# tasso × coefficiente resti costante: le percentuali non cambiano.
_ETA_MAX = [20, 30, 40, 45, 50, 53, 56, 60, 63, 66, 69, 72, 75, 78, 82, 86, 92, 99]
_QUOTE = [0.95, 0.90, 0.85, 0.80, 0.75, 0.70, 0.65, 0.60, 0.55, 0.50, 0.45, 0.40, 0.35, 0.30, 0.25, 0.20, 0.15,
          0.10]


def quota_usufrutto(eta: float) -> float:
    """Quota del valore attribuita all'usufrutto vitalizio di una persona di questa età."""
    i = bisect.bisect_left(_ETA_MAX, int(eta))
    return _QUOTE[min(i, len(_QUOTE) - 1)]


def quota_nuda_proprieta(eta_usufruttuario: float) -> float:
    return 1.0 - quota_usufrutto(eta_usufruttuario)


def moltiplicatore(categoria: str, prima_casa: bool = False) -> float:
    categoria = categoria.upper().replace(" ", "")
    if categoria in MOLTIPLICATORI:
        m = MOLTIPLICATORI[categoria]
    elif categoria[:1] in MOLTIPLICATORI:
        m = MOLTIPLICATORI[categoria[:1]]
    else:
        raise ValueError(f"categoria catastale sconosciuta: {categoria}")
    if prima_casa and categoria[:1] == "A" and categoria != "A/10":
        m = MOLTIPLICATORE_PRIMA_CASA
    return m


def valore_catastale(rendita: float, categoria: str, prima_casa: bool = False) -> float:
    """Valore catastale di un fabbricato: base imponibile non rettificabile dall'Agenzia (art. 34, c. 5, TUS)."""
    return rendita * RIVALUTAZIONE_RENDITA * moltiplicatore(categoria, prima_casa)


def franchigia(parentela: Parentela, disabile: bool = False) -> float:
    f = ALIQUOTE[parentela].franchigia
    return max(f, FRANCHIGIA_DISABILE) if disabile else f


def imposta(base: float, parentela: Parentela, franchigia_disponibile: float | None = None,
            disabile: bool = False) -> float:
    """Imposta di successione o donazione sulla base imponibile di un beneficiario."""
    f = franchigia(parentela, disabile) if franchigia_disponibile is None else franchigia_disponibile
    return ALIQUOTE[parentela].aliquota * max(0.0, base - f)


def ipocatastali(base: float, prima_casa: bool = False) -> float:
    """Imposte ipotecaria e catastale sul trasferimento di un immobile."""
    if base <= 0:
        return 0.0
    if prima_casa:
        return 2 * FISSA_PRIMA_CASA
    return max(IPOTECARIA * base, MINIMO_IPOCATASTALE) + max(CATASTALE * base, MINIMO_IPOCATASTALE)


def aliquota_redditi(quota_stato: float = 0.0) -> float:
    """Aliquota effettiva sui redditi finanziari: 26%, ridotta pro quota per i titoli di Stato."""
    return ALIQUOTA_REDDITI * (1.0 - quota_stato * (1.0 - QUOTA_IMPONIBILE_STATO))
