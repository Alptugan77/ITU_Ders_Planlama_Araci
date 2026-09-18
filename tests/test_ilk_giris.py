"""Faz 24 — SİTEYE İLK GİREN KİŞİ (kullanıcı isteği 24.08.2026).

    "ders seçim aracı ilk gelen kullanıcılar için biraz karmaşık kalıyor…
     ilk kez siteye giren birisi gözüyle bak, normal bir ders seçim aracı
     olarak da kullanılabilir olması önemli"

Bu dosyanın kilitlediği şey tek cümleyle: **araç, hakkında hiçbir şey
bilmediği kişiye bir şey İDDİA ETMESİN ve onu çıkmaza sokmasın.**

Bulunan dört sınıf hata:

1. Varsayılan bölüm geliştiricinin kendi bölümüydü; siteye ilk giren herkes
   HTAE + BLG raporu görüyordu (`test_varsayilan_bolum_YOK`).
2. Bölüm seçme kutusu alfabetik ilk bölümde açılıyordu — dokunmadan
   kaydeden herkes "AIN" oluyordu (`test_program_secimi_BOS_baslar`).
3. Transkript yokken her eşik ✗ işaretleniyordu; bilinmeyen, düşmüş gibi
   görünüyordu (bkz. `test_basvuru.py`).
4. Karşılama kartındaki adımlar birbirini varsayıyor ama gitmediğinde
   "Plan bulunamadı." gibi çıkmazlara düşüyordu.
"""
import re

import pytest


@pytest.fixture(autouse=True)
def no_real_waivers(monkeypatch, tmp_path):
    from itucap import declared
    monkeypatch.setattr(declared, "DEFAULT_PATH", tmp_path / "yok.toml")


from itucap import ui as UI                                   # noqa: E402
from test_ui import _collect, dbs                             # noqa: E402,F401


def _bos_ayar():
    from itucap import config
    return config.Settings()


def _bos(dbs, **kw):
    """Hiç ayar yapılmamış öğrenci — siteye ilk giren kişi."""
    con, ucon, sid = dbs
    return UI.collect(con, ucon, sid, _bos_ayar(), 10, 20, **kw)


# ------------------------------------------------ 1. varsayılan bölüm yok
def test_varsayilan_bolum_YOK():
    """★★ En pahalı hata buydu.

    `tools/site_kur.py` `settings.toml` dosyasını siteye KOYMUYOR (kişisel).
    Varsayılanlar geliştiricinin bölümleriydi, dolayısıyla yayınlanan sitede
    ilk giren herkes HTAE+BLG için eksiksiz bir rapor görüyordu: haftalık
    ızgara, "%0 tamamlandı, 54 ders kaldı". Hiç seçmediği bir bölümün
    raporu, seçtiği sanılarak."""
    s = _bos_ayar()
    assert s.anadal_program == ""
    assert s.cap_program == "" and s.yandal_program == ""
    assert s.second_kind == "yok"


def test_ayarda_program_yazsa_da_tur_TURETILIYOR(tmp_path):
    """⚠️ Varsayılanı boşaltmanın yan etkisi: `cap_program` yazan ama
    `second_kind` yazmayan eski bir dosyada ÇAP sessizce kaybolurdu."""
    from itucap import config
    p = tmp_path / "s.toml"
    p.write_text('[student]\nanadal_program = "HTAE"\ncap_program = "BLG"\n',
                 encoding="utf-8")
    s = config.Settings.load(p)
    assert s.second_kind == "cap" and s.program_of("cap") == "BLG"


# --------------------------------------------------- 2. karşılama kartı
def test_program_yokken_karsilama_ENGELLEYICI(dbs):
    data = _bos(dbs)
    o = data["onboarding"]
    assert o and o["blocking"] is True
    # ⚠️ Faz 47: dönem transkriptten ÖNCE (kullanıcı isteği 18.09.2026).
    assert [a["key"] for a in o["steps"]] == ["program", "donem", "transkript"]
    assert all(not a["done"] for a in o["steps"])


