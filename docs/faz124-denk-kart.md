# Faz 124 — "Açık denklikler" kartı dersin alınabilir olup olmadığını söylüyor

Kullanıcının kendi verisiyle yapılan inceleme (29.09.2026; HTAE anadal,
BLG ÇAP).

## Bulgular

Kart, gereken bir dersin resmî denkliği bu dönem açıksa onu "yerine bu açık
ders alınabilir" diye gösteriyordu. Ancak dersin bu dönem alınabilir olup
olmadığını denetlemiyordu:

| Kart | Gösterilen | Gerçek |
|---|---|---|
| BLG 317E | BBF 302 — dilekçe gerekmez | Önşart BLG 252E (yeni kodu BBF 203E) geçilmemiş |
| BLG 335E | BBF 301 — dilekçe gerekmez | Önşart (BLG 221/223 …) eksik |
| BLG 336E | BBF 303 — dilekçe gerekmez | Önşart BLG 335E (yeni kodu BBF 301E) eksik |
| BLG 4902E | BLG 492 — dilekçe gerekmez | Bitirme çalışması, en az 95 kredi gerekiyor; tamamlanan 85 |
| TUR 121/122 | TUR 111/112 — dilekçe gerekmez | "Yabancı Öğr. İçin Türk Dili", yalnızca yabancı uyruklu öğrenciler için |

Engel paneli (Faz 120) aynı dersleri "önşart eksik" olarak gösteriyordu; iki
ekran birbiriyle çelişiyordu.

Bu tabloyu üreten iki ayrı hata vardı:

* **Taban kod:** OBS'nin resmî listesi kodları dile bağlı olmayan taban
  hâlde yazıyor ("BBF 302"). Katalogda o kod yok, şube BBF 302E'de açık.
  Önşart denetimi var olmayan koda bakınca "önşart yok" sonucuna
  varıyordu. Denetim artık **şubesi açık olan yazımla** yapılıyor.
* **Kredi:** Kredi eşiği için hesaplanan kredi, denkliklerle genişletilmiş
  notlardan alınınca denklikten "kazanılan" dersler de sayılıyordu; 85 kredi
  329 görünüyordu. Kredi artık ham transkriptten (`POL.earned_credits`)
  hesaplanıyor. Diğer bütün çağrıların da ham transkripti kullandığı
  denetlendi.

## Değişiklik (`ui._acik_denklikler`)

* Her açık kaynak için `notTakable` alanı eklendi: "önşart eksik: …" ya da
  "en az 95 kredi gerekir, tamamlanan 85". Şubesi açık yazımlardan biri
  alınabiliyorsa alan boş kalıyor.
* Kartta "bu dönem alınamaz" etiketi ve gerekçesi gösteriliyor. "Dilekçe
  gerekmez / alınabilir" ifadeleri yalnızca alınabilen kaynaklar için
  kullanılıyor.
* Bütün açık kaynaklar alınamıyorsa başlık "denkliği bu dönem açık, ancak
  şartları sağlanmamaktadır" oluyor.
* Bu dönem gerçekten alınabilen denklikler listenin başına alınıyor.
* "Yabancı Öğr. İçin Türk Dili" dersleri kaynak olarak gösterilmiyor
  (Faz 117'deki öneri kuralıyla aynı).

## Doğrulama

`tests/test_faz124_denk_kart.py` 5 test içeriyor:

* taban kodlu kaynakta önşart denetimi;
* ham krediyle kredi eşiği; kredi bilinmiyorsa iddiada bulunulmaması;
* yabancı öğrenci dersinin kaynaktan çıkarılması;
* alınabilen denkliklerin sıralamada öne alınması ve başlık;
* arayüz metinleri.

4 mutasyonun 4'ü kırmızı. Kart kullanıcının verisiyle, yalnızca yerel ve
geçici bir sunucuda tarayıcıda çizildi; konsolda hata yok.
