"""Faz 108 — denklik önerisinde AKTS.

Kullanıcı 27.09.2026: *"akts veya kredi farklıysa denklik olmuyor diye
biliyorum"*. Öneri motoru (`discover._build`) yalnız krediye bakıyordu:
adı ve kredisi aynı, AKTS'si farklı çift "yüksek güven" alıyor ve arayüzdeki
"yüksek güvenlilerin tümünü uygula" ile toplu uygulanabiliyordu.
"""
from pathlib import Path

import pytest

from itucap import config, discover as D


def _c(ad, kredi, akts):
    return {"name": ad, "credits": kredi, "ects": akts}


@pytest.mark.parametrize("kaynak,hedef,guven,gerekce", [
    (_c("Veri Yapıları", 3, 5), _c("Veri Yapıları", 3, 5), D.HIGH, "aynı AKTS (5)"),
    (_c("Veri Yapıları", 3, 5), _c("Veri Yapıları", 3, 7.5), D.LOW, "AKTS farklı: 5 ≠ 7.5"),
    (_c("Veri Yapıları", 3, None), _c("Veri Yapıları", 3, 7.5), D.HIGH, "aynı kredi (3)"),  # AKTS bilinmiyor
    (_c("Veri Yapıları", 3, 5), _c("Veri Yapıları", 4, 5), D.LOW, "kredi farklı: 3 ≠ 4"),
])
def test_GUVEN(kaynak, hedef, guven, gerekce):
    s = D._build("AAA 201E", "BBB 201E", {"AAA 201E": kaynak, "BBB 201E": hedef},
                 {"AAA 201E": "BB"}, "ANADAL")
    assert s.confidence == guven and gerekce in s.reasons, s.reasons


def test_DUSUK_GUVEN_resmi_listeye_yonlendiriyor():
    assert config.DIS_BAGLANTILAR["obsDenklik"]["url"].endswith("/public/GenelTanimlamalar/DersPlanDenklikleri")
    ui = (Path(D.__file__).parent / "ui.py").read_text(encoding="utf-8")
    assert 'level === "dusuk" ? `<div class="modenote"' in ui
    assert "disLink(\"obsDenklik\", \"İTÜ'nün resmî denklik listesine\")" in ui
