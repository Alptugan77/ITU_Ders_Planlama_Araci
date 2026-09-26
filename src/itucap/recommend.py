"""FAZ 5 — Öneri motoru ve çakışmasız program üretici.

★ D5 SONRASI REVİZYON. Yol haritasının puanlaması `100 × dual_count` ile
başlıyordu; ölçtük, bu çiftte çift sayım SIFIR (docs/yol-haritasi-duzeltmeleri.md).
O terim ölü ağırlık. Yerine ÇAP'ın gerçek darboğazını koyuyoruz:

    kritik yol  — ÇAP'ın süresini belirleyen önşart zinciri üzerinde mi?
    unlock      — kaç dersi açıyor?
    kademe      — zincirin ne kadar başında?

ÇAP planı dönemsiz olduğu için (D2) "plandaki yarıyıl" diye bir sinyal yok;
sıralamayı tamamen önşart grafı belirliyor.

SERT KISITLAR (puanlanmaz, eler):
  * geçilmiş (denklikler dahil)
  * önşart sağlanmıyor   -> BİLİNMİYOR ise ELENMEZ, işaretlenir
  * bu dönem açılmamış
  * ★ program kısıtı: ÇAP dersi için ÇAP kodu, anadal dersi için anadal kodu
    `lesson_allowed_program` içinde olmalı. Ölçüm: BLG dersleri yalnız
    BLG/BLGE'ye açık — HTAE koduyla alınamıyor.
  * saat çakışması
"""
from __future__ import annotations

import re
import sqlite3
from itertools import islice
from dataclasses import dataclass, field
from typing import Iterable, Mapping

from . import istek as IST
from . import policy as POL
from . import prereq as P
from . import rules as R
from . import sequence as SEQ

DAY_NAMES = {1: "Pzt", 2: "Sal", 3: "Çar", 4: "Per", 5: "Cum", 6: "Cmt", 7: "Paz"}


# --------------------------------------------------------------------- veri
@dataclass(frozen=True)
class Meeting:
    day: int
    start: int
    end: int
    room: str | None
    building: str | None
    campus: str | None

    def label(self) -> str:
        return (f"{DAY_NAMES.get(self.day, '?')} "
                f"{self.start // 60:02d}:{self.start % 60:02d}-"
                f"{self.end // 60:02d}:{self.end % 60:02d}")


@dataclass
class Section:
    crn: str
    course: str
    instructor: str | None
    capacity: int
    enrolled: int
    meetings: tuple[Meeting, ...]
    # ★ Ders yöntemi (24.08.2026). OBS'de 3417 şubenin HEPSİNDE dolu, 139'u
    # "Virtual (Online)". Çevrimiçi şube KAMPÜS DEĞİŞTİRMİYOR — `campuses()`
    # bunu bilmeden kampüs değişimi sayıyordu.
    method: str | None = None

    @property
    def maske(self) -> int:
        """★★ Faz 91 — haftanın DAKİKA bit maskesi: gün başına 2048 bitlik blok,
        buluşma [başlangıç, bitiş) aralığındaki her dakika bir bit. İki şube
        ancak maskeleri ortak bit taşıyorsa çakışır — `overlaps` ile BİREBİR
        aynı koşul (aynı gün ve a.start < b.end and b.start < a.end), ama tek
        bir AND. Bir kez hesaplanıp saklanıyor (şube nesneleri değişmiyor)."""
        m = self.__dict__.get("_maske")
        if m is None:
            m = 0
            for t in self.meetings:
                if t.end > t.start:
                    m |= ((1 << (t.end - t.start)) - 1) << (t.day * 2048 + t.start)
            self.__dict__["_maske"] = m
        return m

    @property
    def online(self) -> bool:
        return "online" in (self.method or "").lower() \
            or "virtual" in (self.method or "").lower()

    @property
    def free(self) -> int:
        return max(0, (self.capacity or 0) - (self.enrolled or 0))

    @property
    def fill_ratio(self) -> float:
        return (self.enrolled or 0) / self.capacity if self.capacity else 1.0

    def campuses(self) -> set[str]:
        # ⚠️ Çevrimiçi ders bir kampüste DEĞİL. Bina kodu yazsa bile
        # (kayıtlı derslik) öğrenci oraya gitmiyor; kampüs değişimi
        # sayımına katmak var olmayan bir yolculuk uydurmak olurdu.
        if self.online:
            return set()
        return {m.campus for m in self.meetings if m.campus}


@dataclass
class Candidate:
    course: str
    name: str
    role: str                 # 'ANADAL' | 'CAP' | 'YANDAL'
    ects: float
    credits: float
    unlocks: int
    tier: int
    critical: bool            # ikinci programın kritik yolunda mı
    required: bool
    sections: list[Section]
    slot_id: int = 0          # dersin doldurduğu plan slotu (birincil)
    # ★★ Faz 81 — dersin uyabildiği BÜTÜN slotlar (birincisi `slot_id`).
    # Gerçek katalogda havuzdaki (plan, ders) çiftlerinin %38'i birden çok
    # yuvaya uyuyor (ENDE: "Functional-MT" dersleri 5–8. yarıyılın dört
    # yuvasına). Yalnız ilk yuva tutulunca motor bir dönemde o gruptan en çok
    # BİR ders önerebiliyordu — dört yuva boşken.
    slot_ids: tuple = ()
    plan_id: int = 0          # hangi planın slotu (ilerleme projeksiyonu için)
    term_no: int | None = None   # planın kaçıncı dönemi; dönemsiz planda None
    pool_label: str = ""      # ELECTIVE_POOL ise havuzun adı
    prereq_unknown: bool = False
    # ★★ Katalogda ÖNŞART METNİ YOK (ilk kullanıcı incelemesi D1).
    #
    # Ölçüm (24.08.2026): 10789 dersin yalnız 4628'inde (%42.9) önşart metni
    # var; açık şubesi olan 2019 dersin 858'inde (%42.5). Kalan %57 için
    # motor "önşartı yok, alabilirsin" diyordu — oysa doğrusu "BİLMİYORUZ".
    #
    # ⚠️ `prereq_unknown` bundan FARKLI: o, metin VAR ama ayrıştıramadık
    # demek. İkisini karıştırmak, iki ayrı veri sorununu tek etikete
    # sıkıştırıp hangisini düzelteceğimizi gizlerdi.
    prereq_missing: bool = False
    score: float = 0.0
    reasons: list[str] = field(default_factory=list)
    # ★ Puanın kırılımı (Faz 27): [{"key","points","label"}]. Gerekçe METNİ
    # vardı ama ağırlığın büyüklüğü görünmüyordu — "119 dersin önşartı" 30
    # puan mı 3 puan mı kattı, belli değildi.
    parts: list[dict] = field(default_factory=list)
    unit: str = "kredi"       # yük hangi birimden sayılıyor

    @property
    def load(self) -> float:
        """Dönem yükü — İTÜ kredisi (varsayılan) ya da AKTS."""
        return self.credits if self.unit == "kredi" else self.ects

    @property
    def yuvalar(self) -> tuple:
        """Doldurabileceği slotlar; eski tek-slot adaylar için `slot_id`."""
        return self.slot_ids or ((self.slot_id,) if self.slot_id else ())


def yuva_ata(adaylar) -> dict | None:
    """Faz 81 — her adayı AYRI bir slota yerleştir (iki taraflı eşleştirme,
    Kuhn). `{aday indeksi: slot}`; olmuyorsa `None`. Slotu olmayan aday
    (plan dışı) serbest. Aynı dersin iki dili (EEF 110 / EEF 110E) tek slota
    bağlı olduğundan ikisi birlikte eşleşmiyor — eski kural korunuyor."""
    sahip: dict = {}                              # slot -> aday indeksi

    def dene(i, gorulen):
        for s in adaylar[i].yuvalar:
            if s in gorulen:
                continue
            gorulen.add(s)
            if s not in sahip or dene(sahip[s], gorulen):
                sahip[s] = i
                return True
        return False

    for i, a in enumerate(adaylar):
        if a.yuvalar and not dene(i, set()):
            return None
    return {i: s for s, i in sahip.items()}


def yuva_ekle(eslesme: dict, aday) -> dict | None:
    """★★ Faz 91 — `eslesme` (slot → aday) seçilenlerin HEPSİNİ eşliyorsa,
    `aday`ı tek bir artırma yoluyla ekler; yeni eşleştirmeyi döndürür (girdi
    değişmez) ya da olmuyorsa `None`. Berge: cevap `yuva_ata(seçilenler +
    [aday]) is not None` ile AYNI, ama baştan eşleştirme yerine tek DFS."""
    yeni = dict(eslesme)

    def dene(c, gorulen: set) -> bool:
        for y in c.yuvalar:
            if y in gorulen:
                continue
            gorulen.add(y)
            sahip = yeni.get(y)
            if sahip is None or dene(sahip, gorulen):
                yeni[y] = c
                return True
        return False

    return yeni if dene(aday, set()) else None


# ------------------------------------------------------------------ yardımcı
def overlaps(a: Meeting, b: Meeting) -> bool:
    return a.day == b.day and a.start < b.end and b.start < a.end


def section_conflict(x: Section, y: Section) -> bool:
    # ★★ Faz 91 — dakika maskesiyle (bkz. Section.maske); eşdeğeri:
    # any(overlaps(m, n) for m in x.meetings for n in y.meetings)
    return bool(x.maske & y.maske)


# ★★ FAZ 91 — ŞUBELER İSTEK BOYUNCA BİR KEZ OKUNUR (bkz. `istek`).
# Bir sayfa durumunda `load_sections` 1031 kez çağrılıyordu ama yalnız 191
# FARKLI (ders, izinli programlar) için — anlık görüntünün %34'ü. Çağırana
# her seferinde listenin KOPYASI veriliyor (şube nesneleri değiştirilmiyor).
sube_onbellegi = IST.istek


def load_sections(con: sqlite3.Connection, course: str,
                  allowed_programs: set[str]) -> list[Section]:
    """Dersin, öğrencinin PROGRAM KODUYLA alabileceği şubeleri."""
    return list(IST.bellek(("sube", id(con), course, frozenset(allowed_programs)),
                           lambda: _load_sections(con, course, allowed_programs)))


