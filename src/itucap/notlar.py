"""FAZ 38 — Ders not dağılımı: AYRIŞTIRMA, SAKLAMA, OKUMA.

★★ Bu modül `sources/` altında DEĞİL ve olmamalı. `tools/site_kur.py`
tarayıcıya yalnız `ENGINE` listesindeki modülleri kopyalıyor; `sources/`
bilerek dışarıda, çünkü scraper'lar `httpx`/`selectolax` istiyor ve
tarayıcıda bunlar yok. İlk yazımda `ui.py` dağılımı `sources/`den import
etti ve **yayınlanan site açılmaz oldu**:

    ModuleNotFoundError: No module named 'itucap.sources'

`plans.py` de tam bu sebeple var ("tarama bağımlılığı YOK — web için
şart"). Ayrım: AĞ işi `sources/obs_notdagilimi.py`de, geri kalan burada.
`tests/test_site.py` artık bu sınırı kilitliyor.

Kaynak ve uç ayrıntısı: `sources/obs_notdagilimi.py` + `docs/obs-endpoints.md` §5.

Aşağısı kaynağın davranışı — ayrıştırıcının uyması gerekenler.

ESKİ BAŞLIK: OBS Ders Not Dağılımı (`/public/DersNotDagilimi`).

Kullanıcı hatırlattı (02.09.2026): *"derslerin not dağılımı verisine
ulaşabiliyor olabilirsin, bu İTÜ tarafından her dönem yayınlanıyor."*
`docs/fikirler.md` bu fikri **"elimizde böyle bir veri yok"** gerekçesiyle
reddetmişti. Gerekçe düştü: veri var, herkese açık ve tokensiz.

## Uç

    GET /public/DersNotDagilimi/NotDagilimiSearch?bransKodu=MAT&dersNo=103E&yil=2026

Cevap bir HTML **parçası**; içinde satır içi bir betikte:

    const ALL_DATA = [{"DonemKodu":"202630","YilAdi":"2025-2026",
                       "DonemTipAdi":"Summer Semester",
                       "ToplamAciklananOgrenci":991,
                       "Dagilim":[{"HarfNotu":"AA","Sayi":54,"Yuzde":5.45}, …]}, …];

★ Tek istek O YILIN **bütün yarıyıllarını** getiriyor — güz, bahar ve **yaz**.
  (Yaz dönemi verisi elimizde ilk kez var; `fikirler §2.3` için hammadde.)

## ⚠️ Üç tuzak — üçü de ölçüldü

1. **TR ve EN kodu BİRLEŞİK.** `dersNo=212` ile `dersNo=212E` bayt bayt aynı
   cevabı veriyor ve başlık `BLG212 - BLG212E` yazıyor. Yani dağılım bir
   ders ÇİFTİNE ait, tek bir koda değil. "BLG 212E'nin geçme oranı" demek
   veriyi olduğundan dar göstermek olurdu; kanonik anahtarı kaynağın kendi
   başlığından alıyoruz ve iki kodu da takma ad olarak saklıyoruz.

2. **Bulunamadı da HTTP 200.** Olmayan ders `<h4>… could not be found.</h4>`
   ile 200 dönüyor. Durum koduna bakan bir tarayıcı bunu "boş dağılım" diye
   kaydederdi — bu projede tekrar tekrar canımızı yakan **sessiz sıfır**.
   `parse` bu durumu `NotFound` olarak AYIRIYOR.

3. **`yil` bitiş yılı.** `yil=2026` → `YilAdi: "2025-2026"`, kodlar
   `202610/202620/202630`. Yani `202610` **2025-2026 Güz**, 2026-2027 değil.
   (Bu ölçüm `config.donem_adi`'daki bir yıl kaymasını da ortaya çıkardı.)

## Ne YAPMIYORUZ

* **Şubeye ya da hocaya bağlamıyoruz.** Kaynak dağılımı ders düzeyinde
  yayınlıyor; hoca kırılımı YOK. Bir şubenin hocasıyla dersin dağılımını
  yan yana koymak, veride olmayan bir nedensellik iddia etmek olurdu.
* **Puanlamaya sokmuyoruz.** Dağılımı öneri puanına katmak aracı "kolay ders
  bulucu"ya çevirirdi; hangi dersin alınacağı öğrencinin değer yargısı.
  Gösteriyoruz, karar vermiyoruz.
"""
from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field

