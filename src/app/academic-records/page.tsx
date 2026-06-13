"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

import {
  getMe,
  getMyGpa,
  getMyTranscript,
  getGraduationCountdown,
  getMyStanding,
  type MeResponse,
  type AcademicRecordsResponse,
} from "@/lib/api";
import { normalizeErrorMessage, isAbortError } from "@/lib/utils";
import { fmtNum, gpaTone, ArcRingChart, GPATrendArcChart } from "@/components/academic/charts";
import { Button } from "@/components/ui/button";
import ErrorBanner from "@/components/ErrorBanner";
import EmptyState from "@/components/EmptyState";
import { CardSkeleton, TableSkeleton } from "@/components/LoadingSkeleton";
import AppLayout from "@/components/layout/AppLayout";
import { useLanguage } from "@/hooks/useLanguage";
import PageContainer from "@/components/layout/PageContainer";
import { useAuth } from "@/hooks/useAuth";
import { useTheme } from "@/hooks/useTheme";

/* ── Utility functions ─────────────────────────────────── */

function parseTermKey(term: string) {
  const m = term.match(/(winter|spring|summer|fall)\s*(\d{4})/i);
  if (!m) return { year: 0, season: 0 };
  const seasonName = m[1].toLowerCase();
  const year = Number(m[2]);
  const seasonOrder: Record<string, number> = {
    winter: 0,
    spring: 1,
    summer: 2,
    fall: 3,
  };
  return { year, season: seasonOrder[seasonName] ?? 0 };
}

function sortTermsDesc(terms: string[]) {
  return [...terms].sort((a, b) => {
    const A = parseTermKey(a);
    const B = parseTermKey(b);
    if (A.year !== B.year) return B.year - A.year;
    return B.season - A.season;
  });
}

function computeTrendSafe(trend: Array<{ term: string; gpa: number }>) {
  const withKey = trend.map((p, i) => ({ ...p, _i: i, _k: parseTermKey(p.term) }));
  const canSort = withKey.some((x) => x._k.year !== 0);
  if (!canSort) return trend;
  return [...withKey]
    .sort((a, b) => {
      if (a._k.year !== b._k.year) return a._k.year - b._k.year;
      return a._k.season - b._k.season;
    })
    .map(({ term, gpa }) => ({ term, gpa }));
}

