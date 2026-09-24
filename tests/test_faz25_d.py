"""Faz 25/D — güven ve doğruluk.

D1 bozuk ayar dosyası sayfayı kilitlemesin · D2 geri al · D3 verinin yaşı ·
D4 kendi kendini denetleyen tur.

D4'ün varlık sebebi ölçülmüş: Faz 24'teki iki KİLİTLEYİCİ hata (ilk giren
herkes geliştiricinin raporunu görüyor; ilk kaydetme `settings.toml`'u bozup
uygulamayı açılmaz hale getiriyor) kod okuyarak değil, **boş bir kurulumu
gerçekten çalıştırınca** çıktı. O yürüyüşü teste çevirmezsek bir sonraki
aynı sınıftan hata yine kaçar.
"""
import re
import subprocess
import sys

import pytest


@pytest.fixture(autouse=True)
def no_real_waivers(monkeypatch, tmp_path):
    from itucap import declared
    monkeypatch.setattr(declared, "DEFAULT_PATH", tmp_path / "yok.toml")


from itucap import config                                      # noqa: E402
from itucap import ui as UI                                    # noqa: E402

from test_ui import _collect, dbs                              # noqa: E402,F401


# ============================================ D1. bozuk ayar dosyası
def test_bozuk_ayar_dosyasi_PATLAMIYOR(tmp_path):
    """★ Faz 24'te yazıcı hatası düzeldi ama ELLE bozulmuş bir dosya hâlâ
    her isteği ham bir tomllib hatasına çeviriyordu: uygulama hiç açılmıyor,
    ekranda {"error": "Cannot declare ('student',) twice"} yazıyordu."""
    p = tmp_path / "settings.toml"
    p.write_text("[student]\n\n[student]\nanadal_program = \"BLG\"\n",
                 encoding="utf-8")
    s = config.Settings.load(p)              # istisna FIRLATMAMALI
    assert s.load_error and "twice" in s.load_error


def test_bozuk_ayar_SESSIZCE_yok_sayilmiyor(tmp_path):
    """⚠️ Yanlış ayarla çalışmak, çalışmamaktan KÖTÜ: kullanıcı başka bir
    bölümün raporuna bakıp doğru sanar. O yüzden varsayılana düşüyoruz
    (hiçbir bölüm seçili değil) ve hatayı taşıyoruz."""
    p = tmp_path / "settings.toml"
    p.write_text("bu = geçersiz toml [[[\n", encoding="utf-8")
    s = config.Settings.load(p)
    assert s.anadal_program == "" and s.second_kind == "yok"
    assert s.load_error


def test_saglam_dosyada_hata_alani_BOS(tmp_path):
    p = tmp_path / "settings.toml"
    p.write_text('[student]\nanadal_program = "BLG"\n', encoding="utf-8")
    s = config.Settings.load(p)
    assert s.load_error == "" and s.anadal_program == "BLG"


def test_olmayan_dosya_HATA_degil(tmp_path):
    """Dosya yokluğu ilk kullanıcının normal hâli, hata değil."""
    assert config.Settings.load(tmp_path / "yok.toml").load_error == ""


def test_ayar_hatasi_ARAYUZDE_yaziyor(dbs):
    html = UI.render(_collect(dbs))
    assert 'id="ayarHatasi"' in html
    assert "Ayar dosyası okunamadı; varsayılan ayarlar kullanılıyor" in html
    assert "Seçilen bölüm ve dönem <b>kullanılmamaktadır</b>" in html


# ==================================================== D2. geri al
def test_geri_al_YIGINI_var(dbs):
    html = UI.render(_collect(dbs))
    assert "function geriAl()" in html and "const GERI = []" in html


def test_geri_al_TUM_SECIMI_sakliyor(dbs):
    """★ Bir ders eklemek çakışan başkalarını da çıkarabiliyor (havuz
    kuralı, saat çakışması). Tek dersi geri koymak, onunla birlikte
    düşenleri geride bırakırdı."""
    html = UI.render(_collect(dbs))
    govde = re.search(r"function geriKaydet\(etiket\)\{(.*?)\n\}", html, re.S).group(1)
    assert "sel.map(x => ({...x}))" in govde


