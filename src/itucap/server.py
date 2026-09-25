"""FAZ 8 — Yerel uygulama: arayüz artık YAZABİLİYOR.

    make app          # http://127.0.0.1:8770 açılır

Faz 6–7'de arayüz üretilen bir **rapordu**: okunur, düzenlenebilir ama
düzenleme sayfa kapanınca kaybolurdu. Program/dönem/transkript değiştirmek
için terminale dönüp dosya düzenlemek gerekiyordu. Bu, aracın en çok
kullanılacak üç işlemini en zor işlem yapıyordu.

`make ui` (statik tek dosya) **bozulmadı** — çift tıkla açılır, sunucusuz
çalışır, düzenleme panelleri salt okunur görünür ve nedenini yazar.
`make app` aynı sayfayı sunar ve yazma uçlarını açar.

Neden `http.server`? Bağımlılık eklemeden, tek dosyada, tek kullanıcı için
yeterli. Bu bir web servisi değil; **kendi makinende çalışan bir form**.

## Güvenlik — yerel diye açık değil

Tarayıcıdaki HERHANGİ bir sekme `http://127.0.0.1:8770`'e istek atabilir.
Üç kat koruma var:

1. **Yalnız 127.0.0.1'e bağlanır.** Ağdaki başka makine erişemez.
2. **Her çalıştırmada rastgele bir jeton** üretilir, sayfaya gömülür ve her
   yazma isteğinde `X-Itucap-Token` başlığında beklenir. Jetonu bilmeyen bir
   sekme yazamaz.
3. **Origin denetimi.** Başka bir sitenin sayfası istek atarsa reddedilir.

⚠️ Sunucu KİŞİSEL VERİ sunar (notların, ilerlemen). Portu dışarı açma,
tünelleme, paylaşma.
"""
from __future__ import annotations

import json
import re
import secrets
import sys
import sqlite3
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qs, urlparse

from . import changes as CH
from . import config, db, declared
from . import policy as POL
from . import recommend as REC
from . import student as S
from . import ui as UI

MAX_BODY = 1 << 20          # 1 MB — transkript bile çok küçük
HARD_BODY = 16 << 20        # bunun üstünü okumaya bile kalkışma
# ★ Yönetmelik MADDE 20 sırasıyla: harf notları yüksekten alçağa, sonra
# kredisiz ders işaretleri ve muafiyet. `FD` güncel ölçekte YOK — eski
# transkriptlerde tanınıyor ama yeni giriş için önerilmiyor, o yüzden burada
# da yok. Elle yazan kullanıcı için ayrıştırıcı yine kabul ediyor.
GRADES = ["AA", "BA+", "BA", "BB+", "BB", "CB+", "CB", "CC+", "CC",
          "DC+", "DC", "DD+", "DD", "FF", "VF",
          "BL", "BZ", "M", "T", "E"]


def can_refresh() -> bool:
    """Bu ortamda OBS'den veri çekilebilir mi?

    `pipeline` tarama bağımlılıklarını (`httpx`, `selectolax`) içeri alıyor.
    Yerelde varlar; tarayıcıda (Pyodide) yoklar ve gerekmiyorlar da — katalog
    siteyle birlikte yayınlanıyor. Bunu bir BAYRAK olarak taşımak, arayüzün
    çalışmayacak bir düğme göstermesini engelliyor.
    """
    import importlib.util

    return all(importlib.util.find_spec(m) is not None
               for m in ("httpx", "selectolax"))


# ★ Hiçbir şey YAZMAYAN uçlar. `dispatch` bunlardan sonra `snapshot()`
# çağırmıyor: bütün raporu yeniden kurmak ölçülen ~1.5 sn'yi harf başına
# ödemek demek olurdu (Faz 25/B1).
#
# ⚠️ Bu listeye bir uç eklemek "bu uç durumu DEĞİŞTİRMİYOR" demektir.
# Yazan bir ucu buraya koymak, kullanıcının değişikliği yaptığını ama
# ekranda göremediği bir hata üretir — sessiz ve bulması zor.
READ_ONLY_PATHS = frozenset({"/api/katalog", "/api/ders", "/api/crn",
                             "/api/transcript/preview", "/api/capbitis",
                             "/api/tercih/onizle", "/api/yolharitasi",
                             "/api/kalmariski"})


