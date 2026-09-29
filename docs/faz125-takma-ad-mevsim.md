# Faz 125 — ÇAP dersinin açıldığı yarıyıl takma adıyla da aranıyor

Kullanıcının verisiyle yapılan inceleme (29.09.2026; HTAE anadal, BLG ÇAP).

## Bulgu

Yol haritası, ÇAP/yandal dersinin açıldığı yarıyılı ilgili bölümün **lisans
planından** okuyor. BLG ÇAP planı dersleri eski kodlarıyla yazıyor
(BLG 317E, BLG 311E, BLG 335E …), BLG'nin güncel lisans planı ise yeni
kodlarıyla (BBF 302E, BBF 301E …). Doğrudan eşleşme bulunamayınca:

* 7 dersin yarıyılı geçmiş not dağılımından tahmin ediliyordu;
* 3 dersin yarıyılı hiç bilinmiyordu ve harita bunların "her dönem
  açılacağını" varsayıyordu. Örneğin BLG 311E aslında Bahar dersi.

## Değişiklik

Doğrudan eşleşme yoksa yarıyıl, dersin takma adlarıyla (`rules.takma_adlar`:
resmî denklik, beyan edilmiş kod göçü, dil eşi) aranıyor. Bunlar önşart
denetiminin zaten kabul ettiği eşlerdir.

## Ölçüm

Kullanıcının verisinde geçmişten tahmin edilen ders sayısı 7'den 3'e,
yarıyılı bilinmeyen ders sayısı 3'ten 2'ye indi. BLG 311E artık planındaki
Bahar yarıyılına yerleşiyor. Bitişler değişmedi (anadal 9., ÇAP 8. yarıyıl).

Gerçek katalogda 383 anadal+ÇAP çifti (3. yarıyıl), planlanan ÇAP dersleri:

| Yarıyılın kaynağı | Önce | Sonra |
|---|---|---|
| Lisans planı | 5968 | 6579 |
| Geçmiş not dağılımı (tahmin) | 740 | 342 |
| Bilinmiyor ("her dönem") | 627 | 414 |

Bitişler çiftlerin çoğunda değişmedi. ÇAP bitişi 12 çiftte erkene, 6 çiftte
geçe kaydı; anadal bitişi 7 çiftte erkene, 6 çiftte geçe kaydı. İki yönlü
değişim beklenen bir sonuç: tahmin ya da "her dönem açılır" varsayımının
yerini plandaki gerçek yarıyıl aldı.

## Doğrulama

`tests/test_faz125_takma_ad_mevsim.py`: denklikle lisans planından okunan
yarıyıl; denklik yokken yarıyıl bilinmiyor. Mutasyon kırmızı.
