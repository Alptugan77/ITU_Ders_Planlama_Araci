# Faz 45 — Dersi saate kilitle, öneriler etrafında kurulsun

*17.09.2026 · kullanıcı: "dersleri saate kitleme ve önerilerin onun etrafında
şekillenmesi özelliği getirir misin"*

Testler **1071 → 1085** (1083 geçti, 2 atlandı).

---

## A. Neden yeni bir şey

Araçta zaten iki "bu ders dursun" mekanizması vardı ve **ikisi de saati
tutmuyordu**:

| | ne diyor | şubeyi kim seçiyor |
|---|---|---|
| `watch_courses` (kontenjan nöbeti) | "bu dersin kontenjanını izle" | — |
| motor `pinned` | "bu ders programda olsun" | **motor** |
| **`kilitli` (yeni)** | **"bu ders TAM BU SAATTE olsun"** | **sen** |

Motor bir dersi programda tutup şubesini kaydırabiliyor: daha ucuz bir şube
bulunca öneri yenileniyor ve beğendiğin saat gidiyor. Kilit tam bunu
engelliyor.

---

## B. Ölçüm — kilit gerçekten şekillendiriyor mu?

Gerçek veriyle (78 aday, 16 derslik taban program). `BLG 351E` Çar 12:30'dan
**Pzt 14:30'a** kilitlendi:

| ders | kilitsiz | kilitliyken |
|---|---|---|
| **BLG 351E** | Çar 12:30–14:29 | **Pzt 14:30–16:29** ← kilit |
| ATA 121 | Sal 10:30 | Çar 13:30 |
| ATA 122 | Pzt 15:30 | Sal 10:30 |
| GEO 401E | Pzt 13:30 | **programdan çıktı** (kilitli saatle çakışıyor) |
| **toplam** | 16 ders · 22.5 kredi | 15 ders · 20.5 kredi |

Yani istenen şey oluyor — ama **kilit bedava değil**. Altı dersin üzerinde
denendi: 3 denemenin 3'ünde de kilit tuttu, ortalama **1.0 başka ders kaydı**,
ders sayısı 16 → 15.7'ye indi. Bu maliyet arayüzde görünüyor (kredi/ders
sayısı zaten ekranda, kilit şeridi de sebebi söylüyor).

---

## C. İki tasarım kararı — ikisi de ölçümden çıktı

### C1. Kilit SERT kısıt

Yumuşak olsaydı (yalnız sıralamayı etkileseydi) motor kilidi sessizce yok
sayabilirdi ve kullanıcı "kilitledim ama değişti" derdi. Sert olduğu için
**çelişen kilitler sonucu boşaltıyor**. Ölçüldü: `BLG 212E@12486` ile
`ATA 121@10136` (çakışan şubeler) birlikte kilitlenince DEPAR kipinde
**3 → 0 program**.

Bu yüzden boş sonuç *sebebini söylemek zorunda*:

```
ÖNERİ 1 …                    öneri üretilemedi — 2 kilit yüzünden

  1 ders saate kilitli. …
  ┌ Bu kipte hiçbir program kurulamadı — bu kipte bağlayan 2 kilit
  └ (ATA 121, BLG 212E) birbiriyle ya da meşgul saatinle çakışıyor.

  [ATA 121 · CRN 10136 ✕] [BLG 212E · CRN 12486 ✕] [hepsini aç]
```

Sadece "öneri üretilemedi" deseydik kullanıcı dönemi suçlardı — bu repoda
tekrarlayan hata (Faz 25: havuz engelini gizlemek; Faz 44: takasları
ekleme gibi göstermek).

### C2. Kilit yalnız O KİPİN havuzundaki derse bağlanır

Arayüzün iki kipi (DEPAR / "N. dönem + alttan") **ayrı aday havuzu**
kuruyor. Aynı ölçümde `ATA 121`, dönemlik havuzda hiç yok. Kilidi orada da
zorunlu saysaydık o kip de topyekûn boşalırdı:

| kip | ATA 121 aday mı | kilitli sonuç |
|---|---|---|
| 5. dönem + alttan | hayır | **3 öneri** (BLG kilidi tutuyor, ATA kapsam dışı) |
| DEPAR | evet | 0 öneri (iki kilit çakışıyor — doğru sonuç) |

Ders masada değilse kilit "yok sayılmıyor", **kapsam dışı**. Ama ders
havuzdayken CRN kapanmışsa kilit sert kalıyor ve bu **söyleniyor**
(aşağıda).

---

## D. Tutmayan kilit gizlenmiyor

Dönem değişince ya da şube kapanınca kilit karşılıksız kalabiliyor. Satırı
sessizce düşürmek en kolayı olurdu; o zaman kullanıcı *"kilitlemiştim,
saati neden kaydı?"* diye sorardı — ya da daha kötüsü, hiç sormazdı.
İki ayrı cümle var, çünkü iki ayrı durum:

* `neden: "sube"` → **CRN bu kipte açık değil**
* `neden: "ders"` → **bu ders artık aday listesinde yok**

