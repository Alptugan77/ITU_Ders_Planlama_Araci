# Faz 12 — Gece Şeması, doğrulanan mevzuat, "başvurabilir miyim"

> ⚠️ Bu belgedeki bütün sayılar **örnektir**. Depoda kimsenin gerçek notu
> ya da ortalaması yer almaz — kişisel veri `data/` altında kalır ve
> `.gitignore` ile dışarıda tutulur.


```bash
make app                     # yeni tasarım · başvuru ekranı · telefon düzeni
make basvuru                 # komut satırından: hangi programlara başvurabilirim
make basvuru ARGS="--tur yandal"
```

382 test (Faz 12'den 44 yeni).

## ★ Tasarım: Şematik × Gece

Kullanıcı beş yönden ikisinin melezini seçti. Melez, iki yönü ortalamak
değil — her birinden **farklı bir katmanı** almak:

| Şematik'ten (yapı) | Gece'den (zemin) |
|---|---|
| sıfır köşe, hiçbir yerde yuvarlaklık yok | yumuşak koyu zemin `#10141B` (saf siyah değil) |
| kutu yerine **cetvel**: kart kenarlığı değil, altındaki çizgi bölüyor | düşük kontrast gövde — saatlerce bakılıyor |
| gölge yok, degrade yok | tek aksan: periwinkle `#8FA3E8` |
| Chivo 800/900, BÜYÜK HARF başlıklar | gövde IBM Plex Sans |
| ızgarada dönüşümlü çizgi: saat başları kalın | Şematik'in çığlık kırmızısı yerine yumuşatılmış `#E0836F` |

Renk **rolleri** değişmedi ve değişmemeliydi: `--seal` yapısal (cetvel, bölüm
etiketi, tablo başlığı), yeşil/kehribar **veri** (anadal / ikinci program),
kırmızı yalnız mevzuat çelişkisi. Karıştırmak rengin taşıdığı bilgiyi
yok ederdi.

Tasarım artık **koyu doğuyor**: `:root` koyu palet. Işık modu Şematik'in kendi
dünyasına yaklaşıyor — beyaz zemin, sert siyah cetvel. Aynı yapı, iki zemin.

### Testin yönü değil kapsamı ölçmesi

`test_both_themes_declared` "prefers-color-scheme:**dark** var mı" diye
soruyordu. Koyu-doğar tasarımda o sorgu `light` olur ve test kırıldı. Doğru
düzeltme testi yöne göre güncellemek değil, **yönden bağımsız** hâle
getirmekti: üç durumun (bare `:root`, medya sorgusu, `data-theme`) hepsi
tanımlı mı. Yönü test etseydik bir tasarım kararı teste gömülü kalırdı.

Yeni bir test daha eklendi — `test_no_color_is_defined_only_inside_a_theme_block`.
Klasik okunmaz-arayüz hatasını kilitliyor: bir renk yalnız medya sorgusunun
içinde tanımlanırsa, kullanıcı "sistem" ayarındayken o değişken hiç çözülmez
ve bir temanın yazısı öbür temanın zemininde çıkar. Sistem en yaygın ayar.

## ★ Mevzuat: iki ⚠ kalkmıştı, altı eşik geldi

Faz 11'den kalan iki doğrulanmamış eşik yönergeden bulundu — **ikisi de
doğruymuş**. Ama aynı okumada dört eşik daha çıktı ve biri kritik bir ayrım
taşıyor:

| Kural | Değer | Kaynak |
|---|---|---|
| ÇAP başvuru GNO | **3.00** | Madde 15 ✅ (varsayım doğruydu) |
| ÇAP devam GNO | **2.50**, *bir defaya mahsus* düşülebilir | Madde 19/k ✅ |
| ÇAP mezuniyeti — üniversite GNO | 2.50 | Madde 18 **yeni** |
| ÇAP mezuniyeti — ikinci anadal ortalaması | 2.00 | Madde 18 **yeni** |
| Yandal başvuru GNO | 2.50 | Madde 22/a **yeni** |
| Yandal kayıt silme | anadal GNO < 2.00 | Madde 27/c **yeni** |
| Mezuniyet GNO | 2.00 | Yönetmelik MADDE 31/1 **yeni** |

### Üç yeni kavram, üçü de yanlış cevaptan koruyor

**1. Kapsam.** Yandal eşikleri ÇAP öğrencisine uygulanmaz — ayrı maddeler,
farklı sayılar. Hepsini birden göstermek "yedi kuralda kaldın" izlenimi
veriyordu. Eşikler artık `program` (`cap`/`yandal`/`genel`) ve `tur`
(`basvuru`/`devam`/`mezuniyet`) taşıyor; arayüz **aşamaya göre** grupluyor.

> Uyumluluk: `program` yazılmamış eski beyan `genel` sayılır ve **elenmez**.
> Aksi hâlde kapsam alanını eklemek, kullanıcının elle yazdığı eşikleri
> sessizce devre dışı bırakırdı.

**2. Doğru sayı.** "İkinci anadal ortalaması ≥ 2.00" genel GNO'yu değil,
**ÇAP programının kendi ortalamasını** sorar. Fark, notu eksik bir
transkriptte çarpıcı olabiliyor — örnek:

```
genel GNO             1.72     (24/31 dersin notu girilmemiş → DD sayılıyor)
ikinci anadal ort.    3.40     (ÇAP dersleri gerçek notlarıyla girilmiş)
```

Genel GNO ile karşılaştırmak, karşıladığı bir şartta "kaldın" demek olurdu.

**3. Hesaplanamıyorsa iddia yok.** ÇAP planında notlu ders yoksa ortalama
hesaplanamaz; eşik `—` ile "henüz belli değil" döner. ✗ göstermek "kaldın"
demek olurdu, oysa daha başlamamış.

### "Şartlı başarmış"ın şartı bulundu

Faz 11'de `⚠ bilinmiyor` diye bırakılmıştı. MADDE 20/2-b DC+…DD notlarını
"şartlı başarmış" sayıyor ama şartın ne olduğunu yazmıyor. Şart MADDE 31/1'de:

> "… ağırlıklı genel not ortalamasını en az **2.00** düzeyine çıkarmış …"

Yani **iki ayrı soru**, ve motor ikisini ayrı tutuyor:

* **Ders tamamlandı mı?** → Evet. Şartlı not geçer, kredi kazandırır.
* **Mezun olunabilir mi?** → Genel ortalama 2.00'a çıkmışsa.

Tek soruya indirmek iki yönde de hata üretirdi: dersi haksız yere kapatmak ya
da mezuniyeti haksız yere açmak.

## ★ "Başvurabilir miyim" (yapılacaklar 1.3)

Parçalar Faz 9–10'dan beri vardı, birleştiren cümle yoktu. Yeni modül
`basvuru.py` yönergedeki şartları öğrencinin durumuyla karşılaştırıyor ve
programları **kalan işe göre** sıralıyor.

```
ÇAP BAŞVURUSU — GNO 1.72 · 78 kredi · anadal XXX      (örnek çıktı)

  ❌ ÇAP başvurusu            GNO 1.72 / gereken 3.00
  ✅ Başvuru kredi penceresi  78 kredi / pencere 30–94.99
  —  Anadal başarı sıralamasında üst %20
       Sıralama verisi bu araçta yok — OBS'den ya da bölümünden öğren.
```

### Üç değerli işaret

`—` bu ekranın en önemli parçası. Yönerge "üst %20'de bulunması gerekir"
diyor; sıralama verisi ne bizde var ne OBS'den çekiliyor. Bu şartı sessizce
atlamak, **karşılanmamış olabilecek bir şartı karşılanmış göstermek** olurdu.

Bu yüzden `eligible` ("bilinen şart düşmüyor") ile `unknown` ("bakılamayan
şart var") ayrı kavramlar ve arayüz ikisini birlikte gösteriyor. Bir test tam
olarak bu ayrımı kilitliyor (`test_eligible_does_not_mean_all_conditions_met`).

### Kredi bir PENCERE, taban değil

Yönerge en erken 3., **en geç 5. dönem** diyor: 30–94.99 kredi. Yalnız alt
sınıra bakılsaydı 8. dönemdeki öğrenciye "başvurabilirsin" denirdi. Yandalda
üst sınır yok — ikisi ayrı kontrol ediliyor.

### Lisans planından ÇAP tahmini YAPILMIYOR

Sandbox verisinde 127 programın *lisans* planı var, **ÇAP planı yalnız
BLG'de**. Lisans planından "ÇAP'ta şu kadar kalır" demek sayıyı iki katından
fazla şişirirdi — BLG ÇAP 59.5 kredi, BLG lisans ~140. Planı çekilmemiş
programlar seçeneklere değil ayrı bir listeye giriyor, sebebiyle birlikte.
`make all-plans` bu listeyi doldurur.

## ★ Telefon düzeni (yapılacaklar 4.1)

Izgaranın `min-width`'i 660px; telefonda yana kaydırmadan okunmuyordu.
700px altında ızgara gizleniyor, yerini **gün gün dikey liste** alıyor.

★ Listenin ızgaraya göre bilinen zayıflığı çakışmayı göstermemesi — saatler
yan yana değil alt alta. Bunu kabul edip geçmek yerine çakışma **ayrıca
hesaplanıyor**: aynı gün içinde kesişen dersler kırmızıyla ve "ÇAKIŞIYOR"
etiketiyle işaretleniyor. İki test sınırı kilitliyor — kesişenler işaretlensin,
**bitişikler işaretlenmesin** (`<` yerine `<=` yazmak doğru bir programı
yanlış diye gösterirdi).

Aday tablosu da daralıyor: Plan ve AKTS sütunları düşüyor. Rol zaten ders
hücresindeki etikette; satıra dokununca hepsi diyalogda. Kutusunun içinde
yana kaydırmak teknik olarak çalışıyordu ama asıl iş orada yapılıyor —
kaydırarak kullanılacak bir yer değil.

## ★ Kontenjan nöbeti arayüzden (yapılacaklar 4.3)

"Kontenjanı izle" düğmesi ders diyaloğunda; darboğaz raporunda kısa "izle".

★ Düğme yalnız **arz sorunlu** derste var (açılmamış / programa kapalı).
Önşarta ya da kredi eşiğine takılan ders nöbetle çözülmez; oraya düğme koymak
işe yaramayacak bir eylem önermek olurdu.

★ Bir ters sezgi açıkça yazılıyor: izleme listesi **boşken** nöbet planındaki
191 dersi tarıyor. Yani ilk dersi eklemek listeyi genişletmiyor, **daraltıyor**.
Düğmenin yanındaki not bunu söylüyor — sessiz bırakılsaydı kullanıcı
bildirimlerin neden azaldığını anlamazdı.

## ★ İki çözülemeyen önşart kapandı (yapılacaklar 3.x)

`MST 471` ve `ROS 201` motorda `BİLİNMİYOR` diyordu. Ham veriye bakınca
ikisinin de **önşart olmadığı** görüldü — OBS önşart alanına başka şey yazmış:

```
MST 471   →  "Deniz Kazalarıve Emniyet Kültürü"    (dersin kendi ADI)
ROS 201   →  "Türkçe"                               (dersin DİLİ)
```

Doğru düzeltme bir önşart tahmin etmek değil, **"önşart yok" beyan etmek**.
Yeni `[[onsart_beyani]]` bloğu `config/denklikler.toml`'da:

```toml
[[onsart_beyani]]
ders   = "MST 471"
onsart = ""              # boş = ÖNŞART YOK  (≠ bilinmiyor)
not_   = "Katalogda önşart alanında ders adı var; önşart beyanı değil."
```

`onsart = ""` bir **iddiadır**: yanlışsa alınamayacak bir ders alınabilir
görünür. O yüzden her beyan gerekçeli ve `prereq_repair` tablosuna iz
bırakıyor — sessizce uygulanan bir kural denetlenemez.

Sonuç: **10789 dersin 4626'sında önşart var, hepsi ayrıştırıldı, 0 çözülemeyen.**

## Test kapsamı

**Mevzuat** (14) — kapsam alanı ÇAP/yandal ayırıyor · `tur` filtresi ·
**eski beyan elenmiyor** · tolerans taşınıyor · kaynak taşınıyor · projenin
kendi config'inde yedi eşik de doğrulanmış ve kaynaklı · yandal eşiği ÇAP
kapsamında yok · şartlı başarı geçme ile mezuniyeti ayrı tutuyor · beyan
yoksa eşik None · önşart beyanı boş metni "yok" sayıyor · beyan
ayrıştırıcıdan önce giriyor · beyan iz bırakıyor

**Başvuru** (16) — sıralama şartı `None` ve engel değil · `eligible` ≠ "tüm
şartlar tamam" · yandal eşiği ÇAP'a uygulanmıyor · devam/mezuniyet eşikleri
başvuru ekranına girmiyor · kredi penceresi dört sınırda · yandalda üst sınır
yok · **ÇAP planı olmayan program tahmin edilmiyor** · geçilen ders kalan işi
azaltıyor · kayıtlı program elenmiş · sıralama kalan işe göre · JSON üç
değerli işareti koruyor

**Arayüz** (6 yeni) — yandal eşikleri ÇAP öğrencisinde gizli · ikinci anadal
eşiği ikinci anadal ortalamasını kullanıyor (2.50'ye karşı 4.00) ·
hesaplanamayan eşik `None` ve gerekçeli · şartlı kural sayfaya ulaşıyor ·
başvuru taraması toplanıyor · dar ekran düzeni beyan edilmiş · **her renk
bare `:root`'ta tanımlı**

**Telefon** (4, tarayıcı) — ızgara gizli / liste görünür · yana kaydırma yok ·
çakışan iki ders işaretli · **bitişik dersler işaretli değil**

**Nöbet** (3) — uç listeyi açıp kapatıyor · boş ders reddediliyor · liste
sayfaya ulaşıyor
