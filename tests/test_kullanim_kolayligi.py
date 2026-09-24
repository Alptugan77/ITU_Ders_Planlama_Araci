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
    """★ Faz 46: çubuk artık ÇAPA değil GÖRÜNÜM DEĞİŞTİRİCİ.
    `markCurrentSection` (kaydırma anında hangi bölümdeyiz) yerini
    `gorunumAc` aldı."""
    html = UI.render(data)
    for parca in ("secnav", "renderSecNav", "gorunumAc", "acikGorunumler",
                  "scroll-margin-top"):
        assert parca in html, parca
    assert "markCurrentSection" not in html, "eski çapa mantığı repoda kalmış"


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
    p.evaluate("() => gorunumAc('basvuruSection')")
    assert p.locator("#basvuruSection table").count() == 0
    assert p.locator("#basvuruSummary .basvuruitem").count() >= 1
    assert errors == []


def test_pencere_acilinca_tablo_geliyor(page_ui):
    """★ Gizlemek erişilemez kılmak değil: ayrıntı bir tık uzakta."""
    p, errors = page_ui
    p.evaluate("() => gorunumAc('basvuruSection')")
    assert p.locator("#basvuruDlg[open]").count() == 0
    p.locator('#basvuruSummary button[data-k="cap"]').click()
    assert p.locator("#basvuruDlg[open]").count() == 1
    assert p.locator("#basvuruDlgTitle").text_content().strip() == "ÇAP planları"
    assert p.locator("#basvuruBody .blockitem").count() >= 1     # şartlar
    assert errors == []


def test_pencerede_sekme_degistirilebiliyor(page_ui):
    p, errors = page_ui
    p.evaluate("() => gorunumAc('basvuruSection')")
    p.locator('#basvuruSummary button[data-k="yandal"]').click()
    assert p.locator("#basvuruDlgTitle").text_content().strip() == "Yandal planları"
    p.locator('#basvuruTabs .tab[data-k="cap"]').click()
    assert p.locator("#basvuruDlgTitle").text_content().strip() == "ÇAP planları"
    assert errors == []


def test_pencere_kapaniyor(page_ui):
    p, _ = page_ui
    p.evaluate("() => gorunumAc('basvuruSection')")
    p.locator('#basvuruSummary button[data-k="cap"]').click()
    p.locator("#basvuruDlg [data-close]").first.click()
    assert p.locator("#basvuruDlg[open]").count() == 0


def test_bolum_cubugu_yalniz_ACIK_bolumleri_gosteriyor(page_ui):
    """★ Hiçbir yere gitmeyen bağlantı, olmayan bağlantıdan kötüdür.

    ⚠️ Faz 46: hedef bölüm DOM'da var ama yalnız SEÇİLİYKEN görünür.
    "Açık" ölçütü artık `hidden` değil olmak; görünürlük tıklayınca
    doğrulanıyor — ders aynı, kontrol daha sıkı."""
    p, errors = page_ui
    baglar = [a.get_attribute("href")[1:] for a in p.locator("#secnav a").all()]
    assert baglar, "ray boş"
    for hedef in baglar:
        assert p.locator(f"#{hedef}").count() == 1
        assert p.evaluate(f"() => !document.getElementById('{hedef}').hidden")
        p.evaluate(f"() => gorunumAc('{hedef}')")
        assert p.locator(f"#{hedef}").is_visible(), hedef
    assert errors == []


