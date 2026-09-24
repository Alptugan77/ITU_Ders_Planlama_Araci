"""WP1.7 — Pipeline orchestrator.

Tek komut: `python -m itucap.pipeline refresh`
Idempotent: iki kez çalıştırınca aynı sonuç, duplicate yok.

NOT: obs.itu.edu.tr'ye erişim gerektiren adımlar (plans/equivalence) İTÜ ağından
veya normal bir internet bağlantısından çalışır. Sadece itu-helper verisiyle
çalışmak için: `python -m itucap.pipeline refresh --skip-obs`
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

from . import changes, config, db, declared, explore_prereq, notlar, prereq, quality, verify
from .plans import resolve_plans as _resolve_plans
from .plans import watch_codes as _watch_codes
from .http import ObsClient
from .sources import ituhelper, obs_equivalence, obs_notdagilimi, obs_plan


# --------------------------------------------------------------------- adımlar
def step_ituhelper(con, settings, offline: bool = False) -> None:
    src = config.DATA_DIR / "ituhelper"
    with db.run_step(con, "ituhelper.fetch") as box:
        if not offline:
            ituhelper.fetch_all(settings, src)
        box["rows"] = len(ituhelper.FILES)
    with db.run_step(con, "ituhelper.programs") as box:
        box["rows"] = ituhelper.load_programs(con, src)
    with db.run_step(con, "ituhelper.buildings") as box:
        box["rows"] = ituhelper.load_buildings(con, src)
    with db.run_step(con, "ituhelper.courses") as box:
        box["rows"] = ituhelper.load_courses(con, src)
    with db.run_step(con, "ituhelper.lessons") as box:
        # ★ Faz 64 — şubelerin dönemi çekildikleri günden; ayar yalnız geçiş
        # aylarında (bkz. config.donem_kodu_tarihten).
        box["rows"] = ituhelper.load_lessons(
            con, src, config.donem_kodu_tarihten(db.now()) or settings.term)
    with db.run_step(con, "ituhelper.course_plans") as box:
        box["rows"] = ituhelper.load_course_plans(con, src)


def step_obs_plans(con, settings) -> None:
    """Anadal + ÇAP planlarını OBS'den çeker.

    ★ ÇAP planları (anadal, çap) çiftine göre tanımlı olduğundan, ÇAP programının
    TÜM ÇAP planlarını çekip `plan_host_program` üzerinden anadala göre filtreliyoruz.
    """
    client = ObsClient(settings)
    try:
        with db.run_step(con, "obs.plans.anadal") as box:
            metas = obs_plan.list_plans(client, "lisans", f"{settings.anadal_program}_LS")
            n = 0
            for meta in metas:
                n += obs_plan.scrape_plan(client, con, meta)
            box["rows"] = n
            box["message"] = f"{len(metas)} anadal planı"

        with db.run_step(con, "obs.plans.cap") as box:
            metas = obs_plan.list_plans(
                client, config.plan_type_of(settings.second_kind),
                f"{settings.second_program}_LS")
            n = 0
            for meta in metas:
                n += obs_plan.scrape_plan(client, con, meta)
            box["rows"] = n
            box["message"] = f"{len(metas)} ÇAP planı"
    finally:
        client.close()


def step_all_second_plans(con, settings, plan_types=("cap", "yandal"),
                          only: list[str] | None = None) -> dict:
    """FAZ 10 — HER programın ÇAP ve yandal planlarını çeker.

    ★★ PROGRAM KODLARI ARTIK TAHMİN EDİLMİYOR, OBS'YE SORULUYOR (Faz 16).

    Eskiden `f"{program_kodu}_LS"` varsayılıyordu. ÇAP'ta çalışıyor çünkü ÇAP
    planları hedef lisans programına bağlı. **Yandalda çalışmıyor**: yandal
    programları lisans bölümlerinden bağımsız, fakülte düzeyinde tanımlı ve
    kodları farklı (`ECN_YD`, `BHB_YD`, `SUS_YD`). `BLG_LS` diye sormak yanlış
    soruydu; OBS de doğru cevap veriyordu — "bu programda plan yok".

    Doğrusu kademeli menü: fakülte → o fakültenin O PLAN TİPİNDEKİ programları.
    Belgede "atlanabilir" diye işaretliydi (ÇAP için doğru), bu yüzden yıllarca
    hiç çağrılmadı ve içindeki yanlış parametre adı (`akademikBirimId`, doğrusu
    `birimId`) ortaya çıkmadı.

    ⚠️ Keşif boş dönerse ESKİ YÖNTEME düşülüyor. ÇAP tarafı 1081 planla
    çalışıyordu; yeni yolu zorlamak, çalışan bir şeyi kırma riski demekti.
    Hangi yolun kullanıldığı raporda yazıyor.
    """
    client = ObsClient(settings)
    # ★ İki ayrı sayaç: `programs` FARKLI program kodu, `lookups` (kod, tip)
    # sorgusu. Tek sayaç tutmak, iki plan tipi gezildiği için program sayısını
    # iki katına çıkarıyordu — ilerleme çıktısı yanıltıcı olurdu.
    stats = {"programs": 0, "lookups": 0, "plans": 0, "slots": 0, "errors": 0}
    gorulen_kod: set[str] = set()
    per: dict[str, dict[str, int]] = {t: {"plans": 0, "errors": 0, "empty": 0,
                                          "kodlar": 0}
                                      for t in plan_types}
    ilk_hata: dict[str, str] = {}
    yontem: dict[str, str] = {}
    try:
        fakulteler = []
        if not only:
            try:
                fakulteler = obs_plan.list_faculties(client)
            except Exception as exc:                           # noqa: BLE001
                print(f"   ⚠️  Fakülte listesi alınamadı: {str(exc)[:70]}")

        for plan_type in plan_types:
            # 1) Keşif: fakülte fakülte, gerçek program kodları.
            kodlar: list[tuple[str, str]] = []
            if fakulteler:
                for fid, _ad in fakulteler:
                    try:
                        kodlar.extend(
                            obs_plan.list_programs_named(client, fid, plan_type))
                    except Exception as exc:                   # noqa: BLE001
                        ilk_hata.setdefault(plan_type, f"birim {fid}: {exc}")
            kodlar = sorted({k: a for k, a in kodlar}.items())
            if kodlar:
                yontem[plan_type] = "keşif"
                # Lisans programı OLMAYANLARI (yandal gibi) kaydet ki arayüz
                # adlarını gösterebilsin.
                if plan_type != "cap":
                    obs_plan.save_programs(
                        con, [(k, a) for k, a in kodlar
                              if not k.upper().endswith("_LS")], "YD")
            else:
                # 2) Düşüş: eski tahmin. ÇAP'ta çalışıyor, kırmayalım.
                yontem[plan_type] = "tahmin (_LS)"
                base = only or [r[0] for r in con.execute(
                    "SELECT code FROM program WHERE level='LS' ORDER BY code")]
                kodlar = [(f"{c}_LS", c) for c in base]
            per[plan_type]["kodlar"] = len(kodlar)

            # 3) Her kod için plan listesi + detay
            for kod, _ad in kodlar:
                stats["lookups"] += 1
                gorulen_kod.add(kod)
                try:
                    metas = obs_plan.list_plans(client, plan_type, kod)
                except Exception as exc:                       # noqa: BLE001
                    stats["errors"] += 1
                    per[plan_type]["errors"] += 1
                    ilk_hata.setdefault(plan_type, f"{kod}: {exc}")
                    continue
                if not metas:
                    per[plan_type]["empty"] += 1
                for meta in metas:
                    try:
                        stats["slots"] += obs_plan.scrape_plan(client, con, meta)
                        stats["plans"] += 1
                        per[plan_type]["plans"] += 1
                    except Exception as exc:                   # noqa: BLE001
                        stats["errors"] += 1
                        per[plan_type]["errors"] += 1
                        ilk_hata.setdefault(plan_type, f"{kod}: {exc}")
                if stats["lookups"] % 20 == 0:
                    print(f"   … {stats['lookups']} sorgu, {stats['plans']} plan",
                          flush=True)
    finally:
        client.close()

    stats["programs"] = len(gorulen_kod)
    stats["per_type"] = per
    # ★ TİP BAŞINA rapor. Toplam sayı, bir tipin hiç gelmediğini gizliyordu.
    for t, d in per.items():
        durum = "✅" if d["plans"] else "⚠️ "
        print(f"   {durum} {t}: {d['plans']} plan · {d['kodlar']} program kodu "
              f"({yontem.get(t, '?')}) · {d['errors']} hata · "
              f"{d['empty']} kodda liste boş")
        if not d["plans"]:
            print(f"      → '{t}' tipinde HİÇ plan gelmedi. "
                  f"Tanı: make kesif T={t}")
            if t in ilk_hata:
                print(f"      → ilk hata: {ilk_hata[t][:160]}")
    return stats


def step_dedupe_plans(con) -> int:
    """OBS'den gerçek plan çekilen programlarda itu-helper'ın sentetik planını düşür.

    Aynı programın planı iki kaynaktan da gelebiliyor (itu-helper id<0, OBS id>0).
    İterasyon metinleri farklı dilde olduğu için metin eşleştirmesi güvenilmez;
    kural basit: bir (program, plan_tipi) için OBS planı varsa itu-helper kopyası gider.
    """
    cur = con.execute(
        """DELETE FROM plan
            WHERE id < 0
              AND EXISTS (SELECT 1 FROM plan o
                          WHERE o.id > 0
                            AND o.program_code = plan.program_code
                            AND o.plan_type   = plan.plan_type)"""
    )
    con.commit()
    return cur.rowcount


def step_equivalence(con, settings, program_ids: list[int], all_programs: bool = False) -> None:
    client = ObsClient(settings)
    try:
        with db.run_step(con, "obs.equivalence") as box:
            # ★ Önce eski RESMÎ denklikleri sil — tazelemede tekrar taranıyor,
            # yoksa her koşuda çoğalırlardı. Kullanıcı BEYANLARI (user_declared)
            # bu tabloda DEĞİL (Faz 28'de ucon'a taşındı) ama garanti olsun diye
            # yalnız official/requires_approval siliniyor.
            con.execute("""DELETE FROM equivalence_source WHERE equivalence_id IN
                           (SELECT id FROM equivalence WHERE confidence!='user_declared')""")
            con.execute("DELETE FROM equivalence WHERE confidence!='user_declared'")
            if all_programs:
                nprog, tried, found = obs_equivalence.sweep_all(client, con, progress=print)
            else:
                nprog = len(program_ids)
                tried = found = 0
                seen: set = set()          # programlar arası tekilleştirme
                for pid in program_ids:
                    t, f = obs_equivalence.sweep_program(client, con, pid, seen=seen)
                    tried += t
                    found += f
            box["rows"] = found
            box["message"] = (f"{nprog} program{' (tümü)' if all_programs else ''}, "
                              f"{tried} kombinasyon denendi, {found} denklik bulundu")
    finally:
        client.close()


def step_prereq(con) -> dict:
    """FAZ 2 — ham önşart metinlerini AND/OR ağacına çevirip prereq_node'a yazar."""
    with db.run_step(con, "prereq.parse") as box:
        stats = prereq.parse_all(con)
        box["rows"] = stats["nodes"]
        box["message"] = (f"{stats['parsed']}/{stats['with_prereq']} parse edildi, "
                          f"{stats['failed']} çözülemedi, {stats['repaired']} onarıldı")
    return stats


