"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import AppLayout from "@/components/layout/AppLayout";
import { useLanguage } from "@/hooks/useLanguage";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/useAuth";
import { useTheme } from "@/hooks/useTheme";
import { getMyGpa, getMyTranscript, getMyRequirements } from "@/lib/api";

/* ── Grade scale (matches backend GRADE_POINTS) ────────── */
const GRADE_POINTS: Record<string, number | null> = {
  "A+": 4.0, A: 4.0, "A-": 3.7,
  "B+": 3.3, B: 3.0, "B-": 2.7,
  "C+": 2.3, C: 2.0, "C-": 1.7,
  "D+": 1.3, D: 1.0,
  F: 0.0,
  Dropped: null, // doesn't count in GPA; user can change to simulate
};
const GRADE_OPTIONS = Object.keys(GRADE_POINTS);
// Sentinel for in-progress courses with no grade yet — excluded from GPA math
// until the student picks a simulated grade.
const NOT_GRADED = "—";

function normalizeGrade(rawGrade: string, rawStatus: string): string {
  const g = (rawGrade || "").trim();
  // Real letter grade wins, regardless of enrollment status
  if (g in GRADE_POINTS && g !== "Dropped") return g;
  const s = (rawStatus || "").trim().toLowerCase();
  if (s === "dropped" || g.toLowerCase() === "dropped" || g === "W" || g === "WD") {
    return "Dropped";
  }
  return "";
}

/* ── Types ─────────────────────────────────────────────── */
type CourseRow = {
  code: string;
  title: string;
  credits: number;
  grade: string;
  originalGrade: string; // the real grade from transcript (empty if none yet)
  isUserAdded: boolean; // true = course added in new semester; user picks the code
};

type SemesterBlock = {
  id: string;
  name: string;
  courses: CourseRow[];
  isNew: boolean; // true = user-added hypothetical semester
};

/* ── Helpers ───────────────────────────────────────────── */
function semesterGpa(courses: CourseRow[]): number | null {
  let totalPts = 0;
  let totalCr = 0;
  for (const c of courses) {
    const pts = GRADE_POINTS[c.grade];
    if (pts == null) continue;
    totalPts += pts * c.credits;
    totalCr += c.credits;
  }
  return totalCr > 0 ? totalPts / totalCr : null;
}

function cumulativeGpa(semesters: SemesterBlock[]): { gpa: number | null; totalPts: number; totalCr: number } {
  let totalPts = 0;
  let totalCr = 0;
  for (const sem of semesters) {
    for (const c of sem.courses) {
      const pts = GRADE_POINTS[c.grade];
      if (pts == null) continue;
      totalPts += pts * c.credits;
      totalCr += c.credits;
    }
  }
  return { gpa: totalCr > 0 ? totalPts / totalCr : null, totalPts, totalCr };
}

function parseTermKey(term: string) {
  const m = term.match(/(winter|spring|summer|fall)\s*(\d{4})/i);
  if (!m) return { year: 0, season: 0 };
  const order: Record<string, number> = { winter: 0, spring: 1, summer: 2, fall: 3 };
  return { year: Number(m[2]), season: order[m[1].toLowerCase()] ?? 0 };
}

function sortTerms(terms: string[]) {
  return [...terms].sort((a, b) => {
    const A = parseTermKey(a);
    const B = parseTermKey(b);
    return A.year !== B.year ? A.year - B.year : A.season - B.season;
  });
}

