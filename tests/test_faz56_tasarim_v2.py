"""Faz 56 — tasarım sistemi v2: çıkarım, tek kaynak, ölçek denetimi.

Kullanıcı 23.09.2026: *"Extract the design system from this codebase and
make a new design system. improve every aspect of this site and make it
more usable and useful."*

Çıkarım (`tools/tasarim_envanteri.py`) v1 sisteminin söylediğiyle kodun
yaptığını karşılaştırdı:

| | v1 sistemi | kodda (önce) | v2 (sonra) |
|---|---|---|---|
| yazı boyu | 9, taban 10.5px | **21** değer, 8.5px'e kadar | **10** jeton, taban 11px (+grafik 10px) |
| harf aralığı | 6 | **14** | **6** jeton |
| yazı ailesi yığını | 3 | **20** bildirim, 3 ayrı mono yığını | **3** jeton |
| aralık | 2px ızgarası | 55 dolgu / 24 boşluk değeri, 3·5·7·9·11·13·15px | ölçek + denetim |
| palet | jeton | **4 elle kopya** (2 kez ayrıştı) | **1 kaynak**, 4 blok üretiliyor |

Vitrin verisiyle (gerçekçi, uydurma öğrenci — `tools/vitrin.py`) yapılan
ekran taramasında çıkan kullanılabilirlik bulguları:

  ★★ Telefonda gün listesi meşgul saatleri ÇİZMİYORDU: cuma 13:30–17:30
     "staj" masaüstünde taralı bir bloktu, telefonda cuma "boş" yazıyordu.
  ★★ Önerilen programın bir şubesi 70/70 DOLUYDU; ızgarada hiçbir işaret
     yoktu (doluluk yalnız aday listesinde görünüyordu).
  ★  "yer yok" (derslik ilan edilmemiş) kayıt gününde "kontenjan dolu" diye
     okunuyordu.
  ★  Gece temasında onay kutusu, açılır liste ve kaydırma çubuğu AÇIK
     çiziliyordu (`color-scheme` yoktu).
  ★  "Ne değişti" damgayı ISO olarak basıyordu: `2026-09-22T17:00:45`.
  ★  Özet satırının lejantı ikinci programı `var(--cap)`e sabitlemişti —
     yandal öğrencisi amber bir "yandal" noktası görüyordu.
  ★  "İçeriğe atla" yoktu.
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


from itucap import tasarim as T                               # noqa: E402
from itucap import ui as UI                                   # noqa: E402

KAYNAK = pathlib.Path(UI.__file__).read_text(encoding="utf-8")
ARACLAR = pathlib.Path(UI.__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(ARACLAR))
HTML = UI.render({})
CSS = re.search(r"<style>(.*?)</style>", HTML, re.S).group(1)


def _kod(metin: str) -> str:
    return re.sub(r"/\*.*?\*/", " ", metin, flags=re.S)


# ============================================================ 1. tek kaynak
def test_PALET_SABLONDA_ELLE_YAZILMIYOR():
    """★★ Palet dört yerde elle kopyalanmıştı ve iki kez ayrıştı (Faz 38b:
    `--yandal*` unutuldu; Faz 43: iki jeton üç bloğa tek tek eklendi).
    Şablonda artık TEK bir renk tanımı bile yok — hepsi `tasarim.py`den."""
    t0 = KAYNAK.index('_TEMPLATE = r"""')
    sablon = _kod(KAYNAK[t0:])
    tanim = re.findall(r"--[a-z0-9-]+\s*:\s*#[0-9A-Fa-f]{3,8}", sablon)
    assert not tanim, f"şablonda elle yazılmış renk jetonu: {tanim[:4]}"
    assert "__JETONLAR__" in KAYNAK and "__JETONLAR_KAGIT__" in KAYNAK
    assert "__JETONLAR" not in HTML, "yer tutucu çözülmemiş"


