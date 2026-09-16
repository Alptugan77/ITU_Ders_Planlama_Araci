# Faz 40 — Ders başına ton: rengi bozmadan ayırt etmek

*16.09.2026 · kullanıcı: "ders programındaki her ders için biraz daha farklı
bir ton kullanılsın, böylece ayırt etmek ve görselleştirmek kolaylaşsın"*

Ölçülen sorun: haftalık ızgaradaki **14 bloğun 12'si birebir aynı yeşildi**.
Rol rengi (anadal/ÇAP/yandal) doğru çalışıyordu ama rolün içinde hiçbir ayrım
yoktu — "Salı 13:30'daki hangi dersti" sorusu ancak kodu okuyarak
cevaplanıyordu.

Testler **1030 → 1038** (1036 geçti, 2 atlandı).

---

## A. Neyin değişmediği önce

⚠️ **Rolün rengi (hue) değişmedi ve değişmemeliydi.** Bu depoda renk
dekorasyon değil, veri: `--anadal` / `--cap` / `--yandal` hangi programdan
olduğunu söylüyor. Tonu hue'ya bindirmek o bilgiyi yok ederdi.

Ölçüldü ve bu yüzden hue kaydırma **elendi**: anadal 164°, yandal 197° —
arada yalnız 33° var. Ders başına ±12° kaydırmak iki ailenin sınırını
9°'ye indiriyordu, yani "bu yeşil mi mavi mi" sorusunu doğuruyordu.

Değişen şey **açıklık**: ton, rolün *içinde* bir basamak.

---

## B. Merdiven tahminle değil ÖLÇÜYLE seçildi

`color-mix(in oklab, …)` ile `--soft` ya zemine (`--ground`) ya da rolün
kendi rengine (`--accent`) doğru karıştırılıyor. Hangi yöne, ne kadar?
`tools/ton_merdiveni.py` üç sayıya birden bakıyor — **dört rolde ve iki
temada**:

| ölçüt | neden | taban |
|---|---|---|
| yazı kontrastı (WCAG) | blok yazısı okunur kalmalı | **4.5** (AA) |
| zemin farkı ΔE (OKLab) | blok boş hücreden ayrılmalı | **0.035** |
| basamaklar arası ΔE | "iki dersi ayırabiliyor muyum" | büyük olsun |

### İlk deneme yanlıştı — ve ölçüm söyledi

