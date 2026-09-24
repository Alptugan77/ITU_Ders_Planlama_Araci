"""Faz 27 — arayüz: tercihler, puan kırılımı, karşılaştırma, yazdırma, klavye.

En ağırı ilki. **Tercihler YUMUŞAK**: motor önce çalışan programları bulur,
sonra tercihe en uygununu öne alır. Sert kısıt yapmak, gerçek veride kayıt
edilebilir tek programı imkânsız gösterebilirdi — 14 ÇAP dersinden yalnız
2–3'ü bir dönemde alınabiliyor.

İkinci ağırlık, ilk denememin BAŞARISIZ olması: tercihi ayrı bir sıralama
anahtarı yaptım, ölçtüm, hiçbir şeyi değiştirmedi. `blocking_cost` bir float
ve neredeyse hiç eşitlenmiyor; ikinci anahtara sıra hiç gelmiyordu. Aynı
ölçekte TOPLANINCA çalışıyor. `test_tercih_SUBE_SECIMINI_degistiriyor` tam
olarak bunu kilitliyor.
"""
import re

import pytest


@pytest.fixture(autouse=True)
def no_real_waivers(monkeypatch, tmp_path):
    from itucap import declared
    monkeypatch.setattr(declared, "DEFAULT_PATH", tmp_path / "yok.toml")


from itucap import recommend as REC                            # noqa: E402
from itucap import ui as UI                                    # noqa: E402

from test_ui import _collect, dbs                              # noqa: E402,F401


def _sec(crn, gun, baslangic, *, hoca=None, online=False, kampus=None):
    m = REC.Meeting(gun, baslangic, baslangic + 90, None, "X", kampus)
    return REC.Section(crn, "X 101", hoca, 30, 0, (m,),
                       "Virtual (Online)" if online else "Physical (Face to face)")


def _cand(code="X 101", sections=(), **kw):
    varsayilan = dict(course=code, name="", role="ANADAL", ects=5.0, credits=3.0,
                      unlocks=0, tier=0, critical=False, required=True,
                      sections=list(sections))
    varsayilan.update(kw)
    return REC.Candidate(**varsayilan)


# ================================================== 1. tercih = YUMUŞAK
def test_tercih_yoksa_puan_DEGISMIYOR():
    c = _cand(sections=[_sec("1", 1, 510)])
    REC.score_all([c])
    s = REC.Schedule([REC.Pick(c, c.sections[0])], None)
    assert s.pref_delta == 0.0 and s.score == s.base_score


def test_erken_ders_PUANI_dusuruyor():
    c = _cand(sections=[_sec("1", 1, 510)])          # 08:30
    REC.score_all([c])
    t = REC.Preferences(en_erken=630)                # 10:30'dan önce istemiyorum
    s = REC.Schedule([REC.Pick(c, c.sections[0])], t)
    assert s.pref_delta < 0
    assert "erken" in " ".join(s.pref_reasons())


def test_bos_gun_ihlali_SEBEBIYLE_yaziliyor():
    """Sessiz bir eksi puan, "neden bu program önerildi" sorusunu
    cevaplanamaz bırakırdı."""
    c = _cand(sections=[_sec("1", 5, 780)])
    REC.score_all([c])
    s = REC.Schedule([REC.Pick(c, c.sections[0])], REC.Preferences(bos_gunler=(5,)))
    assert s.pref_delta < 0 and s.pref_reasons()


def test_tercih_KRITIK_YOLU_ezemiyor():
    """★★ Tercih ağırlıkları, ders ağırlıklarının çok altında tutuluyor.
    "Sabah istemiyorum" yüzünden ÇAP'ın kritik yolundaki bir ders programdan
    düşerse, araç kullanıcıya bir dönem kaybettirir."""
    assert max(abs(v) for v in REC.TERCIH_AGIRLIK.values()) < REC.WEIGHTS["scarcity"]
    assert max(abs(v) for v in REC.TERCIH_AGIRLIK.values()) < REC.WEIGHTS["cap_role"]
    assert max(abs(v) for v in REC.TERCIH_AGIRLIK.values()) < REC.WEIGHTS["critical"]


