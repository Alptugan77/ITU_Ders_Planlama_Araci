"""Faz 25/B–C — normal ders seçim aracı eksikleri ve kayıt günü.

B1 plan dışı ders · B2 yedek plan · B3 takvim · B4 paylaşılabilir bağlantı ·
B5 hocaya göre arama · C1 kayıt öncesi kontrol · C3 açılmamış ders uyarısı.

Bu dosyanın ana kaygısı B1'de: **plan dışı ders bir şartı DOLDURMAZ.**
Kredisi yüke ve çakışmaya girer (kayıtta da öyle), ama ilerleme yüzdesine
ve slot doluluğuna girmez. Karıştırmak, alınmamış bir şartı alınmış
göstermek olurdu — projenin en pahalı hata türü.
"""
import re

import pytest


@pytest.fixture(autouse=True)
def no_real_waivers(monkeypatch, tmp_path):
    from itucap import declared
    monkeypatch.setattr(declared, "DEFAULT_PATH", tmp_path / "yok.toml")


from itucap import ui as UI                                     # noqa: E402

from test_ui import _collect, dbs                               # noqa: E402,F401


def _state(dbs, **ayar):
    """Sunucu durumunu fixture veritabanlarıyla kur (ağ yok).

    ⚠️ `settings()` gerçek `settings.toml`'u okur; testte geliştiricinin
    kendi bölümlerini almasın diye açıkça veriyoruz."""
    from itucap import config, server as SRV
    con, ucon, sid = dbs
    st = SRV.State.__new__(SRV.State)
    st.con, st.ucon, st.student_id = con, ucon, sid
    s = config.Settings(anadal_program=ayar.pop("anadal", "HTAE"),
                        cap_program=ayar.pop("cap", "BLG"),
                        second_kind="cap", program_codes=["HTAE", "BLG"], **ayar)
    st.settings = lambda: s
    return st


# =========================================================== B1. plan dışı
def test_katalog_aramasi_KOD_ve_AD(dbs):
    st = _state(dbs)
    kodla = st.search_catalog("BLG 212")
    assert "BLG 212E" in {i["course"] for i in kodla["items"]}
    adla = st.search_catalog("mikro")
    assert "BLG 212E" in {i["course"] for i in adla["items"]}


def test_katalog_aramasi_TEK_HARFTE_calismiyor(dbs):
    """Tek harf 3417 şubenin yarısını döndürür; sonuç değil gürültü olur."""
    out = _state(dbs).search_catalog("b")
    assert out["items"] == [] and out["note"]


def test_katalog_ACIK_SUBESI_OLMAYANI_listelemiyor(dbs):
    """★ Seçtirip sonra "şubesi yok" demek, seçim sunmamaktan kötü —
    Faz 20'deki ÇAP listesi kuralının aynısı."""
    con, ucon, sid = dbs
    con.execute("INSERT INTO course(code,name,ects) VALUES ('ZZZ 101','Hayalet',3.0)")
    con.commit()
    out = _state(dbs).search_catalog("hayalet")
    assert out["items"] == []


def test_katalog_kesmesi_SESSIZ_degil(dbs, monkeypatch):
    """"40 sonuç" ile "40+ sonuç" farklı şeyler; sessizce kesmek
    "hepsi bu" demek olurdu."""
    st = _state(dbs)
    monkeypatch.setattr(type(st), "KATALOG_LIMIT", 1)
    out = st.search_catalog("SEC")            # fixture'da üç SEC dersi var
    assert out["truncated"] is True and len(out["items"]) == 1


def test_plandaki_ders_PLAN_DISI_isaretlenmiyor(dbs):
    """Rol yanlış olursa plan dersi "şart doldurmaz" diye gösterilirdi."""
    out = _state(dbs).search_catalog("BLG 212")
    rol = {i["course"]: i["role"] for i in out["items"]}
    assert rol.get("BLG 212E") in {"ANADAL", "CAP", "YANDAL"}, rol


