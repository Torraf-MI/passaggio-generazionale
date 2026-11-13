"""Passaggio generazionale in Italia: legittima, imposte di successione e donazione, confronto tra strumenti."""

from .famiglia import Famiglia, Persona
from .legittima import quote_ab_intestato, quote_riserva
from .normativa import Parentela, imposta, quota_usufrutto, valore_catastale
from .patrimonio import Bene, TipoBene
from .strategie import Donazione, Parametri, PattoDiFamiglia, Polizza, Strategia, Testamento, Trust, confronta, esegui

__all__ = ["Famiglia", "Persona", "Parentela", "Bene", "TipoBene", "Donazione", "PattoDiFamiglia", "Polizza", "Trust",
           "Testamento", "Strategia", "Parametri", "esegui", "confronta", "imposta", "quota_usufrutto",
           "valore_catastale", "quote_ab_intestato", "quote_riserva"]
__version__ = "0.1.0"
