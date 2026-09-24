# Faz 58 — Yol haritası geçmişten öğreniyor, yaz okulu, ÇAP ortalaması, resim

*24.09.2026 · kullanıcı: "continue your work to improve" (ardından yeni PR).*

Faz 57'nin araştırma listesinden (`fikirler.md` "Faz 57 araştırması") beş
kalem, yol haritasının doğruluğunu artıranlar önce:

| | Ne | Neden önce |
|---|---|---|
| Y.2 | Dersin açıldığı yarıyıl **geçmiş not dağılımından** | Vitrinde 6 ÇAP dersinin mevsimi hiçbir planda yoktu, "her dönem açılır" sayılıyordu — plan olduğundan iyimserdi |
| Y.3 | **Yaz okulu** "ya yazın alsaydım" | Alttan ders taşıyan ÇAP öğrencisinin en önemli tıkanıklık çözücüsü (fikirler §2.3) |
| Y.4 | "Bu dönem şunu alırsan" yükü aşıyorsa **hangi ders çıksın** | Faz 57 "bir dersi çıkarman gerekir" deyip bırakıyordu — kararın en zor yeri |
| Y.6 | GNO hedefi **ÇAP'ın kendi ortalaması** için de | Faz 57 bu eşiği "burada yok" diye dışarıda bırakmıştı |
| Y.5 | Haftalık programın **resmi (PNG)** | Program kurucularının en çok paylaşılan çıktısı; bizde yoktu |

Testler **1255 → 1270** (+15), 4 atlandı. Geri alma deneyi:
dokuz kuralın **dokuzu** geri konunca kendi sebebiyle kırmızı (§6).

---

## 1. ★★ Mevsim geçmişten (`yolharitasi.gecmis_mevsimleri`)

Not dağılımı kaynağı (Faz 38) tek istekte bir akademik yılın **bütün**
yarıyıllarını veriyor — Güz, Bahar ve Yaz. O yıl verisi olan bir derste bir
yarıyılın hiç görünmemesi, o yarıyıl not açıklanmadığı demek. Yani "hangi
yarıyıl verildi" sorusu veriyle cevaplanabiliyor.

### ⚠️ Bütünlemeci tuzağı

"Notu var" = "açıldı" sayılamaz. Faz 38b ölçmüştü: Güz dersinin Bahar
dağılımı çoğunlukla birkaç bütünlemeci demek (BLG 212: Baharda n=2, ikisi
de FF). Bunu açılış saysaydık her Güz dersi Baharda da açılır görünür ve
yol haritası olduğundan erken bitiş gösterirdi.

Eşik **yıl içinde**: bir Güz/Bahar yarıyılı hem **≥5 öğrenci** hem de o
akademik yılın en kalabalık yarıyılının **≥¼'ü** ise verilmiş sayılıyor.

* Mutlak taban küçük bütünlemeciyi ayıklıyor (BLG 335E: Güz 80, Bahar 3).
* Oran büyük dersin bütünlemecisini ayıklıyor (Güz 200, Bahar 12 — taban
  geçiliyor, oran geçilmiyor). Test ikisini ayrı ayrı tutuyor.
* Karşılaştırma yıl içinde: başka yılın büyük Güz sınıfı, yalnız Bahar
  verisi olan bir yılı ezmiyor.
* Yaz ayrı: yalnız mutlak taban (yaz sınıfları doğası gereği küçük).

### Nasıl kullanılıyor

| Durum | Sonuç |
|---|---|
| Plan mevsim söylemiyor, geçmiş tek yarıyıl diyor | O yarıyıl (`seasonSource: "gecmis"`) |
| Plan söylemiyor, geçmiş iki yarıyıl diyor | Her dönem — ama artık **bilinen** her dönem, "mevsimi bilinmiyor" sayılmıyor |
| Plan bir mevsim, geçmiş öbürünü de gösteriyor | İkisi de açık, **not düşülüyor** ("geçmişte Güz'de de verildi") — hangisinin doğru olduğunu bilmiyoruz, birini seçmek uydurmak olurdu |
| Dağılım hiç yok | `None` — tahmin yok, eskisi gibi |

Varsayım kutusuna satır giriyor: kaç dersin mevsiminin geçmişten okunduğu,
eşik ve *"geçen yıl açılması bu yıl açılacağı demek değil"*.

### Vitrinde ne değişti

