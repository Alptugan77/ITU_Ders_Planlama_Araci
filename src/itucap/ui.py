"""FAZ 6–7 — Tek dosyalık arayüz.

`make ui` -> `data/itucap.html`. Sunucu gerekmez, çift tıkla açılır.

⚠️ Bu dosya KİŞİSEL VERİ içerir (notların, ilerlemen). `data/` altında durur,
`.gitignore` kapsamındadır ve hiçbir yere gönderilmez. Paylaşma.

Tasarım notu: kayıt **kurum belgesi**. Okunmuyor, taranıyor; ama bir uygulama
panosu gibi değil, bir rapor gibi duruyor — serif başlık, lacivert cetvel,
gölgesiz yüzey, her yerde tabular rakam. İki renk sistemi ayrı tutuluyor:

* **lacivert (--seal)** = YAPI. Cetveller, başlıklar, sekmeler, tablo başları.
* **yeşil / kehribar** = VERİ. Anadal / ikinci program (ÇAP ya da yandal).

Bir renk asla öbürünün işini yapmıyor; yani lacivert bir şey hiçbir zaman
"anadal" anlamına gelmiyor.

Sayfa üç şeyi aynı anda gösteriyor: **neredesin** (ilerleme panelleri),
**bu dönem ne yaparsan ne olur** (taralı projeksiyon katmanı), **neyi neden
yapamıyorsun** (kredi eşiği + darboğaz).
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from . import config
from . import policy as POL
from . import recommend as REC
from . import rules as R
from . import sequence as SEQ
from . import student as S


def _basvuru_info(con: sqlite3.Connection, ucon: sqlite3.Connection,
                  student_id: int, settings) -> dict | None:
    """Başvurulabilirlik taraması — iki tür için de (ÇAP ve yandal).

    Kullanıcı ÇAP yapıyor olsa da yandal sorusu ayrı bir soru; ikisini de
    hesaplayıp arayüze veriyoruz, seçim kullanıcıda.
    """
    from . import basvuru as B

    try:
        exclude = {settings.anadal_program, settings.second_program}
        old, con.row_factory = con.row_factory, sqlite3.Row
        try:
            return {k: B.to_json(B.survey(con, ucon, student_id, k,
                                          exclude=exclude,
                                          anadal=settings.anadal_program))
                    for k in ("cap", "yandal")}
        finally:
            con.row_factory = old
    except Exception:                                          # noqa: BLE001
        # Tarama arayüzün ana işini engellememeli: veri eksikse bölüm gizlenir.
        return None


def _threshold_info(con: sqlite3.Connection, ucon: sqlite3.Connection,
                    student_id: int, gpa, second_kind: str,
                    cap_id: int | None) -> list[dict]:
    """GNO eşiklerini öğrencinin GERÇEK durumuna göre değerlendirir.

    Üç incelik, üçü de yanlış cevap üretmemek için:

    1. **Kapsam.** Yandal eşikleri ÇAP öğrencisine uygulanmaz. Yönergede
       ikisi ayrı maddelerde ve farklı sayılarla duruyor; hepsini birden
       göstermek, uygulanmayan bir kuralda "kaldın" demek olurdu.

    2. **Doğru sayı.** "ÇAP mezuniyeti — ikinci anadal ortalaması ≥ 2.00"
       genel GNO'yu değil, **ikinci anadal programının kendi ortalamasını**
       sorar (Madde 18). Genel GNO ile karşılaştırmak farklı bir soruya
       cevap vermek olurdu; ikinci anadal ortalaması ÇAP planındaki
       derslerden ayrıca hesaplanıyor.

    3. **Hesaplanamıyorsa iddia yok.** ÇAP planında notlu ders yoksa
       ortalama hesaplanamaz; eşik `ok=None` ile "henüz belli değil" olarak
       döner — ✗ göstermek "kaldın" demek olurdu, oysa daha başlamamış.
    """
    kinds = {"cap", "yandal"}
    scope = second_kind if second_kind in kinds else "genel"
    graded = S.graded(ucon, student_id)
    uncertain = S.uncertain_grades(ucon, student_id)

    # İkinci anadalın KENDİ ortalaması — yalnız ÇAP planındaki dersler.
    second_gpa = None
    if cap_id:
        plan_codes = {r[0] for r in con.execute(
            "SELECT DISTINCT course_code FROM plan_slot "
            "WHERE plan_id=? AND course_code IS NOT NULL", (cap_id,))}
        subset = {c: g for c, g in graded.items() if c in plan_codes}
        if subset:
            g2 = POL.gpa(con, subset, uncertain)
            if g2.counted:
                second_gpa = g2

    out = []
    for t in POL.load_thresholds(program=scope):
        against, basis = gpa.value, "genel"
        if t.key == "cap_mezuniyet_ikinci":
            if second_gpa is None:
                out.append({"key": t.key, "label": t.label, "min": t.minimum,
                            "verified": t.verified, "note": t.note,
                            "kind": t.kind, "source": t.source,
                            "basis": "ikinci anadal", "ok": None,
                            "why": "ÇAP planında notlu ders yok — "
                                   "ikinci anadal ortalaması henüz hesaplanamıyor."})
                continue
            against, basis = second_gpa.value, "ikinci anadal"
        out.append({"key": t.key, "label": t.label, "min": t.minimum,
                    "verified": t.verified, "note": t.note,
                    "kind": t.kind, "source": t.source, "basis": basis,
                    "value": against, "tolerance": t.tolerance,
                    "ok": against + 1e-9 >= t.minimum})
    return out


def collect(con: sqlite3.Connection, ucon: sqlite3.Connection, student_id: int,
            settings: config.Settings, anadal_id: int | None, cap_id: int | None,
            max_load: float | None = None, n_schedules: int = 3,
            donem: int | None = None) -> dict:
    grades = S.grades(ucon, student_id)
    equivalences = R.load_equivalences(con)
    second_role = settings.second_role or "CAP"
    second_label = settings.second_label or "ÇAP"

    panels = []
    for plan_id, role in ((anadal_id, "ANADAL"), (cap_id, second_role)):
        if plan_id is None:
            continue
        plan = con.execute("SELECT * FROM plan WHERE id=?", (plan_id,)).fetchone()
        if plan is None:
            continue                     # plan silinmiş/çekilmemiş -> panelsiz devam
        stats = R.plan_progress(con, plan_id, grades, equivalences)
        open_codes = [r[0] for r in con.execute(
            """SELECT course_code FROM plan_slot WHERE id IN (%s)
               AND course_code IS NOT NULL ORDER BY term_no IS NULL, term_no, position"""
            % ",".join("?" * len(stats["open_slots"])), stats["open_slots"])] \
            if stats["open_slots"] else []
        panels.append({
            "role": role,
            "planId": plan_id,
            "program": plan["program_code"],
            "title": plan["title"],
            "percent": stats["percent"],
            "slotsDone": stats["slots_done"], "slotsTotal": stats["slots_total"],
            "openRequired": stats["open_required"],
            "ectsDone": stats["ects_done"], "ectsTotal": stats["ects_total"],
            "creditsDone": stats["credits_done"], "creditsTotal": stats["credits_total"],
            "byCategory": [{"key": k, "done": v[0], "total": v[1]}
                           for k, v in stats["by_category"].items()],
            "remaining": open_codes,
        })

    # ★ Bulunduğun dönem: açık beyan > settings > tahmin. Hangisi olduğu
    # arayüzde yazıyor — sessiz tahmin yanlış listeye yol açardı.
    term_source = "beyan"
    if donem is None:
        donem = settings.donem or 0
    if not donem:
        donem = R.infer_term(con, anadal_id, grades, equivalences)
        term_source = "tahmin"
    limit = settings.max_load if max_load is None else max_load
    limit_credits = limit if settings.unit == "kredi" else 0.0

    def build(max_term):
        cs = REC.candidates(con, ucon, student_id, anadal_id, cap_id,
                            settings.anadal_program, settings.second_program,
                            settings.allowed_programs, settings.unit,
                            second_role=second_role, max_term=max_term)
        return cs, REC.build_schedules(cs, max_load=limit, limit=n_schedules)

    cands, schedules = build(None)
    # ★ İkinci kip: dönemlik + alttan. Ayrı bir aday havuzu ve ayrı programlar.
    term_cands, term_scheds = build(donem) if donem else ([], [])

    def section_json(sec: REC.Section) -> dict:
        return {
            "crn": sec.crn, "capacity": sec.capacity, "enrolled": sec.enrolled,
            "free": sec.free,
            "meetings": [{"day": m.day, "start": m.start, "end": m.end,
                          "building": _building(m.building), "campus": m.campus}
                         for m in sec.meetings],
        }

    names = {r[0]: r[1] for r in con.execute("SELECT code, name FROM course")}

    def schedules_json(scheds, pool):
        out = []
        for sched in scheds:
            alts = REC.alternatives(sched, pool)
            out.append({
                "ects": sched.ects, "credits": sched.credits, "load": sched.load,
                "score": sched.score,
                "campusChanges": sched.campus_changes(),
                "picks": [{
                    "course": p.candidate.course,
                    "name": names.get(p.candidate.course, ""),
                    "role": p.candidate.role,
                    "ects": p.candidate.ects, "credits": p.candidate.credits,
                    "score": p.candidate.score,
                    "reasons": p.candidate.reasons,
                    "slotId": p.candidate.slot_id, "pool": p.candidate.pool_label,
                    "section": section_json(p.section),
                    "alternatives": alts.get(p.candidate.course, []),
                } for p in sorted(sched.picks, key=lambda x: -x.candidate.score)],
            })
        return out

    def candidates_json(pool):
        return [{
            "course": c.course, "name": c.name, "role": c.role, "ects": c.ects,
            "credits": c.credits, "slotId": c.slot_id, "planId": c.plan_id,
            "termNo": c.term_no, "pool": c.pool_label,
            "score": c.score, "unlocks": c.unlocks, "critical": c.critical,
            "required": c.required, "reasons": c.reasons,
            "sections": [section_json(s) for s in c.sections],
        } for c in pool]

    schedule_json = schedules_json(schedules, cands)

    blockers = []
    if cap_id:
        blockers = [{"course": b.course, "reason": b.reason, "detail": b.detail,
                     "name": names.get(b.course, "")}
                    for b in REC.cap_blockers(con, ucon, student_id, cap_id,
                                              settings.second_program,
                                              settings.allowed_programs)]

    # ★ Kredi eşiği (bitirme çalışması) — kaç kredin var, eşik ne, NEYİ tutuyor.
    # Son madde önemli: kural sessizce eleseydi kullanıcı 'GEO 4901E neden
    # kayboldu' diye soracaktı. Eleyen kural kendini göstermek zorunda.
    rules = POL.load_rules()
    have_credits = POL.earned_credits(con, grades)
    plan_courses = {r[0] for r in con.execute(
        "SELECT DISTINCT course_code FROM plan_slot WHERE plan_id IN (?,?) "
        "AND course_code IS NOT NULL", (anadal_id or 0, cap_id or 0))}
    # ★ GNO — transkriptten TAHMİN. Kesinmiş gibi göstermemek için eksiklik
    # kaynakları ayrıca taşınıyor; eşikler doğrulanma durumuyla birlikte.
    gpa = POL.gpa(con, S.graded(ucon, student_id), S.uncertain_grades(ucon, student_id))
    gpa_info = {
        "value": gpa.value, "credits": gpa.credits, "counted": gpa.counted,
        "partial": gpa.partial,
        "noCredit": gpa.skipped_no_credit, "notGraded": gpa.skipped_not_graded,
        "uncertain": gpa.uncertain, "conditional": gpa.conditional,
        "thresholds": _threshold_info(con, ucon, student_id, gpa,
                                      settings.second_kind, cap_id),
    }
    # ★ Şartlı başarı (MADDE 20/2-b + MADDE 31/1). Faz 11'de "şart bilinmiyor"
    # deniyordu; 22.08.2026'da yönetmelikten bulundu: şart, mezuniyet anındaki
    # genel ortalamanın en az 2.00 olması. Ders TAMAMLANMIŞ sayılır.
    _cond = POL.load_conditional()
    gpa_info["conditionalRule"] = {
        "passes": _cond.passes, "minGpa": _cond.graduation_min_gpa,
        "verified": _cond.verified, "source": _cond.source,
        "ok": None if _cond.graduation_min_gpa is None
              else gpa.value + 1e-9 >= _cond.graduation_min_gpa,
    }

    # ★ Yönetmelik MADDE 17 — dönem kredi yükü. Beyan edilen tavan ile
    # yönetmelik hesabı ÇELİŞEBİLİR; sessizce ezmiyoruz, ikisini de gösteriyoruz.
    load_rule = POL.load_limit(gpa.value, second_kind=settings.second_kind)
    load_info = None
    if load_rule:
        load_info = {
            "min": load_rule.minimum, "max": load_rule.maximum,
            "exempt": load_rule.exempt_from_minimum,
            "reasons": load_rule.reasons, "verified": load_rule.verified,
            "source": load_rule.source, "declared": limit_credits,
            "conflict": bool(load_rule.maximum
                             and limit_credits > load_rule.maximum + 1e-9),
            "next": ({"max": load_rule.next_band.max_credits,
                      "minGpa": load_rule.next_band.min_gpa}
                     if load_rule.next_band else None),
        }

    credit_info = {
        "earned": have_credits,
        "unknown": POL.unknown_credit_courses(con, grades),
        "rules": [{
            "name": r.name, "min": r.min_credits, "note": r.note,
            "ok": have_credits + 1e-9 >= r.min_credits,
            "missing": round(max(0.0, r.min_credits - have_credits), 1),
            "holding": sorted(c for c in plan_courses
                              if r.matches(c) and not R.passed(grades.get(c))
                              and not POL.check(c, have_credits, [r])),
        } for r in rules],
    }

    steps = SEQ.plan_sequence(con, cap_id, grades) if cap_id else []
    tiers: dict[int, list] = {}
    for st in steps:
        tiers.setdefault(st.tier, []).append(
            {"course": st.course, "name": names.get(st.course, ""),
             "ects": st.ects or 0, "credits": st.credits or 0,
             "status": st.status, "unlocks": st.unlocks})

    return {
        "generatedAt": __import__("datetime").datetime.now().strftime("%d.%m.%Y %H:%M"),
        "term": settings.term,
        "unit": settings.unit, "unitLabel": settings.unit_label,
        "maxLoad": limit,
        "anadal": settings.anadal_program,
        "cap": settings.second_program,
        "secondRole": second_role,
        "secondLabel": second_label,
        "donem": donem,
        "donemSource": term_source,
        "credits": credit_info,
        "gpa": gpa_info,
        "load": load_info,
        "taking": sorted(S.in_progress(ucon, student_id)),
        "panels": panels,
        "candidates": candidates_json(cands),
        "schedules": schedule_json,
        # ★ Dönemlik + alttan kipi: ayrı aday havuzu, ayrı programlar.
        "modes": [
            {"key": "all", "label": "Tüm adaylar",
             "note": f"{len(cands)} aday · plandaki tüm açık dersler",
             "candidates": candidates_json(cands), "schedules": schedule_json},
            {"key": "term", "label": f"{donem}. dönem + alttan",
             "note": _term_note(term_cands, donem, second_label if cap_id else ""),
             "candidates": candidates_json(term_cands),
             "schedules": schedules_json(term_scheds, term_cands)},
        ] if donem else [],
        "blockers": blockers,
        # ★ FAZ 12 — "başvurabilir miyim" (yapılacaklar 1.3).
        "basvuru": _basvuru_info(con, ucon, student_id, settings),
        "tiers": [{"tier": t, "courses": v} for t, v in sorted(tiers.items())],
        "lessonCount": con.execute("SELECT COUNT(*) FROM lesson").fetchone()[0],
        "uncertain": S.uncertain_grades(ucon, student_id),
    }


def _building(code: str | None) -> str:
    return "belirsiz" if (code or "").lower() == "undeclared" else (code or "")


def _term_note(cands: list[REC.Candidate], donem: int, second_label: str) -> str:
    """Kip başlığının altındaki açıklama — kaç ders nereden geliyor.

    Sayıyı dökmezsek '76 aday' ile '78 aday' arasındaki farkın ne olduğu
    anlaşılmıyor ve kip işe yaramıyor gibi duruyor."""
    now = sum(1 for c in cands if c.term_no == donem)
    below = sum(1 for c in cands if c.term_no is not None and c.term_no < donem)
    free = sum(1 for c in cands if c.term_no is None)
    parts = [f"{now} dönemlik ({donem}. dönem)", f"{below} alttan (1–{donem - 1}. dönem)"]
    if free:
        parts.append(f"{free} {second_label or 'ikinci program'} — planı dönemsiz, hepsi kalır")
    return " · ".join(parts)


def render(data: dict) -> str:
    return _TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=False))


def write(data: dict, dest: Path | None = None) -> Path:
    dest = dest or config.DATA_DIR / "itucap.html"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(render(data), encoding="utf-8")
    return dest


_TEMPLATE = r"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ÇAP Panosu</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Chivo:wght@600;700;800;900&family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<style>
/* ---------------------------------------------------------------------------
   GECE ŞEMASI — "Şematik" ile "Gece"nin melezi (kullanıcı seçimi 22.08.2026).
   İsviçre şemasının disiplini, gece zemininde.

   ŞEMATİK'ten gelen (yapı):
     * sıfır köşe — hiçbir yerde yuvarlaklık yok
     * kutu yerine CETVEL: kartın kenarlığı değil, altındaki çizgi bölüyor
     * gölge yok, degrade yok — tamamen düz
     * başlıklar Chivo 800/900, BÜYÜK HARF, sıkı harf aralığı
     * ızgarada dönüşümlü çizgi ağırlığı: saat başları kalın, yarımlar ince

   GECE'den gelen (zemin ve sıcaklık):
     * koyu ama yumuşak zemin (#10141B) — saf siyah değil, mavi eğilimli
     * düşük kontrast gövde metni; kayıt haftasında saatlerce bakılıyor
     * tek aksan: periwinkle (--seal). Şematik'in çığlık kırmızısı yerine
       yalnız MEVZUAT çakışmasında kullanılan yumuşatılmış bir kırmızı.

   ★ Renk rolleri değişmedi — değişmemeliydi:
     --seal   YAPISAL: cetveller, bölüm etiketleri, tablo başlıkları, seçili sekme
     --anadal / --cap  VERİ: anadal / ikinci program. Dekorasyon değil, bilgi.
     --danger yalnız mevzuat çelişkisi.
   Karıştırmak, rengin taşıdığı bilgiyi yok ederdi.

   Bu tasarım KOYU doğar: :root koyu paletidir. Işık modu Şematik'in kendi
   dünyasına yaklaşır (beyaz zemin, sert siyah cetvel) — aynı yapı, iki zemin.
--------------------------------------------------------------------------- */
:root{
  --ground:#10141B; --surface:#161B24; --surface-2:#1E242F;
  --border:#262E3A; --border-strong:#414C60;
  --ink:#E4E9F2; --ink-2:#9AA5B8; --ink-3:#6C7688;
  --seal:#8FA3E8; --seal-soft:#1A2036;
  --anadal:#5FC0A6; --anadal-soft:#123029; --anadal-ink:#8FD8C3;
  --cap:#D9A05B; --cap-soft:#2E2415; --cap-ink:#EFC48E;
  --danger:#E0836F; --warn:#D9B061;
  --shadow:0 18px 44px -20px rgba(0,0,0,.85);
  --r:0px;
}
:root:not([data-theme="dark"]){
  @media (prefers-color-scheme:light){
    --ground:#FFFFFF; --surface:#FFFFFF; --surface-2:#F0F2F6;
    --border:#D4D9E2; --border-strong:#141821;
    --ink:#0D1017; --ink-2:#4B5462; --ink-3:#727C8C;
    --seal:#3B4E9E; --seal-soft:#E7EAF7;
    --anadal:#0A6B58; --anadal-soft:#D6EBE5; --anadal-ink:#074A3D;
    --cap:#8A5210; --cap-soft:#F6E7D2; --cap-ink:#633B08;
    --danger:#C02D18; --warn:#7A5709;
    --shadow:0 18px 44px -26px rgba(10,15,30,.5);
  }
}
:root[data-theme="light"]{
  --ground:#FFFFFF; --surface:#FFFFFF; --surface-2:#F0F2F6;
  --border:#D4D9E2; --border-strong:#141821;
  --ink:#0D1017; --ink-2:#4B5462; --ink-3:#727C8C;
  --seal:#3B4E9E; --seal-soft:#E7EAF7;
  --anadal:#0A6B58; --anadal-soft:#D6EBE5; --anadal-ink:#074A3D;
  --cap:#8A5210; --cap-soft:#F6E7D2; --cap-ink:#633B08;
  --danger:#C02D18; --warn:#7A5709;
  --shadow:0 18px 44px -26px rgba(10,15,30,.5);
}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);
  font:400 15px/1.6 "IBM Plex Sans",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  -webkit-font-smoothing:antialiased}
.mono{font-family:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,monospace;
  font-variant-numeric:tabular-nums}
.wrap{max-width:1180px;margin:0 auto;padding:32px 22px 80px;display:flex;
  flex-direction:column;gap:30px}
/* Chivo, ağır ve büyük harf — Şematik'in sesi. Gövde IBM Plex Sans'ta kalıyor;
   Chivo'yu uzun metinde kullanmak gece zemininde yorucu olurdu. */
h1,h2,h3{margin:0;text-wrap:balance;
  font-family:"Chivo",Helvetica,Arial,sans-serif;font-weight:800;
  text-transform:uppercase}
h1{font-size:29px;letter-spacing:-.02em;line-height:1.1;font-weight:900}
h2{font-size:15px;letter-spacing:.02em;font-weight:800}
.eyebrow{font-size:10.5px;font-weight:700;letter-spacing:.16em;text-transform:uppercase;
  color:var(--seal);font-family:"Chivo",Helvetica,Arial,sans-serif}
/* Belge başlığı: kalın yapısal cetvel + ince alt cetvel. */
header{padding-bottom:16px;border-bottom:1px solid var(--border)}
header .masthead{display:flex;flex-wrap:wrap;align-items:flex-end;
  justify-content:space-between;gap:16px;
  padding-bottom:14px;border-bottom:3px solid var(--seal);margin-bottom:4px}
header .sub{color:var(--ink-2);font-size:13.5px;margin-top:6px}
button{font:inherit;color:inherit;background:none;border:0;cursor:pointer}
.ghost{border:1px solid var(--border-strong);border-radius:var(--r);padding:6px 13px;
  font-size:12px;background:transparent;font-weight:600;letter-spacing:.05em;
  text-transform:uppercase;font-family:"Chivo",Helvetica,Arial,sans-serif}
.ghost:hover{background:var(--seal-soft);border-color:var(--seal);color:var(--seal)}
:focus-visible{outline:2px solid var(--seal);outline-offset:2px;border-radius:0}
/* Şematik: kutu değil cetvel. Kart, üstündeki kalın çizgiyle bölünüyor;
   kenarlık yalnız hafif bir hat olarak kalıyor. */
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--r)}
.pad{padding:20px 22px}
/* Bölüm başlığı: büyük harf etiket + sona kadar uzanan yapısal cetvel */
.sechead{display:flex;align-items:center;gap:12px;margin-bottom:2px}
.sechead .rule{flex:1;height:2px;background:var(--border-strong);opacity:.55}

.panels{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:18px}
.panel{border-top:6px solid var(--accent)}
.panel[data-role="ANADAL"]{--accent:var(--anadal);--soft:var(--anadal-soft)}
.panel[data-role="CAP"],.panel[data-role="YANDAL"]{--accent:var(--cap);--soft:var(--cap-soft)}
.panel .top{display:flex;align-items:baseline;gap:10px;justify-content:space-between}
.panel .pct{font-family:"IBM Plex Mono",monospace;font-variant-numeric:tabular-nums;
  font-size:27px;font-weight:600;color:var(--accent);letter-spacing:-.03em}
.panel .name{color:var(--ink-2);font-size:12.5px;margin:3px 0 15px}

/* ★ İki katmanlı ölçek: dolu = geçilmiş, taralı = bu dönem seçili.
   'Bu dönemi bitirirsen nerede olursun' sorusunun görsel cevabı. */
.meter{height:10px;background:var(--surface-2);border:1px solid var(--border);
  border-radius:0;overflow:hidden;display:flex}
.meter i{display:block;height:100%;background:var(--accent)}
.meter i.plan{background:repeating-linear-gradient(135deg,
  var(--accent) 0 3px,transparent 3px 6px);opacity:.72}
.proj{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px;margin-top:9px;
  font-size:12.5px;color:var(--ink-2);min-height:19px}
.proj .arrow{color:var(--ink-3)}
.proj b{color:var(--accent);font-weight:600}
.proj .flat{color:var(--ink-3)}
.stats{display:flex;flex-wrap:wrap;gap:16px;margin-top:11px;font-size:13px;
  color:var(--ink-2);padding-top:11px;border-top:1px solid var(--border)}
.stats b{color:var(--ink);font-weight:600}
.stats .gain{color:var(--accent);font-weight:600}
.cats{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}
.cat{font-size:11px;padding:3px 8px;border:1px solid var(--border);border-radius:0;
  background:var(--soft);color:var(--accent);font-weight:600;letter-spacing:.02em}
.cat.zero{background:transparent;color:var(--ink-3)}

.tabs{display:flex;gap:0;flex-wrap:wrap;border:1px solid var(--border);
  border-radius:var(--r);overflow:hidden;background:var(--surface)}
.tab{border:0;border-left:1px solid var(--border);background:transparent;
  padding:8px 15px;font-size:11.5px;color:var(--ink-2);font-weight:600;
  letter-spacing:.06em;text-transform:uppercase;
  font-family:"Chivo",Helvetica,Arial,sans-serif}
.tab:first-child{border-left:0}
/* Seçili sekme: zemin --seal, yazı --ground. İkisi de temaya göre dönüyor,
   yani üç durumun (açık / koyu / sistem) hepsinde kontrast korunuyor —
   sabit #fff yazsaydık koyu temada mavi üstünde beyaz kalırdı. */
.tab[aria-selected="true"]{background:var(--seal);color:var(--ground);font-weight:800}

/* Kip anahtarı — 'tüm adaylar' / 'dönemlik + alttan' */
.modes{display:flex;gap:0;flex-wrap:wrap;border:1px solid var(--border-strong);
  border-radius:var(--r);overflow:hidden;background:var(--surface)}
.modebtn{padding:6px 14px;font-size:13px;color:var(--ink-2);
  border-left:1px solid var(--border)}
.modebtn:first-child{border-left:0}
.modebtn[aria-pressed="true"]{background:var(--seal-soft);color:var(--seal);font-weight:600}
.modenote{font-size:12px;color:var(--ink-3);margin-top:7px}

/* ---------- kurulum şeridi (Faz 8) ---------- */
.setupbar{display:flex;flex-wrap:wrap;gap:10px;align-items:center;
  padding:11px 14px;border:1px solid var(--border);border-left:3px solid var(--seal);
  border-radius:var(--r);background:var(--surface)}
.setupbar .who{font-size:13px;color:var(--ink-2);margin-right:auto}
.setupbar .who b{color:var(--ink);font-weight:600}
.setupbar .ro{font-size:12px;color:var(--ink-3)}
.ghost[disabled]{opacity:.45;cursor:not-allowed}
.ghost.primary{background:var(--seal);color:var(--ground);border-color:var(--seal);
  font-weight:600}
.ghost.primary:hover{opacity:.9;background:var(--seal)}

/* form öğeleri */
.field{display:block;margin-top:12px}
.field>span{display:block;font-size:10.5px;font-weight:600;letter-spacing:.11em;
  text-transform:uppercase;color:var(--seal);margin-bottom:5px}
.field .hint{font-size:12px;color:var(--ink-3);margin-top:4px;letter-spacing:0;
  text-transform:none;font-weight:400}
select,input[type=text],input[type=search],textarea{
  font:inherit;font-size:13.5px;width:100%;padding:7px 9px;color:var(--ink);
  background:var(--surface);border:1px solid var(--border-strong);border-radius:0}
textarea{font-family:"IBM Plex Mono",monospace;font-size:12.5px;min-height:130px;
  resize:vertical}
select:focus,input:focus,textarea:focus{outline:2px solid var(--seal);outline-offset:1px}
.radios{display:flex;gap:0;border:1px solid var(--border-strong);border-radius:0;
  overflow:hidden}
.radios button{flex:1;padding:7px 10px;font-size:13px;color:var(--ink-2);
  border-left:1px solid var(--border)}
.radios button:first-child{border-left:0}
.radios button[aria-pressed="true"]{background:var(--seal-soft);color:var(--seal);
  font-weight:600}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px}
.dlgactions{display:flex;gap:8px;justify-content:flex-end;align-items:center;
  margin-top:18px;padding-top:14px;border-top:1px solid var(--border)}
.dlgactions .msg{margin-right:auto;font-size:12.5px;color:var(--ink-2)}
.dlgactions .msg.bad{color:var(--danger)}
.terms{display:flex;flex-wrap:wrap;gap:6px}
.terms button{width:42px;padding:7px 0;text-align:center;font-size:13px;
  border:1px solid var(--border-strong);border-radius:0;color:var(--ink-2)}
.terms button[aria-pressed="true"]{background:var(--seal);color:var(--ground);
  border-color:var(--seal);font-weight:600}

/* plandan tikleme */
.ckterm{margin-bottom:10px}
.cktermhead{font-size:10.5px;font-weight:600;letter-spacing:.11em;
  text-transform:uppercase;color:var(--seal);padding:8px 0 4px;
  border-bottom:1px solid var(--border);margin-bottom:4px}
.ckrow{display:flex;align-items:center;gap:9px;padding:4px 2px;font-size:13px;
  border-radius:0;cursor:pointer}
.ckrow:hover{background:var(--surface-2)}
.ckrow input{width:15px;height:15px;accent-color:var(--seal);cursor:pointer}
.ckcode{min-width:74px;font-weight:600}
.ckname{flex:1;color:var(--ink-3);font-size:12px;overflow:hidden;
  text-overflow:ellipsis;white-space:nowrap}
.ckcr{color:var(--ink-3);font-size:12px;min-width:24px;text-align:right}
.ckrow select{width:auto;min-width:78px;padding:2px 5px;font-size:12.5px}
.ckrow select:disabled{opacity:.35}

/* transkript tablosu */
.trtable{width:100%;border-collapse:collapse;font-size:13px}
.trtable th{text-align:left;font-size:10.5px;letter-spacing:.11em;text-transform:uppercase;
  color:var(--seal);font-weight:600;padding:0 8px 6px 0;
  border-bottom:1px solid var(--border-strong)}
.trtable td{padding:5px 8px 5px 0;border-top:1px solid var(--border);vertical-align:middle}
.trtable select{width:auto;min-width:74px;padding:3px 6px;font-size:12.5px}
.trtable .rm{color:var(--danger);font-size:12px;padding:2px 6px;
  border:1px solid var(--border);border-radius:0}
.scroll{max-height:290px;overflow-y:auto;margin-top:10px}
.hits{border:1px solid var(--border);border-radius:0;margin-top:6px;
  max-height:190px;overflow-y:auto}
.hit{display:flex;justify-content:space-between;gap:10px;width:100%;text-align:left;
  padding:6px 9px;font-size:13px;border-bottom:1px solid var(--border)}
.hit:last-child{border-bottom:0}
.hit:hover{background:var(--surface-2)}
.hit .meta{color:var(--ink-3);font-size:11.5px}

/* Kredi eşiği kutusu */
.gauge{display:flex;flex-wrap:wrap;gap:18px;align-items:center}
.gaugebar{flex:1;min-width:190px}
.gaugebar .track{height:9px;background:var(--surface-2);border:1px solid var(--border);
  border-radius:0;overflow:hidden}
.gaugebar .track i{display:block;height:100%;background:var(--seal)}
.gaugebar .track i.ok{background:var(--anadal)}
.gaugelabel{font-size:12.5px;color:var(--ink-2);margin-top:6px}
.summary{display:flex;flex-wrap:wrap;gap:14px;align-items:center;font-size:13px;
  color:var(--ink-2);margin-top:2px}
.summary .over{color:var(--danger);font-weight:600}
.dot{display:inline-flex;align-items:center;gap:6px}
.dot i{width:9px;height:9px;border-radius:0;display:block}
.toolbar{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-top:10px}
.toolbar .hint{font-size:12px;color:var(--ink-3)}

.gridwrap{overflow-x:auto}
/* Dar ekran düzeni (yapılacaklar 4.1). Izgara 660px'in altına inemiyor;
   telefonda yerini gün gün dikey liste alıyor. Aynı veri, başka biçim.
   ★ Listenin bilinen zayıflığı çakışmayı göstermemesi — o yüzden çakışma
   burada AYRICA hesaplanıp işaretleniyor. */
.daylist{display:none;grid-template-columns:1fr;gap:14px}
.daylist section{display:flex;flex-direction:column;gap:6px}
.daylist h3{font-size:10.5px;letter-spacing:.16em;color:var(--seal);
  padding-bottom:6px;border-bottom:2px solid var(--border-strong)}
.daylist .row{display:flex;justify-content:space-between;gap:10px;align-items:baseline;
  width:100%;text-align:left;padding:11px 12px;background:var(--soft);
  color:var(--accent-ink);border-left:5px solid var(--accent);font-size:13.5px}
.daylist .row[data-role="ANADAL"]{--accent:var(--anadal);--soft:var(--anadal-soft);--accent-ink:var(--anadal-ink)}
.daylist .row[data-role="CAP"],.daylist .row[data-role="YANDAL"]{--accent:var(--cap);--soft:var(--cap-soft);--accent-ink:var(--cap-ink)}
.daylist .row small{color:var(--ink-2);font-size:11.5px;display:block}
.daylist .row.clash{border-left-color:var(--danger);
  box-shadow:inset 0 0 0 1px var(--danger)}
.daylist .none{color:var(--ink-3);font-size:12.5px;padding:6px 0}
.daylist .warn{color:var(--danger);font-weight:600;font-size:11px;
  letter-spacing:.06em;text-transform:uppercase;
  font-family:"Chivo",Helvetica,Arial,sans-serif}
@media (max-width:700px){
  .gridwrap{display:none}
  .daylist{display:grid}
  .wrap{padding:20px 14px 60px;gap:22px}
  h1{font-size:23px}
  .pad{padding:15px 14px}
  .panels{gap:12px}
  /* Dokunma hedefleri: 44px kuralı */
  .ghost,.tab{min-height:40px;display:inline-flex;align-items:center}
  .tiers{gap:8px}
  /* Aday tablosu 6 sütunla telefona sığmıyordu; kutusunun içinde yana
     kayıyordu ama asıl iş burada yapılıyor — kaydırarak kullanılmamalı.
     Plan ve AKTS sütunları düşüyor: rol zaten ders hücresindeki etikette,
     AKTS karar için kritik değil. Satıra dokununca hepsi diyalogda. */
  table.list th:nth-child(3),table.list td:nth-child(3),
  table.list th:nth-child(5),table.list td:nth-child(5){display:none}
  table.list{font-size:13px}
  table.list td{padding:11px 8px 11px 0}
}
table.grid{border-collapse:collapse;width:100%;min-width:660px;table-layout:fixed}
table.grid th{font-size:10.5px;font-weight:700;letter-spacing:.16em;text-transform:uppercase;
  color:var(--seal);padding:0 0 8px;text-align:left;border-bottom:3px solid var(--seal);
  font-family:"Chivo",Helvetica,Arial,sans-serif}
table.grid th:first-child{width:58px}
table.grid td{height:19px;padding:0 2px;vertical-align:top}
table.grid tr.hr>td{border-top:1px solid var(--border-strong);opacity:1}
table.grid tr.half>td{border-top:1px dotted var(--border)}
table.grid td.hour{border:0!important;color:var(--ink-3);font-size:11.5px;padding-top:2px}
table.grid td.free{cursor:pointer}
table.grid td.free:hover{background:var(--surface-2);
  box-shadow:inset 0 0 0 1px var(--border-strong)}
.blk{border-radius:0;padding:4px 7px;font-size:12px;line-height:1.3;height:100%;
  cursor:pointer;border-left:5px solid var(--accent);background:var(--soft);
  color:var(--accent-ink);overflow:hidden}
.blk[data-role="ANADAL"]{--accent:var(--anadal);--soft:var(--anadal-soft);--accent-ink:var(--anadal-ink)}
.blk[data-role="CAP"],.blk[data-role="YANDAL"]{--accent:var(--cap);--soft:var(--cap-soft);--accent-ink:var(--cap-ink)}
.blk b{display:block;font-weight:600}
.blk small{color:var(--ink-2);font-size:11px}
.empty{color:var(--ink-3);font-size:12px;padding:24px 0;text-align:center}

table.list{width:100%;border-collapse:collapse;font-size:13.5px}
table.list th{text-align:left;font-size:10.5px;letter-spacing:.16em;text-transform:uppercase;
  color:var(--seal);font-weight:700;padding:0 10px 8px 0;
  border-bottom:3px solid var(--seal);font-family:"Chivo",Helvetica,Arial,sans-serif}
table.list td{padding:9px 10px 9px 0;border-top:1px solid var(--border);vertical-align:top}
table.list tr:hover td{background:var(--surface-2)}
.tag{font-size:10px;font-weight:700;padding:2px 7px;border-radius:0;
  letter-spacing:.08em;text-transform:uppercase;
  font-family:"Chivo",Helvetica,Arial,sans-serif}
.tag.ANADAL{background:var(--anadal-soft);color:var(--anadal-ink)}
.tag.CAP,.tag.YANDAL{background:var(--cap-soft);color:var(--cap-ink)}
.why{color:var(--ink-3);font-size:12px;margin-top:3px}
.score{font-weight:600}

.chipline{display:flex;align-items:center;gap:9px;margin:16px 0 8px}
.chip{font-size:10.5px;font-weight:600;padding:3px 9px;border-radius:0;
  letter-spacing:.05em;text-transform:uppercase;border:1px solid currentColor}
.chip.supply{color:var(--danger)}
.chip.prereq{color:var(--warn)}
.chip.credit{color:var(--seal)}
.chip.unknown{color:var(--ink-3)}
.chip.edited{color:var(--cap)}
.blocklist{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:6px}
.blockitem{font-size:12.5px;color:var(--ink-2);padding:7px 10px;border-radius:0;
  background:var(--surface-2);border:1px solid var(--border)}
.blockitem b{color:var(--ink);font-weight:600}
.note{font-size:12.5px;color:var(--ink-2);background:var(--surface-2);
  border-radius:0;padding:11px 14px;border-left:3px solid var(--warn)}

.opt{display:flex;justify-content:space-between;gap:10px;align-items:baseline;width:100%;
  text-align:left;padding:8px 10px;border-radius:0;border:1px solid var(--border);
  background:var(--surface);font-size:13px}
.opt:hover{background:var(--surface-2)}
.opt .meta{color:var(--ink-3);font-size:11.5px}
.optlist{display:flex;flex-direction:column;gap:6px;margin-top:10px;
  max-height:320px;overflow-y:auto}
.danger{color:var(--danger);border-color:currentColor}

.tiers{display:flex;gap:10px;overflow-x:auto;padding-bottom:4px}
.tier{min-width:158px;flex:1}
.tier h3{font-size:10.5px;color:var(--seal);font-weight:700;margin-bottom:8px;
  letter-spacing:.16em;text-transform:uppercase;
  font-family:"Chivo",Helvetica,Arial,sans-serif;
  padding-bottom:6px;border-bottom:2px solid var(--border-strong)}
.tier ul{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:4px}
.tier li{font-size:12px;padding:5px 8px;border-radius:0;background:var(--surface-2);
  border:1px solid var(--border);display:flex;justify-content:space-between;gap:6px}
.tier li[data-s="DONE"]{opacity:.5;text-decoration:line-through}
.tier li[data-s="READY"]{background:var(--cap-soft);color:var(--cap-ink);font-weight:600;
  border-color:var(--cap)}

dialog{border:1px solid var(--border-strong);border-top:6px solid var(--seal);
  border-radius:var(--r);background:var(--surface);
  color:var(--ink);max-width:540px;width:calc(100% - 32px);padding:0;box-shadow:var(--shadow)}
dialog::backdrop{background:rgba(8,16,26,.5)}
dialog .pad{padding:22px 24px}
footer{color:var(--ink-3);font-size:12px;border-top:3px solid var(--seal);padding-top:14px;
  line-height:1.7}
@media (prefers-reduced-motion:no-preference){
  .blk,.tab,.ghost,.opt{transition:background .12s ease,color .12s ease}
}
</style>
</head>
<body>
<div class="wrap">
<header>
  <div class="masthead">
    <div>
      <div class="eyebrow" id="eyebrow"></div>
      <h1 id="doctitle">Ders Planlama Raporu</h1>
    </div>
    <button class="ghost" id="theme">Tema</button>
  </div>
  <div class="sub" id="subtitle"></div>
</header>

<section class="setupbar" id="setupbar"></section>

<section class="panels" id="panels"></section>

<section class="card pad" id="creditSection" hidden>
  <div class="sechead"><div class="eyebrow">Mevzuat kısıtı</div><div class="rule"></div></div>
  <h2 style="margin-bottom:14px">Kredi ve not eşikleri</h2>
  <div id="gpaBody"></div>
  <div id="loadBody"></div>
  <div id="creditBody"></div>
</section>

<section class="card pad" id="suggestSection" hidden>
  <div class="sechead"><div class="eyebrow">Denklik</div><div class="rule"></div></div>
  <h2>Bunu zaten almış olabilirsin</h2>
  <div class="summary">Transkriptindeki dersler ile planlarının <b>dolmamış</b>
    slotları arasında ad eşleşmesi arandı. Uygulamak senin onayınla —
    yanlış bir denklik, tamamlamadığın bir şartı tamamlanmış gösterirdi.</div>
  <div id="suggestBody" style="margin-top:12px"></div>
</section>

<section class="card pad" id="changeSection" hidden>
  <div class="sechead"><div class="eyebrow">Son tazelemeden beri</div><div class="rule"></div></div>
  <div style="display:flex;flex-wrap:wrap;gap:14px;justify-content:space-between;
              align-items:flex-end">
    <div><h2>Ne değişti</h2><div class="modenote" id="changeWhen"></div></div>
    <button class="ghost" id="refreshBtn" hidden>Veriyi tazele</button>
  </div>
  <div id="changeBody" style="margin-top:12px"></div>
</section>

<section class="card pad">
  <div class="sechead"><div class="eyebrow">Bu dönem</div><div class="rule"></div></div>
  <div style="display:flex;flex-wrap:wrap;gap:14px;justify-content:space-between;
              align-items:flex-end;margin-bottom:4px">
    <div>
      <h2>Haftalık program</h2>
      <div class="modes" id="modes" style="margin-top:10px"></div>
      <div class="modenote" id="modeNote"></div>
    </div>
    <div class="tabs" id="tabs"></div>
  </div>
  <div class="summary" id="schedSummary"></div>
  <div class="toolbar">
    <span id="editState" class="chip edited" hidden>değiştirildi</span>
    <button class="ghost primary" id="savePicks" hidden>Programı kaydet</button>
    <button class="ghost" id="reset" hidden>Öneriye dön</button>
    <button class="ghost" id="crnBtn">CRN listesi</button>
    <span id="savedMark" class="chip" style="color:var(--anadal)" hidden></span>
    <span class="hint">Derse tıkla → şube değiştir, yerine başka ders koy, çıkar
      &nbsp;·&nbsp; Boş hücreye tıkla → o saate uyan dersler</span>
  </div>
  <div class="gridwrap" style="margin-top:14px"><table class="grid" id="grid"></table></div>
  <!-- Dar ekranda ızgaranın yerini alır. Aynı veriden kuruluyor; ızgara
       yana kaydırma istediği için telefonda kullanışsızdı (yapılacaklar 4.1). -->
  <div class="daylist" id="daylist" style="margin-top:14px"></div>
  <div id="notime" style="margin-top:14px"></div>
</section>

<section class="card pad">
  <div class="sechead"><div class="eyebrow">Sıralama</div><div class="rule"></div></div>
  <h2>Aday dersler</h2>
  <div class="summary">Puan; kritik yol, kaç dersi açtığı, zorunluluk, kontenjan
    ve kademeden hesaplanır. Satıra tıklayıp programa ekleyebilirsin.</div>
  <div style="overflow-x:auto;margin-top:12px">
    <table class="list" id="cands">
      <thead><tr><th>Puan</th><th>Ders</th><th>Plan</th><th>Kredi</th><th>AKTS</th>
        <th>Şube</th></tr></thead>
      <tbody></tbody>
    </table>
  </div>
</section>

<section class="card pad" id="blockSection">
  <div class="sechead"><div class="eyebrow">Darboğaz</div><div class="rule"></div></div>
  <h2 id="blockTitle">İkinci programda neden alamıyorsun</h2>
  <div id="blockers"></div>
</section>

<!-- FAZ 12 — "başvurabilir miyim" (yapılacaklar 1.3) -->
<section class="card pad" id="basvuruSection" hidden>
  <div class="sechead"><div class="eyebrow">Başvuru</div><div class="rule"></div></div>
  <h2>Başvurabilir miyim</h2>
  <div class="summary">Yönergedeki şartlar senin durumunla karşılaştırılıyor.
    Karar mercii bölümün — bu ekran hazırlık içindir.</div>
  <div class="tabs" id="basvuruTabs" role="tablist" style="margin-top:12px"></div>
  <div id="basvuruBody"></div>
</section>

<section class="card pad">
  <div class="sechead"><div class="eyebrow">Önşart zinciri</div><div class="rule"></div></div>
  <h2 id="tierTitle">Kademeler</h2>
  <div class="summary">Her kademe en az bir dönem. Kademe sayısı, ikinci programı
    bitirebileceğin en kısa süredir.</div>
  <div class="tiers" id="tiers" style="margin-top:14px"></div>
</section>

<footer>
  Bu araç bilgilendirme amaçlıdır; ders kayıt kararların için danışmanına ve OBS'ye danış.
  Veriler <span id="gen" class="mono"></span> itibarıyladır.
  Bu dosya notlarını içerir — paylaşma.
</footer>
</div>

<dialog id="detail"><div class="pad" id="detailBody"></div></dialog>
<dialog id="setup"><div class="pad" id="setupBody"></div></dialog>

<script>
const DATA = __DATA__;
const DAYS = ["Pzt","Sal","Çar","Per","Cum"];
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, c =>
  ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const hhmm = (m) => String(Math.floor(m/60)).padStart(2,"0")+":"+String(m%60).padStart(2,"0");

let LBL = DATA.secondLabel || "ÇAP";
function renderHeader(){
  LBL = DATA.secondLabel || "ÇAP";
  $("#eyebrow").textContent = `${DATA.anadal}${DATA.cap ? ` + ${DATA.cap} ${LBL}` : ""}`
    + (DATA.term ? ` · ${DATA.term}` : "");
  $("#doctitle").textContent = DATA.cap ? `${LBL} Ders Planlama Raporu`
                                        : "Ders Planlama Raporu";
  $("#blockTitle").textContent = `${LBL}'ta neden alamıyorsun`;
  $("#tierTitle").textContent = `${LBL} kademeleri`;
  $("#gen").textContent = DATA.generatedAt;
  $("#subtitle").textContent =
    `${DATA.lessonCount} açık şube · dönem yükü sınırı ${DATA.maxLoad} ${DATA.unitLabel}` +
    (DATA.donem ? ` · ${DATA.donem}. dönem (${DATA.donemSource})` : "");
}

$("#theme").addEventListener("click", () => {
  const cur = document.documentElement.getAttribute("data-theme");
  const dark = cur ? cur === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  document.documentElement.setAttribute("data-theme", dark ? "light" : "dark");
});

/* ================= KURULUM: program · dönem · geçilen dersler =================
   Faz 8. Bu üç şey aracın en çok kullanılan işlemleri ama en zor işlemiydi —
   dosya düzenlemek gerekiyordu. Artık sayfadan yapılıyor.

   ★ `make ui` (statik dosya) ile açıldığında DATA.live yok: paneller salt
   okunur görünür ve nedenini yazar. Sunucusuz sahte bir "kaydet" düğmesi
   göstermek, kaydetmediğini gizlemek olurdu. */
let LIVE = !!DATA.live;
let SETUP = DATA.setup || null;

async function api(path, payload){
  let res;
  try{
    res = await fetch(path, {
      method: "POST", headers: {"Content-Type": "application/json",
                                "X-Itucap-Token": DATA.token || ""},
      body: JSON.stringify(payload)});
  }catch(err){
    // ★ En sık karşılaşılacak hata: kullanıcı terminalde Ctrl+C yapmış.
    // "Failed to fetch" demek yerine ne olduğunu söyle.
    throw new Error("sunucuya ulaşılamadı — `make app` hâlâ çalışıyor mu?");
  }
  const body = await res.json().catch(() => ({error: "cevap okunamadı"}));
  if(!res.ok) throw new Error(body.error || ("hata " + res.status));
  return body;
}

/** Sunucudan gelen yeni durumu uygula — sayfa yenilenmeden. */
function applyState(next){
  Object.assign(DATA, next);
  LIVE = !!DATA.live;
  SETUP = DATA.setup || null;
  MODES.length = 0;
  MODES.push(...((DATA.modes && DATA.modes.length) ? DATA.modes
    : [{key:"all", label:"Tüm adaylar", note:"",
        candidates: DATA.candidates, schedules: DATA.schedules}]));
  boot();
}

function setupBar(){
  const s = SETUP;
  const who = s
    ? `<b>${esc(s.anadalProgram)}</b> anadal` + (s.secondProgram
        ? ` · <b>${esc(s.secondProgram)}</b> ${esc(LBL)}` : " · ikinci program yok")
      + ` · <b>${DATA.donem || "?"}. dönem</b> (${esc(DATA.donemSource)})`
      + ` · <b>${s.transcript.length}</b> ders girilmiş`
    : `<b>${esc(DATA.anadal)}</b>` + (DATA.cap ? ` · <b>${esc(DATA.cap)}</b>` : "")
      + ` · <b>${DATA.donem || "?"}. dönem</b>`;
  $("#setupbar").innerHTML = `<div class="who">${who}</div>
    ${LIVE ? `
      <button class="ghost" data-setup="program">Program</button>
      <button class="ghost" data-setup="donem">Dönem</button>
      <button class="ghost primary" data-setup="plan">Plandan işaretle</button>
      <button class="ghost" data-setup="dersler">Ders ara</button>`
    : `<span class="ro">Düzenlemek için <span class="mono">make app</span></span>
       <button class="ghost" disabled>Program</button>
       <button class="ghost" disabled>Dönem</button>
       <button class="ghost" disabled>Plandan işaretle</button>
       <button class="ghost" disabled>Ders ara</button>`}`;
  $("#setupbar").querySelectorAll("[data-setup]").forEach(b =>
    b.addEventListener("click", () => ({program: programDialog, donem: termDialog,
                                        plan: checklistDialog,
                                        dersler: courseDialogSetup})[b.dataset.setup]()));
}

function openSetup(html, wire){
  $("#setupBody").innerHTML = html + `
    <div class="dlgactions">
      <span class="msg" id="setupMsg"></span>
      <button class="ghost" data-close>Kapat</button>
      <button class="ghost primary" id="setupSave">Kaydet</button>
    </div>`;
  $("#setupBody").querySelectorAll("[data-close]").forEach(b =>
    b.addEventListener("click", () => $("#setup").close()));
  wire();
  $("#setup").showModal();
}

function say(text, bad){
  const el = $("#setupMsg");
  if(el){ el.textContent = text; el.className = "msg" + (bad ? " bad" : ""); }
}

async function save(fn){
  const btn = $("#setupSave");
  if(btn){ btn.disabled = true; }
  say("kaydediliyor…");
  try{
    applyState(await fn());
    say("kaydedildi ✓");
    setTimeout(() => $("#setup").close(), 550);
  }catch(err){
    say(err.message, true);
  }finally{
    if(btn) btn.disabled = false;
  }
}

/* ---------- 1. program seçimi ---------- */
function programDialog(){
  const s = SETUP;
  const codes = [...new Set(s.programs.map(p => p.code))].sort();
  const opts = (sel) => codes.map(c =>
    `<option value="${esc(c)}"${c === sel ? " selected" : ""}>${esc(c)}</option>`).join("");
  openSetup(`
    <div class="eyebrow">Kurulum</div>
    <h2 style="margin-bottom:4px">Program seçimi</h2>
    <p class="modenote" style="margin:2px 0 4px">Değişiklik
      <span class="mono">config/settings.toml</span> dosyasına yazılır ve öğrenci
      kaydın yeni planlara bağlanır.</p>
    <div class="grid2">
      <label class="field"><span>Anadal</span>
        <select id="fAnadal">${opts(s.anadalProgram)}</select></label>
      <label class="field"><span>İkinci program</span>
        <div class="radios" id="fKind">
          ${[["cap","ÇAP"],["yandal","Yandal"],["yok","Yok"]].map(([k,l]) =>
            `<button data-k="${k}" aria-pressed="${k===s.secondKind}">${l}</button>`).join("")}
        </div></label>
    </div>
    <div id="fSecondWrap">
      <label class="field"><span>İkinci programın bölümü</span>
        <select id="fSecond">${opts(s.secondProgram)}</select></label>
      <label class="field"><span>Plan</span>
        <select id="fPlan"></select>
        <span class="hint">Planı boş bırakırsan en güncel OBS planı seçilir.</span></label>
    </div>
    <label class="field"><span>Kayıt yapabildiğin program kodları</span>
      <input type="text" id="fCodes" value="${esc(s.programCodes.join(", "))}">
      <span class="hint">Bir şubenin "Dersi Alabilen Programlar" listesinde bunlardan
        biri varsa dersi alabilirsin. Virgülle ayır.</span></label>`, () => {
    let kind = s.secondKind;
    const wrap = $("#fSecondWrap");
    const fillPlans = () => {
      const want = kind === "yok" ? null : kind;
      const code = $("#fSecond").value;
      const list = s.plans.filter(p => p.plan_type === want && p.program_code === code);
      $("#fPlan").innerHTML = `<option value="">otomatik (en güncel)</option>` +
        list.map(p => `<option value="${p.id}"${p.id === s.secondPlanId ? " selected" : ""}
          >${p.id} · ${p.slots} slot · ${esc((p.title || "").slice(0, 54))}</option>`).join("");
      if(!list.length) $("#fPlan").innerHTML +=
        `<option disabled>bu tipte plan yok — make refresh gerekebilir</option>`;
    };
    const sync = () => { wrap.hidden = kind === "yok"; if(kind !== "yok") fillPlans(); };
    $("#fKind").querySelectorAll("button").forEach(b =>
      b.addEventListener("click", () => {
        kind = b.dataset.k;
        $("#fKind").querySelectorAll("button").forEach(x =>
          x.setAttribute("aria-pressed", x.dataset.k === kind));
        sync();
      }));
    $("#fSecond").addEventListener("change", fillPlans);
    sync();
    $("#setupSave").addEventListener("click", () => save(() => api("/api/programs", {
      anadalProgram: $("#fAnadal").value,
      secondKind: kind,
      secondProgram: $("#fSecond").value,
      secondPlanId: $("#fPlan").value || null,
      programCodes: $("#fCodes").value.split(/[,\s]+/).filter(Boolean),
    })));
  });
}

/* ---------- 2. dönem seçimi ---------- */
function termDialog(){
  const cur = SETUP.donem;
  openSetup(`
    <div class="eyebrow">Kurulum</div>
    <h2 style="margin-bottom:4px">Bulunduğun dönem</h2>
    <p class="modenote" style="margin:2px 0 4px">&#8220;Dönemlik + alttan&#8221;
      öneri kipi bunu kullanır: dönemlik = bu dönemin plan dersleri,
      alttan = önceki dönemlerden kalanlar.</p>
    <label class="field"><span>Dönem</span>
      <div class="terms" id="fTerm">
        <button data-t="0" aria-pressed="${!cur}" style="width:auto;padding:7px 12px"
          >otomatik</button>
        ${[1,2,3,4,5,6,7,8].map(n =>
          `<button data-t="${n}" aria-pressed="${cur === n}">${n}</button>`).join("")}
      </div>
      <span class="hint">Şu an kullanılan: <b class="mono">${DATA.donem}. dönem</b>
        (${esc(DATA.donemSource)}). Otomatik seçilirse geçtiğin slotların en derin
        döneminden çıkarılır — kayıt donduran ya da yaz okulu okuyanda şaşabilir.
      </span></label>`, () => {
    let pick = cur || 0;
    $("#fTerm").querySelectorAll("button").forEach(b =>
      b.addEventListener("click", () => {
        pick = +b.dataset.t;
        $("#fTerm").querySelectorAll("button").forEach(x =>
          x.setAttribute("aria-pressed", +x.dataset.t === pick));
      }));
    $("#setupSave").addEventListener("click", () =>
      save(() => api("/api/donem", {donem: pick})));
  });
}

/* ---------- 3b. plandan tik atarak giriş ---------- */
/* ★ 60+ dersi tek tek aramak işkence. Plan zaten elimizde: dönem dönem
   listele, kullanıcı tiklesin. 0 kredili derste not listesi BL/BZ ile
   başlıyor — o dersler harf notu almıyor. */
function checklistDialog(){
  const plans = (SETUP.checklist || []);
  if(!plans.length){ openDialog(`<div class="empty">Plan bulunamadı.</div>`); return; }
  const passFail = SETUP.passFail || ["BL", "BZ"];
  const state = {};            // course -> {grade, taken}
  plans.forEach(p => p.terms.forEach(t => t.slots.forEach(sl =>
    sl.options.forEach(o => {
      state[o.course] = {taken: o.taken, grade: o.grade || "",
                         ip: o.status === "IN_PROGRESS", credits: o.credits};
    }))));

  const gradeOptions = (course) => {
    const st = state[course];
    const zero = st && (st.credits === 0);
    // 0 kredili derste BL/BZ önce; kredili derste harf notları önce.
    const list = zero ? [...passFail, ...SETUP.grades.filter(g => !passFail.includes(g))]
                      : SETUP.grades;
    const value = st.ip ? "--" : (st.grade || "");
    return `<select class="g" data-course="${esc(course)}"${st.taken ? "" : " disabled"}>
      ${list.map(g => `<option${g === value ? " selected" : ""}>${g}</option>`).join("")}
      <option value="--"${value === "--" ? " selected" : ""}>devam</option>
      <option value=""${value === "" ? " selected" : ""}>bilmiyorum</option>
    </select>`;
  };

  const slotHTML = (sl) => {
    const many = sl.options.length > 1;
    const head = many
      ? `<div class="eyebrow" style="margin:10px 0 4px">${esc(sl.pool || sl.category
          || "seçmeli havuz")} · ${sl.options.length} seçenek</div>` : "";
    return head + sl.options.map(o => `
      <label class="ckrow">
        <input type="checkbox" data-course="${esc(o.course)}"${
          state[o.course].taken ? " checked" : ""}>
        <span class="mono ckcode">${esc(o.course)}</span>
        <span class="ckname">${esc((o.name || "").slice(0, 40))}</span>
        <span class="mono ckcr">${o.credits ?? "–"}</span>
        ${gradeOptions(o.course)}
      </label>`).join("");
  };

  const body = plans.map(p => `
    <div class="field"><span>${esc(p.role)} · ${esc(p.program)}</span>
      ${p.terms.map(t => `
        <div class="ckterm">
          ${p.termBased && t.term ? `<div class="cktermhead">${t.term}. dönem</div>` : ""}
          ${t.slots.map(slotHTML).join("")}
        </div>`).join("")}
    </div>`).join("");

  openSetup(`
    <div class="eyebrow">Kurulum</div>
    <h2 style="margin-bottom:4px">Plandan işaretle</h2>
    <p class="modenote" style="margin:2px 0 6px">Aldığın dersleri tikle.
      <b>0 kredili</b> dersler harf notu almaz — onlarda
      <b class="mono">BL</b> (başarılı) / <b class="mono">BZ</b> (başarısız).
      Not bilmiyorsan <b>DD</b> sayılır.</p>
    <div class="chipline"><span class="chip">tik at</span>
      <span style="color:var(--ink-3);font-size:12px" id="ckCount"></span>
      <button class="ghost" id="ckAllTerm" style="margin-left:auto"
        >Bu döneme kadarki zorunluları işaretle</button></div>
    <div class="scroll" style="max-height:420px">${body}</div>`, () => {
    const box = $("#setupBody");
    const count = () => {
      $("#ckCount").textContent =
        Object.values(state).filter(x => x.taken).length + " ders işaretli";
    };
    count();
    box.querySelectorAll('input[type=checkbox][data-course]').forEach(cb =>
      cb.addEventListener("change", () => {
        const st = state[cb.dataset.course];
        st.taken = cb.checked;
        const sel = box.querySelector(`select.g[data-course="${CSS.escape(cb.dataset.course)}"]`);
        if(sel){ sel.disabled = !cb.checked; }
        count();
      }));
    box.querySelectorAll("select.g").forEach(sel =>
      sel.addEventListener("change", () => {
        const st = state[sel.dataset.course];
        st.ip = sel.value === "--";
        st.grade = (sel.value === "--" || sel.value === "") ? "" : sel.value;
      }));
    const bulk = $("#ckAllTerm");
    if(bulk) bulk.addEventListener("click", () => {
      // Bulunduğun dönemden ÖNCEKİ tüm zorunlu dersleri işaretle — çoğu
      // öğrenci için doğru başlangıç, tek tek düzeltmesi kolay.
      const upto = DATA.donem || 0;
      plans.forEach(p => p.terms.forEach(t => {
        if(!t.term || t.term >= upto) return;
        t.slots.forEach(sl => { if(sl.required) sl.options.forEach(o => {
          state[o.course].taken = true; }); });
      }));
      box.querySelectorAll('input[type=checkbox][data-course]').forEach(cb => {
        cb.checked = state[cb.dataset.course].taken;
        const sel = box.querySelector(`select.g[data-course="${CSS.escape(cb.dataset.course)}"]`);
        if(sel) sel.disabled = !cb.checked;
      });
      count();
    });

    $("#setupSave").addEventListener("click", () => save(() => api("/api/transcript", {
      items: Object.entries(state).filter(([, v]) => v.taken)
        .map(([course, v]) => ({course, grade: v.grade, inProgress: v.ip})),
      replace: false,        // ★ EKLER, silmez: plan dışı dersler korunur
    })));
  });
}

/* ---------- 3. geçilen dersler ---------- */
function courseDialogSetup(){
  // sayfada tutulan çalışma kopyası; 'Kaydet'e kadar sunucuya gitmiyor
  let rows = SETUP.transcript.map(t => ({...t}));
  const grades = SETUP.grades;

  const gradeSelect = (r, i) => {
    const value = r.status === "IN_PROGRESS" ? "--" : (r.grade || "");
    return `<select data-i="${i}" class="g">
      ${grades.map(g => `<option${g === value ? " selected" : ""}>${g}</option>`).join("")}
      <option value="--"${value === "--" ? " selected" : ""}>devam</option>
      <option value=""${value === "" ? " selected" : ""}>bilmiyorum</option>
    </select>`;
  };

  const draw = () => {
    $("#trBody").innerHTML = rows.length ? rows.map((r, i) => `<tr>
        <td><b class="mono">${esc(r.course)}</b>
          <div class="meta" style="color:var(--ink-3);font-size:11.5px"
            >${esc((r.name || "").slice(0, 44))}</div></td>
        <td>${gradeSelect(r, i)}</td>
        <td class="mono" style="color:var(--ink-3)">${r.credits ?? "–"}</td>
        <td style="text-align:right"><button class="rm" data-rm="${i}">çıkar</button></td>
      </tr>`).join("")
      : `<tr><td colspan="4"><div class="empty">Henüz ders girilmemiş.</div></td></tr>`;
    $("#trCount").textContent = rows.length;
    $("#trBody").querySelectorAll("select.g").forEach(sel =>
      sel.addEventListener("change", () => {
        const r = rows[+sel.dataset.i];
        r.grade = sel.value === "--" || sel.value === "" ? null : sel.value;
        r.status = sel.value === "--" ? "IN_PROGRESS" : "PASSED";
        r.inProgress = sel.value === "--";
      }));
    $("#trBody").querySelectorAll("[data-rm]").forEach(b =>
      b.addEventListener("click", () => { rows.splice(+b.dataset.rm, 1); draw(); }));
  };

  openSetup(`
    <div class="eyebrow">Kurulum</div>
    <h2 style="margin-bottom:4px">Geçilen dersler</h2>
    <p class="modenote" style="margin:2px 0 4px">Notu bilmiyorsan
      <b>DD</b> sayılır — en kötü durum. Böylece &#8220;MIN CC&#8221; isteyen bir
      önşartta yanlışlıkla &#8220;alabilirsin&#8221; denmez.</p>

    <label class="field"><span>Ders ekle</span>
      <input type="search" id="trSearch" placeholder="kod ya da ad — örn. MAT 103E"
        autocomplete="off">
      <div class="hits" id="trHits" hidden></div></label>

    <div class="field"><span>Girilmiş dersler (<span id="trCount">0</span>)</span>
      <div class="scroll">
        <table class="trtable">
          <thead><tr><th>Ders</th><th>Not</th><th>Kredi</th><th></th></tr></thead>
          <tbody id="trBody"></tbody>
        </table>
      </div>
    </div>

    ${(SETUP.backups || []).length ? `<details class="field">
      <summary style="cursor:pointer;font-size:13px;color:var(--seal)"
        >Yedekten geri yükle (${SETUP.backups.length})</summary>
      <div class="hint" style="margin:6px 0">Her silici kayıttan önce yedek
        alınıyor. Geri yükleme de yedeklenir — yanlış yedeği seçersen ikinci
        kez kaybetmezsin.</div>
      <div class="blocklist">${SETUP.backups.slice(0, 8).map(b => `
        <div class="blockitem" style="display:flex;justify-content:space-between;gap:8px">
          <span><b class="mono">${esc(b.stamp)}</b>
            <span style="color:var(--ink-3)"> ${b.courses} ders</span></span>
          <button class="rm" data-restore="${esc(b.file)}"
            style="color:var(--seal)">geri yükle</button>
        </div>`).join("")}</div>
    </details>` : ""}

    <details class="field"><summary style="cursor:pointer;font-size:13px;color:var(--seal)"
        >Toplu yapıştır (transkriptini olduğu gibi)</summary>
      <textarea id="trPaste" placeholder="MAT 103E AA&#10;FIZ 101E BB&#10;GEO 220E CC"
        style="margin-top:8px"></textarea>
      <span class="hint">Her satır bir ders: <span class="mono">KOD NOT</span>.
        Not yazmazsan DD sayılır, <span class="mono">--</span> yazarsan "devam ediyor".
        Yapıştırma <b>mevcut listeye eklenir</b>, silmez.</span>
      <button class="ghost" id="trPasteBtn" style="margin-top:8px">Yapıştırılanı ekle</button>
    </details>`, () => {
    draw();

    let timer = null;
    $("#trSearch").addEventListener("input", () => {
      clearTimeout(timer);
      const q = $("#trSearch").value.trim();
      if(q.length < 2){ $("#trHits").hidden = true; return; }
      timer = setTimeout(async () => {
        const res = await fetch("/api/courses?q=" + encodeURIComponent(q));
        const {results} = await res.json();
        const have = new Set(rows.map(r => r.course));
        $("#trHits").hidden = false;
        $("#trHits").innerHTML = results.length ? results.map(c => `
          <button class="hit" data-code="${esc(c.code)}" data-name="${esc(c.name || "")}"
            data-credits="${c.credits ?? ""}"${have.has(c.code) ? " disabled" : ""}>
            <span><b class="mono">${esc(c.code)}</b>
              <span class="meta"> ${esc((c.name || "").slice(0, 40))}</span></span>
            <span class="meta mono">${have.has(c.code) ? "listede"
              : (c.credits ?? "–") + " kredi"}</span></button>`).join("")
          : `<div class="empty" style="padding:12px">eşleşen ders yok</div>`;
        $("#trHits").querySelectorAll("[data-code]").forEach(b =>
          b.addEventListener("click", () => {
            rows.unshift({course: b.dataset.code, name: b.dataset.name,
                          credits: b.dataset.credits ? +b.dataset.credits : null,
                          grade: "DD", status: "PASSED", known: false});
            $("#trSearch").value = ""; $("#trHits").hidden = true; draw();
          }));
      }, 180);
    });

    $("#setupBody").querySelectorAll("[data-restore]").forEach(b =>
      b.addEventListener("click", () => save(() =>
        api("/api/transcript/restore", {file: b.dataset.restore}))));

    $("#trPasteBtn").addEventListener("click", () => save(async () => {
      const body = await api("/api/transcript/paste",
        {text: $("#trPaste").value, replace: false});
      if(body.bad && body.bad.length) say("çözülemeyen satır: " + body.bad.join(" | "), true);
      return body;
    }));

    // ★ replace:true — ekrandaki liste TAM liste. 'çıkar' düğmesinin
    //   çalışması için gerekli; yoksa silinen ders DB'de kalırdı.
    $("#setupSave").addEventListener("click", () => save(() => api("/api/transcript", {
      items: rows.map(r => ({course: r.course, grade: r.grade,
                             inProgress: r.status === "IN_PROGRESS"})),
      replace: true,
    })));
  });
}

/* ---------- dönem kredi yükü (yönetmelik) ---------- */
function renderLoad(){
  const L = DATA.load;
  if(!L || !L.max){ $("#loadBody").innerHTML = ""; return; }
  const fix = LIVE && L.conflict
    ? `<button class="ghost" id="loadFix">Tavanı ${L.max}'e çek</button>` : "";
  $("#loadBody").innerHTML = `
    <div class="gauge" style="margin-bottom:12px">
      <div class="gaugebar" style="max-width:230px">
        <div class="gaugelabel" style="margin-top:0">
          <b class="mono" style="font-size:15px">${L.min ? L.min + "–" : "en çok "}${L.max}</b>
          kredi ${L.verified ? "" : "<b>⚠</b>"}</div>
        <div class="gaugelabel" style="color:var(--ink-3)">
          şu an ayarlı: <b class="mono">${L.declared || "—"}</b></div>
      </div>
      <div style="flex:2;min-width:250px;font-size:12.5px;color:var(--ink-2)">
        ${L.reasons.map(r => `<div>· ${esc(r)}</div>`).join("")}
        ${L.source ? `<div style="color:var(--ink-3);margin-top:4px">${esc(L.source)}</div>` : ""}
      </div>
    </div>
    ${L.conflict ? `<div class="note" style="border-left-color:var(--danger)">
      <b>Ayarlı tavan (${L.declared}) yönetmeliğin izin verdiğinden yüksek
      (${L.max}).</b> ${L.next ? `${L.next.max} krediye çıkmak için GNO ≥
      ${L.next.minGpa.toFixed(2)} gerekiyor; şu an ${DATA.gpa.value.toFixed(2)}.` : ""}
      Motor <b>${L.declared}</b> krediye kadar program kuruyor — kayıtta
      reddedilebilir. ${fix}</div>` : ""}`;
  const btn = $("#loadFix");
  if(btn) btn.addEventListener("click", async () => {
    btn.disabled = true; btn.textContent = "…";
    try{ applyState(await api("/api/maxload", {maxLoad: L.max})); }
    catch(err){ btn.disabled = false; btn.textContent = "hata: " + err.message; }
  });
}

/* ---------- GNO ---------- */
function renderGpa(){
  const g = DATA.gpa;
  if(!g || !g.counted){ $("#gpaBody").innerHTML = ""; return; }
  /* Eşikler AŞAMAYA göre gruplanıyor: başvuru / devam / mezuniyet.
     Yedisini tek sırada kırmızı kırmızı dizmek "yedi kuralda kaldın"
     izlenimi veriyordu; oysa mezuniyet eşiği bugünün sınavı değil.
     ok === null → henüz hesaplanamıyor; ✗ değil "—". */
  const STAGE = {basvuru: "Başvuru", devam: "Devam", mezuniyet: "Mezuniyet"};
  const style = t => t.ok === null
    ? "background:transparent;color:var(--ink-3);border-color:var(--border-strong)"
    : t.ok ? "background:var(--anadal-soft);color:var(--anadal)"
           : "background:transparent;color:var(--danger);border-color:currentColor";
  const mark = t => t.ok === null ? "—" : (t.ok ? "✓" : "✗");
  const groups = Object.keys(STAGE).filter(k => g.thresholds.some(t => t.kind === k));
  const loose = g.thresholds.filter(t => !groups.includes(t.kind));
  const chipOf = t => `
    <span class="cat" style="${style(t)}"
      title="${esc([t.note, t.why, t.source].filter(Boolean).join(" · "))}"
      >${esc(t.label)} ≥ ${t.min.toFixed(2)}
      ${mark(t)}${t.verified ? "" : " ⚠"}${t.tolerance ? " ¹" : ""}</span>`;
  const chips = groups.map(k => `
    <div style="display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-top:7px">
      <span class="eyebrow" style="min-width:74px">${STAGE[k]}</span>
      ${g.thresholds.filter(t => t.kind === k).map(chipOf).join("")}
    </div>`).join("") + (loose.length ? `
    <div class="cats" style="margin-top:7px">${loose.map(chipOf).join("")}</div>` : "");
  const unverified = g.thresholds.filter(t => !t.verified).length;
  const tolerated = g.thresholds.filter(t => t.tolerance);
  const pending = g.thresholds.filter(t => t.ok === null);
  $("#gpaBody").innerHTML = `
    <div class="gauge" style="margin-bottom:14px;padding-bottom:14px;
         border-bottom:1px solid var(--border)">
      <div class="gaugebar" style="max-width:230px">
        <div class="track"><i style="width:${Math.min(100, g.value / 4 * 100)}%"></i></div>
        <div class="gaugelabel"><b class="mono" style="font-size:15px">${g.value.toFixed(2)}</b>
          / 4.00 · <span class="mono">${g.counted}</span> ders,
          <span class="mono">${g.credits}</span> kredi</div>
      </div>
      <div style="flex:2;min-width:250px;font-size:12.5px;color:var(--ink-2)">
        <b>GNO (tahmini)</b> — transkriptinden hesaplandı, <b>OBS'nin resmi
        GNO'su değil</b>. Kesin değer için OBS'ye bak.
        <div class="cats" style="margin-top:8px">${chips}</div>
      </div>
    </div>
    ${g.partial || unverified || (g.conditional || []).length
      ? `<div class="note" style="margin-bottom:14px">
      ${g.noCredit.length ? `Kredisi bilinmeyen <b>${g.noCredit.length}</b> ders
        ortalamaya girmedi (<span class="mono">${g.noCredit.slice(0,5).map(esc).join(", ")}</span>). ` : ""}
      ${g.uncertain.length ? `Notu girilmemiş <b>${g.uncertain.length}</b> ders
        <b>DD</b> sayıldı — gerçek GNO'n daha yüksek olabilir. ` : ""}
      ${(g.conditional || []).length ? condText(g) : ""}
      ${pending.length ? `<b>${pending.length}</b> eşik henüz hesaplanamıyor
        (—): ${pending.map(t => esc(t.why || t.label)).join(" ")} ` : ""}
      ${tolerated.length ? `<b>¹</b> ${tolerated.map(t =>
        esc(t.label)).join(", ")}: yönerge bir defaya mahsus altına düşmeye
        izin veriyor; ikinci kez düşersen kayıt silinir. ` : ""}
      ${unverified ? `Eşiklerin <b>${unverified}</b> tanesi mevzuattan
        <b>doğrulanmadı</b> (⚠ işaretli); teyit edip
        <span class="mono">config/kurallar.toml</span> içinde
        <span class="mono">dogrulandi = true</span> yap.` : ""}
    </div>` : ""}`;
}

/* Şartlı geçer dersler (DC+…DD) — MADDE 20/2-b.
   ★ İki ayrı soruyu ayrı cümlede tutuyor: ders tamamlandı mı (evet), mezun
   olunabilir mi (genel ortalamaya bağlı). Faz 11'de "şart bilinmiyor"
   deniyordu; şart MADDE 31/1'de bulundu — GNO ≥ 2.00. */
function condText(g){
  const r = g.conditionalRule || {};
  const list = `<span class="mono">${g.conditional.slice(0,6).map(esc).join(", ")}</span>`;
  const more = g.conditional.length > 6 ? ` (+${g.conditional.length - 6})` : "";
  if(r.minGpa == null)
    return `<b>${g.conditional.length}</b> dersin notu <b>şartlı geçer</b>
      aralığında (DC+…DD): ${list}${more}. `;
  return `<b>${g.conditional.length}</b> dersin notu <b>şartlı geçer</b>
    aralığında (DC+…DD): ${list}${more}. Bu dersler
    <b>tamamlanmış sayılıyor</b>; şart, mezuniyette genel ortalamanın
    <b class="mono">${r.minGpa.toFixed(2)}</b> düzeyine çıkmış olması
    (${esc(r.source || "MADDE 31")}). ${r.ok === false
      ? `<b style="color:var(--danger)">Şu anki ortalaman bunun altında.</b>`
      : `Şu an bu şartı karşılıyorsun.`} `;
}

/* ---------- değişim raporu ---------- */
function renderChanges(){
  const c = DATA.changes;
  const btn = $("#refreshBtn");
  $("#changeSection").hidden = !(LIVE || (c && c.count));
  if(btn){ btn.hidden = !LIVE; }
  if(!c || !c.since || !c.until || c.since === c.until){
    $("#changeWhen").textContent = LIVE
      ? "Karşılaştırma için en az iki tazeleme gerekiyor."
      : "Karşılaştırma verisi yok.";
    $("#changeBody").innerHTML = "";
    return;
  }
  $("#changeWhen").textContent = `${c.since} → ${c.until} · yalnız seni ilgilendiren dersler`;
  const group = (title, cls, items, line) => items.length ? `
    <div class="chipline"><span class="chip ${cls}">${title}</span>
      <span style="color:var(--ink-3);font-size:12.5px">${items.length}</span></div>
    <div class="blocklist">${items.slice(0, 24).map(i =>
      `<div class="blockitem"><b class="mono">${esc(i.course)}</b> ${line(i)}</div>`
    ).join("")}</div>` : "";
  const html =
    group("açıldı", "credit", c.opened, i => `${i.sections} şube — ${esc((i.name||"").slice(0,34))}`) +
    group("yeni şube", "credit", c.newSections, i => `CRN ${esc(i.crn)} · ${i.free} boş`) +
    group("yer açıldı", "credit", c.freed, i => `CRN ${esc(i.crn)} · ${i.free} boş`) +
    group("kontenjan doldu", "supply", c.filled, i => `CRN ${esc(i.crn)} · ${i.capacity}/${i.capacity}`) +
    group("şube kapandı", "supply", c.closed, i => `CRN ${esc(i.crn)}`);
  $("#changeBody").innerHTML = html ||
    `<div class="empty">Seni ilgilendiren derslerde değişiklik yok.</div>`;
}

/* ---------- denklik önerileri ---------- */
/** ★ Uygulanmış beyanlar — GERİ ALINABİLİR olmalı. Tek tıkla uygulanan bir
    şey tek tıkla kaldırılabilmeli; yanlış bir denklik tamamlamadığın şartı
    tamamlanmış gösterir ve kullanıcı hatasını fark ettiğinde dosyayı elle
    düzenlemek zorunda kalmamalı. */
function appliedHTML(){
  const eq = DATA.equivalences || [];
  if(!eq.length) return "";
  return `<div class="chipline"><span class="chip unknown">uygulanmış beyan</span>
      <span style="color:var(--ink-3);font-size:12.5px">${eq.length}</span></div>
    <div class="blocklist">${eq.map(e => `
      <div class="blockitem" style="display:flex;justify-content:space-between;gap:8px">
        <span><b class="mono">${e.sources.map(esc).join(" + ")}</b>
          <span style="color:var(--ink-3)"> → </span>
          <b class="mono">${esc(e.target)}</b></span>
        ${LIVE ? `<button class="rm" data-uneq="${esc(e.target)}">kaldır</button>` : ""}
      </div>`).join("")}</div>`;
}

function wireApplied(){
  $("#suggestBody").querySelectorAll("[data-uneq]").forEach(b =>
    b.addEventListener("click", async () => {
      b.disabled = true; b.textContent = "…";
      try{ applyState(await api("/api/equivalence/remove", {target: b.dataset.uneq})); }
      catch(err){ b.disabled = false; b.textContent = "hata"; }
    }));
}

function renderSuggestions(){
  const items = DATA.suggestions || [];
  const applied = DATA.equivalences || [];
  $("#suggestSection").hidden = !(items.length || applied.length);
  if(!items.length){
    $("#suggestBody").innerHTML = applied.length
      ? `<div class="modenote" style="margin-bottom:6px">Yeni aday denklik yok.</div>`
        + appliedHTML()
      : "";
    wireApplied();
    return;
  }
  const LABEL = {yuksek: ["yüksek güven", "credit"],
                 orta: ["orta güven", "prereq"],
                 dusuk: ["düşük güven", "supply"]};
  const high = items.filter(i => i.confidence === "yuksek");
  let html = "";
  ["yuksek", "orta", "dusuk"].forEach(level => {
    const group = items.filter(i => i.confidence === level);
    if(!group.length) return;
    const [label, cls] = LABEL[level];
    html += `<div class="chipline"><span class="chip ${cls}">${label}</span>
      <span style="color:var(--ink-3);font-size:12.5px">${group.length}</span></div>
      <div class="optlist" style="max-height:none">${group.map(i => `
        <div class="opt" style="cursor:default">
          <span><b class="mono">${esc(i.source)}</b>
            <span style="color:var(--ink-3)"> → </span>
            <b class="mono">${esc(i.target)}</b>
            <span class="tag ${i.role === "ANADAL" ? "ANADAL" : "CAP"}"
              style="margin-left:6px">${esc(i.role)}</span>
            <div class="meta">${esc(i.sourceName)} · notun
              <b class="mono">${esc(i.sourceGrade)}</b> · ${esc(i.reasons.join(", "))}</div></span>
          ${LIVE ? `<button class="ghost" data-eq="${esc(i.target)}"
            data-src="${esc(i.source)}" style="white-space:nowrap">Uygula</button>`
          : `<span class="meta mono">make app</span>`}
        </div>`).join("")}</div>`;
  });
  if(LIVE && high.length > 1){
    html += `<div style="margin-top:14px">
      <button class="ghost primary" id="eqAll">${high.length} yüksek güvenlinin
        hepsini uygula</button></div>`;
  }
  html += `<div class="modenote" style="margin-top:10px">Uygulanan denklikler
    <span class="mono">config/denklikler.toml</span> dosyasına yazılır —
    açıp görebilir, silebilirsin.</div>`;
  $("#suggestBody").innerHTML = html + appliedHTML();
  $("#suggestBody").querySelectorAll("[data-eq]").forEach(b =>
    b.addEventListener("click", async () => {
      b.disabled = true; b.textContent = "…";
      try{ applyState(await api("/api/equivalence",
          {target: b.dataset.eq, sources: [b.dataset.src]})); }
      catch(err){ b.disabled = false; b.textContent = "hata: " + err.message; }
    }));
  wireApplied();
  const all = $("#eqAll");
  if(all) all.addEventListener("click", async () => {
    all.disabled = true; all.textContent = "uygulanıyor…";
    try{
      let next;
      for(const i of high){
        next = await api("/api/equivalence", {target: i.target, sources: [i.source]});
      }
      applyState(next);
    }catch(err){ all.disabled = false; all.textContent = "hata: " + err.message; }
  });
}

/* ---------- programı kaydet / CRN listesi ---------- */
function savedKey(){
  return (DATA.savedPicks && DATA.savedPicks.picks || [])
    .map(p => p.course + "@" + p.crn).sort().join("|");
}
function currentKey(){
  return sel.map(x => x.course + "@" + x.crn).sort().join("|");
}
function renderSaveState(){
  const btn = $("#savePicks"), mark = $("#savedMark");
  const saved = DATA.savedPicks || {picks: [], savedAt: ""};
  const dirty = currentKey() !== savedKey();
  if(btn) btn.hidden = !LIVE || !dirty || !sel.length;
  if(mark){
    mark.hidden = !(saved.picks.length && !dirty);
    mark.textContent = "kaydedildi" + (saved.savedAt
      ? " · " + saved.savedAt.replace("T", " ").slice(0, 16) : "");
  }
}
function wirePicks(){
  const btn = $("#savePicks");
  if(btn && LIVE) btn.onclick = async () => {
    btn.disabled = true; btn.textContent = "kaydediliyor…";
    try{
      // ★ applyState boot() çağırıyor, o da resetTo(0) yapıyor. Seçimi
      //   sunucudan gelen KAYITLI programla yeniden kuracağız, o yüzden
      //   önce kaydet, sonra durumu tazele.
      applyState(await api("/api/picks", {picks: sel}));
    }catch(err){
      btn.disabled = false; btn.textContent = "hata: " + err.message;
    }
  };
  const crn = $("#crnBtn");
  if(crn) crn.onclick = crnDialog;
}

function crnDialog(){
  const ps = picks();
  if(!ps.length){ openDialog(`<div class="empty">Programda ders yok.</div>`); return; }
  const list = ps.slice().sort((a, b) => a.cand.course.localeCompare(b.cand.course));
  const line = list.map(p => p.sec.crn).join(" ");
  const alts = list.map(p => {
    const others = p.cand.sections.filter(s => s.crn !== p.sec.crn);
    return {course: p.cand.course, others};
  }).filter(x => x.others.length);
  openDialog(`
    <div class="eyebrow">Kayıt günü</div>
    <h2 style="margin-bottom:4px">CRN listesi</h2>
    <p class="modenote" style="margin:2px 0 10px">OBS'ye yazacağın numaralar.
      Araç senin yerine kayıt YAPMAZ — bu liste elle girmen için.</p>
    <label class="field"><span>Tümü (kopyala)</span>
      <input type="text" id="crnLine" class="mono" readonly value="${esc(line)}">
      <span class="hint" id="crnCopied"></span></label>
    <div class="field"><span>${list.length} ders</span>
      <div class="scroll" style="max-height:250px">
        <table class="trtable">
          <thead><tr><th>CRN</th><th>Ders</th><th>Gün / saat</th><th>Boş</th></tr></thead>
          <tbody>${list.map(p => `<tr>
            <td><b class="mono">${esc(p.sec.crn)}</b></td>
            <td><b class="mono">${esc(p.cand.course)}</b>
              <span class="tag ${p.cand.role === "ANADAL" ? "ANADAL" : "CAP"}"
                style="margin-left:5px">${esc(p.cand.role)}</span></td>
            <td class="meta mono">${p.sec.meetings.length
              ? p.sec.meetings.map(m => `${DAYS[m.day-1]} ${hhmm(m.start)}`).join(", ")
              : "saat ilan edilmemiş"}</td>
            <td class="mono ${p.sec.free ? "" : "over"}">${p.sec.free}</td>
          </tr>`).join("")}</tbody>
        </table>
      </div>
    </div>
    ${alts.length ? `<details class="field">
      <summary style="cursor:pointer;font-size:13px;color:var(--seal)"
        >Yedek CRN'ler (kontenjan dolarsa)</summary>
      <div class="scroll" style="max-height:200px">
        <table class="trtable"><tbody>${alts.map(a => `<tr>
          <td><b class="mono">${esc(a.course)}</b></td>
          <td class="meta mono">${a.others.map(s =>
            `${s.crn} (${s.free} boş)`).join(" · ")}</td></tr>`).join("")}</tbody></table>
      </div></details>` : ""}`);
  const input = $("#crnLine");
  if(input){
    input.addEventListener("click", () => {
      input.select();
      try{ document.execCommand("copy"); $("#crnCopied").textContent = "kopyalandı ✓"; }
      catch(e){ $("#crnCopied").textContent = "seçildi — Cmd+C ile kopyala"; }
    });
    $("#crnCopied").textContent = "tıkla, kopyalanır";
  }
}

/* ---------- veriyi tazele ---------- */
function wireRefresh(){
  const btn = $("#refreshBtn");
  if(!btn || !LIVE) return;
  btn.onclick = async () => {
    btn.disabled = true;
    const was = btn.textContent;
    btn.textContent = "tazeleniyor… (1–2 dk)";
    try{
      const next = await api("/api/refresh", {});
      applyState(next);
      const n = (next.changes && next.changes.count) || 0;
      $("#changeWhen").textContent += next.obsError
        ? `  ·  ⚠ OBS'ye ulaşılamadı, eski plan verisi korundu (${next.obsError})`
        : (n ? `  ·  ${n} değişiklik bulundu` : "  ·  değişiklik yok");
    }catch(err){
      $("#changeBody").innerHTML =
        `<div class="note">Tazeleme başarısız: ${esc(err.message)}</div>`;
      btn.disabled = false; btn.textContent = was;
    }
  };
}

/* ---------- kredi eşiği ---------- */
function renderCredits(){
  const info = DATA.credits;
  const hasGpa = (DATA.gpa && DATA.gpa.counted) || (DATA.load && DATA.load.max);
  if(!info || !info.rules || !info.rules.length){
    $("#creditBody").innerHTML = "";
    $("#creditSection").hidden = !hasGpa; return;
  }
  $("#creditSection").hidden = false;
  $("#creditBody").innerHTML = info.rules.map(r => {
    const pct = Math.min(100, Math.round(1000 * info.earned / r.min) / 10);
    return `<div class="gauge" style="margin-bottom:12px">
      <div class="gaugebar">
        <div class="track"><i class="${r.ok ? "ok" : ""}" style="width:${Math.max(2,pct)}%"></i></div>
        <div class="gaugelabel"><b class="mono">${info.earned}</b> / ${r.min} kredi
          ${r.ok ? "· <b>şart sağlandı</b>"
                 : `· <b class="mono">${r.missing}</b> kredi eksik`}</div>
      </div>
      <div style="flex:2;min-width:240px;font-size:12.5px;color:var(--ink-2)">
        <b>${esc(r.name)}</b> — ${esc(r.note)}
        ${r.holding && r.holding.length ? `<div style="margin-top:5px;color:var(--ink-3)">
          Şu an tuttuğu dersler: <span class="mono">${r.holding.map(esc).join(", ")}</span>
          — önerilere girmiyorlar.</div>` : ""}
      </div>
    </div>`;
  }).join("") + (info.unknown && info.unknown.length
    ? `<div class="note" style="margin-top:6px">Kredisi katalogda bulunamayan
       <b>${info.unknown.length}</b> geçilmiş ders var
       (<span class="mono">${info.unknown.slice(0,6).map(esc).join(", ")}</span>).
       Bunlar <b>0 kredi</b> sayıldı — yani eşik olduğundan zor gösteriliyor.</div>` : "")
    + `<div class="modenote" style="margin-top:8px">Kural
       <span class="mono">config/kurallar.toml</span> içinde beyan edilir; mevzuat
       değişirse kod değil o dosya değişir.</div>`;
}

/* ---------- ilerleme panelleri ---------- */
/* ★ Panel iki kez çiziliyor: bir kez sayfa açılırken (yalnız geçilmişler),
   bir kez de her seçim değişiminde (geçilmiş + bu dönem seçili). İkinci
   katman 'bu dönemi bitirirsen ne olur' sorusunun cevabı — barın taralı
   kısmı, yüzdenin sağındaki ok ve kalan zorunlu sayısındaki düşüş. */
function panelHTML(p, plan){
  const pctAfter = p.slotsTotal
    ? Math.round(1000 * (p.slotsDone + plan.slots) / p.slotsTotal) / 10 : p.percent;
  const kind = {ANADAL:"Anadal", CAP:"Çift anadal", YANDAL:"Yandal"}[p.role] || p.role;
  const gain = (a) => a ? ` <span class="gain">+${a}</span>` : "";
  return `<article class="card pad panel" data-role="${p.role}">
    <div class="top">
      <div>
        <div class="eyebrow">${kind}</div>
        <h2>${esc(p.program)}</h2>
      </div>
      <div class="pct mono">%${p.percent}</div>
    </div>
    <div class="name">${esc(p.title)}</div>
    <div class="meter">
      <i style="width:${Math.max(1, p.percent)}%"></i>
      <i class="plan" style="width:${Math.max(0, pctAfter - p.percent)}%"></i>
    </div>
    <div class="proj">${plan.slots
      ? `bu dönem <b class="mono">${plan.slots}</b> slot dolarsa
         <span class="mono">%${p.percent}</span> <span class="arrow">→</span>
         <b class="mono">%${pctAfter}</b>`
      : `<span class="flat">bu dönemki seçimde bu plandan ders yok</span>`}</div>
    <div class="stats">
      <span>slot <b class="mono">${p.slotsDone}/${p.slotsTotal}</b>${gain(plan.slots)}</span>
      <span>kredi <b class="mono">${p.creditsDone}/${p.creditsTotal}</b>${gain(plan.credits)}</span>
      <span>akts <b class="mono">${p.ectsDone}/${p.ectsTotal}</b>${gain(plan.ects)}</span>
      <span>kalan zorunlu <b class="mono">${p.openRequired}</b>${
        plan.required ? ` <span class="arrow">→</span>
          <b class="mono gain">${p.openRequired - plan.required}</b>` : ""}</span>
    </div>
    <div class="cats">${p.byCategory.map(c =>
      `<span class="cat${c.done ? "" : " zero"}">${esc(c.key)} ${c.done}/${c.total}</span>`
    ).join("")}</div>
  </article>`;
}

/** Bu dönemki seçimin bir plana katkısı. Slot bazlı sayıyoruz: aynı havuza
    iki ders koyulamadığı için slot sayısı = ilerleyen slot sayısı. */
function planned(planId){
  const seen = new Set();
  let slots = 0, credits = 0, ects = 0, required = 0;
  for(const p of picks()){
    if(p.cand.planId !== planId || seen.has(p.cand.slotId)) continue;
    seen.add(p.cand.slotId);
    slots++; credits += p.cand.credits; ects += p.cand.ects;
    if(p.cand.required) required++;
  }
  return {slots, credits: +credits.toFixed(1), ects: +ects.toFixed(1), required};
}

function renderPanels(){
  $("#panels").innerHTML =
    DATA.panels.map(p => panelHTML(p, planned(p.planId))).join("");
}

/* ================= DÜZENLENEBİLİR PROGRAM =================
   Izgara salt okunur değil: seçim burada tutuluyor, kullanıcı ders ve şube
   değiştirebiliyor. Kurallar motorla AYNI — çakışma yok, bir havuz slotu tek
   ders. Kredi tavanı aşılırsa engellenmiyor, uyarılıyor (istisnalar olabiliyor). */
/* ★ Kip: 'tüm adaylar' ya da 'N. dönem + alttan'. Her kipin KENDİ aday havuzu
   ve kendi programları var — kip değişince aday listesi de değişiyor, yoksa
   ızgarada olmayan bir dersi tabloda görürdün. */
const MODES = (DATA.modes && DATA.modes.length) ? DATA.modes
  : [{key:"all", label:"Tüm adaylar", note:"",
      candidates: DATA.candidates, schedules: DATA.schedules}];
let mode = 0;
let CAND = {};
const T0 = 8*60, T1 = 21*60, STEP = 30, ROWS = (T1-T0)/STEP;
let active = 0;
let sel = [];                                   // [{course, crn}]

const M = () => MODES[mode];
function useMode(i){
  mode = i;
  CAND = Object.fromEntries(M().candidates.map(c => [c.course, c]));
  active = 0;
  renderModes();
  resetTo(0);
  if(i === 0) startFromSaved();     // kaydedilmiş program varsa onu göster
}
function renderModes(){
  $("#modes").innerHTML = MODES.length < 2 ? "" : MODES.map((m,i) =>
    `<button class="modebtn" aria-pressed="${i===mode}" data-i="${i}">${esc(m.label)}</button>`
  ).join("");
  $("#modes").querySelectorAll(".modebtn").forEach(b =>
    b.addEventListener("click", () => useMode(+b.dataset.i)));
  $("#modeNote").textContent = M().note || "";
}

const sectionOf = (course, crn) => (CAND[course]?.sections || []).find(s => s.crn === crn);
const loadOf = (c) => DATA.unit === "kredi" ? c.credits : c.ects;
const overlap = (a,b) => a.day === b.day && a.start < b.end && b.start < a.end;
const clash = (x,y) => x.meetings.some(m => y.meetings.some(n => overlap(m,n)));

function picks(){
  return sel.map(x => ({cand: CAND[x.course], sec: sectionOf(x.course, x.crn)}))
            .filter(p => p.cand && p.sec);
}
function totals(){
  const ps = picks();
  const sum = (f) => +ps.reduce((a,p) => a + f(p.cand), 0).toFixed(1);
  return {n: ps.length, credits: sum(c=>c.credits), ects: sum(c=>c.ects),
          score: sum(c=>c.score), load: sum(loadOf)};
}
function conflictsWith(section, exceptCourse){
  return picks().filter(p => p.cand.course !== exceptCourse && clash(section, p.sec));
}
function poolBlocker(cand, exceptCourse){
  if(!cand.pool) return null;
  return picks().find(p => p.cand.course !== exceptCourse && p.cand.pool &&
                           p.cand.slotId === cand.slotId) || null;
}
function resetTo(i){
  const sc = M().schedules[i];
  sel = sc ? sc.picks.map(p => ({course: p.course, crn: p.section.crn})) : [];
  render();
}

/** ★ Açılışta: kaydedilmiş programın varsa ONU yükle, öneriyi değil.
    Motorun önerisi her tazelemede yeniden hesaplanıyor; senin seçimin ise
    senin kararın. 'Öneriye dön' düğmesi ikisi arasında geçiş sağlıyor. */
function startFromSaved(){
  const saved = (DATA.savedPicks && DATA.savedPicks.picks) || [];
  const usable = saved.filter(p => sectionOf(p.course, p.crn));
  if(!usable.length) return false;
  sel = usable.map(p => ({course: p.course, crn: p.crn}));
  render();
  return true;
}
function edited(){
  const sc = M().schedules[active];
  const key = (arr) => arr.slice().sort().join("|");
  const now = key(sel.map(x => x.course + "@" + x.crn));
  const base = key((sc ? sc.picks : []).map(p => p.course + "@" + p.section.crn));
  return now !== base;
}

/* ---------- sekmeler + ızgara ---------- */
function renderTabs(){
  $("#tabs").innerHTML = M().schedules.map((s,i) =>
    `<button class="tab" role="tab" aria-selected="${i===active}" data-i="${i}">
       Öneri ${i+1} · ${s.credits} kredi</button>`).join("")
    || `<span class="empty">öneri üretilemedi</span>`;
  $("#tabs").querySelectorAll(".tab").forEach(b =>
    b.addEventListener("click", () => { active = +b.dataset.i; resetTo(active); }));
}

/* Dar ekran görünümü: gün gün dikey liste (yapılacaklar 4.1).
   Izgaranın min-width'i 660px; telefonda yana kaydırmadan okunmuyordu.

   ★ Listenin ızgaraya göre zayıf yanı çakışmayı göstermemesi. Onu kabul edip
   geçmek yerine burada çakışma AÇIKÇA hesaplanıyor: aynı gün içinde saatleri
   kesişen iki ders kırmızıyla ve "ÇAKIŞIYOR" etiketiyle işaretleniyor. */
function renderDayList(){
  const box = $("#daylist");
  if(!box) return;
  const byDay = {};
  picks().forEach(p => p.sec.meetings.forEach(m => {
    (byDay[m.day] = byDay[m.day] || []).push({p, m});
  }));
  let out = "";
  for(let d=1; d<=5; d++){
    const items = (byDay[d] || []).sort((a,b) => a.m.start - b.m.start);
    // Çakışma: aynı gündeki her çift için aralık kesişimi.
    const clash = new Set();
    for(let i=0;i<items.length;i++) for(let j=i+1;j<items.length;j++){
      if(items[i].m.start < items[j].m.end && items[j].m.start < items[i].m.end){
        clash.add(i); clash.add(j);
      }
    }
    out += `<section><h3>${DAYS[d-1]}</h3>`;
    out += items.length ? items.map((it,i) =>
      `<button class="row${clash.has(i) ? " clash" : ""}" data-role="${it.p.cand.role}"
         data-course="${esc(it.p.cand.course)}">
         <span><b class="mono">${esc(it.p.cand.course)}</b>
           <small class="mono">${hhmm(it.m.start)}–${hhmm(it.m.end)}
             ${esc(it.m.building)}</small></span>
         ${clash.has(i) ? '<span class="warn">çakışıyor</span>' : ""}
       </button>`).join("")
      : `<div class="none">boş</div>`;
    out += `</section>`;
  }
  box.innerHTML = out;
  box.querySelectorAll(".row").forEach(el =>
    bind(el, () => courseDialog(el.dataset.course)));
}

function render(){
  renderTabs();
  renderPanels();
  const t = totals();
  const over = DATA.maxLoad && t.load > DATA.maxLoad;
  $("#schedSummary").innerHTML = `
    <span class="dot"><i style="background:var(--anadal)"></i>anadal</span>
    <span class="dot"><i style="background:var(--cap)"></i>${esc(LBL)}</span>
    <span>${t.n} ders</span>
    <span class="mono${over ? " over" : ""}">${t.credits} kredi · ${t.ects} AKTS</span>
    <span>sınır <b class="mono">${DATA.maxLoad} ${DATA.unitLabel}</b>${
      over ? ' <span class="over">aşıldı</span>' : ""}</span>
    <span>puan <b class="mono">${t.score}</b></span>`;
  $("#editState").hidden = !edited();
  $("#reset").hidden = !edited();
  renderSaveState();

  const cells = {}, spans = {}, timeless = [];
  picks().forEach(p => {
    if(!p.sec.meetings.length){ timeless.push(p); return; }
    p.sec.meetings.forEach(m => {
      const a = Math.max(0, Math.floor((m.start-T0)/STEP));
      const b = Math.min(ROWS, Math.ceil((m.end-T0)/STEP));
      cells[`${m.day}-${a}`] = {p, m, span: Math.max(1, b-a)};
      for(let r=a+1; r<b; r++) spans[`${m.day}-${r}`] = true;
    });
  });

  let html = `<thead><tr><th></th>${DAYS.map(d=>`<th>${d}</th>`).join("")}</tr></thead><tbody>`;
  for(let r=0; r<ROWS; r++){
    const min = T0 + r*STEP, onHour = min % 60 === 0;
    html += `<tr class="${onHour ? "hr" : "half"}"><td class="hour mono">${
      onHour ? hhmm(min) : ""}</td>`;
    for(let d=1; d<=5; d++){
      const key = `${d}-${r}`;
      if(spans[key]) continue;
      const c = cells[key];
      if(!c){
        html += `<td class="free" data-day="${d}" data-min="${min}" tabindex="0"
          role="button" aria-label="${DAYS[d-1]} ${hhmm(min)} boş — ders ekle"></td>`;
        continue;
      }
      html += `<td rowspan="${c.span}"><div class="blk" data-role="${c.p.cand.role}"
          data-course="${esc(c.p.cand.course)}" tabindex="0" role="button">
          <b class="mono">${esc(c.p.cand.course)}</b>
          <small class="mono">${hhmm(c.m.start)}–${hhmm(c.m.end)}
            ${esc(c.m.building)}</small></div></td>`;
    }
    html += `</tr>`;
  }
  $("#grid").innerHTML = html + `</tbody>`;
  $("#grid").querySelectorAll(".blk").forEach(el =>
    bind(el, () => courseDialog(el.dataset.course)));
  $("#grid").querySelectorAll("td.free").forEach(el =>
    bind(el, () => slotDialog(+el.dataset.day, +el.dataset.min)));

  renderDayList();

  $("#notime").innerHTML = timeless.length ? `
    <div class="eyebrow" style="margin-bottom:6px">Saati ilan edilmemiş</div>
    <div class="blocklist">${timeless.map(p =>
      `<div class="blockitem" data-course="${esc(p.cand.course)}" tabindex="0"
         role="button" style="cursor:pointer"><b class="mono">${esc(p.cand.course)}</b>
        <span class="tag ${p.cand.role}" style="margin-left:4px">${p.cand.role}</span>
        CRN ${esc(p.sec.crn)} · ${p.cand.credits} kredi</div>`).join("")}</div>` : "";
  $("#notime").querySelectorAll("[data-course]").forEach(el =>
    bind(el, () => courseDialog(el.dataset.course)));

  renderCandidates();
}

function bind(el, fn){
  el.addEventListener("click", fn);
  el.addEventListener("keydown", e => {
    if(e.key === "Enter" || e.key === " "){ e.preventDefault(); fn(); }
  });
}

/* ---------- seçim işlemleri ---------- */
function choose(course, crn){
  const cand = CAND[course], sec = sectionOf(course, crn);
  if(!cand || !sec) return;
  sel = sel.filter(x => x.course !== course);
  const drop = new Set(conflictsWith(sec, course).map(p => p.cand.course));
  const pool = poolBlocker(cand, course);
  if(pool) drop.add(pool.cand.course);
  sel = sel.filter(x => !drop.has(x.course));
  sel.push({course, crn});
  render();
}
function removeCourse(course){
  sel = sel.filter(x => x.course !== course);
  render();
}

/* ---------- diyaloglar ---------- */
function openDialog(html){
  $("#detailBody").innerHTML = html +
    `<div style="margin-top:16px;text-align:right">
       <button class="ghost" data-close>Kapat</button></div>`;
  $("#detailBody").querySelectorAll("[data-close]").forEach(b =>
    b.addEventListener("click", () => $("#detail").close()));
  $("#detailBody").querySelectorAll(".opt").forEach(b =>
    b.addEventListener("click", () => {
      choose(b.dataset.course, b.dataset.crn);
      $("#detail").close();
    }));
  $("#detail").showModal();
}

function optionRow(cand, section, note){
  const times = section.meetings.length
    ? section.meetings.map(m =>
        `${DAYS[m.day-1]} ${hhmm(m.start)}–${hhmm(m.end)} ${esc(m.building)}`).join("<br>")
    : "saat ilan edilmemiş";
  return `<button class="opt" data-course="${esc(cand.course)}" data-crn="${esc(section.crn)}">
      <span><b class="mono">${esc(cand.course)}</b>
        <span class="tag ${cand.role}" style="margin-left:6px">${cand.role}</span>
        <div class="meta">${esc(cand.name)} · ${cand.credits} kredi / ${cand.ects} AKTS
          · puan ${cand.score}${note ? " · " + esc(note) : ""}</div></span>
      <span class="meta mono" style="text-align:right;white-space:nowrap">
        CRN ${esc(section.crn)}<br>${section.enrolled}/${section.capacity}<br>${times}</span>
    </button>`;
}

function courseDialog(course){
  const cand = CAND[course], cur = sel.find(x => x.course === course);
  if(!cand || !cur) return;
  const others = cand.sections.filter(s => s.crn !== cur.crn);
  const fits = others.filter(s => conflictsWith(s, course).length === 0);
  const busy = others.length - fits.length;
  const swaps = swapOptions(cand);

  openDialog(`
    <div class="eyebrow">${cand.role === "ANADAL" ? "Anadal dersi" : LBL + " dersi"}${
      cand.pool ? " · havuz: " + esc(cand.pool) : ""}</div>
    <h2 class="mono">${esc(cand.course)}</h2>
    <div style="color:var(--ink-2);font-size:13px;margin:2px 0 6px">${esc(cand.name)}</div>
    <div class="meta" style="color:var(--ink-3);font-size:12px">
      ${cand.credits} kredi · ${cand.ects} AKTS · puan ${cand.score}
      ${cand.reasons.length ? "<br>" + cand.reasons.map(esc).join("; ") : ""}</div>
    ${fits.length ? `<div class="chipline"><span class="chip">başka şube</span>
      <span style="color:var(--ink-3);font-size:12px">${fits.length} seçenek</span></div>
      <div class="optlist">${fits.map(s => optionRow(cand, s, "")).join("")}</div>` : ""}
    ${busy ? `<div style="color:var(--ink-3);font-size:12px;margin-top:10px">
      ${busy} şube daha var ama programınla çakışıyor.</div>` : ""}
    <div class="chipline"><span class="chip unknown">yerine başka ders</span></div>
    <div class="optlist">${swaps.join("") ||
      `<div class="empty">bu saatlere uyan başka aday yok</div>`}</div>
    <div style="margin-top:14px;display:flex;gap:8px;flex-wrap:wrap">
      <button class="ghost danger" id="removeCourse">Programdan çıkar</button>
      ${watchButton(cand.course)}
    </div>
    ${watchNote(cand.course)}`);
  const rm = $("#removeCourse");
  if(rm) rm.addEventListener("click", () => { $("#detail").close(); removeCourse(course); });
  wireWatch();
}

/* ---------- Kontenjan nöbeti listesi (yapılacaklar 4.3) ----------
   `make watch` izleme listesi settings.toml'daydı; ders başına düğme yoktu.

   ★ Boş liste "planındaki bütün açık dersleri izle" demek (191 ders) — her
   turda bir şey değişir, bildirim gürültüye döner. Yani ilk ders eklemek
   listeyi genişletmiyor, DARALTIYOR. Bu ters sezgi, düğmenin yanında
   açıkça yazılmadan bırakılamaz. */
function watching(){
  return new Set((SETUP && SETUP.watchCourses) || []);
}

function watchButton(course){
  if(!DATA.live) return "";
  const on = watching().has(course);
  return `<button class="ghost" id="watchBtn" data-course="${esc(course)}"
    style="${on ? "color:var(--cap);border-color:var(--cap)" : ""}"
    >${on ? "İzlemeyi bırak" : "Kontenjanı izle"}</button>`;
}

function watchNote(course){
  if(!DATA.live) return "";
  const list = watching();
  if(list.has(course))
    return `<div class="why" style="margin-top:8px">İzlenenler:
      <span class="mono">${[...list].map(esc).join(", ")}</span>.
      <span class="mono">make watch</span> çalışınca bunlar taranır.</div>`;
  if(list.size === 0)
    return `<div class="why" style="margin-top:8px">Şu an izleme listesi <b>boş</b>,
      yani <b>nöbet planındaki tüm açık dersleri</b> tarıyor — her turda bir şey
      değişir, bildirim gürültüye döner. Bu dersi eklersen nöbet
      <b>yalnız ona</b> bakar.</div>`;
  return `<div class="why" style="margin-top:8px">İzlenenler:
    <span class="mono">${[...list].map(esc).join(", ")}</span>.</div>`;
}

function wireWatch(){
  const b = $("#watchBtn");
  if(!b) return;
  b.addEventListener("click", async () => {
    b.disabled = true; b.textContent = "…";
    try{
      const r = await api("/api/watch", {course: b.dataset.course});
      applyState(r);
      $("#detail").close();
    }catch(err){ b.disabled = false; b.textContent = "hata: " + err.message; }
  });
}

function swapOptions(cand){
  const rows = [];
  for(const other of M().candidates){
    if(other.course === cand.course) continue;
    if(sel.some(x => x.course === other.course)) continue;
    const ok = other.sections.find(s => conflictsWith(s, cand.course).length === 0);
    if(!ok) continue;
    const pool = poolBlocker(other, cand.course);
    rows.push([other.score - (pool ? 10000 : 0),
      optionRow(other, ok, pool ? `çıkarılır: ${pool.cand.course} (aynı havuz)` : "")]);
  }
  rows.sort((a,b) => b[0]-a[0]);
  return rows.slice(0, 12).map(r => r[1]);
}

/** Bir şubenin, tıklanan saate ne kadar yakın olduğu. null = o gün dersi yok. */
function proximity(section, day, min){
  const WINDOW = 120;                       // ±2 saat "bu civar" sayılır
  let best = null;
  for(const m of section.meetings){
    if(m.day !== day) continue;
    const d = (m.start <= min && min < m.end) ? 0 : Math.abs(m.start - min);
    if(best === null || d < best) best = d;
  }
  return best === null || best > WINDOW ? null : best;
}

function slotDialog(day, min){
  // Hücreyi TAM kapsayan ders olmayabilir (dersler :30'da başlıyor, hücre :00).
  // O yüzden "bu saat civarı" penceresi kullanıyoruz; boşsa o günün tamamı.
  const collect = (near) => {
    const rows = [];
    for(const cand of M().candidates){
      if(sel.some(x => x.course === cand.course)) continue;
      // ★ Havuz engelini GİZLEME. Seçilince zaten takas ediliyor; saklamak
      //   Çarşamba'da 19 adaydan 18'ini görünmez yapıyordu (20.08.2026).
      const pool = poolBlocker(cand, null);
      let pick = null, dist = Infinity;
      for(const s of cand.sections){
        const d = near ? proximity(s, day, min)
                       : (s.meetings.some(m => m.day === day) ? 0 : null);
        if(d === null) continue;
        const blocked = conflictsWith(s, null).length;
        const cost = blocked * 10000 + d;
        if(cost < dist){ dist = cost; pick = s; }
      }
      if(!pick) continue;
      const drop = conflictsWith(pick, null).map(p => p.cand.course);
      if(pool) drop.push(pool.cand.course + " (aynı havuz)");
      rows.push([-(drop.length * 10000) - dist % 10000 + cand.score / 1000,
        optionRow(cand, pick, drop.length ? "çıkarılır: " + drop.join(", ") : ""),
        cand.course]);
    }
    rows.sort((a,b) => b[0]-a[0]);
    return rows;
  };
  const near = collect(true);
  const nearCodes = new Set(near.map(r => r[2]));
  const rest = collect(false).filter(r => !nearCodes.has(r[2]));
  openDialog(`
    <div class="eyebrow">Boş saat</div>
    <h2>${DAYS[day-1]} ${hhmm(min)}</h2>
    ${near.length ? `<div class="chipline"><span class="chip">bu saat civarı</span>
        <span style="color:var(--ink-3);font-size:12px">${near.length} ders</span></div>
      <div class="optlist">${near.slice(0, 12).map(r => r[1]).join("")}</div>` : ""}
    ${rest.length ? `<div class="chipline"><span class="chip unknown">${
        DAYS[day-1]} günü, başka saatte</span>
        <span style="color:var(--ink-3);font-size:12px">${rest.length} ders</span></div>
      <div class="optlist">${rest.slice(0, 12).map(r => r[1]).join("")}</div>` : ""}
    ${(!near.length && !rest.length)
      ? `<div class="empty">bu güne uyan aday ders yok</div>` : ""}`);
}

$("#reset").addEventListener("click", () => resetTo(active));

/* ---------- aday listesi ---------- */
function renderCandidates(){
  const chosen = new Set(sel.map(x => x.course));
  $("#cands tbody").innerHTML = M().candidates.slice(0, 30).map(c => {
    const free = Math.max(0, ...c.sections.map(s => s.free));
    const inPlan = chosen.has(c.course);
    return `<tr data-course="${esc(c.course)}" style="cursor:pointer"
        title="${inPlan ? "programında" : "programa ekle"}">
      <td class="mono score">${c.score}</td>
      <td><b class="mono">${esc(c.course)}</b>
        ${inPlan ? `<span class="chip" style="margin-left:6px;color:var(--anadal)">programda</span>` : ""}
        ${c.critical ? `<span class="chip supply" style="margin-left:6px">kritik yol</span>` : ""}
        <div class="why">${esc(c.name)}${c.reasons.length
          ? " — " + c.reasons.map(esc).join("; ") : ""}</div></td>
      <td><span class="tag ${c.role}">${c.role}</span></td>
      <td class="mono">${c.credits}</td>
      <td class="mono" style="color:var(--ink-3)">${c.ects}</td>
      <td class="mono">${c.sections.length} (boş ${free})</td>
    </tr>`;
  }).join("") || `<tr><td colspan="6" class="empty">aday ders yok</td></tr>`;
  $("#cands tbody").querySelectorAll("tr[data-course]").forEach(tr =>
    tr.addEventListener("click", () => addDialog(tr.dataset.course)));
}

function addDialog(course){
  const cand = CAND[course];
  if(!cand) return;
  if(sel.some(x => x.course === course)) return courseDialog(course);
  const rows = cand.sections.map(s => {
    const blocked = conflictsWith(s, null);
    return [ -blocked.length, optionRow(cand, s,
      blocked.length ? "çıkarılır: " + blocked.map(p => p.cand.course).join(", ") : "") ];
  });
  rows.sort((a,b) => b[0]-a[0]);
  const pool = poolBlocker(cand, null);
  openDialog(`
    <div class="eyebrow">Programa ekle</div>
    <h2 class="mono">${esc(cand.course)}</h2>
    <div style="color:var(--ink-2);font-size:13px;margin:2px 0 6px">${esc(cand.name)}</div>
    ${pool ? `<div class="note" style="margin-top:8px">Aynı havuzdan
      <b class="mono">${esc(pool.cand.course)}</b> seçili — bunu eklersen o çıkar.</div>` : ""}
    <div class="optlist">${rows.map(r => r[1]).join("")}</div>`);
}

/* ---------- darboğaz ---------- */
const LABELS = {
  KREDI_ESIGI:["kredi eşiği dolmamış","credit"],
  PROGRAMA_KAPALI:["şubeleri programına kapalı","supply"],
  ACILMAMIS:["bu dönem açılmamış","supply"],
  ONSART:["önşart eksik","prereq"],
  BILINMIYOR:["önşart okunamadı","unknown"],
};
/* ---------- Başvurabilir miyim (yapılacaklar 1.3) ----------
   ★ Üç durumlu işaret: ✓ sağlanıyor · ✗ sağlanmıyor · — BURADAN BAKILAMAZ.
   Üçüncüsü şart: yönergedeki "üst %20 sıralama" şartını hesaplayamıyoruz.
   Onu sessizce atlamak, karşılanmamış olabilecek bir şartı karşılanmış
   göstermek olurdu — bu araçtaki en pahalı hata türü. */
let basvuruKind = "cap";

function renderBasvuru(){
  const all = DATA.basvuru;
  const sec = $("#basvuruSection");
  if(!all || !sec) return;
  sec.hidden = false;
  const KINDS = [["cap", "Çift anadal"], ["yandal", "Yandal"]];
  $("#basvuruTabs").innerHTML = KINDS.map(([k, lbl]) =>
    `<button class="tab" role="tab" data-k="${k}"
       aria-selected="${k === basvuruKind}">${lbl}</button>`).join("");
  $("#basvuruTabs").querySelectorAll(".tab").forEach(b =>
    b.addEventListener("click", () => { basvuruKind = b.dataset.k; renderBasvuru(); }));

  const s = all[basvuruKind];
  if(!s){ $("#basvuruBody").innerHTML = `<div class="empty">veri yok</div>`; return; }

  const mark = c => c.ok === null ? "—" : (c.ok ? "✓" : "✗");
  const color = c => c.ok === null ? "var(--ink-3)"
    : (c.ok ? "var(--anadal)" : "var(--danger)");
  const checks = s.checks.map(c => `
    <div class="blockitem" style="border-left:5px solid ${color(c)}">
      <b style="color:${color(c)}">${mark(c)}</b> ${esc(c.label)}
      <div class="why">${esc(c.detail)}${c.source
        ? ` <span style="opacity:.7">· ${esc(c.source)}</span>` : ""}</div>
    </div>`).join("");

  const verdict = !s.eligible
    ? `<b style="color:var(--danger)">Bilinen şartlardan en az biri
       şu an sağlanmıyor.</b>`
    : s.unknownCount
      ? `<b style="color:var(--anadal)">Bakılabilen şartlar tamam.</b>
         ${s.unknownCount} şart bu araçtan doğrulanamıyor — yukarıda “—” ile işaretli.`
      : `<b style="color:var(--anadal)">Bakılabilen tüm şartlar sağlanıyor.</b>`;

  /* ⚠️ Kalan KREDİ sütunu YOK ve bu bilinçli (22.08.2026).
     Kullanıcı sayının yanlış çıktığını bildirdi; iki sebebi vardı — kendi
     ÇAP'ı için beyan ettiği denklikler her programın planına uygulanıyordu,
     ve havuz slotlarının kredisi programdan programa farklı sayılıyor.
     Denklik kapsamı düzeltildi ama kredi hâlâ duramayacağımız bir tahmin.
     Yerine SAĞLAM olan duruyor: birebir kodu tutan, geçilmiş ders sayısı. */
  const rows = s.options.map(o => `
    <tr><td class="mono"><b>${esc(o.code)}</b></td>
      <td>${esc(o.name)}<div class="why">${esc(o.iteration || o.planTitle)}</div></td>
      <td class="mono">${o.slotsTotal}</td>
      <td class="mono">${o.alreadyCount
        ? `<b style="color:var(--anadal)">${o.alreadyCount}</b>` : "0"}
        ${o.alreadyCount ? `<div class="why mono">${o.already.slice(0,4).map(esc).join(", ")}${
          o.alreadyCount > 4 ? " …" : ""}</div>` : ""}</td></tr>`).join("");

  $("#basvuruBody").innerHTML = `
    <div class="note" style="margin:12px 0">${verdict}</div>
    <div class="blocklist" style="margin-bottom:16px">${checks}</div>
    ${s.optionCount ? `
      <div class="chipline"><span class="eyebrow">Sana açık programlar</span>
        <span class="chip credit">${s.optionCount}</span></div>
      <div style="overflow-x:auto"><table class="list">
        <thead><tr><th>Kod</th><th>Program</th><th>Ders sayısı</th>
          <th>Sende sayılan</th></tr></thead>
        <tbody>${rows}</tbody></table></div>
      <div class="why" style="margin-top:8px">“Sende sayılan” = bu planda
        <b>birebir kodu tutan</b>, geçtiğin ders. Kalan kredi yazmıyoruz:
        havuz slotlarının nasıl sayıldığı programdan programa değişiyor,
        duramayacağımız bir sayı olurdu.</div>` : `
      <div class="empty">Anadalına açık ${basvuruKind === "cap" ? "ÇAP" : "yandal"}
        planı bulunamadı.</div>`}
    ${s.otherHost ? `
      <div class="why" style="margin-top:8px">${s.otherHost} plan
        <b>başka anadalların</b> ${basvuruKind === "cap" ? "ÇAP" : "yandal"}'ı
        olduğu için listelenmedi — ÇAP planları (anadal, hedef) çiftine göre
        tanımlı, başka bölümün planına başvuramazsın.</div>` : ""}
    ${s.missingCount ? `
      <div class="note" style="margin-top:14px">
        <b>${s.missingCount}</b> programın ${basvuruKind === "cap" ? "ÇAP" : "yandal"}
        planı henüz çekilmemiş, o yüzden listede yoklar.
        <b>Lisans planından tahmin YAPILMIYOR</b> — ${basvuruKind === "cap" ? "ÇAP" : "yandal"}
        planı lisansın küçük bir alt kümesi, oradan hesaplamak kalan işi
        iki katından fazla şişirirdi. Doldurmak için:
        <span class="mono">make all-plans</span>.
      </div>` : ""}`;
}

function renderBlockers(){
const groups = {};
DATA.blockers.forEach(b => (groups[b.reason] = groups[b.reason] || []).push(b));
let bhtml = "";
["PROGRAMA_KAPALI","ACILMAMIS","ONSART","KREDI_ESIGI","BILINMIYOR"].forEach(k => {
  const items = groups[k]; if(!items) return;
  const [label, cls] = LABELS[k];
  bhtml += `<div class="chipline"><span class="chip ${cls}">${label}</span>
    <span style="color:var(--ink-3);font-size:12.5px">${items.length} ders</span></div>
    <div class="blocklist">${items.map(b => {
      /* ★ Yalnız ARZ sorunlu derste izleme düğmesi var: "açılmamış" ya da
         "programa kapalı" ders sonradan açılabilir, kontenjan değişebilir.
         Önşart ya da kredi eşiği takılması nöbetle çözülmez — oraya düğme
         koymak, işe yaramayacak bir eylem önermek olurdu. */
      const watchable = DATA.live && (k === "ACILMAMIS" || k === "PROGRAMA_KAPALI");
      const on = watchable && watching().has(b.course);
      return `<div class="blockitem"><b class="mono">${esc(b.course)}</b> ${esc(b.detail)}
        ${watchable ? `<button class="watchmini" data-course="${esc(b.course)}"
          style="margin-left:6px;font-size:10.5px;letter-spacing:.05em;
          text-transform:uppercase;border:1px solid currentColor;padding:1px 6px;
          color:${on ? "var(--cap)" : "var(--ink-3)"}"
          >${on ? "izleniyor" : "izle"}</button>` : ""}</div>`;
    }).join("")}</div>`;
});
const supply = (groups.ACILMAMIS||[]).length + (groups.PROGRAMA_KAPALI||[]).length;
if(supply > (groups.ONSART||[]).length){
  bhtml += `<div class="note" style="margin-top:18px">Engelin çoğu önşart değil,
    <b>arz</b>: ders açılmıyor ya da şubeler başka programlara ayrılmış. Bölümle
    veya danışmanla konuşmak, sıralamayı iyileştirmekten daha çok işe yarar.</div>`;
}
if(DATA.lessonCount < 5000){
  bhtml += `<div class="note" style="margin-top:10px">Ders programında şu an
    <span class="mono">${DATA.lessonCount}</span> şube var. Dönem başlarında ilanlar
    kademeli yayınlanıyor — "açılmamış" dersler sonradan çıkabilir.</div>`;
}
$("#blockers").innerHTML = bhtml || `<div class="empty">Engel yok.</div>`;
$("#blockers").querySelectorAll(".watchmini").forEach(b =>
  b.addEventListener("click", async () => {
    b.disabled = true; b.textContent = "…";
    try{ applyState(await api("/api/watch", {course: b.dataset.course})); }
    catch(err){ b.disabled = false; b.textContent = "hata"; }
  }));
$("#blockSection").hidden = !DATA.blockers.length;
}

/* ---------- kademeler ---------- */
function renderTiers(){
$("#tiers").innerHTML = DATA.tiers.map(t => `
  <div class="tier">
    <h3>Kademe ${t.tier} · ${t.courses.reduce((a,c)=>a+c.credits,0)} kredi</h3>
    <ul>${t.courses.map(c => `<li data-s="${c.status}">
      <span class="mono">${esc(c.course)}</span>
      <span class="mono" style="color:var(--ink-3)">${c.credits}</span></li>`).join("")}</ul>
  </div>`).join("") || `<div class="empty">kademe verisi yok</div>`;
}

/* ★ Tek giriş noktası. Sunucudan yeni durum gelince (program/dönem/transkript
   değişti) sayfa yenilenmeden buradan yeniden çiziliyor. */
function boot(){
  setupBar();
  renderHeader();
  renderGpa();
  renderLoad();
  renderCredits();
  renderSuggestions();
  renderChanges();
  wireRefresh();
  wirePicks();
  renderBlockers();
  renderBasvuru();
  renderTiers();
  useMode(0);
}
boot();
</script>
</body>
</html>
"""
