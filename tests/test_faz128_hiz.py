"""Faz 128 — sayfa hesabı hızlandı; sonuç birebir aynı.

Kullanıcının verisiyle (HTAE + BLG ÇAP) ölçüldü: sayfa durumu 2,07 → 1,24 sn
(5 ölçümün ortancası). Yol haritası bir istekte 48 kez kuruluyordu ve her
kurulumda önşart zinciri (bütün ağaçlar), lisans planı mevsimi (bütün plan
satırları) ve denklik dizini baştan hesaplanıyordu. Doğrulama: 150 gerçek
çiftin haritası ve kullanıcının sayfa durumu eski/yeni kodda birebir aynı.
"""
from itucap import istek as IST
from itucap import rules as R
from itucap import yolharitasi as YH
from test_faz57_yol_haritasi import _katalog


def test_DENKLIKLER_istekte_bir_kez_ve_KOPYA(tmp_path, monkeypatch):
    con = _katalog(tmp_path, [("AAA 101", 3, None)], [("AAA 101", 5)])
    con.execute("INSERT INTO equivalence(target_course,confidence) VALUES ('AAA 101','official')")
    con.execute("INSERT INTO equivalence_source(equivalence_id,course_code,min_grade) VALUES (1,'BBB 101','DD')")
    con.commit()
    say = []
    asil = R._denklik_oku
    monkeypatch.setattr(R, "_denklik_oku", lambda *a, **k: say.append(1) or asil(*a, **k))
    with IST.istek():
        a = R.load_equivalences(con)
        a.clear()                                       # çağıran bozsa bile
        b = R.load_equivalences(con)
    assert len(say) == 1 and len(b) == 1 and a is not b
    R.load_equivalences(con)                            # bağlam dışı: taze
    assert len(say) == 2


def test_DIZIN_icerikle_ve_yerinde_degisimde_dogru():
    e1 = R.Equivalence(1, "AAA 101", (("BBB 101", "DD"),), "official", True)
    e2 = R.Equivalence(2, "CCC 101", (("BBB 101", "DD"),), "official", True)
    a, b = [e1], [e1]                                   # aynı içerik, başka liste
    assert R.expand_with_equivalences({"BBB 101": "BB"}, a)[0].get("AAA 101") == "BB"
    assert R.expand_with_equivalences({"BBB 101": "BB"}, b)[0].get("AAA 101") == "BB"
    b.append(e2)                                        # yerinde değişim → yeniden kur
    assert R.expand_with_equivalences({"BBB 101": "BB"}, b)[0].get("CCC 101") == "BB"
    assert "CCC 101" not in R.expand_with_equivalences({"BBB 101": "BB"}, a)[0]


def test_LISANS_MEVSIMI_ilk_satir_kurali(tmp_path):
    con = _katalog(tmp_path, [("XXX 101", 3, None), ("YYY 101", 3, None)], [("XXX 101", 5)])
    con.execute("INSERT INTO plan(id,program_code,plan_type,title,source) VALUES (9,'PPP','lisans','p','obs')")
    for i, (kod, donem) in enumerate([("YYY 101", 4), ("XXX 101", 3), ("YYY 101", 5)]):
        con.execute("INSERT INTO plan_slot(plan_id,slot_kind,course_code,position,term_no) "
                    "VALUES (9,'REQUIRED',?,?,?)", (kod, i, donem))
    con.commit()
    import sqlite3
    con.row_factory = sqlite3.Row
    with IST.istek():
        assert YH._lisans_mevsimi(con, "PPP", {"YYY 101"}) == "20"          # ilk satır: 4
        assert YH._lisans_mevsimi(con, "PPP", {"XXX 101", "YYY 101"}) == "20"
        assert YH._lisans_mevsimi(con, "PPP", {"XXX 101"}) == "10"
        assert YH._lisans_mevsimi(con, "PPP", {"ZZZ 101"}) is None
