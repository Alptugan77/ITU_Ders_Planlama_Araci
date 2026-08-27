# Faz 30 — Boş saate tıklama + kip adı DEPAR

*27.08.2026 · kullanıcı isteği: "x.dönem + alttan da seçilse belli bir saate
tıklayınca o saatte seçilebilecek bütün dersleri göstersin ve tüm adaylar
seçeneğinin ismi Depar olsun"*

## 1. Boş saate tıklama artık TAM havuzdan gösteriyor

Izgaradaki boş bir hücreye tıklayınca açılan pencere (`slotDialog`) zaten
vardı ama **aktif kipin** aday listesini (`M().candidates`) geziyordu.
"x.dönem + alttan" kipinde bu liste yalnız o döneme uygun derslerden
oluşuyor — yani o saatte alınabilecek bir **üst dönem** dersi listede hiç
görünmüyordu.

Artık `slotDialog` **tam havuzu** (`DATA.candidates`) geziyor. Kip yalnız
ÖNERİYİ daraltıyor; boş saate elle ders ekleme hakkını değil.

### Sessiz düşmeyi önlemek

Aktif kipin dışındaki bir ders seçilince `choose()` onu bulmalıydı; ama
`CAND` yalnız aktif kipin haritası. Eskisi olsaydı üst-dönem dersine tıklamak
**hiçbir şey yapmazdı** — bu projedeki "sessiz sıfır" hatasının tam örneği.
`candOf()` eklendi: aktif kipte yoksa tam havuza düşüyor. `choose`, `picks`
ve `sectionOf` üçü de bunu kullanıyor.

### Gizlemek yerine söylemek

Üst-dönem dersi listeden ATILMIYOR ama "üst dönem — bu kipte önerilmez" diye
**işaretleniyor** ve kip içi derslerin altında sıralanıyor. Gizlemek "bu
saatte ders yok" sanılmasına, susup eklemek de kipin sözünü bozmasına yol
açardı. Öğrenci bilerek ekliyor.

### Doğrulama

TARAYICIDA ölçüldü: 1. dönem kipindeyken (`AAA 101E` tek aday), aynı saatte
açık bir 6. dönem dersi (`ZZZ 601E`) boş saate tıklanınca "üst dönem" notuyla
listede çıkıyor. Kaynak araması bunu kanıtlayamazdı; gerçek tıklama akışı
Playwright'la koşuluyor (`test_bos_saat.py`).

## 2. "Tüm adaylar" kipi → DEPAR

Kip anahtarındaki "Tüm adaylar" etiketi artık **DEPAR** — aracın adıyla aynı,
plandaki tüm açık dersleri değerlendiren tam kip.

⚠️ Tek kaynak: etiket `AD_KISA` sabitinden geliyor (sunucu tarafı) ve şablon
fallback'inde `__AD_KISA__` yer tutucusundan. Ad değişirse kip adı da
kendiliğinden değişiyor — elle yazılsaydı aracın adı DEPAR, kipin adı eski
kalırdı (aynı soruya iki kaynak).

## Sayılar

| | |
|---|---|
| Test | **917** |
| Yeni test | 6 (biri uçtan uca tarayıcı) |
