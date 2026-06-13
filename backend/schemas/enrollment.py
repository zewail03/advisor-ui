from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class EnrollRequest(BaseModel):
    section_id: str


class BulkEnrollRequest(BaseModel):
    section_ids: List[str] = Field(..., min_length=1)


class EnrollResult(BaseModel):
    success: bool
    waitlisted: bool = False
    message: str
    section_id: int | str
    course_code: Optional[str] = None
    enrollment_id: Optional[int | str] = None
    waitlist_position: Optional[int] = None
    requires_approval: bool = False
    approval_type: Optional[str] = None


class ScheduleGenerateRequest(BaseModel):
    semester_code: str
    preferred_times: List[str] = []  # morning | afternoon | evening
    off_days: List[str] = []
    max_credits: Optional[int] = None
    priority: str = "balanced"  # graduation | gpa | balanced


class ScheduleOption(BaseModel):
    option_id: str
    label: str
    total_credits: int
    load_score: str
    sections: List[Dict[str, Any]]


class WaitlistJoinRequest(BaseModel):
    section_id: str


class GpaSimulateScenario(BaseModel):
    course_code: str
    predicted_grade: str


class GpaSimulateRequest(BaseModel):
    scenarios: List[GpaSimulateScenario]


class GpaRequiredRequest(BaseModel):
    target_cgpa: float
    course_codes: List[str]
