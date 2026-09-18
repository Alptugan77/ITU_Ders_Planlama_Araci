# Faz 44 — Boş saate tıklayınca: "ekleyebileceğin" ile "takas" ayrıldı

*17.09.2026 · kullanıcı: "x.dönem + alttan kısmında takvime tıklayıp ekstra
ders eklenemiyor onu düzeltir misin"*

Kullanıcı haklıydı ve hata gerçekten oradaydı — ama **sebebi ilk sandığım yer
değildi**. Bu belge iki şeyi birden kaydediyor: bulunan hatayı ve yanlış
teşhisi.

Testler **1065 → 1071** (1069 geçti, 2 atlandı).

---

## A. Ölçüm

Boş hücreye tıklayınca açılan pencere, o saate koyulabilecek dersleri
listeliyor. Her satırın altında bir not var: *"çıkarılır: GEO 321E"* —
yani o dersi eklersen programından bir ders **düşecek**.

Gerçek veriyle, iki kipte, her boş hücre için sayıldı:

| | "N. dönem + alttan" | `all` |
|---|---|---|
| boş hücre | 38 | 56 |
| **yalnız TAKAS sunan hücre** | **27 (%71)** | 24 |
| diyalog tamamen boş | 1 | 32 |
| çakışmadan eklenebilen seçeneği olan | 10 | **0** |

Seçeneklerin düşme sebebi de ayrıldı: **%96'sı gerçek zaman çakışması**,
havuz çakışması tek başına **%0**.

**Motor yanlış değil.** Hafta 14 dersle dolu; boş hücreler derslerin
*arasındaki* boşluklar ve aday şubelerin çoğu 2–3 saatlik, komşu derse
taşıyor. Yani o saate gerçekten sığmıyorlar.

**Yanlış olan sunum.** "çıkarılır: …" notu her satırın *içine* gömülüydü;
liste bir bütün olarak "ekleyebileceğin dersler" gibi duruyordu. Kullanıcı
18 satırı tek tek okuyup "hiçbirini ekleyemiyorum" sonucuna varıyordu — ki
o sonuç doğruydu, sadece ekran bunu söylemiyordu.

---

## B. Düzeltme

Pencere artık iki şeyi ayırıyor:

```
BOŞ SAAT · Pzt 08:00

  ┌ Bu saate çakışmadan sığan ders yok.
  │ Aşağıdaki 18 dersten biri için programında yer açman gerekiyor —
  └ her birinin altında hangi dersin çıkacağı yazılı.

  [ BURAYA SIĞIYOR ]                    …varsa, önce ve ayrı başlıkta
  [ YER AÇMAN GEREKİYOR — BU SAAT CİVARI ]   7 ders
  [ YER AÇMAN GEREKİYOR — PZT GÜNÜ ]        11 ders
```

* **Sığanlar önce.** Hiçbir dersi düşürmeyen seçenekler kendi başlığı
  altında ve listenin başında. Eskiden aynı listede, 12 takas seçeneğinin
  altına gömülebiliyorlardı.
* **Hiç sığmıyorsa bu söyleniyor** — sayıyla. "Genel uyarı" değil: *kaç*
  ders için yer açman gerektiği yazıyor.
* ⚠️ **Takaslar gizlenmiyor.** Bazen istenen şey odur ("şunun yerine bunu
  koy"). Gizleseydik "bu saatte hiçbir şey yok" sanılırdı — bu depoda
  tekrarlayan hata (bkz. Faz 25: havuz engelini gizlemek Çarşamba'da 19
  adayın 18'ini görünmez yapmıştı).

Ölçülen fark, kullanıcının şikâyet ettiği kipte: daha önce yalnız takas
sunduğu görülen bir hücrede, **"Pzt günü, başka saatte sığıyor" grubu**
sayesinde temiz bir seçenek listenin başına çıktı.

---

## C. ⚠️ Yanlış teşhis — ve neden kaydediliyor

İlk teorim şuydu: *Faz 39'da ızgarayı kullanılan aralığa kırpmıştım; "N.
dönem + alttan" kipinde ızgara 08:00–17:00'a kırpılıyor, demek ki
eklenebilecek ders kırpılan saatlerde kalıyor ve tıklanacak hücre ekranda
yok.*

Teoriye uygun kod da yazdım: kırpılan satırlardaki eklenebilir dersleri
bulan `eklenebilirGizli()` ve ızgaranın altında onlara giden kısayollar.

**Ölçünce yanlış çıktı.** O ders (`BHB 201E`) **17:30**'da başlıyor, yani
görünür aralığın içinde; kırpma onu gizlemiyordu. Yazdığım kodu geri aldım.

Kaydedilme sebebi: bu depoda kural *önce ölç, sonra değiştir*. Bu turda
sırayı bozdum — teoriye göre kod yazıp sonra ölçtüm — ve düzeltme hatanın
yanından geçti. `test_ILK_TESHIS_geri_alindi` o kodun geri gelmediğini
tutuyor.

---

## D. Testler

`tests/test_faz44_bos_saat_ekleme.py` (6 test):

| test | neyi tutuyor |
|---|---|
| `test_secenek_KAC_DERS_DUSURDUGUNU_tasiyor` | gruplama nota değil sayıya bakıyor |
| `test_SIGANLAR_ile_TAKASLAR_ayri_gruplarda` | ★★ ayrım + sığanlar önce |
| `test_HIC_SIGMIYORSA_bu_soyleniyor` | sayıyla, genel uyarı değil |
| `test_takas_secenekleri_GIZLENMIYOR` | Faz 25'in dersi |
| `test_ILK_TESHIS_geri_alindi` | ⚠️ ölçmeden yazılan kod depoda kalmasın |
| `test_UCTAN_UCA_sigan_ve_takas_ayriliyor` | ★★ tarayıcıda bütün akış |

Uçtan uca test iki hücreyi birden kovalıyor: çakışan dersin olduğu hücrede
uyarı çıkıyor mu, sığanı olan hücrede "sığıyor" grubu var mı ve o seçenek
**net** ekleniyor mu (1 → 2 ders). İki düzeltme geri konulup kırmızıya
döndükleri görüldü.
