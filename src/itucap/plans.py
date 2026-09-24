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


# ★★ "OTOMATİK (EN GÜNCEL) PLAN" EN GÜNCEL DEĞİLDİ
# (ilk kullanıcı incelemesi A3, 24.08.2026).
#
# Eski sıralama `ORDER BY (source='obs') DESC, id DESC` idi. `id` bir sıra
# numarası DEĞİL, plan kimliği — lisans planlarında negatif ve hash gibi.
# Ölçüm (BLGE, beş müfredat):
#
#     seçilen  -467694   59 slot  2010-2011 / Güz ile 2011-2012 arası
#     doğrusu -4468543   51 slot  2024-2025 / Güz Dönemi Sonrası
#
# Yani 2026'da kayıt yaptıran öğrenci **15 yıllık müfredata** göre
# planlanıyordu. Panel bunu yazıyordu ama öğrenci o satırın seçilebilir bir
# şey olduğunu bilmiyordu — zaten seçemiyordu da (A4).
#
# Doğru sinyal `iteration` metni. İki biçim var:
#     "2024-2025 / Güz Dönemi Sonrası"                        → açık uçlu
#     "2011-2012 / Güz ile 2017-2018 / Güz Dönemleri Arası"   → kapalı aralık
_YIL_RE = __import__("re").compile(r"(\d{4})\s*[-–]\s*\d{4}")


def iteration_key(iteration: str | None) -> tuple[int, int]:
    """(başlangıç yılı, açık uçlu mu) — büyük olan daha güncel.

    ⚠️ Yıl bulunamazsa (0, 0) döner: TAHMİN ETMİYORUZ, en eskiye koyuyoruz.
    Okunamayan bir başlığı "en güncel" saymak, tam da düzeltmeye
    çalıştığımız hatayı geri getirirdi.
    """
    metin = iteration or ""
    yillar = [int(y) for y in _YIL_RE.findall(metin)]
    if not yillar:
        return (0, 0)
    acik = 1 if "sonras" in metin.casefold() else 0
    return (max(yillar) if acik else yillar[0], acik)


def _en_guncel(rows) -> int | None:
    """`(id, iteration, source)` satırlarından en güncel planın id'si."""
    if not rows:
        return None
    en = max(rows, key=lambda r: (1 if (r["source"] == "obs") else 0,
                                  *iteration_key(r["iteration"])))
    return en["id"]


def anadal_plan(con, settings) -> int | None:
    """Anadal lisans planı.

    ★ Beyan edilen `anadal_plan_id` ARTIK OKUNUYOR (inceleme A4). Eskiden
    `settings.example.toml` bu alanı belgeliyordu, `server` API'den kabul
    ediyordu, ama bu fonksiyon ona HİÇ bakmıyordu — yani A3'teki yanlış
    seçime karşı öğrencinin yapabileceği hiçbir şey yoktu.
    """
    istenen = settings.anadal_plan_id or None
    if istenen:
        row = con.execute("SELECT id FROM plan WHERE id=? AND plan_type='lisans'",
                          (istenen,)).fetchone()
        if row:
            return row[0]
        # ⚠️ Beyan edilen plan yoksa SESSİZCE otomatiğe düşüyoruz ama bu bir
        # veri sorunu; `plan_uyarisi()` bunu arayüze taşıyor.
    rows = con.execute(
        """SELECT id, iteration, source FROM plan
            WHERE program_code=? AND plan_type='lisans'""",
        (settings.anadal_program,)).fetchall()
    return _en_guncel(rows)


def plan_uyarisi(con, settings) -> str:
    """Beyan edilen anadal planı bulunamadıysa söylenecek şey."""
    istenen = settings.anadal_plan_id or None
    if not istenen:
        return ""
    row = con.execute("SELECT id FROM plan WHERE id=? AND plan_type='lisans'",
                      (istenen,)).fetchone()
    return "" if row else (
        f"Ayarlardaki anadal planı ({istenen}) katalogda bulunamadı; "
        "en güncel plan kullanılmaktadır.")


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
            plan_id = ikinci_plan(con, code, config.SECOND_KINDS[kind][2],
                                  settings.anadal_program)
        out.append({"kind": kind, "role": role, "label": label,
                    "program": code, "planId": plan_id})
    return out


def ikinci_plan(con, program_code: str, plan_type: str,
                anadal: str = "") -> int | None:
    """ÇAP/yandal planı — ÖNCE anadala uygun olanlar arasından.

    ★★ İnceleme A3'ün ikinci yarısı. HTAE + BLG için kutuda **38 plan**
    vardı ve çoğu başka anadalın (`SEC_BLG`, `ROS_BLG`, `KOM_BLG`…).
    Otomatik seçim `2723 · SEC_BLG` oluyordu; doğrusu `2229 · TUMMUH_BLG`.

    Doğru cevap VERİDE var: `plan_host_program` Faz 19'da dolduruldu
    (10532 satır) ama plan seçiminde hiç kullanılmıyordu.

    ⚠️ Süzgeç BOŞ dönerse süzmeden devam ediyoruz: "senin anadalın için
    ilan edilmiş bir ÇAP planı yok" ile "plan var ama eşleştiremedik"
    aynı şey değil, ve ikincisinde programı hiç göstermemek daha kötü.
    """
    hepsi = con.execute(
        """SELECT id, iteration, source FROM plan
            WHERE program_code=? AND plan_type=?""",
        (program_code, plan_type)).fetchall()
    if not hepsi:
        return None
    if anadal:
        from .normalize import base_program_code
        taban = base_program_code(anadal)
        uygun = {r[0] for r in con.execute(
            f"""SELECT DISTINCT plan_id FROM plan_host_program
                 WHERE plan_id IN ({",".join("?" * len(hepsi))})
                   AND (program_code = ? OR program_code = ?)""",
            [r["id"] for r in hepsi] + [anadal.upper(), taban.upper()])}
        suzulmus = [r for r in hepsi if r["id"] in uygun]
        if suzulmus:
            hepsi = suzulmus
    return _en_guncel(hepsi)


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
