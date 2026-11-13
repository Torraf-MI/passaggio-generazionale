"""I beni del patrimonio, con il valore di mercato, il valore fiscale e i parametri di crescita."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .normativa import valore_catastale


class TipoBene(StrEnum):
    IMMOBILE = "immobile"
    PARTECIPAZIONE = "partecipazione"      # quote di società non quotata
    TITOLI_STATO = "titoli_stato"          # BTP, BOT, CCT: esenti dall'imposta di successione
    FONDI = "fondi"                        # ETF, fondi, azioni quotate
    LIQUIDITA = "liquidita"

    @property
    def descrizione(self) -> str:
        return {"immobile": "Immobile", "partecipazione": "Partecipazione", "titoli_stato": "Titoli di Stato",
                "fondi": "ETF e fondi", "liquidita": "Liquidità"}[self.value]


FATTORE_PREDEFINITO = {
    TipoBene.IMMOBILE: "immobili",
    TipoBene.PARTECIPAZIONE: "azienda",
    TipoBene.TITOLI_STATO: "obbligazioni",
    TipoBene.FONDI: "azioni",
    TipoBene.LIQUIDITA: "liquidita",
}
FINANZIARI = frozenset({TipoBene.TITOLI_STATO, TipoBene.FONDI})


@dataclass
class Bene:
    """Un bene del patrimonio.

    ``valore`` è il valore di mercato, usato per la legittima e per la ricchezza trasferita. La base imponibile
    dell'imposta di successione è il valore catastale per gli immobili (``rendita`` e ``categoria``), il
    patrimonio netto pro quota per le partecipazioni non quotate (``valore_fiscale``) e il valore di mercato per
    il resto. ``costo_fiscale`` serve per le plusvalenze latenti dei titoli.
    """

    nome: str
    tipo: TipoBene
    valore: float
    rendita: float = 0.0
    categoria: str = "A"
    valore_fiscale: float | None = None
    quota_societaria: float = 0.0          # quota del capitale (per l'esenzione delle partecipazioni di controllo)
    costo_fiscale: float | None = None
    quota_stato: float = 0.0               # quota di titoli di Stato (aliquota sui redditi)
    fattore: str | None = None             # fattore di rischio della simulazione

    def __post_init__(self) -> None:
        self.tipo = TipoBene(self.tipo)
        if self.tipo == TipoBene.IMMOBILE and self.rendita <= 0:
            raise ValueError(f"{self.nome}: un immobile richiede la rendita catastale")
        if self.costo_fiscale is None:
            self.costo_fiscale = self.valore
        if self.tipo == TipoBene.TITOLI_STATO:
            self.quota_stato = 1.0
        if self.fattore is None:
            self.fattore = FATTORE_PREDEFINITO[self.tipo]

    @property
    def finanziario(self) -> bool:
        return self.tipo in FINANZIARI

    def base_imponibile(self, valore_mercato: float | None = None, prima_casa: bool = False) -> float:
        """Base imponibile della piena proprietà dell'intero bene, dato il valore di mercato corrente."""
        v = self.valore if valore_mercato is None else valore_mercato
        if self.tipo == TipoBene.IMMOBILE:
            return valore_catastale(self.rendita, self.categoria, prima_casa)
        if self.tipo == TipoBene.PARTECIPAZIONE:
            pn = self.valore if self.valore_fiscale is None else self.valore_fiscale
            return pn * v / self.valore            # il patrimonio netto cresce con il valore dell'azienda
        if self.tipo == TipoBene.TITOLI_STATO:
            return 0.0                             # art. 12, c. 1, lett. i), TUS (in successione)
        return v

    def base_donazione(self, valore_mercato: float | None = None, prima_casa: bool = False) -> float:
        """Base imponibile in una donazione. Per prudenza i titoli di Stato sono tassati al valore di mercato."""
        if self.tipo == TipoBene.TITOLI_STATO:
            return self.valore if valore_mercato is None else valore_mercato
        return self.base_imponibile(valore_mercato, prima_casa)


def totale(beni: list[Bene]) -> float:
    return sum(b.valore for b in beni)
