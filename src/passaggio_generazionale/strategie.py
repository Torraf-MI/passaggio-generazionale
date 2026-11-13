"""Strumenti del passaggio generazionale e motore che ne calcola gli effetti.

Una strategia è un insieme di atti compiuti oggi (donazioni anche di nuda proprietà, polizze vita, trust) più le
regole per i beni che restano alla morte (testamento o successione legittima). Il motore porta tutti i beni
all'anno della morte con uno scenario di mercato e calcola per ogni beneficiario:

* il valore di mercato ricevuto;
* l'imposta di donazione oggi (con il cumulo delle donazioni precedenti, art. 57 TUS) e l'imposta di successione
  alla morte (con la franchigia intera: dal 2025 le donazioni non si sommano più all'eredità);
* le imposte ipotecaria e catastale sugli immobili;
* le imposte sui redditi: sulla vendita dei titoli per pagare il premio di una polizza, sul rendimento della
  polizza alla morte, e quelle latenti sui titoli donati, che conservano il costo fiscale del donante mentre
  quelli ereditati lo aggiornano al valore di successione (art. 68, c. 6, TUIR);
* i costi: atti notarili, costi della polizza, trustee;
* la verifica della legittima con la riunione fittizia.

Tutti gli importi sono riportati a oggi con un tasso di sconto, così strategie con tempi diversi sono confrontabili.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from . import normativa as nv
from .famiglia import Famiglia
from .legittima import VerificaLegittima, quote_famiglia
from .mercato import Mercato
from .patrimonio import Bene, TipoBene

# ----------------------------------------------------------------------------- atti


@dataclass
class Donazione:
    """Donazione oggi di una quota di un bene (o di un importo, per liquidità e titoli), anche della sola
    nuda proprietà con riserva di usufrutto a favore del donante."""

    beneficiario: str
    bene: str
    quota: float = 1.0
    importo: float | None = None
    nuda_proprieta: bool = False


@dataclass
class Polizza:
    """Polizza vita sulla vita del disponente: il capitale è pagato ai beneficiari «iure proprio», fuori
    dall'eredità ed esente dall'imposta di successione (art. 12 TUS). Il premio entra nella legittima
    (art. 1923, c. 2, c.c.)."""

    beneficiari: dict[str, float]
    importo: float
    da_bene: str
    fattore: str | None = None          # crescita degli attivi: per difetto quella del bene da cui viene il premio
    costi_annui: float = 0.01           # costi annui in più rispetto a tenere gli stessi attivi direttamente
    quota_stato: float = 0.0            # quota di titoli di Stato nella gestione (aliquota sul rendimento)
    nome: str = "Polizza vita"


@dataclass
class Trust:
    """Trust con un beneficiario finale: i beni sono segregati e attribuiti dopo ``durata`` anni.

    Con ``entrata=True`` l'imposta si paga al conferimento (opzione dell'art. 4-bis TUS) sul valore di oggi;
    altrimenti all'attribuzione, sul valore di allora. Aliquota e franchigia dipendono dal rapporto tra
    disponente e beneficiario."""

    beneficiario: str
    importo: float
    da_bene: str
    durata: int
    entrata: bool = True
    costo_istituzione: float = 6_000.0
    costo_annuo: float = 0.004
    minimo_annuo: float = 3_000.0
    nome: str = "Trust"


@dataclass
class PattoDiFamiglia:
    """Patto di famiglia (artt. 768-bis ss. c.c.): l'azienda o la partecipazione va oggi a un discendente e gli
    altri legittimari sono liquidati. Quanto attribuito non è soggetto a collazione né a riduzione: esce dalla
    riunione fittizia. Il trasferimento è esente se l'assegnatario mantiene il controllo per cinque anni (art. 3,
    c. 4-ter, TUS); le liquidazioni sono tassate come donazioni del disponente (art. 58 TUS, ris. 12/E/2025).

    ``liquidazioni``: legittimario → importo, pagato con i ``da_beni`` del disponente nell'ordine (una lista, o un
    dizionario bene → importo massimo). L'obbligo è dell'assegnatario, ma il disponente può fornirgli i mezzi."""

    assegnatario: str
    bene: str
    liquidazioni: dict[str, float] = field(default_factory=dict)
    da_beni: list[str] | dict[str, float] = field(default_factory=list)
    costo_atto: float = 5_000.0
    nome: str = "Patto di famiglia"


@dataclass
class Testamento:
    """Disposizioni per i beni che restano alla morte.

    ``assegnazioni``: bene → {persona: quota} (quote della parte del bene ancora nel patrimonio);
    ``usufrutti``: bene → persona che riceve l'usufrutto (la nuda proprietà segue assegnazioni e residuo);
    ``legati``: persona → somma di denaro; ``residuo``: persona → quota di tutto il resto.
    """

    residuo: dict[str, float]
    assegnazioni: dict[str, dict[str, float]] = field(default_factory=dict)
    usufrutti: dict[str, str] = field(default_factory=dict)
    legati: dict[str, float] = field(default_factory=dict)


@dataclass
class Strategia:
    nome: str
    descrizione: str = ""
    atti: list = field(default_factory=list)
    testamento: Testamento | None = None        # None: successione legittima


@dataclass
class Parametri:
    tasso_sconto: float = 0.03
    costo_atto_donazione: float = 2_500.0       # onorario notarile e due testimoni, per atto
    costo_successione: float = 3_000.0          # dichiarazione di successione e volture
    comproprieta_esente: bool = True            # esenzione della partecipazione indivisa con rappresentante comune


# ----------------------------------------------------------------------------- risultati

VOCI = ["Imposta di donazione", "Imposta di successione", "Ipotecaria e catastale", "Imposte sui redditi",
        "Imposte latenti sui titoli donati", "Costi"]
DISPONENTE = "Disponente"


@dataclass
class Assegnazione:
    """Un bene (o una sua parte) che arriva a una persona."""

    persona: str
    bene: str
    fonte: str              # successione, donazione, polizza, trust, patto di famiglia
    diritto: str            # piena, nuda, usufrutto, denaro
    valore: float           # valore di mercato quando arriva (al netto dei costi interni di polizza e trust)
    anno: int
    base: float = 0.0       # base imponibile
    latente: float = 0.0    # imposta latente sulle plusvalenze dei titoli
    legittima: float = 0.0  # valore ai fini della riunione fittizia e dell'imputazione


@dataclass
class Voce:
    """Un'imposta o un costo. ``implicito``: già dedotto dal valore ricevuto (costi interni di polizza e trust)."""

    persona: str
    voce: str
    importo: float
    anno: int
    implicito: bool = False


