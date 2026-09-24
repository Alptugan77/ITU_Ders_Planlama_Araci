# Faz 72 — Yandal öğrencisiyle gerçek site gezintisi

*24.09.2026 · kullanıcı: "make the site more usefull and add new features and
improve the site overall".*

Testler **1332 → 1336** (+4, `tests/test_faz72_yapistirma_ve_basvuru.py`),
4 atlandı. Geri alma deneyi: altı kuralın **altısı** geri konunca kırmızı (§4).

Önceki gezintiler ÇAP'sız (Faz 65) ve ÇAP'lı (Faz 62–63) öğrenciyle
yapılmıştı. Bu kez site gerçek katalogla kuruldu (Pyodide, `site/`) ve
**yandal** öğrencisi gibi gezildi: Makina Mühendisliği (İngilizce, MAKE) +
Ekonomi yandalı (ECN_YD), 5. yarıyıl, 21 derslik transkript (MAT 104E FF,
dört şartlı geçer not) yapıştırıldı. Her görünüm 1400 ve 390 px'te açıldı.

## 1. ★★ Yapıştırılan transkript silinebiliyordu

"Bu 21 dersi ekle" sunucuya yazıyor, pencere 550 ms sonra kapanıyordu. Ölçülen
iz (gerçek site):

| t | pencere | Kaydet | liste | GNO'ya giren ders |
|---|---|---|---|---|
| 0.25 sn | açık | meşgul | 0 | 0 |
| 1.11 sn | **açık** | **etkin** | **0** | 20 |
| 1.62 sn | kapalı | — | — | 20 |

Arada liste hâlâ "Girilmiş dersler (0)" gösteriyor ve **Kaydet** yeniden
etkin oluyordu. Kaydet, ekrandaki listeyi `replace:true` ile gönderir (çıkar
düğmesi bu sayede çalışır) — yani ESKİ, boş liste gidip yapıştırılan
transkripti **siliyordu**: gezintide GNO "bilinmemektedir"e, yol haritası
"bitiş tahmini yapılamamaktadır"a döndü. Ayrıca tek tek eklenip henüz
kaydedilmemiş dersler ve not değişiklikleri yapıştırmada pencereyle birlikte
**sessizce kayboluyordu**.

Artık (`courseDialogSetup` → `trOnizlemeCiz(p, calisma)`):

* Yapıştırmadan **önce** bekleyen düzenleme varsa (ekrandaki liste kayıtlıdan
  farklıysa) Kaydet ile aynı gövdeyle (`govde()`) kaydediliyor; sonra
  yapıştırma ekleniyor.
* Başarıdan hemen sonra — aynı görevde, bir tıklama araya giremeden — liste
  sunucudaki transkriptle yenileniyor. Pencere kapanana kadar Kaydet'e
  basılsa bile gönderilen şey TAM liste.
* `save()` başarıyı döndürüyor (`true`/`false`); öteki çağıranlar dönüşe
  bakmıyor, davranışları değişmedi.

Gerçek sitede aynı akış (yapıştır → hemen Kaydet): liste **21**, GNO 2.18
(20 ders, 53 kredi), yol haritası kuruldu.

## 2. ★ Kayıtlı olunan programın başvuru eşiği GNO panelinde

Yandala kayıtlı öğrenciye GNO paneli **"Başvuru · Yandal başvurusu ≥ 2.50 ✗"**
gösteriyordu (GNO 2.18). Öğrenci zaten yandalda; onun için geçerli olan devam
eşiği (2.00 ✓). Kırmızı ✗ yanlış bir kaygı üretiyordu.

GNO hedefi (Faz 57), not senaryosu (Faz 71) ve danışman soruları (Faz 61) bu
eşiği zaten gizliyordu — kural **dört yerde ayrı ayrı** yazılmıştı
(`!(t.kind === "basvuru" && icinde.has(t.scope))`) ve GNO paneli atlanmıştı.
Artık tek kural, `kayitliBasvuru(t)`; dördü de onu kullanıyor. GNO panelinde
gruplar, çipler ve alt not (doğrulanmamış / toleranslı / bekleyen sayısı) aynı
süzülmüş listeden sayılıyor.

Kayıtlı OLUNMAYAN programın başvurusu gösterilmeye devam ediyor (ÇAP'taki
öğrenci için yandal başvurusu hâlâ bir seçenek) — test ikisini de ölçüyor.

## 3. Not senaryosunda eşik hapları GNO paneliyle aynı

Faz 71'in eşikleri `.chip` ile çiziliyordu: BÜYÜK harf ("YANDAL'A DEVAM ≥
2.00 ✓"), hemen üstteki GNO panelinde aynı eşik küçük harfli hap. Resmî dil
kuralları (Faz 66) büyük harf yazmıyor. Artık `.cat` + `ok`/`no` — GNO
paneliyle aynı renkler. İki temada bakıldı; kontrast aracı 78 çiftin 78'ini
geçiriyor.

## 4. Geri alma deneyi

| Geri konan | Kırmızı |
|---|---|
| GNO paneli eşikleri süzmüyor | statik + uçtan uca |
| Yapıştırma sonrası liste yenilenmiyor | statik + uçtan uca |
| Bekleyen düzenleme yapıştırmadan önce kaydedilmiyor | uçtan uca |
| `save()` başarıyı döndürmüyor | statik + uçtan uca |
| Kural kapsama bakmıyor (hiçbir başvuru gizlenmiyor) | statik + uçtan uca |
| Kural kapsama bakmıyor (her başvuru gizleniyor) | statik + uçtan uca |

Uçtan uca test yarışı zamanlamaya bırakmıyor: sayfa içinde "Bu dersi ekle"ye
basıp Kaydet yeniden etkin olur olmaz (10 ms yoklama) listeyi okuyor ve
Kaydet'e basıyor.

## 5. Gezintide görülüp hata sayılmayanlar

* **MAT 104E (FF) önerilen programda yok.** 11 şubesinin hepsi yandalın tek
  şubeli, kritik yoldaki iki dersiyle (ECN 201E Perşembe, ECN 202E Çarşamba
  08:30) çakışıyor; MAT 104E her dönem açılıyor ("ertelenebilir"). Tercih
  bilinçli. Aday listesinde ders ve gerekçesi görünüyor.
* **MAKE'nin planı 2011-2012 tarihli**, 5. yarıyıl derslerinin bir kısmı bu
  dönem açılmamış ya da başka programlara ayrılmış. Veri (OBS/İTÜ Helper)
  böyle; araç bunu "bu dönem şube açılmamıştır" diye söylüyor.
* **MAK 200E'nin kredisi katalogda yok** — "Kredisi bilinmeyen 1 ders
  ortalamaya katılmadı" yazıyor (uydurma yok).
