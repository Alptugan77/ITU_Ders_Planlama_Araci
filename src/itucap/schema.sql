-- ============================================================================
--  itucap — REFERANS VERİTABANI ŞEMASI (public veri, kişisel veri YOK)
--  Faz 1. Kullanıcı verisi ayrı dosyada: schema_user.sql
-- ============================================================================
PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------- dersler --
CREATE TABLE IF NOT EXISTS course (
    code              TEXT PRIMARY KEY,          -- 'MAT 103E'
    name              TEXT,
    language          TEXT,
    credits           REAL,
    ects              REAL,
    prereq_raw        TEXT,                      -- ham metin, Faz 2'de parse edilecek
    -- ★ Faz 37 — AD YANILTICI. Kaynak (itu-helper courses.psv, 7. alan) bu
    -- sütuna "Sınıf Kısıtı" diyor ama değerleri KREDİ: 'Yok' / '95,00' /
    -- '60,00' / '30,00'. İTÜ'de sınıf zaten kazanılmış krediyle belirlendiği
    -- için alan bir kredi tabanı. `policy.parse_catalog_floor` okur;
    -- `[katalog_kredi_kosulu]` ile kapatılabilir. Sütun adı DEĞİŞTİRİLMEDİ:
    -- kaynağın adı bu ve yeniden adlandırmak, ham veriyle raporu ayrıştırırdı.
    class_restriction TEXT,
    source            TEXT,
    scraped_at        TEXT
);

-- Faz 2'de doldurulacak; şimdilik boş dursun (şema kararı bugünden verilsin)
CREATE TABLE IF NOT EXISTS prereq_node (
    id          INTEGER PRIMARY KEY,
    course_code TEXT REFERENCES course(code),
    parent_id   INTEGER REFERENCES prereq_node(id),
    node_type   TEXT CHECK (node_type IN ('AND', 'OR', 'LEAF')),
    req_course  TEXT,
    min_grade   TEXT
);
CREATE INDEX IF NOT EXISTS ix_prereq_course ON prereq_node(course_code);

-- ★ GÜVENLİK: metni VAR ama çözemediğimiz önşartlar. Bu kayıtlar 'önşartı yok'
--   ile ASLA karıştırılmamalı — motor bunlar için 'BİLİNMİYOR' döndürür.
CREATE TABLE IF NOT EXISTS prereq_unparsed (
    course_code TEXT PRIMARY KEY,
    prereq_raw  TEXT,
    reason      TEXT,
    seen_at     TEXT
);

-- Onarılarak parse edilen önşartlar (arayüzde uyarı gösterilebilsin diye)
CREATE TABLE IF NOT EXISTS prereq_repair (
    course_code TEXT,
    repair      TEXT,
    PRIMARY KEY (course_code, repair)
);

-- -------------------------------------------------------------- programlar --
CREATE TABLE IF NOT EXISTS program (
    code    TEXT PRIMARY KEY,                    -- 'HTAE', 'BLG'
    name    TEXT,
    faculty TEXT,
    level   TEXT                                 -- 'LS', 'OL', ...
);

