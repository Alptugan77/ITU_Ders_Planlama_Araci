# Faz 103 — "Dönemi hafiflet": hangi ders çıkarılmalı

Kullanıcının "continue" isteği üzerine, Faz 100–102'nin devamı.

## Sorun

Dönem zorluğu yüksekken özet "dönem yükü çok ağır; ders sayısının
azaltılması değerlendirilebilir" diyordu ama **hangi** dersin çıkarılacağını
söylemiyordu. Öğrenci her dersi tek tek çıkarıp sayıya bakmak zorundaydı. Bu
repoda genel uyarı yerine somut öneri ilkesi var (Faz 46).

## Değişiklik (`hafifletmeOnerisi`)

Dönem "zor" veya "çok zor" olduğunda (kademe ≥ 4) özetin altında
**"Dönemi hafifletmek için"** bloğu çıkıyor:

* Her ders tek tek çıkarılıp dönem zorluğu yeniden hesaplanıyor (Faz 102'nin
  `programZorlugu`'su).
* **Sıralama:** en çok hafifleten önce; eşitlikte öneri puanı (bu dönem
  alınmamasının maliyeti) düşük olan önce. En çok iki satır.
* Her satırda "çıkar" düğmesi, yeni zorluk, kademe, kaybedilen öneri puanı ve
  "ders sonraki dönemlere kalır" notu var. Düğme `removeCourse`, yani geri
  alınabilir.
* **Önerilmeyen dersler:**
  * kritik yoldaki ders (ertelenirse mezuniyet uzar);
  * saate kilitlenmiş ders (öğrencinin kendi kararı);
  * çıkarılınca ÇAP/yandal yarıyıl tabanını bozan ders (taban şu an
    sağlanıyorsa);
  * **daha önce kalınan ders** (transkriptte FAILED). Tekrarı ertelenirse
    FF/VF ortalamada kalmaya devam eder ve açtığı dersler de gecikir.
* Hiç aday yoksa bunu söylüyor: "Kritik yol, kilit ve tekrar alınan dersler
  dışında çıkarılabilecek ders bulunmamaktadır."
* Motorun önerisine ve öneri puanına dokunulmuyor; karar öğrencinin.

## Gerçek katalog (BLGE, 5. yarıyıl, Öneri 1 = 7.1)

İlk sürümde ikinci öneri **FF'li FIZ 102E** çıkıyordu; kalınan dersi hariç
tutma kuralı bunun üzerine eklendi. Şimdi öneriler BLG 212E (7.1 → 5.9) ve
BLG 337E (7.1 → 6.2).

## Doğrulama

`tests/test_faz103_hafiflet.py` (vitrin uçtan uca) kontrollü zorluk, puan ve
kritiklik vererek şunları sınıyor: kritik dışlama, sıralama ve eşitlik
bozma, kilit, kalınan ders, orta dönemde öneri olmaması, hepsi kritikken
açıklama, ÇAP tabanı, düğmenin çıkarması ve geri alma. Sekiz mutasyonun
sekizi de kırmızı.
