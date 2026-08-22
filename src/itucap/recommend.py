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

import sqlite3
from dataclasses import dataclass, field
from typing import Iterable, Mapping

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

    @property
    def free(self) -> int:
        return max(0, (self.capacity or 0) - (self.enrolled or 0))

    @property
    def fill_ratio(self) -> float:
        return (self.enrolled or 0) / self.capacity if self.capacity else 1.0

    def campuses(self) -> set[str]:
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
    slot_id: int = 0          # dersin doldurduğu plan slotu
    plan_id: int = 0          # hangi planın slotu (ilerleme projeksiyonu için)
    term_no: int | None = None   # planın kaçıncı dönemi; dönemsiz planda None
    pool_label: str = ""      # ELECTIVE_POOL ise havuzun adı
    prereq_unknown: bool = False
    score: float = 0.0
    reasons: list[str] = field(default_factory=list)
    unit: str = "kredi"       # yük hangi birimden sayılıyor

    @property
    def load(self) -> float:
        """Dönem yükü — İTÜ kredisi (varsayılan) ya da AKTS."""
        return self.credits if self.unit == "kredi" else self.ects


# ------------------------------------------------------------------ yardımcı
def overlaps(a: Meeting, b: Meeting) -> bool:
    return a.day == b.day and a.start < b.end and b.start < a.end


def section_conflict(x: Section, y: Section) -> bool:
    return any(overlaps(m, n) for m in x.meetings for n in y.meetings)


