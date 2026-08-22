"""FAZ 2 — Önşart tokenizer + AND/OR ağacı parser'ı.

Girdi uzayı `docs/prereq-patterns.md`'de ölçüldü: 4.628 ders, 281 benzersiz kalıp.
Gramer küçük ama yazımı bozuk:

    " (MAT 102 MIN DDveya MAT 102E MIN DD)veya (MAT 104 MIN DDveya MAT 104E MIN DD) "

Bozukluklar (hepsi gerçek veriden ölçüldü):
  * `DDveya`, `CCve`, `BLveya` — not ile bağlaç BİTİŞİK yazılıyor
  * `)veya (`, `)ve(` — parantezle bağlaç bitişik
  * baştaki/sondaki boşluklar rastgele
  * bir kayıtta sonda başıboş `+` var (CEN 312E)
  * bir kayıtta önşart yerine DERS ADI yazılmış (MST 471) — kod hiç yok

Öncelik: AND (`ve`) OR'dan (`veya`) sıkı bağlar — standart. Ölçüm: gerçek veride
aynı parantez derinliğinde `ve` ile `veya` KARIŞMIYOR (0/4628), yani bu seçim
mevcut veride hiçbir sonucu değiştirmiyor. Yine de karışık girdi gelirse
`Parsed.ambiguous` bayrağı ile işaretlenir — sessizce yanlış cevap verilmez.
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from typing import Mapping

# --------------------------------------------------------------------- notlar
# İTÜ harf notları. `MIN FF` = "ders alınmış olmalı" (başarı şartı yok).
# ★ İTÜ Lisans Eğitim ve Öğretim Yönetmeliği MADDE 20 (Notlar ve işaretler).
# Doğrulandı 22.08.2026: sis.itu.edu.tr/TR/mevzuat/lisans-yonetmelik.php
#
# Ölçek 0.25 adımlı — ARTI notlar ara basamaklar:
#   AA 4.00 · BA+ 3.75 · BA 3.50 · BB+ 3.25 · BB 3.00 · CB+ 2.75 · CB 2.50
#   CC+ 2.25 · CC 2.00 · DC+ 1.75 · DC 1.50 · DD+ 1.25 · DD 1.00 · FF/VF 0.00
#
# Yönetmelik iki başarı düzeyi tanımlıyor (bkz. CONDITIONAL_PASS):
#   AA…CC       -> "başarmış"
#   DC+…DD      -> "ŞARTLI başarmış"
# Önşartlar açık eşik yazdığı için ('MIN DD') buradaki taban DD'de kalıyor.
GRADE_POINTS: dict[str, float] = {
    "AA": 4.0,
    "BA+": 3.75, "BA": 3.5,
    "BB+": 3.25, "BB": 3.0,
    "CB+": 2.75, "CB": 2.5,
    "CC+": 2.25, "CC": 2.0,
    "DC+": 1.75, "DC": 1.5,
    "DD+": 1.25, "DD": 1.0,
    # ⚠️ FD güncel yönetmelikte YOK; eski transkriptlerde geçtiği için
    # tanınmaya devam ediyor. Yeni giriş için arayüzde önerilmiyor.
    "FD": 0.5,
    "FF": 0.0,
    "VF": 0.0,      # vizesiz kaldı
    # Kredisiz ders işaretleri ve muafiyet — ORTALAMAYA GİRMEZLER,
    # bkz. policy.GPA_EXCLUDED. Buradaki değerler yalnız ÖNŞART karşılaştırması
    # için: BL geçer sayılmalı ki staj önşartı açılsın.
    "BL": 1.0,      # kredisiz dersten başarılı
    "BZ": 0.0,      # kredisiz dersten başarısız
    "M": 4.0,       # muaf (yönetmelikteki işaret)
    "MU": 4.0,      # muaf (OBS/transkript yazımı)
    "T": 0.0,       # dersten çekilme
    "E": 0.0,       # tasarım projesi tamamlanmadı
}
PASSING_MIN = 1.0   # DD ve üstü geçer (DC+…DD "şartlı başarmış")

# Yönetmelik MADDE 20: bu notlar "şartlı başarmış" sayılıyor. Mezuniyette
# sayılmaları GNO şartına bağlı — şartın kendisi HENÜZ DOĞRULANMADI, o yüzden
# motor bir kural uygulamıyor, yalnız işaretliyor (bkz. docs/yapilacaklar.md).
CONDITIONAL_PASS = ("DC+", "DC", "DD+", "DD")

DEFAULT_MIN_GRADE = "DD"


class PrereqError(ValueError):
    """Ham metin gramere uymadı."""


# ------------------------------------------------------------------ tokenizer
# Uzun önce: 'BA+' , 'BA'dan önce denenmeli yoksa artı düşer.
_GRADES = sorted(GRADE_POINTS, key=len, reverse=True)
# ⚠️ IGNORECASE KULLANMA. Ders kodunun sonundaki harf ekini ([A-Z]{0,2})
# büyük harfe sabitlemek, 'ECN 211EveyaECN 211' gibi bitişik yazımda
# 'Ev' yutulmasını engelliyor: 'E' kod ekidir, 'veya' küçük harfle başlar.
# Bağlaçlar ve MIN/not için grup-içi (?i:...) ile seçici esneklik veriyoruz.
_TOKEN_RE = re.compile(
    r"""
      (?P<ws>\s+)
    | (?P<lpar>\()
    | (?P<rpar>\))
    | (?P<min>(?i:MIN)\b)
    # Kod eki küçük harf de olabiliyor ('IEB 322e'), ama 've'/'veya' bitişik
    # yazıldığında ('ECN 211EveyaECN 211') bağlacın başını YUTMAMALI.
    | (?P<code>[A-ZÇĞİÖŞÜ]{2,4}\s*\d{3,4}(?:(?![vV][eE])[A-Za-z]){0,2})
    | (?P<grade>(?i:""" + "|".join(re.escape(g) for g in _GRADES) + r"""))
    | (?P<or>(?i:veya))
    | (?P<and>(?i:ve))
    | (?P<junk>[+,;.]+)
    """,
    re.VERBOSE,
)

# ------------------------------------------------------------------- onarımlar
# Gerçek veride ölçülen bozukluklar. Her onarım Parsed.repairs'e yazılır ki
# arayüz "bu dersin önşart verisi düzeltildi" diye uyarabilsin.
_REPAIRS: list[tuple[str, re.Pattern, str]] = [
    # 'DFH DFH 472' -> 'DFH 472'  (branş kodu iki kez yazılmış, MMD 411E)
    ("yinelenen branş kodu", re.compile(r"\b([A-ZÇĞİÖŞÜ]{2,4})\s+(\1\s*\d{3,4})"), r"\2"),
]
# Başta askıda kalan bağlaç: 'veya (A)veya (B)' -> '(A)veya (B)'
# İlk operand veri girişinde kaybolmuş. Kalanı parse etmek bizi GERÇEKTEN
# olduğundan katı yapar (bir alternatifi kaybederiz), o yüzden işaretliyoruz.
_LEADING_OP = re.compile(r"^\s*(?:veya|ve)\s*(?=[\(A-ZÇĞİÖŞÜ])", re.IGNORECASE)


# Yan yana iki grup, arada bağlaç yok: '(A) (B)veya (C)' (MUH 314)
_JUXTAPOSED = re.compile(r"\)(\s*)\(")


def _repair_juxtaposition(text: str) -> tuple[str, str | None]:
    """Eksik bağlacı, ifadenin BASKIN bağlacından çıkarır.

    Tahmin etmiyoruz: ifadenin geri kalanı tek tip bağlaç kullanıyorsa onu
    koyuyoruz. Karışıksa onarmıyoruz — yanlış cevap vermektense çözemedik demek
    daha doğru.
    """
    if not _JUXTAPOSED.search(text):
        return text, None
    n_or = len(re.findall(r"veya", text, re.IGNORECASE))
    n_and = len(re.findall(r"ve", text, re.IGNORECASE)) - n_or
    if n_or and not n_and:
        op = "veya"
    elif n_and and not n_or:
        op = "ve"
    else:
        return text, None
    return _JUXTAPOSED.sub(rf")\1{op} (", text), f"eksik bağlaç '{op}' olarak tamamlandı"


def repair(text: str) -> tuple[str, list[str]]:
    applied: list[str] = []
    out = text
    m = _LEADING_OP.match(out)
    if m:
        out = out[m.end():]
        applied.append("baştaki askıda bağlaç atıldı (bir alternatif kayıp)")
    for name, pattern, replacement in _REPAIRS:
        new = pattern.sub(replacement, out)
        if new != out:
            out = new
            applied.append(name)
    out, note = _repair_juxtaposition(out)
    if note:
        applied.append(note)
    return out, applied

_NO_PREREQ = {"", "-", "--", "yok", "none", "no", "yoktur"}


@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    pos: int


def tokenize(raw: str) -> list[Token]:
    """Ham metni token'lara ayırır. Tanınmayan karakterde PrereqError atar.

    Sıralama önemli: `veya` `ve`'den ÖNCE denenmeli, yoksa 'veya' -> 've'+'ya'.
    Not token'ı ders kodundan sonra geldiği için `DDveya` doğal olarak
    `DD` + `veya` diye bölünür.
    """
    tokens: list[Token] = []
    i = 0
    while i < len(raw):
        m = _TOKEN_RE.match(raw, i)
        if not m:
            raise PrereqError(f"{i}. karakterde tanınmayan girdi: {raw[i:i + 24]!r}")
        kind = m.lastgroup
        if kind not in ("ws", "junk"):
            value = re.sub(r"\s+", " ", m.group()).strip()
            if kind == "code":
                value = re.sub(r"\s*(\d)", r" \1", value, count=1).upper()
            elif kind in ("grade", "min"):
                value = value.upper()
            else:
                value = value.lower()
            tokens.append(Token(kind, value, i))
        i = m.end()
    return tokens


# ----------------------------------------------------------------------- ağaç
@dataclass
class Node:
    kind: str                       # 'AND' | 'OR' | 'LEAF'
    course: str | None = None
    min_grade: str | None = None
    children: list["Node"] = field(default_factory=list)
    parenthesized: bool = False     # öncelik belirsizliğini saptamak için

    # ------------------------------------------------------------ değerlendir
    def satisfied(self, grades: Mapping[str, str]) -> bool:
        if self.kind == "LEAF":
            got = grades.get(self.course)
            if got is None:
                return False
            need = GRADE_POINTS.get(self.min_grade or DEFAULT_MIN_GRADE, PASSING_MIN)
            have = GRADE_POINTS.get(str(got).upper())
            if have is None:
                return False
            return have >= need
        if self.kind == "AND":
            return all(c.satisfied(grades) for c in self.children)
        return any(c.satisfied(grades) for c in self.children)

    def missing(self, grades: Mapping[str, str]) -> list["Node"]:
        """Karşılanmayan YAPRAKLARI döndürür — arayüzde 'neden alamıyorum' için.

        AND altında karşılanmayan her dal; OR altında hiçbiri karşılanmadıysa
        tüm dallar (herhangi biri yeterli olurdu).
        """
        if self.satisfied(grades):
            return []
        if self.kind == "LEAF":
            return [self]
        out: list[Node] = []
        for child in self.children:
            out.extend(child.missing(grades))
        return out

    def courses(self) -> set[str]:
        if self.kind == "LEAF":
            return {self.course} if self.course else set()
        return set().union(*(c.courses() for c in self.children)) if self.children else set()

    def to_text(self) -> str:
        if self.kind == "LEAF":
            return f"{self.course} MIN {self.min_grade}"
        sep = " ve " if self.kind == "AND" else " veya "
        return "(" + sep.join(c.to_text() for c in self.children) + ")"


@dataclass
class Parsed:
    tree: Node | None
    raw: str
    ambiguous: bool = False         # aynı derinlikte ve/veya karışmış
    note: str | None = None         # parse edilemedi -> sebep
    repairs: list[str] = field(default_factory=list)

    @property
    def unparsable(self) -> bool:
        """Önşart METNİ VAR ama çözemedik. 'Önşartı yok' ile KARIŞTIRILMAMALI."""
        return self.tree is None and self.note is not None


# --------------------------------------------------------------------- parser
class _Parser:
    def __init__(self, tokens: list[Token]):
        self.t = tokens
        self.i = 0
        self.ambiguous = False

    def peek(self) -> Token | None:
        return self.t[self.i] if self.i < len(self.t) else None

    def eat(self, kind: str) -> Token:
        tok = self.peek()
        if tok is None or tok.kind != kind:
            got = "girdi sonu" if tok is None else f"{tok.kind}({tok.value!r})"
            raise PrereqError(f"{kind} bekleniyordu, {got} geldi")
        self.i += 1
        return tok

    # expr := term ( 'veya' term )*
    def expr(self) -> Node:
        nodes = [self.term()]
        seen_or = False
        while (tok := self.peek()) and tok.kind == "or":
            self.i += 1
            nodes.append(self.term())
            seen_or = True
        if seen_or and any(n.kind == "AND" and not n.parenthesized for n in nodes):
            self.ambiguous = True
        return nodes[0] if len(nodes) == 1 else Node("OR", children=nodes)

    # term := factor ( 've' factor )*
    def term(self) -> Node:
        nodes = [self.factor()]
        while (tok := self.peek()) and tok.kind == "and":
            self.i += 1
            nodes.append(self.factor())
        return nodes[0] if len(nodes) == 1 else Node("AND", children=nodes)

    # factor := '(' expr ')' | leaf
    def factor(self) -> Node:
        tok = self.peek()
        if tok is None:
            raise PrereqError("beklenmedik girdi sonu")
        if tok.kind == "lpar":
            self.i += 1
            node = self.expr()
            self.eat("rpar")
            node.parenthesized = True
            return node
        return self.leaf()

    # leaf := CODE [ 'MIN' GRADE ]
    def leaf(self) -> Node:
        code = self.eat("code").value
        grade = DEFAULT_MIN_GRADE
        if (tok := self.peek()) and tok.kind == "min":
            self.i += 1
            grade = self.eat("grade").value
        elif (tok := self.peek()) and tok.kind == "grade":
            grade = self.eat("grade").value          # 'MIN' düşmüş olabilir
        return Node("LEAF", course=code, min_grade=grade)


def parse(raw: str | None) -> Parsed:
    """Ham önşart metnini ağaca çevirir. Asla exception sızdırmaz."""
    original = (raw or "").strip()
    if original.lower() in _NO_PREREQ:
        return Parsed(None, original)
    text, repairs = repair(original)
    try:
        tokens = tokenize(text)
    except PrereqError as exc:
        return Parsed(None, original, note=f"tokenize: {exc}", repairs=repairs)
    if not any(t.kind == "code" for t in tokens):
        # ör. MST 471 / ROS 201: önşart alanına ders ADI yazılmış
        return Parsed(None, original, note="ders kodu içermiyor (elle inceleme gerekir)",
                      repairs=repairs)
    parser = _Parser(tokens)
    try:
        tree = parser.expr()
    except PrereqError as exc:
        return Parsed(None, original, note=f"parse: {exc}", repairs=repairs)
    if parser.peek() is not None:
        tok = parser.peek()
        return Parsed(None, original, repairs=repairs,
                      note=f"artık token: {tok.kind}({tok.value!r}) @{tok.pos}")
    return Parsed(tree, original, ambiguous=parser.ambiguous, repairs=repairs)


# ------------------------------------------------------------- DB'ye yazma
def store_tree(con: sqlite3.Connection, course_code: str, node: Node | None) -> int:
    con.execute("DELETE FROM prereq_node WHERE course_code=?", (course_code,))
    if node is None:
        return 0
    count = 0

    def walk(n: Node, parent: int | None) -> None:
        nonlocal count
        cur = con.execute(
            """INSERT INTO prereq_node(course_code,parent_id,node_type,req_course,min_grade)
               VALUES (?,?,?,?,?)""",
            (course_code, parent, n.kind, n.course, n.min_grade),
        )
        count += 1
        for child in n.children:
            walk(child, cur.lastrowid)

    walk(node, None)
    return count


def load_tree(con: sqlite3.Connection, course_code: str) -> Node | None:
    rows = con.execute(
        """SELECT id,parent_id,node_type,req_course,min_grade FROM prereq_node
           WHERE course_code=? ORDER BY id""", (course_code,)).fetchall()
    if not rows:
        return None
    nodes: dict[int, Node] = {}
    root: Node | None = None
    for row in rows:
        node = Node(row[2], course=row[3], min_grade=row[4])
        nodes[row[0]] = node
        if row[1] is None:
            root = node
        else:
            nodes[row[1]].children.append(node)
    return root


def parse_all(con: sqlite3.Connection) -> dict:
    """Tüm dersleri parse edip prereq_node'a yazar. Rapor döndürür. Idempotent."""
    from .db import now

    from .declared import load_prereq_overrides

    stats = {"total": 0, "with_prereq": 0, "parsed": 0, "failed": 0,
             "ambiguous": 0, "repaired": 0, "nodes": 0, "overridden": 0,
             "failures": []}
    con.execute("DELETE FROM prereq_unparsed")
    con.execute("DELETE FROM prereq_repair")
    # Katalog metninin bozuk olduğu beyan edilen dersler (bkz. denklikler.toml).
    # Beyan, ayrıştırıcıdan ÖNCE devreye girer: kaynak metni değiştirir.
    overrides = load_prereq_overrides()
    rows = con.execute("SELECT code, prereq_raw FROM course").fetchall()
    for code, raw in rows:
        stats["total"] += 1
        ov = overrides.get(code)
        if ov is not None:
            raw = ov["text"]
            stats["overridden"] += 1
            con.execute("INSERT OR IGNORE INTO prereq_repair(course_code,repair) VALUES (?,?)",
                        (code, f"elle beyan: {ov['note']}"))
        result = parse(raw)
        if result.tree is None and result.note is None:
            con.execute("DELETE FROM prereq_node WHERE course_code=?", (code,))
            continue                                   # gerçekten önşartı yok
        stats["with_prereq"] += 1
        for item in result.repairs:
            con.execute("INSERT OR IGNORE INTO prereq_repair(course_code,repair) VALUES (?,?)",
                        (code, item))
        if result.repairs:
            stats["repaired"] += 1
        if result.tree is None:
            stats["failed"] += 1
            stats["failures"].append((code, result.raw[:120], result.note))
            con.execute("DELETE FROM prereq_node WHERE course_code=?", (code,))
            con.execute(
                """INSERT OR REPLACE INTO prereq_unparsed(course_code,prereq_raw,reason,seen_at)
                   VALUES (?,?,?,?)""", (code, result.raw, result.note, now()))
            continue
        stats["parsed"] += 1
        if result.ambiguous:
            stats["ambiguous"] += 1
        stats["nodes"] += store_tree(con, code, result.tree)
    con.commit()
    return stats


