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
# ★★ FAZ 85 — TAHMİNİ ZORLUK (not ortalamasından)
#
# Kullanıcı 24.09.2026: *"derslerin önceki dönemlerdeki not ortalaması ve
# dağılımına göre tahmini zorluk derecelendirilmesi yapabilir misin ve bunu
# kullanıcıya uygun bir şekilde sunar mısın"*.
#
# Ölçüt: dersin **olağan dönemlerindeki** harf notlarından iki sayı —
# **geçme oranı** (ağırlık %70) ve **not ortalaması** (%30). İkisi de
# katalogdaki öbür derslere göre yüzdeliğe çevrilip birleştiriliyor; beş
# kademe = birleşik puanın beşte birlik dilimleri.
#
# ★★ Faz 86 — GEÇME ORANI ÖNDE (kullanıcı 24.09.2026): *"zorluk düzeyi
# hesaplamasında geçilme yüzdesini geçilme notunun üstüne koyar mısın bazen
# çan dağılımı yüzünden kolay dersler orta zorlukta veya zor diye
# anlaşılabilir"*. Faz 85 yalnız ortalamaya bakıyordu. Bağıl (çan)
# değerlendirmede ortalama hocanın dağıtımıyla belirlenir; sınıfın çoğu
# geçse de ortalama düşük kalır. Ölçüldü (gerçek katalog, 2025-2026):
# ortalaması < 2.40 ama FF oranı < %4 olan 21 ders vardı ve hepsi "zor" ya da
# "çok zor" çıkıyordu — GMI 214: ortalama 2.18, FF %1.1, n=95 → "çok zor".
# Öğrencinin asıl sorusu "bu dersten kalır mıyım"; ortalama ikincil.
#
# ⚠️ Kararlar ve gerekçeleri:
#   * **VF hariç.** Devamsızlık dersin zorluğu hakkında bir şey söylemez
#     (bkz. modül başlığı). GNO ölçeğindeki `meanPoints` VF'yi 0 sayar; bu
#     ölçü saymaz. İkisi ayrı sorulara cevap.
#   * **Tekrar/bütünleme sınıfı hariç.** Bir dönemin öğrencisi en kalabalık
#     dönemin %25'inden azsa o dönem havuza girmiyor (BLG 335 bahar: n=3,
#     hepsi DD/FF — dersi anlatmıyor).
#   * **BL/BZ dersi derecelenmiyor** — harf notu yok.
#   * **Az veri:** olağan dönemlerde < 20 harf notu → derece YOK;
#     < 60 → derece var ama "az veri" diye işaretli.
#   * **Öneri puanına GİRMİYOR** (Faz 38 kuralı): gösteriyoruz, karar
#     öğrencinin. Ortalama, zorluğun yanında hocanın not verme eğilimini ve
#     sınıfın yapısını da yansıtır — metin bunu her yerde söylüyor.
ZORLUK_MIN_N = 20
ZORLUK_AZ_VERI = 60
ZORLUK_ASIL_PAY = 0.25
ZORLUK_ETIKET = {1: "çok kolay", 2: "kolay", 3: "orta", 4: "zor", 5: "çok zor"}
ZORLUK_AGIRLIK_GECME = 0.7
ZORLUK_AGIRLIK_ORT = 0.3
# Canlı karşılaştırma için katalogda en az bu kadar derecelenebilir ders
# olmalı; yoksa (kısmi çekim, vitrin) yüzdelik anlamsız — aşağıdaki SABİT
# tablolara düşülüyor.
ZORLUK_CANLI_MIN = 300
# Sabit tablolar: gerçek katalogda (2025-2026, OBS; 24.09.2026, derecelenebilen
# 1187 ders) aynı yöntemle ölçülen %0, %5, …, %100 yüzdelik noktaları.
# `tools/zorluk_olcegi.py` yeniden üretir.
ZORLUK_SABIT = {
    "ff": (0.0, 0.0, 0.0, 0.0, 0.0, 1.4, 2.0, 2.7, 3.3, 3.9, 4.6, 5.4, 6.5, 7.6,
           8.8, 10.0, 12.0, 14.3, 18.2, 24.0, 68.0),
    "ort": (0.88, 1.83, 2.01, 2.14, 2.28, 2.36, 2.43, 2.52, 2.59, 2.68, 2.78,
            2.85, 2.94, 3.02, 3.15, 3.27, 3.42, 3.53, 3.66, 3.81, 4.0),
    "skor": (0.071, 0.096, 0.134, 0.174, 0.219, 0.269, 0.313, 0.357, 0.398,
             0.442, 0.483, 0.539, 0.58, 0.619, 0.674, 0.734, 0.781, 0.831, 0.88,
             0.941, 1.0),
}
_HARFLER = tuple(g for g in GRADES if g not in ABSENT_GRADES)       # AA … FF


