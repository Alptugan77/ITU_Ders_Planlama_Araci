"""Yapılandırma. Mevzuat kuralları ve öğrenciye özgü seçimler koda gömülmez."""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parent
ROOT = PKG_DIR.parent.parent
DATA_DIR = Path(os.environ.get("ITUCAP_DATA", ROOT / "data"))
ARCHIVE_DIR = DATA_DIR / "raw_archive"
REF_DB = DATA_DIR / "reference.sqlite3"
USER_DB = DATA_DIR / "user.sqlite3"

OBS = "https://obs.itu.edu.tr"
ITU_HELPER_RAW = "https://raw.githubusercontent.com/itu-helper/data/main"

# --- WP1.1 çıktısı: doğrulanmış OBS uçları (bkz. docs/obs-endpoints.md) ------
EP = {
    "plan_programs": f"{OBS}/public/DersPlan/GetAkademikProgramByBirimIdAndPlanTipi",  # POST
    "plan_page": f"{OBS}/public/DersPlan",                                             # GET (fakülte listesi)
    "plan_list": f"{OBS}/public/DersPlan/DersPlanlariList",                            # GET
    "plan_detail": f"{OBS}/public/DersPlan/DersPlanDetay",                             # GET /{id}
    "pool_group": f"{OBS}/public/DersPlan/_DersGrupSearch",                            # GET ?grupId=
    "eq_page": f"{OBS}/public/GenelTanimlamalar/DersPlanDenklikleri",                  # GET
    "eq_plan_types": f"{OBS}/public/GenelTanimlamalar/GetPlanTipleriByProgramId",       # POST
    "eq_plans": f"{OBS}/public/GenelTanimlamalar/GetDersPlanlariByProgramIdAndPlanTipiId",
    "eq_branches": f"{OBS}/public/GenelTanimlamalar/GetDersBransKodlariByPlanId",       # POST
}

PLAN_TYPES = [
    "on-lisans", "lisans", "cap", "yandal", "muhendislik-tamamlama",
    "bilimsel-hazirlik", "yuksek-lisans", "tezsiz-yuksek-lisans",
    "yuksek-lisans-ikinci-ogretim", "doktora", "uolp",
]

# Kısa kodlar: kullanıcının elle yazacağı ve arayüzün üreteceği biçim.
DAY_CODES = {1: "PZT", 2: "SAL", 3: "ÇAR", 4: "PER", 5: "CUM",
             6: "CMT", 7: "PAZ"}

DAY_INDEX = {
    "pzt": 1, "sal": 2, "çar": 3, "car": 3, "per": 4,
    "cum": 5, "cmt": 6, "paz": 7,
    "monday": 1, "pazartesi": 1,
    "tuesday": 2, "salı": 2, "sali": 2,
    "wednesday": 3, "çarşamba": 3, "carsamba": 3,
    "thursday": 4, "perşembe": 4, "persembe": 4,
    "friday": 5, "cuma": 5,
    "saturday": 6, "cumartesi": 6,
    "sunday": 7, "pazar": 7,
}


SECOND_KINDS = {
    #  kind      rol         etiket      OBS plan tipi
    "cap":    ("CAP",    "ÇAP",    "cap"),
    "yandal": ("YANDAL", "Yandal", "yandal"),
    "yok":    ("",       "",       ""),
}


