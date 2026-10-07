"""Faz 131 — üç ekran aynı soruya aynı cevabı versin.

Kullanıcının verisiyle (HTAE + BLG ÇAP) gezilirken bulundu:

1. **Kademeler "bu dönem alınabilir" diyordu, Engeller "bu dönem
   açılmamış".** Kademedeki READY yalnız önşarta bakıyordu; BLG 102E,
   BLG 202E, BLG 311E kehribar boyanıyordu. Artık önşartı tamam ama arz
   engeli olan ders ayrı durumda (READY_KAPALI), engelin etiketiyle.
2. **Öneri motoru BLG 223E'yi programa koyuyordu, Kademeler aynı dersi
   "önce BLG 102E" diye BEKLİYOR gösteriyordu.** Önşart bir denklikle
   sağlanıyordu; `plan_sequence` ham notla çalışıyordu. Artık denklikler
   (öneri motoru ve ilerleme paneliyle aynı) uygulanıyor.
3. **Engel metni "… açık ve dilekçesiz alınabilir" diye bitiyordu** —
   önşartı EKSİK denk ders için. "Alınabilir" şimdi alınabilir diye
   okunuyordu (bkz. `test_faz120_denk_engel`).
"""
import json
import pathlib
import shutil
import subprocess

import pytest

from itucap import rules as R, sequence, ui as UI
from test_sequence import con, no_real_waivers  # noqa: F401  (fixture)

K = pathlib.Path(UI.__file__).read_text(encoding="utf-8")


def _denk(hedef="BLG 102E", kaynak="BIL 105E"):
    return [R.Equivalence(id=1, target=hedef, sources=((kaynak, "DD"),),
                          confidence="official", applies_to_cap=True)]


def test_SIRA_denklikle_saglanan_onsart(con):  # noqa: F811
    notlar = {"BIL 105E": "BB"}
    ham = {s.course: s.status for s in sequence.plan_sequence(con, 1, notlar)}
    assert ham["BLG 102E"] == "READY" and ham["BLG 223E"] == "PENDING"
    denk = {s.course: s.status for s in sequence.plan_sequence(con, 1, notlar, _denk())}
    # Denklikle BLG 102E yuvası dolu (ilerleme paneliyle aynı hüküm) ve
    # BLG 223E'nin önşartı sağlanmış.
    assert denk["BLG 102E"] == "DONE"
    assert denk["BLG 223E"] == "READY"
    assert denk["BLG 335E"] == "PENDING"
    # Kademe (yapı) denklikten etkilenmiyor.
    assert ({s.course: s.tier for s in sequence.plan_sequence(con, 1, notlar, _denk())}
            == {s.course: s.tier for s in sequence.plan_sequence(con, 1, notlar)})


def test_SIRA_denklik_yoksa_eski_davranis(con):  # noqa: F811
    notlar = {"BLG 102E": "CC"}
    assert ([(s.course, s.status) for s in sequence.plan_sequence(con, 1, notlar)]
            == [(s.course, s.status) for s in sequence.plan_sequence(con, 1, notlar, [])])


def test_CAGIRANLAR_denklik_geciyor():
    kok = pathlib.Path(UI.__file__).parent
    assert "SEQ.plan_sequence(con, pid, grades, equivalences)" in (kok / "recommend.py").read_text(encoding="utf-8")
    assert "SEQ.plan_sequence(con, plan_id, grades, equivalences)" in K
    assert "R.load_equivalences(con, ucon=ucon))" in (kok / "progress.py").read_text(encoding="utf-8")


def _kademe(durum, engeller):
    node = shutil.which("node")
    if not node:
        pytest.skip("node yok")
    i = K.index("const LABELS = {")
    labels = K[i:K.index("};", i) + 2]
    j = K.index("const KADEME_ARZ_ENGELI")
    fn = K[j:K.index("\n}\n", K.index("function kademeDurumu(", j)) + 3]
    betik = (f"const DATA = {{blockers: {json.dumps(engeller)}}};\n{labels}\n{fn}\n"
             f"console.log(JSON.stringify(kademeDurumu({json.dumps(durum)})));")
    r = subprocess.run([node, "-e", betik], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_KADEME_arz_engeli_alinabilir_gostermiyor():
    engel = [{"course": "BLG 102E", "reason": "ACILMAMIS"},
             {"course": "BLG 322E", "reason": "EK_SINAV"},
             {"course": "BLG 335E", "reason": "ONSART"}]
    assert _kademe({"course": "BLG 102E", "status": "READY"}, engel) == {
        "s": "READY_KAPALI", "not": "bu dönem açılmamış"}
    assert _kademe({"course": "BLG 322E", "status": "READY"}, engel)["not"] == "yalnız ek sınav açılmış"
    # Önşart engeli arz değil: READY'ye dokunmuyor (zaten READY olmaz).
    assert _kademe({"course": "BLG 335E", "status": "READY"}, engel)["s"] == "READY"
    assert _kademe({"course": "BLG 212E", "status": "READY"}, engel) == {"s": "READY", "not": ""}
    assert _kademe({"course": "BLG 102E", "status": "DONE"}, engel)["s"] == "DONE"
    assert _kademe({"course": "X", "status": "READY"}, [])["s"] == "READY"


def test_KADEME_gorunum_ve_efsane():
    assert '<li data-s="${kd.s}"' in K
    assert '<span class="tkapali">önşartı tamam · ${esc(kd.not)}</span>' in K
    assert '<span><i class="kapali"></i> önşartı tamam, bu dönem alınamaz</span>' in K
    assert '.tier li[data-s="READY_KAPALI"]{' in K
    # "Alınabilir" dolgusu yalnız gerçekten alınabilir olanda.
    assert '.tier li[data-s="READY"]{background:var(--cap-soft)' in K


def test_TELEFON_kademe_karti_tam_genislik():
    """`.tier li{width:100%}` telefon kuralı, kaynakta sonra gelen aynı
    özgüllükteki temel `width:196px` yüzünden ÖLÜYDÜ (ölçüldü: 196/332px)."""
    j = K.index(".tier ul>li{width:100%}")
    i = K.rindex("@media", 0, j)
    assert K[i:].startswith("@media (max-width:700px){")
    assert "\n  .tier li{width:100%}" not in K, "ölü kural geri geldi"
    temel = K.index(".tier li{font-size:var(--fs-sm);")
    assert "width:196px" in K[temel:temel + 300]
