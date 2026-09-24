#!/usr/bin/env python3
"""Repoya kişisel veri sızmış mı? — CI'da her itmede koşar.

Bu araç bir öğrencinin **notlarını** tutuyor. Repo herkese açık olduğu için
en pahalı hata, bir transkriptin ya da veritabanının yanlışlıkla commit
edilmesi. `.gitignore` bunu engelliyor ama tek savunma olarak yeterli değil:

* yeni bir dosya adı deseni eklenir, `.gitignore` güncellenmeyi unutur,
* `git add -f` ile bilerek eklenen bir dosya sessizce kalır,
* bir belgeye örnek diye gerçek bir transkript satırı yapıştırılır.

★ Bu denetim `.gitignore`a **güvenmiyor**: dosya sisteminde ne varsa ona
bakıyor ve git'in izlediği dosyaları ayrıca sorguluyor. Kendi kendini
doğrulayan bir savunma, kurulumuna güvenen bir savunmadan iyidir.

★★ Dosya ADI yetmez — dosyanın İÇİ de denetleniyor.

22.08.2026'da statik site ilk kurulduğunda yayınlanan katalogda kullanıcının
kendi denklik beyanları çıktı (`equivalence.confidence='user_declared'`).
Dosya adı masumdu (`katalog.sqlite3.gz`), sızıntı içerideydi. `.gitignore`
böyle bir şeyi hiçbir zaman yakalayamaz. O yüzden `site/` kurulduysa
veritabanının içeriği de taranıyor.

Kullanım:
    python tools/gizlilik_denetimi.py          # 0 = temiz, 1 = sızıntı var
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Adı bu kalıplara uyan dosya repoda ASLA olmamalı.
YASAK_ADLAR = [
    "data/user.sqlite3", "data/user.sqlite3-wal", "data/user.sqlite3-shm",
    "data/reference.sqlite3", "data/itucap.html",
    "config/settings.toml", "config/denklikler.toml",
]
YASAK_KALIPLAR = [
    re.compile(r"^transkript.*\.txt$"),
    re.compile(r"^data/yedek/"),
    re.compile(r"^data/(ituhelper|raw_archive)/"),
    re.compile(r"\.transkript$"),
]

# Metin içinde aranan desenler. Belgelerde ÖRNEK sayı olabilir; burada
# aradığımız, transkript BİÇİMİ — "KOD 123E  AA" gibi kod+not çiftleri.
TRANSKRIPT_SATIRI = re.compile(
    r"^\s*[A-Z]{2,4}\s?\d{3}[A-Z]?\s+(AA|BA\+?|BB\+?|CB\+?|CC\+?|DC\+?|DD\+?|FF|VF|BL|BZ)\s*$",
    re.MULTILINE)

# Denetlenecek metin dosyası uzantıları.
METIN = {".md", ".txt", ".toml", ".py", ".html", ".yml", ".yaml", ".json"}


def izlenen_dosyalar() -> list[str] | None:
    """Git'in izlediği dosyalar. Git reposu değilse None."""
    try:
        out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                             text=True, check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return [line for line in out.splitlines() if line]


# Dizini ayakta tutan boş işaretçiler — içleri yok, sızıntı taşıyamazlar.
IZINLI = {".gitkeep", ".gitignore"}


def yasak_mi(yol: str) -> str | None:
    if pathlib.PurePosixPath(yol).name in IZINLI:
        return None
    if yol in YASAK_ADLAR:
        return "kişisel dosya"
    for kalip in YASAK_KALIPLAR:
        if kalip.search(yol):
            return "kişisel dosya kalıbı"
    return None


