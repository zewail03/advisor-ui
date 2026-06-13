// src/app/manage-classes/my-classes/page.tsx
"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

import { getMe, getMySchedule, dropEnrollment, type MeResponse } from "@/lib/api";
import { normalizeErrorMessage, isAbortError, formatDate, formatTime, getDaysUntilDeadline } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import ErrorBanner from "@/components/ErrorBanner";
import EmptyState from "@/components/EmptyState";
import { CardSkeleton } from "@/components/LoadingSkeleton";
import AppLayout from "@/components/layout/AppLayout";
import { useLanguage } from "@/hooks/useLanguage";
import PageContainer from "@/components/layout/PageContainer";
import ManageClassesSubNav from "@/components/layout/ManageClassesSubNav";
import { useAuth } from "@/hooks/useAuth";
import { useTheme } from "@/hooks/useTheme";

/* ── Types ─────────────────────────────────────────────── */

type ClassSchedule = {
  code?: string;
  days?: string;
  time_start?: string;
  time_end?: string;
  room?: string;
  instructor?: string;
};

type EnrolledClass = {
  enrollment_id: string;
  course_code: string;
  course_title: string;
  units: number;
  section_number: number | string;
  term: string;
  status: string;
  start_date?: string;
  end_date?: string;
  lecture?: ClassSchedule;
  tutorial?: ClassSchedule;
  lab?: ClassSchedule;
  schedules?: Array<{
    days: string;
    start_time: string;
    end_time: string;
    room?: string;
    instructor?: string;
    component?: string;
  }>;
};

type EnrollmentStats = {
  enrolled_classes: number;
  units_completed: number;
  completion_percentage: number;
  available_to_enroll: number;
  enrollment_deadline?: string;
};

/* ── Helpers ───────────────────────────────────────────── */



function buildSchedules(cls: EnrolledClass) {
  const schedules: EnrolledClass["schedules"] = [];

  if (cls.lecture) {
    schedules.push({
      days: cls.lecture.days || "",
      start_time: cls.lecture.time_start || "",
      end_time: cls.lecture.time_end || "",
      room: cls.lecture.room || "",
      instructor: cls.lecture.instructor || "",
      component: "Lecture",
    });
  }

  if (cls.tutorial) {
    schedules.push({
      days: cls.tutorial.days || "",
      start_time: cls.tutorial.time_start || "",
      end_time: cls.tutorial.time_end || "",
      room: cls.tutorial.room || "",
      instructor: cls.tutorial.instructor || "",
      component: "Tutorial",
    });
  }

  if (cls.lab) {
    schedules.push({
      days: cls.lab.days || "",
      start_time: cls.lab.time_start || "",
      end_time: cls.lab.time_end || "",
      room: cls.lab.room || "",
      instructor: cls.lab.instructor || "",
      component: "Laboratory",
    });
  }

  return schedules;
}

/* ── Page Component ────────────────────────────────────── */

