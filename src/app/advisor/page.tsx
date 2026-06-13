"use client";

import { useEffect, useState } from "react";
import AppLayout from "@/components/layout/AppLayout";
import { useLanguage } from "@/hooks/useLanguage";
import { useAuth } from "@/hooks/useAuth";
import { getMyAdvisor, getMyApprovals, requestApproval } from "@/lib/api";

const APPROVAL_TYPES = [
  { value: "registration", label: "Semester Registration" },
  { value: "add", label: "Add Course" },
  { value: "drop", label: "Drop Course" },
  { value: "withdrawal", label: "Withdrawal" },
  { value: "load_adjustment", label: "Load Adjustment" },
  { value: "retake", label: "Retake" },
  { value: "freeze", label: "Freeze Semester" },
  { value: "final_chance", label: "Final Chance" },
];

export default function AdvisorPage() {
  const { t } = useLanguage();
  const { token } = useAuth();
  const [advisor, setAdvisor] = useState<any>(null);
  const [approvals, setApprovals] = useState<any[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [form, setForm] = useState({ type: "registration", semester_code: "", justification: "" });
  const [busy, setBusy] = useState(false);

  async function reload() {
    if (!token) return;
    try {
      const [a, b] = await Promise.all([getMyAdvisor(token), getMyApprovals(token)]);
      setAdvisor(a);
      setApprovals(b);
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
      await requestApproval(token, {
        type: form.type,
        semester_code: form.semester_code || undefined,
        justification: form.justification || undefined,
      });
      setForm({ ...form, justification: "" });
      await reload();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppLayout activePath="/advisor" userName="Advisor">
      <main className="px-4 md:px-8 lg:px-16 py-8 space-y-6">
        <header>
          <h1 className="text-3xl font-bold">{t("adv.title")}</h1>
          <p className="text-sm text-zinc-500 dark:text-zinc-400">{t("adv.subtitle")}</p>
        </header>

        {err && <div className="rounded-lg bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300 px-3 py-2 text-sm">{err}</div>}

        <section className="rounded-xl border border-zinc-200 dark:border-zinc-700 dark:border-zinc-800 p-4">
          <h2 className="font-semibold mb-2">{t("adv.assigned")}</h2>
          {advisor ? (
            <div className="text-sm space-y-1">
              <div><strong>{advisor.full_name}</strong> — {advisor.department ?? "—"}</div>
              <div className="text-zinc-500 dark:text-zinc-400">{advisor.email}</div>
              {advisor.office && <div className="text-zinc-500 dark:text-zinc-400">Office: {advisor.office}</div>}
            </div>
          ) : (
            <div className="text-sm text-zinc-500 dark:text-zinc-400">
              No advisor assigned yet. Contact the registrar.
            </div>
          )}
        </section>

        <section className="rounded-xl border border-zinc-200 dark:border-zinc-700 dark:border-zinc-800 p-4">
          <h2 className="font-semibold mb-3">{t("adv.request")}</h2>
          <form onSubmit={submit} className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <select
              className="rounded border border-zinc-300 dark:border-zinc-600 dark:border-zinc-700 bg-transparent px-3 py-2"
              value={form.type}
              onChange={(e) => setForm({ ...form, type: e.target.value })}
            >
              {APPROVAL_TYPES.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
            <input
              placeholder={t("adv.semEg")}
              className="rounded border border-zinc-300 dark:border-zinc-600 dark:border-zinc-700 bg-transparent px-3 py-2"
              value={form.semester_code}
              onChange={(e) => setForm({ ...form, semester_code: e.target.value })}
            />
            <button
              disabled={busy}
              className="rounded bg-[#B8001F] text-white px-4 py-2 disabled:opacity-50"
              type="submit"
            >
              {busy ? "Submitting…" : "Submit"}
            </button>
            <textarea
              placeholder={t("adv.just")}
              className="md:col-span-3 rounded border border-zinc-300 dark:border-zinc-600 dark:border-zinc-700 bg-transparent px-3 py-2"
              rows={3}
              value={form.justification}
              onChange={(e) => setForm({ ...form, justification: e.target.value })}
            />
          </form>
        </section>

        <section className="rounded-xl border border-zinc-200 dark:border-zinc-700 dark:border-zinc-800 p-4">
          <h2 className="font-semibold mb-3">{t("adv.my")}</h2>
          {approvals.length === 0 ? (
            <div className="text-sm text-zinc-500 dark:text-zinc-400">{t("adv.none")}</div>
          ) : (
            <ul className="divide-y divide-zinc-200 dark:divide-zinc-800 text-sm">
              {approvals.map((a) => (
                <li key={a.id} className="py-2 flex items-start justify-between gap-4">
                  <div>
                    <div className="font-medium capitalize">{a.type.replace(/_/g, " ")}</div>
                    <div className="text-xs text-zinc-500 dark:text-zinc-400">
                      {a.semester_code && <>Semester: {a.semester_code} · </>}
                      {new Date(a.created_at).toLocaleDateString()}
                    </div>
                    {a.advisor_comment && (
                      <div className="text-xs mt-1">Note: {a.advisor_comment}</div>
                    )}
                  </div>
                  <StatusBadge status={a.status} />
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
    status === "cancelled" ? "bg-zinc-100 dark:bg-zinc-800 text-zinc-500 dark:text-zinc-400" :
    "bg-amber-100 text-amber-700 dark:text-amber-300";
  return <span className={`rounded px-2 py-0.5 text-xs font-medium capitalize ${color}`}>{status}</span>;
}