def test_ray_GORUNUM_degistiriyor_KAYDIRMIYOR(page_ui):
    """★★ FAZ 46'NIN ÇEKİRDEĞİ. Eskiden bu test çubuğun KAYDIRDIĞINI
    tutuyordu; ölçüm o davranışın sorunun kendisi olduğunu gösterdi
    (sayfa 7,3 ekran, haftalık program 1825px aşağıda). Artık tıklamak
    sayfayı kaydırmıyor — görünümü değiştiriyor: tek bölüm açık kalıyor."""
    p, errors = page_ui
    baglar = p.locator("#secnav a")
    assert baglar.count() >= 2
    once_id = p.evaluate("() => GORUNUM")
    i = 1 if baglar.nth(0).get_attribute("href")[1:] == once_id else 0
    hedef = baglar.nth(i).get_attribute("href")[1:]
    baglar.nth(i).click()
    p.wait_for_timeout(300)
    assert p.evaluate("() => GORUNUM") == hedef
    assert p.locator(f"#{hedef}").is_visible()
    # Önceki görünüm KAPANDI — sayfa iki bölüm birden taşımıyor.
    assert not p.locator(f"#{once_id}").is_visible()
    # Sayfa tek görünüm uzunluğunda: kaydırılacak bir şey kalmıyor.
    assert p.evaluate("() => document.documentElement.scrollHeight <= innerHeight * 3")
    assert errors == []


def test_cubuk_kaydirinca_ekranda_kaliyor(page_ui):
    """★ `position:sticky` sessizce bozulur: bir üst kapsayıcıya `overflow`
    eklendiği anda çalışmayı bırakır ve kimse fark etmez."""
    p, errors = page_ui
    # ⚠️ Faz 46'da sayfa TEK GÖRÜNÜM uzunluğunda ve test verisi küçük:
    # `.govde` görüntü alanından kısa kalırsa `sticky` HİÇ devreye girmez
    # ve test yapışkanlığı değil veri miktarını ölçer. Ölçülen şey CSS
    # mekanizması olduğu için açık görünüme uzun bir dolgu koyuyoruz.
    p.evaluate("""() => { const el = document.getElementById(GORUNUM);
      const d = document.createElement("div");
      d.id = "olcumDolgusu"; d.style.height = "2400px";
      el.appendChild(d); }""")
    p.wait_for_timeout(200)
    assert p.evaluate(
        "() => document.querySelector('.govde').getBoundingClientRect().height"
        " > innerHeight + 400"), "gövde kaydırılabilir değil"
    p.mouse.wheel(0, 1500)
    p.wait_for_timeout(300)
    # ⚠️ `bounding_box()` sayfa koordinatı veriyor; yapışkanlık GÖRÜNTÜ
    # ALANINA göre ölçülür. Kaydırma miktarını çıkarmak yerine doğrudan
    # tarayıcıya soruyoruz.
    bilgi = p.evaluate("""() => { const n = document.querySelector('#secnav');
      return {tepe: Math.round(n.getBoundingClientRect().top),
              kaydi: Math.round(scrollY)}; }""")
    assert bilgi["kaydi"] > 100, f"sayfa kaymadı: {bilgi}"
    # Faz 46: ray `top:18px` ile yapışık (eski çubuk `top:0` idi).
    assert bilgi["tepe"] < 30, f"ray kaydı: {bilgi}"
    assert errors == []


def test_cubuk_bulundugun_bolumu_isaretliyor(page_ui):
    """⚠️ Faz 46: işaret artık `aria-current="page"` — "bulunduğun sayfa",
    eskiden "true" ("kaydırılan bölüm"). Anlam değişti, öznitelik de."""
    p, errors = page_ui
    isaretli = lambda: p.locator('#secnav a[aria-current="page"]')
    assert isaretli().count() == 1
    ilk = isaretli().get_attribute("href")
    baglar = p.locator("#secnav a")
    i = 1 if baglar.nth(0).get_attribute("href") == ilk else 0
    baglar.nth(i).click()
    p.wait_for_timeout(300)
    assert isaretli().count() == 1, "birden fazla ya da hiç işaret"
    assert isaretli().get_attribute("href") != ilk
    assert errors == []


def test_acilista_donemlik_kip_secili(page_ui):
    """★ Uçtan uca: sayfa açıldığında basılı kip dönemlik olmalı."""
    p, errors = page_ui
    if p.locator(".modebtn").count() < 2:
        pytest.skip("bu veride tek kip var")
    assert "dönem" in p.locator('.modebtn[aria-pressed="true"]').inner_text()
    assert errors == []
