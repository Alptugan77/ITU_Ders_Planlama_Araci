#!/usr/bin/env python3
"""Statik site üretici — GitHub Pages için.

    python tools/site_kur.py            # site/ klasörünü kurar
    python -m http.server -d site 8000  # yerelde dene

## Neden Pyodide

Motorun tamamı **standart kütüphane** kullanıyor (`sqlite3`, `re`, `tomllib`,
`dataclasses`). Tarama modülleri (`httpx`, `selectolax`) motorda değil,
`sources/` altında. Bu yüzden motor JavaScript'e ÇEVRİLMEDEN tarayıcıda
çalışabiliyor: Pyodide, CPython'un WebAssembly derlemesi.

Çevirmek yerine taşımanın karşılığı somut:

* **Tek kod tabanı.** Önşart ayrıştırıcısı, puanlama, mevzuat kuralları tek
  yerde. JS'e çevirseydik iki motor olurdu ve bir kural birinde düzelip
  öbüründe düzelmezdi — üstelik hangisinin doğru olduğunu kimse bilmezdi.
* **Aynı testler.** 439 test web sürümünü de kapsıyor, çünkü aynı kod.
* **Bakım.** Mevzuat değişince `config/kurallar.toml` değişiyor; iki dilde
  iki kez uygulanmıyor.

Bedeli ~2.5s'lik ilk yükleme (Pyodide) — dönemde birkaç kez açılan bir araç
için kabul edilebilir.

## Gizlilik — sitenin varlık sebebi

★ Bu site **sunucusuz**. Ziyaretçinin notları:

* tarayıcısında hesaplanır (Pyodide sanal dosya sisteminde bir SQLite),
* tarayıcısında saklanır (IndexedDB),
* **hiçbir yere gönderilmez** — sunucu yok, uç yok, istek yok.

Yayınlanan tek veri herkese açık ders kataloğu. Bu yüzden site tutulacak
kişisel veri üretmiyor: sızdıracak bir veritabanı yok.
"""
from __future__ import annotations

import gzip
import json
import re
import shutil
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"

# ★★ PYODIDE SÜRÜMÜ — TEK KAYNAK.
#
# 22.08.2026'da site yayında `ModuleNotFoundError: No module named 'sqlite3'`
# ile açılmadı. Sebep sürüm karışıklığıydı: yerelde `pyodide@latest` (314.x)
# ile test etmiştim, `app.js` ise CDN'de **0.28.3**'ü işaret ediyordu. İki
# ayrı çalışma ortamı:
#
#   0.28.3  → sqlite3 stdlib'de YOK, ayrı bir wheel olarak yükleniyor
#   314.x   → sqlite3 stdlib'e VENDOR EDİLMİŞ (python_stdlib.zip içinde)
#
# Motor `import sqlite3` ile ayakta; ilk sürümde açılış anında patlıyordu.
#
# Ders: **test edilen sürüm, yayınlanan sürüm olmalı.** Sürüm artık burada
# tek yerde duruyor; `app.js` onu manifest'ten okuyor, GitHub Actions da
# buradan alıyor. `tests/test_site.py` üçünün aynı kaldığını kilitliyor.
#
# Bu sürüm sqlite3'ü vendor ettiği için ek bir paket indirmeye gerek yok —
# çalışma anında CDN'e istek atmamak da gizlilik sözümüzün parçası.
PYODIDE_VERSION = "314.0.5"

# Tarayıcıya giden motor modülleri. Tarama (`sources/`, `pipeline`, `http`) ve
# masaüstüne özgü olanlar (`watch` — macOS bildirimi) DIŞARIDA: hem gereksiz
# hem bağımlılık taşıyorlar.
ENGINE = ["__init__", "basvuru", "changes", "config", "db", "declared",
          "discover", "normalize", "notlar", "plans", "policy", "prereq",
          "progress", "recommend", "rules", "sequence", "server",
          "student", "tasarim", "ui", "yolharitasi"]
SCHEMA = ["schema.sql", "schema_user.sql"]
# Herkese ait yapılandırma. `settings.toml` ve `denklikler.toml` KİŞİSEL —
# siteye girmiyor; ziyaretçininki tarayıcısında oluşuyor.
CONFIG = ["kurallar.toml", "katalog-duzeltmeleri.toml"]


