"""Member and family data access plus the business rules around them."""
from dataclasses import dataclass
from datetime import date

from .. import config

MEMBER_FIELDS = (
    "family_id", "first_name", "middle_name", "last_name", "gender", "dob",
    "relation_to_head", "marital_status", "father_id", "mother_id", "spouse_id",
    "phone", "email", "address", "area", "city", "profession", "education",
    "blood_group", "is_deceased", "notes",
)
FAMILY_FIELDS = (
    "family_name", "head_member_id", "address", "area", "city", "pincode",
    "phone", "native_place", "notes",
)

RELATIONS = [
    "Self (Head)", "Wife", "Husband", "Son", "Daughter", "Father", "Mother",
    "Brother", "Sister", "Daughter-in-law", "Son-in-law", "Grandson",
    "Granddaughter", "Grandfather", "Grandmother", "Nephew", "Niece", "Other",
]
MARITAL_STATUSES = ["Unmarried", "Married", "Widowed", "Divorced"]
BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
GENDERS = {"M": "Male", "F": "Female", "O": "Other"}


# ---------------------------------------------------------------- dates & ages

def parse_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def add_years(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year + years)
    except ValueError:  # 29 Feb in a non-leap year
        return d.replace(year=d.year + years, day=28)


def age_on(dob, today: date | None = None):
    dob = parse_date(dob)
    if dob is None:
        return None
    today = today or date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


# ------------------------------------------------------------------ ID codes

def member_code(member_id):
    return config.format_code(config.MEMBER_PREFIX, member_id, config.MEMBER_ID_WIDTH)


def family_code(family_id):
    return config.format_code(config.FAMILY_PREFIX, family_id, config.FAMILY_ID_WIDTH) if family_id else ""


def yuvak_code(yuvak_no):
    return config.format_code(config.YUVAK_PREFIX, yuvak_no, config.YUVAK_ID_WIDTH) if yuvak_no else ""


def parse_code(text, prefix):
    """Turn 'AM-00012', 'am12' or '12' into 12. Returns None if not a code."""
    text = (text or "").strip().upper()
    if text.startswith(prefix.upper()):
        text = text[len(prefix):]
    text = text.lstrip("-").strip()
    return int(text) if text.isdigit() else None


# -------------------------------------------------------------- Yuvak Mandal

ACTIVE, ALUMNI = "Active", "Alumni"


def yuvak_status(member, today: date | None = None):
    """'Active', 'Alumni' or None for a member row/dict."""
    if member["gender"] != "M":
        return None
    age = age_on(member["dob"], today)
    if age is None:
        return ACTIVE if member["yuvak_no"] else None
    if age > config.YUVAK_MAX_AGE:
        return ALUMNI if member["yuvak_no"] else None
    if age >= config.YUVAK_MIN_AGE:
        return ACTIVE
    return None


def yuvak_dob_window(today: date | None = None):
    """(earliest, latest) DOB, inclusive, of someone who is 18..45 today."""
    today = today or date.today()
    latest = add_years(today, -config.YUVAK_MIN_AGE)
    earliest = date.fromordinal(add_years(today, -(config.YUVAK_MAX_AGE + 1)).toordinal() + 1)
    return earliest.isoformat(), latest.isoformat()


def sync_yuvak_ids(db, today: date | None = None) -> int:
    """Give a Yuvak Mandal ID to every living male aged 18..45 who has none.

    Members keep their ID for life, so once they pass 45 they show as alumni.
    Returns how many IDs were assigned.
    """
    earliest, latest = yuvak_dob_window(today)
    rows = db.execute(
        "SELECT id FROM members WHERE gender = 'M' AND yuvak_no IS NULL AND is_deceased = 0"
        " AND dob IS NOT NULL AND dob <> '' AND dob BETWEEN ? AND ? ORDER BY dob, id",
        (earliest, latest),
    ).fetchall()
    for row in rows:
        assign_yuvak_no(db, row["id"], today)
    db.commit()
    return len(rows)


