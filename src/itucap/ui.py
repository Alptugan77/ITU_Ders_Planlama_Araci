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
from . import prereq as PRQ
from . import recommend as REC
from . import rules as R
from . import sequence as SEQ
from . import student as S


def _busy_info(declared) -> list[dict]:
    """Meşgul saatleri arayüze taşır — ham metniyle birlikte.

    ★ `raw` şart: silme işlemi metnin kendisiyle yapılıyor. İndeksle
    silseydik, iki sekme açıkken listeler kayar ve kullanıcı yanlış aralığı
    silerdi.

    Anlaşılmayan satır DÜŞMÜYOR, `ok=False` ile geliyor: sessizce yok saymak,
    kullanıcının koyduğunu sandığı bir kısıtın uygulanmadığını gizlerdi.
    """
    from .normalize import parse_busy

    out = []
    for raw in declared or ():
        raw = str(raw)
        b = parse_busy(raw)
        if b is None:
            out.append({"raw": raw, "ok": False})
            continue
        out.append({**b, "raw": raw, "ok": True})
    return out


def _basvuru_info(con: sqlite3.Connection, ucon: sqlite3.Connection,
                  student_id: int, settings) -> dict | None:
    """Başvurulabilirlik taraması — iki tür için de (ÇAP ve yandal).

    Kullanıcı ÇAP yapıyor olsa da yandal sorusu ayrı bir soru; ikisini de
    hesaplayıp arayüze veriyoruz, seçim kullanıcıda.
    """
    from . import basvuru as B

    try:
        # İki ikinci program da hariç: zaten kayıtlı olduğun programı
        # "başvurabilirsin" diye listelemek anlamsız.
        exclude = {settings.anadal_program, *(s[3] for s in settings.seconds)}
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
                    student_id: int, gpa, seconds: list[dict]) -> list[dict]:
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
    graded = S.graded(ucon, student_id)
    uncertain = S.uncertain_grades(ucon, student_id)
    kapsamlar = ([(s["kind"], s["label"], s["planId"]) for s in seconds]
                 or [("genel", "", None)])

    # ★ 4. incelik (23.08.2026): ÇAP ve yandal AYNI ANDA olabiliyor ve
    # eşikleri FARKLI maddelerden geliyor (Madde 18 / Madde 22). Tek kapsamla
    # hesaplasaydık biri öbürünün kuralıyla değerlendirilirdi — bu araçtaki
    # en pahalı hata türü, çünkü ekranda doğru görünür.
    out: list[dict] = []
    gorulen: dict[str, dict] = {}
    for scope, scope_label, plan_id in kapsamlar:
        # İkinci anadalın KENDİ ortalaması — yalnız O PLANIN dersleri.
        second_gpa = None
        if plan_id:
            subset = {c: g for c, g in graded.items()
                      if c in R.plan_codes(con, plan_id)}
            if subset:
                g2 = POL.gpa(con, subset, uncertain)
                if g2.counted:
                    second_gpa = g2

        for t in POL.load_thresholds(program=scope):
            if t.key in gorulen:
                # İki kapsamda da çıkan eşik GENEL bir kuraldır (ör. mezuniyet
                # GNO 2.00). İki kez göstermek, iki ayrı şart varmış izlenimi
                # verirdi.
                gorulen[t.key]["scope"] = "genel"
                gorulen[t.key]["scopeLabel"] = ""
                continue
            against, basis = gpa.value, "genel"
            item = {"key": t.key, "label": t.label, "min": t.minimum,
                    "verified": t.verified, "note": t.note,
                    "kind": t.kind, "source": t.source,
                    "scope": scope, "scopeLabel": scope_label}
            if t.key == "cap_mezuniyet_ikinci":
                if second_gpa is None:
                    item.update({"basis": "ikinci anadal", "ok": None,
                                 "why": "ÇAP planında notlu ders yok — "
                                        "ikinci anadal ortalaması henüz "
                                        "hesaplanamıyor."})
                    out.append(item)
                    gorulen[t.key] = item
                    continue
                against, basis = second_gpa.value, "ikinci anadal"
            item.update({"basis": basis, "value": against,
                         "tolerance": t.tolerance,
                         "ok": against + 1e-9 >= t.minimum})
            out.append(item)
            gorulen[t.key] = item
    return out


def second_programs(settings: config.Settings, cap_id: int | None,
                    yandal_id: int | None) -> list[dict]:
    """Etkin ikinci programlar: [{kind, role, label, program, planId}, …].

    ★ ÇAP ve yandal AYNI ANDA alınabiliyor (kullanıcı teyidi 23.08.2026).

    ⚠️ İki çağrı biçimi var ve ikisini de bozmadan taşımak gerekiyordu:
      * `collect(..., cap_id)` — TEK ikinci program; hangi tür olduğunu
        `settings.second_kind` söylüyor. Eski çağrılar (testler, `make ui`)
        böyle. `cap_id` adı tarihsel; içi yandal planı da olabilir.
      * `collect(..., cap_id, yandal_id=…)` — ikisi birden.
    """
    if yandal_id is None:
        kinds = settings.second_kinds
        if not kinds or cap_id is None:
            return []
        kind = kinds[0]
        rol, etiket, _ = config.SECOND_KINDS[kind]
        return [{"kind": kind, "role": rol, "label": etiket,
                 "program": settings.program_of(kind), "planId": cap_id}]
    out = []
    for kind, pid in (("cap", cap_id), ("yandal", yandal_id)):
        if pid is None:
            continue
        rol, etiket, _ = config.SECOND_KINDS[kind]
        out.append({"kind": kind, "role": rol, "label": etiket,
                    "program": settings.program_of(kind), "planId": pid})
    return out


