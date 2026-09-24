# Faz 64 — "Bu dönem" bir yıl geride yazıyordu

*24.09.2026 · kullanıcı: "we are currently in 2026-2027 fall semester not in
2025-2026".*

Kullanıcı haklı. Testler **1300 → 1304** (+4, `tests/test_faz64_bugunku_donem.py`),
4 atlandı. Geri alma deneyi: altı kuralın **altısı** kırmızı (§3).

## 1. Sebep (ölçüldü)

* OBS'nin kendi not dağılımı ucuna göre (Faz 38) dönem kodunun yılı akademik
  yılın **bitiş** yılı: `202610` = **2025-2026** Güz, `202710` = 2026-2027 Güz.
  `config.donem_adi` bu yüzden doğru.
* itu-helper'ın `lessons.psv`'sinde dönem **yok**. Yükleyici şubelere
  ayardaki `term`i basıyordu; o da örnek ayardan kalma `202610`'du — üstelik
  örnek dosyanın yorumu `# 2026-2027 Güz` diyordu (kod ile yorum bir yıl ayrı).
* Yayındaki katalogun 3807 şubesinin hepsi **20.09.2026**'da çekilmiş ama
  `202610` damgalı. Faz 62'den beri site "bu dönem"i bu damgadan aldığı için
  yol haritası, başlık ve danışman özeti 2025-2026 Güz'den başlıyordu.

## 2. Düzeltme

* `config.donem_kodu_tarihten(tarih)`: şubelerin dönemi **çekildikleri günün**
  gerçeği. Eylül–Aralık → Güz (`{yıl+1}10`), Şubat–Mayıs → Bahar (`{yıl}20`).
  Ocak ve Haziran–Ağustos geçiş ayları (final/yaz okulu, yeni programın
  ilanı): OBS'nin hangisini gösterdiği bilinmiyor → **boş**, uydurma yok.
* **Yükleyici** (`pipeline.step_ituhelper`) şubelere bu kodu basıyor; ayar
  yalnız geçiş aylarında.
* **`ui._aktif_donem`**: kullanıcının `term` beyanı → şubelerin çekildiği gün
  → (geçiş ayıysa) katalogdaki damga. Yayındaki eski damgalı katalog da
  **yeniden çekmeden** doğru okunuyor.
* **Başlık, "dönem bitmiş" uyarısı ve not dağılımının mevsimi** artık
  haritayla AYNI dönemi kullanıyor (`collect` içinde tek `aktif_donem`).
  Sitede `term` ayarı olmadığı için başlıkta dönem hiç yazmıyordu; şimdi
  "2026-2027 Güz".
* `site_kur` günlüğü de aynı dönemi yazıyor; damga farklıysa onu da:
  `dönem 202710 (katalog damgası 202610)`.
* `config/settings.example.toml`: `term = "202710"  # 2026-2027 Güz` ve kodun
  nasıl okunduğu; test yorumla kodun aynı dönemi söylediğini denetliyor.
* **Vitrin** (kurmaca öğrenci) bir yıl ileri alındı: bu dönem 2026-2027 Güz,
  transkript 2024-2025 Güz'den başlıyor. Vitrine bağlı dört uçtan uca testin
  beklediği etiketler bir yıl kaydı — davranış aynı (bitiş yarıyılları,
  dönem farkları değişmedi).

**Gerçek katalogla ölçüldü:** ayar olmadan 1. yarıyıl BLG öğrencisi — başlık
"2026-2027 Güz", haritanın ilk kartı 2026-2027 Güz, bitiş 2029-2030 Bahar
(8 yarıyıl).

## 3. Geri alma deneyi

| Geri konan | Kırmızı |
|---|---|
| Tarihten kodda yıl kayması (Faz 38 öncesi hata) | birim ×2 |
| Geçiş ayı da tahmin ediliyor | birim ×2 |
| Aktif dönem katalog damgasına güveniyor | birim |
| Yükleyici ayardaki dönemi basıyor | statik |
| Başlık ayardaki dönemden | statik |
| Örnek ayar yorumu koddan bir yıl ayrı | birim |

## 4. Ne yapılmadı

* Katalog sürümü (`katalog-*`) yeniden yüklenmedi — gerek yok, uygulama eski
  damgayı çekim gününden düzeltiyor. Bir sonraki `make refresh` doğru damgayı
  zaten basacak.
* Kullanıcının kendi `settings.toml`'unda `term = "202610"` yazıyorsa o
  beyan olarak kalıyor (Faz 38 kuralı: sessizce düzeltmiyoruz); o dönemin
  notları açıklandığı için arayüz zaten "bitmiş görünüyor" uyarısını veriyor.
