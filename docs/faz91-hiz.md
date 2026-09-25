# Faz 91 — öneri motoru ve istekler 3–5 kat hızlı; sonuçlar birebir aynı

Kullanıcı 25.09.2026: *"continue your improvements"*.

Faz 90 ölçümlerinde en büyük kullanıcı sorunu hızdı. Gerçek katalogla kurulan
statik sitede (Pyodide) her program ya da dönem değişikliği **7–8 sn**
sürüyordu. Yerelde bir anlık görüntü 0,5–5,5 sn arasındaydı.

## Profil (INSE 1. yarıyıl, yerel)

| Sıcak nokta | Pay | Neden |
|---|---|---|
| `yuva_ata` — 282.000 çağrı | ~%60 | Faz 81'in havuz eşleştirmesi her arama düğümünde **baştan** koşuyordu |
| `load_sections` — 1031 çağrı, 191 farklı | %34 | yol haritası bir istekte 12 kez kuruluyor; her kurulum aynı şubeleri yeniden okuyordu |
| çakışma denetimi — 485.000 karşılaştırma | — | her aday şube, seçilen her şubeyle buluşma buluşma karşılaştırılıyordu |
| kural dosyaları — 50 TOML ayrıştırma; ders adları — 12 okuma; önşart ağaçları — 16 kurulum | — | yine her harita kurulumunda baştan |

## Düzeltmeler — davranış değişmiyor

1. **Artımlı yuva eşleştirmesi** (`recommend.yuva_ekle`).
   * Aramanın bir değişmezi var: seçilen dersler her zaman tamamen eşleşmiş,
     çünkü her seçim bu denetimden geçerek eklendi.
   * Berge teoremine göre yeni aday ancak kendisinden başlayan bir artırma
     yolu varsa eklenebilir. Bu yüzden baştan Kuhn yerine **tek bir DFS**
     yetiyor; cevap birebir aynı.
   * Eşleştirme yığında tutuluyor; geri izlemede önceki hâline dönülüyor.
   * Ucuz yük denetimi artık eşleştirmeden önce yapılıyor. İkisi VE ile
     bağlı olduğu için sonuç aynı.
2. **Dakika maskesi** (`Section.maske`).
   * Şubenin haftası tek bir tam sayı: her gün 2048 bitlik bir blok,
     buluşmanın her dakikası bir bit.
   * İki şube ancak maskeleri ortak bit taşıyorsa çakışıyor. Bu, `overlaps`
     ile aynı koşul: aynı gün ve `a.start < b.end and b.start < a.end`.
   * Arama, seçilenlerin ve meşgul saatlerin maskesini yığında biriktiriyor;
     "bu şube sığar mı" tek bir AND oluyor.
3. **İstek boyunca önbellek** (yeni `istek` modülü).
   * Önbellek yalnız **bir istek** boyunca yaşıyor: anlık görüntü, kalma
     riski, senaryo, ÇAP seçenekleri.
   * Bu süre içinde şubeler, ders adları ve önşart ağaçları bir kez okunuyor.
   * ⚠️ İstekler arası önbellek yok. Kontenjan tazelemesi satırları UPDATE
     ediyor; kalıcı bir önbellek eski doluluğu gösterirdi. İstek içinde veri
     değişmiyor (sunucuda tek kilit, sitede tek iş parçacığı).
   * Çağırana liste kopyası veriliyor; nesneler hiçbir yerde değiştirilmiyor
     (ölçüldü).
   * Modül siteye de gidiyor (`tools/site_kur.py` ENGINE listesi).
4. **Kural dosyaları METNE göre saklanıyor.**
   * Metin her seferinde okunuyor (ucuz); ayrıştırma sonucu saklanıyor.
   * Zaman damgasına güvenilmiyor, çünkü Linux'ta kaba ve testler dosyayı
     hızla yeniden yazıyor.
   * Çağırana derin kopya veriliyor. Kişisel ayar dosyası bu önbelleğe
     alınmıyor.

## Ölçüm

**Eşdeğerlik.** 9 gerçek katalog profili × 3 öneri listesinde her önerinin
dersleri, CRN'leri ve puanı **birebir aynı**. Kalma riski, senaryo ve ÇAP
seçenekleri uçlarının cevapları da **birebir aynı**.

**Yerel, anlık görüntü:**

| Profil | Önce | Sonra |
|---|---|---|
| KMM 1 | 4,74 sn | 1,00 sn |
| JEO 1 | 5,55 sn | 1,04 sn |
| INSE 1 | 5,33 sn | 1,09 sn |
| ELKE 1 | 4,16 sn | 0,86 sn |
| BLGE 5 (transkriptli) | 0,73 sn | 0,45 sn |
| **9 profil toplamı** | **25,2 sn** | **6,8 sn (3,7×)** |

**Yerel, istek üzerine hesaplar** (BLGE 5, transkriptli):

| İstek | Önce | Sonra |
|---|---|---|
| Kalma riski | 0,39 sn | 0,13 sn |
| ÇAP seçenekleri (10 program) | 0,60 sn | 0,36 sn |
| Senaryo | 0,046 sn | 0,034 sn |

**Statik site** (Pyodide, gerçek katalog, KMM 3, aynı makine):

| Değişiklik | Önce (Faz 90) | Sonra |
|---|---|---|
| Program değişikliği | 7,70 sn | **~1,9 sn** (4×) |
| Dönem değişikliği | 6,60 sn | **~1,3 sn** (5×) |

Açılış süresi (~4 sn) değişmedi; o, Pyodide'in ve katalogun yüklenmesi.

## Testler

`tests/test_faz91_hiz.py`:
* **Artımlı eşleştirme:** eski `yuva_ata` karşısında 40 rastgele dizi. Her
  adımda cevap aynı ve eşleştirme geçerli. Girdi değişmiyor.
* **Maske:** eski `overlaps` karşısında 30 rastgele şube kümesi (tüm
  çiftler). Sınırlar: 11:29 biten / 11:30 başlayan, farklı gün, saatsiz şube.
* **İstek önbelleği:**
  * bağlam dışında saklamıyor, içeride bir kez hesaplıyor, iç içe bağlamda
    dıştakini kullanıyor, bağlam bitince temizleniyor;
  * çağıranın listeyi bozması önbelleği etkilemiyor;
  * UPDATE'ten sonraki istek yeni veriyi görüyor.
* **Kural dosyası:** kopya dönüyor; aynı boyda hızlı yeniden yazım görülüyor.
* **Bağlantılar:** dört uç sarılı; `istek` site listesinde.
* **Vitrin:** bir anlık görüntüde her (ders, izinli) bir kez okunuyor. Bu
  test alt süreçte koşuyor: `vitrin.kur` `config`i geçici dizine çeviriyor
  ve aynı süreçte koşunca sonraki 8 test dosyalarını bulamadı. Tam takımda
  görüldü ve düzeltildi.

Önbelleksiz (`-B`) geri alma deneylerinde 10 kuralın 10'u kırmızı.
Aramadaki yığın bağlantıları (eşleştirme yığını, seçilen maskesi, meşgul
saat maskesi) mevcut motor testleriyle yakalanıyor.
