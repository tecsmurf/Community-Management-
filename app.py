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

from community_manager import create_app  # noqa: E402

app = create_app()
