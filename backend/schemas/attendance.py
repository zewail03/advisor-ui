from datetime import date
from typing import Optional

from pydantic import BaseModel


class AttendanceRecordIn(BaseModel):
    enrollment_id: str
    session_date: date
    status: str  # present | absent | excused | late
    contact_type: str = "lecture"
    duration_hours: float = 1.0
    recorded_by: Optional[str] = None
    note: Optional[str] = None


class AttendanceResult(BaseModel):
    success: bool
    absence_pct: float = 0.0
    warning_tier: float = 0.0
    warning_fired: bool = False
    fw_assigned: bool = False
    message: Optional[str] = None
