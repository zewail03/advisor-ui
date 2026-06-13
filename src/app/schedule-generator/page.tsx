"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import AppLayout from "@/components/layout/AppLayout";
import { useLanguage } from "@/hooks/useLanguage";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/hooks/useAuth";
import { bulkEnroll, generateSchedule } from "@/lib/api";

type Difficulty = "Easy" | "Moderate" | "Hard" | "Unknown";

type ScheduleSection = {
  section_id: string;
  course_code: string;
  course_title: string;
  credits: number;
  days: string | null;
  time_start: string | null;
  time_end: string | null;
  room: string | null;
  instructor: string | null;
  difficulty: Difficulty;
  historical_pass_rate: number | null;
  historical_sample_size: number;
  historical_avg_grade_points: number | null;
};

type ScheduleOption = {
  label: string;
  load_score: string;
  weighted_difficulty: number;
  total_credits: number;
  sections: ScheduleSection[];
};

const DIFFICULTY_CLASS: Record<Difficulty, string> = {
  Easy: "bg-emerald-100 text-emerald-700 dark:text-emerald-300 dark:bg-emerald-950 dark:text-emerald-300",
  Moderate: "bg-amber-100 text-amber-700 dark:text-amber-300 dark:bg-amber-950 dark:text-amber-300",
  Hard: "bg-red-100 text-red-700 dark:text-red-300 dark:bg-red-950 dark:text-red-300",
  Unknown: "bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 dark:bg-zinc-800 dark:text-zinc-400",
};

const LOAD_CLASS: Record<string, string> = {
  Easy: "bg-emerald-100 text-emerald-700 dark:text-emerald-300",
  Moderate: "bg-amber-100 text-amber-700 dark:text-amber-300",
  Heavy: "bg-red-100 text-red-700 dark:text-red-300",
};

export default function ScheduleGeneratorPage() {
  const { t } = useLanguage();
  const { token } = useAuth();
  const [semester, setSemester] = useState("Spring-2026");
  const [maxCredits, setMaxCredits] = useState<number | "">("");
  const [options, setOptions] = useState<ScheduleOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [enrolling, setEnrolling] = useState<number | null>(null);
  const [result, setResult] = useState<string | null>(null);

  async function onGenerate() {
    if (!token) return;
    setErr(null);
    setResult(null);
    setLoading(true);
    try {
      const data = await generateSchedule(
        token,
        semester,
        typeof maxCredits === "number" ? maxCredits : undefined,
      );
      setOptions(data.options || []);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to generate");
    } finally {
      setLoading(false);
    }
  }

  async function onAccept(opt: ScheduleOption, idx: number) {
    if (!token) return;
    setEnrolling(idx);
    setResult(null);
    try {
      const data = await bulkEnroll(token, opt.sections.map((s) => s.section_id));
      const ok = (data.results || []).filter((r: any) => r.success).length;
      const total = (data.results || []).length;
      setResult(`Enrolled in ${ok} of ${total} sections.`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to enroll");
    } finally {
      setEnrolling(null);
    }
  }

  return (
    <AppLayout activePath="/schedule-generator" userName="Schedule">
      <main className="px-4 md:px-8 lg:px-16 py-8 space-y-6">
        <motion.header initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} className="space-y-1">
          <h1 className="text-3xl font-bold">{t("sch.title")}</h1>
          <p className="text-zinc-500 dark:text-zinc-400 text-sm">
            We build three conflict-free options: fastest, balanced, and lightest.
          </p>
        </motion.header>

        <section className="flex flex-wrap items-end gap-3">
          <div className="space-y-1">
            <label className="text-xs font-medium">{t("sch.semester")}</label>
            <Input
              value={semester}
              onChange={(e) => setSemester(e.target.value)}
              placeholder={t("reco.egSem")}
              className="w-48"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium">{t("sch.maxCredits")}</label>
            <Input
              type="number"
              value={maxCredits}
              onChange={(e) =>
                setMaxCredits(e.target.value === "" ? "" : Number(e.target.value))
              }
              placeholder={t("sch.eg18")}
              className="w-40"
            />
          </div>
          <Button onClick={onGenerate} disabled={loading}>
            {loading ? "Generating..." : "Generate"}
          </Button>
        </section>

        {err && <div className="rounded-lg bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300 px-3 py-2 text-sm">{err}</div>}
        {result && <div className="rounded-lg bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 px-3 py-2 text-sm">{result}</div>}

        <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <AnimatePresence>
          {options.map((opt, idx) => (
            <motion.div key={idx} initial={{ opacity: 0, y: 30, scale: 0.95 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={{ delay: idx * 0.15, type: "spring", stiffness: 200, damping: 20 }} whileHover={{ y: -4 }} className="rounded-xl border border-zinc-200 dark:border-zinc-700 dark:border-zinc-800 p-4 flex flex-col shadow-sm hover:shadow-lg transition-shadow">
              <div className="flex items-baseline justify-between mb-2">
                <h3 className="font-semibold">{opt.label}</h3>
                <span
                  className={`text-xs rounded-full px-2 py-0.5 font-medium ${
                    LOAD_CLASS[opt.load_score] ?? "bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300"
                  }`}
                  title={`Weighted difficulty ${opt.weighted_difficulty} based on historical pass rates`}
                >
                  {opt.load_score} load
                </span>
              </div>
              <div className="text-sm text-zinc-500 dark:text-zinc-400 mb-3">
                {opt.total_credits} credits · difficulty score {opt.weighted_difficulty}
              </div>
              <ul className="space-y-2 text-sm flex-1">
                {opt.sections.map((s) => (
                  <li key={s.section_id} className="border-b border-zinc-100 dark:border-zinc-800 dark:border-zinc-800 pb-2">
                    <div className="flex items-start justify-between gap-2">
                      <div className="font-medium">
                        {s.course_code} — {s.course_title}
                      </div>
                      <span
                        className={`shrink-0 text-[10px] rounded-full px-1.5 py-0.5 font-medium ${DIFFICULTY_CLASS[s.difficulty]}`}
                        title={
                          s.historical_sample_size > 0 && s.historical_pass_rate !== null
                            ? `${Math.round(s.historical_pass_rate * 100)}% pass rate across ${s.historical_sample_size} historical records`
                            : "Not enough historical data"
                        }
                      >
                        {s.difficulty}
                        {s.historical_pass_rate !== null && s.difficulty !== "Unknown"
                          ? ` · ${Math.round(s.historical_pass_rate * 100)}%`
                          : ""}
                      </span>
                    </div>
                    <div className="text-xs text-zinc-500 dark:text-zinc-400">
                      {s.days} {s.time_start}–{s.time_end} · {s.room} · {s.instructor}
                    </div>
                  </li>
                ))}
              </ul>
              <Button
                className="mt-3"
                onClick={() => onAccept(opt, idx)}
                disabled={enrolling !== null}
              >
                {enrolling === idx ? "Enrolling..." : "Accept & Enroll"}
              </Button>
            </motion.div>
          ))}
          </AnimatePresence>
        </section>
      </main>
    </AppLayout>
  );
}