Yayınlanan statik sitede (temiz kurulum, program seçilmemiş) bu yol
kazara ölçüldü ve doğru çalıştı: kilit yazıldı, yenilemeden sonra durdu ve
şerit *"GEO 315E kilidi tutmuyor — bu ders artık aday listesinde yok"*
dedi.

Bir de **ayrışma** durumu var: kilitli bir dersin şubesini elle
değiştirirsen kilit *taşınmıyor* (ayara sessizce yazmak istemedik). Şerit
bunu söylüyor ve taşımayı tek düğmeye indiriyor:

```
ATA 121 ekranda CRN 10123, kilit CRN 10136 — [kilidi buraya taşı]
```

---

## E. Görsel dil

⚠️ Kilit işareti **renk değil**. Bu arayüzde renk *hangi programdan*
olduğunu (anadal/ÇAP/yandal), ton *hangi ders* olduğunu söylüyor (Faz 40).
Üçüncü bir anlamı renge yüklemek üçünü birden okunmaz yapardı. Kilit iki
şeyle görünüyor:

* sol kenar **6px**'e kalınlaşıyor,
* köşeye küçük bir **asma kilit** çiziliyor (inline SVG, `currentColor`).

İkisi birden, çünkü dar hücrede kalın kenar tek başına fark edilmiyor,
10px'lik simge de tek başına kayboluyor.

`make ui` (sunucusuz tek dosya) çıktısında kilit **uygulanıyor** ama
açılamıyor — orada yazacak yer yok. Sahte bir düğme koymak yerine şerit
bunu yazıyor (aynı ilke: `watchButton`).

---

## F. Nereye dokunuldu

| dosya | ne |
|---|---|
| `recommend.py` | `build_schedules(locked=…)` — havuz kapsamı + şube süzgeci |
| `config.py` | `Settings.kilitli: list[str]` (`"DERS@CRN"`) + `_EDITABLE` |
| `server.py` | `toggle_lock()` + `/api/kilit` (bir derste tek kilit) |
| `ui.py` | `_kilit_ayikla` / `_kilit_bilgisi`, kilit şeridi, ızgara işareti, diyalog düğmesi, boş sonucun sebebi |

Ayar biçimi `"GEO 315E@13601"`: **CRN saklanıyor, saat değil.** Saat CRN'in
bir özelliği; saati saklasaydık şube değişince iki kaynak birbirini
tutmazdı.

---

## G. Testler

`tests/test_faz45_saate_kilit.py` (14 test):

| test | neyi tutuyor |
|---|---|
| `test_motor_KILITLI_SUBEYI_kullaniyor` | ★★ isteğin çekirdeği |
| `test_kilit_dersi_PROGRAMDA_TUTUYOR` | dersi düşürüp kilidi "ihlal etmemiş" sayamaz |
| `test_program_KILIDIN_ETRAFINDA_kuruluyor` | ★★ Pzt kilidi komşuyu düşürüyor, Sal kilidi düşürmüyor |
| `test_HAVUZDA_OLMAYAN_ders_kipi_BOSALTMIYOR` | ⚠️ C2'deki tuzak |
| `test_KAPANMIS_SUBE_kilidi_SESSIZCE_kaymiyor` | sert kısıt, sessiz kaydırma yok |
| `test_ayar_KALICI_ve_yazilabilir` | ayar yazılıyor, yorumlar duruyor |
| `test_ayirma_DERS_ve_CRN` | biçim ayrıştırma; bozuk satır motora girmiyor |
| `test_TUTMAYAN_kilit_listeden_DUSMUYOR` | ★★ iki ayrı sebep, iki ayrı cümle |
| `test_uc_kilidi_ACIP_KAPATIYOR` | sunucu ucu |
| `test_bir_derste_TEK_kilit` | ikinci CRN eskisini düşürüyor ve bunu söylüyor |
| `test_IZGARADA_kilit_ISARETI_var` | işaret var **ve renk taşımıyor** |
| `test_BOS_SONUCUN_SEBEBI_yaziliyor` | ★★ C1'in dersi |
| `test_SUNUCUSUZ_dosyada_sahte_dugme_yok` | kaydetmediğini gizleme |
| `test_UCTAN_UCA_kilit_kuruluyor_gorunuyor_aciliyor` | ★★ tarayıcıda bütün akış |

Üç düzeltme geri konulup kırmızıya döndükleri görüldü: şube süzgeci
(4 test kırmızı), havuz kapsamı (1), ızgara işareti (2).

---

## H. Ölçülen yan bulgu — yazma uçları 5.7 saniye

Kilidi kurmak tarayıcıda **5.7 sn** sürüyor. Sebep kilit değil: her yazma
ucu `snapshot()` çağırıyor, o da iki kip için aday havuzunu ve programları
baştan kuruyor. Aynı gecikme `mesgul`, `watch`, `tercih` uçlarında da var.
Düğme "…" gösteriyor, yani donmuş görünmüyor — ama bu, arayüz listesine
(Faz 46 adayı) ölçülmüş bir madde olarak giriyor.
