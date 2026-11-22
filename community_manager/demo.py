"""Sample data for showing the app without touching real records.

`python run.py --demo` (or the "Community Manager (demo)" shortcut) opens the app
on a separate demo database filled with this made-up data.
"""
from datetime import date, timedelta

from .services import people

FAMILIES = [
    # key, surname, area, address, phone, native place
    ("shah", "Shah", "Navrangpura", "12, Shantinath Society, near Vijay Char Rasta", "98250 11111", "Patan"),
    ("mehta", "Mehta", "Paldi", "B-4, Parshwa Apartments, Paldi Cross Road", "98240 22222", "Radhanpur"),
    ("doshi", "Doshi", "Satellite", "21, Mahavir Bungalows, Jodhpur Gam Road", "99090 33333", "Palanpur"),
    ("kothari", "Kothari", "Vasna", "7, Adinath Nagar, Vasna Barrage Road", "97250 44444", "Deesa"),
    ("sanghvi", "Sanghvi", "Navrangpura", "C-302, Samkit Tower, Stadium Road", "98980 55555", "Tharad"),
    ("jain", "Jain", "Bopal", "45, Siddhachal Residency, Bopal", "90990 66666", "Ranakpur"),
]


def _dob(today, years_ago, days_from_now=0, fixed=None):
    if fixed:
        return fixed
    d = today + timedelta(days=days_from_now)
    return people.add_years(d, -years_ago).isoformat()


