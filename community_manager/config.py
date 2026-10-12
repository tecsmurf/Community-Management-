"""Settings for the community manager.

Change the values here to adjust ID formats or Yuvak Mandal age rules.
"""
import os
import sys
from pathlib import Path

APP_NAME = "Community Manager"
COMMUNITY_NAME = "Ambesh Guru Shwetambar Jain Samaj"
YUVAK_MANDAL_NAME = "Ambesh Yuvak Mandal"

# ID formats. The number part is zero padded to the given width,
# e.g. MEMBER_PREFIX "AM" with width 5 gives AM-00001.
MEMBER_PREFIX, MEMBER_ID_WIDTH = "AM", 5
FAMILY_PREFIX, FAMILY_ID_WIDTH = "AF", 4
YUVAK_PREFIX, YUVAK_ID_WIDTH = "AYM", 4

# Yuvak Mandal: males aged YUVAK_MIN_AGE..YUVAK_MAX_AGE (inclusive) are active
# members. Once they are older than YUVAK_MAX_AGE they become alumni.
YUVAK_MIN_AGE = 18
YUVAK_MAX_AGE = 45

# How many automatic database backups to keep (one is made at every start).
BACKUPS_TO_KEEP = 15


def data_dir() -> Path:
    """Folder where the database and backups live.

    On Windows this is %APPDATA%\\CommunityManager so the data survives
    reinstalls and does not need admin rights. Override with the
    COMMUNITY_DATA_DIR environment variable.
    """
    override = os.environ.get("COMMUNITY_DATA_DIR")
    if override:
        path = Path(override)
    elif sys.platform == "win32" and os.environ.get("APPDATA"):
        path = Path(os.environ["APPDATA"]) / "CommunityManager"
    else:
        path = Path.home() / ".community_manager"
    path.mkdir(parents=True, exist_ok=True)
    return path


def format_code(prefix: str, number: int, width: int) -> str:
    return f"{prefix}-{number:0{width}d}"