from . import config, db

# Harf sırası kaynaktaki sırayla aynı (yüksekten alçağa + VF).
GRADES = ["AA", "BA+", "BA", "BB+", "BB", "CB+", "CB", "CC+", "CC",
          "DC+", "DC", "DD+", "DD", "FF", "VF"]

# ★ Başarısızlık İKİ AYRI şey: `FF` dersten kalmak, `VF` devamsızlıktan
# kalmak. Toplayıp "başarısızlık oranı" demek ikisini aynı sebep gibi
# gösterirdi — devamsızlık dersin zorluğu hakkında bir şey söylemez.
FAIL_GRADES = ("FF", "BZ")
ABSENT_GRADES = ("VF",)
# ★★ Faz 85 — BAŞARILI/BAŞARISIZ ile notlanan dersler (ATA 121, TUR 121 …).
# Gerçek katalogda kaynak bu derslerde harf yerine `BL`/`BZ` yayınlıyor
# (ATA 121 güz: BL 1579, BZ 336, VF 374). `prereq.GRADE_POINTS` BL'yi 1.0
# sayıyor; ortalama ona göre hesaplanınca ATA 121'e "ortalama 0.84" çıkıyor
# ve BZ "geçti" sayılıyordu. BL/BZ GNO'ya girmez: ortalama yalnız harf
# notlarından, BZ başarısızlık.
PASS_FAIL_GRADES = ("BL", "BZ")

SEASONS = {"10": "Güz", "20": "Bahar", "30": "Yaz"}

# ★ Faz 38b — ARTILARIN KATLANDIĞI KOVA.
#
# 15 harf, 15 ince sütun demek ve dağılımın ŞEKLİ kayboluyor (kullanıcı
# geri bildirimi: "+ lar yüzünden dağılım kötü gözüküyor"). Artıyı temel
# harfle aynı kovaya koyunca 9 sütun kalıyor ve şekil okunur oluyor.
#
# ⚠️ Bu bir KAYIP: `BA+` `BA`dan yüksek bir not. O yüzden (a) varsayılan
# görünüm bunu YAZIYOR, (b) ayrıntı bir tıkla geri geliyor, (c) ortalama
# HER ZAMAN 15 harften hesaplanıyor — kova yalnız çizim için.
GRADE_BUCKETS = {"AA": "AA", "BA+": "BA", "BA": "BA", "BB+": "BB", "BB": "BB",
                 "CB+": "CB", "CB": "CB", "CC+": "CC", "CC": "CC",
                 "DC+": "DC", "DC": "DC", "DD+": "DD", "DD": "DD",
                 "FF": "FF", "VF": "VF"}
BUCKET_ORDER = ["AA", "BA", "BB", "CB", "CC", "DC", "DD", "FF", "VF"]


def bucketise(counts: dict[str, int]) -> list[dict]:
    """15 harfi 9 kovaya indirir; her kovanın İÇİNDEKİ kırılım korunur."""
    out = {b: {"key": b, "total": 0, "parts": []} for b in BUCKET_ORDER}
    for harf in GRADES:
        n = counts.get(harf, 0)
        kova = GRADE_BUCKETS.get(harf)
        if kova is None:
            continue
        out[kova]["total"] += n
        out[kova]["parts"].append({"grade": harf, "n": n})
    kovalar = [out[b] for b in BUCKET_ORDER]
    # Faz 85 — BL/BZ yalnız VARSA ek kova: harf notlu derste boş iki sütun
    # çizmek dağılımın şeklini bozardı, BL/BZ'li derste hiç çizmemek de
    # öğrencilerin çoğunu grafikten silerdi.
    for harf in PASS_FAIL_GRADES:
        if counts.get(harf):
            kovalar.append({"key": harf, "total": counts[harf],
                            "parts": [{"grade": harf, "n": counts[harf]}]})
    return kovalar

