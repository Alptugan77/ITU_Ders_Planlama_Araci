"""WP1.8 — Veri kalite kontrolleri.

Sessiz veri bozulması bu projede en tehlikeli hata tipi: yanlış öneri, doğru
görünen bir arayüzle sunulur. Bu yüzden kontroller pipeline'ın SONUNDA her
zaman çalışır ve rapor basar.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from . import db
from .normalize import uncategorised_labels, unmatched_labels


@dataclass
class Finding:
    check_id: str
    severity: str      # 'error' | 'warn' | 'info'
    detail: str


CHECKS: list = []


def check(check_id: str, severity: str = "error"):
    def wrap(fn):
        CHECKS.append((check_id, severity, fn))
        return fn
    return wrap


@check("orphan_slot_course", "warn")
def _orphan_slot_course(con):
    rows = con.execute(
        """SELECT ps.course_code, COUNT(*) n FROM plan_slot ps
           LEFT JOIN course c ON c.code = ps.course_code
           WHERE ps.course_code IS NOT NULL AND c.code IS NULL
           GROUP BY ps.course_code ORDER BY n DESC LIMIT 15"""
    ).fetchall()
    if rows:
        sample = ", ".join(f"{r[0]}({r[1]})" for r in rows)
        return f"course tablosunda karşılığı olmayan plan dersi: {sample}"


@check("orphan_pool_option", "warn")
def _orphan_pool_option(con):
    n = con.execute(
        """SELECT COUNT(*) FROM pool_option po
           LEFT JOIN course c ON c.code = po.course_code WHERE c.code IS NULL"""
    ).fetchone()[0]
    if n:
        return f"{n} havuz seçeneğinin ders karşılığı yok"


@check("empty_pool", "warn")
def _empty_pool(con):
    """Boş seçmeli havuzlar — SEBEBİYLE birlikte.

    18.08.2026: havuz hücresi kodu ve adı birlikte taşıdığı için tüm havuzlar
    sessizce boş kalmıştı; seçmeli dersler 'sayılmıyor' görünüyordu.

    ★ 23.08.2026: bu kontrol grupId'li her boş havuza "PARSE HATASI" diyordu.
    Ölçtük — grup 11083'ün arşivlenmiş cevabında hiç `<table>` yok, yani OBS
    boş sayfa döndürüyor. Kaynağın eksiğini kendi hatamız gibi göstermek,
    düzeltilmesi en zor yalan türü; `pool_status` artık ikisini ayırıyor.
    """
    total, empty = con.execute(
        """SELECT COUNT(*),
                  SUM(NOT EXISTS (SELECT 1 FROM pool_option po WHERE po.slot_id = ps.id))
           FROM plan_slot ps WHERE ps.slot_kind='ELECTIVE_POOL'"""
    ).fetchone()
    if not total or not empty:
        return None
    durum = dict(con.execute(
        """SELECT COALESCE(ps.pool_status,'?'), COUNT(*) FROM plan_slot ps
           WHERE ps.slot_kind='ELECTIVE_POOL' AND ps.pool_group_id IS NOT NULL
             AND NOT EXISTS (SELECT 1 FROM pool_option po WHERE po.slot_id = ps.id)
           GROUP BY 1"""))
    parts = [f"{empty}/{total} seçmeli havuz BOŞ"]
    if durum.get("no_codes"):
        parts.append(f"★ {durum['no_codes']} tanesinde tablo VARDI ama kod "
                     f"çıkaramadık — PARSE HATASI")
    if durum.get("no_table"):
        parts.append(f"{durum['no_table']} tanesinde OBS ders tablosu olmayan "
                     f"sayfa döndürdü (kaynakta boş)")
    if durum.get("?"):
        parts.append(f"{durum['?']} tanesi bu tarayıcı sürümünden önce "
                     f"çekilmiş (sebep kaydedilmemiş) — `make all-plans` netleştirir")
    return " · ".join(parts)


@check("too_many_terms")
def _too_many_terms(con):
    rows = con.execute(
        """SELECT plan_id, MAX(term_no) t FROM plan_slot
           WHERE term_no IS NOT NULL GROUP BY plan_id HAVING t > 12"""
    ).fetchall()
    if rows:
        return f"8'den (tolerans 12) fazla dönemli plan: {[r[0] for r in rows][:10]}"


@check("overfull_lesson", "info")
def _overfull(con):
    n = con.execute(
        "SELECT COUNT(*) FROM lesson WHERE enrolled > capacity AND capacity > 0"
    ).fetchone()[0]
    if n:
        return f"{n} şubede yazılan > kontenjan (normal olabilir, bilgi amaçlı)"


@check("orphan_equivalence", "warn")
def _orphan_equivalence(con):
    n = con.execute(
        """SELECT COUNT(*) FROM equivalence e
           LEFT JOIN course c ON c.code = e.target_course WHERE c.code IS NULL"""
    ).fetchone()[0]
    if n:
        return f"{n} denklikte hedef ders bulunamadı"


@check("cap_plan_present")
def _cap_plan_present(con):
    n = con.execute("SELECT COUNT(*) FROM plan WHERE plan_type='cap'").fetchone()[0]
    if not n:
        return "Hiç ÇAP planı yüklenmemiş (Faz 1 bitiş kriteri #2 sağlanmıyor)"


@check("cap_plan_size")
def _cap_plan_size(con, mine=()):
    """Sayfada ders tablosu VARDI ama slot üretilmedi -> parse anomalisi.

    ★ KAPSAM (21.08.2026). Bu kontrol tek bir ÇAP planı varken yazılmıştı:
    o plan bozuksa araç güvenilmezdi, `error` doğruydu. `--all-programs`
    ile veritabanında **1081 plan** var; başka bir bölümün planındaki
    anomali senin sonuçlarını etkilemiyor ve senin yapabileceğin bir şey
    yok — ama `make`'i düşürüyordu.

    Yeni kural: anomali **senin kullandığın** planlardaysa `error`, değilse
    `warn`. Kontrolün kendisi aynı, ciddiyeti kapsama bağlı.
    """
    rows = con.execute(
        """SELECT p.id, p.program_code, COUNT(ps.id) n FROM plan p
           LEFT JOIN plan_slot ps ON ps.plan_id = p.id
           WHERE p.plan_type IN ('cap','yandal') AND p.has_course_table = 1
           GROUP BY p.id HAVING n = 0 OR n > 60"""
    ).fetchall()
    if not rows:
        return None
    mine = {m for m in mine if m}
    bad_mine = [r for r in rows if r[0] in mine]
    empty = [r for r in rows if r[2] == 0]
    huge = [r for r in rows if r[2] > 60]

    def sample(items):
        return ", ".join(f"{r[0]}({r[1] or '?'}: {r[2]} slot)" for r in items[:6])

    if bad_mine:
        return (f"★ SENİN planında parse hatası: {sample(bad_mine)} — "
                f"sonuçlar güvenilmez, `make plan-info ID={bad_mine[0][0]}` ile bak")
    parts = []
    if empty:
        parts.append(f"{len(empty)} plan boş çıktı ({sample(empty)})")
    if huge:
        parts.append(f"{len(huge)} plan 60'tan fazla slot ({sample(huge)})")
    return ("başka programların planlarında anomali — seni etkilemiyor: "
            + "; ".join(parts))


@check("dropped_plan_rows")
def _dropped_plan_rows(con, mine=()):
    """Sayfadaki satır sayısı ile yazılan slot sayısını KARŞILAŞTIRIR.

    ★ 22.08.2026 — bu kontrol olmasaydı ELK ÇAP planı 28 satırın 5'iyle
    "tamam" görünmeye devam ederdi. `position` her satır için artıyor, slot
    ise yalnız ayrıştırılabilenler için yazılıyor; ikisi arasındaki fark tam
    olarak SESSİZCE DÜŞEN satır sayısıdır.

    Bu, tarayıcıdan bağımsız bir kanıt: eski bir veritabanında da çalışır,
    tarayıcı düzeltildikten sonra da sıfır kalmalıdır.
    """
    rows = con.execute(
        """SELECT p.id, p.plan_type,
                  COALESCE(p.host_program_code || '_', '') || p.program_code AS ad,
                  x.satir - x.slot AS dusen
           FROM plan p JOIN (SELECT plan_id, COUNT(*) slot, MAX(position) + 1 satir
                             FROM plan_slot WHERE position IS NOT NULL
                             GROUP BY plan_id) x ON x.plan_id = p.id
           WHERE x.satir > x.slot ORDER BY dusen DESC"""
    ).fetchall()
    if not rows:
        return None
    mine = {m for m in mine if m}
    toplam = sum(r["dusen"] for r in rows)
    ornek = ", ".join(f"{r['ad']}({r['dusen']})" for r in rows[:6])
    benim = [r for r in rows if r["id"] in mine]
    if benim:
        return (f"★ SENİN planında {sum(r['dusen'] for r in benim)} satır ayrıştırılamadı "
                f"({', '.join(str(r['id']) for r in benim)}) — plan EKSİK görünüyor, "
                f"`make plan-info ID={benim[0]['id']}` ile bak")
    return (f"{len(rows)} planda toplam {toplam} satır ayrıştırılamadı (seni etkilemiyor): "
            f"{ornek}")


@check("plan_credit_mismatch")
def _plan_credit_mismatch(con, mine=()):
    """Sayfanın yazdığı 'Toplam Kredi' ile bizim topladığımız kredi.

    ★ 23.08.2026 — ayrıştırmadan BAĞIMSIZ bir çıpa. Düşen satır kontrolü
    "az yazdık"ı yakalıyor; bu kontrol "ÇOK yazdık"ı yakalıyor. İkincisi
    daha sinsi: eksik veri eksik görünür, uydurulmuş veri DOĞRU görünür.
    Yandal planlarında yardımcı tablolar zorunlu ders sanılıyordu ve
    22,5 kredilik plan 43 ders topluyordu — bu kontrol olsaydı ilk taramada
    yakalanırdı.

    ⚠️ Sayfa toplam yazmamışsa KARŞILAŞTIRMA YOK. Bilinmeyeni 0 sayıp
    "tutmuyor" demek, olmayan bir hata uydurmak olurdu.
    """
    # ★ 23.08.2026: kredi ARALIK olabiliyor ("2 / 2,5 / 3"). Tek sayı gibi
    # toplayınca 65 planda sahte "tutmuyor" uyarısı çıkıyordu — kontrolün
    # kendisi yanlış alarm üretiyordu, ki bu onu okunmaz hâle getirir.
    # Artık ALT ve ÜST toplam hesaplanıyor; ilan edilen kredi bu aralığın
    # içindeyse tutuyor demektir.
    rows = con.execute(
        """SELECT p.id, coalesce(p.host_program_code||'_','')||p.program_code ad,
                  p.declared_credits ilan,
                  ROUND(SUM(coalesce(s.credits_min, s.credits, 0)),2) alt,
                  ROUND(SUM(coalesce(s.credits_max, s.credits, 0)),2) ust
           FROM plan p JOIN plan_slot s ON s.plan_id=p.id
           WHERE p.declared_credits IS NOT NULL AND p.declared_credits > 0
           GROUP BY p.id
           HAVING p.declared_credits < alt - (0.5 + 0.1*p.declared_credits)
               OR p.declared_credits > ust + (0.5 + 0.1*p.declared_credits)
           ORDER BY ABS(ust - p.declared_credits) DESC"""
    ).fetchall()
    if not rows:
        return None
    mine = {m for m in mine if m}
    benim = [r for r in rows if r["id"] in mine]
    hedef = benim or rows

    def ornek(items):
        return ", ".join(
            f"{r['id']}({r['ad']}: "
            + (f"{r['alt']:g} kredi" if r["alt"] == r["ust"]
               else f"{r['alt']:g}–{r['ust']:g} kredi")
            + f" topladık, sayfa {r['ilan']:g} diyor)" for r in items[:4])

    if benim:
        return (f"★ SENİN planında kredi tutmuyor: {ornek(benim)} — "
                f"ayrıştırmada bir şey yanlış, `make plan-info ID={benim[0]['id']}`")
    return (f"{len(rows)} planda kredi toplamı sayfayla tutmuyor "
            f"(seni etkilemiyor): {ornek(hedef)}")


@check("upstream_empty_plans", "info")
def _upstream_empty(con):
    """Sayfada hiç ders tablosu yoktu -> kaynakta boş, bizim hatamız değil."""
    rows = con.execute(
        "SELECT id, title FROM plan WHERE has_course_table = 0 ORDER BY id"
    ).fetchall()
    if rows:
        sample = ", ".join(str(r[0]) for r in rows[:10])
        return f"{len(rows)} plan OBS'de boş yayınlanmış (ders tablosu yok): {sample}"


@check("lessons_present", "warn")
def _lessons_present(con):
    n = con.execute("SELECT COUNT(*) FROM lesson").fetchone()[0]
    if n < 2000:
        return f"lesson tablosu düşük ({n}). Dönem başında ders programı henüz yayınlanmamış olabilir."


@check("meeting_sanity")
def _meeting_sanity(con):
    n = con.execute(
        "SELECT COUNT(*) FROM lesson_meeting WHERE start_min >= end_min OR day_of_week NOT BETWEEN 1 AND 7"
    ).fetchone()[0]
    if n:
        return f"{n} oturumda saat/gün tutarsız"


@check("prereq_parse_rate")
def _prereq_parse_rate(con):
    """Parse oranı düşerse OBS formatı değişmiş demektir — sessiz kalma."""
    total = con.execute(
        """SELECT COUNT(*) FROM course
           WHERE prereq_raw IS NOT NULL AND TRIM(prereq_raw) NOT IN ('','-','Yok','yok')"""
    ).fetchone()[0]
    if not total:
        return None
    failed = con.execute("SELECT COUNT(*) FROM prereq_unparsed").fetchone()[0]
    rate = 100 * (total - failed) / total
    if rate < 99.0:
        return f"önşart parse oranı %{rate:.2f} (eşik %99) — {failed}/{total} çözülemedi"


@check("prereq_unparsed", "info")
def _prereq_unparsed(con):
    rows = con.execute(
        "SELECT course_code FROM prereq_unparsed ORDER BY course_code").fetchall()
    if rows:
        return (f"{len(rows)} dersin önşartı çözülemedi (motor 'BİLİNMİYOR' döner, "
                f"'önşartı yok' demez): {', '.join(r[0] for r in rows[:10])}")


@check("prereq_repaired", "info")
def _prereq_repaired(con):
    n = con.execute("SELECT COUNT(DISTINCT course_code) FROM prereq_repair").fetchone()[0]
    if n:
        return f"{n} dersin önşart metni onarılarak parse edildi (kaynakta bozukluk var)"


@check("prereq_orphan_target", "warn")
def _prereq_orphan(con):
    n = con.execute(
        """SELECT COUNT(DISTINCT req_course) FROM prereq_node p
           WHERE p.node_type='LEAF' AND p.req_course IS NOT NULL
             AND NOT EXISTS (SELECT 1 FROM course c WHERE c.code = p.req_course)"""
    ).fetchone()[0]
    if n:
        return f"{n} önşart dersi course tablosunda yok (kapatılmış ders olabilir)"


@check("unmatched_pool_labels", "warn")
def _unmatched(con):
    """★ Kategori TAŞIYAN ama çözemediğimiz etiketler — BİZİM eksiğimiz.

    23.08.2026'ya kadar bu kontrol "kaynakta kategori yok" olanları da
    sayıyordu (226 etiket) ve rakam düzeltilebilir 66'yı görünmez kılıyordu.
    Düzeltilemeyecek bir şeyi uyarı diye göstermek, uyarıyı okunmaz yapar.
    """
    if unmatched_labels:
        uniq = list(dict.fromkeys(unmatched_labels))
        return (f"{len(uniq)} havuz etiketi kategori KODU taşıyor ama "
                f"çözülemedi: {uniq[:8]}")


@check("uncategorised_pool_labels", "info")
def _uncategorised(con):
    """Kaynakta kategori YOK ("Stüdyo IV", "Temel Meslek II", "Selective").

    Düzeltilecek bir şey yok — kategori uydurmak veri uydurmak olurdu.
    Bilgi olarak duruyor çünkü kategori sayaçlarındaki boşluğu açıklıyor.
    """
    if uncategorised_labels:
        uniq = list(dict.fromkeys(uncategorised_labels))
        return (f"{len(uniq)} havuz etiketinde kaynakta kategori yok "
                f"(kategori sayaçlarına girmiyorlar): {uniq[:6]}")


def run(con: sqlite3.Connection, mine: tuple = ()) -> list[Finding]:
    """Kalite kontrolleri.

    `mine` = kullanıcının kendi plan id'leri. Bazı kontroller ciddiyeti buna
    göre ayarlıyor: kendi planındaki bozukluk `error`, başkasınınki `warn`.
    """
    stamp = db.now()
    findings: list[Finding] = []
    for check_id, severity, fn in CHECKS:
        # Kontroller iki imzadan birini kullanabilir: fn(con) ya da fn(con, mine)
        detail = fn(con, mine) if fn.__code__.co_argcount > 1 else fn(con)
        if detail:
            if check_id in ("cap_plan_size", "dropped_plan_rows", "plan_credit_mismatch") \
                    and "SENİN" not in detail:
                severity = "warn"        # başka programın planı seni düşürmesin
            findings.append(Finding(check_id, severity, detail))
            con.execute(
                "INSERT INTO quality_finding(run_at,check_id,severity,detail) VALUES (?,?,?,?)",
                (stamp, check_id, severity, detail),
            )
    con.commit()
    return findings


def format_report(findings: list[Finding]) -> str:
    if not findings:
        return "✅ Tüm kalite kontrolleri yeşil."
    icon = {"error": "❌", "warn": "⚠️ ", "info": "ℹ️ "}
    lines = [f"{icon.get(f.severity, '•')} [{f.check_id}] {f.detail}" for f in findings]
    n_err = sum(1 for f in findings if f.severity == "error")
    lines.append(f"\n{len(findings)} bulgu ({n_err} hata).")
    return "\n".join(lines)