@dataclass
class Settings:
    anadal_program: str = "HTAE"
    cap_program: str = "BLG"
    term: str = ""
    anadal_plan_id: int | None = None
    cap_plan_id: int | None = None
    # ★ İkinci program ÇAP olmak zorunda değil. Yandal da aynı motorla
    # çalışıyor: ayrı plan, ayrı ilerleme, ayrı renk. Fark yalnız etikette
    # ve OBS'den hangi plan tipinin çekildiğinde.
    second_kind: str = "cap"                 # 'cap' | 'yandal' | 'yok'
    yandal_program: str = ""
    yandal_plan_id: int | None = None
    # ★ Kontenjan nöbetinin izleyeceği dersler (Faz 11). Boşsa planlarının
    # açık slotlarındaki dersler izlenir — dar liste daha az gürültü demek.
    watch_courses: list[str] = field(default_factory=list)
    # ★ Bulunduğun dönem (1..8). 'Dönemlik + alttan' kipi bunu kullanıyor.
    # 0 = otomatik çıkar (geçilmiş slotların en derin dönemi).
    donem: int = 0
    # ★ İKİNCİ ANADALA BAŞLADIĞIN yarıyıl (3 ya da 5) — bulunduğun değil.
    # Yönerge yarıyıl tabanını buna bağlıyor: 3'te başlayan her yarıyıl en az
    # 6, 5'te başlayan en az 9 kredi ikinci anadaldan almak zorunda.
    # 0 = beyan edilmedi → motor hiçbir taban İDDİA ETMEZ. Yanlış bir taban
    # iki yönde de zarar: uydurma bir kuralla "az aldın" demek, ya da gerçek
    # tabanı atlayıp ilişik kesilmesine götürmek.
    cap_baslangic_yariyili: int = 0
    # ★ Ders KONULAMAYACAK saatler — okul dışı işler (iş, antrenman, servis).
    # Biçim: "GÜN BAŞLANGIÇ-BİTİŞ etiket"  →  "PZT 12:30-14:30 iş"
    # Motor bunları "zaten dolu" sayıyor; çakışan şube hiç önerilmiyor.
    # Liste olarak tutuluyor çünkü `update_settings` liste yazabiliyor —
    # ayrı bir [[tablo]] biçimi yeni bir yazıcı gerektirirdi.
    mesgul: list[str] = field(default_factory=list)
    request_delay_s: float = 1.0
    # HTTP başlıkları ASCII olmak zorunda — Türkçe karakter KOYMA (httpx patlar).
    # Yine de güvenlik için http.ascii_header() ile temizleniyor.
    user_agent: str = "itucap/0.1 (kisisel ders planlama araci; github.com/itucap)"
    scrape_plan_types: list[str] = field(default_factory=lambda: ["lisans", "cap"])
    # ★ Şubelerin `Dersi Alabilen Programlar` listesinde arayacağımız kodlar.
    # Öğrenci bu kodların HERHANGİ BİRİYLE kayıt yapabiliyorsa ders alınabilir.
    # (Kullanıcı teyidi 20.08.2026: HTAE, BLG, BLGE.)
    program_codes: list[str] = field(default_factory=lambda: [])

    # ★ Yük birimi. İTÜ'nün kendi kredi sistemi varsayılan; AKTS ikincil olarak
    # her yerde gösterilir ama sınır bu birimden hesaplanır.
    unit: str = "kredi"                 # 'kredi' | 'akts'
    max_load: float = 35.0              # dönem üst sınırı, seçilen birimde

    @classmethod
    def load(cls, path: Path | None = None) -> "Settings":
        path = path or ROOT / "config" / "settings.toml"
        if not path.exists():
            return cls()
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
        merged: dict = {}
        for section in ("student", "scraper"):
            merged.update(raw.get(section, {}))
        known = {f for f in cls.__dataclass_fields__}
        obj = cls(**{k: v for k, v in merged.items() if k in known})
        if obj.second_kind not in SECOND_KINDS:
            obj.second_kind = "cap"
        if not obj.program_codes:       # beyan yoksa kendi kodlarına düş
            obj.program_codes = [c for c in (obj.anadal_program, obj.second_program) if c]
        # ★ İkinci program yandal ise OBS'den yandal planı çekilmeli; kullanıcı
        # scrape_plan_types'ı ayrıca güncellemek zorunda kalmasın.
        need = SECOND_KINDS[obj.second_kind][2]
        if need and need not in obj.scrape_plan_types:
            obj.scrape_plan_types = [*obj.scrape_plan_types, need]
        return obj

    # ------------------------------------------------------- ikinci program
    @property
    def second_role(self) -> str:
        """'CAP' | 'YANDAL' | '' — planlarda ve arayüzde kullanılan rol."""
        return SECOND_KINDS[self.second_kind][0]

    @property
    def second_label(self) -> str:
        """'ÇAP' | 'Yandal' | '' — insan tarafı."""
        return SECOND_KINDS[self.second_kind][1]

    @property
    def second_program(self) -> str:
        return {"cap": self.cap_program, "yandal": self.yandal_program}.get(
            self.second_kind, "") or ""

    @property
    def second_plan_id(self) -> int | None:
        return {"cap": self.cap_plan_id, "yandal": self.yandal_plan_id}.get(
            self.second_kind)

    @property
    def allowed_programs(self) -> set[str]:
        return {c.upper() for c in self.program_codes}

    @property
    def unit_label(self) -> str:
        return "kredi" if self.unit == "kredi" else "AKTS"


# ------------------------------------------------------- ayarları geri yazma
# ★ Arayüzden program/dönem seçilebiliyor; seçim `settings.toml`'a dönmeli.
# Dosyayı tomllib ile okuyup yeniden üretmek YORUMLARI SİLERDİ — o dosyadaki
# yorumlar projenin ölçüm notları (neden 2229, neden 35 kredi). O yüzden
# satır bazlı, yalnız bilinen anahtara dokunan bir yazıcı kullanıyoruz.

_EDITABLE = {
    "anadal_program", "anadal_plan_id", "second_kind",
    "cap_program", "cap_plan_id", "yandal_program", "yandal_plan_id",
    "donem", "term", "unit", "max_load", "program_codes", "watch_courses",
    "cap_baslangic_yariyili", "mesgul",
}


def _trailing_comment(line: str) -> str:
    """Satırın sonundaki yorumu döndürür ('' yoksa).

    Tırnak içindeki '#' yorum değildir: `user_agent = "a#b"` bozulmamalı.
    """
    quote = None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "#":
            return "  " + line[i:].strip()
    return ""


def _toml_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_toml_value(v) for v in value) + "]"
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def update_settings(values: dict, path: Path | None = None) -> Path:
    """`settings.toml` içindeki anahtarları yerinde günceller.

    Yalnız `_EDITABLE` listesindeki anahtarlar yazılır — arayüzden gelen
    rastgele bir alan yapılandırmaya sızamaz. Var olan anahtar satırı
    değiştirilir (yorumları ve sırayı bozmadan), olmayan `[student]` bloğunun
    sonuna eklenir.
    """
    path = path or ROOT / "config" / "settings.toml"
    unknown = set(values) - _EDITABLE
    if unknown:
        raise ValueError(f"düzenlenemez anahtar: {sorted(unknown)}")
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() \
        else ["[student]"]
    pending = dict(values)

    section = ""
    student_end = -1
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
            continue
        if section == "student":
            student_end = i
        if "=" not in stripped or stripped.startswith("#"):
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in pending and section in ("student", ""):
            # ★ Satır sonundaki yorumu KORU. O yorumlar projenin ölçüm notları
            # ('# 2229 = TUMMUH_BLG …'); anahtarı güncellemek onları silmemeli.
            lines[i] = f"{key} = {_toml_value(pending.pop(key))}" + _trailing_comment(line)

    if pending:
        block = [f"{k} = {_toml_value(v)}" for k, v in pending.items()]
        if student_end >= 0:
            lines[student_end + 1:student_end + 1] = block
        else:
            lines += ["", "[student]", *block]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
