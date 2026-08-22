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
