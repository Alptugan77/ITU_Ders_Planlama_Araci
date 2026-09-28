# Faz 113 — Yol haritasının önşart varsayımları

Kullanıcı (28.09.2026): *"önşart varsayımları da yanlış çalışıyor bakar
mısın onlara"*.

Yol haritası, önşartın istediği ders öğrencinin **hiçbir planında yoksa**
(ING 201 dil dersi, eski kodlu ders, planı değişmiş bölüm) o dersi "dış
önşart" sayıyor. Ders yine yerleşiyor, ama kartında "önşart varsayıldı: …"
yazıyor ve varsayımlar kutusunda listeleniyor (Faz 57, 24.09.2026).

## Gerçek katalogda bulunan üç hata (BLGE, 5. yarıyıl, transkriptli)

1. **Varsayım listesi ağaçtaki BÜTÜN dış dersleri yazıyordu.** BLG 4901E
   kartı "önşart varsayıldı: FIZ 101L, FIZ 102L" diyordu. Öğrenci FIZ
   101EL/102EL'i geçmişti; bu dallar zaten sağlanıyordu. Asıl varsayılan
   ders MAT 210 (2024 BLGE planında Mühendislik Matematiği yok) hiç
   görünmüyordu, çünkü kart ilk iki dersi gösteriyor.
2. **"Veya" dalları ayrı ayrı yazılıyordu.** BBF 304E için "MAT 271,
   MAT 271E, ECN 301E, YZV 231, YZV 231E": beşi birden varsayılmış gibi.
   Oysa önşart bunlardan **biri**.
3. **Laboratuvar kodunun dil eşi bulunmuyordu.** `rules.dil_esi("FIZ 101L")`
   "FIZ 101LE" arıyordu (böyle kod yok). Faz 98 kuralı ("plandaki dersin
   dil eşi dış değil") lab derslerinde işlemiyordu. FIZ 101EL henüz
   alınmamışken, "FIZ 101L veya FIZ 101EL" isteyen bir ders Türkçe kod dış
   sayılıp geçilmiş varsayıldığı için lab dersinden **önce** yerleşebiliyordu.
   Katalogda 24 lab çifti (48 kod) bu yüzden eşsiz kalıyordu; bunlar 97
   dersin önşartında geçiyor.

## Düzeltme

* `rules._dil_esi`: dil eki laboratuvar ekinden önce ("FIZ 101L" ↔
  "FIZ 101EL"; Faz 110'daki `ingilizce_kod` ile aynı kural). Kredi eşitliği
  şartı aynen duruyor.
* `yolharitasi.dis_gruplari`: varsayım artık yalnız **karşılanmamış** dallar
  için. Her dal, onu sağlayabilecek dış derslerle **tek grup**. "Veya" ile
  birleşiyor, dil eşleri "MAT 210(E)" diye tek yazılıyor.

BLGE profilinde sonuç:

| Ders | Önce | Sonra |
|---|---|---|
| BLG 4901E | FIZ 101L, FIZ 102L, MAT 210, MAT 210E | MAT 210(E) |
| BBF 304E | ECN 301E, MAT 271, MAT 271E, YZV 231, YZV 231E | ECN 301E veya MAT 271(E) veya YZV 231(E) |

Bu iki varsayım yerinde: 2024 BLGE planında Mühendislik Matematiği yok ve
BBF 304E'nin önşart metni eski kodları istiyor. Olasılık dersi BBF 201E'nin
kredisi ve AKTS'si farklı olduğu için kod göçü beyan edilmedi (Faz 105
ölçütü). Karttaki uyarı öğrenciyi danışmana yönlendiriyor.

## Doğrulama

`tests/test_faz113_onsart_varsayim.py`:
* lab dil eşi (kredi farklıysa eş yok);
* lab önşartında sıra korunuyor;
* varsayım yalnız eksik dal;
* "veya" tek grup;
* `dis_gruplari` birim testi.

Dört mutasyonun dördü kırmızı.