def test_program_yokken_rapor_bolumleri_GIZLENIYOR(dbs):
    """`body.kurulum` her rapor bölümünü gizliyor: bölüm seçilmeden
    gösterilecek doğru bir şey yok."""
    html = UI.render(_bos(dbs))
    css = re.search(r"<style>(.*?)</style>", html, re.S).group(1)
    kural = re.findall(r"body\.kurulum[^{]*\{[^}]*\}", css)
    assert kural, "body.kurulum kuralı yok"


def test_kurulum_bitince_karsilama_KAYBOLUYOR(dbs):
    """Kalıcı bir 'şunu da yap' şeridi, tamamlanmış kurulumda gürültüdür."""
    from itucap import config, student as S
    con, ucon, sid = dbs
    S.add_entries(ucon, sid, [S.make_entry("GEO 303E", "AA")])
    ucon.commit()
    s = config.Settings(anadal_program="HTAE", cap_program="BLG",
                        second_kind="cap", donem=5,
                        program_codes=["HTAE", "BLG"])
    assert UI.collect(con, ucon, sid, s, 10, 20)["onboarding"] is None


def test_eksik_adim_kalinca_karsilama_DURUYOR_ama_rapor_da_duruyor(dbs):
    """⚠️ İki farklı eksik, iki farklı davranış: bölüm yoksa gösterilecek
    doğru bir şey yok (rapor gizli); dönem eksikse rapor doğru ama eksik
    bilgiyle — o zaman rapor DURUYOR, üstte ne yapılacağı yazıyor."""
    from itucap import config
    con, ucon, sid = dbs
    s = config.Settings(anadal_program="HTAE", cap_program="BLG",
                        second_kind="cap", program_codes=["HTAE", "BLG"])
    o = UI.collect(con, ucon, sid, s, 10, 20)["onboarding"]
    assert o and o["blocking"] is False
    assert [a["done"] for a in o["steps"]][0] is True


def test_karsilama_BOLUM_sayar_plan_degil(dbs):
    """★ `plan` tablosunda her bölümün birden çok sürümü var. Satırı saymak
    "445 bölüm seçebilirsin" gibi okunuyordu; kutuda 127 vardı."""
    con, _, _ = dbs
    data = _bos(dbs)
    beklenen = con.execute("SELECT COUNT(DISTINCT program_code) FROM plan "
                           "WHERE plan_type='lisans'").fetchone()[0]
    assert data["onboarding"]["planCount"] == beklenen


# ------------------------------------------------------ 3. program kutusu
def test_program_secimi_BOS_baslar(dbs):
    """★ Boş seçim GERÇEK bir seçenek olmalı.

    Yoksa liste alfabetik ilk bölümde (AIN) açılıyor ve kutuya hiç
    dokunmadan Kaydet'e basan herkes o bölüme yazılıyor — üstelik seçtiğini
    sanarak."""
    html = UI.render(_bos(dbs))
    assert "— bölümünü seç —" in html


def test_program_kutusunda_ADLAR_da_var(dbs):
    """"AIN" tek başına bir tanım değil; kimse kendi OBS kodunu ezbere
    bilmiyor. Ad da yazınca `select` yazarak-arama'sı ikisine de çalışıyor.

    ★ 24.08.2026 (inceleme C3): adı BİLİNMEYEN program artık "ECN — ECN"
    değil "ECN — (adı katalogda yok)" yazıyor. Sunucu bilinmeyen ada kodu
    koyuyordu; kod bir ad değil ve okuyan kişi adın gerçekten "ECN"
    olduğunu sanıyordu. Ölçüldü: 4 kodun (ECN, SEC, VBA, YZV) `program`
    tablosunda satırı yok."""
    html = UI.render(_collect(dbs))
    assert "adi[c] ? `${c} — ${adi[c]}`" in html
    assert "(adı katalogda yok)" in html
    # Kodu ad diye kabul etmiyor.
    assert "p.name.toUpperCase() !== p.code.toUpperCase()" in html


