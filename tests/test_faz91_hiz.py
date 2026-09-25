"""Faz 91 — öneri motoru ve istekler hızlandı; SONUÇLAR aynı.

Kullanıcı 25.09.2026: *"continue your improvements"*. Ölçüm (gerçek katalog,
9 profil): her sayfa durumu statik sitede ~7-8 sn, yerelde 0,5-5 sn sürüyordu.
Profil: sürenin %60'ı her arama düğümünde baştan koşan havuz eşleştirmesi,
%34'ü aynı derslerin şubelerini defalarca okumak.

Bu testler hızlandırmaların ESKİ davranışla birebir aynı cevabı verdiğini
kilitliyor: eşleştirme ve çakışma için rastgele girdilerle eski gerçekleme
karşısında, önbellekler için ömür ve tazelik kurallarıyla.
"""
import pathlib
import random

import pytest

from itucap import db, istek as IST, policy as POL, recommend as REC


# ------------------------------------------------------------ eşleştirme
class _A:
    def __init__(self, yuvalar):
        self.slot_ids = tuple(yuvalar)
        self.slot_id = yuvalar[0] if yuvalar else 0

    yuvalar = REC.Candidate.yuvalar


@pytest.mark.parametrize("tohum", range(40))
def test_ARTIMLI_ESLESTIRME_eskisiyle_ayni(tohum):
    """Aramanın yaptığı gibi: adaylar sırayla geliyor, yalnız sığanlar
    ekleniyor. Her adımda artımlı cevap, baştan Kuhn'un cevabıyla aynı."""
    r = random.Random(tohum)
    yuvalar = list(range(1, r.randint(2, 8)))
    secilen, eslesme = [], {}
    for _ in range(r.randint(3, 14)):
        a = _A(r.sample(yuvalar, r.randint(0, min(3, len(yuvalar)))))
        eski = REC.yuva_ata(secilen + [a]) is not None
        if not a.yuvalar:
            assert eski                                  # yuvasız aday hep serbest
            continue
        yeni = REC.yuva_ekle(eslesme, a)
        assert (yeni is not None) == eski, (tohum, [x.slot_ids for x in secilen], a.slot_ids)
        if yeni is not None:
            # Yeni eşleştirme geçerli: herkes kendi yuvalarından BİRİNDE, yuvalar ayrık.
            assert sorted(map(id, yeni.values())) == sorted(map(id, secilen + [a]))
            assert all(y in c.yuvalar for y, c in yeni.items())
            secilen.append(a)
            eslesme = yeni


def test_ARTIMLI_ESLESTIRME_girdiyi_degistirmiyor():
    a, b = _A([1, 2]), _A([1])
    e1 = REC.yuva_ekle({}, a)
    kopya = dict(e1)
    e2 = REC.yuva_ekle(e1, b)                       # a'yı 2'ye kaydırmak zorunda
    assert e1 == kopya and e2 is not None and e2[1] is b and e2[2] is a


# ------------------------------------------------------------ çakışma maskesi
def _eski_cakisma(x, y):
    return any(REC.overlaps(m, n) for m in x.meetings for n in y.meetings)


@pytest.mark.parametrize("tohum", range(30))
def test_MASKE_eski_cakismayla_ayni(tohum):
    r = random.Random(tohum)

    def sube():
        bul = []
        for _ in range(r.randint(0, 3)):
            bas = r.randint(480, 1300)
            bul.append(REC.Meeting(r.randint(1, 5), bas, bas + r.choice([1, 29, 59, 119, 179, 180]),
                                   None, None, None))
        return REC.Section("x", "X", None, 10, 0, tuple(bul))

    subeler = [sube() for _ in range(25)]
    for a in subeler:
        for b in subeler:
            assert REC.section_conflict(a, b) == _eski_cakisma(a, b)


def test_MASKE_sinirlar():
    m = lambda g, a, b: REC.Section("x", "X", None, 1, 0, (REC.Meeting(g, a, b, None, None, None),))  # noqa: E731
    assert not REC.section_conflict(m(1, 510, 690), m(1, 690, 750))    # 11:30'da biten / başlayan
    assert REC.section_conflict(m(1, 510, 691), m(1, 690, 750))
    assert not REC.section_conflict(m(1, 510, 690), m(2, 510, 690))    # farklı gün
    assert not REC.section_conflict(m(1, 510, 690), REC.Section("y", "Y", None, 1, 0, ()))


# ------------------------------------------------------------ istek önbelleği
def test_ISTEK_BELLEGI_omru():
    sayac = {"n": 0}

    def hesap():
        sayac["n"] += 1
        return sayac["n"]

    assert IST.bellek("k", hesap) == 1 and IST.bellek("k", hesap) == 2   # bağlam dışı: saklamaz
    with IST.istek():
        assert IST.bellek("k", hesap) == 3 and IST.bellek("k", hesap) == 3
        with IST.istek():                                                # iç içe: dıştakini kullanır
            assert IST.bellek("k", hesap) == 3
        assert IST.bellek("k", hesap) == 3
    assert IST.bellek("k", hesap) == 4                                   # bağlam bitti


