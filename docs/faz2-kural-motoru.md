# Faz 2 — Kural motoru

> ⚠️ Bu belgedeki bütün sayılar **örnektir**. Repoda kimsenin gerçek notu
> ya da ortalaması yer almaz — kişisel veri `data/` altında kalır ve
> `.gitignore` ile dışarıda tutulur.


## 1. Önşart gramerinin ölçülmüş tanımı

4.628 önşartlı dersin tamamı taranarak çıkarıldı. Sözcük dağarcığı küçük:

```
ifade   := terim ( 'veya' terim )*
terim   := çarpan ( 've' çarpan )*
çarpan  := '(' ifade ')' | yaprak
yaprak  := DERS_KODU [ 'MIN' NOT ]
```

Ders kodu ve not dışında geçen **tüm** kelimeler ve frekansları:

| Token | Frekans |
|---|---|
| `MIN` | 19.661 |
| `DDveya` | 8.923 |
| `veya` | 4.274 |
| `ve` | 1.429 |
| `CCveya` | 227 |
| `FFveya` | 70 |
| `BBveya` | 58 |
| `DDve` | 43 |
| `DCveya` / `BLveya` / `CCve` | 24 |

Noktalama: yalnızca `(` `)` (9.779 + 9.779, dengeli) ve tek bir başıboş `+`.

### Öncelik

`ve` > `veya` (standart). **Ölçüm: gerçek veride aynı parantez derinliğinde
`ve` ile `veya` hiç karışmıyor (0/4628).** Yani bu seçim mevcut veride hiçbir
sonucu değiştiremez. Yine de karışık girdi gelirse `Parsed.ambiguous` işaretlenir
ve regresyon testi kırmızı yanar — sessizce yanlış cevap üretilmez.

### Notlar

`AA 4.0 · BA 3.5 · BB 3.0 · CB 2.5 · CC 2.0 · DC 1.5 · DD 1.0 · FD 0.5 · FF 0.0`
artı `BL` (Başarılı, kredisiz dersler → 1.0), `BZ`/`VF` (0.0), `MU` (muaf, 4.0).

İki önemli semantik:

* **`MIN FF`** = "dersi almış olmak yeter" (153 kez geçiyor). FF ≥ FF olduğu için
  puan karşılaştırması bunu doğal olarak karşılar.
* **`MIN BL`** = kredisiz/staj dersinde başarılı olmak (MAK 199 → MAK 198).

## 2. Yazım bozuklukları ve onarımlar

| Bozukluk | Örnek | Yaklaşım |
|---|---|---|
| Not–bağlaç bitişik | `DDveya` | Tokenizer doğal olarak böler |
| Parantez–bağlaç bitişik | `)veya (` | Aynı |
| Kod eki küçük harf | `IEB 322e` | Kabul, normalize edilir |
| Kod eki bağlacı yutuyor | `ECN 211EveyaECN 211` | Kod ekinde `(?![vV][eE])` koruması |
| Sonda başıboş karakter | `... MIN DD+` | `junk` token'ı, yok sayılır |
| Baştaki askıda bağlaç | `veya (A)veya (B)` | **Onarılır** + işaretlenir (bir alternatif kayıp) |
| Branş kodu iki kez | `DFH DFH 472` | **Onarılır** |
| Eksik bağlaç | `(A) (B)veya (C)` | İfadenin **baskın** bağlacı kullanılır; karışıksa onarılmaz |
| Önşart yerine ders adı | `Deniz Kazalarıve Emniyet` | Çözülemez → `prereq_unparsed` |

**Sonuç: 4.626/4.628 = %99,96 parse.** Kalan 2 kayıt (`MST 471`, `ROS 201`)
önşart alanına ders adı yazılmış gerçek veri hatası.

## 3. ★ Güvenlik ilkesi: belirsizliği gizleme

Çözülemeyen önşart **"önşartı yok" ile karıştırılmaz.** `prereq_unparsed`
tablosuna yazılır ve motor o ders için `Status.UNKNOWN` döndürür:

```python
R.can_take(con, "ROS 201", grades).status   # -> Status.UNKNOWN
```

Arayüz bunu "önşart verisi okunamadı, danışmanına danış" diye göstermeli.
Sessizce "alabilirsin" demek, cevap verememekten kötüdür.

## 4. API

```python
from itucap import rules as R, prereq as P

R.can_take(con, "BLG 223E", {"BLG 102E": "CC"})
# Verdict(status=OK)

R.can_take(con, "BLG 223E", {})
# Verdict(status=ENGELLI, missing=[("BLG 102E","DD"), ("BIL 104","DD"), ...])

R.slot_satisfied(con, slot_id, grades, R.load_equivalences(con))
# Fulfilment(satisfied=True, course="BLG 233E", via_equivalence=7)

R.plan_progress(con, plan_id, grades)
# {"slots_done": 3, "ects_done": 21.0, "by_category": {"MT": (1,4), ...}}
```

Denklik grafı **transitif kapanış** yapar: `{A,B} → C` ve `{C} → D` varsa
A+B alan öğrenci D'yi de almış sayılır. Döngüye karşı sabit-nokta koruması var.
Denklikle kazanılan derse kaynakların **en düşük** notu atanır.

## 5. Faz 2'nin somut çıktısı: `make sequence`

D5'te ÇAP planının dönemsiz olduğu ve çift sayım olmadığı ölçülmüştü. Geriye
tek yapısal sinyal kalıyor: **önşart zinciri**. `sequence` planı topolojik
kademelere ayırıyor.

TUMMUH_BLG (2229) sonucu:

| Kademe | Ders | AKTS |
|---|---|---|
| 0 | 5 | 28,5 |
| 1 | 6 | 33,5 |
| 2 | 6 | 30 |
| 3 | 1 (BLG 336E) | 5 |
| 4 | 1 (BLG 4901E) | 8 |
| 5 | 1 (BLG 4902E) | 12 |

**En hızlı bitirme: 6 dönem, 117 AKTS.** Zincirin kuyruğu (336E → 4901E → 4902E)
paralelleştirilemiyor; ÇAP'ın süresini bu üç ders belirliyor.

En çok ders açanlar (`unlock_counts`): `BLG 231E` (36), `BLG 102E` (22),
`BLG 252E` (21) — erken alınmaları en kritik dersler.

## 6. ★ Gizli ön yük bulgusu

`sequence` ayrıca **hiçbir planda olmayan ama ÇAP için gereken** dersleri
buluyor. OR alternatifleri doğru ele alınıyor (bir dal anadaldan karşılanabiliyorsa
gizli yük sayılmıyor).

| ÇAP dersi | Gereken |
|---|---|
| `BLG 354E` | `MAT 281` / `MAT 281E` — Lineer Cebir, 4 AKTS |
| `BLG 4901E` | `MAT 210` / `MAT 210E` — Mühendislik Matematiği, 5,5 AKTS |

HTAE planında `MAT 103E` ve `MAT 104E` var ama `MAT 210`/`MAT 281` **yok**.
Yani ÇAP'ın ilan edilen 117 AKTS'sine muhtemelen **~9,5 AKTS daha** ekleniyor.

> Bunlar anadal seçmeli havuzundan alınabiliyorsa yük artmaz. Danışmana
> sorulması gereken somut bir soru — aracın ürettiği ilk gerçek aksiyon maddesi.

## 7. Test kapsamı

87 test. Kritik olanlar:

* Bitişik yazım varyantları (`DDveya`, `)veya (`, `ECN 211EveyaECN 211`)
* Not eşiği, `MIN FF`, `BL` semantiği
* OR dalında `missing()` tüm alternatifleri göstermeli
* **Çözülemeyen önşart `UNKNOWN` döner, `OK` DEĞİL**
* Denklik: çok kaynaklı, min not, transitif kapanış, döngü
* İlerleme plan bazında ayrı (ÇAP ve anadal AKTS'si karışmaz)
* **Gerçek veri regresyonu**: parse oranı ≥ %99,5, öncelik belirsizliği = 0
