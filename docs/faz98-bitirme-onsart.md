# Faz 98 — Yol haritası BLG 4902E'yi BLG 4901E ile aynı döneme koyuyordu

Kullanıcı 25.09.2026: *"yol haritasında BLG4902E nin önşartı BLG4901E ama
sistem BLG4901i aldım sayıyor ve ikisini aynı döneme öneriyor ki bu mümkün
değil"*.

## Sorun

BLG 4902E'nin önşartı `BLG 4901 MIN BB veya BLG 4901E MIN BB`. İki ayrı hata
birlikte çalışıyordu:

1. **Dil eşi "dış önşart" sayılıyordu.** Yol haritası, hiçbir planda olmayan
   önşartı (ör. ING 201, kod göçü) geçilmiş varsayıyor. BLGE planında yalnız
   BLG 4901E var; Türkçe "BLG 4901" hiçbir planda olmadığından dış sayıldı ve
   "veya" her zaman sağlandı. Gerçek katalogda (BLGE, 5. dönem) BLG 4902E,
   BLG 4901E'den **önceki** döneme yerleşiyordu.
2. **Geçilen her ders AA sayılıyordu.** DD ile geçilen (ya da notsuz
   işaretlenip DD sayılan) BLG 4901E, "MIN BB" isteyen BLG 4902E'yi açıyordu.
   Bu dönemin önerileri gerçek notla bakıp dersi engelliyordu; iki ekran
   çelişiyordu.

## Değişiklik (`yolharitasi._kur`)

* Dış önşart kümesinden, **dil eşi herhangi bir planda olan** kodlar
  çıkarılıyor (`R.dil_esi` + `R.plan_codes`, havuzlar dahil). Yalnız
  yerleşecek birimlere bakmak yetmiyordu: BLG 4901E işaretlenince birim
  olmaktan çıkıyor ve "BLG 4901" yine dış sayılıyordu.
* Önşart görünümü geçilmiş derslerde **gerçek notu** kullanıyor; yalnız
  gelecekte alınacak (yerleştirilen) dersler AA varsayılıyor.
* Not yetmediği için yerleşmeyen ders sebebini söylüyor: "önşartın istediği
  not sağlanmamaktadır: BLG 4901E (en az BB, kayıtlı not DD). Notu girilmemiş
  ders DD sayılır; notunuzu girerseniz harita yeniden hesaplanır".

## Doğrulama

* Gerçek katalog, BLGE: 7. dönemde 4901E 2027-28 Güz, 4902E 2027-28 Bahar.
  8. dönemde (4901E notsuz işaretli) 4902E not sebebiyle yerleşmiyor.
* `tests/test_faz98_bitirme_onsart.py` (5 test). Dört mutasyonun dördü de
  kırmızı: eş dışlaması kaldırılınca, yalnız birimlere bakılınca, AA'ya
  dönülünce, sebep metni kaldırılınca.