def zorluk_ortalamasi(terms: dict[str, dict[str, int]]) -> dict | None:
    """Olağan dönemlerin VF'siz harf ortalaması. `terms`: {dönem: {not: n}}.

    Harf notu hiç yoksa (BL/BZ dersi ya da boş) `None`."""
    from .prereq import GRADE_POINTS

    harfli = {t: sum(cs.get(g, 0) for g in _HARFLER) for t, cs in terms.items()}
    en_cok = max(harfli.values(), default=0)
    if not en_cok:
        return None
    asil = sorted((t for t, n in harfli.items() if n >= ZORLUK_ASIL_PAY * en_cok),
                  reverse=True)
    havuz = {g: sum(terms[t].get(g, 0) for t in asil) for g in _HARFLER}
    n = sum(havuz.values())
    ort = sum(GRADE_POINTS[g] * c for g, c in havuz.items()) / n
    return {"mean": round(ort, 2), "n": n, "failRate": round(100.0 * havuz["FF"] / n, 1),
            "terms": asil}


def _donemler(con: sqlite3.Connection, key: str) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for t, g, n in con.execute(
            "SELECT term, grade, students FROM grade_distribution WHERE course_key=?",
            (key,)):
        out.setdefault(t, {})[g] = n
    return out


_OLCEK_CACHE: dict = {}


def _imza(con: sqlite3.Connection) -> tuple:
    """Önbellek anahtarı: veritabanı dosyası + son satır. ⚠️ `id(con)` tek
    başına yetmez — kapanan bağlantının kimliği yeni bir bağlantıya (başka
    bir veritabanına) verilebiliyor. MAX(rowid) B-ağacının ucundan okunuyor
    (ucuz); yeni çekim satır eklediğinde değişiyor."""
    yol = next((r[2] for r in con.execute("PRAGMA database_list") if r[1] == "main"), "")
    return (id(con), yol,
            con.execute("SELECT MAX(rowid) FROM grade_distribution").fetchone()[0])


@dataclass(frozen=True)
class ZorlukOlcegi:
    """Karşılaştırma tabanı. `kaynak="katalog"`: listeler katalogdaki BÜTÜN
    derecelenebilen derslerin değerleri (sıralı). `kaynak="sabit"`: listeler
    21 noktalık yüzdelik tabloları."""
    ff: tuple
    ort: tuple
    skor: tuple
    kaynak: str
    n: int = 0


def _pay(tablo: tuple, x: float, kaynak: str) -> float:
    """`x`ten KÜÇÜK değerlerin payı (0–1), eşitlerin yarısıyla (orta sıra).

    ⚠️ Eşitler önemli: derslerin %20'sinde FF oranı 0 — orta sıra olmasa
    hepsi "en kolay" uca yığılırdı."""
    import bisect
    if not tablo:
        return 0.5
    alt = bisect.bisect_left(tablo, x)
    ust = bisect.bisect_right(tablo, x)
    if kaynak == "katalog":
        return (alt + (ust - alt) / 2) / len(tablo)
    # Yüzdelik tablosu: nokta k, %5·k'ya karşılık geliyor.
    adim = 1 / (len(tablo) - 1)
    if ust > alt:                                   # tabloda eşit nokta(lar)
        return ((alt + ust - 1) / 2) * adim
    if alt == 0:
        return 0.0
    if alt >= len(tablo):
        return 1.0
    a, b = tablo[alt - 1], tablo[alt]
    return ((alt - 1) + (x - a) / (b - a)) * adim


def zorluk_skoru(ff: float, ort: float, olcek: ZorlukOlcegi) -> tuple[float, float, float]:
    """(birleşik zorluk 0–1, FF yüzdeliği, ortalama yüzdeliği).

    FF oranı YÜKSEK ve ortalama DÜŞÜK oldukça zorluk artıyor."""
    p_ff = _pay(olcek.ff, ff, olcek.kaynak)
    p_ort = _pay(olcek.ort, ort, olcek.kaynak)
    return (ZORLUK_AGIRLIK_GECME * p_ff + ZORLUK_AGIRLIK_ORT * (1 - p_ort),
            p_ff, p_ort)


def _yuzdelikler(degerler: list[float]) -> tuple:
    d = sorted(degerler)
    return tuple(d[min(len(d) - 1, round(k * (len(d) - 1) / 20))] for k in range(21))


