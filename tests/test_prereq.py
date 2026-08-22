"""Faz 2 — önşart parser'ı. Vakaların çoğu gerçek OBS verisinden alınmıştır."""
import pytest

from itucap import prereq as P


# ------------------------------------------------------------------ tokenizer
def kinds(text):
    return [t.kind for t in P.tokenize(text)]


def test_glued_grade_and_conjunction():
    """'DDveya' bitişik yazılıyor — gerçek veride 8.923 kez."""
    assert kinds("MAT 102 MIN DDveya MAT 102E MIN DD") == [
        "code", "min", "grade", "or", "code", "min", "grade"]


def test_glued_paren_and_conjunction():
    assert kinds("(MAT 101 MIN DD)veya (FIZ 102 MIN DD)") == [
        "lpar", "code", "min", "grade", "rpar", "or", "lpar", "code", "min", "grade", "rpar"]


def test_veya_before_ve():
    """'veya' önce denenmeli, yoksa 've'+'ya' diye bölünür."""
    assert kinds("MAT 101veya FIZ 102") == ["code", "or", "code"]
    assert kinds("MAT 101ve FIZ 102") == ["code", "and", "code"]


def test_code_suffix_does_not_eat_conjunction():
    """'ECN 211EveyaECN 211' — 'E' kod eki, 'v' bağlacın başı (END 476E)."""
    toks = P.tokenize("ECN 211EveyaECN 211")
    assert [t.value for t in toks] == ["ECN 211E", "veya", "ECN 211"]


def test_lowercase_code_suffix():
    """'IEB 322e' — küçük harfli ek gerçek veride var (IEB 4901E)."""
    toks = P.tokenize("IEB 322e MIN DD")
    assert toks[0].value == "IEB 322E"          # normalize edilir


def test_trailing_junk_tolerated():
    """CEN 312E'nin sonunda başıboş '+' var."""
    assert P.parse("CEN 223E MIN DD+").tree is not None


def test_unknown_input_raises():
    with pytest.raises(P.PrereqError):
        P.tokenize("Türkçe")


# --------------------------------------------------------------------- parser
def test_simple_leaf():
    tree = P.parse("MAT 103E MIN CC").tree
    assert tree.kind == "LEAF" and tree.course == "MAT 103E" and tree.min_grade == "CC"


def test_default_min_grade_is_dd():
    assert P.parse("MAT 103E").tree.min_grade == "DD"


def test_or_group():
    tree = P.parse("(MAT 102 MIN DDveya MAT 102E MIN DD)").tree
    assert tree.kind == "OR" and len(tree.children) == 2


def test_real_world_nested():
    raw = (" (MAT 102 MIN DDveya MAT 102E MIN DD)veya "
           "(MAT 104 MIN DDveya MAT 104E MIN DD) ")
    tree = P.parse(raw).tree
    assert tree.kind == "OR"
    assert tree.courses() == {"MAT 102", "MAT 102E", "MAT 104", "MAT 104E"}


def test_and_binds_tighter_than_or():
    tree = P.parse("MAT 101ve FIZ 102veya KIM 103").tree
    assert tree.kind == "OR"
    assert tree.children[0].kind == "AND"


def test_ambiguity_is_flagged_not_hidden():
    """Gerçek veride 0/4628 ama gelirse sessizce yutulmamalı."""
    assert P.parse("MAT 101ve FIZ 102veya KIM 103").ambiguous is True
    assert P.parse("(MAT 101ve FIZ 102)veya KIM 103").ambiguous is False


def test_no_prereq_variants():
    for text in ["", "  ", "Yok", "yok", "-", None]:
        result = P.parse(text)
        assert result.tree is None and result.note is None
        assert result.unparsable is False


# ------------------------------------------------------------------ onarımlar
def test_repair_leading_dangling_operator():
    """'veya (A)veya (B)' — ilk operand veri girişinde kaybolmuş (BLG 438E)."""
    result = P.parse("veya (AKM 204 MIN DDveya AKM 204E MIN DD)")
    assert result.tree is not None
    assert any("askıda bağlaç" in r for r in result.repairs)


