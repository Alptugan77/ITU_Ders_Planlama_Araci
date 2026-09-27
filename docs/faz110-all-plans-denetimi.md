# Faz 110 — `make all-plans` öncesi denetim

Kullanıcı (27.09.2026): *"dikkatli bir şekilde düzeltmeleri yapıp
geliştirmeye devam eder misin sonrasında ben make all-plans yapacağım"*.

Komut, kopya katalogda (`ITUCAP_DATA` ile, gerçek `data/` dokunulmadan)
`refresh --all-programs --all-equivalences` olarak uçtan uca denendi. Ayrıca
Faz 109'da çekilen 3183 resmî denklik motorda satır satır sınandı. Sekiz
bulgu çıktı, sekizi de düzeltildi.

## Deneme sonucu (eski kodla, 21:58 → 23:29, 91 dakika)

| Adım | Sonuç |
|---|---|
| itu-helper | 11.228 ders, 3904 şube, 130 program |
| OBS anadal planı | 5 plan |
| OBS ikinci program planı | **500 hatası** (bulgu 1) |
| Bütün ÇAP/yandal planları | 1215 plan (ÇAP 1081, 63 kod; yandal 134, 76 kod), 24.793 slot, **0 hata**, ayrıştırılamayan satır yok · 63 dk |
| Resmî denklikler | 93 lisans programı, **3183 denklik**; Faz 109 taramasıyla **birebir aynı küme** · 26 dk |
| Önşart ağacı | 4641/4641 ders, 12 onarım, 0 çözülemeyen |
| Kalite raporu | 15 bulgu, **0 hata** |

Kopya temizliği atlandığı için katalogda BLGE'nin 5 + 5 planı kaldı (bulgu 1).
`docs/prereq-patterns.md` yeniden yazıldı ama içeriği değişmedi.

Yeni kodun farklı olduğu adımlar ayrıca denendi:

* **Ağsız tazeleme** (`--offline --skip-obs`): kopya temizliği 1 planı
  düşürdü, kalite raporunda 0 hata çıktı.
* **Canlı kısmi denklik taraması**: bkz. bulgu 6.
* **Yeni ayrıştırıcı**: bu taramanın satırlarında da tam 11 satırı
  düzeltiyor.

## 1. OBS plan adımı, ikinci program seçilmemişken çöküyordu

`step_obs_plans` ikinci programın planını `f"{second_program}_LS"` koduyla
istiyordu:

* **İkinci program yokken** (`second_kind = "yok"`) boş kodla
  `programKodu=_LS` isteniyordu. OBS 500 döndürdü, istisna fırladı. Aynı
  `try` içindeki itu-helper kopyası temizliği (`step_dedupe_plans`) da
  **atlandı**; aynı programın iki kaynaklı planı katalogda kalıyordu.
* **Yalnız ilk ikinci program** çekiliyordu. Oysa ÇAP ve yandal birlikte
  seçilebiliyor (`settings.seconds`).
* **Yandal kodu** zaten OBS biçiminde ("ECN_YD"). Sonuna "_LS" eklenince OBS
  500 veriyor (canlı ölçüldü: "ECN_YD" 4 plan, ÇAP "EHB_LS" 17 plan).

Artık `settings.seconds` içindeki her program ayrı adımda çekiliyor. Kodda
alt çizgi varsa olduğu gibi kullanılıyor; yoksa sonuna "_LS" ekleniyor.

**Kopya temizliği artık her koşuda.** `step_ituhelper` sentetik planları her
tazelemede yeniden yazıyor. Temizlik OBS plan adımıyla aynı `try` içindeydi;
o adım düşünce ya da `--skip-obs` ile çalışınca atlanıyordu. Önceki
koşulardan kalan OBS planlarının yanında kopyalar kalıyordu. Kum
havuzundaki denemede (eski kodla) BLGE'de 5 OBS planının yanında 5
itu-helper planı, HTAE'de 1 + 1 plan kaldı. Kullanıcının ayarında
`second_kind = "yok"` olduğundan kendi `make all-plans` koşusu da aynı
duruma düşecekti. Temizlik artık bütün OBS adımlarından sonra, onların
sonucundan bağımsız çalışıyor.

Aynı kusur iki yerde daha vardı:

