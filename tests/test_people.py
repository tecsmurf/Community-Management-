from datetime import date

import pytest

from community_manager.services import people, tree

TODAY = date(2026, 10, 10)


def add(db, first, gender="M", dob=None, **kw):
    data = {f: None for f in people.MEMBER_FIELDS}
    data.update(first_name=first, gender=gender, dob=dob, is_deceased=0, **kw)
    return people.save_member(db, data)


def test_age_and_birthdays():
    assert people.age_on("2008-10-10", TODAY) == 18
    assert people.age_on("2008-10-11", TODAY) == 17
    assert people.age_on("2000-02-29", date(2026, 2, 28)) == 25
    assert people.age_on("", TODAY) is None


def test_codes_round_trip():
    assert people.member_code(12) == "AM-00012"
    assert people.family_code(3) == "AF-0003"
    assert people.yuvak_code(7) == "AYM-0007"
    for text in ("AM-00012", "am12", "12", " AM-00012 "):
        assert people.parse_code(text, "AM") == 12
    assert people.parse_code("Ramesh", "AM") is None


def test_yuvak_status_boundaries():
    m = {"gender": "M", "dob": "2008-10-10", "yuvak_no": 1}
    assert people.yuvak_status(m, TODAY) == people.ACTIVE          # just turned 18
    assert people.yuvak_status({**m, "dob": "2008-10-11"}, TODAY) is None  # 17
    assert people.yuvak_status({**m, "dob": "1980-10-11"}, TODAY) == people.ACTIVE  # still 45
    assert people.yuvak_status({**m, "dob": "1980-10-10"}, TODAY) == people.ALUMNI  # turned 46
    assert people.yuvak_status({**m, "gender": "F"}, TODAY) is None
    assert people.yuvak_status({**m, "dob": "1960-01-01", "yuvak_no": None}, TODAY) is None


def test_dob_window_matches_status():
    earliest, latest = people.yuvak_dob_window(TODAY)
    assert (earliest, latest) == ("1980-10-11", "2008-10-10")


def test_ids_assigned_to_eligible_males_only(db):
    young = add(db, "Aarav", dob="2000-01-01")
    boy = add(db, "Kunal", dob="2015-01-01")
    girl = add(db, "Diya", gender="F", dob="2000-01-01")
    elder = add(db, "Mahavir", dob="1950-01-01")
    nodob = add(db, "Unknown")
    got = {i: people.get_member(db, i) for i in (young, boy, girl, elder, nodob)}
    assert got[young]["yuvak_code"] == "AYM-0001" and got[young]["yuvak_status"] == "Active"
    for i in (boy, girl, elder, nodob):
        assert got[i]["yuvak_no"] is None


def test_member_becomes_alumni_and_keeps_id(db):
    mid = add(db, "Rohit", dob="1981-06-01")
    code = people.get_member(db, mid)["yuvak_code"]
    later = date(2027, 6, 1)  # turns 46
    m = people.get_member(db, mid, today=later)
    assert m["yuvak_status"] == "Alumni" and m["yuvak_code"] == code
    assert m["alumni_since"] == "2027-06-01"
    alumni, total = people.search_members(db, people.MemberFilter(yuvak="alumni"), today=later)
    assert total == 1 and alumni[0]["id"] == mid
    assert people.search_members(db, people.MemberFilter(yuvak="active"), today=later)[1] == 0


def test_boy_gets_id_when_he_turns_18(db):
    mid = add(db, "Kunal", dob="2008-12-01")
    assert people.get_member(db, mid)["yuvak_no"] is None
    assert people.sync_yuvak_ids(db, today=date(2026, 12, 1)) == 1
    assert people.get_member(db, mid)["yuvak_code"] == "AYM-0001"


def test_former_member_flag_makes_older_man_alumni(db):
    data = {f: None for f in people.MEMBER_FIELDS}
    data.update(first_name="Suresh", gender="M", dob="1960-01-01", is_deceased=0)
    mid = people.save_member(db, data, former_yuvak=True)
    assert people.get_member(db, mid)["yuvak_status"] == "Alumni"


def test_spouse_link_is_two_way_and_moves(db):
    a = add(db, "Ramesh")
    b = add(db, "Sunita", gender="F", spouse_id=a)
    assert people.get_member(db, a)["spouse_id"] == b
    c = add(db, "Kavita", gender="F")
    data = {**{f: people.get_member(db, a)[f] for f in people.MEMBER_FIELDS}, "spouse_id": c}
    people.save_member(db, data, a)
    assert people.get_member(db, b)["spouse_id"] is None
    assert people.get_member(db, c)["spouse_id"] == a


def test_validation(db):
    son = add(db, "Son")
    with pytest.raises(people.ValidationError):
        add(db, "", gender="M")
    with pytest.raises(people.ValidationError):
        add(db, "X", gender="M", mother_id=son)  # mother must not be male
    with pytest.raises(people.ValidationError):
        add(db, "X", gender="M", dob="2999-01-01")
    child = add(db, "Child", father_id=son)
    data = {**{f: people.get_member(db, son)[f] for f in people.MEMBER_FIELDS}, "father_id": child}
    with pytest.raises(people.ValidationError):
        people.save_member(db, data, son)  # own ancestor


def test_family_tree(db):
    fam = people.save_family(db, {"family_name": "Shah"})
    other = people.save_family(db, {"family_name": "Mehta"})
    grandpa = add(db, "Grandpa", dob="1940-01-01", family_id=fam)
    grandma = add(db, "Grandma", gender="F", dob="1945-01-01", family_id=fam, spouse_id=grandpa)
    son = add(db, "Son", dob="1970-01-01", family_id=fam, father_id=grandpa, mother_id=grandma)
    add(db, "Bahu", gender="F", dob="1972-01-01", family_id=fam, spouse_id=son)
    daughter = add(db, "Daughter", gender="F", dob="1968-01-01", family_id=other,
                   father_id=grandpa, mother_id=grandma)
    add(db, "Grandson", dob="2000-01-01", family_id=fam, father_id=son)

    roots = tree.family_tree(db, fam)
    assert len(roots) == 1
    top = roots[0]
    assert top["person"]["id"] == grandpa and top["spouse"]["id"] == grandma
    kids = [c["person"]["id"] for c in top["children"]]
    assert kids == [daughter, son]  # eldest first, married daughter still shown
    son_node = top["children"][1]
    assert son_node["spouse"]["first_name"] == "Bahu"
    assert [c["person"]["first_name"] for c in son_node["children"]] == ["Grandson"]

    member_root = tree.member_tree(db, son)
    assert member_root["person"]["id"] == grandpa


def test_delete_family_requires_empty(db):
    fam = people.save_family(db, {"family_name": "Jain"})
    mid = add(db, "A", family_id=fam)
    with pytest.raises(people.ValidationError):
        people.delete_family(db, fam)
    people.delete_member(db, mid)
    people.delete_family(db, fam)
    assert people.get_family(db, fam) is None