def _katalog(tmp_path):
    con = db.connect(tmp_path / "ref.sqlite3", "schema.sql")
    con.execute("INSERT INTO lesson(crn,course_code,capacity,enrolled) VALUES ('1','A 101',50,10)")
    con.execute("INSERT INTO lesson_meeting(crn,day_of_week,start_min,end_min) VALUES ('1',1,510,690)")
    con.commit()
    return con


def test_SUBELER_istek_icinde_bir_kez_istekler_arasi_taze(tmp_path, monkeypatch):
    con = _katalog(tmp_path)
    say = {"n": 0}
    orj = REC._load_sections

    def sayan(*a):
        say["n"] += 1
        return orj(*a)

    monkeypatch.setattr(REC, "_load_sections", sayan)
    with IST.istek():
        a = REC.load_sections(con, "A 101", {"X"})
        a.clear()                                       # çağıran listeyi bozsa da…
        b = REC.load_sections(con, "A 101", {"X"})
        assert say["n"] == 1 and len(b) == 1            # …önbellek etkilenmiyor
    # Kontenjan tazelemesi (UPDATE) → sonraki istek YENİ veriyi görür.
    con.execute("UPDATE lesson SET enrolled=50 WHERE crn='1'")
    con.commit()
    with IST.istek():
        assert REC.load_sections(con, "A 101", {"X"})[0].free == 0
    assert say["n"] == 2


def test_KURAL_DOSYASI_icerige_gore(tmp_path):
    yol = tmp_path / "k.toml"
    yol.write_text('[azami_sure]\nyariyil = 14\n', encoding="utf-8")
    a = POL._toml_oku(yol)
    a["azami_sure"]["yariyil"] = 99                     # çağıranın kopyası
    assert POL._toml_oku(yol)["azami_sure"]["yariyil"] == 14
    yol.write_text('[azami_sure]\nyariyil = 12\n', encoding="utf-8")   # aynı boy, hızla
    assert POL._toml_oku(yol)["azami_sure"]["yariyil"] == 12


def test_BAGLANTILAR():
    kaynak = pathlib.Path(REC.__file__).with_name("ui.py").read_text(encoding="utf-8")
    for ad in ("collect", "kalma_riski", "yol_senaryosu", "cap_bitisleri"):
        assert f"@_sube_onbellekli\ndef {ad}(" in kaynak, ad
    site = pathlib.Path(REC.__file__).resolve().parents[2] / "tools" / "site_kur.py"
    assert '"istek"' in site.read_text(encoding="utf-8"), "istek modülü siteye gitmiyor"


_CANLI = r'''
import sys, os, json
sys.path.insert(0, os.environ["ITUCAP_SRC"]); sys.path.insert(0, os.environ["ITUCAP_TOOLS"])
import tempfile, pathlib
import vitrin
kok = vitrin.kur(pathlib.Path(tempfile.mkdtemp(prefix="vitrin-")))
from itucap import declared, server, recommend as REC
declared.DEFAULT_PATH = kok / "config" / "denklikler.toml"
st = server.State(label="ben")
anahtarlar, orj = [], REC._load_sections
def sayan(con, course, allowed):
    anahtarlar.append([course, sorted(allowed)])
    return orj(con, course, allowed)
REC._load_sections = sayan
st.snapshot()
print("OKUMA:" + json.dumps([len(anahtarlar), len({json.dumps(a) for a in anahtarlar})]))
'''


def test_ANLIK_GORUNTU_subeleri_bir_kez_okur(tmp_path, monkeypatch):
    """Vitrin: bir anlık görüntüde her (ders, izinli) için tek okuma.
    ⚠️ Alt süreçte: `vitrin.kur` `config`i geçici dizine çeviriyor; aynı
    süreçte koşsa sonraki testler dosyalarını bulamıyordu (ölçüldü)."""
    import json
    import subprocess
    import sys
    import tempfile
    kok = pathlib.Path(REC.__file__).resolve().parents[2]
    monkeypatch.setenv("ITUCAP_SRC", str(kok / "src"))
    monkeypatch.setenv("ITUCAP_TOOLS", str(kok / "tools"))
    betik = tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, dir=str(tmp_path))
    betik.write(_CANLI); betik.close()
    r = subprocess.run([sys.executable, betik.name], capture_output=True, text=True,
                       timeout=300, cwd=str(tmp_path))
    assert r.returncode == 0, r.stderr[-2000:]
    satir = [x for x in r.stdout.splitlines() if x.startswith("OKUMA:")][0]
    toplam, farkli = json.loads(satir[6:])
    assert toplam and toplam == farkli, (toplam, farkli)