def test_bos_hoca_parcasi_HER_ADI_eslestirmiyor():
    """⚠️ Boş dizge her adın içinde geçer; süzülmezse tüm şubeler
    "istediğin hoca" sayılırdı."""
    assert REC._hoca_eslesir("Feza Buzluca", ("",)) is False
    assert REC._hoca_eslesir("Feza Buzluca", ("buzluca",)) is True
    assert REC._hoca_eslesir(None, ("buzluca",)) is False


def test_ilan_edilmemis_hoca_HICBIR_tercihe_uymuyor():
    """3417 şubenin 887'sinde hoca "-" — ne artı ne eksi almalı."""
    t = REC.Preferences(istenen_hocalar=("buzluca",), istenmeyen_hocalar=("ali",))
    assert REC.sube_tercih_puani(_sec("1", 1, 780, hoca=None), t) == 0


# ========================= 2. ★★ tercih ŞUBE SEÇİMİNİ değiştiriyor mu
def test_tercih_SUBE_SECIMINI_degistiriyor():
    """★★ Faz 27'nin asıl işi ve ilk denememin başarısız olduğu yer.

    Aynı dersin 08:30 ve 14:30 şubesi varken "sabah istemiyorum" seçili
    kullanıcıya yine 08:30 veriliyordu: tercih AYRI bir sıralama anahtarıydı
    ve `blocking_cost` (float) neredeyse hiç eşitlenmediği için ikinci
    anahtara sıra hiç gelmiyordu."""
    # ⚠️ CRN'ler bilerek "a-" / "b-": tercih yokken sıralama son anahtara
    # (CRN) düşüyor ve "a-sabah" kazanıyor. Böylece tercihin şubeyi
    # ÇEVİRDİĞİ tek değişkenle gösteriliyor.
    c = _cand(sections=[_sec("a-sabah", 1, 510), _sec("b-ogleden", 1, 870)])
    REC.score_all([c])
    tercihsiz = REC.build_schedules([c], max_load=10, limit=1)
    assert tercihsiz[0].picks[0].section.crn == "a-sabah"
    tercihli = REC.build_schedules([c], max_load=10, limit=1,
                                   prefs=REC.Preferences(en_erken=630))
    assert tercihli[0].picks[0].section.crn == "b-ogleden"


def test_tercih_DEGERLI_DERSI_dusurmuyor():
    """⚠️ Tercih, ileriye bakış maliyetiyle AYNI ÖLÇEKTE toplanıyor ama
    ders puanları (40–100) tercih ağırlıklarının (≤12) çok üstünde.
    Sabah şubesi tek seçenekse ders yine programda kalmalı."""
    c = _cand(sections=[_sec("tek-sabah", 1, 510)], required=True)
    REC.score_all([c])
    prog = REC.build_schedules([c], max_load=10, limit=1,
                               prefs=REC.Preferences(en_erken=630))
    assert prog and prog[0].picks[0].section.crn == "tek-sabah"
    assert prog[0].pref_delta < 0          # uymuyor AMA gösteriliyor


def test_cevrimici_tercihi_SUBE_seciyor():
    c = _cand(sections=[_sec("yuz", 1, 780), _sec("online", 1, 780, online=True)])
    REC.score_all([c])
    prog = REC.build_schedules([c], max_load=10, limit=1,
                               prefs=REC.Preferences(cevrimici_tercih=True))
    assert prog[0].picks[0].section.crn == "online"


def test_istenmeyen_hoca_SUBE_degistiriyor():
    c = _cand(sections=[_sec("a", 1, 780, hoca="Ali Veli"),
                        _sec("b", 1, 780, hoca="Ayşe Yılmaz")])
    REC.score_all([c])
    prog = REC.build_schedules([c], max_load=10, limit=1,
                               prefs=REC.Preferences(istenmeyen_hocalar=("ali veli",)))
    assert prog[0].picks[0].section.crn == "b"


