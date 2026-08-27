"""FAZ 7 — Mevzuat kısıtları: önşart metninde YAZMAYAN kurallar.

Bir dersin alınabilirliği yalnız `course.prereq_raw`'dan çıkmıyor. Bazı kısıtlar
yönetmelikte durur, ders kataloğunda görünmez. En somut örneği **bitirme
çalışması**: önşart alanı boş olabilir ama belli bir krediyi tamamlamadan
alınamaz.

Bu kuralları koda gömmüyoruz. `config/kurallar.toml` içinde beyan ediliyorlar
ki mevzuat değişince kod değil yapılandırma değişsin — ve kullanıcı hangi
kuralın kendisine uygulandığını dosyayı açıp görebilsin.

⚠️ Aynı ayrım burada da geçerli: **muafiyet krediye sayılmaz.** Muaf sayılan
ders önşartı açar (bkz. `rules.prereq_view`) ama kazanılmış kredi değildir.
Bitirme eşiği gerçek notlardan hesaplanır.
"""
from __future__ import annotations

import fnmatch
import sqlite3
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping

from . import config
from .prereq import CONDITIONAL_PASS, GRADE_POINTS
from .rules import passed

DEFAULT_PATH = config.ROOT / "config" / "kurallar.toml"

# Beyan yoksa uygulanan varsayılan. İTÜ lisans yönetmeliği: bitirme çalışmasına
# başlayabilmek için asgari kredi şartı vardır. Kullanıcı teyidi (21.08.2026):
# **95 kredi**. Kod kalıbı 4901/4902 İTÜ'de bitirme çalışması I/II demektir.
DEFAULT_RULES = [
    {
        "ad": "Bitirme çalışması",
        "min_kredi": 95.0,
        "kalip": ["* 4901", "* 4901E", "* 4902", "* 4902E"],
        # ★ Ölçüm: katalogda adında bitirme/graduation geçen 97 ders var,
        # kod kalıbı bunların yalnız 9'unu kapsıyordu (baskın kod 492/492E).
        "ad_kalip": ["bitirme", "graduation"],
        "aciklama": "Bitirme çalışmasına başlamak için en az 95 kredi gerekir.",
    }
]


@dataclass(frozen=True)
class CreditRule:
    name: str
    min_credits: float
    courses: tuple[str, ...] = ()      # açık ders kodları
    patterns: tuple[str, ...] = ()     # 'GEO 49*' gibi kalıplar
    # ★★ AD KALIBI (ilk kullanıcı incelemesi D1, 24.08.2026).
    #
    # Ölçüm: katalogda adında "bitirme"/"graduation" geçen **97** ders var.
    # Kural yalnız `4901/4902` kodlarını tanıyordu ve bunların **9**'unu
    # kapsıyordu. Baskın kodlar `492` (43) ve `492E` (38).
    #
    # Somut sonucu: 3. dönemdeki, hiç ders geçmemiş bir BLGE öğrencisine
    # ÖNERİ 1'de `BLG 492E — Graduation Project` çıkıyordu (puan 47.5) —
    # aynı sayfadaki mevzuat paneli "0 / 95 kredi · 95 kredi eksik" derken.
    #
    # ⚠️ Kalıbı `* 492` diye genişletmedim: o kodda adı "Tasarım Projesi"
    # olan **20** ders daha var ve beyan edilen kural "bitirme projesi"
    # diyor. Beyan edilmiş bir kuralı, kapsadığını doğrulamadığım derslere
    # genişletmek bu projede yapmamaya çalıştığımız şeyin ta kendisi.
    # Ad üzerinden eşleşmek hem kesin hem beyana sadık.
    name_patterns: tuple[str, ...] = ()
    note: str = ""

    def matches(self, course_code: str, course_name: str = "") -> bool:
        code = course_code.upper().strip()
        if code in {c.upper().strip() for c in self.courses}:
            return True
        if any(fnmatch.fnmatch(code, p.upper().strip()) for p in self.patterns):
            return True
        if course_name and self.name_patterns:
            ad = course_name.casefold()
            return any(p.casefold() in ad for p in self.name_patterns if p)
        return False


@dataclass
class CreditVerdict:
    """Kredi eşiği sonucu. `ok=False` ise ders bu dönem alınamaz."""
    ok: bool
    rule: CreditRule | None = None
    have: float = 0.0

    @property
    def missing(self) -> float:
        return 0.0 if self.ok or self.rule is None else round(
            self.rule.min_credits - self.have, 1)

    def __bool__(self) -> bool:
        return self.ok


