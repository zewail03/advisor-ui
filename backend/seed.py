import os
from typing import List, Tuple, Optional

import pandas as pd
from sqlalchemy.orm import Session

from models import Student, AcademicSummary, Course, StudentProfile, TranscriptCourse


def _split_semicolon_list(value) -> List[str]:
    if value is None:
        return []
    s = str(value).strip()
    if not s:
        return []
    return [x.strip() for x in s.split(";") if x.strip()]


def _pair_courses(codes_raw, titles_raw) -> List[Tuple[str, str]]:
    codes = _split_semicolon_list(codes_raw)
    titles = _split_semicolon_list(titles_raw)
    n = max(len(codes), len(titles))
    pairs: List[Tuple[str, str]] = []
    for i in range(n):
        code = codes[i] if i < len(codes) else ""
        title = titles[i] if i < len(titles) else ""
        if code:
            pairs.append((code, title))
    return pairs


def _to_int(v, default=0) -> int:
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return default
        # handle "12.0" coming from Excel
        return int(float(v))
    except Exception:
        return default


def _to_float_or_none(v) -> Optional[float]:
    try:
        if v is None or pd.isna(v):
            return None
        return float(v)
    except Exception:
        return None


def _resolve_excel_path() -> str:
    """
    Resolve Excel path in a backward-compatible way.
    Priority:
      1) EXCEL_PATH env var (absolute or relative)
      2) Local directory fallback to the newest known filename (v3 -> v2 -> original)
    """
    # 1) env override
    env_path = os.getenv("EXCEL_PATH")
    if env_path:
        if os.path.exists(env_path):
            return env_path
        # if relative, try relative to this file
        rel = os.path.join(os.path.dirname(__file__), env_path)
        if os.path.exists(rel):
            return rel
        raise RuntimeError(f"Excel file not found at EXCEL_PATH: {env_path}")

    # 2) fallbacks (same folder as seed.py)
    base_dir = os.path.dirname(__file__)
    candidates = [
        "AIU_Backend_Students_OneRow_ManyCourses_GPA39_withProfile_WITH_AcademicRecords_WITH_FinancialAccount_v3.xlsx",
        "AIU_Backend_Students_OneRow_ManyCourses_GPA39_withProfile_WITH_AcademicRecords_WITH_FinancialAccount_v2.xlsx",
        "AIU_Backend_Students_OneRow_ManyCourses_GPA39_withProfile_WITH_AcademicRecords_WITH_FinancialAccount.xlsx",
        "AIU_Backend_Students_OneRow_ManyCourses_GPA39_withProfile_WITH_AcademicRecords.xlsx",
    ]
    for fn in candidates:
        p = os.path.join(base_dir, fn)
        if os.path.exists(p):
            return p

    raise RuntimeError(
        "Excel file not found. Set EXCEL_PATH env var or place the Excel file next to seed.py."
    )


def _excel_engine_for(path: str) -> str:
    """
    Pick the correct pandas engine based on extension.
    - .xlsx => openpyxl
    - .xls  => xlrd
    """
    ext = os.path.splitext(path)[1].lower()
    if ext == ".xlsx":
        return "openpyxl"
    if ext == ".xls":
        return "xlrd"
    raise ValueError(f"Unsupported Excel extension: {ext}")


def _read_excel(path: str, **kwargs):
    """
    Read Excel using the correct engine explicitly (avoids xlrd xlsx errors).
    """
    engine = _excel_engine_for(path)
    return pd.read_excel(path, engine=engine, **kwargs)


