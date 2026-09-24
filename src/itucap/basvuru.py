"""FAZ 12 — "Bu programa başvurabilir miyim?"

Yapılacaklar 1.3. Parçaların hepsi zaten vardı ve ayrı ayrı duruyordu:

* GNO ve kredi hesabı           (Faz 9)
* mevzuat eşikleri              (`config/kurallar.toml`, Faz 12'de doğrulandı)
* bütün programların planları    (Faz 10)
* bir plandaki ilerleme          (`rules.plan_progress`)

Eksik olan, bunları birleştirip tek cümle kurmaktı: *"şu programlara
başvurabilirsin, şunlarda şu kadar iş kalır."*

────────────────────────────────────────────────────────────────────────────
Bu modülün üç kuralı var; üçü de aynı sebeple: **bilinmeyeni bilinen gibi
göstermemek.**

1.  **Hesaplanamayan şart "sağlandı" sayılmaz.** Yönerge Madde 15 başvuru
    için "anadal başarı sıralamasında üst %20" şartı koyuyor. Sıralama
    verisi bizde YOK ve OBS'den de çekilmiyor. Bu şart `ok=None` ile
    "buradan bakılamaz" olarak döner — sessizce atlansaydı araç, öğrenciye
    karşılamadığı bir şartı karşılıyormuş gibi gösterebilirdi.

2.  **ÇAP planı yoksa ÇAP tahmini yapılmaz.** Bir programın *lisans* planı
    elimizde olabilir ama ÇAP planı olmayabilir (ÇAP planı lisansın küçük
    bir alt kümesidir — BLG'de 59.5'e karşı ~140 kredi). Lisans planından
    "ÇAP'ta şu kadar kalır" demek, sayıyı iki katından fazla şişirirdi.
    Böyle programlar `missing_plan=True` ile ayrı listelenir.

3.  **Zaten alınmış ders sayılır, ama muafiyet krediye sayılmaz.** Projede
    baştan beri geçerli olan ayrım; burada da `plan_progress` üzerinden
    aynı kural işliyor.
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from typing import Mapping

from . import config
from .normalize import base_program_code, merge_language_variants, strip_accents
from . import policy as POL
from . import rules as R
from . import student as S

# Yönerge Madde 15/22 — başvuru penceresi. Kredi aralığı hangi yarıyıla
# başvurulabileceğini belirliyor.
#   30–59.99 kredi (2. sınıf)  → 3. yarıyıl
#   60–94.99 kredi (3. sınıf)  → 5. yarıyıl
# Üst sınır ÇAP için 94.99; yandalda yönerge yalnız alt sınır veriyor.
CAP_CREDIT_MIN = 30.0
CAP_CREDIT_MAX = 94.99
YANDAL_CREDIT_MIN = 30.0


@dataclass(frozen=True)
class Check:
    """Tek bir başvuru şartı.

    `ok` üç değerli: True (sağlanıyor) · False (sağlanmıyor) ·
    **None (buradan bakılamaz)**. Üçüncüsü olmasaydı, kontrol edemediğimiz
    şartı ya sağlanmış ya sağlanmamış saymak zorunda kalırdık; ikisi de
    yanlış cevap.
    """
    key: str
    label: str
    ok: bool | None
    detail: str = ""
    source: str = ""

    @property
    def blocking(self) -> bool:
        return self.ok is False


@dataclass(frozen=True)
class Option:
    """Başvurulabilecek bir program ve orada zaten sayılan dersler.

    ⚠️ Burada **kredi yok** ve bu bilinçli. 22.08.2026'da kullanıcı kalan
    kredinin yanlış çıktığını bildirdi; sebebi bulundu (bkz. `survey`):
    kullanıcının kendi ÇAP'ı için beyan ettiği denklikler bütün programların
    planlarına uygulanıyordu, "tamamlanan" şişiyordu. Denklik kapsamı
    düzeltildi ama kalan kredi hâlâ havuz slotlarının nasıl sayıldığına
    bağlı bir tahmin. Duramayacağımız bir sayıyı göstermiyoruz —
    `already` (kod eşleşmesi) sağlam, o kalıyor.
    """
    program_code: str
    program_name: str
    plan_id: int | None = None
    plan_title: str = ""
    plan_iteration: str = ""
    host: str = ""
    missing_plan: bool = False
    slots_total: int = 0
    already: list[str] = field(default_factory=list)

    @property
    def already_count(self) -> int:
        return len(self.already)


@dataclass(frozen=True)
class Survey:
    kind: str                      # 'cap' | 'yandal'
    checks: list[Check]
    options: list[Option]
    missing: list[Option]          # planı çekilmemiş programlar
    gpa: float = 0.0
    credits: float = 0.0
    anadal: str = ""
    # ★ Bu plan tipinden katalogda HİÇ plan var mı?
    #
    # 22.08.2026'da doğrulandı: OBS `PlanTipiKodu=yandal` isteğini kabul
    # ediyor ve "Akademik programa bağlı ders planı bulunmamaktadır" diyor.
    # 128 programın hiçbirinde yandal planı yok — uç çalışıyor, VERİ yok.
    #
    # Bu ayrım arayüz için kritik: "henüz çekilmedi" ile "yayınlanmamış"
    # farklı şeyler. Birincisinde kullanıcıya `make all-plans` demek doğru,
    # ikincisinde YANLIŞ — çalıştırsa da bir şey gelmeyecek, boşuna uğraşır.
    plan_type_available: bool = True
    # Başka anadalların ÇAP planı olduğu için elenen plan sayısı.
    # ★ Eleyen kural kendini göstermek zorunda — sessizce süzülen bir liste
    # "İTÜ'de bu kadar ÇAP varmış" diye yanlış bir izlenim bırakırdı.
    other_host: int = 0

    @property
    def eligible(self) -> bool:
        """Bilinen hiçbir şart düşmüyorsa True.

        ⚠️ "Başvurabilirsin" demek DEĞİL — `unknown` boş değilse bakılamayan
        şart var. Arayüz ikisini birlikte göstermek zorunda.
        """
        return not any(c.blocking for c in self.checks)

    @property
    def unknown(self) -> list[Check]:
        return [c for c in self.checks if c.ok is None]


def _checks(kind: str, gpa_value: float, credits: float,
            rules_path=None, has_data: bool = True) -> list[Check]:
    """`has_data=False` → transkript girilmemiş: hiçbir şart DEĞERLENDİRİLMEZ.

    ★ 23.08.2026: transkript yokken GNO 0.00 çıkıyor ve bütün şartlar ✗
    işaretleniyordu — ekran "başvuramazsın" diyordu. Oysa bilinen bir şey yok.
    Veri yokluğunu başarısızlık gibi göstermek, bu araçtaki en pahalı hata
    türünün ta kendisi.
    """
    out: list[Check] = []
    yok = "Transkript girilmediğinden bu şart değerlendirilememektedir."
    for t in POL.load_thresholds(path=rules_path, program=kind, kind="basvuru"):
        out.append(Check(
            key=t.key, label=t.label,
            ok=(gpa_value + 1e-9 >= t.minimum) if has_data else None,
            detail=(f"GNO {gpa_value:.2f} / gereken {t.minimum:.2f}"
                    if has_data else f"{yok} Gereken: {t.minimum:.2f}"),
            source=t.source or t.note,
        ))

    lo = CAP_CREDIT_MIN if kind == "cap" else YANDAL_CREDIT_MIN
    hi = CAP_CREDIT_MAX if kind == "cap" else None
    if not has_data:
        ok, detail = None, (yok + (f" Pencere: {lo:g}–{hi:g}" if hi
                                   else f" En az: {lo:g}"))
    elif hi is None:
        ok = credits + 1e-9 >= lo
        detail = f"{credits:g} kredi / en az {lo:g}"
    else:
        ok = lo - 1e-9 <= credits <= hi + 1e-9
        detail = f"{credits:g} kredi / pencere {lo:g}–{hi:g}"
    out.append(Check("kredi_penceresi", "Başvuru kredi penceresi", ok, detail,
                     "ÇAP/Yandal Yönergesi Madde 15 / 22"))

    # ★ Hesaplanamayan şart. Sıralama verisi ne bizde var ne OBS'den geliyor.
    if kind == "cap":
        out.append(Check(
            "siralama", "Anadal başarı sıralamasında üst %20", None,
            "Sıralama verisi bu araçta bulunmamaktadır; OBS'den veya bölümden öğrenilebilir.",
            "ÇAP/Yandal Yönergesi Madde 15"))
    else:
        out.append(Check(
            "onceki_dersler", "Başvurulan yarıyıla kadarki TÜM dersler başarılmış",
            None,
            "Hangi derslerin 'o yarıyıla kadar' sayıldığı kayıt yılına bağlıdır; "
            "transkriptte başarısız ders varsa danışmanınıza danışınız.",
            "ÇAP/Yandal Yönergesi Madde 22/a"))
    return out


def best_plan(rows) -> object | None:
    """Aynı programın birden çok iterasyonundan GEÇERLİ olanı seç.

    OBS aynı ÇAP çifti için yıl aralığı başına ayrı plan tutuyor:

        TUMMUH_BLG … 2013-2014 / Güz Dönemi Öncesi
        TUMMUH_BLG … 2013-2014 / Güz ile 2018-2019 / Güz Dönemleri Arası
        TUMMUH_BLG … 2018-2019 / Güz Dönemi Sonrası      ← yürürlükte olan

    `id` sırasına güvenmek yanlıştı: id'ler OBS'nin iç sayacı, kronolojik
    değil. "Sonrası" ile biten iterasyon açık uçlu olandır; yoksa en büyük
    başlangıç yılı alınır.
    """
    def rank(row):
        it = (row["iteration"] or "") if hasattr(row, "keys") else ""
        year = 0
        m = re.search(r"(\d{4})\s*-\s*\d{4}", it)
        if m:
            year = int(m.group(1))
        return (1 if "Sonras" in it else 0, year, row["id"] > 0, row["id"])
    return max(rows, key=rank) if rows else None


def host_matches(host: str | None, anadal: str, anadal_name: str = "") -> bool:
    """Bu ÇAP planı BU anadalın öğrencisine açık mı?

    ★ ÇAP planları (anadal, hedef) ÇİFTİNE göre tanımlı: `TUMMUH_BLG`,
    `INS_MAK`, `MIM_FK_END`… `host_program_code` çiftin ANADAL yanı.

    Kullanıcı 22.08.2026'da haklı olarak şunu söyledi: listede başka
    bölümlerin ÇAP planları görünüyordu. `INS_MAK` planı İnşaat
    öğrencisinin planı; Harita öğrencisi ona başvuramaz. Onu listelemek,
    var olmayan bir seçenek göstermekti.
    """
    host = (host or "").upper()
    if not host:
        return False                      # host bilinmiyorsa iddia etmiyoruz
    if host == (anadal or "").upper():
        return True
    if host in UMBRELLA:
        return UMBRELLA[host](anadal_name or "")
    return False


def _fold(text: str) -> str:
    """Türkçe-güvenli karşılaştırma anahtarı.

    ⚠️ `"Mühendisliği".upper()` Python'da **"MÜHENDISLIĞI"** verir — noktalı
    `i`, noktasız `I`'ya döner. "MÜHENDİSL" arayan bir kontrol bu yüzden
    hiçbir mühendislik programını tutmuyordu (ilk yazımda tam bu oldu).
    Aksanları düşürüp küçük harfe indirmek iki yönde de güvenli.
    """
    return strip_accents(text).lower()


# Programın kendisi olmayan "şemsiye" host kodları. Bir ÇAP planı bu kodla
# tanımlıysa tek bir bölümün değil, bir GRUBUN öğrencilerine açıktır.
# Gruba kimin girdiğini program ADINDAN çıkarıyoruz — kod listesini elle
# tutmak, yeni bölüm açıldığında sessizce yanlışa düşerdi.
UMBRELLA = {
    "TUMMUH": lambda name: "muhendis" in _fold(name),      # tüm mühendislik
    "MIM_FK": lambda name: "mimarl" in _fold(name) or "tasarim" in _fold(name),
}


def survey(con: sqlite3.Connection, ucon: sqlite3.Connection, student_id: int,
           kind: str = "cap", exclude: set[str] | None = None,
           anadal: str = "", rules_path=None) -> Survey:
    """Başvurulabilecek programlar ve orada zaten sayılan dersler.

    `exclude` — zaten kayıtlı olunan programlar (anadal, mevcut ÇAP).
    `anadal`  — öğrencinin anadal kodu. Verilirse YALNIZ o anadala açık
                planlar listelenir (bkz. `host_matches`).

    ★ Denklik kapsamı: kullanıcının `denklikler.toml`'da beyan ettiği
    denklikler KENDİ ÇAP'ı için geçerlidir — Fakülte Yönetim Kurulu kararı
    o çifte özeldir. Onları her programın planına uygulamak "tamamlandı"
    sayısını şişiriyordu; başvurmadığın bir programda saydırılmamış bir
    dersi saydırılmış göstermek, aracın vermemesi gereken cevap. Burada
    yalnız **birebir ders kodu** eşleşmesi sayılıyor.
    """
    kind = kind if kind in ("cap", "yandal") else "cap"
    exclude = {c for c in (exclude or set()) if c}

    graded = S.graded(ucon, student_id)
    uncertain = S.uncertain_grades(ucon, student_id)
    gpa = POL.gpa(con, graded, uncertain)
    have_credits = POL.earned_credits(con, graded)
    passed_codes = {c for c, g in graded.items() if R.passed(g)}

    checks = _checks(kind, gpa.value, have_credits, rules_path,
                     has_data=bool(graded))

    # ★ Yandal programları LİSANS PROGRAMI DEĞİL: 'ECN_YD' (Economics Minor),
    # 'ECN' lisans programından ayrı bir şey ve `level='YD'` ile saklanıyor.
    # Tek seviyeye bakmak, yandal taramasında hiçbir program bulamamak
    # demekti — arayüz "yandal yok" diyordu, oysa vardı.
    seviye = "YD" if kind == "yandal" else "LS"
    names = {r[0]: r[1] for r in con.execute(
        "SELECT code, name FROM program WHERE level=?", (seviye,))}
    if not names and kind == "yandal":
        # Program tablosu henüz doldurulmamışsa planların kendisinden türet;
        # ad yoksa kod gösterilir — boş liste göstermekten iyi.
        names = {r[0]: (r[1] or r[0]) for r in con.execute(
            """SELECT p.program_code, COALESCE(pr.name, p.title)
               FROM plan p LEFT JOIN program pr ON pr.code = p.program_code
               WHERE p.plan_type='yandal' AND p.program_code IS NOT NULL""")}
    anadal = (anadal or "").upper()
    anadal_name = names.get(anadal, "")

    # Katalogda bu tipten hiç plan var mı? (host süzmesinden ÖNCE bakılıyor:
    # "sana açık plan yok" ile "bu tipte hiç plan yok" ayrı sorular.)
    plan_type_available = bool(con.execute(
        "SELECT 1 FROM plan WHERE plan_type=? LIMIT 1", (kind,)).fetchone())

    by_program: dict[str, list] = {}
    other_host = 0
    for row in con.execute(
            """SELECT id, program_code, title, iteration, host_program_code
               FROM plan WHERE plan_type=? AND program_code IS NOT NULL""",
            (kind,)):
        # ★ Host süzmesi yalnız ÇAP'ta anlamlı: ÇAP planı (anadal, hedef)
        # çiftine bağlı. Yandal programı herkese açık, bir çifte bağlı değil —
        # süzseydik hepsi elenirdi.
        if kind == "cap" and anadal and not host_matches(
                row["host_program_code"], anadal, anadal_name):
            other_host += 1
            continue
        by_program.setdefault(row["program_code"], []).append(row)

    plans = {code: best_plan(rows) for code, rows in by_program.items()}

    # ★ Dil varyantı tekleştirme (kullanıcı isteği 23.08.2026): ÇAP/yandal
    # seçiminde BLG ile BLGE ayrımı YOK — plan bölüme tanımlı, dile değil.
    # İkisini ayrı satır göstermek, kullanıcıya olmayan bir seçim yaptırıyordu.
    # ⚠️ Yalnız ikisi de listede varsa; 'HTAE'nin 'HTA' diye bir eşi yok.
    goster = set(merge_language_variants(names))
    for kod in list(names):
        if kod not in goster and kod in plans and base_program_code(kod) not in plans:
            goster.add(kod)          # eşinin PLANI yoksa varyantı gizlemeyiz

    options: list[Option] = []
    missing: list[Option] = []
    for code, name in sorted(names.items()):
        if code in exclude or code not in goster:
            continue
        row = plans.get(code)
        if row is None:
            # ★ Lisans planından ÇAP tahmini YAPMIYORUZ — bkz. modül başlığı.
            missing.append(Option(code, name, missing_plan=True))
            continue
        # ★ Öbür dilin kodu da sayılır: İngilizce şubede alınmış ders,
        # Türkçe kodla yazılmış slotu doldurur (bkz. rules.plan_codes).
        slot_codes = R.plan_codes(con, row["id"])
        total = con.execute("SELECT COUNT(*) FROM plan_slot WHERE plan_id=?",
                            (row["id"],)).fetchone()[0]
        options.append(Option(
            program_code=code, program_name=name, plan_id=row["id"],
            plan_title=row["title"] or "",
            plan_iteration=row["iteration"] or "",
            host=row["host_program_code"] or "",
            slots_total=total,
            already=sorted({c for c in slot_codes if c in passed_codes}),
        ))

    # Zaten en çok dersi sayılan program önce — kalan işin tek sağlam ölçüsü.
    options.sort(key=lambda o: (-len(o.already), o.slots_total, o.program_code))
    missing.sort(key=lambda o: o.program_code)
    return Survey(kind=kind, checks=checks, options=options, missing=missing,
                  gpa=gpa.value, credits=have_credits, anadal=anadal,
                  other_host=other_host,
                  plan_type_available=plan_type_available)


def to_json(s: Survey, limit: int = 60) -> dict:
    """Arayüzün beklediği biçim. ⚠️ Kredi alanı YOK — bkz. `Option`."""
    return {
        "kind": s.kind,
        "gpa": s.gpa,
        "credits": s.credits,
        "anadal": s.anadal,
        "eligible": s.eligible,
        "checks": [{"key": c.key, "label": c.label, "ok": c.ok,
                    "detail": c.detail, "source": c.source} for c in s.checks],
        "unknownCount": len(s.unknown),
        "options": [{
            "code": o.program_code, "name": o.program_name,
            "planId": o.plan_id, "planTitle": o.plan_title,
            "iteration": o.plan_iteration, "host": o.host,
            "slotsTotal": o.slots_total,
            "already": o.already[:12], "alreadyCount": o.already_count,
        } for o in s.options[:limit]],
        "optionCount": len(s.options),
        "otherHost": s.other_host,
        "planTypeAvailable": s.plan_type_available,
        "missing": [{"code": o.program_code, "name": o.program_name}
                    for o in s.missing],
        "missingCount": len(s.missing),
    }


def describe(s: Survey) -> str:
    """Komut satırı çıktısı."""
    label = "ÇAP" if s.kind == "cap" else "YANDAL"
    who = f" · anadal {s.anadal}" if s.anadal else ""
    out = [f"{label} BAŞVURUSU — GNO {s.gpa:.2f} · {s.credits:g} kredi{who}", ""]
    for c in s.checks:
        mark = "—" if c.ok is None else ("✅" if c.ok else "❌")
        out.append(f"  {mark} {c.label}")
        if c.detail:
            out.append(f"       {c.detail}")
    out.append("")
    if not s.eligible:
        out.append("  Bilinen şartlardan en az biri sağlanmıyor.")
    elif s.unknown:
        out.append(f"  Bakılabilen şartlar tamam; {len(s.unknown)} şart "
                   f"bu araçtan doğrulanamıyor.")
    else:
        out.append("  Bakılabilen tüm şartlar sağlanıyor.")
    out.append("")

    if s.options:
        out.append(f"SANA AÇIK {label} PROGRAMLARI ({len(s.options)})")
        out.append(f"  {'KOD':<8} {'DERS':>5} {'SAYILAN':>8}  AD")
        for o in s.options[:20]:
            out.append(f"  {o.program_code:<8} {o.slots_total:>5} "
                       f"{o.already_count:>8}  {o.program_name[:44]}")
        out.append("")
        out.append("  'SAYILAN' = bu planda birebir kodu tutan, geçtiğin ders.")
        out.append("  ⚠️ Kalan KREDİ yazmıyoruz: havuz slotlarının nasıl sayıldığı")
        out.append("     programdan programa değişiyor, duramayacağımız bir sayı olurdu.")
    if s.other_host:
        out.append("")
        out.append(f"  ({s.other_host} plan başka anadalların ÇAP'ı olduğu için "
                   f"listelenmedi.)")
    if not s.plan_type_available:
        out.append("")
        out.append(f"⚠️  Katalogda HİÇ {label.lower()} planı yok.")
        out.append("   OBS bu plan tipini tanıyor ama plan yayınlamıyor")
        out.append("   ('Akademik programa bağlı ders planı bulunmamaktadır').")
        out.append("   `make all-plans` bunu DEĞİŞTİRMEZ — çekilecek veri yok.")
        out.append("   Yandal düşünüyorsan bölümünden plan iste.")
    elif s.missing:
        out.append("")
        out.append(f"PLANI ÇEKİLMEMİŞ ({len(s.missing)} program) — "
                   f"`make all-plans` bunları doldurur.")
        out.append("  " + ", ".join(o.program_code for o in s.missing[:25])
                   + (" …" if len(s.missing) > 25 else ""))
    return "\n".join(out)
