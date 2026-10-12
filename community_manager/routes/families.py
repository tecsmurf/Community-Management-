from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from ..db import get_db
from ..services import people, tree
from . import forms

bp = Blueprint("families", __name__, url_prefix="/families")
PAGE_SIZE = 50


@bp.route("/")
def index():
    db = get_db()
    q, area = request.args.get("q", "").strip(), request.args.get("area", "")
    page = max(request.args.get("page", 1, type=int), 1)
    rows, total = people.list_families(db, q, area, PAGE_SIZE, (page - 1) * PAGE_SIZE)
    return render_template("families/index.html", families=rows, total=total, q=q, area=area, page=page,
                           pages=max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1), areas=people.all_areas(db))


def _form(db, family, members=()):
    return render_template("families/form.html", family=family, areas=people.all_areas(db),
                           members=members)


@bp.route("/new", methods=["GET", "POST"])
def new():
    db = get_db()
    if request.method == "POST":
        try:
            family_id = people.save_family(db, forms.family_form(request.form))
        except people.ValidationError as exc:
            flash(str(exc), "error")
            return _form(db, dict(request.form)), 400
        flash(f"Family {people.family_code(family_id)} created. Now add its members.", "success")
        return redirect(url_for("families.view", family_id=family_id))
    return _form(db, {})


@bp.route("/<int:family_id>")
def view(family_id):
    db = get_db()
    family = people.get_family(db, family_id)
    if not family:
        abort(404)
    return render_template("families/view.html", f=family, members=people.family_members(db, family_id))


@bp.route("/<int:family_id>/edit", methods=["GET", "POST"])
def edit(family_id):
    db = get_db()
    family = people.get_family(db, family_id)
    if not family:
        abort(404)
    members = people.family_members(db, family_id)
    if request.method == "POST":
        try:
            people.save_family(db, forms.family_form(request.form), family_id)
        except people.ValidationError as exc:
            flash(str(exc), "error")
            return _form(db, {**family, **request.form}, members), 400
        flash("Family saved.", "success")
        return redirect(url_for("families.view", family_id=family_id))
    if family["head_member_id"]:
        head = people.get_member(db, family["head_member_id"])
        family["head_member_id"] = f"{head['code']} | {head['name']}" if head else ""
    return _form(db, family, members)


@bp.route("/<int:family_id>/delete", methods=["POST"])
def delete(family_id):
    db = get_db()
    try:
        people.delete_family(db, family_id)
    except people.ValidationError as exc:
        flash(str(exc), "error")
        return redirect(url_for("families.view", family_id=family_id))
    flash("Family deleted.", "success")
    return redirect(url_for("families.index"))


@bp.route("/<int:family_id>/tree")
def family_tree(family_id):
    db = get_db()
    family = people.get_family(db, family_id)
    if not family:
        abort(404)
    return render_template("tree.html", title=f"{family['family_name']} family tree ({family['code']})",
                           roots=tree.family_tree(db, family_id), highlight=None,
                           back=url_for("families.view", family_id=family_id))
