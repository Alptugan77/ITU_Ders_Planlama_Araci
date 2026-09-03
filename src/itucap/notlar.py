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
FAIL_GRADES = ("FF",)
ABSENT_GRADES = ("VF",)

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
    return [out[b] for b in BUCKET_ORDER]

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

    ⚠️ Kodu biz TÜRETMİYORUZ. Sondaki `E`'yi atarak eş bulmak bu depoda
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
    puanli = {g: c for g, c in counts.items() if g in GRADE_POINTS}
    n_puanli = sum(puanli.values())
    ortalama = (round(sum(GRADE_POINTS[g] * c for g, c in puanli.items())
                      / n_puanli, 2) if n_puanli else None)
    pct = lambda x: (round(100.0 * x / n, 1) if n else None)  # noqa: E731
    return {"n": n, "passed": passed, "failed": fail, "absent": absent,
            "passRate": pct(passed), "failRate": pct(fail),
            "absentRate": pct(absent), "meanPoints": ortalama,
            "announced": announced,
            "gap": (None if announced is None else announced - n)}
