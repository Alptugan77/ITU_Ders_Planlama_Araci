"""Eski bir veritabanı dosyası yeni şemayla açılabilmeli (sütun ekleme)."""
import re
import sqlite3

from itucap import config, db


def _old_schema() -> str:
    """Mevcut schema.sql'den sonradan eklenen sütunları çıkarıp 'eski' sürümü üretir."""
    sql = (config.PKG_DIR / "schema.sql").read_text(encoding="utf-8")
    for _table, column, coltype in db.ADDED_COLUMNS:
        # sütun satırı + varsa devam eden yorum satırları
        sql = re.sub(rf"^\s*{column}\s+{coltype}\b.*\n(?:\s*--.*\n)*", "", sql,
                     flags=re.MULTILINE)
    return sql


def test_old_db_gets_new_columns(tmp_path):
    path = tmp_path / "old.sqlite3"
    con = sqlite3.connect(path)
    con.executescript(_old_schema())
    con.execute("INSERT INTO plan(id,program_code,plan_type,title) VALUES (1,'HTAE','lisans','x')")
    con.commit()
    # ön koşul: yeni sütunlar gerçekten yok
    for table, column, _ in db.ADDED_COLUMNS:
        assert column not in {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
    con.close()

    con = db.connect(path, "schema.sql")
    for table, column, _ in db.ADDED_COLUMNS:
        cols = {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
        assert column in cols, f"{table}.{column} eklenmedi"

    # veri kaybı olmamalı
    assert con.execute("SELECT COUNT(*) FROM plan").fetchone()[0] == 1


def test_migration_is_idempotent(tmp_path):
    path = tmp_path / "fresh.sqlite3"
    db.connect(path, "schema.sql").close()
    con = db.connect(path, "schema.sql")
    assert db._migrate(con) == []
