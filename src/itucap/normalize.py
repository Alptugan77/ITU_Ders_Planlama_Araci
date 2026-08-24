"""WP1.3 — Normalizasyon yardımcıları.

Ham veride kategori adları tutarsız ("Seçime Bağlı Ders(MT)" / "Elective Course (MT)"
/ boşluksuz varyantlar). Burada tek bir kanonik forma indiriyoruz ama HAM ETİKETİ
asla atmıyoruz — denetim için `pool_label_raw` her zaman saklanır.
"""
from __future__ import annotations

import re
import unicodedata

from .config import DAY_CODES, DAY_INDEX

# --------------------------------------------------------------- kategoriler
CATEGORIES = {"MT", "ITB", "TB", "TM", "ENG", "GE", "ED", "SNT", "OTHER"}

# ★ Kategori kodu etikette DÖRT biçimde geçiyor (23.08.2026'da 1400 gerçek
# etiket üzerinde ölçüldü):
#
#     parantez içinde   "8.yy Elective Course (MT)"  ·  "(MT-Tasarım)"
#     sonda             "Seçime Bağlı Ders MT VI"    ·  "…Crse I-MT"
#     başta             "MT Seçim Dersi 2 (E)"
#     ayrıca            "English Course" → ENG (yedek kural)
#
# Sıra numarası roma ya da arap olabiliyor (I…X, 1…12) ve kategorinin parçası
# DEĞİL. Eski kalıp yalnız I–V'i tanıyordu; "MT VI" ve "MT 1" OTHER'a düşüyordu.
#
# ★★ BÜYÜK HARF ŞART — `re.IGNORECASE` YOK. Sebebi ölçüldü: "Intr. to Sci &
# Eng Comp." bir DERS ADI ve içindeki "Eng" kategori değil. Harf duyarsız
# arasaydık 48 slotu yanlışlıkla ENG diye etiketlerdik. Kategori kodları
# kaynakta her zaman büyük harf; ders adlarındaki İngilizce kelimeler değil.
_CAT = "MT|ITB|TB|TM|ENG|GE|ED|SNT"
_ROMAN = r"(?:I{1,3}|IV|VI{0,3}|IX|X)"
_ORDINAL = rf"(?:\s+(?:{_ROMAN}|\d{{1,2}}))?"
_CAT_PAREN_RE = re.compile(rf"\(\s*({_CAT})(?:{_ORDINAL}|\s*-\s*[^)]*)?\s*\)")
_CAT_TAIL_RE = re.compile(rf"(?:^|[\s(/-])({_CAT}){_ORDINAL}\s*(?:\([^)]*\))?\s*$")
_CAT_HEAD_RE = re.compile(rf"^({_CAT})\s+\S")
# Etikette kategoriye BENZEYEN bir belirteç var mı? (gerçek boşluk ile
# "kaynakta kategori yok"u ayırmak için — bkz. `uncategorised_labels`)
_CAT_ANY_RE = re.compile(rf"(?:^|[\s(/-])({_CAT})(?:[\s)/-]|$)")

_TERM_RE = re.compile(r"(\d{1,2})\s*\.?\s*(?:yy|yarıyıl|yariyil)", re.IGNORECASE)
_TERM_EN_RE = re.compile(r"(\d{1,2})\s*(?:st|nd|rd|th)?\s*Semester", re.IGNORECASE)
_ENGLISH_RE = re.compile(r"English\s+Course", re.IGNORECASE)

# ★ İKİ AYRI LİSTE, çünkü iki ayrı şey:
#   unmatched_labels     — kategori BENZERİ bir kod var ama yerleştiremedik.
#                          Bu BİZİM eksiğimiz, düzeltilebilir.
#   uncategorised_labels — kaynakta kategori YOK ("Stüdyo IV", "Temel Meslek II").
#                          Düzeltilecek bir şey yok; kategori uydurmak veri
#                          uydurmak olurdu.
# Tek liste tutmak, düzeltilebilir 66 etiketi düzeltilemez 226'nın içinde
# görünmez kılıyordu.
unmatched_labels: list[str] = []
uncategorised_labels: list[str] = []


def label_category(label: str) -> str | None:
    """Etiketten kategori kodu — bulunamazsa None."""
    for rx in (_CAT_PAREN_RE, _CAT_TAIL_RE, _CAT_HEAD_RE):
        m = rx.search(label)
        if m:
            return m.group(1)
    return "ENG" if _ENGLISH_RE.search(label) else None