def _gereken_planlar(con: sqlite3.Connection) -> set[int]:
    """Her (anadal × ÇAP/yandal programı) çifti için yerel aracın "otomatik"
    seçeceği plan — `plans.ikinci_plan`in KENDİSİYLE hesaplanıyor ki site ile
    yerel araç ayrışamasın (17 bin çağrı, ~1 sn)."""
    sys.path.insert(0, str(ROOT / "src"))
    from itucap import plans as PL

    eski, con.row_factory = con.row_factory, sqlite3.Row
    try:
        anadallar = [r[0] for r in con.execute(
            "SELECT DISTINCT program_code FROM plan WHERE plan_type='lisans'")]
        out: set[int] = set()
        for tip in ("cap", "yandal"):
            hedefler = [r[0] for r in con.execute(
                "SELECT DISTINCT program_code FROM plan WHERE plan_type=?", (tip,))]
            for h in hedefler:
                for a in anadallar:
                    p = PL.ikinci_plan(con, h, tip, a)
                    if p is not None:
                        out.add(p)
        return out
    finally:
        con.row_factory = eski


def prune(src: Path, dst: Path) -> dict:
    """Katalogdan tarayıcıya gerekmeyeni atar.

    ★ En büyük kazanç eski plan iterasyonları: OBS aynı program için yıl
    aralığı başına ayrı plan tutuyor ve yürürlükte olan yalnız biri.
    Hepsini indirmek ziyaretçiye kullanmayacağı veriyi ödetirdi.
    """
    shutil.copy(src, dst)
    con = sqlite3.connect(dst)
    stats = {}

    # ★★ Gruplama anahtarına HOST DAHİL — 22.08.2026'da eksik ÇAP programı
    # şikâyetinin sebebi buydu.
    #
    # ÇAP planları (anadal, hedef) ÇİFTİNE göre tanımlı: `TUMMUH_BLG`,
    # `INS_BLG`, `MAK_BLG`… Hepsi `program_code='BLG'`. Anahtar yalnız
    # (program, tip) olunca 27 farklı çift tek plana iniyordu: İnşaat
    # öğrencisi kendi `INS_BLG` planını sitede HİÇ bulamıyordu.
    #
    # Gerçek veride etkisi: 527 çift → 63. Planların %88'i siteye girmiyordu.
    # İterasyon seçimi hâlâ doğru (aynı çiftin yıl aralıkları arasından
    # yürürlükte olanı) ama artık ÇİFT BAŞINA yapılıyor.
    rows = con.execute(
        "SELECT id,program_code,plan_type,iteration,host_program_code FROM plan"
    ).fetchall()
    groups: dict[tuple, list] = {}
    for pid, prog, ptype, it, host in rows:
        groups.setdefault((host or "", prog, ptype), []).append((pid, it or ""))

    def rank(x):
        pid, it = x
        m = re.search(r"(\d{4})\s*-\s*\d{4}", it)
        # 'Sonrası' = açık uçlu, yürürlükte olan. Yoksa en yeni yıl aralığı.
        return (1 if "Sonras" in it else 0, int(m.group(1)) if m else 0, pid > 0, pid)

    keep = {max(items, key=rank)[0] for items in groups.values()}
    # ★★ FAZ 54 — otomatik seçimin İHTİYAÇ DUYDUĞU planlar da kalıyor.
    # Çift başına "yürürlükteki iterasyon" yetmiyor: aynı çiftin YENİ
    # iterasyonunun bağlı programlar listesi bazen bir anadalı DÜŞÜRÜYOR
    # (ör. `TUMMUH_MAD` 2023: ELE yok, 2018: ELE var). Yeni olanı tutup eskiyi
    # atınca o anadalın öğrencisi sitede başka bölümün planına düşüyordu —
    # yerel araçla site FARKLI plan seçiyordu (ölçüm: bu düzeltme olmadan
    # 5437 çiftin 272'si). Yerelin seçeceği her planı tutmak, ikisini
    # birebir aynı yapıyor.
    keep |= _gereken_planlar(con)
    con.executemany("DELETE FROM plan WHERE id=?",
                    [(r[0],) for r in rows if r[0] not in keep])
    con.execute("DELETE FROM plan_slot WHERE plan_id NOT IN (SELECT id FROM plan)")
    con.execute("DELETE FROM pool_option WHERE slot_id NOT IN (SELECT id FROM plan_slot)")
    stats["plan"] = f"{len(rows)} → {len(keep)}"
    stats["cift"] = len(groups)

    # Tarama geçmişi ve kalite raporları tarayıcıda kullanılmıyor.
    for t in ("lesson_snapshot", "snapshot_run", "ingest_run", "quality_finding",
              "prereq_unparsed", "prereq_repair", "obs_program_ref"):
        try:
            con.execute(f"DELETE FROM {t}")
        except sqlite3.OperationalError:
            pass
    # ★★★ FAZ 54 — `plan_host_program` SİLİNİYORDU, ama motor onu KULLANIYOR.
    #
    # `plans.ikinci_plan` "otomatik" ÇAP/yandal planını öğrencinin ANADALINA
    # uygun planlar arasından seçiyor (ilk kullanıcı incelemesi A3) ve bunu
    # bu tablodan okuyor. Tablo boşken süzgeç hiçbir şey bulamıyor, kural
    # gereği süzmeden devam ediyor ve EN YENİ planı seçiyordu — hangi bölüm
    # için olursa olsun. Ölçüldü (23.09.2026): anadalına uygun planı olan
    # 5437 (anadal × ikinci program) çiftinin **1802'sinde (%33)** site başka
    # bölümün planını seçiyordu; HTAE + BLG → `ROS_BLG` (doğrusu `TUMMUH_BLG`).
    # A3 düzeltmesi yerelde çalışıyor, yayınlanan sitede HİÇ çalışmamıştı.
    # Yalnız kalan planların satırları tutuluyor (~5,5 bin satır).
    try:
        con.execute("DELETE FROM plan_host_program WHERE plan_id NOT IN (SELECT id FROM plan)")
    except sqlite3.OperationalError:
        pass

    # ★★ KİŞİSEL VERİ — `reference.sqlite3` "herkese açık katalog" diye
    # tasarlandı ama `declared.apply()` kullanıcının KENDİ denklik beyanlarını
    # buraya yazıyor (`confidence='user_declared'`). Yerelde sorun değil;
    # yayınlanınca "bu kişi GEO 220E aldı ve MAT 210E yerine saydırıyor"
    # demek olur — hangi dersleri aldığını ve ne talep ettiğini açık eder.
    #
    # İlk kurulumda gözden kaçtı ve sitede göründü. `.gitignore` bunu
    # yakalayamazdı: sızıntı dosya adında değil, dosyanın İÇİNDE.
    # Bu yüzden `tools/gizlilik_denetimi.py` artık kurulan siteyi de tarıyor.
    n = con.execute(
        "SELECT COUNT(*) FROM equivalence WHERE confidence='user_declared'"
    ).fetchone()[0]
    con.execute("""DELETE FROM equivalence_source WHERE equivalence_id IN
                     (SELECT id FROM equivalence WHERE confidence='user_declared')""")
    con.execute("DELETE FROM equivalence WHERE confidence='user_declared'")
    stats["kisisel_denklik_silindi"] = n

    # `source_url` yerel dosya yollarını taşıyor (/home/kullanici/...) —
    # kullanıcı adını sızdırır. Yayında gereksiz.
    try:
        con.execute("UPDATE equivalence SET source_url=NULL WHERE source_url LIKE '/%'")
    except sqlite3.OperationalError:
        pass
    con.commit()
    con.execute("VACUUM")
    # ★ Faz 38 — not dağılımı yayınlanan katalogu BÜYÜTÜYOR. 176 ders ~0,5 MB
    # ekledi; bütün katalog (`--hepsi`) çekilirse büyüme onlarca kat olur.
    # Sessiz büyüme, bir gün "site neden 30 MB" sorusuna cevapsız bırakırdı.
    try:
        stats["notdagilimi"] = con.execute(
            "SELECT COUNT(DISTINCT course_key) FROM grade_distribution").fetchone()[0]
    except sqlite3.OperationalError:
        stats["notdagilimi"] = 0
    stats["ders"] = con.execute("SELECT COUNT(*) FROM course").fetchone()[0]
    stats["sube"] = con.execute("SELECT COUNT(*) FROM lesson").fetchone()[0]
    stats["donem"] = (con.execute(
        "SELECT term FROM lesson WHERE term IS NOT NULL LIMIT 1").fetchone()
        or ("?",))[0]
    con.close()
    return stats


