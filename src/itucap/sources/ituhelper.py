"""WP1.5 — itu-helper/data hazır veri seti.

Bu kaynak için scraper yazmıyoruz; GitHub Actions ile beslenen PSV/TXT dosyalarını
indirip normalize ediyoruz. ÇAP planları BU KAYNAKTA YOKTUR (bkz. obs_plan.py).
"""
from __future__ import annotations

import hashlib
import html
import re
import sqlite3
from pathlib import Path

from .. import config, db
from ..http import download
from ..normalize import (
    day_to_index,
    normalize_course_code,
    normalize_pool_label,
    obs_code_to_program,
    parse_time_range,
)

FILES = [
    "courses.psv",
    "lessons.psv",
    "course_plans.txt",
    "programme_codes.psv",
    "building_codes.psv",
]

ELECTIVE_RE = re.compile(r"^\[(?P<label>.*?)\*\((?P<options>.*?)\)\]$")


# --------------------------------------------------------------------- indir
def fetch_all(settings: config.Settings, dest: Path | None = None) -> Path:
    dest = dest or config.DATA_DIR / "ituhelper"
    dest.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        download(f"{config.ITU_HELPER_RAW}/{name}", dest / name, settings.user_agent)
    return dest


def read_psv(path: Path) -> list[list[str]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append([c.strip() for c in line.split("|")])
    return rows


# ------------------------------------------------------------------ yükleyici
def load_programs(con: sqlite3.Connection, src: Path) -> int:
    rows = read_psv(src / "programme_codes.psv")
    con.executemany(
        "INSERT OR REPLACE INTO program(code, name, faculty, level) VALUES (?,?,?,?)",
        [(r[0], r[1] if len(r) > 1 else None, r[2] if len(r) > 2 else None,
          r[3] if len(r) > 3 else None) for r in rows],
    )
    con.commit()
    return len(rows)


def load_buildings(con: sqlite3.Connection, src: Path) -> int:
    rows = read_psv(src / "building_codes.psv")
    con.executemany(
        "INSERT OR REPLACE INTO building(code,name,campus) VALUES (?,?,?)",
        [(r[0], html.unescape(r[1]) if len(r) > 1 and r[1] else None,
          (r[2] if len(r) > 2 and r[2] else None)) for r in rows],
    )
    con.commit()
    return len(rows)


def load_courses(con: sqlite3.Connection, src: Path) -> int:
    rows = read_psv(src / "courses.psv")
    payload = []
    for r in rows:
        r = r + [""] * (8 - len(r))
        payload.append((
            # itu-helper ham HTML'den geldiği için '&amp;' gibi kaçışlar taşıyor
            normalize_course_code(r[0]), html.unescape(r[1]) if r[1] else None, r[2] or None,
            _num(r[3]), _num(r[4]),
            r[5] or None,          # prereq_raw: HAM saklanır (WP1.6)
            r[6] or None,
            "itu-helper", db.now(),
        ))
    con.executemany(
        """INSERT INTO course(code,name,language,credits,ects,prereq_raw,
                              class_restriction,source,scraped_at)
           VALUES (?,?,?,?,?,?,?,?,?)
           ON CONFLICT(code) DO UPDATE SET
             name=excluded.name, language=excluded.language, credits=excluded.credits,
             ects=excluded.ects, prereq_raw=excluded.prereq_raw,
             class_restriction=excluded.class_restriction, scraped_at=excluded.scraped_at""",
        payload,
    )
    con.commit()
    return len(payload)


def load_lessons(con: sqlite3.Connection, src: Path, term: str = "") -> int:
    """lessons.psv:
    CRN|Ders Kodu|Öğretim Yöntemi|Öğretim Üyesi|Bina|Gün|Saat|Derslik|Kontenjan|Yazılan|Programlar

    Çok oturumlu dersler Bina/Gün/Saat/Derslik alanlarında BOŞLUKLA ayrılmış
    çoklu değer taşır -> lesson_meeting'e birden fazla satır olarak açılır.
    """
    rows = read_psv(src / "lessons.psv")
    # idempotent: bu dosyadan gelen CRN'leri baştan yaz
    con.execute("DELETE FROM lesson_meeting")
    con.execute("DELETE FROM lesson_allowed_program")
    con.execute("DELETE FROM lesson")
    n_meet = 0
    for r in rows:
        r = r + [""] * (11 - len(r))
        crn = r[0]
        if not crn:
            continue
        con.execute(
            """INSERT OR REPLACE INTO lesson(crn,term,course_code,teaching_method,instructor,
                    building,capacity,enrolled,major_restr,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (crn, term or None, normalize_course_code(r[1]), r[2] or None, r[3] or None,
             (r[4].split(" ") or [None])[0], _int(r[8]), _int(r[9]), r[10] or None, db.now()),
        )
        buildings, days, times, rooms = r[4].split(), r[5].split(), r[6].split(), r[7].split()
        for i, day in enumerate(days):
            rng = parse_time_range(times[i] if i < len(times) else "")
            idx = day_to_index(day)
            if idx is None or rng is None:
                continue
            con.execute(
                """INSERT INTO lesson_meeting(crn,day_of_week,start_min,end_min,room,building)
                   VALUES (?,?,?,?,?,?)""",
                (crn, idx, rng[0], rng[1],
                 rooms[i] if i < len(rooms) else None,
                 buildings[i] if i < len(buildings) else None),
            )
            n_meet += 1
        for prog in {p.strip() for p in r[10].split(",") if p.strip()}:
            con.execute(
                "INSERT OR IGNORE INTO lesson_allowed_program(crn,program_code) VALUES (?,?)",
                (crn, obs_code_to_program(prog)),
            )
    con.commit()
    return n_meet


def load_course_plans(con: sqlite3.Connection, src: Path,
                      only_programs: set[str] | None = None) -> int:
    """course_plans.txt: '#' fakülte, '##' program adı, '###' iterasyon,
    ardından her satır bir DÖNEM, dersler '=' ile ayrılmış.
    Seçmeli format: [Etiket*(D1|D2|D3)]
    """
    name_to_code = {
        (row["name"] or "").strip(): row["code"]
        for row in con.execute("SELECT code, name FROM program")
    }
    text = (src / "course_plans.txt").read_text(encoding="utf-8")
    faculty = program_name = iteration = None
    program_code = None
    term_no = 0
    plan_id = None
    inserted = 0

    for line in text.splitlines():
        if line.startswith("### "):
            iteration = line[4:].strip()
            term_no = 0
            plan_id = None
            if program_code and (not only_programs or program_code in only_programs):
                plan_id = _upsert_plan(
                    con, program_code=program_code, host=None, plan_type="lisans",
                    obs_program_code=None, title=f"{program_name} — {iteration}",
                    iteration=iteration, is_term_based=1,
                    source_url=f"{config.ITU_HELPER_RAW}/course_plans.txt",
                )
            continue
        if line.startswith("## "):
            program_name = line[3:].strip()
            program_code = name_to_code.get(program_name)
            iteration = plan_id = None
            continue
        if line.startswith("# "):
            faculty = line[2:].strip()
            continue
        if plan_id is None:
            continue
        term_no += 1
        if not line.strip():
            continue  # veri girilmemiş dönem
        for position, token in enumerate(line.split("=")):
            token = token.strip()
            if not token:
                continue
            inserted += _insert_slot(con, plan_id, term_no, position, token)
    con.commit()
    return inserted


def _insert_slot(con: sqlite3.Connection, plan_id: int, term_no: int,
                 position: int, token: str) -> int:
    m = ELECTIVE_RE.match(token)
    if m:
        label = m.group("label").strip()
        category, _ = normalize_pool_label(label)
        cur = con.execute(
            """INSERT INTO plan_slot(plan_id,term_no,slot_kind,pool_label_raw,
                                     pool_category,position)
               VALUES (?,?,'ELECTIVE_POOL',?,?,?)""",
            (plan_id, term_no, label, category, position),
        )
        slot_id = cur.lastrowid
        for opt in m.group("options").split("|"):
            code = normalize_course_code(opt)
            if code:
                con.execute(
                    "INSERT OR IGNORE INTO pool_option(slot_id,course_code) VALUES (?,?)",
                    (slot_id, code),
                )
        return 1
    code = normalize_course_code(token)
    if not code:
        return 0
    con.execute(
        """INSERT INTO plan_slot(plan_id,term_no,slot_kind,course_code,position)
           VALUES (?,?,'REQUIRED',?,?)""",
        (plan_id, term_no, code, position),
    )
    return 1


def _upsert_plan(con: sqlite3.Connection, **kw) -> int:
    """course_plans.txt'de OBS plan id'si yok; deterministik negatif id üretiyoruz
    ki OBS'den gelen gerçek id'lerle (pozitif) çakışmasın."""
    key = f"{kw['program_code']}|{kw['plan_type']}|{kw['iteration']}"
    # hashlib: PYTHONHASHSEED'den bağımsız, çalıştırmalar arası STABİL id (idempotency)
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
    synthetic_id = -(int(digest[:12], 16) % 10_000_000 + 1)
    con.execute(
        """INSERT INTO plan(id,program_code,host_program_code,plan_type,obs_program_code,
                            title,iteration,is_term_based,source,source_url,scraped_at)
           VALUES (?,?,?,?,?,?,?,?,'itu-helper',?,?)
           ON CONFLICT(id) DO UPDATE SET title=excluded.title, scraped_at=excluded.scraped_at""",
        (synthetic_id, kw["program_code"], kw["host"], kw["plan_type"],
         kw["obs_program_code"], kw["title"], kw["iteration"], kw["is_term_based"],
         kw["source_url"], db.now()),
    )
    con.execute("DELETE FROM plan_slot WHERE plan_id=?", (synthetic_id,))
    return synthetic_id


def _num(v: str) -> float | None:
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _int(v: str) -> int | None:
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None