def load_rules(path: Path | None = None) -> list[CreditRule]:
    """`config/kurallar.toml` -> kurallar. Dosya yoksa varsayılana düşer."""
    path = DEFAULT_PATH if path is None else path
    blocks = DEFAULT_RULES
    if path.exists():
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
        declared = raw.get("kredi_esigi") or []
        if declared:
            blocks = declared
    out = []
    for b in blocks:
        out.append(CreditRule(
            name=str(b.get("ad") or "kredi eşiği"),
            min_credits=float(b.get("min_kredi") or 0),
            courses=tuple(b.get("dersler") or ()),
            patterns=tuple(b.get("kalip") or ()),
            name_patterns=tuple(b.get("ad_kalip") or ()),
            note=str(b.get("aciklama") or ""),
        ))
    return [r for r in out if r.min_credits > 0]


# --------------------------------------------------------------- kredi sayımı
def earned_credits(con: sqlite3.Connection, grades: Mapping[str, str]) -> float:
    """Geçilen derslerden kazanılan toplam İTÜ kredisi.

    Not: transkriptte olup katalogda bulunmayan eski dersler 0 kredi sayılır.
    Bu, eşiği **olduğundan zor** gösterir — güvenli yön. Kaç dersin kredisinin
    bilinmediği `credit_report` ile ayrıca raporlanıyor ki sessiz kalmasın.
    """
    total = 0.0
    for code, grade in grades.items():
        if not passed(grade):
            continue
        row = con.execute("SELECT credits FROM course WHERE code=?", (code,)).fetchone()
        total += float((row[0] if row else 0) or 0)
    return round(total, 1)


def unknown_credit_courses(con: sqlite3.Connection,
                           grades: Mapping[str, str]) -> list[str]:
    """Geçilmiş ama kredisi bilinmeyen dersler — eşik hesabını eksik bırakırlar."""
    out = []
    for code, grade in grades.items():
        if not passed(grade):
            continue
        row = con.execute("SELECT credits FROM course WHERE code=?", (code,)).fetchone()
        if row is None or not row[0]:
            out.append(code)
    return sorted(out)


# ------------------------------------------------------------------ GNO
# ★ GNO'ya SAYILMAYAN işaretler — yönetmelik MADDE 20:
# "BL, E, BZ veya M olan dersler hariç".
#
#   BL = kredisiz dersten başarılı   -> geçti, ortalamaya girmez
#   BZ = kredisiz dersten başarısız  -> kaldı, ortalamaya girmez
#   M / MU = muaf                    -> sayılmış, ortalamaya girmez
#   T  = dersten çekilme             -> ders alınmamış sayılıyor
#   E  = tasarım projesi tamamlanmadı
#
# BL/M'yi 4.00, BZ/T'yi 0.00 sayan bir hesap GNO'yu bozar: ilki şişirir ve
# "eşiği geçiyorsun" der, ikincisi haksız yere düşürür. Hepsi dışarıda.
# (`GRADE_POINTS` içindeki değerler ÖNŞART karşılaştırması için — BL geçer
# sayılmalı ki staj önşartı açılsın. İki bağlam ayrı.)
GPA_EXCLUDED = {"BL", "BZ", "M", "MU", "T", "E"}

# 0 kredili derste kullanılabilecek notlar — arayüz bunları öne çıkarıyor.
PASS_FAIL_GRADES = ("BL", "BZ")


@dataclass
class Gpa:
    value: float                       # ağırlıklı ortalama
    credits: float                     # ortalamaya giren kredi
    counted: int                       # ortalamaya giren ders sayısı
    skipped_no_credit: list[str] = field(default_factory=list)
    skipped_not_graded: list[str] = field(default_factory=list)
    uncertain: list[str] = field(default_factory=list)
    # ★ MADDE 20'de "şartlı başarmış" sayılan notlar (DC+…DD). Mezuniyette
    # sayılmaları GNO şartına bağlı; şart HENÜZ DOĞRULANMADI, o yüzden motor
    # bir kural uygulamıyor — yalnız hangi dersler olduğunu söylüyor.
    conditional: list[str] = field(default_factory=list)

    @property
    def partial(self) -> bool:
        """Hesabın eksik olduğu biliniyor mu? Arayüz bunu SÖYLEMEK zorunda."""
        return bool(self.skipped_no_credit or self.uncertain)


