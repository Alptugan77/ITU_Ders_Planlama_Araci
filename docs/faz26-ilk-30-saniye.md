# Faz 26 — ilk 30 saniye

> Kullanıcı, 24.08.2026: *"kullanıcı deneyimini artırır mısın, ben siteye
> ilk girdiğimde hâlâ nasıl yapacağımı anlayamayabilirim. sen de siteye
> girip bi bak."*

Siteye girdim. **Yayındaki sürüm Faz 23'ten kalma** — depoda `git remote`
yok, 26 commit yalnız yerelde duruyor, dolayısıyla Faz 24–25'in hiçbiri
sitede değil. Yayındaki sayfada karşılama kartı, katalog araması, geri al,
verinin yaşı — hiçbiri yok; boş bir haftalık ızgara ve "aday ders yok"
yazıyor. Haklı olarak "nasıl yapacağım" sorusu doğuyor.

Ama **yereldeki yeni sürümde de** haklıydı. Ona fresh gözle bakınca dört
ayrı sorun çıktı.

---

## 1. Üç adım da ZORUNLU görünüyordu

Kart "Hoş geldin — **üç adımda kur**" diyordu. Oysa yalnız **bölüm**
zorunlu: bölüm seçilince araç zaten çalışıyor, transkript ve dönem
öneriyi **iyileştiriyor**. Üçünü de zorunlu göstermek, ekranın arkasında
olmayan bir duvar inşa ediyordu.

Artık:

* başlık **"Hoş geldin — tek adımda başla"**,
* zorunlu adım ile isteğe bağlı iyileştirmeler ayrı bloklarda,
  aralarında *"Daha iyi öneri için"* ayracı,
* bölüm seçilince başlık **"Araç çalışıyor — istersen daha da iyileştir"**
  oluyor ve rapor açılıyor.

## 2. Yedi düğme üç iş yapıyordu

Karşılama kartında üç "Aç" düğmesi, hemen altındaki kurulum çubuğunda dört
düğme daha. Hangisinin birincil olduğu belli değildi.

Artık **tek bir birincil eylem** var: sıradaki ilk yapılmamış adımın büyük
düğmesi. O adımın satırında düğme **tekrarlanmıyor** ("şimdi ↑" yazıyor).
Kurulum çubuğu, karşılama sürerken **gizli** — kurulum bitince geri geliyor,
çünkü orada işlevi değiştirmek değil, yapılanı görmek.

## 3. "Aç" bir eylem adı değil

Neyi açtığı yazmıyordu. Artık her adımın kendi eylem adı var: **Bölümünü
seç · Dersleri gir · Dönemi seç**. Yanında süre (*10 saniye · 1 dakika ·
5 saniye*) ve *ne işe yaradığı* ayrı satırda.

Sırası gelmemiş adım **kapalı** ve nedeni yazıyor — tıklanınca çıkmaza
düşen bir düğme, olmayan bir düğmeden kötü.

## 4. ★★ "%0 tamamlandı · kalan zorunlu 44"

Ekranın en görünür yerindeydi. Bölümünü seçen kişi, hiçbir şey girmeden,
ilerleme panelinde **%0** ve **"kalan zorunlu 44"** görüyordu.

Bu bir ölçüm değil: hakkında hiçbir şey bilmediğimiz kişiye *"hiçbir şey
yapmamışsın"* demek. Kredi tavanında (Faz 24) ve başvuru şartlarında zaten
düzeltilen hatanın aynısı, en görünür yerde duruyordu.

Artık transkript yokken:

* yüzde yerine **"—"**,
* panelde **"İlerleme bilinmiyor — geçtiğin dersleri girmedin"** ve yanında
  **Dersleri gir** düğmesi,
* sayılar gizlenmiyor ama etiketleri değişiyor: *"kalan zorunlu 44"* →
  **"zorunlu ders 44"**, *"slot 0/58"* → **"planda slot 58"**, ve altında
  *"Aşağıdaki sayılar planın tamamı, senin kalanın değil."*

⚠️ Sayıyı gizlemek de olmazdı: plan büyüklüğü gerçek bir bilgi. Değişen,
onun **kime ait** olduğu iddiası.

---

## Küçükler

| Ne | Neden |
|---|---|
| Başlık altı: önce araç ne yapıyor, sonra sayılar | *"3417 açık şube · dönem yükü sınırı: transkript girilince"* ilk giren için bağlamsız jargondu |
| "Şimdilik böyle kalsın" | Transkript girmek istemeyen kişi şeridi sonsuza kadar görmemeli. ⚠️ Zorunlu adım eksikken kapatılamıyor — o zaman gösterilecek doğru bir rapor yok |
| Kurulumdan sonra "Programın hazır. Şimdi:" | Dokuz bölüm birden açılıyordu ve hiçbiri "şunu yap" demiyordu. Üç somut eylem, kapatılabilir |
| `localStorage` sarmalayıcı | Gizli sekmede erişim **bile** hata fırlatıyor; tercih kaybolabilir ama sayfa çalışmayı sürdürmeli |
| Telefonda adım satırı | Düğme ve süre metnin yanındayken açıklama 12 karakterlik şeride sıkışıyordu (390 px'te ölçüldü) |

---

## Ölçüm

```
1) başlık altı : İTÜ'nün açık derslerinden çakışmasız haftalık program kurar
                 — önşart, kontenjan ve kredi tavanını denetleyerek.
1) hero başlık : HOŞ GELDİN — TEK ADIMDA BAŞLA
1) düğmeler    : Tema · Bölümünü seç · Dersleri gir(kapalı) · Dönemi seç(kapalı)
1) kurulum çubuğu görünür: False

2) hero başlık : ARAÇ ÇALIŞIYOR — İSTERSEN DAHA DA İYİLEŞTİR
2) program görünür: True
2) yüzde       : "—"   (transkript yok)
2) uyarı       : İlerleme bilinmiyor — geçtiğin dersleri girmedin.
                 Aşağıdaki sayılar planın tamamı, senin kalanın değil.

3) "şimdilik böyle kalsın" → hero gizli, şerit: Programın hazır. Şimdi: …
4) yenileme sonrası hatırlıyor
telefon (390px): yatay taşma yok
sayfa hatası   : []
```

Testler **782 → 802**.

---

## ⚠️ Sitede hâlâ eskisi duruyor

Bu depoda `git remote` **tanımlı değil**. 26 commit yalnız yerelde:

```bash
git remote add origin https://github.com/Alptugan77/ITU_Ders_Secim_Araci.git
git push -u origin main
```

Push edilmeden Faz 24, 25 ve 26'nın hiçbiri siteye çıkmıyor.