class State:
    """Sunucunun paylaşılan durumu. Ayar değişince yeniden yükleniyor."""

    def __init__(self, label: str = "ben", n_schedules: int = 3,
                 max_load: float | None = None):
        self.label = label
        self.n_schedules = n_schedules
        self.max_load = max_load
        self.token = secrets.token_urlsafe(24)
        self.lock = threading.Lock()
        # ★ ThreadingHTTPServer her isteği ayrı iş parçacığında çalıştırıyor.
        # Bağlantıyı paylaşıyoruz ama TÜM DB işi `self.lock` altında —
        # check_same_thread=False tek başına yeterli değil, kilit şart.
        self.con = db.reference_db(same_thread=False)
        self.ucon = db.user_db(same_thread=False)
        self.con.row_factory = sqlite3.Row
        self.ucon.row_factory = sqlite3.Row
        self.student_id = S.ensure_student(self.ucon, label)
        self.busy = False
        # ★★ Faz 28 GÖÇÜ — beyan denklikleri kullanıcı DB'sine taşındı.
        # İki iş: (1) katalogda kalmış eski satırları sil — o dosya
        # yayınlanan sitenin içine giriyor; (2) `denklikler.toml`'u kullanıcı
        # DB'sine uygula, çünkü `load_equivalences` artık katalogdaki
        # beyanları okumuyor ve göç etmeyen kullanıcı beyanlarını SESSİZCE
        # kaybederdi.
        #
        # ⚠️ Dosya YOKSA dokunmuyoruz: "dosya yok" ile "beyan yok" ayrı
        # şeyler, ve ikincisini varsayıp kullanıcı DB'sini boşaltmak veri
        # silmek olurdu.
        try:
            declared.temizle_referans(self.con)
            if declared.DEFAULT_PATH.exists():
                declared.apply(self.ucon)
        except Exception:                                   # noqa: BLE001
            pass          # göç başarısızsa sunucu yine açılmalı

    # ------------------------------------------------------------- okuma
    def settings(self) -> config.Settings:
        return config.Settings.load()

    def plan_ids(self) -> tuple[int | None, int | None]:
        # ★ `pipeline` DEĞİL: o modül tarama bağımlılıklarını (httpx,
        # selectolax) içeri alıyor ve motoru tarayıcıda çalışamaz kılıyordu.
        from .plans import resolve_plans as _resolve_plans
        return _resolve_plans(self.con, self.settings())

    def second_plan_ids(self) -> dict[str, int | None]:
        """{'cap': id|None, 'yandal': id|None} — ikisi AYNI ANDA olabilir."""
        from .plans import resolve_seconds as _resolve_seconds
        return {s["kind"]: s["planId"]
                for s in _resolve_seconds(self.con, self.settings())}

    def snapshot(self) -> dict:
        settings = self.settings()
        from .plans import anadal_plan as _anadal_plan
        anadal_id = _anadal_plan(self.con, settings)
        from .plans import resolve_seconds as _resolve_seconds
        ikinci = _resolve_seconds(self.con, settings)
        # ★ İkinci programları AÇIKÇA veriyoruz. `cap_id` konumsalı tarihsel
        # bir isim (içinde yandal planı da olabiliyor) ve iki program birden
        # gelince belirsizleşiyor — liste o belirsizliği ortadan kaldırıyor.
        data = UI.collect(self.con, self.ucon, self.student_id, settings,
                          anadal_id, None, max_load=self.max_load,
                          n_schedules=self.n_schedules, seconds=ikinci)
        data["live"] = True
        data["token"] = self.token
        data["setup"] = self.setup()
        data["changes"] = self.changes()
        data["suggestions"] = self.suggestions()
        data["equivalences"] = self.applied_equivalences()
        # Tarayıcıda tarama yapılamaz; arayüz "Veriyi tazele" düğmesini
        # buna bakarak gizliyor.
        data["canRefresh"] = can_refresh()
        data["savedPicks"] = self.saved()   # ★ "saved" DEĞİL: uç
        data["alternatives"] = S.load_alts(self.ucon, self.student_id,
                                           self.settings().term)   # Faz 77
        data["alternativesMax"] = S.ALT_MAX
        # cevaplarındaki kayıt sayacıyla çakışıyordu (test yakaladı).
        return data

    # ------------------------------------------------------------ yönlendirme
    # ★ Yazma uçlarının yönlendirmesi HTTP katmanında değil, burada.
    #
    # Sebep: aynı `State` iki farklı taşıyıcıyla kullanılıyor — yerel HTTP
    # sunucusu (`make app`) ve tarayıcıda Pyodide (statik site). Yönlendirme
    # `do_POST` içinde kalsaydı web sürümü onu KOPYALAMAK zorunda kalırdı ve
    # iki kopya zamanla ayrışırdı: bir uç burada düzelir, orada düzelmez.
    # Tek yerde durunca iki taşıyıcı da aynı davranışı alıyor.
    def _route(self, path: str, b: dict) -> dict | None:
        if path == "/api/transcript":
            return self.save_transcript(b.get("items") or [],
                                        bool(b.get("replace")),
                                        b.get("remove") or [])
        if path == "/api/transcript/paste":
            n, bad = self.save_text(b.get("text") or "", bool(b.get("replace")))
            return {"saved": n, "bad": bad}
        if path == "/api/transcript/remove":
            self.remove_course(str(b.get("course") or ""))
            return {}
        if path == "/api/transcript/restore":
            return {"restored": self.restore_backup(b.get("file") or "")}
        if path == "/api/programs":
            self.save_programs(b)
            return {}
        if path == "/api/refresh":
            return self.refresh(bool(b.get("skipObs")))
        if path == "/api/equivalence":
            return {"applied": self.apply_equivalence(
                str(b.get("target") or ""), b.get("sources") or [],
                str(b.get("note") or ""))}
        if path == "/api/equivalence/remove":
            return {"applied": self.remove_equivalence(str(b.get("target") or ""))}
        if path == "/api/picks":
            self.save_picks(b.get("picks") or [])
            return {}
        if path == "/api/picks/clear":
            self.clear_picks()
            return {}
        if path == "/api/alternatif":
            # Faz 77 — adlı alternatif program (Plan B…). Ana program değişmez.
            pairs = [(str(p.get("course", "")), str(p.get("crn", "")))
                     for p in (b.get("picks") or [])]
            return {"alternatifAdi": S.save_alt(self.ucon, self.student_id,
                                                self.settings().term,
                                                str(b.get("name") or ""), pairs)}
        if path == "/api/alternatif/sil":
            S.delete_alt(self.ucon, self.student_id, self.settings().term,
                         str(b.get("name") or ""))
            return {}
        if path == "/api/maxload":
            self.save_max_load(b.get("maxLoad") or 0)
            return {}
        if path == "/api/donem":
            self.save_term(b.get("donem") or 0,
                           b.get("capBaslangic")
                           if b.get("capBaslangic") is not None else None)
            return {}
        if path == "/api/crn":
            return {"crn": self.resolve_crns(b.get("crns") or [])}
        if path == "/api/transcript/preview":
            return {"preview": self.preview_text(b.get("text") or "")}
        if path == "/api/tercih":
            self.save_prefs(b)
            return {}
        if path == "/api/tercih/onizle":
            return {"onizleme": self.preview_prefs(b)}
        if path == "/api/capbitis":
            # Faz 59 — başvuru penceresinde "ya ÇAP'ı şurada yapsaydım".
            return {"capBitis": UI.cap_bitisleri(
                self.con, self.ucon, self.student_id, self.settings(),
                b.get("plans") or [], b.get("bu") or [], b.get("maxLoad") or 0)}
        if path == "/api/yolharitasi":
            # Faz 61 — yol haritası senaryosu (daha hafif yük, boş dönemler).
            return {"senaryo": UI.yol_senaryosu(
                self.con, self.ucon, self.student_id, self.settings(),
                b.get("bu") or [], b.get("maxLoad") or 0, b.get("bos") or [],
                b.get("zor"))}
        if path == "/api/kalmariski":
            # Faz 75 — "bu dersten kalırsam mezuniyetim ne kadar gecikir".
            return {"kalmaRiski": UI.kalma_riski(
                self.con, self.ucon, self.student_id, self.settings(),
                b.get("bu") or [], b.get("maxLoad") or 0)}
        if path == "/api/katalog":
            return {"katalog": self.search_catalog(str(b.get("q") or ""))}
        if path == "/api/ders":
            return {"crn": self.course_sections(str(b.get("course") or ""))}
        if path == "/api/watch":
            return self.toggle_watch(str(b.get("course") or ""))
        if path == "/api/kilit":
            return self.toggle_lock(str(b.get("course") or ""),
                                    str(b.get("crn") or ""),
                                    aralik=str(b.get("aralik") or ""),
                                    satir=str(b.get("satir") or ""))
        if path == "/api/mesgul":
            return self.save_busy(b.get("day") or 0, b.get("start") or 0,
                                  b.get("end") or 0, str(b.get("label") or ""),
                                  str(b.get("remove") or ""))
        return None

    def dispatch(self, path: str, body: dict) -> dict | None:
        """Bir yazma ucunu çalıştırıp YENİ DURUMU döndürür.

        `None` = böyle bir uç yok (HTTP tarafında 404). `ValueError` geçerli
        ama reddedilen istek (400); başka istisna beklenmedik hata (500).
        Bu ayrımı burada tutmak, iki taşıyıcının aynı hata anlamlarını
        paylaşmasını sağlıyor.
        """
        extra = self._route(path, body)
        if extra is None:
            return None
        # ★ SALT OKUNUR uçlar tam durumu YENİDEN HESAPLAMIYOR (Faz 25/B1).
        # `snapshot()` bütün raporu kuruyor (adaylar, programlar, kademeler):
        # ölçüldü, tek çağrı ~1.5 sn. Harf başına arama yapan bir uç için bu
        # kullanılamaz. Bu uçlar hiçbir şey YAZMADIĞI için durum da değişmiyor.
        if path in READ_ONLY_PATHS:
            return extra
        # ★★ Yazdıktan sonra ANA DOSYAYI eksiksiz bırak (23.08.2026).
        # Tarayıcı sürümü kalıcılığı `user.sqlite3` dosyasını KOPYALAYARAK
        # sağlıyor; WAL kipinde veri yan dosyada kalıyordu ve kopyalanan ana
        # dosya boş çıkıyordu. Kip artık tarayıcıda TRUNCATE ama bu çağrı
        # kuşak farkı olan (eskiden WAL açılmış) veritabanlarını da kurtarıyor.
        db.checkpoint(self.ucon)
        return {**extra, **self.snapshot()}

    def setup(self) -> dict:
        """Düzenleme panellerini besleyen veri: programlar, planlar, transkript."""
        settings = self.settings()
        anadal_id, second_id = self.plan_ids()
        return {
            "anadalProgram": settings.anadal_program,
            "anadalPlanId": anadal_id,
            "secondKind": settings.second_kind,
            "secondProgram": settings.second_program,
            "secondPlanId": second_id,
            # ★ Her tür için AYRI seçim — 'ikisi' seçilince iki kutu birden.
            "secondChoice": {k: {"program": settings.program_of(k),
                                 "planId": settings.plan_id_of(k)}
                             for k in ("cap", "yandal")},
            # ★★ Kutuda YALNIZ ekstralar; türetilenler ayrı alanda ve arayüzde
            # okunur rozet olarak duruyor (kullanıcı isteği 27.08.2026).
            "programCodes": sorted(
                {c.strip().upper() for c in settings.program_codes if str(c).strip()}
                - set(settings.derived_programs)),
            "derivedPrograms": settings.derived_programs,
            # ★ Dil eşi ÖNERİSİ (BLG → BLGE). Otomatik EKLENMİYOR: "bu kodla
            # da kayıt yapabilirsin" bir iddia ve yanlışsa alınamayacak dersi
            # alınabilir gösterir. Yalnız katalogda GERÇEKTEN var olan ve
            # şubesi bulunan eşler öneriliyor; eklemek kullanıcının tıkı.
            #
            # ⚠️ KAYITLI ayara göre değil, TÜM eşler gönderiliyor (ölçüldü:
            # 78 çift). Kullanıcı kutuda bölümü değiştirdiğinde öneri de
            # anında değişmeli; kayıtlı ayara bağlasaydık öneri ancak
            # KAYDETTİKTEN SONRA görünürdü — yani tam gerektiği anda değil.
            "languageSiblings": self._dil_esleri(),
            "donem": settings.donem,
            # ÇAP'a başlanan yarıyıl — ikinci anadal kredi tabanını
            # belirliyor. 0 = beyan edilmedi (motor taban iddia etmez).
            "capBaslangic": settings.cap_baslangic_yariyili,
            "unit": settings.unit,
            "maxLoad": settings.max_load,
            "maxLoadAuto": settings.max_load_auto,
            "grades": GRADES,
            # ★ İkinci program seçimi: YALNIZ o tipte planı OLAN bölümler ve
            # dil varyantları tekleştirilmiş (BLG + BLGE -> BLG).
            # Planı olmayan bölümü listelemek, kullanıcıya seçtirip sonra
            # "plan yok" demek olurdu; BLG/BLGE ayrımı ise ÇAP'ta hiç yok.
            "secondPrograms": self.second_programs(),
            # ⚠️ `COALESCE(pr.name, p.program_code)` KALDIRILDI (inceleme C3).
            # Adı bilinmeyen programa kodun kendisini ad diye vermek, arayüzde
            # "ECN — ECN" üretiyordu: kod bir ad DEĞİL, ve okuyan kişi adın
            # gerçekten "ECN" olduğunu sanıyordu. Ölçüldü: 4 program kodunun
            # (ECN, SEC, VBA, YZV) `program` tablosunda satırı yok — adları
            # veride hiç yok, uydurulamaz. Artık `name` NULL geliyor ve
            # arayüz "adı katalogda yok" yazıyor.
            "programs": [dict(r) for r in self.con.execute(
                """SELECT DISTINCT p.program_code AS code,
                          pr.name AS name, p.plan_type
                   FROM plan p LEFT JOIN program pr ON pr.code = p.program_code
                   WHERE p.program_code IS NOT NULL
                   ORDER BY p.program_code""")],
            # ★ Faz 54: `hosts` — planın geçerli olduğu anadal programları.
            # Pencere planları "bölümüne uygun" / "başka bölümlerin" diye
            # ayırıyor; eskiden 38 BLG ÇAP planı tek listedeydi ve hangisinin
            # senin olduğu yazmıyordu.
            "plans": [dict(r) for r in self.con.execute(
                """SELECT id, program_code, plan_type, host_program_code,
                          title, source,
                          (SELECT COUNT(*) FROM plan_slot WHERE plan_id=plan.id) AS slots,
                          (SELECT group_concat(program_code, ' ') FROM plan_host_program
                            WHERE plan_id=plan.id) AS hosts
                   FROM plan ORDER BY plan_type, program_code, id DESC""")],
            "transcript": self.transcript(),
            "checklist": self.plan_checklist(),
            "backups": S.backups(),
            "passFail": list(POL.PASS_FAIL_GRADES),
            # İzleme listesi (yapılacaklar 4.3). BOŞ liste "planındaki tüm
            # açık dersleri izle" demek — arayüz bu ayrımı yazmak zorunda.
            "watchCourses": [str(c).upper() for c in (settings.watch_courses or [])],
            # ★ Faz 27 — yumuşak tercihler. Sıralamaya girer, ELEME YAPMAZ.
            "prefs": {
                "enErken": settings.tercih_en_erken,
                "bosGunler": list(settings.tercih_bos_gunler or []),
                "kampus": bool(settings.tercih_kampus_degisimi),
                "cevrimici": bool(settings.tercih_cevrimici),
                "istenenHocalar": list(settings.tercih_istenen_hocalar or []),
                "istenmeyenHocalar": list(settings.tercih_istenmeyen_hocalar or []),
            },
        }

    def transcript(self) -> list[dict]:
        rows = self.ucon.execute(
            """SELECT course_code, grade, status, source FROM earned_course
               WHERE student_id=? ORDER BY course_code""", (self.student_id,)).fetchall()
        names = {r[0]: (r[1], r[2]) for r in self.con.execute(
            "SELECT code, name, credits FROM course")}
        out = []
        for r in rows:
            name, credits = names.get(r["course_code"], ("", None))
            out.append({"course": r["course_code"], "grade": r["grade"],
                        "status": r["status"], "source": r["source"],
                        "name": name or "", "credits": credits,
                        "known": r["source"] != "manual-nograde"})
        return out

    def plan_checklist(self) -> list[dict]:
        """★ Planın dersleri, dönem dönem, tik atılabilir hâlde.

        Tek tek arayarak girmek 60+ ders için işkence. Plan zaten elimizde:
        listele, kullanıcı tiklesin. Havuz slotları için seçenekler de
        veriliyor — 'ITB havuzundan HUK 217 aldım' diyebilmek gerekiyor.
        """
        settings = self.settings()
        anadal_id, second_id = self.plan_ids()
        taken = {r["course_code"]: r for r in self.ucon.execute(
            """SELECT course_code, grade, status FROM earned_course
               WHERE student_id=?""", (self.student_id,))}
        names = {r[0]: (r[1], r[2]) for r in self.con.execute(
            "SELECT code, name, credits FROM course")}
        out = []
        for plan_id, role in ((anadal_id, "ANADAL"),
                              (second_id, settings.second_role or "CAP")):
            if plan_id is None:
                continue
            plan = self.con.execute("SELECT * FROM plan WHERE id=?",
                                    (plan_id,)).fetchone()
            groups: dict = {}
            for slot in self.con.execute(
                """SELECT id, term_no, slot_kind, course_code, pool_label_raw,
                          pool_category, credits
                   FROM plan_slot WHERE plan_id=?
                   ORDER BY term_no IS NULL, term_no, position""", (plan_id,)
            ):
                term = slot["term_no"] or 0
                codes = ([slot["course_code"]] if slot["course_code"] else
                         [r[0] for r in self.con.execute(
                             "SELECT course_code FROM pool_option WHERE slot_id=?",
                             (slot["id"],))])
                items = []
                for code in filter(None, codes):
                    name, credits = names.get(code, ("", slot["credits"]))
                    got = taken.get(code)
                    items.append({
                        "course": code, "name": name or "",
                        "credits": credits if credits is not None else slot["credits"],
                        "grade": (got["grade"] if got else None),
                        "status": (got["status"] if got else ""),
                        "taken": bool(got),
                    })
                if not items:
                    continue
                groups.setdefault(term, []).append({
                    "slotId": slot["id"],
                    "pool": slot["pool_label_raw"] or "",
                    "category": slot["pool_category"] or "",
                    "required": slot["slot_kind"] == "REQUIRED",
                    "options": items,
                })
            out.append({
                "role": role, "planId": plan_id,
                "program": plan["program_code"] if plan else "",
                "termBased": bool(plan["is_term_based"]) if plan else False,
                "terms": [{"term": t, "slots": v} for t, v in sorted(groups.items())],
            })
        return out

    def search_courses(self, query: str, limit: int = 40) -> list[dict]:
        query = (query or "").strip()
        if len(query) < 2:
            return []
        like = f"%{query}%"
        rows = self.con.execute(
            """SELECT code, name, credits, ects FROM course
               WHERE code LIKE ? OR name LIKE ?
               ORDER BY (code LIKE ?) DESC, code LIMIT ?""",
            (like, like, f"{query}%", limit)).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------- yazma
    def save_transcript(self, items: list[dict], replace: bool,
                        remove: Iterable[str] = ()) -> dict:
        """Formdan gelen kayıtlar. Kural `student.make_entry` — metin girişiyle
        AYNI yer, yoksa aynı girdi nereden girildiğine göre farklı sonuç
        verirdi.

        ★★ FAZ 47 — `remove` (kullanıcı bildirdi 18.09.2026: *"plandan
        işaretle kısmında eğer tik geri çekilirse dersi alınmış olarak
        gözükmesin"*).

        Ölçüldü ve haklıydı: "Plandan işaretle" penceresi YALNIZ tikli
        dersleri gönderiyordu ve `replace=False` ile ekliyordu. Tik geri
        çekilince hiçbir şey olmuyordu — ders transkriptte kalıyor, ekranda
        "almışsın" görünüyordu. (Ölçüm: GEO 303E tiklenip kaydedildi → 37
        satır 38 oldu; tik geri çekilip kaydedildi → **hâlâ 38**.)

        ⚠️ `replace=True` YAPMADIK, çünkü o her şeyi siler: elle girilmiş,
        plan dışı dersler de gider. `remove` yalnız pencerenin GÖSTERDİĞİ ve
        tiklenmemiş dersleri taşıyor — pencerenin görmediği hiçbir satıra
        dokunulmuyor.
        """
        entries = []
        for item in items:
            note = "--" if item.get("inProgress") else ""
            entry = S.make_entry(str(item.get("course", "")),
                                 item.get("grade"), note)
            if entry:
                entries.append(entry)
        kodlar = {S.normalize_course_code(str(c)) for c in (remove or ())}
        kodlar = {c for c in kodlar if c}
        # Silinecek gerçekten var mı? Yedeği boşuna almayalım (son 12 tutuluyor).
        silinecek = 0
        if kodlar:
            yer = ",".join("?" * len(kodlar))
            silinecek = self.ucon.execute(
                f"SELECT COUNT(*) FROM earned_course WHERE student_id=?"
                f" AND course_code IN ({yer})",
                (self.student_id, *sorted(kodlar))).fetchone()[0]
        self._backup(replace or bool(silinecek))
        if silinecek:
            yer = ",".join("?" * len(kodlar))
            self.ucon.execute(
                f"DELETE FROM earned_course WHERE student_id=?"
                f" AND course_code IN ({yer})",
                (self.student_id, *sorted(kodlar)))
            self.ucon.commit()
        S.add_entries(self.ucon, self.student_id, entries, replace=replace)
        return {"saved": len(entries), "removed": silinecek}

    def _backup(self, silici: bool) -> None:
        """Silici yazmadan önce yedek. Elle girilmiş transkript geri gelmez."""
        if silici:
            S.backup(self.ucon, self.student_id)
            S.prune_backups()

    def preview_text(self, text: str) -> dict:
        """Yapıştırılan metni ÇÖZ ama YAZMA — önizleme.

        ★ İlk kullanıcı incelemesi A1: pencere kapanıyor, işlem başarılıymış
        gibi görünüyor, oysa notlar kaybolmuş olabiliyordu. Uygulamadan önce
        ne olacağını göstermek, sessiz veri kaybını imkânsız kılıyor.
        """
        entries, bad, uyarilar = S.parse_report(text or "")
        return {
            "count": len(entries),
            "passed": sum(1 for e in entries if e.status == "PASSED"),
            "inProgress": sum(1 for e in entries if e.status == "IN_PROGRESS"),
            "failed": sum(1 for e in entries if e.status == "FAILED"),
            # ⚠️ Kesme SESSİZ değil: kaç satır gösterilmediği ayrıca yazıyor.
            "items": [{"course": e.course_code, "grade": e.grade,
                       "status": e.status} for e in entries[:60]],
            "shown": min(len(entries), 60),
            "bad": bad[:20], "badTotal": len(bad),
            "warnings": uyarilar[:20], "warningTotal": len(uyarilar),
        }

    def save_text(self, text: str, replace: bool) -> tuple[int, list[str]]:
        """Toplu yapıştırma — transkripti olduğu gibi yapıştırabilmek için."""
        entries, bad, _uyari = S.parse_report(text or "")
        self._backup(replace)
        S.add_entries(self.ucon, self.student_id, entries, replace=replace)
        return len(entries), bad[:20]

    def remove_course(self, code: str) -> int:
        S.backup(self.ucon, self.student_id)
        cur = self.ucon.execute(
            "DELETE FROM earned_course WHERE student_id=? AND course_code=?",
            (self.student_id, S.normalize_course_code(code)))
        self.ucon.commit()
        return cur.rowcount

    def save_programs(self, body: dict) -> dict:
        """Anadal / ikinci program seçimini `settings.toml`'a yazar."""
        values: dict = {}
        kind = str(body.get("secondKind") or "").lower()
        # ★★ DOĞRULAMA `SECOND_CHOICES`'A BAKAR, `SECOND_KINDS`'A DEĞİL
        # (hata bildirimi 24.08.2026: "yandal ve çap planını aynı anda
        # yapmaya çalışınca program türü geçersiz diyor").
        #
        # İkisi farklı soruların cevabı:
        #   SECOND_KINDS   — TEKİL bir türün rolü/etiketi/OBS plan tipi.
        #                    "ikisi" tekil bir tür DEĞİL, orada yok.
        #   SECOND_CHOICES — kullanıcının SEÇEBİLECEĞİ değerler; "ikisi" var.
        #
        # `Settings.load` zaten `SECOND_CHOICES`'a bakıyordu; burası
        # `SECOND_KINDS`'a bakıyordu. İki kaynağın aynı soruya farklı cevap
        # vermesi — bu projede tekrar tekrar canımızı yakan hata sınıfı.
        if kind not in config.SECOND_CHOICES:
            raise ValueError(
                "ikinci program türü geçersiz; geçerli değerler: "
                + ", ".join(sorted(config.SECOND_CHOICES)))
        values["second_kind"] = kind
        anadal = _clean_code(body.get("anadalProgram"))
        if not anadal:
            raise ValueError("anadal programı boş olamaz")
        self._dogrula_program(anadal, "anadal")
        values["anadal_program"] = anadal
        if body.get("anadalPlanId"):
            values["anadal_plan_id"] = int(body["anadalPlanId"])
        # ★ 'ikisi' seçilirse İKİ program da geliyor: {cap: {...}, yandal: {...}}.
        # Tek program seçimlerinde eski gövde biçimi (secondProgram) hâlâ
        # geçerli — statik site ve eski çağrılar bozulmasın.
        istenen = config.SECOND_CHOICES.get(kind, ())
        gelen = body.get("secondPrograms") or {}
        for k in istenen:
            kod = _clean_code((gelen.get(k) or {}).get("program")
                              if gelen else body.get("secondProgram"))
            if not kod:
                raise ValueError(f"{k} programının kodu boş olamaz")
            self._dogrula_program(kod, config.SECOND_KINDS[k][1] if k in
                                  config.SECOND_KINDS else k)
            values[f"{k}_program"] = kod
            plan_id = ((gelen.get(k) or {}).get("planId") if gelen
                       else body.get("secondPlanId"))
            if plan_id:
                values[f"{k}_plan_id"] = int(plan_id)
        codes = [_clean_code(c) for c in (body.get("programCodes") or [])]
        codes = [c for c in codes if c]
        # ⚠️ Bu kutu SERBEST METİN — kullanıcı elle yazabiliyor. Tanınmayanı
        # sessizce atmak, yazdığı kodun işe yaradığını sanmasına yol açardı.
        bilinmeyen = [c for c in codes if self._program_var(c) is False]
        if bilinmeyen:
            raise ValueError(
                "katalogda olmayan program kodu: " + ", ".join(bilinmeyen)
                + " (listeden seçildiğinde kod otomatik olarak doğru girilir)")
        # ★★ Kutuda YALNIZ EKSTRALAR durur (kullanıcı isteği 27.08.2026).
        # Anadal/ÇAP/yandal kodları `allowed_programs` içinde her seferinde
        # yeniden türetiliyor; dosyaya da yazmak onları elle yazılmış
        # kodlardan ayırt edilemez kılardı ve bölüm değişince eskisi kutuda
        # kalırdı. Eski dosyalar da bu kayıtla temizleniyor.
        turetilmis = {values["anadal_program"].upper(),
                      *(values[f"{k}_program"].upper() for k in istenen)}
        ekstra = [c for c in dict.fromkeys(codes) if c not in turetilmis]
        # ⚠️ Boş liste de YAZILIYOR: kullanıcı son ekstrayı sildiyse dosyada
        # kalması, sildiğini sanmasına yol açardı.
        values["program_codes"] = ekstra
        config.update_settings(values)
        self._reenroll()
        return values

    # ---- dil eşi önerisi ---------------------------------------------
    def _dil_esleri(self) -> dict:
        """`{'BLG': {'code':'BLGE','sections':712}, …}` — DOĞRULANMIŞ eşler.

        ★ `BLG` seçen öğrencinin `BLGE` şubelerine de kayıt yapabildiği çok
        yaygın (kullanıcının kendi ayarı: HTAE, BLG, BLGE). Ama bu bir
        İDDİA: yanlışsa, alamayacağı bir dersi alabilir gösterir. O yüzden
        otomatik EKLENMİYOR — öneriliyor, ekleme kullanıcının tıkı.

        ⚠️ Öneri de uydurulmuyor. Eşin katalogda GERÇEKTEN bir programı ya
        da planı olmalı VE o koda açık en az bir şube bulunmalı; şubesi
        olmayan kodu önermek, işe yaramayacak bir seçenek sunmak olurdu.
        Ölçüldü: 205 koddan 78'inin doğrulanmış bir eşi var.

        ⚠️ `HTAE → HTA` GERÇEK bir çift (Harita Mühendisliği / İngilizce).
        `normalize.merge_language_variants` yorumu bunun aksini söylüyordu;
        katalogda ölçünce ikisinin de programı ve yüzlerce şubesi çıktı.
        Yorumdan değil VERİDEN karar veriyoruz.
        """
        # ★ Katalog değişmedikçe sabit; ölçüldü ~50 ms ve `snapshot()` her
        # yazma ucundan sonra çağrılıyor. `refresh` önbelleği düşürüyor.
        onbellek = getattr(self, "_esler_onbellek", None)
        if onbellek is not None:
            return onbellek
        try:
            kodlar = {r[0] for r in self.con.execute(
                "SELECT code FROM program WHERE code IS NOT NULL")}
            kodlar |= {r[0] for r in self.con.execute(
                "SELECT DISTINCT program_code FROM plan WHERE program_code IS NOT NULL")}
            sube = {r[0]: r[1] for r in self.con.execute(
                """SELECT upper(program_code), COUNT(DISTINCT crn)
                   FROM lesson_allowed_program GROUP BY 1""")}
        except sqlite3.Error:
            return {}
        out: dict[str, dict] = {}
        for kod in kodlar:
            es = kod[:-1] if kod.endswith("E") else kod + "E"
            if es and es != kod and es in kodlar and sube.get(es):
                out[kod] = {"code": es, "sections": sube[es]}
        self._esler_onbellek = out
        return out

    # ---- program kodu gerçekten var mı --------------------------------
    def _program_var(self, code: str) -> bool | None:
        """True/False — ve bakılacak veri yoksa `None`: "buradan bakılamaz".

        ★★ KAYNAK, AÇILIR KUTUYU DOLDURAN KAYNAĞIN AYNISI OLMALI.
        İlk hâli yalnız `program` tablosuna bakıyordu; oysa arayüzdeki
        bölüm kutuları `plan` tablosundan doluyor. İkisi AYNI DEĞİL:
        yayınlanan katalogda 127 program kodunun planı var ama `program`
        tablosunda 129 satır var ve **hiçbir yandal yok** — yani kutunun
        sunduğu `BHB_YD` seçilince doğrulama onu reddederdi.

        Aynı soruya iki kaynağın farklı cevap vermesi — bu projenin tekrar
        eden hata sınıfı. Kural: **kullanıcıya sunulan her seçenek geçerli
        sayılır.** Sunmadığımız bir kod (elle yazılan) hâlâ reddediliyor.

        ⚠️ Üç değerli: iki tabloda da hiç satır yoksa (katalog çekilmemiş)
        `None` — "bu kod yanlış" demek yanlış olurdu.
        """
        def _say(sql: str, *p) -> int | None:
            try:
                return self.con.execute(sql, p).fetchone()[0]
            except sqlite3.Error:
                return None

        toplam = (_say("SELECT COUNT(*) FROM plan WHERE program_code IS NOT NULL") or 0) \
            + (_say("SELECT COUNT(*) FROM program") or 0)
        if not toplam:
            return None
        return bool(_say("SELECT COUNT(*) FROM plan WHERE program_code=?", code)
                    or _say("SELECT COUNT(*) FROM program WHERE code=?", code))

    def _dogrula_program(self, code: str, rol: str) -> None:
        """Kod katalogda yoksa AÇIKÇA hata ver.

        ★ Temizleyip doğrulamamak, bu projedeki "sessiz sıfır" hatasının
        ta kendisiydi: bozuk kod dosyaya yazılıyor, plan aramaları boş
        dönüyor, ekran "ders yok" diyordu — sanki program gerçekten boşmuş
        gibi. Artık kaydın kendisi reddediliyor ve sebebi yazıyor.
        """
        if self._program_var(code) is not False:      # True veya "bakılamaz"
            return
        # Öneri de aynı iki kaynaktan: `ALGYD` yazana `ALG_YD`yi gösterebilmek
        # için plan tarafına da bakmak şart (yandalların çoğu orada).
        # ⚠️ Tablo yoksa öneri de yok — hata mesajı yine çıkıyor. Öneri
        # üretememek, hatayı hiç verememeye dönüşmemeli.
        yakin: set[str] = set()
        for sql in ("SELECT program_code FROM plan WHERE program_code LIKE ?",
                    "SELECT code FROM program WHERE code LIKE ?"):
            try:
                yakin |= {r[0] for r in self.con.execute(sql, (code[:3] + "%",))
                          if r[0]}
            except sqlite3.Error:
                continue
        yakin = sorted(yakin)[:4]
        ek = (" (benzer kodlar: " + ", ".join(yakin) + ")") if yakin else ""
        raise ValueError(f"{rol} programı katalogda yok: {code}{ek}")

    def refresh(self, skip_obs: bool = False) -> dict:
        """Veriyi tazeler ve ne değiştiğini döndürür.

        Eş zamanlı iki tazeleme başlatılmasın diye `busy` bayrağı var —
        kilit zaten seri hale getiriyor ama kullanıcı iki kez tıklarsa
        ikincisi 30 saniye bekleyip aynı işi tekrar yapardı.
        """
        if self.busy:
            raise ValueError("veri tazeleme işlemi devam etmektedir")
        if not can_refresh():
            # ★ Tarayıcıda (Pyodide) tarama yığını yok ve olamaz: OBS'ye
            # tarayıcıdan istek atmak zaten CORS'a takılır. Kullanıcıya
            # "ModuleNotFoundError" göstermek yerine ne yapması gerektiğini
            # söylüyoruz — ve arayüz düğmeyi hiç göstermiyor (bkz. canRefresh).
            raise ValueError(
                "veri tazeleme bu ortamda yapılamaz; katalog siteyle birlikte "
                "yayımlanır ve dönem başında güncellenir")
        self.busy = True
        try:
            from . import pipeline
            settings = self.settings()
            pipeline.step_ituhelper(self.con, settings, offline=False)
            obs_error = ""
            if not skip_obs:
                try:
                    pipeline.step_obs_plans(self.con, settings)
                    pipeline.step_dedupe_plans(self.con)
                except Exception as exc:                      # noqa: BLE001
                    # OBS erişilemiyorsa ESKİ VERİ KORUNUR; sessizce başarılı
                    # görünmek yanlış olurdu.
                    obs_error = str(exc)
            # ⚠️ Katalog değişti: dil eşi önbelleği düşüyor, yoksa
            # tazelemeden sonra eski eşler gösterilirdi.
            self._esler_onbellek = None
            declared_n = _apply_declared(self.ucon)
            pipeline.step_prereq(self.con)
            CH.take(self.con)
            diff = CH.compare(self.con, watch=self.watch_codes())
            return {"obsError": obs_error, "declared": declared_n,
                    "changes": _diff_json(diff)}
        finally:
            self.busy = False

    def suggestions(self) -> list[dict]:
        """Aday denklikler — ÖNERİ, uygulanmış değil."""
        from . import discover
        settings = self.settings()
        anadal_id, second_id = self.plan_ids()
        items = discover.suggest(self.con, self.ucon, self.student_id,
                                 [(anadal_id, "ANADAL"),
                                  (second_id, settings.second_role or "CAP")])
        return [{"source": i.source, "sourceName": i.source_name,
                 "sourceGrade": i.source_grade, "target": i.target,
                 "targetName": i.target_name, "role": i.plan_role,
                 "confidence": i.confidence, "reasons": i.reasons,
                 "sourceCredits": i.source_credits,
                 "targetCredits": i.target_credits} for i in items]

    def apply_equivalence(self, target: str, sources: list[str], note: str = "") -> int:
        """Denkliği `denklikler.toml`'a yazar ve hemen uygular.

        Dosyaya yazmak önemli: `make clean` ya da yeni bir tarama sonrası da
        kalsın, ve kullanıcı ne beyan ettiğini açıp görebilsin.
        """
        from .normalize import normalize_course_code
        target = normalize_course_code(target)
        clean = [normalize_course_code(x) for x in sources]
        clean = [c for c in clean if c]
        if not target or not clean:
            raise ValueError("denklik için hedef ve en az bir kaynak gerekir")
        declared.append(target, clean, note=note or "arayüzden onaylandı")
        return declared.apply(self.ucon)

    def applied_equivalences(self) -> list[dict]:
        """Uygulanmış BEYAN denklikleri — kaldırılabilsin diye listeleniyor."""
        out = []
        # ★★ Faz 28 — beyanlar KULLANICI DB'sinde (kişisel veri).
        for row in self.ucon.execute(
            """SELECT id, target_course, note_raw FROM equivalence
               WHERE confidence='user_declared' ORDER BY target_course"""
        ):
            sources = [r[0] for r in self.ucon.execute(
                "SELECT course_code FROM equivalence_source WHERE equivalence_id=?",
                (row["id"],))]
            out.append({"target": row["target_course"], "sources": sources,
                        "note": row["note_raw"] or ""})
        return out

    def remove_equivalence(self, target: str) -> int:
        from .normalize import normalize_course_code
        declared.remove(normalize_course_code(target))
        return declared.apply(self.ucon)

    def second_programs(self) -> dict:
        """{'cap': [{code,name}], 'yandal': [...]} — planı OLAN bölümler."""
        from .normalize import merge_language_variants

        out: dict[str, list] = {}
        for kind in ("cap", "yandal"):
            rows = {r[0]: r[1] for r in self.con.execute(
                """SELECT DISTINCT p.program_code, COALESCE(pr.name, p.program_code)
                   FROM plan p LEFT JOIN program pr ON pr.code = p.program_code
                   WHERE p.plan_type=? AND p.program_code IS NOT NULL
                     AND EXISTS (SELECT 1 FROM plan_slot s WHERE s.plan_id = p.id)""",
                (kind,))}
            out[kind] = [{"code": c, "name": rows.get(c, c)}
                         for c in merge_language_variants(rows)]
        return out

    def saved(self) -> dict:
        return S.load_picks(self.ucon, self.student_id, self.settings().term)

    def save_picks(self, picks: list[dict]) -> int:
        pairs = [(str(p.get("course", "")), str(p.get("crn", ""))) for p in picks]
        return S.save_picks(self.ucon, self.student_id, self.settings().term, pairs)

    def clear_picks(self) -> int:
        return S.clear_picks(self.ucon, self.student_id, self.settings().term)

    def watch_codes(self) -> set[str]:
        from .plans import watch_codes as _watch_codes
        return _watch_codes(self.con, self.ucon, self.settings())

    def changes(self) -> dict:
        return _diff_json(CH.compare(self.con, watch=self.watch_codes()))

    def restore_backup(self, name: str) -> int:
        return S.restore(self.ucon, self.student_id, str(name))

    # ------------------------------------------------------- CRN çözümleme
    # ★ Kullanıcı isteği 23.08.2026: "CRN ile program yükleme olursa iyi olur".
    # OBS'de kaydını yaptıktan sonra CRN'leri yapıştırıp GERÇEK programını
    # görebilmek için.
    #
    # ⚠️ Bu bir OKUMA ama yazma yolundan geçiyor. Sebep: iki taşıyıcı
    # (yerel sunucu + tarayıcıdaki Pyodide) yalnız `dispatch`i paylaşıyor;
    # ayrı bir okuma yolu açmak, web sürümünün onu KOPYALAMASI demek olurdu
    # ve iki kopya zamanla ayrışırdı (bkz. `_route` başlığı).
    def resolve_crns(self, crns) -> dict:
        """CRN listesini şubelere çevirir.

        Bulunamayanı SESSİZCE ATMIYORUZ: kullanıcı 8 CRN yapıştırıp 6 ders
        görürse hangi ikisinin düştüğünü bilmeli — yanlış derse kayıt olmuş
        sanmaktan iyidir.
        """
        temiz, gorulen = [], set()
        for raw in crns:
            kod = re.sub(r"\D", "", str(raw or ""))
            if kod and kod not in gorulen:
                gorulen.add(kod)
                temiz.append(kod)
        if not temiz:
            return {"found": [], "missing": []}
        marks = ",".join("?" * len(temiz))
        satirlar = {r["crn"]: r for r in self.con.execute(
            f"""SELECT l.crn, l.course_code, COALESCE(c.name,'') AS name,
                       COALESCE(c.credits,0) AS credits, COALESCE(c.ects,0) AS ects,
                       l.capacity, l.enrolled, l.instructor, l.teaching_method
                FROM lesson l LEFT JOIN course c ON c.code = l.course_code
                WHERE l.crn IN ({marks})""", temiz)}
        from .plans import anadal_plan as _anadal_plan
        from .plans import resolve_seconds as _resolve_seconds

        settings = self.settings()
        rol_of: dict[str, str] = {}
        for plan_id, rol in ((_anadal_plan(self.con, settings), "ANADAL"),
                             *((s["planId"], s["role"])
                               for s in _resolve_seconds(self.con, settings))):
            if plan_id:
                for kod in self._plan_codes(plan_id):
                    rol_of.setdefault(kod, rol)

        found = []
        for crn in temiz:
            row = satirlar.get(crn)
            if row is None:
                continue
            found.append({
                "crn": crn, "course": row["course_code"], "name": row["name"],
                "credits": float(row["credits"] or 0), "ects": float(row["ects"] or 0),
                "capacity": row["capacity"] or 0, "enrolled": row["enrolled"] or 0,
                # Şube seçerken bakılan iki şey: hoca ve saat (Faz 24/25).
                "instructor": UI._hoca(row["instructor"]),
                "online": REC.Section("", "", None, 0, 0, (),
                                      row["teaching_method"]).online,
                # ★ Planlarında OLMAYAN ders de gösteriliyor ('PLAN DIŞI').
                # Gizleseydik kullanıcı gerçek programını göremezdi; serbest
                # seçmeli ya da başka bir ders de kayıtta olabiliyor.
                "role": rol_of.get(row["course_code"], "PLAN_DISI"),
                # ★ Faz 93: derslik de; bina/derslik öneri motoruyla AYNI
                # temizlikten geçiyor (eskiden ham "undeclared" bina adı
                # diye gidiyordu).
                "meetings": [{**dict(m), "building": UI._building(m["building"]),
                              "room": UI._derslik(m["room"])}
                             for m in self.con.execute(
                    """SELECT lm.day_of_week AS day, lm.start_min AS start,
                              lm.end_min AS end, lm.building, lm.room, b.campus
                       FROM lesson_meeting lm
                       LEFT JOIN building b ON b.code = lm.building
                       WHERE lm.crn=? ORDER BY lm.day_of_week, lm.start_min""",
                    (crn,))],
            })
        return {"found": found,
                "missing": [c for c in temiz if c not in satirlar]}

    # ------------------------------------------------------ katalog araması
    # ★ Faz 25/B1 — PLAN DIŞI ders ekleme (24.08.2026).
    #
    # Araç bugüne kadar yalnız PLANINDAKİ dersleri ekletiyordu. Oysa normal
    # bir ders seçim aracının asıl işlerinden biri "şu dersi programıma
    # sığdırabilir miyim" sorusu; ders başka bölümün olabilir, serbest
    # seçmeli olabilir, sırf merak edilen bir ders olabilir.
    #
    # ⚠️ Buradaki tuzak projenin ana hata sınıfı: plan dışı bir dersi
    # "şu şartı karşıladı" saymak. `role='PLAN_DISI'` tam da bunu engelliyor —
    # kredisi yüke ve çakışmaya girer, hiçbir slotu DOLDURMAZ.
    KATALOG_LIMIT = 40

    def search_catalog(self, q: str) -> dict:
        """Açık şubesi olan dersler arasında kod/ad araması.

        İki dilde de arar: 'olasılık' yazan kişi 'MAT 271E — Probability'yi
        bulmalı (katalogda gerçekten var olan eş kod üzerinden).
        """
        q = (q or "").strip()
        if len(q) < 2:
            return {"items": [], "total": 0, "note": "en az iki harf yaz"}
        like = f"%{q.lower()}%"
        # Eş kodun adı da aransın: 'MAT 271E' için 'MAT 271'in adı.
        satirlar = self.con.execute(
            """SELECT c.code, COALESCE(c.name,'') AS name,
                      COALESCE(c.credits,0) AS credits, COALESCE(c.ects,0) AS ects,
                      COUNT(l.crn) AS subeler,
                      c.class_restriction AS kredi_kosulu,
                      COALESCE(es.name,'') AS alt_name
               FROM course c
               JOIN lesson l ON l.course_code = c.code
               LEFT JOIN course es ON es.code =
                    (CASE WHEN c.code LIKE '%E'
                          THEN substr(c.code, 1, length(c.code)-1)
                          ELSE c.code || 'E' END)
               WHERE lower(c.code) LIKE ?
                  OR lower(c.name) LIKE ?
                  OR lower(COALESCE(es.name,'')) LIKE ?
               GROUP BY c.code
               ORDER BY (lower(c.code) LIKE ?) DESC, c.code
               LIMIT ?""",
            (like, like, like, f"{q.lower()}%", self.KATALOG_LIMIT + 1)).fetchall()
        kesildi = len(satirlar) > self.KATALOG_LIMIT
        satirlar = satirlar[:self.KATALOG_LIMIT]
        # Hangi ders planında var? Rolü doğru yazabilmek için.
        from .plans import anadal_plan as _anadal_plan
        from .plans import resolve_seconds as _resolve_seconds

        settings = self.settings()
        rol_of: dict[str, str] = {}
        for plan_id, rol in ((_anadal_plan(self.con, settings), "ANADAL"),
                             *((s["planId"], s["role"])
                               for s in _resolve_seconds(self.con, settings))):
            if plan_id:
                for kod in self._plan_codes(plan_id):
                    rol_of.setdefault(kod, rol)
        # ★ Faz 37 — katalogda ilan edilmiş kredi tabanı arama sonucunda da
        # taşınıyor. Plan DIŞI ekleme kullanıcının açık kararı, o yüzden
        # ENGELLEMİYORUZ; ama tabanı tutmadığı bir dersi hiç uyarmadan
        # programa koymak, kayıt gününde öğrenilecek bir sürpriz olurdu.
        _katalog_kurali = POL.load_catalog_rule()
        return {
            "items": [{
                "course": r["code"], "name": r["name"], "altName": r["alt_name"],
                "credits": float(r["credits"] or 0), "ects": float(r["ects"] or 0),
                "sectionCount": r["subeler"],
                "role": rol_of.get(r["code"], "PLAN_DISI"),
                "creditFloor": (POL.parse_catalog_floor(r["kredi_kosulu"])
                                if _katalog_kurali.enabled else None),
            } for r in satirlar],
            # ⚠️ Kesme SESSİZ değil: "40 sonuç" ile "40+ sonuç" farklı şeyler.
            "truncated": kesildi,
        }

    def course_sections(self, course: str) -> dict:
        """Bir dersin şubeleri — plan dışı ders eklerken şube seçtirmek için.

        `resolve_crns` ile AYNI biçimde döner: arayüzün tek bir ekleme yolu
        var (`loadFromCrn`), iki ayrı biçim iki ayrı hata demek olurdu.
        """
        course = (course or "").strip().upper()
        crns = [r[0] for r in self.con.execute(
            "SELECT crn FROM lesson WHERE upper(course_code)=?", (course,))]
        return self.resolve_crns(crns)

    def _plan_codes(self, plan_id: int) -> set[str]:
        from . import rules as R

        return R.plan_codes(self.con, plan_id, pools=True)

    def save_max_load(self, value: float) -> float:
        """Dönem kredi tavanını değiştirir (yönetmeliğe uydurmak için)."""
        value = float(value)
        if not 1 <= value <= 60:
            raise ValueError("kredi tavanı 1–60 arasında olmalı")
        config.update_settings({"max_load": value})
        return value

    # ★ Faz 27 — tercihler. Doğrulama BURADA, çünkü arayüz tek giriş yolu
    # değil (statik sitede de aynı `dispatch` çağrılıyor).
    GUN_ADI = {1: "Pzt", 2: "Sal", 3: "Çar", 4: "Per", 5: "Cum"}

    def save_prefs(self, body: dict) -> dict:
        degerler = self._tercih_degerleri(body)
        config.update_settings(degerler)
        return degerler

    def preview_prefs(self, body: dict) -> dict:
        """Faz 59 — tercihi KAYDETMEDEN dene (fikirler §3.6).

        Tercih değiştirmenin bedelini görmek için pencereyi kaydedip ana
        ekrana bakmak gerekiyordu; "hangi tercih neye mal oluyor" sorusu
        deneme–yanılma ile cevaplanıyordu. Burada ayarların BELLEKTEKİ bir
        kopyası tercihlerle değiştirilip rapor aynı yoldan (`UI.collect`)
        kuruluyor; dosyaya hiçbir şey yazılmıyor. İstenen kipin 1. önerisi
        dönüyor — arayüz bugünkü önerisiyle karşılaştırıyor.
        ⚠️ Doğrulama kaydetmeyle AYNI (`_tercih_degerleri`): önizlemenin kabul
        edip kaydetmenin reddettiği bir tercih olmasın.
        """
        import dataclasses
        degerler = self._tercih_degerleri(body)
        settings = dataclasses.replace(self.settings(), **degerler)
        from .plans import anadal_plan as _anadal_plan
        from .plans import resolve_seconds as _resolve_seconds
        data = UI.collect(self.con, self.ucon, self.student_id, settings,
                          _anadal_plan(self.con, settings), None,
                          max_load=self.max_load, n_schedules=1,
                          seconds=_resolve_seconds(self.con, settings))
        kip = str(body.get("mode") or "")
        mod = next((m for m in data.get("modes") or [] if m.get("key") == kip),
                   (data.get("modes") or [{}])[0])
        return {"mode": mod.get("key"), "schedule": (mod.get("schedules") or [None])[0]}

    def _tercih_degerleri(self, body: dict) -> dict:
        erken = int(body.get("enErken") or 0)
        if not 0 <= erken <= 24 * 60:
            raise ValueError("saat 00:00–24:00 arasında olmalı")
        gunler = [int(g) for g in (body.get("bosGunler") or [])
                  if str(g).strip().lstrip("-").isdigit()]
        gunler = sorted({g for g in gunler if 1 <= g <= 5})
        # ⚠️ BEŞ günün beşini de boş istemek, hiçbir program üretilememesi
        # değil (tercih yumuşak) ama anlamsız bir istek: kullanıcıya
        # söylüyoruz, sessizce kabul edip sonucu bozmuyoruz.
        if len(gunler) >= 5:
            raise ValueError("beş günün tamamı boş olarak seçilemez")

        def adlar(anahtar: str) -> list[str]:
            return [s for s in (str(x).strip()
                                for x in (body.get(anahtar) or [])) if s][:10]

        degerler = {
            "tercih_en_erken": erken,
            "tercih_bos_gunler": gunler,
            "tercih_kampus_degisimi": bool(body.get("kampus")),
            "tercih_cevrimici": bool(body.get("cevrimici")),
            "tercih_istenen_hocalar": adlar("istenenHocalar"),
            "tercih_istenmeyen_hocalar": adlar("istenmeyenHocalar"),
        }
        return degerler

    def save_term(self, donem: int, cap_baslangic: int | None = None) -> int:
        donem = int(donem)
        if not 0 <= donem <= 16:
            raise ValueError("dönem 0–16 arasında olmalı")
        values: dict = {"donem": donem}
        if cap_baslangic is not None:
            cb = int(cap_baslangic)
            if not 0 <= cb <= 16:
                raise ValueError("ÇAP başlangıç yarıyılı 0–16 arasında olmalı")
            # ★ Arayüzden girilebilmesi şart: web sürümünde kullanıcının
            # düzenleyebileceği bir `settings.toml` yok. "Dosyaya yaz" demek,
            # web ziyaretçisine yapamayacağı bir şey söylemek olurdu.
            values["cap_baslangic_yariyili"] = cb
        config.update_settings(values)
        return donem

    def save_busy(self, day: int, start: int, end: int, label: str = "",
                  remove: str = "") -> dict:
        """Ders konulamayacak bir saat aralığı ekler ya da siler.

        ★ Silme, İNDEKSLE değil ham METİNLE yapılıyor. İndeks kullansaydık iki
        sekme açıkken listeler kayar ve kullanıcı yanlış aralığı silerdi.
        """
        from .normalize import format_busy, parse_busy

        settings = config.Settings.load()
        current = [str(x) for x in (settings.mesgul or [])]
        if remove:
            yeni = [x for x in current if x.strip() != remove.strip()]
            if len(yeni) == len(current):
                raise ValueError("belirtilen aralık bulunamadı")
            current = yeni
        else:
            day, start, end = int(day), int(start), int(end)
            if not 1 <= day <= 7:
                raise ValueError("gün 1–7 arasında olmalı")
            if not 0 <= start < end <= 24 * 60:
                raise ValueError("bitiş saati başlangıçtan sonra olmalı")
            metin = format_busy(day, start, end, label)
            if parse_busy(metin) is None:      # kendi ürettiğimizi doğrula
                raise ValueError("aralık okunamadı")
            if metin in current:
                raise ValueError("bu aralık zaten tanımlıdır")
            current = sorted({*current, metin})
        config.update_settings({"mesgul": current})
        return {"busyCount": len(current)}

    def toggle_watch(self, course: str) -> dict:
        """`make watch` izleme listesine ders ekler/çıkarır (yapılacaklar 4.3).

        ★ Liste BOŞ bırakılırsa nöbet planlarındaki bütün açık dersleri
        izliyor — 191 ders, her turda bir şey değişiyor, bildirim gürültüye
        dönüyor. O yüzden buradan eklenen ilk ders listeyi *daraltıyor*:
        boş liste "hepsi" demek, bir isim "yalnız bu" demek. Arayüz bu
        anlam değişikliğini söylemek zorunda, sessizce yapmamalı.
        """
        from .normalize import normalize_course_code

        code = normalize_course_code(course or "")
        if not code:
            raise ValueError("ders kodu gerekli")
        settings = config.Settings.load()
        current = [str(c).upper().strip() for c in (settings.watch_courses or [])]
        if code in current:
            current = [c for c in current if c != code]
        else:
            current = sorted({*current, code})
        config.update_settings({"watch_courses": current})
        return {"watching": current, "on": code in current}

    def toggle_lock(self, course: str, crn: str = "", *, aralik: str = "",
                    satir: str = "") -> dict:
        """Bir dersi BULUNDUĞU ŞUBEYE (dolayısıyla saate) kilitler/açar.

        ★★ Faz 53 — `aralik` verilirse (`"00:00-12:30"`) ders bir ŞUBEYE değil
        bir SAAT ARALIĞINA kilitlenir: "bu ders sabah olsun, şubesi fark
        etmez". Bir derste yine TEK kilit — şube kilidi ile aralık kilidi
        birbirinin yerine geçer ve düşen `replaced` ile söylenir.

        `satir`: ayar dosyasındaki bir satırı OLDUĞU GİBİ siler. Elle yazılıp
        okunamayan satır (ör. `"BLG 351E@8.30-12.30"`) arayüzde "okunamadı"
        diye görünüyor; ders kodu bile çözülemeyebildiği için (`"@123"`) onu
        kaldırmanın tek güvenilir yolu satırın kendisi.

        ★★ Faz 45 — kullanıcı isteği 17.09.2026: *"dersleri saate kitleme ve
        önerilerin onun etrafında şekillenmesi"*.

        Kilit `watch_courses`'tan farklı: o "bu ders programda olsun" der ve
        şubeyi motora bırakır — motor daha ucuz bir şube bulunca saati
        kaydırır. Kilit "bu dersi TAM BU SAATTE tut" der.

        ★ Bir ders için TEK kilit. Aynı derse ikinci bir CRN kilitlenirse
        eskisi düşer; iki şube birden tutmak zaten çelişki olurdu (ikisi de
        zorunlu → hiçbir program kurulamaz). Sessizce üst üste yazmak yerine
        eskisini AÇIKÇA değiştiriyoruz ve arayüze hangisinin düştüğünü
        döndürüyoruz.
        """
        from . import recommend as REC
        from .normalize import normalize_course_code

        settings = config.Settings.load()
        current = [str(x).strip() for x in (settings.kilitli or []) if str(x).strip()]
        if satir:
            # Olmayan satırı silmek hata değil (aynı satır iki kez yazılmışsa
            # ilk silişte ikisi de gidiyor; "hepsini aç" ikinciye gelince
            # durmasın). Dönen durum gerçeği gösteriyor.
            kalan = [x for x in current if x != satir.strip()]
            if len(kalan) != len(current):
                config.update_settings({"kilitli": kalan})
            return {"locked": kalan, "on": False, "course": "", "crn": ""}
        code = normalize_course_code(course or "")
        if not code:
            raise ValueError("ders kodu gerekli")
        crn = str(crn or "").strip()
        if aralik:
            # ⚠️ Okunamayan aralık YAZILMIYOR: ayara bozuk satır koymak, motorun
            # uygulamadığı bir kilidi "kilitli" diye göstermek olurdu.
            ab = REC.kilit_araligi(aralik)
            if not ab:
                raise ValueError(f"saat aralığı okunamadı: {aralik} "
                                 "(biçim SS:DD-SS:DD, ör. 08:30-12:30)")
            deger = REC.aralik_yazi(*ab)
        else:
            deger = crn
        # Aynı dersin eski kilidi — hem "aç" hem "şube değiştir" için gerek.
        # ⚠️ Faz 53: elle yazılmış dosyada aynı derse İKİ satır olabilir;
        # motor SONUNCUSUNU uyguluyor. "Geçerli kilit" o; açarken ya da
        # değiştirirken dersin BÜTÜN satırları gidiyor — yoksa silinen
        # satırın yerine gölgedeki eski satır sessizce geçerli olurdu.
        dersin = [x for x in current if x.split("@", 1)[0].strip().upper() == code]
        eski = dersin[-1] if dersin else ""
        eski_deger = eski.split("@", 1)[-1].strip() if eski else ""
        kalan = [x for x in current if x not in dersin]
        if not deger or (eski and eski_deger == deger):
            # Değer verilmediyse ya da zaten o kilit varsa → AÇ.
            config.update_settings({"kilitli": kalan})
            return {"locked": kalan, "on": False, "course": code,
                    "crn": eski_deger}
        # ⚠️ SIRA KORUNUYOR (Faz 45 sıralıyordu): aynı derse iki satır varsa
        # motor sonuncusunu uyguluyor; sıralamak, dokunulmayan bir dersin
        # geçerli kilidini sessizce değiştirebilirdi. Yeni kilit sona.
        yeni = list(dict.fromkeys([*kalan, f"{code}@{deger}"]))
        config.update_settings({"kilitli": yeni})
        return {"locked": yeni, "on": True, "course": code,
                "crn": "" if aralik else crn, "aralik": deger if aralik else "",
                # Arayüz "GEO 315E artık 13601 yerine 13602'ye kilitli" diyebilsin.
                "replaced": eski_deger}

    def _reenroll(self) -> None:
        """Program değişince öğrenci kaydını yeni planlara bağla.

        Eski kayıtlar silinmezse ilerleme paneli kapatılmış bir programı
        göstermeye devam ederdi."""
        from .plans import anadal_plan as _anadal_plan
        from .plans import resolve_seconds as _resolve_seconds

        settings = self.settings()
        self.ucon.execute("DELETE FROM student_enrollment WHERE student_id=?",
                          (self.student_id,))
        anadal_id = _anadal_plan(self.con, settings)
        if anadal_id:
            S.enroll(self.ucon, self.student_id, anadal_id, "ANADAL",
                     settings.anadal_program)
        # ★ ÇAP ve yandal AYNI ANDA: `enrollment` tablosu baştan beri rol
        # taşıyordu ve birden çok kayıt tutabiliyordu; tek kaydı yazan biz
        # kısıtlıyorduk.
        for s in _resolve_seconds(self.con, settings):
            if s["planId"] and s["role"]:
                S.enroll(self.ucon, self.student_id, s["planId"], s["role"],
                         s["program"])
        self.ucon.commit()