def _load_sections(con: sqlite3.Connection, course: str,
                   allowed_programs: set[str]) -> list[Section]:
    out: list[Section] = []
    # ★ Faz 94: katalogda yerleşkesi boş binanın beyanı (katalog değeri önce).
    from . import declared as DEC
    kampus = DEC.load_campus_overrides()
    for row in con.execute(
        """SELECT crn, instructor, capacity, enrolled, teaching_method
           FROM lesson WHERE course_code=?""",
        (course,),
    ):
        progs = {r[0] for r in con.execute(
            "SELECT program_code FROM lesson_allowed_program WHERE crn=?", (row[0],))}
        if progs and not (progs & allowed_programs):
            continue                       # bu şube senin programına kapalı
        meetings = tuple(
            Meeting(m[0], m[1], m[2], m[3], m[4], m[5] or kampus.get(m[4] or ""))
            for m in con.execute(
                """SELECT lm.day_of_week, lm.start_min, lm.end_min, lm.room,
                          lm.building, b.campus
                   FROM lesson_meeting lm
                   LEFT JOIN building b ON b.code = lm.building
                   WHERE lm.crn=? ORDER BY lm.day_of_week, lm.start_min""", (row[0],))
        )
        out.append(Section(row[0], course, row[1], row[2] or 0, row[3] or 0,
                           meetings, row[4]))
    return out


def critical_courses(steps: list[SEQ.Step]) -> set[str]:
    """ÇAP'ın süresini belirleyen zincir: en derin dersten geriye yürü."""
    by_code = {s.course: s for s in steps}
    if not steps:
        return set()
    max_tier = max(s.tier for s in steps)
    frontier = [s.course for s in steps if s.tier == max_tier]
    critical: set[str] = set()
    while frontier:
        code = frontier.pop()
        if code in critical or code not in by_code:
            continue
        critical.add(code)
        frontier.extend(by_code[code].blockers)
    return critical


# ------------------------------------------------------------------ adaylar
def candidates(con: sqlite3.Connection, ucon: sqlite3.Connection, student_id: int,
               anadal_plan_id: int | None, cap_plan_id: int | None,
               anadal_program: str, cap_program: str,
               allowed_programs: Iterable[str] = (), unit: str = "kredi",
               second_role: str = "CAP", max_term: int | None = None,
               credit_rules: list[POL.CreditRule] | None = None,
               second_plans: list[tuple[str, int]] | None = None,
               ) -> list[Candidate]:
    """Bu dönem alınabilecek dersler.

    `max_term` verilirse **dönemlik + alttan** kipi: anadal planından yalnız
    `term_no <= max_term` olan slotlar alınır. Dönemsiz planların (ÇAP/yandal)
    slotlarında `term_no` yok — onlar her kipte kalır, çünkü elenecekleri bir
    dönem bilgisi yok.
    """
    from . import student as S

    grades = S.grades(ucon, student_id)
    taking = S.in_progress(ucon, student_id)   # ★ bu dönem aldıkların
    equivalences = R.load_equivalences(con, ucon=ucon)
    expanded, _via = R.expand_with_equivalences(grades, equivalences)
    prereq_grades = R.prereq_view(expanded)   # muafiyetler yalnız önşartta
    trees = P.parsed_trees(con)
    unlocks = P.unlock_counts(trees)
    unparsed = {r[0] for r in con.execute("SELECT course_code FROM prereq_unparsed")}

    # ★ Kredi eşiği (bitirme çalışması). Muafiyet krediye SAYILMAZ: gerçek notlar.
    rules = POL.load_rules() if credit_rules is None else credit_rules
    # ★ Faz 37 — katalogda ders ders ilan edilmiş taban. Bir kez okunuyor:
    # aday başına dosya açmak, harf başına arama yapan uçta pahalıya gelirdi.
    catalog_rule = POL.load_catalog_rule()
    have_credits = POL.earned_credits(con, grades)

    # ★ ÇAP ve yandal AYNI ANDA (23.08.2026). `second_plans` verilirse
    # [(rol, plan_id), …] olarak birden çok ikinci program gelir; verilmezse
    # eski tekil davranış sürer.
    ikinciler = (second_plans if second_plans is not None
                 else ([(second_role, cap_plan_id)] if cap_plan_id and second_role else []))

    # Kritik yol ve kademe HER ikinci programdan toplanıyor. Yalnız birine
    # baksaydık öbür programın zincir başı dersleri "kritik değil" görünür,
    # öneri sıralaması onları geri atardı.
    cap_steps = []
    for _rol, pid in ikinciler:
        cap_steps += SEQ.plan_sequence(con, pid, grades)
    critical = critical_courses([s for s in cap_steps if s.status != "DONE"])
    tier_of: dict[str, int] = {}
    for s in cap_steps:                     # aynı ders iki planda ise EN DERİN kademe
        tier_of[s.course] = max(tier_of.get(s.course, 0), s.tier)

    out: list[Candidate] = []
    # ★ Öğrenci hangi program kodlarıyla kayıt yapabiliyorsa o kodlar geçerli
    # (HTAE + BLG + BLGE). Kardeş kod OTOMATİK türetilmez — 'HTA' ile 'HTAE'yi
    # eşitlemek İngilizce programdaki öğrenciye Türkçe şube açardı.
    allowed = {c.upper() for c in allowed_programs} or {anadal_program, cap_program}
    for plan_id, role in ((anadal_plan_id, "ANADAL"), *((p, r) for r, p in ikinciler)):
        if plan_id is None or not role:
            continue
        for slot in con.execute(
            """SELECT ps.id, ps.slot_kind, ps.course_code, ps.alt_course_codes, ps.term_no,
                      COALESCE(ps.ects, c.ects)       AS ects,
                      COALESCE(ps.credits, c.credits) AS credits,
                      ps.pool_label_raw
               FROM plan_slot ps LEFT JOIN course c ON c.code = ps.course_code
               WHERE ps.plan_id=?""", (plan_id,)
        ):
            # dönemlik + alttan: bu dönemden İLERİDEKİ dersler elenir
            if (max_term is not None and slot["term_no"] is not None
                    and slot["term_no"] > max_term):
                continue
            if R.slot_satisfied(con, slot["id"], grades, equivalences).satisfied:
                continue
            # ★ Zorunlu slot iki kod taşıyabiliyor (EEF 110 / EEF 110E — aynı
            # dersin iki dili). İkisinin de şubesi önerilebilmeli; yalnız ilkini
            # denemek, o dönem sadece İngilizce şube açıldıysa dersi hiç
            # göstermezdi.
            # ★★ Faz 92 — ÇAP/yandal slotunda Türkçe kodun katalogdaki
            # İNGİLİZCE EŞİ de (tersi değil; bkz. rules.ingilizce_esi). OBS'nin
            # ÇAP planları çoğunlukla Türkçe kod yazıyor ("BLG_EHB": EEF 262)
            # ama o dönem yalnız İngilizce şube (EEF 262E, EHB_LS'ye açık)
            # açılmış olabiliyor. ÇAP planı bölüme tanımlı, dile değil (bkz.
            # normalize.base_program_code); eşi göstermemek, ÇAP öğrencisine
            # alabileceği dersi "açılmamış" diye saklamaktı. Anadal slotuna
            # DOKUNULMUYOR: İngilizce programdaki öğrenciye Türkçe şube
            # önermek ayrı bir karar (dil şartı).
            codes = (R.slot_codes(slot, con if role != "ANADAL" else None)
                     if slot["slot_kind"] == "REQUIRED"
                     else [r[0] for r in con.execute(
                         "SELECT course_code FROM pool_option WHERE slot_id=?", (slot["id"],))])
            pool_label = "" if slot["slot_kind"] == "REQUIRED" else (slot["pool_label_raw"] or "")
            for code in filter(None, codes):
                if R.passed(expanded.get(code)):
                    continue
                if code in taking:
                    continue          # ★ zaten bu dönem alıyorsun, tekrar önerme
                tree = trees.get(code)
                verdict = R.can_take_tree(tree, prereq_grades)
                unknown = code in unparsed
                if verdict.status is R.Status.BLOCKED and not unknown:
                    continue
                info = con.execute(
                    "SELECT name, ects, credits, prereq_raw, class_restriction "
                    "FROM course WHERE code=?", (code,)).fetchone()
                # ⚠️ Ders ADI kredi eşiğine GİRİYOR (inceleme D1): kural
                # kod kalıbıyla bitirme derslerinin 97'sinden yalnız 9'unu
                # tanıyordu. Bu yüzden `info` sorgusu kontrolden ÖNCE.
                # ★ Faz 37: katalogda ilan edilmiş taban da aynı sorgudan
                # geliyor — ayrı bir SELECT aday başına ikinci bir tur olurdu.
                if not POL.check(code, have_credits, rules,
                                 (info["name"] if info else "") or "",
                                 (info["class_restriction"] if info else None),
                                 catalog_rule):
                    continue                      # kredi eşiği — bitirme çalışması
                sections = load_sections(con, code, allowed)
                if not sections:
                    continue
                out.append(Candidate(
                    course=code,
                    name=(info["name"] if info else "") or "",
                    role=role,
                    ects=float(slot["ects"] or (info["ects"] if info else 0) or 0),
                    credits=float(slot["credits"] or (info["credits"] if info else 0) or 0),
                    unlocks=unlocks.get(code, 0),
                    tier=tier_of.get(code, 0),
                    critical=code in critical,
                    required=slot["slot_kind"] == "REQUIRED",
                    sections=sections,
                    prereq_unknown=unknown,
                    prereq_missing=not (info and str(info["prereq_raw"] or "").strip()),
                    slot_id=slot["id"],
                    plan_id=plan_id,
                    term_no=slot["term_no"],
                    pool_label=pool_label,
                    unit=unit,
                ))
    # aynı ders iki slottan gelmişse teki kalsın (ikinci program öncelikli)
    unique: dict[str, Candidate] = {}
    yuvalari: dict[str, list] = {}
    for cand in out:
        yuvalari.setdefault(cand.course, []).append(cand.slot_id)
        if cand.course not in unique or cand.role != "ANADAL":
            unique[cand.course] = cand
    # ★ Faz 81 — ama uyduğu BÜTÜN slotlar tutuluyor; birincil ilk sırada.
    for kod, cand in unique.items():
        cand.slot_ids = tuple(dict.fromkeys([cand.slot_id, *yuvalari[kod]]))
    return score_all(list(unique.values()))


# ----------------------------------------------------------------- puanlama
WEIGHTS = {
    "critical": 100,     # ÇAP'ın süresini belirleyen zincirde
    "cap_role": 50,      # ★ ÇAP dersi — ARZI KISITLI, aşağıya bak
    "required": 40,
    "unlock": 30,
    "early_tier": 25,
    "scarcity": 15,
    "deferrable": -20,   # ★ her dönem açılan ders ertelenebilir
    "full": -5,          # ★★ Faz 90 — bütün şubeleri dolu (aşağıya bak)
}
# ★ Ağırlık gerekçeleri (ölçüme dayalı, 20.08.2026):
#
#   cap_role 50 — ÇAP derslerinin arzı kısıtlı: 14 kalan dersten yalnız 2–3'ü
#     bir dönemde alınabiliyor (bkz. cap_blockers). Kaçırılan fırsat ÇAP'ı bir
#     dönem uzatıyor. Önceki 20'lik ağırlıkta `BLG 351E` (2 kredi, ÇAP), 0 kredili
#     `ATA 122` tarafından programdan dışlanıyordu.
#
#   deferrable -20 — 10'dan fazla şubesi olan ders (ATA 121: 28 şube, TUR 121: 37)
#     fiilen her dönem açılıyor; bu dönem alınmazsa bir şey kaybedilmiyor. Bu,
#     "tek şube / kontenjan kritik" bonusunun aynadaki karşılığı.
DEFERRABLE_SECTIONS = 10

