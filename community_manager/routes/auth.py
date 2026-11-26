"""Login for the shared online version.

The offline versions (one PC, or one phone) need no login. The online version
does, because anyone with the web address could otherwise open the records.
The first account is created on the Setup page with the setup code the
person who put the app online chose (COMMUNITY_SETUP_CODE); after that,
admins add the other accounts on the Users page.
"""
import hmac
import os
import time
from functools import wraps

from flask import (Blueprint, abort, current_app, flash, g, jsonify, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from ..db import get_db

bp = Blueprint("auth", __name__)

PUBLIC_ENDPOINTS = {"auth.login", "auth.setup", "static", "main.manifest", "main.service_worker"}
MIN_PASSWORD = 8


def login_required_here() -> bool:
    return bool(current_app.config.get("LOGIN_REQUIRED"))


def load_user():
    g.user = None
    if not login_required_here():
        return None
    user_id = session.get("user_id")
    if user_id:
        g.user = get_db().execute("SELECT id, username, full_name, is_admin FROM users WHERE id = ?",
                                  (user_id,)).fetchone()
        if g.user is None:
            session.clear()
    if g.user is None and request.endpoint not in PUBLIC_ENDPOINTS:
        if request.path.startswith("/api/"):
            return jsonify(error="login needed"), 401
        if user_count() == 0:
            return redirect(url_for("auth.setup"))
        return redirect(url_for("auth.login", next=request.full_path if request.method == "GET" else None))
    return None


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if login_required_here() and not (g.user and g.user["is_admin"]):
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def user_count() -> int:
    return get_db().execute("SELECT COUNT(*) FROM users").fetchone()[0]


def _safe_next(target):
    return target if target and target.startswith("/") and not target.startswith("//") else url_for("main.dashboard")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if not login_required_here():
        return redirect(url_for("main.dashboard"))
    if user_count() == 0:
        return redirect(url_for("auth.setup"))
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        row = get_db().execute("SELECT id, password_hash FROM users WHERE username = ?", (username,)).fetchone()
        if row and check_password_hash(row["password_hash"], password):
            session.clear()
            session.permanent = True
            session["user_id"] = row["id"]
            return redirect(_safe_next(request.form.get("next")))
        time.sleep(1)  # slow down password guessing
        flash("Wrong username or password.", "error")
    return render_template("auth/login.html", next=request.values.get("next", ""))


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have signed out.", "success")
    return redirect(url_for("auth.login"))


@bp.route("/setup", methods=["GET", "POST"])
def setup():
    """Create the first admin account, once."""
    if not login_required_here() or user_count() > 0:
        return redirect(url_for("auth.login") if login_required_here() else url_for("main.dashboard"))
    expected = os.environ.get("COMMUNITY_SETUP_CODE", "")
    if request.method == "POST":
        code = request.form.get("setup_code", "")
        if not expected or not hmac.compare_digest(code.encode(), expected.encode()):
            time.sleep(1)
            flash("That setup code is not right.", "error")
        else:
            error = _create_user(request.form, is_admin=True)
            if error:
                flash(error, "error")
            else:
                flash("Your admin account is ready. Sign in with it now.", "success")
                return redirect(url_for("auth.login"))
    return render_template("auth/setup.html", has_code=bool(expected))


def _create_user(form, is_admin):
    username = form.get("username", "").strip().lower()
    password = form.get("password", "")
    if not username or not username.replace(".", "").replace("_", "").replace("-", "").isalnum():
        return "Choose a username using letters and numbers only."
    if len(password) < MIN_PASSWORD:
        return f"The password needs at least {MIN_PASSWORD} characters."
    if password != form.get("password2", password):
        return "The two passwords are different."
    db = get_db()
    if db.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
        return f"There is already an account called {username}."
    db.execute("INSERT INTO users (username, full_name, password_hash, is_admin) VALUES (?, ?, ?, ?)",
               (username, form.get("full_name", "").strip() or None, generate_password_hash(password),
                1 if is_admin else 0))
    db.commit()
    return None


@bp.route("/users", methods=["GET", "POST"])
@admin_required
def users():
    if not login_required_here():
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        error = _create_user(request.form, is_admin=bool(request.form.get("is_admin")))
        if error:
            flash(error, "error")
        else:
            flash("Account added. Tell the person their username and password.", "success")
            return redirect(url_for("auth.users"))
    rows = get_db().execute("SELECT id, username, full_name, is_admin, created_at FROM users"
                            " ORDER BY username").fetchall()
    return render_template("auth/users.html", users=rows, form=request.form)


@bp.route("/users/<int:user_id>/password", methods=["POST"])
@admin_required
def reset_password(user_id):
    password = request.form.get("password", "")
    if len(password) < MIN_PASSWORD:
        flash(f"The password needs at least {MIN_PASSWORD} characters.", "error")
    else:
        db = get_db()
        db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (generate_password_hash(password), user_id))
        db.commit()
        flash("Password changed.", "success")
    return redirect(url_for("auth.users"))


@bp.route("/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def delete_user(user_id):
    if g.user and g.user["id"] == user_id:
        flash("You cannot remove your own account.", "error")
        return redirect(url_for("auth.users"))
    db = get_db()
    db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    db.commit()
    flash("Account removed.", "success")
    return redirect(url_for("auth.users"))


@bp.route("/account", methods=["GET", "POST"])
def account():
    if not login_required_here():
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        db = get_db()
        row = db.execute("SELECT password_hash FROM users WHERE id = ?", (g.user["id"],)).fetchone()
        new = request.form.get("password", "")
        if not check_password_hash(row["password_hash"], request.form.get("current", "")):
            flash("Your current password is not right.", "error")
        elif len(new) < MIN_PASSWORD:
            flash(f"The new password needs at least {MIN_PASSWORD} characters.", "error")
        elif new != request.form.get("password2"):
            flash("The two new passwords are different.", "error")
        else:
            db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (generate_password_hash(new), g.user["id"]))
            db.commit()
            flash("Your password was changed.", "success")
            return redirect(url_for("main.dashboard"))
    return render_template("auth/account.html")
