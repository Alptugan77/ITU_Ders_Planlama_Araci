# Faz 41 — Yeni kullanıcı: bilmediğini bilen bir ekran

*16.09.2026 · kullanıcı: "başka eklenebilecek şeyleri düşün ve ekle, bunu
yeni bir kullanıcı açısından da düşünerek yap"*

Yöntem tahmin değil **yürüyüş**: ayar dosyası olmayan, transkripti olmayan,
ama gerçek kataloğu (10792 ders, 3417 açık şube) olan bir kurulum açıldı ve
tarayıcıda adım adım ilerlendi — tıpkı siteyi ilk açan bir öğrenci gibi.

Çıkan üçünün ortak yanı var: üçü de aracın **bilmediği bir şeyi biliyormuş
gibi göstermesiydi**. Yani kapatılanlar bir "arayüz cilası" değil, projenin
ana kuralının yeni kullanıcı tarafındaki açıkları.

Testler **1038 → 1045** (1043 geçti, 2 atlandı).

---

## Önce: iyi çalışan yerler

Faz 24/26'nın işi tutmuş, dokunulmadı:

* İlk ekran **tek zorunlu adım** istiyor ("Bölümünü seç · 10 saniye"),
  gerisi kilitli ve "isteğe bağlı" diye işaretli.
* Kredi bölümü transkript yokken **kendi kendini şikâyet ediyor**:
  *"transkript yok — en düşük band varsayıldı: 22"* ve *"GNO bilinmiyor…
  ‘GNO 0.00’ hesaplanmış bir değer değil"*.
* Bölüm çubuğu, boş bölümleri listelemiyor.

---

## A. ★★ "Kaçıncı dönemdesin" bilinmiyor — ama program bunu söylemiyordu

Ölçüm: yalnız bölümünü seçen (`HTAE`) bir öğrenciye kurulan **14 derslik**
haftalık programın plan dönemleri:

| plan dönemi | 1 | 2 | 3 | 4 | 5 | 7 | 8 |
|---|---|---|---|---|---|---|---|
| ders | 4 | 1 | 1 | 1 | 2 | 3 | 2 |

Yani birinci sınıf dersi **FIZ 101E** ile yedinci dönem dersi **GEO 401E
(Physical Geodesy)** ızgarada yan yana duruyordu — ve ekranda bunu açıklayan
**tek satır yoktu**.

⚠️ Motor yanlış değil. Dönem bilinmeyince plandaki her açık ders adaydır;
üretilen şey "alabileceklerinin tamamı". Yanlış olan **sunum**: başlık
"Haftalık program", ve kullanıcı bunu *"araç bana bunları öneriyor"* diye
okuyor.

⚠️ **Dönem tahmin edilmedi.** Transkript varsa `infer_term` zaten çıkarıyor;
hiçbir şey yokken bir sayı uydurmak bu projenin kaçındığı şeyin ta kendisi
olurdu. Bunun yerine: dağılımı **yaz**, düzeltmeyi **bir tık** uzağa koy.

Programın üstünde artık şu duruyor:

> **Kaçıncı dönemde olduğunu bilmiyorum.**
> Bu yüzden aşağıdaki program planın **7** ayrı döneminden ders karıştırıyor:
> **1.** dönemden 4 · **2.** dönemden 1 · **3.** dönemden 1 · **4.** dönemden 1
> · **5.** dönemden 2 · **7.** dönemden 3 · **8.** dönemden 2.
> Alabileceklerinin tamamı bu — **bu dönem almanı önerdiğim liste değil**.
> [Dönemi seç] *5 saniye — sonra "N. dönem + alttan" kipi açılıyor.*

Sayı dökülüyor, çünkü bu repoda tekrarlayan ders: "bazı dersler farklı
dönemden" diye yazılan uyarı genel bir uyarı sanılıp geçiliyor (bkz. Faz 18,
`_term_note`).

Ölçülen sonuç — düğmeye basıp 3. dönem seçilince:

| | önce | sonra |
|---|---|---|
| ızgaradaki ders | 14 | **10** |
| kaç ayrı plan dönemi | **7** | **3** (1–3) |
| kip sayısı | 1 | 2 ("N. dönem + alttan" açıldı) |