def assign_yuvak_no(db, member_id, today: date | None = None):
    next_no = db.execute("SELECT COALESCE(MAX(yuvak_no), 0) + 1 FROM members").fetchone()[0]
    db.execute(
        "UPDATE members SET yuvak_no = ?, yuvak_joined_on = ? WHERE id = ? AND yuvak_no IS NULL",
        (next_no, (today or date.today()).isoformat(), member_id),
    )


# ------------------------------------------------------------------- members

@dataclass
class MemberFilter:
    q: str = ""
    area: str = ""
    family_id: int | None = None
    gender: str = ""
    yuvak: str = ""          # "", "active", "alumni"
    profession: str = ""
    include_deceased: bool = True


def full_name(m):
    return " ".join(p for p in (m["first_name"], m["middle_name"], m["last_name"]) if p)


def decorate(row, today: date | None = None):
    """Row -> dict with computed fields the templates use."""
    m = dict(row)
    m["code"] = member_code(m["id"])
    m["name"] = full_name(m)
    m["age"] = age_on(m["dob"], today)
    m["family_code"] = family_code(m["family_id"])
    m["yuvak_code"] = yuvak_code(m["yuvak_no"])
    m["yuvak_status"] = yuvak_status(m, today)
    m["gender_label"] = GENDERS.get(m["gender"], "")
    if m["yuvak_status"] == ALUMNI and m["dob"]:
        m["alumni_since"] = add_years(parse_date(m["dob"]), config.YUVAK_MAX_AGE + 1).isoformat()
    return m


MEMBER_SELECT = (
    "SELECT m.*, f.family_name, COALESCE(NULLIF(m.area, ''), f.area) AS display_area,"
    " COALESCE(NULLIF(m.address, ''), f.address) AS display_address,"
    " COALESCE(NULLIF(m.city, ''), f.city) AS display_city"
    " FROM members m LEFT JOIN families f ON f.id = m.family_id"
)


def _filter_sql(flt: MemberFilter, today=None):
    where, args = [], []
    if flt.q:
        number = parse_code(flt.q, config.MEMBER_PREFIX)
        like = f"%{flt.q.strip()}%"
        clause = ("(m.first_name || ' ' || COALESCE(m.middle_name, '') || ' ' || COALESCE(m.last_name, '')"
                  " LIKE ? OR m.first_name || ' ' || COALESCE(m.last_name, '') LIKE ?"
                  " OR m.phone LIKE ? OR m.profession LIKE ?")
        args += [like, like, like, like]
        if number is not None:
            clause += " OR m.id = ?"
            args.append(number)
        yno = parse_code(flt.q, config.YUVAK_PREFIX)
        if flt.q.strip().upper().startswith(config.YUVAK_PREFIX) and yno is not None:
            clause += " OR m.yuvak_no = ?"
            args.append(yno)
        where.append(clause + ")")
    if flt.area:
        where.append("COALESCE(NULLIF(m.area, ''), f.area) = ?")
        args.append(flt.area)
    if flt.family_id:
        where.append("m.family_id = ?")
        args.append(flt.family_id)
    if flt.gender:
        where.append("m.gender = ?")
        args.append(flt.gender)
    if flt.profession:
        where.append("m.profession LIKE ?")
        args.append(f"%{flt.profession}%")
    if not flt.include_deceased:
        where.append("m.is_deceased = 0")
    if flt.yuvak:
        earliest, latest = yuvak_dob_window(today)
        if flt.yuvak == "active":
            where.append("m.gender = 'M' AND m.is_deceased = 0 AND ((m.dob BETWEEN ? AND ?)"
                         " OR ((m.dob IS NULL OR m.dob = '') AND m.yuvak_no IS NOT NULL))")
            args += [earliest, latest]
        elif flt.yuvak == "alumni":
            where.append("m.gender = 'M' AND m.yuvak_no IS NOT NULL AND m.dob < ?")
            args.append(earliest)
    return (" WHERE " + " AND ".join(where)) if where else "", args


