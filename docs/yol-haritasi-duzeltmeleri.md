# Yol haritasına düzeltmeler (Faz 1 keşfinden sonra)

> 17 Ağustos 2026'da OBS üzerinde yapılan canlı keşif, yol haritasındaki üç
> varsayımı çürüttü. Üçü de veri modelini etkiliyor, o yüzden şemaya işlendi.

---

## D1 — ÇAP planı programa değil, **(anadal, ÇAP) ÇİFTİNE** göre tanımlı ⭐

Yol haritası `plan(program_code, plan_type, iteration)` varsayıyordu.
Gerçek: `BLG_LS` + `cap` sorgusu **37 plan** döndürüyor ve başlıkları şöyle:

```
CEV_BLG    Double Major Program Before 2013-2014 / Fall Semester
EHB_BLG    Double Major Program After 2018-2019 / Fall Semester
GEO_BLG    Double Major Program Before 2013-2014 / Fall Semester
TUMMUH_BLG Double Major Program After 2018-2019 / Fall Semester
YZV_BLG    Double Major Program
```

Yani "Bilgisayar ÇAP planı" diye tek bir şey yok; **hangi anadaldan geldiğine
göre farklı plan** var. `TUMMUH` = "tüm mühendislik" ortak planı.

**Şema etkisi:** `plan.host_program_code` alanı eklendi + `plan_host_program`
tablosu (planın geçerli olduğu anadal programları, OBS'deki "Associated
Programs" tablosundan).

**Senin durumun için sonuç:**
`HTA_BLG` diye bir plan **yok**; `GEO_BLG` var ama sadece *2013-2014 öncesi*.
Güncel geçerli plan **`TUMMUH_BLG` — After 2018-2019 / Fall Semester (id 2229)**
ve `HTAE_LS` bu planın Associated Programs listesinde (50 program) **var**.
→ `config/settings.toml → cap_plan_id = 2229`

---

## D2 — ÇAP planları **dönemsiz**

Yol haritası "dönem tablolarını çıkar (dönem 1–8)" diyordu. ÇAP planı düz bir
liste: yarıyıl sütunu yok, yerine `Compulsory/Elective` (Z/S) sütunu var.

Mantıklı: ÇAP öğrencisi dersleri anadal programının boşluklarına yerleştirir,
sabit bir yarıyıl akışı yoktur.

**Şema etkisi:** `plan_slot.term_no` nullable; `plan.is_term_based` bayrağı.
**Algoritma etkisi:** Öneri motorundaki `dönem_yakınlığı_puanı` kriteri ÇAP
slotlarında uygulanamaz — onun yerine "önşart zinciri derinliği" kullanılmalı
(Faz 5'te ele alınacak).

Plan 2229'un yapısı: **20 zorunlu + 2 seçmeli havuz (MT)**, AKTS aralıklı (`4 / 5 / 6`).

---

## D3 — Denklik verisi neredeyse boş; "hepsini çek" mümkün değil

* Denklik sayfası 4 parametrenin **hepsini** zorunlu tutuyor → ders kodu boş
  bırakıp tüm denklikleri almak **mümkün değil**, döngü şart.
* Taranan tüm kombinasyonlarda (HTAE 39, BLG ÇAP 1, Kimya Müh. ~30) **sıfır** kayıt.

**Sonuç:** Denklik, yol haritasında "çekirdek" olarak konumlanmıştı; senin
ÇAP çiftin için pratikte **devre dışı**. Şema ve scraper duruyor (başka
programlarda veri olabilir), ama Faz 2/3 planlaması denkliğe bel bağlamamalı.
Gerçek hayatta denklik gerekirse `confidence='user_declared'` ile elle girilecek
ve "Fakülte Yönetim Kurulu onayı gerekir" diye işaretlenecek.

---

## D5 — ⭐ Bu çiftte **çift sayım yok**, ve bu bir veri hatası değil

Yol haritasının merkezinde şu vardı (§1.2, §1.3):

> "ÇAP'ın matematiksel özü… bir ders iki planda birden sayılabilir. Puanlamada
> **birincil kriter** bu olmalı: `score = 100 × dual_count + …`"

Ölçüm (`make verify`):

| Kesişim | Sayı |
|---|---|
| HTAE zorunlu ∩ ÇAP zorunlu | **0** |
| HTAE zorunlu ∩ ÇAP havuzu | **0** |
| HTAE havuzu ∩ ÇAP zorunlu | **0** |
| HTAE havuzu ∩ ÇAP havuzu | **0** |

Sebep: HTAE planındaki 54 zorunlu ders yalnızca `GEO, MAT, FIZ, ING, ATA, TUR, DAN`
branşlarından; `TUMMUH_BLG` planı ise 20 dersin **hepsi `BLG`**.

Yani **İTÜ ortak dersleri (MAT/FIZ/BİL…) planı yazarken zaten düşmüş.**
`TUMMUH_BLG` tam bir Bilgisayar Mühendisliği programı değil, bir **fark planı**.
Çift sayım "keşfedilecek bir fırsat" değil, plana gömülü bir varsayım.

**Sayılar:**

| | AKTS |
|---|---|
| HTAE zorunlu | 212 |
| ÇAP zorunlu (20 ders) | **117** |
| ÇAP seçmeli (2 × MT havuzu) | ~8–12 |
| **ÇAP'ın ek yükü** | **~125–129** |

### Mimariye etkisi

| Faz | Yol haritası | Gerçek |
|---|---|---|
| 3 — Eşleme motoru | Bipartite matching, ortak ders çözümü | Neredeyse tetiklenmiyor. Yapı kalsın (`slot_fulfillment` genel), ama **kritik yol değil** |
| 5 — Öneri motoru | `100 × dual_count` birincil kriter | **Ölü ağırlık.** Yerine: önşart zinciri derinliği + anadal programına sığdırma + kontenjan |
| 6 — Arayüz | "Çift sayım rozeti UI'ın en görünür öğesi" | Rozet gösterilecek bir şey yok. Yerine: **"ÇAP'ta kalan 125 AKTS'yi kaç döneme yayarım"** |

**Problemin gerçek tanımı bu çift için şu:**
*"ÇAP'ın 22 gereksinimini, anadal programımın boş saatlerine, önşart sırasını
bozmadan ve dönem AKTS sınırını aşmadan nasıl sıralarım?"*
Bu bir **çizelgeleme/sıralama** problemi, çift sayım problemi değil.

> Not: Bu, HTAE+BLG çiftine özgü bir sonuçtur. `GEO_BLG` gibi bölüme özel eski
> planlarda veya başka çiftlerde örtüşme çıkabilir — `verify` bunu her çift için
> ölçüyor, varsayıma gerek yok.

---

## D4 — Küçük düzeltmeler

| Konu | Yol haritası | Gerçek |
|---|---|---|
| Playwright gerekir mi? | "gerekebilir" | **Hayır** — sayfa sunucuda render ediliyor, `httpx` yeterli |
| Havuz kategorisi | MT/ITB/TB/TM/ENG | **SNT** de var (Sanat); ayrıca `(MT I)`, `MT II` gibi parantezsiz/roma rakamlı varyantlar |
| `course_plans.txt` iterasyonları | tüm iterasyonlar | HTAE için **tek** iterasyon (2024-2025 sonrası) — tarihsel planlar sadece OBS'de |
| `lessons.psv` boyutu | "3.381 satır, düşük" | 3.409 satır; **çok oturumlu dersler tek satırda, alanlar boşlukla ayrılmış** (`"MED MED"`, `"Monday Tuesday"`) |

---

## Faz 1 durum tablosu

| Bitiş kriteri | Durum |
|---|---|
| 1. Tek komutla sıfırdan veritabanı | ✅ `make refresh` |
| 2. ≥1 anadal + ≥1 ÇAP planı yüklü | ✅ HTAE (2295, 54 zorunlu + 7 havuz) + TUMMUH_BLG (2229, 20 + 2) |
| 3. ÇAP planı gözle doğrulanmış | ✅ 18.08.2026, OBS ile birebir |
| 4. Çok kaynaklı denklik modellenmiş | ⚠️ şema ✅, veri yok (D3) |
| 5. Güncel dönem CRN'leri | ✅ 3.409 şube, 3.621 oturum |
| 6. Çakışma SQL'i | ✅ `lesson_meeting(day_of_week, start_min, end_min)` |
| 7. Kalite kontrolleri | ✅ 10 kontrol çalışıyor |
| 8. Kullanıcı verisi ayrı, şifre istenmiyor | ✅ `data/user.sqlite3` ayrı dosya |
| 9. `obs-endpoints.md` + `prereq-patterns.md` | ✅ |

**Faz 1 kapandı** — `make verify` tüm kriterleri yeşil raporluyor.
