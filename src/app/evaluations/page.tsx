"use client";

import { useEffect, useState } from "react";
import AppLayout from "@/components/layout/AppLayout";
import { useLanguage } from "@/hooks/useLanguage";
import { useAuth } from "@/hooks/useAuth";
import { getPendingEvaluations, submitEvaluation } from "@/lib/api";

const AXES = [
  { key: "rating_content", label: "Course content" },
  { key: "rating_teaching", label: "Teaching quality" },
  { key: "rating_materials", label: "Materials & resources" },
  { key: "rating_assessment", label: "Assessment fairness" },
  { key: "rating_engagement", label: "Engagement & interaction" },
  { key: "rating_overall", label: "Overall experience" },
];

const defaultRatings = () =>
  Object.fromEntries(AXES.map((a) => [a.key, 4])) as Record<string, number>;

export default function EvaluationsPage() {
  const { t } = useLanguage();
  const { token } = useAuth();
  const [pending, setPending] = useState<any[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [active, setActive] = useState<string | null>(null);
  const [ratings, setRatings] = useState<Record<string, number>>(defaultRatings());
  const [best, setBest] = useState("");
  const [improve, setImprove] = useState("");
  const [anon, setAnon] = useState(true);
  const [busy, setBusy] = useState(false);

  async function reload() {
    if (!token) return;
    try {
      const r = await getPendingEvaluations(token);
      setPending(r.pending);
    } catch (e: any) {
      setErr(e.message);
    }
  }

  useEffect(() => { reload(); /* eslint-disable-next-line */ }, [token]);

  async function submit(enrollmentId: string) {
    if (!token) return;
    setBusy(true);
    setErr(null);
    try {
      await submitEvaluation(token, {
        enrollment_id: enrollmentId,
        ...ratings,
        best_aspect: best || undefined,
        improvement_note: improve || undefined,
        anonymous: anon,
      });
      setActive(null);
      setRatings(defaultRatings());
      setBest("");
      setImprove("");
      await reload();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppLayout activePath="/evaluations" userName="Evaluations">
      <main className="px-4 md:px-8 lg:px-16 py-8 space-y-6">
        <header>
          <h1 className="text-3xl font-bold">{t("ev.title")}</h1>
          <p className="text-sm text-zinc-500 dark:text-zinc-400">{t("ev.subtitle")}</p>
        </header>

        {err && <div className="rounded-lg bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300 px-3 py-2 text-sm">{err}</div>}

        {pending.length === 0 ? (
          <div className="text-sm text-zinc-500 dark:text-zinc-400">{t("ev.none")}</div>
        ) : (
          <div className="space-y-3">
            {pending.map((p) => (
              <div key={p.enrollment_id} className="rounded-xl border border-zinc-200 dark:border-zinc-700 dark:border-zinc-800 p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="font-medium">Course {p.course_id}</div>
                    <div className="text-xs text-zinc-500 dark:text-zinc-400">{p.semester_code} · {p.instructor ?? ""}</div>
                  </div>
                  <button
                    className="rounded border border-zinc-300 dark:border-zinc-600 dark:border-zinc-700 px-3 py-1 text-sm"
                    onClick={() => setActive(active === p.enrollment_id ? null : p.enrollment_id)}
                  >
                    {active === p.enrollment_id ? "Cancel" : "Evaluate"}
                  </button>
                </div>

                {active === p.enrollment_id && (
                  <div className="mt-4 space-y-3">
                    {AXES.map((axis) => (
                      <div key={axis.key}>
                        <div className="flex items-center justify-between text-sm">
                          <span>{axis.label}</span>
                          <span className="text-zinc-500 dark:text-zinc-400">{ratings[axis.key]}</span>
                        </div>
                        <input
                          type="range"
                          min={1}
                          max={5}
                          value={ratings[axis.key]}
                          onChange={(e) => setRatings({ ...ratings, [axis.key]: Number(e.target.value) })}
                          className="w-full"
                        />
                      </div>
                    ))}
                    <textarea
                      placeholder={t("ev.best")}
                      className="w-full rounded border border-zinc-300 dark:border-zinc-600 dark:border-zinc-700 bg-transparent px-3 py-2"
                      value={best}
                      onChange={(e) => setBest(e.target.value)}
                    />
                    <textarea
                      placeholder={t("ev.improve")}
                      className="w-full rounded border border-zinc-300 dark:border-zinc-600 dark:border-zinc-700 bg-transparent px-3 py-2"
                      value={improve}
                      onChange={(e) => setImprove(e.target.value)}
                    />
                    <label className="text-sm flex items-center gap-2">
                      <input type="checkbox" checked={anon} onChange={(e) => setAnon(e.target.checked)} />
                      Submit anonymously
                    </label>
                    <button
                      disabled={busy}
                      className="rounded bg-[#B8001F] text-white px-4 py-2 disabled:opacity-50"
                      onClick={() => submit(p.enrollment_id)}
                    >
                      {busy ? "Submitting…" : "Submit evaluation"}
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </main>
    </AppLayout>
  );
}
