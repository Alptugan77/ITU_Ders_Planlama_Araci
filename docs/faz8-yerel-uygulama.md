# Faz 8 — Yerel uygulama: arayüz artık yazıyor

> ⚠️ Bu belgedeki bütün sayılar **örnektir**. Depoda kimsenin gerçek notu
> ya da ortalaması yer almaz — kişisel veri `data/` altında kalır ve
> `.gitignore` ile dışarıda tutulur.


```bash
make app                      # ▶ http://127.0.0.1:8770
make app ARGS="--port 9000 --no-browser"
```

## ★ Sorun: en çok yapılan iş, en zor iş oluyordu

Faz 7'nin sonunda araç şunu yapabiliyordu: haftalık programı tıklayarak
düzenle, kredi eşiğini gör, kipler arasında geç. Yapamadığı şey daha temeldi —
**kendi verisini değiştirmek**:

| İşlem | Faz 7'de nasıl yapılıyordu |
|---|---|
| Geçilen ders eklemek | `transkript.txt` düzenle → `make transcript FILE=…` |
| Program değiştirmek | `config/settings.toml` düzenle → `make refresh` |
| Dönem değiştirmek | `config/settings.toml` düzenle |

Üçü de metin dosyası düzenlemek demekti. Bir ders eklemek için terminal açmak
gerekiyorsa araç "kullanışlı" değil.

## Karar: iki biçim, tek sayfa

Statik HTML dosyası **yazamaz** — disk erişimi yok. Üç seçenek vardı:

1. `localStorage`'a yaz — `file://` kaynağında tarayıcıya göre çalışır ya da
   çalışmaz, Safari engelliyor. Verinin bir kopyası SQLite'ta, bir kopyası
   tarayıcıda olurdu.
2. Formun ürettiği metni kullanıcı kendi dosyasına yapıştırsın — hâlâ dosya
   düzenlemek.
3. **Küçük bir yerel sunucu.** Sayfa aynı, arkasında yazma uçları var.

Üçüncüsü seçildi ama **ikinci biçim korundu**:

| | `make app` | `make ui` |
|---|---|---|
| Haftalık programı düzenle | ✅ | ✅ (sayfa kapanınca kaybolur) |
| Program / dönem / geçilen ders | ✅ kalıcı | salt okunur |
| Sunucu | evet | hayır — çift tıkla aç |

Statik sayfada düzenleme düğmeleri **görünür ama kapalı**, yanında
`make app` yazıyor. Kaydetmeyecek bir "Kaydet" düğmesi göstermek,
kaydetmediğini gizlemek olurdu.

Bağımlılık eklenmedi: `http.server`, stdlib. Bu bir web servisi değil,
**kendi makinende çalışan bir form**.

## Güvenlik — "yerel" demek "açık" demek değil

Tarayıcıdaki *herhangi* bir sekme `http://127.0.0.1:8770`'e istek atabilir.
Üç kat var:

1. **Yalnız `127.0.0.1`.** `0.0.0.0` değil — ağdaki başka makine erişemez.
2. **Her çalıştırmada yeni jeton.** `secrets.token_urlsafe(24)` üretiliyor,
   sayfaya gömülüyor, her yazma isteğinde `X-Itucap-Token` başlığında
   bekleniyor, `compare_digest` ile karşılaştırılıyor. Jetonu bilmeyen sekme
   yazamaz.
3. **Origin denetimi.** Başka bir sitenin sayfasından gelen istek reddediliyor.

Ayrıca: `Cache-Control: no-store`, `X-Frame-Options: DENY`,
`Referrer-Policy: no-referrer` — kişisel veri ara belleklenmesin, gömülmesin,
sızmasın. İstek günlüğü **kapalı**; `BaseHTTPRequestHandler` varsayılanı ders
kodlarını terminale basardı.

Yazma uçlarının aldığı her alan doğrulanıyor: `second_kind` sabit listeden,
dönem 0–16, program kodları `[^A-Za-z0-9]` süzgecinden geçip 8 karaktere
kırpılıyor, gövde 1 MB ile sınırlı.

## ★ `settings.toml`'a yazarken yorumları koruma

Ayarları `tomllib` ile okuyup yeniden üretmek en kolay yol olurdu ve **bütün
yorumları silerdi**. O dosyadaki yorumlar bu projenin ölçüm notları:

```toml
cap_plan_id = 2229
# ★ 2229 = "TUMMUH_BLG Double Major Program After 2018-2019 / Fall Semester"
#   HTAE_LS bu planın "Associated Programs" listesinde YER ALIYOR (doğrulandı).
```

