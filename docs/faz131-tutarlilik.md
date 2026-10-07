# Faz 131 — Üç ekran aynı soruya aynı cevabı veriyor

**Tarih:** 07.10.2026
**İstek:** "can you continue improving"

Uygulama kullanıcının verisiyle (HTAE + BLG ÇAP, 5. dönem), telefonda ve
koyu temada yeniden gezildi. "Bu dönem hangi ÇAP dersini alabilirim?"
sorusuna üç ekran üç ayrı cevap veriyordu.

| ders | Öneriler | Engeller | Kademeler (önce) | Kademeler (sonra) |
|---|---|---|---|---|
| BLG 223E | programda | — | **önce BLG 102E** (bekliyor) | alınabilir |
| BLG 212E | programda | — | alınabilir | alınabilir |
| BLG 351E | programda | — | alınabilir | alınabilir |
| BLG 102E | — | açılmamış | **alınabilir** | önşartı tamam · bu dönem açılmamış |
| BLG 202E | — | açılmamış | **alınabilir** | önşartı tamam · bu dönem açılmamış |
| BLG 311E | — | açılmamış | **alınabilir** | önşartı tamam · bu dönem açılmamış |
| BLG 322E | — | yalnız ek sınav | **alınabilir** | önşartı tamam · yalnız ek sınav açılmış |
| BLG 252E, BLG 354E | — | yalnız ek sınav | bekliyor | önşartı tamam · yalnız ek sınav açılmış |

## 1. Kademe "alınabilir" yalnız önşarta bakıyordu

`sequence.plan_sequence` READY'yi önşart ağacından çıkarıyordu; şube
açılıp açılmadığına bakmıyordu.

Arayüzde `kademeDurumu()` artık READY bir dersin arz engeline bakıyor.
"Alınamayan dersler" panelindeki ACILMAMIS, PROGRAMA_KAPALI, EK_SINAV ve
KREDI_ESIGI engelleri sayılıyor. Böyle bir engel varsa ders `READY_KAPALI`
oluyor:

- kehribar kesikli kenar çizgisi, dolgu yok;
- kartın içinde "önşartı tamam · <engelin etiketi>" yazıyor;
- efsaneye "önşartı tamam, bu dönem alınamaz" eklendi.

Etiket engel panelinin `LABELS` tablosundan geliyor; ikinci bir metin
kaynağı yok.

## 2. Kademe ve kritik yol ham notla çalışıyordu

Öneri motoru (`candidates`) ve ilerleme paneli (`slot_satisfied`) notları
resmî denkliklerle genişletiyordu; `plan_sequence` genişletmiyordu.
Kullanıcı BLG 223E'nin önşartını bir denklikle sağlıyordu. Öneri motoru
dersi programa koyuyor, kademe görünümü aynı dersi "önce BLG 102E" diye
bekliyor gösteriyordu.

`plan_sequence(…, equivalences=None)` artık denklikleri uyguluyor. Üç
çağıran da denklikleri geçiyor:

- `ui.collect` (kademeler);
- `recommend.candidates` (kritik yol ve kademe sırası);
- `progress.report` (CLI raporu).

Kullanıcının verisinde önce/sonra karşılaştırması:

- üç ders bekliyor → alınabilir: BLG 223E, BLG 252E, BLG 354E;
- aday puanları, programlar ve bitiş dönemleri birebir aynı.

## 3. Engel metni "alınabilir" diyordu, alınamazken

Faz 120'nin `ONSART` dalı ("denk ders açık ama önşartı eksik") şöyle
bitiyordu: "… resmî denkliği BBF 302E açık ve dilekçesiz alınabilir".
Eksik önşartın hemen ardından gelen "alınabilir", "şimdi alabilirim" diye
okunuyordu. Kastedilen sayılmaydı.

Yeni metin: "resmî denkliği BBF 302E açılmıştır, ancak önşartı
tamamlanmadan alınamaz (alındığında dilekçesiz BLG 317E yerine sayılır)".

## 4. Telefonda kademe kartı satırın %60'ıydı

`.tier li{width:100%}` telefon kuralı ölüydü. Kaynakta daha sonra gelen
ve aynı özgüllükte olan temel `.tier li{… width:196px}` kuralı onu
eziyordu; bu dosyadaki dördüncü "ölü kural". Kart 196 px'ti, satır
332 px; ders adları "…" ile kesiliyordu.

`.tier ul>li` ile özgüllük artırıldı. Ölçüm: 332/332 px.

## Koyu tema

Koyu temada 6 görünüm telefonda gezildi: hata yok, taşma yok. Seçili
öneri sekmesi koyu temada da okunuyor (Faz 130).

## Testler

`tests/test_faz131_kademe_tutarlilik.py` (6 test):

- denklikle sağlanan önşart (READY, yuva DONE, kademe yapısı değişmiyor);
- denklik yokken eski davranış;
- üç çağıranın denklik geçmesi;
- `kademeDurumu` node ile çalıştırılarak (arz engelleri, önşart engeli,
  DONE);
- görünüm ve efsane;
- telefon genişlik kuralı.

`tests/test_faz120_denk_engel.py`: önşart eksikken "alınabilir"
denmemesi.

Mutasyon denetimi: 5 mutantın 5'i de kırmızı.
