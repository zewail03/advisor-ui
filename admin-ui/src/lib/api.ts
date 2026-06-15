// Admin API client — talks to the shared FastAPI backend's /admin/* routes.
"use client";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
export const TOKEN_KEY = "aiu_admin_token";
export const ROLE_KEY = "aiu_admin_role";
export const NAME_KEY = "aiu_admin_name";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setSession(token: string, role: string, name: string) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(ROLE_KEY, role);
  localStorage.setItem(NAME_KEY, name);
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(ROLE_KEY);
  localStorage.removeItem(NAME_KEY);
}

export function getRole(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ROLE_KEY);
}

export function getName(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(NAME_KEY);
}

export async function adminLogin(username: string, password: string) {
  const res = await fetch(`${API_URL}/admin/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || "Invalid username or password");
  }
  return res.json() as Promise<{
    access_token: string;
    role: string;
    full_name: string;
  }>;
}

async function authed<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  if (!token) throw new Error("Not authenticated");
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      ...(init?.headers || {}),
      Authorization: `Bearer ${token}`,
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
    },
  });
  if (res.status === 401) {
    clearSession();
    throw new Error("Session expired — please sign in again");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || `Request failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}

const authedGet = <T>(path: string) => authed<T>(path);

export type Overview = {
  students: { total: number; active: number; at_risk: number };
  sections: { open: number };
  financial: { total_outstanding: number; currency: string };
  queues: { pending_petitions: number; pending_advisor_approvals: number };
  viewer: { name: string; role: string };
};

export type AtRiskStudent = {
  student_id: number;
  student_code: string;
  full_name: string;
  cgpa: number | null;
  status: string;
};

export const getOverview = () => authedGet<Overview>("/admin/overview");
export const getAtRisk = () =>
  authedGet<{ count: number; students: AtRiskStudent[] }>("/admin/students/at-risk?limit=25");

// -------------------- ML early-warning risk model -------------------- //
export type RiskModelInfo = {
  model: string;
  trained_at: string;
  feature_names: string[];
  train_min_main_semesters: number;
  metrics: {
    n_train: number;
    n_at_risk: number;
    base_rate: number;
    holdout_auc: number;
    holdout_accuracy: number;
    holdout_precision: number;
    holdout_recall: number;
    cv_auc_mean: number;
    cv_auc_std: number;
    confusion_matrix: number[][];
  };
};

export type RiskPrediction = {
  student_id: number;
  student_code: string;
  full_name: string;
  cgpa: number | null;
  status: string;
  level: number;
  risk_score: number;
  risk_band: "low" | "moderate" | "high";
  horizon: "forecast" | "assessment";
  top_factor: string;
};

export type RiskPredictionsResponse = {
  available: boolean;
  model: RiskModelInfo | null;
  scored: number;
  band_counts: { high?: number; moderate?: number; low?: number };
  students: RiskPrediction[];
};

export const getRiskPredictions = (limit = 25) =>
  authedGet<RiskPredictionsResponse>(`/admin/students/risk-predictions?limit=${limit}`);

// -------------------------- students CRUD -------------------------- //
export type StudentRow = {
  student_id: number;
  student_code: string;
  full_name: string;
  email: string;
  phone: string | null;
  status: string;
  level: number;
  cgpa: number | null;
  program_id: number | null;
  major_id: number | null;
  program_name?: string | null;
  major_name?: string | null;
};

export const listStudents = (params: { q?: string; status?: string; limit?: number; offset?: number }) => {
  const p = new URLSearchParams();
  if (params.q) p.set("q", params.q);
  if (params.status) p.set("status", params.status);
  p.set("limit", String(params.limit ?? 25));
  p.set("offset", String(params.offset ?? 0));
  return authedGet<{ total: number; limit: number; offset: number; students: StudentRow[] }>(
    `/admin/students?${p.toString()}`,
  );
};

export const getStudent = (id: number) => authedGet<StudentRow>(`/admin/students/${id}`);

export const updateStudent = (id: number, patch: Partial<StudentRow>) =>
  authed<{ updated: boolean; changed?: string[]; student: StudentRow }>(`/admin/students/${id}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });

export const resetStudentPassword = (id: number, new_password?: string) =>
  authed<{ success: boolean; student_code: string; temporary_password: string }>(
    `/admin/students/${id}/reset-password`,
    { method: "POST", body: JSON.stringify({ new_password: new_password || null }) },
  );

// -------------------------- audit trail -------------------------- //
export type AuditEvent = {
  id: string;
  occurred_at: string;
  action: string;
  entity_type: string;
  entity_id: string | null;
  actor_id: string | null;
  actor_role: string | null;
  subject_student_id: string | null;
  before: string | null;
  after: string | null;
};

export const getAudit = (params: { action?: string; limit?: number } = {}) => {
  const p = new URLSearchParams();
  if (params.action) p.set("action", params.action);
  p.set("limit", String(params.limit ?? 100));
  return authedGet<{ events: AuditEvent[] }>(`/audit/admin?${p.toString()}`);
};

// -------------------------- business rules -------------------------- //
export type Policy = {
  key: string;
  value: number;
  default: number;
  is_overridden: boolean;
  type: string;
  category: string;
  label: string;
  unit: string;
  description: string;
  enforced?: boolean;
  updated_at: string | null;
  updated_by: string | null;
};

export const getPolicies = () =>
  authedGet<{ can_edit: boolean; categories: { name: string; policies: Policy[] }[] }>(
    "/admin/policies",
  );

export const updatePolicy = (key: string, value: number) =>
  authed<{ updated: boolean; key: string; old: number; new: number }>(`/admin/policies/${key}`, {
    method: "PATCH",
    body: JSON.stringify({ value }),
  });

// -------------------------- grades -------------------------- //
export type GradeRow = {
  grade_id: number;
  course_code: string;
  course_title: string;
  credits: number;
  semester: string;
  grade_letter: string | null;
  grade_points: number | null;
  percentage: number | null;
  counts_in_gpa: boolean;
};

export const GRADE_LETTERS = ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "F", "FW", "W", "I", "S", "U"];

export const getStudentGrades = (id: number) =>
  authedGet<{
    student: { student_id: number; student_code: string; full_name: string; cgpa: number | null };
    grades: GradeRow[];
  }>(`/admin/students/${id}/grades`);

export const updateGrade = (gradeId: number, grade_letter: string) =>
  authed<{
    updated: boolean;
    grade_id: number;
    old_letter: string;
    new_letter: string;
    old_cgpa: number;
    new_cgpa: number;
  }>(`/admin/grades/${gradeId}`, { method: "PATCH", body: JSON.stringify({ grade_letter }) });

// -------------------------- approval queues -------------------------- //
export type Petition = {
  id: string;
  student_id: number;
  student_name: string;
  student_code: string;
  type: string;
  status: string;
  subject: string;
  body: string | null;
  semester_code: string | null;
  current_grade: string | null;
  requested_grade: string | null;
  created_at: string | null;
};

export type AdvisorApprovalItem = {
  id: string;
  student_id: number;
  student_name: string;
  student_code: string;
  type: string;
  status: string;
  semester_code: string | null;
  justification: string | null;
  created_at: string | null;
};

export const getPetitions = (status = "submitted") =>
  authedGet<{ petitions: Petition[] }>(`/admin/petitions?status=${status}`);

export const decidePetition = (id: string, approve: boolean, comment?: string) =>
  authed<{ decided: boolean; status: string }>(`/admin/petitions/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ approve, comment: comment || null }),
  });

