"""Seed the database from real AIU CSVs.

Usage:
    cd backend
    python scripts/seed_from_csv.py --csv-dir "C:/path/to/csv"

Run AFTER tables exist (lifespan or `python scripts/create_tables.py`).
"""
from __future__ import annotations

import argparse
import asyncio
import math
import sys
from pathlib import Path
from typing import Any

import bcrypt
import pandas as pd
from sqlalchemy import delete, insert

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.database import AsyncSessionLocal, engine, Base  # noqa: E402
from models import (  # noqa: E402
    Program, Major, Student, Semester, RegistrationPeriod, AcademicStanding,
    RequirementCategory, RequirementGroup, RequirementGroupCourse,
    Course, Section, SectionMeeting, Prerequisite,
    Enrollment, Grade, Waitlist,
    Advisor, AdvisorAssignment, Notification,
)


DEFAULT_PASSWORD = "changeme123"
DEFAULT_PASSWORD_HASH = bcrypt.hashpw(DEFAULT_PASSWORD.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

CHUNK_SIZE = 1000


def _parse_date(val: Any):
    if val is None or (isinstance(val, float) and math.isnan(val)) or val == "":
        return None
    try:
        return pd.to_datetime(val, errors="coerce", dayfirst=False).date()
    except Exception:
        return None


def _parse_datetime(val: Any):
    if val is None or (isinstance(val, float) and math.isnan(val)) or val == "":
        return None
    try:
        ts = pd.to_datetime(val, errors="coerce", dayfirst=False)
        if pd.isna(ts):
            return None
        return ts.to_pydatetime()
    except Exception:
        return None


def _parse_bool(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return False
    s = str(val).strip().lower()
    return s in ("true", "1", "yes", "y", "t")


def _clean(v: Any):
    """Convert pandas NaN/NA into None; leave everything else untouched."""
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    if isinstance(v, str) and v.strip() == "":
        return None
    return v


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8-sig", keep_default_na=True)


async def _bulk_insert(db, model, rows: list[dict]):
    if not rows:
        return
    for i in range(0, len(rows), CHUNK_SIZE):
        chunk = rows[i : i + CHUNK_SIZE]
        await db.execute(insert(model), chunk)
    await db.commit()


async def _clear_all(db):
    """Wipe tables in FK-safe order."""
    for model in [
        Grade, Enrollment, Waitlist, SectionMeeting, Section, RegistrationPeriod,
        Prerequisite, RequirementGroupCourse, RequirementGroup, RequirementCategory,
        AdvisorAssignment, Advisor, Notification, AcademicStanding,
        Course, Student, Major, Program, Semester,
    ]:
        await db.execute(delete(model))
    await db.commit()


def load_programs(csv: Path) -> list[dict]:
    df = _read_csv(csv)
    return [
        {
            "program_id": int(r["program_id"]),
            "code": r["code"],
            "name": r["name"],
            "type": _clean(r.get("type")),
            "total_credits": int(r["total_credits"]) if not pd.isna(r["total_credits"]) else 140,
            "duration_years": int(r["duration_years"]) if not pd.isna(r["duration_years"]) else 4,
            "department": _clean(r.get("department")),
        }
        for _, r in df.iterrows()
    ]


def load_majors(csv: Path) -> list[dict]:
    df = _read_csv(csv)
    return [
        {
            "major_id": int(r["major_id"]),
            "program_id": int(r["program_id"]),
            "code": r["code"],
            "name": r["name"],
        }
        for _, r in df.iterrows()
    ]


def load_semesters(csv: Path) -> list[dict]:
    df = _read_csv(csv)
    return [
        {
            "semester_id": int(r["semester_id"]),
            "code": r["code"],
            "type": _clean(r.get("type")),
            "year_start": int(r["year_start"]) if not pd.isna(r["year_start"]) else None,
            "year_end": int(r["year_end"]) if not pd.isna(r["year_end"]) else None,
            "start_date": _parse_date(r.get("start_date")),
            "end_date": _parse_date(r.get("end_date")),
            "weeks": int(r["weeks"]) if not pd.isna(r["weeks"]) else None,
            "is_optional": _parse_bool(r.get("is_optional")),
        }
        for _, r in df.iterrows()
    ]


def load_courses(csv: Path) -> list[dict]:
    df = _read_csv(csv)
    return [
        {
            "course_id": int(r["course_id"]),
            "code": r["code"],
            "name": r["name"],
            "credits": int(r["credits"]) if not pd.isna(r["credits"]) else 3,
            "lab_hours": int(r.get("lab_hours") or 0),
            "lecture_hours": int(r.get("lecture_hours") or 0),
            "tutorial_hours": int(r.get("tutorial_hours") or 0),
            "other_hours": int(r.get("other_hours") or 0),
            "swl_hours": int(r.get("swl_hours") or 0),
            "category_id": int(r["category_id"]) if not pd.isna(r.get("category_id")) else None,
            "description": _clean(r.get("description")),
            "major_code": _clean(r.get("major_code")),
        }
        for _, r in df.iterrows()
    ]


def load_students(csv: Path) -> list[dict]:
    df = _read_csv(csv)
    rows = []
    for _, r in df.iterrows():
        rows.append(
            {
                "student_id": int(r["student_id"]),
                "student_code": str(r["student_code"]),
                "full_name": r["full_name"],
                "email": r["email"],
                "phone": str(r["phone"]) if not pd.isna(r["phone"]) else None,
                "hashed_password": DEFAULT_PASSWORD_HASH,
                "program_id": int(r["program_id"]),
                "major_id": int(r["major_id"]) if not pd.isna(r["major_id"]) else None,
                "level": int(r["level"]) if not pd.isna(r["level"]) else 1,
                "status": r.get("status") or "Active",
                "enrollment_date": _parse_date(r.get("enrollment_date")),
                "expected_graduation": _parse_date(r.get("expected_graduation")),
                "cgpa": float(r["cgpa"]) if not pd.isna(r.get("cgpa")) else 0.0,
            }
        )
    return rows


def load_sections(csv: Path) -> list[dict]:
    df = _read_csv(csv)
    return [
        {
            "section_id": int(r["section_id"]),
            "semester_id": int(r["semester_id"]),
            "section_number": str(r["section_number"]),
            "capacity": int(r["capacity"]) if not pd.isna(r["capacity"]) else 30,
            "status": r["status"],
            "course_code": r["course_code"],
            "instructor_name": _clean(r.get("instructor_name")),
        }
        for _, r in df.iterrows()
    ]


def load_section_meetings(csv: Path) -> list[dict]:
    df = _read_csv(csv)
    return [
        {
            "meeting_id": int(r["meeting_id"]),
            "section_id": int(r["section_id"]),
            "meeting_type": _clean(r.get("meeting_type")),
            "day_of_week": _clean(r.get("day_of_week")),
            "start_time": _clean(r.get("start_time")),
            "end_time": _clean(r.get("end_time")),
            "location": _clean(r.get("location")),
        }
        for _, r in df.iterrows()
    ]


def load_enrollments(csv: Path) -> list[dict]:
    df = _read_csv(csv)
    rows = []
    for _, r in df.iterrows():
        rows.append(
            {
                "enrollment_id": int(r["enrollment_id"]),
                "student_id": int(r["student_id"]),
                "section_id": int(r["section_id"]),
                "status": r["status"],
                "attempt_number": int(r.get("attempt_number") or 1),
                "is_retake": _parse_bool(r.get("is_retake")),
                "enrollment_date": _parse_datetime(r.get("enrollment_date")),
                "drop_date": _parse_datetime(r.get("drop_date")),
                "withdrawal_date": _parse_datetime(r.get("withdrawal_date")),
            }
        )
    return rows


def load_grades(csv: Path) -> list[dict]:
    df = _read_csv(csv)
    rows = []
    for _, r in df.iterrows():
        rows.append(
            {
                "grade_id": int(r["grade_id"]),
                "enrollment_id": int(r["enrollment_id"]),
                "grade_letter": _clean(r.get("grade_letter")),
                "grade_points": float(r["grade_points"]) if not pd.isna(r.get("grade_points")) else None,
                "percentage": float(r["percentage"]) if not pd.isna(r.get("percentage")) else None,
                "counts_in_gpa": _parse_bool(r.get("counts_in_gpa")),
                "is_improvement": _parse_bool(r.get("is_improvement")),
                "grade_date": _parse_datetime(r.get("grade_date")),
            }
        )
    return rows


def load_academic_standing(csv: Path) -> list[dict]:
    df = _read_csv(csv)
    rows = []
    for _, r in df.iterrows():
        rows.append(
            {
                "academic_standing_id": int(r["academic_standing_id"]),
                "semester_id": int(r["semester_id"]),
                "student_code": str(r["student_code"]),
                "semester_code": _clean(r.get("semester_code")),
                "semester_gpa": float(r["semester_gpa"]) if not pd.isna(r.get("semester_gpa")) else None,
                "cgpa": float(r["cgpa"]) if not pd.isna(r.get("cgpa")) else None,
                "status": r.get("status") or "Good Standing",
                "warning_count": int(r.get("warning_count") or 0),
                "probation_semesters": int(r.get("probation_semesters") or 0),
                "notes": _clean(r.get("notes")),
                "recorded_at": _parse_date(r.get("recorded_at")),
            }
        )
    return rows


def load_waitlist(csv: Path) -> list[dict]:
    df = _read_csv(csv)
    rows = []
    for _, r in df.iterrows():
        rows.append(
            {
                "waitlist_id": int(r["waitlist_id"]),
                "student_id": int(r["student_id"]),
                "section_id": int(r["section_id"]),
                "position": int(r["position"]) if not pd.isna(r["position"]) else 0,
                "priority": int(r.get("priority") or 0),
                "status": r.get("status") or "Waiting",
                "joined_at": _parse_datetime(r.get("joined_at")),
                "notified_at": _parse_datetime(r.get("notified_at")),
                "registered_at": _parse_datetime(r.get("registered_at")),
            }
        )
    return rows


def load_prerequisites(csv: Path) -> list[dict]:
    df = _read_csv(csv)
    return [
        {
            "prerequisite_id": int(r["prerequisite_id"]),
            "course_code": r["course_code"],
            "course_name": _clean(r.get("course_name")),
            "prerequisite_course_code": r["prerequisite_course_code"],
            "prerequisite_course_name": _clean(r.get("prerequisite_course_name")),
        }
        for _, r in df.iterrows()
    ]


def load_registration_periods(csv: Path) -> list[dict]:
    df = _read_csv(csv)
    return [
        {
            "registration_period_id": int(r["registration_period_id"]),
            "semester_id": int(r["semester_id"]),
            "priority_group": _clean(r.get("priority_group")),
            "open_date": _parse_datetime(r.get("open_date")),
            "close_date": _parse_datetime(r.get("close_date")),
            "is_active": _parse_bool(r.get("is_active")),
        }
        for _, r in df.iterrows()
    ]


def load_requirement_categories(csv: Path) -> list[dict]:
    df = _read_csv(csv)
    # Real CSV has typo "caregory_id" as header
    pk_col = "caregory_id" if "caregory_id" in df.columns else "category_id"
    return [
        {
            "caregory_id": int(r[pk_col]),
            "name": r["name"],
            "description": _clean(r.get("description")),
        }
        for _, r in df.iterrows()
    ]


def load_requirement_groups(csv: Path) -> list[dict]:
    df = _read_csv(csv)
    return [
        {
            "group_id": int(r["group_id"]),
            "program_id": int(r["program_id"]),
            "name": r["name"],
            "course_code": _clean(r.get("course code") or r.get("course_code")),
            "course_name": _clean(r.get("course name") or r.get("course_name")),
            "description": _clean(r.get("description")),
            "min_courses": int(r.get("min_courses") or 0),
            "min_credits": int(r.get("min_credits") or 0),
            "major_id": int(r["major_id"]) if not pd.isna(r.get("major_id")) else None,
        }
        for _, r in df.iterrows()
    ]


def load_requirement_group_courses(csv: Path) -> list[dict]:
    df = _read_csv(csv)
    return [
        {
            "rgc_id": int(r["rgc_id"]),
            "program_id": int(r["program_id"]),
            "major_id": int(r["major_id"]) if not pd.isna(r.get("major_id")) else None,
            "major_code": _clean(r.get("major_code")),
            "group_name": _clean(r.get("group_name")),
            "course_code": r["course_code"],
            "course_name": _clean(r.get("course_name")),
            "is_required": _parse_bool(r.get("is_required")),
            "required_year": int(r["required_year"]) if not pd.isna(r.get("required_year")) else None,
            "required_semester": int(r["required_semester"]) if not pd.isna(r.get("required_semester")) else None,
        }
        for _, r in df.iterrows()
    ]


def load_advisors(csv: Path) -> list[dict]:
    df = _read_csv(csv)
    return [
        {
            "advisor_id": int(r["advisor_id"]),
            "full_name": r["full_name"],
            "email": r["email"],
            "phone": str(r["phone"]) if not pd.isna(r.get("phone")) else None,
            "department": _clean(r.get("department")),
            "max_students": int(r.get("max_students") or 25),
            "specializations": _clean(r.get("specializations")),
        }
        for _, r in df.iterrows()
    ]


def load_advisor_assignments(csv: Path) -> list[dict]:
    df = _read_csv(csv)
    return [
        {
            "advisor_assignment_id": int(r["advisor_assignment_id"]),
            "advisor_id": int(r["advisor_id"]),
            "advisor_name": _clean(r.get("advisor_name")),
            "student_code": str(r["student_code"]),
            "student_name": _clean(r.get("student_name")),
            "assigned_date": _parse_date(r.get("assigned_date")),
            "end_date": _parse_date(r.get("end_date")),
            "is_active": _parse_bool(r.get("is_active")),
        }
        for _, r in df.iterrows()
    ]


def load_notifications(csv: Path) -> list[dict]:
    df = _read_csv(csv)
    return [
        {
            "notification_id": int(r["notification_id"]),
            "student_id": int(r["student_id"]),
            "type": _clean(r.get("type")),
            "subject": _clean(r.get("subject")),
            "message": r["message"],
            "status": r.get("status") or "Unread",
            "created_at": _parse_datetime(r.get("created_at")),
            "sent_at": _parse_datetime(r.get("sent_at")),
            "delivered_at": _parse_datetime(r.get("delivered_at")),
            "read_at": _parse_datetime(r.get("read_at")),
        }
        for _, r in df.iterrows()
    ]


LOAD_PLAN = [
    # (label, subpath, loader_fn, model)
    ("programs",                "programs/programs.csv",                                     load_programs,                   Program),
    ("majors",                  "majors/majors.csv",                                         load_majors,                     Major),
    ("semesters",               "semesters/semesters.csv",                                   load_semesters,                  Semester),
    ("requirement_categories",  "requirement_categories/requirement_categories.csv",         load_requirement_categories,     RequirementCategory),
    ("courses",                 "courses/courses.csv",                                       load_courses,                    Course),
    ("students",                "students/students.csv",                                     load_students,                   Student),
    ("sections",                "sections/sections.csv",                                     load_sections,                   Section),
    ("section_meetings",        "section meetings/section_meetings.csv",                     load_section_meetings,           SectionMeeting),
    ("prerequisites",           "prerequesites/prerequisites.csv",                           load_prerequisites,              Prerequisite),
    ("requirement_groups",      "requirement_groups/requirement_groups.csv",                 load_requirement_groups,         RequirementGroup),
    ("requirement_group_courses","requirement group courses/requirement_group_courses.csv",  load_requirement_group_courses,  RequirementGroupCourse),
    ("registration_periods",    "registration periods/registration_periods.csv",             load_registration_periods,       RegistrationPeriod),
    ("advisors",                "advisors/advisors.csv",                                     load_advisors,                   Advisor),
    ("advisor_assignments",     "advisors assignments/advisor_assignments.csv",              load_advisor_assignments,        AdvisorAssignment),
    ("enrollments",             "enrollments/enrollments.csv",                               load_enrollments,                Enrollment),
    ("grades",                  "grades/grades.csv",                                         load_grades,                     Grade),
    ("academic_standing",       "academic standing/academic_standing.csv",                   load_academic_standing,          AcademicStanding),
    ("waitlist",                "waitlist/waitlist.csv",                                     load_waitlist,                   Waitlist),
    ("notifications",           "notifications/notifications.csv",                           load_notifications,              Notification),
]


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv-dir", required=True, help="Path to the CSV root folder")
    parser.add_argument("--no-create", action="store_true", help="Skip create_all")
    parser.add_argument("--no-clear", action="store_true", help="Skip wiping existing rows")
    args = parser.parse_args()

    csv_root = Path(args.csv_dir).resolve()
    if not csv_root.exists():
        print(f"csv-dir not found: {csv_root}")
        sys.exit(1)

    if not args.no_create:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("Tables ensured.")

    async with AsyncSessionLocal() as db:
        if not args.no_clear:
            await _clear_all(db)
            print("Cleared existing rows.")

        for label, subpath, loader, model in LOAD_PLAN:
            csv_path = csv_root / subpath
            if not csv_path.exists():
                print(f"[skip] {label}: {csv_path} not found")
                continue
            rows = loader(csv_path)
            await _bulk_insert(db, model, rows)
            print(f"[ok]   {label}: {len(rows)} rows")

    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(main())
