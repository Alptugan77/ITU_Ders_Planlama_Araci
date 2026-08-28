"""WP1.4 — Ders denklikleri scraper'ı.

Keşif (17 Ağustos 2026):
*   Sayfa GET ile 4 parametre ister ve HEPSİ ZORUNLUDUR:
        DersPlanDenklikleri?ProgramId=..&PlanTipiId=..&PlanId=..&DersBransKoduId=..
    Eksik parametre -> "Ders denklik bilgisi bulunamadı." (alert)
*   Kademeli menü uçları (POST, JSON, anahtar alan: objectId):
        GetPlanTipleriByProgramId          {programId}
        GetDersPlanlariByProgramIdAndPlanTipiId {programId, planTipiId}
        GetDersBransKodlariByPlanId        {planId}
*   PlanId değerleri DersPlanDetay id'leri ile AYNIDIR (ör. 2229).
*   ★ Veri seyrek: HTAE (248) için 39 kombinasyonun tamamı boş; BLG ÇAP (2229) boş.
    Bu yüzden scraper "bulamadı"yı normal karşılar, hata saymaz.

Denklik metni yönlü ve çok kaynaklı olabilir:
    "KIM 211E ve KIM 212 dersleri alınır ve başarılırsa KIM 206'ya eşdeğer sayılır"
    => {KIM 211E, KIM 212} -> KIM 206
"""
from __future__ import annotations

import re
import sqlite3

from selectolax.parser import HTMLParser

from .. import config, db
from ..http import ObsClient

NOT_FOUND = re.compile(r"bulunamad", re.IGNORECASE)
APPROVAL_RE = re.compile(r"(yönetim kurulu|dilekçe|onay|approval)", re.IGNORECASE)

# ★ DersPlanDenklikleri hücreleri "KOD Ad" biçiminde ve kod isme YAPIŞIK
#   olabiliyor ("BLG 202Numerical Methods in CE"). Eski `\b...\b` regex'i burada
#   HİÇ eşleşmiyordu (rakam ile ismin ilk harfi arasında sınır yok) — yani her
#   satır sessizce düşüyordu; Ağustos'ta "0 denklik" görülmesinin bir sebebi de
#   buydu. Kodu satır BAŞINDAN alıyoruz; ismin baş BÜYÜK harfini ("...202N…") dil
#   eki ("...202E") sanmamak için: tek harf ancak ardından KÜÇÜK harf gelmiyorsa
#   koda dahil. OBS'nin bu sayfası kodları taban (E'siz) yazıyor — dil eşleştirme
#   sonra `rules`/`server._dil_esleri` katmanında yapılıyor.
_LEAD = re.compile(r"^\s*([A-ZÇĞİÖŞÜ]{2,4})\s*(\d{3,4})([A-Z]?)")


def _lead_code(text: str) -> str | None:
    """'BLG 202Numerical…' -> 'BLG 202'; 'MAT 210 Müh. Mat.' -> 'MAT 210'."""
    m = _LEAD.match(text or "")
    if not m:
        return None
    pre, num, suf = m.group(1), m.group(2), m.group(3)
    if suf and text[m.end():m.end() + 1].islower():
        suf = ""                       # 'N' aslında ismin baş harfi (Numerical)
    return f"{pre} {num}{suf}"


def plan_types(client: ObsClient, program_id: int) -> list[dict]:
    return _objects(client.post_json(config.EP["eq_plan_types"], {"programId": program_id}))


def plans(client: ObsClient, program_id: int, plan_type_id: int) -> list[dict]:
    return _objects(client.post_json(
        config.EP["eq_plans"], {"programId": program_id, "planTipiId": plan_type_id}))


def branches(client: ObsClient, plan_id: int) -> list[dict]:
    return _objects(client.post_json(config.EP["eq_branches"], {"planId": plan_id}))


def _objects(payload) -> list[dict]:
    return payload if isinstance(payload, list) else []


