"""Faz 25/A — elimizde olan ama arayüze hiç çıkmayan veri.

Üç şey OBS'den çekiliyordu, veritabanında duruyordu, motorda taşınıyordu ve
kullanıcı hiç göremiyordu:

* `lesson.teaching_method` — 3417 şubenin hepsinde dolu, 139'u çevrimiçi;
* `enrolled/capacity` — yazıyordu ama okumak için hesap gerekiyordu;
* `unlock_map` — "119 dersin önşartı" diyorduk, hangileri demiyorduk.
"""
import re

import pytest


@pytest.fixture(autouse=True)
def no_real_waivers(monkeypatch, tmp_path):
    from itucap import declared
    monkeypatch.setattr(declared, "DEFAULT_PATH", tmp_path / "yok.toml")


from itucap import prereq as PRQ                                # noqa: E402
from itucap import recommend as REC                             # noqa: E402
from itucap import ui as UI                                     # noqa: E402

from test_ui import _collect, dbs                               # noqa: E402,F401


# ------------------------------------------------------- A1. çevrimiçi ders
@pytest.mark.parametrize("yontem,cevrimici", [
    ("Virtual (Online)", True),
    ("virtual (online)", True),
    ("Online", True),
    ("Physical (Face to face)", False),
    ("", False), (None, False),
])
def test_cevrimici_sube_TANINIYOR(yontem, cevrimici):
    s = REC.Section("1", "X 101", None, 10, 0, (), yontem)
    assert s.online is cevrimici


def test_cevrimici_ders_KAMPUS_DEGISIMI_saymiyor():
    """★ Çevrimiçi ders bir kampüste DEĞİL.

    Kayıtlı bir dersliği olsa bile öğrenci oraya gitmiyor; kampüs değişimi
    sayımına katmak var olmayan bir yolculuk uydurmak olurdu. Araç bu sayıyı
    program seçiminde ölçüt olarak kullanıyor."""
    m = REC.Meeting(1, 510, 600, None, "MED", "Ayazağa")
    yuz_yuze = REC.Section("1", "X 101", None, 10, 0, (m,), "Physical (Face to face)")
    online = REC.Section("2", "X 101", None, 10, 0, (m,), "Virtual (Online)")
    assert yuz_yuze.campuses() == {"Ayazağa"}
    assert online.campuses() == set()


def test_yontem_veritabanindan_OKUNUYOR(dbs):
    con, ucon, sid = dbs
    con.execute("UPDATE lesson SET teaching_method='Virtual (Online)' WHERE crn='100'")
    con.commit()
    subeler = REC.load_sections(con, "BLG 212E", {"BLG"})
    assert {s.crn: s.online for s in subeler} == {"100": True, "101": False}


def test_cevrimici_arayuze_CIKIYOR(dbs):
    con, ucon, sid = dbs
    con.execute("UPDATE lesson SET teaching_method='Virtual (Online)' WHERE crn='100'")
    con.commit()
    data = _collect(dbs)
    c = [x for x in data["candidates"] if x["course"] == "BLG 212E"][0]
    assert [s["online"] for s in c["sections"]] == [True, False]
    assert "çevrimiçi" in UI.render(data)


# --------------------------------------------------------- A2. doluluk çubuğu
def test_doluluk_cubugu_SABLONDA(dbs):
    html = UI.render(_collect(dbs))
    assert "function doluluk(sections)" in html
    assert ".capbar" in html


def test_doluluk_kontenjan_YOKKEN_oran_UYDURMUYOR(dbs):
    """★ Kontenjanı 0 ilan edilmiş şubede "%100 dolu" demek uydurma olurdu.
    (Katalogda gerçekten var: kontenjanı 0 yazan şubeler.)"""
    html = UI.render(_collect(dbs))
    govde = re.search(r"function doluluk\(sections\)\{(.*?)\n\}", html, re.S).group(1)
    assert 'if(!cap) return' in govde
    assert "kontenjan yok" in govde


def test_doluluk_TARIH_yaziyor(dbs):
    """⚠️ Kontenjan tazeleme anına ait. Yaşsız bir gerçek gibi göstermek,
    üç gün önceki "boş"u bugünün "boş"u sandırırdı.

    ⚠️⚠️ FAZ 54'TE YENİDEN YAZILDI: bu test `DATA.generatedAt`ı İSTİYORDU —
    yani yanlış damgayı kilitliyordu. `generatedAt` sayfanın ÜRETİLDİĞİ an;
    sitede her açılışta "şimdi". 23 gün önceki kontenjan "bugün 20:56
    itibarıyla" görünüyordu. Doğrusu son tazeleme (`veriTarihi()`)."""
    html = UI.render(_collect(dbs))
    govde = re.search(r"function doluluk\(sections\)\{(.*?)\n\}", html, re.S).group(1)
    assert "veriTarihi()" in govde
    assert "generatedAt" not in govde


# ------------------------------------------------------ A3. önşart zinciri
def test_unlock_map_HANGI_dersler(dbs):
    con, ucon, sid = dbs
    trees = PRQ.parsed_trees(con)
    assert PRQ.unlock_map(trees).get("BLG 212E") == ["BLG 351E"]


def test_unlock_map_sayisi_unlock_counts_ILE_TUTUYOR(dbs):
    """İki fonksiyon aynı ağaçtan konuşuyor; ayrışırlarsa biri yalan söyler."""
    con, ucon, sid = dbs
    trees = PRQ.parsed_trees(con)
    harita, sayi = PRQ.unlock_map(trees), PRQ.unlock_counts(trees)
    assert {k: len(v) for k, v in harita.items()} == sayi


