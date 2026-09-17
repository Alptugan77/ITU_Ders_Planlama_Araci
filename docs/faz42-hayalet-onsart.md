# Faz 42 — Hayalet önşart: olmayan dersi aramaya göndermek

*16.09.2026 · kullanıcı: "bir sonraki faza geç"*

Sıradaki faz deponun kendi açık listesinden seçildi. `fikirler.md`'de aynı
kökten iki kalem duruyordu — §1.1 *"`BLG 4901` / `BLG 492` — aynı ders, iki
kod"* ve F.4 *"kod göçü tablosu hâlâ yok"*. İkisi de **kod göçü**ne bakıyor;
ölçünce asıl zararın plan slotlarında değil **önşart grafiğinde** olduğu
çıktı.

Testler **1045 → 1055** (1053 geçti, 2 atlandı).

---

## A. Ölçüm

**Hayalet önşart** = bir dersin önşartının, katalogda bulunmayan bir ders
adını taşıması.

| | sayı |
|---|---|
| önşart ağacı olan ders | 4627 |
| önşart yaprağı | 19365 |
| **katalogda olmayan ders anan yaprak** | **1509 (%7.8)** |
| farklı hayalet kod | 275 |
| bunların katalogda **dil eşi** olanı | 219 |
| etkilenen ders | 910 |

⚠️ 275'in 219'u zararsız çıktı: `BIL 100` katalogda yok ama `BIL 100E` var,
**ve kaynak metnin kendisi ikisini zaten "veya" ile eşliyor**
(`(BLG 102 MIN DDveya BLG 102E MIN DD)`). Yani burada eksik bir şey yok;
motor `BIL 100E` almış öğrenciyi doğru kabul ediyor — ölçerek doğrulandı.

Geriye kalan 56 kodun hiçbir eşi yok: kapanmış ya da kod değiştirmiş dersler
(`ELH 332`, `ISL 221`, `AKM 202`…).

---

## B. ★★ Bulunan HATA: gerçek alternatif kesilip hayaletler kalıyordu

Eksik önşart listesi şöyle üretiliyordu:

```python
missing = ", ".join(sorted({m[0] for m in verdict.missing})[:4])
```

**Alfabetik sırala, dörde kes.** Alfabetik sıra hayalet/gerçek ayrımını
bilmiyor. Ölçülen sonuç:

| | önce | sonra |
|---|---|---|
| eksik önşartı gösterilen ders | 4627 | 4627 |
| gösterilen dördünde hayalet kod olan | **723 (%15.6)** | işaretli |
| ★★ gerçek alternatifi tamamen kesilen | **2** | **0** |

O iki ders `FIZ 241E` ve `FIZ 272E`. Ekranda görünen:

```
eksik: BIL 102, BIL 102CE, BIL 102E, BIL 102FE
```

Dördü de katalogda **yok**. Öğrencinin gerçekten alabileceği
`BIL 104E / BIL 105E / BIL 106E` ise kesilip gizlenmişti. Yani ekran yalnız
çıkmaz sokakları gösteriyordu.

Düzeltmeden sonra aynı ders:

```
eksik: BIL 104E, BIL 105E, BIL 106E, BIL 108E +22
```

⚠️ Hayalet kod **atılmıyor**, sıraya sokuluyor: öğrencinin transkriptinde
eski koduyla duruyor olabilir ve önşartı gerçekten sağlıyor olabilir. Yalnız
listenin sonuna gidiyor ve işaretleniyor:
`… (⚠ 2'si katalogda yok — eski kod olabilir)`.

---

## C. ★ Önşartı hiç açılamayan 16 ders

Ağacın hiçbir dalı katalogdaki derslerle kapanmıyorsa, o ders bu araçtan
**hiç alınamaz**. 4627 dersin **16'sı** böyle:

```
ELH 445   önşart: (ELH 332 veya ELH 332E)   ← ikisi de katalogda yok
ISL 315   önşart: ISL 221                   ← katalogda yok
CAB 710, ELH 450E, ELH 453E, ELH 455, ELH 457, ELH 458, ELH 476,
ELH 478, ISL 242E, ISL 320E, ISL 418E, ISL 420, ISL 420E, …
```

Araç bunlara *"eksik önşart: ELH 332"* diyordu — öğrenciyi **olmayan bir
dersi aramaya göndermek**. Artık ayrı bir kategori:

