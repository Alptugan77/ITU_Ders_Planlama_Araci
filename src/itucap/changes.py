"""FAZ 9 — Dönem başında ne değişti?

    make changes

Ders programı dönem başlarında **kademeli** yayınlanıyor. Faz 5'te ölçtük:
14 kalan ÇAP dersinden 10'u "bu dönem açılmamış" görünüyordu — ama bunların
bir kısmı sonradan açılıyor. Kontenjanlar da kayıt haftasında saatler içinde
doluyor.

Bu, "her gün OBS'yi elle tara" işi. Araç zaten her `refresh`'te tüm şubeleri
çekiyor; tek eksik **hafızaydı**. Her tazelemede bir anlık görüntü alınıyor,
iki görüntü karşılaştırılıp şu üç soru cevaplanıyor:

* Beklediğim ders **açıldı mı**?
* Programımdaki bir şube **kapandı mı**?
* Kontenjan **doldu mu**?

Anlık görüntü referans DB'de (`lesson_snapshot`) — kişisel veri değil.
"""
from __future__ import annotations

import datetime as dt
import sqlite3
from dataclasses import dataclass, field

KEEP = 12                # kaç anlık görüntü saklanacak


def take(con: sqlite3.Connection, stamp: str | None = None) -> str:
    """Şu andaki şube durumunu kaydeder ve damgayı döndürür."""
    stamp = stamp or dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    con.execute("DELETE FROM lesson_snapshot WHERE taken_at=?", (stamp,))
    con.execute(
        """INSERT INTO lesson_snapshot(taken_at, crn, course_code, capacity, enrolled)
           SELECT ?, crn, course_code, capacity, enrolled FROM lesson""", (stamp,))
    n = con.execute("SELECT COUNT(*) FROM lesson").fetchone()[0]
    con.execute("INSERT OR REPLACE INTO snapshot_run(taken_at, lessons) VALUES (?,?)",
                (stamp, n))
    prune(con)
    con.commit()
    return stamp


def prune(con: sqlite3.Connection, keep: int = KEEP) -> int:
    old = stamps(con)[keep:]
    for stamp in old:
        con.execute("DELETE FROM lesson_snapshot WHERE taken_at=?", (stamp,))
        con.execute("DELETE FROM snapshot_run WHERE taken_at=?", (stamp,))
    return len(old)


def stamps(con: sqlite3.Connection) -> list[str]:
    """Kaydedilmiş görüntüler, yeniden eskiye.

    ⚠️ `snapshot_run`'dan okunuyor, `lesson_snapshot`'tan DEĞİL: şubesiz bir
    görüntü ikinciye hiç satır yazmaz ve görünmez olurdu."""
    return [r[0] for r in con.execute(
        "SELECT taken_at FROM snapshot_run ORDER BY taken_at DESC")]


@dataclass
class Diff:
    since: str = ""
    until: str = ""
    opened: list[dict] = field(default_factory=list)      # yeni açılan ders
    new_sections: list[dict] = field(default_factory=list)  # var olan derse şube
    closed: list[dict] = field(default_factory=list)      # kaybolan şube
    filled: list[dict] = field(default_factory=list)      # kontenjan doldu
    freed: list[dict] = field(default_factory=list)       # yer açıldı

    @property
    def empty(self) -> bool:
        return not (self.opened or self.new_sections or self.closed
                    or self.filled or self.freed)

    def count(self) -> int:
        return (len(self.opened) + len(self.new_sections) + len(self.closed)
                + len(self.filled) + len(self.freed))


def _rows(con, stamp):
    return {r["crn"]: r for r in con.execute(
        """SELECT crn, course_code, capacity, enrolled FROM lesson_snapshot
           WHERE taken_at=?""", (stamp,))}


def compare(con: sqlite3.Connection, since: str | None = None,
            until: str | None = None, watch: set[str] | None = None) -> Diff:
    """İki anlık görüntüyü karşılaştırır.

    `watch` verilirse (ilgilendiğin ders kodları) rapor yalnız onları içerir —
    3400 şubelik bir dökümde senin dersin kaybolur.
    """
    have = stamps(con)
    if len(have) < 2:
        # Tek görüntüyle karşılaştırma yapılamaz. `since` boş bırakılıyor ki
        # arayüz 'değişiklik yok' ile 'henüz veri yok'u karıştırmasın.
        return Diff(since="", until=have[0] if have else "")
    until = until or have[0]
    since = since or have[1]
    old, new = _rows(con, since), _rows(con, until)
    old_courses = {r["course_code"] for r in old.values()}
    new_courses = {r["course_code"] for r in new.values()}
    names = {r[0]: r[1] for r in con.execute("SELECT code, name FROM course")}

    def keep(code):
        return watch is None or code in watch

    diff = Diff(since=since, until=until)
    for code in sorted(new_courses - old_courses):
        if keep(code):
            n = sum(1 for r in new.values() if r["course_code"] == code)
            diff.opened.append({"course": code, "name": names.get(code, ""),
                                "sections": n})
    for crn, row in new.items():
        code = row["course_code"]
        if not keep(code):
            continue
        before = old.get(crn)
        if before is None:
            if code in old_courses:      # ders zaten vardı, şube eklendi
                diff.new_sections.append({"course": code, "crn": crn,
                                          "name": names.get(code, ""),
                                          "free": _free(row)})
            continue
        was, now = _free(before), _free(row)
        if was > 0 and now == 0:
            diff.filled.append({"course": code, "crn": crn, "name": names.get(code, ""),
                                "capacity": row["capacity"]})
        elif was == 0 and now > 0:
            diff.freed.append({"course": code, "crn": crn, "name": names.get(code, ""),
                               "free": now})
    for crn, row in old.items():
        code = row["course_code"]
        if crn not in new and keep(code):
            diff.closed.append({"course": code, "crn": crn, "name": names.get(code, "")})
    return diff


def _free(row) -> int:
    return max(0, (row["capacity"] or 0) - (row["enrolled"] or 0))


def format_diff(diff: Diff, watching: int = 0) -> str:
    if not diff.since or not diff.until:
        return ("Karşılaştırma için en az iki anlık görüntü gerekiyor.\n"
                "`make refresh` çalıştırdıkça birikirler.")
    head = [f"DEĞİŞİM RAPORU   {diff.since}  →  {diff.until}"]
    if watching:
        head.append(f"  (yalnız seni ilgilendiren {watching} ders)")
    if diff.empty:
        head.append("\n  Değişiklik yok.")
        return "\n".join(head)

    def block(title, items, line):
        if not items:
            return []
        out = [f"\n{title} ({len(items)})"]
        out += ["  " + line(i) for i in items]
        return out

    body = []
    body += block("★ AÇILDI", diff.opened,
                  lambda i: f"{i['course']:<12} {i['sections']} şube — {i['name'][:44]}")
    body += block("★ YENİ ŞUBE", diff.new_sections,
                  lambda i: f"{i['course']:<12} CRN {i['crn']}  {i['free']} boş")
    body += block("KONTENJAN DOLDU", diff.filled,
                  lambda i: f"{i['course']:<12} CRN {i['crn']}  {i['capacity']}/{i['capacity']}")
    body += block("YER AÇILDI", diff.freed,
                  lambda i: f"{i['course']:<12} CRN {i['crn']}  {i['free']} boş")
    body += block("ŞUBE KAPANDI", diff.closed,
                  lambda i: f"{i['course']:<12} CRN {i['crn']}")
    return "\n".join(head + body)
