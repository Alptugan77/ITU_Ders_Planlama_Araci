"""Faz 130 — uygulama simgesi ve ana ekrana ekleme.

Kullanıcı (07.10.2026): *"can you add an app icon for when adding it to
homescreen"*. Eskiden ne simge ne Web App Manifest vardı: ana ekrana
eklenince tarayıcı sayfanın küçük bir ekran görüntüsünü ya da baş harfi
koyuyor, uygulama adres çubuğuyla açılıyordu.
"""
import importlib
import io
import json
import struct
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from itucap import server, tasarim as T, ui as UI

KOK = Path(UI.__file__).resolve().parents[2]


def _png_boyu(veri: bytes) -> tuple[int, int]:
    assert veri[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", veri[16:24])


def _uretici():
    sys.path.insert(0, str(KOK / "tools"))
    try:
        return importlib.import_module("simge_uret")
    finally:
        sys.path.pop(0)


def test_DOSYALAR_pakette_ve_boylari_dogru():
    beklenen = {"favicon-32.png": 32, "icon-192.png": 192, "icon-512.png": 512,
                "icon-maskable-512.png": 512, "apple-touch-icon.png": 180}
    for ad, boy in beklenen.items():
        assert _png_boyu((UI.SIMGE_DIZINI / ad).read_bytes()) == (boy, boy), ad
    assert set(UI.SIMGELER) == set(beklenen) | {"favicon.svg"}
    # Paket verisi: kurulu pakette de olsun.
    assert '"simge/*.png", "simge/*.svg"' in (KOK / "pyproject.toml").read_text(encoding="utf-8")


def test_SVG_uretecin_ciktisiyla_ayni():
    """Elle düzenlenmiş bir dosya üreteçten ayrışmasın."""
    assert (UI.SIMGE_DIZINI / "favicon.svg").read_text(encoding="utf-8") == _uretici().svg()


def test_PNG_uretecin_ciktisiyla_ayni():
    Image = pytest.importorskip("PIL.Image")
    U = _uretici()
    for ad in UI.SIMGELER:
        if not ad.endswith(".png"):
            continue
        dosya = Image.open(UI.SIMGE_DIZINI / ad).convert("RGB")
        taze = Image.open(io.BytesIO(U.DOSYALAR[ad]())).convert("RGB")
        assert dosya.tobytes() == taze.tobytes(), f"{ad}: `python tools/simge_uret.py` çalıştırılmalı"


def test_RENKLER_tasarim_sisteminden():
    U = _uretici()
    renk = {ad: (g, d) for ad, g, d, _ in T.RENKLER}
    assert U.SEAL == renk["seal"][1]
    assert U.ANADAL == renk["anadal"][0] and U.CAP == renk["cap"][0]
    assert UI.tema_renkleri() == {"gece": renk["ground"][0], "gunduz": renk["ground"][1]}


def test_MASKABLE_icerik_guvenli_bolgede():
    """Android simgeyi daireye kırpıyor; güvenli bölge merkezdeki %80'lik
    daire (yarıçap 0,4·boy). Her köşe onun içinde olmalı."""
    U = _uretici()
    for x, y, g, h, _ in U.sekiller(512, U.MASKABLE):
        for kx, ky in ((x, y), (x + g, y), (x, y + h), (x + g, y + h)):
            assert ((kx - 256) ** 2 + (ky - 256) ** 2) ** 0.5 <= 0.4 * 512, (kx, ky)
    # `any` simge kırpılmıyor ama içerik yine de kenara yapışık değil.
    assert min(min(x, y) for x, y, *_ in U.sekiller()) >= 0.18 * 512


def test_MANIFEST():
    m = UI.web_manifest()
    assert m["short_name"] == UI.AD_KISA and UI.AD_ACILIM in m["name"]
    assert m["display"] == "standalone" and m["lang"] == "tr"
    assert m["start_url"] == "./" and m["scope"] == "./", "site alt dizinde — yol göreli"
    amac = {(i["src"], i["purpose"]) for i in m["icons"]}
    assert ("icon-512.png", "any") in amac and ("icon-192.png", "any") in amac
    assert ("icon-maskable-512.png", "maskable") in amac
    assert all(i["src"] in UI.SIMGELER for i in m["icons"])
    json.dumps(m, ensure_ascii=False)


def test_HEAD_etiketleri():
    html = UI.render({})
    bas = html[:html.index("</head>")]
    for parca in ('<link rel="manifest" href="app.webmanifest">',
                  '<link rel="apple-touch-icon" href="apple-touch-icon.png">',
                  '<link rel="icon" href="favicon.svg" type="image/svg+xml">',
                  '<meta name="apple-mobile-web-app-title" content="DEPAR">',
                  'viewport-fit=cover',
                  f'<meta name="theme-color" content="{UI.tema_renkleri()["gunduz"]}" '
                  'media="(prefers-color-scheme: light)">'):
        assert parca in bas, parca
    assert "__TEMA_" not in html, "yer tutucu kaldı"
    # Seçili tema çubuğa da uygulanıyor; güvenli bölge payı alt çubukta.
    assert "temaRenginiUygula();\n});" in html
    assert ".ray{padding-bottom:env(safe-area-inset-bottom,0px)}" in html


def test_SUNUCU_simge_ve_manifest():
    h = server.build(object(), host="127.0.0.1", port=0)
    threading.Thread(target=h.serve_forever, daemon=True).start()
    taban = f"http://127.0.0.1:{h.server_address[1]}/"
    try:
        r = urllib.request.urlopen(taban + "app.webmanifest")
        assert r.headers["Content-Type"] == "application/manifest+json"
        assert json.loads(r.read())["short_name"] == "DEPAR"
        r = urllib.request.urlopen(taban + "icon-192.png")
        assert r.headers["Content-Type"] == "image/png" and _png_boyu(r.read()) == (192, 192)
        r = urllib.request.urlopen(taban + "favicon.svg")
        assert r.headers["Content-Type"] == "image/svg+xml"
        # Liste dışı ad, dizin dışına çıkma denemesi: 404.
        for yol in ("ui.py", "simge/icon-192.png", "..%2Fui.py", "icon-193.png"):
            with pytest.raises(urllib.error.HTTPError) as e:
                urllib.request.urlopen(taban + yol)
            assert e.value.code == 404, yol
    finally:
        h.shutdown()


def test_SITE_kurulumu_kopyaliyor():
    k = (KOK / "tools" / "site_kur.py").read_text(encoding="utf-8")
    assert "for ad in UI.SIMGELER:\n        shutil.copy(UI.SIMGE_DIZINI / ad, SITE / ad)" in k
    assert "(SITE / UI.WEB_MANIFEST).write_text(" in k
    # Çevrimdışı katman dosya listesini sitede olandan çıkarıyor → simgeler de
    # önbellekte; ayrı bir liste tutulmuyor.
    assert "site.rglob(\"*\")" in k


# --- Faz 130 düzeltmeleri (kullanıcı: "also fix and improve the app") --------
K = Path(UI.__file__).read_text(encoding="utf-8")


def _kontrast(a: str, b: str) -> float:
    def L(h):
        c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        c = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    x, y = sorted((L(a), L(b)))
    return (y + 0.05) / (x + 0.05)


def test_TABAN_isareti_secili_sekmede_okunuyor():
    """Kırmızı "taban ✗" lacivert seçili sekmede 1,3:1 idi."""
    r = {ad: (g, d) for ad, g, d, _ in T.RENKLER}
    for i in (0, 1):                                  # gece, gündüz
        assert _kontrast(r["danger"][i], r["seal"][i]) < 3, "ölçüm değişti — yorum güncellenmeli"
        assert _kontrast(r["ground"][i], r["seal"][i]) >= 4.5
    assert '<span class="tabtaban">· taban ✗</span>' in K
    assert 'style="color:var(--danger)">· taban ✗' not in K
    assert '.tab[aria-selected="true"] .tabtaban{color:inherit;' in K


def test_TELEFON_kapat_kosede_ve_baglantilar_44px():
    j = K.index("#sonraki{position:relative}")
    i = K.rindex("@media", 0, j)
    assert K[i:].startswith("@media (max-width:700px){"), "telefon kuralı değil"
    tel = K[i:K.index("\n}\n", j)]
    assert "#sonraki .sonrakiliste .kapat{position:absolute;" in tel
    assert "#sonraki{position:relative}" in tel
    # Yalnız "Yararlı bağlantılar" satırı (son div); cümle içindeki veri
    # kaynağı bağlantısı satır akışını bozmasın diye dışarıda.
    assert (".kaynaklar>div:last-child a.dislink{display:inline-block;min-height:44px;\n"
            "    padding-block:10px}") in tel
