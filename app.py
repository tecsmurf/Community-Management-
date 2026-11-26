"""Entry point for the shared online version (hosted on Vercel).

The host gives the database address in DATABASE_URL, and the person who put
the app online sets COMMUNITY_SECRET_KEY (any long random text) and
COMMUNITY_SETUP_CODE (used once, to create the first admin account).
The PC and phone offline versions start from run.py and mobile/ instead.
"""
import os
import time

# Dates such as birthdays and the Yuvak Mandal age follow Indian time.
os.environ["TZ"] = "Asia/Kolkata"
time.tzset()
# The server's disk is temporary; only the database keeps the records.
os.environ.setdefault("COMMUNITY_DATA_DIR", "/tmp/community-manager")

from flask import Flask  # noqa: E402


def make_app() -> Flask:
    if os.environ.get("COMMUNITY_DATABASE_URL") or os.environ.get("DATABASE_URL"):
        from community_manager import create_app

        return create_app()
    # Without a database anything typed in would be lost, so open nothing yet.
    waiting = Flask(__name__)

    @waiting.route("/", defaults={"_path": ""})
    @waiting.route("/<path:_path>")
    def not_ready(_path):
        return ("<h1>Community Manager is being set up</h1>"
                "<p>The database is not connected yet. Please try again later.</p>"), 503

    return waiting


app = make_app()
