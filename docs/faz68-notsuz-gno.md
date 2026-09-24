# Faz 68 — Notu girilmemiş ders GNO'ya DD olarak girmiyor

*24.09.2026 · kullanıcı: "can you continue on your improvements and create a
pr afterwards".*

Site gerçek katalogla kuruldu ve bu kez **ÇAP'lı** bir öğrenciyle gezildi:
BLG anadal + EHB ÇAP, 5. yarıyıl, ÇAP'a 5. yarıyılda başlamış; dersler
"Plandan işaretle" ile girildi (önerilen 26 tik, notlar "bilmiyorum").

Testler **1313 → 1318** (+5, `tests/test_faz68_notsuz_gno.py`), 4 atlandı. Geri alma deneyi: beş
kuralın **beşi** kırmızı (ilk denemede biri yeşil kaldı — başvuru taramasının
kendisi test edilmiyordu; test eklendi).

## Bulunan hata (ölçüldü)

Notu girilmemiş 26 ders GNO'ya **DD** olarak girdi. Ekranda:

* **GNO 1.00**; "ÇAP'a devam ✗", "ÇAP mezuniyeti ✗", "Mezuniyet ✗";
* kredi sınırı GNO 1.00'dan **22** (genel sınır) — öneriler buna göre;
* GNO hedefi: "bu dönem yeterli değil — tüm dersler AA olsa bile 1.46";
* başvuru penceresi: "ÇAP başvurusu · GNO 1.00 / gereken 3.00 ✗".

Hiçbiri ölçülmüş değildi. Plandan işaretleme, sitede ders girmenin en kolay
yolu; yani bu, yeni öğrencilerin çoğunun göreceği ekrandı.

## Düzeltme

* `policy.gpa`: notu bilinmeyen ders **ortalamaya girmiyor**; `uncertain`
  listesinde raporlanıyor. GNO yalnız notu bilinen derslerden.
  ⚠️ **Önşart** denetiminde DD varsayımı aynen duruyor (en kötü durum:
  "MIN CC" yanlışlıkla sağlanmaz) — test bunu da denetliyor.
* Hiç harf notu yoksa (`counted == 0`) GNO **bilinmiyor**:
  * GNO eşikleri ✗ değil **—** ("Harf notu girilmiş ders bulunmadığından GNO
    bilinmemektedir");
  * başvuru: GNO şartı "—", **kredi penceresi yine değerlendiriliyor**
    (başarılan kredi biliniyor);
  * kredi sınırı: "harf notu girilmedi; en düşük band varsayıldı" + açıklama
    + **Transkript yapıştır** düğmesi; başlıkta "dönem yükü sınırı: harf
    notları girilince"; kayıt kontrolünde "—".
* Kısmen notlu transkriptte: "Notu girilmemiş N ders ortalamaya katılmadı;
  GNO yalnızca notu bilinen derslerden hesaplanmıştır".
* ⚠️ İki durum AYRI tutuldu: `load.noTranscript` = hiç ders girilmemiş
  (ilerleme de bilinmiyor), `load.noGrades` = dersler var, not yok (yalnız
  GNO bilinmiyor). İlk denemede ikisi aynı bayraktaydı; ilerleme panelleri
  notsuz girişte "İlerleme bilinmiyor" diyecekti.

**Gerçek sitede ölçüldü (düzeltme sonrası):** aynı öğrenci — kredi bölümü
"GNO bilinmemektedir … Transkript yapıştır", başvuru "— ÇAP başvurusu: Harf
notu girilmiş ders bulunmadığından … Gereken: 3.00", kredi penceresi ✓.
