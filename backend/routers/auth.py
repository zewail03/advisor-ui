from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_student,
    get_password_hash,
    verify_password,
)
from models.academic import AcademicStanding
from models.student import Program, Student
from schemas.auth import (
    AccessTokenResponse,
    ChangePasswordRequest,
    LoginRequest,
    MeResponse,
    RefreshRequest,
    TokenResponse,
)

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Student).where(Student.student_code == req.student_code)
    )
    student = result.scalar_one_or_none()
    if not student or not student.hashed_password or not verify_password(
        req.password, student.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )

    access = create_access_token(
        {"sub": str(student.student_id), "student_code": student.student_code}
    )
    refresh = create_refresh_token({"sub": str(student.student_id)})
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh_token(req: RefreshRequest):
    try:
        payload = decode_token(req.refresh_token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Token is not a refresh token")
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    new_access = create_access_token({"sub": sub})
    return AccessTokenResponse(access_token=new_access)


@router.post("/change-password")
async def change_password(
    req: ChangePasswordRequest,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    if not student.hashed_password or not verify_password(
        req.old_password, student.hashed_password
    ):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    student.hashed_password = get_password_hash(req.new_password)
    await db.commit()
    return {"message": "Password updated successfully"}


@router.get("/me", response_model=MeResponse)
async def me(
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    program_code = None
    if student.program_id:
        program = await db.get(Program, student.program_id)
        program_code = program.code if program else None

    standing_result = await db.execute(
        select(AcademicStanding)
        .where(AcademicStanding.student_code == student.student_code)
        .order_by(AcademicStanding.recorded_at.desc())
        .limit(1)
    )
    standing = standing_result.scalar_one_or_none()

    return MeResponse(
        id=student.student_id,
        student_code=student.student_code,
        full_name=student.full_name,
        email=student.email,
        program=program_code,
        academic_level=student.level or 1,
        cgpa=float(standing.cgpa) if standing and standing.cgpa is not None else (
            float(student.cgpa) if student.cgpa is not None else None
        ),
        standing=standing.status if standing else None,
    )
