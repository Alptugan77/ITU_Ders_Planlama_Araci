"""Faz 50 — not dağılımı çubukları + telefon arayüzü (18.09.2026).

Kullanıcı iki şey söyledi:

1. *"not dağılımında +lar yüzünden barların tabanları aynı seviyede
   olmuyor"* — ölçüldü, haklıydı: "artıları ayır" kipinde 15 sütunun
   tabanı **ÜÇ AYRI seviyede**, 7px fark.
2. *"telefonun arayüz tasarımını geliştirebilir misin, şu anda telefonda
   kullanılması biraz zor"* — 390px'te her görünüm ve her pencere gezildi.

| ölçüm (390px) | önce | sonra |
|---|---|---|
| aday listesinde bir ders satırı | **330px**, sağdaki sayı KESİK ("180"→"18") | **118–165px**, kesik yok |
| içeriğin başladığı yer (10 görünüm) | 475px | **255px** |
| öneri sekmeleri | **3 satır**, "ÖNERİ 1 · 20KREDİ" | **1 satır**, "20 kredi" |
| 44px altı denetim | görünüm başına 7–8 | 0 (34'te kalan iki sınıf bilerek) |
| `.watchmini` telefon kuralı | **ölü** (24px) | 34px |
| çubuk tabanı (15 kova) | 3 seviye, 7px fark | **tek seviye** |

⚠️ Çubuk hatasının kökü etiketten daha derindi: `.ndsut` esnek kutuydu ve
üç öğe (sayı + %100 çubuk + etiket) kabı taşırıyordu; tarayıcı hepsini
büzüyor, büzülme çubuğun boyuna göre değiştiği için TABAN kayıyordu.
Üstelik yüzdeler kabın tamamına göre isteniyordu, yani ölçek de yanlıştı.
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


from itucap import ui as UI                                    # noqa: E402

KAYNAK = pathlib.Path(UI.__file__).read_text(encoding="utf-8")
CSS = re.search(r"<style>(.*?)</style>", KAYNAK, re.S).group(1)


def _kural(ad: str) -> str:
    m = re.search(r"(?m)^" + re.escape(ad) + r"\{([^}]*)\}", CSS)
    assert m, f"{ad} kuralı yok"
    return m.group(1).replace("\n", "").replace(" ", "")


def _telefon_blogu() -> str:
    """`@media (max-width:700px)` bloklarının tamamı (birden fazla var).

    ⚠️ `split` ile ilk bloğu almak KIRILGAN — repoda üç ayrı 700px bloğu
    var ve hangisine yazıldığı zamanla değişiyor. Süslü parantez sayıyoruz.
    """
    out = []
    for m in re.finditer(r"@media \(max-width:700px\)\{", CSS):
        i, derinlik = m.end(), 1
        while i < len(CSS) and derinlik:
            if CSS[i] == "{":
                derinlik += 1
            elif CSS[i] == "}":
                derinlik -= 1
            i += 1
        out.append(CSS[m.end():i - 1])
    assert out, "telefon bloğu yok"
    return "\n".join(out)


TELEFON = _telefon_blogu()


# ==================================== 1. çubuk tabanı — kaynak
def test_SUTUN_esnek_kutu_DEGIL_izgara():
    """★★ Kök sebep: esnek kutuda üç öğe kabı taşırıyor ve tarayıcı
    hepsini büzüyordu; büzülme çubuğun boyuna bağlı olduğu için TABAN
    kayıyordu. Izgarada 1. satır sayı, 2. satır çubuk alanı, 3. satır
    etiket — birinci ve üçüncü satır bütün sütunlarda aynı."""
    k = _kural(".ndsut")
    assert "display:grid" in k, k
    assert "grid-template-rows:autominmax(0,1fr)auto" in k, k
    assert "justify-content:flex-end" not in k, "eski esnek kutu geri gelmiş"


def test_ETIKET_KUTUSU_sabit_yukseklikte():
    """Etiket karakter sayısına göre büyürse taban yine kayar."""
    assert "height:12px" in _kural(".ndsut>span")
    genis = re.search(r"\.ndgrafik\.genis \.ndsut>span\{([^}]*)\}", CSS)
    assert genis and "height:20px" in genis.group(1).replace(" ", "")


def test_GENIS_ETIKET_yer_varsa_DIK_DEGIL():
    """⚠️ Döndürülmüş 8.5px yazı okunmuyor. Ölçüldü: 560px'ten sonra sütun
    ≥26px, yatay 'BA+' 17px — sığıyor. Dar ekranda (390px'te sütun 17.7px)
    sığmadığı için orada dikey kalıyor."""
    assert "writing-mode:horizontal-tb" in CSS
    m = re.search(r"@media \(min-width:560px\)\{(.*?)\n\}", CSS, re.S)
    assert m and ".ndgrafik.genis .ndsut>span" in m.group(1)


# ==================================== 2. telefon — kaynak
def test_SEKME_ETIKETI_TEK_parca():
    """★★ Esnek kutu ÖĞE SINIRINDAKİ boşluğu yutuyor: "ÖNERİ 1 · 20KREDİ".
    Aynı sınıf arz başlığında (Faz 46) ve `summary` tabanında (Faz 48) da
    çıktı. Etiketin tamamı tek `<span>` içinde olmalı."""
    assert 'class="tabmetin"' in KAYNAK
    fn = re.search(r"function renderTabs\(\)\{(.*?)\n\}", KAYNAK, re.S).group(1)
    kod = re.sub(r"/\*.*?\*/", " ", fn, flags=re.S)
    # Kredi sayısı da `.tabfark` içinde: seçili olmayan sekme kısa kalıyor.
    assert re.search(r'class="tabfark"\s*>\s*·\s*\$\{s\.credits\}', kod), kod[:400]


def test_ADAY_TABLOSU_telefonda_KART():
    """★★ Ölçüldü (390px): ders satırı 330px ve kontenjan sütunu kutunun
    DIŞINA taşıp rakamı kesiyordu. Tablo tek DOM kalıyor, telefonda kart
    olarak diziliyor — iki ayrı çizim yazsaydık ayrışırlardı."""
    assert "#cands,#cands tbody,#cands tr,#cands td{display:block}" in TELEFON
    assert "#cands thead{display:none}" in TELEFON
    assert "#cands tr[data-course]{display:grid" in TELEFON
    # Başlıksız çıplak sayı bırakmıyoruz: kredi hücresi etiketini taşıyor.
    assert 'data-e="kredi"' in KAYNAK
    assert 'content:" " attr(data-e)' in TELEFON


def test_SIMDI_paneli_telefonda_PROGRAM_gorunumunde():
    """Panel "Programın hazır. Şimdi:" diyor; 11 görünümün 10'unda
    içeriğin önünde 144px yer kaplıyordu."""
    assert ':root:not([data-gorunum="schedSection"]) #sonraki{display:none}' in TELEFON
    # Alt çubuğun kopyası olan iki düğme telefonda çıkıyor.
    assert '#sonraki [data-go="schedSection"]' in TELEFON
    assert '#sonraki [data-go="candSection"]{display:none}' in TELEFON


def test_TELEFON_HEDEF_kurali_OLU_DEGIL():
    """★★ Medya sorgusu ÖZGÜLLÜK KAZANDIRMIYOR. `.rm,.watchmini` telefon
    kuralı (34px) medya bloğundaydı ama `.watchmini`nin temel kuralı
    kaynakta DAHA SONRA gelip aynı özgüllükte eziyordu — ölçüldü: hesaplanan
    `min-height` 24px, yani kural iki fazdır ölüydü."""
    assert "button.rm,button.watchmini{min-height:34px" in TELEFON.replace("\n", "")
    assert ".ghost,.tab{min-height:44px" in TELEFON
    assert ".modebtn,#candRole button{min-height:44px" in TELEFON


# ==================================== 3. çubuk tabanı — tarayıcıda
_BAR = """<!doctype html><meta charset="utf-8">
<style>__CSS__</style>
<div class="puan" style="width:__W__px">
  <div class="ndgrafik __GENIS__">__SUT__</div>
</div>"""


def _bar_sayfa(genis: bool) -> str:
    kutu = (["AA", "BA+", "BA", "BB+", "BB", "CB+", "CB", "CC+", "CC",
             "DC+", "DC", "DD+", "DD", "FF", "VF"] if genis
            else ["AA", "BA", "BB", "CB", "CC", "DC", "DD", "FF", "VF"])
    sut = "".join(
        f'<div class="ndsut"><b>{7 + i}</b>'
        f'<i class="{"kotu" if k in ("FF", "VF") else ""}" '
        f'style="height:{20 + i * 5}%"></i><span>{k}</span></div>'
        for i, k in enumerate(kutu))
    return (_BAR.replace("__CSS__", CSS).replace("__SUT__", sut)
            .replace("__GENIS__", "genis" if genis else ""))


OLC_BAR = """() => {
  const g = document.querySelector(".ndgrafik");
  const s = [...g.querySelectorAll(".ndsut")].map(e => {
    const i = e.querySelector("i").getBoundingClientRect();
    const t = e.querySelector("span").getBoundingClientRect();
    return {alt: Math.round(i.bottom * 10) / 10, barY: i.height,
            etAlt: Math.round(t.bottom * 10) / 10,
            etY: Math.round(t.height * 10) / 10};
  });
  const u = a => [...new Set(a)];
  return {sutun: s.length,
          taban: u(s.map(x => x.alt)).length,
          etiketTaban: u(s.map(x => x.etAlt)).length,
          etiketYuk: u(s.map(x => x.etY)).length,
          tasma: Math.round(Math.max(0,
            g.getBoundingClientRect().top - Math.min(...s.map(x => x.alt - x.barY)))),
          enBuyuk: Math.round(Math.max(...s.map(x => x.barY)))};
}"""


def test_CUBUK_TABANLARI_ayni_seviyede(tmp_path):
    """★★ Bildirilen hata, tarayıcıda ölçülüyor: dört genişlik × iki kip.

    ⚠️ Kaynakta kural aramak YETMEZ — hatanın kendisi "kural var ama
    tarayıcı başka türlü hesaplıyor"du (esnek büzülme). Ölçüm şart."""
    pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import sync_playwright

    try:
        pw = sync_playwright().start()
        b = pw.chromium.launch()
    except Exception as exc:                                   # pragma: no cover
        pytest.skip(f"playwright başlatılamadı: {exc}")
    try:
        for w in (1512, 560, 390, 320):
            pg = b.new_page(viewport={"width": w, "height": 900})
            for genis in (False, True):
                yol = tmp_path / f"bar{w}{int(genis)}.html"
                yol.write_text(_bar_sayfa(genis).replace("__W__", str(min(w, 490) - 40)),
                               encoding="utf-8")
                pg.goto(yol.as_uri()); pg.wait_for_timeout(120)
                r = pg.evaluate(OLC_BAR)
                ad = f"{w}px {'15' if genis else '9'} kova"
                assert r["taban"] == 1, f"{ad}: çubuk tabanı {r['taban']} seviyede"
                assert r["etiketTaban"] == 1, f"{ad}: etiketler hizasız"
                assert r["etiketYuk"] == 1, f"{ad}: etiket kutuları farklı boyda"
                assert r["tasma"] == 0, f"{ad}: çubuk kabı {r['tasma']}px taşıyor"
                assert r["enBuyuk"] < 104, f"{ad}: ölçek yanlış ({r['enBuyuk']}px)"
            pg.close()
    finally:
        b.close(); pw.stop()


# ==================================== 4. telefon — uçtan uca
_CANLI = r'''
import os, sys, tempfile, threading, time
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
PLAN = [("AAA 101E", 1, 1), ("BBB 102E", 1, 2), ("CCC 103E", 1, 3)]
for kod, term, i in PLAN:
    con.execute("INSERT INTO course(code,name,credits,ects) VALUES (?,?,3,4)",
                (kod, "Uzun Adli Bir Ders " + kod))
    con.execute("INSERT INTO plan_slot(plan_id,slot_kind,course_code,position,term_no)"
                " VALUES (1,'REQUIRED',?,?,?)", (kod, i, term))
    # İki şube: motor birden çok program kurabilsin (sekmeler doğsun).
    for j, bas in enumerate((540 + i * 10, 780)):
        crn = str(700 + i * 10 + j)
        con.execute("INSERT INTO lesson(crn,course_code,capacity,enrolled)"
                    " VALUES (?,?,40,?)", (crn, kod, 10 * i))
        con.execute("INSERT INTO lesson_allowed_program(crn,program_code)"
                    " VALUES (?,'HTAE')", (crn,))
        con.execute("INSERT INTO lesson_meeting(crn,day_of_week,start_min,end_min)"
                    " VALUES (?,?,?,?)", (crn, i, bas, bas + 110))
con.commit(); con.close(); db.connect(config.USER_DB, "schema_user.sql").close()

from itucap import server
st = server.State(label="ben")
h = server.build(st, host="127.0.0.1", port=0); P = h.server_address[1]
threading.Thread(target=h.serve_forever, daemon=True).start(); time.sleep(0.4)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width":390,"height":844}, is_mobile=True, has_touch=True)
    hata = []
    pg.on("pageerror", lambda e: hata.append(str(e)[:160]))
    pg.goto(f"http://127.0.0.1:{P}/", wait_until="networkidle", timeout=30000)
    pg.wait_for_timeout(1800)
    pg.evaluate("() => gorunumAc('candSection')"); pg.wait_for_timeout(700)
    kart = pg.evaluate("""() => {
      const tr = [...document.querySelectorAll("#cands tbody tr[data-course]")];
      if(!tr.length) return {yok: true};
      const kesik = [...document.querySelectorAll("#cands td")].filter(e => {
        const r = e.getBoundingClientRect();
        return r.width > 0 && (r.right > innerWidth + 1 ||
               e.scrollWidth > e.clientWidth + 1); }).length;
      return {duzen: getComputedStyle(tr[0]).display,
              enYuksek: Math.round(Math.max(...tr.map(e =>
                e.getBoundingClientRect().height))),
              kesik, tasma: document.documentElement.scrollWidth - innerWidth}; }""")
    print("KART_DUZEN:" + str(kart.get("duzen")))
    print("KART_YUKSEK:" + str(kart.get("enYuksek")))
    print("KART_KESIK:" + str(kart.get("kesik")))
    print("KART_TASMA:" + str(kart.get("tasma")))
    # --- sekmeler: boşluk yutuluyor mu, kaç satır
    pg.evaluate("() => gorunumAc('schedSection')"); pg.wait_for_timeout(600)
    sek = pg.evaluate("""() => {
      const t = [...document.querySelectorAll("#tabs .tab")];
      if(t.length < 2) return {az: true};
      const ust = [...new Set(t.map(e =>
        Math.round(e.getBoundingClientRect().top)))];
      const sec = document.querySelector('#tabs .tab[aria-selected="true"]');
      const f = sec && sec.querySelector(".tabfark");
      let bosluk = null;
      if(f && f.firstChild){
        /* ⚠️ Boşluk `.tabfark`ın İÇİNDE (" · 20 kredi"), o yüzden kutuların
           arasını ölçmek 0 verir. Metin düğümünün 1. karakterinden
           başlayan aralığı ölçüyoruz: boşluk yutulduysa 0, durursa >0. */
        const et = sec.querySelector(".tabmetin").firstChild;
        const r1 = document.createRange();
        r1.setStart(et, 0); r1.setEnd(et, et.length);
        const r2 = document.createRange();
        r2.setStart(f.firstChild, 1); r2.setEnd(f.firstChild, f.firstChild.length);
        bosluk = Math.round((r2.getBoundingClientRect().left -
                             r1.getBoundingClientRect().right) * 10) / 10;
      }
      const kisa = t.filter(e => e.getAttribute("aria-selected") !== "true"
        && e.id !== "karsilastir")
        .map(e => (e.innerText||"").replace(/\s+/g," ").trim().length);
      return {sayi: t.length, satir: ust.length, bosluk,
              secilmeyenUzunluk: Math.max(0, ...kisa)}; }""")
    print("SEKME_SAYI:" + str(sek.get("sayi")))
    print("SEKME_SATIR:" + str(sek.get("satir")))
    print("SEKME_SECILMEYEN:" + str(sek.get("secilmeyenUzunluk")))
    print("SEKME_BOSLUK:" + str(sek.get("bosluk")))
    # --- dokunma hedefleri (bütün görünümler)
    kucuk = []
    for gid in pg.evaluate("() => acikGorunumler().map(([id]) => id)"):
        pg.evaluate("(x) => gorunumAc(x)", gid); pg.wait_for_timeout(300)
        kucuk += pg.evaluate("""() => [...document.querySelectorAll(
            'button, [role="button"], summary, select, input[type=checkbox], .ray a')]
          .filter(e => { const r = e.getBoundingClientRect();
            return r.width > 0 && r.height > 0 && r.height < 32
              && !(e.closest("label") &&
                   e.closest("label").getBoundingClientRect().height >= 32); })
          .map(e => (e.id || e.className || e.tagName).toString().split(" ")[0]
            + Math.round(e.getBoundingClientRect().height))""")
    print("KUCUK34:" + (",".join(sorted(set(kucuk))) if kucuk else "-"))
    # --- içerik ekranın neresinde başlıyor (kabuk bedeli)
    # ⚠️ Karşılama kartı kapatılıyor: ilk kurulum kartı BİLEREK uzun ve
    # bu ölçüm onu değil, KABUĞU (başlık + paneller) ölçüyor.
    pg.evaluate("""() => { try{ localStorage.setItem("heroKapali","1"); }catch(e){}
      const h = document.querySelector("#hero"); if(h) h.hidden = true;
      if(typeof renderSonraki === "function") renderSonraki(); }""")
    pg.wait_for_timeout(400)
    bas = []
    for gid in ("candSection", "panels", "tierSection"):
        pg.evaluate("(x) => gorunumAc(x)", gid); pg.evaluate("() => scrollTo(0,0)")
        pg.wait_for_timeout(300)
        bas.append(pg.evaluate("(id) => Math.round(document.getElementById(id)"
                               ".getBoundingClientRect().top + scrollY)", gid))
    print("BOLUM_BASI:" + ",".join(str(x) for x in bas))
    print("HATA:" + ("|".join(hata[:3]) if hata else "-"))
    b.close()
h.shutdown()
'''


def test_UCTAN_UCA_telefon(tmp_path, monkeypatch):
    """★★ 390px'te gerçek sayfa: aday kartları, sekme satırı, hedef boyu ve
    içeriğin başladığı yer."""
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
                       text=True, timeout=300)
    if r.returncode != 0:
        pytest.fail(r.stderr[-1500:])
    c = dict(s.split(":", 1) for s in r.stdout.strip().splitlines()
             if ":" in s and s.split(":", 1)[0].isupper())
    assert c["KART_DUZEN"] == "grid", f"aday satırı telefonda kart değil: {c}"
    assert int(c["KART_YUKSEK"]) < 220, f"kart hâlâ çok uzun: {c}"
    assert c["KART_KESIK"] == "0", f"hücre kesiliyor: {c}"
    assert int(c["KART_TASMA"]) <= 1, f"sayfa yana taşıyor: {c}"
    if c.get("SEKME_SATIR") not in (None, "None"):
        # ★ Asıl değişiklik: seçili OLMAYAN sekme artık yalnız "Öneri 2".
        # Kredi ve ayırt edici metin `.tabfark` içinde, o da telefonda
        # yalnız seçili sekmede görünüyor (Faz 46 kararı).
        # ⚠️ "tek satır" ölçütü VERİYE bağlı (gerçek veride 3 öneri tek
        # satıra sığdı, bu yapmacık veride seçili sekmenin ayırt edici
        # metni daha uzun) — o yüzden satır sayısına ÜST SINIR koyuyoruz,
        # asıl güvence kısa etiket.
        assert int(c["SEKME_SECILMEYEN"]) <= 12, \
            f"seçili olmayan sekme hâlâ uzun: {c}"
        assert int(c["SEKME_SATIR"]) <= 2, f"sekmeler üç satıra yayılmış: {c}"
        assert float(c["SEKME_BOSLUK"]) > 0.5, \
            f"esnek kutu sekmedeki boşluğu yutuyor ('20KREDİ'): {c}"
    assert c["KUCUK34"] == "-", f"34px altı dokunma hedefi: {c['KUCUK34']}"
    assert all(int(x) < 330 for x in c["BOLUM_BASI"].split(",")), \
        f"içerik hâlâ çok aşağıda başlıyor: {c}"
    assert c["HATA"] == "-", f"JS hatası: {c['HATA']}"
