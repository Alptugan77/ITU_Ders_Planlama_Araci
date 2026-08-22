"""WP1.6 — Önşart kalıplarının keşfi.

Faz 1'de önşartları PARSE ETMİYORUZ, sadece ham saklıyoruz. Bu script ham
metinlerdeki benzersiz kalıpları frekansa göre çıkarır; çıktısı Faz 2'nin
parser spesifikasyonudur.

Bilinen tuzaklar:
    " (MAT 102 MIN DDveya MAT 102E MIN DD)veya (MAT 104 MIN DD...) "
      -> 'DDveya' bitişik, baştaki/sondaki boşluklar rastgele.
"""
from __future__ import annotations

import re
import sqlite3
from collections import Counter
from pathlib import Path

CODE = re.compile(r"[A-ZÇĞİÖŞÜ]{2,4}\s?\d{3,4}[A-Z]{0,2}")
GRADE = re.compile(r"\b[A-F]{2}\b")


def skeleton(raw: str) -> str:
    """Ders kodlarını <C>, notları <G> ile değiştirip kalıbı çıkarır."""
    s = CODE.sub("<C>", raw or "")
    s = GRADE.sub("<G>", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"(?i)\bve\b", " AND ", s)
    s = re.sub(r"(?i)veya", " OR ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def analyse(con: sqlite3.Connection) -> tuple[Counter, Counter]:
    patterns: Counter = Counter()
    tokens: Counter = Counter()
    for (raw,) in con.execute(
        "SELECT prereq_raw FROM course WHERE prereq_raw IS NOT NULL AND TRIM(prereq_raw) <> ''"
    ):
        text = raw.strip()
        if text.lower() in {"yok", "none", "-"}:
            continue
        patterns[skeleton(text)] += 1
        for tok in re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü]+", CODE.sub(" ", text)):
            tokens[tok.lower()] += 1
    return patterns, tokens


def write_report(con: sqlite3.Connection, dest: Path, top: int = 60) -> Path:
    patterns, tokens = analyse(con)
    total = sum(patterns.values())
    lines = [
        "# Önşart kalıpları (WP1.6 çıktısı)",
        "",
        "Faz 2 parser'ının karşılaması gereken girdi uzayı. Otomatik üretildi —",
        "elle düzenleme, `make prereq-report` ile yenile.",
        "",
        f"- Önşartı olan ders sayısı: **{total}**",
        f"- Benzersiz kalıp sayısı: **{len(patterns)}**",
        "",
        "## En sık kalıplar",
        "",
        "| # | Frekans | Kalıp (<C>=ders kodu, <G>=not) |",
        "|---|---------|--------------------------------|",
    ]
    for i, (pat, n) in enumerate(patterns.most_common(top), 1):
        lines.append(f"| {i} | {n} | `{pat[:160]}` |")
    lines += ["", "## Bağlaç / anahtar kelime frekansları", "",
              "| Token | Frekans |", "|-------|---------|"]
    for tok, n in tokens.most_common(25):
        lines.append(f"| `{tok}` | {n} |")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dest
