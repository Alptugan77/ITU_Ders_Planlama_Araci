# Faz 84 — gerçek sitede 1. dönem öğrencisi

Kullanıcı 24.09.2026: *"geliştirmelere devam et ve sonrasında pr oluştur"*.

Site gerçek katalogla kuruldu (`tools/site_kur.py`). Senaryo: KMM, ikinci
program yok, **1. dönem**, hiç ders girilmemiş. Faz 79'daki son sınıf
gezisinin öbür ucu.

## Bulunanlar

### 1. Başvuruda boş onay — düzeltildi

Başvuru bölümü şunu yazıyordu:

> ✓ **Çift anadal** denetlenebilen şartlar sağlanmaktadır · 3 şart bu araçla denetlenemez

Transkript yokken şartların **hiçbiri** değerlendirilemiyor: GNO yok, kredi
yok, sıralama zaten hiç bilinmiyor. `eligible` "düşen şart yok" demek ve
şartların hepsi bilinmediğinde bu boş bir doğru. Ekrana yeşil onay olarak
basılıyordu; 1. dönem öğrencisi ÇAP'a başvurabileceğini sanabilirdi.

Şimdi:

- Özet satırı: işaret nötr **—**, metin *"şartlar değerlendirilememektedir
  (başarılan dersler girilmemiştir)"*.
- Kredi penceresi bilinmiyor ama beyan edilen dönem 3'ten küçükse bir bilgi
  notu: *"başvuru penceresi genellikle 3. yarıyıldan (30 kredi) itibaren
  açılır; şu an 1. dönemdesiniz"*. ✗ değil, çünkü intibak/yatay geçiş
  öğrencisinin kredisi dönemden fazla olabilir.
- Pencerenin kararı: *"Şartların hiçbiri değerlendirilememektedir."*

Transkriptli öğrencide davranış aynı (en az bir şart biliniyorsa eski metin).

### 2. "0 alttan (1–0. dönem)" — düzeltildi

Kip notu 1. dönemde alttan bölümünü atlıyor.

### 3. İncelenip hata olmadığı görülen

İlk gezide öneride FIZ 102E, KMM 211 gibi üst dönem dersleri çıktı. Neden:
gezi betiği dönemi doğrudan API'yle ayarlıyor ve sayfanın *varsayılan kip*
bayrağını geçmiyordu; sayfa önceki kipte (DEPAR, tüm plan) kaldı. Arayüzden
dönem seçildiğinde "1. dönem + alttan" kipi açılıyor ve öneri yalnız 1.
dönem derslerinden oluşuyor (8 ders, 18 kredi). DEPAR'da üst dönem dersinin
çıkması o kipin tanımı; önşart verisi katalogda bu derslerde yok
("ÖNŞART BİLGİSİ YOK" rozeti bunu söylüyor).

## Testler

`tests/test_faz84_ilk_donem.py` — kip notu birim testi ve vitrinde
transkriptsiz 1. dönem durumu (özet satırı, işaretler, pencere). Geri alma
deneyi: iki kural geri alınınca iki test de kırmızı.
