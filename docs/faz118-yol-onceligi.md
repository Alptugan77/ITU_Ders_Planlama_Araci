# Faz 118 — Yol haritası önceliği

Kullanıcı (28.09.2026): *"yol haritasında anadala öncelik ver veya ikisini
en kısa sürede bitir gibi bir ayar ekler misin"*.

## Sorun

Harita her dönemi tek bir sırayla dolduruyordu: en uzun önşart zincirini
başlatan ders önce (kritik yol), eşitlikte planın dönem sırası. Bu kural iki
programın hangi bitişinin öğrenci için önemli olduğunu bilmiyor. Gerçek
katalogda ölçüldü: tek sıra çoğu çiftte ÇAP'ı gereksiz yere geciktiriyor,
bazı çiftlerde anadalı da.

## Ayar (`settings.yol_onceligi`)

| Değer | Ekrandaki ad | Ölçüt (küçük olan iyi) |
|---|---|---|
| `birlikte` (varsayılan) | Programları birlikte en kısa sürede bitir | yerleşmeyen ders → en geç biten programın bitişi → bitişlerin toplamı |
| `anadal` | Anadala öncelik ver | anadalın yerleşmeyen dersi → anadalın bitişi → toplam yerleşmeyen → en geç bitiş → toplam |

İki programlı haritada (`yolharitasi.kur`) üç **yerleştirme sırası**
deneniyor (`SIRALAR`) ve ayarın ölçütüne göre en iyisi seçiliyor:

* `kritik`: en uzun zincir önce (eski tek kural);
* `anadal_once`: anadal birimleri önce, kendi içinde kritik sıra;
* `ikinci_once`: ÇAP/yandal birimleri önce, kendi içinde kritik sıra.

Eşitlikte ayarın doğal sırası seçiliyor: `birlikte` için `kritik`, böylece
eski sonuç korunuyor; `anadal` için `anadal_once`. ÇAP yarıyıl kredi tabanı
(yönerge) her sırada önce doldurulmaya çalışılıyor.

**Neden arama, neden sabit bir "anadal önce" sırası değil?** Sabit sıra
383 çiftin 49'unda her iki bitişi de kritik sıraya göre kötüleştiriyordu. Bu
plan hiçbir öğrenci için doğru cevap olamaz. 11 çiftte ise anadalı bile
geciktiriyordu (açgözlü yerleştirmenin bilinen anomalisi). Arama iki durumu
da dışarıda bırakıyor.

Tek programlı haritada sıra bitişi değiştirmediğinden harita bir kez
kuruluyor ve panel görünmüyor.

## Her yerde aynı ayar

Sayfadaki harita, "bu dönem alırsanız", kalma riski, senaryo ve ÇAP
seçenekleri penceresi aynı ayarla kuruluyor (`ui.py`'deki dört `YH.kur`
çağrısı). Biri unutulursa iki ekran farklı bitiş söyler; test bunu
denetliyor.

## Arayüz

Yol haritası görünümünün üstünde "Öncelik" satırında iki düğme var. Seçim
kaydediliyor (`/api/yolonceligi`, doğrulama sunucuda). Motor iki ayarın
sonucunu da döndürdüğünden, satır öbür ayarın bitişlerini seçmeden önce
yazıyor: "Anadala öncelik ver seçilirse: anadal 2028-2029 Güz · ÇAP
2029-2030 Bahar". İki ayar aynı bitişi veriyorsa bu da yazıyor. Varsayımlar
kutusunda hangi ölçütün uygulandığı yer alıyor.

## Hız

Üç sırayı denemek maliyeti üçe katlayacaktı. Önce gereksiz tekrarlar
giderildi (sonuç birebir aynı; 142 çiftlik tarama öncesi ve sonrası
karşılaştırıldı):

* **Denklik listesi her kurulumda kopyalanıyordu.** `rules` denklik
  dizinini liste nesnesine göre önbelleğe alıyor; her kopya 3183 denkliğin
  dizinini baştan kurduruyordu (~25 ms/kurulum).
* **Dersin AKTS'si** için `plan_slot.course_code` dizinsiz sorgulanıyordu
  (~0,7 ms/ders). Artık istek boyunca ders başına bir kez okunuyor.
* **Önşart görünümü** (denklik genişletmesi + önşart görünümü) aynı dönemde
  her birim için yeniden hesaplanıyordu. Artık kurulum içinde bir kez.
* Bu dönem şubesi olan dersler, sınıf kısıtları ve okunamayan önşartlar
  istek boyunca bir kez okunuyor.

BLGE+EHB ÇAP profilinde tek kurulum 78 ms'den 15 ms'ye indi. Üç sıralı arama
46 ms sürüyor; bu, eski tek kurulumdan hızlı. Tarama süresi 79,6 sn'den
14,5 sn'ye düştü.

## Ölçüm (gerçek katalog, 383 anadal+ÇAP çifti, 21 kredi sınırı)

Öğrenci, anadal planının ilk (yarıyıl − 1) dönemini geçmiş; ÇAP'a o yarıyıl
başlıyor.

| | 3. yarıyıl | 5. yarıyıl |
|---|---|---|
| `birlikte`: ortak bitiş öne çekildi | 53 çift (48 × 1, 5 × 2 dönem) | 53 çift (50 × 1, 3 × 2) |
| `anadal`: anadal bitişi öne çekildi | 71 çift (55 × 1, 16 × 2) | 55 çift (51 × 1, 4 × 2) |
| sabit "anadal önce" sırası her iki bitişi de kötüleştiriyor | 49 çift | 22 çift |

`birlikte` seçimlerinin 270/383'ü `ikinci_once`. ÇAP dersleri çoğunlukla tek
mevsimde açılıyor ve kritik sıra o mevsimleri anadalın eşit zincirli
dersleriyle dolduruyordu.

## Doğrulama

`tests/test_faz118_yol_onceligi.py`:

* elle kurulmuş katalogda iki ayarın seçtiği sıra ve bitişler (5 → 4 ortak
  bitiş; anadal 2. dönemde);
* öbür ayarın sonucu, taban notu, ölçüt sıraları;
* tek programda tek kurulum; ayar ve sıra adları ayrı; geçersiz değer
  reddediliyor;
* ayar dosyası (okuma, yazma, geçersizse varsayılan) ve sunucu ucu;
* dört harita çağrısı ayarı geçiriyor;
* AKTS belleği ders başına; denklik listesi kopyalanmıyor;
* vitrinde uçtan uca: panel, tıklama, ayar dosyası, telefonda taşma yok.

18 mutasyonun 17'si kırmızı. Kalan biri eşdeğer: yerleşmeyen dersi olan
programın bitişi zaten "hesaplanamadı" (ufuk dışı) sayıldığından, ölçütte
yerleşmeyen ile en geç bitişin yer değiştirmesi sonucu değiştiremiyor.
