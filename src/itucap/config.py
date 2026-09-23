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


# ⚠️ TEKİL türlerin tablosu. "ikisi" burada YOK ve olmamalı: "ikisi"nin tek
# bir rolü, tek bir etiketi, tek bir OBS plan tipi yok. Seçilebilir değerler
# `SECOND_CHOICES`'ta; doğrulama ORAYA bakmalı.
#
# ★★ Hata bildirimi 24.08.2026: "yandal ve çap planını aynı anda yapmaya
# çalışınca program türü geçersiz diyor". Sebebi tam olarak buydu —
# `server.save_programs` doğrulamayı bu sözlükle yapıyordu. Aynı karışıklık
# `pipeline` ve `verify` içinde `SECOND_KINDS[second_kind]` biçiminde
# KeyError olarak da duruyordu; `plan_type_of()` onları da kapatıyor.
SECOND_KINDS = {
    #  kind      rol         etiket      OBS plan tipi
    "cap":    ("CAP",    "ÇAP",    "cap"),
    "yandal": ("YANDAL", "Yandal", "yandal"),
    "yok":    ("",       "",       ""),
}

# ★ İkinci program SEÇİMİ — ÇAP ve yandal AYNI ANDA alınabiliyor
# (kullanıcı teyidi 23.08.2026). Bu yüzden `second_kind` artık "hangi tür"
# değil "hangi türLER" sorusunun cevabı.
#
# Neden tek bir alan? `settings.toml` yazıcısı satır bazlı ve yorumları
# koruyor; skaler ve liste yazabiliyor ama `[[tablo]]` yazamıyor. Tek bir
# skaler seçim, iki ayrı bayrağın birbiriyle çelişme ihtimalini de ortadan
# kaldırıyor — bu projede tekrar tekrar canımızı yakan şey iki kaynağın
# aynı soruya farklı cevap vermesiydi.
SECOND_CHOICES: dict[str, tuple[str, ...]] = {
    "cap":    ("cap",),
    "yandal": ("yandal",),
    "ikisi":  ("cap", "yandal"),
    "yok":    (),
}


def plan_type_of(second_kind: str, fallback: str = "cap") -> str:
    """`second_kind` için OBS plan tipi — "ikisi" dahil, KeyError YOK.

    ★ `SECOND_KINDS[second_kind][2]` üç yerde doğrudan çağrılıyordu
    (`pipeline` iki kez, `verify` bir kez) ve `second_kind == "ikisi"`
    olduğunda hepsi KeyError veriyordu: ÇAP+yandal seçen kullanıcıda
    `make refresh`, `make verify` ve `make programs` çöküyordu.

    ⚠️ "ikisi"nde TEK bir plan tipi yok; ilkini döndürüyoruz ve çağıranların
    hepsi zaten tek tip isteyen yerler (tarama komutu, doğrulama raporu).
    Doğru cevabı isteyen yer `settings.seconds` üzerinden dönmeli.
    """
    turler = SECOND_CHOICES.get(second_kind, ())
    if not turler:
        return fallback
    return SECOND_KINDS[turler[0]][2] or fallback


# OBS dönem kodunun son iki hanesi.
_YARIYIL = {"10": "Güz", "20": "Bahar", "30": "Yaz"}


def term_year(kod: str) -> int | None:
    """`'202610'` → `2026`. Akademik yılın **BİTİŞ** yılı. Çözemezse None."""
    k = str(kod or "").strip()
    if len(k) != 6 or not k.isdigit() or k[4:] not in _YARIYIL:
        return None
    return int(k[:4])


