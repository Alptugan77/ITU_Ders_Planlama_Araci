"""Faz 53 — kontenjan nöbeti ARKA PLANDA (yapılacaklar 4.2).

`make watch` bir terminal penceresini işgal ediyordu; pencere kapanınca ya da
bilgisayar yeniden başlayınca nöbet de bitiyordu. macOS'un servis yöneticisi
(`launchd`) onu bir Kullanıcı Aracısı olarak çalıştırıyor.

⚠️ Bu kapsayıcı Linux: `launchctl` burada YOK. Testler (a) üretilen tanımın
kendisini `plistlib` ile, (b) verilen komutları sahte bir çalıştırıcıyla
doğruluyor. Gerçek Mac denemesi 23.09.2026'da kullanıcı tarafından yapıldı
(`nobet kur` → `make watch-durum` "çalışıyor" → `make watch-kaldir`); bu
docstring o yüzden güncellendi — testler aynı.
"""
import plistlib
import subprocess

import pytest

from itucap import config as C
from itucap import nobet_servisi as NS
from itucap import watch as W


class _Sahte:
    """`subprocess.run` yerine: komutları kaydeder, istenen cevabı döner."""

    def __init__(self, cevap=None):
        self.komutlar, self.cevap = [], cevap or {}

    def __call__(self, komut, **kw):
        self.komutlar.append(komut)
        kod, cikti = self.cevap.get(komut[1], (0, ""))
        return subprocess.CompletedProcess(komut, kod, stdout=cikti, stderr="hata")


@pytest.fixture
def kok(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "ROOT", tmp_path / "depo")
    (tmp_path / "depo").mkdir()
    return tmp_path


def test_TANIM_dogru(kok):
    t = plistlib.loads(NS.plist_uret("/v/bin/python", 600, only_good=True))
    assert t["Label"] == "tr.itucap.nobet"
    # launchd'nin PATH'i sanal ortamı bilmiyor → MUTLAK python yolu.
    assert t["ProgramArguments"] == ["/v/bin/python", "-m", "itucap.pipeline",
                                     "watch", "--every", "600", "--only-good"]
    assert t["WorkingDirectory"] == str(kok / "depo")
    assert t["RunAtLoad"] is True
    # Çökünce yeniden başla, NORMAL bitince başlatma; en fazla 5 dk'da bir.
    assert t["KeepAlive"] == {"SuccessfulExit": False}
    assert t["ThrottleInterval"] >= W.MIN_INTERVAL
    # Günlük data/ altında (gitignore'da) ve çıktı tamponlanmıyor.
    assert t["StandardOutPath"] == t["StandardErrorPath"] == str(kok / "depo" / "data" / "nobet.log")
    assert t["EnvironmentVariables"]["PYTHONUNBUFFERED"] == "1"
    assert "--kayit" not in t["ProgramArguments"]


def test_KUR_yaziyor_ve_YUKLUYOR(kok, capsys):
    s = _Sahte()
    assert NS.kur(every=120, ev=kok, sistem="Darwin", calistir=s, python="/v/py") == 0
    yol = kok / "Library" / "LaunchAgents" / "tr.itucap.nobet.plist"
    t = plistlib.loads(yol.read_bytes())
    # 120 sn istense de nöbetin tabanı (5 dk) uygulanıyor.
    assert t["ProgramArguments"][-1] == str(W.MIN_INTERVAL)
    # Önce eskisini İNDİR (yoksa yeni aralık sessizce uygulanmazdı), sonra yükle.
    assert [k[1] for k in s.komutlar] == ["bootout", "bootstrap"]
    assert s.komutlar[1][2].startswith("gui/") and s.komutlar[1][3] == str(yol)
    assert "5 dakikada bir" in capsys.readouterr().out


def test_YUKLENEMEZSE_basari_DEMIYOR(kok, capsys):
    s = _Sahte({"bootstrap": (5, "")})
    assert NS.kur(ev=kok, sistem="Darwin", calistir=s, python="/v/py") == 1
    assert "yükleyemedi" in capsys.readouterr().err


def test_KALDIR(kok, capsys):
    s = _Sahte()
    NS.kur(ev=kok, sistem="Darwin", calistir=s, python="/v/py")
    assert NS.kaldir(ev=kok, sistem="Darwin", calistir=s) == 0
    assert not NS.plist_yolu(kok).exists()
    assert s.komutlar[-1][1] == "bootout"
    # İkinci kez kaldırmak hata değil, durumu söylüyor.
    assert NS.kaldir(ev=kok, sistem="Darwin", calistir=s) == 0
    assert "Kurulu bir arka plan nöbeti yok" in capsys.readouterr().out


def test_DURUM_uc_ayri_cumle(kok, capsys):
    """Kurulu değil · kurulu ama yüklü değil · yüklü ama çalışmıyor · çalışıyor."""
    assert NS.durum(ev=kok, sistem="Darwin", calistir=_Sahte()) == 1
    assert "Kurulu bir arka plan nöbeti yok" in capsys.readouterr().out
    NS.kur(ev=kok, sistem="Darwin", calistir=_Sahte(), python="/v/py")
    capsys.readouterr()
    assert NS.durum(ev=kok, sistem="Darwin", calistir=_Sahte({"print": (113, "")})) == 1
    assert "YÜKLÜ DEĞİL" in capsys.readouterr().out
    assert NS.durum(ev=kok, sistem="Darwin",
                    calistir=_Sahte({"print": (0, "\tstate = not running\n")})) == 1
    assert "ÇALIŞMIYOR" in capsys.readouterr().out
    g = NS.gunluk_yolu()
    g.parent.mkdir(parents=True, exist_ok=True)
    g.write_text("[10:00] değişiklik yok (1. tur)\n", encoding="utf-8")
    assert NS.durum(ev=kok, sistem="Darwin",
                    calistir=_Sahte({"print": (0, "\tstate = running\n\tpid = 4242\n")})) == 0
    cikti = capsys.readouterr().out
    assert "pid 4242" in cikti and "her 10 dk" in cikti and "değişiklik yok" in cikti


def test_MACOS_DEGILSE_hicbir_sey_YAZILMIYOR(kok, capsys):
    s = _Sahte()
    assert NS.kur(ev=kok, sistem="Linux", calistir=s) == 2
    assert not (kok / "Library").exists() and s.komutlar == []
    assert "Hiçbir dosya yazılmadı" in capsys.readouterr().err


def test_KOMUT_SATIRI_ve_MAKE():
    import sys
    # Gerçek komut satırı: bu sistem macOS değil → 2 ve açıklama, dosya yok.
    r = subprocess.run([sys.executable, "-m", "itucap.pipeline", "nobet", "durum"],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 2 and "launchd" in r.stderr, r.stderr
    kaynak = (C.ROOT / "Makefile").read_text(encoding="utf-8")
    for hedef in ("watch-kur:", "watch-kaldir:", "watch-durum:"):
        assert hedef in kaynak, hedef
    assert "itucap.pipeline nobet kur $(ARGS)" in kaynak
    src = (C.ROOT / "src" / "itucap" / "pipeline.py").read_text(encoding="utf-8")
    assert 'nb.add_argument("eylem", choices=["kur", "kaldir", "durum"])' in src
    # Kayıt günü kipi arka plana BİLEREK taşınmadı.
    blok = src[src.index('sub.add_parser("nobet"'):src.index("set_defaults(func=cmd_nobet)")]
    assert "--kayit" not in blok
