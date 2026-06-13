// src/app/manage-classes/enroll/[courseCode]/page.tsx
"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { motion } from "framer-motion";

import { normalizeErrorMessage, formatDate, formatTime } from "@/lib/utils";

import { Button } from "@/components/ui/button";
import ErrorBanner from "@/components/ErrorBanner";
import EmptyState from "@/components/EmptyState";
import { CardSkeleton, TableSkeleton } from "@/components/LoadingSkeleton";

import AppLayout from "@/components/layout/AppLayout";
import { useLanguage } from "@/hooks/useLanguage";
import PageContainer from "@/components/layout/PageContainer";
import { useAuth } from "@/hooks/useAuth";
import { useTheme } from "@/hooks/useTheme";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

type Schedule = {
  code?: string;
  days?: string;
  time_start?: string;
  time_end?: string;
  room?: string;
  instructor?: string;
};

type CourseSection = {
  section_id: number;
  section_number: number;
  session_type: string;
  status: string;
  total_seats: number;
  enrolled_seats: number;
  available_seats: number;
  start_date?: string;
  end_date?: string;
  lecture?: Schedule;
  tutorial?: Schedule;
  lab?: Schedule;
};

type CourseInfo = {
  code: string;
  title: string;
  description?: string;
  units: number;
  grading_type: string;
  components?: string;
  career: string;
  prerequisites?: string;
};

