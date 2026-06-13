from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class StudentSummary(BaseModel):
    id: str
    student_number: str
    full_name: str
    email: str
    program: Optional[str] = None
    academic_level: int


class GpaResponse(BaseModel):
    cgpa: float
    sgpa_current: float
    semester_history: List[Dict[str, Any]]


class StandingResponse(BaseModel):
    standing: str
    cgpa: float
    consecutive_probation_semesters: int
    risk_message: Optional[str] = None


class RequirementOut(BaseModel):
    requirement_id: str
    category: str
    total_units_required: float
    units_completed: float
    units_in_progress: float
    completion_percentage: float
    satisfied: bool
    is_core: bool
    courses: List[Dict[str, Any]]


class ProfileUpdate(BaseModel):
    phone: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    nationality: Optional[str] = None
    school_id: Optional[str] = None
    home_address: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_relationship: Optional[str] = None
    emergency_phone: Optional[str] = None
    emergency_email: Optional[str] = None
    notif_email: Optional[int] = None
    notif_sms: Optional[int] = None
    notif_advisor: Optional[int] = None
    public_profile: Optional[int] = None
