from typing import Optional

from pydantic import BaseModel


class CapstoneEnrollRequest(BaseModel):
    stage: str  # field_training_a | _b | graduation_project_i | _ii
    semester_code: str
    supervisor_name: Optional[str] = None
    supervisor_email: Optional[str] = None
    title: Optional[str] = None
    company_or_lab: Optional[str] = None


class MilestoneUpdate(BaseModel):
    completed: Optional[bool] = None
    score: Optional[float] = None
    notes: Optional[str] = None


class FinalSubmission(BaseModel):
    grade_letter: str
    grade_points: float
    report_url: Optional[str] = None
