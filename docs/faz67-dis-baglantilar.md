# Faz 67 — İTÜ Helper, OBS, Kepler ve yönergeye yönlendirme

*24.09.2026 · kullanıcı: "gelişmelere devam et ve gerektiğinde site içinde itü
helper gibi sitelere yönlendir ve bahset".*

Araç, verisini iki kaynaktan alıyor ama bunu sayfada hiç söylemiyordu:
ders/şube/kontenjan **İTÜ Helper**'ın açık veri reposundan
(`itu-helper/data`), planlar/denklikler/not dağılımları **İTÜ OBS**'den.
Kullanıcının asıl işi (ders kaydı) ise başka bir sitede — Kepler'de —
yapılıyor. Artık sayfa bu siteleri yerinde anıyor ve bağlantı veriyor.

Testler **1307 → 1313** (+6, `tests/test_faz67_dis_baglantilar.py`), 4 atlandı.
Geri alma deneyi: beş kuralın **beşi** kırmızı.

## Adresler — tek yerde, uydurma değil

`config.DIS_BAGLANTILAR` (arayüz `DATA.links` ile okur):

| Anahtar | Site | Kaynak |
|---|---|---|
| `kepler` | Kepler — ders kaydı | İTÜ Helper ana sayfası, "İTÜ KISAYOLLARI" |
| `obsProgram` | OBS Ders Programı | aynı liste |
| `obsPlan` | OBS Ders Planları | aynı liste + `config.EP["plan_page"]` |
| `obsNot` | OBS Ders Not Dağılımı | `docs/obs-endpoints.md` §5 |
| `yonerge` | ÇAP/Yandal Yönergesi | `kurallar.toml` kaynağı |
| `ituHelper`, `ituHelperOnsart`, `ituHelperProgram` | İTÜ Helper ve iki aracı | `github.com/itu-helper/home` ve `prereq-scheduler` |
| `ituHelperVeri` | `itu-helper/data` | aracın veri kaynağı |

Test, arayüzdeki her `disLink("…")` anahtarının bu tabloda olduğunu ve
betikte elle yazılmış başka bir dış adres bulunmadığını denetliyor.

## Nerede

* **Alt bilgi:** veri kaynakları (İTÜ Helper açık veri reposu, İTÜ OBS) ve
  yararlı bağlantılar (Kepler, OBS Ders Programı, OBS Ders Planları,
  ÇAP/Yandal Yönergesi, İTÜ Helper önşart zinciri ve program oluşturucu).
* **Karşılama kartı:** verinin nereden geldiği, İTÜ Helper'ın adıyla.
* **Kayıt günü (CRN listesi):** *"Ders kaydı Kepler üzerinden, “Ders Kayıt
  İşlemleri” ekranına CRN girilerek yapılır"* + güncel kontenjan için OBS
  Ders Programı. ⚠️ Eskiden "OBS'ye girilecek numaralar" yazıyordu — kayıt
  Kepler'de yapılıyor (web araması ile doğrulandı); basılı listede ve "CRN'den
  yükle" penceresinde de düzeltildi.
* **Ders penceresi:** OBS Ders Programı (şube/kontenjan) ve OBS Ders Planları
  (önşart). Not dağılımının "Kaynak" satırı, verinin okunduğu OBS sayfasına
  **doğrudan** gidiyor (`NotDagilimiSearch?bransKodu=…&dersNo=…&yil=…`,
  `obs_notdagilimi` ile aynı uç).
* **İlerleme panelleri:** OBS'den çekilen planda "planı OBS'de görüntüle"
  (`DersPlanDetay/{id}`; gerçek katalogda 1216 planın tamamı); İTÜ Helper
  kaynaklı planda "plan kaynağı: İTÜ Helper" — OBS'de karşılığı olmayan bir
  sayfaya link verilmiyor.
* **Kademeler:** planların önşart zinciri için İTÜ Helper Önşart Zinciri.
* **Başvuru penceresi:** yönergenin tam metni ve OBS Ders Planları.
* **Site notu:** "güncel kontenjan bilgisi OBS Ders Programı sayfasındadır"
  artık bağlantı.

## Kurallar

* Yeni sekmede açılır, `rel="noopener noreferrer"`: hangi sayfadan
  gelindiği (paylaşım bağlantısındaki CRN'ler dahil) karşı siteye gitmez.
  Bağlantılar yalnız kullanıcı tıklayınca istek yapar — sitenin "üçüncü
  tarafa istek atılmaz" sözü korunuyor.
* Altı çizili ve ↗ işaretli (renk tek işaret değil); dokunma alanı ≥ 24 px
  (Faz 48 kuralı — ilk sürümde 15 px'ti, test yakaladı).