def search_members(db, flt: MemberFilter, limit=50, offset=0, order="name", today=None):
    where, args = _filter_sql(flt, today)
    orders = {
        "name": "m.first_name COLLATE NOCASE, m.last_name COLLATE NOCASE",
        "id": "m.id",
        "family": "m.family_id, m.id",
        "yuvak": "m.yuvak_no",
        "age": "m.dob IS NULL OR m.dob = '', m.dob",
    }
    total = db.execute(f"SELECT COUNT(*) FROM members m LEFT JOIN families f ON f.id = m.family_id{where}",
                       args).fetchone()[0]
    sql = f"{MEMBER_SELECT}{where} ORDER BY {orders.get(order, orders['name'])}"
    if limit:
        sql += " LIMIT ? OFFSET ?"
        args = args + [limit, offset]
    rows = db.execute(sql, args).fetchall()
    return [decorate(r, today) for r in rows], total


def get_member(db, member_id, today=None):
    row = db.execute(f"{MEMBER_SELECT} WHERE m.id = ?", (member_id,)).fetchone()
    return decorate(row, today) if row else None


def members_by_ids(db, ids):
    ids = [i for i in ids if i]
    if not ids:
        return {}
    marks = ",".join("?" * len(ids))
    return {r["id"]: decorate(r) for r in db.execute(f"{MEMBER_SELECT} WHERE m.id IN ({marks})", ids)}


def family_members(db, family_id):
    rows = db.execute(f"{MEMBER_SELECT} WHERE m.family_id = ? ORDER BY m.dob IS NULL OR m.dob = '', m.dob, m.id",
                      (family_id,)).fetchall()
    return [decorate(r) for r in rows]


def children_of(db, member_id):
    rows = db.execute(f"{MEMBER_SELECT} WHERE m.father_id = ? OR m.mother_id = ?"
                      " ORDER BY m.dob IS NULL OR m.dob = '', m.dob, m.id",
                      (member_id, member_id)).fetchall()
    return [decorate(r) for r in rows]


def siblings_of(db, member):
    if not member["father_id"] and not member["mother_id"]:
        return []
    rows = db.execute(
        f"{MEMBER_SELECT} WHERE m.id <> ? AND ((m.father_id IS NOT NULL AND m.father_id = ?)"
        " OR (m.mother_id IS NOT NULL AND m.mother_id = ?)) ORDER BY m.dob IS NULL OR m.dob = '', m.dob",
        (member["id"], member["father_id"], member["mother_id"])).fetchall()
    return [decorate(r) for r in rows]


class ValidationError(ValueError):
    pass


def validate_member(db, data, member_id=None):
    if not data.get("first_name"):
        raise ValidationError("First name is required.")
    if data.get("gender") not in GENDERS:
        raise ValidationError("Please choose a gender.")
    if data.get("dob"):
        dob = parse_date(data["dob"])
        if dob is None:
            raise ValidationError("Date of birth must be a valid date.")
        if dob > date.today():
            raise ValidationError("Date of birth cannot be in the future.")
    for key, label in (("father_id", "Father"), ("mother_id", "Mother"), ("spouse_id", "Spouse")):
        rel = data.get(key)
        if rel is None:
            continue
        if member_id and rel == member_id:
            raise ValidationError(f"{label} cannot be the same person.")
        other = db.execute("SELECT gender FROM members WHERE id = ?", (rel,)).fetchone()
        if other is None:
            raise ValidationError(f"{label}: member {member_code(rel)} does not exist.")
        if key == "father_id" and other["gender"] == "F":
            raise ValidationError("Father must be a male member.")
        if key == "mother_id" and other["gender"] == "M":
            raise ValidationError("Mother must be a female member.")
    if member_id:
        _check_not_own_ancestor(db, member_id, [data.get("father_id"), data.get("mother_id")])
    if data.get("family_id") and not db.execute("SELECT 1 FROM families WHERE id = ?",
                                                (data["family_id"],)).fetchone():
        raise ValidationError(f"Family {family_code(data['family_id'])} does not exist.")