def test_URETILEN_bloklar_dort_ve_her_biri_TAM():
    """Gece, medya-gündüz, açık-gündüz, kâğıt: her biri paletin tamamı."""
    palet = set(T.palet("gece"))
    bloklar = {
        "gece": re.search(r"(?m)^:root\{(.*?)\n\}", CSS, re.S),
        "medya": re.search(r"@media \(prefers-color-scheme:light\)\{(.*?)\n  \}", CSS, re.S),
        "acik": re.search(r':root\[data-theme="light"\]\{(.*?)\n\}', CSS, re.S),
        "kagit": re.search(r"@media print\{.*?\n  :root\{(.*?)\}", CSS, re.S),
    }
    for ad, m in bloklar.items():
        assert m, f"{ad} bloğu üretilmemiş"
        jeton = set(re.findall(r"--([a-z0-9-]+):", m.group(1)))
        assert palet <= jeton, f"{ad}: eksik {sorted(palet - jeton)}"


def test_COLOR_SCHEME_iki_temada_da():
    """★ Gece temasında yerel denetimler (onay kutusu, açılır liste, kaydırma
    çubuğu) açık çiziliyordu — koyu kartın ortasında bembeyaz bir kare."""
    gece = re.search(r"(?m)^:root\{(.*?)\n\}", CSS, re.S).group(1)
    assert "color-scheme:dark" in gece
    assert CSS.count("color-scheme:light") >= 3, "gündüz blokları + kâğıt"


def test_TAKMA_ADLAR_var_olan_jetona_bakiyor():
    palet = set(T.palet("gece"))
    for ad, hedef, _ in T.TAKMA_ADLAR:
        assert hedef in palet, f"{ad} → olmayan {hedef}"
        assert f"--{ad}:var(--{hedef})" in CSS


def test_MODUL_saf_ve_import_aninda_dosya_okumuyor():
    """Pyodide paketine giriyor (`ui` onu içeri alıyor): yalnız standart
    kütüphane, import anında dosya yok — Faz 38 ve 43'ün tuzağı."""
    kaynak = pathlib.Path(T.__file__).read_text(encoding="utf-8")
    importlar = re.findall(r"(?m)^(?:from|import) ([\w.]+)", kaynak)
    assert set(importlar) <= {"__future__"}, importlar
    assert "open(" not in kaynak and "read_text" not in kaynak
    import site_kur
    assert "tasarim" in site_kur.ENGINE


def test_OLCUM_ARACLARI_ayni_kaynagi_okuyor():
    """Kontrast ve ton merdiveni artık `tasarim`dan okuyor — CSS'in
    KAYNAĞINI, kopyasını değil."""
    import kontrast_olcumu as K
    import ton_merdiveni as M
    assert K.palet()["gece"]["ink-3"] == T.palet("gece")["ink-3"]
    assert M.palet()["gündüz"]["--seal"] == T.palet("gunduz")["seal"]
    ciftler = {(a, b) for a, b, _t, _n in K.CIFTLER}
    for yuzey in ("ground", "surface", "surface-2", "seal-soft"):
        assert ("border-control", yuzey) in ciftler, yuzey
    assert ("danger", "surface") in ciftler and ("warn", "surface") in ciftler


# ============================================================ 2. ölçek
def test_OLCEK_DENETIMI_temiz():
    """★★ Bir kerelik temizlik yetmez: her faz yeni bir `12.5px` ekleyebilir.
    Elle yazılan CSS ve satır içi stiller v2 ölçeğinin dışına çıkamaz."""
    import tasarim_envanteri as E
    bulgu = E.denetle()
    assert not bulgu, "\n".join(bulgu[:12])


def test_DENETIM_gercekten_yakaliyor():
    """Muhafızın muhafızı: ölçek dışı bir değer eklenince denetim kırmızı."""
    import tasarim_envanteri as E
    eski = E.sablon
    try:
        css, govde = eski()
        E.sablon = lambda: (css + "\n.x{font-size:12.5px;padding:7px}",
                            govde + '<i style="color:#ff0000"></i>')
        bulgu = " ".join(E.denetle())
    finally:
        E.sablon = eski
    assert "font-size:12.5px" in bulgu and "7px" in bulgu and "#ff0000" in bulgu


