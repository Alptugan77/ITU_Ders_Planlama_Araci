"""SQLite yardımcıları. Referans DB ile kullanıcı DB'si bilinçli olarak ayrıdır."""
from __future__ import annotations

import sqlite3
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from . import config


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# Şema kesin değişecek. Ağır bir migration aracı (Alembic) yerine, eklenen
# sütunları otomatik tamamlayan hafif bir mekanizma: CREATE TABLE IF NOT EXISTS
# mevcut tabloya sütun EKLEMEZ, o boşluğu burası kapatır.
ADDED_COLUMNS: list[tuple[str, str, str]] = [
    # (tablo, sütun, tip)
    ("plan", "source", "TEXT"),
    ("plan", "has_course_table", "INTEGER"),
    ("plan_slot", "type_raw", "TEXT"),
    ("plan_slot", "ects", "REAL"),
    ("plan_slot", "alt_course_codes", "TEXT"),
    ("plan_slot", "zs_raw", "TEXT"),
    ("plan", "declared_credits", "REAL"),
    ("plan_slot", "credits_raw", "TEXT"),
    ("plan_slot", "credits_min", "REAL"),
    ("plan_slot", "credits_max", "REAL"),
    ("plan_slot", "pool_status", "TEXT"),
]


def _migrate(con: sqlite3.Connection) -> list[str]:
    applied = []
    tables = {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    for table, column, coltype in ADDED_COLUMNS:
        if table not in tables:
            continue
        cols = {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
        if column not in cols:
            con.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")
            applied.append(f"{table}.{column}")
    if applied:
        con.commit()
    return applied


# ★★ 23.08.2026 — VERİ KAYBI HATASI. Tarayıcı sürümünde transkript ve
# kaydedilen program her yenilemede kayboluyordu; yalnız `settings.toml`
# kalıyordu.
#
# Sebep WAL: SQLite yazdığını `user.sqlite3-wal` yan dosyasına koyuyor ve ana
# dosyaya ancak bir "checkpoint"te aktarıyor. Ölçtük — 37 derslik bir
# veritabanında ana dosya **4096 bayt** (sadece başlık), veri 78KB'lık WAL'da.
# Site kalıcılık için YALNIZ ana dosyayı IndexedDB'ye yazıyordu; yan dosya
# sayfa kapanınca yok oluyordu. `settings.toml` düz metin olduğu için
# etkilenmiyordu — "sadece bölüm ayarları kalıyor" belirtisi tam olarak buydu.
#
# WAL yerel sunucu için seçilmişti (ThreadingHTTPServer, eşzamanlı okuma).
# Tarayıcıda tek iş parçacığı var; WAL hiçbir şey kazandırmıyor, yalnız
# kaybettiriyor. O yüzden ortama göre seçiyoruz.
def journal_mode() -> str:
    """Tarayıcıda (Pyodide/Emscripten) WAL YOK — yan dosya kalıcı olamıyor."""
    return "TRUNCATE" if sys.platform == "emscripten" else "WAL"


def checkpoint(con: sqlite3.Connection) -> None:
    """WAL'daki her şeyi ANA DOSYAYA aktarır.

    Kalıcılığı dosyayı kopyalayarak sağlayan her ortam (tarayıcı, yedekleme)
    bunu çağırmak zorunda. WAL kipinde değilse zararsız."""
    try:
        con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    except sqlite3.Error:
        pass                     # WAL değil ya da kilitli — yazılacak bir şey yok


def connect(path: Path, schema: str | None = None,
            same_thread: bool = True) -> sqlite3.Connection:
    """SQLite bağlantısı.

    `same_thread=False` yalnız yerel sunucu için (Faz 8): `ThreadingHTTPServer`
    her isteği ayrı iş parçacığında çalıştırıyor. Bağlantıyı paylaşmak, tüm DB
    işini tek bir kilit altında tutmak koşuluyla güvenli — `server.State.lock`
    bunu sağlıyor.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, check_same_thread=same_thread)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    # Var olan bir WAL veritabanına TRUNCATE demek onu önce checkpoint eder;
    # yani kip değişimi veri taşımayı da hallediyor.
    con.execute(f"PRAGMA journal_mode = {journal_mode()}")
    if schema:
        # Önce migrate: schema.sql'deki indeksler yeni sütunlara dokunabiliyor,
        # eski bir veritabanında CREATE INDEX aksi halde patlar.
        _migrate(con)
        con.executescript((config.PKG_DIR / schema).read_text(encoding="utf-8"))
        con.commit()
        _migrate(con)
    return con


def reference_db(same_thread: bool = True) -> sqlite3.Connection:
    return connect(config.REF_DB, "schema.sql", same_thread=same_thread)


def user_db(same_thread: bool = True) -> sqlite3.Connection:
    return connect(config.USER_DB, "schema_user.sql", same_thread=same_thread)


@contextmanager
def run_step(con: sqlite3.Connection, step: str):
    """Bir pipeline adımını ingest_run tablosuna kaydeder (WP1.7)."""
    cur = con.execute(
        "INSERT INTO ingest_run(step, started_at, status) VALUES (?,?,?)",
        (step, now(), "running"),
    )
    run_id = cur.lastrowid
    con.commit()
    box = {"rows": 0, "message": ""}
    try:
        yield box
    except Exception as exc:  # kısmi başarı, tam kayıptan iyidir: eski veriyi silme
        con.execute(
            "UPDATE ingest_run SET ended_at=?, status=?, message=? WHERE id=?",
            (now(), "fail", f"{type(exc).__name__}: {exc}"[:500], run_id),
        )
        con.commit()
        raise
    else:
        con.execute(
            "UPDATE ingest_run SET ended_at=?, status=?, rows=?, message=? WHERE id=?",
            (now(), "ok", box["rows"], str(box["message"])[:500], run_id),
        )
        con.commit()
