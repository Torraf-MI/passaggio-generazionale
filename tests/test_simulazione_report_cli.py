import json

import numpy as np
import pytest

from passaggio_generazionale import cli, configurazione, dati
from passaggio_generazionale.analisi import imposta_per_parentela
from passaggio_generazionale.mercato import Mercato, ParametriMercato
from passaggio_generazionale.report import build_report, contesto
from passaggio_generazionale.simulazione import probabilita_morte_per_anno, speranza_di_vita


def test_speranza_di_vita_calibrata():
    assert speranza_di_vita(74, "M") == pytest.approx(12.5, abs=0.2)
    assert speranza_di_vita(74, "F") == pytest.approx(14.9, abs=0.2)
    assert speranza_di_vita(60, "M") > speranza_di_vita(80, "M")
    p = probabilita_morte_per_anno(74, "M")
    assert p.sum() == pytest.approx(1.0) and (p >= 0).all()


def test_mercato_atteso_e_scenari():
    m = Mercato.atteso(anni=10)
    assert m.crescita("azioni", 10) == pytest.approx(1.05**10)
    assert m.crescita("azioni", 10, 5) == pytest.approx(1.05**5)
    sc = Mercato.scenari(4000, 5, ParametriMercato(), np.random.default_rng(1))
    media = np.mean([s.crescita("azioni", 5) for s in sc])
    assert media == pytest.approx(1.05**5, rel=0.03)                        # media aritmetica rispettata
    assert all(s.crescita("liquidita", 5) == pytest.approx(1.015**5) for s in sc[:5])


def test_simulazione_demo(analisi_demo):
    s = analisi_demo.simulazione
    n = analisi_demo.cfg.simulazione.scenari
    assert s.netto.shape == (n, len(analisi_demo.esiti))
    sint = s.sintesi()
    assert sint.loc["Testamento", "Differenza media"] == 0
    assert sint.loc["Nuda proprietà", "Scenari migliori"] > 0.9
    assert 0.1 < sint.loc["Testamento fai da te", "Scenari con lesione"] < 1.0   # dipende dai mercati
    assert sint.loc["Piano integrato", "Scenari con lesione"] <= 0.05


def test_imposta_per_parentela():
    t = imposta_per_parentela(np.array([0.0, 1_000_000.0, 2_000_000.0]))
    assert t.loc[2_000_000.0, "Figlio"] == pytest.approx(40_000)
    assert t.loc[1_000_000.0, "Convivente o estraneo"] == pytest.approx(80_000)


def test_json_andata_e_ritorno(tmp_path):
    cfg = configurazione.esempio()
    p = tmp_path / "caso.json"
    p.write_text(json.dumps(configurazione.a_dizionario(cfg), ensure_ascii=False), encoding="utf-8")
    cfg2 = configurazione.carica(p)
    assert [s.nome for s in cfg2.strategie] == [s.nome for s in cfg.strategie]
    assert cfg2.famiglia["Elena"].prima_casa
    assert cfg2.indice_riferimento == cfg.indice_riferimento


def test_esempio_json_del_repository():
    cfg = configurazione.carica("esempi/famiglia_bianchi.json")
    assert cfg.famiglia.disponente == "Giorgio Bianchi"
    assert len(cfg.beni) == len(dati.patrimonio_dimostrativo())


def test_report_e_cli(analisi_demo, tmp_path):
    out = build_report(analisi_demo, tmp_path / "r.html", data_note="nota")
    html = out.read_text(encoding="utf-8")
    for testo in ("Passaggio generazionale", "Piano integrato", "riunione fittizia", "plotly"):
        assert testo in html
    ctx = contesto(analisi_demo)
    assert ctx["best"] == "Piano integrato"
    assert cli.main(["--demo", "--veloce", "--output", str(tmp_path / "c.html")]) == 0
    assert (tmp_path / "c.html").exists()
