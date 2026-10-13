# Faz 136 — Ders penceresi: önce şube ve eylemler, sonra analiz

**Tarih:** 13.10.2026
**İstek:** "continue improving the ui and ux"

Izgarada bir derse tıklanınca açılan pencere en çok kullanılan pencere:
şube değiştirmek, dersi çıkarmak, saate kilitlemek buradan yapılıyor.
Ölçüldüğünde (1440px, vitrin öğrencisi) sırası şuydu:

1. başlık, kredi
2. puan kırılımı
3. zorluk kutusu (334px; yarısı yöntem paragrafı)
4. not dağılımı, dış bağlantılar
5. başka şube, yerine başka ders
6. **Programdan çıkar · Bu saate kilitle · Kontenjanı izle**
7. kilit ve izleme açıklamaları

Seçili şubenin CRN'i, saati, dersliği ve hocası pencerenin hiçbir yerinde
yoktu. Asıl eylemler ~900px aşağıdaydı.

## Yeni sıra

1. başlık, kredi
2. **Programdaki şube**: CRN, gün ve saat, derslik, hoca, doluluk
3. **eylemler** ve "Şube fark etmez, saat önemliyse" satırı
4. başka şube, yerine başka ders (karar verilecek seçenekler)
5. **Ders hakkında**: puan kırılımı, zorluk, not dağılımı, dış bağlantılar
6. kilit ve izleme açıklamaları

Zorluk kutusunda formül ve ölçek "Nasıl hesaplanır?" altında katlı.
"Tahmindir; öneri puanına dahil edilmez" notu katlanmıyor.

## Odak

Eylemler üste çıkınca pencerenin ilk odaklanabilir öğesi "Programdan
çıkar" oluyordu: pencere açılır açılmaz Enter'a basan dersi silerdi.
Odak artık başlıkta (`tabindex="-1" autofocus`). "Programa ekle"
penceresinde de aynı.

Görsel: `Claude outputs/f136-ders-penceresi-once-sonra.png`.
