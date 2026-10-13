"""Faz 132 — yeniden düzen: kimlik aynı, kabuk ve hiyerarşi yeni.

Kullanıcı (12.10.2026): *"redesign the ui and ux of the site"*. Vitrin
öğrencisiyle her görünüm masaüstünde ve telefonda, iki temada gezildi:

* Masaüstünde üst çubuk üç satırdı (1440px'te 125px) ve "Sonraki adımlar"
  şeridi her görünümün tepesinde 90px duruyordu; içerik y=305'te
  başlıyordu. Şimdi y≈120.
* Programın sağ sütununda dokuz düğme aynı ağırlıkta alt alta duruyordu.
* Yol haritasında öncelik ve senaryo denetimleri cümle arasına serpilmişti.
"""
import pathlib
import re

from itucap import ui as UI

K = pathlib.Path(UI.__file__).read_text(encoding="utf-8")
_T = K[K.index("_TEMPLATE = r"):]
CSS = _T[_T.index("<style>"):_T.index("</style>")]
KATMAN = CSS[CSS.index("FAZ 132 — YENİDEN DÜZEN"):]


def test_UST_CUBUK_tek_bant_ad_durum_dugme():
    masa = re.search(r"@media \(min-width:701px\)\{(.*?)\n\}", KATMAN, re.S).group(1)
    assert 'grid-template-areas:"ad durum dugme" "ad veri dugme"' in masa
    # Telefonun kendi düzeni (Faz 129) dokunulmadan duruyor.
    assert "header .basdugme{order:2;margin-left:auto;display:flex" in CSS


def test_SONRAKI_yalniz_programda_ve_ray_kopyasi_yok():
    masa = re.search(r"@media \(min-width:701px\)\{(.*?)\n\}", KATMAN, re.S).group(1)
    assert ':root:not([data-gorunum="schedSection"]) #sonraki{display:none}' in masa
    assert '#sonraki [data-go="schedSection"],#sonraki [data-go="candSection"]{display:none}' in masa


def test_SAG_SUTUN_iki_grup():
    yan = re.search(r'<aside class="prgyan">(.*?)</aside>', K, re.S).group(1)
    i = yan.index('class="aracbaslik"')
    # Kaydetme başlığın ÜSTÜNDE, kayıt/paylaşım ALTINDA.
    assert yan.index('id="savePicks"') < i and yan.index('id="altKaydet"') < i
    for kimlik in ("crnBtn", "crnLoad", "icsBtn", "pngBtn", "danismanBtn", "shareBtn"):
        assert yan.index(f'id="{kimlik}"') > i, kimlik
    # Kayıt günü ile CRN'den yükle yan yana (ikisi de OBS kaydı).
    assert yan.index('id="crnLoad"') - yan.index('id="crnBtn"') < 80
    assert ".prgyan .toolbar{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))" in KATMAN
    assert "grid-column:1 / -1" in KATMAN


def test_GORUNUM_GIRISI_hareket_duyarliliginda_yok():
    m = re.search(r"@media \(prefers-reduced-motion:no-preference\)\{([^}]*\})", KATMAN)
    assert m and "gorunumGir" in m.group(1)
    assert "animation" not in KATMAN.replace(m.group(0), "").split("@keyframes")[0]


def test_OZET_NOTLARINDA_cizgi_baslangici_yok():
    """Not satırı zaten ayrı satırda (`display:block`); baştaki "— " süs."""
    for eski in ('ozetnot">— çıkarılırsa', 'ozetnot">— uygun boş', 'ozetnot">— ${ne(x)}'):
        assert eski not in K, eski


def test_KATMAN_yalniz_olcek_jetonu():
    """Yeni katmanda çıplak px/hex yok (ölçek denetiminin ruhu)."""
    govde = KATMAN[KATMAN.index("*/") + 2:]
    govde = re.sub(r"/\*.*?\*/", "", govde, flags=re.S).split("@keyframes")[0]
    assert not re.search(r"#[0-9A-Fa-f]{3,6}\b", govde)
    # İzinli: kırılma noktaları, alt çizgi kayması (optik), ray etiket sütunu.
    govde = re.sub(r"\((?:min|max)-width:\d+px\)", "", govde)
    govde = govde.replace("text-underline-offset:3px", "").replace("flex:0 0 72px", "")
    assert not re.findall(r"\d+px", govde)
