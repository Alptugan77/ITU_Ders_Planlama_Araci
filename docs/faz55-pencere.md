# Faz 55 — Pencerenin dışına tıklayınca kapansın

*23.09.2026 · kullanıcı: **"sitenin üzerine açılan sekmelerde arka tarafa yani
normal arayüze tıklayınca oraya geçip açılan kısım kapansın"***

Testler **1214 → 1219**.

## Ne vardı

Sayfanın üzerine açılan üç pencere var: ders penceresi (`detail`), kurulum
penceresi (`setup`: program, dönem, transkript, tercihler, meşgul saat…) ve
başvuru planları (`basvuruDlg`). Üçü de kipli `<dialog>`. Arka plan
tıklamayı **yutuyordu**: kapatmanın tek yolu "Kapat" ya da Esc idi.

## Şimdi

* Pencerenin dışına (karartılmış arka plana) tıklamak onu **kapatıyor**.
* Tıklama **altındaki yere geçiyor**:
  * raydaki "Alabileceğim dersler"e tıklayan oraya gidiyor,
  * ızgaradaki başka bir derse tıklayan o dersin penceresini açıyor,
  * boş bir yere tıklayan yalnız pencereyi kapatmış oluyor.
* Telefonda da çalışıyor: pencerenin iki yanındaki 16px'lik karartılmış
  şerit yetiyor.

## Üç tuzak — üçü de tarayıcıda test ediliyor

1. **Sürükleme.** Pencerenin içindeki bir kutuda metin seçerken fare dışarıda
   bırakılırsa tarayıcı bir "tıklama" üretiyor ve hedefi pencerenin kendisi
   oluyor. Pencere yalnız basış da (pointerdown) dışarıda olduysa kapanıyor.
2. **Kenar.** Pencerenin üstündeki 6px'lik mavi şerit de hedefi pencere olan
   bir tıklama üretiyor. Koordinat kutunun içindeyse pencere kapanmıyor.
3. **Kaydedilmemiş iş.** Kurulum penceresinde bir şey değiştirdiysen (tik,
   seçim, yazı) ilk dış tıklama işi **sessizce silmiyor**. Pencere açık
   kalıyor ve şunu yazıyor: *"Kaydedilmemiş değişiklik var — saklamak için
   Kaydet. Bırakmak için dışarıya bir kez daha tıkla ya da Kapat."* İkinci
   dış tıklama bilerek bırakmak sayılıyor. Hiçbir şey değiştirmediysen tek
   tıklama yeter.

## Testler

`tests/test_faz55_pencere.py` (5 test):

* **Kaynak bekçileri (4):** sayfadaki bütün pencereler kapsanıyor; sürükleme
  ve kenar korumaları yerinde; kaydedilmemiş iş korunuyor; tıklama pencere
  kapandıktan sonra alttaki yere geçiyor.
* **Tarayıcıda uçtan uca (1):**
  1. Raya tıklanınca pencere kapanıyor ve görünüm değişiyor.
  2. Izgaradaki başka derse tıklanınca onun penceresi açılıyor.
  3. Sürükleme pencereyi kapatmıyor.
  4. Kenara tıklamak pencereyi kapatmıyor.
  5. Değişiklik varken ilk dış tıklama uyarıyor, ikincisi kapatıyor.
  6. Değişiklik yokken tek dış tıklama kapatıyor.
  7. Telefonda da kapanıyor.

Geri alma deneyi: 6 durumun 6'sı kendi sebebiyle kırmızı. Statik sitede de
denendi (tarayıcıda Python): ders penceresi açıkken raya tıklamak pencereyi
kapatıp o görünüme geçiyor.
