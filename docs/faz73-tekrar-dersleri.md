# Faz 73 — Başarısız olunan ders programda yoksa nedeni

*24.09.2026 · kullanıcı: "continue and create a pr" (öncesinde: "make the site
more usefull and add new features and improve the site overall").*

Testler **1336 → 1339** (+3, `tests/test_faz73_tekrar_dersleri.py`), 4 atlandı.
Geri alma deneyi: dokuz kuralın **dokuzu** geri konunca kırmızı (§3).

## 1. Neden

Faz 72 gezintisinde MAT 104E'den FF alan yandal öğrencisinin önerilen
programında MAT 104E yoktu. Neden bilinçliydi — 11 şubenin hepsi yandalın tek
şubeli, kritik yoldaki iki dersiyle çakışıyordu — ama **hiçbir yer bunu
söylemiyordu**. Öğrenci ızgaraya bakıp şubeleri tek tek karşılaştırmak
zorundaydı; tekrar edilmesi gereken bir dersin sessizce dışarıda kalması,
kayıt gününden sonra fark edilirse bir dönem kaybettirir.

## 2. Ne var

Haftalık programın özetinde, "dolu şube" satırlarının altında **"Tekrar
alınması gereken ders(ler) programda değil"**. Transkriptte başarısız
(`FAILED` — FF, VF; `earned_course` dersin SON durumunu tuttuğu için sonradan
geçilmiş ders buraya girmiyor) ve programda olmayan her ders için:

| Durum | Yazılan | Düğme |
|---|---|---|
| Aday değil, darboğazda gerekçesi var | gerekçe ("bu dönem şube açılmamıştır", programa kapalı, önşart…) | — |
| Aday değil, gerekçe yok | *yazılmıyor* — planlarda kalan bir ders değil (ör. seçmeli havuzdan bırakılmış) | — |
| Bütün şubeler **ilan edilmiş** kontenjanla dolu | "bütün şubeleri doludur; kontenjanın izlenmesi önerilir" | — |
| Açık şubeler yalnız meşgul saatlerle çakışıyor | öyle yazıyor | — |
| Uyan şube var | "CRN … programla çakışmamaktadır" | **programa ekle** |
| Programdaki derslerle çakışıyor | çakışan dersler adıyla | **ekle, X çıkar** — en az krediyi düşüren şube |

Tek dokunuşun **yan etkisi önceden** yazılıyor: dönem sınırı aşılıyorsa
("eklenirse dönem yükü 24 / 20 ile sınırı aşar") ve çıkan ders ikinci
programın dersiyse ve yarıyıl tabanı bozuluyorsa ("ÇAP yarıyıl tabanı (9
kredi) sağlanamaz"). Ekleme `choose()` ile yapılıyor — ızgaradaki değişiklikle
aynı yol, geri alınabilir.

Vitrin öğrencisi (MAT 210E FF): *"MAT 210E · ekle, BLG 252E çıkar — şubeleri
programdaki BLG 252E ile çakışmaktadır; ÇAP yarıyıl tabanı (9 kredi)
sağlanamaz"*. BLG 252E çıkarılınca satır "programa ekle"ye dönüyor, eklenince
kayboluyor.

Kontenjanı **ilan edilmemiş** şube "dolu" sayılmıyor (uydurma olurdu); ekleme
düğmesi ise boş yeri bilinen şubeyi tercih ediyor.

**Danışman özeti:** uyan şubesi olmayan başarısız ders için soru —
*"Başarısız olduğum MAT 210E (FF) bu dönem programımda yer almamaktadır
(şubeleri programımdaki derslerle çakışmaktadır). Bu dersi ne zaman tekrar
almalıyım?"* Uyan şubesi olan ders soru değil; tek dokunuşla çözülüyor.

## 3. Geri alma deneyi

| Geri konan | Kırmızı |
|---|---|
| Özet çizilmiyor | statik + uçtan uca |
| Düğme bağlı değil | statik + uçtan uca |
| İlansız kontenjan "dolu" sayılıyor | statik + uçtan uca |
| Meşgul saatlere bakılmıyor | statik + uçtan uca |
| Gerekçesiz (planda olmayan) ders de yazılıyor | statik + uçtan uca |
| Çakışmada en az kredi değil en çok kredi düşüren şube | uçtan uca |
| Yarıyıl tabanı uyarısı yok | uçtan uca |
| Dönem sınırı uyarısı yok | statik + uçtan uca |
| Danışman sorusu yok | uçtan uca |

İlk denemede "en az kredi" kuralı geri konunca test **yeşil** kaldı: vitrinde
yalnız bir çakışan şube var. Sayfa içinde iki şube kuruldu (biri iki dersle,
biri tek dersle çakışan; kötüsü listede önde) — artık kırmızı.

## 4. Ne yapılmadı

* **Yönetmelikteki "başarısız dersi ilk açıldığı dönemde alma" önceliği.**
  Böyle bir kural varsa motorun puanlamasını değiştirmeli; kaynağı teyit
  edilmediği için `kurallar.toml`'a yazılmadı, araç yalnızca durumu gösteriyor.
* **Şartlı geçer (DC/DD) notların tekrarı:** GNO 2.00'ın altındayken
  danışman sorusu zaten var (Faz 61); ayrı bir satır açılmadı.