_ALL_DATA_RE = re.compile(r"const\s+ALL_DATA\s*=\s*(\[.*?\])\s*;", re.S)
_HEAD_RE = re.compile(r"<h[1-6][^>]*>(.*?)</h[1-6]>", re.S)
# ⚠️ Ders numarasının SONUNDA birden fazla harf olabiliyor. Ölçüm
# (02.09.2026, 251 plan dersi): `ING 103CO`, `ING 103SC`, `ING 103AC`,
# `ING 103DD`, `FIZ 101EL`. Tek harfe izin veren ilk kalıp bu kodlarda
# `ValueError` fırlatıyordu — yani 251 dersin bir kısmı hiç sorulamıyordu.
_CODE_RE = re.compile(r"\b([A-ZÇĞİÖŞÜ]{2,4})\s?(\d{3,4}[A-Z]{0,3})\b")
_NOT_FOUND_RE = re.compile(r"could not be found|bulunamad", re.I)

class NotFound(Exception):
    """OBS bu ders/yıl için dağılım yayınlamamış. Boş dağılımdan FARKLI."""


@dataclass(frozen=True)
class TermDistribution:
    term: str                       # '202610'
    year_name: str                  # '2025-2026'
    term_name: str                  # 'Fall Semester'
    announced: int                  # ToplamAciklananOgrenci
    counts: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class CourseDistribution:
    key: str                        # kanonik anahtar: 'MAT 103'
    codes: tuple[str, ...]          # ('MAT 103', 'MAT 103E') — başlıktan
    title: str                      # ham başlık
    terms: tuple[TermDistribution, ...] = ()


# --------------------------------------------------------------- kod işleri
def split_code(code: str) -> tuple[str, str]:
    """`'MAT 103E'` → `('MAT', '103E')`. Uç bu iki alanı ayrı istiyor."""
    m = _CODE_RE.search((code or "").upper().strip())
    if not m:
        raise ValueError(f"ders kodu ayrıştırılamadı: {code!r}")
    return m.group(1), m.group(2)


def _norm(brans: str, ders_no: str) -> str:
    return f"{brans} {ders_no}"


def codes_from_title(title: str) -> tuple[str, ...]:
    """Başlıktaki ders kodları — `'MAT103 - MAT103E, Matematik I / …'`.

    ⚠️ Kodu biz TÜRETMİYORUZ. Sondaki `E`'yi atarak eş bulmak bu repoda
    başka yerlerde kullanılan bir sezgi; burada gerek yok çünkü **kaynak
    çiftin ikisini de yazıyor**. Sezgi yerine kaynağı okumak, `BLG 4901E`
    gibi 'E' ile biten ama İngilizce eşi başka olan kodlarda da doğru kalır.
    """
    bas = (title or "").split(",")[0]
    return tuple(dict.fromkeys(_norm(a, b) for a, b in _CODE_RE.findall(bas)))


# ---------------------------------------------------------------- ayrıştır
def parse(html: str, fallback_code: str = "") -> CourseDistribution:
    """HTML parçasını `CourseDistribution`'a çevirir.

    Dağılım yoksa `NotFound` fırlatır — çağıran "veri yok" ile "hepsi sıfır"
    arasındaki farkı görebilsin diye.
    """
    text = html or ""
    m = _ALL_DATA_RE.search(text)
    if not m:
        if _NOT_FOUND_RE.search(text):
            raise NotFound("OBS bu ders/yıl için dağılım yayınlamamış")
        # ⚠️ Ne veri ne de 'bulunamadı' — sayfa yapısı değişmiş olabilir.
        # Bunu 'veri yok' saymak sessiz kayıp olurdu.
        raise ValueError("ALL_DATA bulunamadı ve 'bulunamadı' mesajı da yok "
                         "— sayfa yapısı değişmiş olabilir")
    try:
        raw = json.loads(m.group(1))
    except json.JSONDecodeError as exc:
        raise ValueError(f"ALL_DATA JSON değil: {exc}") from exc

    head = _HEAD_RE.search(text)
    title = re.sub(r"\s+", " ", head.group(1)).strip() if head else ""
    codes = codes_from_title(title)
    if not codes and fallback_code:
        codes = (_norm(*split_code(fallback_code)),)
    if not codes:
        raise ValueError("başlıkta ders kodu yok")

    terms = []
    for blok in raw:
        counts = {}
        for satir in blok.get("Dagilim") or []:
            harf = str(satir.get("HarfNotu") or "").strip().upper()
            if harf:
                counts[harf] = int(satir.get("Sayi") or 0)
        terms.append(TermDistribution(
            term=str(blok.get("DonemKodu") or "").strip(),
            year_name=str(blok.get("YilAdi") or "").strip(),
            term_name=str(blok.get("DonemTipAdi") or "").strip(),
            announced=int(blok.get("ToplamAciklananOgrenci") or 0),
            counts=counts,
        ))
    # Dönem koduna göre azalan: en yeni önde.
    terms.sort(key=lambda t: t.term, reverse=True)
    return CourseDistribution(key=codes[0], codes=codes, title=title,
                              terms=tuple(terms))


