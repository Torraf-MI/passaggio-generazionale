"""Simulazione Monte Carlo: quando avverrà la successione e quanto varranno i beni.

L'anno della morte segue una legge di Gompertz, con forza di mortalità ``exp((x - M) / s) / s``, calibrata sulla
speranza di vita italiana per età e sesso (tavole ISTAT 2024: a 74 anni circa 12,5 anni per un uomo e 14,9 per
una donna). I beni crescono con scenari lognormali correlati. Ogni strategia è valutata sugli stessi scenari.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .famiglia import Famiglia
from .mercato import Mercato, ParametriMercato
from .patrimonio import Bene
from .strategie import Parametri, Strategia, esegui

# età modale e dispersione della legge di Gompertz (calibrate sulle speranze di vita ISTAT 2024)
GOMPERTZ = {"M": (86.7, 9.6), "F": (90.7, 8.4)}


def _sopravvivenza(eta: float, t: np.ndarray, sesso: str) -> np.ndarray:
    m, s = GOMPERTZ[sesso.upper()]
    return np.exp(-(np.exp((eta + t - m) / s) - np.exp((eta - m) / s)))


def speranza_di_vita(eta: float, sesso: str = "M") -> float:
    t = np.linspace(0, 70, 7001)
    return float(np.trapezoid(_sopravvivenza(eta, t, sesso), t))


def probabilita_morte_per_anno(eta: float, sesso: str = "M", anni: int = 45) -> np.ndarray:
    """Probabilità che la successione si apra nell'anno 1, 2, ... (la morte nell'anno t è contata in t)."""
    s = _sopravvivenza(eta, np.arange(anni + 1, dtype=float), sesso)
    p = s[:-1] - s[1:]
    return p / p.sum()


def anni_morte(eta: float, sesso: str, n: int, rng: np.random.Generator, anni: int = 45) -> np.ndarray:
    p = probabilita_morte_per_anno(eta, sesso, anni)
    return rng.choice(np.arange(1, anni + 1), size=n, p=p)


@dataclass
class ParametriSimulazione:
    scenari: int = 1_000
    seme: int = 7
    mercato: ParametriMercato = field(default_factory=ParametriMercato)


@dataclass
class RisultatoSimulazione:
    strategie: list[str]
    anni: np.ndarray                    # anno della morte per scenario
    netto: np.ndarray                   # scenari × strategie, netto ai beneficiari riportato a oggi
    costi: np.ndarray                   # scenari × strategie, imposte e costi riportati a oggi
    lesione: np.ndarray                 # scenari × strategie, lesione di legittima
    per_persona: dict[str, np.ndarray]  # persona -> scenari × strategie
    riferimento: int = 0

    def differenze(self, riferimento: int | None = None) -> pd.DataFrame:
        r = self.riferimento if riferimento is None else riferimento
        d = self.netto - self.netto[:, [r]]
        return pd.DataFrame(d, columns=self.strategie)

    def sintesi(self, riferimento: int | None = None) -> pd.DataFrame:
        r = self.riferimento if riferimento is None else riferimento
        d = self.differenze(r)
        out = pd.DataFrame({
            "Netto medio": self.netto.mean(axis=0),
            "Imposte e costi medi": self.costi.mean(axis=0),
            "Differenza media": d.mean().values,
            "Differenza 5° percentile": d.quantile(0.05).values,
            "Differenza 95° percentile": d.quantile(0.95).values,
            "Scenari migliori": (d > 1.0).mean().values,
            "Scenari con lesione": (self.lesione > 1.0).mean(axis=0),
            "Lesione media": [float(c[c > 1.0].mean()) if (c > 1.0).any() else 0.0
                                          for c in self.lesione.T],
        }, index=self.strategie)
        return out

    def costi_per_anno(self) -> pd.DataFrame:
        """Imposte e costi medi per anno della morte (scenari raggruppati)."""
        df = pd.DataFrame(self.costi, columns=self.strategie)
        df["anno"] = self.anni
        return df.groupby("anno").mean()


def simula(strategie: list[Strategia], famiglia: Famiglia, beni: list[Bene],
           par: ParametriSimulazione | None = None, parametri: Parametri | None = None,
           riferimento: int = 0) -> RisultatoSimulazione:
    par = par or ParametriSimulazione()
    rng = np.random.default_rng(par.seme)
    anni = anni_morte(famiglia.eta, famiglia.sesso, par.scenari, rng)
    durata = max([getattr(a, "durata", 0) for s in strategie for a in s.atti] + [int(anni.max())])
    mercati = Mercato.scenari(par.scenari, durata + 1, par.mercato, rng)
    n, k = par.scenari, len(strategie)
    netto, costi, les = np.zeros((n, k)), np.zeros((n, k)), np.zeros((n, k))
    persone = {p: np.zeros((n, k)) for p in famiglia.nomi}
    for i in range(n):
        for j, s in enumerate(strategie):
            e = esegui(s, famiglia, beni, int(anni[i]), mercati[i], parametri)
            netto[i, j] = e.netto_totale
            costi[i, j] = sum(v.importo * e.sconto(v.anno) for v in e.voci) + sum(
                a.latente * e.sconto(a.anno) for a in e.assegnazioni)
            les[i, j] = e.lesione_totale
            for p in persone:
                persone[p][i, j] = e.netto(p)
    return RisultatoSimulazione([s.nome for s in strategie], anni, netto, costi, les, persone, riferimento)
