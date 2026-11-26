import csv
import io
import tempfile
from datetime import datetime
from pathlib import Path

from flask import (Blueprint, Response, current_app, flash, jsonify, redirect, render_template, request,
                   send_file, url_for)

from .. import config, db
from ..services import people
from .auth import admin_required

bp = Blueprint("main", __name__)


@bp.route("/")
def dashboard():
    conn = db.get_db()
    recent = conn.execute(f"{people.MEMBER_SELECT} ORDER BY m.id DESC LIMIT 8").fetchall()
    return render_template("dashboard.html", stats=people.stats(conn),
                           recent=[people.decorate(r) for r in recent],
                           birthdays=people.upcoming_birthdays(conn, days=30)[:12],
                           areas=people.area_counts(conn)[:10])


@bp.route("/api/version")
def live_version():
    """A number that changes whenever members or families change (see base.html)."""
    response = jsonify(version=db.get_db().data_version())
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.route("/manifest.webmanifest")
def manifest():
    """Lets phones and computers install the online version like an app."""
    icon = url_for("static", filename="icon-512.png")
    data = {
        "name": config.APP_NAME, "short_name": "Community", "start_url": url_for("main.dashboard"),
        "scope": "/", "display": "standalone", "background_color": "#f6f3ee", "theme_color": "#B5541C",
        "description": f"Members, families and {config.YUVAK_MANDAL_NAME} records for {config.COMMUNITY_NAME}.",
        "icons": [
            {"src": url_for("static", filename="icon-192.png"), "sizes": "192x192", "type": "image/png"},
            {"src": icon, "sizes": "512x512", "type": "image/png"},
            {"src": url_for("static", filename="icon-maskable-512.png"), "sizes": "512x512",
             "type": "image/png", "purpose": "maskable"},
        ],
    }
    return jsonify(data), 200, {"Content-Type": "application/manifest+json"}


@bp.route("/sw.js")
def service_worker():
    # The records always come from the server, so the worker caches nothing.
    script = "self.addEventListener('install', () => self.skipWaiting());\n" \
             "self.addEventListener('fetch', () => {});\n"
    return Response(script, mimetype="text/javascript", headers={"Cache-Control": "no-cache"})


@bp.route("/help")
def help_page():
    return render_template("help.html")


@bp.app_errorhandler(404)
def not_found(_exc):
    return render_template("404.html"), 404


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
    content = "﻿" + buf.getvalue()
    filename = f"members-{datetime.now():%Y%m%d}.csv"
    native = current_app.config.get("NATIVE")
    if native:
        tmp = Path(tempfile.mkdtemp()) / filename
        tmp.write_text(content, encoding="utf-8")
        return _saved_on_phone(native.save_file(tmp, filename, "text/csv"), f"{len(rows)} members exported")
    return Response(content, mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={filename}"})


def _saved_on_phone(saved, what):
    """After the phone's save screen: say what happened and go back."""
    if saved:
        flash(f"{what} and saved.", "success")
    else:
        flash("Nothing was saved.", "error")
    back = request.referrer or url_for("main.dashboard")
    return redirect(back if back.startswith(request.host_url) else url_for("main.dashboard"))


@bp.route("/backup", methods=["GET"])
def backup_page():
    backups = sorted(Path(current_app.config["BACKUP_DIR"]).glob("community-*.db"), reverse=True)
    path = current_app.config["DATABASE"]
    return render_template("backup.html", backups=backups,
                           db_path=None if db.is_postgres(path) else path)


@bp.route("/backup/download")
def backup_download():
    tmp = Path(tempfile.mkdtemp()) / f"community-backup-{datetime.now():%Y%m%d-%H%M}.db"
    db.write_backup(current_app.config["DATABASE"], tmp)
    native = current_app.config.get("NATIVE")
    if native:
        return _saved_on_phone(native.save_file(tmp, tmp.name, "application/octet-stream"), "Backup created")
    return send_file(tmp, as_attachment=True, download_name=tmp.name)


@bp.route("/backup/restore", methods=["POST"])
@admin_required
def backup_restore():
    tmp = Path(tempfile.mkdtemp()) / "upload.db"
    native = current_app.config.get("NATIVE")
    if native:
        # The phone app opens its own file picker and copies the chosen file to tmp.
        if not native.pick_file(tmp):
            flash("No file was chosen.", "error")
            return redirect(url_for("main.backup_page"))
    else:
        upload = request.files.get("file")
        if not upload or not upload.filename:
            flash("Choose a backup file first.", "error")
            return redirect(url_for("main.backup_page"))
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
