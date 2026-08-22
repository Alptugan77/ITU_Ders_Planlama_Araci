#!/bin/bash
# itucap — çift tıklayınca uygulamayı açar (macOS).
#
# Finder'da çift tıkla. İlk çalıştırmada bir kez izin vermen gerekebilir:
#   Sağ tık > Aç  ya da  chmod +x itucap.command
#
# Ne yapıyor: klasöre geçer, sanal ortam yoksa kurar, sunucuyu başlatır.
# Durdurmak için bu pencerede Ctrl+C.
cd "$(dirname "$0")" || exit 1

if [ ! -x .venv/bin/python ]; then
  echo "⚙️  Sanal ortam yok, kuruluyor (bir kerelik, birkaç dakika)…"
  make setup || { echo "❌ Kurulum başarısız."; read -r -p "Kapatmak için Enter"; exit 1; }
fi

if [ ! -f data/reference.sqlite3 ]; then
  echo "📥 Veri yok, ilk tazeleme yapılıyor…"
  make refresh
fi

echo
make app
echo
read -r -p "Kapatmak için Enter'a bas "
