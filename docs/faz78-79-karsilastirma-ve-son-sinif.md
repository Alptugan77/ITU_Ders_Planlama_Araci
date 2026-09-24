# Faz 78–79 — Programlar yan yana · son sınıf öğrencisiyle gerçek site

*24.09.2026 · kullanıcı: "geliştirmelere devam et ve sonrasında pr oluştur".*

Testler **1351 → 1367** (+16; `tests/test_faz78_karsilastirma.py`,
`tests/test_faz79_son_sinif.py`), 4 atlandı. Geri alma deneyi: **11 kuralın
11'i** geri konunca kırmızı (§3).

## 1. Faz 78 — Karşılaştırma bütün programları kapsıyor

Faz 77 alternatif programları getirdi, ama "Karşılaştır" yalnız motorun
önerilerini yan yana koyuyordu; "Plan B mi Plan C mi" yine sekme ezberlemekti.

* Sütunlar: **öneriler + ızgaradaki program + kaydedilen program +
  alternatifler**. Aynı program birden çok adla geliyorsa tek sütun, başlıkta
  adlar birlikte ("Izgaradaki = Plan B").
* Her sütun **aynı işlevle** ölçülüyor (`programOlcu`): kredi, ders, puan, dolu
  günler, boş gün, en erken/en geç, ders arası bekleme, kampüs değişimi,
  çevrimiçi, saatsiz. Tanım sunucunun `_program_sekli` ve `campus_changes`iyle
  aynı — test, her öneri için istemci ölçüsünün sunucunun şekliyle **birebir**
  aynı olduğunu doğruluyor.
* Yeni satırlar (yalnız bir sütunda varsa): **Dolu şube**, **Çakışma**.
* Sütun düğmesi: öneri için "Bunu seç", program için "Programa yükle" (geri
  alınabilir).
* "Karşılaştır" sekmesi artık iki ya da daha çok **farklı** program varsa
  çıkıyor (tek öneri + bir alternatif de yeter). Kayıtlı bölümünde
  "Yan yana karşılaştır" düğmesi.

## 2. Faz 79 — 7. yarıyıl, ikinci programı olmayan öğrenci (gerçek site)

Site gerçek katalogla kuruldu (Pyodide). Öğrenci: Endüstri Mühendisliği
(İngilizce), 7. yarıyıl, ikinci program yok, 2021 planından 34 derslik
transkript (END 331E FF, beş şartlı geçer not, üç BL). Üç hata çıktı.

### 2.1 ★★ Transkript: "Türk"ün T'si not sanılıyordu

`TUR 121 Türk Dili I 0 2 BL` satırında ayrıştırıcı kodun hemen ardındaki
`[A-Za-z]{1,2}` parçasını not arıyordu; "ü" ASCII olmadığından **"T"**
yakalanıyordu — T = dersten çekilme. Ders **BAŞARISIZ** kaydedildi ve yeniden
öneriliyordu (TUR 121, TUR 122 programa girdi). "Mühendislik" → "M" (muaf)
aynı tuzak.

Düzeltme: not parçası ancak ardından **boşluk, satır sonu ya da `, ; |`**
geliyorsa not (`_NOT_SONU`). Gerçek "T" (`TUR 121 T`) ve kısa biçimler
(`mat 103e cc`, `MAT 103E, BB`, `MAT 103E|AA`, `BA+`, `--`, `?`)
değişmedi — hepsi parametreli testte.

### 2.2 ★★ İkinci programı olmayana ÇAP eşikleri

İkinci program yokken eşikler "genel" kapsamla yükleniyordu ve `applies_to`
genel kapsamda **her eşiği** kabul ediyor. ÇAP'sız 7. yarıyıl öğrencisi
"ÇAP'a devam ≥ 2.50 ✗ ¹", "ÇAP mezuniyeti — üniversite GNO ✗", "1 eşik
hesaplanamıyor: ÇAP planında harf notlu ders bulunmadığından…" görüyor; danışman
özeti ona "ÇAP'a devam için… nasıl ulaşabilirim?" dahil **dört ÇAP sorusu**
yazıyordu.

Düzeltme (`_threshold_info`): kapsam genelken yalnız **genel** eşikler ve
**başvuru** eşikleri (bir seçenek olarak) kalıyor; kayıtlı olunmayan programın
devam/mezuniyet eşiği uygulanmıyor. Aynı yerde bir kaçak da kapandı: planı
bulunamayan ama **beyan edilen** ikinci program (`plansiz`) kapsama giriyor —
yoksa planı çekilmemiş ÇAP öğrencisinin ÇAP eşikleri bu düzeltmeyle
kaybolurdu.

### 2.3 ★ İstek üzerine kurulan haritalar havuz yuvasını bilmiyordu

Sayfadaki yol haritası bu dönem alınan seçmelinin **havuz yuvasını**
(`slotId`) biliyordu; istek üzerine kurulanlar (`_harita_girdisi`: Faz 59 ÇAP
seçenekleri, Faz 61 senaryolar, Faz 75 kalma riski) `slotId: 0` sabitiyle
kuruluyordu → alınan seçmelinin yuvası BOŞ sayılıp ileriki bir döneme bir ders
daha konuyordu. Gerçek sitede aynı program için iki bitiş: yol haritası
**2027-2028 Güz**, kalma riskinin tabanı **2027-2028 Bahar**.

Düzeltme: haritanın "bu dönem" öğeleri `slotId` taşıyor; `capBitisGirdi` ve
`kalmaGirdi` onu gönderiyor; `_harita_girdisi` doğrulayıp (tamsayı, ≥ 0,
bozuksa 0) geçiriyor. Düzeltmeden sonra gerçek sitede ikisi de 2027-2028 Güz.
(Vitrinde seçmelinin yuvası iki yoldan da aynı çözülüyor; test bu yüzden
aktarımı ölçüyor: sayfadaki yuvalar istek ucunda korunuyor, kalma riskinin
tabanı sayfadaki haritayla aynı.)

## 3. Geri alma deneyi

| Faz | Geri konan | Kırmızı |
|---|---|---|
| 78 | Aynı program iki sütun | statik + uçtan uca |
| 78 | Alternatifler sütun değil | statik + uçtan uca |
| 78 | İstemci ölçüsü sunucudan farklı (bekleme) | uçtan uca |
| 78 | "Programa yükle" alternatifi yüklemiyor | statik + uçtan uca |
| 79 | Not ayraçla bitmek zorunda değil | birim |
| 79 | Genel kapsam her eşiği alıyor | statik + uçtan uca |
| 79 | Genel kapsam başvuruyu da atıyor | statik + uçtan uca |
| 79 | Plansız beyan kapsam değil | statik |
| 79 | İstek ucu yuvayı atıyor | statik + uçtan uca |
| 79 | Harita öğesi yuvasız | statik + uçtan uca |
| 79 | Kalma girdisi yuvasız | statik |

## 4. Gezintide görülüp hata sayılmayanlar

* **END 4901E (Tasarım I) programda yok:** "Bitirme çalışması: 79/95 kredi —
  16 kredi eksik" — kredi eşiği kuralı, darboğazda yazıyor.
* **END 4902E'nin önşartı "END 4901"** (dil eşi olmayan eski kod) planda yok →
  "önşart varsayıldı". `fikirler.md` §1.1'deki kod göçü kalemi.
* **Önerilen programda beş dolu şube:** hepsi tek şubeli ya da uyan boş şubesi
  olmayan dersler; özet ve danışman özeti bunu zaten söylüyor.
