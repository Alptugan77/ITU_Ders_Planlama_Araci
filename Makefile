PY ?= python3
VENV := .venv
BIN := $(VENV)/bin

.PHONY: help setup refresh offline app watch changes suggest all-plans plans plan-info programs basvuru gizlilik status verify sequence student transcript progress recommend ui test prereq-report clean

help:
	@echo "make setup     - sanal ortam + bağımlılıklar"
	@echo "make refresh   - tüm veriyi tazele (itu-helper + OBS)"
	@echo "make offline   - sadece diskteki itu-helper verisiyle yeniden kur"
	@echo "make status    - veritabanı özeti"
	@echo "make verify    - Faz 1 bitiş kriterleri raporu"
	@echo "make sequence  - ikinci programı önşart kademelerine ayır (Faz 2)"
	@echo "make programs  - ÇAP/yandal planlarını listele (T=yandal ile tip seç)"
	@echo "make changes   - son iki tazeleme arasında ne değişti (yeni ders, dolan kontenjan)"
	@echo "make suggest   - aday denklikler (aldığın ders = plandaki ders)"
	@echo "make watch     - kontenjan nöbeti: yer açılınca bildirim (Ctrl+C ile dur)"
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
	@echo "make basvuru  - hangi ÇAP/yandal programlarına başvurabilirim"
	@echo "make gizlilik - depoya kişisel veri sızmış mı"

setup:
	$(PY) -m venv $(VENV)
	$(BIN)/pip install -q --upgrade pip
	$(BIN)/pip install -q -e ".[dev]"
	@# Kişisel yapılandırma depoda yok — örnekten kopyalanır, üzerine yazılmaz.
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

gizlilik:
	$(BIN)/python tools/gizlilik_denetimi.py

basvuru:
	$(BIN)/python -m itucap.pipeline basvuru $(ARGS)

plans:
	$(BIN)/python -m itucap.pipeline plans $(or $(P),BLG_LS) --plan-type $(or $(T),cap)

watch:
	$(BIN)/python -m itucap.pipeline watch $(ARGS)

changes:
	$(BIN)/python -m itucap.pipeline changes $(ARGS)

suggest:
	$(BIN)/python -m itucap.pipeline suggest

plan-info:
	@test -n "$(ID)" || (echo "kullanım: make plan-info ID=1815"; exit 1)
	$(BIN)/python -m itucap.pipeline plan-info $(ID)

all-plans:
	$(BIN)/python -m itucap.pipeline refresh --all-programs

programs:
	$(BIN)/python -m itucap.pipeline programs $(if $(T),--tur $(T),) $(if $(Q),--ara $(Q),)

test:
	$(BIN)/python -m pytest -q
	$(BIN)/python tools/gizlilik_denetimi.py

clean:
	rm -f data/reference.sqlite3*
	@echo "kullanıcı DB'si (data/user.sqlite3) BİLEREK silinmedi."
