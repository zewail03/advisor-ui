// src/lib/api.ts — talks to the new async FastAPI backend.

import { REFRESH_LS_KEY, TOKEN_LS_KEY } from "@/lib/constants";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export const apiBaseUrl = () => API_URL;

function authHeaders(token: string) {
  return { Authorization: `Bearer ${token}` };
}

async function safeJson(res: Response) {
  try {
    return await res.json();
  } catch {
    return null;
  }
}

function extractDetail(payload: any): string | null {
  if (!payload) return null;
  if (typeof payload.detail === "string") return payload.detail;
  if (Array.isArray(payload.detail) && payload.detail?.[0]?.msg) {
    return String(payload.detail[0].msg);
  }
  if (typeof payload.message === "string") return payload.message;
  return null;
}

async function throwApiError(res: Response, fallback: string) {
  const payload = await safeJson(res);
  throw new Error(extractDetail(payload) || fallback);
}

async function apiFetch(
  url: string,
  init?: RequestInit & { timeoutMs?: number },
): Promise<Response> {
  const timeoutMs = init?.timeoutMs ?? 15000;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  const externalSignal = init?.signal;
  if (externalSignal) {
    if (externalSignal.aborted) controller.abort();
    else externalSignal.addEventListener("abort", () => controller.abort(), { once: true });
  }

  try {
    const { timeoutMs: _t, signal: _s, ...rest } = init ?? {};
    return await fetch(url, { ...rest, signal: controller.signal });
  } catch (e) {
    if (externalSignal?.aborted) throw new DOMException("Aborted", "AbortError");
    if (e instanceof DOMException && e.name === "AbortError")
      throw new Error("Request timed out: cannot reach backend");
    if (e instanceof TypeError) throw new Error("Network error: cannot reach backend");
    if (e instanceof Error) throw new Error(e.message || "Network error");
    throw new Error("Network error");
  } finally {
    clearTimeout(timer);
  }
}

async function authed(
  path: string,
  token: string,
  init?: RequestInit & { timeoutMs?: number },
): Promise<Response> {
  const res = await apiFetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      ...(init?.headers || {}),
      ...authHeaders(token),
    },
  });
  if (res.status === 401 && typeof window !== "undefined") {
    const refreshed = await tryRefresh();
    if (refreshed) {
      return apiFetch(`${API_URL}${path}`, {
        ...init,
        headers: {
          ...(init?.headers || {}),
          ...authHeaders(refreshed),
        },
      });
    }
  }
  return res;
}

async function tryRefresh(): Promise<string | null> {
  if (typeof window === "undefined") return null;
  const refresh = localStorage.getItem(REFRESH_LS_KEY);
  if (!refresh) return null;
  try {
    const res = await apiFetch(`${API_URL}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refresh }),
    });
    if (!res.ok) return null;
    const data = await res.json();
    localStorage.setItem(TOKEN_LS_KEY, data.access_token);
    return data.access_token as string;
  } catch {
    return null;
  }
}

/** ========================= Types ========================= */
export type TokenPair = { access_token: string; refresh_token: string; token_type: string };

export type MeResponse = {
  id: string;
  student_number: string;
  full_name: string;
  email: string;
  program: string | null;
  academic_level: string | null;
  cgpa: number | null;
  standing: string;
};

export type GpaSummary = {
  cgpa: number | null;
  sgpa_current: number | null;
  total_credits: number;
  completed_credits: number;
  semester_history: Array<{ semester: string; sgpa: number; cgpa?: number | null }>;
};

export type StandingInfo = {
  standing: string;
  cgpa: number | null;
  consecutive_probation_semesters: number;
  risk_message: string | null;
};

/** ========================= Auth ========================= */
export async function login(student_number: string, password: string): Promise<TokenPair> {
  const res = await apiFetch(`${API_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ student_code: student_number, password }),
  });
  if (!res.ok) await throwApiError(res, "Login failed");
  return res.json();
}

export async function changePassword(token: string, current_password: string, new_password: string) {
  const res = await authed("/auth/change-password", token, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ current_password, new_password }),
  });
  if (!res.ok) await throwApiError(res, "Failed to change password");
  return res.json();
}

export async function getMe(token: string, signal?: AbortSignal): Promise<MeResponse> {
  const res = await authed("/auth/me", token, { signal });
  if (!res.ok) await throwApiError(res, "Failed to load profile");
  return res.json();
}