# ★★ Faz 94 — sıkışık yerleşke geçişi (bkz. `Schedule.sikisik_gecisler`).
# Ceza ders puanlarıyla (40–100) aynı ölçekte: aynı dersleri geçişsiz veren
# program öne geçer, ama değerli bir ders bunun için programdan düşmez.
# Sert kısıt DEĞİL — başka yol yoksa program yine önerilir, arayüz uyarır.
YERLESKE_ESIK_DK = 60
SIKISIK_GECIS_CEZASI = 30.0

# ★★ FAZ 90 — KONTENJAN, GERÇEK HALİYLE (ölçüm 25.09.2026, gerçek katalog).
#
# "Kontenjan kritik" bonusu ilk sürümden beri dersin EN DOLU şubesine
# bakıyordu (`max(fill_ratio)`). İki sonucu vardı:
#   * 70 boş yeri olan BLG 351E "kritik" sayılıyordu (şubelerinden biri
#     doluydu). Yedi profilde adayların %70–100'ü bonusu alıyordu — bonus
#     artık hiçbir şeyi ayırt etmiyordu.
#   * Bütün şubeleri DOLU ders de bonus alıyordu; kapanmış bir ders "hemen
#     al" diye öne çıkıyordu. BLGE 5. yarıyılda "TM Elective I" havuzunda
#     dolu BLG 345E ile 4 boş yerli BLG 368E aynı puanı alıyor, eşitliği
#     ALFABE bozuyordu → öneri 1 dolu seçmeli içeriyordu.
# Şimdi:
#   * "kritik" = bütün şubelerin kontenjanı BİLİNİYOR ve açık şubelerin EN
#     BOŞU bile %85'ten dolu (gerçekten "yer kalmıyor").
#   * "dolu"   = bütün şubelerin kontenjanı biliniyor ve hiçbirinde yer yok →
#     küçük bir ceza (-5): aynı havuzdaki açık ders öne geçer; alternatif
#     yoksa ders yine önerilir ve arayüz "kontenjan izlenmeli" der.
#   * Kontenjanı ilan edilmemiş şube varsa "bilinmiyor": ne bonus ne ceza —
#     bilinmeyen, bilinen gibi gösterilmez.
KRITIK_DOLULUK = 0.85
# Şube seçiminde dolu şubenin maliyeti (puan cinsinden, `blocking_cost` ile
# aynı ölçek): boş şube, dolu şubeden en fazla bu kadar daha çok değer
# yakıyorsa boş şube seçilir. Ölçüm: 14 profil×kipin 11'inde önerinin bir
# dersi, aynı dersin AÇIK şubesi varken dolu şubeye yerleştiriliyordu.
DOLU_SUBE_MALIYETI = 15.0


def kontenjan_durumu(sections) -> str:
    """'dolu' | 'kritik' | 'acik' | 'bilinmiyor' (Faz 90)."""
    if not sections or any(not s.capacity for s in sections):
        return "bilinmiyor"
    acik = [s for s in sections if s.free > 0]
    if not acik:
        return "dolu"
    return "kritik" if min(s.fill_ratio for s in acik) > KRITIK_DOLULUK else "acik"


# ---------------------------------------------------------------- tercihler
@dataclass
class Preferences:
    """Kullanıcının YUMUŞAK tercihleri (Faz 27, yapılacaklar §2.2).

    ★★ Bunlar SERT KISIT DEĞİL, sıralama ağırlığı.

    Sebebi ölçülmüş bir davranış: gerçek veride 14 ÇAP dersinden yalnız 2–3'ü
    bir dönemde alınabiliyor. "Sabah dersi istemiyorum"u sert kısıt yapmak,
    kayıt edilebilir tek programı imkânsız gösterebilirdi. Tercih, iki
    ÇALIŞAN program arasında seçim yaptırır; çalışan tek programı elemez.

    ⚠️ Aynı sebeple ağırlıklar `WEIGHTS` düzeyinde küçük tutuluyor: bir
    tercih, ÇAP dersini ya da kritik yolu asla ezmemeli.
    """
    # Bu saatten önce başlayan ders istenmiyor (dakika; 0 = önemsiz).
    en_erken: int = 0
    # Boş kalması istenen günler (1=Pzt … 5=Cum).
    bos_gunler: tuple[int, ...] = ()
    kampus_degisimi_istemiyorum: bool = False
    cevrimici_tercih: bool = False
    # İstenen / istenmeyen öğretim üyeleri (küçük harfe indirilmiş parçalar).
    istenen_hocalar: tuple[str, ...] = ()
    istenmeyen_hocalar: tuple[str, ...] = ()

    @property
    def var_mi(self) -> bool:
        return bool(self.en_erken or self.bos_gunler
                    or self.kampus_degisimi_istemiyorum or self.cevrimici_tercih
                    or self.istenen_hocalar or self.istenmeyen_hocalar)


# Tercih ağırlıkları — WEIGHTS'in en küçüğünün (scarcity 15) altında kalıyor:
# bir tercih, kritik yolu (100) ya da ÇAP dersini (50) asla ezemesin.
TERCIH_AGIRLIK = {
    "erken": -6,        # istenmeyen saatteki HER ders için
    "bos_gun": -10,     # boş istenen güne düşen HER ders için
    "kampus": -5,       # her kampüs değişimi için
    "online": 3,        # çevrimiçi HER şube için
    "hoca_istenen": 8,
    "hoca_istenmeyen": -12,
}


def _hoca_eslesir(ad: str | None, parcalar: Iterable[str]) -> bool:
    """Ad parçası eşleşmesi — 'buzluca' ile 'Feza Buzluca' tutar.

    ⚠️ Boş parça HER ADI eşleştirirdi; süzülüyor.
    """
    temiz = (ad or "").casefold()
    if not temiz:
        return False
    return any(p for p in parcalar if p and p.casefold() in temiz)


def sube_tercih_puani(sec: "Section", tercih: Preferences | None) -> float:
    """TEK bir şubenin tercih puanı — şube SEÇİMİNDE kullanılıyor.

    ★★ Faz 27'nin asıl işi burada. Programı bütün olarak puanlamak yetmiyor:
    motor zaten çakışmasız programı buluyor ve aynı dersin sabah şubesiyle
    öğleden sonra şubesi arasında tercihe bakmadan seçim yapıyordu. Ölçüldü:
    "sabah istemiyorum" yalnız program puanına girdiğinde üç önerinin üçü de
    aynı sabah şubesini içeriyordu — yani tercih hiçbir şeyi değiştirmiyordu.

    ⚠️ Yine YUMUŞAK: `blocking_cost` (ileriye bakış) daha ağır basıyor.
    Tercih, iki eşdeğer şube arasında ayırt edici; değerli bir dersi
    programdan düşürecek kadar güçlü değil.
    """
    if tercih is None or not tercih.var_mi:
        return 0.0
    puan = 0.0
    if sec.online and tercih.cevrimici_tercih:
        puan += TERCIH_AGIRLIK["online"]
    if _hoca_eslesir(sec.instructor, tercih.istenen_hocalar):
        puan += TERCIH_AGIRLIK["hoca_istenen"]
    if _hoca_eslesir(sec.instructor, tercih.istenmeyen_hocalar):
        puan += TERCIH_AGIRLIK["hoca_istenmeyen"]
    for m in sec.meetings:
        if tercih.en_erken and m.start < tercih.en_erken:
            puan += TERCIH_AGIRLIK["erken"]
        if m.day in tercih.bos_gunler:
            puan += TERCIH_AGIRLIK["bos_gun"]
    return puan


def _tercih_sayaclari(picks: Iterable["Pick"],
                      tercih: Preferences) -> dict[str, int]:
    """Tercih başına kaç ihlal/uyum var. Sayım TEK YERDE.

    ★ Faz 37: puan ve "neyi bırakırsan olur" analizi aynı sayıları kullanmak
    zorunda. İkisi ayrı sayarsa arayüz "Cuma boşalıyor" der ama puan
    değişmez — kullanıcı hangisine inanacağını bilemez.
    """
    say = {"erken": 0, "bos_gun": 0, "online": 0,
           "hoca_istenen": 0, "hoca_istenmeyen": 0}
    for p in picks:
        sec = p.section
        if sec.online:
            say["online"] += 1
        if _hoca_eslesir(sec.instructor, tercih.istenen_hocalar):
            say["hoca_istenen"] += 1
        if _hoca_eslesir(sec.instructor, tercih.istenmeyen_hocalar):
            say["hoca_istenmeyen"] += 1
        for m in sec.meetings:
            if tercih.en_erken and m.start < tercih.en_erken:
                say["erken"] += 1
            if m.day in tercih.bos_gunler:
                say["bos_gun"] += 1
    return say


def tercih_puani(picks: Iterable["Pick"], tercih: Preferences | None,
                 kampus_degisimi: int = 0) -> tuple[float, list[str]]:
    """Bir programın tercihlere göre puan farkı ve gerekçeleri.

    Ayrı bir fonksiyon: hem `Schedule.score` hem arayüz aynı sayıyı
    göstermeli. İki yerde ayrı hesaplamak, "puan 22.5 ama neden" sorusunu
    cevaplanamaz hale getirirdi.
    """
    if tercih is None or not tercih.var_mi:
        return 0.0, []
    puan = 0.0
    sebep: list[str] = []
    _s = _tercih_sayaclari(picks, tercih)
    erken, bos = _s["erken"], _s["bos_gun"]
    online = _s["online"]
    istenen, istenmeyen = _s["hoca_istenen"], _s["hoca_istenmeyen"]
    if erken:
        puan += TERCIH_AGIRLIK["erken"] * erken
        sebep.append(f"{erken} ders tercih edilen saatten erken başlıyor")
    if bos:
        puan += TERCIH_AGIRLIK["bos_gun"] * bos
        sebep.append(f"{bos} ders boş kalması istenen güne denk geliyor")
    if tercih.kampus_degisimi_istemiyorum and kampus_degisimi:
        puan += TERCIH_AGIRLIK["kampus"] * kampus_degisimi
        sebep.append(f"{kampus_degisimi} kampüs değişimi")
    if tercih.cevrimici_tercih and online:
        puan += TERCIH_AGIRLIK["online"] * online
        sebep.append(f"{online} çevrimiçi şube")
    if istenen:
        puan += TERCIH_AGIRLIK["hoca_istenen"] * istenen
        sebep.append(f"{istenen} derste tercih edilen öğretim üyesi")
    if istenmeyen:
        puan += TERCIH_AGIRLIK["hoca_istenmeyen"] * istenmeyen
        sebep.append(f"{istenmeyen} derste tercih edilmeyen öğretim üyesi")
    return round(puan, 1), sebep