def _apply_declared(con) -> int:
    try:
        return declared.apply(con)
    except Exception:                                  # noqa: BLE001
        return 0


def _diff_json(diff: "CH.Diff") -> dict:
    return {"since": diff.since, "until": diff.until, "count": diff.count(),
            "opened": diff.opened, "newSections": diff.new_sections,
            "closed": diff.closed, "filled": diff.filled, "freed": diff.freed}


def _clean_code(value) -> str:
    """Program kodu: harf/rakam/alt çizgi, en fazla 16 karakter.

    ★★ ALT ÇİZGİ SİLİNİYORDU — HER YANDAL KODU BOZULUYORDU.
    Eski hâli `[^A-Za-z0-9]` siliyordu; oysa katalogdaki 205 program
    kodunun 78'i alt çizgi taşıyor ve BUNLARIN HEPSİ YANDAL:
    `ALG_YD`, `ARC_YD`, `MAT_YD_EC`… Kullanıcı kutudan "ALG_YD" seçiyor,
    dosyaya "ALGYD" yazılıyor, o kod hiçbir şeyle eşleşmiyordu —
    yandal planı SESSİZCE boş dönüyordu. Bu projede tekrar tekrar
    canımızı yakan "sessiz sıfır" hatasının tam örneği.

    8 karakterlik kesme de aynı şeyi yapıyordu: `MAT_YD_EC` 9 karakter.
    Katalogdaki en uzun kod 9; 16 rahat bir tavan.

    ⚠️ Bu işlev artık yalnız TEMİZLİYOR. Kodun gerçekten var olduğunu
    `_dogrula_program` denetliyor — temizleyip doğrulamamak, uydurma bir
    kodu geçerliymiş gibi kaydetmek demekti.
    """
    return re.sub(r"[^A-Za-z0-9_]", "", str(value or "")).upper()[:16]