function generateTranscriptPDF(studentName: string, studentId: string, records: AcademicRecordsResponse) {
  const lines: string[] = [];
  lines.push("=========================================");
  lines.push("      OFFICIAL ACADEMIC TRANSCRIPT");
  lines.push("   Al Alamein International University");
  lines.push("=========================================\n");
  lines.push(`Student Name: ${studentName}`);
  lines.push(`Student ID: ${studentId}`);
  lines.push(
    `Date Issued: ${new Date().toLocaleDateString("en-US", {
      year: "numeric",
      month: "long",
      day: "numeric",
    })}\n`
  );
  lines.push("─────────────────────────────────────────\n");
  lines.push("ACADEMIC SUMMARY");
  lines.push("─────────────────────────────────────────");
  lines.push(`Cumulative GPA: ${fmtNum(records.summary.cgpa, 2)}`);
  lines.push(`Completed Credit Hours: ${records.summary.completed_hours ?? "—"}`);
  lines.push(`Remaining Credit Hours: ${records.summary.remaining_hours ?? "—"}`);
  lines.push(`Total Program Credit Hours: ${records.summary.total_hours ?? "—"}`);
  lines.push(`Class Rank: ${records.summary.class_rank ?? "—"}`);
  lines.push(`Academic Status: ${records.summary.status ?? "Good Standing"}\n`);

  const termKeys = sortTermsDesc(Object.keys(records.terms));
  for (const term of termKeys) {
    const block = records.terms[term];
    lines.push("\n─────────────────────────────────────────");
    lines.push(`${term.toUpperCase()}`);
    lines.push(`Term GPA: ${fmtNum(block.term_gpa, 2)}`);
    lines.push(`Credits: ${block.courses.reduce((sum, c) => sum + (c.credits || 0), 0)}`);
    lines.push("─────────────────────────────────────────\n");
    lines.push("Course Code".padEnd(15) + "Course Name".padEnd(40) + "Credits".padEnd(10) + "Grade".padEnd(8) + "Points");
    lines.push("-".repeat(80));
    for (const course of block.courses) {
      const code = (course.code || "").padEnd(15);
      const name = (course.title || "").substring(0, 38).padEnd(40);
      const credits = String(course.credits ?? "—").padEnd(10);
      const grade = (course.grade || "—").padEnd(8);
      const points = course.points !== null && course.points !== undefined ? fmtNum(course.points, 2) : "—";
      lines.push(code + name + credits + grade + points);
    }
  }
  lines.push("\n\n─────────────────────────────────────────");
  lines.push("END OF TRANSCRIPT");
  lines.push("─────────────────────────────────────────");
  lines.push("\nThis is an official transcript issued by");
  lines.push("Al Alamein International University");
  const content = lines.join("\n");
  const blob = new Blob([content], { type: "text/plain" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `Transcript_${studentId}_${new Date().getTime()}.txt`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

/* ── Page component ────────────────────────────────────── */

export default function AcademicRecordsPage() {
  const { t } = useLanguage();
  const { isDark } = useTheme();
  const { token, signOut } = useAuth();

  const [summary, setSummary] = useState<MeResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [records, setRecords] = useState<AcademicRecordsResponse | null>(null);
  const [recordsLoading, setRecordsLoading] = useState(true);
  const [openTerm, setOpenTerm] = useState<string | null>(null);
  const [countdown, setCountdown] = useState<any>(null);
  const [standingInfo, setStandingInfo] = useState<any>(null);

  const loadData = useCallback(async (tkn: string, signal?: AbortSignal) => {
    setErr(null);
    setRecordsLoading(true);
    try {
      const [me, gpa, transcript, grad, standing] = await Promise.all([
        getMe(tkn, signal),
        getMyGpa(tkn, signal),
        getMyTranscript(tkn, signal),
        getGraduationCountdown(tkn, signal).catch(() => null),
        getMyStanding(tkn, signal).catch(() => null),
      ]);
      if (signal?.aborted) return;
      const terms: AcademicRecordsResponse["terms"] = {};
      const transcriptData = transcript.terms || transcript;
      const termEntries = Array.isArray(transcriptData)
        ? transcriptData.map((t: any) => [t.semester, t] as const)
        : Object.entries(transcriptData as Record<string, any>);
      for (const [semKey, termBlock] of termEntries) {
        const block = termBlock as any;
        terms[semKey as string] = {
          term_gpa: block.term_gpa ?? null,
          courses: (block.courses || []).map((c: any) => ({
            code: c.course_code || c.code,
            title: c.course_name || c.course_title || c.title,
            credits: c.credits ?? null,
            grade: c.grade || c.grade_letter || null,
            points: c.grade_points ?? c.points ?? null,
            status: c.status ?? null,
          })),
        };
      }
      setSummary(me);
      setCountdown(grad);
      setStandingInfo(standing);
      setRecords({
        summary: {
          cgpa: gpa.cgpa,
          completed_hours: gpa.completed_credits,
          remaining_hours: (gpa.total_credits && gpa.completed_credits != null) ? gpa.total_credits - gpa.completed_credits : null,
          total_hours: gpa.total_credits,
          class_rank: null,
          status: me.standing ?? null,
        },
        gpa_trend: (gpa.semester_history || []).map((s) => ({ term: s.semester, gpa: s.sgpa })),
        terms,
      });
    } catch (e: unknown) {
      if (isAbortError(e)) return;
      const msg = normalizeErrorMessage(e, "Failed to load academic records");
      if (msg.toLowerCase().includes("unauthorized") || msg.toLowerCase().includes("invalid token")) {
        signOut();
        return;
      }
      setErr(msg);
    } finally {
      if (!signal?.aborted) setRecordsLoading(false);
    }
  }, [signOut]);

  useEffect(() => {
    if (!token) return;
    const controller = new AbortController();
    loadData(token, controller.signal);
    return () => controller.abort();
  }, [token, loadData]);

  const retry = useCallback(() => {
    if (token) loadData(token);
  }, [token, loadData]);

  function handleDownloadTranscript() {
    if (!records || !summary) {
      alert("Academic records not loaded yet");
      return;
    }
    generateTranscriptPDF(summary.full_name, summary.student_number, records);
  }

  const cgpa = records?.summary?.cgpa ?? null;
  const completedHours = records?.summary?.completed_hours ?? null;
  const remaining = records?.summary?.remaining_hours ?? null;
  const totalHours = records?.summary?.total_hours ?? null;
  const rank = records?.summary?.class_rank ?? null;
  const status = records?.summary?.status ?? "Good Standing";
  const tone = gpaTone(cgpa);
  const takenHours = totalHours && remaining !== null ? totalHours - remaining : completedHours;
  const trend = useMemo(() => computeTrendSafe(records?.gpa_trend ?? []), [records?.gpa_trend]);
  const latestChange = trend.length >= 2 ? trend[trend.length - 1].gpa - trend[trend.length - 2].gpa : undefined;
  const termKeys = records?.terms ? sortTermsDesc(Object.keys(records.terms)) : [];

  return (
    <AppLayout activePath="/academic-records" userName={summary?.full_name ?? "Loading..."}>
      <PageContainer className="px-6 md:px-12 lg:px-20">
        <div className="max-w-[1400px] mx-auto">
          {err && (
            <div className="space-y-2">
              <ErrorBanner message={err} isDark={isDark} onDismiss={() => setErr(null)} />
              <Button
                type="button"
                onClick={retry}
                className="h-9 rounded-lg bg-[#B8001F] hover:bg-[#9A0019] px-5 text-sm font-semibold text-white"
              >
                Retry
              </Button>
            </div>
          )}
          <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} className="mb-8">
            <h1 className="text-[28px] font-bold text-[#A0001A] dark:text-[#ef4444]">{t("rec.title")}</h1>
          </motion.div>

          {recordsLoading && !records && (
            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <CardSkeleton isDark={isDark} />
                <CardSkeleton isDark={isDark} />
                <CardSkeleton isDark={isDark} />
              </div>
              <TableSkeleton rows={5} isDark={isDark} />
            </div>
          )}

          {!recordsLoading && records && termKeys.length === 0 && (
            <EmptyState
              title={t("rec.noRecords")}
              description="Your transcript will appear here once you complete your first semester."
              icon="📚"
              isDark={isDark}
            />
          )}

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
            <motion.div
              initial={{ opacity: 0, scale: 0.9, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              transition={{ delay: 0.1, type: "spring", stiffness: 200, damping: 20 }}
              className={`rounded-xl border p-6 shadow-sm hover:shadow-md transition-shadow ${isDark ? "border-zinc-700 bg-zinc-800" : "border-zinc-200 bg-white"}`}
            >
              <ArcRingChart value={cgpa} max={4} label={t("rec.cgpa")} sublabel={`${cgpa !== null ? fmtNum(cgpa, 2) : "—"}`} color={tone.fill} isDark={isDark} />
            </motion.div>

            <motion.div
              initial={{ opacity: 0, scale: 0.9, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              transition={{ delay: 0.2, type: "spring", stiffness: 200, damping: 20 }}
              className={`rounded-xl border p-6 shadow-sm hover:shadow-md transition-shadow ${isDark ? "border-zinc-700 bg-zinc-800" : "border-zinc-200 bg-white"}`}
            >
              <ArcRingChart value={remaining} max={totalHours || 144} label={t("rec.remHours")} sublabel={`Taken ${takenHours ?? "—"} / ${totalHours ?? 144}`} color="#16a34a" isDark={isDark} />
              <div className="text-center mt-4">
                <div className={`text-xs ${isDark ? "text-zinc-400" : "text-zinc-500"}`}>
                  Academic Standing : <span className="font-bold text-green-600 dark:text-green-400">{status}</span>
                </div>
              </div>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, scale: 0.9, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              transition={{ delay: 0.3, type: "spring", stiffness: 200, damping: 20 }}
              whileHover={{ y: -3 }}
              className={`rounded-xl border shadow-sm hover:shadow-lg transition-shadow overflow-hidden ${isDark ? "border-zinc-700 bg-zinc-800" : "border-zinc-200 bg-white"}`}
            >
              <div className="relative w-full h-full rounded-xl bg-gradient-to-br from-[#0F2E73] via-[#1E40AF] to-[#2563EB] px-7 py-8 text-white overflow-hidden">
                <motion.div
                  className="absolute -right-10 -top-10 w-44 h-44 rounded-full bg-white/5"
                  animate={{ scale: [1, 1.12, 1] }}
                  transition={{ duration: 4.5, repeat: Infinity, ease: "easeInOut" }}
                />
                <motion.div
                  className="absolute -left-6 -bottom-6 w-28 h-28 rounded-full bg-white/5"
                  animate={{ scale: [1.1, 1, 1.1] }}
                  transition={{ duration: 4.5, repeat: Infinity, ease: "easeInOut" }}
                />
                <motion.div
                  className="absolute right-6 top-6 w-2 h-2 rounded-full bg-white"
                  animate={{ opacity: [0.3, 1, 0.3] }}
                  transition={{ duration: 2.5, repeat: Infinity, ease: "easeInOut" }}
                />
                <div className="relative">
                  <motion.div
                    initial={{ opacity: 0, x: -6 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.45, duration: 0.4 }}
                    className="text-[10px] font-bold tracking-[0.2em] uppercase opacity-90"
                  >
                    Class Rank
                  </motion.div>
                  <motion.div
                    initial={{ opacity: 0, y: 10, scale: 0.85 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    transition={{ delay: 0.55, type: "spring", stiffness: 180, damping: 18 }}
                    className="mt-3 flex items-baseline gap-1.5"
                  >
                    <div className="text-[56px] font-bold leading-none tabular-nums bg-gradient-to-br from-white to-white/70 bg-clip-text text-transparent">
                      {rank === null || rank === undefined ? "—" : String(rank)}
                    </div>
                    {(typeof rank === "number" || (typeof rank === "string" && !isNaN(Number(rank)))) && (
                      <div className="text-xl font-semibold opacity-80">th</div>
                    )}
                  </motion.div>
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.85, duration: 0.4 }}
                    className="mt-3 text-[10px] font-semibold opacity-80 tracking-wide"
                  >
                    out of 30 students
                  </motion.div>
                </div>
              </div>
            </motion.div>
          </div>

          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }} className="mb-10">
            <h2 className="mb-4 text-lg font-bold text-[#A0001A] dark:text-[#ef4444]">{t("rec.trend")}</h2>
            {recordsLoading ? (
              <div className={`rounded-xl border p-8 text-center text-sm animate-pulse ${isDark ? "border-zinc-700 bg-zinc-800 text-zinc-400" : "border-zinc-200 bg-white text-zinc-500"}`}>
                Loading trend data...
              </div>
            ) : (
              <GPATrendArcChart points={trend} latestChange={latestChange} isDark={isDark} />
            )}
          </motion.div>

          {countdown && (
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.45 }} className="mb-10">
              <h2 className="mb-4 text-lg font-bold text-[#A0001A] dark:text-[#ef4444]">{t("rec.gradProgress")}</h2>
              <div className={`grid grid-cols-1 sm:grid-cols-3 gap-4`}>
                <motion.div whileHover={{ scale: 1.03, y: -4 }} className={`rounded-xl border p-5 shadow-sm transition-shadow hover:shadow-md ${isDark ? "border-zinc-700 bg-zinc-800" : "border-zinc-200 bg-white"}`}>
                  <div className={`text-xs uppercase tracking-wide font-semibold ${isDark ? "text-zinc-400" : "text-zinc-500"}`}>{t("rec.best")}</div>
                  <div className="text-3xl font-bold mt-2 text-green-600">{countdown.best_case ?? countdown.best_case_semesters ?? "—"} <span className="text-base font-medium">{t("rec.semesters")}</span></div>
                </motion.div>
                <motion.div whileHover={{ scale: 1.03, y: -4 }} className={`rounded-xl border p-5 shadow-sm transition-shadow hover:shadow-md ${isDark ? "border-zinc-700 bg-zinc-800" : "border-zinc-200 bg-white"}`}>
                  <div className={`text-xs uppercase tracking-wide font-semibold ${isDark ? "text-zinc-400" : "text-zinc-500"}`}>{t("rec.worst")}</div>
                  <div className="text-3xl font-bold mt-2 text-amber-600">{countdown.worst_case ?? countdown.worst_case_semesters ?? "—"} <span className="text-base font-medium">{t("rec.semesters")}</span></div>
                </motion.div>
                <motion.div whileHover={{ scale: 1.03, y: -4 }} className={`rounded-xl border p-5 shadow-sm transition-shadow hover:shadow-md ${isDark ? "border-zinc-700 bg-zinc-800" : "border-zinc-200 bg-white"}`}>
                  <div className={`text-xs uppercase tracking-wide font-semibold ${isDark ? "text-zinc-400" : "text-zinc-500"}`}>{t("rec.remCredits")}</div>
                  <div className="text-3xl font-bold mt-2 text-[#B8001F]">{countdown.remaining_credits}</div>
                </motion.div>
              </div>
            </motion.div>
          )}

          {standingInfo?.risk_message && (
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.47 }} className="mb-10">
              <div className="rounded-xl border-2 border-amber-400 bg-amber-50 dark:bg-amber-950/30 dark:border-amber-600 p-5">
                <div className="text-sm font-bold text-amber-700 dark:text-amber-400">{t("rec.standingAlert")}</div>
                <div className="text-sm mt-1 text-amber-600 dark:text-amber-300">{standingInfo.risk_message}</div>
              </div>
            </motion.div>
          )}

          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.5 }} className="mb-10">
            <div className="mb-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
              <h2 className="text-lg font-bold text-[#A0001A] dark:text-[#ef4444]">{t("rec.semGrades")}</h2>
              <Button
                type="button"
                className="h-10 rounded-full bg-[#163A8A] hover:bg-[#0F2E73] px-6 text-sm font-bold shadow-md hover:shadow-lg transition-all flex items-center gap-2"
                onClick={handleDownloadTranscript}
                disabled={!records || recordsLoading}
              >
                <span>⬇</span>Download Official Transcript
              </Button>
            </div>
            <div className={`rounded-xl border shadow-sm overflow-hidden ${isDark ? "border-zinc-700 bg-zinc-800" : "border-zinc-200 bg-white"}`}>
              <div className={isDark ? "divide-y divide-zinc-700" : "divide-y divide-zinc-100"}>
                {recordsLoading ? (
                  <div className={`p-8 text-center text-sm animate-pulse ${isDark ? "text-zinc-400" : "text-zinc-500"}`}>{t("rec.loadingTerms")}</div>
                ) : termKeys.length === 0 ? (
                  <div className={`p-8 text-center text-sm ${isDark ? "text-zinc-400" : "text-zinc-500"}`}>{t("rec.noTerms")}</div>
                ) : (
                  termKeys.map((term, idx) => {
                    const block = records!.terms[term];
                    const isOpen = openTerm === term;
                    const termCredits = block.courses.reduce((sum, c) => sum + (c.credits || 0), 0);
                    return (
                      <motion.div key={term} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: idx * 0.05 }}>
                        <button
                          type="button"
                          onClick={() => setOpenTerm((prev) => (prev === term ? null : term))}
                          className={`w-full px-6 py-5 flex items-center justify-between transition-colors ${isDark ? "hover:bg-zinc-700" : "hover:bg-zinc-50"}`}
                        >
                          <div className="flex items-center gap-4">
                            <div className={`text-base font-bold ${isDark ? "text-white" : "text-zinc-900"}`}>{term}</div>
                          </div>
                          <div className="flex items-center gap-4">
                            <div className={`text-sm font-semibold ${isDark ? "text-zinc-400" : "text-zinc-600"}`}>{termCredits} Credits</div>
                            <div className="rounded-full bg-green-600 px-4 py-2 text-xs font-bold text-white min-w-[80px] text-center flex items-center gap-2">
                              <span>GPA:</span>
                              <span>{block.term_gpa === null ? "—" : fmtNum(block.term_gpa, 2)}</span>
                              <span className="text-[10px]">⏱</span>
                            </div>
                            <motion.div
                              animate={{ rotate: isOpen ? 180 : 0 }}
                              transition={{ duration: 0.2 }}
                              className={isDark ? "text-zinc-500 text-xl" : "text-zinc-400 text-xl"}
                            >
                              ▸
                            </motion.div>
                          </div>
                        </button>
                        <AnimatePresence initial={false}>
                          {isOpen && (
                            <motion.div
                              initial={{ height: 0, opacity: 0 }}
                              animate={{ height: "auto", opacity: 1 }}
                              exit={{ height: 0, opacity: 0 }}
                              transition={{ height: { duration: 0.35, ease: [0.04, 0.62, 0.23, 0.98] }, opacity: { duration: 0.25 } }}
                              className="overflow-hidden"
                            >
                              <div className="px-6 pb-6">
                                <div className={`rounded-xl border overflow-hidden ${isDark ? "border-zinc-700" : "border-zinc-200"}`}>
                                  <div
                                    className={`grid grid-cols-12 gap-4 px-6 py-3 text-xs font-bold border-b ${
                                      isDark ? "bg-zinc-700 text-zinc-300 border-zinc-600" : "bg-zinc-50 text-zinc-600 border-zinc-200"
                                    }`}
                                  >
                                    <div className="col-span-2">{t("rec.courseCode")}</div>
                                    <div className="col-span-5">{t("rec.courseName")}</div>
                                    <div className="col-span-2 text-center">{t("rec.credits")}</div>
                                    <div className="col-span-2 text-center">{t("rec.grade")}</div>
                                    <div className="col-span-1 text-center">{t("rec.points")}</div>
                                  </div>
                                  <div className={isDark ? "divide-y divide-zinc-700 bg-zinc-800" : "divide-y divide-zinc-100 bg-white"}>
                                    {block.courses.map((c, cidx) => (
                                      <motion.div
                                        key={c.code + cidx}
                                        initial={{ opacity: 0, x: -10 }}
                                        animate={{ opacity: 1, x: 0 }}
                                        transition={{ delay: cidx * 0.03 }}
                                        className={`grid grid-cols-12 gap-4 px-6 py-4 text-sm transition-colors ${isDark ? "hover:bg-zinc-700" : "hover:bg-zinc-50"}`}
                                      >
                                        <div className={`col-span-2 font-semibold ${isDark ? "text-white" : "text-zinc-900"}`}>{c.code}</div>
                                        <div className={`col-span-5 ${isDark ? "text-zinc-300" : "text-zinc-700"}`}>{c.title}</div>
                                        <div className={`col-span-2 text-center ${isDark ? "text-zinc-400" : "text-zinc-600"}`}>{c.credits ?? "—"}</div>
                                        <div className="col-span-2 text-center">
                                          <span
                                            className={`inline-block px-3 py-1 rounded-full text-xs font-bold ${
                                              c.status === "Pending" ? "bg-blue-100 text-blue-700" : "bg-green-100 text-green-700"
                                            }`}
                                          >
                                            {c.grade || c.status || "—"}
                                          </span>
                                        </div>
                                        <div className={`col-span-1 text-center font-semibold ${isDark ? "text-zinc-400" : "text-zinc-600"}`}>
                                          {c.points !== null && c.points !== undefined ? fmtNum(c.points, 2) : "—"}
                                        </div>
                                      </motion.div>
                                    ))}
                                  </div>
                                </div>
                              </div>
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </motion.div>
                    );
                  })
                )}
              </div>
            </div>
          </motion.div>
        </div>
      </PageContainer>
    </AppLayout>
  );
}
