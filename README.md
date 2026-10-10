# Community Manager

Software to manage the followers of Ambesh Guru (Shwetambar Jain community): members,
families, the Ambesh Yuvak Mandal and family trees. It runs on one Windows PC, needs no
internet, and keeps all data in a single SQLite database file on that PC.

## What it does

- **Member ID** for every person (`AM-00001`) and **Family ID** for every household (`AF-0001`).
- **Member details**: name, gender, date of birth (age is worked out automatically), mobile,
  email, address, area, city, profession, education, blood group, marital status, notes.
- **Family relations**: family, relation to the head, father, mother, husband/wife. Spouse
  links are kept two-way automatically. The member page lists parents, spouse, children and
  brothers/sisters.
- **Family tree** for each family and for each member, drawn from the father/mother/spouse
  links. Married daughters who moved to another family still appear in their parents' tree.
- **Ambesh Yuvak Mandal ID** (`AYM-0001`) given automatically to every male aged 18 to 45.
  When a boy turns 18 he gets his ID the next time the app is opened.
- **Alumni**: after 45 a member keeps his Yuvak ID and is listed as alumni automatically.
  Older men who were members in the past can be marked as alumni with one tick box.
- Yuvak Mandal page with Active, Alumni, and "Coming up this year" (who joins or becomes
  alumni in the next 12 months).
- Search and filters (name, any ID, phone, area, gender, profession, Yuvak status).
- Export to Excel (CSV), print any page.
- Backup: an automatic copy at every start (last 15 kept), one-click backup download and restore.

## Installing on Windows (for the person using it)

1. Get `CommunityManager-Setup.exe` (see "Building the installer" below).
2. Double-click it and follow the steps. No admin rights are needed.
3. Open **Community Manager** from the desktop or Start menu. A black window opens and
   the app appears in the web browser. Keep the black window open while working; close
   it to stop the app.

Data is stored in `%APPDATA%\CommunityManager\community.db`. Uninstalling or upgrading
the app does not delete it. Use **Backup → Download backup** regularly and keep the
file somewhere safe.

## Building the installer

**Easiest: GitHub Actions.** Every push builds the installer automatically. Open the
repository's *Actions* tab, click the latest "Test and build Windows installer" run,
and download `CommunityManager-Setup` from the *Artifacts* section.

**On a Windows PC:** install Python 3.11+ and [Inno Setup 6](https://jrsoftware.org/isdl.php), then run

```bat
packaging\build_windows.bat
```

The installer is written to `dist\CommunityManager-Setup.exe`.

## Running from source (for development)

```bash
pip install -r requirements.txt -r requirements-dev.txt
python run.py            # opens http://127.0.0.1:5055 in the browser
python -m pytest         # run the tests
```

Set `COMMUNITY_DATA_DIR` to use a different data folder (handy for trying things out
without touching real data).

## How the code is organised

| Path | What it is |
| --- | --- |
| `run.py` | Launcher: starts the server and opens the browser |
| `community_manager/config.py` | ID prefixes, Yuvak Mandal age limits, names |
| `community_manager/migrations/` | Database structure, one numbered `.sql` file per change |
| `community_manager/services/people.py` | Members, families, IDs, Yuvak Mandal rules |
| `community_manager/services/tree.py` | Family tree building |
| `community_manager/routes/` | One file per section of the app (Flask blueprints) |
| `community_manager/templates/` | HTML pages |
| `packaging/` | PyInstaller and Inno Setup files for the Windows installer |

### Adding a feature later

- **New database fields or tables:** add `community_manager/migrations/002_<name>.sql`.
  It runs once automatically on the next start, so existing data is kept.
- **New section** (for example events or donations): add a service in `services/`, a
  blueprint in `routes/`, register it in `community_manager/__init__.py`, and add a link
  in `templates/base.html`.
- **Change ID formats or age limits:** edit `community_manager/config.py`.
