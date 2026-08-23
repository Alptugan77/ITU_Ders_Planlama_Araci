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
from urllib.parse import parse_qs, urlparse

from . import changes as CH
from . import config, db, declared
from . import policy as POL
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

    # ------------------------------------------------------------- okuma
    def settings(self) -> config.Settings:
        return config.Settings.load()

    def plan_ids(self) -> tuple[int | None, int | None]:
        # ★ `pipeline` DEĞİL: o modül tarama bağımlılıklarını (httpx,
        # selectolax) içeri alıyor ve motoru tarayıcıda çalışamaz kılıyordu.
        from .plans import resolve_plans as _resolve_plans
        return _resolve_plans(self.con, self.settings())

    def snapshot(self) -> dict:
        settings = self.settings()
        anadal_id, second_id = self.plan_ids()
        data = UI.collect(self.con, self.ucon, self.student_id, settings,
                          anadal_id, second_id, max_load=self.max_load,
                          n_schedules=self.n_schedules)
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
            return {"saved": self.save_transcript(b.get("items") or [],
                                                  bool(b.get("replace")))}
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
        if path == "/api/maxload":
            self.save_max_load(b.get("maxLoad") or 0)
            return {}
        if path == "/api/donem":
            self.save_term(b.get("donem") or 0,
                           b.get("capBaslangic")
                           if b.get("capBaslangic") is not None else None)
            return {}
        if path == "/api/watch":
            return self.toggle_watch(str(b.get("course") or ""))
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
            "programCodes": sorted(settings.allowed_programs),
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
            "programs": [dict(r) for r in self.con.execute(
                """SELECT DISTINCT p.program_code AS code,
                          COALESCE(pr.name, p.program_code) AS name, p.plan_type
                   FROM plan p LEFT JOIN program pr ON pr.code = p.program_code
                   WHERE p.program_code IS NOT NULL
                   ORDER BY p.program_code""")],
            "plans": [dict(r) for r in self.con.execute(
                """SELECT id, program_code, plan_type, host_program_code,
                          title, source,
                          (SELECT COUNT(*) FROM plan_slot WHERE plan_id=plan.id) AS slots
                   FROM plan ORDER BY plan_type, program_code, id DESC""")],
            "transcript": self.transcript(),
            "checklist": self.plan_checklist(),
            "backups": S.backups(),
            "passFail": list(POL.PASS_FAIL_GRADES),
            # İzleme listesi (yapılacaklar 4.3). BOŞ liste "planındaki tüm
            # açık dersleri izle" demek — arayüz bu ayrımı yazmak zorunda.
            "watchCourses": [str(c).upper() for c in (settings.watch_courses or [])],
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
    def save_transcript(self, items: list[dict], replace: bool) -> int:
        """Formdan gelen kayıtlar. Kural `student.make_entry` — metin girişiyle
        AYNI yer, yoksa aynı girdi nereden girildiğine göre farklı sonuç
        verirdi."""
        entries = []
        for item in items:
            note = "--" if item.get("inProgress") else ""
            entry = S.make_entry(str(item.get("course", "")),
                                 item.get("grade"), note)
            if entry:
                entries.append(entry)
        self._backup(replace)
        S.add_entries(self.ucon, self.student_id, entries, replace=replace)
        return len(entries)

    def _backup(self, replace: bool) -> None:
        """Silici yazmadan önce yedek. Elle girilmiş transkript geri gelmez."""
        if replace:
            S.backup(self.ucon, self.student_id)
            S.prune_backups()

    def save_text(self, text: str, replace: bool) -> tuple[int, list[str]]:
        """Toplu yapıştırma — transkripti olduğu gibi yapıştırabilmek için."""
        entries, bad = S.parse_text(text or "")
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
        if kind not in config.SECOND_KINDS:
            raise ValueError("ikinci program türü geçersiz")
        values["second_kind"] = kind
        anadal = _clean_code(body.get("anadalProgram"))
        if not anadal:
            raise ValueError("anadal programı boş olamaz")
        values["anadal_program"] = anadal
        if body.get("anadalPlanId"):
            values["anadal_plan_id"] = int(body["anadalPlanId"])
        if kind != "yok":
            second = _clean_code(body.get("secondProgram"))
            if not second:
                raise ValueError("ikinci programın kodu boş olamaz")
            values[f"{kind}_program"] = second
            if body.get("secondPlanId"):
                values[f"{kind}_plan_id"] = int(body["secondPlanId"])
        codes = [_clean_code(c) for c in (body.get("programCodes") or [])]
        codes = [c for c in codes if c]
        if codes:
            values["program_codes"] = codes
        config.update_settings(values)
        self._reenroll()
        return values

    def refresh(self, skip_obs: bool = False) -> dict:
        """Veriyi tazeler ve ne değiştiğini döndürür.

        Eş zamanlı iki tazeleme başlatılmasın diye `busy` bayrağı var —
        kilit zaten seri hale getiriyor ama kullanıcı iki kez tıklarsa
        ikincisi 30 saniye bekleyip aynı işi tekrar yapardı.
        """
        if self.busy:
            raise ValueError("tazeleme zaten sürüyor")
        if not can_refresh():
            # ★ Tarayıcıda (Pyodide) tarama yığını yok ve olamaz: OBS'ye
            # tarayıcıdan istek atmak zaten CORS'a takılır. Kullanıcıya
            # "ModuleNotFoundError" göstermek yerine ne yapması gerektiğini
            # söylüyoruz — ve arayüz düğmeyi hiç göstermiyor (bkz. canRefresh).
            raise ValueError(
                "veri tazeleme bu ortamda yapılamıyor — katalog siteyle "
                "birlikte yayınlanıyor ve dönem başında güncelleniyor")
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
            declared_n = _apply_declared(self.con)
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
        return declared.apply(self.con)

    def applied_equivalences(self) -> list[dict]:
        """Uygulanmış BEYAN denklikleri — kaldırılabilsin diye listeleniyor."""
        out = []
        for row in self.con.execute(
            """SELECT id, target_course, note_raw FROM equivalence
               WHERE confidence='user_declared' ORDER BY target_course"""
        ):
            sources = [r[0] for r in self.con.execute(
                "SELECT course_code FROM equivalence_source WHERE equivalence_id=?",
                (row["id"],))]
            out.append({"target": row["target_course"], "sources": sources,
                        "note": row["note_raw"] or ""})
        return out

    def remove_equivalence(self, target: str) -> int:
        from .normalize import normalize_course_code
        declared.remove(normalize_course_code(target))
        return declared.apply(self.con)

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

    def save_max_load(self, value: float) -> float:
        """Dönem kredi tavanını değiştirir (yönetmeliğe uydurmak için)."""
        value = float(value)
        if not 1 <= value <= 60:
            raise ValueError("kredi tavanı 1–60 arasında olmalı")
        config.update_settings({"max_load": value})
        return value

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
                raise ValueError("böyle bir aralık yok")
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
                raise ValueError("bu aralık zaten var")
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

    def _reenroll(self) -> None:
        """Program değişince öğrenci kaydını yeni planlara bağla.

        Eski kayıtlar silinmezse ilerleme paneli kapatılmış bir programı
        göstermeye devam ederdi."""
        settings = self.settings()
        anadal_id, second_id = self.plan_ids()
        self.ucon.execute("DELETE FROM student_enrollment WHERE student_id=?",
                          (self.student_id,))
        if anadal_id:
            S.enroll(self.ucon, self.student_id, anadal_id, "ANADAL",
                     settings.anadal_program)
        if second_id and settings.second_role:
            S.enroll(self.ucon, self.student_id, second_id, settings.second_role,
                     settings.second_program)
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
    """Program kodu: yalnız harf/rakam, en fazla 8 karakter."""
    return re.sub(r"[^A-Za-z0-9]", "", str(value or "")).upper()[:8]


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
            return self._error(403, "jeton geçersiz — sayfayı yenile")
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
