# Faz 22 — Veri kaybı, CRN'den yükleme, kredi tabanı motorda

**Tarih:** 23.08.2026 · **Test:** 630 (öncesi 601)

---

## 1. ★ VERİ KAYBI: transkript ve kaydedilen program uçuyordu

> "planlar ve transkript kayıtlı kalmıyor kaydedilen program da, sadece anadal
> ve çap bölümü kayıtlı kalıyor"

### Teşhis

Önce veriye baktım, koda değil. Veri **duruyordu**:

```
user.sqlite3        45 KB   · 37 ders, 14 kayıtlı seçim
```

Yani yazma değil **okuma/taşıma** sorunu. Sonra dosyaları tarttım:

```
u.sqlite3        4 096 bayt   ← yalnız BAŞLIK
u.sqlite3-wal   78 312 bayt   ← BÜTÜN VERİ
```

SQLite **WAL** kipinde yazdığını yan dosyada tutuyor ve ana dosyaya ancak bir
*checkpoint*te aktarıyor. Site kalıcılığı `user.sqlite3`'ü IndexedDB'ye
**kopyalayarak** sağlıyor; yan dosya sayfa kapanınca yok oluyor.

`settings.toml` düz metin olduğu için etkilenmiyordu — **"sadece bölüm ayarları
kalıyor" belirtisi tam olarak buydu.** Belirti, sebebi doğrudan gösteriyordu.

### Düzeltme

WAL yerel sunucu için seçilmişti (`ThreadingHTTPServer`, eşzamanlı okuma).
Tarayıcıda tek iş parçacığı var: WAL hiçbir şey kazandırmıyor, yalnız
kaybettiriyor.

```python
def journal_mode() -> str:
    return "TRUNCATE" if sys.platform == "emscripten" else "WAL"
```

Var olan bir WAL veritabanını TRUNCATE ile açmak onu önce checkpoint ediyor —
kip değişimi veri taşımayı da halletti. Ayrıca `dispatch` her yazmadan sonra
`db.checkpoint()` çağırıyor: kuşak farkı olan dosyalar da kurtuluyor.

### Testin şekli değişti

Eski testler **"yazıldı mı"** diye soruyordu ve hepsi geçiyordu. Yeni testler
**"dosyayı kopyalayınca duruyor mu"** diye soruyor — tarayıcı kalıcılığının
tek varsayımı bu:

```python
state.dispatch("/api/picks", {...})
shutil.copy(USER_DB, hedef)          # ★ yalnız ANA dosya
assert sqlite3.connect(hedef).execute("SELECT COUNT(*) FROM saved_pick")...
```

Bir test de hatayı bilerek üretiyor (WAL kipinde, checkpoint'ten önce) ve
`OperationalError` bekliyor — düzeltme geri alınırsa test bunu söyler.

---

## 2. CRN'den program yükleme

> "CRN ile program yükleme olursa iyi olur"

OBS'de kaydını yaptıktan sonra CRN'leri yapıştır, ızgarada **gerçek** programın
görünsün. `POST /api/crn` → şube, saat, kontenjan, rol.

İki karar:

**Planında olmayan ders de yükleniyor** (`PLAN_DISI`, nötr renk). Gizleseydik
kullanıcı gerçek programını göremezdi — serbest seçmeli, ortak zorunlu ya da
başka bölümden alınan ders de kayıtta olabiliyor. Rengi nötr çünkü hangi
programa saydığını **biz bilmiyoruz**.

**Bulunamayan CRN sessizce atılmıyor.** 8 yapıştırıp 6 ders görürsen hangi
ikisinin düştüğünü bilmelisin; yanlış derse kayıt olmuş sanmaktan iyidir.

Uç bir **okuma** ama yazma yolundan (`dispatch`) geçiyor. Sebep mimari: iki
taşıyıcı (yerel sunucu + tarayıcıdaki Pyodide) yalnız `dispatch`i paylaşıyor;
ayrı bir okuma yolu açmak, web sürümünün onu kopyalaması ve ikisinin zamanla
ayrışması demek olurdu.

---

## 3. Yarıyıl kredi tabanı artık motorda (yapılacaklar 1.4)

Taban Faz 13'te eklenmişti ama yalnız bir **uyarıydı**: motor onu bilmiyordu.

Gerçek veride ölçtüm:

```
cap_baslangic beyan yok → ÇAP kredisi 4.0 · eksik yok (taban iddia edilmiyor)
cap_baslangic = 5       → ÇAP kredisi 4.0 · EKSİK 5.0 kredi
```

Yani motor, tabanı 9 olan bir öğrenciye 4 kredilik bir programı "en iyi
program" diye sunuyordu.

Artık `build_schedules(..., floors={"CAP": 9})`:

* tabanı **karşılayan** programlar sıralamada öne geçiyor,
* karşılamayanlar **elenmiyor**,
* her önerinin yanında `floorGaps` var; arayüz sekmede `taban ✗` yazıyor,
* hiçbiri karşılamıyorsa bunu **açıkça söylüyor**.

### Neden sert kısıt değil

Yönerge tabanın "ÇAP Koordinatörünün uygun görüşü ve Fakülte Yönetim Kurulu
Kararı ile yarıya kadar düşürülebileceğini" söylüyor. Ayrıca o dönem açılan
ders yetmiyor olabilir — senin verinde tam olarak bu: ÇAP'tan yalnız iki ders
açık, hangi kombinasyon seçilirse seçilsin 9 krediye ulaşılmıyor.

Karşılayan hiç program yoksa eleyip boş liste döndürmek, **çözülebilir bir
durumu imkânsız göstermek** olurdu. Onun yerine sıralama değişiyor ve eksik
yazılıyor.

İndirimli değil **ilan edilen** taban kullanılıyor: indirim "düşürülebilir",
otomatik uygulamak alınmamış bir kararı alınmış saymak olurdu.
