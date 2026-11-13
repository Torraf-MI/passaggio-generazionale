"""La famiglia: chi trasferisce il patrimonio e chi lo riceve."""

from __future__ import annotations

from dataclasses import dataclass, field

from .normativa import Parentela

LEGITTIMARI = frozenset({Parentela.CONIUGE, Parentela.FIGLIO, Parentela.ASCENDENTE})


@dataclass
class Persona:
    """Un possibile beneficiario, descritto dal rapporto con chi trasferisce."""

    nome: str
    parentela: Parentela
    eta: float
    disabile: bool = False          # handicap grave (L. 104/1992): franchigia di 1,5 milioni
    prima_casa: bool = False        # ha i requisiti «prima casa»: ipotecaria e catastale fisse
    note: str = ""

    def __post_init__(self) -> None:
        self.parentela = Parentela(self.parentela)

    @property
    def legittimario(self) -> bool:
        """Coniuge, figli e (in assenza di figli) genitori hanno diritto a una quota di riserva."""
        return self.parentela in LEGITTIMARI


@dataclass
class Famiglia:
    disponente: str
    eta: float
    sesso: str = "M"
    persone: list[Persona] = field(default_factory=list)

    def __post_init__(self) -> None:
        nomi = [p.nome for p in self.persone]
        if len(set(nomi)) != len(nomi):
            raise ValueError("nomi dei beneficiari duplicati")

    def __getitem__(self, nome: str) -> Persona:
        for p in self.persone:
            if p.nome == nome:
                return p
        raise KeyError(nome)

    def per_parentela(self, *parentele: Parentela) -> list[str]:
        return [p.nome for p in self.persone if p.parentela in parentele]

    @property
    def coniuge(self) -> str | None:
        c = self.per_parentela(Parentela.CONIUGE)
        if len(c) > 1:
            raise ValueError("più di un coniuge")
        return c[0] if c else None

    @property
    def figli(self) -> list[str]:
        return self.per_parentela(Parentela.FIGLIO)

    @property
    def ascendenti(self) -> list[str]:
        return self.per_parentela(Parentela.ASCENDENTE)

    @property
    def fratelli(self) -> list[str]:
        return self.per_parentela(Parentela.FRATELLO)

    @property
    def nomi(self) -> list[str]:
        return [p.nome for p in self.persone]