# ------------------------------------------------------------------ sakla
def store(con: sqlite3.Connection, dist: CourseDistribution,
          year: int) -> int:
    """Dağılımı yaz. Aynı (anahtar, dönem) yeniden yazılır, birikmez."""
    n = 0
    for t in dist.terms:
        con.execute("DELETE FROM grade_distribution WHERE course_key=? AND term=?",
                    (dist.key, t.term))
        con.executemany(
            """INSERT INTO grade_distribution
                 (course_key, term, grade, students, announced, term_name, year_name)
               VALUES (?,?,?,?,?,?,?)""",
            [(dist.key, t.term, g, c, t.announced, t.term_name, t.year_name)
             for g, c in t.counts.items()])
        n += 1
    for kod in dist.codes:
        con.execute("""INSERT INTO grade_distribution_alias(course_code, course_key)
                       VALUES (?,?) ON CONFLICT(course_code) DO UPDATE SET
                         course_key=excluded.course_key""", (kod, dist.key))
    con.execute("""INSERT INTO grade_distribution_run
                     (course_key, year, terms, title, status, fetched_at)
                   VALUES (?,?,?,?,?,?)
                   ON CONFLICT(course_key, year) DO UPDATE SET
                     terms=excluded.terms, title=excluded.title,
                     status=excluded.status, fetched_at=excluded.fetched_at""",
                (dist.key, int(year), n, dist.title, "ok", db.now()))
    con.commit()
    return n


def store_missing(con: sqlite3.Connection, code: str, year: int) -> None:
    """★ 'Yayınlanmamış' da bir BİLGİ. Kaydedilmezse her tazelemede yeniden
    sorulur ve kullanıcı "neden bu derste veri yok" sorusuna cevap bulamaz."""
    brans, ders_no = split_code(code)
    con.execute("""INSERT INTO grade_distribution_run
                     (course_key, year, terms, title, status, fetched_at)
                   VALUES (?,?,0,'',?,?)
                   ON CONFLICT(course_key, year) DO UPDATE SET
                     terms=0, status=excluded.status, fetched_at=excluded.fetched_at""",
                (_norm(brans, ders_no), int(year), "yayinlanmamis", db.now()))
    con.commit()


# ------------------------------------------------------------------- oku
def lookup(con: sqlite3.Connection, code: str) -> str | None:
    """Ders kodundan kanonik anahtar. Bilinmiyorsa None — TAHMİN YOK."""
    try:
        kod = _norm(*split_code(code))
    except ValueError:
        return None
    row = con.execute(
        "SELECT course_key FROM grade_distribution_alias WHERE course_code=?",
        (kod,)).fetchone()
    return row[0] if row else None


