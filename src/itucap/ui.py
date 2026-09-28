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
from . import tasarim as TASARIM
from . import yolharitasi as YH
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
                     names, section_json, kendi_program: str | None = None) -> list[dict]:
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

    ★★ Faz 111 — DİLEKÇESİZ (kullanıcı 28.09.2026: *"denk derslerde bölümümün
    kodu alabilir gözüküyorsa dilekçesiz de alabiliyorum"*). Şubenin OBS'deki
    "alabilir" listesinde ANADAL kodu (`kendi_program`) açıkça yazıyorsa
    kaynak `dilekcesiz` işaretleniyor ve o şubeler `dilekcesizCrn`'de.
    Listesi boş ya da "-" olan şube bu iddiaya GİRMİYOR: bilinmeyen, bilinen
    gibi gösterilmez.
    """
    # ★ Faz 115 — bölümün iki dil programı aynı bölüm (kullanıcı 28.09.2026:
    # anadal BLGE, şube "BLG_LS"/BLG'ye açık, kart yine "dilekçeyle" diyordu).
    # ★ Faz 115 — ÇAP/yandal programı da "kendi" programın (kullanıcı: "çap
    # kodumdan bahsediyorum ve blg kodum"). Kural `normalize`da (Faz 117:
    # öneri motoru da aynısını kullanıyor).
    from .normalize import kendi_program_kodlari
    kendi = kendi_program_kodlari(
        [kendi_program] if isinstance(kendi_program, (str, type(None))) else kendi_program)

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
        dilekcesiz = [sec.crn for sec in secs if any(
            str(r[0]).strip().upper() in kendi for r in con.execute(
                "SELECT program_code FROM lesson_allowed_program WHERE crn=?", (sec.crn,)))]
        return {"code": code, "name": name_of(code), "minGrade": min_not,
                "passed": passed(code), "open": bool(secs),
                "dilekcesiz": bool(dilekcesiz), "dilekcesizCrn": dilekcesiz,
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
    kapsamlar = ([(s["kind"], s["label"], s.get("planId")) for s in seconds]
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
            # ★ Faz 92: dil eşi de — slotu dolduran ders ortalamaya da girer.
            subset = {c: g for c, g in graded.items()
                      if c in R.plan_codes(con, plan_id, esler=True)}
            if subset:
                g2 = POL.gpa(con, subset, uncertain)
                if g2.counted:
                    second_gpa = g2

        for t in POL.load_thresholds(program=scope):
            # ★★ Faz 79 — İKİNCİ PROGRAMI OLMAYAN öğrenci. "genel" kapsam
            # `applies_to` ile BÜTÜN eşikleri alıyordu: gerçek sitede ÇAP'sız
            # 7. yarıyıl öğrencisi "ÇAP'a devam ≥ 2.50 ✗", "ÇAP mezuniyeti ✗"
            # görüyor, danışman özeti ona dört ÇAP sorusu yazıyordu. Kayıtlı
            # olmadığı programın DEVAM ve MEZUNİYET eşiği ona uygulanmaz;
            # BAŞVURU eşiği ise bir seçenek olarak kalıyor.
            if scope == "genel" and t.program not in ("genel", "") and t.kind != "basvuru":
                continue
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
            if t.key != "cap_mezuniyet_ikinci" and not gpa.counted:
                # ★ Faz 68 — harf notu yoksa GNO ölçülmedi: ✗ değil "—".
                item.update({"basis": "genel", "ok": None,
                             "why": "Harf notu girilmiş ders bulunmadığından GNO "
                                    "bilinmemektedir."})
                out.append(item)
                gorulen[t.key] = item
                continue
            if t.key == "cap_mezuniyet_ikinci":
                if second_gpa is None:
                    item.update({"basis": "ikinci anadal", "ok": None,
                                 "why": "ÇAP planında harf notlu ders "
                                        "bulunmadığından ikinci anadal "
                                        "ortalaması henüz hesaplanamamaktadır."})
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


def _tekrar_notlari(con: sqlite3.Connection, graded: dict[str, str],
                    havuz: set[str]) -> dict[str, dict]:
    """Faz 57 — bu dönem TEKRAR alınabilecek derslerin ortalamadaki payı.

    GNO hedefi ("2.50'de kalmak için bu dönem kaç ortalama gerekir") tekrar
    alınan dersi YENİ ders gibi sayarsa yanlış çıkar: İTÜ'de son alınan not
    geçerli (Faz 9), eski notun puanı ve kredisi ortalamadan ÇIKIYOR. FF'yi
    tekrar eden öğrenci için fark büyük — FF'nin sıfırı gidiyor.
    Yalnız GNO'ya giren notlar (`POL.gpa` ile aynı süzgeç).
    """
    out = {}
    for code in sorted(havuz & set(graded)):
        g = str(graded[code] or "").upper()
        if g in POL.GPA_EXCLUDED or g not in PRQ.GRADE_POINTS:
            continue
        row = con.execute("SELECT credits FROM course WHERE code=?", (code,)).fetchone()
        kredi = float((row[0] if row else 0) or 0)
        if kredi > 0:
            out[code] = {"grade": g, "credits": kredi,
                         "points": round(PRQ.GRADE_POINTS[g] * kredi, 4)}
    return out


def _ikinci_gno_tabani(con: sqlite3.Connection, ucon: sqlite3.Connection,
                       student_id: int, seconds: list[dict]) -> list[dict]:
    """Faz 58 — ÇAP'ın KENDİ ortalamasının hedef hesabı için tabanı.

    "ÇAP mezuniyeti — ikinci anadal ortalaması ≥ 2.00" genel GNO'yu değil,
    yalnız ÇAP planındaki derslerin ortalamasını soruyor (`_threshold_info`,
    2. incelik). Faz 57'nin GNO hedefi bu eşiği dışarıda bırakıp "burada
    yok" diyordu. Aynı alt küme (`R.plan_codes`, dil eşi dahil) ve aynı
    `POL.gpa`; arayüz bu dönemki programdan yalnız bu kodları sayıyor.
    Yalnız ÇAP — yandalın böyle bir eşiği yok (Faz 23.08.2026 notu).
    """
    graded = S.graded(ucon, student_id)
    uncertain = S.uncertain_grades(ucon, student_id)
    out = []
    for s2 in seconds:
        if s2.get("kind") != "cap" or not s2.get("planId"):
            continue
        kodlar = R.plan_codes(con, s2["planId"], esler=True)
        g2 = POL.gpa(con, {c: g for c, g in graded.items() if c in kodlar}, uncertain)
        out.append({"label": s2["label"], "program": s2["program"],
                    "points": g2.points, "credits": g2.credits,
                    "codes": sorted(kodlar)})
    return out


def _kalan_gno_tabani(con: sqlite3.Connection, ucon: sqlite3.Connection,
                      student_id: int, grades, equivalences, anadal_id,
                      seconds: list[dict]) -> dict | None:
    """Faz 69 — mezuniyete kadar KALAN BÜTÜN derslerin ortalama tabanı.

    Kullanıcı 24.09.2026: *"eşikler için gereken dönem ortalamasının dışında
    kalan bütün derslerden gereken dönem ortalamasını da hesaplayıp
    gösterir misin"*. "Bu dönem yeterli değil" diyen bir eşiğin asıl sorusu:
    kalan derslerin HEPSİNDE hangi ortalama yeter?

    Kalan dersler yol haritasıyla AYNI kaynaktan (`YH._birimler`): anadal ve
    ÇAP'ta ortak ders tek sayılıyor, havuz slotu kendi kredisiyle. Bu dönemin
    programı da kalan derslerin içinde. Kalan derslerden daha önce notu olup
    geçilmemiş olanlar (FF/VF) TEKRAR sayılıyor: eski notun kredisi ve puanı
    ortalamadan düşüyor (İTÜ'de son not geçerli; `_tekrar_notlari` ile aynı).
    """
    if not anadal_id:
        return None
    planlar = [{"planId": anadal_id, "role": "ANADAL"}] + [
        {"planId": s2["planId"], "role": s2["role"]} for s2 in seconds if s2.get("planId")]
    birimler = YH._birimler(con, planlar, grades, equivalences, {})
    graded = S.graded(ucon, student_id)

    def taban(bs):
        kredili = [b for b in bs if b.kredi > 0]
        kodlar = {k for b in kredili if b.ders for k in b.kodlar}
        tekrar = _tekrar_notlari(con, graded, kodlar)
        return {"credits": round(sum(b.kredi for b in kredili), 1),
                "courses": len(kredili),
                "pools": sum(1 for b in kredili if not b.ders),
                "poolAssumed": sum(1 for b in kredili
                                   if getattr(b, "_kredi_varsayildi", False)),
                "retakeCredits": round(sum(r["credits"] for r in tekrar.values()), 1),
                "retakePoints": round(sum(r["points"] for r in tekrar.values()), 4),
                "retake": sorted(tekrar)}

    out = {"genel": taban(birimler)}
    if any(s2.get("kind") == "cap" and s2.get("planId") for s2 in seconds):
        out["ikinci"] = taban([b for b in birimler if "CAP" in b.roller])
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



def _sube_onbellekli(f):
    """★★ Faz 91 — isteğin tamamı boyunca önbellek (bkz. `istek`): bir istekte
    aynı şubeler, ders adları ve önşart ağaçları bir kez okunur."""
    import functools
    from . import istek as IST

    @functools.wraps(f)
    def sar(*a, **k):
        with IST.istek():
            return f(*a, **k)
    return sar


def _panel_donemleri(con: sqlite3.Connection, plan_id: int, open_slots) -> dict:
    """İlerleme kartı için planın DÖNEM DÖNEM durumu ve açık yuvaları.

    ★★ Faz 99 (kullanıcı 25.09.2026: "ilerleme durumu kısmı biraz boş
    kaldı"). Kart yüzde ve sayı veriyordu ama HANGİ derslerin kaldığını ve
    planın neresinde olunduğunu söylemiyordu: "%62 · kalan zorunlu 14"
    okunup geçiliyordu. Bu veri planda zaten var (`term_no`).

    `terms` yalnız her yuvanın dönemi belliyse dolu: ÇAP/yandal planlarında
    `term_no` NULL (şema notu) — dönem uydurmuyoruz, o kartta yalnız açık
    yuva listesi çıkıyor.
    """
    acik = set(open_slots)
    rows = con.execute(
        """SELECT ps.id, ps.term_no, ps.slot_kind, ps.course_code,
                  ps.pool_label_raw, ps.pool_category, c.name
             FROM plan_slot ps LEFT JOIN course c ON c.code = ps.course_code
            WHERE ps.plan_id=? ORDER BY ps.term_no IS NULL, ps.term_no, ps.position""",
        (plan_id,)).fetchall()
    donemli = bool(rows) and all(r["term_no"] is not None for r in rows)
    terms: dict[int, list[int]] = {}
    acik_liste = []
    for r in rows:
        if donemli:
            t = terms.setdefault(int(r["term_no"]), [0, 0])
            t[1] += 1
            if r["id"] not in acik:
                t[0] += 1
        if r["id"] in acik:
            zorunlu = r["slot_kind"] == "REQUIRED"
            acik_liste.append({
                "code": r["course_code"] if zorunlu else None,
                "label": (r["course_code"] if zorunlu
                          else (r["pool_label_raw"] or r["pool_category"] or "Seçmeli")),
                "name": r["name"] or "",
                "term": r["term_no"],
                "required": zorunlu,
            })
    return {"terms": [{"term": k, "done": v[0], "total": v[1]}
                      for k, v in sorted(terms.items())],
            "open": acik_liste}


@_sube_onbellekli
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
    # ★ Faz 64 — "bu dönem" tek yerden: ayar, yoksa şubelerin çekildiği gün.
    aktif_donem = _aktif_donem(con, settings)
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
            # ★ Faz 67 — OBS'den çekilen planın resmî sayfası (itu-helper
            # kaynaklı planların OBS'de karşılığı yok → None, link çizilmez).
            "url": (plan["source_url"] if str(plan["source_url"] or "")
                    .startswith(config.OBS + "/public/DersPlan/DersPlanDetay/") else None),
            "source": plan["source"],
            "percent": stats["percent"],
            "slotsDone": stats["slots_done"], "slotsTotal": stats["slots_total"],
            "openRequired": stats["open_required"],
            "ectsDone": stats["ects_done"], "ectsTotal": stats["ects_total"],
            "creditsDone": stats["credits_done"], "creditsTotal": stats["credits_total"],
            "byCategory": [{"key": k, "done": v[0], "total": v[1]}
                           for k, v in stats["by_category"].items()],
            "remaining": open_codes,
            **_panel_donemleri(con, plan_id, stats["open_slots"]),
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
            # ★ Faz 93 — DERSLİK. Veride vardı (`lesson_meeting.room`, gerçek
            # katalogda 3900 buluşmanın 1725'i) ama arayüze hiç çıkmıyordu:
            # öğrenci programa bakıp "MED" görüyor, hangi sınıfa gideceğini
            # OBS'de ayrıca arıyordu. İlan edilmemiş derslik ("--") BOŞ döner.
            "meetings": [{"day": m.day, "start": m.start, "end": m.end,
                          "building": _building(m.building), "room": _derslik(m.room),
                          "campus": m.campus}
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
            _yuva = dict(zip((p.candidate.course for p in sched.picks),
                             _yuvalar_ata([p.candidate for p in sched.picks])))
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
                # Faz 94: arada < 60 dk olan yerleşke değişimi.
                "tightTransfers": sched.sikisik_gecisler(),
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
                    "slotId": _yuva.get(p.candidate.course, p.candidate.slot_id),
                    "pool": p.candidate.pool_label,
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
        # ★ Faz 116 — dersin takma adlarını (yeni kod, dil eşi, denklik) anan
        # dersler de: BBF 203E alınınca, önşartı "BLG 252E" diyen BBF 301E açılır.
        adlar = R.takma_adlar(con, code, equivalences)
        for k in sorted(R.acilan_hedefler(_unlock_map, adlar)):
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
                _nd_cache[code] = ND.distribution(con, code, aktif_donem)
            except Exception:                     # noqa: BLE001
                # Dağılım bir SÜS; okunamazsa aracın geri kalanı çalışmalı.
                _nd_cache[code] = None
        d = _nd_cache[code]
        if not d:
            return None
        # ★★ Faz 85/87 — tahmini zorluk (10 üzerinden, iki alt puan).
        try:
            _zorluk = ND.zorluk(con, code)
        except Exception:                         # noqa: BLE001
            _zorluk = None
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
            "difficulty": _zorluk,
            "terms": [{
                "term": t["term"], "termName": t["termName"],
                "yearName": t["yearName"], "season": t["season"],
                "counts": t["counts"],
                "buckets": ND.bucketise(t["counts"]),
                # ★ Faz 67 — verinin okunduğu OBS sayfasının kendisi.
                "url": config.notdagilimi_url(code, config.term_year(t["term"]) or 0),
                **t["summary"],
            } for t in d["terms"]],
        }

    def candidates_json(pool):
        return [{
            "course": c.course, "name": c.name, "altName": _diger_dil(c.course),
            "role": c.role, "ects": c.ects,
            "credits": c.credits, "slotId": c.slot_id, "planId": c.plan_id,
            "slotIds": list(c.yuvalar),                       # Faz 81
            "termNo": c.term_no, "pool": c.pool_label,
            "score": c.score, "unlocks": c.unlocks, "critical": c.critical,
            "prereqUnknown": c.prereq_unknown, "prereqMissing": c.prereq_missing,
            # ★ Puanın kırılımı — "neden bu ders önde" sorusunun cevabı.
            "parts": c.parts,
            # `unlocks` katalogdaki toplam, `opens` SENİN planındaki liste.
            # İkisi ayrı sayı; birini öbürünün yerine yazmak yanlış olurdu.
            "opens": _acilanlar(c.course),
            "required": c.required, "reasons": c.reasons,
            # ★ Faz 117 — plandaki bu dersin yerine resmî denklikle (dilekçesiz).
            "denkOf": c.denk_of,
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
    # Faz 120 — dilekçesiz denk (`candidates` ile aynı "kendi program" kümesi).
    kendi_programlar = [settings.anadal_program, *(s["program"] for s in seconds)]
    if anadal_id:
        blockers += [{"course": b.course, "reason": b.reason, "detail": b.detail,
                      "name": names.get(b.course, ""),
                      "role": "ANADAL", "label": "anadal",
                      "program": settings.anadal_program}
                     for b in REC.cap_blockers(con, ucon, student_id, anadal_id,
                                               settings.anadal_program,
                                               settings.allowed_programs,
                                               max_term=donem or None,
                                               kendi_programlar=kendi_programlar)]
    for s in seconds:
        blockers += [{"course": b.course, "reason": b.reason, "detail": b.detail,
                      "name": names.get(b.course, ""),
                      "role": s["role"], "label": s["label"],
                      "program": s["program"]}
                     for b in REC.cap_blockers(con, ucon, student_id, s["planId"],
                                               s["program"],
                                               settings.allowed_programs,
                                               dil_esi=True,
                                               kendi_programlar=kendi_programlar)]

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
        # Faz 79 — planı bulunamayan ama BEYAN edilen ikinci program da kapsam:
        # ÇAP öğrencisinin ÇAP eşikleri planı çekilmemiş diye kaybolmasın.
        "thresholds": _threshold_info(con, ucon, student_id, gpa, seconds + plansiz),
        "points": gpa.points,
        "retake": _tekrar_notlari(con, S.graded(ucon, student_id),
                                  {c.course for c in [*cands, *term_cands]}),
        "secondGpa": _ikinci_gno_tabani(con, ucon, student_id, seconds),
        # ★ Faz 69 — mezuniyete kadar kalan bütün dersler.
        "remaining": _kalan_gno_tabani(con, ucon, student_id, grades, equivalences,
                                       anadal_id, seconds),
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
            # ⚠️ Faz 68: "transkript yok" (hiç ders girilmemiş) ile "not yok"
            # (dersler var, hiçbirinin harf notu yok) AYRI. İlkinde ilerleme de
            # bilinmiyor; ikincisinde yalnız GNO — ilerleme panelleri bu bayrağa
            # bakıyor, karıştırılırsa "İlerleme bilinmiyor" yanlış çıkardı.
            "noTranscript": not S.graded(ucon, student_id),
            "noGrades": bool(S.graded(ucon, student_id)) and not gpa.counted,
            # Tavan nereden geldi: 'yönetmelik' (GNO'dan otomatik) | 'ayar' | 'çağrı'.
            # Türetilmiş bir sayıyı beyan edilmiş gibi göstermemek için.
            "limitSource": limit_source,
            "conflict": bool(load_rule.maximum
                             and limit_credits > load_rule.maximum + 1e-9),
            "next": ({"max": load_rule.next_band.max_credits,
                      "minGpa": load_rule.next_band.min_gpa}
                     if load_rule.next_band else None),
            # ★ Faz 71 — bantların tamamı: not senaryosu gelecek dönemin
            # sınırını AYNI kurallardan (kurallar.toml) hesaplıyor.
            "bands": [{"label": b.label, "minGpa": b.min_gpa, "max": b.max_credits}
                      for b in POL.load_bands()[0]],
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

    yol_haritasi = _yol_haritasi(con, ucon, student_id, settings, anadal_id, seconds,
                                 grades, equivalences, donem, limit_credits, load_rule,
                                 _floor, [*cands, *term_cands],
                                 term_scheds if term_scheds else schedules)

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
        # ★ Faz 64 — sitede `term` ayarı yok: başlık da haritayla AYNI dönemi
        # (şubelerin çekildiği gün) yazıyor.
        "term": aktif_donem,
        # ★ B3 — başlıkta ham `202610` yazıyordu. Çözülemezse BOŞ; arayüz
        # o zaman ham kodu yazmaya devam ediyor, isim UYDURMUYOR.
        "termLabel": config.donem_adi(aktif_donem),
        # ★★ Faz 38 — planladığın dönemin notları AÇIKLANMIŞ mı?
        # Takvimden tahmin etmiyoruz, kaynağa soruyoruz: o dönem için
        # kaç dersin dağılımı yayınlanmış. Sıfırdan büyükse dönem geçmişte
        # kalmış demektir ve `settings.term` büyük ihtimalle yanlış.
        # ⚠️ 0 "gelecekte" DEMEK DEĞİL — hiç çekilmemiş de olabilir; arayüz
        # bu ikisini `gradeCoverage.courses` ile ayırıyor.
        "termGraded": ND.term_already_graded(con, aktif_donem),
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
        "links": config.DIS_BAGLANTILAR,
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
            gereken_dersler, settings.allowed_programs, names, section_json,
            [settings.anadal_program, *(x[3] for x in settings.seconds)]),
        # Her ikinci programın KENDİ kademe zinciri.
        "tierGroups": tier_groups,
        # ★★ Faz 57 — mezuniyet yol haritası (çok dönemli plan, §2.1).
        "roadmap": yol_haritasi,
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
        {"key": "program", "label": "Bölüm seçimi",
         "cta": "Bölümünüzü seçin",
         "detail": "Anadal programınız. Çift anadal veya yandal programına "
                   "kayıtlı değilseniz \u201cYok\u201d seçeneğini bırakın.",
         "why": "Öneriler bu seçimden sonra oluşturulur.",
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
        {"key": "donem", "label": "Yarıyıl bilgisi",
         "cta": "Yarıyılınızı seçin",
         "detail": "Kaçıncı yarıyılda olduğunuzu tek tıklamayla belirtin.",
         "why": "\u201cN. dönem + alttan\u201d önerisi bu bilgiye göre oluşturulur; "
                "bir sonraki adımda önceki yarıyılların zorunlu dersleri "
                "işaretli olarak gelir.",
         "sure": "5 saniye", "required": False,
         "done": bool(settings.donem), "action": "donem"},
        {"key": "transkript", "label": "Başarılan dersler",
         "cta": "Dersleri girin",
         "detail": ("Önceki yarıyılların zorunlu dersleri işaretli olarak gelir; "
                    "yalnızca düzeltme yapmanız yeterlidir."
                    if settings.donem else
                    "Transkriptinizi olduğu gibi yapıştırabilir veya dersleri "
                    "plan üzerinden işaretleyebilirsiniz."),
         "why": "Kalan dersler, önşart durumu ve kredi sınırı bu bilgiden "
                "hesaplanır.",
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


def _aktif_donem(con: sqlite3.Connection, settings) -> str:
    """Yol haritasının "bu dönem"i: ayardaki dönem, yoksa KATALOĞUN dönemi.

    ★ 24.09.2026 — statik sitede kimse `term` ayarı girmiyor; harita (ve ÇAP
    seçeneklerinin bitişi, senaryolar) bu yüzden sitede HİÇ görünmüyordu,
    yalnız yerel uygulamada. Şubelerin hepsi tek bir döneme aitse o dönem
    "bu dönem"dir — tahmin değil, katalogun kendisi. Birden çok dönem varsa
    ya da hiç yoksa boş: uydurmuyoruz.
    """
    term = str(settings.term or "")
    if len(term) == 6:
        return term
    try:
        # ★★ Faz 64 — önce şubelerin ÇEKİLDİĞİ gün: yayındaki katalogda şubeler
        # 20.09.2026'da çekilmiş ama örnek ayardan kalma `202610` (2025-2026
        # Güz) basılmıştı; site bir yıl geride başlıyordu. Basılı dönem yalnız
        # tarih bir geçiş ayına düşüyorsa kullanılıyor.
        cekim = con.execute("SELECT MAX(updated_at) FROM lesson").fetchone()[0]
        if config.donem_kodu_tarihten(cekim):
            return config.donem_kodu_tarihten(cekim)
        donemler = [str(r[0]) for r in con.execute(
            "SELECT DISTINCT term FROM lesson WHERE term IS NOT NULL AND term != ''")]
    except sqlite3.Error:
        return ""
    return donemler[0] if len(donemler) == 1 and len(donemler[0]) == 6 else ""


def _yuvalar_ata(adaylar) -> list[int]:
    """Faz 81 — her adaya AYRI bir slot (eşleştirme); olmuyorsa birincil slot.
    `None` (plan dışı ders) için 0. Yol haritası bu dönem doldurulan yuvaları
    böyle öğreniyor: iki Functional-MT dersi iki ayrı yuvayı dolduruyor."""
    gercek = [(i, a) for i, a in enumerate(adaylar) if a is not None]
    atama = REC.yuva_ata([a for _, a in gercek]) or {}
    out = [0] * len(adaylar)
    for k, (i, a) in enumerate(gercek):
        out[i] = atama.get(k, a.slot_id)
    return out


def _yol_haritasi(con, ucon, student_id, settings, anadal_id, seconds, grades,
                  equivalences, donem, limit_credits, load_rule, taban, havuz,
                  acilis_programlari) -> dict | None:
    """Faz 57 — mezuniyet yol haritası (`yolharitasi.kur`).

    "Bu dönem" ne sayılıyor: KAYDEDİLEN program varsa o (kayıt haftasında
    gerçekten alacağın şey), yoksa açılışta gösterilen kipin 1. önerisi.
    Hangisinin kullanıldığı haritanın üstünde YAZIYOR.

    ⚠️ Kredi sınırı KREDİ cinsinden olmalı: birim AKTS ise yönetmelik
    tavanına (MADDE 17) bakılıyor, o da yoksa harita KURULMUYOR — AKTS'yi
    krediye çevirmek uydurma olurdu.
    """
    term = _aktif_donem(con, settings)
    if not anadal_id or not term:
        return None
    sinir = limit_credits or (load_rule.maximum if load_rule else 0)
    if not sinir:
        return None
    ders = {c.course: c for c in havuz}
    kredi = {r[0]: r[1] for r in con.execute("SELECT code, credits FROM course")}
    kayitli = S.load_picks(ucon, student_id, settings.term).get("picks") or []
    if kayitli:
        yuva = _yuvalar_ata([ders.get(p["course"]) for p in kayitli])
        bu = [{"course": p["course"],
               "credits": (ders[p["course"]].credits if p["course"] in ders
                           else float(kredi.get(p["course"]) or 0)),
               "slotId": yuva[k],
               "role": ders[p["course"]].role if p["course"] in ders else "PLAN_DISI"}
              for k, p in enumerate(kayitli)]
        kaynak = f"kaydedilen program ({len(bu)} ders)"
    elif acilis_programlari:
        secim = acilis_programlari[0].picks
        yuva = _yuvalar_ata([pk.candidate for pk in secim])
        bu = [{"course": pk.candidate.course, "credits": pk.candidate.credits,
               "slotId": yuva[k], "role": pk.candidate.role}
              for k, pk in enumerate(secim)]
        kaynak = f"açılıştaki öneri 1 ({len(bu)} ders)"
    else:
        bu, kaynak = [], "hiçbir ders (program boş)"
    planlar = [{"planId": anadal_id, "role": "ANADAL", "label": "anadal",
                "program": settings.anadal_program}]
    planlar += [{"planId": s["planId"], "role": s["role"], "label": s["label"],
                 "program": s["program"]} for s in seconds if s.get("planId")]
    def kur(bu_donem, yaz=None):
        return YH.kur(con, grades, planlar, term=term, donem=donem or 0,
                      max_load=float(sinir), bu_donem=bu_donem, bu_donem_kaynagi=kaynak,
                      equivalences=equivalences, taban=taban, yaz=yaz,
                      mesgul=REC.busy_sections(settings.mesgul),          # Faz 82
                      oncelik=settings.yol_onceligi)                      # Faz 118

    def bitisler(h):
        return {p["role"]: (p["finish"] or {}).get("index") for p in h["programs"]}

    def kazanc_olc(once: dict, yeni: dict) -> list[dict]:
        out = []
        for p in yeni["programs"]:
            a, b = once.get(p["role"]), (p["finish"] or {}).get("index")
            if a is not None and b is not None and b < a:
                out.append({"role": p["role"], "label": p["label"],
                            "terms": a - b, "finish": p["finish"]})
        return out

    # ★★ FAZ 63 — TRANSKRİPT YOKKEN HARİTA YOK (gerçek katalogda ölçüldü).
    # 2+. yarıyılda olduğunu söyleyip geçtiğin dersleri girmediysen harita
    # planın TAMAMINI kalan sayıyordu: "13. yarıyılda bitersin, azami süreyi
    # aşıyorsun" — hakkında hiçbir şey bilmediğimiz kişiye yanlış ve korkutucu
    # bir cevap. İlerleme panelleri bunu Faz 26'da düzeltmişti ("İlerleme
    # bilinmiyor"); harita da aynı kuralı izliyor. 1. yarıyılda boş
    # transkript doğru — harita kuruluyor.
    if _transkript_eksik(donem, grades):
        return {"noTranscript": True, "donem": donem}
    try:
        sonuc = kur(bu)
        # ★ "BU DÖNEM ŞUNU ALIRSAN" — haritanın asıl işe yarayan cevabı.
        # Bu dönem aday havuzunda olup programda OLMAYAN, arkasından zincir
        # gelen dersler için harita yeniden kuruluyor ve bitiş dönemi
        # karşılaştırılıyor. Yalnız ölçülen kazanç yazılıyor; saat çakışması
        # ve yük sınırı burada ÇÖZÜLMÜYOR, ekranda söyleniyor.
        # ⚠️ En çok 5 aday: statik sitede her kurulum Pyodide'da çalışıyor.
        simdiki = bitisler(sonuc)
        yuk = sum(float(x["credits"] or 0) for x in bu)
        adaylar = [h for h in sonuc.get("heads", [])
                   if h["course"] in ders and ders[h["course"]].sections
                   and h["chain"] >= 2][:5]
        etki = []
        for h in adaylar:
            c = ders[h["course"]]
            # Faz 81 — eklenen ders, bu dönemin dersleriyle çakışmayan yuvaya.
            yuva = _yuvalar_ata([ders.get(x["course"]) for x in bu] + [c])[-1]
            bas = {"course": c.course, "credits": c.credits,
                   "slotId": yuva, "role": c.role}
            yeni = kur([*bu, bas])
            kazanc = kazanc_olc(simdiki, yeni)
            if kazanc:
                etki.append({"course": c.course, "name": c.name, "credits": c.credits,
                             "role": c.role, "gains": kazanc,
                             "overLoad": yuk + c.credits > float(sinir) + 1e-9,
                             "_bas": bas, "_yeni": bitisler(yeni)})
        # ★★ Faz 58 — YÜK AŞILIYORSA HANGİ DERS ÇIKSIN. "Bir dersi çıkarman
        # gerekir" deyip bırakmak, kararı en zor yerinde kullanıcıya
        # bırakıyordu. Programdaki her ders tek tek çıkarılıp harita yeniden
        # kuruluyor; kazancı KORUYAN ve yükü sınıra indiren çıkarma öneriliyor.
        # Kazancı tam koruyan yoksa en az kaybettiren — kayıp YAZIYOR.
        # ⚠️ En çok 2 aday × programdaki ders sayısı kurulum (Pyodide).
        # ⚠️ ÇAP yarıyıl tabanını bu dönem BOZAN çıkarma önerilmiyor — yük
        # sınırını tutturmak için yönetmelik ihlali önermek olurdu.
        def cap_kredi(liste):
            return sum(float(y["credits"] or 0) for y in liste if y.get("role") == "CAP")
        for e in [x for x in etki if x["overLoad"]][:2]:
            fazla = yuk + e["credits"] - float(sinir)
            en_iyi = None
            for x in bu:
                if float(x["credits"] or 0) + 1e-9 < fazla:
                    continue                    # tek başına yetmiyor
                sonra = [y for y in bu if y is not x] + [e["_bas"]]
                if taban and cap_kredi(sonra) + 1e-9 < taban.minimum <= cap_kredi(bu) + 1e-9:
                    continue
                dene = bitisler(kur(sonra))
                kayip = sum((dene.get(r) if dene.get(r) is not None else 99) - v
                            for r, v in e["_yeni"].items() if v is not None)
                anahtar = (max(0, kayip), x["role"] == "ANADAL", x["course"])
                if en_iyi is None or anahtar < en_iyi[0]:
                    en_iyi = (anahtar, x, max(0, kayip))
            if en_iyi:
                _, x, kayip = en_iyi
                ad = (ders[x["course"]].name if x["course"] in ders else
                      (con.execute("SELECT name FROM course WHERE code=?",
                                   (x["course"],)).fetchone() or [""])[0])
                e["drop"] = {"course": x["course"], "name": ad, "lossTerms": kayip}
        for e in etki:
            e.pop("_bas", None), e.pop("_yeni", None)
        sonuc["takeNow"] = etki
        # ★★ Faz 58 — YAZ OKULU. Geçmişte yazın gerçekten açılmış (not
        # dağılımı, en az `YH.GECMIS_TABAN` öğrenci) ders ilk yazda alınırsa
        # bitiş değişiyor mu? Yalnız değişenler yazılıyor.
        yazlar = []
        for a in sonuc.get("summerCandidates", [])[:8]:
            yeni = kur(bu, yaz=a["course"])
            if not (yeni.get("summer") or {}).get("placed"):
                continue
            kazanc = kazanc_olc(simdiki, yeni)
            if kazanc:
                yazlar.append({"course": a["course"], "name": a["name"],
                               "credits": a["credits"], "history": a["history"],
                               "term": yeni["summer"]["label"], "gains": kazanc})
        sonuc["summerGains"] = yazlar
        # Faz 59 — azami öğrenim süresi (beyan edilmişse; doğrulanma durumuyla).
        az = POL.load_max_duration()
        sonuc["maxDuration"] = ({"semesters": az.semesters, "verified": az.verified,
                                 "source": az.source, "note": az.note} if az else None)
        return sonuc
    except Exception as exc:                            # noqa: BLE001
        # Harita yardımcı bir görünüm: kurulamazsa sayfanın geri kalanı
        # açılmalı — ama sessiz değil, sebebi görünümde yazıyor.
        return {"error": f"{type(exc).__name__}: {exc}"}


def _transkript_eksik(donem, grades) -> bool:
    """Faz 63 — 2+. yarıyılda ama geçilmiş TEK ders yok: harita kurulmaz.

    Sayfadaki harita ve istek üzerine kurulanlar (ÇAP seçenekleri,
    senaryolar) AYNI kuralı buradan alıyor."""
    return (donem or 0) >= 2 and not any(R.passed(g) for g in (grades or {}).values())


def _harita_girdisi(con, ucon, student_id: int, settings, bu_donem, max_load) -> dict:
    """İstek üzerine kurulan haritaların (ÇAP seçenekleri, senaryolar) ORTAK
    girdisi ve doğrulaması — ikisi ayrışırsa aynı öğrenci için iki farklı
    harita çıkardı."""
    from .plans import anadal_plan
    anadal_id = anadal_plan(con, settings)
    term = _aktif_donem(con, settings)
    if not anadal_id or len(term) != 6:
        raise ValueError("anadal planı ya da dönem bilinmiyor")
    try:
        max_load = float(max_load)
    except (TypeError, ValueError):
        raise ValueError("kredi sınırı geçersiz") from None
    if not 1 <= max_load <= 60:
        raise ValueError("kredi sınırı geçersiz")
    grades = S.grades(ucon, student_id)
    if _transkript_eksik(int(settings.donem or 0), grades):
        raise ValueError("başarılan dersler girilmediği için bitiş tahmini yapılamıyor")

    def _slot(x):
        # ★★ Faz 79 — seçmeli dersin doldurduğu HAVUZ YUVASI. Eskiden 0'a
        # sabitti: sayfadaki harita yuvayı biliyordu (`_yol_haritasi`), istek
        # üzerine kurulanlar bilmiyordu → bu dönem alınan seçmelinin yuvası
        # BOŞ sayılıp ileri bir döneme bir ders daha konuyordu. Gerçek sitede
        # (ENDE, 3 seçmeli): kalma riskinin tabanı 2027-2028 Bahar, sayfadaki
        # harita 2027-2028 Güz — aynı program için iki bitiş.
        try:
            return max(0, int(x.get("slotId") or 0))
        except (TypeError, ValueError):
            return 0
    return {
        "anadal_id": anadal_id, "term": term, "max_load": max_load,
        "grades": grades,
        "equivalences": R.load_equivalences(con, ucon=ucon),
        "donem": int(settings.donem or 0),
        "bu": [{"course": str(x.get("course") or ""), "credits": float(x.get("credits") or 0),
                "slotId": _slot(x), "role": str(x.get("role") or "")}
               for x in (bu_donem or [])[:20] if x.get("course")],
        "anadal": {"planId": anadal_id, "role": "ANADAL", "label": "anadal",
                   "program": settings.anadal_program},
    }


def _senaryo_planlari(con, settings, g: dict) -> tuple[list[dict], object]:
    """Senaryo haritalarının plan listesi ve ÇAP tabanı — `collect` ile AYNI
    kaynaktan (`resolve_seconds`, `cap_baslangic_yariyili`)."""
    from .plans import resolve_seconds
    ikinci = resolve_seconds(con, settings)
    cap = next((x for x in ikinci if x.get("kind") == "cap" and x.get("planId")), None)
    taban = POL.second_floor(settings.cap_baslangic_yariyili) if cap else None
    planlar = [g["anadal"]] + [{"planId": x["planId"], "role": x["role"], "label": x["label"],
                                "program": x["program"]} for x in ikinci if x.get("planId")]
    return planlar, taban


@_sube_onbellekli
def kalma_riski(con: sqlite3.Connection, ucon: sqlite3.Connection, student_id: int,
                settings, bu_donem: list[dict], max_load) -> dict:
    """★★ Faz 75 — "Bu dersten kalırsam mezuniyetim ne kadar gecikir?"

    Öğrencinin dönem boyunca en çok sorduğu şeylerden biri; cevabı ancak
    haritayı yeniden kurarak ölçülebiliyor. Taban: bu dönemin programı
    (`bu_donem`) geçilmiş varsayılarak kurulan harita. Her ders için: o ders
    ÇIKARILARAK (kalınmış = hâlâ alınacak) yeniden kuruluyor; her programın
    bitiş yarıyılı tabanla karşılaştırılıyor. Önşart zinciri, açıldığı
    yarıyıl ve dönem kredi sınırı haritanın kendi kuralları — ayrı bir hesap
    yok. Salt okunur; hiçbir şey kaydedilmiyor.

    Bitişi bilinmeyen program (UOLP, yerleşemeyen ders) için gecikme `None`:
    "0 dönem" demek uydurma olurdu.
    """
    g = _harita_girdisi(con, ucon, student_id, settings, bu_donem, max_load)
    planlar, taban = _senaryo_planlari(con, settings, g)

    def kur(bu):
        return YH.kur(con, g["grades"], planlar, term=g["term"], donem=g["donem"],
                      max_load=g["max_load"], bu_donem=bu, bu_donem_kaynagi="senaryo",
                      equivalences=g["equivalences"], taban=taban,
                      mesgul=REC.busy_sections(settings.mesgul),
                      oncelik=settings.yol_onceligi)                      # Faz 118

    def bitisler(h):
        return {p["role"]: p for p in h.get("programs") or []}

    taban_h = bitisler(kur(g["bu"]))
    dersler = []
    for x in g["bu"]:
        h = bitisler(kur([y for y in g["bu"] if y["course"] != x["course"]]))
        programlar = []
        for rol, b in taban_h.items():
            k = h.get(rol) or {}
            once, sonra = b.get("finishSemester"), k.get("finishSemester")
            programlar.append({
                "role": rol, "label": b.get("label") or rol, "program": b.get("program", ""),
                "finish": k.get("finish"), "finishSemester": sonra,
                "delay": (sonra - once) if once is not None and sonra is not None else None,
            })
        dersler.append({"course": x["course"], "credits": x["credits"], "programs": programlar})
    return {"base": [{"role": r, "label": b.get("label") or r, "program": b.get("program", ""),
                      "finish": b.get("finish"), "finishSemester": b.get("finishSemester")}
                     for r, b in taban_h.items()],
            "courses": dersler, "maxLoad": g["max_load"]}


@_sube_onbellekli
def yol_senaryosu(con: sqlite3.Connection, ucon: sqlite3.Connection, student_id: int,
                  settings, bu_donem: list[dict], max_load, bos, zor=None) -> dict:
    """Faz 61 — yol haritası SENARYOSU: daha hafif dönem yükü ve boş dönemler.

    "Çalışıyorum, dönemde en çok 18 kredi alabilirim", "3. dönem Erasmus'a
    gidiyorum" — ikisi de bitişi değiştiriyor ve ikisi de ancak haritayı
    YENİDEN kurarak ölçülebiliyor. Kaydedilmiyor (salt okunur
    `/api/yolharitasi`); arayüz sonucu bugünkü haritayla karşılaştırıyor.
    Programlar ve ÇAP tabanı `collect` ile AYNI kaynaktan (`resolve_seconds`,
    `cap_baslangic_yariyili`).
    """
    g = _harita_girdisi(con, ucon, student_id, settings, bu_donem, max_load)
    try:
        bos = sorted({int(x) for x in (bos or [])})
    except (TypeError, ValueError):
        raise ValueError("boş dönem geçersiz") from None
    if any(not 1 <= x <= YH.UFUK for x in bos) or len(bos) > 6:
        raise ValueError("boş dönem geçersiz")
    # ★ Faz 89 — dönem başına en çok N zor ders (1–5); yok/0 → sınır yok.
    try:
        zor = int(zor) if zor not in (None, "", 0, "0") else None
    except (TypeError, ValueError):
        raise ValueError("zor ders sınırı geçersiz") from None
    if zor is not None and not 1 <= zor <= 5:
        raise ValueError("zor ders sınırı geçersiz")
    planlar, taban = _senaryo_planlari(con, settings, g)
    h = YH.kur(con, g["grades"], planlar, term=g["term"], donem=g["donem"],
               max_load=g["max_load"], bu_donem=g["bu"],
               bu_donem_kaynagi="senaryo", equivalences=g["equivalences"],
               taban=taban, bos=bos, mesgul=REC.busy_sections(settings.mesgul),
               zor_siniri=zor, oncelik=settings.yol_onceligi)             # Faz 118
    az = POL.load_max_duration()
    h["maxDuration"] = ({"semesters": az.semesters, "verified": az.verified,
                         "source": az.source, "note": az.note} if az else None)
    h["scenario"] = {"maxLoad": g["max_load"], "empty": bos, "hardMax": zor,
                     "loadBand": yuk_basamagi(g["max_load"])}             # Faz 119
    return h


def yuk_basamagi(kredi: float) -> dict | None:
    """★ Faz 119 — bu dönem yükü yönetmelikte hangi GNO ile alınabiliyor
    (MADDE 17/2 basamakları, `kurallar.toml` [[kredi_yuku]]).

    Senaryoya artık serbest değer giriliyor; mevcut sınırın ÜSTÜNDE bir yük
    ancak GNO şartıyla alınabilir ve arayüz bunu söylüyor. En yüksek
    basamağın da üstündeyse `aboveMax` — yönetmelik bu yükü hiç tanımıyor.
    Basamak beyan edilmemişse `None` (şart uydurulmuyor)."""
    bantlar, _ = POL.load_bands()
    if not bantlar:
        return None
    uyan = [b for b in bantlar if b.max_credits + 1e-9 >= kredi]
    if not uyan:
        en_ust = max(bantlar, key=lambda b: b.max_credits)
        return {"aboveMax": True, "max": en_ust.max_credits, "minGpa": None, "label": ""}
    b = min(uyan, key=lambda b: (b.min_gpa, b.max_credits))
    return {"aboveMax": False, "max": b.max_credits, "minGpa": b.min_gpa, "label": b.label}


@_sube_onbellekli
def cap_bitisleri(con: sqlite3.Connection, ucon: sqlite3.Connection, student_id: int,
                  settings, plan_ids: list, bu_donem: list[dict],
                  max_load: float) -> dict:
    """Faz 59 — "Ya ÇAP'ı şu bölümde yapsaydım?" (fikirler Y.1).

    Başvuru penceresi her ÇAP programı için "sende sayılan ders" sayısını
    veriyordu; asıl soruyu — **ne zaman biterim** — cevaplamıyordu. Yol
    haritası motoru herhangi bir plan listesiyle çalışıyor: anadal + aday
    ÇAP planı birlikte kuruluyor.

    Varsayımlar (arayüz yazıyor): ÇAP'a **bir sonraki yarıyıl** başlanıyor
    (yarıyıl tabanı ona göre); bu dönem yol haritasındaki dersler alınıyor;
    başvurunun kabulü, kontenjan ve sıralama şartı bu hesapta YOK. Şu anki
    ÇAP/yandal plana girmiyor — soru "onun yerine bu olsaydı".

    ⚠️ Salt okunur ve istek üzerine (`/api/capbitis`): 60 programı sayfa
    açılırken kurmak statik sitede (Pyodide) saniyeler sürerdi.
    """
    g = _harita_girdisi(con, ucon, student_id, settings, bu_donem, max_load)
    anadal_id, term, max_load = g["anadal_id"], g["term"], g["max_load"]
    grades, equivalences, donem, bu = g["grades"], g["equivalences"], g["donem"], g["bu"]
    taban = POL.second_floor(donem + 1) if donem else None
    anadal = g["anadal"]

    def kur(planlar):
        return YH.kur(con, grades, planlar, term=term, donem=donem, max_load=max_load,
                      bu_donem=bu, equivalences=equivalences, taban=taban,
                      mesgul=REC.busy_sections(settings.mesgul),
                      oncelik=settings.yol_onceligi)                      # Faz 118

    def bitis(h, rol):
        p = next((p for p in h["programs"] if p["role"] == rol), None)
        return p, ((p or {}).get("finish") or {}).get("index")

    _, yalniz = bitis(kur([anadal]), "ANADAL")
    sonuc = {}
    for pid in list(plan_ids or [])[:60]:
        try:
            pid = int(pid)
        except (TypeError, ValueError):
            continue
        row = con.execute("SELECT program_code FROM plan WHERE id=? AND plan_type='cap'",
                          (pid,)).fetchone()
        if not row:
            continue
        h = kur([anadal, {"planId": pid, "role": "CAP", "label": "ÇAP",
                          "program": row[0]}])
        cap, cap_i = bitis(h, "CAP")
        _, ana_i = bitis(h, "ANADAL")
        sonuc[str(pid)] = {
            "finish": cap["finish"] if cap else None,
            "finishSemester": cap.get("finishSemester") if cap else None,
            "remaining": cap["remaining"] if cap else 0,
            # ⚠️ Kalan KREDİ bilerek yok: başvuru penceresi onu göstermiyor
            # (22.08.2026 — havuz slotlarının kredisi programdan programa farklı).
            "unplaced": cap["unplaced"] if cap else 0,
            # ÇAP anadalı geciktiriyor mu — yalnız anadalla kurulan haritaya göre.
            "anadalDelay": (ana_i - yalniz if ana_i is not None and yalniz is not None
                            else None),
            "floorShort": sum(1 for t in h["terms"] if t.get("floorGap")),
            "unknownSeason": h["unknownSeason"],
        }
    return {"startTerm": donem + 1 if donem else None,
            "floor": taban.minimum if taban else None,
            "anadalAlone": yalniz, "results": sonuc}


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
        return ("Katalogda açık şube bulunmamaktadır; ders programı henüz "
                "yayımlanmamış olabilir (make refresh).")
    if not anadal_id:
        return "Anadal planı bulunamadı. Lütfen bölüm seçiminizi kontrol edin."
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
    return (f"{toplam_sube} şubenin hiçbiri şu program kodlarına açık değildir: "
            + ", ".join(sorted(kodlar))
            + ". Program penceresindeki “Gelişmiş → Kayıt yapılabilen program "
              "kodları” alanı boşaltıldığında kodlar seçilen bölümlerden türetilir.")


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


def _derslik(room: str | None) -> str:
    """Faz 93 — derslik; ilan edilmemişse ("--") BOŞ. `_building` ile aynı
    ilke: "--" bir sınıf adı değil, boş gelen yeri arayüz söylüyor."""
    temiz = (room or "").strip()
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
    parts = [f"{now} dönemlik ({donem}. dönem)"]
    # ★ Faz 84 — 1. dönemde "alttan" diye bir şey yok: gerçek sitede
    # "0 alttan (1–0. dönem)" yazıyordu.
    if donem > 1:
        parts.append(f"{below} alttan (1–{donem - 1}. dönem)")
    if free:
        parts.append(f"{free} {second_label or 'ikinci program'} (planda dönem bilgisi yok; tüm dersler dahil)")
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
    # ★ Faz 56 — palet ve ölçekler tek kaynaktan (`tasarim.py`).
    html = (html.replace("__JETONLAR__", TASARIM.css_jetonlari())
            .replace("__JETONLAR_KAGIT__", TASARIM.css_kagit()))
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
     * koyu ama yumuşak zemin (#1A1F29, Faz 70'te açıldı) — saf siyah değil, mavi eğilimli
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
/* ★★ FAZ 56 — PALET VE ÖLÇEKLER ÜRETİLİYOR (`src/itucap/tasarim.py`).
   Bu üç blok eskiden burada ELLE yazılıydı, kâğıt bloğuyla dört kopya.
   İki kez ayrıştılar: Faz 38b'de `--yandal*` açık blokta unutuldu, Faz 43'te
   iki yeni jeton üç bloğa tek tek eklendi. Faz 43'ün ölçtüğü AA düzeltmeleri
   (`--ink-3`, `--border-strong`) ve Faz 40'ın ton merdiveni aynı değerlerle
   `tasarim.RENKLER`de duruyor — değer değişmedi, yeri değişti. */
__JETONLAR__
*{box-sizing:border-box}
/* ★ Faz 56 — içeriğe atla: odaklanana kadar ekranın dışında. */
.atla{position:absolute;left:var(--sp-4);top:-80px;z-index:var(--z-skip);
  padding:var(--sp-4) var(--sp-6);background:var(--seal);color:var(--on-seal);
  font-family:var(--font-display);font-weight:700;font-size:var(--fs-md);
  text-decoration:none}
.atla:focus{top:var(--sp-4)}
#icerik:focus{outline:none}
/* ★★ `hidden` GERÇEKTEN gizlesin (24.08.2026 ölçümü).
   Tarayıcının `[hidden]{display:none}` kuralı en zayıf özgüllükte; `.ghost`
   ya da `.radios` gibi display kuran HER sınıf onu eziyor ve `hidden`
   sessizce işlevsiz kalıyordu ("Veriyi tazele" düğmesi gizlenmesi gereken
   yerde duruyordu). Bu tek satır hata sınıfının tamamını kapatıyor. */
[hidden]{display:none !important}
body{margin:0;background:var(--ground);color:var(--ink);
  font:400 var(--fs-base)/var(--lh-body) var(--font-sans);
  -webkit-font-smoothing:antialiased}
.mono{font-family:var(--font-mono);
  font-variant-numeric:tabular-nums}
/* Çerçeve genişliği: BÜTÜN SEKMELERDE AYNI (Faz 52 — aşağıdaki nota bak). */
.wrap{max-width:1720px;margin:0 auto;padding:32px 24px 80px;display:flex;
  flex-direction:column;gap:32px}
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
/* ★★ FAZ 56 — AÇIKLAMA PARAGRAFI ESNEK SATIR DEĞİL.
   Bölüm açıklamaları `.summary` taşıyordu; o bir ESNEK sayı satırı (gap
   14px) ve içine düz yazı konunca her `<b>` ayrı bir öğe oluyor. Vitrin
   ekranında ölçüldü: Kademeler'de "Çizgiler önşart bağıdır" cümlenin
   ortasında kendi satırına kırılıyordu. v1 tasarım sistemi bu kuralı
   yazmıştı (`.aciklama`), uygulama hiç almamıştı. Esnek kutu sınıfının
   dördüncü görülüşü (bkz. Faz 48 `summary`, Faz 50 "20KREDİ"). */
.aciklama{font-size:var(--fs-lg);color:var(--ink-2);margin-top:2px;
  line-height:var(--lh-body)}
main .aciklama{max-width:80ch}
/* Chivo, ağır ve büyük harf — Şematik'in sesi. Gövde IBM Plex Sans'ta kalıyor;
   Chivo'yu uzun metinde kullanmak gece zemininde yorucu olurdu. */
h1,h2,h3{margin:0;text-wrap:balance;
  font-family:var(--font-display);font-weight:800;
  text-transform:uppercase}
h1{font-size:var(--fs-4xl);letter-spacing:var(--ls-tight);line-height:var(--lh-tight);font-weight:900}
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
.acilim{margin-top:6px;font-family:var(--font-display);
  font-size:var(--fs-sm);letter-spacing:var(--ls-label);color:var(--ink-3);font-weight:600;
  text-transform:uppercase}
.acilim b{color:var(--seal);font-weight:900;letter-spacing:var(--ls-caps)}
/* ★ Faz 56 — h2 15 → 18px. Bölüm başlığı gövdeyle AYNI boydaydı; tek
   ayrım ağırlık ve büyük harfti. Ölçek basamağı `fs-xl`. */
h2{font-size:var(--fs-xl);letter-spacing:var(--ls-0);font-weight:800;line-height:var(--lh-tight)}
.eyebrow{font-size:var(--fs-xs);font-weight:700;letter-spacing:var(--ls-eyebrow);text-transform:uppercase;
  color:var(--seal);font-family:var(--font-display)}
/* Belge başlığı: kalın yapısal cetvel + ince alt cetvel. */
header{padding-bottom:16px;border-bottom:1px solid var(--border)}
header .masthead{display:flex;flex-wrap:wrap;align-items:flex-end;
  justify-content:space-between;gap:16px;
  padding-bottom:14px;border-bottom:3px solid var(--seal);margin-bottom:4px}
header .sub{color:var(--ink-2);font-size:var(--fs-lg);margin-top:6px}
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
body:not(.kurulum) header h1{font-size:var(--fs-3xl);letter-spacing:var(--ls-tight);order:1}
/* Tek satırda ad ÖNCE okunmalı; eyebrow (program listesi) onu izler. */
body:not(.kurulum) header .eyebrow{order:2}
body:not(.kurulum) header .acilim{display:none}
body:not(.kurulum) header .sub{margin:0;font-size:var(--fs-md)}
body:not(.kurulum) header #theme{margin-left:auto;order:9}
/* ⚠️ "tazele" düğmesi CÜMLENİN İÇİNDE duruyordu; 390px'te satır düğmenin
   ortasından kırılıyor, hem okuma hem tıklama bozuluyordu (ölçüldü).
   Satır artık esnek: metin bir parça, düğme ayrı bir parça. */
.veriyasi{display:flex;flex-wrap:wrap;align-items:center;gap:4px 8px}
/* ★★ FAZ 46 — haftalık programın düzeni: ızgara solda, bağlam sağda. */
/* ★★ FAZ 47 — sağ sütun 330 → 240px ve düğmeler ALT ALTA (kullanıcı
   isteği: *"genişliğini azaltıp yukardan aşağıya tuşları listeleyip"*).
   Kazanılan 90px doğrudan ızgaraya gidiyor. */
.prgduzen{display:grid;grid-template-columns:minmax(0,1fr) 240px;gap:20px;
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
.ipucu>summary{cursor:pointer;font-size:var(--fs-md);color:var(--ink-2);
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
.ghost{border:1px solid var(--border-control);border-radius:var(--r);
  padding:8px 14px;min-height:34px;
  font-size:var(--fs-md);background:transparent;font-weight:600;letter-spacing:var(--ls-wide);
  font-family:var(--font-display)}
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
:focus-visible{outline:2px solid var(--focus);outline-offset:2px;border-radius:var(--r)}
/* Şematik: kutu değil cetvel. Kart, üstündeki kalın çizgiyle bölünüyor;
   kenarlık yalnız hafif bir hat olarak kalıyor. */
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--r)}
.pad{padding:20px 24px}
/* Bölüm başlığı: büyük harf etiket + sona kadar uzanan yapısal cetvel */
.sechead{display:flex;align-items:center;gap:12px;margin-bottom:2px}
.sechead .rule{flex:1;height:2px;background:var(--border-strong);opacity:.55}

.panels{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:20px}
.panel{border-top:6px solid var(--accent)}
.panel[data-role="ANADAL"]{--accent:var(--anadal);--soft:var(--anadal-soft)}
.panel[data-role="CAP"]{--accent:var(--cap);--soft:var(--cap-soft)}
.panel[data-role="YANDAL"]{--accent:var(--yandal);--soft:var(--yandal-soft)}
.panel .top{display:flex;align-items:baseline;gap:10px;justify-content:space-between}
.panel .pctbox{text-align:right;line-height:var(--lh-none)}
.panel .pct{font-family:var(--font-mono);font-variant-numeric:tabular-nums;
  font-size:var(--fs-3xl);font-weight:600;color:var(--accent);letter-spacing:var(--ls-tight)}
/* ★ Büyük yüzde etiketsizdi — ne olduğu (tamamlanma) belirsizdi (01.09.2026). */
.panel .pctlbl{font-family:var(--font-display);font-size:var(--fs-xs);
  font-weight:700;letter-spacing:var(--ls-label);text-transform:uppercase;color:var(--ink-3);
  margin-top:4px}
/* ★ Transkript yokken yüzde bir ÖLÇÜM değil: "%0" yerine "—". */
.panel .pct.unknown{color:var(--ink-3)}
.panel .name{color:var(--ink-2);font-size:var(--fs-md);margin:4px 0 16px}
.proj.bilinmiyor{border-left:3px solid var(--warn);padding:8px 10px;
  background:var(--surface-2);margin-bottom:12px;line-height:var(--lh-body)}

/* ★ İki katmanlı ölçek: dolu = geçilmiş, taralı = bu dönem seçili.
   'Bu dönemi bitirirsen nerede olursun' sorusunun görsel cevabı. */
.meter{height:10px;background:var(--surface-2);border:1px solid var(--border);
  border-radius:var(--r);overflow:hidden;display:flex}
.meter i{display:block;height:100%;background:var(--accent)}
.meter i.plan{background:repeating-linear-gradient(135deg,
  var(--accent) 0 3px,transparent 3px 6px);opacity:.72}
.proj{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px;margin-top:10px;
  font-size:var(--fs-md);color:var(--ink-2);min-height:19px}
.proj .arrow{color:var(--ink-3)}
.proj b{color:var(--accent);font-weight:600}
.proj .flat{color:var(--ink-3)}
.stats{display:flex;flex-wrap:wrap;gap:16px;margin-top:12px;font-size:var(--fs-md);
  color:var(--ink-2);padding-top:12px;border-top:1px solid var(--border)}
.stats b{color:var(--ink);font-weight:600}
.stats .gain{color:var(--accent);font-weight:600}
.cats{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}
.cat{font-size:var(--fs-xs);padding:4px 8px;border:1px solid var(--border);border-radius:var(--r);
  background:var(--soft);color:var(--accent);font-weight:600;letter-spacing:var(--ls-wide)}
.cat.zero{background:transparent;color:var(--ink-3)}
/* ★ Faz 99 — planın dönem dönem durumu. Her dönem bir sütun: dolu kısım
   tamamlanan yuva oranı. Bulunulan dönem çerçeveli; ÖNCEKİ dönemlerde açık
   yuva kalmışsa uyarı rengi (geride kalan ders). */
.dnmbas{margin-top:14px;padding-top:12px;border-top:1px solid var(--border);
  font-size:var(--fs-xs);color:var(--ink-3)}
.dnmler{display:grid;grid-template-columns:repeat(auto-fit,minmax(30px,1fr));gap:4px;margin-top:6px}
.dnm{display:flex;flex-direction:column;align-items:center;gap:4px;padding:4px 0;
  border:1px solid transparent;border-radius:var(--r);font-size:var(--fs-xs);color:var(--ink-3)}
.dnm .dbar{width:10px;height:34px;background:var(--surface-2);border:1px solid var(--border);
  border-radius:var(--r);overflow:hidden;display:flex;flex-direction:column;justify-content:flex-end}
.dnm .dbar i{display:block;width:100%;background:var(--accent)}
.dnm .dno{font-weight:700;color:var(--ink-2)}
.dnm.tamam .dbar i{background:var(--ok)}
.dnm.geride .dbar{border-color:var(--warn)}
.dnm.geride .dno{color:var(--warn-ink)}
.dnm.simdi{border-color:var(--accent);background:var(--soft)}
.kalan{margin-top:12px;font-size:var(--fs-sm);color:var(--ink-2)}
.kalan + .kalan{margin-top:8px}
.kalan .kbas{font-weight:600;margin-bottom:6px}
.kalan .kbas.geride{color:var(--warn-ink)}
.kalan .kliste{display:flex;flex-wrap:wrap;gap:4px}
.kders{font-family:var(--font-mono);font-size:var(--fs-xs);padding:2px 6px;
  border:1px solid var(--border);border-radius:var(--r);background:var(--surface);color:var(--ink-2)}
button.kders{cursor:pointer}
button.kders:hover{border-color:var(--accent);color:var(--accent)}
.kders.havuz{font-family:inherit;border-style:dashed}
.kders.secili{border-color:var(--accent);background:var(--soft);color:var(--accent)}

.tabs{display:flex;gap:0;flex-wrap:wrap;border:1px solid var(--border);
  border-radius:var(--r);overflow:hidden;background:var(--surface)}
.tab{border:0;border-left:1px solid var(--border);background:transparent;
  padding:8px 12px;font-size:var(--fs-xs);color:var(--ink-2);font-weight:600;
  letter-spacing:var(--ls-caps);text-transform:uppercase;
  font-family:var(--font-display)}
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
  border:1px solid var(--border-control);
  border-radius:var(--r);overflow:hidden;background:var(--surface)}
.modebtn{padding:6px 14px;font-size:var(--fs-md);color:var(--ink-2);cursor:pointer;
  border-left:1px solid var(--border)}
.modebtn:first-child{border-left:0}
.modebtn[aria-pressed="true"]{background:var(--seal-soft);color:var(--seal);font-weight:600}
.modenote{font-size:var(--fs-sm);color:var(--ink-3);margin-top:8px}
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
  padding:12px 14px;border:1px solid var(--border);border-left:3px solid var(--seal);
  border-radius:var(--r);background:var(--surface)}
.setupbar .who{font-size:var(--fs-md);color:var(--ink-2);margin-right:auto}
.setupbar .who b{color:var(--ink);font-weight:600}
.setupbar .ro{font-size:var(--fs-sm);color:var(--ink-3)}
/* Faz 54 — sitede verinin yedeği: kendi satırında, çubuğun altında. */
.setupbar .verikutusu{flex-basis:100%;margin-top:8px;padding:12px 14px;
  border:1px solid var(--border);border-left:3px solid var(--seal);
  background:var(--surface);font-size:var(--fs-lg);line-height:var(--lh-normal);color:var(--ink-2)}
.verikutusu b{color:var(--ink)}
.veridugmeler{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
.verikalici,.veriyedek{margin-top:8px;font-size:var(--fs-md)}
.veriyedek:empty{display:none}
.heroyedek{margin-top:8px}
/* Kısa bildirim — kip pencere DEĞİL: sayfayı kilitlemiyor. */
.bildirim{position:fixed;left:50%;bottom:22px;transform:translateX(-50%) translateY(12px);
  background:var(--seal);color:var(--ground);padding:10px 16px;border-radius:var(--r);
  font-size:var(--fs-lg);box-shadow:var(--shadow-toast);z-index:var(--z-toast);
  opacity:0;pointer-events:none;transition:opacity var(--dur-base),transform var(--dur-base);max-width:min(92vw,520px)}
.bildirim.acik{opacity:1;transform:translateX(-50%) translateY(0)}
@media (prefers-reduced-motion:reduce){.bildirim{transition:none}}
/* Satır içi küçük düğme — veri yaşının yanındaki "tazele". */
.ghost.mini{font-size:var(--fs-sm);padding:1px 8px;vertical-align:baseline}
/* Türetilen program kodları — okunur rozet; önerilenler tıklanabilir. */
.kodlar{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:2px 0 4px}
.kod{font-family:var(--font-mono);
  font-size:var(--fs-sm);padding:2px 10px;border-radius:var(--r);
  border:1px solid var(--border-control);color:var(--ink-2);background:var(--surface)}
.kod.ekle{cursor:pointer;border-style:dashed;color:var(--seal)}
.kod.ekle:hover{border-style:solid;background:var(--surface-2)}
/* Seçili ama planı bulunamayan ikinci program — seçim duruyor, hesap yok. */
.setupbar .uyari{font-size:var(--fs-xs);padding:1px 6px;border:1px solid var(--warn);
  color:var(--warn);border-radius:var(--r);white-space:nowrap}
.ghost[disabled]{opacity:.45;cursor:not-allowed}
/* Meşgul düğme dönen halkası — "kaydediliyor" belli olsun (kullanıcı isteği
   28.08.2026). Meşgulken opaklığı düşürmüyoruz ki metin+dönme okunur kalsın. */
.ghost.mesgul{opacity:1;cursor:progress}
.spin{display:inline-block;width:13px;height:13px;vertical-align:-2px;
  margin-right:8px;border:2px solid currentColor;border-top-color:transparent;
  border-radius:var(--r-round);animation:spin var(--dur-spin) linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
@media(prefers-reduced-motion:reduce){.spin{animation:none;border-top-color:currentColor}}
.ghost.primary{background:var(--seal);color:var(--ground);border-color:var(--seal);
  font-weight:600}
/* ★ Faz 56 — `--seal-hover` Faz 43'ten beri TANIMLIYDI ama hiç kullanılmıyordu;
   üzerine gelme hâlâ opaklıkla yapılıyordu (zemin de soluyor). */
.ghost.primary:hover{background:var(--seal-hover);border-color:var(--seal-hover);
  color:var(--on-seal)}

/* form öğeleri */
.field{display:block;margin-top:12px}
.field>span{display:block;font-size:var(--fs-xs);font-weight:600;letter-spacing:var(--ls-label);
  text-transform:uppercase;color:var(--seal);margin-bottom:6px}
.field .hint{font-size:var(--fs-sm);color:var(--ink-3);margin-top:4px;letter-spacing:var(--ls-0);
  text-transform:none;font-weight:400}
select,input[type=text],input[type=search],textarea{
  font:inherit;font-size:var(--fs-lg);width:100%;padding:8px 10px;color:var(--ink);
  background:var(--surface);border:1px solid var(--border-control);border-radius:var(--r)}
textarea{font-family:var(--font-mono);font-size:var(--fs-md);min-height:130px;
  resize:vertical}
select:focus,input:focus,textarea:focus{outline:2px solid var(--focus);outline-offset:1px}
.radios{display:flex;gap:0;border:1px solid var(--border-control);border-radius:var(--r);
  overflow:hidden}
.radios button{flex:1;padding:8px 10px;font-size:var(--fs-md);color:var(--ink-2);
  border-left:1px solid var(--border)}
.radios button:first-child{border-left:0}
.radios button[aria-pressed="true"]{background:var(--seal-soft);color:var(--seal);
  font-weight:600}
/* Aday süzgeci — arama + rol + kontenjan. Tek satır, kartın içinde. */
.candbar{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-top:12px}
.candbar input[type=search]{flex:1 1 240px;min-width:200px}
.candbar .radios{flex:0 0 auto}
.candbar .radios button{flex:0 0 auto;padding:6px 12px}
.tickbox{display:flex;align-items:center;gap:6px;font-size:var(--fs-md);color:var(--ink-2);
  cursor:pointer;white-space:nowrap;min-height:24px}
/* ★ Faz 46 — onay kutusu 13×13px'ti (tarayıcı varsayılanı). Etiketin
   tamamı zaten tıklanabilir ama kutunun KENDİSİ de tabanın üstünde
   olmalı: dokunmatikte insanlar kutuya basıyor. */
.tickbox input[type="checkbox"]{width:18px;height:18px;margin:4px;
  accent-color:var(--seal);flex:0 0 auto}
.candcount{margin-left:auto;font-size:var(--fs-sm);color:var(--ink-3);
  font-variant-numeric:tabular-nums}
/* Klavye ipucu — dar ekranda gizli (orada klavye yok). */
.kisayol{font-size:var(--fs-xs);color:var(--ink-3);white-space:nowrap}
@media (max-width:700px){.kisayol{display:none}}
/* ★ Satıra tıklayınca ekleme penceresi açılıyor ama tıklanabilir olduğu belli
   değildi (01.09.2026) — imleç + hafif vurgu ekledik. Klavye odağı (.odak)
   daha güçlü (seal-soft + çerçeve) kalıyor ki ikisi ayrışsın. */
#cands tbody tr[data-course]{cursor:pointer}
#cands tbody tr[data-course]:hover{background:var(--surface-2)}
/* Klavye odağı — fare seçimi gibi görünmeli ki nerede olduğun belli olsun. */
#cands tbody tr.odak{outline:2px solid var(--focus);outline-offset:-2px;
  background:var(--seal-soft)}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px}
/* Gelişmiş alan — ilk kurulumda kapalı. Nadir kullanılan bir metin kutusunu
   zorunlu alanların yanına koymak, kurulumu üç kat karmaşık gösteriyordu. */
.adv{margin-top:14px;border-top:1px solid var(--border);padding-top:8px}
.adv>summary{cursor:pointer;font-size:var(--fs-sm);color:var(--ink-3);
  letter-spacing:var(--ls-caps);text-transform:uppercase}
.adv>summary:hover{color:var(--ink)}
.dlgactions{display:flex;gap:8px;justify-content:flex-end;align-items:center;
  margin-top:20px;padding-top:14px;border-top:1px solid var(--border)}
.dlgactions .msg{margin-right:auto;font-size:var(--fs-md);color:var(--ink-2)}
.dlgactions .msg.bad{color:var(--danger)}
.terms{display:flex;flex-wrap:wrap;gap:6px}
.terms button{width:42px;padding:8px 0;text-align:center;font-size:var(--fs-md);
  border:1px solid var(--border-control);border-radius:var(--r);color:var(--ink-2)}
.terms button[aria-pressed="true"]{background:var(--seal);color:var(--ground);
  border-color:var(--seal);font-weight:600}

/* plandan tikleme */
.ckterm{margin-bottom:10px}
.cktermhead{font-size:var(--fs-xs);font-weight:600;letter-spacing:var(--ls-label);
  text-transform:uppercase;color:var(--seal);padding:8px 0 4px;
  border-bottom:1px solid var(--border);margin-bottom:4px}
.ckrow{display:flex;align-items:center;gap:10px;padding:4px 2px;font-size:var(--fs-md);
  border-radius:var(--r);cursor:pointer}
.ckrow:hover{background:var(--surface-2)}
.ckrow input{width:15px;height:15px;accent-color:var(--seal);cursor:pointer}
.ckcode{min-width:74px;font-weight:600}
.ckname{flex:1;color:var(--ink-3);font-size:var(--fs-sm);overflow:hidden;
  text-overflow:ellipsis;white-space:nowrap}
.ckcr{color:var(--ink-3);font-size:var(--fs-sm);min-width:24px;text-align:right}
.ckrow select{width:auto;min-width:78px;padding:2px 6px;font-size:var(--fs-md)}
.ckrow select:disabled{opacity:.35}

/* transkript tablosu */
.trtable{width:100%;border-collapse:collapse;font-size:var(--fs-md)}
.trtable th{text-align:left;font-size:var(--fs-xs);letter-spacing:var(--ls-label);text-transform:uppercase;
  color:var(--seal);font-weight:600;padding:0 8px 6px 0;
  border-bottom:1px solid var(--border-strong)}
.trtable td{padding:6px 8px 6px 0;border-top:1px solid var(--border);vertical-align:middle}
.trtable select{width:auto;min-width:74px;padding:4px 6px;font-size:var(--fs-md)}
/* ★ Faz 48 — TABAN `.rm`in KENDİSİNDE. Faz 46'da yalnız `.trtable .rm`
   büyütülmüştü; taramada "Sayılan derslerim" bölümündeki `kaldır` düğmesi
   46×22px olarak kalmış çıktı. Aynı sınıfın üç kullanım yeri var; kural
   sınıfa yazılınca üçü de tabanın üstünde. */
.rm{min-height:24px;display:inline-flex;align-items:center}
.trtable .rm{color:var(--danger);font-size:var(--fs-sm);padding:2px 8px;
  border:1px solid var(--border);border-radius:var(--r);
  /* Faz 46: 46×22px'ti — WCAG 2.2 AA tabanı 24×24. */
  min-height:24px;display:inline-flex;align-items:center}
.scroll{max-height:290px;overflow-y:auto;margin-top:10px}
.hits{border:1px solid var(--border);border-radius:var(--r);margin-top:6px;
  max-height:190px;overflow-y:auto}
.hit{display:flex;justify-content:space-between;gap:10px;width:100%;text-align:left;
  padding:6px 10px;font-size:var(--fs-md);border-bottom:1px solid var(--border)}
.hit:last-child{border-bottom:0}
.hit:hover{background:var(--surface-2)}
.hit .meta{color:var(--ink-3);font-size:var(--fs-sm)}

/* Kredi eşiği kutusu */
.gauge{display:flex;flex-wrap:wrap;gap:20px;align-items:center}
.gaugebar{flex:1;min-width:190px}
.gaugebar .track{height:9px;background:var(--surface-2);border:1px solid var(--border);
  border-radius:var(--r);overflow:hidden}
.gaugebar .track i{display:block;height:100%;background:var(--seal)}
/* ★ Faz 56 — DURUM rengi `--ok`: sağlanıyor (✓), tamam, kaydedildi, programda.
   v1'de bunlar doğrudan `--anadal` yazıyordu — rol (hangi program) ile durum
   (sağlandı mı) aynı adı taşıyordu. Bugün aynı ton; ayrışırsa tek satır. */
.gaugebar .track i.ok{background:var(--ok)}
.gaugelabel{font-size:var(--fs-md);color:var(--ink-2);margin-top:6px}
.summary{display:flex;flex-wrap:wrap;gap:14px;align-items:center;font-size:var(--fs-md);
  color:var(--ink-2);margin-top:2px}
.summary .over{color:var(--danger);font-weight:600}
/* ★★ FAZ 56 — haftalık programın özeti (bağlam sütununun tepesi). */
.prgyan #schedSummary{flex-direction:column;align-items:stretch;gap:6px;margin:0}
.yukust{display:flex;align-items:baseline;gap:6px;flex-wrap:wrap;color:var(--ink-2)}
.yuksayi{font-size:var(--fs-3xl);font-weight:600;color:var(--ink);
  letter-spacing:var(--ls-tight);line-height:var(--lh-none)}
.yuk{height:6px;background:var(--surface-2);border:1px solid var(--border);overflow:hidden}
.yuk>i{display:block;height:100%;background:var(--seal)}
.yuk.asti>i{background:var(--danger)}
.ozetsatir{color:var(--ink-2)}
.ozetdolu{font-size:var(--fs-sm);line-height:var(--lh-normal);color:var(--ink)}
.ozetdolu .yerdurum{margin:0 4px 0 0}
.ozetsekil{font-size:var(--fs-sm);color:var(--ink-2);line-height:var(--lh-normal);margin-top:2px}
.ozetdolusatir+.ozetdolusatir{margin-top:6px}
.ozetdolusatir .ozetnot{display:block}
.ozetdolusatir button{margin-left:4px}
.ozetnot{color:var(--ink-3)}
.ozettekrar{padding-top:6px;border-top:1px solid var(--border)}
.hafiflet{margin-top:6px;padding-top:6px;border-top:1px solid var(--border)}   /* Faz 103 */
.hafiflet .ozetbaslik{font-weight:600;margin-bottom:4px}
.why.uyansube{color:var(--ok)}
.tickliste{display:flex;flex-direction:column;gap:6px}
.tickliste .tickbox{white-space:normal;align-items:flex-start;flex-wrap:wrap}
.tickliste .tickbox .hint{flex-basis:100%;margin-left:32px}
.yhkalma{margin-top:14px}
.yhad.gecmis{color:var(--ink-3)}
.yhgecmisnot{margin:14px 0 6px}
.gecmisnot{margin-top:12px;font-size:var(--fs-sm);color:var(--ink-2);line-height:var(--lh-normal)}
.yhsaat{font-size:var(--fs-xs);color:var(--ink-3);margin:2px 0 4px;line-height:var(--lh-snug)}
.yhsaat .ok{color:var(--ok)}
/* ★★ Faz 85 — tahmini zorluk ölçeği: beş yükselen çubuk + etiket. Renk
   yalnız destek; kademe etikette ve ekran okuyucu metninde de yazıyor. */
.zorluk{display:inline-flex;align-items:center;gap:6px;font-size:var(--fs-xs);
  font-weight:600;letter-spacing:var(--ls-wide);color:var(--ink-2);white-space:nowrap;
  vertical-align:middle}
.zorluk .zcubuk{display:inline-flex;align-items:flex-end;gap:2px}
.zorluk .zcubuk i{display:block;width:4px;background:var(--border-strong)}
.zorluk .zcubuk i:nth-child(1){height:4px}
.zorluk .zcubuk i:nth-child(2){height:6px}
.zorluk .zcubuk i:nth-child(3){height:8px}
.zorluk .zcubuk i:nth-child(4){height:10px}
.zorluk .zcubuk i:nth-child(5){height:12px}
.zorluk .zcubuk i.on{background:currentColor}
.zorluk.z1,.zorluk.z2{color:var(--ok)}
.zorluk.z3{color:var(--ink-2)}
.zorluk.z4{color:var(--warn)}
.zorluk.z5{color:var(--danger)}
.zorluk .azveri{color:var(--ink-3);font-weight:400}
td .zorluk,.yhdonem li>.zorluk{margin-left:6px}
.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);
  white-space:nowrap}
.zorlukkutu{border:1px solid var(--border);border-radius:var(--r);padding:10px 12px;
  margin:12px 0;background:var(--surface-2)}
.zorlukkutu .zorlukust{display:flex;flex-wrap:wrap;align-items:center;gap:10px;
  font-size:var(--fs-sm);color:var(--ink-2)}
.zorlukkutu .zorlukust .zorluk{font-size:var(--fs-sm)}
.zorlukkutu .why{margin-top:6px}
.zorlukkutu .zgenel{font-size:var(--fs-sm);color:var(--ink-2)}
.zorlukkutu .zgenel b{font-size:var(--fs-md);color:var(--ink)}
.zorluk .zskor{font-weight:600}
.zaltlar{display:grid;gap:8px;margin-top:10px}
.zakts{margin-top:8px;font-size:var(--fs-sm);color:var(--ink-2)}   /* Faz 102 */
.zalt{display:grid;grid-template-columns:minmax(0,190px) minmax(0,1fr) auto;
  align-items:center;gap:4px 10px;font-size:var(--fs-sm);color:var(--ink-2)}
.zalt .zagirlik{color:var(--ink-3);font-size:var(--fs-xs)}
.zalt .zbar{height:8px;background:var(--border);border-radius:var(--r);overflow:hidden}
.zalt .zbar i{display:block;height:100%;background:currentColor}
.zalt.z1 .zbar,.zalt.z2 .zbar{color:var(--ok)}
.zalt.z3 .zbar{color:var(--ink-3)}
.zalt.z4 .zbar{color:var(--warn)}
.zalt.z5 .zbar{color:var(--danger)}
.zalt .zdeger b{color:var(--ink)}
.zalt .zdayanak{grid-column:1 / -1;font-size:var(--fs-xs);color:var(--ink-3)}
@media(max-width:700px){.zalt{grid-template-columns:minmax(0,1fr) auto}
  .zalt .zbar{grid-column:1 / -1;grid-row:2}}
.zorlukkutu .zorluknot{margin-top:6px;font-size:var(--fs-xs);color:var(--ink-3);
  line-height:var(--lh-snug)}
.ozetzorluk{font-size:var(--fs-sm);color:var(--ink-2);margin-top:6px;line-height:var(--lh-snug)}
.ozetzorluk .yogun{color:var(--warn)}
.yhzorluk{font-size:var(--fs-xs);color:var(--ink-3);margin:2px 0 4px}
.yhzorluk b{color:var(--warn)}
.kalmariskli{color:var(--warn)}
.kalmariskli b{color:var(--ink)}
.altbaslik{display:flex;align-items:baseline;gap:8px;margin-top:16px;padding-top:12px;
  border-top:1px solid var(--border)}
.altsatir{padding:8px 0;border-bottom:1px solid var(--border);font-size:var(--fs-sm)}
.altozet{color:var(--ink-2);margin-top:2px}
.altdugmeler{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}
.nskalma:empty{display:none}
.ozettekrar .ozetbaslik{font-weight:600;margin-bottom:4px}
.ozetlejant{display:flex;flex-wrap:wrap;gap:4px 12px;font-size:var(--fs-sm);
  padding-top:6px;border-top:1px solid var(--border)}
.ozetpuan{font-size:var(--fs-sm);color:var(--ink-3)}
.ozetpuan b{color:var(--ink-2)}
.dot{display:inline-flex;align-items:center;gap:6px}
.dot i{width:9px;height:9px;border-radius:var(--r);display:block}
.toolbar{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-top:10px}
.toolbar .hint{font-size:var(--fs-sm);color:var(--ink-3)}

.gridwrap{overflow-x:auto}
/* Dar ekran düzeni (yapılacaklar 4.1). Izgara 660px'in altına inemiyor;
   telefonda yerini gün gün dikey liste alıyor. Aynı veri, başka biçim.
   ★ Listenin bilinen zayıflığı çakışmayı göstermemesi — o yüzden çakışma
   burada AYRICA hesaplanıp işaretleniyor. */
.daylist{display:none;grid-template-columns:1fr;gap:14px}
.daylist section{display:flex;flex-direction:column;gap:6px}
.daylist h3{font-size:var(--fs-xs);letter-spacing:var(--ls-eyebrow);color:var(--seal);
  padding-bottom:6px;border-bottom:2px solid var(--border-strong)}
.daylist .row{display:flex;justify-content:space-between;gap:10px;align-items:baseline;
  width:100%;text-align:left;padding:12px 12px;font-size:var(--fs-lg);
  color:var(--accent-ink);--tonhedef:var(--soft);--tonoran:0%;
  border-left:5px solid color-mix(in oklab, var(--accent),
    var(--tonhedef) calc(var(--tonoran) / 2));
  background:color-mix(in oklab, var(--soft), var(--tonhedef) var(--tonoran))}
.daylist .row[data-role="ANADAL"]{--accent:var(--anadal);--soft:var(--anadal-soft);--accent-ink:var(--anadal-ink)}
.daylist .row[data-role="CAP"]{--accent:var(--cap);--soft:var(--cap-soft);--accent-ink:var(--cap-ink)}
.daylist .row[data-role="YANDAL"]{--accent:var(--yandal);--soft:var(--yandal-soft);--accent-ink:var(--yandal-ink)}
.daylist .row small{color:inherit;font-size:var(--fs-sm);display:block}
.daylist .row.clash{border-left-color:var(--danger);
  box-shadow:inset 0 0 0 1px var(--danger)}
.daylist .none{color:var(--ink-3);font-size:var(--fs-md);padding:6px 0}
/* Faz 96 — kullanım kılavuzu. */
.basdugme{display:flex;gap:8px;align-items:flex-start}
/* Faz 97 — eşiyle karşılanmış plan dersi (Plandan işaretle). */
.ckviayazi{color:var(--ok);font-size:var(--fs-sm)}
.ckrow.ckvia{color:var(--ink-2)}
.yardimnot{display:block;margin-top:4px;color:var(--ink-2);font-size:var(--fs-sm)}
.yardim h3{margin:24px 0 8px;font-size:var(--fs-lg)}
.yardim h4{margin:0 0 8px;font-size:var(--fs-md)}
.yardim ul,.yardim ol{margin:0 0 12px;padding-left:20px;line-height:var(--lh-normal)}
.yardim li{margin-bottom:4px}
.yardimliste{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px}
.yardimkart{border:1px solid var(--border);border-radius:var(--r);padding:12px 16px;
  background:var(--surface)}
.yardimkart .ghost.mini,.yardimadim .ghost.mini{margin:4px 4px 0 0}
.yardimisaret{display:grid;grid-template-columns:max-content 1fr;gap:8px 16px;margin:0 0 12px}
.yardimisaret dt{font-family:var(--font-mono);font-size:var(--fs-sm)}
.yardimisaret dd{margin:0;color:var(--ink-2)}
/* Faz 95 — sıradaki ders ve bugünün etiketi. */
.daylist .siradaki{border:1px solid var(--border-strong);border-radius:var(--r);
  padding:8px 12px;font-size:var(--fs-md);background:var(--surface-2)}
.daylist .bugun{color:var(--ink-2);text-transform:none;font-weight:600}
.daylist .warn{color:var(--danger);font-weight:600;font-size:var(--fs-xs);
  letter-spacing:var(--ls-caps);text-transform:uppercase;
  font-family:var(--font-display)}
/* ★★ FAZ 56 — meşgul saat telefon listesinde de (ızgaradakiyle aynı tarama:
   bir DERS değil, veri renklerini kullanmıyor). */
.daylist .row.mesgul{color:var(--ink-2);border-left-color:var(--border-strong);
  background:repeating-linear-gradient(135deg,var(--surface-2) 0 5px,
    transparent 5px 10px)}
.daylist .row.mesgul.clash{border-left-color:var(--danger)}
/* ★★ FAZ 56 — seçili şubenin yeri (dolu / son N). Rozet KENDİ zemininde
   (`surface`): blok rolün tonlu zemininde duruyor ve ton merdiveni yalnız
   `-ink` yazısını ölçüyor — danger/warn o zeminlerde ölçülmedi. Zemin
   verince çift ölçülen bir çift oluyor (`tools/kontrast_olcumu.py`). */
.yerdurum{display:inline-block;margin-left:4px;padding:2px 4px;
  font-family:var(--font-display);font-size:var(--fs-xs);font-weight:700;
  letter-spacing:var(--ls-caps);text-transform:uppercase;line-height:var(--lh-none);
  white-space:nowrap;vertical-align:1px;border:1px solid currentColor;
  background:var(--surface)}
.yerdurum.dolu{color:var(--danger)}
.yerdurum.az{color:var(--warn)}
@media (max-width:700px){
  .gridwrap{display:none}
  /* ⚠️ Izgara gizliyken saat kırpma düğmesi de gizlenmeli: telefonda
     ızgara yok, gün gün liste var — "tüm günü göster" hiçbir şey yapmaz.
     (Faz 39'da eklerken atlandı, mobil turda görüldü.) */
  .gridaralik{display:none}
  .daylist{display:grid}
  .wrap{padding:20px 14px 56px;gap:24px}
  h1{font-size:var(--fs-2xl)}
  .pad{padding:16px 14px}
  .panels{gap:12px}
  /* Dokunma hedefleri: 44px kuralı.
     ⚠️ Kural "44" diyordu ama değer 40'tı (Faz 39). Faz 50 telefon turunda
     ölçüldü: her görünümde 7–8 denetim 44'ün altında (`Tema` 34, `tazele`
     ve bütün `.ghost`lar 40). WCAG 2.2 tabanı 24 — o sağlanıyordu; bu
     reponun KENDİ telefon kuralı 44 ve tutulmuyordu. */
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
  .tier li span.dispre{min-height:32px;padding:0 10px;
    display:inline-flex;align-items:center}
  .tiers{gap:8px}
  /* Faz 80 — tek sütunda çizgiler dinlenmede gizli; odakta yalnız zincir. */
  .tierlinks path{display:none}
  .tierstage.focus .tierlinks path.line.on{display:inline}
  .tier li{width:100%}
  /* Aday tablosu 6 sütunla telefona sığmıyordu; kutusunun içinde yana
     kayıyordu ama asıl iş burada yapılıyor — kaydırarak kullanılmamalı.
     Plan ve AKTS sütunları düşüyor: rol zaten ders hücresindeki etikette,
     AKTS karar için kritik değil. Satıra dokununca hepsi diyalogda. */
  #cands th:nth-child(3),#cands td:nth-child(3),
  #cands th:nth-child(5),#cands td:nth-child(5){display:none}
  table.list{font-size:var(--fs-md)}
  table.list td{padding:12px 8px 12px 0}
  /* ★★ FAZ 50 — ADAY TABLOSU TELEFONDA KART (kullanıcı: "telefonda
     kullanılması biraz zor").
     Ölçüldü (390px): dört sütun kalsa bile ders sütununa ~160px düşüyordu;
     açıklama 25 karakterde sarıyor, TEK ders satırı **330px** oluyordu ve
     sağdaki kontenjan sütunu kutunun DIŞINA taşıp rakamı kesiyordu
     ("180" → "18"). Yani telefonda liste hem çok uzun hem eksik okunuyordu.

     Tablo tek DOM olarak kalıyor — masaüstünde hâlâ tablo, telefonda kart.
     İki ayrı çizim yazsaydık ikisi ayrışırdı (bu repoda ölçülmüş bir
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
  #cands td.score{grid-column:2;grid-row:1;text-align:right;font-size:var(--fs-base);
    font-weight:700;color:var(--ink)}
  #cands td.score::after{content:" puan";font-size:var(--fs-xs);font-weight:600;
    letter-spacing:var(--ls-caps);color:var(--ink-3)}
  #cands tr[data-course]>td:nth-child(2){grid-column:1;grid-row:1}
  #cands tr[data-course]>td:nth-child(4){grid-column:1;grid-row:2}
  #cands tr[data-course]>td:nth-child(4)::after{content:" " attr(data-e);
    color:var(--ink-3);font-size:var(--fs-sm)}
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
table.grid th{font-size:var(--fs-xs);font-weight:700;letter-spacing:var(--ls-eyebrow);text-transform:uppercase;
  color:var(--seal);padding:0 0 8px;text-align:left;border-bottom:3px solid var(--seal);
  font-family:var(--font-display)}
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
table.grid td.hour{border:0!important;color:var(--ink-3);font-size:var(--fs-sm);padding-top:2px}
/* ⚠️ Boş hücrenin TIKLANABİLİR olduğu, üstüne gelmeden de görünmeli:
   ölçümde hücrenin hiçbir görsel işareti yoktu, yalnız hover vardı.
   İşaret sönük ve hücrenin köşesinde — ızgaranın okunmasını bozmuyor. */
table.grid td.free{cursor:pointer;position:relative}
table.grid td.free::after{content:"+";position:absolute;left:4px;top:1px;
  font-size:var(--fs-sm);line-height:var(--lh-none);color:var(--ink-3);opacity:.45}
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
.blk{border-radius:var(--r);padding:4px 8px;font-size:var(--fs-sm);line-height:var(--lh-snug);height:100%;
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
  font-size:var(--fs-xs);opacity:.75}
.blk{position:relative}
/* Ders adı — dar hücrede kesiliyor; tam adı `title` taşıyor. */
/* ★ FAZ 40 — aynı dersin bütün saatleri. İşaret RENK DEĞİL: çerçeve.
   Tonla yarışmıyor, renk körlüğünde de okunuyor, ve `.clash`ın kırmızı
   çerçevesinin üstüne binmiyor (o `border-left` + inset gölge kullanıyor). */
.blk.esder,.daylist .row.esder{outline:2px solid var(--ink);outline-offset:-2px}
.blk.esder{z-index:var(--z-lift)}
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
.note.kilit .kilitsatir button{font-size:var(--fs-sm)}
/* Faz 53 — ders penceresinde saat aralığına kilit. Basılı olan KALIN ÇERÇEVE
   ile (renk değil; zorlanmış renk kipinde de görünsün — Faz 51 dersi). */
.kilitgrup{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-top:10px}
.kilitgrupad{font-size:var(--fs-md);color:var(--ink-2)}
.kilitaralik[aria-pressed="true"]{border:2px solid var(--ink);color:var(--ink);
  font-weight:600}
.kilitaralik:disabled{opacity:.55;cursor:not-allowed}
.kilitsay{color:var(--ink-3);font-weight:400}
/* ★★ FAZ 56 — BLOK İÇİ YAZI YALNIZ `-ink`, TAM GÜÇTE. v1 tasarım sistemi bu
   kuralı yazmıştı ("ad için opaklık, saat için ink-2 verme"), kod almamıştı.
   Ton merdiveniyle ölçüldü (en kötü basamak): ad `-ink` %85 opaklıkta
   **3.80:1**, saat · yer · CRN satırı `ink-2` ile **3.09:1** — taban 4.5.
   CRN kayıt günü elle yazılan sayı. Tam `-ink` 4.67:1. Hiyerarşi artık
   boy ve ağırlıkta; renkte değil. */
.blkad{display:block;font-size:var(--fs-xs);line-height:var(--lh-snug);
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap;margin-top:1px}
.daylist .row.online{border-left-style:dashed}
/* Ders konulamayacak saat — okul dışı iş. Taralı, çünkü bir DERS değil:
   veri renklerini (yeşil/kehribar) kullansaydı programın parçası sanılırdı. */
.blk.mesgul{--accent:var(--ink-3);border-left-color:var(--border-strong);
  background:repeating-linear-gradient(135deg,var(--surface-2) 0 5px,
    transparent 5px 10px);color:var(--ink-2);cursor:pointer}
.blk.mesgul b{font-weight:600;letter-spacing:var(--ls-wide)}
table.grid td.busycell{background:repeating-linear-gradient(135deg,
  var(--surface-2) 0 5px,transparent 5px 10px)}
.blk b{display:block;font-weight:600}
.blk small{color:inherit;font-size:var(--fs-xs)}
/* Faz 93 — bina + derslik tek parça kalıyor ("INB D01" ikiye bölünmesin)
   ve göz onu ilk arıyor: ders saatine giderken bakılan şey bu. */
.yer{white-space:nowrap}
.blk .yer,.daylist .row .yer{font-weight:600}
.empty{color:var(--ink-3);font-size:var(--fs-sm);padding:24px 0;text-align:center}

table.list{width:100%;border-collapse:collapse;font-size:var(--fs-lg)}
table.list th{text-align:left;font-size:var(--fs-xs);letter-spacing:var(--ls-eyebrow);text-transform:uppercase;
  color:var(--seal);font-weight:700;padding:0 10px 8px 0;
  border-bottom:3px solid var(--seal);font-family:var(--font-display)}
table.list td{padding:10px 10px 10px 0;border-top:1px solid var(--border);vertical-align:top}
table.list tr:hover td{background:var(--surface-2)}
.tag{font-size:var(--fs-xs);font-weight:700;padding:2px 8px;border-radius:var(--r);
  letter-spacing:var(--ls-caps);text-transform:uppercase;
  font-family:var(--font-display)}
.tag.ANADAL{background:var(--anadal-soft);color:var(--anadal-ink)}
.tag.CAP{background:var(--cap-soft);color:var(--cap-ink)}
.tag.YANDAL{background:var(--yandal-soft);color:var(--yandal-ink)}
/* CRN'den yüklenen, planlarında olmayan ders — nötr renk, çünkü
   hangi programa saydığını biz bilmiyoruz. */
.tag.PLAN_DISI{background:var(--surface-2);color:var(--ink-3)}
.why{color:var(--ink-3);font-size:var(--fs-sm);margin-top:4px}
.score{font-weight:600}

.chipline{display:flex;align-items:center;gap:10px;margin:16px 0 8px}
/* ★ `inline-block` + `nowrap` (UX 27.08.2026): rozet dar mobil ekranda
   ORTASINDAN bölünüyordu ("ÖNŞART / BİLGİSİ YOK") ve kenarlık kırık bir
   kutu çiziyordu. Rozet tek parça; sığmazsa bütün olarak alt satıra iner.
   `margin-bottom` sarınca üst üste binmesin diye. */
.chip{display:inline-block;white-space:nowrap;font-size:var(--fs-xs);font-weight:600;
  padding:4px 10px;border-radius:var(--r);margin-bottom:4px;
  letter-spacing:var(--ls-wide);text-transform:uppercase;border:1px solid currentColor}
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
.denkhedef{font-size:var(--fs-md);color:var(--ink-2);margin-bottom:6px;
  display:flex;flex-wrap:wrap;gap:6px;align-items:baseline}
.denkhedef .denkad{color:var(--ink-3);font-size:var(--fs-sm)}
.denkok{color:var(--ink-3);font-size:var(--fs-sm)}
.denkkaynak{border:1px solid var(--border);background:var(--surface);
  padding:8px 10px;margin-top:6px;cursor:pointer}
.denkkaynak:hover{background:var(--surface-2)}
.denkkaynak.bilgi{cursor:default}
.denkkaynak.bilgi:hover{background:var(--surface)}
.denkkaynak .denkad{color:var(--ink-3);font-size:var(--fs-sm);margin-left:6px}
.denkkaynak .denkmeta{color:var(--ink-3);font-size:var(--fs-sm);margin-top:2px}
.denknot{font-size:var(--fs-sm);color:var(--ink-3);margin-top:6px}
.chip.supply{color:var(--danger)}
.chip.prereq{color:var(--warn)}
.chip.credit{color:var(--seal)}
.chip.unknown{color:var(--ink-3)}
.chip.edited{color:var(--cap)}
.blocklist{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:6px}
.blockitem{font-size:var(--fs-md);color:var(--ink-2);padding:8px 10px;border-radius:var(--r);
  background:var(--surface-2);border:1px solid var(--border)}
.blockitem b{color:var(--ink);font-weight:600}
/* Kontenjan nöbeti rozeti (Faz 39). Eskiden 6 bildirimlik SATIR İÇİ stil
   olarak engelli HER dersin yanında tekrar ediyordu — 11 kez. Sınıfa
   taşındı; durumu artık `aria-pressed` söylüyor (ekran okuyucu "izle"
   düğmesinin basılı olduğunu duymuyordu). */
.watchmini{margin-left:6px;font-size:var(--fs-xs);letter-spacing:var(--ls-wide);
  text-transform:uppercase;border:1px solid currentColor;padding:1px 8px;
  color:var(--ink-3);
  /* Faz 46: 38×21px'ti — WCAG 2.2 AA tabanı 24×24. */
  min-height:24px;min-width:24px;display:inline-flex;align-items:center;
  justify-content:center}
.watchmini[aria-pressed="true"]{color:var(--cap)}
.note{font-size:var(--fs-md);color:var(--ink-2);background:var(--surface-2);
  border-radius:var(--r);padding:12px 14px;border-left:3px solid var(--warn)}

.opt{display:flex;justify-content:space-between;gap:10px;align-items:baseline;width:100%;
  text-align:left;padding:8px 10px;border-radius:var(--r);border:1px solid var(--border);
  background:var(--surface);font-size:var(--fs-md)}
.opt:hover{background:var(--surface-2)}
.opt .meta{color:var(--ink-3);font-size:var(--fs-sm)}
/* Öğretim üyesi — şube seçerken bakılan iki şeyden biri (öbürü saat). */
.hoca{color:var(--ink-2);font-size:var(--fs-xs);letter-spacing:var(--ls-wide)}
/* Kontenjan doluluk çubuğu. Sayı okumak yerine bakılabilsin. */
.cap{display:inline-flex;align-items:center;gap:8px;white-space:nowrap;font-size:var(--fs-sm)}
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
.opens{color:var(--ink-3);font-size:var(--fs-sm)}
/* Plan dışı kredi — yüke sayılır, şart doldurmaz. İkisini birden söylüyor. */
.planout{color:var(--warn)}
/* Verinin yaşı — kontenjan sayıları buna ait. Bayatladıysa göze girsin. */
.veriyasi{font-size:var(--fs-sm);color:var(--ink-3);margin-top:2px}
.veriyasi.stale{color:var(--warn);font-weight:600}
.veriyasi .sitenot{margin-left:.6em;font-weight:400}
/* Bozuk ayar dosyası — sayfa açılıyor ama sessiz kalmıyor. */
.note.ayarhata{border-left:3px solid var(--danger);padding-left:10px;
  margin:14px 0}
/* Faz 53: dosya okunuyor ama bir satır yanlış tabloda — hata değil, uyarı. */
.note.ayarhata.yumusak{border-left-color:var(--warn)}
/* Yapıştırma önizlemesi — üç sayı ayrı okunsun. */
.ozetler{display:flex;flex-wrap:wrap;gap:8px}
.ozet{font-size:var(--fs-sm);padding:4px 10px;border:1px solid var(--border);
  color:var(--ink-2)}
.ozet.ok{border-color:var(--ok);color:var(--ok)}
.ozet.uyari{border-color:var(--warn);color:var(--warn)}
/* Satır içi uyarı yazısı (katalogda olmayan ders, planı olmayan program). */
.meta .uyari,td .uyari,.ckname .uyari,#roadmapSection .uyari{color:var(--warn)}
.ozet.kotu{border-color:var(--danger);color:var(--danger)}
/* Puan kırılımı — "neden bu puan". Eksi katkı da aynı görsel dilde. */
.puan{margin-top:10px;border-top:1px solid var(--border);padding-top:8px}
.puan>summary{cursor:pointer;font-size:var(--fs-md);color:var(--seal)}
.puanliste{display:flex;flex-direction:column;gap:4px;margin-top:8px}
.puansatir{display:grid;grid-template-columns:1fr 90px 46px;gap:8px;
  align-items:center;font-size:var(--fs-sm)}
.puansatir .ad{color:var(--ink-2)}
.puansatir .bar{height:7px;background:var(--surface-2);border:1px solid var(--border)}
.puansatir .bar>i{display:block;height:100%;background:var(--seal)}
.puansatir.eksi .bar>i{background:var(--warn)}
.puansatir .deger{text-align:right;color:var(--ink-2);font-variant-numeric:tabular-nums}
.puansatir.eksi .deger{color:var(--warn)}
.puantoplam{margin-top:8px;font-size:var(--fs-sm);color:var(--ink-3);line-height:var(--lh-body)}
/* Faz 38 — not dağılımı sütun grafiği (kütüphane yok).
   ★ Faz 38b: varsayılan 9 KOVA. 15 ince sütun dağılımın şeklini
   kaybettiriyordu ("+ lar yüzünden kötü gözüküyor"). Etiketler artık
   yatay — 9 kova sığıyor; "artıları ayır" 15'e çıkarınca dikey oluyor. */
.ndgrafik{display:grid;grid-template-columns:repeat(9,1fr);gap:6px;
  align-items:end;height:104px;margin:10px 0 8px}
.ndgrafik.genis{grid-template-columns:repeat(15,1fr);gap:4px}
/* ★★ FAZ 50 — SÜTUN ÜÇ SATIRLIK IZGARA (eskiden esnek kutuydu).
   Ölçüldü: esnek kutuda üç öğe (sayı 10px + çubuk %100 + etiket) kabı
   TAŞIYOR, tarayıcı da hepsini büzüyordu — büzülme miktarı çubuğun boyuna
   göre değiştiği için TABANLAR kayıyordu. Üstelik "%100" çubuk kabın
   tamamı kadar isteniyor, yani ölçek de yanlıştı.
   Izgarada: 1. satır sayı, 2. satır ÇUBUK ALANI (kalan yer), 3. satır
   etiket. Birinci ve üçüncü satır bütün sütunlarda aynı yükseklikte
   olduğu için taban ortak ve yüzdeler aynı alana göre. */
.ndsut{display:grid;grid-template-rows:auto minmax(0,1fr) auto;
  justify-items:center;height:100%;gap:4px;min-width:0}
.ndsut>i{align-self:end}
.ndsut>b{font-size:var(--fs-xs);font-weight:600;color:var(--ink-3);line-height:var(--lh-none);
  font-variant-numeric:tabular-nums}
.ndsut>i{display:block;width:100%;background:var(--seal);border-radius:var(--r)}
.ndsut>i.kotu{background:var(--warn)}
/* ★★ FAZ 50 — ETİKET SATIRI SABİT YÜKSEKLİKTE (kullanıcı 18.09.2026:
   *"+lar yüzünden barların tabanları aynı seviyede olmuyor"*).
   Ölçüldü ("artıları ayır", 15 sütun): tabanlar ÜÇ AYRI seviyede, 7px
   fark. Sebep: sütun alttan hizalı (`justify-content:flex-end`) ve DİKEY
   yazılan etiket karakter sayısıyla büyüyor — "BA+" 17px, "AA" 12px. Uzun
   etiket çubuğu yukarı itiyordu. Etiket kutusu sabitlenince taban ortak. */
.ndsut>span{font-size:var(--fs-xs);color:var(--ink-2);line-height:var(--lh-none);white-space:nowrap;
  height:12px;display:flex;align-items:flex-start;justify-content:center}
.ndgrafik.genis .ndsut>b{font-size:var(--fs-2xs)}
/* Dar ekranda 15 etiket yan yana sığmıyor (ölçüm: 390px'te sütun 17.7px,
   yatay "BA+" 17px — bitişik), o yüzden dikey. Kutu yine SABİT. */
.ndgrafik.genis .ndsut>span{font-size:var(--fs-2xs);writing-mode:vertical-rl;
  transform:rotate(180deg);height:20px;align-items:center}
/* ⚠️ Yer varsa dikey yazı YOK: ölçüldü, 560px'ten sonra sütun ≥26px ve
   yatay etiket 17px — sığıyor. Döndürülmüş 8.5px yazı okunmuyor. */
@media (min-width:560px){
  .ndgrafik.genis .ndsut>span{writing-mode:horizontal-tb;transform:none;
    height:12px;align-items:flex-start}
}
.ndozet{display:flex;flex-wrap:wrap;gap:10px;font-size:var(--fs-sm);color:var(--ink-2);
  align-items:center}
/* Dönem seçici — OBS'nin kendi sayfasında da var. */
.ndsekme{display:flex;flex-wrap:wrap;gap:4px;margin-top:8px}
.ndtab{font:inherit;font-size:var(--fs-sm);padding:4px 8px;cursor:pointer;
  background:var(--surface-2);border:1px solid var(--border);color:var(--ink-2)}
.ndtab>span{color:var(--ink-3);font-size:var(--fs-xs)}
.ndtab.sec{background:var(--seal-soft);border-color:var(--seal);color:var(--ink)}
.ndtab:active{transform:translateY(1px)}
@media (prefers-reduced-motion:reduce){.ndtab:active{transform:none}}
/* Yarıyıl uyuşmazlığı — sessiz kalınmayacak kadar önemli. */
.ndmevsim{margin-top:8px;padding:8px 10px;font-size:var(--fs-sm);line-height:var(--lh-normal);
  background:var(--warn-soft);color:var(--warn-ink);
  border-left:3px solid var(--warn)}
/* Tercihin programa etkisi. */
.tercihnot{font-size:var(--fs-sm)}
.tercihnot.ok{color:var(--ok)}
.tercihnot.uymaz{color:var(--warn)}
/* Yan yana karşılaştırma tablosu. */
table.cmp{border-collapse:collapse;width:100%;font-size:var(--fs-md)}
table.cmp th,table.cmp td{border:1px solid var(--border);padding:6px 10px;
  text-align:left;vertical-align:top}
table.cmp thead th{font-size:var(--fs-xs);letter-spacing:var(--ls-caps);text-transform:uppercase;
  color:var(--ink-3)}
table.cmp tbody th{color:var(--ink-2);font-weight:600;white-space:nowrap}
table.cmp .secili{background:var(--seal-soft)}
table.cmp .meta{font-size:var(--fs-xs);color:var(--ink-3)}
table.cmp .meta.eksi{color:var(--warn)}
table.cmp .meta.arti{color:var(--ok)}
/* Arz uyarısı — planındaki ders bu dönem alınamıyorsa, ÜSTTE. */
.note.arz{margin-top:10px;border-left:3px solid var(--warn);padding-left:10px}
.note.arz .meta{color:var(--ink-3);font-size:var(--fs-sm)}
/* Kayıt öncesi kontrol — üç durumlu (✓ / ✗ / — bakılamaz). */
.checks{display:flex;flex-direction:column;gap:6px;margin-top:6px}
.check{display:flex;gap:8px;align-items:baseline;font-size:var(--fs-md)}
.check .mark{width:14px;text-align:center;font-weight:700}
.check.ok .mark{color:var(--ok)}
.check.bad .mark{color:var(--danger)}
.check.unknown .mark{color:var(--ink-3)}
.check .meta{color:var(--ink-3);font-size:var(--fs-sm)}
/* Yedek plan satırı — çakışan / uyan / dolu ayrı okunsun. */
.yedek{display:flex;gap:8px;flex-wrap:wrap;align-items:baseline;font-size:var(--fs-md);
  padding:4px 0;border-bottom:1px solid var(--border)}
.yedek:last-child{border-bottom:0}
.yedek.uyar>b{color:var(--ok)}
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
.tierstage{position:relative;display:flex;flex-direction:column;gap:40px}
/* ★ Çizgiler kutuların ÜSTÜNDE (z-index:2 > .tier'in 1'i). Altında kalınca
   birden çok kademe atlayan ya da sarmış satıra giden bağlar kutuların
   arkasında kayboluyordu — "bağlar tam bağlanmıyor" (kullanıcı 27.08.2026).
   Kılıf (zemin renginde) kutunun üstünden geçerken de çizgiyi okunur tutuyor,
   pointer-events:none olduğu için tıklama yine kutulara geçiyor. */
.tierlinks{position:absolute;left:0;top:0;pointer-events:none;overflow:visible;z-index:var(--z-links)}
/* ★ Çizgi tasarımı (27.08.2026). Eski hâlde çizgiler dururken NEREDEYSE
   GÖRÜNMEZDİ (opacity .55, kenarlık rengi) ve yapı ancak tıklayınca ortaya
   çıkıyordu. İki iyileştirme:
   1. KILIF: her çizginin altına zemin renginde kalın bir kat — çizgiler
      kesişince ve kutu kenarından geçince ayrışıyor (kartografide "casing").
   2. Dinlenmede de OKUNUR: bağ rengi (seal) ve daha belirgin. */
.tierlinks path.casing{fill:none;stroke:var(--ground);stroke-width:5;
  stroke-linecap:round}
.tierlinks path.line{fill:none;stroke:var(--seal);stroke-width:1.6;opacity:.55;
  stroke-linecap:round;transition:opacity var(--dur-fast),stroke var(--dur-fast),stroke-width var(--dur-fast)}
.tierstage.focus .tierlinks path.line{opacity:.08}
.tierstage.focus .tierlinks path.line.on{stroke:var(--cap);stroke-width:2.6;opacity:1}
.tier{position:relative;z-index:var(--z-lift)}
.tier > h3{font-size:var(--fs-xs);color:var(--seal);font-weight:700;margin-bottom:10px;
  letter-spacing:var(--ls-eyebrow);text-transform:uppercase;
  font-family:var(--font-display);
  padding-bottom:6px;border-bottom:2px solid var(--border-strong)}
.tier ul{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:8px}
.tier li{font-size:var(--fs-sm);padding:8px 10px;border-radius:var(--r);background:var(--surface-2);
  border:1px solid var(--border);border-left:3px solid var(--border-strong);
  display:flex;flex-direction:column;gap:4px;cursor:pointer;width:196px;
  transition:opacity var(--dur-fast),box-shadow var(--dur-fast)}
.tier li:hover{box-shadow:var(--shadow-lift)}
.tier li .top{display:flex;justify-content:space-between;gap:6px;align-items:baseline}
/* Plan İÇİ önşart — çizginin temsil ettiği bağ. "önce:" ile okunuyor. */
.tier li .dep{font-size:var(--fs-xs);line-height:var(--lh-snug);color:var(--ink-2)}
.tier li .dep b{color:var(--ink);font-weight:600}
/* Plan DIŞI önşart artık KOMPAKT rozet — eskiden 2-3 satır metin her kutuyu
   şişiriyordu (mobilde iyice). Tam liste ipucunda. */
.tier li .dispre{font-size:var(--fs-xs);color:var(--ink-3);border:1px solid var(--border);
  padding:0 8px;align-self:flex-start;border-radius:var(--r);cursor:pointer;
  user-select:none;
  /* Faz 46: 72×18px'ti — WCAG 2.2 AA tabanı 24×24. */
  min-height:24px;display:inline-flex;align-items:center}
.tier li .dispre:hover{color:var(--ink-2);border-color:var(--border-strong)}
.tier li .dispre[aria-expanded="true"]{color:var(--seal);border-color:var(--seal);
  background:var(--seal-soft)}
/* Rozet açılınca kodlar burada — mobilde de erişilir olsun diye SADECE ipucu
   değil (title tooltip dokunmatikte yok). */
.tier li .disout{font-size:var(--fs-xs);color:var(--ink-2);line-height:var(--lh-snug);
  border-top:1px dashed var(--border);padding-top:4px}
.tier li .disout .mono{color:var(--ink)}
.tier li[data-s="DONE"]{opacity:.5;border-left-color:var(--ok)}
/* Faz 80 — ders adı (tek satır), kademenin dönemi, katlanmış kademe. */
.tier li .tad{font-size:var(--fs-xs);color:var(--ink-2);font-weight:400;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tier > h3 .tierdonem{float:right;color:var(--ink-3);font-weight:600;letter-spacing:var(--ls-0);
  text-transform:none;font-family:var(--font-sans)}
.tier.bitti > h3{color:var(--ink-3);border-bottom-width:1px}
.tierbitti{font-size:var(--fs-sm);color:var(--ink-3);line-height:var(--lh-normal)}
.tier li[data-s="DONE"] .top{text-decoration:line-through}
/* Alınabilir = önşartların tamamı sağlanmış, BU DÖNEM alınabilir. */
.tier li[data-s="READY"]{background:var(--cap-soft);color:var(--cap-ink);font-weight:600;
  border-color:var(--cap);border-left-color:var(--cap)}
.tierstage.focus .tier li{opacity:.22}
.tierstage.focus .tier li.on{opacity:1}
.tier li.root{outline:2px solid var(--cap);outline-offset:2px}
/* Kademe efsanesi — renklerin ne anlama geldiği. */
.tierlegend{display:flex;flex-wrap:wrap;gap:14px;margin:2px 0 16px;
  font-size:var(--fs-sm);color:var(--ink-2)}
.tierlegend span{display:inline-flex;align-items:center;gap:6px}
.tierlegend i{width:22px;height:12px;border:1px solid var(--border);
  border-left:3px solid var(--border-strong);display:inline-block}
.tierlegend i.rdy{background:var(--cap-soft);border-color:var(--cap);border-left-color:var(--cap)}
.tierlegend i.done{border-left-color:var(--ok);opacity:.6}
.tierlegend i.line{width:22px;height:0;border:0;border-top:2px solid var(--seal);opacity:.7}
.tierfoot{margin-top:10px;font-size:var(--fs-sm);color:var(--ink-3);line-height:var(--lh-body)}
.tiergroup + .tiergroup{margin-top:24px;padding-top:24px;
  border-top:1px dashed var(--border-strong)}
.tiergroup > h3{font-size:var(--fs-md);margin-bottom:12px;display:flex;gap:8px;align-items:center}
.tiergroup > h3 .tag{font-size:var(--fs-xs)}

/* ★★ FAZ 57 — mezuniyet yol haritası. Özet önce (program başına bitiş), sonra
   bu dönem fark yaratacak ders, varsayımlar, dönem kartları. */
.yhprogramlar{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));
  gap:12px;margin-top:14px}
.yhprogram{border:1px solid var(--border);border-top:6px solid var(--accent);
  padding:12px 14px;background:var(--surface)}
.yhprogram[data-role="ANADAL"]{--accent:var(--anadal)}
.yhprogram[data-role="CAP"]{--accent:var(--cap)}
.yhprogram[data-role="YANDAL"]{--accent:var(--yandal)}
.yhbitis{font-family:var(--font-display);font-size:var(--fs-xl);font-weight:800;
  line-height:var(--lh-tight);margin-top:6px}
.yhalt{font-size:var(--fs-sm);color:var(--ink-2);margin-top:4px}
.yhgec{font-size:var(--fs-sm);color:var(--warn);font-weight:600;margin-top:6px}
.yhzamaninda{font-size:var(--fs-sm);color:var(--ok);margin-top:6px}
.yhsimdi{margin-top:14px}
.yhsatir{margin-top:8px;line-height:var(--lh-normal)}
.yhsatir .yhdugmeler .ghost{margin-left:0}
.yhvarsayim{margin-top:14px;border-left-color:var(--seal)}
.yhvarsayim ul{margin:6px 0 0;padding-left:20px;font-size:var(--fs-sm);
  line-height:var(--lh-normal)}
.yhzincir{margin-top:14px;font-size:var(--fs-md);color:var(--ink-2)}
.yhdonemler{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));
  gap:12px;margin-top:14px}
.yhdonem{border:1px solid var(--border);padding:10px 12px;background:var(--surface-2)}
.yhdonem.simdi{border-color:var(--seal);background:var(--seal-soft)}
.yhdonem.bos{background:transparent;border-style:dashed}
.yhdonem.yaz{border-style:dashed;border-color:var(--warn)}
.yhyaz{margin-top:14px}
.yhdugmeler{display:flex;flex-wrap:wrap;gap:8px;margin-top:6px}
/* Faz 118 — yol haritası önceliği. */
.yhoncelik{display:flex;flex-wrap:wrap;gap:8px 12px;align-items:center;margin-bottom:12px;
  font-size:var(--fs-md)}
.yhoncelik .radios{flex:0 1 auto}
.yhoncelik .radios button{flex:0 1 auto;padding:6px 12px}
.yhoncelik .meta{flex:1 1 260px}
/* Faz 61 — senaryo. */
.yhsenaryo{display:flex;flex-wrap:wrap;gap:8px 12px;align-items:center;margin-bottom:14px;
  font-size:var(--fs-md)}
.yhsenaryo select{width:auto}
.yhsenaryo input[type=number]{width:5.5em;padding:6px 8px}
.yhsenaryo input[aria-invalid=true]{border-color:var(--warn)}
.yhbosetiket{color:var(--ink-3)}
.yhseritsenaryo{border-left-color:var(--warn);margin-bottom:14px}
.yhseritsenaryo button{margin-left:8px}
.yhdonem.atlandi{border-style:dashed;border-color:var(--warn)}
/* Faz 61 — danışman özeti. */
.dozet h3{font-size:var(--fs-md);margin:14px 0 6px;letter-spacing:var(--ls-eyebrow);
  text-transform:uppercase;color:var(--seal)}
.dozet table{width:100%;border-collapse:collapse;font-size:var(--fs-sm)}
.dozet td,.dozet th{border-bottom:1px solid var(--border);padding:4px 6px;text-align:left;
  vertical-align:top}
.dozet ul{margin:4px 0 0;padding-left:20px;font-size:var(--fs-md);line-height:var(--lh-normal)}
.dozet .dsoru li{margin-bottom:4px}
.dozet .dnot{font-size:var(--fs-sm);color:var(--ink-3);margin-top:12px}
.yhdonem>h3{font-size:var(--fs-xs);letter-spacing:var(--ls-eyebrow);color:var(--seal);
  padding-bottom:6px;border-bottom:2px solid var(--border-strong);display:flex;
  gap:6px;align-items:center;flex-wrap:wrap}
.yhdonem .yhkredi{font-size:var(--fs-sm);color:var(--ink-3);margin-top:6px}
.yhdonem ul{list-style:none;margin:8px 0 0;padding:0;display:flex;
  flex-direction:column;gap:6px}
.yhdonem li{font-size:var(--fs-sm);line-height:var(--lh-snug)}
.yhdonem li .yhad{display:block;color:var(--ink-3)}
.yhdonem li .tag{margin-left:4px}
.yhdonem .empty{padding:8px 0;text-align:left}
/* Faz 57 — GNO hedefi (Kredi sınırım). */
.gnohedef{margin-bottom:14px;padding-bottom:14px;border-bottom:1px solid var(--border)}
/* Faz 71 — dönem sonu not senaryosu. */
.notsenaryo .nsust{margin:6px 0;font-size:var(--fs-sm);color:var(--ink-2)}
.notsenaryo .nskaydir{overflow-x:auto}
.nstablo{width:100%;border-collapse:collapse;font-size:var(--fs-sm)}
.nstablo th{text-align:left;color:var(--ink-3);font-weight:600;padding:4px 8px;
  border-bottom:1px solid var(--border-strong)}
.nstablo td{padding:4px 8px;border-bottom:1px solid var(--border);vertical-align:middle}
.nstablo .sayi{text-align:right}
.nstablo select,.notsenaryo .nsust select{min-height:32px}
.nssonuc{margin-top:10px;display:grid;gap:4px;font-size:var(--fs-md)}
.nsesik{display:flex;flex-wrap:wrap;gap:6px;margin-top:4px}
/* Faz 72 — GNO panelindeki eşik hapları ile AYNI görünüm (küçük harf; .chip
   BÜYÜK harf yazıyordu ve aynı eşik iki ayrı kılıkta görünüyordu). */
.nsesik .cat.ok{background:var(--ok-soft);color:var(--ok)}
.nsesik .cat.no{background:transparent;color:var(--danger);border-color:currentColor}
.gnobaslik{display:flex;flex-wrap:wrap;gap:4px 10px;align-items:baseline;margin-bottom:6px}
.gnosatir{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:2px 12px;
  padding:8px 0;border-top:1px solid var(--border);font-size:var(--fs-md)}
.gnosatir .gereken{text-align:right;white-space:nowrap}
.gnosatir .gnoalt{grid-column:1/-1;font-size:var(--fs-sm);color:var(--ink-3)}
/* Faz 69 — kalan bütün derslerde gereken ortalama (her eşiğin ikinci satırı). */
.gnosatir .gnokalan{grid-column:1/-1;font-size:var(--fs-sm);color:var(--ink-2);
  padding-left:10px;border-left:2px solid var(--border)}
.gnook{color:var(--ok);font-weight:600}
.gnoyok{color:var(--danger);font-weight:600}
.gnohedef .meta{font-size:var(--fs-sm);color:var(--ink-3);line-height:var(--lh-normal)}
.gnonot{margin-top:8px}
/* Faz 60 — çevrimdışı şeridi (kopyadan açılan sayfa canlı değil). */
.note.cevrimdisi{border-left-color:var(--warn);margin:8px 0}
/* Faz 59 — tercih önizlemesi. */
.tercihonizle{margin-top:14px;display:flex;flex-direction:column;gap:6px;align-items:flex-start}
.tercihsonuc{margin-top:6px;align-self:stretch;display:flex;flex-direction:column;gap:6px}
.tercihdegisim{font-size:var(--fs-md)}
.tercihonizle .hint{font-size:var(--fs-sm);color:var(--ink-3);line-height:var(--lh-normal)}
.yhuyari{font-size:var(--fs-sm);color:var(--warn);margin-top:6px}

/* Bölüm çubuğu — yapışkan, tek satır, dar ekranda yana kayıyor. */
/* ⚠️ `var(--bg)` diye bir jeton YOK — doğrusu `--ground`. Yanlış ad
   çözümlenmeyince arka plan ŞEFFAF kalıyor ve kartlar çubuğun içinden
   geçerken üst üste biniyordu (kullanıcı raporu 23.08.2026). */
/* ★★ FAZ 46 — RAY (eski `.secnav` çapa çubuğu).
   Ölçülen sorun: 10 çapa, hepsi aynı sayfada; tıklamak kaydırıyordu.
   Artık görünüm değiştiriyor ve sayfa tek görünüm uzunluğunda.
   ⚠️ Ölçüde değişen tek şey konum DEĞİL, ANLAM: bu yüzden `aria-current`
   "page" (bulunduğun görünüm), eskiden "true" (kaydırılan bölüm) idi. */
.govde{display:grid;grid-template-columns:216px minmax(0,1fr);gap:24px;
  align-items:start}
.ray{position:sticky;top:18px;display:flex;flex-direction:column;gap:2px;
  border-right:1px solid var(--border);padding-right:10px}
.ray a{font-size:var(--fs-lg);letter-spacing:var(--ls-wide);
  font-family:var(--font-display);font-weight:700;
  color:var(--ink-2);text-decoration:none;padding:0 10px;
  border-left:3px solid transparent;
  /* ★ Faz 46: dokunma hedefi 40 → 44px (WCAG 2.2 AA tabanı 24, dokunmatik
     kılavuzu 44). Ray zaten dikey, yüksekliği bedava. */
  min-height:44px;display:flex;align-items:center;gap:8px}
.ray a:hover{color:var(--ink);background:var(--surface-2)}
.ray a[aria-current="page"]{color:var(--seal);border-left-color:var(--seal);
  background:var(--seal-soft)}
.ray .raysayi{margin-left:auto;font-family:var(--font-mono);
  font-size:var(--fs-sm);font-weight:400;color:var(--ink-3)}
.ray .raysayi:empty{display:none}
.ray .rayad.kisa{display:none}
.raydaha,.raykesme{display:none}
.ray .raybaslik{font-family:var(--font-mono);font-size:var(--fs-xs);
  letter-spacing:var(--ls-eyebrow);color:var(--ink-3);padding:14px 10px 6px;text-transform:uppercase}
.ray .raybaslik:first-child{padding-top:0}
.ray:empty{display:none}
.govde:has(.ray:empty){grid-template-columns:minmax(0,1fr)}
.icerik{display:flex;flex-direction:column;gap:32px;min-width:0}
/* ★ Telefon: ray ALT SEKME ÇUBUĞU olur. Ölçüm: 390px'te 10 çapanın 3'ü
   görünüyordu ve haftalık program 4 ekran aşağıdaydı. Alt çubuk hem her
   zaman görünür hem başparmak menzilinde. Birincil 4 sekme yazılı,
   gerisi "Daha" altında — sığmayanı kaydırmaya bırakmak, görünmeyen
   sekme demekti. */
@media (max-width:700px){
  .govde{grid-template-columns:minmax(0,1fr);gap:0}
  .ray{position:fixed;left:0;right:0;bottom:0;top:auto;z-index:var(--z-nav);
    flex-direction:row;gap:0;padding:0;border-right:0;
    border-top:1px solid var(--border);background:var(--surface);
    box-shadow:var(--shadow-sticky)}
  .ray a{flex:1 1 0;min-width:0;min-height:56px;padding:0 4px;
    flex-direction:column;justify-content:center;gap:2px;
    font-size:var(--fs-xs);letter-spacing:var(--ls-wide);text-align:center;
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
  .tab{flex:1 1 auto;min-width:0;padding:8px 10px;font-size:var(--fs-xs);
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
  body:not(.kurulum) header h1{font-size:var(--fs-xl)}
  body:not(.kurulum) header .eyebrow{flex:1 1 100%;order:3;font-size:var(--fs-xs)}
  body:not(.kurulum) header .sub{flex:1 1 100%;order:4;font-size:var(--fs-sm)}
  body:not(.kurulum) header #theme{order:2;min-height:44px;padding:0 12px}
  .veriyasi{gap:2px 6px}
  /* Dördü çubukta, gerisi "Daha" altında. */
  .ray a[data-alt]{display:none}
  .raydaha{display:flex;flex:1 1 0;min-width:0;min-height:56px;padding:0 4px;
    flex-direction:column;align-items:center;justify-content:center;
    background:transparent;border:0;border-top:3px solid transparent;
    font-family:var(--font-display);font-weight:700;
    font-size:var(--fs-xs);letter-spacing:var(--ls-wide);color:var(--ink-2);cursor:pointer}
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
  .wrap{padding-bottom:80px}
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
body.kurulum #roadmapSection,
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
.hero h2{font-size:var(--fs-2xl);margin:6px 0 8px}
.hero .lead{font-size:var(--fs-lg);color:var(--ink-2);line-height:var(--lh-body);max-width:62ch}
.steps{display:flex;flex-direction:column;gap:10px;margin-top:20px}
.step{display:flex;gap:14px;align-items:flex-start;padding:12px 14px;
  background:var(--surface-2);border:1px solid var(--border)}
/* ★ Faz 54: bitmiş ve kapalı adım OPAKLIKLA soldurulmuyor. `opacity:.5`
   açıklamaları 2,0–3,5:1'e düşürüyordu (taban 4,5) — oysa kapalı adımın
   metni yeni gelen kişiye SIRADA ne olduğunu anlatan tek yer. Durum artık
   renk ve kenarla: soluk başlık, kesik kenar, kilit simgesi. */
.step.done .body b{color:var(--ink-2)}
.step .no{flex:0 0 26px;height:26px;display:grid;place-items:center;
  background:var(--seal-soft);color:var(--seal);font-weight:700;font-size:var(--fs-sm);
  font-family:var(--font-display)}
.step.done .no{background:var(--ok-soft);color:var(--ok)}
.step .body{flex:1;min-width:0}
.step .body b{display:block;font-size:var(--fs-lg)}
.step .body span{display:block;font-size:var(--fs-sm);color:var(--ink-3)}
.step .body .why{margin-top:4px;color:var(--ink-2);font-style:italic}
.step button{flex:0 0 auto}
.step .sure{flex:0 0 auto;font-size:var(--fs-xs);color:var(--ink-3);white-space:nowrap;
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
.heroCta{display:flex;align-items:center;gap:12px;margin-top:20px;flex-wrap:wrap}
.heroCta .meta{font-size:var(--fs-sm);color:var(--ink-3)}
.heroSkip{margin-left:auto;font-size:var(--fs-md)}
.heroDismiss{font-size:var(--fs-sm);color:var(--ink-3)}
.ghost.big{font-size:var(--fs-lg);padding:12px 20px;letter-spacing:var(--ls-wide)}
/* Zorunlu adım ile isteğe bağlı iyileştirmeleri AYIRAN çizgi. */
.stepsplit{margin:20px 0 8px;font-size:var(--fs-xs);letter-spacing:var(--ls-label);
  text-transform:uppercase;color:var(--ink-3);display:flex;align-items:center;gap:10px}
.stepsplit::after{content:"";flex:1;height:1px;background:var(--border)}
.herofoot{margin-top:16px;font-size:var(--fs-sm);color:var(--ink-3);line-height:var(--lh-loose)}
/* "Şimdi ne yapabilirsin" — bir kerelik, kapatılabilir. */
.note.sonraki{border-left:3px solid var(--ok);padding:10px 12px;margin:14px 0}
.sonrakiliste{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px}
.sonrakiliste .kapat{margin-left:auto;color:var(--ink-3)}

/* Kaydedilen program bölümü. */
.savedhead{display:flex;flex-wrap:wrap;gap:14px;justify-content:space-between;
  align-items:flex-end;margin-bottom:12px}
.savedgrid{display:flex;flex-wrap:wrap;gap:8px}
.savedcard{background:var(--surface-2);border:1px solid var(--border);
  --accent:var(--anadal);padding:8px 12px;min-width:184px;flex:1 1 184px;
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
.savedcard .when{font-size:var(--fs-sm);color:var(--ink-3);margin-top:4px}
.savedcard .miss{font-size:var(--fs-sm);color:var(--warn)}
.savedtotals{margin-top:12px;font-size:var(--fs-md);color:var(--ink-2)}

/* Başvuru bölümünün KISA hâli — ayrıntı pencerede. */
.basvuruline{display:flex;flex-direction:column;gap:8px;margin-top:12px}
.basvuruitem{display:flex;align-items:center;gap:12px;padding:10px 12px;
  background:var(--surface-2);border:1px solid var(--border)}
.basvuruitem .mark{font-size:var(--fs-base);font-weight:700;line-height:var(--lh-none)}
.basvuruitem .what{flex:1;min-width:0;display:flex;flex-direction:column;gap:2px}
.basvuruitem .why{font-size:var(--fs-sm);color:var(--ink-3)}
.basvuruitem button{flex:0 0 auto;white-space:nowrap}
@media (max-width:560px){
  .yardimisaret{grid-template-columns:1fr}.yardimisaret dd{margin-bottom:8px}   /* Faz 96 */
  button.kders{min-height:36px;padding:6px 10px}   /* Faz 99 — dokunma hedefi */
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
dialog .pad{padding:24px 24px}
/* ★ Faz 67 — dış bağlantılar: altı çizili (renk tek işaret değil) ve ↗. */
a.dislink{color:var(--seal);text-decoration:underline;text-underline-offset:2px;
  /* Cümle içi bağlantının dokunma alanı ≥24px (Faz 48 kuralı): satır içi
     dolgu satır aralığını değiştirmeden tıklanabilir alanı büyütür. */
  padding-block:6px}
a.dislink:hover{color:var(--ink)}
.dislinkler{color:var(--ink-3);font-size:var(--fs-sm);margin-top:8px;line-height:var(--lh-loose)}
.planlink{font-size:var(--fs-sm);font-weight:400;white-space:nowrap}
.kaynaklar{margin-top:8px}
.kaynaklar>div{margin-top:4px}
footer{color:var(--ink-3);font-size:var(--fs-sm);border-top:3px solid var(--seal);padding-top:14px;
  line-height:var(--lh-loose)}
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

   Bu repoda kural: bilgi sessizce kaybolmaz. Renk gidiyorsa YAZI gelir,
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
    font-size:var(--fs-xs);letter-spacing:var(--ls-caps);text-transform:uppercase;
    white-space:nowrap}
  .blk[data-role]{border:1px solid CanvasText}
  /* 2. ÇUBUKLAR: dolu kısım sistem vurgusu, kanal kenarlıkla belli. */
  .capbar,.meter,.gaugebar .track,.yuk{border:1px solid CanvasText;background:Canvas}
  .capbar>i,.meter i,.gaugebar .track i,.yuk>i{background:Highlight}
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
  html,body{background:var(--ground);color:var(--kagit-murekkep)}
  /* ★★ FAZ 48 — KÂĞIT HER ZAMAN GÜNDÜZ PALETİ (taramada ölçüldü).
     Gece şemasındayken yazdırınca `--ink-3` kâğıda **açık gri** çıkıyordu:
     saat sütunu (08:00, 09:00…) rgb(132,142,161), özet satırı
     rgb(154,165,184) — beyaz kâğıtta ~2,6:1, yani okunmuyor. Kart zemini de
     rgb(22,27,36) kalıyordu (tarayıcı zemin basmayı açarsa siyah blok).
     ⚠️ Yeni palet UYDURULMADI: birebir açık tema jetonları. */
  __JETONLAR_KAGIT__
  /* Boş hücrenin "+" işareti bir DAVET; kâğıtta tıklanacak bir şey yok. */
  #grid td.free::after{content:"" !important}
  header,#secnav,#setupbar,#hero,#sonraki,.toolbar,.candbar,.modes,
  #candSection,#blockSection,#suggestSection,#changeSection,#basvuruSection,
  /* ⚠️ `#panels` ve `#savedSection` de burada: görünüm kipinden önce
     hepsi birden açıktı, şimdi hangi görünümdeysen o kâğıda sızıyordu —
     aynı Cmd+P aynı kâğıdı vermeli. */
  #panels,#savedSection,
  #tierSection,#roadmapSection,#creditSection,.tabs,#notime .blockitem button,
  #arzUyari,#ayarHatasi,#cevrimdisiNot,dialog,
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
  #grid td,#grid th{border-color:var(--kagit-cizgi)}
  .blk{border:1px solid var(--kagit-blok);background:var(--ground) !important;
    color:var(--kagit-murekkep) !important}
  .blk .mono{color:var(--kagit-murekkep)}
  /* ★ CRN listesi kâğıtta ASIL İŞ — ızgaranın altına basılıyor.
     Ekranda pencerede duruyor; yazdırırken pencere açık olmayabilir. */
  #printCrn{display:block !important}
  a[href]::after{content:""}          /* URL'leri metne eklemesin */
  /* Faz 61 — danışman özeti: yalnız özet basılıyor (kap body'ye taşınıyor). */
  body.ozetbaski>*:not(#ozetBaski){display:none !important}
  body.ozetbaski #ozetBaski{display:block !important}
}
#printCrn{display:none}
#printCrn table{width:100%;border-collapse:collapse;font-size:11pt}
#printCrn th,#printCrn td{border:1px solid var(--kagit-cizgi);padding:4px 6px;text-align:left}

@media (prefers-reduced-motion:no-preference){
  .blk,.tab,.ghost,.opt{transition:background var(--dur-fast) ease,color var(--dur-fast) ease}
}
</style>
</head>
<body>
<!-- ★ FAZ 56 — İÇERİĞE ATLA. Faz 51 `<main>` yer işaretini ekledi ama klavye
     kullanıcısı hâlâ her görünüm değişiminde üst çubuktaki ve raydaki
     ~13 durağı geçmek zorundaydı. Yalnız odaklanınca görünüyor. -->
<a class="atla" href="#icerik">İçeriğe atla</a>
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
    <div class="basdugme">
      <!-- Faz 96: kılavuz ilk gelen öğrencinin ilk sorusu; rayda en altta
           (telefonda "Daha" içinde) kaybolmasın. -->
      <button class="ghost" id="kilavuzBtn" type="button">Kılavuz</button>
      <button class="ghost" id="theme">Tema</button>
    </div>
  </div>
  <div class="sub" id="subtitle"></div>
  <!-- D3: verinin yaşı. Kontenjan sayıları buna ait, sayfanın üretildiği
       ana değil; ikisi günlerce ayrışabiliyor. -->
  <div class="sub veriyasi" id="veriYasi"></div>
</header>

<!-- D1: bozuk ayar dosyası. Sayfa açılıyor ama ne olduğu yazıyor. -->
<div class="note ayarhata" id="ayarHatasi" hidden></div>
<!-- Faz 61: danışman özetinin baskı kabı — yalnız "Yazdır"da doluyor. -->
<div id="ozetBaski" hidden></div>
<!-- Faz 60: çevrimdışı ya da cihazdaki kopyadan açıldı — veri canlı değil. -->
<div class="note cevrimdisi" id="cevrimdisiNot" role="status" hidden></div>

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

<!-- ★★ Faz 96 — KULLANIM KILAVUZU (kullanıcı isteği 25.09.2026: "aracın
     kullanım alanlarını, yapabildiklerini ve nasıl kullanılacağını anlatan bir
     yardım bölümü"). Özellikler 95 fazda eklendi ve çoğu bir düğmenin ya da
     bir görünümün içinde; yeni gelen öğrenci neyin var olduğunu bilmiyordu.
     Her madde ilgili görünüme GÖTÜREN bir düğme taşıyor — anlatmak yetmiyor,
     yeri göstermek gerekiyor. Sınırlar da burada: "bilinmeyen, bilinen gibi
     gösterilmez" ilkesi kullanıcıya da söylenmeli. -->
<section class="card pad yardim" id="yardimSection">
  <div class="sechead"><div class="eyebrow">Yardım</div><div class="rule"></div></div>
  <h2>Kullanım kılavuzu</h2>
  <p class="aciklama">__AD_KISA__, __AD_KURUM__ öğrencileri için bir ders programı ve mezuniyet
    planlama aracıdır. Anadal, çift anadal (ÇAP) ve yandal programlarını birlikte
    ele alır. Kayıt yapmaz; ders kaydı Kepler'de sizin tarafınızdan yapılır.</p>

  <h3>Başlarken</h3>
  <ol class="yardimadim">
    <li><b>Bölümünüzü ve yarıyılınızı seçiniz.</b> Varsa ÇAP ya da yandal
      programınızı da ekleyiniz. <button type="button" class="ghost mini" data-git="setupbar">Ayarlara git</button></li>
    <li><b>Aldığınız dersleri plandan işaretleyiniz.</b> "Plandan işaretle"
      penceresi bölümünüzün ders planını yarıyıl yarıyıl listeler; geçtiğiniz
      dersleri işaretlemeniz yeterlidir. Yarıyılınızı seçtiyseniz önceki
      yarıyılların zorunlu dersleri işaretli gelir — bu bir öneridir, lütfen
      kontrol ediniz. Notunu seçmediğiniz ders DD sayılır; GNO ve kredi yükü
      sınırı gerçek notlardan hesaplanacaksa aynı pencereden
      "Transkript yapıştır" ile notlarınızı da girebilirsiniz.
      <button type="button" class="ghost mini" data-ac="plan">Plandan işaretle</button></li>
    <li><b>Önerilen programı inceleyiniz.</b> Araç açılışta size uyan birkaç
      haftalık program önerir. <button type="button" class="ghost mini" data-git="schedSection">Haftalık programa git</button></li>
  </ol>

  <h3>Neler yapabilirsiniz</h3>
  <div class="yardimliste">
    <div class="yardimkart">
      <h4>Kayıt haftası</h4>
      <ul>
        <li>Önkoşulları, kredi yükü sınırını ve kontenjanı gözeten, çakışmasız
          program önerileri; farklı seçenekleri yan yana <b>karşılaştırma</b>.</li>
        <li>Bir dersi ya da şubesini <b>kilitleme</b> ve <b>meşgul saat</b>
          (iş, staj) ekleme. <b>Program tercihleri</b> ile boş gün, sabah dersi,
          kampüs değişimi ve öğretim üyesi tercihlerinizi belirtebilirsiniz.</li>
        <li>Dolu şube yerine tek dokunuşla boş şubeye geçiş; kontenjanı dolan
          ders için yedek CRN'ler.</li>
        <li><b>Kayıt günü listesi</b>: Kepler'e girilecek CRN'ler, çevrimdışı da
          açılır. <b>Takvime aktar</b>, <b>Resim (PNG)</b>, <b>Yazdır</b>.</li>
        <li><b>Programı kaydet</b> ve <b>Alternatif olarak kaydet</b> ile
          Plan A / B / C saklama; Kepler'de yaptığınız kaydı <b>CRN'den program
          yükle</b> ile geri getirme.</li>
      </ul>
      <button type="button" class="ghost mini" data-git="schedSection">Haftalık program</button>
      <button type="button" class="ghost mini" data-git="savedSection">Kaydedilen program</button>
    </div>
    <div class="yardimkart">
      <h4>Ders seçimi</h4>
      <ul>
        <li><b>Alınabilecek dersler</b>: şubeleri, saatleri, derslikleri ve
          doluluğuyla. Planınızın dışındaki bir dersi de <b>Ders ekle</b> ile
          programa koyabilirsiniz.</li>
        <li>Geçmiş dönemlerin not dağılımından <b>tahmini zorluk</b> (geçme ve
          yüksek not alma zorluğu, 10 üzerinden) ve bir dersin hangi dersleri
          açtığı.</li>
        <li><b>Alınamayan dersler</b>: neden alınamadığı (önşart, bu dönem
          açılmamış, şubeler başka programlara ayrılmış, kredi eşiği).</li>
      </ul>
      <button type="button" class="ghost mini" data-git="candSection">Alınabilecek dersler</button>
      <button type="button" class="ghost mini" data-git="blockSection">Alınamayan dersler</button>
    </div>
    <div class="yardimkart">
      <h4>İlerleme ve mezuniyet</h4>
      <ul>
        <li><b>İlerleme durumu</b>: anadal ve ikinci programda tamamlanan ve
          kalan dersler, ayrı ayrı.</li>
        <li><b>Yol haritası</b>: kalan derslerin dönemlere dağıtılmış hâli ve
          tahmini mezuniyet dönemi. Daha hafif yük, boş dönem (staj, Erasmus),
          yaz okulu ve dönem başına zor ders sınırı ile denenebilir.</li>
        <li><b>Kalma riski</b>: bir dersten kalınırsa mezuniyetin kaç dönem
          gecikeceği.</li>
      </ul>
      <button type="button" class="ghost mini" data-git="panels">İlerleme durumu</button>
      <button type="button" class="ghost mini" data-git="roadmapSection">Yol haritası</button>
    </div>
    <div class="yardimkart">
      <h4>Not ortalaması ve eşikler</h4>
      <ul>
        <li>Tahmini GNO, ÇAP'ın kendi ortalaması ve yönetmelikteki eşiklere
          (kredi yükü, ÇAP'a devam, mezuniyet) göre durumunuz.</li>
        <li><b>GNO hedefi</b>: bir eşiğe ulaşmak için bu dönem gereken ortalama.</li>
        <li><b>Not senaryosu</b>: bu dönemin derslerine not yazıp dönem sonu
          GNO'nuzu görme.</li>
      </ul>
      <button type="button" class="ghost mini" data-git="creditSection">Kredi ve not eşikleri</button>
    </div>
    <div class="yardimkart">
      <h4>ÇAP ve yandal</h4>
      <ul>
        <li><b>Başvuru</b>: yönergedeki şartların sizin durumunuzla
          karşılaştırması; her programda şimdiden sayılan dersleriniz ve
          tahmini bitiş dönemi.</li>
        <li><b>Denk dersler</b> ve <b>sayılabilecek dersler</b>: resmî
          denklikler ile aldığınız bir dersin başka bir gereksinimi karşılayıp
          karşılamadığı.</li>
      </ul>
      <button type="button" class="ghost mini" data-git="basvuruSection">Başvuru</button>
    </div>
    <div class="yardimkart">
      <h4>Danışman görüşmesi ve günlük kullanım</h4>
      <ul>
        <li><b>Danışman özeti</b>: programınız, ilerlemeniz ve danışmana
          sorulacaklar tek sayfada, yazdırılabilir.</li>
        <li>Telefonda gün listesi: her dersin saati, binası ve dersliği;
          listenin başında <b>sıradaki ders</b>.</li>
        <li><b>Son değişiklikler</b>: son veri tazelemesinden bu yana açılan,
          kapanan ya da dolan şubeler.</li>
      </ul>
      <button type="button" class="ghost mini" data-git="changeSection">Son değişiklikler</button>
    </div>
  </div>

  <h3>İşaretler</h3>
  <dl class="yardimisaret">
    <dt><span class="yerdurum dolu">dolu</span> <span class="yerdurum az">son 2</span></dt>
    <dd>Şubenin kontenjanı dolu ya da azalmış (veri tarihine göre; güncel
      doluluk OBS'dedir).</dd>
    <dt><span class="yerdurum az">⚠ Maçka → Ayazağa · 1 dk</span></dt>
    <dd>Arka arkaya iki ders farklı yerleşkede; arada az zaman var.</dd>
    <dt>INB D01</dt>
    <dd>Bina ve derslik. "yer bildirilmedi" ise OBS yer ilan etmemiştir.</dd>
    <dt>çevrimiçi ⌂</dt>
    <dd>Uzaktan yürütülen şube; kampüse gitmeyi gerektirmez.</dd>
    <dt>kolay · orta · zor</dt>
    <dd>Geçmiş not dağılımından tahmini zorluk; kişisel bir tahmin değildir.</dd>
  </dl>

  <h3>Bilmeniz gerekenler</h3>
  <ul class="yardimsinir">
    <li><b>Hesaplar tahmindir; esas olan OBS, Kepler ve yönetmeliktir.</b> Kayıt ve
      başvuru kararlarınızı danışmanınızla birlikte veriniz.</li>
    <li>Kontenjan ve şube bilgisi son tazeleme tarihindedir (sayfanın üstünde
      yazar); kayıt anında değişmiş olabilir.</li>
    <li>Araçta akademik takvim yoktur: tatil ve sınav haftalarını bilmez.</li>
    <li>Bir bilgi veride yoksa araç onu tahmin etmez, "bildirilmemiş" ya da
      "bilinmiyor" yazar.</li>
    <li>Notlarınız ve ayarlarınız yalnızca kendi bilgisayarınızda ya da
      tarayıcınızda saklanır; başka bir yere gönderilmez.</li>
  </ul>
</section>

<!-- ★ KAYDEDİLEN PROGRAM en üstte (kullanıcı isteği 23.08.2026).
     Kayıt haftasında araca dönmenin sebebi bu: "ben ne kaydetmiştim".
     Aşağıdaki ızgara bir ÇALIŞMA alanı ve düzenlendikçe değişiyor; kayıtlı
     program ise sabit bir kayıt. İkisini aynı yerde göstermek, hangisinin
     hangisi olduğunu belirsizleştiriyordu. -->
<section class="card pad" id="savedSection" hidden>
  <div class="sechead"><div class="eyebrow">Kayıtlı</div><div class="rule"></div></div>
  <div class="savedhead">
    <div><h2>Kaydedilen program</h2>
      <div class="summary" id="savedWhen"></div></div>
    <div class="toolbar" id="savedActions"></div>
  </div>
  <div id="savedList"></div>
  <div id="altList"></div>
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
    <summary>Kullanım ve renk açıklamaları</summary>
    <div class="hint">Bir derse tıklandığında şube değiştirilebilir, ders başka bir
      dersle değiştirilebilir veya programdan çıkarılabilir. Boş bir hücreye
      tıklandığında o saate uyan dersler listelenir.</div>
    <div class="hint" id="tonNot">Renk, dersin ait olduğu programı; ton ise dersi
      gösterir (aynı ton, aynı ders). 9'dan fazla derste tonlar tekrarlanır;
      ders adı, üzerine gelindiğinde görüntülenir.</div>
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
      <!-- ★ Faz 77 — Plan B, Plan C… -->
      <button class="ghost" id="altKaydet" hidden>Alternatif olarak kaydet</button>
      <!-- D2: tek adım geri. "Öneriye dön" her şeyi siliyordu. -->
      <button class="ghost" id="undo" hidden>Geri al</button>
      <button class="ghost" id="reset" hidden>Öneriye dön</button>
      <button class="ghost" id="crnBtn">Kayıt günü</button>
      <button class="ghost" id="icsBtn">Takvime aktar</button>
      <button class="ghost" id="pngBtn">Resim (PNG)</button>
      <button class="ghost" id="danismanBtn">Danışman özeti</button>
      <button class="ghost" id="shareBtn">Bağlantı</button>
      <button class="ghost" id="crnLoad">CRN'den yükle</button>
      <span id="savedMark" class="chip" style="color:var(--ok)" hidden></span>
    </div>
  </aside>
  </div><!-- /prgduzen -->
</section>


<section class="card pad" id="creditSection" hidden>
  <div class="sechead"><div class="eyebrow">Mevzuat kısıtı</div><div class="rule"></div></div>
  <h2 style="margin-bottom:14px">Kredi ve not eşikleri</h2>
  <div id="gpaBody"></div>
  <div id="gnoHedefBody"></div>
  <div id="notSenaryoBody"></div>
  <div id="loadBody"></div>
  <div id="floorBody"></div>
  <div id="creditBody"></div>
</section>

<section class="card pad" id="suggestSection" hidden>
  <div class="sechead"><div class="eyebrow">Denklik</div><div class="rule"></div></div>
  <h2>Daha önce alınmış olabilecek dersler</h2>
  <div class="aciklama">Transkriptteki dersler ile planların <b>doldurulmamış</b>
    slotları arasında ad eşleşmesi aranmıştır. Eşleşmeler yalnızca onayınızla
    uygulanır; hatalı bir denklik, tamamlanmamış bir şartı tamamlanmış
    gösterebilir.</div>
  <div id="suggestBody" style="margin-top:12px"></div>
</section>

<!-- ★ Almam gereken bir dersin denkliği bu dönem açıksa (kullanıcı isteği
     27.08.2026). Aday listesinden ayrı: burada gösterilen ders planımda
     olmayabilir ama denklikle bir gereksinimi karşılıyor. -->
<section class="card pad" id="denklikSection" hidden>
  <div class="sechead"><div class="eyebrow">Denklik</div><div class="rule"></div></div>
  <h2>Bu dönem açılan denk dersler</h2>
  <div class="aciklama">Alınması gereken bir dersin <b>denk</b> dersi bu dönem
    açılmışsa burada listelenir. Denk ders alındığında gereken ders yerine
    sayılabilir; bu genellikle <b>başka bir bölümün</b> dersidir ve
    <b>dilekçe</b> ile saydırılır. Kaynak: OBS'de ilan edilen resmî denklikler
    ve kullanıcı beyanları. Saydırma işlemi için danışmanınıza ve fakülte
    yönetim kuruluna başvurunuz.</div>
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
  <div class="aciklama">Puan; kritik yol, dersin önşartı olduğu ders sayısı,
    zorunluluk, kontenjan ve kademe dikkate alınarak hesaplanır. Bir satıra
    tıklanarak ders programa eklenebilir.</div>
  <!-- ★ 24.08.2026 — liste ilk 30 ile kesiliyordu ve arama yoktu: aklındaki
       dersi arayan kişi onu bulamıyor, "bu araç benim dersimi bilmiyor"
       diye çıkıyordu. Süzgeç kesme sınırını da kaldırıyor. -->
  <div class="candbar">
    <!-- ★ FAZ 51 — YER TUTUCU ETİKET DEĞİLDİR. Ölçüldü: bu kutunun
         `<label>`ı, `aria-label`ı ve `aria-labelledby`si yoktu; ekran
         okuyucu "arama" diyip geçiyordu. Üstelik yer tutucu yazmaya
         başlayınca kayboluyor — neyin arandığını hatırlatan tek şeydi. -->
    <input type="search" id="candQ" aria-label="Aday derslerde ara"
      placeholder="Ders arama — kod, ad veya öğretim üyesi (örn. MAT 103E, olasılık)">
    <div class="radios" id="candRole"></div>
    <label class="tickbox"><input type="checkbox" id="candFree"> yalnızca kontenjanı olanlar</label>
    <!-- ★ Faz 74 — "programıma daha ne sığar?" -->
    <label class="tickbox"><input type="checkbox" id="candFit"> yalnızca programa sığanlar</label>
    <!-- ★ Faz 76 — sıralama yalnız GÖRÜNTÜ; öneri puanı değişmiyor. -->
    <label class="tickbox">Sıralama <select id="candSort" aria-label="Aday dersleri sırala">
      <option value="">öneri puanı</option>
      <option value="ort">geçmiş not ortalaması</option>
      <option value="zor">tahmini zorluk (kolaydan zora)</option>
      <option value="bos">boş kontenjan</option></select></label>
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
  <h2 id="blockTitle">İkinci programda alınamayan dersler</h2>
  <div id="blockers"></div>
</section>

<!-- FAZ 12 — "başvurabilir miyim" (yapılacaklar 1.3) -->
<section class="card pad" id="basvuruSection" hidden>
  <div class="sechead"><div class="eyebrow">Başvuru</div><div class="rule"></div></div>
  <h2>Başvuru koşulları</h2>
  <!-- ★ 22.08.2026: bölüm iki satıra indi, ayrıntı pencereye taşındı.
       Şartlar + program tablosu sayfanın en uzun bölümüydü ve her açılışta
       oradaydı; oysa dönemde birkaç kez bakılan bir şey. -->
  <div class="basvuruline" id="basvuruSummary"></div>
</section>

<dialog id="basvuruDlg" class="wide"><div class="pad">
  <h2 id="basvuruDlgTitle" style="margin-bottom:4px">ÇAP planları</h2>
  <div class="aciklama">Yönergedeki şartlar mevcut durumunuzla karşılaştırılmaktadır.
    Başvuru kararı ilgili bölüme aittir; bu ekran yalnızca hazırlık amaçlıdır.</div>
  <div class="tabs" id="basvuruTabs" role="tablist" style="margin-top:12px"></div>
  <div id="basvuruBody"></div>
  <div class="toolbar" style="margin-top:16px">
    <button class="ghost" data-close>Kapat</button>
  </div>
</div></dialog>

<!-- ★★ FAZ 57 — MEZUNİYET YOL HARİTASI (yol haritası §2.1). Kademeler
     "en az kaç dönem" diyordu; burada kalan dersler dönem dönem yerleşiyor
     ve her programın tahmini bitişi yazıyor. Varsayımlar planın ÜSTÜNDE. -->
<section class="card pad" id="roadmapSection" hidden>
  <div class="sechead"><div class="eyebrow">Mezuniyet</div><div class="rule"></div></div>
  <h2>Yol haritası</h2>
  <div class="aciklama">Kalan dersler; önşart sırası, dönemlik kredi sınırı ve
    dersin açıldığı yarıyıl dikkate alınarak dönemlere yerleştirilmiştir.
    Hesaplamanın dayandığı varsayımlar aşağıda listelenmiştir.</div>
  <div id="roadmapBody"></div>
</section>

<section class="card pad" id="tierSection">
  <div class="sechead"><div class="eyebrow">Önşart zinciri</div><div class="rule"></div></div>
  <h2 id="tierTitle">Kademeler</h2>
  <div class="aciklama">Her kademe en az bir dönem sürer; kademe sayısı ikinci
    programın tamamlanabileceği en kısa süreyi gösterir. <b>Çizgiler önşart
    bağlarını</b> gösterir. Bir dersin üzerine gelindiğinde yalnızca o dersin
    zinciri görüntülenir; tıklandığında sabitlenir, ikinci tıklamada serbest
    bırakılır.</div>
  <div class="tierlegend" aria-hidden="true">
    <span><i class="rdy"></i> bu dönem alınabilir</span>
    <span><i class="done"></i> alınmış</span>
    <span><i></i> önşartı bekliyor</span>
    <span><i class="line"></i> önşart bağı</span>
  </div>
  <!-- Her ikinci programın KENDİ zinciri; aralarında önşart ilişkisi yok. -->
  <div id="tierGroups" style="margin-top:14px"></div>
</section>

</main><!-- /icerik -->
</div><!-- /govde -->

<footer>
  Bu araç yalnızca bilgilendirme amaçlıdır; ders kaydına ilişkin kararlar için
  danışmanınıza ve OBS'ye başvurunuz.
  Şube ve kontenjan verisi <span id="gen" class="mono"></span> itibarıyla.
  <!-- ★ "Bu dosya notlarını içerir" YALNIZ gerçekten içeriyorsa yazılıyor:
       transkript girmemiş kişiye söylenince, girmediği bir veriyi sızdırdığını
       sanıyor. Uyarı her yerde tekrarlanınca da okunmaz oluyor. -->
  <span id="gizlilik"></span>
  <div id="kaynaklar" class="kaynaklar"></div>
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
/* ★ Faz 111 — saati olmayan şubenin yazısı. Ek/sınırsız sınav şubesi (OBS
   öğretim yöntemi) bir ders değil, azami süreyi dolduranın sınav hakkı
   (2547 s. Kanun m. 44/c): saati "ilan edilmemiş" değil, HİÇ yok. */
const saatsizYazi = (sec, kip) => sec && sec.sinav ? sec.sinav
  : (kip === "kisa" ? "saat ilan edilmemiş" : "saati ilan edilmemiş");
/* ★ Faz 67 — DIŞ SİTEYE YÖNLENDİRME. Adresler tek yerde:
   `config.DIS_BAGLANTILAR` (→ DATA.links). Yeni sekmede açılır ve
   `noreferrer`: hangi sayfadan gelindiği (ve adres çubuğundaki paylaşım
   parametresi) karşı siteye gönderilmez. ↗ işareti, bağlantının aracın
   DIŞINA çıktığını gösterir. */
const disLink = (k, etiket, url) => {
  const L = (DATA.links || {})[k] || {};
  const u = url || L.url;
  if(!u) return etiket ? esc(etiket) : "";
  return `<a class="dislink" href="${esc(u)}" target="_blank" rel="noopener noreferrer"
    title="${esc([L.aciklama, "yeni sekmede açılır"].filter(Boolean).join(" · "))}">${
    esc(etiket || L.ad || u)}<span aria-hidden="true"> ↗</span></a>`;
};

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
   tam ad ipucunda.
   ★ Faz 56 — "yer yok" DEĞİL: kayıt gününde CRN'nin yanındaki "yer yok"
   KONTENJAN DOLU diye okunuyordu (ızgarada "15:30–18:29 yer yok · 22305").
   Kontenjanın dili "dolu / N boş"; derslik ilan edilmediyse bu yazıyor.
   Terminal (`recommend._building_label`) aynı sözü kullanıyor. */
/* ★★ Faz 93 — DERSLİK (kullanıcı isteği 25.09.2026: "sadece programa bakarak
   derslere gidilebilecek şekilde sınıfları gösterir misin"). Izgarada yalnız
   bina kodu ("MED") duruyordu; derslik veride vardı ama hiç gösterilmiyordu.
   Artık "MED D102". Derslik ilan edilmemişse yalnız bina yazılıyor ve ipucu
   bunu SÖYLÜYOR — uydurulmuyor. Yardımcılar buluşmanın kendisini alıyor
   (eski çağrılar için bina kodu da kabul). */
const _yerBina = (m) => typeof m === "string" ? m : ((m && m.building) || "");
const _yerSinif = (m) => (m && typeof m === "object" && m.room) || "";
const yerYazi = (m) => {
  const b = _yerBina(m), r = _yerSinif(m);
  return b ? (r ? `${b} ${r}` : b) : "yer bildirilmedi";
};
const yerBaslik = (m) => {
  const b = _yerBina(m), r = _yerSinif(m);
  if(!b) return "OBS'de yer bildirilmemiş";
  const ad = (DATA.buildings || {})[b];
  return `${ad ? `${b} — ${ad}` : b} · ${r ? `derslik ${r}` : "derslik OBS'de bildirilmemiş"}`;
};
/* Takvim dosyası için: "MED D102 — Maden Fakültesi". */
const yerTakvim = (m) => {
  const b = _yerBina(m), r = _yerSinif(m);
  if(!b) return "";
  const ad = (DATA.buildings || {})[b];
  return `${r ? `${b} ${r}` : b}${ad ? ` — ${ad}` : ""}`;
};

let LBL = DATA.secondLabel || "ÇAP";
/* ★ ÇAP ve yandal aynı anda olabiliyor: başlıklar TEK programa göre
   yazıldığında öbürü yokmuş gibi görünüyordu. */
const SECONDS = () => DATA.seconds || [];
/* ★ Seçili ama planı bulunamayan ikinci programlar. Bunları hiç yazmamak,
   "kaydım gitmiş" sanılmasına yol açıyordu (yandal kodu bozulunca tam da
   bu oldu). Planı yok diye SEÇİM yok sayılmıyor. */
const SECONDS_YOK = () => DATA.secondsMissing || [];
/* ★ Zaten girilmiş programın BAŞVURU eşiği hiçbir yerde ölçüt değil: yandal
   öğrencisine "Yandal başvurusu ≥ 2.50 ✗" demek yanlış bir kaygı üretir.
   Faz 57–71'de dört yerde ayrı ayrı yazılmıştı ve GNO paneli atlanmıştı
   (Faz 72, gerçek sitede yandal öğrencisiyle görüldü); artık tek kural. */
const kayitliBasvuru = (t) => t.kind === "basvuru"
  && SECONDS().some(x => x.kind === t.scope);
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
  $("#blockTitle").textContent = "Alınamayan dersler";
  $("#tierTitle").textContent = ikili ? "Kademeler" : `${LBL} kademeleri`;
  $("#gen").textContent = veriTarihi();
  $("#kaynaklar").innerHTML = `<div><b>Veri kaynakları:</b> ders, şube ve kontenjan
      bilgileri ${disLink("ituHelperVeri", "İTÜ Helper açık veri reposundan")}; ders
      planları, denklikler ve not dağılımları ${disLink("obsPlan", "İTÜ OBS")}'den
      alınmaktadır.</div>
    <div><b>Yararlı bağlantılar:</b> ${disLink("kepler", "Kepler (ders kaydı)")} ·
      ${disLink("obsProgram")} · ${disLink("obsPlan")} · ${disLink("yonerge")} ·
      ${disLink("ituHelper")} (${disLink("ituHelperOnsart", "önşart zinciri")},
      ${disLink("ituHelperProgram", "program oluşturucu")})</div>`;
  /* ★ Faz 54: sitede "bu dosya" YOK — notlar tarayıcıda. Yanlış yeri
     söylemek, neyin nerede durduğunu (ve neyin kaybolabileceğini) gizler. */
  $("#gizlilik").textContent = (DATA.load && DATA.load.noTranscript) ? ""
    : siteMi() ? "Notlarınız yalnızca bu tarayıcıda saklanır; tarayıcı verileri silindiğinde kaybolur. Yedek almanız önerilir (Ayar)."
    : "Bu dosya notlarınızı içerir; paylaşmayınız.";
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
          : DATA.load && DATA.load.noGrades
          ? "dönem yükü sınırı: harf notları girilince"
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
/* ★ Faz 56 — anlık görüntü damgası ISO olarak geliyordu ve "Ne değişti"
   onu olduğu gibi basıyordu: "2026-09-22T17:00:45 → 2026-09-23T17:00:45".
   Aracın her yerde kullandığı biçim `22.09.2026 17:00`. Çözülemeyen damga
   OLDUĞU GİBİ kalıyor — uydurma bir tarih ham damgadan kötü. */
function tarihYaz(ham){
  const m = /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/.exec(String(ham || ""));
  return m ? `${m[3]}.${m[2]}.${m[1]} ${m[4]}:${m[5]}` : String(ham || "");
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

/* ★★ FAZ 60 — ÇEVRİMDIŞI AÇILDIYSA SÖYLE (fikirler Y.8).
   Statik site artık cihazdaki kopyadan da açılıyor (`sw.js`). Kayıt günü
   bu hayat kurtarır — ama kontenjan sayısı kopyanın tazelendiği ana ait.
   Onu canlıymış gibi göstermek, bu aracın baştan beri yapmadığı şey:
   katalog kopyadan geldiyse ya da bağlantı yoksa şerit tarihiyle yazıyor.
   Yalnız statik sitede (`make app` her zaman canlı veriyle çalışıyor). */
function cevrimdisiDurumu(){
  const el = $("#cevrimdisiNot");
  if(!el) return;
  const kopya = !!window.__ITUCAP_ONBELLEK__;
  const agYok = !!window.__ITUCAP_API__ && navigator.onLine === false;
  el.hidden = !(kopya || agYok);
  if(el.hidden) return;
  el.innerHTML = `<b>${agYok ? "Bağlantı yok" : "Cihazdaki kopyadan açıldı"}</b>.
    Planınız, CRN'leriniz ve yedekleriniz kullanılabilir durumdadır; ancak ${esc(veriYasiMetni())}.
    Kontenjanlar değişmiş olabilir; <b>CRN'leri OBS'de doğrulayınız</b>.`;
}
addEventListener("online", cevrimdisiDurumu);
addEventListener("offline", cevrimdisiDurumu);

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
    yayımlanmıştır; dönem tamamlanmış görünmektedir.">⚠ ${
    esc(DATA.termLabel || DATA.term)} tamamlanmış görünüyor</b>`;
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
    + (siteMi() ? `<span class="veriyazi sitenot">Site dönem başında güncellenir;
         güncel kontenjan bilgisi ${disLink("obsProgram")} sayfasındadır.</span>`
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
    el.innerHTML = `<b>Ayar dosyası okunamadı; varsayılan ayarlar kullanılıyor.</b>
      <div class="mono" style="margin-top:4px">${esc(hata)}</div>
      <div style="margin-top:6px">Seçilen bölüm ve dönem <b>kullanılmamaktadır</b>.
        Dosyayı düzeltiniz veya seçimleri aşağıdan yeniden yapınız.</div>`;
    return;
  }
  if(!uyari.length) return;
  /* ★★ FAZ 53 — dosya OKUNUYOR ama bazı satırlar yanlış tabloda duruyor ve
     hiçbir şey yapmıyor. Kullanıcının kendi dosyasında ölçüldü:
     `cap_baslangic_yariyili` `[regulation]` altındaydı — yorum "3 ya da 5
     yaz" diyor, yazılsa yarıyıl tabanı UYGULANMIYOR ve kimse söylemiyordu.
     Fatal değil (sayfa doğru çalışıyor), o yüzden kırmızı değil. */
  const yer = (u) => u.tablo ? `[${esc(u.tablo)}]` : "ilk tablo başlığından önce";
  el.innerHTML = `<b>Ayar dosyasında okunmayan ${uyari.length === 1 ? "bir satır"
      : uyari.length + " satır"} bulunmaktadır.</b>
    <ul style="margin:6px 0 0;padding-left:20px">${uyari.map(u => `<li>
      <span class="mono">${esc(u.anahtar)}</span> ${yer(u)} altında — ${u.golge
        ? `araç <span class="mono">[student]</span> altındaki değeri kullanmaktadır;
           bu satır <b>etkisiz bir kopyadır</b>`
        : `araç bu satırı <b>okumamaktadır</b>; varsayılan değer geçerlidir`}.</li>`).join("")}</ul>
    <div style="margin-top:6px">Düzeltmek için bu satırları
      <span class="mono">config/settings.toml</span> dosyasında
      <span class="mono">[student]</span> başlığının altına taşıyınız veya siliniz.</div>`;
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
    throw new Error("sunucuya ulaşılamadı; `make app` komutunun çalıştığını kontrol ediniz");
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
/* Faz 75 — sunucudan her yeni durum bir sürüm; istek üzerine hesaplanan
   önbellekler (kalma riski) buna bağlı: transkript değişince eski sonuç
   geçersiz. `var` — kanca bu dosya yürürken de çağırabilir. */
var DURUM_SURUMU = 0;
function applyState(next, secenek){
  DURUM_SURUMU++;
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
      <button class="ghost" data-setup="dersler">Başarılan dersler</button>
      <button class="ghost" data-setup="tercih">Tercihler${
        tercihSayisi() ? ` <span class="chip">${tercihSayisi()}</span>` : ""}</button>`
    : `<span class="ro">Düzenlemek için <span class="mono">make app</span></span>
       <button class="ghost" disabled>Program</button>
       <button class="ghost" disabled>Dönem</button>
       <button class="ghost" disabled>Plandan işaretle</button>
       <button class="ghost" disabled>Başarılan dersler</button>
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
    <b>Verileriniz yalnızca bu tarayıcıda saklanır.</b> Bölüm bilginiz,
    ${n ? `<b>${n}</b> dersiniz` : "dersleriniz"}, kilitleriniz ve kaydedilen program
    bu tarayıcının deposunda tutulur; hiçbir sunucuya gönderilmez. Tarayıcı verileri
    silindiğinde, başka bir cihaza geçildiğinde veya tarayıcı yer açmak için
    temizlik yaptığında bu veriler <b>kaybolur</b>.
    <div class="veridugmeler">
      <button class="ghost" id="yedekIndir">Yedek indir</button>
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
    durum.innerHTML = `<b>Bu yedek, mevcut verilerin yerine geçecektir.</b>
      Yedek: ${esc((O.tarih || "").slice(0, 10))} · ${esc(O.anadal || "bölüm yok")} ·
      <b>${Number(O.ders) || 0}</b> ders. Mevcut: ${esc((SETUP && SETUP.anadalProgram) || "bölüm yok")} ·
      <b>${simdi}</b> ders.
      <div class="veridugmeler">
        ${simdi || (SETUP && SETUP.anadalProgram)
          ? `<button class="ghost" data-yedek="once">Önce mevcut verileri indir</button>` : ""}
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
      durum.textContent = `İndirildi (${n} dosya). Dosya notlarınızı içerdiğinden
        güvenli bir yerde saklayınız.`;
    }catch(e){ hataBildir($("#yedekIndir"), e); }
  });
  $("#yedekSec").addEventListener("click", () => yedekDosyaSec(durum));
  /* Kalıcı depolama: tarayıcı SORULMADAN temizleyebilir mi? Soru tarayıcıya
     yalnız DÜĞMEYLE gidiyor — Firefox izin penceresi açıyor, habersiz
     açılması şaşırtırdı. */
  const k = $("#veriKalici");
  const yaz = (v) => {
    k.innerHTML = v === true
      ? "✓ Tarayıcı bu siteye <b>kalıcı depolama</b> izni vermiştir; veriler yer açmak için silinmez."
      : v === false
        ? `⚠️ Tarayıcı yer açmak için bu sitenin verilerini <b>silebilir</b>.
           <button class="ghost mini" id="kaliciIste">Kalıcı depolama iste</button>`
        : "Bu tarayıcı kalıcı depolamayı desteklemiyor; yedek almanız önerilir.";
    const b = $("#kaliciIste");
    if(b) b.addEventListener("click", async () => {
      const r = await Y.kaliciIste();
      yaz(r);
      if(r === false) say2("tarayıcı isteği kabul etmedi; yedek indirmeniz önerilir");
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
                    + `lütfen pencereyi kapatmayınız`);
  }, 1000);
  try{
    applyState(await fn(), secenek);
    say("kaydedildi ✓");
    setTimeout(() => $("#setup").close(), 550);
    return true;
  }catch(err){
    say(err.message, true);
    return false;
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
    (sel ? "" : `<option value="" selected>— bölüm seçiniz —</option>`) +
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
    return (sel ? "" : `<option value="" selected>— ${KIND_LABEL[k]} bölümü seçiniz —</option>`)
      + liste.map(p => `<option value="${esc(p.code)}"${p.code === sel ? " selected" : ""}
        >${esc(p.code)} — ${esc(p.name || p.code)}</option>`).join("");
  };
  openSetup(`
    <div class="eyebrow">Kurulum</div>
    <h2 style="margin-bottom:4px">Program seçimi</h2>
    <p class="modenote" style="margin:2px 0 4px">Bir tek anadal yeter.
      <b>Çift anadal veya yandal programına kayıtlı değilseniz “Yok” seçeneğini
      bırakınız</b>; araç bu durumda yalnızca anadal için çalışır.</p>
    <div class="grid2">
      <label class="field"><span>Anadal <b style="color:var(--anadal)">*</b></span>
        <!-- ★ C7 — 127 satırlık kutuda arama yoktu ve liste KODA göre
             sıralıydı: öğrenci "Bilgisayar" diye arıyor, liste
             "AIN, ARC, BES…" diye gidiyordu. -->
        <input type="search" id="fAnadalQ" autocomplete="off"
          placeholder="Bölüm arama — “bilgisayar”, “BLG”, “makina”…"
          style="margin-bottom:6px">
        <select id="fAnadal" size="1">${opts(s.anadalProgram)}</select>
        <span class="hint" id="fAnadalSayi">Listede
          <b class="mono">${codes.length}</b> bölüm var.
          Bölümünüz listede yoksa o bölümün ders planı henüz alınmamıştır.</span></label>
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
          <span class="hint" id="fPlanNot-${k}">Plan seçilmezse en güncel OBS planı kullanılır.</span></label>
      </div>`).join("")}
    <details class="adv"${ozelKod ? " open" : ""}>
      <summary>Gelişmiş</summary>
      <div class="field"><span>Kayıt yapılabilen program kodları</span>
        <div class="kodlar" id="fTuretilen"></div>
        <span class="hint">Bir şubenin "Dersi Alabilen Programlar" listesinde bu
          kodlardan biri bulunuyorsa ders alınabilir. Kodlar yukarıdaki seçimlerden
          <b>otomatik</b> olarak türetilir ve seçimler değiştiğinde güncellenir.</span>
      </div>
      <div class="field" id="fOneriKutu" hidden><span>Bunlar da eklenebilir</span>
        <div class="kodlar" id="fOneri"></div>
        <!-- ⚠️ Otomatik EKLENMİYOR: "bu kodla da kayıt yapabilirsin" bir
             iddia ve yanlışsa alamayacağın dersi alabilir gösterir. -->
        <span class="hint">Aynı bölümün diğer dildeki programı. Yalnızca bu
          programa kayıt yapılabiliyorsa ekleyiniz; <b>emin değilseniz eklemeyiniz</b>.
          Aksi hâlde alınamayacak dersler alınabilir olarak gösterilebilir.</span>
      </div>
      <label class="field"><span>Ekstra program kodları</span>
        <input type="text" id="fCodes" value="${esc((s.programCodes || []).join(", "))}"
          placeholder="genellikle boş bırakılır">
        <span class="hint">Yukarıdakilere <b>ek olarak</b> kayıt yapılabilen
          kodlar. Anadal, ÇAP ve yandal kodlarının buraya yazılması gerekmez.
          Kodları virgülle ayırınız.</span></label>
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
      if(not) not.innerHTML = !code || !list.length ? "Plan seçilmezse en güncel OBS planı kullanılır."
        : !an ? "Planlar anadala göre ayrıldığından önce anadal seçiniz."
        : uygun.length ? `<b>${uygun.length}</b> plan ${esc(an)} öğrencileri için ilan edilmiştir;
            plan seçilmezse en güncel olanı kullanılır.`
        : `⚠️ Bu bölümün ${KIND_LABEL[k]} planlarından hiçbiri ${esc(an)} için ilan
            edilmemiştir. Otomatik seçim en güncel planı kullanır; <b>bu plan sizin
            planınız olmayabilir</b>. Lütfen OBS'den doğrulayınız.`;
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
        ? t.map(c => `<span class="kod" title="seçimlerden türetildi">${esc(c)}</span>`).join("")
        : `<span class="hint">bölüm seçildiğinde burada görüntülenir</span>`;
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
        (secili ? "" : `<option value="">— bölüm seçiniz —</option>`)
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
        say("Lütfen önce anadal bölümünü seçiniz", true);
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
        say(eksik.map(k => KIND_LABEL[k]).join(" ve ") + " bölümü seçilmedi; lütfen seçiniz", true);
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

/* ★★ FAZ 57 — KAMPÜS TERCİHİ NE KADAR VERİYLE ÇALIŞIYOR (fikirler.md F.2).
   Ölçüm (Faz 37, iki kez): buluşmaların %42,5'inde bina ilan edilmemiş.
   Kampüsü bilinmeyen buluşma kampüs değişimi SAYILMIYOR — yani tercih o
   derslerde hiç uygulanmıyor. Kutuyu işaretleyen bunu bilmeli; kendi
   adaylarında ölçülüp yazılıyor. Hepsi biliniyorsa hiçbir şey yazmıyor. */
function kampusKapsami(){
  let top = 0, yok = 0;
  (M().candidates || []).forEach(c => (c.sections || []).forEach(s => {
    if(s.online) return;
    (s.meetings || []).forEach(m => { top++; if(!m.campus) yok++; });
  }));
  if(!top || !yok) return "";
  return `<span class="hint" style="display:block">Aday derslerin
    <b class="mono">${top}</b> yüz yüze ders saatinden <b class="mono">${yok}</b>
    tanesinde bina/kampüs ilan edilmemiştir; bu tercih söz konusu saatlerde uygulanamaz.</span>`;
}

function tercihDialog(){
  const P = (SETUP && SETUP.prefs) || {};
  let erken = P.enErken || 0;
  let gunler = new Set(P.bosGunler || []);
  openSetup(`
    <div class="eyebrow">Kurulum</div>
    <h2 style="margin-bottom:4px">Tercihler</h2>
    <p class="modenote" style="margin:2px 0 4px">Tercihler <b>eleme değil,
      sıralama</b> amacıyla kullanılır: araç önce uygulanabilir programları
      belirler, ardından tercihlerinize en uygun olanı öne alır. Tercihlere
      uymayan tek bir uygulanabilir program varsa bu program yine de gösterilir.</p>

    <label class="field"><span>Şu saatten önce ders istemiyorum</span>
      <div class="radios" id="fErken">
        ${TERCIH_SAAT.map(([v, l]) =>
          `<button data-v="${v}" aria-pressed="${v === erken}">${l}</button>`).join("")}
      </div></label>

    <label class="field"><span>Boş kalmasını istediğim günler</span>
      <div class="terms" id="fGun">
        ${TERCIH_GUN.map(([v, l]) => `<button data-v="${v}"
          aria-pressed="${gunler.has(v)}" style="width:auto;padding:8px 12px"
          >${l}</button>`).join("")}
      </div>
      <span class="hint">Beş günün tamamı seçilemez.</span></label>

    <!-- ★ Faz 80 — iki onay kutusu 190px'lik ızgara sütunlarındaydı ve
         .tickbox satır KAYDIRMIYOR (white-space:nowrap): "Aynı gün kampüs
         değiştirmek istemiyorum" yandaki kutunun üstüne taşıyordu (1400px'te
         ölçüldü). Alt alta liste; etiket gerekirse kayıyor. -->
    <div class="tickliste" style="margin-top:14px">
      <label class="tickbox"><input type="checkbox" id="fKampus"
        ${P.kampus ? "checked" : ""}> Aynı gün kampüs değiştirmek istemiyorum${
        kampusKapsami()}</label>
      <label class="tickbox"><input type="checkbox" id="fOnline"
        ${P.cevrimici ? "checked" : ""}> Çevrimiçi şubeyi yeğlerim</label>
    </div>

    <details class="adv"${(P.istenenHocalar || []).length
      || (P.istenmeyenHocalar || []).length ? " open" : ""}>
      <summary>Öğretim üyesi</summary>
      <label class="field"><span>Tercih edilen öğretim üyeleri</span>
        <input type="text" id="fHocaVar"
          value="${esc((P.istenenHocalar || []).join(", "))}"
          placeholder="Buzluca, Şule Itır"></label>
      <label class="field"><span>Tercih edilmeyen öğretim üyeleri</span>
        <input type="text" id="fHocaYok"
          value="${esc((P.istenmeyenHocalar || []).join(", "))}">
        <span class="hint">Adın bir kısmı yeterlidir; adları virgülle ayırınız.
          ⚠️ 3417 şubenin 887'sinde öğretim üyesi ilan edilmemiştir; bu şubeler
          tercih puanını etkilemez.</span></label>
    </details>
    <div class="tercihonizle">
      <button class="ghost" id="fOnizle" type="button">Kaydetmeden dene</button>
      <span class="hint">1. önerinin bu tercihlerle nasıl değişeceğini gösterir;
        hiçbir şey kaydedilmez.</span>
      <div id="fOnizleSonuc" aria-live="polite"></div>
    </div>`, () => {
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
        else if(gunler.size >= 4) { say("beş günün tamamı boş olarak seçilemez", true); return; }
        else gunler.add(v);
        b.setAttribute("aria-pressed", gunler.has(v));
        say("");
      }));
    /* Kaydet ve "Kaydetmeden dene" AYNI gövdeyi gönderiyor — iki ayrı
       toplama yolu ayrışırsa önizleme başka bir şeyi denemiş olurdu. */
    const govde = () => {
      const ayir = (id) => $(id).value.split(",").map(s => s.trim()).filter(Boolean);
      return {enErken: erken, bosGunler: [...gunler],
              kampus: $("#fKampus").checked, cevrimici: $("#fOnline").checked,
              istenenHocalar: ayir("#fHocaVar"), istenmeyenHocalar: ayir("#fHocaYok")};
    };
    $("#setupSave").addEventListener("click", () => {
      save(() => api("/api/tercih", govde()), {});   // kip korunur (Faz 54)
    });
    $("#fOnizle").addEventListener("click", async () => {
      const btn = $("#fOnizle"), bitti = dugmeMesgul(btn, "hesaplanıyor…");
      try{
        const r = await api("/api/tercih/onizle", {...govde(), mode: M().key});
        $("#fOnizleSonuc").innerHTML = tercihOnizleme((M().schedules || [])[0],
                                                      r.onizleme && r.onizleme.schedule);
      }catch(err){
        $("#fOnizleSonuc").innerHTML = `<div class="note ayarhata">Denenemedi —
          ${esc(err.message || String(err))}</div>`;
      }finally{ bitti(); }
    });
  });
}

/* ★★ FAZ 59 — TERCİHİ KAYDETMEDEN DENE (fikirler §3.6).
   Tercihin bedelini görmek için kaydedip ana ekrana bakmak, beğenmezsen
   pencereyi yeniden açıp geri almak gerekiyordu. Sunucu ayarların
   BELLEKTEKİ kopyasıyla raporu kuruyor (`/api/tercih/onizle`, salt okunur);
   burada bugünkü 1. öneriyle yan yana: hangi ders/şube değişiyor, haftanın
   şekli, tercih puanı ve — karşılanamıyorsa — ne bırakılmalı. */
function tercihOnizleme(once, sonra){
  if(!sonra) return `<div class="note tercihsonuc">Bu tercihlerle program
    oluşturulamadı. Tercihler eleme yapmadığından neden başka bir kısıttır.</div>`;
  const o = new Map(((once && once.picks) || []).map(p => [p.course, p.section.crn]));
  const y = new Map(sonra.picks.map(p => [p.course, p.section.crn]));
  const degisim = [
    ...[...y.keys()].filter(k => !o.has(k)).map(k => `+ <b class="mono">${esc(k)}</b>`),
    ...[...o.keys()].filter(k => !y.has(k)).map(k => `− <b class="mono">${esc(k)}</b>`),
    ...[...y.keys()].filter(k => o.has(k) && o.get(k) !== y.get(k)).map(k =>
      `<b class="mono">${esc(k)}</b> şubesi <span class="mono">${esc(o.get(k))} → ${
        esc(y.get(k))}</span>`)];
  const sekil = (x) => {
    const s = x && x.shape;
    if(!s || s.earliest == null) return "—";
    return `${s.days.length} gün · <span class="mono">${hhmm(s.earliest)}–${hhmm(s.latest)}</span>
      · boş gün: ${(s.freeDays || []).map(d => DAYS[d - 1]).join(" ") || "yok"}`;
  };
  const d = sonra.prefDelta || 0;
  return `<div class="note tercihsonuc">
    <div><b>1. öneri bu tercihlerle</b>${degisim.length ? "" : " — <b>değişmiyor</b>"}</div>
    ${degisim.length ? `<div class="tercihdegisim">${degisim.join(" · ")}</div>` : ""}
    <div class="meta">mevcut: ${sekil(once)}<br>bu tercihlerle: ${sekil(sonra)}</div>
    ${(sonra.prefReasons || []).length ? `<div>Tercih puanı <b class="mono">${
      d > 0 ? "+" : ""}${d}</b>: ${sonra.prefReasons.map(esc).join(" · ")}</div>`
      : `<div>Tercihleriniz bu öneride tamamen karşılanmaktadır ✓</div>`}
    ${tercihCaresi(sonra)}
    <div class="meta">Değişiklikler kaydedilmedi. Uygulamak için “Kaydet” düğmesini kullanınız.</div></div>`;
}

/* ---------- 2. dönem seçimi ---------- */
function termDialog(){
  const cur = SETUP.donem;
  const capCur = SETUP.capBaslangic || 0;
  /* ★ Faz 65 — ÇAP'ı olmayana "ÇAP'a başladığın yarıyıl" sorulmuyordu değil,
     SORULUYORDU (gerçek sitede BLGE + "Yok" ile görüldü). Soru yalnız ÇAP
     varken; yoksa dönem düğmesi TEK TIKLA kaydediyor — kurulum listesi
     "Tek tıklama" diyordu, iki tık gerekiyordu. */
  const capVar = ["cap", "ikisi"].includes(SETUP.secondKind);
  openSetup(`
    <div class="eyebrow">Kurulum</div>
    <h2 style="margin-bottom:4px">Yarıyıl bilgisi</h2>
    <p class="modenote" style="margin:2px 0 4px">&#8220;Dönemlik + alttan&#8221;
      öneri kipi bu bilgiyi kullanır. Dönemlik: bu yarıyılın plan dersleri;
      alttan: önceki yarıyıllardan kalan dersler.</p>
    <label class="field"><span>Dönem</span>
      <div class="terms" id="fTerm">
        <button data-t="0" aria-pressed="${!cur}" style="width:auto;padding:8px 12px"
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
        : `<b>Yarıyıl bilgisi bulunmamaktadır.</b> Başarılan dersler de
           girilmediğinden yarıyıl çıkarılamamaktadır; öneri bu nedenle planın
           tüm dönemlerinden ders içermektedir.`}
        Otomatik seçimde yarıyıl, başarılan slotların en ileri döneminden
        çıkarılır; kayıt donduran veya yaz okuluna devam eden öğrencilerde
        sonuç farklı olabilir.
      </span></label>
    ${capVar ? `<label class="field" style="margin-top:14px"><span>ÇAP'a başlanan yarıyıl</span>
      <div class="terms" id="fCap">
        <button data-t="0" aria-pressed="${!capCur}" style="width:auto;padding:8px 12px"
          >bilmiyorum</button>
        <button data-t="3" aria-pressed="${capCur === 3}">3</button>
        <button data-t="5" aria-pressed="${capCur === 5}">5</button>
      </div>
      <span class="hint">Bulunulan yarıyıl <b>değil</b>, ikinci anadala
        <b>başlanan</b> yarıyıldır. Yönerge, yarıyıl tabanını bu bilgiye bağlar:
        3'te başlayan her dönem en az <b>6</b>, 5'te başlayan en az <b>9</b>
        kredilik dersi ikinci anadaldan almak zorunda.
        &#8220;Bilmiyorum&#8221; seçilirse araç hiçbir taban iddia etmez.
      </span></label>` : ""}`, () => {
    let pick = cur || 0;
    let capPick = capCur || 0;
    const kaydet = () => save(() => api("/api/donem", {donem: pick, capBaslangic: capPick}));
    if(capVar) $("#fCap").querySelectorAll("button").forEach(b =>
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
        if(!capVar) kaydet();
      }));
    $("#setupSave").addEventListener("click", kaydet);
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
      <h2 style="margin-bottom:4px">${yok ? "Bölüm seçilmedi" : "Plan bulunamadı"}</h2>
      <p class="modenote">${yok
        ? `İşaretlenecek ders listesi <b>bölümünüzün planından</b> alınır;
           bölüm seçilmeden gösterilecek bir plan bulunmamaktadır.`
        : `Seçilen bölümün ders planı katalogda bulunmamaktadır. Program
           seçimini değiştirebilir veya başarılan dersleri tek tek girebilirsiniz.`}</p>
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
                         ip: o.status === "IN_PROGRESS", credits: o.credits,
                         via: o.via || ""};
    }))));

  /* ★★ FAZ 47 — DÖNEMDEN ÖNERİLEN TİKLER (kullanıcı 18.09.2026:
     *"5. dönem olan birisi geçtiği dersleri işaretlemek için otomatik tik
     attırabilir"*).

     ⚠️⚠️ ÖNERİ, İDDİA DEĞİL. Bu repoda kural: bilinmeyen, bilinen gibi
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
        if(state[o.course] && !state[o.course].taken && !state[o.course].via){
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
    /* ★ Faz 97 — İngilizce eşiyle karşılanmış ÇAP/yandal dersi: tik KİLİTLİ,
       not seçimi yok. Tiklenebilseydi transkripte notsuz ikinci bir ders
       eklenirdi (bkz. server.plan_checklist). */
    return head + sl.options.map(o => o.via ? `
      <label class="ckrow ckvia" title="${esc(`${o.via} (${o.viaGrade || ""}) bu dersin İngilizce karşılığıdır; ÇAP/yandal gereksinimini karşılar. Ayrıca işaretlemeniz gerekmez.`)}">
        <input type="checkbox" checked disabled data-via="${esc(o.course)}">
        <span class="mono ckcode">${esc(o.course)}</span>
        <span class="ckname">${o.name ? esc(o.name.slice(0, 40)) : ""}</span>
        <span class="mono ckcr">${o.credits ?? "–"}</span>
        <span class="ckviayazi">✓ ${esc(o.via)} ile karşılandı</span>
      </label>` : `
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
    <p class="modenote" style="margin:2px 0 6px">Alınan dersleri işaretleyiniz.
      <b>0 kredili</b> dersler harf notu almaz — onlarda
      <b class="mono">BL</b> (başarılı) / <b class="mono">BZ</b> (başarısız).
      Notu bilinmeyen ders <b>DD</b> olarak sayılır.</p>
    <!-- ★ Faz 65 — kurulum listesi "en kolayı: transkriptini yapıştır"
         diyordu ama "Dersleri gir" buraya açılıyordu ve buradan yapıştırmaya
         yol YOKTU. Tikle girilen ders notsuz (DD) sayılıyor; GNO ve kredi
         tavanı için gerçek notlar ancak yapıştırmayla geliyor. -->
    <p class="modenote" style="margin:0 0 6px">Dersleri notlarıyla birlikte girmek için:
      <button class="ghost mini" id="ckYapistir">transkript yapıştır</button>
      (GNO ve kredi sınırı gerçek notlardan hesaplanır).</p>
    ${onerilen.length ? `<div class="note" style="border-left:3px solid var(--warn);
      padding-left:10px;margin:8px 0">
      <b>${onerilen.length} ders işaretlendi.</b> ${donem}. yarıyılda olduğunuz
      belirtildiğinden 1–${donem - 1}. yarıyılların zorunlu dersleri işaretlenmiştir.
      <b>Bu işaretleme bir tahmindir:</b> başarılamayan dersin işaretini kaldırınız.
      <button class="ghost mini" id="ckUndo" style="margin-left:6px"
        >tüm işaretleri kaldır</button></div>`
      : (donem === 1 ? `<div class="note" style="margin:8px 0">
          <b>1. yarıyıldasınız;</b> önceki yarıyıl bulunmadığından liste boş başlar.
          Yaz okulunda veya muafiyetle alınan ders varsa işaretleyiniz.</div>` : "")}
    <div class="chipline"><span class="chip">işaretle</span>
      <span style="color:var(--ink-3);font-size:var(--fs-sm)" id="ckCount"></span>
      <button class="ghost" id="ckAllTerm" style="margin-left:auto"
        >Önceki yarıyılların zorunlu derslerini işaretle</button></div>
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
    $("#ckYapistir").addEventListener("click", () => {
      $("#setup").close();            // açık pencerede showModal hata verir
      courseDialogSetup();
    });
    const bulk = $("#ckAllTerm");
    if(bulk) bulk.addEventListener("click", () => {
      // Bulunduğun dönemden ÖNCEKİ tüm zorunlu dersleri işaretle — çoğu
      // öğrenci için doğru başlangıç, tek tek düzeltmesi kolay.
      const upto = DATA.donem || 0;
      plans.forEach(p => p.terms.forEach(t => {
        if(!t.term || t.term >= upto) return;
        t.slots.forEach(sl => { if(sl.required) sl.options.forEach(o => {
          if(!state[o.course].via) state[o.course].taken = true; }); });
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
      remove: Object.entries(state).filter(([, v]) => !v.taken && !v.via)
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
  /* ★★ FAZ 72 — yapıştırma çalışma kopyasını ESKİ bırakıyordu. "Bu 21 dersi
     ekle" sunucuya yazıyor, pencere 550 ms sonra kapanıyordu; o arada liste
     hâlâ "Girilmiş dersler (0)" gösteriyor ve "Kaydet" yeniden açılıyordu.
     Kaydet'e basılırsa ESKİ liste replace:true ile gidip yapıştırılan
     transkripti siliyordu (gerçek sitede ölçüldü: 20 ders → GNO bilinmiyor).
     Tek tek eklenip kaydedilmemiş dersler de pencereyle birlikte
     kayboluyordu. Artık: bekleyen düzenleme yapıştırmadan ÖNCE kaydediliyor,
     başarıdan sonra liste sunucudaki transkriptle yenileniyor. */
  const govde = () => ({
    items: rows.map(r => ({course: r.course, grade: r.grade,
                           inProgress: r.status === "IN_PROGRESS"})),
    replace: true,
  });
  const ozet = () => JSON.stringify(govde().items);
  let kayitli = ozet();
  const calisma = {
    bekleyen: () => ozet() !== kayitli ? govde() : null,
    yenile: () => { rows = SETUP.transcript.map(t => ({...t})); kayitli = ozet(); draw(); },
  };

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
          <div class="meta" style="color:var(--ink-3);font-size:var(--fs-sm)">${
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
    <h2 style="margin-bottom:4px">Başarılan dersler</h2>
    <p class="modenote" style="margin:2px 0 4px">Notu bilinmeyen ders en düşük
      geçer not olan <b>DD</b> olarak sayılır. Böylece &#8220;MIN CC&#8221; koşulu
      bulunan bir önşart yanlışlıkla sağlanmış gösterilmez.</p>

    <!-- ★ KOLAY YOL ÖNDE (ilk kullanıcı incelemesi D2). Kart "transkriptini
         olduğu gibi yapıştır" diyordu ama pencerede öne çıkan şey tek tek
         ders yazmaktı; yapıştırma katlanmış bir <details> içindeydi. -->
    <label class="field"><span>1 · Transkript yapıştırma (önerilen)</span>
      <textarea id="trPaste" style="margin-top:4px"
        placeholder="OBS not dökümünü olduğu gibi yapıştırınız; sütunlu biçim de kabul edilir:&#10;MAT 103E    Mathematics I    4.0   6.0   BB&#10;FIZ 101E    Physics I        3.0   4.5   CB"
        ></textarea>
      <span class="hint">Sütunlu döküm veya <span class="mono">KOD NOT</span>
        biçimi kabul edilir. <b>Bulunan dersler uygulanmadan önce gösterilir.</b>
        Yapıştırılan dersler mevcut listeye <b>eklenir</b>; mevcut kayıtlar silinmez.</span>
      <div style="display:flex;gap:8px;margin-top:8px;flex-wrap:wrap">
        <button class="ghost primary" id="trOnizle">Önizle</button>
      </div>
      <div id="trOnizleme" style="margin-top:10px"></div></label>

    <label class="field"><span>2 · Tek tek ekleme</span>
      <input type="search" id="trSearch" placeholder="Kod veya ad — örn. MAT 103E"
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
      <summary style="cursor:pointer;font-size:var(--fs-md);color:var(--seal)"
        >Yedekten geri yükle (${SETUP.backups.length})</summary>
      <div class="hint" style="margin:6px 0">Silme içeren her kayıttan önce yedek
        alınır. Geri yükleme işlemi de yedeklendiğinden yanlış bir yedek
        seçildiğinde veri kaybı oluşmaz.</div>
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
        `<div class="empty">önce transkript metnini yapıştırınız</div>`; return; }
      kutu.innerHTML = `<div class="empty">okunuyor…</div>`;
      try{
        const r = await api("/api/transcript/preview", {text: metin});
        trOnizlemeCiz(r.preview || {}, calisma);
      }catch(err){
        kutu.innerHTML = `<div class="empty">${esc(err.message)}</div>`;
      }
    });

    // ★ replace:true — ekrandaki liste TAM liste. 'çıkar' düğmesinin
    //   çalışması için gerekli; yoksa silinen ders DB'de kalırdı.
    $("#setupSave").addEventListener("click", () => save(() => api("/api/transcript", govde())));
  });
}

/* ---------- yapıştırma önizlemesi (ilk kullanıcı incelemesi A1) ----------
   ⚠️ Üç sayı AYRI: bulundu · atlandı · notu okunamadı. Tek bir "10 ders
   eklendi" satırı, atlanan 8 satırı ve okunamayan 2 notu gizliyordu. */
function trOnizlemeCiz(p, calisma = null){
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
      <b>Notu okunamayan satırlar</b> (başarılı, DD olarak sayıldı):
      <div class="hint">${p.warnings.map(esc).join("<br>")}</div></div>` : ""}
    ${(p.bad || []).length ? `<div class="note" style="margin-top:8px">
      <b>Atlanan satırlar</b> (ders kodu bulunamadı):
      <div class="hint mono">${p.bad.map(esc).join("<br>")}${
        p.badTotal > p.bad.length ? `<br>…+${p.badTotal - p.bad.length}` : ""}</div></div>` : ""}
    <button class="ghost primary" id="trUygula" style="margin-top:10px"
      ${p.count ? "" : "disabled"}>Bu ${p.count} dersi ekle</button>`;
  const btn = $("#trUygula");
  if(btn) btn.addEventListener("click", async () => {
    const tamam = await save(async () => {
      const bekleyen = calisma && calisma.bekleyen();     // Faz 72
      if(bekleyen) await api("/api/transcript", bekleyen);
      return api("/api/transcript/paste", {text: $("#trPaste").value, replace: false});
    });
    // Aynı görevde (tıklama araya giremeden): liste artık kaydedilen transkript.
    if(tamam && calisma) calisma.yenile();
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
/* Yarıyıl tabanının bu dönemki durumu — renderFloor ve danışman özeti
   AYNI hesabı kullanıyor (Faz 61). Yalnız İKİNCİ programın kredileri. */
function tabanDurumu(F){
  const ikinci = picks().filter(p => p.cand.role !== "ANADAL");
  const kredi = +ikinci.reduce((a,p) => a + (p.cand.credits || 0), 0).toFixed(1);
  return {ikinci, kredi, ok: kredi + 1e-9 >= F.min, eksik: +(F.min - kredi).toFixed(1)};
}

function renderFloor(){
  const box = $("#floorBody");
  const F = DATA.secondFloor;
  if(!box) return;
  if(!F){ box.innerHTML = ""; return; }

  if(F.undeclared){
    box.innerHTML = `<div class="note" style="margin-top:12px">
      <b>İkinci anadal yarıyıl tabanı hesaplanamamaktadır.</b>
      Yönerge, ÇAP'a <b>3.</b> yarıyılda başlayan öğrenci için her dönem en az
      <b>6</b>, <b>5.</b> yarıyılda başlayan öğrenci için en az <b>9</b> kredi
      şartı öngörmektedir; ancak başlanan yarıyıl belirtilmemiştir.
      ${LIVE
        ? `Bu bilgi <b>Dönem</b> düğmesinden girilebilir.`
        : `Bu bilgi <span class="mono">config/settings.toml</span> dosyasındaki
           <span class="mono">${esc(F.setting)}</span> alanına yazılabilir.`}</div>`;
    return;
  }

  const {ikinci, kredi, ok, eksik} = tabanDurumu(F);
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
      <b>Bu dönem açılan derslerle tabanı karşılayan çakışmasız bir program
      bulunamamıştır.</b> Oluşturulan ${oneriler.length} öneriden hiçbiri, ders
      arzı, saat çakışması veya önşart nedeniyle ${F.min} krediye ulaşmamaktadır.
      Tabanın indirilmesi mümkündür (aşağıda) ve dönem başında yeni şubeler
      açılabilir. Danışmanınızla görüşmeniz önerilir.</div>` : ""}
    <div class="gauge" style="margin-top:14px;padding-top:14px;
         border-top:1px solid var(--border)">
      <div class="gaugebar" style="max-width:230px">
        <div class="track"><i class="${ok ? "ok" : ""}"
          style="width:${Math.min(100, F.min ? kredi / F.min * 100 : 0)}%"></i></div>
        <div class="gaugelabel"><b class="mono" style="font-size:var(--fs-base)">${kredi}</b>
          / ${F.min} kredi ${F.verified ? "" : "<b>⚠</b>"}
          <span style="color:var(--ink-3)">— ${esc(LBL)} tarafından</span></div>
      </div>
      <div style="flex:2;min-width:250px;font-size:var(--fs-md);color:var(--ink-2)">
        <b>İkinci anadaldan yarıyıl tabanı.</b>
        ÇAP'a <b>${F.startTerm}.</b> yarıyılda başlandığından her dönem
        ikinci anadaldan en az <b class="mono">${F.min}</b> kredilik ders
        alınması gerekmektedir.
        <div style="color:var(--ink-3);margin-top:4px">Bu kural, dönem kredi
          bandından (MADDE 17) ayrıdır; ÇAP öğrencisi kredi bandından muaftır,
          bu tabandan muaf değildir.</div>
        ${F.source ? `<div style="color:var(--ink-3)">${esc(F.source)}</div>` : ""}
      </div>
    </div>
    ${ok ? "" : `<div class="note" style="border-left-color:var(--danger);margin-top:12px">
      <b>Seçili programda ikinci anadaldan ${kredi} kredi bulunmaktadır; taban ${F.min} kredidir.</b>
      ${eksik} kredi eksiktir.
      ${R ? `<div style="margin-top:6px">Yönerge, tabanın
        <b>${R.min}</b> krediye kadar indirilmesine izin vermektedir; ancak
        indirim <b>başvuru ile</b> yapılır:
        ${R.conditions.map(c => `<span class="chip credit"
          style="margin:0 4px 0 0">${esc(c)}</span>`).join("")}
        gereklidir${R.deadline ? `; son tarih: <b>${esc(R.deadline)}</b>` : ""}.
        ${indirimYeterMi
          ? `<b style="color:var(--ok)">İndirim onaylanırsa mevcut seçim
             yeterli olacaktır.</b>`
          : `İndirim onaylansa bile ${+(R.min - kredi).toFixed(1)} kredi
             daha gerekmektedir.`}</div>` : ""}
    </div>`}`;
}

function renderLoad(){
  const L = DATA.load;
  if(!L || !L.max){ $("#loadBody").innerHTML = ""; return; }
  const fix = LIVE && L.conflict
    ? `<button class="ghost" id="loadFix">Sınırı ${L.max} krediye düşür</button>` : "";
  $("#loadBody").innerHTML = `
    <div class="gauge" style="margin-bottom:12px">
      <div class="gaugebar" style="max-width:230px">
        <div class="gaugelabel" style="margin-top:0">
          <b class="mono" style="font-size:var(--fs-base)">${L.min ? L.min + "–" : "en çok "}${L.max}</b>
          kredi ${L.verified ? "" : "<b>⚠</b>"}</div>
        <div class="gaugelabel" style="color:var(--ink-3)">
          ${L.noTranscript
            /* ★★ İnceleme B4 — Faz 26 kararının uygulanmamış yarısı.
               Transkript yokken GNO 0.00 bir ÖLÇÜM değil, veri yokluğu.
               "GNO'ndan hesaplandı" demek onu ölçülmüş gibi sunuyordu; üstelik
               sayı süs değil, motor gerçekten bu tavanla program kuruyor.
               ⚠️ Tavanı gizlemiyoruz — motor bir sayı kullanmak ZORUNDA.
               Söylediğimiz şey değişiyor: "hesaplandı" değil, "VARSAYILDI". */
            ? `transkript girilmedi; <b>en düşük band varsayıldı</b>:`
            : L.noGrades ? `harf notu girilmedi; <b>en düşük band varsayıldı</b>:`
            : (({"yönetmelik": "kullanılan değer (GNO'dan hesaplandı)",
                 "ayar": "elle ayarlanmış değer (settings.toml)",
                 "çağrı": "bu çalıştırmaya özel değer"}[L.limitSource] || "ayarlı değer") + ":")}
          <b class="mono">${L.declared || "—"}</b></div>
      </div>
      <div style="flex:2;min-width:250px;font-size:var(--fs-md);color:var(--ink-2)">
        ${L.noTranscript ? `<div class="note" style="margin-bottom:8px">
          <b>GNO bilinmemektedir.</b> Aşağıdaki gerekçelerde yer alan “GNO 0.00”
          hesaplanmış bir değer <b>değildir</b>; başarılan dersler henüz
          girilmemiştir. Dersler girildiğinde kredi sınırı değişebilir.
          ${LIVE ? `<button class="ghost" data-setup="plan"
            style="margin-left:6px">Dersleri girin</button>` : ""}</div>` : ""}
        ${L.noGrades ? `<div class="note" style="margin-bottom:8px">
          <b>GNO bilinmemektedir.</b> Başarılan dersler girilmiş, ancak hiçbirinin
          harf notu girilmemiştir; notu bilinmeyen ders ortalamaya katılmaz. Aşağıdaki
          gerekçelerde yer alan “GNO 0.00” hesaplanmış bir değer <b>değildir</b>. Notlar
          transkript yapıştırılarak girildiğinde kredi sınırı değişebilir.
          ${LIVE || window.__ITUCAP_API__ ? `<button class="ghost" data-setup="dersler"
            style="margin-left:6px">Transkript yapıştır</button>` : ""}</div>` : ""}
        ${L.reasons.map(r => `<div>· ${esc(r)}</div>`).join("")}
        ${L.source ? `<div style="color:var(--ink-3);margin-top:4px">${esc(L.source)}</div>` : ""}
      </div>
    </div>
    ${L.conflict ? `<div class="note" style="border-left-color:var(--danger)">
      <b>Ayarlanan sınır (${L.declared}), yönetmeliğin izin verdiği değerden
      (${L.max}) yüksektir.</b> ${L.next ? `${L.next.max} krediye çıkmak için GNO ≥
      ${L.next.minGpa.toFixed(2)} gerekmektedir; mevcut GNO ${DATA.gpa.value.toFixed(2)}.` : ""}
      Program <b>${L.declared}</b> krediye kadar oluşturulmaktadır; bu durum
      kayıt sırasında reddedilebilir. ${fix}</div>` : ""}`;
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
    : t.ok ? "background:var(--ok-soft);color:var(--ok)"
           : "background:transparent;color:var(--danger);border-color:currentColor";
  const mark = t => t.ok === null ? "—" : (t.ok ? "✓" : "✗");
  const esikler = g.thresholds.filter(t => !kayitliBasvuru(t));
  const groups = Object.keys(STAGE).filter(k => esikler.some(t => t.kind === k));
  const loose = esikler.filter(t => !groups.includes(t.kind));
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
    <div style="display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-top:8px">
      <span class="eyebrow" style="min-width:74px">${STAGE[k]}</span>
      ${esikler.filter(t => t.kind === k).map(chipOf).join("")}
    </div>`).join("") + (loose.length ? `
    <div class="cats" style="margin-top:8px">${loose.map(chipOf).join("")}</div>` : "");
  const unverified = esikler.filter(t => !t.verified).length;
  const tolerated = esikler.filter(t => t.tolerance);
  const pending = esikler.filter(t => t.ok === null);
  $("#gpaBody").innerHTML = `
    <div class="gauge" style="margin-bottom:14px;padding-bottom:14px;
         border-bottom:1px solid var(--border)">
      <div class="gaugebar" style="max-width:230px">
        <div class="track"><i style="width:${Math.min(100, g.value / 4 * 100)}%"></i></div>
        <div class="gaugelabel"><b class="mono" style="font-size:var(--fs-base)">${g.value.toFixed(2)}</b>
          / 4.00 · <span class="mono">${g.counted}</span> ders,
          <span class="mono">${g.credits}</span> kredi</div>
      </div>
      <div style="flex:2;min-width:250px;font-size:var(--fs-md);color:var(--ink-2)">
        <b>GNO (tahmini)</b>: transkriptten hesaplanmıştır; <b>OBS'deki resmî
        GNO değildir</b>. Kesin değer için OBS'ye başvurunuz.
        <div class="cats" style="margin-top:8px">${chips}</div>
      </div>
    </div>
    ${g.partial || unverified || (g.conditional || []).length
      ? `<div class="note" style="margin-bottom:14px">
      ${g.noCredit.length ? `Kredisi bilinmeyen <b>${g.noCredit.length}</b> ders
        ortalamaya katılmadı (<span class="mono">${g.noCredit.slice(0,5).map(esc).join(", ")}</span>). ` : ""}
      ${g.uncertain.length ? `Notu girilmemiş <b>${g.uncertain.length}</b> ders
        ortalamaya katılmadı; GNO yalnızca notu bilinen derslerden hesaplanmıştır
        (önşart denetiminde bu dersler en düşük geçer not olan <b>DD</b> ile
        sayılır). ` : ""}
      ${(g.conditional || []).length ? condText(g) : ""}
      ${pending.length ? `<b>${pending.length}</b> eşik henüz hesaplanamamaktadır
        (—): ${pending.map(t => esc(t.why || t.label)).join(" ")} ` : ""}
      ${tolerated.length ? `<b>¹</b> ${tolerated.map(t =>
        esc(t.label)).join(", ")}: yönerge, eşiğin altına bir defaya mahsus
        düşülmesine izin verir; ikinci kez düşülmesi durumunda kayıt silinir. ` : ""}
      ${unverified ? `Eşiklerden <b>${unverified}</b> tanesi mevzuattan
        <b>doğrulanmamıştır</b> (⚠ işaretli). Teyit edildikten sonra
        <span class="mono">config/kurallar.toml</span> dosyasında
        <span class="mono">dogrulandi = true</span> olarak işaretlenebilir.` : ""}
    </div>` : ""}`;
}

/* ★★ FAZ 57 — GNO HEDEFİ: "eşikte kalmak için bu dönem kaç ortalama?"
   Eşik çipleri bugünü söylüyordu (✓/✗); asıl soru yarındı: ÇAP'a devam
   2.50 isteyen öğrenci 2.61'deyken bu dönem 21 kredi alırsa kaça kadar
   düşebilir? Cevap bir TAHMİN değil (fikirler.md "GNO'n şu kadar olur"u
   reddediyor — alacağın nottan bağımsız sayı): alacağın notun EŞİĞİ.
     gereken = (hedef × (C' + T) − P') / T
   C', P': ortalamaya giren kredi ve puan; tekrar alınan dersin ESKİ notu
   çıkarılmış (İTÜ'de son not geçerli, Faz 9). T: programdaki kredi.
   ⚠️ Puan toplamı Python'dan yuvarlanmadan geliyor (`gpa.points`);
   value × credits 2 haneli yuvarlamayı gereken ortalamaya taşırdı. */
const HARF_PUAN = [["FF",0],["DD",1],["DD+",1.25],["DC",1.5],["DC+",1.75],["CC",2],
  ["CC+",2.25],["CB",2.5],["CB+",2.75],["BB",3],["BB+",3.25],["BA",3.5],["BA+",3.75],["AA",4]];
function gnoHedefleri(){
  const g = DATA.gpa, out = [], gor = new Map();
  /* ★ Faz 58: anahtar TABAN + eşik. Faz 57'de yalnız eşikti; ÇAP'ın kendi
     ortalaması (2.00) ile genel mezuniyet (2.00) aynı satıra birleşirdi —
     iki ayrı ortalamanın iki ayrı şartı. */
  /* `donemlik`: yalnız bu dönemin sonucuna bağlı hedef (dönem kredi sınırı);
     mezuniyete kadar kalan dersler satırı ona anlamsız, gösterilmiyor. */
  const ekle = (min, ad, taban, donemlik = false) => {
    const k = taban + ":" + min.toFixed(2);
    if(gor.has(k)){ const h0 = gor.get(k); h0.adlar.push(ad);
      h0.donemlik = h0.donemlik && donemlik; return; }
    const h = {min, adlar: [ad], taban, donemlik};
    gor.set(k, h); out.push(h);
  };
  /* Zaten girilmiş programın BAŞVURU eşiği hedef değil: ÇAP öğrencisine
     "ÇAP başvurusu için 3.71 gerekir" demek yanlış bir kaygı üretirdi. */
  (g.thresholds || []).filter(t => t.basis === "genel" && t.min > 0 && !kayitliBasvuru(t))
    .forEach(t => ekle(t.min, t.label, "genel"));
  const L = DATA.load;
  if(L && L.next && L.next.minGpa) ekle(L.next.minGpa,
    `dönem sınırının ${L.next.max} krediye çıkması`, "genel", true);
  if((g.secondGpa || []).length)
    (g.thresholds || []).filter(t => t.basis === "ikinci anadal" && t.min > 0)
      .forEach(t => ekle(t.min, t.label, "ikinci"));
  return out.sort((a, b) => (a.taban === "ikinci") - (b.taban === "ikinci") || a.min - b.min);
}
/* Bir ortalamanın bu dönemki hesabı: C', P' tekrar alınan dersin eski notu
   düşülmüş kredi ve puan; T bu ortalamaya giren programdaki kredi. */
function gnoTabani(C0, P0, secili){
  const g = DATA.gpa;
  const T = secili.reduce((a, p) => a + p.cand.credits, 0);
  const tekrar = secili.filter(p => (g.retake || {})[p.cand.course])
    .map(p => ({course: p.cand.course, ...g.retake[p.cand.course]}));
  const C = C0 - tekrar.reduce((a, r) => a + r.credits, 0);
  const P = P0 - tekrar.reduce((a, r) => a + r.points, 0);
  return {T, C, P, tekrar};
}
/* ★★ FAZ 69 — MEZUNİYETE KADAR KALAN BÜTÜN DERSLERDE gereken ortalama.
   Kullanıcı: "eşikler için gereken dönem ortalamasının dışında kalan bütün
   derslerden gereken dönem ortalamasını da hesaplayıp gösterir misin".
   Taban sunucudan (`gpa.remaining`, yol haritasıyla aynı kalan dersler):
   T = kalan kredi; C, P = bugünkü ortalamanın kredisi/puanı, kalan
   derslerden daha önce notu olup geçilmemişlerin (tekrar) payı düşülmüş. */
/* Hesabın kendisi — satır (kalanSatiri) ve danışman sorusu AYNI sayıyı
   kullanıyor (Faz 70). null: taban yok ya da hedef yalnız bu döneme bağlı. */
function kalanGereken(h, g, ik){
  const R = (g.remaining || {})[h.taban];
  if(!R || h.donemlik) return null;
  const C0 = h.taban === "ikinci" ? (ik ? ik.credits : 0) : g.credits;
  const P0 = h.taban === "ikinci" ? (ik ? ik.points : 0) : g.points;
  const T = R.credits, C = C0 - R.retakeCredits, P = P0 - R.retakePoints;
  if(!T) return {T};
  return {T, x: (h.min * (C + T) - P) / T, enIyi: (P + 4 * T) / (C + T)};
}
function kalanSatiri(h, g, ik){
  const k = kalanGereken(h, g, ik);
  if(!k) return "";
  const {T, x, enIyi} = k;
  const bas = `Mezuniyete kadar kalan tüm derslerde (<b class="mono">${T}</b> kredi):`;
  if(!T) return `<span class="gnokalan">${bas.replace(":", "")} — kalan ders bulunmamaktadır.</span>`;
  let metin;
  if(x <= 1e-9)
    metin = `<span class="gnook">her durumda ✓</span> — kalan derslerin tümünden FF alınsa
      bile ortalama eşiğin üzerinde kalır.`;
  else if(x > 4 + 1e-9)
    metin = `<span class="gnoyok">ulaşılamaz</span> — kalan derslerin tümü AA olsa bile
      ortalama en fazla <b class="mono">${enIyi.toFixed(2)}</b> olur; danışmanınızla
      görüşmeniz önerilir.`;
  else {
    const harf = HARF_PUAN.find(([, v]) => v + 1e-9 >= x);
    metin = `ortalama en az <b class="mono">${(Math.ceil(x * 100 - 1e-6) / 100).toFixed(2)}</b>
      (her dersten en az <b class="mono">${harf[0]}</b>).`;
  }
  return `<span class="gnokalan">${bas} ${metin}</span>`;
}
function renderGnoHedef(){
  const kutu = $("#gnoHedefBody");
  if(!kutu) return;
  const g = DATA.gpa;
  if(!g || !g.counted || typeof g.points !== "number"){ kutu.innerHTML = ""; return; }
  const hedefler = gnoHedefleri();
  if(!hedefler.length){ kutu.innerHTML = ""; return; }
  const secili = picks().filter(p => (p.cand.credits || 0) > 0);
  const tabanlar = {genel: gnoTabani(g.credits, g.points, secili)};
  const ik = (g.secondGpa || [])[0];
  if(ik){
    const kod = new Set(ik.codes);
    tabanlar.ikinci = gnoTabani(ik.credits, ik.points,
      secili.filter(p => kod.has(p.cand.course)));
  }
  const {T, tekrar} = tabanlar.genel;
  const baslik = `<div class="gnobaslik"><b>Eşikler için gereken ortalama</b>
    <span class="meta">programdaki <b class="mono">${T}</b> kredi üzerinden${
      tekrar.length ? ` · tekrar: ${tekrar.map(r => `<span class="mono">${esc(r.course)}</span>
        (${esc(r.grade)})`).join(", ")}` : ""}</span></div>`;
  if(!T){
    kutu.innerHTML = `<div class="gnohedef">${baslik}<div class="meta">Programda kredili
      ders bulunmamaktadır; hesaplama için ders seçiniz.</div></div>`;
    return;
  }
  const satirlar = hedefler.map(h => {
    const {T, C, P} = tabanlar[h.taban];
    const ikinci = h.taban === "ikinci";
    const once = ikinci ? `Bu dönem, yalnız ${esc(ik.label)} dersleri
      (<b class="mono">${T}</b> kredi): ` : "Bu dönem: ";
    let sag, alt;
    if(!T){
      const simdi = C ? P / C : null;
      sag = `<span class="${simdi !== null && simdi + 1e-9 >= h.min ? "gnook" : "meta"}">${
        simdi === null ? "henüz yok" : "bu dönem değişmiyor"}</span>`;
      alt = simdi === null ? `Bu dönem ${esc(ik.label)} dersi ve notlu
          ${esc(ik.label)} dersi bulunmadığından ortalama henüz hesaplanamamaktadır.`
        : `Bu dönem ${esc(ik.label)} dersi bulunmamaktadır; ${esc(ik.label)} ortalaması
          <b class="mono">${simdi.toFixed(2)}</b> olarak kalır.`;
    } else {
      const x = (h.min * (C + T) - P) / T;
      const enIyi = (P + 4 * T) / (C + T);
      if(x <= 1e-9){
        sag = `<span class="gnook">her durumda ✓</span>`;
        alt = once + "tüm derslerden FF alınsa bile ortalama eşiğin üzerinde kalır.";
      } else if(x > 4 + 1e-9){
        sag = `<span class="gnoyok">bu dönem yeterli değil</span>`;
        alt = once + `tüm dersler AA olsa bile ortalama en fazla <b class="mono">${enIyi.toFixed(2)}</b>
          olur; eşiğe birden fazla dönemde ulaşılabilir.`;
      } else {
        const harf = HARF_PUAN.find(([, v]) => v + 1e-9 >= x);
        sag = `<b class="mono">≥ ${(Math.ceil(x * 100 - 1e-6) / 100).toFixed(2)}</b>`;
        alt = once + `her dersten en az <b class="mono">${harf[0]}</b> alınması yeterlidir.`;
      }
      alt = alt.charAt(0).toUpperCase() + alt.slice(1);
    }
    return `<div class="gnosatir" data-taban="${h.taban}">
      <span><b class="mono">${h.min.toFixed(2)}</b> — ${h.adlar.map(esc).join(" · ")}</span>
      <span class="gereken">${sag}</span>
      <span class="gnoalt">${alt}</span>
      ${kalanSatiri(h, g, ik)}</div>`;
  }).join("");
  kutu.innerHTML = `<div class="gnohedef">${baslik}${satirlar}
    <div class="meta gnonot">Bu değerler gereken notun hesabıdır. GNO transkriptten
      alınmıştır (<span class="mono">${g.value.toFixed(2)}</span>, tahmini).
      Tekrar alınan derste eski not yerine yeni not sayılmıştır (İTÜ'de son not
      geçerlidir); derslerin harf notlu olduğu varsayılmıştır.${kalanNotu(g)}</div>
  </div>`;
}

/* ★★ FAZ 71 — DÖNEM SONU NOT SENARYOSU ("bu notları alırsam ne olur").
   GNO hedefi soruyu tersinden soruyordu (eşik için hangi ortalama gerekir);
   öğrencinin kurduğu cümle ise "MAT 210E'den CC, BLG 223E'den BB alırsam
   GNO'm, ÇAP ortalamam ve gelecek dönem kredi sınırım ne olur". Taban GNO
   hedefiyle AYNI (`gnoTabani`: tekrar alınan dersin eski notu düşülür);
   eşikler `DATA.gpa.thresholds`, kredi sınırı `DATA.load.bands`
   (kurallar.toml). Seçimler yalnız bu tarayıcıda hatırlanır (kolaylık);
   hiçbir kayda yazılmaz. */
let NOT_SENARYO = null;
function notSenaryo(){
  if(NOT_SENARYO) return NOT_SENARYO;
  try{ NOT_SENARYO = JSON.parse(localStorage_get("notSenaryo") || "{}") || {}; }
  catch(e){ NOT_SENARYO = {}; }
  return NOT_SENARYO;
}
const NS_PUAN = Object.fromEntries(HARF_PUAN);
const yuvarla2 = (x) => Math.round(x * 100 + 1e-9) / 100;
function senaryoHesapla(secili, notlar){
  const g = DATA.gpa || {};
  const notlu = secili.filter(p => notlar[p.cand.course] in NS_PUAN);
  const kr = (l) => l.reduce((a, p) => a + p.cand.credits, 0);
  const pu = (l) => l.reduce((a, p) => a + p.cand.credits * NS_PUAN[notlar[p.cand.course]], 0);
  const T = kr(notlu);
  const r = {notlu, eksik: secili.length - notlu.length, T, donem: T ? pu(notlu) / T : null,
             gno: null, ikinci: null};
  if(g.counted && T){
    const b = gnoTabani(g.credits, g.points, notlu);
    r.gno = (b.P + pu(notlu)) / (b.C + T);
  }
  const ik = (g.secondGpa || [])[0];
  if(ik){
    const kod = new Set(ik.codes);
    const l = notlu.filter(p => kod.has(p.cand.course));
    const b = gnoTabani(ik.credits, ik.points, l);
    r.ikinciAd = ik.label;
    r.ikinciSimdi = ik.credits ? ik.points / ik.credits : null;
    r.ikinci = (b.C + kr(l)) ? (b.P + pu(l)) / (b.C + kr(l)) : r.ikinciSimdi;
  }
  return r;
}
/* Yönetmeliğin GNO bantlarından sınır — `policy.load_limit` ile aynı kural:
   GNO'nun tuttuğu bantların en yükseği. */
function bantSiniri(gno){
  const B = (DATA.load && DATA.load.bands) || [];
  const tutan = B.filter(b => gno + 1e-9 >= b.minGpa);
  return tutan.length ? Math.max(...tutan.map(b => b.max)) : null;
}
/* ★★ Faz 88 — "geçmişteki ortanca notla doldur". Derecelenebilen (Faz 87:
   yeterli veri, harf notlu) dersin olağan dönemlerindeki ortanca harf notu.
   Kişisel tahmin DEĞİL; öğrencinin "tipik bir sonuçla GNO'm ne olur"
   sorusuna başlangıç noktası. */
let NS_ORTANCA = null;          // son "ortanca" uygulamasının özeti (oturumluk)
const ortancaNot = (c) => { const z = zorlukOf(c); return z && z.median in NS_PUAN ? z.median : null; };
const ortancaIpucu = (c) => { const m = ortancaNot(c);
  return m ? ` <span class="meta nsortanca" title="Geçmişte dersi alan öğrencilerin ortanca harf notu (olağan dönemler, VF hariç)">ortanca <b class="mono">${m}</b></span>` : ""; };
function renderNotSenaryo(odak){
  const kutu = $("#notSenaryoBody");
  if(!kutu) return;
  const g = DATA.gpa;
  const secili = picks().filter(p => (p.cand.credits || 0) > 0);
  if(!g || !secili.length){ kutu.innerHTML = ""; return; }
  const notlar = notSenaryo();
  const r = senaryoHesapla(secili, notlar);
  const secim = (c) => `<select class="nssec" data-ns="${esc(c)}"
      aria-label="${esc(c)} için beklenen not"><option value="">—</option>${
      HARF_PUAN.slice().reverse().map(([h]) =>
        `<option${notlar[c] === h ? " selected" : ""}>${h}</option>`).join("")}</select>`;
  const satirlar = secili.map(p => {
    const rt = (g.retake || {})[p.cand.course];
    return `<tr><td class="mono">${esc(p.cand.course)}</td>
      <td>${esc(p.cand.name || "")}${rt ? ` <span class="chip unknown"
        title="Eski not ortalamadan düşülür; son alınan not geçerlidir">tekrar · eski ${
        esc(rt.grade)}</span>` : ""}</td>
      <td class="mono sayi">${p.cand.credits}</td><td>${secim(p.cand.course)}${ortancaIpucu(p.cand)}</td></tr>`;
  }).join("");
  const ok = (v, min) => yuvarla2(v) + 1e-9 >= min;
  const esikler = !r.T ? [] : (g.thresholds || [])
    .filter(t => t.min > 0 && !kayitliBasvuru(t))
    .map(t => {
      const v = t.basis === "ikinci anadal" ? r.ikinci : r.gno;
      return v === null ? "" : `<span class="cat ${ok(v, t.min) ? "ok" : "no"}">${
        esc(t.label)} ≥ ${t.min.toFixed(2)} ${ok(v, t.min) ? "✓" : "✗"}</span>`;
    }).join("");
  const L = DATA.load || {};
  const simdiSinir = L.max || null;
  const sonraSinir = r.gno !== null && DATA.unit === "kredi" ? bantSiniri(yuvarla2(r.gno)) : null;
  const ok2 = (a, b) => `<b class="mono">${a}</b>${b !== undefined && b !== null
    ? ` <span aria-hidden="true">→</span> <b class="mono">${b}</b>` : ""}`;
  const sonuc = !r.T
    ? `<div class="meta">Sonucu görmek için en az bir ders için beklenen notu seçiniz.</div>`
    : `<div class="nssonuc">
        <div>Dönem ortalaması: <b class="mono">${r.donem.toFixed(2)}</b>
          <span class="meta">(${r.notlu.length} ders, ${r.T} kredi)</span></div>
        <div>GNO (tahmini): ${g.counted ? ok2(g.value.toFixed(2), yuvarla2(r.gno).toFixed(2))
          : `<span class="meta">bilinmemektedir; harf notu girilmiş ders bulunmadığından
             yalnızca dönem ortalaması hesaplanmıştır.</span>`}</div>
        ${r.ikinciAd ? `<div>${esc(r.ikinciAd)} ortalaması: ${r.ikinciSimdi === null
          ? (r.ikinci === null ? `<span class="meta">henüz hesaplanamamaktadır</span>`
             : ok2("—", yuvarla2(r.ikinci).toFixed(2)))
          : ok2(r.ikinciSimdi.toFixed(2), r.ikinci === null ? null : yuvarla2(r.ikinci).toFixed(2))}</div>` : ""}
        ${sonraSinir ? `<div>Gelecek dönem kredi sınırı (yönetmelik): ${
          ok2(simdiSinir || "—", sonraSinir)} kredi</div>` : ""}
        ${esikler ? `<div class="nsesik">${esikler}</div>` : ""}
        ${r.eksik ? `<div class="meta">${r.eksik} ders için not seçilmediğinden hesaba
          katılmamıştır.</div>` : ""}
        <div class="nskalma" data-kalma="ns">${kalmaNsIcerik()}</div>
      </div>`;
  kutu.innerHTML = `<div class="gnohedef notsenaryo">
    <div class="gnobaslik"><b>Dönem sonu not senaryosu</b>
      <span class="meta">programdaki dersler için beklenen notları seçiniz; sonuç
        anında hesaplanır, hiçbir kayda yazılmaz</span></div>
    <div class="nsust"><label>Tümüne uygula:
      <select id="nsHepsi" aria-label="Tüm derslere aynı notu uygula"><option value="">seçiniz</option>
        ${HARF_PUAN.slice().reverse().map(([h]) => `<option>${h}</option>`).join("")}
        ${secili.some(p => ortancaNot(p.cand)) ? `<option value="ortanca">geçmişteki ortanca not</option>` : ""}
        <option value="temizle">temizle</option></select></label></div>
    ${NS_ORTANCA ? `<div class="meta nsortancanot" role="status">${NS_ORTANCA.uygulanan} derse
      geçmişteki ortanca harf notu yazılmıştır${NS_ORTANCA.eksik ? `; <b>${NS_ORTANCA.eksik}</b>
      ders için geçmiş veri bulunmadığından notu elle seçiniz` : ""}. Ortanca not, dersi
      geçmişte alan öğrencilerin ortasındaki notudur (olağan dönemler, VF hariç); kişisel
      bir tahmin değildir.</div>` : ""}
    <div class="nskaydir"><table class="nstablo"><thead><tr><th>Ders</th><th>Ad</th>
      <th class="sayi">Kredi</th><th>Beklenen not</th></tr></thead>
      <tbody>${satirlar}</tbody></table></div>
    ${sonuc}
    <div class="meta gnonot">Hesap tahminidir: GNO transkriptten alınmıştır; tekrar
      alınan derste eski not yerine yeni not sayılır. Kredi sınırı İTÜ Lisans Eğitim ve
      Öğretim Yönetmeliği MADDE 17'deki GNO bantlarından hesaplanır.</div>
  </div>`;
  kutu.querySelectorAll(".nssec").forEach(s => s.addEventListener("change", () => {
    NS_ORTANCA = null;                       // tek tek seçim: toplu uygulamanın notu eskidi
    if(s.value) notlar[s.dataset.ns] = s.value; else delete notlar[s.dataset.ns];
    localStorage_set("notSenaryo", JSON.stringify(notlar));
    renderNotSenaryo(s.dataset.ns);        // yeniden çizim odağı kaybettirmesin
  }));
  if(odak){
    const hedef = [...kutu.querySelectorAll(".nssec")].find(x => x.dataset.ns === odak)
      || (odak === "*" ? $("#nsHepsi") : null);
    if(hedef) hedef.focus();
  }
  kalmaBagla(); kalmaOto();        // Faz 75 — FF seçilince kendiliğinden
  const hep = $("#nsHepsi");
  if(hep) hep.addEventListener("change", () => {
    NS_ORTANCA = null;
    if(hep.value === "ortanca"){
      /* Faz 88 — verisi olan derse ortanca; olmayanın seçimine DOKUNULMUYOR
         (bilinmeyen, bilinen gibi doldurulmaz) ve sayısı söyleniyor. */
      NS_ORTANCA = {uygulanan: 0, eksik: 0};
      secili.forEach(p => { const m = ortancaNot(p.cand);
        if(m){ notlar[p.cand.course] = m; NS_ORTANCA.uygulanan++; } else NS_ORTANCA.eksik++; });
    }
    else secili.forEach(p => { if(hep.value === "temizle") delete notlar[p.cand.course];
                               else if(hep.value) notlar[p.cand.course] = hep.value; });
    localStorage_set("notSenaryo", JSON.stringify(notlar));
    renderNotSenaryo("*");
  });
}

/* ★★ FAZ 75 — KALMA RİSKİ: "bu dersten kalırsam mezuniyetim ne kadar gecikir?"
   Cevap haritayı yeniden kurarak ölçülüyor (`/api/kalmariski`, salt okunur):
   taban = bu dönemin PROGRAMI (ızgaradaki seçim) geçilmiş; her ders için o
   ders çıkarılıp yeniden kuruluyor. Önşart zinciri, açıldığı yarıyıl ve kredi
   sınırı haritanın kendi kuralları.
   KENDİLİĞİNDEN, ama yalnız sonucun GÖRÜNDÜĞÜ yerde (`kalmaOto`): yol
   haritası görünümü açıkken ya da not senaryosunda FF seçilmişken. Ölçüldü:
   gerçek katalogda Pyodide'de 6 ders için 0,35 sn; ızgaradaki her
   değişiklikte bunu ödemek gereksiz olurdu. Sonuç program, sınır ve durum
   sürümüne bağlı; biri değişince eski sonuç gösterilmiyor. Düğme, hata ya da
   otomatik tetik yokken elle hesaplamak için duruyor. */
let KALMA = null;          // {anahtar, veri, hata, yukleniyor}
function kalmaGirdi(){
  const ps = picks();
  const atama = yuvaAta(ps.map(p => p.cand)) || ps.map(p => p.cand.slotId || 0);   // Faz 81
  return {bu: ps.map((p, i) => ({course: p.cand.course, credits: p.cand.credits,
                                 role: p.cand.role, slotId: atama[i] || p.cand.slotId || 0})),
          maxLoad: (DATA.roadmap || {}).maxLoad};
}
function kalmaAnahtari(){
  const g = kalmaGirdi();
  return JSON.stringify([g.bu.map(x => x.course).sort(), g.maxLoad, DURUM_SURUMU]);
}
function kalmaHesaplanabilir(){
  const R = DATA.roadmap;
  return !!(R && !R.noTranscript && !R.error && R.maxLoad && picks().length
            && (LIVE || window.__ITUCAP_API__));
}
const kalmaGuncel = () => !!(KALMA && KALMA.anahtar === kalmaAnahtari());
async function kalmaYukle(){
  if(!kalmaHesaplanabilir()) return;
  const anahtar = kalmaAnahtari();
  KALMA = {anahtar, veri: null, hata: "", yukleniyor: true};
  kalmaCiz();
  await bekleBoyansin();         // "hesaplanıyor…" boyansın, sonra bloklayan hesap
  try{
    const r = await api("/api/kalmariski", kalmaGirdi());
    if(!KALMA || KALMA.anahtar !== anahtar) return;
    KALMA.veri = r.kalmaRiski;
  }catch(err){
    if(!KALMA || KALMA.anahtar !== anahtar) return;
    KALMA.hata = err.message || String(err);
  }
  KALMA.yukleniyor = false;
  kalmaCiz();
}
/* Yalnız yer tutucular yeniden dolduruluyor — not senaryosunun seçim
   kutuları yeniden çizilmesin (odak kaybolmasın). */
function kalmaCiz(){
  document.querySelectorAll("[data-kalma]").forEach(k => {
    k.innerHTML = k.dataset.kalma === "ns" ? kalmaNsIcerik() : kalmaPanelIcerik();
  });
  kalmaBagla();
  kalmaOto();
}
/* Sonuç görünür bir yerde isteniyorsa ve güncel değilse hesapla. Hata
   alınmış anahtar için yeniden denemiyor (sonsuz döngü olmasın). */
let KALMA_ZAMANLI = false;
function kalmaOto(){
  if(KALMA_ZAMANLI || !kalmaHesaplanabilir() || kalmaGuncel()) return;
  const gor = document.documentElement.dataset.gorunum;
  const notlar = typeof notSenaryo === "function" ? notSenaryo() : {};
  const ffVar = picks().some(p => notlar[p.cand.course] === "FF");
  if(!(gor === "roadmapSection" || (gor === "creditSection" && ffVar))) return;
  KALMA_ZAMANLI = true;
  setTimeout(() => { KALMA_ZAMANLI = false; if(!kalmaGuncel()) kalmaYukle(); }, 60);
}
function kalmaBagla(){
  document.querySelectorAll("[data-kalma] [data-kalmahesap]").forEach(b => {
    if(!b.dataset.bagli){ b.dataset.bagli = "1"; b.addEventListener("click", () => kalmaYukle()); }
  });
}
/* İkinci programın gecikmesi anadal bitişini aşmıyorsa iki programın BİRLİKTE
   tamamlandığı dönem (ikisinin en geç bitişi) değişmiyor — bunu söylemek
   "2 dönem gecikir"in yarattığı yanlış kaygıyı gideriyor. Diplomanın ne
   zaman verildiği yönergeye bağlı; burada yalnız dönem karşılaştırılıyor. */
const gecikmeYazi = (p, c) => {
  if(p.delay === null) return `${esc(p.label)} bitişi hesaplanamamaktadır`;
  if(p.delay <= 0) return `${esc(p.label)} bitişi değişmez`;
  const ana = (c.programs || []).find(x => x.role === "ANADAL");
  const asmaz = p.role !== "ANADAL" && ana && ana.finishSemester !== null
    && p.finishSemester !== null && p.finishSemester <= ana.finishSemester;
  return `${esc(p.label)} bitişi <b>${p.delay} dönem</b> gecikir${
    p.finish ? ` (${esc(p.finish.label)})` : ""}${asmaz
    ? ", ancak anadal bitişini aşmadığından iki programın birlikte tamamlanacağı dönem değişmez" : ""}`;
};
function kalmaDugme(metin){
  return KALMA && KALMA.yukleniyor && !kalmaGuncel() ? ""
    : `<button class="ghost mini" data-kalmahesap="1">${metin}</button>`;
}
function kalmaPanelIcerik(){
  if(!kalmaHesaplanabilir()) return "";
  const bas = `<b>Kalma riski</b> — bu dönemin programındaki bir dersten kalınması
    durumunda mezuniyet ne kadar gecikir?`;
  if(!kalmaGuncel()) return `<div class="note yhkalma">${bas}
    ${KALMA && KALMA.veri ? `<div class="meta">Program veya veriler değişmiştir.</div>` : ""}
    <div style="margin-top:6px">${kalmaDugme(KALMA && KALMA.veri ? "Yeniden hesapla" : "Hesapla")}</div></div>`;
  if(KALMA.yukleniyor) return `<div class="note yhkalma">${bas}
    <div class="meta" role="status">hesaplanıyor… (her ders için yol haritası yeniden kurulmaktadır)</div></div>`;
  if(KALMA.hata) return `<div class="note yhkalma">${bas}<div class="meta">Hesaplanamadı:
    ${esc(KALMA.hata)}</div></div>`;
  const V = KALMA.veri;
  /* ★★ Faz 88 — "kalırsam ne olur"un yanına "kalma ihtimali ne kadar":
     geçmişte kalma oranı = FF + VF (Faz 87: VF, vize barajı nedeniyle final
     hakkını kaybedenleri de gösteriyor). Aynı gecikmede kalma oranı yüksek
     ders önde. Oranı bilinmeyen dersin oranı UYDURULMUYOR. */
  const kalmaOrani = c => { const z = zorlukOf(candOf(c.course)); return z ? +(100 - z.passRate).toFixed(1) : null; };
  const gecikme = c => Math.max(...c.programs.map(p => p.delay || 0));
  const etkili = V.courses.filter(c => c.programs.some(p => p.delay !== 0))
    .sort((a, b) => gecikme(b) - gecikme(a) || (kalmaOrani(b) ?? -1) - (kalmaOrani(a) ?? -1));
  const etkisiz = V.courses.length - etkili.length;
  const RISK_ORAN = 20;
  const riskli = etkili.filter(c => gecikme(c) > 0 && (kalmaOrani(c) ?? 0) >= RISK_ORAN);
  return `<div class="note yhkalma">${bas}
    ${riskli.length ? `<div class="yhsatir kalmariskli"><b>Öncelik:</b> ${riskli.map(c =>
      `<b class="mono">${esc(c.course)}</b>`).join(", ")} — hem mezuniyeti geciktirebilir hem
      de geçmişte bu dersi geçemeyen öğrenci oranı %${RISK_ORAN} veya üzerindedir.</div>` : ""}
    ${etkili.map(c => { const o = kalmaOrani(c);
      return `<div class="yhsatir"><b class="mono">${esc(c.course)}</b> —
      ${c.programs.filter(p => p.delay !== 0).map(p => gecikmeYazi(p, c)).join("; ")}<span class="meta"> ·
      ${o === null ? "geçmiş kalma oranı bilinmemektedir"
        : `geçmişte kalma oranı <b class="mono">%${o}</b> (FF + VF)`}</span></div>`; }).join("")}
    ${etkisiz ? `<div class="yhsatir">${etkili.length ? "Diğer " : ""}<b>${etkisiz}</b> dersten
      kalınması bitişi değiştirmemektedir.</div>` : ""}
    <div class="meta" style="margin-top:6px">Taban: programdaki ${V.courses.length} dersin
      geçildiği varsayımı — ${V.base.map(b => `${esc(b.label)} ${b.finish
        ? esc(b.finish.label) : "bitiş hesaplanamamaktadır"}`).join(", ")}. Kalınan ders
      sonraki uygun döneme yerleştirilmiştir; önşart zinciri, dersin açıldığı yarıyıl ve
      dönem kredi sınırı yol haritasındaki kurallarla hesaplanmıştır. Kalma oranı OBS not
      dağılımının olağan dönemlerinden alınmıştır; kişisel bir tahmin değildir. GNO etkisi
      için "Kredi ve not" bölümündeki not senaryosu kullanılabilir.</div></div>`;
}
/* Not senaryosunda FF seçilen dersler için aynı sonuç. */
function kalmaNsIcerik(){
  const notlar = notSenaryo();
  const secili = new Set(picks().map(p => p.cand.course));
  const ff = Object.keys(notlar).filter(c => notlar[c] === "FF" && secili.has(c)).sort();
  if(!ff.length || !kalmaHesaplanabilir()) return "";
  if(!kalmaGuncel() || KALMA.yukleniyor || KALMA.hata)
    return `<div class="meta">FF seçilen ${ff.length} dersin mezuniyet tarihine etkisi:
      ${KALMA && KALMA.yukleniyor && kalmaGuncel() ? "hesaplanıyor…"
        : KALMA && KALMA.hata && kalmaGuncel() ? "hesaplanamadı — " + esc(KALMA.hata)
        : kalmaDugme("Hesapla")}</div>`;
  return ff.map(k => {
    const c = KALMA.veri.courses.find(x => x.course === k);
    return c ? `<div><b class="mono">${esc(k)}</b> dersinden kalınırsa:
      ${c.programs.map(p => gecikmeYazi(p, c)).join("; ")}</div>` : "";
  }).join("");
}

/* Kalan-ders satırının dayandığı şey — sayı ile birlikte yazılıyor. */
function kalanNotu(g){
  const R = (g.remaining || {}).genel;
  if(!R || !R.credits) return "";
  return ` “Kalan tüm dersler” satırı, planlardaki henüz tamamlanmamış
    <b class="mono">${R.courses}</b> dersin (${R.pools ? `<b class="mono">${R.pools}</b>
    seçmeli havuz dahil; ` : ""}bu dönemin programı dahil) mezuniyet anındaki ortalamasını
    gösterir${R.retake.length ? `; daha önce başarılamayan
    <span class="mono">${R.retake.map(esc).join(", ")}</span> tekrar sayılmıştır` : ""}${
    R.poolAssumed ? `; kredisi planda yazmayan ${R.poolAssumed} havuz 3 kredi varsayılmıştır` : ""}.
    ÇAP'a devam ve başvuru eşikleri ise her dönem ve başvuru anında ayrıca sağlanmalıdır.`;
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
    <b>tamamlanmış sayılır</b>; şart, mezuniyette genel ortalamanın
    <b class="mono">${r.minGpa.toFixed(2)}</b> düzeyine ulaşmış olmasıdır
    (${esc(r.source || "MADDE 31")}). ${r.ok === false
      ? `<b style="color:var(--danger)">Mevcut ortalama bu değerin altındadır.</b>`
      : `Mevcut durumda bu şart karşılanmaktadır.`} `;
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
    : saatsizYazi(secs[0], "kisa");
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
            ? ` role="button" tabindex="0" title="Programa eklemek için tıklayınız"`
            : ` title="Aday havuzunda değildir; bilgi amaçlıdır"`}>
        <div><b class="mono">${esc(k.code)}</b>
          ${k.name ? `<span class="denkad">${esc(k.name)}</span>` : ""}
          ${k.sections.some(x => x.online) ? `<span class="chip online"
            style="margin-left:6px">çevrimiçi</span>` : ""}${
          /* ★ Faz 111 — şube bölümünüze açıksa dilekçe gerekmiyor. */
          k.dilekcesiz ? `<span class="chip prereq" style="margin-left:6px"
            title="Şube, OBS'de programlarınızın (anadal veya ÇAP/yandal) alabileceği şube olarak listelenmiştir${
              k.dilekcesizCrn.length < k.sections.length
                ? ": CRN " + esc(k.dilekcesizCrn.join(", ")) : ""}">dilekçesiz</span>` : ""}</div>
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
          açılmamıştır; denkliğin tamamlanması için bu ders de gereklidir.`
        : (alinmis.length ? "Bu açık ders de alındığında denklik tamamlanır." : "")}</div>`;
    }
    /* Köken çerçevesi: resmi = OBS + dilekçe; beyan = kendi bildirdiğin. */
    if (!e.declared) {
      /* ★ Faz 111 — şubesi bölümünüze açık kaynak dilekçesiz alınıyor. */
      const serbest = acik.filter(k => k.dilekcesiz);
      const onay = e.confidence === "requires_approval"
        ? "bölüm/yönetim kurulu onayı gerekebilir"
        : serbest.length === acik.length && acik.length
          ? "şubesi programınıza açık olduğundan <b>dilekçe gerekmez</b>"
          : serbest.length
            ? `<b>${serbest.map(k => esc(k.code)).join(", ")}</b> şubesi programınıza açık
               olduğundan dilekçesiz alınabilir, diğerleri dilekçeyle saydırılır`
            : "dilekçeyle saydırılır";
      not += `<div class="denknot">OBS resmî ders denkliği${
        capraz ? " — <b>başka bölümden</b>" : ""}; ${onay}. Danışmanınızla doğrulayınız.</div>`;
    }
    /* Başlık: OR ise "birini al", tek/AND ise "denkliği açık". */
    const baslik = e.mode === "or"
      ? (acik.length > 1 ? "— yerine şu açık derslerden <b>biri</b> alınabilir:"
                         : "— yerine bu açık ders alınabilir:")
      : "— denkliği açık:";
    return `<div class="denkrow">
      <div class="denkhedef">
        <span class="tag ${e.needed ? "CAP" : "unknown"}">${e.needed
          ? "gereken" : "beyan"}</span>
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
      ? "Karşılaştırma için en az iki veri tazelemesi gereklidir."
      : "Karşılaştırma verisi yok.";
    $("#changeBody").innerHTML = "";
    return;
  }
  $("#changeWhen").textContent =
    `${tarihYaz(c.since)} → ${tarihYaz(c.until)} · yalnızca ilgili dersler`;
  const group = (title, cls, items, line) => items.length ? `
    <div class="chipline"><span class="chip ${cls}">${title}</span>
      <span style="color:var(--ink-3);font-size:var(--fs-md)">${items.length}</span></div>
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
    `<div class="empty">İlgili derslerde değişiklik bulunmamaktadır.</div>`;
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
      <span style="color:var(--ink-3);font-size:var(--fs-md)">${eq.length}</span></div>
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
      <span style="color:var(--ink-3);font-size:var(--fs-md)">${group.length}</span></div>${
      /* ★ Faz 108 — kredisi ya da AKTS'si farklı ders çoğunlukla denk sayılmaz
         (kullanıcı 27.09.2026). Düğme kalıyor (karar öğrencinin) ama
         uygulamadan önce neye bakılacağı yazıyor. */
      level === "dusuk" ? `<div class="modenote" style="margin:4px 0 6px">Kredisi, AKTS'si ya da
        dili farklı dersler çoğunlukla denk sayılmaz. Uygulamadan önce
        ${disLink("obsDenklik", "İTÜ'nün resmî denklik listesine")} bakınız ya da
        danışmanınıza sorunuz.</div>` : ""}
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
      <button class="ghost primary" id="eqAll">Yüksek güvenli ${high.length}
        eşleşmenin tümünü uygula</button></div>`;
  }
  html += `<div class="modenote" style="margin-top:10px">Uygulanan denklikler
    <span class="mono">config/denklikler.toml</span> dosyasına yazılır; bu
    dosyada görüntülenebilir ve silinebilir.</div>`;
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
  sec.hidden = !saved.length && !(DATA.alternatives || []).length;
  renderAlternatifler();                     // Faz 77
  if(!saved.length){
    $("#savedWhen").textContent = "Ana program kaydedilmemiştir; alternatif programlar aşağıdadır.";
    $("#savedList").innerHTML = ""; $("#savedActions").innerHTML = "";
    return;
  }

  const when = (DATA.savedPicks.savedAt || "").replace("T", " ").slice(0, 16);
  $("#savedWhen").textContent = (when ? when + " tarihinde kaydedildi" : "kaydedildi")
    + (donemYazi() ? " · " + donemYazi() : "");

  let kredi = 0, akts = 0, eksik = 0;
  const kart = saved.map(p => {
    const hit = findSection(p.course, p.crn);
    if(!hit){ eksik++; return `<div class="savedcard">
      <b class="mono">${esc(p.course)}</b><span class="crn mono">${esc(p.crn)}</span>
      <div class="miss">şube bu dönemin verisinde bulunmamaktadır</div></div>`; }
    kredi += hit.cand.credits || 0; akts += hit.cand.ects || 0;
    const saat = (hit.sec.meetings || []).map(m =>
      `${DAYS[m.day-1] || "?"} ${hhmm(m.start)}`).join(" · ") || saatsizYazi(hit.sec);
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
      <h2 style="margin-bottom:4px">Kaydedilen CRN'ler</h2>
      <p class="modenote" style="margin:2px 0 10px">Ders kaydı sırasında
        ${disLink("kepler")} sistemindeki “Ders Kayıt İşlemleri” ekranına girilecek
        numaralar. Araç, ders kaydı işlemini sizin adınıza yapmaz.</p>
      <label class="field"><span>Tümü (kopyala)</span>
        <input type="text" class="mono" readonly value="${esc(line)}"></label>
      `);
  });
}

/* ★★ FAZ 77 — ALTERNATİF PROGRAMLAR (Plan B, Plan C…).
   Kayıt gününde bir şube dolunca çoğu zaman tek ders değil bütün program
   değişiyor (çakışmalar zincirleniyor). Öğrenci birkaç TAM program
   hazırlamak istiyor; araç yalnız bir tane saklıyordu. Ana program
   (`savedPicks`) aynen duruyor; alternatifler adlarıyla, aynı dönem
   anahtarıyla kullanıcı veritabanında (`saved_alt`). Her alternatifin tek
   satırlık özeti karşılaştırma için: ders, kredi, kampüs günü, saat
   aralığı, çakışma ve dolu şube — bunlar ELDEKİ veriyle hesaplanıyor;
   şubesi artık bulunmayan ders "bulunamadı" diye sayılıyor. */
const ALT_ONERI = ["Plan B", "Plan C", "Plan D", "Plan E", "Plan F", "Plan G"];
function altOzet(liste){
  const hits = liste.map(p => ({p, hit: findSection(p.course, p.crn)}));
  const var_ = hits.filter(x => x.hit);
  const kredi = +var_.reduce((a, x) => a + (x.hit.cand.credits || 0), 0).toFixed(1);
  const gun = new Set();
  let ilk = Infinity, son = -Infinity;
  var_.forEach(x => {
    if(x.hit.sec.online) return;
    (x.hit.sec.meetings || []).forEach(m => {
      gun.add(m.day); ilk = Math.min(ilk, m.start); son = Math.max(son, m.end);
    });
  });
  const carpisan = [];
  var_.forEach((a, i) => var_.slice(i + 1).forEach(b => {
    if(clash(a.hit.sec, b.hit.sec)) carpisan.push(`${a.p.course} ↔ ${b.p.course}`);
  }));
  return {n: liste.length, kredi, eksik: hits.length - var_.length,
          gun: [...gun].sort((a, b) => a - b), ilk, son, carpisan,
          dolu: var_.filter(x => x.hit.sec.capacity && yerSayisi(x.hit.sec) === 0)
                    .map(x => x.p.course)};
}
const programAnahtari = (liste) => liste.map(p => p.course + "@" + p.crn).sort().join("|");
function altYukle(a){
  const i = modeIndexFor(a.picks);
  if(i >= 0 && i !== mode) useMode(i);
  geriKaydet(`${a.name} yüklendi`);
  sel = a.picks.map(p => ({course: p.course, crn: p.crn})).filter(p => sectionOf(p.course, p.crn));
  render();
  gorunumAc("schedSection", true);
}
function renderAlternatifler(){
  const kutu = $("#altList");
  if(!kutu) return;
  const alts = DATA.alternatives || [];
  if(!alts.length){ kutu.innerHTML = ""; return; }
  const simdi = currentKey();
  kutu.innerHTML = `<div class="altbaslik"><h3>Alternatif programlar</h3>
      <span class="meta">${alts.length} / ${DATA.alternativesMax || alts.length}</span>
      <button class="ghost mini" id="altKarsilastir">Yan yana karşılaştır</button></div>
    ${alts.map((a, i) => {
      const o = altOzet(a.picks);
      const when = (a.savedAt || "").replace("T", " ").slice(0, 16);
      return `<div class="altsatir">
        <div class="altad"><b>${esc(a.name)}</b>${programAnahtari(a.picks) === simdi
          ? ` <span class="chip credit">ızgarada</span>` : ""}
          <span class="meta">${esc(when)}</span></div>
        <div class="altozet">${o.n} ders · <b class="mono">${o.kredi}</b> kredi${o.gun.length
          ? ` · ${o.gun.length} gün kampüste (${o.gun.map(d => DAYS[d - 1]).join(" ")})
             · <span class="mono">${hhmm(o.ilk)}–${hhmm(o.son)}</span>` : ""}${o.carpisan.length
          ? ` · <span class="uyari">çakışma: ${o.carpisan.map(esc).join(", ")}</span>` : ""}${o.dolu.length
          ? ` · <span class="uyari">dolu: ${o.dolu.map(esc).join(", ")}</span>` : ""}${o.eksik
          ? ` · <span class="uyari">${o.eksik} şube bu dönemin verisinde bulunamadı</span>` : ""}</div>
        <div class="altdugmeler">
          <button class="ghost mini" data-altyukle="${i}">Programa yükle</button>
          <button class="ghost mini" data-altcrn="${i}">CRN'ler</button>
          ${LIVE ? `<button class="ghost mini" data-altsil="${i}">Sil</button>` : ""}</div>
      </div>`;
    }).join("")}`;
  const kk = $("#altKarsilastir");
  if(kk) kk.addEventListener("click", karsilastirDialog);
  kutu.querySelectorAll("[data-altyukle]").forEach(b =>
    b.addEventListener("click", () => altYukle(alts[+b.dataset.altyukle])));
  kutu.querySelectorAll("[data-altcrn]").forEach(b => b.addEventListener("click", () => {
    const a = alts[+b.dataset.altcrn];
    openDialog(`<div class="eyebrow">Kayıt günü</div>
      <h2 style="margin-bottom:4px">${esc(a.name)} — CRN'ler</h2>
      <p class="modenote" style="margin:2px 0 10px">${disLink("kepler")} “Ders Kayıt
        İşlemleri” ekranına girilecek numaralar.</p>
      <label class="field"><span>Tümü (kopyala)</span>
        <input type="text" class="mono" readonly value="${esc(a.picks.map(p => p.crn).join(" "))}"></label>`);
  }));
  /* Silme geri alınamıyor: ilk dokunuş sorar, ikincisi siler. */
  kutu.querySelectorAll("[data-altsil]").forEach(b => b.addEventListener("click", async () => {
    const a = alts[+b.dataset.altsil];
    if(b.dataset.onay !== "1"){
      b.dataset.onay = "1"; b.textContent = `“${a.name}” silinsin mi? Onaylayınız`; return;
    }
    const geri = dugmeMesgul(b, "Siliniyor…");
    try{ applyState(await api("/api/alternatif/sil", {name: a.name}), {koru: true}); }
    catch(err){ geri(); hataBildir(b, err); }
  }));
}
function altKaydetDialog(){
  if(!sel.length) return;
  const alts = DATA.alternatives || [];
  const adlar = alts.map(a => a.name);
  const oneri = ALT_ONERI.find(x => !adlar.includes(x)) || "";
  openDialog(`<div class="eyebrow">Alternatif program</div>
    <h2 style="margin-bottom:4px">Alternatif olarak kaydet</h2>
    <p class="modenote" style="margin:2px 0 10px">Izgaradaki program
      (<b class="mono">${sel.length}</b> ders) adıyla saklanır; ana kaydedilen program
      değişmez. Kayıt gününde bir şube dolduğunda alternatife tek dokunuşla geçilebilir
      ve CRN'leri “Kayıt günü” penceresinde de listelenir. En çok
      <b>${DATA.alternativesMax || 5}</b> alternatif kaydedilebilir.</p>
    <label class="field"><span>Ad</span>
      <input type="text" id="altAd" maxlength="40" value="${esc(oneri)}"></label>
    ${adlar.length ? `<div class="hint">Kayıtlı: ${adlar.map(esc).join(", ")} — aynı ad
      yazılırsa o alternatifin üzerine kaydedilir.</div>` : ""}
    <div style="margin-top:10px"><button class="ghost primary" id="altKaydetOk">Kaydet</button>
      <span class="hint" id="altDurum" role="status"></span></div>`);
  const ok = $("#altKaydetOk");
  ok.addEventListener("click", async () => {
    const geri = dugmeMesgul(ok, "Kaydediliyor…");
    await bekleBoyansin();
    try{
      applyState(await api("/api/alternatif", {name: $("#altAd").value, picks: sel}), {koru: true});
      $("#detail").close();
    }catch(err){
      geri(); $("#altDurum").textContent = err.message || String(err);
    }
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
  const alt = $("#altKaydet");                 // Faz 77
  if(alt) alt.hidden = !LIVE || !sel.length;
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
  const alt = $("#altKaydet");
  if(alt && LIVE) alt.onclick = altKaydetDialog;
  const crn = $("#crnBtn");
  if(crn) crn.onclick = crnDialog;
  const yukle = $("#crnLoad");
  if(yukle) yukle.onclick = crnLoadDialog;
  const ics = $("#icsBtn");
  if(ics) ics.onclick = icsIndir;
  const png = $("#pngBtn");
  if(png) png.onclick = () => resimIndir().catch(err => hataBildir(png, err));
  const dan = $("#danismanBtn");
  if(dan) dan.onclick = danismanDialog;
  const pay = $("#shareBtn");
  if(pay) pay.onclick = paylasDialog;
}

function paylasDialog(){
  const url = paylasBaglantisi();
  if(!url){ openDialog(`<div class="empty">Programda ders bulunmamaktadır.</div>`); return; }
  openDialog(`
    <div class="eyebrow">Paylaş</div>
    <h2 style="margin-bottom:4px">Program bağlantısı</h2>
    <p class="modenote" style="margin:2px 0 10px">Bağlantı <b>yalnızca CRN'leri</b>
      içerir. Notlarınız, transkriptiniz ve bölüm bilginiz <b>bağlantıya eklenmez</b>;
      bağlantıyı açan kişi yalnızca haftalık programı görür.</p>
    <label class="field"><span>Kopyala</span>
      <input type="text" id="shareUrl" class="mono" readonly value="${esc(url)}">
      <span class="hint" id="shareCopied">Tıklandığında seçilir.</span></label>`);
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
    <p class="modenote" style="margin:2px 0 10px">Kepler'de kayıt yapıldıysa kayıtlı
      derslerin CRN'leri buraya yapıştırılarak kesinleşen program ızgarada
      görüntülenebilir. Bu işlem yalnızca <b>görüntüleme</b> amaçlıdır; araç Kepler'e
      veya OBS'ye veri göndermez.</p>
    <label class="field"><span>CRN'ler (boşluk, virgül veya satır ile ayrılmış)</span>
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
                  `bu dönemin verisinde bulunamadı: ${eksik.join(", ")}`);
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
                 sinav: x.sinav || null,                       /* Faz 111 */
                 meetings: (x.meetings || []).map(m => ({
                   day: m.day, start: m.start, end: m.end,
                   building: m.building, room: m.room || "", campus: m.campus}))};
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
              pool: "", score: 0, opens: [], denkOf: x.denkOf || "",
              reasons: [x.role === "PLAN_DISI"
                        ? "plan dışı; hiçbir şartı karşılamaz"
                        : x.denkOf ? `${x.denkOf} yerine (resmî denklik)` : "CRN ile eklendi"],
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
      <p class="modenote">Katalog araması için uygulamayı <span class="mono">make app</span>
        ile başlatınız.</p>`);
    return;
  }
  openDialog(`
    <div class="eyebrow">Katalog</div>
    <h2 style="margin-bottom:4px">Ders ara ve programa ekle</h2>
    <p class="modenote" style="margin:2px 0 10px">Planda bulunmayan dersler de
      eklenebilir; bu dersler <b>plan dışı</b> olarak işaretlenir. Kredileri dönem
      yüküne ve çakışma denetimine <b>dahil edilir</b>, ancak hiçbir plan şartını
      <b>karşılamaz</b>.</p>
    <label class="field"><span>Kod veya ad</span>
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
    ilan etmiştir; mevcut krediniz ${c.earned}.">${floor} kredi gerekir</span>`;
}

function katalogCiz(k){
  const items = k.items || [];
  if(!items.length){
    $("#katSonuc").innerHTML = `<div class="empty">${esc(k.note
      || "açık şubesi olan eşleşen ders bulunamadı")}</div>`;
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
      items.length} sonuç gösterilmektedir; daha fazla sonuç için aramayı daraltınız.</div>` : ""}`;
  $("#katSonuc").querySelectorAll("[data-kat]").forEach(b =>
    b.addEventListener("click", () => katalogEkle(b.dataset.kat)));
}

async function katalogEkle(course){
  $("#katSonuc").innerHTML = `<div class="empty">şubeler getiriliyor…</div>`;
  try{
    const r = await api("/api/ders", {course});
    const bulunan = (r.crn || {}).found || [];
    if(!bulunan.length){
      $("#katSonuc").innerHTML = `<div class="empty">bu dersin açık şubesi bulunmamaktadır</div>`;
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
  let saatsiz = 0, sinavli = 0;
  picks().forEach(p => {
    if(!p.sec.meetings.length){ p.sec.sinav ? sinavli++ : saatsiz++; return; }
    p.sec.meetings.forEach((m, i) => {
      const ad = `${p.cand.course}${p.cand.name ? " — " + p.cand.name : ""}`;
      sat.push("BEGIN:VEVENT",
        `UID:${p.sec.crn}-${m.day}-${m.start}-${i}@itucap`,
        `DTSTART:${icsTarih(m.day, m.start, 0)}`,
        `DTEND:${icsTarih(m.day, m.end, 0)}`,
        `RRULE:FREQ=WEEKLY;COUNT=${ICS_HAFTA};BYDAY=${ICS_GUN[m.day-1] || "MO"}`,
        `SUMMARY:${icsKacis(ad)}`,
        `LOCATION:${icsKacis(yerTakvim(m))}`,
        /* ⚠️ Satır sonu BURADA gerçek satır sonu; `\n` kaçışını `icsKacis`
           yapıyor. Elle kaçırırsak ters bölü ikinci kez kaçırılıyor ve
           takvim uygulamasında "\\n" diye görünüyor (ölçüldü). */
        `DESCRIPTION:${icsKacis(
          `CRN ${p.sec.crn}${p.sec.instructor ? " · " + p.sec.instructor : ""}` +
          "\n" +
          `Tarihler tahminidir: akademik takvim bu araçta bulunmadığından ` +
          `başlangıç olarak önümüzdeki pazartesi alınmıştır. Lütfen dönem başına göre düzenleyiniz.`)}`,
        "END:VEVENT");
    });
  });
  sat.push("END:VCALENDAR");
  return {metin: sat.join("\r\n"), saatsiz, sinavli};
}

const icsKacis = (s) => String(s ?? "")
  .replace(/\\/g, "\\\\").replace(/;/g, "\\;").replace(/,/g, "\\,")
  .replace(/\n/g, "\\n");

function icsIndir(){
  const {metin, saatsiz, sinavli} = icsMetni();
  const blob = new Blob([metin], {type: "text/calendar;charset=utf-8"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "ders-programi.ics";
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 5000);
  if(saatsiz) alertLine(
    `${saatsiz} dersin saati ilan edilmediğinden takvim dosyasına eklenmemiştir.`);
  /* Faz 111 — ek sınav şubesinin ders saati yok; sınav tarihi OBS'de ilan edilir. */
  if(sinavli) alertLine(
    `${sinavli} ek sınav şubesinin ders saati olmadığından takvim dosyasına eklenmemiştir.`);
}

/* ---------- ★★ FAZ 61 — DANIŞMAN ÖZETİ ----------
   İTÜ'de ders kaydı danışman onayıyla bitiyor. Öğrenci görüşmeye ne
   götüreceğini beş ayrı görünümden (program, kredi, yol haritası, darboğaz,
   başvuru) kendisi topluyordu. Burada tek sayfa: durum, bu dönemin programı
   CRN'leriyle, mevzuat kontrolleri, tahmini bitiş ve — asıl işe yarayan —
   KENDİLİĞİNDEN ÇIKAN SORULAR: yalnız ölçülen sorunlardan (taban eksiği,
   yük aşımı, dolu şube, gecikme, yerleşmeyen ders, tutmayan eşik…).
   ⚠️ GNO içeriyor — resimden (Faz 58) farkı bu: danışman zaten transkripti
   görüyor. Sayfa bunu yazıyor. Hesaplar görünümlerle AYNI yardımcılardan
   (`tabanDurumu`, `totals`, `picks`); özet kendi hesabını yapmıyor. */
const buyukBas = (m) => m ? m.charAt(0).toLocaleUpperCase("tr") + m.slice(1) : m;
/* ★★ Faz 112 — YALNIZ DİLEKÇE GEREKTİRENLER (kullanıcı 28.09.2026: "danışman
   özeti kısmında da dilekçe dışında danışmana sorulacak diye yazdığın
   şeyleri çıkarabilirsin"). Eskiden ~20 kaynaktan soru üretiliyordu (bitiş
   gecikmesi, GNO eşikleri, zor dersler, kalma riski, saat…); bunlar
   görünümlerde zaten var. Burada yalnız danışman görüşmesinde DİLEKÇEYLE
   yapılacak işler kalıyor: yük sınırı, ÇAP tabanı indirimi, dolu şubeye
   kontenjan, denklikle saydırma. */
function danismanSorulari(){
  const q = [], F = DATA.secondFloor, t = totals();
  if(DATA.maxLoad && t.load > DATA.maxLoad)
    q.push(`Programım <b>${t.load}</b> ${esc(DATA.unitLabel)} olup ${DATA.maxLoad} sınırını
      aşmaktadır; sınırın üzerinde ders alabilmek için dilekçe gerekir.`);
  if(F && !F.undeclared && F.relief){
    const d = tabanDurumu(F);
    if(!d.ok) q.push(`İkinci anadaldan bu dönem <b>${d.kredi}</b> kredi alıyorum; yarıyıl
      tabanı ${F.min} kredidir (<b>${d.eksik}</b> kredi eksik). Tabanın ${F.relief.min}
      krediye indirilmesi için dilekçe verilebilir.`);
  }
  /* ★★ Faz 90 — dolu şubeler TEK maddede; programla çakışmayan BOŞ şubesi
     olan ders dilekçe değil, tek dokunuşla çözülüyor (bosSube). */
  const doluSube = picks().filter(p => p.sec.capacity && yerSayisi(p.sec) === 0 && !bosSube(p.cand.course));
  if(doluSube.length) q.push(`${doluSube.map(p => `<b class="mono">${esc(p.cand.course)}</b>
      (CRN ${esc(p.sec.crn)})`).join(", ")} ${doluSube.length > 1 ? "şubelerimin" : "şubemin"}
    kontenjanı doludur ve programımla çakışmayan boş şube bulunmamaktadır; kontenjan
    açılması için dilekçe verilebilir.`);
  /* ★ Faz 111/112 — programdaki ders, gereken bir dersin resmî denkliğiyse ve
     şubesi bölümüne açık DEĞİLSE saydırmak için dilekçe gerekiyor. */
  const secili = new Set(picks().map(p => p.cand.course));
  (DATA.openEquivalents || []).filter(e => !e.declared && e.needed).forEach(e =>
    e.sources.filter(k => secili.has(k.code) && k.open && !k.passed && !k.dilekcesiz)
      .forEach(k => q.push(`<b class="mono">${esc(k.code)}</b> dersini
        <b class="mono">${esc(e.target)}</b> yerine saydırmak için denklik dilekçesi
        verilmelidir${e.confidence === "requires_approval"
          ? " (bölüm/yönetim kurulu onayı gerekebilir)" : ""}.`)));
  return q;
}

function danismanOzeti(){
  const t = totals(), R = DATA.roadmap, g = DATA.gpa, F = DATA.secondFloor;
  const ikinci = SECONDS().map(x => `${esc(x.label)} ${esc(x.program)}`).join(" · ");
  const saat = p => p.sec.meetings.length ? p.sec.meetings.map(m =>
    `${DAYS[m.day - 1]} ${hhmm(m.start)}–${hhmm(m.end)}`).join(", ") : "saat yok";
  const satirlar = picks().map(p => `<tr><td class="mono"><b>${esc(p.cand.course)}</b></td>
    <td>${esc(p.cand.name)}</td><td>${esc(p.cand.role === "PLAN_DISI" ? "plan dışı" : p.cand.role)}</td>
    <td class="mono">${p.cand.credits}</td><td class="mono">${esc(p.sec.crn)}${
      p.sec.capacity && yerSayisi(p.sec) === 0 ? ` <span class="uyari">dolu</span>${
        (b => b ? `<div class="meta">boş şube: ${esc(b.crn)}</div>` : "")(bosSube(p.cand.course))}` : ""}</td>
    <td>${saat(p)}</td><td>${(z => z ? `${esc(z.label)} <span class="mono">${zp(z.score)}</span>`
      : "—")(zorlukOf(p.cand))}</td></tr>`).join("");
  const kontrol = [];
  if(DATA.maxLoad) kontrol.push(`Dönem yükü <b class="mono">${t.load} / ${DATA.maxLoad}</b>
    ${esc(DATA.unitLabel)} ${t.load > DATA.maxLoad ? "— <b>sınır aşıldı</b>" : "✓"}`);
  if(F && !F.undeclared){
    const d = tabanDurumu(F);
    kontrol.push(`ÇAP yarıyıl tabanı <b class="mono">${d.kredi} / ${F.min}</b> ${d.ok ? "✓" : "— <b>eksik</b>"}`);
  }
  if(g && g.counted) kontrol.push(`GNO (tahmini) <b class="mono">${g.value.toFixed(2)}</b> ·
    <span class="mono">${g.credits}</span> kredi`);
  const pz = programZorlugu(picks().map(p => p.cand));                // Faz 89
  /* Faz 100 — dönem zorluğu ders sayısı ve krediyle artıyor. */
  if(pz.ort !== null) kontrol.push(`Tahmini dönem zorluğu <b class="mono">${zp(pz.donem)}</b> / 10
    (${ZORLUK_AD[pz.donemKademe]}; ${pz.ders} ders, ${pz.akts} AKTS; geçmiş not dağılımından) ·
    ders ortalaması <span class="mono">${zp(pz.ort)}</span> · ${pz.zor ? `<b>${pz.zor}</b> zor ders` : "zor ders yok"}${
    pz.yok ? ` · ${pz.yok} ders için veri yok` : ""}`);
  const bitis = R && !R.error && !R.noTranscript ? (R.programs || []).map(p => `<li><b>${esc(buyukBas(p.label))}</b>:
    ${p.finish ? `${esc(p.finish.label)}${p.finishSemester ? ` (${p.finishSemester}. yarıyıl)` : ""}`
      : p.jointDegree ? `tahmin edilmedi — ortak program (${esc(p.jointDegree)})` : "hesaplanamadı"}${p.nominal && p.finish ? (p.finish.index > p.nominal.index
      ? ` — plandakinden ${p.finish.index - p.nominal.index} dönem geç` : " — plandakiyle aynı") : ""}</li>`)
    .join("") : "";
  const sorular = danismanSorulari();
  return `<div class="dozet">
    <div class="eyebrow">Danışman görüşmesi · ${esc(DATA.termLabel || "")}</div>
    <h2>Danışman özeti</h2>
    <div class="meta">Anadal <b>${esc(DATA.anadal || "")}</b>${ikinci ? " · " + ikinci : ""}${
      DATA.donem ? ` · <b>${DATA.donem}.</b> yarıyıl` : ""} · hazırlandı
      ${esc(tarihYaz(new Date().toISOString()))}</div>
    <h3>Bu dönemin programı</h3>
    ${satirlar ? `<table><thead><tr><th>Ders</th><th>Ad</th><th>Program</th><th>Kr</th>
      <th>CRN</th><th>Saat</th><th>Tahmini zorluk</th></tr></thead><tbody>${satirlar}</tbody></table>`
      : `<div class="empty">Programda ders bulunmamaktadır.</div>`}
    <h3>Kontroller</h3><ul>${kontrol.map(k => `<li>${k}</li>`).join("")}</ul>
    ${bitis ? `<h3>Tahmini bitiş</h3><ul>${bitis}</ul>` : ""}
    <h3>Dilekçe gerektirenler</h3>
    ${sorular.length ? `<ul class="dsoru">${sorular.map(x => `<li>${x}</li>`).join("")}</ul>`
      : `<div class="meta">Dilekçe gerektiren bir durum bulunmamaktadır.</div>`}
    <div class="dnot">GNO ve bitiş bilgileri tahminidir (transkript ve yol haritası
      varsayımlarına dayanır). Kesin bilgi için OBS esas alınmalıdır. ⚠️ Bu sayfa GNO
      bilgisini içerir; yalnızca danışmanınızla paylaşınız. __AD_TAM__ ile hazırlanmıştır;
      ${esc(veriYasiMetni())}.</div>
  </div>`;
}

function danismanDialog(){
  const html = danismanOzeti();
  openDialog(html + `<div style="margin-top:12px">
    <button class="ghost primary" id="ozetYazdir">Yazdır</button></div>`);
  $("#ozetYazdir").addEventListener("click", () => {
    /* Baskı kuralı body'nin DOĞRUDAN çocuklarını gizliyor; kap bir
       sarmalayıcının içinde kalırsa sayfa BOŞ basılıyordu (ölçüldü). */
    const kab = $("#ozetBaski");
    if(kab.parentElement !== document.body) document.body.appendChild(kab);
    kab.innerHTML = html;
    document.body.classList.add("ozetbaski");
    $("#detail").close();
    const bitti = () => { document.body.classList.remove("ozetbaski"); kab.innerHTML = "";
                          removeEventListener("afterprint", bitti); };
    addEventListener("afterprint", bitti);
    window.print();
  });
}

/* ---------- ★★ FAZ 58 — PROGRAMIN RESMİ (PNG) ----------
   Ders programı kurucularının (Coursicle, Schedule Builder) en çok
   paylaşılan çıktısı haftanın resmi; bizde bağlantı ve `.ics` vardı, resim
   yoktu — öğrenci ekran görüntüsü alıp kırpıyordu (telefonda ızgara zaten
   gün listesine dönüyor, resim hiç çıkmıyordu).
   `<canvas>`a tarayıcıda çiziliyor; dış kütüphane yok (gizlilik denetimi
   dış kaynağı reddediyor), hiçbir yere gönderilmiyor.
   Renkler SAYFANIN: jetonlar `:root`tan, blok zemini ve yazısı ızgaradaki
   bloğun HESAPLANMIŞ renginden (ton merdiveni dahil) — resim ekrandaki
   temayla aynı. ⚠️ İçinde yalnız ders, şube, saat ve bina var; not,
   transkript, GNO YOK. */
async function resimIndir(){
  const ps = picks();
  if(!ps.length){ alertLine("Programda ders bulunmadığından resim oluşturulmadı."); return; }
  if(document.fonts && document.fonts.ready) await document.fonts.ready;
  const kok = getComputedStyle(document.documentElement);
  const j = (ad) => kok.getPropertyValue("--" + ad).trim();
  const SANS = j("font-sans") || "sans-serif", MONO = j("font-mono") || "monospace";
  const mesgul = (DATA.busy || []).filter(b => b.ok);
  const saatli = ps.filter(p => p.sec.meetings.length);
  const saatsiz = ps.filter(p => !p.sec.meetings.length);
  const dk = [...saatli.flatMap(p => p.sec.meetings), ...mesgul];
  const bas = Math.floor(Math.min(...dk.map(m => m.start), 8 * 60 + 30) / 60) * 60;
  const son = Math.ceil(Math.max(...dk.map(m => m.end), 12 * 60) / 60) * 60;
  const O = 2, G = 1100, SOL = 56, UST = 92, GUN_UST = 28, DK = 1.1, PAY = 16;
  const altSatir = (saatsiz.length ? 22 : 0) + 40;
  const Y = UST + GUN_UST + (son - bas) * DK + altSatir;
  const tuval = document.createElement("canvas");
  tuval.width = G * O; tuval.height = Math.ceil(Y) * O;
  const c = tuval.getContext("2d");
  c.scale(O, O);
  c.fillStyle = j("ground"); c.fillRect(0, 0, G, Y);
  const yaz = (metin, x, y, font, renk, genislik) => {
    c.font = font; c.fillStyle = renk;
    let m = String(metin);
    if(genislik) while(m.length > 1 && c.measureText(m).width > genislik) m = m.slice(0, -2) + "…";
    c.fillText(m, x, y);
  };
  const t = totals();
  yaz("Haftalık ders programı", PAY, 34, `700 20px ${SANS}`, j("ink"));
  yaz(`${DATA.termLabel || ""} · ${t.n} ders · ${t.load}${DATA.maxLoad ? " / " + DATA.maxLoad : ""} ${
      DATA.unitLabel || ""}`, PAY, 58, `400 13px ${SANS}`, j("ink-2"));
  /* Ad yer tutucudan (bkz. test_ad.py — ad değişince sayfada eski ad kalmasın). */
  yaz("__AD_TAM__ — CRN'leri kayıttan önce OBS'de doğrulayınız", PAY, 78,
      `400 11px ${SANS}`, j("ink-3"));
  const sw = (G - SOL - PAY) / 5;
  const x0 = (gun) => SOL + (gun - 1) * sw;
  const y0 = (dak) => UST + GUN_UST + (dak - bas) * DK;
  c.strokeStyle = j("border"); c.lineWidth = 1;
  DAYS.forEach((d, i) => yaz(d, x0(i + 1) + 6, UST + 18, `600 12px ${SANS}`, j("ink-2")));
  for(let m = bas; m <= son; m += 60){
    c.beginPath(); c.moveTo(SOL, y0(m) + .5); c.lineTo(G - PAY, y0(m) + .5); c.stroke();
    if(m < son) yaz(hhmm(m), PAY, y0(m) + 12, `400 11px ${MONO}`, j("ink-3"));
  }
  for(let d = 1; d <= 6; d++){
    const x = Math.round(x0(d)) + .5;
    c.beginPath(); c.moveTo(x, UST + GUN_UST); c.lineTo(x, y0(son)); c.stroke();
  }
  const kutu = (x, y, w, h, zemin, serit) => {
    c.fillStyle = zemin; c.fillRect(x, y, w, h);
    if(serit){ c.fillStyle = serit; c.fillRect(x, y, 3, h); }
  };
  mesgul.forEach(b => {
    const x = x0(b.day) + 2, y = y0(b.start) + 1, w = sw - 4, h = (b.end - b.start) * DK - 2;
    kutu(x, y, w, h, j("surface-2"));
    c.save(); c.beginPath(); c.rect(x, y, w, h); c.clip();
    c.strokeStyle = j("border");
    for(let k = -h; k < w; k += 10){ c.beginPath(); c.moveTo(x + k, y + h); c.lineTo(x + k + h, y); c.stroke(); }
    c.restore();
    yaz(b.label || "meşgul", x + 8, y + 16, `600 12px ${SANS}`, j("ink-2"), w - 12);
  });
  const rolRenk = {ANADAL: "anadal", CAP: "cap", YANDAL: "yandal"};
  saatli.forEach(p => {
    const blk = document.querySelector(`#grid .blk[data-course="${CSS.escape(p.cand.course)}"]`);
    const hs = blk ? getComputedStyle(blk) : null;
    const rol = rolRenk[p.cand.role];
    p.sec.meetings.forEach(m => {
      const x = x0(m.day) + 2, y = y0(m.start) + 1, w = sw - 4, h = (m.end - m.start) * DK - 2;
      /* Önce jeton (her tarayıcı okur), sonra bloğun hesaplanmış rengi:
         `color-mix()` sonucunu okuyamayan tarayıcıda atama sessizce
         düşer ve jeton kalır. */
      c.fillStyle = rol ? j(rol + "-soft") : j("surface-2");
      if(hs) c.fillStyle = hs.backgroundColor;
      const zemin = c.fillStyle;
      c.fillStyle = rol ? j(rol + "-ink") : j("ink");
      if(hs) c.fillStyle = hs.color;
      const yazi = c.fillStyle;
      kutu(x, y, w, h, zemin, rol ? j(rol) : j("ink-3"));
      c.save(); c.beginPath(); c.rect(x, y, w, h); c.clip();
      yaz(p.cand.course, x + 9, y + 16, `700 12px ${MONO}`, yazi, w - 14);
      if(h > 34) yaz(p.cand.name || "", x + 9, y + 31, `400 11px ${SANS}`, yazi, w - 14);
      if(h > 50) yaz(`CRN ${p.sec.crn} · ${p.sec.online ? "çevrimiçi" : yerYazi(m)}`,
                     x + 9, y + 46, `400 10px ${MONO}`, yazi, w - 14);
      c.restore();
    });
  });
  let ay = y0(son) + 24;
  if(saatsiz.length){
    yaz(`Saati olmayan: ${saatsiz.map(p => p.cand.course + " (CRN " + p.sec.crn
          + (p.sec.sinav ? ", " + p.sec.sinav.toLowerCase() : "") + ")").join(", ")}`,
        PAY, ay, `400 12px ${SANS}`, j("ink-2"), G - 2 * PAY);
    ay += 22;
  }
  yaz(`Oluşturuldu: ${tarihYaz(new Date().toISOString())} · kontenjan ve saatler değişebilir`,
      PAY, ay, `400 11px ${SANS}`, j("ink-3"));
  const blob = await new Promise(r => tuval.toBlob(r, "image/png"));
  if(!blob) throw new Error("tarayıcı resmi oluşturamadı");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "ders-programi.png";
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 5000);
  return {genislik: tuval.width, yukseklik: tuval.height};
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
      `Bağlantıdaki ${eksik.length} CRN katalogda bulunamadı: ${eksik.join(", ")}`);
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
  if(L.noTranscript || L.noGrades)
    ekle(null, "Kredi sınırı", L.noGrades
      ? "harf notu girilmediğinden sınır bilinmemektedir"
      : "transkript girilmediğinden sınır bilinmemektedir");
  else
    ekle(t.credits <= DATA.maxLoad + 1e-9, "Kredi sınırı",
         `${t.credits} / ${DATA.maxLoad} ${DATA.unitLabel}`);

  // 2) Çakışma — ızgaradaki kuralın AYNISI
  const carpisan = [];
  ps.forEach((a, i) => ps.slice(i + 1).forEach(b => {
    if(clash(a.sec, b.sec)) carpisan.push(`${a.cand.course} ↔ ${b.cand.course}`);
  }));
  ekle(!carpisan.length, "Saat çakışması", carpisan.join(", ") || "bulunmuyor");

  // 3) Kontenjan
  const doluOlan = ps.filter(p => !p.sec.free).map(p => p.cand.course);
  ekle(!doluOlan.length, "Kontenjan",
       doluOlan.length ? "dolu: " + doluOlan.join(", ")
                       : `${ps.length} şubede kontenjan mevcut (${esc(veriTarihi())} verisi;
                          kayıt sırasında OBS'deki güncel sayıyı kontrol ediniz)`);

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
         "ÇAP'a başlanan yarıyıl belirtilmediğinden taban değerlendirilmedi");
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
    <span class="hint">&#8220;—&#8221; işareti, koşulun bu araçla denetlenemediğini
      gösterir; koşulun sağlandığı anlamına gelmez. Kontenjan sayıları son veri
      tazelemesine aittir.</span></div>`;
}

function crnDialog(){
  const ps = picks();
  if(!ps.length){ openDialog(`<div class="empty">Programda ders bulunmamaktadır.</div>`); return; }
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
    <p class="modenote" style="margin:2px 0 10px">Ders kaydı ${disLink("kepler")}
      üzerinden, “Ders Kayıt İşlemleri” ekranına CRN girilerek yapılır. Araç, ders
      kaydını sizin adınıza yapmaz; bu liste kayıt ekranına elle girilmek üzere
      hazırlanmıştır. Kayıttan hemen önce güncel kontenjan ${disLink("obsProgram")}
      sayfasından kontrol edilebilir.</p>
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
                style="margin-left:6px">${esc(p.cand.role)}</span></td>
            <td class="meta mono">${p.sec.meetings.length
              ? p.sec.meetings.map(m => `${DAYS[m.day-1]} ${hhmm(m.start)}`).join(", ")
              : saatsizYazi(p.sec, "kisa")}</td>
            <td class="mono ${p.sec.free ? "" : "over"}">${p.sec.free}</td>
          </tr>`).join("")}</tbody>
        </table>
      </div>
    </div>
    ${alts.length ? `<details class="field"${
      /* Seçtiğin şubelerden biri doluysa yedek plan AÇIK gelsin — o an
         gerçekten lazım olan şey odur. */
      list.some(p => !p.sec.free) ? " open" : ""}>
      <summary style="cursor:pointer;font-size:var(--fs-md);color:var(--seal)"
        >Yedek plan — seçilen şubenin dolması durumunda</summary>
      <div class="scroll" style="max-height:240px">
        <table class="trtable"><tbody>${alts.map(a => `<tr>
          <td style="vertical-align:top"><b class="mono">${esc(a.course)}</b>
            <div class="meta mono">mevcut: ${esc(a.sec.crn)}</div></td>
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
      </div></details>` : ""}
    ${(DATA.alternatives || []).length ? `<details class="field"${
      list.some(p => !p.sec.free) ? " open" : ""}>
      <summary style="cursor:pointer;font-size:var(--fs-md);color:var(--seal)"
        >Alternatif programlar (${DATA.alternatives.length})</summary>
      ${DATA.alternatives.map(a => {
        const o = altOzet(a.picks);
        return `<label class="field"><span>${esc(a.name)} · ${o.n} ders · ${o.kredi} kredi${
          o.dolu.length ? ` · dolu: ${o.dolu.map(esc).join(", ")}` : ""}</span>
          <input type="text" class="mono" readonly value="${esc(a.picks.map(p => p.crn).join(" "))}"></label>`;
      }).join("")}</details>` : ""}`);
  const input = $("#crnLine");
  if(input){
    input.addEventListener("click", () => {
      input.select();
      try{ document.execCommand("copy"); $("#crnCopied").textContent = "kopyalandı ✓"; }
      catch(e){ $("#crnCopied").textContent = "seçildi; Cmd+C (Ctrl+C) ile kopyalayınız"; }
    });
    $("#crnCopied").textContent = "tıklandığında kopyalanır";
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
    if(not) not.textContent = "Katalog siteyle birlikte yayımlanır ve "
      + "dönem başında güncellenir.";
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
      : (n ? `${n} değişiklik bulundu` : "değişiklik bulunmadı");
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
    return `<div class="modenote" style="margin-top:6px">Katalogda bazı dersler
      için ayrıca <b>kredi koşulu</b> ilan edilmiştir (95 / 60 / 30 kredi).
      Hangi koşulların sağlandığı, transkript girildikten sonra görüntülenir.</div>`;
  if(!c.blocked || !c.blocked.length) return "";
  const GOSTER = 12;
  const rows = c.blocked.slice(0, GOSTER).map(b =>
    `<li><span class="mono">${esc(b.course)}</span> ${esc(b.name)} —
       en az <b class="mono">${b.min}</b> kredi,
       <b class="mono">${b.missing}</b> kredi eksik</li>`).join("");
  const fazla = c.blocked.length - GOSTER;
  return `<div class="note" style="margin-top:6px">
    Katalogda bu <b>${c.blocked.length}</b> ders için ayrıca kredi koşulu ilan edilmiştir;
    koşul şu anda <b>sağlanmadığından</b> bu dersler önerilere dahil edilmemiştir:
    <ul style="margin:6px 0 0 20px;padding:0">${rows}${
      fazla > 0 ? `<li>… ve ${fazla} ders daha</li>` : ""}</ul>
    <div style="margin-top:6px;color:var(--ink-3)">
      Kaynak: ${esc(c.source)}${c.verified ? ""
        : " · ⚠ bu alanın kaynaktaki adı “Sınıf Kısıtı”dır; kredi tabanı olarak"
          + " yorumlanmaktadır. Devre dışı bırakmak için"
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
      <div style="flex:2;min-width:240px;font-size:var(--fs-md);color:var(--ink-2)">
        <b>${esc(r.name)}</b> — ${esc(r.note)}
        ${r.holding && r.holding.length ? `<div style="margin-top:6px;color:var(--ink-3)">
          Bu koşula bağlı dersler: <span class="mono">${r.holding.map(esc).join(", ")}</span>
          (önerilere dahil edilmemiştir).</div>` : ""}
      </div>
    </div>`;
  }).join("") + (info.unknown && info.unknown.length
    ? `<div class="note" style="margin-top:6px">Kredisi katalogda bulunamayan
       <b>${info.unknown.length}</b> başarılı ders bulunmaktadır
       (<span class="mono">${info.unknown.slice(0,6).map(esc).join(", ")}</span>).
       Bu dersler <b>0 kredi</b> olarak sayıldığından eşiğe uzaklık olduğundan fazla görünebilir.</div>` : "")
    /* ★ Faz 37 — katalogda ders ders ilan edilmiş taban. Beyan edilmiş
       kuralın dışında kalan dersleri buraya yazmasak, motor onları eler ve
       kullanıcı sebebini hiçbir yerde göremezdi. */
    + catalogCreditHtml(info)
    + `<div class="modenote" style="margin-top:8px">Kural
       <span class="mono">config/kurallar.toml</span> dosyasında tanımlanır; mevzuat
       değiştiğinde yalnızca bu dosyanın güncellenmesi yeterlidir.</div>`;
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
          title="${bilinmiyor ? "Başarılan dersler girilmedi" : ""}"
          >${bilinmiyor ? "—" : "%" + p.percent}</div>
        ${bilinmiyor ? "" : `<div class="pctlbl">tamamlandı</div>`}
      </div>
    </div>
    <div class="name">${esc(p.title)}${p.url
      ? ` <span class="planlink">${disLink("obsPlan", "planı OBS'de görüntüle", p.url)}</span>`
      : p.source === "itu-helper"
        ? ` <span class="planlink">${disLink("ituHelperVeri", "plan kaynağı: İTÜ Helper")}</span>` : ""}</div>
    ${bilinmiyor ? `<div class="proj bilinmiyor">
      <b>İlerleme bilinmemektedir</b>; başarılan dersler girilmemiştir.
      Aşağıdaki sayılar kalan dersleri değil, <b>planın tamamını</b> göstermektedir.
      ${LIVE ? `<button class="ghost" data-setup="plan"
        style="margin-left:8px">Dersleri girin</button>` : ""}</div>` : `
    <div class="meter">
      <i style="width:${Math.max(1, p.percent)}%"></i>
      <i class="plan" style="width:${Math.max(0, pctAfter - p.percent)}%"></i>
    </div>`}
    ${bilinmiyor ? "" : `<div class="proj">${plan.slots
      ? `bu dönem <b class="mono">${plan.slots}</b> slot dolarsa
         <span class="mono">%${p.percent}</span> <span class="arrow">→</span>
         <b class="mono">%${pctAfter}</b>`
      : `<span class="flat">bu dönemki seçimde bu plandan ders bulunmamaktadır</span>`}</div>`}
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
    ${bilinmiyor ? "" : donemHTML(p)}
  </article>`;
}

/* ★★ Faz 99 — "İLERLEME DURUMU BİRAZ BOŞ KALDI" (kullanıcı 25.09.2026).
   Kart yüzde ve sayı veriyordu; HANGİ derslerin kaldığını, planın neresinde
   olunduğunu söylemiyordu. Şimdi: dönem şeridi (yalnız dönemleri belli
   planlarda — ÇAP/yandal planında `term_no` yok, uydurmuyoruz) ve kalan
   yuvaların listesi. Ders adına tıklanınca ders penceresi açılıyor; bu
   dönem seçili olan ders işaretli (seçim değişince kart yeniden çiziliyor).

   ⚠️ "Geride kalan" yalnız ANADAL kartında ve dönem biliniyorsa: `DATA.donem`
   anadal dönemi, ÇAP planının dönemleriyle karşılaştırılamaz. */
function donemHTML(p){
  const acik = p.open || [];
  const terms = p.terms || [];
  const donem = p.role === "ANADAL" ? (+DATA.donem || 0) : 0;
  const secili = new Set(picks().map(x => x.cand.course));
  const cip = (o) => {
    const ad = o.name ? `${o.label} — ${o.name}` : o.label;
    if(!o.required)
      return `<span class="kders havuz" title="Seçmeli yuva${o.term ? ` · ${o.term}. dönem` : ""}">${esc(o.label)}</span>`;
    const s = secili.has(o.code);
    const ic = `${s ? "✓ " : ""}${esc(o.label)}`;
    const baslik = esc(ad) + (o.term ? ` · ${o.term}. dönem` : "")
      + (s ? " · bu dönemki programda seçili" : "");
    return candOf(o.code)
      ? `<button type="button" class="kders${s ? " secili" : ""}" data-ders="${esc(o.code)}"
           title="${baslik}">${ic}</button>`
      : `<span class="kders" title="${baslik} · bu dönem açılmamış ya da alınamıyor">${ic}</span>`;
  };
  const GOSTER = 10;
  const grup = (baslik, liste, sinif) => liste.length ? `<div class="kalan">
      <div class="kbas${sinif ? " " + sinif : ""}">${baslik}</div>
      <div class="kliste">${liste.slice(0, GOSTER).map(cip).join("")}${
        liste.length > GOSTER ? `<span class="kders havuz">+${liste.length - GOSTER}</span>` : ""}</div>
    </div>` : "";
  const serit = terms.length ? `<div class="dnmbas">Plan dönemleri · çubuk, dönemdeki
      yuvaların tamamlanan kısmını gösterir</div>
    <div class="dnmler" aria-label="Plan dönemleri">${terms.map(t => {
      const pct = t.total ? Math.round(100 * t.done / t.total) : 0;
      const tamam = t.done === t.total;
      const geride = donem && t.term < donem && !tamam;
      const sinif = [tamam ? "tamam" : "", geride ? "geride" : "",
                     t.term === donem ? "simdi" : ""].filter(Boolean).join(" ");
      return `<div class="dnm${sinif ? " " + sinif : ""}" data-term="${t.term}"
        title="${t.term}. dönem · ${t.done}/${t.total} yuva tamamlandı${
          geride ? " · geride kalan yuva var" : ""}${t.term === donem ? " · bulunduğunuz dönem" : ""}">
        <span class="dbar"><i style="height:${pct}%"></i></span>
        <span class="dno">${t.term}</span>
      </div>`;
    }).join("")}</div>` : "";
  if(!acik.length)
    return serit + `<div class="kalan"><div class="kbas">Plandaki bütün yuvalar tamamlanmıştır.</div></div>`;
  if(donem && terms.length){
    const geride = acik.filter(o => o.term < donem);
    const simdi = acik.filter(o => o.term === donem);
    const sonra = acik.filter(o => o.term > donem);
    return serit
      + grup(`Önceki dönemlerden kalan <b class="mono">${geride.length}</b> yuva`, geride, "geride")
      + grup(`${donem}. dönemin (bulunduğunuz dönem) yuvaları`, simdi)
      + (geride.length || simdi.length ? ""
         : grup(`Sıradaki yuvalar`, sonra.filter(o => o.term === sonra[0].term)));
  }
  const zorunlu = acik.filter(o => o.required);
  const havuz = acik.length - zorunlu.length;
  return serit + grup(`Kalan zorunlu dersler (<b class="mono">${zorunlu.length}</b>)${
      havuz ? ` · ayrıca <b class="mono">${havuz}</b> seçmeli yuva` : ""}`,
    zorunlu.length ? zorunlu : acik);
}

/** Bu dönemki seçimin bir plana katkısı. Slot bazlı sayıyoruz: aynı havuza
    iki ders koyulamadığı için slot sayısı = ilerleyen slot sayısı. */
function planned(planId){
  const seen = new Set();
  let slots = 0, credits = 0, ects = 0, required = 0;
  const ps = picks();
  // Faz 81 — iki seçmeli iki AYRI yuvayı doldurabiliyor (eşleştirme).
  const atama = yuvaAta(ps.map(p => p.cand)) || ps.map(p => p.cand.slotId);
  for(const [i, p] of ps.entries()){
    const yuva = atama[i] || p.cand.slotId;
    if(p.cand.planId !== planId || seen.has(yuva)) continue;
    seen.add(yuva);
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
  $("#panels").querySelectorAll("[data-ders]").forEach(b =>
    b.addEventListener("click", () => addDialog(b.dataset.ders)));   /* seçiliyse şube, değilse ekleme */
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
    b => b.reason === "ACILMAMIS" || b.reason === "PROGRAMA_KAPALI" || b.reason === "EK_SINAV");
  if(!arz.length){ kutu.hidden = true; kutu.innerHTML = ""; return; }
  kutu.hidden = false;
  const acilmamis = arz.filter(b => b.reason === "ACILMAMIS");
  const kapali = arz.filter(b => b.reason === "PROGRAMA_KAPALI");
  const sinav = arz.filter(b => b.reason === "EK_SINAV");
  const satir = (liste, ad) => liste.length
    ? `<div style="margin-top:4px"><b>${liste.length}</b> ders ${ad}:
       <span class="mono">${liste.slice(0, 6).map(b => esc(b.course)).join(", ")}${
         liste.length > 6 ? ` +${liste.length - 6}` : ""}</span></div>` : "";
  /* ★★ FAZ 46 — KATLANDI, GİZLENMEDİ.
     Ölçüm (17.09.2026): bu kutu 115px ve 47 kelimeydi ve haftalık ızgaranın
     ÖNÜNDE duruyordu; sayfada aynı anda açık 60 ikincil metin parçasının
     en büyüğüydü. Artık özeti tek satır — ama SAYIYLA, çünkü bu repoda
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
        ${satir(acilmamis, "henüz ilan edilmemiştir")}
        ${satir(kapali, "şubeleri başka programlara ayrılmıştır")}
        ${satir(sinav, "için yalnızca ek sınav açılmıştır (ders saati yoktur)")}
        <div style="margin-top:6px" class="meta">Veri
          <span class="mono">${esc(veriTarihi())}</span> itibarıyladır;
          dönem başında ilanlar kademeli olarak yayımlanır.
          <a href="#blockSection" id="arzDetay">Ayrıntılar için Darboğaz bölümü</a>.</div>
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
    + (dönemsiz ? ` · dönem bilgisi olmayan ${dönemsiz}` : "");
  kutu.innerHTML = `
    <b>Yarıyıl bilgisi girilmemiştir.</b>
    <div style="margin-top:4px">Bu nedenle aşağıdaki program, planın
      <b>${dönemler.length}</b> farklı döneminden ders içermektedir:
      ${dökum}. Liste alınabilecek derslerin tamamını gösterir;
      <b>bu dönem için önerilen ders listesi değildir</b>.</div>
    <div class="dlgactions" style="border:0;padding:0;margin-top:8px;
      justify-content:flex-start">
      <button class="ghost primary" id="donemUyariAc">Yarıyılınızı seçin</button>
      <span class="meta">Seçimden sonra “N. dönem + alttan” kipi açılır ve
        öneri bu yarıyıla göre oluşturulur.</span>
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
      <th>Gün / saat · yer</th><th>Kredi</th></tr></thead>
      <tbody>${ps.map(p => `<tr>
        <td class="mono">${esc(p.sec.crn)}</td>
        <td class="mono">${esc(p.cand.course)}</td>
        <td>${esc((p.cand.name || "").slice(0, 40))}</td>
        <td>${p.sec.meetings.length
          ? p.sec.meetings.map(m =>
              `${DAYS[m.day-1]} ${hhmm(m.start)}–${hhmm(m.end)} · ${
                p.sec.online ? "çevrimiçi" : esc(yerYazi(m))}`).join("<br>")
          : saatsizYazi(p.sec)}</td>
        <td class="mono">${p.cand.credits}</td>
      </tr>`).join("")}</tbody></table>
    <div style="margin-top:3mm;font-size:9pt">
      ${esc(veriYasiMetni())} · Bu liste bilgilendirme amaçlıdır;
      ders kaydı Kepler (kepler-beta.itu.edu.tr) üzerinden yapılır.</div>`;
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
    return `<span class="tercihnot ok">tercihlere uygun</span>`;
  return `<span class="tercihnot ${d < 0 ? "uymaz" : "ok"}"
    title="Tercihler eleme için değil sıralama için kullanılır; uymayan program da gösterilir.">
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
/* ★★ FAZ 57 — HAFTANIN ŞEKLİ ÖZETTE. Karşılaştırma ekranı (Faz 27) iki
   önerinin şeklini yan yana koyuyordu ama ELLE düzenlenen programın şekli
   hiçbir yerde yazmıyordu: bir şube değiştirince "kampüse kaç gün
   gidiyorum, en uzun boşluğum ne" sorusu ızgarayı saymakla cevaplanıyordu.
   Kampüs günü = YÜZ YÜZE buluşması olan gün; çevrimiçi şube gün eklemiyor.
   Ara: aynı gün iki ders arasındaki boşluk (en uzunu, günüyle). */
function haftaSekli(){
  const gun = {};
  picks().forEach(p => {
    if(p.sec.online) return;
    p.sec.meetings.forEach(m => (gun[m.day] = gun[m.day] || []).push([m.start, m.end]));
  });
  const gunler = Object.keys(gun).map(Number).sort((a, b) => a - b);
  if(!gunler.length) return "";
  let ilk = Infinity, son = -Infinity, ara = 0, araGun = 0;
  gunler.forEach(d => {
    const s = gun[d].sort((a, b) => a[0] - b[0]);
    ilk = Math.min(ilk, s[0][0]);
    let bitis = s[0][1];
    for(let i = 1; i < s.length; i++){
      if(s[i][0] - bitis > ara){ ara = s[i][0] - bitis; araGun = d; }
      bitis = Math.max(bitis, s[i][1]);
    }
    son = Math.max(son, bitis);
  });
  /* İTÜ saatleri :29'da bitip :30'da başlıyor; ham fark "2 sa 1 dk" yazıyordu.
     5 dakikaya yuvarlanıyor. */
  const saat = dk => { dk = Math.round(dk / 5) * 5;
    return dk % 60 ? (dk >= 60 ? `${Math.floor(dk / 60)} sa ` : "") + `${dk % 60} dk`
                   : `${dk / 60} sa`; };
  return `<div class="ozetsekil"><span class="aciklamali" title="Yüz yüze dersin
    olduğu günler (çevrimiçi şube sayılmıyor)"><b class="mono">${gunler.length}</b>
    gün kampüste</span> · ${gunler.map(d => DAYS[d - 1]).join(" ")} ·
    <span class="mono">${hhmm(ilk)}–${hhmm(son)}</span>${ara >= 60
      ? ` · en uzun ara <span class="mono">${saat(ara)}</span> (${DAYS[araGun - 1]})` : ""}</div>`;
}

/* ★★ FAZ 57 — DOLU ŞUBEDEN BOŞ ŞUBEYE TEK DOKUNUŞ.
   Özet "dolu" diyordu, sonra kullanıcı dersin penceresini açıp şubeleri tek
   tek okuyup doluluğuna ve saatine bakmak zorundaydı. Vitrinde açılış
   önerisi GEO 331E'yi dolu şubesine (70/70) koyuyor; öbür şubesinde 15 yer
   var ama GEO 385E ile çakışıyor → "uyan boş şube yok". GEO 385E çıkınca
   aynı satır tek dokunuşla geçiriyor.
   Seçilen şube: başka şube, kontenjanı İLAN EDİLMİŞ ve boş yeri olan
   (bilinmeyen kontenjan "boş" sayılmıyor), programındaki derslerle ve meşgul
   saatlerinle çakışmayan; birden çoksa en çok boş yeri olan.
   Geçiş `choose()` ile — geri alınabilir, ızgaradaki değişiklikle aynı yol. */
function yerSayisi(s){
  return s && s.capacity
    ? Math.max(0, typeof s.free === "number" ? s.free : s.capacity - (s.enrolled || 0)) : 0;
}
function mesgulCakisir(s){
  return (DATA.busy || []).filter(b => b.ok).some(b => (s.meetings || []).some(m =>
    m.day === b.day && m.start < b.end && b.start < m.end));
}
function bosSube(course){
  const cand = candOf(course), cur = sel.find(x => x.course === course);
  if(!cand || !cur) return null;
  return cand.sections.filter(s => s.crn !== cur.crn && yerSayisi(s) > 0
      && !conflictsWith(s, course).length && !mesgulCakisir(s))
    .sort((a, b) => yerSayisi(b) - yerSayisi(a))[0] || null;
}
/* ★★ FAZ 73 — BAŞARISIZ OLUNAN DERS PROGRAMDA YOKSA, NEDENİ.
   Gerçek sitede (Faz 72 gezintisi) MAT 104E'den FF alan öğrencinin önerilen
   programında MAT 104E yoktu ve hiçbir yer nedenini söylemiyordu: 11 şubenin
   hepsi yandalın tek şubeli iki dersiyle çakışıyordu. Motorun tercihi
   bilinçli olabilir; ama öğrenci bunu ızgaraya bakıp bulmak zorundaydı.
   Transkriptte FAILED olan (ve sonradan geçilmemiş — `earned_course` dersin
   SON durumunu tutuyor) her ders için, programda değilse:
     · aday değil → darboğazdaki gerekçe (açılmamış, programa kapalı, önşart);
       gerekçe de yoksa planlarda kalan bir ders değildir → yazılmıyor;
     · bütün şubeler dolu (kontenjanı İLAN EDİLMİŞ ve 0 boş) → "dolu";
     · uyan şube var → "programa eklenebilir" + tek dokunuş;
     · yalnız meşgul saatlerinizle çakışıyor → öyle yazıyor;
     · programdaki derslerle çakışıyor → EN AZ krediyi düşüren şube ve
       çıkacak dersler adıyla; ekleme `choose()` ile, geri alınabilir.
   Kontenjanı ilan edilmemiş şube "açık olabilir" sayılıyor (dolu demek
   uydurma olurdu); ekleme düğmesi yine de boş yeri bilinen şubeyi seçiyor. */
function tekrarDurumu(){
  const secili = new Set(sel.map(x => x.course));
  const acikOlabilir = (s) => !s.capacity || yerSayisi(s) > 0;
  return ((SETUP && SETUP.transcript) || [])
    .filter(t => t.status === "FAILED" && !secili.has(t.course))
    .map(t => {
      const r = {course: t.course, grade: t.grade || "", tur: "", crn: "", cikar: []};
      const cand = candOf(t.course);
      if(!cand){
        const b = (DATA.blockers || []).find(x => x.course === t.course);
        if(!b) return null;
        return {...r, tur: "ENGEL", detay: b.detail || ""};
      }
      const acik = cand.sections.filter(acikOlabilir);
      if(!acik.length) return {...r, tur: "DOLU"};
      const serbest = acik.filter(s => !mesgulCakisir(s));
      if(!serbest.length) return {...r, tur: "MESGUL"};
      const yerli = (l) => l.filter(s => yerSayisi(s) > 0).length ? l.filter(s => yerSayisi(s) > 0) : l;
      const uyan = yerli(serbest.filter(s => !conflictsWith(s, t.course).length));
      if(uyan.length){
        const s = uyan.slice().sort((a, b) => yerSayisi(b) - yerSayisi(a))[0];
        return {...r, tur: "UYAR", crn: s.crn};
      }
      const kredi = (s) => conflictsWith(s, t.course).reduce((a, p) => a + (p.cand.credits || 0), 0);
      const s = yerli(serbest).slice().sort((a, b) => kredi(a) - kredi(b)
        || yerSayisi(b) - yerSayisi(a))[0];
      return {...r, tur: "CAKISIYOR", crn: s.crn,
              cikar: conflictsWith(s, t.course).map(p => p.cand.course)};
    }).filter(Boolean).map(r => r.crn ? {...r, ...eklemeEtkisi(r)} : r);
}
/* Tek dokunuşun iki yan etkisi ÖNCEDEN söyleniyor (sonradan kırmızıya dönen
   bir sayaçla öğrenmek yerine): dönem sınırı aşılıyor mu, ikinci programın
   yarıyıl tabanı (Faz 58 Y.4'teki gibi) bozuluyor mu. */
function eklemeEtkisi(r){
  const cand = candOf(r.course), cikan = new Set(r.cikar);
  const kalan = picks().filter(p => !cikan.has(p.cand.course));
  const yuk = kalan.reduce((a, p) => a + loadOf(p.cand), 0) + loadOf(cand);
  const F = DATA.secondFloor;
  let tabanBozar = false;
  if(F && F.min && !F.undeclared && tabanDurumu(F).ok){
    const ik = kalan.filter(p => p.cand.role !== "ANADAL")
      .reduce((a, p) => a + (p.cand.credits || 0), 0)
      + (cand.role !== "ANADAL" ? cand.credits || 0 : 0);
    tabanBozar = ik + 1e-9 < F.min;
  }
  return {asar: !!(DATA.maxLoad && yuk > DATA.maxLoad + 1e-9), yuk: +yuk.toFixed(1), tabanBozar};
}
function tekrarOzeti(){
  const L = tekrarDurumu();
  if(!L.length) return "";
  const ne = (x) => x.tur === "ENGEL" ? esc(x.detay || "bu dönem alınamamaktadır")
    : x.tur === "DOLU" ? "bütün şubeleri doludur; kontenjanın izlenmesi önerilir"
    : x.tur === "MESGUL" ? "açık şubeleri meşgul olarak işaretlediğiniz saatlerle çakışmaktadır"
    : x.tur === "UYAR" ? `CRN <span class="mono">${esc(x.crn)}</span> programla çakışmamaktadır`
    : `şubeleri programdaki <span class="mono">${x.cikar.map(esc).join(", ")}</span>
       ile çakışmaktadır`;
  const dugme = (x) => x.tur === "UYAR"
    ? ` <button class="ghost mini" data-tekrar="${esc(x.course)}" data-crn="${esc(x.crn)}"
        >programa ekle</button>`
    : x.tur === "CAKISIYOR"
    ? ` <button class="ghost mini" data-tekrar="${esc(x.course)}" data-crn="${esc(x.crn)}"
        >ekle, ${x.cikar.map(esc).join(" ve ")} çıkar</button>` : "";
  return `<div class="ozetdolu ozettekrar"><div class="ozetbaslik">Tekrar alınması gereken
      ders${L.length > 1 ? "ler" : ""} programda değil</div>${L.map(x => `
    <div class="ozetdolusatir"><span class="yerdurum dolu">${esc(x.grade || "kaldı")}</span>
      <b class="mono">${esc(x.course)}</b>${dugme(x)}
      <span class="ozetnot">— ${ne(x)}${x.asar ? `; eklenirse dönem yükü
        <b class="mono">${x.yuk}</b> / ${DATA.maxLoad} ile sınırı aşar` : ""}${x.tabanBozar
        ? `; ${esc(LBL)} yarıyıl tabanı (${DATA.secondFloor.min} kredi) sağlanamaz` : ""}</span></div>`).join("")}</div>`;
}
/* ★★ FAZ 81 — HAVUZ YUVALARI EŞLEŞTİRMEYLE (motorun `yuva_ata`sıyla aynı).
   Seçmeli, uyduğu HERHANGİ bir boş yuvaya girebiliyor; yalnız birincil yuvası
   doluysa "yerine geçer" demek, ENDE'de dört Functional-MT yuvası boşken
   ikinci dersi engelliyordu. Dönen dizi: her adaya bir slot; olmuyorsa null. */
const yuvalariOf = (c) => (c.slotIds && c.slotIds.length) ? c.slotIds
  : (c.slotId ? [c.slotId] : []);
function yuvaAta(adaylar){
  const sahip = new Map();
  const dene = (i, gorulen) => {
    for(const s of yuvalariOf(adaylar[i])){
      if(gorulen.has(s)) continue;
      gorulen.add(s);
      if(!sahip.has(s) || dene(sahip.get(s), gorulen)){ sahip.set(s, i); return true; }
    }
    return false;
  };
  for(let i = 0; i < adaylar.length; i++)
    if(yuvalariOf(adaylar[i]).length && !dene(i, new Set())) return null;
  const out = new Array(adaylar.length).fill(0);
  sahip.forEach((i, s) => { out[i] = s; });
  return out;
}
function poolBlocker(cand, exceptCourse){
  if(!cand.pool) return null;
  const digerleri = picks().filter(p => p.cand.course !== exceptCourse);
  if(yuvaAta([...digerleri.map(p => p.cand), cand])) return null;   // boş yuva var
  /* Yerine geçeceği ders: çıkarılınca eşleşmenin kurulduğu, yuvası ortak ilk
     seçmeli. */
  const ortak = digerleri.filter(p => p.cand.pool &&
    yuvalariOf(p.cand).some(s => yuvalariOf(cand).includes(s)));
  return ortak.find(p => yuvaAta([...digerleri.filter(q => q !== p).map(q => q.cand), cand]))
    || ortak[0] || null;
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
/* ★★ Faz 101 — IZGARA HANGİ PROGRAMI GÖSTERİYOR (kullanıcı 25.09.2026:
   "kaydedilen program gözüktüğünde üstte önerilen program seçilmiş
   gözüktüğü için karıştırılabilir; programın kredisi ve kaç çevrimiçi ders
   olduğu"). Açılışta kaydedilen program yükleniyordu ama sekme şeridinde
   "Öneri 1 · 24 kredi" seçili duruyor, yanında "değiştirildi" yazıyordu:
   ızgaradaki 21 kredilik program Öneri 1'in düzenlenmişi gibi okunuyordu.
   Kaynak İÇERİKTEN çıkarılıyor — kaydedilen, alternatif, CRN'den yükleme,
   geri alma hangi yoldan gelinirse gelinsin doğru kalsın diye:
     · bir öneriyle aynıysa o öneri (sekmesi seçili),
     · kaydedilen programla aynıysa "Kaydedilen",
     · bir alternatifle aynıysa onun adı,
     · hiçbiri değilse null (düzenlenmiş). `SON_KAYNAK` en son tanınan
       öneri-dışı kaynağı tutuyor: kaydedilen program düzenlenince şerit
       "Kaydedilen · değiştirildi" diyor, Öneri 1 demiyor. */
let SON_KAYNAK = null;
function izgaraKaynagi(){
  if(!sel.length) return {tur: "bos"};
  const k = currentKey();
  const anahtar = (liste) => liste.map(p => p.course + "@" + p.crn).sort().join("|");
  const i = M().schedules.findIndex(sc =>
    anahtar(sc.picks.map(p => ({course: p.course, crn: p.section.crn}))) === k);
  if(i >= 0) return {tur: "oneri", i};
  const kay = (DATA.savedPicks && DATA.savedPicks.picks) || [];
  if(kay.length && anahtar(kay) === k) return {tur: "kayitli", ad: "Kaydedilen"};
  const a = (DATA.alternatives || []).find(x => anahtar(x.picks || []) === k);
  if(a) return {tur: "alt", ad: a.name};
  return null;
}

/* ---------- sekmeler + ızgara ---------- */
function renderTabs(){
  /* ★ Taban eksiği sekmede GÖRÜNÜYOR (yapılacaklar 1.4). Motor artık tabanı
     karşılayan programı öne alıyor; karşılamayan da listede kalıyor çünkü
     taban indirilebilir ve o dönem açılan ders yetmiyor olabilir. Ama
     hangisinin eksik olduğu yazmadan sunmak, kabul edilemez bir programı
     "en iyi" diye göstermek olurdu. */
  const kaynak = izgaraKaynagi();
  if(kaynak && kaynak.tur === "oneri"){ active = kaynak.i; SON_KAYNAK = null; }
  else if(kaynak && kaynak.ad) SON_KAYNAK = kaynak;
  else if(kaynak && kaynak.tur === "bos") SON_KAYNAK = null;
  /* Öneri sekmesi yalnız ızgara O öneriyse ya da ondan düzenlendiyse seçili. */
  const disKaynak = kaynak && kaynak.ad ? kaynak : (!kaynak && SON_KAYNAK) || null;
  /* Kaydedilen program varsa sekmesi HEP duruyor (tıklayınca yüklenir):
     "Öneriye dön"den sonra kaydedilene geri dönmenin yolu şeritte kalıyor. */
  const kayitliVar = ((DATA.savedPicks && DATA.savedPicks.picks) || [])
    .some(p => sectionOf(p.course, p.crn));
  $("#tabs").innerHTML = (disKaynak ? kaynakSekmesi(disKaynak, !kaynak)
      : kayitliVar ? kaynakSekmesi({tur: "kayitli", ad: "Kaydedilen"}, false, false) : "")
    + M().schedules.map((s,i) => {
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
    return `<button class="tab" role="tab" aria-selected="${!disKaynak && i===active}" data-i="${i}"
       title="${esc(tam)}"><span class="tabmetin"
       >Öneri ${i+1}<span class="tabfark"> · ${s.credits} kredi${
         oneriFarki(s, i)}</span>${eksik.length
         ? ` <span style="color:var(--danger)">· taban ✗</span>` : ""}</span></button>`;
  }).join("") || oneriYok();
  /* ★ Faz 27 — yan yana karşılaştırma. Sekmeler arasında geçiş vardı ama
     farkı görmek için ızgarayı iki kez ezberlemek gerekiyordu. */
  if(karsilastirmaSutunlari().length > 1)         // Faz 78 — alternatifler de sayılıyor
    $("#tabs").innerHTML += `<button class="tab" id="karsilastir">Karşılaştır</button>`;
  $("#tabs").querySelectorAll(".tab[data-i]").forEach(b =>
    b.addEventListener("click", () => { active = +b.dataset.i; resetTo(active); }));
  $("#tabs").querySelectorAll(".tab[data-kayitli]").forEach(b =>       // Faz 101
    b.addEventListener("click", () => { geriKaydet("kaydedilen program yüklendi"); startFromSaved(); }));
  const k = $("#karsilastir");
  if(k) k.addEventListener("click", karsilastirDialog);
}

/* Faz 101 — ızgaradaki öneri-dışı programın sekmesi: KENDİ kredisi ve
   çevrimiçi ders sayısı (öneri sekmesinin sayıları o öneriye ait). */
function kaynakSekmesi(k, degisti, secili = true){
  /* Seçili değilse (ızgarada öneri var) sayılar KAYDEDİLEN programınki. */
  const ps = secili ? picks() : (DATA.savedPicks.picks || [])
    .map(p => ({cand: candOf(p.course), sec: sectionOf(p.course, p.crn)})).filter(p => p.cand && p.sec);
  const kredi = +ps.reduce((a, p) => a + (p.cand.credits || 0), 0).toFixed(1);
  const cev = ps.filter(p => p.sec.online).length;
  const fark = ` · ${kredi} kredi${cev ? ` · ${cev} çevrimiçi` : ""}`;
  const tam = `${k.ad} program${fark}${degisti ? " · değiştirildi" : ""}`
    + (secili ? " — ızgarada gösterilen program" : " — ızgaraya yüklemek için tıklayınız");
  return `<button type="button" class="tab kaynaktab" role="tab" aria-selected="${secili}"
    ${secili ? "" : `data-kayitli="1"`} title="${esc(tam)}"
    ><span class="tabmetin">${esc(k.ad)}<span class="tabfark">${esc(fark)}</span></span></button>`;
}

/* ★★ FAZ 45 — "öneri üretilemedi" TEK BAŞINA YALAN SAYILIR bir cümle.
   Kilit SERT kısıt: iki kilit birbiriyle çakışırsa ya da kilitli şube
   meşgul saatle çakışırsa motor hiçbir program kuramaz. Kullanıcı o an
   "bu dönem çakışmasız program yok" sanır — oysa sebep kendi koyduğu
   kısıt ve bir tıkla geri alınabilir. Sebebi söylemeyen bir boş ekran,
   bu repoda tekrarlayan hatanın (Faz 25, Faz 44) aynısı olurdu. */
function oneriYok(){
  const kl = kilitliBuKipte();
  if(!kl.length) return `<span class="empty">öneri üretilemedi</span>`;
  /* ⚠️ Uzun cümle BURAYA sığmıyor (ölçüldü: sekme şeridi dar, metin
     kenara değiyor). Kısa sebep burada, ayrıntı + "aç" düğmeleri
     kilit şeridinde — ikisi aynı ekranda. */
  return `<span class="empty" style="color:var(--danger)"
    >öneri üretilemedi — <b>${kl.length} kilit nedeniyle</b></span>`;
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
/* ★★ FAZ 78 — KARŞILAŞTIRMA HER PROGRAMI KAPSIYOR.
   Karşılaştırma yalnız motorun önerilerini yan yana koyuyordu; öğrencinin
   elle düzenlediği ızgara, kaydettiği program ve alternatifleri (Faz 77)
   dışarıdaydı — "Plan B mi Plan C mi" sorusu iki sekmeyi ezberlemek
   demekti. Artık her sütun AYNI işlevle ölçülüyor (`programOlcu`): şekil
   tanımı sunucunun `_program_sekli` ve `campus_changes`iyle aynı (test
   öneriler için ikisini karşılaştırıyor). Aynı programın iki adı varsa
   (ör. kaydedilen = Öneri 1) tek sütun, iki ad. */
function programOlcu(liste){
  const hits = liste.map(p => ({p, hit: findSection(p.course, p.crn)})).filter(x => x.hit);
  const gunler = {};
  let online = 0, saatsiz = 0;
  hits.forEach(({hit}) => {
    if(hit.sec.online) online++;
    if(!(hit.sec.meetings || []).length) saatsiz++;
    (hit.sec.meetings || []).forEach(m => (gunler[m.day] = gunler[m.day] || []).push([m.start, m.end]));
  });
  const gun = Object.keys(gunler).map(Number).sort((a, b) => a - b);
  const hepsi = gun.flatMap(d => gunler[d]);
  let bekleme = 0;
  gun.forEach(d => {
    const s = gunler[d].slice().sort((a, b) => a[0] - b[0] || a[1] - b[1]);
    for(let i = 1; i < s.length; i++) bekleme += Math.max(0, s[i][0] - s[i - 1][1]);
  });
  let kampus = 0;
  const kgun = {};
  hits.forEach(({hit}) => { if(hit.sec.online) return;
    (hit.sec.meetings || []).forEach(m => (kgun[m.day] = kgun[m.day] || []).push([m.start, m.campus])); });
  Object.values(kgun).forEach(s => { s.sort((a, b) => a[0] - b[0]);
    for(let i = 1; i < s.length; i++) if(s[i - 1][1] && s[i][1] && s[i - 1][1] !== s[i][1]) kampus++; });
  const carpisan = [];
  hits.forEach((a, i) => hits.slice(i + 1).forEach(b => {
    if(clash(a.hit.sec, b.hit.sec)) carpisan.push(`${a.p.course} ↔ ${b.p.course}`); }));
  return {
    courses: liste.map(p => p.course), eksik: liste.length - hits.length,
    credits: +hits.reduce((a, x) => a + (x.hit.cand.credits || 0), 0).toFixed(1),
    score: +hits.reduce((a, x) => a + (x.hit.cand.score || 0), 0).toFixed(1),
    shape: {days: gun, freeDays: [1, 2, 3, 4, 5].filter(g => !gun.includes(g)),
            earliest: hepsi.length ? Math.min(...hepsi.map(x => x[0])) : null,
            latest: hepsi.length ? Math.max(...hepsi.map(x => x[1])) : null,
            online, timeless: saatsiz, gaps: bekleme},
    campusChanges: kampus, carpisan,
    dolu: hits.filter(x => x.hit.sec.capacity && yerSayisi(x.hit.sec) === 0).map(x => x.p.course),
    zorluk: programZorlugu(hits.map(x => x.hit.cand)),
  };
}
/* ★★ Faz 88 — programın tahmini zorluğu: derslerin genel puanlarının (10
   üzerinden, Faz 87) KREDİ AĞIRLIKLI ortalaması. 4 kredilik çok zor ders,
   1 kredilik laboratuvardan fazla yük getirir. Verisi olmayan ders ortalamaya
   GİRMİYOR ve sayısı ayrıca yazılıyor — ortalamayı "bilinen derslerin"
   ortalaması olarak okumak gerekiyor. Hiçbir dersin verisi yoksa `ort` null. */
/* ★★★ Faz 100 — DÖNEM ZORLUĞU YÜKLE ARTIYOR (kullanıcı 25.09.2026: "alınan
   ders sayısı arttıkça zorluk artmalı; 1 ders alındığında o ders çok zor
   olsa bile kolay geçer ama 15 tane orta ders alınırsa dönem zor geçer").
   Ortalama (`ort`) bunu göremiyordu: tek bir çok zor ders 9/10, on beş orta
   ders 5/10 çıkıyordu. `donem` derslerin YÜKÜNÜ topluyor, her birimi dersin
   zorluğuyla ağırlıklandırarak (kolay ders de emek istiyor, 0'a inmiyor).

   ★★ Faz 102 — YÜK = AKTS (kullanıcı 25.09.2026: "akts ne kadar emek
   gerektirdiğinin de bir göstergesi"). Faz 100'de yük krediydi; kredi ders
   saatini, AKTS toplam emeği ölçüyor (1 AKTS ≈ 25–30 saat):
       ağırlık = 0.5 + not tabanlı puan / 10   (çok kolay 0.5 … orta 1.0 … çok zor 1.5)
       dönem   = 10 × Σ(ağırlık × AKTS) / 60, en çok 10
   Ölçek: normal dönem 30 AKTS; orta zorlukta ≈ 5 (orta). Tek çok zor ders
   (4.5 AKTS) ≈ 1.1; on beş orta ders (75 AKTS) → 10.
   ⚠️ Ağırlık NOT TABANLI puandan (`gradeOverall`): ders puanındaki AKTS
   düzeltmesini (Faz 102, `notlar.akts_etkisi`) burada kullanmak AKTS'yi iki
   kez saymak olurdu — miktar olarak zaten toplanıyor.
   ⚠️ AKTS'si bilinmeyen ders (katalogda ~%20): kredisinin 1.75 katı
   (katalogdaki AKTS/kredi oranı, ölçüldü) ve sayısı yazılıyor. Zorluk verisi
   olmayan ders ORTA sayılıyor (yükten düşürmek dönemi hafif gösterirdi).
   Hiçbir dersin zorluk verisi yoksa `donem` null: yalnız yükten zorluk
   iddia etmiyoruz. */
const DONEM_ZORLUK_TAVAN = 60;
const AKTS_KREDI_ORANI = 1.75;
const zorlukKademesi = s => s < 2 ? 1 : s < 4 ? 2 : s < 6 ? 3 : s < 8.5 ? 4 : 5;
/** Çekirdek: kalemler = [{akts, kredi, z}] (z: zorluk nesnesi ya da null). */
function donemZorlugu(kalemler){
  let top = 0, agirlik = 0, zor = 0, yok = 0, yuk = 0, akts = 0, aktsTahmin = 0;
  kalemler.forEach(k => {
    const z = k.z && k.z.level ? k.z : null;
    let a = k.akts > 0 ? +k.akts : 0;
    if(!a){ a = (k.kredi > 0 ? k.kredi : 3) * AKTS_KREDI_ORANI; aktsTahmin++; }
    akts += a;
    const notPuani = z ? (typeof z.gradeOverall === "number" ? z.gradeOverall : z.score) : null;
    yuk += (z ? 0.5 + notPuani / 10 : 1.0) * a;
    if(!z){ yok++; return; }
    top += z.score * a; agirlik += a;          // ortalama da AKTS ağırlıklı (Faz 102)
    if(z.level >= 4) zor++;
  });
  const bilinen = kalemler.length - yok;
  const donem = bilinen
    ? Math.round(Math.min(10, 10 * yuk / DONEM_ZORLUK_TAVAN) * 10) / 10 : null;
  return {ort: agirlik ? Math.round(top / agirlik * 10) / 10 : null, zor, yok, bilinen,
          donem, donemKademe: donem === null ? null : zorlukKademesi(donem),
          ders: kalemler.length, akts: Math.round(akts * 10) / 10, aktsTahmin};
}
function programZorlugu(adaylar){
  return donemZorlugu(adaylar.map(c => ({akts: c.ects, kredi: c.credits,
                                         z: zorlukOf(c)})));
}
function karsilastirmaSutunlari(){
  const sutun = [];
  const ekle = (ad, liste, tur, veri) => {
    const k = programAnahtari(liste);
    const var_ = sutun.find(s => s.anahtar === k);
    if(var_){ var_.adlar.push(ad); return; }
    sutun.push({adlar: [ad], anahtar: k, liste, tur, veri, olcu: programOlcu(liste)});
  };
  M().schedules.forEach((s, i) => ekle(`Öneri ${i + 1}`,
    s.picks.map(p => ({course: p.course, crn: p.section.crn})), "oneri", {i, s}));
  if(sel.length) ekle("Izgaradaki", sel.slice(), "izgara", null);
  const kay = (DATA.savedPicks && DATA.savedPicks.picks) || [];
  if(kay.length) ekle("Kaydedilen", kay, "program", {name: "Kaydedilen", picks: kay});
  (DATA.alternatives || []).forEach(a => ekle(a.name, a.picks, "program", a));
  return sutun;
}
function karsilastirDialog(){
  const list = karsilastirmaSutunlari();
  if(list.length < 2){ openDialog(`<div class="empty">Karşılaştırılacak ikinci bir program
    bulunmamaktadır.</div>`); return; }
  const simdi = currentKey();
  const dersKumeleri = list.map(s => new Set(s.olcu.courses));
  /* Hepsinde ortak olan dersler farkı GÖSTERMİYOR; ayıklanınca tabloda
     yalnız gerçekten değişen dersler kalıyor. */
  const ortak = [...dersKumeleri[0]].filter(c => dersKumeleri.every(k => k.has(c)));
  const secili = (s) => s.anahtar === simdi;
  const satir = (baslik, hucre, ipucu) => `<tr>
    <th${ipucu ? ` title="${esc(ipucu)}"` : ""}>${baslik}</th>
    ${list.map((s, i) => `<td class="${secili(s) ? "secili" : ""}">${hucre(s.olcu, s, i)}</td>`).join("")}
  </tr>`;
  const dk = (m) => m === null || m === undefined ? "—"
    : `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
  openDialog(`
    <div class="eyebrow">Karşılaştırma</div>
    <h2 style="margin-bottom:4px">Programlar yan yana</h2>
    <p class="modenote" style="margin:2px 0 10px">Öneriler, ızgaradaki program,
      kaydedilen program ve alternatifler aynı ölçüyle karşılaştırılır. ${ortak.length
      ? `<b class="mono">${ortak.length}</b> ders tüm programlarda ortaktır; aşağıda
         yalnızca <b>farklılıklar</b> gösterilmektedir.`
      : "Programların ortak dersi bulunmamaktadır."}</p>
    <div class="scroll"><table class="cmp">
      <thead><tr><th></th>${list.map(s =>
        `<th class="${secili(s) ? "secili" : ""}">${s.adlar.map(esc).join(" = ")}</th>`).join("")}</tr></thead>
      <tbody>
        ${satir("Kredi", o => `<b class="mono">${o.credits}</b>`)}
        ${satir("Ders", o => `<b class="mono">${o.courses.length}</b>${o.eksik
          ? `<div class="meta uyari">${o.eksik} şube bulunamadı</div>` : ""}`)}
        ${satir("Puan", (o, s) => `<b class="mono">${o.score}</b>${
          s.tur === "oneri" && s.veri.s.prefDelta ? `<div class="meta ${s.veri.s.prefDelta < 0 ? "eksi" : "arti"}">
            tercih ${s.veri.s.prefDelta > 0 ? "+" : ""}${s.veri.s.prefDelta}</div>` : ""}`,
          "Yüksek puan, dersin bu dönem alınmamasının maliyetinin yüksek olduğunu gösterir")}
        ${list.some(s => s.olcu.zorluk.ort !== null) ? satir("Tahmini zorluk", o => {
          const z = o.zorluk;
          if(z.ort === null) return `<span class="meta">veri yok</span>`;
          const enHafif = Math.min(...list.map(s => s.olcu.zorluk.donem ?? Infinity));
          /* Faz 100: eşik 0.3 — dönem ölçeğinde 1 puan 4 ağırlıklı kredi; 3 kredilik
             bir dersin ortadan çok zora çıkması dönemi ≈0.4 değiştiriyor. */
          /* ⚠️ Onda birlik adımlarla karşılaştır: 6.4 + 0.3 kayan noktada 6.7'den büyük. */
          const fark = list.some(s => Math.round(((s.olcu.zorluk.donem ?? -Infinity) - enHafif) * 10) >= 3);
          /* "En hafif" yalnız her sütunda derslerin EN AZ YARISI biliniyorsa:
             8 dersin 3'ünden çıkan ortalamayla sıralamak, bilinmeyeni bilinen
             gibi göstermek olurdu. */
          const yeterli = list.every(s => s.olcu.zorluk.bilinen >= s.olcu.zorluk.yok);
          /* Faz 100 — dönem zorluğu (yükle artan) ana sayı; ortalama altta. */
          return `<b class="mono">${zp(z.donem)}</b> / 10${z.donem === enHafif && fark && yeterli
              ? ` <span class="chip" style="color:var(--ok)">en hafif</span>` : ""}
            <div class="meta">ders ortalaması <span class="mono">${zp(z.ort)}</span> ·
              ${z.zor ? `<b class="mono">${z.zor}</b> zor ders` : "zor ders yok"}${
              z.yok ? ` · ${z.yok} ders için veri yok` : ""}</div>`;
        }, DONEM_ZORLUK_IPUCU) : ""}
        ${satir("Dolu günler", o => (o.shape.days || []).map(d => GUNAD[d - 1]).join(" ") || "—")}
        ${satir("Boş gün", o => (o.shape.freeDays || []).map(d => `<b>${GUNAD[d - 1]}</b>`).join(" ") || "—")}
        ${satir("En erken", o => `<span class="mono">${dk(o.shape.earliest)}</span>`)}
        ${satir("En geç", o => `<span class="mono">${dk(o.shape.latest)}</span>`)}
        ${satir("Ders arası bekleme", o => `<span class="mono">${
          Math.round((o.shape.gaps || 0) / 60 * 10) / 10} sa</span>`,
          "Aynı gün içindeki toplam boşluk")}
        ${satir("Kampüs değişimi", o => `<span class="mono">${o.campusChanges}</span>${
          o.tightTransfers ? ` <span class="yerdurum az">${o.tightTransfers} sıkışık (arada &lt; 60 dk)</span>` : ""}`)}
        ${satir("Çevrimiçi", o => `<span class="mono">${o.shape.online || 0}</span>`)}
        ${list.some(s => s.olcu.shape.timeless)
          ? satir("Saati ilan edilmemiş", o => `<span class="mono">${o.shape.timeless || 0}</span>`,
              "Bu dersler ızgarada gösterilmez ve çakışma denetimine dahil edilmez")
          : ""}
        ${list.some(s => s.olcu.dolu.length)
          ? satir("Dolu şube", o => o.dolu.length
              ? o.dolu.map(c => `<div class="mono uyari">${esc(c)}</div>`).join("")
              : `<span class="meta">—</span>`) : ""}
        ${list.some(s => s.olcu.carpisan.length)
          ? satir("Çakışma", o => o.carpisan.length
              ? o.carpisan.map(c => `<div class="mono uyari">${esc(c)}</div>`).join("")
              : `<span class="meta">—</span>`) : ""}
        ${satir("Değişen dersler", o => {
          const farkli = o.courses.filter(c => !ortak.includes(c));
          return farkli.length
            ? farkli.map(c => `<div class="mono">${esc(c)}</div>`).join("")
            : `<span class="meta">—</span>`;
        })}
        ${satir("", (o, s, i) => secili(s)
          ? `<span class="chip">görüntüleniyor</span>`
          : `<button class="ghost" data-kyas="${i}">${s.tur === "oneri" ? "Bunu seç" : "Programa yükle"}</button>`)}
      </tbody>
    </table></div>`);
  $("#detailBody").querySelectorAll("[data-kyas]").forEach(b =>
    b.addEventListener("click", () => {
      const s = list[+b.dataset.kyas];
      $("#detail").close();
      if(s.tur === "oneri"){ active = s.veri.i; resetTo(active); }
      else altYukle({name: s.adlar[0], picks: s.liste});
    }));
}

/* Dar ekran görünümü: gün gün dikey liste (yapılacaklar 4.1).
   Izgaranın min-width'i 660px; telefonda yana kaydırmadan okunmuyordu.

   ★ Listenin ızgaraya göre zayıf yanı çakışmayı göstermemesi. Onu kabul edip
   geçmek yerine burada çakışma AÇIKÇA hesaplanıyor: aynı gün içinde saatleri
   kesişen iki ders kırmızıyla ve "ÇAKIŞIYOR" etiketiyle işaretleniyor. */
/* ★★ Faz 95 — SIRADAKİ DERS. Telefonda gün listesi Pazartesi'den başlıyordu;
   okulda sorulan soru "şimdi ne var, sıradaki ders nerede". Listenin başında
   bir satır: şu an süren ders ya da bugünün sıradaki dersi, yoksa bir
   sonraki ders günü — saat, bina ve derslikle.
   ⚠️ Araçta akademik takvim YOK (bkz. takvim dosyası notu): tatilde de
   "şimdi" diyebilirdi. Bu yüzden söz "programınıza göre"; bir dersin
   gerçekten yapıldığını iddia etmiyor. Meşgul saatler ders değil, sayılmıyor. */
const GUN_TAM = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"];
const SIMDI = () => { const t = new Date();
  return {gun: ((t.getDay() + 6) % 7) + 1, dk: t.getHours() * 60 + t.getMinutes()}; };
function siradaki(an){
  const hepsi = picks().flatMap(p => p.sec.meetings.map(m => ({p, m})));
  if(!hepsi.length) return null;
  const bugun = hepsi.filter(x => x.m.day === an.gun).sort((a, b) => a.m.start - b.m.start);
  const suren = bugun.find(x => x.m.start <= an.dk && an.dk < x.m.end);
  if(suren) return {tur: "simdi", ...suren};
  const sonra = bugun.find(x => x.m.start > an.dk);
  if(sonra) return {tur: "sonra", ...sonra, fark: sonra.m.start - an.dk};
  for(let i = 1; i <= 7; i++){
    const g = ((an.gun - 1 + i) % 7) + 1;
    const o = hepsi.filter(x => x.m.day === g).sort((a, b) => a.m.start - b.m.start)[0];
    if(o) return {tur: "ileri", ...o, gun: g};
  }
  return null;
}
function siradakiHTML(an){
  const s = siradaki(an);
  if(!s) return "";
  const yer = s.p.sec.online ? "çevrimiçi" : yerYazi(s.m);
  const ders = `<b class="mono">${esc(s.p.cand.course)}</b> · <span class="yer">${esc(yer)}</span>`;
  const sure = (dk) => dk < 60 ? `${dk} dk` : `${Math.floor(dk / 60)} sa ${dk % 60 ? (dk % 60) + " dk" : ""}`.trim();
  const metin = s.tur === "simdi"
      ? `Şimdi: ${ders} · bitiş ${hhmm(s.m.end)}`
      : s.tur === "sonra"
      ? `Sıradaki: ${hhmm(s.m.start)} ${ders} (${sure(s.fark)} sonra)`
      : `Bugün başka ders yok. ${GUN_TAM[s.gun - 1] || ""} ilk ders: ${hhmm(s.m.start)} ${ders}`;
  return `<div class="siradaki" title="Programınıza göre; akademik takvim bu araçta bulunmadığından tatil ve sınav haftaları bilinmiyor">${metin}</div>`;
}

/* Sayfa açık kaldıkça yalnız bu satır tazeleniyor (dakikada bir); liste
   baştan çizilmiyor — dokunuş ve odak bozulmasın. */
setInterval(() => {
  const el = document.querySelector("#daylist .siradaki");
  if(el) el.outerHTML = siradakiHTML(SIMDI());
}, 60000);

function renderDayList(){
  const box = $("#daylist");
  if(!box) return;
  const byDay = {};
  picks().forEach(p => p.sec.meetings.forEach(m => {
    (byDay[m.day] = byDay[m.day] || []).push({p, m});
  }));
  /* ★★ FAZ 56 — MEŞGUL SAATLER TELEFONDA DA. Izgara onları çiziyordu, bu
     liste çizmiyordu: vitrin verisinde cuma 13:30–17:30 "staj" masaüstünde
     taralı bir bloktu, telefonda cuma "boş" yazıyordu. Aynı veri iki
     biçimde iki farklı şey söylüyordu — bu repoda ölçülmüş bir hata sınıfı.
     Meşgul saatle kesişen ders ÇAKIŞMA sayılıyor (elle eklenen ders oraya
     düşebilir; ızgarada o hücreyi ders örtüyor, burada ikisi de görünüyor). */
  (DATA.busy || []).filter(b => b.ok).forEach(b => {
    (byDay[b.day] = byDay[b.day] || []).push({busy: b, m: {start: b.start, end: b.end}});
  });
  let out = "";
  for(let d=1; d<=5; d++){
    const items = (byDay[d] || []).sort((a,b) => a.m.start - b.m.start);
    // Çakışma: aynı gündeki her çift için aralık kesişimi. İki meşgul
    // saatin kesişmesi bir ders çakışması değil — en az biri ders olmalı.
    const clash = new Set();
    for(let i=0;i<items.length;i++) for(let j=i+1;j<items.length;j++){
      if(items[i].busy && items[j].busy) continue;
      if(items[i].m.start < items[j].m.end && items[j].m.start < items[i].m.end){
        clash.add(i); clash.add(j);
      }
    }
    out += `<section><h3>${DAYS[d-1]}${d === SIMDI().gun ? ` <span class="bugun">bugün</span>` : ""}</h3>`;
    out += items.length ? items.map((it,i) => it.busy
      ? `<button class="row mesgul${clash.has(i) ? " clash" : ""}"
           data-busy="${esc(it.busy.raw)}" title="Kaldırmak için dokununuz">
           <span><b>${esc(it.busy.label || "meşgul")}</b>
             <small class="mono">${hhmm(it.m.start)}–${hhmm(it.m.end)} · ders yerleştirilmez</small></span>
           ${clash.has(i) ? '<span class="warn">çakışıyor</span>' : ""}
         </button>`
      : `<button class="row${clash.has(i) ? " clash" : ""}${
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
               : `<span class="yer" title="${esc(yerBaslik(it.m))}">${
                    esc(yerYazi(it.m))}</span>`}
             · ${esc(it.p.sec.crn)}${yerDurumu(it.p.sec)}${gecisNotu(it.p, it.m)}</small></span>
         ${clash.has(i) ? '<span class="warn">çakışıyor</span>' : ""}
       </button>`).join("")
      : `<div class="none">boş</div>`;
    out += `</section>`;
  }
  box.innerHTML = siradakiHTML(SIMDI()) + out;
  box.querySelectorAll(".row[data-course]").forEach(el =>
    bind(el, () => courseDialog(el.dataset.course)));
  box.querySelectorAll(".row[data-busy]").forEach(el =>
    bind(el, () => busyDialog(null, null, el.dataset.busy)));
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
  /* ★★ FAZ 56 — ÖZET BİR SATIR YIĞINI DEĞİL.
     Eski hâli 240px'lik sütunda yedi parçalı bir esnek satırdı ve sarınca
     "sınır 22 kredi puan 792.5" gibi birbirine yapışık okunuyordu; asıl
     soru ("sınıra ne kadar yakınım") bir hesap istiyordu. Şimdi:
       · yük ve sınır TEK bakışta — büyük sayı + ölçek (aşınca kırmızı VE
         "aşıldı" yazıyor; renk tek işaret değil),
       · DOLU şube varsa adıyla (ızgaradaki rozetin özeti),
       · lejant her ikinci programın KENDİ renginde. ⚠️ Eskiden nokta
         `var(--cap)`e sabitti: yandal öğrencisi amber bir "yandal" noktası
         görüyordu, blokları ise mavi.
       · "puan" ne olduğunu söylüyor (dokununca açıklama — Faz 51). */
  const oran = DATA.maxLoad ? Math.min(1, t.load / DATA.maxLoad) : 0;
  const cevrimici = picks().filter(p => p.sec.online).length;      // Faz 101
  const ikincil = DATA.unitLabel === "kredi"
    ? `${t.ects} AKTS` : `${t.credits} kredi`;
  const doluSube = picks().filter(p => p.sec.capacity &&
    Math.max(0, typeof p.sec.free === "number" ? p.sec.free
      : p.sec.capacity - (p.sec.enrolled || 0)) === 0);
  $("#schedSummary").innerHTML = `
    <div class="yukust"><b class="mono yuksayi${over ? " over" : ""}">${t.load}</b>
      <span>${DATA.maxLoad ? `/ <span class="mono">${DATA.maxLoad}</span> ` : ""}${
        esc(DATA.unitLabel)}</span>${over ? ' <span class="over">aşıldı</span>' : ""}</div>
    ${DATA.maxLoad ? `<div class="yuk${over ? " asti" : ""}" role="img"
      aria-label="dönem yükü ${t.load} / ${DATA.maxLoad} ${esc(DATA.unitLabel)}${
        over ? " — sınır aşıldı" : ""}"><i style="width:${(oran * 100).toFixed(0)}%"></i></div>` : ""}
    <div class="ozetsatir">${t.n} ders · <span class="mono">${ikincil}</span>${
      cevrimici ? ` · <span class="mono">${cevrimici}</span> çevrimiçi` : ""}</div>
    ${haftaSekli()}
    ${zorlukOzeti()}
    ${disKredi ? `<div class="planout">bunun <b class="mono">${disKredi}</b>
      kredisi <b>plan dışıdır</b>; yüke sayılır, şart karşılamaz</div>` : ""}
    ${doluSube.length ? `<div class="ozetdolu">${doluSube.map(p => {
      const b = bosSube(p.cand.course);
      return `<div class="ozetdolusatir"><span class="yerdurum dolu">dolu</span>
        <b class="mono">${esc(p.cand.course)}</b>${b
          ? ` <button class="ghost mini" data-bosa="${esc(p.cand.course)}"
              data-crn="${esc(b.crn)}">boş şubeye geç</button>
            <span class="ozetnot">CRN <span class="mono">${esc(b.crn)}</span> ·
              <span class="mono">${yerSayisi(b)}</span> boş yer · çakışmıyor</span>`
          : ` <span class="ozetnot">— uygun boş şube bulunmamaktadır; kontenjanın izlenmesi önerilir</span>`}</div>`;
    }).join("")}</div>` : ""}
    ${tekrarOzeti()}
    <div class="ozetlejant">
      <span class="dot"><i style="background:var(--anadal)"></i>anadal</span>
      ${SECONDS().map(x => `<span class="dot"><i style="background:var(--${
        x.role === "YANDAL" ? "yandal" : "cap"})"></i>${esc(x.label)}</span>`).join("")}
    </div>
    <div class="ozetpuan"><span class="aciklamali" title="Programdaki derslerin
      puanlarının toplamı: kritik yol, açtığı dersler, zorunluluk ve kontenjan.
      Öneriler bu sayıya göre sıralanır; tek başına bir değerlendirme notu değildir.">öneri
      puanı</span> <b class="mono">${t.score}</b></div>
    ${tercihNotu()}`;
  $("#schedSummary").querySelectorAll("[data-bosa]").forEach(b =>
    b.addEventListener("click", () => choose(b.dataset.bosa, b.dataset.crn)));
  $("#schedSummary").querySelectorAll("[data-hafiflet]").forEach(b =>  // Faz 103
    b.addEventListener("click", () => removeCourse(b.dataset.hafiflet)));
  $("#schedSummary").querySelectorAll("[data-tekrar]").forEach(b =>   // Faz 73
    b.addEventListener("click", () => choose(b.dataset.tekrar, b.dataset.crn)));
  /* Faz 101 — "değiştirildi" yalnız ızgara TANINAN hiçbir programa (öneri,
     kaydedilen, alternatif) eşit değilse; "Öneriye dön" seçili öneriden
     farklıysa (kaydedilen programdan öneriye geçmenin yolu). */
  $("#editState").hidden = !!izgaraKaynagi();
  $("#reset").hidden = !edited();
  $("#reset").title = `Öneri ${active + 1} ızgaraya yüklenir (geri alınabilir)`;
  renderSaveState();
  renderFloor();
  renderGnoHedef();          // Faz 57 — seçim değişince gereken ortalama da
  renderNotSenaryo();        // Faz 71 — dönem sonu not senaryosu
  kalmaCiz();                // Faz 75 — program değişince "yeniden hesapla"
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
          title="Kaldırmak için tıklayınız">
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
                        c.p.sec.online ? "çevrimiçi" : yerBaslik(c.m),
                        kld ? kilitBaslik(c.p.cand.course) : ""]
                       .filter(Boolean).join(" · "))}">
          ${kld ? `<span class="kilitim">${KILIT_SVG}</span>` : ""}
          <b class="mono">${esc(c.p.cand.course)}</b>
          ${c.p.cand.name ? `<span class="blkad">${esc(c.p.cand.name)}</span>` : ""}
          <small class="mono">${hhmm(c.m.start)}–${hhmm(c.m.end)}
            ${c.p.sec.online ? "çevrimiçi" : `<span class="yer">${esc(yerYazi(c.m))}</span>`}
            · ${esc(c.p.sec.crn)}${yerDurumu(c.p.sec)}${gecisNotu(c.p, c.m)}</small></div></td>`;
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

  /* ★ Faz 111 — ek sınav şubesi, saati ilan edilmemişler grubunda DEĞİL: saati
     hiç yok, bir ders değil, bir sınav hakkı. Ayrı başlık, kısa açıklama. */
  const notimeGrup = (liste, baslik, aciklama) => liste.length ? `
    <div class="eyebrow" style="margin-bottom:6px">${baslik}</div>
    ${aciklama ? `<div class="meta" style="margin-bottom:6px">${aciklama}</div>` : ""}
    <div class="blocklist">${liste.map(p =>
      `<div class="blockitem" data-course="${esc(p.cand.course)}" tabindex="0"
         role="button" style="cursor:pointer"><b class="mono">${esc(p.cand.course)}</b>
        <span class="tag ${p.cand.role}" style="margin-left:4px">${p.cand.role}</span>
        CRN ${esc(p.sec.crn)} · ${p.sec.sinav ? esc(p.sec.sinav.toLowerCase()) + " · " : ""}${
        p.cand.credits} kredi</div>`).join("")}</div>` : "";
  const sinavli = timeless.filter(p => p.sec.sinav);
  $("#notime").innerHTML =
    notimeGrup(timeless.filter(p => !p.sec.sinav), "Saati ilan edilmemiş", "")
    + notimeGrup(sinavli, "Ek sınav",
        `Ders saati yoktur; ek sınav hakkı azami öğrenim süresini dolduran
         öğrencilere tanınır (2547 sayılı Kanun m. 44/c).`);
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
      uygulanmaz</b>; ders bu kipin aday havuzunda bulunmamaktadır.${
      oneren >= 0 ? ` Kilitlendiğinde <b>${esc(MODES[oneren].label)}</b> kipinin
      önerilerinde bu şube sabit tutulur.` : ""}</div>`;
  const l = kilitler()[course];
  if(l && l.tur === "aralik")
    return `<div class="why" style="margin-top:8px"><b>${esc(ilkBuyuk(kilitYonelme(l)))}
      kilitli</b>: öneriler bu dersi o saatlere uyan ${l.uyan.length} şubeden
      birinde tutar; <b>şube araç tarafından seçilir</b>.${
      kilitliMi(course, crn) ? "" : ` ⚠️ Ekrandaki
      <span class="mono">CRN ${esc(crn)}</span> bu aralığın <b>dışındadır</b>;
      elle yapılan değişiklikten sonra öneriye dönüldüğünde kilit yeniden uygulanır.`}
      "Bu saate kilitle" seçildiğinde aralık kilidi <b>bu şubeye</b> dönüştürülür.</div>`;
  if(l && l.crn !== crn)
    return `<div class="why" style="margin-top:8px">Bu ders
      <span class="mono">CRN ${esc(l.crn)}</span> şubesine kilitlidir; ekrandaki
      şube <span class="mono">CRN ${esc(crn)}</span>. Kilitlendiğinde kilit
      <b>bu şubeye taşınır</b>; bir derste yalnızca bir kilit bulunabilir.</div>`;
  if(l)
    return `<div class="why" style="margin-top:8px">Saate kilitli: öneriler
      bu dersi <b>bu şubede</b> tutarak kalan programı <b>buna göre</b> oluşturur.</div>`;
  return `<div class="why" style="margin-top:8px">Kilitlendiğinde araç bu dersi
    <b>bu şubede</b> tutar ve kalan programı buna göre oluşturur. Kilitlenmezse
    ders programda kalabilir; ancak <b>şubesi (dolayısıyla saati) değişebilir</b>.
    Yalnızca saat önemliyse <b>sabah</b> veya <b>öğleden sonra</b> kilidi
    kullanılabilir; bu durumda o saatlerdeki bütün şubeler denenir.</div>`;
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
      Öneriler bu derslere göre oluşturulmuştur.${okunmayan.length ? ` ⚠️
      ${okunmayan.length} kilit satırı <b>uygulanmamaktadır</b>
      (${okunmayan.map(satirAd).join(", ")}).` : ""} Kilidi kaldırmak için
      uygulamayı <span class="mono">make app</span> ile başlatınız veya
      <span class="mono">settings.toml</span> dosyasındaki
      <span class="mono">kilitli</span> satırını düzenleyiniz.`;
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
  const neden = (l) => l.neden === "sube" ? `CRN ${esc(l.crn)} bu kipte açık değildir`
    : l.neden === "aralik" ? `bu dersin <b>${esc(kilitEtiketi(l))}</b> saatlerine
        tamamen uyan şubesi bulunmamaktadır`
    : "bu ders artık aday listesinde bulunmamaktadır";
  el.innerHTML = `${uygulanan.length ? `<b>${uygulanan.length} ders saate kilitli.</b>` : ""}
    ${/* ⚠️ Giriş cümlesi KOŞULLU: kilitlerin hepsi bu kipin havuzu dışındaysa
          "etrafında kuruluyor" demek düpedüz yanlış olurdu — motor onları bu
          kipte hiç görmüyor (Faz 49). */ ""}
    ${!uygulanan.length ? "" : bagli.length ? `Öneriler ${bagli.length < uygulanan.length
        ? `bu kipte bağlayan <b>${bagli.length}</b> dersin`
        : "bu derslerin"} saatini sabit tutarak <b>buna göre</b> oluşturulmaktadır.`
      : `<b>Bu kipte hiçbir kilit uygulanmamaktadır.</b>`}
    ${bosSonuc && bagli.length ? `<div style="margin-top:6px;color:var(--danger)">
      <b>Bu kipte program oluşturulamadı.</b> Bu kipte uygulanan
      ${bagli.length} kilit (${bagli.map(ad).join(", ")}) birbiriyle veya
      meşgul saatlerle çakışmaktadır. Aşağıdan bir kilidi kaldırınız.
      </div>` : ""}
    ${kirik.length ? `<div style="margin-top:6px;color:var(--danger)">
      ${kirik.map(l => `${ad(l)} kilidi <b>uygulanamıyor</b>: ${neden(l)}.`).join("<br>")}
      </div>` : ""}
    ${okunmayan.length ? `<div style="margin-top:6px;color:var(--danger)">
      ${okunmayan.map(l => `${satirAd(l)} <b>uygulanmamaktadır</b>: ${l.tur === "golge"
        ? `aynı ders için sonradan yazılan kilit geçerlidir`
        : `satır okunamadı; geçerli biçim <span class="mono">DERS@CRN</span> veya
           <span class="mono">DERS@SS:DD-SS:DD</span>`}.`).join("<br>")}
      </div>` : ""}
    ${/* ★★ FAZ 49 — KAPSAM DIŞI KİLİT. Motor kilidi yalnız o kipin
          havuzundaki derse bağlıyor; kilitli üst dönem dersi "5. dönem +
          alttan" kipinde sessizce yok sayılıyordu ve şerit yine
          "etrafında kuruluyor" diyordu. Tutmayan kilitle aynı sınıf:
          söylenmeden bırakılamaz, ama HATA da değil — öbür kipte
          çalışıyor, o yüzden kırmızı değil. */ ""}
    ${kapsamDisi.length ? `<div style="margin-top:6px">
      ${kapsamDisi.map(l => `${ad(l)} kilidi <b>bu kipte uygulanmamaktadır</b>;
        ders bu kipin aday havuzunda bulunmamaktadır${
        kipAdi(l.course) ? `. Kilit <b>${esc(kipAdi(l.course))}</b> kipinde uygulanır`
                         : ""}.`).join("<br>")}
      </div>` : ""}
    ${kayan.length ? `<div style="margin-top:6px">
      ${kayan.map(k => `${ad(k.l)} ekranda <span class="mono">CRN ${esc(k.crn)}</span>,
        kilit <span class="mono">${esc(kilitEtiketi(k.l))}</span>${k.l.tur === "aralik"
          ? " (ekrandaki şube bu saatlerin dışındadır)" : ""} —
        <button class="ghost mini" data-tasi="${esc(k.l.course)}"
          data-crn="${esc(k.crn)}">${k.l.tur === "aralik"
            ? "kilidi bu şubeye çevir" : "kilidi buraya taşı"}</button>`).join("<br>")}
      </div>` : ""}
    <div class="kilitsatir">${rozet}
      ${list.length > 1 ? `<button class="ghost mini" id="kilitHepsi"
        >tüm kilitleri kaldır</button>` : ""}</div>`;
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
        `${DAYS[m.day-1]} ${hhmm(m.start)}–${hhmm(m.end)} <span class="yer" title="${
           esc(yerBaslik(m))}">${esc(yerYazi(m))}</span>`).join("<br>")
    : saatsizYazi(section, "kisa");
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
      · yüksek puan, dersin <b>bu dönem alınmamasının maliyetinin yüksek</b> olduğunu gösterir; dersin niteliğine ilişkin bir değerlendirme değildir</div>
  </details>`;
}

/* ---------- ★★ FAZ 85 — TAHMİNİ ZORLUK ----------
   Kullanıcı 24.09.2026: *"derslerin önceki dönemlerdeki not ortalaması ve
   dağılımına göre tahmini zorluk derecelendirilmesi yapabilir misin"*.
   Hesap sunucuda (`notlar.zorluk`): olağan dönemlerin VF'siz harf
   ortalaması, katalogdaki öbür derslere göre beşte birlik dilime oturtuluyor.
   ⚠️ Faz 38 kuralı aynen: ÖNERİ PUANINA GİRMİYOR; her yerde "tahmini" ve
   neden tahmin olduğu yazıyor (ortalama hocanın not verme eğilimini de
   yansıtır). Derecelenemeyen ders için kademe UYDURULMUYOR. */
const zorlukOf = c => {
  const z = c && c.grades && c.grades.difficulty;
  return z && z.level ? z : null;
};
/* ★★★ Faz 87 — İKİ ALT PUAN, 10 ÜZERİNDEN (kullanıcı 24.09.2026): geçme
   zorluğu (geçme oranından, VF başarısız sayılır) ve yüksek not alma zorluğu
   (harf notu ortalamasından); genel = %70 geçme + %30 yüksek not. Hesap
   sunucuda (`notlar.zorluk`); burada yalnız gösterim. */
const zp = x => Number(x).toFixed(1);
const zorlukDonemleri = z => (z.termLabels || []).map(kisaDonem).join(", ");
function zorlukIpucu(z){
  const d = zorlukDonemleri(z);
  return `Tahmini zorluk: 10 üzerinden ${zp(z.score)} (${z.label}). `
    + `Geçme zorluğu ${zp(z.passScore)}/10 (geçme oranı %${z.passRate}, VF dahil); `
    + `yüksek not alma zorluğu ${zp(z.gradeScore)}/10 (ortalama ${z.mean.toFixed(2)}). `
    + aktsCumlesi(z)
    + `Olağan dönemler${d ? `: ${d}` : ""}; ${z.n} öğrenci.`
    + (z.lowData ? " Az veriye dayanmaktadır." : "");
}
/* ★ Faz 102 — AKTS (iş yükü) düzeltmesi: 0.1 × (AKTS − 5), en çok ±1
   (hesap sunucuda, `notlar.akts_etkisi`). */
const isaretli = x => (x > 0 ? "+" : x < 0 ? "−" : "±") + Math.abs(x).toFixed(1);
function aktsCumlesi(z){
  return typeof z.ectsEffect === "number"
    ? `İş yükü ${z.ects} AKTS (tipik ders 5): ${z.ectsEffect
        ? isaretli(z.ectsEffect) : "genel puanı değiştirmez"}. `
    : z.gradeOverall !== undefined ? "AKTS bilinmediğinden iş yükü hesaba katılmadı. " : "";
}
function zorlukRozet(z, puansiz){
  if(!z || !z.level) return "";
  const cub = [1, 2, 3, 4, 5].map(i => `<i class="${i <= z.level ? "on" : ""}"></i>`).join("");
  return `<span class="zorluk z${z.level}" title="${esc(zorlukIpucu(z))}"
    ><span class="zcubuk" aria-hidden="true">${cub}</span><span class="sr-only">tahmini zorluk: </span>${
      esc(z.label)}${puansiz ? "" : ` <span class="mono zskor">${zp(z.score)}</span><span class="sr-only"> / 10</span>`}${
      z.lowData ? ` <span class="azveri">· az veri</span>` : ""}</span>`;
}
/* Alt puan satırı: ad · 0–10 çubuğu · puan · dayanak. Çubuğun rengi alt
   puanın kendi kademesinden (aynı bantlar). */
const ZORLUK_BANT = [2, 4, 6, 8.5];
const zorlukKademe = x => 1 + ZORLUK_BANT.filter(b => x >= b).length;
function zorlukAlt(ad, puan, agirlik, dayanak){
  return `<div class="zalt z${zorlukKademe(puan)}">
    <span class="zad">${ad} <span class="zagirlik">ağırlık ${agirlik}</span></span>
    <span class="zbar" aria-hidden="true"><i style="width:${(puan * 10).toFixed(0)}%"></i></span>
    <span class="mono zdeger"><b>${zp(puan)}</b> / 10</span>
    <span class="zdayanak">${dayanak}</span></div>`;
}
/* Ders penceresindeki açıklamalı kutu. */
function zorlukKutusu(cand){
  const z = cand && cand.grades && cand.grades.difficulty;
  if(!z) return "";
  if(!z.level) return `<div class="zorlukkutu"><div class="zorlukust"><b>Tahmini zorluk</b>
      <span class="zorluk">derecelendirilemedi</span></div>
      <div class="why">${esc(z.reason || "")}</div></div>`;
  const d = zorlukDonemleri(z);
  return `<div class="zorlukkutu">
    <div class="zorlukust"><b>Tahmini zorluk</b> ${zorlukRozet(z, true)}
      <span class="zgenel"><b class="mono">${zp(z.score)}</b> / 10</span></div>
    <div class="zaltlar">
      ${zorlukAlt("Geçme zorluğu", z.passScore, "%70",
         `geçme oranı <b class="mono">%${z.passRate}</b> (VF dahil)`)}
      ${zorlukAlt("Yüksek not alma zorluğu", z.gradeScore, "%30",
         `harf notu ortalaması <b class="mono">${z.mean.toFixed(2)}</b>`)}
    </div>
    <div class="zakts">${typeof z.ectsEffect === "number"
      ? `İş yükü: <b class="mono">${z.ects}</b> AKTS (tipik ders 5) → ${z.ectsEffect
         ? `genel puana <b class="mono">${isaretli(z.ectsEffect)}</b> (not tabanlı puan
            <span class="mono">${zp(z.gradeOverall)}</span>)`
         : "genel puanı değiştirmez"}`
      : `İş yükü: AKTS bilinmediğinden hesaba katılmadı.`}</div>
    <div class="why">Olağan dönemler${d ? `: ${esc(d)}` : ""}; <span class="mono">${z.n}</span> öğrenci.${
      z.lowData ? " <b>Az veriye dayanmaktadır.</b>" : ""}</div>
    <div class="zorluknot">Genel puan = geçme zorluğu × 0.7 + yüksek not alma zorluğu × 0.3,
      artı iş yükü düzeltmesi 0.1 × (AKTS − 5), en çok ±1: AKTS dersin gerektirdiği
      emeğin ölçüsüdür. Ölçek: geçme oranı %100 → 0, %85 → 5, %70 ve altı → 10; ortalama 4.00 → 0,
      2.50 → 5, 1.00 ve altı → 10. <b>VF geçemeyenlere sayılır</b> (vizeden kalan
      öğrenci finale giremediği için VF görünür). Kademe: 0–2 çok kolay · 2–4 kolay ·
      4–6 orta · 6–8.5 zor · 8.5–10 çok zor.
      Tahmindir: notlar dersin zorluğunun yanında öğretim üyesinin not verme eğilimini
      ve dersi alan öğrencilerin yapısını da yansıtır. Tekrar/bütünleme niteliğindeki
      küçük sınıflar hesaba katılmaz. Bu bilgi öneri puanına <b>dahil edilmez</b>.</div>
  </div>`;
}
/* Programın zorluk karışımı — özet ve karşılaştırma için. */
function zorlukKarisimi(ps){
  const say = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0};
  let yok = 0;
  ps.forEach(p => { const z = zorlukOf(p.cand); if(z) say[z.level]++; else yok++; });
  return {say, yok, zor: say[4] + say[5]};
}
function zorlukOzeti(){
  const ps = picks();
  if(!ps.length) return "";
  const k = zorlukKarisimi(ps);
  const parca = [5, 4, 3, 2, 1].filter(l => k.say[l])
    .map(l => `<b class="mono">${k.say[l]}</b> ${ZORLUK_AD[l]}`);
  if(!parca.length) return "";
  /* Faz 88/100 — karşılaştırmadaki sayılarla AYNI (dönem zorluğu + ortalama). */
  const pz = programZorlugu(ps.map(p => p.cand));
  /* Faz 100 — önce DÖNEM zorluğu (yükle artan), sonra derslerin ortalaması. */
  return `<div class="ozetzorluk aciklamali" title="${esc(DONEM_ZORLUK_IPUCU)}">tahmini dönem zorluğu <b class="mono">${
    zp(pz.donem)}</b>/10 (${ZORLUK_AD[pz.donemKademe]}) · <span class="mono">${pz.ders}</span> ders,
    <span class="mono">${pz.akts}</span> AKTS${pz.aktsTahmin
      ? ` (${pz.aktsTahmin} dersin AKTS'si kredisinden tahmin edildi)` : ""} · ders ortalaması <b class="mono">${
    zp(pz.ort)}</b>/10: ${parca.join(" · ")}${k.yok ? ` · ${k.yok} ders için veri yok (orta sayıldı)` : ""}${
    pz.donem >= 8.5
      ? ` — <span class="yogun">dönem yükü çok ağır; ders sayısının azaltılması değerlendirilebilir</span>`
      : k.zor >= 3
      ? ` — <span class="yogun">zor ders sayısı yüksek; yükün dengelenmesi değerlendirilebilir</span>` : ""}</div>${
    pz.donemKademe >= 4 ? hafifletmeOnerisi(ps, pz) : ""}`;
}
/* ★★ Faz 103 — "DÖNEMİ HAFİFLET" SOMUT. Özet "dönem yükü çok ağır; ders
   sayısının azaltılması değerlendirilebilir" diyordu ama HANGİ dersin
   çıkarılacağını söylemiyordu (bu repoda genel uyarı yasak — Faz 46).
   Dönem "zor" ya da "çok zor"ken: her dersi tek tek çıkarıp dönem zorluğunu
   yeniden hesaplıyoruz; en çok hafifleten, eşitlikte öneri puanı (bu dönem
   alınmamasının maliyeti) en düşük olan önce. En çok iki satır.
   Hiç önerilmeyenler:
     · kritik yoldaki ders (`critical`: ertelenirse mezuniyet uzar),
     · saate kilitlenmiş ders (öğrencinin kendi kararı),
     · çıkarılınca ÇAP/yandal yarıyıl tabanını bozan ders (şu an sağlanıyorsa),
     · daha önce KALINAN ders (transkriptte FAILED): tekrarı ertelenirse FF/VF
       ortalamada kalmaya devam eder ve açtığı dersler de gecikir. Gerçek
       katalogda (BLGE, 5. yarıyıl) ikinci öneri FF'li FIZ 102E çıkıyordu.
   Çıkar düğmesi `removeCourse` — geri alınabilir. Öneri puanına ve motorun
   önerisine dokunmuyor: karar öğrencinin. */
function hafifletmeOnerisi(ps, pz){
  const F = DATA.secondFloor;
  const tabanVar = F && F.min && !F.undeclared && tabanDurumu(F).ok;
  const kalinan = new Set(((SETUP && SETUP.transcript) || [])
    .filter(t => t.status === "FAILED").map(t => t.course));
  const adaylar = ps.filter(p => !p.cand.critical && !kilitliMi(p.cand.course, p.sec.crn)
                               && !kalinan.has(p.cand.course))
    .filter(p => {
      if(!tabanVar || p.cand.role === "ANADAL") return true;
      return tabanDurumu(F).kredi - (p.cand.credits || 0) + 1e-9 >= F.min;
    })
    .map(p => {
      const kalan = programZorlugu(ps.filter(x => x !== p).map(x => x.cand));
      return {p, yeni: kalan.donem, kademe: kalan.donemKademe,
              dusus: Math.round((pz.donem - (kalan.donem ?? pz.donem)) * 10) / 10};
    })
    .filter(x => x.dusus > 0)
    .sort((a, b) => b.dusus - a.dusus || (a.p.cand.score || 0) - (b.p.cand.score || 0))
    .slice(0, 2);
  if(!adaylar.length) return `<div class="hafiflet"><span class="ozetnot">Kritik yol, kilit
    ve tekrar alınan dersler dışında çıkarılabilecek ders bulunmamaktadır.</span></div>`;
  return `<div class="hafiflet"><div class="ozetbaslik">Dönemi hafifletmek için</div>${
    adaylar.map(x => `<div class="ozetdolusatir"><b class="mono">${esc(x.p.cand.course)}</b>
      <button class="ghost mini" data-hafiflet="${esc(x.p.cand.course)}">çıkar</button>
      <span class="ozetnot">— çıkarılırsa dönem zorluğu <span class="mono">${zp(pz.donem)}</span>
        → <b class="mono">${zp(x.yeni)}</b> (${ZORLUK_AD[x.kademe]}) · öneri puanı
        <span class="mono">−${Math.round(x.p.cand.score || 0)}</span>; ders sonraki dönemlere kalır</span></div>`
    ).join("")}</div>`;
}
const DONEM_ZORLUK_IPUCU = "Dönem zorluğu ders sayısı ve AKTS ile artar: AKTS dersin gerektirdiği "
  + "emeğin ölçüsüdür. Her dersin AKTS'si not dağılımından gelen zorluğuna göre ağırlıklandırılıp "
  + "toplanır (çok kolay 0.5 … orta 1.0 … çok zor 1.5); 60 ağırlıklı AKTS 10/10 sayılır, 30 "
  + "AKTS'lik orta yük yaklaşık 5/10'dur. AKTS'si bilinmeyen dersin AKTS'si kredisinin 1.75 katı, "
  + "zorluk verisi olmayan ders orta sayılır. Ders ortalaması AKTS ağırlıklıdır. Geçmiş not "
  + "dağılımından tahmindir; öneri puanına dahil değildir.";
const ZORLUK_AD = {1: "çok kolay", 2: "kolay", 3: "orta", 4: "zor", 5: "çok zor"};

/* ---------- geçmiş dönem not dağılımı (Faz 38) ----------
   İTÜ her dönem ders bazında harf notu dağılımı yayınlıyor
   (obs.itu.edu.tr/public/DersNotDagilimi). Bu bölüm o veriyi GÖSTERİR;
   öneri puanına GİRMEZ.

   ⚠️ Dört şeyi açıkça yazmak zorundayız, yoksa sayı olduğundan fazlasını
   iddia eder:
     1. Dağılım TR+EN kodun İKİSİNİ birden kapsıyor (kaynak öyle yayınlıyor).
     2. GEÇMİŞ bir döneme ait; hocası, sınavı, kontenjanı değişmiş olabilir.
     3. VF FF'ten AYRI yazılıyor. ★ Faz 88: VF yalnız devamsızlık değil —
        final sınavına girme koşulunu (devam, vize/ödev barajı) sağlayamayan
        öğrenci (kullanıcı, Faz 87). Tahmini zorlukta geçemeyenlere sayılıyor;
        "zorluğu göstermez" demek o hesapla çelişiyordu.
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
    ? ND_HARF.concat(["BL", "BZ"].filter(k => donem.counts[k]))   /* Faz 85 */
        .map(k => ({key: k, total: donem.counts[k] || 0,
                         parts: [{grade: k, n: donem.counts[k] || 0}]}))
    : donem.buckets;
  const enBuyuk = Math.max(...kutu.map(b => b.total), 1);
  const bar = kutu.map(b => {
    const kotu = (b.key === "FF" || b.key === "VF" || b.key === "BZ");
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
    <b>${esc(g.wantedSeason)}</b> dönemine ait dağılım bulunmamaktadır;
    <b>${esc(donem.season)}</b> dönemi gösterilmektedir. Dersin olağan yarıyılı
    dışında dersi çoğunlukla <b>tekrar alan öğrenciler</b> aldığından bu dağılım
    dersin olağan dönemini yansıtmayabilir.</div>` : "";

  return `<details class="puan" data-ndbox="${esc(cand.course)}">
    <summary>Not dağılımı — <b class="mono">${donem.n}</b> kişi,
      geçen <b class="mono">%${donem.passRate}</b></summary>
    ${sekme}${uyari}
    <div class="ndgrafik${artili ? " genis" : ""}">${bar}</div>
    <div class="ndozet">
      <span>ortalama <b class="mono">${donem.meanPoints ?? "—"}</b></span>
      <span>FF <b class="mono">%${donem.failRate}</b></span>
      <span title="Final sınavına girme koşulunu sağlayamayan öğrenciler (devamsızlık ya da vize/ödev barajı); tahmini zorlukta geçemeyenlere sayılır">
        VF <b class="mono">%${donem.absentRate}</b></span>
      <span>${esc(donem.yearName)} ${esc(donem.season)}</span>
      <button class="ghost mini" data-ndplus="${esc(cand.course)}"
        >${artili ? "artıları birleştir" : "artıları ayır"}</button>
    </div>
    <div class="puantoplam">
      ${artili ? "15 harf notu ayrı ayrı gösterilmektedir."
        : "Okunabilirlik için <b>artılı notlar temel harfle birlikte</b> "
          + "sayılmıştır (BA+ → BA). Ayrıntı üstteki düğmeyle görüntülenebilir; "
          + "<b>ortalama her zaman 15 harf notundan</b> hesaplanır."}
      <br>Kaynak: ${disLink("obsNot", "İTÜ OBS Ders Not Dağılımı", donem.url)} · <b>${g.codes.map(esc).join(" + ")}</b>
      birlikte (OBS, Türkçe ve İngilizce kodları ayırmamaktadır)${
      g.terms.length > 1 ? ` · ${g.terms.length} döneme ait veri mevcut` : ""}.${
      /* ⚠️ Kaynağın kendi toplamı harflerin toplamına her zaman eşit değil
         (ölçüm: MAT 103 güz 2988/2987). Farkı yazmamak, sayıyı olduğundan
         kesin gösterirdi. */
      donem.gap ? `<br>OBS toplamı <b class="mono">${donem.announced}</b>;
        harf notlarının toplamı <b class="mono">${donem.n}</b>; ${donem.gap} öğrenci
        listelenen 15 harf notunun dışındadır (BL/BZ/muafiyet olabilir).` : ""}
      <br>⚠️ Veriler <b>geçmiş</b> bir döneme aittir; öğretim üyesi, sınav ve
      kontenjan değişmiş olabilir. Bu bilgi öneri puanına <b>dahil edilmez</b>.
      Ortalama, aracın GNO ölçeğiyle hesaplanır: <b>FF</b> ve <b>VF</b> sıfır
      puandır. <b>VF</b>, final sınavına girme koşulunu sağlayamayan öğrencileri
      gösterir (devamsızlık ya da vize/ödev barajı); tahmini zorlukta geçemeyenlere sayılır.
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

   ⚠️ Bu repoda kip politikası zaten yazılıydı (27.08.2026, boş saat
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
      cand.pool ? " · havuz: " + esc(cand.pool) : ""}${
      cand.denkOf ? " · " + esc(cand.denkOf) + " yerine (resmî denklik)" : ""}</div>
    <h2 class="mono">${esc(cand.course)}</h2>
    <div style="color:var(--ink-2);font-size:var(--fs-md);margin:2px 0 6px">${esc(cand.name)}</div>
    <div class="meta" style="color:var(--ink-3);font-size:var(--fs-sm)">
      ${cand.credits} kredi · ${cand.ects} AKTS
      ${cand.reasons.length ? "<br>" + cand.reasons.map(esc).join("; ") : ""}</div>
    ${disKip ? `<div class="why" style="margin-top:8px">Bu ders
      <b>${esc(M().label || "bu kip")}</b> kipinin aday havuzunda bulunmamaktadır.
      Ders programda yer almakta olup şubesi buradan değiştirilebilir; ancak bu kip
      dersi <b>kendiliğinden önermez</b> ve ders çıkarıldığında geri eklenmez.
      ${onerenKip >= 0 ? `Öneren kip: <b>${esc(MODES[onerenKip].label)}</b>.`
        : ""}</div>` : ""}
    ${puanKirilimi(cand)}
    ${zorlukKutusu(cand)}
    ${notDagilimi(cand)}
    <div class="dislinkler">Resmî kaynaklarda: ${disLink("obsProgram", "şube ve kontenjan (OBS Ders Programı)")}
      · ${disLink("obsPlan", "önşart ve ders planı (OBS Ders Planları)")}</div>
    ${fits.length ? `<div class="chipline"><span class="chip">başka şube</span>
      <span style="color:var(--ink-3);font-size:var(--fs-sm)">${fits.length} seçenek</span></div>
      <div class="optlist">${fits.map(s => optionRow(cand, s, "")).join("")}</div>` : ""}
    ${busy ? `<div style="color:var(--ink-3);font-size:var(--fs-sm);margin-top:10px">
      ${busy} şube daha bulunmaktadır; ancak bu şubeler programla çakışmaktadır.</div>` : ""}
    <div class="chipline"><span class="chip unknown">yerine başka ders</span></div>
    <div class="optlist">${swaps.join("") ||
      `<div class="empty">bu saatlere uyan başka aday ders bulunmamaktadır</div>`}</div>
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
      <span class="mono">make watch</span> çalıştırıldığında bu dersler taranır
      (arka planda: <span class="mono">make watch-kur</span>).</div>`;
  if(list.size === 0)
    return `<div class="why" style="margin-top:8px">İzleme listesi şu anda <b>boştur</b>;
      bu nedenle nöbet <b>plandaki tüm açık dersleri</b> taramaktadır. Her turda
      değişiklik olacağından bildirimler ayırt edilemez hâle gelebilir. Bu ders
      eklendiğinde nöbet <b>yalnızca bu dersi</b> izler.</div>`;
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
      if(disinda(cand.course)) notlar.push("üst dönem; bu kipte önerilmez");
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
         <span style="color:var(--ink-3);font-size:var(--fs-sm)">${liste.length} ders</span></div>
       <div class="optlist">${liste.slice(0, 12).map(r => r[1]).join("")}</div>` : "";
  openDialog(`
    <div class="eyebrow">Boş saat</div>
    <h2>${DAYS[day-1]} ${hhmm(min)}</h2>
    ${hicTemiz && varTakas ? `<div class="note" style="margin-bottom:12px">
        <b>Bu saate çakışmadan yerleştirilebilecek ders bulunmamaktadır.</b>
        <div style="margin-top:4px">Aşağıdaki <b>${varTakas}</b> dersten biri
        için programda <b>yer açılması</b> gerekmektedir; her birinin altında
        çıkarılacak ders belirtilmiştir.</div></div>` : ""}
    ${grup("bu saate uygun", "", nearT)}
    ${grup(DAYS[day-1] + " günü, başka saatte uygun", "", restT)}
    ${grup("yer açılması gerekir — bu saat civarı", "unknown", nearX)}
    ${grup("yer açılması gerekir — " + DAYS[day-1] + " günü", "unknown", restX)}
    ${(!near.length && !rest.length)
      ? `<div class="empty">bu güne uyan aday ders bulunmamaktadır</div>` : ""}
    ${LIVE ? `<div style="margin-top:14px;padding-top:12px;
         border-top:1px solid var(--border)">
      <button class="ghost" id="busyAdd">Bu saati derse kapat</button>
      <div class="why" style="margin-top:6px">Okul dışı bir yükümlülük (staj,
        antrenman, servis vb.) bulunuyorsa bu saat kapatılabilir; araç bu saate
        ders yerleştirmez.</div></div>` : ""}`);
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
      <div class="meta" style="color:var(--ink-2);font-size:var(--fs-md);margin:4px 0 14px">
        ${b.ok ? `${DAYS[b.day-1]} ${hhmm(b.start)}–${hhmm(b.end)}`
               : `<span class="mono">${esc(remove)}</span> — satır okunamadı`}
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
    <p class="modenote" style="margin:2px 0 10px">Araç bu aralığa ders
      yerleştirmez. Kaldırmak için ızgaradaki taralı bloğa tıklayınız.</p>
    <label class="field"><span>Gün</span>
      <div class="terms" id="fGun">
        ${DAYS.map((d, i) => `<button data-d="${i+1}"
          aria-pressed="${i+1 === day}" style="width:auto;padding:8px 12px"
          >${d}</button>`).join("")}
      </div></label>
    <label class="field" style="margin-top:12px"><span>Saat</span>
      <div style="display:flex;gap:8px;align-items:center">
        <input type="time" id="fBas" value="${hhmm(bas)}" step="900">
        <span style="color:var(--ink-3)">–</span>
        <input type="time" id="fBit" value="${hhmm(bit)}" step="900">
      </div></label>
    <label class="field" style="margin-top:12px"><span>Açıklama</span>
      <input type="text" id="fAd" maxlength="40" placeholder="iş, antrenman, servis…">
      <span class="hint">İsteğe bağlıdır; ızgarada bu metin gösterilir.</span></label>`, () => {
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
const FILT = {q: "", role: "", free: false, fit: false, sort: ""};
const LIMIT = 30;

/* ★★ FAZ 74 — "PROGRAMIMA DAHA NE SIĞAR?"
   Kayıt haftasının en sık sorusu. Aday listesi yalnız "kontenjanı olanlar"
   diye süzülebiliyordu; hangisinin programdaki derslerle çakışmadan ve dönem
   sınırını aşmadan eklenebileceğini bulmak için her dersin penceresini açıp
   şubelere tek tek bakmak gerekiyordu. Bir ders SIĞAR, eğer:
     · programda değilse ve aynı havuzdan seçili bir dersi çıkarmıyorsa,
     · yükü dönem sınırına sığıyorsa (sınır biliniyorsa),
     · en az bir şubesi: saati İLAN EDİLMİŞ (saatsiz şube çakışmıyor
       görünür ama bilinmiyor — bilinmeyen bilinen gibi gösterilmez),
       kontenjanı dolu değil (ilan edilmemiş kontenjan dolu sayılmaz),
       programla ve meşgul saatlerle çakışmıyor.
   Uyan şube satırda CRN'iyle yazıyor. */
function sigdigiSube(c, kalan){
  if(sel.some(x => x.course === c.course) || poolBlocker(c, null)) return null;
  if(loadOf(c) > kalan + 1e-9) return null;
  return c.sections.filter(s => (s.meetings || []).length
      && (!s.capacity || yerSayisi(s) > 0)
      && !conflictsWith(s, c.course).length && !mesgulCakisir(s))
    .sort((a, b) => yerSayisi(b) - yerSayisi(a))[0] || null;
}
const kalanYuk = () => DATA.maxLoad ? DATA.maxLoad - totals().load : Infinity;
/* ★★ FAZ 76 — SEÇMELİ SEÇERKEN GEÇMİŞ NOT DAĞILIMI LİSTEDE.
   Öğrenci seçmeli ararken OBS'nin not dağılımı sayfasını ders ders açıyor;
   veri (Faz 38) sayfada zaten vardı ama yalnız dersin penceresinde. Satırda
   kısa özet (seçmeli havuz dersleri için her zaman, sıralama "geçmiş not
   ortalaması" iken hepsi için) ve isteğe bağlı sıralama. Faz 38'in kuralı
   aynen: bu bilgi öneri PUANINA girmiyor; sıralama yalnız görüntü. Dönem,
   dersin penceresindeki varsayılanla aynı (`grades.selected`); dersin olağan
   yarıyılı dışındaysa (çoğunlukla tekrar alanlar) bunu yazıyor. */
function gecmisOzet(c){
  const g = c.grades;
  if(!g || !(g.terms || []).length) return null;
  const d = g.terms.find(t => t.term === g.selected) || g.terms[0];
  if(!d || !d.n || typeof d.meanPoints !== "number") return null;
  return {ort: d.meanPoints, gecen: d.passRate, n: d.n,
          etiket: `${d.yearName} ${d.season}`,
          mevsimDisi: !!g.wantedSeason && d.season !== g.wantedSeason};
}
const bosYer = (c) => c.sections.reduce((a, s) => a + yerSayisi(s), 0);
function siralanmis(l){
  if(FILT.sort === "ort") return l.map((c, i) => [c, i]).sort(([a, i], [b, j]) => {
    const x = gecmisOzet(a), y = gecmisOzet(b);
    return (y ? y.ort : -1) - (x ? x.ort : -1) || i - j;
  }).map(([c]) => c);
  /* Faz 85/87 — kolaydan zora, genel puana (10 üzerinden) göre; verisi
     olmayan sonda (sırası korunarak). */
  if(FILT.sort === "zor") return l.map((c, i) => [c, i]).sort(([a, i], [b, j]) => {
    const x = zorlukOf(a), y = zorlukOf(b);
    return (x ? x.score : 99) - (y ? y.score : 99) || i - j;
  }).map(([c]) => c);
  if(FILT.sort === "bos") return l.map((c, i) => [c, i])
    .sort(([a, i], [b, j]) => bosYer(b) - bosYer(a) || i - j).map(([c]) => c);
  return l;
}
function filteredCandidates(){
  const q = FILT.q.trim().toLocaleLowerCase("tr");
  const kalan = kalanYuk();
  return M().candidates.filter(c => {
    if(FILT.role && c.role !== FILT.role) return false;
    if(FILT.free && !c.sections.some(s => s.free > 0)) return false;
    if(FILT.fit && !sigdigiSube(c, kalan)) return false;
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
  return `<span class="cap ${sinif}" title="${esc(veriTarihi())} itibarıyla; güncel doluluk bilgisi OBS'dedir">
      <span class="capbar"><i style="width:${(oran * 100).toFixed(0)}%"></i></span>
      <span class="mono">${bos === 0 ? "dolu" : bos + " boş"}</span>
      <span class="mono capsub">${sections.length} şube</span></span>`;
}

/* ★★ FAZ 56 — SEÇİLİ ŞUBENİN YERİ IZGARADA.
   Aday listesi doluluğu gösteriyordu (`doluluk`), ama programın kendisi —
   kayıt gününe götürülen ızgara — göstermiyordu: vitrin verisinde önerilen
   programın bir şubesi 70/70 DOLUYDU ve blokta hiçbir işaret yoktu. Kayıt
   gününde ilk düşülen yer burası.
   ⚠️ Eşik `doluluk` ile AYNI (0 → dolu, ≤3 → son N): aynı şube iki yerde
   iki farklı durumda görünmesin. Boş olan şubede işaret YOK — ızgara
   gürültüsü ancak dikkat gerektiren şeyi söylemeli. İşaret yalnız renk
   değil: sözcük + çerçeve (zorlanmış renk kipinde de okunuyor). */
/* ★★ Faz 94 — YERLEŞKE GEÇİŞİ. İTÜ'de ders :29'da bitiyor, sonraki :30'da
   başlıyor. Arka arkaya iki ders farklı yerleşkedeyse (Ayazağa → Maçka)
   araya bir dakika kalıyor ve öğrenci bunu programa bakarak göremiyordu —
   "kampüs değişimi" sayısı üç saatlik arayı da bir dakikalık arayı da aynı
   sayıyordu. Artık ikinci derste işaret var.
   ⚠️ Katalogda yol süresi YOK; eşik (60 dk) bir kabul, bir ölçüm değil.
   Bu yüzden söz "yetişemezsiniz" değil, "arada N dakika var". Yerleşkesi
   bilinmeyen ders (çevrimiçi ya da bina ilan edilmemiş) uyarı üretmiyor. */
const YERLESKE_ESIK_DK = 60;
const kisaYerleske = (k) => (k || "").split(" ")[0];
function yerleskeGecisi(p, m){
  if(!p || p.sec.online || !m || !m.campus) return null;
  let onceki = null;
  picks().forEach(q => {
    if(q.sec.online) return;
    q.sec.meetings.forEach(n => {
      if(n.day !== m.day || n.end > m.start) return;
      if(!onceki || n.end > onceki.m.end) onceki = {p: q, m: n};
    });
  });
  if(!onceki || !onceki.m.campus || onceki.m.campus === m.campus) return null;
  const ara = m.start - onceki.m.end;
  return ara < YERLESKE_ESIK_DK
    ? {ders: onceki.p.cand.course, nereden: kisaYerleske(onceki.m.campus),
       nereye: kisaYerleske(m.campus), ara} : null;
}
function gecisNotu(p, m){
  const g = yerleskeGecisi(p, m);
  if(!g) return "";
  const t = `Önceki ders (${g.ders}) ${g.nereden} yerleşkesinde, bu ders ${g.nereye} ` +
    `yerleşkesinde; arada ${g.ara} dakika var. Yerleşkeler arası yol bu sürede ` +
    `yetişmeyebilir.`;
  return ` <span class="yerdurum az gecis" title="${esc(t)}">⚠ ${esc(g.nereden)} → ${
    esc(g.nereye)} · ${g.ara} dk</span>`;
}
function yerDurumu(sec){
  const cap = (sec && sec.capacity) || 0;
  if(!cap) return "";
  const bos = Math.max(0, typeof sec.free === "number"
    ? sec.free : cap - (sec.enrolled || 0));
  const not = `${veriTarihi()} itibarıyla; güncel doluluk bilgisi OBS'dedir`;
  if(bos === 0) return ` <span class="yerdurum dolu" title="Kontenjan dolu · ${esc(not)}">dolu</span>`;
  if(bos <= 3) return ` <span class="yerdurum az" title="${bos} yer kaldı · ${esc(not)}">son ${bos}</span>`;
  return "";
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
  const hepsi = siralanmis(filteredCandidates());
  /* ★ Arama yapılmışken kesme YOK: aradığın ders 40. sıradaysa da gelmeli. */
  const list = FILT.q.trim() ? hepsi : hepsi.slice(0, LIMIT);
  const cnt = $("#candCount");
  const kalan = kalanYuk();
  /* Seçmeli havuz yuvası programda doluysa ders "sığmıyor": eklemek o yuvadaki
     dersi çıkarır (`choose` ile aynı kural). Gerçek sitede 6 kredi boş kalıp
     "0 ders" yazınca nedeni görünmüyordu — sayıyla birlikte söylüyoruz. */
  const havuzDolu = FILT.fit ? M().candidates.filter(c =>
    !chosen.has(c.course) && poolBlocker(c, null)).length : 0;
  if(cnt && FILT.fit) cnt.textContent = `${hepsi.length} ders programa sığıyor${
    kalan !== Infinity ? ` · sınıra ${+kalan.toFixed(1)} ${DATA.unitLabel} kaldı` : ""}${
    havuzDolu ? ` · ${havuzDolu} seçmeli dersin havuz yuvası programda dolu`
      + " (eklenirse o yuvadaki dersin yerine geçer)" : ""}`;
  else if(cnt) cnt.textContent = hepsi.length === M().candidates.length
    ? (hepsi.length > list.length
        ? `${M().candidates.length} aday · ilk ${list.length} listeleniyor`
        : `${hepsi.length} aday`)
    : `${M().candidates.length} adaydan ${hepsi.length} tanesi`;
  if(cnt && FILT.sort === "ort") cnt.textContent += " · geçmiş not ortalamasına göre"
    + " sıralı (öneri puanına dahil değildir; verisi olmayanlar sonda)";
  if(cnt && FILT.sort === "zor") cnt.textContent += " · tahmini zorluğa göre sıralı, kolaydan"
    + " zora (öneri puanına dahil değildir; verisi olmayanlar sonda)";
  $("#cands tbody").innerHTML = list.map(c => {
    const free = Math.max(0, ...c.sections.map(s => s.free));
    const inPlan = chosen.has(c.course);
    const uyan = FILT.fit ? sigdigiSube(c, kalan) : null;
    const gecmis = (c.pool || FILT.sort === "ort") ? gecmisOzet(c) : null;
    return `<tr data-course="${esc(c.course)}" style="cursor:pointer"
        title="${inPlan ? "programda" : "programa ekle"}">
      <td class="mono score">${c.score}</td>
      <td><b class="mono">${esc(c.course)}</b>
        ${inPlan ? `<span class="chip" style="margin-left:6px;color:var(--ok)">programda</span>` : ""}
        ${c.critical ? `<span class="chip supply" style="margin-left:6px">kritik yol</span>` : ""}
        ${c.denkOf ? `<span class="chip prereq" style="margin-left:6px"
          title="Plandaki ${esc(c.denkOf)} dersinin resmî denkliği; şubesi programınıza açık olduğundan dilekçe gerekmez. Bu ders geçilince ${esc(c.denkOf)} yuvası dolar.">${esc(c.denkOf)} yerine</span>` : ""}
        ${c.prereqUnknown ? `<span class="chip unknown"
          style="margin-left:6px" title="Önşart metni bulunmakla birlikte okunamamıştır; danışmanınıza danışınız">önşart okunamadı</span>`
          : (c.prereqMissing ? `<span class="chip unknown" style="margin-left:6px"
              title="Katalogda önşart metni bulunmamaktadır; bu, dersin önşartı olmadığı anlamına gelmez. OBS'den doğrulayınız.">önşart bilgisi yok</span>` : "")}
        ${zorlukRozet(zorlukOf(c))}
        ${c.sections.every(s => s.online)
          ? `<span class="chip online" style="margin-left:6px">çevrimiçi</span>`
          : (c.sections.some(s => s.online)
             ? `<span class="chip online" style="margin-left:6px">çevrimiçi şube var</span>` : "")}
        <div class="why">${esc(c.name)}${c.reasons.length
          ? " — " + c.reasons.map(esc).join("; ") : ""}${acilanNot(c)}</div>${uyan
          ? `<div class="why uyansube">uyan şube: CRN <span class="mono">${esc(uyan.crn)}</span>
             · ${uyan.meetings.map(m => `${DAYS[m.day - 1]} ${hhmm(m.start)}`).join(", ")}${
             uyan.capacity ? ` · ${yerSayisi(uyan)} boş yer` : " · kontenjan ilan edilmemiş"}</div>` : ""}${gecmis
          ? `<div class="why ndkisa">geçmiş dönem: ortalama <b class="mono">${gecmis.ort}</b>
             · %${gecmis.gecen} geçti · n=${gecmis.n} (${esc(gecmis.etiket)})${gecmis.mevsimDisi
             ? ` · <span class="uyari">olağan yarıyılı dışı</span>` : ""}</div>` : ""}</td>
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
    (FILT.q || FILT.role || FILT.free || FILT.fit)
      ? `süzgece uyan ders bulunmamaktadır — <a href="#" id="candClear">süzgeci temizle</a>`
      : (M().candidates.length
          ? "aday ders bulunmamaktadır"
          : (DATA.emptyReason
             || "aday ders bulunmamaktadır; bölüm ve başarılan ders bilgilerini kontrol ediniz"))
  }</td></tr>`;
  $("#cands tbody").querySelectorAll("tr[data-course]").forEach(tr =>
    tr.addEventListener("click", () => addDialog(tr.dataset.course)));
  const clr = $("#candClear");
  if(clr) clr.addEventListener("click", (e) => {
    e.preventDefault();
    FILT.q = ""; FILT.role = ""; FILT.free = false; FILT.fit = false;
    $("#candQ").value = ""; $("#candFree").checked = false; $("#candFit").checked = false;
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
$("#candFit").addEventListener("change", (e) => {
  FILT.fit = e.target.checked; renderCandidates();
});
$("#candSort").addEventListener("change", (e) => {
  FILT.sort = e.target.value; renderCandidates();
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

/* ★★ FAZ 83 — GEÇMİŞTE AÇILDIĞI DÖNEMLER (not dağılımından).
   Kullanıcı: "geçmişteki not dağılımlarından derslerin hangi dönemlerde
   açıldığı ile ilgili küçük bir bilgi geç, doğruluğunun belirsiz olduğunu
   belirterek". Ham veri: not açıklanmış her dönem, öğrenci sayısıyla. Az
   öğrencili dönem çoğunlukla tekrar/bütünleme sınıfı — sayı bunu görünür
   kılıyor; açıklama doğruluğun belirsiz olduğunu söylüyor. */
const kisaDonem = (l) => String(l || "").replace(/^(\d{4})-\d{2}(\d{2})/, "$1-$2");
function gecmisDonemNotu(cand){
  const T = ((cand && cand.grades && cand.grades.terms) || []).filter(t => t.n > 0);
  if(!T.length) return "";
  return `<div class="gecmisnot"><b>Geçmişte açıldığı dönemler</b>
    (not dağılımına göre): ${T.slice(0, 6).map(t => `${esc(kisaDonem(`${t.yearName} ${t.season}`))}
      <span class="mono">(${t.n} öğrenci)</span>`).join(" · ")}
    <div class="meta">Yalnızca not açıklanmış dönemleri gösterir; az öğrencili dönem
      çoğunlukla tekrar veya bütünleme sınıfıdır. Doğruluğu belirsizdir; dersin ileride
      aynı dönemlerde açılacağı kesin değildir.</div></div>`;
}
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
    <div style="color:var(--ink-2);font-size:var(--fs-md);margin:2px 0 6px">${esc(cand.name)}</div>
    ${pool ? `<div class="note" style="margin-top:8px">Aynı havuzdan
      <b class="mono">${esc(pool.cand.course)}</b> seçilidir; bu ders eklendiğinde o ders çıkarılır.</div>` : ""}
    <div class="optlist">${rows.map(r => r[1]).join("")}</div>
    ${zorlukKutusu(cand)}
    ${gecmisDonemNotu(cand)}`);
}

/* ---------- darboğaz ---------- */
const LABELS = {
  KREDI_ESIGI:["kredi eşiği dolmamış","credit"],
  PROGRAMA_KAPALI:["şubeleri programa kapalı","supply"],
  ACILMAMIS:["bu dönem açılmamış","supply"],
  /* ★ Faz 111 — yalnız ek/sınırsız sınav şubesi açılmış ders. Arz sorunu
     değil (izleme düğmesi yok): ders bu dönem okutulmuyor, açılan şube
     azami süreyi dolduranın sınav hakkı. */
  EK_SINAV:["yalnız ek sınav açılmış","unknown"],
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
        ? `<span class="chip" style="color:var(--ok)">tamam</span>`
        : (LIVE && s !== sonraki
            ? `<button class="ghost" data-act="${s.action}"
                 ${kilitli ? "disabled title='Önce bölüm seçiniz'" : ""}
                 >${esc(s.cta)}</button>`
            : (s === sonraki
               ? `<span class="chip" style="color:var(--seal)">şimdi ↑</span>` : ""))}
      <span class="sure">${esc(s.sure)}</span>
    </div>`;

  box.innerHTML = `
    <div class="sechead"><div class="eyebrow">Başlangıç</div><div class="rule"></div></div>
    <h2>${!acik ? "Hoş geldiniz"
      : (calisiyorMu() ? "Program oluşturuldu"
                       : "Program oluşturulamadı")}</h2>
    <p class="lead">${acik
      ? (calisiyorMu()
        ? `Haftalık program oluşturulmuştur. Aşağıdaki adımlar <b>isteğe
           bağlıdır</b>; tamamlandığında öneriler durumunuza göre yeniden oluşturulur.`
        /* ★★ İnceleme B1: bu cümle ızgara BOŞ ve "öneri üretilemedi" yazarken
           de duruyordu. Başlık motorun ÇIKTISINA bakmalı, ayarın varlığına
           değil. */
        : `<b>Öneri üretilemedi.</b> ${esc(DATA.emptyReason
            || "Aday ders bulunamadı. Başarılan dersleri ve yarıyıl bilgisini giriniz.")}`)
      : `Bu araç, İTÜ'de bu dönem açılan derslerden <b>çakışmasız bir haftalık
         program</b> oluşturur; önşart, kontenjan ve kredi koşullarını denetler.
         Başlamak için <b>yalnızca bölüm seçimi gereklidir</b>. Çift anadal veya
         yandal programına kayıtlı olmayan öğrenciler de aracı kullanabilir.`}</p>

    ${sonraki && LIVE ? `
      <div class="heroCta">
        <button class="ghost primary big" data-act="${sonraki.action}"
          >${esc(sonraki.cta)}</button>
        <span class="meta">${esc(sonraki.sure)}${
          sonraki.required ? "" : " · isteğe bağlı"}</span>
        ${acik ? `<a href="#schedSection" class="heroSkip">Programa git ↓</a>
          <button class="ghost heroDismiss" data-kapat="1"
            >Bu adımları atla</button>` : ""}
      </div>` : ""}

    <div class="steps">${zorunlu.map(s => stepHTML(s, false)).join("")}</div>
    ${istege.length ? `
      <div class="stepsplit">Öneriyi iyileştirmek için ${
        acik ? "" : "(bölüm seçiminden sonra)"}</div>
      <div class="steps">${istege.map(s => stepHTML(s, !acik)).join("")}</div>` : ""}

    <div class="herofoot">
      Seçilebilecek <b class="mono">${O.planCount}</b> bölüm ve
      <b class="mono">${O.lessonCount}</b> açık şube bulunmaktadır.
      ${LIVE ? "" : `Bu kopya <b>salt okunurdur</b>; düzenleme için uygulamayı
        <span class="mono">make app</span> ile başlatınız.`}
      <div style="margin-top:6px">${siteMi()
        ? "Girilen bilgiler hiçbir sunucuya gönderilmez; veriler tarayıcıda saklanır."
        : "Girilen bilgiler bu bilgisayarda saklanır (<span class=\"mono\">data/</span>)."}
        Ders ve şube verileri ${disLink("ituHelper", "İTÜ Helper")} açık veri projesinden,
        ders planları ${disLink("obsPlan", "İTÜ OBS")}'den alınmaktadır.</div>
      ${/* ★ Faz 54: YENİ CİHAZDA yedekten devam — Ayar görünümü kurulum
            bitmeden gizli, yedeği yüklemenin tek yolu burası. */ ""}
      ${siteMi() && window.__ITUCAP_YEDEK__ ? `<div class="heroyedek">Başka bir
        tarayıcıda çalışılmışsa:
        <button class="ghost mini" id="heroYedek">yedekten devam et…</button>
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
    <b>Program hazırdır. Sonraki adımlar:</b>
    <div class="sonrakiliste">
      <button class="ghost" data-go="schedSection">Haftalık program</button>
      <button class="ghost" data-go="candSection">Ders ekle / değiştir</button>
      ${tercihGoster ? `<button class="ghost" data-go="tercih"
        title="Başlangıç saati, boş gün gibi tercihler.
Hiçbir dersi elemez; yalnızca sıralamayı değiştirir."
        >Program tercihleri</button>` : ""}
      <button class="ghost" data-go="crn">Kayıt günü listesi</button>
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
  ["schedSection", "Haftalık program", "PLANLA", "Program", false],
  ["candSection", "Alınabilecek dersler", "PLANLA", "Dersler", false],
  ["blockSection", "Alınamayan dersler", "PLANLA", "Engeller", false],
  ["savedSection", "Kaydedilen program", "PLANLA", "Kayıtlı", true],
  ["panels", "İlerleme durumu", "DURUM", "İlerleme", false],
  /* Faz 57 — mezuniyet yol haritası. Telefonda "Daha" altında: dönemde
     birkaç kez bakılan bir şey, kayıt haftasının dört işinden biri değil. */
  ["roadmapSection", "Yol haritası", "DURUM", "Harita", true],
  ["creditSection", "Kredi ve not eşikleri", "DURUM", "Kredi", true],
  ["suggestSection", "Sayılabilecek dersler", "DURUM", "Sayılan", true],
  ["denklikSection", "Denk dersler", "DURUM", "Denklik", true],
  ["changeSection", "Son değişiklikler", "DURUM", "Değişen", true],
  ["basvuruSection", "Başvuru", "DURUM", "Başvuru", true],
  ["tierSection", "Kademeler", "DURUM", "Kademe", true],
  /* ★ Kurulum çubuğu da bir görünüm (Faz 46): her ziyarette bakılan bir
     şey değil, ama kaybolmamalı — bölüm/dönem/not düzeltmenin tek yeri. */
  ["setupbar", "Bölüm, yarıyıl, notlar", "AYAR", "Ayar", true],
  /* Faz 96 — kullanım kılavuzu; her zaman açık, telefonda "Daha" altında. */
  ["yardimSection", "Kullanım kılavuzu", "YARDIM", "Kılavuz", true],
];

/* Kılavuzdaki "git" düğmeleri ilgili görünümü açıyor. ⚠️ Görünüm o an
   kapalıysa (ör. henüz kaydedilmiş program yok) `gorunumAc` sessizce ilk
   görünüme düşerdi — "Kaydedilen program"a basan haftalık programa
   gidiyordu. Onun yerine kılavuzda kalıp nedenini söylüyoruz. */
document.addEventListener("click", ev => {
  const b = ev.target.closest && ev.target.closest("#yardimSection [data-git]");
  if(!b) return;
  const eski = b.nextElementSibling;
  if(eski && eski.classList.contains("yardimnot")) eski.remove();
  if(acikGorunumler().some(([x]) => x === b.dataset.git)){
    gorunumAc(b.dataset.git, true);
    return;
  }
  b.insertAdjacentHTML("afterend", `<span class="yardimnot" role="status">Bu bölüm şu an
    gösterilecek veri olmadığı için kapalı (ör. henüz kaydedilmiş program ya da
    değişiklik yok).</span>`);
});
document.addEventListener("click", ev => {
  if(ev.target.closest && ev.target.closest("#kilavuzBtn")) gorunumAc("yardimSection", true);
});
/* Kılavuzdaki eylem düğmeleri (ör. "Plandan işaretle") kurulumdaki pencereyi
   AYNI işlevle açıyor — ikinci bir yol yazılmıyor. */
document.addEventListener("click", ev => {
  const b = ev.target.closest && ev.target.closest("#yardimSection [data-ac]");
  if(b && b.dataset.ac === "plan") checklistDialog();
});

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
  if(typeof kalmaOto === "function") kalmaOto();     // Faz 75
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

/* ★ Faz 56 — "İçeriğe atla" odağı `<main>`e TAŞIYOR; adres çubuğuna `#icerik`
   yazmıyor (paylaşılan bağlantı `#crn=` taşıyor, onu kirletmesin). */
(() => {
  const atla = document.querySelector(".atla");
  if(atla) atla.addEventListener("click", ev => {
    ev.preventDefault();
    const m = $("#icerik");
    if(!m) return;
    m.tabIndex = -1;
    m.focus();
  });
})();

/* ★★ FAZ 57 — MEZUNİYET YOL HARİTASI (`yolharitasi.kur`).
   Kademeler görünümü "ÇAP en az kaç dönem" diyordu; bu görünüm kalan
   dersleri dönem dönem yerleştirip her programın tahmini bitişini yazıyor.
   Asıl işe yarayan satır "bu dönem şunu alırsan": vitrin verisinde öneri 1
   GEO 341E'yi (Güz dersi, arkasında 2 derslik zincir) çakışma yüzünden
   dışarıda bırakıyordu ve bu anadalı BİR YIL geciktiriyordu — ekranda
   hiçbir yerde yazmıyordu.
   ⚠️ Varsayımlar planın ÜSTÜNDE ve görünür: gelecek dönemlerin arzı
   bilinmiyor; bilinmeyeni bilinen gibi göstermemenin tek yolu söylemek. */
/* ★ FAZ 59 — BİTİŞ KAÇINCI YARIYIL, AZAMİ SÜREYİ AŞIYOR MU.
   Öğrenci süreyi dönem adıyla değil yarıyıl sayısıyla düşünüyor ("10.
   yarıyılda biter"). Azami süre (`kurallar.toml` [azami_sure]) yalnız
   ANADAL için karşılaştırılıyor: ÇAP'ın kendi süre kuralını doğrulamadık,
   uydurmuyoruz. Doğrulanmamış sayı ⚠ ile ve kaynağıyla. */
/* Senaryodaki bitiş, bugünkü plandakine göre (aynı rol). */
function senaryoFarki(p, T){
  const b = (T.programs || []).find(x => x.role === p.role);
  const a = b && b.finish, y = p.finish;
  if(!a || !y) return y || !a ? "" : `<div class="yhgec">bu senaryoda bitiş hesaplanamadı</div>`;
  const d = y.index - a.index;
  return d > 0 ? `<div class="yhgec">mevcut plana göre <span class="mono">${d}</span> dönem geç</div>`
    : d < 0 ? `<div class="yhzamaninda">mevcut plana göre ${-d} dönem erken</div>`
    : `<div class="yhzamaninda">mevcut planla aynı</div>`;
}

function yariyilSatiri(p, md){
  if(!p.finishSemester) return "";
  const anadal = p.role === "ANADAL";
  const isaret = md && !md.verified ? " ⚠" : "";
  const baslik = md ? esc([md.source, md.verified ? "" : "doğrulanmadı", md.note]
    .filter(Boolean).join(" · ")) : "";
  const asti = anadal && md && p.finishSemester > md.semesters;
  return `<div class="yhalt"><span class="mono">${p.finishSemester}</span>. yarıyıl${
    anadal && md ? ` · <span class="aciklamali" title="${baslik}">azami ${
      md.semesters}${isaret}</span>` : ""}</div>${asti ? `<div class="yhgec">azami öğrenim
      süresini <span class="mono">${p.finishSemester - md.semesters}</span> yarıyıl
      aşmaktadır; danışmanınızla görüşmeniz önerilir</div>` : ""}`;
}

/* ★★ FAZ 61 — SENARYO: daha hafif dönem yükü, boş dönem (Erasmus/staj).
   "Çalışıyorum, en çok 18 kredi", "3. dönem Erasmus" — ikisi de bitişi
   değiştiriyor ve ikisi de ancak haritayı YENİDEN kurarak ölçülüyor
   (`/api/yolharitasi`, salt okunur). KAYDEDİLMİYOR: senaryo açıkken şerit
   bunu söylüyor, kartlar bugünkü plana göre farkı yazıyor. Durum yeniden
   kurulunca (boot) senaryo kapanıyor — eski bir tabana göre fark yazmasın. */
let YH_SENARYO = null, YH_AYAR = null;
function yhAyar(){
  const T = DATA.roadmap;
  if(!YH_AYAR) YH_AYAR = {maxLoad: T.maxLoad, bos: new Set(), zor: 0};
  return YH_AYAR;
}
async function yhSenaryoKur(){
  const T = DATA.roadmap, A = yhAyar();
  const kutu = $("#yhSenaryoDurum");
  if(A.maxLoad === T.maxLoad && !A.bos.size && !A.zor){ YH_SENARYO = null; renderRoadmap(); return; }
  if(kutu) kutu.textContent = "hesaplanıyor…";
  try{
    const r = await api("/api/yolharitasi", {bu: capBitisGirdi().bu, maxLoad: A.maxLoad,
                                             bos: [...A.bos], zor: A.zor || null});
    YH_SENARYO = r.senaryo;
  }catch(err){
    YH_SENARYO = null;
    if(kutu) kutu.textContent = "senaryo oluşturulamadı: " + (err.message || err);
    return;
  }
  renderRoadmap();
}
function yhSenaryoPaneli(T){
  if(!(LIVE || window.__ITUCAP_API__)) return "";
  const A = yhAyar();
  /* ★ Faz 119 (kullanıcı isteği 28.09.2026: "dönem başına en çok kredi
     kısmında istenilen değerin girilmesine izin verebilir misin") — sabit
     liste yerine SERBEST değer (1–60, yarım kredi adımı; sunucu aynı aralığı
     doğruluyor). Liste yalnız öneri. Mevcut sınırın üstündeki değer kabul
     ediliyor; yönetmeliğin istediği GNO şeritte yazıyor. */
  const oneriler = [T.maxLoad, 25, 22, 21, 18, 15, 12].filter((v, i, a) =>
    v && a.indexOf(v) === i);
  const donemler = (T.terms || []).filter(t => !t.current && !t.summer && t.index <= 8);
  return `<div class="yhsenaryo" role="group" aria-label="Senaryo">
    <span class="eyebrow">Senaryo</span>
    <label>Dönem başına en çok <input id="yhYuk" type="number" inputmode="decimal"
      min="1" max="60" step="0.5" value="${A.maxLoad}" list="yhYukOneri"
      aria-describedby="yhSenaryoDurum" title="Mevcut sınır: ${T.maxLoad} kredi"> kredi</label>
    <datalist id="yhYukOneri">${oneriler.map(v => `<option value="${v}">${
      v === T.maxLoad ? "mevcut sınır" : ""}</option>`).join("")}</datalist>
    ${yhZorVar(T) ? `<label title="Tahmini zorluğu 10 üzerinden 6 ve üstü olan dersler; fazlası sonraki uygun döneme bırakılır"
      >Dönem başına en çok <select id="yhZor">${[0, 1, 2, 3].map(v =>
      `<option value="${v}"${v === (A.zor || 0) ? " selected" : ""}>${v ? v : "sınırsız"}</option>`).join("")}</select>
      zor ders</label>` : ""}
    <span class="yhbosetiket">Boş bırakılacak dönemler (Erasmus, staj):</span>
    ${donemler.map(t => `<button class="ghost mini" data-bos="${t.index}"
      aria-pressed="${A.bos.has(t.index)}">${A.bos.has(t.index) ? "✓ " : ""}${
        esc(t.label)}</button>`).join("")}
    <span class="meta" id="yhSenaryoDurum" aria-live="polite"></span>
  </div>`;
}

/* ★ Faz 119 — mevcut sınırın üstündeki senaryo yükü: yönetmeliğin istediği
   GNO (MADDE 17/2, `kurallar.toml`). Basamak bilinmiyorsa hiçbir şart
   uydurulmuyor, yalnız "mevcut sınırın üzerindedir" deniyor. */
function yukSarti(sc, sinir){
  if(!(sc.maxLoad > sinir)) return "";
  const b = sc.loadBand;
  const ust = ` <span class="uyari">(mevcut sınırınızın, ${sinir} kredinin, üzerindedir`;
  if(!b) return ust + ")</span>";
  if(b.aboveMax) return ust + `; yönetmelikteki en yüksek sınır ${b.max} kredidir,
    bu yük alınamaz)</span>`;
  return ust + (b.minGpa ? `; yönetmeliğe göre en az ${b.minGpa.toFixed(2)} GNO gerekir)`
    : ")") + "</span>";
}

/* ★★ FAZ 118 — YOL HARİTASI ÖNCELİĞİ (kullanıcı isteği 28.09.2026).
   İkinci program varken iki ayar: programların BİRLİKTE en kısa sürede
   bitmesi ya da anadalın önce bitmesi. KAYDEDİLİYOR (`/api/yolonceligi`):
   senaryo değil, öğrencinin tercihi — sayfadaki harita, "bu dönem alırsan",
   kalma riski ve ÇAP seçenekleri aynı ayarla kuruluyor. Motor her iki
   ayarın sonucunu da döndürdüğü için öbür seçeneğin bitişi seçmeden önce
   yazıyor: öğrenci neyi neye değiştiğini görerek karar veriyor. */
const YH_ONCELIK_AD = {birlikte: "Programları birlikte en kısa sürede bitir",
                       anadal: "Anadala öncelik ver"};
function yhOncelikPaneli(T, R){
  const P = R.priority || T.priority;
  if(!P || !P.options) return "";
  const secili = (T.priority && T.priority.setting) || P.setting || "birlikte";
  const prog = (rol) => (R.programs || []).find(x => x.role === rol) || {label: rol};
  /* Ortak programın (UOLP) bitişi zaten tahmin edilmiyor — satırda da yok. */
  const bitis = (f) => Object.keys(f).filter(rol => !prog(rol).jointDegree)
    .map(rol => `${esc(prog(rol).label)} <b>${
      f[rol].label ? esc(f[rol].label) : "hesaplanamadı"}</b>`).join(" · ");
  const oburu = secili === "birlikte" ? "anadal" : "birlikte";
  const a = P.options[secili], b = P.options[oburu];
  const ayni = a && b && Object.keys(a.finish).every(r =>
    (a.finish[r] || {}).index === ((b.finish || {})[r] || {}).index);
  const yazilabilir = LIVE || window.__ITUCAP_API__;
  return `<div class="yhoncelik" role="group" aria-label="Yol haritası önceliği">
    <span class="eyebrow">Öncelik</span>
    <div class="radios">${["birlikte", "anadal"].map(k => `<button type="button"
      data-oncelik="${k}" aria-pressed="${k === secili}"${yazilabilir ? "" : " disabled"}
      >${YH_ONCELIK_AD[k]}</button>`).join("")}</div>
    <span class="meta">${!b ? "" : ayni
      ? "İki ayar bu plan için aynı bitişi vermektedir."
      : `${YH_ONCELIK_AD[oburu]} seçilirse: ${bitis(b.finish)}`}</span>
  </div>`;
}

/* ★★ Faz 89 — "zor dersleri dağıt" senaryosu yalnız haritada zor ders
   VARSA sunuluyor (verisiz katalogda anlamsız bir seçenek olurdu). */
const yhZorVar = (T) => (T.terms || []).some(t => !t.current
  && (t.items || []).some(i => i.difficulty && i.difficulty.level >= 4));

/* ★★ Faz 85 — dönem kartında "kaç zor ders". Yerleşimi değiştirmiyor; zor
   dersleri aynı döneme yığan bir planı öğrenci kendisi görebilsin diye.
   ★ Faz 102 — kartta da DÖNEM zorluğu: haftalık programın özetiyle aynı
   hesap (`donemZorlugu`: AKTS × not tabanlı ağırlık). Hiçbir dersin zorluk
   verisi yoksa satır çıkmıyor. */
function yhZorluk(t){
  const items = t.items || [];
  if(!items.some(i => i.difficulty && i.difficulty.level)) return "";
  const d = donemZorlugu(items.map(i => ({akts: i.ects, kredi: i.credits, z: i.difficulty})));
  return `<div class="yhzorluk aciklamali" title="${esc(DONEM_ZORLUK_IPUCU)} Yerleşimi etkilemez."
    >tahmini dönem zorluğu <b class="mono">${zp(d.donem)}</b>/10 (${ZORLUK_AD[d.donemKademe]})${
      d.zor ? ` · <b class="mono">${d.zor}</b> zor ders` : ""}${
      d.donem >= 8.5 || d.zor >= 3 ? " — yük yoğun olabilir" : ""}</div>`;
}

function renderRoadmap(){
  const sec = $("#roadmapSection"), T = DATA.roadmap;
  if(!sec) return;
  sec.hidden = !T;
  if(!T) return;
  if(T.noTranscript){
    $("#roadmapBody").innerHTML = `<div class="proj bilinmiyor"><b>Bitiş tahmini
      yapılamamaktadır.</b> <b class="mono">${T.donem}.</b> yarıyılda olduğunuz
      belirtilmiş, ancak başarılan dersler girilmemiştir. Bu durumda planın
      <b>tamamı</b> kalan ders olarak sayılacağından hatalı bir bitiş tarihi
      hesaplanır.${LIVE || window.__ITUCAP_API__ ? ` <button class="ghost"
      data-setup="plan" style="margin-left:8px">Dersleri girin</button>` : ""}</div>`;
    $("#roadmapBody").querySelectorAll("[data-setup]").forEach(b =>
      b.addEventListener("click", () => checklistDialog()));
    return;
  }
  const R = (YH_SENARYO && !T.error) ? YH_SENARYO : T;
  const body = $("#roadmapBody");
  if(R.error){
    body.innerHTML = `<div class="note ayarhata">Yol haritası oluşturulamadı:
      <span class="mono">${esc(R.error)}</span>. Aracın diğer bölümleri bu durumdan etkilenmez.</div>`;
    return;
  }
  const rolTag = (r) => r ? `<span class="tag ${r === "ANADAL" || r === "CAP"
    || r === "YANDAL" ? r : "PLAN_DISI"}">${esc(r === "PLAN_DISI" ? "plan dışı" : r)}</span>` : "";
  const programlar = (R.programs || []).map(p => {
    const gec = p.finish && p.nominal ? p.finish.index - p.nominal.index : null;
    return `<article class="yhprogram" data-role="${esc(p.role)}">
      <div class="eyebrow">${esc(p.label)}${p.program ? " · " + esc(p.program) : ""}</div>
      <div class="yhbitis">${p.remaining === 0 ? "tamamlanmış"
        : (p.finish ? esc(p.finish.label) : p.jointDegree ? "tahmin edilmedi" : "hesaplanamadı")}</div>
      ${p.jointDegree ? `<div class="yhalt"><span class="uyari">ortak program (UOLP ·
        ${esc(p.jointDegree)})</span> — ortak üniversitedeki dönemler veride bulunmamaktadır;
        sıralama yalnızca İTÜ dersleri içindir</div>` : ""}
      <div class="yhalt">${p.remaining ? `tahmini bitiş · ${p.remaining} ders,
        <span class="mono">${p.remainingCredits}</span> kredi kaldı` : "kalan ders bulunmamaktadır"}${
        p.unplaced ? ` · <span class="uyari">${p.unplaced} ders yerleşmedi</span>` : ""}${
        p.externalAssumed ? ` · <span class="uyari">${p.externalAssumed} dersin dış önşartı
          varsayıldı</span>` : ""}</div>
      ${gec === null ? "" : (gec > 0
        ? `<div class="yhgec">plandaki bitişten ${gec} dönem geç
             (${esc(p.nominal.label)})</div>`
        : `<div class="yhzamaninda">plandaki bitişle aynı ✓</div>`)}
      ${yariyilSatiri(p, R.maxDuration)}
      ${R === T ? "" : senaryoFarki(p, T)}
    </article>`;
  }).join("");
  const simdi = (R.takeNow || []).length ? `<div class="note yhsimdi">
      <b>Bu dönem alınması bitişi öne çekecek ${R.takeNow.length > 1 ? "dersler" : "ders"}</b>
      ${R.takeNow.map(x => `<div class="yhsatir"><b class="mono">${esc(x.course)}</b>
        <span>${esc(x.name)}</span> — bu dönem alınırsa ${x.gains.map(g =>
          `<span>${esc(g.label)} <b>${g.terms} dönem erken</b> biter
           (${esc(g.finish.label)})</span>`).join(", ")}${x.overLoad ? (x.drop
          ? ` <span class="uyari">· yük sınırı aşılmaktadır</span> — <b class="mono">${
              esc(x.drop.course)}</b> çıkarılırsa ${x.drop.lossTerms
              ? `kazancın <b>${x.drop.lossTerms} dönemi</b> kaybedilir`
              : "kazanç <b>korunur</b>"} (çıkarılan ders sonraki dönemlere yerleştirilir)`
          : ` <span class="uyari">· yük sınırı aşılmaktadır; tek bir dersin çıkarılması
              yeterli değildir veya ÇAP tabanını bozmaktadır</span>`) : ""}
        <span class="yhdugmeler">${x.drop ? `<button class="ghost mini" data-dene="${esc(x.course)}"
            data-cikar="${esc(x.drop.course)}">${esc(x.drop.course)} çıkarılarak dene</button>` : ""}
        <button class="ghost mini" data-dene="${esc(x.course)}">Programda dene</button></span></div>`).join("")}
      <div class="meta" style="margin-top:6px">Saat çakışması bu bölümde hesaplanmamıştır;
        "Programda dene" seçeneği şubeleri ve çıkarılacak dersi gösterir.</div></div>` : "";
  /* ★★ FAZ 58 — YAZ OKULU. Geçmişte yazın GERÇEKTEN açılmış ders (not
     dağılımı) ilk yazda alınırsa bitiş değişiyor mu. Düğme yok: yaz okulu
     bu dönemin programına eklenemez; kararın ne kazandırdığını söylüyoruz. */
  const yaz = (R.summerGains || []).length ? `<div class="note yhyaz">
      <b>Yaz okulu seçeneği</b>
      ${R.summerGains.map(x => `<div class="yhsatir"><b class="mono">${esc(x.course)}</b>
        <span>${esc(x.name)}</span> — ${x.history.map(h => `${esc(h.label)}'da açıldı
          (<span class="mono">${h.n}</span> öğrenci)`).join(", ")}; <b>${esc(x.term)}</b>
        döneminde alınırsa ${x.gains.map(g => `${esc(g.label)} <b>${g.terms} dönem erken</b> biter
          (${esc(g.finish.label)})`).join(", ")}</div>`).join("")}
      <div class="meta" style="margin-top:6px">Dersin geçen yaz açılmış olması bu yaz da
        açılacağı anlamına gelmez; yaz okulunun ücreti, kontenjanı ve kredi sınırı bu
        hesaba dahil değildir.</div>
    </div>` : "";
  const varsayim = `<div class="note yhvarsayim"><b>Hesaplama varsayımları</b>
      <ul>${(R.assumptions || []).map(a => `<li>${esc(a)}</li>`).join("")}</ul></div>`;
  const zincir = (R.longest || []).length > 1 ? `<div class="yhzincir">En uzun önşart
      zinciri: ${R.longest.map(c => `<b class="mono">${esc(c)}</b>`).join(" → ")} —
      bu zincir en az <b>${R.longest.length} dönem</b> sürer.</div>` : "";
  /* Faz 83 — "geçmişte" etiketinin ne olduğu, kartların hemen üstünde. */
  const gecmisAciklama = (R.terms || []).some(t => !t.current && t.items.some(i => (i.past || []).length))
    ? `<div class="meta yhgecmisnot">“geçmişte”: dersin OBS not dağılımında göründüğü dönemler
        (parantezde not alan öğrenci sayısı). Doğruluğu belirsizdir; dersin ileride aynı
        dönemlerde açılacağı kesin değildir.</div>` : "";
  const donemler = gecmisAciklama + `<div class="yhdonemler">${(R.terms || []).map(t => `
    <section class="yhdonem${t.current ? " simdi" : ""}${t.summer ? " yaz" : ""}${
      t.items.length ? "" : " bos"}${t.skipped ? " atlandi" : ""}">
      <h3><span>${esc(t.label)}</span>${t.current
        ? '<span class="chip credit">bu dönem</span>'
        : t.summer ? '<span class="chip">yaz okulu</span>' : ""}</h3>
      <div class="yhkredi"><span class="mono">${t.credits}</span> kredi${
        t.current ? ` · ${esc(R.source || "")}` : ""}</div>
      ${!t.current && t.timeCheck ? `<div class="yhsaat">≈ <span class="mono">${
        Math.round((t.weeklyMinutes || 0) / 60)}</span> sa/hafta ders${t.items.length
        ? (t.timeCheck === "var"
            ? ` · <span class="ok">bu dönemin şube saatleriyle çakışmasız program kurulabiliyor</span>`
            : ` · <span title="Bu yarıyılın ders saatleri henüz bilinmemektedir">saatler bilinmiyor; yalnız haftalık saat denetlendi</span>`)
        : ""}</div>` : ""}
      ${yhZorluk(t)}
      ${(t.timeDeferred || []).length ? `<div class="yhuyari">Saat çakışması nedeniyle bu döneme
        konamadı: <span class="mono">${t.timeDeferred.map(esc).join(", ")}</span></div>` : ""}
      ${(t.hardDeferred || []).length ? `<div class="yhuyari">Dönem başına zor ders
        sınırı nedeniyle sonraki döneme bırakıldı:
        <span class="mono">${t.hardDeferred.map(esc).join(", ")}</span></div>` : ""}
      ${(t.hourDeferred || []).length ? `<div class="yhuyari">Haftalık boş saat
        (meşgul saatler dışında) yetmediğinden bu döneme konamadı:
        <span class="mono">${t.hourDeferred.map(esc).join(", ")}</span></div>` : ""}
      ${t.floorGap ? `<div class="yhuyari">ÇAP yarıyıl tabanına
        <span class="mono">${t.floorGap}</span> kredi eksik; bu dönemde alınabilecek
        yeterli ÇAP dersi bulunmamaktadır</div>` : ""}
      ${t.items.length ? `<ul>${t.items.map(i => `<li>
          <b class="mono">${esc(i.course || i.pool)}</b>${(i.roles || []).map(rolTag).join("")}
          <span class="mono" style="color:var(--ink-3)"> · ${i.credits} kr</span>
          ${i.difficulty ? zorlukRozet(i.difficulty) : ""}
          ${i.course && i.name ? `<span class="yhad">${esc(i.name)}</span>` : ""}
          ${i.pool ? `<span class="yhad">seçmeli havuz — ders seçimi öğrenciye aittir</span>` : ""}
          ${!t.current && i.course && !i.season && !i.seasonSource ? `<span class="yhad uyari"
            title="Hiçbir planda ve geçmiş dağılımda bulunamadı; her dönem açıldığı varsayıldı"
            >mevsimi bilinmiyor</span>` : ""}
          ${i.seasonSource === "gecmis" ? `<span class="yhad"
            title="Planlarda bulunmamaktadır; geçmiş not dağılımında sınıf açılan yarıyıl esas alındı"
            >mevsimi geçmiş dönemlerden</span>` : ""}
          ${i.alsoSeasonSource === "gecmis" ? `<span class="yhad"
            title="Plan farklı bir yarıyıl belirtmektedir; ders geçmişte bu yarıyılda da açılmıştır"
            >geçmişte ${i.alsoSeason === "10" ? "Güz'de" : "Bahar'da"} da verildi</span>` : ""}
          ${i.unparsed ? `<span class="yhad uyari">önşartı okunamadı; danışmanınıza danışınız</span>` : ""}
          ${(i.externalPrereq || []).length ? `<span class="yhad uyari"
            title="Bu dersin önşartı planlarda bulunmamaktadır; önşartın sağlandığı veya muafiyet olduğu varsayıldı"
            >önşart varsayıldı: ${i.externalPrereq.slice(0, 2).map(esc).join(", ")}</span>` : ""}
          ${!t.current && (i.past || []).length ? `<span class="yhad gecmis"
            title="OBS not dağılımına göre; kesin değildir">geçmişte: ${i.past.slice(0, 4).map(g =>
              `${esc(kisaDonem(g.label))} <span class="mono">(${g.n})</span>`).join(" · ")}</span>` : ""}
        </li>`).join("")}</ul>`
        : t.skipped ? `<div class="empty">Boş bırakılan dönem (Erasmus, staj veya izin);
            bu dönemde İTÜ dersi planlanmamıştır.</div>`
        : `<div class="empty">Bu döneme yerleştirilen ders bulunmamaktadır; kalan dersler
            bu yarıyılda açılmamakta veya önşartları henüz tamamlanmamaktadır.</div>`}
    </section>`).join("")}</div>`;
  const kalan = (R.unplaced || []).length ? `<div class="note" style="margin-top:14px">
      <b>${R.unplaced.length} ders yerleştirilemedi</b>; bu nedenle bitiş hesaplanamamıştır:
      ${R.unplaced.map(u => `<div><b class="mono">${esc(u.course || u.pool)}</b>
        <span class="meta">${esc(u.reason)}</span></div>`).join("")}</div>` : "";
  const serit = R === T ? "" : `<div class="note yhseritsenaryo" role="status">
      <b>Senaryo görüntülenmektedir (kaydedilmedi).</b> ${[
        R.scenario.maxLoad !== T.maxLoad ? `dönem başına en çok <b class="mono">${
          R.scenario.maxLoad}</b> kredi${yukSarti(R.scenario, T.maxLoad)}` : "",
        R.scenario.empty.length ? `boş: ${(R.terms || []).filter(t => t.skipped)
          .map(t => esc(t.label)).join(", ")}` : "",
        R.scenario.hardMax ? `dönem başına en çok <b class="mono">${
          R.scenario.hardMax}</b> zor ders` : ""].filter(Boolean).join(" · ")}
      <button class="ghost mini" id="yhSenaryoKapat">Mevcut plana dön</button></div>`;
  body.innerHTML = `${yhOncelikPaneli(T, R)}${yhSenaryoPaneli(T)}${serit}<div class="yhprogramlar">${programlar}</div>${
    simdi}${yaz}<div data-kalma="yh">${kalmaPanelIcerik()}</div>${varsayim}${zincir}${donemler}${kalan}`;
  kalmaBagla(); kalmaOto();        // Faz 75
  const yuk = $("#yhYuk");
  if(yuk) yuk.addEventListener("change", () => {
    const v = Number(String(yuk.value).replace(",", "."));
    if(!yuk.value || !isFinite(v) || v < 1 || v > 60 || Math.round(v * 2) !== v * 2){
      const d = $("#yhSenaryoDurum");
      if(d) d.textContent = "1 ile 60 arasında, tam ya da buçuklu bir kredi değeri giriniz.";
      yuk.setAttribute("aria-invalid", "true");
      return;
    }
    yuk.removeAttribute("aria-invalid");
    yhAyar().maxLoad = v; yhSenaryoKur();
  });
  const zorSec = $("#yhZor");
  if(zorSec) zorSec.addEventListener("change", () => { yhAyar().zor = +zorSec.value; yhSenaryoKur(); });
  body.querySelectorAll("[data-oncelik]").forEach(b => b.addEventListener("click", async () => {
    if(b.getAttribute("aria-pressed") === "true") return;
    const geri = dugmeMesgul(b, "hesaplanıyor…");
    try{ applyState(await api("/api/yolonceligi", {oncelik: b.dataset.oncelik})); }
    catch(err){ geri(); hataBildir(b, err); }
  }));
  body.querySelectorAll("[data-bos]").forEach(b => b.addEventListener("click", () => {
    const A = yhAyar(), i = +b.dataset.bos;
    if(A.bos.has(i)) A.bos.delete(i); else A.bos.add(i);
    yhSenaryoKur();
  }));
  const kapat = $("#yhSenaryoKapat");
  if(kapat) kapat.addEventListener("click", () => { YH_AYAR = null; YH_SENARYO = null; renderRoadmap(); });
  body.querySelectorAll("[data-dene]").forEach(b => b.addEventListener("click", () => {
    gorunumAc("schedSection", true);
    /* Çıkarma önerisi: önce çıkar (geri alınabilir), sonra şube seçimi. */
    if(b.dataset.cikar && sel.some(x => x.course === b.dataset.cikar))
      removeCourse(b.dataset.cikar);
    addDialog(b.dataset.dene);
  }));
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

/* ★ Faz 84 — Kredi penceresi değerlendirilemediğinde (transkript yok) beyan
   edilen dönem yine bir şey söylüyor: pencere 30 krediden (2. sınıf, 3.
   yarıyıl) açılıyor. Yalnız BİLGİ — transfer/intibak öğrencisinin kredisi
   dönemden fazla olabilir, o yüzden ✗ değil. */
function basvuruDonemNotu(s){
  const k = (s.checks || []).find(c => c.key === "kredi_penceresi");
  if(!k || k.ok !== null || !DATA.donem || DATA.donem >= 3) return "";
  return `başvuru penceresi genellikle 3. yarıyıldan (30 kredi) itibaren açılır; şu an ${DATA.donem}. dönemdesiniz`;
}

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
    /* ★ Faz 84 — HİÇBİR şart değerlendirilemiyorsa (transkript yok) "✓
       denetlenebilen şartlar sağlanmaktadır" boş bir doğruydu: gerçek sitede
       1. dönemdeki, dersi girilmemiş öğrenci ÇAP için yeşil onay görüyordu.
       Bilinmeyen, bilinen gibi gösterilmez — işaret nötr, metin nedenini söylüyor. */
    const bilinen = (s.checks || []).filter(c => c.ok !== null).length;
    const belirsiz = iyi && !bilinen;
    const durum = !iyi ? "bir şart sağlanmamaktadır"
      : belirsiz ? `şartlar değerlendirilememektedir${DATA.load && DATA.load.noTranscript
          ? " (başarılan dersler girilmemiştir)" : ""}${basvuruDonemNotu(s) ? " · " + basvuruDonemNotu(s) : ""}`
      : s.unknownCount ? `denetlenebilen şartlar sağlanmaktadır · ${s.unknownCount} şart bu araçla denetlenemez`
      : "denetlenebilen tüm şartlar sağlanmaktadır";
    const sayi = s.planTypeAvailable === false ? "OBS'de plan yayımlanmamıştır"
      : s.optionCount ? `${s.optionCount} program açık` : "uygun plan bulunmamaktadır";
    return `<div class="basvuruitem">
      <span class="mark" style="color:${belirsiz ? "var(--ink-3)" : iyi ? "var(--ok)" : "var(--danger)"}"
        >${belirsiz ? "—" : iyi ? "✓" : "✗"}</span>
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
    : (c.ok ? "var(--ok)" : "var(--danger)");
  const checks = s.checks.map(c => `
    <div class="blockitem" style="border-left:5px solid ${color(c)}">
      <b style="color:${color(c)}">${mark(c)}</b> ${esc(c.label)}
      <div class="why">${esc(c.detail)}${c.source
        ? ` <span style="opacity:.7">· ${esc(c.source)}</span>` : ""}</div>
    </div>`).join("");

  const verdict = !s.eligible
    ? `<b style="color:var(--danger)">Bilinen şartlardan en az biri
       şu anda sağlanmamaktadır.</b>`
    : !s.checks.some(c => c.ok !== null)            /* Faz 84 — boş onay yok */
      ? `<b>Şartların hiçbiri değerlendirilememektedir.</b>
         Başarılan dersler girildiğinde GNO ve kredi şartları denetlenir.${basvuruDonemNotu(s) ? " Not: " + esc(basvuruDonemNotu(s)) + "." : ""}`
    : s.unknownCount
      ? `<b style="color:var(--ok)">Denetlenebilen şartlar sağlanmaktadır.</b>
         ${s.unknownCount} şart bu araçla doğrulanamamaktadır (yukarıda “—” ile işaretlidir).`
      : `<b style="color:var(--ok)">Denetlenebilen tüm şartlar sağlanmaktadır.</b>`;

  /* ⚠️ Kalan KREDİ sütunu YOK ve bu bilinçli (22.08.2026).
     Kullanıcı sayının yanlış çıktığını bildirdi; iki sebebi vardı — kendi
     ÇAP'ı için beyan ettiği denklikler her programın planına uygulanıyordu,
     ve havuz slotlarının kredisi programdan programa farklı sayılıyor.
     Denklik kapsamı düzeltildi ama kredi hâlâ duramayacağımız bir tahmin.
     Yerine SAĞLAM olan duruyor: birebir kodu tutan, geçilmiş ders sayısı. */
  /* ★ Faz 59 — "tahmini bitiş" sütunu yalnız ÇAP'ta ve hesaplanabiliyorsa
     (yol haritası var, uç çağrılabiliyor). Sonuç gelene kadar "hesaplanıyor". */
  const bitisVar = basvuruKind === "cap" && capBitisHesaplanabilir();
  const cb = bitisVar && CAP_BITIS && CAP_BITIS.veri;
  const sirali = s.options.slice();
  if(cb && BASVURU_SIRA === "bitis"){
    const ix = o => { const r = cb.results[String(o.planId)];
      return r && r.finish ? r.finish.index : 99; };
    sirali.sort((a, b) => ix(a) - ix(b));
  }
  const rows = sirali.map(o => `
    <tr><td class="mono"><b>${esc(o.code)}</b></td>
      <td>${o.name ? esc(o.name) : `<span style="color:var(--ink-3)">(adı katalogda yok)</span>`}<div class="why">${esc(o.iteration || o.planTitle)}</div></td>
      <td class="mono">${o.slotsTotal}</td>
      <td class="mono">${o.alreadyCount
        ? `<b style="color:var(--ok)">${o.alreadyCount}</b>` : "0"}
        ${o.alreadyCount ? `<div class="why mono">${o.already.slice(0,4).map(esc).join(", ")}${
          o.alreadyCount > 4 ? " …" : ""}</div>` : ""}</td>
      ${bitisVar ? `<td data-bitis="${esc(String(o.planId))}">${capBitisHucre(o.planId)}</td>` : ""}</tr>`).join("");

  $("#basvuruBody").innerHTML = `
    <div class="note" style="margin:12px 0">${verdict}</div>
    <div class="blocklist" style="margin-bottom:8px">${checks}</div>
    <div class="dislinkler" style="margin-bottom:16px">Şartların tam metni:
      ${disLink("yonerge")} · Planlar: ${disLink("obsPlan")}</div>
    ${s.optionCount ? `
      <div class="chipline"><span class="eyebrow">Başvurulabilecek programlar</span>
        <span class="chip credit">${s.optionCount}</span>
        ${cb && s.options.length > 1 ? `<button class="ghost mini" id="basvuruSira"
          >${BASVURU_SIRA === "bitis" ? "Sayılan derse göre sırala"
                                      : "Bitişe göre sırala"}</button>` : ""}</div>
      <div style="overflow-x:auto"><table class="list">
        <thead><tr><th>Kod</th><th>Program</th><th>Ders sayısı</th>
          <th>Sayılan ders</th>${bitisVar ? "<th>Tahmini ÇAP bitişi</th>" : ""}</tr></thead>
        <tbody>${rows}</tbody></table></div>
      ${bitisVar ? `<div class="why" id="capBitisNot" style="margin-top:8px">${capBitisNotu()}</div>` : ""}
      <div class="why" style="margin-top:8px">“Sayılan ders”: bu planda
        <b>ders kodu birebir eşleşen</b> başarılı dersler. Kalan kredi
        gösterilmemektedir; havuz slotlarının sayılma biçimi programdan programa
        değiştiğinden güvenilir bir değer hesaplanamaz.</div>` : `
      <div class="empty">Anadalınıza açık ${basvuruKind === "cap" ? "ÇAP" : "yandal"}
        planı bulunamadı.</div>`}
    ${s.otherHost ? `
      <div class="why" style="margin-top:8px">${s.otherHost} plan
        <b>başka anadalların</b> ${basvuruKind === "cap" ? "ÇAP" : "yandal"}'ı
        olduğundan listelenmemiştir. ÇAP planları (anadal, hedef) çiftine göre
        tanımlanır; başka bir anadala ait plana başvuru yapılamaz.</div>` : ""}
    ${s.planTypeAvailable === false ? `
      <div class="note" style="margin-top:14px;border-left-color:var(--warn)">
        <b>İTÜ ${basvuruKind === "cap" ? "ÇAP" : "yandal"} ders planlarını
        OBS'de yayımlanmamaktadır.</b>
        Sorgu doğru biçimde yapılmakta; ancak OBS
        <i>“Akademik programa bağlı ders planı bulunmamaktadır”</i> yanıtını
        vermektedir. 128 programın hiçbirinde plan bulunmamaktadır (doğrulama: 22.08.2026).
        <div style="margin-top:6px">Yukarıdaki <b>şartlar</b> yönergeye dayanır
        ve geçerlidir; ancak plan bulunmadan kalan ders sayısı <b>hesaplanamaz</b>.
        Yandal planı için ilgili bölüme başvurunuz.</div>
      </div>` : (s.missingCount ? `
      <div class="note" style="margin-top:14px">
        <b>${s.missingCount}</b> programın ${basvuruKind === "cap" ? "ÇAP" : "yandal"}
        planı henüz alınmadığından bu programlar listede yer almamaktadır.
        <b>Lisans planından tahmin yapılmamaktadır</b>; ${basvuruKind === "cap" ? "ÇAP" : "yandal"}
        planı lisans planının küçük bir alt kümesi olduğundan bu yöntem kalan
        iş yükünü olduğundan fazla gösterir. Planları almak için:
        <span class="mono">make all-plans</span>.
      </div>` : "")}`;
  const sira = $("#basvuruSira");
  if(sira) sira.addEventListener("click", () => {
    BASVURU_SIRA = BASVURU_SIRA === "bitis" ? "ders" : "bitis";
    renderBasvuruBody();
  });
  if(bitisVar && !(CAP_BITIS && CAP_BITIS.anahtar === capBitisAnahtari())) capBitisYukle();
}

/* ★★ FAZ 59 — "YA ÇAP'I ŞU BÖLÜMDE YAPSAYDIM?" (fikirler Y.1).
   Derece planlayıcılarının en çok kullanılan özelliği: programa girmeden
   önce bitiş tarihini görmek. Pencere "sende sayılan ders" sayısını
   veriyordu; asıl soru ne zaman biteceğiydi. Yol haritası motoru anadal +
   aday ÇAP planıyla yeniden kuruluyor (`/api/capbitis`, salt okunur).
   İstek üzerine: 60 programı sayfa açılırken kurmak statik sitede
   saniyeler sürerdi. Sonuç bu dönemin dersleri ve kredi sınırı değişmedikçe
   önbellekte. */
let CAP_BITIS = null, BASVURU_SIRA = "ders";
function capBitisHesaplanabilir(){
  const R = DATA.roadmap;
  return !!(R && !R.error && !R.noTranscript && (R.terms || []).length
            && (LIVE || window.__ITUCAP_API__));
}
function capBitisGirdi(){
  const R = DATA.roadmap;
  return {bu: R.terms[0].items.map(i => ({course: i.course, credits: i.credits,
                                          role: (i.roles || [])[0] || "",
                                          slotId: i.slotId || 0})),      // Faz 79
          maxLoad: R.maxLoad};
}
function capBitisAnahtari(){
  const g = capBitisGirdi();
  return JSON.stringify([g.bu.map(x => x.course).sort(), g.maxLoad,
                         ((DATA.basvuru || {}).cap || {options: []}).options.map(o => o.planId)]);
}
async function capBitisYukle(){
  const s = DATA.basvuru && DATA.basvuru.cap;
  if(!s || !s.options.length || !capBitisHesaplanabilir()) return;
  const anahtar = capBitisAnahtari();
  CAP_BITIS = {anahtar, veri: null, hata: ""};
  try{
    const r = await api("/api/capbitis", {plans: s.options.map(o => o.planId),
                                          ...capBitisGirdi()});
    if(!CAP_BITIS || CAP_BITIS.anahtar !== anahtar) return;
    CAP_BITIS.veri = r.capBitis;
  }catch(err){
    if(CAP_BITIS && CAP_BITIS.anahtar === anahtar) CAP_BITIS.hata = err.message || "hata";
  }
  if($("#basvuruDlg").open && basvuruKind === "cap") renderBasvuruBody();
}
function capBitisHucre(planId){
  if(!CAP_BITIS) return `<span class="why">hesaplanıyor…</span>`;
  if(CAP_BITIS.hata) return `<span class="why" title="${esc(CAP_BITIS.hata)}">hesaplanamadı</span>`;
  if(!CAP_BITIS.veri) return `<span class="why">hesaplanıyor…</span>`;
  const r = CAP_BITIS.veri.results[String(planId)];
  if(!r) return `<span class="why">—</span>`;
  if(!r.finish) return `<span class="uyari">hesaplanamadı</span><div class="why">${
    r.unplaced} ders yerleştirilemedi (önşartı planlarda bulunmuyor veya planlama süresinin dışında)</div>`;
  /* ⚠️ Kalan KREDİ yok — bu pencerenin 22.08.2026 kararı (havuz slotlarının
     kredisi programdan programa farklı sayılıyor). Ders sayısı sağlam. */
  const notlar = [`${r.remaining} ders kaldı`];
  if(r.anadalDelay > 0) notlar.push(`<span class="uyari">anadalı ${r.anadalDelay} dönem geciktirir</span>`);
  if(r.floorShort) notlar.push(`<span class="uyari">${r.floorShort} dönemde yarıyıl tabanı sağlanamıyor</span>`);
  if(r.unknownSeason) notlar.push(`${r.unknownSeason} dersin mevsimi bilinmiyor`);
  return `<b>${esc(r.finish.label)}</b>${r.finishSemester ? ` <span class="why">(${
    r.finishSemester}. yarıyıl)</span>` : ""}<div class="why">${notlar.join(" · ")}</div>`;
}
function capBitisNotu(){
  const v = CAP_BITIS && CAP_BITIS.veri;
  return `<b>Tahmini ÇAP bitişi</b>: ÇAP'a <b>${v && v.startTerm ? v.startTerm + ". yarıyılda" :
    "bir sonraki yarıyılda"}</b> başlanacağı${v && v.floor ? ` (yarıyıl tabanı
    <span class="mono">${v.floor}</span> kredi)` : ""} ve bu dönem yol haritasındaki
    derslerin alınacağı varsayılmıştır. Yol haritasının varsayımları geçerlidir;
    <b>başvurunun kabulü, kontenjan ve sıralama şartı bu hesaba dahil değildir</b>.
    Mevcut ÇAP/yandal programı hesaba katılmamıştır; her satır, mevcut programın
    yerine ilgili programın seçilmesi durumunu gösterir.`;
}

function renderBlockers(){
const groups = {};
DATA.blockers.forEach(b => (groups[b.reason] = groups[b.reason] || []).push(b));
let bhtml = "";
["PROGRAMA_KAPALI","ACILMAMIS","ONSART","ONSART_KATALOGDA_YOK",
 "KREDI_ESIGI","BILINMIYOR","EK_SINAV"].forEach(k => {
  const items = groups[k]; if(!items) return;
  const [label, cls] = LABELS[k];
  bhtml += `<div class="chipline"><span class="chip ${cls}">${label}</span>
    <span style="color:var(--ink-3);font-size:var(--fs-md)">${items.length} ders</span></div>
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
  bhtml += `<div class="note" style="margin-top:20px">Engellerin çoğu önşarttan değil,
    <b>ders arzından</b> kaynaklanmaktadır: ders açılmamakta veya şubeler başka
    programlara ayrılmaktadır. Bu konuda bölüm veya danışman ile görüşülmesi önerilir.</div>`;
}
if(DATA.lessonCount < 5000){
  bhtml += `<div class="note" style="margin-top:10px">Ders programında şu anda
    <span class="mono">${DATA.lessonCount}</span> şube bulunmaktadır. Dönem başlarında
    ilanlar kademeli olarak yayımlanır; "açılmamış" görünen dersler sonradan açılabilir.</div>`;
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

/* ★★ FAZ 80 — KADEMELERİN TASARIMI (kullanıcı 24.09.2026: "kademeler
   kısmının tasarımını iyileştirir misin").
   · Kutu yalnız ders KODU gösteriyordu; artık adı da (tek satır).
   · Kademe başlığı ZAMANI söylüyor: tamamlanmamış ilk kademe bu dönem, her
     sonraki kademe en az bir dönem sonra ("en erken 2027-2028 Bahar").
     "En erken": dersin açıldığı yarıyıl daha da geciktirebilir.
   · TAMAMLANMIŞ kademe tek satıra katlanıyor — üstü çizili kutular ekranın
     yarısını kaplıyordu; bağları "önce …" metninde zaten yazıyor.
   · Dar ekranda (tek sütun) çizgiler dinlenmede GİZLİ, bir derse dokununca
     yalnız o zincirin çizgileri çıkıyor: 390px'te bütün bağlar sağdaki
     oluğa üst üste biniyor, okunmayan bir yumak oluşuyordu. */
function donemIleri(kod, n){
  let y = +String(kod).slice(0, 4), s = String(kod).slice(4);
  if(!y || !["10", "20"].includes(s)) return "";
  for(let k = 0; k < n; k++){ if(s === "10") s = "20"; else { s = "10"; y++; } }
  return `${y - 1}-${y} ${s === "10" ? "Güz" : "Bahar"}`;
}
const kademeBitti = (t) => t.courses.length && t.courses.every(c => c.status === "DONE");
function renderTierGroup(grup, i){
  const stage = $("#tierStage" + i);
  const ilkAcik = grup.tiers.findIndex(t => !kademeBitti(t));
  const cols = grup.tiers.map((t, j) => kademeBitti(t) ? `
    <div class="tier bitti">
      <h3>Kademe ${t.tier} · tamamlandı</h3>
      <div class="tierbitti">${t.courses.map(c => `<span class="mono"
        title="${esc(c.name || c.course)}">${esc(c.course)}</span>`).join(" · ")}</div>
    </div>` : `
    <div class="tier">
      <h3>Kademe ${t.tier} · ${t.courses.reduce((a,c)=>a+c.credits,0)} kredi${
        ilkAcik >= 0 && DATA.term ? `<span class="tierdonem"
          title="Her kademe en az bir dönem sürer; dersin açıldığı yarıyıl bu tarihi geciktirebilir">
          ${j === ilkAcik ? "bu dönem" : "en erken " + esc(donemIleri(DATA.term, j - ilkAcik))}</span>` : ""}</h3>
      <ul>${t.courses.map(c => `<li data-s="${c.status}" data-c="${esc(c.course)}"
            title="${esc(c.name || c.course)}">
        <span class="top"><span class="mono">${esc(c.course)}</span>
        <span class="mono" style="color:var(--ink-3)">${c.credits}</span></span>
        ${c.name ? `<span class="tad">${esc(c.name)}</span>` : ""}
        ${(c.needs && c.needs.length)
            ? `<span class="dep">önce <b>${c.needs.map(esc).join("</b> · <b>")}</b></span>` : ""}
        ${(c.outside && c.outside.length)
            ? `<span class="dispre" role="button" tabindex="0" aria-expanded="false"
                 title="Plan dışından önşart (anadalda alınmış olabilir)">+${c.outside.length} dış önşart</span>
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
    `${bagli} ders plan içinden bir önşarta bağlıdır` +
    (disari.size ? ` · ${disari.size} önşart plan dışındandır (anadalda alınmış olabilir)` : "") +
    ` · kademe 0: hemen alınabilir. Planların önşart zincirleri
      ${disLink("ituHelperOnsart", "İTÜ Helper Önşart Zinciri")} sayfasında da incelenebilir.`;
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
  YH_SENARYO = null; YH_AYAR = null;   // Faz 61 — yeni durumda eski senaryo yok
  renderRoadmap();
  cevrimdisiDurumu();       // Faz 60
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
   Artık perdeye tıklamak pencereyi kapatıyor.

   ★★ FAZ 57 — TIKLAMA ARTIK ALTINA GEÇMİYOR (kullanıcı 23.09.2026: *"when a
   window opens and to close mouse is clicked out of the window just close
   the window do not interact with background"*). Faz 55'te dış tıklama
   pencereyi kapatıp ALTINDAKİ öğeye de iletiliyordu (ray bağlantısı,
   ızgaradaki başka ders). Pratikte kapatmak için tıklanan yer çoğu zaman
   rastgele bir yerdi: pencere kapanırken ızgarada başka bir dersin
   penceresi açılıyor ya da görünüm değişiyordu — kullanıcı yalnız kapatmak
   istemişti. Dış tıklamanın TEK işi artık kapatmak; olay orada duruyor.

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
        say("Kaydedilmemiş değişiklikler bulunmaktadır. Saklamak için Kaydet düğmesini, "
            + "vazgeçmek için pencere dışına ikinci kez tıklayınız veya Kapat düğmesini kullanınız.", true);
        return;
      }
      /* Faz 57 — yalnız kapat. Olay burada duruyor: belge düzeyindeki
         dinleyiciler (sayfa içi bağlantı, açıklamaya dokunma) onu görmesin. */
      e.preventDefault();
      e.stopPropagation();
      d.close();
    });
  });
})();

boot();
</script>
</body>
</html>
"""
