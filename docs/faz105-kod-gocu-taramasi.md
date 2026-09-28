# Faz 105 — Kod göçü taraması: bütün planlarda aynı hata sınıfı

Faz 104, BBF göçünü (BLG 252E → BBF 203E) tek bir profil gezisinde bulmuştu.
Bu faz aynı hata sınıfını **bütün lisans planlarında** sistematik olarak
arıyor.

## Ölçüt: plana sadık öğrenci engellenmemeli

Her bölümün en güncel lisans planında t. dönemdeki her zorunlu ders için
önceki dönemlerin bütün zorunluları geçilmiş sayıldı (`prereq_view`, beyanlar
dahil). Önşartı yine sağlanamayan ders, planın kendi sırasıyla okuyan
öğrenciyi engelliyor demek.

* **İlk ölçüm:** 2027 zorunlu dersin 126'sı engelli, 55 bölümde.
* **Faz 105 beyanlarından sonra:** 109 engelli, 47 bölümde.

Kalan engellerin çoğu kod göçü değil. Büyük kısmı hazırlık ya da muafiyetle
karşılanan önşartlar (ör. ING 201'in istediği ING 101/102/112 planda hiç
yok) ya da seçmeli havuzdan gelen dersler. Yol haritası bunları zaten "dış
önşart" olarak ele alıyor.

## Kod göçü adayı ve beyan ölçütü

**Aday:** eksik bir önşart koduyla adı ve kredisi aynı bir ders, planın
önceki dönemlerinde var. Fakülte dersi yeni koduyla okutuyor, önşart metni
eski kodda kalmış olabilir.

**Beyan için iki bağımsız kanıt gerekiyor:**
1. Eski ve yeni dersin adı, kredisi **ve AKTS'si** aynı.
2. Bölümün kendi resmî planı yeni kodu, önşartında eski kodu isteyen dersten
   **önceki** döneme koyuyor. Fakülte, yeni kodla alınan dersin önşartı
   karşılamasını açıkça bekliyor.

İkinci kanıt, Faz 104'te "farklı bölümlerin aynı adlı dersi" diye
reddedilen ELE/ELH/EHB 222'yi kapsıyor: TEL planı EHB 222'yi, ELE 222 isteyen
ELE 311'den önce koyuyor.

**Beyan edilen 17 çift:**

| Eski | Yeni | Plan | Engellenen |
|---|---|---|---|
| BLG 335E | BBF 301E | BLGE, SECE, YZVE | BBF 303E |
| FIZ 313E | FIZ 215 | FIZ, FZT | FIZ 310, FZT 302E |
| MAT 210 | BLG 210E | BLG | BLG 4901 |
| EHB 222 | EEE 225E | CEN | EEE 315E |
| EEF 210 | EEE 210E | EEE | KON 313E |
| EEF 232 | EEE 232E | EEE | KON 313E |
| ECN 101E, ECN 105E | EFN 105E | EFN | EFN 201E |
| ICM 104E | IAD 104E | IAD | IAD 4902E |
| END 210 | IND 210E | IND | IND 4901E |
| MAT 271E | MDN 271 | MAD | MAD 441E |
| ISL 233E | MMD 233E | MMD | MMD 244E, MMD 353E |
| MUK 203E | NAE 203 | NAE | GEM 325E, MUK 204E |
| ELE 222(E), ELH 222(E) | EHB 222(E) | TEL | ELE 311 |

**Beyan edilmeyenler** (AKTS farklı, elle incelenmeli): GEM 211E → NAE 102E,
JEO 114 → JEO 117, TEK 314(E) → TER 201E, FIZ 252E → FIZ 215,
EHB 232E → EEE 232E.

## Değişiklik

* **Grup olarak uygulama:** beyanlar artık zincir kurabiliyor (ELE 222 ↔
  EHB 222 ↔ EEE 225E). `declared.code_migration_groups` birleşim-bul ile
  kapanışı alıyor; `prereq_view` ve yol haritasının "dış önşart" kuralı
  grupları kullanıyor. İkili uygulama sıraya bağlı ve eksik kalırdı.
* **`tools/kod_gocu_taramasi.py`:** tarama her katalog tazelemesinde yeniden
  koşulabilsin diye araç hâline geldi. Özet, `--liste` ile engelli dersler ve
  kod göçü adayları. Aday otomatik beyan edilmez.
* **`config/katalog-duzeltmeleri.toml`:** 17 yeni `[[kod_gocu]]`; her birinin
  `not_` alanında iki kanıt da yazılı.

## Doğrulama

* **`tests/test_faz105_kod_gocu_taramasi.py`:**
  * aracın sentetik göçü bulması ve beyandan sonra engelin kalkması;
  * farklı adlı dersi aday saymaması;
  * zincirin geçişli olması;
  * gerçek beyanların iki kanıtı taşıması ve AKTS'si farklı adayların beyan
    edilmemiş olması.
* **Mutasyonlar:** 5 mutasyonun 5'i kırmızı (birleşim, kapanış, ad ölçütü,
  aracın beyanları kullanması, gerçek beyan).