/* ── Page ──────────────────────────────────────────────── */
export default function GpaSimulatorPage() {
  const { t } = useLanguage();
  const { token } = useAuth();
  const { isDark } = useTheme();

  const [semesters, setSemesters] = useState<SemesterBlock[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [availableCourses, setAvailableCourses] = useState<Array<{ code: string; title: string; credits: number }>>([]);
  const [originalGpa, setOriginalGpa] = useState<number | null>(null);

  // Load transcript + available courses
  const loadData = useCallback(async (tkn: string) => {
    setLoading(true);
    setErr(null);
    try {
      const [gpa, transcript, requirements] = await Promise.all([
        getMyGpa(tkn),
        getMyTranscript(tkn),
        getMyRequirements(tkn).catch(() => ({ requirements: [] })),
      ]);

      setOriginalGpa(gpa.cgpa);

      // Build semester blocks from transcript
      const termData = transcript.terms || transcript;
      const termEntries: [string, any][] = Array.isArray(termData)
        ? termData.map((t: any) => [t.semester, t])
        : Object.entries(termData);

      const termNames = sortTerms(termEntries.map(([k]) => k));
      const blocks: SemesterBlock[] = termNames.map((termName) => {
        const entry = termEntries.find(([k]) => k === termName);
        const block = entry ? entry[1] : { courses: [] };
        const courses: CourseRow[] = (block.courses || []).map((c: any) => {
          const rawGrade = c.grade || c.grade_letter || "";
          const rawStatus = c.status || "";
          const normalized = normalizeGrade(rawGrade, rawStatus);
          return {
            code: c.course_code || c.code || "",
            title: c.course_name || c.course_title || c.title || "",
            credits: c.credits ?? 3,
            // No grade yet (in progress) -> "—": excluded from GPA until the
            // student picks a simulated grade for it.
            grade: normalized || NOT_GRADED,
            originalGrade: normalized || NOT_GRADED,
            isUserAdded: false,
          };
        });
        return { id: termName, name: termName, courses, isNew: false };
      });
      setSemesters(blocks);

      // Available courses for adding (unsatisfied requirements)
      const avail: Array<{ code: string; title: string; credits: number }> = [];
      for (const cat of requirements.requirements || []) {
        for (const c of cat.courses || []) {
          if (!c.satisfied) avail.push({ code: c.code, title: c.title, credits: c.credits ?? 3 });
        }
      }
      setAvailableCourses(avail);
    } catch (e: any) {
      setErr(e.message || "Failed to load data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (token) loadData(token);
  }, [token, loadData]);

  // Semester mutations
  function addSemester() {
    const id = `new-${Date.now()}`;
    setSemesters((prev) => [
      ...prev,
      { id, name: "New Semester", courses: [], isNew: true },
    ]);
  }

  function removeSemester(semId: string) {
    setSemesters((prev) => prev.filter((s) => s.id !== semId));
  }

  function updateSemesterName(semId: string, name: string) {
    setSemesters((prev) => prev.map((s) => (s.id === semId ? { ...s, name } : s)));
  }

  // Course mutations within a semester
  function addCourse(semId: string) {
    setSemesters((prev) =>
      prev.map((s) => {
        if (s.id !== semId) return s;
        return {
          ...s,
          courses: [...s.courses, { code: "", title: "New Course", credits: 3, grade: "A", originalGrade: "", isUserAdded: true }],
        };
      }),
    );
  }

  function updateCourse(semId: string, courseIdx: number, patch: Partial<CourseRow>) {
    setSemesters((prev) =>
      prev.map((s) => {
        if (s.id !== semId) return s;
        return {
          ...s,
          courses: s.courses.map((c, i) => (i === courseIdx ? { ...c, ...patch } : c)),
        };
      }),
    );
  }

  function removeCourse(semId: string, courseIdx: number) {
    setSemesters((prev) =>
      prev.map((s) => {
        if (s.id !== semId) return s;
        return { ...s, courses: s.courses.filter((_, i) => i !== courseIdx) };
      }),
    );
  }

  function selectAvailableCourse(semId: string, courseIdx: number, courseCode: string) {
    const found = availableCourses.find((c) => c.code === courseCode);
    if (found) {
      updateCourse(semId, courseIdx, { code: found.code, title: found.title, credits: found.credits });
    }
  }

  // Real-time calculations
  const cumulative = useMemo(() => cumulativeGpa(semesters), [semesters]);
  const gpaChange = originalGpa != null && cumulative.gpa != null ? cumulative.gpa - originalGpa : null;

  // Check if user changed any grade from the original transcript, or added any courses/semesters
  const hasEdits = semesters.some(
    (s) => s.isNew || s.courses.some((c) => c.isUserAdded || c.grade !== c.originalGrade),
  );

  function resetAll() {
    if (!token) return;
    loadData(token);
  }

  const cardClass = `rounded-xl border shadow-sm ${isDark ? "border-zinc-700 bg-zinc-800" : "border-zinc-200 bg-white"}`;
  const headerClass = `text-xs uppercase tracking-wide font-semibold ${isDark ? "text-zinc-400" : "text-zinc-500"}`;

  return (
    <AppLayout activePath="/gpa-simulator" userName="GPA Simulator">
      <main className="px-4 md:px-8 lg:px-16 py-8 max-w-[1200px] mx-auto">
        <motion.header initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} className="mb-8">
          <h1 className="text-[28px] font-bold text-[#A0001A] dark:text-[#ef4444]">{t("sim.title")}</h1>
          <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">
            See how your current and future grades affect your cumulative GPA. Edit grades or add new semesters to simulate scenarios.
          </p>
        </motion.header>

        {err && (
          <div className="rounded-lg bg-red-50 dark:bg-red-950/30 text-red-700 dark:text-red-400 px-4 py-3 text-sm mb-6 border border-red-200 dark:border-red-800">
            {err}
          </div>
        )}

        {/* ── Cumulative GPA Summary ── */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="mb-8">
          <div className={`${cardClass} p-8`}>
            <div className="text-center">
              <div className={`text-[11px] uppercase tracking-[0.25em] font-bold ${isDark ? "text-zinc-400" : "text-zinc-500"}`}>
                Cumulative GPA
              </div>
              {(() => {
                const displayGpa = cumulative.totalCr > 0 && cumulative.gpa != null ? cumulative.gpa : 0;
                const tone =
                  cumulative.totalCr === 0 ? "text-zinc-400 dark:text-zinc-500"
                  : displayGpa >= 3.5 ? "text-green-600 dark:text-green-400"
                  : displayGpa >= 2.5 ? "text-amber-500 dark:text-amber-400"
                  : "text-red-500 dark:text-red-400";
                return (
                  <motion.div
                    key={displayGpa.toFixed(3)}
                    initial={{ scale: 0.92, opacity: 0.4 }}
                    animate={{ scale: 1, opacity: 1 }}
                    transition={{ duration: 0.25, ease: "easeOut" }}
                    className={`text-[68px] font-bold mt-2 leading-none tabular-nums tracking-tight ${tone}`}
                  >
                    {displayGpa.toFixed(2)}
                  </motion.div>
                );
              })()}
              <div className={`flex items-center justify-center gap-3 mt-4 text-sm font-semibold`}>
                {originalGpa != null ? (
                  <span className={isDark ? "text-zinc-500" : "text-zinc-400"}>
                    Starting: <span className="tabular-nums">{originalGpa.toFixed(2)}</span>
                  </span>
                ) : null}
                {gpaChange != null && hasEdits && cumulative.totalCr > 0 && (
                  <>
                    <span className="text-zinc-400">•</span>
                    <span className={gpaChange > 0 ? "text-green-600 dark:text-green-400" : gpaChange < 0 ? "text-red-600 dark:text-red-400" : ""}>
                      {gpaChange >= 0 ? "+" : ""}{gpaChange.toFixed(3)}
                    </span>
                  </>
                )}
              </div>
            </div>
            <div className={`flex flex-wrap items-center justify-center gap-x-4 gap-y-1 mt-6 text-xs ${isDark ? "text-zinc-500" : "text-zinc-400"}`}>
              <span>Formula: Σ(Grade Points × Credits) / Σ(Credits)</span>
              <span>•</span>
              <span>{t("sim.totalCredits")} <span className="tabular-nums font-semibold">{cumulative.totalCr}</span></span>
              {hasEdits && (
                <>
                  <span>•</span>
                  <button
                    onClick={resetAll}
                    className={`font-semibold underline ${isDark ? "text-blue-400 hover:text-blue-300" : "text-blue-600 hover:text-blue-700"}`}
                    type="button"
                  >
                    Reset to transcript
                  </button>
                </>
              )}
            </div>
          </div>
        </motion.div>

        {loading && (
          <div className="space-y-4">
            {[1, 2].map((i) => (
              <div key={i} className={`${cardClass} p-6 animate-pulse`}>
                <div className={`h-5 w-32 rounded ${isDark ? "bg-zinc-700" : "bg-zinc-200"}`} />
                <div className={`h-4 w-full rounded mt-4 ${isDark ? "bg-zinc-700" : "bg-zinc-200"}`} />
                <div className={`h-4 w-3/4 rounded mt-2 ${isDark ? "bg-zinc-700" : "bg-zinc-200"}`} />
              </div>
            ))}
          </div>
        )}

        {/* ── Semester Blocks ── */}
        <div className="space-y-6">
          <AnimatePresence>
            {semesters.map((sem, semIdx) => {
              const sgpa = semesterGpa(sem.courses);
              const semCredits = sem.courses.reduce((sum, c) => sum + (c.credits || 0), 0);
              // A real transcript term with every grade posted is history — locked.
              // A real term with ungraded courses is in progress — only its
              // missing grades can be simulated. Hypothetical terms are free.
              const isCompleted =
                !sem.isNew &&
                sem.courses.length > 0 &&
                sem.courses.every((c) => c.originalGrade !== NOT_GRADED);
              const isInProgress = !sem.isNew && !isCompleted;

              return (
                <motion.div
                  key={sem.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -20, height: 0 }}
                  transition={{ delay: semIdx * 0.05 }}
                  className={cardClass}
                >
                  {/* Semester header */}
                  <div className={`flex items-center justify-between px-6 py-4 border-b ${isDark ? "border-zinc-700" : "border-zinc-200"}`}>
                    <div className="flex items-center gap-3">
                      {sem.isNew ? (
                        <input
                          type="text"
                          value={sem.name}
                          onChange={(e) => updateSemesterName(sem.id, e.target.value)}
                          className={`text-base font-bold bg-transparent border-b-2 border-dashed outline-none px-1 py-0.5 w-48 ${
                            isDark ? "border-zinc-600 text-white" : "border-zinc-300 text-zinc-900"
                          }`}
                          placeholder={t("sim.semName")}
                        />
                      ) : (
                        <div className={`text-base font-bold px-1 py-0.5 ${isDark ? "text-white" : "text-zinc-900"}`}>
                          {sem.name}
                        </div>
                      )}
                      {sem.isNew && (
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-400">
                          HYPOTHETICAL
                        </span>
                      )}
                      {isCompleted && (
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full flex items-center gap-1 ${
                          isDark ? "bg-zinc-700 text-zinc-300" : "bg-zinc-100 text-zinc-500"
                        }`}>
                          🔒 COMPLETED
                        </span>
                      )}
                      {isInProgress && (
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400">
                          IN PROGRESS
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-4">
                      <div className={`text-sm ${isDark ? "text-zinc-400" : "text-zinc-500"}`}>
                        {semCredits} Credits
                      </div>
                      <div className={`rounded-full px-4 py-1.5 text-xs font-bold text-white min-w-[90px] text-center ${
                        sgpa == null ? "bg-zinc-400" : sgpa >= 3.5 ? "bg-green-600" : sgpa >= 2.5 ? "bg-amber-500" : "bg-red-500"
                      }`}>
                        GPA: {sgpa != null ? sgpa.toFixed(2) : "—"}
                      </div>
                      {sem.isNew && (
                        <button
                          onClick={() => removeSemester(sem.id)}
                          className="text-red-500 hover:text-red-700 text-sm font-medium"
                          type="button"
                          title={t("sim.removeSem")}
                        >
                          Remove
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Course table */}
                  <div className="px-6 py-3">
                    {/* Table header */}
                    <div className={`grid grid-cols-12 gap-3 text-xs font-bold uppercase tracking-wide py-2 ${isDark ? "text-zinc-500" : "text-zinc-400"}`}>
                      <div className="col-span-3">{t("sim.course")}</div>
                      <div className="col-span-4">{t("sim.name")}</div>
                      <div className="col-span-2 text-center">{t("sim.credits")}</div>
                      <div className="col-span-2 text-center">{t("sim.grade")}</div>
                      <div className="col-span-1 text-center">{t("sim.pts")}</div>
                    </div>

                    {/* Course rows */}
                    <div className={`divide-y ${isDark ? "divide-zinc-700/50" : "divide-zinc-100"}`}>
                      {sem.courses.map((course, cIdx) => {
                        const pts = GRADE_POINTS[course.grade];
                        const isModified = !course.isUserAdded && course.grade !== course.originalGrade;
                        // Posted grades are history: the whole row is read-only.
                        // In-progress courses (no grade yet) allow ONLY a
                        // simulated grade. User-added rows stay fully editable.
                        const isLocked = !course.isUserAdded && course.originalGrade !== NOT_GRADED;
                        const gradeEditable = !isLocked;
                        const detailsEditable = course.isUserAdded;
                        const staticCell = `text-sm px-2 py-1.5 ${isDark ? "text-zinc-300" : "text-zinc-700"}`;
                        return (
                          <div key={cIdx} className={`grid grid-cols-12 gap-3 py-3 items-center text-sm ${isDark ? "hover:bg-zinc-700/30" : "hover:bg-zinc-50"} rounded transition-colors ${isLocked ? "opacity-90" : ""}`}>
                            {/* Course code */}
                            <div className="col-span-3">
                              {detailsEditable ? (
                                <input
                                  type="text"
                                  value={course.code}
                                  onChange={(e) => updateCourse(sem.id, cIdx, { code: e.target.value.toUpperCase() })}
                                  className={`w-full h-9 rounded-lg border px-2 text-sm font-semibold ${
                                    isDark ? "bg-zinc-700 border-zinc-600 text-white" : "bg-white border-zinc-300"
                                  }`}
                                  placeholder={t("sim.egCode")}
                                />
                              ) : (
                                <div className={`${staticCell} font-semibold`}>{course.code}</div>
                              )}
                            </div>

                            {/* Title */}
                            <div className="col-span-4">
                              {detailsEditable ? (
                                <input
                                  type="text"
                                  value={course.title}
                                  onChange={(e) => updateCourse(sem.id, cIdx, { title: e.target.value })}
                                  className={`w-full h-9 rounded-lg border px-2 text-sm ${
                                    isDark ? "bg-zinc-700 border-zinc-600 text-white" : "bg-white border-zinc-300"
                                  }`}
                                  placeholder={t("sim.courseName")}
                                />
                              ) : (
                                <div className={staticCell}>{course.title}</div>
                              )}
                            </div>

                            {/* Credits */}
                            <div className="col-span-2 text-center">
                              {detailsEditable ? (
                                <input
                                  type="number"
                                  min={1}
                                  max={6}
                                  value={course.credits}
                                  onChange={(e) => updateCourse(sem.id, cIdx, { credits: Number(e.target.value) || 1 })}
                                  className={`w-16 h-9 rounded-lg border px-2 text-sm text-center mx-auto ${
                                    isDark ? "bg-zinc-700 border-zinc-600 text-white" : "bg-white border-zinc-300"
                                  }`}
                                />
                              ) : (
                                <div className={`${staticCell} text-center tabular-nums`}>{course.credits}</div>
                              )}
                            </div>

                            {/* Grade */}
                            <div className="col-span-2 text-center">
                              {gradeEditable ? (
                                <div className="relative inline-block">
                                  <select
                                    value={course.grade}
                                    onChange={(e) => updateCourse(sem.id, cIdx, { grade: e.target.value })}
                                    className={`h-9 rounded-lg border-2 px-2 text-sm font-bold text-center mx-auto transition-colors ${
                                      course.grade === "Dropped" ? "w-24" : "w-20"
                                    } ${
                                      course.grade === "Dropped"
                                        ? isDark
                                          ? "bg-zinc-700/60 border-dashed border-zinc-500 text-zinc-300"
                                          : "bg-green-50 border-dashed border-green-300 text-green-700"
                                        : isModified
                                        ? isDark
                                          ? "bg-blue-900/40 border-blue-500 text-blue-200"
                                          : "bg-blue-50 border-blue-400 text-blue-700"
                                        : isDark
                                        ? "bg-zinc-700 border-zinc-600 text-white"
                                        : "bg-white border-zinc-300"
                                    }`}
                                    title={isModified ? `Original: ${course.originalGrade}` : ""}
                                  >
                                    {!course.isUserAdded && (
                                      <option value={NOT_GRADED}>{NOT_GRADED}</option>
                                    )}
                                    {GRADE_OPTIONS.map((g) => (
                                      <option key={g} value={g}>{g}</option>
                                    ))}
                                  </select>
                                  {isModified && (
                                    <span className="absolute -top-1 -right-1 w-2 h-2 rounded-full bg-blue-500 ring-2 ring-white dark:ring-zinc-800" title={`Changed from ${course.originalGrade}`}></span>
                                  )}
                                </div>
                              ) : (
                                <span className={`inline-flex h-9 items-center justify-center rounded-lg px-3 text-sm font-bold w-20 ${
                                  isDark ? "bg-zinc-700/60 text-zinc-200" : "bg-zinc-100 text-zinc-700"
                                }`}>
                                  {course.grade}
                                </span>
                              )}
                            </div>

                            {/* Points / Remove */}
                            <div className="col-span-1 text-center flex items-center justify-center gap-1">
                              <span className={`font-semibold ${isDark ? "text-zinc-400" : "text-zinc-500"}`}>
                                {pts != null ? pts.toFixed(1) : "—"}
                              </span>
                              {course.isUserAdded && (
                                <button
                                  onClick={() => removeCourse(sem.id, cIdx)}
                                  className="text-red-400 hover:text-red-600 ml-1 font-bold"
                                  type="button"
                                  title={t("sim.removeCourse")}
                                >
                                  ×
                                </button>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>

                    {/* Add course — only in hypothetical semesters; past terms are facts */}
                    {sem.isNew && (
                      <button
                        onClick={() => addCourse(sem.id)}
                        className={`mt-2 text-sm font-medium px-3 py-1.5 rounded-lg transition-colors ${
                          isDark ? "text-blue-400 hover:bg-zinc-700" : "text-blue-600 hover:bg-blue-50"
                        }`}
                        type="button"
                      >
                        + Add Course
                      </button>
                    )}
                  </div>
                </motion.div>
              );
            })}
          </AnimatePresence>
        </div>

        {/* ── Add Semester Button ── */}
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }} className="mt-6 flex justify-center">
          <Button
            onClick={addSemester}
            className="h-12 rounded-xl bg-[#163A8A] hover:bg-[#0F2E73] px-8 text-sm font-bold shadow-md hover:shadow-lg transition-all"
          >
            + Add Semester
          </Button>
        </motion.div>

        {/* ── GPA Scale Reference ── */}
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.4 }} className="mt-10">
          <h3 className={`text-sm font-bold mb-3 ${isDark ? "text-zinc-400" : "text-zinc-500"}`}>{t("sim.scale")}</h3>
          <div className={`${cardClass} p-4`}>
            <div className="flex flex-wrap gap-3 justify-center">
              {GRADE_OPTIONS.map((g) => (
                <div key={g} className={`text-center px-3 py-2 rounded-lg text-xs ${isDark ? "bg-zinc-700" : "bg-zinc-50"}`}>
                  <div className="font-bold">{g}</div>
                  <div className={isDark ? "text-zinc-400" : "text-zinc-500"}>{GRADE_POINTS[g]?.toFixed(1)}</div>
                </div>
              ))}
            </div>
          </div>
        </motion.div>
      </main>
    </AppLayout>
  );
}
