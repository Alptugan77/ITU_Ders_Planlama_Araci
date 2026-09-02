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
          "student", "ui"]
SCHEMA = ["schema.sql", "schema_user.sql"]
# Herkese ait yapılandırma. `settings.toml` ve `denklikler.toml` KİŞİSEL —
# siteye girmiyor; ziyaretçininki tarayıcısında oluşuyor.
CONFIG = ["kurallar.toml", "katalog-duzeltmeleri.toml"]


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
    con.executemany("DELETE FROM plan WHERE id=?",
                    [(r[0],) for r in rows if r[0] not in keep])
    con.execute("DELETE FROM plan_slot WHERE plan_id NOT IN (SELECT id FROM plan)")
    con.execute("DELETE FROM pool_option WHERE slot_id NOT IN (SELECT id FROM plan_slot)")
    stats["plan"] = f"{len(rows)} → {len(keep)}"
    stats["cift"] = len(groups)

    # Tarama geçmişi ve kalite raporları tarayıcıda kullanılmıyor.
    for t in ("lesson_snapshot", "snapshot_run", "ingest_run", "quality_finding",
              "prereq_unparsed", "prereq_repair", "obs_program_ref",
              "plan_host_program"):
        try:
            con.execute(f"DELETE FROM {t}")
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

    # ★ Kabuk: AYNI şablon, verisi sonradan yükleniyor.
    shell = UI.render({}, deferred=True)
    shell = shell.replace("</head>", f'{_LOADER_CSS}</head>', 1)
    shell = shell.replace("<body>", f"<body>{_loader_html(UI)}", 1)
    shell = shell.replace("</body>", f'<script src="./app.js"></script></body>', 1)
    (SITE / "index.html").write_text(shell, encoding="utf-8")
    shutil.copy(ROOT / "web" / "app.js", SITE / "app.js")

    (SITE / "manifest.json").write_text(json.dumps({
        "engine": ENGINE, "config": CONFIG, "schema": SCHEMA,
        "pyodide": {"version": PYODIDE_VERSION,
                    "local": bool(pyodide_dir and pyodide_dir.exists())},
        "catalog": {"file": "katalog.sqlite3.gz", "bytes": gz, "raw": raw,
                    **{k: str(v) for k, v in stats.items()}},
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
    print(f"   plan {stats['plan']} (yalnız yürürlükteki iterasyon)")
    print(f"   not dağılımı {stats.get('notdagilimi', 0)} ders "
          f"(`make notdagilimi` ile artar; katalog boyutunu büyütür)")
    print(f"   dene: python -m http.server -d {SITE} 8000")
    return SITE


_LOADER_CSS = """
<style>
#yukleniyor{position:fixed;inset:0;z-index:99;display:flex;align-items:center;
  justify-content:center;background:var(--ground);color:var(--ink)}
#yukleniyor .kutu{max-width:460px;padding:0 24px}
#yukleniyor .yukAd{font-size:30px;margin:8px 0 0;line-height:1.05;
  font-family:"Chivo",Helvetica,Arial,sans-serif;font-weight:900}
#yukleniyor .yukAd .kurum{color:var(--ink-3)}
#yukleniyor .acilim{margin:6px 0 16px}
#yukleniyor p{color:var(--ink-2);font-size:13.5px;line-height:1.65}
#yukleniyor .adim{font-family:"IBM Plex Mono",monospace;font-size:12px;
  color:var(--ink-3);margin-top:14px;min-height:18px}
#yukleniyor .cubuk{height:3px;background:var(--surface-2);margin-top:10px;
  overflow:hidden}
#yukleniyor .cubuk i{display:block;height:100%;width:0;background:var(--seal);
  transition:width .3s ease}
#yukleniyor .gizli{color:var(--anadal);font-weight:600}
</style>
"""


def _loader_html(UI) -> str:
    """Yükleme ekranı — ad TEK KAYNAKTAN (ui.AD_*). Eskiden "İTÜ ÇAP · YANDAL /
    Ders planlama" elle yazılıydı ve ad değişince (İTÜ DEPAR) burada eski
    kalıyordu. Artık uygulama başlığıyla aynı: kurum + kısaltma + vurgulu açılım.
    """
    return f"""
<div id="yukleniyor"><div class="kutu">
  <h1 class="yukAd"><span class="kurum">{UI.AD_KURUM}</span> {UI.AD_KISA}</h1>
  <div class="acilim">{UI.acilim_html()}</div>
  <p><span class="gizli">Notların tarayıcından çıkmıyor.</span>
     Bu sitenin sunucusu yok: hesap senin cihazında yapılıyor, girdiğin
     notlar yalnız bu tarayıcıda saklanıyor. Yayınlanan tek veri herkese
     açık ders kataloğu.</p>
  <div class="cubuk"><i id="yukCubuk"></i></div>
  <div class="adim" id="yukAdim">başlıyor…</div>
</div></div>
"""


if __name__ == "__main__":
    pyo = None
    if len(sys.argv) > 1:
        pyo = Path(sys.argv[1])
    build(pyo)
