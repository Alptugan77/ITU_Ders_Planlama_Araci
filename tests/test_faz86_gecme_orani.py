"""Faz 86 — tahmini zorlukta GEÇME ORANI ortalamanın önünde.

Kullanıcı 24.09.2026: *"zorluk düzeyi hesaplamasında geçilme yüzdesini
geçilme notunun üstüne koyar mısın bazen çan dağılımı yüzünden kolay dersler
orta zorlukta veya zor diye anlaşılabilir"*.

Faz 85 yalnız ortalamaya bakıyordu. Gerçek katalogda ortalaması < 2.40 ama
FF oranı < %4 olan 21 ders "zor"/"çok zor" çıkıyordu (GMI 214: ortalama
2.18, FF %1.1, n=95 → "çok zor").
"""
import pathlib

from itucap import notlar as ND
from itucap import ui as UI

KAYNAK = pathlib.Path(UI.__file__).read_text(encoding="utf-8")
S = ND.SABIT_OLCEK


def test_CAN_EGRISI_dersi_zor_gorunmuyor():
    # GMI 214'ün gerçek sayıları: düşük ortalama, neredeyse herkes geçiyor.
    assert ND.zorluk_kademesi(1.1, 2.18, S)["level"] == 3          # eskiden 5
    # Aynı ortalama, FF %16 → çok zor. Farkı geçme oranı yapıyor.
    assert ND.zorluk_kademesi(16.0, 2.18, S)["level"] == 5


def test_GECME_ORANI_ortalamadan_AGIR():
    # Ortalaması yüksek ama sınıfın beşte biri kalan ders, ortalaması düşük
    # ama herkesin geçtiği dersten ZOR.
    a = ND.zorluk_kademesi(20.0, 3.2, S)["level"]
    b = ND.zorluk_kademesi(0.0, 2.0, S)["level"]
    assert a > b, (a, b)
    assert ND.ZORLUK_AGIRLIK_GECME > ND.ZORLUK_AGIRLIK_ORT
    assert ND.ZORLUK_AGIRLIK_GECME + ND.ZORLUK_AGIRLIK_ORT == 1


def test_ESITLER_orta_sirada():
    """Derslerin ~%20'sinde FF = 0. Orta sıra olmasa hepsi en kolay uca
    yığılırdı; ortalama onları kendi aralarında ayırmalı."""
    assert ND._pay(S.ff, 0.0, "sabit") == 0.1                    # 5 eşit nokta: %0–%20
    assert ND._pay((1.0, 2.0, 2.0, 3.0), 2.0, "katalog") == 0.5
    assert ND.zorluk_kademesi(0.0, 3.9, S)["level"] < ND.zorluk_kademesi(0.0, 1.5, S)["level"]


def test_CANLI_olcek_katalogdan(tmp_path):
    from itucap import db
    con = db.connect(tmp_path / "ref.sqlite3", "schema.sql")
    # 320 ders: FF oranı 0…31, ortalama 2.0…3.6 — kolaydan zora düzgün yayılım.
    for i in range(320):
        ff = i // 10
        con.execute("INSERT INTO grade_distribution(course_key,term,grade,students,announced)"
                    " VALUES (?,?,?,?,0)", (f"DRS {100 + i}", "202610", "FF", ff))
        con.execute("INSERT INTO grade_distribution(course_key,term,grade,students,announced)"
                    " VALUES (?,?,?,?,0)", (f"DRS {100 + i}", "202610", "BB", 100 - ff))
        con.execute("INSERT INTO grade_distribution_alias(course_code,course_key) VALUES (?,?)",
                    (f"DRS {100 + i}", f"DRS {100 + i}"))
    con.commit()
    o = ND.zorluk_olcegi(con)
    assert o.kaynak == "katalog" and o.n == 320 and len(o.skor) == 320
    kolay, zor = ND.zorluk(con, "DRS 100"), ND.zorluk(con, "DRS 419")
    assert (kolay["level"], zor["level"]) == (1, 5)
    assert kolay["passRate"] == 100.0 and zor["passRate"] == 69.0
    assert zor["passLowerShare"] == 2 and zor["catalog"] == 320


def test_SABIT_tablolar_uretilebilir():
    """Tablolar elle yazılmadı: araç aynı yöntemle üretiyor."""
    arac = pathlib.Path(UI.__file__).resolve().parents[2] / "tools" / "zorluk_olcegi.py"
    assert "ND.zorluk_olcegi(con)" in arac.read_text(encoding="utf-8")
    for ad in ("ff", "ort", "skor"):
        t = ND.ZORLUK_SABIT[ad]
        assert len(t) == 21 and list(t) == sorted(t), ad


def test_ARAYUZ_gecme_orani_once():
    i = KAYNAK.index("function zorlukCumlesi(")
    f = KAYNAK[i:KAYNAK.index("\n}\n", i)]
    assert f.index("geçme oranı %") < f.index("harf notu ortalaması")
    assert "Kademe ağırlıklı olarak <b>geçme oranından</b> (%70)" in KAYNAK
    # Sıralamada kademeden sonra geçme oranı.
    assert "(y ? y.passRate : 0) - (x ? x.passRate : 0)" in KAYNAK