def test_anadal_listesi_YALNIZ_lisans_plani_olanlar(dbs):
    """★ Aynı ilke ÇAP/yandal listesinde zaten vardı. Anadalda çıkmaz daha
    pahalı: rapor komple boş çıkıyor ve araç bozuk görünüyor."""
    html = UI.render(_collect(dbs))
    assert 's.programs.filter(p => p.plan_type === "lisans")' in html


def test_bos_anadal_KAYDEDILMIYOR(dbs):
    html = UI.render(_collect(dbs))
    assert "Önce anadal bölümünü seç" in html


def test_sunucu_da_bos_anadali_REDDEDIYOR(tmp_path, monkeypatch):
    """Arayüz güvenliği tek başına yetmez — API doğrudan da çağrılabiliyor."""
    from itucap import config, server as SRV
    monkeypatch.setattr(config, "ROOT", tmp_path)
    (tmp_path / "config").mkdir()
    state = SRV.State.__new__(SRV.State)
    with pytest.raises(ValueError):
        SRV.State.save_programs(state, {"anadalProgram": "", "secondKind": "yok"})


# ------------------------------------------- 4. bilinmeyeni bilinen sayma
def test_transkript_yokken_kredi_tavani_IDDIA_EDILMIYOR(dbs):
    """★ GNO 0.00 bir ölçüm değil, veri yokluğu. Üst çubukta
    "dönem yükü sınırı 22 kredi" yazmak, hesaplanmış bir sayı sunmaktı."""
    data = _bos(dbs)
    assert data["load"]["noTranscript"] is True
    html = UI.render(data)
    assert "dönem yükü sınırı: transkript girilince" in html


def test_not_yokken_gizlilik_uyarisi_YAZILMIYOR(dbs):
    """Hiç not girmemiş kişiye "bu dosya notlarını içerir" demek,
    girmediği bir veriyi sızdırdığını sandırıyor. Her yerde tekrarlanan
    uyarı da okunmaz oluyor."""
    html = UI.render(_bos(dbs))
    assert '<span id="gizlilik"></span>' in html
    assert "DATA.load.noTranscript)\n    ? \"\" : \"Bu dosya notlarını içerir" in html


def test_notlar_VARKEN_uyari_geri_geliyor(dbs):
    """⚠️ Uyarıyı koşullu yapmak, gerçekten not varken kaybetmemeli."""
    con, ucon, sid = dbs
    from itucap import student as S
    con.execute("UPDATE course SET credits=3.0 WHERE code='GEO 303E'")
    con.commit()
    S.add_entries(ucon, sid, [S.make_entry("GEO 303E", "AA")])
    ucon.commit()
    data = _collect(dbs)
    assert data["load"]["noTranscript"] is False


# ------------------------------------------------------- 5. çıkmaz yok
def test_plandan_isaretle_program_yokken_YOL_GOSTERIYOR(dbs):
    """★ Karşılamadaki 2. adıma 1. adımı atlayarak tıklayan kişi
    "Plan bulunamadı." görüyordu: ne olduğu, ne yapması gerektiği belli
    olmayan bir çıkmaz."""
    html = UI.render(_collect(dbs))
    assert "Önce bölümünü seç" in html
    assert 'id="goProgram"' in html


def test_ders_ara_dugmesi_YANLIS_ad_degil(dbs):
    """★ "Ders ara" düğmesi GEÇİLEN dersler penceresini açıyordu; ilk giren
    kişi "alacağım dersi arayacağım" diye tıklayıp transkripte düşüyordu."""
    html = UI.render(_collect(dbs))
    assert 'data-setup="dersler">Geçtiğin dersler<' in html
    # ⚠️ "Ders ara" ADI yasak değil — YERİ önemliydi. Kurulum çubuğundaki
    # düğme artık ne yaptığını söylüyor; gerçek katalog aramasının başlığında
    # "Ders ara" yazması doğru (Faz 25/B1).
    assert 'data-setup="dersler">Ders ara<' not in html


