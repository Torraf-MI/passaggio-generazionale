import pytest

from passaggio_generazionale import normativa as nv
from passaggio_generazionale.normativa import Parentela


@pytest.mark.parametrize("eta,quota", [(18, 0.95), (20, 0.95), (21, 0.90), (45, 0.80), (66, 0.50), (70, 0.40),
                                       (74, 0.35), (75, 0.35), (76, 0.30), (92, 0.15), (99, 0.10), (104, 0.10)])
def test_usufrutto_per_eta(eta, quota):
    assert nv.quota_usufrutto(eta) == pytest.approx(quota)
    assert nv.quota_nuda_proprieta(eta) == pytest.approx(1 - quota)


def test_valore_catastale():
    assert nv.valore_catastale(1_000, "A/2") == pytest.approx(126_000)
    assert nv.valore_catastale(1_000, "A/2", prima_casa=True) == pytest.approx(115_500)
    assert nv.valore_catastale(1_000, "A/10", prima_casa=True) == pytest.approx(63_000)   # niente prima casa
    assert nv.valore_catastale(1_000, "C/1") == pytest.approx(42_840)
    assert nv.valore_catastale(1_000, "C/6") == pytest.approx(126_000)
    with pytest.raises(ValueError):
        nv.valore_catastale(1_000, "Z")


def test_aliquote_e_franchigie():
    assert nv.imposta(1_500_000, Parentela.FIGLIO) == pytest.approx(20_000)
    assert nv.imposta(900_000, Parentela.CONIUGE) == 0
    assert nv.imposta(150_000, Parentela.FRATELLO) == pytest.approx(3_000)
    assert nv.imposta(100_000, Parentela.PARENTE) == pytest.approx(6_000)
    assert nv.imposta(100_000, Parentela.ESTRANEO) == pytest.approx(8_000)
    assert nv.imposta(1_400_000, Parentela.FIGLIO, disabile=True) == 0
    assert nv.imposta(1_600_000, Parentela.ESTRANEO, disabile=True) == pytest.approx(8_000)


def test_ipotecaria_e_catastale():
    assert nv.ipocatastali(100_000) == pytest.approx(3_000)
    assert nv.ipocatastali(5_000) == pytest.approx(400)                     # minimi di 200 € ciascuna
    assert nv.ipocatastali(500_000, prima_casa=True) == pytest.approx(400)
    assert nv.ipocatastali(0) == 0


def test_aliquota_redditi():
    assert nv.aliquota_redditi() == pytest.approx(0.26)
    assert nv.aliquota_redditi(1.0) == pytest.approx(0.125)
    assert nv.aliquota_redditi(0.5) == pytest.approx(0.1925)
