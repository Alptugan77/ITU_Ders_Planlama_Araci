"""Faz 45 — dersi SAATE KİLİTLE, öneriler etrafında kurulsun.

Kullanıcı 17.09.2026: *"dersleri saate kitleme ve önerilerin onun etrafında
şekillenmesi özelliği getirir misin"*.

`watch_courses` "bu ders programda olsun" diyordu ama ŞUBEYİ motora
bırakıyordu; motor daha ucuz bir şube bulunca saat kayıyordu. Kilit şubeyi —
dolayısıyla saati — sabitliyor ve programın kalanı onun etrafında kuruluyor.

Gerçek veriyle ölçüldü (`BLG 351E` Çar 12:30 → Pzt 14:30'a kilitlendi):

    ATA 121   Sal 10:30 → Çar 13:30
    ATA 122   Pzt 15:30 → Sal 10:30
    GEO 401E  Pzt 13:30 → PROGRAMDAN ÇIKTI   (kilitli saatle çakışıyor)
    16 ders / 22.5 kredi → 15 ders / 20.5 kredi

Yani kilit BEDAVA DEĞİL ve bu görünmek zorunda. 3 kilit denemesinin 3'ünde de
kilit tuttu, ortalama 1.0 başka ders kaydı.

⚠️ İKİ TASARIM KARARI, ikisi de ölçümden çıktı:

1. **Kilit SERT kısıt.** Yumuşak olsaydı motor onu sessizce yok sayabilirdi.
   Sert olduğu için çelişen kilitler SONUÇ BOŞ verir — ölçüldü: `BLG 212E`
   ve `ATA 121` çakışan şubelere kilitlenince DEPAR kipinde 0 program çıktı.
   Arayüz bunu "kilit nedeniyle" demek zorunda; yoksa kullanıcı "bu dönem
   çakışmasız program yok" sanır.
2. **Kilit yalnız O KİPİN havuzundaki derse bağlanır.** Arayüzün iki kipi
   ayrı aday havuzu kuruyor. Aynı ölçümde `ATA 121` "5. dönem + alttan"
   havuzunda YOK; kilidi orada da zorunlu saysaydık o kip de topyekûn
   boşalırdı (3 → 0 program). Kapsam dışı olmak, yok sayılmak değil.
"""
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def no_real_waivers(monkeypatch, tmp_path):
    from itucap import declared
    monkeypatch.setattr(declared, "DEFAULT_PATH", tmp_path / "yok.toml")


from itucap import config as C                                # noqa: E402
from itucap import recommend as REC                           # noqa: E402
from itucap import ui as UI                                   # noqa: E402

KAYNAK = pathlib.Path(UI.__file__).read_text(encoding="utf-8")


# --------------------------------------------------------------- motor
def _sube(crn, kod, gun, bas, bit):
    return REC.Section(crn=crn, course=kod, instructor=None, capacity=40,
                       enrolled=0,
                       meetings=(REC.Meeting(gun, bas, bit, None, None, None),))


def _aday(kod, subeler, **kw):
    ayar = dict(name=kod, role="ANADAL", ects=4.0, credits=3.0, unlocks=0,
                tier=0, critical=False, required=True, sections=subeler)
    ayar.update(kw)
    return REC.Candidate(course=kod, **ayar)


def _havuz():
    """AAA: Pzt 09–11 ya da Sal 09–11 · BBB: yalnız Pzt 09–11."""
    return [
        _aday("AAA 101", [_sube("100", "AAA 101", 1, 540, 660),
                          _sube("101", "AAA 101", 2, 540, 660)]),
        _aday("BBB 102", [_sube("200", "BBB 102", 1, 540, 660)]),
    ]


