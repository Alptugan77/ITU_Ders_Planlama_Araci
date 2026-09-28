# Faz 111 — Ek sınav şubesi bir ders değil

Kullanıcı (28.09.2026): *"derslerde öğretim yöntemi ek sınav olanları ek
sınav olarak göster yönetmeliğe uygun şekilde o yüzden saatleri yok bazı
derslerin"*.

## Mevzuat

2547 sayılı Kanun m. 44/c: azami öğrenim süresi sonunda mezun olamayan
öğrenciye, başarısız olduğu bütün dersler için **iki ek sınav** hakkı
verilir. Ek sınavlar sonunda tek dersi kalana **sınırsız sınav** hakkı
tanınır. Bu haklar ders değil, sınavdır: derse devam, ders saati ve
kontenjan yoktur.

## Veri

OBS bu hakları "Ek Sınav" ve "Sınırsız Sınav" öğretim yöntemli şube olarak
listeliyor. `make all-plans` sonrası katalogda:

* 71 "Ek Sınav" ve 2 "Sınırsız Sınav" şubesi var. Hiçbirinin saati yok,
  kontenjanı 0.
* 71 dersin 69'unun tek şubesi ek sınav şubesi.
* 65'inde alabilecek program "-", 6'sında gerçek programlar yazılı (BLG,
  BLGE, EHB, MAT …).

## Eski davranış (hatalı)

* **Programa açık ek sınav şubesi** saatsiz normal şube sayılıyordu. Öneri
  motoru onu "saatsiz, çakışmaz" diye programa koyabiliyordu. Oysa normal
  bir öğrenci bu şubeye kayıt olamaz.
* **"-" programlı ek sınav şubesi** Faz 104 kuralıyla "saati, kontenjanı ve
  alabilecek programlar henüz ilan edilmemiştir" diye gösteriliyordu. Bu
  yanlış: ilan bekleyen bir şey yok. (Faz 104'te ölçülen "70 ilansız
  şube"nin 65'i aslında ek sınav şubesiydi.)
* Yol haritası ek sınav şubesini "ders bu dönem açık" sayıyordu. Bahar
  dersine "Güz'de de açılıyor" diyebiliyordu (BLG 322E, BLG 354E).

## Yeni davranış

* `recommend.sinav_turu(yöntem)` → "Ek sınav" | "Sınırsız sınav" | None;
  `Section.sinav` aynı bilgi.
* **Öneri ve program:** ek/sınırsız sınav şubesi yüklenmiyor
  (`_load_sections`). Aday listesine, önerilen programa, açık denklik
  kartına ve yol haritasının şube tahminine girmiyor.
* **Alınamayan dersler:** yalnız sınav şubesi açılmış ders yeni bir engel
  türüyle görünüyor (`EK_SINAV`, "yalnız ek sınav açılmış"): *"bu dönem
  yalnızca ek sınav şubesi açılmıştır; ders saati yoktur. Ek sınav hakkı
  azami öğrenim süresini dolduran öğrencilere tanınır (2547 s. Kanun
  m. 44/c)"*. Arz uyarısında ayrı satır, izleme düğmesi yok (beklenecek
  bir ilan yok).
* **CRN ile yükleme:** azami süresini dolduran öğrenci kendi ek sınav
  CRN'sini girerse şube gösteriliyor, ama saat yerine **"Ek sınav"**
  yazıyor. Izgaranın altında "Saati ilan edilmemiş" listesinden ayrı bir
  **"Ek sınav"** grubunda, mevzuat açıklamasıyla duruyor. Danışman
  sorularına "saati ilan edilmemiştir" sorusu olarak girmiyor. Yazdırılabilir
  liste, PNG ve kayıtlı program kartları da "Ek sınav" yazıyor.
* **Katalogdan (plan dışı) ekleme:** ek sınav şubesi listelenmiyor, yalnız
  ek sınav şubesi olan ders aramada çıkmıyor.
* **İlerleme paneli** (komut satırı): "[bu dönem yalnız ek sınav açılmış]".

Saatsiz şube yazısı arayüzde tek bir yardımcıda (`saatsizYazi`); başka
yerde elle yazılmıyor.

## Gerçek katalogla ölçüm

`make all-plans` sonrası katalogda (BLGE planı, 8. döneme kadar):

* Ek sınav şubesi yüklenen ders: **0** (71 dersin 69'u tamamen düşüyor,
  2'sinin normal şubesi kalıyor).
* BLG 322E ve BLG 354E artık "henüz ilan edilmemiş" değil, "yalnız ek sınav
  açılmış".

## Doğrulama

* `tests/test_faz111_ek_sinav.py` (16 test): yöntem tanıma (8 yazım),
  şubenin programa girmemesi, engel metni (ek ve sınırsız sınav), normal
  şubesi olan dersin aday kalması, Faz 104 davranışının korunması, öneri,
  ilerleme özeti, yol haritası, CRN alanı, katalog araması, arayüz
  etiketleri.
* Mutasyonlar: 8 değişikliğin 8'i geri alınınca testler kırmızı.
* Tarayıcıda (açık/koyu tema) CRN'den ek sınav şubesi yüklendi: ızgara
  altında "Ek sınav" grubu, konsolda hata yok.

## Ek: denk derste dilekçesiz alma

Kullanıcı (28.09.2026): *"denk derslerde bölümümün kodu alabilir
gözüküyorsa dilekçesiz de alabiliyorum"*.

"Denkliği açık dersler" kartı her resmî denklik için "dilekçeyle
saydırılır" yazıyordu. Artık her kaynak dersin şubeleri OBS'deki "alabilir"
listesine göre ayrılıyor (`lesson_allowed_program`):

* Şubelerinden birinin listesinde **anadal kodunuz** (ör. BLGE) açıkça
  yazıyorsa ders **"dilekçesiz"** etiketi alıyor. Etiketin ipucunda hangi
  CRN'lerin bölümünüze açık olduğu yazıyor.
* Kartın notu buna göre:
  * açık kaynakların hepsi bölümünüze açıksa "şubesi bölümünüze açık
    olduğundan dilekçe gerekmez";
  * bir kısmı açıksa "X şubesi bölümünüze açık olduğundan dilekçesiz
    alınabilir, diğerleri dilekçeyle saydırılır";
  * hiçbiri açık değilse eskisi gibi "dilekçeyle saydırılır".
* Listesi boş ya da "-" olan şube dilekçesiz sayılmıyor; bilinmeyen bir
  şey bilinen gibi gösterilmiyor. "Onay gerekebilir" işaretli denklikte
  (requires_approval) not değişmiyor.

Testler: `test_DENKLIK_bolume_acik_sube_dilekcesiz`,
`test_DENKLIK_arayuz_dilekcesiz`. Kart tarayıcıda çizildi, hata yok.