def donem_adi(kod: str) -> str:
    """`202610` → `2025-2026 Güz`. Çözemezse BOŞ döner.

    ★ İlk kullanıcı incelemesi B3: başlıkta ham `202610` yazıyordu. Bu kod
    OBS'nin iç gösterimi; öğrencinin gördüğü hiçbir yerde böyle yazmıyor.

    ★★ FAZ 38 — BİR YIL KAYMASI DÜZELTİLDİ (02.09.2026).
    Buradaki eski yorum *"`202610` kodlu şubeler 23.08.2026'da çekildi — yani
    2026-2027 Güz"* diyordu ve kod `f"{yil}-{yil+1}"` üretiyordu. Yani
    `202610` → "2026-2027 Güz".

    OBS'nin **kendi** not dağılımı ucu bunu yalanlıyor:

        yil=2026 → 202610 | 2025-2026 | Fall Semester   (n=2988, MAT 103E)
                   202620 | 2025-2026 | Spring Semester
                   202630 | 2025-2026 | Summer Semester (n=991)

    Üç ardışık yılda tutarlı. Mantık da doğruluyor: `202630` yazın notları
    Eylül 2026'da açıklanmış durumda; "2026-2027 yazı" olsaydı o yaz daha
    yaşanmamış olurdu. Yani koddaki yıl akademik yılın **BİTİŞ** yılı.

    ⚠️ Bu düzeltmenin bir sonucu var: `settings.toml`'da `term = "202610"`
    yazan kullanıcı **geçmiş bir dönemi** (2025-2026 Güz) planlıyor demektir.
    `settings.term_is_past()` bunu ayrıca uyarıyor — sessizce düzeltmiyoruz,
    çünkü hangi dönemi planladığı kullanıcının beyanı.

    ⚠️ Tanımadığı kalıba İSİM UYDURMUYOR. Boş dönüyor ve çağıran taraf ham
    kodu yazmaya devam ediyor — yanlış bir dönem adı yazmak, ham koddan
    çok daha kötü olurdu (öğrenci "bahar" sanıp yanlış döneme bakar).
    """
    k = str(kod or "").strip()
    if len(k) != 6 or not k.isdigit():
        return ""
    yil, yariyil = k[:4], k[4:]
    ad = _YARIYIL.get(yariyil)
    if not ad:
        return ""
    return f"{int(yil) - 1}-{yil} {ad}"


# Dosyadan OKUNMAYAN, yalnız yükleme sonucunu taşıyan alanlar.
_IC_ALANLAR = {"load_error", "load_uyarilari"}


def _yanlis_yerdekiler(raw: dict, known: set[str], merged: dict) -> list[dict]:
    """Okunan tabloların DIŞINDA duran ayar anahtarları (Faz 53).

    `[regulation]` gibi bir tablonun altına ya da ilk tablo başlığından
    ÖNCEYE yazılmış `donem`, `mesgul`, `cap_baslangic_yariyili`… TOML için
    geçerli, bizim için görünmez. `golge=True`: aynı anahtar `[student]`da
    da var — geçerli olan o, bu satır yalnız yanıltıcı bir kopya.
    """
    out = []
    for tablo, icerik in raw.items():
        if tablo in ("student", "scraper"):
            continue
        if isinstance(icerik, dict):
            anahtarlar = [k for k in icerik if k in known]
        elif tablo in known:
            # Tablo başlığından önce yazılmış düz anahtar (`donem = 5` en üstte).
            anahtarlar, tablo = [tablo], ""
        else:
            continue
        for k in anahtarlar:
            out.append({"anahtar": k, "tablo": tablo, "golge": k in merged})
    return out


