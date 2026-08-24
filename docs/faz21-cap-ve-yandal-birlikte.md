# Faz 21 — ÇAP ve yandal aynı anda

**Tarih:** 23.08.2026 · **Test:** 601 (öncesi 575) · Yapılacaklar 1.6

> "yandal ve çap aynı anda alınabiliyor"

Araç bugüne kadar **tek** ikinci program varsayıyordu: `second_kind`,
`second_program`, `second_role` — hepsi tekil.

---

## Asıl risk ders sayısı değil, kural karışması

Bu fazın zor kısmı iki planı yan yana koymak değildi. Zor kısmı şuydu:
**ÇAP'ın ve yandalın kuralları farklı maddelerden geliyor.**

| Kural | Kaynak | Kime |
|---|---|---|
| Başvuru GNO 3.00 · devam 2.50 | Yönerge Madde 15 / 19 | ÇAP |
| Mezuniyet: üniversite 2.50 + **ikinci anadal 2.00** | Madde 18 | ÇAP |
| Başvuru 2.50 · kayıt silme 2.00 | Madde 22 / 27 | Yandal |
| İkinci anadaldan asgari yarıyıl kredisi (6 / 9) | Yönerge | **yalnız ÇAP** |
| Kredi yükü alt sınırı muafiyeti | MADDE 17/1 | ÇAP öğrencisi |

Tek "ikinci program" kutusuna sıkıştırılsaydı biri öbürünün kuralıyla
değerlendirilirdi — ve bu **ekranda doğru görünürdü.** Bu araçta yapılabilecek
en pahalı hata türü tam olarak bu.

Bu yüzden:

* Eşikler artık **kapsam** taşıyor (`scope`: `cap` / `yandal` / `genel`) ve iki
  program birdeyken arayüzde hangi programın kuralı olduğu **yazıyor**.
* İki kapsamda da çıkan eşik (ör. mezuniyet GNO 2.00) **genel** sayılıyor ve
  bir kez gösteriliyor — iki kez göstermek iki ayrı şart varmış izlenimi verirdi.
* **Yarıyıl tabanı yalnız ÇAP'ta.** Yönerge "İkinci anadala N. yarıyılda
  başlayan öğrenci…" diyor; "ikinci anadal" = ÇAP. Eskiden yandala da
  uygulanıyordu — var olmayan bir kuralla "az aldın" demek olurdu.
* İkinci anadal ortalaması **o planın kendi derslerinden** hesaplanıyor;
  iki program varsa iki ayrı hesap.

## Model

`second_kind` artık "hangi tür" değil "hangi tür**LER**" sorusunun cevabı:

```python
SECOND_CHOICES = {"cap": ("cap",), "yandal": ("yandal",),
                  "ikisi": ("cap", "yandal"), "yok": ()}
```

Tek bir skaler alan — çünkü `settings.toml` yazıcısı satır bazlı ve yorumları
koruyor (`[[tablo]]` yazamıyor), **ve** iki ayrı bayrağın birbiriyle çelişme
ihtimalini ortadan kaldırıyor. Bu projede tekrar tekrar canımızı yakan şey iki
kaynağın aynı soruya farklı cevap vermesiydi.

İyi haber: `cap_program` / `yandal_program` alanları zaten AYRI duruyordu.
Veritabanı da hazırdı — `enrollment` rol taşıyor ve birden çok kayıt tutabiliyor.
Tek kaydı yazan **bizdik**.

### `cap_id` adı bir tuzağa dönüştü

`collect(…, anadal_id, cap_id)` konumsalındaki `cap_id` tarihsel bir isim:
içinde yandal planı da olabiliyordu, "hangi tür" sorusunun cevabı
`settings.second_kind`'daydı. İki program gelince bu belirsizlik **hataya
döndü** — yandal seçiliyken rol `CAP` çıkıyordu (sunucu testi yakaladı).

Çözüm: çağıran taraf artık ikinci programları **açıkça liste olarak**
verebiliyor (`collect(..., seconds=[...])`). Eski konumsal çağrı bozulmadı ve
testi var.

## Ne değişti

| Yer | Değişiklik |
|---|---|
| `config` | `second_kinds`, `seconds`, `program_of`, `plan_id_of` |
| `plans` | `anadal_plan`, `resolve_seconds` (liste); `resolve_plans` ilkini verir |
| `recommend` | `second_plans=[(rol, plan_id), …]`; kritik yol ve kademe **her** programdan |
| `ui.collect` | `seconds=` ile açık liste; paneller, adaylar, darboğaz, eşikler, kademeler çoğullaştı |
| `ui` JSON | `seconds`, `tierGroups`, eşiklerde `scope`, darboğazda `role`/`program` |
| `server` | `_reenroll` iki kaydı da yazıyor; `/api/programs` `secondPrograms` alıyor |
| arayüz | "İkisi" seçeneği + iki bölüm/plan kutusu; yandala **ayrı renk** |

Yandalın kendi rengi olması kozmetik değil: ÇAP ile aynı renkte olsalardı
ızgarada ve panelde hangisinin hangisi olduğu anlaşılmazdı.

## Kademeler ayrı

Her ikinci program **kendi** kademe zincirini alıyor. Tek listede
birleştirseydik iki ayrı programın zincirleri birbirine bağlıymış gibi
görünürdü — aralarında önşart ilişkisi yok. Bir derse tıklayınca da yalnız
kendi grubundaki zincir aydınlanıyor.

## Geri uyumluluk

Tek programlı kullanım hiç değişmedi ve iki testle korunuyor: eski konumsal
çağrı (`collect(..., 10, 20)`) ve tek yandal seçimi.
