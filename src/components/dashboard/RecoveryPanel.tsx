"use client";

import { useEffect, useState } from "react";

import { dropEnrollment, getRecoveryPlan, type RecoveryPlan } from "@/lib/api";
import { normalizeErrorMessage } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { useLanguage } from "@/hooks/useLanguage";
import type { TranslationKey } from "@/lib/i18n";

type Props = {
  token: string;
  isDark: boolean;
};

const SEVERITY_THEME: Record<RecoveryPlan["severity"], { labelKey: string; border: string; badge: string; headline: string }> = {
  critical: {
    labelKey: "recovery.critical",
    border: "border-red-500",
    badge: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300",
    headline: "text-red-700 dark:text-red-400",
  },
  warning: {
    labelKey: "recovery.warning",
    border: "border-amber-500",
    badge: "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
    headline: "text-amber-700 dark:text-amber-400",
  },
  none: {
    labelKey: "",
    border: "",
    badge: "",
    headline: "",
  },
};

export default function RecoveryPanel({ token, isDark }: Props) {
  const { t } = useLanguage();
  const [plan, setPlan] = useState<RecoveryPlan | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [dropping, setDropping] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getRecoveryPlan(token, controller.signal)
      .then(setPlan)
      .catch((e) => {
        if (controller.signal.aborted) return;
        setErr(normalizeErrorMessage(e, "Failed to load recovery plan"));
      });
    return () => controller.abort();
  }, [token]);

  if (err || !plan || plan.severity === "none") return null;

  const theme = SEVERITY_THEME[plan.severity];

  async function handleDrop(enrollmentId: string) {
    setDropping(enrollmentId);
    try {
      await dropEnrollment(token, enrollmentId);
      const refreshed = await getRecoveryPlan(token);
      setPlan(refreshed);
    } catch (e) {
      setErr(normalizeErrorMessage(e, "Failed to drop course"));
    } finally {
      setDropping(null);
    }
  }

  return (
    <div
      className={`mb-8 rounded-2xl border-2 ${theme.border} ${
        isDark ? "bg-zinc-900" : "bg-white"
      } p-6 shadow-sm`}
    >
      <div className="flex items-start justify-between gap-4 mb-4">
        <div>
          <div className={`text-xs font-semibold mb-1 ${theme.headline}`}>{t("recovery.title")}</div>
          <h2 className={`text-xl font-bold ${isDark ? "text-white" : "text-zinc-900"}`}>
            {theme.labelKey ? t(theme.labelKey as TranslationKey) : ""}
          </h2>
          <div className={`text-sm mt-1 ${isDark ? "text-zinc-400" : "text-zinc-600"}`}>
            {t("recovery.currentCgpa")} {plan.current_cgpa.toFixed(2)} · {t("recovery.target")} {plan.target_cgpa.toFixed(2)}
            {plan.consecutive_probation > 0 && ` · ${plan.consecutive_probation} ${t("recovery.consecutive")}`}
          </div>
        </div>
        <span className={`shrink-0 text-xs rounded-full px-3 py-1 font-semibold ${theme.badge}`}>
          {plan.severity.toUpperCase()}
        </span>
      </div>

      {plan.drop_candidates.length > 0 && (
        <div className="mb-4">
          <div className={`text-sm font-semibold mb-2 ${isDark ? "text-zinc-200" : "text-zinc-800"}`}>
            {t("recovery.drops")}
          </div>
          <div className="space-y-2">
            {plan.drop_candidates.map((c) => (
              <div
                key={c.enrollment_id}
                className={`flex items-center justify-between rounded-lg border p-3 ${
                  isDark ? "border-zinc-800 bg-zinc-950/50" : "border-zinc-200 bg-zinc-50"
                }`}
              >
                <div>
                  <div className={`text-sm font-semibold ${isDark ? "text-white" : "text-zinc-900"}`}>
                    {c.course_code} — {c.course_title}
                  </div>
                  <div className="text-xs text-zinc-500">
                    {t("recovery.midterm")}: {c.midterm_score?.toFixed(0)}% · {c.credits} {t("recovery.credits")}
                  </div>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleDrop(c.enrollment_id)}
                  disabled={dropping === c.enrollment_id}
                  className="border-red-500 text-red-700 hover:bg-red-50 dark:hover:bg-red-950"
                >
                  {dropping === c.enrollment_id ? t("recovery.dropping") : t("recovery.drop")}
                </Button>
              </div>
            ))}
          </div>
        </div>
      )}

      {plan.retake_candidates.length > 0 && (
        <div className="mb-4">
          <div className={`text-sm font-semibold mb-2 ${isDark ? "text-zinc-200" : "text-zinc-800"}`}>
            {t("recovery.retakes")}
          </div>
          <div className="space-y-1">
            {plan.retake_candidates.slice(0, 3).map((c, i) => (
              <div
                key={`${c.course_code}-${i}`}
                className={`flex items-center justify-between text-sm ${isDark ? "text-zinc-300" : "text-zinc-700"}`}
              >
                <span>
                  <span className="font-semibold">{c.course_code}</span> ({c.credits} {t("recovery.credits")}) — {t("recovery.prior")}{" "}
                  <span className="font-semibold">{c.prior_grade}</span> · {c.prior_semester}
                </span>
                <span className="text-xs text-emerald-600 dark:text-emerald-400 font-semibold">
                  +{c.improvement_ceiling.toFixed(1)} {t("recovery.ceiling")}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {plan.grades_needed.feasible && plan.grades_needed.minimum_letter_per_course && (
        <div className={`mb-4 rounded-lg px-3 py-2 text-sm ${isDark ? "bg-zinc-800 text-zinc-200" : "bg-zinc-100 text-zinc-800"}`}>
          {t("recovery.minGrade")} {plan.grades_needed.target_cgpa.toFixed(1)}:{" "}
          <span className="font-bold">{plan.grades_needed.minimum_letter_per_course}</span>
          {plan.grades_needed.avg_grade_points_needed !== undefined && (
            <span className="text-zinc-500">
              {" "}
              ({t("recovery.avg")} {plan.grades_needed.avg_grade_points_needed.toFixed(2)} {t("recovery.points")})
            </span>
          )}
        </div>
      )}
      {plan.grades_needed.feasible === false && (
        <div className={`mb-4 rounded-lg px-3 py-2 text-sm ${isDark ? "bg-red-950 text-red-300" : "bg-red-50 text-red-700"}`}>
          {plan.grades_needed.reason ??
            `${t("recovery.notFeasible1")} ${plan.grades_needed.target_cgpa.toFixed(1)} ${t("recovery.notFeasible2")}`}
        </div>
      )}

      <div>
        <div className={`text-sm font-semibold mb-2 ${isDark ? "text-zinc-200" : "text-zinc-800"}`}>{t("recovery.actionPlan")}</div>
        <ul className={`text-sm space-y-1 list-disc pl-5 ${isDark ? "text-zinc-300" : "text-zinc-700"}`}>
          {plan.recommended_actions.map((a, i) => (
            <li key={i}>{a}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}