def load_sections(con: sqlite3.Connection, course: str,
                  allowed_programs: set[str]) -> list[Section]:
    """Dersin, öğrencinin PROGRAM KODUYLA alabileceği şubeleri."""
    out: list[Section] = []
    for row in con.execute(
        """SELECT crn, instructor, capacity, enrolled FROM lesson WHERE course_code=?""",
        (course,),
    ):
        progs = {r[0] for r in con.execute(
            "SELECT program_code FROM lesson_allowed_program WHERE crn=?", (row[0],))}
        if progs and not (progs & allowed_programs):
            continue                       # bu şube senin programına kapalı
        meetings = tuple(
            Meeting(m[0], m[1], m[2], m[3], m[4], m[5])
            for m in con.execute(
                """SELECT lm.day_of_week, lm.start_min, lm.end_min, lm.room,
                          lm.building, b.campus
                   FROM lesson_meeting lm
                   LEFT JOIN building b ON b.code = lm.building
                   WHERE lm.crn=? ORDER BY lm.day_of_week, lm.start_min""", (row[0],))
        )
        out.append(Section(row[0], course, row[1], row[2] or 0, row[3] or 0, meetings))
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
               credit_rules: list[POL.CreditRule] | None = None
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
    equivalences = R.load_equivalences(con)
    expanded, _via = R.expand_with_equivalences(grades, equivalences)
    prereq_grades = R.prereq_view(expanded)   # muafiyetler yalnız önşartta
    trees = P.parsed_trees(con)
    unlocks = P.unlock_counts(trees)
    unparsed = {r[0] for r in con.execute("SELECT course_code FROM prereq_unparsed")}

    # ★ Kredi eşiği (bitirme çalışması). Muafiyet krediye SAYILMAZ: gerçek notlar.
    rules = POL.load_rules() if credit_rules is None else credit_rules
    have_credits = POL.earned_credits(con, grades)

    cap_steps = SEQ.plan_sequence(con, cap_plan_id, grades) if cap_plan_id else []
    critical = critical_courses([s for s in cap_steps if s.status != "DONE"])
    tier_of = {s.course: s.tier for s in cap_steps}

    out: list[Candidate] = []
    # ★ Öğrenci hangi program kodlarıyla kayıt yapabiliyorsa o kodlar geçerli
    # (HTAE + BLG + BLGE). Kardeş kod OTOMATİK türetilmez — 'HTA' ile 'HTAE'yi
    # eşitlemek İngilizce programdaki öğrenciye Türkçe şube açardı.
    allowed = {c.upper() for c in allowed_programs} or {anadal_program, cap_program}
    for plan_id, role in ((anadal_plan_id, "ANADAL"), (cap_plan_id, second_role)):
        if plan_id is None or not role:
            continue
        for slot in con.execute(
            """SELECT ps.id, ps.slot_kind, ps.course_code, ps.term_no,
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
            codes = ([slot["course_code"]] if slot["slot_kind"] == "REQUIRED"
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
                if not POL.check(code, have_credits, rules):
                    continue                      # kredi eşiği — bitirme çalışması
                sections = load_sections(con, code, allowed)
                if not sections:
                    continue
                info = con.execute(
                    "SELECT name, ects, credits FROM course WHERE code=?", (code,)).fetchone()
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
                    slot_id=slot["id"],
                    plan_id=plan_id,
                    term_no=slot["term_no"],
                    pool_label=pool_label,
                    unit=unit,
                ))
    # aynı ders iki slottan gelmişse teki kalsın (ikinci program öncelikli)
    unique: dict[str, Candidate] = {}
    for cand in out:
        if cand.course not in unique or cand.role != "ANADAL":
            unique[cand.course] = cand
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


def score_all(cands: list[Candidate]) -> list[Candidate]:
    max_unlock = max((c.unlocks for c in cands), default=1) or 1
    max_tier = max((c.tier for c in cands), default=0)
    for c in cands:
        score = 0.0
        c.reasons = []
        if c.critical:
            score += WEIGHTS["critical"]
            c.reasons.append("kritik yolda — ÇAP'ın süresini bu zincir belirliyor")
        share = c.unlocks / max_unlock
        score += WEIGHTS["unlock"] * share
        if c.unlocks:
            c.reasons.append(f"{c.unlocks} dersin önşartı")
        if c.required:
            score += WEIGHTS["required"]
        else:
            c.reasons.append("seçmeli havuzdan")
        if max_tier:
            score += WEIGHTS["early_tier"] * (max_tier - c.tier) / max_tier
        best = max((s.fill_ratio for s in c.sections), default=1.0)
        if best > 0.85:
            score += WEIGHTS["scarcity"]
            c.reasons.append("kontenjan kritik")
        if len(c.sections) == 1:
            score += WEIGHTS["scarcity"] / 2
            c.reasons.append("tek şube")
        elif len(c.sections) > DEFERRABLE_SECTIONS:
            score += WEIGHTS["deferrable"]
            c.reasons.append(f"{len(c.sections)} şube — her dönem açılıyor, ertelenebilir")
        if c.role != "ANADAL":
            score += WEIGHTS["cap_role"]
            label = "Yandal" if c.role == "YANDAL" else "ÇAP"
            c.reasons.append(f"{label} dersi — arzı kısıtlı")
        if c.prereq_unknown:
            c.reasons.append("⚠ önşartı okunamadı — danışmanına sor")
        c.score = round(score, 1)
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
    def score(self) -> float:
        return round(sum(p.candidate.score for p in self.picks), 1)

    def campus_changes(self) -> int:
        """Aynı gün içinde kampüs değiştiren ardışık ders çifti sayısı."""
        by_day: dict[int, list[tuple[int, str | None]]] = {}
        for pick in self.picks:
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


SECTION_BRANCHES = 3      # bir ders için denenecek alternatif şube sayısı
SEARCH_BUDGET = 300_000   # emniyet supabı: arama düğümü üst sınırı
POOL_FACTOR = 60          # kaç aday program toplanıp sıralanacak (limit × bu)


def build_schedules(cands: list[Candidate], max_load: float = 35.0,
                    limit: int = 3, pinned: Iterable[str] = (),
                    fixed: Iterable[Section] = ()) -> list[Schedule]:
    """Greedy + backtracking. Farklı DERS KÜMELERİ üretir, aynı kümenin
    farklı CRN varyantlarını tekrar etmez (alternatifler ayrıca raporlanır).

    ★ İKİ DÜZELTME (20.08.2026, gerçek programla karşılaştırmadan):

    1. Bir ders için TEK şube denemek yetmiyor. `BLG 351E`'nin Pazartesi şubesi
       `GEO 401E` ile çakışıyor ama Çarşamba şubesi çakışmıyor.
    2. İlk bulunan tam programı kabul etmek yetmiyor — o, saf açgözlü sonuç.
       Bir HAVUZ toplayıp toplam puana göre sıralıyoruz; böylece "şubeyi kaydırıp
       bir ders daha sığdıran" çözüm öne geçiyor."""
    pinned = {p.upper() for p in pinned}
    fixed = list(fixed)
    results: list[Schedule] = []
    seen: set[tuple[str, ...]] = set()

    # Sabit dersler (ör. anadalda zaten kayıtlı olduğun şubeler) çakışma tabanı
    def fits(section: Section, chosen: list[Pick]) -> bool:
        if any(section_conflict(section, f) for f in fixed):
            return False
        return not any(section_conflict(section, p.section) for p in chosen)

    budget = [SEARCH_BUDGET]
    pool_size = max(limit, limit * POOL_FACTOR)

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

    def pools_used(chosen: list[Pick]) -> set[int]:
        return {p.candidate.slot_id for p in chosen if p.candidate.pool_label}

    def search(index: int, chosen: list[Pick], load: float) -> None:
        if len(results) >= pool_size or budget[0] <= 0:
            return
        budget[0] -= 1
        if index >= len(cands):
            if chosen:
                key = tuple(sorted(p.candidate.course for p in chosen))
                if key not in seen:
                    seen.add(key)
                    results.append(Schedule(list(chosen)))
            return
        cand = cands[index]
        must = cand.course in pinned
        # ★ Bir seçmeli havuz slotu TEK ders ile dolar. Bu kontrol olmadan motor
        # aynı ITB havuzu için HUK 217 + HUK 218'i birlikte öneriyordu (20.08.2026).
        pool_taken = bool(cand.pool_label) and cand.slot_id in pools_used(chosen)
        if not pool_taken and load + cand.load <= max_load:
            tried = 0
            # Önce en az değer yakan şube; eşitlikte en boş olan (kontenjan riski).
            # Saati ilan edilmemiş şube hiçbir şeyle çakışmadığı için ileriye
            # bakış maliyeti 0 çıkıyor ve metriği kandırıyor. Belirsizlik avantaj
            # değil: saatli şubeler önce denenir, saatsiz olan son çare.
            ordered = sorted(cand.sections,
                             key=lambda s: (not s.meetings, blocking_cost(s, index),
                                            -s.free, s.crn))
            for section in ordered:
                if not fits(section, chosen):
                    continue
                chosen.append(Pick(cand, section))
                search(index + 1, chosen, load + cand.load)
                chosen.pop()
                tried += 1
                if tried >= SECTION_BRANCHES:
                    break
        if not must:
            search(index + 1, chosen, load)

    search(0, [], 0.0)
    if pinned:
        results = [s for s in results if pinned <= set(s.courses())]
    # Puanı en yüksek programlar; eşitlikte daha dolu ve daha az kampüs değişimi
    results.sort(key=lambda s: (-s.score, -s.load, s.campus_changes()))
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
# 'undeclared' = "İlgili Bölümce Açıklanacak" — kullanıcıya İngilizce sızmasın
def _building_label(code: str | None) -> str:
    return "belirsiz" if (code or "").lower() == "undeclared" else (code or "")


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
        rooms = {_building_label(m.building) for m in pick.section.meetings if m.building}
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
    reason: str          # 'ACILMAMIS' | 'PROGRAMA_KAPALI' | 'ONSART' | 'BILINMIYOR'
    detail: str = ""


def cap_blockers(con: sqlite3.Connection, ucon: sqlite3.Connection, student_id: int,
                 cap_plan_id: int, cap_program: str,
                 allowed_programs: Iterable[str] = ()) -> list[Blocker]:
    """Kalan her ÇAP dersi için 'neden bu dönem alamıyorum' cevabı.

    Ölçüm (18.08.2026): engelin çoğu önşart DEĞİL, **arz**. ÇAP dersleri ya bu
    dönem açılmıyor ya da şubeleri başka programlara ayrılmış oluyor.
    """
    from . import student as S

    grades = S.grades(ucon, student_id)
    taking = S.in_progress(ucon, student_id)
    equivalences = R.load_equivalences(con)
    expanded, _ = R.expand_with_equivalences(grades, equivalences)
    prereq_grades = R.prereq_view(expanded)
    trees = P.parsed_trees(con)
    unparsed = {r[0] for r in con.execute("SELECT course_code FROM prereq_unparsed")}
    rules = POL.load_rules()
    credits_have = POL.earned_credits(con, grades)

    out: list[Blocker] = []
    for row in con.execute(
        """SELECT id, course_code FROM plan_slot
           WHERE plan_id=? AND slot_kind='REQUIRED' AND course_code IS NOT NULL
           ORDER BY position""", (cap_plan_id,)
    ):
        code = row["course_code"]
        if R.slot_satisfied(con, row["id"], grades, equivalences).satisfied:
            continue
        if code in taking:
            # Engel değil, DURUM: bu dönem alıyorsun. Ayırt etmezsek 'neden
            # önerilmedi' sorusuna yanlış cevap verirdik.
            out.append(Blocker(code, "ALIYORSUN", "bu dönem programında"))
            continue
        crns = [r[0] for r in con.execute(
            "SELECT crn FROM lesson WHERE course_code=?", (code,))]
        if not crns:
            out.append(Blocker(code, "ACILMAMIS", "bu dönem hiç şube yok"))
            continue
        allowed = {c.upper() for c in allowed_programs} or {cap_program}
        if not load_sections(con, code, allowed):
            progs = sorted({r[0] for r in con.execute(
                "SELECT DISTINCT program_code FROM lesson_allowed_program WHERE crn IN (%s)"
                % ",".join("?" * len(crns)), crns)})
            out.append(Blocker(code, "PROGRAMA_KAPALI",
                               f"{len(crns)} şube var ama yalnız {', '.join(progs)} alabiliyor"))
            continue
        if code in unparsed:
            out.append(Blocker(code, "BILINMIYOR", "önşart verisi okunamadı"))
            continue
        verdict = R.can_take_tree(trees.get(code), prereq_grades)
        if verdict.status is R.Status.BLOCKED:
            missing = ", ".join(sorted({m[0] for m in verdict.missing})[:4])
            out.append(Blocker(code, "ONSART", f"eksik: {missing}"))
            continue
        # ★ Önşartı sağlansa bile mevzuat engelleyebilir (bitirme kredi eşiği).
        cv = POL.check(code, credits_have, rules)
        if not cv:
            out.append(Blocker(code, "KREDI_ESIGI",
                               f"{cv.rule.name}: {credits_have:g}/{cv.rule.min_credits:g} kredi"
                               f" — {cv.missing:g} kredi eksik"))
    return out


def format_blockers(blockers: list[Blocker], n_lessons: int | None = None) -> str:
    if not blockers:
        return ""
    labels = {
        "ACILMAMIS": "bu dönem açılmamış",
        "PROGRAMA_KAPALI": "şubeleri programına kapalı",
        "ONSART": "önşart eksik",
        "KREDI_ESIGI": "kredi eşiği dolmamış",
        "ALIYORSUN": "bu dönem alıyorsun",
        "BILINMIYOR": "önşart okunamadı",
    }
    groups: dict[str, list[Blocker]] = {}
    for b in blockers:
        groups.setdefault(b.reason, []).append(b)
    out = ["", "=" * 72, "ÇAP'TA NEDEN ALAMIYORSUN", "=" * 72]
    for reason in ("PROGRAMA_KAPALI", "ACILMAMIS", "ONSART", "BILINMIYOR"):
        items = groups.get(reason)
        if not items:
            continue
        out.append(f"\n  {labels[reason].upper()} ({len(items)} ders)")
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