/** ========================= Students ========================= */
export async function getMyGpa(token: string, signal?: AbortSignal): Promise<GpaSummary> {
  const res = await authed("/students/me/gpa", token, { signal });
  if (!res.ok) await throwApiError(res, "Failed to load GPA");
  return res.json();
}

export async function getMyStanding(token: string, signal?: AbortSignal): Promise<StandingInfo> {
  const res = await authed("/students/me/standing", token, { signal });
  if (!res.ok) await throwApiError(res, "Failed to load standing");
  return res.json();
}

export async function getMyTranscript(token: string, signal?: AbortSignal) {
  const res = await authed("/students/me/transcript", token, { signal });
  if (!res.ok) await throwApiError(res, "Failed to load transcript");
  return res.json();
}

export async function getMyRequirements(token: string, signal?: AbortSignal) {
  const res = await authed("/students/me/requirements", token, { signal });
  if (!res.ok) await throwApiError(res, "Failed to load requirements");
  return res.json();
}

export type ReqTreeCourse = {
  code: string;
  title: string;
  description: string | null;
  units: number;
  taken: boolean;
  in_progress: boolean;
  grade: string | null;
  term: string | null;
  status: "Taken" | "In Progress" | "Not Started";
};
export type ReqSubrequirement = {
  category: string;
  is_basket: boolean;
  basis: "units" | "courses";
  required: number;
  completed: number;
  in_progress: number;
  completion_percentage: number;
  satisfied: boolean;
  courses: ReqTreeCourse[];
};
export type ReqSemester = {
  name: string;
  slot: number;
  required: number;
  completed: number;
  in_progress: number;
  completion_percentage: number;
  satisfied: boolean;
  subrequirements: ReqSubrequirement[];
};
export type RequirementTree = {
  program: { name: string; code: string | null; total_credits: number } | null;
  overall: {
    required: number;
    completed: number;
    in_progress: number;
    completion_percentage: number;
    satisfied: boolean;
  } | null;
  semesters: ReqSemester[];
};

export async function getMyRequirementsTree(
  token: string,
  signal?: AbortSignal,
): Promise<RequirementTree> {
  const res = await authed("/students/me/requirements-tree", token, { signal });
  if (!res.ok) await throwApiError(res, "Failed to load requirements");
  return res.json();
}

export async function getMyStudyPlan(token: string, signal?: AbortSignal) {
  const res = await authed("/students/me/study-plan", token, { signal });
  if (!res.ok) await throwApiError(res, "Failed to load study plan");
  return res.json();
}

export async function getGraduationCheck(token: string, signal?: AbortSignal) {
  const res = await authed("/students/me/graduation-check", token, { signal });
  if (!res.ok) await throwApiError(res, "Failed to load graduation check");
  return res.json();
}

export async function getGraduationCountdown(token: string, signal?: AbortSignal) {
  const res = await authed("/students/me/graduation-countdown", token, { signal });
  if (!res.ok) await throwApiError(res, "Failed to load graduation countdown");
  return res.json();
}

export type RecoveryPlan = {
  severity: "critical" | "warning" | "none";
  current_cgpa: number;
  target_cgpa: number;
  consecutive_probation: number;
  at_risk_courses: Array<{
    enrollment_id: string;
    course_id: string;
    course_code: string;
    course_title: string;
    credits: number;
    midterm_score: number | null;
    flagged: boolean;
  }>;
  drop_candidates: Array<{
    enrollment_id: string;
    course_id: string;
    course_code: string;
    course_title: string;
    credits: number;
    midterm_score: number | null;
    flagged: boolean;
  }>;
  retake_candidates: Array<{
    course_code: string;
    course_title: string;
    credits: number;
    prior_grade: string;
    prior_grade_points: number | null;
    prior_semester: string;
    improvement_ceiling: number;
  }>;
  grades_needed: {
    target_cgpa: number;
    avg_grade_points_needed?: number;
    minimum_letter_per_course?: string;
    feasible: boolean;
    reason?: string;
    current_cgpa?: number;
    per_course?: Array<{ course_id: string; course_code: string; minimum_grade: string }>;
  };
  recommended_actions: string[];
};

export async function getRecoveryPlan(token: string, signal?: AbortSignal): Promise<RecoveryPlan> {
  const res = await authed("/students/me/recovery-plan", token, { signal });
  if (!res.ok) await throwApiError(res, "Failed to load recovery plan");
  return res.json();
}

