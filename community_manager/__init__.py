"""Community Manager: a small Flask + SQLite app that runs on one PC."""
import os
import secrets
from datetime import date
from pathlib import Path

from flask import Flask

from . import config, db
from .services import people

__version__ = "1.0.0"


def create_app(test_config=None):
    app = Flask(__name__)
    data_dir = config.data_dir()
    app.config.update(
        DATABASE=str(data_dir / "community.db"),
        BACKUP_DIR=str(data_dir / "backups"),
        SECRET_KEY=_secret_key(data_dir),
        MAX_CONTENT_LENGTH=200 * 1024 * 1024,
    )
    if test_config:
        app.config.update(test_config)

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

    from .routes import families, main, members, yuvak
    for module in (main, members, families, yuvak):
        app.register_blueprint(module.bp)

    @app.context_processor
    def globals_for_templates():
        return {"cfg": config, "today": date.today(), "app_version": __version__,
                "genders": people.GENDERS}

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