def zorluk_olcegi(con: sqlite3.Connection) -> ZorlukOlcegi:
    """Katalogda derecelenebilen (n ≥ ZORLUK_MIN_N) derslerin FF oranları,
    ortalamaları ve birleşik puanları. Yeterli ders yoksa sabit tablolar.
    Veri değişmedikçe bir kez hesaplanıyor (tarayıcıda her durum
    değişikliğinde 39 bin satırı yeniden okumamak için)."""
    anahtar = _imza(con)
    if anahtar in _OLCEK_CACHE:
        return _OLCEK_CACHE[anahtar]
    hepsi: dict[str, dict[str, dict[str, int]]] = {}
    for k, t, g, n in con.execute(
            "SELECT course_key, term, grade, students FROM grade_distribution"):
        hepsi.setdefault(k, {}).setdefault(t, {})[g] = n
    ciftler = []
    for terms in hepsi.values():
        z = zorluk_ortalamasi(terms)
        if z and z["n"] >= ZORLUK_MIN_N:
            ciftler.append((z["failRate"], z["mean"]))
    if len(ciftler) >= ZORLUK_CANLI_MIN:
        taban = ZorlukOlcegi(tuple(sorted(f for f, _ in ciftler)),
                             tuple(sorted(o for _, o in ciftler)), (), "katalog")
        skor = tuple(sorted(zorluk_skoru(f, o, taban)[0] for f, o in ciftler))
        olcek = ZorlukOlcegi(taban.ff, taban.ort, skor, "katalog", len(ciftler))
    else:
        olcek = SABIT_OLCEK
    _OLCEK_CACHE.clear()
    _OLCEK_CACHE[anahtar] = olcek
    return olcek


def zorluk_kademesi(ff: float, ort: float, olcek: ZorlukOlcegi) -> dict:
    """Kademe 1–5 ve açıklamada kullanılan paylar (%)."""
    skor, p_ff, p_ort = zorluk_skoru(ff, ort, olcek)
    p = _pay(olcek.skor, skor, olcek.kaynak)
    kademe = 1 + min(4, int(p * 5))
    canli = olcek.kaynak == "katalog"
    return {"level": kademe, "scale": olcek.kaynak,
            "catalog": olcek.n if canli else None,
            # Geçme oranı bundan DÜŞÜK olan derslerin payı = FF'si yüksek olanlar.
            "passLowerShare": round(100 * (1 - p_ff)) if canli else None,
            "meanLowerShare": round(100 * p_ort) if canli else None}


_ZORLUK_CACHE: dict = {}


def zorluk(con: sqlite3.Connection, code: str,
           olcek: ZorlukOlcegi | None = None) -> dict | None:
    """Bir dersin tahmini zorluğu. Dağılımı hiç yoksa `None`; varsa ama
    derecelenemiyorsa `level=None` ve `reason`.

    Sonuç önbellekte: kalma riski haritayı ders başına yeniden kuruyor ve
    her kurulum aynı dersleri soruyor (tarayıcıda Pyodide'de pahalı)."""
    olcek = zorluk_olcegi(con) if olcek is None else olcek
    anahtar = (*_imza(con), code, olcek.kaynak, olcek.n)
    if anahtar not in _ZORLUK_CACHE:
        if len(_ZORLUK_CACHE) > 5000:
            _ZORLUK_CACHE.clear()
        _ZORLUK_CACHE[anahtar] = _zorluk(con, code, olcek)
    return _ZORLUK_CACHE[anahtar]


def _zorluk(con: sqlite3.Connection, code: str, olcek: ZorlukOlcegi) -> dict | None:
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
    donem_adi = [config.donem_adi(t) or t for t in z["terms"]]
    temel = {"passRate": round(100.0 - z["failRate"], 1),
             "mean": z["mean"], "n": z["n"], "failRate": z["failRate"],
             "terms": z["terms"], "termLabels": donem_adi}
    if z["n"] < ZORLUK_MIN_N:
        return {**temel, "level": None,
                "reason": f"Olağan dönemlerde yalnızca {z['n']} harf notu vardır; "
                          f"derecelendirme için en az {ZORLUK_MIN_N} gerekir."}
    k = zorluk_kademesi(z["failRate"], z["mean"], olcek)
    return {**temel, **k, "label": ZORLUK_ETIKET[k["level"]],
            "lowData": z["n"] < ZORLUK_AZ_VERI}


SABIT_OLCEK = ZorlukOlcegi(ZORLUK_SABIT["ff"], ZORLUK_SABIT["ort"],
                           ZORLUK_SABIT["skor"], "sabit")