# ============================================== 3. ayar ↔ motor çevirisi
def test_ayar_TEK_YERDE_cevriliyor():
    """⚠️ Ayar alanları ile motorun alanları ayrı adlarda. İki yerde
    çevirmek, birinin unutulduğu sessiz bir hataya açık olurdu."""
    from itucap import config
    s = config.Settings(tercih_en_erken=630, tercih_bos_gunler=[5],
                        tercih_kampus_degisimi=True, tercih_cevrimici=True,
                        tercih_istenen_hocalar=["Buzluca"],
                        tercih_istenmeyen_hocalar=["X"])
    t = s.preferences()
    assert t.en_erken == 630 and t.bos_gunler == (5,)
    assert t.kampus_degisimi_istemiyorum and t.cevrimici_tercih
    assert t.istenen_hocalar == ("Buzluca",) and t.var_mi


def test_gecersiz_gun_SESSIZCE_atiliyor():
    """9. gün diye bir şey yok; kalanı bozmadan düşürülüyor."""
    from itucap import config
    t = config.Settings(tercih_bos_gunler=[1, 9, 0, 5]).preferences()
    assert t.bos_gunler == (1, 5)


def test_bes_gunun_besi_REDDEDILIYOR(tmp_path, monkeypatch):
    """Anlamsız bir istek: sessizce kabul edip sonucu bozmuyoruz."""
    from itucap import config, server as SRV
    monkeypatch.setattr(config, "ROOT", tmp_path)
    (tmp_path / "config").mkdir()
    st = SRV.State.__new__(SRV.State)
    with pytest.raises(ValueError):
        SRV.State.save_prefs(st, {"bosGunler": [1, 2, 3, 4, 5]})


def test_gecersiz_saat_REDDEDILIYOR(tmp_path, monkeypatch):
    from itucap import config, server as SRV
    monkeypatch.setattr(config, "ROOT", tmp_path)
    (tmp_path / "config").mkdir()
    st = SRV.State.__new__(SRV.State)
    with pytest.raises(ValueError):
        SRV.State.save_prefs(st, {"enErken": 5000})


def test_tercih_arayuzde_YUMUSAK_oldugunu_yaziyor(dbs):
    """★ Kullanıcı "istemiyorum dedim ama yine koydu" diye aracı hatalı
    sanmasın."""
    html = UI.render(_collect(dbs))
    assert "eleme değil" in html and "sıralama" in html
    assert "uymayan tek bir uygulanabilir program varsa bu program yine de gösterilir" in html
    assert "eleme için değil sıralama için" in html      # program özetindeki ipucu


# ================================================ 4. puan kırılımı §3.1
def test_kirilim_toplami_PUANLA_tutuyor():
    """⚠️ Ayrışırlarsa arayüz yalan söyler."""
    c = _cand(sections=[_sec("1", 1, 510)], critical=True, unlocks=3, role="CAP")
    REC.score_all([c])
    assert round(sum(p["points"] for p in c.parts), 1) == c.score


def test_sifir_katki_KAYDEDILMIYOR():
    """Listeyi "bu terim seni etkilemedi" satırlarıyla doldurmak, gerçekten
    etkileyenleri gizler."""
    c = _cand(sections=[_sec("1", 1, 510)], critical=False, unlocks=0)
    REC.score_all([c])
    assert all(p["points"] for p in c.parts)


def test_kirilim_BUYUKTEN_kucuge():
    c = _cand(sections=[_sec("1", 1, 510)], critical=True, unlocks=3, role="CAP")
    REC.score_all([c])
    mutlak = [abs(p["points"]) for p in c.parts]
    assert mutlak == sorted(mutlak, reverse=True)


def test_kirilim_arayuze_CIKIYOR(dbs):
    data = _collect(dbs)
    assert all("parts" in c for c in data["candidates"])
    html = UI.render(data)
    assert "function puanKirilimi(cand)" in html
    assert "neden?" in html


def test_puanin_ANLAMI_yaziyor(dbs):
    """★ "Yüksek puan = daha iyi ders" YANLIŞ okuma. Puan, bu dönem
    kaçırmanın maliyetini ölçüyor."""
    html = UI.render(_collect(dbs))
    assert "bu dönem alınmamasının maliyetinin yüksek" in html


def test_eksi_katki_da_GORUNUYOR(dbs):
    """⚠️ Çubuk mutlak değere göre ölçekleniyor; yoksa "puanı düşüren şey"
    hiç görünmezdi (ertelenebilir ders −20)."""
    html = UI.render(_collect(dbs))
    assert ".puansatir.eksi" in html
    assert "Math.abs(p.points)" in html


