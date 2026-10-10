"""Helpers for reading HTML form values."""
from .. import config
from ..services import people


def text(form, key):
    value = (form.get(key) or "").strip()
    return value or None


def code_ref(form, key, prefix):
    """Read a picker value like 'AM-00012 | Name' and return 12 (or None)."""
    raw = text(form, key)
    if raw is None:
        return None
    number = people.parse_code(raw.split("|")[0], prefix)
    if number is None:
        raise people.ValidationError(f"Could not understand '{raw}'. Pick a name from the list.")
    return number


def member_form(form):
    data = {k: text(form, k) for k in people.MEMBER_FIELDS}
    for key in ("first_name", "middle_name", "last_name", "area", "city"):
        if data[key]:
            data[key] = " ".join(data[key].split())
    data["gender"] = data["gender"] or ""
    data["is_deceased"] = 1 if form.get("is_deceased") else 0
    data["family_id"] = code_ref(form, "family_id", config.FAMILY_PREFIX)
    for key in ("father_id", "mother_id", "spouse_id"):
        data[key] = code_ref(form, key, config.MEMBER_PREFIX)
    return data


def family_form(form):
    data = {k: text(form, k) for k in people.FAMILY_FIELDS}
    data["head_member_id"] = code_ref(form, "head_member_id", config.MEMBER_PREFIX)
    return data
