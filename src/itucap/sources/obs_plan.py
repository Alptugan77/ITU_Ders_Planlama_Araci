"""WP1.1 + WP1.2 — OBS ders planı scraper'ı (ÇAP DAHİL).

Keşif notları (17–18 Ağustos 2026, docs/obs-endpoints.md):

*   Kademeli menü ATLANABİLİR. Plan listesi tek GET ile alınır:
        /public/DersPlan/DersPlanlariList?PlanTipiKodu=cap&programKodu=BLG_LS
*   Plan detayı basit tamsayı id ile: /public/DersPlan/DersPlanDetay/2229
*   ★ ÇAP planları (ANADAL, ÇAP) çiftine göre tanımlı: 'TUMMUH_BLG', 'GEO_BLG'...
*   ★ İKİ FARKLI SAYFA DÜZENİ VAR:
      - ANADAL (lisans/uolp): her yarıyıl için AYRI tablo, önünde "N. Semester"
        başlığı. HTAE (2295) -> 8 tablo.
      - ÇAP: TEK düz tablo, yarıyıl yok, 'Compulsory/Elective' (Z/S) sütunu var.
        Ayrıca #dersPlanProgramList = planın geçerli olduğu anadal programları.
*   Her iki düzende de sütunlar aynı:
      Course Code | Course Title | Language | Compulsory/Elective | Credit |
      ECTS | Teo. | Tutorial | Lab. | Type
    Son sütun ('Type') ders kategorisini DOĞRUDAN verir (MT/TB/TM/ITB/EC) —
    etiket metnini parse etmekten daha güvenilir.
*   Seçmeli havuz linki: /public/DersPlan/_DersGrupSearch?grupId=11386
"""
from __future__ import annotations

import re
import sqlite3
from urllib.parse import parse_qs, urlparse

from selectolax.parser import HTMLParser

from .. import config, db
from ..normalize import (
    CATEGORIES,
    course_codes_in,
    normalize_course_code,
    normalize_pool_label,
    obs_code_to_program,
    split_cap_plan_code,
)

# ★ Ayrıştırılamayan plan satırları. Sessizce düşürmek, bu projede tekrar
# tekrar canımızı yakan hata biçimi (bkz. http.post_json). `pipeline` tarama
# sonunda buradan rapor veriyor; ayrıca `quality.py` veritabanına bakarak
# aynı boşluğu geriye dönük de yakalıyor (satır sayısı = MAX(position)+1).
dropped_rows: list[tuple[int, list[str]]] = []

_CODE_TITLE_RE = re.compile(r"^(?P<code>[A-Z0-9]+(?:_[A-Z0-9]+)+)\s+(?P<rest>.*)$")
# "1. Semester" / "1. Yarıyıl" / "1.Yarıyıl"
_TERM_HEAD_RE = re.compile(r"^\s*(\d{1,2})\s*\.\s*(Semester|Yarıyıl|Yariyil)\b", re.IGNORECASE)
_HEADER_ROW_RE = re.compile(r"course\s*code|ders\s*kodu", re.IGNORECASE)


# --------------------------------------------------------------- plan listesi
def list_plans(client, plan_type: str, obs_program_code: str) -> list[dict]:
    """(plan_type, program) için mevcut planları döndürür: id, başlık, iterasyon."""
    html = client.get(config.EP["plan_list"],
                      {"PlanTipiKodu": plan_type, "programKodu": obs_program_code})
    tree = HTMLParser(html)
    out: list[dict] = []
    for row in tree.css("table tbody tr"):
        link = row.css_first("a[href]")
        if not link:
            continue
        m = re.search(r"/DersPlanDetay/(\d+)", link.attributes.get("href", ""))
        if not m:
            continue
        cells = [c.text(strip=True) for c in row.css("td")]
        title = cells[-1] if cells else ""
        code_m = _CODE_TITLE_RE.match(title)
        pair_code = code_m.group("code") if code_m else None
        # ★ (anadal, hedef) ÇİFTİ yalnız ÇAP'ta var: 'TUMMUH_BLG'.
        # Yandal programı bir çift değil, kendi başına bir program
        # ('ECN_YD' = Economics Minor). split_cap_plan_code onu ('ECN','YD')
        # diye bölerdi ve 'YD' adında olmayan bir programa bağlardı.
        if plan_type == "cap" and pair_code:
            host, target = split_cap_plan_code(pair_code)
        else:
            host, target = None, (pair_code or None)
        out.append({
            "plan_id": int(m.group(1)),
            "title": title,
            "pair_code": pair_code,
            "host_program_code": host,
            "target_program_code": target,
            "iteration": _iteration_of(title),
            "plan_type": plan_type,
            "obs_program_code": obs_program_code,
        })
    return out


