# Faz 114 — Yol haritası önce plan yolunu kullanıyor

Faz 113'ün devamı (kullanıcı 28.09.2026: *"önşart varsayımları da yanlış
çalışıyor"*). Faz 113 varsayımın nasıl **yazıldığını** düzeltti. Bu faz
varsayımın **ne zaman yapıldığını** düzeltiyor.

## Ölçüm

127 lisans planının hepsinde, plana sadık ve transkripti boş öğrenci için
yol haritası kuruldu (`$SP/yh_tara.py`; eski ve yeni kod aynı katalogla).
İki kusur çıktı:

1. **Denklikle plandan kazanılan kod "dış" sayılıyordu.** Dış sayılan 4294
   önşart kodunun 1499'u planın kendi derslerinden resmî denklikle
   kazanılıyordu. Örnek: PEME'de PEM 209E "TES 122 veya MIM 142" istiyor ve
   resmî listede TES 122 ≡ MIM 142 var. MIM 142 dış sayılıp geçilmiş
   varsayıldığı için PEM 209E, onu açan TES 122'den önce yerleşebiliyordu.
2. **Dış varsayım, plan yolu varken de yapılıyordu.** MATE'de MAT 112E "MAT
   111E veya MAT 101" istiyor. MAT 101 hiçbir planda yok, dış sayılıyor ve
   hemen varsayılıyordu. Böylece MAT 112E, planın MAT 111E'sinden önce
   yerleşiyordu ve kartta "önşart varsayıldı: MAT 101" yazıyordu. BIOE'de
   ING 201A ile ING 112A arasında da aynı durum vardı.

## Düzeltme (`yolharitasi.py`)

* **Görünüm yerleşen derslere denklik uyguluyor** (`gorunum`). Plan dersi
  yerleşince resmî denkliğin hedefi de sağlanmış sayılıyor.
* **Denklikle plandan kazanılan kod dış değil.** Kaynak yalnız tek tek
  yerleşecek birimler (`kod_birim`). İlk denemede bütün plan kodlarını
  kullandım; havuz seçenekleri hiç tek tek yerleşmediği için IBM, MTO ve
  ENTE'de 5 ders yerleşemedi. Düzeltildi.
* **Plan yolu önce.** Önşart, planın henüz yerleşmemiş dersleriyle
  sağlanabiliyorsa dış varsayım yapılmıyor; ders plan dersini bekliyor. Dış
  varsayım yalnız plan yolu olmayan dallar için.
* **Dış varsayım denklikten sonra ekleniyor.** Varsayılan dış dersten
  denklik zinciri kurulmuyor. Aksi hâlde HTAE'de dış JDF 122 (≡ GEO 103)
  GEO 114E'yi, planın GEO 103E'sinden önce ve kartta hiçbir varsayım
  yazmadan açıyordu.

## Sonuç (127 plan)

| | Önce | Sonra |
|---|---|---|
| Kartta "önşart varsayıldı" | 277 | **84** |
| Önşart sırası ihlali | 0 | 0 |
| Yerleşemeyen ders | 16 | 16 |

32 planda tahmini bitiş değişti; çoğu 1–2 dönem geç (3'ü erken). Bunlar
eski iyimserliğin düzelmesi: dersler artık planın kendi önşart sırasına
uyuyor. Taramadaki öğrenci içinde bulunulan dönemi boş geçiriyor; gerçek
öğrencide fark daha küçük. Gerçek BLGE profili değişmedi (varsayımlar
MAT 210(E) ve BBF 304E'nin "biri" grubu). Kurulum süresi değişmedi
(~3.3 sn).

## Doğrulama

`tests/test_faz114_plan_yolu.py`:
* denklikle plandan kazanılan kod dış sayılmıyor, sıra korunuyor;
* plan yolu varken dış varsayım yapılmıyor;
* plan yolu yoksa varsayım sürüyor;
* karma dal (bir dal denklikle plandan, öbürü gerçekten dış).

Üç mutasyonun üçü kırmızı. Yol haritası testleri (97) geçiyor.