def test_TANIMLI_renk_jetonu_KULLANILIYOR():
    """★ `--seal-hover` Faz 43'ten beri tanımlıydı ve HİÇ kullanılmıyordu:
    birincil düğmenin üzerine gelmesi hâlâ opaklıkla yapılıyordu — tam da
    jetonun önlemek için eklendiği şey. Tanımlı renk jetonu ölü kalamaz.
    (Aralık/çizgi/hedef ölçekleri bilerek hariç: onlar değer olarak yazılıp
    `--denetle` ile ölçeğe bağlanıyor.)"""
    t0 = KAYNAK.index('_TEMPLATE = r"""')
    sablon = KAYNAK[t0:]
    adlar = (list(T.palet("gece")) + [a for a, _, _ in T.TAKMA_ADLAR]
             + [a for a, _, _ in T.KAGIT_EK] + [a for a, _, _ in T.YAZI_BOYU]
             + [a for a, _, _ in T.AILELER] + [a for a, _, _ in T.KATMAN])
    olu = [a for a in adlar if f"var(--{a})" not in sablon]
    assert not olu, f"tanımlı ama kullanılmayan jeton: {olu}"
    kural = re.search(r"\.ghost\.primary:hover\{([^}]*)\}", _kod(CSS)).group(1)
    assert "seal-hover" in kural and "opacity" not in kural, kural


def test_BLOK_ICI_yazi_yalniz_INK():
    """★★ Ton merdiveniyle ölçüldü (en kötü basamak): blok adı `-ink` %85
    opaklıkta 3.80:1, saat · yer · CRN satırı `ink-2` ile 3.09:1 — taban
    4.5. v1 sistemi kuralı yazmıştı, kod almamıştı."""
    duz = _kod(CSS)
    for secici in (r"\.blkad", r"\.blk small", r"\.daylist \.row small"):
        kural = re.search(r"(?m)^" + secici + r"\{([^}]*)\}", duz).group(1)
        assert "opacity" not in kural, (secici, kural)
        assert "ink-2" not in kural and "ink-3" not in kural, (secici, kural)
    import ton_merdiveni as M
    yazi, _z, _a = M.olc(M.MERDIVEN)
    assert yazi >= 4.5, yazi


def test_DURUM_rengi_ROL_rengi_degil():
    """v1'de ✓, "tamam", "programda" doğrudan `--anadal` yazıyordu: rol
    (hangi program) ile durum (sağlandı mı) aynı adı taşıyordu."""
    duz = _kod(CSS)
    for secici in (r"\.check\.ok \.mark", r"\.ozet\.ok", r"\.gaugebar \.track i\.ok"):
        kural = re.search(r"(?m)^" + secici + r"\{([^}]*)\}", duz).group(1)
        assert "var(--ok)" in kural and "anadal" not in kural, (secici, kural)
    assert ">programda</span>" in KAYNAK and 'color:var(--ok)">programda' in KAYNAK


def test_yazi_TABANI_11px():
    """v1 "10.5px taban" diyordu ama kodda 8.5/9/9.5/10px vardı. v2'de akan
    metin ≥11px; 10px YALNIZ grafik ekseni ve sayaçta (`--fs-2xs`)."""
    boylar = {a: int(d[:-2]) for a, d, _ in T.YAZI_BOYU}
    assert min(v for k, v in boylar.items() if k != "fs-2xs") == 11
    # ⚠️ Şablonun elle yazılan CSS'i, üretilen sayfa DEĞİL: gömülü yazı
    # tiplerinin base64'ü üstünde `[^{}]+\{` geri izlemesi 4 dakika sürüyordu.
    import tasarim_envanteri as E
    kullanan = [m.group(1) for m in re.finditer(r"([^{}]*)\{([^{}]*)\}", _kod(E.sablon()[0]))
                if "font-size:var(--fs-2xs)" in m.group(2)]
    assert kullanan, "fs-2xs hiç kullanılmıyor — jeton gereksiz mi?"
    for secici in kullanan:
        assert "nd" in secici or "online" in secici, f"fs-2xs metinde: {secici.strip()}"


