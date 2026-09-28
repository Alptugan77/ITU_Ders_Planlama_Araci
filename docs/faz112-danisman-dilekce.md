# Faz 112 — Danışman özetinde yalnız dilekçe gerektirenler

Kullanıcı (28.09.2026): *"danışman özeti kısmında da dilekçe dışında
danışmana sorulacak diye yazdığın şeyleri çıkarabilirsin"*.

"Danışmana sorulacaklar" listesi (Faz 61'den beri) yaklaşık yirmi kaynaktan
soru üretiyordu: bitiş gecikmesi, azami süre, "bu dersi öne almalı mıyım",
yerleşmeyen ders, GNO eşikleri, şartlı geçme, zor dersler, kalma riski,
tekrar dersleri, saati ilan edilmemiş ders, ortak lisans, transkriptsizlik.
Bunların hepsi ilgili görünümlerde (yol haritası, GNO paneli, kalma riski,
program) zaten gösteriliyor.

Bölümün adı artık **"Dilekçe gerektirenler"**. Yalnız görüşmede dilekçeyle
yapılacak işler kalıyor:

1. **Dönem yük sınırı aşımı:** sınırın üzerinde ders almak için dilekçe.
2. **ÇAP yarıyıl tabanı:** taban tutmuyorsa ve kurallarda bir indirim
   (`relief`) tanımlıysa, indirim için dilekçe. İndirim yoksa madde çıkmıyor;
   eksik taban "Kontroller" satırında yazmaya devam ediyor.
3. **Dolu şube:** programla çakışmayan boş şubesi olmayan dolu şube için
   kontenjan açılması talebi (tek madde, Faz 90'daki gibi).
4. **Denklikle saydırma (yeni):** programdaki bir ders, gereken bir dersin
   resmî denkliğiyse ve şubesi bölümünüze açık değilse (Faz 111
   "dilekçesiz" değilse), "X dersini Y yerine saydırmak için denklik
   dilekçesi verilmelidir". Onay gerektiren denklikte ayrıca belirtiliyor.

Hiç madde yoksa "Dilekçe gerektiren bir durum bulunmamaktadır." yazıyor.
Özetin program tablosu, kontroller ve tahmini bitiş bölümleri değişmedi.

## Doğrulama

* `tests/test_faz112_danisman_dilekce.py`: yalnız 4 madde kaynağı kaldı,
  kaldırılan kaynaklar yok; tarayıcıda denklik maddesi dilekçeli kaynakta
  çıkıyor, dilekçesiz kaynakta çıkmıyor (geri alma denemesiyle kırmızı).
* Eski testler (Faz 61, 63, 70, 72, 73, 89, 90) kaldırılan soruların artık
  çıkmadığını sınayacak biçimde güncellendi.
