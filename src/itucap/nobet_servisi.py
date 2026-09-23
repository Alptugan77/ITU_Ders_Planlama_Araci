"""FAZ 53 — Kontenjan nöbetini ARKA PLANDA çalıştır (yapılacaklar 4.2).

    make watch-kur                      # 10 dakikada bir, oturum açılınca kendiliğinden
    make watch-kur ARGS="--only-good"   # yalnız fırsatları bildir
    make watch-durum                    # çalışıyor mu, son satırlar
    make watch-kaldir                   # durdur ve kaldır

`make watch` bir terminal penceresini işgal ediyordu; pencere kapanınca ya
da bilgisayar yeniden başlayınca nöbet de bitiyordu — kayıt haftası boyunca
açık tutulması gereken şey tam da buydu. macOS'un kendi servis yöneticisi
(`launchd`) bir **Kullanıcı Aracısı** (LaunchAgent) olarak çalıştırıyor:
oturum açılınca başlıyor, terminal gerekmiyor, bildirimler yine masaüstüne.

## Kararlar

* **Kullanıcı aracısı, sistem servisi değil.** `~/Library/LaunchAgents`:
  yönetici parolası istemiyor, yalnız SENİN oturumunda çalışıyor ve
  bildirimi gösterebiliyor (sistem servisi masaüstüne ulaşamazdı).
* **Çökünce yeniden başla, bitince başlatma.** `KeepAlive.SuccessfulExit =
  false`: süreç hatayla düşerse (ağ yok, OBS yanıt vermiyor) `launchd` onu
  yeniden başlatıyor; `ThrottleInterval = 300` bunu **en fazla 5 dakikada
  bir** yapıyor — çöküp kalkan bir döngü OBS'yi dakikada onlarca kez
  yormasın.
* **Kayıt günü kipi (`--kayit`) YOK.** O kip 1 dakikada bir tarayıp 2 saat
  sonra kendiliğinden duruyor; arka planda unutulup günlerce dönmesi
  kaçınılması gereken şeyin ta kendisi (bkz. `watch.KAYIT_MAX_SURE`).
* **Günlük `data/` altında** (`nobet.log`): içinde izlediğin dersler var,
  `data/` zaten `.gitignore`da.
* **Yalnız macOS.** Başka sistemde hiçbir dosya YAZILMIYOR ve ne yapılacağı
  söyleniyor — yarım kurulmuş bir servis, kurulmamış olandan kötü.
"""
from __future__ import annotations

import os
import platform
import plistlib
import subprocess
import sys
from pathlib import Path
from typing import Callable

from . import config

ETIKET = "tr.itucap.nobet"          # launchd adı — ASCII, ters alan adı biçimi
YENIDEN_BASLAMA_ARASI = 300         # sn — watch.MIN_INTERVAL ile aynı taban


def plist_yolu(ev: Path | None = None) -> Path:
    return (ev or Path.home()) / "Library" / "LaunchAgents" / f"{ETIKET}.plist"


def gunluk_yolu() -> Path:
    return config.ROOT / "data" / "nobet.log"


def plist_uret(python: str, every: int, only_good: bool = False) -> bytes:
    """launchd tanımı. `python` MUTLAK yol olmalı: launchd'nin PATH'i
    `/usr/bin:/bin:/usr/sbin:/sbin` — sanal ortamı bilmiyor."""
    arg = [python, "-m", "itucap.pipeline", "watch", "--every", str(int(every))]
    if only_good:
        arg.append("--only-good")
    gunluk = str(gunluk_yolu())
    return plistlib.dumps({
        "Label": ETIKET,
        "ProgramArguments": arg,
        "WorkingDirectory": str(config.ROOT),
        # Çıktı günlüğe ANINDA düşsün; yoksa `watch-durum` boş görünürdü.
        "EnvironmentVariables": {"PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"},
        "RunAtLoad": True,
        "KeepAlive": {"SuccessfulExit": False},
        "ThrottleInterval": YENIDEN_BASLAMA_ARASI,
        "ProcessType": "Background",
        "LowPriorityIO": True,
        "StandardOutPath": gunluk,
        "StandardErrorPath": gunluk,
    })


def _alan() -> str:
    """launchctl'in kullanıcı oturumu alanı: `gui/501`."""
    return f"gui/{os.getuid()}"


Calistir = Callable[..., "subprocess.CompletedProcess"]


def _macos_mu(sistem: str | None) -> bool:
    if (sistem or platform.system()) == "Darwin":
        return True
    print("⚠️  Arka plan nöbeti macOS'un launchd'si ile kuruluyor; bu sistem "
          f"{sistem or platform.system()}. Hiçbir dosya yazılmadı.\n"
          "   Nöbeti yine de çalıştırabilirsin: `make watch` (terminal açık kalmalı).",
          file=sys.stderr)
    return False