def test_h2_govdeden_BUYUK():
    """★ Bölüm başlığı gövdeyle aynı 15px'ti; tek ayrım ağırlıktı."""
    h2 = re.search(r"(?m)^h2\{([^}]*)\}", CSS).group(1)
    assert int(T.coz(h2).split("font-size:")[1].split("px")[0]) > 15


# ============================================================ 3. tasarım sistemi dışa aktarımı
def test_JETONLAR_JSON_tasarim_sistemi_bicimine_uyuyor():
    """Design System artifact'ının okuduğu biçim: her aile `{"tokens": […]}`,
    adlar `[A-Za-z0-9][A-Za-z0-9_.-]*` ve aileler arasında TEK; renk değeri
    hex ya da var olan bir jetona takma ad."""
    j = T.jetonlar_json()
    adlar = []
    for aile, govde in j.items():
        if aile in ("name", "version", "type"):
            continue
        for t in govde["tokens"]:
            assert re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", t["name"]), t
            assert t.get("usage"), f"kullanım notu yok: {t['name']}"
            adlar.append(t["name"])
    assert len(adlar) == len(set(adlar)), "aynı ad iki ailede"
    renkler = {t["name"] for t in j["color"]["tokens"]}
    for t in j["color"]["tokens"]:
        v = t["value"]
        if isinstance(v, str) and v.startswith("{"):
            assert v[1:-1] in renkler, t
        else:
            for tema in (v.values() if isinstance(v, dict) else [v]):
                assert re.fullmatch(r"#[0-9A-Fa-f]{6}|rgba\([^()]*\)", tema), t
    assert {f["family"] for f in j["type"]["fonts"]} == {"Geist", "Geist Mono"}  # Faz 133


# ============================================================ 4. kullanılabilirlik (kaynak)
def test_YER_YOK_kalkti_TEK_soz():
    """★ "yer yok" kayıt gününde "kontenjan dolu" diye okunuyordu."""
    from itucap import recommend as REC
    assert '"yer yok"' not in _kod(KAYNAK), "kodda eski söz duruyor"
    assert REC._building_label("undeclared") == "yer bildirilmedi"
    # Faz 93: yardımcı artık buluşmanın kendisini alıyor (bina + derslik);
    # yeri olmayanın sözü aynı kaldı.
    assert 'return b ? (r ? `${b} ${r}` : b) : "yer bildirilmedi";' in KAYNAK


def test_YER_DURUMU_esigi_doluluk_ile_AYNI():
    """Aynı şube iki yerde iki durumda görünmesin: 0 → dolu, ≤3 → son N."""
    yd = re.search(r"function yerDurumu\(sec\)\{(.*?)\n\}", KAYNAK, re.S).group(1)
    dl = re.search(r"function doluluk\(sections\)\{(.*?)\n\}", KAYNAK, re.S).group(1)
    assert "bos === 0" in yd and "bos <= 3" in yd
    assert 'bos === 0 ? "full" : (bos <= 3 ? "tight"' in dl


def test_ACIKLAMA_esnek_satirda_DEGIL():
    """★ Bölüm açıklamaları esnek `.summary` içindeydi: her `<b>` ayrı öğe
    oldu ve Kademeler'de "Çizgiler önşart bağıdır" cümlenin ortasında kendi
    satırına kırıldı. Düz yazı taşıyan `.summary` kalmamalı."""
    t0 = KAYNAK.index('_TEMPLATE = r"""')
    for m in re.finditer(r'<div class="summary"(?: id="[^"]*")?>([^<]*)', KAYNAK[t0:]):
        assert not m.group(1).strip(), f"düz yazı esnek satırda: {m.group(1)[:50]!r}"
    assert KAYNAK[t0:].count('<div class="aciklama">') >= 5
    kural = re.search(r"(?m)^\.aciklama\{([^}]*)\}", _kod(CSS)).group(1)
    assert "display" not in kural, "açıklama yine esnek/ızgara yapılmış"