def test_motor_KILITLI_SUBEYI_kullaniyor():
    """★★ İsteğin çekirdeği: kilitlenen şube DEĞİŞMİYOR."""
    cs = _havuz()
    # Kilitsiz: motor AAA için istediği şubeyi seçebilir.
    kilitli = REC.build_schedules(cs, max_load=35, limit=3,
                                  locked={"AAA 101": "101"})
    assert kilitli, "kilitliyken hiç program çıkmadı"
    for s in kilitli:
        crn = {p.candidate.course: p.section.crn for p in s.picks}
        assert crn.get("AAA 101") == "101", f"kilit tutmadı: {crn}"


def test_kilit_dersi_PROGRAMDA_TUTUYOR():
    """Kilit aynı zamanda 'bu ders programda olsun' demek — yoksa motor
    dersi tamamen düşürüp kilidi teknik olarak 'ihlal etmemiş' olurdu."""
    for s in REC.build_schedules(_havuz(), max_load=35, limit=3,
                                 locked={"AAA 101": "101"}):
        assert "AAA 101" in {p.candidate.course for p in s.picks}


def test_program_KILIDIN_ETRAFINDA_kuruluyor():
    """AAA Pzt'ye kilitlenince BBB (yalnız Pzt şubesi var) DÜŞMELİ;
    Sal'a kilitlenince İKİSİ DE girmeli. Kilit öneriyi şekillendiriyor."""
    pzt = REC.build_schedules(_havuz(), max_load=35, limit=1,
                              locked={"AAA 101": "100"})[0]
    sal = REC.build_schedules(_havuz(), max_load=35, limit=1,
                              locked={"AAA 101": "101"})[0]
    assert {p.candidate.course for p in pzt.picks} == {"AAA 101"}
    assert {p.candidate.course for p in sal.picks} == {"AAA 101", "BBB 102"}


def test_HAVUZDA_OLMAYAN_ders_kipi_BOSALTMIYOR():
    """⚠️ Ölçülmüş tuzak: iki kip ayrı aday havuzu kuruyor. `all` kipinde
    kilitlenen ders dönemlik havuzda olmayabilir; kilidi orada da zorunlu
    saysaydık o kip topyekûn boşalırdı."""
    kilitsiz = REC.build_schedules(_havuz(), max_load=35, limit=3)
    disarda = REC.build_schedules(_havuz(), max_load=35, limit=3,
                                  locked={"ZZZ 999": "00000"})
    assert len(disarda) == len(kilitsiz) > 0, "kapsam dışı kilit kipi boşalttı"


def test_KAPANMIS_SUBE_kilidi_SESSIZCE_kaymiyor():
    """⚠️ Ders havuzda ama CRN yoksa motor BAŞKA ŞUBEYE GEÇMİYOR — sonuç
    boş çıkıyor. Sessizce kaydırmak, kullanıcının koyduğu kısıtı yok
    saymak olurdu; arayüz bunu `locked[].ok` ile söylüyor."""
    assert REC.build_schedules(_havuz(), max_load=35, limit=3,
                               locked={"AAA 101": "99999"}) == []


# --------------------------------------------------------------- ayar
def test_ayar_KALICI_ve_yazilabilir(tmp_path):
    """Kilit bir seçim değil AYAR: sayfa yenilenince durmalı."""
    assert "kilitli" in C._EDITABLE, "arayüzden yazılamaz"
    p = tmp_path / "settings.toml"
    p.write_text('[student]\nanadal_program = "GEO"  # not\n', encoding="utf-8")
    C.update_settings({"kilitli": ["GEO 315E@13601"]}, path=p)
    metin = p.read_text(encoding="utf-8")
    assert 'kilitli = ["GEO 315E@13601"]' in metin
    assert "# not" in metin, "yazıcı yorumu sildi"
    assert C.Settings.load(p).kilitli == ["GEO 315E@13601"]


def test_ayirma_DERS_ve_CRN():
    assert UI._kilit_ayikla(["geo 315e@13601", " BLG 212E @ 12486 "]) == {
        "GEO 315E": "13601", "BLG 212E": "12486"}
    # Bozuk satır motora GİRMİYOR (uygulanamaz bir kısıt uygulanmış sayılmaz).
    assert UI._kilit_ayikla(["GEO 315E", "@123", ""]) == {}


