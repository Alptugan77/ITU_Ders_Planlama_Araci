"""FAZ 10 — Denklik keşfi: "bunu zaten almışsın" demek.

Kullanıcı 21.08.2026'da şunu söyledi: *"eşliği olanlar otomatik geçildi
sayılsın, mesela ben BBF 103 aldım."*

Motor bunu Faz 2'den beri yapabiliyor (`rules.expand_with_equivalences`) ama
bir şartla: **denkliğin tanımlı olması.** D3'te ölçtük, OBS bu çift için hiç
denklik yayınlamamış. Yani mekanizma vardı, veri yoktu; kullanıcının her
denkliği elle `config/denklikler.toml`'a yazması gerekiyordu.

Bu modül eksik parçayı dolduruyor: **aday denklikleri buluyor.**

    BBF 103E  "Discrete Mathematics"  3 kredi   (aldın)
    BLG 112E  "Discrete Mathematics"  3 kredi   (ÇAP planında)
    -> aynı ad, aynı kredi

## ★ Neden otomatik UYGULAMIYORUZ

Ad eşleşmesi tek başına zayıf: katalogda "Fluid Mechanics" adını taşıyan
17 ayrı ders var (ölçüldü). Yanlış bir denkliği sessizce uygulamak, bu
projedeki en kötü hata olurdu — öğrenci tamamlamadığı bir şartı tamamlanmış
sanar, dersi almaz, mezun olamaz.

O yüzden buradaki iş **öneri**: aday bulunur, güven seviyesi hesaplanır,
gerekçesi yazılır. Uygulamak tek tık ama **kullanıcının tıkı**.

Aramayı dar tutmak da güvenliğin parçası: yalnız (a) transkriptinde geçilmiş
dersler ile (b) planlarının HENÜZ DOLMAMIŞ slotları karşılaştırılıyor. 4600
derslik katalogda kör arama yapmıyoruz.
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass

from . import rules as R
from . import student as S

# Güven seviyeleri — arayüz bunlara göre renklendiriyor ve
# "yüksek güvenlileri kabul et" düğmesi yalnız HIGH'ları alıyor.
HIGH, MEDIUM, LOW = "yuksek", "orta", "dusuk"


def normalize_name(name: str | None) -> str:
    """Ders adını karşılaştırılabilir hale getirir.

    Noktalama, çoklu boşluk ve yaygın kısaltmalar temizleniyor. Roma rakamı
    eki (I / II / III) KORUNUYOR — 'Fluid Mechanics I' ile 'Fluid Mechanics II'
    aynı ders değil ve bu ayrımı kaybetmek yanlış denklik üretirdi.
    """
    text = (name or "").lower().strip()
    text = text.replace("&", " and ")
    text = re.sub(r"[^0-9a-zçğıöşü]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


@dataclass
class Suggestion:
    source: str              # senin aldığın ders
    source_name: str
    source_grade: str
    target: str              # planındaki ders
    target_name: str
    plan_role: str           # 'ANADAL' | 'CAP' | 'YANDAL'
    confidence: str
    reasons: list[str]
    source_credits: float | None = None
    target_credits: float | None = None

    def key(self) -> tuple[str, str]:
        return (self.source, self.target)


def _course_rows(con) -> dict:
    return {r["code"]: r for r in con.execute(
        "SELECT code, name, credits, ects FROM course")}


def _open_slot_courses(con, plan_id: int, grades, equivalences) -> set[str]:
    """Planın DOLMAMIŞ slotlarındaki ders kodları (havuz seçenekleri dahil)."""
    out: set[str] = set()
    for slot in con.execute(
        "SELECT id, slot_kind, course_code FROM plan_slot WHERE plan_id=?", (plan_id,)
    ):
        if R.slot_satisfied(con, slot["id"], grades, equivalences).satisfied:
            continue
        if slot["course_code"]:
            out.add(slot["course_code"])
        out.update(r[0] for r in con.execute(
            "SELECT course_code FROM pool_option WHERE slot_id=?", (slot["id"],)))
    return {c for c in out if c}


def suggest(con: sqlite3.Connection, ucon: sqlite3.Connection, student_id: int,
            plans: list[tuple[int | None, str]]) -> list[Suggestion]:
    """Aday denklikler: aldığın ders ↔ planındaki dolmamış slot.

    `plans` = [(plan_id, rol), ...]
    """
    grades = S.grades(ucon, student_id)
    if not grades:
        return []
    equivalences = R.load_equivalences(con, ucon=ucon)
    expanded, _ = R.expand_with_equivalences(grades, equivalences)
    already = {(s, e.target) for e in equivalences for s, _g in e.sources}
    courses = _course_rows(con)

    # aldığın dersleri ada göre indeksle
    by_name: dict[str, list[str]] = {}
    for code in grades:
        row = courses.get(code)
        key = normalize_name(row["name"] if row else "")
        if len(key) >= 6:                    # 'staj' gibi kısa adlar ayırt etmiyor
            by_name.setdefault(key, []).append(code)

    out: list[Suggestion] = []
    seen: set[tuple[str, str]] = set()
    for plan_id, role in plans:
        if plan_id is None:
            continue
        for target in sorted(_open_slot_courses(con, plan_id, grades, equivalences)):
            if R.passed(expanded.get(target)):
                continue                     # zaten denklikle kazanılmış
            trow = courses.get(target)
            if trow is None:
                continue
            key = normalize_name(trow["name"])
            for source in by_name.get(key, []):
                if source == target or (source, target) in already:
                    continue
                if (source, target) in seen:
                    continue
                seen.add((source, target))
                out.append(_build(source, target, courses, grades, role))
    order = {HIGH: 0, MEDIUM: 1, LOW: 2}
    out.sort(key=lambda s: (order[s.confidence], s.target))
    return out


def _build(source, target, courses, grades, role) -> Suggestion:
    srow, trow = courses.get(source), courses.get(target)
    sc = float(srow["credits"] or 0) if srow else 0.0
    tc = float(trow["credits"] or 0) if trow else 0.0
    reasons = ["aynı ders adı"]
    confidence = MEDIUM

    if sc and tc and abs(sc - tc) < 0.01:
        reasons.append(f"aynı kredi ({sc:g})")
        confidence = HIGH
    elif sc and tc:
        reasons.append(f"kredi farklı: {sc:g} ≠ {tc:g}")
        confidence = LOW
    else:
        reasons.append("kredi bilinmiyor")
        confidence = LOW

    # ★ Aynı ders numarası güçlü bir işaret: 'MAT 210' ile 'GEO 210' gibi.
    if _number(source) and _number(source) == _number(target):
        reasons.append("aynı ders numarası")
    # Dil eki uyuşmazlığı zayıflatıcı: Türkçe ders İngilizce şubenin yerine
    # geçmeyebilir (bu projede HTA/HTAE ayrımında da aynı ilke geçerli).
    if source.endswith("E") != target.endswith("E"):
        reasons.append("dil eki farklı (biri İngilizce)")
        confidence = LOW if confidence == HIGH else confidence

    return Suggestion(
        source=source, source_name=(srow["name"] if srow else "") or "",
        source_grade=str(grades.get(source, "")),
        target=target, target_name=(trow["name"] if trow else "") or "",
        plan_role=role, confidence=confidence, reasons=reasons,
        source_credits=sc or None, target_credits=tc or None)


def _number(code: str) -> str:
    m = re.search(r"(\d{3,4})", code or "")
    return m.group(1) if m else ""


def format_suggestions(items: list[Suggestion]) -> str:
    if not items:
        return ("Aday denklik bulunamadı.\n"
                "(Transkriptindeki dersler ile planlarının açık slotları "
                "arasında ad eşleşmesi arıyoruz.)")
    labels = {HIGH: "YÜKSEK GÜVEN", MEDIUM: "ORTA GÜVEN", LOW: "DÜŞÜK GÜVEN"}
    lines = [f"DENKLİK ÖNERİLERİ ({len(items)})", ""]
    current = None
    for s in items:
        if s.confidence != current:
            current = s.confidence
            lines.append(f"— {labels[current]} —")
        lines.append(f"  {s.source:<11} → {s.target:<11} [{s.plan_role}]  "
                     f"{s.source_name[:34]}")
        lines.append(f"  {'':<11}   {', '.join(s.reasons)}")
    lines += ["", "Uygulamak için:",
              "  python -m itucap.pipeline equivalence add "
              "--target '<plandaki>' --sources '<aldığın>'",
              "ya da `make app` içindeki Denklikler panelinden tek tıkla."]
    return "\n".join(lines)