export type CourseRecommendation = {
  course_id: string;
  code: string;
  title: string;
  credits: number;
  unlocks: number;
  offered_this_semester: boolean;
  prereqs_met: boolean;
  prereq_blocker: string | null;
  difficulty: "Easy" | "Moderate" | "Hard" | "Unknown";
  historical_pass_rate: number | null;
  historical_sample_size: number;
  score: number;
  reason: string;
};

export type CourseRecommendationsResponse = {
  semester: string;
  current_cgpa: number;
  cgpa_band?: "recovery" | "standard" | "advanced";
  recommendations: CourseRecommendation[];
  reason?: string;
};

export async function getCourseRecommendations(
  token: string,
  opts: { semester?: string; top_n?: number } = {},
  signal?: AbortSignal,
): Promise<CourseRecommendationsResponse> {
  const p = new URLSearchParams();
  if (opts.semester) p.set("semester", opts.semester);
  if (opts.top_n) p.set("top_n", String(opts.top_n));
  const qs = p.toString();
  const res = await authed(
    `/students/me/course-recommendations${qs ? `?${qs}` : ""}`,
    token,
    { signal },
  );
  if (!res.ok) await throwApiError(res, "Failed to load recommendations");
  return res.json();
}

/** ========================= Courses ========================= */
export async function searchCourses(
  token: string,
  opts: { q?: string; department?: string } = {},
) {
  const p = new URLSearchParams();
  if (opts.q) p.set("q", opts.q);
  if (opts.department) p.set("department", opts.department);
  const res = await authed(`/courses?${p.toString()}`, token);
  if (!res.ok) await throwApiError(res, "Failed to search courses");
  return res.json();
}

export async function getCourseDetail(token: string, courseId: string) {
  const res = await authed(`/courses/${courseId}`, token);
  if (!res.ok) await throwApiError(res, "Failed to load course");
  return res.json();
}

export async function searchSections(
  token: string,
  opts: { semester: string; q?: string },
) {
  const p = new URLSearchParams({ semester: opts.semester });
  if (opts.q) p.set("q", opts.q);
  const res = await authed(`/courses/sections/search?${p.toString()}`, token);
  if (!res.ok) await throwApiError(res, "Failed to search sections");
  return res.json();
}

/** ========================= Enrollments ========================= */
export async function getMySchedule(token: string, semester?: string) {
  const p = semester ? `?semester=${encodeURIComponent(semester)}` : "";
  const res = await authed(`/enrollments/me/schedule${p}`, token);
  if (!res.ok) await throwApiError(res, "Failed to load schedule");
  return res.json();
}

export async function enrollSection(token: string, section_id: string) {
  const res = await authed("/enrollments", token, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ section_id }),
  });
  if (!res.ok) await throwApiError(res, "Failed to enroll");
  return res.json();
}

export async function bulkEnroll(token: string, section_ids: string[]) {
  const res = await authed("/enrollments/bulk", token, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ section_ids }),
  });
  if (!res.ok) await throwApiError(res, "Bulk enrollment failed");
  return res.json();
}

export async function dryRunEnroll(token: string, section_ids: string[]) {
  const res = await authed("/enrollments/dry-run", token, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ section_ids }),
  });
  if (!res.ok) await throwApiError(res, "Dry run failed");
  return res.json();
}

export async function dropEnrollment(token: string, enrollment_id: string) {
  const res = await authed(`/enrollments/${enrollment_id}`, token, { method: "DELETE" });
  if (!res.ok) await throwApiError(res, "Failed to drop");
  return res.json();
}

export async function joinWaitlist(token: string, section_id: string) {
  const res = await authed("/enrollments/waitlist", token, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ section_id }),
  });
  if (!res.ok) await throwApiError(res, "Failed to join waitlist");
  return res.json();
}

/** ========================= Schedule ========================= */
export async function generateSchedule(token: string, semester_code: string, max_credits?: number) {
  const res = await authed("/schedule/generate", token, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ semester_code, max_credits }),
  });
  if (!res.ok) await throwApiError(res, "Failed to generate schedules");
  return res.json();
}

/** ========================= GPA ========================= */
export async function simulateGpa(
  token: string,
  scenarios: Array<{ course_code: string; predicted_grade: string }>,
) {
  const res = await authed("/gpa/simulate", token, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scenarios }),
  });
  if (!res.ok) await throwApiError(res, "Failed to simulate GPA");
  return res.json();
}

