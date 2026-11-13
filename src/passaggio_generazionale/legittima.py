"""Successione legittima (artt. 565-586 c.c.) e quote di riserva dei legittimari (artt. 536-552 c.c.).

Le quote sono frazioni esatte (``fractions.Fraction``). Non sono considerati la rappresentazione dei figli
premorti, i fratelli unilaterali e i parenti oltre i fratelli.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction as F

from .famiglia import Famiglia


def quote_ab_intestato(coniuge: str | None, figli: list[str], ascendenti: list[str] = (),
                       fratelli: list[str] = ()) -> dict[str, F]:
    """Quote dell'eredità senza testamento."""
    q: dict[str, F] = {}
    if figli:
        if coniuge is None:
            return {f: F(1, len(figli)) for f in figli}                       # art. 566
        if len(figli) == 1:
            return {coniuge: F(1, 2), figli[0]: F(1, 2)}                      # art. 581
        q[coniuge] = F(1, 3)
        q.update({f: F(2, 3) / len(figli) for f in figli})
        return q
    altri = list(ascendenti) + list(fratelli)
    if coniuge is not None:
        if not altri:
            return {coniuge: F(1)}                                             # art. 583
        q[coniuge] = F(2, 3)                                                   # art. 582
        q.update(_genitori_e_fratelli(ascendenti, fratelli, F(1, 3), minimo_genitori=F(1, 4)))
        return q
    if not altri:
        raise ValueError("nessun erede legittimo considerato: l'eredità andrebbe ad altri parenti o allo Stato")
    return _genitori_e_fratelli(ascendenti, fratelli, F(1), minimo_genitori=F(1, 2))  # artt. 568-571


def _genitori_e_fratelli(genitori: list[str], fratelli: list[str], totale: F, minimo_genitori: F) -> dict[str, F]:
    if not genitori:
        return {f: totale / len(fratelli) for f in fratelli}
    if not fratelli:
        return {g: totale / len(genitori) for g in genitori}
    n = len(genitori) + len(fratelli)
    quota_genitori = max(totale * len(genitori) / n, minimo_genitori)          # per capi, con il minimo ai genitori
    q = {g: quota_genitori / len(genitori) for g in genitori}
    q.update({f: (totale - quota_genitori) / len(fratelli) for f in fratelli})
    return q


def quote_riserva(coniuge: str | None, figli: list[str], ascendenti: list[str] = ()) -> dict[str, F]:
    """Quote di legittima. Il resto è la quota disponibile."""
    if figli:
        n = len(figli)
        if coniuge is None:
            tot = F(1, 2) if n == 1 else F(2, 3)                               # art. 537
            return {f: tot / n for f in figli}
        if n == 1:
            return {coniuge: F(1, 3), figli[0]: F(1, 3)}                      # art. 542, c. 1
        return {coniuge: F(1, 4), **{f: F(1, 2) / n for f in figli}}          # art. 542, c. 2
    if coniuge is not None:
        if ascendenti:
            return {coniuge: F(1, 2), **{a: F(1, 4) / len(ascendenti) for a in ascendenti}}  # art. 544
        return {coniuge: F(1, 2)}                                                           # art. 540
    if ascendenti:
        return {a: F(1, 3) / len(ascendenti) for a in ascendenti}                          # art. 538
    return {}


def quote_famiglia(famiglia: Famiglia) -> tuple[dict[str, F], dict[str, F]]:
    """Quote ab intestato e quote di riserva per una famiglia."""
    ab = quote_ab_intestato(famiglia.coniuge, famiglia.figli, famiglia.ascendenti, famiglia.fratelli)
    ascendenti = [] if famiglia.figli else famiglia.ascendenti
    return ab, quote_riserva(famiglia.coniuge, famiglia.figli, ascendenti)


def disponibile(riserve: dict[str, F]) -> F:
    return F(1) - sum(riserve.values(), F(0))


@dataclass
class VerificaLegittima:
    """Riunione fittizia (art. 556 c.c.) e confronto tra quanto ricevuto e quota di riserva."""

    relictum: float                         # beni lasciati alla morte, al netto dei debiti
    donatum: float                          # donazioni e liberalità in vita, valutate all'apertura
    riserve: dict[str, F]
    ricevuto: dict[str, float]              # per legittimario: beni ereditati + donazioni imputate (art. 564)
    a_non_legittimari: float                # quanto va a chi non è legittimario

    @property
    def massa(self) -> float:
        return self.relictum + self.donatum

    @property
    def quota_disponibile(self) -> float:
        return float(disponibile(self.riserve)) * self.massa

    def riserva(self, nome: str) -> float:
        return float(self.riserve.get(nome, 0)) * self.massa

    def lesione(self, nome: str) -> float:
        """Quanto manca per raggiungere la legittima: l'importo che il legittimario può chiedere in riduzione."""
        return max(0.0, self.riserva(nome) - self.ricevuto.get(nome, 0.0))

    @property
    def lesioni(self) -> dict[str, float]:
        return {n: self.lesione(n) for n in self.riserve}

    @property
    def rispettata(self) -> bool:
        return all(v < 1.0 for v in self.lesioni.values())
