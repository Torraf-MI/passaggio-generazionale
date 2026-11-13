"""Analisi completa di un caso: quote, confronto delle strategie alla speranza di vita e simulazione."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

import numpy as np
import pandas as pd

from . import normativa as nv
from .configurazione import Configurazione
from .legittima import quote_famiglia
from .patrimonio import TipoBene
from .simulazione import RisultatoSimulazione, simula, speranza_di_vita
from .strategie import Esito, confronta, tabella_confronto


@dataclass
class Analisi:
    cfg: Configurazione
    anno_morte: int
    speranza: float
    ab_intestato: dict[str, Fraction]
    riserve: dict[str, Fraction]
    esiti: list[Esito]
    simulazione: RisultatoSimulazione | None

    @property
    def riferimento(self) -> int:
        return self.cfg.indice_riferimento

    @property
    def tabella(self) -> pd.DataFrame:
        return tabella_confronto(self.esiti)

    def rischio_lesione(self, nome: str) -> float:
        """Probabilità di lesione della legittima nella simulazione (o 0/1 nello scenario atteso)."""
        if self.simulazione is not None:
            j = self.simulazione.strategie.index(nome)
            return float((self.simulazione.lesione[:, j] > 1.0).mean())
        return 0.0 if self.esito(nome).legittima.rispettata else 1.0

    @property
    def migliore(self) -> Esito:
        """La strategia con il netto più alto tra quelle con un testamento (che realizzano le volontà del
        disponente) e che rispettano la legittima in almeno il 95% degli scenari, se c'è la simulazione."""
        ok = [e for e in self.esiti if e.strategia.testamento is not None and e.legittima.rispettata
              and self.rischio_lesione(e.strategia.nome) <= 0.05]
        return max(ok or self.esiti, key=lambda e: e.netto_totale)

    def esito(self, nome: str) -> Esito:
        return next(e for e in self.esiti if e.strategia.nome == nome)

    def netti(self) -> pd.DataFrame:
        """Netto a oggi per beneficiario e strategia."""
        return pd.DataFrame({e.strategia.nome: {p: e.netto(p) for p in self.cfg.famiglia.nomi}
                             for e in self.esiti}).T

    def patrimonio(self) -> pd.DataFrame:
        """Valore di mercato e base imponibile in successione di ogni bene."""
        righe = []
        for b in self.cfg.beni:
            base = b.base_imponibile()
            nota = ""
            if b.tipo == TipoBene.IMMOBILE:
                nota = f"rendita {b.rendita:,.0f} €".replace(",", ".") + f", categoria {b.categoria}"
            elif b.tipo == TipoBene.PARTECIPAZIONE:
                nota = "patrimonio netto; esente se al coniuge o ai discendenti con il controllo"
            elif b.tipo == TipoBene.TITOLI_STATO:
                nota = "esenti dall'imposta di successione"
            elif b.tipo == TipoBene.FONDI:
                nota = f"plusvalenza latente {b.valore - b.costo_fiscale:,.0f} €".replace(",", ".")
            righe.append({"bene": b.nome, "tipo": b.tipo.descrizione, "valore": b.valore, "base": base,
                          "rapporto": base / b.valore if b.valore else 0.0, "nota": nota})
        return pd.DataFrame(righe).set_index("bene")

    def ricevuto_per_persona(self) -> pd.DataFrame:
        """Valore ricevuto da ciascuno (a oggi) per strategia e fonte."""
        righe = []
        for e in self.esiti:
            for a in e.assegnazioni:
                righe.append({"strategia": e.strategia.nome, "persona": a.persona, "fonte": a.fonte,
                              "valore": a.valore * e.sconto(a.anno)})
        return pd.DataFrame(righe).pivot_table(index=["strategia", "persona"], columns="fonte", values="valore",
                                               aggfunc="sum", fill_value=0.0)


def imposta_per_parentela(importi: np.ndarray) -> pd.DataFrame:
    """Imposta di successione su un'eredità o una donazione, per grado di parentela."""
    return pd.DataFrame({p.descrizione: [nv.imposta(x, p) for x in importi] for p in nv.Parentela
                         if p not in (nv.Parentela.DISCENDENTE, nv.Parentela.ASCENDENTE)}, index=importi)


def analizza(cfg: Configurazione) -> Analisi:
    f = cfg.famiglia
    e = speranza_di_vita(f.eta, f.sesso)
    T = cfg.anno_morte or max(1, int(round(e)))
    ab, ris = quote_famiglia(f)
    esiti = confronta(cfg.strategie, f, cfg.beni, T, parametri=cfg.parametri)
    sim = None
    if cfg.simula:
        sim = simula(cfg.strategie, f, cfg.beni, cfg.simulazione, cfg.parametri, cfg.indice_riferimento)
    return Analisi(cfg, T, e, ab, ris, esiti, sim)