@dataclass
class Esito:
    strategia: Strategia
    anno_morte: int
    tasso: float
    assegnazioni: list[Assegnazione]
    voci: list[Voce]
    legittima: VerificaLegittima
    righe: list[dict]
    nomi: list[str] = field(default_factory=list)

    def sconto(self, anno: int) -> float:
        return (1.0 + self.tasso) ** -anno

    def per_persona(self) -> pd.DataFrame:
        """Valori riportati a oggi per beneficiario. Le spese pagate in vita dal disponente non sono attribuite
        ai beneficiari: hanno già ridotto il patrimonio che resta in eredità."""
        presenti = {a.persona for a in self.assegnazioni}
        persone = [n for n in self.nomi if n in presenti] + sorted(presenti - set(self.nomi))
        df = pd.DataFrame(0.0, index=persone, columns=["Ricevuto", *VOCI, "Netto"])
        for a in self.assegnazioni:
            df.loc[a.persona, "Ricevuto"] += a.valore * self.sconto(a.anno)
            df.loc[a.persona, "Imposte latenti sui titoli donati"] += a.latente * self.sconto(a.anno)
        for v in self.voci:
            if v.persona in df.index and not v.implicito:
                df.loc[v.persona, v.voce] += v.importo * self.sconto(v.anno)
        df["Netto"] = df["Ricevuto"] - df[VOCI].sum(axis=1)
        return df

    def costi(self) -> pd.Series:
        """Imposte e costi del passaggio riportati a oggi, compresi quelli pagati in vita e quelli interni."""
        s = pd.Series(0.0, index=VOCI)
        for v in self.voci:
            s[v.voce] += v.importo * self.sconto(v.anno)
        for a in self.assegnazioni:
            s["Imposte latenti sui titoli donati"] += a.latente * self.sconto(a.anno)
        return s

    @property
    def costo_totale(self) -> float:
        return float(self.costi().sum())

    @property
    def netto_totale(self) -> float:
        """Netto riportato a oggi per tutti i beneficiari (calcolo diretto, senza pandas: serve nella simulazione)."""
        r = sum((a.valore - a.latente) * self.sconto(a.anno) for a in self.assegnazioni)
        return r - sum(v.importo * self.sconto(v.anno) for v in self.voci
                       if not v.implicito and v.persona != DISPONENTE)

    def netto(self, persona: str) -> float:
        r = sum((a.valore - a.latente) * self.sconto(a.anno) for a in self.assegnazioni if a.persona == persona)
        return r - sum(v.importo * self.sconto(v.anno) for v in self.voci if not v.implicito and v.persona == persona)

    @property
    def lesione_totale(self) -> float:
        return float(sum(self.legittima.lesioni.values()))


