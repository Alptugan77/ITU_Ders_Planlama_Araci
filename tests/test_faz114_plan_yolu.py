"""Faz 114 — yol haritası önce plan yolunu kullanıyor; dış varsayım son çare.

Gerçek katalogda 127 lisans planında (plana sadık, transkriptsiz öğrenci):
* dış sayılan 4294 önşart kodunun 1499'u planın kendi derslerinden RESMÎ
  DENKLİKLE kazanılıyordu (TES 122 ≡ MIM 142); dış sayılınca geçilmiş
  varsayılıyor, ders onu açan plan dersinden ÖNCE yerleşiyordu;
* plandaki alternatif henüz yerleşmemişken dış ders hemen varsayılıyordu:
  MATE'de MAT 112E, planın MAT 111E'sinden önce ("MAT 101 varsayıldı"),
  BIOE'de ING 201A, ING 112A'dan önce.
Sonuç: kartlardaki dış varsayım 277 → 84; sıra ihlali 0, yerleşemeyen ders
değişmedi (16).
"""
from itucap import rules as R
from test_faz57_yol_haritasi import _katalog, _kur, _yer


def _harita(con, **kw):
    h = _kur(con, **kw)
    return _yer(h), {i["course"]: i["externalPrereq"] for t in h["terms"] for i in t["items"]}, h


def test_DENKLIKLE_plandan_kazanilan_dis_degil(tmp_path):
    """Önşart eski kodu (MIM 142) istiyor; plan yeni kodu (TES 122) daha SONRA
    koyuyor; resmî liste TES 122 ≡ MIM 142."""
    con = _katalog(tmp_path / "a", [("MIM 142", 3, None), ("TES 122", 3, None),
                                    ("PEM 209E", 3, "MIM 142 MIN DD")],
                   plan=[("PEM 209E", 5), ("TES 122", 6)])
    esd = [R.Equivalence(1, "MIM 142", (("TES 122", "DD"),), "official", True)]
    yer, dis, _ = _harita(con, equivalences=esd)
    assert yer["TES 122"] < yer["PEM 209E"], yer
    assert dis["PEM 209E"] == []
    yer, dis, _ = _harita(con)                               # denklik yoksa: dış varsayım
    assert dis["PEM 209E"] == ["MIM 142"]


def test_PLAN_YOLU_varken_dis_varsayilmaz(tmp_path):
    con = _katalog(tmp_path / "b", [("MAT 101", 4, None), ("MAT 111E", 4, None),
                                    ("MAT 112E", 4, "MAT 111E MIN DDveya MAT 101 MIN DD")],
                   plan=[("MAT 112E", 5), ("MAT 111E", 5)])        # aynı plan dönemi
    yer, dis, _ = _harita(con)
    assert yer["MAT 111E"] < yer["MAT 112E"], yer
    assert dis["MAT 112E"] == []


def test_PLAN_YOLU_yoksa_varsayim_suruyor(tmp_path):
    con = _katalog(tmp_path / "c", [("ING 101", 3, None), ("ING 201A", 3, "ING 101 MIN DD")],
                   plan=[("ING 201A", 5)])
    yer, dis, h = _harita(con)
    assert "ING 201A" in yer and dis["ING 201A"] == ["ING 101"]
    assert any("(ING 101)" in a for a in h["assumptions"])


def test_KARMA_dal_denklik_ve_gercek_dis(tmp_path):
    """Bir dal denklikle plandan (TES 122 ≡ MIM 142), öbür dal gerçekten dış
    (EXT 101). Plan yolu tek başına yetmiyor; dış yol kullanılırken MIM 142
    de varsayılmamalı: ders TES 122'yi bekliyor, varsayım yalnız EXT 101."""
    con = _katalog(tmp_path / "d", [("MIM 142", 3, None), ("TES 122", 3, None), ("EXT 101", 3, None),
                                    ("PEM 209E", 3, "MIM 142 MIN DDve EXT 101 MIN DD")],
                   plan=[("PEM 209E", 5), ("TES 122", 5)])
    esd = [R.Equivalence(1, "MIM 142", (("TES 122", "DD"),), "official", True)]
    yer, dis, _ = _harita(con, equivalences=esd)
    assert yer["TES 122"] < yer["PEM 209E"], yer
    assert dis["PEM 209E"] == ["EXT 101"], dis