def test_ICERIGE_ATLA_var():
    assert '<a class="atla" href="#icerik">İçeriğe atla</a>' in KAYNAK
    assert ".atla:focus{top:var(--sp-4)}" in CSS


# ============================================================ 5. uçtan uca (vitrin)
_CANLI = r'''
import os, sys, re
sys.path.insert(0, os.environ["ITUCAP_TOOLS"])
import vitrin
adres, h = vitrin.ac()
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width":1400,"height":1000}, color_scheme="dark")
    pg = ctx.new_page()
    pg.goto(adres, wait_until="networkidle", timeout=30000); pg.wait_for_timeout(1200)
    pg.evaluate("() => { gorunumAc('schedSection'); }"); pg.wait_for_timeout(200)
    print("SEMA:" + pg.evaluate("() => getComputedStyle(document.documentElement).colorScheme"))
    print("BASLIK_H:" + str(pg.evaluate("() => Math.round(document.querySelector('.prgbaslik').getBoundingClientRect().height)")))
    # Dolu ve az yerli şubeyi programa koy (deney düzeneği: veride biri 70/70,
    # öbürü 58/60) ve ızgarayı yeniden çiz.
    pg.evaluate("""() => { sel = sel.map(x => x.course === 'GEO 331E' ? {...x, crn: '13603'}
        : x.course === 'BLG 222E' ? {...x, crn: '22305'} : x); render(); }""")
    pg.wait_for_timeout(200)
    print("DOLU:" + pg.evaluate("""() => [...document.querySelectorAll('#grid .blk')]
        .filter(e => e.querySelector('.yerdurum.dolu')).map(e => e.dataset.course).sort().join(',')"""))
    print("AZ:" + pg.evaluate("""() => [...document.querySelectorAll('#grid .blk .yerdurum.az')]
        .map(e => e.textContent.trim()).join(',')"""))
    print("BLOK_YAZI:" + str(pg.evaluate("""() => [...document.querySelectorAll('#grid .blk:not(.mesgul)')]
        .every(b => { const c = getComputedStyle(b).color;
          return [...b.querySelectorAll('small, .blkad')].every(e => getComputedStyle(e).color === c
            && getComputedStyle(e).opacity === '1'); })""")))
    print("OZET_DOLU:" + pg.evaluate("() => (document.querySelector('.ozetdolu')||{}).textContent || ''").replace("\n", " "))
    print("YUK:" + str(pg.evaluate("() => !!document.querySelector('#schedSummary .yuk[role=img]')")))
    # Yandal öğrencisi: lejant noktası yandal renginde.
    print("LEJANT:" + pg.evaluate("""() => { const e = DATA.seconds; DATA.seconds = [{kind:'yandal',
        role:'YANDAL', label:'yandal', program:'X'}]; render();
        const h = document.querySelector('.ozetlejant').innerHTML; DATA.seconds = e; render(); return h.includes('var(--yandal)') && !h.includes('var(--cap)') ? 'yandal' : h; }"""))
    pg.evaluate("() => gorunumAc('tierSection')"); pg.wait_for_timeout(200)
    print("ACIKLAMA:" + pg.evaluate("""() => { const d = document.querySelector('#tierSection .aciklama');
        return d ? getComputedStyle(d).display : '-'; }"""))
    pg.evaluate("() => gorunumAc('changeSection')"); pg.wait_for_timeout(200)
    print("DEGISTI:" + pg.evaluate("() => document.querySelector('#changeWhen').textContent"))
    # İçeriğe atla: ilk Tab görünür bağlantıya, Enter odağı <main>e.
    pg.evaluate("() => { document.activeElement && document.activeElement.blur(); window.scrollTo(0,0); }")
    pg.keyboard.press("Tab"); pg.wait_for_timeout(100)
    print("ATLA:" + pg.evaluate("""() => { const a = document.activeElement;
        return a.className + '|' + (a.getBoundingClientRect().top >= 0); }"""))
    pg.keyboard.press("Enter"); pg.wait_for_timeout(100)
    print("MAIN:" + pg.evaluate("() => document.activeElement.id + '|' + location.hash"))
    ctx.close()
    ctx = b.new_context(viewport={"width":390,"height":844}, is_mobile=True, has_touch=True,
                        color_scheme="light")
    pg = ctx.new_page()
    pg.goto(adres, wait_until="networkidle", timeout=30000); pg.wait_for_timeout(1200)
    pg.evaluate("() => gorunumAc('schedSection')"); pg.wait_for_timeout(200)
    print("TEL_SEMA:" + pg.evaluate("() => getComputedStyle(document.documentElement).colorScheme"))
    print("TEL_CUMA:" + pg.evaluate("""() => { const s = [...document.querySelectorAll('#daylist section')][4];
        return [...s.querySelectorAll('.row')].map(r => r.className.replace('row','').trim() + '=' + r.textContent.replace(/\s+/g,' ').trim().slice(0,30)).join(' | ') || s.textContent; }"""))
    print("TEL_TASMA:" + str(pg.evaluate("() => document.documentElement.scrollWidth - innerWidth")))
    b.close()
h.shutdown()
'''


