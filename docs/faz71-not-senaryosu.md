# Faz 71 — Dönem sonu not senaryosu

*24.09.2026 · kullanıcı: "make the site more usefull and add new features and
improve the site overall".*

Testler **1326 → 1332** (+6, `tests/test_faz71_not_senaryosu.py`), 4 atlandı.
Geri alma deneyi: on kuralın **onu** geri konunca kendi sebebiyle kırmızı (§4).

## 1. Neden

GNO hedefi (Faz 57, 69) soruyu **tersinden** soruyordu: "ÇAP'a devam için bu
dönem hangi ortalama gerekir?" Öğrencinin dönem sonunda kurduğu cümle ise
ileri yönlü: *"MAT 210E'den CC, BLG 223E'den BB alırsam GNO'm, ÇAP
ortalamam ve gelecek dönem kredi sınırım ne olur?"* Bu hesap şimdiye kadar
İTÜ Helper'daki not hesaplayıcıda ya da elle yapılıyordu; tekrar alınan dersin
eski notunun düşülmesi ve ÇAP ortalamasının ayrı hesabı çoğu zaman atlanıyordu.

## 2. Ne var

**Kredi ve not** görünümünde, GNO hedefinin altında **"Dönem sonu not
senaryosu"**:

* Programdaki her kredili ders için bir **beklenen not** seçimi (AA … FF,
  artılı notlar dahil) ve "Tümüne uygula" (tek tıkla hepsine BB; "temizle").
* Sonuç anında:
  * **Dönem ortalaması** (kaç ders, kaç kredi üzerinden);
  * **GNO (tahmini)** bugünkü → senaryo;
  * **ÇAP / yandal ortalaması** bugünkü → senaryo (yalnız o programın
    dersleri);
  * **Gelecek dönem kredi sınırı (yönetmelik)** bugünkü → senaryo — MADDE 17
    bantları, `kurallar.toml`'dan;
  * **Eşikler** (ÇAP'a devam, ÇAP mezuniyeti, mezuniyet …) ✓ / ✗ — her biri
    kendi ölçüsüyle (ikinci anadal ortalaması eşiği ÇAP ortalamasına bakıyor).
* Tekrar alınan ders tabloda **"tekrar · eski FF"** diye işaretli.

Vitrin öğrencisi (GNO 2.78, ÇAP 2.75), 7 ders BB + BLG 223E AA:
`Dönem ortalaması 3.13 (8 ders, 24 kredi) · GNO 2.78 → 2.86 · ÇAP 2.75 → 3.10 ·
kredi sınırı 25 → 25 · dört eşik ✓`. Hepsi FF: `GNO 2.78 → 2.12 · sınır
25 → 22 · ÇAP eşikleri ✗, mezuniyet 2.00 ✓`.

## 3. Hesap — hangi kural nereden

| Parça | Kaynak | Neden |
|---|---|---|
| Taban (kredi, puan) | `gnoTabani` — GNO hedefiyle **aynı** | Tekrar alınan dersin eski notu düşülüyor (İTÜ'de son not geçerli). Vitrinde MAT 210E FF (3 kr): (214 + 3×2) / 77 = **2.857**; düşülmeseydi 220 / 80 = 2.75. |
| Not seçilmeyen ders | hesaba **girmiyor** | Sessizce DD ya da FF saymak uydurma olurdu; "1 ders için not seçilmediğinden hesaba katılmamıştır" yazıyor. |
| GNO | yalnız `gpa.counted` iken | Transkriptte harf notu yoksa GNO bilinmiyor; yalnız dönem ortalaması gösteriliyor. |
| Eşik karşılaştırması | iki basamağa yuvarlanmış değer | Transkript GNO'yu iki basamakta gösteriyor; 2.4999 "2.50 ✓" görünüp "✗" yazmasın. |
| Kayıtlı olunan programın **başvuru** eşiği | gösterilmiyor | ÇAP'taki öğrenciye "ÇAP başvurusu ≥ 3.00" anlamsız. |
| Kredi sınırı | `DATA.load.bands` ← `policy.load_bands()` | JS'teki kural `policy.load_limit` ile aynı (tutan bantların en yükseği); test sekiz GNO değerinde ikisini karşılaştırıyor. Yalnız kredi birimli programda. |
| Seçimler | yalnız bu tarayıcı (`itucap.notSenaryo`) | Kolaylık; hiçbir kayda, sunucuya gitmiyor. Sayfa yenilenince duruyor, "temizle" siliyor. |

Seçim değiştiğinde bölüm yeniden çiziliyor; odak **aynı seçimde** kalıyor
(klavyeyle ders ders ilerlerken kaybolmasın).

## 4. Geri alma deneyi

| Geri konan | Kırmızı |
|---|---|
| Tekrar alınan dersin eski notu düşülmüyor | statik + uçtan uca |
| Not seçilmeyen ders FF sayılıyor | uçtan uca |
| Kredi sınırı tutan bantların en düşüğü | statik + uçtan uca |
| Başvuru eşiği kayıtlı programda da gösteriliyor | statik + uçtan uca |
| İkinci anadal eşiği GNO'ya bakıyor | statik + uçtan uca |
| Seçim kaydedilmiyor | statik + uçtan uca |
| Yeniden çizimde odak kayboluyor | uçtan uca |
| Harf notu yokken GNO uyduruluyor | statik |
| Kredi birimi olmayan programda sınır yazılıyor | statik |
| Bantlar arayüze gönderilmiyor | statik + uçtan uca |

Genişlik 1400 ve 390 px'te: taşma yok, sayfa hatası yok.

## 5. Ne yapılmadı

* **Harfsiz notlar** (BL/BZ, muafiyet): seçimde yok; bu dersler GNO'ya
  girmediği için hesaba etkisi yok. Programda böyle bir ders varsa seçilmeden
  bırakılabilir — "hesaba katılmamıştır" satırı bunu söylüyor.
* **Akademik durum** (başarılı / sınamalı): İTÜ yönetmeliğindeki eşiklerin
  dönem sayısına bağlı kısmı `kurallar.toml`'da beyan edilmediği için
  yazılmadı.
