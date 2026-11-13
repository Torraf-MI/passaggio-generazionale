"""Grafici interattivi (plotly) e report HTML per la famiglia."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
from jinja2 import Environment, PackageLoader, select_autoescape
from plotly.offline import get_plotlyjs, get_plotlyjs_version

from . import normativa as nv
from .analisi import Analisi, imposta_per_parentela
from .legittima import disponibile
from .strategie import VOCI

BLU, BLU_SCURO, ACQUA, ARANCIO = "#2a78d6", "#1c5cab", "#1baf7a", "#eb6834"
ROSSO, GIALLO, VIOLA, GRIGIO = "#e34948", "#e8a317", "#8a5cd1", "#8c8b86"
TESTO, TESTO_SECONDARIO, GRIGLIA = "#222222", "#52514e", "#e6e5e1"
COLORE_VOCE = dict(zip(VOCI, [GIALLO, BLU_SCURO, ACQUA, VIOLA, ROSSO, GRIGIO], strict=True))
PALETTE_PERSONE = [BLU_SCURO, ARANCIO, ACQUA, VIOLA, GIALLO, ROSSO, GRIGIO, BLU]
COLORE_PARENTELA = {"Coniuge o unito civilmente": BLU_SCURO, "Figlio": ACQUA, "Fratello o sorella": GIALLO,
                    "Altri parenti e affini": ARANCIO, "Convivente o estraneo": ROSSO}
PLOTLY_CDN = f"https://cdn.plot.ly/plotly-{get_plotlyjs_version()}.min.js"


def _eur(x: float, dec: int = 0) -> str:
    s = f"{abs(x):,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{'−' if x < -0.5 * 10**-dec else ''}{s} €"


def _pct(x: float, dec: int = 1, segno: bool = False) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "–"
    s = f"{x * 100:+.{dec}f}%" if segno else f"{x * 100:.{dec}f}%"
    return s.replace(".", ",").replace("-", "−")


def _num(x: float, dec: int = 0) -> str:
    s = f"{x:,.{dec}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".").replace("-", "−")


def _frazione(f) -> str:
    return f"{f.numerator}/{f.denominator}" if f.denominator != 1 else str(f.numerator)


def _layout(fig: go.Figure, titolo: str, altezza: int = 420) -> go.Figure:
    fig.update_layout(
        title={"text": titolo, "x": 0, "font": {"size": 15, "color": TESTO}},
        height=altezza, template="plotly_white",
        font={"family": "Segoe UI, Helvetica, Arial, sans-serif", "size": 12, "color": TESTO_SECONDARIO},
        margin={"l": 70, "r": 20, "t": 60, "b": 50}, separators=",.",
        hoverlabel={"bgcolor": "white", "font_color": TESTO}, legend={"orientation": "h", "y": -0.16, "x": 0},
    )
    fig.update_xaxes(gridcolor=GRIGLIA, zeroline=False)
    fig.update_yaxes(gridcolor=GRIGLIA, zerolinecolor="#bdbcb6")
    return fig


def _colori_persone(a: Analisi) -> dict[str, str]:
    return {n: PALETTE_PERSONE[i % len(PALETTE_PERSONE)] for i, n in enumerate(a.cfg.famiglia.nomi)}


# ----------------------------------------------------------------------------- grafici
def grafico_parentela(massimo: float = 3_000_000) -> go.Figure:
    x = np.linspace(0, massimo, 121)
    t = imposta_per_parentela(x)
    fig = go.Figure()
    for c in t.columns:
        fig.add_scatter(x=x, y=t[c], mode="lines", name=c,
                        line={"color": COLORE_PARENTELA.get(c, GRIGIO), "width": 2.5},
                        hovertemplate=f"{c}<br>%{{x:,.0f}} €: imposta %{{y:,.0f}} €<extra></extra>")
    fig.update_xaxes(title="Valore ricevuto (base imponibile, €)", tickformat=",.0f")
    fig.update_yaxes(title="Imposta di successione o donazione (€)", tickformat=",.0f")
    return _layout(fig, "La stessa eredità, un'imposta diversa per ogni grado di parentela")


def grafico_quote(a: Analisi) -> go.Figure:
    col = _colori_persone(a)
    fig = go.Figure()
    righe = ["Senza testamento", "Quote di legittima"]
    nomi = list(dict.fromkeys(list(a.ab_intestato) + list(a.riserve)))
    for n in nomi:
        v = [float(a.ab_intestato.get(n, 0)), float(a.riserve.get(n, 0))]
        fig.add_bar(y=righe, x=v, name=n, orientation="h", marker_color=col.get(n, GRIGIO),
                    text=[_frazione(a.ab_intestato.get(n)) if a.ab_intestato.get(n) else "",
                          _frazione(a.riserve.get(n)) if a.riserve.get(n) else ""], textposition="inside",
                    hovertemplate=f"{n}: %{{x:.1%}}<extra></extra>")
    d = disponibile(a.riserve)
    fig.add_bar(y=righe, x=[0, float(d)], name="Quota disponibile", orientation="h", marker_color="#d9d8d3",
                text=["", _frazione(d)], textposition="inside", hovertemplate="Disponibile: %{x:.1%}<extra></extra>")
    fig.update_layout(barmode="stack")
    fig.update_xaxes(tickformat=".0%", range=[0, 1])
    return _layout(fig, "A chi va il patrimonio senza testamento, e quanto il testamento non può togliere", 300)


def grafico_patrimonio(a: Analisi) -> go.Figure:
    p = a.patrimonio().iloc[::-1]
    fig = go.Figure()
    fig.add_bar(y=p.index, x=p["valore"], name="Valore di mercato", orientation="h", marker_color="#c9d8ec",
                hovertemplate="%{y}<br>valore di mercato %{x:,.0f} €<extra></extra>")
    fig.add_bar(y=p.index, x=p["base"], name="Base imponibile in successione", orientation="h",
                marker_color=BLU_SCURO, text=[_pct(r, 0) for r in p["rapporto"]], textposition="outside",
                cliponaxis=False, hovertemplate="%{y}<br>base imponibile %{x:,.0f} €<extra></extra>")
    fig.update_layout(barmode="overlay")
    fig.update_xaxes(title="€", tickformat=",.0f")
    fig.update_yaxes(automargin=True)
    return _layout(fig, "Il patrimonio: valore di mercato e base imponibile", 120 + 45 * len(p))


def grafico_confronto(a: Analisi) -> go.Figure:
    t = a.tabella.iloc[::-1]
    fig = go.Figure()
    for v in VOCI:
        if t[v].abs().sum() < 1:
            continue
        fig.add_bar(y=t.index, x=t[v], name=v, orientation="h", marker_color=COLORE_VOCE[v],
                    hovertemplate=f"%{{y}}<br>{v}: %{{x:,.0f}} €<extra></extra>")
    tot = t["Totale imposte e costi"]
    fig.add_scatter(y=t.index, x=tot, mode="text", text=[_eur(x) for x in tot], textposition="middle right",
                    showlegend=False, hoverinfo="skip", cliponaxis=False)
    fig.update_layout(barmode="stack")
    fig.update_xaxes(title="Imposte e costi riportati a oggi (€)", tickformat=",.0f", range=[0, tot.max() * 1.22])
    fig.update_yaxes(automargin=True)
    return _layout(fig, f"Quanto costa il passaggio, strategia per strategia (morte tra {a.anno_morte} anni)",
                   140 + 42 * len(t))


def grafico_beneficiari(a: Analisi) -> go.Figure:
    n = a.netti().iloc[::-1]
    col = _colori_persone(a)
    fig = go.Figure()
    for p in n.columns:
        fig.add_bar(y=n.index, x=n[p], name=p, orientation="h", marker_color=col[p],
                    hovertemplate=f"%{{y}}<br>{p}: %{{x:,.0f}} €<extra></extra>")
    fig.update_layout(barmode="stack")
    fig.update_xaxes(title="Netto ricevuto, riportato a oggi (€)", tickformat=",.0f")
    fig.update_yaxes(automargin=True)
    return _layout(fig, "Chi riceve cosa, al netto di imposte e costi", 140 + 42 * len(n))


def grafico_legittima(a: Analisi) -> go.Figure:
    nomi = [e.strategia.nome for e in a.esiti][::-1]
    esiti = a.esiti[::-1]
    col = _colori_persone(a)
    fig = go.Figure()
    for f in list(a.riserve)[::-1]:
        r = [e.legittima.ricevuto.get(f, 0.0) / e.legittima.riserva(f) for e in esiti]
        fig.add_bar(y=nomi, x=r, name=f, orientation="h", marker_color=[ROSSO if x < 0.999 else col[f] for x in r],
                    text=[_pct(x, 0) for x in r], textposition="outside", cliponaxis=False,
                    hovertemplate=f"%{{y}}<br>{f} riceve il %{{x:.0%}} della sua legittima<extra></extra>")
    fig.add_vline(x=1, line_color=ROSSO, line_dash="dash")
    fig.update_layout(barmode="group", legend={"traceorder": "reversed"})
    fig.update_xaxes(title="Ricevuto (eredità, donazioni e premi) in % della quota di legittima", tickformat=".0%",
                     rangemode="tozero")
    fig.update_yaxes(automargin=True)
    return _layout(fig, "La legittima è rispettata? Sotto il 100% il legittimario può chiedere la riduzione",
                   160 + 55 * len(nomi))


def grafico_rischio(a: Analisi) -> go.Figure:
    s = a.simulazione.sintesi().iloc[::-1]
    r = s["Scenari con lesione"]
    fig = go.Figure(go.Bar(y=s.index, x=r, orientation="h", marker_color=[ROSSO if x > 0.05 else ACQUA for x in r],
                           text=[_pct(x, 0) for x in r], textposition="outside", cliponaxis=False,
                           customdata=[_eur(x) for x in s["Lesione media"]],
                           hovertemplate="%{y}: lesione nel %{x:.0%} degli scenari<br>lesione media %{customdata}"
                                         "<extra></extra>"))
    fig.update_xaxes(title="Scenari in cui un legittimario riceve meno della sua quota", tickformat=".0%",
                     range=[0, max(0.1, r.max() * 1.18)])
    fig.update_yaxes(automargin=True)
    return _layout(fig, "Il rischio di lite: la legittima si calcola sui valori alla morte, non su quelli di oggi",
                   140 + 42 * len(s))


def grafico_usufrutto(a: Analisi) -> go.Figure:
    eta = np.arange(18, 100)
    np_q = [nv.quota_nuda_proprieta(x) for x in eta]
    fig = go.Figure(go.Scatter(x=eta, y=np_q, mode="lines", line={"shape": "hv", "color": BLU_SCURO, "width": 2.5},
                               name="Nuda proprietà", hovertemplate="%{x} anni: %{y:.0%}<extra></extra>"))
    e = a.cfg.famiglia.eta
    fig.add_scatter(x=[e], y=[nv.quota_nuda_proprieta(e)], mode="markers+text", marker={"color": ROSSO, "size": 11},
                    text=[f"{a.cfg.famiglia.disponente.split()[0]}, {e:.0f} anni: "
                          f"{_pct(nv.quota_nuda_proprieta(e), 0)}"],
                    textposition="top left", showlegend=False, hoverinfo="skip")
    fig.update_xaxes(title="Età dell'usufruttuario")
    fig.update_yaxes(title="Nuda proprietà, in % della piena proprietà", tickformat=".0%", range=[0, 1])
    return _layout(fig, "Quanto vale la nuda proprietà: più è anziano chi si tiene l'usufrutto, più si paga", 360)


def grafico_simulazione(a: Analisi, scelte: list[str] | None = None) -> go.Figure:
    s = a.simulazione
    d = s.differenze()
    rif = s.strategie[s.riferimento]
    scelte = scelte or [n for n in s.strategie if n != rif and "legittima" not in n.lower()
                        and "fai da te" not in n.lower() and d[n].quantile(0.05) > -150_000]
    fig = go.Figure()
    for i, n in enumerate(scelte):
        fig.add_box(x=d[n], name=n, marker_color=PALETTE_PERSONE[i % len(PALETTE_PERSONE)], boxpoints=False,
                    hovertemplate=f"{n}<extra></extra>")
    fig.add_vline(x=0, line_color=GRIGIO)
    fig.update_xaxes(title=f"Netto ai beneficiari rispetto a «{rif}» (€, a oggi)", tickformat=",.0f")
    fig.update_yaxes(autorange="reversed", automargin=True)
    fig.update_layout(showlegend=False)
    return _layout(fig, f"Simulazione: {len(s.anni):,} scenari di durata della vita e dei mercati".replace(",", "."),
                   140 + 45 * len(scelte))


def grafico_tempo(a: Analisi, scelte: list[str] | None = None) -> go.Figure:
    s = a.simulazione
    d = s.differenze()
    d["anno"] = s.anni
    conta = d.groupby("anno").size()
    m = d.groupby("anno").mean()[conta >= max(10, len(s.anni) // 100)]
    rif = s.strategie[s.riferimento]
    scelte = scelte or [n for n in s.strategie if n != rif and "fai da te" not in n.lower()
                        and "legittima" not in n.lower() and m[n].min() > -100_000]
    fig = go.Figure()
    for i, n in enumerate(scelte):
        fig.add_scatter(x=m.index, y=m[n], mode="lines+markers", name=n,
                        line={"color": PALETTE_PERSONE[i % len(PALETTE_PERSONE)], "width": 2.2},
                        marker={"size": 5},
                        hovertemplate=f"{n}<br>successione tra %{{x}} anni: %{{y:,.0f}} €<extra></extra>")
    fig.add_hline(y=0, line_color=GRIGIO)
    fig.update_xaxes(title="Anni fino alla successione")
    fig.update_yaxes(title=f"Netto rispetto a «{rif}» (€, a oggi)", tickformat=",.0f")
    return _layout(fig, "Il tempo cambia la classifica: vantaggio medio per anno della successione", 440)


def _grafici(a: Analisi) -> dict:
    g = {"parentela": grafico_parentela(), "quote": grafico_quote(a), "patrimonio": grafico_patrimonio(a),
         "confronto": grafico_confronto(a), "beneficiari": grafico_beneficiari(a), "legittima": grafico_legittima(a),
         "usufrutto": grafico_usufrutto(a)}
    if a.simulazione is not None:
        g["rischio"] = grafico_rischio(a)
        g["simulazione"] = grafico_simulazione(a)
        g["tempo"] = grafico_tempo(a)
    return g


def salva_grafici(a: Analisi, cartella: str | Path, scala: float = 2.0) -> list[Path]:
    cartella = Path(cartella)
    cartella.mkdir(parents=True, exist_ok=True)
    out = []
    for nome, fig in _grafici(a).items():
        p = cartella / f"{nome}.png"
        fig.write_image(str(p), width=1000, height=fig.layout.height or 420, scale=scala)
        out.append(p)
    return out


# ----------------------------------------------------------------------------- contesto
def contesto(a: Analisi) -> dict:
    f = a.cfg.famiglia
    rif = a.esiti[a.riferimento]
    best = a.migliore
    t = a.tabella
    tot_valore = sum(b.valore for b in a.cfg.beni)
    pat = a.patrimonio()
    kpi = [
        ("Patrimonio", _eur(tot_valore), f"base imponibile {_eur(pat['base'].sum())}"),
        ("Orizzonte", f"{a.anno_morte} anni", f"speranza di vita a {f.eta:.0f} anni: {_num(a.speranza, 1)}"),
        (f"Costo con «{rif.strategia.nome}»", _eur(rif.costo_totale),
         _pct(rif.costo_totale / tot_valore, 1) + " del patrimonio"),
        (f"Costo con «{best.strategia.nome}»", _eur(best.costo_totale),
         f"netto in più: {_eur(best.netto_totale - rif.netto_totale)}"),
    ]
    if a.simulazione is not None:
        sint = a.simulazione.sintesi()
        r_rif, r_best = sint.loc[rif.strategia.nome], sint.loc[best.strategia.nome]
        kpi[3] = (f"«{best.strategia.nome}»", _eur(best.netto_totale - rif.netto_totale),
                  f"netto in più; lesione nel {_pct(r_best['Scenari con lesione'], 0)} degli scenari")
        kpi.insert(3, (f"Rischio di lite con «{rif.strategia.nome}»", _pct(r_rif["Scenari con lesione"], 0),
                       "degli scenari; lesione media " + _eur(r_rif["Lesione media"])))
    else:
        les = [e for e in a.esiti if e.lesione_totale > 1]
        if les:
            e = max(les, key=lambda x: x.lesione_totale)
            kpi.append(("Lesione di legittima", _eur(e.lesione_totale), f"con «{e.strategia.nome}»"))
    persone = [{"nome": p.nome, "parentela": p.parentela.descrizione, "eta": _num(p.eta),
                "legittimario": "sì" if p.nome in a.riserve else "no",
                "ab": _frazione(a.ab_intestato[p.nome]) if p.nome in a.ab_intestato else "–",
                "riserva": _frazione(a.riserve[p.nome]) if p.nome in a.riserve else "–",
                "aliquota": _pct(nv.ALIQUOTE[p.parentela].aliquota, 0),
                "franchigia": _eur(nv.franchigia(p.parentela, p.disabile)), "note": p.note} for p in f.persone]
    beni = [{"nome": n, "tipo": r["tipo"], "valore": _eur(r["valore"]), "base": _eur(r["base"]),
             "rapporto": _pct(r["rapporto"], 0), "nota": r["nota"]} for n, r in pat.iterrows()]
    aliquote = [{"parentela": p.descrizione, "aliquota": _pct(s.aliquota, 0), "franchigia": _eur(s.franchigia)}
                for p, s in nv.ALIQUOTE.items()]
    strategie = []
    for e in a.esiti:
        r = t.loc[e.strategia.nome]
        strategie.append({
            "nome": e.strategia.nome, "descrizione": e.strategia.descrizione,
            "voci": [_eur(r[v]) for v in VOCI], "totale": _eur(r["Totale imposte e costi"]),
            "netto": _eur(r["Netto ai beneficiari"]), "diff": _eur(e.netto_totale - rif.netto_totale),
            "lesione": _eur(e.lesione_totale) if e.lesione_totale > 1 else "–", "rosso": e.lesione_totale > 1,
            "migliore": e is best, "riferimento": e is rif})
    netti = a.netti()
    tab_netti = [{"strategia": s, "valori": [_eur(v) for v in r]} for s, r in netti.iterrows()]
    leg = []
    for e in a.esiti:
        v = e.legittima
        leg.append({"strategia": e.strategia.nome, "massa": _eur(v.massa), "donatum": _eur(v.donatum),
                    "disponibile": _eur(v.quota_disponibile),
                    "persone": [{"nome": n, "riserva": _eur(v.riserva(n)), "ricevuto": _eur(v.ricevuto.get(n, 0.0)),
                                 "lesione": _eur(v.lesione(n)), "rosso": v.lesione(n) > 1} for n in v.riserve]})
    registro = []
    for e in (rif, best):
        for r in e.righe:
            if r["base"] > 0.5 or r["imposta"] > 0.5:
                registro.append({"strategia": e.strategia.nome, "momento": r["momento"], "atto": r["atto"],
                                 "persona": r["persona"], "base": _eur(r["base"]), "franchigia": _eur(r["franchigia"]),
                                 "imposta": _eur(r["imposta"])})
    ctx = {
        "disponente": f.disponente, "nome": f.disponente.split()[0], "eta": _num(f.eta), "oggi": _data(date.today()),
        "kpi": kpi, "persone": persone, "beni": beni, "aliquote": aliquote, "strategie": strategie, "voci": VOCI,
        "netti_colonne": list(netti.columns), "netti": tab_netti, "legittima": leg, "registro": registro,
        "rif": rif.strategia.nome, "best": best.strategia.nome, "anno_morte": a.anno_morte,
        "tasso": _pct(a.cfg.parametri.tasso_sconto, 0), "speranza": _num(a.speranza, 1),
        "np_oggi": _pct(nv.quota_nuda_proprieta(f.eta), 0), "u_oggi": _pct(nv.quota_usufrutto(f.eta), 0),
        "eur": _eur, "pct": _pct, "num": _num,
    }
    if a.simulazione is not None:
        s = a.simulazione.sintesi()
        ctx["sim"] = [{"strategia": n, "netto": _eur(r["Netto medio"]), "costi": _eur(r["Imposte e costi medi"]),
                       "media": _eur(r["Differenza media"]), "p5": _eur(r["Differenza 5° percentile"]),
                       "p95": _eur(r["Differenza 95° percentile"]), "migliori": _pct(r["Scenari migliori"], 0),
                       "lesione": _pct(r["Scenari con lesione"], 0), "rif": n == rif.strategia.nome,
                       "lesione_media": _eur(r["Lesione media"]) if r["Scenari con lesione"] > 0 else "–"}
                      for n, r in s.iterrows()]
        ctx["scenari"] = _num(len(a.simulazione.anni))
        ctx["anni_mediana"] = _num(float(np.median(a.simulazione.anni)))
        ctx["anni_p10"] = _num(float(np.percentile(a.simulazione.anni, 10)))
        ctx["anni_p90"] = _num(float(np.percentile(a.simulazione.anni, 90)))
    return ctx


def _data(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def build_report(a: Analisi, output: str | Path, data_note: str = "", offline: bool = False) -> Path:
    env = Environment(loader=PackageLoader("passaggio_generazionale", "templates"), autoescape=select_autoescape())
    g = {k: fig.to_html(full_html=False, include_plotlyjs=False, config={"displaylogo": False, "responsive": True})
         for k, fig in _grafici(a).items()}
    html = env.get_template("report.html.j2").render(
        **contesto(a), grafici=g, data_note=data_note, plotly_cdn=PLOTLY_CDN,
        plotly_inline=get_plotlyjs() if offline else None)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    return output
