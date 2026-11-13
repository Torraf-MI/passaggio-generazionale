"""Uso come libreria: quote, imposte e confronto di due strategie per una famiglia semplice."""

from passaggio_generazionale import (
    Bene,
    Donazione,
    Famiglia,
    Parentela,
    Persona,
    Polizza,
    Strategia,
    Testamento,
    TipoBene,
    confronta,
    imposta,
    quote_ab_intestato,
    quote_riserva,
)
from passaggio_generazionale.strategie import tabella_confronto

# quote del codice civile
print("Senza testamento:", quote_ab_intestato("Anna", ["Marco", "Laura"]))
print("Legittima:       ", quote_riserva("Anna", ["Marco", "Laura"]))

# la stessa somma, un'imposta diversa per parentela
for p in (Parentela.FIGLIO, Parentela.FRATELLO, Parentela.ESTRANEO):
    print(f"1,2 milioni a {p.descrizione.lower()}: imposta {imposta(1_200_000, p):,.0f} €")

famiglia = Famiglia("Giorgio", 74, persone=[
    Persona("Marco", Parentela.FIGLIO, 46),
    Persona("Elena", Parentela.ESTRANEO, 66, prima_casa=True),
])
beni = [
    Bene("Casa", TipoBene.IMMOBILE, 900_000, rendita=2_000, categoria="A/2"),
    Bene("BTP", TipoBene.TITOLI_STATO, 400_000),
    Bene("ETF", TipoBene.FONDI, 1_500_000, costo_fiscale=1_000_000),
    Bene("Conto", TipoBene.LIQUIDITA, 600_000),
]
testamento = Testamento(usufrutti={"Casa": "Elena"}, legati={"Elena": 400_000}, residuo={"Marco": 1.0})
btp = Testamento(assegnazioni={"BTP": {"Elena": 1.0}}, usufrutti={"Casa": "Elena"}, residuo={"Marco": 1.0})
strategie = [
    Strategia("Testamento", testamento=testamento),
    Strategia("BTP a Elena", testamento=btp),
    Strategia("Polizza per Elena", atti=[Polizza({"Elena": 1.0}, 400_000, "Conto")],
              testamento=Testamento(usufrutti={"Casa": "Elena"}, residuo={"Marco": 1.0})),
    Strategia("Donazione a Marco", atti=[Donazione("Marco", "Conto", importo=500_000)], testamento=testamento),
]
esiti = confronta(strategie, famiglia, beni, anno_morte=12)
print(tabella_confronto(esiti)[["Totale imposte e costi", "Netto ai beneficiari", "Lesione di legittima"]].round(0))
for e in esiti:
    print(f"{e.strategia.nome:<24} Elena riceve {e.netto('Elena'):>10,.0f} € netti (valore di oggi)")
