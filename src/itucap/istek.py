"""★★ FAZ 91 — İSTEK BOYUNCA ÖNBELLEK.

Bir sayfa durumu (anlık görüntü) ya da istek üzerine hesap (kalma riski,
senaryo, ÇAP seçenekleri) aynı veriyi defalarca okuyordu: yol haritası bir
istekte 12 kez kuruluyor ve her kurulum aynı şubeleri, ders adlarını, önşart
ağaçlarını baştan okuyordu (gerçek katalog, ölçüm 25.09.2026).

⚠️ Önbellek YALNIZ bir istek boyunca yaşıyor (`istek()` bağlamı). Kontenjan
tazelemesi satırları UPDATE ediyor; istekler arası bir önbellek eski doluluk
verisini gösterirdi. İstek içinde veri değişmiyor: sunucu bütün DB işini tek
kilit altında yapıyor, statik sitede tek iş parçacığı var. Bağlam dışında
`bellek()` hiç saklamadan hesaplıyor — davranış eskisiyle aynı.

İş parçacığına özel; iç içe bağlamlar dıştakini kullanıyor.

⚠️ Bu modül tarayıcıya da gidiyor: `tools/site_kur.py` ENGINE listesinde.
"""
from __future__ import annotations

import contextlib
import threading

_YEREL = threading.local()


@contextlib.contextmanager
def istek():
    """Bu blok boyunca `bellek()` aynı anahtar için bir kez hesaplar."""
    dis = getattr(_YEREL, "d", None) is not None
    if not dis:
        _YEREL.d = {}
    try:
        yield
    finally:
        if not dis:
            _YEREL.d = None


def bellek(anahtar, hesap):
    """İstek bağlamındaysa `anahtar` için `hesap()`ın sonucunu saklar.

    ⚠️ Saklanan nesne çağıranlar arasında PAYLAŞILIYOR: yalnız okunan
    değerler için kullanılmalı (değiştirilecekse çağıran kopyalamalı)."""
    d = getattr(_YEREL, "d", None)
    if d is None:
        return hesap()
    if anahtar not in d:
        d[anahtar] = hesap()
    return d[anahtar]
