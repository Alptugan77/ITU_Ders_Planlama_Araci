"""Elle bildirilen denklikler (`config/denklikler.toml`).

OBS'de bu ÇAP çifti için yayınlanmış denklik yok (D3). Kullanıcının kendi
bildiği denklikler burada, VERSİYONLANABİLİR bir dosyada tutulur ve her
`make refresh` sırasında yeniden uygulanır — böylece `make clean` sonrası da
kaybolmaz.

★★ FAZ 28 — BUNLAR KİŞİSEL VERİ. Bu dosya eskiden "kişisel veri DEĞİL
(müfredat bilgisi)" diyor ve referans veritabanına yazıyordu; oysa
`tools/gizlilik_denetimi.py` yayınlanan katalogda `confidence='user_declared'`
görürse HATA veriyordu. Aynı soruya iki kaynak farklı cevap veriyordu — bu
projenin tekrar eden hata sınıfı — ve denetim haklıydı: "şu dersim şunun
yerine saysın" beyanı, hangi dersleri aldığını ve neye başvurduğunu ele
verir. Artık `user.sqlite3`'e yazılıyor, `confidence='user_declared'` ile
işaretleniyor ve arayüzde "resmi" denkliklerden ayrılıyor.
"""
from __future__ import annotations

import sqlite3
import tomllib
from pathlib import Path

from . import config, db
from .normalize import normalize_course_code

DEFAULT_PATH = config.ROOT / "config" / "denklikler.toml"
# ★ Katalog düzeltmeleri KİŞİSEL DEĞİL: OBS'nin ders kataloğundaki hataları
# beyan ederler, kimin transkriptiyle ilgileri yoktur. O yüzden ayrı bir
# dosyada ve repoya girerler — herkes aynı hatayla karşılaşıyor.
CATALOG_PATH = config.ROOT / "config" / "katalog-duzeltmeleri.toml"


def load_file(path: Path | None = None) -> list[dict]:
    path = path or DEFAULT_PATH
    if not path.exists():
        return []
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    out = []
    for item in raw.get("denklik", []):
        target = normalize_course_code(item.get("hedef", ""))
        sources = [normalize_course_code(s) for s in item.get("kaynak", []) if s]
        if not target or not sources:
            continue
        out.append({
            "target": target,
            "sources": sources,
            "min_grade": (item.get("min_not") or "DD").upper(),
            "plan_type": item.get("plan"),
            "note": item.get("not_", ""),
        })
    return out


def load_waivers(path: Path | None = None) -> dict[str, str]:
    """Önşart muafiyetleri: {ders: gerekçe}.

    Denklikten farklı — elde bir karşılık dersi yok, sadece "bu önşart benden
    aranmıyor" beyanı var. Motor bu dersleri sağlanmış sayar.
    """
    path = path or DEFAULT_PATH
    if not path.exists():
        return {}
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for item in raw.get("muafiyet", []):
        note = item.get("not_", "muafiyet beyanı")
        for code in item.get("dersler", []):
            code = normalize_course_code(code)
            if code:
                out[code] = note
    return out


def waiver_grades(path: Path | None = None) -> dict[str, str]:
    """Muafiyetleri kural motoruna verilebilir {ders: not} biçiminde döndürür.

    'MU' (muaf) = 4.0, böylece MIN AA dahil her eşiği geçer.
    """
    return {code: "MU" for code in load_waivers(path)}


def load_prereq_overrides(path: Path | None = None) -> dict[str, dict]:
    """Katalogdaki önşart METNİNİ değiştiren beyanlar: {ders: {...}}.

    Denklik ve muafiyetten farklı. Bunlar öğrenciyle ilgili değil — **kaynak
    verisinin bozuk** olduğunun beyanı. OBS bazı derslerde önşart alanına
    önşart yazmıyor (ders adı, dil adı gibi). Ayrıştırıcı haklı olarak
    çözemiyor ve motor "BİLİNMİYOR" diyor; oysa doğrusu çoğu zaman
    "önşart yok".

    ⚠️ `onsart = ""` → önşart YOK demektir, "bilinmiyor" değil. Bu bir
    iddiadır: yanlışsa alınamayacak bir ders alınabilir görünür. O yüzden her
    beyan bir `not_` ile gerekçelendirilir ve arayüzde kaynağıyla gösterilir.
    """
    path = path or CATALOG_PATH
    if not path.exists():
        return {}
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for item in raw.get("onsart_beyani", []):
        code = normalize_course_code(item.get("ders", ""))
        if not code:
            continue
        out[code] = {
            "text": str(item.get("onsart") or "").strip(),
            "note": str(item.get("not_") or "beyan"),
        }
    return out


