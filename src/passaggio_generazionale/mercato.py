"""Crescita dei beni nel tempo: scenario atteso e scenari casuali correlati."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

FATTORI = ("immobili", "azioni", "obbligazioni", "azienda", "liquidita")


@dataclass
class ParametriMercato:
    """Rendimenti attesi di prezzo (aritmetici, annui) e volatilità per fattore. I redditi (affitti, cedole,
    dividendi) sono considerati consumati dal disponente, allo stesso modo in tutte le strategie."""

    rendimenti: dict[str, float] = field(default_factory=lambda: {
        "immobili": 0.02, "azioni": 0.05, "obbligazioni": 0.025, "azienda": 0.04, "liquidita": 0.015})
    volatilita: dict[str, float] = field(default_factory=lambda: {
        "immobili": 0.07, "azioni": 0.16, "obbligazioni": 0.05, "azienda": 0.22, "liquidita": 0.0})
    correlazioni: dict[tuple[str, str], float] = field(default_factory=lambda: {
        ("azioni", "azienda"): 0.6, ("azioni", "obbligazioni"): 0.2, ("azioni", "immobili"): 0.3,
        ("immobili", "azienda"): 0.3, ("obbligazioni", "immobili"): 0.2})

    def matrice(self) -> np.ndarray:
        c = np.eye(len(FATTORI))
        for (a, b), r in self.correlazioni.items():
            i, j = FATTORI.index(a), FATTORI.index(b)
            c[i, j] = c[j, i] = r
        return c


class Mercato:
    """Fattori di crescita annui per ciascun fattore: ``lordi[f][t]`` porta il valore dall'anno t a t+1."""

    def __init__(self, lordi: dict[str, np.ndarray]):
        self.lordi = {f: np.asarray(v, dtype=float) for f, v in lordi.items()}
        self._cum = {f: np.concatenate([[1.0], np.cumprod(v)]) for f, v in self.lordi.items()}

    @property
    def orizzonte(self) -> int:
        return len(next(iter(self.lordi.values())))

    def crescita(self, fattore: str, t1: int, t0: int = 0) -> float:
        """Moltiplicatore del valore tra l'anno t0 e l'anno t1."""
        c = self._cum[fattore]
        if t1 >= len(c):
            raise ValueError(f"orizzonte di {len(c) - 1} anni superato ({t1})")
        return float(c[t1] / c[t0])

    def annuale(self, fattore: str, t: int) -> float:
        return float(self.lordi[fattore][t])

    @classmethod
    def atteso(cls, par: ParametriMercato | None = None, anni: int = 50) -> Mercato:
        par = par or ParametriMercato()
        return cls({f: np.full(anni, 1.0 + par.rendimenti[f]) for f in FATTORI})

    @classmethod
    def scenari(cls, n: int, anni: int, par: ParametriMercato | None = None,
                rng: np.random.Generator | None = None) -> list[Mercato]:
        """Scenari lognormali correlati con la media aritmetica dei parametri."""
        par = par or ParametriMercato()
        rng = rng or np.random.default_rng(0)
        chol = np.linalg.cholesky(par.matrice())
        sig = np.array([par.volatilita[f] for f in FATTORI])
        mu = np.array([np.log1p(par.rendimenti[f]) for f in FATTORI]) - 0.5 * sig**2
        z = rng.standard_normal((n, anni, len(FATTORI))) @ chol.T
        g = np.exp(mu + sig * z)
        return [cls({f: g[k, :, i] for i, f in enumerate(FATTORI)}) for k in range(n)]
