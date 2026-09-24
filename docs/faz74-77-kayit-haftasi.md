# Faz 74–77 — Kayıt haftasının dört sorusu

*24.09.2026 · kullanıcı: "eklenebilecek çok işe yarar şeyleri düşün ve
ekleyebileceklerini ekle. bu ders programı aracının mümkün olan en iyi ve işe
yarar durumda olmasını istiyorum".*

Araç zaten geniş: yedek plan, `.ics`, paylaşma, yol haritası, GNO hedefi, not
senaryosu, danışman özeti. Eksikleri bulmak için var olan her şey tarandı ve
öğrencinin kayıt haftasında sorduğu, aracın **cevaplayamadığı** dört soru
seçildi:

| Faz | Soru | Önce |
|---|---|---|
| 74 | Programıma daha ne sığar? | Her dersin penceresini açıp şubelere bakmak |
| 75 | Bu dersten kalırsam mezuniyetim ne kadar gecikir? | Cevap yoktu |
| 76 | Hangi seçmeli? (geçmiş not dağılımı) | Dersleri tek tek açmak |
| 77 | Plan B / Plan C | Tek program saklanabiliyordu |

Testler **1339 → 1351** (+12; `tests/test_faz74…77_*.py`), 4 atlandı.
Geri alma deneyi: **23 kuralın 23'ü** geri konunca kırmızı (§5).

---

## 1. Faz 74 — "yalnızca programa sığanlar"

Aday listesinde yeni süzgeç. Bir ders **sığar**, eğer:

* programda değilse ve aynı havuz yuvasında seçili bir dersi çıkarmıyorsa
  (`poolBlocker` — `choose()` ile aynı kural),
* yükü dönem sınırına sığıyorsa,
* en az bir şubesi **saati ilan edilmiş**, kontenjanı dolu değil (ilan
  edilmemiş kontenjan "dolu" sayılmıyor), programla ve meşgul saatlerle
  çakışmıyorsa.

Saatsiz şube ızgarada hiçbir şeyle çakışmıyor görünür ama bilinmiyor —
**bilinmeyen, bilinen gibi gösterilmez**. Satırda uyan şube yazıyor:
*"uyan şube: CRN 13661 · Çar 12:30 · 1 boş yer"*. Sayı satırı:
*"2 ders programa sığıyor · sınıra 4 kredi kaldı"*.

**Gerçek sitede bulunan:** yandal öğrencisinde 6 kredi boşken "0 ders" çıktı.
Neden: dört seçmeli havuz yuvasının dördü de programda dolu; başka bir
seçmeli ancak birinin YERİNE geçer. Doğru ama sessizdi — sayı satırı artık
*"… · 34 seçmeli dersin havuz yuvası programda dolu (eklenirse o yuvadaki
dersin yerine geçer)"* diyor.

## 2. Faz 75 — Kalma riski

`/api/kalmariski` (salt okunur): taban = ızgaradaki program geçilmiş; her ders
için **o ders çıkarılarak** yol haritası yeniden kuruluyor ve her programın
bitiş yarıyılı karşılaştırılıyor. Önşart zinciri, dersin açıldığı yarıyıl ve
dönem kredi sınırı haritanın kendi kuralları; ayrı bir hesap yok. Girdi ve
doğrulama senaryo haritalarıyla ortak (`_harita_girdisi`,
`_senaryo_planlari` — `yol_senaryosu`ndan çıkarıldı). Bitişi bilinmeyen
programda (UOLP, yerleşemeyen ders) gecikme `None`: "0 dönem" uydurulmuyor.

* **Yol haritası:** *"BLG 223E — ÇAP bitişi 2 dönem gecikir (2028-2029 Bahar),
  ancak anadal bitişini aşmadığından iki programın birlikte tamamlanacağı dönem
  değişmez · Diğer 7 dersten kalınması bitişi değiştirmemektedir."* Taban
  bitişler de yazıyor (açılıştaki öneriyle değil ızgaradaki programla).
* **Not senaryosu:** FF seçilen ders için aynı cümle.
* **Kendiliğinden, ama yalnız göründüğü yerde:** yol haritası görünümü açıkken
  ya da not senaryosunda FF seçilmişken. Ölçüldü — gerçek katalog, Pyodide,
  6 ders: **0,35 sn**. Izgaradaki her değişiklikte ödemek gereksiz; başka
  görünümde program değişince sonuç "Program veya veriler değişmiştir" diyor,
  eski sayıyı göstermiyor. Anahtar: program + sınır + durum sürümü
  (`DURUM_SURUMU`, her `applyState`te artıyor — transkript değişince eski
  sonuç geçersiz).
* Yer tutucular (`[data-kalma]`) ayrı dolduruluyor: not senaryosunun seçim
  kutuları yeniden çizilmiyor, odak kaybolmuyor.

Gerçek sitede (MAKE + Ekonomi yandalı): ECN 201E ve ECN 202E'den kalınırsa
yandal bitişi 2 dönem gecikiyor (2030-2031 Güz) — anadalı aşıyor, yani gerçek
gecikme.