def test_repair_duplicated_branch_code():
    """'DFH DFH 472' -> 'DFH 472' (MMD 411E)."""
    result = P.parse("(DFH 472E MIN DDveya DFH DFH 472 MIN DD)")
    assert result.tree is not None
    assert result.tree.courses() == {"DFH 472E", "DFH 472"}


def test_repair_juxtaposition_uses_dominant_operator():
    """'(A) (B)veya (C)' — eksik bağlaç baskın bağlaçtan tamamlanır (MUH 314)."""
    result = P.parse("(MAT 101 MIN DD) (FIZ 102 MIN DD)veya (KIM 103 MIN DD)")
    assert result.tree is not None
    assert result.tree.kind == "OR"


def test_juxtaposition_not_repaired_when_mixed():
    """Bağlaçlar karışıksa TAHMİN ETME — çözemedik demek daha doğru."""
    result = P.parse("(MAT 101 MIN DD) (FIZ 102 MIN DD)veya (KIM 103 MIN DD)ve (BIL 104 MIN DD)")
    assert result.tree is None
    assert result.unparsable is True


# ------------------------------------------------------------ değerlendirme
def test_grade_threshold():
    tree = P.parse("MAT 103E MIN CC").tree
    assert tree.satisfied({"MAT 103E": "BB"}) is True     # BB(3.0) >= CC(2.0)
    assert tree.satisfied({"MAT 103E": "CC"}) is True     # eşit
    assert tree.satisfied({"MAT 103E": "DD"}) is False    # DD(1.0) < CC(2.0)
    assert tree.satisfied({}) is False


def test_min_ff_means_course_was_taken():
    """MIN FF = 'dersi almış olmak yeter', başarı şartı yok."""
    tree = P.parse("DNK 201 MIN FF").tree
    assert tree.satisfied({"DNK 201": "FF"}) is True
    assert tree.satisfied({"DNK 201": "AA"}) is True
    assert tree.satisfied({}) is False


def test_bl_pass_fail_grade():
    """BL (Başarılı) kredisiz derslerde geçer sayılır (MAK 199)."""
    tree = P.parse("(MAK 198E MIN BLveya MAK 198 MIN BL)").tree
    assert tree.satisfied({"MAK 198": "BL"}) is True
    assert tree.satisfied({"MAK 198": "FF"}) is False


def test_and_or_semantics():
    tree = P.parse("(MAT 101 MIN DDveya FIZ 102 MIN DD)ve KIM 103 MIN DD").tree
    assert tree.satisfied({"MAT 101": "DD", "KIM 103": "DD"}) is True
    assert tree.satisfied({"FIZ 102": "DD", "KIM 103": "DD"}) is True
    assert tree.satisfied({"MAT 101": "DD"}) is False        # C eksik
    assert tree.satisfied({"KIM 103": "DD"}) is False        # ikisi de eksik


def test_missing_explains_or_branches():
    """OR dalında hiçbiri yoksa TÜM alternatifler gösterilmeli."""
    tree = P.parse("(MAT 101 MIN DDveya FIZ 102 MIN DD)ve KIM 103 MIN DD").tree
    missing = {n.course for n in tree.missing({"KIM 103": "AA"})}
    assert missing == {"MAT 101", "FIZ 102"}
    assert tree.missing({"MAT 101": "AA", "KIM 103": "AA"}) == []


# ------------------------------------------------------------------ yardımcı
def test_unlock_counts_and_depth():
    trees = {
        "FIZ 200": P.parse("MAT 100 MIN DD").tree,
        "KIM 300": P.parse("FIZ 200 MIN DD").tree,
        "BIL 300": P.parse("MAT 100 MIN DD").tree,
    }
    assert P.unlock_counts(trees)["MAT 100"] == 2
    assert P.depth_of(trees, "KIM 300") == 2
    assert P.depth_of(trees, "MAT 100") == 0


def test_depth_survives_cycles():
    trees = {"MAT 100": P.parse("FIZ 200 MIN DD").tree, "FIZ 200": P.parse("MAT 100 MIN DD").tree}
    assert P.depth_of(trees, "MAT 100") >= 0        # sonsuz döngüye girmez


def test_to_text_roundtrip():
    tree = P.parse("(MAT 101 MIN DDveya FIZ 102 MIN CC)ve KIM 103 MIN DD").tree
    assert P.parse(tree.to_text()).tree.courses() == tree.courses()
