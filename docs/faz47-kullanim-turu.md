# Faz 47 — Kullanım turu: altı geri bildirim

*18.09.2026 · kullanıcı, uygulamayı kullanırken altı şey söyledi.*

Testler **1102 → 1116** (1114 geçti, 2 atlandı).

Biri **gerçek bir veri kirlenmesiydi** ve ölçümle doğrulandı; geri kalanı
Faz 46'nın kabuğunun bıraktığı pürüzler.

---

## A. ★★ Tik geri çekilince ders düşmüyordu

> *"plandan işaretle kısmında eğer tik geri çekilirse dersi alınmış olarak
> gözükmesin"*

**Ölçüldü, haklıydı.** Gerçek veriyle, tarayıcıda:

| adım | transkript satırı | `GEO 303E` içeride mi |
|---|---|---|
| başlangıç | 37 | hayır |
| tikle + Kaydet | 38 | **evet** |
| tiki geri çek + Kaydet | **38** | **evet** ← hata |

Sebep tek satırdı: pencere **yalnız tikli** dersleri gönderiyor ve
`replace: false` ile **ekliyordu**. Tik geri çekilince gönderilecek bir şey
olmuyor, dolayısıyla hiçbir şey olmuyordu. Ders transkriptte kalıyor, araç
"bunu almışsın" diyor, ilerleme yüzdesi ve önşart hesabı da onunla
çalışıyordu.

**Düzeltme:** uç artık `remove` listesi alıyor — pencerenin **gösterdiği ve
tiklenmemiş** dersler.

⚠️ `replace: true` YAPILMADI. O, elle girilmiş ve plan dışı dersleri de
silerdi; `replace: false`u oraya koyan not haklıydı. `remove` dar kapsamlı:
pencerenin görmediği hiçbir satıra dokunulmuyor (`test_remove_PENCERENIN_
GORMEDIGINE_dokunmuyor`).

⚠️ Silici yazma **yedeksiz olmaz**: `_backup` artık "bir şey silinecek mi"
sorusuna bakıyor, yalnız `replace`e değil. Silinecek yoksa yedek de
alınmıyor — yedek sayısı 12 ile sınırlı, boşuna yedek eskileri düşürürdü.

---

## B. Ölçülen yerleşim: ızgara her ekranda 660px'ti

> *"bilgisayarda yanlardaki boşlukları kaldırabilirsin biraz ders programını
> çok sıkıştırıyor"*

| ekran | ızgara (önce) | boş kenar (önce) | ızgara (sonra) | gün sütunu |
|---|---|---|---|---|
| 1440px | 660px | 50+50 | **846px** | 120 → **158px** |
| 1512px | 660px | 86+86 | **918px** | 120 → **172px** |
| 1680px | 660px | 170+170 | **1086px** | 120 → **206px** |
| 1920px | 660px | **290+290** | **1126px** | 120 → **214px** |
| 2560px | 660px | **610+610** | 1126px | 214px |

Sayfa 1340px'e kilitliydi ve ızgara `min-width:660px`e sıkışıyordu; ders
adı hücrede kesiliyordu ("Özel Ölçme Uygul…").

⚠️ **Genişleme yalnız ızgara görünümünde.** Tasarım sistemi *"sayfa en fazla
1340px"* diyor ve bu METİN için doğru — uzun satır okunmaz. O yüzden
`:root[data-gorunum="schedSection"] .wrap` genişliyor, metin ağırlıklı
görünümler (kademeler, aday tablosu, mevzuat) **1340px'te kalıyor**.
Ölçüldü: 1920px'te ızgara görünümü 1720, aday görünümü 1340.

Sağ sütun **330 → 240px**, düğmeler alt alta (kullanıcının önerdiği biçim);
kazanılan 90px doğrudan ızgaraya gitti. Lejant/ipucu katlanmış hâliyle
**ızgaranın altına** indi — anlattığı şeyin yanında, dar sütunu şişirmeden.
Ad yazısı **20 → 25px**.

