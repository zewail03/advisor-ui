// src/app/manage-classes/requirements/page.tsx
"use client";

import { useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Check, Diamond, ChevronRight, Loader2 } from "lucide-react";

import {
  getMe,
  getMyRequirementsTree,
  type MeResponse,
  type RequirementTree,
  type ReqSemester,
  type ReqSubrequirement,
  type ReqTreeCourse,
} from "@/lib/api";
import { normalizeErrorMessage, isAbortError } from "@/lib/utils";

import ErrorBanner from "@/components/ErrorBanner";
import EmptyState from "@/components/EmptyState";
import { CardSkeleton } from "@/components/LoadingSkeleton";

import AppLayout from "@/components/layout/AppLayout";
import { useLanguage } from "@/hooks/useLanguage";
import PageContainer from "@/components/layout/PageContainer";
import ManageClassesSubNav from "@/components/layout/ManageClassesSubNav";
import { useAuth } from "@/hooks/useAuth";
import { useTheme } from "@/hooks/useTheme";

/* ── Small presentational pieces ───────────────────────── */

function StatusPill({ satisfied, isDark }: { satisfied: boolean; isDark: boolean }) {
  if (satisfied) {
    return (
      <span className="inline-flex items-center gap-1 text-[13px] font-semibold text-green-600">
        <span className="flex h-4 w-4 items-center justify-center rounded-full bg-green-600">
          <Check size={11} strokeWidth={3} className="text-white" />
        </span>
        Satisfied
      </span>
    );
  }
  return (
    <span className={`inline-flex items-center gap-1 text-[13px] font-semibold ${isDark ? "text-amber-400" : "text-amber-500"}`}>
      <Diamond size={13} strokeWidth={3} className="fill-amber-500 text-amber-500" />
      Not Satisfied
    </span>
  );
}

function ProgressMeter({
  label,
  pct,
  isDark,
}: {
  label: string;
  pct: number;
  isDark: boolean;
}) {
  const clamped = Math.max(0, Math.min(100, pct));
  return (
    <div className="flex items-center gap-4">
      <span className={`whitespace-nowrap text-xs ${isDark ? "text-zinc-400" : "text-zinc-500"}`}>
        {label} {pct.toFixed(0)}%
      </span>
      <div className="w-40 shrink-0">
        <div className={`h-2 rounded-sm ${isDark ? "bg-zinc-800" : "bg-zinc-200"}`}>
          <div className="h-full rounded-sm bg-green-600 transition-all duration-500" style={{ width: `${clamped}%` }} />
        </div>
        <div className="mt-0.5 flex justify-between text-[9px] text-zinc-400">
          <span>0%</span>
          <span>100%</span>
        </div>
      </div>
    </div>
  );
}

/* ── Course row + detail ───────────────────────────────── */

function CourseRow({ course, isDark }: { course: ReqTreeCourse; isDark: boolean }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <tr
        className={`cursor-pointer border-b ${isDark ? "border-zinc-800 hover:bg-zinc-900" : "border-zinc-100 hover:bg-white"}`}
        onClick={() => course.description && setOpen((o) => !o)}
      >
        <td className={`py-2.5 pl-2 text-sm font-bold ${isDark ? "text-white" : "text-zinc-900"}`}>{course.code}</td>
        <td className={`py-2.5 text-sm ${isDark ? "text-zinc-300" : "text-zinc-700"}`}>{course.title}</td>
        <td className={`py-2.5 text-center text-sm ${isDark ? "text-zinc-300" : "text-zinc-700"}`}>{course.units.toFixed(2)}</td>
        <td className={`py-2.5 text-center text-sm ${isDark ? "text-zinc-400" : "text-zinc-500"}`}>{course.term || "—"}</td>
        <td className="py-2.5 text-center">
          {course.grade ? (
            <span className="rounded-md bg-green-100 px-2 py-0.5 text-xs font-bold text-green-700">{course.grade}</span>
          ) : (
            <span className="text-zinc-400">{"—"}</span>
          )}
        </td>
        <td className="py-2.5 pr-2 text-center">
          {course.taken ? (
            <span className="inline-flex items-center gap-1 text-xs font-bold text-green-600">
              <Check size={13} strokeWidth={3} /> Taken
            </span>
          ) : course.in_progress ? (
            <span className="rounded-md bg-blue-100 px-2 py-0.5 text-xs font-bold text-blue-700">In Progress</span>
          ) : (
            <span className={`rounded-md px-2 py-0.5 text-xs font-semibold ${isDark ? "bg-zinc-800 text-zinc-400" : "bg-zinc-100 text-zinc-500"}`}>
              Planned
            </span>
          )}
        </td>
      </tr>
      <AnimatePresence>
        {open && course.description && (
          <tr>
            <td colSpan={6} className="p-0">
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.2 }}
                className="overflow-hidden"
              >
                <div className={`mx-2 mb-2 rounded-lg px-4 py-3 text-xs leading-relaxed ${isDark ? "bg-zinc-950 text-zinc-400" : "bg-zinc-50 text-zinc-600"}`}>
                  <span className="font-semibold">Course Detail · </span>
                  {course.description}
                </div>
              </motion.div>
            </td>
          </tr>
        )}
      </AnimatePresence>
    </>
  );
}

