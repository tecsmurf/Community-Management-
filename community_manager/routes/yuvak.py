from datetime import date

from flask import Blueprint, render_template, request

from .. import config
from ..db import get_db
from ..services import people

bp = Blueprint("yuvak", __name__, url_prefix="/yuvak-mandal")


@bp.route("/")
def index():
    db = get_db()
    tab = request.args.get("tab", "active")
    q = request.args.get("q", "").strip()
    today = date.today()
    if tab == "upcoming":
        rows = _upcoming(db, today)
    else:
        tab = tab if tab in ("active", "alumni") else "active"
        rows, _ = people.search_members(db, people.MemberFilter(q=q, yuvak=tab), limit=0, order="yuvak")
    counts = {t: people.search_members(db, people.MemberFilter(yuvak=t), limit=1)[1]
              for t in ("active", "alumni")}
    return render_template("yuvak/index.html", tab=tab, rows=rows, q=q, counts=counts)


def _upcoming(db, today, days=365):
    """Boys turning 18 and members turning 46 within the next year."""
    rows, _ = people.search_members(db, people.MemberFilter(gender="M", include_deceased=False), limit=0)
    out = []
    for m in rows:
        dob = people.parse_date(m["dob"])
        if not dob:
            continue
        for years, event in ((config.YUVAK_MIN_AGE, "Joins"), (config.YUVAK_MAX_AGE + 1, "Becomes alumni")):
            when = people.add_years(dob, years)
            if today < when <= date.fromordinal(today.toordinal() + days):
                out.append({**m, "event": event, "event_date": when.isoformat()})
    return sorted(out, key=lambda r: r["event_date"])
