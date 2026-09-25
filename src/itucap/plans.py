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
    metin = (iteration or "").casefold()
    yillar = [int(y) for y in _YIL_RE.findall(metin)]
    if not yillar:
        return (0, 0)
    # ★ Faz 92 — "Öncesi" ESKİ. "2023-2024 / Güz Dönemi Öncesi" 2023'ten
    # ÖNCE başlayanların planı; aynı yılla başlayan "2023-2024 … ile
    # 2026-2027 … Arası" ondan YENİ. İkisi de (2023, 0) alıyordu ve eşitliği
    # satır sırası bozuyordu: gerçek katalogda 19 (anadal, ÇAP/yandal)
    # çiftinde (ör. ELE → GEO) yürürlükten kalkmış plan seçiliyordu.
    # Kapsadığı en geç başlangıç Y-1 — anahtar da o.
    if "öncesi" in metin or "oncesi" in metin:
        return (yillar[0] - 1, 0)
    # "sonra": OBS'de bir başlık "Sonraı" diye yazılmış (ölçüldü) — "sonras"
    # onu kapalı aralık sanıyordu.
    acik = 1 if "sonra" in metin else 0
    return (max(yillar) if acik else yillar[0], acik)


def en_guncel_satir(rows, anadal: str = ""):
    """`(id, iteration, source)` satırlarından en güncel olanı (satırın kendisi).

    ★ Faz 92: başvuru taraması (`basvuru.survey`) da BUNU kullanıyor. Eskiden
    kendi seçicisi vardı (`best_plan`) ve ikisi bazı çiftlerde farklı
    iterasyonu seçiyordu: pencerede gösterilen plan, program seçilince
    kullanılan plan değildi.

    ★ Eşitlikte sıra AÇIK: önce anadalın KENDİ planı (ISL öğrencisi için
    "ISL_ELE", "TUMMUH_ELE" değil — ikisi de OBS'de ISL'ye açık ve ikisinin
    de iterasyonu boş), sonra küçük id. Eskiden eşitliği sorgunun satır
    sırası bozuyordu ve o sıra SQLite'ın seçtiği indekse bağlıydı: iki
    sorgu aynı iki plandan farklısını seçiyordu.
    """
    if not rows:
        return None
    from .normalize import base_program_code
    an = (anadal or "").upper()
    ozel = {an, base_program_code(an)} - {""}

    def anahtar(r):
        host = (r["host_program_code"] or "").upper() if "host_program_code" in r.keys() else ""
        return (1 if (r["source"] == "obs") else 0, *iteration_key(r["iteration"]),
                1 if host in ozel else 0, -r["id"])
    return max(rows, key=anahtar)


def _en_guncel(rows, anadal: str = "") -> int | None:
    """`(id, iteration, source)` satırlarından en güncel planın id'si."""
    en = en_guncel_satir(rows, anadal)
    return en["id"] if en is not None else None


def ev_sahibi_suzgeci(con, plan_type: str, anadal: str,
                      program_code: str | None = None) -> tuple[set[int], set[int]]:
    """(anadala AÇIK planlar, OBS'de ilişkili program listesi OLAN planlar).

    Kaynak `plan_host_program` — OBS plan sayfasındaki "İlişkili Programlar"
    tablosu. Anadalın kendisi de dil eşinin taban kodu da (HTAE → HTA)
    kabul ediliyor; OBS çoğu planda ikisini birlikte yazıyor ama hepsinde
    değil.

    İkinci küme, "bu planın listesi VAR ve sen onda YOKSUN" ile "bu planın
    listesi hiç çekilmemiş" ayrımı için: ikincisinde çağıran yedek bir
    yönteme düşebilir, birincisinde düşmemeli.
    """
    from .normalize import base_program_code
    an = (anadal or "").upper()
    kabul = {an, base_program_code(an).upper()} - {""}
    sql = """SELECT h.plan_id, h.program_code FROM plan_host_program h
               JOIN plan p ON p.id = h.plan_id WHERE p.plan_type = ?"""
    args: list = [plan_type]
    if program_code:
        sql += " AND p.program_code = ?"
        args.append(program_code)
    acik: set[int] = set()
    listeli: set[int] = set()
    for pid, kod in con.execute(sql, args):
        listeli.add(pid)
        if (kod or "").upper() in kabul:
            acik.add(pid)
    return acik, listeli


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
        """SELECT id, iteration, source, host_program_code FROM plan
            WHERE program_code=? AND plan_type=?""",
        (program_code, plan_type)).fetchall()
    if not hepsi:
        return None
    if anadal:
        uygun, _ = ev_sahibi_suzgeci(con, plan_type, anadal, program_code)
        suzulmus = [r for r in hepsi if r["id"] in uygun]
        if suzulmus:
            hepsi = suzulmus
    return _en_guncel(hepsi, anadal)


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