---

## C. Kaydedilen programı yükleyince ekran değişmiyordu

> *"kaydettiğim programı yükle dedikten sonra otomatik haftalık programım
> kısmına yönlendirsin"*

Faz 46'nın bıraktığı pürüz: düğme `scrollIntoView` çağırıyordu ve görünüm
kipinde bu **hiçbir şey yapmıyor** — hedef bölüm kapalı. Kullanıcı "yükle"ye
basıyor, program yükleniyor ama göründüğü yer kapalı kalıyordu. Artık
`gorunumAc("schedSection", true)`.

Aynı sınıftan bir hatayı Faz 46'da da yakalamıştık (sayfa içi bölüm
bağlantıları). **Ders:** görünüm kipine geçerken "bir yere götüren" HER
çağrı yerinin gözden geçirilmesi gerekiyor; kaydırma artık taşıma değil.

---

## D. Önce dönem, sonra transkript

> *"ilk önce dönem seçtir 1.dönem olan birisinin geçtiği ders yoktur veya
> 5.dönem olan birisi geçtiği dersleri işaretlemek için otomatik tik
> attırabilir"*

Kurulum adımları **program → dönem → transkript** oldu. Sıra keyfî değil,
**bağımlılık**: dönem biliniyorsa "Plandan işaretle" penceresi geçmiş
dönemlerin zorunlularını önceden tikleyebiliyor ve iş bir dakikadan on
saniyeye iniyor. Ters sırada o öneri yapılamıyor.

Ölçüldü (gerçek katalog, GEO, dönem 5): pencere **31 dersi** önceden
işaretledi, 356 onay kutusu arasından.

### ⚠️⚠️ Öneri, iddia değil

Bu depoda kural: *bilinmeyen, bilinen gibi gösterilmez.* **"5. dönemdesin"
demek "1–4. dönemin hepsini geçtin" demek değildir** — ders bırakmış,
kalmış, yatay geçmiş olabilir. O yüzden öneri dört şeyle çevrildi:

1. Yalnız transkript **henüz boşken** yapılıyor; girdiysen dokunulmuyor.
2. Pencerenin tepesinde **sayıyla** yazıyor: *"31 ders senin için
   işaretlendi — bu bir tahmin, kayıt değil."*
3. **"hepsinin tikini kaldır"** tek tık.
4. Hiçbiri **Kaydet'e basılmadan** yazılmıyor.

1. dönemdekine hiçbir şey işaretlenmiyor ve bu **söyleniyor**: *"1.
dönemdesin — geçmiş dönemin yok, bu liste boş başlıyor."* Açıklamasız boş
liste, bu depoda hata sayılıyor.

---

## E. Testler

`tests/test_faz47_kullanim.py` (14 test): tik geri çekilince ders düşüyor ·
`remove` pencerenin görmediğine dokunmuyor · silmeden önce yedek · silecek
yoksa boşuna yedek yok · arayüz tiksizleri gönderiyor · dönem transkriptten
önce · öneri tiki iddia değil · 1. dönem hiçbir şey işaretlemiyor · ızgara
görünümü geniş / metin görünümü dar · sağ sütun dar + düğmeler alt alta ·
lejant ızgaranın altında · ad yazısı büyüdü · yükleyince görünüm değişiyor ·
uçtan uca.

Üç düzeltme geri konulup kırmızıya döndükleri görüldü: arayüzdeki `remove`,
sunucudaki `remove`, geniş ızgara görünümü.

Yeniden yazılan üç test (silinmedi, sebebi başlarında):
`test_faz26_ilk30saniye.test_her_adimin_KENDI_eylem_adi_var` ve
`test_ilk_giris.test_program_yokken_karsilama_ENGELLEYICI` (adım sırası
değişti), `test_ux_mobil.test_rozet_TEK_PARCA` (kırılgan `split(".chip{")`
nitelenmiş bir kural eklenince yanlış kuralı okuyordu — satır başına
çapalandı).