def score_all(cands: list[Candidate]) -> list[Candidate]:
    """Adayları puanla ve puanın NEREDEN geldiğini kaydet.

    ★ Faz 27 — `parts` eklendi (yapılacaklar §3.1). Eskiden yalnız gerekçe
    METNİ vardı: "119 dersin önşartı" yazıyordu ama bunun puana 30 mu 3 mü
    kattığı görünmüyordu. Sıralamaya güvenmek için ağırlığın büyüklüğünü
    görmek gerekiyor — özellikle "neden bu ders önde" sorusunda.
    """
    max_unlock = max((c.unlocks for c in cands), default=1) or 1
    max_tier = max((c.tier for c in cands), default=0)
    for c in cands:
        score = 0.0
        c.reasons = []
        c.parts = []

        def kat(anahtar: str, deger: float, etiket: str, sebep: str = "") -> None:
            """Puana ekle ve kırılımda sakla. Sıfır katkı KAYDEDİLMİYOR —
            listeyi 'bu terim seni etkilemedi' satırlarıyla doldurmak,
            gerçekten etkileyenleri gizler."""
            nonlocal score
            if not deger:
                return
            score += deger
            c.parts.append({"key": anahtar, "points": round(deger, 1),
                            "label": etiket})
            if sebep:
                c.reasons.append(sebep)

        if c.critical:
            kat("critical", WEIGHTS["critical"], "kritik yolda",
                "kritik yolda — ÇAP süresini bu zincir belirler")
        share = c.unlocks / max_unlock
        kat("unlock", WEIGHTS["unlock"] * share,
            f"{c.unlocks} dersin önşartı",
            f"{c.unlocks} dersin önşartı" if c.unlocks else "")
        if c.required:
            kat("required", WEIGHTS["required"], "zorunlu ders")
        else:
            c.reasons.append("seçmeli havuzdan")
        if max_tier:
            kat("early_tier", WEIGHTS["early_tier"] * (max_tier - c.tier) / max_tier,
                "zincirin başında")
        durum = kontenjan_durumu(c.sections)          # ★★ Faz 90
        if durum == "kritik":
            kat("scarcity", WEIGHTS["scarcity"], "kontenjan kritik",
                "kontenjan kritik")
        elif durum == "dolu":
            kat("full", WEIGHTS["full"], "bütün şubeler dolu",
                "bütün şubeler dolu — kontenjan izlenmeli")
        if len(c.sections) == 1:
            kat("single", WEIGHTS["scarcity"] / 2, "tek şube", "tek şube")
        elif len(c.sections) > DEFERRABLE_SECTIONS:
            kat("deferrable", WEIGHTS["deferrable"],
                f"{len(c.sections)} şube — ertelenebilir",
                f"{len(c.sections)} şube — her dönem açılır, ertelenebilir")
        if c.role != "ANADAL":
            label = "Yandal" if c.role == "YANDAL" else "ÇAP"
            kat("cap_role", WEIGHTS["cap_role"], f"{label} dersi — arzı kısıtlı",
                f"{label} dersi — arzı kısıtlı")
        # ⚠️ ÖNŞART DURUMU ARTIK YALNIZ ROZETTE (UX düzeltmesi 27.08.2026):
        # aynı bilgi hem rozet hem `reasons` metni olarak iki kez görünüyordu
        # ve GEO derslerinin ~%85'inde katalogda önşart metni olmadığı için
        # her satırda tekrar eden bir gürültüye dönüşmüştü (ölçüldü: 18
        # adayın 15'i). Rozet kompakt sinyali, ipucu da "OBS'den doğrula"
        # tavsiyesini taşıyor; metinde ayrıca yazmak yer kaplıyordu.
        #
        # "Önşartı yok" DEMİYORUZ — katalogda metin yok, bu iki farklı şey.
        # O ayrımı rozetin kendisi ve ipucu koruyor.
        c.score = round(score, 1)
        # ⚠️ Kırılım toplamı puanla TUTMALI. Ayrışırlarsa arayüz yalan söyler;
        # test bunu kilitliyor (test_faz27).
        c.parts.sort(key=lambda x: -abs(x["points"]))
    cands.sort(key=lambda x: (-x.score, x.course))
    return cands


# --------------------------------------------------- çakışmasız kombinasyon
@dataclass
class Pick:
    candidate: Candidate
    section: Section


