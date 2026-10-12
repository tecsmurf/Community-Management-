from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from ..db import get_db
from ..services import people, tree
from . import forms

bp = Blueprint("members", __name__, url_prefix="/members")
PAGE_SIZE = 50


def filter_from_args(args):
    return people.MemberFilter(
        q=args.get("q", "").strip(),
        area=args.get("area", ""),
        gender=args.get("gender", ""),
        yuvak=args.get("yuvak", ""),
        profession=args.get("profession", "").strip(),
        include_deceased=args.get("deceased", "1") == "1",
    )


@bp.route("/")
def index():
    db = get_db()
    flt = filter_from_args(request.args)
    page = max(request.args.get("page", 1, type=int), 1)
    order = request.args.get("order", "name")
    rows, total = people.search_members(db, flt, PAGE_SIZE, (page - 1) * PAGE_SIZE, order)
    return render_template("members/index.html", members=rows, total=total, flt=flt, page=page,
                           pages=max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1), order=order,
                           areas=people.all_areas(db))


def _form_context(db, member=None):
    return {
        "member": member or {},
        "member_choices": people.member_choices(db),
        "family_choices": people.family_choices(db),
        "areas": people.all_areas(db),
        "professions": people.all_professions(db),
        "relations": people.RELATIONS,
        "marital_statuses": people.MARITAL_STATUSES,
        "blood_groups": people.BLOOD_GROUPS,
    }


def _refs_for_form(db, member):
    """Turn stored ids into the labels the picker inputs show."""
    labels = {c["id"]: c["label"] for c in people.member_choices(db)}
    fam = {c["id"]: c["label"] for c in people.family_choices(db)}
    member = dict(member)
    for key in ("father_id", "mother_id", "spouse_id"):
        member[key + "_label"] = labels.get(member.get(key), "")
    member["family_id_label"] = fam.get(member.get("family_id"), "")
    return member


@bp.route("/new", methods=["GET", "POST"])
def new():
    db = get_db()
    if request.method == "POST":
        try:
            data = forms.member_form(request.form)
            member_id = people.save_member(db, data, former_yuvak=bool(request.form.get("former_yuvak")))
        except people.ValidationError as exc:
            flash(str(exc), "error")
            return render_template("members/form.html", **_form_context(db, _echo(request.form))), 400
        flash(f"Member {people.member_code(member_id)} added.", "success")
        if request.form.get("next") == "another":
            return redirect(url_for("members.new", family=request.form.get("family_id", "")))
        return redirect(url_for("members.view", member_id=member_id))

    member = {}
    family_id = people.parse_code((request.args.get("family") or "").split("|")[0], people.config.FAMILY_PREFIX)
    if family_id:
        family = people.get_family(db, family_id)
        if family:
            member = {"family_id": family_id, "last_name": family["family_name"]}
    for key in ("father_id", "mother_id"):
        if request.args.get(key, type=int):
            member[key] = request.args.get(key, type=int)
    if member.get("father_id") and not member.get("family_id"):
        father = people.get_member(db, member["father_id"])
        if father:
            member.update(family_id=father["family_id"], last_name=father["last_name"])
            if father["spouse_id"] and not member.get("mother_id"):
                member["mother_id"] = father["spouse_id"]
    return render_template("members/form.html", **_form_context(db, _refs_for_form(db, member)))


def _echo(form):
    """Re-show what the user typed after a validation error."""
    member = {k: form.get(k, "") for k in people.MEMBER_FIELDS}
    for key in ("father_id", "mother_id", "spouse_id", "family_id"):
        member[key + "_label"] = form.get(key, "")
        member[key] = None
    member["is_deceased"] = 1 if form.get("is_deceased") else 0
    member["id"] = form.get("id", type=int)
    return member


@bp.route("/<int:member_id>")
def view(member_id):
    db = get_db()
    member = people.get_member(db, member_id)
    if not member:
        abort(404)
    related = people.members_by_ids(db, [member["father_id"], member["mother_id"], member["spouse_id"]])
    return render_template(
        "members/view.html", m=member,
        father=related.get(member["father_id"]), mother=related.get(member["mother_id"]),
        spouse=related.get(member["spouse_id"]), children=people.children_of(db, member_id),
        siblings=people.siblings_of(db, member),
    )


@bp.route("/<int:member_id>/edit", methods=["GET", "POST"])
def edit(member_id):
    db = get_db()
    member = people.get_member(db, member_id)
    if not member:
        abort(404)
    if request.method == "POST":
        try:
            data = forms.member_form(request.form)
            people.save_member(db, data, member_id, former_yuvak=bool(request.form.get("former_yuvak")))
        except people.ValidationError as exc:
            flash(str(exc), "error")
            echoed = _echo(request.form)
            echoed.update(id=member_id, code=member["code"], yuvak_no=member["yuvak_no"])
            return render_template("members/form.html", **_form_context(db, echoed)), 400
        flash("Changes saved.", "success")
        return redirect(url_for("members.view", member_id=member_id))
    return render_template("members/form.html", **_form_context(db, _refs_for_form(db, member)))


@bp.route("/<int:member_id>/delete", methods=["POST"])
def delete(member_id):
    db = get_db()
    member = people.get_member(db, member_id)
    if not member:
        abort(404)
    people.delete_member(db, member_id)
    flash(f"{member['name']} ({member['code']}) was deleted.", "success")
    return redirect(url_for("members.index"))


@bp.route("/<int:member_id>/tree")
def family_tree(member_id):
    db = get_db()
    member = people.get_member(db, member_id)
    if not member:
        abort(404)
    root = tree.member_tree(db, member_id)
    return render_template("tree.html", title=f"Family tree of {member['name']}", roots=[root],
                           highlight=member_id, back=url_for("members.view", member_id=member_id))