def normalize_pool_label(raw: str) -> tuple[str, int | None]:
    """('7.yy Seçime Bağlı Ders(MT)') -> ('MT', 7). Eşleşmezse ('OTHER', None)."""
    if not raw:
        return "OTHER", None
    label = raw.strip()
    category = label_category(label)
    term = None
    for rx in (_TERM_RE, _TERM_EN_RE):
        t = rx.search(label)
        if t:
            term = int(t.group(1))
            break
    if category is None:
        category = "OTHER"
        (unmatched_labels if _CAT_ANY_RE.search(label)
         else uncategorised_labels).append(label)
    return category, term


# ------------------------------------------------------------- kredi aralığı
# ★ 23.08.2026: havuz slotlarının kredisi TEK SAYI OLMAYABİLİYOR —
# "2 / 2,5 / 3" gibi bir ARALIK, çünkü havuzdan hangi dersi seçtiğine bağlı.
# `float()` bunu çözemiyordu ve kredi sessizce NULL kalıyordu: katalogdaki
# 4923 havuz slotunun kredisi yoktu ve planların toplamı sayfadakinden düşük
# çıkıyordu (65 planda "kredi tutmuyor" uyarısı).
#
# ⚠️ Aralıktan TEK BİR SAYI SEÇMİYORUZ. Ortalama ya da en küçüğü almak,
# kaynakta olmayan bir sayı uydurmak olurdu — ve o sayı kredi tavanına,
# yarıyıl tabanına, ilerleme yüzdesine akardı. Aralık aralık olarak duruyor.
_NUM_RE = re.compile(r"\d+(?:[.,]\d+)?")


def parse_credit_range(raw: str) -> tuple[float | None, float | None]:
    """'2 / 2,5 / 3' -> (2.0, 3.0) · '3' -> (3.0, 3.0) · '' -> (None, None)."""
    sayilar = [float(x.replace(",", ".")) for x in _NUM_RE.findall(raw or "")]
    return (min(sayilar), max(sayilar)) if sayilar else (None, None)


# ------------------------------------------------------------------ zamanlar
def hhmm_to_min(value: str) -> int | None:
    value = value.strip()
    m = re.fullmatch(r"(\d{1,2})[:.](\d{2})", value)
    if not m:
        return None
    return int(m.group(1)) * 60 + int(m.group(2))


def parse_time_range(value: str) -> tuple[int, int] | None:
    """'11:30/13:29' -> (690, 809). Bozuk/boş girdide None."""
    if not value or "/" not in value:
        return None
    a, _, b = value.partition("/")
    start, end = hhmm_to_min(a), hhmm_to_min(b)
    if start is None or end is None:
        return None
    return start, end


def day_to_index(value: str) -> int | None:
    key = strip_accents(value.strip().lower())
    for name, idx in DAY_INDEX.items():
        if strip_accents(name) == key:
            return idx
    return None


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


# -------------------------------------------------------------- ders kodları
_CODE_RE = re.compile(r"^([A-ZÇĞİÖŞÜ]{2,4})\s*(\d{3,4}[A-Z]*)$")


def normalize_course_code(raw: str) -> str:
    """'MAT103E' / 'MAT  103E' -> 'MAT 103E'. Tanınmazsa sıkıştırılmış hali döner."""
    s = re.sub(r"\s+", " ", (raw or "").strip().upper())
    if not s:
        return ""
    m = _CODE_RE.match(s.replace(" ", "")) or _CODE_RE.match(s)
    if m:
        return f"{m.group(1)} {m.group(2)}"
    m2 = re.match(r"^([A-ZÇĞİÖŞÜ]{2,4})(\d{3,4}[A-Z]*)$", s.replace(" ", ""))
    if m2:
        return f"{m2.group(1)} {m2.group(2)}"
    return s


_CODE_ONLY_RE = re.compile(r"^[A-ZÇĞİÖŞÜ]{2,4} \d{3,4}[A-Z]*$")
_SPLIT_RE = re.compile(r"[\n\r|/,;]+")


def course_codes_in(cell_text: str) -> list[str]:
    """Bir hücredeki BÜTÜN ders kodları — sıra korunur, tekrar atılır.

    ★ 22.08.2026: OBS'nin yeni plan sayfalarında Türkçe ve İngilizce kod AYNI
    hücrede duruyor:  ``EEF 110<br>EEF 110E<br>``. Bunlar aynı dersin iki dili;
    öğrenci hangisini alırsa slot dolar.

    ⚠️ AYIRICI ÖNEMLİ. `Node.text(strip=True)` bunları BİTİŞİK veriyor
    ("EEF 110EEF 110E") ve o metinden kod çıkarmaya çalışmak sessizce YANLIŞ
    kod üretir ("EEF 110EE" gibi). Bu yüzden çağıran taraf hücreyi
    `text(separator="\\n")` ile okumak ZORUNDA; burada da yalnız ayırıcıyla
    bölünmüş parçalara bakıyoruz, ham metinde kod ARAMIYORUZ.
    """
    out: list[str] = []
    for part in _SPLIT_RE.split(cell_text or ""):
        code = normalize_course_code(part)
        if _CODE_ONLY_RE.match(code) and code not in out:
            out.append(code)
    return out


