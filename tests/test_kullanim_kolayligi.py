"""Faz 18 — kullanım kolaylığı (kullanıcı isteği 22.08.2026).

Üç istek:
  1. Ders önerisinde AÇILIŞTA gösterilen kip "N. dönem + alttan" olsun.
  2. "Başvurabilir miyim" bölümü küçülsün; ayrıntı açılır pencereye ("ÇAP
     planları") taşınsın.
  3. Sayfa on bölüm uzunluğunda — gezinmek kolaylaşsın.

★ Hepsinin ortak riski aynı: bir şeyi GİZLERKEN erişilemez kılmak. Testler
bu yüzden "küçüldü mü" değil, "hâlâ ulaşılabiliyor mu" diye soruyor.
"""
import pytest


@pytest.fixture(autouse=True)
def no_real_waivers(monkeypatch, tmp_path):
    from itucap import declared
    monkeypatch.setattr(declared, "DEFAULT_PATH", tmp_path / "yok.toml")


from itucap import ui as UI


# ------------------------------------------------------- 1. varsayılan kip
HEPSI = {"key": "all", "label": "Tüm adaylar", "note": "", "candidates": [1],
         "schedules": [{"picks": []}]}


def _donemlik(schedules):
    return {"key": "term", "label": "5. dönem + alttan", "note": "",
            "candidates": [1], "schedules": schedules}


def test_donemlik_kip_varsayilan():
    """★ Asıl istek: açılışta dönemlik kip gelsin."""
    assert [m["key"] for m in UI._modes(HEPSI, _donemlik([{"picks": []}]))] \
        == ["term", "all"]


def test_bos_donemlik_kip_one_gecmez():
    """★ Dönemlik havuz program üretemediyse varsayılan yapılmamalı.

    Yapsaydık kullanıcı açılışta bomboş bir ızgara görür ve bunu 'araç bozuk'
    diye okurdu. Doğru ama boş bir varsayılan, dolu bir ekrandan kötüdür."""
    assert [m["key"] for m in UI._modes(HEPSI, _donemlik([]))] == ["all", "term"]


def test_iki_kip_de_her_zaman_duruyor():
    """Sıralama değişiyor, kip KAYBOLMUYOR — öbürüne tek tıkla geçilebilmeli."""
    for scheds in ([{"picks": []}], []):
        assert {m["key"] for m in UI._modes(HEPSI, _donemlik(scheds))} == {"all", "term"}


# --------------------------------------------------------- 2 + 3. şablon
# ★ Veri kurulumunu test_ui.py'den ödünç alıyoruz. İkinci bir kopya tutmak,
# er geç ikisinin ayrışması ve testlerden birinin gerçeği ölçmemesi demek.
from test_ui import _collect, dbs  # noqa: E402,F401


@pytest.fixture()
def data(dbs):
    return _collect(dbs, donem=5)


def test_sablon_basvuru_penceresini_kuruyor(data):
    html = UI.render(data)
    for parca in ("basvuruDlg", "basvuruSummary", "openBasvuru",
                  "renderBasvuruBody", "ÇAP planları", "Yandal planları"):
        assert parca in html, parca


def test_sablon_bolum_cubugunu_kuruyor(data):
    html = UI.render(data)
    for parca in ("secnav", "renderSecNav", "markCurrentSection", "scroll-margin-top"):
        assert parca in html, parca


# ------------------------------------------------------ tarayıcıda gerçek
@pytest.fixture()
def page_ui(data, tmp_path):
    pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import sync_playwright

    dest = UI.write(data, tmp_path / "ui.html")
    try:
        pw = sync_playwright().start()
        browser = pw.chromium.launch()
        p = browser.new_page(viewport={"width": 1400, "height": 1000})
    except Exception as exc:                      # tarayıcı indirilmemiş
        pytest.skip(f"playwright başlatılamadı: {exc}")
    errors = []
    p.on("pageerror", lambda e: errors.append(str(e)))
    p.goto(dest.as_uri())
    yield p, errors
    browser.close()
    pw.stop()


def test_basvuru_bolumu_iki_satira_indi(page_ui):
    """★ Küçülme ölçülebilir olsun: bölümde tablo KALMAMALI."""
    p, errors = page_ui
    assert p.locator("#basvuruSection table").count() == 0
    assert p.locator("#basvuruSummary .basvuruitem").count() >= 1
    assert errors == []