def _check_pyodide(d: Path) -> None:
    """Paketlenen Pyodide beklediğimiz sürüm mü ve sqlite3 içeriyor mu?

    ★ İkinci kontrol, yayını bir kez düşüren hatanın kendisi. `import sqlite3`
    motorun her modülünde var; stdlib'de yoksa site açılış anında ölüyor ve
    bunu ancak tarayıcıda fark ediyoruz. Kurulum sırasında bakmak bedava.
    """
    import zipfile

    meta = d / "package.json"
    if meta.exists():
        v = json.loads(meta.read_text(encoding="utf-8")).get("version")
        if v != PYODIDE_VERSION:
            raise SystemExit(
                f"❌ pyodide sürümü uyuşmuyor: paket {v}, beklenen "
                f"{PYODIDE_VERSION}.\n"
                f"   Test edilen sürüm ile yayınlanan sürüm aynı olmalı.\n"
                f"   npm install pyodide@{PYODIDE_VERSION}")
    stdlib = d / "python_stdlib.zip"
    if stdlib.exists():
        with zipfile.ZipFile(stdlib) as z:
            if not any(n.startswith("sqlite3/") for n in z.namelist()):
                raise SystemExit(
                    f"❌ pyodide {PYODIDE_VERSION} sqlite3'ü vendor etmiyor.\n"
                    "   Motor `import sqlite3` ile ayakta; site açılmaz.\n"
                    "   sqlite3'ü vendor eden bir sürüm seç ya da wheel'i "
                    "pakete ekle.")


