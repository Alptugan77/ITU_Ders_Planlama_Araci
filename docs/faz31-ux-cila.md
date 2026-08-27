# Faz 31 — UX/UI cila: gerçek ekranlardan bulunanlar

*27.08.2026 · kullanıcı isteği: "ux ve ui konusunda eksikleri bulup giderir
misin sonrasında da olabildiğince iyi hale getirir misin"*

## Yöntem: tahmin değil, gezi

Uygulama gerçek bir öğrenci gibi **hem masaüstü (1280px) hem iPhone (390px)**
genişliğinde gezildi ve her durum ekran görüntüsüyle incelendi: karşılama,
ana rapor, aday listesi, haftalık ızgara, ders ekle penceresi, program
formu. Kullanıcının bütün ekran görüntüleri iPhone'dan geliyordu — mobil
öncelikli bakıldı.

Beş somut sorun çıktı. Hepsi ekranı görmeden fark edilemezdi.

## 🔴 1. Şube kartı mobilde CRN'i KESİYORDU

Ders ekle penceresindeki şube seçenek kartı iki kolonluydu (solda ders,
sağda CRN/saat/hoca). 390px'e sığmıyor, sağ kolon kenardan kesiliyordu:

```
CRN 124…            Sanem Kabada…
Cum 08:30–11:29 yer y…
```

**CRN kayıt günü OBS'ye yazılan sayı** — kesik olması kabul edilemez. Kart
mobilde alt alta diziliyor; tam genişlik açılınca CRN, saat ve hoca adı
eksiksiz görünüyor.

## 🟡 2. Rozet ortasından bölünüyordu

"ÖNŞART BİLGİSİ YOK" rozeti dar ekranda iki satıra bölünüyor ve kenarlık
**kırık bir kutu** çiziyordu. Rozet `inline-block` + `white-space:nowrap`
ile tek parça; sığmazsa bütün olarak alt satıra iniyor.

## 🟡 3. Önşart durumu iki kez yazılıyordu

Her aday satırında önşart durumu hem rozet ("ÖNŞART BİLGİSİ YOK") hem de
gerekçe metni ("önşart bilgisi katalogda yok — OBS'den doğrula") olarak
görünüyordu. GEO derslerinin çoğunda katalogda önşart metni olmadığı için
bu, **18 adayın 15'inde** tekrar eden bir gürültüydü.

Metin kaldırıldı; rozet kalıyor ve "OBS'den doğrula" tavsiyesi rozetin
ipucuna taşındı. Bilgi kaybı yok, satır çok daha temiz.

⚠️ "Önşartı yok" DEMİYORUZ hâlâ — katalogda metin yok, bu iki farklı şey.
O ayrımı rozet ve ipucu koruyor.

## 🟡 4. Bölüm çubuğu kaydırma ipucu vermiyordu

Mobilde 9 bölümlük yapışkan çubuk ekrana sığmıyor, sonuncusu ("Kademeler")
kenardan kesiliyor ve **kaydırılabildiğine dair hiçbir ipucu yoktu** —
kullanıcı orada başka bölüm olduğunu göremiyordu. Kenar solması eklendi:
kaydırılabilir yönde çubuk soluyor, tamamen kaydırınca kayboluyor (yanlış
ipucu vermesin).

## 🟢 5. Kredi tavanının kaynağı yazmıyordu

Kullanıcı `max_load = 30` ayarlayıp başlıkta "dönem yükü sınırı **40**
kredi" görünce "bozuk mu?" diyebilir. Yönetmelik (MADDE 17) GNO'ya göre
tavanı yükseltiyor ve bunu söylemeden göstermek, ayarıyla çelişen bir sayıyı
açıklamasız bırakıyordu. Başlık artık kaynağı yazıyor:

```
dönem yükü sınırı 40 kredi (yönetmelik)
```

Dönem etiketindeki "(beyan)/(tahmin)" ile aynı desen.

## Dokunulmayan — çünkü iyiydi

- **Karşılama akışı** tek zorunlu adım, isteğe bağlı adımlar kilitli ve
  gerekçeli, gizlilik notu — net. Over-tweaking riski almadım.
- **Haftalık ızgara** masaüstünde takvim, mobilde gün-gün kart yığını olarak
  zaten iyi uyarlanmış.
- **Program formu** düzenli ve anlaşılır.
- **Aday listesi masaüstünde** geniş kolonlarla temiz; sorun yalnız mobil
  yoğunluğuydu ve o da 2–4 ile hafifledi.

## Sayılar

| | |
|---|---|
| Gezilen ekran | 12 (masaüstü + mobil) |
| Bulunan sorun | 5 |
| Test | **923** |
| Yeni gerileme testi | 6 |
