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
from ..normalize import normalize_course_code

NOT_FOUND = re.compile(r"bulunamad", re.IGNORECASE)
COURSE_RE = re.compile(r"\b([A-ZÇĞİÖŞÜ]{2,4})\s?(\d{3,4}[A-Z]{0,2})\b")
APPROVAL_RE = re.compile(r"(yönetim kurulu|dilekçe|onay|approval)", re.IGNORECASE)
CAP_RE = re.compile(r"(ÇAP|çift ana ?dal|double major)", re.IGNORECASE)


def plan_types(client: ObsClient, program_id: int) -> list[dict]:
    return _objects(client.post_json(config.EP["eq_plan_types"], {"programId": program_id}))


def plans(client: ObsClient, program_id: int, plan_type_id: int) -> list[dict]:
    return _objects(client.post_json(
        config.EP["eq_plans"], {"programId": program_id, "planTipiId": plan_type_id}))


def branches(client: ObsClient, plan_id: int) -> list[dict]:
    return _objects(client.post_json(config.EP["eq_branches"], {"planId": plan_id}))


def _objects(payload) -> list[dict]:
    return payload if isinstance(payload, list) else []


def sweep_program(client: ObsClient, con: sqlite3.Connection, program_id: int,
                  max_plans: int | None = None) -> tuple[int, int]:
    """Bir program için tüm (plan tipi, plan, branş) kombinasyonlarını tarar.

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
                found += _fetch_one(client, con, program_id, pt_id, pl_id, br.get("objectId"),
                                    plan_type_name=pt.get("planTipiAdiLanguage", ""))
    con.commit()
    return tried, found


def _fetch_one(client: ObsClient, con: sqlite3.Connection, program_id, plan_type_id,
               plan_id, branch_id, plan_type_name: str = "") -> int:
    params = {"ProgramId": program_id, "PlanTipiId": plan_type_id,
              "PlanId": plan_id, "DersBransKoduId": branch_id}
    html = client.get(config.EP["eq_page"], params)
    if NOT_FOUND.search(html):
        return 0
    tree = HTMLParser(html)
    table = tree.css_first("table")
    if table is None:
        return 0
    url = config.EP["eq_page"] + "?" + "&".join(f"{k}={v}" for k, v in params.items())
    n = 0
    for row in table.css("tbody tr"):
        cells = [c.text(strip=True) for c in row.css("td")]
        if not cells:
            continue
        n += _store(con, cells, plan_id, url, plan_type_name)
    return n


def _store(con: sqlite3.Connection, cells: list[str], plan_id: int, url: str,
           plan_type_name: str) -> int:
    """Satırı yönlü denkliğe çevirir. Hedef = plandaki ders, kaynak(lar) = yerine sayılanlar.

    Sütun düzeni programdan programa değişebildiği için heuristik: ilk hücrede tek
    ders kodu varsa o HEDEF, kalan hücrelerdeki tüm kodlar KAYNAK'tır. Ham metin
    her zaman note_raw'a yazılır ki yanlış yorum sonradan düzeltilebilsin.
    """
    raw = " | ".join(cells)
    head_codes = [normalize_course_code(f"{a} {b}") for a, b in COURSE_RE.findall(cells[0])]
    tail_codes = [normalize_course_code(f"{a} {b}")
                  for a, b in COURSE_RE.findall(" ".join(cells[1:]))]
    if not head_codes or not tail_codes:
        return 0
    target = head_codes[0]
    sources = [c for c in tail_codes if c != target]
    if not sources:
        return 0

    confidence = "requires_approval" if APPROVAL_RE.search(raw) else "official"
    # ÖİDB notu: "Bölüm tarafından belirlenmiş ders denklikleri, gerektiği durumlarda
    # ÇAP ders planı için de geçerlidir." -> varsayılan 1; metin ÇAP'ı dışlarsa 0.
    applies_to_cap = 0 if re.search(r"ÇAP.{0,20}(geçerli değil|hariç)", raw, re.IGNORECASE) else 1
    cur = con.execute(
        """INSERT INTO equivalence(target_course,target_plan_id,applies_to_cap,confidence,
                                   note_raw,source_url,scraped_at)
           VALUES (?,?,?,?,?,?,?)""",
        (target, plan_id, applies_to_cap, confidence, raw, url, db.now()),
    )
    eq_id = cur.lastrowid
    grade = _min_grade(raw)
    for code in dict.fromkeys(sources):
        con.execute(
            "INSERT OR IGNORE INTO equivalence_source(equivalence_id,course_code,min_grade)"
            " VALUES (?,?,?)", (eq_id, code, grade),
        )
    return 1


def _min_grade(text: str) -> str:
    m = re.search(r"\bMIN\s*([A-F]{2})\b", text, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    return "DD" if re.search(r"başarıl|geç(er|ilir)", text, re.IGNORECASE) else "DD"