-- OBS iç kimlikleri (scraper'ın ihtiyacı; kod<->id eşlemesi)
CREATE TABLE IF NOT EXISTS obs_program_ref (
    obs_program_id INTEGER PRIMARY KEY,          -- DersPlanDenklikleri ProgramId
    program_code   TEXT,                         -- 'BLG'  (çıkarılabildiyse)
    obs_code       TEXT,                         -- 'BLG_LS'
    title          TEXT,
    faculty_id     INTEGER
);

-- ------------------------------------------------------------------ plan --
-- ★ ÇAP DÜZELTMESİ (2026-08-17 keşfi):
--   ÇAP planları (anadal, çap) ÇİFTİNE göre tanımlı: 'TUMMUH_BLG', 'GEO_BLG'...
--   Bu yüzden host_program_code alanı şart. Anadal planlarında NULL'dur.
CREATE TABLE IF NOT EXISTS plan (
    id                INTEGER PRIMARY KEY,       -- OBS DersPlanDetay id'si (stabil)
    program_code      TEXT,                      -- planın ait olduğu program: 'BLG'
    host_program_code TEXT,                      -- ÇAP ise anadal tarafı: 'TUMMUH', 'GEO'
    plan_type         TEXT NOT NULL,             -- 'lisans'|'cap'|'yandal'|'uolp'|...
    obs_program_code  TEXT,                      -- 'BLG_LS'
    title             TEXT,                      -- ham başlık
    iteration         TEXT,                      -- '... After 2018-2019 / Fall Semester'
    is_term_based     INTEGER DEFAULT 1,         -- ÇAP planları 0 (dönemsiz düz liste)
    has_course_table  INTEGER,                   -- OBS sayfasında ders tablosu var mıydı?
                                                 -- 0 + slot yok = kaynakta boş (parse hatası DEĞİL)
    notes_raw         TEXT,                      -- sayfadaki serbest metin notlar
    -- ★ Sayfanın KENDİ yazdığı 'Toplam Kredi'. Doğrulama çıpası:
    --   bizim topladığımız kredi bunu tutmuyorsa ayrıştırma yanlış.
    declared_credits  REAL,
    source            TEXT,                      -- 'obs' | 'itu-helper'
    source_url        TEXT,
    scraped_at        TEXT
);
CREATE INDEX IF NOT EXISTS ix_plan_lookup ON plan(program_code, plan_type, host_program_code);

-- ★ Bir ÇAP planının geçerli olduğu ANADAL programları
--   (OBS DersPlanDetay sayfasındaki "Associated Programs" tablosu)
CREATE TABLE IF NOT EXISTS plan_host_program (
    plan_id      INTEGER REFERENCES plan(id) ON DELETE CASCADE,
    program_code TEXT,                           -- 'HTAE_LS' -> 'HTAE'
    obs_code     TEXT,                           -- ham: 'HTAE_LS'
    program_name TEXT,
    updated_at   TEXT,
    PRIMARY KEY (plan_id, obs_code)
);

-- Planın doldurulması gereken TEK gereksinimi
CREATE TABLE IF NOT EXISTS plan_slot (
    id             INTEGER PRIMARY KEY,
    plan_id        INTEGER REFERENCES plan(id) ON DELETE CASCADE,
    term_no        INTEGER,                      -- ÇAP planlarında NULL
    slot_kind      TEXT CHECK (slot_kind IN ('REQUIRED', 'ELECTIVE_POOL')),
    course_code    TEXT,                         -- REQUIRED ise dolu
    -- ★ Aynı dersin öbür dilindeki kodu/kodları, VİRGÜLLE ayrılmış: 'EEF 110E'.
    --   (Kodun İÇİNDE boşluk var — ayırıcı boşluk OLAMAZ.)
    --   OBS'nin yeni plan sayfaları iki kodu tek hücrede veriyor; ikisi de
    --   slotu doldurur, ikisinin de şubesi önerilebilir.
    alt_course_codes TEXT,
    zs_raw         TEXT,                         -- ham 'Z'/'S' sütunu (atmıyoruz)
    pool_label_raw TEXT,                         -- ham etiket (denetim için ASLA silme)
    pool_category  TEXT,                         -- 'MT'|'ITB'|'TB'|'TM'|'ENG'|'SNT'|'OTHER'
    pool_group_id  TEXT,                         -- OBS grupId (_DersGrupSearch)
    credits        REAL,                         -- tek değerse; aralıksa NULL
    -- ★ Havuz slotunun kredisi ARALIK olabiliyor ("2 / 2,5 / 3"): hangi dersi
    --   seçtiğine bağlı. Aralıktan tek sayı seçmek uydurma olurdu; aralığı
    --   aralık olarak saklıyoruz ve toplamlar buna göre yapılıyor.
    credits_raw    TEXT,
    credits_min    REAL,
    credits_max    REAL,
    ects_raw       TEXT,                         -- '4 / 5 / 6' ya da '4,5' olabilir
    ects           REAL,                         -- tek değerse sayısal karşılığı
    type_raw       TEXT,                         -- OBS 'Type' sütunu: MT/TB/TM/ITB/EC/LA
    position       INTEGER
);
CREATE INDEX IF NOT EXISTS ix_slot_plan ON plan_slot(plan_id);

CREATE TABLE IF NOT EXISTS pool_option (
    slot_id     INTEGER REFERENCES plan_slot(id) ON DELETE CASCADE,
    course_code TEXT,
    PRIMARY KEY (slot_id, course_code)
);

-- -------------------------------------------------------------- denklik --
CREATE TABLE IF NOT EXISTS equivalence (
    id             INTEGER PRIMARY KEY,
    target_course  TEXT,                         -- neyin yerine sayılıyor
    target_plan_id INTEGER,                      -- NULL = tüm planlar
    applies_to_cap INTEGER DEFAULT 1,
    confidence     TEXT CHECK (confidence IN ('official','requires_approval','user_declared')),
    note_raw       TEXT,
    source_url     TEXT,
    scraped_at     TEXT
);

CREATE TABLE IF NOT EXISTS equivalence_source (
    equivalence_id INTEGER REFERENCES equivalence(id) ON DELETE CASCADE,
    course_code    TEXT,
    min_grade      TEXT DEFAULT 'DD',
    PRIMARY KEY (equivalence_id, course_code)
);

-- --------------------------------------------------------- açılan şubeler --
CREATE TABLE IF NOT EXISTS lesson (
    crn             TEXT PRIMARY KEY,
    term            TEXT,
    course_code     TEXT,
    course_title    TEXT,
    instructor      TEXT,
    building        TEXT,
    teaching_method TEXT,
    capacity        INTEGER,
    enrolled        INTEGER,
    major_restr     TEXT,
    -- ★ Faz 37 ölçümü: aşağıdaki İKİ sütun 3417 şubenin HİÇBİRİNDE dolu değil.
    -- Sebep veri kaybı değil: itu-helper `lessons.psv` 11 alan yayınlıyor
    -- (CRN|Kod|Yöntem|Hoca|Bina|Gün|Saat|Derslik|Kontenjan|Yazılan|Programlar)
    -- ve içinde ne önşart ne sınıf kısıtı var. Sütunlar kaldırılmadı çünkü
    -- kaynak yarın yayınlamaya başlayabilir; `quality.kaynak_yayinlamiyor`
    -- kontrolü durumu her taramada rapor ediyor.
    -- ⚠️ Bu sütunların boşluğundan "kısıt yok" SONUCU ÇIKARILMAZ.
    prereq_raw      TEXT,
    class_restr     TEXT,
    updated_at      TEXT
);

CREATE TABLE IF NOT EXISTS lesson_meeting (
    id          INTEGER PRIMARY KEY,
    crn         TEXT REFERENCES lesson(crn) ON DELETE CASCADE,
    day_of_week INTEGER,                         -- 1=Pazartesi ... 7=Pazar
    start_min   INTEGER,                         -- 690 = 11:30
    end_min     INTEGER,
    room        TEXT,
    building    TEXT
);
CREATE INDEX IF NOT EXISTS ix_meeting_crn ON lesson_meeting(crn);
CREATE INDEX IF NOT EXISTS ix_meeting_day ON lesson_meeting(day_of_week, start_min);

-- Bina -> kampüs. Kampüs değişimi öneri puanında ceza olarak kullanılır
-- (Ayazağa <-> Maçka arası gidiş dönüş bir dersi fiilen alınamaz kılabiliyor).
CREATE TABLE IF NOT EXISTS building (
    code   TEXT PRIMARY KEY,
    name   TEXT,
    campus TEXT
);

CREATE TABLE IF NOT EXISTS lesson_allowed_program (
    crn          TEXT REFERENCES lesson(crn) ON DELETE CASCADE,
    program_code TEXT,
    PRIMARY KEY (crn, program_code)
);

-- ------------------------------------------------------------- pipeline --
CREATE TABLE IF NOT EXISTS ingest_run (
    id         INTEGER PRIMARY KEY,
    step       TEXT,
    started_at TEXT,
    ended_at   TEXT,
    status     TEXT,                             -- 'ok'|'fail'|'skip'
    rows       INTEGER,
    message    TEXT
);

CREATE TABLE IF NOT EXISTS quality_finding (
    id       INTEGER PRIMARY KEY,
    run_at   TEXT,
    check_id TEXT,
    severity TEXT,                               -- 'error'|'warn'|'info'
    detail   TEXT
);

-- ★ FAZ 9: dönem başında ne değişti? Her `refresh` bir anlık görüntü bırakır;
--   iki görüntünün farkı "ders açıldı / şube kapandı / kontenjan doldu" der.
--   Kişisel veri DEĞİL — yalnız kamuya açık şube durumu.
-- ★ Görüntünün KENDİSİ ayrı kayıt. Şubesiz bir görüntü (dönem başı, OBS henüz
--   yayınlamadı) `lesson_snapshot`'a hiç satır yazmıyor; ayrı tablo olmasa
--   "boş görüntü" ile "görüntü yok" ayırt edilemezdi ve 'hepsi kapandı' gibi
--   önemli bir değişim görünmez olurdu (21.08.2026, test yakaladı).
CREATE TABLE IF NOT EXISTS snapshot_run (
    taken_at TEXT PRIMARY KEY,
    lessons  INTEGER
);

CREATE TABLE IF NOT EXISTS lesson_snapshot (
    taken_at    TEXT,
    crn         TEXT,
    course_code TEXT,
    capacity    INTEGER,
    enrolled    INTEGER,
    PRIMARY KEY (taken_at, crn)
);
CREATE INDEX IF NOT EXISTS ix_snapshot_course ON lesson_snapshot(course_code);