function EnrollCourseContent() {
  const { t } = useLanguage();
  const router = useRouter();
  const params = useParams();
  const courseCode = params.courseCode as string;
  const { isDark } = useTheme();
  const { token } = useAuth();

  const [course, setCourse] = useState<CourseInfo | null>(null);
  const [sections, setSections] = useState<CourseSection[]>([]);
  const [selectedSectionId, setSelectedSectionId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [enrolling, setEnrolling] = useState(false);

  useEffect(() => {
    if (!courseCode) return;
    if (!token) {
      router.push("/");
      return;
    }
    loadCourseData(courseCode);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [courseCode, token]);

  async function loadCourseData(code: string) {
    setLoading(true);
    setError(null);

    try {
      const res = await fetch(`${API_URL}/courses/${code}/sections`);
      if (!res.ok) throw new Error("Failed to load course");
      const data = await res.json();
      setCourse(data.course);
      setSections(data.sections || []);
    } catch (e) {
      setError(normalizeErrorMessage(e, "Failed to load course"));
    } finally {
      setLoading(false);
    }
  }

  async function handleEnroll() {
    if (!selectedSectionId) {
      alert("Please select a section first");
      return;
    }

    if (!token) {
      router.push("/");
      return;
    }

    setEnrolling(true);

    try {
      const res = await fetch(`${API_URL}/courses/enroll`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ section_id: selectedSectionId }),
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || "Failed to enroll");
      }

      alert("Enrollment successful!");
      router.push("/manage-classes/my-classes");
    } catch (e) {
      alert(normalizeErrorMessage(e, "Failed to enroll"));
    } finally {
      setEnrolling(false);
    }
  }

  function goBack() {
    router.back();
  }

  return (
    <PageContainer>
      <div className="max-w-7xl mx-auto">
        {/* Back Button */}
        <button
          onClick={goBack}
          className={`mb-6 flex items-center gap-2 text-sm font-bold ${
            isDark ? "text-white hover:text-[#B8001F]" : "text-zinc-700 hover:text-[#B8001F]"
          } transition-colors`}
        >
          <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
            <path d="M12 4l-8 8 8 8" stroke="currentColor" strokeWidth="2" fill="none" />
          </svg>
          Back to Requirements
        </button>

        {error && (
          <ErrorBanner message={error} isDark={isDark} onDismiss={() => setError(null)} />
        )}

        {loading && (
          <div className="space-y-4">
            <CardSkeleton />
            <TableSkeleton rows={3} />
          </div>
        )}

        {!loading && course && (
          <>
            {/* Course Header */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.05 }}
              className="mb-8 rounded-2xl bg-[#B8001F] px-6 py-5 shadow-lg hover:shadow-md transition-all duration-200"
            >
              <div className="text-white/80 text-sm font-bold mb-2">{course.code}</div>
              <div className="text-white text-2xl font-extrabold mb-3">{course.title}</div>
            </motion.div>

            {/* Course Information */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className={`mb-8 rounded-2xl ${
                isDark ? "bg-zinc-900 border-zinc-800" : "bg-white border-zinc-200"
              } border shadow-sm px-6 py-6 hover:shadow-md transition-all duration-200`}
            >
              <div className={`text-lg font-extrabold mb-4 ${isDark ? "text-white" : "text-zinc-900"}`}>
                Course Information
              </div>

              {course.description && (
                <p className={`text-sm mb-4 ${isDark ? "text-zinc-300" : "text-zinc-700"}`}>
                  {course.description}
                </p>
              )}

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div>
                  <span className="text-zinc-500">{t("enr.units")}</span>
                  <div className={`font-semibold ${isDark ? "text-white" : "text-zinc-900"}`}>
                    {course.units.toFixed(2)}
                  </div>
                </div>
                <div>
                  <span className="text-zinc-500">{t("enr.grading")}</span>
                  <div className={`font-semibold ${isDark ? "text-white" : "text-zinc-900"}`}>
                    {course.grading_type}
                  </div>
                </div>
                <div>
                  <span className="text-zinc-500">{t("enr.components")}</span>
                  <div className={`font-semibold ${isDark ? "text-white" : "text-zinc-900"}`}>
                    {course.components || "\u2014"}
                  </div>
                </div>
                <div>
                  <span className="text-zinc-500">{t("enr.career")}</span>
                  <div className={`font-semibold ${isDark ? "text-white" : "text-zinc-900"}`}>
                    {course.career}
                  </div>
                </div>
              </div>
            </motion.div>

            {/* Class Selection */}
            <div className="mb-8">
              <div className={`text-lg font-extrabold mb-4 ${isDark ? "text-white" : "text-zinc-900"}`}>
                Class Selection
              </div>

              {sections.length === 0 ? (
                <EmptyState
                  title={t("enr.noSections")}
                  description="No sections are currently available for this course."
                  icon="\ud83c\udf93"
                  isDark={isDark}
                />
              ) : (
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.2 }}
                  className={`rounded-2xl ${
                    isDark ? "bg-zinc-900 border-zinc-800" : "bg-white border-zinc-200"
                  } border shadow-sm overflow-hidden hover:shadow-md transition-all duration-200`}
                >
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead>
                        <tr
                          className={`border-b ${
                            isDark ? "border-zinc-800 bg-zinc-950/40" : "border-zinc-200 bg-[#F5F6FA]"
                          }`}
                        >
                          <th className={`px-6 py-4 text-left text-xs font-bold ${isDark ? "text-zinc-400" : "text-zinc-600"}`}>
                            Option
                          </th>
                          <th className={`px-6 py-4 text-left text-xs font-bold ${isDark ? "text-zinc-400" : "text-zinc-600"}`}>
                            Status
                          </th>
                          <th className={`px-6 py-4 text-left text-xs font-bold ${isDark ? "text-zinc-400" : "text-zinc-600"}`}>
                            Session
                          </th>
                          <th className={`px-6 py-4 text-left text-xs font-bold ${isDark ? "text-zinc-400" : "text-zinc-600"}`}>
                            Class
                          </th>
                          <th className={`px-6 py-4 text-left text-xs font-bold ${isDark ? "text-zinc-400" : "text-zinc-600"}`}>
                            Meeting Dates
                          </th>
                          <th className={`px-6 py-4 text-left text-xs font-bold ${isDark ? "text-zinc-400" : "text-zinc-600"}`}>
                            Days & Times
                          </th>
                          <th className={`px-6 py-4 text-left text-xs font-bold ${isDark ? "text-zinc-400" : "text-zinc-600"}`}>
                            Room
                          </th>
                          <th className={`px-6 py-4 text-left text-xs font-bold ${isDark ? "text-zinc-400" : "text-zinc-600"}`}>
                            Instructor
                          </th>
                          <th className={`px-6 py-4 text-center text-xs font-bold ${isDark ? "text-zinc-400" : "text-zinc-600"}`}>
                            Seats
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {sections.map((section) => {
                          const isSelected = selectedSectionId === section.section_id;
                          const isClosed = section.status === "Closed";
                          const seatStatus = section.available_seats > 0 ? "Opened" : "Closed";

                          return (
                            <tr
                              key={section.section_id}
                              className={`border-b ${
                                isDark ? "border-zinc-800" : "border-zinc-100"
                              } ${isSelected ? (isDark ? "bg-blue-900/20" : "bg-blue-50") : ""} hover:shadow-md transition-all duration-200 cursor-pointer`}
                              onClick={() => !isClosed && setSelectedSectionId(section.section_id)}
                            >
                              <td className="px-6 py-4">
                                <input
                                  type="radio"
                                  name="section"
                                  checked={isSelected}
                                  onChange={() => setSelectedSectionId(section.section_id)}
                                  disabled={isClosed}
                                  className="h-4 w-4 cursor-pointer"
                                />
                              </td>
                              <td className="px-6 py-4">
                                <span
                                  className={`px-2 py-1 rounded-md text-xs font-bold ${
                                    section.status === "Opened"
                                      ? "bg-green-100 text-green-700"
                                      : "bg-red-100 text-red-700"
                                  }`}
                                >
                                  {section.status}
                                </span>
                              </td>
                              <td className={`px-6 py-4 text-sm ${isDark ? "text-zinc-300" : "text-zinc-700"}`}>
                                {section.session_type}
                              </td>
                              <td className="px-6 py-4">
                                {section.lecture && (
                                  <div className={`text-sm ${isDark ? "text-zinc-300" : "text-zinc-700"}`}>
                                    Lecture \u2013 {section.lecture.code}
                                  </div>
                                )}
                                {section.tutorial && (
                                  <div className={`text-sm ${isDark ? "text-zinc-300" : "text-zinc-700"}`}>
                                    Tutorial \u2013 {section.tutorial.code}
                                  </div>
                                )}
                                {section.lab && (
                                  <div className={`text-sm ${isDark ? "text-zinc-300" : "text-zinc-700"}`}>
                                    Lab \u2013 {section.lab.code}
                                  </div>
                                )}
                              </td>
                              <td className={`px-6 py-4 text-sm ${isDark ? "text-zinc-300" : "text-zinc-700"}`}>
                                {formatDate(section.start_date)} \u2013 {formatDate(section.end_date)}
                              </td>
                              <td className="px-6 py-4">
                                {section.lecture && (
                                  <div className={`text-sm ${isDark ? "text-zinc-300" : "text-zinc-700"}`}>
                                    {section.lecture.days} {formatTime(section.lecture.time_start)} \u2013{" "}
                                    {formatTime(section.lecture.time_end)}
                                  </div>
                                )}
                                {section.tutorial && (
                                  <div className={`text-sm ${isDark ? "text-zinc-300" : "text-zinc-700"}`}>
                                    {section.tutorial.days} {formatTime(section.tutorial.time_start)} \u2013{" "}
                                    {formatTime(section.tutorial.time_end)}
                                  </div>
                                )}
                                {section.lab && (
                                  <div className={`text-sm ${isDark ? "text-zinc-300" : "text-zinc-700"}`}>
                                    {section.lab.days} {formatTime(section.lab.time_start)} \u2013{" "}
                                    {formatTime(section.lab.time_end)}
                                  </div>
                                )}
                              </td>
                              <td className="px-6 py-4">
                                {section.lecture && (
                                  <div className={`text-sm ${isDark ? "text-zinc-300" : "text-zinc-700"}`}>
                                    {section.lecture.room}
                                  </div>
                                )}
                                {section.tutorial && (
                                  <div className={`text-sm ${isDark ? "text-zinc-300" : "text-zinc-700"}`}>
                                    {section.tutorial.room}
                                  </div>
                                )}
                                {section.lab && (
                                  <div className={`text-sm ${isDark ? "text-zinc-300" : "text-zinc-700"}`}>
                                    {section.lab.room}
                                  </div>
                                )}
                              </td>
                              <td className={`px-6 py-4 text-sm ${isDark ? "text-zinc-300" : "text-zinc-700"}`}>
                                {section.lecture?.instructor || "staff"}
                              </td>
                              <td className="px-6 py-4 text-center">
                                <span
                                  className={`px-2 py-1 rounded-md text-xs font-bold ${
                                    seatStatus === "Opened"
                                      ? "bg-green-100 text-green-700"
                                      : "bg-red-100 text-red-700"
                                  }`}
                                >
                                  {section.available_seats} / {section.total_seats}
                                </span>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </motion.div>
              )}
            </div>

            {/* Enroll Button */}
            {sections.length > 0 && (
              <div className="flex justify-end">
                <Button
                  onClick={handleEnroll}
                  disabled={!selectedSectionId || enrolling}
                  className={`bg-[#1E3A8A] hover:bg-[#193276] text-white rounded-full h-12 px-8 text-sm font-bold ${
                    !selectedSectionId || enrolling ? "opacity-50 cursor-not-allowed" : ""
                  }`}
                  type="button"
                >
                  {enrolling ? "Enrolling..." : "Enroll Selected Option"}
                </Button>
              </div>
            )}
          </>
        )}
      </div>
    </PageContainer>
  );
}

export default function EnrollCoursePage() {
  return (
    <AppLayout activePath="/manage-classes/enroll" userName="Loading...">
      <EnrollCourseContent />
    </AppLayout>
  );
}
