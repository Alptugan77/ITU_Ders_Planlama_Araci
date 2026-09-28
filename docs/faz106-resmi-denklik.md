# Faz 106 — Resmî denklikler yayınlanan kataloğa girmiyordu

Kullanıcı 27.09.2026: *"akts veya kredi farklıysa denklik olmuyor diye
biliyorum ama itü denklikleri yayınlıyor zaten
https://obs.itu.edu.tr/public/GenelTanimlamalar/DersPlanDenklikleri"*.

## Bulgu

* Kazıyıcı vardı (`sources/obs_equivalence.py`, `step_equivalence`), ama adım
  **isteğe bağlıydı** (`--all-equivalences` ya da `eq_all_programs`).
* Yayınlanan katalog (`make all-plans`) onsuz kurulmuştu: `equivalence`
  tablosu **tamamen boş** (0 satır).
* Faz 104–105'te elle beyan edilen 21 kod göçünün hiçbiri resmî tabloyla
  karşılaştırılamadı. Bekleyen 5 aday da öyle.
* **Kullanıcının kuralı:** AKTS ya da kredi farklıysa denklik olmaz. Faz
  105'te AKTS'si farklı 5 aday zaten beyan edilmemişti; bu kural onu doğruluyor.

## Değişiklik

* **`make all-plans` → `refresh --all-programs --all-equivalences`:**
  yayınlanan katalog artık resmî denklikleri de içerecek.
* **Kalite raporu:** `official_equivalence_empty` uyarısı. Resmî denklik
  yoksa `make refresh` bunu söylüyor, sessiz kalmıyor.
* **Yol haritası:** önşartta resmî denklikler de sayılıyor
  (`expand_with_equivalences`); öneri motoru (`candidates`, `cap_blockers`)
  zaten sayıyordu. Eskiden denklikle karşılanan ders plan slotunu
  dolduruyor ama onu isteyen dersin önşartını açmıyordu; eski kod "dış
  önşart" sayılıp **varsayılıyordu**.
* **`tools/kod_gocu_taramasi.py`** resmî denklikleri de sayıyor. Katalog
  denkliklerle kurulduğunda, kalan engeller OBS'nin kendi denkliğiyle de
  açılmayanlar olacak.

## Bekleyen

Bu oturumun bulut ortamı `obs.itu.edu.tr`'ye erişemiyor (ağ politikası), bu
yüzden denklikler burada çekilemedi. `make all-plans` erişimi olan bir
makinede çalıştırılınca:

1. `python tools/kod_gocu_taramasi.py` çalıştır. Araç kalan engelleri ölçüyor
   ve (Faz 107) her `[[kod_gocu]]` beyanını resmî tabloyla karşılaştırıyor:
   "N resmî listede var, M YOK". Karşılığı olmayan her beyan ⚠ ile listeleniyor.
2. Resmî denkliği olan beyan gereksizleşir ama zararsızdır. Karşılığı olmayan
   beyan yeniden değerlendirilmeli. Karşılaştırmada yalnız tek kaynaklı
   denklik sayılıyor; "A + B → C" bir kod göçü değil.

## Doğrulama

`tests/test_faz106_resmi_denklik.py` (4 test): kalite uyarısı, Makefile
hedefi, aracın denkliği sayması, yol haritasında denkliğin varsayım değil
karşılama olarak sayılması. Dört mutasyonun dördü de kırmızı. İlk turda yol
haritası mutasyonu yeşil kalmıştı: ders "dış önşart varsayımıyla" yine
yerleşiyordu. Test artık varsayım yapılmadığını da sınıyor.
