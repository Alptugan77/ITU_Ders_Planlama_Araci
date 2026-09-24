# Faz 66 — Arayüz metinleri resmî dile çevrildi

*24.09.2026 · kullanıcı: "bir plan, kehanet değil gibi lafları azaltıp resmi
bir şekilde açıklamaları oluşturur musun".*

Arayüzün tamamı "sen" hitabıyla ve yer yer slogan niteliğinde cümlelerle
yazılmıştı ("Bir plan, kehanet değil", "uydurmuyoruz", "işine yaramaz").
Görünür metnin tamamı resmî bir üsluba çevrildi. Testler **1307 geçti**,
4 atlandı; tasarım denetimi ve gizlilik denetimi temiz.

## Üslup kuralları (bundan sonraki metinler için)

1. **Açıklamalar kişisiz ve edilgendir:** "Kalan dersler … dikkate alınarak
   dönemlere yerleştirilmiştir", "… varsayılmıştır".
2. **Doğrudan hitap gerekiyorsa "siz":** "Bölümünüzü seçin", "danışmanınıza
   başvurunuz". "Sen" hitabı ve "-sın/-sin" ekleri kullanılmaz.
3. **Gezinme ve başlıklar isim tamlamasıdır:** "Alınabilecek dersler",
   "Alınamayan dersler", "İlerleme durumu", "Kredi ve not eşikleri".
4. **Düğmeler** Türkçe arayüz geleneğindeki kısa emir kipini korur
   ("Kaydet", "Kapat", "Yazdır"); cümle düğmelerde "siz" kullanılır
   ("Dersleri girin").
5. **Slogan, espri ve büyük harfle vurgu yoktur** ("YOK", "HİÇ", "DEĞİL"
   yerine düz yazım ve `<b>`).
6. Aracın dürüstlük ilkesi değişmedi, yalnız dili değişti: bilinmeyen şey
   yine açıkça "bilinmemektedir / hesaplanamamaktadır / tahminidir" diye
   yazılır.

## Kapsam

* `src/itucap/ui.py` — sayfa şablonu, bütün görünümler ve pencereler
  (kurulum, dönem, plandan işaretleme, transkript, tercihler, kilitler,
  boş saat, kayıt günü, paylaşım, katalog araması, danışman özeti, başvuru,
  yol haritası, kredi eşikleri, ilerleme panelleri), hata ve boş durum
  iletileri, kurulum adımları (`_onboarding`).
* `src/itucap/yolharitasi.py` — yol haritası varsayımları ve
  "yerleştirilemedi" sebepleri.
* `src/itucap/recommend.py` — puan gerekçeleri, tercih gerekçeleri,
  engeller ("bu dönem şube açılmamıştır").
* `policy.py`, `basvuru.py`, `plans.py`, `student.py`, `server.py` —
  arayüze ulaşan gerekçe ve hata iletileri.
* `web/app.js` ve `tools/site_kur.py` — statik sitenin yükleme ekranı.
* Danışmana sorulacak sorular öğrencinin ağzından (birinci tekil kişi)
  kaldı, ancak resmî yazıldı: "Hangi dersi bırakmam gerekir veya sınırın
  artırılması mümkün müdür?"
* Komut satırı (terminal) çıktıları geliştirici aracı olduğundan bu fazın
  dışında bırakıldı.

## Testler

Metni sabitleyen 71 test yeni metne yönlendirildi; her testin denetlediği
olgu (ör. "transkript yokken sınırın bilinmediği yazıyor", "tercihler eleme
yapmıyor") aynı kaldı, yalnız aranan ifade değişti. Uçtan uca testler
(yol haritası, senaryo, danışman özeti, kilitler, boş saat) yeni metinle
tarayıcıda geçiyor.
