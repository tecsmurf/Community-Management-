"""Database connections, schema migrations and backups.

Two kinds of database are supported:

* SQLite, a single file on this computer (the offline Windows version), and
* PostgreSQL, given as a ``postgres://`` URL (the shared online version that
  the PC and phone use together).

The app's SQL is written for SQLite. ``PgConnection`` translates the few
differences so the same code runs on both.

To change the database structure later, add the next numbered file to
``migrations/`` (SQLite) and ``migrations/postgres/`` (PostgreSQL), e.g.
``003_add_donations.sql``. It runs once, automatically, on the next start.
Backups are always SQLite files, whichever database the app uses, so a
backup from the online version restores on the PC and the other way round.
"""
import re
import shutil
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

from flask import current_app, g

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
PG_MIGRATIONS_DIR = MIGRATIONS_DIR / "postgres"

# Tables whose changes other open screens should notice (see data_version).
TRACKED_TABLES = ("members", "families")
# Data copied by backups and restores, in an order that respects references.
BACKUP_TABLES = ("families", "members")
DEFERRED_LINKS = {"families": ("head_member_id",), "members": ("father_id", "mother_id", "spouse_id")}


def is_postgres(target) -> bool:
    return str(target).startswith(("postgres://", "postgresql://"))


def connect(target):
    if is_postgres(target):
        return PgConnection(target)
    return SqliteConnection(target)


def get_db():
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE"])
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


# --------------------------------------------------------------- connections

_WRITE = re.compile(r"^\s*(INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+(\w+)", re.IGNORECASE)


class _Base:
    """Common behaviour: count edits so other screens can refresh."""

    def _note_write(self, sql, rowcount):
        match = _WRITE.match(sql)
        if match and match.group(2).lower() in TRACKED_TABLES and rowcount:
            self._changed = True

    def commit(self):
        if getattr(self, "_changed", False):
            self._changed = False
            self._execute("UPDATE app_state SET value = value + 1 WHERE key = 'data_version'", ())
        self._commit()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, *_):
        if exc_type is None:
            self.commit()
        else:
            self.rollback()

    def data_version(self) -> int:
        row = self.execute("SELECT value FROM app_state WHERE key = 'data_version'").fetchone()
        return row[0] if row else 0


class SqliteConnection(_Base):
    kind = "sqlite"

    def __init__(self, path):
        self.raw = sqlite3.connect(path, detect_types=0)
        self.raw.row_factory = sqlite3.Row
        self.raw.execute("PRAGMA foreign_keys = ON")

    def _execute(self, sql, args):
        return self.raw.execute(sql, args)

    def execute(self, sql, args=()):
        cur = self.raw.execute(sql, args)
        self._note_write(sql, cur.rowcount)
        return cur

    def executescript(self, script):
        self.raw.executescript(script)

    def _commit(self):
        self.raw.commit()

    def rollback(self):
        self.raw.rollback()

    def close(self):
        self.raw.close()


class Row(dict):
    """A result row readable by column name or by position, like sqlite3.Row."""

    def __init__(self, names, values):
        super().__init__(zip(names, values))
        self._values = values

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return super().__getitem__(key)


def _row_factory(cursor):
    names = [c.name for c in cursor.description] if cursor.description else []
    return lambda values: Row(names, values)


class PgCursor:
    def __init__(self, cur, lastrowid=None):
        self._cur, self.lastrowid = cur, lastrowid
        self.rowcount = cur.rowcount

    def fetchone(self):
        return self._cur.fetchone() if self._cur.description else None

    def fetchall(self):
        return self._cur.fetchall() if self._cur.description else []

    def __iter__(self):
        return iter(self.fetchall())


TIMEZONE = "Asia/Kolkata"
_TRANSLATIONS = [
    (re.compile(r"datetime\('now',\s*'localtime'\)"),
     f"to_char(now() AT TIME ZONE '{TIMEZONE}', 'YYYY-MM-DD HH24:MI:SS')"),
    (re.compile(r"([\w.]+) COLLATE NOCASE"), r"lower(\1)"),
    (re.compile(r"\bLIKE\b"), "ILIKE"),
]
_ID_TABLES = ("members", "families", "users")


def translate(sql: str) -> str:
    """SQLite-flavoured SQL -> PostgreSQL."""
    for pattern, repl in _TRANSLATIONS:
        sql = pattern.sub(repl, sql)
    return sql.replace("%", "%%").replace("?", "%s")


