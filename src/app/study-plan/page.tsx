"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import AppLayout from "@/components/layout/AppLayout";
import { useLanguage } from "@/hooks/useLanguage";
import { useAuth } from "@/hooks/useAuth";
import { useTheme } from "@/hooks/useTheme";
import { getGraduationCheck, getMyStudyPlan } from "@/lib/api";

const SEMESTER_LABELS = [
  "Spring 2026", "Summer 2026", "Fall 2026",
  "Spring 2027", "Summer 2027", "Fall 2027",
  "Spring 2028", "Summer 2028", "Fall 2028",
  "Spring 2029",
];
const MAX_CREDITS_PER_SEM = 18;

type CourseEntry = { code: string; title: string; credits: number };

function groupIntoSemesters(remaining: CourseEntry[]) {
  const semesters: Array<{ label: string; courses: CourseEntry[]; total_credits: number }> = [];
  let idx = 0;
  let current: CourseEntry[] = [];
  let currentCredits = 0;

  for (const c of remaining) {
    if (currentCredits + c.credits > MAX_CREDITS_PER_SEM && current.length > 0) {
      semesters.push({
        label: SEMESTER_LABELS[idx] || `Semester ${idx + 1}`,
        courses: current,
        total_credits: currentCredits,
      });
      idx++;
      current = [];
      currentCredits = 0;
    }
    current.push(c);
    currentCredits += c.credits;
  }
  if (current.length > 0) {
    semesters.push({
      label: SEMESTER_LABELS[idx] || `Semester ${idx + 1}`,
      courses: current,
      total_credits: currentCredits,
    });
  }
  return semesters;
}

export default function StudyPlanPage() {
  const { t } = useLanguage();
  const { token } = useAuth();
  const { isDark } = useTheme();
  const [plan, setPlan] = useState<any>(null);
  const [grad, setGrad] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    Promise.all([getMyStudyPlan(token), getGraduationCheck(token)])
      .then(([a, b]) => {
        setPlan(a);
        setGrad(b);
      })
      .catch((e) => setErr(e.message));
  }, [token]);

  const remaining: CourseEntry[] = (plan?.remaining || []).map((c: any) => ({
    code: c.code || c.course_code,
    title: c.title || c.course_title || c.course_name,
    credits: c.credits || c.credit_hours || 3,
  }));

  const semesters = plan?.semesters || groupIntoSemesters(remaining);
  const totalRemaining = remaining.reduce((s, c) => s + c.credits, 0);

  return (
    <AppLayout activePath="/study-plan" userName="Study Plan">
      <main className="px-4 md:px-8 lg:px-16 py-8 space-y-6">
        <motion.header initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}>
          <h1 className="text-3xl font-bold">{t("plan.title")}</h1>
          <p className={`text-sm ${isDark ? "text-zinc-400" : "text-zinc-500"}`}>{t("plan.subtitle")}</p>
        </motion.header>

        {err && <div className="rounded-lg bg-red-50 text-red-700 px-3 py-2 text-sm">{err}</div>}

        {grad && (
          <motion.section
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ type: "spring", stiffness: 200, damping: 20 }}
            className={`rounded-xl border p-5 ${
              grad.eligible
                ? "border-emerald-300 bg-emerald-50 dark:bg-emerald-950/30"
                : "border-amber-300 bg-amber-50 dark:bg-amber-950/30"
            }`}
          >
            <h2 className="font-semibold mb-2 text-lg">
              {grad.eligible ? "Graduation-eligible" : "Not yet eligible"}
            </h2>
            <div className="text-sm">
              {totalRemaining > 0
                ? `${totalRemaining} credits remaining across ${remaining.length} courses`
                : "All required courses completed!"}
            </div>
            {(grad.missing || grad.missing_requirements || []).length > 0 && (
              <ul className="mt-3 text-sm list-disc list-inside space-y-1">
                {(grad.missing || grad.missing_requirements || []).map((m: any, i: number) => (
                  <li key={i}>
                    <span className="font-semibold">{m.category}</span>: {m.units_remaining || m.remaining} credits remaining
                  </li>
                ))}
              </ul>
            )}
          </motion.section>
        )}

        {remaining.length > 0 && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className={`rounded-xl border p-4 text-center ${isDark ? "border-zinc-700 bg-zinc-800" : "border-zinc-200 bg-white"}`}>
              <div className="text-2xl font-bold text-[#B8001F]">{remaining.length}</div>
              <div className={`text-xs mt-1 ${isDark ? "text-zinc-400" : "text-zinc-500"}`}>{t("plan.coursesLeft")}</div>
            </div>
            <div className={`rounded-xl border p-4 text-center ${isDark ? "border-zinc-700 bg-zinc-800" : "border-zinc-200 bg-white"}`}>
              <div className="text-2xl font-bold text-[#B8001F]">{totalRemaining}</div>
              <div className={`text-xs mt-1 ${isDark ? "text-zinc-400" : "text-zinc-500"}`}>{t("plan.creditsLeft")}</div>
            </div>
            <div className={`rounded-xl border p-4 text-center ${isDark ? "border-zinc-700 bg-zinc-800" : "border-zinc-200 bg-white"}`}>
              <div className="text-2xl font-bold text-green-600">{semesters.length}</div>
              <div className={`text-xs mt-1 ${isDark ? "text-zinc-400" : "text-zinc-500"}`}>Semesters (est.)</div>
            </div>
            <div className={`rounded-xl border p-4 text-center ${isDark ? "border-zinc-700 bg-zinc-800" : "border-zinc-200 bg-white"}`}>
              <div className="text-2xl font-bold text-amber-600">{totalRemaining > 0 ? Math.round(totalRemaining / Math.max(semesters.length, 1)) : 0}</div>
              <div className={`text-xs mt-1 ${isDark ? "text-zinc-400" : "text-zinc-500"}`}>Avg Credits/Sem</div>
            </div>
          </motion.div>
        )}

        <section className="space-y-4">
          {semesters.map((sem: any, idx: number) => (
            <motion.div
              key={sem.label}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.08, type: "spring", stiffness: 200, damping: 20 }}
              whileHover={{ y: -2 }}
              className={`rounded-xl border p-5 shadow-sm hover:shadow-md transition-shadow ${isDark ? "border-zinc-700 bg-zinc-800" : "border-zinc-200 bg-white"}`}
            >
              <div className="flex items-baseline justify-between mb-3">
                <h3 className="font-bold text-base">{sem.label}</h3>
                <span className={`text-xs font-semibold px-3 py-1 rounded-full ${isDark ? "bg-zinc-700 text-zinc-300" : "bg-zinc-100 text-zinc-600"}`}>
                  {sem.total_credits} credits
                </span>
              </div>
              <div className="space-y-2">
                {(sem.courses || []).map((c: any) => (
                  <div key={c.code || c.course_code} className={`flex justify-between items-center py-2 px-3 rounded-lg text-sm ${isDark ? "hover:bg-zinc-700" : "hover:bg-zinc-50"} transition-colors`}>
                    <span>
                      <span className="font-semibold">{c.code || c.course_code}</span>
                      <span className={`ml-2 ${isDark ? "text-zinc-400" : "text-zinc-600"}`}>{c.title || c.course_title}</span>
                    </span>
                    <span className={`text-xs font-medium ${isDark ? "text-zinc-500" : "text-zinc-400"}`}>{c.credits || c.credit_hours} cr</span>
                  </div>
                ))}
              </div>
            </motion.div>
          ))}
        </section>
      </main>
    </AppLayout>
  );
}
