# Faz 128 — Sayfa hesabı hızlandı

Kullanıcının verisiyle (HTAE + BLG ÇAP) ölçüldü: sayfa durumunun hesabı
**2,07 sn'den 1,24 sn'ye** indi (beş ölçümün ortancası). Statik site aynı
motoru tarayıcıda (Pyodide) birkaç kat daha yavaş çalıştırdığından fark
orada daha belirgin.

## Neden yavaştı

Yol haritası bir istekte 48 kez kuruluyor: 8 çağrı (sayfa, "bu dönem
alınırsa", yaz okulu) × 6 yerleştirme varyantı (Faz 118/122). Her kurulumda
aynı hesaplar baştan yapılıyordu:

| Hesap | Sorun | Süre (profil) |
|---|---|---|
| Önşart zinciri yüksekliği | Her birim için bütün önşart ağaçları yeniden geziliyordu (2544 çağrı) | ~0,7 sn |
| Lisans planından mevsim | Her ders için planın bütün satırları taranıyordu | ~0,5 sn |
| Denklik listesi | Bir istekte 12 kez okunuyordu; her yeni liste 3183 denkliğin dizinini baştan kurduruyordu | ~0,4 sn |

## Değişiklik

* Önşart ağaçlarının kodları istek boyunca bir kez çıkarılıyor. Bağımlılar
  tek geçişte kuruluyor; sıra korunuyor.
* Lisans planı için program başına bir dizin tutuluyor (kod → ilk satırın
  sırası ve dönemi). Kural değişmedi: kodlardan biriyle eşleşen ilk satır.
* `load_equivalences` istek boyunca bir kez okunuyor ve çağırana kopya
  veriyor. Yazma uçları istek bağlamının dışında çalıştığından yeni bir
  beyan bir sonraki durumda okunuyor.
* Denklik dizini önbelleği, liste kimliği tutmadığında içerikle de
  eşleşiyor. Yerinde değişen liste yine yeniden kurduruyor.

## Doğrulama

* 150 gerçek anadal+ÇAP çiftinin yol haritası ve kullanıcının sayfa
  durumunun tamamı, eski ve yeni kodda **birebir aynı** (JSON karşılaştırması).
* `tests/test_faz128_hiz.py`:
  * denklikler istekte bir kez okunuyor ve kopya dönüyor; bağlam dışında taze okunuyor;
  * içerikle eşleşen dizin doğru; yerinde değişen liste yeniden kuruluyor;
  * lisans mevsiminde ilk satır kuralı korunuyor.
