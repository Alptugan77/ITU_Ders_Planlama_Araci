"""FAZ 38 — OBS Ders Not Dağılımı: **yalnız ÇEKME**.

    GET /public/DersNotDagilimi/NotDagilimiSearch?bransKodu=MAT&dersNo=103E&yil=2026

Cevap bir HTML **parçası**; içinde satır içi bir betikte:

    const ALL_DATA = [{"DonemKodu":"202630","YilAdi":"2025-2026",
                       "DonemTipAdi":"Summer Semester",
                       "ToplamAciklananOgrenci":991,
                       "Dagilim":[{"HarfNotu":"AA","Sayi":54,"Yuzde":5.45}, …]}, …];

★ Tek istek O YILIN bütün yarıyıllarını getiriyor — güz, bahar ve **yaz**.
Uç ayrıntısı ve ölçülen tuzaklar: `docs/obs-endpoints.md` §5.

★★ AYRIŞTIRMA VE SAKLAMA BURADA DEĞİL, `itucap.notlar`'da.

`tools/site_kur.py` tarayıcıya yalnız `ENGINE` listesindeki modülleri
kopyalıyor; `sources/` bilerek dışarıda (scraper'lar `httpx`/`selectolax`
istiyor, tarayıcıda yok). İlk yazımda her şey bu dosyadaydı ve `ui.py`
buradan import ediyordu — **yayınlanan site açılmaz oldu**:

    ModuleNotFoundError: No module named 'itucap.sources'

O yüzden sınır net: **ağa dokunan tek fonksiyon burada**, geri kalan
`notlar.py`de. `tests/test_site.py` bu sınırı artık kilitliyor.
"""
from __future__ import annotations

from .. import config
from ..notlar import (  # noqa: F401  (dışarıdan bu modül üzerinden de erişiliyor)
    GRADES,
    CourseDistribution,
    NotFound,
    TermDistribution,
    parse,
    split_code,
)

ENDPOINT = f"{config.OBS}/public/DersNotDagilimi/NotDagilimiSearch"


def fetch(client, code: str, year: int) -> CourseDistribution:
    """Tek ders + tek yıl. `NotFound` fırlatabilir.

    ⚠️ `client` bir `http.ObsClient`: istek aralığı ve yeniden deneme onda.
    Buraya çıplak `httpx` koymak, İTÜ'yü yorma korumasını atlatırdı.
    """
    brans, ders_no = split_code(code)
    html = client.get(ENDPOINT, {"bransKodu": brans, "dersNo": ders_no,
                                 "yil": int(year)})
    return parse(html, fallback_code=code)
