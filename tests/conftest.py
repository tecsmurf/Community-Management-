"""Test fixtures.

Set TEST_DATABASE_URL to a PostgreSQL URL to run every test against the
shared online database instead of a SQLite file, for example
TEST_DATABASE_URL=postgresql://cm@127.0.0.1:55432/cm_test
The tests empty that database, so never point it at real data.
"""
import os

import pytest

from community_manager import create_app
from community_manager.db import get_db

PG_URL = os.environ.get("TEST_DATABASE_URL")


def _empty_postgres(url):
    import psycopg

    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("COMMUNITY_DATA_DIR", str(tmp_path))
    config = {"TESTING": True}
    if PG_URL:
        _empty_postgres(PG_URL)
        config["DATABASE"] = PG_URL
    app = create_app(config)
    return app


def make_user(app, username="admin", password="secret-pass", is_admin=True):
    from werkzeug.security import generate_password_hash

    with app.app_context():
        conn = get_db()
        cur = conn.execute("INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, ?)",
                           (username, generate_password_hash(password), int(is_admin)))
        conn.commit()
        return cur.lastrowid


@pytest.fixture
def client(app):
    """A browser; already signed in when the app needs a login (online)."""
    client = app.test_client()
    if app.config["LOGIN_REQUIRED"]:
        user_id = make_user(app)
        with client.session_transaction() as session:
            session["user_id"] = user_id
    return client


@pytest.fixture
def db(app):
    with app.app_context():
        yield get_db()