def _iteration_of(title: str) -> str:
    """Başlıktan iterasyon aralığını çıkarır. OBS dili oturuma göre değişir.

    EN: '... Double Major Program After 2018-2019 / Fall Semester'
        -> niteleyici BAŞTA  ('After ...')
    TR: '... ÇAP Programı 2018-2019 / Güz Dönemi Sonrası'
        -> niteleyici SONDA, aralık yıl ile başlıyor
    """
    m = re.search(r"\b(?:Before|After|Between)\b.*$", title)
    if m:
        return m.group(0).strip()
    m = re.search(r"\d{4}-\d{4}.*$", title)
    return m.group(0).strip() if m else ""


# ---------------------------------------------------------------- plan detayı
def scrape_plan(client, con: sqlite3.Connection, meta: dict, fetch_pools: bool = True) -> int:
    """Bir planı çeker; plan + plan_slot + plan_host_program tablolarına yazar."""
    url = f"{config.EP['plan_detail']}/{meta['plan_id']}"
    tree = HTMLParser(client.get(url))
    tables = tree.css("table")
    if not tables:
        raise RuntimeError(
            f"Plan {meta['plan_id']}: tablo bulunamadı (sayfa yapısı değişmiş olabilir)")

    host_table = tree.css_first("#dersPlanProgramList")
    # NOT: selectolax aynı düğüm için farklı Python nesneleri döndürebiliyor,
    # bu yüzden kimlik (`is`) ile değil id niteliğiyle eliyoruz.
    course_tables = [t for t in tables if t.attributes.get("id") != "dersPlanProgramList"]
    terms = _term_numbers(course_tables)
    is_term_based = any(t is not None for t in terms)

    con.execute(
        """INSERT INTO plan(id,program_code,host_program_code,plan_type,obs_program_code,
                            title,iteration,is_term_based,has_course_table,notes_raw,
                            source,source_url,scraped_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(id) DO UPDATE SET
             program_code=excluded.program_code, host_program_code=excluded.host_program_code,
             plan_type=excluded.plan_type, title=excluded.title, iteration=excluded.iteration,
             is_term_based=excluded.is_term_based,
             has_course_table=excluded.has_course_table, notes_raw=excluded.notes_raw,
             source=excluded.source, scraped_at=excluded.scraped_at""",
        (meta["plan_id"],
         meta.get("target_program_code") or obs_code_to_program(meta["obs_program_code"]),
         meta.get("host_program_code"), meta["plan_type"], meta["obs_program_code"],
         meta["title"], meta["iteration"], int(is_term_based), int(bool(course_tables)),
         _notes(tree), "obs", url, db.now()),
    )
    # idempotent yeniden yazım
    con.execute("DELETE FROM plan_slot WHERE plan_id=?", (meta["plan_id"],))
    con.execute("DELETE FROM plan_host_program WHERE plan_id=?", (meta["plan_id"],))

    n = position = 0
    for table, term_no in zip(course_tables, terms):
        for row in table.css("tr"):
            cells = row.css("td")
            if not cells:
                continue                                    # th başlık satırı
            texts = [c.text(strip=True) for c in cells]
            if not any(texts) or _HEADER_ROW_RE.search(texts[0]):
                continue                                    # boş satır / td'li başlık
            n += _slot_from_row(con, meta["plan_id"], cells, texts, term_no, position)
            position += 1

    if host_table is not None:
        for row in host_table.css("tbody tr"):
            cells = [c.text(strip=True) for c in row.css("td")]
            if not cells or not cells[0]:
                continue
            con.execute(
                """INSERT OR REPLACE INTO plan_host_program(plan_id,program_code,obs_code,
                        program_name,updated_at) VALUES (?,?,?,?,?)""",
                (meta["plan_id"], obs_code_to_program(cells[0]), cells[0],
                 cells[1] if len(cells) > 1 else None,
                 cells[2] if len(cells) > 2 else None),
            )
    con.commit()

    if fetch_pools:
        fetch_pool_options(client, con, meta["plan_id"])
    return n