* Arayüzdeki "veriyi tazele" (`server.State.refresh`) temizliği OBS
  adımıyla aynı `try` içinde yapıyordu.
* Nöbet turunda (`make watch`, `watch.tick`) temizlik **hiç yoktu**. Her
  tur itu-helper planlarını yeniden yazıyor, kopyalar bir sonraki tam
  tazelemeye kadar kalıyordu.

İkisi de artık OBS'den bağımsız temizliyor.

## 2. Resmî denklikler İngilizce kodlarda da uygulanıyor

OBS DersPlanDenklikleri kodları **dilden bağımsız, taban biçimde** yazıyor
("BBF 203 ≡ BLG 252"; 3183 kaynağın hiçbiri E'li değil). Motor kodları
birebir eşleştirdiği için İngilizce programdaki öğrencide (BBF 203E,
BLG 252E) **hiçbir resmî denklik tetiklenmiyordu**. Katalogdaki
hedeflerden 1117'si yalnız E'li kodla var.

Kural: **dil korunur** (`rules._dil_yazimlari`).

* Kaynaklar İngilizce yazımlarıyla sağlanırsa hedefin İngilizce yazımı
  kazanılır; kaynaklar Türkçeyse Türkçesi.
* Türkçe ders İngilizce anadal yuvasını doldurmaz. Bu, Faz 92 ilkesiyle
  aynı: dil serbestliği yalnız ÇAP/yandal yuvasında (`slot_codes`).
* Karışık dilli, çok kaynaklı denklik tetiklenmez (ihtiyatlı).
* Laboratuvar eki dil ekinden sonra gelir: FIZ 101L → FIZ 101EL
  (`rules.ingilizce_kod`).
* Kullanıcı **beyanları** yazıldığı gibi uygulanır; dili beyan seçer.

Denklikler ders düzeyinde. Aynı hedef iki planda farklı kaynaklarla
görünmüyor, bu yüzden denkliklerin her planda uygulanması doğru.

**Etki** (`tools/kod_gocu_taramasi.py`, 3183 denklikli katalog): plana
sadık öğrencide engelli zorunlu ders 104'ten **92**'ye indi (42 bölüm).
Gerçek BLGE profiline yeni plan yuvası eklenmedi, yani ilerleme şişmiyor.

## 3. Ayrıştırıcı, isme yapışık büyük harfi kod eki sanıyordu

Ders adı büyük harfli bir kısaltmayla başlayınca ilk harfi koda yapışıyordu:

* "EHB 101EHM Giriş…" → EHB 101E
* "SBP 126CBS ve Planlama" → SBP 126C
* "MET 435PÇT…" → MET 435P
* "DFH 490E-Seyir…" → DFH 490E

3183 satırın 11'i hatalıydı (7 farklı kod).

`_lead_code` kuralı: ek **isme yapışıksa**

* ardından küçük harf geliyorsa isim harfidir (eskisi gibi);
* "E" hiçbir zaman ek sayılmaz, çünkü sayfa taban kod yazıyor;
* "L" laboratuvar eki olarak korunur (sayfadaki 5 L'li satırın hepsi
  laboratuvar);
* başka bir harf ancak ekli kod katalogda varsa ek sayılır
  ("ING 112AAkademik…" → ING 112A).

Gerçek satırlarla yeniden ayrıştırınca tam olarak bu 11 satır değişiyor,
başka satır değişmiyor.

## 4. Denklikle gelen not: ulaşılabilen EN İYİ not

Eski kural ilk bulunan yolu kullanıyordu. 300 rastgele transkriptin 5'inde
not, listenin sırasına göre değişiyordu (DFH 321: DFH 474 yoluyla CC,
GUV 491 yoluyla CB). Kendi aldığı dersten FF olan ama denk dersi geçmiş
öğrenci de önşartta ve yuvada "kalmış" sayılıyordu.

Yeni kural monoton bir sabit nokta:

* Bir denklik, kaynaklarının en düşük notunu verir.
* Hedefe birden çok yoldan varılıyorsa, ya da ham notu denklikten
  gelenden kötüyse, **iyisi kalır**. Eşitlikte ham not kalır.
* Notu yükselen ders zincirde ilerler (A → B → C).
* Sonuç listenin sırasından bağımsız. Kod göçü görünümünün kuralıyla aynı
  (`prereq_view`, Faz 104).

**Not ortalaması etkilenmez.** Genişletilmiş notlar yalnız önşart, yuva ve
yol haritası için kullanılıyor. Bütün `policy.gpa` çağrıları ham notlardan
yapılıyor (`S.graded`); bu kontrol edildi.

## 5. Hız

3183 denklik iki dilde 6366 yazım demek. `slot_satisfied` her plan yuvası
için genişletme istiyor (gerçek BLGE profilinde bir kurulumda 1724 çağrı);
dil yazımları eklenince kurulum 5.9 sn'den 28.6 sn'ye çıktı. Alınan
önlemler:

* "Kaynak kod → yazımlar" dizini her liste için bir kez kuruluyor.
* Her tur yalnız bir önceki turda notu değişen kodlara dokunan yazımları
  deniyor.
* Aynı not seti ve aynı yazım kümesi için sonuç önbellekte tutuluyor;
  çağırana kopyası dönüyor. Sonuç kendi yazım listesiyle birlikte
  saklandığı için eskimiş bir sonuç dönemez. Yerinde değiştirilen liste
  yeniden kuruluyor.
* Denklikler tek bir JOIN sorgusuyla yükleniyor. Eskiden her denklik için
  ayrı bir kaynak sorgusu atılıyordu: 3183 denklikte çağrı başına 25 ms
  yerine artık 11 ms, bir kurulumda 14 çağrı var. Sonuç liste, sırası
  dahil, eskisiyle birebir aynı (gerçek katalogda karşılaştırıldı).

Gerçek BLGE profili artık **3 sn**'de kuruluyor (Faz 109'da 5.9 sn).
Doğrulama: 300 rastgele transkriptte sonuç, her turda bütün listeyi tarayan
naif uygulamayla birebir aynı; liste karıştırılınca da değişmiyor
(0/300 fark, 0/300 sıra farkı).

