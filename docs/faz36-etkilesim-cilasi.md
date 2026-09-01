# Faz 36 — Etkileşim cilası

*01.09.2026 · kullanıcı isteği: "can you improve the ui and the ux further"*

Araç zaten olgun (odak halkaları, kaydırma-takip/scroll-spy, gece/gündüz teması,
mobil düzen, hareket duyarlılığı, kaydetme göstergeleri hep vardı). Bu yüzden
yeniden tasarım değil, **bütünü yükselten küçük ve güvenli dokunuşlar** yapıldı;
mevcut tasarım dili (koyu zemin, Chivo büyük-harf etiketler, aksан çubukları)
korundu.

## Ne değişti

1. **Bas-hisset (`:active`).** Hiçbir düğmede tıklama anını gösteren geri
   bildirim yoktu. Artık `.ghost`, `.tab`, `.modebtn`, bölüm çubuğu ve
   eklenebilir kod rozetleri basınca 1px iniyor — "bastım mı?" belirsizliğini de
   azaltıyor. Hareket duyarlılığında (`prefers-reduced-motion`) kapalı.

2. **Öneri sekmelerinde hover.** Seçili olmayan "Öneri 1/2/3" sekmelerinin
   hiçbir hover durumu yoktu; tıklanabilir oldukları belli değildi. Artık
   üstüne gelince vurgulanıyor.

3. **Aday ders satırı tıklanabilir görünüyor.** Satıra tıklayınca ekleme
   penceresi açılıyordu ama ne imleç ne de vurgu vardı — keşfedilmiyordu. Artık
   imleç `pointer`, üstüne gelince hafif zemin. Klavye odağı (daha güçlü:
   seal-soft + çerçeve) ile karışmıyor.

4. **Büyük yüzdeye etiket.** İlerleme kartındaki büyük "%6.6" sayısının ne
   olduğu (tamamlanma) yazmıyordu. Altına küçük **"tamamlandı"** eklendi.

## Sayılar

| | |
|---|---|
| Test | **951** (+1: etkileşim cilası) |
| Değişen | `ui.py` (CSS: `:active`, `.tab`/satır hover, `.pctlbl`; panelHTML etiketi) |
| Doğrulama | tarayıcıda: satır hover bg+imleç değişti, ilerleme kartı etiketi, düzen bozulmadı |

## Daha ileri gidilebilecek yerler (kullanıcı kararına bağlı, büyük)

- İlerleme kartları yoğun (çok sayı); "bu dönem ne yapmalıyım / yolunda mıyım"
  odaklı bir özet katmanı.
- Çok dönemli plan görünümü (yol haritasında §2.1).
- Eski/yeni kod eşlemesi (BLG 4901 ↔ BLG 492) — "açtıkları" doğruluğu.
