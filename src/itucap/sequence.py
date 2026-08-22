"""FAZ 2 çıktısı — ÇAP planının önşart sırasına göre kademelendirilmesi.

ÇAP planları dönemsizdir (D2) ve bu çiftte çift sayım yoktur (D5). Dolayısıyla
"hangi dersi ne zaman alabilirim" sorusunun tek yapısal cevabı **önşart zinciri**.
Burada planı topolojik kademelere ayırıyoruz:

    kademe 0 : önşartı olmayan / hemen alınabilir dersler
    kademe k : ancak k-1'deki dersler bittikten sonra alınabilenler

Bu, Faz 5'teki öneri motorunun "dönem yakınlığı" kriterinin yerine geçer.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Mapping

from . import prereq as P
from .rules import Status, can_take_tree, passed, prereq_view


@dataclass
class Step:
    course: str
    tier: int
    ects: float | None
    credits: float | None
    unlocks: int                      # bu ders kaç dersin önşartında geçiyor
    blockers: list[str] = field(default_factory=list)   # plan İÇİNDEKİ önkoşullar
    external: list[str] = field(default_factory=list)   # plan DIŞINDAN gerekenler
    status: str = "PENDING"           # 'DONE' | 'READY' | 'PENDING' | 'UNKNOWN'


def plan_sequence(con: sqlite3.Connection, plan_id: int,
                  grades: Mapping[str, str] | None = None) -> list[Step]:
    """Planın zorunlu derslerini önşart kademelerine ayırır."""
    grades = dict(grades or {})
    prereq_grades = prereq_view(grades)     # muafiyetler yalnız önşartta geçerli
    trees = P.parsed_trees(con)
    unlocks = P.unlock_counts(trees)
    unparsed = {r[0] for r in con.execute("SELECT course_code FROM prereq_unparsed")}

    # AKTS önce slottan, yoksa ders kataloğundan (eski taramalarda slot AKTS'si boş).
    rows = con.execute(
        """SELECT ps.course_code,
                  COALESCE(ps.ects, c.ects)       AS ects,
                  COALESCE(ps.credits, c.credits) AS credits
           FROM plan_slot ps
           LEFT JOIN course c ON c.code = ps.course_code
           WHERE ps.plan_id=? AND ps.slot_kind='REQUIRED' AND ps.course_code IS NOT NULL
           ORDER BY ps.position""", (plan_id,)).fetchall()
    in_plan = {r[0] for r in rows}

    # Kademe = plan içi önşart grafındaki en uzun yol.
    # Plan DIŞI önşartlar kademeyi belirlemez (anadalda alınmış olabilirler),
    # ama ayrıca raporlanır ki gözden kaçmasın.
    tier: dict[str, int] = {}

    def compute(course: str, seen: frozenset[str] = frozenset()) -> int:
        if course in tier:
            return tier[course]
        if course in seen:            # döngü emniyeti
            return 0
        deps = _plan_deps(trees.get(course), in_plan)
        value = 1 + max((compute(d, seen | {course}) for d in deps), default=-1)
        tier[course] = value
        return value

    steps: list[Step] = []
    for course, ects, credits in rows:
        level = compute(course)
        tree = trees.get(course)
        deps = sorted(_plan_deps(tree, in_plan))
        outside = sorted((tree.courses() - in_plan) if tree else set())

        if passed(grades.get(course)):
            status = "DONE"
        elif course in unparsed:
            status = "UNKNOWN"
        elif can_take_tree(tree, prereq_grades).status is Status.OK:
            status = "READY"
        else:
            status = "PENDING"

        steps.append(Step(course, level, ects, credits, unlocks.get(course, 0),
                          deps, outside, status))

    steps.sort(key=lambda s: (s.tier, -s.unlocks, s.course))
    return steps


def _plan_deps(tree: P.Node | None, in_plan: set[str]) -> set[str]:
    """Ağaçtaki dersler arasından plan İÇİNDE olanlar.

    OR dalında plan içi bir alternatif varsa o dal zaten sağlanabilir sayılır;
    kademelendirme için ihtiyatlı davranıp OR'un plan içi üyelerini de bağımlılık
    kabul ediyoruz (en kötü durum sıralaması).
    """
    if tree is None:
        return set()
    return tree.courses() & in_plan


def hidden_prerequisites(con: sqlite3.Connection, cap_plan_id: int,
                         anadal_plan_id: int | None) -> dict[str, list[str]]:
    """ÇAP derslerinin, HİÇBİR planda bulunmayan önşartları.

    Bu, ÇAP'ın ilan edilmemiş ek yüküdür: ne anadal planında ne ÇAP planında
    olan, ama ÇAP dersini alabilmek için gereken dersler.

    OR alternatifleri doğru ele alınır — bir dalın herhangi bir üyesi
    planlardan biriyle karşılanabiliyorsa gizli yük SAYILMAZ.
    """
    available = _plan_courses(con, cap_plan_id)
    if anadal_plan_id is not None:
        available |= _plan_courses(con, anadal_plan_id)
    # "hepsini geçeceğim" varsayımı + beyan edilen önşart muafiyetleri
    assumed = prereq_view({code: "AA" for code in available})

    trees = P.parsed_trees(con)
    out: dict[str, list[str]] = {}
    for course in sorted(_plan_courses(con, cap_plan_id, required_only=True)):
        tree = trees.get(course)
        if tree is None or tree.satisfied(assumed):
            continue
        out[course] = sorted({n.course for n in tree.missing(assumed)})
    return out


def _plan_courses(con: sqlite3.Connection, plan_id: int,
                  required_only: bool = False) -> set[str]:
    codes = {r[0] for r in con.execute(
        "SELECT course_code FROM plan_slot WHERE plan_id=? AND course_code IS NOT NULL",
        (plan_id,))}
    if required_only:
        return codes
    codes |= {r[0] for r in con.execute(
        """SELECT po.course_code FROM pool_option po
           JOIN plan_slot ps ON ps.id = po.slot_id WHERE ps.plan_id=?""", (plan_id,))}
    return codes


def format_hidden(hidden: dict[str, list[str]], con: sqlite3.Connection | None = None) -> str:
    if not hidden:
        return ("\nGİZLİ ÖN YÜK: yok — ÇAP derslerinin tüm önşartları iki planın "
                "içinden karşılanabiliyor.")
    out = ["", "=" * 72,
           "GİZLİ ÖN YÜK — hiçbir planda olmayan ama ÇAP için gereken dersler",
           "=" * 72]
    every: set[str] = set()
    for course, needs in hidden.items():
        every |= set(needs)
        out.append(f"  {course:<11} ← {', '.join(needs)}")
    out.append("")
    out.append(f"  {len(every)} farklı ders, {len(hidden)} ÇAP dersini engelliyor.")
    if con is not None:
        rows = con.execute(
            "SELECT code, name, ects FROM course WHERE code IN (%s) ORDER BY code"
            % ",".join("?" * len(every)), sorted(every)).fetchall()
        for row in rows:
            out.append(f"     {row[0]:<11} {(row[1] or '')[:40]:<42} {row[2] or 0:g} AKTS")
    out.append("  ⚠️  Bu dersleri anadal seçmeli havuzundan alabiliyorsan yük artmaz;")
    out.append("      alamıyorsan ÇAP'ın ilan edilen AKTS'sine EKLENİR. Danışmanına sor.")
    return "\n".join(out)


def format_sequence(steps: list[Step], title: str = "") -> str:
    icon = {"DONE": "✔", "READY": "▶", "PENDING": "·", "UNKNOWN": "?"}
    out: list[str] = []
    if title:
        out += [title, "=" * len(title)]
    total = sum(s.ects or 0 for s in steps)
    total_cr = sum(s.credits or 0 for s in steps)
    tiers = sorted({s.tier for s in steps})
    for level in tiers:
        group = [s for s in steps if s.tier == level]
        ects = sum(s.ects or 0 for s in group)
        cr = sum(s.credits or 0 for s in group)
        label = "plan içi önşartı yok" if level == 0 else f"{level} kademe sonra"
        out.append(f"\nKADEME {level} — {label}  "
                   f"({len(group)} ders, {cr:g} kredi / {ects:g} AKTS)")
        for step in group:
            extra = []
            if step.blockers:
                extra.append("plan içi önşart: " + ", ".join(step.blockers))
            if step.external:
                extra.append("dışarıdan: " + ", ".join(step.external[:4])
                             + (" …" if len(step.external) > 4 else ""))
            suffix = f"   [{'; '.join(extra)}]" if extra else ""
            out.append(f"  {icon.get(step.status, '·')} {step.course:<11} "
                       f"{(step.credits or 0):>4g} kr  açtığı ders: {step.unlocks:<4}{suffix}")
    out.append(f"\nToplam: {len(steps)} ders, {total_cr:g} kredi / {total:g} AKTS, "
               f"{len(tiers)} kademe")
    out.append("En kısa süre (kademe sayısı kadar dönem): "
               f"{len(tiers)} dönem — her kademeyi tek dönemde bitirirsen.")
    return "\n".join(out)
