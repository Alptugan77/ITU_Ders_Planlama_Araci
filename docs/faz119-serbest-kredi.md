# Faz 119 — Senaryoda serbest dönem kredisi

Kullanıcı (28.09.2026): *"dönem başına en çok kredi kısmında istenilen
değerin girilmesine izin verebilir misin"*.

## Önce

Yol haritası senaryosundaki "Dönem başına en çok … kredi" bir açılır
listeydi: mevcut sınır, 21, 18, 15, 12. Yalnız sınırın **altındaki** değerler
sunuluyordu. 17 ya da 24 kredi denenemiyordu.

## Şimdi

* Sayı kutusu: 1–60 arası tam ya da buçuklu değer (`step=0.5`). Sunucu aynı
  aralığı zaten doğruluyordu (`_harita_girdisi`). Öneri listesi (mevcut
  sınır, 25, 22, 21, 18, 15, 12) yalnız kolaylık için.
* Geçersiz değerde senaryo değişmiyor. Kutunun yanında "1 ile 60 arasında,
  tam ya da buçuklu bir kredi değeri giriniz." yazıyor ve kutu
  `aria-invalid` alıyor.
* **Mevcut sınırın üstü reddedilmiyor.** "GNO'm yükselirse ne zaman
  biterim" sorusu meşru. Senaryo şeridi yönetmeliğin istediği GNO'yu yazıyor
  (MADDE 17/2, `kurallar.toml` [[kredi_yuku]]; `ui.yuk_basamagi`):
  * "mevcut sınırınızın, 25 kredinin, üzerindedir; yönetmeliğe göre en az
    3.00 GNO gerekir";
  * en yüksek basamağın (40) da üstündeyse "yönetmelikteki en yüksek sınır
    40 kredidir, bu yük alınamaz";
  * basamak beyan edilmemişse hiçbir şart uydurulmuyor.

## Doğrulama

`tests/test_faz119_serbest_kredi.py`:

* basamak hesabı (22 → GNO 0; 22,5 ve 25 → 2,25; 26 → 3,00; 41 → üstünde);
* beyan yoksa `None`;
* arayüz: sayı kutusu, doğrulama, şart metni;
* vitrinde masaüstü ve telefonda: 17,5 kabul, 30'da GNO 3,00 şartı, 45'te
  "en yüksek sınır", 0 reddediliyor ve senaryo değişmiyor, yatay taşma yok.

`test_faz61_senaryo_ve_danisman.py` yeni kutuyla güncellendi (liste
seçimi yerine değer yazılıyor). 6 mutasyonun 6'sı kırmızı.
