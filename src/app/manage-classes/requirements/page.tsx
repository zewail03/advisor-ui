// src/app/manage-classes/requirements/page.tsx
"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import { motion, AnimatePresence } from "framer-motion";

import { getMe, getMyRequirements, type MeResponse } from "@/lib/api";
import { normalizeErrorMessage, isAbortError } from "@/lib/utils";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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

type Course = {
  code: string;
  title: string;
  units: number;
  is_required: boolean;
  taken: boolean;
  grade?: string;
  term?: string;
};

type Requirement = {
  requirement_id: string;
  category: string;
  total_units_required: number;
  units_completed: number;
  units_in_progress: number;
  completion_percentage: number;
  status: string;
  is_core: boolean;
  courses: Course[];
};

/* ── Helpers ───────────────────────────────────────────── */

function getStatusColor(status: string): string {
  if (status === "Satisfied") return "bg-green-100 text-green-700 border-green-200";
  if (status === "In Progress") return "bg-orange-100 text-orange-700 border-orange-200";
  return "bg-zinc-100 text-zinc-600 border-zinc-200";
}

/* ── Page component ────────────────────────────────────── */

export default function RequirementsPage() {
  const { t } = useLanguage();
  const { isDark } = useTheme();
  const { token, signOut } = useAuth();

  const [summary, setSummary] = useState<MeResponse | null>(null);
  const [requirements, setRequirements] = useState<Requirement[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [expandedReqs, setExpandedReqs] = useState<Set<string>>(new Set());
  const [searchQuery, setSearchQuery] = useState("");

  /* ── Data fetching ─────────────────────────────────── */

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

    loadRequirements(token);

    return () => controller.abort();
  }, [token, signOut]);

  async function loadRequirements(tkn: string) {
    setLoading(true);
    setError(null);

    try {
      const data = await getMyRequirements(tkn);
      const mapped: Requirement[] = (data.requirements || []).map((r: any) => {
        const status = r.satisfied
          ? "Satisfied"
          : r.units_completed > 0
            ? "In Progress"
            : "Not Started";
        return {
          requirement_id: String(r.requirement_id),
          category: r.category,
          total_units_required: r.total_units_required,
          units_completed: r.units_completed,
          units_in_progress: r.units_in_progress ?? 0,
          completion_percentage: r.completion_percentage,
          status,
          is_core: r.is_core,
          courses: (r.courses || []).map((c: any) => ({
            code: c.code,
            title: c.title,
            units: c.units,
            is_required: c.is_required,
            taken: c.taken,
            grade: c.grade ?? undefined,
            term: c.semester ?? undefined,
          })),
        };
      });
      setRequirements(mapped);
    } catch (e) {
      const msg = normalizeErrorMessage(e, "Failed to load requirements");
      if (msg.toLowerCase().includes("unauthorized") || msg.toLowerCase().includes("invalid token")) {
        signOut();
        return;
      }
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  /* ── Expand / collapse ─────────────────────────────── */

  function toggleRequirement(reqId: string) {
    setExpandedReqs((prev) => {
      const next = new Set(prev);
      if (next.has(reqId)) {
        next.delete(reqId);
      } else {
        next.add(reqId);
      }
      return next;
    });
  }

  /* ── Filtered list ─────────────────────────────────── */

  const filteredRequirements = requirements.filter((req) => {
    if (!searchQuery) return true;
    const searchLower = searchQuery.toLowerCase();
    return (
      req.category.toLowerCase().includes(searchLower) ||
      req.courses.some(
        (c) => c.code.toLowerCase().includes(searchLower) || c.title.toLowerCase().includes(searchLower)
      )
    );
  });

  /* ── Render ────────────────────────────────────────── */

  return (
    <AppLayout activePath="/manage-classes/requirements" userName={summary?.full_name ?? "Loading..."}>
      <PageContainer>
        <ManageClassesSubNav activePath="/manage-classes/requirements" isDark={isDark} />

        {error && (
          <ErrorBanner message={error} isDark={isDark} onDismiss={() => setError(null)} />
        )}

        {/* Quick Search */}
        <div className={`mb-8 rounded-2xl ${isDark ? "bg-zinc-900 border-zinc-800" : "bg-white border-zinc-200"} border shadow-sm px-6 py-6`}>
          <div className={`text-xl font-extrabold mb-3 italic ${isDark ? "text-white" : "text-zinc-900"}`}>
            Quick Search
          </div>
          <div className="text-sm text-zinc-500 mb-4">{t("req.find")}</div>
          <div className="flex items-center gap-3">
            <div className="relative flex-1">
              <span className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2">
                <Image
                  src="/search.svg"
                  alt="search"
                  width={16}
                  height={16}
                  className={isDark ? "brightness-0 invert" : ""}
                />
              </span>
              <Input
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder={t("req.search")}
                className={`h-12 w-full rounded-lg pl-11 text-sm ${
                  isDark ? "bg-zinc-800 border-zinc-700 text-white placeholder:text-zinc-500" : "bg-white"
                }`}
              />
            </div>
            <Button
              className="bg-[#B8001F] hover:bg-[#A0001A] text-white rounded-lg h-12 px-8 text-sm font-bold"
              type="button"
            >
              Search Courses
            </Button>
          </div>
        </div>

        {loading && (
          <div className="space-y-4">
            <CardSkeleton />
            <CardSkeleton />
            <CardSkeleton />
            <CardSkeleton />
          </div>
        )}

        {/* My Requirements List */}
        {!loading && (
          <div className="mb-8">
            <div className={`text-2xl font-extrabold mb-6 ${isDark ? "text-white" : "text-zinc-900"}`}>
              My Requirements
            </div>

            {filteredRequirements.length === 0 && (
              <EmptyState
                title={t("req.none")}
                description="Degree requirements will appear here."
                icon="📋"
                isDark={isDark}
              />
            )}

            {filteredRequirements.map((req, idx) => {
              const isExpanded = expandedReqs.has(req.requirement_id);
              const statusColor = getStatusColor(req.status);

              return (
                <motion.div
                  key={req.requirement_id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: idx * 0.08 }}
                  className={`mb-4 rounded-xl ${
                    isDark ? "bg-zinc-900 border-zinc-800" : "bg-white border-zinc-200"
                  } border shadow-sm overflow-hidden hover:shadow-md transition-all duration-200`}
                >
                  {/* Requirement Header */}
                  <div
                    className={`px-6 py-5 cursor-pointer ${isDark ? "hover:bg-zinc-800" : "hover:bg-zinc-50"}`}
                    onClick={() => toggleRequirement(req.requirement_id)}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-3">
                          <div className={`font-extrabold text-base ${isDark ? "text-white" : "text-zinc-900"}`}>
                            {req.category}
                          </div>
                          <span className={`px-3 py-1 rounded-full text-xs font-bold border ${statusColor}`}>
                            {req.status}
                          </span>
                        </div>

                        {/* Progress Bar */}
                        <div className="mb-2">
                          <div className="flex items-center justify-between mb-1 text-xs">
                            <span className="text-zinc-500">
                              {req.units_completed.toFixed(0)} / {req.total_units_required.toFixed(0)} Credits Completed
                            </span>
                            <span className="font-bold text-green-600">{req.completion_percentage.toFixed(0)}%</span>
                          </div>
                          <div className={`h-2 rounded-full overflow-hidden ${isDark ? "bg-zinc-800" : "bg-zinc-200"}`}>
                            <div
                              className="h-full bg-green-600 transition-all duration-500"
                              style={{ width: `${Math.min(req.completion_percentage, 100)}%` }}
                            />
                          </div>
                        </div>

                        <div className="text-xs text-zinc-500">
                          Units: {req.total_units_required.toFixed(0)} required / {req.units_completed.toFixed(0)} satisfied / 0.00 needed
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

                  {/* Expanded Course Table */}
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
                          {req.courses.length === 0 ? (
                            <div className="py-8 text-center text-sm text-zinc-500">
                              No courses in this category
                            </div>
                          ) : (
                            <div className="overflow-x-auto">
                              <table className="w-full">
                                <thead>
                                  <tr className={`border-b ${isDark ? "border-zinc-800" : "border-zinc-200"}`}>
                                    <th className={`text-left py-3 text-xs font-bold ${isDark ? "text-zinc-400" : "text-zinc-600"}`}>
                                      Course
                                    </th>
                                    <th className={`text-left py-3 text-xs font-bold ${isDark ? "text-zinc-400" : "text-zinc-600"}`}>
                                      Description
                                    </th>
                                    <th className={`text-center py-3 text-xs font-bold ${isDark ? "text-zinc-400" : "text-zinc-600"}`}>
                                      Units
                                    </th>
                                    <th className={`text-center py-3 text-xs font-bold ${isDark ? "text-zinc-400" : "text-zinc-600"}`}>
                                      Term
                                    </th>
                                    <th className={`text-center py-3 text-xs font-bold ${isDark ? "text-zinc-400" : "text-zinc-600"}`}>
                                      Grade
                                    </th>
                                    <th className={`text-center py-3 text-xs font-bold ${isDark ? "text-zinc-400" : "text-zinc-600"}`}>
                                      Status
                                    </th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {req.courses.map((course, cidx) => (
                                    <tr
                                      key={`${course.code}-${cidx}`}
                                      className={`border-b ${isDark ? "border-zinc-800 hover:bg-zinc-900" : "border-zinc-100 hover:bg-white"}`}
                                    >
                                      <td className={`py-3 text-sm font-bold ${isDark ? "text-white" : "text-zinc-900"}`}>
                                        {course.code}
                                      </td>
                                      <td className={`py-3 text-sm ${isDark ? "text-zinc-300" : "text-zinc-700"}`}>
                                        {course.title}
                                      </td>
                                      <td className={`py-3 text-sm text-center ${isDark ? "text-zinc-300" : "text-zinc-700"}`}>
                                        {course.units.toFixed(2)}
                                      </td>
                                      <td className={`py-3 text-sm text-center ${isDark ? "text-zinc-300" : "text-zinc-700"}`}>
                                        {course.term || "\u2014"}
                                      </td>
                                      <td className="py-3 text-sm text-center">
                                        {course.taken && course.grade ? (
                                          <span className="px-2 py-1 rounded-md bg-green-100 text-green-700 text-xs font-bold">
                                            {course.grade}
                                          </span>
                                        ) : (
                                          <span className="text-zinc-400">\u2014</span>
                                        )}
                                      </td>
                                      <td className="py-3 text-sm text-center">
                                        {course.taken ? (
                                          <span className="text-green-600 font-bold text-xs">{"\u2713"} Taken</span>
                                        ) : (
                                          <span className="px-2 py-1 rounded-md bg-blue-100 text-blue-700 text-xs font-bold">
                                            Requirements
                                          </span>
                                        )}
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          )}
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </motion.div>
              );
            })}
          </div>
        )}
      </PageContainer>
    </AppLayout>
  );
}
