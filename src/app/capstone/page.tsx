"use client";

import { useEffect, useState } from "react";
import AppLayout from "@/components/layout/AppLayout";
import { useLanguage } from "@/hooks/useLanguage";
import { useAuth } from "@/hooks/useAuth";
import {
  enrollCapstone,
  getCapstoneEligibility,
  getMyCapstone,
  patchMilestone,
} from "@/lib/api";

const STAGES = [
  { value: "field_training_a", label: "Field Training A (§19 · 60%)" },
  { value: "field_training_b", label: "Field Training B (§19 · 75%)" },
  { value: "graduation_project_i", label: "Graduation Project I (§20 · 80%)" },
  { value: "graduation_project_ii", label: "Graduation Project II (§20 · 90%)" },
];

export default function CapstonePage() {
  const { t } = useLanguage();
  const { token } = useAuth();
  const [entries, setEntries] = useState<any[]>([]);
  const [elig, setElig] = useState<Record<string, any>>({});
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    stage: "field_training_a",
    semester_code: "",
    supervisor_name: "",
    supervisor_email: "",
    title: "",
    company_or_lab: "",
  });

  async function reload() {
    if (!token) return;
    try {
      const [a, b] = await Promise.all([getMyCapstone(token), getCapstoneEligibility(token)]);
      setEntries(a.entries);
      setElig(b);
    } catch (e: any) {
      setErr(e.message);
    }
  }

  useEffect(() => { reload(); /* eslint-disable-next-line */ }, [token]);

  async function enroll(e: React.FormEvent) {
    e.preventDefault();
    if (!token) return;
    setBusy(true);
    setErr(null);
    try {
      await enrollCapstone(token, form);
      await reload();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function toggleMilestone(id: string, completed: boolean) {
    if (!token) return;
    try {
      await patchMilestone(token, id, { completed });
      await reload();
    } catch (e: any) {
      setErr(e.message);
    }
  }

  const stageElig = elig[form.stage];

  return (
    <AppLayout activePath="/capstone" userName="Capstone">
      <main className="px-4 md:px-8 lg:px-16 py-8 space-y-6">
        <header>
          <h1 className="text-3xl font-bold">{t("cap.title")}</h1>
          <p className="text-sm text-zinc-500 dark:text-zinc-400">{t("cap.subtitle")}</p>
        </header>

        {err && <div className="rounded-lg bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300 px-3 py-2 text-sm">{err}</div>}

        <section className="grid grid-cols-1 md:grid-cols-4 gap-3">
          {STAGES.map((s) => {
            const e = elig[s.value];
            return (
              <div key={s.value} className="rounded-xl border border-zinc-200 dark:border-zinc-700 dark:border-zinc-800 p-3">
                <div className="text-xs text-zinc-500 dark:text-zinc-400 uppercase">{s.label}</div>
                {e ? (
                  <>
                    <div className={`text-sm font-semibold mt-1 ${e.eligible ? "text-emerald-600 dark:text-emerald-400" : "text-amber-600 dark:text-amber-400"}`}>
                      {e.eligible ? "Eligible" : "Not yet"}
                    </div>
                    <div className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
                      {e.completion_pct?.toFixed?.(1) ?? e.completion_pct}% of {e.threshold_pct}%
                    </div>
                  </>
                ) : (
                  <div className="text-xs text-zinc-500 dark:text-zinc-400">Loading…</div>
                )}
              </div>
            );
          })}
        </section>

        <section className="rounded-xl border border-zinc-200 dark:border-zinc-700 dark:border-zinc-800 p-4">
          <h2 className="font-semibold mb-3">{t("cap.register")}</h2>
          <form onSubmit={enroll} className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <select
              className="rounded border border-zinc-300 dark:border-zinc-600 dark:border-zinc-700 bg-transparent px-3 py-2"
              value={form.stage}
              onChange={(e) => setForm({ ...form, stage: e.target.value })}
            >
              {STAGES.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
            <input
              placeholder={t("cap.semEg")}
              required
              className="rounded border border-zinc-300 dark:border-zinc-600 dark:border-zinc-700 bg-transparent px-3 py-2"
              value={form.semester_code}
              onChange={(e) => setForm({ ...form, semester_code: e.target.value })}
            />
            <input
              placeholder={t("cap.supName")}
              className="rounded border border-zinc-300 dark:border-zinc-600 dark:border-zinc-700 bg-transparent px-3 py-2"
              value={form.supervisor_name}
              onChange={(e) => setForm({ ...form, supervisor_name: e.target.value })}
            />
            <input
              placeholder={t("cap.supEmail")}
              className="rounded border border-zinc-300 dark:border-zinc-600 dark:border-zinc-700 bg-transparent px-3 py-2"
              value={form.supervisor_email}
              onChange={(e) => setForm({ ...form, supervisor_email: e.target.value })}
            />
            <input
              placeholder={t("cap.projTitle")}
              className="md:col-span-2 rounded border border-zinc-300 dark:border-zinc-600 dark:border-zinc-700 bg-transparent px-3 py-2"
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
            />
            <input
              placeholder={t("cap.company")}
              className="md:col-span-2 rounded border border-zinc-300 dark:border-zinc-600 dark:border-zinc-700 bg-transparent px-3 py-2"
              value={form.company_or_lab}
              onChange={(e) => setForm({ ...form, company_or_lab: e.target.value })}
            />
            {stageElig && !stageElig.eligible && (
              <div className="md:col-span-2 text-xs rounded bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300 px-3 py-2">
                {stageElig.message}
              </div>
            )}
            <button
              disabled={busy || (stageElig && !stageElig.eligible)}
              className="rounded bg-[#B8001F] text-white px-4 py-2 disabled:opacity-50"
              type="submit"
            >
              {busy ? "Registering…" : "Register"}
            </button>
          </form>
        </section>

        <section className="space-y-4">
          {entries.map((entry) => (
            <div key={entry.id} className="rounded-xl border border-zinc-200 dark:border-zinc-700 dark:border-zinc-800 p-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-semibold capitalize">{entry.stage.replace(/_/g, " ")}</h3>
                  <div className="text-xs text-zinc-500 dark:text-zinc-400">
                    {entry.semester_code} · {entry.status}
                    {entry.title && <> · {entry.title}</>}
                  </div>
                </div>
                {entry.grade_letter && (
                  <span className="rounded bg-emerald-100 text-emerald-700 dark:text-emerald-300 px-2 py-0.5 text-xs font-medium">
                    {entry.grade_letter}
                  </span>
                )}
              </div>
              <ul className="mt-3 text-sm space-y-1">
                {entry.milestones.map((m: any) => (
                  <li key={m.id} className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={m.completed}
                      onChange={(e) => toggleMilestone(m.id, e.target.checked)}
                    />
                    <span className={m.completed ? "line-through text-zinc-500 dark:text-zinc-400" : ""}>{m.name}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </section>
      </main>
    </AppLayout>
  );
}