# ----------------------------------------------------------------------------- motore


def _valore_legittima(b: Bene, quota: float, valore_T: float) -> float:
    """Valore di una liberalità nella riunione fittizia: il denaro al nominale (art. 751 c.c.), gli altri beni
    al valore all'apertura della successione, in piena proprietà anche se donati in nuda proprietà."""
    return b.valore * quota if b.tipo == TipoBene.LIQUIDITA else valore_T


def _quota(b: Bene, quota: float | None, importo: float | None) -> float:
    if importo is not None:
        if b.tipo not in (TipoBene.LIQUIDITA, TipoBene.FONDI, TipoBene.TITOLI_STATO):
            raise ValueError(f"{b.nome}: un importo si può trasferire solo da liquidità o titoli")
        return importo / b.valore
    return 1.0 if quota is None else quota


def esegui(strategia: Strategia, famiglia: Famiglia, beni: list[Bene], anno_morte: int,
           mercato: Mercato | None = None, parametri: Parametri | None = None) -> Esito:
    """Calcola gli effetti di una strategia se il disponente muore tra ``anno_morte`` anni."""
    if anno_morte < 1:
        raise ValueError("l'anno della morte deve essere almeno 1")
    par = parametri or Parametri()
    T = anno_morte
    orizzonte = max([a.durata for a in strategia.atti if isinstance(a, Trust)] + [T])
    mercato = mercato or Mercato.atteso(anni=orizzonte + 1)
    patr = {b.nome: b for b in beni}
    if len(patr) != len(beni):
        raise ValueError("nomi dei beni duplicati")
    liquidi = [n for n, b in patr.items() if b.tipo == TipoBene.LIQUIDITA]
    quota_rest = {n: 1.0 for n in patr}
    cassa = 0.0                                  # spese pagate oggi dal disponente
    ass: list[Assegnazione] = []
    voci: list[Voce] = []
    righe: list[dict] = []
    franchigia_residua = {p.nome: nv.franchigia(p.parentela, p.disabile) for p in famiglia.persone}
    donatum = 0.0

    def g(b: Bene, t1: int, t0: int = 0) -> float:
        return mercato.crescita(b.fattore, t1, t0)

    def preleva(b: Bene, q: float) -> None:
        if q > quota_rest[b.nome] + 1e-9:
            raise ValueError(f"{b.nome}: quota trasferita ({q:.4f}) superiore a quella disponibile "
                             f"({quota_rest[b.nome]:.4f})")
        quota_rest[b.nome] -= q

    def paga_oggi(voce: str, importo: float) -> None:
        nonlocal cassa
        voci.append(Voce(DISPONENTE, voce, importo, 0))
        cassa -= importo

    def imposta_donazione(persona: str, base: float, descr: str) -> float:
        """Imposta con il cumulo delle donazioni precedenti allo stesso beneficiario (art. 57 TUS)."""
        p = famiglia[persona]
        usata = min(base, franchigia_residua[persona])
        franchigia_residua[persona] -= usata
        imp = nv.ALIQUOTE[p.parentela].aliquota * (base - usata)
        righe.append({"momento": "oggi", "atto": descr, "persona": persona, "base": base, "franchigia": usata,
                      "imposta": imp})
        return imp

    # --- atti di oggi
    for atto in strategia.atti:
        if isinstance(atto, Donazione):
            b, p = patr[atto.bene], famiglia[atto.beneficiario]
            q = _quota(b, atto.quota, atto.importo)
            preleva(b, q)
            np_quota = nv.quota_nuda_proprieta(famiglia.eta) if atto.nuda_proprieta else 1.0
            base = b.base_donazione(prima_casa=p.prima_casa) * q * np_quota
            esente = (b.tipo == TipoBene.PARTECIPAZIONE and p.parentela in nv.PARENTELE_ESENZIONE_AZIENDA
                      and q * b.quota_societaria > 0.5)
            descr = f"Donazione {'nuda proprietà ' if atto.nuda_proprieta else ''}{b.nome}"
            if esente:
                descr += " (esente: partecipazione di controllo)"
            paga_oggi("Imposta di donazione", imposta_donazione(p.nome, 0.0 if esente else base, descr))
            if b.tipo == TipoBene.IMMOBILE:
                paga_oggi("Ipotecaria e catastale", nv.ipocatastali(base, p.prima_casa))
            paga_oggi("Costi", par.costo_atto_donazione)
            v_T = b.valore * q * g(b, T)
            lat = nv.aliquota_redditi(b.quota_stato) * max(0.0, v_T - b.costo_fiscale * q) if b.finanziario else 0.0
            leg = _valore_legittima(b, q, v_T)
            ass.append(Assegnazione(p.nome, b.nome, "donazione", "piena", v_T, T, base, lat, leg))
            donatum += leg

        elif isinstance(atto, Polizza):
            b = patr[atto.da_bene]
            q = _quota(b, None, atto.importo)
            preleva(b, q)
            if b.finanziario:
                plus = max(0.0, (b.valore - b.costo_fiscale) * q)
                imp = nv.aliquota_redditi(b.quota_stato) * plus
                paga_oggi("Imposte sui redditi", imp)
                righe.append({"momento": "oggi", "atto": f"Vendita {b.nome} per pagare il premio",
                              "persona": DISPONENTE, "base": plus, "franchigia": 0.0, "imposta": imp})
            lordo = atto.importo * mercato.crescita(atto.fattore or b.fattore, T)
            capitale = lordo * (1.0 - atto.costi_annui) ** T
            irpef = nv.aliquota_redditi(atto.quota_stato) * max(0.0, capitale - atto.importo)
            tot = sum(atto.beneficiari.values())
            for persona, w in atto.beneficiari.items():
                w /= tot
                famiglia[persona]
                ass.append(Assegnazione(persona, atto.nome, "polizza", "denaro", capitale * w, T,
                                        legittima=atto.importo * w))
                voci.append(Voce(persona, "Imposte sui redditi", irpef * w, T))
                voci.append(Voce(persona, "Costi", (lordo - capitale) * w, T, implicito=True))
            donatum += atto.importo
            righe.append({"momento": "alla morte", "atto": f"{atto.nome}: capitale esente, imposta sul rendimento",
                          "persona": ", ".join(atto.beneficiari), "base": max(0.0, capitale - atto.importo),
                          "franchigia": 0.0, "imposta": irpef})

        elif isinstance(atto, Trust):
            b, p = patr[atto.da_bene], famiglia[atto.beneficiario]
            q = _quota(b, None, atto.importo)
            preleva(b, q)
            paga_oggi("Costi", atto.costo_istituzione)
            if atto.entrata:
                paga_oggi("Imposta di donazione",
                          imposta_donazione(p.nome, b.base_donazione() * q, f"{atto.nome}: conferimento"))
            v, D = atto.importo, atto.durata
            for t in range(D):
                v *= mercato.annuale(b.fattore, t)
                fee = max(atto.costo_annuo * v, atto.minimo_annuo)
                v -= fee
                voci.append(Voce(p.nome, "Costi", fee, t + 1, implicito=True))
            if not atto.entrata:
                base = b.base_donazione(v / q) * q
                usata = min(base, franchigia_residua[p.nome])
                franchigia_residua[p.nome] -= usata
                imp = nv.ALIQUOTE[p.parentela].aliquota * (base - usata)
                voci.append(Voce(p.nome, "Imposta di donazione", imp, D))
                righe.append({"momento": f"anno {D}", "atto": f"{atto.nome}: attribuzione", "persona": p.nome,
                              "base": base, "franchigia": usata, "imposta": imp})
            lat = nv.aliquota_redditi(b.quota_stato) * max(0.0, v - b.costo_fiscale * q) if b.finanziario else 0.0
            leg = _valore_legittima(b, q, b.valore * q * g(b, T))
            ass.append(Assegnazione(p.nome, atto.nome, "trust", "piena", v, D, latente=lat, legittima=leg))
            donatum += leg
        elif isinstance(atto, PattoDiFamiglia):
            b, p = patr[atto.bene], famiglia[atto.assegnatario]
            preleva(b, quota_rest[b.nome])
            esente = p.parentela in nv.PARENTELE_ESENZIONE_AZIENDA and (
                b.tipo != TipoBene.PARTECIPAZIONE or b.quota_societaria > 0.5)
            base = b.base_donazione()
            paga_oggi("Imposta di donazione", imposta_donazione(
                p.nome, 0.0 if esente else base, f"{atto.nome}: {b.nome}" + (" (esente)" if esente else "")))
            paga_oggi("Costi", atto.costo_atto)
            ass.append(Assegnazione(p.nome, b.nome, "patto di famiglia", "piena", b.valore * g(b, T), T, base))
            for persona, importo in atto.liquidazioni.items():
                famiglia[persona]
                resto = importo
                limiti = atto.da_beni if isinstance(atto.da_beni, dict) else dict.fromkeys(atto.da_beni, float("inf"))
                for nome, limite in limiti.items():
                    if resto <= 1e-6:
                        break
                    fonte = patr[nome]
                    usa = min(resto, limite, fonte.valore * quota_rest[nome])
                    if usa <= 0:
                        continue
                    qf = usa / fonte.valore
                    preleva(fonte, qf)
                    v_T = usa * g(fonte, T)
                    lat = (nv.aliquota_redditi(fonte.quota_stato) * max(0.0, v_T - fonte.costo_fiscale * qf)
                           if fonte.finanziario else 0.0)
                    ass.append(Assegnazione(persona, f"Liquidazione ({nome})", "patto di famiglia", "piena",
                                            v_T, T, fonte.base_donazione() * qf, lat))
                    resto -= usa
                if resto > 1e-6:
                    raise ValueError(f"{atto.nome}: beni insufficienti per liquidare {persona}")
                paga_oggi("Imposta di donazione", imposta_donazione(
                    persona, importo, f"{atto.nome}: liquidazione a {persona}"))
        else:
            raise TypeError(f"atto non riconosciuto: {atto!r}")

    if abs(cassa) > 0 and not liquidi:
        raise ValueError("serve un conto di liquidità da cui pagare imposte e costi di oggi")

    # --- successione
    cassa_T = cassa * mercato.crescita("liquidita", T)
    if strategia.testamento is None:
        ab, _ = quote_famiglia(famiglia)
        test = Testamento(residuo={k: float(v) for k, v in ab.items()})
    else:
        test = strategia.testamento
    valori_T = {n: b.valore * quota_rest[n] * g(b, T) for n, b in patr.items()}
    for n in liquidi:
        valori_T[n] += cassa_T / len(liquidi)
    if any(v < -1e-6 for v in valori_T.values()):
        raise ValueError("la liquidità non basta a pagare imposte e costi di oggi")
    eredita = _successione(patr, quota_rest, valori_T, test, famiglia, T, par, righe, voci)
    ass.extend(eredita)
    tot = sum(test.residuo.values())
    for persona, w in test.residuo.items():
        voci.append(Voce(persona, "Costi", par.costo_successione * w / tot, T))

    # --- legittima: riunione fittizia e imputazione delle liberalità ricevute
    _, riserve = quote_famiglia(famiglia)
    ricevuto = {n: 0.0 for n in riserve}
    for a in ass:
        if a.persona in ricevuto:
            ricevuto[a.persona] += a.legittima
    a_altri = sum(a.legittima for a in ass if a.persona not in riserve)
    verifica = VerificaLegittima(sum(valori_T.values()), donatum, riserve, ricevuto, a_altri)
    return Esito(strategia, T, par.tasso_sconto, ass, voci, verifica, righe, famiglia.nomi)


