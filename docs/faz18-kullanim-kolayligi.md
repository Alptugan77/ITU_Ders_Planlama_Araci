# Faz 18 — Kullanım kolaylığı

**Tarih:** 22.08.2026 · **Test:** 535 (öncesi 521)

> "ders öneri kısmında ilk önerilen kısımın x.dönem + alttan olması daha iyi
> olur onun dışında kullanım kolaylığını artırıp başvurabilir miyim kısmını
> açılabilir pencere ile çap planları şeklinde küçültür müsün"

Üç istek, tek ortak risk: **bir şeyi öne alırken ya da gizlerken erişilemez
kılmak.** Testler bu yüzden "küçüldü mü" değil, "hâlâ ulaşılabiliyor mu" diye
soruyor.

---

## 1. Varsayılan kip: "N. dönem + alttan"

Açılışta gösterilen kip artık dönemlik havuz. "Tüm adaylar" bir keşif kipi —
kayıt haftasında bakılan şey bu değil.

**Ama boş kipe düşürmüyoruz.** Dönemlik havuz çakışmasız bir program
üretemediyse (alttan çok ders, arz yok, saatler çakışıyor) kullanıcı açılışta
bomboş bir ızgara görürdü ve bunu "araç bozuk" diye okurdu. O durumda "Tüm
adaylar" önde kalıyor:

```python
return [donemlik, hepsi] if donemlik.get("schedules") else [hepsi, donemlik]
```

Sıra değişiyor, **kip kaybolmuyor** — öbürüne hep tek tıkla geçiliyor.

Kip sırası artık `ui._modes()` içinde, tek satırda ve testli. Eskiden `collect`
içinde gömülü bir liste sabitiydi; sıranın bir *karar* olduğu görünmüyordu.

## 2. "Başvurabilir miyim" → iki satır + pencere

Bölüm sayfanın en uzun parçasıydı: iki sekme, altı şart kartı, program
tablosu, üç uyarı kutusu — hepsi her açılışta oradaydı. Oysa dönemde birkaç
kez bakılan bir şey.

Şimdi sayfada duran hâli:

```
✗ Çift anadal   bir şart sağlanmıyor · 63 program açık      [ÇAP planları]
✗ Yandal        bir şart sağlanmıyor · OBS'de plan yok      [Yandal planları]
```

Ayrıntının tamamı `#basvuruDlg` penceresinde — şartlar, üç durumlu işaret
(✓ / ✗ / **—** buradan bakılamaz), program tablosu, uyarılar. Hiçbir bilgi
atılmadı, yeri değişti.

Pencere `dialog.wide` (880px): program tablosu 540px'e sığmıyordu ve içeriği
kesmek yerine pencereyi büyütmek doğrusu. Yükseklik ekranla sınırlı, taşan
kısım pencerenin içinde kayıyor.

## 3. Bölüm çubuğu

Sayfa on bölüm uzunluğunda; aranan yere kaydırarak gitmek en sık yapılan iş
hâline gelmişti. Başlığın altında yapışkan bir çubuk var: İlerleme · Program ·
Eşikler · Denklik · Değişim · Adaylar · Darboğaz · Başvuru · Kademeler.

Üç incelik:

**Gizli bölüm çubukta da yok.** Veri gelince (transkript yüklenince, denklik
önerisi çıkınca) bölüm açılıyor ve bağlantısı kendiliğinden beliriyor.
Hiçbir yere gitmeyen bir bağlantı, olmayan bağlantıdan kötüdür.

**`scroll-margin-top`.** Yapışkan çubuk olmadan hedef bölümün başlığı çubuğun
altında kalırdı.

**`position:sticky` sessizce bozulur** — bir üst kapsayıcıya `overflow`
eklendiği anda çalışmayı bırakır ve kimse fark etmez. Kaydırıp çubuğun yerinde
kaldığını ölçen bir test var.

Bulunduğun bölüm çubukta işaretli. IntersectionObserver yerine kaydırma anında
ölçüyoruz: bölümler açılıp kapandığı için gözlemciyi her çizimde yeniden kurmak
gerekirdi.