export async function requiredGrades(token: string, target_cgpa: number, course_codes: string[]) {
  const res = await authed("/gpa/required", token, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ target_cgpa, course_codes }),
  });
  if (!res.ok) await throwApiError(res, "Failed to compute required grades");
  return res.json();
}

/** ========================= Financial ========================= */
export async function getBalance(token: string, semester?: string) {
  const p = semester ? `?semester=${encodeURIComponent(semester)}` : "";
  const res = await authed(`/financial/balance${p}`, token);
  if (!res.ok) await throwApiError(res, "Failed to load balance");
  return res.json();
}

export async function getInvoices(token: string, semester?: string) {
  const p = semester ? `?semester=${encodeURIComponent(semester)}` : "";
  const res = await authed(`/financial/invoices${p}`, token);
  if (!res.ok) await throwApiError(res, "Failed to load invoices");
  return res.json();
}

export async function getPaymentHistory(token: string) {
  const res = await authed("/financial/payment-history", token);
  if (!res.ok) await throwApiError(res, "Failed to load payment history");
  return res.json();
}

export async function getScholarships(token: string) {
  const res = await authed("/financial/scholarships", token);
  if (!res.ok) await throwApiError(res, "Failed to load scholarships");
  return res.json();
}

/* ── Online payment (Stripe test mode) ── */
export async function getPaymentConfig(token: string, signal?: AbortSignal): Promise<{ enabled: boolean; mode: string }> {
  const res = await authed("/financial/payment-config", token, { signal });
  if (!res.ok) return { enabled: false, mode: "test" };
  return res.json();
}

export async function startCheckout(
  token: string,
): Promise<{ url: string; session_id: string; amount: number; currency: string }> {
  const res = await authed("/financial/checkout", token, { method: "POST" });
  if (!res.ok) await throwApiError(res, "Could not start checkout");
  return res.json();
}

export async function confirmCheckout(
  token: string,
  session_id: string,
): Promise<{ paid: boolean; new_balance?: number; amount?: number; status?: string; already_recorded?: boolean }> {
  const res = await authed("/financial/checkout/confirm", token, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id }),
  });
  if (!res.ok) await throwApiError(res, "Could not confirm payment");
  return res.json();
}

/** ========================= Notifications ========================= */
export async function getNotifications(token: string) {
  const res = await authed("/notifications", token);
  if (!res.ok) await throwApiError(res, "Failed to load notifications");
  return res.json();
}

export async function markNotificationRead(token: string, id: string) {
  const res = await authed(`/notifications/${id}/read`, token, { method: "PATCH" });
  if (!res.ok) await throwApiError(res, "Failed to mark read");
  return res.json();
}

export async function markAllNotificationsRead(token: string) {
  const res = await authed("/notifications/mark-all-read", token, { method: "POST" });
  if (!res.ok) await throwApiError(res, "Failed to mark all read");
  return res.json();
}

export type StudentProfile = Record<string, any>;

export type AcademicRecordCourse = {
  code: string;
  title: string;
  credits: number | null;
  grade: string | null;
  points?: number | null;
  status?: string | null;
};

export type AcademicRecordsResponse = {
  summary: {
    cgpa: number | null;
    completed_hours: number | null;
    remaining_hours: number | null;
    total_hours: number | null;
    class_rank: string | number | null;
    status: string | null;
  };
  gpa_trend: Array<{ term: string; gpa: number }>;
  terms: Record<string, { term_gpa: number | null; courses: AcademicRecordCourse[] }>;
};

export async function getProfile(token: string, signal?: AbortSignal): Promise<StudentProfile> {
  const res = await authed("/students/me", token, { signal });
  if (!res.ok) await throwApiError(res, "Failed to load profile");
  return res.json();
}

export async function updateProfile(token: string, patch: Partial<StudentProfile>) {
  const res = await authed("/students/me", token, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!res.ok) await throwApiError(res, "Failed to update profile");
  return res.json();
}

// ===== §4 Advisor =====
export async function getMyAdvisor(token: string) {
  const res = await authed("/advisor/me", token);
  if (!res.ok) await throwApiError(res, "Failed to load advisor");
  return res.json();
}