BLG 335E (Güz 80 + Baharda 3 bütünlemeci) artık yalnız Güz, BLG 336E yalnız
Bahar. Sonuç: ÇAP'ın tahmini bitişi **2026-2027 Güz → 2026-2027 Bahar** — bir
dönem geç, ama doğru. Ve 2026-2027 Güz kartı artık *"ÇAP yarıyıl tabanına 6
kredi eksik — o dönem alınabilir yeterli ÇAP dersi yok"* diyor: iki dersin
mevsimi ayrışınca o Güz yalnız bir ÇAP dersi alınabiliyor. Eski plan bu
yönetmelik sorununu "her dönem açılır" varsayımıyla gizliyordu.

⚠️ Yolda bir vitrin hatası: dağılımların `year_name` tablosu elle yazılmıştı
ve bir yıl kaymıştı (`202510` → "2025-2026"; doğrusu 2024-2025, Faz 38).
Artık koddan türetiliyor.

## 2. ★★ Yaz okulu — "ya yazın alsaydım"

`yolharitasi.kur(..., yaz="GEO 341E")`: ders **ilk yaz okulunda** alınmış
sayılıyor. İlk yaz, ilk Bahar'ın arkası — bu dönem Güz'se bir sonraki
Bahar'dan sonra, Bahar'sa hemen arkasında (iki durum da test ediliyor).

* **Uygulanan:** önşart (yaza kadar geçilmiş sayılanlarla) ve kredi eşiği.
* **Uygulanmayan:** mevsim ve "plandaki dönemden önce değil" kuralı — yaz
  okulu tam da öne almak için kullanılıyor.
* Yaz dersi önündeki Bahar'ın sırasını alıyor: bir sonraki Güz'de geçilmiş.
  Takvimde Bahar kartının hemen arkasında kesikli bir "yaz okulu" kartı.

Arayüz yalnız geçmişte yazın **gerçekten** açılmış (≥5 öğrenci) dersleri
deniyor (en çok 8) ve yalnız bitişi değiştirenleri yazıyor. Vitrinde:

> **Yaz okulu fırsatı** — GEO 341E Engineering Surveying — 2024-2025 Yaz'da
> açıldı (14 öğrenci); **2025-2026 Yaz** alırsan anadal **2 dönem erken**
> biter (2026-2027 Bahar). *Geçen yaz açılması bu yaz açılacağı demek değil;
> yaz okulunun ücreti, kontenjanı ve kredi sınırı bu hesapta yok.*

Düğme yok: yaz okulu bu dönemin programına eklenemez. Kararın ne
kazandırdığını söylüyoruz.

## 3. ★ Hangi ders çıksın

"Bu dönem şunu alırsan" satırı yükü aşıyorsa, programdaki her ders tek tek
çıkarılıp harita yeniden kuruluyor. Öneri: yükü sınıra indiren (tek başına
yetmeyen ders denenmiyor) ve kazancı **koruyan** çıkarma; tam koruyan
yoksa en az kaybettiren — kayıp yazıyor.

⚠️ **ÇAP yarıyıl tabanını bu dönem bozan çıkarma önerilmiyor.** Vitrin
öğrencisi tam 9 kredi ÇAP dersi alıyor (taban 9). Koruma geri alınınca
ölçüldü: öneri **BLG 222E** (ÇAP) oluyordu — kazanç kaybı yok, eşitlikte
"anadal dışı önce" kuralı onu seçiyordu. Yük sınırını tutturmak için
yönetmelik ihlali önermek olurdu.

Vitrinde: *"GEO 315E çıkarsa kazanç **korunuyor** (o ders sonraki dönemlere
yerleşiyor)"* ve **GEO 315E çıkar, dene** düğmesi: dersi çıkarıyor (geri
alınabilir: "Geri al: GEO 315E çıkarıldı"), ders programına geçip GEO
341E'nin şube penceresini açıyor.

Bedeli: en çok 2 aday × programdaki ders sayısı kurulum. Vitrinde bütün
sayfa kurulumu (harita + 1 aday + 8 çıkarma + 1 yaz) **0,1 s**.

## 4. GNO hedefi — ÇAP'ın kendi ortalaması

"ÇAP mezuniyeti — ikinci anadal ortalaması ≥ 2.00" genel GNO'yu değil,
yalnız ÇAP planındaki derslerin ortalamasını soruyor (`_threshold_info`, 2.
incelik). Faz 57 bu satırı "burada yok" diye dışarıda bırakıyordu.

