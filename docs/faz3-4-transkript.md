# Faz 3+4 — Transkript girişi ve ilerleme paneli

> ⚠️ Bu belgedeki bütün sayılar **örnektir**. Repoda kimsenin gerçek notu
> ya da ortalaması yer almaz — kişisel veri `data/` altında kalır ve
> `.gitignore` ile dışarıda tutulur.


D5'ten sonra Faz 3 (eşleme motoru) küçüldü — çift sayım fiilen yok, geriye
"hangi ders hangi slotu dolduruyor" muhasebesi kaldı. Bu yüzden Faz 3 ile
Faz 4 birleştirildi.

## Akış

```bash
make student                       # kaydı kur + transkript şablonu üret
$EDITOR transkript.txt             # aldığın derslerin '# ' işaretini sil, not yaz
make transcript FILE=transkript.txt
make progress                      # anadal + ÇAP paneli
```

## Elle giriş tasarımı

Ders kodlarını **yazmak zorunda değilsin.** `make student` planlarından hazır
bir kontrol listesi üretiyor:

```
# --- 3. yarıyıl ---
# GEO 201E             # Cartography I
# GEO 209E             # Real Estate's Law
# GEO 213E             # Positioning Method and Systems
```

Aldığın dersin başındaki `# ` işaretini silip notunu yazıyorsun. İş, kod
yazmaktan not yazmaya iniyor. Plan dışı dersler için dosyanın sonuna elle
ekleme yapılabiliyor.

Kabul edilen satır biçimleri:

| Yazım | Anlamı |
|---|---|
| `MAT 103E AA` | geçildi, notu biliniyor |
| `mat103e,bb` | aynı — küçük harf, virgül, boşluksuz hepsi çalışır |
| `MAT 103E` | geçildi ama not bilinmiyor |
| `MAT 103E --` | hâlâ alıyorum |
| `# MAT 103E` | hiç almadım |
| `-> GEO 413E AA` | havuz satırını serbest doldurma da çalışır |

Şablon dolu bir `transkript.txt` bulursa **üzerine yazmaz**, yanına
`transkript-yeni.txt` açar (`--overwrite` ile zorlanabilir).

## İki karar

**1. Notu bilinmeyen ders `DD` sayılır.** "Geçtim ama notumu hatırlamıyorum"
durumunda en kötü geçer not varsayılıyor. Böylece `MIN CC` isteyen bir önşartta
yanlışlıkla "alabilirsin" denmiyor. Panel bu dersleri ayrıca uyarı olarak
listeliyor, çünkü seni gereksiz engelliyor olabilir.

**2. "Devam ediyorum" ile "notumu bilmiyorum" ayrı tutuluyor.** Devam eden ders
geçilmiş sayılmıyor, ama `MIN FF` ("dersi almış olmak yeter") isteyen önşartlar
için `include_in_progress=True` ile hesaba katılabiliyor.

## İlerleme paneli

Anadal ve ÇAP **ayrı** hesaplanıyor (yol haritası §1.7 — tek "toplam AKTS"
göstergesi yanıltıcı olurdu):

```
ANADAL — HTAE
  █████████░░░░░░░░░░░░░░░  %37.7
  slot : 23/61      AKTS : 87/212
  ITB 0/1 · MT 0/4 · TB 0/1 · TM 0/1 · ZORUNLU 23/54

CAP — BLG
  █░░░░░░░░░░░░░░░░░░░░░░░  %5
  slot : 1/20      AKTS : 8/117
```

Ardından **şu an alabileceklerin**, önşart motorundan geçirilerek ve açık
şube/kontenjan bilgisiyle:

```
ÇAP'TA ŞU AN ALABİLECEKLERİN
  ▶ BLG 231E     4.5 AKTS  açtığı ders: 36   [3 şube, en boşu CRN 12476: 0/70]
  ▶ BLG 252E       5 AKTS  açtığı ders: 21   [bu dönem açılmamış]
  ▶ BLG 223E       8 AKTS  açtığı ders: 14   [2 şube, en boşu CRN 12469: 0/80]

  ÇAP zorunlu: 1/20 bitti · kalan 109 AKTS · en az 6 dönem (önşart zinciri)
```

"Açtığı ders" sayısı sıralamayı belirliyor: `BLG 231E` 36 dersin önşartında
geçiyor, o yüzden en üstte.

## slot_fulfillment

Faz 3'ün kalan işi. Her geçilen ders, doldurduğu `(plan, slot)` çiftine
bağlanıyor. Tablo genel — aynı ders birden fazla plana bağlanabilir; bu çiftte
olmuyor ama `double_counted()` kontrolü duruyor ve test edildi.

Denklikle karşılanan slotlarda `via_equivalence` doluyor, böylece arayüz
"bu ders X'in yerine sayıldı" diyebilecek.

## Gizlilik

Bu fazda üretilen her şey kişisel veri:

* `data/user.sqlite3` — referans veriden ayrı dosya, `.gitignore`'da
* `transkript*.txt` — `.gitignore`'a eklendi
* OBS şifresi hiçbir aşamada istenmiyor

## Yaşanan hata: seçmeli dersler sayılmıyordu (18.08.2026)

İlk gerçek kullanımda seçmeli dersler ilerlemeye yansımadı. Kök neden
`_DersGrupSearch` sayfasının hücre yapısıydı:

```html
<td><a href="...DersBilgi...">GEO 413E</a><br>Navigation Sys. and Methods</td>
```

Ders kodu ve **adı aynı hücrede**. Parser hücre metnini doğrudan kod sanıyordu,
`"GEO 413E Navigation Sys. and Methods"` hiçbir ders koduna uymuyor, havuz
sessizce boş kalıyordu. Artık kod önce `<a>` metninden, o yoksa hücre metninin
başındaki koddan okunuyor.

Bu sınıf hatayı bir daha sessiz geçirmemek için `empty_pool` kontrolü sertleşti:
bir havuzun OBS `grupId`'si varsa ama seçeneği yoksa, bu **parse hatası** olarak
raporlanıyor — "kaynakta tanımlı değil" durumundan ayrı.

İki yan bulgu daha çıktı: `plan_slot.ects` boş olan eski taramalarda AKTS
toplamları 0 görünüyordu (artık ders kataloğundan tamamlanıyor), ve havuz satırı
serbest doldurulduğunda satır çözülemiyordu.

## Test kapsamı

108 test (Faz 3+4'ten 21 yeni). Kritik olanlar:

* Satır çözme varyantları (küçük harf, virgül, boşluksuz, yorum)
* Notsuz ders `DD` sayılıyor ve `grade_known=False` işaretleniyor
* Devam eden ders geçilmiş sayılmıyor, ama "notsuz" listesine de girmiyor
* Başarısız ders (`FF`) geçilmiş sayılmıyor
* Aynı ders iki kez girilirse güncelleniyor, çoğalmıyor
* Şablonun kendisi parse edilince **boş** çıkıyor (kazara "hepsini aldım" olmaz)
* `slot_fulfillment` idempotent
* Çift sayım gerçekten olursa yakalanıyor
* İlerleme plan bazında ayrı; `MIN CC` eşiği "alabileceklerin" listesinde doğru
