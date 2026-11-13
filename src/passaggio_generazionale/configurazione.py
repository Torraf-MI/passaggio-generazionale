"""Configurazione di un caso: famiglia, patrimonio, strategie e parametri, anche da un file JSON."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import dati
from .famiglia import Famiglia, Persona
from .mercato import ParametriMercato
from .patrimonio import Bene
from .simulazione import ParametriSimulazione
from .strategie import Donazione, Parametri, PattoDiFamiglia, Polizza, Strategia, Testamento, Trust

ATTI = {"donazione": Donazione, "polizza": Polizza, "trust": Trust, "patto_di_famiglia": PattoDiFamiglia}
TIPO_ATTO = {v: k for k, v in ATTI.items()}


@dataclass
class Configurazione:
    famiglia: Famiglia
    beni: list[Bene]
    strategie: list[Strategia]
    parametri: Parametri = field(default_factory=Parametri)
    simulazione: ParametriSimulazione = field(default_factory=ParametriSimulazione)
    riferimento: str | None = None      # strategia di confronto (per difetto il primo testamento)
    anno_morte: int | None = None       # per difetto la speranza di vita
    simula: bool = True
    dimostrativo: bool = False

    @property
    def indice_riferimento(self) -> int:
        nomi = [s.nome for s in self.strategie]
        if self.riferimento:
            return nomi.index(self.riferimento)
        for i, s in enumerate(self.strategie):
            if s.testamento is not None and not s.atti:
                return i
        return 0


def esempio() -> Configurazione:
    return Configurazione(dati.famiglia_dimostrativa(), dati.patrimonio_dimostrativo(),
                          dati.strategie_dimostrative(), riferimento="Testamento", dimostrativo=True)


# ----------------------------------------------------------------------------- JSON
def _strategia(d: dict) -> Strategia:
    atti = []
    for a in d.get("atti", []):
        a = dict(a)
        atti.append(ATTI[a.pop("tipo")](**a))
    t = d.get("testamento")
    return Strategia(d["nome"], d.get("descrizione", ""), atti, Testamento(**t) if t else None)


def da_dizionario(d: dict) -> Configurazione:
    f = d["famiglia"]
    famiglia = Famiglia(f["disponente"], f["eta"], f.get("sesso", "M"), [Persona(**p) for p in f["persone"]])
    beni = [Bene(**b) for b in d["beni"]]
    sim = d.get("simulazione", {})
    merc = sim.pop("mercato", None) if isinstance(sim, dict) else None
    par_sim = ParametriSimulazione(**sim)
    if merc:
        par_sim.mercato = ParametriMercato(**{k: v for k, v in merc.items() if k != "correlazioni"})
    return Configurazione(famiglia, beni, [_strategia(s) for s in d["strategie"]],
                          Parametri(**d.get("parametri", {})), par_sim, d.get("riferimento"),
                          d.get("anno_morte"), d.get("simula", True))


def carica(percorso: str | Path) -> Configurazione:
    return da_dizionario(json.loads(Path(percorso).read_text(encoding="utf-8")))


def a_dizionario(cfg: Configurazione) -> dict:
    """Serializza una configurazione (senza i parametri di mercato, che restano quelli predefiniti)."""
    def atto(a) -> dict:
        return {"tipo": TIPO_ATTO[type(a)], **{k: v for k, v in asdict(a).items() if v is not None}}

    def bene(b: Bene) -> dict:
        d = {"nome": b.nome, "tipo": b.tipo.value, "valore": b.valore}
        for k in ("rendita", "categoria", "valore_fiscale", "quota_societaria", "costo_fiscale"):
            v = getattr(b, k)
            if k == "categoria" and b.tipo.value != "immobile":
                continue
            if v and not (k == "costo_fiscale" and v == b.valore):
                d[k] = v
        return d

    f = cfg.famiglia
    return {
        "famiglia": {"disponente": f.disponente, "eta": f.eta, "sesso": f.sesso,
                     "persone": [{**asdict(p), "parentela": p.parentela.value} for p in f.persone]},
        "beni": [bene(b) for b in cfg.beni],
        "strategie": [{"nome": s.nome, "descrizione": s.descrizione, "atti": [atto(a) for a in s.atti],
                       **({"testamento": asdict(s.testamento)} if s.testamento else {})} for s in cfg.strategie],
        "parametri": asdict(cfg.parametri),
        "simulazione": {"scenari": cfg.simulazione.scenari, "seme": cfg.simulazione.seme},
        "riferimento": cfg.riferimento,
    }
