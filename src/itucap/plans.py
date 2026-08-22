"""Plan çözümleme — hangi plan id'si hangi programa ait.

★ Bu işlev `pipeline.py` içindeydi ama oraya ait değildi: `pipeline` tarama
(scraping) modüllerini içeri alıyor — `httpx`, `selectolax`. Plan çözümlemek
için ağ erişimine ihtiyaç yok, saf bir veritabanı sorgusu.

Ayırmanın somut kazancı: motor artık tarayıcıda da (Pyodide) çalışabiliyor.
`server.State` bu işlevi çağırıyordu ve onun yüzünden bütün tarama yığınını
sürüklüyordu; tarayıcıda `httpx` yok, `selectolax` yok — ve olmasına da gerek
yok, çünkü tarama kullanıcının makinesinde yapılıyor.
"""
from __future__ import annotations

import sqlite3

from . import config


def resolve_plans(con, settings) -> tuple[int | None, int | None]:
    """(anadal_plan_id, ikinci_plan_id) — OBS kaynaklı olan tercih edilir.

    İkinci plan ÇAP ya da yandal olabilir; `second_kind` hangisini arayacağımızı
    söylüyor. `second_kind='yok'` ise ikinci plan None döner ve motor tek
    programla çalışır.
    """
    anadal = con.execute(
        """SELECT id FROM plan WHERE program_code=? AND plan_type='lisans'
            ORDER BY (source='obs') DESC, id DESC LIMIT 1""",
        (settings.anadal_program,)).fetchone()
    anadal_id = anadal[0] if anadal else None
    if settings.second_kind == "yok":
        return anadal_id, None
    second_id = settings.second_plan_id
    if second_id is None:
        plan_type = config.SECOND_KINDS[settings.second_kind][2]
        row = con.execute(
            """SELECT id FROM plan WHERE program_code=? AND plan_type=?
                ORDER BY (source='obs') DESC, id DESC LIMIT 1""",
            (settings.second_program, plan_type)).fetchone()
        second_id = row[0] if row else None
    return anadal_id, second_id


def watch_codes(con, ucon, settings) -> set[str]:
    """Seni ilgilendiren ders kodları: iki planın da açık slotlarındakiler.

    3400 şubelik ham dökümde kendi dersini bulmak imkânsız; rapor varsayılan
    olarak buna daraltılıyor."""
    from . import student as S

    student_id = S.ensure_student(ucon)
    grades = S.grades(ucon, student_id)
    anadal_id, second_id = resolve_plans(con, settings)
    codes: set[str] = set()
    for plan_id in (anadal_id, second_id):
        if plan_id is None:
            continue
        for row in con.execute(
            """SELECT ps.course_code, ps.id FROM plan_slot ps WHERE ps.plan_id=?""",
            (plan_id,)
        ):
            if row[0]:
                codes.add(row[0])
            codes.update(r[0] for r in con.execute(
                "SELECT course_code FROM pool_option WHERE slot_id=?", (row[1],)))
    return {c for c in codes if c and c not in grades}