def test_plan_disi_ders_gercekten_PLAN_DISI(dbs):
    con, ucon, sid = dbs
    con.execute("INSERT INTO course(code,name,credits,ects) "
                "VALUES ('FEL 101','Felsefeye Giriş',3.0,4.0)")
    con.execute("INSERT INTO lesson(crn,course_code,capacity,enrolled) "
                "VALUES ('900','FEL 101',30,0)")
    con.commit()
    out = _state(dbs).search_catalog("felsefe")
    assert [i["role"] for i in out["items"]] == ["PLAN_DISI"]


def test_ders_subeleri_CRN_ile_AYNI_bicimde(dbs):
    """★ Arayüzün tek bir ekleme yolu var (`injectSections`). İki ayrı
    biçim, zamanla ayrışan iki ayrı hata demek olurdu."""
    st = _state(dbs)
    a = st.course_sections("BLG 212E")["found"]
    b = st.resolve_crns(["100", "101"])["found"]
    assert {x["crn"] for x in a} == {x["crn"] for x in b}
    assert set(a[0]) == set(b[0])


def test_sube_bilgisinde_HOCA_ve_CEVRIMICI_var(dbs):
    con, ucon, sid = dbs
    con.execute("UPDATE lesson SET instructor='Feza Buzluca', "
                "teaching_method='Virtual (Online)' WHERE crn='100'")
    con.commit()
    s = [x for x in _state(dbs).course_sections("BLG 212E")["found"]
         if x["crn"] == "100"][0]
    assert s["instructor"] == "Feza Buzluca" and s["online"] is True


def test_plan_disi_HICBIR_SLOTU_doldurmuyor(dbs):
    """★★ B1'in tek kuralı. Şablonda `slotId: 0` ve `pool: ""` sabit."""
    html = UI.render(_collect(dbs))
    govde = re.search(r"function injectSections\(bulunan\)\{(.*?)\n\}", html, re.S).group(1)
    assert "slotId: 0" in govde and 'pool: ""' in govde
    assert "plan dışı — hiçbir şartı doldurmaz" in govde


def test_plan_disi_kredi_ozette_AYRICA_yaziyor(dbs):
    """Kredi yüke girer ama ilerleme yüzdesi artmaz. İkisi aynı satırda
    yazmazsa kullanıcı farkı hataya yorar."""
    html = UI.render(_collect(dbs))
    assert "plan dışı</b> — yüke sayılır, şart doldurmaz" in html


def test_salt_okunur_kopyada_katalog_KAPALI(dbs):
    """Statik dosyada sunucu yok; düğme "çalışmıyor" demek yerine niye
    çalışmadığını söylüyor."""
    html = UI.render(_collect(dbs))
    assert "Bu kopya salt okunur" in html


# ============================================== salt okunur uçlar hızlı olsun
def test_katalog_ucu_TAM_DURUMU_yeniden_kurmuyor(dbs):
    """★ Ölçüm: `snapshot()` bütün raporu kuruyor, tek çağrı ~1.5 sn.
    Harf başına arama yapan bir uç için kullanılamaz."""
    from itucap import server as SRV
    assert "/api/katalog" in SRV.READ_ONLY_PATHS
    assert "/api/ders" in SRV.READ_ONLY_PATHS


def test_YAZAN_uclar_salt_okunur_listesinde_DEGIL():
    """⚠️ Yazan bir ucu bu listeye koymak, kullanıcının değişikliği yaptığı
    ama ekranda göremediği sessiz bir hata üretir."""
    from itucap import server as SRV
    yazanlar = {"/api/programs", "/api/donem", "/api/transcript",
                "/api/picks", "/api/maxload", "/api/mesgul", "/api/watch"}
    assert not (yazanlar & SRV.READ_ONLY_PATHS)


# ============================================================ B2. yedek plan
def test_yedek_plan_CAKISMAYI_soyluyor(dbs):
    """Eskiden yalnız "öbür CRN'ler" listeleniyordu; hangisinin çakıştığı
    yazmıyordu. Kayıt gününde lazım olan cümle: "10493 dolarsa 10495'e geç,
    çakışma yok"."""
    html = UI.render(_collect(dbs))
    assert "Yedek plan — seçtiğin şube dolarsa" in html
    assert "çakışmıyor" in html and "çıkarılır: " in html


