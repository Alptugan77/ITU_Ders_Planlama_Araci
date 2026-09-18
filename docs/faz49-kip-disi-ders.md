# Faz 49 — Izgaradaki derse tıklanamıyordu

*18.09.2026 · kullanıcı: **"x.dönem + alttan kısmında kaydettiğim program
yüklenince üstten olan derslere tıklayamıyorum"***

Testler **1128 → 1136**. Haklıydı; ölçüldü ve sebebi tek kelimeydi.

---

## Ölçüm (gerçek veri, açılış ekranı, "5. dönem + alttan")

| | |
|---|---|
| ızgarada duran ders | **14** |
| kipin aday havuzu | **11** |
| havuz DIŞI ama ekranda duran | **5** — `GEO 401E` · `ATA 121` · `TUR 121` · `GEO 464E` · `SNT 103E` |
| o beşine tıklayınca | **hiçbir şey**: pencere yok, hata yok, açıklama yok |
| havuzdaki bir derse tıklayınca | pencere açılıyor |

Açılışta kaydedilen program yükleniyor (`startFromSaved`) ve kaydedilen
program **bütün** derslerini getiriyor — doğrusu da bu. Ama kip havuzu
dönemlik: 5. döneme kadar olan dersler. Üst dönemden kaydettiklerin ızgarada
çiziliyor, tıklanınca hiçbir şey olmuyordu.

## Sebep

Pencere dersi **`CAND`** (AKTİF KİPİN havuzu) üzerinden çözüyordu:

```js
const cand = CAND[course];
if(!cand || !cur) return;          // ← sessiz çıkış
```

Oysa ızgara **`candOf`** ile çiziliyor — o, kipte bulamazsa tam havuza
düşüyor. Yani *çizen* ile *açan* iki ayrı havuza bakıyordu; aradaki fark
ekranda duran ama açılamayan ders olarak çıkıyordu.

> ⚠️ Kip politikası bu depoda **27.08.2026'da zaten yazılıydı** (boş saat
> penceresinin yorumunda): *"kip yalnız ÖNERİYİ daraltıyor, elle ekleme
> hakkını değil."* Pencere o politikadan habersizdi. `choose`, `sectionOf`,
> `picks` ve ızgara doğru yerden okuyordu; yalnız pencere okumuyordu.

---

## Düzeltme: açmak yetmiyor, söylemek de gerekiyor

Pencereyi `candOf` ile açmak bir satır. Ama açtığınızda **iki şey gerçekten
farklı** ve söylenmezse kullanıcı yanılır:

**1. Bu kip o dersi kendiliğinden önermez.** Çıkarırsan geri getirmez.
Pencere artık bunu yazıyor ve **hangi kipin önerdiğini** de söylüyor
("Öneren kip: **DEPAR**") — yoksa "peki nerede bulurum" sorusu açıkta kalırdı.

**2. Kilit bu kipte bağlamaz.** Motor kilidi yalnız o kipin havuzundaki derse
bağlıyor (`recommend.build_schedules`: `locked = {… if k in havuzda}`) — ve
bu doğru, Faz 45'te ölçülmüştü: aksi hâlde kip topyekûn boşalıyordu. Ama
pencere açılınca kilit düğmesi de göründü, yani **basılıp hiçbir şey
yapmayan bir düğme** doğdu. Düğmeyi gizlemedik (öbür kipte gerçekten
çalışıyor); ne yapıp ne yapmayacağını yazdık.

Aynı sessizlik **kilit şeridinde** de vardı ve bu Faz 49'dan eskiydi:

| | önce | sonra |
|---|---|---|
| kapsam dışı kilit varken şerit | *"Öneriler bu derslerin şubesini sabit tutup **etrafında** kuruluyor."* | *"**Bu kipte hiçbiri bağlamıyor.**"* |
| hangi kilit, nerede bağlar | — | *"GEO 401E kilidi **bu kipte bağlamıyor** — ders bu kipin aday havuzunda değil; **DEPAR** kipinde bağlıyor."* |

