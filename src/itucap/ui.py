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

import html as _html
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
# ★★ Faz 38 — not dağılımı yalnız OKUNUYOR. İlk yazımda bu satır
# `from .sources import obs_notdagilimi` idi ve YAYINLANAN SİTE AÇILMADI:
# `site_kur.py` tarayıcıya `sources/` kopyalamıyor (scraper bağımlılıkları).
# Okuma tarafı `notlar.py`de ve `ENGINE` listesinde.
from . import notlar as ND


def _dil_esi(code: str) -> list[str]:
    """Dersin dil eşi dahil kod kümesi: 'MAT 210' -> ['MAT 210','MAT 210E'].

    ★ OBS denklik sayfası kodları TABAN (E'siz) yazıyor ("MAT 210"), plan ise
    E'li ("MAT 210E"). Eşleşmezsek denklik sessizce görünmez. Körlemesine E
    ekliyoruz AMA türetilen kodu asla OLUMLAMIYORUZ — yalnız arama anahtarı:
    kullanılması için gerçekten gereken'de olması ya da şubesi olması gerekiyor.
    (normalize.merge_language_variants'taki uyarı: kör son-harf atma yanlış
    programa yönlendirir — burada CHECK'e bağladığımız için güvenli.)
    """
    code = (code or "").strip()
    if not code:
        return []
    alt = code[:-1] if code.endswith("E") else code + "E"
    return [code, alt] if alt != code else [code]


def _acik_denklikler(con, equivalences, expanded, gereken, allowed,
                     names, section_json) -> list[dict]:
    """Almam gereken bir dersin DENKLİĞİ bu dönem açıksa, onu bilgileriyle
    listeler (kullanıcı isteği 27.08.2026; resmi OBS denklikleri 28.08.2026).

    Denklik yönü: `kaynak → hedef`. Kaynağı alınca hedef sağlanmış sayılıyor.
    Yani planında gereken 'hedef' yerine, bu dönem AÇIK olan 'kaynak' dersi
    (çoğu zaman başka bölümden — dilekçeyle) alabilirsin. Örnek: BLG 202E
    gerekiyor, resmi denkliği MAT 202 bu dönem açık — MAT 202'yi al, sayılır.

    İki kaynak, iki dil:
      · **Resmi** (OBS DersPlanDenklikleri): hedefe göre GRUPLANIR, kaynaklar
        birbirinin ALTERNATİFİ (`mode="or"`, herhangi biri yeter). Yalnız hedef
        gerçekten gereken bir plan dersiyse gösterilir (yoksa gürültü).
      · **Beyan** (user_declared): kullanıcının kendi bildirdiği; her zaman
        gösterilir. Çok kaynaklıysa AND (`mode="and"`, hepsi gerekli).

    Dil eşi: OBS "MAT 202" ↔ katalog "MAT 202E" (bkz. `_dil_esi`). Hedefi
    gereken'e, kaynağı şubelere eşle; iki varyant da açıksa şubeleri birleştir.
    """
    def passed(code):
        return any(R.passed(expanded.get(s)) for s in _dil_esi(code))

    def name_of(code):
        for s in _dil_esi(code):
            if names.get(s):
                return names[s]
        return names.get(code, "")

    def kaynak_json(code, min_not):
        secs, crn = [], set()
        for s in _dil_esi(code):                    # iki dil varyantının şubeleri
            for sec in REC.load_sections(con, s, allowed):
                if sec.crn not in crn:
                    crn.add(sec.crn); secs.append(sec)
        return {"code": code, "name": name_of(code), "minGrade": min_not,
                "passed": passed(code), "open": bool(secs),
                "sections": [section_json(s) for s in secs]}

    def gereken_kodu(target):
        return next((s for s in _dil_esi(target) if s in gereken), None)

    # Resmi denklikleri hedef-tabanına göre grupla (OR alternatifleri birleşsin).
    resmi: dict[str, dict] = {}
    beyanlar: list = []
    for e in equivalences:
        if passed(e.target):
            continue
        if e.confidence == "user_declared":
            beyanlar.append(e)
            continue
        hk = gereken_kodu(e.target)
        if hk is None:                              # resmi ama gereken değil
            continue
        base = hk[:-1] if hk.endswith("E") else hk
        g = resmi.setdefault(base, {"target": hk, "sources": {}, "conf": "official",
                                    "note": e.note or ""})
        for code, min_not in e.sources:
            g["sources"].setdefault(code, min_not)
        if e.confidence == "requires_approval":
            g["conf"] = "requires_approval"

    out: list[dict] = []
    for g in resmi.values():                        # --- resmi: OR alternatif ---
        kaynaklar = [kaynak_json(code, mn) for code, mn in g["sources"].items()]
        if not any(k["open"] and not k["passed"] for k in kaynaklar):
            continue
        kaynaklar.sort(key=lambda k: (not (k["open"] and not k["passed"]), k["code"]))
        out.append({
            "target": g["target"], "targetName": name_of(g["target"]),
            "needed": True, "declared": False, "confidence": g["conf"],
            "note": g["note"], "mode": "or", "sources": kaynaklar,
            "allReady": True,                       # OR: bir açık kaynak yeter
        })

    gorulen: set = set()
    for e in beyanlar:                              # --- beyan: AND (çok kaynak) ---
        kaynaklar = [kaynak_json(code, mn) for code, mn in e.sources]
        if not any(k["open"] and not k["passed"] for k in kaynaklar):
            continue
        base = e.target[:-1] if e.target.endswith("E") else e.target
        anahtar = (frozenset(k["code"] for k in kaynaklar), base)
        if anahtar in gorulen:
            continue
        gorulen.add(anahtar)
        out.append({
            "target": e.target, "targetName": name_of(e.target),
            "needed": gereken_kodu(e.target) is not None, "declared": True,
            "confidence": e.confidence, "note": e.note or "",
            "mode": "and" if len(kaynaklar) > 1 else "one", "sources": kaynaklar,
            "allReady": all(k["open"] or k["passed"] for k in kaynaklar),
        })
    out.sort(key=lambda x: (not x["needed"], x["target"]))
    return out


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


def _kilit_satirlari(declared) -> list[dict]:
    """Ayardaki `kilitli` satırlarını OLDUĞU GİBİ çözer — bozukları da.

    Her satır: `{"satir", "course", "deger", "tur"}`; `tur` ∈ `"sube"` (CRN,
    Faz 45) · `"aralik"` (`SS:DD-SS:DD`, Faz 53) · `"bozuk"`.

    ★ Aynı derse iki satır varsa (elle yazılmış) motor SONUNCUSUNU uyguluyor
    (sözlük); öncekiler `"golge"` olarak işaretleniyor ki arayüz "bu satır
    uygulanmıyor" diyebilsin.
    """
    out: list[dict] = []
    for raw in declared or ():
        satir = str(raw).strip()
        if not satir:
            continue
        ders, _, deger = satir.partition("@")
        ders, deger = ders.strip().upper(), deger.strip()
        tur = REC.kilit_bicimi(deger) if ders else "bozuk"
        if tur == "aralik":
            deger = REC.aralik_yazi(*REC.kilit_araligi(deger))
        out.append({"satir": satir, "course": ders, "deger": deger, "tur": tur})
    son = {s["course"]: i for i, s in enumerate(out) if s["tur"] != "bozuk"}
    for i, s in enumerate(out):
        if s["tur"] != "bozuk" and son[s["course"]] != i:
            s["tur"] = "golge"
    return out


def _kilit_ayikla(declared) -> dict[str, str]:
    """`["GEO 315E@13601", "BLG 351E@00:00-12:30"]` →
    `{"GEO 315E": "13601", "BLG 351E": "00:00-12:30"}` — motorun gördüğü.

    Biçimi bozuk satır motora GİRMİYOR ama sessizce de düşmüyor:
    `_kilit_bilgisi` onu arayüze "okunamadı" diye taşıyor. ⚠️ Faz 53'e kadar
    bu docstring aynı şeyi söylüyordu ama `_kilit_bilgisi` yalnız BU
    sözlüğü okuyordu — bozuk satır hiçbir yerde görünmüyordu.
    """
    return {s["course"]: s["deger"] for s in _kilit_satirlari(declared)
            if s["tur"] in ("sube", "aralik")}


def _kilit_bilgisi(declared, havuz: dict) -> list[dict]:
    """Kilitleri arayüze taşır — ve her birinin GERÇEKTEN TUTUP tutmadığını.

    `havuz`: `{DERS: {CRN: [{"day":…,"start":…,"end":…}, …]}}` — aday havuzu.

    ★★ `ok=False` olan kilit, dönem değişip CRN kaybolduğunda (ya da ders
    havuzdan çıktığında) çıkıyor. O satırı listeden düşürmek en kolayı
    olurdu ama kullanıcı "dersim kilitliydi, saati neden kaydı?" diye
    sorardı. Kilit duruyor, yanında neden tutmadığı yazıyor.

    ★ Faz 53 — aralık kilidinde `ok`, dersin o aralığa BÜTÜNÜYLE uyan en az
    bir şubesi olması; `uyan` o şubelerin listesi (arayüz sayısını yazıyor).
    """
    out = []
    for s in _kilit_satirlari(declared):
        ders, deger, tur = s["course"], s["deger"], s["tur"]
        kayit = {"course": ders, "satir": s["satir"], "tur": tur, "crn": "",
                 "aralik": "", "ok": False, "neden": "", "meetings": [],
                 "uyan": []}
        if tur in ("bozuk", "golge"):
            # Motor bu satırı UYGULAMIYOR — arayüz bunu söylemek zorunda.
            kayit["neden"] = "bicim" if tur == "bozuk" else "golge"
            out.append(kayit)
            continue
        subeler = havuz.get(ders) or {}
        if tur == "aralik":
            lo, hi = REC.kilit_araligi(deger)
            uyan = sorted(crn for crn, ms in subeler.items()
                          if ms and all(lo <= m["start"] and m["end"] <= hi
                                        for m in ms))
            kayit.update(aralik=deger, lo=lo, hi=hi, uyan=uyan, ok=bool(uyan),
                         # Ders havuzda ama aralığa uyan şubesi yok → ayrı cümle.
                         neden="" if uyan else ("aralik" if subeler else "ders"))
        else:
            kayit.update(crn=deger, ok=deger in subeler,
                         meetings=subeler.get(deger) or [],
                         # Ders havuzda ama CRN yok → "şube kapandı"; ders de
                         # yok → "bu ders artık aday değil". İkisi farklı cümle.
                         neden=("" if deger in subeler
                                else ("sube" if subeler else "ders")))
        out.append(kayit)
    return sorted(out, key=lambda x: (x["course"], x["tur"] == "golge"))


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
    equivalences = R.load_equivalences(con, ucon=ucon)
    if seconds is None:
        seconds = second_programs(settings, cap_id, yandal_id)
    # ★★ PLANSIZ İKİNCİ PROGRAM SESSİZCE SİLİNİYORDU.
    # `resolve_seconds` planı bulunamayan türü BİLEREK listede bırakıyor
    # ("yandalım var ama araç göstermiyor" ile "yandal planı çekilmemiş"
    # ayrı şeyler). Burası bir satır sonra o ayrımı çöpe atıyordu: ekranda
    # yandal HİÇ görünmüyor, kullanıcı seçimi kaydolmamış sanıyordu.
    # Aynı soruya iki kaynağın farklı cevap vermesi — bu projedeki ikinci
    # klasik hata sınıfı.
    #
    # Plan gerektiren her yer (paneller, ilerleme, taban) filtrelenmiş
    # listeyi kullanmaya devam ediyor; `plansiz` yalnızca GÖSTERİLİYOR.
    plansiz = [s for s in seconds if not s.get("planId")]
    seconds = [s for s in seconds if s.get("planId")]
    # Tekil değerler eski davranış için: İLK ikinci program.
    second_role = (seconds[0]["role"] if seconds else "") or "CAP"
    second_label = (seconds[0]["label"] if seconds else "") or "ÇAP"
    # ★ Yarıyıl tabanı ve ÇAP mezuniyet ortalaması YALNIZ ÇAP'a ait
    # (Yönerge Madde 18 / MADDE 17). Yandal planını ÇAP kurallarıyla
    # değerlendirmek, uygulanmayan bir kuralda "kaldın" demek olurdu.
    cap_plan_id = next((s["planId"] for s in seconds if s["kind"] == "cap"), None)

    # ★ "Açık denkliği olan gereken dersler" için: bütün planların DOLMAMIŞ
    # slot dersleri (kullanıcı isteği 27.08.2026). `_open_slot_courses`
    # havuz seçeneklerini de kapsıyor ve sağlanmış slotu atlıyor.
    from .discover import _open_slot_courses as _dolmamis
    gereken_dersler: set[str] = set()

    panels = []
    for plan_id, role in ((anadal_id, "ANADAL"),
                          *((s["planId"], s["role"]) for s in seconds)):
        if plan_id is None:
            continue
        plan = con.execute("SELECT * FROM plan WHERE id=?", (plan_id,)).fetchone()
        if plan is None:
            continue                     # plan silinmiş/çekilmemiş -> panelsiz devam
        gereken_dersler |= _dolmamis(con, plan_id, grades, equivalences)
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
        # ★★ Faz 45 — `locked` motora SERT kısıt olarak giriyor: kilitli
        # dersin yalnız o şubesi deneniyor, program onun etrafında kuruluyor.
        return cs, REC.build_schedules(cs, max_load=limit, limit=n_schedules,
                                       fixed=busy, floors=floors, prefs=prefs,
                                       locked=locked)

    # ★ Faz 27 — yumuşak tercihler. SIRALAMAYA giriyor, eleme YAPMIYOR.
    prefs = settings.preferences()
    busy = REC.busy_sections(settings.mesgul)
    # ★★ Faz 45 — saate kilit. `build()` bunu okuyor (kapanış değişkeni).
    locked = _kilit_ayikla(settings.kilitli)
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
                # ★ Motorun kendi puanı ile tercih farkı AYRI taşınıyor:
                # "puan 22.5" tek başına, tercihin ne kadar etkilediğini
                # gizliyordu. Arayüz ikisini de yazıyor.
                "baseScore": sched.base_score,
                "prefDelta": sched.pref_delta,
                "prefReasons": sched.pref_reasons(),
                # ★ Faz 37 (fikirler §3.5): tercih karşılanamıyorsa NEYİ
                # bırakınca karşılanacağını da söyle — tek adımlık öneri.
                "prefRelief": sched.pref_relief(),
                "campusChanges": sched.campus_changes(),
                # Yan yana karşılaştırma için (Faz 27): programın "şekli".
                "shape": _program_sekli(sched),
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

    # ★ Faz 38 — not dağılımı. Aday başına tek sorgu yerine tek seferde
    # okuyup önbelleğe alıyoruz; `candidates_json` iki kez çağrılıyor.
    _nd_cache: dict[str, dict | None] = {}

    def _not_dagilimi(code: str):
        if code not in _nd_cache:
            try:
                _nd_cache[code] = ND.distribution(con, code, settings.term)
            except Exception:                     # noqa: BLE001
                # Dağılım bir SÜS; okunamazsa aracın geri kalanı çalışmalı.
                _nd_cache[code] = None
        d = _nd_cache[code]
        if not d:
            return None
        # ★ Faz 38b — BÜTÜN dönemler taşınıyor, yalnız seçili olan değil:
        # arayüzde dönem değiştirmek yeni bir istek gerektirmesin. Ders
        # başına 1-3 dönem × 9 kova; sayfa boyutuna etkisi ihmal edilebilir.
        return {
            "codes": d["codes"],
            "selected": d["selected"]["term"],
            "wantedSeason": d["wantedSeason"],
            # ⚠️ Üç değerli (True/False/None) — "istenen yarıyıl bilinmiyor"
            # ile "uyuşmuyor" ayrı şeyler.
            "seasonMismatch": d["seasonMismatch"],
            "terms": [{
                "term": t["term"], "termName": t["termName"],
                "yearName": t["yearName"], "season": t["season"],
                "counts": t["counts"],
                "buckets": ND.bucketise(t["counts"]),
                **t["summary"],
            } for t in d["terms"]],
        }

    def candidates_json(pool):
        return [{
            "course": c.course, "name": c.name, "altName": _diger_dil(c.course),
            "role": c.role, "ects": c.ects,
            "credits": c.credits, "slotId": c.slot_id, "planId": c.plan_id,
            "termNo": c.term_no, "pool": c.pool_label,
            "score": c.score, "unlocks": c.unlocks, "critical": c.critical,
            "prereqUnknown": c.prereq_unknown, "prereqMissing": c.prereq_missing,
            # ★ Puanın kırılımı — "neden bu ders önde" sorusunun cevabı.
            "parts": c.parts,
            # `unlocks` katalogdaki toplam, `opens` SENİN planındaki liste.
            # İkisi ayrı sayı; birini öbürünün yerine yazmak yanlış olurdu.
            "opens": _acilanlar(c.course),
            "required": c.required, "reasons": c.reasons,
            # ★ Faz 38 — geçmiş dönemlerin not dağılımı (OBS yayınlıyor).
            # ⚠️ PUANA GİRMİYOR. Dağılımı puanlamaya sokmak aracı "kolay ders
            # bulucu"ya çevirirdi; hangi dersi almanın değdiği öğrencinin
            # değer yargısı, motorun değil.
            "grades": _not_dagilimi(c.course),
            "sections": [section_json(s) for s in c.sections],
        } for c in pool]

    schedule_json = schedules_json(schedules, cands)

    # ★ Darboğaz HER ikinci program için ayrı hesaplanıyor ve hangisine ait
    # olduğu satırda yazıyor — iki programın engellerini tek listede
    # ayrımsız göstermek "hangi program yüzünden takıldım" sorusunu
    # cevapsız bırakırdı.
    # ★★ İnceleme C6 — "bu dersi neden alamıyorum" sorusu ANADAL için de
    # cevaplanıyor artık. Darboğaz yalnız ikinci program için hesaplanıyordu
    # ("İkinci programda neden alamıyorsun"); tek programlı öğrenci — yani
    # aracın kullanıcılarının çoğu — bu cevabı HİÇ görmüyordu.
    blockers = []
    if anadal_id:
        blockers += [{"course": b.course, "reason": b.reason, "detail": b.detail,
                      "name": names.get(b.course, ""),
                      "role": "ANADAL", "label": "anadal",
                      "program": settings.anadal_program}
                     for b in REC.cap_blockers(con, ucon, student_id, anadal_id,
                                               settings.anadal_program,
                                               settings.allowed_programs,
                                               max_term=donem or None)]
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

    # ★★ FAZ 37 — katalogda ders ders ilan edilmiş kredi tabanı.
    #
    # Beyan edilmiş kural (yukarıdaki `rules`) katalogda tabanı olan 498
    # dersin yalnız 173'ünü tanıyordu. Kalan 325'i motorun kör noktasındaydı.
    # Artık motor onları da eliyor — ve eleme GÖRÜNÜR olmak zorunda: burada
    # yalnız SENİN planlarındaki, henüz geçmediğin ve tabanı tutmayan
    # dersler listeleniyor. (Katalogda tabanı olup tabanı zaten dolduran
    # dersi yazmak gürültü olurdu: onlar zaten alınabiliyor.)
    #
    # ⚠️ TRANSKRİPT YOKKEN LİSTELEMİYORUZ (Faz 24/26'nın dersi). 0 kredi bir
    # ÖLÇÜM değil, veri yokluğu; "bu 12 dersi tutmuyorsun" demek daha
    # girilmemiş bir transkript üzerinden iddia üretmek olurdu. Kuralın
    # varlığı yine söyleniyor — sessiz kalmak da doğru olmazdı.
    catalog_rule = POL.load_catalog_rule()
    catalog_blocked = []
    if catalog_rule.enabled and grades:
        # ⚠️ `pools=True` şart: katalog tabanı taşıyan derslerin çoğu SEÇMELİ
        # HAVUZDA (CEV/BIO/ELK seçmelileri). Havuzları dışarıda bırakmak,
        # elenen dersin sebebini tam da en çok elenen yerde gizlerdi.
        for code in sorted(R.plan_codes(con, anadal_id,
                                        *(s["planId"] for s in seconds),
                                        pools=True)):
            row = con.execute(
                "SELECT name, class_restriction FROM course WHERE code=?",
                (code,)).fetchone()
            if row is None or R.passed(grades.get(code)):
                continue
            floor = POL.parse_catalog_floor(row["class_restriction"])
            if floor is None or have_credits + 1e-9 >= floor:
                continue
            # Beyan edilmiş kural zaten aynı dersi (aynı ya da daha katı
            # eşikle) tutuyorsa iki kez yazma — kullanıcı için tek engel.
            covered = any(r.matches(code, row["name"] or "")
                          and r.min_credits + 1e-9 >= floor for r in rules)
            if covered:
                continue
            catalog_blocked.append({
                "course": code, "name": row["name"] or "", "min": floor,
                "missing": round(max(0.0, floor - have_credits), 1),
            })

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
        "catalog": {
            "enabled": catalog_rule.enabled,
            "verified": catalog_rule.verified,
            "source": catalog_rule.source,
            "blocked": catalog_blocked,
            # Transkript yokken liste ÜRETİLMEDİ — "hiç engel yok" ile
            # "henüz bakamıyoruz" farklı şeyler.
            "noTranscript": not grades,
        },
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
        # ★ C3 — bina kodu ("TMB") tek başına bir yer değil. Tam ad ipucunda.
        "buildings": _bina_adlari(con),
        # ★ Aday ders sıfırsa GERÇEK sebep (inceleme A5). Boş dize = ölçülen
        # bir sebep yok; arayüz o zaman genel mesajı yazıyor.
        "emptyReason": (_bos_havuz_sebebi(con, anadal_id, settings.allowed_programs)
                        if not cands else ""),
        # Beyan edilen anadal planı bulunamadıysa (inceleme A4).
        "planWarning": _plan_uyarisi(con, settings),
        # ★ Faz 25/D1 — bozuk ayar dosyası. Sessizce varsayılana düşmek,
        # kullanıcıya başka bir bölümün raporunu doğru sandırırdı.
        "settingsError": settings.load_error,
        # ★ Faz 53 — okunan tabloların dışında kalan ayar satırları.
        "settingsWarnings": settings.load_uyarilari,
        "term": settings.term,
        # ★ B3 — başlıkta ham `202610` yazıyordu. Çözülemezse BOŞ; arayüz
        # o zaman ham kodu yazmaya devam ediyor, isim UYDURMUYOR.
        "termLabel": config.donem_adi(settings.term),
        # ★★ Faz 38 — planladığın dönemin notları AÇIKLANMIŞ mı?
        # Takvimden tahmin etmiyoruz, kaynağa soruyoruz: o dönem için
        # kaç dersin dağılımı yayınlanmış. Sıfırdan büyükse dönem geçmişte
        # kalmış demektir ve `settings.term` büyük ihtimalle yanlış.
        # ⚠️ 0 "gelecekte" DEMEK DEĞİL — hiç çekilmemiş de olabilir; arayüz
        # bu ikisini `gradeCoverage.courses` ile ayırıyor.
        "termGraded": ND.term_already_graded(con, settings.term),
        "gradeCoverage": ND.coverage(con),
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
        # ★ Seçili ama PLANI BULUNAMAYAN ikinci programlar. Bunlar için
        # ilerleme/taban hesaplanamıyor ama SEÇİM DURUYOR — arayüz
        # "yandalın yok" değil "yandalın var, planı katalogda yok" diyor.
        "secondsMissing": plansiz,
        "donem": donem,
        "donemSource": term_source,
        "credits": credit_info,
        "gpa": gpa_info,
        "load": load_info,
        "secondFloor": floor_info,
        # Ders konulamayacak saatler — ızgarada gösteriliyor ve motor
        # bunlarla çakışan şubeyi hiç önermiyor.
        "busy": _busy_info(settings.mesgul),
        # ★★ Faz 45 — SAATE KİLİTLİ dersler. Motor bunları sert kısıt olarak
        # uyguluyor; buradaki liste arayüzün kilit rozetini basması ve bir
        # kilidin tutmadığını SÖYLEYEBİLMESİ için.
        "locked": _kilit_bilgisi(
            settings.kilitli,
            {c.course: {s.crn: [{"day": m.day, "start": m.start, "end": m.end}
                                for m in s.meetings]
                        for s in c.sections}
             for c in [*cands, *term_cands]}),
        "taking": sorted(S.in_progress(ucon, student_id)),
        "panels": panels,
        "candidates": candidates_json(cands),
        "schedules": schedule_json,
        # ★ Dönemlik + alttan kipi: ayrı aday havuzu, ayrı programlar.
        # Sıra ÖNEMLİ — ilk kip açılışta gösterilen kip.
        "modes": _modes(
            # ★ "Tüm adaylar" → "DEPAR" (kullanıcı isteği 27.08.2026): aracın
            # adıyla aynı, plandaki tüm açık dersleri değerlendiren tam kip.
            {"key": "all", "label": AD_KISA,
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
        # ★ Almam gereken bir dersin DENKLİĞİ bu dönem açıksa (kullanıcı
        # isteği 27.08.2026). Aday listesinden ayrı: burada gösterilen ders
        # planımda olmayabilir ama denklikle bir gereksinimi karşılıyor.
        "openEquivalents": _acik_denklikler(
            con, equivalences,
            R.expand_with_equivalences(grades, equivalences)[0],
            gereken_dersler, settings.allowed_programs, names, section_json),
        # Her ikinci programın KENDİ kademe zinciri.
        "tierGroups": tier_groups,
        "lessonCount": con.execute("SELECT COUNT(*) FROM lesson").fetchone()[0],
        "uncertain": S.uncertain_grades(ucon, student_id),
    }


# ============================================================ ARACIN ADI
# ★ Kullanıcı kararı 27.08.2026. Kısaltma UYDURMA DEĞİL, açılımın kendisi:
#
#       DErs Planlama ARacı  →  DEPAR
#
# "Depar" gerçek bir Türkçe kelime (ani hızlanma) ve kayıt haftasının işi
# tam olarak o: plan önceden kurulur, kayıt anı depar olur.
#
# ⚠️ Ad TEK YERDE. Sekme başlığı, sayfa başlığı ve README ayrı ayrı yazılsaydı
# biri değişip öbürü kalırdı — bu projede aynı soruya iki kaynağın farklı
# cevap vermesi tekrar eden hata sınıfı.
AD_KISA = "DEPAR"
AD_KURUM = "İTÜ"
AD_TAM = f"{AD_KURUM} {AD_KISA}"
AD_ACILIM = "Ders Planlama Aracı"

# ⚠️ Takvim dosyası (ICS) PRODID alanı ASCII olmak zorunda; "İTÜ" oraya
# olduğu gibi yazılamaz. Katlama TEK YERDE, yoksa ad değişince biri kalırdı.
_ASCII = str.maketrans({"İ": "I", "ı": "i", "Ü": "U", "ü": "u", "Ö": "O",
                        "ö": "o", "Ş": "S", "ş": "s", "Ğ": "G", "ğ": "g",
                        "Ç": "C", "ç": "c"})


def ad_ascii() -> str:
    """`İTÜ DEPAR — Ders Planlama Aracı` → ASCII karşılığı."""
    return f"{AD_TAM} {AD_ACILIM}".translate(_ASCII)


def _tr_upper(s: str) -> str:
    """Türkçe'ye saygılı büyük harf: i→İ, ı→I."""
    return s.replace("i", "İ").replace("ı", "I").upper()


def acilim_html(acilim: str | None = None, kisaltma: str | None = None) -> str:
    """Açılımı, kısaltmayı OLUŞTURDUĞU harfler vurgulu olarak döndürür.

    `Ders Planlama Aracı` + `DEPAR` → `<b>DE</b>rs <b>P</b>lanlama <b>AR</b>acı`

    ★ Elle boyamak yerine TÜRETİYORUZ: ikisi ayrışamaz. Ad değişirse ya
    doğru vurgu çıkar ya da hiç çıkmaz — yanlış vurgu çıkamaz.

    ⚠️ Kısaltma açılımdan çıkmıyorsa `ValueError`. Sessizce vurgusuz metin
    döndürmek, "kısaltma açılımdan geliyor" iddiasını ekranda yalanlamadan
    ölü bırakırdı; ad değiştiren kişi bunu fark etmeli.
    """
    # ⚠️ Sabitler VARSAYILAN DEĞER OLARAK yazılmıyor: Python varsayılanları
    # işlev tanımlanırken bir kez hesaplar, yani `AD_ACILIM`'in o anki
    # KOPYASI donar. Sabit sonradan değişse imza eski değeri kullanmaya
    # devam ederdi — aynı soruya iki kaynak, bu projedeki klasik hata.
    # (Testte yakalandı: adı değiştirip sayfayı çizince eski açılım çıktı.)
    acilim = AD_ACILIM if acilim is None else acilim
    kisaltma = AD_KISA if kisaltma is None else kisaltma
    kalan = list(_tr_upper(kisaltma))
    parcalar: list[str] = []
    for i, kelime in enumerate(acilim.split(" ")):
        if i:
            parcalar.append(" ")
        # Bu kelimenin başından kaç harf kısaltmaya gidiyor?
        n = 0
        while n < len(kelime) and kalan and _tr_upper(kelime[n]) == kalan[0]:
            kalan.pop(0)
            n += 1
        kacir = _html.escape
        parcalar.append(f"<b>{kacir(kelime[:n])}</b>" + kacir(kelime[n:]) if n
                        else kacir(kelime))
    if kalan:
        raise ValueError(
            f"kısaltma açılımdan çıkmıyor: {kisaltma!r} ⊄ {acilim!r} "
            f"(artan harfler: {''.join(kalan)})")
    return "".join(parcalar)


# ★ Örnek ayar dosyasındaki yer tutucular. Bunlar SEÇİM değil; kurulumu
# tamamlanmış saymak, hiç seçim yapmamış kullanıcıya "tamam" demek olurdu.
YER_TUTUCU_KOD = {"XXX", "YYY", "ZZZ", "KOD", "-"}


def _gercek_program(kod: str | None) -> bool:
    temiz = (kod or "").strip().upper()
    return bool(temiz) and temiz not in YER_TUTUCU_KOD


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
         # ⚠️ YER TUTUCU "yapıldı" sayılmıyor (inceleme B2): örnek ayar
         # dosyası `anadal_program = "XXX"` yazıyor ve kart bunu ✓ TAMAM diye
         # gösteriyordu — kurulum bitmiş sanılıyordu.
         "done": _gercek_program(settings.anadal_program), "action": "program"},
        # ★★ FAZ 47 — DÖNEM, TRANSKRİPTTEN ÖNCE (kullanıcı 18.09.2026:
        # *"ilk önce dönem seçtir; 1. dönem olan birisinin geçtiği ders
        # yoktur veya 5. dönem olan birisi geçtiği dersleri işaretlemek
        # için otomatik tik attırabilir"*).
        #
        # Sıra keyfî değil, BAĞIMLILIK: dönem biliniyorsa "Plandan işaretle"
        # penceresi 1..N-1. dönemin zorunlularını ÖNERİ olarak tikleyebiliyor
        # ve iş bir dakikadan on saniyeye iniyor. Tersi sırada o öneri
        # yapılamıyor, çünkü hangi döneme kadar tikleneceği bilinmiyor.
        {"key": "donem", "label": "Bulunduğun dönemi söyle",
         "cta": "Dönemi seç",
         "detail": "Kaçıncı dönemdesin? Tek tıklama.",
         "why": "Hem \u201cN. dönem + alttan\u201d önerisi buna göre kuruluyor, "
                "hem de bir sonraki adımda geçmiş dönemlerin zorunlu dersleri "
                "senin için işaretleniyor.",
         "sure": "5 saniye", "required": False,
         "done": bool(settings.donem), "action": "donem"},
        {"key": "transkript", "label": "Geçtiğin dersleri gir",
         "cta": "Dersleri gir",
         "detail": ("Dönemini söylediysen geçmiş dönemlerin zorunluları hazır "
                    "işaretli gelir — sen yalnız düzeltirsin."
                    if settings.donem else
                    "En kolayı: transkriptini olduğu gibi yapıştır. İstersen "
                    "plandan tikle."),
         "why": "Neyin kaldığını, önşartların tuttuğunu ve kredi tavanını "
                "bundan çıkarıyor.",
         "sure": "1 dakika", "required": False,
         "done": bool(S.grades(ucon, student_id)), "action": "plan"},
        # ⚠️ TERCİHLER BURAYA EKLENMEDİ — ve bu bilinçli. Denendi: dördüncü
        # bir "kurulum adımı" yapılınca karşılama kartı HİÇ kaybolmuyor,
        # çünkü tercih çoğu kullanıcıda hep boş kalıyor. Faz 26'nın tam da
        # kaldırdığı "ekranın arkasında duvar var" hissi geri geliyordu
        # (üç test bunu yakaladı). Tercihler kurulum değil, İNCE AYAR:
        # kurulum bitince çıkan "şimdi ne yapabilirsin" şeridinde duruyor.
    ]
    eksik = [a for a in adimlar if not a["done"]]
    if not eksik:
        return None
    return {
        # ★ Program yoksa rapor GÖSTERİLMİYOR; sonraki adımlar eksikse rapor
        # duruyor ama üstte ne yapılacağı yazıyor. İkisi farklı: birinde
        # gösterilecek doğru bir şey yok, öbüründe var ama eksik.
        "blocking": not _gercek_program(settings.anadal_program),
        "steps": adimlar,
        # ⚠️ BÖLÜM sayısı, plan sayısı değil. `plan` tablosunda her bölümün
        # birden çok sürümü var (445 satır / 127 bölüm); satırı saymak
        # "445 bölüm seçebilirsin" gibi okunuyordu — seçim kutusunda 127 var.
        "planCount": con.execute(
            "SELECT COUNT(DISTINCT program_code) FROM plan "
            "WHERE plan_type='lisans'").fetchone()[0],
        "lessonCount": con.execute("SELECT COUNT(*) FROM lesson").fetchone()[0],
    }


def _plan_uyarisi(con, settings) -> str:
    """Beyan edilen anadal planı katalogda yoksa (inceleme A4)."""
    try:
        from .plans import plan_uyarisi
        return plan_uyarisi(con, settings)
    except Exception:                                          # noqa: BLE001
        return ""


def _bos_havuz_sebebi(con, anadal_id, allowed) -> str:
    """Aday ders SIFIRSA gerçek sebebi bul (ilk kullanıcı incelemesi A5).

    ★★ Eskiden tek bir cümle vardı: *"ders programı henüz yayınlanmamış
    olabilir (make refresh)"*. Ölçülen gerçek sebep bambaşkaydı:
    `program_codes` örnek dosyadaki yer tutucuda (`XXX`, `YYY`) kalmıştı ve
    hiçbir şube o kodlara açık olmadığı için HER ŞEY eleniyordu. Kullanıcı
    `make refresh` çalıştırıp saatini harcıyor, sonuç değişmiyordu.

    ⚠️ Sebep UYDURULMUYOR: hangi durumu ölçtüysek onu söylüyoruz, ölçemediysek
    "sebep bulunamadı" diyoruz.
    """
    try:
        toplam_sube = con.execute("SELECT COUNT(*) FROM lesson").fetchone()[0]
    except sqlite3.Error:
        return ""
    if not toplam_sube:
        return ("Katalogda hiç açık şube yok — ders programı henüz "
                "yayınlanmamış olabilir (make refresh).")
    if not anadal_id:
        return "Anadal planın bulunamadı — bölümünü seçtiğinden emin ol."
    kodlar = {str(c).upper() for c in (allowed or []) if str(c).strip()}
    if not kodlar:
        return ""
    # Bu program kodlarına açık KAÇ şube var?
    isaret = ",".join("?" * len(kodlar))
    acik = con.execute(
        f"""SELECT COUNT(DISTINCT crn) FROM lesson_allowed_program
             WHERE upper(program_code) IN ({isaret})""", sorted(kodlar)).fetchone()[0]
    if acik:
        return ""
    return (f"{toplam_sube} şubenin HİÇBİRİ şu program kodlarına açık değil: "
            + ", ".join(sorted(kodlar))
            + ". Program penceresindeki “Gelişmiş → Kayıt yapabildiğin program "
              "kodları” alanını BOŞALT — o zaman seçtiğin bölümlerden türetilir.")


def _program_sekli(sched) -> dict:
    """Bir programın karşılaştırılabilir "şekli" (Faz 27).

    "Öneri 1 / 2 / 3" arasında geçiş vardı ama farkı görmek için ızgarayı
    iki kez ezberlemek gerekiyordu. Karşılaştırma ekranının ihtiyacı olan
    şey ders listesi değil, ŞEKİL: hangi günler dolu, en erken saat, kaç
    boş gün, kaç çevrimiçi.
    """
    gunler: dict[int, list[tuple[int, int]]] = {}
    online = 0
    for p in sched.picks:
        if p.section.online:
            online += 1
        for m in p.section.meetings:
            gunler.setdefault(m.day, []).append((m.start, m.end))
    # ⚠️ Saati ilan edilmemiş ders hiçbir güne düşmüyor; "boş gün" sayısı
    # onu boşluk sanmasın diye ayrıca raporlanıyor.
    saatsiz = sum(1 for p in sched.picks if not p.section.meetings)
    ilk = min((s for gun in gunler.values() for s, _ in gun), default=None)
    son = max((e for gun in gunler.values() for _, e in gun), default=None)
    return {
        "days": sorted(gunler),
        "freeDays": [g for g in range(1, 6) if g not in gunler],
        "earliest": ilk, "latest": son,
        "online": online, "timeless": saatsiz,
        # Günlük "boşluk" (ders arası bekleme) toplamı — dakika.
        "gaps": sum(
            max(0, b - a)
            for gun in gunler.values()
            for (_, a), (b, _) in zip(sorted(gun), sorted(gun)[1:])),
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


# OBS'nin "yer bildirilmedi" için kullandığı değerler.
_BINA_YOK = {"", "-", "--", "undeclared", "tba", "tbd"}


def _building(code: str | None) -> str:
    """İlan edilmemiş yer BOŞ döner — "belirsiz" DEĞİL (inceleme C3).

    ★ Eski hâli `undeclared`'ı "belirsiz" diye yazıyordu ve ızgarada bina
    kodunun durduğu yerde duruyordu: okuyan kişi bunu bir BİNA ADI sanıyordu.
    Ölçüldü: 3630 buluşmanın 1542'si (%42) böyle — yani ızgaranın neredeyse
    yarısı uydurma bir yer adı taşıyordu.

    ⚠️ `_hoca` ile aynı ilke: bilinmeyen bilinmeyen kalıyor. Arayüz boş
    gelen yerde "yer bildirilmemiş" yazıyor, bina kodu yazmıyor.
    """
    temiz = (code or "").strip()
    return "" if temiz.lower() in _BINA_YOK else temiz


def _bina_adlari(con: sqlite3.Connection) -> dict:
    """`{'TMB': 'Temel Bilimler Binası', …}` — kod tek başına bir yer değil."""
    try:
        return {r[0]: r[1] for r in con.execute(
            "SELECT code, name FROM building WHERE name IS NOT NULL AND name<>''")
            if r[0] and r[1] and r[1].strip().upper() != r[0].strip().upper()}
    except sqlite3.Error:
        return {}


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


def _gomulu_json(data: dict) -> str:
    """JSON'u `<script>` içine GÜVENLE gömer (penetrasyon testi 27.08.2026).

    ★★ AÇIK — DOĞRULANMIŞ, TARAYICIDA ÇALIŞAN XSS. `json.dumps` `</script>`
    dizisini kaçırmıyor: `/` olduğu gibi kalıyor. Sayfa DATA'yı doğrudan
    `<script>const DATA = …;</script>` içine gömdüğü için, kullanıcının
    yazdığı serbest metin (meşgul saat etiketi, denklik notu) `</script>`
    taşırsa tarayıcı script'i ERKEN KAPATIYOR ve kalanı HTML olarak
    işliyor. Kanıt: `mesgul` etiketine `</script><script>…</script>` konup
    sayfa açıldığında enjekte script gerçekten çalıştı ve `document.domain`
    okudu.

    Tehdit yüzeyi bugün dar (yerelde çoğunlukla kişi kendine; paylaşım
    bağlantısı yalnız rakam kabul ediyor) ama:
      · `settings.toml` paylaşılabilir/içe aktarılabilir bir dosya,
      · yarın serbest metin taşıyan bir içe aktarma eklense anında sömürülür,
      · ve gömülü JSON'dan script kaçışı, tek başına kapatılması gereken bir
        kusur — "şu an ulaşılmıyor" bir savunma değil.

    Kaçış: `<`, `>`, `&`, U+2028, U+2029 → `\\uXXXX`. Bu karakterler JSON'da
    YALNIZ string değerlerinin İÇİNDE geçebilir (yapısal sözdiziminde asla),
    o yüzden `\\u` kaçışı çözümlenen değeri DEĞİŞTİRMİYOR — `JSON.parse`
    aynı nesneyi veriyor. Standart ve kayıpsız.
    """
    ham = json.dumps(data, ensure_ascii=False)
    return (ham.replace("<", "\\u003c").replace(">", "\\u003e")
            .replace("&", "\\u0026")
            .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))


def render(data: dict, *, deferred: bool = False,
           fontlar_sonda: bool = False) -> str:
    """Tek dosyalık arayüz.

    `deferred=True` → veriyi SONRA yükleyen bir kabuk üretir. Statik site
    (GitHub Pages) için: sayfa açılır, Pyodide yüklenir, motor tarayıcıda
    çalışır, sonuç `window.__ITUCAP_APPLY__(data)` ile içeri verilir.

    `fontlar_sonda=True` → gömülü yazı tipleri `<head>` yerine sayfanın
    SONUNA konuyor. ★★ Faz 52 ölçümü: statik sitede yükleme ekranından ÖNCE
    571 KB iniyordu ve bunun **486 KB'ı yazı tipiydi**; ~200 KB/s'lik bir
    bağlantıda ziyaretçi **3 saniye bembeyaz** sayfaya bakıyordu. Yazı
    tipleri sona alınınca yükleyiciden önce yalnız ~86 KB kalıyor. Bedeli:
    yükleyici ilk anda sistem yazı tipiyle çiziliyor (`font-display:swap`),
    yazı tipi gelince değişiyor. Uygulamanın kendisi saniyeler sonra
    çizildiği için onu hiç etkilemiyor.
    ⚠️ Yalnız statik site için: `make app` ve `make ui` yerelden açılıyor,
    orada bekleme yok ve sıra değişmiyor.

    ★ Şablon kopyalanmıyor — aynı CSS ve aynı JS. İki sürüm çıkarsaydı
    tasarım düzeltmesi birinde yapılır, öbüründe unutulurdu.
    """
    html = _TEMPLATE.replace("__DATA__", _gomulu_json(data))
    if fontlar_sonda:
        html = html.replace(
            "__FONTLAR__", "/* yazı tipleri sayfanın sonunda (Faz 52) */")
        # ⚠️ SON `</body>`: şablonun ortasında (bir JS dizgesinde, bir
        # yorumda) aynı dizge geçerse ilkini değiştirmek yazı tiplerini
        # oraya gömerdi. Bugün tek tane var; yarın olmayabilir.
        bas, _, son = html.rpartition("</body>")
        html = (bas + f'<style id="gomuluFontlar">\n{_font_yuzleri()}\n</style>\n'
                + "</body>" + son)
    else:
        html = html.replace("__FONTLAR__", _font_yuzleri())
    # ★ Ad TEK KAYNAKTAN. Şablona üç ayrı yere elle yazılsaydı biri değişip
    # öbürü kalırdı; `acilim_html` de vurguyu kısaltmadan türetiyor.
    for anahtar, deger in (("__AD_TAM__", AD_TAM), ("__AD_KURUM__", AD_KURUM),
                           ("__AD_KISA__", AD_KISA),
                           ("__AD_ACILIM_DUZ__", AD_ACILIM),
                           ("__AD_ASCII__", ad_ascii()),
                           ("__AD_ACILIM__", acilim_html())):
        html = html.replace(anahtar, deger)
    if deferred:
        html = html.replace("\nboot();\n", "\nwindow.__ITUCAP_APPLY__ = applyState;\n")
    return html


# ★★ FAZ 43 — YAZI TİPLERİ ARTIK GOOGLE'DAN GELMİYOR.
#
# Ölçüm (17.09.2026, tarayıcıda): sayfa her açılışta `fonts.googleapis.com`a
# **1 istek** atıyordu. Oysa README şunu söylüyor: *"Pyodide bile CDN'den değil
# siteden geliyor — açılışta üçüncü bir tarafa haber verilmiyor."* İki cümle
# aynı anda doğru olamaz: Google Fonts isteği ziyaretçinin IP'sini ve
# tarayıcı imzasını üçüncü bir tarafa veriyordu. Pyodide için verilen karar
# neyse (pakete al), yazı tipi için de o.
#
# Dosyalar `src/itucap/fonts/` altında, SIL OFL 1.1 ile (lisans metinleri
# yanlarında). Chivo dosyaları Latin + Latin Genişletilmiş-A (Türkçe) alt
# kümesi; IBM Plex dosyaları IBM'in dağıttığı hâliyle **değiştirilmedi** —
# "Plex" OFL'de ayrılmış bir yazı tipi adı, alt kümeye indirmek onu
# "Modified Version" yapardı.
#
# ⚠️ NEDEN GÖMÜLÜ (base64), ayrı dosya değil: aracın üç çıktısı var —
# `make app` (sunucu), `make ui` (çift tıklanan TEK dosya), `make site`.
# Ayrı dosya `make ui`'yi bozardı; sunucuya da statik dosya yolu eklemek
# gerekirdi. Tek mekanizma, üç çıktıda aynı davranış. Bedeli ölçüldü:
# 355 KB woff2 → 473 KB base64. Sitenin toplam yükünün yanında (Pyodide ~10
# MB) küçük.
#
# ⚠️ Dosyalar İMPORT ANINDA değil, RENDER SIRASINDA okunuyor. `ui` modülü
# Pyodide paketine giriyor (`site_kur.ENGINE`) ama `fonts/` girmiyor —
# import anında okusaydık site açılmazdı (Faz 38'de `sources/` yüzünden tam
# olarak bu oldu). Dosya yoksa sistem yazı tipine düşüyor; Google'a
# DÜŞMÜYOR. Gerçekten gömüldüğünü test kontrol ediyor.
_FONT_YUZLERI = (
    # (dosya, aile, ağırlık)
    ("Chivo-SemiBold.woff2", "Chivo", 600),
    ("Chivo-Bold.woff2", "Chivo", 700),
    ("Chivo-ExtraBold.woff2", "Chivo", 800),
    ("Chivo-Black.woff2", "Chivo", 900),
    ("IBMPlexSans-Regular.woff2", "IBM Plex Sans", 400),
    ("IBMPlexSans-SemiBold.woff2", "IBM Plex Sans", 600),
    ("IBMPlexSans-Bold.woff2", "IBM Plex Sans", 700),
    ("IBMPlexMono-Regular.woff2", "IBM Plex Mono", 400),
    ("IBMPlexMono-SemiBold.woff2", "IBM Plex Mono", 600),
)


def font_dizini() -> Path:
    return Path(__file__).resolve().parent / "fonts"


def _font_yuzleri() -> str:
    """Gömülü `@font-face` blokları. Dosya yoksa BOŞ döner (sistem yazı tipi)."""
    import base64

    kok = font_dizini()
    parcalar = []
    for dosya, aile, agirlik in _FONT_YUZLERI:
        yol = kok / dosya
        try:
            ham = yol.read_bytes()
        except OSError:
            continue
        b64 = base64.b64encode(ham).decode("ascii")
        parcalar.append(
            f"@font-face{{font-family:\"{aile}\";font-style:normal;"
            f"font-weight:{agirlik};font-display:swap;"
            f"src:url(data:font/woff2;base64,{b64}) format(\"woff2\")}}")
    if not parcalar:
        return ("/* ⚠️ Yazı tipi dosyaları bulunamadı — sistem yazı tipine\n"
                "   düşülüyor. Google Fonts'a DÜŞÜLMÜYOR (gizlilik). */")
    return "\n".join(parcalar)


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
<title>__AD_TAM__ — __AD_ACILIM_DUZ__</title>
<!-- ★ Kayıtlı tema BOYAMADAN ÖNCE uygulanıyor: yoksa sayfa önce sistem
     temasında çizilip sonra kullanıcının seçtiğine atlıyordu (yükleme
     ekranında bile). try/catch — localStorage bazı bağlamlarda kapalı. -->
<script>try{var t=localStorage.getItem("itucap.tema");if(t==="dark"||t==="light")document.documentElement.setAttribute("data-theme",t);}catch(e){}</script>
<style>
__FONTLAR__
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
  /* ★★ FAZ 43 — ÖLÇÜLEN AA HATASI (tasarım sistemi, 17.09.2026).
     `--ink-3` gece zemininde 4.03:1'di (taban 4.5), yüzeyde 3.40:1.
     `--border-strong` 2.13:1'di (denetim kenarı tabanı 3.0). İkisi de
     ikincil METİN ve KENAR taşıyor, yani az görünen değil çok görünen
     yerler: meta, ipucu, CRN, tablo çizgisi. Yeni değerler ölçüldü:
     5.59 / 4.72 ve 3.69. (`tools/kontrast_olcumu.py`) */
  --border:#262E3A; --border-strong:#647085;
  --ink:#E4E9F2; --ink-2:#9AA5B8; --ink-3:#848EA1;
  --seal:#8FA3E8; --seal-soft:#1A2036;
  /* Faz 43 — tasarım sisteminden: birincil düğmenin üzerine gelme rengi
     (opaklık DEĞİL, ayrı bir renk) ve pencere perdesi. */
  --seal-hover:#9EB3F9; --scrim:rgba(8,16,26,.5);
  --anadal:#5FC0A6; --anadal-soft:#123029; --anadal-ink:#8FD8C3;
  --cap:#D9A05B; --cap-soft:#2E2415; --cap-ink:#EFC48E;
  /* ★ Yandal AYRI renk: ÇAP ve yandal aynı anda olabiliyor, aynı renkte
     olsalardı panelde ve ızgarada hangisi olduğu anlaşılmazdı. */
  --yandal:#7FB2C9; --yandal-soft:#16252C; --yandal-ink:#A9D2E4;
  --danger:#E0836F; --warn:#D9B061;
  /* ★ Faz 38b — uyarı kutusunun zemini/mürekkebi. Eskiden iki yerde
     `var(--warn-bg,#fdf3e3)` diye YEDEKLİ yazılıyordu: jeton tanımsız
     olduğu için gece şemasında da açık zemin çıkıyordu. */
  --warn-soft:#2B2415; --warn-ink:#E8C88A;
  --shadow:0 18px 44px -20px rgba(0,0,0,.85);
  --r:0px;
}
:root:not([data-theme="dark"]){
  @media (prefers-color-scheme:light){
    --ground:#FFFFFF; --surface:#FFFFFF; --surface-2:#F0F2F6;
    --border:#D4D9E2; --border-strong:#141821;
    --ink:#0D1017; --ink-2:#4B5462; --ink-3:#5F6878;
    --seal:#3B4E9E; --seal-soft:#E7EAF7;
    --seal-hover:#2F3F8E; --scrim:rgba(8,16,26,.5);
    --anadal:#0A6B58; --anadal-soft:#D6EBE5; --anadal-ink:#074A3D;
    --cap:#8A5210; --cap-soft:#F6E7D2; --cap-ink:#633B08;
    --yandal:#1F5C77; --yandal-soft:#DCECF4; --yandal-ink:#154457;
    --danger:#C02D18; --warn:#7A5709;
    --warn-soft:#FCF1DB; --warn-ink:#6B4A05;
    --shadow:0 18px 44px -26px rgba(10,15,30,.5);
  }
}
:root[data-theme="light"]{
  --ground:#FFFFFF; --surface:#FFFFFF; --surface-2:#F0F2F6;
  --border:#D4D9E2; --border-strong:#141821;
  --ink:#0D1017; --ink-2:#4B5462; --ink-3:#5F6878;
  --seal:#3B4E9E; --seal-soft:#E7EAF7;
  --seal-hover:#2F3F8E; --scrim:rgba(8,16,26,.5);
  --anadal:#0A6B58; --anadal-soft:#D6EBE5; --anadal-ink:#074A3D;
  --cap:#8A5210; --cap-soft:#F6E7D2; --cap-ink:#633B08;
  /* ⚠️ Faz 38b'de fark edildi: bu blokta `--yandal*` YOKTU, yani açık şema
     AÇIKÇA seçilince yandal renkleri gece paletinden geliyordu (medya
     sorgulu blokta vardı, burada unutulmuş). */
  --yandal:#1F5C77; --yandal-soft:#DCECF4; --yandal-ink:#154457;
  --danger:#C02D18; --warn:#7A5709;
  --warn-soft:#FCF1DB; --warn-ink:#6B4A05;
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
/* Çerçeve genişliği: BÜTÜN SEKMELERDE AYNI (Faz 52 — aşağıdaki nota bak). */
.wrap{max-width:1720px;margin:0 auto;padding:32px 24px 80px;display:flex;
  flex-direction:column;gap:30px}
/* ★★ FAZ 47 — HAFTALIK PROGRAM GÖRÜNÜMÜ GENİŞ (kullanıcı 18.09.2026:
   *"yanlardaki boşlukları kaldırabilirsin, ders programını çok
   sıkıştırıyor"*).

   Ölçüldü: ızgara HER ekran genişliğinde 660px kalıyordu — 1920px'te iki
   yanda 290'ar piksel, 2560px'te 610'ar piksel boş duruyordu. Gün sütunu
   120px'e sıkışıyor ve ders adı kesiliyordu.

   ⚠️ Tasarım sistemi "sayfa en fazla 1340px" diyor ve bu METİN için doğru:
   uzun satır okunmaz. O yüzden genişleme YALNIZ ızgara görünümünde — metin
   ağırlıklı bölümler (kademeler, aday tablosu, mevzuat) 1340'ta kalıyor.

   ★★ FAZ 52 — BU KARAR KULLANICI İSTEĞİYLE GERİ ALINDI (21.09.2026:
   *"bütün sekmelerde arayüzün genişliği aynı olsun"*). Ölçüldü:
     · 1920px ekranda program 1720px, öbür sekmeler 1340px — sekme değişince
       sol ray **196px zıplıyor**, çerçeve 380px daralıyordu (1440px'te 56px);
     · üstelik 1340px çerçeve okuma ölçüsünü zaten KORUMUYORDU: düz yazı
       satırları o genişlikte bile **~153 karaktere** çıkıyordu.
   Yani kilit yanlış yerdeydi. Çerçeve artık her sekmede aynı (1720px), okuma
   ölçüsü ise METNİN KENDİSİNDE (aşağıda `max-width:80ch`). Hem zıplama
   kalktı hem uzun satırlar bugünkünden KISA. */
/* Okuma ölçüsü: düz yazı ~80 karakterde kırılsın (çerçeve ne kadar geniş
   olursa olsun). Tablolar, ızgara ve kartlar çerçevenin tamamını kullanıyor. */
main .summary,main .modenote,main p,main .hint{max-width:80ch}
/* Chivo, ağır ve büyük harf — Şematik'in sesi. Gövde IBM Plex Sans'ta kalıyor;
   Chivo'yu uzun metinde kullanmak gece zemininde yorucu olurdu. */
h1,h2,h3{margin:0;text-wrap:balance;
  font-family:"Chivo",Helvetica,Arial,sans-serif;font-weight:800;
  text-transform:uppercase}
h1{font-size:29px;letter-spacing:-.02em;line-height:1.1;font-weight:900}
/* ★ FAZ 43 — TAKLİT KALIN (synthetic bold) YOK.
   Ölçüm (tarayıcıda, 17.09.2026): sayfa üç ağırlığı İSTİYOR ama hiçbiri
   yüklü değildi — 36 ders kodu `IBM Plex Mono 700`, 7 `<b>`
   `IBM Plex Sans 900`, aracın alt başlığı `Chivo 500`. Yüklü olmayan
   ağırlığı tarayıcı İNCE YÜZÜ ŞİŞİREREK taklit ediyor; gerçek yüzden
   daha bulanık ve daha geniş çıkıyor. 12.5px ders kodunda göze çarpıyor.
   ⚠️ Çare ağırlık EKLEMEK değil (her ağırlık ~60 KB): istenen ağırlığı
   gömülü olanlara indirmek. `<b>` varsayılanı `bolder`, kalın bir
   bağlamda 900'e tırmanıyordu — 700'e sabitleniyor. */
b,strong{font-weight:700}
b.mono,.mono b,.mono strong{font-weight:600}
/* ---------- aracın adı: DErs Planlama ARacı → DEPAR ----------
   ★ Kısaltmanın nereden geldiği GÖSTERİLİYOR, açıklanmıyor. Vurgulu
   harfler `ui.acilim_html()` ile açılımdan türetiliyor.

   ⚠️ Büyük harf CSS'te, metinde DEĞİL: ekranda "DErs Planlama ARacı"
   okunuyor ama kopyalanınca ve ekran okuyucuda "Ders Planlama Aracı"
   kalıyor — vurgu bir sunum tercihi, metnin kendisi değil. */
h1 .kurum{color:var(--ink-3);font-weight:700}
.acilim{margin-top:5px;font-family:"Chivo",Helvetica,Arial,sans-serif;
  font-size:11.5px;letter-spacing:.13em;color:var(--ink-3);font-weight:600;
  text-transform:uppercase}
.acilim b{color:var(--seal);font-weight:900;letter-spacing:.1em}
h2{font-size:15px;letter-spacing:.02em;font-weight:800}
.eyebrow{font-size:10.5px;font-weight:700;letter-spacing:.16em;text-transform:uppercase;
  color:var(--seal);font-family:"Chivo",Helvetica,Arial,sans-serif}
/* Belge başlığı: kalın yapısal cetvel + ince alt cetvel. */
header{padding-bottom:16px;border-bottom:1px solid var(--border)}
header .masthead{display:flex;flex-wrap:wrap;align-items:flex-end;
  justify-content:space-between;gap:16px;
  padding-bottom:14px;border-bottom:3px solid var(--seal);margin-bottom:4px}
header .sub{color:var(--ink-2);font-size:13.5px;margin-top:6px}
/* ★★ FAZ 46 — ÜST ÇUBUK. Ölçüm: başlık 174px ve 45 kelimeydi; ızgaranın
   önündeki en büyük tek blok. Kurulum BİTMİŞSE ad küçülüp durum satırıyla
   aynı hizaya geçiyor (54px). Kurulum sürerken tam masthead kalıyor:
   orada ekranda gösterilecek başka bir şey yok ve aracın kendini tanıtması
   gereken tek an o. */
body:not(.kurulum) header{display:flex;align-items:center;gap:8px 16px;
  flex-wrap:wrap;padding-bottom:10px;border-bottom:3px solid var(--seal)}
body:not(.kurulum) header .masthead{display:contents}
body:not(.kurulum) header .masthead>div{display:flex;align-items:baseline;
  gap:10px;flex-wrap:wrap;min-width:0}
/* ★ Faz 47 — kullanıcı: "itü depar yazısı biraz daha büyük olabilir".
   Faz 46'da 29 → 20px inmişti; 25px üst çubuğu büyütmeden okunuyor. */
body:not(.kurulum) header h1{font-size:25px;letter-spacing:-.015em;order:1}
/* Tek satırda ad ÖNCE okunmalı; eyebrow (program listesi) onu izler. */
body:not(.kurulum) header .eyebrow{order:2}
body:not(.kurulum) header .acilim{display:none}
body:not(.kurulum) header .sub{margin:0;font-size:12.5px}
body:not(.kurulum) header #theme{margin-left:auto;order:9}
/* ⚠️ "tazele" düğmesi CÜMLENİN İÇİNDE duruyordu; 390px'te satır düğmenin
   ortasından kırılıyor, hem okuma hem tıklama bozuluyordu (ölçüldü).
   Satır artık esnek: metin bir parça, düğme ayrı bir parça. */
.veriyasi{display:flex;flex-wrap:wrap;align-items:center;gap:4px 8px}
/* ★★ FAZ 46 — haftalık programın düzeni: ızgara solda, bağlam sağda. */
/* ★★ FAZ 47 — sağ sütun 330 → 240px ve düğmeler ALT ALTA (kullanıcı
   isteği: *"genişliğini azaltıp yukardan aşağıya tuşları listeleyip"*).
   Kazanılan 90px doğrudan ızgaraya gidiyor. */
.prgduzen{display:grid;grid-template-columns:minmax(0,1fr) 240px;gap:18px;
  align-items:start;margin-top:12px}
.prgyan .toolbar{flex-direction:column;align-items:stretch;gap:6px}
.prgyan .toolbar .ghost{width:100%;justify-content:center}
.prgyan .chip{align-self:flex-start}
.prgorta{min-width:0}
.prgyan{display:flex;flex-direction:column;gap:12px;min-width:0}
.prgyan .toolbar{margin:0}
/* ⚠️ Dar ekranda sütun ızgaranın ALTINA düşüyor, üstüne değil: üstüne
   düşseydi Faz 46'nın çözdüğü sorun (313 kelime ızgaranın önünde) telefonda
   aynen geri gelirdi. */
@media (max-width:1100px){
  .prgduzen{grid-template-columns:minmax(0,1fr)}
  .prgyan{order:2}
  .prgorta{order:1}
}
/* ★ FAZ 48 — Katlanan başlık da bir HEDEF: 24px tabanı (WCAG 2.2 AA 2.5.8).
   Ölçüldü (pencere taraması): dokuz pencerenin altısında `<summary>`
   19–21px yüksekliğindeydi — puan kırılımı, "Gelişmiş", yedek listeleri.
   İpucu ve arz başlıkları zaten 24'tü, onlara dokunmuyor.
   ⚠️ Taban kuralda `display:flex` YOK, bilerek: (a) iki metin düğümü
   arasındaki boşluğu yutuyor ("11 dersbu dönem" — arz başlığındaki nota
   bak), (b) `list-item` kutusu kalkınca yerleşik açılma üçgeni siliniyor
   ve o başlıkların TEK açılma işareti o. Dikey dolgu ikisine de
   dokunmadan tabanı sağlıyor. */
summary{padding-block:2px;min-height:24px}
/* İpuçları katlanıyor — silinmiyor (Faz 40'ın dersi). */
.ipucu>summary{cursor:pointer;font-size:12.5px;color:var(--ink-2);
  min-height:24px;display:flex;align-items:center;list-style:none}
.ipucu>summary::-webkit-details-marker{display:none}
.ipucu>summary::before{content:"▸";margin-right:6px;color:var(--ink-3)}
.ipucu[open]>summary::before{content:"▾"}
.ipucu>summary:hover{color:var(--seal)}
.ipucu .hint{display:block;margin-top:6px}
/* Arz uyarısı katlanmış — SAYISI kapalıyken de görünüyor. */
.arzdetay>summary{cursor:pointer;min-height:24px;display:flex;align-items:center;
  list-style:none;color:var(--warn-ink)}
.arzdetay>summary::-webkit-details-marker{display:none}
.arzdetay>summary::before{content:"▸";margin-right:6px;opacity:.8}
.arzdetay[open]>summary::before{content:"▾"}
.arzgovde{margin-top:6px}
/* Yatay kaydırılabilir tablo: kenar solması "devamı var" diyor. */
.listwrap{overflow-x:auto;scrollbar-width:thin}
.listwrap[data-more="right"]{mask-image:linear-gradient(90deg,#000 calc(100% - 28px),transparent)}
.listwrap[data-more="left"]{mask-image:linear-gradient(90deg,transparent,#000 28px)}
.listwrap[data-more="both"]{mask-image:linear-gradient(90deg,transparent,#000 28px,#000 calc(100% - 28px),transparent)}
/* Kip + öneri sekmeleri TEK satır (eskiden iki bloktu, 145px). */
.prgbaslik{display:flex;flex-wrap:wrap;gap:10px 14px;align-items:center}
.prgbaslik h2{margin-right:2px}
.prgbaslik .tabs{margin-left:auto}
button{font:inherit;color:inherit;background:none;border:0;cursor:pointer}
/* ★★ FAZ 39 — DÜĞMELERDE BÜYÜK HARF KALKTI.
   Ölçüm: sayfada 162 öğe zorla BÜYÜK HARF'e çevriliyordu ve bunların en
   uzunları düğmelerdi ("NASIL BİR PROGRAM İSTEDİĞİNİ SÖYLE", "KAYIT GÜNÜ
   LİSTESİNİ AL"). Uzun büyük harf dizisi kelime siluetini yok eder; Türkçe'de
   İ/I ayrımı yüzünden daha da yavaş okunur. Sesi taşıyan şey Chivo ve ağırlık
   — onlar duruyor. ⚠️ BAŞLIKLAR, eyebrow'lar, tablo başlıkları ve rozetler
   BÜYÜK HARF kalıyor: onlar kısa ve tasarımın kimliği. */
.ghost{border:1px solid var(--border-strong);border-radius:var(--r);
  padding:7px 13px;min-height:34px;
  font-size:12.5px;background:transparent;font-weight:600;letter-spacing:.01em;
  font-family:"Chivo",Helvetica,Arial,sans-serif}
.ghost:hover{background:var(--seal-soft);border-color:var(--seal);color:var(--seal)}
/* ★ Tıklama geri bildirimi (01.09.2026): hafif "bas-hisset". Kayıt/tazele
   halkasının yanında, her düğmede basıldığı anı da belli ediyor. Hareket
   duyarlılığında kapalı. */
@media (prefers-reduced-motion:no-preference){
  .ghost:active,.tab:active,.modebtn:active,.ray a:active,.kod.ekle:active{
    transform:translateY(1px)}
}
/* Seçili OLMAYAN öneri sekmesi de tıklanabilir görünsün (eskiden hover yoktu). */
.tab:not([aria-selected="true"]):hover{background:var(--seal-soft);color:var(--seal)}
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
.panel .pctbox{text-align:right;line-height:1}
.panel .pct{font-family:"IBM Plex Mono",monospace;font-variant-numeric:tabular-nums;
  font-size:27px;font-weight:600;color:var(--accent);letter-spacing:-.03em}
/* ★ Büyük yüzde etiketsizdi — ne olduğu (tamamlanma) belirsizdi (01.09.2026). */
.panel .pctlbl{font-family:"Chivo",Helvetica,Arial,sans-serif;font-size:9px;
  font-weight:700;letter-spacing:.13em;text-transform:uppercase;color:var(--ink-3);
  margin-top:3px}
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
/* Etiketin tek parçası — kırpma (ellipsis) buradan işliyor, düğmeden değil:
   esnek kutunun öğesi kırpılır, kabın kendisi değil. */
.tabmetin{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
/* Seçili sekme: zemin --seal, yazı --ground. İkisi de temaya göre dönüyor,
   yani üç durumun (açık / koyu / sistem) hepsinde kontrast korunuyor —
   sabit #fff yazsaydık koyu temada mavi üstünde beyaz kalırdı. */
.tab[aria-selected="true"]{background:var(--seal);color:var(--ground);font-weight:800}

/* Kip anahtarı — 'tüm adaylar' (DEPAR) / 'dönemlik + alttan'.
   ★ inline-flex: kutu İÇERİĞE göre daralıyor. Eskiden `flex` (blok, tam
   genişlik) olduğu için kısa "DEPAR" düğmesinin sağında kutunun İÇİNDE ama
   hiçbir düğmenin İÇİNDE OLMAYAN ölü bir alan kalıyordu — görünürde kutunun
   parçası ama tıklanamıyor (kullanıcı raporu 28.08.2026). Artık kutu tam
   düğmeler kadar; dar ekranda taşmasın diye max-width. */
.modes{display:inline-flex;max-width:100%;gap:0;flex-wrap:wrap;
  border:1px solid var(--border-strong);
  border-radius:var(--r);overflow:hidden;background:var(--surface)}
.modebtn{padding:6px 14px;font-size:13px;color:var(--ink-2);cursor:pointer;
  border-left:1px solid var(--border)}
.modebtn:first-child{border-left:0}
.modebtn[aria-pressed="true"]{background:var(--seal-soft);color:var(--seal);font-weight:600}
.modenote{font-size:12px;color:var(--ink-3);margin-top:7px}
/* ★ FAZ 41 — BOŞ kip kutusu 2×2px SİYAH NOKTA olarak çiziliyordu.
   `.modes` çerçeveli; içi boşalınca geriye yalnız çerçeve kalıyor ve açık
   şemada `--border-strong` (#141821) neredeyse siyah. Kip düğmeleri ancak
   dönem BİLİNİYORSA iki tane oluyor (`MODES.length < 2` → innerHTML "")
   — yani bu noktayı YALNIZ yeni kullanıcı görüyordu, başlığın hemen
   altında, sebepsiz. */
.modes:empty{display:none}
/* Dönem bilinmiyor uyarısı — mühür rengiyle, arz uyarısından ayrılsın diye:
   o bir SORUN bildiriyor, bu bir EKSİK BİLGİ. İkisi birden görünebiliyor,
   o yüzden aralarında boşluk var: dipdibe gelince tek bir blok gibi
   okunuyorlardı. */
.note.donemsiz{border-left-color:var(--seal);margin-top:10px}

/* ---------- kurulum şeridi (Faz 8) ---------- */
.setupbar{display:flex;flex-wrap:wrap;gap:10px;align-items:center;
  padding:11px 14px;border:1px solid var(--border);border-left:3px solid var(--seal);
  border-radius:var(--r);background:var(--surface)}
.setupbar .who{font-size:13px;color:var(--ink-2);margin-right:auto}
.setupbar .who b{color:var(--ink);font-weight:600}
.setupbar .ro{font-size:12px;color:var(--ink-3)}
/* Faz 54 — sitede verinin yedeği: kendi satırında, çubuğun altında. */
.setupbar .verikutusu{flex-basis:100%;margin-top:8px;padding:12px 14px;
  border:1px solid var(--border);border-left:3px solid var(--seal);
  background:var(--surface);font-size:13.5px;line-height:1.55;color:var(--ink-2)}
.verikutusu b{color:var(--ink)}
.veridugmeler{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
.verikalici,.veriyedek{margin-top:8px;font-size:13px}
.veriyedek:empty{display:none}
.heroyedek{margin-top:8px}
/* Kısa bildirim — kip pencere DEĞİL: sayfayı kilitlemiyor. */
.bildirim{position:fixed;left:50%;bottom:22px;transform:translateX(-50%) translateY(12px);
  background:var(--seal);color:var(--ground);padding:9px 16px;border-radius:var(--r);
  font-size:13.5px;box-shadow:0 6px 24px rgba(0,0,0,.22);z-index:60;
  opacity:0;pointer-events:none;transition:opacity .18s,transform .18s;max-width:min(92vw,520px)}
.bildirim.acik{opacity:1;transform:translateX(-50%) translateY(0)}
@media (prefers-reduced-motion:reduce){.bildirim{transition:none}}
/* Satır içi küçük düğme — veri yaşının yanındaki "tazele". */
.ghost.mini{font-size:11.5px;padding:1px 8px;vertical-align:baseline}
/* Türetilen program kodları — okunur rozet; önerilenler tıklanabilir. */
.kodlar{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:2px 0 4px}
.kod{font-family:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,monospace;
  font-size:12px;padding:2px 9px;border-radius:var(--r);
  border:1px solid var(--border-strong);color:var(--ink-2);background:var(--surface)}
.kod.ekle{cursor:pointer;border-style:dashed;color:var(--seal)}
.kod.ekle:hover{border-style:solid;background:var(--surface-2)}
/* Seçili ama planı bulunamayan ikinci program — seçim duruyor, hesap yok. */
.setupbar .uyari{font-size:11px;padding:1px 6px;border:1px solid var(--warn);
  color:var(--warn);border-radius:var(--r);white-space:nowrap}
.ghost[disabled]{opacity:.45;cursor:not-allowed}
/* Meşgul düğme dönen halkası — "kaydediliyor" belli olsun (kullanıcı isteği
   28.08.2026). Meşgulken opaklığı düşürmüyoruz ki metin+dönme okunur kalsın. */
.ghost.mesgul{opacity:1;cursor:progress}
.spin{display:inline-block;width:13px;height:13px;vertical-align:-2px;
  margin-right:7px;border:2px solid currentColor;border-top-color:transparent;
  border-radius:50%;animation:spin .7s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
@media(prefers-reduced-motion:reduce){.spin{animation:none;border-top-color:currentColor}}
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
  cursor:pointer;white-space:nowrap;min-height:24px}
/* ★ Faz 46 — onay kutusu 13×13px'ti (tarayıcı varsayılanı). Etiketin
   tamamı zaten tıklanabilir ama kutunun KENDİSİ de tabanın üstünde
   olmalı: dokunmatikte insanlar kutuya basıyor. */
.tickbox input[type="checkbox"]{width:18px;height:18px;margin:3px;
  accent-color:var(--seal);flex:0 0 auto}
.candcount{margin-left:auto;font-size:12px;color:var(--ink-3);
  font-variant-numeric:tabular-nums}
/* Klavye ipucu — dar ekranda gizli (orada klavye yok). */
.kisayol{font-size:11px;color:var(--ink-3);white-space:nowrap}
@media (max-width:700px){.kisayol{display:none}}
/* ★ Satıra tıklayınca ekleme penceresi açılıyor ama tıklanabilir olduğu belli
   değildi (01.09.2026) — imleç + hafif vurgu ekledik. Klavye odağı (.odak)
   daha güçlü (seal-soft + çerçeve) kalıyor ki ikisi ayrışsın. */
#cands tbody tr[data-course]{cursor:pointer}
#cands tbody tr[data-course]:hover{background:var(--surface-2)}
/* Klavye odağı — fare seçimi gibi görünmeli ki nerede olduğun belli olsun. */
#cands tbody tr.odak{outline:2px solid var(--seal);outline-offset:-2px;
  background:var(--seal-soft)}
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
/* ★ Faz 48 — TABAN `.rm`in KENDİSİNDE. Faz 46'da yalnız `.trtable .rm`
   büyütülmüştü; taramada "Sayılan derslerim" bölümündeki `kaldır` düğmesi
   46×22px olarak kalmış çıktı. Aynı sınıfın üç kullanım yeri var; kural
   sınıfa yazılınca üçü de tabanın üstünde. */
.rm{min-height:24px;display:inline-flex;align-items:center}
.trtable .rm{color:var(--danger);font-size:12px;padding:2px 8px;
  border:1px solid var(--border);border-radius:0;
  /* Faz 46: 46×22px'ti — WCAG 2.2 AA tabanı 24×24. */
  min-height:24px;display:inline-flex;align-items:center}
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
  width:100%;text-align:left;padding:11px 12px;font-size:13.5px;
  color:var(--accent-ink);--tonhedef:var(--soft);--tonoran:0%;
  border-left:5px solid color-mix(in oklab, var(--accent),
    var(--tonhedef) calc(var(--tonoran) / 2));
  background:color-mix(in oklab, var(--soft), var(--tonhedef) var(--tonoran))}
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
  /* ⚠️ Izgara gizliyken saat kırpma düğmesi de gizlenmeli: telefonda
     ızgara yok, gün gün liste var — "tüm günü göster" hiçbir şey yapmaz.
     (Faz 39'da eklerken atlandı, mobil turda görüldü.) */
  .gridaralik{display:none}
  .daylist{display:grid}
  .wrap{padding:20px 14px 60px;gap:22px}
  h1{font-size:23px}
  .pad{padding:15px 14px}
  .panels{gap:12px}
  /* Dokunma hedefleri: 44px kuralı.
     ⚠️ Kural "44" diyordu ama değer 40'tı (Faz 39). Faz 50 telefon turunda
     ölçüldü: her görünümde 7–8 denetim 44'ün altında (`Tema` 34, `tazele`
     ve bütün `.ghost`lar 40). WCAG 2.2 tabanı 24 — o sağlanıyordu; bu
     deponun KENDİ telefon kuralı 44 ve tutulmuyordu. */
  .ghost,.tab{min-height:44px;display:inline-flex;align-items:center}
  /* ★ Ölçüm (Faz 39, 390px): telefonda 32 denetim 32px'in ALTINDAydı —
     `kaldır` ×4 (22px), `izle` ×11 (21px), `+N dış önşart` ×17 (19px).
     Masaüstünde sıkışık durmaları doğru (fare pikseli tutturur), parmakla
     ıskalanıyorlardı. Yalnız telefonda büyütülüyor. */
  /* ⚠️⚠️ ÖĞE ADIYLA nitelenmiş (`button.rm`), bilerek: bu kural bir medya
     sorgusunda ama `.watchmini`nin TEMEL kuralı kaynakta DAHA SONRA
     geliyor (Faz 46'da `min-height:24px` eklendi) ve aynı özgüllükte
     olduğu için onu eziyordu. Ölçüldü (Faz 50, 390px): `.watchmini`
     hesaplanan `min-height` = 24px, yani bu satır iki fazdır ÖLÜYDÜ.
     Medya sorgusu özgüllük KAZANDIRMIYOR — sık yapılan varsayım. */
  button.rm,button.watchmini{min-height:34px;padding-left:10px;
    padding-right:10px;display:inline-flex;align-items:center;
    justify-content:center}
  /* Birincil denetimler 44: kip anahtarı ve rol süzgeci (ölçüm: 33px). */
  .modebtn,#candRole button{min-height:44px;display:inline-flex;
    align-items:center;justify-content:center}
  /* ★ Faz 50 ölçümü: katlanan başlık (24px) ve onay kutusu (18px)
     telefonda tabanın altındaydı. Katlanan başlık bir DÜĞME gibi
     davranıyor — parmakla açılıyor. */
  /* ⚠️ Sınıflı kardeşleri de yazmak ŞART: `.ipucu>summary` ve
     `.arzdetay>summary` kendi 24px'ini koyuyor ve öğe seçicisinden daha
     özgül. Bu dosyadaki üçüncü "ölü kural" tuzağı (Faz 50). */
  summary,.ipucu>summary,.arzdetay>summary{min-height:32px}
  .tickbox{min-height:44px}
  /* Faz 54: arama kutusu telefonda 38px'ti — yazmaya başlamak için dokunulan ilk yer. */
  #candQ{min-height:44px}
  .tickbox input[type="checkbox"]{width:22px;height:22px}
  /* ⚠️ `span.` niteliği ŞART — `.watchmini` ile aynı hastalık: temel
     kural (satır ~2450) kaynakta daha sonra geliyor ve aynı özgüllükte
     olduğu için bunu eziyordu. Ölçüldü (Faz 50, 390px): hesaplanan
     `min-height` 24px, yani bu satır da iki fazdır ölüydü. */
  .tier li span.dispre{min-height:32px;padding:0 9px;
    display:inline-flex;align-items:center}
  .tiers{gap:8px}
  /* Aday tablosu 6 sütunla telefona sığmıyordu; kutusunun içinde yana
     kayıyordu ama asıl iş burada yapılıyor — kaydırarak kullanılmamalı.
     Plan ve AKTS sütunları düşüyor: rol zaten ders hücresindeki etikette,
     AKTS karar için kritik değil. Satıra dokununca hepsi diyalogda. */
  #cands th:nth-child(3),#cands td:nth-child(3),
  #cands th:nth-child(5),#cands td:nth-child(5){display:none}
  table.list{font-size:13px}
  table.list td{padding:11px 8px 11px 0}
  /* ★★ FAZ 50 — ADAY TABLOSU TELEFONDA KART (kullanıcı: "telefonda
     kullanılması biraz zor").
     Ölçüldü (390px): dört sütun kalsa bile ders sütununa ~160px düşüyordu;
     açıklama 25 karakterde sarıyor, TEK ders satırı **330px** oluyordu ve
     sağdaki kontenjan sütunu kutunun DIŞINA taşıp rakamı kesiyordu
     ("180" → "18"). Yani telefonda liste hem çok uzun hem eksik okunuyordu.

     Tablo tek DOM olarak kalıyor — masaüstünde hâlâ tablo, telefonda kart.
     İki ayrı çizim yazsaydık ikisi ayrışırdı (bu depoda ölçülmüş bir
     hata sınıfı). Aynı `<tr>`, başka yerleşim:
        kod + rozetler ................................ puan
        açıklama (tam genişlik)
        kredi ................................. kontenjan
     ⚠️ Sütun BAŞLIKLARI kartta yok; sayının ne olduğu `data-e` ile
     hücrenin yanına yazılıyor — başlıksız çıplak sayı bırakmıyoruz. */
  #cands,#cands tbody,#cands tr,#cands td{display:block}
  #cands thead{display:none}
  #cands tr[data-course]{display:grid;grid-template-columns:minmax(0,1fr) auto;
    gap:2px 10px;align-items:baseline;padding:12px 0;
    border-bottom:1px solid var(--border)}
  #cands tr[data-course]>td{padding:0;border:0}
  #cands td.score{grid-column:2;grid-row:1;text-align:right;font-size:15px;
    font-weight:700;color:var(--ink)}
  #cands td.score::after{content:" puan";font-size:10px;font-weight:600;
    letter-spacing:.06em;color:var(--ink-3)}
  #cands tr[data-course]>td:nth-child(2){grid-column:1;grid-row:1}
  #cands tr[data-course]>td:nth-child(4){grid-column:1;grid-row:2}
  #cands tr[data-course]>td:nth-child(4)::after{content:" " attr(data-e);
    color:var(--ink-3);font-size:11.5px}
  #cands tr[data-course]>td:nth-child(6){grid-column:2;grid-row:2;
    justify-self:end;white-space:nowrap}
  #cands .why{margin-top:2px}
  /* Kart düzeninde tablo kaydırma kutusu boş yere kaymasın. */
  #candWrap{overflow-x:visible}
}
table.grid{border-collapse:collapse;width:100%;min-width:660px;table-layout:fixed}
/* Izgara kırpma düğmesi (Faz 39) — ızgaranın hemen altında, sessiz. */
.gridaralik{margin-top:6px}
.gridaralik:empty{display:none}
table.grid th{font-size:10.5px;font-weight:700;letter-spacing:.16em;text-transform:uppercase;
  color:var(--seal);padding:0 0 8px;text-align:left;border-bottom:3px solid var(--seal);
  font-family:"Chivo",Helvetica,Arial,sans-serif}
table.grid th:first-child{width:58px}
/* ★★ FAZ 46 — YARIM SAAT SATIRI 19px → 28px.
   Ölçüm (17.09.2026): boş hücreler 235×19px'ti; WCAG 2.2 AA (2.5.8 Target
   Size, Minimum) tabanı 24×24. Yani Faz 44'te düzelttiğimiz "boş saate
   tıkla → ders ekle" özelliğinin HEDEFİ tabanın altındaydı — 38 hücrede.
   Bedeli: 19 satırlık ızgara 361px → 532px. Kazanılan: özelliğin
   tıklanabilmesi. */
table.grid td{height:28px;padding:0 2px;vertical-align:top}
table.grid tr.hr>td{border-top:1px solid var(--border-strong);opacity:1}
table.grid tr.half>td{border-top:1px dotted var(--border)}
table.grid td.hour{border:0!important;color:var(--ink-3);font-size:11.5px;padding-top:2px}
/* ⚠️ Boş hücrenin TIKLANABİLİR olduğu, üstüne gelmeden de görünmeli:
   ölçümde hücrenin hiçbir görsel işareti yoktu, yalnız hover vardı.
   İşaret sönük ve hücrenin köşesinde — ızgaranın okunmasını bozmuyor. */
table.grid td.free{cursor:pointer;position:relative}
table.grid td.free::after{content:"+";position:absolute;left:4px;top:1px;
  font-size:12px;line-height:1;color:var(--ink-3);opacity:.45}
table.grid td.free:hover{background:var(--seal-soft);
  box-shadow:inset 0 0 0 1px var(--border-strong)}
table.grid td.free:hover::after{opacity:1;color:var(--seal)}
/* ★★ FAZ 40 — DERS BAŞINA TON (kullanıcı isteği 16.09.2026).
   Eskiden bir rolün bütün dersleri BİREBİR aynı renkteydi: ızgaradaki 14
   bloğun 10'u aynı yeşil. "Salı 13:30'daki hangi dersti" sorusu ancak
   koda okunarak cevaplanıyordu.

   ⚠️ Rolün RENGİ (hue) değişmiyor — o BİLGİ taşıyor (anadal/ÇAP/yandal).
   Değişen yalnız AÇIKLIK: ders kodundan türeyen bir basamak, `--soft`u ya
   zemine (`--ground`) ya da rolün kendi rengine (`--accent`) doğru
   karıştırıyor. Yani ton rolün İÇİNDE bir basamak, rolün yerine geçen bir
   renk değil.

   ⚠️ Ton bir İPUCU, kimlik değil: 8 basamak var, hafta 14 ders taşıyabilir,
   iki ders aynı tona düşebilir. O yüzden kod HER BLOKTA yazılı ve aynı
   dersin bütün saatleri `.esder` ile ayrıca işaretlenebiliyor — renk tek
   işaret değil (renk körlüğü). */
.blk{border-radius:0;padding:4px 7px;font-size:12px;line-height:1.3;height:100%;
  cursor:pointer;color:var(--accent-ink);overflow:hidden;
  /* Varsayılan = TON YOK: hedef `--soft`, oran 0 → iki karışım da kimlik.
     Ton verilen blokta bu iki jeton satır içinde değişiyor. */
  --tonhedef:var(--soft); --tonoran:0%;
  border-left:5px solid color-mix(in oklab, var(--accent),
    var(--tonhedef) calc(var(--tonoran) / 2));
  background:color-mix(in oklab, var(--soft), var(--tonhedef) var(--tonoran))}
.blk[data-role="ANADAL"]{--accent:var(--anadal);--soft:var(--anadal-soft);--accent-ink:var(--anadal-ink)}
.blk[data-role="CAP"]{--accent:var(--cap);--soft:var(--cap-soft);--accent-ink:var(--cap-ink)}
.blk[data-role="YANDAL"]{--accent:var(--yandal);--soft:var(--yandal-soft);--accent-ink:var(--yandal-ink)}
.blk[data-role="PLAN_DISI"],.daylist .row[data-role="PLAN_DISI"]{
  --accent:var(--ink-3);--soft:var(--surface-2);--accent-ink:var(--ink-2)}
/* ★ ÇEVRİMİÇİ DERS DAHA AÇIK (kullanıcı isteği 24.08.2026).
   Kampüse gitmiyorsun: ızgarada "orada olman gereken" saatlerden görsel
   olarak ayrılması, haftanın nasıl geçeceğini bir bakışta okutuyor.

   ⚠️ Rengi tamamen SOLDURMUYORUZ: ders programın parçası, kredisi sayılıyor,
   çakışması var. Soluk bir blok "önemsiz" diye okunurdu. Dolgu açılıyor ama
   sol şerit ve yazı rengi rolün rengini koruyor — hangi programdan olduğu
   yine görünüyor. Ayrıca renk TEK işaret değil: köşede ⌂ simgesi var,
   çünkü renk körlüğünde ton farkı okunmayabilir. */
/* ⚠️ Faz 40 notu: çevrimiçi bloğun dolgusu BİLEREK yok, o yüzden ders tonu
   burada yalnız şeritte görünüyor — ve tam oranla, çünkü yarışan dolgu yok.
   Tonun zayıf kaldığı tek yer burası; aynı ders vurgusu (`.esder`) bunu
   kapatıyor. */
.blk.online{background:transparent;
  border-left-style:dashed;
  border-left-color:color-mix(in oklab, var(--accent),
    var(--tonhedef) var(--tonoran));
  box-shadow:inset 0 0 0 1px var(--border)}
.blk.online::after{content:"⌂";position:absolute;right:5px;top:3px;
  font-size:10px;opacity:.75}
.blk{position:relative}
/* Ders adı — dar hücrede kesiliyor; tam adı `title` taşıyor. */
/* ★ FAZ 40 — aynı dersin bütün saatleri. İşaret RENK DEĞİL: çerçeve.
   Tonla yarışmıyor, renk körlüğünde de okunuyor, ve `.clash`ın kırmızı
   çerçevesinin üstüne binmiyor (o `border-left` + inset gölge kullanıyor). */
.blk.esder,.daylist .row.esder{outline:2px solid var(--ink);outline-offset:-2px}
.blk.esder{z-index:1}
/* ★★ FAZ 45 — SAATE KİLİTLİ ders.
   İşaret yine RENK DEĞİL (renk programı, ton dersi söylüyor; üçüncü bir
   anlamı renge yüklemek üçünü birden okunmaz yapardı). Kilit iki şeyle
   görünüyor: sol kenar KALINLAŞIYOR ve köşeye bir asma kilit çiziliyor.
   İkisi birden, çünkü kalın kenar tek başına dar hücrede fark edilmiyor,
   simge tek başına da 12px'te kayboluyor. */
.blk.kilit{border-left-width:6px;border-left-style:solid}
.kilitim{position:absolute;right:4px;bottom:3px;line-height:0;opacity:.85;
  color:var(--accent-ink,var(--ink))}
.kilitim svg{display:block;width:10px;height:10px}
.daylist .row.kilit{border-left-width:6px;border-left-style:solid}
/* Kilit şeridi — hangi derslerin kilitli olduğu ızgaraya bakmadan okunsun. */
.note.kilit{margin-top:10px;border-left:3px solid var(--ink);padding-left:10px}
.note.kilit.tutmuyor{border-left-color:var(--danger)}
.note.kilit .kilitsatir{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}
.note.kilit .kilitsatir button{font-size:12px}
/* Faz 53 — ders penceresinde saat aralığına kilit. Basılı olan KALIN ÇERÇEVE
   ile (renk değil; zorlanmış renk kipinde de görünsün — Faz 51 dersi). */
.kilitgrup{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-top:10px}
.kilitgrupad{font-size:12.5px;color:var(--ink-2)}
.kilitaralik[aria-pressed="true"]{border:2px solid var(--ink);color:var(--ink);
  font-weight:600}
.kilitaralik:disabled{opacity:.55;cursor:not-allowed}
.kilitsay{color:var(--ink-3);font-weight:400}
.blkad{display:block;font-size:10.5px;line-height:1.25;opacity:.85;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap;margin-top:1px}
.daylist .row.online{border-left-style:dashed}
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
/* ★ `inline-block` + `nowrap` (UX 27.08.2026): rozet dar mobil ekranda
   ORTASINDAN bölünüyordu ("ÖNŞART / BİLGİSİ YOK") ve kenarlık kırık bir
   kutu çiziyordu. Rozet tek parça; sığmazsa bütün olarak alt satıra iner.
   `margin-bottom` sarınca üst üste binmesin diye. */
.chip{display:inline-block;white-space:nowrap;font-size:10.5px;font-weight:600;
  padding:3px 9px;border-radius:0;margin-bottom:3px;
  letter-spacing:.05em;text-transform:uppercase;border:1px solid currentColor}
/* ★★ FAZ 51 — `title` DOKUNMATİKTE GÖRÜNMEZ.
   Ölçüldü (390px, on bir görünüm): görünür 102 `title`ın 82'si tıklanamayan
   bir öğedeydi, yani telefonda o metne ULAŞILAMIYORDU. Bunların 24'ü
   kısa bir etiketi açıklayan GERÇEK cümleler ve üçü bu projenin temel
   dürüstlük notları:
     · "önşart bilgisi yok" → *"Katalogda önşart metni yok — 'önşartı yok'
       demek DEĞİL. OBS'den doğrula."*
     · "⚠ dönem bitmiş görünüyor" → hangi kanıta dayandığı,
     · kategori/eşik rozetleri → yönergedeki şartın kendisi.
   Fare kullanıcısı bunu üstüne gelerek okuyordu; telefondaki kişi hiç
   okuyamıyordu. Artık noktalı altı çizili ve DOKUNULABİLİR: metin kısa
   bildirim olarak çıkıyor (canlı bölgeye de düşüyor).
   ⚠️ `title` KALDIRILMADI: ekran okuyucu onu zaten açıklama olarak
   okuyor, fare kullanıcısı da üstüne gelince görüyor. Eklenen tek şey
   dokunmatikteki yol. */
.chip[title],.cat[title],.veriyasi .stale[title],.aciklamali[title]{
  text-decoration:underline dotted;text-underline-offset:3px;cursor:help}
/* Denkliği açık gereken dersler (kullanıcı isteği 27.08.2026). */
.denkrow{padding:10px 0;border-top:1px solid var(--border)}
.denkrow:first-child{border-top:0}
.denkhedef{font-size:13px;color:var(--ink-2);margin-bottom:6px;
  display:flex;flex-wrap:wrap;gap:6px;align-items:baseline}
.denkhedef .denkad{color:var(--ink-3);font-size:12px}
.denkok{color:var(--ink-3);font-size:12px}
.denkkaynak{border:1px solid var(--border);background:var(--surface);
  padding:8px 10px;margin-top:6px;cursor:pointer}
.denkkaynak:hover{background:var(--surface-2)}
.denkkaynak.bilgi{cursor:default}
.denkkaynak.bilgi:hover{background:var(--surface)}
.denkkaynak .denkad{color:var(--ink-3);font-size:12px;margin-left:6px}
.denkkaynak .denkmeta{color:var(--ink-3);font-size:11.5px;margin-top:2px}
.denknot{font-size:11.5px;color:var(--ink-3);margin-top:6px}
.chip.supply{color:var(--danger)}
.chip.prereq{color:var(--warn)}
.chip.credit{color:var(--seal)}
.chip.unknown{color:var(--ink-3)}
.chip.edited{color:var(--cap)}
.blocklist{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:6px}
.blockitem{font-size:12.5px;color:var(--ink-2);padding:7px 10px;border-radius:0;
  background:var(--surface-2);border:1px solid var(--border)}
.blockitem b{color:var(--ink);font-weight:600}
/* Kontenjan nöbeti rozeti (Faz 39). Eskiden 6 bildirimlik SATIR İÇİ stil
   olarak engelli HER dersin yanında tekrar ediyordu — 11 kez. Sınıfa
   taşındı; durumu artık `aria-pressed` söylüyor (ekran okuyucu "izle"
   düğmesinin basılı olduğunu duymuyordu). */
.watchmini{margin-left:6px;font-size:10.5px;letter-spacing:.05em;
  text-transform:uppercase;border:1px solid currentColor;padding:1px 8px;
  color:var(--ink-3);
  /* Faz 46: 38×21px'ti — WCAG 2.2 AA tabanı 24×24. */
  min-height:24px;min-width:24px;display:inline-flex;align-items:center;
  justify-content:center}
.watchmini[aria-pressed="true"]{color:var(--cap)}
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
.veriyasi .sitenot{margin-left:.6em;font-weight:400}
/* Bozuk ayar dosyası — sayfa açılıyor ama sessiz kalmıyor. */
.note.ayarhata{border-left:3px solid var(--danger);padding-left:10px;
  margin:14px 0}
/* Faz 53: dosya okunuyor ama bir satır yanlış tabloda — hata değil, uyarı. */
.note.ayarhata.yumusak{border-left-color:var(--warn)}
/* Yapıştırma önizlemesi — üç sayı ayrı okunsun. */
.ozetler{display:flex;flex-wrap:wrap;gap:8px}
.ozet{font-size:12px;padding:3px 9px;border:1px solid var(--border);
  color:var(--ink-2)}
.ozet.ok{border-color:var(--anadal);color:var(--anadal)}
.ozet.uyari{border-color:var(--warn);color:var(--warn)}
/* Satır içi uyarı yazısı (katalogda olmayan ders, planı olmayan program). */
.meta .uyari,td .uyari,.ckname .uyari{color:var(--warn)}
.ozet.kotu{border-color:var(--danger);color:var(--danger)}
/* Puan kırılımı — "neden bu puan". Eksi katkı da aynı görsel dilde. */
.puan{margin-top:10px;border-top:1px solid var(--border);padding-top:8px}
.puan>summary{cursor:pointer;font-size:12.5px;color:var(--seal)}
.puanliste{display:flex;flex-direction:column;gap:4px;margin-top:8px}
.puansatir{display:grid;grid-template-columns:1fr 90px 46px;gap:8px;
  align-items:center;font-size:12px}
.puansatir .ad{color:var(--ink-2)}
.puansatir .bar{height:7px;background:var(--surface-2);border:1px solid var(--border)}
.puansatir .bar>i{display:block;height:100%;background:var(--seal)}
.puansatir.eksi .bar>i{background:var(--warn)}
.puansatir .deger{text-align:right;color:var(--ink-2);font-variant-numeric:tabular-nums}
.puansatir.eksi .deger{color:var(--warn)}
.puantoplam{margin-top:8px;font-size:11.5px;color:var(--ink-3);line-height:1.6}
/* Faz 38 — not dağılımı sütun grafiği (kütüphane yok).
   ★ Faz 38b: varsayılan 9 KOVA. 15 ince sütun dağılımın şeklini
   kaybettiriyordu ("+ lar yüzünden kötü gözüküyor"). Etiketler artık
   yatay — 9 kova sığıyor; "artıları ayır" 15'e çıkarınca dikey oluyor. */
.ndgrafik{display:grid;grid-template-columns:repeat(9,1fr);gap:6px;
  align-items:end;height:104px;margin:10px 0 8px}
.ndgrafik.genis{grid-template-columns:repeat(15,1fr);gap:3px}
/* ★★ FAZ 50 — SÜTUN ÜÇ SATIRLIK IZGARA (eskiden esnek kutuydu).
   Ölçüldü: esnek kutuda üç öğe (sayı 10px + çubuk %100 + etiket) kabı
   TAŞIYOR, tarayıcı da hepsini büzüyordu — büzülme miktarı çubuğun boyuna
   göre değiştiği için TABANLAR kayıyordu. Üstelik "%100" çubuk kabın
   tamamı kadar isteniyor, yani ölçek de yanlıştı.
   Izgarada: 1. satır sayı, 2. satır ÇUBUK ALANI (kalan yer), 3. satır
   etiket. Birinci ve üçüncü satır bütün sütunlarda aynı yükseklikte
   olduğu için taban ortak ve yüzdeler aynı alana göre. */
.ndsut{display:grid;grid-template-rows:auto minmax(0,1fr) auto;
  justify-items:center;height:100%;gap:3px;min-width:0}
.ndsut>i{align-self:end}
.ndsut>b{font-size:10px;font-weight:600;color:var(--ink-3);line-height:1;
  font-variant-numeric:tabular-nums}
.ndsut>i{display:block;width:100%;background:var(--seal);border-radius:2px 2px 0 0}
.ndsut>i.kotu{background:var(--warn)}
/* ★★ FAZ 50 — ETİKET SATIRI SABİT YÜKSEKLİKTE (kullanıcı 18.09.2026:
   *"+lar yüzünden barların tabanları aynı seviyede olmuyor"*).
   Ölçüldü ("artıları ayır", 15 sütun): tabanlar ÜÇ AYRI seviyede, 7px
   fark. Sebep: sütun alttan hizalı (`justify-content:flex-end`) ve DİKEY
   yazılan etiket karakter sayısıyla büyüyor — "BA+" 17px, "AA" 12px. Uzun
   etiket çubuğu yukarı itiyordu. Etiket kutusu sabitlenince taban ortak. */
.ndsut>span{font-size:10px;color:var(--ink-2);line-height:1;white-space:nowrap;
  height:12px;display:flex;align-items:flex-start;justify-content:center}
.ndgrafik.genis .ndsut>b{font-size:8.5px}
/* Dar ekranda 15 etiket yan yana sığmıyor (ölçüm: 390px'te sütun 17.7px,
   yatay "BA+" 17px — bitişik), o yüzden dikey. Kutu yine SABİT. */
.ndgrafik.genis .ndsut>span{font-size:8.5px;writing-mode:vertical-rl;
  transform:rotate(180deg);height:20px;align-items:center}
/* ⚠️ Yer varsa dikey yazı YOK: ölçüldü, 560px'ten sonra sütun ≥26px ve
   yatay etiket 17px — sığıyor. Döndürülmüş 8.5px yazı okunmuyor. */
@media (min-width:560px){
  .ndgrafik.genis .ndsut>span{writing-mode:horizontal-tb;transform:none;
    height:12px;align-items:flex-start}
}
.ndozet{display:flex;flex-wrap:wrap;gap:10px;font-size:12px;color:var(--ink-2);
  align-items:center}
/* Dönem seçici — OBS'nin kendi sayfasında da var. */
.ndsekme{display:flex;flex-wrap:wrap;gap:4px;margin-top:8px}
.ndtab{font:inherit;font-size:11.5px;padding:3px 8px;cursor:pointer;
  background:var(--surface-2);border:1px solid var(--border);color:var(--ink-2)}
.ndtab>span{color:var(--ink-3);font-size:10.5px}
.ndtab.sec{background:var(--seal-soft);border-color:var(--seal);color:var(--ink)}
.ndtab:active{transform:translateY(1px)}
@media (prefers-reduced-motion:reduce){.ndtab:active{transform:none}}
/* Yarıyıl uyuşmazlığı — sessiz kalınmayacak kadar önemli. */
.ndmevsim{margin-top:8px;padding:7px 9px;font-size:12px;line-height:1.5;
  background:var(--warn-soft);color:var(--warn-ink);
  border-left:3px solid var(--warn)}
/* Tercihin programa etkisi. */
.tercihnot{font-size:12px}
.tercihnot.ok{color:var(--anadal)}
.tercihnot.uymaz{color:var(--warn)}
/* Yan yana karşılaştırma tablosu. */
table.cmp{border-collapse:collapse;width:100%;font-size:12.5px}
table.cmp th,table.cmp td{border:1px solid var(--border);padding:6px 9px;
  text-align:left;vertical-align:top}
table.cmp thead th{font-size:11px;letter-spacing:.08em;text-transform:uppercase;
  color:var(--ink-3)}
table.cmp tbody th{color:var(--ink-2);font-weight:600;white-space:nowrap}
table.cmp .secili{background:var(--seal-soft)}
table.cmp .meta{font-size:11px;color:var(--ink-3)}
table.cmp .meta.eksi{color:var(--warn)}
table.cmp .meta.arti{color:var(--anadal)}
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
.tierstage{position:relative;display:flex;flex-direction:column;gap:38px}
/* ★ Çizgiler kutuların ÜSTÜNDE (z-index:2 > .tier'in 1'i). Altında kalınca
   birden çok kademe atlayan ya da sarmış satıra giden bağlar kutuların
   arkasında kayboluyordu — "bağlar tam bağlanmıyor" (kullanıcı 27.08.2026).
   Kılıf (zemin renginde) kutunun üstünden geçerken de çizgiyi okunur tutuyor,
   pointer-events:none olduğu için tıklama yine kutulara geçiyor. */
.tierlinks{position:absolute;left:0;top:0;pointer-events:none;overflow:visible;z-index:2}
/* ★ Çizgi tasarımı (27.08.2026). Eski hâlde çizgiler dururken NEREDEYSE
   GÖRÜNMEZDİ (opacity .55, kenarlık rengi) ve yapı ancak tıklayınca ortaya
   çıkıyordu. İki iyileştirme:
   1. KILIF: her çizginin altına zemin renginde kalın bir kat — çizgiler
      kesişince ve kutu kenarından geçince ayrışıyor (kartografide "casing").
   2. Dinlenmede de OKUNUR: bağ rengi (seal) ve daha belirgin. */
.tierlinks path.casing{fill:none;stroke:var(--ground);stroke-width:5;
  stroke-linecap:round}
.tierlinks path.line{fill:none;stroke:var(--seal);stroke-width:1.6;opacity:.55;
  stroke-linecap:round;transition:opacity .12s,stroke .12s,stroke-width .12s}
.tierstage.focus .tierlinks path.line{opacity:.08}
.tierstage.focus .tierlinks path.line.on{stroke:var(--cap);stroke-width:2.6;opacity:1}
.tier{position:relative;z-index:1}
.tier > h3{font-size:10.5px;color:var(--seal);font-weight:700;margin-bottom:10px;
  letter-spacing:.16em;text-transform:uppercase;
  font-family:"Chivo",Helvetica,Arial,sans-serif;
  padding-bottom:6px;border-bottom:2px solid var(--border-strong)}
.tier ul{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:8px}
.tier li{font-size:12px;padding:7px 10px;border-radius:0;background:var(--surface-2);
  border:1px solid var(--border);border-left:3px solid var(--border-strong);
  display:flex;flex-direction:column;gap:3px;cursor:pointer;width:196px;
  transition:opacity .12s,box-shadow .12s}
.tier li:hover{box-shadow:0 2px 10px -4px rgba(0,0,0,.5)}
.tier li .top{display:flex;justify-content:space-between;gap:6px;align-items:baseline}
/* Plan İÇİ önşart — çizginin temsil ettiği bağ. "önce:" ile okunuyor. */
.tier li .dep{font-size:10.5px;line-height:1.35;color:var(--ink-2)}
.tier li .dep b{color:var(--ink);font-weight:600}
/* Plan DIŞI önşart artık KOMPAKT rozet — eskiden 2-3 satır metin her kutuyu
   şişiriyordu (mobilde iyice). Tam liste ipucunda. */
.tier li .dispre{font-size:10px;color:var(--ink-3);border:1px solid var(--border);
  padding:0 7px;align-self:flex-start;border-radius:var(--r);cursor:pointer;
  user-select:none;
  /* Faz 46: 72×18px'ti — WCAG 2.2 AA tabanı 24×24. */
  min-height:24px;display:inline-flex;align-items:center}
.tier li .dispre:hover{color:var(--ink-2);border-color:var(--border-strong)}
.tier li .dispre[aria-expanded="true"]{color:var(--seal);border-color:var(--seal);
  background:var(--seal-soft)}
/* Rozet açılınca kodlar burada — mobilde de erişilir olsun diye SADECE ipucu
   değil (title tooltip dokunmatikte yok). */
.tier li .disout{font-size:10px;color:var(--ink-2);line-height:1.4;
  border-top:1px dashed var(--border);padding-top:3px}
.tier li .disout .mono{color:var(--ink)}
.tier li[data-s="DONE"]{opacity:.5;border-left-color:var(--anadal)}
.tier li[data-s="DONE"] .top{text-decoration:line-through}
/* Alınabilir = önşartların tamamı sağlanmış, BU DÖNEM alınabilir. */
.tier li[data-s="READY"]{background:var(--cap-soft);color:var(--cap-ink);font-weight:600;
  border-color:var(--cap);border-left-color:var(--cap)}
.tierstage.focus .tier li{opacity:.22}
.tierstage.focus .tier li.on{opacity:1}
.tier li.root{outline:2px solid var(--cap);outline-offset:2px}
/* Kademe efsanesi — renklerin ne anlama geldiği. */
.tierlegend{display:flex;flex-wrap:wrap;gap:14px;margin:2px 0 16px;
  font-size:11.5px;color:var(--ink-2)}
.tierlegend span{display:inline-flex;align-items:center;gap:6px}
.tierlegend i{width:22px;height:12px;border:1px solid var(--border);
  border-left:3px solid var(--border-strong);display:inline-block}
.tierlegend i.rdy{background:var(--cap-soft);border-color:var(--cap);border-left-color:var(--cap)}
.tierlegend i.done{border-left-color:var(--anadal);opacity:.6}
.tierlegend i.line{width:22px;height:0;border:0;border-top:2px solid var(--seal);opacity:.7}
.tierfoot{margin-top:10px;font-size:11.5px;color:var(--ink-3);line-height:1.6}
.tiergroup + .tiergroup{margin-top:26px;padding-top:22px;
  border-top:1px dashed var(--border-strong)}
.tiergroup > h3{font-size:13px;margin-bottom:12px;display:flex;gap:8px;align-items:center}
.tiergroup > h3 .tag{font-size:10px}

/* Bölüm çubuğu — yapışkan, tek satır, dar ekranda yana kayıyor. */
/* ⚠️ `var(--bg)` diye bir jeton YOK — doğrusu `--ground`. Yanlış ad
   çözümlenmeyince arka plan ŞEFFAF kalıyor ve kartlar çubuğun içinden
   geçerken üst üste biniyordu (kullanıcı raporu 23.08.2026). */
/* ★★ FAZ 46 — RAY (eski `.secnav` çapa çubuğu).
   Ölçülen sorun: 10 çapa, hepsi aynı sayfada; tıklamak kaydırıyordu.
   Artık görünüm değiştiriyor ve sayfa tek görünüm uzunluğunda.
   ⚠️ Ölçüde değişen tek şey konum DEĞİL, ANLAM: bu yüzden `aria-current`
   "page" (bulunduğun görünüm), eskiden "true" (kaydırılan bölüm) idi. */
.govde{display:grid;grid-template-columns:216px minmax(0,1fr);gap:26px;
  align-items:start}
.ray{position:sticky;top:18px;display:flex;flex-direction:column;gap:2px;
  border-right:1px solid var(--border);padding-right:10px}
.ray a{font-size:13.5px;letter-spacing:.01em;
  font-family:"Chivo",Helvetica,Arial,sans-serif;font-weight:700;
  color:var(--ink-2);text-decoration:none;padding:0 10px;
  border-left:3px solid transparent;
  /* ★ Faz 46: dokunma hedefi 40 → 44px (WCAG 2.2 AA tabanı 24, dokunmatik
     kılavuzu 44). Ray zaten dikey, yüksekliği bedava. */
  min-height:44px;display:flex;align-items:center;gap:8px}
.ray a:hover{color:var(--ink);background:var(--surface-2)}
.ray a[aria-current="page"]{color:var(--seal);border-left-color:var(--seal);
  background:var(--seal-soft)}
.ray .raysayi{margin-left:auto;font-family:"IBM Plex Mono",ui-monospace,monospace;
  font-size:11.5px;font-weight:400;color:var(--ink-3)}
.ray .raysayi:empty{display:none}
.ray .rayad.kisa{display:none}
.raydaha,.raykesme{display:none}
.ray .raybaslik{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:10.5px;
  letter-spacing:.16em;color:var(--ink-3);padding:14px 10px 6px;text-transform:uppercase}
.ray .raybaslik:first-child{padding-top:0}
.ray:empty{display:none}
.govde:has(.ray:empty){grid-template-columns:minmax(0,1fr)}
.icerik{display:flex;flex-direction:column;gap:30px;min-width:0}
/* ★ Telefon: ray ALT SEKME ÇUBUĞU olur. Ölçüm: 390px'te 10 çapanın 3'ü
   görünüyordu ve haftalık program 4 ekran aşağıdaydı. Alt çubuk hem her
   zaman görünür hem başparmak menzilinde. Birincil 4 sekme yazılı,
   gerisi "Daha" altında — sığmayanı kaydırmaya bırakmak, görünmeyen
   sekme demekti. */
@media (max-width:700px){
  .govde{grid-template-columns:minmax(0,1fr);gap:0}
  .ray{position:fixed;left:0;right:0;bottom:0;top:auto;z-index:40;
    flex-direction:row;gap:0;padding:0;border-right:0;
    border-top:1px solid var(--border);background:var(--surface);
    box-shadow:0 -6px 14px -8px rgba(0,0,0,.55)}
  .ray a{flex:1 1 0;min-width:0;min-height:56px;padding:0 4px;
    flex-direction:column;justify-content:center;gap:2px;
    font-size:10.5px;letter-spacing:.02em;text-align:center;
    border-left:0;border-top:3px solid transparent}
  .ray a[aria-current="page"]{border-left-color:transparent;
    border-top-color:var(--seal)}
  .ray a .rayad{display:block;overflow:hidden;text-overflow:ellipsis;
    white-space:nowrap;max-width:100%}
  .ray .rayad.uzun{display:none}
  .ray .rayad.kisa{display:block}
  .ray .raysayi{margin:0}
  .ray .raybaslik{display:none}
  /* ★★ FAZ 46 — ÖNERİ SEKMELERİ TELEFONDA TEK SATIR.
     Ölçüm: "ÖNERİ 2 · 19.5 KREDİ · 2 ÇEVRİMİÇİ" 390px'te sığmıyor ve üç
     sekme alt alta 4 satır yer kaplıyordu — haftalık programın hemen
     önünde. Ayırt edici metin YALNIZ SEÇİLİ sekmede kalıyor: öbürlerinde
     zaten okunmuyordu, çünkü seçili olmayan sekmenin farkı ancak ona
     geçince işe yarıyor.
     ⚠️ Bilgi kaybolmuyor — sekmeye basınca beliriyor, ve `title` her
     sekmede tam metni taşıyor. */
  .tab{flex:1 1 auto;min-width:0;padding:8px 9px;font-size:11px;
    white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .tab:not([aria-selected="true"]) .tabfark{display:none}
  /* ★ FAZ 50 — "Karşılaştır" kendi satırını İSTEMİYOR artık: kredi sayısı
     `.tabfark` içine girince seçili olmayan sekme "Öneri 2" kadar kısa ve
     dördü tek satıra sığıyor (ölçüldü: 3 satır → 1, ~180px kazanç). */
  #karsilastir{flex:0 1 auto;border-left:1px solid var(--border)}
  /* ★★ FAZ 50 — "Şimdi:" panelindeki İKİ DÜĞME ALT ÇUBUĞUN KOPYASI.
     Telefonda gezinme sabit alt çubukta: "Program" ve "Dersler" sekmeleri
     ekranın altında HER ZAMAN duruyor. Aynı iki hedefi panelde tekrar
     etmek, ölçülen 232px'lik panelin yarısını yiyordu — üstelik her
     görünümde, içeriğin ÖNÜNDE.
     ⚠️ Bilgi gizlenmiyor: hedefin kendisi ekranda, bir dokunuş uzakta.
     Panelde yalnız alt çubukta KARŞILIĞI OLMAYAN eylemler kalıyor. */
  #sonraki [data-go="schedSection"],
  #sonraki [data-go="candSection"]{display:none}
  #sonraki{padding:10px 12px}
  .sonrakiliste{gap:8px}
  /* ⚠️ Panel "Programın hazır. Şimdi:" diyor — yeri PROGRAM görünümü.
     Telefonda her görünümün üstünde duruyordu: ölçüldü, 11 görünümün
     10'unda içeriğin önünde 144px. Masaüstünde kalıyor (orada içerik
     zaten ekranın üstünde başlıyor). */
  :root:not([data-gorunum="schedSection"]) #sonraki{display:none}
  /* Başlık satırı telefonda iki satıra bölünmesin diye sekmeler alta. */
  .prgbaslik .tabs{margin-left:0;flex:1 1 100%}
  /* Üst çubuk: ad ve Tema aynı satırda, durum satırları küçük. */
  body:not(.kurulum) header{gap:4px 10px;padding-bottom:8px}
  body:not(.kurulum) header h1{font-size:18px}
  body:not(.kurulum) header .eyebrow{flex:1 1 100%;order:3;font-size:9.5px}
  body:not(.kurulum) header .sub{flex:1 1 100%;order:4;font-size:11.5px}
  body:not(.kurulum) header #theme{order:2;min-height:44px;padding:0 12px}
  .veriyasi{gap:2px 6px}
  /* Dördü çubukta, gerisi "Daha" altında. */
  .ray a[data-alt]{display:none}
  .raydaha{display:flex;flex:1 1 0;min-width:0;min-height:56px;padding:0 4px;
    flex-direction:column;align-items:center;justify-content:center;
    background:transparent;border:0;border-top:3px solid transparent;
    font-family:"Chivo",Helvetica,Arial,sans-serif;font-weight:700;
    font-size:10.5px;letter-spacing:.02em;color:var(--ink-2);cursor:pointer}
  .raydaha[aria-expanded="true"]{color:var(--seal);border-top-color:var(--seal);
    background:var(--seal-soft)}
  /* ⚠️ `wrap-reverse` + `order` ŞART. Düz `wrap` ile alt sekmeler DOM
     sırasına göre birinci satıra karışıyor ve dört birincil sekme
     "Pr… De… Ne…" diye eziliyordu (ölçüldü). `order` dördünü tek satırda
     tutuyor, `wrap-reverse` o satırı EN ALTTA — başparmak menzilinde —
     bırakıyor; açılan ızgara yukarı doğru büyüyor. */
  .ray[data-acik]{flex-wrap:wrap-reverse}
  .ray a:not([data-alt]),.raydaha,.raykesme{order:1}
  .ray[data-acik] .raykesme{display:block;flex:0 0 100%;height:0;min-height:0}
  .ray[data-acik] a[data-alt]{display:flex;flex:0 0 33.333%;order:2;
    border-bottom:1px solid var(--border)}
  /* Alt çubuk içeriğin son satırını yemesin. */
  .wrap{padding-bottom:78px}
}
/* ⚠️ Etkin olmayan görünüm KAPALI ama DOM'da: `hidden` (veri yok) ile
   karıştırılmasın diye ayrı öznitelik. İkisini tek bayrağa bindirmek,
   "veri yok" ile "şu an bakmıyorsun"u aynı şey yapardı. */
[data-disgorunum]{display:none !important}
section[id]{scroll-margin-top:16px}

/* ★ Bölüm seçilmemişken rapor bölümleri GİZLİ. Boş bir ızgara, dolu bir
   yanlış ızgaradan iyidir ama ikisi de gereksiz — kullanıcının yapması
   gereken tek şey var ve o yukarıda duruyor. */
body.kurulum #panels,
body.kurulum #savedSection,
body.kurulum #schedSection,
body.kurulum #creditSection,
body.kurulum #suggestSection,
body.kurulum #denklikSection,
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
/* Ray gizliyken içerik tek sütuna açılsın (aksi hâlde 216px'lik boş bir
   sütun kalır ve karşılama kartı sağa kaçar). */
body.kurulum .govde{grid-template-columns:minmax(0,1fr)}

/* Karşılama (ilk ziyaret). */
.hero{border-top:6px solid var(--seal)}
.hero h2{font-size:22px;margin:6px 0 8px}
.hero .lead{font-size:14px;color:var(--ink-2);line-height:1.65;max-width:62ch}
.steps{display:flex;flex-direction:column;gap:10px;margin-top:18px}
.step{display:flex;gap:14px;align-items:flex-start;padding:12px 14px;
  background:var(--surface-2);border:1px solid var(--border)}
/* ★ Faz 54: bitmiş ve kapalı adım OPAKLIKLA soldurulmuyor. `opacity:.5`
   açıklamaları 2,0–3,5:1'e düşürüyordu (taban 4,5) — oysa kapalı adımın
   metni yeni gelen kişiye SIRADA ne olduğunu anlatan tek yer. Durum artık
   renk ve kenarla: soluk başlık, kesik kenar, kilit simgesi. */
.step.done .body b{color:var(--ink-2)}
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
.step.kilit{border-style:dashed;background:transparent}
.step.kilit .body b{color:var(--ink-2)}
.step.kilit .body .why{color:var(--ink-3)}
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
  --accent:var(--anadal);padding:8px 11px;min-width:184px;flex:1 1 184px;
  --tonhedef:var(--accent);--tonoran:0%;
  border-left:4px solid color-mix(in oklab, var(--accent),
    var(--tonhedef) var(--tonoran))}
/* ★★ FAZ 39 — SINIF ÇAKIŞMASI. Bu satır eskiden `.savedcard.cap` idi ve
   `.cap` YUKARIDA (satır ~1857) kontenjan çipinin sınıfı:
   `display:inline-flex; white-space:nowrap`. Yani kaydedilen programdaki
   HER ÇAP/yandal ders kartı satır içine çöküp kırpılıyordu — kod, CRN, ad
   ve saat tek satırda, kartın dışına taşarak. Ad DEĞİŞTİ; renk aynı. */
.savedcard.ikinci{--accent:var(--cap)}
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
  /* ★★ Şube seçenek kartı telefonda ALT ALTA (UX 27.08.2026). İki kolon
     (solda ders, sağda CRN/saat/hoca) yan yana sığmıyordu: CRN ve hoca adı
     sağ kenardan KESİLİYORDU — üstelik CRN kayıt günü yazılan sayı, kesik
     olması kabul edilemez. Alt alta gelince tam genişlik açılıyor. */
  .opt{flex-direction:column;align-items:stretch;gap:4px}
  .opt > span:last-child{text-align:left !important;white-space:normal}
}

dialog{border:1px solid var(--border-strong);border-top:6px solid var(--seal);
  border-radius:var(--r);background:var(--surface);
  color:var(--ink);max-width:540px;width:calc(100% - 32px);padding:0;box-shadow:var(--shadow)}
/* Program tablosu 540px'e sığmıyor; içeriği kesmek yerine pencereyi büyütüyoruz.
   Yükseklik ekranla sınırlı, taşan kısım pencerenin İÇİNDE kayıyor. */
dialog.wide{max-width:880px}
dialog.wide .pad{max-height:min(84vh,760px);overflow-y:auto}
dialog::backdrop{background:var(--scrim)}
dialog .pad{padding:22px 24px}
footer{color:var(--ink-3);font-size:12px;border-top:3px solid var(--seal);padding-top:14px;
  line-height:1.7}
/* ★ Faz 27 — YAZDIRMA (yapılacaklar §3.2).
   Kayıt günü ekran yerine kâğıda bakan çok: ızgara + CRN listesi tek sayfa.
   ⚠️ Yazdırılan sayfa, ekranın bir fotoğrafı değil: düğmeler, süzgeçler,
   gezinme çubuğu kâğıtta işe yaramaz — çıkarılıyor. Kalan şey kayıt
   masasında lazım olan şey. */
/* ★★ FAZ 51 — ZORLANMIŞ RENK KİPİ (Windows yüksek kontrast /
   `forced-colors: active`). Tarayıcı bu kipte bütün renkleri kullanıcının
   paletiyle DEĞİŞTİRİYOR. Bu araçta renk veri taşıdığı için ölçüm kötüydü:

     · ızgara blokları **11 ayrı tondan tek renge** düştü (rol + ders tonu
       bilgisi tamamen kayboldu); telefonda gün listesi de aynı,
     · doluluk ve ilerleme çubuklarının DOLU kısmı ile kanalı aynı renge
       düştü — yani çubuk tamamen GÖRÜNMEZ oldu (kayıt gününde bakılan tek
       sayı bu),
     · seçili sekme, seçili kip ve açık bölüm "seçili" görünmüyordu.

   Bu depoda kural: bilgi sessizce kaybolmaz. Renk gidiyorsa YAZI gelir,
   çubuklar sistem renkleriyle yeniden çizilir.
   ⚠️ `forced-color-adjust:none` KULLANILMADI: kullanıcının paletini
   ezmek, yüksek kontrast isteyen kişinin isteğini geri çevirmek olurdu.
   Sistem renkleri (`Highlight`, `CanvasText`) zaten o palettendir. */
@media (forced-colors: active){
  /* 1. ROL, renk yerine yazıyla. Ton (ders ayrımı) yazıya çevrilemez ama
        blok zaten ders KODUNU taşıyor; kaybolan tek şey roldü. */
  .blk[data-role="ANADAL"]::after,.daylist .row[data-role="ANADAL"]::after{
    content:" · anadal"}
  .blk[data-role="CAP"]::after,.daylist .row[data-role="CAP"]::after{
    content:" · ÇAP"}
  .blk[data-role="YANDAL"]::after,.daylist .row[data-role="YANDAL"]::after{
    content:" · yandal"}
  .blk[data-role="PLAN_DISI"]::after,.daylist .row[data-role="PLAN_DISI"]::after{
    content:" · plan dışı"}
  .blk[data-role]::after,.daylist .row[data-role]::after{
    font-size:10px;letter-spacing:.06em;text-transform:uppercase;
    white-space:nowrap}
  .blk[data-role]{border:1px solid CanvasText}
  /* 2. ÇUBUKLAR: dolu kısım sistem vurgusu, kanal kenarlıkla belli. */
  .capbar,.meter,.gaugebar .track{border:1px solid CanvasText;background:Canvas}
  .capbar>i,.meter i,.gaugebar .track i{background:Highlight}
  /* Taralı "bu dönem planlanan" dilim: tarama da düzleşiyor, ayrımı
     kesikli kenarla koruyoruz. */
  .meter i.plan{background:Canvas;border-right:2px dashed CanvasText;opacity:1}
  /* 3. SEÇİLİ durumlar. `aria-selected`/`aria-pressed` ekran okuyucuya
        zaten söylüyordu; eksik olan GÖRSEL ayrımdı.
     ⚠️⚠️ `background:Highlight; color:HighlightText` KULLANILMADI, ölçüldü:
     Chromium zorlanmış kipte yazının arkasına `Canvas` renginde bir
     "arka levha" çiziyor; HighlightText de beyaz olunca yazı BEYAZ ÜSTÜNE
     BEYAZ düşüyor ve sekme düpedüz boş beyaz bir şerit olarak çıkıyordu
     (ekran görüntüsüyle doğrulandı). Seçiliyi KALIN ÇERÇEVEYLE
     söylüyoruz; yazı okunaklı kalıyor. */
  .tab[aria-selected="true"],.modebtn[aria-pressed="true"],
  .ray a[aria-current="page"],.watchmini[aria-pressed="true"]{
    background:Canvas;color:CanvasText;
    outline:3px solid Highlight;outline-offset:-3px}
  /* 4. Doluluk uyarısı (dolu / az yer kaldı) renkle söyleniyordu; sayı
        zaten yazıyor, kenarlıkla pekiştiriyoruz. */
  .cap.full,.cap.tight{outline:1px solid CanvasText;outline-offset:1px}
}

@media print{
  @page{margin:12mm}
  html,body{background:#fff;color:#000}
  /* ★★ FAZ 48 — KÂĞIT HER ZAMAN GÜNDÜZ PALETİ (taramada ölçüldü).
     Gece şemasındayken yazdırınca `--ink-3` kâğıda **açık gri** çıkıyordu:
     saat sütunu (08:00, 09:00…) rgb(132,142,161), özet satırı
     rgb(154,165,184) — beyaz kâğıtta ~2,6:1, yani okunmuyor. Kart zemini de
     rgb(22,27,36) kalıyordu (tarayıcı zemin basmayı açarsa siyah blok).
     ⚠️ Yeni palet UYDURULMADI: birebir açık tema jetonları. */
  :root{
    --ground:#FFFFFF; --surface:#FFFFFF; --surface-2:#F0F2F6;
    --border:#D4D9E2; --border-strong:#141821;
    --ink:#0D1017; --ink-2:#4B5462; --ink-3:#5F6878;
    --seal:#3B4E9E; --seal-soft:#E7EAF7;
    --seal-hover:#2F3F8E; --scrim:rgba(8,16,26,.5);
    --anadal:#0A6B58; --anadal-soft:#D6EBE5; --anadal-ink:#074A3D;
    --cap:#8A5210; --cap-soft:#F6E7D2; --cap-ink:#633B08;
    --yandal:#1F5C77; --yandal-soft:#DCECF4; --yandal-ink:#154457;
    --danger:#C02D18; --warn:#7A5709;
    --warn-soft:#FCF1DB; --warn-ink:#6B4A05;
    --shadow:none}
  /* Boş hücrenin "+" işareti bir DAVET; kâğıtta tıklanacak bir şey yok. */
  #grid td.free::after{content:"" !important}
  header,#secnav,#setupbar,#hero,#sonraki,.toolbar,.candbar,.modes,
  #candSection,#blockSection,#suggestSection,#changeSection,#basvuruSection,
  /* ⚠️ `#panels` ve `#savedSection` de burada: görünüm kipinden önce
     hepsi birden açıktı, şimdi hangi görünümdeysen o kâğıda sızıyordu —
     aynı Cmd+P aynı kâğıdı vermeli. */
  #panels,#savedSection,
  #tierSection,#creditSection,.tabs,#notime .blockitem button,
  #arzUyari,#ayarHatasi,dialog,
  /* ★★ FAZ 48 — Faz 46/47'nin KABUĞU KÂĞIDA SIZIYORDU (taramada ölçüldü).
     `.govde` iki sütunlu ızgara: ray `display:none` olsa bile 216px'lik
     SÜTUN duruyordu; `.prgduzen` de 240px'lik bağlam sütununu ayırıyordu.
     Sonuç: A4'te ızgara 660px, sayfanın yarısı boş. Tasarım sisteminin
     kuralı: "basılan sayfa ekranın fotoğrafı değil" — ekran denetimleri
     çıkar, ızgara ve CRN listesi kalır. */
  .ipucu,#kilitNot,#donemUyari,.gridaralik{display:none !important}
  .govde,.prgduzen{display:block !important}
  .prgyan{margin-bottom:6mm}
  .icerik{display:block}
  /* ★★ FAZ 48 — BAŞKA GÖRÜNÜMDEYKEN YAZDIRINCA KÂĞIT BOŞ ÇIKIYORDU.
     Ölçüldü: "Alabileceğim dersler"deyken Cmd+P → 166 karakter, 179px.
     Sebep iki kuralın çarpışması: görünüm kipi açık olmayan bölüme
     `[data-disgorunum]{display:none !important}` koyuyor, yazdırma bloğu da
     zaten öbür bölümleri gizliyor — geriye hiçbir şey kalmıyordu.
     Kâğıt her zaman HAFTALIK PROGRAM + CRN listesi: yazdırma ekranın
     fotoğrafı değil, elde taşınan çıktı. Görünüm gizlemesini burada
     kimlik seçicisiyle geri alıyoruz (`!important`i ancak o yener). */
  #schedSection[data-disgorunum]{display:block !important}
  /* Kâğıtta kart kenarlığı ve gölge gürültü. */
  .card{border:0;box-shadow:none;padding:0;margin:0 0 10mm}
  section[id]{break-inside:avoid}
  /* Kâğıdın genişliği okuma ölçüsüne değil SAYFAYA bağlı; ekrandaki
     1340/1720px kilidi kâğıtta 1464 ile 1280 arasında gidip geliyordu. */
  .wrap{max-width:none !important;padding:0 !important}
  #grid{width:100%}
  #grid td,#grid th{border-color:#999}
  .blk{border:1px solid #666;background:#fff !important;color:#000 !important}
  .blk .mono{color:#000}
  /* ★ CRN listesi kâğıtta ASIL İŞ — ızgaranın altına basılıyor.
     Ekranda pencerede duruyor; yazdırırken pencere açık olmayabilir. */
  #printCrn{display:block !important}
  a[href]::after{content:""}          /* URL'leri metne eklemesin */
}
#printCrn{display:none}
#printCrn table{width:100%;border-collapse:collapse;font-size:11pt}
#printCrn th,#printCrn td{border:1px solid #999;padding:4px 6px;text-align:left}

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
      <!-- ★ Kısaltma UYDURMA değil, açılımın kendisi: DErs Planlama ARacı.
           Vurgulu harfler `ui.acilim_html()` ile TÜRETİLİYOR — elle
           boyansaydı ad değişince ikisi ayrışırdı. -->
      <h1 id="doctitle"><span class="kurum">__AD_KURUM__</span> __AD_KISA__</h1>
      <div class="acilim">__AD_ACILIM__</div>
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

<!-- ★ İLK ZİYARET. Program seçilmemişken rapor GÖSTERİLMİYOR: seçilmemiş
     bir bölümün dolu haftalık programı, aracın söyleyebileceği en yanlış şey. -->
<section class="card pad hero" id="hero" hidden></section>

<!-- Faz 26: kurulum bitince "şimdi ne yapabilirsin". Bir kerelik. -->
<div class="note sonraki" id="sonraki" hidden></div>

<!-- ★★ FAZ 46 — KABUK (kullanıcı isteği 18.09.2026: "bütün düzeltmeleri ve
     yeni tasarımı uygular mısın").
     Ölçüm: haftalık programın tepesi masaüstünde y=1825px, telefonda
     y=3354px'ti; sayfa 11 bölüm yığını hâlinde 7,3 / 16,4 ekrandı. Bölüm
     çubuğu bir ÇAPAYDI — tıklamak sayfayı kaydırıyor, kısaltmıyordu.
     Artık: solda ray (telefonda alt sekme çubuğu), sağında TEK görünüm.
     ⚠️ Bölümler DOM'dan silinmiyor, yalnız etkin olmayan görünüm
     kapanıyor; veri yokluğundan `hidden` olanlar ayrı bir şey ve ray'de
     hiç görünmüyor (tıklayınca boş açılan bir sekme, olmayan sekmeden
     kötüdür). -->
<div class="govde">
<nav class="ray" id="secnav" aria-label="Bölümler"></nav>
<!-- ★ FAZ 51 — `<main>` yer işareti. Ölçüldü: sayfada `banner` (header),
     `navigation` (ray) ve `contentinfo` (footer) vardı ama **`main` YOKTU**;
     ekran okuyucu kullanıcısı "asıl içeriğe atla" yapamıyordu. Etiket
     değişti, sınıf aynı — bütün CSS `.icerik` üzerinden. -->
<main class="icerik" id="icerik">

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
  <!-- ★★ FAZ 46 — başlık, kip ve öneri sekmeleri TEK satırda (eskiden iki
       blok, 145px). Kip notu ("79 aday · plandaki tüm açık dersler") altta
       kalıyor: tek satır ve kipin ne demek olduğunu söyleyen tek yer. -->
  <div class="prgbaslik">
    <h2>Haftalık program</h2>
    <div class="modes" id="modes"></div>
    <div class="tabs" id="tabs">
      <!-- Faz 27: önerileri yan yana karşılaştır. -->
    </div>
  </div>
  <div class="modenote" id="modeNote"></div>
  <!-- ★★ FAZ 46 — PROGRAM ORTADA, BAĞLAM SAĞDA.
       Ölçüm (17.09.2026): ızgaranın ÜSTÜNDE 8 blokta 313 kelime vardı —
       özet, arz uyarısı, kilit şeridi, araç çubuğu ve iki ipucu satırı.
       Hepsi tek tek doğru ama hepsi birden ızgarayı ekrandan itiyordu.
       Artık sağ sütunda: aynı bilgi, aynı yerde, programın yanında.
       ⚠️ Hiçbiri GİZLENMİYOR — yalnız yer değiştiriyor. Dar ekranda
       (≤1100px) sütun ızgaranın ALTINA düşüyor, üstüne değil. -->
  <div class="prgduzen">
  <div class="prgorta">
  <div class="gridwrap"><table class="grid" id="grid"></table></div>
  <div id="gridAralik" class="gridaralik"></div>
  <!-- Dar ekranda ızgaranın yerini alır. Aynı veriden kuruluyor; ızgara
       yana kaydırma istediği için telefonda kullanışsızdı (yapılacaklar 4.1). -->
  <div class="daylist" id="daylist"></div>
  <div id="notime" style="margin-top:14px"></div>
  <!-- ★ Yazdırınca ızgaranın altına basılan CRN listesi (Faz 27).
       Ekranda gizli: orada CRN'ler zaten "Kayıt günü" penceresinde. -->
  <div id="printCrn"></div>
  <!-- ★★ FAZ 47 — LEJANT IZGARANIN ALTINDA (kullanıcı 18.09.2026:
       *"ders programı hakkındaki lejant gibi bilgileri ders programının
       altında tutabilirsin"*). Faz 46'da sağ sütuna almıştım; orada dar
       sütunu şişiriyordu ve anlattığı şeyin — ızgaranın — yanında değil
       üstündeydi. ⚠️ Yine KATLI: Faz 40'ın dersi gereği silinmiyor. -->
  <details class="ipucu">
    <summary>Nasıl kullanılır · renkler ne diyor</summary>
    <div class="hint">Derse tıkla → şube değiştir, yerine başka ders koy, çıkar.
      Boş hücreye tıkla → o saate uyan dersler.</div>
    <div class="hint" id="tonNot">Renk hangi programdan olduğunu söylüyor
      &nbsp;·&nbsp; ton hangi ders olduğunu: aynı ton, aynı ders — 9 tondan
      sonrası tekrar eder, emin olmak için dersin üstüne gel</div>
  </details>
  </div><!-- /prgorta -->

  <aside class="prgyan">
    <div class="summary" id="schedSummary"></div>
    <!-- C3: arz uyarısı — kayıt gününden ÖNCE bilinmesi gereken şey. -->
    <div class="note arz" id="arzUyari" hidden></div>
    <!-- ★★ FAZ 45 — SAATE KİLİT ŞERİDİ. Kilit görünmez bir kısıt olamaz:
         motor onun etrafında program kuruyor. -->
    <div class="note kilit" id="kilitNot" hidden></div>
    <!-- ★★ FAZ 41 — DÖNEM BİLİNMİYORSA PROGRAM BUNU SÖYLEMELİ. -->
    <div class="note donemsiz" id="donemUyari" hidden></div>
    <div class="toolbar">
      <span id="editState" class="chip edited" hidden>değiştirildi</span>
      <button class="ghost primary" id="savePicks" hidden>Programı kaydet</button>
      <!-- D2: tek adım geri. "Öneriye dön" her şeyi siliyordu. -->
      <button class="ghost" id="undo" hidden>Geri al</button>
      <button class="ghost" id="reset" hidden>Öneriye dön</button>
      <button class="ghost" id="crnBtn">Kayıt günü</button>
      <button class="ghost" id="icsBtn">Takvime aktar</button>
      <button class="ghost" id="shareBtn">Bağlantı</button>
      <button class="ghost" id="crnLoad">CRN'den yükle</button>
      <span id="savedMark" class="chip" style="color:var(--anadal)" hidden></span>
    </div>
  </aside>
  </div><!-- /prgduzen -->
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

<!-- ★ Almam gereken bir dersin denkliği bu dönem açıksa (kullanıcı isteği
     27.08.2026). Aday listesinden ayrı: burada gösterilen ders planımda
     olmayabilir ama denklikle bir gereksinimi karşılıyor. -->
<section class="card pad" id="denklikSection" hidden>
  <div class="sechead"><div class="eyebrow">Denklik</div><div class="rule"></div></div>
  <h2>Denkliği bu dönem açık</h2>
  <div class="summary">Almam gereken bir dersin <b>denkliği</b> bu dönem
    açıksa burada. O açık dersi alırsan gereken ders sayılır — çoğu zaman
    <b>başka bölümden</b> bir ders, <b>dilekçeyle</b> saydırılır. Kaynak:
    OBS'nin ilan ettiği resmî denklikler + kendi beyanların. Saydırma için
    danışmanına ve fakülte yönetim kuruluna danış.</div>
  <div id="denklikBody" style="margin-top:12px"></div>
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
    <!-- ★ FAZ 51 — YER TUTUCU ETİKET DEĞİLDİR. Ölçüldü: bu kutunun
         `<label>`ı, `aria-label`ı ve `aria-labelledby`si yoktu; ekran
         okuyucu "arama" diyip geçiyordu. Üstelik yer tutucu yazmaya
         başlayınca kayboluyor — neyin arandığını hatırlatan tek şeydi. -->
    <input type="search" id="candQ" aria-label="Aday derslerde ara"
      placeholder="ders ara — kod, ad ya da hoca (örn. MAT 103E, olasılık, Feza)">
    <div class="radios" id="candRole"></div>
    <label class="tickbox"><input type="checkbox" id="candFree"> yalnız yeri olanlar</label>
    <!-- ★ Faz 25/B1 — planında OLMAYAN dersi de aramak/eklemek için. -->
    <button class="ghost" id="katalogBtn">Katalogda ara</button>
    <span class="candcount" id="candCount"></span>
    <span class="kisayol">↑↓ gez · Enter ekle · / ara</span>
  </div>
  <!-- ★ Faz 46: 390px'te tablo 418px — kutusunun içinde yana kayıyor ama
       kaydırılabildiğine dair hiçbir işaret yoktu (ölçüldü). Kenar solması
       "burada devamı var" diyor; tamamen kaydırınca kayboluyor ki yanlış
       ipucu vermesin. -->
  <div class="listwrap" id="candWrap" style="margin-top:12px">
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
    bitirebileceğin en kısa süredir. <b>Çizgiler önşart bağıdır</b> — bir dersin
    üstüne gelince yalnız o dersin zinciri belirir, tıklarsan kilitlenir
    (ikinci tıkta çözülür).</div>
  <div class="tierlegend" aria-hidden="true">
    <span><i class="rdy"></i> bu dönem alınabilir</span>
    <span><i class="done"></i> almışsın</span>
    <span><i></i> önşartı bekliyor</span>
    <span><i class="line"></i> önşart bağı</span>
  </div>
  <!-- Her ikinci programın KENDİ zinciri; aralarında önşart ilişkisi yok. -->
  <div id="tierGroups" style="margin-top:14px"></div>
</section>

</main><!-- /icerik -->
</div><!-- /govde -->

<footer>
  Bu araç bilgilendirme amaçlıdır; ders kayıt kararların için danışmanına ve OBS'ye danış.
  Şube ve kontenjan verisi <span id="gen" class="mono"></span> itibarıyla.
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

/* ★★ FAZ 40 — ders başına TON basamağı.
   Rolün rengi sabit; bu yalnız `--soft`u hangi yöne, ne kadar kaydıracağımızı
   söylüyor. İki hedef de JETON: tema değişince ton kendiliğinden yeni
   paletten hesaplanıyor — renk JS'te PİŞİRİLMİYOR. (Tema düğmesi yeniden
   render ETMİYOR; pişmiş renk eski temada kalırdı.)

   ⚠️ Merdiven TAHMİNLE değil ÖLÇÜYLE seçildi (tools/ton_merdiveni.py). Üç
   taban birden tutuluyor, dört rolde ve İKİ temada:
     · yazı kontrastı  ≥ 4.5  (WCAG AA)          — ölçülen en kötü 4.67
     · zemin farkı ΔE  ≥ 0.035 (OKLab)           — ölçülen en kötü 0.039
       (blok, boş hücreden ayrılmalı; yoksa ton uğruna blok kayboluyor)
     · basamaklar arası ΔE en büyük olsun        — ölçülen en kötü 0.0174
   İlk denemede merdivenin yarısı `--ground` yönündeydi ve ÖLÇÜLDÜ: o üç
   basamak arası ΔE 0.006, yani GÖRÜNMÜYORDU — `--soft` koyu temada zaten
   `--ground`a çok yakın. Ayrıntı: docs/faz40-ders-tonlari.md */
const TON_BASAMAK = [
  ["soft",    0], ["ground", 38],
  ["accent",  5], ["accent",  9], ["accent", 15], ["accent", 19],
  ["accent", 23], ["accent", 29], ["accent", 33],
];
/* ⚠️ PLAN DIŞI dersin tonu YOK. Rengi gri (`--soft`=yüzey, `--accent`=--ink-3);
   gri bir aileden merdiven çıkarmak ölçüldü ve İKİ tabanı da düşürüyordu
   (yazı 4.39 — AA altı; zemin ΔE 0.021 — blok boş hücreden ayrılmıyor).
   Renksizlik burada zaten BİLGİ: bu ders hiçbir planın parçası değil. */
const TONSUZ_ROL = new Set(["PLAN_DISI"]);

/** Ders kodundan KARARLI tercih — aynı ders her açılışta aynı basamağı ister. */
function tonTercihi(kod){
  let h = 0;
  const s = String(kod || "");
  for(let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return h % TON_BASAMAK.length;
}

/* Görünümdeki dersler için basamak dağıtımı. Tercih hash'ten gelir; o basamak
   AYNI ROLDE doluysa ileri sondalanır. Yani 9 basamak dolana kadar hiçbir iki
   ders aynı tona düşmüyor.
   ⚠️ Bedeli: hafta değişince çakışan derslerin tonu kayabiliyor. Kabul edildi,
   çünkü ton bir İPUCU — kimlik kodun kendisi, her blokta yazılı. */
let TON_HARITA = {};
function tonHaritaKur(kodRolCiftleri){
  TON_HARITA = {};
  const dolu = {};
  const gorulen = new Set();
  const liste = kodRolCiftleri
    .filter(([kod, rol]) => kod && !TONSUZ_ROL.has(rol))
    .filter(([kod]) => !gorulen.has(kod) && gorulen.add(kod))
    .sort((a, b) => a[0].localeCompare(b[0], "tr"));   // kararlı sıra
  liste.forEach(([kod, rol]) => {
    const alinan = dolu[rol] = dolu[rol] || new Set();
    let i = tonTercihi(kod);
    for(let n = 0; n < TON_BASAMAK.length && alinan.has(i); n++)
      i = (i + 1) % TON_BASAMAK.length;
    alinan.add(i);
    TON_HARITA[kod] = i;
  });
}

/** Bloğa yapıştırılacak satır içi jetonlar. Renk DEĞİL: yön + oran — tema
    değişince tarayıcı yeni paletten yeniden hesaplıyor. */
function tonStil(kod, rol){
  if(TONSUZ_ROL.has(rol)) return "";
  const i = TON_HARITA[kod] !== undefined ? TON_HARITA[kod] : tonTercihi(kod);
  const [hedef, oran] = TON_BASAMAK[i];
  return hedef === "soft" ? ""
    : `--tonhedef:var(--${hedef});--tonoran:${oran}%`;
}

/* ★ FAZ 40 — AYNI DERSİN BÜTÜN SAATLERİ.
   Ton bir ipucu; bu onu KESİNLİĞE çeviriyor. Bir bloğun üzerine gelince ya
   da klavyeyle odaklanınca o dersin haftadaki bütün buluşmaları
   işaretleniyor — ızgarada ve gün listesinde aynı anda.

   ⚠️ İşaret RENK DEĞİL (çerçeve + hafif büyütme): renk körlüğünde de
   okunuyor ve tonun kendisiyle yarışmıyor. */
function esDersBagla(){
  const hepsi = () => document.querySelectorAll("#grid .blk[data-course], "
                                              + "#daylist .row[data-course]");
  const isaretle = (kod) => hepsi().forEach(el =>
    el.classList.toggle("esder", !!kod && el.dataset.course === kod));
  hepsi().forEach(el => {
    el.addEventListener("mouseenter", () => isaretle(el.dataset.course));
    el.addEventListener("mouseleave", () => isaretle(null));
    el.addEventListener("focus",      () => isaretle(el.dataset.course));
    el.addEventListener("blur",       () => isaretle(null));
  });
}

/* ★ B3 — dönem: ekranda okunur ad, ham kod ise ipucunda. Çözülemediyse
   ham kod yazıyor; uydurma bir dönem adı ham koddan çok daha kötü. */
const donemYazi = () => DATA.termLabel || DATA.term || "";

/* ★ C3 — YER. Sunucu ilan edilmemiş binayı artık BOŞ gönderiyor
   (eskiden "belirsiz" yazıyordu ve bir bina adı sanılıyordu; ölçüldü:
   3630 buluşmanın 1542'si böyle). Kod tek başına da bir yer değil —
   tam ad ipucunda. */
const yerYazi = (kod) => kod ? kod : "yer yok";
const yerBaslik = (kod) => {
  if(!kod) return "OBS'de yer bildirilmemiş";
  const ad = (DATA.buildings || {})[kod];
  return ad ? `${kod} — ${ad}` : kod;
};

let LBL = DATA.secondLabel || "ÇAP";
/* ★ ÇAP ve yandal aynı anda olabiliyor: başlıklar TEK programa göre
   yazıldığında öbürü yokmuş gibi görünüyordu. */
const SECONDS = () => DATA.seconds || [];
/* ★ Seçili ama planı bulunamayan ikinci programlar. Bunları hiç yazmamak,
   "kaydım gitmiş" sanılmasına yol açıyordu (yandal kodu bozulunca tam da
   bu oldu). Planı yok diye SEÇİM yok sayılmıyor. */
const SECONDS_YOK = () => DATA.secondsMissing || [];
const ikinciYazi = () =>
  [...SECONDS().map(x => ` · <b>${esc(x.program)}</b> ${esc(x.label)}`),
   ...SECONDS_YOK().map(x => ` · <b>${esc(x.program)}</b> ${esc(x.label)}` +
       ` <span class="uyari" title="Bu programın planı katalogda bulunamadı;` +
       ` ilerleme ve taban hesaplanamıyor.">planı yok</span>`)].join("");
function renderHeader(){
  LBL = DATA.secondLabel || "ÇAP";
  const ikili = SECONDS().length > 1;
  $("#eyebrow").textContent = [DATA.anadal,
      ...SECONDS().map(s => `${s.program} ${s.label}`)].filter(Boolean).join(" + ")
    + (donemYazi() ? ` · ${donemYazi()}` : "");
  if(DATA.termLabel) $("#eyebrow").title = "OBS dönem kodu: " + DATA.term;
  /* ★ Başlıkta program adı YOK (kullanıcı isteği 23.08.2026): araç ÇAP'a
     özel değil, yandalda ve ÇAP'sız kullanımda da aynı araç. Hangi programa
     baktığın zaten üstteki eyebrow'da yazıyor.
     ⚠️ Başlık artık BURADAN YAZILMIYOR — şablonda duruyor ve tek kaynağı
     `ui.AD_*` sabitleri. JS'ten ezmek ikinci bir kaynak demekti. */
  /* ★ C6 — başlık artık anadalı da kapsıyor. */
  $("#blockTitle").textContent = "Bu dersleri neden alamıyorsun";
  $("#tierTitle").textContent = ikili ? "Kademeler" : `${LBL} kademeleri`;
  $("#gen").textContent = veriTarihi();
  /* ★ Faz 54: sitede "bu dosya" YOK — notlar tarayıcıda. Yanlış yeri
     söylemek, neyin nerede durduğunu (ve neyin kaybolabileceğini) gizler. */
  $("#gizlilik").textContent = (DATA.load && DATA.load.noTranscript) ? ""
    : siteMi() ? "Notların yalnız bu tarayıcıda — tarayıcı verisini silersen gider; yedeğini al (Ayar)."
    : "Bu dosya notlarını içerir — paylaşma.";
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
          /* ★ Kaynağı da yaz (UX 27.08.2026): kullanıcı 30 ayarlayıp
             başlıkta 40 görünce "bozuk mu" diyor. Yönetmelik GNO'ya göre
             tavanı yükseltiyor (MADDE 17) ve bunu söylemeden göstermek,
             ayarıyla çelişen bir sayıyı açıklamasız bırakıyordu. Dönem
             etiketindeki "(beyan)/(tahmin)" ile aynı desen. */
          : `dönem yükü sınırı ${DATA.maxLoad} ${DATA.unitLabel}`
            + ({yönetmelik: " (yönetmelik)", ayar: "", çağrı: ""}[
                 (DATA.load || {}).limitSource] || ""),
        DATA.donem ? `${DATA.donem}. dönem (${DATA.donemSource})` : "",
      ].filter(Boolean).join(" · ");
}

/* ---------- verinin yaşı (Faz 25/D3) ----------
   ★ "0/240" üç gün önceki veriyse yanıltıcı. Alt bilgide bir kez yazmak
   yetmiyordu; kontenjana bakılan HER yerde tarih var (doluluk çubuğunun
   `title`'ı, kayıt kontrolü) ve veri bayatladıysa üstte uyarı çıkıyor. */
/** ★★ FAZ 54 — Kontenjanın AİT OLDUĞU an: son tazeleme. Dört yer (alt bilgi,
    doluluk çubuğu, kayıt kontrolü, arz notu) `generatedAt`ı — sayfanın
    ÜRETİLDİĞİ anı — yazıyordu. Sitede sayfa her açılışta tarayıcıda
    üretiliyor: 23 gün önceki kontenjan "bugün 20:56 itibarıyla" görünüyordu,
    aynı sayfanın başı "23 gün önce tazelendi" derken. Faz 25/D3 bunu tepede
    düzeltmişti; bu dört yer eski damgada kalmıştı (doluluk çubuğunun yorumu
    bile "yaşsız bir gerçek gibi durmasın" diyordu). */
/** Statik site mi (tarayıcıda Python)? Tazeleme yok, veri tarayıcıda. */
function siteMi(){
  return LIVE && DATA.canRefresh === false;
}
function veriTarihi(){
  const A = DATA.dataAge;
  return A && A.raw ? A.raw : "tarihi bilinmeyen bir tazeleme";
}
function veriYasiMetni(){
  const A = DATA.dataAge;
  if(!A) return "veri tazeleme tarihi bilinmiyor";
  if(A.days === null) return `veri ${A.raw}`;
  const t = A.calendarDays;
  const g = t === 0 ? "bugün" : (t === 1 ? "dün" : `${t} gün önce`);
  return `şube/kontenjan verisi ${g} tazelendi (${A.raw})`;
}

/* ---------- kısa bildirim ----------
   ★ Bölüm gizliyken sonucun yazılacağı bir yer gerekiyordu. `alert` iki
   sebeple olmaz: kip bir pencere açıp sayfayı kilitler, ve tarayıcı
   otomasyonunda tüm olayları durdurur. `aria-live` ile okuyucuya da gidiyor. */
let _bildirimZaman = null;
/* ★★ FAZ 51 — CANLI BÖLGE AÇILIŞTA VAR OLMALI.
   Ölçüldü: sayfada `aria-live` taşıyan HİÇBİR öğe yoktu; bölge ilk
   bildirimle birlikte, İÇİ DOLU olarak DOM'a giriyordu. Ekran okuyucular
   canlı bölgeyi önceden tanıyıp sonraki DEĞİŞİKLİĞİ duyuruyor; hazır
   metinle sonradan eklenen bir bölge çoğu okuyucuda hiç okunmuyor. Yani
   "kaydedildi", "tazeleme bu ortamda yapılamıyor" gibi bütün kısa
   bildirimler görme engelli kullanıcıya SESSİZ geçiyordu. */
function bildirimBolgesi(){
  let el = $("#bildirim");
  if(!el){
    el = document.createElement("div");
    el.id = "bildirim"; el.className = "bildirim";
    el.setAttribute("role", "status"); el.setAttribute("aria-live", "polite");
    document.body.appendChild(el);
  }
  return el;
}

function say2(text){
  const el = bildirimBolgesi();
  el.textContent = text;
  el.classList.add("acik");
  clearTimeout(_bildirimZaman);
  _bildirimZaman = setTimeout(() => el.classList.remove("acik"), 6000);
}

/* ★★ Faz 38 — planladığın dönemin notları ÇOKTAN AÇIKLANMIŞ.
   Takvimden tahmin etmiyoruz: OBS o dönem için dağılım yayınlamışsa dönem
   bitmiş demektir. `settings.term` büyük olasılıkla bir yıl geride.
   ⚠️ Sessizce düzeltmiyoruz — hangi dönemi planladığı kullanıcının beyanı;
   biz yalnız çelişkiyi gösteriyoruz. */
function gecmisDonemUyarisi(){
  const n = DATA.termGraded || 0;
  if(!n) return "";
  return ` · <b class="stale" title="Bu dönem için ${n} dersin not dağılımı
    yayınlanmış; yani dönem tamamlanmış görünüyor.">⚠ ${
    esc(DATA.termLabel || DATA.term)} bitmiş görünüyor</b>`;
}

function renderVeriYasi(){
  const el = $("#veriYasi");
  if(!el) return;
  /* ★ D3'ün ikinci yarısı: "Veriyi tazele" düğmesi YALNIZCA "Ne değişti"
     bölümünün içindeydi. O bölüm artık karşılaştırılacak bir şey yoksa
     gizleniyor — düğme de onunla birlikte kaybolurdu. Tazeleme, verinin
     yaşını yazan satırın yanına taşındı: soruyu soran cümlenin yanında
     cevabı veren düğme. */
  /* ⚠️ Metin ve düğme AYRI parça (Faz 46): tek metin düğümü içine gömülü
     bir düğme dar ekranda cümlenin ortasında kalıyordu. */
  /* ★ Faz 54: sitede tazeleme YOK (katalog siteyle yayınlanıyor). Eskiden
     düğme duruyordu ve basınca "bu ortamda yapılamıyor" diyordu — hiç
     çalışmayacak bir düğme. Yerine neden eski olduğu yazıyor. */
  el.innerHTML = `<span class="veriyazi">${esc(veriYasiMetni())}</span>`
    + (siteMi() ? `<span class="veriyazi sitenot">Site dönem başında güncelleniyor —
         güncel kontenjan OBS'de.</span>`
       : LIVE ? `<button class="ghost mini" id="veriTazele">tazele</button>` : "")
    + gecmisDonemUyarisi();
  el.classList.toggle("stale", !!(DATA.dataAge && DATA.dataAge.stale));
  const b = $("#veriTazele");
  if(b) b.addEventListener("click", () => {
    const asil = $("#refreshBtn");
    if(asil) asil.click();
    else say2("tazeleme bu ortamda yapılamıyor");
  });
}

/* ---------- bozuk ayar dosyası (Faz 25/D1) ----------
   ⚠️ Sessizce varsayılana düşmek, kullanıcıya başka bir bölümün raporunu
   doğru sandırırdı. Sayfa AÇILIYOR ama ne olduğunu ve nerede olduğunu
   tepede yazıyor. */
function renderAyarHatasi(){
  const el = $("#ayarHatasi");
  if(!el) return;
  const hata = DATA.settingsError;
  const uyari = DATA.settingsWarnings || [];
  el.hidden = !hata && !uyari.length;
  el.classList.toggle("yumusak", !hata && uyari.length > 0);
  if(hata){
    el.innerHTML = `<b>Ayar dosyan okunamadı — varsayılanlarla açıldı.</b>
      <div class="mono" style="margin-top:4px">${esc(hata)}</div>
      <div style="margin-top:6px">Seçtiğin bölüm ve dönem <b>kullanılmıyor</b>.
        Dosyayı düzelt ya da aşağıdan yeniden seç.</div>`;
    return;
  }
  if(!uyari.length) return;
  /* ★★ FAZ 53 — dosya OKUNUYOR ama bazı satırlar yanlış tabloda duruyor ve
     hiçbir şey yapmıyor. Kullanıcının kendi dosyasında ölçüldü:
     `cap_baslangic_yariyili` `[regulation]` altındaydı — yorum "3 ya da 5
     yaz" diyor, yazılsa yarıyıl tabanı UYGULANMIYOR ve kimse söylemiyordu.
     Fatal değil (sayfa doğru çalışıyor), o yüzden kırmızı değil. */
  const yer = (u) => u.tablo ? `[${esc(u.tablo)}]` : "ilk tablo başlığından önce";
  el.innerHTML = `<b>Ayar dosyanda okunmayan ${uyari.length === 1 ? "bir satır"
      : uyari.length + " satır"} var.</b>
    <ul style="margin:6px 0 0;padding-left:18px">${uyari.map(u => `<li>
      <span class="mono">${esc(u.anahtar)}</span> ${yer(u)} altında — ${u.golge
        ? `araç <span class="mono">[student]</span>'taki değeri kullanıyor, bu
           satır <b>yalnız yanıltıcı bir kopya</b>`
        : `araç onu <b>okumuyor</b>, varsayılan değer geçerli`}.</li>`).join("")}</ul>
    <div style="margin-top:6px">Düzeltmek için bu satırları
      <span class="mono">config/settings.toml</span> içinde
      <span class="mono">[student]</span> başlığının altına taşı (ya da sil).</div>`;
}

$("#theme").addEventListener("click", () => {
  const cur = document.documentElement.getAttribute("data-theme");
  const dark = cur ? cur === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  const yeni = dark ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", yeni);
  localStorage_set("tema", yeni);      // ★ sonraki açılışta bu tema açılsın
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

/* ★★ FAZ 51 — HATA GÖRME ENGELLİ KULLANICIYA DA ULAŞSIN.
   Ölçüldü: bir uç 500 dönünce hata GÖRÜNÜYOR — ama yalnız düğmenin
   ETİKETİ olarak ("hata: deneme"). Sekiz çağrı yerinin hepsi böyle. İki
   sorun: (a) hiçbiri canlı bölgeye düşmüyor, yani ekran okuyucu hiçbir şey
   söylemiyor; (b) düğmenin erişilebilir ADI hatayla değişiyor — geri
   dönen kullanıcı "hata: …" adlı bir düğme buluyor, ne yaptığını bilmiyor.
   ⚠️ Görsel biçim DEĞİŞTİRİLMEDİ: hatayı eylemin durduğu yerde göstermek
   doğru ve yerleşik. Eklenen tek şey, aynı cümlenin canlı bölgeye de
   düşmesi ve düğmenin asıl adının `aria-label`da korunması. */
function hataBildir(btn, err){
  const mesaj = (err && err.message) || String(err || "hata");
  if(btn){
    if(!btn.dataset.asilAd) btn.dataset.asilAd = (btn.textContent || "").trim();
    btn.disabled = false;
    btn.textContent = "hata: " + mesaj;
    btn.title = mesaj;
    /* Erişilebilir ad eski eylemi söylemeye devam ediyor. */
    if(btn.dataset.asilAd)
      btn.setAttribute("aria-label", btn.dataset.asilAd + " — hata: " + mesaj);
  }
  say2("hata: " + mesaj);
  return mesaj;
}

/** Sunucudan gelen yeni durumu uygula — sayfa yenilenmeden.

    ★★ FAZ 53 — `boot()` İLK AÇILIŞ İÇİN yazılmıştı ve her durum
    değişikliğinde baştan koşuyordu: kip 0'a dönüyor, KAYDEDİLEN PROGRAM
    yeniden yükleniyor, paylaşılan bağlantı (#crn=…) yeniden uygulanıyordu.
    Ölçüldü (gerçek veri): tam kipte (tüm adaylar) bir dersi kilitleyen kullanıcı
    "5. dönem + alttan"a atılıyor, ızgarada kilitli öneri değil kaydettiği
    eski program duruyor ve şerit "bu kipte bağlamıyor · ekranda CRN 10123"
    diyordu — kilit çalışıyordu ama ekran bozuk gösteriyordu.

    Artık kip KORUNUYOR (anahtarıyla). Öneriyi değiştiren işlerden sonra
    (kilit, meşgul saat, tavan, ayar) o kipin 1. önerisi gösteriliyor;
    öneriyi değiştirmeyen işlerde (`koru`: izleme, kaydetme) ızgara ve sekme
    olduğu gibi kalıyor. Kaydedilen programı açılışta yüklemek ve bağlantıyı
    uygulamak yalnız İLK açılışın işi. */
function applyState(next, secenek){
  const onceki = {kip: (MODES[mode] || {}).key, active, sel: sel.slice(),
                  koru: !!(secenek && secenek.koru),
                  varsayilan: !!(secenek && secenek.varsayilanKip)};
  Object.assign(DATA, next);
  LIVE = !!DATA.live;
  SETUP = DATA.setup || null;
  MODES.length = 0;
  MODES.push(...((DATA.modes && DATA.modes.length) ? DATA.modes
    : [{key:"all", label:"__AD_KISA__", note:"",
        candidates: DATA.candidates, schedules: DATA.schedules}]));
  /* ⚠️⚠️ FAZ 54 — Sitede İLK durum da buradan geliyor: kabuk boş veriyle
     çiziliyor, `boot()` hiç koşmuyor, sitenin kancası doğrudan bu işlev.
     Faz 53 bunu "durum değişikliği" sandı: boş kabuğun tek kipi ("all")
     korunuyor, kaydedilen program YÜKLENMİYOR ve paylaşılan bağlantı
     (#crn=…) HİÇ UYGULANMIYORDU. İlk kez koşan boot, ilk açılıştır. */
  boot(_acildi ? onceki : undefined);
}
/** `boot()` en az bir kez tamamlandı mı (Faz 54 — bkz. applyState). */
let _acildi = false;

function setupBar(){
  const s = SETUP;
  const who = s
    ? `<b>${esc(s.anadalProgram)}</b> anadal`
      + ((SECONDS().length || SECONDS_YOK().length)
         ? ikinciYazi() : " · ikinci program yok")
      + ` · <b>${DATA.donem || "?"}. dönem</b> (${esc(DATA.donemSource)})`
      + ` · <b>${s.transcript.length}</b> ders girilmiş`
    : `<b>${esc(DATA.anadal)}</b>` + ikinciYazi()
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
      <button class="ghost" data-setup="dersler">Geçtiğin dersler</button>
      <button class="ghost" data-setup="tercih">Tercihler${
        tercihSayisi() ? ` <span class="chip">${tercihSayisi()}</span>` : ""}</button>`
    : `<span class="ro">Düzenlemek için <span class="mono">make app</span></span>
       <button class="ghost" disabled>Program</button>
       <button class="ghost" disabled>Dönem</button>
       <button class="ghost" disabled>Plandan işaretle</button>
       <button class="ghost" disabled>Geçtiğin dersler</button>
       <button class="ghost" disabled>Tercihler</button>`}
    ${veriKutusu()}`;
  $("#setupbar").querySelectorAll("[data-setup]").forEach(b =>
    b.addEventListener("click", () => ({program: programDialog, donem: termDialog,
                                        plan: checklistDialog, tercih: tercihDialog,
                                        dersler: courseDialogSetup})[b.dataset.setup]()));
  wireVeriKutusu();
}

/* ★★ FAZ 54 — SİTEDE VERİNİN YEDEĞİ. Transkript, bölüm, kilitler YALNIZ bu
   tarayıcının deposunda. Tarayıcı verisini silmek, başka cihaza geçmek ya
   da Safari'nin 7 gün girilmeyen sitenin deposunu temizlemesi hepsini
   götürüyordu ve geri almanın yolu yoktu. Yedek bir dosya; indirmek ve
   yüklemek tamamen tarayıcıda. Yerel uygulamada (`make app`) veri zaten
   `data/` altında ve yedekleniyor — orada bu kutu yok. */
function veriKutusu(){
  if(!siteMi() || !window.__ITUCAP_YEDEK__) return "";
  const n = SETUP ? SETUP.transcript.length : 0;
  return `<div class="verikutusu" id="veriKutusu">
    <b>Verin yalnız bu tarayıcıda.</b> Bölümün, ${n ? `<b>${n}</b> dersin` : "derslerin"},
    kilitlerin ve kaydettiğin program bu tarayıcının deposunda — hiçbir sunucuya
    gitmiyor. Tarayıcı verisini silersen, başka cihaza geçersen ya da tarayıcı
    yer açmak için temizlerse <b>gider</b>.
    <div class="veridugmeler">
      <button class="ghost" id="yedekIndir">Yedeğini indir</button>
      <button class="ghost" id="yedekSec">Yedekten yükle…</button>
    </div>
    <div class="verikalici" id="veriKalici"></div>
    <div class="veriyedek" id="veriYedek" role="status" aria-live="polite"></div>
  </div>`;
}

/** Yedek dosyasını seç → doğrula → NE OLACAĞINI söyle → onaylanırsa yükle.
    İki yerden çağrılıyor: Ayar'daki veri kutusu ve (yeni cihazda) ilk kart. */
function yedekDosyaSec(durum){
  const Y = window.__ITUCAP_YEDEK__;
  if(!Y || !durum) return;
  const inp = document.createElement("input");
  inp.type = "file"; inp.accept = "application/json,.json"; inp.hidden = true;
  document.body.appendChild(inp);
  inp.addEventListener("change", async () => {
    const dosya = inp.files[0];
    inp.remove();
    if(!dosya) return;
    let sonuc;
    try{ sonuc = await Y.oku(dosya); }
    catch(e){
      durum.innerHTML = `<span style="color:var(--danger)">Yüklenmedi: ${esc(e.message)}.</span>`;
      return;
    }
    /* ⚠️ Uygulamadan ÖNCE ne olacağı söyleniyor: yedek şimdiki verinin
       YERİNE geçiyor. Önce şimdikini indirmek tek tık. */
    const O = sonuc.ozet, simdi = SETUP ? SETUP.transcript.length : 0;
    durum.innerHTML = `<b>Bu yedek şimdiki verinin yerine geçecek.</b>
      Yedek: ${esc((O.tarih || "").slice(0, 10))} · ${esc(O.anadal || "bölüm yok")} ·
      <b>${Number(O.ders) || 0}</b> ders. Şimdi: ${esc((SETUP && SETUP.anadalProgram) || "bölüm yok")} ·
      <b>${simdi}</b> ders.
      <div class="veridugmeler">
        ${simdi || (SETUP && SETUP.anadalProgram)
          ? `<button class="ghost" data-yedek="once">Önce şimdikini indir</button>` : ""}
        <button class="ghost primary" data-yedek="uygula">Yedeği yükle</button>
        <button class="ghost" data-yedek="vazgec">Vazgeç</button></div>`;
    const b = (k) => durum.querySelector(`[data-yedek="${k}"]`);
    if(b("once")) b("once").addEventListener("click", () => Y.indir());
    b("vazgec").addEventListener("click", () => { durum.textContent = ""; });
    b("uygula").addEventListener("click", async () => {
      b("uygula").disabled = true; b("uygula").textContent = "yükleniyor…";
      try{ await Y.uygula(sonuc.yedek); }
      catch(e){ hataBildir(b("uygula"), e); }
    });
  });
  inp.click();
}

async function wireVeriKutusu(){
  const Y = window.__ITUCAP_YEDEK__;
  if(!$("#veriKutusu") || !Y) return;
  const durum = $("#veriYedek");
  $("#yedekIndir").addEventListener("click", async () => {
    try{
      const n = await Y.indir();
      durum.textContent = `İndirildi (${n} dosya). Dosyayı güvenli bir yere koy —
        içinde notların var.`;
    }catch(e){ hataBildir($("#yedekIndir"), e); }
  });
  $("#yedekSec").addEventListener("click", () => yedekDosyaSec(durum));
  /* Kalıcı depolama: tarayıcı SORULMADAN temizleyebilir mi? Soru tarayıcıya
     yalnız DÜĞMEYLE gidiyor — Firefox izin penceresi açıyor, habersiz
     açılması şaşırtırdı. */
  const k = $("#veriKalici");
  const yaz = (v) => {
    k.innerHTML = v === true
      ? "✓ Tarayıcı bu siteye <b>kalıcı depolama</b> verdi: yer açmak için verini silmez."
      : v === false
        ? `⚠️ Tarayıcı yer açmak için bu sitenin verisini <b>silebilir</b>.
           <button class="ghost mini" id="kaliciIste">Kalıcı saklamasını iste</button>`
        : "Bu tarayıcı kalıcı depolamayı desteklemiyor — yedeğini al.";
    const b = $("#kaliciIste");
    if(b) b.addEventListener("click", async () => {
      const r = await Y.kaliciIste();
      yaz(r);
      if(r === false) say2("tarayıcı kabul etmedi — yedeğini indir");
    });
  };
  try{ yaz(await Y.kalici()); }catch(e){ yaz(null); }
}

/** Kaç tercih etkin — çubukta rozet olarak. Sıfırsa rozet YOK: "0" yazmak
    kullanıcıya bir şey söylemiyor, yer kaplıyor. */
function tercihSayisi(){
  const P = (SETUP && SETUP.prefs) || {};
  return (P.enErken ? 1 : 0) + ((P.bosGunler || []).length ? 1 : 0)
    + (P.kampus ? 1 : 0) + (P.cevrimici ? 1 : 0)
    + ((P.istenenHocalar || []).length ? 1 : 0)
    + ((P.istenmeyenHocalar || []).length ? 1 : 0);
}

function openSetup(html, wire){
  SETUP_KIRLI = false;                 /* Faz 55 — bkz. pencereDisinaTiklama */
  $("#setupBody").innerHTML = html + `
    <div class="dlgactions">
      <span class="msg" id="setupMsg"></span>
      <button class="ghost" data-close>Kapat</button>
      <button class="ghost primary" id="setupSave">Kaydet</button>
    </div>`;
  $("#setupBody").querySelectorAll("[data-close]").forEach(b =>
    b.addEventListener("click", () => $("#setup").close()));
  wire();
  pencereAdiVer($("#setup"), $("#setupBody"));      /* Faz 51 */
  $("#setup").showModal();
}

/** Pencerenin adını İLK BAŞLIĞINDAN türetir (Faz 51).
    Üç ayrı pencere açıcı var; üçü de buradan geçiyor ki biri unutulmasın. */
function pencereAdiVer(dlg, govde){
  if(!dlg) return;
  const bas = (govde || dlg).querySelector("h1,h2,h3");
  if(bas){
    if(!bas.id) bas.id = "dlgbaslik-" + (dlg.id || "x");
    dlg.setAttribute("aria-labelledby", bas.id);
  }else{
    dlg.removeAttribute("aria-labelledby");
  }
}

function say(text, bad){
  const el = $("#setupMsg");
  if(el){ el.textContent = text; el.className = "msg" + (bad ? " bad" : ""); }
}

/* ★ Düğmeyi MEŞGUL göster: dönen halka + metin, ve tıklamayı kilitle. Geri
   döndüren işlev veriyor — eski içeriği aynen geri koyuyor. "Kaydediliyor
   olduğu belli olsun" (kullanıcı 28.08.2026); yalnız soluklaştırmak yetmiyordu. */
function dugmeMesgul(btn, metin){
  if(!btn) return () => {};
  const eski = btn.innerHTML;
  btn.disabled = true;
  btn.classList.add("mesgul");
  btn.innerHTML = `<span class="spin" aria-hidden="true"></span>${esc(metin)}`;
  return () => { btn.disabled = false; btn.classList.remove("mesgul"); btn.innerHTML = eski; };
}

/* ★ Meşgul göstergesini tarayıcı BOYASIN diye bir kare bekle. Statik sitede
   (Pyodide) kaydetme ana iş parçacığını BLOKLUYOR — halkayı boyamadan hesaba
   girersek dönme ancak 7 sn sonra görünür, kullanıcı "bastım mı, başladı mı?"
   diye takılırdı (kullanıcı raporu 31.08.2026). İki rAF: biri stil değişsin,
   biri ekrana çizilsin. Yerel (fetch) sürümde bir karelik gecikme fark etmez. */
const bekleBoyansin = () => new Promise(r =>
  requestAnimationFrame(() => requestAnimationFrame(r)));

/* ★ Faz 54: `secenek` applyState'e gidiyor. Kurulum işleri (program, dönem,
   transkript) DURUMU değiştiriyor: varsayılan kipe dönülüyor — dönem ilk kez
   seçilince "N. dönem + alttan" kipi açılmalı (ilk kartın sözü bu). Tercih ve
   meşgul saat yalnız öneriyi değiştiriyor: kip korunuyor. */
async function save(fn, secenek = {varsayilanKip: true}){
  const btn = $("#setupSave");
  const geri = dugmeMesgul(btn, "Kaydediliyor…");
  say("kaydediliyor…");
  await bekleBoyansin();          // ★ halka BOYANSIN, sonra bloklayan hesap
  /* ★ ÖLÇÜLDÜ: ÇAP + yandal birlikte kaydedilince sunucu her şeyi baştan
     hesaplıyor ve bu 7 saniye sürüyor. Ekranda tek satır "kaydediliyor…"
     yazıp durunca kullanıcı takıldı sanıp pencereyi kapatıyor ya da
     tekrar tıklıyordu. Üç saniyeyi geçen bekleme ARTIK KENDİNİ SÖYLÜYOR;
     sayacı uydurmuyoruz, geçen gerçek süreyi yazıyoruz. */
  const t0 = Date.now();
  const sayac = setInterval(() => {
    const sn = Math.round((Date.now() - t0) / 1000);
    if(sn >= 3) say(`kaydediliyor… ${sn} sn — plan yeniden hesaplanıyor, `
                    + `pencereyi kapatma`);
  }, 1000);
  try{
    applyState(await fn(), secenek);
    say("kaydedildi ✓");
    setTimeout(() => $("#setup").close(), 550);
  }catch(err){
    say(err.message, true);
  }finally{
    clearInterval(sayac);
    geri();
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
  /* ⚠️ Adı koduyla AYNI olan kayıt "ad" sayılmıyor: sunucu eskiden
     bilinmeyen ada kodu koyuyordu ve liste "ECN — ECN" yazıyordu. */
  s.programs.forEach(p => {
    if(p.name && p.name.toUpperCase() !== p.code.toUpperCase() && !adi[p.code])
      adi[p.code] = p.name;
  });
  const codes = [...new Set(s.programs.filter(p => p.plan_type === "lisans")
                                      .map(p => p.code))].sort();
  /* ★ Kod tek başına bir tanım değil: "AIN" ne demek olduğunu kimse bilmiyor.
     Ad da yazınca yerleşik `select` yazarak-arama'sı hem koda hem ada çalışıyor. */
  /* Adı bilinmiyorsa SÖYLÜYORUZ. Kodu tek başına bırakmak, kullanıcıya
     "bu kod ne demek" sorusunu cevapsız bırakırdı; kodu ad diye yazmak
     ise yanlış bilgi olurdu. */
  const label = (c) => adi[c] ? `${c} — ${adi[c]}` : `${c} — (adı katalogda yok)`;
  const opts = (sel) =>
    /* ★ Boş seçim GERÇEK bir seçenek: yoksa liste alfabetik ilk bölümde
       (AIN) açılıyor ve dokunmadan Kaydet'e basan herkes o bölüme yazılıyor. */
    (sel ? "" : `<option value="" selected>— bölümünü seç —</option>`) +
    codes.map(c => `<option value="${esc(c)}"${c === sel ? " selected" : ""}
      >${esc(label(c))}</option>`).join("");
  const kindsOf = (k) => k === "ikisi" ? ["cap", "yandal"] : (k === "yok" ? [] : [k]);
  /* ★★ TÜRETİLEN KODLAR ARTIK KUTUDA DEĞİL (kullanıcı isteği 27.08.2026):
     *"alabileceğim ders kodlarını anadal çap ve yandala göre otomatik ekler
     misin, orada sadece ekstra program türleri girilebilsin"*.

     Sunucu `programCodes` alanında yalnız EKSTRALARI gönderiyor;
     `derivedPrograms` seçimlerden türetilenler. Kutu artık bölüm
     değiştikçe eskiyen bir kopya taşımıyor — eskisi tam da bu yüzden
     tehlikeliydi: anadalını değiştiren kişinin ders havuzu eski koda göre
     süzülmeye devam ediyordu ve ekranda hiçbir yerde yazmıyordu. */
  const ozelKod = (s.programCodes || []).length > 0;
  /* ★ C8 — boş seçenek ÖNDE. Kutu ilk bölümde (ARC — Mimarlık KKTC) açılıp
     "Kaydet"e basan kişiye tamamen yanlış ama GEÇERLİ GÖRÜNEN bir kurulum
     üretiyordu. */
  const secondOpts = (k, sel) => {
    const liste = (s.secondPrograms || {})[k] || [];
    if(!liste.length) return `<option value="">bu tipte plan yok — make all-plans</option>`;
    return (sel ? "" : `<option value="" selected>— ${KIND_LABEL[k]} bölümü seç —</option>`)
      + liste.map(p => `<option value="${esc(p.code)}"${p.code === sel ? " selected" : ""}
        >${esc(p.code)} — ${esc(p.name || p.code)}</option>`).join("");
  };
  openSetup(`
    <div class="eyebrow">Kurulum</div>
    <h2 style="margin-bottom:4px">Program seçimi</h2>
    <p class="modenote" style="margin:2px 0 4px">Bir tek anadal yeter.
      <b>Çift anadal ya da yandal yapmıyorsan “Yok” bırak</b> — araç normal
      ders seçim aracı olarak çalışır.</p>
    <div class="grid2">
      <label class="field"><span>Anadal <b style="color:var(--anadal)">*</b></span>
        <!-- ★ C7 — 127 satırlık kutuda arama yoktu ve liste KODA göre
             sıralıydı: öğrenci "Bilgisayar" diye arıyor, liste
             "AIN, ARC, BES…" diye gidiyordu. -->
        <input type="search" id="fAnadalQ" autocomplete="off"
          placeholder="bölüm ara — “bilgisayar”, “BLG”, “makina”…"
          style="margin-bottom:6px">
        <select id="fAnadal" size="1">${opts(s.anadalProgram)}</select>
        <span class="hint" id="fAnadalSayi">Listede
          <b class="mono">${codes.length}</b> bölüm var.
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
          <span class="hint" id="fPlanNot-${k}">Planı boş bırakırsan en güncel OBS planı seçilir.</span></label>
      </div>`).join("")}
    <details class="adv"${ozelKod ? " open" : ""}>
      <summary>Gelişmiş</summary>
      <div class="field"><span>Kayıt yapabildiğin program kodları</span>
        <div class="kodlar" id="fTuretilen"></div>
        <span class="hint">Bir şubenin "Dersi Alabilen Programlar" listesinde
          bunlardan biri varsa dersi alabilirsin. Yukarıdaki seçimlerden
          <b>otomatik</b> geliyor — değişince kendiliğinden güncelleniyor.</span>
      </div>
      <div class="field" id="fOneriKutu" hidden><span>Bunlar da eklenebilir</span>
        <div class="kodlar" id="fOneri"></div>
        <!-- ⚠️ Otomatik EKLENMİYOR: "bu kodla da kayıt yapabilirsin" bir
             iddia ve yanlışsa alamayacağın dersi alabilir gösterir. -->
        <span class="hint">Aynı bölümün öbür dil sürümü. Kayıt yapabiliyorsan
          ekle — <b>emin değilsen ekleme</b>, aracın alamayacağın dersi
          alabilir göstermesine yol açar.</span>
      </div>
      <label class="field"><span>Ekstra program kodları</span>
        <input type="text" id="fCodes" value="${esc((s.programCodes || []).join(", "))}"
          placeholder="genelde boş kalır">
        <span class="hint">Yukarıdakilere <b>ek olarak</b> kayıt yapabildiğin
          kodlar. Anadal/ÇAP/yandal kodlarını buraya yazmana gerek yok.
          Virgülle ayır.</span></label>
    </details>`, () => {
    let kind = s.secondKind;
    /* ★★ FAZ 54 — PLANIN KİMİN İÇİN OLDUĞU YAZIYOR. ÇAP planları (anadal,
       hedef) çiftine tanımlı: BLG'nin 38 planının biri Harita, biri İnşaat
       öğrencisi için. Liste hepsini tek yığın halinde, "en güncel" önde
       veriyordu; hangisinin SENİN planın olduğu yazmıyordu. Motor otomatik
       seçimde anadala uyanı arıyor (`plans.ikinci_plan`) — pencere de aynı
       ayrımı gösteriyor. Anadal değişince liste de değişiyor. */
    /* `normalize.base_program_code` ile AYNI kural (testte karşılaştırılıyor):
       "HTAE" → "HTA". Plan bağları bazen dilsiz koda yazılı. */
    const tabanKod = (c) => (c && c.length > 2 && c.endsWith("E")) ? c.slice(0, -1) : c;
    const planUygunMu = (p, an) => {
      const h = (p.hosts || "").split(" ");
      return !!an && (h.includes(an) || h.includes(tabanKod(an)));
    };
    const fillPlans = (k) => {
      const code = $("#fProg-" + k).value;
      const an = $("#fAnadal").value;
      const secili = ((s.secondChoice || {})[k] || {}).planId;
      const list = s.plans.filter(p => p.plan_type === k && p.program_code === code);
      const uygun = list.filter(p => planUygunMu(p, an));
      const diger = list.filter(p => !planUygunMu(p, an));
      const secenek = (p) => `<option value="${p.id}"${p.id === secili ? " selected" : ""}
          >${p.id} · ${p.slots} slot · ${esc((p.title || "").slice(0, 54))}</option>`;
      const grup = (ad, ps) => ps.length
        ? `<optgroup label="${esc(ad)}">${ps.map(secenek).join("")}</optgroup>` : "";
      $("#fPlan-" + k).innerHTML =
        `<option value="">${an && uygun.length ? `otomatik — ${esc(an)} için en güncel`
                                                 : "otomatik (en güncel)"}</option>`
        + (an ? grup(`${an} öğrencileri için (${uygun.length})`, uygun)
                + grup(`başka bölümlerin planları (${diger.length})`, diger)
              : list.map(secenek).join(""));
      if(!list.length) $("#fPlan-" + k).innerHTML +=
        `<option disabled>bu bölümde ${KIND_LABEL[k]} planı yok</option>`;
      const not = $("#fPlanNot-" + k);
      if(not) not.innerHTML = !code || !list.length ? "Planı boş bırakırsan en güncel OBS planı seçilir."
        : !an ? "Önce anadalını seç — planlar anadala göre ayrılıyor."
        : uygun.length ? `<b>${uygun.length}</b> plan ${esc(an)} öğrencileri için ilan edilmiş;
            boş bırakırsan en günceli seçilir.`
        : `⚠️ Bu bölümün ${KIND_LABEL[k]} planlarının hiçbiri ${esc(an)} için ilan
            edilmemiş. Otomatik seçim en güncel planı alır — <b>senin planın
            olmayabilir</b>, OBS'den doğrula.`;
    };
    /* ★★ Türetilen kodlar CANLI: kullanıcı bölümü değiştirince rozetler
       anında değişiyor. Kaydedilmiş değeri göstermek, "otomatik" sözünü
       kaydetmeden önce tutmamak olurdu — ve tam da eski hatanın kaynağıydı:
       kutudaki kod, ekrandaki seçimle uyuşmuyordu. */
    const turetilenKodlar = () => {
      const acik = kindsOf(kind);
      return [...new Set([$("#fAnadal").value,
        ...acik.map(k => $("#fProg-" + k) && $("#fProg-" + k).value)]
        .filter(Boolean).map(x => x.toUpperCase()))];
    };
    const cizKodlar = () => {
      const t = turetilenKodlar();
      $("#fTuretilen").innerHTML = t.length
        ? t.map(c => `<span class="kod" title="seçimlerinden geliyor">${esc(c)}</span>`).join("")
        : `<span class="hint">bölüm seçince burada görünecek</span>`;
      /* Öneri, ARTIK SEÇİLİ OLANA göre süzülüyor: kullanıcı ekstra kutusuna
         elle yazdıysa ya da bölümü değiştirdiyse öneri de değişmeli. */
      const yazili = new Set(($("#fCodes").value || "").split(/[,\s]+/)
        .filter(Boolean).map(x => x.toUpperCase()));
      const esler = s.languageSiblings || {};
      const oneri = t.map(k => esler[k] && {...esler[k], from: k})
        .filter(o => o && !t.includes(o.code) && !yazili.has(o.code))
        .filter((o, i, a) => a.findIndex(x => x.code === o.code) === i);
      $("#fOneriKutu").hidden = !oneri.length;
      $("#fOneri").innerHTML = oneri.map(o =>
        `<button type="button" class="kod ekle" data-kod="${esc(o.code)}"
           title="${esc(o.code)} koduna açık ${o.sections} şube var">
           + ${esc(o.code)}</button>`).join("");
      $("#fOneri").querySelectorAll("[data-kod]").forEach(b =>
        b.addEventListener("click", () => {
          const v = ($("#fCodes").value || "").split(/[,\s]+/).filter(Boolean);
          v.push(b.dataset.kod);
          $("#fCodes").value = [...new Set(v)].join(", ");
          cizKodlar();
        }));
    };
    const sync = () => {
      const acik = kindsOf(kind);
      ["cap","yandal"].forEach(k => {
        $("#fWrap-" + k).hidden = !acik.includes(k);
        if(acik.includes(k)) fillPlans(k);
      });
      cizKodlar();
    };
    /* Yazarak süzme — seçili olan her zaman listede kalıyor, yoksa
       süzgeç yazarken kullanıcının seçimi sessizce düşerdi. */
    const anadalQ = $("#fAnadalQ");
    if(anadalQ) anadalQ.addEventListener("input", () => {
      const q = anadalQ.value.trim().toLocaleLowerCase("tr");
      const secili = $("#fAnadal").value;
      const uyan = codes.filter(c => !q
        || label(c).toLocaleLowerCase("tr").includes(q) || c === secili);
      $("#fAnadal").innerHTML =
        (secili ? "" : `<option value="">— bölümünü seç —</option>`)
        + uyan.map(c => `<option value="${esc(c)}"${c === secili ? " selected" : ""}
            >${esc(label(c))}</option>`).join("");
      $("#fAnadalSayi").innerHTML = q
        ? `<b class="mono">${uyan.length}</b> bölüm eşleşti`
        : `Listede <b class="mono">${codes.length}</b> bölüm var.`;
    });
    $("#fKind").querySelectorAll("button").forEach(b =>
      b.addEventListener("click", () => {
        kind = b.dataset.k;
        $("#fKind").querySelectorAll("button").forEach(x =>
          x.setAttribute("aria-pressed", x.dataset.k === kind));
        sync();
      }));
    ["cap","yandal"].forEach(k =>
      $("#fProg-" + k).addEventListener("change", () => { fillPlans(k); cizKodlar(); }));
    /* Anadal değişince de rozetler değişmeli — türetmenin ilk kaynağı o.
       Faz 54: plan listeleri de (hangi plan kimin için). */
    $("#fAnadal").addEventListener("change", () => {
      kindsOf(kind).forEach(k => fillPlans(k));
      cizKodlar();
    });
    $("#fCodes").addEventListener("input", cizKodlar);
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
      /* ⚠️ Kutuya YALNIZ EKSTRALAR gidiyor. Anadal/ÇAP/yandal kodları
         `allowed_programs` içinde her okumada yeniden türetiliyor; dosyaya
         yazmak, program değiştiğinde eski kodları geride bırakırdı — ve
         bırakıyordu da. */
      save(() => api("/api/programs", {
        anadalProgram: anadal,
        secondKind: kind,
        secondPrograms: secim,
        programCodes: $("#fCodes").value.split(/[,\s]+/).filter(Boolean),
      }));
    });
  });
}

/* ---------- 1b. tercihler (Faz 27) ----------
   ★★ Bunlar YUMUŞAK. "Sabah dersi istemiyorum"u eleme kuralı yapmak,
   gerçek veride kayıt edilebilir tek programı imkânsız gösterebilirdi
   (14 ÇAP dersinden yalnız 2–3'ü bir dönemde alınabiliyor). Tercih, iki
   ÇALIŞAN program arasında seçim yaptırıyor; çalışan tek programı elemiyor.
   Pencere bunu AÇIKÇA yazıyor, yoksa kullanıcı "istemiyorum dedim ama yine
   koydu" diye aracı hatalı sanar. */
const TERCIH_GUN = [[1, "Pzt"], [2, "Sal"], [3, "Çar"], [4, "Per"], [5, "Cum"]];
const TERCIH_SAAT = [[0, "önemsiz"], [510, "08:30"], [570, "09:30"],
                     [630, "10:30"], [690, "11:30"]];

function tercihDialog(){
  const P = (SETUP && SETUP.prefs) || {};
  let erken = P.enErken || 0;
  let gunler = new Set(P.bosGunler || []);
  openSetup(`
    <div class="eyebrow">Kurulum</div>
    <h2 style="margin-bottom:4px">Tercihlerin</h2>
    <p class="modenote" style="margin:2px 0 4px">Bunlar <b>eleme değil,
      sıralama</b>: araç önce çalışan programları bulur, sonra tercihlerine
      en uygun olanı öne alır. Tek çalışan program tercihine uymuyorsa yine
      de gösterilir — <b>çünkü gösterilmemesi işine yaramaz.</b></p>

    <label class="field"><span>Şu saatten önce ders istemiyorum</span>
      <div class="radios" id="fErken">
        ${TERCIH_SAAT.map(([v, l]) =>
          `<button data-v="${v}" aria-pressed="${v === erken}">${l}</button>`).join("")}
      </div></label>

    <label class="field"><span>Boş kalmasını istediğim günler</span>
      <div class="terms" id="fGun">
        ${TERCIH_GUN.map(([v, l]) => `<button data-v="${v}"
          aria-pressed="${gunler.has(v)}" style="width:auto;padding:7px 12px"
          >${l}</button>`).join("")}
      </div>
      <span class="hint">Beşini birden seçemezsin.</span></label>

    <div class="grid2" style="margin-top:14px">
      <label class="tickbox"><input type="checkbox" id="fKampus"
        ${P.kampus ? "checked" : ""}> Aynı gün kampüs değiştirmek istemiyorum</label>
      <label class="tickbox"><input type="checkbox" id="fOnline"
        ${P.cevrimici ? "checked" : ""}> Çevrimiçi şubeyi yeğlerim</label>
    </div>

    <details class="adv"${(P.istenenHocalar || []).length
      || (P.istenmeyenHocalar || []).length ? " open" : ""}>
      <summary>Öğretim üyesi</summary>
      <label class="field"><span>İstediğim hocalar</span>
        <input type="text" id="fHocaVar"
          value="${esc((P.istenenHocalar || []).join(", "))}"
          placeholder="Buzluca, Şule Itır"></label>
      <label class="field"><span>İstemediğim hocalar</span>
        <input type="text" id="fHocaYok"
          value="${esc((P.istenmeyenHocalar || []).join(", "))}">
        <span class="hint">Ad parçası yeter. Virgülle ayır.
          ⚠️ 3417 şubenin 887'sinde hoca ilan edilmemiş — onlar hiçbir
          tercihe uymaz, ne artı ne eksi alır.</span></label>
    </details>`, () => {
    $("#fErken").querySelectorAll("button").forEach(b =>
      b.addEventListener("click", () => {
        erken = +b.dataset.v;
        $("#fErken").querySelectorAll("button").forEach(x =>
          x.setAttribute("aria-pressed", +x.dataset.v === erken));
      }));
    $("#fGun").querySelectorAll("button").forEach(b =>
      b.addEventListener("click", () => {
        const v = +b.dataset.v;
        if(gunler.has(v)) gunler.delete(v);
        else if(gunler.size >= 4) { say("beş günün beşini boş isteyemezsin", true); return; }
        else gunler.add(v);
        b.setAttribute("aria-pressed", gunler.has(v));
        say("");
      }));
    $("#setupSave").addEventListener("click", () => {
      const ayir = (id) => $(id).value.split(",").map(s => s.trim()).filter(Boolean);
      save(() => api("/api/tercih", {
        enErken: erken,
        bosGunler: [...gunler],
        kampus: $("#fKampus").checked,
        cevrimici: $("#fOnline").checked,
        istenenHocalar: ayir("#fHocaVar"),
        istenmeyenHocalar: ayir("#fHocaYok"),
      }), {});                        // kip korunur (Faz 54)
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
      <!-- ⚠️ FAZ 41: burada eskiden dönem bilinmiyorken de "0. dönem (tahmin)"
           yazıyordu. "0. dönem" diye bir şey yok ve "(tahmin)" YAPILMAMIŞ bir
           tahmini yapılmış gösteriyordu — transkript yokken çıkarılacak bir
           şey yok. Bilinmiyorsa bilinmediğini yazıyor. -->
      <span class="hint">${DATA.donem
        ? `Şu an kullanılan: <b class="mono">${DATA.donem}. dönem</b>
           (${esc(DATA.donemSource || "ayar")}).`
        : `<b>Şu an dönem bilinmiyor</b> — geçtiğin dersleri de girmediğin için
           çıkarılabilecek bir şey yok, o yüzden öneri planın her döneminden
           ders karıştırıyor.`}
        Otomatik seçilirse geçtiğin slotların en derin
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

  /* ★★ FAZ 47 — DÖNEMDEN ÖNERİLEN TİKLER (kullanıcı 18.09.2026:
     *"5. dönem olan birisi geçtiği dersleri işaretlemek için otomatik tik
     attırabilir"*).

     ⚠️⚠️ ÖNERİ, İDDİA DEĞİL. Bu depoda kural: bilinmeyen, bilinen gibi
     gösterilmez. "5. dönemdesin" demek "1–4. dönemin hepsini geçtin"
     DEMEK DEĞİL — ders bırakmış, kalmış, yatay geçmiş olabilir. O yüzden:
     · yalnız transkript HENÜZ BOŞKEN öneriliyor (girdiysen dokunulmuyor),
     · kaç ders işaretlendiği pencerenin tepesinde SAYIYLA yazıyor,
     · "hepsini kaldır" tek tık,
     · ve hiçbiri Kaydet'e basmadan yazılmıyor.
     1. dönemdeysen hiçbir şey işaretlenmiyor — geçmiş dönemin yok. */
  const donem = DATA.donem || 0;
  const bostu = !(SETUP.transcript || []).length;
  let onerilen = [];
  if(donem > 1 && bostu){
    plans.forEach(p => p.terms.forEach(t => {
      if(!t.term || t.term >= donem) return;
      t.slots.forEach(sl => { if(sl.required) sl.options.forEach(o => {
        if(state[o.course] && !state[o.course].taken){
          state[o.course].taken = true;
          onerilen.push(o.course);
        }
      }); });
    }));
  }

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
        <span class="ckname">${o.name ? esc(o.name.slice(0, 40))
          : `<span class="uyari">katalogda yok</span>`}</span>
        <span class="mono ckcr"${o.credits === null || o.credits === undefined
          ? ` title="Kredisi katalogda yok."` : ""}>${o.credits ?? "–"}</span>
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
    ${onerilen.length ? `<div class="note" style="border-left:3px solid var(--warn);
      padding-left:10px;margin:8px 0">
      <b>${onerilen.length} ders senin için işaretlendi</b> — ${donem}.
      dönemde olduğunu söyledin, 1–${donem - 1}. dönemin zorunluları tiklendi.
      <b>Bu bir tahmin, kayıt değil:</b> geçmediğin varsa tikini kaldır.
      <button class="ghost mini" id="ckUndo" style="margin-left:6px"
        >hepsinin tikini kaldır</button></div>`
      : (donem === 1 ? `<div class="note" style="margin:8px 0">
          <b>1. dönemdesin</b> — geçmiş dönemin yok, bu liste boş başlıyor.
          Yaz okulu ya da muafiyetle aldığın ders varsa tikle.</div>` : "")}
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
    const geriAl = $("#ckUndo");
    if(geriAl) geriAl.addEventListener("click", () => {
      onerilen.forEach(k => { if(state[k]) state[k].taken = false; });
      onerilen = [];
      box.querySelectorAll('input[type=checkbox][data-course]').forEach(cb => {
        cb.checked = state[cb.dataset.course].taken;
        const sel = box.querySelector(`select.g[data-course="${CSS.escape(cb.dataset.course)}"]`);
        if(sel) sel.disabled = !cb.checked;
      });
      count();
      geriAl.closest(".note").remove();
    });
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

    /* ★★ FAZ 47 — TİK GERİ ÇEKİLİNCE DERS DÜŞÜYOR (kullanıcı bildirdi
       18.09.2026). Ölçüldü: pencere yalnız TİKLİ dersleri gönderiyordu ve
       `replace:false` ile ekliyordu; tik geri çekilince hiçbir şey olmuyor,
       ders transkriptte kalıyordu (37 → 38 satır, geri çekince yine 38).

       ⚠️ `replace:true` YAPILMADI — o, elle girilmiş ve plan dışı dersleri
       de silerdi. `remove` YALNIZ bu pencerenin gösterdiği ve tiklenmemiş
       dersleri taşıyor; pencerenin görmediği hiçbir satıra dokunulmuyor. */
    $("#setupSave").addEventListener("click", () => save(() => api("/api/transcript", {
      items: Object.entries(state).filter(([, v]) => v.taken)
        .map(([course, v]) => ({course, grade: v.grade, inProgress: v.ip})),
      remove: Object.entries(state).filter(([, v]) => !v.taken)
        .map(([course]) => course),
      replace: false,        // ★ EKLER: plan DIŞI dersler korunur
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
    /* ★ E — "BLG 105E · (adsız) · –". Katalogda BULUNMAYAN ders böyle
       görünüyordu: boş ad ve sıfıra benzeyen bir tire. Kullanıcı kendi
       yazdığı kodun yanlış mı yoksa dersin eski mi olduğunu anlayamıyordu.
       Ölçüldü: transkript kodları katalogla eşleşmeyebiliyor (eski/kapanmış
       ders), ve plan slotlarının 67'si de katalogda olmayan derse bakıyor.
       Artık SEBEBİ yazıyor — kredi hanesindeki tire de açıklanıyor. */
    const yok = (r) => !r.name && r.credits === null && r.credits !== 0;
    $("#trBody").innerHTML = rows.length ? rows.map((r, i) => `<tr>
        <td><b class="mono">${esc(r.course)}</b>
          <div class="meta" style="color:var(--ink-3);font-size:11.5px">${
            yok(r) ? `<span class="uyari">bu ders katalogda yok</span>`
                   : esc((r.name || "").slice(0, 44))}</div></td>
        <td>${gradeSelect(r, i)}</td>
        <td class="mono" style="color:var(--ink-3)"${
          r.credits === null || r.credits === undefined
            ? ` title="Kredisi katalogda yok; kredi toplamına katılmıyor."` : ""
          }>${r.credits ?? "–"}</td>
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

    <!-- ★ KOLAY YOL ÖNDE (ilk kullanıcı incelemesi D2). Kart "transkriptini
         olduğu gibi yapıştır" diyordu ama pencerede öne çıkan şey tek tek
         ders yazmaktı; yapıştırma katlanmış bir <details> içindeydi. -->
    <label class="field"><span>1 · Transkriptini yapıştır (en kolayı)</span>
      <textarea id="trPaste" style="margin-top:4px"
        placeholder="OBS not dökümünü olduğu gibi yapıştır — sütunlu hâli de olur:&#10;MAT 103E    Mathematics I    4.0   6.0   BB&#10;FIZ 101E    Physics I        3.0   4.5   CB"
        ></textarea>
      <span class="hint">Sütunlu döküm de, <span class="mono">KOD NOT</span>
        biçimi de olur. <b>Uygulamadan önce ne bulduğunu göstereceğim.</b>
        Yapıştırma mevcut listeye <b>eklenir</b>, silmez.</span>
      <div style="display:flex;gap:8px;margin-top:8px;flex-wrap:wrap">
        <button class="ghost primary" id="trOnizle">Ne bulduğuna bak</button>
      </div>
      <div id="trOnizleme" style="margin-top:10px"></div></label>

    <label class="field"><span>2 · ya da tek tek ekle</span>
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

`, () => {
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

    /* ★★ ÖNİZLEME (ilk kullanıcı incelemesi A1). Eskiden yapıştır → kaydet
       tek adımdı ve sessizce yanlış sonuç üretebiliyordu: pencere kapanıyor,
       işlem başarılıymış gibi görünüyordu. Artık uygulamadan ÖNCE ne
       bulunduğu gösteriliyor. */
    $("#trOnizle").addEventListener("click", async () => {
      const kutu = $("#trOnizleme");
      const metin = $("#trPaste").value;
      if(!metin.trim()){ kutu.innerHTML =
        `<div class="empty">önce transkriptini yapıştır</div>`; return; }
      kutu.innerHTML = `<div class="empty">okunuyor…</div>`;
      try{
        const r = await api("/api/transcript/preview", {text: metin});
        trOnizlemeCiz(r.preview || {});
      }catch(err){
        kutu.innerHTML = `<div class="empty">${esc(err.message)}</div>`;
      }
    });

    // ★ replace:true — ekrandaki liste TAM liste. 'çıkar' düğmesinin
    //   çalışması için gerekli; yoksa silinen ders DB'de kalırdı.
    $("#setupSave").addEventListener("click", () => save(() => api("/api/transcript", {
      items: rows.map(r => ({course: r.course, grade: r.grade,
                             inProgress: r.status === "IN_PROGRESS"})),
      replace: true,
    })));
  });
}

/* ---------- yapıştırma önizlemesi (ilk kullanıcı incelemesi A1) ----------
   ⚠️ Üç sayı AYRI: bulundu · atlandı · notu okunamadı. Tek bir "10 ders
   eklendi" satırı, atlanan 8 satırı ve okunamayan 2 notu gizliyordu. */
function trOnizlemeCiz(p){
  const kutu = $("#trOnizleme");
  if(!p.count && !(p.bad || []).length){
    kutu.innerHTML = `<div class="empty">bu metinde ders satırı bulunamadı</div>`;
    return;
  }
  const rozet = (n, ad, sinif) => n
    ? `<span class="ozet ${sinif || ""}"><b class="mono">${n}</b> ${ad}</span>` : "";
  kutu.innerHTML = `
    <div class="ozetler">
      ${rozet(p.count, "ders bulundu", "ok")}
      ${rozet(p.passed, "geçilmiş")}
      ${rozet(p.inProgress, "devam ediyor")}
      ${rozet(p.failed, "kalınmış")}
      ${rozet(p.badTotal, "satır atlandı", "kotu")}
      ${rozet(p.warningTotal, "notu okunamadı", "uyari")}
    </div>
    ${p.count ? `<div class="scroll" style="max-height:190px;margin-top:8px">
      <table class="trtable"><tbody>${(p.items || []).map(i => `<tr>
        <td><b class="mono">${esc(i.course)}</b></td>
        <td class="mono">${i.grade || (i.status === "IN_PROGRESS" ? "devam" : "—")}</td>
      </tr>`).join("")}</tbody></table>
      ${p.count > p.shown ? `<div class="hint">…ve ${p.count - p.shown} ders daha
        (hepsi eklenecek)</div>` : ""}
    </div>` : ""}
    ${(p.warnings || []).length ? `<div class="note" style="margin-top:8px">
      <b>Notu okunamayan satırlar</b> — “geçtim (DD)” sayıldı:
      <div class="hint">${p.warnings.map(esc).join("<br>")}</div></div>` : ""}
    ${(p.bad || []).length ? `<div class="note" style="margin-top:8px">
      <b>Atlanan satırlar</b> (ders kodu bulunamadı):
      <div class="hint mono">${p.bad.map(esc).join("<br>")}${
        p.badTotal > p.bad.length ? `<br>…+${p.badTotal - p.bad.length}` : ""}</div></div>` : ""}
    <button class="ghost primary" id="trUygula" style="margin-top:10px"
      ${p.count ? "" : "disabled"}>Bu ${p.count} dersi ekle</button>`;
  const btn = $("#trUygula");
  if(btn) btn.addEventListener("click", () => save(async () => {
    const body = await api("/api/transcript/paste",
      {text: $("#trPaste").value, replace: false});
    return body;
  }));
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
          ${L.noTranscript
            /* ★★ İnceleme B4 — Faz 26 kararının uygulanmamış yarısı.
               Transkript yokken GNO 0.00 bir ÖLÇÜM değil, veri yokluğu.
               "GNO'ndan hesaplandı" demek onu ölçülmüş gibi sunuyordu; üstelik
               sayı süs değil, motor gerçekten bu tavanla program kuruyor.
               ⚠️ Tavanı gizlemiyoruz — motor bir sayı kullanmak ZORUNDA.
               Söylediğimiz şey değişiyor: "hesaplandı" değil, "VARSAYILDI". */
            ? `transkript yok — <b>en düşük band varsayıldı</b>:`
            : (({"yönetmelik": "motor bunu kullanıyor — GNO'ndan hesaplandı",
                 "ayar": "elle ayarlı (settings.toml)",
                 "çağrı": "bu çalıştırmaya özel"}[L.limitSource] || "şu an ayarlı") + ":")}
          <b class="mono">${L.declared || "—"}</b></div>
      </div>
      <div style="flex:2;min-width:250px;font-size:12.5px;color:var(--ink-2)">
        ${L.noTranscript ? `<div class="note" style="margin-bottom:8px">
          <b>GNO bilinmiyor.</b> Aşağıdaki gerekçelerde geçen “GNO 0.00”
          hesaplanmış bir değer <b>değil</b> — geçtiğin dersleri girmedin.
          Girdiğinde tavan da değişebilir.
          ${LIVE ? `<button class="ghost" data-setup="plan"
            style="margin-left:6px">Dersleri gir</button>` : ""}</div>` : ""}
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
  $("#loadBody").querySelectorAll("[data-setup]").forEach(b =>
    b.addEventListener("click", () => ({program: programDialog, donem: termDialog,
                                        plan: checklistDialog, tercih: tercihDialog,
                                        dersler: courseDialogSetup})[b.dataset.setup]()));
  const btn = $("#loadFix");
  if(btn) btn.addEventListener("click", async () => {
    btn.disabled = true; btn.textContent = "…";
    try{ applyState(await api("/api/maxload", {maxLoad: L.max})); }
    catch(err){ hataBildir(btn, err); }
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
/* ---------- denkliği açık gereken dersler (kullanıcı isteği 27.08.2026) ----------
   ★ "Almam gereken bir dersin denkliği bu dönem açıksa onları listeleyip
   bilgilerini göster." Aday listesinden AYRI: buradaki açık ders (kaynak)
   planımda olmayabilir ama denklikle bir gereksinimi (hedef) karşılıyor. */
function renderAcikDenklik(){
  const liste = DATA.openEquivalents || [];
  const sec = $("#denklikSection");
  if(!sec) return;
  sec.hidden = !liste.length;
  if(!liste.length){ $("#denklikBody").innerHTML = ""; return; }
  const saat = (secs) => (secs[0] && secs[0].meetings.length)
    ? secs[0].meetings.map(m => `${DAYS[m.day-1]} ${hhmm(m.start)}–${hhmm(m.end)}`).join(", ")
    : "saat ilan edilmemiş";
  $("#denklikBody").innerHTML = liste.map(e => {
    /* Açık ve henüz alınmamış kaynaklar — asıl gösterilecek olanlar. */
    const acik = e.sources.filter(k => k.open && !k.passed);
    const kaynakHTML = acik.map(k => {
      const s = k.sections[0] || {};
      /* Aday havuzunda mı — tıklayıp eklenebilir mi? Değilse bilgi kartı
         (yine de CRN/saat/kontenjan görünüyor). Sessiz tıklanamazlık yerine
         görünüm ve ipucu farklı.
         ⚠️ Faz 49'da bakıldı ve BİLEREK `CAND` bırakıldı: buradaki
         tıklanamazlık SESSİZ değil (kartın görünümü ve `title`ı söylüyor),
         yani ızgaradaki hatanın sınıfında değil. `addDialog` artık tam
         havuza düşüyor, yani açmak isteyen tek satır uzakta — ama bu
         öğrencinin verisinde ölçülecek tek bir kart bile çıkmadı
         (`openEquivalents` boş), ölçmeden değiştirmiyoruz. */
      const eklenebilir = !!CAND[k.code];
      return `<div class="denkkaynak${eklenebilir ? "" : " bilgi"}"
          data-course="${esc(k.code)}"${eklenebilir
            ? ` role="button" tabindex="0" title="Programa eklemek için tıkla"`
            : ` title="Aday havuzunda değil — bilgi amaçlı"`}>
        <div><b class="mono">${esc(k.code)}</b>
          ${k.name ? `<span class="denkad">${esc(k.name)}</span>` : ""}
          ${k.sections.some(x => x.online) ? `<span class="chip online"
            style="margin-left:6px">çevrimiçi</span>` : ""}</div>
        <div class="denkmeta mono">
          ${k.sections.length === 1 ? `CRN ${esc(s.crn)} · ` : ""}${esc(saat(k.sections))}
          ${s.instructor ? ` · ${esc(s.instructor)}` : ""}</div>
        <div style="margin-top:4px">${doluluk(k.sections)}</div>
      </div>`;
    }).join("");
    const kapali = e.sources.filter(k => !k.open && !k.passed);
    const alinmis = e.sources.filter(k => k.passed);
    /* Başka bölümden mi (kod öneki farklı)? Dilekçe çerçevesi için. */
    const hedefOn = e.target.split(" ")[0];
    const capraz = acik.some(k => k.code.split(" ")[0] !== hedefOn);
    /* mode="or": kaynaklar birbirinin ALTERNATİFİ (resmi OBS). Kapalı olan
       "eksik" değil, sadece başka bir seçenek — AND uyarısı verme.
       mode="and": çok kaynaklı beyan; kapalı olan tamamlanmayı engeller. */
    let not = "";
    if (e.mode === "and" && e.sources.length > 1) {
      not = `<div class="denknot">${
        alinmis.length ? `<b>${alinmis.map(k => esc(k.code)).join(", ")}</b> zaten alınmış. ` : ""
        }${kapali.length ? `⚠ <b>${kapali.map(k => esc(k.code)).join(", ")}</b> bu dönem
          kapalı — denkliğin tamamlanması için o da gerekiyor.`
        : (alinmis.length ? "Bu açık dersi de alınca denklik tamamlanıyor." : "")}</div>`;
    }
    /* Köken çerçevesi: resmi = OBS + dilekçe; beyan = kendi bildirdiğin. */
    if (!e.declared) {
      const onay = e.confidence === "requires_approval"
        ? "bölüm/yönetim kurulu onayı gerekebilir"
        : "dilekçeyle saydırılır";
      not += `<div class="denknot">OBS resmî ders denkliği${
        capraz ? " — <b>başka bölümden</b>" : ""}; ${onay}. Danışmanına doğrulat.</div>`;
    }
    /* Başlık: OR ise "birini al", tek/AND ise "denkliği açık". */
    const baslik = e.mode === "or"
      ? (acik.length > 1 ? "— yerine şu açık derslerden <b>birini</b> al:"
                         : "— yerine bu açık ders alınabilir:")
      : "— denkliği açık:";
    return `<div class="denkrow">
      <div class="denkhedef">
        <span class="tag ${e.needed ? "CAP" : "unknown"}">${e.needed
          ? "gereken" : "beyanın"}</span>
        <b class="mono">${esc(e.target)}</b>
        ${e.targetName ? `<span class="denkad">${esc(e.targetName)}</span>` : ""}
        <span class="denkok">${baslik}</span></div>
      ${kaynakHTML}
      ${not}
    </div>`;
  }).join("");
  /* Kaynağa tıklama = programa ekle penceresi — YALNIZ aday havuzundaysa. */
  $("#denklikBody").querySelectorAll(".denkkaynak:not(.bilgi)[data-course]")
    .forEach(el => bind(el, () => addDialog(el.dataset.course)));
}

function renderChanges(){
  const c = DATA.changes;
  const btn = $("#refreshBtn");
  /* ★★ D3 — İLK GİREN KİŞİYE BOŞ BÖLÜM GÖSTERİLİYORDU. Ölçüt `LIVE`
     olduğu için, hiç tazeleme yapmamış birine "Ne değişti" başlığı ve
     altında "en az iki tazeleme gerekiyor" cümlesi çıkıyordu: henüz
     kullanmadığı bir özelliğin boş kabuğu, üstelik bölüm çubuğunda da
     bir sıra kaplıyordu.

     Yeni ölçüt KARŞILAŞTIRILACAK BİR ŞEY OLMASI. Tazeleme düğmesi
     kaybolmuyor — araç çubuğuna değil, ilk tazelemeden sonra bu bölüme
     dönüyor; `LIVE` iken zaten üstteki veri-yaşı satırından da
     tazelenebiliyor. */
  const karsilastirilabilir = !!(c && c.since && c.until && c.since !== c.until);
  $("#changeSection").hidden = !(karsilastirilabilir || (c && c.count));
  if(btn){ btn.hidden = !LIVE; }
  if(!karsilastirilabilir){
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
      catch(err){ hataBildir(b, err); }
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
    }catch(err){ hataBildir(all, err); }
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
    + (donemYazi() ? " · " + donemYazi() : "");

  let kredi = 0, akts = 0, eksik = 0;
  const kart = saved.map(p => {
    const hit = findSection(p.course, p.crn);
    if(!hit){ eksik++; return `<div class="savedcard">
      <b class="mono">${esc(p.course)}</b><span class="crn mono">${esc(p.crn)}</span>
      <div class="miss">şube bu dönemin verisinde yok</div></div>`; }
    kredi += hit.cand.credits || 0; akts += hit.cand.ects || 0;
    const saat = (hit.sec.meetings || []).map(m =>
      `${DAYS[m.day-1] || "?"} ${hhmm(m.start)}`).join(" · ") || "saati ilan edilmemiş";
    return `<div class="savedcard ${hit.cand.role === "ANADAL" ? "" : "ikinci"}"
      style="${tonStil(p.course, hit.cand.role)}">
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
    /* ★★ FAZ 47 — YÜKLEYİNCE HAFTALIK PROGRAMA GEÇ (kullanıcı 18.09.2026).
       Burada `scrollIntoView` vardı; Faz 46'da görünüm kipine geçince
       ÇALIŞMAZ oldu — hedef bölüm kapalı, kaydırılacak bir şey yok.
       Kullanıcı "yükle"ye basıp aynı ekranda kalıyordu: program yüklendi
       ama göründüğü yer kapalı. Görünüm değişikliği kaydırmanın yerini
       alıyor. */
    gorunumAc("schedSection", true);
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
  if(btn){
    /* ★ Düğme KALICI bir eleman; kaydederken dugmeMesgul onu "meşgul" (dönen
       halka, KİLİTLİ) yapıyor. Her yeniden çizimde TEMİZ duruma döndür — yoksa
       kaydedip başka programa/kipe geçince düğme "Kaydediliyor…" kilitli takılı
       kalıyor ve yeni programı KAYDEDEMİYORDUN (kullanıcı raporu 31.08.2026).
       Kaydetme sırasındaki meşgul hâli await boyunca duruyor; bu sıfırlama
       ancak kaydetme bitip sayfa yeniden çizilince çalışıyor. */
    btn.disabled = false;
    btn.classList.remove("mesgul");
    btn.textContent = "Programı kaydet";
    btn.hidden = !LIVE || !dirty || !sel.length;
  }
  if(mark){
    mark.hidden = !(saved.picks.length && !dirty);
    mark.textContent = "kaydedildi" + (saved.savedAt
      ? " · " + saved.savedAt.replace("T", " ").slice(0, 16) : "");
  }
}
function wirePicks(){
  const btn = $("#savePicks");
  if(btn && LIVE) btn.onclick = async () => {
    const geri = dugmeMesgul(btn, "Kaydediliyor…");
    await bekleBoyansin();          // ★ halka boyansın (Pyodide blokluyor)
    try{
      // ★ Önce kaydet, sonra durumu tazele. (Başarıda sayfa yeniden
      //   kuruluyor, düğme zaten yenileniyor; geri() yalnız hata yolunda.)
      // ★ Faz 53: `koru` — kip ve ızgara OLDUĞU GİBİ kalıyor. Eskiden
      //   applyState kip 0'a dönüp kaydedileni yeniden yüklüyordu; başka
      //   kipte kaydeden kişi kendini öbür kipte buluyordu.
      applyState(await api("/api/picks", {picks: sel}), {koru: true});
    }catch(err){
      geri(); hataBildir(btn, err);
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
  /* ★★ FAZ 48 — aynı sınıf: kapalı bölüme kaydırmak hiçbir şey yapmıyordu.
     CRN'den program yükleyen kişi listeyi girip "tamam" diyor ve aynı
     ekranda kalıyordu. */
  gorunumAc("schedSection", true);
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

/* Katalogda ilan edilmiş kredi tabanını tutmuyorsan rozet (Faz 37).
   Kazanılmış kredi bilinmiyorsa (transkript yok) İDDİA ETMİYORUZ. */
function katalogKrediUyarisi(it){
  const floor = it && it.creditFloor;
  if(!floor) return "";
  const c = DATA.credits;
  if(!c || !c.rules || !c.rules.length) return "";
  if(c.earned + 1e-9 >= floor) return "";
  return `<span class="tag" style="margin-left:6px;background:var(--warn-soft);
    color:var(--warn-ink)" title="Katalog bu ders için asgari ${floor} kredi
    ilan etmiş; şu an ${c.earned} kredin var.">${floor} kredi ister</span>`;
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
            it.role === "PLAN_DISI" ? "plan dışı" : it.role}</span>${
          /* ★ Faz 37 — katalogda ilan edilmiş kredi tabanını tutmuyorsan
             rozet çıkar. ENGEL değil (plan dışı ekleme senin kararın), ama
             sessiz de kalmıyor: kayıt gününde öğrenilecek bir sürpriz. */
          katalogKrediUyarisi(it)}
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
               "PRODID:-//itucap//__AD_ASCII__//TR",
               "CALSCALE:GREGORIAN"];
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
                       : `${ps.length} şubede yer var (${esc(veriTarihi())} verisiyle —
                          kayıtta OBS'deki güncel sayıya bak)`);

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
  btn.onclick = () => tazele(btn);
}

/* ★ Tazeleme İKİ yerden başlatılabiliyor: "Ne değişti" bölümündeki düğme ve
   veri-yaşı satırındaki küçük düğme. İlerlemeyi TIKLANAN düğme gösteriyor —
   eskiden metin hep gizli bölümdeki düğmeye yazılıyordu ve oradan
   başlatılmayan tazeleme 1–2 dakika boyunca hiçbir iz bırakmıyordu. */
async function tazele(btn){
  if(!btn || btn.disabled) return;
  const geri = dugmeMesgul(btn, "Tazeleniyor… (1–2 dk)");    /* dönen halka */
  await bekleBoyansin();          // ★ halka boyansın, sonra bloklayan tarama
  try{
    const next = await api("/api/refresh", {});
    applyState(next);
    const n = (next.changes && next.changes.count) || 0;
    /* Sonuç, "Ne değişti" bölümü artık görünür olduğu için oraya yazılıyor;
       görünmüyorsa (karşılaştırma çıkmadıysa) düğmenin yanında duruyor. */
    const not = $("#changeWhen");
    const ek = next.obsError
      ? `⚠ OBS'ye ulaşılamadı, eski plan verisi korundu (${next.obsError})`
      : (n ? `${n} değişiklik bulundu` : "değişiklik yok");
    if(not && !$("#changeSection").hidden) not.textContent += "  ·  " + ek;
    else say2(ek);
  }catch(err){
    const g = $("#changeBody");
    if(g && !$("#changeSection").hidden)
      g.innerHTML = `<div class="note">Tazeleme başarısız: ${esc(err.message)}</div>`;
    else say2("Tazeleme başarısız: " + err.message);
    geri();
  }
}

/* ★ Katalogda ilan edilmiş kredi tabanı (Faz 37).
   Kaynak sütuna "Sınıf Kısıtı" diyor ama değerleri kredi (95,00 / 60,00 /
   30,00 / Yok). Yorum bizim olduğu için hem KAYNAĞI hem doğrulanma durumunu
   yazıyoruz ve kapatılabilir olduğunu söylüyoruz — kesinmiş gibi sunmuyoruz. */
function catalogCreditHtml(info){
  const c = info && info.catalog;
  if(!c || !c.enabled) return "";
  /* ⚠️ Transkript yokken "engel yok" DEMİYORUZ — bakamadığımızı yazıyoruz. */
  if(c.noTranscript)
    return `<div class="modenote" style="margin-top:6px">Katalog bazı dersler
      için ayrıca <b>kredi koşulu</b> ilan ediyor (95 / 60 / 30 kredi).
      Hangilerini tuttuğun ancak transkriptin girilince görünür.</div>`;
  if(!c.blocked || !c.blocked.length) return "";
  const GOSTER = 12;
  const rows = c.blocked.slice(0, GOSTER).map(b =>
    `<li><span class="mono">${esc(b.course)}</span> ${esc(b.name)} —
       en az <b class="mono">${b.min}</b> kredi,
       <b class="mono">${b.missing}</b> kredi eksik</li>`).join("");
  const fazla = c.blocked.length - GOSTER;
  return `<div class="note" style="margin-top:6px">
    Katalog bu <b>${c.blocked.length}</b> ders için ayrıca kredi koşulu ilan etmiş;
    şu an <b>tutmuyorsun</b>, o yüzden önerilere girmiyorlar:
    <ul style="margin:5px 0 0 18px;padding:0">${rows}${
      fazla > 0 ? `<li>… ve ${fazla} ders daha</li>` : ""}</ul>
    <div style="margin-top:5px;color:var(--ink-3)">
      Kaynak: ${esc(c.source)}${c.verified ? ""
        : " · ⚠ bu alanın adı kaynakta “Sınıf Kısıtı”; kredi tabanı olarak"
          + " okumak bizim yorumumuz. Kapatmak için"
          + " <span class=\"mono\">kurallar.toml → [katalog_kredi_kosulu] kullan = false</span>."}
    </div></div>`;
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
    /* ★ Faz 37 — katalogda ders ders ilan edilmiş taban. Beyan edilmiş
       kuralın dışında kalan dersleri buraya yazmasak, motor onları eler ve
       kullanıcı sebebini hiçbir yerde göremezdi. */
    + catalogCreditHtml(info)
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
      <div class="pctbox">
        <div class="pct mono${bilinmiyor ? " unknown" : ""}"
          title="${bilinmiyor ? "Geçtiğin dersler girilmedi" : ""}"
          >${bilinmiyor ? "—" : "%" + p.percent}</div>
        ${bilinmiyor ? "" : `<div class="pctlbl">tamamlandı</div>`}
      </div>
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
      `<span class="cat${(bilinmiyor || c.done) ? "" : " zero"}"${
        c.key === "OTHER" ? ` title="Kaynakta bu havuzun kategorisi yazmıyor` +
        ` (bkz. Faz 23) — kategori uydurmuyoruz."` : ""}>${
        /* ★ Faz 37 — 'OTHER' motorun iç etiketi; kullanıcıya bir şey
           anlatmıyordu. Yandal kartında tek görünen chip oydu. */
        esc(c.key === "OTHER" ? "KATEGORİSİZ" : c.key)} ${
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
  : [{key:"all", label:"__AD_KISA__", note:"",
      candidates: DATA.candidates, schedules: DATA.schedules}];
let mode = 0;
let CAND = {};
const T0 = 8*60, T1 = 21*60, STEP = 30, ROWS = (T1-T0)/STEP;
/* Izgara tüm günü mü gösteriyor (Faz 39). Oturumluk, kalıcı tercih değil. */
let GRID_TUM = false;
let active = 0;
let sel = [];                                   // [{course, crn}]

const M = () => MODES[mode];

/* ★ TÜM aday havuzu — hangi kipte olursak olalım DEĞİŞMEYEN tam liste.
   `DATA.candidates` sunucuda her zaman tam `cands`'tan üretiliyor ('all'
   kipiyle aynı). "x.dönem + alttan" kipi bunun bir ALT KÜMESİ.

   Neden ayrı: boş saate tıklayınca o saatte alınabilecek HER dersi
   göstermek istiyoruz (kullanıcı isteği 27.08.2026) — kip süzgeci yalnız
   ÖNERİYİ daraltıyor, elle ekleme hakkını değil. */
const TUM_CAND = () => Object.fromEntries((DATA.candidates || []).map(c => [c.course, c]));
/* Aktif kipte yoksa tam havuza düş: elle eklenen üst-dönem dersi de
   `choose`/`picks`'te çözülebilsin, yoksa tıklama SESSİZCE hiçbir şey
   yapmazdı. */
const candOf = (course) => CAND[course] || TUM_CAND()[course];

function useMode(i, secenek){
  mode = i;
  /* ⚠️ Kip değişince geri yığını TEMİZLENİYOR: her kipin KENDİ aday havuzu
     var, öbür kipin seçimini geri yüklemek ızgarada olmayan bir dersi
     göstermeye çalışırdı. */
  GERI.length = 0;
  CAND = Object.fromEntries(M().candidates.map(c => [c.course, c]));
  active = 0;
  renderModes();
  resetTo(0);
  // Kaydedilmiş program varsa onu göster — kullanıcı kipe TIKLAYINCA ya da
  // ilk açılışta; bir ayar değişikliğinden sonra değil (Faz 53).
  if(i === 0 && !(secenek && secenek.kayitli === false)) startFromSaved();
}
function renderModes(){
  $("#modes").innerHTML = MODES.length < 2 ? "" : MODES.map((m,i) =>
    `<button class="modebtn" aria-pressed="${i===mode}" data-i="${i}">${esc(m.label)}</button>`
  ).join("");
  $("#modes").querySelectorAll(".modebtn").forEach(b =>
    b.addEventListener("click", () => useMode(+b.dataset.i)));
  $("#modeNote").textContent = M().note || "";
}

const sectionOf = (course, crn) => (candOf(course)?.sections || []).find(s => s.crn === crn);
const loadOf = (c) => DATA.unit === "kredi" ? c.credits : c.ects;
const overlap = (a,b) => a.day === b.day && a.start < b.end && b.start < a.end;
const clash = (x,y) => x.meetings.some(m => y.meetings.some(n => overlap(m,n)));

function picks(){
  return sel.map(x => ({cand: candOf(x.course), sec: sectionOf(x.course, x.crn)}))
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
  /* ★★ FAZ 46 — KATLANDI, GİZLENMEDİ.
     Ölçüm (17.09.2026): bu kutu 115px ve 47 kelimeydi ve haftalık ızgaranın
     ÖNÜNDE duruyordu; sayfada aynı anda açık 60 ikincil metin parçasının
     en büyüğüydü. Artık özeti tek satır — ama SAYIYLA, çünkü bu depoda
     "genel uyarı" yasak: kaç ders olduğu kapalıyken de yazıyor. Ayrıntı
     tek tıkla, aynı yerde.
     ⚠️ `open` YOK: kutu kapalı açılıyor. İlk açılışta açık olsaydı
     katlamanın bir anlamı kalmazdı.
     ⚠️ Başlık TEK `<span>` içinde: `<summary>` esnek kutu ve iki ayrı metin
     düğümü arasındaki boşluk yutuluyor ("11 dersbu dönem" çıkıyordu).
     ⚠️⚠️ Şablon dizgesinin İÇİNDE ters tırnak kullanma — JS dizgeyi orada
     kapatıyor ve sayfa komple ölüyor (bu satır o hatadan kaldı). */
  kutu.innerHTML = `
    <details class="arzdetay">
      <summary><span><b>${arz.length} ders</b> bu dönem alınamıyor</span></summary>
      <div class="arzgovde">
        ${satir(acilmamis, "şu ana kadar ilan edilmemiş")}
        ${satir(kapali, "şubeleri başka programlara ayrılmış")}
        <div style="margin-top:6px" class="meta">Veri
          <span class="mono">${esc(veriTarihi())}</span> itibarıyla —
          dönem başında ilanlar kademeli yayınlanıyor.
          <a href="#blockSection" id="arzDetay">Darboğaz bölümünde ayrıntı</a>.</div>
      </div>
    </details>`;
}

/* ★★ FAZ 41 — "KAÇINCI DÖNEMDESİN" BİLİNMİYORSA, PROGRAM BUNU SÖYLER.

   Ölçüm (16.09.2026, yeni kullanıcı yürüyüşü): yalnız bölümünü seçen bir
   öğrenciye kurulan 14 derslik programda plan dönemleri şöyleydi —
   1. dönemden 4, 2.'den 1, 3.'ten 1, 4.'ten 1, 5.'ten 2, 7.'den 3, 8.'den 2.
   Yani birinci sınıf öğrencisi FIZ 101E ile GEO 401E'yi (Physical Geodesy)
   yan yana görüyordu ve ekranda bunu açıklayan tek satır yoktu.

   ⚠️ Motor UYDURMUYOR: dönem bilinmediği için plandaki her açık ders aday.
   Yanlış olan hesap değil, SUNUM — "senin haftalık programın" diye
   gösterilen şey aslında "hiçbir şey bilmezsem en çok bunları alabilirsin".

   ⚠️ Dönemi TAHMİN ETMİYORUZ. Transkript varsa `infer_term` zaten tahmin
   ediyor; hiçbir şey yokken bir sayı uydurmak, projenin kaçındığı şeyin ta
   kendisi olurdu. Bunun yerine: ölçülen dağılımı YAZ, düzeltmeyi bir tık
   uzağa koy. */
function renderDonemUyarisi(){
  const kutu = $("#donemUyari");
  if(!kutu) return;
  const ps = picks();
  /* Dönem biliniyorsa (ayardan ya da transkriptten tahminle) susuyoruz. */
  if(DATA.donem || !ps.length){ kutu.hidden = true; kutu.innerHTML = ""; return; }

  const say = {};
  let dönemsiz = 0;
  ps.forEach(p => {
    const t = p.cand.termNo;
    if(t === null || t === undefined) dönemsiz++;
    else say[t] = (say[t] || 0) + 1;
  });
  const dönemler = Object.keys(say).map(Number).sort((a, b) => a - b);
  if(!dönemler.length && !dönemsiz){ kutu.hidden = true; return; }

  kutu.hidden = false;
  const dökum = dönemler.map(t => `<b>${t}.</b> dönemden ${say[t]}`).join(" · ")
    + (dönemsiz ? ` · plan dönemi yazmayan ${dönemsiz}` : "");
  kutu.innerHTML = `
    <b>Kaçıncı dönemde olduğunu bilmiyorum.</b>
    <div style="margin-top:4px">Bu yüzden aşağıdaki program planın
      <b>${dönemler.length}</b> ayrı döneminden ders karıştırıyor:
      ${dökum}. Alabileceklerinin tamamı bu — <b>bu dönem almanı önerdiğim
      liste değil</b>.</div>
    <div class="dlgactions" style="border:0;padding:0;margin-top:8px;
      justify-content:flex-start">
      <button class="ghost primary" id="donemUyariAc">Dönemi seç</button>
      <span class="meta">5 saniye — sonra “N. dönem + alttan” kipi açılıyor
        ve öneri oraya odaklanıyor.</span>
    </div>`;
  const d = $("#donemUyariAc");
  if(d) d.addEventListener("click", () => termDialog());
}

/* ---------- yazdırma için CRN listesi (Faz 27) ----------
   Ekranda gizli, kâğıtta ızgaranın altında. Kayıt masasında bakılan şey bu:
   hangi CRN, hangi ders, hangi saat. */
function renderPrintCrn(){
  const el = $("#printCrn");
  if(!el) return;
  const ps = picks().slice().sort((a, b) =>
    a.cand.course.localeCompare(b.cand.course));
  if(!ps.length){ el.innerHTML = ""; return; }
  el.innerHTML = `
    <h3 style="margin:8mm 0 3mm;font-size:12pt">Kayıt listesi — ${
      ps.length} ders · ${totals().credits} kredi</h3>
    <table><thead><tr><th>CRN</th><th>Ders</th><th>Ad</th>
      <th>Gün / saat</th><th>Kredi</th></tr></thead>
      <tbody>${ps.map(p => `<tr>
        <td class="mono">${esc(p.sec.crn)}</td>
        <td class="mono">${esc(p.cand.course)}</td>
        <td>${esc((p.cand.name || "").slice(0, 40))}</td>
        <td>${p.sec.meetings.length
          ? p.sec.meetings.map(m =>
              `${DAYS[m.day-1]} ${hhmm(m.start)}–${hhmm(m.end)}`).join("<br>")
          : "saati ilan edilmemiş"}</td>
        <td class="mono">${p.cand.credits}</td>
      </tr>`).join("")}</tbody></table>
    <div style="margin-top:3mm;font-size:9pt">
      ${esc(veriYasiMetni())} · Bu liste bilgilendirme amaçlıdır;
      kaydı OBS'den sen yaparsın.</div>`;
}

/* ---------- tercihin bu programa etkisi (Faz 27) ----------
   ⚠️ Tercih tanımlıysa AMA bu program ona uymuyorsa da yazıyor. Sessiz
   kalmak, "istemiyorum dedim, yine koydu" hissini açıklamasız bırakırdı;
   sebebini söylemek, aracı hatalı sanmayı önlüyor. */
function tercihNotu(){
  const s = M().schedules[active];
  if(!s || !tercihSayisi()) return "";
  const d = s.prefDelta || 0;
  const sebep = (s.prefReasons || []).join(" · ");
  if(!d && !sebep)
    return `<span class="tercihnot ok">tercihlerine uyuyor</span>`;
  return `<span class="tercihnot ${d < 0 ? "uymaz" : "ok"}"
    title="Tercih eleme değil sıralama: uymayan program da gösterilir.">
    tercih ${d > 0 ? "+" : ""}${d}${sebep ? " · " + esc(sebep) : ""}</span>`
    + tercihCaresi(s);
}

/* ★ Faz 37 (fikirler §3.5) — "karşılayamadım" demek yetmiyor: NE BIRAKMALI.
   Tek adımlık, geri alınabilir öneri. Kredi kaybını da yazıyoruz: boş gün
   uğruna sessizce bir zorunlu ders düşmesin. */
function tercihCaresi(s){
  const r = (s && s.prefRelief) || [];
  if(!r.length) return "";
  /* ⚠️ Ek almadan yazıyoruz: "BHB 201E'yi" ile "MAT 103'ü" farklı ekler
     istiyor ve ek doğru seçilemiyor (kod okunuşuna bağlı). Edilgen biçim
     her kodda doğru: "… çıkarılırsa". */
  const ilk = r.slice(0, 2).map(x =>
    `<b class="mono">${esc(x.course)}</b> çıkarılırsa ${esc(x.gains[0])}` +
    ` <span style="color:var(--ink-3)">(−${x.credits} kredi${
      x.required ? ", ZORUNLU ders" : ""})</span>`).join(" · ");
  return `<span class="tercihnot" style="background:transparent;
    color:var(--ink-2)">↳ ${ilk}</span>`;
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
    /* ⚠️ `title` HER sekmede tam metni taşıyor: telefonda ayırt edici
       kısım seçili olmayan sekmede gizleniyor (Faz 46) ve bilgi yalnız
       görsel olarak katlanıyor, yok olmuyor. */
    const tam = `Öneri ${i + 1} · ${s.credits} kredi`
      + oneriFarki(s, i).replace(/<[^>]+>/g, "")
      + (eksik.length ? " · taban ✗: " + eksik.map(g =>
          `${g.role} ${g.missing} kredi`).join(", ") : "");
    /* ⚠️⚠️ Etiketin TAMAMI TEK `<span>` içinde ve bu şart: `.tab` esnek
       kutu (telefonda 44px hedef için), esnek kutu da ÖĞE SINIRINDAKİ
       boşluğu yutuyor. Ölçüldü (390px): "ÖNERİ 1 · 20KREDİ" — `kredi`nin
       önündeki boşluk `.tabfark` esnek öğe olduğu için siliniyordu. Aynı
       sınıf arz başlığında (Faz 46) ve `summary` tabanında (Faz 48) da
       çıktı; burası üçüncüsü.
       ⚠️ KREDİ SAYISI da `.tabfark` içinde: telefonda seçili olmayan sekme
       yalnız "Öneri 2" yazıyor ve üç sekme + Karşılaştır TEK SATIRA sığıyor
       (ölçüldü: 3 satır → 1). Tam metin her sekmenin `title`ında. */
    return `<button class="tab" role="tab" aria-selected="${i===active}" data-i="${i}"
       title="${esc(tam)}"><span class="tabmetin"
       >Öneri ${i+1}<span class="tabfark"> · ${s.credits} kredi${
         oneriFarki(s, i)}</span>${eksik.length
         ? ` <span style="color:var(--danger)">· taban ✗</span>` : ""}</span></button>`;
  }).join("") || oneriYok();
  /* ★ Faz 27 — yan yana karşılaştırma. Sekmeler arasında geçiş vardı ama
     farkı görmek için ızgarayı iki kez ezberlemek gerekiyordu. */
  if(M().schedules.length > 1)
    $("#tabs").innerHTML += `<button class="tab" id="karsilastir">Karşılaştır</button>`;
  $("#tabs").querySelectorAll(".tab[data-i]").forEach(b =>
    b.addEventListener("click", () => { active = +b.dataset.i; resetTo(active); }));
  const k = $("#karsilastir");
  if(k) k.addEventListener("click", karsilastirDialog);
}

/* ★★ FAZ 45 — "öneri üretilemedi" TEK BAŞINA YALAN SAYILIR bir cümle.
   Kilit SERT kısıt: iki kilit birbiriyle çakışırsa ya da kilitli şube
   meşgul saatle çakışırsa motor hiçbir program kuramaz. Kullanıcı o an
   "bu dönem çakışmasız program yok" sanır — oysa sebep kendi koyduğu
   kısıt ve bir tıkla geri alınabilir. Sebebi söylemeyen bir boş ekran,
   bu depoda tekrarlayan hatanın (Faz 25, Faz 44) aynısı olurdu. */
function oneriYok(){
  const kl = kilitliBuKipte();
  if(!kl.length) return `<span class="empty">öneri üretilemedi</span>`;
  /* ⚠️ Uzun cümle BURAYA sığmıyor (ölçüldü: sekme şeridi dar, metin
     kenara değiyor). Kısa sebep burada, ayrıntı + "aç" düğmeleri
     kilit şeridinde — ikisi aynı ekranda. */
  return `<span class="empty" style="color:var(--danger)"
    >öneri üretilemedi — <b>${kl.length} kilit yüzünden</b></span>`;
}

/** Bu kipte GERÇEKTEN bağlayan kilitler (aday havuzunda olanlar). ⚠️ Okunamayan
    ve gölgede kalan satırlar motora girmiyor — bağlayan sayılmaz (Faz 53). */
function kilitliBuKipte(){
  const havuz = new Set((M().candidates || []).map(c => c.course));
  return Object.values(kilitler()).filter(l => havuz.has(l.course));
}

const GUNAD = ["Pzt", "Sal", "Çar", "Per", "Cum"];

/* ---------- sekme etiketinde AYIRT EDİCİ olan (inceleme C4) ----------
   ★ Üç sekme de "ÖNERİ n · 20 KREDİ" yazıyordu; farkı görmek için
   "Karşılaştır"a girmek gerekiyordu — oysa fark zaten hesaplanmış.
   Etiket, o öneriyi ÖBÜRLERİNDEN ayıran tek şeyi taşıyor.

   ⚠️ Ayırt edici bir şey YOKSA hiçbir şey yazmıyoruz: uydurma bir etiket
   ("dengeli", "yoğun") kullanıcıya olmayan bir fark anlatırdı. */
function oneriFarki(s, i){
  const hepsi = M().schedules || [];
  if(hepsi.length < 2 || !s.shape) return "";
  /* ⚠️ KENDİ `shape`'ini kolluyorduk ama ÖBÜRLERİNİNKİNİ okurken
     kollamıyorduk: `shape`siz tek bir öneri (eski önbellek, kısmi durum)
     burada istisna atıyor ve SEKME ÇUBUĞU KOMPLE ÇİZİLMİYORDU. Testte
     ölçüldü. Erişimin tamamı tek yerden ve korumalı. */
  const SEKIL = (x) => (x && x.shape) || {};
  const erken = (x) => SEKIL(x).earliest;
  /* 1) Yalnız BU önerinin boş bıraktığı gün var mı? */
  const benimBos = new Set(s.shape.freeDays || []);
  for(const g of benimBos){
    if(hepsi.every((o, j) => j === i || !(SEKIL(o).freeDays || []).includes(g)))
      return ` · <b>${GUNAD[g-1]} boş</b>`;
  }
  /* 2) En geç başlayan bu mu? */
  const enGec = Math.max(...hepsi.map(x => erken(x) ?? -1));
  if(erken(s) === enGec && hepsi.some(x => (erken(x) ?? -1) < enGec))
    return ` · <b>${hhmm(erken(s))} başlıyor</b>`;
  /* 3) En az kampüs değişimi bu mu? */
  const kampus = (x) => x.campusChanges ?? 0;
  const enAz = Math.min(...hepsi.map(kampus));
  if(kampus(s) === enAz && hepsi.some(x => kampus(x) > enAz))
    return ` · <b>tek kampüs</b>`;
  /* 4) En çok çevrimiçi bu mu? */
  const cevrim = (x) => SEKIL(x).online || 0;
  const enCok = Math.max(...hepsi.map(cevrim));
  if(enCok && cevrim(s) === enCok && hepsi.some(x => cevrim(x) < enCok))
    return ` · <b>${enCok} çevrimiçi</b>`;
  /* 5) En az BEKLEME bu mu? (ölçüldü: üç öneri 218 / 668 / 339 dakika
     boşlukla çıkabiliyor — öğrenci için en somut fark bu, ve `gaps`
     zaten hesaplanıyordu ama hiçbir yerde ayırt edici sayılmıyordu.)
     Eşik 30 dk: birkaç dakikalık farkı "az bekleme" diye satmak,
     olmayan bir üstünlük iddia etmek olurdu. */
  const bosluk = (x) => SEKIL(x).gaps ?? null;
  const benim = bosluk(s);
  if(benim !== null){
    const enAzB = Math.min(...hepsi.map(x => bosluk(x) ?? Infinity));
    if(benim === enAzB && hepsi.some(x => (bosluk(x) ?? Infinity) >= benim + 30))
      return ` · <b>en az bekleme</b>`;
  }
  /* 6) En erken BİTEN bu mu? Aynı eşikle. */
  const gec = (x) => SEKIL(x).latest ?? null;
  if(gec(s) !== null){
    const enErkenBitis = Math.min(...hepsi.map(x => gec(x) ?? Infinity));
    if(gec(s) === enErkenBitis
        && hepsi.some(x => (gec(x) ?? Infinity) >= enErkenBitis + 30))
      return ` · <b>${hhmm(gec(s))}'de bitiyor</b>`;
  }
  return "";
}

/* ---------- önerileri yan yana (Faz 27, yapılacaklar §3.4) ----------
   ★ Karşılaştırmanın ihtiyacı olan şey ders listesi değil, ŞEKİL: hangi
   günler dolu, ne zaman başlıyor, kaç boş gün, arada ne kadar bekleme.
   Ders kodlarını üç kolonda dökmek, farkı bulmayı yine kullanıcıya
   bırakırdı — o zaten sekmelerde yapabiliyordu. */
function karsilastirDialog(){
  const list = M().schedules;
  if(list.length < 2){ openDialog(`<div class="empty">Tek öneri var.</div>`); return; }
  const dersKumeleri = list.map(s => new Set(s.picks.map(p => p.course)));
  /* Hepsinde ortak olan dersler farkı GÖSTERMİYOR; ayıklanınca tabloda
     yalnız gerçekten değişen dersler kalıyor. */
  const ortak = [...dersKumeleri[0]].filter(c => dersKumeleri.every(k => k.has(c)));
  const satir = (baslik, hucre, ipucu) => `<tr>
    <th${ipucu ? ` title="${esc(ipucu)}"` : ""}>${baslik}</th>
    ${list.map((s, i) => `<td class="${i === active ? "secili" : ""}">${hucre(s, i)}</td>`).join("")}
  </tr>`;
  const dk = (m) => m === null || m === undefined ? "—"
    : `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
  openDialog(`
    <div class="eyebrow">Karşılaştırma</div>
    <h2 style="margin-bottom:4px">Öneriler yan yana</h2>
    <p class="modenote" style="margin:2px 0 10px">${ortak.length
      ? `<b class="mono">${ortak.length}</b> ders üçünde de aynı; aşağıda
         yalnız <b>değişenler</b> var.`
      : "Önerilerin ortak dersi yok."}</p>
    <div class="scroll"><table class="cmp">
      <thead><tr><th></th>${list.map((s, i) =>
        `<th class="${i === active ? "secili" : ""}">Öneri ${i + 1}</th>`).join("")}</tr></thead>
      <tbody>
        ${satir("Kredi", s => `<b class="mono">${s.credits}</b>`)}
        ${satir("Ders", s => `<b class="mono">${s.picks.length}</b>`)}
        ${satir("Puan", s => `<b class="mono">${s.score}</b>${
          s.prefDelta ? `<div class="meta ${s.prefDelta < 0 ? "eksi" : "arti"}">
            tercih ${s.prefDelta > 0 ? "+" : ""}${s.prefDelta}</div>` : ""}`,
          "Yüksek puan = bu dönem kaçırmak daha pahalı")}
        ${satir("Dolu günler", s => (s.shape.days || [])
          .map(d => GUNAD[d - 1]).join(" ") || "—")}
        ${satir("Boş gün", s => (s.shape.freeDays || [])
          .map(d => `<b>${GUNAD[d - 1]}</b>`).join(" ") || "—")}
        ${satir("En erken", s => `<span class="mono">${dk(s.shape.earliest)}</span>`)}
        ${satir("En geç", s => `<span class="mono">${dk(s.shape.latest)}</span>`)}
        ${satir("Ders arası bekleme", s => `<span class="mono">${
          Math.round((s.shape.gaps || 0) / 60 * 10) / 10} sa</span>`,
          "Aynı gün içindeki toplam boşluk")}
        ${satir("Kampüs değişimi", s => `<span class="mono">${s.campusChanges}</span>`)}
        ${satir("Çevrimiçi", s => `<span class="mono">${s.shape.online || 0}</span>`)}
        ${list.some(s => s.shape.timeless)
          ? satir("Saati ilan edilmemiş", s => `<span class="mono">${
              s.shape.timeless || 0}</span>`,
              "Bu dersler ızgarada görünmüyor; çakışma denetimine de girmiyor")
          : ""}
        ${satir("Değişen dersler", s => {
          const farkli = s.picks.map(p => p.course).filter(c => !ortak.includes(c));
          return farkli.length
            ? farkli.map(c => `<div class="mono">${esc(c)}</div>`).join("")
            : `<span class="meta">—</span>`;
        })}
        ${satir("", (s, i) => i === active
          ? `<span class="chip">şu an açık</span>`
          : `<button class="ghost" data-sec="${i}">Bunu seç</button>`)}
      </tbody>
    </table></div>`);
  $("#detailBody").querySelectorAll("[data-sec]").forEach(b =>
    b.addEventListener("click", () => {
      $("#detail").close();
      active = +b.dataset.sec;
      resetTo(active);
    }));
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
      `<button class="row${clash.has(i) ? " clash" : ""}${
         it.p.sec.online ? " online" : ""}${
         kilitliMi(it.p.cand.course, it.p.sec.crn) ? " kilit" : ""}"
         data-role="${it.p.cand.role}"
         data-course="${esc(it.p.cand.course)}"
         style="${tonStil(it.p.cand.course, it.p.cand.role)}">
         <span><b class="mono">${esc(it.p.cand.course)}</b>
           ${kilitliMi(it.p.cand.course, it.p.sec.crn)
             ? `<span class="kilitim" role="img"
                  aria-label="${esc(kilitBaslik(it.p.cand.course))}"
                  style="position:static;display:inline-block;
                  vertical-align:-1px;margin-left:4px">${KILIT_SVG}</span>` : ""}
           ${it.p.cand.name ? `<span class="blkad">${esc(it.p.cand.name)}</span>` : ""}
           <small class="mono">${hhmm(it.m.start)}–${hhmm(it.m.end)}
             ${it.p.sec.online ? "çevrimiçi ⌂"
               : `<span title="${esc(yerBaslik(it.m.building))}">${
                    esc(yerYazi(it.m.building))}</span>`}
             · ${esc(it.p.sec.crn)}</small></span>
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
  /* ★ FAZ 40 — ton dağıtımı HER ŞEYDEN ÖNCE. Haftalık program ve kaydedilen
     program aynı haritayı kullanmalı, yoksa aynı ders iki yerde iki tonda
     görünürdü. */
  tonHaritaKur([
    ...picks().map(p => [p.cand.course, p.cand.role]),
    ...((DATA.savedPicks && DATA.savedPicks.picks) || []).map(p => {
      const hit = findSection(p.course, p.crn);
      return [p.course, hit ? hit.cand.role : "ANADAL"];
    }),
  ]);
  renderTabs();
  renderKilitNot();          // Faz 45 — saate kilitli dersler şeridi
  raySayilari();             // Faz 46 — raydaki sayılar kip değişince de doğru
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
    <span>puan <b class="mono">${t.score}</b></span>
    ${tercihNotu()}`;
  $("#editState").hidden = !edited();
  $("#reset").hidden = !edited();
  renderSaveState();
  renderFloor();
  renderArzUyarisi();
  renderDonemUyarisi();
  renderGeri();
  renderPrintCrn();

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

  /* ★★ FAZ 39 — IZGARA KULLANILAN ARALIĞA KIRPILIYOR.
     Ölçüm: 540px'lik ızgaranın **177px'i** (%33) alttaki boş saatlerdi —
     dersler 16:29'da bitiyor, ızgara 21:00'a kadar sürüyordu. Boş satırlar
     günü olduğundan boş gösteriyor ve mobilde ekranı yiyordu.
     ⚠️ Boş hücre BİR ÖZELLİK ("tıkla → o saate uyan dersler"), o yüzden
     saatler SİLİNMİYOR: dolu aralığın bir saat öncesi/sonrası duruyor ve
     gizlenen aralık düğmede AÇIKÇA yazıyor. */
  let ilk = ROWS, son = -1;
  for(let r = 0; r < ROWS; r++)
    for(let d = 1; d <= 5; d++)
      if(cells[`${d}-${r}`] || spans[`${d}-${r}`]){
        if(r < ilk) ilk = r;
        if(r > son) son = r;
      }
  const PAY = 60 / STEP;                    // bir saatlik pay
  let rBas = 0, rSon = ROWS;
  if(son >= 0 && !GRID_TUM){
    rBas = Math.max(0, Math.floor((ilk - PAY) / PAY) * PAY);
    rSon = Math.min(ROWS, Math.ceil((son + 1 + PAY) / PAY) * PAY);
    if(rSon - rBas < 6 * PAY) rSon = Math.min(ROWS, rBas + 6 * PAY);
  }
  const gizli = (rBas > 0 ? 1 : 0) + (rSon < ROWS ? 1 : 0);
  $("#gridAralik").innerHTML = son < 0 ? "" : (GRID_TUM
    ? `<button class="ghost mini" id="gridKisalt">saatleri kısalt</button>`
    : (gizli ? `<button class="ghost mini" id="gridTum">tüm günü göster
         (${hhmm(T0)}–${hhmm(T1)})</button>` : ""));

  let html = `<thead><tr><th></th>${DAYS.map(d=>`<th>${d}</th>`).join("")}</tr></thead><tbody>`;
  for(let r=rBas; r<rSon; r++){
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
      /* ★ Izgara hücresinde artık DERS ADI ve CRN de var (ilk kullanıcı
         incelemesi C1/C2): birinci sınıf öğrencisi "EHB 222E"nin hangi ders
         olduğunu bilmiyor, ve kayıt gününün asıl sayısı CRN.
         ⚠️ Ad hücreye SIĞMAYABİLİR; kesiliyor ama `title` tam adı taşıyor —
         bilgi kaybolmuyor, yalnız yer darsa görünmüyor. */
      const kld = kilitliMi(c.p.cand.course, c.p.sec.crn);
      html += `<td rowspan="${c.span}"><div class="blk ${
          c.p.sec.online ? "online" : ""} ${kld ? "kilit" : ""}"
          data-role="${c.p.cand.role}"
          data-course="${esc(c.p.cand.course)}" tabindex="0" role="button"
          style="${tonStil(c.p.cand.course, c.p.cand.role)}"
          title="${esc([c.p.cand.course, c.p.cand.name, c.p.sec.instructor,
                        "CRN " + c.p.sec.crn,
                        c.p.sec.online ? "çevrimiçi" : yerBaslik(c.m.building),
                        kld ? kilitBaslik(c.p.cand.course) : ""]
                       .filter(Boolean).join(" · "))}">
          ${kld ? `<span class="kilitim">${KILIT_SVG}</span>` : ""}
          <b class="mono">${esc(c.p.cand.course)}</b>
          ${c.p.cand.name ? `<span class="blkad">${esc(c.p.cand.name)}</span>` : ""}
          <small class="mono">${hhmm(c.m.start)}–${hhmm(c.m.end)}
            ${c.p.sec.online ? "çevrimiçi" : esc(yerYazi(c.m.building))}
            · ${esc(c.p.sec.crn)}</small></div></td>`;
    }
    html += `</tr>`;
  }
  $("#grid").innerHTML = html + `</tbody>`;
  $("#grid").querySelectorAll(".blk").forEach(el =>
    bind(el, () => courseDialog(el.dataset.course)));
  $("#grid").querySelectorAll("td.free").forEach(el =>
    bind(el, () => slotDialog(+el.dataset.day, +el.dataset.min)));
  const gt = $("#gridTum"), gk = $("#gridKisalt");
  if(gt) gt.addEventListener("click", () => { GRID_TUM = true;  render(); });
  if(gk) gk.addEventListener("click", () => { GRID_TUM = false; render(); });
  $("#grid").querySelectorAll(".blk.mesgul").forEach(el =>
    bind(el, () => busyDialog(null, null, el.dataset.busy)));

  renderDayList();
  esDersBagla();

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

/* ---------- SAATE KİLİT (Faz 45) ----------
   Kullanıcı isteği 17.09.2026: *"dersleri saate kitleme ve önerilerin onun
   etrafında şekillenmesi"*.

   ★ Kilit `sel` (senin seçimin) DEĞİL, bir AYAR: motora giriyor ve bütün
   öneriler onun etrafında kuruluyor. O yüzden sunucuya yazılıyor ve
   sayfa yenilenince duruyor — "geri al" ile kaybolan bir şey değil.

   ⚠️ Kilit ile "programımda dursun" AYNI ŞEY DEĞİL. Motor bir dersi
   programda tutup ŞUBESİNİ kaydırabiliyor (daha ucuz şube bulunca). Kilit
   şubeyi — dolayısıyla saati — sabitliyor. */
const KILIT_SVG = `<svg viewBox="0 0 12 12" fill="none" aria-hidden="true"
  ><path d="M3.4 5.2V3.6a2.6 2.6 0 0 1 5.2 0v1.6" stroke="currentColor"
    stroke-width="1.3" stroke-linecap="round"/><rect x="2.1" y="5.2" width="7.8"
    height="5.6" rx="1.1" fill="currentColor"/></svg>`;

/** Motorun UYGULADIĞI kilitler (ders → kilit). Okunamayan ya da aynı derse
    ikinci kez yazılmış satırlar burada yok — onlar yalnız şeritte, "uygulanmıyor"
    diye görünüyor. */
function kilitler(){
  const m = {};
  (DATA.locked || []).forEach(l => {
    if(l.tur === "sube" || l.tur === "aralik") m[l.course] = l;
  });
  return m;
}
/* ★★ FAZ 53 — SAAT ARALIĞINA KİLİT. 12:30 veriden seçildi (motor:
   `KILIT_ONAYAR`): hiçbir ders 12:00'de başlamıyor, sabah dersleri en geç
   12:29'da bitiyor, öğleden sonrakiler 12:30'da başlıyor. */
const OGLE = 12 * 60 + 30;
const KILIT_ARALIKLARI = [
  {aralik: "00:00-12:30", lo: 0, hi: OGLE, ad: "sabah", yonelme: "sabaha",
   dugme: "Sabah olsun", aciklama: "12:30'dan önce biten şube"},
  {aralik: "12:30-24:00", lo: OGLE, hi: 1440, ad: "öğleden sonra",
   yonelme: "öğleden sonraya", dugme: "Öğleden sonra olsun",
   aciklama: "12:30'da ya da sonra başlayan şube"},
];
/** Şubenin BÜTÜN saatleri aralıkta mı? Saati ilan edilmemiş şube UYMAZ
    (motordaki `araliga_uyar` ile aynı tanım). */
function araligaUyar(sec, lo, hi){
  const ms = (sec && sec.meetings) || [];
  return ms.length > 0 && ms.every(m => lo <= m.start && m.end <= hi);
}
/** Kilidin kısa adı — rozet, ızgara başlığı ve not aynı sözü kullansın. */
function kilitEtiketi(l){
  if(l.tur !== "aralik") return "CRN " + l.crn;
  const on = KILIT_ARALIKLARI.find(k => k.lo === l.lo && k.hi === l.hi);
  return on ? on.ad : `${hhmm(l.lo)}–${hhmm(l.hi)} arası`;
}
/** "…'e kilitli" için yönelme hâli: sabaha · öğleden sonraya · 10:30–15:30 arasına. */
function kilitYonelme(l){
  if(l.tur !== "aralik") return "CRN " + l.crn + " şubesine";
  const on = KILIT_ARALIKLARI.find(k => k.lo === l.lo && k.hi === l.hi);
  return on ? on.yonelme : `${hhmm(l.lo)}–${hhmm(l.hi)} arasına`;
}
/** Bu ders (istenirse: bu şube) kilidi KARŞILIYOR mu? Aralık kilidinde şube
    serbest; ekrandaki şube aralığa uyuyorsa kilitli sayılır. */
function kilitliMi(course, crn){
  const l = kilitler()[course];
  if(!l) return false;
  if(crn === undefined) return true;
  if(l.tur === "aralik") return araligaUyar(sectionOf(course, crn), l.lo, l.hi);
  return l.crn === crn;
}
/** Kilidi aç/kapat. `crn` ve `aralik` boşsa AÇMA demek (sunucu uçu öyle
    okuyor); aynı kilit yeniden gönderilirse de açılıyor. */
async function kilitYaz(course, crn, btn, aralik){
  const eski = btn ? btn.innerHTML : "";
  if(btn){ btn.disabled = true; btn.textContent = "…"; }
  try{
    applyState(await api("/api/kilit", {course, crn: crn || "", aralik: aralik || ""}));
    const d = $("#detail");
    if(d && d.open) d.close();
  }catch(err){
    /* ⚠️ Burada etiket KORUNUYOR (düğmede kilit simgesi var, yazıya
       çevirmek simgeyi yok ederdi) — hata `title`da ve canlı bölgede. */
    if(btn){ btn.disabled = false; btn.innerHTML = eski;
             btn.title = "hata: " + err.message; }
    say2("hata: " + err.message);
  }
}

function kilitButonu(course, crn){
  /* Statik tek dosyada (`make ui`) yazacak bir yer yok; sahte bir düğme
     göstermek kaydetmediğini gizlemek olurdu (bkz. `watchButton`). */
  if(!DATA.live) return "";
  /* ⚠️ Yalnız ŞUBE kilidi "açık" sayılıyor: ders öğleden sonraya kilitliyken
     bu düğme "Kilidi aç" deseydi, basan kişi hangi kilidi açtığını bilmezdi. */
  const l = kilitler()[course];
  const on = !!l && l.tur !== "aralik" && l.crn === crn;
  return `<button class="ghost" id="kilitBtn" data-course="${esc(course)}"
    data-crn="${esc(crn)}" aria-pressed="${on}"
    style="${on ? "color:var(--ink);border-color:var(--ink)" : ""}"
    >${on ? "Kilidi aç" : "Bu saate kilitle"}</button>`;
}

/* ★★ FAZ 53 — "Bu ders SABAH olsun, şubesi fark etmez" (yapılacaklar 2.4).
   Faz 45'te tek yol bir şube seçip ona kilitlemekti; ölçüldü, o yol
   aralıktaki öbür şubeleri motordan saklıyordu ve 139 denemenin 22'sinde
   hiç program çıkmıyordu. Her düğme o aralığa BÜTÜNÜYLE uyan şube sayısını
   yazıyor — sıfırsa düğme kapalı ve nedeni yazılı (bilinmeyen saatli şube
   sayılmıyor, "sabah" diye iddia edilemez). */
function kilitAralikSatiri(cand){
  if(!DATA.live) return "";
  const l = kilitler()[cand.course];
  const dugmeler = KILIT_ARALIKLARI.map(k => {
    const n = cand.sections.filter(s => araligaUyar(s, k.lo, k.hi)).length;
    const on = !!l && l.tur === "aralik" && l.lo === k.lo && l.hi === k.hi;
    return `<button class="ghost kilitaralik" data-aralik="${k.aralik}"
      data-course="${esc(cand.course)}" aria-pressed="${on}"
      ${n || on ? "" : `disabled title="${esc(k.aciklama)} yok"`}
      >${on ? `${k.ad[0].toLocaleUpperCase("tr") + k.ad.slice(1)} kilidini aç`
             : k.dugme}<span class="kilitsay"> · ${n ? `${n} şube` : "şubesi yok"}</span></button>`;
  }).join("");
  return `<div class="kilitgrup" role="group" aria-label="Saat aralığına kilitle">
    <span class="kilitgrupad">Şube fark etmez, saat önemliyse:</span>${dugmeler}</div>`;
}

/* `disKip`: ders AKTİF kipin havuzunda değil. `oneren`: onu havuzunda tutan
   kipin sırası, yoksa -1.

   ⚠️ Motor kilidi YALNIZ o kipin havuzundaki derse bağlıyor
   (`recommend.build_schedules`: `locked = {… if k in havuzda}`) — yani bu
   kipte kilit SESSİZCE bağlamaz. Düğmeyi gizlemiyoruz (öbür kipte gerçekten
   işe yarıyor); ne yapıp ne yapmayacağını yazıyoruz. */
function kilitNotu(course, crn, disKip, oneren){
  if(!DATA.live) return "";
  if(disKip)
    return `<div class="why" style="margin-top:8px">⚠️ Kilit <b>bu kipte
      bağlamaz</b> — ders bu kipin aday havuzunda değil.${
      oneren >= 0 ? ` Kilitlersen <b>${esc(MODES[oneren].label)}</b> kipinin
      önerilerinde bu şube sabit tutulur.` : ""}</div>`;
  const l = kilitler()[course];
  if(l && l.tur === "aralik")
    return `<div class="why" style="margin-top:8px"><b>${esc(ilkBuyuk(kilitYonelme(l)))}
      kilitli</b>: öneriler bu dersi o saatlere uyan ${l.uyan.length} şubeden
      birinde tutuyor, <b>şubeyi motor seçiyor</b>.${
      kilitliMi(course, crn) ? "" : ` ⚠️ Ekranda duran
      <span class="mono">CRN ${esc(crn)}</span> bu aralığın <b>dışında</b> —
      elle değiştirdiysen öneriye dönünce kilit yine uygulanır.`}
      "Bu saate kilitle" dersen aralık kilidi <b>bu şubeye</b> dönüşür.</div>`;
  if(l && l.crn !== crn)
    return `<div class="why" style="margin-top:8px">Bu ders
      <span class="mono">CRN ${esc(l.crn)}</span> şubesine kilitli; ekranda
      duran <span class="mono">CRN ${esc(crn)}</span>. Kilitlersen kilit
      <b>bu şubeye taşınır</b> — bir derste tek kilit olabilir.</div>`;
  if(l)
    return `<div class="why" style="margin-top:8px">Saate kilitli: öneriler
      bu dersi <b>bu şubede</b> tutup <b>etrafında</b> kuruluyor.</div>`;
  return `<div class="why" style="margin-top:8px">Kilitlersen motor bu dersi
    <b>bu şubede</b> tutar ve programın kalanını etrafında kurar. Kilitlemezsen
    ders programda kalabilir ama <b>şubesi (dolayısıyla saati) kayabilir</b>.
    Şube değil yalnız saat önemliyse <b>sabaha</b> ya da <b>öğleden sonraya</b>
    kilitle — motor o saatlerdeki bütün şubeleri dener.</div>`;
}

/** Izgara/gün listesi için: "sabaha kilitli" · "CRN 13601 şubesine kilitli".
    ⚠️ Telefon satırında simge `aria-hidden`dı; ekran okuyucu kilidi hiç
    duymuyordu (Faz 53'te fark edildi) — artık bu metin simgenin adı. */
function kilitBaslik(course){
  const l = kilitler()[course];
  return l ? kilitYonelme(l) + " kilitli" : "";
}

function ilkBuyuk(s){
  return s ? s[0].toLocaleUpperCase("tr") + s.slice(1) : s;
}

function wireKilit(){
  const b = $("#kilitBtn");
  /* ⚠️ Şube düğmesi yalnız ŞUBE kilidini açar; ders bir aralığa kilitliyken
     basmak, aralık kilidini BU ŞUBEYE çevirir (sunucu: bir derste tek kilit). */
  if(b) b.addEventListener("click", () => {
    const l = kilitler()[b.dataset.course];
    const acik = !!l && l.tur !== "aralik" && l.crn === b.dataset.crn;
    kilitYaz(b.dataset.course, acik ? "" : b.dataset.crn, b);
  });
  document.querySelectorAll("#detail .kilitaralik").forEach(d =>
    d.addEventListener("click", () =>
      /* Aynı aralık yeniden gönderilince sunucu kilidi AÇIYOR. */
      kilitYaz(d.dataset.course, "", d, d.dataset.aralik)));
}

/** Izgaranın üstündeki şerit: hangi dersler kilitli, biri tutmuyorsa neden. */
function renderKilitNot(){
  const el = $("#kilitNot");
  if(!el) return;
  const list = DATA.locked || [];
  if(!list.length){ el.hidden = true; return; }
  el.hidden = false;
  /* ★ Faz 53: motorun UYGULADIĞI kilitler ile uygulamadığı satırlar ayrı.
     Elle yazılıp okunamayan (`"BLG 351E@8.30-12.30"`) ya da aynı derse
     ikinci kez yazılmış satır motora GİRMİYOR — ve bu söyleniyor. Faz 45'te
     `_kilit_ayikla` onları atlıyordu, docstring "arayüz söylüyor" diyordu
     ama hiçbir yerde görünmüyorlardı. */
  const uygulanan = list.filter(l => l.tur === "sube" || l.tur === "aralik");
  const okunmayan = list.filter(l => l.tur === "bozuk" || l.tur === "golge");
  const ad = (l) => `<span class="mono">${esc(l.course)}</span>`;
  const satirAd = (l) => `<span class="mono">${esc(l.satir)}</span>`;
  /* ★ Sunucusuz tek dosyada (`make ui`) kilit YİNE UYGULANIYOR — ayardan
     okunuyor — ama açılamıyor. Düğmeleri göstermek yerine bunu yazıyoruz;
     tıklanınca hiçbir şey yapmayan bir düğme, kaydetmediğini gizlerdi. */
  if(!DATA.live){
    el.innerHTML = `<b>${uygulanan.length} ders saate kilitli</b>
      (${uygulanan.map(l => `${ad(l)} · ${esc(kilitEtiketi(l))}`).join(", ")}).
      Öneriler bunların etrafında kuruldu.${okunmayan.length ? ` ⚠️
      ${okunmayan.length} kilit satırı <b>uygulanmıyor</b>
      (${okunmayan.map(satirAd).join(", ")}).` : ""} Kilidi açmak için
      <span class="mono">make app</span> ile aç ya da
      <span class="mono">settings.toml</span> içindeki
      <span class="mono">kilitli</span> satırını düzenle.`;
    return;
  }
  const kirik = uygulanan.filter(l => !l.ok);
  el.classList.toggle("tutmuyor", kirik.length > 0 || okunmayan.length > 0 ||
    (!(M().schedules || []).length && !!kilitliBuKipte().length));
  const rozet = uygulanan.map(l => `<button class="ghost mini" data-ac="${esc(l.course)}"
      title="kilidi aç">${esc(l.course)} · ${esc(kilitEtiketi(l))}${
      l.ok ? "" : " ✗"} ✕</button>`).join("") +
    okunmayan.map(l => `<button class="ghost mini" data-satir="${esc(l.satir)}"
      title="bu satırı sil">${esc(l.satir)} ✗ ✕</button>`).join("");
  /* ⚠️ TUTMAYAN kilit gizlenmiyor. Dönem/şube değişince CRN kaybolabiliyor;
     satırı sessizce düşürseydik kullanıcı "kilitlemiştim, saati neden
     kaydı?" diye sorardı — ya da daha kötüsü, hiç sormazdı. */
  /* ★ EKRANDAKİ ŞUBE İLE KİLİT AYRIŞMIŞ olabilir: kilitli bir dersin
     şubesini elle değiştirmek kilidi TAŞIMIYOR (ayara sessizce yazmak
     istemiyoruz). O zaman ızgarada kilit rozeti de çıkmıyor ve kullanıcı
     kilidin düştüğünü sanabilir. Ayrışmayı burada söyleyip taşımayı tek
     düğmeye indiriyoruz. Aralık kilidinde ayrışma = ekrandaki şube
     aralığın DIŞINDA (Faz 53). */
  const kayan = uygulanan.map(l => {
    const s = sel.find(x => x.course === l.course);
    return (s && !kilitliMi(l.course, s.crn)) ? {l, crn: s.crn} : null;
  }).filter(Boolean);
  /* ★★ SONUÇ BOŞSA SEBEBİ BURADA YAZILI. Kilit sert kısıt: iki kilit
     çakışırsa ya da kilitli şube meşgul saate denk gelirse motor hiçbir
     program kuramıyor. Sekme şeridinde yalnız kısa sebep var; hangi
     kilitlerin bağladığı ve nasıl açılacağı burada.
     ⚠️ Faz 53'e kadar bu cümle BAZEN YANLIŞTI: düşük puanlı tek bir derse
     kilit (ör. ALM 102) motoru bütçe tükenene kadar ölü dallarda
     dolaştırıyor ve hiç program çıkmıyordu — tek kilit, hiç meşgul saat
     yokken "birbiriyle çakışıyor" deniyordu. Motor artık kilitli dersi
     önce yerleştiriyor; boş sonuç gerçekten bir çakışma demek. */
  const bagli = kilitliBuKipte();
  /* Kilit duruyor ve şubesi açık (`ok`), ama ders BU kipin havuzunda yok. */
  const kapsamDisi = uygulanan.filter(l => l.ok && !bagli.includes(l));
  const kipAdi = (course) => {
    const i = MODES.findIndex(m => (m.candidates || []).some(c => c.course === course));
    return i >= 0 ? MODES[i].label : "";
  };
  const bosSonuc = !(M().schedules || []).length;
  const neden = (l) => l.neden === "sube" ? `CRN ${esc(l.crn)} bu kipte açık değil`
    : l.neden === "aralik" ? `bu dersin <b>${esc(kilitEtiketi(l))}</b> saatlerine
        bütünüyle uyan şubesi yok`
    : "bu ders artık aday listesinde yok";
  el.innerHTML = `${uygulanan.length ? `<b>${uygulanan.length} ders saate kilitli.</b>` : ""}
    ${/* ⚠️ Giriş cümlesi KOŞULLU: kilitlerin hepsi bu kipin havuzu dışındaysa
          "etrafında kuruluyor" demek düpedüz yanlış olurdu — motor onları bu
          kipte hiç görmüyor (Faz 49). */ ""}
    ${!uygulanan.length ? "" : bagli.length ? `Öneriler ${bagli.length < uygulanan.length
        ? `bu kipte bağlayan <b>${bagli.length}</b> dersin`
        : "bu derslerin"} saatini sabit tutup <b>etrafında</b> kuruluyor.`
      : `<b>Bu kipte hiçbiri bağlamıyor.</b>`}
    ${bosSonuc && bagli.length ? `<div style="margin-top:6px;color:var(--danger)">
      <b>Bu kipte hiçbir program kurulamadı</b> — bu kipte bağlayan
      ${bagli.length} kilit (${bagli.map(ad).join(", ")})
      birbiriyle ya da meşgul saatinle çakışıyor. Aşağıdan birini aç.
      </div>` : ""}
    ${kirik.length ? `<div style="margin-top:6px;color:var(--danger)">
      ${kirik.map(l => `${ad(l)} kilidi <b>tutmuyor</b> — ${neden(l)}.`).join("<br>")}
      </div>` : ""}
    ${okunmayan.length ? `<div style="margin-top:6px;color:var(--danger)">
      ${okunmayan.map(l => `${satirAd(l)} <b>uygulanmıyor</b> — ${l.tur === "golge"
        ? `aynı derse sonra yazılan kilit geçerli`
        : `okunamadı; biçim <span class="mono">DERS@CRN</span> ya da
           <span class="mono">DERS@SS:DD-SS:DD</span>`}.`).join("<br>")}
      </div>` : ""}
    ${/* ★★ FAZ 49 — KAPSAM DIŞI KİLİT. Motor kilidi yalnız o kipin
          havuzundaki derse bağlıyor; kilitli üst dönem dersi "5. dönem +
          alttan" kipinde sessizce yok sayılıyordu ve şerit yine
          "etrafında kuruluyor" diyordu. Tutmayan kilitle aynı sınıf:
          söylenmeden bırakılamaz, ama HATA da değil — öbür kipte
          çalışıyor, o yüzden kırmızı değil. */ ""}
    ${kapsamDisi.length ? `<div style="margin-top:6px">
      ${kapsamDisi.map(l => `${ad(l)} kilidi <b>bu kipte bağlamıyor</b> —
        ders bu kipin aday havuzunda değil${
        kipAdi(l.course) ? `; <b>${esc(kipAdi(l.course))}</b> kipinde bağlıyor`
                         : ""}.`).join("<br>")}
      </div>` : ""}
    ${kayan.length ? `<div style="margin-top:6px">
      ${kayan.map(k => `${ad(k.l)} ekranda <span class="mono">CRN ${esc(k.crn)}</span>,
        kilit <span class="mono">${esc(kilitEtiketi(k.l))}</span>${k.l.tur === "aralik"
          ? " — ekrandaki şube bu saatlerin dışında" : ""} —
        <button class="ghost mini" data-tasi="${esc(k.l.course)}"
          data-crn="${esc(k.crn)}">${k.l.tur === "aralik"
            ? "kilidi bu şubeye çevir" : "kilidi buraya taşı"}</button>`).join("<br>")}
      </div>` : ""}
    <div class="kilitsatir">${rozet}
      ${list.length > 1 ? `<button class="ghost mini" id="kilitHepsi"
        >hepsini aç</button>` : ""}</div>`;
  el.querySelectorAll("[data-ac]").forEach(b =>
    b.addEventListener("click", () => kilitYaz(b.dataset.ac, "", b)));
  el.querySelectorAll("[data-satir]").forEach(b =>
    b.addEventListener("click", async () => {
      b.disabled = true;
      try{ applyState(await api("/api/kilit", {satir: b.dataset.satir})); }
      catch(e){ hataBildir(b, e); }
    }));
  el.querySelectorAll("[data-tasi]").forEach(b =>
    b.addEventListener("click", () => kilitYaz(b.dataset.tasi, b.dataset.crn, b)));
  const h = $("#kilitHepsi");
  if(h) h.addEventListener("click", async () => {
    h.disabled = true; h.textContent = "…";
    /* ★ Her çağrı TAM DURUMU döndürüyor (`dispatch` snapshot ekliyor);
       sonuncusunu uygulamak yeter. Ayrı bir "durumu tazele" uçu POST
       kabul etmiyor — oraya gitmek sessiz bir hata olurdu.
       ⚠️ Faz 53: her satır KENDİSİYLE siliniyor — okunamayan satırın ders
       kodu bile olmayabilir (`"@123"`), ders koduyla silmek onu bırakırdı. */
    let son = null;
    for(const l of list){
      try{ son = await api("/api/kilit", {satir: l.satir}); }
      catch(e){ hataBildir(h, e); return; }
    }
    if(son) applyState(son);
  });
}

function choose(course, crn){
  const cand = candOf(course), sec = sectionOf(course, crn);
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
  /* ★★ FAZ 51 — PENCERENİN ADI. Ölçüldü: altı pencerenin HİÇBİRİNDE
     `aria-label`/`aria-labelledby` yoktu; ekran okuyucu açılışta yalnız
     "iletişim kutusu" diyordu — hangi ders, hangi saat, ne penceresi
     olduğu söylenmiyordu. Hepsinin ilk başlığı zaten bir `<h2>`; adı
     ondan TÜRETİYORUZ, tek yerde, yeni pencereler dahil.
     ⚠️ Elle yazılmış bir ada gerek yok: ikisi ayrışırsa ekranda bir şey,
     kulakta başka bir şey olurdu. */
  pencereAdiVer($("#detail"), $("#detailBody"));
  $("#detail").showModal();
}

function optionRow(cand, section, note){
  const times = section.meetings.length
    ? section.meetings.map(m =>
        `${DAYS[m.day-1]} ${hhmm(m.start)}–${hhmm(m.end)} <span title="${
           esc(yerBaslik(m.building))}">${esc(yerYazi(m.building))}</span>`).join("<br>")
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

/* ---------- "neden bu puan" (Faz 27, yapılacaklar §3.1) ----------
   ★ Gerekçe METNİ vardı ("119 dersin önşartı") ama bunun puana 30 mu 3 mü
   kattığı görünmüyordu. Sıralamaya güvenmek için ağırlığın büyüklüğünü
   görmek gerekiyor.

   ⚠️ Çubuk MUTLAK değere göre ölçekleniyor: eksi katkılar (ertelenebilir
   ders −20) da aynı görsel dilde okunmalı, yoksa "puanı düşüren şey" hiç
   görünmüyor. */
function puanKirilimi(cand){
  const parts = cand.parts || [];
  if(!parts.length) return "";
  const enBuyuk = Math.max(...parts.map(p => Math.abs(p.points)), 1);
  const toplam = parts.reduce((a, p) => a + p.points, 0);
  return `<details class="puan"${parts.length <= 3 ? " open" : ""}>
    <summary>Puan <b class="mono">${cand.score}</b> — neden?</summary>
    <div class="puanliste">${parts.map(p => `
      <div class="puansatir ${p.points < 0 ? "eksi" : ""}">
        <span class="ad">${esc(p.label)}</span>
        <span class="bar"><i style="width:${
          (Math.abs(p.points) / enBuyuk * 100).toFixed(0)}%"></i></span>
        <span class="mono deger">${p.points > 0 ? "+" : ""}${p.points}</span>
      </div>`).join("")}</div>
    <div class="puantoplam">toplam <b class="mono">${Math.round(toplam * 10) / 10}</b>
      · yüksek puan = <b>bu dönem kaçırmak daha pahalı</b>, "daha iyi ders" değil</div>
  </details>`;
}

/* ---------- geçmiş dönem not dağılımı (Faz 38) ----------
   İTÜ her dönem ders bazında harf notu dağılımı yayınlıyor
   (obs.itu.edu.tr/public/DersNotDagilimi). Bu bölüm o veriyi GÖSTERİR;
   öneri puanına GİRMEZ.

   ⚠️ Dört şeyi açıkça yazmak zorundayız, yoksa sayı olduğundan fazlasını
   iddia eder:
     1. Dağılım TR+EN kodun İKİSİNİ birden kapsıyor (kaynak öyle yayınlıyor).
     2. GEÇMİŞ bir döneme ait; hocası, sınavı, kontenjanı değişmiş olabilir.
     3. VF (devamsızlık) FF'ten AYRI — devamsızlık dersin zorluğu değil.
     4. Ortalama yalnız harf notu alanlardan; VF ölçeğe girmiyor. */
function notDagilimi(cand){
  const g = cand && cand.grades;
  if(!g || !g.terms || !g.terms.length) return "";
  const secim = ND_SECIM[cand.course] || {};
  const donem = g.terms.find(t => t.term === (secim.term || g.selected))
             || g.terms[0];
  if(!donem || !donem.n) return "";
  const artili = !!secim.artili;

  /* ★ Faz 38b — VARSAYILAN 9 KOVA, 15 harf DEĞİL.
     Geri bildirim: "+ lar yüzünden dağılım kötü gözüküyor". 15 ince sütun
     dağılımın ŞEKLİNİ kaybettiriyordu. Artı temel harfle aynı kovada;
     ⚠️ bu bir kayıp (BA+ ≠ BA), o yüzden yazıyor ve bir tıkla geri geliyor.
     Ortalama HER ZAMAN 15 harften — kova yalnız çizim için. */
  const kutu = artili
    ? ND_HARF.map(k => ({key: k, total: donem.counts[k] || 0,
                         parts: [{grade: k, n: donem.counts[k] || 0}]}))
    : donem.buckets;
  const enBuyuk = Math.max(...kutu.map(b => b.total), 1);
  const bar = kutu.map(b => {
    const kotu = (b.key === "FF" || b.key === "VF");
    const kirilim = b.parts.length > 1
      ? b.parts.map(p => `${p.grade}: ${p.n}`).join(" · ")
      : `${b.key}: ${b.total} kişi`;
    return `<div class="ndsut" title="${esc(kirilim)}">
      <b>${b.total}</b>
      <i class="${kotu ? "kotu" : ""}" style="height:${
        b.total ? Math.max(3, b.total / enBuyuk * 100).toFixed(0) : 0}%"></i>
      <span>${b.key}</span></div>`;
  }).join("");

  /* Dönem seçici — OBS'nin kendi sayfasında da var. Elimizdeki her dönem. */
  const sekme = g.terms.length > 1 ? `<div class="ndsekme">${
    g.terms.map(t => `<button class="ndtab${t.term === donem.term ? " sec" : ""}"
      data-ndterm="${esc(t.term)}" data-ndcourse="${esc(cand.course)}"
      >${esc(t.yearName)} ${esc(t.season)} <span>n=${t.n}</span></button>`)
      .join("")}</div>` : "";

  /* ⚠️ Yarıyıl uyuşmuyorsa SESSİZ kalmıyoruz. Bir güz dersinin bahar
     dağılımı çoğunlukla birkaç bütünlemeci demek — sayı var ama dersi
     anlatmıyor. Ölçüm: 176 dersin 36'sında güz verisi yok. */
  const yanlisMevsim = !!g.wantedSeason && donem.season !== g.wantedSeason;
  const uyari = yanlisMevsim ? `<div class="ndmevsim">⚠ Bu ders için
    <b>${esc(g.wantedSeason)}</b> dönemi dağılımı elimizde yok;
    <b>${esc(donem.season)}</b> dönemi gösteriliyor. Farklı yarıyılda dersi
    çoğunlukla <b>tekrar alanlar</b> alır — bu dağılım dersin normal
    dönemini anlatmayabilir.</div>` : "";

  return `<details class="puan" data-ndbox="${esc(cand.course)}">
    <summary>Not dağılımı — <b class="mono">${donem.n}</b> kişi,
      geçen <b class="mono">%${donem.passRate}</b></summary>
    ${sekme}${uyari}
    <div class="ndgrafik${artili ? " genis" : ""}">${bar}</div>
    <div class="ndozet">
      <span>ortalama <b class="mono">${donem.meanPoints ?? "—"}</b></span>
      <span>FF <b class="mono">%${donem.failRate}</b></span>
      <span title="Devamsızlıktan kalma — dersin zorluğu hakkında bir şey söylemez">
        VF <b class="mono">%${donem.absentRate}</b></span>
      <span>${esc(donem.yearName)} ${esc(donem.season)}</span>
      <button class="ghost mini" data-ndplus="${esc(cand.course)}"
        >${artili ? "artıları birleştir" : "artıları ayır"}</button>
    </div>
    <div class="puantoplam">
      ${artili ? "15 harf ayrı gösteriliyor."
        : "<b>Artılar temel harfle birlikte</b> sayıldı (BA+ → BA); şeklin "
          + "okunabilmesi için. Ayrıntı için üstteki düğme; <b>ortalama her "
          + "zaman 15 harften</b> hesaplanıyor."}
      <br>Kaynak: İTÜ ÖBS Ders Not Dağılımı · <b>${g.codes.map(esc).join(" + ")}</b>
      birlikte (OBS Türkçe ve İngilizce kodu ayırmıyor)${
      g.terms.length > 1 ? ` · elimizde ${g.terms.length} dönem var` : ""}.${
      /* ⚠️ Kaynağın kendi toplamı harflerin toplamına her zaman eşit değil
         (ölçüm: MAT 103 güz 2988/2987). Farkı yazmamak, sayıyı olduğundan
         kesin gösterirdi. */
      donem.gap ? `<br>OBS toplamı <b class="mono">${donem.announced}</b>;
        harflerin toplamı <b class="mono">${donem.n}</b> — ${donem.gap} kişi
        listelenen 15 harfin dışında (BL/BZ/muafiyet olabilir).` : ""}
      <br>⚠️ <b>Geçmiş</b> bir döneme ait: hoca, sınav ve kontenjan değişmiş
      olabilir. Öneri puanına <b>girmiyor</b> — hangi dersin değdiği senin
      kararın. Ortalama aracın kendi GNO ölçeğiyle: <b>FF</b> de <b>VF</b> de
      sıfır puan. <b>VF devamsızlıktır</b>, dersin zorluğu değil.
    </div>
  </details>`;
}

/* Ders penceresinde seçili dönem / artı kırılımı — pencere kapanınca
   unutuluyor, kalıcı bir tercih DEĞİL. */
const ND_SECIM = {};
const ND_HARF = ["AA","BA+","BA","BB+","BB","CB+","CB","CC+","CC",
                 "DC+","DC","DD+","DD","FF","VF"];

function ndBagla(course){
  const kutu = $(`[data-ndbox="${CSS.escape(course)}"]`);
  if(!kutu) return;
  const yenile = () => {
    const acik = kutu.open;
    /* ⚠️ `candOf` — `CAND` DEĞİL: pencere artık kipin havuzunda olmayan
       ders için de açılıyor (Faz 49); burada `CAND` kalsaydı dönem sekmesine
       basınca not dağılımı kutusu boşalırdı. */
    kutu.outerHTML = notDagilimi(candOf(course));
    const yeni = $(`[data-ndbox="${CSS.escape(course)}"]`);
    if(yeni){ yeni.open = acik; ndBagla(course); }
  };
  kutu.querySelectorAll("[data-ndterm]").forEach(b =>
    b.addEventListener("click", e => {
      e.preventDefault();
      ND_SECIM[course] = {...(ND_SECIM[course] || {}), term: b.dataset.ndterm};
      yenile();
    }));
  const p = kutu.querySelector("[data-ndplus]");
  if(p) p.addEventListener("click", e => {
    e.preventDefault();
    const s = ND_SECIM[course] || {};
    ND_SECIM[course] = {...s, artili: !s.artili};
    yenile();
  });
}

/* ★★ FAZ 49 — IZGARADAKİ DERSE TIKLANAMIYORDU (kullanıcı 18.09.2026:
   *"x.dönem + alttan kısmında kaydettiğim program yüklenince üstten olan
   derslere tıklayamıyorum"*).

   Ölçüldü (gerçek veri, "5. dönem + alttan"): açılışta kaydedilen program
   yükleniyor, ızgarada 14 ders var, bunların **5'i** (GEO 401E, ATA 121,
   TUR 121, GEO 464E, SNT 103E) kipin 11 kişilik havuzunda YOK. O beşine
   tıklayınca hiçbir şey olmuyordu: ne pencere, ne hata, ne açıklama.

   Sebep tek kelimeydi: pencere dersi `CAND` (AKTİF KİPİN havuzu) üzerinden
   çözüyordu. Oysa ızgara `candOf` ile çiziliyor — o, kipte yoksa tam havuza
   düşüyor. Yani ekranda çizilen ama açılamayan ders çıkıyordu.

   ⚠️ Bu depoda kip politikası zaten yazılıydı (27.08.2026, boş saat
   penceresi): *"kip yalnız ÖNERİYİ daraltıyor, elle ekleme hakkını değil."*
   Pencere o politikadan habersizdi. Artık `choose`, `sectionOf`, `picks` ve
   ızgarayla aynı yerden okuyor.

   ⚠️ Açmak yetmez: ders bu kipin havuzunda olmadığını SÖYLEMELİ, yoksa
   "çıkardım, geri gelmedi" sessiz bir şaşkınlık olurdu. */
function courseDialog(course){
  const cand = candOf(course), cur = sel.find(x => x.course === course);
  if(!cand || !cur) return;
  const disKip = !CAND[course];
  const onerenKip = disKip
    ? MODES.findIndex(m => (m.candidates || []).some(c => c.course === course))
    : -1;
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
      ${cand.credits} kredi · ${cand.ects} AKTS
      ${cand.reasons.length ? "<br>" + cand.reasons.map(esc).join("; ") : ""}</div>
    ${disKip ? `<div class="why" style="margin-top:8px">Bu ders
      <b>${esc(M().label || "bu kip")}</b> kipinin aday havuzunda değil —
      programında duruyor ve buradan şubesini değiştirebilirsin, ama bu kip
      onu <b>kendiliğinden önermez</b>: çıkarırsan geri getirmez.
      ${onerenKip >= 0 ? `Öneren kip: <b>${esc(MODES[onerenKip].label)}</b>.`
        : ""}</div>` : ""}
    ${puanKirilimi(cand)}
    ${notDagilimi(cand)}
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
      ${kilitButonu(cand.course, cur.crn)}
      ${watchButton(cand.course)}
    </div>
    ${kilitAralikSatiri(cand)}
    ${kilitNotu(cand.course, cur.crn, disKip, onerenKip)}
    ${watchNote(cand.course)}`);
  const rm = $("#removeCourse");
  if(rm) rm.addEventListener("click", () => { $("#detail").close(); removeCourse(course); });
  wireKilit();
  wireWatch();
  ndBagla(course);            // dönem sekmeleri + artı kırılımı (Faz 38b)
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
      <span class="mono">make watch</span> çalışınca bunlar taranır
      (arka planda: <span class="mono">make watch-kur</span>).</div>`;
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
      applyState(r, {koru: true});
      $("#detail").close();
    }catch(err){ hataBildir(b, err); }
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
  /* ★★ TAM HAVUZDAN (kullanıcı isteği 27.08.2026): "x.dönem + alttan"
     kipinde bile boş saate tıklayınca o saatte alınabilecek HER ders
     görünsün. Kip yalnız öneriyi daraltıyor; elle ekleme hakkını değil.
     Aktif kipte olmayan ders "üst dönem" diye işaretleniyor — gizlemiyoruz,
     sebebini yazıyoruz. */
  const aktif = new Set(M().candidates.map(c => c.course));
  const disinda = (kod) => !aktif.has(kod);
  const collect = (near) => {
    const rows = [];
    for(const cand of (DATA.candidates || [])){
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
      /* ⚠️ Aktif kipin dışındaki ders "üst dönem" diye SÖYLENİYOR: gizlemek
         "bu saatte ders yok" sanılmasına, susup eklemek de kipin sözünü
         bozmasına yol açardı. Kullanıcı bilerek ekliyor. */
      const notlar = [];
      if(drop.length) notlar.push("çıkarılır: " + drop.join(", "));
      if(disinda(cand.course)) notlar.push("üst dönem — bu kipte önerilmez");
      rows.push([-(drop.length * 10000) - dist % 10000 + cand.score / 1000
                 - (disinda(cand.course) ? 5 : 0),   // kip içi önce sıralanır
        optionRow(cand, pick, notlar.join(" · ")),
        cand.course, drop.length]);   // [3] = kaç ders düşer (Faz 44)
    }
    rows.sort((a,b) => b[0]-a[0]);
    return rows;
  };
  const near = collect(true);
  const nearCodes = new Set(near.map(r => r[2]));
  const rest = collect(false).filter(r => !nearCodes.has(r[2]));
  /* ★★ FAZ 44 — "EKLENEBİLİR" İLE "TAKAS" AYRILDI.
     Kullanıcı 17.09.2026: *"x.dönem + alttan kısmında takvime tıklayıp
     ekstra ders eklenemiyor"*. Ölçüldü, haklıydı:

       "N. dönem + alttan" kipi — 38 boş hücrenin **27'sinde (%71)** sunulan
       seçeneklerin HEPSİ mevcut bir dersi çıkarıyordu; yalnız 10 hücrede
       hiçbir şey düşürmeyen bir seçenek vardı.
       `all` kipi — 56 hücrenin 24'ünde yalnız takas, **hiçbirinde** temiz
       ekleme yoktu.

     Motor yanlış değil: hafta 14 dersle dolu, boş hücreler derslerin
     ARASINDAKİ boşluklar ve aday şubelerin çoğu 2–3 saatlik, komşu derse
     taşıyor. Yanlış olan SUNUM — "çıkarılır: GEO 321E" notu her satırın
     içine gömülüydü, liste "ekleyebileceğin dersler" gibi duruyordu.
     Kullanıcı tek tek okuyup "hiçbirini ekleyemiyorum" sonucuna varıyordu.

     ⚠️ Takas seçenekleri GİZLENMİYOR: bazen gerçekten istenen şey odur
     ("şunun yerine bunu koy"). Yalnız ayrı başlık altına alınıyor ve ne
     kaybedileceği başlıkta yazıyor. */
  const temiz = (r) => r[3] === 0;
  const nearT = near.filter(temiz), nearX = near.filter(r => !temiz(r));
  const restT = rest.filter(temiz), restX = rest.filter(r => !temiz(r));
  const hicTemiz = !nearT.length && !restT.length;
  const varTakas = nearX.length + restX.length;
  const grup = (baslik, cls, liste) => liste.length
    ? `<div class="chipline"><span class="chip ${cls}">${baslik}</span>
         <span style="color:var(--ink-3);font-size:12px">${liste.length} ders</span></div>
       <div class="optlist">${liste.slice(0, 12).map(r => r[1]).join("")}</div>` : "";
  openDialog(`
    <div class="eyebrow">Boş saat</div>
    <h2>${DAYS[day-1]} ${hhmm(min)}</h2>
    ${hicTemiz && varTakas ? `<div class="note" style="margin-bottom:12px">
        <b>Bu saate çakışmadan sığan ders yok.</b>
        <div style="margin-top:4px">Aşağıdaki <b>${varTakas}</b> dersten biri
        için programında <b>yer açman</b> gerekiyor — her birinin altında
        hangi dersin çıkacağı yazılı.</div></div>` : ""}
    ${grup("buraya sığıyor", "", nearT)}
    ${grup(DAYS[day-1] + " günü, başka saatte sığıyor", "", restT)}
    ${grup("yer açman gerekiyor — bu saat civarı", "unknown", nearX)}
    ${grup("yer açman gerekiyor — " + DAYS[day-1] + " günü", "unknown", restX)}
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
      }catch(err){ hataBildir(btn, err); }
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
        label: $("#fAd").value}), {});   // kip korunur (Faz 54)
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
  return `<span class="cap ${sinif}" title="${esc(veriTarihi())} itibarıyla — güncel doluluk OBS'de">
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

/* Aday tablosunun yatay kaydırma ipucu (Faz 46). Aynı desen eski bölüm
   çubuğundaydı; çubuk kalktı, ipucu gereken yere taşındı. */
function listeKenarSolmasi(){
  const w = $("#candWrap");
  if(!w) return;
  const guncelle = () => {
    const sonda = w.scrollLeft + w.clientWidth >= w.scrollWidth - 2;
    const basta = w.scrollLeft <= 2;
    w.dataset.more = w.scrollWidth <= w.clientWidth + 2 ? "none"
      : basta ? "right" : sonda ? "left" : "both";
  };
  guncelle();
  w.onscroll = () => requestAnimationFrame(guncelle);
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
        ${c.prereqUnknown ? `<span class="chip unknown"
          style="margin-left:6px" title="Önşart metni var ama okunamadı — danışmanına sor">önşart okunamadı</span>`
          : (c.prereqMissing ? `<span class="chip unknown" style="margin-left:6px"
              title="Katalogda önşart metni yok — 'önşartı yok' demek DEĞİL. OBS'den doğrula.">önşart bilgisi yok</span>` : "")}
        ${c.sections.every(s => s.online)
          ? `<span class="chip online" style="margin-left:6px">çevrimiçi</span>`
          : (c.sections.some(s => s.online)
             ? `<span class="chip online" style="margin-left:6px">çevrimiçi şube var</span>` : "")}
        <div class="why">${esc(c.name)}${c.reasons.length
          ? " — " + c.reasons.map(esc).join("; ") : ""}${acilanNot(c)}</div></td>
      <td><span class="tag ${c.role}">${c.role}</span></td>
      <!-- data-e: telefonda kart düzeninde sütun başlığı olmuyor; sayının
           ne olduğu hücrenin yanına yazılıyor (Faz 50).
           Ters tırnak YOK: bu metin bir JS şablon dizgesinin içinde. -->
      <td class="mono" data-e="kredi">${c.credits}</td>
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
          : (DATA.emptyReason
             || "aday ders yok — bölümünü ve geçtiğin dersleri girdiğinden emin ol"))
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
  listeKenarSolmasi();
}

$("#candQ").addEventListener("input", (e) => {
  FILT.q = e.target.value; renderCandidates();
});
$("#candFree").addEventListener("change", (e) => {
  FILT.free = e.target.checked; renderCandidates();
});
$("#katalogBtn").addEventListener("click", () => katalogDialog());

/* ---------- klavye (Faz 27, yapılacaklar §3.3) ----------
   Aday tablosunda her şey fareyle yapılıyordu. Kayıt haftasında liste
   uzun ve tek tek tıklamak yoruyor.

   ⚠️ Kısayollar YAZI ALANINDA çalışmıyor: arama kutusuna "j" yazan kişi
   satır atlamamalı. Tek istisna arama kutusunda ok tuşları — oradan
   listeye geçmek doğal.  */
let CAND_ODAK = -1;

function candSatirlar(){
  return [...document.querySelectorAll("#cands tbody tr[data-course]")];
}

function candOdakla(i){
  const satirlar = candSatirlar();
  if(!satirlar.length) return;
  CAND_ODAK = Math.max(0, Math.min(satirlar.length - 1, i));
  satirlar.forEach((tr, n) => tr.classList.toggle("odak", n === CAND_ODAK));
  satirlar[CAND_ODAK].scrollIntoView({block: "nearest"});
}

document.addEventListener("keydown", (e) => {
  const t = e.target;
  const yaziAlani = t && /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName);
  const aramaKutusu = t && t.id === "candQ";
  if(document.querySelector("dialog[open]")) return;   /* pencere açıkken karışmasın */

  /* "/" aramaya odaklanır — listelerde yerleşik alışkanlık. */
  if(e.key === "/" && !yaziAlani){
    const q = $("#candQ");
    if(q){ e.preventDefault(); q.focus(); q.select(); }
    return;
  }
  if(yaziAlani && !aramaKutusu) return;

  if(e.key === "ArrowDown" || (e.key === "j" && !yaziAlani)){
    e.preventDefault(); candOdakla(CAND_ODAK + 1);
  }else if(e.key === "ArrowUp" || (e.key === "k" && !yaziAlani)){
    e.preventDefault(); candOdakla(CAND_ODAK - 1);
  }else if(e.key === "Enter" && CAND_ODAK >= 0){
    const tr = candSatirlar()[CAND_ODAK];
    if(tr){ e.preventDefault(); addDialog(tr.dataset.course); }
  }else if(e.key === "Escape" && aramaKutusu){
    t.value = ""; FILT.q = ""; renderCandidates(); t.blur();
  }
});

function addDialog(course){
  /* Aynı sınıf (Faz 49): ekleme penceresi de kipin havuzuna kilitliydi.
     Çağıranların hepsi bugün kip havuzundan geliyor, ama denklik kartı ve
     katalogdan ekleme yolları tam havuzdan ders getirebiliyor. */
  const cand = candOf(course);
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
  /* ★★ FAZ 42 — önşartı katalogda OLMAYAN bir dersi isteyen ders.
     "eksik: ELH 332" demek öğrenciyi var olmayan bir dersi aramaya
     göndermek olur; ayrı kategori, ayrı tavsiye. */
  ONSART_KATALOGDA_YOK:["önşartı katalogda yok","unknown"],
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
               donem: () => termDialog(), tercih: () => tercihDialog()};

  const zorunlu = O.steps.filter(s => s.required);
  const istege  = O.steps.filter(s => !s.required);
  const acik    = zorunlu.every(s => s.done);      /* araç çalışıyor mu */
  /* ★ TEK birincil eylem: sıradaki ilk yapılmamış adım. Yedi düğme arasından
     hangisine basılacağını kullanıcıya seçtirmek, "nasıl yapacağımı
     anlayamıyorum" hissinin ana kaynağıydı. */
  const sonraki = O.steps.find(s => !s.done);
  /* Motor gerçekten çıktı üretiyor mu — ayar dolu olması yetmiyor. */
  const calisiyorMu = () => (M().schedules || []).length > 0
    || (M().candidates || []).length > 0;

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
    <h2>${!acik ? "Hoş geldin — tek adımda başla"
      : (calisiyorMu() ? "Araç çalışıyor — istersen daha da iyileştir"
                       : "Bir şey ters gitti")}</h2>
    <p class="lead">${acik
      ? (calisiyorMu()
        ? `Aşağıdaki haftalık program <b>şu an çalışıyor</b>. Aşağıdaki iki şey
           <b>isteğe bağlı</b>; girersen öneriler senin durumuna göre kurulur.`
        /* ★★ İnceleme B1: bu cümle ızgara BOŞ ve "öneri üretilemedi" yazarken
           de duruyordu. Başlık motorun ÇIKTISINA bakmalı, ayarın varlığına
           değil. */
        : `<b>Öneri üretilemedi.</b> ${esc(DATA.emptyReason
            || "Aday ders bulunamadı — geçtiğin dersleri ve dönemini girmeyi dene.")}`)
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
      <div style="margin-top:6px">${siteMi()
        ? "Girdiğin hiçbir şey sunucuya gitmiyor; veri tarayıcında kalıyor."
        : "Girdiğin her şey bu bilgisayarda kalıyor (<span class=\"mono\">data/</span>)."}</div>
      ${/* ★ Faz 54: YENİ CİHAZDA yedekten devam — Ayar görünümü kurulum
            bitmeden gizli, yedeği yüklemenin tek yolu burası. */ ""}
      ${siteMi() && window.__ITUCAP_YEDEK__ ? `<div class="heroyedek">Başka bir
        tarayıcıda çalıştıysan:
        <button class="ghost mini" id="heroYedek">yedeğinden devam et…</button>
        <div class="veriyedek" id="heroYedekDurum" role="status" aria-live="polite"></div>
      </div>` : ""}
    </div>`;
  const hy = box.querySelector("#heroYedek");
  if(hy) hy.addEventListener("click", () => yedekDosyaSec(box.querySelector("#heroYedekDurum")));
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
  /* ★ E — TERCİHLER KEŞFEDİLMİYORDU. Motor Faz 27'den beri "erken
     başlamak istemem", "Cuma boş olsun", "kampüs değiştirmeyeyim" gibi
     yumuşak tercihleri sıralamaya katıyor; ama ilk giren kişi böyle bir
     kutu olduğunu bilmiyordu — yalnız kurulum çubuğunda küçük bir düğme
     olarak duruyordu. Yeri BURASI: kurulum değil, ince ayar.

     ⚠️ Zaten tercih girmiş kişiye "tercihlerini söyle" demiyoruz. */
  const tercihGoster = !tercihSayisi();
  el.innerHTML = `
    <b>Programın hazır. Şimdi:</b>
    <div class="sonrakiliste">
      <button class="ghost" data-go="schedSection">Haftalık programa bak</button>
      <button class="ghost" data-go="candSection">Ders ekle / değiştir</button>
      ${tercihGoster ? `<button class="ghost" data-go="tercih"
        title="Erken başlamak istemiyorsan, bir gün boş kalsın istiyorsan…
Hiçbir dersi elemez; yalnız sıralamayı değiştirir."
        >Nasıl bir program istediğini söyle</button>` : ""}
      <button class="ghost" data-go="crn">Kayıt günü listesini al</button>
      <button class="ghost kapat" data-kapat="1">Kapat</button>
    </div>`;
  el.querySelectorAll("[data-go]").forEach(b => b.addEventListener("click", () => {
    if(b.dataset.go === "crn"){ crnDialog(); return; }
    if(b.dataset.go === "tercih"){ tercihDialog(); return; }
    /* ★★ FAZ 48 — `scrollIntoView` BURADA DA ÖLÜYDÜ (taramada bulundu).
       Faz 46'da görünüm kipine geçtik; kapalı bir bölüme kaydırmak hiçbir
       şey yapmıyor. "Haftalık programa bak" ve "Ders ekle / değiştir"
       düğmeleri tıklanıyor, hiçbir şey olmuyordu. Aynı sınıftan üçüncü
       hata — `test_faz48` artık sınıfın tamamını tutuyor. */
    gorunumAc(b.dataset.go, true);
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
/* ★ C5 — sekme adları öğrencinin sözlüğünde olmalı. "EŞİKLER · DENKLİK ·
   DEĞİŞİM · ADAYLAR" araç geliştiricisinin dili; öğrenci ne olduklarını
   bilmiyor. */
/* ★★ FAZ 46 — GÖRÜNÜMLER (eski "bölüm çapaları").
   `grup`: rayda hangi başlığın altında. `kisa`: telefon sekmesinde yazan ad
   (uzun ad 390px'te üç sekmeyi ekrandan taşırıyordu). `alt: true` =
   telefonda "Daha" altında; başparmak menzilindeki dört yer, dönemde en çok
   dönülen dört işe ayrıldı.
   ⚠️ SIRA ÖNEMLİ: ilk uygun görünüm açılış görünümüdür. Haftalık program
   başta duruyor çünkü aracın ÜRETTİĞİ şey o. */
const SECTIONS = [
  ["schedSection", "Haftalık programım", "PLANLA", "Program", false],
  ["candSection", "Alabileceğim dersler", "PLANLA", "Dersler", false],
  ["blockSection", "Neden alamıyorum", "PLANLA", "Neden", false],
  ["savedSection", "Kaydettiğim", "PLANLA", "Kayıtlı", true],
  ["panels", "İlerlemem", "DURUM", "İlerlemem", false],
  ["creditSection", "Kredi sınırım", "DURUM", "Kredi", true],
  ["suggestSection", "Sayılan derslerim", "DURUM", "Sayılan", true],
  ["denklikSection", "Denkliği açık", "DURUM", "Denklik", true],
  ["changeSection", "Son değişiklikler", "DURUM", "Değişen", true],
  ["basvuruSection", "Başvuru", "DURUM", "Başvuru", true],
  ["tierSection", "Kademeler", "DURUM", "Kademe", true],
  /* ★ Kurulum çubuğu da bir görünüm (Faz 46): her ziyarette bakılan bir
     şey değil, ama kaybolmamalı — bölüm/dönem/not düzeltmenin tek yeri. */
  ["setupbar", "Bölüm, dönem, notlar", "AYAR", "Ayar", true],
];

/* Görünümü olan bölümler: DOM'da var ve veri yokluğundan gizli DEĞİL.
   ⚠️ `offsetParent` KULLANILMIYOR: artık etkin olmayan görünüm de
   `display:none` ve o kontrol her bölümü "kapalı" sayardı — ray kendi
   kendini boşaltırdı. */
function acikGorunumler(){
  return SECTIONS.filter(([id]) => {
    const el = document.getElementById(id);
    return el && !el.hidden;
  });
}

let GORUNUM = "";

/** Tek görünüm açık kalsın. Bilinmeyen/kapalı id verilirse ilk uyguna düşer. */
function gorunumAc(id, odakla){
  const acik = acikGorunumler();
  if(!acik.length){ GORUNUM = ""; return ""; }
  if(!acik.some(([x]) => x === id)) id = acik[0][0];
  GORUNUM = id;
  /* ★ Faz 47 — etkin görünüm KÖK ÖĞEDE de duruyor: haftalık program
     görünümü sayfayı GENİŞLETİYOR (aşağıdaki `.wrap` kuralı), metin ağırlıklı
     görünümler 1340px okuma ölçüsünde kalıyor. CSS'in JS değişkenini
     görmesinin tek yolu bu. */
  document.documentElement.dataset.gorunum = id;
  for(const [x] of SECTIONS){
    const el = document.getElementById(x);
    if(!el) continue;
    if(x === id) el.removeAttribute("data-disgorunum");
    else el.setAttribute("data-disgorunum", "");
  }
  const nav = $("#secnav");
  if(nav) nav.querySelectorAll("a[data-gorunum]").forEach(a =>
    a.setAttribute("aria-current", a.dataset.gorunum === id ? "page" : "false"));
  /* ⚠️⚠️ ÖLÇÜLERİNİ ÇİZİM ANINDA ALAN ŞEYLER YENİDEN ÇİZİLMELİ.
     Testte yakalandı: kademe diyagramının bağ çizgileri `getBoundingClientRect`
     ile kuruluyor; bölüm kapalıyken hepsi 0 çıkıyor ve görünüm açılınca
     çizgisiz bir diyagram kalıyordu. Gizli bir bölümün ölçüsü yoktur —
     görünür olunca bir kez daha ölçmek zorundayız. */
  if(id === "tierSection" && typeof drawTierLinks === "function")
    requestAnimationFrame(drawTierLinks);
  if(odakla){
    /* ⚠️ Görünüm değişince sayfa kaydırılmıyor — KAYDIRMAMAK bu değişikliğin
       amacı. Ama ekran okuyucu ve klavye kullanıcısı için odağın nereye
       gittiği söylenmeli, yoksa "hiçbir şey olmadı" sanılır. */
    const el = document.getElementById(id);
    if(el){ el.setAttribute("tabindex", "-1"); el.focus({preventScroll: true}); }
    if(scrollY > 0) scrollTo({top: 0, behavior: "smooth"});
  }
  return id;
}

function renderSecNav(){
  const nav = $("#secnav");
  if(!nav) return;
  const acik = acikGorunumler();
  /* Tek bölüm varsa ray gereksiz — ama o zaman o bölüm de açık kalmalı. */
  if(acik.length < 2){
    nav.innerHTML = "";
    for(const [x] of SECTIONS){
      const el = document.getElementById(x);
      if(el) el.removeAttribute("data-disgorunum");
    }
    GORUNUM = acik.length ? acik[0][0] : "";
    return;
  }
  let grup = "";
  nav.innerHTML = acik.map(([id, lbl, g, kisa, alt]) => {
    const bas = g !== grup ? `<div class="raybaslik">${g}</div>` : "";
    grup = g;
    return bas + `<a href="#${id}" data-gorunum="${id}"${alt ? ' data-alt="1"' : ""}
      ><span class="rayad uzun">${lbl}</span><span class="rayad kisa">${kisa}</span
      ><span class="raysayi" data-sayi="${id}"></span></a>`;
  }).join("");
  /* ★ Telefonda dört sekme yazılı, gerisi "Daha"da. Kaydırmaya bırakmak
     ölçülmüş bir hataydı: 390px'te 10 çapanın 3'ü görünüyordu. */
  if(acik.some(([, , , , alt]) => alt))
    /* ⚠️ `raykesme` bir SATIR KIRICI, süs değil. Ölçüldü: birincil
       sekmelerin `flex-basis`i 0 olduğu için esnek satır dolmuş sayılmıyor
       ve "Daha" açılınca ilk iki alt sekme aynı satıra sızıp dört birincil
       sekmeyi 26px'e eziyordu. Boyu 0, ekran okuyucuda yok. */
    nav.insertAdjacentHTML("beforeend",
      `<button type="button" class="raydaha" id="rayDaha" aria-expanded="false"
        ><span class="rayad kisa">Daha</span></button>
       <span class="raykesme" aria-hidden="true"></span>`);
  nav.querySelectorAll("a[data-gorunum]").forEach(a =>
    a.addEventListener("click", ev => {
      ev.preventDefault();
      nav.removeAttribute("data-acik");
      const d = $("#rayDaha");
      if(d) d.setAttribute("aria-expanded", "false");
      gorunumAc(a.dataset.gorunum, true);
    }));
  const daha = $("#rayDaha");
  if(daha) daha.addEventListener("click", () => {
    const acikMi = nav.hasAttribute("data-acik");
    if(acikMi) nav.removeAttribute("data-acik"); else nav.setAttribute("data-acik", "");
    daha.setAttribute("aria-expanded", String(!acikMi));
  });
  raySayilari();
  gorunumAc(GORUNUM || acik[0][0]);
}

/* ★★ Sayfa içi bölüm bağlantıları da GÖRÜNÜM AÇAR (Faz 46).
   Metin içinde "Darboğaz bölümünde ayrıntı" gibi bağlantılar var; eskiden
   o bölüme kaydırıyorlardı. Görünüm kipinde kaydırmak hiçbir şey yapmaz —
   hedef bölüm kapalı. Bağlantıyı çalışmaz bırakmak, Faz 25'te ve 44'te
   ölçtüğümüz "gizlenen şey yok sayılır" hatasının aynısı olurdu. */
addEventListener("click", ev => {
  const a = ev.target.closest && ev.target.closest('a[href^="#"]:not([data-gorunum])');
  if(!a) return;
  const id = a.getAttribute("href").slice(1);
  if(!SECTIONS.some(([x]) => x === id)) return;
  ev.preventDefault();
  gorunumAc(id, true);
});

/* ★★ FAZ 51 — AÇIKLAMAYA DOKUNMA. `title` dokunmatik ekranda hiç
   görünmüyor; ölçüldü, 24 gerçek açıklama telefonda ulaşılmazdı.
   ⚠️ YAKALAMA evresinde (`true`) ve `stopPropagation` ile: bu rozetlerin
   çoğu tıklanabilir bir SATIRIN içinde duruyor; yakalamasaydık dokunuş
   satırın penceresini açar, açıklama yine okunmazdı.
   ⚠️ Öğelere `tabindex`/`role` EKLENMİYOR: ekran okuyucu `title`ı zaten
   açıklama olarak okuyor, 24 yeni durak eklemek onun için gürültü olurdu.
   Eklenen tek şey, dokunmatikteki okuma yolu. */
addEventListener("click", ev => {
  const e = ev.target.closest &&
    ev.target.closest(".chip[title], .cat[title], .stale[title], .aciklamali[title]");
  if(!e) return;
  const t = (e.getAttribute("title") || "").replace(/\s+/g, " ").trim();
  if(!t) return;
  ev.preventDefault();
  ev.stopPropagation();
  say2(t);
}, true);

/* Rayda sayı: "kaç aday", "kaç engel". Bölüme girmeden büyüklüğü görünsün —
   eskiden bunu öğrenmenin tek yolu oraya kaydırmaktı.
   ⚠️ Uydurma sayı yok: sayamadığımız bölümde hiçbir şey yazmıyor. */
function raySayilari(){
  const yaz = (id, n) => {
    const el = document.querySelector(`.raysayi[data-sayi="${id}"]`);
    if(el) el.textContent = n == null ? "" : String(n);
  };
  yaz("candSection", (M().candidates || []).length || null);
  yaz("blockSection", (DATA.blockers || []).length || null);
  yaz("changeSection", (DATA.changes || []).length || null);
  yaz("savedSection", ((DATA.savedPicks && DATA.savedPicks.picks) || []).length || null);
}

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
  pencereAdiVer($("#basvuruDlg"));                  /* Faz 51 */
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
["PROGRAMA_KAPALI","ACILMAMIS","ONSART","ONSART_KATALOGDA_YOK",
 "KREDI_ESIGI","BILINMIYOR"].forEach(k => {
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
          aria-pressed="${on ? "true" : "false"}"
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
    try{ applyState(await api("/api/watch", {course: b.dataset.course}), {koru: true}); }
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
let tierFocus = null;   /* tıkla-kilit */
let tierHover = null;   /* üstüne-gel önizleme; kilit yoksa geçerli */

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
            ? `<span class="dep">önce <b>${c.needs.map(esc).join("</b> · <b>")}</b></span>` : ""}
        ${(c.outside && c.outside.length)
            ? `<span class="dispre" role="button" tabindex="0" aria-expanded="false"
                 title="Plan dışından önşart — anadalda almış olabilirsin">+${c.outside.length} dış önşart</span>
               <span class="disout" hidden>plan dışı: <span class="mono">${c.outside.map(esc).join(" · ")}</span></span>` : ""}
      </li>`).join("")}</ul>
    </div>`).join("");
  stage.innerHTML = `<svg class="tierlinks" id="tierLinks${i}" aria-hidden="true"></svg>` + cols;

  stage.querySelectorAll(".tier li").forEach(li => {
    li.addEventListener("click", () => {
      const code = li.dataset.c;
      tierFocus = (tierFocus === code) ? null : code;
      tierHover = null;
      paintTierFocus();
    });
    /* Üstüne gelince önizleme; tıklayınca kilit. Kilit varken hover karışmaz
       ki dokunmatikte de (hover yok) tıkla-kilit tek davranış olsun. */
    li.addEventListener("mouseenter", () => {
      if (tierFocus) return;
      tierHover = li.dataset.c; paintTierFocus();
    });
    li.addEventListener("mouseleave", () => {
      if (tierFocus) return;
      tierHover = null; paintTierFocus();
    });
  });

  /* Dış-önşart rozeti: tıkla/enter ile kodları aç-kapa. stopPropagation ki
     rozete basmak dersi odaklamasın. */
  stage.querySelectorAll(".dispre").forEach(ch => {
    const list = ch.nextElementSibling;
    const ac = () => {
      const acik = ch.getAttribute("aria-expanded") === "true";
      ch.setAttribute("aria-expanded", acik ? "false" : "true");
      if (list) list.hidden = acik;
    };
    ch.addEventListener("click", e => { e.stopPropagation(); ac(); });
    ch.addEventListener("keydown", e => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); e.stopPropagation(); ac(); }
    });
  });

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
                        r: r.right - box.left,          /* sağ kenar (mobil oluk) */
                        t: r.top - box.top, b: r.bottom - box.top};
  });
  svg.setAttribute("width", stage.scrollWidth);
  svg.setAttribute("height", stage.scrollHeight);
  /* ★ Her bağ İKİ yol: önce zemin renginde KILIF (casing), sonra çizgi.
     Bütün kılıflar bütün çizgilerin ALTINDA olsun diye ayrı biriktirip
     kılıf+çizgi sırayla değil, önce hepsi-kılıf sonra hepsi-çizgi basılıyor;
     yoksa sonraki kılıf önceki çizgiyi örterdi. */
  const kilif = [], cizgi = [];
  (grup.tiers || []).forEach(t => t.courses.forEach(c => (c.needs||[]).forEach(dep => {
    const a = at[dep], b = at[c.course];
    if (!a || !b) return;                       /* ders çizilmemişse çizgi de yok */
    /* Kademeler AŞAĞI doğru: çizgi önşartın ALTINDAN çıkıp dersin ÜSTÜNE
       giriyor. */
    const dy = b.t - a.b;
    let dd;
    if (Math.abs(b.x - a.x) < 24) {
      /* ★ Dikey bağ — mobilde kutular TEK SÜTUNda alt alta olunca bütün
         çizgiler aynı x'te üst üste biniyor ve diyagram "tek bir çizgi" gibi
         görünüp dallanmayı gizliyordu (telefon raporu 28.08.2026). Çizgiyi
         kutunun SAĞ KENARINDAN çıkarıp sağdaki OLUĞA kavislendiriyoruz —
         kutu içeriğini (kredi sayısı) kesmiyor. Kavis dikey mesafeyle
         büyüdüğü için kademe ATLAYAN bağ aradaki kutuların etrafından geniş
         bir yayla dolaşıp komşu bağlardan ayrışıyor. (Masaüstünde kutular
         yatay yayıldığından bu dal nadiren çalışır.) */
      const rx = a.r;                               /* iki kutu da aynı sağ kenar */
      const oluk = Math.max(0, box.width - rx);
      const kav = Math.min(oluk * 0.85, 20 + dy * 0.14);
      const cx = rx + kav;
      dd = `M ${rx} ${a.b} C ${cx} ${a.b + dy*0.30}, ${cx} ${b.t - dy*0.30}, ${rx} ${b.t}`;
    } else {
      const d = Math.max(14, dy / 2);
      dd = `M ${a.x} ${a.b} C ${a.x} ${a.b+d}, ${b.x} ${b.t-d}, ${b.x} ${b.t}`;
    }
    kilif.push(`<path class="casing" d="${dd}"></path>`);
    cizgi.push(`<path class="line" d="${dd}" data-a="${esc(dep)}" data-b="${esc(c.course)}"></path>`);
  })));
  svg.innerHTML = kilif.join("") + cizgi.join("");
}

function paintTierFocus(){
  const secili = tierHover || tierFocus;   /* hover kilidi geçici olarak eziyor */
  (DATA.tierGroups || []).forEach((g, i) => {
    const stage = $("#tierStage" + i);
    if (!stage) return;
    /* Zincir GRUBUN KENDİ grafından: iki program arasında önşart bağı yok,
       birinde seçilen ders öbürünü söndürmemeli ama aydınlatmamalı da. */
    const kendinde = (g.tiers || []).some(t =>
      t.courses.some(c => c.course === secili));
    const chain = (secili && kendinde) ? tierChain(g.tiers, secili) : null;
    stage.classList.toggle("focus", !!chain);
    stage.querySelectorAll(".tier li").forEach(li => {
      li.classList.toggle("on", !!chain && chain.has(li.dataset.c));
      li.classList.toggle("root", li.dataset.c === secili);
    });
    /* Yalnız çizgiler; kılıf her zaman zeminde kalsın diye .line hedefleniyor. */
    stage.querySelectorAll(".tierlinks path.line").forEach(p => p.classList.toggle(
      "on", !!chain && chain.has(p.dataset.a) && chain.has(p.dataset.b)));
  });
}

addEventListener("resize", () => requestAnimationFrame(drawTierLinks));

/* ★ Tek giriş noktası. Sunucudan yeni durum gelince (program/dönem/transkript
   değişti) sayfa yenilenmeden buradan yeniden çiziliyor. */
/** `onceki` yoksa İLK açılış; varsa `applyState`ten geliyor (Faz 53). */
function boot(onceki){
  bildirimBolgesi();      /* canlı bölge ÖNCE var olsun (Faz 51) */
  setupBar();
  renderHeader();
  renderGpa();
  renderLoad();
  renderFloor();
  renderCredits();
  renderSuggestions();
  renderAcikDenklik();
  renderChanges();
  wireRefresh();
  wirePicks();
  renderBlockers();
  renderHero();
  renderSonraki();
  renderBasvuru();
  renderTiers();
  if(!onceki){
    useMode(0);
  }else{
    /* Faz 53: kip anahtarıyla korunuyor; yoksa (program değişti, dönem
       kipi kalktı) ilk kipe düşülüyor. Kaydedilen program YÜKLENMİYOR. */
    /* Faz 54: kurulum işlerinden sonra VARSAYILAN kip (dönem ilk kez
       seçilince dönemlik kip açılsın — ilk kartın verdiği söz). */
    const i = onceki.varsayilan ? -1 : MODES.findIndex(m => m.key === onceki.kip);
    useMode(i >= 0 ? i : 0, {kayitli: false});
    if(i >= 0 && onceki.koru) seciliGeriKoy(onceki);
  }
  renderSaved();      // useMode'dan SONRA: MODES aday havuzu kurulmuş olmalı
  renderSecNav();     // en sona: hangi bölümlerin açık olduğu ancak burada belli
  // ★ Paylaşılan bağlantı (#crn=…) EN SON: kaydedilen programı da eziyor,
  // çünkü kullanıcı o bağlantıya bilerek tıkladı. ⚠️ Yalnız İLK açılışta —
  // yoksa her ayar değişikliği bağlantının programını yeniden yüklerdi.
  if(!onceki) baglantidanYukle();
  _acildi = true;
}

/** `koru`: öneriyi değiştirmeyen bir işten sonra (izleme, kaydetme) sekme
    ve ızgara OLDUĞU GİBİ kalsın. Seçimdeki bir ders artık çözülemiyorsa
    (havuzdan çıktı) seçimi zorla tutmuyoruz — öneriye dönülüyor. */
function seciliGeriKoy(onceki){
  if(onceki.active < (M().schedules || []).length) active = onceki.active;
  const hepsi = onceki.sel.length && onceki.sel.every(x => sectionOf(x.course, x.crn));
  if(hepsi){ sel = onceki.sel.map(x => ({course: x.course, crn: x.crn})); render(); }
  else resetTo(active);
}
/* ★★ FAZ 55 — PENCERENİN DIŞINA TIKLAYINCA KAPANSIN (kullanıcı 23.09.2026:
   *"sitenin üzerine açılan sekmelerde arka tarafa yani normal arayüze
   tıklayınca oraya geçip açılan kısım kapansın"*).

   Üç pencere de (`detail`, `setup`, `basvuruDlg`) kipli `<dialog>`: arka
   plan tıklamayı yutuyordu, kapatmanın tek yolu "Kapat" ya da Esc idi.
   Artık perdeye tıklamak pencereyi kapatıyor VE tıklama altındaki yere
   geçiyor — raydaki "Alabileceğim dersler"e tıklayan oraya gidiyor,
   ızgaradaki başka derse tıklayan onun penceresini açıyor.

   ⚠️ Üç tuzak, üçü de ölçüldü:
   · Pencere İÇİNDE başlayıp DIŞINDA biten sürükleme (kutudaki metni
     seçerken) de bir "click" üretiyor ve hedefi pencerenin kendisi. Yalnız
     `pointerdown` da dışarıda olduysa kapanıyor.
   · Pencerenin kenarı (üstteki 6px şerit) da hedefi pencere olan bir
     tıklama; koordinat kutunun İÇİNDEYSE kapanmıyor.
   · KAYDEDİLMEMİŞ değişiklik varken (kurulum penceresi: program, dönem,
     transkript, tercih…) dışarıya tıklamak işi SESSİZCE silmiyor: pencere
     açık kalıyor ve ne yapılacağı yazıyor. Bir kez daha dışarıya tıklamak
     artık bilerek bırakmak demek. */
let SETUP_KIRLI = false;
(function pencereDisinaTiklama(){
  const kb = $("#setupBody");
  if(kb){
    kb.addEventListener("input", () => { SETUP_KIRLI = true; });
    kb.addEventListener("change", () => { SETUP_KIRLI = true; });
    kb.addEventListener("click", (e) => {
      const b = e.target.closest && e.target.closest("button");
      if(b && !b.matches("[data-close], #setupSave")) SETUP_KIRLI = true;
    });
  }
  const disarida = (d, e) => {
    const r = d.getBoundingClientRect();
    return e.clientX < r.left || e.clientX > r.right
        || e.clientY < r.top || e.clientY > r.bottom;
  };
  let basla = null, uyarildi = false;
  document.querySelectorAll("dialog").forEach(d => {
    d.addEventListener("close", () => { uyarildi = false; });
    d.addEventListener("pointerdown", (e) => {
      basla = (e.target === d && disarida(d, e)) ? d : null;
    });
    d.addEventListener("click", (e) => {
      const gecerli = basla === d && e.target === d && disarida(d, e);
      basla = null;
      if(!gecerli) return;
      if(d.id === "setup" && SETUP_KIRLI && !uyarildi){
        uyarildi = true;
        say("Kaydedilmemiş değişiklik var — saklamak için Kaydet. "
            + "Bırakmak için dışarıya bir kez daha tıkla ya da Kapat.", true);
        return;
      }
      d.close();
      /* Tıklama altındaki yere geçsin. Kapandıktan SONRA bakılıyor: açıkken
         noktadaki öğe perde. */
      const alt = document.elementFromPoint(e.clientX, e.clientY);
      if(!alt || alt.closest("dialog[open]")) return;
      if(alt.matches("input, textarea, select")) alt.focus();
      alt.dispatchEvent(new MouseEvent("click", {bubbles: true, cancelable: true,
        view: window, clientX: e.clientX, clientY: e.clientY}));
    });
  });
})();

boot();
</script>
</body>
</html>
"""