Bunu silmek, üç fazlık keşfi silmek olurdu. `config.update_settings()` satır
bazlı çalışıyor:

* yalnız **beyaz listedeki** anahtarlara dokunuyor (`_EDITABLE`) — arayüzden
  gelen rastgele bir alan yapılandırmaya sızamaz
* var olan anahtarın satırını değiştiriyor, **satır sonu yorumunu koruyarak**
* olmayan anahtarı `[student]` bloğunun sonuna ekliyor
* tırnak içindeki `#` yorum sayılmıyor (`user_agent = "a#b"` bozulmuyor)

## ★ Tek karar noktası: `student.make_entry`

Ders girişi artık iki yoldan geliyor: form ve toplu yapıştırma. İkisinin ayrı
kural yazması, **aynı girdinin nereden girildiğine göre farklı sonuç vermesi**
demek olurdu.

`parse_line` (metin) ve `save_transcript` (form) ikisi de
`student.make_entry`'ye gidiyor. Kural orada, tek yerde:

* not yazılmadı → **DD, geçti** (en kötü durum; "MIN CC"de yanlışlıkla
  "alabilirsin" denmesin)
* `--` / `?` → devam ediyor, geçilmiş sayılmaz
* tanınmayan not → devam ediyor + not düşülür

Test ikisinin aynı sonucu verdiğini kilitliyor.

## Üç panel

**Program seçimi** — anadal listesi, ikinci program türü (ÇAP / Yandal / Yok),
bölüm ve plan. Plan boş bırakılırsa en güncel OBS planı seçiliyor. Kaydedince
`settings.toml` güncelleniyor **ve öğrenci kaydı yeni planlara bağlanıyor** —
eski kayıt silinmezse ilerleme paneli kapatılmış bir programı göstermeye devam
ederdi.

**Dönem seçimi** — 1–8 ya da "otomatik". Hangisinin kullanıldığı hem şeritte
hem başlıkta yazıyor (`7. dönem (tahmin)`).

**Geçilen dersler** — arayarak ders ekle, not seç, çıkar; ya da transkripti
olduğu gibi yapıştır. Kaydetme `replace: true` ile gidiyor: ekrandaki liste
**tam liste**. "Çıkar" düğmesinin gerçekten silmesi buna bağlı.

Kaydetten sonra sayfa yenilenmiyor — sunucu yeni durumu döndürüyor, `boot()`
her şeyi yeniden çiziyor. Ders eklendiğinde kredi eşiği, ilerleme barı, öneriler
ve darboğaz aynı anda güncelleniyor.

## Bir hata: iş parçacığı

İlk çalıştırmada her istek `500` döndü. `ThreadingHTTPServer` her isteği ayrı
iş parçacığında çalıştırıyor; `sqlite3` bağlantısı varsayılan olarak yalnız
kendi parçacığında kullanılabiliyor.

Çözüm iki parçalı: `check_same_thread=False` **ve** tüm DB işinin tek bir
kilit altında olması. İlki tek başına yeterli değil — sessiz veri yarışı
üretirdi.

## Test kapsamı

222 test (Faz 8'den 27 yeni).

**Ayar yazıcısı** — yorumlar korunuyor · satır sonu yorumu korunuyor · tırnak
içindeki `#` yorum sayılmıyor · olmayan anahtar `[student]`'a ekleniyor ·
beyaz liste dışı anahtar reddediliyor · liste ve sayı gidip geliyor

**Tek karar noktası** — form ve metin aynı sonucu veriyor · notsuz giriş DD ·
devam eden ders geçilmiş sayılmıyor

**Uçlar** — `/api/state` canlı bayrağı, jeton ve kurulum verisi taşıyor ·
sayfa `no-store` ve `DENY` başlıklarıyla sunuluyor · ders araması · bilinmeyen
yol 404

**Güvenlik** — jetonsuz yazma 403 · yanlış jeton 403 · yabancı origin 403 ·
kendi origin'i 200 · 1 MB üstü gövde 400 · dönem aralığı · geçersiz program
türü/boş kod 400 · program kodları temizleniyor

**Yazma** — dönem kaydediliyor ve kip etiketi değişiyor · ders eklenince kredi
artıyor · `replace` silinen dersi gerçekten siliyor · yapıştırmada çözülemeyen
satırlar raporlanıyor · yandala geçiş rolü ve panelleri değiştiriyor · "yok"
tek programa düşürüyor · program değişince öğrenci yeniden kaydediliyor
