"""Faz 110 — denklik taraması eski tabloyu ancak TAM sonuçla ezer.

`step_equivalence` eski resmî denklikleri silip sayfa sayfa commit ediyor
(tam tarama 26 dk, ~1200 istek). Sessizce kırılan kazıyıcı (Faz 109: 0
denklik), yarıda kesilen ağ, Ctrl-C ya da birkaç programın hatası
yayınlanacak kataloğu boş/eksik bırakıyordu. Artık silmeden önce yedek
alınıyor; sonuç şüpheliyse eski tablo geri yükleniyor.
"""
import pytest

from itucap import config, db, pipeline as PL
from itucap.sources import obs_equivalence as EQ


def _ekle(con, hedef, kaynak, guven="official"):
    cur = con.execute("INSERT INTO equivalence(target_course,confidence,note_raw) VALUES (?,?,?)",
                      (hedef, guven, f"{hedef} ≡ {kaynak}"))
    con.execute("INSERT INTO equivalence_source(equivalence_id,course_code,min_grade) VALUES (?,?,'DD')",
                (cur.lastrowid, kaynak))


def _tablo(con):
    return sorted(tuple(r) for r in con.execute(
        """SELECT e.target_course, s.course_code, e.confidence FROM equivalence e
             JOIN equivalence_source s ON s.equivalence_id=e.id"""))


@pytest.fixture()
def kur(tmp_path, monkeypatch):
    class Sahte:
        def __init__(self, *_a, **_k): pass
        def close(self): pass
    monkeypatch.setattr(PL, "ObsClient", Sahte)
    con = db.connect(tmp_path / "r.sqlite3", "schema.sql")
    for i in range(10):
        _ekle(con, f"ESK {100 + i}", f"KYN {100 + i}")
    _ekle(con, "BEY 100", "BEY 200", "user_declared")      # kalıntı beyan: dokunulmaz
    con.commit()
    once = _tablo(con)

    def tara(yeni: int, hata: int = 0, patla: type | None = None):
        def sahte_sweep(client, con, progress=None, hatalar=None, **_k):
            for i in range(yeni):
                _ekle(con, f"YEN {100 + i}", f"KYN {100 + i}")
                con.commit()                       # gerçek kazıyıcı sayfa sayfa commit
            for i in range(hata):
                hatalar.append((i, f"P{i}", "zaman aşımı"))
            if patla:
                _ekle(con, "YAR 100", "YAR 200")   # commit edilmemiş yarım sayfa
                raise patla("ağ koptu")
            return 93, 200, yeni
        monkeypatch.setattr(EQ, "sweep_all", sahte_sweep)
        PL.step_equivalence(con, config.Settings(), [], all_programs=True)
        return _tablo(con)
    return con, once, tara


def test_TAM_tarama_eskiyi_ezer(kur):
    con, once, tara = kur
    sonra = tara(12)
    assert len(sonra) == 13 and all(h.startswith(("YEN", "BEY")) for h, _k, _g in sonra)


def test_BOS_tarama_eskiyi_korur(kur):
    con, once, tara = kur
    assert tara(0) == once
    mesaj = con.execute("SELECT message FROM ingest_run ORDER BY id DESC").fetchone()[0]
    assert "REDDEDİLDİ" in mesaj and "hiç denklik" in mesaj


def test_HATALI_ve_kucuk_tarama_eskiyi_korur(kur):
    con, once, tara = kur
    assert tara(9, hata=2) == once


def test_HATALI_ama_buyuyen_tarama_kabul(kur):
    """Birkaç program düşse de tablo büyüdüyse yeni liste daha eksiksiz."""
    con, once, tara = kur
    assert len(tara(11, hata=1)) == 12


def test_YARIYA_inen_tarama_eskiyi_korur(kur):
    con, once, tara = kur
    assert tara(4) == once


def test_ISTISNA_ve_CTRL_C_eskiyi_geri_yukler(kur):
    con, once, tara = kur
    with pytest.raises(RuntimeError):
        tara(3, patla=RuntimeError)
    assert _tablo(con) == once
    with pytest.raises(KeyboardInterrupt):
        tara(3, patla=KeyboardInterrupt)
    assert _tablo(con) == once


def test_ESKI_BOSSA_her_sonuc_kabul(tmp_path, monkeypatch):
    assert PL.denklik_korunmali(0, 0, 5) is None
    assert PL.denklik_korunmali(0, 3, 1) is None
    assert PL.denklik_korunmali(3183, 3183, 0) is None
    assert PL.denklik_korunmali(3183, 3000, 0) is None      # doğal küçülme (%6) kabul


def test_SWEEP_ALL_hatalari_sayar(tmp_path, monkeypatch):
    monkeypatch.setattr(EQ, "all_program_ids", lambda c, u: [(1, "A"), (2, "B"), (3, "C")])

    def sp(client, con, pid, **_k):
        if pid == 2:
            raise RuntimeError("500")
        return 1, 1
    monkeypatch.setattr(EQ, "sweep_program", sp)
    hatalar = []
    assert EQ.sweep_all(None, None, hatalar=hatalar) == (3, 2, 2)
    assert [h[:2] for h in hatalar] == [(2, "B")]