def build(pyodide_dir: Path | None = None) -> Path:
    sys.path.insert(0, str(ROOT / "src"))
    from itucap import ui as UI

    ref = ROOT / "data" / "reference.sqlite3"
    if not ref.exists():
        raise SystemExit(f"❌ katalog yok: {ref}\n   Önce `make refresh` çalıştır.")

    if SITE.exists():
        shutil.rmtree(SITE)
    (SITE / "itucap").mkdir(parents=True)
    (SITE / "config").mkdir()

    for name in ENGINE:
        shutil.copy(ROOT / "src" / "itucap" / f"{name}.py",
                    SITE / "itucap" / f"{name}.py")
    for name in SCHEMA:
        shutil.copy(ROOT / "src" / "itucap" / name, SITE / "itucap" / name)
    for name in CONFIG:
        shutil.copy(ROOT / "config" / name, SITE / "config" / name)

    tmp = SITE / "_katalog.sqlite3"
    stats = prune(ref, tmp)
    raw = tmp.stat().st_size
    (SITE / "katalog.sqlite3.gz").write_bytes(
        gzip.compress(tmp.read_bytes(), 9))
    tmp.unlink()
    gz = (SITE / "katalog.sqlite3.gz").stat().st_size

    (SITE / "index.html").write_text(kabuk(UI), encoding="utf-8")
    shutil.copy(ROOT / "web" / "app.js", SITE / "app.js")

    (SITE / "manifest.json").write_text(json.dumps({
        "engine": ENGINE, "config": CONFIG, "schema": SCHEMA,
        "pyodide": {"version": PYODIDE_VERSION,
                    "local": bool(pyodide_dir and pyodide_dir.exists())},
        "catalog": {"file": "katalog.sqlite3.gz", "bytes": gz, "raw": raw,
                    **{k: str(v) for k, v in stats.items()}},
        # ★★ FAZ 52 — İLERLEME ÇUBUĞU GERÇEK BAYTA BAĞLI. Eskiden adım
        # sayıyordu (6 adım, her biri %16,7); ölçüldü: yavaş bağlantıda
        # çubuk **68 saniye %16,7'de donuk** kaldı, sonra **%100'deyken
        # 4,7 sn** daha çalıştı. Adımlar eşit değil, çubuk da yalan
        # söylüyordu. Artık yükleyici hangi dosyadan kaç bayt beklediğini
        # buradan biliyor.
        "yuk": _beklenen_baytlar(pyodide_dir, SITE),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    # GitHub Pages Jekyll'i atlasın (alt çizgiyle başlayan dosyaları yer).
    (SITE / ".nojekyll").write_text("", encoding="utf-8")

    if pyodide_dir and pyodide_dir.exists():
        _check_pyodide(pyodide_dir)
        shutil.copytree(pyodide_dir, SITE / "pyodide")
        print(f"   pyodide {PYODIDE_VERSION} pakete alındı (CDN'e istek yok)")
    else:
        print(f"   ⚠️  pyodide paketlenmedi — çalışma anında CDN'den "
              f"({PYODIDE_VERSION}) indirilecek.")
        print("      Yayında bunu yapma: her ziyaretçi üçüncü tarafa istek atar.")

    print(f"✅ {SITE}")
    print(f"   katalog {raw/1e6:.1f} MB → gzip {gz/1e6:.1f} MB · "
          f"{stats['ders']} ders · {stats['sube']} şube · dönem {stats['donem']}")
    print(f"   plan {stats['plan']} (yürürlükteki iterasyon + otomatik seçimin gerektirdikleri)")
    print(f"   not dağılımı {stats.get('notdagilimi', 0)} ders "
          f"(`make notdagilimi` ile artar; katalog boyutunu büyütür)")
    print(f"   dene: python -m http.server -d {SITE} 8000")
    return SITE


def kabuk(UI) -> str:
    """Statik sitenin `index.html`i: AYNI şablon, verisi sonradan yükleniyor.

    ★★ FAZ 52 — iki sıra değişti, ikisi de ölçümden:
      · yazı tipleri SONDA (bkz. `UI.render` fontlar_sonda): ~200 KB/s'de
        yükleyiciden önce 571 KB iniyordu → 3 sn beyaz sayfa;
      · `app.js` yükleyicinin HEMEN ARKASINDA ve `async`: eskiden sayfanın en
        sonundaydı, yani Pyodide indirmesi 835 KB'lık HTML bitmeden
        BAŞLAMIYORDU. `async` betik indikçe çalışıyor; arayüzü beslemeden önce
        DOM'un bitmesini kendisi bekliyor (`domHazir`).
    Ayrı bir işlev, çünkü test bu sırayı `build()` çalıştırmadan doğruluyor.
    """
    shell = UI.render({}, deferred=True, fontlar_sonda=True)
    shell = shell.replace("</head>", f'{_LOADER_CSS}</head>', 1)
    return shell.replace(
        "<body>", f'<body>{_loader_html(UI)}'
                  f'<script src="./app.js" async></script>', 1)


# Pyodide'ın açılışta çektiği dosyalar (314.0.5 için ölçüldü, 21.09.2026):
# `pyodide.js` ve `pyodide.asm.mjs` <script> ile, gerisi `fetch` ile geliyor.
PYODIDE_DOSYALARI = ["pyodide.js", "pyodide.asm.mjs", "pyodide.asm.wasm",
                     "python_stdlib.zip", "pyodide-lock.json"]


def _beklenen_baytlar(pyodide_dir: Path | None, site: Path) -> dict:
    """Yükleyicinin indireceği her dosyanın boyu — çubuğun paydası.

    ⚠️ Anahtar, istek yolunun SONU: Pyodide pakete alınmadıysa CDN'den
    geliyor ve yolu farklı (`/pyodide/v314.0.5/full/…`); o yüzden Pyodide
    dosyaları yalnız ADIYLA tutuluyor. Pyodide bilinmiyorsa (paketlenmemiş
    ve yerelde yok) o dosyalar listede yok — yükleyici o bölümde adım
    kipine düşüyor, uydurma bir sayı göstermiyor.
    """
    dosyalar: dict[str, int] = {}
    if pyodide_dir and pyodide_dir.exists():
        for ad in PYODIDE_DOSYALARI:
            p = pyodide_dir / ad
            if p.exists():
                dosyalar[ad] = p.stat().st_size
    for alt in ("itucap", "config"):
        for p in sorted((site / alt).glob("*")):
            if p.is_file():
                dosyalar[f"{alt}/{p.name}"] = p.stat().st_size
    katalog = site / "katalog.sqlite3.gz"
    if katalog.exists():
        dosyalar[katalog.name] = katalog.stat().st_size
    return {"dosyalar": dosyalar, "toplam": sum(dosyalar.values())}


_LOADER_CSS = """
<style>
/* ★★ FAZ 52 — YÜKLEME EKRANI (kullanıcı 21.09.2026: "açılış ekranını
   güncelleyip yazıları büyütebilirsin — açılış ekranı dediğim yüklenme
   ekranı"). Ölçüm (önce):
     · izlenen tek satır (hangi adımda olduğu) 12px, GRİ, eş aralıklı,
     · çubuk 3px,
     · adımlar SAYILIYORDU, işler değil: yavaş bağlantıda çubuk 68 sn
       %16,7'de durdu, sonra %100'deyken 4,7 sn daha çalıştı.
   Şimdi: durum 19px ve koyu, çubuk 8px ve bayta bağlı, bayt + süre satırı,
   beş adımlık liste, hata olursa "Yeniden dene". */
#yukleniyor{position:fixed;inset:0;z-index:99;display:flex;align-items:center;
  justify-content:center;background:var(--ground);color:var(--ink);
  overflow:auto;padding:32px 20px}
#yukleniyor .kutu{width:100%;max-width:560px}
#yukleniyor .yukAd{font-size:clamp(40px,9vw,56px);margin:0;line-height:1;
  font-family:"Chivo",Helvetica,Arial,sans-serif;font-weight:900;
  letter-spacing:-.01em}
#yukleniyor .yukAd .kurum{color:var(--ink-3)}
#yukleniyor .acilim{font-size:14px;margin:12px 0 30px}
/* Durum: izlenen asıl şey — büyük, koyu, canlı bölge. */
#yukleniyor .yukAdim{font-size:19px;font-weight:600;line-height:1.35;
  color:var(--ink);min-height:26px}
#yukleniyor .cubuk{height:8px;background:var(--surface-2);margin-top:14px;
  overflow:hidden;position:relative;border:1px solid var(--border)}
#yukleniyor .cubuk i{display:block;height:100%;width:0;background:var(--seal);
  transition:width .35s ease}
/* Bayt akmıyor ama iş sürüyor (derleme, hesap): kayan şerit — çubuk
   donmuş görünmesin. İndirme sırasında YOK: orada hareket bayttan geliyor,
   sahte hareket takılmayı gizlerdi. */
#yukleniyor .cubuk.calisiyor::after{content:"";position:absolute;inset:0;
  background:linear-gradient(90deg,transparent,rgba(255,255,255,.4),transparent);
  animation:yukKay 1.4s linear infinite}
@keyframes yukKay{from{transform:translateX(-100%)}to{transform:translateX(100%)}}
#yukleniyor .yukSayi{font-family:"IBM Plex Mono",monospace;font-size:14px;
  color:var(--ink-2);margin-top:9px;min-height:20px;
  font-variant-numeric:tabular-nums}
#yukleniyor .yukUyari{font-size:15px;line-height:1.5;color:var(--warn-ink);
  margin-top:8px}
#yukleniyor .yukListe{list-style:none;margin:24px 0 0;padding:16px 0 0;
  border-top:1px solid var(--border);display:grid;gap:8px}
#yukleniyor .yukListe li{font-size:15px;color:var(--ink-3);display:flex;
  gap:10px;align-items:baseline}
/* ⚠️ İşaretler eş aralıklı yazı tipinde DEĞİL: IBM Plex Mono'da "✓" yok,
   yedek yazı tipi onu "√" gibi çiziyordu (ekran görüntüsünde görüldü). */
#yukleniyor .yukListe li::before{content:"○";width:1.1em;flex:none;
  font-family:system-ui,"Segoe UI Symbol","Apple Symbols","Noto Sans Symbols 2",
    sans-serif;font-weight:700}
#yukleniyor .yukListe li[data-durum="simdi"]{color:var(--ink);font-weight:600}
#yukleniyor .yukListe li[data-durum="simdi"]::before{content:"●";color:var(--seal)}
#yukleniyor .yukListe li[data-durum="bitti"]{color:var(--ink-2)}
#yukleniyor .yukListe li[data-durum="bitti"]::before{content:"✓";color:var(--anadal)}
#yukleniyor .yukListe li[data-durum="hata"]{color:var(--danger);font-weight:600}
#yukleniyor .yukListe li[data-durum="hata"]::before{content:"✕"}
#yukleniyor .yukListe .sure{margin-left:auto;font-weight:400;font-size:13px;
  color:var(--ink-3);font-family:"IBM Plex Mono",monospace}
#yukleniyor .gizlilik{font-size:16px;line-height:1.6;color:var(--ink-2);
  margin:26px 0 0}
#yukleniyor .gizlilik b{color:var(--anadal)}
#yukleniyor .yukHata{margin-top:20px;padding-top:14px;
  border-top:3px solid var(--danger)}
#yukleniyor .yukHata h2{font-size:21px;color:var(--danger);margin:0 0 6px}
#yukleniyor .yukHata p{font-size:15px;line-height:1.55;color:var(--ink-2);
  margin:0 0 12px}
#yukleniyor .yukHata code{font-family:"IBM Plex Mono",monospace;
  font-size:13.5px;display:block;white-space:pre-wrap;word-break:break-word;
  color:var(--ink);background:var(--surface-2);padding:8px 10px;margin:0 0 14px}
#yukleniyor .yukHata button{font:inherit;font-size:16px;font-weight:600;
  min-height:48px;padding:0 22px;background:var(--seal);color:var(--ground);
  border:0;cursor:pointer}
@media (prefers-reduced-motion:reduce){
  #yukleniyor .cubuk i{transition:none}
  #yukleniyor .cubuk.calisiyor::after{animation:none}}
/* Zorlanmış renk (Faz 51 dersi): dolu kısım ile kanal aynı renge düşmesin. */
@media (forced-colors:active){
  #yukleniyor .cubuk{border-color:CanvasText;background:Canvas}
  #yukleniyor .cubuk i{background:Highlight}
  #yukleniyor .cubuk.calisiyor::after{display:none}}
</style>
"""

# Adım adları app.js'teki `ASAMALAR` ile AYNI sırada — test ikisini eşliyor.
YUK_ASAMALARI = [("python", "Python çalışma ortamı"),
                 ("motor", "Motor dosyaları"),
                 ("katalog", "Ders kataloğu"),
                 ("veri", "Kayıtlı verin"),
                 ("hesap", "Programın hesaplanıyor")]


def _loader_html(UI) -> str:
    """Yükleme ekranı — ad TEK KAYNAKTAN (ui.AD_*). Eskiden "İTÜ ÇAP · YANDAL /
    Ders planlama" elle yazılıydı ve ad değişince (İTÜ DEPAR) burada eski
    kalıyordu. Artık uygulama başlığıyla aynı: kurum + kısaltma + vurgulu açılım.

    ★ Faz 52: ekran okuyucu için `role="status"` (adım değişince okunuyor)
    ve gerçek bir `role="progressbar"` (değeri app.js güncelliyor). Eskiden
    ikisi de yoktu — görmeyen kullanıcı 90 sn'lik bekleyişte hiçbir şey
    duymuyordu. Bayt satırı `aria-hidden`: saniyede iki kez değişiyor,
    okunsaydı gürültü olurdu.
    """
    adimlar = "".join(
        f'<li data-a="{a}" data-durum="bekliyor">{ad}<span class="sure"></span></li>'
        for a, ad in YUK_ASAMALARI)
    return f"""
<div id="yukleniyor" aria-busy="true"><div class="kutu">
  <h1 class="yukAd"><span class="kurum">{UI.AD_KURUM}</span> {UI.AD_KISA}</h1>
  <div class="acilim">{UI.acilim_html()}</div>
  <div class="yukAdim" id="yukAdim" role="status" aria-live="polite">Başlıyor…</div>
  <div class="cubuk" id="yukCubukKap" role="progressbar"
       aria-label="Yükleme ilerlemesi" aria-valuemin="0" aria-valuemax="100"
       aria-valuenow="0"><i id="yukCubuk"></i></div>
  <div class="yukSayi" id="yukSayi" aria-hidden="true"></div>
  <div class="yukUyari" id="yukUyari" hidden></div>
  <!-- Hata, durumun HEMEN ALTINDA: gizlilik notunun arkasında kalsaydı
       telefonda "Yeniden dene" ilk ekrandan taşabilirdi. -->
  <div class="yukHata" id="yukHata" hidden></div>
  <ol class="yukListe" id="yukListe">{adimlar}</ol>
  <p class="gizlilik"><b>Notların tarayıcından çıkmıyor.</b>
     Bu sitenin sunucusu yok: hesap senin cihazında yapılıyor, girdiğin
     notlar yalnız bu tarayıcıda saklanıyor. Yayınlanan tek veri herkese
     açık ders kataloğu.</p>
</div></div>
"""


if __name__ == "__main__":
    pyo = None
    if len(sys.argv) > 1:
        pyo = Path(sys.argv[1])
    build(pyo)
