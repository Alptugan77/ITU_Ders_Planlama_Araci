"""Faz 125 — ÇAP dersinin açıldığı yarıyıl takma adıyla da aranıyor.

Kullanıcının verisinde (HTAE + BLG ÇAP, 29.09.2026) BLG ÇAP planı eski kodu
(BLG 317E, BLG 311E) yazıyor; BLG'nin güncel lisans planı yeni kodu (BBF 302E
…). Mevsim plandan bulunamıyor, geçmişten tahmin ediliyor ya da "her dönem
açılır" varsayılıyordu. Resmî denklik / kod göçü / dil eşiyle (`takma_adlar`)
aranıyor. 383 gerçek çiftte planlanan ÇAP derslerinde: geçmişten tahmin
740 → 342, bilinmeyen 627 → 414.
"""
from itucap import rules as R
from test_faz57_yol_haritasi import ANADAL, CAP, _katalog, _kur


def _cat(tmp_path):
    con = _katalog(tmp_path, [("AAA 101", 3, None), ("BBB 317E", 3, None), ("BBB 302E", 3, None)],
                   [("AAA 101", 5)], cap=["BBB 317E"])
    # BBB'nin LİSANS planı yeni kodu 6. dönemde (Bahar) yazıyor.
    con.execute("INSERT INTO plan(id,program_code,plan_type,title,source) VALUES (3,'BBB','lisans','l','obs')")
    con.execute("INSERT INTO plan_slot(plan_id,slot_kind,course_code,credits,position,term_no) "
                "VALUES (3,'REQUIRED','BBB 302E',3,0,6)")
    con.commit()
    return con


def _mevsim(h, kod):
    return next((i["season"], i["seasonSource"]) for t in h["terms"] for i in t["items"]
                if i["course"] == kod)


def test_DENKLIKLE_lisans_planindan(tmp_path):
    con = _cat(tmp_path)
    # Gerçek veride olduğu gibi iki yönlü (BLG 317 ↔ BBF 302).
    esd = [R.Equivalence(1, "BBB 317", (("BBB 302", "DD"),), "official", True),
           R.Equivalence(2, "BBB 302", (("BBB 317", "DD"),), "official", True)]
    h = _kur(con, planlar=ANADAL + CAP, equivalences=esd)
    assert _mevsim(h, "BBB 317E") == ("20", "lisans")
    h = _kur(con, planlar=ANADAL + CAP)                      # denklik yoksa bilinmiyor
    assert _mevsim(h, "BBB 317E") == (None, "")