def test_geri_yigini_SINIRLI(dbs):
    """Sınırsız yığın, uzun oturumda belleği şişirir."""
    html = UI.render(_collect(dbs))
    assert "GERI_DERINLIK" in html and "GERI.shift()" in html


def test_kip_degisince_yigin_TEMIZLENIYOR(dbs):
    """⚠️ Her kipin KENDİ aday havuzu var; öbür kipin seçimini geri yüklemek
    ızgarada olmayan bir dersi göstermeye çalışırdı.

    ⚠️ Faz 53'te yeniden yazıldı: `useMode` ikinci bir parametre aldı
    (`{kayitli: false}` — durum değişikliğinden sonra kaydedilen program
    yeniden yüklenmesin); imza deseni ona göre gevşetildi, kontrol aynı."""
    html = UI.render(_collect(dbs))
    govde = re.search(r"function useMode\(i(?:, \w+)?\)\{(.*?)\n\}", html, re.S).group(1)
    assert "GERI.length = 0" in govde


def test_oneriye_don_de_GERI_ALINABILIR(dbs):
    """Yanlışlıkla basan kişi bütün emeğini kaybediyordu."""
    html = UI.render(_collect(dbs))
    assert 'geriKaydet("öneriye dönüldü")' in html


def test_ctrl_z_yazi_alaninda_CALISMIYOR(dbs):
    """Metin kutusunda Ctrl+Z yazıyı geri almalı, programı değil."""
    html = UI.render(_collect(dbs))
    assert "/^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)" in html


# ================================================== D3. verinin yaşı
def test_veri_yasi_toplaniyor(dbs):
    data = _collect(dbs)
    assert "dataAge" in data


def test_veri_yasi_damga_YOKSA_bugun_VARSAYMIYOR(tmp_path):
    """⚠️ Bilmemek, taze sanmaktan iyidir."""
    from itucap import db
    con = db.connect(tmp_path / "r.sqlite3", "schema.sql")
    assert UI._veri_yasi(con) is None


def test_veri_yasi_gun_HESAPLIYOR(tmp_path):
    import datetime as dt

    from itucap import db
    con = db.connect(tmp_path / "r.sqlite3", "schema.sql")
    eski = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=5)).isoformat()
    con.execute("INSERT INTO course(code,name) VALUES ('X 101','X')")
    con.execute("INSERT INTO lesson(crn,course_code,updated_at) VALUES ('1','X 101',?)",
                (eski,))
    con.commit()
    yas = UI._veri_yasi(con)
    assert 4.5 < yas["days"] < 5.5 and yas["stale"] is True


def test_taze_veri_BAYAT_isaretlenmiyor(tmp_path):
    import datetime as dt

    from itucap import db
    con = db.connect(tmp_path / "r.sqlite3", "schema.sql")
    con.execute("INSERT INTO course(code,name) VALUES ('X 101','X')")
    con.execute("INSERT INTO lesson(crn,course_code,updated_at) VALUES ('1','X 101',?)",
                (dt.datetime.now(dt.timezone.utc).isoformat(),))
    con.commit()
    assert UI._veri_yasi(con)["stale"] is False


def test_bozuk_damga_PATLAMIYOR(tmp_path):
    from itucap import db
    con = db.connect(tmp_path / "r.sqlite3", "schema.sql")
    con.execute("INSERT INTO course(code,name) VALUES ('X 101','X')")
    con.execute("INSERT INTO lesson(crn,course_code,updated_at) "
                "VALUES ('1','X 101','dün falan')")
    con.commit()
    yas = UI._veri_yasi(con)
    assert yas["days"] is None and yas["stale"] is None