def step_reports(con) -> Path:
    return explore_prereq.write_report(con, config.ROOT / "docs" / "prereq-patterns.md")


def step_quality(con, settings=None) -> list[quality.Finding]:
    """Kalite kontrolleri. Kullanıcının kendi planları ayrıca geçiliyor:
    kendi planındaki bozukluk `error`, başka bölümünki `warn`."""
    mine: tuple = ()
    if settings is not None:
        try:
            mine = tuple(x for x in _resolve_plans(con, settings) if x)
        except Exception:                                  # noqa: BLE001
            mine = ()
    return quality.run(con, mine)


# ------------------------------------------------------------------------ cli
def cmd_refresh(args) -> int:
    settings = config.Settings.load()
    con = db.reference_db()
    db.user_db().close()  # kullanıcı DB'sini de oluştur (ayrı dosya, WP1.9)

    step_ituhelper(con, settings, offline=args.offline)
    if not args.skip_obs:
        try:
            step_obs_plans(con, settings)
            dropped = step_dedupe_plans(con)
            if dropped:
                print(f"↺ {dropped} itu-helper planı OBS sürümüyle değiştirildi")
        except Exception as exc:  # noqa: BLE001
            print(f"⚠️  OBS plan adımı başarısız: {exc}", file=sys.stderr)
            print("    Eski veri korundu. --skip-obs ile devam edebilirsin.", file=sys.stderr)
        if getattr(args, "all_programs", False):
            try:
                stats = step_all_second_plans(con, settings)
                print(f"🌍 Tüm programlar: {stats['plans']} ÇAP/yandal planı, "
                      f"{stats['slots']} slot ({stats['errors']} hata)")
                # ★ Ayrıştırılamayan satırlar SESSİZCE geçilmiyor. 22.08.2026'da
                # ELK planlarında 435 satır böyle kaybolmuştu ve hiçbir yerde
                # yazmıyordu; plan "5 ders" görünüyordu.
                if obs_plan.dropped_rows:
                    planlar = {p for p, _ in obs_plan.dropped_rows}
                    print(f"⚠️  {len(obs_plan.dropped_rows)} satır ayrıştırılamadı "
                          f"({len(planlar)} planda) — örnek: "
                          f"{obs_plan.dropped_rows[0][1][:3]}", file=sys.stderr)
            except Exception as exc:                           # noqa: BLE001
                print(f"⚠️  Tüm program taraması başarısız: {exc}", file=sys.stderr)
        # ★ Resmî ders denklikleri (OBS DersPlanDenklikleri). Program id'leri
        # önce CLI (--equivalence-program-id), yoksa ayardaki `eq_program_ids`.
        # `--all-equivalences` ya da ayardaki `eq_all_programs` → TÜM lisans
        # programları (kullanıcı isteği 28.08.2026: "diğer programlar için de
        # baksın"). Böylece bir kez ayara yazınca her `make refresh` çekiyor.
        eq_all = getattr(args, "all_equivalences", False) or settings.eq_all_programs
        eq_ids = args.equivalence_program_id or settings.eq_program_ids
        if eq_all or eq_ids:
            try:
                step_equivalence(con, settings, eq_ids, all_programs=eq_all)
            except Exception as exc:  # noqa: BLE001
                print(f"⚠️  Denklik adımı başarısız: {exc}", file=sys.stderr)

    with db.run_step(con, "declared.equivalences") as box:
        # ★★ Faz 28 — beyanlar KULLANICI DB'sine yazılıyor (kişisel veri).
        # `temizle_referans` göç: eski sürümde katalogda kalmış satırları
        # siliyor; o dosya yayınlanan sitenin içine giriyor.
        declared.temizle_referans(con)
        box["rows"] = declared.apply(db.user_db())
    if box["rows"]:
        print(f"🔁 {box['rows']} beyan edilmiş denklik uygulandı "
              f"(config/denklikler.toml)")

    stats = step_prereq(con)
    print(f"\n🌳 Önşart ağacı: {stats['parsed']}/{stats['with_prereq']} ders parse edildi "
          f"({stats['nodes']} düğüm), {stats['repaired']} onarıldı, "
          f"{stats['failed']} çözülemedi")

    # ★ Anlık görüntü: bir sonraki tazelemede "ne değişti" diyebilmek için.
    stamp = changes.take(con)
    diff = changes.compare(con)
    if not diff.empty:
        print(f"\n🔔 Son tazelemeden bu yana {diff.count()} değişiklik "
              f"— ayrıntı: make changes")

    report = step_reports(con)
    findings = step_quality(con, settings)
    print(f"📄 {report.relative_to(config.ROOT)} yazıldı")
    print("\n=== Kalite raporu ===")
    print(quality.format_report(findings))
    print(f"\n🗄  Referans DB: {config.REF_DB}")
    print(f"🔒 Kullanıcı DB: {config.USER_DB} (kişisel veri, repoya commit edilmez)")
    errors = [f for f in findings if f.severity == "error"]
    # ★ Kapanış satırı açık olsun: uyarılar tazelemeyi başarısız yapmaz.
    # Önceden 1081 planın birindeki anomali `make: *** Error 1` veriyordu ve
    # tarama başarılı olmasına rağmen başarısız görünüyordu (21.08.2026).
    if errors:
        print(f"\n❌ Tazeleme bitti ama {len(errors)} HATA var — yukarı bak.")
    else:
        print("\n✅ Tazeleme başarılı. (Uyarılar bilgi amaçlı, veri kullanılabilir.)")
    return 1 if errors else 0