def _check_not_own_ancestor(db, member_id, parent_ids):
    if not member_id:
        return
    seen, stack = set(), [p for p in parent_ids if p]
    while stack:
        pid = stack.pop()
        if pid == member_id:
            raise ValidationError("That would make this person their own ancestor.")
        if pid in seen:
            continue
        seen.add(pid)
        row = db.execute("SELECT father_id, mother_id FROM members WHERE id = ?", (pid,)).fetchone()
        if row:
            stack += [p for p in (row["father_id"], row["mother_id"]) if p]


def save_member(db, data, member_id=None, former_yuvak=False):
    """Insert or update a member. Returns the member id."""
    validate_member(db, data, member_id)
    values = [data.get(f) for f in MEMBER_FIELDS]
    if member_id:
        old = db.execute("SELECT spouse_id FROM members WHERE id = ?", (member_id,)).fetchone()
        sets = ", ".join(f"{f} = ?" for f in MEMBER_FIELDS)
        db.execute(f"UPDATE members SET {sets}, updated_at = datetime('now', 'localtime') WHERE id = ?",
                   values + [member_id])
        old_spouse = old["spouse_id"] if old else None
    else:
        marks = ", ".join("?" * len(MEMBER_FIELDS))
        cur = db.execute(f"INSERT INTO members ({', '.join(MEMBER_FIELDS)}) VALUES ({marks})", values)
        member_id = cur.lastrowid
        old_spouse = None
    _link_spouse(db, member_id, data.get("spouse_id"), old_spouse)
    if data.get("relation_to_head") == "Self (Head)" and data.get("family_id"):
        db.execute("UPDATE families SET head_member_id = ? WHERE id = ?", (member_id, data["family_id"]))
    if former_yuvak and data.get("gender") == "M":
        assign_yuvak_no(db, member_id)
    db.commit()
    sync_yuvak_ids(db)
    return member_id


def _link_spouse(db, member_id, spouse_id, old_spouse_id):
    """Keep spouse links two-way."""
    if old_spouse_id and old_spouse_id != spouse_id:
        db.execute("UPDATE members SET spouse_id = NULL WHERE id = ? AND spouse_id = ?",
                   (old_spouse_id, member_id))
    if spouse_id:
        # The new spouse's previous partner loses the link.
        db.execute("UPDATE members SET spouse_id = NULL WHERE spouse_id = ? AND id <> ?",
                   (spouse_id, member_id))
        db.execute("UPDATE members SET spouse_id = ? WHERE id = ?", (member_id, spouse_id))


def delete_member(db, member_id):
    db.execute("DELETE FROM members WHERE id = ?", (member_id,))
    db.commit()


# ------------------------------------------------------------------ families

def decorate_family(row):
    f = dict(row)
    f["code"] = family_code(f["id"])
    return f


def list_families(db, q="", area="", limit=50, offset=0):
    where, args = [], []
    if q:
        number = parse_code(q, config.FAMILY_PREFIX)
        clause = "(f.family_name LIKE ? OR f.address LIKE ? OR f.phone LIKE ?"
        args += [f"%{q}%"] * 3
        if number is not None:
            clause += " OR f.id = ?"
            args.append(number)
        where.append(clause + ")")
    if area:
        where.append("f.area = ?")
        args.append(area)
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    total = db.execute(f"SELECT COUNT(*) FROM families f{where_sql}", args).fetchone()[0]
    rows = db.execute(
        "SELECT f.*, (SELECT COUNT(*) FROM members m WHERE m.family_id = f.id) AS member_count,"
        " h.first_name || COALESCE(' ' || h.last_name, '') AS head_name"
        f" FROM families f LEFT JOIN members h ON h.id = f.head_member_id{where_sql}"
        " ORDER BY f.family_name COLLATE NOCASE, f.id LIMIT ? OFFSET ?",
        args + [limit, offset]).fetchall()
    return [decorate_family(r) for r in rows], total