def test_UCTAN_UCA_vitrin(tmp_path):
    try:
        import playwright  # noqa: F401
    except ImportError:
        pytest.skip("playwright yok")
    import os
    env = dict(os.environ, ITUCAP_TOOLS=str(ARACLAR))
    betik = tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, dir=str(tmp_path))
    betik.write(_CANLI); betik.close()
    r = subprocess.run([sys.executable, betik.name], capture_output=True, text=True,
                       timeout=240, env=env)
    if r.returncode != 0:
        if "Executable doesn't exist" in r.stderr or "BrowserType.launch" in r.stderr:
            pytest.skip("tarayıcı başlatılamadı")
        pytest.fail(r.stderr[-1500:])
    c = dict(s.split(":", 1) for s in r.stdout.strip().splitlines()
             if ":" in s and s.split(":", 1)[0].isupper())
    assert c["SEMA"] == "dark" and c["TEL_SEMA"] == "light", c
    assert int(c["BASLIK_H"]) < 50, f"başlık/kip/sekme satırı sarmış: {c['BASLIK_H']}px"
    assert c["DOLU"] == "GEO 331E", f"dolu şube ızgarada işaretlenmedi: {c['DOLU']}"
    # ⚠️ Faz 57: vitrin artık mevzuat dosyalarını da taşıyor; GNO'dan gelen
    # 25 kredilik sınır açılış önerisine bir ders daha (son 1 yerli) ekledi.
    # Ölçülen şey rozetin ÇİZİLMESİ: BLG 222E'nin şubesi "son 2" olmalı.
    az = c["AZ"].split(",")
    assert "son 2" in az and all(re.fullmatch(r"son [123]", x) for x in az), c["AZ"]
    assert c["BLOK_YAZI"] == "True", "blok içi yazı -ink'ten sapmış (renk ya da opaklık)"
    assert "GEO 331E" in c["OZET_DOLU"], c["OZET_DOLU"]
    assert c["YUK"] == "True"
    assert c["LEJANT"] == "yandal", f"yandal lejantı: {c['LEJANT']}"
    assert re.match(r"\d{2}\.\d{2}\.\d{4} \d{2}:\d{2} → \d{2}\.\d{2}\.\d{4} \d{2}:\d{2}",
                    c["DEGISTI"]), c["DEGISTI"]
    assert c["ACIKLAMA"] == "block", f"Kademeler açıklaması: {c['ACIKLAMA']}"
    assert c["ATLA"] == "atla|true", c["ATLA"]
    assert c["MAIN"] == "icerik|", f"odak <main>e geçmedi ya da adres kirlendi: {c['MAIN']}"
    assert "mesgul=staj" in c["TEL_CUMA"], f"telefonda cuma: {c['TEL_CUMA']}"
    assert int(c["TEL_TASMA"]) <= 1, c["TEL_TASMA"]
