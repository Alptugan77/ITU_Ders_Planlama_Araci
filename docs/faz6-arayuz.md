# Faz 6 — Arayüz

> ⚠️ Bu belgedeki bütün sayılar **örnektir**. Depoda kimsenin gerçek notu
> ya da ortalaması yer almaz — kişisel veri `data/` altında kalır ve
> `.gitignore` ile dışarıda tutulur.


```bash
make ui          # data/itucap.html üretir ve açar
make ui ARGS="--ects 24 --count 5"
```

Tek dosya, sunucu gerekmez, çift tıkla açılır. Google Fonts dışında hiçbir dış
kaynağa bağlanmaz; veri HTML'in içine gömülüdür.

## ⚠️ Kişisel veri

Bu dosya **notlarını ve ilerlemeni içerir**. `data/` altında durur, `.gitignore`
kapsamındadır (`data/*.html`). Paylaşma, bir yere yükleme.

Bu yüzden arayüz bilerek **yerel bir dosya** olarak tasarlandı — bir web
servisine, paylaşılabilir bir bağlantıya ya da buluta konmuyor.

## Tasarım kararları

Bu bir doküman değil, **panel**: okunmuyor, taranıyor. O yüzden ağırlık
tipografide değil bilgi mimarisinde.

* **İki renk, tek anlam.** Yeşil = anadal, kehribar = ÇAP. Bu eşleme panelde,
  ızgarada, aday listesinde, her yerde aynı. Renk dekorasyon değil, veri.
* **Önce özet, sonra ayrıntı.** Yüzdeler ve AKTS üstte; ızgara ortada; aday
  listesi, darboğaz ve kademeler altta.
* **Durum biçimle de kodlanıyor.** Engel türleri çip rengiyle (arz = kırmızı,
  önşart = kehribar), bitmiş dersler üstü çizili, "şu an alınabilir" vurgulu.
* **Rakamlar hizalı.** Kod, saat, CRN ve AKTS için `tabular-nums` mono yüz.
* Açık ve koyu tema, üç durumun (açık / koyu / sistem) hepsi için tanımlı.

## Haftalık ızgara — yarım saatlik satırlar

İlk sürüm saatlik satır kullanıyordu ve **üç ders görünmüyordu**: İTÜ dersleri
`:30`'da başlayıp `:29`'da bittiği için `08:30–11:29` ile `11:30–13:29` aynı
saat kutusuna düşüyor, ikincisi `rowspan` altında kayboluyordu.

Izgara 30 dakikalık satırlara geçti. Saat etiketi yalnız tam saatlerde,
yarım saat çizgileri noktalı.

**Saati ilan edilmemiş dersler** (proje dersleri, "İlgili Bölümce Açıklanacak")
ızgarada gösterilemez. Bunlar ızgaranın altında ayrı bir şeritte listeleniyor —
yoksa başlıkta "8 ders" yazıp 5 blok göstermiş oluyorduk. Test bu değişmezi
koruyor: `zamanlı + zamansız == toplam`.

## ★ Program düzenlenebilir (20.08.2026)

İlk sürüm öneriyi **okunur** gösteriyordu: motorun ürettiği üç program, üç
sekme, bitti. Ama motorun karşılaştırma sonucu şunu söylemişti — havuz içi
tercih zevk meselesi (`GEO 464E` mi `GEO 458E` mi), motor eşit puanlılardan
kontenjanı bol olanı alıyor. Bu kararı kullanıcıdan almanın yolu `--pin`
bayrağıydı: terminale dön, komutu yeniden yaz, HTML'i yeniden üret. Arayüz
zaten ekranda dururken bu saçma.

Artık ızgara **düzenlenebilir bir durum**. `sel = [{course, crn}]` sekmeden
başlatılıyor, tıklamalarla değişiyor, her değişiklikte ızgara + toplamlar
yeniden çiziliyor.

