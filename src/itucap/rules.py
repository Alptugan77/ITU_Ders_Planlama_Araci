"""FAZ 2 — Kural motoru: alınabilirlik, denklik grafı, slot karşılanması.

İki soruya cevap verir:

    alinabilir(ders)          -> Verdict(OK | ENGELLI | BILINMIYOR, eksikler)
    karsilanir_mi(slot)       -> Fulfilment(karşılandı mı, hangi dersle, hangi denklikle)

Tasarım ilkesi: **belirsizliği gizleme.** Önşart metni çözülemediyse motor
"önşartı yok" demez, `BILINMIYOR` döner ve arayüz kullanıcıyı danışmanına
yönlendirir. Sessizce yanlış cevap vermek, cevap verememekten kötüdür.
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Mapping

from .prereq import GRADE_POINTS, PASSING_MIN, Node, parse
from . import istek as IST


class Status(str, Enum):
    OK = "OK"                    # önşartlar sağlanıyor
    BLOCKED = "ENGELLI"          # eksik önşart var
    UNKNOWN = "BILINMIYOR"       # önşart verisi çözülemedi -> danışmana sor


@dataclass
class Verdict:
    status: Status
    missing: list[tuple[str, str]] = field(default_factory=list)   # (ders, min not)
    note: str | None = None

    def __bool__(self) -> bool:
        return self.status is Status.OK


def prereq_view(grades: Mapping[str, str]) -> dict[str, str]:
    """Önşart değerlendirmesi için notlara muafiyetleri ekler.

    ⚠️ Bu görünüm SADECE önşart kontrolünde kullanılır. Muaf sayılan bir ders
    GEÇİLMİŞ değildir — plan slotunu doldurmaz, AKTS'ye sayılmaz. İkisini
    karıştırmak ilerlemeyi olduğundan iyi gösterirdi.
    """
    from .declared import code_migration_groups, waiver_grades

    view = dict(waiver_grades())
    view.update(grades)          # gerçek notlar muafiyeti EZER
    # ★★ Faz 104 — beyan edilmiş KOD GÖÇÜ: yeni kodu geçen, eski kodu isteyen
    # önşartı karşılar (ve tersi). BLGE 2024-25 planıyla okuyan öğrenci
    # BBF 203E'yi geçiyordu ama BBF 301E/302E'nin önşartı "BLG 252E" diyordu:
    # 5. dönemin iki ana dersi engelli, program yarı boş kalıyordu. Yalnız
    # önşart görünümünde — plan slotu doldurmaz (muafiyetlerle aynı ilke).
    # İkisi de varsa İYİ olanı: eski kodla FF, yeni kodla BB alan öğrenci.
    # Faz 105: beyanlar zincir kurabildiği için GRUP olarak (bkz.
    # `declared.code_migration_groups`).
    for grup in set(code_migration_groups().values()):
        notlar = [view[k] for k in grup if k in view]
        if notlar:
            iyi = max(notlar, key=lambda g: GRADE_POINTS.get(str(g).upper(), -1.0))
            for k in grup:
                view[k] = iyi
    return view


def passed(grade: str | None) -> bool:
    return grade is not None and GRADE_POINTS.get(str(grade).upper(), -1.0) >= PASSING_MIN


# --------------------------------------------------------------- denklik grafı
@dataclass(frozen=True)
class Equivalence:
    id: int
    target: str
    sources: tuple[tuple[str, str], ...]     # ((ders, min_not), ...) — HEPSİ gerekli
    confidence: str
    applies_to_cap: bool
    note: str | None = None


# ★ Kullanıcı DB'sinden gelen denkliklerin id'leri bu kadar ötelenir.
# İki ayrı dosyada ikisi de 1'den başlıyor; ötelemezsek `via_equivalence`
# yanlış denkliğe işaret ederdi — "bu ders şu denklikle sayıldı" derken
# BAŞKA bir denkliği göstermek, sessizce yanlış cevap vermenin ta kendisi.
BEYAN_ID_OFSET = 1_000_000_000


def _denklik_oku(con: sqlite3.Connection, include_cap: bool,
                 ofset: int = 0, yalniz_beyan: bool = False,
                 beyan_haric: bool = False) -> list[Equivalence]:
    out: list[Equivalence] = []
    # ★ Faz 110 — TEK sorgu. Denklik başına ayrı kaynak sorgusu 3183 resmî
    # denklikte çağrı başına ~40 ms tutuyordu; gerçek BLGE kurulumunda 14
    # çağrı = 0.59 sn (kurulumun %20'si). Sıra eskisiyle aynı: denklik id'si,
    # içinde kaynak kodu (eski sorgu birincil anahtar dizinini kullanıyordu).
    try:
        rows = list(con.execute(
            """SELECT e.id, e.target_course, e.confidence, e.applies_to_cap, e.note_raw,
                      s.course_code, s.min_grade
                 FROM equivalence e JOIN equivalence_source s ON s.equivalence_id = e.id
                ORDER BY e.id, s.course_code"""))
    except sqlite3.Error:
        # Tablo yoksa (eski kullanıcı DB'si) denklik yok demektir — çökmüyoruz.
        return out
    kaynaklar: dict[int, list] = {}
    satir: dict[int, tuple] = {}
    for row in rows:
        if include_cap and not row[3]:
            continue
        beyan = row[2] == "user_declared"
        if yalniz_beyan and not beyan:
            continue
        if beyan_haric and beyan:
            continue
        satir.setdefault(row[0], row)
        kaynaklar.setdefault(row[0], []).append((row[5], row[6] or "DD"))
    for eid, row in satir.items():
        out.append(Equivalence(eid + ofset, row[1], tuple(kaynaklar[eid]),
                               row[2], bool(row[3]), row[4]))
    return out


def load_equivalences(con: sqlite3.Connection, include_cap: bool = True,
                      ucon: sqlite3.Connection | None = None) -> list[Equivalence]:
    """Resmî denklikler katalogdan, BEYAN denklikleri kullanıcı DB'sinden.

    ★★ Faz 28 (inceleme B5). Beyanlar `reference.sqlite3`'e yazılıyordu ve
    `declared.py` "bunlar kişisel veri değil" diyordu; oysa
    `tools/gizlilik_denetimi.py` yayınlanan katalogda `user_declared`
    görürse HATA veriyordu. Aynı soruya iki kaynak farklı cevap veriyordu —
    ve denetim haklıydı: "şu dersim şunun yerine saysın" beyanı, hangi
    dersleri aldığını ve neye başvurduğunu ele veriyor.

    ⚠️ Referans DB'deki `user_declared` satırları HER DURUMDA yok sayılıyor
    — göç etmemiş eski dosyalarda kalıntı olabilirler ve oradan okumak,
    yayınlanan siteye kişisel beyan sızdırmanın yolu olurdu. Kayıp yok:
    beyanların asıl kaynağı `config/denklikler.toml` ve `declared.apply`
    açılışta onu kullanıcı DB'sine yeniden uyguluyor.

    ⚠️ `ucon` verilmezse beyanlar OKUNMAZ. Yayınlanan site için DOĞRU
    davranış (orada kişisel dosya zaten yok).
    """
    out = _denklik_oku(con, include_cap, beyan_haric=True)
    if ucon is not None:
        out += _denklik_oku(ucon, include_cap, ofset=BEYAN_ID_OFSET,
                            yalniz_beyan=True)
    return out


_KOD_PARCA = re.compile(r"^([A-ZÇĞİÖŞÜ]{2,4} \d{3,4})(E?)([A-Z]*)$")


def ingilizce_kod(code: str) -> str:
    """Kodun İngilizce yazımı: 'BLG 252' → 'BLG 252E', 'FIZ 101L' → 'FIZ 101EL'
    (dil eki laboratuvar ekinden ÖNCE — katalogda FIZ 101EL). Zaten E'liyse
    ya da biçim tanınmıyorsa kodun kendisi."""
    m = _KOD_PARCA.match(code or "")
    if not m:
        return code
    kok, _e, ek = m.groups()
    return f"{kok}E{ek}"


def _dil_yazimlari(eq: Equivalence) -> list[tuple[str, tuple[tuple[str, str], ...]]]:
    """Denkliğin uygulanacağı (hedef, kaynaklar) yazımları.

    ★★ Faz 110 — resmî sayfa (OBS DersPlanDenklikleri) kodları DİLDEN
    BAĞIMSIZ, taban biçimde yazıyor ("BBF 203 ≡ BLG 252"; 3183 kaynağın
    hiçbiri E'li değil). Motor birebir eşleştirdiği için İngilizce programdaki
    öğrencide (BBF 203E, BLG 252E) HİÇBİR resmî denklik tetiklenmiyordu —
    katalogdaki hedeflerin 1117'si yalnız E'li kodla var.
    Kural: DİL KORUNUR. Kaynaklar İngilizce yazımlarıyla sağlanırsa hedefin
    İngilizce yazımı kazanılır; Türkçe ise Türkçesi. Türkçe ders İngilizce
    anadal yuvasını doldurmaz (Faz 92 ilkesi: dil serbestliği yalnız
    ÇAP/yandal slotunda, `slot_codes`). Karışık dilli çok kaynaklı denklik
    tetiklenmez (ihtiyatlı).
    Kullanıcı BEYANLARI kodu tam yazıldığı gibi — beyan kendi dilini seçiyor."""
    yazim = [(eq.target, eq.sources)]
    if eq.confidence == "official":
        en = (ingilizce_kod(eq.target),
              tuple((ingilizce_kod(c), g) for c, g in eq.sources))
        if en != yazim[0]:
            yazim.append(en)
    return yazim


# ★★ Faz 110 — HIZ. 3183 resmî denklik iki dilde 6366 yazım; `slot_satisfied`
# her plan yuvası için genişletme istiyor (gerçek BLGE profilinde bir kurulumda
# 1724 çağrı) ve her çağrı bütün listeyi tur tur tarıyordu: kurulum 5.9 sn →
# 28.6 sn. İki önlem, SONUÇ AYNI:
#   * yazımlar ve "kaynak kod → yazımlar" dizini liste başına BİR kez kurulur
#     (liste nesnesine göre; önbellek listeyi TUTAR, kimlik yeniden
#     kullanılamaz — uzunluk ve uçlar da denetlenir: yerinde eklenen liste
#     yeniden kurulur);
#   * aynı not seti + aynı yazım kümesi için sonuç önbellekte (kopya döner).
#     Sonuç, üretildiği yazım listesinin KENDİSİYLE saklanır ve kimliği
#     denetlenir; eskimiş bir kurulumun sonucu dönemez.
_YAZIM_ONBELLEK: list = []          # [(liste, (uzunluk, ilk, son), yazımlar, dizin)]
_GENIS_ONBELLEK: dict = {}          # anahtar → (yazımlar, notlar, via)


def _yazim_dizini(eqs: list) -> tuple[list, dict]:
    imza = (len(eqs), eqs[0] if eqs else None, eqs[-1] if eqs else None)
    for i, (liste, im, yazimlar, dizin) in enumerate(_YAZIM_ONBELLEK):
        if liste is eqs:
            if im[0] == imza[0] and im[1] is imza[1] and im[2] is imza[2]:
                return yazimlar, dizin
            del _YAZIM_ONBELLEK[i]      # liste yerinde değişmiş: yeniden kur
            break
    yazimlar = [(eq.id, hedef, kaynaklar)
                for eq in eqs for hedef, kaynaklar in _dil_yazimlari(eq)]
    dizin: dict[str, list[int]] = {}
    for n, (_id, _h, kaynaklar) in enumerate(yazimlar):
        for kod, _g in kaynaklar:
            dizin.setdefault(kod, []).append(n)
    if len(_YAZIM_ONBELLEK) >= 8:
        _YAZIM_ONBELLEK.pop(0)
        _GENIS_ONBELLEK.clear()
    _YAZIM_ONBELLEK.append((eqs, imza, yazimlar, dizin))
    return yazimlar, dizin


def expand_with_equivalences(
    grades: Mapping[str, str],
    equivalences: Iterable[Equivalence],
    max_rounds: int = 10,
) -> tuple[dict[str, str], dict[str, int]]:
    """Denklikleri TRANSİTİF olarak uygular.

    {A,B} -> C ve {C} -> D varsa, A+B alan öğrenci D'yi de almış sayılır.
    Sabit noktaya kadar döner (en fazla max_rounds, döngüye karşı emniyet).
    Resmî denklikler iki dilde de (bkz. `_dil_yazimlari`).

    Her turda yalnız bir önceki turda kazanılan (ya da notu yükselen) kodlara
    dokunan yazımlar denenir.

    ★★ Faz 110 — NOT: öğrencinin ulaşabildiği EN İYİ not. Bir yazım, kaynaklarının
    en düşük notunu verir; hedefe birden çok yoldan varılıyorsa (ya da hedefi
    kendisi almış ama denk dersten daha iyi geçmişse — FF alıp denğini BB ile
    geçen) iyisi kalır. Eşitlikte ham not. Monoton bir sabit nokta: sonuç
    listenin SIRASINDAN bağımsız (eski "ilk bulunan" kuralında 300 rastgele
    transkriptin 5'inde not sıraya göre değişiyordu). Kod göçü görünümünün
    (`prereq_view`, Faz 104) kuralıyla aynı. Genişletilmiş notlar yalnız
    önşart/slot/harita için; not ORTALAMASI ham notlardan (`policy.gpa`).

    Dönüş: (genişletilmiş notlar, ders -> hangi denklik id'siyle kazanıldı)
    """
    eqs = equivalences if isinstance(equivalences, list) else list(equivalences)
    if not eqs:
        return dict(grades), {}
    yazimlar, dizin = _yazim_dizini(eqs)
    anahtar = (id(yazimlar), max_rounds,
               frozenset((k, str(v)) for k, v in grades.items()))
    hazir = _GENIS_ONBELLEK.get(anahtar)
    if hazir is not None and hazir[0] is yazimlar:
        return dict(hazir[1]), dict(hazir[2])

    result = dict(grades)
    via: dict[str, int] = {}
    yeni = set(result)
    for _ in range(max_rounds):
        adaylar = sorted({n for kod in yeni for n in dizin.get(kod, ())})
        yeni = set()
        for n in adaylar:
            eq_id, target, sources = yazimlar[n]
            got = []
            for code, min_grade in sources:
                have = result.get(code)
                need = GRADE_POINTS.get(min_grade.upper(), PASSING_MIN)
                if have is None or GRADE_POINTS.get(str(have).upper(), -1.0) < need:
                    got = None
                    break
                got.append(str(have).upper())
            if not got:
                continue
            # denklikle kazanılan derse, kaynakların EN DÜŞÜK notunu ver
            aday = min(got, key=lambda g: GRADE_POINTS.get(g, 0.0))
            eski = result.get(target)
            if eski is not None and (GRADE_POINTS.get(aday, -1.0)
                                     <= GRADE_POINTS.get(str(eski).upper(), -1.0)):
                continue
            result[target] = aday
            via[target] = eq_id
            yeni.add(target)
        if not yeni:
            break
    if len(_GENIS_ONBELLEK) > 4096:
        _GENIS_ONBELLEK.clear()
    _GENIS_ONBELLEK[anahtar] = (yazimlar, dict(result), dict(via))
    return result, via


# ------------------------------------------------------------- alınabilirlik
def can_take(con: sqlite3.Connection, course_code: str,
             grades: Mapping[str, str]) -> Verdict:
    """Bu ders, elimizdeki notlarla alınabilir mi?"""
    row = con.execute(
        "SELECT reason FROM prereq_unparsed WHERE course_code=?", (course_code,)).fetchone()
    if row:
        return Verdict(Status.UNKNOWN, note=f"önşart verisi çözülemedi: {row[0]}")

    raw = con.execute("SELECT prereq_raw FROM course WHERE code=?", (course_code,)).fetchone()
    if raw is None:
        return Verdict(Status.UNKNOWN, note="ders course tablosunda yok")
    tree = parse(raw[0]).tree
    if tree is None:
        return Verdict(Status.OK)                    # önşartı yok
    grades = prereq_view(grades)
    if tree.satisfied(grades):
        return Verdict(Status.OK)
    missing = [(n.course, n.min_grade) for n in tree.missing(grades)]
    return Verdict(Status.BLOCKED, missing=missing)


def can_take_tree(tree: Node | None, grades: Mapping[str, str]) -> Verdict:
    """Ağaç zaten belleğe alınmışsa DB'ye gitmeyen sürüm (öneri motoru için)."""
    if tree is None:
        return Verdict(Status.OK)
    if tree.satisfied(grades):
        return Verdict(Status.OK)
    return Verdict(Status.BLOCKED,
                   missing=[(n.course, n.min_grade) for n in tree.missing(grades)])


# ------------------------------------------------------------ slot karşılanma
def dil_esi(con: sqlite3.Connection | None, code: str | None) -> str | None:
    """Dersin öbür dildeki kodu ('EHB 222' ↔ 'EHB 222E') — yalnız katalogda
    GERÇEKTEN varsa ve kredisi aynıysa.

    ★★ Faz 92. `alt_course_codes` eşi yalnız İKİ KOD AYNI PLANDA yazılıysa
    taşıyor. OBS'nin ÇAP planları çoğunlukla Türkçe kod yazıyor ("BLG_EHB":
    EHB 222); BLGE öğrencisi aynı dersi anadalında İngilizce almış (EHB 222E).
    Ders geçilmişti ama ÇAP paneli 0/16 diyor, "EHB 222 — bu dönem şube
    açılmamıştır" diye engel gösteriyor, ÇAP ortalamasına almıyordu. BLG
    öğrencisinin geçtiği EHB 222 ise iki planı da dolduruyordu — aynı ders,
    dile göre farklı sonuç.
    ⚠️ Eş körlemesine türetilmiyor: katalogda olmalı; iki kredi de biliniyor
    ve farklıysa aynı ders olduğundan emin değiliz (obs_plan'daki kuralla
    aynı; ölçüm: 2809 çiftin 2807'sinde kredi ve AKTS birebir aynı).
    ⚠️ Yalnız ÇAP/yandal planlarında kullanılıyor (bkz. `dil_serbest`).
    """
    code = (code or "").strip()
    if con is None or not code:
        return None
    # Bir istekte aynı kod defalarca soruluyor (her slot denetimi) — istek
    # önbelleği (Faz 91).
    return IST.bellek(("dil_esi", id(con), code), lambda: _dil_esi(con, code))


def ingilizce_esi(con: sqlite3.Connection | None, code: str | None) -> str | None:
    """Türkçe kodun İngilizce eşi ('EHB 222' → 'EHB 222E'); İngilizce kodda None.

    ★ YÖN ÖNEMLİ. İngilizce şubede alınan ders Türkçe kodlu slotu doldurur —
    araç bunu zaten kabul ediyordu (bkz. obs_plan'ın TR/E birleştirmesi,
    öneri motorunun "iki dilin şubesi" notu). TERSİ belirsiz: Türkçe ders
    İngilizce dersin yerine geçmeyebilir (Faz 10, HTA/HTAE ilkesi) — orada
    `discover` "dil eki farklı" diye DÜŞÜK güvenli öneri yapıyor, karar
    kullanıcının. Slot eşleştirmesi bu yüzden yalnız bu yönü kullanıyor.
    """
    code = (code or "").strip()
    if not code or code.endswith("E"):
        return None
    return dil_esi(con, code)


def _dil_esi(con: sqlite3.Connection, code: str) -> str | None:
    # ★ Faz 113 — laboratuvar eki dil ekinden SONRA: 'FIZ 101L' ↔ 'FIZ 101EL'.
    # Eskiden 'FIZ 101LE' aranıyordu (yok): lab dersinin eşi hiç bulunmuyordu,
    # yol haritası "FIZ 101L veya FIZ 101EL" önşartında Türkçe kodu dış ders
    # sayıp geçilmiş varsayıyordu (BLG 4901E kartı: "önşart varsayıldı:
    # FIZ 101L, FIZ 102L" — öğrenci FIZ 101EL'i geçmişti).
    m = _KOD_PARCA.match(code)
    if m and m.group(3):
        kok, e, ek = m.groups()
        es = f"{kok}{ek}" if e else f"{kok}E{ek}"
    else:
        es = code[:-1] if code.endswith("E") else code + "E"
    kredi = dict(con.execute("SELECT code, credits FROM course WHERE code IN (?, ?)",
                             (code, es)).fetchall())
    if es not in kredi:
        return None
    a, b = kredi.get(code), kredi[es]
    if a is not None and b is not None and abs(float(a) - float(b)) > 0.01:
        return None
    return es


def dil_serbest(plan_type: str | None) -> bool:
    """Bu plan türünde dersin öbür dildeki kodu da sayılır mı?

    ★ ÇAP/yandal planı BÖLÜME tanımlı, dile değil (bkz.
    normalize.base_program_code): OBS aynı "BLG_EHB" planını BLG'ye de BLGE'ye
    de veriyor. Anadal (lisans) planında ise dil programın kendi kuralı —
    İngilizce programın zorunlu dersini Türkçe şubenin karşılayıp
    karşılamadığını araç bilemez. Bilmediğini "tamamlandı" diye göstermek,
    öğrenciye saymayan bir dersi atlatmak olurdu; orada yalnız planın kendi
    yazdığı eşler (`alt_course_codes`) sayılıyor.
    """
    return (plan_type or "") in ("cap", "yandal")


def slot_codes(row, con: sqlite3.Connection | None = None) -> list[str]:
    """Bir REQUIRED slotu dolduran BÜTÜN kodlar: ana kod + öbür dildeki karşılığı.

    `row` içinde `course_code` ve `alt_course_codes` bulunmalı. Eski taramalarda
    `alt_course_codes` yok/NULL — o zaman tek elemanlı liste döner, davranış
    değişmez.

    `con` verilirse Türkçe kodun katalogdaki İngilizce eşi de eklenir (bkz.
    `ingilizce_esi` — yalnız bu yön). Çağıran yalnız ÇAP/yandal slotu için
    veriyor (bkz. `dil_serbest`).
    """
    try:
        main = row["course_code"]
        alt = row["alt_course_codes"]
    except (IndexError, KeyError, TypeError):
        main, alt = (row[1] if len(row) > 1 else None), None
    out = [c for c in [main] if c]
    for code in filter(None, (alt or "").split(",")):
        if code not in out:
            out.append(code)
    if con is not None:
        for code in list(out):
            es = ingilizce_esi(con, code)
            if es and es not in out:
                out.append(es)
    return out


def plan_codes(con: sqlite3.Connection, *plan_ids: int | None,
               pools: bool = False, esler: bool = False) -> set[str]:
    """Planlardaki bütün ders kodları — ÖBÜR DİLİN kodu dahil.

    Tek yerde topladık çünkü aynı sorgu üç yerde ayrı ayrı yazılıydı ve
    `alt_course_codes` eklenince üçünü birden düzeltmek gerekti. Biri unutulsaydı
    (ör. ÇAP ortalaması) İngilizce şubede alınan ders sessizce hesap dışı kalırdı.

    `esler=True`: Türkçe kodların KATALOGDAKİ İngilizce eşi de (bkz.
    `ingilizce_esi`) —
    "bu ders bu planda sayılır mı" soranlar için (ÇAP ortalaması, başvuru
    taraması). Varsayılan kapalı: "planındaki dersler" listesini gezip her
    birine ayrı uyarı yazan yerler (katalog tabanı) eşi ikinci bir ders sanır.
    """
    ids = [p for p in plan_ids if p]
    if not ids:
        return set()
    marks = ",".join("?" * len(ids))
    out: set[str] = set()
    for row in con.execute(
            f"""SELECT course_code, alt_course_codes FROM plan_slot
                WHERE plan_id IN ({marks}) AND course_code IS NOT NULL""", ids):
        out.add(row[0])
        out |= {c for c in (row[1] or "").split(",") if c}
    if esler:
        out |= {es for es in (ingilizce_esi(con, c) for c in list(out)) if es}
    if pools:
        out |= {r[0] for r in con.execute(
            f"""SELECT po.course_code FROM pool_option po JOIN plan_slot ps
                ON ps.id = po.slot_id WHERE ps.plan_id IN ({marks})""", ids)}
    return out


@dataclass
class Fulfilment:
    satisfied: bool
    course: str | None = None            # slotu dolduran ders
    via_equivalence: int | None = None   # doğrudan ise None
    candidates: list[str] = field(default_factory=list)   # havuzda uygun olanlar


def slot_satisfied(con: sqlite3.Connection, slot_id: int, grades: Mapping[str, str],
                   equivalences: Iterable[Equivalence] | None = None) -> Fulfilment:
    """Bir plan slotu geçilen derslerle karşılanıyor mu?"""
    slot = con.execute(
        """SELECT s.slot_kind, s.course_code, s.alt_course_codes, p.plan_type
           FROM plan_slot s LEFT JOIN plan p ON p.id = s.plan_id WHERE s.id=?""",
        (slot_id,)).fetchone()
    if slot is None:
        return Fulfilment(False)

    expanded, via = (dict(grades), {})
    if equivalences:
        expanded, via = expand_with_equivalences(grades, equivalences)

    if slot[0] == "REQUIRED":
        # ★ Aynı dersin Türkçe/İngilizce kodu (EEF 110 / EEF 110E): plan ikisini
        # birden yazıyor, öğrenci BİRİNİ alıyor. Yalnız ilkine bakmak, İngilizce
        # şubeyi almış öğrenciye dersi hiç almamış muamelesi yapardı.
        # ★ Faz 92: ÇAP/yandal slotunda katalogdaki dil eşi de (bkz. dil_esi).
        for code in slot_codes(slot, con if dil_serbest(slot[3]) else None):
            if passed(expanded.get(code)):
                return Fulfilment(True, code, via.get(code))
        return Fulfilment(False)

    options = [r[0] for r in con.execute(
        "SELECT course_code FROM pool_option WHERE slot_id=?", (slot_id,))]
    hits = [c for c in options if passed(expanded.get(c))]
    if hits:
        return Fulfilment(True, hits[0], via.get(hits[0]), candidates=hits)
    return Fulfilment(False, candidates=options)


# ------------------------------------------------------------ bulunduğun dönem
def infer_term(con: sqlite3.Connection, plan_id: int | None,
               grades: Mapping[str, str],
               equivalences: Iterable[Equivalence] | None = None) -> int:
    """Öğrencinin kaçıncı dönemde olduğunun **tahmini**.

    Ölçüt: geçilmiş slotların en derin `term_no`'su. 5. dönem dersini geçmiş
    biri en az 5. dönemdedir.

    ⚠️ Bu bir tahmin, kayıt kaydı değil. Kayıt donduran, yaz okulu okuyan ya da
    alttan çok ders taşıyan öğrencide şaşar. O yüzden arayüz hangi değerin
    kullanıldığını **yazıyor** ve `config/settings.toml` içinden `donem` ile
    ezilebiliyor. Sessizce tahmin edip yanlış listelemek en kötüsü olurdu.
    """
    if plan_id is None:
        return 0
    equivalences = list(equivalences or [])
    best = 0
    for row in con.execute(
        """SELECT id, term_no FROM plan_slot
           WHERE plan_id=? AND term_no IS NOT NULL""", (plan_id,)
    ):
        if row[1] > best and slot_satisfied(con, row[0], grades, equivalences).satisfied:
            best = row[1]
    return best


# --------------------------------------------------------------- ilerleme
def plan_progress(con: sqlite3.Connection, plan_id: int, grades: Mapping[str, str],
                  equivalences: Iterable[Equivalence] | None = None) -> dict:
    """Bir plandaki ilerleme. ÇAP ve anadal için AYRI çağrılır (kredi karışmasın)."""
    # AKTS önce slottan, yoksa ders kataloğundan. itu-helper kaynaklı planlarda
    # slot AKTS'si yok; katalog olmadan anadal toplamı 0 görünüyordu.
    slots = con.execute(
        """SELECT ps.id, ps.slot_kind, ps.course_code, ps.pool_category,
                  COALESCE(ps.ects, c.ects)       AS ects,
                  COALESCE(ps.credits, c.credits) AS credits
           FROM plan_slot ps
           LEFT JOIN course c ON c.code = ps.course_code
           WHERE ps.plan_id=?""", (plan_id,)).fetchall()
    equivalences = list(equivalences or [])
    done = ects_done = ects_total = cr_done = cr_total = 0
    by_category: dict[str, list[int]] = {}
    open_slots: list[int] = []
    open_required = 0

    for slot in slots:
        ects = slot["ects"] or 0.0
        credits = slot["credits"] or 0.0
        ects_total += ects
        cr_total += credits
        result = slot_satisfied(con, slot[0], grades, equivalences)
        key = slot[3] or ("ZORUNLU" if slot[1] == "REQUIRED" else "-")
        bucket = by_category.setdefault(key, [0, 0])
        bucket[1] += 1
        if result.satisfied:
            done += 1
            ects_done += ects
            cr_done += credits
            bucket[0] += 1
        else:
            open_slots.append(slot[0])
            if slot[1] == "REQUIRED":
                open_required += 1

    return {
        "plan_id": plan_id,
        "slots_done": done,
        "slots_total": len(slots),
        "open_required": open_required,
        "ects_done": round(ects_done, 1),
        "ects_total": round(ects_total, 1),
        "credits_done": round(cr_done, 1),
        "credits_total": round(cr_total, 1),
        "percent": round(100 * done / len(slots), 1) if slots else 0.0,
        "by_category": {k: tuple(v) for k, v in sorted(by_category.items())},
        "open_slots": open_slots,
    }
