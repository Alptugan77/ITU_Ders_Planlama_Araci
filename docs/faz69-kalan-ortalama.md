# Faz 69 — Eşikler için kalan bütün derslerde gereken ortalama

*24.09.2026 · kullanıcı: "eşikler için gereken dönem ortalamasının dışında
kalan bütün derslerden gereken dönem ortalamasını da hesaplayıp gösterir
misin, pr aç sonrasında".*

Testler **1318 → 1321** (+3, `tests/test_faz69_kalan_ortalama.py`), 4 atlandı.
Geri alma deneyi: altı kuralın **altısı** kırmızı.

## Ne değişti

Kredi ve not eşikleri bölümündeki hesap (Faz 57) her eşik için yalnız **bu
dönemin** programından gereken ortalamayı veriyordu. "Bu dönem yeterli değil"
diyen bir eşiğin asıl sorusu cevapsızdı: mezuniyete kadar kalan derslerin
**hepsinde** hangi ortalama yeter?

Her eşik satırına ikinci bir satır eklendi:

> 2.50 — ÇAP'a devam · ÇAP mezuniyeti — üniversite GNO ……… ≥ 1.61
> Bu dönem: her dersten en az DC+ alınması yeterlidir.
> │ Mezuniyete kadar kalan tüm derslerde (66 kredi): ortalama en az **2.07**
> │ (her dersten en az CC+).

Sonuç üç biçimde: *en az X (harf)*, *her durumda ✓* (kalan derslerin hepsi
FF olsa bile) ya da *ulaşılamaz* (hepsi AA olsa bile en fazla Y — danışmana
yönlendirme).

## Hesap

`x = (eşik × (C + T) − P) / T`

* **T** — kalan kredi. Kalan dersler yol haritasıyla **aynı kaynaktan**
  (`yolharitasi._birimler`): anadal ve ÇAP'ta ortak ders tek sayılıyor,
  seçmeli havuz kendi kredisiyle; planda kredisi yazmayan havuz **3
  varsayılıyor** ve bu notta yazıyor. Bu dönemin programı kalan derslerin
  içinde.
* **C, P** — bugünkü ortalamanın kredisi ve puanı; kalan derslerden daha önce
  notu olup geçilmemiş olanlar (FF/VF) **tekrar** sayılıyor: eski notun
  kredisi ve puanı düşülüyor (İTÜ'de son not geçerli — bu dönemki hesapla
  aynı kural, `_tekrar_notlari`).
* ÇAP'ın kendi ortalaması (ikinci anadal ≥ 2.00) için yalnız ÇAP'ın kalan
  dersleri ve ÇAP ortalamasının kendi tabanı.
* Dönem kredi sınırı hedefi (ör. "40 krediye çıkması") yalnız bu dönemin
  sonucuna bağlı olduğundan ona kalan-ders satırı **çizilmiyor**.
* Not satırı, kalan-ders satırının neyi gösterdiğini yazıyor: mezuniyet
  anındaki ortalama; ÇAP'a devam ve başvuru eşikleri her dönem ve başvuru
  anında ayrıca sağlanmalı.

**Vitrinde elle doğrulandı:** GNO 2.78 (77 kredi, 214 puan), kalan 66 kredi,
MAT 210E (FF) tekrar → C = 74; 2.50 için (2.5 × 140 − 214) / 66 = 2.06… →
**2.07** (CC+); mezuniyet 2.00 için 1.00; ÇAP ortalaması 2.00 için 27 kredi
üzerinden 1.84.