⚠️ Kırmızı değil: bu bir hata değil, **kapsam** meselesi. Öbür kipte kilit
çalışıyor.

---

## Aynı sınıf: `CAND` mı `candOf` mu

Üç yer daha aynı havuza kilitliydi; ikisi düzeltildi, biri ölçülüp bırakıldı:

* **not dağılımı tazelemesi** (`ndBagla`) — pencere artık kip dışı ders için
  de açılıyor; `CAND` kalsaydı dönem sekmesine basınca kutu **boşalırdı** ✅
* **ekleme penceresi** (`addDialog`) — bugünkü çağıranların hepsi kip
  havuzundan geliyor, ama katalogdan/denklikten ekleme yolları tam havuzdan
  ders getirebiliyor ✅
* **denklik kartı** (`renderAcikDenklik`) — ⚠️ **bilerek bırakıldı**: oradaki
  tıklanamazlık **sessiz değil** (kart görünümü ve `title`ı söylüyor), yani
  bildirilen hatanın sınıfında değil. Üstelik bu öğrencinin verisinde
  ölçülecek tek bir kart bile çıkmadı (`openEquivalents` boş) — ölçmeden
  değiştirmiyoruz.

**Sınıf muhafızı:** artık tek tek işlevler değil, kaynaktaki **`CAND[`
okumaları** sayılıyor. Dört yer beklenen, her birinin sebebi testte yazılı;
beşincisi çıkarsa test kırılıyor. Ekranda duran bir dersi `CAND` ile çözen
her yeni satır aynı hatayı geri getirirdi.

---

## Muhafız denemesi: yedi denemenin üçü yeşil kaldı

Düzeltmeleri tek tek geri koyduk. Üçü testleri **kırmadı** — üçü de
"metin kaynakta var mı" diye bakıyordu:

1. `${disKip ? …}` → `${false ? …}`: dizge duruyor, ekranda görünmüyor.
   Üstelik uçtan uca ölçüm de yeşil kaldı, çünkü aradığı cümle
   ("aday havuzunda değil") **kilit notunda da** geçiyordu — ayırt edici
   olmayan bir cümleye bakıyordu.
2. `if(disKip)` → `if(false)`: aynı hastalık.
3. `kapsamDisi` → `kapsamDisiYOK`: muhafız `"kapsamDisi" in govde` diyordu
   ve yeni ad **alt dizge olarak** onu içeriyordu.

Üçü de **davranışa** çevrildi: uçtan uca test artık tarayıcıda okunan metne
bakıyor (ayırt edici cümlelerle) ve kaynak muhafızları dizgeyi değil
**koşulu** arıyor (`${disKip ? `, `if(disKip)`, `const kapsamDisi = list.filter(`).
Tekrar denendi: **dördü de kırmızı**.

> Faz 48 aynı dersi vermişti (yorumunu okuyan muhafız). Bu, o dersin ikinci
> yarısı: **muhafız metne değil davranışa bakmalı.**

---

## Testler

`tests/test_faz49_kip_disi_ders.py` (8 test): pencere tam havuza düşüyor ·
kip dışı olduğu söyleniyor · kilidin bu kipte bağlamayacağı yazıyor · şerit
bağlamayan kilit için yanlış cümle kurmuyor · `CAND[` okumaları sayılı yerde
(sınıf muhafızı) · not dağılımı tazelemesi tam havuzdan · ekleme penceresi
tam havuzdan · **uçtan uca**: programı kaydet → sayfayı yeniden aç → açılış
kipi "2. dönem + alttan" → üst dönem dersinin ızgaradaki bloğuna tıkla →
pencere açılıyor, kip notu ve kilit notu görünüyor, kilitleyince şerit doğru
cümleyi kuruyor.
