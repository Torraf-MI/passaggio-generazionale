import numpy as np
import pytest

from passaggio_generazionale import dati
from passaggio_generazionale.famiglia import Famiglia, Persona
from passaggio_generazionale.mercato import FATTORI, Mercato
from passaggio_generazionale.normativa import Parentela
from passaggio_generazionale.patrimonio import Bene, TipoBene
from passaggio_generazionale.strategie import (
    Donazione,
    Parametri,
    PattoDiFamiglia,
    Polizza,
    Strategia,
    Testamento,
    Trust,
    esegui,
)

PIATTO = Mercato({f: np.ones(40) for f in FATTORI})
ZERO = Parametri(tasso_sconto=0.0, costo_atto_donazione=0.0, costo_successione=0.0)


def famiglia():
    return Famiglia("Nonno", 74, persone=[
        Persona("Figlio", Parentela.FIGLIO, 45),
        Persona("Amica", Parentela.ESTRANEO, 60),
        Persona("Nipote", Parentela.DISCENDENTE, 10),
    ])


def imposte(e, voce):
    return sum(v.importo for v in e.voci if v.voce == voce)


def corri(beni, strategia, anni=1, mercato=PIATTO):
    return esegui(strategia, famiglia(), beni, anni, mercato, ZERO)


def test_successione_con_franchigia():
    e = corri([Bene("Conto", TipoBene.LIQUIDITA, 2_000_000)], Strategia("legittima"))
    assert imposte(e, "Imposta di successione") == pytest.approx(40_000)        # 4% oltre 1 milione
    assert e.netto("Figlio") == pytest.approx(1_960_000)
    assert e.legittima.rispettata


def test_doppia_franchigia_donazione_e_successione():
    beni = [Bene("Conto", TipoBene.LIQUIDITA, 2_000_000)]
    e = corri(beni, Strategia("dona", atti=[Donazione("Figlio", "Conto", importo=1_000_000)]))
    assert imposte(e, "Imposta di donazione") == 0
    assert imposte(e, "Imposta di successione") == 0                             # nessun cumulo dal 2025
    assert e.netto("Figlio") == pytest.approx(2_000_000)


def test_cumulo_tra_donazioni_allo_stesso_beneficiario():
    beni = [Bene("Conto", TipoBene.LIQUIDITA, 2_000_000)]
    atti = [Donazione("Figlio", "Conto", importo=800_000), Donazione("Figlio", "Conto", importo=800_000)]
    e = corri(beni, Strategia("due donazioni", atti=atti))
    assert imposte(e, "Imposta di donazione") == pytest.approx(0.04 * 600_000)


def test_titoli_di_stato_esenti_anche_per_un_estraneo():
    beni = [Bene("BTP", TipoBene.TITOLI_STATO, 500_000), Bene("Conto", TipoBene.LIQUIDITA, 500_000)]
    a_btp = Testamento(assegnazioni={"BTP": {"Amica": 1.0}}, residuo={"Figlio": 1.0})
    a_conto = Testamento(assegnazioni={"Conto": {"Amica": 1.0}}, residuo={"Figlio": 1.0})
    e1, e2 = corri(beni, Strategia("btp", testamento=a_btp)), corri(beni, Strategia("conto", testamento=a_conto))
    assert e1.netto("Amica") == pytest.approx(500_000)
    assert e2.netto("Amica") == pytest.approx(500_000 * 0.92)


def test_polizza_esente_tassato_solo_il_rendimento():
    beni = [Bene("Conto", TipoBene.LIQUIDITA, 1_000_000)]
    m = Mercato({f: np.full(40, 1.10) for f in FATTORI})
    s = Strategia("polizza", atti=[Polizza({"Amica": 1.0}, 500_000, "Conto", costi_annui=0.0)],
                  testamento=Testamento(residuo={"Figlio": 1.0}))
    e = corri(beni, s, anni=1, mercato=m)
    pol = [a for a in e.assegnazioni if a.fonte == "polizza"][0]
    assert pol.valore == pytest.approx(550_000)
    assert sum(v.importo for v in e.voci if v.persona == "Amica" and v.voce == "Imposta di successione") == 0
    assert e.netto("Amica") == pytest.approx(550_000 - 0.26 * 50_000)
    assert e.legittima.donatum == pytest.approx(500_000)                       # nella legittima contano i premi