def _term_numbers(tables) -> list[int | None]:
    """Her ders tablosunun yarıyıl numarasını, kendinden önce gelen başlıktan bulur.

    Anadal planı: 8 tablo, her birinin önünde '1. Semester' ... '8. Semester'.
    ÇAP planı: tek tablo, başlık yok -> None (dönemsiz).
    """
    out: list[int | None] = []
    for table in tables:
        term = None
        node = table
        for _ in range(12):                     # sınırlı yukarı/geri arama
            node = node.prev or node.parent
            if node is None:
                break
            text = (node.text(strip=True) or "")[:60]
            m = _TERM_HEAD_RE.match(text)
            if m:
                term = int(m.group(1))
                break
        out.append(term)
    # Fallback: başlık yakalanamadıysa ama birden çok tablo varsa sıraya göre numaralandır
    if len(out) > 1 and all(t is None for t in out):
        out = list(range(1, len(out) + 1))
    return out


def _slot_from_row(con, plan_id: int, cells, texts: list[str], term_no: int | None,
                   position: int) -> int:
    title = texts[1] if len(texts) > 1 else ""
    kind_col = texts[3] if len(texts) > 3 else ""
    credits = _num(texts[4]) if len(texts) > 4 else None
    ects_raw = texts[5] if len(texts) > 5 else None
    type_raw = texts[9] if len(texts) > 9 else (texts[-1] if texts else None)

    link = cells[0].css_first("a[href]")
    href = link.attributes.get("href", "") if link else ""
    group_id = parse_qs(urlparse(href).query).get("grupId", [None])[0]

    # ★ AYIRICI ŞART. Yeni plan sayfalarında ilk hücre iki kod taşıyor
    # ("EEF 110<br>EEF 110E"); `strip=True` bunları bitiştiriyor ve o metinden
    # kod çıkarmaya çalışmak yanlış kod üretir. Bkz. normalize.course_codes_in.
    codes = course_codes_in(cells[0].text(separator="\n", strip=True))

    ects = _num(ects_raw)          # '4 / 5 / 6' aralığında None döner, ham hali korunur
    secmeli = kind_col.strip().upper().startswith(("S", "E"))   # Seçmeli / Elective

    if group_id or not codes:
        if not group_id and not codes:
            # Ne grup bağlantısı ne ders kodu — havuz başlığı mı, ayrıştıramadığımız
            # bir satır mı bilmiyoruz. Z/S sütunu doluysa havuz sayıyoruz;
            # değilse SESSİZCE atmıyoruz, raporluyoruz.
            if not secmeli:
                dropped_rows.append((plan_id, texts))
                return 0
        # 'Type' sütunu kategoriyi doğrudan verir; etiket parse'ı yedek.
        category = (type_raw or "").strip().upper()
        if category not in CATEGORIES:
            category, _ = normalize_pool_label(title)
        con.execute(
            """INSERT INTO plan_slot(plan_id,term_no,slot_kind,pool_label_raw,pool_category,
                                     pool_group_id,credits,ects_raw,ects,type_raw,zs_raw,
                                     position)
               VALUES (?,?,'ELECTIVE_POOL',?,?,?,?,?,?,?,?,?)""",
            (plan_id, term_no, title, category, group_id, credits, ects_raw, ects,
             type_raw, kind_col or None, position),
        )
        return 1

    if secmeli:
        # ★ ADI BELLİ ama ZORUNLU OLMAYAN ders (Z/S sütunu 'S', grup bağlantısı yok).
        # Eskiden BOŞ bir havuz olarak yazılıyordu: seçeneği olmayan, hiçbir zaman
        # dolamayan bir slot — ilerlemeyi sonsuza kadar eksik gösteriyordu.
        # Doğrusu, seçeneği kendisi olan bir havuz: "seçmeli, seçenek EEF 206".
        category = (type_raw or "").strip().upper()
        if category not in CATEGORIES:
            category, _ = normalize_pool_label(title)
        cur = con.execute(
            """INSERT INTO plan_slot(plan_id,term_no,slot_kind,pool_label_raw,pool_category,
                                     credits,ects_raw,ects,type_raw,zs_raw,position)
               VALUES (?,?,'ELECTIVE_POOL',?,?,?,?,?,?,?,?)""",
            (plan_id, term_no, title or codes[0], category, credits, ects_raw, ects,
             type_raw, kind_col or None, position),
        )
        for code in codes:
            con.execute("INSERT OR IGNORE INTO pool_option(slot_id,course_code) VALUES (?,?)",
                        (cur.lastrowid, code))
        return 1

    con.execute(
        """INSERT INTO plan_slot(plan_id,term_no,slot_kind,course_code,alt_course_codes,
                                 credits,ects_raw,ects,type_raw,zs_raw,position)
           VALUES (?,?,'REQUIRED',?,?,?,?,?,?,?,?)""",
        (plan_id, term_no, codes[0], ",".join(codes[1:]) or None,
         credits, ects_raw, ects, type_raw, kind_col or None, position),
    )
    return 1