def gpa(con: sqlite3.Connection, graded: Mapping[str, str],
        uncertain: Iterable[str] = ()) -> Gpa:
    """Transkriptten ağırlıklı GNO.

    ⚠️ Bu bir **tahmin**, OBS'nin resmi GNO'su değil. Üç kaynaktan sapabilir:
    kredisi bilinmeyen ders, notu girilmemiş ders (DD varsayılıyor), ve
    tekrar edilen derste hangi notun sayıldığı. Üçü de ayrıca raporlanıyor
    ki arayüz sayıyı olduğundan kesin göstermesin.
    """
    unknown_grade = set(uncertain)
    total_points = total_credits = 0.0
    counted = 0
    no_credit: list[str] = []
    not_graded: list[str] = []
    conditional: list[str] = []
    for code, grade in graded.items():
        g = str(grade or "").upper()
        if g in GPA_EXCLUDED or g not in GRADE_POINTS:
            not_graded.append(code)
            continue
        row = con.execute("SELECT credits FROM course WHERE code=?", (code,)).fetchone()
        credits = float((row[0] if row else 0) or 0)
        if credits <= 0:
            no_credit.append(code)       # 0 kredili ders GNO'ya girmez
            continue
        total_points += GRADE_POINTS[g] * credits
        total_credits += credits
        counted += 1
        # ★ Notu GİRİLMEMİŞ ders DD varsayılıyor (en kötü durum). Onu
        # "şartlı geçer" diye raporlamak, kullanıcıya var olmayan bir sorun
        # göstermek olurdu — gerçek not girilince çoğu yukarı çıkacak.
        if g in CONDITIONAL_PASS and code not in unknown_grade:
            conditional.append(code)
    value = round(total_points / total_credits, 2) if total_credits else 0.0
    return Gpa(value, round(total_credits, 1), counted,
               sorted(no_credit), sorted(not_graded),
               sorted(unknown_grade & set(graded)),
               sorted(conditional))


@dataclass(frozen=True)
class Threshold:
    key: str
    label: str
    minimum: float
    verified: bool
    note: str = ""
    # Hangi programa uygulanır: "cap" · "yandal" · "genel" (ikisi de).
    program: str = "genel"
    # Ne zaman bakılır: "basvuru" · "devam" · "mezuniyet" · "" (belirsiz).
    kind: str = ""
    # Madde 19/k gibi "bir defaya mahsus altına düşülebilir" toleransı.
    tolerance: int = 0
    source: str = ""

    def applies_to(self, program: str) -> bool:
        """`program` bu eşiğin kapsamında mı? 'genel' her şeye uyar."""
        return self.program in ("genel", "") or program in ("genel", "") \
            or self.program == program


def load_thresholds(path: Path | None = None,
                    program: str | None = None,
                    kind: str | None = None) -> list[Threshold]:
    """GNO eşikleri — `config/kurallar.toml` içindeki `[[gno_esigi]]`.

    ★ `dogrulandi = false` olan eşik arayüzde **doğrulanmamış** diye
    işaretleniyor. Mevzuattan teyit edilmemiş bir sayıyı kesinmiş gibi
    göstermek, bu projede kaçındığımız tam olarak bu hata.

    `program`/`kind` verilirse yalnız eşleşenler döner. Eşiğin kendi
    `program`ı yazılmamışsa "genel" sayılır ve elenmez — eski beyanlar
    böylece çalışmaya devam eder.
    """
    path = DEFAULT_PATH if path is None else path
    blocks = []
    if path.exists():
        blocks = tomllib.loads(path.read_text(encoding="utf-8")).get("gno_esigi") or []
    out = []
    for b in blocks:
        try:
            minimum = float(b.get("min_gno"))
        except (TypeError, ValueError):
            continue
        try:
            tol = int(b.get("tolerans") or 0)
        except (TypeError, ValueError):
            tol = 0
        t = Threshold(
            key=str(b.get("anahtar") or b.get("ad") or "gno"),
            label=str(b.get("ad") or "GNO eşiği"),
            minimum=minimum,
            verified=bool(b.get("dogrulandi")),
            note=str(b.get("aciklama") or ""),
            program=str(b.get("program") or "genel"),
            kind=str(b.get("tur") or ""),
            tolerance=tol,
            source=str(b.get("kaynak") or ""),
        )
        if program is not None and not t.applies_to(program):
            continue
        if kind is not None and t.kind and t.kind != kind:
            continue
        out.append(t)
    return out


