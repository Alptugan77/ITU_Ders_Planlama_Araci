# Faz 104 — Gerçek katalog gezisi: BBF kod göçü ve ilan edilmemiş şubeler

Kullanıcının "continue" isteği üzerine son özellikler (ilerleme şeridi,
dönem zorluğu, hafifletme, kaydedilen sekmesi) gerçek katalogla, BLGE +
EHB ÇAP profiliyle gezildi. Yeni özellikler doğru çalıştı; gezi iki eski
hata buldu.

## 1. Kod göçü: BLG 252E → BBF 203E

### Belirti
BLGE 5. yarıyıl + EHB ÇAP öğrencisine en iyi öneri **22 kredilik sınırın
11'i** idi. 5. dönemin iki ana dersi (BBF 301E, BBF 302E) önşart yüzünden
engelliydi: "eksik: BLG 252, BLG 252E, YZV 201E…".

### Sebep
BLGE 2024-2025 planı BLG kodlarını BBF'ye taşımış. BBF 203E "Object Oriented
Programming" ile BLG 252E'nin adı, kredisi (3), AKTS'si (5) ve önşart metni
birebir aynı. Resmî plan BBF 203E'yi 4., onu isteyen BBF 301E'yi 5. döneme
koyuyor. Ancak BBF 301E'nin önşart metni hâlâ eski kodu (BLG 252E) istiyor.
Yeni planla okuyan her BLGE öğrencisi bu yüzden engelleniyordu.

### Ölçüm (`fikirler.md` §1.1 ve F.4'ün ilk ölçümü)
Aynı ad, kredi ve AKTS'ye sahip, farklı önekli kod çiftleri arandı. Yalnız
**fiilen engel yaratanlar** sayıldı: yeni kodun olduğu, eski kodun olmadığı
bir planda eski kodu önşartında isteyen ve yeni kodu kabul etmeyen bir ders
olmalı. Sonuç 18 çift. Beyan edilenler yalnız kanıtı tartışmasız olanlar,
yani BBF göçü:

| Eski | Yeni | Kanıt | Engellediği |
|---|---|---|---|
| BLG 252E | BBF 203E | ad, kredi, AKTS, önşart birebir | BBF 301E, BBF 302E, BLG 411E |
| BLG 336E | BBF 303E | ad, kredi, AKTS, önşart birebir | BLG 417E, BLG 4901E |
| BLG 454E | BBF 304E | ad, kredi, AKTS, önşart birebir | YZV 411E |
| BLG 112E | BBF 103E | ad, kredi, AKTS; ikisi de önşartsız | BBF 204E |

**Beyan edilmeyenler** (farklı bölümlerin aynı adlı dersleri, göç değil):
ELE/ELH/EHB 222 "Elektroniğe Giriş", FIZ 106E/FIZ 102E, KON 214/KON 301E,
ECN 105E/ECN 101E, MIM→ARC, ISL→MMD gibi. Bunlar için beyan, OBS'nin kabul
edip etmediği bilinmeden "aynı ders" iddiası olurdu.

### Değişiklik
* **`config/katalog-duzeltmeleri.toml` → `[[kod_gocu]]`:** dört beyan, her
  birinin kanıtı `not_` alanında.
* **`declared.load_code_migrations`:** dosya değiştikçe yeniden okunuyor
  (mtime önbelleği; `prereq_view` sık çağrılıyor).
* **`rules.prereq_view`:** yeni kodu geçen, eski kodu isteyen önşartı
  karşılar; tersi de geçerli. İkisi de varsa iyi not alınır (eski kodla FF,
  yeni kodla CB). Etkisi yalnız önşartta: plan slotu doldurmaz, ilerlemeyi
  değiştirmez; muafiyetlerle aynı ilke. Öneri, engeller, sıralama ve yol
  haritası hep bu görünümden geçtiği için düzeltme hepsine ulaşıyor.
* **Yol haritası:** göç hedefi plandaysa eski kod "dış önşart" sayılmıyor
  (Faz 98'deki dil eşi kuralının kardeşi). Aksi hâlde geçilmiş varsayılıp
  BBF 301E, BBF 203E'den önceki döneme yerleşebiliyordu.
* **Engel metni:** "eksik: BLG 252E (yeni kodu BBF 203E)". Öğrenci planında
  eski kodu değil yeni kodu görüyor.

### Etki (gerçek katalog, aynı gezi)
* Öneriler 11 / 14 / 14 krediden **17 / 20 / 20**'ye çıktı; BBF 301E ve
  BBF 302E programda.
* Yol haritasında anadalın "dış önşartı varsayıldı" sayısı **8'den 4'e** indi.
  Bitiş dönemi değişmedi (bu öğrenciyi ÇAP bağlıyor).

## 2. "-" bir program kodu değil: ilan edilmemiş şube

### Belirti
"Alınamayan dersler" BLG 322E ve BLG 354E için şunu yazıyordu: *"1 şube
bulunmaktadır; yalnızca - alabilir"*.

### Sebep
Kaynak, alabilecek programları ilan edilmemiş şubeye "-" yazıyor. 2026 Güz'de
3807 şubenin 70'i böyle; 68'inde kontenjan 0, hoca ve bina "-", yalnız
3'ünde saat var. Motor bunları "başka programlara ayrılmış" (PROGRAMA_KAPALI)
sayıyordu, arz uyarısında da ders yanlış gruba düşüyordu.

### Değişiklik (`recommend.cap_blockers`)
* **Bütün şubeleri "-" olan ders:** ACILMAMIS, "N şube listelenmiş, ancak
  saati, kontenjanı ve alabilecek programlar henüz ilan edilmemiştir".
  Gerçek katalogda 58 ders.
* **İlanlı şubesi de olan ders:** PROGRAMA_KAPALI kalıyor ama "-" yazılmıyor.
  Gerçek katalogda 6 ders.
* Şube yüklemesi değişmedi: "-" şubesi zaten kimseye önerilmiyordu.

## Doğrulama
* **`tests/test_faz104_kod_gocu.py` (8 test):**
  * gerçek beyanlar ve kanıtları;
  * önşart görünümünün iki yönü, iyi not ve beyansız hâl;
  * engel (yeni kodu geçen engellenmiyor, beyansız engelli, eksik metni);
  * yol haritası (sıra, dış sayılmama, ters plan sırası).
* **`tests/test_faz104_ilansiz_sube.py` (3 test).**
* **Mutasyonlar:** 6 mutasyonun 6'sı kırmızı. İlk turda "dış önşart" kuralı
  yeşil kalmıştı; ters plan sırası testi o yüzden eklendi.