def test_vendere_titoli_per_il_premio_tassa_la_plusvalenza():
    beni = [Bene("ETF", TipoBene.FONDI, 1_000_000, costo_fiscale=600_000), Bene("Conto", TipoBene.LIQUIDITA, 100_000)]
    e = corri(beni, Strategia("p", atti=[Polizza({"Amica": 1.0}, 500_000, "ETF", costi_annui=0.0)],
                              testamento=Testamento(residuo={"Figlio": 1.0})))
    assert imposte(e, "Imposte sui redditi") == pytest.approx(0.26 * 200_000)


def test_nuda_proprieta_a_74_anni_vale_il_65_percento():
    beni = [Bene("Casa", TipoBene.IMMOBILE, 500_000, rendita=1_000, categoria="A/2"),
            Bene("Conto", TipoBene.LIQUIDITA, 50_000)]
    e = corri(beni, Strategia("np", atti=[Donazione("Amica", "Casa", nuda_proprieta=True)],
                              testamento=Testamento(residuo={"Figlio": 1.0})))
    base = 126_000 * 0.65
    assert e.righe[0]["base"] == pytest.approx(base)
    assert imposte(e, "Imposta di donazione") == pytest.approx(0.08 * base)
    assert imposte(e, "Ipotecaria e catastale") == pytest.approx(0.03 * base)
    casa = [a for a in e.assegnazioni if a.bene == "Casa"]
    assert len(casa) == 1 and casa[0].valore == pytest.approx(500_000)          # alla morte la piena proprietà
    assert casa[0].legittima == pytest.approx(500_000)


def test_partecipazione_di_controllo_esente_solo_in_famiglia():
    az = Bene("Srl", TipoBene.PARTECIPAZIONE, 3_000_000, valore_fiscale=2_000_000, quota_societaria=0.7)
    conto = Bene("Conto", TipoBene.LIQUIDITA, 10_000)
    e1 = corri([az, conto], Strategia("figlio", testamento=Testamento(residuo={"Figlio": 1.0})))
    assert imposte(e1, "Imposta di successione") == 0
    e2 = corri([az, conto], Strategia("amica", testamento=Testamento(assegnazioni={"Srl": {"Amica": 1.0}},
                                                                     residuo={"Figlio": 1.0})))
    assert imposte(e2, "Imposta di successione") == pytest.approx(0.08 * 2_000_000)
    e3 = corri([az, conto], Strategia("metà", testamento=Testamento(assegnazioni={"Srl": {"Figlio": 0.5,
                                                                                         "Nipote": 0.5}},
                                                                    residuo={"Figlio": 1.0})))
    assert imposte(e3, "Imposta di successione") == 0                            # indivisa con rappresentante comune


def test_titoli_donati_perdono_l_aggiornamento_del_costo():
    beni = [Bene("ETF", TipoBene.FONDI, 1_000_000, costo_fiscale=600_000), Bene("Conto", TipoBene.LIQUIDITA, 10_000)]
    e1 = corri(beni, Strategia("eredita"))
    e2 = corri(beni, Strategia("dona", atti=[Donazione("Figlio", "ETF")]))
    assert sum(a.latente for a in e1.assegnazioni) == 0
    assert sum(a.latente for a in e2.assegnazioni) == pytest.approx(0.26 * 400_000)


def test_legato_di_usufrutto_divide_la_base():
    beni = [Bene("Casa", TipoBene.IMMOBILE, 600_000, rendita=1_000, categoria="A/2"),
            Bene("Conto", TipoBene.LIQUIDITA, 10_000)]
    t = Testamento(usufrutti={"Casa": "Amica"}, residuo={"Figlio": 1.0})
    e = corri(beni, Strategia("usufrutto", testamento=t))                       # Amica avrà 61 anni: 55%
    usu = [a for a in e.assegnazioni if a.diritto == "usufrutto"][0]
    assert usu.base == pytest.approx(126_000 * 0.55)
    assert usu.valore == pytest.approx(600_000 * 0.55)
    nuda = [a for a in e.assegnazioni if a.diritto == "nuda"][0]
    assert nuda.base == pytest.approx(126_000 * 0.45)


def test_legati_in_denaro():
    beni = [Bene("Conto", TipoBene.LIQUIDITA, 1_000_000)]
    e = corri(beni, Strategia("legato", testamento=Testamento(legati={"Amica": 100_000}, residuo={"Figlio": 1.0})))
    assert e.netto("Amica") == pytest.approx(92_000)
    assert e.netto("Figlio") == pytest.approx(900_000)
    with pytest.raises(ValueError):
        corri(beni, Strategia("troppo", testamento=Testamento(legati={"Amica": 2e6}, residuo={"Figlio": 1.0})))


