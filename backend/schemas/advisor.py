from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AdvisorOut(BaseModel):
    id: str
    faculty_id: str
    full_name: str
    email: str
    department: Optional[str] = None
    specialization: Optional[str] = None
    office: Optional[str] = None
    phone: Optional[str] = None

    class Config:
        from_attributes = True


class ApprovalRequest(BaseModel):
    type: str
    related_id: Optional[str] = None
    semester_code: Optional[str] = None
    justification: Optional[str] = None
    payload_json: Optional[str] = None


class ApprovalDecision(BaseModel):
    approve: bool
    comment: Optional[str] = None


class ApprovalOut(BaseModel):
    id: str
    student_id: str
    advisor_id: Optional[str]
    type: str
    status: str
    related_id: Optional[str]
    semester_code: Optional[str]
    justification: Optional[str]
    advisor_comment: Optional[str]
    created_at: datetime
    resolved_at: Optional[datetime]

    class Config:
        from_attributes = True
