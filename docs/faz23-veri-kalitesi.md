# Faz 23 — Uyarılar eyleme dönük olsun

**Tarih:** 23.08.2026 · **Test:** 656 (öncesi 630) · Yapılacaklar §3

Önce Faz 19 doğrulandı: yeniden taramada **`dropped_plan_rows` raporda hiç
görünmedi** — sıfır düşen satır. Yandal düzeltmesi tuttu (24793 slot, öncekinden
505 az; fazlalık yardımcı tablolardan geliyordu).

Geriye kalan uyarılara baktım ve **üçünün yanlış alarm** olduğunu buldum.
Yanlış alarm veren bir uyarı okunmaz hâle gelir; okunmayan uyarı hiç olmamış
gibidir. Bu faz uyarıları susturmuyor — **doğru şeyi söylemelerini** sağlıyor.

| Uyarı | Önce | Sonra |
|---|---|---|
| kategori eşlenemedi | 1236 slot | **26** |
| kredi tutmuyor | 65 plan | yalnız gerçekten tutmayanlar |
| boş havuz "PARSE HATASI" | 11 | sebebiyle ayrılmış |

---

## 1. Kategori etiketleri: 1236 → 26

İlk içgüdüm regex'i genişletmekti. Önce **ölçtüm**: 292 farklı OTHER
etiketinin yalnız **66'sı** kategori kodu taşıyordu; 226'sında kaynakta
kategori **yoktu** (`Stüdyo IV`, `Temel Meslek II`, `Selective`,
`Meslek Teknolojisi VII`).

Yani uyarının çoğu düzeltilemeyecek bir şeyi hata diye gösteriyordu. İki iş:

**(a) Gerçek boşlukları kapat.** 1400 gerçek etiket üzerinde ölçülen dört
biçim vardı ve kalıp yalnız birini tanıyordu:

```
parantezde   "(MT)"  ·  "(MT-Tasarım)"          ← son ek tanınmıyordu
sonda        "MT VI" ·  "…CrseI-MT"             ← roma V'in ötesi, tire
başta        "MT Seçim Dersi 2 (E)"             ← hiç tanınmıyordu
```

Sonuç ölçüldü: **45 etiket kazanıldı, 0 kayıp, 0 kategori değişti.**

**(b) `re.IGNORECASE` KALDIRILDI.** Bu tek başına bir hata düzeltmesi:
`Intr. to Sci & Eng Comp.` bir **ders adı** ve içindeki "Eng" kategori değil.
Harf duyarsız arasaydık **48 slotu yanlışlıkla ENG** diye etiketlerdik.
Kategori kodları kaynakta her zaman büyük harf; ders adlarındaki İngilizce
kelimeler değil.

**(c) Uyarı ikiye ayrıldı.** `unmatched_labels` (kategori var, çözemedik —
bizim eksiğimiz) ve `uncategorised_labels` (kaynakta kategori yok — bilgi).
Tek listede toplamak, düzeltilebilir 26'yı düzeltilemez 1210'un içinde
görünmez kılıyordu.

## 2. Kredi bir sayı değil, bir ARALIK

65 plan "kredi tutmuyor" diyordu. Sebep:

```
Dersler | Seçime Bağlı Ders I | | S | 2 / 2,5 / 3 | 4 / 4,5 / 5 / 5,5 / 6 | …
                                      ^^^^^^^^^^^ kredi
```

Havuz slotunun kredisi **hangi dersi seçtiğine bağlı**. `float()` bunu
çözemiyor ve kredi sessizce NULL kalıyordu — katalogdaki **4923 havuz
slotunun kredisi yoktu**, planların toplamı da doğal olarak sayfadakinden
düşük çıkıyordu.

⚠️ **Aralıktan tek sayı seçmedik.** Ortalama ya da en küçüğü almak, kaynakta
olmayan bir sayı uydurmak olurdu — ve o sayı kredi tavanına, yarıyıl tabanına,
ilerleme yüzdesine akardı. Aralık `credits_min`/`credits_max` olarak duruyor;
kontrol de ilan edilen krediyi **aralıkla** karşılaştırıyor ve raporda
"5–6 kredi topladık" yazıyor.

## 3. Boş havuzun SEBEBİ

Kontrol, grupId'si olan her boş havuza "PARSE HATASI (havuz sayfası yapısı
değişmiş olabilir)" diyordu. Grup 11083'ün arşivlenmiş cevabına baktım:
**içinde hiç `<table>` yok.** OBS boş sayfa döndürüyor.

Kaynağın eksiğini kendi hatamız gibi göstermek, düzeltilmesi en zor yalan
türü — kimse aramadığı hatayı bulamaz. `pool_status` artık üçünü ayırıyor:

* `no_table` — OBS ders tablosu olmayan sayfa döndürdü (kaynakta boş)
* `no_codes` — tablo vardı, kod çıkaramadık (**bizim** hatamız)
* kayıtsız — bu sürümden önce çekilmiş; "bilmiyorum" demek, yanlış sebep
  uydurmaktan iyidir

---

## Yeniden tarama gerekiyor

`credits_raw` / `credits_min` / `credits_max` ve `pool_status` **tarama
anında** doluyor. `make all-plans` çalıştırılana kadar kredi uyarısı eski
sayıyı göstermeye devam eder; kategori düzeltmesi de yeni taramada işler.
