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
  programın LİSANS planında aynı dersin dönemi. İkisi de bulunamazsa
  (Faz 58) dersin GEÇMİŞ not dağılımına bakılıyor (`gecmis_mevsimleri`);
  o da yoksa ders "her dönem açılır" sayılıyor ve bu SAYILIP yazılıyor;
* yerleştirilemeyen ders sessizce düşmüyor: `yerlesmeyen` listesinde
  sebebiyle duruyor (planlarında olmayan bir önşart, kredi eşiği, ufuk);
* ★ Faz 82 — SAAT: bu dönemle AYNI mevsimdeki gelecek dönemlerde (Güz ise
  sonraki Güz'ler) dersler, bu dönemin şube saatleriyle ÇAKIŞMASIZ bir program
  kurulabiliyorsa aynı döneme konuyor; kurulamıyorsa ders sonraki uygun
  döneme kalıyor. Öbür mevsimin saati bilinmiyor — orada denetim yok ve
  kart bunu söylüyor.
* kontenjan, şube, saat çakışması (öbür mevsimde) YOK — bunlar yalnız bu dönem için
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

import re
import sqlite3
from dataclasses import dataclass, field
from typing import Iterable, Mapping

from . import config
from . import policy as POL
from . import recommend as REC
from . import prereq as P
from . import rules as R

UFUK = 12           # en çok kaç dönem ileri (6 yıl)
GECER = "AA"        # yerleştirilen ders "geçildi" sayılırken verilen not

# ★ Faz 58 — geçmiş dağılımda GERÇEK açılışı bütünlemeciden ayıran eşik.
# Güz dersinin Bahar dağılımı çoğunlukla birkaç bütünlemeci demek (Faz 38b:
# BLG 212 Baharda n=2, ikisi de FF). "Notu var" = "açıldı" saysaydık her
# Güz dersi Baharda da açılır görünürdü.
GECMIS_TABAN = 5    # bir yarıyılda en az bu kadar notlu öğrenci
GECMIS_ORAN = 0.25  # ve o akademik yılın en kalabalık yarıyılının en az ¼'ü


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
    mevsim_kaynagi: str = ""       # 'plan' | 'lisans' | 'gecmis' | ''
    ek_mevsim_kaynagi: str = ""    # 'sube' (bu dönem şubesi) | 'gecmis'
    gecmis: dict | None = None     # `gecmis_mevsimleri` sonucu
    dis_onsart: list[str] = field(default_factory=list)   # varsayılan dış önşartlar
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


def gecmis_donemleri(gecmis: dict | None, en_cok: int = 6) -> list[dict]:
    """Faz 83 — not dağılımında dersin GÖRÜNDÜĞÜ dönemler, yeniden eskiye.

    Kullanıcı 24.09.2026: "geçmişteki not dağılımlarından derslerin hangi
    dönemlerde açıldığı ile ilgili küçük bir bilgi geç, doğruluğunun belirsiz
    olduğunu belirterek". Mevsim kararı (`gecmis_mevsimleri`) eşikli; bu liste
    HAM veriyi gösteriyor (öğrenci sayısıyla) ki az öğrencili dönem — çoğunlukla
    tekrar/bütünleme sınıfı — kendi sayısıyla görünsün. Yorum çağıranda:
    kesin değildir.
    """
    if not gecmis:
        return []
    return [{"term": t, "label": config.donem_adi(t) or t, "n": n}
            for t, n in sorted(gecmis.get("terms", {}).items(), reverse=True)
            if n > 0][:en_cok]


def gecmis_mevsimleri(con: sqlite3.Connection, kodlar: Iterable[str]) -> dict | None:
    """Faz 58 — dersin geçmiş not dağılımından GERÇEKTEN verildiği yarıyıllar.

    Kaynak (Faz 38) tek istekte bir akademik yılın BÜTÜN yarıyıllarını
    veriyor; o yıl verisi olan bir derste bir yarıyılın hiç görünmemesi,
    o yarıyıl not açıklanmadığı demek. Bu yüzden karşılaştırma yıl içinde:
    bir Güz/Bahar yarıyılı, `GECMIS_TABAN` öğrenciyi ve o yılın en kalabalık
    yarıyılının `GECMIS_ORAN`ını geçiyorsa "verildi" sayılıyor. Yaz ayrı:
    yalnız `GECMIS_TABAN`.

    Döner: {"seasons": {'10','20'} alt kümesi, "summer": [{term, label, n}],
    "terms": {term: n}} — dağılımı hiç olmayan derste None (TAHMİN YOK).
    ⚠️ "Geçen yıl açıldı" ≠ "bu yıl açılacak"; çağıran bunu varsayım olarak
    yazmak zorunda.
    """
    from . import notlar
    anahtarlar = sorted({a for a in (notlar.lookup(con, k) for k in kodlar) if a})
    if not anahtarlar:
        return None
    isaret = ",".join("?" * len(anahtarlar))
    sayilar: dict[str, int] = {}
    for term, n in con.execute(
            f"""SELECT term, SUM(students) FROM grade_distribution
                WHERE course_key IN ({isaret}) GROUP BY term""", anahtarlar):
        sayilar[str(term)] = int(n or 0)
    if not sayilar:
        return None
    mevsimler: set[str] = set()
    yaz = []
    for yil in sorted({t[:4] for t in sayilar}):
        duzenli = {m: sayilar.get(yil + m, 0) for m in ("10", "20")}
        ust = max(duzenli.values())
        for m, n in duzenli.items():
            if n >= GECMIS_TABAN and n >= GECMIS_ORAN * ust:
                mevsimler.add(m)
        n = sayilar.get(yil + "30", 0)
        if n >= GECMIS_TABAN:
            yaz.append({"term": yil + "30", "label": config.donem_adi(yil + "30")
                        or yil + "30", "n": n})
    return {"seasons": mevsimler, "summer": yaz, "terms": sayilar}


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
                # ★ Faz 92: ÇAP/yandal slotunda dil eşi de — anadalın
                # EHB 222E'si ile ÇAP'ın EHB 222'si AYNI ders, iki ayrı dönemde
                # iki kez planlanmamalı. (Anadal slotuna eklenmiyor: bkz.
                # rules.dil_serbest; birleşme ÇAP tarafındaki eşle oluyor.)
                kodlar = set(R.slot_codes(row, con if plan["role"] != "ANADAL" else None))
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
                # Faz 69 — kredisi planda yazmayan havuz: 3 VARSAYILDI; bunu
                # kullanan hesap (kalan derslerde gereken ortalama) söylüyor.
                b._kredi_varsayildi = not kredi   # type: ignore[attr-defined]
            b._plan = plan                     # type: ignore[attr-defined]
            out[b.anahtar] = b
    return list(out.values())


def ortak_program(con: sqlite3.Connection, program: str) -> str | None:
    """Faz 63 — UOLP (uluslararası ortak lisans) programıysa ortak üniversite.

    Gerçek katalogda 20 program böyle ("… UOLP (Saraybosna-IUS)"): planı
    YALNIZ İTÜ'de alınan dersleri içeriyor (BES 3.–6., CES 5.–8. yarıyıl).
    Ortak üniversitedeki dönemler veride yok; haritanın "son İTÜ dersi"
    mezuniyet değil. Adı OBS'nin program listesinden — başka işaret yok.
    """
    row = con.execute("SELECT name FROM program WHERE code=?", (program or "",)).fetchone()
    ad = (row[0] if row else "") or ""
    if "UOLP" not in ad:
        return None
    m = re.search(r"UOLP\s*\(([^)]+)\)", ad)
    return m.group(1).strip() if m else "ortak üniversite"


def _sondaki_boslari_at(donemler: list[dict]) -> list[dict]:
    son = max((d["index"] for d in donemler if d["current"] or d["items"]), default=0)
    return [d for d in donemler if d["index"] <= son]


def kur(con: sqlite3.Connection, grades: Mapping[str, str], planlar: list[dict], *,
        term: str, donem: int, max_load: float, bu_donem: Iterable[dict],
        bu_donem_kaynagi: str = "", equivalences=None,
        taban: POL.SecondFloor | None = None, ufuk: int = UFUK,
        yaz: str | None = None, bos: Iterable[int] = (), mesgul: Iterable = (),
        zor_siniri: int | None = None) -> dict:
    """Yol haritası.

    `planlar`: `[{"planId", "role", "label", "program"}]` — anadal önce.
    `bu_donem`: bu dönem alınacağı varsayılan dersler `[{"course", "credits",
    "slotId", "role"}]` (kaydedilen program ya da açılıştaki öneri).
    `yaz` (Faz 58): İLK yaz okulunda alınacağı varsayılan tek ders — "ya
    yazın alsaydım" sorusu için. İlk yaz, ilk Bahar'dan sonra gelen yaz:
    bu dönem Güz'se bir sonraki Bahar'ın arkası.
    `bos` (Faz 61): hiç İTÜ dersi alınmayacak dönemlerin sırası (1 = gelecek
    dönem) — Erasmus, staj, izin. Yarıyıl sayısına DAHİL sayılıyor.
    `zor_siniri` (Faz 89): bir döneme en çok bu kadar "zor" ders (tahmini
    zorluk kademesi ≥ 4, yani genel puan ≥ 6) konur; fazlası sonraki uygun
    döneme kalır. Senaryo — "zor dersleri dağıtırsam ne zaman biterim".

    ⚠️ Bağlantının `row_factory`si çağıranın; burada geçici değişip geri
    konuyor (sunucu `Row`, testler düz demet kullanıyor).
    """
    eski = con.row_factory
    con.row_factory = sqlite3.Row
    try:
        return _kur(con, grades, planlar, term=term, donem=donem, max_load=max_load,
                    bu_donem=bu_donem, bu_donem_kaynagi=bu_donem_kaynagi,
                    equivalences=equivalences, taban=taban, ufuk=ufuk, yaz=yaz,
                    bos=frozenset(int(x) for x in bos), mesgul=tuple(mesgul),
                    zor_siniri=zor_siniri)
    finally:
        con.row_factory = eski


def _kur(con, grades, planlar, *, term, donem, max_load, bu_donem, bu_donem_kaynagi,
         mesgul=(), zor_siniri=None,
         equivalences, taban, ufuk, yaz=None, bos=frozenset()) -> dict:
    equivalences = list(equivalences or [])
    from . import istek as IST
    # ★ Faz 91 — istek boyunca bir kez (harita bir istekte 12 kez kuruluyor).
    names = IST.bellek(("ders_adlari", id(con)), lambda: {
        r[0]: r[1] for r in con.execute("SELECT code, name FROM course")})
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
    bilinmeyen_mevsim = gecmisten = 0
    for b in birimler:
        plan = b._plan                                  # type: ignore[attr-defined]
        if b.donem_no:
            b.mevsim, b.mevsim_kaynagi = _mevsim(b.donem_no), "plan"
        elif b.ders:
            m = _lisans_mevsimi(con, plan.get("program", ""), b.kodlar)
            if m:
                b.mevsim, b.mevsim_kaynagi = m, "lisans"
        if b.mevsim and b.kodlar & acik and term[4:] != b.mevsim:
            b.ek_mevsim, b.ek_mevsim_kaynagi = term[4:], "sube"
        # ★ Faz 58 — geçmiş: planlar susuyorsa mevsim, konuşuyorsa ek mevsim.
        # Plan ile geçmiş çelişirse ikisi de açık sayılıyor ve NOT düşülüyor —
        # hangisinin doğru olduğunu bilmiyoruz, birini seçmek uydurmak olurdu.
        b.gecmis = gecmis_mevsimleri(con, b.kodlar) if b.ders else None
        g = (b.gecmis or {}).get("seasons") or set()
        if g and b.yer is None:
            if b.mevsim is None:
                b.mevsim_kaynagi = "gecmis"
                b.mevsim = next(iter(g)) if len(g) == 1 else None
                gecmisten += 1
            elif not b.ek_mevsim and (g - {b.mevsim}):
                b.ek_mevsim, b.ek_mevsim_kaynagi = next(iter(g - {b.mevsim})), "gecmis"
                gecmisten += 1
        if b.mevsim is None and not b.mevsim_kaynagi and b.yer is None:
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
    # ★ Faz 106 — önşartta RESMÎ DENKLİKLER de sayılıyor (öneri motoru
    # `candidates`/`cap_blockers` gibi: `expand_with_equivalences`). Eskiden
    # harita ham transkripte bakıyordu: denklikle karşılanan ders plan slotunu
    # dolduruyor ama onu isteyen dersin önşartını açmıyordu — iki ekran farklı.
    genis, _ = R.expand_with_equivalences(grades, equivalences)
    gecilen = {c for c, g in genis.items() if R.passed(g)}
    varsayilan = set(gecilen) | alinan_kodlar
    # ★★ DIŞ ÖNŞART (24.09.2026, gerçek katalogla ölçüldü). Önşartın istediği
    # ders HİÇBİR planında yoksa (ING 201 dil dersi, MAT 210 ↔ yeni kodu gibi
    # kod göçleri — fikirler §1.1) ders eskiden HİÇ yerleşmiyordu ve tek bir
    # böyle ders bütün programın bitişini "hesaplanamadı" yapıyordu: BLG+EHB
    # öğrencisinde iki programın ikisi de. Bu dersler öğrencide çoğunlukla
    # geçilmiş, muaf ya da başka kodla alınmış. Okunamayan önşartla AYNI
    # kural: yerleşiyor, hangi dış dersin VARSAYILDIĞI derste ve varsayım
    # kutusunda yazıyor. Ancak dış ders varsayılınca da tutmuyorsa (planlı
    # bir ders eksik) ders bekliyor.
    dis = set()
    for b in birimler:
        a = agaclar.get(b.ders) if b.ders else None
        if a is not None:
            dis |= a.courses()
    dis -= set(kod_birim) | varsayilan
    # ★★ Faz 98 — PLANDAKİ DERSİN DİL EŞİ "DIŞ" DEĞİL (kullanıcı 25.09.2026:
    # "BLG 4902E'nin önşartı BLG 4901E ama sistem BLG 4901'i aldım sayıyor ve
    # ikisini aynı döneme öneriyor"). Önşart "BLG 4901 MIN BB veya BLG 4901E
    # MIN BB"; BLGE planında yalnız BLG 4901E var, Türkçe "BLG 4901" hiçbir
    # planda yok → dış sayılıp GEÇİLMİŞ varsayılıyordu ve "veya" hep
    # sağlanıyordu: BLG 4902E, BLG 4901E'den ÖNCEKİ döneme bile yerleşiyordu.
    # Dış kuralı "hiçbir planda olmayan ders" (ING 201, kod göçü) içindi;
    # katalogda eşi planda olan kod aynı dersin öbür dili — plandan alınacak.
    # ⚠️ Yalnız YERLEŞECEK birimlere bakmak yetmiyor: BLG 4901E işaretlenip
    # (geçilmiş) birim olmaktan çıkınca "BLG 4901" yine dış sayılıyordu. Bütün
    # plan kodlarına bakılıyor.
    plan_kodlari = R.plan_codes(con, *(p["planId"] for p in planlar), pools=True)
    dis = {c for c in dis if R.dil_esi(con, c) not in plan_kodlari}
    # ★ Faz 104 — aynı sebeple: beyan edilmiş kod göçünün yeni kodu plandaysa
    # eski kod "dış" değil (BLG 252E → BBF 203E). Dış sayılınca geçilmiş
    # varsayılıyor ve BBF 301E, BBF 203E'den önceki döneme yerleşebiliyordu.
    from .declared import code_migration_groups
    goc = code_migration_groups()
    dis = {c for c in dis if not ((goc.get(c, frozenset()) | goc.get(R.dil_esi(con, c) or "", frozenset()))
                                  & plan_kodlari)}
    # ★★ Faz 98 — GEÇİLMİŞ DERSİN GERÇEK NOTU. Görünüm her geçilen derse "AA"
    # veriyordu; DD ile geçilmiş (ya da notsuz işaretlenip DD sayılan)
    # BLG 4901E, "MIN BB" isteyen BLG 4902E'yi açıyordu. Bu dönemin önerileri
    # gerçek notla bakıp dersi engelliyordu — iki ekran çelişiyordu. Yalnız
    # yerleştirilen (gelecekte alınacak) dersler "AA" varsayılıyor.
    gercek_not = {c: str(g).upper() for c, g in genis.items() if R.passed(g)}

    def gorunum(kodlar):
        v = {c: GECER for c in kodlar}
        v.update({c: g for c, g in gercek_not.items() if c in v})
        return R.prereq_view(v)

    def onsart_tamam(b: Birim, agac) -> bool:
        if agac is None or agac.satisfied(gorunum(varsayilan)):
            b.dis_onsart = []
            return True
        if agac.satisfied(gorunum(varsayilan | dis)):
            b.dis_onsart = sorted(agac.courses() & dis)
            return True
        return False
    # ★★ Faz 85 — tahmini zorluk (not ortalamasından). Yerleşimi ETKİLEMİYOR;
    # yalnız kartta "bu dönemde kaç zor ders" okunabilsin diye taşınıyor.
    from . import notlar as ND
    _zk: dict = {}

    def zorluk_ozeti(kod):
        if not kod:
            return None
        if kod not in _zk:
            try:
                z = ND.zorluk(con, kod)
            except Exception:                                  # noqa: BLE001
                z = None
            _zk[kod] = ({k: z.get(k) for k in ("level", "label", "score", "passScore",
                                             "gradeScore", "passRate", "mean", "n",
                                             "gradeOverall", "ects", "ectsEffect",
                                             "termLabels", "lowData")}
                        if z and z.get("level") else None)
        return _zk[kod]

    # ★ Faz 102 — kalemin AKTS'si: kartta dönem zorluğu AKTS'yi yük olarak
    # topluyor. Havuz yuvasında slotun AKTS'si; bilinmiyorsa None (arayüz
    # krediden tahmin ediyor ve bunu yazıyor).
    _ak: dict = {}

    def akts_of(kod, slot=None):
        anahtar = kod or f"slot:{slot}"
        if anahtar not in _ak:
            if kod:
                _ak[anahtar] = ND.ders_aktsi(con, kod)
            elif slot:
                r = con.execute("SELECT ects FROM plan_slot WHERE id=?", (slot,)).fetchone()
                _ak[anahtar] = float(r[0]) if r and r[0] else None
            else:
                _ak[anahtar] = None
        return _ak[anahtar]

    kazanilan = POL.earned_credits(con, grades) + sum(
        float(p.get("credits") or 0) for p in bu_donem)
    donemler = [{"code": term, "label": config.donem_adi(term) or term,
                 "index": 0, "current": True, "credits": round(sum(
                     float(p.get("credits") or 0) for p in bu_donem), 1),
                 "items": [{"course": p["course"], "name": names.get(p["course"], ""),
                            "credits": p.get("credits") or 0,
                            "roles": [p.get("role") or ""], "pool": "",
                            # Faz 79 — havuz yuvası; istek üzerine kurulan
                            # haritalar (senaryo, ÇAP seçenekleri) geri gönderiyor.
                            "slotId": p.get("slotId") or 0,
                            "ects": akts_of(p["course"]),                 # Faz 102
                            "difficulty": zorluk_ozeti(p["course"])}     # Faz 85
                           for p in sorted(bu_donem, key=lambda x: x["course"])],
                 "floorGap": None}]

    # ★ Faz 58 — YAZ OKULU. Mevsim ve "plandaki dönemden önce değil" kuralı
    # yazda uygulanmıyor (yaz okulu tam da öne almak için kullanılıyor);
    # önşart ve kredi eşiği uygulanıyor. Yaz dersi, önündeki Bahar'ın
    # sırasını alıyor: bir sonraki Güz'de geçilmiş sayılıyor.
    yaz_sonuc: dict | None = None

    def yaz_yerlestir(t: int, bahar: str) -> None:
        nonlocal yaz_sonuc, kazanilan
        if not yaz or yaz_sonuc is not None:
            return
        kod_yaz = bahar[:4] + "30"
        b = next((x for x in birimler if x.ders and yaz in x.kodlar), None)
        if b is None or b.yer is not None:
            yaz_sonuc = {"course": yaz, "placed": False,
                         "reason": ("planlarda kalan dersler arasında değil" if b is None
                                    else "bu dönem alınmaktadır" if b.yer == 0
                                    else "yaz okulundan önceki döneme zaten yerleşmektedir")}
            return
        agac = agaclar.get(b.ders)
        hazir = b.ders in okunamayan or onsart_tamam(b, agac)
        if not hazir or not POL.check(b.ders, kazanilan, kurallar, names.get(b.ders, ""),
                                      siniflama.get(b.ders), katalog_kurali).ok:
            yaz_sonuc = {"course": b.ders, "placed": False,
                         "reason": "önşartı veya kredi eşiği o yaza kadar sağlanmamaktadır"}
            return
        b.yer = t
        varsayilan.update(b.kodlar)
        kazanilan += b.kredi
        yaz_sonuc = {"course": b.ders, "placed": True, "index": t, "code": kod_yaz,
                     "label": config.donem_adi(kod_yaz) or kod_yaz}
        donemler.append({
            "code": kod_yaz, "label": yaz_sonuc["label"], "index": t, "current": False,
            "summer": True, "credits": b.kredi, "floorGap": None,
            "items": [{"course": b.ders, "name": b.ad, "credits": b.kredi,
                       "roles": sorted(b.roller), "pool": "", "season": "30",
                       "seasonSource": "yaz", "chain": b.yukseklik,
                       "unparsed": b.ders in okunamayan}]})

    if term[4:] == "20":
        yaz_yerlestir(0, term)

    # ---------------------------------------------- ★★ Faz 82 — saat gerçekliği
    # Kullanıcı: "yol haritasında derslerin saatlerinin toplamı alabileceğim
    # saatlere sığmıyor gibi geldi, biraz imkânsız bir tahmin". Harita her
    # dönemi yalnız KREDİ sınırına kadar dolduruyordu; o derslerin aynı hafta
    # içinde çakışmadan alınıp alınamayacağına hiç bakmıyordu. Bu dönemin
    # şube saatleri aynı mevsimin sonraki dönemleri için en iyi bilgi
    # (İTÜ'de ders saatleri yıldan yıla çoğunlukla korunuyor) — o dönemlerde
    # bir ders ancak çakışmasız bir şube kombinasyonu varsa konuyor.
    # Saati hiç bilinmeyen ders (bu dönem şubesi yok) denetimi DARALTMIYOR:
    # bilinmeyen, bilinen gibi gösterilmez — kısıt da uydurulmaz.
    izinli = {str(p.get("program") or "").upper() for p in planlar if p.get("program")}
    _subeler: dict = {}

    def subeler(ders: str) -> list:
        """Saatli şubeler; MEŞGUL saatlerinle çakışanlar sayılmıyor."""
        if ders not in _subeler:
            hepsi = [s for s in REC.load_sections(con, ders, izinli) if s.meetings]
            _subeler[ders] = (hepsi, [s for s in hepsi if not any(
                REC.section_conflict(s, m) for m in mesgul)])
        return _subeler[ders][1] if _subeler[ders][0] else []

    def saatli(ders: str) -> bool:
        subeler(ders)
        return bool(_subeler[ders][0])

    # ★ Haftalık saat bütçesi — BÜTÜN dönemlerde (öbür mevsimde de). Ders
    # penceresi Pzt–Cum 08:30–17:30 (2700 dk) eksi meşgul saatlerin bu
    # penceredeki kısmı. Dersin haftalık saati: bu dönem şubesi varsa en kısa
    # şubesinin toplamı, yoksa kredisi × ölçülen dakika/kredi oranı (şubesi
    # olan derslerin ortancası; ölçülemezse 60). Sığmayan ders sonraki
    # döneme — meşgul saat yoksa bu sınır pratikte hiç bağlamıyor.
    PENCERE = (510, 1050)
    bos_dk = 5 * (PENCERE[1] - PENCERE[0]) - sum(
        max(0, min(m.end, PENCERE[1]) - max(m.start, PENCERE[0]))
        for s in mesgul for m in s.meetings if 1 <= m.day <= 5)
    _dk: dict = {}

    def ders_dk(ders: str) -> int | None:
        if ders not in _dk:
            hepsi = [s for s in REC.load_sections(con, ders, izinli) if s.meetings] \
                if ders else []
            _dk[ders] = min((sum(m.end - m.start for m in s.meetings) for s in hepsi),
                            default=None)
        return _dk[ders]

    oranlar = sorted(ders_dk(b.ders) / b.kredi for b in birimler
                     if b.ders and b.kredi and ders_dk(b.ders))
    dk_kredi = oranlar[len(oranlar) // 2] if oranlar else 60.0

    def haftalik_dk(b) -> float:
        d = ders_dk(b.ders) if b.ders else None
        return float(d) if d is not None else b.kredi * dk_kredi

    _sigar: dict = {}

    def cakismasiz(dersler: list) -> bool:
        anahtar = frozenset(dersler)
        if anahtar in _sigar:
            return _sigar[anahtar]
        # Saatli ama meşgul saatler yüzünden HİÇ şubesi kalmayan ders: sığmaz.
        if any(saatli(d) and not subeler(d) for d in dersler):
            _sigar[anahtar] = False
            return False
        listeler = sorted((subeler(d) for d in dersler if subeler(d)), key=len)
        butce = [20000]

        def ara(i: int, secili: list) -> bool:
            if i == len(listeler):
                return True
            for s in listeler[i]:
                butce[0] -= 1
                if butce[0] < 0:
                    return True                  # bütçe bitti → bilinmiyor, kısıtlama yok
                if not any(REC.section_conflict(s, x) for x in secili):
                    secili.append(s)
                    if ara(i + 1, secili):
                        return True
                    secili.pop()
            return False

        _sigar[anahtar] = ara(0, [])
        return _sigar[anahtar]

    def alinabilir(b: Birim, t: int, kod: str, kredi_var: float) -> bool:
        if t < b.en_erken:
            return False
        if b.mevsim and kod[4:] not in (b.mevsim, b.ek_mevsim):
            return False
        if not b.ders:
            return True                      # havuz: hangi ders seçileceği bilinmiyor
        if b.ders in okunamayan:
            return True                      # önşart okunamadı — notla işaretleniyor
        if not onsart_tamam(b, agaclar.get(b.ders)):
            return False
        return POL.check(b.ders, kredi_var, kurallar, names.get(b.ders, ""),
                         siniflama.get(b.ders), katalog_kurali).ok

    kod = term
    hep_saat, hep_butce = set(), set()          # Faz 82 — gerekçe için
    hep_zor: set = set()                        # Faz 89

    def zor_mu(ders) -> bool:
        z = zorluk_ozeti(ders) if ders else None
        return bool(z and z["level"] >= 4)
    for t in range(1, ufuk + 1):
        kod = sonraki_donem(kod)
        if not kalan:
            break
        if t in bos:
            # ★ Faz 61 — BOŞ DÖNEM (Erasmus, staj, izin): o dönem İTÜ dersi yok.
            # Kart takvimde KALIYOR ("boş bıraktın") — atmak planı kısa gösterirdi.
            # ÇAP tabanı eksiği burada yazılmıyor: kararı sen verdin, yönergedeki
            # istisnayı (izinli dönem) danışmanın bilir; plan onu uydurmuyor.
            donemler.append({"code": kod, "label": config.donem_adi(kod) or kod,
                             "index": t, "current": False, "credits": 0,
                             "items": [], "floorGap": None, "skipped": True})
            if kod[4:] == "20" and yaz:
                yaz_yerlestir(t, kod)
                kalan = [b for b in kalan if b.yer is None]
            continue
        uygun = [b for b in kalan if alinabilir(b, t, kod, kazanilan)]
        saat_bilinir = kod[4:] == term[4:]          # Faz 82 — aynı mevsim
        ertelenen_saat: list = []
        ertelenen_butce: list = []
        ertelenen_zor: list = []                # Faz 89
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

        def zora_sigar(b: Birim) -> bool:
            """★ Faz 89 — senaryo: bu dönemde zor ders sınırı dolmadı mı.
            Havuz (ders belli değil) ve verisiz ders sayılmıyor — zorluğu
            bilinmeyen ders "zor" diye ertelenmez."""
            if not zor_siniri or not zor_mu(b.ders):
                return True
            if sum(1 for x in secilen if zor_mu(x.ders)) < zor_siniri:
                return True
            ertelenen_zor.append(b.ders)
            return False

        def saate_sigar(b: Birim) -> bool:
            """Faz 82 — b eklenince (1) haftalık saat bütçesi aşılmıyor mu,
            (2) aynı mevsimde çakışmasız program kurulabiliyor mu."""
            if sum(haftalik_dk(x) for x in secilen) + haftalik_dk(b) > bos_dk + 1e-9:
                ertelenen_butce.append(b.ders or b.havuz)
                return False
            if not saat_bilinir or not b.ders or not saatli(b.ders):
                return True
            ok = cakismasiz([x.ders for x in secilen if x.ders and saatli(x.ders)] + [b.ders])
            if not ok:
                ertelenen_saat.append(b.ders)
            return ok

        # İki geçiş: ÇAP yarıyıl tabanı varsa önce ÇAP dersleri TABAN
        # DOLANA KADAR (öncelik sırasıyla), sonra herkes öncelik sırasıyla.
        # Hepsini ÇAP'a vermek anadalın kritik yolunu gereksiz geciktirirdi.
        if taban:
            for b in uygun:
                if cap_kredi + 1e-9 >= taban.minimum:
                    break
                if ("CAP" in b.roller and toplam + b.kredi <= max_load + 1e-9
                        and zora_sigar(b) and saate_sigar(b)):
                    al(b)
        for b in uygun:
            if (b not in secilen and b.ders not in ertelenen_saat
                    and toplam + b.kredi <= max_load + 1e-9
                    and zora_sigar(b) and saate_sigar(b)):
                al(b)
        for b in secilen:
            b.yer = t
            varsayilan |= b.kodlar
        hep_saat.update(ertelenen_saat)
        hep_butce.update(x for x in ertelenen_butce if x)
        hep_zor.update(ertelenen_zor)
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
                       "alsoSeasonSource": b.ek_mevsim_kaynagi,
                       "chain": b.yukseklik,
                       "unparsed": b.ders in okunamayan,
                       "externalPrereq": b.dis_onsart,
                       "past": gecmis_donemleri(b.gecmis),                 # Faz 83
                       "ects": akts_of(b.ders, getattr(b, "_slot", None)),  # Faz 102
                       "difficulty": zorluk_ozeti(b.ders)}                 # Faz 85
                      for b in secilen],
            # Faz 82 — saat denetimi: "var" (aynı mevsim, çakışmasız program
            # bulundu) / "yok" (öbür mevsim, saat bilinmiyor).
            "timeCheck": "var" if saat_bilinir else "yok",
            "timeDeferred": sorted(set(ertelenen_saat)),
            "hourDeferred": sorted(set(x for x in ertelenen_butce if x)),
            "hardDeferred": sorted(set(ertelenen_zor)),                   # Faz 89
            "weeklyMinutes": round(sum(haftalik_dk(b) for b in secilen)),
            "availableMinutes": bos_dk,
            # ÇAP tabanı tutmuyorsa SÖYLENİYOR (yeterli alınabilir ÇAP dersi yok).
            "floorGap": (round(taban.minimum - cap_kredi, 1)
                         if taban and cap_kalan and cap_kredi < taban.minimum else None),
        })
        if kod[4:] == "20" and yaz:
            yaz_yerlestir(t, kod)
            kalan = [b for b in kalan if b.yer is None]

    # ---------------------------------------------- 4. yerleşmeyenler — sebebiyle
    yerlesmeyen = []
    for b in kalan:
        sebep = f"{ufuk} dönem içinde yerleştirilemedi"
        agac = agaclar.get(b.ders) if b.ders else None
        if agac is not None:
            eksik = sorted({n.course for n in agac.missing(gorunum(varsayilan))})
            # Faz 98: eksik ders GEÇİLMİŞ ama notu yetmiyorsa bunu söyle —
            # "planlarda bulunmayan" demek yanlış olurdu.
            notu_yetmeyen = sorted(c for c in eksik if c in gercek_not)
            if notu_yetmeyen:
                need = {n.course: n.min_grade for n in agac.missing(gorunum(varsayilan))}
                sebep = ("önşartın istediği not sağlanmamaktadır: " + ", ".join(
                    f"{c} (en az {need.get(c) or 'DD'}, kayıtlı not {gercek_not[c]})"
                    for c in notu_yetmeyen[:3])
                    + ". Notu girilmemiş ders DD sayılır; notunuzu girerseniz "
                      "harita yeniden hesaplanır")
                eksik = []
            if eksik:
                # Faz 82 — önşart PLANDA ama kendisi yerleştirilemediyse bu
                # "planlarda bulunmayan" değil (meşgul saatlerle görülen hata).
                kalan_kod = {k for x in kalan for k in x.kodlar}
                if set(eksik) <= kalan_kod:
                    sebep = ("önşartı yerleştirilemeyen ders(ler)e bağlıdır: "
                             + ", ".join(eksik[:4]))
                else:
                    sebep = ("önşartı planlarda bulunmayan ders(ler)dir: "
                             + ", ".join(eksik[:4]))
        if b.ders and not POL.check(b.ders, kazanilan, kurallar,
                                    names.get(b.ders, ""), siniflama.get(b.ders),
                                    katalog_kurali).ok:
            sebep = "kredi eşiği sağlanmamaktadır"
        # ★ Faz 82 — saat gerekçeleri, en somutundan.
        elif b.ders and mesgul and saatli(b.ders) and not subeler(b.ders):
            sebep = ("bu dönemin bütün şubeleri meşgul saatlerinizle çakışmaktadır; "
                     "ders saatleri yıldan yıla korunursa aynı yarıyılda da alınamaz")
        elif b.ders and b.ders in hep_saat:
            sebep = "her denendiği dönemde öbür derslerle saat çakışması oluşmaktadır"
        elif (b.ders or b.havuz) in hep_butce:
            sebep = "haftalık boş saat (meşgul saatler dışında) yetmemektedir"
        elif b.ders and b.ders in hep_zor:
            sebep = (f"dönem başına en çok {zor_siniri} zor ders senaryosunda "
                     f"{ufuk} dönem içinde yerleştirilememiştir")
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

    programlar, ortaklar = [], []
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
        # ★ Faz 63 — ortak programda bitiş, plandaki bitiş ve yarıyıl YOK:
        # ortak üniversitedeki dönemler bilinmiyor; son İTÜ dersini mezuniyet
        # gibi göstermek (ve azami süreye vurmak) uydurma olurdu.
        ortak = ortak_program(con, plan.get("program", ""))
        if ortak:
            ortaklar.append(ortak)
        programlar.append({
            "role": rol, "label": plan.get("label") or rol,
            "nominal": None if ortak else nominal,
            "program": plan.get("program", ""),
            "remaining": len(onun), "remainingCredits": round(sum(b.kredi for b in onun), 1),
            "finish": None if ortak or kalmayan or son is None else etiket(son),
            "jointDegree": ortak,
            # Faz 59 — bitişin öğrencinin kaçıncı yarıyılı olduğu (yaz sayılmıyor;
            # bu dönem = `donem`). Dönem bilinmiyorsa None — tahmin yok.
            "finishSemester": (donem + son if donem and not ortak and not kalmayan
                               and son is not None else None),
            "unplaced": len(kalmayan),
            # Dış önşartı VARSAYILARAK yerleşen ders sayısı — bitiş buna bağlı.
            "externalAssumed": sum(1 for b in onun if b.yer not in (None, 0) and b.dis_onsart),
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
        "Planlanan her dersin ilk denemede başarıyla tamamlanacağı varsayılmıştır.",
        f"Bu dönem: {bu_donem_kaynagi or 'seçili program'} alınmış kabul edilmiştir.",
        f"Her dönem en fazla {max_load:g} kredi (mevcut sınır) alınacağı varsayılmıştır; "
        "GNO değiştiğinde sınır da değişebilir.",
        "Derslerin, plandaki dönemin yarıyılında açılacağı varsayılmıştır (tek dönem: Güz, "
        "çift dönem: Bahar); ÇAP/yandal dersinin yarıyılı ilgili programın lisans planından "
        "alınmıştır. Bu dönem şubesi bulunan dersin bu yarıyılda da açılacağı kabul edilmiştir.",
        f"Saat çakışması: {config.donem_adi(term).split()[-1] if config.donem_adi(term) else 'bu'} "
        "dönemlerinde bu dönemin şube saatleri esas alınarak her döneme çakışmasız bir "
        "programın kurulabileceği dersler konmuştur (ders saatlerinin yıldan yıla korunduğu "
        "varsayılmıştır); öbür yarıyılın saatleri bilinmediğinden orada denetlenmemiştir. "
        "Kontenjan dikkate alınmamıştır. Yaz okulu hesaba katılmamıştır.",
        *([f"Meşgul saatleriniz (haftada {round((2700 - bos_dk) / 60)} saat, "
           "Pzt–Cum 08:30–17:30 içinde) dikkate alınmıştır: bu saatlerle çakışan şubeler "
           "sayılmamış, her dönemin ders saati kalan boş saatlere sığdırılmıştır."]
          if mesgul else []),
        "Seçmeli havuzdan hangi dersin seçileceği bilinmediğinden havuz dersleri için önşart "
        "aranmamıştır.",
        "Derslerin yanındaki \u201cgeçmişte\u201d bilgisi OBS not dağılımından türetilmiştir; "
        "yalnızca not açıklanmış dönemleri gösterir ve az öğrencili dönem çoğunlukla tekrar "
        "veya bütünleme sınıfıdır. Doğruluğu belirsizdir: dersin ileride aynı dönemlerde "
        "açılacağı kesin değildir.",
    ]
    dis_var = [b for b in birimler if b.yer not in (None, 0) and b.dis_onsart]
    if dis_var:
        ornek = sorted({k for b in dis_var for k in b.dis_onsart})[:4]
        varsayimlar.append(
            f"{len(dis_var)} dersin önşartı planlarında olmayan derslerden "
            f"({', '.join(ornek)}{'…' if len({k for b in dis_var for k in b.dis_onsart}) > 4 else ''})"
            "; bu derslerin başarıldığı, muaf olunduğu veya başka bir kodla alındığı "
            "varsayılmıştır. Aksi durumda transkripte eklenmesi veya danışmana danışılması "
            "önerilir.")
    if bos:
        varsayimlar.append(
            f"{len(bos)} dönem boş bırakılmıştır (Erasmus/staj/izin): bu dönemlerde İTÜ "
            "dersi planlanmamış ve dönemler yarıyıl sayısına dahil edilmiştir. Kayıt dondurma "
            "yarıyıl sayısına dahil edilmeyebilir; yurt dışında alınan derslerin denkliği bu "
            "hesapta yer almamaktadır.")
    if zor_siniri:
        varsayimlar.append(
            f"Her döneme en çok {zor_siniri} zor ders (tahmini zorluk 10 üzerinden 6 ve "
            "üstü) konmuştur; fazlası sonraki uygun döneme bırakılmıştır. Zorluk geçmiş not "
            "dağılımından tahmindir; zorluğu bilinmeyen dersler ve seçmeli havuzlar sınıra "
            "sayılmamıştır.")
    if gecmisten:
        varsayimlar.append(
            f"{gecmisten} dersin açıldığı yarıyıl geçmiş not dağılımından belirlenmiştir: "
            f"yalnızca düzenli bir sınıfın (en az {GECMIS_TABAN} öğrenci ve o yılın en "
            f"kalabalık yarıyılının %{GECMIS_ORAN * 100:.0f}'i) bulunduğu yarıyıl esas "
            "alınmıştır. Dersin geçen yıl açılmış olması bu yıl da açılacağı anlamına gelmez.")
    if ortaklar:
        varsayimlar.append(
            f"⚠ Ortak program (UOLP · {', '.join(ortaklar)}): planda yalnızca İTÜ'de alınan "
            "dersler yer almaktadır; ortak üniversitedeki dönemler bu veride bulunmamaktadır. "
            "Dersler ardışık İTÜ dönemlerine yerleştirilmiş, bitiş tahmini yapılmamıştır. "
            "Hangi yarıyılların İTÜ'de geçeceği için danışmanınıza başvurunuz.")
    if bilinmeyen_mevsim:
        varsayimlar.append(f"⚠ {bilinmeyen_mevsim} dersin açıldığı yarıyıl hiçbir planda ve "
                           "geçmiş not dağılımında bulunamamıştır; bu derslerin her dönem "
                           "açılacağı varsayılmıştır.")
    return {
        "term": term, "maxLoad": max_load, "source": bu_donem_kaynagi,
        # ⚠️ Boş dönem ATILMIYOR (yalnız sondakiler): Bahar'da açılan bir dersi
        # bekleyen Güz dönemi planın bir parçası — atmak takvimi olduğundan
        # kısa gösterirdi.
        "terms": _sondaki_boslari_at(donemler),
        "programs": programlar, "unplaced": yerlesmeyen,
        "chain": zincir, "longest": en_uzun, "heads": baslar,
        "unknownSeason": bilinmeyen_mevsim,
        "summer": yaz_sonuc,
        # Geçmişte YAZ okulunda gerçekten açılmış, bu dönem alınmayan dersler —
        # "yazın alırsan ne değişir" sorusunun adayları (çağıran ölçüyor).
        "summerCandidates": [
            {"course": b.ders, "name": b.ad, "credits": b.kredi, "chain": b.yukseklik,
             "roles": sorted(b.roller), "history": b.gecmis["summer"]}
            for b in sorted(birimler, key=lambda b: (-b.yukseklik, b.anahtar))
            if b.ders and b.yer != 0 and b.gecmis and b.gecmis["summer"]],
        "floor": ({"minimum": taban.minimum, "verified": taban.verified}
                  if taban else None),
        "assumptions": varsayimlar,
    }
