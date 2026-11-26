"""The shared online version: sign-in, live updates and moving data across."""
import sqlite3

import pytest

from community_manager import create_app, db as dbmod
from community_manager.routes import auth
from community_manager.services import people

from conftest import PG_URL, _empty_postgres, make_user
from test_people import add


@pytest.fixture
def online_app(tmp_path, monkeypatch):
    """Login switched on, as it is for the online version."""
    monkeypatch.setenv("COMMUNITY_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("COMMUNITY_SETUP_CODE", "open-sesame")
    monkeypatch.setattr(auth.time, "sleep", lambda _s: None)
    config = {"TESTING": True, "LOGIN_REQUIRED": True}
    if PG_URL:
        _empty_postgres(PG_URL)
        config["DATABASE"] = PG_URL
    return create_app(config)


def sign_in(client, username, password):
    return client.post("/login", data={"username": username, "password": password})


def test_first_admin_is_created_with_the_setup_code(online_app):
    client = online_app.test_client()
    assert client.get("/").headers["Location"].endswith("/setup")
    form = {"username": "Ramesh", "password": "long-enough", "password2": "long-enough", "full_name": "Ramesh"}
    assert b"not right" in client.post("/setup", data={**form, "setup_code": "guess"}, follow_redirects=True).data
    client.post("/setup", data={**form, "setup_code": "open-sesame"})
    # Setup closes once an account exists.
    assert client.get("/setup").headers["Location"].endswith("/login")
    assert sign_in(client, "ramesh", "wrong-pass").status_code == 200
    assert client.get("/").status_code == 302
    sign_in(client, "RAMESH", "long-enough")  # usernames ignore capitals
    page = client.get("/")
    assert page.status_code == 200 and b"Sign out" in page.data and b"Users" in page.data


def test_pages_need_sign_in(online_app):
    client = online_app.test_client()
    make_user(online_app, "admin", "secret-pass")
    assert client.get("/members/").headers["Location"].startswith("/login?next=/members/")
    assert client.get("/api/version").status_code == 401
    assert client.get("/backup/download").status_code == 302
    # The pieces a phone needs to install the app stay public.
    assert client.get("/manifest.webmanifest").json["display"] == "standalone"
    assert client.get("/sw.js").status_code == 200
    assert client.get("/static/icon-512.png").status_code == 200
    # After signing in, the page asked for opens.
    response = client.post("/login", data={"username": "admin", "password": "secret-pass", "next": "/members/"})
    assert response.headers["Location"] == "/members/"
    assert client.post("/login", data={"username": "admin", "password": "secret-pass",
                                       "next": "//evil.example"}).headers["Location"] == "/"


def test_team_members_cannot_manage_accounts_or_restore(online_app):
    make_user(online_app, "admin", "secret-pass")
    client = online_app.test_client()
    sign_in(client, "admin", "secret-pass")
    client.post("/users", data={"username": "sunita", "password": "team-pass1"})
    client.post("/logout")
    sign_in(client, "sunita", "team-pass1")
    assert client.get("/").status_code == 200
    assert client.get("/users").status_code == 403
    assert client.post("/backup/restore").status_code == 403
    assert b"Restore from a backup" not in client.get("/backup").data
    # Changing one's own password works.
    client.post("/account", data={"current": "team-pass1", "password": "team-pass2", "password2": "team-pass2"})
    client.post("/logout")
    assert sign_in(client, "sunita", "team-pass2").status_code == 302


def test_admin_adds_resets_and_removes_accounts(online_app):
    make_user(online_app, "admin", "secret-pass")
    client = online_app.test_client()
    sign_in(client, "admin", "secret-pass")
    assert b"at least 8" in client.post("/users", data={"username": "x", "password": "short"},
                                        follow_redirects=True).data
    client.post("/users", data={"username": "sunita", "password": "team-pass1"})
    assert b"already an account" in client.post("/users", data={"username": "Sunita", "password": "team-pass1"},
                                                 follow_redirects=True).data
    with online_app.app_context():
        conn = dbmod.get_db()
        sunita = conn.execute("SELECT id FROM users WHERE username = 'sunita'").fetchone()["id"]
        admin = conn.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()["id"]
    client.post(f"/users/{sunita}/password", data={"password": "reset-pass1"})
    client.post(f"/users/{admin}/delete")  # cannot remove yourself
    client.post(f"/users/{sunita}/delete")
    with online_app.app_context():
        names = [r["username"] for r in dbmod.get_db().execute("SELECT username FROM users").fetchall()]
    assert names == ["admin"]


def test_live_version_changes_when_records_change(client, db):
    before = client.get("/api/version").json["version"]
    page = client.get("/members/").get_data(as_text=True)
    assert f"var version = {before}," in page
    add(db, "Ramesh", dob="1990-01-01")
    after = client.get("/api/version").json["version"]
    assert after > before
    # Reading pages or saving nothing does not change it.
    client.get("/")
    assert client.get("/api/version").json["version"] == after


def test_records_copy_between_databases_with_all_links(app, db, tmp_path):
    fam = people.save_family(db, {"family_name": "Shah", "address": "1 Road", "area": "North"})
    grandpa = add(db, "Mohan", dob="1950-01-01", family_id=fam)
    grandma = add(db, "Kamla", gender="F", dob="1952-01-01", family_id=fam, spouse_id=grandpa)
    son = add(db, "Ramesh", dob="1980-01-01", family_id=fam, father_id=grandpa, mother_id=grandma,
              relation_to_head="Self (Head)")
    backup = tmp_path / "copy.db"
    dbmod.write_backup(app.config["DATABASE"], backup)
    assert dbmod.is_valid_database(backup)

    # The backup is an ordinary SQLite file with every link intact.
    plain = sqlite3.connect(backup)
    row = plain.execute("SELECT father_id, mother_id FROM members WHERE id = ?", (son,)).fetchone()
    assert row == (grandpa, grandma)
    assert plain.execute("SELECT head_member_id FROM families WHERE id = ?", (fam,)).fetchone()[0] == son
    plain.close()

    # Restoring it somewhere else gives the same records, and new ones get fresh IDs.
    other = tmp_path / "other.db"
    dbmod.migrate(other)
    dbmod.copy_records(backup, other)
    conn = dbmod.connect(other)
    try:
        assert conn.execute("SELECT spouse_id FROM members WHERE id = ?", (grandpa,)).fetchone()[0] == grandma
        assert conn.data_version() == 1
        new_id = conn.execute("INSERT INTO members (first_name, gender) VALUES ('New', 'M')").lastrowid
        assert new_id == son + 1
    finally:
        conn.close()