@dataclass
class Settings:
    # ★★ VARSAYILAN BOŞ (23.08.2026). Eskiden "HTAE"/"BLG" yazıyordu —
    # geliştiricinin kendi bölümleri. `settings.toml` siteye girmiyor
    # (kişisel), yani YAYINLANAN SİTEYE İLK GİREN HERKES o iki programın
    # raporunu görüyordu: dolu bir haftalık program, "%0 tamamlandı,
    # 54 ders kaldı"… hiç seçmediği bir bölüm için.
    #
    # Boş varsayılan, aracın seçilmemiş bir şeyi seçilmiş gibi göstermesini
    # engelliyor; arayüz bu durumda rapor yerine KARŞILAMA ekranı açıyor.
    anadal_program: str = ""
    cap_program: str = ""
    term: str = ""
    anadal_plan_id: int | None = None
    cap_plan_id: int | None = None
    # ★ İkinci program ÇAP olmak zorunda değil. Yandal da aynı motorla
    # çalışıyor: ayrı plan, ayrı ilerleme, ayrı renk. Fark yalnız etikette
    # ve OBS'den hangi plan tipinin çekildiğinde.
    second_kind: str = "yok"                 # 'cap' | 'yandal' | 'yok'
    yandal_program: str = ""
    yandal_plan_id: int | None = None
    # ★ Kontenjan nöbetinin izleyeceği dersler (Faz 11). Boşsa planlarının
    # açık slotlarındaki dersler izlenir — dar liste daha az gürültü demek.
    watch_courses: list[str] = field(default_factory=list)
    # ★★ Faz 27 — YUMUŞAK TERCİHLER (yapılacaklar §2.2).
    #
    # Bunlar SERT KISIT DEĞİL, sıralama ağırlığı: "sabah dersi istemiyorum"u
    # eleme kuralı yapmak, gerçek veride kayıt edilebilir tek programı
    # imkânsız gösterebilirdi (14 ÇAP dersinden yalnız 2–3'ü bir dönemde
    # alınabiliyor). Tercih, iki ÇALIŞAN program arasında seçim yaptırır.
    #
    # `tercih_en_erken` dakika cinsinden (540 = 09:00); 0 = önemsiz.
    tercih_en_erken: int = 0
    tercih_bos_gunler: list[int] = field(default_factory=list)   # 1=Pzt … 5=Cum
    tercih_kampus_degisimi: bool = False        # True = istemiyorum
    tercih_cevrimici: bool = False              # True = çevrimiçi şubeyi yeğle
    tercih_istenen_hocalar: list[str] = field(default_factory=list)
    tercih_istenmeyen_hocalar: list[str] = field(default_factory=list)
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
    # ★★ SAATE KİLİT (Faz 45, kullanıcı isteği 17.09.2026: *"dersleri saate
    # kitleme ve önerilerin onun etrafında şekillenmesi"*).
    # Biçim: "DERS@CRN"  →  "GEO 315E@13601"
    # `watch_courses` "bu ders programda olsun" der ama ŞUBEYİ motora bırakır;
    # kilit "bu dersi TAM BU SAATTE tut" der. Motor kilitli dersin yalnız o
    # şubesini dener, kalan programı onun etrafında kurar.
    # ⚠️ CRN saklanıyor, saat değil — saat CRN'in bir özelliği. Dönem değişip
    # CRN kaybolursa kilit sessizce düşmemeli; arayüz "kilit tutmuyor" demeli.
    kilitli: list[str] = field(default_factory=list)
    request_delay_s: float = 1.0
    # HTTP başlıkları ASCII olmak zorunda — Türkçe karakter KOYMA (httpx patlar).
    # Yine de güvenlik için http.ascii_header() ile temizleniyor.
    user_agent: str = "itucap/0.1 (kisisel ders planlama araci; github.com/itucap)"
    scrape_plan_types: list[str] = field(default_factory=lambda: ["lisans", "cap"])
    # ★ OBS Ders Plan Denklikleri sayfası (28.08.2026, kullanıcı isteği: *"ders
    # denkliklerini bu siteden çekmek lazım"*). Bu sayfanın `ProgramId`i, plan
    # id'lerinden AYRI bir sayı uzayında (dropdown'dan: GEO_LS=1247, BLG=871).
    # Buraya kendi anadal/ÇAP programlarının ProgramId'lerini yaz; `make refresh`
    # her tazelemede o programların resmî denkliklerini çeker. Boşsa denklik
    # adımı ATLANIR (sessizce değil — adım "0 program" der).
    #   eq_program_ids = [1247, 871]     # Geomatik (anadal) + Bilgisayar (ÇAP)
    eq_program_ids: list[int] = field(default_factory=list)
    # ★ TÜM (lisans) programların denkliklerini tara (28.08.2026: "diğer
    # programlar için de baksın"). Kapsamlı ama YAVAŞ — ~93 program, her
    # tazelemede yüzlerce istek. Açıkken `eq_program_ids` yerine geçer; arayüz
    # yine yalnız GEREKEN derslerine denk düşenleri gösterir (fazlası süzülür).
    # Nadir değişir; kayıt haftasında kapatıp `eq_program_ids`'e dönmek hızlı.
    eq_all_programs: bool = False
    # ★★ EKSTRA program kodları — anadal/ÇAP/yandal kodları BURAYA YAZILMAZ.
    # (Kullanıcı isteği 27.08.2026: *"alabileceğim ders kodlarını anadal çap
    # ve yandala göre otomatik ekler misin, orada sadece ekstra program
    # türleri girilebilsin"*.)
    #
    # Şubelerin `Dersi Alabilen Programlar` listesinde arayacağımız kodlar
    # `allowed_programs`; o da SEÇİLENLERDEN TÜRETİLENLER ∪ BURASI.
    # Eskiden bu alan listenin TAMAMIydı ve seçim değiştiğinde elle
    # güncellenmesi gerekiyordu — güncellenmeyince ders havuzu sessizce
    # yanlış kalıyordu (bkz. `_bos_havuz_sebebi`, yer tutucu `XXX` vakası).
    #
    # ⚠️ Geriye dönük uyumlu: eski dosyalarda burada türetilenler de yazıyor;
    # birleşim aynı kümeyi verdiği için davranış değişmiyor.
    program_codes: list[str] = field(default_factory=lambda: [])

    # ★ Yük birimi. İTÜ'nün kendi kredi sistemi varsayılan; AKTS ikincil olarak
    # her yerde gösterilir ama sınır bu birimden hesaplanır.
    unit: str = "kredi"                 # 'kredi' | 'akts'
    max_load: float = 35.0              # dönem üst sınırı, seçilen birimde
    # ★ Tavanı GNO'ya göre yönetmelikten al (MADDE 17/2-a). Kullanıcı isteği
    # 23.08.2026. Elle bir sayı dayatmak, GNO değiştiğinde eskiyen ve kimsenin
    # güncellemediği bir ayar demekti. `false` yaparsan `max_load` aynen geçerli.
    max_load_auto: bool = True

    # ★ Faz 25/D1 — bozuk ayar dosyası sayfayı KİLİTLEMESİN (24.08.2026).
    #
    # Faz 24'te yazıcı hatası düzeldi ama ELLE bozulmuş bir dosya hâlâ her
    # isteği ham bir `tomllib` hatasına çeviriyordu: uygulama hiç açılmıyor,
    # ekranda `{"error": "Cannot declare ('student',) twice"}` yazıyor.
    #
    # ⚠️ Sessizce yok saymak da olmaz: yanlış ayarla çalışmak, çalışmamaktan
    # kötü — kullanıcı başka bir bölümün raporuna bakıp doğru sanır. Bu yüzden
    # varsayılana düşüyoruz (yani HİÇBİR bölüm seçili değil, karşılama kartı
    # açılıyor) ve hatayı `load_error` alanında TAŞIYORUZ; arayüz bunu
    # tepede yazmak zorunda.
    load_error: str = ""
    # ★★ FAZ 53 — YANLIŞ TABLODA DURAN AYAR SESSİZCE YOK SAYILIYORDU.
    #
    # `load` yalnız `[student]` ve `[scraper]`ı okuyor. Kullanıcının kendi
    # dosyasında (Mac, 21.09.2026) `cap_baslangic_yariyili` ve `mesgul`
    # satırları dosyanın SONUNA, yani `[regulation]` tablosunun altına
    # düşmüştü: yorum "3 ya da 5 yaz" diyor, yazılsa HİÇBİR ŞEY olmuyor —
    # yarıyıl kredi tabanı uygulanmıyor ve araç bunu söylemiyordu.
    # Satırı başka tablodan okumak da doğru değil (hangisi geçerli?); ne
    # olduğunu ve nereye taşınacağını söylüyoruz.
    load_uyarilari: list[dict] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path | None = None) -> "Settings":
        path = path or ROOT / "config" / "settings.toml"
        if not path.exists():
            return cls()
        try:
            raw = tomllib.loads(path.read_text(encoding="utf-8"))
        except (tomllib.TOMLDecodeError, OSError, UnicodeDecodeError) as exc:
            obj = cls()
            obj.load_error = f"{path.name}: {exc}"
            return obj
        merged: dict = {}
        for section in ("student", "scraper"):
            merged.update(raw.get(section, {}))
        known = {f for f in cls.__dataclass_fields__} - _IC_ALANLAR
        obj = cls(**{k: v for k, v in merged.items() if k in known})
        obj.load_uyarilari = _yanlis_yerdekiler(raw, known, merged)
        # ★ `second_kind` dosyada YAZMIYORSA program kodlarından çıkarılıyor.
        # Varsayılanı düz "yok" bırakmak, `cap_program = "BLG"` yazmış ama
        # `second_kind` yazmamış bir kullanıcının ÇAP'ını sessizce yok
        # sayardı — beyan edilmiş bir şeyi görmezden gelmek.
        # Hiçbir program kodu yoksa "yok" doğru: ilk ziyaretçi bir program
        # SEÇMEDİ, aracın onun adına seçmesi de saçma olurdu.
        if "second_kind" not in merged:
            varlar = [k for k in ("cap", "yandal") if obj.program_of(k)]
            obj.second_kind = ("ikisi" if len(varlar) == 2
                               else (varlar[0] if varlar else "yok"))
        if obj.second_kind not in SECOND_CHOICES:
            obj.second_kind = "cap"
        # ⚠️ Buradaki "beyan yoksa kendi kodlarına düş" satırı KALDIRILDI:
        # türetme artık `allowed_programs`'ta, her seferinde. Alanı doldurmak,
        # türetilmiş kodları kullanıcının ELLE YAZDIĞI kodlardan ayırt
        # edilemez hale getiriyordu — arayüz de onları kutuda gösteriyor ve
        # bölüm değişince eski kod orada kalıyordu.
        # ★ İkinci program yandal ise OBS'den yandal planı çekilmeli; kullanıcı
        # scrape_plan_types'ı ayrıca güncellemek zorunda kalmasın.
        for kind in obj.second_kinds:
            need = SECOND_KINDS[kind][2]
            if need and need not in obj.scrape_plan_types:
                obj.scrape_plan_types = [*obj.scrape_plan_types, need]
        return obj

    # ------------------------------------------------------- ikinci program
    @property
    def second_kinds(self) -> tuple[str, ...]:
        """Etkin ikinci program türleri, sırayla: ('cap',) | ('cap','yandal') | ()

        ★ ÇAP ve yandal aynı anda alınabiliyor. Tekil `second_*` özellikleri
        BİRİNCİSİNİ döndürüyor ve eski çağrı yerleri için duruyor; iki
        programın da hesaba katılması gereken yerler bu listeyi kullanmalı.
        """
        return SECOND_CHOICES.get(self.second_kind, ("cap",))

    def program_of(self, kind: str) -> str:
        return ({"cap": self.cap_program, "yandal": self.yandal_program}
                .get(kind, "") or "")

    def plan_id_of(self, kind: str) -> int | None:
        """★★ `0` = "seçilmedi" ve `None`'a çevriliyor (hata: A1 incelemesi A2).

        Örnek ayar dosyası `cap_plan_id = 0` yazıyordu; kod "seçilmedi"yi
        `None` ile anlıyordu. `0 != None` olduğu için `resolve_seconds`
        `planId: 0` — var olmayan bir plan — döndürüyor ve **ÇAP bütün
        ekrandan sessizce düşüyordu**: panel yok, ders yok, kritik yol yok,
        hata mesajı da yok. `plans.py`'deki "planı bulunamayan tür listede
        KALIYOR" yolu hiç çalışmıyordu.
        """
        ham = {"cap": self.cap_plan_id, "yandal": self.yandal_plan_id}.get(kind)
        return ham or None

    @property
    def seconds(self) -> list[tuple[str, str, str, str, int | None]]:
        """[(kind, rol, etiket, program_kodu, plan_id), …] — program kodu OLANLAR.

        ⚠️ Kodu boş olan tür atlanıyor: "ikisi" seçilip yandal kodu
        girilmemişse ortada bir yandal YOK. Boş kodla devam etmek, olmayan
        bir programın planını aramak ve "plan bulunamadı" demek olurdu.
        """
        out = []
        for kind in self.second_kinds:
            code = self.program_of(kind)
            if not code:
                continue
            rol, etiket, _ = SECOND_KINDS[kind]
            out.append((kind, rol, etiket, code, self.plan_id_of(kind)))
        return out

    @property
    def second_role(self) -> str:
        """'CAP' | 'YANDAL' | '' — planlarda ve arayüzde kullanılan rol."""
        return SECOND_KINDS[self.second_kinds[0]][0] if self.second_kinds else ""

    @property
    def second_label(self) -> str:
        """'ÇAP' | 'Yandal' | '' — insan tarafı."""
        return SECOND_KINDS[self.second_kinds[0]][1] if self.second_kinds else ""

    @property
    def second_program(self) -> str:
        return self.program_of(self.second_kinds[0]) if self.second_kinds else ""

    @property
    def second_plan_id(self) -> int | None:
        return self.plan_id_of(self.second_kinds[0]) if self.second_kinds else None

    @property
    def derived_programs(self) -> list[str]:
        """Seçimlerden TÜRETİLEN kodlar: anadal + ÇAP + yandal.

        ★ Kullanıcı isteği 27.08.2026. Bunlar zaten kayıtlı olduğu
        programlar — elle yazdırmanın anlamı yok ve bölüm değişince eski
        kodun kutuda kalması sessiz bir hataydı.
        """
        gorulen: list[str] = []
        for c in (self.anadal_program, *(s[3] for s in self.seconds)):
            k = str(c or "").strip().upper()
            if k and k not in gorulen:
                gorulen.append(k)
        return gorulen

    @property
    def allowed_programs(self) -> set[str]:
        """Türetilenler ∪ ekstralar — şube süzgecinin baktığı küme."""
        return {*self.derived_programs,
                *(c.strip().upper() for c in self.program_codes if str(c).strip())}

    @property
    def unit_label(self) -> str:
        return "kredi" if self.unit == "kredi" else "AKTS"

    def preferences(self):
        """Motorun anladığı biçime çevir.

        ⚠️ Tek yerde çevriliyor: ayar alanları ile motorun alanları ayrı
        adlarda ve iki yerde çevirmek, birinin unutulduğu sessiz bir hataya
        açık olurdu (ör. arayüz tercihe göre gösterip motorun saymaması).
        """
        from .recommend import Preferences

        return Preferences(
            en_erken=int(self.tercih_en_erken or 0),
            bos_gunler=tuple(int(g) for g in (self.tercih_bos_gunler or [])
                             if str(g).strip().isdigit() and 1 <= int(g) <= 7),
            kampus_degisimi_istemiyorum=bool(self.tercih_kampus_degisimi),
            cevrimici_tercih=bool(self.tercih_cevrimici),
            istenen_hocalar=tuple(
                s for s in (str(x).strip() for x in (self.tercih_istenen_hocalar or []))
                if s),
            istenmeyen_hocalar=tuple(
                s for s in (str(x).strip() for x in (self.tercih_istenmeyen_hocalar or []))
                if s),
        )