def program_options(html: str, undergrad_only: bool = True) -> list[tuple[int, str]]:
    """Denklik sayfasının Program açılır menüsünden (id, ad) listesi.

    ★ Program LİSTESİ sayfanın kendisinde (`select#programId`); cascade uçları
    zaten programId istiyor ama listeyi vermiyor. `undergrad_only`: adı
    'Undergraduate' içerenler (yüksek lisans/doktora hariç) — denklikler
    lisans planlarında. (Ölçüldü: 339 programın 93'ü lisans.)
    """
    sel = HTMLParser(html).css_first("select#programId, select[name=programId]")
    if sel is None:
        return []
    out = []
    for o in sel.css("option"):
        val = (o.attributes.get("value") or "").strip()
        name = o.text(strip=True)
        if not val.isdigit():
            continue
        if undergrad_only and "Undergraduate" not in name:
            continue
        out.append((int(val), name))
    return out


def all_program_ids(client: ObsClient, undergrad_only: bool = True) -> list[tuple[int, str]]:
    return program_options(client.get(config.EP["eq_page"], {}), undergrad_only)


def sweep_program(client: ObsClient, con: sqlite3.Connection, program_id: int,
                  max_plans: int | None = None, seen: set | None = None) -> tuple[int, int]:
    """Bir program için tüm (plan tipi, plan, branş) kombinasyonlarını tarar.

    `seen`: programlar arası tekilleştirme için paylaşılan (hedef, kaynak)
    kümesi — aynı denklik iki programın sayfasında da çıkabiliyor.
    Dönüş: (denenen kombinasyon sayısı, bulunan denklik sayısı)
    """
    tried = found = 0
    for pt in plan_types(client, program_id):
        pt_id = pt.get("objectId")
        plan_list = plans(client, program_id, pt_id)
        if max_plans:
            plan_list = plan_list[-max_plans:]
        for pl in plan_list:
            pl_id = pl.get("objectId")
            for br in branches(client, pl_id):
                tried += 1
                found += _fetch_one(client, con, program_id, pt_id, pl_id,
                                    br.get("objectId"), seen=seen)
    con.commit()
    return tried, found


def sweep_all(client: ObsClient, con: sqlite3.Connection, max_plans: int | None = 1,
              undergrad_only: bool = True, progress=None) -> tuple[int, int, int]:
    """TÜM (lisans) programların denkliklerini tarar — kullanıcı isteği
    28.08.2026: *"diğer programlar için de denklikleri kontrol edip uygun ders
    var mı diye baksın"*.

    Kapsamlı ama YAVAŞ (çok istek). `max_plans=1`: her plan tipinin yalnız EN
    SON planı (eski sürümler denklikleri büyük ölçüde tekrar eder). Programlar
    arası tekilleştirme paylaşılan `seen` ile. Bir programın hatası ötekini
    kesmesin diye tek tek yutuluyor. Dönüş: (program, kombinasyon, denklik).
    """
    progs = all_program_ids(client, undergrad_only)
    if progress:
        progress(f"🌍 {len(progs)} lisans programı taranacak (yavaş olabilir)…")
    seen: set = set()
    tried = found = 0
    for i, (pid, name) in enumerate(progs, 1):
        try:
            t, f = sweep_program(client, con, pid, max_plans=max_plans, seen=seen)
        except Exception as exc:                       # noqa: BLE001
            if progress:
                progress(f"  ⚠ {name} ({pid}): {exc}")
            continue
        tried += t
        found += f
        if progress and (f or i % 25 == 0):
            progress(f"  [{i}/{len(progs)}] {name}: +{f}")
    return len(progs), tried, found


