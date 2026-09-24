# Faz 70 — Gece teması okunurluğu

*24.09.2026 · kullanıcı: "continue your improvements and can you change dark
theme it is less readable then light theme. and create a pr".*

Testler **1321 → 1326** (+5, `tests/test_faz70_koyu_tema.py`), 4 atlandı.
Geri alma deneyi: eski palet → üç test kırmızı; danışman sorusu kaldırılınca
iki test kırmızı.

## Teşhis (ölçüldü)

Kontrast **oranları** iki temada yakındı — gövde 14:1 / 19:1, açıklama
6.95:1 / 7.65:1 — ve kontrast aracı iki temayı da geçiriyordu. Gece yine de
okunmuyordu; sebep algı:

| Ölçü | Eski gece | Yeni gece | Gündüz |
|---|---|---|---|
| Zemin ışıklığı (OKLab L) | 0.19 (siyaha yakın) | **0.24** | 1.00 |
| Kart ↔ sayfa farkı (ΔE) | 0.031 | **0.038** | — |
| İnce çizgi / kart | 1.26:1 | **1.46:1** | 1.42:1 |
| Açıklama (ink-2) / kart | 6.95:1 | **9.03:1** | 7.65:1 |
| Meta, ipucu (ink-3) / kart | 5.23:1 | **6.91:1** | 5.62:1 |

Neredeyse siyah zemin açık yazıda parlama yapıyor, kart sayfadan
ayrılmıyordu ve kenarlar kayboluyordu. Koyu zeminde küçük boy gri yazı da
aynı oranda gündüzdekinden soluk algılanıyor.

## Değişiklik

Tek kaynak `src/itucap/tasarim.py` (CSS oradan üretiliyor): gece paleti
"loş koyu"ya çekildi — zemin `#1A1F29`, kart `#222835`, ikincil yüzey
`#2B3240`, çizgi `#3A4252`; yazı `#EEF2F8` / `#C3CBD8` / `#A9B2C2`; aksan ve
veri renkleri aynı aileden bir basamak açık. Gündüz teması **değişmedi**.

* `tools/kontrast_olcumu.py`: 42 çiftin tamamı taban üstünde.
* `tools/ton_merdiveni.py`: ders tonları — yazı ≥ 4.60 (taban 4.5), zemin
  ΔE ≥ 0.043 (taban 0.035), basamak ΔE 0.0167 (test tabanı 0.015).
* Yeni test yukarıdaki dört algı ölçüsünü sabitliyor (ikincil yazı, katman
  ayrımı, çizgi, zemin ışıklığı) — biri geri kayarsa kırmızı.

## Ek: ulaşılamayan eşik danışmana soruluyor

Faz 69'un kalan-ders hesabı tek yardımcıya (`kalanGereken`) alındı; satır ve
danışman özeti aynı sayıyı kullanıyor. Kalan bütün dersler AA olsa bile bir
eşiğe ulaşılamıyorsa danışman özetine soru ekleniyor: *"Mezuniyet için
GNO'nun 2.00 olması gerekmektedir; kalan tüm derslerim (66 kredi) AA olsa
bile ortalamam en fazla 1.00 olur. Seçeneklerim nelerdir?"*