_CODE_ONLY_RE = re.compile(r"^[A-ZÇĞİÖŞÜ]{2,4} \d{3,4}[A-Z]*$")
_CODE_IN_TEXT_RE = re.compile(r"^\s*([A-ZÇĞİÖŞÜ]{2,4}\s?\d{3,4}[A-Z]{0,2})\b")


def _pool_code(cell) -> str | None:
    """Havuz satırından ders kodunu çıkarır.

    ⚠️ Hücre kodu ve ADI birlikte taşıyor:
        <a href="...DersBilgi...">GEO 413E</a><br>Navigation Sys. and Methods
    Doğrudan hücre metnini kod sanmak sessizce BOŞ havuz üretiyordu. Önce
    bağlantı metnine, o yoksa metnin başındaki koda bakıyoruz.
    """
    link = cell.css_first("a")
    if link:
        code = normalize_course_code(link.text(strip=True))
        if _CODE_ONLY_RE.match(code):
            return code
    m = _CODE_IN_TEXT_RE.match(cell.text(strip=True) or "")
    if m:
        code = normalize_course_code(m.group(1))
        if _CODE_ONLY_RE.match(code):
            return code
    return None


def fetch_pool_options(client, con: sqlite3.Connection, plan_id: int) -> int:
    """Seçmeli havuzların içeriğini _DersGrupSearch partial view'ından çeker."""
    total = 0
    rows = con.execute(
        "SELECT id, pool_group_id FROM plan_slot WHERE plan_id=? AND pool_group_id IS NOT NULL",
        (plan_id,),
    ).fetchall()
    for row in rows:
        tree = HTMLParser(client.get(config.EP["pool_group"], {"grupId": row["pool_group_id"]}))
        for tr in tree.css("table tr"):
            cells = tr.css("td")
            if not cells:
                continue
            code = _pool_code(cells[0])
            if code:
                con.execute(
                    "INSERT OR IGNORE INTO pool_option(slot_id,course_code) VALUES (?,?)",
                    (row["id"], code),
                )
                total += 1
    con.commit()
    return total


def _notes(tree: HTMLParser) -> str | None:
    """Plan sayfasındaki serbest metin notlar (denklik/kredi şartları buraya gömülü)."""
    chunks = []
    for node in tree.css("div.alert, div.panel-body > p, .card-body > p, .aciklama"):
        text = node.text(strip=True)
        if 30 < len(text) < 4000:
            chunks.append(text)
    return "\n\n".join(dict.fromkeys(chunks)) or None


