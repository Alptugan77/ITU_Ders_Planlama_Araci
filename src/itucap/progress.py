"""FAZ 3+4 — İlerleme paneli: anadal ve ÇAP YAN YANA, kredileri ayrı.

Yol haritası §1.7: "ÇAP kredi toplamına sadece ÇAP planındaki derslerin kredisi
dahil edilir. Tek bir 'toplam AKTS' göstergesi yanıltıcıdır."

Ayrıca slot_fulfillment tablosunu üretir (Faz 3'ün kalan işi): hangi geçilen ders
hangi planın hangi slotunu dolduruyor. D5'ten sonra çift sayım pratikte
görülmüyor ama tablo genel — aynı ders iki plana da bağlanabilir.
"""
from __future__ import annotations

import sqlite3
from typing import Mapping

from . import rules as R
from . import sequence as SEQ
from .db import now


# ---------------------------------------------------------- slot eşlemesi
def rebuild_fulfillment(con: sqlite3.Connection, ucon: sqlite3.Connection,
                        student_id: int, plan_ids: list[int],
                        grades: Mapping[str, str]) -> int:
    """slot_fulfillment'ı sıfırdan üretir. Idempotent."""
    equivalences = R.load_equivalences(con, ucon=ucon)
    ucon.execute("DELETE FROM slot_fulfillment WHERE student_id=?", (student_id,))
    written = 0
    for plan_id in plan_ids:
        for (slot_id,) in con.execute(
                "SELECT id FROM plan_slot WHERE plan_id=?", (plan_id,)):
            result = R.slot_satisfied(con, slot_id, grades, equivalences)
            if not result.satisfied:
                continue
            earned = ucon.execute(
                """SELECT id FROM earned_course
                   WHERE student_id=? AND course_code=? AND status='PASSED' LIMIT 1""",
                (student_id, result.course)).fetchone()
            ucon.execute(
                """INSERT OR REPLACE INTO slot_fulfillment
                       (student_id,slot_id,earned_id,via_equivalence,is_auto,decided_at)
                   VALUES (?,?,?,?,1,?)""",
                (student_id, slot_id, earned[0] if earned else None,
                 result.via_equivalence, now()),
            )
            written += 1
    ucon.commit()
    return written


def double_counted(con: sqlite3.Connection, ucon: sqlite3.Connection,
                   student_id: int) -> list[tuple[str, int]]:
    """Birden fazla planın slotunu dolduran dersler (çift sayım fiilen olursa)."""
    rows = ucon.execute(
        """SELECT ec.course_code, COUNT(DISTINCT sf.slot_id) n
           FROM slot_fulfillment sf JOIN earned_course ec ON ec.id = sf.earned_id
           WHERE sf.student_id=? GROUP BY ec.course_code HAVING n > 1""",
        (student_id,)).fetchall()
    return [(r[0], r[1]) for r in rows]


# ------------------------------------------------------------------- rapor
def _bar(percent: float, width: int = 24) -> str:
    filled = int(round(width * percent / 100))
    return "█" * filled + "░" * (width - filled)


def panel(con: sqlite3.Connection, plan_id: int, role: str,
          grades: Mapping[str, str],
          ucon: sqlite3.Connection | None = None) -> list[str]:
    plan = con.execute("SELECT * FROM plan WHERE id=?", (plan_id,)).fetchone()
    if plan is None:
        return [f"{role}: plan {plan_id} bulunamadı"]
    stats = R.plan_progress(con, plan_id, grades,
                            R.load_equivalences(con, ucon=ucon))
    out = [
        f"{role} — {plan['program_code']}",
        f"  {plan['title'][:62]}",
        f"  {_bar(stats['percent'])}  %{stats['percent']:g}",
        f"  slot : {stats['slots_done']}/{stats['slots_total']}"
        f"      kredi : {stats['credits_done']:g}/{stats['credits_total']:g}"
        f"      AKTS : {stats['ects_done']:g}/{stats['ects_total']:g}",
    ]
    cats = " · ".join(f"{k} {v[0]}/{v[1]}" for k, v in stats["by_category"].items())
    out.append(f"  {cats}")

    open_codes = [r[0] for r in con.execute(
        """SELECT course_code FROM plan_slot
           WHERE id IN (%s) AND course_code IS NOT NULL
           ORDER BY term_no IS NULL, term_no, position""" %
        ",".join("?" * len(stats["open_slots"])), stats["open_slots"])] \
        if stats["open_slots"] else []
    if open_codes:
        shown = ", ".join(open_codes[:12])
        more = f" … (+{len(open_codes) - 12})" if len(open_codes) > 12 else ""
        out.append(f"  kalan zorunlu: {shown}{more}")
    n_pool = len(stats["open_slots"]) - len(open_codes)
    if n_pool:
        out.append(f"  kalan seçmeli havuz: {n_pool}")
    return out


