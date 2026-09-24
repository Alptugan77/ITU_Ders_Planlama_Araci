# Faz 83 — Dersin geçmişte açıldığı dönemler (doğruluğu belirsiz)

*24.09.2026 · kullanıcı: "bir de geçmişteki not dağılımlarından derslerin hangi
dönemlerde açıldığı ile ilgili küçük bir bilgi geç doğruluğunun belirsiz
olduğunu belirterek".*

Testler +3 (`tests/test_faz83_gecmis_donemler.py`).

* **Yol haritası:** gelecek dönemlere konan her derste küçük bir satır —
  "geçmişte: 2025-26 Bahar (3) · 2025-26 Güz (80)"; parantezde not alan
  öğrenci sayısı, yeniden eskiye, en çok dört dönem (`gecmis_donemleri`,
  mevsim kararından ayrı: ham veri). Kartların üstünde tek satır açıklama:
  *"Doğruluğu belirsizdir; dersin ileride aynı dönemlerde açılacağı kesin
  değildir."* Aynı cümle varsayımlar listesinde.
* **Ders ekleme penceresi:** "Geçmişte açıldığı dönemler (not dağılımına
  göre): 2025-26 Güz (115 öğrenci)" ve aynı uyarı.
* Sayı bilerek gösteriliyor: az öğrencili dönem (ör. Bahar'da 3 kişi)
  çoğunlukla tekrar/bütünleme sınıfıdır — bunu metin söylüyor, sayı gösteriyor.