def distribution(con: sqlite3.Connection, code: str,
                 term: str | None = None) -> dict | None:
    """Bir dersin dağılımı. `term` verilmezse EN YENİ dönem.

    ⚠️ 'En yeni' ile 'aynı yarıyıl' farklı şeyler. Güz dersinin bahar
    dağılımı çoğunlukla birkaç bütünlemeci demek (BLG 212E: bahar n=2,
    ikisi de FF). O yüzden `same_season` da dönüyor ve arayüz aynı
    yarıyılın verisini tercih edebiliyor.
    """
    key = lookup(con, code)
    if not key:
        return None
    rows = con.execute(
        """SELECT term, grade, students, announced, term_name, year_name
           FROM grade_distribution WHERE course_key=?
           ORDER BY term DESC""", (key,)).fetchall()
    if not rows:
        return None
    by_term: dict[str, dict] = {}
    for r in rows:
        blok = by_term.setdefault(r["term"], {
            "term": r["term"], "termName": r["term_name"],
            "yearName": r["year_name"], "announced": r["announced"],
            "counts": {}})
        blok["counts"][r["grade"]] = r["students"]
    donemler = [by_term[k] for k in sorted(by_term, reverse=True)]
    for d in donemler:
        d["season"] = SEASONS.get(d["term"][-2:], d["term"][-2:])
        d["summary"] = summarise(d["counts"], d["announced"])
    # ★★ Faz 38b — YARIYIL UYUŞMAZLIĞI ARTIK SESSİZ DEĞİL.
    #
    # `settings.term` güz ise ve elimizde yalnız BAHAR dağılımı varsa,
    # eskiden sessizce bahar gösteriliyordu. Ölçüm (176 ders): 36 dersin
    # güz dağılımı yok ve arayüz 31'inde bahar, 5'inde YAZ gösteriyordu.
    # Bir güz dersinin bahar dağılımı çoğunlukla birkaç bütünlemeci demek
    # (BLG 212: baharda n=2, ikisi de FF) — yani sayı var ama dersi
    # ANLATMIYOR. Gösteriyoruz ama "başka yarıyıl" diye işaretliyoruz.
    mevsim = str(term)[-2:] if term else ""
    aday = [d for d in donemler if mevsim and d["term"].endswith(mevsim)]
    secili = aday[0] if aday else donemler[0]
    return {"key": key, "codes": _codes_of(con, key),
            "terms": donemler, "selected": secili,
            "wantedSeason": SEASONS.get(mevsim) if mevsim else None,
            # ⚠️ Üç değerli: True/False/None (istenen yarıyıl bilinmiyor).
            "seasonMismatch": (None if not mevsim
                               else not secili["term"].endswith(mevsim)),
            "summary": secili["summary"]}


def _codes_of(con: sqlite3.Connection, key: str) -> list[str]:
    return [r[0] for r in con.execute(
        "SELECT course_code FROM grade_distribution_alias WHERE course_key=? "
        "ORDER BY course_code", (key,))]


def term_already_graded(con: sqlite3.Connection, term: str) -> int:
    """Bu dönemde kaç dersin notu AÇIKLANMIŞ.

    ★ Faz 38 — planladığın dönemin geçmişte kalıp kalmadığını takvimden
    tahmin etmiyoruz; kaynağa soruyoruz. Notu açıklanmış bir dönem için
    "ders seçiyorum" demek büyük ihtimalle yanlış `term` demektir.

    ⚠️ 0 dönmesi "dönem gelecekte" DEMEK DEĞİL: not dağılımı hiç
    çekilmemiş de olabilir. Çağıran taraf ikisini ayırmak zorunda.
    """
    if not term:
        return 0
    return con.execute(
        "SELECT COUNT(DISTINCT course_key) FROM grade_distribution WHERE term=?",
        (str(term),)).fetchone()[0]


def coverage(con: sqlite3.Connection) -> dict:
    """Elimizde ne kadar dağılım var — arayüz "veri yok" ile "hiç çekilmedi"
    arasındaki farkı yazabilsin diye."""
    n_ders = con.execute(
        "SELECT COUNT(DISTINCT course_key) FROM grade_distribution").fetchone()[0]
    n_yok = con.execute(
        "SELECT COUNT(*) FROM grade_distribution_run WHERE status='yayinlanmamis'"
    ).fetchone()[0]
    son = con.execute(
        "SELECT MAX(fetched_at) FROM grade_distribution_run").fetchone()[0]
    return {"courses": n_ders, "unpublished": n_yok, "fetchedAt": son}