> **önşartı katalogda yok** — `ELH 445 · önşartı katalogda yok: ELH 332,
> ELH 332E — hiçbiri katalogda yok`

Tavsiyesi de farklı: burada "git önşartı al" diye bir yol yok; danışmana
sormak ya da denklik beyan etmek gerekiyor.

⚠️ Bu bir veri hatası **olmayabilir** — ders gerçekten kapanmış olabilir.
Araç bunu iddia etmiyor, yalnız katalogda karşılığı olmadığını söylüyor.

---

## D. Yeni kategori ÜÇ yerde birden

Faz 37'nin dersi tekrarlanmasın diye: `KREDI_ESIGI` o fazda hesaplanıyor,
arayüzde görünüyor ama `make recommend` çıktısından **sessizce düşüyordu**.
Yeni `ONSART_KATALOGDA_YOK` kategorisi üç yere birden eklendi ve üçü de
teste bağlandı:

1. `recommend.format_blockers` — etiket sözlüğü **ve** sıra listesi,
2. `ui.py` `LABELS` — etiket **ve** gruplama sırası,
3. `quality.py` — `prereq_cozulemez` bulgusu.

⚠️ Deponun zaten bir `prereq_orphan_target` kontrolü vardı ve "275 önşart
dersi course tablosunda yok" diyordu. O sayı **sebebi** ölçüyor ve çoğu
zararsız (219'unun dil eşi var). Yeni kontrol **sonucu** ölçüyor: kaç ders
gerçekten açılamıyor. İkisi birlikte duruyor.

---

## E. Ne yapılmadı — ve neden

* **Kod göçü tablosu doldurulmadı.** `fikirler.md` §1.1 bunu isterken kendi
  uyarısını da yazıyor: *"Otomatik tahmin **etme** — 'aynı ders' iddiası
  yanlışsa ilerleme yüzdesi bozulur."* Ölçtüm: OBS'nin resmî denklik tablosu
  (`equivalence`) bu katalogda **boş** (0 satır). Yani `ELH 332 → EHB 332E`
  diyecek bir kaynak elimizde yok. Kaynaksız eşleme, tam da bu projenin
  kaçındığı şey olurdu.
* **Hayalet kodlar listeden silinmedi.** Öğrencinin transkriptinde eski
  koduyla duruyor olabilir; silmek, sağlanmış bir önşartı yok saymak olurdu.
* **Dil eşi otomatik eklenmedi.** Kaynak zaten "veya" ile eşliyor; motor
  adına bir eşleme uydurmak gereksiz ve riskli.

Kullanıcının kendi programında bu fazın görünür bir etkisi **yok** — kendi
darboğaz listesindeki kodların (`BLG 252`, `BLG 312`, `BLG 322`, `BLG 4901`)
hepsi katalogda var. Düzeltme başka bölümlerdeki öğrenciler için.

---

## F. Testler

`tests/test_faz42_hayalet_onsart.py` (10 test):

| test | neyi tutuyor |
|---|---|
| `test_ALINABILIR_ders_ONCE_hayalet_SONRA` | ★★ kesme gerçek alternatifi yutamaz |
| `test_kesilen_sayisi_YAZIYOR` | `+N` ile kaç tane gizlendiği yazıyor |
| `test_HAYALET_kod_isaretleniyor` | atılmıyor, işaretleniyor |
| `test_hepsi_hayaletse_AYRI_DURUM` | açılamayan ders ayrı |
| `test_hepsi_gercekse_UYARI_YOK` | gereksiz yere uyarmıyor |
| `test_yeni_kategori_KOMUT_SATIRINDA_dusmuyor` | ★★ Faz 37 tuzağı |
| `test_yeni_kategori_ARAYUZDE_de_var` | arayüz gruplaması |
| `test_UCTAN_UCA_olu_ders_AYRI_kategoride` | motor uçtan uca |
| `test_UCTAN_UCA_karma_derste_ALINABILIR_once` | motor uçtan uca |
| `test_kalite_kaydi_SONUCU_olcuyor` | `prereq_cozulemez` |

İki düzeltme geri konulup **kırmızıya döndükleri görüldü**: alfabetik sıralama
geri gelince gerçek alternatif kayboluyor, kategori sıra listesinden düşünce
komut satırı raporu sessizleşiyor.

`python tools/hayalet_onsart.py` ölçümü tekrar üretiyor; `--liste` ile
açılamayan dersleri ve gizlenen alternatifleri döküyor.
