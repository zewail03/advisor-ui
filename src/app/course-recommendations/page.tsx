"use client";

import { useCallback, useEffect, useState } from "react";

import { motion } from "framer-motion";
import AppLayout from "@/components/layout/AppLayout";
import { useLanguage } from "@/hooks/useLanguage";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  getCourseRecommendations,
  type CourseRecommendation,
  type CourseRecommendationsResponse,
} from "@/lib/api";
import { normalizeErrorMessage } from "@/lib/utils";
import { useAuth } from "@/hooks/useAuth";
import { useTheme } from "@/hooks/useTheme";

type Difficulty = CourseRecommendation["difficulty"];

const DIFFICULTY_CLASS: Record<Difficulty, string> = {
  Easy: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
  Moderate: "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
  Hard: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300",
  Unknown: "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400",
};

const BAND_COPY: Record<string, { title: string; tone: string }> = {
  recovery: {
    title: "Recovery mode — easier courses weighted higher to rebuild CGPA.",
    tone: "bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-300",
  },
  standard: {
    title: "Standard mode — balancing unlock impact with manageable difficulty.",
    tone: "bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
  },
  advanced: {
    title: "Advanced mode — prioritizing progress; you can handle harder courses.",
    tone: "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
  },
};

export default function CourseRecommendationsPage() {
  const { t } = useLanguage();
  const { token } = useAuth();
  const { isDark } = useTheme();
  const [semester, setSemester] = useState("Spring-2026");
  const [topN, setTopN] = useState<number>(5);
  const [data, setData] = useState<CourseRecommendationsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(
    async (signal?: AbortSignal) => {
      if (!token) return;
      setErr(null);
      setLoading(true);
      try {
        const resp = await getCourseRecommendations(
          token,
          { semester, top_n: topN },
          signal,
        );
        setData(resp);
      } catch (e) {
        if (signal?.aborted) return;
        setErr(normalizeErrorMessage(e, "Failed to load recommendations"));
      } finally {
        if (!signal?.aborted) setLoading(false);
      }
    },
    [token, semester, topN],
  );

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
    // Initial load only — refetch triggered explicitly via button.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const recs = data?.recommendations ?? [];
  const band = data?.cgpa_band ? BAND_COPY[data.cgpa_band] : null;

  return (
    <AppLayout activePath="/course-recommendations" userName="Recommendations">
      <main className="px-4 md:px-8 lg:px-16 py-8 space-y-6">
        <motion.header initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} className="space-y-1">
          <h1 className="text-3xl font-bold">{t("reco.title")}</h1>
          <p className={`text-sm ${isDark ? "text-zinc-400" : "text-zinc-500"}`}>
            Ranked by how many downstream courses each unlocks, historical pass rate from past
            students, and whether it&apos;s offered this semester. Weighted for your CGPA band.
          </p>
        </motion.header>

        <section className="flex flex-wrap items-end gap-3">
          <div className="space-y-1">
            <label className="text-xs font-medium">{t("reco.semester")}</label>
            <Input
              value={semester}
              onChange={(e) => setSemester(e.target.value)}
              placeholder={t("reco.egSem")}
              className="w-48"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium">{t("reco.howMany")}</label>
            <Input
              type="number"
              min={1}
              max={20}
              value={topN}
              onChange={(e) => setTopN(Math.max(1, Math.min(20, Number(e.target.value) || 5)))}
              className="w-28"
            />
          </div>
          <Button onClick={() => load()} disabled={loading || !token}>
            {loading ? "Loading…" : "Refresh"}
          </Button>
        </section>

        {err && (
          <div className="rounded-lg bg-red-50 text-red-700 px-3 py-2 text-sm dark:bg-red-950 dark:text-red-300">
            {err}
          </div>
        )}

        {data && (
          <div className={`flex flex-wrap items-center gap-3 text-sm ${isDark ? "text-zinc-300" : "text-zinc-700"}`}>
            <span className="font-semibold">
              CGPA {data.current_cgpa.toFixed(2)}
            </span>
            {band && (
              <span className={`rounded-full px-3 py-1 text-xs font-semibold ${band.tone}`}>
                {band.title}
              </span>
            )}
          </div>
        )}

        {!loading && data && recs.length === 0 && (
          <div className={`rounded-lg px-3 py-2 text-sm ${isDark ? "bg-zinc-900 text-zinc-300" : "bg-zinc-50 text-zinc-700"}`}>
            {data.reason ?? "No recommendations available for this semester."}
          </div>
        )}

        <section className="space-y-3">
          {recs.map((r, i) => (
            <motion.article
              key={r.course_id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.08, type: "spring", stiffness: 200, damping: 20 }}
              whileHover={{ y: -3, scale: 1.01 }}
              className={`rounded-xl border p-4 shadow-sm hover:shadow-md transition-shadow ${
                isDark ? "border-zinc-800 bg-zinc-900" : "border-zinc-200 bg-white"
              } ${!r.prereqs_met ? "opacity-70" : ""}`}
            >
              <div className="flex items-start justify-between gap-3 mb-2">
                <div className="flex items-baseline gap-3 flex-wrap">
                  <span className={`text-xs font-mono ${isDark ? "text-zinc-500" : "text-zinc-400"}`}>
                    #{i + 1}
                  </span>
                  <h3 className="font-semibold text-lg">
                    {r.code} — {r.title}
                  </h3>
                  <span className={`text-xs ${isDark ? "text-zinc-400" : "text-zinc-500"}`}>
                    {r.credits} credits
                  </span>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span
                    className={`text-xs rounded-full px-2 py-0.5 font-medium ${DIFFICULTY_CLASS[r.difficulty]}`}
                    title={
                      r.historical_sample_size > 0 && r.historical_pass_rate !== null
                        ? `${Math.round(r.historical_pass_rate * 100)}% pass rate across ${r.historical_sample_size} past students`
                        : "Not enough historical data"
                    }
                  >
                    {r.difficulty}
                    {r.historical_pass_rate !== null && r.difficulty !== "Unknown"
                      ? ` · ${Math.round(r.historical_pass_rate * 100)}%`
                      : ""}
                  </span>
                  {r.offered_this_semester ? (
                    <span className="text-xs rounded-full px-2 py-0.5 font-medium bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
                      Offered
                    </span>
                  ) : (
                    <span className="text-xs rounded-full px-2 py-0.5 font-medium bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400">
                      Not offered
                    </span>
                  )}
                </div>
              </div>

              <div className={`text-sm ${isDark ? "text-zinc-300" : "text-zinc-700"}`}>
                {r.reason}.
              </div>

              <div className="mt-2 flex flex-wrap gap-3 text-xs">
                {r.unlocks > 0 && (
                  <span className={`${isDark ? "text-zinc-400" : "text-zinc-600"}`}>
                    Unlocks <span className="font-semibold">{r.unlocks}</span> downstream course
                    {r.unlocks !== 1 ? "s" : ""}
                  </span>
                )}
                <span className={`${isDark ? "text-zinc-500" : "text-zinc-500"}`}>
                  score {r.score.toFixed(2)}
                </span>
                {!r.prereqs_met && r.prereq_blocker && (
                  <span className="text-amber-700 dark:text-amber-400">
                    Prereqs pending: {r.prereq_blocker}
                  </span>
                )}
              </div>
            </motion.article>
          ))}
        </section>
      </main>
    </AppLayout>
  );
}