export async function getMyApprovals(token: string) {
  const res = await authed("/advisor/me/approvals", token);
  if (!res.ok) await throwApiError(res, "Failed to load approvals");
  return res.json() as Promise<any[]>;
}

export async function requestApproval(
  token: string,
  payload: {
    type: string;
    related_id?: string;
    semester_code?: string;
    justification?: string;
    payload_json?: string;
  },
) {
  const res = await authed("/advisor/me/approvals", token, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) await throwApiError(res, "Failed to submit approval request");
  return res.json();
}

// ===== §14/§15/§16/§27 Petitions =====
export async function getPetitionEligibility(token: string) {
  const res = await authed("/petitions/me/eligibility", token);
  if (!res.ok) await throwApiError(res, "Failed to check eligibility");
  return res.json() as Promise<Record<string, { eligible: boolean; message: string }>>;
}

export async function getMyPetitions(token: string) {
  const res = await authed("/petitions/me", token);
  if (!res.ok) await throwApiError(res, "Failed to load petitions");
  return res.json() as Promise<any[]>;
}

export async function submitPetition(token: string, payload: Record<string, any>) {
  const res = await authed("/petitions/me", token, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) await throwApiError(res, "Failed to submit petition");
  return res.json();
}

// ===== §19/§20 Capstone =====
export async function getCapstoneEligibility(token: string) {
  const res = await authed("/capstone/me/eligibility", token);
  if (!res.ok) await throwApiError(res, "Failed to check capstone eligibility");
  return res.json() as Promise<
    Record<
      string,
      { eligible: boolean; message: string; completion_pct: number; threshold_pct: number }
    >
  >;
}

export async function getMyCapstone(token: string) {
  const res = await authed("/capstone/me", token);
  if (!res.ok) await throwApiError(res, "Failed to load capstone entries");
  return res.json() as Promise<{ entries: any[] }>;
}

export async function enrollCapstone(token: string, payload: Record<string, any>) {
  const res = await authed("/capstone/me", token, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) await throwApiError(res, "Failed to enroll in capstone");
  return res.json();
}

export async function patchMilestone(
  token: string,
  milestoneId: string,
  update: { completed?: boolean; score?: number; notes?: string },
) {
  const res = await authed(`/capstone/milestones/${milestoneId}`, token, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(update),
  });
  if (!res.ok) await throwApiError(res, "Failed to update milestone");
  return res.json();
}

// ===== §7 Attendance =====
export async function getMyAttendance(token: string, semester?: string) {
  const q = semester ? `?semester=${encodeURIComponent(semester)}` : "";
  const res = await authed(`/attendance/me${q}`, token);
  if (!res.ok) await throwApiError(res, "Failed to load attendance");
  return res.json() as Promise<{ records: any[] }>;
}

// ===== §10 Retakes =====
export async function getRetakeEligibility(token: string, sectionId: string) {
  const res = await authed(`/retakes/eligibility/${sectionId}`, token);
  if (!res.ok) await throwApiError(res, "Failed to check retake eligibility");
  return res.json();
}

export async function getMyRetakes(token: string) {
  const res = await authed("/retakes/me", token);
  if (!res.ok) await throwApiError(res, "Failed to load retakes");
  return res.json() as Promise<{ records: any[] }>;
}

// ===== §31 Course Evaluations =====
export async function getPendingEvaluations(token: string) {
  const res = await authed("/evaluations/me/pending", token);
  if (!res.ok) await throwApiError(res, "Failed to load pending evaluations");
  return res.json() as Promise<{ pending: any[] }>;
}

export async function submitEvaluation(token: string, payload: Record<string, any>) {
  const res = await authed("/evaluations", token, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) await throwApiError(res, "Failed to submit evaluation");
  return res.json();
}

// ===== §30 Audit (current student only) =====
export async function getMyAuditTrail(token: string, action?: string) {
  const q = action ? `?action=${encodeURIComponent(action)}` : "";
  const res = await authed(`/audit/me${q}`, token);
  if (!res.ok) await throwApiError(res, "Failed to load audit trail");
  return res.json() as Promise<{ events: any[] }>;
}

// ===== §6 Withdrawal =====
export async function withdrawEnrollment(token: string, enrollmentId: string) {
  const res = await authed(`/enrollments/${enrollmentId}/withdraw`, token, {
    method: "POST",
  });
  if (!res.ok) await throwApiError(res, "Failed to withdraw");
  return res.json();
}

