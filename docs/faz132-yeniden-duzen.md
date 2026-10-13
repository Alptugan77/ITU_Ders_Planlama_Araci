# Faz 132 — Yeniden düzen: kimlik aynı, kabuk yeni

**Tarih:** 12.10.2026
**İstek:** "redesign the ui and ux of the site"

Vitrin öğrencisiyle (`make vitrin`) her görünüm masaüstünde (1440px) ve
telefonda (390px), gece ve gündüz temasında gezildi. Görsel kimlik
(sıfır köşe, cetvel, Chivo başlık, tek aksan, Faz 56/70'in ölçülü paleti)
kullanıcının seçimi olduğu için korundu. Değişen şey **düzen ve hiyerarşi**,
özellikle her görünümde tekrar eden kabuk.

| | önce | sonra |
|---|---|---|
| masaüstünde içeriğin başladığı yer | y = 305px | y ≈ 120px |
| üst çubuk (masaüstü) | 3 satır, 125px; "tazele" kendi satırında | tek bant: ad · durum · Kılavuz/Tema |
| "Sonraki adımlar" şeridi | her görünümde, 90px, ilk iki düğmesi rayın kopyası | yalnız programda, tek satır, kopya düğme yok |
| programın sağ sütunu | 9 düğme aynı ağırlıkta alt alta (~350px) | birincil tam genişlik + "Kayıt ve paylaşım" 2 sütunlu ızgara (~250px) |
| yol haritası ayarları | cümle arasına serpilmiş, dönem düğmeleri alanların arasına kırılıyor | tek ayar panosu, sabit etiket sütunu, boş dönemler kendi satırında |
| görünüm değişimi | anlık, fark edilmiyor | 0,18 sn giriş (hareket duyarlılığında yok) |

## 1. Üst çubuk tek bant

Masaüstünde (`min-width:701px`) başlık üç sütunlu bir ızgara:
`"ad durum dugme" / "ad veri dugme"`. Durum satırı ile veri yaşı aynı
sütunda iki ince satır; ince bir hatla addan ayrılıyor. "tazele" artık
çerçeveli bir düğme değil, cümlenin devamı olan bağlantı görünümlü bir
düğme (telefonda Faz 129'un 44px hedefi korunuyor).

Telefondaki düzen (Faz 129/130) değişmedi.

## 2. "Sonraki adımlar" yalnız programda

Faz 50 telefonda bu şeridi program dışındaki görünümlerde gizlemişti;
masaüstünde "içerik zaten üstte başlıyor" diye bırakılmıştı. Ölçüldü:
masaüstünde de içeriği 90px aşağı itiyordu ve "Haftalık program" ile
"Ders ekle / değiştir" düğmeleri soldaki rayın birebir kopyasıydı. Kural
artık iki ekranda da aynı.

## 3. Sağ sütun iki grup

Birincil eylem ("Programı kaydet") 44px ve tam genişlikte; "Alternatif
olarak kaydet" onun altında. Ayraçlı bir "Kayıt ve paylaşım" başlığının
altında altı ikincil eylem iki sütunlu ızgarada: Kayıt günü ile CRN'den
yükle yan yana (ikisi de OBS kaydına dair), sonra takvim, resim, danışman
özeti, bağlantı. Faz 47'nin "dar sütun" kararı (240px) duruyor.

Özet notlarının başındaki "— " kaldırıldı: not zaten kendi satırında.

## 4. Yol haritası ayar panosu

Öncelik ve senaryo satırları `surface-2` zeminli tek bir panoda; etiket
sütunu sabit (72px), "Boş bırakılacak dönemler" kendi alt satırında.

## Ölçek

Yeni katmandaki bütün değerler v2 ölçek jetonu;
`make tasarim ARGS=--denetle` temiz. `tests/test_faz132_yeniden_duzen.py`
çıplak px/hex kullanımını da yakalıyor (kırılma noktaları ve tek bir
optik kayma hariç).