def apply(con: sqlite3.Connection, path: Path | None = None) -> int:
    """Beyan edilen denklikleri KULLANICI veritabanına yazar. Idempotent.

    ★★ Faz 28 — hedef DB değişti: `reference.sqlite3` yerine
    `user.sqlite3`. Çağıranların hepsi artık `ucon` geçiyor; parametre adı
    `con` olarak kaldı çünkü işlev hangi bağlantıyı verirsen ona yazıyor.
    Gerekçe `schema_user.sql`'de ve `rules.load_equivalences`'ta.
    """
    con.execute(
        """DELETE FROM equivalence_source WHERE equivalence_id IN
             (SELECT id FROM equivalence WHERE confidence='user_declared')""")
    con.execute("DELETE FROM equivalence WHERE confidence='user_declared'")
    items = load_file(path)
    for item in items:
        cur = con.execute(
            """INSERT INTO equivalence(target_course,target_plan_id,applies_to_cap,
                                       confidence,note_raw,source_url,scraped_at)
               VALUES (?,NULL,1,'user_declared',?,?,?)""",
            (item["target"],
             f"BEYAN: {', '.join(item['sources'])} -> {item['target']}. {item['note']}".strip(),
             str(path or DEFAULT_PATH), db.now()),
        )
        for code in item["sources"]:
            con.execute(
                """INSERT OR IGNORE INTO equivalence_source(equivalence_id,course_code,min_grade)
                   VALUES (?,?,?)""", (cur.lastrowid, code, item["min_grade"]))
    con.commit()
    return len(items)


def remove(target: str, path: Path | None = None) -> bool:
    """Bir beyanı dosyadan siler. `apply()` sonra çağrılmalı.

    ★ Geri alınabilirlik güvenliğin parçası: arayüzden tek tıkla denklik
    uygulanabiliyorsa, tek tıkla kaldırılabilmeli de. Yanlış bir denklik
    tamamlamadığın bir şartı tamamlanmış gösterir; kullanıcı hatasını fark
    ettiğinde dosyayı elle düzenlemek zorunda kalmamalı.

    Dosya satır bazlı düzenleniyor — yorumlar ve `[[muafiyet]]` blokları
    olduğu gibi kalıyor.
    """
    path = path or DEFAULT_PATH
    if not path.exists():
        return False
    target = normalize_course_code(target)
    lines = path.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    i = 0
    removed = False
    while i < len(lines):
        if lines[i].strip() != "[[denklik]]":
            out.append(lines[i])
            i += 1
            continue
        block_end = i + 1
        while block_end < len(lines) and not lines[block_end].strip().startswith("[["):
            block_end += 1
        block = lines[i:block_end]
        hedef = ""
        for line in block:
            if line.strip().startswith("hedef"):
                hedef = normalize_course_code(line.split("=", 1)[1].strip().strip('"'))
        if hedef == target and not removed:
            removed = True
            while out and not out[-1].strip():      # bloğun önündeki boş satır
                out.pop()
        else:
            out.extend(block)
        i = block_end
    if removed:
        path.write_text("\n".join(out).rstrip("\n") + "\n", encoding="utf-8")
    return removed


def append(target: str, sources: list[str], min_grade: str = "DD",
           note: str = "", path: Path | None = None) -> Path:
    """Yeni bir beyanı dosyaya ekler (CLI için)."""
    path = path or DEFAULT_PATH
    lines = [
        "",
        "[[denklik]]",
        f'hedef   = "{normalize_course_code(target)}"',
        "kaynak  = [" + ", ".join(f'"{normalize_course_code(s)}"' for s in sources) + "]",
        f'min_not = "{min_grade.upper()}"',
    ]
    if note:
        lines.append(f'not_    = "{note}"')
    with path.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return path


def temizle_referans(con: sqlite3.Connection) -> int:
    """Referans DB'de kalmış ESKİ beyan satırlarını siler (Faz 28 göçü).

    ★ Faz 28'den önce beyanlar `reference.sqlite3`'e yazılıyordu. O satırlar
    artık okunmuyor (`rules.load_equivalences` referans DB'deki
    `user_declared` kayıtlarını her durumda atlıyor) ama DURUYORLAR — ve
    o dosya yayınlanan sitenin içine giriyor. Kalıntıyı bırakmak, "okumuyoruz
    ki" diyerek kişisel veriyi yayınlamak olurdu.

    ⚠️ Kayıp yok: beyanların asıl kaynağı `config/denklikler.toml`;
    `apply()` onu kullanıcı DB'sine yeniden yazıyor.
    """
    try:
        n = con.execute(
            "SELECT COUNT(*) FROM equivalence WHERE confidence='user_declared'"
        ).fetchone()[0]
    except sqlite3.Error:
        return 0
    if not n:
        return 0
    con.execute(
        """DELETE FROM equivalence_source WHERE equivalence_id IN
             (SELECT id FROM equivalence WHERE confidence='user_declared')""")
    con.execute("DELETE FROM equivalence WHERE confidence='user_declared'")
    con.commit()
    return n