export const getAdvisorApprovals = (status = "pending") =>
  authedGet<{ approvals: AdvisorApprovalItem[] }>(`/admin/advisor-approvals?status=${status}`);

export const decideAdvisorApproval = (id: string, approve: boolean, comment?: string) =>
  authed<{ decided: boolean; status: string }>(`/admin/advisor-approvals/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ approve, comment: comment || null }),
  });

// -------------------------- catalog (courses/sections) -------------------------- //
export type CourseRow = {
  course_id: number;
  code: string;
  name: string;
  credits: number;
  major_code: string | null;
  sections: number;
};

export type SectionRow = {
  section_id: number;
  section_number: string;
  semester: string;
  instructor_name: string | null;
  capacity: number;
  status: string;
  enrolled: number;
};

export type CourseDetail = {
  course_id: number;
  code: string;
  name: string;
  credits: number;
  description: string | null;
  major_code: string | null;
  lecture_hours: number;
  lab_hours: number;
  sections: SectionRow[];
};

export const listCourses = (params: { q?: string; limit?: number; offset?: number }) => {
  const p = new URLSearchParams();
  if (params.q) p.set("q", params.q);
  p.set("limit", String(params.limit ?? 25));
  p.set("offset", String(params.offset ?? 0));
  return authedGet<{ total: number; courses: CourseRow[] }>(`/admin/courses?${p.toString()}`);
};

export const getCourse = (id: number) => authedGet<CourseDetail>(`/admin/courses/${id}`);

export const updateCourse = (id: number, patch: Partial<CourseDetail>) =>
  authed<{ updated: boolean; changed?: string[] }>(`/admin/courses/${id}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });

