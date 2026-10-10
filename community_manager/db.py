"""SQLite connection handling, schema migrations and backups.

To change the database structure later, add a new file to the migrations
folder named with the next number (e.g. 002_add_donations.sql). It runs
once, automatically, the next time the app starts.
"""
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from flask import current_app, g

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def connect(path) -> sqlite3.Connection:
    conn = sqlite3.connect(path, detect_types=0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE"])
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def migrate(path) -> None:
    conn = connect(path)
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " name TEXT PRIMARY KEY,"
            " applied_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')))"
        )
        done = {r["name"] for r in conn.execute("SELECT name FROM schema_migrations")}
        for script in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if script.name in done:
                continue
            with conn:
                conn.executescript(script.read_text(encoding="utf-8"))
                conn.execute("INSERT INTO schema_migrations (name) VALUES (?)", (script.name,))
    finally:
        conn.close()


def backup(path, backup_dir: Path, keep: int) -> Path | None:
    """Copy the database into backup_dir and prune old copies."""
    path = Path(path)
    if not path.exists() or path.stat().st_size == 0:
        return None
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"community-{datetime.now():%Y%m%d-%H%M%S}.db"
    write_backup(path, target)
    copies = sorted(backup_dir.glob("community-*.db"))
    for old in copies[:-keep] if keep > 0 else []:
        old.unlink(missing_ok=True)
    return target


def write_backup(src, target) -> None:
    """Consistent copy of a live SQLite database."""
    source = sqlite3.connect(src)
    dest = sqlite3.connect(target)
    try:
        source.backup(dest)
    finally:
        dest.close()
        source.close()


def is_valid_database(path) -> bool:
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            conn.close()
    except sqlite3.DatabaseError:
        return False
    return {"members", "families"} <= tables


def restore(upload_path, db_path) -> None:
    shutil.copyfile(upload_path, db_path)
