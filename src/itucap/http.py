"""Rate-limit'li HTTP istemcisi + ham yanıt arşivi (WP1.7).

OBS'yi yormamak için istekler arası bekleme ve exponential backoff vardır.
Her yanıt diske arşivlenir; sayfa yapısı değiştiğinde eski parse'ı debug
edebilmek için bu arşiv kritiktir.
"""
from __future__ import annotations

import hashlib
import time
from datetime import date
from pathlib import Path

import httpx

from . import config


def ascii_header(value: str) -> str:
    """HTTP başlık değerlerini ASCII'ye indirger.

    httpx başlıkları ascii ile encode eder; 'kişisel' gibi bir User-Agent
    UnicodeEncodeError ile patlar. Türkçe harfleri ASCII karşılıklarına çevirip
    kalanı atıyoruz — başlık kozmetik, veri kaybı değil.
    """
    table = str.maketrans({
        "ç": "c", "Ç": "C", "ğ": "g", "Ğ": "G", "ı": "i", "İ": "I",
        "ö": "o", "Ö": "O", "ş": "s", "Ş": "S", "ü": "u", "Ü": "U",
    })
    return (value or "").translate(table).encode("ascii", "ignore").decode("ascii")


class ObsClient:
    def __init__(self, settings: config.Settings, archive: bool = True):
        self.s = settings
        self.archive = archive
        self._last = 0.0
        self.client = httpx.Client(
            headers={
                "User-Agent": ascii_header(settings.user_agent),
                "Accept-Language": "tr,en;q=0.8",
            },
            timeout=30.0,
            follow_redirects=True,
        )

    # ------------------------------------------------------------------ util
    def _throttle(self) -> None:
        wait = self.s.request_delay_s - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()

    def _archive(self, url: str, params, text: str) -> None:
        if not self.archive:
            return
        key = hashlib.sha1(f"{url}{params}".encode()).hexdigest()[:16]
        d = config.ARCHIVE_DIR / date.today().isoformat()
        d.mkdir(parents=True, exist_ok=True)
        slug = url.rstrip("/").split("/")[-1][:40] or "root"
        (d / f"{slug}-{key}.html").write_text(text, encoding="utf-8")

    def _request(self, method: str, url: str, *, params=None, data=None, ajax=False) -> str:
        headers = {"X-Requested-With": "XMLHttpRequest"} if ajax else {}
        delay = 2.0
        last_exc: Exception | None = None
        for attempt in range(4):
            self._throttle()
            try:
                r = self.client.request(method, url, params=params, data=data, headers=headers)
                if r.status_code in (429, 502, 503, 504):
                    raise httpx.HTTPStatusError(f"HTTP {r.status_code}", request=r.request, response=r)
                r.raise_for_status()
                self._archive(url, params or data, r.text)
                return r.text
            except Exception as exc:  # noqa: BLE001 - ağ hataları için geniş yakalama
                last_exc = exc
                if attempt == 3:
                    break
                time.sleep(delay)
                delay *= 2
        raise RuntimeError(f"İstek başarısız: {method} {url} -> {last_exc}")

    # ------------------------------------------------------------------- api
    def get(self, url: str, params: dict | None = None) -> str:
        return self._request("GET", url, params=params)

    def post_json(self, url: str, data: dict) -> list | dict:
        import json

        txt = self._request("POST", url, data=data, ajax=True)
        try:
            return json.loads(txt)
        except json.JSONDecodeError:
            return []

    def close(self) -> None:
        self.client.close()


def download(url: str, dest: Path, user_agent: str) -> Path:
    """itu-helper gibi statik dosyalar için basit indirici."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with httpx.stream("GET", url, headers={"User-Agent": ascii_header(user_agent)},
                      timeout=120.0, follow_redirects=True) as r:
        r.raise_for_status()
        with dest.open("wb") as fh:
            for chunk in r.iter_bytes():
                fh.write(chunk)
    return dest
