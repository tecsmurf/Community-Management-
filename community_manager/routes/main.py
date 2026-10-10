import csv
import io
import tempfile
from datetime import datetime
from pathlib import Path

from flask import (Blueprint, Response, current_app, flash, redirect, render_template, request,
                   send_file, url_for)

from .. import config, db
from ..services import people

bp = Blueprint("main", __name__)


@bp.route("/")
def dashboard():
    conn = db.get_db()
    recent = conn.execute(f"{people.MEMBER_SELECT} ORDER BY m.id DESC LIMIT 8").fetchall()
    return render_template("dashboard.html", stats=people.stats(conn),
                           recent=[people.decorate(r) for r in recent])


@bp.route("/search")
def search():
    q = request.args.get("q", "").strip()
    number = people.parse_code(q, config.FAMILY_PREFIX)
    if number and q.upper().startswith(config.FAMILY_PREFIX) and people.get_family(db.get_db(), number):
        return redirect(url_for("families.view", family_id=number))
    return redirect(url_for("members.index", q=q))


EXPORT_COLUMNS = [
    ("Member ID", "code"), ("Name", "name"), ("Gender", "gender_label"), ("Date of birth", "dob"),
    ("Age", "age"), ("Family ID", "family_code"), ("Family", "family_name"),
    ("Relation to head", "relation_to_head"), ("Marital status", "marital_status"),
    ("Phone", "phone"), ("Email", "email"), ("Address", "display_address"), ("Area", "display_area"),
    ("City", "display_city"), ("Profession", "profession"), ("Education", "education"),
    ("Blood group", "blood_group"), ("Yuvak Mandal ID", "yuvak_code"),
    ("Yuvak Mandal status", "yuvak_status"), ("Deceased", "is_deceased"), ("Notes", "notes"),
]


@bp.route("/export/members.csv")
def export_members():
    from .members import filter_from_args
    rows, _ = people.search_members(db.get_db(), filter_from_args(request.args), limit=0, order="id")
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([c[0] for c in EXPORT_COLUMNS])
    for m in rows:
        writer.writerow(["Yes" if k == "is_deceased" and m[k] else ("" if k == "is_deceased" else m.get(k) or "")
                         for _, k in EXPORT_COLUMNS])
    # BOM so Excel opens it with the right encoding.
    return Response("﻿" + buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=members-{datetime.now():%Y%m%d}.csv"})


@bp.route("/backup", methods=["GET"])
def backup_page():
    backups = sorted(Path(current_app.config["BACKUP_DIR"]).glob("community-*.db"), reverse=True)
    return render_template("backup.html", backups=backups, db_path=current_app.config["DATABASE"])


@bp.route("/backup/download")
def backup_download():
    tmp = Path(tempfile.mkdtemp()) / f"community-backup-{datetime.now():%Y%m%d-%H%M}.db"
    db.write_backup(current_app.config["DATABASE"], tmp)
    return send_file(tmp, as_attachment=True, download_name=tmp.name)


@bp.route("/backup/restore", methods=["POST"])
def backup_restore():
    upload = request.files.get("file")
    if not upload or not upload.filename:
        flash("Choose a backup file first.", "error")
        return redirect(url_for("main.backup_page"))
    tmp = Path(tempfile.mkdtemp()) / "upload.db"
    upload.save(tmp)
    if not db.is_valid_database(tmp):
        flash("That file is not a Community Manager backup.", "error")
        return redirect(url_for("main.backup_page"))
    # Keep a copy of the current data before replacing it.
    db.backup(current_app.config["DATABASE"], Path(current_app.config["BACKUP_DIR"]), config.BACKUPS_TO_KEEP + 1)
    db.close_db()
    db.restore(tmp, current_app.config["DATABASE"])
    db.migrate(current_app.config["DATABASE"])
    flash("Backup restored. The previous data was saved in the backups folder.", "success")
    return redirect(url_for("main.dashboard"))