def kur(every: int = 600, only_good: bool = False, *, ev: Path | None = None,
        sistem: str | None = None, calistir: Calistir = subprocess.run,
        python: str | None = None) -> int:
    from . import watch

    if not _macos_mu(sistem):
        return 2
    every = max(watch.MIN_INTERVAL, int(every))
    yol = plist_yolu(ev)
    yol.parent.mkdir(parents=True, exist_ok=True)
    gunluk_yolu().parent.mkdir(parents=True, exist_ok=True)
    # Eskisi yüklüyse önce indir: `bootstrap` aynı adla ikinci kez yüklemez
    # ve yeni aralık SESSİZCE uygulanmamış olurdu.
    calistir(["launchctl", "bootout", f"{_alan()}/{ETIKET}"],
             capture_output=True, text=True)
    yol.write_bytes(plist_uret(python or sys.executable, every, only_good))
    r = calistir(["launchctl", "bootstrap", _alan(), str(yol)],
                 capture_output=True, text=True)
    if r.returncode != 0:
        print(f"❌ launchd nöbeti yükleyemedi: {(r.stderr or r.stdout).strip()}\n"
              f"   Tanım dosyası: {yol}", file=sys.stderr)
        return 1
    print(f"✅ Nöbet arka planda — {every // 60} dakikada bir"
          + (" · yalnız fırsatlar" if only_good else "") + ".\n"
          "   Oturum açılınca kendiliğinden başlar; terminal gerekmez.\n"
          f"   Günlük: {gunluk_yolu()}\n"
          "   Durum:  make watch-durum · Durdur: make watch-kaldir\n"
          "   ⚠️  OBS'ye düzenli istek atıyor — kayıt dönemi bitince kaldır.")
    return 0


def kaldir(*, ev: Path | None = None, sistem: str | None = None,
           calistir: Calistir = subprocess.run) -> int:
    if not _macos_mu(sistem):
        return 2
    yol = plist_yolu(ev)
    calistir(["launchctl", "bootout", f"{_alan()}/{ETIKET}"],
             capture_output=True, text=True)
    if yol.exists():
        yol.unlink()
        print(f"⏹  Nöbet durduruldu ve kaldırıldı ({yol}).")
    else:
        print("Kurulu bir arka plan nöbeti yok.")
    return 0


def durum(*, ev: Path | None = None, sistem: str | None = None,
          calistir: Calistir = subprocess.run, satir: int = 8) -> int:
    """Kurulu mu, yüklü mü, çalışıyor mu — ve son satırlar.

    ⚠️ Üç ayrı durum, üç ayrı cümle: dosya var ama yüklü değil (oturum
    kapanıp açılmamış ya da elle indirilmiş) ile yüklü ama süreç yok
    (çöktü, yeniden başlamayı bekliyor) aynı şey değil."""
    if not _macos_mu(sistem):
        return 2
    yol = plist_yolu(ev)
    if not yol.exists():
        print("Kurulu bir arka plan nöbeti yok. Kurmak için: make watch-kur")
        return 1
    tanim = plistlib.loads(yol.read_bytes())
    arg = tanim.get("ProgramArguments", [])
    every = arg[arg.index("--every") + 1] if "--every" in arg else ""
    aralik = f"her {int(every) // 60} dk" if str(every).isdigit() else "aralık okunamadı"
    r = calistir(["launchctl", "print", f"{_alan()}/{ETIKET}"],
                 capture_output=True, text=True)
    if r.returncode != 0:
        print(f"⚠️  Tanım var ({yol}) ama launchd'ye YÜKLÜ DEĞİL. "
              "Yeniden kur: make watch-kur")
        kod = 1
    else:
        cikti = r.stdout or ""
        pid = next((s.split("=", 1)[1].strip() for s in cikti.splitlines()
                    if s.strip().startswith("pid =")), "")
        if pid:
            print(f"✅ Nöbet çalışıyor (pid {pid}) — {aralik}"
                  + (" · yalnız fırsatlar" if "--only-good" in arg else "") + ".")
            kod = 0
        else:
            print("⚠️  Yüklü ama şu an ÇALIŞMIYOR — büyük olasılıkla hatayla "
                  f"düştü; launchd {YENIDEN_BASLAMA_ARASI // 60} dakika içinde "
                  "yeniden deneyecek. Nedeni aşağıdaki satırlarda.")
            kod = 1
    g = gunluk_yolu()
    if g.exists():
        son = g.read_text(encoding="utf-8", errors="replace").splitlines()[-satir:]
        print(f"\n— {g.name} (son {len(son)} satır) —")
        for s in son:
            print("  " + s)
    return kod