def report(con: sqlite3.Connection, ucon: sqlite3.Connection, student_id: int,
           cap_plan_id: int | None = None) -> str:
    from . import student as S

    grades = S.grades(ucon, student_id)
    rows = S.enrollments(ucon, student_id)
    out: list[str] = []
    w = out.append

    w("=" * 72)
    w(f"İLERLEME — {len(grades)} geçilmiş ders")
    w("=" * 72)
    if not rows:
        return "\n".join(out + ["", "Kayıt yok. Önce:  make student"])

    for row in rows:
        w("")
        out.extend(panel(con, row["plan_id"], row["role"], grades, ucon=ucon))

    uncertain = S.uncertain_grades(ucon, student_id)
    if uncertain:
        w("")
        w(f"⚠️  {len(uncertain)} dersin notu girilmemiş, EN KÖTÜ DURUM (DD) varsayıldı: "
          f"{', '.join(uncertain[:10])}")
        w("    MIN CC/BB isteyen önşartlarda bu seni gereksiz engelleyebilir.")

    shared = double_counted(con, ucon, student_id)
    if shared:
        w("")
        w(f"★ ÇİFT SAYILAN DERSLER: {', '.join(f'{c} ({n} slot)' for c, n in shared)}")

    # --------------------------------------------------- ÇAP'ta sırada ne var
    cap = next((r for r in rows if r["role"] in ("CAP", "YANDAL")), None)
    plan_id = cap_plan_id or (cap["plan_id"] if cap else None)
    if plan_id is not None:
        steps = SEQ.plan_sequence(con, plan_id, grades)
        ready = [s for s in steps if s.status == "READY"]
        unknown = [s for s in steps if s.status == "UNKNOWN"]
        w("")
        w("=" * 72)
        w("ÇAP'TA ŞU AN ALABİLECEKLERİN")
        w("=" * 72)
        if not ready:
            w("  (önşartları sağlanan ÇAP dersi yok)")
        allowed = _cap_programs(ucon, student_id)
        for step in sorted(ready, key=lambda s: (-s.unlocks, s.course)):
            sections = _open_sections(con, step.course, allowed)
            w(f"  ▶ {step.course:<11} {(step.credits or 0):>4g} kr / "
              f"{(step.ects or 0):g} akts  açtığı ders: {step.unlocks:<4} {sections}")
        if unknown:
            w(f"  ? önşartı okunamayan: {', '.join(s.course for s in unknown)}"
              " — danışmanına sor")

        done = sum(1 for s in steps if s.status == "DONE")
        left = [s for s in steps if s.status != "DONE"]
        left_ects = sum(s.ects or 0 for s in left)
        left_cr = sum(s.credits or 0 for s in left)
        tiers_left = len({s.tier for s in left})
        w("")
        w(f"  ÇAP zorunlu: {done}/{len(steps)} bitti · kalan {left_cr:g} kredi / "
          f"{left_ects:g} AKTS · en az {tiers_left} dönem (önşart zinciri)")
    return "\n".join(out)


def _cap_programs(ucon: sqlite3.Connection, student_id: int) -> set[str]:
    from . import config, student as S

    settings = config.Settings.load()
    return settings.allowed_programs or {settings.second_program}


def _open_sections(con: sqlite3.Connection, course_code: str,
                   allowed_programs: set[str] | None = None) -> str:
    """Şube özeti — PROGRAM KISITINA göre. Alamayacağın şubeyi 'var' saymak
    yanıltıcı: BLG 223E'nin 2 şubesi var ama ikisi de yalnız SECE'ye açık."""
    from .recommend import load_sections

    total = con.execute(
        "SELECT COUNT(*) FROM lesson WHERE course_code=?", (course_code,)).fetchone()[0]
    if not total:
        return "[bu dönem açılmamış]"
    if allowed_programs is None:
        return f"[{total} şube]"
    sections = load_sections(con, course_code, allowed_programs)
    if not sections:
        return f"[{total} şube var ama programına kapalı]"
    free = [s for s in sections if s.free > 0]
    if not free:
        return f"[{len(sections)} şube, hepsi dolu]"
    best = max(free, key=lambda s: s.free)
    return f"[{len(sections)} şube, en boşu CRN {best.crn}: {best.enrolled}/{best.capacity}]"
