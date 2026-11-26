"""Community Manager: a small Flask app.

It runs offline on one PC or phone with a SQLite file, or online with a
shared PostgreSQL database so every phone and computer sees the same records.
"""
import os
import secrets
from datetime import date, timedelta
from pathlib import Path

from flask import Flask, g

from . import config, db
from .services import people

__version__ = "1.2.0"


def create_app(test_config=None):
    app = Flask(__name__)
    data_dir = config.data_dir()
    app.config.update(
        # The shared online version gets a PostgreSQL URL from its host.
        DATABASE=(os.environ.get("COMMUNITY_DATABASE_URL") or os.environ.get("DATABASE_URL")
                  or str(data_dir / "community.db")),
        BACKUP_DIR=str(data_dir / "backups"),
        SECRET_KEY=_secret_key(data_dir),
        MAX_CONTENT_LENGTH=200 * 1024 * 1024,
    )
    if test_config:
        app.config.update(test_config)
    online = db.is_postgres(app.config["DATABASE"])
    if online and not app.config.get("TESTING") and not os.environ.get("COMMUNITY_SECRET_KEY"):
        # Every server copy must sign logins with the same key.
        raise RuntimeError("Set COMMUNITY_SECRET_KEY for the online version.")
    app.config.setdefault("LOGIN_REQUIRED", online)
    app.config.setdefault("LIVE_INTERVAL_MS", 10000)
    app.config.update(
        PERMANENT_SESSION_LIFETIME=timedelta(days=30),
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=online and not app.config.get("TESTING"),
    )

    if not app.config.get("TESTING"):
        db.backup(app.config["DATABASE"], Path(app.config["BACKUP_DIR"]),
                  config.BACKUPS_TO_KEEP)
    db.migrate(app.config["DATABASE"])
    conn = db.connect(app.config["DATABASE"])
    try:
        people.sync_yuvak_ids(conn)
    finally:
        conn.close()

    app.teardown_appcontext(db.close_db)

    from .routes import auth, families, main, members, yuvak
    for module in (auth, main, members, families, yuvak):
        app.register_blueprint(module.bp)
    app.before_request(auth.load_user)

    @app.context_processor
    def globals_for_templates():
        return {"cfg": config, "today": date.today(), "app_version": __version__,
                "genders": people.GENDERS, "demo_mode": app.config.get("DEMO", False),
                "native_app": bool(app.config.get("NATIVE")),
                "online": app.config["LOGIN_REQUIRED"],
                "signed_in": not app.config["LOGIN_REQUIRED"] or g.get("user") is not None,
                "data_version": db.get_db().data_version(),
                "live_interval_ms": app.config["LIVE_INTERVAL_MS"]}

    @app.before_request
    def daily_yuvak_sync():
        # Boys who turn 18 while the app is left open still get their ID.
        today = date.today()
        if app.config.get("_last_sync") != today:
            people.sync_yuvak_ids(db.get_db(), today)
            app.config["_last_sync"] = today

    return app


def _secret_key(data_dir):
    path = data_dir / "secret.key"
    if not path.exists():
        path.write_text(secrets.token_hex(32))
    return os.environ.get("COMMUNITY_SECRET_KEY") or path.read_text().strip()