def _fetch_one(client: ObsClient, con: sqlite3.Connection, program_id, plan_type_id,
               plan_id, branch_id, plan_type_name: str = "", seen: set | None = None) -> int:
    params = {"ProgramId": program_id, "PlanTipiId": plan_type_id,
              "PlanId": plan_id, "DersBransKoduId": branch_id}
    html = client.get(config.EP["eq_page"], params)
    if NOT_FOUND.search(html):
        return 0
    url = config.EP["eq_page"] + "?" + "&".join(f"{k}={v}" for k, v in params.items())
    return parse_table(con, html, plan_id, url, seen=seen)


def parse_table(con: sqlite3.Connection, html: str, plan_id: int | None, url: str,
                seen: set | None = None) -> int:
    """DersPlanDenklikleri tablosunu yönlü denkliğe çevirir.

    ★ İki sütun: **'Course At The Plan'** = HEDEF (plandaki ders), **'Equivalent
    Course'** = ``<br>`` ile ayrılmış ALTERNATİFLER. Her alternatif BAĞIMSIZ:
    birini alınca hedef sağlanır (OR). Bu yüzden her alternatif AYRI bir denklik
    satırı olur — hepsi tek denkliğin AND kaynağı DEĞİL (öyle saklasak "hepsini
    al" derdi). Ham satır ``note_raw``a yazılıyor ki yanlış ayrıştırma görülebilsin.

    HTTP'den ayrı bir işlev: gerçek kayıtlı sayfalarla doğrudan test edilebiliyor.
    """
    table = HTMLParser(html).css_first("table")
    if table is None:
        return 0
    rows = table.css("tbody tr") or table.css("tr")
    n = 0
    if seen is None:
        seen = set()                       # tek sayfa için yerel; sweep paylaşır
    for row in rows:
        tds = row.css("td")
        if len(tds) < 2:
            continue                                  # başlık / boş satır
        target = _lead_code(tds[0].text(strip=True))
        if not target:
            continue
        # ★ Hücreyi `separator="\n"` ile oku: <br> satır sonuna dönüşsün. Ham
        #   `text(strip=True)` alternatifleri BİTİŞİK verir ("…PythonBIL 101")
        #   ve kod çıkarımı sessizce bozulur (normalize.py'deki uyarı).
        for ln in tds[1].text(separator="\n").split("\n"):
            src = _lead_code(ln.strip())
            if not src or src == target or (target, src) in seen:
                continue
            seen.add((target, src))
            raw = f"{tds[0].text(strip=True)} ≡ {ln.strip()}"
            n += _store_pair(con, target, src, plan_id, url, raw)
    con.commit()
    return n


def _store_pair(con: sqlite3.Connection, target: str, source: str,
                plan_id: int | None, url: str, raw: str) -> int:
    """Tek (hedef ← kaynak) denkliği. Kaynağı alınca hedef sağlanır."""
    confidence = "requires_approval" if APPROVAL_RE.search(raw) else "official"
    # ÖİDB notu: "Bölüm tarafından belirlenmiş ders denklikleri, gerektiği
    # durumlarda ÇAP ders planı için de geçerlidir." -> varsayılan 1; ÇAP'ı açıkça
    # dışlayan metin varsa 0.
    applies_to_cap = 0 if re.search(r"ÇAP.{0,20}(geçerli değil|hariç)", raw, re.IGNORECASE) else 1
    cur = con.execute(
        """INSERT INTO equivalence(target_course,target_plan_id,applies_to_cap,confidence,
                                   note_raw,source_url,scraped_at)
           VALUES (?,?,?,?,?,?,?)""",
        (target, plan_id, applies_to_cap, confidence, raw, url, db.now()),
    )
    con.execute(
        "INSERT OR IGNORE INTO equivalence_source(equivalence_id,course_code,min_grade)"
        " VALUES (?,?,?)", (cur.lastrowid, source, _min_grade(raw)),
    )
    return 1


def _min_grade(text: str) -> str:
    m = re.search(r"\bMIN\s*([A-F]{2})\b", text, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    return "DD" if re.search(r"başarıl|geç(er|ilir)", text, re.IGNORECASE) else "DD"