Artık `_ikinci_gno_tabani()` aynı alt kümeyi (`R.plan_codes`, dil eşi dahil)
ve aynı `POL.gpa`'yı veriyor; arayüz bu dönemki programdan **yalnız ÇAP
planındaki** dersleri sayıyor. Vitrinde: *"2.00 — ÇAP mezuniyeti — ikinci
anadal ortalaması · ≥ 1.50 · Yalnız ÇAP dersleri (bu dönem 9 kredi): her
dersten en az DC alırsan yeter."* Bu dönem hiç ÇAP dersi yoksa "bu dönem
değişmiyor" ve bugünkü ÇAP ortalaması.

★ Yolda bir birleşme hatası önlendi: Faz 57'de hedefler yalnız eşik
değerine göre birleşiyordu. ÇAP'ın 2.00'ı ile genel mezuniyetin 2.00'ı AYNI
satıra düşerdi — iki ayrı ortalamanın iki ayrı şartı. Anahtar artık taban +
eşik; satırlar `data-taban` taşıyor.

## 5. Programın resmi (PNG)

Araç çubuğunda **Resim (PNG)**. `<canvas>`a tarayıcıda çiziliyor; dış
kütüphane yok, hiçbir yere gönderilmiyor.

* Renkler sayfanın: jetonlar `:root`tan, blok zemini ve yazısı ızgaradaki
  bloğun **hesaplanmış** renginden (ton merdiveni dahil). Resim ekrandaki
  temayla aynı — gece temasında gece resmi.
* ⚠️ `color-mix()` sonucunu canvas'a veremeyen tarayıcıda atama sessizce
  düşer; önce jeton atanıyor, o kalıyor.
* İçinde yalnız ders, şube, saat, bina (çevrimiçi şubede "çevrimiçi"),
  meşgul saatler ve saati ilan edilmemiş dersler. **Not, transkript, GNO
  yok** — test fonksiyonun gövdesinde bunları arıyor.
* Altında "CRN'leri kayıttan önce OBS'de doğrula" ve oluşturulma tarihi.

## 6. Testler ve geri alma deneyi

`tests/test_faz58_gecmis_ve_yaz.py` (15 test) + Faz 57 testlerinin
güncellenen iki doğrulaması (GNO formülü `gnoTabani`na taşındı; E2E yalnız
genel satırları okuyor).

| Geri konan | Kırmızı |
|---|---|
| Oran eşiği yok | `test_BUYUK_dersin_BUTUNLEMECISI_ORANLA_ayikliyor` |
| Karşılaştırma yıl dışı (bütün yılların en büyüğü) | `test_KARSILASTIRMA_YIL_ICINDE` |
| Yaz eşiği yok | `test_YAZ_yalniz_GERCEK_sinifsa`, `…YAZ_ADAYLARI…` |
| Geçmiş hiç kullanılmıyor | `…PLAN_SUSUYORSA…`, `…celisirse…`, uçtan uca |
| Plan–geçmiş çelişkisinde ek mevsim yok | `…celisirse_IKISI_DE_acik` |
| Bu dönem Bahar'sa yaz hemen arkasında değil | `test_BU_DONEM_BAHARSA_yaz_HEMEN_arkasinda` |
| ÇAP tabanı koruması yok | statik + uçtan uca (öneri ÇAP dersi oluyor) |
| ÇAP hedefi bütün programı sayıyor | uçtan uca (≥ değeri) |

⚠️ İlk turda oran eşiğinin geri alınması **yeşil kaldı**: testteki
bütünlemeci (3 kişi) zaten mutlak tabanın altındaydı, oranı hiçbir test
ölçmüyordu. Ayrı bir test eklendi (Güz 200, Bahar 12).

Deneyler `PYTHONDONTWRITEBYTECODE=1` ile ve `__pycache__` silinerek
koşuyor (Faz 57'deki `.pyc` dersinden).

⚠️ Tam paket bir hatamı yakaladı: resmin altına aracın adını elle
("İTÜ DEPAR") yazmıştım. `test_ad.py` ad değişince sayfada eski adın
kalmadığını ölçüyor; ad artık `__AD_TAM__` yer tutucusundan geliyor.

## 7. Ne yapılmadı

* **Y.1 "Ya ÇAP'ı başka bölümde yapsaydım"** — motor hazır (`kur` herhangi
  bir plan listesiyle çalışıyor), ama başvuru ekranındaki her aday için
  kabul yarıyılı varsayımı gerekiyor. Ayrı faz.
* Yaz okulu yalnız **tek ders** için deneniyor; iki dersin birlikte yazda
  alınması ve yaz okulunun kredi sınırı (mevzuattan doğrulanmadı) yok.
* Resimde "dolu / son N" rozeti yok — kontenjan anlık, resim kalıcı.
