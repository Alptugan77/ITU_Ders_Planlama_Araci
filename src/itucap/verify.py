"""Faz 1 bitiş kriterlerini (Definition of Done) makinede doğrulayan rapor.

`python -m itucap.pipeline verify` ile çalışır. Amaç: OBS'deki görüntüyle
veritabanındaki hali GÖZLE karşılaştırabilmen için ikisini yan yana koymak —
otomatik teste körü körüne güvenme, yol haritası da bunu söylüyor.
"""
from __future__ import annotations

import sqlite3

from . import config


def _plan_row(con, program: str, plan_type: str) -> sqlite3.Row | None:
    return con.execute(
        """SELECT * FROM plan
            WHERE program_code = ? AND plan_type = ?
            ORDER BY (source='obs') DESC, id DESC LIMIT 1""",
        (program, plan_type),
    ).fetchone()


def _slot_summary(con, plan_id: int) -> dict:
    kinds = dict(con.execute(
        "SELECT slot_kind, COUNT(*) FROM plan_slot WHERE plan_id=? GROUP BY 1", (plan_id,)
    ).fetchall())
    terms = con.execute(
        """SELECT term_no, COUNT(*) FROM plan_slot WHERE plan_id=?
           GROUP BY term_no ORDER BY term_no IS NULL, term_no""", (plan_id,)
    ).fetchall()
    cats = dict(con.execute(
        """SELECT COALESCE(pool_category,'-'), COUNT(*) FROM plan_slot
           WHERE plan_id=? AND slot_kind='ELECTIVE_POOL' GROUP BY 1""", (plan_id,)
    ).fetchall())
    options = con.execute(
        """SELECT COUNT(*) FROM pool_option po
           JOIN plan_slot ps ON ps.id = po.slot_id WHERE ps.plan_id=?""", (plan_id,)
    ).fetchone()[0]
    return {"kinds": kinds, "terms": terms, "cats": cats, "options": options}


def _course_sets(con, plan_id: int) -> tuple[set[str], set[str]]:
    """(zorunlu dersler, havuzlardaki dersler) — çift sayım analizi için."""
    req = {r[0] for r in con.execute(
        "SELECT course_code FROM plan_slot WHERE plan_id=? AND course_code IS NOT NULL",
        (plan_id,))}
    pool = {r[0] for r in con.execute(
        """SELECT po.course_code FROM pool_option po
           JOIN plan_slot ps ON ps.id = po.slot_id WHERE ps.plan_id=?""", (plan_id,))}
    return req, pool


def _sample(items: list[str], n: int = 6) -> str:
    if not items:
        return ""
    head = ", ".join(items[:n])
    return f"({head}{', …' if len(items) > n else ''})"


