"""Faz 23 — veri kalitesi: uyarılar EYLEME DÖNÜK olsun (yapılacaklar §3).

`make refresh` dokuz uyarı basıyordu ve üçü yanlış alarmdı. Yanlış alarm veren
bir uyarı okunmaz hâle gelir; okunmayan uyarı da hiç olmamış gibidir. Bu faz
uyarıları düzeltmiyor — **doğru şeyi söylemelerini** sağlıyor.

Gerçek katalogda ölçülenler (23.08.2026, 6962 havuz slotu · 1215 plan):

| Uyarı | Önce | Sonra | Neden |
|---|---|---|---|
| kategori eşlenemedi | 1236 slot | **26** | 1210'unda kaynakta kategori YOK |
| kredi tutmuyor | 65 plan | (aralık) | kredi tek sayı değil, ARALIK |
| boş havuz "PARSE HATASI" | 11 | sebebiyle | OBS tablosuz sayfa döndürüyor |
"""
import pytest


@pytest.fixture(autouse=True)
def no_real_waivers(monkeypatch, tmp_path):
    from itucap import declared
    monkeypatch.setattr(declared, "DEFAULT_PATH", tmp_path / "yok.toml")


from itucap import db, quality
from itucap import normalize as N


@pytest.fixture()
def con(tmp_path, monkeypatch):
    from itucap import config
    monkeypatch.setattr(config, "REF_DB", tmp_path / "r.sqlite3")
    c = db.connect(tmp_path / "r.sqlite3", "schema.sql")
    N.unmatched_labels.clear()
    N.uncategorised_labels.clear()
    return c


def _plan(con, plan_id, ilan, slots):
    """slots: [(credits, credits_min, credits_max)]"""
    con.execute("""INSERT INTO plan(id,program_code,plan_type,title,source,declared_credits)
                   VALUES (?,'BLG','cap','p','obs',?)""", (plan_id, ilan))
    for i, (kr, lo, hi) in enumerate(slots):
        con.execute("""INSERT INTO plan_slot(plan_id,slot_kind,course_code,credits,
                                             credits_min,credits_max,position)
                       VALUES (?,'REQUIRED',?,?,?,?,?)""",
                    (plan_id, f"XXX {100+i}", kr, lo, hi, i))
    con.commit()


# --------------------------------------------------- kredi ARALIĞI karşılaştırma
def test_aralikli_kredi_YANLIS_ALARM_uretmiyor(con):
    """★ Asıl düzeltme. Havuz kredisi '2 / 2,5 / 3' olabiliyor; tek sayı gibi
    toplayınca 65 planda sahte 'tutmuyor' çıkıyordu."""
    _plan(con, 1, 8.0, [(3.0, 3.0, 3.0), (None, 2.0, 3.0), (None, 2.0, 3.0)])
    assert quality._plan_credit_mismatch(con) is None      # 7–9 aralığı, ilan 8


def test_aralik_disinda_kalan_HALA_yakalaniyor(con):
    """Kontrolün körelmediğinin kanıtı: ilan aralığın dışındaysa uyarı var."""
    _plan(con, 2, 30.0, [(3.0, 3.0, 3.0), (None, 2.0, 3.0)])
    detay = quality._plan_credit_mismatch(con)
    assert detay and "2" in detay


def test_aralik_ARALIK_olarak_yaziliyor(con):
    """Rapor '5–6 kredi topladık' demeli; tek sayı yazmak uydurma olurdu."""
    _plan(con, 3, 40.0, [(None, 2.0, 3.0), (None, 3.0, 3.0)])
    detay = quality._plan_credit_mismatch(con)
    assert "5–6 kredi" in detay


def test_tek_degerde_tire_YOK(con):
    _plan(con, 4, 40.0, [(3.0, 3.0, 3.0)])
    assert "3 kredi topladık" in quality._plan_credit_mismatch(con)