def site_denetle() -> list[str]:
    """Kurulmuş `site/` klasörü — yayınlanacak veri temiz mi?

    Katalog herkese açık olmalı. İçinde kullanıcıya ait tek bir satır bile
    olmamalı: kimin hangi dersi aldığı ya da ne saydırdığı kişisel veri.
    """
    import gzip
    import sqlite3
    import tempfile

    site = ROOT / "site"
    gz = site / "katalog.sqlite3.gz"
    if not gz.exists():
        return []
    sorunlar: list[str] = []

    # Kişisel yapılandırma siteye hiç girmemeli.
    for ad in ("settings.toml", "denklikler.toml"):
        if (site / "config" / ad).exists():
            sorunlar.append(f"  ❌ site/config/{ad} — kişisel yapılandırma yayında")
    if (site / "data").exists() or (site / "user.sqlite3").exists():
        sorunlar.append("  ❌ site/ içinde kullanıcı veritabanı var")

    with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as fh:
        fh.write(gzip.decompress(gz.read_bytes()))
        yol = fh.name
    try:
        con = sqlite3.connect(yol)
        n = con.execute(
            "SELECT COUNT(*) FROM equivalence WHERE confidence='user_declared'"
        ).fetchone()[0]
        if n:
            sorunlar.append(
                f"  ❌ katalogda {n} adet KİŞİSEL denklik beyanı "
                f"(equivalence.confidence='user_declared')")
        # Yerel dosya yolları kullanıcı adını sızdırır.
        n = con.execute(
            "SELECT COUNT(*) FROM equivalence WHERE source_url LIKE '/home/%' "
            "OR source_url LIKE '/Users/%'").fetchone()[0]
        if n:
            sorunlar.append(f"  ❌ katalogda {n} kayıtta yerel dosya yolu var")
        # Öğrenci tabloları referans şemasında yok; varsa yanlış DB yayınlanmış.
        for t in ("student", "earned_course", "slot_fulfillment", "term_pick"):
            try:
                c = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            except sqlite3.OperationalError:
                continue
            sorunlar.append(f"  ❌ katalogda '{t}' tablosu var ({c} satır) — "
                            f"kullanıcı veritabanı yayınlanmış olabilir")
        con.close()
    finally:
        pathlib.Path(yol).unlink(missing_ok=True)
    return sorunlar


def main() -> int:
    sorunlar: list[str] = []

    dosyalar = izlenen_dosyalar()
    kaynak = "git ls-files"
    if dosyalar is None:
        # Git reposu değil — dosya sistemine bak. `.venv` ve `data` hariç.
        kaynak = "dosya sistemi"
        dosyalar = [
            str(p.relative_to(ROOT)) for p in ROOT.rglob("*")
            if p.is_file() and not any(
                part in {".venv", ".git", "__pycache__", ".pytest_cache"}
                for part in p.parts)
        ]

    for yol in dosyalar:
        sebep = yasak_mi(yol)
        if sebep:
            sorunlar.append(f"  ❌ {yol}  ({sebep})")

    # Metin içinde transkript satırı var mı?
    for yol in dosyalar:
        p = ROOT / yol
        if p.suffix not in METIN or not p.exists():
            continue
        if yol.startswith("tools/gizlilik_denetimi"):
            continue                       # kendi desenlerimiz
        try:
            metin = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for eslesme in TRANSKRIPT_SATIRI.finditer(metin):
            satir = metin[:eslesme.start()].count("\n") + 1
            sorunlar.append(
                f"  ❌ {yol}:{satir}  transkript satırı gibi: "
                f"{eslesme.group().strip()!r}")

    site_sorunlari = site_denetle()
    sorunlar.extend(site_sorunlari)

    print(f"Gizlilik denetimi — {len(dosyalar)} dosya ({kaynak})"
          + ("  + kurulmuş site" if (ROOT / "site" / "katalog.sqlite3.gz").exists()
             else ""))
    if sorunlar:
        print("\nSIZINTI:\n" + "\n".join(sorunlar))
        print("\nBu dosyalar kişisel veri içerebilir ve herkese açık bir repoda")
        print("durmamalı. `git rm --cached <dosya>` ile çıkar, `.gitignore`a ekle.")
        print("⚠️  Zaten itilmişse geçmişten de temizlenmeli (git-filter-repo).")
        return 1
    print("✅ Kişisel veri bulunmadı.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