def summarise(counts: dict[str, int], announced: int | None = None) -> dict:
    """Dağılımdan türetilen sayılar.

    ★ Ortalama, aracın **kendi GNO ölçeğiyle** aynı (`prereq.GRADE_POINTS`):
    `FF` ve `VF` sıfır puandır — İTÜ ortalamada ikisini de sayar. Buradaki
    ortalamayı başka bir kuralla hesaplamak, aynı sayfada iki farklı
    "ortalama" tanımı bırakırdı.
    ⚠️ Ama `VF` **devamsızlık**, `FF` başarısızlık: ikisi ayrı yüzde olarak
    da yazılıyor, çünkü düşük bir ortalamanın devam politikasından mı
    zorluktan mı geldiği okunabilmeli.

    ⚠️ ÖLÇÜM (02.09.2026): kaynağın kendi toplamı (`ToplamAciklananOgrenci`)
    harflerin toplamına HER ZAMAN eşit değil — MAT 103 güz 2988/2987,
    bahar 1682/1678. Aradaki kişiler listelenen 15 harfin dışında
    (`BL`/`BZ`/muafiyet olabilir). Birini öbürünün yerine yazmak veriyi
    düzeltmek olurdu; ikisini de taşıyıp farkı `gap` ile söylüyoruz.
    """
    from .prereq import GRADE_POINTS

    n = sum(counts.values())
    fail = sum(counts.get(g, 0) for g in FAIL_GRADES)
    absent = sum(counts.get(g, 0) for g in ABSENT_GRADES)
    passed = n - fail - absent
    puanli = {g: c for g, c in counts.items()
              if g in GRADE_POINTS and g not in PASS_FAIL_GRADES}
    n_puanli = sum(puanli.values())
    # Yalnız VF varsa (BL/BZ dersinde devamsızlar) harf ortalaması YOK;
    # "0.00" demek dersi herkesin kaldığı bir ders gibi gösterirdi.
    if not any(c for g, c in puanli.items() if g not in ABSENT_GRADES):
        n_puanli = 0
    ortalama = (round(sum(GRADE_POINTS[g] * c for g, c in puanli.items())
                      / n_puanli, 2) if n_puanli else None)
    pct = lambda x: (round(100.0 * x / n, 1) if n else None)  # noqa: E731
    return {"n": n, "passed": passed, "failed": fail, "absent": absent,
            "passRate": pct(passed), "failRate": pct(fail),
            "absentRate": pct(absent), "meanPoints": ortalama,
            "announced": announced,
            # Faz 85 — BL/BZ ile notlanan öğrenci sayısı (ortalamaya girmez).
            "passFail": sum(counts.get(g, 0) for g in PASS_FAIL_GRADES),
            "gap": (None if announced is None else announced - n)}