def test_ilan_yoksa_KARSILASTIRMA_YOK(con):
    """★ Bilinmeyeni 0 sayıp 'tutmuyor' demek, olmayan bir hata uydurmaktı."""
    con.execute("""INSERT INTO plan(id,program_code,plan_type,title,source)
                   VALUES (9,'BLG','cap','p','obs')""")
    con.execute("""INSERT INTO plan_slot(plan_id,slot_kind,course_code,credits,position)
                   VALUES (9,'REQUIRED','XXX 101',3.0,0)""")
    con.commit()
    assert quality._plan_credit_mismatch(con) is None


# ------------------------------------------------- etiket uyarısının kapsamı
def test_kaynakta_kategori_olmayan_UYARI_DEGIL(con):
    """★ 1210 slotu 'düzeltilmesi gereken hata' diye göstermek, uyarıyı
    okunmaz yapıyordu. Kategori uydurmak da veri uydurmak olurdu."""
    for etiket in ("Stüdyo IV", "Temel Meslek II", "Selective"):
        N.normalize_pool_label(etiket)
    assert quality._unmatched(con) is None            # hata sayılmıyor
    bilgi = quality._uncategorised(con)
    assert bilgi and "kaynakta kategori yok" in bilgi


def test_kategori_tasiyip_cozulemeyen_UYARI(con):
    N.normalize_pool_label("Seçmeli MT Ders")
    detay = quality._unmatched(con)
    assert detay and "kategori KODU taşıyor" in detay


def test_iki_uyari_AYRI_sayiyor(con):
    N.normalize_pool_label("Stüdyo IV")
    N.normalize_pool_label("Seçmeli MT Ders")
    assert "1 havuz etiketi" in quality._unmatched(con)
    assert "1 havuz etiketinde" in quality._uncategorised(con)


# ----------------------------------------------- boş havuzun SEBEBİ yazıyor
def _havuz(con, plan_id, slot_id, durum):
    con.execute("""INSERT OR IGNORE INTO plan(id,program_code,plan_type,title,source)
                   VALUES (?,'BLG','cap','p','obs')""", (plan_id,))
    con.execute("""INSERT INTO plan_slot(id,plan_id,slot_kind,pool_label_raw,
                                         pool_group_id,pool_status,position)
                   VALUES (?,?,'ELECTIVE_POOL','havuz','999',?,0)""",
                (slot_id, plan_id, durum))
    con.commit()


def test_kaynakta_bos_havuz_PARSE_HATASI_DEMIYOR(con):
    """★ Kaynağın eksiğini kendi hatamız gibi göstermek, düzeltilmesi en zor
    yalan türü. Grup 11083'ün arşivlenmiş cevabında hiç <table> yok."""
    _havuz(con, 11, 101, "no_table")
    detay = quality._empty_pool(con)
    assert "kaynakta boş" in detay
    assert "PARSE HATASI" not in detay


def test_gercek_parse_hatasi_HALA_soyleniyor(con):
    _havuz(con, 12, 102, "no_codes")
    detay = quality._empty_pool(con)
    assert "PARSE HATASI" in detay and "tablo VARDI" in detay


def test_sebebi_bilinmeyen_ESKI_kayit_ayri(con):
    """Bu tarayıcı sürümünden önce çekilmiş slotlar için sebep yok —
    'bilmiyorum' demek, yanlış sebep uydurmaktan iyidir."""
    _havuz(con, 13, 103, None)
    detay = quality._empty_pool(con)
    assert "sebep kaydedilmemiş" in detay


def test_bos_havuz_yoksa_uyari_yok(con):
    con.execute("""INSERT INTO plan(id,program_code,plan_type,title,source)
                   VALUES (14,'BLG','cap','p','obs')""")
    cur = con.execute("""INSERT INTO plan_slot(plan_id,slot_kind,pool_label_raw,
                                               pool_group_id,pool_status,position)
                         VALUES (14,'ELECTIVE_POOL','havuz','999','ok',0)""")
    con.execute("INSERT INTO pool_option(slot_id,course_code) VALUES (?,'XXX 101')",
                (cur.lastrowid,))
    con.commit()
    assert quality._empty_pool(con) is None
