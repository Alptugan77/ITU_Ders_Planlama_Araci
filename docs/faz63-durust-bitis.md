# Faz 63 — Yol haritası bilmediği bitişi göstermiyor

*24.09.2026 · kullanıcı: "continue on your improvements and additions".*

Faz 62'de site gerçek katalogla ayağa kalkınca ilk kez **127 anadal
programının hepsi** kuruldu (her biri boş bir öğrenciyle, gerçek katalog,
`snapshot()`): 0 çökme, ortanca 0.7 sn. Hata yoktu ama iki yerde harita
**bilmediği bir şeyi bilir gibi** yazıyordu — aracın temel kuralı
("bilinmeyen, bilinen gibi gösterilmez") çiğneniyordu.

Testler **1294 → 1300** (+6, `tests/test_faz63_durust_bitis.py`), 4 atlandı. Geri alma deneyi:
altı kuralın **altısı** geri konunca kendi sebebiyle kırmızı (§3).

---

## 1. ★★ Transkript girilmemişken bitiş tahmini yok

Taramada öğrenci 5. yarıyılda, transkript boş. Harita planın **tamamını**
kalan sayıyordu: "13. yarıyılda bitersin, azami süreyi aşıyorsun —
danışmanınla konuş". Sitede ilk açılışta dönemini söyleyip dersleri henüz
girmemiş herkesin gördüğü şey buydu — yanlış ve korkutucu. İlerleme
panelleri bunu Faz 26'da düzeltmişti ("İlerleme bilinmiyor"); harita
düzeltilmemişti.

Kural (`ui._transkript_eksik`): **2+. yarıyılda ve geçilmiş tek ders yok**
→ harita kurulmuyor. 1. yarıyılda boş transkript doğru (harita kuruluyor);
dönem bilinmiyorsa eski davranış. FF/VF gibi geçmeyen notlar "girilmiş"
saymıyor.

* **Yol haritası:** "Bitiş tahmini yapılamıyor — 5. yarıyılda olduğunu
  söyledin ama geçtiğin dersleri girmedin; harita planın tamamını kalan
  sayardı…" + **Dersleri gir** (kurulum penceresini açıyor).
* **İstek üzerine kurulanlar** (senaryo `/api/yolharitasi`, ÇAP seçenekleri
  `/api/capbitis`) AYNI kuralı ortak girdiden (`_harita_girdisi`) alıyor ve
  400 veriyor; başvuru penceresinde "tahmini bitiş" sütunu çıkmıyor.
* **Danışman özeti:** "Tahmini bitiş" bölümü yok; soru olarak *"Geçtiğim
  dersleri araca girmedim — mezuniyet planımı birlikte gözden geçirebilir
  miyiz?"*

## 2. ★★ Ortak lisans (UOLP) programlarında bitiş yok

Gerçek katalogda **20 UOLP programı** var ("Bilgisayar Mühendisliği
(İngilizce) UOLP (Saraybosna-IUS)", SUNY, NJIT, Strathclyde…). Planları
YALNIZ İTÜ'de alınan dersleri içeriyor: BES 3.–6., CES/EHS/MSS 5.–8.
yarıyıl, SUNY programları 1.–6. Ortak üniversitedeki dönemler veride yok.
Harita son İTÜ dersini **mezuniyet** gibi yazıyordu (SIN, 5. yarıyılda:
"2026-2027 Bahar"), öteki dönemleri İTÜ dönemi sayıp azami süreye
de vuruyordu.

`yolharitasi.ortak_program()` programın OBS adından ortak üniversiteyi
okuyor (başka işaret yok). UOLP programında:

* `finish`, `nominal`, `finishSemester` **yok**; `jointDegree` = ortak
  üniversite. Dersler yine yerleşiyor (önşart sırası işe yarıyor).
* Kart: **"tahmin edilmedi"** + "ortak program (UOLP · Saraybosna-IUS) —
  ortak üniversitedeki dönemler veride yok; sıralama yalnız İTÜ dersleri
  için". Varsayım kutusunda ⚠ satırı.
* Danışman özeti: bitiş "tahmin edilmedi — ortak program (…)"; soru:
  *"Ortak programdayım (…) — kalan yarıyıllarımdan hangileri İTÜ'de,
  hangileri ortak üniversitede? Mezuniyet dönemim ne olur?"*

Tarama (1. yarıyıl, boş transkript) sonrası: 20 UOLP programının 20'si
işaretli, başka hiçbir programın bitişi kaybolmadı.

**BES'in boş programı** (taramada 0 ders) hata değil: BES'in İTÜ planı 3.
yarıyılda başlıyor ve 1. yarıyıl İTÜ dersleri bu dönem açılmıyor —
öğrenci o dönem ortak üniversitede.

## 3. Geri alma deneyi

| Geri konan | Kırmızı |
|---|---|
| Sayfadaki harita transkriptsiz kuruluyor | statik + uçtan uca |
| İstek ucu (senaryo/ÇAP) transkriptsiz kuruluyor | statik + uçtan uca (400 yok) |
| Geçmeyen not (FF, VF) "girilmiş" sayılıyor | birim |
| Arayüzde transkriptsiz dal yok | statik + uçtan uca |
| UOLP işaretlenmiyor | birim |
| UOLP'de yarıyıl numarası yazılıyor | birim |

## 4. Ne yapılmadı

* UOLP'nin **hangi yarıyılının İTÜ'de** olduğu: programdan programa değişiyor
  (2+2, 1+1+1+1, Saraybosna'da ilk dört yarıyıl) ve bu veride yok. Bilinse
  ortak üniversite dönemleri "boş dönem" (Faz 61) olarak haritaya
  girebilirdi — kaynağı bulunursa küçük bir iş.
