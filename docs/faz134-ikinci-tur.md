# Faz 134 — İkinci tur: rozet düğme değil, köşe kuralı her kutuda

**Tarih:** 13.10.2026
**İstek:** "continue improving ui/ux" (Faz 132–133'ün devamı)

Vitrin öğrencisiyle dokuz görünüm masaüstünde ve telefonda, iki temada
yeniden gezildi. Faz 133'ün yeni görsel dili oturduktan sonra göze batan
beş pürüz düzeltildi.

| | önce | sonra |
|---|---|---|
| aday satırındaki durum rozetleri | tam renkli çerçeve, 32px, düğme gibi | sönük çerçeve, basık (~22px); renk aynı |
| açıklamalı metnin noktalı alt çizgisi | özet sütununda her satırda koyu | çizgi duruyor (Faz 51), rengi sönük |
| not senaryosu seçimleri | satır genişliğinde (~340px) | içerik genişliğinde (~112px) |
| "en çok 25 kredi" | "en çok" sözcükleri eş aralıklı yazıyla | yalnız sayı eş aralıklı |
| bitirme koşulu göstergesi | diğerlerinden geniş, önceki bloğa yapışık | aynı 230px sütun, ince hatla ayrık |
| köşesiz kutular | yol haritası dönemleri, program kartları, başvuru öğeleri, kredi alanı, "izle" | `--r` / `--r-sm` |

## Rozet ve düğme

Aday listesinde satırın kendisi tıklanıyor; satırda düğme yok. Faz 133'te
düğmeler de 8px köşeli ve çerçeveli olduğu için "programda", "kritik yol",
"önşart bilgisi yok" rozetleri birer düğme gibi okunuyordu. Rozetin
çerçevesi artık kendi renginin %32'si; yazı rengi değişmediği için kontrast
ölçümü aynı.

## Köşe denetimi

`tests/test_faz134_ikinci_tur.py` her görünümde dört kenarı çerçeveli olan
ve köşesi 0 kalan kutuları sayıyor; liste boş olmalı. Tablo hücreleri ve
kademe lejantının küçük renk örnekleri bilerek dışarıda.

## Ölçüm

* `make tasarim ARGS=--denetle`: 0 bildirim.
* `python tools/kontrast_olcumu.py`: 80 çiftin hepsi tabanın üstünde.
* `python tools/ton_merdiveni.py`: tabanlar tutuyor.

Görseller: `Claude outputs/f134-*.png`.