# ═══════════════════════════════════════════════════════════════════════
# ★★ FAZ 85 — TAHMİNİ ZORLUK (not dağılımından)
#
# Kullanıcı 24.09.2026: *"derslerin önceki dönemlerdeki not ortalaması ve
# dağılımına göre tahmini zorluk derecelendirilmesi yapabilir misin ve bunu
# kullanıcıya uygun bir şekilde sunar mısın"*.
#
# ★★★ FAZ 87 — İKİ ALT PUAN, 10 ÜZERİNDEN (kullanıcı 24.09.2026):
# *"zorluğu iki kısıma ayır yüksek not alma zorluğu ve geçme zorluğu bunları
# 10 üzerinden puanlandır sonra geçme zorluğunun %70i ile yüksek not alma
# zorluğunun %30unu toplayıp genel bir zorluk üret örnek olarak 2.5 ortalama
# 10 üzerinden 5 ediyor vfleri de geçme oranına say çünkü vizeden kalan
# kişiler finale giremediği için vf gözüküyor %85 geçme oranı da 10 üzerinden
# 5 gibi düşün mat 103 çok zor değil belki zor sayılabilir"*.
#
#   * **Geçme zorluğu** (0–10) — geçme oranından; **VF başarısızlık sayılır**
#     (vizeden kalan öğrenci finale giremediği için VF görünüyor).
#     %100 → 0 · %85 → 5 · %70 ve altı → 10 (doğrusal).
#   * **Yüksek not alma zorluğu** (0–10) — harf notu alanların ortalamasından
#     (VF'li öğrencinin harf notu yok, ortalamaya girmez).
#     4.00 → 0 · 2.50 → 5 · 1.00 ve altı → 10 (doğrusal).
#   * **Genel** = 0.7 × geçme + 0.3 × yüksek not. Çan eğrisiyle not verilen
#     ve herkesin geçtiği ders (GMI 214: %97.9 geçme, ortalama 2.18) düşük
#     ortalamasına rağmen kolay çıkıyor (2.3).
#   * **Kademe** genelden: 0–2 çok kolay · 2–4 kolay · 4–6 orta · 6–8.5 zor ·
#     8.5–10 çok zor. "Çok zor" bilerek dar: MAT 103 (8.3) zor, FIZ 102 (9.2)
#     çok zor — kullanıcının yargısı.
#
#   Faz 85–86'nın katalog yüzdeliği KALKTI: mutlak ölçek "10 üzerinden 5"
#   diye okunabiliyor, katalogdaki öbür derslere bağlı değil ve vitrinde de
#   gerçek katalogda da aynı sayıyı veriyor (sabit tablo gerekmiyor).
#
# ⚠️ Değişmeyen kararlar:
#   * **Tekrar/bütünleme sınıfı hariç.** Öğrencisi (VF dahil) en kalabalık
#     dönemin %25'inden az olan dönem havuza girmiyor (BLG 335 bahar: n=3).
#   * **BL/BZ dersi derecelenmiyor** — harf notu yok.
#   * **Az veri:** olağan dönemlerde < 20 öğrenci → derece YOK; < 60 →
#     derece var ama "az veri" diye işaretli.
#   * **Öneri puanına GİRMİYOR** (Faz 38 kuralı): gösteriyoruz, karar
#     öğrencinin. Notlar hocanın not verme eğilimini ve sınıfın yapısını da
#     yansıtır — metin bunu her yerde söylüyor.
ZORLUK_MIN_N = 20
ZORLUK_AZ_VERI = 60
ZORLUK_ASIL_PAY = 0.25
ZORLUK_ETIKET = {1: "çok kolay", 2: "kolay", 3: "orta", 4: "zor", 5: "çok zor"}
ZORLUK_AGIRLIK_GECME = 0.7
ZORLUK_AGIRLIK_NOT = 0.3
# Ölçek çapaları (kullanıcının verdiği): (değer → 0, değer → 5).
GECME_CAPA = (100.0, 85.0)            # geçme oranı %
NOT_CAPA = (4.0, 2.5)                 # harf notu ortalaması
# Kademe sınırları (genel puan, 10 üzerinden).
ZORLUK_BANTLARI = (2.0, 4.0, 6.0, 8.5)
_HARFLER = tuple(g for g in GRADES if g not in ABSENT_GRADES)       # AA … FF


def _on_uzerinden(deger: float, capa: tuple[float, float]) -> float:
    """Doğrusal: capa[0] → 0, capa[1] → 5; 0–10 arasına kırpılır."""
    sifir, bes = capa
    return round(max(0.0, min(10.0, 5.0 * (sifir - deger) / (sifir - bes))), 1)


def gecme_zorlugu(gecme_orani: float) -> float:
    return _on_uzerinden(gecme_orani, GECME_CAPA)


def not_zorlugu(ortalama: float) -> float:
    return _on_uzerinden(ortalama, NOT_CAPA)


def genel_zorluk(gecme: float, yuksek_not: float) -> float:
    return round(ZORLUK_AGIRLIK_GECME * gecme + ZORLUK_AGIRLIK_NOT * yuksek_not, 1)


def zorluk_kademesi(genel: float) -> int:
    return 1 + sum(1 for b in ZORLUK_BANTLARI if genel >= b)