# ------------------------------------------------------ şartlı başarı (M.20/2-b)
@dataclass(frozen=True)
class ConditionalRule:
    """MADDE 20/2-b'nin "şartlı başarmış"ı ve MADDE 31/1'deki şartı.

    ★ İki soruyu ayrı tutuyor:
      * **Ders tamamlandı mı?** → evet, şartlı not geçer sayılır (`passes`).
      * **Mezun olunabilir mi?** → genel ortalama `graduation_min_gpa`
        düzeyine çıkmışsa.

    İkisini tek soruya indirmek iki yönde de hata üretirdi: dersi haksız yere
    kapatmak ya da mezuniyeti haksız yere açmak.
    """
    grades: tuple[str, ...] = CONDITIONAL_PASS
    passes: bool = True
    graduation_min_gpa: float | None = None
    verified: bool = False
    source: str = ""


def load_conditional(path: Path | None = None) -> ConditionalRule:
    path = DEFAULT_PATH if path is None else path
    block: Mapping = {}
    if path.exists():
        block = tomllib.loads(path.read_text(encoding="utf-8")).get("sartli_basari") or {}
    grades = tuple(str(g).upper() for g in (block.get("notlar") or CONDITIONAL_PASS))
    try:
        min_gpa = float(block["mezuniyet_min_gno"])
    except (KeyError, TypeError, ValueError):
        min_gpa = None
    return ConditionalRule(
        grades=grades or CONDITIONAL_PASS,
        passes=bool(block.get("gecer", True)),
        graduation_min_gpa=min_gpa,
        verified=bool(block.get("dogrulandi")),
        source=str(block.get("kaynak") or ""),
    )


# ------------------------------------------------- dönem kredi yükü (MADDE 17)
# İTÜ Lisans Eğitim ve Öğretim Yönetmeliği MADDE 17 (Değişik: RG 22/07/2022-31900)
#
# (1) ... birinci yarıyıl öğrencileri ve **ÇAP öğrencileri** ile son sınıf
#     öğrencileri hariç olmak üzere, gözetim listesinde bulunmayan öğrencilerin
#     kredi yükü **en az 13, en çok 22 kredi** olmak zorundadır.
#
# (2) a) Daha fazla kredi almak isteyen öğrencilerden; **25 kredi dahil** en az
#     **2.25** GNO, **25 kredinin üzerinde** en az **3.00** GNO aranır.
#
# İki fıkra AYRI şeyler söylüyor ve bunu karıştırmamak önemli:
#   * (1) bir BANT (13–22) ve ÇAP öğrencisi bu banttan MUAF.
#   * (2) bandın üstüne çıkmanın GNO şartı ve "her öğrenci" diyor — muafiyet yok.
# Yani ÇAP öğrencisinin alt sınırı yok ama üst sınırı GNO'suna bağlı.


@dataclass(frozen=True)
class LoadBand:
    """GNO'ya bağlı bir kredi tavanı basamağı."""
    label: str
    max_credits: float
    min_gpa: float


@dataclass
class LoadLimit:
    minimum: float          # 0 = alt sınır uygulanmıyor (muaf)
    maximum: float
    reasons: list[str] = field(default_factory=list)
    exempt_from_minimum: bool = False
    verified: bool = True
    source: str = ""
    next_band: LoadBand | None = None      # bir üst basamak ve şartı


def load_bands(path: Path | None = None) -> tuple[list[LoadBand], dict]:
    """`[[kredi_yuku]]` basamakları + `[kredi_yuku_bant]` alt/üst bandı."""
    path = DEFAULT_PATH if path is None else path
    raw = {}
    if path.exists():
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    bands = []
    for b in raw.get("kredi_yuku") or []:
        try:
            bands.append(LoadBand(str(b.get("ad") or ""),
                                  float(b.get("max_kredi")),
                                  float(b.get("min_gno") or 0)))
        except (TypeError, ValueError):
            continue
    bands.sort(key=lambda b: b.max_credits)
    return bands, raw.get("kredi_yuku_bant") or {}