# --------------------------------------------------------------------- HTTP
class Handler(BaseHTTPRequestHandler):
    state: State = None          # sunucu kurulurken atanıyor
    server_version = "itucap"
    sys_version = ""

    def log_message(self, fmt, *args):        # sessiz: istekler kişisel veri
        pass

    # ------------------------------------------------------------ yardımcı
    def _send(self, code: int, payload: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload)))
        # Kişisel veri: ara belleklenmesin, gömülmesin, referrer sızmasın.
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(payload)

    def _json(self, payload: dict, code: int = 200) -> None:
        self._send(code, json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _error(self, code: int, message: str) -> None:
        self._json({"error": message}, code)

    def _authorized(self) -> bool:
        """Yazma isteği bu sayfadan mı geliyor?

        Jeton her çalıştırmada yeniden üretiliyor ve yalnız sunulan sayfada
        var. Origin denetimi de ikinci kat: başka bir sitenin sekmesi
        127.0.0.1'e istek atsa bile jetonu bilmiyor."""
        if not secrets.compare_digest(
                self.headers.get("X-Itucap-Token", ""), self.state.token):
            return False
        origin = self.headers.get("Origin")
        if origin and urlparse(origin).hostname not in ("127.0.0.1", "localhost"):
            return False
        return True

    def _body(self) -> dict:
        """İstek gövdesi.

        ⚠️ Çok büyük gövdeyi OKUMADAN reddedersek istemci yazmayı bitiremiyor
        ve 400 yerine kırık bağlantı görüyor. O yüzden sert bir tavana kadar
        **boşaltıp** sonra reddediyoruz."""
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            raise ValueError("gövde boş")
        if length > HARD_BODY:
            raise ConnectionError("gövde okunamayacak kadar büyük")
        raw = self.rfile.read(length)
        if length > MAX_BODY:
            raise ValueError(f"gövde çok büyük ({length} bayt, sınır {MAX_BODY})")
        return json.loads(raw.decode("utf-8"))

    # ----------------------------------------------------------------- GET
    def do_GET(self) -> None:
        url = urlparse(self.path)
        query = parse_qs(url.query)
        try:
            if url.path in ("/", "/index.html"):
                with self.state.lock:
                    html = UI.render(self.state.snapshot())
                return self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")
            if url.path == "/api/state":
                with self.state.lock:
                    return self._json(self.state.snapshot())
            if url.path == "/api/courses":
                with self.state.lock:
                    return self._json({"results": self.state.search_courses(
                        (query.get("q") or [""])[0])})
            if url.path == "/api/health":
                return self._json({"ok": True})
        except Exception as exc:                       # noqa: BLE001
            return self._error(500, str(exc))
        self._error(404, "yok")

    # ---------------------------------------------------------------- POST
    def do_POST(self) -> None:
        if not self._authorized():
            return self._error(403, "oturum anahtarı geçersiz; lütfen sayfayı yenileyiniz")
        url = urlparse(self.path)
        try:
            body = self._body()
            with self.state.lock:
                # Yönlendirme State.dispatch'te — aynı sözleşmeyi tarayıcıdaki
                # Pyodide sürümü de kullanıyor (bkz. State._route).
                result = self.state.dispatch(url.path, body)
        except ValueError as exc:
            return self._error(400, str(exc))
        except Exception as exc:                       # noqa: BLE001
            return self._error(500, str(exc))
        if result is None:
            return self._error(404, "yok")
        self._json(result)


def build(state: State, host: str = "127.0.0.1", port: int = 8770) -> ThreadingHTTPServer:
    handler = type("BoundHandler", (Handler,), {"state": state})
    return ThreadingHTTPServer((host, port), handler)


def serve(port: int = 8770, label: str = "ben", n_schedules: int = 3,
          max_load: float | None = None, open_browser: bool = True) -> int:
    state = State(label=label, n_schedules=n_schedules, max_load=max_load)
    # ⚠️ 127.0.0.1 — ağdaki başka makine erişemesin. '0.0.0.0' YAPMA.
    # ★ Port doluysa (çoğu zaman kendi eski `make app`'in) sonrakini dene.
    # Traceback basıp çıkmak, kullanıcıya çözemeyeceği bir hata göstermekti.
    httpd = None
    for offset in range(10):
        try:
            httpd = build(state, "127.0.0.1", port + offset)
            break
        except OSError as exc:
            if exc.errno not in (48, 98, 10048):        # EADDRINUSE
                raise
            print(f"⚠️  {port + offset} portu dolu, {port + offset + 1} deneniyor…")
    if httpd is None:
        print(f"❌ {port}–{port + 9} portlarının hepsi dolu. "
              f"Çalışan bir `make app` var mı? "
              f"Başka port: make app ARGS=\"--port 9100\"", file=sys.stderr)
        return 1
    url = f"http://127.0.0.1:{httpd.server_address[1]}/"
    print(f"▶  {url}")
    print("   Program, dönem ve geçilen dersler artık sayfadan düzenlenebilir.")
    print("   ⚠️  Notlarını sunuyor. Portu dışarı açma, tünelleme, paylaşma.")
    print("   Durdurmak için Ctrl+C.")
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n⏹  durduruldu")
    finally:
        httpd.server_close()
    return 0