export default function MyClassesPage() {
  const { t } = useLanguage();
  const { isDark } = useTheme();
  const { token, signOut } = useAuth();

  const [summary, setSummary] = useState<MeResponse | null>(null);
  const [tableView, setTableView] = useState(false);

  const [classes, setClasses] = useState<EnrolledClass[]>([]);
  const [stats, setStats] = useState<EnrollmentStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [expandedClasses, setExpandedClasses] = useState<Set<string>>(new Set());
  const [dropModalOpen, setDropModalOpen] = useState(false);
  const [classToDropId, setClassToDropId] = useState<string | null>(null);
  const [classToDropName, setClassToDropName] = useState<string>("");

  /* ── Data fetching ──────────────────────────────────── */

  useEffect(() => {
    if (!token) return;
    const controller = new AbortController();

    getMe(token, controller.signal)
      .then((d) => {
        if (!controller.signal.aborted) setSummary(d);
      })
      .catch((e) => {
        if (isAbortError(e) || controller.signal.aborted) return;
        const msg = normalizeErrorMessage(e, "Failed to load summary");
        if (msg.toLowerCase().includes("unauthorized") || msg.toLowerCase().includes("invalid token")) {
          signOut();
        }
      });

    loadData(token);

    return () => controller.abort();
  }, [token, signOut]);

  async function loadData(tkn: string) {
    setLoading(true);
    setError(null);

    try {
      const sched = await getMySchedule(tkn);
      const transformedClasses: EnrolledClass[] = (sched.schedule || []).map((e: any) => {
        const lecture: ClassSchedule = {
          days: e.days || "",
          time_start: e.time_start || "",
          time_end: e.time_end || "",
          room: e.room || "",
          instructor: e.instructor || "",
        };
        const cls: EnrolledClass = {
          enrollment_id: String(e.enrollment_id),
          course_code: e.course_code,
          course_title: e.course_title,
          units: e.credits ?? 0,
          section_number: e.section_number,
          term: e.semester,
          status: e.status,
          lecture,
        };
        cls.schedules = buildSchedules(cls);
        return cls;
      });

      setClasses(transformedClasses);

      const totalUnits = transformedClasses.reduce((sum, c) => sum + (c.units || 0), 0);
      setStats({
        enrolled_classes: transformedClasses.length,
        units_completed: totalUnits,
        completion_percentage: 0,
        available_to_enroll: 0,
      });
    } catch (e) {
      if ((e as any)?.message?.toLowerCase?.().includes("unauthorized")) {
        signOut();
        return;
      }
      setError(normalizeErrorMessage(e, "Failed to load data"));
    } finally {
      setLoading(false);
    }
  }

  /* ── Actions ────────────────────────────────────────── */

  function toggleClass(enrollmentId: string) {
    setExpandedClasses((prev) => {
      const next = new Set(prev);
      if (next.has(enrollmentId)) {
        next.delete(enrollmentId);
      } else {
        next.add(enrollmentId);
      }
      return next;
    });
  }

  function openDropModal(enrollmentId: string, courseName: string) {
    setClassToDropId(enrollmentId);
    setClassToDropName(courseName);
    setDropModalOpen(true);
  }

  async function confirmDrop() {
    if (!classToDropId || !token) return;

    try {
      await dropEnrollment(token, classToDropId);
      await loadData(token);
      setDropModalOpen(false);
      setClassToDropId(null);
    } catch (e) {
      const msg = normalizeErrorMessage(e, "Failed to drop class");
      if (msg.toLowerCase().includes("unauthorized") || msg.toLowerCase().includes("invalid token")) {
        signOut();
        return;
      }
      alert(msg);
    }
  }

  function handlePrint() {
    if (!tableView) {
      setTableView(true);
      setTimeout(() => {
        window.print();
      }, 100);
    } else {
      window.print();
    }
  }

  const daysUntilDeadline = getDaysUntilDeadline(stats?.enrollment_deadline);

  /* ── Render ─────────────────────────────────────────── */

  return (
    <AppLayout activePath="/manage-classes/my-classes" userName={summary?.full_name ?? "Loading..."}>
      {/* Print Styles */}
      <style jsx global>{`
        @media print {
          @page {
            size: landscape;
            margin: 0.5cm;
          }

          body {
            background: white !important;
          }

          header, footer, nav, .no-print {
            display: none !important;
          }

          .print-timetable {
            display: block !important;
            background: white !important;
            color: black !important;
          }

          table {
            page-break-inside: avoid;
            border-collapse: collapse;
          }

          td, th {
            border: 1px solid #ccc !important;
            padding: 8px !important;
          }

          .bg-\\[\\#B8001F\\] {
            background: #B8001F !important;
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
          }
        }
      `}</style>

      <PageContainer>
        <ManageClassesSubNav activePath="/manage-classes/my-classes" isDark={isDark} />

        {error && (
          <ErrorBanner message={error} isDark={isDark} onDismiss={() => setError(null)} />
        )}

        {/* Stats Cards */}
        {stats && (
          <div className="mb-8 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="rounded-xl bg-[#2E3F8F] px-6 py-5 shadow-sm hover:shadow-md transition-all duration-200"
            >
              <div className="text-white/90 text-sm font-bold mb-3">{t("cls.enrolled")}</div>
              <div className="text-white text-[32px] font-extrabold leading-none mb-2">
                {classes.length}
              </div>
              <div className="text-white/90 text-sm font-semibold flex items-center gap-1">
                <span className="text-green-400">✓</span> {classes.reduce((sum, cls) => sum + cls.units, 0).toFixed(0)} Credits
              </div>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="rounded-xl bg-[#2E3F8F] px-6 py-5 shadow-sm hover:shadow-md transition-all duration-200"
            >
              <div className="text-white/90 text-sm font-bold mb-3">{t("cls.units")}</div>
              <div className="text-white text-[32px] font-extrabold leading-none mb-2">
                {stats?.completion_percentage || 0}%
              </div>
              <div className="text-white/90 text-sm font-semibold">
                / {stats?.units_completed || 0} Units
              </div>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
              className="rounded-xl bg-[#2E3F8F] px-6 py-5 shadow-sm hover:shadow-md transition-all duration-200"
            >
              <div className="text-white/90 text-sm font-bold mb-3">{t("cls.avail")}</div>
              <div className="text-white text-[32px] font-extrabold leading-none mb-2">
                {stats?.available_to_enroll || 0}
              </div>
              <div className="text-white/90 text-sm font-semibold">
                Classes
              </div>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4 }}
              className="rounded-xl bg-[#2E3F8F] px-6 py-5 shadow-sm hover:shadow-md transition-all duration-200"
            >
              <div className="text-white/90 text-sm font-bold mb-3">{t("cls.deadline")}</div>
              <div className="text-white text-[32px] font-extrabold leading-none">
                {daysUntilDeadline !== null ? `${daysUntilDeadline} days` : "—"}
              </div>
            </motion.div>
          </div>
        )}

        {/* Current Enrollment Section */}
        <div className="mb-8">
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div
                className="px-4 py-2 rounded-full text-sm font-bold bg-[#B8001F] text-white"
              >
                <span className="mr-2">⚫</span>
                Fall 2025-2026 • Undergraduate
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setTableView(!tableView)}
                className={`p-2 rounded-lg transition-colors ${
                  tableView
                    ? "bg-[#B8001F] text-white"
                    : isDark ? "hover:bg-zinc-800 text-zinc-300" : "hover:bg-zinc-100 text-zinc-600"
                }`}
                title={tableView ? "Switch to Card View" : "Switch to Table View"}
              >
                📅
              </button>
              <button
                onClick={handlePrint}
                className={`p-2 rounded-lg transition-colors ${
                  isDark ? "hover:bg-zinc-800 text-zinc-300" : "hover:bg-zinc-100 text-zinc-600"
                }`}
                title={t("cls.print")}
              >
                🖨️
              </button>
            </div>
          </div>

          {loading && (
            <div className="space-y-4">
              <CardSkeleton />
              <CardSkeleton />
              <CardSkeleton />
            </div>
          )}

          {!loading && classes.length === 0 && (
            <EmptyState
              title={t("cls.none")}
              description="You haven't enrolled in any classes yet."
              icon="📚"
              isDark={isDark}
            />
          )}

          {/* Weekly Timetable View */}
          {!loading && tableView && classes.length > 0 && (
            <div className={`print-timetable rounded-xl border ${
              isDark ? "bg-zinc-900 border-zinc-800" : "bg-white border-zinc-200"
            } shadow-sm overflow-hidden`}>
              <div className={`px-6 py-4 border-b ${isDark ? "border-zinc-800" : "border-zinc-200"}`}>
                <h2 className={`text-xl font-bold ${isDark ? "text-white" : "text-zinc-900"}`}>
                  Weekly Timetable
                </h2>
                <p className={`text-sm ${isDark ? "text-zinc-400" : "text-zinc-600"}`}>
                  Your class schedule for the week
                </p>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full border-collapse">
                  <thead>
                    <tr className={isDark ? "bg-zinc-800" : "bg-zinc-50"}>
                      <th className={`sticky left-0 z-10 px-4 py-3 text-left text-sm font-bold border-r ${
                        isDark ? "bg-zinc-800 border-zinc-700 text-white" : "bg-zinc-50 border-zinc-200 text-zinc-900"
                      }`}>
                        Time
                      </th>
                      {["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"].map((day) => (
                        <th
                          key={day}
                          className={`px-4 py-3 text-center text-sm font-bold border-r ${
                            isDark ? "border-zinc-700 text-white" : "border-zinc-200 text-zinc-900"
                          }`}
                        >
                          {day}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {(() => {
                      const timeSlots = [];
                      for (let hour = 9; hour <= 16; hour++) {
                        const time12 = hour > 12 ? hour - 12 : hour;
                        const ampm = hour >= 12 ? "PM" : "AM";
                        const displayTime = `${time12}:00 ${ampm}`;
                        timeSlots.push({ hour, display: displayTime });
                      }

                      const getClassAtTimeAndDay = (hour: number, dayName: string) => {
                        for (const cls of classes) {
                          if (!cls.schedules) continue;
                          for (const sched of cls.schedules) {
                            if (!sched.days || !sched.start_time) continue;

                            let schedHour: number | null = null;

                            const ampmMatch = sched.start_time.match(/(\d+):(\d+)\s*(AM|PM)/i);
                            const h24Match = sched.start_time.match(/^(\d+):(\d+)(?::(\d+))?$/);

                            if (ampmMatch) {
                              schedHour = parseInt(ampmMatch[1]);
                              const ap = ampmMatch[3].toUpperCase();
                              if (ap === "PM" && schedHour !== 12) schedHour += 12;
                              if (ap === "AM" && schedHour === 12) schedHour = 0;
                            } else if (h24Match) {
                              schedHour = parseInt(h24Match[1]);
                            }

                            if (schedHour === null) continue;

                            const dayAbbrev = dayName.substring(0, 3);
                            const dayMatches =
                              sched.days.toLowerCase().includes(dayName.toLowerCase()) ||
                              sched.days.toLowerCase().includes(dayAbbrev.toLowerCase());

                            if (dayMatches && schedHour === hour) {
                              return { cls, sched };
                            }
                          }
                        }
                        return null;
                      };

                      return timeSlots.map(({ hour, display }) => (
                        <tr
                          key={hour}
                          className={`border-b ${isDark ? "border-zinc-800" : "border-zinc-200"}`}
                        >
                          <td className={`sticky left-0 z-10 px-4 py-4 text-sm font-medium border-r ${
                            isDark ? "bg-zinc-900 border-zinc-700 text-zinc-300" : "bg-white border-zinc-200 text-zinc-600"
                          }`}>
                            {display}
                          </td>
                          {["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"].map((day) => {
                            const classInfo = getClassAtTimeAndDay(hour, day);

                            return (
                              <td
                                key={day}
                                className={`px-2 py-2 text-sm border-r ${
                                  isDark ? "border-zinc-700" : "border-zinc-200"
                                } ${classInfo ? (isDark ? "bg-[#B8001F]/20" : "bg-[#FFE4E1]") : ""}`}
                              >
                                {classInfo && (
                                  <div className="p-2 rounded-lg bg-[#B8001F] text-white">
                                    <div className="font-bold text-xs mb-1">
                                      {classInfo.cls.course_code}
                                    </div>
                                    <div className="text-[10px] opacity-90">
                                      {classInfo.cls.course_title}
                                    </div>
                                    <div className="text-[10px] opacity-75 mt-1">
                                      {classInfo.sched.room || "Room TBA"}
                                    </div>
                                    <div className="text-[10px] opacity-75">
                                      {classInfo.sched.component || "Lecture"}
                                    </div>
                                  </div>
                                )}
                              </td>
                            );
                          })}
                        </tr>
                      ));
                    })()}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Card View */}
          {!loading && !tableView &&
            classes.map((cls, idx) => {
              const isExpanded = expandedClasses.has(cls.enrollment_id);

              return (
                <motion.div
                  key={cls.enrollment_id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: idx * 0.08 }}
                  className={`mb-4 rounded-xl ${
                    isDark ? "bg-zinc-900 border-zinc-800" : "bg-white border-zinc-200"
                  } border shadow-sm overflow-hidden hover:shadow-md transition-all duration-200`}
                >
                  {/* Class Header */}
                  <div
                    className={`px-6 py-4 cursor-pointer ${isDark ? "hover:bg-zinc-800" : "hover:bg-zinc-50"}`}
                    onClick={() => toggleClass(cls.enrollment_id)}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                          <div className={`font-bold text-base ${isDark ? "text-white" : "text-zinc-900"}`}>
                            {cls.course_code} / {cls.course_code}
                          </div>
                          <span
                            className="px-3 py-1 rounded-full text-xs font-bold"
                            style={{ backgroundColor: "#F59E0B", color: "white" }}
                          >
                            {cls.units.toFixed(2)} Units
                          </span>
                        </div>
                        <div className={`text-sm font-semibold mb-2 ${isDark ? "text-zinc-300" : "text-zinc-700"}`}>
                          {cls.course_title}
                        </div>
                        <div className="flex items-center gap-4 text-xs text-zinc-500">
                          {cls.lecture && (
                            <span>
                              {cls.lecture.days} {formatTime(cls.lecture.time_start)} –{" "}
                              {formatTime(cls.lecture.time_end)}
                            </span>
                          )}
                          <span>
                            {formatDate(cls.start_date)} – {formatDate(cls.end_date)}
                          </span>
                        </div>
                      </div>
                      <motion.div
                        animate={{ rotate: isExpanded ? 180 : 0 }}
                        transition={{ duration: 0.2 }}
                        className="ml-4"
                      >
                        <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor" className="text-zinc-400">
                          <path d="M5 7l5 5 5-5" stroke="currentColor" strokeWidth="2" fill="none" />
                        </svg>
                      </motion.div>
                    </div>
                  </div>

                  {/* Expanded Details */}
                  <AnimatePresence>
                    {isExpanded && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.3 }}
                        className="overflow-hidden"
                      >
                        <div className={`px-6 pb-6 ${isDark ? "bg-zinc-950/40" : "bg-zinc-50"}`}>
                          {/* Lecture */}
                          {cls.lecture && (
                            <div className="mb-4">
                              <div className="text-xs font-bold text-zinc-500 mb-2">Lecture – {cls.lecture.code}</div>
                              <div className="grid grid-cols-2 gap-4 text-sm">
                                <div>
                                  <span className="text-zinc-500">{t("cls.room")}</span>
                                  <div className={`font-semibold ${isDark ? "text-white" : "text-zinc-900"}`}>
                                    {cls.lecture.room || "—"}
                                  </div>
                                </div>
                                <div>
                                  <span className="text-zinc-500">{t("cls.time")}</span>
                                  <div className={`font-semibold ${isDark ? "text-white" : "text-zinc-900"}`}>
                                    {cls.lecture.days} {formatTime(cls.lecture.time_start)} –{" "}
                                    {formatTime(cls.lecture.time_end)}
                                  </div>
                                </div>
                              </div>
                            </div>
                          )}

                          {/* Tutorial */}
                          {cls.tutorial && (
                            <div className="mb-4">
                              <div className="text-xs font-bold text-zinc-500 mb-2">Tutorial – {cls.tutorial.code}</div>
                              <div className="grid grid-cols-2 gap-4 text-sm">
                                <div>
                                  <span className="text-zinc-500">{t("cls.room")}</span>
                                  <div className={`font-semibold ${isDark ? "text-white" : "text-zinc-900"}`}>
                                    {cls.tutorial.room || "—"}
                                  </div>
                                </div>
                                <div>
                                  <span className="text-zinc-500">{t("cls.time")}</span>
                                  <div className={`font-semibold ${isDark ? "text-white" : "text-zinc-900"}`}>
                                    {cls.tutorial.days} {formatTime(cls.tutorial.time_start)} –{" "}
                                    {formatTime(cls.tutorial.time_end)}
                                  </div>
                                </div>
                              </div>
                            </div>
                          )}

                          {/* Laboratory */}
                          {cls.lab && (
                            <div className="mb-4">
                              <div className="text-xs font-bold text-zinc-500 mb-2">Laboratory – {cls.lab.code}</div>
                              <div className="grid grid-cols-2 gap-4 text-sm">
                                <div>
                                  <span className="text-zinc-500">{t("cls.lab")}</span>
                                  <div className={`font-semibold ${isDark ? "text-white" : "text-zinc-900"}`}>
                                    {cls.lab.room || "—"}
                                  </div>
                                </div>
                                <div>
                                  <span className="text-zinc-500">{t("cls.time")}</span>
                                  <div className={`font-semibold ${isDark ? "text-white" : "text-zinc-900"}`}>
                                    {cls.lab.days} {formatTime(cls.lab.time_start)} – {formatTime(cls.lab.time_end)}
                                  </div>
                                </div>
                              </div>
                            </div>
                          )}

                          {/* Action Buttons */}
                          <div className="flex items-center gap-3 mt-6">
                            <Button
                              className="bg-[#1E3A8A] hover:bg-[#193276] text-white rounded-full h-10 px-6 text-sm font-bold"
                              type="button"
                            >
                              View Syllabus
                            </Button>
                            <Button
                              variant="outline"
                              className={`rounded-full h-10 px-6 text-sm font-bold ${
                                isDark ? "border-zinc-700 text-white hover:bg-zinc-800" : "border-zinc-300"
                              }`}
                              type="button"
                            >
                              Email Instructor
                            </Button>
                            <Button
                              onClick={() => openDropModal(cls.enrollment_id, cls.course_title)}
                              className="bg-[#B8001F] hover:bg-[#A0001A] text-white rounded-full h-10 px-6 text-sm font-bold"
                              type="button"
                            >
                              Drop Class
                            </Button>
                          </div>
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </motion.div>
              );
            })}
        </div>
      </PageContainer>

      {/* Drop Confirmation Modal */}
      <AnimatePresence>
        {dropModalOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-black/50 z-50"
              onClick={() => setDropModalOpen(false)}
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.9 }}
              className="fixed inset-0 z-50 flex items-center justify-center p-4"
            >
              <div
                className={`w-full max-w-md rounded-2xl ${
                  isDark ? "bg-zinc-900 border-zinc-800" : "bg-white"
                } border shadow-2xl p-6`}
              >
                <h3 className={`text-xl font-bold mb-3 ${isDark ? "text-white" : "text-zinc-900"}`}>
                  Drop Class?
                </h3>
                <p className={`text-sm mb-6 ${isDark ? "text-zinc-300" : "text-zinc-600"}`}>
                  Are you sure you want to drop <span className="font-bold">{classToDropName}</span>? This action
                  cannot be undone.
                </p>
                <div className="flex items-center gap-3">
                  <Button
                    onClick={() => setDropModalOpen(false)}
                    variant="outline"
                    className={`flex-1 rounded-full h-11 font-bold ${
                      isDark ? "border-zinc-700 text-white hover:bg-zinc-800" : ""
                    }`}
                  >
                    Cancel
                  </Button>
                  <Button
                    onClick={confirmDrop}
                    className="flex-1 bg-[#B8001F] hover:bg-[#A0001A] text-white rounded-full h-11 font-bold"
                  >
                    Drop Class
                  </Button>
                </div>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </AppLayout>
  );
}
