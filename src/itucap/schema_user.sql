-- ============================================================================
--  itucap — KULLANICI VERİTABANI (KİŞİSEL VERİ)
--  WP1.9: referans veriden AYRI dosyada tutulur, repoya commit EDİLMEZ.
--  OBS şifresi hiçbir zaman istenmez, saklanmaz.
-- ============================================================================
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS student (
    id         INTEGER PRIMARY KEY,
    label      TEXT,                 -- 'ben' gibi serbest etiket; ad/no gerekmez
    created_at TEXT
);

-- ★ Öğrenci ↔ plan çok-a-çok (anadal + ÇAP aynı anda)
CREATE TABLE IF NOT EXISTS student_enrollment (
    student_id   INTEGER REFERENCES student(id) ON DELETE CASCADE,
    plan_id      INTEGER,            -- referans DB'deki plan.id (cross-db FK yok)
    role         TEXT CHECK (role IN ('ANADAL', 'CAP', 'YANDAL')),
    program_code TEXT,
    started_term TEXT,
    PRIMARY KEY (student_id, plan_id)
);

CREATE TABLE IF NOT EXISTS earned_course (
    id          INTEGER PRIMARY KEY,
    student_id  INTEGER REFERENCES student(id) ON DELETE CASCADE,
    course_code TEXT,
    grade       TEXT,                -- 'AA'..'FF', '--'
    term        TEXT,
    status      TEXT CHECK (status IN ('PASSED', 'FAILED', 'IN_PROGRESS')),
    source      TEXT,                -- 'manual'|'transcript_pdf'|'paste'
    UNIQUE (student_id, course_code, term)
);

-- ★ ÇAP'ın kalbi: aynı earned_course birden fazla planın slotunu doldurabilir
CREATE TABLE IF NOT EXISTS slot_fulfillment (
    student_id      INTEGER,
    slot_id         INTEGER,         -- referans DB'deki plan_slot.id
    earned_id       INTEGER REFERENCES earned_course(id) ON DELETE CASCADE,
    via_equivalence INTEGER,         -- referans DB'deki equivalence.id, NULL = doğrudan
    is_auto         INTEGER DEFAULT 1,
    decided_at      TEXT,
    PRIMARY KEY (student_id, slot_id)
);
CREATE INDEX IF NOT EXISTS ix_fulfil_earned ON slot_fulfillment(earned_id);

-- ★ FAZ 10: arayüzde kurduğun program. Izgaradaki düzenleme sayfa kapanınca
--   kayboluyordu; motorun ÖNERİSİ ile SENİN seçimin ayrı şeyler ve ikincisi
--   de saklanmalı. `saved_at` boşsa kayıt yok demektir.
CREATE TABLE IF NOT EXISTS saved_pick (
    student_id  INTEGER REFERENCES student(id) ON DELETE CASCADE,
    term        TEXT,
    course_code TEXT,
    crn         TEXT,
    position    INTEGER,
    saved_at    TEXT,
    PRIMARY KEY (student_id, term, course_code)
);

-- ★★ FAZ 77: ALTERNATİF PROGRAMLAR ("Plan B", "Plan C"…). Kayıt gününde
-- dolan bir şube bütün programı değiştirebiliyor; öğrenci birkaç tam program
-- hazırlayıp aralarında geçmek istiyor. `saved_pick` ANA programdır ve
-- değişmedi; alternatifler adlarıyla ayrı tutuluyor, aynı dönem anahtarıyla.
CREATE TABLE IF NOT EXISTS saved_alt (
    student_id  INTEGER REFERENCES student(id) ON DELETE CASCADE,
    term        TEXT,
    name        TEXT,
    course_code TEXT,
    crn         TEXT,
    position    INTEGER,
    saved_at    TEXT,
    PRIMARY KEY (student_id, term, name, course_code)
);

-- ★★ FAZ 28: BEYAN EDİLEN DENKLİKLER ARTIK BURADA (kişisel veri).
--   Eskiden `reference.sqlite3`'e yazılıyordu ve `declared.py` "bunlar kişisel
--   veri DEĞİL, müfredat bilgisi" diyordu. Oysa `tools/gizlilik_denetimi.py`
--   yayınlanan katalogda `confidence='user_declared'` görürse HATA veriyordu:
--   aynı soruya iki kaynak farklı cevap veriyordu. Denetim haklıydı — bir
--   öğrencinin "şu dersim şunun yerine saysın" beyanı, hangi dersleri aldığını
--   ve neye başvurduğunu ele veriyor. Kişisel veri tek dosyada toplanıyor.
--
--   Şema referans DB'dekiyle AYNI: `rules.load_equivalences` ikisini de aynı
--   sorguyla okuyabilsin diye.
CREATE TABLE IF NOT EXISTS equivalence (
    id             INTEGER PRIMARY KEY,
    target_course  TEXT,
    target_plan_id INTEGER,
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