def test_trust_tassazione_in_entrata_e_in_uscita():
    beni = [Bene("Conto", TipoBene.LIQUIDITA, 1_000_000)]
    m = Mercato({f: np.full(40, 1.05) for f in FATTORI})
    t = Testamento(residuo={"Figlio": 1.0})
    entrata = Trust("Amica", 200_000, "Conto", durata=5, costo_istituzione=0, costo_annuo=0, minimo_annuo=0)
    uscita = Trust("Amica", 200_000, "Conto", durata=5, entrata=False, costo_istituzione=0, costo_annuo=0,
                   minimo_annuo=0)
    e1 = corri(beni, Strategia("in", atti=[entrata], testamento=t), mercato=m)
    e2 = corri(beni, Strategia("out", atti=[uscita], testamento=t), mercato=m)
    assert imposte(e1, "Imposta di donazione") == pytest.approx(16_000)
    assert imposte(e2, "Imposta di donazione") == pytest.approx(0.08 * 200_000 * 1.05**5)


def test_errori_di_configurazione():
    beni = [Bene("Conto", TipoBene.LIQUIDITA, 100_000)]
    with pytest.raises(ValueError):
        corri(beni, Strategia("x", testamento=Testamento(residuo={"Figlio": 0.5})))
    with pytest.raises(ValueError):
        corri(beni, Strategia("x", atti=[Donazione("Figlio", "Conto", importo=200_000)]))
    with pytest.raises(ValueError):
        corri(beni, Strategia("x"), anni=0)


def test_caso_dimostrativo(analisi_demo):
    a = analisi_demo
    fai = a.esito("Testamento fai da te")
    assert fai.legittima.lesione(dati.LAURA) > 500_000                         # Laura può chiedere la riduzione
    assert a.esito("Testamento").legittima.rispettata
    assert a.migliore.strategia.nome == "Piano integrato"
    assert a.rischio_lesione("Piano integrato") <= 0.05 < a.rischio_lesione("Testamento")
    leg = a.esito("Successione legittima")
    assert leg.netto(dati.ELENA) == 0 and leg.netto(dati.SOFIA) == 0           # senza testamento nulla a Elena
    assert a.esito("BTP per legato").netto(dati.ELENA) > a.esito("Testamento").netto(dati.ELENA)
    don = a.esito("Donazioni in vita").costi()
    assert don["Imposte latenti sui titoli donati"] > 100_000
    for e in a.esiti:                                                           # massa = eredità + liberalità
        if not any(x.fonte == "patto di famiglia" for x in e.assegnazioni):
            assert e.legittima.massa > sum(b.valore for b in a.cfg.beni)
    patto = a.esito("Patto di famiglia")                                        # l'azienda esce dalla massa
    assert patto.legittima.massa < a.esito("Testamento").legittima.massa - 3_000_000


def test_patto_di_famiglia():
    az = Bene("Srl", TipoBene.PARTECIPAZIONE, 3_000_000, valore_fiscale=2_000_000, quota_societaria=0.7)
    fam = Famiglia("Padre", 70, persone=[Persona("A", Parentela.FIGLIO, 40), Persona("B", Parentela.FIGLIO, 38)])
    beni = [az, Bene("Conto", TipoBene.LIQUIDITA, 1_500_000)]
    s = Strategia("patto", atti=[PattoDiFamiglia("A", "Srl", {"B": 1_000_000}, ["Conto"], costo_atto=0)],
                  testamento=Testamento(residuo={"A": 0.5, "B": 0.5}))
    e = esegui(s, fam, beni, 1, PIATTO, ZERO)
    assert imposte(e, "Imposta di donazione") == 0                               # esente + franchigia di B
    assert e.legittima.massa == pytest.approx(500_000)                            # azienda e liquidazione fuori
    assert e.legittima.rispettata
    assert e.netto("A") == pytest.approx(3_250_000)
    with pytest.raises(ValueError):
        esegui(Strategia("x", atti=[PattoDiFamiglia("A", "Srl", {"B": 2_000_000}, ["Conto"])],
                         testamento=Testamento(residuo={"A": 1.0})), fam, beni, 1, PIATTO, ZERO)