# ------------------------------------------------------- ayarları geri yazma
# ★ Arayüzden program/dönem seçilebiliyor; seçim `settings.toml`'a dönmeli.
# Dosyayı tomllib ile okuyup yeniden üretmek YORUMLARI SİLERDİ — o dosyadaki
# yorumlar projenin ölçüm notları (neden 2229, neden 35 kredi). O yüzden
# satır bazlı, yalnız bilinen anahtara dokunan bir yazıcı kullanıyoruz.

_EDITABLE = {
    "anadal_program", "anadal_plan_id", "second_kind",
    "cap_program", "cap_plan_id", "yandal_program", "yandal_plan_id",
    "donem", "term", "unit", "max_load", "max_load_auto", "program_codes", "watch_courses",
    "cap_baslangic_yariyili", "mesgul", "kilitli",
    "tercih_en_erken", "tercih_bos_gunler", "tercih_kampus_degisimi",
    "tercih_cevrimici", "tercih_istenen_hocalar", "tercih_istenmeyen_hocalar",
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
    # ★★ Kontrol karakterleri de kaçılıyor (güvenlik denetimi 27.08.2026).
    # Eski hâli yalnız `\` ve `"` kaçıyordu; bir SATIR SONU geçseydi
    # `"a\nkey = evil"` gibi GEÇERLİ ama BAŞKA anahtar taşıyan bir TOML
    # satırı üretirdi — dosyaya anahtar enjeksiyonu.
    #
    # Bugün buraya serbest metin round-trip doğrulamasından geçmeden
    # ulaşamıyor (meşgul etiketi `parse_busy` ile kolunuyor); ama yazıcının
    # KENDİ BAŞINA güvenli olması gerekir — "çağıran zaten temizliyor"
    # sessiz bir varsayım ve yeni bir alan eklendiğinde çöker. Bu projedeki
    # "yazıcı okuyamayacağı şeyi üretmesin" ilkesinin ta kendisi.
    metin = (str(value).replace("\\", "\\\\").replace('"', '\\"')
             .replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t"))
    # Kalan kontrol karakterleri (U+0000–U+001F) → \uXXXX.
    metin = "".join(c if ord(c) >= 0x20 else f"\\u{ord(c):04x}" for c in metin)
    return '"' + metin + '"'


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
    # `student_end` = yeni anahtarın ekleneceği yer: [student] bloğunun son
    # satırı. ★ BAŞLIĞIN KENDİSİ de çapa: blok BOŞSA (yeni kurulan dosyada
    # ya da elle yazılmış boş blokta) eskiden -1 kalıyordu ve aşağıdaki
    # `else` dalı İKİNCİ bir `[student]` başlığı ekliyordu. tomllib bunu
    # "Cannot declare ('student',) twice" diye reddediyor; ilk kaydetme
    # uygulamayı bir daha açılmaz hale getiriyordu.
    student_end = -1
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
            if section == "student":
                student_end = i
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
    metin = "\n".join(lines) + "\n"

    # ★★ Faz 25/D1 — YAZDIĞIMIZ DOSYA OKUNABİLİR OLMALI (24.08.2026).
    #
    # Bozuk bir `settings.toml` arayüzden düzeltilemiyordu: yazıcı satır
    # bazlı çalıştığı için bozukluğu (ör. iki `[student]` başlığı) olduğu
    # gibi koruyordu. Kullanıcı hatayı görüyor, "Program"dan yeniden
    # seçiyor, aynı hatayı yine görüyordu — kapalı bir döngü.
    try:
        tomllib.loads(metin)
    except tomllib.TOMLDecodeError:
        try:
            tomllib.loads(path.read_text(encoding="utf-8") if path.exists() else "")
        except tomllib.TOMLDecodeError:
            # Girdi ZATEN bozuktu: kurtarabileceğimiz bir yapı yok.
            # ⚠️ Dosyayı silmiyoruz — içinde kullanıcının notları olabilir;
            # yanına yedekliyoruz ve temiz bir dosya yazıyoruz.
            if path.exists():
                path.with_suffix(path.suffix + ".bozuk").write_text(
                    path.read_text(encoding="utf-8"), encoding="utf-8")
            metin = "[student]\n" + "\n".join(
                f"{k} = {_toml_value(v)}" for k, v in values.items()) + "\n"
        else:
            # Girdi sağlamdı, çıktı bozuk → HATA BİZDE. Sessizce üstüne
            # yazmak, kullanıcının çalışan ayarını bozmak olurdu.
            raise ValueError(
                "ayar yazıcısı geçersiz TOML üretti; dosya değiştirilmedi")
    path.write_text(metin, encoding="utf-8")
    return path