İlk merdivenin yarısı `--ground` yönündeydi (32/21/11%). Tarayıcıda gerçek
piksel okunduğunda o üç basamağın arasındaki fark **ΔE 0.006** çıktı: yani
**görünmüyorlardı**. Sebep basit ama akla gelmiyor — gece temasında
`--anadal-soft` (#123029) zaten `--ground`a (#10141B) çok yakın, o yöne
gitmek hiçbir yere gitmiyor.

Arama sonucu seçilen merdiven — bir zemin basamağı, gerisi accent yönünde:

```js
const TON_BASAMAK = [
  ["soft",    0], ["ground", 38],
  ["accent",  5], ["accent",  9], ["accent", 15], ["accent", 19],
  ["accent", 23], ["accent", 29], ["accent", 33],
];
```

Ölçülen sonuç (hem Python'da hem tarayıcıda, aynı sayılar):

| rol | tema | yazı | zemin ΔE | basamak ΔE |
|---|---|---|---|---|
| ANADAL | gece | 4.67 | 0.063 | 0.0175 |
| CAP | gece | 5.14 | 0.055 | 0.0177 |
| YANDAL | gece | 5.37 | 0.039 | 0.0183 |
| ANADAL | gündüz | 5.09 | 0.049 | 0.0180 |
| CAP | gündüz | 4.97 | 0.046 | 0.0174 |
| YANDAL | gündüz | 5.16 | 0.044 | 0.0188 |

**En kötü: yazı 4.67 · zemin ΔE 0.039 · basamak ΔE 0.0174.** Üçü de tabanın
üstünde.

⚠️ Merdiveni uzatmak cazip — renkler daha çok ayrışır. Ölçüldü:
`accent %36`'da yazı kontrastı **4.40**'a, yani AA'nın altına düşüyor.
`test_MERDIVEN_olculen_tabanlarin_USTUNDE` bunu tutuyor ve ölçümü
`ui.py`'nin paletinden yapıyor — palet değişirse test yeni palete göre ölçer.

---

## C. ★ Plan dışı dersin tonu YOK

`PLAN_DISI` rolünün rengi gri (`--soft`=yüzey, `--accent`=`--ink-3`). Gri bir
aileden merdiven çıkarmak ölçüldü ve **iki tabanı birden düşürüyordu**:
yazı **4.39** (AA altı), zemin ΔE **0.021** (blok boş hücreden ayrılmıyor).

Dışarıda bırakıldı. Renksizlik burada zaten bilgi: *bu ders hiçbir planın
parçası değil.*

---

## D. Ton JS'te PİŞMİYOR — yoksa tema düğmesi sessizce bozulurdu

Tema düğmesi yeniden **render etmiyor**, yalnız `data-theme`i değiştiriyor.
Ton JS'te bir renge çevrilip satır içine yazılsaydı, tema değişince o renk
**eski palette kalırdı** — ve kimse fark etmezdi.

O yüzden satır içinde renk yok, **yön + oran** var:

```html
<div class="blk" style="--tonhedef:var(--accent);--tonoran:19%">
```

Karışımı CSS yapıyor, yani her zaman yürürlükteki paletle:

```css
.blk{--tonhedef:var(--soft); --tonoran:0%;      /* varsayılan = ton yok */
  background:color-mix(in oklab, var(--soft), var(--tonhedef) var(--tonoran));
  border-left:5px solid color-mix(in oklab, var(--accent),
    var(--tonhedef) calc(var(--tonoran) / 2));}
```

Uçtan uca test tam bunu kovalıyor: tema değişince **üç bloğun üçünün de**
hesaplanmış zemini değişmeli. Renk pişirilince test kırmızıya dönüyor
(denendi).

⚠️ Bu arada deponun kendi `test_kullanilan_her_css_jetonu_TANIMLI` testi
`--tonhedef`/`--tonoran` jetonlarını yakaladı: varsayılanlar `var(…, yedek)`
içine saklanmıştı. Açıkça tanımlandılar — hem test geçti hem CSS okunur oldu.

---

## E. Çakışma: ton bir İPUCU, kimlik değil

9 basamak var; bir haftada 12 anadal dersi olabiliyor. Dağıtım şöyle: tercih
ders kodunun hash'inden geliyor (aynı ders her açılışta aynı tonu ister), o
basamak **aynı rolde** doluysa ileri sondalanıyor.

| | önce | sonra |
|---|---|---|
| 12 anadal dersi için farklı ton | **7** | **9** |
| ÇAP dersleri | 2/2 | 2/2 |

⚠️ Bedeli açık: hafta değişince çakışan derslerin tonu kayabiliyor. Kabul
edildi, çünkü **ton bir ipucu — kimlik kodun kendisi** ve her blokta yazılı.
Haftalık program ile kaydedilen program aynı haritayı kullanıyor, yoksa aynı
ders iki yerde iki tonda görünürdü.

⚠️ Çevrimiçi derste ton yalnız **şeritte** görünüyor: o bloğun dolgusu
bilerek yok (Faz 25 kararı — "kampüse gitmiyorsun"). Telefon listesinde dolgu
duruyor, orada ton tam görünüyor.

---

## F. Tonun ne dediği EKRANDA yazılı

Proje ilkesi: bir görsel kodlama anlam taşıyorsa, ne taşıdığını **söylemek
zorunda**. Yoksa koyu yeşil "daha dolu" ya da "daha zor" diye okunabilir.
Izgaranın üstünde:

> Renk hangi programdan olduğunu söylüyor · ton hangi ders olduğunu: aynı
> ton, aynı ders — 9 tondan sonrası tekrar eder, emin olmak için dersin
> üstüne gel

Basamak sayısı da gizlenmiyor. "9 tondan sonrası tekrar eder" cümlesi, aracın
**bilmediğini bilinen gibi göstermeme** kuralının renk tarafındaki karşılığı.

---

## G. Aynı dersin bütün saatleri

Bir bloğun üzerine gelince (ya da klavyeyle odaklanınca) o dersin haftadaki
bütün buluşmaları işaretleniyor — ızgarada ve gün listesinde aynı anda.

⚠️ İşaret **renk değil, çerçeve**: tonla yarışmıyor ve renk körlüğünde de
okunuyor.

⚠️ Ne kadar işe yarıyor, ölçüldü: açık şubelerin **%15.5'i** (3089'un 479'u)
birden fazla güne yayılıyor. Yani her programda birden çok blok yanmıyor —
bu haftalık programda hiç yanmıyor, çünkü 14 dersin hepsi haftada bir kez
buluşuyor. Yine de "hangi bloğa bakıyorum" sorusunu kapatıyor ve ızgarayı
telefon listesine bağlıyor.

---

## H. Testler

`tests/test_faz40_ders_tonlari.py` (8 test):

| test | neyi tutuyor |
|---|---|
| `test_MERDIVEN_olculen_tabanlarin_USTUNDE` | ★★ kontrast/ayrım **tabanı**, paletten ölçerek |
| `test_PLAN_DISI_dersin_tonu_YOK` | gri aileden merdiven çıkmaz |
| `test_TON_jetonla_veriliyor_RENK_PISIRILMIYOR` | ★★ tema güvenliği |
| `test_ton_karisimi_CSS_TARAFINDA` | varsayılan = ton yok |
| `test_TONUN_NE_DEDIGI_ekranda_YAZILI` | görsel kodlama kendini açıklıyor |
| `test_AYNI_DERSIN_butun_saatleri_isaretlenebiliyor` | vurgu + klavye |
| `test_ton_haritasi_AYNI_DERSE_AYNI_TON` | ızgara ve kaydedilen program aynı harita |
| `test_UCTAN_UCA_tonlar_FARKLI_ve_TEMAYLA_degisiyor` | ★★ tarayıcıda, gerçek renkle |

İki tanesi geri konularak kırmızıya döndürüldü: renk pişirme (uçtan uca test
de yakaladı) ve merdiveni `accent %45`'e uzatma.

`python tools/ton_merdiveni.py` ölçümü tekrar üretiyor;
`--ara` ile daha iyi merdiven arıyor.