def test_pencere_acilinca_tablo_geliyor(page_ui):
    """★ Gizlemek erişilemez kılmak değil: ayrıntı bir tık uzakta."""
    p, errors = page_ui
    assert p.locator("#basvuruDlg[open]").count() == 0
    p.locator('#basvuruSummary button[data-k="cap"]').click()
    assert p.locator("#basvuruDlg[open]").count() == 1
    assert p.locator("#basvuruDlgTitle").text_content().strip() == "ÇAP planları"
    assert p.locator("#basvuruBody .blockitem").count() >= 1     # şartlar
    assert errors == []


def test_pencerede_sekme_degistirilebiliyor(page_ui):
    p, errors = page_ui
    p.locator('#basvuruSummary button[data-k="yandal"]').click()
    assert p.locator("#basvuruDlgTitle").text_content().strip() == "Yandal planları"
    p.locator('#basvuruTabs .tab[data-k="cap"]').click()
    assert p.locator("#basvuruDlgTitle").text_content().strip() == "ÇAP planları"
    assert errors == []


def test_pencere_kapaniyor(page_ui):
    p, _ = page_ui
    p.locator('#basvuruSummary button[data-k="cap"]').click()
    p.locator("#basvuruDlg [data-close]").first.click()
    assert p.locator("#basvuruDlg[open]").count() == 0


def test_bolum_cubugu_yalniz_ACIK_bolumleri_gosteriyor(page_ui):
    """★ Hiçbir yere gitmeyen bağlantı, olmayan bağlantıdan kötüdür."""
    p, errors = page_ui
    baglar = [a.get_attribute("href")[1:] for a in p.locator("#secnav a").all()]
    assert baglar, "çubuk boş"
    for hedef in baglar:
        assert p.locator(f"#{hedef}").count() == 1
        assert p.locator(f"#{hedef}").is_visible()
    assert errors == []


def test_bolum_cubugu_kaydiriyor(page_ui):
    """Son bağlantıyı SEÇMİYORUZ: sayfa sonunda bölüm zaten yukarı çıkamaz,
    test o zaman kaydırmayı değil sayfa boyunu ölçerdi."""
    p, errors = page_ui
    baglar = p.locator("#secnav a")
    i = 2 if baglar.count() > 3 else 1
    hedef = baglar.nth(i).get_attribute("href")[1:]
    once = p.locator(f"#{hedef}").bounding_box()["y"]
    baglar.nth(i).click()
    p.wait_for_timeout(800)                      # smooth scroll
    sonra = p.locator(f"#{hedef}").bounding_box()["y"]
    assert sonra < once and sonra < 200, f"{once} -> {sonra}"
    assert errors == []


def test_cubuk_kaydirinca_ekranda_kaliyor(page_ui):
    """★ `position:sticky` sessizce bozulur: bir üst kapsayıcıya `overflow`
    eklendiği anda çalışmayı bırakır ve kimse fark etmez."""
    p, errors = page_ui
    p.mouse.wheel(0, 1500)
    p.wait_for_timeout(300)
    kutu = p.locator("#secnav").bounding_box()
    assert kutu["y"] < 10, f"çubuk kaydı: {kutu['y']}"
    assert errors == []


def test_cubuk_bulundugun_bolumu_isaretliyor(page_ui):
    p, errors = page_ui
    ilk = p.locator('#secnav a[aria-current="true"]').get_attribute("href")
    p.mouse.wheel(0, 2500)
    p.wait_for_timeout(400)
    assert p.locator('#secnav a[aria-current="true"]').count() == 1
    assert p.locator('#secnav a[aria-current="true"]').get_attribute("href") != ilk
    assert errors == []


def test_acilista_donemlik_kip_secili(page_ui):
    """★ Uçtan uca: sayfa açıldığında basılı kip dönemlik olmalı."""
    p, errors = page_ui
    if p.locator(".modebtn").count() < 2:
        pytest.skip("bu veride tek kip var")
    assert "dönem" in p.locator('.modebtn[aria-pressed="true"]').inner_text()
    assert errors == []
