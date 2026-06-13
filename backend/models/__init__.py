"""ORM models aligned with the real AIU database schema.

Non-demo models (attendance, capstone, financial, petitions, retake,
evaluation) are present as files but not imported here while the app is
focused on the demo path. Re-add them after their routers are updated.
"""
from core.database import Base

from models.student import Program, Major, Student
from models.academic import (
    Semester,
    RegistrationPeriod,
    AcademicStanding,
    RequirementCategory,
    RequirementGroup,
    RequirementGroupCourse,
)
from models.course import (
    Course,
    Section,
    SectionMeeting,
    Prerequisite,
    CourseEmbedding,
)
from models.enrollment import (
    Enrollment,
    Grade,
    GRADE_POINTS,
    Waitlist,
)
from models.ai_models import (
    ChatSession,
    ChatMessage,
    Notification,
)
from models.advisor import (
    Advisor,
    AdvisorAssignment,
    AdvisorApproval,
    ApprovalType,
    ApprovalStatus,
    MAX_STUDENTS_PER_ADVISOR,
)
from models.audit import AuditLog
from models.financial import FinancialAccount, FinancialTransaction, Scholarship
from models.staff import Staff, StaffRole, WRITE_ROLES
from models.policy import PolicyConfig
from models.petitions import Petition, PetitionType, PetitionStatus
from models.capstone import (
    CapstoneEnrollment,
    CapstoneMilestone,
    CapstoneStage,
    CapstoneStatus,
)
from models.evaluation import CourseEvaluation, CourseEvaluationSummary
from models.retake import RetakeRecord
from models.attendance import (
    AttendanceRecord,
    AttendanceSummary,
    AttendanceStatus,
    ContactType,
)


__all__ = [
    "Base",
    "Program", "Major", "Student",
    "Semester", "RegistrationPeriod", "AcademicStanding",
    "RequirementCategory", "RequirementGroup", "RequirementGroupCourse",
    "Course", "Section", "SectionMeeting", "Prerequisite", "CourseEmbedding",
    "Enrollment", "Grade", "GRADE_POINTS", "Waitlist",
    "ChatSession", "ChatMessage", "Notification",
    "Advisor", "AdvisorAssignment", "AdvisorApproval",
    "ApprovalType", "ApprovalStatus", "MAX_STUDENTS_PER_ADVISOR",
    "AuditLog",
    "FinancialAccount", "FinancialTransaction", "Scholarship",
    "Petition", "PetitionType", "PetitionStatus",
    "CapstoneEnrollment", "CapstoneMilestone", "CapstoneStage", "CapstoneStatus",
    "CourseEvaluation", "CourseEvaluationSummary",
    "RetakeRecord",
    "AttendanceRecord", "AttendanceSummary", "AttendanceStatus", "ContactType",
    "Staff", "StaffRole", "WRITE_ROLES",
    "PolicyConfig",
]