def collect(con: sqlite3.Connection, ucon: sqlite3.Connection, student_id: int,
            settings: config.Settings, anadal_id: int | None, cap_id: int | None,
            max_load: float | None = None, n_schedules: int = 3,
            donem: int | None = None, yandal_id: int | None = None,
            seconds: list[dict] | None = None) -> dict:
    """`seconds` verilirse ikinci programlar DOĞRUDAN oradan gelir.

    ★ Sunucu bunu kullanıyor. `cap_id` konumsal argümanı tarihsel bir
    isim — içinde yandal planı da olabiliyordu ve "hangi tür" sorusunun
    cevabı `settings.second_kind`'daydı. İki program birden gelince bu
    belirsizlik hataya döndü (yandal seçiliyken rol CAP çıkıyordu), o yüzden
    çağıran taraf artık listeyi açıkça verebiliyor.
    """
    grades = S.grades(ucon, student_id)
    equivalences = R.load_equivalences(con)
    if seconds is None:
        seconds = second_programs(settings, cap_id, yandal_id)
    seconds = [s for s in seconds if s.get("planId")]
    # Tekil değerler eski davranış için: İLK ikinci program.
    second_role = (seconds[0]["role"] if seconds else "") or "CAP"
    second_label = (seconds[0]["label"] if seconds else "") or "ÇAP"
    # ★ Yarıyıl tabanı ve ÇAP mezuniyet ortalaması YALNIZ ÇAP'a ait
    # (Yönerge Madde 18 / MADDE 17). Yandal planını ÇAP kurallarıyla
    # değerlendirmek, uygulanmayan bir kuralda "kaldın" demek olurdu.
    cap_plan_id = next((s["planId"] for s in seconds if s["kind"] == "cap"), None)

    panels = []
    for plan_id, role in ((anadal_id, "ANADAL"),
                          *((s["planId"], s["role"]) for s in seconds)):
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
    # ★ Kredi tavanı GNO'dan (MADDE 17/2-a) — kullanıcı isteği 23.08.2026.
    # Elle yazılan tavan GNO değiştiğinde eskiyor ve kimse güncellemiyor;
    # motor da kayıtta reddedilecek bir program öneriyordu.
    #
    # ⚠️ Üç emniyet:
    #   * Açık çağrıdaki `max_load` her zaman kazanır (testler, `--max-load`).
    #   * `max_load_auto = false` ile elle ayar geri gelir.
    #   * Tavan YALNIZ birim 'kredi' iken otomatik — yönetmelik krediden
    #     konuşuyor, AKTS tavanı diye bir madde yok; AKTS'ye çevirmek
    #     uydurma olurdu.
    limit = settings.max_load if max_load is None else max_load
    limit_source = "ayar" if max_load is None else "çağrı"
    if max_load is None and settings.max_load_auto and settings.unit == "kredi":
        _gpa_now = POL.gpa(con, S.graded(ucon, student_id),
                           S.uncertain_grades(ucon, student_id))
        # ★ MADDE 17/1 muafiyeti ÇAP öğrencisine ait. İki program birden
        # varsa muafiyet yine geçerli — belirleyici olan ÇAP'ın varlığı.
        _rule = POL.load_limit(_gpa_now.value,
                               second_kind=("cap" if "cap" in settings.second_kinds
                                            else settings.second_kind))
        if _rule and _rule.maximum:
            limit, limit_source = _rule.maximum, "yönetmelik"
    limit_credits = limit if settings.unit == "kredi" else 0.0

    def build(max_term):
        cs = REC.candidates(con, ucon, student_id, anadal_id,
                            seconds[0]["planId"] if seconds else None,
                            settings.anadal_program, settings.second_program,
                            settings.allowed_programs, settings.unit,
                            second_role=second_role, max_term=max_term,
                            second_plans=[(s["role"], s["planId"]) for s in seconds])
        # ★ Meşgul saatler `fixed` olarak giriyor: motor onları "zaten dolu"
        # sayıyor ve çakışan şubeyi hiç önermiyor. Ayrı bir çakışma yolu
        # yazmak iki tanım demek olurdu (bkz. REC.busy_sections).
        return cs, REC.build_schedules(cs, max_load=limit, limit=n_schedules,
                                       fixed=busy, floors=floors)

    busy = REC.busy_sections(settings.mesgul)
    # ★ Yarıyıl kredi tabanı artık motora GİRİYOR (yapılacaklar 1.4).
    # Faz 13'ten beri yalnız bir uyarıydı; gerçek veride önerilen program
    # ikinci anadaldan 4 kredi içeriyordu, taban 9'du.
    #
    # ⚠️ İNDİRİMLİ değil İLAN EDİLEN taban kullanılıyor: yönerge indirimi
    # "düşürülebilir" diyor (talep + koordinatör + FYK). Otomatik uygulamak,
    # alınmamış bir kararı alınmış saymak olurdu.
    _floor = POL.second_floor(settings.cap_baslangic_yariyili) if cap_plan_id else None
    floors = {"CAP": _floor.minimum} if _floor else None
    cands, schedules = build(None)
    # ★ İkinci kip: dönemlik + alttan. Ayrı bir aday havuzu ve ayrı programlar.
    term_cands, term_scheds = build(donem) if donem else ([], [])

    def section_json(sec: REC.Section) -> dict:
        return {
            "crn": sec.crn, "capacity": sec.capacity, "enrolled": sec.enrolled,
            "free": sec.free,
            # ★ 24.08.2026 — öğretim üyesi motorda taşınıyordu ama arayüze hiç
            # çıkmıyordu. Şube seçerken bakılan iki şeyden biri (öbürü saat).
            #
            # ⚠️ OBS ilan edilmemiş hocayı "-" yazıyor (3417 şubenin 887'si).
            # Onu ad diye basmak, "hocası tire" demek olurdu; boş dönüyor ve
            # arayüz o satırı hiç yazmıyor — bilinmeyen, bilinmeyen kalıyor.
            "instructor": _hoca(sec.instructor),
            # ★ Çevrimiçi şube (24.08.2026). `teaching_method` OBS'de 3417
            # şubenin hepsinde dolu, 139'u "Virtual (Online)" — arayüze hiç
            # çıkmıyordu. Kampüse gitmeyen ders, seçimi doğrudan etkiliyor.
            "online": sec.online,
            "meetings": [{"day": m.day, "start": m.start, "end": m.end,
                          "building": _building(m.building), "campus": m.campus}
                         for m in sec.meetings],
        }

    names = {r[0]: r[1] for r in con.execute("SELECT code, name FROM course")}

    # ★ Türkçe arama (24.08.2026). Katalogda İngilizce programın dersi
    # İngilizce adla duruyor: "MAT 271E — Probability". Türkçe düşünen
    # öğrenci "olasılık" arayınca hiçbir şey bulamıyordu.
    #
    # ⚠️ Ad UYDURULMUYOR: yalnız katalogda GERÇEKTEN var olan eş kodun
    # (MAT 271E → MAT 271) adı kullanılıyor ve yalnız farklıysa. Program
    # kodlarında körlemesine son harfi atmak var olmayan bir programa
    # yönlendiriyordu (bkz. HTAE/HTA, Faz 20); burada varlık kontrolü şart.
    def _dil_esi(code: str) -> str:
        """Katalogda GERÇEKTEN var olan öbür dildeki kod; yoksa boş."""
        es = code[:-1] if code.endswith("E") else code + "E"
        return es if es in names else ""

    def _diger_dil(code: str) -> str:
        es = _dil_esi(code)
        ad = names.get(es) if es else None
        return ad if ad and ad != names.get(code) else ""

    def schedules_json(scheds, pool):
        out = []
        for sched in scheds:
            alts = REC.alternatives(sched, pool)
            out.append({
                "ects": sched.ects, "credits": sched.credits, "load": sched.load,
                "score": sched.score,
                "campusChanges": sched.campus_changes(),
                # ★ Taban eksiği program BAŞINA raporlanıyor: motor tabanı
                # karşılayamıyorsa bunu SÖYLÜYOR, sessizce en iyi görünen
                # programı sunmuyor (yapılacaklar 1.4).
                "floorGaps": [{"role": rol, "missing": eksik}
                              for rol, eksik in sched.floor_gaps(floors).items()],
                "creditsByRole": [{"role": rol, "credits": kr}
                                  for rol, kr in sched.credits_by_role().items()],
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

    # ★ "119 dersin önşartı" diyorduk ama HANGİLERİ olduğunu söylemiyorduk.
    # Sayı ikna edici değil, liste ikna edici. Yalnız SENİN planındaki ve
    # HENÜZ GEÇMEDİĞİN dersler yazılıyor — katalogdaki 119 dersin çoğu
    # başka bölümlerin dersi ve senin için bir anlam taşımıyor.
    _trees = PRQ.parsed_trees(con)
    _unlock_map = PRQ.unlock_map(_trees)
    _plan_codes: set[str] = set()
    _my_plan_ids = [pid for pid in ([anadal_id] + [s["planId"] for s in seconds])
                    if pid]
    if _my_plan_ids:
        _isaret = ",".join("?" * len(_my_plan_ids))
        _plan_codes = {r[0] for r in con.execute(
            f"""SELECT DISTINCT course_code FROM plan_slot
                WHERE plan_id IN ({_isaret}) AND course_code IS NOT NULL""",
            _my_plan_ids)}
        _plan_codes |= {r[0] for r in con.execute(
            f"""SELECT DISTINCT po.course_code FROM pool_option po
                JOIN plan_slot ps ON ps.id = po.slot_id
                WHERE ps.plan_id IN ({_isaret})""", _my_plan_ids)}
        # ★ İki dilli kod. Türkçe BLG planı zorunlu dersi 'BLG 355' yazıyor,
        # önşart ağacı 'BLG 355E' diyor: ilk ölçümde 119 dersin KESİŞİMİ SIFIR
        # çıktı. `plan_slot.alt_course_codes` bu eşi taşıyor ama 41480 slotun
        # yalnız 667'sinde dolu — tek başına yetmiyor.
        #
        # ⚠️ Eş körlemesine türetilmiyor: katalogda GERÇEKTEN var olması
        # gerekiyor. Ölçüm (24.08.2026): 2809 E/TR çiftinin 2807'sinde kredi
        # ve AKTS birebir aynı — aynı dersin iki dili olduklarının kanıtı.
        # Kalan 2'si de aynı ders (adları yer değiştirmiş kayıt hatası).
        _plan_codes |= {c for c in (r[0] for r in con.execute(
            f"""SELECT DISTINCT alt_course_codes FROM plan_slot
                WHERE plan_id IN ({_isaret})
                  AND TRIM(COALESCE(alt_course_codes,'')) <> ''""", _my_plan_ids))
            for c in c.split(",") if c}
    _plan_own = set(_plan_codes)            # planda BİREBİR yazan kodlar
    _plan_codes |= {c for c in map(_dil_esi, _plan_codes) if c}
    _passed = {c for c, g in grades.items() if R.passed(g)}
    # Geçilen dersin öbür dildeki kodu da geçilmiş sayılır — yoksa
    # "BLG 351E'yi açar" derken öğrencinin BLG 351'i geçtiğini kaçırırdık.
    _passed |= {c for c in map(_dil_esi, _passed) if c}

    def _acilanlar(code: str) -> list[str]:
        """`code` alınırsa SENİN planında açılacak dersler.

        ⚠️ Dil çifti TEKLEŞTİRİLİYOR: önşart ağacı 'MAT 201' ve 'MAT 201E'yi
        ayrı düğüm olarak taşıyor, ikisini birden yazmak "iki ders açılıyor"
        demek olurdu. Planda birebir yazan varyant tercih ediliyor.
        """
        secili: dict[str, str] = {}
        for k in _unlock_map.get(code, []):
            if k not in _plan_codes or k in _passed:
                continue
            if k == code or k == _dil_esi(code):
                continue
            anahtar = k[:-1] if (k.endswith("E") and _dil_esi(k)) else k
            onceki = secili.get(anahtar)
            if onceki is None or (k in _plan_own and onceki not in _plan_own):
                secili[anahtar] = k
        return sorted(secili.values())

    def candidates_json(pool):
        return [{
            "course": c.course, "name": c.name, "altName": _diger_dil(c.course),
            "role": c.role, "ects": c.ects,
            "credits": c.credits, "slotId": c.slot_id, "planId": c.plan_id,
            "termNo": c.term_no, "pool": c.pool_label,
            "score": c.score, "unlocks": c.unlocks, "critical": c.critical,
            # `unlocks` katalogdaki toplam, `opens` SENİN planındaki liste.
            # İkisi ayrı sayı; birini öbürünün yerine yazmak yanlış olurdu.
            "opens": _acilanlar(c.course),
            "required": c.required, "reasons": c.reasons,
            "sections": [section_json(s) for s in c.sections],
        } for c in pool]

    schedule_json = schedules_json(schedules, cands)

    # ★ Darboğaz HER ikinci program için ayrı hesaplanıyor ve hangisine ait
    # olduğu satırda yazıyor — iki programın engellerini tek listede
    # ayrımsız göstermek "hangi program yüzünden takıldım" sorusunu
    # cevapsız bırakırdı.
    blockers = []
    for s in seconds:
        blockers += [{"course": b.course, "reason": b.reason, "detail": b.detail,
                      "name": names.get(b.course, ""),
                      "role": s["role"], "label": s["label"],
                      "program": s["program"]}
                     for b in REC.cap_blockers(con, ucon, student_id, s["planId"],
                                               s["program"],
                                               settings.allowed_programs)]

    # ★ Kredi eşiği (bitirme çalışması) — kaç kredin var, eşik ne, NEYİ tutuyor.
    # Son madde önemli: kural sessizce eleseydi kullanıcı 'GEO 4901E neden
    # kayboldu' diye soracaktı. Eleyen kural kendini göstermek zorunda.
    rules = POL.load_rules()
    have_credits = POL.earned_credits(con, grades)
    plan_courses = R.plan_codes(con, anadal_id, *(s["planId"] for s in seconds))
    # ★ GNO — transkriptten TAHMİN. Kesinmiş gibi göstermemek için eksiklik
    # kaynakları ayrıca taşınıyor; eşikler doğrulanma durumuyla birlikte.
    gpa = POL.gpa(con, S.graded(ucon, student_id), S.uncertain_grades(ucon, student_id))
    gpa_info = {
        "value": gpa.value, "credits": gpa.credits, "counted": gpa.counted,
        "partial": gpa.partial,
        "noCredit": gpa.skipped_no_credit, "notGraded": gpa.skipped_not_graded,
        "uncertain": gpa.uncertain, "conditional": gpa.conditional,
        "thresholds": _threshold_info(con, ucon, student_id, gpa, seconds),
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
    load_rule = POL.load_limit(gpa.value,
                               second_kind=("cap" if "cap" in settings.second_kinds
                                            else settings.second_kind))
    load_info = None
    if load_rule:
        load_info = {
            "min": load_rule.minimum, "max": load_rule.maximum,
            "exempt": load_rule.exempt_from_minimum,
            "reasons": load_rule.reasons, "verified": load_rule.verified,
            "source": load_rule.source, "declared": limit_credits,
            # ★ Transkript yokken GNO 0.00 bir ÖLÇÜM değil, veri yokluğu.
            # Tavanı "GNO'ndan hesaplandı" diye sunmak yanlış olurdu:
            # en düşük bandı VARSAYIYORUZ ve bunu yazıyoruz.
            "noTranscript": not gpa.counted,
            # Tavan nereden geldi: 'yönetmelik' (GNO'dan otomatik) | 'ayar' | 'çağrı'.
            # Türetilmiş bir sayıyı beyan edilmiş gibi göstermemek için.
            "limitSource": limit_source,
            "conflict": bool(load_rule.maximum
                             and limit_credits > load_rule.maximum + 1e-9),
            "next": ({"max": load_rule.next_band.max_credits,
                      "minGpa": load_rule.next_band.min_gpa}
                     if load_rule.next_band else None),
        }

    # ★ İkinci anadaldan asgari yarıyıl kredisi — MADDE 17'den AYRI kural.
    #   MADDE 17/1 → toplam yük bandı, ÇAP öğrencisi MUAF.
    #   bu kural   → yalnız ikinci anadaldan alınacak TABAN.
    # ÇAP öğrencisinin toplam alt sınırı yok ama ikinci anadal tarafında
    # tabanı var; "muaf" diye bunu da atlamak ilişik kesilmesine götürebilirdi.
    # ★ 23.08.2026: bu kural YALNIZ ÇAP'a ait. Yönerge "İkinci anadala N.
    # yarıyılda başlayan öğrenci…" diyor; "ikinci anadal" = ÇAP. Yandalın
    # kendi maddeleri var (Madde 22+) ve orada böyle bir taban bulamadık.
    # Eskiden ikisine de uygulanıyordu — yandal öğrencisine var olmayan bir
    # kuralla "az aldın" demek olurdu.
    floor_info = None
    if cap_plan_id:
        floor = POL.second_floor(settings.cap_baslangic_yariyili)
        if floor:
            relief = floor.relief
            floor_info = {
                "min": floor.minimum, "startTerm": floor.start_term,
                "verified": floor.verified, "source": floor.source,
                "relief": ({"min": floor.relieved_minimum,
                            "conditions": list(relief.conditions),
                            "deadline": relief.deadline,
                            # ⚠️ Otomatik DEĞİL. Yönerge "düşürülebilir" diyor;
                            # şartı (talep + koordinatör + FYK) ve süresi var.
                            "automatic": relief.automatic}
                           if relief else None),
            }
        elif not settings.cap_baslangic_yariyili:
            # Beyan yok → taban İDDİA EDİLMİYOR, ama sessiz de kalınmıyor:
            # kullanıcı böyle bir kuralın varlığından haberdar olmalı.
            floor_info = {"undeclared": True, "setting": "cap_baslangic_yariyili"}

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

    # ★ Kademeler arasındaki ÖNŞART BAĞLARI (kullanıcı isteği 22.08.2026).
    # `blockers` = bu dersin plan İÇİNDEKİ önşartları; tersini de veriyoruz ki
    # arayüz "bu dersi geçmezsem neler kilitli kalır" sorusunu da çizebilsin.
    # Plan DIŞI önşartlar (`external`) ayrı duruyor: onlar anadalda alınmış
    # olabilir, kademeyi belirlemezler — ikisini karıştırmak yanıltıcı olurdu.
    #
    # ★ 23.08.2026: her ikinci program KENDİ kademelerini alıyor. Tek listede
    # birleştirseydik iki ayrı programın zincirleri birbirine bağlıymış gibi
    # görünürdü — oysa aralarında önşart ilişkisi yok.
    def _tiers_of(plan_id):
        steps = SEQ.plan_sequence(con, plan_id, grades) if plan_id else []
        opens: dict[str, list[str]] = {}
        for st in steps:
            for dep in st.blockers:
                opens.setdefault(dep, []).append(st.course)
        tiers: dict[int, list] = {}
        for st in steps:
            tiers.setdefault(st.tier, []).append(
                {"course": st.course, "name": names.get(st.course, ""),
                 "ects": st.ects or 0, "credits": st.credits or 0,
                 "status": st.status, "unlocks": st.unlocks,
                 "needs": st.blockers, "opens": sorted(opens.get(st.course, [])),
                 "outside": st.external[:6]})
        return [{"tier": k, "courses": v} for k, v in sorted(tiers.items())]

    tier_groups = [{"role": s["role"], "label": s["label"],
                    "program": s["program"], "planId": s["planId"],
                    "tiers": _tiers_of(s["planId"])} for s in seconds]

    return {
        # ★★ İLK ZİYARET (23.08.2026). Program seçilmemişse araç RAPOR
        # ÜRETMİYOR, karşılama ekranı gösteriyor.
        #
        # Eskiden varsayılan program kodları geliştiricinin kendi bölümleriydi
        # ve `settings.toml` siteye girmediği için YAYINLANAN SİTEYE İLK GİREN
        # HERKES o bölümlerin dolu bir raporunu görüyordu: haftalık program,
        # "%0 tamamlandı, 54 ders kaldı"… hiç seçmediği bir bölüm için.
        # Seçilmemiş bir şeyi seçilmiş gibi göstermek, bu araçtaki en temel
        # yanlış — hem de ilk saniyede.
        "onboarding": _onboarding(con, ucon, student_id, settings, anadal_id, seconds),
        "generatedAt": __import__("datetime").datetime.now().strftime("%d.%m.%Y %H:%M"),
        # ★ Faz 25/D3 — VERİNİN YAŞI. `generatedAt` sayfanın üretildiği an;
        # kontenjan ve şube bilgisi ise SON TAZELEMEye ait. İkisi günlerce
        # ayrışabilir: bugün açılan sayfa üç gün önceki kontenjanı gösterir.
        # Tek tarih yazmak, eski sayıyı bugünkü gibi gösteriyordu.
        "dataAge": _veri_yasi(con),
        # ★ Faz 25/D1 — bozuk ayar dosyası. Sessizce varsayılana düşmek,
        # kullanıcıya başka bir bölümün raporunu doğru sandırırdı.
        "settingsError": settings.load_error,
        "term": settings.term,
        "unit": settings.unit, "unitLabel": settings.unit_label,
        "maxLoad": limit,
        "anadal": settings.anadal_program,
        "cap": settings.second_program,
        "secondRole": second_role,
        "secondLabel": second_label,
        # ★ Etkin ikinci programların TAMAMI (ÇAP ve/veya yandal).
        # Tekil `cap`/`secondRole` alanları ilkini gösteriyor ve eski
        # çağrı yerleri için duruyor.
        "seconds": seconds,
        "donem": donem,
        "donemSource": term_source,
        "credits": credit_info,
        "gpa": gpa_info,
        "load": load_info,
        "secondFloor": floor_info,
        # Ders konulamayacak saatler — ızgarada gösteriliyor ve motor
        # bunlarla çakışan şubeyi hiç önermiyor.
        "busy": _busy_info(settings.mesgul),
        "taking": sorted(S.in_progress(ucon, student_id)),
        "panels": panels,
        "candidates": candidates_json(cands),
        "schedules": schedule_json,
        # ★ Dönemlik + alttan kipi: ayrı aday havuzu, ayrı programlar.
        # Sıra ÖNEMLİ — ilk kip açılışta gösterilen kip.
        "modes": _modes(
            {"key": "all", "label": "Tüm adaylar",
             "note": f"{len(cands)} aday · plandaki tüm açık dersler",
             "candidates": candidates_json(cands), "schedules": schedule_json},
            {"key": "term", "label": f"{donem}. dönem + alttan",
             "note": _term_note(term_cands, donem,
                                ("ikinci program" if len(seconds) > 1
                                 else (second_label if seconds else ""))),
             "candidates": candidates_json(term_cands),
             "schedules": schedules_json(term_scheds, term_cands)},
        ) if donem else [],
        "blockers": blockers,
        # ★ FAZ 12 — "başvurabilir miyim" (yapılacaklar 1.3).
        "basvuru": _basvuru_info(con, ucon, student_id, settings),
        # Her ikinci programın KENDİ kademe zinciri.
        "tierGroups": tier_groups,
        "lessonCount": con.execute("SELECT COUNT(*) FROM lesson").fetchone()[0],
        "uncertain": S.uncertain_grades(ucon, student_id),
    }


def _onboarding(con, ucon, student_id, settings, anadal_id, seconds) -> dict | None:
    """Kurulum durumu — eksikse arayüz rapor yerine "buradan başla" gösterir.

    ★★ Faz 26 (24.08.2026) — kullanıcı isteği: "siteye ilk girdiğimde hâlâ
    nasıl yapacağımı anlayamayabilirim." Haklıydı; üç sebebi vardı:

    1. **Üç adım da ZORUNLU görünüyordu.** Oysa yalnız BÖLÜM zorunlu: bölüm
       seçilince araç zaten çalışıyor, öbür ikisi öneriyi İYİLEŞTİRİYOR.
       "Üç adımda kur" demek, ekranın arkasında bir duvar varmış hissi
       veriyordu.
    2. **Yedi düğme üç iş yapıyordu.** Karşılamada üç "Aç" + kurulum
       çubuğunda dört düğme; hangisinin birincil olduğu belli değildi.
    3. **"Aç" bir eylem adı değil.** Neyi açtığı yazmıyordu.

    Artık: tek bir birincil eylem ve adı ne yaptığını söylüyor; zorunlu adım
    ile isteğe bağlı iyileştirmeler AYRI; sırası gelmemiş adım KAPALI.
    """
    adimlar = [
        {"key": "program", "label": "Bölümünü seç",
         "cta": "Bölümünü seç",
         "detail": "Anadal programın. Çift anadal ya da yandal yapmıyorsan "
                   "\u201cYok\u201d bırak.",
         "why": "Araç bundan sonra çalışmaya başlıyor.",
         "sure": "10 saniye", "required": True,
         "done": bool(settings.anadal_program), "action": "program"},
        {"key": "transkript", "label": "Geçtiğin dersleri gir",
         "cta": "Dersleri gir",
         "detail": "En kolayı: transkriptini olduğu gibi yapıştır. İstersen "
                   "plandan tikle.",
         "why": "Neyin kaldığını, önşartların tuttuğunu ve kredi tavanını "
                "bundan çıkarıyor.",
         "sure": "1 dakika", "required": False,
         "done": bool(S.grades(ucon, student_id)), "action": "plan"},
        {"key": "donem", "label": "Bulunduğun dönemi söyle",
         "cta": "Dönemi seç",
         "detail": "Kaçıncı dönemdesin? Tek tıklama.",
         "why": "\u201cN. dönem + alttan\u201d önerisi buna göre kuruluyor.",
         "sure": "5 saniye", "required": False,
         "done": bool(settings.donem), "action": "donem"},
    ]
    eksik = [a for a in adimlar if not a["done"]]
    if not eksik:
        return None
    return {
        # ★ Program yoksa rapor GÖSTERİLMİYOR; sonraki adımlar eksikse rapor
        # duruyor ama üstte ne yapılacağı yazıyor. İkisi farklı: birinde
        # gösterilecek doğru bir şey yok, öbüründe var ama eksik.
        "blocking": not settings.anadal_program,
        "steps": adimlar,
        # ⚠️ BÖLÜM sayısı, plan sayısı değil. `plan` tablosunda her bölümün
        # birden çok sürümü var (445 satır / 127 bölüm); satırı saymak
        # "445 bölüm seçebilirsin" gibi okunuyordu — seçim kutusunda 127 var.
        "planCount": con.execute(
            "SELECT COUNT(DISTINCT program_code) FROM plan "
            "WHERE plan_type='lisans'").fetchone()[0],
        "lessonCount": con.execute("SELECT COUNT(*) FROM lesson").fetchone()[0],
    }


def _veri_yasi(con: sqlite3.Connection) -> dict | None:
    """Şube/kontenjan verisi ne zaman tazelendi.

    ★ Sayfanın üretildiği an (`generatedAt`) ile verinin tazelendiği an
    AYRI şeyler ve günlerce ayrışabiliyor: bugün açılan bir sayfa üç gün
    önceki kontenjanı gösterir. Tek tarih yazmak, eski sayıyı bugünkü gibi
    gösteriyordu.

    ⚠️ Damga yoksa `None` — "bugün" varsaymıyoruz. Bilmemek, taze sanmaktan
    iyidir.
    """
    try:
        ham = con.execute("SELECT MAX(updated_at) FROM lesson").fetchone()[0]
    except sqlite3.Error:
        return None
    if not ham:
        return None
    import datetime as _dt

    try:
        t = _dt.datetime.fromisoformat(str(ham))
    except ValueError:
        return {"raw": str(ham), "days": None, "stale": None}
    simdi = _dt.datetime.now(_dt.timezone.utc) if t.tzinfo else _dt.datetime.now()
    gun = (simdi - t).total_seconds() / 86400
    # ⚠️ "bugün / dün" TAKVİM GÜNÜ demek, "24 saat" değil. Dün 12:50'de
    # tazelenen veri 13 saat sonra hâlâ "bugün" görünüyordu.
    takvim = (simdi.date() - t.date()).days
    return {
        "raw": t.strftime("%d.%m.%Y %H:%M"),
        "days": round(gun, 1),
        "calendarDays": takvim,
        # 2 gün: kayıt haftasında kontenjan bundan çok daha hızlı değişiyor.
        "stale": gun > 2,
    }


_HOCA_YOK = {"", "-", "--", "---", "tba", "tbd", "belirsiz"}


def _hoca(ad: str | None) -> str:
    """İlan edilmemiş öğretim üyesi BOŞ döner, "-" değil.

    OBS ilan edilmemiş hocayı `-` yazıyor: 3417 şubenin 887'si böyle.
    Onu ad diye basmak "hocası tire" demek olurdu; arayüz boş gelen satırı
    hiç yazmıyor, böylece bilinmeyen bilinmeyen kalıyor.
    """
    temiz = (ad or "").strip()
    return "" if temiz.lower() in _HOCA_YOK else temiz


def _building(code: str | None) -> str:
    return "belirsiz" if (code or "").lower() == "undeclared" else (code or "")


def _modes(hepsi: dict, donemlik: dict) -> list[dict]:
    """Kip sırası. İLK sıradaki kip açılışta gösterilir.

    ★ Kullanıcı isteği 22.08.2026: varsayılan "N. dönem + alttan" olsun.
    Kayıt haftasında bakılan şey bu; "tüm adaylar" bir keşif kipi, başlangıç
    noktası değil.

    ⚠️ Ama BOŞ kipe düşürmüyoruz. Dönemlik havuz çakışmasız bir program
    üretemediyse (alttan çok ders, arz yok, saatler çakışıyor) kullanıcı
    açılışta bomboş bir ızgara görür ve bunu "araç bozuk" diye okur.
    O durumda 'Tüm adaylar' önde kalıyor — dolu bir ekran, doğru ama boş bir
    varsayılandan iyidir.
    """
    return [donemlik, hepsi] if donemlik.get("schedules") else [hepsi, donemlik]


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


def render(data: dict, *, deferred: bool = False) -> str:
    """Tek dosyalık arayüz.

    `deferred=True` → veriyi SONRA yükleyen bir kabuk üretir. Statik site
    (GitHub Pages) için: sayfa açılır, Pyodide yüklenir, motor tarayıcıda
    çalışır, sonuç `window.__ITUCAP_APPLY__(data)` ile içeri verilir.

    ★ Şablon kopyalanmıyor — aynı CSS ve aynı JS. İki sürüm çıkarsaydı
    tasarım düzeltmesi birinde yapılır, öbüründe unutulurdu.
    """
    html = _TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=False))
    if deferred:
        html = html.replace("\nboot();\n", "\nwindow.__ITUCAP_APPLY__ = applyState;\n")
    return html


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
<title>Ders Planlama Aracı</title>
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
  /* ★ Yandal AYRI renk: ÇAP ve yandal aynı anda olabiliyor, aynı renkte
     olsalardı panelde ve ızgarada hangisi olduğu anlaşılmazdı. */
  --yandal:#7FB2C9; --yandal-soft:#16252C; --yandal-ink:#A9D2E4;
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
  --yandal:#1F5C77; --yandal-soft:#DCECF4; --yandal-ink:#154457;
    --yandal:#1F5C77; --yandal-soft:#DCECF4; --yandal-ink:#154457;
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
/* ★★ `hidden` GERÇEKTEN gizlesin (24.08.2026 ölçümü).
   Tarayıcının `[hidden]{display:none}` kuralı en zayıf özgüllükte; `.ghost`
   ya da `.radios` gibi display kuran HER sınıf onu eziyor ve `hidden`
   sessizce işlevsiz kalıyordu ("Veriyi tazele" düğmesi gizlenmesi gereken
   yerde duruyordu). Bu tek satır hata sınıfının tamamını kapatıyor. */
[hidden]{display:none !important}
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
.panel[data-role="CAP"]{--accent:var(--cap);--soft:var(--cap-soft)}
.panel[data-role="YANDAL"]{--accent:var(--yandal);--soft:var(--yandal-soft)}
.panel .top{display:flex;align-items:baseline;gap:10px;justify-content:space-between}
.panel .pct{font-family:"IBM Plex Mono",monospace;font-variant-numeric:tabular-nums;
  font-size:27px;font-weight:600;color:var(--accent);letter-spacing:-.03em}
/* ★ Transkript yokken yüzde bir ÖLÇÜM değil: "%0" yerine "—". */
.panel .pct.unknown{color:var(--ink-3)}
.panel .name{color:var(--ink-2);font-size:12.5px;margin:3px 0 15px}
.proj.bilinmiyor{border-left:3px solid var(--warn);padding:8px 10px;
  background:var(--surface-2);margin-bottom:12px;line-height:1.6}

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
/* Aday süzgeci — arama + rol + kontenjan. Tek satır, kartın içinde. */
.candbar{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-top:12px}
.candbar input[type=search]{flex:1 1 240px;min-width:200px}
.candbar .radios{flex:0 0 auto}
.candbar .radios button{flex:0 0 auto;padding:6px 11px}
.tickbox{display:flex;align-items:center;gap:6px;font-size:12.5px;color:var(--ink-2);
  cursor:pointer;white-space:nowrap}
.candcount{margin-left:auto;font-size:12px;color:var(--ink-3);
  font-variant-numeric:tabular-nums}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px}
/* Gelişmiş alan — ilk kurulumda kapalı. Nadir kullanılan bir metin kutusunu
   zorunlu alanların yanına koymak, kurulumu üç kat karmaşık gösteriyordu. */
.adv{margin-top:14px;border-top:1px solid var(--border);padding-top:8px}
.adv>summary{cursor:pointer;font-size:12px;color:var(--ink-3);
  letter-spacing:.06em;text-transform:uppercase}
.adv>summary:hover{color:var(--ink)}
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
.daylist .row[data-role="CAP"]{--accent:var(--cap);--soft:var(--cap-soft);--accent-ink:var(--cap-ink)}
.daylist .row[data-role="YANDAL"]{--accent:var(--yandal);--soft:var(--yandal-soft);--accent-ink:var(--yandal-ink)}
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
.blk[data-role="CAP"]{--accent:var(--cap);--soft:var(--cap-soft);--accent-ink:var(--cap-ink)}
.blk[data-role="YANDAL"]{--accent:var(--yandal);--soft:var(--yandal-soft);--accent-ink:var(--yandal-ink)}
.blk[data-role="PLAN_DISI"],.daylist .row[data-role="PLAN_DISI"]{
  --accent:var(--ink-3);--soft:var(--surface-2);--accent-ink:var(--ink-2)}
/* Ders konulamayacak saat — okul dışı iş. Taralı, çünkü bir DERS değil:
   veri renklerini (yeşil/kehribar) kullansaydı programın parçası sanılırdı. */
.blk.mesgul{--accent:var(--ink-3);border-left-color:var(--border-strong);
  background:repeating-linear-gradient(135deg,var(--surface-2) 0 5px,
    transparent 5px 10px);color:var(--ink-2);cursor:pointer}
.blk.mesgul b{font-weight:600;letter-spacing:.02em}
table.grid td.busycell{background:repeating-linear-gradient(135deg,
  var(--surface-2) 0 5px,transparent 5px 10px)}
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
.tag.CAP{background:var(--cap-soft);color:var(--cap-ink)}
.tag.YANDAL{background:var(--yandal-soft);color:var(--yandal-ink)}
/* CRN'den yüklenen, planlarında olmayan ders — nötr renk, çünkü
   hangi programa saydığını biz bilmiyoruz. */
