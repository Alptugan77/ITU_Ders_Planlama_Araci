# Önşart kalıpları (WP1.6 çıktısı)

Faz 2 parser'ının karşılaması gereken girdi uzayı. Otomatik üretildi —
elle düzenleme, `make prereq-report` ile yenile.

- Önşartı olan ders sayısı: **4628**
- Benzersiz kalıp sayısı: **281**

## En sık kalıplar

| # | Frekans | Kalıp (<C>=ders kodu, <G>=not) |
|---|---------|--------------------------------|
| 1 | 1098 | `<C> MIN <G>` |
| 2 | 931 | `(<C> MIN DD OR <C> MIN <G>)` |
| 3 | 651 | `(<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>)` |
| 4 | 366 | `(<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>)` |
| 5 | 107 | `(<C> MIN CC OR <C> MIN <G>)` |
| 6 | 99 | `(<C> MIN DD OR <C> MIN <G>) AND (<C> MIN DD OR <C> MIN <G>)` |
| 7 | 93 | `(<C> MIN DD OR <C> MIN <G>) OR <C> MIN <G>` |
| 8 | 84 | `<C> MIN CC OR <C> MIN <G>` |
| 9 | 76 | `(<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>)` |
| 10 | 61 | `<C> MIN DD OR <C> MIN <G>` |
| 11 | 46 | `(<C> MIN BB OR <C> MIN <G>)` |
| 12 | 42 | `((<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>)) AND ((<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>))` |
| 13 | 38 | `((<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>))` |
| 14 | 33 | `<C> MIN DD OR (<C> MIN DD OR <C> MIN <G>)` |
| 15 | 32 | `(<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>) OR <C> MIN <G>` |
| 16 | 32 | `(<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>)` |
| 17 | 31 | `(<C> MIN DD OR <C> MIN <G>) AND ((<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>))` |
| 18 | 25 | `<C> MIN DD OR (<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>)` |
| 19 | 25 | `(<C> MIN CC OR <C> MIN <G>) OR <C> MIN <G>` |
| 20 | 22 | `(<C> MIN DD OR <C> MIN DD OR <C> MIN <G>)` |
| 21 | 22 | `((<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>)) AND ((<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>))` |
| 22 | 20 | `((<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>)) AND (<C> MIN DD OR <C> MIN <G>)` |
| 23 | 20 | `(<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>) OR ((<C> MIN DD OR <C> MIN <G>) AND (<C> MIN DD OR <C> MIN <G>))` |
| 24 | 20 | `((<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>))` |
| 25 | 17 | `((<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>)) AND ((<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>))` |
| 26 | 17 | `(<C> MIN DD OR <C> MIN <G>) AND (<C> MIN DD OR <C> MIN <G>) AND (<C> MIN DD OR <C> MIN <G>)` |
| 27 | 15 | `((<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>)) AND ((<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>) OR (` |
| 28 | 15 | `((<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>))` |
| 29 | 12 | `((<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>)) AND ((<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>) OR (` |
| 30 | 10 | `<C> MIN DDve <C> MIN <G>` |
| 31 | 10 | `(<C> MIN DD OR <C> MIN <G>) OR <C> MIN DD OR <C> MIN <G>` |
| 32 | 10 | `((<C> MIN DD OR <C> MIN <G>) AND (<C> MIN DD OR <C> MIN <G>)) OR (<C> MIN DD OR <C> MIN <G>)` |
| 33 | 10 | `<C> MIN DDve (<C> MIN DD OR <C> MIN <G>)` |
| 34 | 9 | `(<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>) OR <C> MIN <G>` |
| 35 | 9 | `(<C> MIN DD OR <C> MIN <G>) AND (<C> MIN DD OR <C> MIN <G>) AND ((<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>))` |
| 36 | 9 | `((<C> MIN DD OR <C> MIN <G>) OR <C> MIN <G>)` |
| 37 | 8 | `(<C> MIN DD OR <C> MIN <G>) OR <C> MIN DD OR (<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>)` |
| 38 | 7 | `((<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>)) AND ((<C> MIN DD OR <C> MIN <G>) OR (` |
| 39 | 7 | `(<C> MIN DD OR <C> MIN <G>) AND (<C> MIN DD OR <C> MIN <G>) AND (<C> MIN DD OR <C> MIN <G>) AND (<C> MIN DD OR <C> MIN <G>) AND (<C> MIN DD OR <C> MIN <G>) AND ` |
| 40 | 7 | `((<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>) OR <C> MIN <G>)` |
| 41 | 7 | `(<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>) OR (<C> ` |
| 42 | 6 | `(<C> MIN DD OR <C> MIN <G>) OR <C> MIN DD OR (<C> MIN DD OR <C> MIN <G>)` |
| 43 | 6 | `(<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>) OR (<C> ` |
| 44 | 6 | `(<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>) OR <C> MIN DD OR <C> MIN <G>` |
| 45 | 6 | `((<C> MIN DD OR <C> MIN <G>) OR <C> MIN <G>) AND (<C> MIN DD OR <C> MIN <G>)` |
| 46 | 6 | `(<C> MIN DD OR <C> MIN <G>) AND (<C> MIN DD OR <C> MIN <G>) AND (<C> MIN DD OR <C> MIN <G>) AND (<C> MIN DD OR <C> MIN <G>) AND (<C> MIN DD OR <C> MIN <G>) AND ` |
| 47 | 6 | `((<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>) OR (<C>` |
| 48 | 5 | `(<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>) OR <C> MIN DD OR (<C> MIN DD OR <C> MIN <G>)` |
| 49 | 5 | `<C>` |
| 50 | 5 | `((<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>)) AND ((` |
| 51 | 5 | `<C> MIN DD OR (<C> MIN DD OR <C> MIN <G>) OR <C> MIN <G>` |
| 52 | 5 | `((<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>)) AND ((<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>)) AND ((<C> MIN DD OR <C> MIN <G>) O` |
| 53 | 5 | `(<C> MIN DD OR <C> MIN <G>) AND <C> MIN <G>` |
| 54 | 5 | `(<C> MIN BL OR <C> MIN BL)` |
| 55 | 5 | `((<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>)) AND ((<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>) OR (` |
| 56 | 5 | `(<C> MIN DD OR (<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>))` |
| 57 | 5 | `(<C> MIN DD OR <C> MIN <G>) OR <C> MIN DD OR (<C> MIN DD OR <C> MIN <G>) OR <C> MIN DD OR <C> MIN DD OR (<C> MIN DD OR <C> MIN <G>) OR <C> MIN DD OR <C> MIN DD ` |
| 58 | 4 | `((<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>)) AND ((<C> MIN DD OR <C> MIN <G>) OR (<C> MIN DD OR <C> MIN <G>)) AND ((<C> MIN DD OR <C> MIN <G>) O` |
| 59 | 4 | `<C> MIN DDve (<C> MIN DD OR <C> MIN <G>) AND (<C> MIN DD OR <C> MIN <G>) AND (<C> MIN DD OR <C> MIN <G>) AND (<C> MIN DD OR <C> MIN <G>) AND (<C> MIN DD OR <C> ` |
| 60 | 4 | `(<C> MIN FF OR <C> MIN <G>) OR (<C> MIN FF OR <C> MIN <G>) OR (<C> MIN FF OR <C> MIN <G>) OR (<C> MIN FF OR <C> MIN <G>)` |

## Bağlaç / anahtar kelime frekansları

| Token | Frekans |
|-------|---------|
| `min` | 19661 |
| `dd` | 9103 |
| `ddveya` | 8923 |
| `veya` | 4274 |
| `ve` | 1429 |
| `cc` | 1042 |
| `ccveya` | 227 |
| `ff` | 83 |
| `ffveya` | 70 |
| `bb` | 68 |
| `bbveya` | 58 |
| `ddve` | 43 |
| `dc` | 13 |
| `dcveya` | 11 |
| `blveya` | 7 |
| `bl` | 7 |
| `ccve` | 6 |
| `e` | 1 |
| `dfh` | 1 |
| `deniz` | 1 |
| `kazalarıve` | 1 |
| `emniyet` | 1 |
| `kültürü` | 1 |
| `türkçe` | 1 |
