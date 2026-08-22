"""WP1.3 — Normalizasyon yardımcıları.

Ham veride kategori adları tutarsız ("Seçime Bağlı Ders(MT)" / "Elective Course (MT)"
/ boşluksuz varyantlar). Burada tek bir kanonik forma indiriyoruz ama HAM ETİKETİ
asla atmıyoruz — denetim için `pool_label_raw` her zaman saklanır.
"""
from __future__ import annotations

import re
import unicodedata

from .config import DAY_INDEX

# --------------------------------------------------------------- kategoriler
CATEGORIES = {"MT", "ITB", "TB", "TM", "ENG", "GE", "ED", "SNT", "OTHER"}

# Kategori parantez içinde olabilir ("(MT)", "(MT I)", "( ITB )") ya da hiç parantez
# olmadan serbest metinde geçebilir ("Seçime Bağlı Ders MT II"). Roma rakamı sıra
# numarasıdır (I/II/III), kategorinin parçası değildir.
_ROMAN = r"(?:\s+(?:I{1,3}|IV|V))?"
_CAT_PAREN_RE = re.compile(rf"\(\s*(MT|ITB|TB|TM|ENG|GE|ED|SNT){_ROMAN}\s*\)", re.IGNORECASE)
_CAT_BARE_RE = re.compile(rf"\b(MT|ITB|TB|TM|ENG|GE|ED|SNT){_ROMAN}\s*$", re.IGNORECASE)
_TERM_RE = re.compile(r"(\d{1,2})\s*\.?\s*(?:yy|yarıyıl|yariyil)", re.IGNORECASE)
_TERM_EN_RE = re.compile(r"(\d{1,2})\s*(?:st|nd|rd|th)?\s*Semester", re.IGNORECASE)
_ENGLISH_RE = re.compile(r"English\s+Course", re.IGNORECASE)

unmatched_labels: list[str] = []  # sessizce yutma: pipeline sonunda raporlanır


def normalize_pool_label(raw: str) -> tuple[str, int | None]:
    """('7.yy Seçime Bağlı Ders(MT)') -> ('MT', 7). Eşleşmezse ('OTHER', None)."""
    if not raw:
        return "OTHER", None
    label = raw.strip()
    m = _CAT_PAREN_RE.search(label) or _CAT_BARE_RE.search(label)
    category = m.group(1).upper() if m else None
    if category is None and _ENGLISH_RE.search(label):
        category = "ENG"
    term = None
    for rx in (_TERM_RE, _TERM_EN_RE):
        t = rx.search(label)
        if t:
            term = int(t.group(1))
            break
    if category is None:
        category = "OTHER"
        unmatched_labels.append(label)
    return category, term


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
