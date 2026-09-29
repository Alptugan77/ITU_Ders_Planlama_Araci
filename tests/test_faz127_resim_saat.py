"""Faz 127 — program resminde (PNG) blokların içinde saat aralığı.

Kullanıcı (29.09.2026): *"ders programında ve görselinde ders bloklarının
içine saat aralığını yazar mısın"*. Izgaradaki blokta saat vardı; indirilen
resimde yalnız ders kodu, adı ve CRN vardı. Saat artık ders kodunun hemen
altında (en kısa blokta da görünsün diye addan önce); meşgul blokta da.
"""
import pathlib

from itucap import ui as UI

K = pathlib.Path(UI.__file__).read_text(encoding="utf-8")


def _resim():
    i = K.index("async function resimIndir(")
    return K[i:K.index("\n}\n", i)]


def test_RESIM_blokta_saat_addan_once():
    r = _resim()
    saat = r.index("yaz(`${hhmm(m.start)}–${hhmm(m.end)}`")
    ad = r.index('yaz(p.cand.name || ""')
    assert r.index("yaz(p.cand.course") < saat < ad
    assert "if(h > 24) yaz(`${hhmm(m.start)}" in r          # 1 saatlik blokta da (66 px)


def test_RESIM_mesgul_blokta_saat():
    assert "yaz(`${hhmm(b.start)}–${hhmm(b.end)}`" in _resim()


def test_IZGARA_blokta_saat_duruyor():
    assert '<small class="mono">${hhmm(c.m.start)}–${hhmm(c.m.end)}' in K