def test_veri_yasi_arayuzde_AYRI_satir(dbs):
    """`generatedAt` sayfanın üretildiği an; kontenjan SON TAZELEMEye ait.
    İkisi günlerce ayrışabilir; tek tarih yazmak eskiyi bugünkü gibi
    gösteriyordu."""
    html = UI.render(_collect(dbs))
    assert 'id="veriYasi"' in html and "function veriYasiMetni()" in html
    assert "veri tazeleme tarihi bilinmiyor" in html


# ================================ D4. kendi kendini denetleyen tur
BOS_KURULUM = r'''
import json, pathlib, sqlite3, sys
sys.path.insert(0, {src!r})
from itucap import config, db, student as S, ui

tmp = pathlib.Path({tmp!r})
con = db.connect(tmp / "ref.sqlite3", "schema.sql"); con.row_factory = sqlite3.Row
con.execute("INSERT INTO program(code,name,level) VALUES ('BLG','Bilgisayar','LS')")
con.execute("""INSERT INTO plan(id,program_code,plan_type,title,source)
               VALUES (1,'BLG','lisans','BLG Lisans','obs')""")
con.execute("""INSERT INTO plan_slot(plan_id,slot_kind,course_code,credits,position,term_no)
               VALUES (1,'REQUIRED','BLG 101',3.0,0,1)""")
con.execute("INSERT INTO course(code,name,credits,ects) VALUES ('BLG 101','Giriş',3.0,4.0)")
con.execute("INSERT INTO lesson(crn,course_code,capacity,enrolled) VALUES ('1','BLG 101',30,0)")
con.commit()
ucon = db.connect(tmp / "user.sqlite3", "schema_user.sql")
sid = S.ensure_student(ucon)
data = ui.collect(con, ucon, sid, config.Settings(), None, None)
out = tmp / "ilk.html"
out.write_text(ui.render(data), encoding="utf-8")
print(json.dumps({{"path": str(out), "blocking": bool(data["onboarding"])}}))
'''


@pytest.fixture()
def ilk_giris_sayfasi(tmp_path):
    """HİÇ ayarı olmayan bir kurulumun sayfasını AYRI bir süreçte üret.

    ⚠️ Ayrı süreç şart: bu depoda `config/settings.toml` VAR ve testin
    içinde import edilmiş modüller onu görüyor. Faz 24'teki hata tam da
    "geliştiricinin dosyası varken sorun görünmüyor" hatasıydı.
    """
    from itucap import config as C
    kod = BOS_KURULUM.format(src=str(C.ROOT / "src"), tmp=str(tmp_path))
    r = subprocess.run([sys.executable, "-c", kod], capture_output=True, text=True,
                       cwd=str(C.ROOT))
    assert r.returncode == 0, r.stderr[-1500:]
    import json as _json
    return _json.loads(r.stdout.strip().splitlines()[-1])


def test_bos_kurulum_sayfasi_URETILIYOR(ilk_giris_sayfasi):
    assert ilk_giris_sayfasi["blocking"] is True


def test_bos_kurulumda_SAYFA_HATASI_yok(ilk_giris_sayfasi):
    """★★ D4'ün asıl işi. Şablonda dizge aramak, JS'in çalıştığını
    göstermiyor; boş kurulumda ayrı bir dal çalışıyor ve orada patlayan
    bir hata sayfayı bembeyaz bırakır."""
    pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import sync_playwright

    try:
        pw = sync_playwright().start()
        tarayici = pw.chromium.launch()
        p = tarayici.new_page(viewport={"width": 1200, "height": 900})
    except Exception as exc:
        pytest.skip(f"playwright başlatılamadı: {exc}")
    try:
        hatalar = []
        p.on("pageerror", lambda e: hatalar.append(str(e)))
        p.goto("file://" + ilk_giris_sayfasi["path"])
        p.wait_for_timeout(600)
        assert hatalar == [], hatalar
        # Karşılama kartı görünüyor, rapor bölümleri gizli.
        assert p.locator("#hero").is_visible()
        assert "kurulum" in p.evaluate("document.body.className")
        gorunur = p.evaluate("""() => [...document.querySelectorAll('[hidden]')]
            .filter(e => e.getClientRects().length).map(e => e.id)""")
        assert gorunur == [], gorunur
    finally:
        tarayici.close(); pw.stop()


