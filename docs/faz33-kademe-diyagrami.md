# Faz 33 — ÇAP önşart diyagramı (kademeler) tasarımı

*27.08.2026 · kullanıcı isteği: "çap önşart diyagramının tasarımını
iyileştirir misin"*

## Eski tasarımın sorunları

Diyagram doğru ama okunmuyordu. Ölçtüğüm somut sorunlar (6 kademe, 20 ders,
19 bağ olan gerçek BLG ÇAP planında):

1. **Çizgiler dinlenmede neredeyse görünmezdi.** `opacity:.55` + kenarlık
   rengiyle çizilen bağlar ancak bir derse *tıklayınca* ortaya çıkıyordu.
   Yapı — diyagramın bütün değeri — varsayılan hâlde gizliydi.
2. **Kesişen çizgiler spagetti.** Alt kademelere inen bağlar birbirini ve
   kutu kenarlarını kesince hangi çizginin nereye gittiği kayboluyordu.
3. **`dışarıdan: A, B, C…` her kutuyu şişiriyordu.** Plan dışı önşartların
   tam listesi her kutuya 2–3 satır ekliyordu; mobilde iyice.
4. **Renklerin ne demek olduğu belirsizdi.** Turuncu = "bu dönem alınabilir"
   hiçbir yerde yazmıyordu.
5. **Yön yoktu.** Hangi ders hangisinin önşartı, ancak tıklayıp zinciri
   görünce anlaşılıyordu.

## Yapılan değişiklikler

### 1. Çizgiler artık dinlenmede de okunur — ve kesişimler ayrışıyor
Kartografideki **"casing"** tekniği: her bağın altına zemin renginde kalın
bir kat (`path.casing`, genişlik 5) çiziliyor, üstüne asıl çizgi
(`path.line`, seal rengi). İki çizgi kesişince alttaki, üsttekinin kılıfıyla
"kesiliyor" gibi görünüyor — hangi çizginin devam ettiği belli oluyor. Bütün
kılıflar bütün çizgilerin *altında* (önce hepsi-kılıf, sonra hepsi-çizgi
basılıyor); yoksa sonraki kılıf önceki çizgiyi örterdi.

### 2. Üstüne gelince önizleme (yeni)
Eskiden zinciri görmek için **tıklamak** gerekiyordu. Artık bir dersin
üstüne gelince zinciri (ataları + torunları) turuncuyla beliriyor, gerisi
sönüyor; **tıklayınca kilitleniyor** (ikinci tıkta çözülür). Fareyle
gezerken bütün plan "kendi kendini anlatıyor". Dokunmatikte hover yok —
orada tıkla-kilit tek davranış olarak çalışıyor.

### 3. Plan dışı önşart: kompakt rozet, tıkla-aç
`dışarıdan: MAT 102, MAT 102E, MAT 104…` yerine artık **`+4 dış önşart`**
rozeti. Kutu kısa kalıyor ama **bilgi kaybolmuyor**: kodlar DOM'da duruyor
ve rozete basınca (ya da klavyede Enter/Space) altında açılıyor. Bunu
sadece `title` ipucuna koymadım — dokunmatikte tooltip yok; rozet açılınca
mobilde de erişilir. Rozete basmak dersi **odaklamıyor** (`stopPropagation`)
— yalnız kodları açıyor.

### 4. Durum, kenarlıkta + efsanede
Her kutunun sol kenarı durumu söylüyor: **turuncu** = bu dönem alınabilir,
**yeşil** = almışsın (üstü çizili, soluk), düz = önşartı bekliyor. Başlıkta
küçük bir **efsane** bu üç rengi ve çizgiyi açıklıyor.

### 5. Plan içi önşart: "önce **BLG 231E**"
Çizginin temsil ettiği plan-içi bağ, kutuda `⟵ …` yerine `önce **kod**`
olarak yazılı — kodlar koyu, okunur.

## Dürüstlük / erişilebilirlik

- Çizgi çizilemezse (ders o an DOM'da yoksa) bağ atlanıyor ama **metin
  duruyor**: plan içi "önce …", plan dışı rozet+liste. Bilgi çizime bağlı
  değil.
- Dış-önşart kodları yalnız tooltip'te değil — **tıkla/dokun ile açılan**
  görünür listede. Klavyeyle de açılıyor (`role=button`, `tabindex=0`,
  `aria-expanded`).
- Hover önizlemesi geçici; kilit kalıcı. Test ikisini ayırıyor: fare
  çekilince önizleme kalkar, kilit kalır.

## Sayılar

| | |
|---|---|
| Test | **933** (+1: rozet dersi kilitlemiyor) |
| Değişen dosya | `ui.py` (kademe CSS + `renderTierGroup`/`drawTierGroupLinks`/`paintTierFocus`/efsane) |
| Doğrulama | masaüstü (dinlenme + hover + kilit), rozet-açık, mobil 390px — tarayıcıda ekran görüntüsüyle |
| Çizim | 19 bağ → 19 kılıf + 19 çizgi; hover'da 12 çizgi + 11 ders yanıyor |
