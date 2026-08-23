# Faz 20 — Arayüz düzeltmeleri ve otomatik kredi tavanı

**Tarih:** 23.08.2026 · **Test:** 575 (öncesi 554)

Yedi kullanıcı isteği. Sekizincisi (**ÇAP ve yandal aynı anda**) veri modelini
değiştirdiği için ayrı faza bırakıldı — bkz. sonda.

---

## 1. Başlıktan program adı çıktı

`ÇAP Ders Planlama Raporu` → **Ders Planlama Aracı**. Araç ÇAP'a özel değil;
yandalda ve ikinci programsız kullanımda da aynı araç. Hangi programa baktığın
zaten üstteki satırda yazıyor.

## 2. Üst çubuğun arka planı şeffaf değil

Sebebi bir **yazım hatası**ydı: `background: var(--bg)` yazılmıştı, oysa jetonun
adı `--ground`. Tanımsız bir `var()` sessizce çözülmüyor ve arka plan hiç
boyanmıyor — kartlar çubuğun içinden geçiyordu.

Bu, sessizce yanlış davranan bir hata sınıfı. Tek tek düzeltmek yetmez, o yüzden
genel bir test eklendi:

```python
def test_kullanilan_her_css_jetonu_TANIMLI(dbs):
    kullanilan <= tanimli
```

Şablondaki her `var(--x)` gerçekten tanımlı olmak zorunda. Yazım hatası artık
"saydam" değil, **kırmızı test**.

## 3. Kademeler aşağı doğru

Yan yana sütunlar uzun planda yatay kaydırma istiyordu ve kademe sırası
okunmuyordu. Artık kademeler alt alta, aralarında 34px boşluk; her kademenin
dersleri kendi içinde yan yana sarıyor.

Bağlantı çizgileri de döndü: önşartın **altından** çıkıp dersin **üstüne**
giriyor. Yatay bezier bırakılsaydı çizgiler kutuların üstünden geçer, bağı
göstermek yerine karartırdı.

## 4. Kaydedilen program en üstte, ayrı bölüm

Kayıt haftasında araca dönmenin sebebi bu: *"ben ne kaydetmiştim"*. Aşağıdaki
ızgara bir **çalışma alanı** ve düzenlendikçe değişiyor; kayıtlı program ise
sabit bir kayıt. İkisi aynı yerdeyken hangisinin hangisi olduğu belirsizdi.

Bir incelik: aday havuzu **kipe göre** değişiyor ve varsayılan kip artık
"N. dönem + alttan". Kaydedilen ders o kipin havuzunda olmayabilir. Bu yüzden
şube **bütün kiplerde** aranıyor; bulunamazsa kod ve CRN yine gösteriliyor ve
"bu dönemin verisinde yok" deniyor. Sessizce eksik göstermek, kullanıcının
kaydettiğini sandığı dersi kaybetmesi olurdu. "Programa yükle" düğmesi de
gerekirse dersin bulunduğu kipe geçiyor.

## 5. Kredi tavanı GNO'dan otomatik

Elle yazılan tavan (35) GNO değiştiğinde eskiyordu ve kimse güncellemiyordu;
motor da kayıtta reddedilecek bir program öneriyordu. Artık tavan MADDE 17/2-a
hesabından geliyor.

Üç emniyet:

* Açık çağrıdaki `max_load` her zaman kazanır (testler, `--max-load`).
* `max_load_auto = false` ile elle ayar geri gelir.
* **Yalnız birim `kredi` iken.** Yönetmelik krediden konuşuyor; AKTS tavanı
  diye bir madde yok, çevirmek uydurma olurdu.

Arayüz sayının nereden geldiğini yazıyor (`limitSource`) — türetilmiş bir sayıyı
beyan edilmiş gibi göstermemek için.

## 6+7. ÇAP/yandal listesi: planı olmayan bölüm yok, BLG/BLGE tek satır

**Planı olmayan bölüm listelenmiyor.** Seçtirip sonra "plan yok" demek, seçim
sunmamaktan kötü. Hem başvuru ekranında hem program seçim penceresinde geçerli;
pencere artık plan tipine göre süzülmüş liste alıyor (`second_programs()`).

**Dil varyantı tekleştirildi:** ÇAP planı bölüme tanımlı, dile değil — `BLG` ile
`BLGE` ayrı satır göstermek kullanıcıya olmayan bir seçim yaptırıyordu.

⚠️ Yalnız **ikisi de varsa** birleşiyor. `HTAE`'nin `HTA` diye bir eşi yok;
körlemesine son harfi atmak var olmayan bir programa yönlendirirdi. Bölümün
yalnız İngilizce planı varsa o kod olduğu gibi kalıyor.

---

## Ayrı faza kalan: ÇAP ve yandal aynı anda

Araç bugün **anadal + tek ikinci program** varsayıyor: `second_program`,
`second_kind`, `second_role` — hepsi tekil. Kullanıcı ikisinin birlikte
alınabildiğini söyledi ve haklı.

İyi haber: veritabanı buna hazır — `enrollment` tablosu rol taşıyor, birden çok
kayıt tutulabiliyor. Değişmesi gereken üst katman: `collect()` iki plan
kimliği alıyor, paneller ikili, kredi tabanı/eşikler tek "ikinci program"
üzerinden hesaplanıyor.

Ayrı tutmamın sebebi, karışması muhtemel iki sayı olması: **ÇAP'ın kendi
ortalaması** ile **yandalın kendi yükü** farklı maddelerden geliyor
(Madde 18 / Madde 22) ve tek "ikinci program" kutusuna sıkıştırılırsa
biri öbürünün kuralıyla değerlendirilir — tam olarak bu araçtaki en pahalı
hata türü.
