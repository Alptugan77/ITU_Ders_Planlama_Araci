"""FAZ 11 — Kontenjan nöbeti: sen sormadan haber ver.

    make watch                    # 10 dakikada bir, Ctrl+C ile dur
    make watch ARGS="--every 300 --once"

Faz 9 "ne değişti" diyebiliyordu ama **sen sorunca**. Kayıt haftasında asıl
istenen şey bu değil: *"BLG 351E'de yer açılınca haber ver."* Kontenjan
saatler içinde doluyor ve boşalıyor; ekrana bakarak yakalanmıyor.

Nöbetçi belirli aralıkla veriyi tazeliyor, Faz 9'un anlık görüntülerini
karşılaştırıyor ve **yalnız seni ilgilendiren** bir değişiklik varsa
bildirim atıyor.

## Neyi izliyor

Varsayılan: iki planının açık slotlarındaki dersler (Faz 9'daki `watch`
süzgeci). `config/settings.toml` içindeki `izleme` listesiyle daraltılabilir:

    izleme = ["BLG 351E", "BLG 335E"]

Dar liste daha iyi: 191 ders izlerken her tazelemede bir şey değişir ve
bildirim gürültüye döner.

## Bildirim

macOS'ta `osascript` ile masaüstü bildirimi — **bağımlılık yok**. Başka
işletim sisteminde ya da `osascript` yoksa sessizce terminale yazıyor.
Bildirim gönderemiyorsa bunu bir kez söylüyor, sonra susuyor.

⚠️ Nöbetçi OBS'ye düzenli istek atıyor. Varsayılan aralık **10 dakika** ve
altına inmesi engelli: kayıt haftasında bile bundan sık taramanın kazancı
yok, OBS'yi yormanın anlamı da.
"""
from __future__ import annotations

import shlex
import subprocess
import sys
import time

from . import changes as CH
from . import config, db

MIN_INTERVAL = 300          # 5 dk — normal nöbette bunun altına inilemez
DEFAULT_INTERVAL = 600

# ★ Faz 25/C2 — KAYIT GÜNÜ kipi (24.08.2026).
#
# Kayıt gününde kontenjan dakikalar içinde değişiyor; 10 dakikada bir bakan
# nöbet o gün işe yaramıyor. Ama sınırı topluca düşürmek İTÜ sunucularını
# gereksiz yere yormak demek — bu araç kimsenin altyapısını meşgul etmemeli.
#
# Uzlaşma: ayrı ve AÇIKÇA istenen bir kip, daha kısa aralık, ve KENDİ KENDİNE
# BİTEN bir süre. Unutulup günlerce dönen bir nöbet, asıl kaçınmak istediğimiz
# şey; sınır olmadan kısa aralık vermek onu davet ederdi.
KAYIT_INTERVAL = 60         # 1 dk
KAYIT_MAX_SURE = 2 * 3600   # 2 saat sonra kendiliğinden duruyor


def notify(title: str, message: str) -> bool:
    """Masaüstü bildirimi. Gönderilemezse False — çağıran karar verir."""
    try:
        script = (f'display notification {json_str(message)} '
                  f'with title {json_str(title)}')
        subprocess.run(["osascript", "-e", script], check=True,
                       capture_output=True, timeout=10)
        return True
    except Exception:                                      # noqa: BLE001
        return False


def json_str(text: str) -> str:
    """AppleScript dizgesi — tırnak kaçışı `shlex` ile değil elle yapılıyor."""
    return '"' + str(text).replace("\\", "\\\\").replace('"', '\\"')[:220] + '"'


def summarize(diff: CH.Diff) -> str:
    """Bildirim tek satır olmalı — en çok işe yarayan üçünü öne al."""
    parts = []
    if diff.freed:
        parts.append("yer açıldı: " + ", ".join(i["course"] for i in diff.freed[:3]))
    if diff.opened:
        parts.append("açıldı: " + ", ".join(i["course"] for i in diff.opened[:3]))
    if diff.new_sections:
        parts.append("yeni şube: " + ", ".join(i["course"] for i in diff.new_sections[:3]))
    if diff.filled:
        parts.append("doldu: " + ", ".join(i["course"] for i in diff.filled[:3]))
    if diff.closed:
        parts.append("kapandı: " + ", ".join(i["course"] for i in diff.closed[:3]))
    return " · ".join(parts) or "değişiklik var"