# ---------------------------------------------------- 6. aday süzgeci
def test_aday_tablosunda_ARAMA_var(dbs):
    """★ Liste ilk 30'da kesiliyordu ve arama yoktu: 31. sıradaki ders
    arayana YOK görünüyordu."""
    html = UI.render(_collect(dbs))
    assert 'id="candQ"' in html
    assert "function filteredCandidates()" in html


def test_arama_yapilinca_KESME_kalkıyor(dbs):
    """Aradığın ders 40. sıradaysa da gelmeli."""
    html = UI.render(_collect(dbs))
    assert "FILT.q.trim() ? hepsi : hepsi.slice(0, LIMIT)" in html


def test_arama_SIRALAMAYI_degistirmiyor(dbs):
    """⚠️ Eşleşmeye göre yeniden sıralamak, motorun gerekçeli puan sırasını
    sessizce ezerdi. Süzgeç yalnız SÜZÜYOR."""
    html = UI.render(_collect(dbs))
    govde = re.search(r"function filteredCandidates\(\)\{(.*?)\n\}", html, re.S).group(1)
    assert ".sort(" not in govde


def test_iki_ayri_BOS_iki_ayri_cevap(dbs):
    """Süzgeç boşalttıysa çıkış yolu, havuz baştan boşsa sebep."""
    html = UI.render(_collect(dbs))
    assert "süzgece uyan ders yok" in html
    assert "bölümünü ve geçtiğin dersleri girdiğinden emin ol" in html