def load(db, today=None):
    """Fill an empty database with sample families and members."""
    if db.execute("SELECT COUNT(*) FROM members").fetchone()[0]:
        return
    today = today or date.today()
    fam = {}
    for key, name, area, address, phone, native in FAMILIES:
        fam[key] = people.save_family(db, {
            "family_name": name, "area": area, "city": "Ahmedabad", "address": address,
            "phone": phone, "native_place": native, "pincode": None, "head_member_id": None, "notes": None,
        })
    ids = {}

    def add(key, first, gender, dob, family, **kw):
        data = {f: None for f in people.MEMBER_FIELDS}
        data.update(first_name=first, gender=gender, dob=dob, family_id=fam[family], is_deceased=0,
                    last_name=kw.pop("last_name", dict((k, n) for k, n, *_ in FAMILIES)[family]))
        for rel in ("father_id", "mother_id", "spouse_id"):
            if rel in kw:
                kw[rel] = ids[kw[rel]]
        former = kw.pop("former_yuvak", False)
        data.update(kw)
        ids[key] = people.save_member(db, data, former_yuvak=former)

    # Shah family: three generations, a married daughter in the Mehta family.
    add("hiralal", "Hiralal", "M", "1938-04-02", "shah", relation_to_head="Father", is_deceased=1,
        profession="Cloth merchant", marital_status="Married")
    add("kamla", "Kamlaben", "F", "1942-08-12", "shah", spouse_id="hiralal", relation_to_head="Mother",
        marital_status="Widowed", blood_group="B+")
    add("ramesh", "Ramesh", "M", _dob(today, 58, 3), "shah", middle_name="Hiralal", father_id="hiralal",
        mother_id="kamla", relation_to_head="Self (Head)", profession="Textile business", phone="98250 11111",
        marital_status="Married", education="B.Com", blood_group="O+", former_yuvak=True)
    add("sunita", "Sunita", "F", "1971-05-20", "shah", spouse_id="ramesh", relation_to_head="Wife",
        profession="Teacher", marital_status="Married", education="M.A., B.Ed.")
    add("mahesh", "Mahesh", "M", "1981-09-09", "shah", middle_name="Hiralal", father_id="hiralal",
        mother_id="kamla", relation_to_head="Brother", profession="Chartered Accountant", phone="98250 11112",
        marital_status="Married", education="CA")
    add("nisha", "Nisha", "F", "1984-02-11", "shah", spouse_id="mahesh", relation_to_head="Sister-in-law", profession="Homemaker", marital_status="Married")
    add("aarav", "Aarav", "M", "1998-11-30", "shah", middle_name="Ramesh", father_id="ramesh", mother_id="sunita",
        relation_to_head="Son", profession="Software engineer", phone="98250 11113", education="B.Tech",
        marital_status="Unmarried", blood_group="O+")
    add("diya", "Diya", "F", _dob(today, 24, 9), "shah", father_id="ramesh", mother_id="sunita",
        relation_to_head="Daughter", profession="Student", education="M.Sc.", marital_status="Unmarried")
    add("kunal", "Kunal", "M", _dob(today, 18, 40), "shah", father_id="ramesh", mother_id="sunita",
        relation_to_head="Son", profession="Student", education="Class 12", marital_status="Unmarried")
    add("vihaan", "Vihaan", "M", "2014-06-18", "shah", father_id="mahesh", mother_id="nisha",
        relation_to_head="Nephew", profession="Student")

    # Mehta family.
    add("prakash", "Prakash", "M", _dob(today, 46, 75), "mehta", relation_to_head="Self (Head)",
        profession="Diamond trader", phone="98240 22222", marital_status="Married", education="B.Com")
    add("priti", "Priti", "F", "1972-03-03", "mehta", father_id="hiralal", mother_id="kamla", spouse_id="prakash",
        relation_to_head="Wife", profession="Homemaker", marital_status="Married")
    add("rishabh", "Rishabh", "M", "2000-01-26", "mehta", father_id="prakash", mother_id="priti",
        relation_to_head="Son", profession="Pharmacist", phone="98240 22223", education="B.Pharm")
    add("khushi", "Khushi", "F", "2005-07-14", "mehta", father_id="prakash", mother_id="priti",
        relation_to_head="Daughter", profession="Student", education="B.Com")

    # Doshi family.
    add("jayesh", "Jayesh", "M", "1965-12-01", "doshi", relation_to_head="Self (Head)", profession="Doctor",
        phone="99090 33333", education="MBBS, MD", marital_status="Married", former_yuvak=True)
    add("rekha", "Rekha", "F", _dob(today, 59, 1), "doshi", spouse_id="jayesh", relation_to_head="Wife",
        profession="Doctor", education="MBBS", marital_status="Married")
    add("parth", "Parth", "M", "1992-04-10", "doshi", father_id="jayesh", mother_id="rekha", relation_to_head="Son",
        profession="Architect", phone="99090 33334", marital_status="Married", education="B.Arch")
    add("hetal", "Hetal", "F", "1994-10-02", "doshi", spouse_id="parth", relation_to_head="Daughter-in-law",
        profession="Interior designer", marital_status="Married")
    add("moksh", "Moksh", "M", "2019-08-23", "doshi", father_id="parth", mother_id="hetal",
        relation_to_head="Grandson")

    # Kothari family.
    add("navin", "Navin", "M", _dob(today, 45, 20), "kothari", relation_to_head="Self (Head)",
        profession="Jeweller", phone="97250 44444", marital_status="Married", education="B.Com")
    add("bhavna", "Bhavna", "F", "1984-01-19", "kothari", spouse_id="navin", relation_to_head="Wife",
        profession="Boutique owner", marital_status="Married")
    add("yash", "Yash", "M", "2007-03-30", "kothari", father_id="navin", mother_id="bhavna",
        relation_to_head="Son", profession="Student", education="Class 12")

    # Sanghvi family.
    add("dilip", "Dilip", "M", "1955-02-14", "sanghvi", relation_to_head="Self (Head)", profession="Retired banker",
        phone="98980 55555", marital_status="Married", former_yuvak=True)
    add("manju", "Manjula", "F", "1959-06-06", "sanghvi", spouse_id="dilip", relation_to_head="Wife",
        profession="Homemaker", marital_status="Married")
    add("chirag", "Chirag", "M", _dob(today, 37, 14), "sanghvi", father_id="dilip", mother_id="manju",
        relation_to_head="Son", profession="Stock broker", phone="98980 55556", marital_status="Married")
    add("pooja", "Pooja", "F", "1990-09-27", "sanghvi", spouse_id="chirag", relation_to_head="Daughter-in-law",
        profession="Software tester", marital_status="Married")
    add("aanya", "Aanya", "F", "2016-12-12", "sanghvi", father_id="chirag", mother_id="pooja",
        relation_to_head="Granddaughter")

    # Jain family.
    add("sanjay", "Sanjay", "M", "1978-08-08", "jain", relation_to_head="Self (Head)", profession="Pharma distributor",
        phone="90990 66666", marital_status="Married", education="M.Pharm")
    add("kavita", "Kavita", "F", "1981-11-21", "jain", spouse_id="sanjay", relation_to_head="Wife",
        profession="Chartered Accountant", marital_status="Married")
    add("dhruv", "Dhruv", "M", "2003-05-05", "jain", father_id="sanjay", mother_id="kavita", relation_to_head="Son",
        profession="Law student", education="LL.B.")
    add("tanvi", "Tanvi", "F", "2009-10-31", "jain", father_id="sanjay", mother_id="kavita",
        relation_to_head="Daughter", profession="Student")
