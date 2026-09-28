# Faz 116 — "Açtıkları" dersin takma adlarıyla sayılıyor

Sayı, önşart metnindeki kodu birebir arıyordu. Önşart metinleri çoğu
zaman eski kodu anıyor (BLG 252E), plan ise yeni kodu koyuyor (BBF 203E).
Gerçek BLGE planında yeni kodlu derslerin sayıları:

* BBF 202E, BBF 204E, BBF 301E, BBF 303E: **0**
* BBF 203E: **1**

Bu sayı iki yerde kullanılıyor:

* öneri puanının "açtığı ders" bileşeni ("N dersin önşartı");
* adayın "açtıkları" listesi ("bunu almazsan şu dersler kapalı kalır").

İkisi de bu dersleri küçümsüyordu.

## Kural

`rules.takma_adlar(kod)`: önşart metinlerinde dersin yerine geçen kodlar.
Hepsi önşart denetiminin zaten kabul ettiği eşleşmeler:

* dersin kendisi;
* dil eşi (`dil_esi`, Faz 113'ten beri lab kodları dahil);
* beyan edilmiş kod göçü grubu (`[[kod_gocu]]`);
* resmî ya da beyan denklikle karşılanan kodlar.

`rules.acilan_hedefler`: bu adlardan birini önşartında anan dersler.

## Etki (gerçek BLGE planı)

| Ders | Önce | Sonra | Planda açtıkları |
|---|---|---|---|
| BBF 203E | 1 | 22 | BBF 301E, BBF 302E, BLG 411E |
| BBF 303E | 0 | 8 | BLG 417E, BLG 4901E |
| BBF 301E | 0 | 3 | BBF 303E |
| BBF 103E | 2 | 9 | BBF 204E |
| BLG 223E | 14 | 19 | BBF 301E, BLG 312E |

Sayı katalog genelinde (eskisi gibi). Bazı dersler resmî denklikleri çok
bölümde önşart olduğu için büyüyor: BBF 102E ≡ MAT 261E, 4 → 66. Bu,
FIZ 101E'nin 132'siyle aynı anlamda; puan en büyük sayıya göre
normalleştiriliyor. Transkriptli BLGE profilinde önerilen program
değişmedi. BBF 301E'nin kartında artık "açtıkları: BBF 303E" yazıyor.
Kurulum süresi değişmedi.

## Doğrulama

`tests/test_faz116_takma_adlar.py`:

* takma adlar: dil eşi, kod göçü, denklik;
* adayın açtığı ders sayısı (0 → 2);
* arayüzdeki "açtıkları" listesi.

5 mutasyonun 5'i kırmızı.