# --------------------------------------------------- 7. sayfa JS'i AYRIŞIYOR
def test_sayfanin_JS_i_AYRISIYOR(dbs, tmp_path):
    """★ Bu testin varlık sebebi somut bir hata: şablon dizesinin İÇİNE
    yazılan bir HTML yorumunda ters tırnak (`) kullanınca şablon orada
    kapanıyor ve TÜM sayfa betiği ayrışmaz hale geliyor. Sayfa bembeyaz
    açılıyor, hiçbir düğme çalışmıyor.

    Eskiden bu yalnız `test_kademe_baglari` içinde, ilgisiz bir iddianın
    yan etkisi olarak yakalanıyordu — hata mesajı 'çizgiler çizilmedi'
    diyordu. Sözdizimi hatası, sözdizimi testiyle yakalanmalı."""
    import shutil
    import subprocess

    node = shutil.which("node")
    if not node:
        pytest.skip("node yok")
    html = UI.render(_collect(dbs))
    betik = re.search(r"<script>(.*?)</script>", html, re.S).group(1)
    p = tmp_path / "ui.mjs"
    p.write_text(betik, encoding="utf-8")
    r = subprocess.run([node, "--check", str(p)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[:800]


def test_ilk_girise_ait_sayfanin_JS_i_de_AYRISIYOR(dbs, tmp_path):
    """Karşılama kartı ayrı bir dal — kendi şablonu var, kendi hatası olabilir."""
    import shutil
    import subprocess

    node = shutil.which("node")
    if not node:
        pytest.skip("node yok")
    betik = re.search(r"<script>(.*?)</script>", UI.render(_bos(dbs)), re.S).group(1)
    p = tmp_path / "ilk.mjs"
    p.write_text(betik, encoding="utf-8")
    r = subprocess.run([node, "--check", str(p)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[:800]


# ------------------------------------------------- 8. `hidden` gerçekten gizler
def test_hidden_ozniteligi_HER_ZAMAN_gizliyor(dbs):
    """★★ Tarayıcının `[hidden]{display:none}` kuralı en zayıf özgüllükte.
    `display` kuran her sınıf onu eziyordu:

      * `.radios{display:flex}` → gizlenen rol düğmeleri ince bir çizgi
        olarak görünüyordu,
      * `.ghost{display:inline-flex}` → `<button class="ghost" hidden>`
        (ör. "Veriyi tazele") gizlenmesi gereken yerde duruyordu.

    Tek tek yamamak yerine tek kural: `hidden` her zaman gizler."""
    css = re.search(r"<style>(.*?)</style>", UI.render(_collect(dbs)), re.S).group(1)
    css = re.sub(r"/\*.*?\*/", " ", css, flags=re.S)
    assert re.search(r"\[hidden\]\s*\{[^}]*display\s*:\s*none\s*!important", css)


def test_display_kuran_sinif_hidden_i_EZEMEZ(dbs, tmp_path):
    """Kuralı yazmak yetmez — tarayıcıda ölç."""
    pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import sync_playwright

    dest = UI.write(_collect(dbs), tmp_path / "ui.html")
    try:
        pw = sync_playwright().start()
        tarayici = pw.chromium.launch()
        p = tarayici.new_page()
    except Exception as exc:
        pytest.skip(f"playwright başlatılamadı: {exc}")
    try:
        p.goto(dest.as_uri())
        p.wait_for_timeout(400)
        gorunur = p.evaluate("""() => [...document.querySelectorAll('[hidden]')]
            .filter(e => e.offsetParent !== null || e.getClientRects().length)
            .map(e => e.id || e.className)""")
        assert gorunur == [], gorunur
    finally:
        tarayici.close(); pw.stop()


# ---------------------------------------------- 9. öğretim üyesi + TR arama
@pytest.mark.parametrize("ham,beklenen", [
    ("Mehmet Özkan", "Mehmet Özkan"),
    ("  Ayşe Yıldız ", "Ayşe Yıldız"),
    ("-", ""), ("--", ""), ("", ""), (None, ""), ("TBA", ""), ("belirsiz", ""),
])
def test_ilan_edilmemis_hoca_BOS_doner(ham, beklenen):
    """★ OBS ilan edilmemiş hocayı "-" yazıyor: 3417 şubenin 887'si.
    Onu ad diye basmak "hocası tire" demek olurdu."""
    assert UI._hoca(ham) == beklenen


def test_hoca_sube_secme_penceresinde_GORUNUYOR(dbs):
    """Şube seçerken bakılan iki şeyden biri (öbürü saat). Veri motorda
    taşınıyordu ama arayüze hiç çıkmıyordu."""
    data = _collect(dbs)
    assert all("instructor" in s
               for c in data["candidates"] for s in c["sections"])
    assert 'class="hoca"' in UI.render(data)


def test_TR_arama_icin_obur_dilin_adi_TASINIYOR(dbs):
    """★ İngilizce programın dersi katalogda İngilizce adla duruyor
    ("MAT 271E — Probability"); Türkçe düşünen öğrenci "olasılık" arayınca
    hiçbir şey bulamıyordu."""
    con, ucon, sid = dbs
    con.execute("INSERT INTO course(code,name,ects) VALUES ('BLG 212','Mikroişlemciler',7.0)")
    con.commit()
    data = _collect(dbs)
    c = [x for x in data["candidates"] if x["course"] == "BLG 212E"][0]
    assert c["altName"] == "Mikroişlemciler"
    assert "(c.altName || \"\")" in UI.render(data)


def test_esi_OLMAYAN_derste_ad_UYDURULMUYOR(dbs):
    """⚠️ Program kodlarında körlemesine son harfi atmak var olmayan bir
    programa yönlendiriyordu (HTAE/HTA, Faz 20). Derste de varlık kontrolü
    şart: eşi yoksa alan boş."""
    data = _collect(dbs)
    c = [x for x in data["candidates"] if x["course"] == "GEO 303E"][0]
    assert c["altName"] == ""


def test_ayni_ad_iki_dilde_ayni_ise_TEKRARLANMIYOR(dbs):
    """Katalogda "AKM 204E — Fluid Mechanics" ile "AKM 204 — Fluid Mechanics"
    gibi ADI AYNI çiftler var; aynı metni ikinci kez taşımanın anlamı yok."""
    con, ucon, sid = dbs
    con.execute("INSERT INTO course(code,name,ects) VALUES "
                "('GEO 303','Kadastro',3.0)")            # E'li ile AYNI ad
    con.commit()
    data = _collect(dbs)
    c = [x for x in data["candidates"] if x["course"] == "GEO 303E"][0]
    assert c["altName"] == ""