def cmd_plans(args) -> int:
    """Bir program için mevcut planları listeler (keşif aracı).

    ★ BOŞ SONUÇ SESSİZ KALMAZ. Eskiden hiçbir şey basmıyordu; `yandal`
    planlarının neden gelmediğini anlamak için kodu okumak gerekti
    (22.08.2026). Sorulan adresi ve dönen satır sayısını yazmak, "bir şey
    yok" ile "bir şey soruldu ve boş döndü" arasındaki farkı görünür kılıyor.
    """
    settings = config.Settings.load()
    client = ObsClient(settings, archive=False)
    try:
        if getattr(args, "tara", False):
            # Lisansüstü tipleri dışarıda: bu araç lisans öğrencisi için ve
            # her tip bir OBS isteği demek ("OBS'yi yorma" kuralı).
            # Liste AÇIK yazılıyor — "lisans geçmeyenler" gibi bir filtre
            # 'doktora'yı içeri alıyordu.
            LISANS_TIPLERI = ("lisans", "cap", "yandal", "uolp", "on-lisans",
                              "muhendislik-tamamlama", "bilimsel-hazirlik")
            tipler = [t for t in config.PLAN_TYPES if t in LISANS_TIPLERI]
            print(f"'{args.program}' için plan tipleri deneniyor "
                  f"({len(tipler)} istek, aralarda "
                  f"{settings.request_delay_s:g}s bekleme)…\n")
            bulunan = []
            for tip in tipler:
                try:
                    metas = obs_plan.list_plans(client, tip, args.program)
                    isaret = "✅" if metas else "—"
                    print(f"  {isaret} {tip:<24} {len(metas):>3} plan")
                    if metas:
                        bulunan.append(tip)
                        for m in metas[:2]:
                            print(f"       {m['plan_id']:>6}  {(m['title'] or '')[:56]}")
                except Exception as exc:                       # noqa: BLE001
                    print(f"  ❌ {tip:<24} hata: {str(exc)[:70]}")
            print()
            if bulunan:
                print(f"Plan DÖNEN tipler: {', '.join(bulunan)}")
            else:
                print("Hiçbir tipte plan yok — program kodu yanlış olabilir.")
                print(f"Denenen kod: {args.program!r} "
                      f"(genelde 'BLG_LS' gibi, sonda _LS)")
            return 0

        metas = obs_plan.list_plans(client, args.plan_type, args.program)
        print(f"{config.EP['plan_list']}"
              f"?PlanTipiKodu={args.plan_type}&programKodu={args.program}")
        print(f"→ {len(metas)} plan\n")
        for meta in metas:
            host = meta["host_program_code"] or "-"
            print(f"{meta['plan_id']:>6}  host={host:<8} {meta['title']}")
        if not metas:
            print("Bu (tip, program) çifti için OBS plan döndürmedi.")
            print(f"Hangi tiplerde plan var, görmek için:")
            print(f"  make plans P={args.program} ARGS=--tara")
    finally:
        client.close()
    return 0