| Tıklanan | Açılan | İçerik |
|---|---|---|
| Ders bloğu | `courseDialog` | aynı dersin **başka şubeleri**, **yerine başka ders**, "Programdan çıkar" |
| Boş hücre | `slotDialog` | "bu saat civarı" (±2 saat) ve "{gün} günü, başka saatte" |
| Aday satırı | `addDialog` | o dersin şubeleri |

Üç kural, ekran tarafında da motorla **aynı**:

1. **Çakışan ders düşer.** Seçim engellenmiyor — çakıştığı ders programdan
   çıkarılıyor ve seçenek satırında önceden yazıyor: `çıkarılır: GEO 401E`.
2. **Aynı havuzdan tek ders.** `slotId` eşitse öteki çıkarılıyor
   (`çıkarılır: HUK 217 (aynı havuz)`).
3. **Kredi tavanı uyarı, engel değil.** 35 aşılırsa toplam kırmızıya dönüp
   "aşıldı" yazıyor; seçim yine yapılabiliyor — istisnalar OBS'de olabiliyor,
   arayüz kullanıcı adına karar vermiyor.

Düzenleme yapıldığında "değiştirildi" çipi ve **Öneriye dön** düğmesi çıkıyor;
sekmeye tekrar tıklamak da o öneriye sıfırlıyor. Motorun puanı canlı
güncelleniyor, yani kullanıcı kendi tercihinin kaça mal olduğunu görüyor
(`1083.2` → `1023.2`).

### Bir hata: havuz engelini gizlemek

İlk denemede aynı havuzdan bir ders zaten programdaysa, o havuzun öbür dersleri
diyalogda **hiç gösterilmiyordu**. Çarşamba'da 19 adaydan 18'i görünmez oldu.
Yanlış olan varsayımdı: seçilince zaten takas ediliyor, engel değil. Artık
gösteriliyorlar — yanlarında ne çıkacağı yazılı.

## Etkileşim

* **Öneri sekmeleri** — programlar arasında geçiş, ızgara yeniden çizilir
* **Derse tıkla** → şube değiştir, yerine başka ders koy, programdan çıkar
* **Boş hücreye tıkla** → o saate uyan adaylar, seçince programa girer
* **Tema** düğmesi — sistem temasını ezer
* Klavye: bloklar ve boş hücreler `Tab` ile gezilir, `Enter`/`Space` açar

> Faz 7 bu arayüzün üstüne kredi eşiği kutusu, program kipi anahtarı ve
> ilerleme projeksiyonu ekledi; kayıt da "pano"dan **kurum belgesine** döndü.
> Bkz. `docs/faz7-kurallar-ve-kipler.md`.

## Test kapsamı

195 test (Faz 6'dan 17'si arayüz, Faz 7'den 12'si daha).

**Veri sözleşmesi** (JS çalıştırmadan, her makinede):

* JSON gömülüyor ve geçerli; `__DATA__` yer tutucusu kalmıyor
* Google Fonts dışında dış kaynak yok
* Üç tema durumu da tanımlı, `body` kendi zeminini boyuyor
* **Programdaki her ders ya ızgarada ya saatsiz listede** — kaybolan ders yok
* Aday **tüm şubelerini** taşıyor — yoksa "başka şube" diyaloğu boş açılır
* Önerideki CRN adayın şube listesinde **var** — yoksa ızgara sessizce boş çizer
* Havuz kimliği (`slotId`, `pool`) ve kredi/AKTS istemciye ulaşıyor
* Şablon etkileşimi bağlıyor: tıklanabilir hücre, üç diyalog, geri alma

**Tarayıcıda davranış** (Playwright; proje bağımlılığı değil, yoksa atlanır):

* Sayfa JS hatasız açılıyor, ızgarada blok var
* Boş hücre aday listeliyor; seçim ızgarayı değiştiriyor ve "Öneriye dön" çıkıyor
* Ders çıkarma + sıfırlama başlangıç durumunu geri getiriyor
* Arka arkaya seçimlerden sonra **çakışma yok**
* Aynı havuzdan iki ders programda birlikte duramıyor
