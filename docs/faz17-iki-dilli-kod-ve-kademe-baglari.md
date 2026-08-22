# Faz 17 — Kaybolan ders satırları ve kademe bağları

**Tarih:** 22.08.2026 · **Test:** 521 (öncesi 505)

İki kullanıcı raporu:

> "elk çap planı 5 ders gözüküyor ama daha fazla olması lazım böyle birkaç
> program var — bir de çap kademelerini birbirine önşartla bağlı olanları belli
> edecek şekilde olsun"

---

## 1. Kaybolan satırlar: 85 planda 435 ders

### Teşhis

Önce sayıya baktık, hikâyeye değil. `plan_slot.position` her SATIR için artıyor,
kayıt ise yalnız ayrıştırılabilen satır için yazılıyor. İkisinin farkı, tam
olarak sessizce düşen satır sayısı:

```sql
SELECT COUNT(*) slot, MAX(position)+1 satir FROM plan_slot WHERE plan_id=2533
--  slot = 5      satir = 28
```

Yani sayfada **28 satır** vardı, veritabanına **5** yazılmıştı. "Bu plan zaten
5 dersmiş" açıklaması ölmüş oldu.

### Sebep

OBS'nin yeni plan sayfalarında ders kodu hücresi **iki kod** taşıyor:

```html
<td><a>EEF 110</a><br><a>EEF 110E</a><br></td>   <!-- yeni: tek satır, iki kod -->
```

Eski düzende Türkçe ve İngilizce ders **ayrı satırdı** ve tarayıcı tek kod
bekliyordu. `Node.text(strip=True)` iki kodu **bitişik** veriyor
(`"EEF 110EEF 110E"`), kalıba uymuyor, satır `return 0` ile düşüyordu.

Gerçek veride: **85 ÇAP planı, 435 satır.** Hepsi ÇAP; lisans planları eski
düzende kaldığı için etkilenmemiş.

### İki tuzak

**Bitişik metinden kod aramak.** `EEF 110EEF 110E` üzerinde kod regex'i
çalıştırırsanız `EEF 110EE` diye **var olmayan bir ders** üretir. Boş sonuçtan
beterdir: öğrenci onu OBS'de arar, bulamaz, aracın yanıldığını anlayamaz.
Bu yüzden `course_codes_in` yalnız **ayırıcıyla bölünmüş** parçalara bakıyor;
çağıran taraf hücreyi `text(separator="\n")` ile okumak zorunda.

**Ayırıcı olarak boşluk.** İlk düzeltmede alternatif kodlar boşlukla
saklanmıştı — ama kodun **içinde** boşluk var (`EEF 110E`), `split()` onu
ikiye bölüyordu. Test yakaladı; ayırıcı virgül oldu.

### Ne değişti

| Yer | Değişiklik |
|---|---|
| `plan_slot.alt_course_codes` | öbür dilin kodu, virgülle (`'EEF 110E'`) |
| `plan_slot.zs_raw` | ham Z/S sütunu — artık atılmıyor |
| `rules.slot_satisfied` | zorunlu slot **iki koddan biriyle** dolar |
| `rules.plan_codes()` | plandaki bütün kodlar, tek yerde (üç yerde ayrı yazılıydı) |
| `recommend` | iki dilin de şubesi önerilebilir; ikisi birden programa GİRMEZ |
| `sequence` | önşart metni öbür dilin kodunu yazsa da bağ görünür |

`slots_used` genelleşti: eskiden yalnız havuz slotları "tek dersle dolar"
sayılıyordu, artık zorunlu slotlar da. Olmasaydı motor `EEF 110` ile
`EEF 110E`'yi aynı programa koyup aynı dersi iki kez aldırırdı.

### Adı belli ama zorunlu olmayan ders

`Z/S = S` ama grup bağlantısı yok (`EEF 206 İşaret İşleme`). Eskiden
**seçeneksiz bir havuz** yazılıyordu: hiçbir zaman dolamayan, ilerlemeyi
sonsuza kadar eksik gösteren bir slot. Artık seçenekleri dersin iki dili olan
bir havuz — yani gerçekte ne ise o.

### Bir daha sessizce olmasın

İki savunma:

1. `obs_plan.dropped_rows` — ayrıştırılamayan satır tarama sonunda **stderr'e
   yazılıyor**.
2. `quality.dropped_plan_rows` — veritabanına bakarak aynı boşluğu **geriye
   dönük** buluyor. Tarayıcıdan bağımsız: eski bir katalogda da çalışır,
   düzeltmeden sonra sıfır kalmalıdır. Senin planındaysa `error`, başkasının
   planındaysa `warn`.

> Sessiz sıfır bu projede tekrar eden hata biçimi: `post_json` boş liste
> döndürüyordu, `list_programs` boş liste döndürüyordu, şimdi de `_slot_from_row`
> `0` döndürüyordu. Üçü de "veri yok" ile "anlayamadım"ı aynı şeye çeviriyordu.

---

## 2. Kademe bağları

Kademe listesi vardı ama **neden** o kademede olduğu yazmıyordu. Artık:

* Her ders kutusu kendi plan içi önşartını yazıyor (`⟵ EEF 211`).
* Kutular arası **SVG çizgiler** bağı gösteriyor.
* Bir derse tıklayınca yalnız **o dersin zinciri** kalıyor — ataları *ve*
  torunları; ikinci tıkta hepsi geri geliyor.

Üç karar:

**Metin + çizgi, ikisi birden.** Çizgi çizilemese (yazdırma, dar ekran, JS
kapalı) bilgi kaybolmasın diye önşart kutunun içinde de yazıyor.

**Çizgiler kayan katmanın İÇİNDE.** `.tiers` yatay kayıyor. Çizgi katmanı
dışarıda olsaydı kaydırınca yerinde kalır, yanlış dersleri bağlıyormuş gibi
görünürdü — sessiz değil ama **görsel** bir yalan.

**Plan içi ve plan dışı önşart AYRI.** `⟵` plan içi bağ, "dışarıdan:" plan dışı.
Aynı çizgiyle gösterseydik anadalda çoktan alınmış bir dersi ÇAP zincirinin
parçası sanardık.

---

## 3. Şunu doğrulamak lazım

Düzeltme **tarayıcıda**; senin kataloğun hâlâ eski taramadan geliyor.
`make all-plans` çalıştırmadan site yine 5 ders gösterir.

```bash
make all-plans          # yeniden tara — dakikalar sürer
make refresh            # kalite raporu: 'dropped_plan_rows' SIFIR olmalı
make plan-info ID=2533  # 28 slot görmelisin
```

Sonra katalog sürümünü yenile (`katalog-YYYYMMDD`) ve Pages iş akışını tekrar
çalıştır.