def cmd_kesif(args) -> int:
    """OBS'ye program kodlarını SOR — tahmin etme.

    Tarayıcı `f"{program}_LS"` varsayıyordu; ÇAP'ta doğru ama yandalda değil:
    yandal programları lisans bölümlerinden bağımsız, FAKÜLTE düzeyinde
    yayınlanıyor. Bu komut kademeli menüyü kullanıp gerçek kodları çıkarıyor.
    """
    settings = config.Settings.load()
    client = ObsClient(settings, archive=False)
    tip = args.plan_type
    try:
        fakulteler = obs_plan.list_faculties(client)
        if not fakulteler:
            print("❌ Fakülte listesi okunamadı — sayfa yapısı değişmiş olabilir.")
            print(f"   Elle bak: {config.EP['plan_page']}")
            return 1
        # ★★ KONTROL İSTEĞİ — sıfır sonucu yorumlanabilir kılan şey bu.
        #
        # 22.08.2026: 23 fakültenin hepsinde 'yandal' 0 program döndü ve
        # bundan "OBS yayınlamıyor" sonucunu çıkardım. Yanlıştı: kullanıcı
        # İşletme'de 3 yandal olduğunu söyledi. Sıfır, "veri yok" da olabilir
        # "cevabı anlayamadım" da — kontrol isteği olmadan ayırt edilemez.
        #
        # Bilinen-dolu bir çiftle (fakülte 28 + cap → BLG_LS…) aynı kod
        # yolunu çalıştırıyoruz. O da 0 dönerse sorun BİZDE.
        kontrol_ham, kontrol = obs_plan.list_programs_debug(client, "28", "cap")
        print(f"kontrol isteği (fakülte 28 + cap): {len(kontrol)} program"
              + (f"  {', '.join(kontrol[:4])}" if kontrol else ""))
        if not kontrol:
            print("  ❌ Kontrol isteği de boş — ayrıştırma ya da uç sorunu, "
                  "veri yokluğu değil.")
            print(f"  Ham cevap (ilk 400 karakter):\n    "
                  + repr(kontrol_ham)[:400])
            print("\n  Bu çıktıyı paylaş; cevabın biçimine göre ayrıştırıcı "
                  "düzeltilecek.")
            return 1
        print()

        print(f"{len(fakulteler)} akademik birim, '{tip}' programları "
              f"(aralarda {settings.request_delay_s:g}s)…\n")
        toplam: list[tuple[str, str, str]] = []
        for fid, ad in fakulteler:
            try:
                ham, kodlar = obs_plan.list_programs_debug(client, fid, tip)
            except Exception as exc:                           # noqa: BLE001
                print(f"  ❌ [{fid:>3}] {ad[:38]:<40} hata: {str(exc)[:50]}")
                continue
            # Cevap DOLU ama kod çıkaramadıysak bunu göster — sessiz sıfır yok.
            if not kodlar and ham not in ([], {}, None, ""):
                print(f"  ⁇ [{fid:>3}] {ad[:38]:<40} cevap var, kod "
                      f"çıkarılamadı: {repr(ham)[:90]}")
                continue
            isaret = "✅" if kodlar else "— "
            print(f"  {isaret} [{fid:>3}] {ad[:38]:<40} {len(kodlar):>3} program"
                  + (f"  {', '.join(kodlar[:4])}" if kodlar else ""))
            toplam.extend((fid, ad, k) for k in kodlar)
        print()
        if not toplam:
            print(f"'{tip}' tipinde hiçbir fakültede program dönmedi.")
            print("Kontrol isteği çalıştığı için bu, ayrıştırma hatası DEĞİL —")
            print("OBS bu tipi bu uçtan yayınlamıyor görünüyor. Yine de tek")
            print(f"programda doğrula:  make plans P=BLG_LS T={tip}")
            return 0
        print(f"Toplam {len(toplam)} program kodu.")
        if args.planlar:
            print(f"\nHer kod için plan listesi ({len(toplam)} istek daha)…\n")
            planli = 0
            for fid, ad, kod in toplam:
                try:
                    metas = obs_plan.list_plans(client, tip, kod)
                except Exception as exc:                       # noqa: BLE001
                    print(f"  ❌ {kod:<16} hata: {str(exc)[:50]}")
                    continue
                if metas:
                    planli += 1
                    print(f"  ✅ {kod:<16} {len(metas):>3} plan   "
                          f"{(metas[0]['title'] or '')[:44]}")
            print(f"\n{planli}/{len(toplam)} kodda plan var.")
        else:
            print("Plan listesini de görmek için: --planlar")
    finally:
        client.close()
    return 0


def cmd_sequence(args) -> int:
    """ÇAP planını önşart kademelerine ayırıp yazdırır."""
    from . import sequence

    settings = config.Settings.load()
    con = db.reference_db()
    plan_id = args.plan_id or settings.second_plan_id
    if plan_id is None:
        row = con.execute(
            "SELECT id FROM plan WHERE program_code=? AND plan_type='cap' LIMIT 1",
            (settings.second_program,)).fetchone()
        plan_id = row[0] if row else None
    if plan_id is None:
        print("Plan bulunamadı. config/settings.toml içindeki cap_plan_id'yi doldur.",
              file=sys.stderr)
        return 1
    title = con.execute("SELECT title FROM plan WHERE id=?", (plan_id,)).fetchone()
    steps = sequence.plan_sequence(con, plan_id)
    print(sequence.format_sequence(steps, title[0] if title else f"plan {plan_id}"))

    anadal = con.execute(
        """SELECT id FROM plan WHERE program_code=? AND plan_type='lisans'
            ORDER BY (source='obs') DESC, id DESC LIMIT 1""",
        (settings.anadal_program,)).fetchone()
    hidden = sequence.hidden_prerequisites(con, plan_id, anadal[0] if anadal else None)
    print(sequence.format_hidden(hidden, con))
    return 0




def cmd_programs(args) -> int:
    """İkinci program adaylarını listeler: hangi plan id'sini yazacağını gösterir."""
    settings = config.Settings.load()
    con = db.reference_db()
    plan_type = args.tur or config.plan_type_of(settings.second_kind)
    rows = con.execute(
        """SELECT id, program_code, host_program_code, title, source
           FROM plan WHERE plan_type=? ORDER BY program_code, id DESC""",
        (plan_type,)).fetchall()
    if args.ara:
        needle = args.ara.upper()
        rows = [r for r in rows
                if needle in ((r["program_code"] or "") + " " + (r["title"] or "")).upper()]
    if not rows:
        print(f"'{plan_type}' tipinde plan yok. `make refresh` gerekebilir "
              f"(config/settings.toml -> second_kind = \"{plan_type}\").", file=sys.stderr)
        return 1
    print(f"{plan_type.upper()} PLANLARI ({len(rows)})\n")
    for r in rows:
        n = con.execute("SELECT COUNT(*) FROM plan_slot WHERE plan_id=?", (r["id"],)).fetchone()[0]
        host = f" · anahtar: {r['host_program_code']}" if r["host_program_code"] else ""
        print(f"  {r['id']:>6}  {r['program_code'] or '?':<8} {n:>3} slot{host}")
        print(f"          {(r['title'] or '')[:88]}")
    print(f"\nSeçtiğini config/settings.toml içine yaz:\n"
          f'  second_kind    = "{plan_type}"\n'
          f'  {plan_type}_program = "..."\n'
          f"  {plan_type}_plan_id = <id>")
    return 0


def cmd_basvuru(args) -> int:
    """FAZ 12 — hangi programlara başvurabilirim, nerede ne kadar iş kalır."""
    from . import basvuru as B

    settings = config.Settings.load()
    con = db.reference_db()
    ucon = db.user_db()
    sid = args.student or 1
    kind = args.tur or (settings.second_kind
                        if settings.second_kind in ("cap", "yandal") else "cap")
    con.row_factory = __import__("sqlite3").Row
    s = B.survey(con, ucon, sid, kind, anadal=settings.anadal_program,
                 exclude={settings.anadal_program, settings.second_program})
    print(B.describe(s))
    return 0


