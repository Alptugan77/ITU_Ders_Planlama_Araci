# Faz 32 — Denkliği açık gereken dersler

*27.08.2026 · kullanıcı isteği: "küçük bir sekmede almam gereken derslerin
eğer denkliği olan bir ders açıksa onları listeleyip bilgilerini gösteren bir
kısım ekler misin"*

## Ne yapıyor

Almam gereken bir dersin (hedef) **denkliği** bu dönem açıksa, o açık dersi
(kaynak) bilgileriyle listeliyor. Denklik yönü:

```
{kaynaklar} → hedef        kaynakları alınca hedef sağlanır
```

Yani planımda gereken `MAT 210E` yerine, denkliği olan ve bu dönem açık olan
`GEO 220E`'yi alırsam `MAT 210E` sayılır. Bölüm her satırda gösteriyor:
gereken ders, açık denkliği, ve o dersin **CRN'i, saati, hocası, kontenjanı**.

```
BEYANIN  MAT 210E  Engineering Mathematics  — denkliği açık:
   GEO 220E  Geomatik Müh.İçin Müh. Mat.
   CRN 13493 · Pzt 13:30–16:29 · Hasan Tonbul       50 boş · 1 şube
```

## Aday listesinden neden ayrı

Aday listesi **planındaki açık dersleri** gösteriyor. Burada gösterilen kaynak
ders **planında olmayabilir** ama denklikle bir gereksinimi karşılıyor. ÇAP
öğrencisi için asıl kazanç bu: bir **anadal** dersi (GEO 220E) aynı anda bir
**ÇAP** gereksinimini (MAT 210E) karşılıyor. Bunu aday listesi göstermezdi
çünkü GEO 220E, BLG ÇAP planının slotlarında değil.

## Hangi denklikler gösteriliyor — ve neden

| Durum | Karar |
|---|---|
| Hedef zaten SAĞLANMIŞ (aldın/denklikle kazandın) | gösterilmez — eyleme dönük değil |
| Kaynağın hiçbiri açık değil | gösterilmez — alınacak bir şey yok |
| Kaynağı zaten aldın | gösterilmez — denklik zaten uygulanır |
| **Kullanıcı beyanı** (`user_declared`) | **her zaman** gösterilir — beyan niyeti bildirir |
| **Resmî** denklik (OBS) | yalnız hedef GERÇEKTEN gereken bir plan dersiyse |

Son ayrım önemli: resmî denklikler katalog çapında; hepsini göstermek
gürültü olurdu. Kullanıcının **kendi beyanı** ise "bunu şunun yerine
saydıracağım" demek — niyeti açık, o yüzden hedefi plan slotunda olmasa da
gösteriliyor. (Ölçüldü: gerçek katalogda 4 beyan var; ikisi bu dönem açık bir
kaynağa denk geliyor — MAT 210E←GEO 220E, MAT 281E←GEO 109E.)

## Dürüstlük ayrıntıları

- **Çok kaynaklı denklik** (`{A,B} → X`): biri açık biri kapalıysa gösterilir
  ama `allReady=False` ve ⚠ ile "o da gerekiyor" yazılır — tek başına açık
  kaynak hedefi tamamlamaz.
- **Dil varyantı** (`MAT 210E` + `MAT 210`): aynı kaynaktan aynı şey; tek
  satıra tekleştiriliyor.
- **Program kapalı şube** açık sayılmıyor — `load_sections` öğrencinin
  program koduyla süzüyor.
- Kaynağa tıklama programa ekleme penceresini açıyor — **yalnız aday
  havuzundaysa**. Değilse kart bilgi amaçlı (yine CRN/saat/kontenjan
  görünüyor), sessiz tıklanamazlık yerine görünüm ve ipucu farklı.

## Sayılar

| | |
|---|---|
| Test | **932** |
| Yeni test | 9 |
| Yeni bölüm | `#denklikSection` — masaüstü + mobil doğrulandı |
