"""Gerçek veri regresyonu — OBS/itu-helper formatı değişirse burası kırmızı yanar.

Veritabanı yoksa atlanır (CI'da ağ olmayabilir). Yerelde `make refresh` sonrası
`make test` çalıştırıldığında gerçek 4.6k kayıt üzerinden ölçer.
"""
import sqlite3

import pytest

from itucap import config, prereq as P

MIN_PARSE_RATE = 99.5      # %


@pytest.fixture(scope="module")
def con():
    if not config.REF_DB.exists():
        pytest.skip("reference.sqlite3 yok — önce `make refresh`")
    connection = sqlite3.connect(config.REF_DB)
    if connection.execute("SELECT COUNT(*) FROM course").fetchone()[0] < 1000:
        pytest.skip("referans DB boş görünüyor")
    return connection


def test_real_corpus_parse_rate(con):
    total = failed = 0
    failures = []
    for code, raw in con.execute("SELECT code, prereq_raw FROM course"):
        result = P.parse(raw)
        if result.tree is None and result.note is None:
            continue                       # önşartı yok
        total += 1
        if result.tree is None:
            failed += 1
            failures.append((code, result.note))
    assert total > 4000, f"beklenenden az önşartlı ders: {total}"
    rate = 100 * (total - failed) / total
    assert rate >= MIN_PARSE_RATE, (
        f"parse oranı %{rate:.2f} < %{MIN_PARSE_RATE}. İlk hatalar: {failures[:5]}")


def test_no_ambiguous_precedence_in_real_data(con):
    """Gerçek veride aynı derinlikte ve/veya karışmıyor. Karışırsa haberimiz olsun."""
    ambiguous = [code for code, raw in con.execute("SELECT code, prereq_raw FROM course")
                 if P.parse(raw).ambiguous]
    assert ambiguous == [], f"öncelik belirsizliği çıktı: {ambiguous[:10]}"


def test_every_parsed_tree_roundtrips(con):
    """to_text() çıktısı yeniden parse edilebilmeli (ağaç tutarlılığı)."""
    checked = 0
    for _code, raw in con.execute(
            "SELECT code, prereq_raw FROM course WHERE prereq_raw IS NOT NULL LIMIT 800"):
        tree = P.parse(raw).tree
        if tree is None:
            continue
        again = P.parse(tree.to_text()).tree
        assert again is not None
        assert again.courses() == tree.courses()
        checked += 1
    assert checked > 100