## 6. Denklik taraması eski tabloyu ancak tam sonuçla eziyor

`step_equivalence`, eski resmî denklikleri silip yeni sonucu sayfa sayfa
commit ediyordu. Tam tarama yaklaşık 26 dakika sürüyor ve 1200 kadar
istek atıyor. Şu
durumlarda yayınlanacak katalog boş ya da eksik kalıyordu:

* Faz 109'daki gibi sessizce kırılmış bir kazıyıcı (0 denklik),
* ağın yarıda kopması ya da **Ctrl-C**,
* birkaç programın hata vermesi.

Kalite raporu yalnız tablo tamamen boşken uyarıyordu.

Artık silmeden önce yedek alınıyor. Şu durumlarda eski tablo geri
yükleniyor (`pipeline.denklik_korunmali`):

* tarama istisnayla kesilirse (Ctrl-C dahil);
* hiç denklik gelmezse;
* program hataları varken yeni tablo eskisinden küçükse;
* yeni tablo eskisinin yarısından küçükse.

Eski tablo boşsa her sonuç kabul ediliyor, çünkü kaybedilecek bir şey yok.
Reddedilen tarama hem çıktıda hem `ingest_run` mesajında yazıyor.
`sweep_all` artık hata veren programları sayıyor.

**Kısmi tarama artık birleştiriyor.** Faz 34'ün önerdiği akışta tam
taramadan sonra hızlı tazeleme için ayara `eq_program_ids` yazılıyor. Eski
kod bu tazelemede 3183 satırlık tabloyu seçilen programların satırlarıyla
eziyordu; yeni koruma da onu her seferinde reddederdi. Artık yalnız seçilen
programların satırları (`source_url`deki `ProgramId`) silinip yenileniyor.
Diğer programların satırları `seen`e konuyor, böylece aynı denklik ikinci
kez yazılmıyor. Koruma yalnız bu kapsamı karşılaştırıyor.

**Canlı deneme** (3183 denklikli kopya katalog, program 153):

* Eski birleştirmesiz kod tabloyu 269 satıra indirecekti. Koruma bunu
  reddetti ve 3183 satır birebir korundu.
* Birleştirmeli kod programın 144 satırını yeniledi (içerik aynı). Diğer
  programların 3039 satırı değişmedi, tekrar eden çift yok.

## 7. Uzun taramada ilerleme

