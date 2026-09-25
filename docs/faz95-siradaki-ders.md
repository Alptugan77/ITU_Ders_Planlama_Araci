# Faz 95 — telefonda sıradaki ders

Kullanıcı 25.09.2026: *"continue"*. Faz 93–94'ün ("programa bakarak derse
gidilebilsin") devamı.

## Sorun

Telefonun gün listesi her zaman Pazartesi'den başlıyordu. Okulda sorulan
soru ise "şimdi ne var, sıradaki ders nerede?". Cevap için listeyi kaydırıp
günü bulmak ve saati kendin karşılaştırmak gerekiyordu.

## Değişiklik

* Gün listesinin başında tek satır:
  * ders sürüyorsa: `Şimdi: GEO 315E · INB D01 · bitiş 11:29`;
  * bugün sonra ders varsa: `Sıradaki: 08:30 GEO 315E · INB D01 (1 sa sonra)`;
  * bugün ders kalmadıysa (ya da hafta sonuysa): `Bugün başka ders yok.
    Salı ilk ders: 13:30 GEO 351E · INB D05`.
* Bugünün başlığında "bugün" etiketi.
* Sayfa açık kaldıkça satır dakikada bir tazeleniyor. Liste baştan
  çizilmiyor, dokunuş ve odak bozulmuyor.
* Çevrimiçi ders "çevrimiçi" yazıyor; meşgul saatler ders sayılmıyor.
* Saatten sonra ek yok ("bitiş 11:29"): "11:29'a" doğru olur ama "16:20'a"
  yanlış olurdu.

⚠️ Araçta akademik takvim yok. Tatilde ya da sınav haftasında da "Şimdi"
yazabilir. Bu yüzden ipucu "programınıza göre" diyor; dersin gerçekten
yapıldığını iddia etmiyor.

## Doğrulama

* `tests/test_faz95_siradaki_ders.py`: tarayıcı saati sabitlenerek (Pazartesi
  07:30 → 09:00) açılış, tazeleme ve dört durum sınandı.
* 8 geri alma deneyinden 7'si kırmızı. Kalan "Pazar = 0" deneyi eşdeğer:
  liste yalnız hafta içini gösterdiği için sonuç değişmiyor.