def get_family(db, family_id):
    row = db.execute("SELECT * FROM families WHERE id = ?", (family_id,)).fetchone()
    return decorate_family(row) if row else None


def save_family(db, data, family_id=None):
    if not data.get("family_name"):
        raise ValidationError("Family name is required.")
    values = [data.get(f) for f in FAMILY_FIELDS]
    if family_id:
        sets = ", ".join(f"{f} = ?" for f in FAMILY_FIELDS)
        db.execute(f"UPDATE families SET {sets}, updated_at = datetime('now', 'localtime') WHERE id = ?",
                   values + [family_id])
    else:
        marks = ", ".join("?" * len(FAMILY_FIELDS))
        family_id = db.execute(f"INSERT INTO families ({', '.join(FAMILY_FIELDS)}) VALUES ({marks})",
                               values).lastrowid
    db.commit()
    return family_id


def delete_family(db, family_id):
    if db.execute("SELECT COUNT(*) FROM members WHERE family_id = ?", (family_id,)).fetchone()[0]:
        raise ValidationError("Move or delete this family's members before deleting the family.")
    db.execute("DELETE FROM families WHERE id = ?", (family_id,))
    db.commit()


def all_areas(db):
    rows = db.execute(
        "SELECT area FROM families WHERE area IS NOT NULL AND area <> ''"
        " UNION SELECT area FROM members WHERE area IS NOT NULL AND area <> '' ORDER BY 1").fetchall()
    return [r[0] for r in rows]


def all_professions(db):
    rows = db.execute("SELECT DISTINCT profession FROM members WHERE profession IS NOT NULL"
                      " AND profession <> '' ORDER BY 1").fetchall()
    return [r[0] for r in rows]


def member_choices(db):
    """Light list of all members for the relation pickers."""
    rows = db.execute(
        "SELECT m.id, m.first_name, m.middle_name, m.last_name, m.gender, m.dob, f.family_name"
        " FROM members m LEFT JOIN families f ON f.id = m.family_id"
        " ORDER BY m.first_name COLLATE NOCASE, m.last_name COLLATE NOCASE").fetchall()
    out = []
    for r in rows:
        label = f"{member_code(r['id'])} | {full_name(r)}"
        if r["dob"]:
            label += f" | b. {r['dob'][:4]}"
        if r["family_name"]:
            label += f" | {r['family_name']}"
        out.append({"id": r["id"], "gender": r["gender"], "label": label})
    return out


def family_choices(db):
    rows = db.execute("SELECT id, family_name, area FROM families ORDER BY family_name COLLATE NOCASE").fetchall()
    return [{"id": r["id"], "label": f"{family_code(r['id'])} | {r['family_name']}"
             + (f" | {r['area']}" if r["area"] else "")} for r in rows]


def stats(db, today=None):
    q = lambda sql, *a: db.execute(sql, a).fetchone()[0]  # noqa: E731
    return {
        "members": q("SELECT COUNT(*) FROM members WHERE is_deceased = 0"),
        "families": q("SELECT COUNT(*) FROM families"),
        "male": q("SELECT COUNT(*) FROM members WHERE is_deceased = 0 AND gender = 'M'"),
        "female": q("SELECT COUNT(*) FROM members WHERE is_deceased = 0 AND gender = 'F'"),
        "yuvak_active": search_members(db, MemberFilter(yuvak="active"), limit=1, today=today)[1],
        "yuvak_alumni": search_members(db, MemberFilter(yuvak="alumni"), limit=1, today=today)[1],
        "areas": len(all_areas(db)),
    }
