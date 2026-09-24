"""Faz 62 — site yarı boş açılıyordu (kullanıcı 24.09.2026: "the site is not
working properly it doesnot load the courses and other stuff it is semi-blank").

Sebep (yayındaki katalog + Pyodide ile yerelde kurulup Chromium'da ölçüldü):
`site_kur.kabuk` yükleyiciyi ve `app.js`i `str.replace("<body>", …, 1)` ile
İLK "<body>" METNİNE yazıyordu. Faz 61'de bir CSS yorumu "kap <body>'ye
taşınıyor" diyordu → yükleyici ve betik <style>'ın İÇİNE girdi; tarayıcı
onları metin saydı, `app.js` HİÇ İSTENMEDİ (sunucu yalnız `/` isteği aldı),
Pyodide başlamadı, veri gelmedi.

Ayrıca aynı ölçümde: sitede kimse `term` ayarı girmediği için yol haritası,
ÇAP seçeneklerinin bitişi ve senaryolar sitede HİÇ görünmüyordu; gerçek
katalogda da tek bir "dış önşart" (planlarda olmayan ders) iki programın
bitişini birden "hesaplanamadı" yapıyordu.
"""
import pathlib
import sqlite3
import sys
from html.parser import HTMLParser
from pathlib import Path

from itucap import config
from itucap import db
from itucap import ui as UI

KOK = Path(UI.__file__).resolve().parents[2]
sys.path.insert(0, str(KOK / "tools"))
import site_kur  # noqa: E402

KAYNAK = pathlib.Path(UI.__file__).read_text(encoding="utf-8")


class _Etiketler(HTMLParser):
    """Tarayıcının GERÇEKTEN etiket saydıklarını topla (<style>/<script> içi metin)."""

    def __init__(self):
        super().__init__()
        self.betikler, self.idler, self.yigin = [], set(), []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "script" and a.get("src"):
            self.betikler.append((a["src"], list(self.yigin)))
        if a.get("id"):
            self.idler.add(a["id"])
        if tag not in ("meta", "link", "br", "img", "input", "hr", "source"):
            self.yigin.append(tag)

    def handle_endtag(self, tag):
        if tag in self.yigin:
            while self.yigin and self.yigin.pop() != tag:
                pass


def test_APP_JS_GERCEK_ETIKET_ve_BODY_icinde():
    p = _Etiketler()
    p.feed(site_kur.kabuk(UI))
    app = [(src, yol) for src, yol in p.betikler if src == "./app.js"]
    assert len(app) == 1, f"app.js etiket olarak {len(app)} kez var — yükleyici çalışmaz"
    yol = app[0][1]
    assert "body" in yol and "style" not in yol, yol
    assert "yukleniyor" in p.idler, "yükleyici öğesi etiket değil (metin içinde kalmış)"


def test_SABLONDA_BODY_METNI_TEK():
    """Yorumdaki bir "<body>" yeniden aynı hatayı üretmesin."""
    sablon = UI.render({}, deferred=True, fontlar_sonda=True)
    assert sablon.count("<body>") == 1
    assert sablon.count("</head>\n<body>") == 1


def test_KABUK_sinir_BOZULURSA_KURULUM_DURUR(monkeypatch):
    gercek = UI.render
    monkeypatch.setattr(UI, "render", lambda *a, **k: gercek(*a, **k).replace(
        "</head>\n<body>", "</head>\n  <body>"))
    try:
        site_kur.kabuk(UI)
    except SystemExit as e:
        assert "sınırı tek değil" in str(e)
    else:
        raise AssertionError("bozuk şablonla site sessizce kuruldu")


def _katalog(tmp_path, donemler):
    con = db.connect(tmp_path / "ref.sqlite3", "schema.sql")
    for i, d in enumerate(donemler):
        con.execute("INSERT INTO lesson(crn,term,course_code) VALUES (?,?,'X 1')", (str(i), d))
    con.commit()
    return con


def test_DONEM_ayardan_yoksa_KATALOGDAN_ama_UYDURMADAN(tmp_path):
    s = config.Settings()
    s.term = ""
    assert UI._aktif_donem(_katalog(tmp_path / "a", ["202610", "202610"]), s) == "202610"
    # İki dönem karışıksa ya da hiç yoksa: bilinmiyor.
    assert UI._aktif_donem(_katalog(tmp_path / "b", ["202610", "202620"]), s) == ""
    assert UI._aktif_donem(_katalog(tmp_path / "c", []), s) == ""
    s.term = "202520"
    assert UI._aktif_donem(_katalog(tmp_path / "d", ["202610"]), s) == "202520"
    i = KAYNAK.index("def _yol_haritasi(")
    k = KAYNAK[i:KAYNAK.index("\ndef ", i + 1)]
    assert "term = _aktif_donem(con, settings)" in k
    j = KAYNAK.index("def _harita_girdisi(")
    g = KAYNAK[j:KAYNAK.index("\ndef ", j + 1)]
    assert "term = _aktif_donem(con, settings)" in g