---

## B. ★ Boş kip kutusu 2×2 piksel SİYAH NOKTA olarak çiziliyordu

`.modes` çerçeveli bir kutu. Kip düğmeleri **yalnız dönem biliniyorsa** iki
tane oluyor; tek kip varsa `renderModes` içeriği boşaltıyor
(`MODES.length < 2 → innerHTML ""`). Geriye çerçeve kalıyor: açık şemada
`--border-strong` **#141821**, yani neredeyse siyah.

Sonuç: "HAFTALIK PROGRAM" başlığının hemen altında, sebepsiz bir nokta.

⚠️ Bunu **yalnız yeni kullanıcı görebiliyordu.** Dönemi girilmiş hiçbir
kurulumda kutu boşalmıyor — o yüzden 1038 testin ve aylardır kullanılan
arayüzün gözünden kaçmış. Tek satır: `.modes:empty{display:none}`.

---

## C. ★ "0. dönem (tahmin)" — yapılmamış bir tahmin

Dönem diyaloğu, dönem bilinmezken de şunu yazıyordu:

> Şu an kullanılan: **0. dönem** (tahmin).

İki ayrı yanlış tek cümlede: **"0. dönem" diye bir şey yok**, ve transkript
yokken çıkarılacak bir şey olmadığı için ortada bir **tahmin de yok**.
Artık bilinmiyorsa bilinmediğini yazıyor ve nedenini söylüyor.

---

## D. Ne yapılmadı — ve neden

* **Dönemi zorunlu adım yapmak.** Faz 26 bilerek "tek zorunlu adım"
  kurmuştu; ikinci bir kapı koymak o kararı geri alırdı. Uyarı, kapı
  koymadan aynı işi görüyor.
* **Dönemi uydurmak (ör. "yeni kullanıcı = 1. dönem").** Kayıt donduran,
  yatay geçişle gelen, yaz okulu okuyan öğrencide sessizce yanlış olurdu.
* **Öneriyi alttan derslere doğru eğmek.** Puanlamayı bilinmeyen bir
  varsayımla oynatmak, uyarıyı okunmaz bir "akıllı" davranışa çevirirdi.
  Motor ne yaptığını söylüyor; kullanıcı bir tıkla düzeltiyor.

---

## E. Testler

`tests/test_faz41_yeni_kullanici.py` (7 test):

| test | neyi tutuyor |
|---|---|
| `test_DONEM_bilinmiyorsa_program_bunu_SOYLUYOR` | ★★ uyarı var ve dönem biliniyorken SUSUYOR |
| `test_donem_uyarisi_OLCULEN_dagilimi_yaziyor` | sayı dökülüyor, "öneri değil" deniyor |
| `test_donem_uyarisinda_TEK_TIKLIK_cikis_var` | dürüstlük yetmez, çıkışı da olmalı |
| `test_donem_bilinmiyorken_TAHMIN_iddia_EDILMIYOR` | "0. dönem (tahmin)" geri gelemez |
| `test_BOS_kip_kutusu_cizilmiyoR` | 2×2 nokta |
| `test_iki_uyari_YAN_YANA_okunabiliyor` | arz uyarısından ayrı renk + boşluk |
| `test_UCTAN_UCA_donem_bilinmiyor_uyarisi_ve_cikisi` | ★★ tarayıcıda bütün akış |

Uçtan uca test yeni kullanıcının durumunu birebir kuruyor: `settings.toml`
var ama içinde `donem` **yok**; plan 1. ve 6. dönemden birer ders taşıyor.
Uyarının çıktığı, sayıyı yazdığı, kip kutusunun çizilmediği, düğmenin
diyaloğu açtığı ve dönem seçilince uyarının kaybolup kipin geldiği — hepsi
tek akışta doğrulanıyor.

İki düzeltme geri konulup **kırmızıya döndükleri görüldü** (uyarı çağrısı
silindiğinde ve `.modes:empty` kaldırıldığında uçtan uca test de düşüyor).