def cmd_student(args) -> int:
    """Öğrenci kaydını kurar: anadal + ÇAP planlarına bağlar."""
    from . import student as S

    settings = config.Settings.load()
    con = db.reference_db()
    ucon = db.user_db()
    anadal_id, cap_id = _resolve_plans(con, settings)
    if anadal_id is None or cap_id is None:
        print("Planlar bulunamadı — önce `make refresh` çalıştır.", file=sys.stderr)
        return 1

    student_id = S.ensure_student(ucon, args.label)
    S.enroll(ucon, student_id, anadal_id, "ANADAL", settings.anadal_program)
    S.enroll(ucon, student_id, cap_id, settings.second_role or "CAP",
             settings.second_program)
    print(f"✅ Öğrenci #{student_id} ({args.label})")
    for row in S.enrollments(ucon, student_id):
        plan = con.execute("SELECT title FROM plan WHERE id=?", (row["plan_id"],)).fetchone()
        print(f"   {row['role']:<7} {row['program_code']:<6} plan {row['plan_id']}  "
              f"{(plan[0] if plan else '')[:48]}")

    dest = S.write_template(con, [anadal_id, cap_id], args.template, args.overwrite)
    print(f"\n📝 Transkript şablonu: {dest}")
    if dest.name.endswith("-yeni.txt"):
        print("   (mevcut transkript.txt korundu — üzerine yazmak için --overwrite)")
    print("   Aldığın derslerin başındaki '# ' işaretini sil, notunu yaz.")
    print(f"   Sonra:  make transcript FILE={dest.name}")
    return 0


def cmd_transcript(args) -> int:
    from . import student as S

    con = db.reference_db()
    ucon = db.user_db()
    student_id = S.ensure_student(ucon, args.label)

    if args.action == "clear":
        print(f"🗑  {S.clear(ucon, student_id)} kayıt silindi")
        return 0

    if args.action == "list":
        rows = ucon.execute(
            """SELECT course_code, grade, status, source FROM earned_course
               WHERE student_id=? ORDER BY course_code""", (student_id,)).fetchall()
        for row in rows:
            mark = "?" if row["source"] == "manual-nograde" else " "
            print(f"  {row['course_code']:<11} {row['grade'] or '--':<3}{mark} {row['status']}")
        print(f"\n{len(rows)} kayıt")
        return 0

    # add
    if args.file:
        text = Path(args.file).read_text(encoding="utf-8")
    else:
        print("Ders kodlarını yapıştır, bitince Ctrl-D:", file=sys.stderr)
        text = sys.stdin.read()
    entries, bad = S.parse_text(text)
    known = {r[0] for r in con.execute("SELECT code FROM course")}
    unknown = [e.course_code for e in entries if e.course_code not in known]

    # ★ Silici yazmadan ÖNCE yedek. Sunucu tarafında (Faz 9) vardı, komut
    # satırında YOKTU — aynı tehlikeli işlem nereden çağrıldığına göre farklı
    # davranıyordu. `--replace` ile yanlış dosya vermek transkripti siliyordu
    # (22.08.2026, bu oldu).
    if args.replace:
        saved = S.backup(ucon, student_id)
        S.prune_backups()
        if saved:
            print(f"💾 Yedek: {saved}")
    n = S.add_entries(ucon, student_id, entries, args.term, replace=args.replace)
    if args.replace and not entries:
        print("⚠️  Dosyada hiç ders yoktu — transkript BOŞALDI. "
              "Geri almak için yukarıdaki yedeği yükle:", file=sys.stderr)
        print(f"    make transcript FILE={saved}" if saved else "", file=sys.stderr)
    n_nograde = sum(1 for e in entries if e.status == "PASSED" and not e.grade_known)
    n_running = sum(1 for e in entries if e.status == "IN_PROGRESS")
    n_failed = sum(1 for e in entries if e.status == "FAILED")
    print(f"✅ {n} ders kaydedildi — {n_nograde} notsuz, {n_running} devam ediyor, "
          f"{n_failed} başarısız")
    if unknown:
        print(f"⚠️  {len(unknown)} ders kataloğda yok (kod hatası olabilir): "
              f"{', '.join(unknown[:10])}")
    if bad:
        print(f"⚠️  {len(bad)} satır çözülemedi: {bad[:5]}")

    settings = config.Settings.load()
    anadal_id, cap_id = _resolve_plans(con, settings)
    plans = [p for p in (anadal_id, cap_id) if p]
    if plans:
        from . import progress as PR
        written = PR.rebuild_fulfillment(con, ucon, student_id,
                                         plans, S.grades(ucon, student_id))
        print(f"🔗 {written} slot eşlendi")
    return 0


def cmd_progress(args) -> int:
    from . import progress as PR
    from . import student as S

    con = db.reference_db()
    ucon = db.user_db()
    student_id = S.ensure_student(ucon, args.label)
    settings = config.Settings.load()
    _, cap_id = _resolve_plans(con, settings)
    print(PR.report(con, ucon, student_id, cap_id))
    return 0


def cmd_recommend(args) -> int:
    """FAZ 5 — bu döneme çakışmasız ders programı önerileri."""
    from . import recommend as REC
    from . import student as S

    settings = config.Settings.load()
    con = db.reference_db()
    ucon = db.user_db()
    student_id = S.ensure_student(ucon, args.label)
    anadal_id, cap_id = _resolve_plans(con, settings)

    cands = REC.candidates(con, ucon, student_id, anadal_id, cap_id,
                           settings.anadal_program, settings.second_program,
                           settings.allowed_programs, settings.unit)
    if not cands:
        print("Bu dönem alabileceğin aday ders bulunamadı.\n"
              "  · ders programı henüz yayınlanmamış olabilir (make refresh)\n"
              "  · ya da tüm slotların dolu")
        return 0

    only = (args.only or "").upper()
    if only in ("CAP", "ANADAL"):
        cands = [c for c in cands if c.role == only]
    print(REC.format_candidates(cands, args.top))

    max_load = args.limit if args.limit is not None else settings.max_load
    schedules = REC.build_schedules(cands, max_load=max_load, limit=args.count,
                                    pinned=args.pin or [])
    if not schedules:
        print(f"\nÇakışmasız kombinasyon üretilemedi. --limit {max_load:g} "
              f"{settings.unit_label} sınırını artırmayı dene.")
        return 0
    for i, schedule in enumerate(schedules, 1):
        print(REC.format_schedule(schedule, cands, i))

    if cap_id:
        blockers = REC.cap_blockers(
            con, ucon, student_id, cap_id, settings.second_program,
            settings.allowed_programs)
        n_lessons = con.execute("SELECT COUNT(*) FROM lesson").fetchone()[0]
        text = REC.format_blockers(blockers, n_lessons)
        if text:
            print(text)
    print("\n⚠️  Bu araç bilgilendirme amaçlıdır. Ders kayıt kararların için "
          "danışmanına ve OBS'ye danış.")
    return 0


def cmd_equivalence(args) -> int:
    """Elle denklik beyanı ekler (config/denklikler.toml).

    ★★ Faz 28: BEYANLAR ARTIK KULLANICI DB'SİNDE. Liste iki dosyayı da
    okuyor — resmî denklikler katalogda, beyanlar `user.sqlite3`'te —
    yoksa kendi eklediğin beyan listede görünmezdi.
    """
    from . import declared

    con = db.reference_db()
    ucon = db.user_db()
    if args.action == "list":
        rows = []
        for kaynak, baglanti in (("katalog", con), ("beyan", ucon)):
            try:
                rows += [(kaynak, baglanti, r) for r in baglanti.execute(
                    """SELECT e.id, e.target_course, e.confidence, e.note_raw
                       FROM equivalence e
                       ORDER BY e.confidence, e.target_course""").fetchall()]
            except sqlite3.Error:
                continue
        for kaynak, baglanti, row in rows:
            srcs = [r[0] for r in baglanti.execute(
                "SELECT course_code FROM equivalence_source WHERE equivalence_id=?", (row[0],))]
            print(f"  [{row['confidence']:<17}] {' + '.join(srcs)} -> {row['target_course']}")
        print(f"\n{len(rows)} denklik")
        return 0
    path = declared.append(args.target, args.sources, args.min_grade, args.note)
    declared.temizle_referans(con)
    n = declared.apply(ucon)
    print(f"✅ {path} güncellendi, {n} beyan uygulandı")
    print("   ⚠️  Bu SENİN beyanın. Ders saydırma için Fakülte Yönetim Kurulu "
          "kararı gerekebilir — danışmanına doğrulat.")
    return 0