def test_bos_kurulumda_CIKMAZ_ekran_yok(ilk_giris_sayfasi):
    """Her karşılama adımının bir çıkış yolu olmalı: "Plan bulunamadı." gibi
    ne olduğu belirsiz bir ekran, kullanıcıyı orada bırakıyordu."""
    metin = __import__("pathlib").Path(ilk_giris_sayfasi["path"]).read_text(
        encoding="utf-8")
    assert "Bölüm seçilmedi" in metin
    assert 'id="goProgram"' in metin


def test_bugun_dun_TAKVIM_gunu(tmp_path):
    """⚠️ "bugün / dün" takvim günü demek, "24 saat" değil. Dün 12:50'de
    tazelenen veri 13 saat sonra hâlâ "bugün" görünüyordu (ölçüldü)."""
    import datetime as dt

    from itucap import db
    con = db.connect(tmp_path / "r.sqlite3", "schema.sql")
    dun = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=13)).isoformat()
    con.execute("INSERT INTO course(code,name) VALUES ('X 101','X')")
    con.execute("INSERT INTO lesson(crn,course_code,updated_at) VALUES ('1','X 101',?)",
                (dun,))
    con.commit()
    yas = UI._veri_yasi(con)
    assert yas["days"] < 1                    # 24 saat dolmadı
    assert yas["calendarDays"] in (0, 1)      # takvim günü ayrı bilgi


# ------------------------------- bozuk dosya arayüzden DÜZELTİLEBİLMELİ
def test_bozuk_dosya_arayuzden_DUZELTILEBILIYOR(tmp_path):
    """★★ Kapalı döngü: yazıcı satır bazlı çalıştığı için bozukluğu (iki
    `[student]` başlığı) olduğu gibi koruyordu. Kullanıcı hatayı görüyor,
    "Program"dan yeniden seçiyor, aynı hatayı yine görüyordu."""
    p = tmp_path / "settings.toml"
    p.write_text("[student]\n\n[student]\nanadal_program = \"BLG\"\n",
                 encoding="utf-8")
    assert config.Settings.load(p).load_error          # önce bozuk
    config.update_settings({"anadal_program": "MAK", "donem": 3}, path=p)
    s = config.Settings.load(p)
    assert s.load_error == ""                          # sonra sağlam
    assert s.anadal_program == "MAK" and s.donem == 3


def test_bozuk_dosya_SILINMIYOR_yedekleniyor(tmp_path):
    """⚠️ İçinde kullanıcının notları olabilir."""
    p = tmp_path / "settings.toml"
    p.write_text("[student]\n\n[student]\n# ölçüm notum\nx = 1\n", encoding="utf-8")
    config.update_settings({"donem": 2}, path=p)
    yedek = p.with_suffix(p.suffix + ".bozuk")
    assert yedek.exists() and "ölçüm notum" in yedek.read_text(encoding="utf-8")


def test_saglam_dosya_bozulacaksa_YAZILMIYOR(tmp_path, monkeypatch):
    """⚠️ Girdi sağlamken çıktı bozuksa hata BİZDE. Sessizce üstüne yazmak,
    kullanıcının çalışan ayarını bozmak olurdu."""
    p = tmp_path / "settings.toml"
    saglam = '[student]\nanadal_program = "BLG"\n'
    p.write_text(saglam, encoding="utf-8")
    monkeypatch.setattr(config, "_toml_value", lambda v: "[[[bozuk")
    with pytest.raises(ValueError):
        config.update_settings({"donem": 3}, path=p)
    assert p.read_text(encoding="utf-8") == saglam      # dokunulmadı