def load_limit(gpa_value: float, second_kind: str = "cap",
               first_term: bool = False, final_year: bool = False,
               path: Path | None = None) -> LoadLimit | None:
    """Yönetmeliğe göre bu dönem alabileceğin en az / en çok kredi.

    `None` dönerse kural beyan edilmemiş demektir — arayüz hiçbir şey iddia
    etmez. Sessizce bir sayı uydurmaktan iyidir.
    """
    bands, band_cfg = load_bands(path)
    if not bands and not band_cfg:
        return None

    reasons: list[str] = []
    allowed = 0.0
    nxt: LoadBand | None = None
    for band in bands:
        if gpa_value + 1e-9 >= band.min_gpa:
            allowed = max(allowed, band.max_credits)
        elif nxt is None:
            nxt = band
    if bands and allowed:
        hit = max((b for b in bands if b.max_credits == allowed),
                  key=lambda b: b.min_gpa)
        reasons.append(f"GNO {gpa_value:.2f} → en çok {allowed:g} kredi"
                       + (f" ({hit.label})" if hit.label else ""))
    if nxt:
        reasons.append(f"{nxt.max_credits:g} krediye çıkmak için GNO ≥ "
                       f"{nxt.min_gpa:.2f} gerekiyor")

    minimum = float(band_cfg.get("min_kredi") or 0)
    exempt = False
    exemptions = {str(x).lower() for x in (band_cfg.get("muaf") or [])}
    if second_kind == "cap" and "cap" in exemptions:
        exempt, why = True, "ÇAP öğrencisi"
    elif second_kind == "yandal" and "yandal" in exemptions:
        exempt, why = True, "yandal öğrencisi"
    elif first_term and "birinci_yariyil" in exemptions:
        exempt, why = True, "birinci yarıyıl"
    elif final_year and "son_sinif" in exemptions:
        exempt, why = True, "son sınıf"
    if exempt:
        reasons.append(f"alt sınır uygulanmıyor — {why}")
        minimum = 0.0
    elif minimum:
        reasons.append(f"alt sınır {minimum:g} kredi")

    band_max = float(band_cfg.get("max_kredi") or 0)
    if band_max and not allowed:
        allowed = band_max
    return LoadLimit(minimum=minimum, maximum=allowed or band_max,
                     reasons=reasons, exempt_from_minimum=exempt,
                     verified=bool(band_cfg.get("dogrulandi")),
                     source=str(band_cfg.get("kaynak") or ""),
                     next_band=nxt)


# ------------------------------------------------------------------ kontrol
def check(course_code: str, credits_have: float,
          rules: list[CreditRule] | None = None,
          course_name: str = "") -> CreditVerdict:
    """Bu ders, kazanılmış krediyle alınabilir mi?

    Birden fazla kural eşleşirse **en katısı** uygulanır.

    ⚠️ `course_name` isteğe bağlı ve VARSAYILAN BOŞ: ad verilmezse eski
    davranış aynen sürüyor. Ad kalıbı olan kurallar yalnız ad geldiğinde
    devreye giriyor — çağıranı zorunlu tutmak, adı olmayan yerlerde sessizce
    "kural yok" demeye çevirirdi.
    """
    hits = [r for r in (rules if rules is not None else load_rules())
            if r.matches(course_code, course_name)]
    if not hits:
        return CreditVerdict(True)
    strictest = max(hits, key=lambda r: r.min_credits)
    if credits_have + 1e-9 >= strictest.min_credits:
        return CreditVerdict(True, strictest, credits_have)
    return CreditVerdict(False, strictest, credits_have)


def describe(rules: list[CreditRule] | None = None) -> str:
    rules = rules if rules is not None else load_rules()
    if not rules:
        return "Kredi eşiği kuralı tanımlı değil."
    lines = ["KREDİ EŞİĞİ KURALLARI"]
    for r in rules:
        what = ", ".join([*r.courses, *r.patterns]) or "-"
        lines.append(f"  {r.name}: en az {r.min_credits:g} kredi  ({what})")
        if r.note:
            lines.append(f"    {r.note}")
    return "\n".join(lines)


# ------------------------------- ikinci anadaldan asgari yarıyıl kredisi
# ÇAP/Yandal Yönergesi:
#   "İkinci anadala 3. yarıyılda başlayan öğrenci her yarıyıl en az 6,
#    5. yarıyılda başlayan öğrenci ise her yarıyıl en az 9 kredilik ders
#    almak zorundadır. … talep etmesi halinde … ÇAP Koordinatörünün uygun
#    görüşü ve Fakülte Yönetim Kurulu Kararı ile … yarıya kadar
#    düşürülebilir."
#
# ★ MADDE 17'deki banttan BAŞKA bir kural. Karıştırmak tehlikeli:
#     MADDE 17/1 → TOPLAM yük bandı (13–22); ÇAP öğrencisi MUAF.
#     bu kural   → yalnız İKİNCİ ANADALDAN alınacak asgari kredi.
#   ÇAP öğrencisinin toplam alt sınırı yok ama ikinci anadal tarafında
#   TABANI var. "ÇAP muaf" diye bunu da atlamak, öğrenciyi ÇAP'tan ilişik
#   kesilmeye götürebilirdi.