def test_yedek_plan_dolu_subede_ACIK_geliyor(dbs):
    html = UI.render(_collect(dbs))
    assert "list.some(p => !p.sec.free)" in html


# ================================================================ B3. takvim
def test_ics_uretiliyor(dbs):
    html = UI.render(_collect(dbs))
    assert "BEGIN:VCALENDAR" in html and "RRULE:FREQ=WEEKLY" in html


def test_ics_tarihleri_TAHMIN_oldugunu_yaziyor(dbs):
    """★ Akademik takvim (dönem başı, tatiller) bu araçta YOK. Tarihleri
    kesinmiş gibi yazmak, yanlış bir günü doğru göstermek olurdu."""
    html = UI.render(_collect(dbs))
    assert "Tarihler TAHMİNİ" in html
    assert "COUNT=${ICS_HAFTA}" in html          # sonsuza kadar tekrar YOK


def test_ics_kacisi_TERS_BOLU_yu_iki_kez_kacirmiyor(dbs):
    """⚠️ Ölçüldü: elle `\\n` yazınca `icsKacis` ters bölüyü ikinci kez
    kaçırıyor ve takvimde "\\\\n" görünüyordu."""
    html = UI.render(_collect(dbs))
    govde = re.search(r"function icsMetni\(\)\{(.*?)\n\}", html, re.S).group(1)
    assert '"\\n"' in govde


def test_saati_ilan_edilmemis_ders_SESSIZCE_dusmuyor(dbs):
    """Takvimde 5 ders bekleyip 4 görmek, hangisinin düştüğünü sormalı."""
    html = UI.render(_collect(dbs))
    assert "saati ilan edilmemiş — takvim dosyasına GİRMEDİ" in html


# ============================================================ B4. bağlantı
def test_baglantida_YALNIZ_crn_var(dbs):
    """✔ Gizlilik: CRN kişisel veri değil. Not/transkript/bölüm girmiyor —
    ve bunu kullanıcıya da YAZIYORUZ, çünkü haklı bir soru."""
    html = UI.render(_collect(dbs))
    govde = re.search(r"function paylasBaglantisi\(\)\{(.*?)\n\}", html, re.S).group(1)
    assert "picks().map(p => p.sec.crn)" in govde
    assert "grades" not in govde and "transcript" not in govde
    assert "Notların, transkriptin ve bölümün <b>girmiyor</b>" in html


def test_baglantidaki_eksik_crn_SESSIZCE_atilmiyor(dbs):
    html = UI.render(_collect(dbs))
    assert "Bağlantıdaki ${eksik.length} CRN katalogda yok" in html


# ================================================== B5. hocaya göre arama
def test_arama_HOCA_adini_da_kapsiyor(dbs):
    html = UI.render(_collect(dbs))
    govde = re.search(r"function filteredCandidates\(\)\{(.*?)\n\}", html, re.S).group(1)
    assert "s.instructor" in govde


# ============================================ C1. kayıt öncesi kontrol
def test_kayit_kontrolu_UC_DURUMLU(dbs):
    """★ "—" = buradan bakılamaz. Transkript yokken tavanı "tamam" saymak,
    bilinmeyeni bilinen göstermek olurdu."""
    html = UI.render(_collect(dbs))
    assert "function kayitKontrol()" in html
    assert "ok === null ? \"—\"" in html
    assert "sağlandı demek DEĞİL" in html


def test_kayit_kontrolu_BES_BASLIK(dbs):
    html = UI.render(_collect(dbs))
    for baslik in ("Kredi tavanı", "Çakışma yok", "Kontenjan",
                   "İkinci anadal tabanı", "Her dersin CRN'i var"):
        assert baslik in html, baslik


