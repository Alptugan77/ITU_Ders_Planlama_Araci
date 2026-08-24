# Faz 27 — arayüz: tercihler, puan kırılımı, karşılaştırma

> Kullanıcı, 24.08.2026: *"ui kısmında geliştirmeler yapıp eklenebilecek
> yeni şeyleri ekler misin"*

`docs/fikirler.md` §3'ün tamamı ve §2.2. Testler **802 → 834**.

---

## 1. ★★ Tercih ağırlıkları (§2.2)

*"Sabah dersi istemiyorum", "Cuma boş olsun", "kampüs değiştirmeyeyim",
"çevrimiçi olsun", "şu hoca / bu hoca olmasın".*

Faz 25'te hoca ve çevrimiçi bilgisi arayüze çıkmıştı — artık **ölçüt olarak**
kullanılabilir hale geldiler.

### Neden sert kısıt değil

Tercihler **eleme yapmıyor**, sıralama ağırlığı. Sebebi ölçülmüş bir
davranış: gerçek veride 14 ÇAP dersinden yalnız 2–3'ü bir dönemde
alınabiliyor. "Sabah dersi istemiyorum"u eleme kuralı yapmak, kayıt
edilebilir **tek** programı imkânsız gösterebilirdi.

Tercih, iki **çalışan** program arasında seçim yaptırır; çalışan tek
programı elemez. Pencere bunu açıkça yazıyor — yoksa kullanıcı *"istemiyorum
dedim ama yine koydu"* diye aracı hatalı sanar.

Ağırlıklar bilerek küçük (`≤12`), ders ağırlıkları ise 40–100. Bir tercih
**asla** kritik yoldaki ya da ÇAP'a ait bir dersi programdan düşüremez.
Bu bir test: `test_tercih_KRITIK_YOLU_ezemiyor`.

### ★★ İlk denemem çalışmadı

Tercihi şube sıralamasında **ayrı bir anahtar** yaptım. Ölçtüm: **hiçbir şeyi
değiştirmedi.**

`blocking_cost` (ileriye bakış maliyeti) bir float ve neredeyse hiç
eşitlenmiyor — dolayısıyla ikinci anahtara sıra hiç gelmiyor. FIZ 102E'nin
hem 08:30 hem 14:30 şubesi varken, "sabah istemiyorum" seçili kullanıcıya
yine 08:30 veriliyordu.

Doğrusu: ikisi de **puan** cinsinden, o yüzden **toplanıyorlar**.

```
_sube_maliyeti(s) = blocking_cost(s) - sube_tercih_puani(s)
```

6 puanlık bir tercih, 6 puandan **az** değer yakan bir şube farkını
çevirebiliyor; daha fazlasını çeviremiyor. Anlam tam olarak istenen:
yumuşak ama etkili.

Ölçüm (BLG, 5. dönem, gerçek katalog):

| Tercih | Sonuç |
|---|---|
| yok | günler Çar Per **Cum** |
| Cuma boş | günler **Pzt Sal Çar Per** · tercih farkı 0 |
| Pzt + Cum boş | günler Sal Çar Per Cum · tercih farkı −10 *(ikisi birden olmuyor, söylüyor)* |
| sabah istemem | 08:30 kalıyor · tercih farkı −18 *(üç dersin 14:30 şubeleri birbiriyle çakışıyor)* |

Son iki satır önemli: tercih **karşılanamadığında sessiz kalmıyor**, sebebini
yazıyor.

---

## 2. "Neden bu puan" (§3.1)

Gerekçe **metni** vardı — *"119 dersin önşartı"* — ama bunun puana **30 mu 3
mü** kattığı görünmüyordu. Sıralamaya güvenmek için ağırlığın büyüklüğünü
görmek gerekiyor.

Ders penceresinde artık kırılım var: her terim, çubuğu ve puanı.

⚠️ Çubuk **mutlak değere** göre ölçekleniyor: eksi katkılar
(*"28 şube — ertelenebilir"* −20) da aynı görsel dilde okunmalı, yoksa
"puanı düşüren şey" hiç görünmüyor.

⚠️ Kırılım toplamı puanla **tutmak zorunda** — ayrışırlarsa arayüz yalan
söyler. Test kilitliyor.

Altında bir cümle: *"yüksek puan = bu dönem kaçırmak daha pahalı,
'daha iyi ders' değil"*. Puanın yanlış okunması, aracın en olası
yanlış anlaşılması.

---

## 3. Önerileri yan yana (§3.4)

"Öneri 1 / 2 / 3" arasında geçiş vardı ama farkı görmek için ızgarayı iki
kez ezberlemek gerekiyordu.

★ Karşılaştırmanın ihtiyacı olan şey ders listesi **değil**, **şekil**:
hangi günler dolu, ne zaman başlıyor, kaç boş gün, arada ne kadar bekleme,
kaç kampüs değişimi. Ders kodlarını üç kolonda dökmek, farkı bulmayı yine
kullanıcıya bırakırdı — o zaten sekmelerde yapabiliyordu.

Üçünde de ortak olan dersler **ayıklanıyor**; tabloda yalnız gerçekten
değişenler kalıyor.

Gerçek çıktı:

```
              ÖNERİ 1      ÖNERİ 2      ÖNERİ 3
En erken      13:30        08:30        12:30
Boş gün       Çar Per Cum  Çar Per Cum  Sal Per Cum
```

---

## 4. Yazdırma (§3.2)

Kayıt günü ekran yerine kâğıda bakan çok. `@media print`:

* düğmeler, süzgeçler, gezinme çubuğu, pencereler **çıkıyor** — kâğıtta işe
  yaramazlar;
* ızgara sadeleşiyor (kart kenarlığı, gölge yok);
* ızgaranın altına **CRN listesi** basılıyor: CRN · ders · ad · gün/saat ·
  kredi. Ekranda gizli, çünkü orada zaten "Kayıt günü" penceresinde —
  ama yazdırırken o pencere açık olmayabilir;
* listenin altında **verinin yaşı**: kâğıda basılan kontenjan, basıldığı
  anın değil son tazelemenin.

---

## 5. Klavye (§3.3)

`↑` `↓` (ya da `j` `k`) gez · `Enter` ekle · `/` aramaya git · `Esc` aramayı
temizle.

⚠️ Kısayollar **yazı alanında çalışmıyor**: arama kutusuna "j" yazan kişi
satır atlamamalı. Ve **pencere açıkken** çalışmıyor: ok tuşu arkadaki
listeyi gezdirmemeli.

Telefonda ipucu gizli — orada klavye yok.

---

## Ölçüm

```
tercih düğmesi rozeti : 3          (üç tercih etkin)
özet                  : … puan 22.5 · tercihlerine uyuyor
klavye ↓↓ + Enter     : BLG 345E → "Programa ekle" penceresi
/                     : arama kutusuna odaklandı
puan kırılımı         : "tek şube +7.5"
karşılaştırma satırı  : Kredi · Ders · Puan · Dolu günler · Boş gün ·
                        En erken · En geç · Ders arası bekleme ·
                        Kampüs değişimi · Çevrimiçi · Değişen dersler
yazdırma              : görünen bölüm yalnız [panels, schedSection]
                        görünen düğme sayısı 0 · CRN listesi 3 satır
telefon (390px)       : yatay taşma yok, kısayol ipucu gizli
sayfa hatası          : []
```