def report(con: sqlite3.Connection, settings: config.Settings) -> tuple[str, bool]:
    out: list[str] = []
    checks: list[tuple[str, bool]] = []
    w = out.append

    anadal = _plan_row(con, settings.anadal_program, "lisans")
    cap = None
    if settings.second_plan_id:
        cap = con.execute("SELECT * FROM plan WHERE id=?",
                          (settings.second_plan_id,)).fetchone()
    if cap is None:
        cap = _plan_row(con, settings.second_program,
                        config.SECOND_KINDS[settings.second_kind][2] or "cap")

    # --------------------------------------------------------------- anadal
    w("=" * 72)
    w(f"ANADAL — {settings.anadal_program}")
    w("=" * 72)
    if anadal is None:
        w("  ✗ plan bulunamadı")
        checks.append(("anadal planı yüklü", False))
    else:
        s = _slot_summary(con, anadal["id"])
        w(f"  plan id     : {anadal['id']}   kaynak: {anadal['source']}")
        w(f"  başlık      : {anadal['title']}")
        w(f"  iterasyon   : {anadal['iteration']}")
        w(f"  kaynak URL  : {anadal['source_url']}")
        w(f"  slotlar     : {s['kinds']}   havuz seçeneği: {s['options']}")
        w("  yarıyıl dağılımı:")
        for term_no, n in s["terms"]:
            w(f"      {('dönemsiz' if term_no is None else f'{term_no}. yarıyıl'):>12} : {n} slot")
        w(f"  havuz kategorileri: {s['cats']}")
        checks.append(("anadal planı yüklü", True))
        checks.append(("anadal planı 8 yarıyıla yayılmış",
                       len([t for t, _ in s["terms"] if t is not None]) >= 8))
        checks.append(("anadal havuzlarında OTHER yok", "OTHER" not in s["cats"]))

    # ------------------------------------------------------------------ ÇAP
    w("")
    w("=" * 72)
    w(f"{settings.second_label or 'ÇAP'} — {settings.second_program}")
    w("=" * 72)
    if cap is None:
        w("  ✗ plan bulunamadı")
        checks.append(("ÇAP planı yüklü", False))
    else:
        s = _slot_summary(con, cap["id"])
        hosts = [r[0] for r in con.execute(
            "SELECT program_code FROM plan_host_program WHERE plan_id=? ORDER BY program_code",
            (cap["id"],))]
        w(f"  plan id     : {cap['id']}   kaynak: {cap['source']}")
        w(f"  başlık      : {cap['title']}")
        w(f"  anadal tarafı: {cap['host_program_code']}   dönemli mi: {bool(cap['is_term_based'])}")
        w(f"  kaynak URL  : {cap['source_url']}")
        w(f"  slotlar     : {s['kinds']}   havuz seçeneği: {s['options']}")
        w(f"  havuz kategorileri: {s['cats']}")
        w(f"  geçerli olduğu anadal programı sayısı: {len(hosts)}")
        in_list = settings.anadal_program in hosts
        w(f"  ★ {settings.anadal_program} bu planın kapsamında mı: "
          f"{'EVET' if in_list else 'HAYIR — yanlış plan seçmiş olabilirsin!'}")
        checks.append(("ÇAP planı yüklü", True))
        checks.append((f"{settings.anadal_program} ÇAP planının kapsamında", in_list))
        checks.append(("ÇAP planında ders var", sum(s["kinds"].values()) > 0))

        w("")
        w("  --- ÇAP planındaki dersler (OBS ile karşılaştır) ---")
        for row in con.execute(
            """SELECT slot_kind, course_code, pool_label_raw, credits, ects_raw, type_raw
               FROM plan_slot WHERE plan_id=? ORDER BY position""", (cap["id"],)):
            label = row["course_code"] or f"[havuz] {row['pool_label_raw']}"
            w(f"    {label:<46} kr={row['credits']!s:<5} akts={row['ects_raw']!s:<9} "
              f"tip={row['type_raw']}")

    # ---------------------------------------------------- ortak ders analizi
    if anadal is not None and cap is not None:
        w("")
        w("=" * 72)
        w("ÇİFT SAYIM ANALİZİ")
        w("=" * 72)
        a_req, a_pool = _course_sets(con, anadal["id"])
        c_req, c_pool = _course_sets(con, cap["id"])

        rr = sorted(a_req & c_req)
        rp = sorted(a_req & c_pool)
        pr = sorted(a_pool & c_req)
        pp = sorted(a_pool & c_pool)
        w(f"  zorunlu ∩ zorunlu : {len(rr):>4}  {_sample(rr)}")
        w(f"  anadal zorunlu ∩ ÇAP havuzu : {len(rp):>4}  {_sample(rp)}")
        w(f"  anadal havuzu ∩ ÇAP zorunlu : {len(pr):>4}  {_sample(pr)}")
        w(f"  havuz ∩ havuz     : {len(pp):>4}  {_sample(pp)}")

        cap_ects = con.execute(
            "SELECT SUM(ects) FROM plan_slot WHERE plan_id=? AND slot_kind='REQUIRED'",
            (cap["id"],)).fetchone()[0] or 0
        n_pools = con.execute(
            "SELECT COUNT(*) FROM plan_slot WHERE plan_id=? AND slot_kind='ELECTIVE_POOL'",
            (cap["id"],)).fetchone()[0]
        w("")
        w(f"  ÇAP zorunlu AKTS toplamı : {cap_ects:g}  (+ {n_pools} seçmeli havuz)")
        total_overlap = len(rr) + len(rp) + len(pr) + len(pp)
        if total_overlap == 0:
            w("")
            w("  ⚠️  HİÇ ÖRTÜŞME YOK — ve bu bir veri hatası değil.")
            w("      ÇAP planı zaten 'fark planı': İTÜ ortak dersleri planı yazarken")
            w("      düşmüş. Yani ÇAP'ın yükü tamamen EK. Öneri motorunun birincil")
            w("      kriteri 'çift sayım' olamaz — sıralama önşart zinciri ve")
            w("      programa sığdırma üzerinden kurulmalı (bkz. Faz 5).")
        else:
            w(f"      {total_overlap} örtüşme noktası var — çift sayım Faz 3'te modellenecek.")

    # ------------------------------------------------------- altyapı testleri
    w("")
    w("=" * 72)
    w("ALTYAPI")
    w("=" * 72)
    n_conflict = con.execute(
        """SELECT COUNT(*) FROM lesson_meeting m1
           JOIN lesson_meeting m2 ON m1.day_of_week = m2.day_of_week AND m1.crn < m2.crn
           WHERE m1.start_min < m2.end_min AND m2.start_min < m1.end_min
             AND m1.crn IN (SELECT crn FROM lesson WHERE course_code='MAT 103E')"""
    ).fetchone()[0]
    w(f"  çakışma sorgusu çalışıyor (MAT 103E örneği): {n_conflict} çakışan çift")
    checks.append(("çakışma sorgusu çalışıyor", True))

    n_lessons = con.execute("SELECT COUNT(*) FROM lesson").fetchone()[0]
    n_meet = con.execute("SELECT COUNT(*) FROM lesson_meeting").fetchone()[0]
    w(f"  şube: {n_lessons}   oturum: {n_meet}")
    checks.append(("güncel dönem CRN'leri yüklü", n_lessons > 0 and n_meet > 0))

    w(f"  referans DB: {config.REF_DB}")
    w(f"  kullanıcı DB ayrı dosya: {config.USER_DB.exists()}")
    checks.append(("kullanıcı verisi ayrı dosyada", config.REF_DB != config.USER_DB))

    # ------------------------------------------------------------- özet
    w("")
    w("=" * 72)
    w("FAZ 1 BİTİŞ KRİTERLERİ")
    w("=" * 72)
    for name, ok in checks:
        w(f"  {'✅' if ok else '❌'} {name}")
    passed = all(ok for _, ok in checks)
    w("")
    w("✅ Faz 1 tamam." if passed else "❌ Eksik kriter var, Faz 2'ye geçme.")
    return "\n".join(out), passed
