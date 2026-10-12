"""Builds family trees from the father / mother / spouse links."""
from . import people

MAX_DEPTH = 15


def _load_all(db):
    rows = db.execute(f"{people.MEMBER_SELECT}").fetchall()
    members = {r["id"]: people.decorate(r) for r in rows}
    children = {}
    for m in members.values():
        for parent in {m["father_id"], m["mother_id"]} - {None}:
            children.setdefault(parent, []).append(m["id"])
    return members, children


def _sort_key(members):
    return lambda mid: (not members[mid]["dob"], members[mid]["dob"] or "", mid)


def _build(members, children, person_id, seen, depth=0):
    person = members[person_id]
    seen.add(person_id)
    spouse = members.get(person["spouse_id"])
    if spouse and spouse["id"] in seen:
        spouse = None
    if spouse:
        seen.add(spouse["id"])
    kids = set(children.get(person_id, []))
    if spouse:
        kids |= set(children.get(spouse["id"], []))
    node = {"person": person, "spouse": spouse, "children": []}
    if depth >= MAX_DEPTH:
        return node
    for kid in sorted(kids, key=_sort_key(members)):
        if kid not in seen:
            node["children"].append(_build(members, children, kid, seen, depth + 1))
    return node


def family_tree(db, family_id):
    """List of root nodes covering everyone in the family."""
    members, children = _load_all(db)
    in_family = {mid for mid, m in members.items() if m["family_id"] == family_id}

    def has_parent_in_family(mid):
        m = members[mid]
        return bool({m["father_id"], m["mother_id"]} & in_family)

    roots = []
    for mid in sorted(in_family, key=_sort_key(members)):
        if has_parent_in_family(mid):
            continue
        spouse_id = members[mid]["spouse_id"]
        if spouse_id in in_family and has_parent_in_family(spouse_id):
            continue  # married in: shown next to their spouse
        roots.append(mid)
    # Prefer the husband as the root of a couple so the wife shows beside him.
    roots.sort(key=lambda mid: members[mid]["gender"] != "M")

    seen, nodes = set(), []
    for mid in roots:
        if mid not in seen:
            nodes.append(_build(members, children, mid, seen))
    # Anyone still missing (e.g. a loop in the data) is shown on their own.
    for mid in sorted(in_family - seen):
        nodes.append(_build(members, children, mid, seen))
    return nodes


def member_tree(db, member_id):
    """Tree from the member's eldest known paternal ancestor downwards."""
    members, children = _load_all(db)
    if member_id not in members:
        return None
    top, visited = member_id, {member_id}
    while True:
        m = members[top]
        parent = m["father_id"] or m["mother_id"]
        if not parent or parent in visited or parent not in members:
            break
        visited.add(parent)
        top = parent
    return _build(members, children, top, set())
