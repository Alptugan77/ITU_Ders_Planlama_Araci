# Faz 35 — Arayüz cilası (tema, yükleme, mobil diyagram, genişlik)

*28.08.2026 · kullanıcı isteği: "temayı da kaydedip bir sonraki açılışta ona
göre açılsın ve yüklenme ekranını düzelt, telefonda çap önşart diyagramı tek
bir çizgi ile bağlanıyormuş gibi gözüküyor alt alta olduğu için ve
bilgisayardan girişlerde yanlarda çok boşluk var biraz azaltılabilir"*

## 1. Tema kalıcı

Tema düğmesi seçimi artık `localStorage`a (`itucap.tema`) yazıyor; sonraki
açılışta o tema açılıyor. **Boyamadan önce** uygulansın diye `<head>`e küçük bir
betik kondu — yoksa sayfa (yükleme ekranı dâhil) önce sistem temasında çizilip
kullanıcının seçtiğine ATLIYOR, göz kırpması oluyordu. `try/catch`: localStorage
gizli sekmede/engelliyse sessizce sistem temasına düşer.

## 2. Yükleme ekranı

Statik sitedeki (Pyodide açılırken görünen) ekran hâlâ **eski markayı**
gösteriyordu: "İTÜ ÇAP · YANDAL / Ders planlama". Artık ad TEK KAYNAKTAN
(`ui.AD_*`) türetiliyor — uygulama başlığıyla birebir: **İTÜ DEPAR** + vurgulu
açılım (**De**rs **P**lanlama **Ar**acı). Ad değişince burası da değişecek
(`site_kur._loader_html(UI)`), elle güncelleme gerekmiyor. Tema betiğiyle
birlikte ekran doğru temada açılıyor.

## 3. Telefonda önşart diyagramı — "tek çizgi" düzeltildi

Mobilde kutular tek sütunda alt alta gelince bütün önşart çizgileri aynı x'te
üst üste biniyor, diyagram düz bir zincir ("tek çizgi") gibi görünüp
**dallanmayı gizliyordu**. Çözüm: dikey bağlar kutunun **sağ kenarından** çıkıp
sağdaki **oluğa** kavisleniyor (kutu içeriğini, kredi sayısını kesmeden).
Kavis dikey mesafeyle büyüdüğü için **kademe atlayan** bağ aradaki kutuların
etrafından geniş bir yayla dolaşıp komşu bağlardan ayrışıyor — dallanma
görünür oluyor. Masaüstünde kutular yatay yayıldığından bu dal çalışmıyor,
oradaki eğri zaten ayrık (`|Δx| < 24` koşulu).

## 4. Masaüstünde kenar boşluğu

İçerik genişliği `1180px` → **`1340px`** (yan pay 32→30). 1680px ekranda her
yanda boşluk ~250px'ten ~170px'e indi; okunabilirliği bozacak kadar
genişletilmedi.

## 5. "Kaydediliyor" belli olsun

*"kaydete basılınca yükleniyor olduğu belli olsun"* — Kaydet düğmesi eskiden
yalnız soluklaşıyordu (metni "Kaydet" kalıyordu) ve altta küçük bir
"kaydediliyor…" satırı vardı; ÇAP+yandal birlikte kaydı 7 sn sürünce kullanıcı
takıldı sanıyordu. Artık **dönen bir halka + "Kaydediliyor…"** düğmenin
üstünde. `dugmeMesgul(btn, metin)` yardımcısı düğmeyi kilitliyor, halkayı
koyuyor, geri döndüren işlev veriyor. **Bütün kayıtlar** `save()`ten geçtiği
için tek yerde çözüldü (program, dönem, transkript, tercih, meşgul); ayrıca
"Programı kaydet" ve "Veriyi tazele" (1–2 dk) de aynı halkayı kullanıyor.
`aria-hidden` + `prefers-reduced-motion` (hareket duyarlılığında dönmüyor).

### 5b. Meşgul göstergesinin iki hatası (31.08.2026 raporu)

Kullanıcı iki şey bildirdi, ikisi de düzeldi:

1. **"Basınca başladığı belli olmuyor" (program/dönem).** Halka `innerHTML` ile
   konuyordu ama hemen ardından **statik sitede Pyodide hesabı ana iş
   parçacığını BLOKLUYOR** — tarayıcı halkayı boyayamadan 7 sn donuyor, sonra
   bitmiş oluyordu. `bekleBoyansin()` (iki `requestAnimationFrame`) ile halka
   önce **boyanıyor**, sonra bloklayan işe giriliyor. `save()`, "Programı
   kaydet" ve "Veriyi tazele" bunu kullanıyor. (Yerel `fetch` sürümünde bir
   karelik gecikme fark etmez.)

2. **Kaydettikten sonra başka programa/kipe geçince düğme "Kaydediliyor…"
   kilitli takılıyordu ve yeni programı KAYDETTİRMİYORDU.** `#savePicks` KALICI
   bir eleman; `dugmeMesgul` onu meşgul (kilitli) bırakıyor, `renderSaveState()`
   ise yalnız `hidden`'ı değiştiriyordu — meşgul hâli hiç sıfırlanmıyordu.
   Artık her çizimde düğme temizleniyor (kilit açık, metin "Programı kaydet"),
   böylece kaydedip geçince yeni ders programı da kaydedilebiliyor.

## Sayılar

| | |
|---|---|
| Test | **950** (+2: kaydet meşgul göstergesi + boyanma/sıfırlama) |
| Değişen | `ui.py` (tema betiği + kayıt, `.wrap`, tier kavis, `.spin`/`dugmeMesgul`), `site_kur.py` (yükleme ekranı) |
| Doğrulama | tema kalıcı; mobil tier oluk yayları; yükleme ekranı; 1680px genişlik; meşgul halka tarayıcıda (meşgul→geri) |