def _num(v):
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------- program keşfi
# ★ Program kodlarını TAHMİN ETMEK yerine OBS'ye sormak.
#
# Tarayıcı baştan beri `f"{program_kodu}_LS"` varsayıyordu. ÇAP için çalışıyor
# çünkü ÇAP planları hedef lisans programına bağlı. **Yandal için çalışmıyor**:
# kullanıcı 22.08.2026'da söyledi — yandal programları lisans bölümlerinden
# bağımsız, FAKÜLTE düzeyinde yayınlanıyor. Yani `BLG_LS` diye sormak yanlış
# soru; o kodda yandal planı olmaması normal.
#
# Doğrusu, OBS'nin kademeli menüsünü kullanmak: fakülteyi seç → o fakültenin
# O PLAN TİPİNDEKİ programlarını al. Bu adım "isteğe bağlı" diye atlanmıştı
# (docs/obs-endpoints.md 1.2); ÇAP'ta atlanabilir, yandalda atlanamaz.
#
# Fakülte id'leri SABİT YAZILMIYOR, sayfadan okunuyor: yeni fakülte açılırsa
# ya da id değişirse kod kendiliğinden uyum sağlasın.

# ★★ Parametre adı: `birimId` — `akademikBirimId` DEĞİL.
#
# docs/obs-endpoints.md'de `akademikBirimId` yazıyordu ve yanlıştı. Fark
# edilmemesinin sebebi, bu adımın hiç kullanılmamış olması: ÇAP'ta program
# kodu tahmin edilebildiği için ("BLG" → "BLG_LS") kademeli menü atlanmıştı.
# Yandalda tahmin çalışmıyor (kodlar `ECN_YD`, `BHB_YD`, `SUS_YD`) ve uç ilk
# kez gerçekten çağrıldı — yanlış parametre boş cevap veriyordu.
#
# 22.08.2026'da ağ isteğinden doğrulandı:
#   birimId=10&planTipiKodu=yandal
#   → [{programKodu:"ECN_YD", programAdi:"Economics (Minor)"}, …]
PROGRAM_PARAM = "birimId"


def list_faculties(client) -> list[tuple[str, str]]:
    """Ders planı sayfasındaki akademik birim listesi: [(id, ad), …]."""
    html = client.get(config.EP["plan_page"])
    tree = HTMLParser(html)
    out: list[tuple[str, str]] = []
    for sel in tree.css("select"):
        name = (sel.attributes.get("id") or "") + " " + (sel.attributes.get("name") or "")
        if "birim" not in name.lower() and "fakulte" not in name.lower():
            continue
        for opt in sel.css("option"):
            val = (opt.attributes.get("value") or "").strip()
            ad = opt.text(strip=True)
            if val and val not in ("0", "-1") and ad:
                out.append((val, ad))
        if out:
            break
    return out


def list_programs_debug(client, faculty_id: str, plan_type: str):
    """Ham cevabı ve çıkarılan kodları birlikte döndürür (tanı için)."""
    data = client.post_json(config.EP["plan_programs"],
                            {PROGRAM_PARAM: faculty_id,
                             "planTipiKodu": plan_type})
    return data, _kodlari_cikar(data)


def _programlari_cikar(data) -> list[tuple[str, str]]:
    """Cevaptan (kod, ad) çiftleri. Ad yoksa kodun kendisi kullanılır.

    Yandal programlarının insan okunur adı yalnız burada geliyor
    ("Economics (Minor)"); `program` tablosunda karşılığı yok çünkü onlar
    lisans programı değil. Adı atarsak arayüzde `ECN_YD` yazar ve kullanıcı
    hangi program olduğunu anlamaz.
    """
    ciftler: list[tuple[str, str]] = []

    def gez(x):
        if isinstance(x, dict):
            if "_ham" in x:
                for kod in re.findall(r'value="([A-Za-z0-9_]{2,})"', x["_ham"]):
                    ciftler.append((kod.upper(), kod.upper()))
                return
            kod = next((str(x[k]) for k in ("programKodu", "ProgramKodu", "Kod",
                                            "kod", "Value", "value")
                        if x.get(k)), None)
            if kod:
                ad = next((str(x[k]) for k in ("programAdi", "ProgramAdi", "Ad",
                                               "ad", "Text", "text")
                           if x.get(k)), kod)
                ciftler.append((kod.strip().upper(), ad.strip()))
                return
            for v in x.values():
                if isinstance(v, (list, dict)):
                    gez(v)
        elif isinstance(x, list):
            for item in x:
                gez(item)
        elif isinstance(x, str) and re.fullmatch(r"[A-Za-z0-9_]{2,}", x.strip()):
            ciftler.append((x.strip().upper(), x.strip().upper()))

    gez(data)
    return ciftler


