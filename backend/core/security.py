from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import bcrypt
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.config import settings
from core.database import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def _truncate(password: str) -> bytes:
    # bcrypt silently ignores bytes past 72; truncate explicitly so both
    # hash + verify operate on the same input.
    return password.encode("utf-8")[:72]


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_truncate(plain), hashed.encode("utf-8"))
    except ValueError:
        return False


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(_truncate(password), bcrypt.gensalt()).decode("utf-8")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def create_twofactor_challenge(data: dict) -> str:
    """Short-lived token issued after a correct password when 2FA is on. It is
    NOT an access token — it only authorizes the /auth/2fa/verify step."""
    to_encode = data.copy()
    to_encode.update({
        "exp": datetime.utcnow() + timedelta(minutes=5),
        "type": "2fa_challenge",
    })
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def create_admin_token(data: dict) -> str:
    """Access token for staff/admin principals. Carries scope='admin' so a
    student token can never satisfy an admin dependency, and vice versa."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire, "type": "access", "scope": "admin"})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])


async def get_current_student(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exc
    try:
        payload = decode_token(token)
        # reject non-access tokens and admin-scoped tokens (no cross-principal use)
        if payload.get("type") != "access" or payload.get("scope") == "admin":
            raise credentials_exc
        student_id: Optional[str] = payload.get("sub")
        if not student_id:
            raise credentials_exc
    except JWTError:
        raise credentials_exc

    from models.student import Student

    try:
        student_pk = int(student_id)
    except (TypeError, ValueError):
        raise credentials_exc

    result = await db.execute(
        select(Student).where(Student.student_id == student_pk)
    )
    student = result.scalar_one_or_none()
    if not student:
        raise credentials_exc
    return student


# --------------------------- staff / admin auth --------------------------- #

oauth2_admin_scheme = OAuth2PasswordBearer(tokenUrl="/admin/auth/login", auto_error=False)


async def get_current_staff(
    token: Optional[str] = Depends(oauth2_admin_scheme),
    db: AsyncSession = Depends(get_db),
):
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate admin credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exc
    try:
        payload = decode_token(token)
        # an admin token MUST carry scope=admin — a student token never will
        if payload.get("type") != "access" or payload.get("scope") != "admin":
            raise credentials_exc
        staff_id = payload.get("sub")
        if not staff_id:
            raise credentials_exc
    except JWTError:
        raise credentials_exc

    from models.staff import Staff

    try:
        staff_pk = int(staff_id)
    except (TypeError, ValueError):
        raise credentials_exc

    staff = (
        await db.execute(select(Staff).where(Staff.staff_id == staff_pk))
    ).scalar_one_or_none()
    if not staff or not staff.is_active:
        raise credentials_exc
    return staff


def require_role(*allowed_roles: str):
    """Dependency factory: gate an endpoint to specific staff roles.

    super_admin always passes. Usage:
        staff: Staff = Depends(require_role(StaffRole.registrar))
    """
    allowed = {r.value if hasattr(r, "value") else str(r) for r in allowed_roles}

    async def _checker(staff=Depends(get_current_staff)):
        if staff.role != "super_admin" and staff.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions for this action",
            )
        return staff

    return _checker