def interesting(diff: CH.Diff, only_good: bool = False) -> bool:
    """Bildirim atmaya değer mi?

    `only_good=True` ise yalnız FIRSAT bildirilir (yer açıldı / ders açıldı /
    yeni şube). Dolan kontenjan da bilgi ama gece 3'te uyandırmaya değmez.
    """
    if only_good:
        return bool(diff.freed or diff.opened or diff.new_sections)
    return not diff.empty


def watch_codes(con, ucon, settings) -> set[str]:
    """İzlenecek dersler: beyan varsa o, yoksa planlarının açık slotları."""
    declared = {str(c).upper().strip() for c in (settings.watch_courses or [])}
    if declared:
        return declared
    from .pipeline import _watch_codes
    return _watch_codes(con, ucon, settings)


def tick(settings, skip_obs: bool = False) -> CH.Diff:
    """Bir tur: tazele, anlık görüntü al, karşılaştır."""
    from . import pipeline

    con = db.reference_db()
    ucon = db.user_db()
    pipeline.step_ituhelper(con, settings, offline=False)
    if not skip_obs:
        try:
            pipeline.step_obs_plans(con, settings)
        except Exception as exc:                           # noqa: BLE001
            print(f"   ⚠️  OBS adımı atlandı: {exc}", file=sys.stderr)
    CH.take(con)
    return CH.compare(con, watch=watch_codes(con, ucon, settings))


def run(every: int = DEFAULT_INTERVAL, once: bool = False,
        only_good: bool = False, skip_obs: bool = False,
        kayit: bool = False) -> int:
    settings = config.Settings.load()
    taban = KAYIT_INTERVAL if kayit else MIN_INTERVAL
    if kayit and every == DEFAULT_INTERVAL:
        every = KAYIT_INTERVAL          # kip seçildiyse varsayılan da değişsin
    every = max(taban, int(every))
    con = db.reference_db()
    ucon = db.user_db()
    codes = watch_codes(con, ucon, settings)
    source = "beyan" if settings.watch_courses else "planlarındaki açık dersler"
    print(f"👁  Nöbet başladı — {len(codes)} ders izleniyor ({source})")
    aralik = f"{every // 60} dk" if every >= 60 else f"{every} sn"
    print(f"   aralık: {aralik} · Ctrl+C ile dur")
    if kayit:
        print(f"   ⚡ KAYIT GÜNÜ kipi — {KAYIT_MAX_SURE // 3600} saat sonra "
              "kendiliğinden duruyor.")
        print("   ⚠️  Bu kip OBS'ye sık istek atıyor; kayıt penceresi dışında "
              "kullanma.")
    if settings.watch_courses:
        print("   " + ", ".join(sorted(codes)[:12]))
    can_notify = True
    rounds = 0
    basladi = time.monotonic()
    try:
        while True:
            # ⚠️ Süre sınırı SESSİZ değil: neden durduğunu yazıyor, yoksa
            # kullanıcı nöbetin çöktüğünü sanar ve bir daha güvenmez.
            if kayit and time.monotonic() - basladi > KAYIT_MAX_SURE:
                print(f"\n⏹  kayıt günü kipi {KAYIT_MAX_SURE // 3600} saat "
                      f"doldu, nöbet durdu ({rounds} tur). Devam için "
                      "komutu yeniden çalıştır.")
                return 0
            rounds += 1
            stamp = time.strftime("%H:%M:%S")
            diff = tick(settings, skip_obs=skip_obs)
            if interesting(diff, only_good):
                text = summarize(diff)
                print(f"[{stamp}] 🔔 {text}")
                print(CH.format_diff(diff, watching=len(codes)))
                if can_notify and not notify("itucap — kontenjan", text):
                    can_notify = False
                    print("   (masaüstü bildirimi gönderilemedi; "
                          "yalnız terminale yazılacak)")
            else:
                print(f"[{stamp}] değişiklik yok ({rounds}. tur)")
            if once:
                return 0
            time.sleep(every)
    except KeyboardInterrupt:
        print(f"\n⏹  nöbet bitti ({rounds} tur)")
        return 0
