# Faz 62 — Site yarı boş açılıyordu

*24.09.2026 · kullanıcı: "the site is not working properly it doesnot load the
courses and other stuff it is semi-blank can you fix it".*

Testler **1289 → 1294** (+5), 4 atlandı.

## Nasıl ölçüldü

Yayındaki site bu ortamdan açılamıyor (ağ politikası). Onun yerine yayının
**aynısı** kuruldu: `katalog-20260918` sürüm varlığı (sha256 eşleşti) +
`pyodide@314.0.5` + `tools/site_kur.py`, yerel sunucuda gerçek Chromium.
Ekran yarı boştu; konsolda TEK satır yoktu ve sunucu yalnız `/` isteği
almıştı — `app.js` hiç istenmemişti.

## 1. ★★ Sebep: yükleyici <style>'ın içine yazılıyordu (Faz 61'in hatası)

`site_kur.kabuk` yükleyiciyi ve `app.js`i `str.replace("<body>", …, 1)` ile
İLK "<body>" METNİNE yazıyordu. Faz 61'de danışman özetinin baskı kuralına
yazdığım CSS yorumu "kap <body>'ye taşınıyor" diyordu; yükleyici ve betik
<style>'ın içine girdi, tarayıcı onları metin saydı. Python hiç başlamadı,
katalog hiç yüklenmedi — başlık ve boş bölüm kabukları kaldı.

* Yorumlardaki `<body>` kaldırıldı.
* `kabuk` artık GERÇEK sınırı hedefliyor (`</head>\n<body>`) ve tam bir kez
  bulamazsa kurulum DURUYOR — sessizce bozuk site yayınlanmıyor.
* `test_faz62_site_acilis.py`: kurulan kabuk bir HTML ayrıştırıcıyla
  okunuyor; `app.js` ve yükleyici gerçek etiket, `<body>` içinde. Asıl hata
  geri konunca üç test kırmızı.

Vitrin testleri bunu yakalamadı çünkü vitrin yerel uygulamayı (`make app`)
açıyor, statik kabuğu değil — bu faz o boşluğu kapatıyor.

## 2. Sitede yol haritası hiç görünmüyordu

Sitede kimse `term` ayarı girmiyor; yol haritası, ÇAP seçeneklerinin bitişi
ve senaryolar yalnız yerel uygulamada çalışıyordu. `_aktif_donem`: ayar
yoksa, şubelerin HEPSİ tek bir döneme aitse o dönem (katalogun kendisi);
karışık ya da boşsa bilinmiyor — uydurma yok.

## 3. Gerçek katalogda bitiş hep "hesaplanamadı"ydı

Önşartı hiçbir planda olmayan ders (ING 201, MAT 210 gibi kod göçleri —
fikirler §1.1) hiç yerleşmiyordu; BLG + EHB ÇAP'ta iki programın ikisinin de
bitişi "hesaplanamadı" çıkıyordu. Okunamayan önşartla aynı kural: ders
yerleşiyor, derste "önşart varsayıldı: …", kartta "N dersin dış önşartı
varsayıldı", varsayım kutusunda liste. Planlı önşart eksikse ders yine
bekliyor (test).

## 4. Faz 60 çevrimdışı testi ~%50 kırmızıydı — kök sebep

"Kararsız" bir kök sebep değil. Ölçüldü:

* HTTP `Last-Modified` saniye çözünürlüklü; test 1,4 sn sürüyor. ESKI/YENI
  katalog ve `sw.js` aynı saniyede yazılınca yeniden doğrulama 304 alıyor,
  yeni sürüm hiç kurulmuyordu. Yayında olmaz (ETag, dağıtımlar ayrı);
  düzenekte dosya zamanları ileri alınıyor.
* Bekleme koşulu boşuna sağlanabiliyordu; artık yeni `sw.js`'ten hesaplanan
  önbellek ADINI bekliyor. 20/20 yeşil; üç koruduğu hata geri konunca yine
  kırmızı.
* ★ Yolda gerçek bir `sw.js` hatası: devir teslimde eski SW, yenisinin
  sildiği önbelleği `caches.open` ile YENİDEN yaratıyordu. Önbelleği artık
  yalnız `install` yaratıyor; yerine yenisi geçmiş SW hiçbir şey saklamıyor.