.tag.PLAN_DISI{background:var(--surface-2);color:var(--ink-3)}
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
/* Öğretim üyesi — şube seçerken bakılan iki şeyden biri (öbürü saat). */
.hoca{color:var(--ink-2);font-size:11px;letter-spacing:.02em}
/* Kontenjan doluluk çubuğu. Sayı okumak yerine bakılabilsin. */
.cap{display:inline-flex;align-items:center;gap:7px;white-space:nowrap;font-size:12px}
.capbar{display:inline-block;width:44px;height:6px;background:var(--surface-2);
  border:1px solid var(--border);overflow:hidden}
.capbar>i{display:block;height:100%;background:var(--ink-3)}
.cap.tight .capbar>i{background:var(--warn)}
.cap.full .capbar>i{background:var(--danger)}
.cap.full{color:var(--danger)}
.capsub{color:var(--ink-3)}
/* Çevrimiçi şube — kampüse gitmiyor, kampüs değişimi de saymıyoruz. */
.chip.online{color:var(--yandal);border-color:var(--yandal)}
/* "Bunu alırsan şunlar açılır" — sayı değil, isim. */
.opens{color:var(--ink-3);font-size:11.5px}
/* Plan dışı kredi — yüke sayılır, şart doldurmaz. İkisini birden söylüyor. */
.planout{color:var(--warn)}
/* Verinin yaşı — kontenjan sayıları buna ait. Bayatladıysa göze girsin. */
.veriyasi{font-size:12px;color:var(--ink-3);margin-top:2px}
.veriyasi.stale{color:var(--warn);font-weight:600}
/* Bozuk ayar dosyası — sayfa açılıyor ama sessiz kalmıyor. */
.note.ayarhata{border-left:3px solid var(--danger);padding-left:10px;
  margin:14px 0}
/* Arz uyarısı — planındaki ders bu dönem alınamıyorsa, ÜSTTE. */
.note.arz{margin-top:10px;border-left:3px solid var(--warn);padding-left:10px}
.note.arz .meta{color:var(--ink-3);font-size:12px}
/* Kayıt öncesi kontrol — üç durumlu (✓ / ✗ / — bakılamaz). */
.checks{display:flex;flex-direction:column;gap:5px;margin-top:6px}
.check{display:flex;gap:8px;align-items:baseline;font-size:13px}
.check .mark{width:14px;text-align:center;font-weight:700}
.check.ok .mark{color:var(--anadal)}
.check.bad .mark{color:var(--danger)}
.check.unknown .mark{color:var(--ink-3)}
.check .meta{color:var(--ink-3);font-size:12px}
/* Yedek plan satırı — çakışan / uyan / dolu ayrı okunsun. */
.yedek{display:flex;gap:8px;flex-wrap:wrap;align-items:baseline;font-size:12.5px;
  padding:3px 0;border-bottom:1px solid var(--border)}
.yedek:last-child{border-bottom:0}
.yedek.uyar>b{color:var(--anadal)}
.yedek.carpisir{color:var(--ink-3)}
.yedek.dolu{color:var(--ink-3);text-decoration:line-through}
.optlist{display:flex;flex-direction:column;gap:6px;margin-top:10px;
  max-height:320px;overflow-y:auto}
.danger{color:var(--danger);border-color:currentColor}

.tiers{padding-bottom:4px}
/* ★ Kademeler AŞAĞI doğru (kullanıcı isteği 23.08.2026). Yan yana sütunlarda
   uzun plan yatay kaydırma istiyordu ve kademe sırası okunmuyordu; aşağı
   akınca sıra doğal olarak okunuyor ve aralara nefes payı sığıyor.
   Bağlantı çizgileri sahnenin İÇİNDE kalmaya devam ediyor. */
.tierstage{position:relative;display:flex;flex-direction:column;gap:34px}
.tierlinks{position:absolute;left:0;top:0;pointer-events:none;overflow:visible;z-index:0}
.tierlinks path{fill:none;stroke:var(--border-strong);stroke-width:1.4;opacity:.55}
.tierlinks path.on{stroke:var(--cap);stroke-width:2.2;opacity:1}
.tierstage.focus .tierlinks path{opacity:.1}
.tierstage.focus .tierlinks path.on{opacity:1}
.tier{position:relative;z-index:1}
.tier h3{font-size:10.5px;color:var(--seal);font-weight:700;margin-bottom:10px;
  letter-spacing:.16em;text-transform:uppercase;
  font-family:"Chivo",Helvetica,Arial,sans-serif;
  padding-bottom:6px;border-bottom:2px solid var(--border-strong)}
.tier ul{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:8px}
.tier li{font-size:12px;padding:6px 10px;border-radius:0;background:var(--surface-2);
  border:1px solid var(--border);display:flex;flex-direction:column;gap:2px;
  cursor:pointer;width:196px}
.tier li .top{display:flex;justify-content:space-between;gap:6px}
.tier li .dep{font-size:10px;line-height:1.35;color:var(--ink-3)}
.tier li .dep.out{font-style:italic}
.tier li[data-s="DONE"]{opacity:.5}
.tier li[data-s="DONE"] .top{text-decoration:line-through}
.tier li[data-s="READY"]{background:var(--cap-soft);color:var(--cap-ink);font-weight:600;
  border-color:var(--cap)}
.tierstage.focus .tier li{opacity:.22}
.tierstage.focus .tier li.on{opacity:1}
.tier li.root{outline:2px solid var(--cap);outline-offset:1px}
.tierfoot{margin-top:10px;font-size:11.5px;color:var(--ink-3);line-height:1.6}
.tiergroup + .tiergroup{margin-top:26px;padding-top:22px;
  border-top:1px dashed var(--border-strong)}
.tiergroup > h3{font-size:13px;margin-bottom:12px;display:flex;gap:8px;align-items:center}
.tiergroup > h3 .tag{font-size:10px}

/* Bölüm çubuğu — yapışkan, tek satır, dar ekranda yana kayıyor. */
/* ⚠️ `var(--bg)` diye bir jeton YOK — doğrusu `--ground`. Yanlış ad
   çözümlenmeyince arka plan ŞEFFAF kalıyor ve kartlar çubuğun içinden
   geçerken üst üste biniyordu (kullanıcı raporu 23.08.2026). */
.secnav{position:sticky;top:0;z-index:30;display:flex;gap:2px;overflow-x:auto;
  background:var(--ground);border-bottom:2px solid var(--border-strong);
  box-shadow:0 6px 14px -8px rgba(0,0,0,.55);
  margin:0 0 18px;padding:8px 0;scrollbar-width:none}
.secnav::-webkit-scrollbar{display:none}
.secnav a{flex:0 0 auto;font-size:11px;letter-spacing:.12em;text-transform:uppercase;
  font-family:"Chivo",Helvetica,Arial,sans-serif;font-weight:700;
  color:var(--ink-3);text-decoration:none;padding:6px 10px;border:1px solid transparent}
.secnav a:hover{color:var(--ink)}
.secnav a[aria-current="true"]{color:var(--seal);border-color:var(--border-strong);
  background:var(--seal-soft)}
.secnav:empty{display:none}
/* Yapışkan çubuk, kaydırınca başlığın üstüne oturmasın diye hedefe pay. */
section[id]{scroll-margin-top:56px}

/* ★ Bölüm seçilmemişken rapor bölümleri GİZLİ. Boş bir ızgara, dolu bir
   yanlış ızgaradan iyidir ama ikisi de gereksiz — kullanıcının yapması
   gereken tek şey var ve o yukarıda duruyor. */
body.kurulum #panels,
body.kurulum #savedSection,
body.kurulum #schedSection,
body.kurulum #creditSection,
body.kurulum #suggestSection,
body.kurulum #changeSection,
body.kurulum #candSection,
body.kurulum #blockSection,
body.kurulum #basvuruSection,
body.kurulum #tierSection,
/* ★ Faz 26 — kurulum çubuğu da gizli. Karşılama kartındaki adımlarla AYNI
   üç işi yapan dört düğme daha koymak, "yedi düğme üç iş" karmaşasının
   kaynağıydı: kullanıcı hangisine basacağını seçmek zorunda kalıyordu.
   Kurulum bitince çubuk geri geliyor — orada işlevi değiştirmek değil,
   yapılanı GÖRMEK ve düzeltmek. */
body.kurulum #setupbar,
body.kurulum #secnav{display:none}

/* Karşılama (ilk ziyaret). */
.hero{border-top:6px solid var(--seal)}
.hero h2{font-size:22px;margin:6px 0 8px}
.hero .lead{font-size:14px;color:var(--ink-2);line-height:1.65;max-width:62ch}
.steps{display:flex;flex-direction:column;gap:10px;margin-top:18px}
.step{display:flex;gap:14px;align-items:flex-start;padding:12px 14px;
  background:var(--surface-2);border:1px solid var(--border)}
.step.done{opacity:.55}
.step .no{flex:0 0 26px;height:26px;display:grid;place-items:center;
  background:var(--seal-soft);color:var(--seal);font-weight:700;font-size:12px;
  font-family:"Chivo",Helvetica,Arial,sans-serif}
.step.done .no{background:var(--anadal-soft);color:var(--anadal)}
.step .body{flex:1;min-width:0}
.step .body b{display:block;font-size:13.5px}
.step .body span{display:block;font-size:12px;color:var(--ink-3)}
.step .body .why{margin-top:3px;color:var(--ink-2);font-style:italic}
.step button{flex:0 0 auto}
.step .sure{flex:0 0 auto;font-size:11px;color:var(--ink-3);white-space:nowrap;
  min-width:62px;text-align:right}
/* ★ Sırası gelmemiş adım KAPALI: tıklanınca çıkmaza düşen bir düğme,
   olmayan bir düğmeden kötü. */
.step.kilit{opacity:.5}
.step.kilit button{cursor:not-allowed}
/* Sıradaki adım göze girsin — büyük düğme onun. */
.step.simdi{border-color:var(--seal);background:var(--seal-soft)}
/* ★ TEK birincil eylem. Yedi düğme arasından seçtirmek, "nasıl yapacağımı
   anlayamıyorum" hissinin ana kaynağıydı. */
.heroCta{display:flex;align-items:center;gap:12px;margin-top:18px;flex-wrap:wrap}
.heroCta .meta{font-size:12px;color:var(--ink-3)}
.heroSkip{margin-left:auto;font-size:13px}
.heroDismiss{font-size:12px;color:var(--ink-3)}
.ghost.big{font-size:14px;padding:11px 20px;letter-spacing:.04em}
/* Zorunlu adım ile isteğe bağlı iyileştirmeleri AYIRAN çizgi. */
.stepsplit{margin:18px 0 8px;font-size:11px;letter-spacing:.11em;
  text-transform:uppercase;color:var(--ink-3);display:flex;align-items:center;gap:10px}
.stepsplit::after{content:"";flex:1;height:1px;background:var(--border)}
.herofoot{margin-top:16px;font-size:12px;color:var(--ink-3);line-height:1.7}
/* "Şimdi ne yapabilirsin" — bir kerelik, kapatılabilir. */
.note.sonraki{border-left:3px solid var(--anadal);padding:10px 12px;margin:14px 0}
.sonrakiliste{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px}
.sonrakiliste .kapat{margin-left:auto;color:var(--ink-3)}

/* Kaydedilen program bölümü. */
.savedhead{display:flex;flex-wrap:wrap;gap:14px;justify-content:space-between;
  align-items:flex-end;margin-bottom:12px}
.savedgrid{display:flex;flex-wrap:wrap;gap:8px}
.savedcard{background:var(--surface-2);border:1px solid var(--border);
  border-left:4px solid var(--anadal);padding:8px 11px;min-width:184px;flex:1 1 184px}
.savedcard.cap{border-left-color:var(--cap)}
.savedcard .crn{float:right;color:var(--ink-3)}
.savedcard .when{font-size:11.5px;color:var(--ink-3);margin-top:3px}
.savedcard .miss{font-size:11.5px;color:var(--warn)}
.savedtotals{margin-top:12px;font-size:12.5px;color:var(--ink-2)}

/* Başvuru bölümünün KISA hâli — ayrıntı pencerede. */
.basvuruline{display:flex;flex-direction:column;gap:8px;margin-top:12px}
.basvuruitem{display:flex;align-items:center;gap:12px;padding:10px 12px;
  background:var(--surface-2);border:1px solid var(--border)}
.basvuruitem .mark{font-size:16px;font-weight:700;line-height:1}
.basvuruitem .what{flex:1;min-width:0;display:flex;flex-direction:column;gap:2px}
.basvuruitem .why{font-size:11.5px;color:var(--ink-3)}
.basvuruitem button{flex:0 0 auto;white-space:nowrap}
@media (max-width:560px){
  .basvuruitem{flex-wrap:wrap}
  .basvuruitem button{width:100%}
  /* ★ Karşılama adımları telefonda: düğme ve süre metnin YANINDA değil,
     ALTINDA. Yan yana durunca açıklama 12 karakterlik bir şeride sıkışıp
     okunmaz oluyordu (ölçüldü, 390px). */
  .step{flex-wrap:wrap}
  .step .body{flex:1 1 100%;order:2}
  .step .no{order:1}
  .step .sure{order:1;margin-left:auto;min-width:0}
  .step button{order:3;width:100%;margin-top:8px}
  .step .chip{order:3;margin-top:8px}
  .heroCta{flex-direction:column;align-items:stretch}
  .heroCta .ghost.big{width:100%}
  .heroSkip{margin-left:0}
}

dialog{border:1px solid var(--border-strong);border-top:6px solid var(--seal);
  border-radius:var(--r);background:var(--surface);
  color:var(--ink);max-width:540px;width:calc(100% - 32px);padding:0;box-shadow:var(--shadow)}
/* Program tablosu 540px'e sığmıyor; içeriği kesmek yerine pencereyi büyütüyoruz.
   Yükseklik ekranla sınırlı, taşan kısım pencerenin İÇİNDE kayıyor. */
dialog.wide{max-width:880px}
dialog.wide .pad{max-height:min(84vh,760px);overflow-y:auto}
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
      <h1 id="doctitle">Ders Planlama Aracı</h1>
    </div>
    <button class="ghost" id="theme">Tema</button>
  </div>
  <div class="sub" id="subtitle"></div>
  <!-- D3: verinin yaşı. Kontenjan sayıları buna ait, sayfanın üretildiği
       ana değil; ikisi günlerce ayrışabiliyor. -->
  <div class="sub veriyasi" id="veriYasi"></div>
</header>

<!-- D1: bozuk ayar dosyası. Sayfa açılıyor ama ne olduğu yazıyor. -->
<div class="note ayarhata" id="ayarHatasi" hidden></div>

<!-- ★ Bölüm çubuğu (22.08.2026). Sayfa on bölüm uzunluğunda; aranan yere
     kaydırarak gitmek en sık yapılan iş hâline gelmişti. Gizli bölümler
     (veri yoksa) çubukta da GÖRÜNMÜYOR — tıklayınca hiçbir yere gitmeyen
     bir bağlantı, olmayan bir bağlantıdan kötüdür. -->
<nav class="secnav" id="secnav" aria-label="Bölümler"></nav>

<!-- ★ İLK ZİYARET. Program seçilmemişken rapor GÖSTERİLMİYOR: seçilmemiş
     bir bölümün dolu haftalık programı, aracın söyleyebileceği en yanlış şey. -->
<section class="card pad hero" id="hero" hidden></section>

<!-- Faz 26: kurulum bitince "şimdi ne yapabilirsin". Bir kerelik. -->
<div class="note sonraki" id="sonraki" hidden></div>

<section class="setupbar" id="setupbar"></section>

<!-- ★ KAYDEDİLEN PROGRAM en üstte (kullanıcı isteği 23.08.2026).
     Kayıt haftasında araca dönmenin sebebi bu: "ben ne kaydetmiştim".
     Aşağıdaki ızgara bir ÇALIŞMA alanı ve düzenlendikçe değişiyor; kayıtlı
     program ise sabit bir kayıt. İkisini aynı yerde göstermek, hangisinin
     hangisi olduğunu belirsizleştiriyordu. -->
<section class="card pad" id="savedSection" hidden>
  <div class="sechead"><div class="eyebrow">Kayıtlı</div><div class="rule"></div></div>
  <div class="savedhead">
    <div><h2>Kaydettiğin program</h2>
      <div class="summary" id="savedWhen"></div></div>
    <div class="toolbar" id="savedActions"></div>
  </div>
  <div id="savedList"></div>
</section>

<section class="panels" id="panels"></section>

<section class="card pad" id="schedSection">
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
  <!-- C3: arz uyarısı — kayıt gününden ÖNCE bilinmesi gereken şey. -->
  <div class="note arz" id="arzUyari" hidden></div>
  <div class="toolbar">
    <span id="editState" class="chip edited" hidden>değiştirildi</span>
    <button class="ghost" id="crnLoad">CRN'den yükle</button>
    <button class="ghost primary" id="savePicks" hidden>Programı kaydet</button>
    <!-- D2: tek adım geri. "Öneriye dön" her şeyi siliyordu. -->
    <button class="ghost" id="undo" hidden>Geri al</button>
    <button class="ghost" id="reset" hidden>Öneriye dön</button>
    <button class="ghost" id="crnBtn">Kayıt günü</button>
    <button class="ghost" id="icsBtn">Takvime aktar</button>
    <button class="ghost" id="shareBtn">Bağlantı</button>
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


<section class="card pad" id="creditSection" hidden>
  <div class="sechead"><div class="eyebrow">Mevzuat kısıtı</div><div class="rule"></div></div>
  <h2 style="margin-bottom:14px">Kredi ve not eşikleri</h2>
  <div id="gpaBody"></div>
  <div id="loadBody"></div>
  <div id="floorBody"></div>
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

<section class="card pad" id="candSection">
  <div class="sechead"><div class="eyebrow">Sıralama</div><div class="rule"></div></div>
  <h2>Aday dersler</h2>
  <div class="summary">Puan; kritik yol, kaç dersi açtığı, zorunluluk, kontenjan
    ve kademeden hesaplanır. Satıra tıklayıp programa ekleyebilirsin.</div>
  <!-- ★ 24.08.2026 — liste ilk 30 ile kesiliyordu ve arama yoktu: aklındaki
       dersi arayan kişi onu bulamıyor, "bu araç benim dersimi bilmiyor"
       diye çıkıyordu. Süzgeç kesme sınırını da kaldırıyor. -->
  <div class="candbar">
    <input type="search" id="candQ"
      placeholder="ders ara — kod, ad ya da hoca (örn. MAT 103E, olasılık, Feza)">
    <div class="radios" id="candRole"></div>
    <label class="tickbox"><input type="checkbox" id="candFree"> yalnız yeri olanlar</label>
    <!-- ★ Faz 25/B1 — planında OLMAYAN dersi de aramak/eklemek için. -->
    <button class="ghost" id="katalogBtn">Katalogda ara</button>
    <span class="candcount" id="candCount"></span>
  </div>
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
  <!-- ★ 22.08.2026: bölüm iki satıra indi, ayrıntı pencereye taşındı.
       Şartlar + program tablosu sayfanın en uzun bölümüydü ve her açılışta
       oradaydı; oysa dönemde birkaç kez bakılan bir şey. -->
  <div class="basvuruline" id="basvuruSummary"></div>
</section>

<dialog id="basvuruDlg" class="wide"><div class="pad">
  <h2 id="basvuruDlgTitle" style="margin-bottom:4px">ÇAP planları</h2>
  <div class="summary">Yönergedeki şartlar senin durumunla karşılaştırılıyor.
    Karar mercii bölümün — bu ekran hazırlık içindir.</div>
  <div class="tabs" id="basvuruTabs" role="tablist" style="margin-top:12px"></div>
  <div id="basvuruBody"></div>
  <div class="toolbar" style="margin-top:16px">
    <button class="ghost" data-close>Kapat</button>
  </div>
</div></dialog>

<section class="card pad" id="tierSection">
  <div class="sechead"><div class="eyebrow">Önşart zinciri</div><div class="rule"></div></div>
  <h2 id="tierTitle">Kademeler</h2>
  <div class="summary">Her kademe en az bir dönem. Kademe sayısı, ikinci programı
    bitirebileceğin en kısa süredir. <b>Çizgiler önşart bağıdır</b> — bir derse
    tıklarsan yalnız o dersin zinciri kalır, ikinci tıkta hepsi geri gelir.</div>
  <!-- Her ikinci programın KENDİ zinciri; aralarında önşart ilişkisi yok. -->
  <div id="tierGroups" style="margin-top:14px"></div>
</section>