def cmd_ui(args) -> int:
    """FAZ 6 — tek dosyalık arayüz üretir (kişisel veri içerir, paylaşma)."""
    from . import student as S
    from . import ui as UI

    settings = config.Settings.load()
    con = db.reference_db()
    ucon = db.user_db()
    student_id = S.ensure_student(ucon, args.label)
    anadal_id, cap_id = _resolve_plans(con, settings)
    data = UI.collect(con, ucon, student_id, settings, anadal_id, cap_id,
                      max_load=args.limit, n_schedules=args.count,
                      donem=args.donem)
    dest = UI.write(data, args.out)
    print(f"✅ {dest}")
    print(f"   {len(data['candidates'])} aday · {len(data['schedules'])} program · "
          f"{len(data['blockers'])} engel")
    print("   Tarayıcıda aç:  open " + str(dest))
    print("   ⚠️  Bu dosya notlarını içerir. Paylaşma, bir yere yükleme.")
    return 0




def cmd_watch(args) -> int:
    """FAZ 11 — kontenjan nöbeti."""
    from . import watch

    return watch.run(every=args.every, once=args.once,
                     only_good=args.only_good, skip_obs=args.skip_obs,
                     kayit=args.kayit)


def cmd_nobet(args) -> int:
    """FAZ 53 — nöbeti arka planda (macOS launchd) kur / kaldır / durum."""
    from . import nobet_servisi as NS

    if args.eylem == "kur":
        return NS.kur(every=args.every, only_good=args.only_good)
    if args.eylem == "kaldir":
        return NS.kaldir()
    return NS.durum()


def cmd_plan_info(args) -> int:
    """Tek bir planın ham durumu — 'bu plan neden boş' sorusu için."""
    con = db.reference_db()
    plan = con.execute("SELECT * FROM plan WHERE id=?", (args.plan_id,)).fetchone()
    if plan is None:
        print(f"Plan {args.plan_id} veritabanında yok.", file=sys.stderr)
        return 1
    for key in plan.keys():
        print(f"  {key:<20} {plan[key]}")
    kinds = con.execute(
        """SELECT slot_kind, COUNT(*) FROM plan_slot WHERE plan_id=?
           GROUP BY slot_kind""", (args.plan_id,)).fetchall()
    print(f"\n  slotlar: {dict(kinds) or 'YOK'}")
    hosts = [r[0] for r in con.execute(
        "SELECT program_code FROM plan_host_program WHERE plan_id=?", (args.plan_id,))]
    print(f"  geçerli olduğu anadal programları: {len(hosts)}"
          + (f" ({', '.join(hosts[:8])}…)" if hosts else ""))
    for row in con.execute(
        """SELECT slot_kind, course_code, pool_label_raw, credits FROM plan_slot
           WHERE plan_id=? ORDER BY position LIMIT 15""", (args.plan_id,)
    ):
        print(f"    {row[0]:<14} {row[1] or row[2] or '?':<28} {row[3] or ''}")
    if plan["source_url"]:
        print(f"\n  Tarayıcıda aç:  {plan['source_url']}")
    if not kinds and plan["has_course_table"]:
        print("\n  ⚠️  Sayfada ders tablosu VAR ama slot üretilmemiş.")
        print("      Bu plan senin planın değilse seni etkilemez.")
    return 0


def cmd_suggest(args) -> int:
    """FAZ 10 — aday denklikleri listeler (uygulamaz)."""
    from . import discover
    from . import student as S

    settings = config.Settings.load()
    con = db.reference_db()
    ucon = db.user_db()
    student_id = S.ensure_student(ucon, args.label)
    anadal_id, second_id = _resolve_plans(con, settings)
    items = discover.suggest(con, ucon, student_id,
                             [(anadal_id, "ANADAL"),
                              (second_id, settings.second_role or "CAP")])
    print(discover.format_suggestions(items))
    return 0


def cmd_changes(args) -> int:
    """FAZ 9 — iki tazeleme arası ne değişti."""
    settings = config.Settings.load()
    con = db.reference_db()
    ucon = db.user_db()
    watch = None if args.all else _watch_codes(con, ucon, settings)
    diff = changes.compare(con, since=args.since, until=args.until, watch=watch)
    print(changes.format_diff(diff, watching=len(watch or ())))
    have = changes.stamps(con)
    if len(have) < 2:
        print(f"\n(şu an {len(have)} anlık görüntü var; "
              f"`make refresh` çalıştırdıkça birikiyor)")
    return 0


def cmd_app(args) -> int:
    """FAZ 8 — yerel uygulama: arayüzden program/dönem/transkript düzenlenir."""
    from . import server

    return server.serve(port=args.port, label=args.label, n_schedules=args.count,
                        max_load=args.limit, open_browser=not args.no_browser)