def parsed_trees(con: sqlite3.Connection) -> dict[str, Node]:
    """Tüm ağaçları bellekte toplar (öneri motoru için hızlı erişim)."""
    out: dict[str, Node] = {}
    for code, raw in con.execute(
        "SELECT code, prereq_raw FROM course WHERE prereq_raw IS NOT NULL"
    ):
        result = parse(raw)
        if result.tree is not None:
            out[code] = result.tree
    return out


def unlock_counts(trees: Mapping[str, Node]) -> dict[str, int]:
    """Her dersin KAÇ dersin önşartında geçtiği — Faz 5 skorlamasının girdisi."""
    counts: dict[str, int] = {}
    for target, tree in trees.items():
        for course in tree.courses():
            counts[course] = counts.get(course, 0) + 1
    return counts


def depth_of(trees: Mapping[str, Node], course: str, _seen: set[str] | None = None) -> int:
    """Önşart zinciri derinliği: bu dersi alabilmek için kaç kademe gerekiyor.

    ÇAP planları dönemsiz olduğu için (bkz. D2) sıralamayı bu belirleyecek.
    Döngü olursa (veride görülmedi) 0 döner, sonsuz döngüye girmez.
    """
    _seen = _seen or set()
    if course in _seen or course not in trees:
        return 0
    _seen = _seen | {course}
    subs = [depth_of(trees, c, _seen) for c in trees[course].courses()]
    return 1 + max(subs, default=0)