<footer>
  Bu araç bilgilendirme amaçlıdır; ders kayıt kararların için danışmanına ve OBS'ye danış.
  Veriler <span id="gen" class="mono"></span> itibarıyladır.
  <!-- ★ "Bu dosya notlarını içerir" YALNIZ gerçekten içeriyorsa yazılıyor:
       transkript girmemiş kişiye söylenince, girmediği bir veriyi sızdırdığını
       sanıyor. Uyarı her yerde tekrarlanınca da okunmaz oluyor. -->
  <span id="gizlilik"></span>
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
/* ★ ÇAP ve yandal aynı anda olabiliyor: başlıklar TEK programa göre
   yazıldığında öbürü yokmuş gibi görünüyordu. */
const SECONDS = () => DATA.seconds || [];
function renderHeader(){
  LBL = DATA.secondLabel || "ÇAP";
  const ikili = SECONDS().length > 1;
  $("#eyebrow").textContent = [DATA.anadal,
      ...SECONDS().map(s => `${s.program} ${s.label}`)].filter(Boolean).join(" + ")
    + (DATA.term ? ` · ${DATA.term}` : "");
  /* ★ Başlıkta program adı YOK (kullanıcı isteği 23.08.2026): araç ÇAP'a
     özel değil, yandalda ve ÇAP'sız kullanımda da aynı araç. Hangi programa
     baktığın zaten üstteki eyebrow'da yazıyor. */
  $("#doctitle").textContent = "Ders Planlama Aracı";
  $("#blockTitle").textContent = ikili
    ? "İkinci programlarında neden alamıyorsun"
    : `${LBL}'ta neden alamıyorsun`;
  $("#tierTitle").textContent = ikili ? "Kademeler" : `${LBL} kademeleri`;
  $("#gen").textContent = DATA.generatedAt;
  $("#gizlilik").textContent = (DATA.load && DATA.load.noTranscript)
    ? "" : "Bu dosya notlarını içerir — paylaşma.";
  renderVeriYasi();
  renderAyarHatasi();
  /* ★ Transkript yokken GNO da yok; "dönem yükü sınırı 35 kredi" o zaman
     hesaplanmış bir sayı değil, varsayılan. Bilinmeyeni bilinen gibi
     göstermemek için transkript gelene kadar yazılmıyor. */
  /* ★ Faz 26 — İLK SATIR ne olduğunu söylemeli, sayı dökmemeli.
     "3417 açık şube · dönem yükü sınırı: transkript girilince" siteye ilk
     giren için anlamsız: bağlamı olmayan bir jargon. Kurulum sürerken araç
     kendini tanıtıyor; kurulum bitince sayılar geri geliyor, çünkü o zaman
     bakılan şey onlar. */
  $("#subtitle").textContent = DATA.onboarding && DATA.onboarding.blocking
    ? "İTÜ'nün açık derslerinden çakışmasız haftalık program kurar — "
      + "önşart, kontenjan ve kredi tavanını denetleyerek."
    : [
        `${DATA.lessonCount} açık şube`,
        DATA.load && DATA.load.noTranscript
          ? "dönem yükü sınırı: transkript girilince"
          : `dönem yükü sınırı ${DATA.maxLoad} ${DATA.unitLabel}`,
        DATA.donem ? `${DATA.donem}. dönem (${DATA.donemSource})` : "",
      ].filter(Boolean).join(" · ");
}

/* ---------- verinin yaşı (Faz 25/D3) ----------
   ★ "0/240" üç gün önceki veriyse yanıltıcı. Alt bilgide bir kez yazmak
   yetmiyordu; kontenjana bakılan HER yerde tarih var (doluluk çubuğunun
   `title`'ı, kayıt kontrolü) ve veri bayatladıysa üstte uyarı çıkıyor. */
function veriYasiMetni(){
  const A = DATA.dataAge;
  if(!A) return "veri tazeleme tarihi bilinmiyor";
  if(A.days === null) return `veri ${A.raw}`;
  const t = A.calendarDays;
  const g = t === 0 ? "bugün" : (t === 1 ? "dün" : `${t} gün önce`);
  return `şube/kontenjan verisi ${g} tazelendi (${A.raw})`;
}

function renderVeriYasi(){
  const el = $("#veriYasi");
  if(!el) return;
  el.textContent = veriYasiMetni();
  el.classList.toggle("stale", !!(DATA.dataAge && DATA.dataAge.stale));
}

/* ---------- bozuk ayar dosyası (Faz 25/D1) ----------
   ⚠️ Sessizce varsayılana düşmek, kullanıcıya başka bir bölümün raporunu
   doğru sandırırdı. Sayfa AÇILIYOR ama ne olduğunu ve nerede olduğunu
   tepede yazıyor. */
