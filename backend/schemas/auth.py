from pydantic import BaseModel, Field
from typing import Optional


class LoginRequest(BaseModel):
    student_code: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8)


class MeResponse(BaseModel):
    id: int
    student_code: str
    full_name: str
    email: str
    program: Optional[str] = None
    academic_level: int
    cgpa: Optional[float] = None
    standing: Optional[str] = None
