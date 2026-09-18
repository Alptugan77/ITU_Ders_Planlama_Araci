"""Faz 26 — ilk 30 saniye.

> *"ben siteye ilk girdiğimde hâlâ nasıl yapacağımı anlayamayabilirim"*
> — kullanıcı, 24.08.2026

Faz 24 karşılama kartını getirdi ama kart hâlâ üç şeyi yanlış yapıyordu:

1. **Üç adım da zorunlu görünüyordu.** Oysa yalnız BÖLÜM zorunlu; öbür ikisi
   öneriyi iyileştiriyor. "Üç adımda kur" demek, ekranın arkasında duvar
   varmış hissi veriyordu.
2. **Yedi düğme üç iş yapıyordu** (kartta üç "Aç" + kurulum çubuğunda dört).
3. **"Aç" bir eylem adı değil.**

Ve ekranın en görünür yerinde bir dördüncüsü duruyordu: bölüm seçilir
seçilmez **"%0 tamamlandı · kalan zorunlu 44"**. Hakkında hiçbir şey
bilmediğimiz kişiye "hiçbir şey yapmamışsın" demek — kredi tavanında
(Faz 24) düzeltilen hatanın aynısı.
"""
import re

import pytest


@pytest.fixture(autouse=True)
def no_real_waivers(monkeypatch, tmp_path):
    from itucap import declared
    monkeypatch.setattr(declared, "DEFAULT_PATH", tmp_path / "yok.toml")


from itucap import ui as UI                                    # noqa: E402

from test_ui import _collect, dbs                              # noqa: E402,F401


def _bos(dbs, **kw):
    from itucap import config
    con, ucon, sid = dbs
    return UI.collect(con, ucon, sid, config.Settings(), 10, None, **kw)


def _sadece_bolum(dbs, **kw):
    """Bölüm seçilmiş, transkript ve dönem YOK — aracın çalıştığı ilk an."""
    from itucap import config
    con, ucon, sid = dbs
    s = config.Settings(anadal_program="HTAE", second_kind="yok",
                        program_codes=["HTAE"])
    return UI.collect(con, ucon, sid, s, 10, None, **kw)


# ======================================== 1. zorunlu / isteğe bağlı ayrımı
def test_YALNIZ_bolum_zorunlu(dbs):
    """★ Aracın çalışması için tek gereken bölüm. Üçünü de zorunlu göstermek,
    olmayan bir duvar inşa etmekti."""
    adimlar = _bos(dbs)["onboarding"]["steps"]
    zorunlu = [a["key"] for a in adimlar if a["required"]]
    assert zorunlu == ["program"]


def test_bolum_secilince_ARTIK_engellemiyor(dbs):
    o = _sadece_bolum(dbs)["onboarding"]
    assert o is not None                      # kart duruyor (eksik var)
    assert o["blocking"] is False             # ama rapor GİZLENMİYOR


def test_baslik_TEK_ADIM_diyor(dbs):
    html = UI.render(_bos(dbs))
    assert "Hoş geldin — tek adımda başla" in html
    assert "üç adımda kur" not in html.lower()


def test_bolum_secilince_baslik_ARAÇ_CALISIYOR(dbs):
    html = UI.render(_sadece_bolum(dbs))
    assert "Araç çalışıyor — istersen daha da iyileştir" in html


# ============================================== 2. tek birincil eylem
def test_her_adimin_KENDI_eylem_adi_var(dbs):
    """★ "Aç" neyi açtığını söylemiyordu."""
    adimlar = _bos(dbs)["onboarding"]["steps"]
    # ⚠️ Faz 47: SIRA DEĞİŞTİ — dönem, transkriptten önce. Sebebi bağımlılık:
    # dönem biliniyorsa "Plandan işaretle" geçmiş dönemlerin zorunlularını
    # ÖNERİ olarak tikliyor; ters sırada o öneri yapılamıyor.
    assert [a["cta"] for a in adimlar] == ["Bölümünü seç", "Dönemi seç",
                                           "Dersleri gir"]
    assert all(a["cta"] != "Aç" for a in adimlar)


def test_siradaki_adim_IKI_KEZ_sunulmuyor(dbs):
    """⚠️ Büyük düğme zaten sıradaki adım; satırda tekrarlamak "hangisine
    basacağım" sorusunu geri getiriyordu."""
    html = UI.render(_bos(dbs))
    govde = re.search(r"const stepHTML = \(s, kilitli\) => `(.*?)`;", html, re.S).group(1)
    assert "s !== sonraki" in html
    assert "şimdi ↑" in govde


def test_kurulum_cubugu_karsilama_sirasinda_GIZLI(dbs):
    """★ Aynı üç işi yapan dört düğme daha — "yedi düğme üç iş" karmaşası."""
    css = re.search(r"<style>(.*?)</style>", UI.render(_bos(dbs)), re.S).group(1)
    kural = re.search(r"body\.kurulum[^{]*#setupbar[^{]*\{[^}]*\}", css) \
        or re.search(r"body\.kurulum #setupbar,\s*\n?[^{]*\{[^}]*\}", css)
    assert kural, "body.kurulum #setupbar kuralı yok"


# =================================================== 3. kilitli adımlar
def test_sirasi_gelmemis_adim_KAPALI(dbs):
    """★ Tıklanınca çıkmaza düşen bir düğme, olmayan bir düğmeden kötü."""
    html = UI.render(_bos(dbs))
    assert "disabled title='Önce bölümünü seç'" in html
    assert ".step.kilit" in html