def cmd_notdagilimi(args) -> int:
    """FAZ 38 — ders not dağılımlarını OBS'den çek.

    ★★ FAZ 38b — VARSAYILAN KAPSAM GENİŞLETİLDİ (kullanıcı: "daha çok
    dersin not dağılımı olması lazım").

    Eski varsayılan yalnız **plandaki** derslerdi (251 ders). Ama araç
    plan dışı ders de ekletiyor (Faz 25/B1): katalog aramasından çıkan her
    ders programa girebiliyor ve orada dağılım YOKTU. Yeni varsayılan
    "bu dönem gerçekten alabileceğin her ders": plan dersleri **+ açık
    şubesi olan dersler**. Ölçüm: 1793 tekil ders, ~30 dk.

    ⚠️ Yine de bütün katalog DEĞİL. 10792 dersin çoğunun bu dönem şubesi
    yok; kimsenin bakamayacağı 3600 ders için İTÜ sunucusunu yarım saat
    daha yormak ölçüsüz olurdu. İsteyen `--hepsi` diyebilir (~1,5 saat).
    `--plan` eski dar kapsamı geri getirir.
    """
    con = db.reference_db()
    settings = config.Settings.load()
    year = args.yil or config.term_year(settings.term)
    if not year:
        print("❌ yıl çıkarılamadı; --yil ver (örn. --yil 2026)", file=sys.stderr)
        return 1

    if args.ders:
        kodlar = [k.strip().upper() for k in args.ders if k.strip()]
    elif args.hepsi:
        kodlar = [r[0] for r in con.execute("SELECT code FROM course ORDER BY code")]
    else:
        # ⚠️ `resolve_plans` yalnız İLK ikinci programı verir; ÇAP + yandal
        # birlikteyken yandalın dersleri sessizce dışarıda kalırdı.
        from .plans import anadal_plan as _anadal_plan
        from .plans import resolve_seconds as _resolve_seconds

        plan_ids = [p for p in [_anadal_plan(con, settings),
                                *(s["planId"] for s in _resolve_seconds(con, settings))]
                    if p]
        if not plan_ids:
            print("❌ plan bulunamadı; önce `make refresh`", file=sys.stderr)
            return 1
        marks = ",".join("?" * len(plan_ids))
        kodlar = sorted({r[0] for r in con.execute(
            f"""SELECT course_code FROM plan_slot
                WHERE plan_id IN ({marks}) AND course_code IS NOT NULL
                UNION
                SELECT po.course_code FROM pool_option po
                  JOIN plan_slot ps ON ps.id = po.slot_id
                 WHERE ps.plan_id IN ({marks})""",
            plan_ids + plan_ids) if r[0]})
        if not args.plan:
            # ★ Faz 38b — açık şubesi olan her ders. Plan dışı ekleme
            # (Faz 25/B1) bunları programa sokabiliyor; dağılımsız
            # bırakmak, aracın en çok kullanılan arama yolunu kör bırakırdı.
            kodlar = sorted(set(kodlar) | {r[0] for r in con.execute(
                "SELECT DISTINCT course_code FROM lesson "
                "WHERE course_code IS NOT NULL") if r[0]})

    # ★ TR/EN çiftini İKİ KEZ sormuyoruz: kaynak zaten ikisini birleştirip
    # dönüyor. Zaten bilinen bir takma adı olan kodu atlıyoruz.
    kalan, gorulen = [], set()
    for kod in kodlar:
        key = notlar.lookup(con, kod)
        if key and key in gorulen:
            continue
        kalan.append(kod)
    kodlar = kalan

    print(f"▶  {len(kodlar)} ders · yıl {year} "
          f"(istek arası {settings.request_delay_s:g} sn)")
    client = ObsClient(settings)
    ok = yok = hata = 0
    try:
        for i, kod in enumerate(kodlar, 1):
            if notlar.lookup(con, kod) in gorulen:
                continue
            try:
                dist = obs_notdagilimi.fetch(client, kod, year)
            except notlar.NotFound:
                notlar.store_missing(con, kod, year)
                yok += 1
            except Exception as exc:            # noqa: BLE001
                hata += 1
                print(f"   ⚠️  {kod}: {type(exc).__name__}: {exc}")
            else:
                notlar.store(con, dist, year)
                gorulen.add(dist.key)
                ok += 1
            if args.verbose or i % 25 == 0:
                print(f"   {i}/{len(kodlar)} · ✔{ok} ·  yayınlanmamış {yok}"
                      f" · hata {hata}")
    except KeyboardInterrupt:
        print("\n⏹  durduruldu — o ana kadar çekilenler KAYITLI.")
    finally:
        client.close()
    print(f"✅ {ok} ders dağılımı · {yok} yayınlanmamış · {hata} hata")
    if hata:
        print("   ⚠️  Hatalı dersler tekrar denenebilir; kayıtlılar korunuyor.")
    return 0


def cmd_verify(args) -> int:
    """Faz 1 bitiş kriterlerini raporlar (OBS ile gözle karşılaştırmak için)."""
    con = db.reference_db()
    text, passed = verify.report(con, config.Settings.load())
    print(text)
    return 0 if passed else 1


def cmd_fixture(args) -> int:
    """Bir plan detay sayfasını test fixture'ı olarak kaydeder (ağsız parser testi)."""
    settings = config.Settings.load()
    client = ObsClient(settings, archive=False)
    try:
        html = client.get(f"{config.EP['plan_detail']}/{args.plan_id}")
    finally:
        client.close()
    dest = config.ROOT / "tests" / "fixtures" / f"cap_plan_{args.plan_id}.html"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(html, encoding="utf-8")
    print(f"✅ {dest} ({len(html)} bayt)")
    return 0


