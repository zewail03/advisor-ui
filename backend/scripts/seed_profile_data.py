"""Seed read-only profile demographics for all students (fast bulk version).

Values are deterministic per student (seeded RNG on student_id) and derived
from existing dataset facts wherever possible:
  * date_of_birth : intake year (student_code prefix) minus 17-19 years
  * gender        : matches the student's actual first name
  * nationality   : ~96% Egyptian, small deterministic international mix
  * school_id     : HS-{intake_year}-{student_id:05d}
  * address/city  : north-coast-weighted Egyptian cities with real postal codes
  * emergency     : parent contact built from the student's own family name

Run (with the API server stopped, to avoid the SQLite write lock):
    python -m scripts.seed_profile_data
"""
import os
import random
import sqlite3

DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), "aiu.db")

FEMALE_NAMES = {
    "Alia", "Amira", "Asmaa", "Aya", "Basma", "Dalia", "Dina", "Duaa", "Eman",
    "Enas", "Esraa", "Farah", "Farida", "Faten", "Fatma", "Ghada", "Habiba",
    "Hadeer", "Hala", "Hana", "Hanaa", "Heba", "Iman", "Jana", "Laila", "Lama",
    "Lamia", "Layla", "Lina", "Mai", "Malak", "Maram", "Mariam", "Marina",
    "Marwa", "Menna", "Mona", "Nada", "Nadia", "Nadine", "Nagwa", "Nesma",
    "Noha", "Noor", "Nour", "Noura", "Radwa", "Rahma", "Rana", "Rania", "Reem",
    "Reham", "Ritaj", "Safaa", "Sahar", "Salma", "Salwa", "Samar", "Sanaa",
    "Sara", "Sawsan", "Shahd", "Shaima", "Shaimaa", "Soha", "Somaya", "Suad",
    "Yara", "Yasmin",
}

MALE_FIRST = ["Mohamed", "Ahmed", "Mahmoud", "Khaled", "Omar", "Hassan", "Tarek", "Ayman", "Sherif", "Hossam"]
FEMALE_FIRST = ["Mona", "Hala", "Nadia", "Heba", "Rania", "Sahar", "Ghada", "Eman", "Dalia", "Samar"]

# (city, postal_code, weight) — north-coast weighted, AIU is in El Alamein
CITIES = [
    ("Alexandria", "21500", 30),
    ("El Alamein", "51718", 18),
    ("Marsa Matruh", "51511", 8),
    ("Cairo", "11511", 16),
    ("Giza", "12511", 10),
    ("Borg El Arab", "21934", 6),
    ("Tanta", "31511", 4),
    ("Mansoura", "35511", 4),
    ("Damanhur", "22511", 4),
]
STREETS = [
    "El Geish Rd", "Corniche Rd", "El Horreya Ave", "Port Said St",
    "Ahmed Orabi St", "El Nasr St", "Fawzy Moaz St", "Gamal Abdel Nasser Ave",
    "23 July St", "El Bahr St",
]
NATIONALITIES = ["Sudanese", "Jordanian", "Palestinian", "Libyan", "Saudi", "Syrian"]
EMAIL_DOMAINS = ["gmail.com", "outlook.com", "yahoo.com"]

_city_pool = [c for c in CITIES for _ in range(c[2])]


def _build(student_id: int, student_code: str, full_name: str) -> tuple:
    rng = random.Random(student_id)
    parts = (full_name or "").split(" ", 1)
    first = parts[0] if parts else ""
    family = parts[1] if len(parts) > 1 else "Hassan"

    # intake year from the student_code prefix (e.g. 251... -> 2025)
    intake = 2000 + int(student_code[:2]) if student_code[:2].isdigit() else 2025
    birth_year = intake - rng.choice([17, 18, 18, 18, 19])
    dob = f"{birth_year:04d}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}"

    gender = "Female" if first in FEMALE_NAMES else "Male"
    nationality = "Egyptian" if rng.random() < 0.96 else rng.choice(NATIONALITIES)
    school_id = f"HS-{intake}-{student_id:05d}"

    city, postal, _w = rng.choice(_city_pool)
    address = f"{rng.randint(2, 180)} {rng.choice(STREETS)}"

    relation = rng.choices(["Father", "Mother", "Guardian"], weights=[6, 3, 1])[0]
    if relation == "Mother":
        contact_first = rng.choice(FEMALE_FIRST)
    else:
        contact_first = rng.choice(MALE_FIRST)
    contact_name = f"{contact_first} {family}"
    phone = "01" + rng.choice("0125") + "".join(str(rng.randint(0, 9)) for _ in range(8))
    email = (
        f"{contact_first}.{family.split(' ')[0]}{rng.randint(1, 99)}"
        f"@{rng.choice(EMAIL_DOMAINS)}"
    ).lower().replace(" ", "")

    return (dob, gender, nationality, school_id, address, city, postal,
            contact_name, relation, phone, email, student_id)


def seed() -> None:
    con = sqlite3.connect(DB, timeout=30)
    con.execute("PRAGMA busy_timeout=30000")
    cur = con.cursor()
    students = cur.execute(
        "SELECT student_id, student_code, full_name FROM students"
    ).fetchall()
    rows = [_build(sid, code, name) for sid, code, name in students]
    cur.executemany(
        "UPDATE students SET date_of_birth=?, gender=?, nationality=?, school_id=?, "
        "home_address=?, city=?, postal_code=?, emergency_contact_name=?, "
        "emergency_relationship=?, emergency_phone=?, emergency_email=? "
        "WHERE student_id=?",
        rows,
    )
    con.commit()
    con.close()
    print(f"Seeded profile demographics for {len(rows)} students.")


if __name__ == "__main__":
    seed()
