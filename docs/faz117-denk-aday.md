# Faz 117 — Dilekçesiz denk dersler öneride

Kullanıcı (28.09.2026): *"programda olan derslerin dilekçe gerektirmeyen
denklerini öneride kullanabilirsin ve kullanıcı bunları diğer dersler gibi
kullanabilir olacak şekilde ayarla"*.

## Kural (`recommend.candidates`)

Plandaki zorunlu bir dersin (X) resmî, tek kaynaklı denkliği olan ders (D)
aşağıdaki şartları sağlıyorsa aday oluyor:

* **Dilekçesiz:** D'nin şubesi öğrencinin **kendi** programına açık
  (anadal/ÇAP/yandal; BLG, BLGE, BLG_LS; `normalize.kendi_program_kodlari`,
  Faz 115'teki kart kuralıyla aynı). Yalnız ek program koduyla açık şube
  sayılmıyor.
* **Önşart ve kredi eşiği** D için tutuyor (diğer adaylarla aynı denetim).
* D, "Yabancı Öğr. İçin Türk Dili" (TUR 111/112) değil. Bu derslerin
  şubeleri bütün programlara açık görünüyor, ama yalnız yabancı uyruklu
  öğrenci içindir.

Aday, X'in **yuvasına** bağlanıyor. Yuva eşleştirmesi (Faz 81) X ile D'yi
aynı programa birlikte koymuyor. D geçilince X'in yuvası zaten doluyor
(`expand_with_equivalences`), ilerleme ve yol haritası bunu görüyor.

* **Yük:** D'nin kendi kredisi/AKTS'si (alınan ders o).
* **Puan:** X de bu dönem açıksa D **−40** alıyor ("X bu dönem açık —
  plandaki ders önce"). Öneri planın kendi dersini seçiyor, D seçilebilir
  kalıyor. X açık değilse ceza yok; D öneride doğrudan kullanılıyor.
* **Arayüz:** aday satırında "X yerine" etiketi, gerekçede "X yerine
  (resmî denklik, dilekçesiz)". Ders penceresinde de yazıyor.
* **CRN ile yükleme:** OBS'den yapıştırılan CRN plandaki dersin resmî
  denkliğiyse "plan dışı" değil, o dersin rolüyle ve "X yerine" bilgisiyle
  geliyor.

## Ölçüm (gerçek katalog, 127 lisans planı, transkriptsiz öğrenci)

* 430 denk aday (TUR 111/112 hariç tutulmadan önce).
* 290'ında plandaki ders bu dönem açık değil; denk ders öneride doğrudan
  kullanılabiliyor. Örnek: ARC planı ARC kodlarını yazıyor, dersler MIM
  koduyla açılmış (MIM 203E ← ARC 203E).
* Transkriptli BLGE profilinde önerilen program değişmedi. Tek denk aday
  TUR 112 ("Yabancı Öğr. İçin Türk Dili II") idi ve hariç tutuldu.
  Kurulum süresi değişmedi.

## Doğrulama

`tests/test_faz117_denk_aday.py`:

* kendi program kodları;
* denk aday yuvaya bağlı, gerekçe, puan cezası, aynı yuvada birlikte
  seçilemiyor, yük denk dersin kendisinden;
* plan dersi kapalıyken ceza yok;
* yalnız ek programa açık şube aday değil;
* yabancı öğrenci dersi hariç;
* arayüz etiketi;
* CRN ile gelen denk dersin rolü.

7 mutasyonun 7'si kırmızı. Etiket tarayıcıda çizildi, konsolda hata yok.
