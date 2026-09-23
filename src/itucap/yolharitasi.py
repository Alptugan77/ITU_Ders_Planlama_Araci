"""Mezuniyet yol haritası — çok dönemli plan (Faz 57, yol haritası §2.1).

Araç bugüne kadar **bu dönemi** planlıyordu. "ÇAP kaç dönemde biter"
sorusuna kademe sayısıyla bir *alt sınır* veriyordu (Kademeler görünümü),
bir *plan* vermiyordu. Bu modül kalan dersleri gelecek dönemlere
yerleştiriyor ve her program için tahmini bitiş dönemini söylüyor.

⚠️ Bu bir PLAN, kehanet değil. Aracın ana kuralı burada en çok zorlanıyor:
gelecek dönemlerin arzı (hangi ders açılacak, kaç şube, kaç kontenjan)
bilinmiyor. O yüzden:

* her varsayım `varsayimlar` listesinde AÇIKÇA dönüyor ve arayüz onları
  planın ÜSTÜNDE yazıyor;
* mevsim (Güz/Bahar) TAHMİN EDİLMİYOR, planlardan OKUNUYOR: anadal dersinin
  mevsimi kendi planındaki dönemin tek/çiftliği; ÇAP/yandal dersininki, o
  programın LİSANS planında aynı dersin dönemi. İkisi de bulunamazsa ders
  "her dönem açılır" sayılıyor ve bu SAYILIP yazılıyor;
* yerleştirilemeyen ders sessizce düşmüyor: `yerlesmeyen` listesinde
  sebebiyle duruyor (planlarında olmayan bir önşart, kredi eşiği, ufuk);
* kontenjan, şube, saat çakışması YOK — bunlar yalnız bu dönem için
  hesaplanabiliyor. Plan bunu da yazıyor.

Kurallar (hepsi motorun var olan parçalarından):
* önşart ağacı `prereq.parsed_trees` — yerleştirilmiş ders o dönemin
  sonunda geçilmiş sayılıyor;
* kredi eşiği (bitirme projesi ≥95 kredi gibi) `policy.check` — birikmiş
  kredi dönem dönem büyüyor;
* dönem kredi sınırı: bugünkü sınır (`max_load`);
* ÇAP yarıyıl tabanı (`policy.second_floor`) varsa her dönem önce ÇAP
  dersleriyle doldurulmaya çalışılıyor; tutmuyorsa dönem bunu söylüyor.

⚠️ Pyodide paketine giriyor (`site_kur.ENGINE`): tarama bağımlılığı yok,
import anında dosya okumuyor.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Iterable, Mapping

from . import config
from . import policy as POL
from . import prereq as P
from . import rules as R

UFUK = 12           # en çok kaç dönem ileri (6 yıl)
GECER = "AA"        # yerleştirilen ders "geçildi" sayılırken verilen not


@dataclass
class Birim:
    """Yerleştirilecek bir plan birimi: zorunlu ders ya da seçmeli havuz."""
    anahtar: str
    ders: str                      # ders kodu; havuzda boş
    kodlar: set[str]               # dersi karşılayan bütün kodlar (dil eşi)
    ad: str
    kredi: float
    roller: set[str]
    donem_no: int | None           # planın kaçıncı dönemi (anadal)
    havuz: str = ""                # seçmeli havuzun adı
    mevsim: str | None = None      # '10' Güz, '20' Bahar, None bilinmiyor
    ek_mevsim: str | None = None   # bu dönem şubesi VAR → o mevsimde de açılıyor
    mevsim_kaynagi: str = ""       # 'plan' | 'lisans' | ''
    en_erken: int = 1              # en erken dönem indeksi (0 = bu dönem)
    yukseklik: int = 0             # arkasından gelen en uzun zincir
    yer: int | None = None         # yerleştirildiği dönem indeksi
    notlar: list[str] = field(default_factory=list)


def sonraki_donem(kod: str) -> str:
    """`202610` → `202620` → `202710`. Yaz (`30`) planlamaya girmiyor."""
    yil, ek = int(kod[:4]), kod[4:]
    return f"{yil}20" if ek == "10" else f"{yil + 1}10"


def _mevsim(donem_no: int | None) -> str | None:
    if not donem_no:
        return None
    return "10" if donem_no % 2 else "20"


def _lisans_mevsimi(con: sqlite3.Connection, program: str, kodlar: set[str]):
    """ÇAP/yandal dersinin mevsimi — ev sahibi programın LİSANS planından."""
    if not program:
        return None
    for row in con.execute(
            """SELECT ps.course_code, ps.alt_course_codes, ps.term_no
               FROM plan_slot ps JOIN plan p ON p.id = ps.plan_id
               WHERE p.program_code=? AND p.plan_type='lisans'
                 AND ps.term_no IS NOT NULL""", (program,)):
        if kodlar & set(R.slot_codes(row)):
            return _mevsim(row["term_no"])
    return None


def _birimler(con, planlar, grades, equivalences, names) -> list[Birim]:
    """Planların HENÜZ KARŞILANMAMIŞ slotları — aynı ders iki planda tek birim."""
    out: dict[str, Birim] = {}
    kod_to_anahtar: dict[str, str] = {}
    for plan in planlar:
        rows = con.execute(
            """SELECT ps.id, ps.slot_kind, ps.course_code, ps.alt_course_codes,
                      ps.pool_label_raw, ps.pool_category, ps.term_no,
                      COALESCE(ps.credits, ps.credits_min, c.credits) AS kredi
               FROM plan_slot ps LEFT JOIN course c ON c.code = ps.course_code
               WHERE ps.plan_id=? ORDER BY ps.position""", (plan["planId"],)).fetchall()
        for row in rows:
            if R.slot_satisfied(con, row["id"], grades, equivalences).satisfied:
                continue
            kredi = float(row["kredi"] or 0)
            if row["slot_kind"] == "REQUIRED" and row["course_code"]:
                kodlar = set(R.slot_codes(row))
                eski = next((kod_to_anahtar[k] for k in kodlar if k in kod_to_anahtar), None)
                if eski:                       # aynı ders başka planda da var
                    out[eski].roller.add(plan["role"])
                    continue
                b = Birim(row["course_code"], row["course_code"], kodlar,
                          names.get(row["course_code"], ""), kredi, {plan["role"]},
                          row["term_no"])
                for k in kodlar:
                    kod_to_anahtar[k] = b.anahtar
            else:
                etiket = row["pool_label_raw"] or row["pool_category"] or "Seçmeli"
                b = Birim(f"havuz:{row['id']}", "", set(), etiket, kredi or 3.0,
                          {plan["role"]}, row["term_no"], havuz=etiket)
                b._slot = row["id"]            # type: ignore[attr-defined]
            b._plan = plan                     # type: ignore[attr-defined]
            out[b.anahtar] = b
    return list(out.values())


def _sondaki_boslari_at(donemler: list[dict]) -> list[dict]:
    son = max((d["index"] for d in donemler if d["current"] or d["items"]), default=0)
    return [d for d in donemler if d["index"] <= son]


def kur(con: sqlite3.Connection, grades: Mapping[str, str], planlar: list[dict], *,
        term: str, donem: int, max_load: float, bu_donem: Iterable[dict],
        bu_donem_kaynagi: str = "", equivalences=None,
        taban: POL.SecondFloor | None = None, ufuk: int = UFUK) -> dict:
    """Yol haritası.

    `planlar`: `[{"planId", "role", "label", "program"}]` — anadal önce.
    `bu_donem`: bu dönem alınacağı varsayılan dersler `[{"course", "credits",
    "slotId", "role"}]` (kaydedilen program ya da açılıştaki öneri).

    ⚠️ Bağlantının `row_factory`si çağıranın; burada geçici değişip geri
    konuyor (sunucu `Row`, testler düz demet kullanıyor).
    """
    eski = con.row_factory
    con.row_factory = sqlite3.Row
    try:
        return _kur(con, grades, planlar, term=term, donem=donem, max_load=max_load,
                    bu_donem=bu_donem, bu_donem_kaynagi=bu_donem_kaynagi,
                    equivalences=equivalences, taban=taban, ufuk=ufuk)
    finally:
        con.row_factory = eski


def _kur(con, grades, planlar, *, term, donem, max_load, bu_donem, bu_donem_kaynagi,
         equivalences, taban, ufuk) -> dict:
    equivalences = list(equivalences or [])
    names = {r[0]: r[1] for r in con.execute("SELECT code, name FROM course")}
    siniflama = {r[0]: r[1] for r in con.execute(
        "SELECT code, class_restriction FROM course WHERE class_restriction IS NOT NULL")}
    kurallar, katalog_kurali = POL.load_rules(), POL.load_catalog_rule()
    agaclar = P.parsed_trees(con)
    okunamayan = {r[0] for r in con.execute("SELECT course_code FROM prereq_unparsed")}

    birimler = _birimler(con, planlar, grades, equivalences, names)
    bu_donem = [dict(p) for p in bu_donem]

    # ---------------------------------------------- 0. bu dönem (dönem 0)
    alinan_kodlar = {p["course"] for p in bu_donem}
    alinan_slot = {p.get("slotId") for p in bu_donem if p.get("slotId")}
    for b in birimler:
        if b.ders and b.kodlar & alinan_kodlar:
            b.yer = 0
        elif b.havuz and getattr(b, "_slot", None) in alinan_slot:
            b.yer = 0

    # ---------------------------------------------- 1. mevsim ve en erken dönem
    # ★ Bu dönemin şubeleri VERİ: planı "Bahar" dese de bu Güz şubesi olan
    # ders Güz'de de açılıyor (vitrinde MAT 210E: plan 4. dönem, bu Güz iki
    # şube). Yalnız plana bakmak onu gereksiz yere bir dönem kaydırıyordu.
    acik = {r[0] for r in con.execute("SELECT DISTINCT course_code FROM lesson")}
    bilinmeyen_mevsim = 0
    for b in birimler:
        plan = b._plan                                  # type: ignore[attr-defined]
        if b.donem_no:
            b.mevsim, b.mevsim_kaynagi = _mevsim(b.donem_no), "plan"
        elif b.ders:
            m = _lisans_mevsimi(con, plan.get("program", ""), b.kodlar)
            if m:
                b.mevsim, b.mevsim_kaynagi = m, "lisans"
        if b.mevsim and b.kodlar & acik and term[4:] != b.mevsim:
            b.ek_mevsim = term[4:]
        if b.mevsim is None and b.yer is None:
            bilinmeyen_mevsim += 1
        # Anadal dersi planındaki dönemden ÖNCE konmuyor (planın sırası);
        # alttan kalan (donem_no < donem) hemen gelecek döneme.
        if donem and b.donem_no and plan.get("role") == "ANADAL":
            b.en_erken = max(1, b.donem_no - donem)

    # ---------------------------------------------- 2. zincir yüksekliği
    kod_birim = {k: b for b in birimler for k in b.kodlar}

    def bagimlilar(b: Birim) -> list[Birim]:
        return [x for x in birimler if x is not b and x.ders and agaclar.get(x.ders)
                and agaclar[x.ders].courses() & b.kodlar]

    yukseklik: dict[str, int] = {}

    def yuksek(b: Birim, yol: frozenset = frozenset()) -> int:
        if b.anahtar in yukseklik:
            return yukseklik[b.anahtar]
        if b.anahtar in yol:
            return 1
        v = 1 + max((yuksek(x, yol | {b.anahtar}) for x in bagimlilar(b)), default=0)
        yukseklik[b.anahtar] = v
        return v

    for b in birimler:
        b.yukseklik = yuksek(b)
    kalan = [b for b in birimler if b.yer is None]
    zincir = max((b.yukseklik for b in kalan), default=0)

    # ---------------------------------------------- 3. dönem dönem yerleştir
    gecilen = {c for c, g in grades.items() if R.passed(g)}
    varsayilan = set(gecilen) | alinan_kodlar
    kazanilan = POL.earned_credits(con, grades) + sum(
        float(p.get("credits") or 0) for p in bu_donem)
    donemler = [{"code": term, "label": config.donem_adi(term) or term,
                 "index": 0, "current": True, "credits": round(sum(
                     float(p.get("credits") or 0) for p in bu_donem), 1),
                 "items": [{"course": p["course"], "name": names.get(p["course"], ""),
                            "credits": p.get("credits") or 0,
                            "roles": [p.get("role") or ""], "pool": ""}
                           for p in sorted(bu_donem, key=lambda x: x["course"])],
                 "floorGap": None}]

    def alinabilir(b: Birim, t: int, kod: str, kredi_var: float) -> bool:
        if t < b.en_erken:
            return False
        if b.mevsim and kod[4:] not in (b.mevsim, b.ek_mevsim):
            return False
        if not b.ders:
            return True                      # havuz: hangi ders seçileceği bilinmiyor
        if b.ders in okunamayan:
            return True                      # önşart okunamadı — notla işaretleniyor
        agac = agaclar.get(b.ders)
        if agac is not None and not agac.satisfied(
                R.prereq_view({c: GECER for c in varsayilan})):
            return False
        return POL.check(b.ders, kredi_var, kurallar, names.get(b.ders, ""),
                         siniflama.get(b.ders), katalog_kurali).ok

    kod = term
    for t in range(1, ufuk + 1):
        kod = sonraki_donem(kod)
        if not kalan:
            break
        uygun = [b for b in kalan if alinabilir(b, t, kod, kazanilan)]
        # Öncelik: en uzun zinciri başlatan önce (kritik yol), sonra planın
        # dönem sırası, zorunlu ders seçmeli havuzdan önce.
        uygun.sort(key=lambda b: (-b.yukseklik, b.donem_no or 99,
                                  bool(b.havuz), b.anahtar))
        secilen, toplam, cap_kredi = [], 0.0, 0.0

        def al(b: Birim) -> None:
            nonlocal toplam, cap_kredi
            secilen.append(b)
            toplam += b.kredi
            if "CAP" in b.roller:
                cap_kredi += b.kredi

        # İki geçiş: ÇAP yarıyıl tabanı varsa önce ÇAP dersleri TABAN
        # DOLANA KADAR (öncelik sırasıyla), sonra herkes öncelik sırasıyla.
        # Hepsini ÇAP'a vermek anadalın kritik yolunu gereksiz geciktirirdi.
        if taban:
            for b in uygun:
                if cap_kredi + 1e-9 >= taban.minimum:
                    break
                if "CAP" in b.roller and toplam + b.kredi <= max_load + 1e-9:
                    al(b)
        for b in uygun:
            if b not in secilen and toplam + b.kredi <= max_load + 1e-9:
                al(b)
        for b in secilen:
            b.yer = t
            varsayilan |= b.kodlar
        kazanilan += toplam
        kalan = [b for b in kalan if b.yer is None]
        # Taban eksiği yalnız ÇAP SÜRERKEN söyleniyor: son ÇAP döneminde
        # kalan kredi tabanın altındaysa fazlasını almak zaten imkânsız.
        cap_kalan = any("CAP" in b.roller for b in kalan)
        donemler.append({
            "code": kod, "label": config.donem_adi(kod) or kod, "index": t,
            "current": False, "credits": round(toplam, 1),
            "items": [{"course": b.ders, "name": b.ad, "credits": b.kredi,
                       "roles": sorted(b.roller), "pool": b.havuz,
                       "season": b.mevsim, "seasonSource": b.mevsim_kaynagi,
                       "alsoSeason": b.ek_mevsim,
                       "chain": b.yukseklik,
                       "unparsed": b.ders in okunamayan}
                      for b in secilen],
            # ÇAP tabanı tutmuyorsa SÖYLENİYOR (yeterli alınabilir ÇAP dersi yok).
            "floorGap": (round(taban.minimum - cap_kredi, 1)
                         if taban and cap_kalan and cap_kredi < taban.minimum else None),
        })

    # ---------------------------------------------- 4. yerleşmeyenler — sebebiyle
    yerlesmeyen = []
    for b in kalan:
        sebep = f"{ufuk} dönem içinde yerleşmedi"
        agac = agaclar.get(b.ders) if b.ders else None
        if agac is not None:
            eksik = sorted({n.course for n in agac.missing(
                R.prereq_view({c: GECER for c in varsayilan}))})
            if eksik:
                sebep = ("önşartı planlarında olmayan ders(ler) istiyor: "
                         + ", ".join(eksik[:4]))
        if b.ders and not POL.check(b.ders, kazanilan, kurallar,
                                    names.get(b.ders, ""), siniflama.get(b.ders),
                                    katalog_kurali).ok:
            sebep = "kredi eşiği"
        yerlesmeyen.append({"course": b.ders, "name": b.ad, "pool": b.havuz,
                            "credits": b.kredi, "roles": sorted(b.roller),
                            "reason": sebep})

    # ---------------------------------------------- 5. program başına bitiş
    # Anadalın PLANDAKİ bitişi: planın son dönemi − bulunduğun dönem. Dönem
    # bilinmiyorsa hesaplanmıyor (tahmin etmiyoruz).
    kodlar_sirali = [term]
    for _ in range(ufuk):
        kodlar_sirali.append(sonraki_donem(kodlar_sirali[-1]))

    def etiket(i: int) -> dict:
        return {"index": i, "code": kodlar_sirali[i],
                "label": config.donem_adi(kodlar_sirali[i]) or kodlar_sirali[i]}

    programlar = []
    for plan in planlar:
        rol = plan["role"]
        onun = [b for b in birimler if rol in b.roller]
        kalmayan = [b for b in onun if b.yer is None]
        son = max((b.yer for b in onun if b.yer is not None), default=None)
        son_donem = None
        if rol == "ANADAL" and donem:
            son_donem = con.execute("SELECT MAX(term_no) FROM plan_slot WHERE plan_id=?",
                                    (plan["planId"],)).fetchone()[0]
        nominal = (etiket(max(0, son_donem - donem))
                   if son_donem and 0 <= son_donem - donem <= ufuk else None)
        programlar.append({
            "role": rol, "label": plan.get("label") or rol, "nominal": nominal,
            "program": plan.get("program", ""),
            "remaining": len(onun), "remainingCredits": round(sum(b.kredi for b in onun), 1),
            "finish": None if kalmayan or son is None else etiket(son),
            "unplaced": len(kalmayan),
            "chain": max((b.yukseklik for b in onun if b.yer != 0), default=0),
        })

    # En uzun zincirin kendisi — "neden bu kadar sürüyor"un cevabı.
    en_uzun = []
    bas = max((b for b in birimler if b.yer != 0), key=lambda b: b.yukseklik, default=None)
    while bas is not None and bas.ders:
        en_uzun.append(bas.ders)
        sonraki = [x for x in bagimlilar(bas) if x.yer != 0]
        bas = max(sonraki, key=lambda b: b.yukseklik, default=None)

    # Bu dönem alınmayan, arkasından zincir gelen dersler — "bu dönem
    # alırsan ne değişir" sorusunun adayları (çağıran yeniden kurup ölçüyor).
    baslar = [{"course": b.ders, "chain": b.yukseklik, "roles": sorted(b.roller),
               "credits": b.kredi}
              for b in sorted(birimler, key=lambda b: -b.yukseklik)
              if b.ders and b.yer != 0]

    varsayimlar = [
        "Planladığın her dersi ilk denemede geçeceğin varsayıldı.",
        f"Bu dönem: {bu_donem_kaynagi or 'seçili program'} alınmış sayıldı.",
        f"Her dönem en çok {max_load:g} kredi — bugünkü sınırın. GNO'n değişirse "
        "sınır da değişir.",
        "Dersler planlarındaki dönemin mevsiminde açılır sayıldı (tek dönem → Güz, "
        "çift → Bahar); ÇAP/yandal dersinin mevsimi o programın lisans planından okundu. "
        "Bu dönem şubesi olan ders bu mevsimde de açılır sayıldı.",
        "Kontenjan, şube ve saat çakışması bu planda YOK — onlar yalnız bu dönem için "
        "bilinebiliyor. Yaz okulu hesaba katılmadı.",
        "Seçmeli havuzda hangi dersi seçeceğin bilinmediği için havuzun önşartı yok sayıldı.",
    ]
    if bilinmeyen_mevsim:
        varsayimlar.append(f"⚠ {bilinmeyen_mevsim} dersin mevsimi hiçbir planda bulunamadı "
                           "— her dönem açılır sayıldı.")
    return {
        "term": term, "maxLoad": max_load, "source": bu_donem_kaynagi,
        # ⚠️ Boş dönem ATILMIYOR (yalnız sondakiler): Bahar'da açılan bir dersi
        # bekleyen Güz dönemi planın bir parçası — atmak takvimi olduğundan
        # kısa gösterirdi.
        "terms": _sondaki_boslari_at(donemler),
        "programs": programlar, "unplaced": yerlesmeyen,
        "chain": zincir, "longest": en_uzun, "heads": baslar,
        "unknownSeason": bilinmeyen_mevsim,
        "floor": ({"minimum": taban.minimum, "verified": taban.verified}
                  if taban else None),
        "assumptions": varsayimlar,
    }