/* ── Sub-requirement (category) node ───────────────────── */

function SubRequirement({ sub, isDark }: { sub: ReqSubrequirement; isDark: boolean }) {
  const [open, setOpen] = useState(false);
  const label = sub.basis === "courses" ? "Courses Completed" : "Units Completed";
  return (
    <div className={`border-t ${isDark ? "border-zinc-800" : "border-zinc-100"}`}>
      <div
        className={`flex cursor-pointer items-center justify-between gap-4 py-3 pl-10 pr-4 ${isDark ? "hover:bg-zinc-900" : "hover:bg-zinc-50"}`}
        onClick={() => setOpen((o) => !o)}
      >
        <div className="min-w-0">
          <div className={`truncate text-sm font-bold ${isDark ? "text-white" : "text-zinc-900"}`}>{sub.category}</div>
          <div className="mt-1">
            <StatusPill satisfied={sub.satisfied} isDark={isDark} />
          </div>
        </div>
        <div className="flex items-center gap-3">
          <ProgressMeter label={label} pct={sub.completion_percentage} isDark={isDark} />
          <motion.span animate={{ rotate: open ? 90 : 0 }} transition={{ duration: 0.2 }}>
            <ChevronRight size={16} className="text-zinc-400" />
          </motion.span>
        </div>
      </div>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="overflow-hidden"
          >
            <div className={`px-6 pb-4 pt-1 ${isDark ? "bg-zinc-950/40" : "bg-zinc-50/60"}`}>
              <div className={`mb-2 text-xs ${isDark ? "text-zinc-400" : "text-zinc-500"}`}>
                {sub.basis === "courses"
                  ? `${sub.completed.toFixed(0)} of ${sub.required.toFixed(0)} courses completed`
                  : `${sub.required.toFixed(2)} required, ${sub.completed.toFixed(2)} taken, ${Math.max(0, sub.required - sub.completed).toFixed(2)} needed`}
                {sub.is_basket && <span className="ml-1 italic">· choose from the list below</span>}
              </div>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className={`border-b ${isDark ? "border-zinc-800" : "border-zinc-200"}`}>
                      {["Course", "Description", "Units", "Term", "Grade", "Status"].map((h, i) => (
                        <th
                          key={h}
                          className={`py-2 text-xs font-bold ${i === 0 ? "pl-2 text-left" : i === 1 ? "text-left" : "text-center"} ${isDark ? "text-zinc-400" : "text-zinc-600"}`}
                        >
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {sub.courses.map((c, i) => (
                      <CourseRow key={`${c.code}-${i}`} course={c} isDark={isDark} />
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/* ── Semester block ────────────────────────────────────── */

function SemesterBlock({
  sem,
  isDark,
  defaultOpen,
}: {
  sem: ReqSemester;
  isDark: boolean;
  defaultOpen: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className={`overflow-hidden rounded-xl border shadow-sm ${isDark ? "border-zinc-800 bg-zinc-900" : "border-zinc-200 bg-white"}`}>
      <div
        className={`flex cursor-pointer items-center justify-between gap-4 px-5 py-4 ${isDark ? "hover:bg-zinc-800/60" : "hover:bg-zinc-50"}`}
        onClick={() => setOpen((o) => !o)}
      >
        <div>
          <div className={`text-base font-extrabold ${isDark ? "text-white" : "text-zinc-900"}`}>{sem.name}</div>
          <div className="mt-1">
            <StatusPill satisfied={sem.satisfied} isDark={isDark} />
          </div>
        </div>
        <div className="flex items-center gap-3">
          <ProgressMeter label="Units Completed" pct={sem.completion_percentage} isDark={isDark} />
          <motion.span animate={{ rotate: open ? 90 : 0 }} transition={{ duration: 0.2 }}>
            <ChevronRight size={18} className="text-zinc-400" />
          </motion.span>
        </div>
      </div>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="overflow-hidden"
          >
            {sem.subrequirements.map((sub) => (
              <SubRequirement key={sub.category} sub={sub} isDark={isDark} />
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/* ── Page ──────────────────────────────────────────────── */

export default function RequirementsPage() {
  useLanguage();
  const { isDark } = useTheme();
  const { token, signOut } = useAuth();

  const [summary, setSummary] = useState<MeResponse | null>(null);
  const [tree, setTree] = useState<RequirementTree | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
        if (msg.toLowerCase().includes("unauthorized") || msg.toLowerCase().includes("invalid token")) signOut();
      });

    setLoading(true);
    setError(null);
    getMyRequirementsTree(token, controller.signal)
      .then((d) => {
        if (!controller.signal.aborted) setTree(d);
      })
      .catch((e) => {
        if (isAbortError(e) || controller.signal.aborted) return;
        const msg = normalizeErrorMessage(e, "Failed to load requirements");
        if (msg.toLowerCase().includes("unauthorized") || msg.toLowerCase().includes("invalid token")) {
          signOut();
          return;
        }
        setError(msg);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [token, signOut]);

  const overall = tree?.overall;
  const firstUnsatisfied = useMemo(
    () => tree?.semesters.find((s) => !s.satisfied)?.slot ?? null,
    [tree],
  );

  return (
    <AppLayout activePath="/manage-classes/requirements" userName={summary?.full_name ?? "Loading..."}>
      <PageContainer>
        <ManageClassesSubNav activePath="/manage-classes/requirements" isDark={isDark} />

        {error && <ErrorBanner message={error} isDark={isDark} onDismiss={() => setError(null)} />}

        {/* Program header */}
        {tree?.program && overall && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            className={`mb-6 rounded-2xl border p-6 shadow-sm ${isDark ? "border-zinc-800 bg-zinc-900" : "border-zinc-200 bg-white"}`}
          >
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <div className={`text-xl font-extrabold ${isDark ? "text-white" : "text-zinc-900"}`}>{tree.program.name}</div>
                <div className="mt-1.5 flex items-center gap-3">
                  <StatusPill satisfied={overall.satisfied} isDark={isDark} />
                  <span className="text-xs text-zinc-400">·</span>
                  <span className={`text-xs font-semibold ${isDark ? "text-zinc-300" : "text-zinc-600"}`}>
                    {overall.completed.toFixed(0)} / {tree.program.total_credits.toFixed(0)} credits
                  </span>
                </div>
              </div>
              <ProgressMeter label="Units Completed" pct={overall.completion_percentage} isDark={isDark} />
            </div>
          </motion.div>
        )}

        {/* legend */}
        {!loading && tree?.semesters?.length ? (
          <div className="mb-4 flex flex-wrap items-center gap-4 text-xs text-zinc-500">
            <span className="inline-flex items-center gap-1">
              <span className="flex h-3.5 w-3.5 items-center justify-center rounded-full bg-green-600">
                <Check size={9} strokeWidth={3} className="text-white" />
              </span>
              Satisfied
            </span>
            <span className="inline-flex items-center gap-1">
              <Diamond size={12} strokeWidth={3} className="fill-amber-500 text-amber-500" /> Not Satisfied
            </span>
            <span className="italic">Click a semester → requirement → course to drill in.</span>
          </div>
        ) : null}

        {loading && (
          <div className="space-y-4">
            <CardSkeleton />
            <CardSkeleton />
            <CardSkeleton />
          </div>
        )}

        {!loading && (!tree || tree.semesters.length === 0) && (
          <EmptyState title="No requirements" description="Your degree requirements will appear here." icon="📋" isDark={isDark} />
        )}

        {!loading && tree && tree.semesters.length > 0 && (
          <div className="space-y-3 pb-8">
            {tree.semesters.map((sem, idx) => (
              <motion.div
                key={sem.slot}
                initial={{ opacity: 0, y: 14 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: Math.min(idx * 0.05, 0.4) }}
              >
                <SemesterBlock sem={sem} isDark={isDark} defaultOpen={sem.slot === firstUnsatisfied} />
              </motion.div>
            ))}
          </div>
        )}

        {loading && (
          <div className="mt-2 flex items-center gap-2 text-sm text-zinc-400">
            <Loader2 size={16} className="animate-spin" /> Building your degree audit…
          </div>
        )}
      </PageContainer>
    </AppLayout>
  );
}