def cmd_status(args) -> int:
    con = db.reference_db()
    q = lambda s: con.execute(s).fetchone()[0]  # noqa: E731
    print(f"course              : {q('SELECT COUNT(*) FROM course')}")
    print(f"program             : {q('SELECT COUNT(*) FROM program')}")
    print(f"plan (toplam)       : {q('SELECT COUNT(*) FROM plan')}")
    n_cap = q("SELECT COUNT(*) FROM plan WHERE plan_type='cap'")
    print(f"plan (ÇAP)          : {n_cap}")
    print(f"plan_slot           : {q('SELECT COUNT(*) FROM plan_slot')}")
    print(f"pool_option         : {q('SELECT COUNT(*) FROM pool_option')}")
    print(f"equivalence         : {q('SELECT COUNT(*) FROM equivalence')}")
    print(f"lesson              : {q('SELECT COUNT(*) FROM lesson')}")
    print(f"lesson_meeting      : {q('SELECT COUNT(*) FROM lesson_meeting')}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="itucap", description="İTÜ ÇAP ders planı veri pipeline'ı")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("refresh", help="tüm veriyi tazele")
    r.add_argument("--skip-obs", action="store_true", help="sadece itu-helper verisi")
    r.add_argument("--offline", action="store_true", help="indirme yapma, diskteki dosyaları kullan")
    r.add_argument("--equivalence-program-id", type=int, nargs="*", default=[],
                   help="denklik taraması yapılacak OBS ProgramId'leri")
    r.add_argument("--all-equivalences", action="store_true",
                   help="TÜM lisans programlarının denkliklerini tara (yavaş; OBS gerekir)")
    r.add_argument("--all-programs", action="store_true",
                   help="HER programın ÇAP/yandal planını çek (yavaş; OBS gerekir)")
    r.set_defaults(func=cmd_refresh)

    l = sub.add_parser("plans", help="bir program için OBS planlarını listele")
    l.add_argument("program", help="OBS program kodu, ör. BLG_LS")
    l.add_argument("--plan-type", default="cap", choices=config.PLAN_TYPES)
    l.add_argument("--tara", action="store_true",
                   help="tüm plan tiplerini dene — hangisinde plan var?")
    l.set_defaults(func=cmd_plans)

    k = sub.add_parser("kesif",
                       help="OBS'ye sor: bu plan tipinde hangi programlar var")
    k.add_argument("--plan-type", default="yandal", choices=config.PLAN_TYPES)
    k.add_argument("--planlar", action="store_true",
                   help="bulunan her program için plan listesini de çek")
    k.set_defaults(func=cmd_kesif)

    v = sub.add_parser("verify", help="Faz 1 bitiş kriterleri raporu")
    v.set_defaults(func=cmd_verify)

    q = sub.add_parser("sequence", help="ÇAP planını önşart kademelerine ayır")
    q.add_argument("--plan-id", type=int, default=None)
    q.set_defaults(func=cmd_sequence)

    st = sub.add_parser("student", help="öğrenci kaydı + transkript şablonu üret")
    st.add_argument("--label", default="ben")
    st.add_argument("--template", type=Path, default=None)
    st.add_argument("--overwrite", action="store_true",
                    help="mevcut transkript dosyasının üzerine yaz (dikkat: veri kaybı)")
    st.set_defaults(func=cmd_student)

    tr = sub.add_parser("transcript", help="geçilen dersleri gir / listele / sil")
    tr.add_argument("action", choices=["add", "list", "clear"])
    tr.add_argument("--file", default=None, help="ders listesi dosyası (yoksa stdin)")
    tr.add_argument("--term", default="", help="dönem etiketi (isteğe bağlı)")
    tr.add_argument("--replace", action="store_true", help="eskileri silip baştan yaz")
    tr.add_argument("--label", default="ben")
    tr.set_defaults(func=cmd_transcript)

    pg = sub.add_parser("progress", help="anadal + ÇAP ilerleme paneli")
    pg.add_argument("--label", default="ben")
    pg.set_defaults(func=cmd_progress)

    rc = sub.add_parser("recommend", help="çakışmasız ders programı önerileri")
    rc.add_argument("--limit", type=float, default=None,
                    help="dönem yük üst sınırı (birim config/settings.toml'da)")
    rc.add_argument("--ects", type=float, dest="limit", help=argparse.SUPPRESS)
    rc.add_argument("--count", type=int, default=3, help="kaç alternatif program")
    rc.add_argument("--top", type=int, default=12, help="listelenecek aday sayısı")
    rc.add_argument("--only", default=None, choices=["cap", "anadal", "CAP", "ANADAL"])
    rc.add_argument("--pin", action="append", help="bu ders mutlaka olsun (tekrarlanabilir)")
    rc.add_argument("--label", default="ben")
    rc.set_defaults(func=cmd_recommend)

    ui = sub.add_parser("ui", help="tek dosyalık arayüz üret")
    ui.add_argument("--limit", type=float, default=None)
    ui.add_argument("--ects", type=float, dest="limit", help=argparse.SUPPRESS)
    ui.add_argument("--count", type=int, default=3)
    ui.add_argument("--donem", type=int, default=None,
                    help="bulunduğun dönem (1..8); yazmazsan settings/otomatik")
    ui.add_argument("--out", type=Path, default=None)
    ui.add_argument("--label", default="ben")
    ui.set_defaults(func=cmd_ui)

    app = sub.add_parser("app", help="yerel uygulama: sayfadan düzenlenebilir arayüz")
    app.add_argument("--port", type=int, default=8770)
    app.add_argument("--limit", type=float, default=None)
    app.add_argument("--count", type=int, default=3)
    app.add_argument("--label", default="ben")
    app.add_argument("--no-browser", action="store_true")
    app.set_defaults(func=cmd_app)

    w = sub.add_parser("watch", help="kontenjan nöbeti: değişince haber ver")
    w.add_argument("--every", type=int, default=600, help="saniye (en az 300)")
    w.add_argument("--once", action="store_true", help="tek tur çalış ve çık")
    w.add_argument("--only-good", action="store_true",
                   help="yalnız FIRSAT bildir (yer açıldı / ders açıldı)")
    w.add_argument("--skip-obs", action="store_true")
    # ★ Kayıt günü kipi: 1 dk aralık, 2 saat sonra kendiliğinden durur.
    # AÇIKÇA istenmesi gerekiyor — sınırı topluca düşürmek İTÜ sunucularını
    # gereksiz yormak olurdu.
    w.add_argument("--kayit", action="store_true",
                   help="kayıt günü kipi: 1 dk aralık, 2 saat sonra durur")
    w.set_defaults(func=cmd_watch)

    # ★ Faz 53 — arka plan nöbeti (yapılacaklar 4.2). `--kayit` BİLEREK yok:
    # 1 dk'lık kip arka planda unutulup günlerce dönmemeli.
    nb = sub.add_parser("nobet", help="nöbeti arka planda çalıştır (macOS launchd)")
    nb.add_argument("eylem", choices=["kur", "kaldir", "durum"])
    nb.add_argument("--every", type=int, default=600, help="saniye (en az 300)")
    nb.add_argument("--only-good", action="store_true",
                    help="yalnız FIRSAT bildir (yer açıldı / ders açıldı)")
    nb.set_defaults(func=cmd_nobet)

    nd = sub.add_parser("notdagilimi",
                        help="ders not dağılımlarını OBS'den çek (Faz 38)")
    nd.add_argument("--yil", type=int, default=None,
                    help="akademik yılın BİTİŞ yılı (202610 → 2026)")
    nd.add_argument("--hepsi", action="store_true",
                    help="BÜTÜN katalog (~5400 istek, ~1,5 saat)")
    nd.add_argument("--plan", action="store_true",
                    help="yalnız planındaki dersler (dar kapsam, ~4 dk)")
    nd.add_argument("--ders", action="append",
                    help="yalnız bu ders (tekrarlanabilir)")
    nd.add_argument("--verbose", action="store_true")
    nd.set_defaults(func=cmd_notdagilimi)

    pi = sub.add_parser("plan-info", help="bir planın ham durumu (neden boş?)")
    pi.add_argument("plan_id", type=int)
    pi.set_defaults(func=cmd_plan_info)

    sg = sub.add_parser("suggest", help="aday denklikleri bul (aldığın ders = plandaki ders)")
    sg.add_argument("--label", default="ben")
    sg.set_defaults(func=cmd_suggest)

    ch = sub.add_parser("changes", help="son iki tazeleme arasında ne değişti")
    ch.add_argument("--all", action="store_true",
                    help="yalnız kendi derslerin değil, HER ders")
    ch.add_argument("--since", default=None, help="anlık görüntü damgası")
    ch.add_argument("--until", default=None)
    ch.set_defaults(func=cmd_changes)

    pr = sub.add_parser("programs", help="ikinci program (ÇAP/yandal) planlarını listele")
    pr.add_argument("--tur", choices=["cap", "yandal"], default=None,
                    help="plan tipi; yazmazsan settings.second_kind")
    pr.add_argument("--ara", default=None, help="program kodu ya da başlıkta ara")
    pr.set_defaults(func=cmd_programs)

    bv = sub.add_parser("basvuru", help="hangi ÇAP/yandal programlarına başvurabilirim")
    bv.add_argument("--tur", choices=["cap", "yandal"], default=None,
                    help="plan tipi; yazmazsan settings.second_kind")
    bv.add_argument("--student", type=int, default=None)
    bv.set_defaults(func=cmd_basvuru)

    eq = sub.add_parser("equivalence", help="elle denklik beyanı")
    eq.add_argument("action", choices=["add", "list"])
    eq.add_argument("--target", help="yerine sayılacak ders, ör. MAT 210E")
    eq.add_argument("--sources", nargs="*", default=[], help="elindeki ders(ler)")
    eq.add_argument("--min-grade", default="DD")
    eq.add_argument("--note", default="")
    eq.set_defaults(func=cmd_equivalence)

    f = sub.add_parser("fixture", help="plan detay HTML'ini test fixture'ı olarak kaydet")
    f.add_argument("plan_id", type=int)
    f.set_defaults(func=cmd_fixture)

    s = sub.add_parser("status", help="veritabanı özeti")
    s.set_defaults(func=cmd_status)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