## 3. Faz 76 — Geçmiş not dağılımı listede

Faz 38'in verisi yalnız dersin penceresindeydi. Artık:

* **Seçmeli havuz** derslerinin satırında kısa özet: *"geçmiş dönem: ortalama
  3.09 · %95.7 geçti · n=69 (2025-2026 Güz)"*; dönem, penceredeki
  varsayılanla aynı; olağan yarıyılı dışındaysa işaretli.
* **Sıralama:** öneri puanı (varsayılan) · geçmiş not ortalaması · boş
  kontenjan. Kararlı; verisi olmayan sonda. "Geçmiş not ortalaması" seçiliyken
  bütün satırlarda özet var.
* Faz 38'in kuralı aynen: **öneri puanına girmiyor** (test: `recommend.py`
  bu alanlara dokunmuyor; sıralama değişince puanlar aynı).

## 4. Faz 77 — Alternatif programlar

"Alternatif olarak kaydet" (ızgaranın araç çubuğunda): ızgaradaki program
adıyla saklanıyor (öneri: Plan B, Plan C…). Ana program (`saved_pick`)
değişmiyor; alternatifler yeni `saved_alt` tablosunda, aynı dönem anahtarıyla —
yerel sunucuda ve sitede (IndexedDB'ye her yazmadan sonra) kalıcı; sayfa
yenilenince duruyor (gerçek sitede ölçüldü).

* Dönem başına en çok **5**; aynı ad → üzerine; boş ad, boş program ve sınır
  aşımı **reddediliyor** (sessizce en eskisini silmek veriyi habersiz
  değiştirirdi).
* **Kayıtlı** bölümünde her alternatif tek satır özetle: ders, kredi, kampüs
  günleri, saat aralığı, çakışma, dolu şube, bulunamayan şube — karşılaştırma
  için. "Programa yükle" (geri alınabilir), "CRN'ler", "Sil" (ilk dokunuş
  sorar).
* **Kayıt günü** penceresinde "Alternatif programlar" bölümü: her birinin CRN
  satırı kopyalanmaya hazır; seçili programda dolu şube varsa açık geliyor.

## 5. Geri alma deneyi

| Faz | Geri konan | Kırmızı |
|---|---|---|
| 74 | Saatsiz şube sığar sayılıyor | statik + uçtan uca |
| 74 | Yük sınırına bakılmıyor | statik + uçtan uca |
| 74 | Meşgul saate bakılmıyor | statik + uçtan uca |
| 74 | Süzgeç uygulanmıyor | statik + uçtan uca |
| 74 | Havuz nedeni yazılmıyor | uçtan uca |
| 75 | Ders çıkarılmıyor (taban = varyant) | statik + uçtan uca |
| 75 | Program değişince eski sonuç | uçtan uca |
| 75 | "Anadal bitişini aşmıyor" nüansı yok | uçtan uca |
| 75 | render yer tutucuyu güncellemiyor | statik + uçtan uca |
| 75 | FF seçilince hesaplanmıyor | uçtan uca |
| 75 | Görünüm açılınca hesaplanmıyor | statik + uçtan uca |
| 75 | Görünmezken de hesaplanıyor | statik + uçtan uca |
| 75 | Uç salt okunur listede değil | statik |
| 76 | Sıralama uygulanmıyor | statik + uçtan uca |
| 76 | Verisi olmayan önde | statik + uçtan uca |
| 76 | Sıralama kararsız | statik + uçtan uca |
| 77 | 5 sınırı yok | birim |
| 77 | Aynı ad üzerine değil ekleniyor | birim |
| 77 | Boş ad kabul ediliyor | birim + uçtan uca |
| 77 | Silme onay istemiyor | uçtan uca |
| 77 | Yükleme geri alınamıyor | uçtan uca |
| 77 | Kayıt gününde alternatif yok | uçtan uca |
| 77 | Anlık durum alternatifleri vermiyor | uçtan uca |

Deneyin kendisi de bir kez yanıldı: `[] or S.load_alts(…)` "geri alma"sı
Python'da yine listeyi döndürüyordu → yeşil. Doğru geri alma (`= []`) kırmızı.

Yolda bir hata da yakalandı: FF seçimi yalnız not senaryosunu yeniden
çiziyordu, kalma riski tetiklenmiyordu (uçtan uca test yakaladı; iki çizim
işlevi de artık `kalmaOto()` çağırıyor).

## 6. Ne yapılmadı

* **Birden çok havuz yuvasına uyan seçmeli:** aday, uyduğu İLK havuz yuvasıyla
  geliyor (motorun Faz 27 davranışı); aynı dersin başka bir ITB yuvasını
  doldurabileceği aday listesinde görünmüyor. Motor değişikliği — ayrı iş.
* **Alternatifleri yan yana ızgarada karşılaştırma:** özet satırı var; iki
  haftalık ızgarayı üst üste koyan görünüm yok.