class PgConnection(_Base):
    kind = "postgres"

    def __init__(self, url):
        import psycopg  # only needed for the online version

        self.raw = psycopg.connect(url, row_factory=_row_factory, prepare_threshold=None)

    def _execute(self, sql, args):
        return self.raw.execute(sql, args)

    def execute(self, sql, args=()):
        pg_sql = translate(sql)
        match = _WRITE.match(sql)
        wants_id = (match and match.group(1).upper().startswith("INSERT")
                    and match.group(2).lower() in _ID_TABLES and "RETURNING" not in sql.upper())
        if wants_id:
            pg_sql += " RETURNING id"
        cur = self.raw.execute(pg_sql, tuple(args))
        lastrowid = cur.fetchone()[0] if wants_id else None
        self._note_write(sql, cur.rowcount)
        return PgCursor(cur, lastrowid)

    def executescript(self, script):
        self.raw.execute(script)

    def _commit(self):
        self.raw.commit()

    def rollback(self):
        self.raw.rollback()

    def close(self):
        self.raw.close()


# ----------------------------------------------------------------- migrations

def migrate(target) -> None:
    conn = connect(target)
    folder = PG_MIGRATIONS_DIR if conn.kind == "postgres" else MIGRATIONS_DIR
    try:
        if conn.kind == "postgres":
            # Only one starting server should run migrations at a time.
            conn.execute("SELECT pg_advisory_xact_lock(424242)")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " name TEXT PRIMARY KEY,"
            " applied_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')))"
        )
        done = {r["name"] for r in conn.execute("SELECT name FROM schema_migrations").fetchall()}
        for script in sorted(folder.glob("*.sql")):
            if script.name in done:
                continue
            conn.executescript(script.read_text(encoding="utf-8"))
            conn.execute("INSERT INTO schema_migrations (name) VALUES (?)", (script.name,))
        conn.commit()
    finally:
        conn.close()


# ------------------------------------------------------------------- backups

def backup(target, backup_dir: Path, keep: int) -> Path | None:
    """Copy a SQLite database file into backup_dir and prune old copies.

    The online (PostgreSQL) version is backed up by its host instead.
    """
    if is_postgres(target):
        return None
    path = Path(target)
    if not path.exists() or path.stat().st_size == 0:
        return None
    backup_dir.mkdir(parents=True, exist_ok=True)
    out = backup_dir / f"community-{datetime.now():%Y%m%d-%H%M%S}.db"
    write_backup(path, out)
    copies = sorted(backup_dir.glob("community-*.db"))
    for old in copies[:-keep] if keep > 0 else []:
        old.unlink(missing_ok=True)
    return out


def write_backup(src, target) -> None:
    """Write the records in `src` (a file or URL) to a new SQLite file."""
    if not is_postgres(src):
        source = sqlite3.connect(src)
        dest = sqlite3.connect(target)
        try:
            source.backup(dest)
        finally:
            dest.close()
            source.close()
        return
    migrate(target)
    copy_records(src, target)


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


def restore(upload_path, target) -> None:
    """Replace the records in `target` with those in a SQLite backup file."""
    if not is_postgres(target):
        shutil.copyfile(upload_path, target)
        return
    # Bring an older backup up to the current structure before copying.
    work = Path(tempfile.mkdtemp()) / "restore.db"
    shutil.copyfile(upload_path, work)
    migrate(work)
    copy_records(work, target)


def copy_records(src, dst) -> None:
    """Replace all families and members in `dst` with those in `src`.

    Links between rows (parents, spouse, head of family) are filled in after
    every row exists, so the order of rows never matters. Login accounts are
    not part of the records and are left alone.
    """
    source, dest = connect(src), connect(dst)
    try:
        dest.execute("UPDATE families SET head_member_id = NULL")
        dest.execute("DELETE FROM members")
        dest.execute("DELETE FROM families")
        links = []  # (table, columns, rows) to fill in once every row exists
        for table in BACKUP_TABLES:
            dest_cols = _columns(dest, table)
            rows = source.execute(f"SELECT * FROM {table} ORDER BY id").fetchall()
            if not rows:
                continue
            cols = [c for c in rows[0].keys() if c in dest_cols]
            later = [c for c in DEFERRED_LINKS[table] if c in cols]
            now_cols = [c for c in cols if c not in later]
            marks = ", ".join("?" * len(now_cols))
            for row in rows:
                dest.execute(f"INSERT INTO {table} ({', '.join(now_cols)}) VALUES ({marks})",
                             [row[c] for c in now_cols])
            links.append((table, later, rows))
        for table, later, rows in links:
            sets = ", ".join(f"{c} = ?" for c in later)
            for row in rows:
                if any(row[c] for c in later):
                    dest.execute(f"UPDATE {table} SET {sets} WHERE id = ?", [row[c] for c in later] + [row["id"]])
        if dest.kind == "postgres":
            for table in BACKUP_TABLES:
                dest.execute(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'),"
                             f" COALESCE((SELECT MAX(id) FROM {table}), 0) + 1, false)")
        dest._changed = True
        dest.commit()
    except Exception:
        dest.rollback()
        raise
    finally:
        source.close()
        dest.close()


def _columns(conn, table):
    if conn.kind == "postgres":
        rows = conn.execute("SELECT column_name FROM information_schema.columns WHERE table_name = ?",
                            (table,)).fetchall()
        return {r[0] for r in rows}
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