def test_TUTMAYAN_kilit_listeden_DUSMUYOR():
    """★★ Dönem değişip CRN kaybolunca satırı sessizce atmak, kullanıcının
    'kilitlemiştim, saati neden kaydı?' diye sormasına yol açardı."""
    havuz = {"GEO 315E": {"13601": [{"day": 1, "start": 540, "end": 660}]},
             "BLG 212E": {"12486": []}}
    bilgi = UI._kilit_bilgisi(
        ["GEO 315E@13601", "BLG 212E@99999", "YOK 100@1"], havuz)
    durum = {b["course"]: (b["ok"], b["neden"]) for b in bilgi}
    assert durum["GEO 315E"] == (True, "")
    assert durum["BLG 212E"] == (False, "sube"), "şube kapandı ayrı cümle"
    assert durum["YOK 100"] == (False, "ders"), "ders havuzda yok ayrı cümle"


# --------------------------------------------------------------- sunucu
def _durum(tmp_path, monkeypatch):
    from itucap import db, server
    monkeypatch.setattr(C, "ROOT", tmp_path)
    (tmp_path / "config").mkdir()
    (tmp_path / "data").mkdir()
    (tmp_path / "config" / "settings.toml").write_text(
        '[student]\nanadal_program = "GEO"\n', encoding="utf-8")
    monkeypatch.setattr(C, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(C, "REF_DB", tmp_path / "data" / "reference.sqlite3")
    monkeypatch.setattr(C, "USER_DB", tmp_path / "data" / "user.sqlite3")
    db.connect(C.REF_DB, "schema.sql").close()
    db.connect(C.USER_DB, "schema_user.sql").close()
    st = server.State.__new__(server.State)
    return st


def test_uc_kilidi_ACIP_KAPATIYOR(tmp_path, monkeypatch):
    st = _durum(tmp_path, monkeypatch)
    r = st.toggle_lock("geo 315e", "13601")
    assert r["on"] is True and r["locked"] == ["GEO 315E@13601"]
    assert C.Settings.load(tmp_path / "config" / "settings.toml").kilitli \
        == ["GEO 315E@13601"]
    # Aynı CRN tekrar → AÇ.
    r = st.toggle_lock("GEO 315E", "13601")
    assert r["on"] is False and r["locked"] == []


def test_bir_derste_TEK_kilit(tmp_path, monkeypatch):
    """⚠️ İki şube birden kilitlenirse hiçbir program kurulamaz (ikisi de
    zorunlu). Sessizce üstüne yazmak yerine eskisini AÇIKÇA bildiriyoruz."""
    st = _durum(tmp_path, monkeypatch)
    st.toggle_lock("GEO 315E", "13601")
    r = st.toggle_lock("GEO 315E", "13602")
    assert r["locked"] == ["GEO 315E@13602"], "iki kilit birden kaldı"
    assert r["replaced"] == "13601", "düşen kilit söylenmiyor"


# --------------------------------------------------------------- arayüz
def test_IZGARADA_kilit_ISARETI_var():
    """Kilit görünmez bir kısıt olamaz; ızgarada işareti olmalı.
    ⚠️ İşaret RENK DEĞİL — renk programı, ton dersi söylüyor (Faz 40)."""
    assert 'kld ? "kilit" : ""' in KAYNAK, "blokta kilit sınıfı yok"
    assert '<span class="kilitim">${KILIT_SVG}</span>' in KAYNAK
    assert ".blk.kilit{border-left-width:6px" in KAYNAK
    # Renk taşımıyor: ton değişkenlerine dokunmuyor.
    kural = re.search(r"\.blk\.kilit\{([^}]*)\}", KAYNAK).group(1)
    assert "background" not in kural and "--ton" not in kural


def test_BOS_SONUCUN_SEBEBI_yaziliyor():
    """★★ Kilit sert kısıt olduğu için sonuç boş çıkabiliyor. "öneri
    üretilemedi" tek başına yanlış yönlendirir: kullanıcı kendi koyduğu
    kısıtı değil, dönemi suçlar. (Faz 25 ve Faz 44'ün aynı dersi.)"""
    fn = re.search(r"function oneriYok\(\)\{(.*?)\n\}", KAYNAK, re.S).group(1)
    assert "kilit nedeniyle" in fn
    assert "kilitliBuKipte()" in fn, "kipte bağlamayan kilit suçlanmamalı"
    serit = re.search(r"function renderKilitNot\(\)\{(.*?)\n\}\n", KAYNAK,
                      re.S).group(1)
    assert "Bu kipte program oluşturulamadı." in serit
    assert "data-ac=" in serit, "tek tıkla açma yok"


def test_SUNUCUSUZ_dosyada_sahte_dugme_yok():
    """`make ui` çıktısında yazacak yer yok; tıklanınca hiçbir şey yapmayan
    bir düğme kaydetmediğini gizlerdi (bkz. `watchButton`)."""
    fn = re.search(r"function kilitButonu\(course, crn\)\{(.*?)\n\}", KAYNAK,
                   re.S).group(1)
    assert "if(!DATA.live) return \"\";" in fn


# --------------------------------------------------------- uçtan uca
_CANLI = r'''
import sys, tempfile, threading, time, os
from pathlib import Path
sys.path.insert(0, os.environ["ITUCAP_SRC"])
_T = Path(tempfile.mkdtemp()); (_T/"config").mkdir(); (_T/"data").mkdir()
(_T/"config"/"settings.toml").write_text(
    '[student]\nanadal_program="HTAE"\nsecond_kind="yok"\n', encoding="utf-8")
import itucap.config as config
config.ROOT = _T; config.DATA_DIR = _T/"data"
config.REF_DB = _T/"data"/"reference.sqlite3"; config.USER_DB = _T/"data"/"user.sqlite3"
from itucap import db
con = db.connect(config.REF_DB, "schema.sql")
con.execute("INSERT INTO program(code,name,level) VALUES ('HTAE','H','LS')")
con.execute("INSERT INTO plan(id,program_code,plan_type,title,source)"
            " VALUES (1,'HTAE','lisans','x','obs')")
# AAA'nın İKİ şubesi var (Pzt 09-11 / Sal 09-11); BBB yalnız Pzt 09-11.
# AAA Sal'a kilitlenirse ikisi de sığar, Pzt'ye kilitlenirse BBB düşer.
plan = [("AAA 101E", [("300", 1, 540, 660), ("301", 2, 540, 660)]),
        ("BBB 102E", [("400", 1, 540, 660)])]
for i, (kod, subeler) in enumerate(plan):
    con.execute("INSERT INTO course(code,name,credits,ects) VALUES (?,?,3,4)",
                (kod, "Ders " + kod))
    con.execute("INSERT INTO plan_slot(plan_id,slot_kind,course_code,position,term_no)"
                " VALUES (1,'REQUIRED',?,?,1)", (kod, i))
    for crn, gun, bas, bit in subeler:
        con.execute("INSERT INTO lesson(crn,course_code,capacity,enrolled)"
                    " VALUES (?,?,40,0)", (crn, kod))
        con.execute("INSERT INTO lesson_allowed_program(crn,program_code)"
                    " VALUES (?,'HTAE')", (crn,))
        con.execute("INSERT INTO lesson_meeting(crn,day_of_week,start_min,end_min)"
                    " VALUES (?,?,?,?)", (crn, gun, bas, bit))
con.commit(); con.close(); db.connect(config.USER_DB, "schema_user.sql").close()

from itucap import server
st = server.State(label="ben")
h = server.build(st, host="127.0.0.1", port=0); P = h.server_address[1]
threading.Thread(target=h.serve_forever, daemon=True).start(); time.sleep(0.4)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width":1400,"height":1000})
    pg.goto(f"http://127.0.0.1:{P}/", wait_until="networkidle", timeout=30000)
    pg.wait_for_timeout(1500)
    print("SERIT0:" + ("gizli" if pg.eval_on_selector("#kilitNot","e=>e.hidden")
                       else "acik"))
    # AAA'yı Sal şubesine (301) kilitle — arayüzün kendi uçundan.
    pg.evaluate("""async () => { applyState(
        await api("/api/kilit", {course:"AAA 101E", crn:"301"})); }""")
    pg.wait_for_timeout(1500)
    crnler = pg.evaluate("""() => (MODES[0].schedules||[]).map(s => {
        const x = s.picks.find(p => p.course === "AAA 101E");
        return x ? x.section.crn : null; })""")
    print("ONERI_CRN:" + ",".join(str(c) for c in crnler))
    print("SERIT1:" + ("gizli" if pg.eval_on_selector("#kilitNot","e=>e.hidden")
                       else "acik"))
    pg.evaluate("() => resetTo(0)"); pg.wait_for_timeout(600)
    print("ROZET:" + str(pg.eval_on_selector_all("#grid .blk.kilit","e=>e.length")))
    print("SVG:" + str(pg.eval_on_selector_all("#grid .kilitim svg","e=>e.length")))
    # Diyalogdaki düğme metni kilitliyken değişiyor mu?
    pg.click('#grid .blk[data-course="AAA 101E"]'); pg.wait_for_timeout(600)
    print("DUGME:" + pg.eval_on_selector("#kilitBtn","e=>e.textContent.trim()"))
    pg.evaluate("() => document.querySelector('dialog[open]').close()")
    # Şeritten aç.
    pg.wait_for_timeout(300)
    pg.click("#kilitNot [data-ac]")
    pg.wait_for_function("() => (DATA.locked||[]).length === 0", timeout=60000)
    pg.wait_for_timeout(400)
    print("SERIT2:" + ("gizli" if pg.eval_on_selector("#kilitNot","e=>e.hidden")
                       else "acik"))
    print("ROZET2:" + str(pg.eval_on_selector_all("#grid .blk.kilit","e=>e.length")))
    b.close()
h.shutdown()
'''


def test_UCTAN_UCA_kilit_kuruluyor_gorunuyor_aciliyor(tmp_path, monkeypatch):
    """★★ Tarayıcıda bütün akış: kilitle → bütün öneriler o şubeyi
    kullanıyor → ızgarada işaret ve şerit çıkıyor → tek tıkla açılıyor."""
    if not shutil.which("node"):
        pytest.skip("node yok")
    try:
        import playwright  # noqa: F401
    except ImportError:
        pytest.skip("playwright yok")
    monkeypatch.setenv("ITUCAP_SRC", str(Path(UI.__file__).resolve().parents[1]))
    betik = tempfile.NamedTemporaryFile("w", suffix=".py", delete=False,
                                        dir=str(tmp_path))
    betik.write(_CANLI); betik.close()
    r = subprocess.run([sys.executable, betik.name], capture_output=True,
                       text=True, timeout=240)
    if r.returncode != 0:
        pytest.fail(r.stderr[-1500:])
    c = dict(s.split(":", 1) for s in r.stdout.strip().splitlines()
             if ":" in s and s.split(":", 1)[0].isupper())
    assert c["SERIT0"] == "gizli", "kilit yokken şerit görünüyor"
    assert set(c["ONERI_CRN"].split(",")) == {"301"}, \
        f"kilit bütün önerilerde tutmadı: {c['ONERI_CRN']}"
    assert c["SERIT1"] == "acik", "kilit varken şerit çıkmıyor"
    assert int(c["ROZET"]) == 1, f"ızgarada kilit işareti yok: {c}"
    assert int(c["SVG"]) == 1, "asma kilit simgesi çizilmemiş"
    assert c["DUGME"] == "Kilidi aç", f"düğme durumu yanlış: {c['DUGME']}"
    assert c["SERIT2"] == "gizli", "kilit açılınca şerit kalmış"
    assert int(c["ROZET2"]) == 0, "kilit açılınca işaret kalmış"