def test_transkriptsiz_tavan_BAKILAMAZ(dbs):
    html = UI.render(_collect(dbs))
    assert "transkript girilmedi — tavan bilinmiyor" in html


def test_beyansiz_taban_IDDIA_edilmiyor(dbs):
    """Yönerge tabanı BAŞLANGIÇ YARIYILINA bağlıyor; beyan yoksa "tamam"
    değil, "bakılamıyor"."""
    html = UI.render(_collect(dbs))
    assert "taban iddia edilmiyor" in html


def test_kontenjan_kontrolu_TARIH_yaziyor(dbs):
    html = UI.render(_collect(dbs))
    govde = re.search(r"function kayitKontrol\(\)\{(.*?)\n\}", html, re.S).group(1)
    assert "DATA.generatedAt" in govde


# ================================================== C2. kayıt günü nöbeti
def test_kayit_kipi_daha_SIK_ama_SINIRLI():
    """★ Kayıt gününde kontenjan dakikalar içinde değişiyor; 10 dk'da bir
    bakan nöbet o gün işe yaramıyor.

    ⚠️ Ama sınırı TOPLUCA düşürmek İTÜ sunucularını gereksiz yormak olurdu.
    Uzlaşma: ayrı ve AÇIKÇA istenen bir kip + kendiliğinden biten süre.
    Sınırsız kısa aralık, unutulup günlerce dönen bir nöbeti davet ederdi."""
    from itucap import watch as W
    assert W.KAYIT_INTERVAL < W.MIN_INTERVAL
    assert W.KAYIT_INTERVAL >= 60          # saniyede bir istek atmıyoruz
    assert W.KAYIT_MAX_SURE <= 4 * 3600


def test_normal_nobette_taban_DEGISMEDI():
    """Kip eklemek eski davranışı gevşetmemeli."""
    from itucap import watch as W
    assert W.MIN_INTERVAL == 300 and W.DEFAULT_INTERVAL == 600


def test_kayit_kipi_ACIKCA_isteniyor():
    from itucap import pipeline
    p = pipeline.build_parser() if hasattr(pipeline, "build_parser") else None
    if p is None:
        import inspect
        assert '"--kayit"' in inspect.getsource(pipeline)
        return
    ns = p.parse_args(["watch"])
    assert ns.kayit is False


def test_kayit_kipi_SURE_dolunca_SEBEBINI_yaziyor():
    """Sessizce durmak, kullanıcıya "nöbet çöktü" dedirtir ve bir daha
    güvenilmez."""
    import inspect

    from itucap import watch as W
    kaynak = inspect.getsource(W.run)
    assert "kayıt günü kipi" in kaynak and "nöbet durdu" in kaynak


# ============================================ C3. açılmamış ders uyarısı
def test_arz_uyarisi_USTTE(dbs):
    """Planındaki bir ders bu dönem açılmadıysa bu, kayıt gününden ÖNCE
    bilinmesi gereken bir şey — darboğaz bölümü sayfanın aşağısında."""
    html = UI.render(_collect(dbs))
    assert 'id="arzUyari"' in html
    assert "function renderArzUyarisi()" in html
    assert html.index('id="arzUyari"') < html.index('id="blockSection"')


def test_arz_uyarisi_HIC_ACILMAYACAK_demiyor(dbs):
    """⚠️ Dönem başında ilanlar kademeli yayınlanıyor. "Açılmayacak" demek
    olmayan bir bilgiyi iddia etmek olurdu."""
    html = UI.render(_collect(dbs))
    govde = re.search(r"function renderArzUyarisi\(\)\{(.*?)\n\}", html, re.S).group(1)
    assert "şu ana kadar ilan edilmemiş" in govde
    assert "açılmayacak" not in govde        # yorumlar hariç, ÜRETİLEN metin


def test_arz_uyarisi_engel_yokken_GIZLI(dbs):
    html = UI.render(_collect(dbs))
    govde = re.search(r"function renderArzUyarisi\(\)\{(.*?)\n\}", html, re.S).group(1)
    assert "kutu.hidden = true" in govde
