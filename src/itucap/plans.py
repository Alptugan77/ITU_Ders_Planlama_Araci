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
from . import rules as R


def anadal_plan(con, settings) -> int | None:
    row = con.execute(
        """SELECT id FROM plan WHERE program_code=? AND plan_type='lisans'
            ORDER BY (source='obs') DESC, id DESC LIMIT 1""",
        (settings.anadal_program,)).fetchone()
    return row[0] if row else None


def resolve_seconds(con, settings) -> list[dict]:
    """Etkin ikinci programların planları.

    ★ ÇAP ve yandal AYNI ANDA alınabiliyor (kullanıcı teyidi 23.08.2026),
    o yüzden burası bir LİSTE döndürüyor. `resolve_plans` bunun ilkini veren
    eski imza; iki programı da hesaba katması gereken yerler buraya bakmalı.

    Planı bulunamayan tür listede KALIYOR (`plan_id=None`). Sessizce atmak,
    "yandalım var ama araç göstermiyor" ile "yandal planı çekilmemiş"i aynı
    şeye çevirirdi — arayüz farkı söyleyebilmeli.
    """
    out: list[dict] = []
    for kind, role, label, code, plan_id in settings.seconds:
        if plan_id is None:
            row = con.execute(
                """SELECT id FROM plan WHERE program_code=? AND plan_type=?
                    ORDER BY (source='obs') DESC, id DESC LIMIT 1""",
                (code, config.SECOND_KINDS[kind][2])).fetchone()
            plan_id = row[0] if row else None
        out.append({"kind": kind, "role": role, "label": label,
                    "program": code, "planId": plan_id})
    return out


def resolve_plans(con, settings) -> tuple[int | None, int | None]:
    """(anadal_plan_id, İLK ikinci plan) — eski imza, tek program bekleyenler için.

    ⚠️ İki ikinci program varken bu yalnız birincisini verir. Kredi tabanı,
    eşikler, paneller gibi HER İKİSİNİ ilgilendiren yerlerde
    `resolve_seconds` kullan.
    """
    seconds = resolve_seconds(con, settings)
    return anadal_plan(con, settings), (seconds[0]["planId"] if seconds else None)


def watch_codes(con, ucon, settings) -> set[str]:
    """Seni ilgilendiren ders kodları: iki planın da açık slotlarındakiler.

    3400 şubelik ham dökümde kendi dersini bulmak imkânsız; rapor varsayılan
    olarak buna daraltılıyor."""
    from . import student as S

    student_id = S.ensure_student(ucon)
    grades = S.grades(ucon, student_id)
    ids = [anadal_plan(con, settings),
           *(s["planId"] for s in resolve_seconds(con, settings))]
    codes = R.plan_codes(con, *ids, pools=True)
    return {c for c in codes if c and c not in grades}
