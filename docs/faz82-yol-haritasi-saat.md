# Faz 82 — Yol haritası derslerin saatlerine bakıyor

*24.09.2026 · kullanıcı: "yol haritasında derslerin saatlerinin toplamı
alabileceğim saatlere sığmıyor gibi geldi biraz imkansız bir tahmin ve
hesaplama bunu biraz geliştirir misin".*

Testler +6 (`tests/test_faz82_yol_haritasi_saat.py`). Geri alma deneyi: altı
kuralın altısı kırmızı.

## Sorun

Harita her gelecek dönemi yalnız **kredi sınırına** kadar dolduruyordu (vitrin:
25 sınırda 24 kredi). O derslerin aynı hafta içinde **çakışmadan** alınıp
alınamayacağına ve öğrencinin **meşgul saatlerine** (iş, staj) hiç bakmıyordu;
"Kontenjan, şube ve saat çakışması bu planda dikkate alınmamıştır" diye
yazıyordu. GNO 3.00'ü geçip sınırı 40 krediye çıkan öğrenciye dönem başına 40
kredilik, haftaya sığmayacak dönemler de çizebilirdi.

## Ne değişti

1. **Aynı mevsimde çakışma denetimi.** Bu dönemin şube saatleri, aynı
   mevsimin sonraki dönemleri (bu Güz → sonraki Güz'ler) için en iyi bilgi —
   İTÜ'de ders saatleri yıldan yıla çoğunlukla korunuyor. Bir ders o döneme
   ancak seçilenlerle **çakışmasız bir şube kombinasyonu** kurulabiliyorsa
   giriyor; kurulamıyorsa sonraki uygun döneme kalıyor ve kart bunu
   ("Saat çakışması nedeniyle bu döneme konamadı: …") söylüyor. Arama
   bütçeli (20.000 adım); bütçe biterse "bilinmiyor" sayılıp kısıt
   uydurulmuyor. Şubesi hiç olmayan ders denetimi daraltmıyor.
2. **Meşgul saatler.** Harita artık meşgul saatleri alıyor (sayfa, senaryo,
   kalma riski, ÇAP seçenekleri — dört çağıranın dördü): bu saatlerle çakışan
   şubeler sayılmıyor.
3. **Haftalık saat bütçesi — bütün dönemlerde.** Ders penceresi Pzt–Cum
   08:30–17:30 (45 sa) eksi meşgul saatler. Dersin haftalık saati bu dönem
   şubesi varsa en kısa şubesinden, yoksa kredi × ölçülen dakika/kredi
   oranından (şubesi olanların ortancası). Öbür mevsimde (saat bilinmeyen)
   tek denetim bu; meşgul saat yoksa pratikte bağlamıyor.
4. **Kartta:** "≈ 25 sa/hafta ders · bu dönemin şube saatleriyle çakışmasız
   program kurulabiliyor" ya da "saatler bilinmiyor; yalnız haftalık saat
   denetlendi"; ertelenen dersler nedeniyle.
5. **Yerleşemeyen dersin gerekçesi somut:** "bu dönemin bütün şubeleri meşgul
   saatlerinizle çakışmaktadır", "her denendiği dönemde öbür derslerle saat
   çakışması oluşmaktadır", "haftalık boş saat yetmemektedir". Yolda eski bir
   yanlış da düzeldi: önşartı planda olan ama yerleştirilemeyen ders için
   "önşartı **planlarda bulunmayan**" yazıyordu → "önşartı yerleştirilemeyen
   ders(ler)e bağlıdır".

## Gerçek katalogda ölçüm

* ENDE 7. yarıyıl ve MAKE + Ekonomi yandalı: Güz dönemlerinde (≈22 kredi,
  ≈25 sa/hafta) çakışmasız program **kurulabiliyor** — erteleme yok; artık bu
  bir varsayım değil, denetlenmiş bir bilgi ve kartta yazıyor. Bahar
  dönemlerinin saati bilinmiyor; orada yalnız haftalık saat denetleniyor.
* Pzt–Çar tam gün çalışan (vitrin) öğrencide BLG 223E, GEO 315E… Güz'de
  hiçbir döneme konmuyor ve gerekçesi yazıyor; önceden harita bunları
  sorunsuz yerleştiriyordu.
* Hesap süresi: vitrin 0,13 sn, gerçek sitede (Pyodide) 1–1,4 sn.