def zorluk_ortalamasi(terms: dict[str, dict[str, int]]) -> dict | None:
    """Olağan dönemlerin sayıları. `terms`: {dönem: {not: n}}.

    `n` VF dahil öğrenci; `passRate` VF'yi başarısız sayar; `mean` yalnız harf
    notu alanlardan. Harf notu hiç yoksa (BL/BZ dersi ya da boş) `None`."""
    from .prereq import GRADE_POINTS

    boy = {t: sum(cs.get(g, 0) for g in GRADES) for t, cs in terms.items()}
    harfli = {t: sum(cs.get(g, 0) for g in _HARFLER) for t, cs in terms.items()}
    if not max(harfli.values(), default=0):
        return None
    en_cok = max(boy.values())
    asil = sorted((t for t, n in boy.items()
                   if n >= ZORLUK_ASIL_PAY * en_cok and harfli[t]), reverse=True)
    havuz = {g: sum(terms[t].get(g, 0) for t in asil) for g in GRADES}
    n_harf = sum(havuz[g] for g in _HARFLER)
    n = n_harf + havuz["VF"]
    ort = sum(GRADE_POINTS[g] * havuz[g] for g in _HARFLER) / n_harf
    return {"mean": round(ort, 2), "n": n,
            "passRate": round(100.0 * (n_harf - havuz["FF"]) / n, 1),
            "failRate": round(100.0 * havuz["FF"] / n, 1),
            "absentRate": round(100.0 * havuz["VF"] / n, 1),
            "terms": asil}


def _donemler(con: sqlite3.Connection, key: str) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for t, g, n in con.execute(
            "SELECT term, grade, students FROM grade_distribution WHERE course_key=?",
            (key,)):
        out.setdefault(t, {})[g] = n
    return out


def _imza(con: sqlite3.Connection) -> tuple:
    """Önbellek anahtarı: veritabanı dosyası + son satır. ⚠️ `id(con)` tek
    başına yetmez — kapanan bağlantının kimliği yeni bir bağlantıya (başka
    bir veritabanına) verilebiliyor. MAX(rowid) B-ağacının ucundan okunuyor
    (ucuz); yeni çekim satır eklediğinde değişiyor."""
    yol = next((r[2] for r in con.execute("PRAGMA database_list") if r[1] == "main"), "")
    return (id(con), yol,
            con.execute("SELECT MAX(rowid) FROM grade_distribution").fetchone()[0])


_ZORLUK_CACHE: dict = {}


def zorluk(con: sqlite3.Connection, code: str) -> dict | None:
    """Bir dersin tahmini zorluğu. Dağılımı hiç yoksa `None`; varsa ama
    derecelenemiyorsa `level=None` ve `reason`.

    Sonuç önbellekte: kalma riski haritayı ders başına yeniden kuruyor ve
    her kurulum aynı dersleri soruyor (tarayıcıda Pyodide'de pahalı)."""
    anahtar = (*_imza(con), code)
    if anahtar not in _ZORLUK_CACHE:
        if len(_ZORLUK_CACHE) > 5000:
            _ZORLUK_CACHE.clear()
        _ZORLUK_CACHE[anahtar] = _zorluk(con, code)
    return _ZORLUK_CACHE[anahtar]


def _zorluk(con: sqlite3.Connection, code: str) -> dict | None:
    key = lookup(con, code)
    if not key:
        return None
    terms = _donemler(con, key)
    if not terms:
        return None
    z = zorluk_ortalamasi(terms)
    if z is None:
        bl = any(cs.get(g) for cs in terms.values() for g in PASS_FAIL_GRADES)
        return {"level": None,
                "reason": ("Ders başarılı/başarısız (BL/BZ) ile notlanmaktadır; "
                           "harf notu ortalaması yoktur." if bl
                           else "Harf notu verisi bulunmamaktadır.")}
    temel = {**{k: z[k] for k in ("passRate", "mean", "n", "failRate", "absentRate", "terms")},
             "termLabels": [config.donem_adi(t) or t for t in z["terms"]]}
    if z["n"] < ZORLUK_MIN_N:
        return {**temel, "level": None,
                "reason": f"Olağan dönemlerde yalnızca {z['n']} öğrenci vardır; "
                          f"derecelendirme için en az {ZORLUK_MIN_N} gerekir."}
    gecme, yuksek = gecme_zorlugu(z["passRate"]), not_zorlugu(z["mean"])
    genel = genel_zorluk(gecme, yuksek)
    kademe = zorluk_kademesi(genel)
    return {**temel, "level": kademe, "label": ZORLUK_ETIKET[kademe],
            "score": genel, "passScore": gecme, "gradeScore": yuksek,
            "lowData": z["n"] < ZORLUK_AZ_VERI}
