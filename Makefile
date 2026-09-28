PY ?= python3
VENV := .venv
BIN := $(VENV)/bin

.PHONY: help setup refresh offline app watch watch-kur watch-kaldir watch-durum changes notdagilimi suggest all-plans plans kesif plan-info programs basvuru site gizlilik vitrin tasarim status verify sequence student transcript progress recommend ui test prereq-report clean

help:
	@echo "make setup     - sanal ortam + bağımlılıklar"
	@echo "make refresh   - tüm veriyi tazele (itu-helper + OBS)"
	@echo "make offline   - sadece diskteki itu-helper verisiyle yeniden kur"
	@echo "make status    - veritabanı özeti"
	@echo "make verify    - Faz 1 bitiş kriterleri raporu"
	@echo "make sequence  - ikinci programı önşart kademelerine ayır (Faz 2)"
	@echo "make programs  - ÇAP/yandal planlarını listele (T=yandal ile tip seç)"
	@echo "make changes   - son iki tazeleme arasında ne değişti (yeni ders, dolan kontenjan)"
	@echo "make notdagilimi - geçmiş dönemlerin harf notu dağılımı (ARGS=\"--hepsi\")"
	@echo "make suggest   - aday denklikler (aldığın ders = plandaki ders)"
	@echo "make watch     - kontenjan nöbeti: yer açılınca bildirim (Ctrl+C ile dur)"
	@echo "make watch-kur - nöbeti ARKA PLANDA kur (macOS; watch-durum / watch-kaldir)"
	@echo "make all-plans - HER programın ÇAP/yandal planını çek (yavaş)"
	@echo ""
	@echo "make student            - kaydı kur + transkript şablonu üret"
	@echo "make transcript FILE=x  - geçilen dersleri yükle"
	@echo "make progress           - anadal + ikinci program ilerleme paneli"
	@echo "make recommend          - çakışmasız ders programı önerileri (Faz 5)"
	@echo "make app                - YEREL UYGULAMA: düzenlenebilir arayüz (Faz 8)"
	@echo "make ui                 - tek dosyalık statik rapor üret + aç (Faz 6-7)"
	@echo "make ui ARGS=\"--donem 7\"  - bulunduğun dönemi elle ver"
	@echo ""
	@echo "make test      - testler"
	@echo "make plans P=BLG_LS T=cap  - OBS plan listesi"
	@echo "make plans P=BLG_LS ARGS=--tara - hangi plan tiplerinde plan var"
	@echo "make kesif T=yandal ARGS=--planlar - OBS'ye sor: hangi programlar var"
	@echo "make basvuru  - hangi ÇAP/yandal programlarına başvurabilirim"
	@echo "make site     - GitHub Pages için statik site kur"
	@echo "make gizlilik - repoya kişisel veri sızmış mı"
	@echo "make vitrin   - uydurma bir öğrenciyle arayüzü aç (ARGS=\"--ekran DIZIN\")"
	@echo "make tasarim  - tasarım envanteri (ARGS=--denetle: ölçek dışı değer var mı)"

setup:
	$(PY) -m venv $(VENV)
	$(BIN)/pip install -q --upgrade pip
	$(BIN)/pip install -q -e ".[dev]"
	@# Kişisel yapılandırma repoda yok — örnekten kopyalanır, üzerine yazılmaz.
	@test -f config/settings.toml   || cp config/settings.example.toml   config/settings.toml
	@test -f config/denklikler.toml || cp config/denklikler.example.toml config/denklikler.toml
	@echo "✅ hazır."
	@echo "   1) make programs           → plan id'lerini bul"
	@echo "   2) config/settings.toml    → kendi bölümünü yaz"
	@echo "   3) make refresh            → veriyi çek"

refresh:
	$(BIN)/python -m itucap.pipeline refresh

offline:
	$(BIN)/python -m itucap.pipeline refresh --skip-obs --offline

status:
	$(BIN)/python -m itucap.pipeline status

verify:
	$(BIN)/python -m itucap.pipeline verify

sequence:
	$(BIN)/python -m itucap.pipeline sequence

student:
	$(BIN)/python -m itucap.pipeline student

transcript:
	@test -n "$(FILE)" || (echo "kullanım: make transcript FILE=transkript.txt"; exit 1)
	$(BIN)/python -m itucap.pipeline transcript add --file "$(FILE)" --replace

progress:
	$(BIN)/python -m itucap.pipeline progress

recommend:
	$(BIN)/python -m itucap.pipeline recommend $(ARGS)

app:
	$(BIN)/python -m itucap.pipeline app $(ARGS)

ui:
	$(BIN)/python -m itucap.pipeline ui $(ARGS)
	@command -v open >/dev/null && open data/itucap.html || true

site:
	$(BIN)/python tools/site_kur.py $(ARGS)
	@echo "   dene: python3 -m http.server -d site 8000"

gizlilik:
	$(BIN)/python tools/gizlilik_denetimi.py

# Faz 56 — gerçekçi ama UYDURMA bir öğrenci; tasarım turları onunla ölçülüyor.
vitrin:
	$(BIN)/python tools/vitrin.py $(ARGS)

# Faz 56 — tasarım sistemi: envanter / ölçek denetimi / tokens.json.
tasarim:
	$(BIN)/python tools/tasarim_envanteri.py $(ARGS)

basvuru:
	$(BIN)/python -m itucap.pipeline basvuru $(ARGS)

kesif:
	$(BIN)/python -m itucap.pipeline kesif --plan-type $(or $(T),yandal) $(ARGS)

plans:
	$(BIN)/python -m itucap.pipeline plans $(or $(P),BLG_LS) --plan-type $(or $(T),cap) $(ARGS)

watch:
	$(BIN)/python -m itucap.pipeline watch $(ARGS)

# Faz 53 — nöbeti ARKA PLANDA (macOS launchd): terminal gerekmez, oturum
# açılınca kendiliğinden başlar.
watch-kur:
	$(BIN)/python -m itucap.pipeline nobet kur $(ARGS)

watch-kaldir:
	$(BIN)/python -m itucap.pipeline nobet kaldir

watch-durum:
	$(BIN)/python -m itucap.pipeline nobet durum

changes:
	$(BIN)/python -m itucap.pipeline changes $(ARGS)

# Faz 38 — geçmiş dönemlerin harf notu dağılımı (OBS public).
# Varsayılan kapsam PLANINDAKİ dersler (~250 istek, 4-5 dk). Bütün katalog
# için ARGS="--hepsi" — ~5400 istek, 1,5 saat; dönemde bir kez yeter.
notdagilimi:
	$(BIN)/python -m itucap.pipeline notdagilimi $(ARGS)

suggest:
	$(BIN)/python -m itucap.pipeline suggest

plan-info:
	@test -n "$(ID)" || (echo "kullanım: make plan-info ID=1815"; exit 1)
	$(BIN)/python -m itucap.pipeline plan-info $(ID)

all-plans:
	$(BIN)/python -m itucap.pipeline refresh --all-programs --all-equivalences

programs:
	$(BIN)/python -m itucap.pipeline programs $(if $(T),--tur $(T),) $(if $(Q),--ara $(Q),)

test:
	$(BIN)/python -m pytest -q
	$(BIN)/python tools/gizlilik_denetimi.py

clean:
	rm -f data/reference.sqlite3*
	@echo "kullanıcı DB'si (data/user.sqlite3) BİLEREK silinmedi."