@dataclass
class Schedule:
    picks: list[Pick]
    # ★ Tercihler programa BAĞLI taşınıyor: `score` iki yerden okunuyor
    # (sıralama ve arayüz) ve ikisinin aynı sayıyı vermesi gerekiyor.
    prefs: "Preferences | None" = None

    @property
    def ects(self) -> float:
        return round(sum(p.candidate.ects for p in self.picks), 1)

    @property
    def credits(self) -> float:
        return round(sum(p.candidate.credits for p in self.picks), 1)

    @property
    def load(self) -> float:
        return round(sum(p.candidate.load for p in self.picks), 1)

    @property
    def base_score(self) -> float:
        """Tercihlerden BAĞIMSIZ puan — motorun kendi değerlendirmesi."""
        return round(sum(p.candidate.score for p in self.picks), 1)

    @property
    def score(self) -> float:
        return round(self.base_score + self.pref_delta
                     - SIKISIK_GECIS_CEZASI * self.sikisik_gecisler(), 1)

    def sikisik_gecisler(self) -> int:
        """★★ Faz 94 — arka arkaya, FARKLI yerleşkede ve arada < 60 dk olan
        ders çifti sayısı.

        Ölçüm (25.09.2026, gerçek katalog, 11 profil): önerilerdeki 17
        yerleşke değişiminin 10'unda arada 1 DAKİKA vardı (ör. ISL 224E Maçka
        11:29'da biter, BLG 351E Ayazağa 11:30'da başlar). `campus_changes`
        üç saatlik arayı da bir dakikalık arayı da aynı sayıyordu ve yalnız
        tercih açıksa sıralamaya giriyordu.
        ⚠️ Katalogda yol süresi yok; eşik bir kabul. Yerleşkesi bilinmeyen
        buluşma (çevrimiçi, bina ilan edilmemiş) sayılmıyor.
        """
        by_day: dict[int, list[tuple[int, int, str | None]]] = {}
        for pick in self.picks:
            if pick.section.online:
                continue
            for m in pick.section.meetings:
                by_day.setdefault(m.day, []).append((m.start, m.end, m.campus))
        n = 0
        for slots in by_day.values():
            slots.sort()
            for a, b in zip(slots, slots[1:]):
                if a[2] and b[2] and a[2] != b[2] and b[0] - a[1] < YERLESKE_ESIK_DK:
                    n += 1
        return n

    @property
    def pref_delta(self) -> float:
        return tercih_puani(self.picks, self.prefs, self.campus_changes())[0]

    def pref_reasons(self) -> list[str]:
        return tercih_puani(self.picks, self.prefs, self.campus_changes())[1]

    # ★★ FAZ 37 — "tercihini karşılayamadım" demek yetmiyor: NEYİ bırakırsan
    # olur (docs/fikirler.md §3.5).
    #
    # Faz 27 ölçümü: "Pzt + Cuma boş" istendiğinde motor ikisini birden
    # sağlayamıyor ve −10 farkla en yakınını sunuyor. Doğru davranış, ama
    # kullanıcı çıkışın nerede olduğunu göremiyordu.
    #
    # ⚠️ Yalnız TEK adımlık öneri veriyoruz: "şu iki dersi de çıkar" demek
    # programı baştan kurmak olurdu ve o işi zaten motor yapıyor (öbür
    # öneriler). Tek ders çıkarmak geri alınabilir bir hamle.
    #
    # ⚠️ Kredi/şart etkisini SAKLAMIYORUZ: çıkarılan ders kredi ve slot
    # kaybettirir. Öneriyle birlikte kaç kredi gittiğini de veriyoruz ki
    # "boş gün" uğruna sessizce bir zorunlu ders düşmesin.
    def pref_relief(self) -> list[dict]:
        """Tek bir dersi çıkarınca TAM sağlanan tercihler."""
        if self.prefs is None or not self.prefs.var_mi or len(self.picks) < 2:
            return []
        simdi = _tercih_sayaclari(self.picks, self.prefs)
        # Yalnız İHLAL sayan tercihler için anlamlı: "istediğin hoca" sayısını
        # sıfıra indirmek bir kazanç değil, kayıp.
        ihlaller = {"erken": "{n} ders erken başlıyor",
                    "bos_gun": "boş kalması istenen gün(ler) boşalıyor",
                    "hoca_istenmeyen": "tercih edilmeyen öğretim üyesi kalmıyor"}
        aktif = {k for k, v in simdi.items() if v and k in ihlaller}
        if not aktif:
            return []
        out: list[dict] = []
        for p in self.picks:
            kalan = [q for q in self.picks if q is not p]
            sonra = _tercih_sayaclari(kalan, self.prefs)
            kazanc = [ihlaller[k].format(n=simdi[k])
                      for k in aktif if sonra[k] == 0]
            if not kazanc:
                continue
            out.append({
                "course": p.candidate.course,
                "role": p.candidate.role,
                "required": bool(p.candidate.required),
                "credits": p.candidate.credits,
                "gains": kazanc,
            })
        # Zorunlu dersi çıkarmayı önce ÖNERME: en ucuz hamle önde olsun.
        out.sort(key=lambda d: (d["required"], d["credits"]))
        return out

    def campus_changes(self) -> int:
        """Aynı gün içinde kampüs değiştiren ardışık ders çifti sayısı."""
        by_day: dict[int, list[tuple[int, str | None]]] = {}
        for pick in self.picks:
            # ★ Faz 57: çevrimiçi şube kampüste değil (`Section.campuses`
            # bunu biliyordu, bu sayım bilmiyordu) — kayıtlı dersliği olan
            # çevrimiçi ders var olmayan bir yolculuk ekliyordu.
            if pick.section.online:
                continue
            for m in pick.section.meetings:
                by_day.setdefault(m.day, []).append((m.start, m.campus))
        changes = 0
        for slots in by_day.values():
            slots.sort()
            for (_, a), (_, b) in zip(slots, slots[1:]):
                if a and b and a != b:
                    changes += 1
        return changes

    def courses(self) -> tuple[str, ...]:
        return tuple(sorted(p.candidate.course for p in self.picks))

    # ---------------------------------------------- yarıyıl kredi tabanı
    # ★ Yapılacaklar 1.4 (23.08.2026). Taban Faz 13'te eklenmişti ama yalnız
    # bir UYARIYDI; motor onu bilmiyordu. Gerçek veride sonuç şuydu: önerilen
    # program ikinci anadaldan **4 kredi** içeriyordu, taban ise 9. Yani motor
    # kabul edilemez bir programı "en iyi program" diye sunuyordu.
    def credits_by_role(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for p in self.picks:
            out[p.candidate.role] = round(
                out.get(p.candidate.role, 0.0) + (p.candidate.credits or 0.0), 1)
        return out

    def floor_gaps(self, floors: dict[str, float] | None) -> dict[str, float]:
        """{rol: eksik kredi} — tabanı karşılamayan roller."""
        if not floors:
            return {}
        var = self.credits_by_role()
        return {rol: round(taban - var.get(rol, 0.0), 1)
                for rol, taban in floors.items()
                if taban and var.get(rol, 0.0) + 1e-9 < taban}

    def meets_floors(self, floors: dict[str, float] | None) -> bool:
        return not self.floor_gaps(floors)


# ★★ FAZ 53 — SAAT ARALIĞINA KİLİT (yapılacaklar 2.4).
#
# Faz 45'in kilidi ŞUBEYE bağlıydı: "bu ders TAM BU SAATTE". Kullanıcının
# asıl sık istediği daha gevşek: "bu ders SABAH olsun, şubesi fark etmez".
# Bugüne kadar tek yolu bir şube seçip ona kilitlemekti — yani motorun o
# aralıktaki ÖBÜR şubeleri denemesini de engellemek.
#
# Aynı ayar satırı, iki biçim: `"DERS@CRN"` (Faz 45) ya da
# `"DERS@SS:DD-SS:DD"`. Değer bir aralıksa motor dersi yine programda tutar
# (kilit sert), ama yalnız BÜTÜN saatleri o aralıkta kalan şubeleri dener.
KILIT_ARALIK_DESENI = re.compile(r"^\s*(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})\s*$")
# Veriden seçildi (21.09.2026, 3630 buluşma): hiçbir ders 12:00'de başlamıyor;
# sabah dersleri en geç 12:29'da bitiyor (763 buluşma), öğleden sonrakiler
# 12:30'da başlıyor (178). Saatli 3089 şubenin 1283'ü tamamen sabah,
# 1412'si tamamen öğleden sonra; 394'ü iki yana taşıyor ve İKİSİNE DE uymaz.
OGLE = 12 * 60 + 30
KILIT_ONAYAR = {"sabah": (0, OGLE), "ogleden_sonra": (OGLE, 24 * 60)}


def kilit_araligi(deger: str) -> tuple[int, int] | None:
    """`"08:30-12:30"` → `(510, 750)`. Değer aralık değilse (CRN ise) ya da
    bozuksa `None` — ikisini ayırmak çağıranın işi (`kilit_bicimi`)."""
    m = KILIT_ARALIK_DESENI.match(str(deger or ""))
    if not m:
        return None
    sa, da, sb, db = (int(x) for x in m.groups())
    if da > 59 or db > 59:
        return None
    a, b = sa * 60 + da, sb * 60 + db
    return (a, b) if 0 <= a < b <= 24 * 60 else None


def aralik_yazi(lo: int, hi: int) -> str:
    """`(510, 750)` → `"08:30-12:30"` — ayara yazılan tek biçim."""
    return f"{lo // 60:02d}:{lo % 60:02d}-{hi // 60:02d}:{hi % 60:02d}"


def kilit_bicimi(deger: str) -> str:
    """`"sube"` (CRN) · `"aralik"` · `"bozuk"`.

    ⚠️ Bozuk değer CRN SAYILMAZ. Sayılsaydı `"8.30-12.30"` gibi bir yazım
    hatası hiçbir şubeyle eşleşmez, ders zorunlu kalır ve BÜTÜN ÖNERİLER
    boşalırdı — kullanıcı da "CRN 8.30-12.30 açık değil" gibi anlamsız bir
    cümle okurdu. Bozuk satır motora hiç girmiyor; arayüz onu ayrıca
    "okunamadı" diye gösteriyor."""
    deger = str(deger or "").strip()
    if kilit_araligi(deger):
        return "aralik"
    return "sube" if deger.isdigit() else "bozuk"


def araliga_uyar(section: Section, lo: int, hi: int) -> bool:
    """Şubenin BÜTÜN saatleri `[lo, hi]` içinde mi?

    ⚠️ Saati ilan edilmemiş şube UYMAZ. "Sabah olsun" diyen kullanıcıya
    saati bilinmeyen şubeyi vermek, bilinmeyeni biliniyor gibi göstermek
    olurdu (verideki 3417 şubenin 328'inin saati yok)."""
    return bool(section.meetings) and all(
        lo <= m.start and m.end <= hi for m in section.meetings)


def kilide_uyar(section: Section, deger: str) -> bool:
    """Bu şube bu kilidi karşılıyor mu (iki biçim için de)."""
    aralik = kilit_araligi(deger)
    if aralik:
        return araliga_uyar(section, *aralik)
    return section.crn == str(deger).strip()


SECTION_BRANCHES = 3      # bir ders için denenecek alternatif şube sayısı
SEARCH_BUDGET = 300_000   # emniyet supabı: arama düğümü üst sınırı
POOL_FACTOR = 60          # kaç aday program toplanıp sıralanacak (limit × bu)


def build_schedules(cands: list[Candidate], max_load: float = 35.0,
                    limit: int = 3, pinned: Iterable[str] = (),
                    fixed: Iterable[Section] = (),
                    floors: dict[str, float] | None = None,
                    prefs: Preferences | None = None,
                    locked: Mapping[str, str] | None = None) -> list[Schedule]:
    """Greedy + backtracking. Farklı DERS KÜMELERİ üretir, aynı kümenin
    farklı CRN varyantlarını tekrar etmez (alternatifler ayrıca raporlanır).

    ★ İKİ DÜZELTME (20.08.2026, gerçek programla karşılaştırmadan):

    1. Bir ders için TEK şube denemek yetmiyor. `BLG 351E`'nin Pazartesi şubesi
       `GEO 401E` ile çakışıyor ama Çarşamba şubesi çakışmıyor.
    2. İlk bulunan tam programı kabul etmek yetmiyor — o, saf açgözlü sonuç.
       Bir HAVUZ toplayıp toplam puana göre sıralıyoruz; böylece "şubeyi kaydırıp
       bir ders daha sığdıran" çözüm öne geçiyor."""
    pinned = {p.upper() for p in pinned}
    # ★★ FAZ 45 — SAATE KİLİT (kullanıcı isteği 17.09.2026).
    #
    # `pinned` "bu ders programda olsun" diyor ama ŞUBEYİ motora bırakıyor;
    # kullanıcı bir dersi beğendiği SAATTE tutmak istiyor. `locked` tam olarak
    # o: {ders: CRN}. Kilitli dersin yalnız o şubesi denenir, gerisi onun
    # etrafında kurulur.
    #
    # ⚠️ Kilit SERT kısıt — ve bu bilinçli. Yumuşak olsaydı (sıralamayı
    # etkileseydi) motor kilidi sessizce yok sayabilirdi; kullanıcı da
    # "kilitledim ama değişti" derdi. Sert olduğu için kilitler birbiriyle
    # çakıştığında SONUÇ BOŞ çıkıyor — arayüz bunu "kilit yüzünden" diye
    # söylemek zorunda, yoksa "çakışmasız kombinasyon yok" sanılır.
    # ⚠️ Faz 53: BOZUK değer motora girmiyor (bkz. `kilit_bicimi`) — girseydi
    # hiçbir şubeyle eşleşmeyip bütün önerileri boşaltırdı.
    locked = {str(k).upper(): str(v).strip() for k, v in (locked or {}).items()
              if kilit_bicimi(v) != "bozuk"}
    # ⚠️ Kilit yalnız BU HAVUZDA olan derse bağlanır. Sebebi ölçülmüş bir
    # tuzak: arayüzün iki kipi (DEPAR / "N. dönem + alttan") AYRI aday
    # havuzları kuruyor. `all` kipinde kilitlenen üst dönem dersi, dönemlik
    # havuzda hiç yok — kilidi orada da zorunlu saysaydık o kip topyekûn
    # boşalırdı. Ders masada değilse kilit "yok sayılmıyor", KAPSAM DIŞI.
    # Ders havuzda ama CRN kapanmışsa kilit SERT kalıyor ve sonuç boşalıyor;
    # o gerçekten söylenmesi gereken bir durum (arayüz `locked[].ok` ile
    # söylüyor), sessizce şube kaydırmak değil.
    havuzda = {c.course for c in cands}
    locked = {k: v for k, v in locked.items() if k in havuzda}
    pinned |= set(locked)
    # ★★ FAZ 53 — KİLİTLİ/ZORUNLU DERS ARAMADA ÖNE ALINIYOR (ölçüm 21.09.2026).
    #
    # Adaylar puana göre sıralı ve arama derinlik öncelikli: kilitli ders
    # düşük puanlıysa (ör. ALM 102, ATA 121) SONLARDA kalıyordu. Motor önce
    # yüksek puanlı dersleri yerleştiriyor, kilitli derse gelince onun saati
    # dolu çıkıyor ve dal ölüyordu — bütçe (SEARCH_BUDGET) bu ölü dallarda
    # tükeniyordu. Gerçek veride 139 tek şube kilidi (Faz 45'in tek yolu)
    # denendi: **22'si HİÇ PROGRAM ÜRETMEDİ** — `ALM 102`nin iki şubesi de
    # "öneri üretilemedi" verdi. Arayüz bunu "kilitler birbiriyle ya da
    # meşgul saatinle çakışıyor" diye açıklıyordu: tek kilit ve hiç meşgul
    # saat yokken. Öne alınınca 22'nin 22'si program üretti; o kilitlerde
    # arama ~1,5 sn → ~0,15 sn.
    # ⚠️ Kilit/zorunlu YOKSA sıra DEĞİŞMİYOR — bütün kilitsiz sonuçlar
    # birebir aynı (testte tutuluyor).
    if pinned:
        cands = sorted(cands, key=lambda c: c.course not in pinned)   # kararlı
    fixed = list(fixed)
    results: list[Schedule] = []
    # ders kümesi → [results indeksi, sıkışık geçiş sayısı]
    seen: dict[tuple[str, ...], list] = {}

    # Sabit dersler (ör. anadalda zaten kayıtlı olduğun şubeler) çakışma tabanı.
    # ★★ Faz 91 — seçilenlerin ve sabitlerin dakika maskeleri YIĞINDA birikiyor:
    # "bu şube sığar mı" tek AND (eskiden her seçilen şubeyle ayrı ayrı).
    dolu_maske = [0]
    for f in fixed:
        dolu_maske[0] |= f.maske

    def fits(section: Section, chosen: list[Pick]) -> bool:
        return not (section.maske & dolu_maske[-1])

    budget = [SEARCH_BUDGET]
    pool_size = max(limit, limit * POOL_FACTOR)
    # ★★ Faz 92 — AYNI DERSİN İKİ DİLİ AYNI PROGRAMA GİRMEZ. ÇAP slotu dil
    # eşini de aday yapınca (EHB 222 Türkçe, ÇAP) ile anadalın EHB 222E'si
    # ayrı slotlara eşleşip birlikte seçilebilirdi — aynı dersi iki kez almak.
    # (Anadal X, ÇAP XE yazdığında bu eskiden de mümkündü.) İkisi de aday
    # listesindeyse ikizdirler: katalog çiftlerinin 2809'undan 2807'si aynı
    # kredi/AKTS'li aynı ders (bkz. rules.dil_esi).
    _kodlar = {c.course for c in cands}
    ikiz = {c.course: e for c in cands
            for e in [c.course[:-1] if c.course.endswith("E") else c.course + "E"]
            if e in _kodlar}
    # Aday indeksi → denenecek şubeler, sıralı. Bkz. `search` içindeki not.
    _sira: dict[int, list[Section]] = {}
    # Aralık kilitli derslerin indeksleri: orada aralığa uyan BÜTÜN şubeler
    # deneniyor ve her dal havuzdan/bütçeden adil pay alıyor (bkz. `search`).
    _aralik_idx: set[int] = set()
    # Sonuç tavanı ve bütçe tabanı YIĞINLARI.
    ust = [pool_size]
    taban = [0]

    def blocking_cost(section: Section, index: int) -> float:
        """Bu şube seçilirse, GERİYE KALAN adaylardan kaçının puanı yanar?

        ★ Şubeyi sadece 'en boş' diye seçmek yetmiyor. `BLG 351E`'nin Pazartesi
        şubesi zorunlu `GEO 401E` ile (72,5 puan), Çarşamba şubesi ise yalnızca
        bir havuz dersiyle (32,5) çakışıyor. İleriye bakmadan seçince daha
        değerli ders programdan düşüyordu (20.08.2026).

        Bir aday ancak TÜM şubeleri bu şubeyle çakışıyorsa 'yanmış' sayılır.
        """
        cost = 0.0
        for other in cands[index + 1:]:
            if not other.sections:
                continue
            if all(section_conflict(section, sec) for sec in other.sections):
                cost += other.score
        return cost

    # ★★ FAZ 91 — ARTIMLI YUVA EŞLEŞTİRMESİ (ölçüm 25.09.2026, gerçek katalog).
    #
    # Faz 81'in "havuz dolu mu" sorusu her arama düğümünde `yuva_ata`yı
    # SIFIRDAN koşuyordu: seçilenlerin hepsi + aday için baştan Kuhn. INSE 1.
    # yarıyılda 282.000 çağrı, profilde 12 sn'nin 7,2 sn'si. Oysa aramanın
    # değişmezi var: `chosen` HER ZAMAN tamamen eşleşmiş (her seçim bu
    # denetimden geçerek eklendi). Berge teoremi: seçilenlerin hepsini
    # eşleyen bir eşleştirmeye yeni aday ancak ONDAN başlayan bir artırma yolu
    # varsa eklenebilir — tek bir DFS yeter, cevap `yuva_ata(chosen + [aday])
    # is not None` ile AYNI. Eşleştirme yığında tutuluyor (geri izlemede
    # önceki hâline dönülüyor). Kopya küçük: bir dönemde ~10 ders.
    yuva_yigin: list[dict] = [{}]

    def search(index: int, chosen: list[Pick], load: float) -> None:
        if len(results) >= ust[-1] or budget[0] <= taban[-1]:
            return
        budget[0] -= 1
        if index >= len(cands):
            if chosen:
                key = tuple(sorted(p.candidate.course for p in chosen))
                if key not in seen:
                    yeni = Schedule(list(chosen), prefs)
                    seen[key] = [len(results), yeni.sikisik_gecisler()]
                    results.append(yeni)
                elif seen[key][1]:
                    # ★★ Faz 94: aynı ders kümesinin ŞUBE varyantı yalnız
                    # sıkışık yerleşke geçişi daha AZSA eskisinin yerine geçer.
                    # Eskiden ilk bulunan kalıyordu; 11:30 Ayazağa şubesi 14:30
                    # şubesinden önce denenince 1 dakikalık geçiş kalıcıydı.
                    # Geçiş yoksa hiçbir şey değişmiyor (ilk bulunan kalıyor).
                    # Sayı kayıtta: geçişi olmayan kümede (çoğu) hiç hesap yok.
                    yeni = Schedule(list(chosen), prefs)
                    n = yeni.sikisik_gecisler()
                    if n < seen[key][1]:
                        results[seen[key][0]] = yeni
                        seen[key][1] = n
            return
        cand = cands[index]
        must = cand.course in pinned
        # ★ Bir seçmeli havuz slotu TEK ders ile dolar. Bu kontrol olmadan motor
        # aynı ITB havuzu için HUK 217 + HUK 218'i birlikte öneriyordu (20.08.2026).
        # ★★ Faz 81 — "dolu" artık EŞLEŞTİRME: seçilenlerin her biri ayrı bir
        # slota yerleşebiliyorsa aday da girer (ENDE'de dört Functional-MT
        # yuvası boşken yalnız birinci yuvaya bakılıyordu).
        # ★★ Faz 91 — önce ucuz yük denetimi; eşleştirme yalnız yük sığıyorsa
        # (ikisi VE ile bağlı, sonuç aynı). Eşleştirme artımlı (bkz. yuva_ekle).
        sigar = load + cand.load <= max_load
        if sigar and ikiz and cand.course in ikiz:
            es = ikiz[cand.course]
            sigar = not any(p.candidate.course == es for p in chosen)
        yeni_yuva = yuva_ekle(yuva_yigin[-1], cand) if sigar and cand.yuvalar else None
        pool_taken = bool(cand.yuvalar) and yeni_yuva is None
        if not pool_taken and sigar:
            # Önce en az değer yakan şube; eşitlikte en boş olan (kontenjan riski).
            # Saati ilan edilmemiş şube hiçbir şeyle çakışmadığı için ileriye
            # bakış maliyeti 0 çıkıyor ve metriği kandırıyor. Belirsizlik avantaj
            # değil: saatli şubeler önce denenir, saatsiz olan son çare.
            # ★★ Faz 27: tercih ŞUBE SEÇİMİNE giriyor ve `blocking_cost` ile
            # AYNI ÖLÇEKTE toplanıyor — ikisi de "puan" cinsinden.
            #
            # ⚠️ İlk denemede tercihi ayrı bir sıralama anahtarı yapmıştım;
            # ölçtüm, HİÇBİR ŞEYİ değiştirmedi: `blocking_cost` bir float ve
            # neredeyse hiç eşitlenmiyor, dolayısıyla ikinci anahtara sıra
            # hiç gelmiyordu. FIZ 102E'nin hem 08:30 hem 14:30 şubesi varken
            # "sabah istemiyorum" seçili kullanıcıya yine 08:30 veriliyordu.
            #
            # Toplayınca anlam doğru çıkıyor: 6 puanlık bir tercih, 6 puandan
            # AZ değer yakan bir şube farkını çevirebilir; daha fazlasını
            # çeviremez. Ders puanları 40–100 aralığında olduğu için tercih
            # hiçbir zaman değerli bir dersi programdan düşüremiyor.
            # ★★ FAZ 46 — SIRA İNDEKS BAŞINA BİR KEZ (ölçüm 18.09.2026).
            # `blocking_cost(s, index)` yalnız `index`e ve şubeye bağlı;
            # `chosen`a BAKMIYOR. Yani aynı indeksteki sıralama arama
            # ağacının her düğümünde aynı çıkıyordu ve baştan hesaplanıyordu:
            # profilde 46.549 çağrı, `snapshot()`ın 3,4 saniyesi.
            # ⚠️ Bu bir ÖNBELLEK, davranış değişikliği değil: sıralama
            # anahtarına `chosen` girerse bu memo KALDIRILMALI (testte
            # tutuluyor).
            ordered = _sira.get(index)
            if ordered is None:
                def _sube_maliyeti(s: Section) -> float:
                    # ★★ Faz 90 — dolu şubenin maliyeti (bkz. DOLU_SUBE_MALIYETI).
                    dolu = DOLU_SUBE_MALIYETI if s.capacity and s.free == 0 else 0.0
                    return blocking_cost(s, index) - sube_tercih_puani(s, prefs) + dolu

                ordered = sorted(cand.sections,
                                 key=lambda s: (not s.meetings, _sube_maliyeti(s),
                                                -s.free, s.crn))
                # Kilitliyse tek şube denenir — "saate kilit" tam olarak bu.
                # ★ Faz 53: aralık kilidinde o aralığa uyan BÜTÜN şubeler
                # denenir (sıra yine aynı ölçüyle) — şube motora kalıyor,
                # saat kullanıcının.
                if cand.course in locked:
                    ordered = [s for s in ordered
                               if kilide_uyar(s, locked[cand.course])]
                    if kilit_bicimi(locked[cand.course]) == "aralik":
                        _aralik_idx.add(index)
                _sira[index] = ordered
            # ★★ FAZ 53 — ARALIK KİLİDİNDE ADİL PAY (ölçüm 21.09.2026).
            # Aralıktaki şubelerin yalnız 3'ünü denemek YETMİYOR, hepsini
            # denemek de yetmiyor: ilk şubenin alt ağacı havuzu (`pool_size`)
            # tek başına dolduruyordu, ötekilere sıra gelmiyordu. Ölçüldü: 26
            # durumun 5'inde aralık kilidi, aralıktaki bir şubeye TEK kilitten
            # daha kötü program verdi (ATA 122 öğleden sonra 1161,1 → 1088,6).
            # Her şube dalı, kalan havuzun ve kalan bütçenin kalan dal sayısına
            # bölünmüş payını alıyor (kullanmadığı pay sonrakine geçiyor):
            # 26 durumun 26'sında aralık kilidi en iyi tek şube kilidine
            # yetişti ya da geçti, süre medyanı 0,18 sn.
            paylas = index in _aralik_idx
            uyanlar = (s for s in ordered if fits(s, chosen))
            # Öbür derslerde `fits` eskisi gibi TEMBEL (sınıra varınca durur).
            denenecek = (list(uyanlar) if paylas
                         else islice(uyanlar, SECTION_BRANCHES))
            for j, section in enumerate(denenecek):
                if paylas:
                    kalan = len(denenecek) - j
                    ust.append(min(ust[-1], len(results)
                                   + max(1, (ust[-1] - len(results)) // kalan)))
                    taban.append(budget[0] - max(1, (budget[0] - taban[-1]) // kalan))
                chosen.append(Pick(cand, section))
                dolu_maske.append(dolu_maske[-1] | section.maske)
                if yeni_yuva is not None:
                    yuva_yigin.append(yeni_yuva)
                search(index + 1, chosen, load + cand.load)
                if yeni_yuva is not None:
                    yuva_yigin.pop()
                dolu_maske.pop()
                chosen.pop()
                if paylas:
                    ust.pop(); taban.pop()
        if not must:
            search(index + 1, chosen, load)

    search(0, [], 0.0)
    if pinned:
        results = [s for s in results if pinned <= set(s.courses())]
    # ★ Yarıyıl kredi tabanını KARŞILAYAN programlar önce (yapılacaklar 1.4).
    #
    # ⚠️ SERT KISIT DEĞİL. Yönerge tabanın "ÇAP Koordinatörünün uygun görüşü ve
    # Fakülte Yönetim Kurulu Kararı ile yarıya kadar düşürülebileceğini"
    # söylüyor; ayrıca o dönem açılan ders yetmiyor olabilir. Karşılayan hiç
    # program yoksa eleyip boş liste döndürmek, çözülebilir bir durumu
    # imkânsız göstermek olurdu. Onun yerine SIRALAMA değişiyor ve eksik
    # `floor_gaps` ile raporlanıyor — arayüz bunu yazıyor.
    results.sort(key=lambda s: (not s.meets_floors(floors),
                                -s.score, -s.load, s.campus_changes()))
    return results[:limit]


def alternatives(schedule: Schedule, cands: list[Candidate]) -> dict[str, list[str]]:
    """Her ders için çakışmayan diğer CRN'ler (kontenjan dolarsa yedek)."""
    out: dict[str, list[str]] = {}
    for pick in schedule.picks:
        others = []
        for section in pick.candidate.sections:
            if section.crn == pick.section.crn:
                continue
            clash = any(section_conflict(section, p.section)
                        for p in schedule.picks if p is not pick)
            if not clash:
                others.append(f"{section.crn} ({section.enrolled}/{section.capacity})")
        if others:
            out[pick.candidate.course] = others
    return out


# -------------------------------------------------------------------- çıktı
# 'undeclared' = "İlgili Bölümce Açıklanacak" — kullanıcıya İngilizce sızmasın.
# ★ "belirsiz" DEĞİL "yer yok" (Faz 28): arayüzle aynı sözü kullanıyoruz ve
# "belirsiz" bir bina adı gibi okunuyordu. Ölçüldü: 3630 buluşmanın 1542'si
# (%42) ilan edilmemiş — yani en sık görülen "bina adı" uydurma bir kelimeydi.
_YER_YOK = {"", "-", "--", "undeclared", "tba", "tbd"}


def _building_label(code: str | None) -> str:
    # ★ Faz 56: "yer yok" → "yer bildirilmedi". Kayıt aracında CRN'nin yanında
    # "yer yok" KONTENJAN DOLU diye okunuyordu; oysa anlamı "derslik ilan
    # edilmemiş". Arayüzle AYNI söz (Faz 28'in kuralı) — ikisi birlikte değişti.
    return "yer bildirilmedi" if (code or "").strip().lower() in _YER_YOK else (code or "").strip()


def format_candidates(cands: list[Candidate], top: int = 12) -> str:
    out = ["=" * 72, "ADAY DERSLER (puana göre)", "=" * 72]
    for cand in cands[:top]:
        free = max((s.free for s in cand.sections), default=0)
        out.append(
            f"  {cand.score:>5.1f}  {cand.course:<11} {cand.role:<7} "
            f"{cand.credits:>4g} kr / {cand.ects:g} akts  "
            f"{len(cand.sections)} şube (en boş {free})  {cand.name[:24]}")
        if cand.reasons:
            out.append(f"          · {'; '.join(cand.reasons)}")
    if len(cands) > top:
        out.append(f"  … {len(cands) - top} aday daha")
    return "\n".join(out)


def format_schedule(schedule: Schedule, cands: list[Candidate], index: int = 1) -> str:
    out = ["", "=" * 72,
           f"ÖNERİ {index} — {len(schedule.picks)} ders · {schedule.credits:g} kredi / "
           f"{schedule.ects:g} AKTS · puan {schedule.score:g} · "
           f"kampüs değişimi {schedule.campus_changes()}",
           "=" * 72]
    for pick in sorted(schedule.picks, key=lambda p: -p.candidate.score):
        times = " | ".join(m.label() for m in pick.section.meetings) or "saat bilgisi yok"
        # ★ Faz 93: derslik de ("MED D102"); ilan edilmemişse yalnız bina.
        rooms = {_building_label(m.building) + (
                     f" {m.room.strip()}" if (m.room or "").strip().lower() not in _YER_YOK
                     and (m.building or "").strip().lower() not in _YER_YOK else "")
                 for m in pick.section.meetings if m.building}
        out.append(
            f"  {pick.candidate.course:<11} {pick.candidate.role:<7} "
            f"{pick.candidate.credits:>4g} kr  CRN {pick.section.crn} "
            f"({pick.section.enrolled}/{pick.section.capacity})  "
            f"{times}  {'/'.join(sorted(rooms))}")
    alts = alternatives(schedule, cands)
    if alts:
        out.append("\n  Alternatif CRN (kontenjan dolarsa):")
        for course, others in alts.items():
            out.append(f"    {course:<11} {', '.join(others[:4])}")
    out.append("")
    out.append(weekly_grid(schedule))
    return "\n".join(out)


def weekly_grid(schedule: Schedule, start_hour: int = 8, end_hour: int = 20) -> str:
    """Basit haftalık ızgara — Faz 6'daki görsel gridin metin karşılığı."""
    cells: dict[tuple[int, int], str] = {}
    for pick in schedule.picks:
        for m in pick.section.meetings:
            for hour in range(m.start // 60, (m.end + 59) // 60):
                cells[(m.day, hour)] = pick.candidate.course.replace(" ", "")[:9]
    header = "      " + "".join(f"{DAY_NAMES[d]:<11}" for d in range(1, 6))
    lines = [header, "     " + "-" * 55]
    for hour in range(start_hour, end_hour):
        row = f"{hour:02d}:00 "
        for day in range(1, 6):
            row += f"{cells.get((day, hour), ''):<11}"
        lines.append(row.rstrip() if row.strip() else row)
    return "\n".join(lines)


# ------------------------------------------------- ÇAP darboğaz çözümlemesi
@dataclass
class Blocker:
    course: str
    # 'ACILMAMIS' | 'PROGRAMA_KAPALI' | 'ONSART' | 'ONSART_KATALOGDA_YOK'
    # | 'KREDI_ESIGI' | 'ALIYORSUN' | 'BILINMIYOR'
    reason: str
    detail: str = ""


# ★★ FAZ 42 — HAYALET ÖNŞART: katalogda olmayan dersi isteyen önşart.
#
# Ölçüm (16.09.2026, gerçek katalog): 19670 önşart yaprağının **1537'si (%7.8)**
# katalogda bulunmayan bir ders adını taşıyor; 275 farklı kod, 910 ders.
# Bunların 219'unun katalogda bir DİL EŞİ var (`BIL 100` yok ama `BIL 100E`
# var) ve kaynak metin ikisini zaten "veya" ile eşliyor — orada zarar yok.
# Geriye kalan 56 kodun hiçbir eşi yok: bunlar kapanmış ya da kod değiştirmiş
# dersler.
#
# İki ölçülen zarar:
#   ★★ Eksik önşart listesi ALFABETİK sıralanıp 4'e kesiliyordu. FIZ 241E ve
#      FIZ 272E'de gösterilen dördün DÖRDÜ de katalogda yok
#      (`BIL 102, BIL 102CE, BIL 102E, BIL 102FE`), öğrencinin gerçekten
#      alabileceği `BIL 104E/105E/106E` ise kesilip gizleniyordu. Ekran yalnız
#      çıkmaz sokakları gösteriyordu.
#   ★  Engelli 4627 dersin 723'ünde (%15.6) listede en az bir hayalet kod var
#      ve hangisinin peşine düşülebileceği YAZMIYOR.
#
# ⚠️ Hayalet kod ATILMIYOR: öğrencinin transkriptinde eski kodla duruyor
# olabilir ve önşartı gerçekten sağlıyor olabilir. Yalnız SIRAYA sokuluyor
# (alınabilir olanlar önce) ve işaretleniyor.
def _onsart_ayikla(eksik: set[str], katalog: set[str],
                   goster: int = 4) -> tuple[str, bool]:
    """Eksik önşart listesini okunur hâle getirir.

    Dönüş: (metin, hepsi_hayalet_mi).
    """
    alinabilir = sorted(c for c in eksik if c in katalog)
    hayalet = sorted(c for c in eksik if c not in katalog)
    # Alınabilirler ÖNCE — kesme hepsini yutmasın.
    sirali = alinabilir + hayalet
    gosterilen = sirali[:goster]
    kalan = len(sirali) - len(gosterilen)
    # ★ Faz 104 — kod göçü beyanı olan eski kodun yanına yeni kodu: öğrenci
    # planında "BLG 252E"yi değil "BBF 203E"yi görüyor.
    from .declared import load_code_migrations
    yeni_kod = {e: y for e, y in load_code_migrations()}
    parca = ", ".join(f"{c} (yeni kodu {yeni_kod[c]})" if c in yeni_kod else c
                      for c in gosterilen)
    if kalan:
        parca += f" +{kalan}"
    n_hayalet = sum(1 for c in gosterilen if c not in katalog)
    if n_hayalet:
        parca += (f" (⚠ {n_hayalet}'i katalogda yok — eski kod olabilir)"
                  if alinabilir else " — hiçbiri katalogda yok")
    return parca, not alinabilir


def cap_blockers(con: sqlite3.Connection, ucon: sqlite3.Connection, student_id: int,
                 cap_plan_id: int, cap_program: str,
                 allowed_programs: Iterable[str] = (),
                 max_term: int | None = None,
                 dil_esi: bool = False) -> list[Blocker]:
    """Kalan her ders için 'neden bu dönem alamıyorum' cevabı.

    Ölçüm (18.08.2026): engelin çoğu önşart DEĞİL, **arz**. ÇAP dersleri ya bu
    dönem açılmıyor ya da şubeleri başka programlara ayrılmış oluyor.

    ★ `max_term` ANADAL için gerekli (inceleme C6): dönemli bir lisans
    planında ileriki dönemlerin dersleri "alamıyorsun" değil, "sırası
    gelmedi". Hepsini engel diye listelemek, 8. dönem derslerini 1. dönem
    öğrencisinin karşısına sorun gibi çıkarırdı.
    """
    from . import student as S

    grades = S.grades(ucon, student_id)
    taking = S.in_progress(ucon, student_id)
    equivalences = R.load_equivalences(con, ucon=ucon)
    expanded, _ = R.expand_with_equivalences(grades, equivalences)
    prereq_grades = R.prereq_view(expanded)
    trees = P.parsed_trees(con)
    unparsed = {r[0] for r in con.execute("SELECT course_code FROM prereq_unparsed")}
    rules = POL.load_rules()
    catalog_rule = POL.load_catalog_rule()
    credits_have = POL.earned_credits(con, grades)
    # Faz 42 — hayalet önşartı ayırt etmek için katalogdaki kodlar (tek sorgu).
    katalog_kodlari = {r[0] for r in con.execute("SELECT code FROM course")}

    out: list[Blocker] = []
    for row in con.execute(
        """SELECT id, course_code, term_no FROM plan_slot
           WHERE plan_id=? AND slot_kind='REQUIRED' AND course_code IS NOT NULL
           ORDER BY position""", (cap_plan_id,)
    ):
        code = row["course_code"]
        # ⚠️ Sırası GELMEMİŞ ders bir engel değil. Dönemsiz plandaki slotta
        # `term_no` yok — orada eleme yapmıyoruz, çünkü elenecek bir dönem
        # bilgisi yok (ÇAP/yandal planları böyle).
        if (max_term is not None and row["term_no"] is not None
                and row["term_no"] > max_term):
            continue
        if R.slot_satisfied(con, row["id"], grades, equivalences).satisfied:
            continue
        # ★ Faz 92: ÇAP/yandal slotunda dil eşinin şubesi de sayılır (bkz.
        # `candidates`). Engel satırı planın yazdığı kodla kalıyor.
        kodlar = ([code, *(k for k in R.slot_codes({"course_code": code,
                                                   "alt_course_codes": None}, con)
                           if k != code)] if dil_esi else [code])
        if any(k in taking for k in kodlar):
            # Engel değil, DURUM: bu dönem alıyorsun. Ayırt etmezsek 'neden
            # önerilmedi' sorusuna yanlış cevap verirdik.
            out.append(Blocker(code, "ALIYORSUN", "bu dönem programında"))
            continue
        crns = [r[0] for k in kodlar for r in con.execute(
            "SELECT crn FROM lesson WHERE course_code=?", (k,))]
        if not crns:
            out.append(Blocker(code, "ACILMAMIS", "bu dönem şube açılmamıştır"))
            continue
        allowed = {c.upper() for c in allowed_programs} or {cap_program}
        acik_kod = next((k for k in kodlar if load_sections(con, k, allowed)), None)
        if acik_kod is None:
            progs = sorted({r[0] for r in con.execute(
                "SELECT DISTINCT program_code FROM lesson_allowed_program WHERE crn IN (%s)"
                % ",".join("?" * len(crns)), crns)})
            # ★★ Faz 104 — "-" BİR PROGRAM DEĞİL. Kaynak, alabilecek programları
            # henüz ilan edilmemiş şubeye "-" yazıyor (gerçek katalog, 2026 Güz:
            # 3807 şubenin 70'i; 68'inde kontenjan 0, hoca "-", bina "-", yalnız
            # 3'ünde saat var). Bunlar "başka programlara ayrılmış" değil,
            # İLAN EDİLMEMİŞ: arayüz "yalnızca - alabilir" yazıyordu ve dersi
            # arz uyarısında yanlış gruba (programa kapalı) koyuyordu. Dersin
            # BÜTÜN şubeleri böyleyse ACILMAMIS (dönem başında ilanlar kademeli
            # yayımlanıyor); ilanlı şubesi de varsa yalnız gerçek programlar yazılıyor.
            gercek = [p for p in progs if p not in ("-", "")]
            if not gercek:
                out.append(Blocker(code, "ACILMAMIS",
                                   f"{len(crns)} şube listelenmiş, ancak saati, kontenjanı ve "
                                   "alabilecek programlar henüz ilan edilmemiştir"))
                continue
            out.append(Blocker(code, "PROGRAMA_KAPALI",
                               f"{len(crns)} şube bulunmaktadır; yalnızca {', '.join(gercek)} alabilir"))
            continue
        code = acik_kod                    # önşart/kredi: açık olan kodla
        if code in unparsed:
            out.append(Blocker(row["course_code"], "BILINMIYOR", "önşart verisi okunamadı"))
            continue
        verdict = R.can_take_tree(trees.get(code), prereq_grades)
        if verdict.status is R.Status.BLOCKED:
            metin, hepsi_hayalet = _onsart_ayikla(
                {m[0] for m in verdict.missing}, katalog_kodlari)
            if hepsi_hayalet:
                # ⚠️ Bu ders katalogdaki HİÇBİR dersle açılamıyor. "eksik:
                # ELH 332" demek, öğrenciyi var olmayan bir dersi aramaya
                # göndermek olurdu.
                out.append(Blocker(row["course_code"], "ONSART_KATALOGDA_YOK",
                                   f"önşartı katalogda bulunmamaktadır: {metin}"))
            else:
                out.append(Blocker(row["course_code"], "ONSART", f"eksik: {metin}"))
            continue
        # ★ Önşartı sağlansa bile mevzuat engelleyebilir (bitirme kredi eşiği).
        _ad = con.execute("SELECT name, class_restriction FROM course WHERE code=?",
                          (code,)).fetchone()
        cv = POL.check(code, credits_have, rules, (_ad[0] if _ad else "") or "",
                       (_ad[1] if _ad else None), catalog_rule)
        if not cv:
            out.append(Blocker(row["course_code"], "KREDI_ESIGI",
                               f"{cv.rule.name}: {credits_have:g}/{cv.rule.min_credits:g} kredi"
                               f" — {cv.missing:g} kredi eksik"))
    return out


def _tr_upper(text: str) -> str:
    """Türkçe büyük harf. `'önşart eksik'.upper()` → 'ÖNŞART EKSIK' (noktasız
    I) verir; başlıklarda gözle görülen bir yazım hatası. `i` → `İ` önce
    değiştirilip sonra `upper()` çağrılıyor."""
    return text.replace("i", "İ").upper()


def format_blockers(blockers: list[Blocker], n_lessons: int | None = None) -> str:
    if not blockers:
        return ""
    labels = {
        "ACILMAMIS": "bu dönem açılmamış",
        "PROGRAMA_KAPALI": "şubeleri programına kapalı",
        "ONSART": "önşart eksik",
        "ONSART_KATALOGDA_YOK": "önşartı katalogda yok",
        "KREDI_ESIGI": "kredi eşiği dolmamış",
        "ALIYORSUN": "bu dönem alıyorsun",
        "BILINMIYOR": "önşart okunamadı",
    }
    groups: dict[str, list[Blocker]] = {}
    for b in blockers:
        groups.setdefault(b.reason, []).append(b)
    out = ["", "=" * 72, "ÇAP'TA NEDEN ALAMIYORSUN", "=" * 72]
    # ★★ Faz 37 — `KREDI_ESIGI` bu listede YOKTU. Engel hesaplanıyor, sözlükte
    # etiketi duruyor, arayüz gösteriyor; `make recommend` çıktısı ise sessizce
    # düşürüyordu. Eleyen kural kendini göstermek zorunda (bkz. tasarım ilkesi)
    # — "GEO 4901E neden kayboldu" sorusunun komut satırındaki hâliydi.
    for reason in ("PROGRAMA_KAPALI", "ACILMAMIS", "ONSART",
                   "ONSART_KATALOGDA_YOK", "KREDI_ESIGI", "BILINMIYOR"):
        items = groups.get(reason)
        if not items:
            continue
        out.append(f"\n  {_tr_upper(labels[reason])} ({len(items)} ders)")
        for b in items:
            out.append(f"    {b.course:<11} {b.detail}")
    if n_lessons is not None and n_lessons < 5000:
        out.append(f"\n  ℹ️  Ders programında şu an {n_lessons} şube var. Dönem başlarında")
        out.append("      ilanlar kademeli yayınlanıyor — 'açılmamış' dersler sonradan")
        out.append("      çıkabilir. Kayıt haftasına yakın `make refresh` ile tazele.")
    supply = len(groups.get("ACILMAMIS", [])) + len(groups.get("PROGRAMA_KAPALI", []))
    if supply > len(groups.get("ONSART", [])):
        out.append("\n  ⚠️  Engelin çoğu önşart değil, ARZ: ders açılmıyor ya da")
        out.append("      şubeler başka programlara ayrılmış. Bölümle/danışmanla")
        out.append("      konuşmak, ders çalışmaktan daha çok işe yarar.")
    return "\n".join(out)


# ------------------------------------------------------------ meşgul saatler
def busy_sections(declared: Iterable[str]) -> list[Section]:
    """Ders konulamayacak saatleri, çakışma taşıyan sahte şubelere çevirir.

    ★ Yeni bir çakışma mantığı YAZMIYORUZ. `build_schedules` zaten `fixed`
    parametresiyle "bunlarla çakışan şube seçilemez" diyebiliyor (anadalda
    kayıtlı olduğun şubeler için). Okul dışı bir işi de aynı şey sayıyoruz:
    saat doluysa doludur, sebebi ders olması gerekmez.

    Ayrı bir yol yazsaydık iki çakışma tanımı olurdu ve biri düzelirken
    öbürü unutulurdu — kayıt haftasında fark edilecek türden bir hata.

    ⚠️ Bunlar SERT kısıt: çakışan şube hiç önerilmiyor. Yumuşak tercih
    ("mümkünse sabah olmasın") ayrı bir iş — bkz. yapılacaklar 2.2.
    """
    from .normalize import parse_busy

    out: list[Section] = []
    for i, raw in enumerate(declared or ()):
        b = parse_busy(str(raw))
        if b is None:
            continue                       # anlaşılmayan beyan sessizce atlanır
        out.append(Section(
            crn=f"mesgul-{i}", course=f"⛔ {b['label']}", instructor=None,
            capacity=0, enrolled=0,
            meetings=(Meeting(b["day"], b["start"], b["end"],
                              None, None, None),)))
    return out
