# Faz 29 — Penetrasyon testi

*27.08.2026 · kullanıcı isteği: "penetrasyon testi yapar mısın"*

Bu araç bir öğrencinin **notlarını** işliyor ve yerelde bir HTTP sunucusu
açıyor. İkisi de gerçek saldırı yüzeyi. Bu belge, savunmayı okumak yerine
**kırmayı denemenin** sonucu — sunucuyu ayağa kaldırıp dışarıdan, kötü niyetli
bir sekmenin ya da yerel bir sürecin atacağı ham istekleri attım.

## Yöntem

`tests/test_guvenlik.py` bir sunucu başlatıp saldırıyor; ayrıca gerçek bir
tarayıcıda (Playwright) enjekte edilen script'in çalışıp çalışmadığını
ölçüyor. **Metin araması değil, davranış ölçümü** — çünkü "sayfada `<script>`
görünüyor" ile "script çalışıyor" ayrı şeyler.

## 🔴 Bulunan: gömülü JSON'dan XSS — DOĞRULANDI, TARAYICIDA ÇALIŞTI

Sayfa, tüm veriyi tek satırda gömüyor:

```html
<script>const DATA = {…};</script>
```

`{…}` kısmı `json.dumps(data)` ile üretiliyor. **`json.dumps`, `</script>`
dizisini kaçırmıyor** — `/` olduğu gibi kalıyor. Yani DATA içindeki bir
string `</script>` taşırsa tarayıcı script'i **erken kapatıyor** ve kalanı
HTML olarak işliyor.

Kanıt: meşgul saat etiketine (kullanıcının yazdığı serbest metin,
`settings.toml`'a yazılıyor ve sayfada yansıtılıyor)

```
</script><script>window.__XSS__=document.domain</script>
```

konup sayfa açıldığında **enjekte script gerçekten çalıştı** ve
`document.domain`'i okudu. `window.__XSS__` doldu.

### Tehdit yüzeyi — dürüst değerlendirme

Bugün dar:

* Yerelde çoğunlukla kişi **kendine** enjekte ediyor (kendi etiketini yazıyor).
* Paylaşım bağlantısı (`#crn=…`) yalnız `[\d,]+` kabul ediyor — serbest metin
  oradan giremiyor. Kontrol edildi, güvenli.
* Yayınlanan statik sitede DATA çalışma anında `JSON.parse` ile geliyor,
  script kaynağına gömülmüyor — o yol bu kaçıştan etkilenmiyor.

Ama kapatılması şart:

* `settings.toml` **paylaşılabilir / içe aktarılabilir** bir dosya.
* Yarın serbest metin taşıyan bir içe aktarma (transkript paylaşımı, ayar
  içe alma) eklense **anında** sömürülür.
* Gömülü JSON'dan script kaçışı tek başına bir kusur — "şu an ulaşılmıyor"
  bir savunma değil, bir erteleme.

### Düzeltme

`ui._gomulu_json`: JSON'u gömmeden önce `<`, `>`, `&`, U+2028, U+2029 →
`\uXXXX`. Bu karakterler JSON'da **yalnız string değerlerinin içinde**
geçebilir (yapısal sözdiziminde asla), o yüzden `\u` kaçışı `JSON.parse`'ın
verdiği değeri **değiştirmiyor** — kayıpsız. Standart, bilinen çözüm.

Playwright testi düzeltmeden sonra `window.__XSS__`'in **boş** kaldığını
doğruluyor; ve gerileme testi bunu kalıcı kılıyor.

## 🟢 Dayanan saldırılar (28 deneme)

| Saldırı | Sonuç |
|---|---|
| Jetonsuz yazma (POST) | 403 |
| CSRF: kötü `Origin` + geçerli jeton | 403 |
| Uzunluğu eşit yanlış jeton | 403 (zamanlama-güvenli) |
| Durum değiştiren GET | yok — GET yan etkisiz |
| DNS-rebinding: sahte `Host` | 403 (jeton yeter) |
| Yol geçişi: `restore('../../etc/passwd')` ve 3 varyant | 400 |
| Transkriptten `<script>` | `esc()` ile kaçtı |
| Bozuk JSON gövdesi | 400, iz yok |
| Negatif/devasa `maxLoad`, `dönem`, `gün` | 400, üç değerli aralık |
| 20 MB gövde | reddedildi, sunucu ayakta |
| Güvenlik başlıkları (nosniff, DENY, no-referrer, no-store) | hepsi var |
| **TOML anahtar enjeksiyonu** (etiketle) | round-trip doğrulaması reddetti |
| Prototip kirlenmesi (`__proto__`) | zararsız, 200 |

## 🟡 Sertleştirme: TOML yazıcı kendi başına güvenli

Meşgul etiketi enjeksiyonu **dayandı** ama sebebi `_toml_value` değildi:
`save_busy`, ürettiği satırı `parse_busy` ile geri okuyup doğruluyor
(satır sonu içeren etiket regex'e uymuyor → reddediliyor). Yani koruma
**round-trip doğrulamasında**, yazıcıda değil.

`_toml_value` yalnız `\` ve `"` kaçıyordu; bir satır sonu geçseydi

```
mesgul = ["x"
max_load = 9999"]
```

gibi **geçerli ama başka anahtar taşıyan** bir TOML üretirdi. Bugün buraya
serbest metin round-trip'ten geçmeden ulaşamıyor — ama yazıcının **kendi
başına** güvenli olması gerekir. "Çağıran zaten temizliyor" sessiz bir
varsayım ve yeni bir alan eklendiğinde çöker. Bu, projedeki *"yazıcı
okuyamayacağı şeyi üretmesin"* ilkesinin ta kendisi.

Sertleştirildi: `_toml_value` artık satır sonu, tab ve tüm kontrol
karakterlerini (`U+0000–U+001F`) kaçıyor. Değer kayıpsız korunuyor.

## Sayılar

| | |
|---|---|
| Toplam saldırı denemesi | 28 |
| Açık (düzeltildi) | 1 |
| Sertleştirme | 1 |
| Yeni güvenlik gerileme testi | 7 |
| Test | **911** |

## Kapsam dışı — bilerek

* **Yayınlanan sitenin sunucusu yok.** Denetlenecek bir uç yok; saldırı
  yüzeyi tarayıcıdaki kendi verisi. Yeni XSS düzeltmesi orada da geçerli
  (aynı `render`), ama oradaki DATA zaten `JSON.parse` yolundan geliyor.
* **OBS tarafı test edilmedi.** Araç OBS'ye yazmıyor, şifre istemiyor; tek
  yönlü okuma ve o da kullanıcının kendi makinesinde.
* **Ağ/taşıma katmanı** (TLS vb.) — sunucu yalnız `127.0.0.1`'e bağlanıyor,
  ağa hiç çıkmıyor. Tehdit modeli "aynı makinedeki başka sekme/süreç", ve
  jeton + Origin denetimi tam olarak onu karşılıyor.