function renderAyarHatasi(){
  const el = $("#ayarHatasi");
  if(!el) return;
  const hata = DATA.settingsError;
  el.hidden = !hata;
  if(!hata) return;
  el.innerHTML = `<b>Ayar dosyan okunamadı — varsayılanlarla açıldı.</b>
    <div class="mono" style="margin-top:4px">${esc(hata)}</div>
    <div style="margin-top:6px">Seçtiğin bölüm ve dönem <b>kullanılmıyor</b>.
      Dosyayı düzelt ya da aşağıdan yeniden seç.</div>`;
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
  /* ★ Taşıyıcıdan bağımsız uç çağrısı.
     `make app` → HTTP ile 127.0.0.1'e. Statik site → tarayıcıdaki Python
     (Pyodide) doğrudan `State.dispatch` çağırıyor, ağa hiç çıkılmıyor.
     İkisi de AYNI uç adlarını ve aynı cevabı kullanıyor; arayüz hangi
     taşıyıcıda olduğunu bilmek zorunda değil. */
  if(window.__ITUCAP_API__) return window.__ITUCAP_API__(path, payload);
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
    ? `<b>${esc(s.anadalProgram)}</b> anadal`
      + (SECONDS().length
         ? SECONDS().map(x => ` · <b>${esc(x.program)}</b> ${esc(x.label)}`).join("")
         : " · ikinci program yok")
      + ` · <b>${DATA.donem || "?"}. dönem</b> (${esc(DATA.donemSource)})`
      + ` · <b>${s.transcript.length}</b> ders girilmiş`
    : `<b>${esc(DATA.anadal)}</b>`
      + SECONDS().map(x => ` · <b>${esc(x.program)}</b> ${esc(x.label)}`).join("")
      + ` · <b>${DATA.donem || "?"}. dönem</b>`;
  /* ★ "Ders ara" YANLIŞ addı (24.08.2026): düğme GEÇİLEN dersleri düzenleme
     penceresini açıyor. İlk giren kişi "alacağım dersi arayacağım" diye
     tıklayıp transkript ekranına düşüyordu. Aday tablosundaki süzgeç
     gerçek "ders ara" işini görüyor; bu düğmenin adı ne yaptığını söylüyor. */
  $("#setupbar").innerHTML = `<div class="who">${who}</div>
    ${LIVE ? `
      <button class="ghost" data-setup="program">Program</button>
      <button class="ghost" data-setup="donem">Dönem</button>
      <button class="ghost primary" data-setup="plan">Plandan işaretle</button>
      <button class="ghost" data-setup="dersler">Geçtiğin dersler</button>`
    : `<span class="ro">Düzenlemek için <span class="mono">make app</span></span>
       <button class="ghost" disabled>Program</button>
       <button class="ghost" disabled>Dönem</button>
       <button class="ghost" disabled>Plandan işaretle</button>
       <button class="ghost" disabled>Geçtiğin dersler</button>`}`;
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
/* ★ ÇAP ve yandal AYNI ANDA alınabiliyor (23.08.2026): 'İkisi' seçilince
   iki ayrı bölüm+plan kutusu birden açılıyor. Her tür KENDİ listesinden
   seçiliyor — o türde planı olmayan bölüm hiç görünmüyor. */
const KIND_LABEL = {cap: "ÇAP", yandal: "Yandal"};

function programDialog(){
  const s = SETUP;
  /* ★ Anadal listesi YALNIZ lisans planı olan bölümler (24.08.2026).
     Aynı ilke ÇAP/yandal listesinde zaten vardı: seçtirip sonra
     "plan yok" demek, seçim sunmamaktan kötü. Anadalda dead-end daha da
     pahalı — rapor komple boş çıkıyor ve araç bozuk görünüyor. */
  const adi = {};
  s.programs.forEach(p => { if(p.name && !adi[p.code]) adi[p.code] = p.name; });
  const codes = [...new Set(s.programs.filter(p => p.plan_type === "lisans")
                                      .map(p => p.code))].sort();
  /* ★ Kod tek başına bir tanım değil: "AIN" ne demek olduğunu kimse bilmiyor.
     Ad da yazınca yerleşik `select` yazarak-arama'sı hem koda hem ada çalışıyor. */
  const label = (c) => adi[c] ? `${c} — ${adi[c]}` : c;
  const opts = (sel) =>
    /* ★ Boş seçim GERÇEK bir seçenek: yoksa liste alfabetik ilk bölümde
       (AIN) açılıyor ve dokunmadan Kaydet'e basan herkes o bölüme yazılıyor. */
    (sel ? "" : `<option value="" selected>— bölümünü seç —</option>`) +
    codes.map(c => `<option value="${esc(c)}"${c === sel ? " selected" : ""}
      >${esc(label(c))}</option>`).join("");
  const kindsOf = (k) => k === "ikisi" ? ["cap", "yandal"] : (k === "yok" ? [] : [k]);
  /* ⚠️ "Gelişmiş" kutusunun açık gelme ölçütü "kod var mı" DEĞİL:
     Settings.load beyan yoksa kodları seçilen programlardan TÜRETİYOR,
     dolayısıyla liste hiç boş gelmiyor ve kutu bölüm seçilir seçilmez
     açık kalıyordu. Ölçüt: kullanıcı türetilenden farklı bir şey yazmış mı. */
  const turetilmis = new Set([s.anadalProgram,
    ...["cap", "yandal"].map(k => ((s.secondChoice || {})[k] || {}).program)]
    .filter(Boolean).map(x => x.toUpperCase()));
  const ozelKod = s.programCodes.some(c => !turetilmis.has(c.toUpperCase()))
    || s.programCodes.length !== turetilmis.size;
  const secondOpts = (k, sel) => ((s.secondPrograms || {})[k] || [])
    .map(p => `<option value="${esc(p.code)}"${p.code === sel ? " selected" : ""}
      >${esc(p.code)} — ${esc(p.name)}</option>`).join("")
    || `<option value="">bu tipte plan yok — make all-plans</option>`;
  openSetup(`
    <div class="eyebrow">Kurulum</div>
    <h2 style="margin-bottom:4px">Program seçimi</h2>
    <p class="modenote" style="margin:2px 0 4px">Bir tek anadal yeter.
      <b>Çift anadal ya da yandal yapmıyorsan “Yok” bırak</b> — araç normal
      ders seçim aracı olarak çalışır.</p>
    <div class="grid2">
      <label class="field"><span>Anadal <b style="color:var(--anadal)">*</b></span>
        <select id="fAnadal">${opts(s.anadalProgram)}</select>
        <span class="hint">Listede <b class="mono">${codes.length}</b> bölüm var.
          Seninkini göremiyorsan o bölümün ders planı henüz çekilmemiştir.</span></label>
      <label class="field"><span>İkinci program</span>
        <div class="radios" id="fKind">
          ${[["yok","Yok"],["cap","ÇAP"],["yandal","Yandal"],["ikisi","İkisi"]].map(([k,l]) =>
            `<button data-k="${k}" aria-pressed="${k===s.secondKind}">${l}</button>`).join("")}
        </div>
        <span class="hint">İsteğe bağlı.</span></label>
    </div>
    ${["cap","yandal"].map(k => `
      <div id="fWrap-${k}" hidden>
        <label class="field"><span>${KIND_LABEL[k]} bölümü</span>
          <select id="fProg-${k}">${secondOpts(k,
            ((s.secondChoice || {})[k] || {}).program)}</select></label>
        <label class="field"><span>${KIND_LABEL[k]} planı</span>
          <select id="fPlan-${k}"></select>
          <span class="hint">Planı boş bırakırsan en güncel OBS planı seçilir.</span></label>
      </div>`).join("")}
    <details class="adv"${ozelKod ? " open" : ""}>
      <summary>Gelişmiş</summary>
      <label class="field"><span>Kayıt yapabildiğin program kodları</span>
        <input type="text" id="fCodes" value="${esc(s.programCodes.join(", "))}">
        <span class="hint">Bir şubenin "Dersi Alabilen Programlar" listesinde bunlardan
          biri varsa dersi alabilirsin. <b>Boş bırak</b> — o zaman yukarıda
          seçtiklerin kullanılır. Virgülle ayır.</span></label>
    </details>`, () => {
    let kind = s.secondKind;
    const fillPlans = (k) => {
      const code = $("#fProg-" + k).value;
      const secili = ((s.secondChoice || {})[k] || {}).planId;
      const list = s.plans.filter(p => p.plan_type === k && p.program_code === code);
      $("#fPlan-" + k).innerHTML = `<option value="">otomatik (en güncel)</option>` +
        list.map(p => `<option value="${p.id}"${p.id === secili ? " selected" : ""}
          >${p.id} · ${p.slots} slot · ${esc((p.title || "").slice(0, 54))}</option>`).join("");
      if(!list.length) $("#fPlan-" + k).innerHTML +=
        `<option disabled>bu bölümde ${KIND_LABEL[k]} planı yok</option>`;
    };
    const sync = () => {
      const acik = kindsOf(kind);
      ["cap","yandal"].forEach(k => {
        $("#fWrap-" + k).hidden = !acik.includes(k);
        if(acik.includes(k)) fillPlans(k);
      });
    };
    $("#fKind").querySelectorAll("button").forEach(b =>
      b.addEventListener("click", () => {
        kind = b.dataset.k;
        $("#fKind").querySelectorAll("button").forEach(x =>
          x.setAttribute("aria-pressed", x.dataset.k === kind));
        sync();
      }));
    ["cap","yandal"].forEach(k =>
      $("#fProg-" + k).addEventListener("change", () => fillPlans(k)));
    sync();
    $("#setupSave").addEventListener("click", () => {
      const anadal = $("#fAnadal").value;
      /* ★ Sunucu da reddediyor ama hata orada "anadal programı boş olamaz"
         diye çıkıyor; burada söylemek, kullanıcıyı alana geri götürüyor. */
      if(!anadal){
        say("Önce anadal bölümünü seç", true);
        $("#fAnadal").focus();
        return;
      }
      const secim = {};
      kindsOf(kind).forEach(k => secim[k] = {
        program: $("#fProg-" + k).value,
        planId: $("#fPlan-" + k).value || null,
      });
      const eksik = kindsOf(kind).filter(k => !secim[k].program);
      if(eksik.length){
        say(eksik.map(k => KIND_LABEL[k]).join(" ve ") + " bölümü seçilmedi", true);
        return;
      }
      /* ⚠️ Boş bırakılan kod alanı DOLDURULMUYOR: motor boşken zaten
         seçilen programlardan türetiyor (recommend.candidates). Buraya
         sabitlemek, program değiştiğinde eski kodları geride bırakırdı. */
      save(() => api("/api/programs", {
        anadalProgram: anadal,
        secondKind: kind,
        secondPrograms: secim,
        programCodes: $("#fCodes").value.split(/[,\s]+/).filter(Boolean),
      }));
    });
  });
}

/* ---------- 2. dönem seçimi ---------- */
function termDialog(){
  const cur = SETUP.donem;
  const capCur = SETUP.capBaslangic || 0;
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
      </span></label>
    <label class="field" style="margin-top:14px"><span>ÇAP'a başladığın yarıyıl</span>
      <div class="terms" id="fCap">
        <button data-t="0" aria-pressed="${!capCur}" style="width:auto;padding:7px 12px"
          >bilmiyorum</button>
        <button data-t="3" aria-pressed="${capCur === 3}">3</button>
        <button data-t="5" aria-pressed="${capCur === 5}">5</button>
      </div>
      <span class="hint">Bulunduğun dönem <b>değil</b> — ikinci anadala
        <b>başladığın</b> yarıyıl. Yönerge yarıyıl tabanını buna bağlıyor:
        3'te başlayan her dönem en az <b>6</b>, 5'te başlayan en az <b>9</b>
        kredilik dersi ikinci anadaldan almak zorunda.
        &#8220;Bilmiyorum&#8221; seçilirse araç hiçbir taban iddia etmez.
      </span></label>`, () => {
    let pick = cur || 0;
    let capPick = capCur || 0;
    $("#fCap").querySelectorAll("button").forEach(b =>
      b.addEventListener("click", () => {
        capPick = +b.dataset.t;
        $("#fCap").querySelectorAll("button").forEach(x =>
          x.setAttribute("aria-pressed", +x.dataset.t === capPick));
      }));
    $("#fTerm").querySelectorAll("button").forEach(b =>
      b.addEventListener("click", () => {
        pick = +b.dataset.t;
        $("#fTerm").querySelectorAll("button").forEach(x =>
          x.setAttribute("aria-pressed", +x.dataset.t === pick));
      }));
    $("#setupSave").addEventListener("click", () =>
      save(() => api("/api/donem", {donem: pick, capBaslangic: capPick})));
  });
}

/* ---------- 3b. plandan tik atarak giriş ---------- */
/* ★ 60+ dersi tek tek aramak işkence. Plan zaten elimizde: dönem dönem
   listele, kullanıcı tiklesin. 0 kredili derste not listesi BL/BZ ile
   başlıyor — o dersler harf notu almıyor. */
function checklistDialog(){
  const plans = (SETUP.checklist || []);
  if(!plans.length){
    /* ★ İki ayrı boş, iki ayrı cevap (24.08.2026). Karşılama kartındaki 2.
       adıma 1. adımı atlayarak tıklayan kişi "Plan bulunamadı." görüyordu —
       ne olduğu, ne yapması gerektiği belli olmayan bir çıkmaz. */
    const yok = !SETUP.anadalProgram;
    openDialog(`
      <div class="eyebrow">Kurulum</div>
      <h2 style="margin-bottom:4px">${yok ? "Önce bölümünü seç" : "Plan bulunamadı"}</h2>
      <p class="modenote">${yok
        ? `Tikleyeceğin ders listesi <b>senin planından</b> geliyor;
           bölüm seçilmeden gösterilecek bir plan yok.`
        : `Seçtiğin bölümün ders planı katalogda yok. Programı değiştirebilir
           ya da geçtiğin dersleri tek tek girebilirsin.`}</p>
      <div class="dlgactions">
        <button class="ghost primary" id="goProgram">Program seçimini aç</button>
      </div>`);
    $("#goProgram").addEventListener("click", () => {
      $("#detail").close(); programDialog();
    });
    return;
  }
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
/* ---------- İkinci anadaldan asgari yarıyıl kredisi ----------
   ÇAP/Yandal Yönergesi: 3. yarıyılda başlayan her yarıyıl en az 6, 5'te
   başlayan en az 9 kredilik dersi İKİNCİ ANADALDAN almak zorunda.

   ★ MADDE 17'deki banttan AYRI kural ve ikisi karıştırılmamalı:
     MADDE 17/1 → TOPLAM yük bandı (13–22); ÇAP öğrencisi MUAF.
     bu kural   → yalnız ikinci anadaldan alınacak TABAN.
   "ÇAP muaf" diye bunu da atlamak, öğrenciyi ÇAP'tan ilişik kesilmeye
   götürebilirdi. O yüzden ayrı bir panelde ve seçime göre CANLI hesaplanıyor.

   ★ İndirim OTOMATİK DEĞİL: yönerge "düşürülebilir" diyor, "düşürülür"
   demiyor. Tabanı sessizce yarıya çekmek, alınmamış bir FYK kararını
   alınmış varsaymak olurdu. Bir ÇARE olarak gösteriliyor. */
function renderFloor(){
  const box = $("#floorBody");
  const F = DATA.secondFloor;
  if(!box) return;
  if(!F){ box.innerHTML = ""; return; }

  if(F.undeclared){
    box.innerHTML = `<div class="note" style="margin-top:12px">
      <b>İkinci anadaldan yarıyıl tabanı hesaplanamıyor.</b>
      Yönerge, ÇAP'a <b>3.</b> yarıyılda başlayana her dönem en az <b>6</b>,
      <b>5.</b> yarıyılda başlayana en az <b>9</b> kredi şartı koyuyor —
      ama hangi yarıyılda başladığın beyan edilmemiş.
      ${LIVE
        ? `<b>Dönem</b> düğmesinden gir — araç o zaman uyarabilir.`
        : `<span class="mono">config/settings.toml</span> içindeki
           <span class="mono">${esc(F.setting)}</span> alanına yaz.`}</div>`;
    return;
  }

  // Yalnız İKİNCİ programın kredileri — anadal sayılmaz.
  const ikinci = picks().filter(p => p.cand.role !== "ANADAL");
  const kredi = +ikinci.reduce((a,p) => a + (p.cand.credits || 0), 0).toFixed(1);
  const ok = kredi + 1e-9 >= F.min;
  const eksik = +(F.min - kredi).toFixed(1);
  const R = F.relief;
  const indirimYeterMi = R && kredi + 1e-9 >= R.min;

  /* ★ Motor tabanı hiç karşılayamıyorsa bunu SÖYLÜYORUZ. Sessiz kalıp en
     yüksek puanlı programı sunmak, kullanıcıyı kayıt gününde şaşırtırdı. */
  const oneriler = M().schedules || [];
  const hicbiriOlmuyor = oneriler.length > 0 &&
    oneriler.every(s => (s.floorGaps || []).length);

  box.innerHTML = `
    ${hicbiriOlmuyor ? `<div class="note" style="margin-top:12px;
        border-left-color:var(--warn)">
      <b>Bu dönem açık derslerden tabanı karşılayan çakışmasız program
      bulunamadı.</b> Motor ${oneriler.length} öneri üretti, hiçbiri
      ${F.min} krediye ulaşmıyor — arz, çakışma ya da önşart yüzünden.
      Bu <b>imkânsız</b> demek değil: taban indirilebiliyor (aşağıda) ve
      dönem başında yeni şube açılabiliyor. Danışmanınla konuş.</div>` : ""}
    <div class="gauge" style="margin-top:14px;padding-top:14px;
         border-top:1px solid var(--border)">
      <div class="gaugebar" style="max-width:230px">
        <div class="track"><i class="${ok ? "ok" : ""}"
          style="width:${Math.min(100, F.min ? kredi / F.min * 100 : 0)}%"></i></div>
        <div class="gaugelabel"><b class="mono" style="font-size:15px">${kredi}</b>
          / ${F.min} kredi ${F.verified ? "" : "<b>⚠</b>"}
          <span style="color:var(--ink-3)">— ${esc(LBL)} tarafından</span></div>
      </div>
      <div style="flex:2;min-width:250px;font-size:12.5px;color:var(--ink-2)">
        <b>İkinci anadaldan yarıyıl tabanı.</b>
        ÇAP'a <b>${F.startTerm}.</b> yarıyılda başladığın için her dönem
        en az <b class="mono">${F.min}</b> kredilik dersi ikinci anadaldan
        alman gerekiyor.
        <div style="color:var(--ink-3);margin-top:4px">Bu, dönem kredi
          bandından (MADDE 17) ayrı bir kural — o banttan ÇAP öğrencisi muaf,
          bu tabandan değil.</div>
        ${F.source ? `<div style="color:var(--ink-3)">${esc(F.source)}</div>` : ""}
      </div>
    </div>
    ${ok ? "" : `<div class="note" style="border-left-color:var(--danger);margin-top:12px">
      <b>Seçili programda ikinci anadaldan ${kredi} kredi var, taban ${F.min}.</b>
      ${eksik} kredi eksik.
      ${R ? `<div style="margin-top:6px">Yönerge tabanı
        <b>${R.min}</b> krediye kadar indirmene izin veriyor — ama
        <b>kendiliğinden olmuyor</b>:
        ${R.conditions.map(c => `<span class="chip credit"
          style="margin:0 4px 0 0">${esc(c)}</span>`).join("")}
        gerekiyor${R.deadline ? `, son tarih: <b>${esc(R.deadline)}</b>` : ""}.
        ${indirimYeterMi
          ? `<b style="color:var(--anadal)">İndirim onaylanırsa şu anki
             seçimin yeterli olur.</b>`
          : `İndirim onaylansa bile ${+(R.min - kredi).toFixed(1)} kredi
             daha gerekir.`}</div>` : ""}
    </div>`}`;
}

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
          ${{"yönetmelik": "motor bunu kullanıyor — GNO'ndan hesaplandı",
             "ayar": "elle ayarlı (settings.toml)",
             "çağrı": "bu çalıştırmaya özel"}[L.limitSource] || "şu an ayarlı"}:
          <b class="mono">${L.declared || "—"}</b></div>
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
  /* ★ Hangi PROGRAMIN kuralı olduğu yazıyor. ÇAP ve yandal aynı anda
     alınabiliyor ve eşikleri farklı maddelerden geliyor; etiketsiz
     gösterirsek biri öbürünün kuralı sanılır. 'genel' olanda etiket yok —
     ikisine de uygulanan kural. */
  const cokProgram = (DATA.seconds || []).length > 1;
  const chipOf = t => `
    <span class="cat" style="${style(t)}"
      title="${esc([t.note, t.why, t.source].filter(Boolean).join(" · "))}"
      >${cokProgram && t.scopeLabel ? `<b>${esc(t.scopeLabel)}</b> · ` : ""}
      ${esc(t.label)} ≥ ${t.min.toFixed(2)}
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

/* ---------- kaydedilen program (en üstteki bölüm) ----------
   ★ Kayıtlı program, aşağıdaki ÇALIŞMA ızgarasından ayrı duruyor: ızgara
   düzenlendikçe değişiyor, bu ise sabit bir kayıt.

   ⚠️ Aday havuzu KİPE göre değişiyor. Kaydedilen ders o anki kipin havuzunda
   olmayabilir (varsayılan artık "N. dönem + alttan"). O yüzden şubeyi BÜTÜN
   kiplerde arıyoruz — bulamazsak kodu ve CRN'i yine gösterip "bu kipte yok"
   diyoruz. Sessizce eksik göstermek, kullanıcının kaydettiğini sandığı dersi
   kaybetmesi demek olurdu. */
function findSection(course, crn){
  for(const m of MODES){
    const c = (m.candidates || []).find(x => x.course === course);
    const s = c && (c.sections || []).find(x => x.crn === crn);
    if(s) return {cand: c, sec: s, mode: m};
  }
  return null;
}

function modeIndexFor(picks){
  for(let i = 0; i < MODES.length; i++){
    const ok = picks.every(p => (MODES[i].candidates || []).some(
      c => c.course === p.course && (c.sections || []).some(s => s.crn === p.crn)));
    if(ok) return i;
  }
  return -1;
}

function renderSaved(){
  const sec = $("#savedSection");
  if(!sec) return;
  const saved = (DATA.savedPicks && DATA.savedPicks.picks) || [];
  sec.hidden = !saved.length;
  if(!saved.length) return;

  const when = (DATA.savedPicks.savedAt || "").replace("T", " ").slice(0, 16);
  $("#savedWhen").textContent = (when ? when + " tarihinde kaydedildi" : "kaydedildi")
    + (DATA.term ? " · " + DATA.term : "");

  let kredi = 0, akts = 0, eksik = 0;
  const kart = saved.map(p => {
    const hit = findSection(p.course, p.crn);
    if(!hit){ eksik++; return `<div class="savedcard">
      <b class="mono">${esc(p.course)}</b><span class="crn mono">${esc(p.crn)}</span>
      <div class="miss">şube bu dönemin verisinde yok</div></div>`; }
    kredi += hit.cand.credits || 0; akts += hit.cand.ects || 0;
    const saat = (hit.sec.meetings || []).map(m =>
      `${DAYS[m.day-1] || "?"} ${hhmm(m.start)}`).join(" · ") || "saati ilan edilmemiş";
    return `<div class="savedcard ${hit.cand.role === "ANADAL" ? "" : "cap"}">
      <b class="mono">${esc(p.course)}</b><span class="crn mono">${esc(p.crn)}</span>
      <div class="when">${esc(hit.cand.name || "")}</div>
      <div class="when mono">${esc(saat)}</div></div>`;
  }).join("");

  $("#savedList").innerHTML = `<div class="savedgrid">${kart}</div>
    <div class="savedtotals">${saved.length} ders · <b class="mono">${kredi}</b> kredi
      · <b class="mono">${akts}</b> AKTS
      ${eksik ? ` · <b style="color:var(--warn)">${eksik} şube bulunamadı</b>` : ""}</div>`;

  const i = modeIndexFor(saved);
  $("#savedActions").innerHTML =
    `<button class="ghost primary" id="savedOpen">Programa yükle</button>
     <button class="ghost" id="savedCrn">CRN listesi</button>`;
  $("#savedOpen").addEventListener("click", () => {
    if(i >= 0 && i !== mode) useMode(i);       /* dersin bulunduğu kipe geç */
    sel = saved.map(p => ({course: p.course, crn: p.crn}))
               .filter(p => sectionOf(p.course, p.crn));
    render();
    $("#schedSection").scrollIntoView({behavior: "smooth", block: "start"});
  });
  $("#savedCrn").addEventListener("click", () => {
    const line = saved.map(p => p.crn).join(" ");
    openDialog(`<div class="eyebrow">Kayıt günü</div>
      <h2 style="margin-bottom:4px">Kaydettiğin CRN'ler</h2>
      <p class="modenote" style="margin:2px 0 10px">OBS'ye yazacağın numaralar.
        Araç senin yerine kayıt YAPMAZ.</p>
      <label class="field"><span>Tümü (kopyala)</span>
        <input type="text" class="mono" readonly value="${esc(line)}"></label>
      `);
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
  renderSaved();                 // kaydedilen bölüm her çizimde güncel kalsın
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
  const yukle = $("#crnLoad");
  if(yukle) yukle.onclick = crnLoadDialog;
  const ics = $("#icsBtn");
  if(ics) ics.onclick = icsIndir;
  const pay = $("#shareBtn");
  if(pay) pay.onclick = paylasDialog;
}

function paylasDialog(){
  const url = paylasBaglantisi();
  if(!url){ openDialog(`<div class="empty">Programda ders yok.</div>`); return; }
  openDialog(`
    <div class="eyebrow">Paylaş</div>
    <h2 style="margin-bottom:4px">Programının bağlantısı</h2>
    <p class="modenote" style="margin:2px 0 10px">Bağlantıda <b>yalnız CRN'ler</b>
      var. Notların, transkriptin ve bölümün <b>girmiyor</b> — açan kişi senin
      ızgaranı görür, verini görmez.</p>
    <label class="field"><span>Kopyala</span>
      <input type="text" id="shareUrl" class="mono" readonly value="${esc(url)}">
      <span class="hint" id="shareCopied">Tıklayınca seçilir.</span></label>`);
  const inp = $("#shareUrl");
  if(inp) inp.addEventListener("click", () => {
    inp.select();
    navigator.clipboard && navigator.clipboard.writeText(url)
      .then(() => { $("#shareCopied").textContent = "kopyalandı ✓"; })
      .catch(() => {});
  });
}

/* ---------- CRN'den program yükle ----------
   ★ Kullanıcı isteği 23.08.2026. OBS'de kaydını yaptıktan sonra CRN'leri
   yapıştırıp GERÇEK programını görebilmek için.

   ⚠️ Planında OLMAYAN ders de yükleniyor ('plan dışı' etiketiyle). Gizleseydik
   kullanıcı gerçek programını göremezdi — serbest seçmeli, ortak zorunlu ya da
   başka bir bölümden alınan ders de kayıtta olabiliyor.
   ⚠️ Bulunamayan CRN sessizce atılmıyor: 8 yapıştırıp 6 ders görürsen hangi
   ikisinin düştüğünü bilmelisin. */
function crnLoadDialog(){
  openDialog(`
    <div class="eyebrow">Kayıt sonrası</div>
    <h2 style="margin-bottom:4px">CRN'den program yükle</h2>
    <p class="modenote" style="margin:2px 0 10px">OBS'de kaydını yaptıysan
      CRN'leri buraya yapıştır — ızgarada gerçek programın görünsün.
      Bu bir <b>görüntüleme</b>; araç OBS'ye hiçbir şey yazmaz.</p>
    <label class="field"><span>CRN'ler (boşluk, virgül ya da satır)</span>
      <textarea id="crnIn" rows="4" class="mono"
        placeholder="12486 13524 12550"></textarea></label>
    <div class="dlgactions"><span class="msg" id="crnMsg"></span>
      <button class="ghost primary" id="crnGo">Yükle</button></div>`);
  const not = (metin, kotu) => {
    const el = $("#crnMsg");
    if(el){ el.textContent = metin; el.className = "msg" + (kotu ? " bad" : ""); }
  };
  $("#crnGo").addEventListener("click", async () => {
    const liste = ($("#crnIn").value.match(/\d{3,}/g) || []);
    if(!liste.length){ not("CRN bulunamadı", true); return; }
    not("aranıyor…");
    try{
      const cevap = await api("/api/crn", {crns: liste});
      const bulunan = (cevap.crn && cevap.crn.found) || [];
      const eksik = (cevap.crn && cevap.crn.missing) || [];
      if(!bulunan.length){
        not(`hiçbiri bulunamadı (${eksik.join(", ")})`, true); return;
      }
      loadFromCrn(bulunan);
      $("#detail").close();
      if(eksik.length)
        alertLine(`${bulunan.length} ders yüklendi · ${eksik.length} CRN ` +
                  `bu dönemin verisinde YOK: ${eksik.join(", ")}`);
    }catch(err){ not(err.message, true); }
  });
}

/* Bulunan şubeleri aday havuzuna ENJEKTE edip seçime alıyor.
   Havuza koymadan `sel`e yazmak işe yaramaz: ızgara `CAND` üzerinden
   çiziliyor ve bilmediği dersi gösteremez. */
/* Şubeleri havuza yazar ve dersin aday nesnesini döndürür.
   ⚠️ Aday havuzuna da (`M().candidates`) giriyor: yalnız `CAND`'a yazmak
   ızgarayı doldururdu ama ders aday tablosunda görünmezdi ve "nereden
   geldi bu" sorusunu cevapsız bırakırdı. */
function injectSections(bulunan){
  const dokunulan = [];
  bulunan.forEach(x => {
    const sec = {crn: x.crn, capacity: x.capacity, enrolled: x.enrolled,
                 free: Math.max(0, (x.capacity||0) - (x.enrolled||0)),
                 instructor: x.instructor || "", online: !!x.online,
                 meetings: (x.meetings || []).map(m => ({
                   day: m.day, start: m.start, end: m.end,
                   building: m.building, campus: m.campus}))};
    let cand = CAND[x.course];
    if(cand){
      if(!cand.sections.some(s => s.crn === x.crn)) cand.sections.push(sec);
    }else{
      cand = {course: x.course, name: x.name, altName: x.altName || "",
              role: x.role === "PLAN_DISI" ? "PLAN_DISI" : x.role,
              ects: x.ects, credits: x.credits, unlocks: 0, tier: 0,
              critical: false, required: false, slotId: 0, planId: 0,
              /* ★ `pool` BOŞ ve `slotId` 0 — plan dışı ders HİÇBİR SLOTU
                 doldurmuyor. Kredisi yüke ve çakışmaya girer, ilerleme
                 yüzdesine girmez. Projenin ana hata sınıfı tam burada:
                 alınmamış bir şartı alınmış saymak. */
              pool: "", score: 0, opens: [],
              reasons: [x.role === "PLAN_DISI"
                        ? "plan dışı — hiçbir şartı doldurmaz" : "CRN ile eklendi"],
              sections: [sec]};
      CAND[x.course] = cand;
      MODES.forEach(m => { if(!(m.candidates || []).some(c => c.course === x.course))
        (m.candidates = m.candidates || []).push(cand); });
    }
    dokunulan.push(cand);
  });
  return dokunulan;
}

function loadFromCrn(bulunan){
  injectSections(bulunan);
  sel = bulunan.map(x => ({course: x.course, crn: x.crn}));
  render();
  $("#schedSection").scrollIntoView({behavior: "smooth", block: "start"});
}

/* ---------- plan dışı ders ekleme (Faz 25/B1) ----------
   ★ Araç bugüne kadar YALNIZ planındaki dersleri ekletiyordu. Oysa normal
   bir ders seçim aracının asıl sorularından biri "şu dersi programıma
   sığdırabilir miyim": başka bölümün dersi, serbest seçmeli, ya da sırf
   merak edilen bir ders. Katalog (3417 şube) zaten elimizdeydi. */
let KATALOG_ISTEK = 0;

function katalogDialog(){
  if(!LIVE){
    openDialog(`<div class="eyebrow">Ders ara</div>
      <h2 style="margin-bottom:4px">Bu kopya salt okunur</h2>
      <p class="modenote">Katalog araması için <span class="mono">make app</span>
        ile aç.</p>`);
    return;
  }
  openDialog(`
    <div class="eyebrow">Katalog</div>
    <h2 style="margin-bottom:4px">Ders ara ve programa ekle</h2>
    <p class="modenote" style="margin:2px 0 10px">Planında olmayan dersi de
      ekleyebilirsin — <b>plan dışı</b> diye işaretlenir. Kredisi dönem yüküne
      ve çakışma denetimine <b>girer</b>, hiçbir plan şartını <b>doldurmaz</b>.</p>
    <label class="field"><span>Kod ya da ad</span>
      <input type="search" id="katQ" autocomplete="off"
        placeholder="örn. MAT 271, olasılık, thermodynamics"></label>
    <div id="katSonuc" style="margin-top:10px"></div>`);
  const kutu = $("#katQ");
  kutu.focus();
  /* Harf başına sorgu atmıyoruz; 220 ms dursun diye bekliyoruz.
     ⚠️ Sıra numarası ayrıca gerekiyor: geciken ESKİ cevap, yeni aramanın
     sonucunu ezerse kullanıcı yazdığından başka bir liste görür. */
  let zaman = 0;
  kutu.addEventListener("input", () => {
    clearTimeout(zaman);
    const q = kutu.value.trim();
    if(q.length < 2){
      ++KATALOG_ISTEK;
      $("#katSonuc").innerHTML = `<div class="empty">en az iki harf yaz</div>`;
      return;
    }
    $("#katSonuc").innerHTML = `<div class="empty">aranıyor…</div>`;
    zaman = setTimeout(() => {
      const istek = ++KATALOG_ISTEK;
      api("/api/katalog", {q}).then(r => {
        if(istek !== KATALOG_ISTEK) return;      /* eski cevap geç geldi */
        katalogCiz(r.katalog || {});
      }).catch(err => {
        if(istek === KATALOG_ISTEK)
          $("#katSonuc").innerHTML = `<div class="empty">${esc(err.message)}</div>`;
      });
    }, 220);
  });
}

function katalogCiz(k){
  const items = k.items || [];
  if(!items.length){
    $("#katSonuc").innerHTML = `<div class="empty">${esc(k.note
      || "açık şubesi olan eşleşen ders yok")}</div>`;
    return;
  }
  $("#katSonuc").innerHTML = `
    <div class="optlist">${items.map(it => `
      <button class="opt" data-kat="${esc(it.course)}">
        <span><b class="mono">${esc(it.course)}</b>
          <span class="tag ${it.role}" style="margin-left:6px">${
            it.role === "PLAN_DISI" ? "plan dışı" : it.role}</span>
          <div class="meta">${esc(it.name)}${it.altName && it.altName !== it.name
            ? " · " + esc(it.altName) : ""}</div></span>
        <span class="meta mono" style="text-align:right;white-space:nowrap">
          ${it.credits} kredi<br>${it.sectionCount} şube</span>
      </button>`).join("")}</div>
    ${k.truncated ? `<div class="modenote" style="margin-top:8px">İlk ${
      items.length} sonuç gösteriliyor — daha fazlası var, aramayı daralt.</div>` : ""}`;
  $("#katSonuc").querySelectorAll("[data-kat]").forEach(b =>
    b.addEventListener("click", () => katalogEkle(b.dataset.kat)));
}

async function katalogEkle(course){
  $("#katSonuc").innerHTML = `<div class="empty">şubeler getiriliyor…</div>`;
  try{
    const r = await api("/api/ders", {course});
    const bulunan = (r.crn || {}).found || [];
    if(!bulunan.length){
      $("#katSonuc").innerHTML = `<div class="empty">bu dersin açık şubesi yok</div>`;
      return;
    }
    injectSections(bulunan);
    renderCandFilters(); renderCandidates();
    $("#detail").close();
    addDialog(course);            /* şube seçimi normal akışla */
  }catch(err){
    $("#katSonuc").innerHTML = `<div class="empty">${esc(err.message)}</div>`;
  }
}

function alertLine(metin){
  const el = $("#schedSummary");
  if(!el) return;
  const d = document.createElement("div");
  d.className = "note";
  d.style.marginTop = "8px";
  d.textContent = metin;
  el.appendChild(d);
}

/* ---------- takvime aktar (Faz 25/B3) ----------
   Program yalnız gün + saat: bir `.ics` dosyası olarak inebilir ve telefon
   takvimine tek dokunuşla girer. Tamamen tarayıcıda üretiliyor — hiçbir yere
   veri gitmiyor (statik sitede de böyle; sunucu yok).

   ⚠️ Bu bir ders takvimi DEĞİL, haftalık tekrar eden bir taslak: akademik
   takvim (dönem başlangıcı, tatiller, telafi) elimizde yok. O yüzden
   dosyada bunu yazan bir açıklama var ve tekrar 15 haftayla sınırlı —
   "sonsuza kadar her hafta" demek, olmayan bir bilgiyi iddia etmek olurdu. */
const ICS_HAFTA = 15;
const ICS_GUN = ["MO", "TU", "WE", "TH", "FR"];

function icsTarih(gun, dakika, ofsetGun){
  /* Dönem başlangıcı bilinmediği için ÖNÜMÜZDEKİ pazartesiden başlatıyoruz.
     Kullanıcı takvimde tarihleri kaydırabilir; yanlış bir tarihi doğruymuş
     gibi yazmaktansa bunu dosyada AÇIKÇA söylüyoruz. */
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  d.setDate(d.getDate() + ((8 - (d.getDay() || 7)) % 7 || 7) + (gun - 1) + ofsetGun);
  d.setMinutes(dakika);
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}${p(d.getMonth()+1)}${p(d.getDate())}T${
    p(d.getHours())}${p(d.getMinutes())}00`;
}

function icsMetni(){
  const sat = ["BEGIN:VCALENDAR", "VERSION:2.0",
               "PRODID:-//itucap//ders planlama araci//TR", "CALSCALE:GREGORIAN"];
  let saatsiz = 0;
  picks().forEach(p => {
    if(!p.sec.meetings.length){ saatsiz++; return; }
    p.sec.meetings.forEach((m, i) => {
      const ad = `${p.cand.course}${p.cand.name ? " — " + p.cand.name : ""}`;
      sat.push("BEGIN:VEVENT",
        `UID:${p.sec.crn}-${m.day}-${m.start}-${i}@itucap`,
        `DTSTART:${icsTarih(m.day, m.start, 0)}`,
        `DTEND:${icsTarih(m.day, m.end, 0)}`,
        `RRULE:FREQ=WEEKLY;COUNT=${ICS_HAFTA};BYDAY=${ICS_GUN[m.day-1] || "MO"}`,
        `SUMMARY:${icsKacis(ad)}`,
        `LOCATION:${icsKacis(m.building || "")}`,
        /* ⚠️ Satır sonu BURADA gerçek satır sonu; `\n` kaçışını `icsKacis`
           yapıyor. Elle kaçırırsak ters bölü ikinci kez kaçırılıyor ve
           takvim uygulamasında "\\n" diye görünüyor (ölçüldü). */
        `DESCRIPTION:${icsKacis(
          `CRN ${p.sec.crn}${p.sec.instructor ? " · " + p.sec.instructor : ""}` +
          "\n" +
          `Tarihler TAHMİNİ: akademik takvim bu araçta yok, ` +
          `önümüzdeki pazartesiden başlatıldı. Dönem başına kaydır.`)}`,
        "END:VEVENT");
    });
  });
  sat.push("END:VCALENDAR");
  return {metin: sat.join("\r\n"), saatsiz};
}

const icsKacis = (s) => String(s ?? "")
  .replace(/\\/g, "\\\\").replace(/;/g, "\\;").replace(/,/g, "\\,")
  .replace(/\n/g, "\\n");

function icsIndir(){
  const {metin, saatsiz} = icsMetni();
  const blob = new Blob([metin], {type: "text/calendar;charset=utf-8"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "ders-programi.ics";
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 5000);
  if(saatsiz) alertLine(
    `${saatsiz} dersin saati ilan edilmemiş — takvim dosyasına GİRMEDİ.`);
}

/* ---------- paylaşılabilir bağlantı (Faz 25/B4) ----------
   Program yalnız CRN'lerden ibaret. Adres çubuğuna yazınca arkadaşın da
   aynı ızgarayı görüyor.
   ✔ Gizlilik: CRN kişisel veri değil. Not, transkript, bölüm — hiçbiri
   bağlantıya GİRMİYOR. Bunu kullanıcıya da yazıyoruz, çünkü "programımı
   paylaşınca notlarım da gider mi" haklı bir soru. */
function paylasBaglantisi(){
  const crns = picks().map(p => p.sec.crn).filter(Boolean);
  const kok = location.href.split("#")[0];
  return crns.length ? `${kok}#crn=${crns.join(",")}` : "";
}

function baglantidanYukle(){
  const m = /[#&]crn=([\d,]+)/.exec(location.hash || "");
  if(!m || !LIVE) return false;
  const liste = m[1].split(",").filter(Boolean);
  if(!liste.length) return false;
  api("/api/crn", {crns: liste}).then(cevap => {
    const bulunan = (cevap.crn && cevap.crn.found) || [];
    const eksik = (cevap.crn && cevap.crn.missing) || [];
    if(bulunan.length) loadFromCrn(bulunan);
    /* ⚠️ Bulunamayan CRN sessizce atılmıyor: bağlantıdaki 6 dersin 4'ü
       gelirse hangi ikisinin düştüğü yazmalı. */
    if(eksik.length) alertLine(
      `Bağlantıdaki ${eksik.length} CRN katalogda yok: ${eksik.join(", ")}`);
  }).catch(err => alertLine("Bağlantı yüklenemedi: " + err.message));
  return true;
}

/* ---------- kayıt öncesi kontrol (Faz 25/C1) ----------
   ★ Araç bu bilgilerin HEPSİNİ zaten biliyordu ama beş ayrı bölüme
   dağılmıştı: tavan üstte, taban ortada, çakışma ızgarada, kontenjan
   tabloda. Kayıt tuşuna basmadan önce tek ekranda görülmesi gereken şey.

   ⚠️ Üç durumlu: ✓ tamam · ✗ sorun var · — BURADAN BAKILAMAZ. Üçüncüsü
   şart; ör. transkript girilmemişse tavan bilinmiyor demektir, "tamam"
   demek olmaz. */
function kayitKontrol(){
  const ps = picks();
  const L = DATA.load || {};
  const t = totals();
  const satirlar = [];
  const ekle = (ok, ad, not) => satirlar.push({ok, ad, not});

  // 1) Kredi tavanı
  if(L.noTranscript)
    ekle(null, "Kredi tavanı", "transkript girilmedi — tavan bilinmiyor");
  else
    ekle(t.credits <= DATA.maxLoad + 1e-9, "Kredi tavanı",
         `${t.credits} / ${DATA.maxLoad} ${DATA.unitLabel}`);

  // 2) Çakışma — ızgaradaki kuralın AYNISI
  const carpisan = [];
  ps.forEach((a, i) => ps.slice(i + 1).forEach(b => {
    if(clash(a.sec, b.sec)) carpisan.push(`${a.cand.course} ↔ ${b.cand.course}`);
  }));
  ekle(!carpisan.length, "Çakışma yok", carpisan.join(", ") || "temiz");

  // 3) Kontenjan
  const doluOlan = ps.filter(p => !p.sec.free).map(p => p.cand.course);
  ekle(!doluOlan.length, "Kontenjan",
       doluOlan.length ? "dolu: " + doluOlan.join(", ")
                       : `${ps.length} şubede yer var (${esc(DATA.generatedAt)})`);

  // 4) Yarıyıl tabanı — YALNIZ ÇAP varsa ve başlangıç yarıyılı beyan edilmişse.
  // ⚠️ Beyan yoksa "tamam" değil, "bakılamıyor": yönerge tabanı başlangıç
  // yarıyılına bağlıyor ve biz onu bilmiyoruz.
  const F = DATA.secondFloor;
  if(F && !F.undeclared){
    const ikinci = +ps.filter(p => p.cand.role !== "ANADAL" && p.cand.role !== "PLAN_DISI")
                      .reduce((a, p) => a + (p.cand.credits || 0), 0).toFixed(1);
    ekle(ikinci + 1e-9 >= F.min, "İkinci anadal tabanı",
         `${ikinci} / ${F.min} kredi`);
  }else if(F){
    ekle(null, "İkinci anadal tabanı",
         "ÇAP'a başladığın yarıyıl beyan edilmedi — taban iddia edilmiyor");
  }

  // 5) CRN'ler elinde mi
  const crnYok = ps.filter(p => !p.sec.crn).map(p => p.cand.course);
  ekle(!crnYok.length, "Her dersin CRN'i var", crnYok.join(", ") || `${ps.length} CRN`);

  const isaret = (ok) => ok === null ? "—" : (ok ? "✓" : "✗");
  const sinif = (ok) => ok === null ? "unknown" : (ok ? "ok" : "bad");
  return `<div class="field"><span>Kayıt öncesi kontrol</span>
    <div class="checks">${satirlar.map(r => `
      <div class="check ${sinif(r.ok)}"><span class="mark">${isaret(r.ok)}</span>
        <span><b>${esc(r.ad)}</b> <span class="meta">${r.not}</span></span></div>`).join("")}
    </div>
    <span class="hint">&#8220;—&#8221; = buradan bakılamaz, sağlandı demek DEĞİL.
      Kontenjan sayıları son tazelemeye ait.</span></div>`;
}

function crnDialog(){
  const ps = picks();
  if(!ps.length){ openDialog(`<div class="empty">Programda ders yok.</div>`); return; }
  const list = ps.slice().sort((a, b) => a.cand.course.localeCompare(b.cand.course));
  const line = list.map(p => p.sec.crn).join(" ");
  /* ★ Faz 25/B2 — YEDEK PLAN. Eskiden yalnız "öbür CRN'ler" listeleniyordu;
     hangisinin çakıştığı, hangisinde yer kaldığı yazmıyordu. Kayıt gününde
     lazım olan cümle şu: "10493 dolarsa 10495'e geç, çakışma yok". */
  const alts = list.map(p => {
    const others = p.cand.sections.filter(s => s.crn !== p.sec.crn)
      .map(s => {
        const carpisan = conflictsWith(s, p.cand.course);
        return {s, carpisan, sira: (carpisan.length ? 1 : 0) * 1000 - s.free};
      })
      .sort((a, b) => a.sira - b.sira);
    return {course: p.cand.course, sec: p.sec, others};
  }).filter(x => x.others.length);
  openDialog(`
    <div class="eyebrow">Kayıt günü</div>
    <h2 style="margin-bottom:4px">CRN listesi</h2>
    <p class="modenote" style="margin:2px 0 10px">OBS'ye yazacağın numaralar.
      Araç senin yerine kayıt YAPMAZ — bu liste elle girmen için.</p>
    ${kayitKontrol()}
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
    ${alts.length ? `<details class="field"${
      /* Seçtiğin şubelerden biri doluysa yedek plan AÇIK gelsin — o an
         gerçekten lazım olan şey odur. */
      list.some(p => !p.sec.free) ? " open" : ""}>
      <summary style="cursor:pointer;font-size:13px;color:var(--seal)"
        >Yedek plan — seçtiğin şube dolarsa</summary>
      <div class="scroll" style="max-height:240px">
        <table class="trtable"><tbody>${alts.map(a => `<tr>
          <td style="vertical-align:top"><b class="mono">${esc(a.course)}</b>
            <div class="meta mono">şu an ${esc(a.sec.crn)}</div></td>
          <td>${a.others.map(o => `<div class="yedek ${
              o.carpisan.length ? "carpisir" : (o.s.free ? "uyar" : "dolu")}">
            <b class="mono">${esc(o.s.crn)}</b>
            <span class="mono">${o.s.free ? o.s.free + " boş" : "dolu"}</span>
            <span class="meta mono">${o.s.meetings.length
              ? o.s.meetings.map(m => `${DAYS[m.day-1]} ${hhmm(m.start)}`).join(", ")
              : "saati yok"}</span>
            <span class="meta">${o.carpisan.length
              ? "çıkarılır: " + o.carpisan.map(x => esc(x.cand.course)).join(", ")
              : "çakışmıyor"}</span>
          </div>`).join("")}</td></tr>`).join("")}</tbody></table>
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
  if(!btn) return;
  /* ★ Tarayıcıda (statik site) tarama yapılamaz: `httpx`/`selectolax` yok,
     üstelik OBS'ye tarayıcıdan istek atmak CORS'a takılır. Çalışmayacak bir
     düğme göstermek, kullanıcıya var olmayan bir yol önermek olurdu. */
  if(LIVE && DATA.canRefresh === false){
    btn.hidden = true;
    const not = $("#changeWhen");
    if(not) not.textContent = "Katalog siteyle birlikte yayınlanıyor; "
      + "dönem başında güncelleniyor.";
    return;
  }
  if(!LIVE) return;
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
  const kind = {ANADAL:"Anadal", CAP:"Çift anadal", YANDAL:"Yandal",
              PLAN_DISI:"Plan dışı"}[p.role] || p.role;
  const gain = (a) => a ? ` <span class="gain">+${a}</span>` : "";
  /* ★★ Faz 26 — TRANSKRİPT YOKKEN "%0" BİR ÖLÇÜM DEĞİL.
     Siteye ilk giren, bölümünü seçer seçmez "%0 tamamlandı · kalan zorunlu
     44" görüyordu. Bu, hakkında hiçbir şey bilmediğimiz kişiye "hiçbir şey
     yapmamışsın" demek. Kredi tavanında (Faz 24) ve başvuru şartlarında
     zaten düzeltilen hatanın aynısı, en görünür yerde duruyordu. */
  const bilinmiyor = DATA.load && DATA.load.noTranscript;
  return `<article class="card pad panel" data-role="${p.role}">
    <div class="top">
      <div>
        <div class="eyebrow">${kind}</div>
        <h2>${esc(p.program)}</h2>
      </div>
      <div class="pct mono${bilinmiyor ? " unknown" : ""}"
        title="${bilinmiyor ? "Geçtiğin dersler girilmedi" : ""}"
        >${bilinmiyor ? "—" : "%" + p.percent}</div>
    </div>
    <div class="name">${esc(p.title)}</div>
    ${bilinmiyor ? `<div class="proj bilinmiyor">
      <b>İlerleme bilinmiyor</b> — geçtiğin dersleri girmedin.
      Aşağıdaki sayılar <b>planın tamamı</b>, senin kalanın değil.
      ${LIVE ? `<button class="ghost" data-setup="plan"
        style="margin-left:8px">Dersleri gir</button>` : ""}</div>` : `
    <div class="meter">
      <i style="width:${Math.max(1, p.percent)}%"></i>
      <i class="plan" style="width:${Math.max(0, pctAfter - p.percent)}%"></i>
    </div>`}
    ${bilinmiyor ? "" : `<div class="proj">${plan.slots
      ? `bu dönem <b class="mono">${plan.slots}</b> slot dolarsa
         <span class="mono">%${p.percent}</span> <span class="arrow">→</span>
         <b class="mono">%${pctAfter}</b>`
      : `<span class="flat">bu dönemki seçimde bu plandan ders yok</span>`}</div>`}
    <div class="stats">
      <span>${bilinmiyor ? "planda slot" : "slot"}
        <b class="mono">${bilinmiyor ? p.slotsTotal
          : p.slotsDone + "/" + p.slotsTotal}</b>${gain(plan.slots)}</span>
      <span>kredi <b class="mono">${bilinmiyor ? p.creditsTotal
        : p.creditsDone + "/" + p.creditsTotal}</b>${gain(plan.credits)}</span>
      <span>akts <b class="mono">${bilinmiyor ? p.ectsTotal
        : p.ectsDone + "/" + p.ectsTotal}</b>${gain(plan.ects)}</span>
      <span>${bilinmiyor ? "zorunlu ders" : "kalan zorunlu"}
        <b class="mono">${p.openRequired}</b>${
        plan.required ? ` <span class="arrow">→</span>
          <b class="mono gain">${p.openRequired - plan.required}</b>` : ""}</span>
    </div>
    <div class="cats">${p.byCategory.map(c =>
      `<span class="cat${(bilinmiyor || c.done) ? "" : " zero"}">${esc(c.key)} ${
        bilinmiyor ? c.total : c.done + "/" + c.total}</span>`
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
  /* "İlerleme bilinmiyor" uyarısındaki düğme kurulum çubuğuyla AYNI işi
     yapıyor — tek yerden bağlanıyor ki iki davranış ayrışmasın. */
  $("#panels").querySelectorAll("[data-setup]").forEach(b =>
    b.addEventListener("click", () => ({program: programDialog, donem: termDialog,
                                        plan: checklistDialog,
                                        dersler: courseDialogSetup})[b.dataset.setup]()));
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
  /* ⚠️ Kip değişince geri yığını TEMİZLENİYOR: her kipin KENDİ aday havuzu
     var, öbür kipin seçimini geri yüklemek ızgarada olmayan bir dersi
     göstermeye çalışırdı. */
  GERI.length = 0;
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
/* ---------- açılmamış ders uyarısı (Faz 25/C3) ----------
   ★ "Bu dönem açılmamış" bilgisi darboğaz bölümünde vardı ama sayfanın
   AŞAĞISINDA. Oysa planındaki bir ders bu dönem hiç açılmadıysa bu, kayıt
   gününden ÖNCE bilinmesi gereken bir şey: mezuniyet planını değiştirir,
   yaz okulu ya da bir sonraki döneme kaydırma gerektirir.

   ⚠️ Dönem başında ilanlar KADEMELİ yayınlanıyor. "Hiç açılmayacak" demek
   yok; "şu ana kadar ilan edilmemiş" diyoruz ve tazeleme tarihini yazıyoruz. */
function renderArzUyarisi(){
  const kutu = $("#arzUyari");
  if(!kutu) return;
  const arz = (DATA.blockers || []).filter(
    b => b.reason === "ACILMAMIS" || b.reason === "PROGRAMA_KAPALI");
  if(!arz.length){ kutu.hidden = true; kutu.innerHTML = ""; return; }
  kutu.hidden = false;
  const acilmamis = arz.filter(b => b.reason === "ACILMAMIS");
  const kapali = arz.filter(b => b.reason === "PROGRAMA_KAPALI");
  const satir = (liste, ad) => liste.length
    ? `<div style="margin-top:4px"><b>${liste.length}</b> ders ${ad}:
       <span class="mono">${liste.slice(0, 6).map(b => esc(b.course)).join(", ")}${
         liste.length > 6 ? ` +${liste.length - 6}` : ""}</span></div>` : "";
  kutu.innerHTML = `
    <b>Planındaki bazı dersler bu dönem alınamıyor.</b>
    ${satir(acilmamis, "şu ana kadar ilan edilmemiş")}
    ${satir(kapali, "şubeleri başka programlara ayrılmış")}
    <div style="margin-top:6px" class="meta">Veri
      <span class="mono">${esc(DATA.generatedAt)}</span> itibarıyla —
      dönem başında ilanlar kademeli yayınlanıyor.
      <a href="#blockSection" id="arzDetay">Darboğaz bölümünde ayrıntı</a>.</div>`;
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
  /* ★ Taban eksiği sekmede GÖRÜNÜYOR (yapılacaklar 1.4). Motor artık tabanı
     karşılayan programı öne alıyor; karşılamayan da listede kalıyor çünkü
     taban indirilebilir ve o dönem açılan ders yetmiyor olabilir. Ama
     hangisinin eksik olduğu yazmadan sunmak, kabul edilemez bir programı
     "en iyi" diye göstermek olurdu. */
  $("#tabs").innerHTML = M().schedules.map((s,i) => {
    const eksik = (s.floorGaps || []);
    return `<button class="tab" role="tab" aria-selected="${i===active}" data-i="${i}"
       ${eksik.length ? `title="taban eksiği: ${eksik.map(g =>
         `${g.role} ${g.missing} kredi`).join(", ")}"` : ""}>
       Öneri ${i+1} · ${s.credits} kredi${eksik.length
         ? ` <span style="color:var(--danger)">· taban ✗</span>` : ""}</button>`;
  }).join("") || `<span class="empty">öneri üretilemedi</span>`;
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
  /* ★ Plan dışı ders SAYILIYOR ama SAYILMIYOR: kredisi dönem yüküne girer
     (kayıtta da öyle), hiçbir plan şartını doldurmaz. İkisi aynı satırda
     yazmazsa kullanıcı 13 krediyi görüp "%43 → %50 olmalıydı" diye
     düşünüyor. Sessiz kalmak, farkı hataya çeviriyordu. */
  const disKredi = picks().filter(p => p.cand.role === "PLAN_DISI")
    .reduce((a, p) => a + (p.cand.credits || 0), 0);
  $("#schedSummary").innerHTML = `
    <span class="dot"><i style="background:var(--anadal)"></i>anadal</span>
    ${SECONDS().length ? `<span class="dot"><i style="background:var(--cap)"></i>${
      esc(LBL)}</span>` : ""}
    <span>${t.n} ders</span>
    <span class="mono${over ? " over" : ""}">${t.credits} kredi · ${t.ects} AKTS</span>
    ${disKredi ? `<span class="planout">bunun <b class="mono">${disKredi}</b>
      kredisi <b>plan dışı</b> — yüke sayılır, şart doldurmaz</span>` : ""}
    <span>sınır <b class="mono">${DATA.maxLoad} ${DATA.unitLabel}</b>${
      over ? ' <span class="over">aşıldı</span>' : ""}</span>
    <span>puan <b class="mono">${t.score}</b></span>`;
  $("#editState").hidden = !edited();
  $("#reset").hidden = !edited();
  renderSaveState();
  renderFloor();
  renderArzUyarisi();
  renderGeri();

  const cells = {}, spans = {}, timeless = [];
  /* ★ Meşgul saatler ders bloklarıyla AYNI hücre haritasına giriyor.
     Ayrı bir katman çizseydik üst üste binerlerdi; motor zaten bu saatlere
     ders koymuyor (bkz. REC.busy_sections), ızgara da öyle davranmalı. */
  (DATA.busy || []).filter(b => b.ok).forEach((b, i) => {
    const a = Math.max(0, Math.floor((b.start - T0) / STEP));
    const z = Math.min(ROWS, Math.ceil((b.end - T0) / STEP));
    if(z <= a) return;
    cells[`${b.day}-${a}`] = {busy: b, span: Math.max(1, z - a)};
    for(let r = a + 1; r < z; r++) spans[`${b.day}-${r}`] = true;
  });
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
      if(c.busy){
        html += `<td rowspan="${c.span}" class="busycell"><div class="blk mesgul"
          data-busy="${esc(c.busy.raw)}" tabindex="0" role="button"
          title="Kaldırmak için tıkla">
          <b>${esc(c.busy.label)}</b>
          <small class="mono">${hhmm(c.busy.start)}–${hhmm(c.busy.end)}</small>
        </div></td>`;
        continue;
      }
      /* ⚠️ Hoca adı hücreye YAZILMIYOR, `title` olarak veriliyor: ızgara
         hücresi zaten dar ve ders kodu okunmaz hale gelirdi. Şube seçme
         penceresinde tam adıyla duruyor. */
      html += `<td rowspan="${c.span}"><div class="blk" data-role="${c.p.cand.role}"
          data-course="${esc(c.p.cand.course)}" tabindex="0" role="button"
          title="${esc([c.p.cand.name, c.p.sec.instructor,
                        "CRN " + c.p.sec.crn].filter(Boolean).join(" · "))}">
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
  $("#grid").querySelectorAll(".blk.mesgul").forEach(el =>
    bind(el, () => busyDialog(null, null, el.dataset.busy)));

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

  renderCandFilters();
  renderCandidates();
}

function bind(el, fn){
  el.addEventListener("click", fn);
  el.addEventListener("keydown", e => {
    if(e.key === "Enter" || e.key === " "){ e.preventDefault(); fn(); }
  });
}

/* ---------- seçim işlemleri ---------- */
/* ★ Faz 25/D2 — GERİ AL. Yanlışlıkla ders çıkarınca geri getirmenin yolu
   yoktu; "Öneriye dön" tüm programı sıfırlıyordu, yani bir hatayı düzeltmek
   için bütün emeği silmek gerekiyordu.

   ⚠️ Yığın SEÇİMİN TAMAMINI saklıyor, "şu dersi geri koy" değil: bir ders
   eklemek çakışan başkalarını da çıkarabiliyor (havuz kuralı, saat çakışması).
   Tek dersi geri koymak, onunla birlikte düşenleri geride bırakırdı. */
const GERI = [];
const GERI_DERINLIK = 20;

function geriKaydet(etiket){
  GERI.push({sel: sel.map(x => ({...x})), etiket});
  if(GERI.length > GERI_DERINLIK) GERI.shift();
}

function geriAl(){
  const onceki = GERI.pop();
  if(!onceki) return false;
  sel = onceki.sel;
  render();
  return true;
}

function renderGeri(){
  const b = $("#undo");
  if(!b) return;
  b.hidden = !GERI.length;
  const son = GERI[GERI.length - 1];
  b.textContent = son && son.etiket ? `Geri al: ${son.etiket}` : "Geri al";
}

function choose(course, crn){
  const cand = CAND[course], sec = sectionOf(course, crn);
  if(!cand || !sec) return;
  const vardi = sel.some(x => x.course === course);
  geriKaydet(vardi ? `${course} şube değişikliği` : `${course} eklendi`);
  sel = sel.filter(x => x.course !== course);
  const drop = new Set(conflictsWith(sec, course).map(p => p.cand.course));
  const pool = poolBlocker(cand, course);
  if(pool) drop.add(pool.cand.course);
  sel = sel.filter(x => !drop.has(x.course));
  sel.push({course, crn});
  render();
}
function removeCourse(course){
  geriKaydet(`${course} çıkarıldı`);
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
        ${section.online ? `<span class="chip online"
          style="margin-left:6px">çevrimiçi</span>` : ""}
        <div class="meta">${esc(cand.name)} · ${cand.credits} kredi / ${cand.ects} AKTS
          · puan ${cand.score}${note ? " · " + esc(note) : ""}</div>
        <div style="margin-top:4px">${doluluk([section])}</div></span>
      <span class="meta mono" style="text-align:right;white-space:nowrap">
        CRN ${esc(section.crn)}<br>${times}
        ${section.instructor
          ? `<br><span class="hoca">${esc(section.instructor)}</span>` : ""}</span>
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
      ? `<div class="empty">bu güne uyan aday ders yok</div>` : ""}
    ${LIVE ? `<div style="margin-top:14px;padding-top:12px;
         border-top:1px solid var(--border)">
      <button class="ghost" id="busyAdd">Bu saati derse kapat</button>
      <div class="why" style="margin-top:6px">Okul dışı bir işin varsa
        (staj, antrenman, servis) bu saati kapatabilirsin — motor buraya
        ders koymaz.</div></div>` : ""}`);
  const ba = $("#busyAdd");
  if(ba) ba.addEventListener("click", () => {
    $("#detail").close();
    busyDialog(day, min);
  });
}

/* ---------- Ders konulamayacak saatler ----------
   Kullanıcı isteği 22.08.2026: "planda ders seçilemeyecek yerler
   belirlenebilmeli okul dışı aktiviteler için".

   ★ Bu SERT bir kısıt: çakışan şube hiç önerilmiyor. Motor tarafında yeni
   bir çakışma mantığı yazılmadı — aralık, zaten kayıtlı bir ders gibi
   `build_schedules(fixed=…)` ile veriliyor (bkz. REC.busy_sections). İki
   ayrı çakışma tanımı olsaydı biri düzelirken öbürü unutulurdu. */
function busyDialog(day, min, remove){
  if(remove){
    const b = (DATA.busy || []).find(x => x.raw === remove) || {};
    openDialog(`
      <div class="eyebrow">Kapalı saat</div>
      <h2>${esc(b.label || "meşgul")}</h2>
      <div class="meta" style="color:var(--ink-2);font-size:13px;margin:4px 0 14px">
        ${b.ok ? `${DAYS[b.day-1]} ${hhmm(b.start)}–${hhmm(b.end)}`
               : `<span class="mono">${esc(remove)}</span> — okunamadı`}
      </div>
      <button class="ghost danger" id="busyDel">Bu saati aç</button>`);
    $("#busyDel").addEventListener("click", async () => {
      const btn = $("#busyDel");
      btn.disabled = true; btn.textContent = "…";
      try{
        applyState(await api("/api/mesgul", {remove}));
        $("#detail").close();
      }catch(err){ btn.disabled = false; btn.textContent = "hata: " + err.message; }
    });
    return;
  }
  // Varsayılan aralık: tıklanan hücreden 2 saat. Kullanıcı daraltabilir.
  const bas = min, bit = Math.min(24*60, min + 120);
  openSetup(`
    <div class="eyebrow">Kurulum</div>
    <h2 style="margin-bottom:4px">Bu saati derse kapat</h2>
    <p class="modenote" style="margin:2px 0 10px">Motor bu aralığa ders
      koymayacak. Kaldırmak için ızgaradaki taralı bloğa tıkla.</p>
    <label class="field"><span>Gün</span>
      <div class="terms" id="fGun">
        ${DAYS.map((d, i) => `<button data-d="${i+1}"
          aria-pressed="${i+1 === day}" style="width:auto;padding:7px 12px"
          >${d}</button>`).join("")}
      </div></label>
    <label class="field" style="margin-top:12px"><span>Saat</span>
      <div style="display:flex;gap:8px;align-items:center">
        <input type="time" id="fBas" value="${hhmm(bas)}" step="900">
        <span style="color:var(--ink-3)">–</span>
        <input type="time" id="fBit" value="${hhmm(bit)}" step="900">
      </div></label>
    <label class="field" style="margin-top:12px"><span>Ne için?</span>
      <input type="text" id="fAd" maxlength="40" placeholder="iş, antrenman, servis…">
      <span class="hint">İsteğe bağlı — ızgarada bu yazacak.</span></label>`, () => {
    let gun = day;
    $("#fGun").querySelectorAll("button").forEach(b =>
      b.addEventListener("click", () => {
        gun = +b.dataset.d;
        $("#fGun").querySelectorAll("button").forEach(x =>
          x.setAttribute("aria-pressed", +x.dataset.d === gun));
      }));
    $("#setupSave").addEventListener("click", () => {
      const toMin = (v) => {
        const [h, m] = String(v || "").split(":").map(Number);
        return (h || 0) * 60 + (m || 0);
      };
      save(() => api("/api/mesgul", {
        day: gun, start: toMin($("#fBas").value), end: toMin($("#fBit").value),
        label: $("#fAd").value}));
    });
  });
}

$("#reset").addEventListener("click", () => {
  /* "Öneriye dön" de geri alınabilir olmalı: yanlışlıkla basan kişi
     bütün emeğini kaybediyordu. */
  geriKaydet("öneriye dönüldü");
  resetTo(active);
});
$("#undo").addEventListener("click", () => geriAl());
/* Ctrl/Cmd+Z — yazı alanında değilken. */
document.addEventListener("keydown", (e) => {
  if((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z" && !e.shiftKey){
    const t = e.target;
    if(t && /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)) return;
    if(geriAl()) e.preventDefault();
  }
});

/* ---------- aday listesi ----------
   ★ Süzgeç (24.08.2026). Üç ayrı sorunu birden kapatıyor:
     * liste 30'da kesiliyordu — 31. sıradaki ders arayana YOK görünüyordu,
     * "şu dersi almak istiyorum" diyen kişi listeyi gözle tarıyordu,
     * anadal/ÇAP karışık geldiği için "yalnız kendi bölümüm" bakılamıyordu.
   ⚠️ Arama SIRALAMAYI değiştirmiyor; puan sırası korunuyor. Eşleşmeye göre
   yeniden sıralamak, motorun gerekçeli sırasını sessizce ezerdi. */
const FILT = {q: "", role: "", free: false};
const LIMIT = 30;

function filteredCandidates(){
  const q = FILT.q.trim().toLocaleLowerCase("tr");
  return M().candidates.filter(c => {
    if(FILT.role && c.role !== FILT.role) return false;
    if(FILT.free && !c.sections.some(s => s.free > 0)) return false;
    if(!q) return true;
    /* ★ `altName` = aynı dersin ÖBÜR DİLDEKİ adı (MAT 271E ↔ MAT 271).
       İngilizce programın öğrencisi listede "Probability" görüyor ama
       "olasılık" arıyor.
       ★ Hoca adı da aranıyor (Faz 25/B5): öğrencinin gerçekte kullandığı
       ölçütlerden biri "şu hocayı istiyorum". 2530 şubede gerçek ad var. */
    const metin = c.course + " " + c.name + " " + (c.altName || "") + " " +
      c.sections.map(s => s.instructor || "").join(" ");
    return metin.toLocaleLowerCase("tr").includes(q);
  });
}

function renderCandFilters(){
  const roles = [...new Set(M().candidates.map(c => c.role))];
  const box = $("#candRole");
  if(!box) return;
  /* Tek rol varsa (ÇAP/yandal yok) düğmeler gereksiz gürültü. */
  box.hidden = roles.length < 2;
  if(box.hidden){ FILT.role = ""; return; }
  box.innerHTML = [["", "Hepsi"], ...roles.map(r => [r, r])].map(([v, l]) =>
    `<button data-r="${esc(v)}" aria-pressed="${v === FILT.role}">${esc(l)}</button>`).join("");
  box.querySelectorAll("button").forEach(b => b.addEventListener("click", () => {
    FILT.role = b.dataset.r; renderCandFilters(); renderCandidates();
  }));
}

/* ★ Doluluk ÇUBUĞU (24.08.2026). "0/240" ile "18/18" arasındaki farkı
   görmek için hesap yapmak gerekiyordu; kayıt gününde bakılan tek şey bu.
   ⚠️ Kontenjan TAZELEME ANINA ait — "şu an boş" değil, "şu tarihte boştu".
   Onu `title`'a yazıyoruz ki sayı yaşsız bir gerçek gibi durmasın. */
function doluluk(sections){
  const cap = sections.reduce((a, s) => a + (s.capacity || 0), 0);
  const dolu = sections.reduce((a, s) => a + (s.enrolled || 0), 0);
  const bos = Math.max(0, cap - dolu);
  if(!cap) return `<span class="mono" style="color:var(--ink-3)"
    title="Kontenjan ilan edilmemiş">${sections.length} şube · kontenjan yok</span>`;
  const oran = Math.min(1, dolu / cap);
  const sinif = bos === 0 ? "full" : (bos <= 3 ? "tight" : "");
  return `<span class="cap ${sinif}" title="${esc(DATA.generatedAt)} itibarıyla">
      <span class="capbar"><i style="width:${(oran * 100).toFixed(0)}%"></i></span>
      <span class="mono">${bos === 0 ? "dolu" : bos + " boş"}</span>
      <span class="mono capsub">${sections.length} şube</span></span>`;
}

/* ★ "119 dersin önşartı" sayısı ikna edici değil; hangi dersler olduğu
   ikna edici. `opens` = SENİN planındaki, HENÜZ GEÇMEDİĞİN dersler. */
function acilanNot(c){
  const a = c.opens || [];
  if(!a.length) return "";
  const bas = a.slice(0, 4).map(esc).join(", ");
  return ` <span class="opens" title="${esc(a.join(", "))}">↳ açtıkları: ${bas}${
    a.length > 4 ? ` +${a.length - 4}` : ""}</span>`;
}

function renderCandidates(){
  const chosen = new Set(sel.map(x => x.course));
  const hepsi = filteredCandidates();
  /* ★ Arama yapılmışken kesme YOK: aradığın ders 40. sıradaysa da gelmeli. */
  const list = FILT.q.trim() ? hepsi : hepsi.slice(0, LIMIT);
  const cnt = $("#candCount");
  if(cnt) cnt.textContent = hepsi.length === M().candidates.length
    ? (hepsi.length > list.length
        ? `${M().candidates.length} aday · ilk ${list.length} listeleniyor`
        : `${hepsi.length} aday`)
    : `${M().candidates.length} adaydan ${hepsi.length} tanesi`;
  $("#cands tbody").innerHTML = list.map(c => {
    const free = Math.max(0, ...c.sections.map(s => s.free));
    const inPlan = chosen.has(c.course);
    return `<tr data-course="${esc(c.course)}" style="cursor:pointer"
        title="${inPlan ? "programında" : "programa ekle"}">
      <td class="mono score">${c.score}</td>
      <td><b class="mono">${esc(c.course)}</b>
        ${inPlan ? `<span class="chip" style="margin-left:6px;color:var(--anadal)">programda</span>` : ""}
        ${c.critical ? `<span class="chip supply" style="margin-left:6px">kritik yol</span>` : ""}
        ${c.sections.every(s => s.online)
          ? `<span class="chip online" style="margin-left:6px">çevrimiçi</span>`
          : (c.sections.some(s => s.online)
             ? `<span class="chip online" style="margin-left:6px">çevrimiçi şube var</span>` : "")}
        <div class="why">${esc(c.name)}${c.reasons.length
          ? " — " + c.reasons.map(esc).join("; ") : ""}${acilanNot(c)}</div></td>
      <td><span class="tag ${c.role}">${c.role}</span></td>
      <td class="mono">${c.credits}</td>
      <td class="mono" style="color:var(--ink-3)">${c.ects}</td>
      <td>${doluluk(c.sections)}</td>
    </tr>`;
  }).join("") || `<tr><td colspan="6" class="empty">${
    /* ★ İki BOŞ birbirinden ayrı: süzgeç boşalttıysa çıkış yolunu söyle,
       havuz baştan boşsa NEDEN boş olduğunu söyle. Tek bir "aday ders yok"
       ikisini de aynı çıkmaza sokuyordu. */
    (FILT.q || FILT.role || FILT.free)
      ? `süzgece uyan ders yok — <a href="#" id="candClear">süzgeci temizle</a>`
      : (M().candidates.length
          ? "aday ders yok"
          : "aday ders yok — bölümünü ve geçtiğin dersleri girdiğinden emin ol")
  }</td></tr>`;
  $("#cands tbody").querySelectorAll("tr[data-course]").forEach(tr =>
    tr.addEventListener("click", () => addDialog(tr.dataset.course)));
  const clr = $("#candClear");
  if(clr) clr.addEventListener("click", (e) => {
    e.preventDefault();
    FILT.q = ""; FILT.role = ""; FILT.free = false;
    $("#candQ").value = ""; $("#candFree").checked = false;
    renderCandFilters(); renderCandidates();
  });
}

$("#candQ").addEventListener("input", (e) => {
  FILT.q = e.target.value; renderCandidates();
});
$("#candFree").addEventListener("change", (e) => {
  FILT.free = e.target.checked; renderCandidates();
});
$("#katalogBtn").addEventListener("click", () => katalogDialog());

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

/* ---------- karşılama ----------
   ★ Üç adım ve sırası önemli: bölüm seçilmeden transkript anlamsız,
   transkript girilmeden öneri "her şeyi alabilirsin" der. */
function renderHero(){
  const O = DATA.onboarding, box = $("#hero");
  if(!box) return;
  if(!O){ box.hidden = true; document.body.classList.remove("kurulum"); return; }
  box.hidden = false;
  /* `blocking` = bölüm bile seçilmemiş. O zaman rapor bölümleri gizleniyor:
     gösterilecek doğru bir şey yok. Sonraki adımlar eksikse rapor duruyor
     ama üstte ne yapılacağı yazıyor — o durumda veri var, sadece eksik. */
  document.body.classList.toggle("kurulum", !!O.blocking);
  /* ★ Bölüm seçilmişse araç çalışıyor demektir; transkript girmek
     istemeyen kişi bu şeridi sonsuza kadar görmemeli. Kapatma tercihi
     tarayıcıda kalıyor, kurulum çubuğundan her zaman geri dönülebilir.
     ⚠️ ZORUNLU adım eksikken kapatılamıyor — o zaman gösterilecek doğru
     bir rapor yok, şeridi gizlemek kullanıcıyı boş ekranda bırakırdı. */
  if(!O.blocking && localStorage_get("heroKapali")){
    box.hidden = true;
    return;
  }
  const ACT = {program: () => programDialog(), plan: () => checklistDialog(),
               donem: () => termDialog()};

  const zorunlu = O.steps.filter(s => s.required);
  const istege  = O.steps.filter(s => !s.required);
  const acik    = zorunlu.every(s => s.done);      /* araç çalışıyor mu */
  /* ★ TEK birincil eylem: sıradaki ilk yapılmamış adım. Yedi düğme arasından
     hangisine basılacağını kullanıcıya seçtirmek, "nasıl yapacağımı
     anlayamıyorum" hissinin ana kaynağıydı. */
  const sonraki = O.steps.find(s => !s.done);

  /* ⚠️ Sıradaki adımın düğmesi satırda TEKRARLANMIYOR: yukarıdaki büyük
     düğme zaten o. Aynı eylemi iki kez sunmak, "hangisine basacağım"
     sorusunu geri getiriyordu. */
  const stepHTML = (s, kilitli) => `
    <div class="step ${s.done ? "done" : ""} ${kilitli ? "kilit" : ""} ${
      s === sonraki ? "simdi" : ""}">
      <span class="no">${s.done ? "✓" : (kilitli ? "🔒" : "→")}</span>
      <span class="body"><b>${esc(s.label)}</b>
        <span>${s.detail}</span>
        <span class="why">${s.why}</span></span>
      ${s.done
        ? `<span class="chip" style="color:var(--anadal)">tamam</span>`
        : (LIVE && s !== sonraki
            ? `<button class="ghost" data-act="${s.action}"
                 ${kilitli ? "disabled title='Önce bölümünü seç'" : ""}
                 >${esc(s.cta)}</button>`
            : (s === sonraki
               ? `<span class="chip" style="color:var(--seal)">şimdi ↑</span>` : ""))}
      <span class="sure">${esc(s.sure)}</span>
    </div>`;

  box.innerHTML = `
    <div class="sechead"><div class="eyebrow">Başlangıç</div><div class="rule"></div></div>
    <h2>${acik ? "Araç çalışıyor — istersen daha da iyileştir"
                : "Hoş geldin — tek adımda başla"}</h2>
    <p class="lead">${acik
      ? `Aşağıdaki haftalık program <b>şu an çalışıyor</b>. Aşağıdaki iki şey
         <b>isteğe bağlı</b>; girersen öneriler senin durumuna göre kurulur.`
      : `İTÜ'nün açık derslerinden sana <b>çakışmasız bir haftalık program</b>
         kuruyor: önşartın tutuyor mu, kontenjan var mı, hangi ders hangi
         kapıyı açıyor. <b>Tek zorunlu şey bölümünü seçmen</b> — çift anadal
         ya da yandal yapmıyorsan da kullanabilirsin.`}</p>

    ${sonraki && LIVE ? `
      <div class="heroCta">
        <button class="ghost primary big" data-act="${sonraki.action}"
          >${esc(sonraki.cta)}</button>
        <span class="meta">${esc(sonraki.sure)}${
          sonraki.required ? "" : " · isteğe bağlı"}</span>
        ${acik ? `<a href="#schedSection" class="heroSkip">Programı gör ↓</a>
          <button class="ghost heroDismiss" data-kapat="1"
            >Şimdilik böyle kalsın</button>` : ""}
      </div>` : ""}

    <div class="steps">${zorunlu.map(s => stepHTML(s, false)).join("")}</div>
    ${istege.length ? `
      <div class="stepsplit">Daha iyi öneri için ${
        acik ? "" : "(bölümü seçtikten sonra)"}</div>
      <div class="steps">${istege.map(s => stepHTML(s, !acik)).join("")}</div>` : ""}

    <div class="herofoot">
      Seçebileceğin <b class="mono">${O.planCount}</b> bölüm ve
      <b class="mono">${O.lessonCount}</b> açık şube var.
      ${LIVE ? "" : `Bu <b>salt okunur</b> bir kopya —
        düzenlemek için <span class="mono">make app</span>.`}
      <div style="margin-top:6px">Girdiğin hiçbir şey sunucuya gitmiyor;
        veri tarayıcında kalıyor.</div>
    </div>`;
  box.querySelectorAll("[data-act]").forEach(b =>
    b.addEventListener("click", () => (ACT[b.dataset.act] || (() => {}))()));
  const kapat = box.querySelector("[data-kapat]");
  if(kapat) kapat.addEventListener("click", () => {
    localStorage_set("heroKapali", "1");
    box.hidden = true;
    renderSonraki();
  });
}

/* ---------- kurulumdan sonra: şimdi ne yapabilirsin (Faz 26) ----------
   ★ Kurulum bitince ekranda dokuz bölüm birden açılıyordu ve hiçbiri
   "şimdi şunu yap" demiyordu. Bir kerelik, kapatılabilir bir şerit:
   üç somut eylem, hepsi tıklanabilir. */
function renderSonraki(){
  const el = $("#sonraki");
  if(!el) return;
  /* Kurulum sürerken gösterme: karşılama kartıyla yarışır. Karşılama
     kapatılmışsa (kullanıcı "şimdilik böyle kalsın" dedi) rapor görünür
     durumda demektir — o zaman gösterilebilir. */
  const heroDuruyor = DATA.onboarding && !localStorage_get("heroKapali");
  if(heroDuruyor || !LIVE || localStorage_get("sonrakiKapali")){
    el.hidden = true; return;
  }
  el.hidden = false;
  el.innerHTML = `
    <b>Programın hazır. Şimdi:</b>
    <div class="sonrakiliste">
      <button class="ghost" data-go="schedSection">Haftalık programa bak</button>
      <button class="ghost" data-go="candSection">Ders ekle / değiştir</button>
      <button class="ghost" data-go="crn">Kayıt günü listesini al</button>
      <button class="ghost kapat" data-kapat="1">Kapat</button>
    </div>`;
  el.querySelectorAll("[data-go]").forEach(b => b.addEventListener("click", () => {
    if(b.dataset.go === "crn"){ crnDialog(); return; }
    const hedef = document.getElementById(b.dataset.go);
    if(hedef) hedef.scrollIntoView({behavior: "smooth", block: "start"});
  }));
  el.querySelector("[data-kapat]").addEventListener("click", () => {
    localStorage_set("sonrakiKapali", "1");
    el.hidden = true;
  });
}

/* ⚠️ `localStorage` bazı bağlamlarda (gizli sekme, site verisi engelli)
   ERİŞİLDİĞİNDE bile hata fırlatıyor. Kapatma tercihi kaybolabilir ama
   sayfa çalışmayı sürdürmeli. */
function localStorage_get(k){
  try{ return localStorage.getItem("itucap." + k); }catch(e){ return null; }
}
function localStorage_set(k, v){
  try{ localStorage.setItem("itucap." + k, v); }catch(e){ /* önemli değil */ }
}

/* ---------- bölüm çubuğu ----------
   Gizli bölüm çubukta da yok: veri gelince (transkript yüklenince, denklik
   önerisi çıkınca) bölüm açılıyor ve bağlantısı kendiliğinden beliriyor. */
const SECTIONS = [
  ["savedSection", "Kayıtlı"], ["panels", "İlerleme"], ["schedSection", "Program"],
  ["creditSection", "Eşikler"], ["suggestSection", "Denklik"],
  ["changeSection", "Değişim"], ["candSection", "Adaylar"],
  ["blockSection", "Darboğaz"], ["basvuruSection", "Başvuru"],
  ["tierSection", "Kademeler"],
];

function renderSecNav(){
  const nav = $("#secnav");
  if(!nav) return;
  const acik = SECTIONS.filter(([id]) => {
    const el = document.getElementById(id);
    return el && !el.hidden && el.offsetParent !== null;
  });
  nav.innerHTML = acik.length < 3 ? ""
    : acik.map(([id, lbl]) => `<a href="#${id}">${lbl}</a>`).join("");
  nav.querySelectorAll("a").forEach(a => a.addEventListener("click", ev => {
    ev.preventDefault();
    document.getElementById(a.hash.slice(1))
            .scrollIntoView({behavior: "smooth", block: "start"});
  }));
  markCurrentSection();
}

/* Hangi bölümdeyiz — çubukta işaretli dursun. IntersectionObserver yerine
   kaydırma anında ölçüyoruz: bölümler açılıp kapandığı için gözlemciyi her
   çizimde yeniden kurmak gerekirdi. */
function markCurrentSection(){
  const nav = $("#secnav");
  if(!nav || !nav.children.length) return;
  let simdiki = nav.children[0].hash.slice(1);
  for(const a of nav.children){
    const el = document.getElementById(a.hash.slice(1));
    if(el && el.getBoundingClientRect().top <= 80) simdiki = a.hash.slice(1);
  }
  for(const a of nav.children)
    a.setAttribute("aria-current", String(a.hash.slice(1) === simdiki));
}
addEventListener("scroll", () => requestAnimationFrame(markCurrentSection),
                 {passive: true});

const BASVURU_KINDS = [["cap", "Çift anadal", "ÇAP planları"],
                       ["yandal", "Yandal", "Yandal planları"]];

/* Sayfada duran KISA hâl: iki satır, her birinde pencereyi açan düğme.
   Ayrıntı (şartlar + program tablosu) pencerede — dönemde birkaç kez
   bakılan bir şey sayfanın en uzun bölümü olmamalı. */
function renderBasvuru(){
  const all = DATA.basvuru;
  const sec = $("#basvuruSection");
  if(!all || !sec) return;
  const satirlar = BASVURU_KINDS.filter(([k]) => all[k]).map(([k, lbl, btn]) => {
    const s = all[k];
    const iyi = s.eligible;
    const durum = !iyi ? "bir şart sağlanmıyor"
      : s.unknownCount ? `bakılabilenler tamam · ${s.unknownCount} şart buradan görülemiyor`
      : "bakılabilen tüm şartlar sağlanıyor";
    const sayi = s.planTypeAvailable === false ? "OBS'de plan yayınlanmamış"
      : s.optionCount ? `${s.optionCount} program açık` : "sana açık plan yok";
    return `<div class="basvuruitem">
      <span class="mark" style="color:${iyi ? "var(--anadal)" : "var(--danger)"}"
        >${iyi ? "✓" : "✗"}</span>
      <span class="what"><b>${lbl}</b><span class="why">${esc(durum)} · ${esc(sayi)}</span></span>
      <button class="ghost" data-k="${k}">${btn}</button></div>`;
  }).join("");
  if(!satirlar){ sec.hidden = true; return; }
  sec.hidden = false;
  $("#basvuruSummary").innerHTML = satirlar;
  $("#basvuruSummary").querySelectorAll("button[data-k]").forEach(b =>
    b.addEventListener("click", () => openBasvuru(b.dataset.k)));
}

function openBasvuru(kind){
  basvuruKind = kind || basvuruKind;
  renderBasvuruBody();
  $("#basvuruDlg").showModal();
}

function renderBasvuruBody(){
  const all = DATA.basvuru;
  $("#basvuruDlgTitle").textContent =
    (BASVURU_KINDS.find(([k]) => k === basvuruKind) || [,, "Planlar"])[2];
  $("#basvuruTabs").innerHTML = BASVURU_KINDS.filter(([k]) => all[k])
    .map(([k, lbl]) => `<button class="tab" role="tab" data-k="${k}"
       aria-selected="${k === basvuruKind}">${lbl}</button>`).join("");
  $("#basvuruTabs").querySelectorAll(".tab").forEach(b =>
    b.addEventListener("click", () => { basvuruKind = b.dataset.k; renderBasvuruBody(); }));
  $("#basvuruDlg").querySelectorAll("[data-close]").forEach(b =>
    b.addEventListener("click", () => $("#basvuruDlg").close()));

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
    ${s.planTypeAvailable === false ? `
      <div class="note" style="margin-top:14px;border-left-color:var(--warn)">
        <b>İTÜ ${basvuruKind === "cap" ? "ÇAP" : "yandal"} ders planlarını
        OBS'de yayınlamıyor.</b>
        Uç çalışıyor ve doğru sorgulanıyor; OBS
        <i>“Akademik programa bağlı ders planı bulunmamaktadır”</i> diyor —
        128 programın hiçbirinde plan yok (doğrulandı 22.08.2026).
        <div style="margin-top:6px">Yukarıdaki <b>şartlar</b> yönergeden
        geliyor ve geçerli; ama plan olmadan “kaç ders kalır” sorusunu
        <b>cevaplayamayız</b> ve uydurmayız. Yandal düşünüyorsan planı
        bölümünden iste.</div>
      </div>` : (s.missingCount ? `
      <div class="note" style="margin-top:14px">
        <b>${s.missingCount}</b> programın ${basvuruKind === "cap" ? "ÇAP" : "yandal"}
        planı henüz çekilmemiş, o yüzden listede yoklar.
        <b>Lisans planından tahmin YAPILMIYOR</b> — ${basvuruKind === "cap" ? "ÇAP" : "yandal"}
        planı lisansın küçük bir alt kümesi, oradan hesaplamak kalan işi
        iki katından fazla şişirirdi. Doldurmak için:
        <span class="mono">make all-plans</span>.
      </div>` : "")}`;
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
      /* İki ikinci program varsa hangisine ait olduğu YAZIYOR — ayrımsız
         liste "hangi program yüzünden takıldım" sorusunu cevapsız bırakırdı. */
      const etiket = SECONDS().length > 1 && b.label
        ? `<span class="tag ${b.role === "YANDAL" ? "YANDAL" : "CAP"}"
             style="margin-left:6px">${esc(b.label)}</span>` : "";
      return `<div class="blockitem"><b class="mono">${esc(b.course)}</b>${etiket}
        ${esc(b.detail)}
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
/* ★ Kullanıcı isteği 22.08.2026: "çap kademelerini birbirine önşartla bağlı
   olanları belli edecek şekilde olsun".

   İki katman:
   1. Her ders kutusu KENDİ önşartlarını yazıyor (metin — kopyalanabilir,
      yazdırılabilir, çizgiler çizilmese bile bilgi kaybolmaz).
   2. Kutular arası SVG çizgiler bağı gösteriyor; bir derse tıklayınca yalnız
      o dersin zinciri (öncesi + sonrası) kalıyor.

   Plan İÇİ önşart ile plan DIŞI önşart bilinçli olarak AYRI gösteriliyor:
   dışarıdakiler kademeyi belirlemiyor (anadalda alınmış olabilirler) ve aynı
   çizgiyle göstermek "bu ÇAP dersi şu ÇAP dersine bağlı" izlenimi verirdi. */
let tierFocus = null;

function tierGraph(tiers){
  const needs = {}, opens = {};
  tiers.forEach(t => t.courses.forEach(c => {
    needs[c.course] = c.needs || [];
    opens[c.course] = c.opens || [];
  }));
  return {needs, opens};
}

/* Zincir = seçilen dersin bütün ataları + bütün torunları. */
function tierChain(tiers, code){
  const g = tierGraph(tiers), out = new Set([code]);
  const walk = (node, map) => (map[node] || []).forEach(n => {
    if (!out.has(n)) { out.add(n); walk(n, map); }
  });
  walk(code, g.needs); walk(code, g.opens);
  return out;
}

function renderTiers(){
  const wrap = $("#tierGroups");
  if (!wrap) return;
  tierFocus = null;                     /* veri değiştiyse eski seçim geçersiz */
  const gruplar = (DATA.tierGroups || []).filter(g => (g.tiers || []).length);
  /* ★ İkinci program yoksa bu bölümün gösterecek bir şeyi yok. Boş kart
     bırakmak, aracı "ÇAP aracı" gibi gösteriyordu — oysa normal ders
     seçimi için de kullanılabilir olması gerekiyor. */
  const sec = $("#tierSection");
  if (sec) sec.hidden = !gruplar.length;
  if (!gruplar.length){ wrap.innerHTML = ""; return; }
  /* ★ Her programın KENDİ sahnesi. Tek sahnede birleştirseydik iki ayrı
     programın zincirleri birbirine bağlıymış gibi görünürdü. */
  wrap.innerHTML = gruplar.map((g, i) => `
    <section class="tiergroup" data-g="${i}">
      ${gruplar.length > 1 ? `<h3><span class="tag ${g.role === "ANADAL" ? "ANADAL" : "CAP"}"
        >${esc(g.label || g.role)}</span> ${esc(g.program || "")}</h3>` : ""}
      <div class="tiers"><div class="tierstage" id="tierStage${i}">
        <svg class="tierlinks" id="tierLinks${i}" aria-hidden="true"></svg>
      </div></div>
      <div class="tierfoot" id="tierFoot${i}"></div>
    </section>`).join("");
  gruplar.forEach((g, i) => renderTierGroup(g, i));
  requestAnimationFrame(drawTierLinks);
}

function renderTierGroup(grup, i){
  const stage = $("#tierStage" + i);
  const cols = grup.tiers.map(t => `
    <div class="tier">
      <h3>Kademe ${t.tier} · ${t.courses.reduce((a,c)=>a+c.credits,0)} kredi</h3>
      <ul>${t.courses.map(c => `<li data-s="${c.status}" data-c="${esc(c.course)}"
            title="${esc(c.name || c.course)}">
        <span class="top"><span class="mono">${esc(c.course)}</span>
        <span class="mono" style="color:var(--ink-3)">${c.credits}</span></span>
        ${(c.needs && c.needs.length)
            ? `<span class="dep">⟵ ${c.needs.map(esc).join(", ")}</span>` : ""}
        ${(c.outside && c.outside.length)
            ? `<span class="dep out">dışarıdan: ${c.outside.map(esc).join(", ")}</span>` : ""}
      </li>`).join("")}</ul>
    </div>`).join("");
  stage.innerHTML = `<svg class="tierlinks" id="tierLinks${i}" aria-hidden="true"></svg>` + cols;

  stage.querySelectorAll(".tier li").forEach(li => li.addEventListener("click", () => {
    const code = li.dataset.c;
    tierFocus = (tierFocus === code) ? null : code;
    paintTierFocus();
  }));

  const bagli = grup.tiers.reduce((a,t) =>
    a + t.courses.filter(c => (c.needs||[]).length).length, 0);
  const disari = new Set();
  grup.tiers.forEach(t => t.courses.forEach(c => (c.outside||[]).forEach(x => disari.add(x))));
  $("#tierFoot" + i).innerHTML =
    `${bagli} ders plan içinden bir önşarta bağlı` +
    (disari.size ? ` · ${disari.size} önşart plan DIŞINDAN geliyor (anadalda almış olabilirsin)` : "") +
    ` · kademe 0 = hemen alınabilir.`;
}

function drawTierLinks(){
  (DATA.tierGroups || []).forEach((g, i) => drawTierGroupLinks(g, i));
  paintTierFocus();
}

function drawTierGroupLinks(grup, i){
  const stage = $("#tierStage" + i), svg = $("#tierLinks" + i);
  if (!stage || !svg) return;
  const box = stage.getBoundingClientRect();
  const at = {};
  stage.querySelectorAll(".tier li").forEach(li => {
    const r = li.getBoundingClientRect();
    at[li.dataset.c] = {x: r.left - box.left + r.width / 2,
                        t: r.top - box.top, b: r.bottom - box.top};
  });
  svg.setAttribute("width", stage.scrollWidth);
  svg.setAttribute("height", stage.scrollHeight);
  const paths = [];
  (grup.tiers || []).forEach(t => t.courses.forEach(c => (c.needs||[]).forEach(dep => {
    const a = at[dep], b = at[c.course];
    if (!a || !b) return;                       /* ders çizilmemişse çizgi de yok */
    /* Kademeler artık AŞAĞI doğru: çizgi önşartın ALTINDAN çıkıp dersin
       ÜSTÜNE giriyor. Yatay bezier bıraksaydık çizgiler kutuların üstünden
       geçer, bağı göstermek yerine karartırdı. */
    const d = Math.max(14, (b.t - a.b) / 2);
    paths.push(`<path d="M ${a.x} ${a.b} C ${a.x} ${a.b+d}, ${b.x} ${b.t-d}, ${b.x} ${b.t}"
                      data-a="${esc(dep)}" data-b="${esc(c.course)}"></path>`);
  })));
  svg.innerHTML = paths.join("");
}

function paintTierFocus(){
  (DATA.tierGroups || []).forEach((g, i) => {
    const stage = $("#tierStage" + i);
    if (!stage) return;
    /* Zincir GRUBUN KENDİ grafından: iki program arasında önşart bağı yok,
       birinde seçilen ders öbürünü söndürmemeli ama aydınlatmamalı da. */
    const kendinde = (g.tiers || []).some(t =>
      t.courses.some(c => c.course === tierFocus));
    const chain = (tierFocus && kendinde) ? tierChain(g.tiers, tierFocus) : null;
    stage.classList.toggle("focus", !!chain);
    stage.querySelectorAll(".tier li").forEach(li => {
      li.classList.toggle("on", !!chain && chain.has(li.dataset.c));
      li.classList.toggle("root", li.dataset.c === tierFocus);
    });
    stage.querySelectorAll(".tierlinks path").forEach(p => p.classList.toggle(
      "on", !!chain && chain.has(p.dataset.a) && chain.has(p.dataset.b)));
  });
}

addEventListener("resize", () => requestAnimationFrame(drawTierLinks));

/* ★ Tek giriş noktası. Sunucudan yeni durum gelince (program/dönem/transkript
   değişti) sayfa yenilenmeden buradan yeniden çiziliyor. */
function boot(){
  setupBar();
  renderHeader();
  renderGpa();
  renderLoad();
  renderFloor();
  renderCredits();
  renderSuggestions();
  renderChanges();
  wireRefresh();
  wirePicks();
  renderBlockers();
  renderHero();
  renderSonraki();
  renderBasvuru();
  renderTiers();
  useMode(0);
  renderSaved();      // useMode'dan SONRA: MODES aday havuzu kurulmuş olmalı
  renderSecNav();     // en sona: hangi bölümlerin açık olduğu ancak burada belli
  // ★ Paylaşılan bağlantı (#crn=…) EN SON: kaydedilen programı da eziyor,
  // çünkü kullanıcı o bağlantıya bilerek tıkladı.
  baglantidanYukle();
}
boot();
</script>
</body>
</html>
"""