# ============================================== 5. karşılaştırma §3.4
def test_karsilastirma_SEKIL_ustunden(dbs):
    """★ Ders kodlarını üç kolonda dökmek farkı bulmayı yine kullanıcıya
    bırakırdı — o zaten sekmelerde yapabiliyordu."""
    data = _collect(dbs)
    if not data["schedules"]:
        pytest.skip("fixture'da program yok")
    s = data["schedules"][0]["shape"]
    for anahtar in ("days", "freeDays", "earliest", "latest", "online",
                    "timeless", "gaps"):
        assert anahtar in s, anahtar


def test_saatsiz_ders_BOS_GUN_sayilmiyor(dbs):
    """⚠️ Saati ilan edilmemiş ders hiçbir güne düşmüyor; onu boşluk
    sanmamak için ayrıca sayılıyor."""
    data = _collect(dbs)
    if not data["schedules"]:
        pytest.skip("fixture'da program yok")
    assert isinstance(data["schedules"][0]["shape"]["timeless"], int)


def test_karsilastirma_ORTAK_dersleri_ayikliyor(dbs):
    html = UI.render(_collect(dbs))
    assert "function karsilastirDialog()" in html
    assert "yalnızca <b>farklılıklar</b>" in html


def test_karsilastirma_TEK_oneride_gosterilmiyor(dbs):
    html = UI.render(_collect(dbs))
    assert "M().schedules.length > 1" in html


# ================================================== 6. yazdırma §3.2
def test_yazdirmada_DUGMELER_gizli(dbs):
    html = UI.render(_collect(dbs))
    css = re.search(r"<style>(.*?)</style>", html, re.S).group(1)
    blok = re.search(r"@media print\{(.*?)\n\}", css, re.S).group(1)
    for parca in ("#secnav", "#setupbar", ".toolbar", ".candbar", "dialog"):
        assert parca in blok, parca


def test_yazdirmada_CRN_listesi_var(dbs):
    """Kayıt masasında bakılan şey bu; ekranda pencerede duruyor ama
    yazdırırken pencere açık olmayabilir."""
    html = UI.render(_collect(dbs))
    assert 'id="printCrn"' in html and "function renderPrintCrn()" in html
    assert "#printCrn{display:none}" in html


def test_yazdirilan_listede_VERI_YASI_var(dbs):
    """Kâğıda basılan kontenjan, basıldığı anın değil son tazelemenin."""
    html = UI.render(_collect(dbs))
    govde = re.search(r"function renderPrintCrn\(\)\{(.*?)\n\}", html, re.S).group(1)
    assert "veriYasiMetni()" in govde


# ==================================================== 7. klavye §3.3
def test_klavye_kisayollari_var(dbs):
    html = UI.render(_collect(dbs))
    assert "function candOdakla(i)" in html
    assert 'e.key === "ArrowDown"' in html and 'e.key === "Enter"' in html


def test_kisayol_YAZI_ALANINDA_calismiyor(dbs):
    """⚠️ Arama kutusuna "j" yazan kişi satır atlamamalı."""
    html = UI.render(_collect(dbs))
    assert 'const yaziAlani = t && /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)' in html
    assert 'e.key === "j" && !yaziAlani' in html


def test_kisayol_PENCERE_acikken_calismiyor(dbs):
    """Pencere açıkken ok tuşu arkadaki listeyi gezdirmemeli."""
    html = UI.render(_collect(dbs))
    assert 'if(document.querySelector("dialog[open]")) return;' in html


# ============================================== 8. sayfa hâlâ ayrışıyor
def test_sayfanin_JS_i_AYRISIYOR(dbs, tmp_path):
    import shutil
    import subprocess

    node = shutil.which("node")
    if not node:
        pytest.skip("node yok")
    betik = re.search(r"<script>(.*?)</script>", UI.render(_collect(dbs)), re.S).group(1)
    p = tmp_path / "ui.mjs"
    p.write_text(betik, encoding="utf-8")
    r = subprocess.run([node, "--check", str(p)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[:800]