export const updateSection = (sectionId: number, patch: Partial<SectionRow>) =>
  authed<{ updated: boolean; changed?: string[] }>(`/admin/sections/${sectionId}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });

export const createSection = (courseId: number, body: {
  semester_id: number;
  section_number: string;
  instructor_name?: string;
  capacity?: number;
  status?: string;
}) =>
  authed<{ created: boolean; section_id: number }>(`/admin/courses/${courseId}/sections`, {
    method: "POST",
    body: JSON.stringify(body),
  });

export const getSemesters = () =>
  authedGet<{ semesters: { semester_id: number; code: string }[] }>("/admin/semesters");

// -------------------------- financial -------------------------- //
export type FinancialAccount = {
  semester: string;
  currency: string;
  tuition_fee: number;
  transportation_fee: number;
  fines: number;
  total_charges: number;
  scholarship_credit: number;
  payments_made: number;
  current_balance: number;
  payment_status: string;
  payment_due_date: string | null;
};
export type FinTxn = {
  id: string;
  date: string;
  type: string;
  category: string;
  description: string;
  amount: number;
  status: string;
  reference: string;
};
export type ScholarshipRow = {
  id: string;
  type: string;
  percentage: number;
  amount: number;
  status: string;
  notes: string;
};

export const getFinancial = (id: number) =>
  authedGet<{
    student: { student_id: number; student_code: string; full_name: string };
    account: FinancialAccount | null;
    transactions: FinTxn[];
    scholarships: ScholarshipRow[];
  }>(`/admin/students/${id}/financial`);

export const postPayment = (id: number, amount: number, method: string) =>
  authed<{ posted: boolean; new_balance: number; status: string }>(
    `/admin/students/${id}/financial/payment`,
    { method: "POST", body: JSON.stringify({ amount, method }) },
  );

export const addFine = (id: number, amount: number, description: string) =>
  authed<{ posted: boolean; new_balance: number }>(`/admin/students/${id}/financial/fine`, {
    method: "POST",
    body: JSON.stringify({ amount, description }),
  });

export const grantScholarship = (id: number, scholarship_type: string, amount: number, notes?: string) =>
  authed<{ granted: boolean; new_balance: number }>(`/admin/students/${id}/financial/scholarship`, {
    method: "POST",
    body: JSON.stringify({ scholarship_type, amount, notes: notes || null }),
  });

export const rebillFromPolicy = (id: number) =>
  authed<{
    rebilled: boolean;
    term_credits: number;
    tuition_per_credit: number;
    tuition_fee: number;
    transportation_fee: number;
    new_balance: number;
    status: string;
  }>(`/admin/students/${id}/financial/rebill`, { method: "POST" });

export const revokeScholarship = (scholarshipId: string) =>
  authed<{ revoked: boolean; new_balance: number | null }>(`/admin/scholarships/${scholarshipId}`, {
    method: "DELETE",
  });

// -------------------------- notifications / announcements -------------------------- //
export const sendNotification = (body: {
  subject: string;
  message: string;
  type: string;
  target: "all" | "student";
  student_code?: string;
}) =>
  authed<{ sent: number; recipients: string }>("/admin/notifications/send", {
    method: "POST",
    body: JSON.stringify(body),
  });

export type Announcement = { subject: string; type: string; recipients: number; sent_at: string | null };

export const getRecentBroadcasts = () =>
  authedGet<{ announcements: Announcement[] }>("/admin/notifications/recent");

// -------------------------- offerings / schedule builder -------------------------- //
export type Meeting = {
  meeting_type: string;
  day_of_week: string;
  start_time: string;
  end_time: string;
  location?: string | null;
};
export type Offering = {
  section_id: number;
  course_code: string;
  course_title: string;
  section_number: string;
  instructor_name: string | null;
  capacity: number;
  status: string;
  enrolled: number;
  meetings: Meeting[];
};

export const getCourseOptions = () =>
  authedGet<{ courses: { course_id: number; code: string; name: string }[] }>("/admin/course-options");

export type Room = { room_id: number; name: string; room_type: string; capacity: number | null };

export const getRooms = () => authedGet<{ rooms: Room[] }>("/admin/rooms");

export const createRoom = (body: { name: string; room_type: string; capacity?: number }) =>
  authed<{ created: boolean; room_id: number; name: string }>("/admin/rooms", {
    method: "POST",
    body: JSON.stringify(body),
  });

export const getOfferings = (semesterId: number) =>
  authedGet<{ semester: { semester_id: number; code: string }; offerings: Offering[] }>(
    `/admin/offerings?semester_id=${semesterId}`,
  );

export const createSemester = (body: { code: string; type?: string; year_start?: number; year_end?: number }) =>
  authed<{ created: boolean; semester_id: number; code: string }>("/admin/semesters", {
    method: "POST",
    body: JSON.stringify(body),
  });

export const createOffering = (body: {
  semester_id: number;
  course_id: number;
  section_number: string;
  instructor_name?: string;
  capacity: number;
  status: string;
  meetings: Meeting[];
}) =>
  authed<{ created: boolean; section_id: number }>("/admin/offerings", {
    method: "POST",
    body: JSON.stringify(body),
  });

export const deleteOffering = (sectionId: number) =>
  authed<{ deleted: boolean }>(`/admin/offerings/${sectionId}`, { method: "DELETE" });

// -------------------------- AI assistant -------------------------- //
export type AssistantAnswer = {
  answer: string;
  tool: string;
  source: string;
  columns: string[];
  rows: (string | number | null)[][];
  metric: number | null;
};

export type Anomaly = {
  key: string;
  title: string;
  severity: "high" | "medium" | "low" | "ok";
  count: number;
  detail: string;
  sample: string[];
};

export type AnomalyReport = {
  generated_for: string;
  total_checks: number;
  flagged: number;
  checks: Anomaly[];
};

export const getAssistantSuggestions = () =>
  authedGet<{ suggestions: string[] }>("/admin/assistant/suggestions");

export const askAssistant = (question: string) =>
  authed<AssistantAnswer>("/admin/assistant/query", {
    method: "POST",
    body: JSON.stringify({ question }),
  });

export const getAnomalies = () => authedGet<AnomalyReport>("/admin/assistant/anomalies");

// -------------------------- staff management (super-admin only) -------------------------- //
export type StaffMember = {
  id: number;
  username: string;
  full_name: string;
  email: string;
  role: string;
  is_active: boolean;
  created_at: string | null;
  last_login_at: string | null;
};

export const listStaff = () =>
  authedGet<{ staff: StaffMember[]; roles: string[]; me: number }>("/admin/staff");

export const createStaff = (body: {
  username: string;
  full_name: string;
  email: string;
  role: string;
  password?: string;
}) =>
  authed<{ created: boolean; staff: StaffMember; temporary_password: string | null }>("/admin/staff", {
    method: "POST",
    body: JSON.stringify(body),
  });

export const updateStaff = (
  id: number,
  patch: { full_name?: string; email?: string; role?: string; is_active?: boolean },
) =>
  authed<{ updated: boolean; changed: string[]; staff: StaffMember }>(`/admin/staff/${id}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });

export const resetStaffPassword = (id: number, new_password?: string) =>
  authed<{ reset: boolean; username: string; temporary_password: string }>(
    `/admin/staff/${id}/reset-password`,
    { method: "POST", body: JSON.stringify({ new_password: new_password || null }) },
  );
