# Faz 61 — Yol haritası senaryoları ve danışman özeti

*24.09.2026 · kullanıcı: "can you continue on your improvements and aditions".*

`fikirler.md`'nin "Faz 57 araştırması" listesi kapandı; bu turun iki işi
öğrencinin planla GERÇEKTE ne yaptığından seçildi: planı kendi hayatına
uydurmak (iş, Erasmus, staj) ve planı danışmana götürmek.

Testler **1283 → 1289** (+6), 4 atlandı. Geri alma deneyi:
sekiz kuralın **sekizi** geri konunca kendi sebebiyle kırmızı (§3).

---

## 1. ★★ Yol haritası senaryoları

"Çalışıyorum, dönemde en çok 18 kredi alabilirim", "3. dönem Erasmus'a
gidiyorum" — ikisi de bitişi değiştiriyor ve ikisi de ancak haritayı
**yeniden kurarak** ölçülebiliyor. Yol haritası görünümünün üstünde:

* **Dönem başına en çok** [sınırın · 21 · 18 · 15 · 12] kredi;
* **Boş bırak (Erasmus, staj):** gelecek dönemlerin düğmeleri (seçili olan ✓
  taşıyor — renk tek işaret değil).

Seçim salt okunur `/api/yolharitasi`'ya gidiyor; harita senaryoyla çiziliyor,
üstünde *"Senaryo gösteriliyor — kaydedilmedi. boş: 2026-2027 Güz · [Bugünkü
plana dön]"* şeridi, her program kartında *"bugünkü plana göre N dönem geç"*.
Hiçbir şey kaydedilmiyor; durum yeniden kurulunca (boot) senaryo kapanıyor —
eski bir tabana göre fark yazmasın.

**Vitrinde ölçülen:** 2026-2027 Güz'ü boş bırakmak anadalı **bir yıl**
geciktiriyor (2028-2029 Bahar, 12. yarıyıl): GEO 341E yalnız Güz'de açılıyor
ve arkasında iki derslik zincir var. Aynı öğrenci 2025-2026 Bahar'ı boş
bıraksa bitiş değişmiyor. Erasmus'u hangi döneme koyacağının cevabı bu.

### Motor: `yolharitasi.kur(..., bos=[…])`

* Boş dönemde İTÜ dersi yok; kart takvimde **kalıyor** ("Boş bıraktın —
  Erasmus, staj ya da izin") — atmak planı kısa gösterirdi.
* Yarıyıl sayısına **dahil** (Erasmus/staj kayıtlı dönem); kayıt dondurma
  sayılmayabilir — varsayım kutusunda yazıyor, yurt dışı derslerin denkliği
  de hesapta yok.
* Boş dönemde ÇAP tabanı eksiği yazılmıyor: kararı öğrenci verdi, izinli
  dönemin yönergedeki durumunu danışman bilir; plan onu uydurmuyor.
* Girdi `cap_bitisleri` ile ORTAK yardımcıdan (`_harita_girdisi`): kredi
  sınırı 1–60, en çok 6 boş dönem, sıra 1–12; aksi `ValueError` (400).

## 2. ★★ Danışman özeti

İTÜ'de ders kaydı danışman onayıyla bitiyor. Öğrenci görüşmeye ne
götüreceğini beş ayrı görünümden topluyordu. Programın araç çubuğunda
**Danışman özeti**: tek sayfa, **Yazdır** ile yalnız o basılıyor.

* **Bu dönemin programı** — ders, ad, program, kredi, **CRN**, saat;
* **Kontroller** — dönem yükü, ÇAP yarıyıl tabanı, GNO (tahmini);
* **Tahmini bitiş** — yarıyıl numarasıyla ve plana göre farkla;
* **Danışmana sorulacaklar** — yalnız ÖLÇÜLEN sorunlardan: yük aşımı, taban
  eksiği (indirim yolu varsa onu da soruyor), dolu şube, saati ilan
  edilmemiş ders, plana göre gecikme, azami süre, "bu dönem şunu alırsan",
  yerleşmeyen ders, ÇAP tabanının tutmadığı gelecek dönem, tutmayan GNO
  eşiği (girilmiş programın başvuru eşiği hariç), şartlı geçer + GNO < 2.00.
  Sorun yoksa "Ölçülen bir sorun yok".

**Vitrinde:** GEO 341E'yi olağan yoldan eklemek bir ÇAP dersini (saat
çakışması) düşürüyor ve özet hemen soruyor: *"İkinci anadaldan bu dönem 6
kredi alıyorum; yarıyıl tabanı 9 (3 eksik). Tabanın 4.5'e indirilmesi için
başvurabilir miyim?"* — yol haritasının "bu dönem şunu alırsan" önerisinin
bedeli, danışmana gitmeden önce görünüyor.

### Kurallar

* Özet **kendi hesabını yapmıyor**: taban `tabanDurumu()` (renderFloor ile
  ortak — bu fazda tek yere alındı), yük `totals()`, dersler `picks()`.
  Test özetteki tablo satırı sayısını programdaki ders sayısıyla
  karşılaştırıyor.
* ⚠️ GNO içeriyor — PNG resminden (Faz 58) farkı bu; danışman transkripti
  zaten görüyor. Sayfa bunu yazıyor ("yalnız danışmanınla paylaş").
* Aracın adı yer tutucudan (`__AD_TAM__`, test_ad.py).

### Baskı hatası (ölçüldü)

İlk sürüm **boş sayfa** basıyordu: baskı kuralı `<body>`'nin doğrudan
çocuklarını gizliyor, özet kabı ise bir sarmalayıcının içindeydi. Kap artık
yazdırırken `<body>`'ye taşınıyor; `afterprint` sonrası sayfa eski hâline
dönüyor (ikisi de uçtan uca test ediliyor, baskı ortamı taklit edilerek).

## 3. Testler ve geri alma deneyi

`tests/test_faz61_senaryo_ve_danisman.py` (6 test). Tam paket dört eski testin
KOD YERİNİ sabitlediğini gösterdi; davranış aynı, yer değişti ve testler yeni
yere yönlendirildi: taban filtresi `tabanDurumu`nda (test_ui), sınırlar
`_harita_girdisi`nde (Faz 59), yol haritası gövdesi iki satır (Faz 57), ve
Faz 48'in "ilk `@media print` bloğu = kâğıt paleti" varsayımı — özet için
ayrı bir baskı bloğu açmıştım, kurallar artık ana baskı bloğunda.

| Geri konan | Kırmızı |
|---|---|
| Boş dönem kartı takvimden atılıyor | birim + uçtan uca |
| Boş dönem uygulanmıyor | birim + uçtan uca |
| Senaryo girdisi sınırsız | statik + uçtan uca (400 beklenirken kabul) |
| Senaryo ucu salt okunur değil | statik |
| Yeni durumda eski senaryo kalıyor | statik |
| Özet tabanı kendi hesaplıyor | statik + uçtan uca (6/9 sorusu yok) |
| Baskı kabı sarmalayıcıda kalıyor | statik + uçtan uca (boş sayfa) |
| Baskıdan sonra sayfa temizlenmiyor | statik + uçtan uca |

## 4. Ne yapılmadı

* Senaryo **kaydedilmiyor** — bilerek: kalıcı "Erasmus dönemi" ayarı
  öneriyi de etkilemeli (o dönem şube önermemek), bu ayrı bir iş.
* Yurt dışında alınan derslerin denkliği senaryoya girmiyor (veri yok).
