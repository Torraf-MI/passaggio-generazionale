"""Riga di comando: legittima, imposte e confronto delle strategie di passaggio generazionale.

Esempi::

    passaggio-generazionale --demo
    passaggio-generazionale --config esempi/famiglia_bianchi.json --output output/report.html
    passaggio-generazionale --demo --veloce --grafici docs/img
"""

from __future__ import annotations

import argparse
import sys

from . import configurazione
from .analisi import analizza
from .report import _eur, _frazione, _pct, build_report, salva_grafici

NOTA_DEMO = ("Caso dimostrativo: persone, beni e valori sono di fantasia, costruiti per mostrare le situazioni tipiche "
             "del passaggio generazionale in Italia.")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="passaggio-generazionale", description=__doc__.splitlines()[0])
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--config", help="File JSON con famiglia, beni e strategie")
    src.add_argument("--demo", action="store_true", help="Usa il caso dimostrativo")
    p.add_argument("--output", default="output/report.html", help="Percorso del report HTML")
    p.add_argument("--grafici", help="Cartella dove salvare anche i grafici PNG (richiede kaleido)")
    p.add_argument("--offline", action="store_true", help="Include plotly.js nel report (funziona senza rete)")
    p.add_argument("--veloce", action="store_true", help="Salta la simulazione Monte Carlo")
    p.add_argument("--scenari", type=int, help="Numero di scenari della simulazione")
    p.add_argument("--anni", type=int, help="Anni fino alla successione (per difetto la speranza di vita)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    cfg = configurazione.esempio() if args.demo else configurazione.carica(args.config)
    if args.veloce:
        cfg.simula = False
    if args.scenari:
        cfg.simulazione.scenari = args.scenari
    if args.anni:
        cfg.anno_morte = args.anni
    a = analizza(cfg)
    path = build_report(a, args.output, data_note=NOTA_DEMO if cfg.dimostrativo else "", offline=args.offline)
    if args.grafici:
        salva_grafici(a, args.grafici)

    f = cfg.famiglia
    print(f"{f.disponente}, {f.eta:.0f} anni: patrimonio {_eur(sum(b.valore for b in cfg.beni))}")
    print("Quote senza testamento: " + ", ".join(f"{n} {_frazione(q)}" for n, q in a.ab_intestato.items()))
    print("Quote di legittima:     " + ", ".join(f"{n} {_frazione(q)}" for n, q in a.riserve.items()))
    print(f"\nConfronto con la successione tra {a.anno_morte} anni (valori a oggi)")
    rif = a.esiti[a.riferimento]
    for e in a.esiti:
        les = f"   LESIONE {_eur(e.lesione_totale)}" if e.lesione_totale > 1 else ""
        diff = _eur(e.netto_totale - rif.netto_totale)
        print(f"  {e.strategia.nome:<24} imposte e costi {_eur(e.costo_totale):>11}   netto "
              f"{_eur(e.netto_totale):>13}   vs {rif.strategia.nome}: {diff:>10}{les}")
    if a.simulazione is not None:
        s = a.simulazione.sintesi()
        print(f"\nSimulazione ({len(a.simulazione.anni)} scenari)")
        for n, r in s.iterrows():
            print(f"  {n:<24} differenza media {_eur(r['Differenza media']):>10}   "
                  f"migliore nel {_pct(r['Scenari migliori'], 0):>5}   lesione di legittima nel "
                  f"{_pct(r['Scenari con lesione'], 0):>4} degli scenari")
        print(f"\nStrategia consigliata: {a.migliore.strategia.nome}")
    print(f"\nReport salvato in {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
