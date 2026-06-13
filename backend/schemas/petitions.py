from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class PetitionSubmit(BaseModel):
    type: str
    subject: str
    body: Optional[str] = None
    payload_json: Optional[str] = None
    enrollment_id: Optional[str] = None
    current_grade: Optional[str] = None
    requested_grade: Optional[str] = None
    freeze_semester_code: Optional[str] = None
    source_program_code: Optional[str] = None
    target_program_code: Optional[str] = None


class PetitionDecision(BaseModel):
    approve: bool
    reviewer_role: str = "registrar"
    comment: Optional[str] = None


class PetitionOut(BaseModel):
    id: str
    student_id: str
    type: str
    status: str
    subject: str
    body: Optional[str]
    enrollment_id: Optional[str]
    current_grade: Optional[str]
    requested_grade: Optional[str]
    freeze_semester_code: Optional[str]
    source_program_code: Optional[str]
    target_program_code: Optional[str]
    transfer_cgpa_snapshot: Optional[float]
    reviewer_id: Optional[str]
    reviewer_role: Optional[str]
    decision_comment: Optional[str]
    submitted_at: datetime
    decided_at: Optional[datetime]
    effect_applied: bool

    class Config:
        from_attributes = True
