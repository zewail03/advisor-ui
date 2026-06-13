"use client";

import { useEffect, useState } from "react";
import AppLayout from "@/components/layout/AppLayout";
import { useLanguage } from "@/hooks/useLanguage";
import { useAuth } from "@/hooks/useAuth";
import { getMyPetitions, getPetitionEligibility, submitPetition } from "@/lib/api";

const TYPES = [
  { value: "final_chance", label: "Final Chance (§14)" },
  { value: "freeze", label: "Freeze Semester (§15)" },
  { value: "transfer_in", label: "Transfer Into AIU (§16)" },
  { value: "transfer_between_programs", label: "Transfer Between Programs (§16)" },
  { value: "grade_appeal", label: "Grade Appeal (§27)" },
];

export default function PetitionsPage() {
  const { t } = useLanguage();
  const { token } = useAuth();
  const [petitions, setPetitions] = useState<any[]>([]);
  const [elig, setElig] = useState<Record<string, any>>({});
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState<any>({
    type: "freeze",
    subject: "",
    body: "",
    freeze_semester_code: "",
    enrollment_id: "",
    current_grade: "",
    requested_grade: "",
    target_program_code: "",
  });

  async function reload() {
    if (!token) return;
    try {
      const [p, e] = await Promise.all([getMyPetitions(token), getPetitionEligibility(token)]);
      setPetitions(p);
      setElig(e);
    } catch (e: any) {
      setErr(e.message);
    }
  }

  useEffect(() => { reload(); /* eslint-disable-next-line */ }, [token]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!token) return;
    setBusy(true);
    setErr(null);
    try {
      const payload: any = { type: form.type, subject: form.subject, body: form.body };
      if (form.type === "freeze") payload.freeze_semester_code = form.freeze_semester_code;
      if (form.type === "transfer_between_programs") payload.target_program_code = form.target_program_code;
      if (form.type === "grade_appeal") {
        payload.enrollment_id = form.enrollment_id;
        payload.current_grade = form.current_grade;
        payload.requested_grade = form.requested_grade;
      }
      await submitPetition(token, payload);
      setForm({ ...form, subject: "", body: "" });
      await reload();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  const currentElig = elig[form.type];

  return (
    <AppLayout activePath="/petitions" userName="Petitions">
      <main className="px-4 md:px-8 lg:px-16 py-8 space-y-6">
        <header>
          <h1 className="text-3xl font-bold">{t("pet.title")}</h1>
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            {t("pet.subtitle")}
          </p>
        </header>

        {err && <div className="rounded-lg bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300 px-3 py-2 text-sm">{err}</div>}

        <section className="rounded-xl border border-zinc-200 dark:border-zinc-700 dark:border-zinc-800 p-4">
          <h2 className="font-semibold mb-3">{t("pet.new")}</h2>
          <form onSubmit={submit} className="space-y-3">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <select
                className="rounded border border-zinc-300 dark:border-zinc-600 dark:border-zinc-700 bg-transparent px-3 py-2"
                value={form.type}
                onChange={(e) => setForm({ ...form, type: e.target.value })}
              >
                {TYPES.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
              <input
                placeholder={t("pet.subject")}
                required
                className="rounded border border-zinc-300 dark:border-zinc-600 dark:border-zinc-700 bg-transparent px-3 py-2"
                value={form.subject}
                onChange={(e) => setForm({ ...form, subject: e.target.value })}
              />
            </div>

            {currentElig && (
              <div
                className={`text-xs rounded px-3 py-2 ${
                  currentElig.eligible ? "bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300" : "bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300"
                }`}
              >
                {currentElig.eligible ? "Eligible." : `Not eligible — ${currentElig.message}`}
              </div>
            )}

            {form.type === "freeze" && (
              <input
                placeholder={t("pet.freezeSem")}
                className="w-full rounded border border-zinc-300 dark:border-zinc-600 dark:border-zinc-700 bg-transparent px-3 py-2"
                value={form.freeze_semester_code}
                onChange={(e) => setForm({ ...form, freeze_semester_code: e.target.value })}
              />
            )}
            {form.type === "transfer_between_programs" && (
              <input
                placeholder={t("pet.target")}
                className="w-full rounded border border-zinc-300 dark:border-zinc-600 dark:border-zinc-700 bg-transparent px-3 py-2"
                value={form.target_program_code}
                onChange={(e) => setForm({ ...form, target_program_code: e.target.value })}
              />
            )}
            {form.type === "grade_appeal" && (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <input
                  placeholder={t("pet.enrId")}
                  className="rounded border border-zinc-300 dark:border-zinc-600 dark:border-zinc-700 bg-transparent px-3 py-2"
                  value={form.enrollment_id}
                  onChange={(e) => setForm({ ...form, enrollment_id: e.target.value })}
                />
                <input
                  placeholder={t("pet.curGrade")}
                  className="rounded border border-zinc-300 dark:border-zinc-600 dark:border-zinc-700 bg-transparent px-3 py-2"
                  value={form.current_grade}
                  onChange={(e) => setForm({ ...form, current_grade: e.target.value })}
                />
                <input
                  placeholder={t("pet.reqGrade")}
                  className="rounded border border-zinc-300 dark:border-zinc-600 dark:border-zinc-700 bg-transparent px-3 py-2"
                  value={form.requested_grade}
                  onChange={(e) => setForm({ ...form, requested_grade: e.target.value })}
                />
              </div>
            )}

            <textarea
              placeholder={t("pet.reason")}
              rows={4}
              className="w-full rounded border border-zinc-300 dark:border-zinc-600 dark:border-zinc-700 bg-transparent px-3 py-2"
              value={form.body}
              onChange={(e) => setForm({ ...form, body: e.target.value })}
            />
            <button
              disabled={busy || (currentElig && !currentElig.eligible)}
              className="rounded bg-[#B8001F] text-white px-4 py-2 disabled:opacity-50"
              type="submit"
            >
              {busy ? "Submitting…" : "Submit petition"}
            </button>
          </form>
        </section>

        <section className="rounded-xl border border-zinc-200 dark:border-zinc-700 dark:border-zinc-800 p-4">
          <h2 className="font-semibold mb-3">{t("pet.my")}</h2>
          {petitions.length === 0 ? (
            <div className="text-sm text-zinc-500 dark:text-zinc-400">{t("pet.none")}</div>
          ) : (
            <ul className="divide-y divide-zinc-200 dark:divide-zinc-800 text-sm">
              {petitions.map((p) => (
                <li key={p.id} className="py-2 flex items-start justify-between gap-4">
                  <div>
                    <div className="font-medium">{p.subject}</div>
                    <div className="text-xs text-zinc-500 dark:text-zinc-400">
                      {p.type.replace(/_/g, " ")} · {new Date(p.submitted_at).toLocaleDateString()}
                    </div>
                    {p.decision_comment && (
                      <div className="text-xs mt-1">Decision: {p.decision_comment}</div>
                    )}
                  </div>
                  <StatusBadge status={p.status} />
                </li>
              ))}
            </ul>
          )}
        </section>
      </main>
    </AppLayout>
  );
}

function StatusBadge({ status }: { status: string }) {
  const color =
    status === "approved" ? "bg-emerald-100 text-emerald-700 dark:text-emerald-300" :
    status === "rejected" ? "bg-red-100 text-red-700 dark:text-red-300" :
    status === "under_review" ? "bg-blue-100 text-blue-700 dark:text-blue-300" :
    status === "withdrawn" ? "bg-zinc-100 dark:bg-zinc-800 text-zinc-500 dark:text-zinc-400" :
    "bg-amber-100 text-amber-700 dark:text-amber-300";
  return <span className={`rounded px-2 py-0.5 text-xs font-medium capitalize ${color}`}>{status.replace(/_/g, " ")}</span>;
}
