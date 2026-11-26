import io

from community_manager.services import people


def test_pages_load(client):
    for url in ("/", "/members/", "/families/", "/yuvak-mandal/", "/yuvak-mandal/?tab=alumni",
                "/yuvak-mandal/?tab=upcoming", "/backup", "/members/new", "/families/new", "/help"):
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


def test_missing_page_shows_friendly_404(client):
    r = client.get("/members/999")
    assert r.status_code == 404 and "Page not found" in r.get_data(as_text=True)


def test_demo_data_loads_and_renders(app, client, db):
    from community_manager import demo
    demo.load(db)
    demo.load(db)  # second call is a no-op
    assert db.execute("SELECT COUNT(*) FROM members").fetchone()[0] == 31
    for url in ("/", "/families/1/tree", "/yuvak-mandal/?tab=alumni", "/yuvak-mandal/?tab=upcoming", "/members/"):
        assert client.get(url).status_code == 200, url
    assert "Ramesh" in client.get("/yuvak-mandal/?tab=alumni").get_data(as_text=True)


class FakePhone:
    """Stands in for the Android app's save and open screens."""

    def __init__(self, pick=None, save=True):
        self.saved, self.pick, self.save = [], pick, save

    def save_file(self, path, filename, mime):
        self.saved.append((filename, mime, path.read_bytes()))
        return self.save

    def pick_file(self, target):
        if self.pick is None:
            return False
        target.write_bytes(self.pick)
        return True


def test_phone_app_saves_and_restores_through_native_screens(app, client):
    client.post("/families/new", data={"family_name": "Before"})
    phone = FakePhone()
    app.config["NATIVE"] = phone

    html = client.get("/backup").get_data(as_text=True)
    assert "Choose backup file and restore" in html and 'type="file"' not in html
    assert 'class="native"' in client.get("/families/1").get_data(as_text=True)

    r = client.get("/backup/download", headers={"Referer": "http://localhost/backup"})
    assert r.status_code == 302 and r.headers["Location"].endswith("/backup")
    name, mime, data = phone.saved[-1]
    assert name.endswith(".db") and data.startswith(b"SQLite format 3")

    r = client.get("/export/members.csv", follow_redirects=True)
    assert "0 members exported and saved" in r.get_data(as_text=True)
    assert phone.saved[-1][0].endswith(".csv")

    client.post("/families/new", data={"family_name": "After"})
    phone.pick = data
    r = client.post("/backup/restore", follow_redirects=True)
    assert "Backup restored" in r.get_data(as_text=True)
    html = client.get("/families/").get_data(as_text=True)
    assert "Before" in html and "After" not in html

    phone.pick, phone.save = None, False
    assert "No file was chosen" in client.post("/backup/restore", follow_redirects=True).get_data(as_text=True)
    assert "Nothing was saved" in client.get("/backup/download", follow_redirects=True).get_data(as_text=True)
