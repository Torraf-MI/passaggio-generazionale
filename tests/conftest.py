import pytest

from passaggio_generazionale import configurazione
from passaggio_generazionale.analisi import analizza


@pytest.fixture(scope="session")
def analisi_demo():
    cfg = configurazione.esempio()
    cfg.simulazione.scenari = 60
    return analizza(cfg)