def seed(db: Session) -> None:
    """
    Seeds the database from your Excel file.

    ✅ Fix: explicitly selects correct engine (.xlsx=openpyxl, .xls=xlrd)
    ✅ Keeps ALL existing academic seeding behavior.
    ✅ Still seeds TranscriptCourses exactly as before.
    ✅ Financial sheets are detected; seeding them is OPTIONAL and only runs
       if matching ORM models exist in models.py (to avoid breaking your backend).

    NOTE:
    - You chose option D (Payment Methods stored in frontend localStorage),
      so PaymentMethods sheet is intentionally ignored.
    """
    if db.query(Student).first():
        return

    excel_path = _resolve_excel_path()
    PROGRAM_TOTAL_HOURS = int(os.getenv("PROGRAM_TOTAL_HOURS", "144"))

    # -------------------------
    # Sheet 1: students + summary + profile + simple courses
    # -------------------------
    df = _read_excel(excel_path, sheet_name=0)

    for _, row in df.iterrows():
        student_id = str(row.get("student_id", "")).strip()
        name = str(row.get("student_name", "")).strip()
        password = str(row.get("temp_password", "")).strip()

        if not student_id or not name:
            continue

        # CGPA
        cgpa = row.get("cgpa", 0.0)
        try:
            cgpa = float(cgpa) if cgpa is not None and not pd.isna(cgpa) else 0.0
        except Exception:
            cgpa = 0.0

        # Total credits
        total_credit_hours = _to_int(row.get("total_credit_hours", 0), 0)
        remaining_hours = max(0, PROGRAM_TOTAL_HOURS - total_credit_hours)

        # Create student
        s = Student(student_id=student_id, name=name, password=password)
        db.add(s)
        db.commit()
        db.refresh(s)

        # Academic summary
        summary = AcademicSummary(
            student_id_fk=s.id,
            gpa=cgpa,
            total_credit_hours=total_credit_hours,
            remaining_hours=remaining_hours,
            class_rank="-",
            total_students=0,
        )
        db.add(summary)
        db.commit()

        # Profile
        prof = StudentProfile(
            student_id_fk=s.id,
            full_name=str(row.get("full_name", name) or "").strip(),
            student_id=str(row.get("student_id", student_id) or "").strip(),
            date_of_birth=str(row.get("date_of_birth", "") or "").strip(),
            gender=str(row.get("gender", "") or "").strip(),
            nationality=str(row.get("nationality", "") or "").strip(),
            school_id=str(row.get("school_id", "") or "").strip(),
            username=str(row.get("username", "") or "").strip(),
            email=str(row.get("email", "") or "").strip(),
            phone=str(row.get("phone", "") or "").strip(),
            home_address=str(row.get("home_address", "") or "").strip(),
            city=str(row.get("city", "") or "").strip(),
            postal_code=str(row.get("postal_code", "") or "").strip(),
            emergency_contact_name=str(row.get("emergency_contact_name", "") or "").strip(),
            emergency_relationship=str(row.get("emergency_relationship", "") or "").strip(),
            emergency_phone=str(row.get("emergency_phone", "") or "").strip(),
            emergency_email=str(row.get("emergency_email", "") or "").strip(),
            program=str(row.get("program", "") or "").strip(),
            major=str(row.get("major", "") or "").strip(),
            academic_year=str(row.get("academic_year", "") or "").strip(),
            expected_graduation=str(row.get("expected_graduation", "") or "").strip(),
            academic_advisor=str(row.get("academic_advisor", "") or "").strip(),
            notif_email=_to_int(row.get("notif_email", 1), 1),
            notif_sms=_to_int(row.get("notif_sms", 1), 1),
            notif_advisor=_to_int(row.get("notif_advisor", 1), 1),
            public_profile=_to_int(row.get("public_profile", 0), 0),
        )
        db.add(prof)
        db.commit()

        # Simple courses list (from semicolon columns)
        pairs = _pair_courses(row.get("course_codes"), row.get("course_titles"))
        for code, title in pairs:
            db.add(Course(student_id_fk=s.id, code=code, title=title))
        db.commit()

    # -------------------------
    # TranscriptCourses sheet (Academic Records)
    # -------------------------
    try:
        records_df = _read_excel(excel_path, sheet_name="TranscriptCourses")
    except Exception as e:
        print(f"⚠️  Warning: Could not read TranscriptCourses sheet: {e}")
        return

    student_map = {s.student_id: s.id for s in db.query(Student).all()}
    print(f"✅ Processing {len(records_df)} transcript course records...")

    for _, row in records_df.iterrows():
        sid_raw = str(row.get("student_id", "")).strip()
        if not sid_raw:
            continue

        student_pk = student_map.get(sid_raw)
        if not student_pk:
            continue

        term_raw = str(row.get("term", "")).strip()
        year_raw = row.get("year", "")

        if term_raw and year_raw and str(year_raw).strip() and str(year_raw).strip().lower() != "nan":
            term = f"{term_raw} {str(year_raw).strip()}"
        elif term_raw:
            term = term_raw
        else:
            term = "Unknown"

        course_code = str(row.get("course_code", "") or "").strip()
        # support both "course_title" (your original) and "course_name" (if you ever rename)
        course_name = str(row.get("course_title", row.get("course_name", "")) or "").strip()

        credits = _to_int(row.get("credits", 0), 0)
        grade_letter = str(row.get("grade", "") or "").strip()
        grade_points = _to_float_or_none(row.get("points"))
        status = str(row.get("status", "") or "").strip()

        db.add(
            TranscriptCourse(
                student_id_fk=student_pk,
                term=term,
                course_code=course_code,
                course_name=course_name,
                credits=credits,
                grade_letter=grade_letter,
                grade_points=grade_points,
                status=status,
            )
        )

    db.commit()
    print(f"✅ Successfully seeded {len(records_df)} transcript courses!")

    # -------------------------
    # OPTIONAL: Financial sheets (only if you later add ORM models)
    # -------------------------
    # You chose payment methods = frontend localStorage => ignore PaymentMethods sheet.
    try:
        from models import FinancialAccount, FinancialTransaction, Scholarship  # type: ignore
    except Exception:
        FinancialAccount = None  # type: ignore
        FinancialTransaction = None  # type: ignore
        Scholarship = None  # type: ignore

    # If you haven't added these models yet, we just log and exit gracefully.
    if not (FinancialAccount and FinancialTransaction and Scholarship):
        try:
            xl = pd.ExcelFile(excel_path, engine=_excel_engine_for(excel_path))
            financial_sheets = {"FinancialAccounts", "FinancialTransactions", "Scholarships"}
            present = financial_sheets.intersection(set(xl.sheet_names))
            if present:
                print(
                    f"ℹ️  Financial sheets detected in Excel ({', '.join(sorted(present))}), "
                    "but Financial ORM models are not defined yet, so they were not seeded."
                )
        except Exception:
            pass
        return

    # If you DO add the models later, the code below will start seeding automatically.
    try:
        fa_df = _read_excel(excel_path, sheet_name="FinancialAccounts")
        tx_df = _read_excel(excel_path, sheet_name="FinancialTransactions")
        sch_df = _read_excel(excel_path, sheet_name="Scholarships")
    except Exception as e:
        print(f"⚠️  Warning: Could not read financial sheets: {e}")
        return

    # Map student_id string -> students.id PK
    student_map = {s.student_id: s.id for s in db.query(Student).all()}

    # Seed FinancialAccounts
    for _, r in fa_df.iterrows():
        sid = str(r.get("student_id", "")).strip()
        student_pk = student_map.get(sid)
        if not student_pk:
            continue
        db.add(
            FinancialAccount(
                student_id_fk=student_pk,
                term=str(r.get("term", "")).strip(),
                term_credits=_to_int(r.get("term_credits", 0), 0),
                tuition_fee=_to_int(r.get("tuition_fee", 0), 0),
                transportation_fee=_to_int(r.get("transportation_fee", 0), 0),
                fines=_to_int(r.get("fines", 0), 0),
                total_charges=_to_int(r.get("total_charges", 0), 0),
                scholarship_credit=_to_int(r.get("scholarship_credit", 0), 0),
                payments_made=_to_int(r.get("payments_made", 0), 0),
                current_balance=_to_int(r.get("current_balance", 0), 0),
                payment_due_date=str(r.get("payment_due_date", "")).strip(),
                payment_status=str(r.get("payment_status", "")).strip(),
                currency=str(r.get("currency", "EGP")).strip(),
                last_updated=str(r.get("last_updated", "")).strip(),
            )
        )
    db.commit()
    print("✅ Seeded FinancialAccounts")

    # Seed FinancialTransactions
    for _, r in tx_df.iterrows():
        sid = str(r.get("student_id", "")).strip()
        student_pk = student_map.get(sid)
        if not student_pk:
            continue
        db.add(
            FinancialTransaction(
                student_id_fk=student_pk,
                transaction_id=str(r.get("transaction_id", "")).strip(),
                term=str(r.get("term", "")).strip(),
                date=str(r.get("date", "")).strip(),
                type=str(r.get("type", "")).strip(),
                category=str(r.get("category", "")).strip(),
                description=str(r.get("description", "")).strip(),
                amount=_to_int(r.get("amount", 0), 0),
                currency=str(r.get("currency", "EGP")).strip(),
                status=str(r.get("status", "")).strip(),
                reference=str(r.get("reference", "")).strip(),
            )
        )
    db.commit()
    print("✅ Seeded FinancialTransactions")

    # Seed Scholarships
    for _, r in sch_df.iterrows():
        sid = str(r.get("student_id", "")).strip()
        student_pk = student_map.get(sid)
        if not student_pk:
            continue
        db.add(
            Scholarship(
                student_id_fk=student_pk,
                scholarship_id=str(r.get("scholarship_id", "")).strip(),
                term=str(r.get("term", "")).strip(),
                scholarship_type=str(r.get("scholarship_type", "")).strip(),
                percentage=_to_int(r.get("percentage", 0), 0),
                amount=_to_int(r.get("amount", 0), 0),
                status=str(r.get("status", "")).strip(),
                criteria_basis=str(r.get("criteria_basis", "")).strip(),
                cgpa_at_award=_to_float_or_none(r.get("cgpa_at_award")),
                notes=str(r.get("notes", "")).strip(),
            )
        )
    db.commit()
    print("✅ Seeded Scholarships")