def test_bolum_secilince_KILIT_aciliyor(dbs):
    html = UI.render(_sadece_bolum(dbs))
    assert "const acik    = zorunlu.every(s => s.done)" in html


# ============================== 4. transkript yokken ilerleme İDDİA EDİLMİYOR
def test_transkriptsiz_panel_YUZDE_gostermiyor(dbs):
    """★★ Faz 26'nın en görünür düzeltmesi. Bölüm seçilir seçilmez
    "%0 tamamlandı · kalan zorunlu 44" yazıyordu."""
    html = UI.render(_sadece_bolum(dbs))
    assert "İlerleme bilinmiyor" in html
    assert 'bilinmiyor ? "—" : "%" + p.percent' in html


def test_transkriptsiz_sayilar_PLANIN_TAMAMI_diye_etiketleniyor(dbs):
    """⚠️ Sayıyı gizlemek de olmaz: plan büyüklüğü gerçek bir bilgi.
    Ama "kalan zorunlu 44" ile "zorunlu ders 44" farklı iddialar."""
    html = UI.render(_sadece_bolum(dbs))
    assert "senin kalanın değil" in html
    assert 'bilinmiyor ? "zorunlu ders" : "kalan zorunlu"' in html


def test_transkript_VARKEN_yuzde_geri_geliyor(dbs):
    """⚠️ Koşullu yapmak, gerçekten veri varken bilgiyi kaybetmemeli."""
    from itucap import student as S
    con, ucon, sid = dbs
    con.execute("UPDATE course SET credits=3.0 WHERE code='GEO 303E'")
    con.commit()
    S.add_entries(ucon, sid, [S.make_entry("GEO 303E", "AA")])
    ucon.commit()
    data = _collect(dbs)
    assert data["load"]["noTranscript"] is False


def test_bilinmiyor_uyarisinda_COZUM_dugmesi_var(dbs):
    """Sorunu söyleyip çözümü söylememek, kullanıcıyı arama işine sokar."""
    html = UI.render(_sadece_bolum(dbs))
    assert 'data-setup="plan"' in html


# ============================== 5. başlık altı: önce ne olduğu, sonra sayılar
def test_ilk_satir_ARACIN_NE_YAPTIGINI_soyluyor(dbs):
    """★ "3417 açık şube · dönem yükü sınırı: transkript girilince" siteye
    ilk giren için bağlamı olmayan bir jargon."""
    html = UI.render(_bos(dbs))
    assert "çakışmasız haftalık program kurar" in html


def test_kurulumdan_sonra_SAYILAR_geri_geliyor(dbs):
    """Kurulum bitince bakılan şey sayılar."""
    html = UI.render(_bos(dbs))
    assert "DATA.onboarding && DATA.onboarding.blocking" in html
    assert "açık şube" in html


# ===================================== 6. kurulumdan sonra ne yapabilirsin
def test_sonraki_adim_seridi_var(dbs):
    html = UI.render(_collect(dbs))
    assert 'id="sonraki"' in html and "function renderSonraki()" in html
    assert "Programın hazır. Şimdi:" in html


def test_sonraki_serit_KAPATILABILIR(dbs):
    """Kalıcı bir "şunu yap" şeridi, ikinci ziyarette gürültüdür."""
    html = UI.render(_collect(dbs))
    assert 'localStorage_set("sonrakiKapali"' in html


def test_karsilama_ZORUNLU_adim_eksikken_kapatilamiyor(dbs):
    """⚠️ Bölüm seçilmemişken şeridi gizlemek, kullanıcıyı boş ekranda
    bırakırdı — gösterilecek doğru bir rapor yok."""
    html = UI.render(_bos(dbs))
    assert "if(!O.blocking && localStorage_get(\"heroKapali\"))" in html
    govde = re.search(r"\$\{sonraki && LIVE \? `(.*?)` : \"\"\}", html, re.S).group(1)
    assert "acik ?" in govde              # kapatma düğmesi yalnız `acik` iken


def test_localStorage_erisimi_SARILI(dbs):
    """⚠️ Gizli sekmede / site verisi engelliyken `localStorage` ERİŞİLDİĞİNDE
    bile hata fırlatıyor. Tercih kaybolabilir ama sayfa çalışmalı."""
    html = UI.render(_collect(dbs))
    for fn in ("localStorage_get", "localStorage_set"):
        govde = re.search(rf"function {fn}\(.*?\)\{{(.*?)\n\}}", html, re.S).group(1)
        assert "try{" in govde and "catch" in govde


# ================================================ 7. sayfa hâlâ ayrışıyor
def test_sayfanin_JS_i_AYRISIYOR(dbs, tmp_path):
    import shutil
    import subprocess

    node = shutil.which("node")
    if not node:
        pytest.skip("node yok")
    for ad, data in (("bos", _bos(dbs)), ("bolum", _sadece_bolum(dbs))):
        betik = re.search(r"<script>(.*?)</script>", UI.render(data), re.S).group(1)
        p = tmp_path / f"{ad}.mjs"
        p.write_text(betik, encoding="utf-8")
        r = subprocess.run([node, "--check", str(p)], capture_output=True, text=True)
        assert r.returncode == 0, (ad, r.stderr[:800])