def _successione(patr: dict[str, Bene], quota_rest: dict[str, float], valori_T: dict[str, float],
                 test: Testamento, famiglia: Famiglia, T: int, par: Parametri, righe: list[dict],
                 voci: list[Voce]) -> list[Assegnazione]:
    tot_residuo = sum(test.residuo.values())
    if abs(tot_residuo - 1.0) > 1e-6:
        raise ValueError(f"le quote del residuo devono sommare a 1 (sommano {tot_residuo:.4f})")
    for nome in list(test.assegnazioni) + list(test.usufrutti):
        if nome not in patr:
            raise KeyError(f"bene non presente nel patrimonio: {nome}")
    base_persona: dict[str, float] = {}
    out: list[Assegnazione] = []

    # i legati in denaro sono pagati con i beni del residuo: prima liquidità e titoli, poi il resto
    legati = sum(test.legati.values())
    residui = {n: v * (1.0 - sum(test.assegnazioni.get(n, {}).values())) for n, v in valori_T.items()}
    liquidi = {n for n, b in patr.items() if b.tipo in (TipoBene.LIQUIDITA, TipoBene.FONDI, TipoBene.TITOLI_STATO)}
    res_liq = sum(v for n, v in residui.items() if n in liquidi)
    res_altri = sum(v for n, v in residui.items() if n not in liquidi)
    if legati > res_liq + res_altri + 1e-6:
        raise ValueError("i legati in denaro superano il valore dei beni del residuo")
    if legati <= res_liq:
        r_liq, r_altri = (1.0 - legati / res_liq if res_liq > 0 else 1.0), 1.0
    else:
        r_liq, r_altri = 0.0, 1.0 - (legati - res_liq) / res_altri
    for persona, imp in test.legati.items():
        famiglia[persona]
        out.append(Assegnazione(persona, "Legato in denaro", "successione", "denaro", imp, T, imp, legittima=imp))
        base_persona[persona] = base_persona.get(persona, 0.0) + imp

    for n, b in patr.items():
        v_T, q_est = valori_T[n], quota_rest[n]
        if v_T <= 1e-9:
            continue
        quote = dict(test.assegnazioni.get(n, {}))
        resto = 1.0 - sum(quote.values())
        if resto < -1e-9:
            raise ValueError(f"{n}: quote assegnate superiori a 1")
        riduzione = r_liq if n in liquidi else r_altri
        for persona, w in test.residuo.items():
            quote[persona] = quote.get(persona, 0.0) + resto * w * riduzione
        quote = {p: w for p, w in quote.items() if w > 1e-12}
        usufruttuario = test.usufrutti.get(n)
        u = nv.quota_usufrutto(famiglia[usufruttuario].eta + T) if usufruttuario else 0.0
        diritti = [(p, w, "nuda" if usufruttuario else "piena", 1.0 - u) for p, w in quote.items()]
        if usufruttuario:
            diritti.append((usufruttuario, sum(quote.values()), "usufrutto", u))
        prima_casa = any(famiglia[p].prima_casa for p, *_ in diritti)
        base_bene = b.base_imponibile(b.valore * v_T / (b.valore * q_est) if q_est > 0 else b.valore,
                                      prima_casa) * q_est
        if b.tipo == TipoBene.LIQUIDITA:
            base_bene = v_T
        eleggibili = all(famiglia[p].parentela in nv.PARENTELE_ESENZIONE_AZIENDA for p in quote)
        ipo: list[tuple[str, float]] = []
        for persona, w, diritto, frazione in diritti:
            p = famiglia[persona]
            base = base_bene * w * frazione
            if b.tipo == TipoBene.PARTECIPAZIONE and p.parentela in nv.PARENTELE_ESENZIONE_AZIENDA:
                controllo = w * q_est * b.quota_societaria > 0.5
                indivisa = par.comproprieta_esente and eleggibili and q_est * b.quota_societaria > 0.5
                if controllo or indivisa:
                    base = 0.0
            valore = v_T * w * frazione
            out.append(Assegnazione(persona, n, "successione", diritto, valore, T, base, legittima=valore))
            base_persona[persona] = base_persona.get(persona, 0.0) + base
            if b.tipo == TipoBene.IMMOBILE:
                ipo.append((persona, base_bene * w * frazione))
        if ipo:
            tot = sum(x for _, x in ipo)
            imp = nv.ipocatastali(tot, prima_casa)
            for persona, x in ipo:
                voci.append(Voce(persona, "Ipotecaria e catastale", imp * x / tot if tot else 0.0, T))

    for persona, base in base_persona.items():
        p = famiglia[persona]
        imp = nv.imposta(base, p.parentela, disabile=p.disabile)
        voci.append(Voce(persona, "Imposta di successione", imp, T))
        righe.append({"momento": "alla morte", "atto": "Successione", "persona": persona, "base": base,
                      "franchigia": min(base, nv.franchigia(p.parentela, p.disabile)), "imposta": imp})
    return out


def confronta(strategie: list[Strategia], famiglia: Famiglia, beni: list[Bene], anno_morte: int,
              mercato: Mercato | None = None, parametri: Parametri | None = None) -> list[Esito]:
    return [esegui(s, famiglia, beni, anno_morte, mercato, parametri) for s in strategie]


def tabella_confronto(esiti: list[Esito]) -> pd.DataFrame:
    righe = []
    for e in esiti:
        c = e.costi()
        righe.append({"Strategia": e.strategia.nome, **c.to_dict(), "Totale imposte e costi": c.sum(),
                      "Netto ai beneficiari": e.netto_totale, "Lesione di legittima": e.lesione_totale})
    return pd.DataFrame(righe).set_index("Strategia")