@dataclass(frozen=True)
class FloorRelief:
    """Tabanı indirme hakkı — KENDİLİĞİNDEN uygulanmaz."""
    ratio: float                       # "yarıya kadar" → 0.5
    conditions: tuple[str, ...] = ()
    deadline: str = ""
    automatic: bool = False
    verified: bool = False
    source: str = ""

    def reduced(self, minimum: float) -> float:
        return round(minimum * self.ratio, 2)


@dataclass(frozen=True)
class SecondFloor:
    """Bu yarıyıl ikinci anadaldan alınması gereken asgari kredi."""
    minimum: float
    start_term: int
    verified: bool = False
    source: str = ""
    relief: FloorRelief | None = None

    def satisfied_by(self, credits: float) -> bool:
        return credits + 1e-9 >= self.minimum

    @property
    def relieved_minimum(self) -> float | None:
        """İndirim ONAYLANIRSA taban ne olurdu? Onaylanmış varsaymıyoruz."""
        return self.relief.reduced(self.minimum) if self.relief else None


def load_relief(path: Path | None = None) -> FloorRelief | None:
    path = DEFAULT_PATH if path is None else path
    if not path.exists():
        return None
    block = tomllib.loads(path.read_text(encoding="utf-8")).get(
        "ikinci_anadal_taban_indirim") or {}
    try:
        ratio = float(block["oran"])
    except (KeyError, TypeError, ValueError):
        return None
    return FloorRelief(
        ratio=ratio,
        conditions=tuple(str(c) for c in (block.get("kosullar") or [])),
        deadline=str(block.get("son_tarih") or ""),
        # ⚠️ Varsayılan False. Yönerge "düşürülebilir" diyor, "düşürülür"
        # demiyor; şartı ve süresi var. Kendiliğinden uygulamak, alınmamış
        # bir kurul kararını alınmış saymak olurdu.
        automatic=bool(block.get("otomatik", False)),
        verified=bool(block.get("dogrulandi")),
        source=str(block.get("kaynak") or ""),
    )


def second_floor(start_term: int, path: Path | None = None) -> SecondFloor | None:
    """ÇAP'a `start_term`. yarıyılda başlayan öğrencinin yarıyıl tabanı.

    ★ `start_term` **başladığın** yarıyıl, bulunduğun değil. Beyan
    edilmemişse (0) `None` döner — motor hiçbir taban iddia etmez. Yanlış
    bir taban iki yönde de zarar: uydurulmuş bir kuralla "az aldın" demek,
    ya da gerçek tabanı atlayıp ilişik kesilmesine götürmek.

    Beyan edilen yarıyıl tam eşleşmiyorsa **en yakın küçük** basamak
    uygulanır (yönerge 3 ve 5'i sayıyor; 4. yarıyılda başlayan için 3'ün
    tabanı, 6'da başlayan için 5'inki). Yukarı yuvarlamak, yönergenin
    söylemediği bir yükümlülük yaratırdı.
    """
    path = DEFAULT_PATH if path is None else path
    if not path.exists() or not start_term:
        return None
    blocks = tomllib.loads(path.read_text(encoding="utf-8")).get(
        "ikinci_anadal_taban") or []
    tiers: list[tuple[int, float, bool, str]] = []
    for b in blocks:
        try:
            tiers.append((int(b["baslangic_yariyili"]), float(b["min_kredi"]),
                          bool(b.get("dogrulandi")), str(b.get("kaynak") or "")))
        except (KeyError, TypeError, ValueError):
            continue
    if not tiers:
        return None
    tiers.sort()
    hit = None
    for term, minimum, verified, source in tiers:
        if start_term >= term:
            hit = (term, minimum, verified, source)
    if hit is None:
        # Beyan edilen en küçük basamağın altında başlamış — yönerge bu
        # durumu saymıyor, biz de uydurmuyoruz.
        return None
    term, minimum, verified, source = hit
    return SecondFloor(minimum=minimum, start_term=term, verified=verified,
                       source=source, relief=load_relief(path))