def test_acilanlar_YALNIZ_kendi_planindan(dbs):
    """★ Katalogdaki 119 dersin çoğu başka bölümün dersi; hepsini yazmak
    "senin için 119 kapı açılıyor" demek olurdu. `opens` yalnız SENİN
    planındaki, HENÜZ GEÇMEDİĞİN dersleri sayıyor."""
    data = _collect(dbs)
    c = [x for x in data["candidates"] if x["course"] == "BLG 212E"][0]
    assert c["opens"] == ["BLG 351E"]


def test_gecilen_ders_acilanlar_listesinden_CIKIYOR(dbs):
    """Geçtiğin dersi "açılacak" diye saymak, biteni yapılacak göstermek."""
    from itucap import student as S
    con, ucon, sid = dbs
    S.add_entries(ucon, sid, [S.make_entry("BLG 351E", "AA")])
    ucon.commit()
    data = _collect(dbs)
    c = [x for x in data["candidates"] if x["course"] == "BLG 212E"][0]
    assert c["opens"] == []


def test_acilanlar_ve_unlocks_AYRI_sayilar(dbs):
    """`unlocks` katalog toplamı, `opens` senin planın. Birini öbürünün
    yerine yazmak yanlış olurdu — ikisi de veride kalıyor."""
    data = _collect(dbs)
    c = [x for x in data["candidates"] if x["course"] == "BLG 212E"][0]
    assert "unlocks" in c and "opens" in c


def test_acilanlar_arayuzde_ISIMLE(dbs):
    html = UI.render(_collect(dbs))
    assert "function acilanNot(c)" in html
    assert "açtıkları:" in html


def test_acilanlarda_dil_cifti_TEKLESTIRILIYOR(dbs):
    """★ Ölçüm (24.08.2026): önşart ağacı 'MAT 201' ve 'MAT 201E'yi ayrı
    düğüm olarak taşıyor. İkisini birden yazmak "iki ders açılıyor" demek
    olurdu — BLG planında MAT 102 için tam olarak bu oluyordu."""
    from itucap import student as S
    con, ucon, sid = dbs
    # BLG 351E'nin Türkçe eşi de katalogda olsun ve plana girsin
    con.execute("INSERT INTO course(code,name,ects,prereq_raw) "
                "VALUES ('BLG 351','Lab TR',2.0,'BLG 212E MIN DD')")
    con.execute("INSERT INTO plan_slot(plan_id,slot_kind,course_code,ects,position) "
                "VALUES (20,'REQUIRED','BLG 351',2.0,9)")
    con.commit()
    from itucap import prereq as P
    P.parse_all(con)
    data = _collect(dbs)
    c = [x for x in data["candidates"] if x["course"] == "BLG 212E"][0]
    assert c["opens"] == ["BLG 351E"] or c["opens"] == ["BLG 351"], c["opens"]
    assert len(c["opens"]) == 1


def test_plan_disi_ders_acilanlara_GIRMIYOR(dbs):
    """Katalogdaki 119 dersin çoğu başka bölümün dersi."""
    con, ucon, sid = dbs
    con.execute("INSERT INTO course(code,name,ects,prereq_raw) "
                "VALUES ('XXX 999','Alakasız',3.0,'BLG 212E MIN DD')")
    con.commit()
    from itucap import prereq as P
    P.parse_all(con)
    data = _collect(dbs)
    c = [x for x in data["candidates"] if x["course"] == "BLG 212E"][0]
    assert "XXX 999" not in c["opens"]


# ------------------------------------------- tarayıcıda gerçekten görünüyor mu
@pytest.fixture()
def sayfa(dbs, tmp_path):
    """Şablonda dizge aramak yetmez: JS'in o dalı çalıştırdığını görmek gerek."""
    pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import sync_playwright

    con, ucon, sid = dbs
    con.execute("UPDATE lesson SET teaching_method='Virtual (Online)' WHERE crn='100'")
    con.execute("UPDATE lesson SET capacity=10, enrolled=10 WHERE crn='200'")
    con.commit()
    dest = UI.write(_collect(dbs), tmp_path / "ui.html")
    try:
        pw = sync_playwright().start()
        tarayici = pw.chromium.launch()
        p = tarayici.new_page(viewport={"width": 1300, "height": 1000})
    except Exception as exc:
        pytest.skip(f"playwright başlatılamadı: {exc}")
    hatalar = []
    p.on("pageerror", lambda e: hatalar.append(str(e)))
    p.goto(dest.as_uri())
    p.wait_for_timeout(500)
    yield p, hatalar
    tarayici.close(); pw.stop()


def test_tarayicida_acilanlar_YAZIYOR(sayfa):
    p, hatalar = sayfa
    assert hatalar == []
    metin = p.eval_on_selector_all(".opens", "es=>es.map(e=>e.textContent)")
    assert any("BLG 351E" in m for m in metin), metin


def test_tarayicida_cevrimici_ROZETI(sayfa):
    p, _ = sayfa
    assert p.locator(".chip.online").count() >= 1


def test_tarayicida_DOLU_sube_kirmizi(sayfa):
    """Kontenjanı bitmiş şube "10/10" diye değil, bakılabilir biçimde."""
    p, _ = sayfa
    assert p.locator(".cap.full").count() >= 1
    assert "dolu" in p.locator(".cap.full").first.inner_text()