def base_program_code(code: str) -> str:
    """'BLGE' -> 'BLG'. Programın dil varyantını kanonik koda indirger.

    İTÜ'de aynı bölümün Türkçe ve İngilizce programı ayrı kodla duruyor
    (BLG / BLGE). ÇAP–yandal seçiminde bu ayrım YOK: ÇAP planı bölüme
    tanımlı, dile değil. İkisini ayrı program gibi listelemek kullanıcıya
    olmayan bir seçim yaptırıyordu.
    """
    code = (code or "").strip().upper()
    return code[:-1] if len(code) > 2 and code.endswith("E") else code


def merge_language_variants(codes) -> list[str]:
    """Dil varyantlarını tekleştirir: {'BLG','BLGE','HTAE'} -> ['BLG','HTAE'].

    ⚠️ Yalnız İKİSİ DE varsa birleştiriyoruz. 'HTAE'nin 'HTA' diye bir eşi
    yok; körlemesine son harfi atmak var olmayan bir programa yönlendirirdi.
    """
    codes = {str(c).strip().upper() for c in codes if c}
    return sorted(c for c in codes
                  if not (c.endswith("E") and base_program_code(c) in codes))


def obs_code_to_program(obs_code: str) -> str:
    """'HTAE_LS' -> 'HTAE', 'EHB_MTM_LS' -> 'EHB_MTM'."""
    code = (obs_code or "").strip().upper()
    for suffix in ("_LS", "_OL", "_YL", "_DR"):
        if code.endswith(suffix):
            return code[: -len(suffix)]
    return code


def split_cap_plan_code(obs_program_code: str) -> tuple[str | None, str | None]:
    """ÇAP plan başlığındaki 'TUMMUH_BLG' -> ('TUMMUH', 'BLG').

    ★ Faz 1 keşfi: ÇAP planları (anadal, çap) ÇİFTİNE göre tanımlıdır.
    'TUMMUH' = tüm mühendislik programları için ortak plan.
    """
    code = (obs_program_code or "").strip().upper()
    if "_" not in code:
        return None, code or None
    host, _, target = code.rpartition("_")
    return host or None, target or None


# --------------------------------------------------- meşgul saat beyanı
# "PZT 12:30-14:30 iş" gibi tek satırlık bir aralık.
#
# ★ Neden metin? `settings.toml`'a liste olarak yazılabilsin diye. Yorum
# koruyan satır bazlı yazıcımız (`config.update_settings`) skaler ve liste
# yazabiliyor; `[[tablo]]` yazamıyor. Kullanıcı dosyayı elle de açıp
# okuyabilsin istedik — "PZT 12:30-14:30 iş" bir insanın yazabileceği şey.
_MESGUL_RE = re.compile(
    r"^\s*(?P<gun>[A-Za-zÇĞİÖŞÜçğıöşü]+|[1-7])\s+"
    r"(?P<bas>\d{1,2}[:.]\d{2})\s*[-–]\s*(?P<bit>\d{1,2}[:.]\d{2})"
    r"(?:\s+(?P<ad>.+?))?\s*$")


def parse_busy(raw: str) -> dict | None:
    """'PZT 12:30-14:30 iş' → {'day':1,'start':750,'end':870,'label':'iş'}

    Geçersizse `None` — sessizce atlanır, çünkü bu bir KISIT beyanı ve
    anlaşılmayan bir kısıtı tahmin etmek yanlış ders elemeye yol açardı.
    """
    m = _MESGUL_RE.match(raw or "")
    if not m:
        return None
    day = day_to_index(m.group("gun"))
    if day is None:
        try:
            day = int(m.group("gun"))
        except ValueError:
            return None
    if not 1 <= day <= 7:
        return None
    start = hhmm_to_min(m.group("bas").replace(".", ":"))
    end = hhmm_to_min(m.group("bit").replace(".", ":"))
    if start is None or end is None or end <= start:
        return None
    return {"day": day, "start": start, "end": end,
            "label": (m.group("ad") or "").strip() or "meşgul"}


def format_busy(day: int, start: int, end: int, label: str = "") -> str:
    """Yapıdan metne — arayüzden gelen seçimi dosyaya yazarken."""
    ad = " " + label.strip() if label and label.strip() else ""
    return (f"{DAY_CODES.get(day, str(day))} "
            f"{start // 60:02d}:{start % 60:02d}-"
            f"{end // 60:02d}:{end % 60:02d}{ad}")
