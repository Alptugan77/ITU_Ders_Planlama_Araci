"""Güvenlik gerilemesi — penetrasyon testinde bulunanlar (27.08.2026).

Bu dosya bir kez düzeltilen açığın geri gelmemesini kolluyor. Her test bir
SALDIRIYI temsil ediyor, "şuna dikkat" notu değil.
"""
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import pytest

from itucap import ui as UI


# ============================================================ 1. gömülü XSS
def test_JSON_script_baglamindan_KACAMIYOR():
    """★★ DOĞRULANMIŞ AÇIK: `json.dumps` `</script>`'i kaçırmıyor; DATA
    doğrudan `<script>` içine gömüldüğü için kullanıcı metnindeki
    `</script>` script'i erken kapatıp HTML enjekte ediyordu."""
    kotu = {"x": "</script><script>window.__XSS__=1</script>"}
    gomulu = UI._gomulu_json(kotu)
    assert "</script>" not in gomulu
    assert "<" not in gomulu and ">" not in gomulu
    # `<` ve `>` kaçışlı hâlleriyle var.
    assert "\\u003c" in gomulu and "\\u003e" in gomulu


def test_kacis_KAYIPSIZ():
    """⚠️ Kaçış değeri değiştirmemeli: `<`,`>`,`&` JSON'da yalnız string
    içinde geçer, `\\u` kaçışı JSON.parse'ta aynı nesneyi verir."""
    ornek = {"note": "</script> & <b>x</b>   satır", "n": 3.5,
             "l": [1, "<a>", None], "ic": {"k": "v>w & z"}}
    assert json.loads(UI._gomulu_json(ornek)) == ornek


def test_satir_ayiriclari_da_kacisli():
    """U+2028/U+2029 JS'te satır sonu sayılır ve string'i bozabilir; JSON'da
    ham geçerlerdi."""
    gomulu = UI._gomulu_json({"x": "a b c"})
    assert " " not in gomulu and " " not in gomulu


def test_render_ciktisinda_ham_kapanis_etiketi_yok():
    """Sayfanın tamamında: hangi alandan gelirse gelsin `</script>` yalnız
    GERÇEK script kapanışları olmalı, veri içinde değil."""
    data = {"schedules": [], "candidates": [],
            "busy": [{"label": "</script><script>alert(1)</script>",
                      "day": 1, "start": 600, "end": 700, "raw": "x"}]}
    html = UI.render(data)
    # DATA bloğundaki gömülü değerde kapanış etiketi olmamalı.
    blok = html.split("const DATA = ")[1].split(";\n")[0]
    assert "</script>" not in blok
    assert "alert(1)" in blok        # veri KAYBOLMADI, yalnız kaçtı


# ====================================== 2. TARAYICIDA gerçekten çalışmıyor
def _canli_xss_denemesi(tmp_path: Path) -> str | None:
    """Meşgul etiketine script enjekte et, sayfayı aç, çalıştı mı bak.
    Dönen: enjekte script çalıştıysa değer, çalışmadıysa None."""
    if not shutil.which("node"):        # playwright yoksa atla
        pytest.skip("node/playwright yok")
    try:
        import playwright  # noqa: F401
    except ImportError:
        pytest.skip("playwright yok")

    betik = tempfile.NamedTemporaryFile("w", suffix=".py", delete=False,
                                        dir=str(tmp_path))
    betik.write(_CANLI_BETIK)
    betik.close()
    r = subprocess.run([sys.executable, betik.name], capture_output=True,
                       text=True, timeout=120)
    return r.stdout.strip().splitlines()[-1] if r.returncode == 0 else \
        pytest.fail(r.stderr[-800:])


_CANLI_BETIK = '''
import sys, tempfile, threading, time
from pathlib import Path
sys.path.insert(0, "SRC_YOLU".replace("SRC_YOLU", __import__("os").environ.get("ITUCAP_SRC", "src")))
_T = Path(tempfile.mkdtemp()); (_T/"config").mkdir(); (_T/"data").mkdir()
(_T/"config"/"settings.toml").write_text('[student]\\nanadal_program="HTAE"\\nsecond_kind="yok"\\n', encoding="utf-8")
import itucap.config as config
config.ROOT=_T; config.DATA_DIR=_T/"data"
config.REF_DB=_T/"data"/"reference.sqlite3"; config.USER_DB=_T/"data"/"user.sqlite3"
from itucap import db
con=db.connect(config.REF_DB,"schema.sql")
con.execute("INSERT INTO program(code,name,level) VALUES ('HTAE','H','LS')")
con.execute("INSERT INTO course(code,name,credits,ects) VALUES ('MAT 103E','C',4,6)")
con.execute("INSERT INTO plan(id,program_code,plan_type,title,source) VALUES (1,'HTAE','lisans','x','obs')")
con.commit(); con.close(); db.connect(config.USER_DB,"schema_user.sql").close()
from itucap import server
st=server.State(label="ben")
st.dispatch("/api/mesgul", {"day":1,"start":600,"end":700,
    "label":"</script><script>window.__XSS__=1</script>"})
h=server.build(st,host="127.0.0.1",port=0); P=h.server_address[1]
threading.Thread(target=h.serve_forever,daemon=True).start(); time.sleep(0.4)
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page()
    pg.goto(f"http://127.0.0.1:{P}/", wait_until="load", timeout=30000)
    pg.wait_for_timeout(600)
    print(pg.evaluate("window.__XSS__ || 'GUVENLI'"))
    b.close()
h.shutdown()
'''


def test_XSS_tarayicida_CALISMIYOR(tmp_path, monkeypatch):
    """★★ Asıl kanıt: enjekte script gerçek tarayıcıda ÇALIŞMAMALI."""
    import os
    monkeypatch.setenv("ITUCAP_SRC",
                       str(Path(UI.__file__).resolve().parents[1]))
    sonuc = _canli_xss_denemesi(tmp_path)
    assert sonuc == "GUVENLI", f"XSS çalıştı: {sonuc!r}"


# ============================================== 3. TOML yazıcı enjeksiyonu
def test_toml_yazici_ANAHTAR_ENJEKSIYONUNA_dayanikli():
    """★★ `_toml_value` eskiden satır sonu kaçmıyordu; bir `\\n` GEÇERLİ ama
    başka anahtar taşıyan bir TOML satırı üretebilirdi. Yazıcı KENDİ BAŞINA
    güvenli olmalı — "çağıran zaten temizliyor" sessiz bir varsayım."""
    import tomllib

    from itucap import config

    kotu = 'x"\nmax_load = 9999\ny = "'
    satir = f"mesgul = [{config._toml_value(kotu)}]"
    ayar = tomllib.loads(satir)
    assert list(ayar) == ["mesgul"], "başka anahtar enjekte oldu"
    assert ayar["mesgul"][0] == kotu, "değer bozuldu"


def test_toml_yazici_kontrol_karakterleri(tmp_path, monkeypatch):
    """Tam yazma-okuma turu: kontrol karakterli değer dosyayı bozmamalı."""
    import tomllib

    from itucap import config

    monkeypatch.setattr(config, "ROOT", tmp_path)
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "settings.toml").write_text(
        '[student]\nanadal_program="HTAE"\n', encoding="utf-8")
    # watch_courses serbest listeye en yakın _EDITABLE alan.
    config.update_settings({"watch_courses": ["OK 101", "kö\ntü\ttab"]})
    metin = (tmp_path / "config" / "settings.toml").read_text(encoding="utf-8")
    ayar = tomllib.loads(metin)          # bozuksa burada patlar
    assert ayar["student"]["watch_courses"] == ["OK 101", "kö\ntü\ttab"]
