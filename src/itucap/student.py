"""FAZ 3+4 — Öğrenci verisi: kayıt, transkript girişi, slot eşlemesi.

Gizlilik (WP1.9): bu modülün yazdığı her şey `data/user.sqlite3` içindedir —
referans veriden AYRI dosya, `.gitignore` kapsamında. OBS şifresi hiç istenmez.

Transkript girişi ELLE yapılır. Yazma yükünü azaltmak için `template()` planından
hazır bir kontrol listesi üretir; kullanıcı yalnızca not sütununu doldurur.
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from . import config, db
from .normalize import normalize_course_code
from .prereq import GRADE_POINTS, PASSING_MIN

# 'MAT 103E AA' | 'MAT103E,AA' | 'MAT 103E' | 'MAT 103E  BA+  2024-2025 Güz'
# ★ Not deseni ARTI notları da almalı (BA+, CC+ …) ve tek harfli
#   işaretleri de (M, T, E) — yönetmelik MADDE 20.
_LINE_RE = re.compile(
    r"^\s*(?P<code>[A-ZÇĞİÖŞÜ]{2,4}\s*\d{3,4}[A-Za-z]{0,2})"
    r"(?:\s*[,;|\t ]\s*(?P<grade>[A-Za-z]{1,2}\+?|--|\?)?)?"
    r"(?P<rest>.*)$",
    re.IGNORECASE,      # elle girişte küçük harf normal: 'mat 103e cc'
)
# Aynı desen ama satır başına BAĞLI DEĞİL: '(havuz: ...) -> GEO 413E AA' gibi
# kullanıcı yazımlarında kodu metnin içinden yakalamak için.
_LINE_SEARCH_RE = re.compile(
    r"\b(?P<code>[A-ZÇĞİÖŞÜ]{2,4}\s*\d{3,4}[A-Za-z]{0,2})"
    r"(?:\s*[,;|\t ]\s*(?P<grade>[A-Za-z]{1,2}\+?|--|\?)?)?"
    r"(?P<rest>.*)$",
    re.IGNORECASE,
)
IN_PROGRESS_MARKS = {"--", "?", "DEVAM", "ALIYORUM", "IP"}


@dataclass
class Entry:
    course_code: str
    grade: str | None
    status: str            # 'PASSED' | 'FAILED' | 'IN_PROGRESS'
    grade_known: bool
    note: str = ""


def make_entry(code: str, grade: str | None, note: str = "") -> Entry | None:
    """(ders, not) çiftinden kayıt — **tek karar noktası**.

    Hem metin girişi (`parse_line`) hem arayüz formu buradan geçiyor. İkisinin
    ayrı kural yazması, aynı girdinin nereden girildiğine göre farklı sonuç
    vermesi demek olurdu (Faz 8).
    """
    code = normalize_course_code(code)
    if not code:
        return None
    raw = (grade or "").strip().upper()
    if raw in IN_PROGRESS_MARKS or note.strip().upper() in IN_PROGRESS_MARKS:
        return Entry(code, None, "IN_PROGRESS", False, note)
    if not raw:
        # Not verilmedi -> "geçtim" varsayılır ama EN KÖTÜ DURUM (DD) alınır.
        # Böylece MIN CC gibi eşiklerde yanlışlıkla "alabilirsin" denmez.
        return Entry(code, "DD", "PASSED", False, note)
    if raw not in GRADE_POINTS:
        return Entry(code, None, "IN_PROGRESS", False, f"bilinmeyen not: {raw}")
    status = "PASSED" if GRADE_POINTS[raw] >= PASSING_MIN else "FAILED"
    return Entry(code, raw, status, True, note)


def parse_line(line: str) -> Entry | None:
    """Tek satırı çözer. Yorum (#) ve boş satır -> None."""
    text = line.split("#", 1)[0].strip()
    if not text:
        return None
    m = _LINE_RE.match(text)
    if not m:
        # Şablondaki havuz satırını kullanıcı '... -> GEO 413E AA' diye
        # doldurabiliyor. Baştan eşleşmezse metin içinde ilk ders kodunu ara.
        m = _LINE_SEARCH_RE.search(text)
    if not m:
        return None
    return make_entry(m.group("code"), m.group("grade"), (m.group("rest") or "").strip())


def parse_text(text: str) -> tuple[list[Entry], list[str]]:
    """Çok satırlı girdi -> (kayıtlar, çözülemeyen satırlar)."""
    entries: list[Entry] = []
    bad: list[str] = []
    for line in text.splitlines():
        if not line.split("#", 1)[0].strip():
            continue
        entry = parse_line(line)
        if entry is None:
            bad.append(line.strip())
        else:
            entries.append(entry)
    return entries, bad


# ------------------------------------------------------------------ kayıtlar
def ensure_student(ucon: sqlite3.Connection, label: str = "ben") -> int:
    row = ucon.execute("SELECT id FROM student WHERE label=?", (label,)).fetchone()
    if row:
        return row[0]
    cur = ucon.execute("INSERT INTO student(label, created_at) VALUES (?,?)",
                       (label, db.now()))
    ucon.commit()
    return cur.lastrowid


def enroll(ucon: sqlite3.Connection, student_id: int, plan_id: int, role: str,
           program_code: str) -> None:
    ucon.execute(
        """INSERT OR REPLACE INTO student_enrollment(student_id,plan_id,role,program_code)
           VALUES (?,?,?,?)""", (student_id, plan_id, role, program_code))
    ucon.commit()


def enrollments(ucon: sqlite3.Connection, student_id: int) -> list[sqlite3.Row]:
    return ucon.execute(
        """SELECT * FROM student_enrollment WHERE student_id=?
           ORDER BY CASE role WHEN 'ANADAL' THEN 0 WHEN 'CAP' THEN 1 ELSE 2 END""",
        (student_id,)).fetchall()


def add_entries(ucon: sqlite3.Connection, student_id: int, entries: list[Entry],
                term: str = "", replace: bool = False) -> int:
    if replace:
        ucon.execute("DELETE FROM earned_course WHERE student_id=?", (student_id,))
    for entry in entries:
        ucon.execute(
            """INSERT INTO earned_course(student_id,course_code,grade,term,status,source)
               VALUES (?,?,?,?,?,?)
               ON CONFLICT(student_id,course_code,term) DO UPDATE SET
                 grade=excluded.grade, status=excluded.status, source=excluded.source""",
            (student_id, entry.course_code, entry.grade, term, entry.status,
             _source_of(entry)),
        )
    ucon.commit()
    return len(entries)


def _source_of(entry: "Entry") -> str:
    """Kaynak etiketi. 'Devam ediyor' ile 'notu bilinmiyor' AYRI şeylerdir."""
    if entry.status == "IN_PROGRESS":
        return "manual-inprogress"
    return "manual" if entry.grade_known else "manual-nograde"


def grades(ucon: sqlite3.Connection, student_id: int,
           include_in_progress: bool = False) -> dict[str, str]:
    """Kural motoruna verilecek {ders: not} sözlüğü.

    Devam eden dersler varsayılan olarak DIŞARIDA — 'MIN FF' (dersi almış olmak)
    isteyen önşartlar için include_in_progress=True ile çağrılır.
    """
    query = "SELECT course_code, grade, status FROM earned_course WHERE student_id=?"
    out: dict[str, str] = {}
    for code, grade, status in ucon.execute(query, (student_id,)):
        if status == "PASSED" and grade:
            out[code] = grade
        elif status == "IN_PROGRESS" and include_in_progress:
            out[code] = "FF"          # alınmış ama başarı yok
    return out


def in_progress(ucon: sqlite3.Connection, student_id: int) -> set[str]:
    """★ Bu dönem ALDIĞIN dersler.

    Geçilmiş değiller, ama tekrar önerilmemeleri gerekiyor: motor bunları
    'henüz geçmemiş' diye adaya koyuyordu ve zaten programında olan dersi
    tekrar öneriyordu (21.08.2026'da bulundu).
    """
    return {r[0] for r in ucon.execute(
        "SELECT course_code FROM earned_course WHERE student_id=? AND status='IN_PROGRESS'",
        (student_id,))}


def graded(ucon: sqlite3.Connection, student_id: int) -> dict[str, str]:
    """GNO hesabı için {ders: not} — kalınan dersler DAHİL.

    Aynı ders birden çok kez alınmışsa **en yüksek** not sayılıyor: tekrar
    alan öğrenci notunu yükseltmiştir. (İTÜ'de son alınan not geçerlidir;
    dönem bilgisi transkriptte her zaman olmadığı için en yüksek notu
    kullanmak pratikte aynı sonucu veriyor ve dönemsiz girişte de çalışıyor.)
    """
    best: dict[str, str] = {}
    for code, grade, status in ucon.execute(
        """SELECT course_code, grade, status FROM earned_course WHERE student_id=?""",
        (student_id,)
    ):
        if status == "IN_PROGRESS" or not grade:
            continue
        have = best.get(code)
        if have is None or GRADE_POINTS.get(grade.upper(), -1) > GRADE_POINTS.get(have, -1):
            best[code] = grade.upper()
    return best


def uncertain_grades(ucon: sqlite3.Connection, student_id: int) -> list[str]:
    """Notu girilmemiş, DD varsayılan dersler — eşik hesabında riskli olanlar."""
    return [r[0] for r in ucon.execute(
        "SELECT course_code FROM earned_course WHERE student_id=? AND source='manual-nograde'"
        " ORDER BY course_code", (student_id,))]


def backup(ucon: sqlite3.Connection, student_id: int,
           stamp: str | None = None) -> Path | None:
    """★ Transkripti dosyaya yedekler; silici yazmadan ÖNCE çağrılır.

    Bu projedeki tek geri döndürülemez veri elle girilmiş transkript: OBS'den
    yeniden çekilemiyor, kullanıcı tek tek yazdı. Arayüzdeki "Kaydet" tam
    listeyi yazıyor (`replace=True`) — bir hata ya da yanlış tıklama her şeyi
    silebilirdi. Yedek ucuz, kayıp pahalı.

    Yedekler `data/yedek/` altında ve `.gitignore` kapsamında (kişisel veri).
    """
    rows = ucon.execute(
        """SELECT course_code, grade, status FROM earned_course
           WHERE student_id=? ORDER BY course_code""", (student_id,)).fetchall()
    if not rows:
        return None            # boş transkriptin yedeği anlamsız
    stamp = stamp or __import__("datetime").datetime.now().strftime("%Y%m%d-%H%M%S")
    folder = config.DATA_DIR / "yedek"
    folder.mkdir(parents=True, exist_ok=True)
    # ★ Damga saniye çözünürlüklü; aynı saniyede iki silici yazma olursa
    # ikinci yedek birinciyi SESSİZCE eziyordu — tam da önlemesi gereken
    # kaybı yaratıyordu (22.08.2026, test yakaladı).
    dest = folder / f"transkript-{stamp}.txt"
    n = 2
    while dest.exists():
        dest = folder / f"transkript-{stamp}-{n}.txt"
        n += 1
    lines = [f"# itucap transkript yedeği — {stamp}",
             "# geri yüklemek için:  make transcript FILE=" + str(dest), ""]
    for code, grade, status in rows:
        mark = "--" if status == "IN_PROGRESS" else (grade or "")
        lines.append(f"{code} {mark}".rstrip())
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dest


def prune_backups(keep: int = 20) -> int:
    """Eski yedekleri budar — klasör sonsuza kadar büyümesin."""
    folder = config.DATA_DIR / "yedek"
    if not folder.exists():
        return 0
    files = sorted(folder.glob("transkript-*.txt"), reverse=True)
    for path in files[keep:]:
        path.unlink(missing_ok=True)
    return max(0, len(files) - keep)


def backups() -> list[dict]:
    """Mevcut yedekler, yeniden eskiye."""
    folder = config.DATA_DIR / "yedek"
    if not folder.exists():
        return []
    out = []
    for path in sorted(folder.glob("transkript-*.txt"), reverse=True):
        entries, _bad = parse_text(path.read_text(encoding="utf-8"))
        out.append({"file": path.name, "courses": len(entries),
                    "stamp": path.stem.replace("transkript-", "")})
    return out


def restore(ucon: sqlite3.Connection, student_id: int, name: str) -> int:
    """Bir yedeği geri yükler.

    ★ Geri yükleme de silici bir yazma — ÖNCE mevcut hâlin yedeklenir.
    Yanlış yedeği seçen kullanıcı iki kez kaybetmesin.
    """
    folder = config.DATA_DIR / "yedek"
    path = folder / Path(name).name          # dizin çıkışı yok
    if path.parent != folder or not path.exists():
        raise ValueError(f"yedek bulunamadı: {name}")
    entries, _bad = parse_text(path.read_text(encoding="utf-8"))
    if not entries:
        raise ValueError("yedek boş görünüyor, geri yüklenmedi")
    backup(ucon, student_id)
    add_entries(ucon, student_id, entries, replace=True)
    return len(entries)


def clear(ucon: sqlite3.Connection, student_id: int) -> int:
    cur = ucon.execute("DELETE FROM earned_course WHERE student_id=?", (student_id,))
    ucon.commit()
    return cur.rowcount


# ------------------------------------------------------------------- şablon
def template(con: sqlite3.Connection, plan_ids: list[int]) -> str:
    """Planlardan hazır kontrol listesi üretir — kullanıcı sadece not yazar.

    Elle giriş yükünü ders kodu YAZMAKTAN not yazmaya indirir.
    """
    lines = [
        "# İTÜ ÇAP — transkript girişi",
        "#",
        "# Tüm dersler # ile KAPALI geliyor. ALDIĞIN derslerin başındaki '# ' işaretini",
        "# sil ve notunu yaz. Almadıklarına dokunma.",
        "#",
        "#   MAT 103E AA      -> geçildi, notu biliniyor",
        "#   MAT 103E         -> geçildi ama not bilinmiyor (en kötü durum DD sayılır)",
        "#   MAT 103E --      -> hâlâ alıyorum",
        "#   # MAT 103E       -> hiç almadım (öyle kalsın)",
        "#",
        "# Kaydet, sonra:  make transcript FILE=<bu dosya>",
        "",
    ]
    for plan_id in plan_ids:
        plan = con.execute(
            "SELECT title, plan_type, program_code FROM plan WHERE id=?", (plan_id,)).fetchone()
        if plan is None:
            continue
        lines += ["", f"# ===== {plan['program_code']} — {plan['title']} =====", ""]
        rows = con.execute(
            """SELECT term_no, slot_kind, course_code, pool_label_raw, ects
               FROM plan_slot WHERE plan_id=?
               ORDER BY term_no IS NULL, term_no, position""", (plan_id,)).fetchall()
        current_term = object()
        for row in rows:
            if row["term_no"] != current_term:
                current_term = row["term_no"]
                header = ("dönemsiz" if current_term is None
                          else f"{current_term}. yarıyıl")
                lines.append(f"\n# --- {header} ---")
            if row["slot_kind"] == "REQUIRED":
                name = con.execute("SELECT name FROM course WHERE code=?",
                                   (row["course_code"],)).fetchone()
                label = (name[0] if name else "")[:34]
                lines.append(f"# {row['course_code']:<11}          # {label}")
            else:
                # Kod satırın BAŞINA gelmeli; açıklama '#' sonrasında kalsın.
                lines.append(f"# ...........          "
                             f"# ↑ SEÇMELİ havuz: {row['pool_label_raw']} "
                             f"— aldığın dersin kodunu noktaların yerine yaz")
    lines += [
        "",
        "# --- plan dışı aldığın dersler (varsa buraya ekle) ---",
        "",
    ]
    return "\n".join(lines) + "\n"


def write_template(con: sqlite3.Connection, plan_ids: list[int],
                   dest: Path | None = None, overwrite: bool = False) -> Path:
    """Şablonu yazar. Dolu bir dosyanın ÜZERİNE YAZMAZ.

    Kullanıcı saatlerce not girdikten sonra `make student`'ı tekrar çalıştırırsa
    emeği gitmesin diye yanına '-yeni' ekli bir dosya açılır.
    """
    dest = dest or config.ROOT / "transkript.txt"
    if dest.exists() and not overwrite:
        dest = dest.with_name(f"{dest.stem}-yeni{dest.suffix}")
    dest.write_text(template(con, plan_ids), encoding="utf-8")
    return dest


# ------------------------------------------------- kaydedilmiş program (Faz 10)
def save_picks(ucon: sqlite3.Connection, student_id: int, term: str,
               picks: list[tuple[str, str]]) -> int:
    """Arayüzde kurduğun programı saklar. `picks` = [(ders, crn), ...]

    Motorun ÖNERİSİ ile SENİN seçimin ayrı şeyler: öneri her `refresh`'te
    yeniden hesaplanıyor, seçim ise senin kararın ve kalıcı olmalı.
    """
    ucon.execute("DELETE FROM saved_pick WHERE student_id=? AND term=?",
                 (student_id, term))
    now = __import__("datetime").datetime.now().isoformat(timespec="seconds")
    for i, (course, crn) in enumerate(picks):
        code = normalize_course_code(course)
        if not code or not crn:
            continue
        ucon.execute(
            """INSERT OR REPLACE INTO saved_pick
               (student_id, term, course_code, crn, position, saved_at)
               VALUES (?,?,?,?,?,?)""", (student_id, term, code, str(crn), i, now))
    ucon.commit()
    return len(picks)


def load_picks(ucon: sqlite3.Connection, student_id: int, term: str) -> dict:
    rows = ucon.execute(
        """SELECT course_code, crn, saved_at FROM saved_pick
           WHERE student_id=? AND term=? ORDER BY position""",
        (student_id, term)).fetchall()
    return {"savedAt": rows[0][2] if rows else "",
            "picks": [{"course": r[0], "crn": r[1]} for r in rows]}


def clear_picks(ucon: sqlite3.Connection, student_id: int, term: str) -> int:
    cur = ucon.execute("DELETE FROM saved_pick WHERE student_id=? AND term=?",
                       (student_id, term))
    ucon.commit()
    return cur.rowcount