def _kodlari_cikar(data) -> list[str]:
    """Cevaptan program kodlarını çıkarır — biçim ne olursa olsun.

    OBS'nin cevabı belgelenmemiş ve sürüme göre değişebiliyor: düz liste,
    sözlük listesi, sarmalanmış sözlük ya da HTML `<option>` parçası.
    Hepsini deniyoruz; hiçbiri tutmazsa çağıran taraf ham cevabı görsün diye
    boş dönüyoruz ama SESSİZ kalmıyoruz (bkz. cmd_kesif).
    """
    ALAN = ("Kod", "kod", "Value", "value", "ProgramKodu", "programKodu",
            "Text", "text", "Ad", "ad", "Id", "id")
    out: list[str] = []

    def gez(x):
        if isinstance(x, str):
            out.append(x)
        elif isinstance(x, dict):
            if "_ham" in x:                       # JSON değil, HTML gelmiş
                out.extend(re.findall(r'value="([A-Z0-9_]+)"', x["_ham"]))
                return
            for k in ALAN:
                if x.get(k):
                    out.append(str(x[k]))
                    return
            for v in x.values():                  # sarmalanmış liste
                if isinstance(v, (list, dict)):
                    gez(v)
        elif isinstance(x, list):
            for item in x:
                gez(item)

    gez(data)
    # Program kodu kalıbı: harf/rakam/alt çizgi, en az 2 karakter.
    return [k.strip().upper() for k in out
            if k and re.fullmatch(r"[A-Za-z0-9_]{2,}", k.strip())]


def list_programs_named(client, faculty_id: str, plan_type: str
                        ) -> list[tuple[str, str]]:
    """(fakülte, plan tipi) için [(kod, ad), …]."""
    return _programlari_cikar(client.post_json(
        config.EP["plan_programs"],
        {PROGRAM_PARAM: faculty_id, "planTipiKodu": plan_type}))


def list_programs(client, faculty_id: str, plan_type: str) -> list[str]:
    """(fakülte, plan tipi) için OBS program kodları — ör. ['BLG_LS', …].

    Cevabın biçimi belgelenmemiş; hem JSON listesi hem HTML `<option>`
    dönebiliyor. İkisini de karşılıyoruz ve tanımadığımız biçimde SESSİZCE
    boş dönmüyoruz — çağıran taraf farkı görebilsin.
    """
    return _kodlari_cikar(client.post_json(
        config.EP["plan_programs"],
        {PROGRAM_PARAM: faculty_id, "planTipiKodu": plan_type}))


def save_programs(con, programs, level: str) -> int:
    """Keşfedilen programları `program` tablosuna yazar.

    ★ Yandal programları lisans programı DEĞİL ('ECN_YD' = Economics Minor,
    'ECN' lisans programından ayrı bir şey). `level` onları ayırıyor: arayüz
    yandal ararken `level='YD'`, ÇAP ararken `level='LS'` satırlarına bakıyor.
    Aynı tabloya karışık koyup ayırt etmemek, ÇAP listesinde yandal
    programlarının görünmesine yol açardı.
    """
    n = 0
    for kod, ad in programs:
        con.execute(
            """INSERT INTO program(code,name,faculty,level) VALUES (?,?,?,?)
               ON CONFLICT(code) DO UPDATE SET
                 name=excluded.name, level=excluded.level""",
            (kod, ad, "", level))
        n += 1
    con.commit()
    return n
