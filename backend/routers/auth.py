from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.database import get_db
from core.security import (
    create_access_token,
    create_refresh_token,
    create_twofactor_challenge,
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
from services import otp

router = APIRouter()


def _issue_tokens(student: Student) -> dict:
    access = create_access_token(
        {"sub": str(student.student_id), "student_code": student.student_code}
    )
    refresh = create_refresh_token({"sub": str(student.student_id)})
    return {"access_token": access, "refresh_token": refresh, "token_type": "bearer"}


@router.post("/login")
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

    # Password OK. If 2FA is on, mint a one-time code, "deliver" it (demo: on
    # screen; production: email/SMS), and require it at /auth/2fa/verify before
    # handing out tokens.
    if student.totp_enabled:
        code = otp.generate_code()
        otp.set_otp(student, code)
        await db.commit()
        challenge = create_twofactor_challenge({"sub": str(student.student_id)})
        resp = {"twofa_required": True, "challenge_token": challenge, "delivery": "demo"}
        if settings.otp_demo_show_code:
            resp["demo_code"] = code
        return resp

    return _issue_tokens(student)


class TwoFAVerifyRequest(BaseModel):
    challenge_token: str
    code: str


class TwoFACodeRequest(BaseModel):
    code: str


def _delivery_payload(code: str, extra: dict | None = None) -> dict:
    resp = {"delivery": "demo", **(extra or {})}
    if settings.otp_demo_show_code:
        resp["demo_code"] = code  # demo only — production emails/SMS this instead
    return resp


@router.post("/2fa/verify")
async def twofa_verify(req: TwoFAVerifyRequest, db: AsyncSession = Depends(get_db)):
    """Second login step: exchange a valid challenge + the emailed code for tokens."""
    try:
        payload = decode_token(req.challenge_token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Your verification step expired — sign in again.")
    if payload.get("type") != "2fa_challenge":
        raise HTTPException(status_code=401, detail="Invalid challenge token")
    sub = payload.get("sub")
    student = await db.get(Student, int(sub)) if sub else None
    if not student or not student.totp_enabled:
        raise HTTPException(status_code=401, detail="Two-factor is not active for this account")
    if not otp.verify_and_consume(student, req.code):
        raise HTTPException(status_code=401, detail="Invalid or expired code")
    await db.commit()
    return _issue_tokens(student)


@router.get("/2fa/status")
async def twofa_status(student: Student = Depends(get_current_student)):
    return {"enabled": bool(student.totp_enabled)}


@router.post("/2fa/send")
async def twofa_send(
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """Issue + deliver a one-time code for the logged-in student (used to confirm
    enabling or disabling 2FA)."""
    code = otp.generate_code()
    otp.set_otp(student, code)
    await db.commit()
    return _delivery_payload(code, {"sent": True})


@router.post("/2fa/enable")
async def twofa_enable(
    req: TwoFACodeRequest,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    if student.totp_enabled:
        return {"enabled": True}
    if not otp.verify_and_consume(student, req.code):
        raise HTTPException(status_code=400, detail="That code didn't match. Request a new one and try again.")
    student.totp_enabled = True
    await db.commit()
    return {"enabled": True}


@router.post("/2fa/disable")
async def twofa_disable(
    req: TwoFACodeRequest,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    if not student.totp_enabled:
        return {"enabled": False}
    if not otp.verify_and_consume(student, req.code):
        raise HTTPException(status_code=400, detail="Invalid code — two-factor stays on.")
    student.totp_enabled = False
    student.otp_hash = None
    student.otp_expires_at = None
    await db.commit()
    return {"enabled": False}


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
