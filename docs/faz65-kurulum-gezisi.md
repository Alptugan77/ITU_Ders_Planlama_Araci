# Faz 65 — Gerçek sitede yeni öğrenci gezisi

*24.09.2026 · kullanıcı: "can you continue and create a pr".*

Site gerçek katalogla (3807 şube, Pyodide) kuruldu ve Chromium'da yeni bir
öğrenci gibi, **tıklayarak** gezildi: BLGE, ikinci program yok, 3. yarıyıl,
plandan işaretle, sonra bütün görünümler — masaüstü ve 390 px telefon.
Faz 64'ün düzeltmesi yerinde: başlık "2026-2027 Güz", haritanın ilk kartı
2026-2027 Güz, bitiş 2028-2029 Bahar (8. yarıyıl). İki pürüz bulundu.

Testler **1304 → 1307** (+3, `tests/test_faz65_kurulum.py`), 4 atlandı.
Geri alma deneyi: dört kuralın **dördü** kırmızı (§3).

## 1. Dönem penceresi

* ÇAP'ı **olmayan** öğrenciye "ÇAP'a başladığın yarıyıl" soruluyordu —
  yönergenin ikinci anadal tabanını anlatan bir paragrafla. Artık yalnız
  ikinci program ÇAP ya da "ikisi" iken.
* Kurulum listesi "Kaçıncı dönemdesin? **Tek tıklama.**" diyordu; sayı +
  Kaydet iki tıktı. ÇAP yoksa sayıya basmak artık kaydedip kapatıyor. ÇAP
  varsa iki soru birlikte cevaplandığı için Kaydet duruyor (sayıya basmak
  kaydetmiyor — test ediliyor, yoksa taban seçilemezdi).

## 2. Plandan işaretle → transkript yapıştır

Kurulum listesi "En kolayı: transkriptini olduğu gibi yapıştır" diyordu ama
"Dersleri gir" plandan-işaretle penceresini açıyordu ve oradan yapıştırmaya
**yol yoktu**. Tikle girilen ders notsuz (DD) sayılıyor; GNO ve kredi tavanı
için gerçek notlar yalnız yapıştırmayla geliyor. Pencerenin başında artık
*"Notlarınla girmek istersen: [transkriptini yapıştır] — GNO ve kredi tavanı
gerçek notlarından hesaplanır."* Gerçek sitede ölçüldü: üç satırlık OBS
dökümü → "3 ders bulundu, 3 geçilmiş".

## Ölçülüp hata OLMADIĞI görülenler

* 1. öneride ATA 121 **dolu** şubede ve "uyan boş şube yok" yazıyor; aday
  listesi "27 boş" diyor. Çelişki değil: 27 **koltuk** — BLGE'ye açık iki
  boş şube (10132 Çar, 10146 Sal) bu programdaki başka derslerle çakışıyor.
* Telefonda (390 px) yol haritası, program ve aday listesi yatay taşmıyor.

## 3. Geri alma deneyi

| Geri konan | Kırmızı |
|---|---|
| ÇAP sorusu herkese | statik + uçtan uca |
| ÇAP'sızda tek tık kaydetmiyor | statik + uçtan uca |
| ÇAP'lıda da tek tık kaydediyor (taban seçilemez) | statik + uçtan uca |
| Yapıştırma bağlantısı pencereyi açmıyor | statik + uçtan uca |
