-- Families: one row per household. The code shown to users is built from id.
CREATE TABLE families (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    family_name     TEXT NOT NULL,
    head_member_id  INTEGER REFERENCES members(id) ON DELETE SET NULL,
    address         TEXT,
    area            TEXT,
    city            TEXT,
    pincode         TEXT,
    phone           TEXT,
    native_place    TEXT,
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- Members: every person. The member code is built from id; the Yuvak Mandal
-- code is built from yuvak_no, which is assigned once and never reused.
CREATE TABLE members (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    family_id        INTEGER REFERENCES families(id) ON DELETE SET NULL,
    first_name       TEXT NOT NULL,
    middle_name      TEXT,
    last_name        TEXT,
    gender           TEXT NOT NULL CHECK (gender IN ('M', 'F', 'O')),
    dob              TEXT,                -- YYYY-MM-DD
    relation_to_head TEXT,
    marital_status   TEXT,
    father_id        INTEGER REFERENCES members(id) ON DELETE SET NULL,
    mother_id        INTEGER REFERENCES members(id) ON DELETE SET NULL,
    spouse_id        INTEGER REFERENCES members(id) ON DELETE SET NULL,
    phone            TEXT,
    email            TEXT,
    address          TEXT,                -- blank means same as family
    area             TEXT,
    city             TEXT,
    profession       TEXT,
    education        TEXT,
    blood_group      TEXT,
    is_deceased      INTEGER NOT NULL DEFAULT 0,
    yuvak_no         INTEGER UNIQUE,
    yuvak_joined_on  TEXT,
    notes            TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at       TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX idx_members_family ON members(family_id);
CREATE INDEX idx_members_father ON members(father_id);
CREATE INDEX idx_members_mother ON members(mother_id);
CREATE INDEX idx_members_name ON members(first_name, last_name);