Plan taraması kum havuzunda 63 dakika sürdü (ÇAP 63 kod, yandal 76 kod;
1215 plan, 24.793 slot, 0 hata, ayrıştırılamayan satır yok). İlk 20 kod
tek başına 19 dakika tuttu. Eskiden yalnız her 20 sorguda bir satır
yazılıyordu. Artık önce toplam yazılıyor ("cap: 63 program kodu taranacak
(keşif)"), ardından her 10 kodda bir "cap 10/63 kod" satırı geliyor.

## 8. Kalite uyarısı yanıltıcıydı: "1146 denklikte hedef ders bulunamadı"

Denemenin kalite raporunda bu uyarı çıktı. Kontrol hedef kodu katalogda
birebir arıyordu. 1146 hedefin 1126'sı katalogda yalnız İngilizce
yazımıyla var (bulgu 2); motor onları zaten buluyor. Kontrol artık resmî
denklikte iki yazımı da deniyor. Beyanlarda yalnız yazıldığı gibi arıyor,
motorla aynı kural. Uyarı örnek de veriyor. Deneme kataloğunda 20 gerçek
eksik kaldı; yeni ayrıştırıcıyla **14**'e iniyor (ELE 321, TEL 412,
TEL 331, BLG 332, CEN 103 …, yani kapanmış dersler).

## Doğrulama

* **Testler:**
  * `tests/test_faz110_all_plans.py`: ikinci program yok / ÇAP / ÇAP +
    yandal; ilerleme çıktısı; OBS adımı düşünce ve `--skip-obs`'ta kopya
    temizliği (komut satırı, arayüz, nöbet turu).
  * `tests/test_faz110_denklik_dil.py`: ek ayrıştırma (10 durum), İngilizce
    kod, dil korunur, beyan yazıldığı gibi, karışık dil, anadal yuvası dil
    kuralı, en iyi not (iki sıra), FF + denk geçmiş, zincirde yükselme,
    önbellek kirletilemez, yerinde değişen liste, tek sorgulu yükleyici,
    kalite kontrolünde iki yazım.
  * `tests/test_faz110_denklik_koruma.py`: tam tarama ezer; boş, hatalı ve
    küçük, yarıya inen, istisna ve Ctrl-C taramaları eskiyi korur; eski
    boşsa her sonuç kabul; `sweep_all` hataları sayar; kısmi tarama yalnız
    kendi programını yeniler (ProgramId=1, 15 ve 153 karışmıyor), boş
    kısmi tarama eskiyi korur.
* **Mutasyonlar:** 33 mutasyonun 33'ü kırmızı: dil, ayrıştırıcı, en iyi
  not, önbellek, yükleyicide varsayılan not, ikinci programlar, kopya
  temizliği (üç yerde), ilerleme çıktısı, denklik korumasının 9 kolu,
  kısmi taramanın 4 kolu ve kalite kontrolünün 2 kolu.
  Yükleyicideki `ORDER BY … s.course_code` kaldırılınca sonuç değişmiyor:
  SQLite kaynakları zaten birincil anahtar dizininden, kod sırasıyla
  okuyor. Sıralama yalnız bu davranışı güvenceye alıyor.

## `make all-plans` sonrası

Süre: yaklaşık 1.5 saat (plan taraması 63 dk, denklikler 26 dk).

1. Çıktının başında "OBS plan adımı başarısız" satırı **olmamalı**.
2. "Tüm programlar: 1215 ÇAP/yandal planı … (0 hata)" civarı bir satır
   beklenir.
3. Denklik satırında "YENİ TABLO REDDEDİLDİ" yoksa yeni tablo yerleşmiştir
   (beklenen 3183 denklik).
4. Kalite raporunda 0 hata beklenir. `orphan_equivalence` uyarısı yaklaşık
   14 denklik (kapanmış dersler) göstermelidir.
5. `python tools/kod_gocu_taramasi.py`: 18 beyanın 18'i resmî listede,
   engelli ders yaklaşık 92 beklenir.
6. `docs/prereq-patterns.md` her tazelemede yeniden yazılıyor (izlenen
   dosya). Kum havuzunda içerik değişmedi; değişirse farkı commit etmek
   isteğe bağlı.
7. Siteyi yeniden kurunuz; öğrenciler yeni kataloğu ancak o zaman görür.
