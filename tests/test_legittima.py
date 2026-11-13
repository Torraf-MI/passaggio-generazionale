from fractions import Fraction as F

import pytest

from passaggio_generazionale.legittima import disponibile, quote_ab_intestato, quote_riserva


@pytest.mark.parametrize("coniuge,figli,attese", [
    ("C", ["A"], {"C": F(1, 2), "A": F(1, 2)}),
    ("C", ["A", "B"], {"C": F(1, 3), "A": F(1, 3), "B": F(1, 3)}),
    ("C", ["A", "B", "D", "E"], {"C": F(1, 3), "A": F(1, 6), "B": F(1, 6), "D": F(1, 6), "E": F(1, 6)}),
    (None, ["A", "B"], {"A": F(1, 2), "B": F(1, 2)}),
    ("C", [], {"C": F(1)}),
])
def test_ab_intestato_con_figli_o_coniuge(coniuge, figli, attese):
    assert quote_ab_intestato(coniuge, figli) == attese


def test_ab_intestato_coniuge_genitori_fratelli():
    q = quote_ab_intestato("C", [], ["P"], ["X", "Y"])
    assert q["C"] == F(2, 3)
    assert q["P"] == F(1, 4)                              # agli ascendenti almeno un quarto (art. 582)
    assert q["X"] == q["Y"] == F(1, 24)
    assert sum(q.values()) == 1


def test_ab_intestato_genitori_e_fratelli():
    q = quote_ab_intestato(None, [], ["P"], ["X", "Y", "Z"])
    assert q["P"] == F(1, 2)                              # mai meno della metà (art. 571)
    assert q["X"] == F(1, 6)
    q = quote_ab_intestato(None, [], ["P", "M"], ["X"])
    assert q == {"P": F(1, 3), "M": F(1, 3), "X": F(1, 3)}
    with pytest.raises(ValueError):
        quote_ab_intestato(None, [])


@pytest.mark.parametrize("coniuge,figli,ascendenti,attese,disp", [
    (None, ["A"], [], {"A": F(1, 2)}, F(1, 2)),
    (None, ["A", "B", "D"], [], {"A": F(2, 9), "B": F(2, 9), "D": F(2, 9)}, F(1, 3)),
    ("C", [], [], {"C": F(1, 2)}, F(1, 2)),
    ("C", ["A"], [], {"C": F(1, 3), "A": F(1, 3)}, F(1, 3)),
    ("C", ["A", "B"], [], {"C": F(1, 4), "A": F(1, 4), "B": F(1, 4)}, F(1, 4)),
    (None, [], ["P", "M"], {"P": F(1, 6), "M": F(1, 6)}, F(2, 3)),
    ("C", [], ["P"], {"C": F(1, 2), "P": F(1, 4)}, F(1, 4)),
])
def test_quote_di_riserva(coniuge, figli, ascendenti, attese, disp):
    r = quote_riserva(coniuge, figli, ascendenti)
    assert r == attese
    assert disponibile(r) == disp
