-- A counter that goes up whenever members or families change, so other open
-- screens (the PC and the phone) know to refresh.
CREATE TABLE IF NOT EXISTS app_state (
    key   TEXT PRIMARY KEY,
    value INTEGER NOT NULL DEFAULT 0
);
INSERT OR IGNORE INTO app_state (key, value) VALUES ('data_version', 0);

-- Login accounts for the shared online version.
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    full_name     TEXT,
    password_hash TEXT NOT NULL,
    is_admin      INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
