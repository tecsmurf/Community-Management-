import io

from community_manager.services import people


def test_pages_load(client):
    for url in ("/", "/members/", "/families/", "/yuvak-mandal/", "/yuvak-mandal/?tab=alumni",
                "/yuvak-mandal/?tab=upcoming", "/backup", "/members/new", "/families/new"):
        assert client.get(url).status_code == 200, url


def test_full_flow(client, db):
    r = client.post("/families/new", data={"family_name": "Shah", "area": "Navrangpura", "address": "12 MG Road"})
    assert r.status_code == 302
    fam_label = "AF-0001 | Shah"

    r = client.post("/members/new", data={"first_name": "Ramesh", "last_name": "Shah", "gender": "M",
                                          "dob": "1975-03-04", "family_id": fam_label,
                                          "relation_to_head": "Self (Head)", "profession": "Business"})
    assert r.status_code == 302
    r = client.post("/members/new", data={"first_name": "Sunita", "gender": "F", "family_id": fam_label,
                                          "spouse_id": "AM-00001 | Ramesh Shah"})
    assert r.status_code == 302
    r = client.post("/members/new", data={"first_name": "Aarav", "gender": "M", "dob": "2001-05-05",
                                          "family_id": fam_label, "father_id": "AM-00001 | Ramesh Shah",
                                          "mother_id": "AM-00002"})
    assert r.status_code == 302

    assert people.get_family(db, 1)["head_member_id"] == 1
    assert people.get_member(db, 1)["spouse_id"] == 2
    aarav = people.get_member(db, 3)
    assert aarav["yuvak_code"] == "AYM-0001" and aarav["display_area"] == "Navrangpura"

    page = client.get("/members/3").get_data(as_text=True)
    assert "AYM-0001" in page and "Ramesh" in page
    assert "Aarav" in client.get("/families/1/tree").get_data(as_text=True)
    assert "Aarav" in client.get("/members/3/tree").get_data(as_text=True)
    assert "Aarav" in client.get("/yuvak-mandal/").get_data(as_text=True)
    assert "Aarav" in client.get("/members/?q=AM-00003").get_data(as_text=True)
    assert "Aarav" in client.get("/members/?q=AYM-0001").get_data(as_text=True)
    assert client.get("/search?q=AF-0001").headers["Location"].endswith("/families/1")

    csv = client.get("/export/members.csv").get_data(as_text=True)
    assert "AYM-0001" in csv and csv.count("\n") == 4

    r = client.post("/members/3/edit", data={"first_name": "Aarav", "gender": "M", "dob": "2001-05-05",
                                             "family_id": fam_label, "father_id": "AM-00003"})
    assert r.status_code == 400 and "same person" in r.get_data(as_text=True)


def test_bad_picker_value_shows_error(client):
    r = client.post("/members/new", data={"first_name": "X", "gender": "M", "father_id": "somebody"})
    assert r.status_code == 400
    assert "Pick a name from the list" in r.get_data(as_text=True)


def test_backup_download_and_restore(client, db):
    client.post("/families/new", data={"family_name": "Before"})
    backup = client.get("/backup/download").data
    assert backup.startswith(b"SQLite format 3")
    client.post("/families/new", data={"family_name": "After"})
    r = client.post("/backup/restore", data={"file": (io.BytesIO(backup), "b.db")},
                    content_type="multipart/form-data")
    assert r.status_code == 302
    html = client.get("/families/").get_data(as_text=True)
    assert "Before" in html and "After" not in html

    r = client.post("/backup/restore", data={"file": (io.BytesIO(b"junk"), "b.db")},
                    content_type="multipart/form-data", follow_redirects=True)
    assert "not a Community Manager backup" in r.get_data(as_text=True)
